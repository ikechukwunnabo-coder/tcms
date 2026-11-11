import csv
import io
import tempfile
from datetime import date, timedelta

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.billing.models import CorporateAccount
from apps.catalogue.models import Course
from apps.certification import services as cert
from apps.certification.models import (
    Certificate,
    CertificateReminder,
    CertificateSequence,
    OpitoFile,
)
from apps.common.enums import CertificateReminderStatus, ExpiryTypeCode, RoleCode
from apps.delivery.models import TrainingRecord
from apps.learners.models import Learner
from apps.medicals.models import Medical
from apps.medicals.services import MedicalGateError
from apps.portal.models import PortalAccount
from apps.workflow.models import WorkflowStatus


class CertificateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)
        cls.course = Course.objects.get(course_code="FIRST-AID")  # validity 3, non-OPITO
        cls.learner = Learner.objects.create(
            badge_no="C001", surname="Roe", first_name="Jane", birth_date=date(1990, 5, 6)
        )
        cls.record = TrainingRecord.objects.create(
            learner=cls.learner,
            course=cls.course,
            status=WorkflowStatus.objects.get(pk=9),
            start_date=date(2026, 1, 13),
        )
        cls.on_date = date(2026, 1, 1)

    def _valid_medical(self):
        Medical.objects.create(
            learner=self.learner,
            issued_date=date(2025, 1, 1),
            expiry_date=date(2027, 1, 1),
            active=True,
            fitness="fit",
        )

    def test_interim_number_r_cert_01(self):
        number = cert.interim_certificate_no(self.record, today=self.on_date)
        self.assertTrue(number.startswith("T26"))
        self.assertTrue(number.endswith("90"))  # birth year 1990 -> 90

    def test_allocate_increments_r_cert_02(self):
        first = cert.allocate_certificate_number(
            course_year=2026, item_id=self.course.pk, birth_date=self.learner.birth_date
        )
        second = cert.allocate_certificate_number(
            course_year=2026, item_id=self.course.pk, birth_date=self.learner.birth_date
        )
        self.assertNotEqual(first, second)
        seq = CertificateSequence.objects.get(course_year=2026, item_id=self.course.pk)
        self.assertEqual(seq.last_number, 2)

    def test_issue_requires_medical_r_cert_04(self):
        with self.assertRaises(MedicalGateError):
            cert.issue_certificate(self.record, on_date=self.on_date)

    def test_issue_with_medical(self):
        self._valid_medical()
        certificate = cert.issue_certificate(self.record, on_date=self.on_date)
        self.assertTrue(certificate.certificate_no.startswith("T26"))
        self.assertEqual(certificate.expiry_date, date(2029, 1, 12))

    def test_signature_and_seal_r_wf_07(self):
        self._valid_medical()
        certificate = cert.issue_certificate(self.record, on_date=self.on_date)
        cert.apply_signature_and_seal(certificate)
        certificate.refresh_from_db()
        self.assertTrue(certificate.signature_applied)
        self.assertTrue(certificate.seal_applied)
        self.assertIsNotNone(certificate.md_approved_at)

    def test_no_expiry_course_has_no_expiry_date(self):
        self._valid_medical()
        self.course.expiry_type = ExpiryTypeCode.NONE
        self.course.save(update_fields=["expiry_type"])
        certificate = cert.issue_certificate(self.record, on_date=self.on_date)
        self.assertIsNone(certificate.expiry_date)

    def test_foet_expiry_uses_previous_expiry(self):
        self._valid_medical()
        record = TrainingRecord.objects.create(
            learner=self.learner,
            course=Course.objects.get(course_code="FOET"),
            status=WorkflowStatus.objects.get(pk=9),
            start_date=date(2026, 1, 13),
            prev_expiry=date(2026, 6, 30),
        )
        certificate = cert.issue_certificate(record, on_date=self.on_date)
        self.assertEqual(certificate.expiry_date, date(2030, 6, 30))


class CertificateRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)
        cls.course = Course.objects.get(course_code="BOSIET")
        cls.learner = Learner.objects.create(
            badge_no="PDF01", surname="Okafor", first_name="Ada", birth_date=date(1991, 4, 2)
        )
        cls.record = TrainingRecord.objects.create(
            learner=cls.learner,
            course=cls.course,
            status=WorkflowStatus.objects.get(pk=9),
            start_date=date(2026, 2, 2),
        )

    def _certificate(self):
        Medical.objects.create(
            learner=self.learner,
            issued_date=date(2025, 1, 1),
            expiry_date=date(2027, 1, 1),
            active=True,
            fitness="fit",
        )
        return cert.issue_certificate(self.record, on_date=date(2026, 2, 1))

    def test_renders_a_real_pdf(self):
        certificate = self._certificate()
        data = cert.certificate_pdf_bytes(certificate)
        self.assertTrue(data.startswith(b"%PDF-"))
        self.assertGreater(len(data), 2000)

    def test_renders_signed_and_sealed_without_artwork(self):
        certificate = self._certificate()
        cert.apply_signature_and_seal(certificate)
        certificate.refresh_from_db()
        data = cert.certificate_pdf_bytes(certificate)
        self.assertTrue(data.startswith(b"%PDF-"))

    def test_stored_artefact_is_preferred(self):
        certificate = self._certificate()
        key = f"test_certificates/{certificate.certificate_no}.pdf"
        storage = default_storage
        storage.save(key, ContentFile(b"%PDF-stored"))
        try:
            certificate.object_key = key
            certificate.save(update_fields=["object_key"])
            self.assertEqual(cert.certificate_pdf_bytes(certificate), b"%PDF-stored")
        finally:
            storage.delete(key)


class CertificateReminderServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)
        cls.course = Course.objects.get(course_code="BOSIET")
        cls.learner = Learner.objects.create(
            badge_no="R100", surname="Doe", first_name="John", birth_date=date(1990, 1, 1)
        )
        cls.record = TrainingRecord.objects.create(
            learner=cls.learner,
            course=cls.course,
            status=WorkflowStatus.objects.get(pk=9),
            start_date=date(2026, 1, 13),
        )
        cls.expiry = date(2026, 6, 30)

    def _cert(self, no="T26100", expiry=None, learner=None):
        return Certificate.objects.create(
            training_record=self.record,
            learner=learner or self.learner,
            certificate_no=no,
            issued_at=timezone.now(),
            expiry_date=expiry if expiry is not None else self.expiry,
        )

    def _verified_portal(self, email="john@example.com"):
        user = User.objects.create_user("john", email=email, password="pw")
        user.email_verified = True
        user.save(update_fields=["email_verified"])
        PortalAccount.objects.create(user=user, learner=self.learner)
        return user

    def test_schedule_creates_offset_rows(self):
        certificate = self._cert()
        rows = cert.schedule_reminders(certificate)
        self.assertEqual([r.offset_days for r in rows], [90, 60, 30, 0])
        self.assertEqual(rows[0].due_on, self.expiry - timedelta(days=90))
        self.assertEqual(rows[-1].due_on, self.expiry)

    def test_schedule_skips_no_expiry(self):
        certificate = Certificate.objects.create(
            training_record=self.record,
            learner=self.learner,
            certificate_no="T26199",
            issued_at=timezone.now(),
            expiry_date=None,
        )
        self.assertEqual(cert.schedule_reminders(certificate), [])

    def test_schedule_is_idempotent(self):
        certificate = self._cert()
        cert.schedule_reminders(certificate)
        cert.schedule_reminders(certificate)
        self.assertEqual(CertificateReminder.objects.filter(certificate=certificate).count(), 4)

    def test_recipient_uses_verified_portal_email(self):
        self._verified_portal()
        certificate = self._cert()
        self.assertEqual(cert.resolve_reminder_recipient(certificate), "john@example.com")

    def test_recipient_for_nominee_is_lead_email(self):
        lead = User.objects.create_user("lead", email="lead@corp.example", password="pw")
        account = CorporateAccount.objects.create(
            name="Acme", lead_user=lead, lead_email="lead@corp.example"
        )
        self.learner.corporate_account = account
        self.learner.save(update_fields=["corporate_account"])
        certificate = self._cert()
        self.assertEqual(cert.resolve_reminder_recipient(certificate), "lead@corp.example")

    def test_validity_status_ladder(self):
        certificate = self._cert()
        self.assertEqual(cert.validity_status(certificate, date(2026, 1, 1)), "valid")
        self.assertEqual(cert.validity_status(certificate, date(2026, 4, 2)), "expiring_soon")
        self.assertEqual(cert.validity_status(certificate, date(2026, 7, 1)), "expired")
        successor = self._cert(no="T26101")
        certificate.renewed_by_certificate = successor
        certificate.save(update_fields=["renewed_by_certificate"])
        self.assertEqual(cert.validity_status(certificate, date(2026, 1, 1)), "renewed")

    def test_release_schedules_reminders_and_is_idempotent(self):
        certificate = self._cert()
        cert.release(certificate)
        released = certificate.released_at
        self.assertIsNotNone(released)
        cert.release(certificate)
        certificate.refresh_from_db()
        self.assertEqual(certificate.released_at, released)
        self.assertEqual(certificate.reminders.count(), 4)

    def test_run_reminders_sends_due_only(self):
        self._verified_portal()
        certificate = self._cert()
        cert.release(certificate)
        # Before the 90-day window nothing is due except the on-expiry-90 row:
        result = cert.run_reminders(date(2026, 3, 1))
        self.assertEqual(result["due"], 0)
        result = cert.run_reminders(date(2026, 4, 1))  # due_on = expiry - 90 = Apr 1
        self.assertEqual(result["sent"], 1)
        row = certificate.reminders.get(offset_days=90)
        self.assertEqual(row.status, CertificateReminderStatus.SENT)
        self.assertIsNotNone(row.sent_at)

    def test_run_reminders_suppresses_renewed(self):
        self._verified_portal()
        certificate = self._cert()
        successor = self._cert(no="T26102")
        certificate.renewed_by_certificate = successor
        certificate.save(update_fields=["renewed_by_certificate"])
        cert.release(certificate)
        result = cert.run_reminders(date(2026, 6, 30))
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["suppressed"], 4)
        self.assertFalse(
            certificate.reminders.filter(status=CertificateReminderStatus.PENDING).exists()
        )

    def test_run_reminders_skips_unreleased(self):
        self._verified_portal()
        certificate = self._cert()
        cert.schedule_reminders(certificate)
        result = cert.run_reminders(date(2026, 6, 30))
        self.assertEqual(result["skipped"], 4)
        self.assertEqual(result["sent"], 0)

    def test_run_reminders_fails_without_recipient(self):
        certificate = self._cert()
        cert.release(certificate)
        result = cert.run_reminders(date(2026, 6, 30))
        self.assertEqual(result["failed"], 4)

    def test_manual_reminder_requires_recipient(self):
        certificate = self._cert()
        with self.assertRaises(cert.NoReminderRecipient):
            cert.send_reminder_now(certificate)

    def test_issue_links_renewed_certificate(self):
        Medical.objects.create(
            learner=self.learner,
            issued_date=date(2025, 1, 1),
            expiry_date=date(2027, 1, 1),
            active=True,
            fitness="fit",
        )
        previous = self._cert(no="T26103", expiry=date(2025, 1, 12))
        self.record.prev_expiry = date(2025, 1, 12)
        self.record.save(update_fields=["prev_expiry"])
        new = cert.issue_certificate(self.record, on_date=date(2026, 1, 1))
        previous.refresh_from_db()
        self.assertEqual(previous.renewed_by_certificate_id, new.pk)


class CertificateReminderAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)
        cls.course = Course.objects.get(course_code="BOSIET")
        cls.learner = Learner.objects.create(
            badge_no="R200", surname="Smith", first_name="Ann", birth_date=date(1991, 2, 2)
        )
        cls.record = TrainingRecord.objects.create(
            learner=cls.learner,
            course=cls.course,
            status=WorkflowStatus.objects.get(pk=9),
            start_date=date(2026, 1, 13),
        )
        cls.admin = User.objects.create_user("admin2", password="pw")
        cls.admin.roles.add(Role.objects.get(pk=RoleCode.ADMIN))
        cls.printer = User.objects.create_user("printer2", password="pw")
        cls.printer.roles.add(Role.objects.get(pk=RoleCode.PRINTER))

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def _cert(self):
        return Certificate.objects.create(
            training_record=self.record,
            learner=self.learner,
            certificate_no="T26200",
            issued_at=timezone.now(),
            expiry_date=date(2026, 6, 30),
        )

    def test_admin_can_release(self):
        certificate = self._cert()
        self._auth(self.admin)
        response = self.client.post(f"/api/v1/certificates/{certificate.pk}/release/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["released_at"])

    def test_printer_cannot_release(self):
        certificate = self._cert()
        self._auth(self.printer)
        response = self.client.post(f"/api/v1/certificates/{certificate.pk}/release/")
        self.assertEqual(response.status_code, 403)

    def test_reminders_endpoint_lists_scheduled(self):
        certificate = self._cert()
        cert.release(certificate)
        self._auth(self.admin)
        response = self.client.get(f"/api/v1/certificates/{certificate.pk}/reminders/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

    def test_remind_requires_recipient(self):
        certificate = self._cert()
        self._auth(self.admin)
        response = self.client.post(f"/api/v1/certificates/{certificate.pk}/remind/")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["error"], "no_reminder_recipient")




@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class CertificateDocumentAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)
        cls.course = Course.objects.get(course_code="FIRST-AID")
        cls.opito_course = Course.objects.get(course_code="BOSIET")
        cls.learner = Learner.objects.create(
            badge_no="DOC1", surname="Stone", first_name="Mia", birth_date=date(1990, 1, 1)
        )
        Medical.objects.create(
            learner=cls.learner,
            issued_date=date(2025, 1, 1),
            expiry_date=date(2027, 1, 1),
            active=True,
            fitness="fit",
        )
        cls.record = TrainingRecord.objects.create(
            learner=cls.learner,
            course=cls.course,
            status=WorkflowStatus.objects.get(pk=9),
            start_date=date(2026, 1, 13),
        )
        cls.opito_record = TrainingRecord.objects.create(
            learner=cls.learner,
            course=cls.opito_course,
            status=WorkflowStatus.objects.get(pk=9),
            start_date=date(2026, 1, 13),
        )
        cls.admin = User.objects.create_user("docadmin", password="pw")
        cls.admin.roles.add(Role.objects.get(pk=RoleCode.ADMIN))
        cls.printer = User.objects.create_user("docprinter", password="pw")
        cls.printer.roles.add(Role.objects.get(pk=RoleCode.PRINTER))
        cls.viewer = User.objects.create_user("docviewer", password="pw")
        cls.viewer.roles.add(Role.objects.get(pk=RoleCode.FRONT_DESK))

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def _issue(self, record):
        self._auth(self.admin)
        return self.client.post(
            "/api/v1/certificates/issue/", {"training_record": record.pk}, format="json"
        )

    def test_non_opito_generate_head_and_download(self):
        response = self._issue(self.record)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["format"], 1)
        self.assertEqual(response.data["source"], "generated")
        certificate_id = response.data["id"]

        generated = self.client.post(f"/api/v1/certificates/{certificate_id}/generate/")
        self.assertEqual(generated.status_code, 200)
        self.assertTrue(generated.data["object_key"])

        head = self.client.head(f"/api/v1/certificates/{certificate_id}/document/")
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head["Content-Type"], "application/pdf")
        self.assertGreater(int(head["Content-Length"]), 0)

        download = self.client.get(f"/api/v1/certificates/{certificate_id}/document/")
        self.assertEqual(download.status_code, 200)
        self.assertTrue(b"".join(download.streaming_content).startswith(b"%PDF-"))

    def test_read_only_role_can_download_but_not_manage_documents(self):
        response = self._issue(self.record)
        certificate_id = response.data["id"]
        self._auth(self.viewer)
        self.assertEqual(
            self.client.head(f"/api/v1/certificates/{certificate_id}/document/").status_code,
            200,
        )
        self.assertEqual(
            self.client.post(f"/api/v1/certificates/{certificate_id}/generate/").status_code,
            403,
        )
        self.assertEqual(
            self.client.post(f"/api/v1/certificates/{certificate_id}/print/").status_code,
            403,
        )

    def test_opito_upload_requires_write_role(self):
        response = self._issue(self.opito_record)
        certificate_id = response.data["id"]
        self._auth(self.viewer)
        upload = SimpleUploadedFile(
            "opito.pdf", b"%PDF-1.4\n% test certificate\n", content_type="application/pdf"
        )
        denied = self.client.post(
            f"/api/v1/certificates/{certificate_id}/upload/",
            {"file": upload},
            format="multipart",
        )
        self.assertEqual(denied.status_code, 403)

    def test_opito_issue_upload_and_download(self):
        response = self._issue(self.opito_record)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["format"], 4)
        self.assertTrue(response.data["certificate_no"].startswith("OPITO-"))
        self.assertEqual(CertificateSequence.objects.count(), 0)
        certificate_id = response.data["id"]

        missing = self.client.get(f"/api/v1/certificates/{certificate_id}/document/")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.data["error"], "certificate_document_missing")

        generated = self.client.post(f"/api/v1/certificates/{certificate_id}/generate/")
        self.assertEqual(generated.status_code, 422)

        upload = SimpleUploadedFile(
            "opito.pdf", b"%PDF-1.4\n% test certificate\n", content_type="application/pdf"
        )
        uploaded = self.client.post(
            f"/api/v1/certificates/{certificate_id}/upload/",
            {
                "file": upload,
                "certificate_no": "OPITO-EXT-1",
                "opito_learner_id": "OL-99",
            },
            format="multipart",
        )
        self.assertEqual(uploaded.status_code, 200)
        self.assertEqual(uploaded.data["source"], "uploaded")
        self.assertEqual(uploaded.data["certificate_no"], "OPITO-EXT-1")
        self.assertEqual(uploaded.data["opito_learner_id"], "OL-99")

        download = self.client.get(f"/api/v1/certificates/{certificate_id}/document/")
        self.assertEqual(download.status_code, 200)

    def test_upload_rejects_non_pdf(self):
        response = self._issue(self.opito_record)
        certificate_id = response.data["id"]
        upload = SimpleUploadedFile("bad.pdf", b"not a pdf", content_type="application/pdf")
        rejected = self.client.post(
            f"/api/v1/certificates/{certificate_id}/upload/",
            {"file": upload},
            format="multipart",
        )
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(rejected.data["error"], "invalid_certificate_document")

    def test_print_auto_completes_when_course_has_no_id_card(self):
        response = self._issue(self.record)
        certificate_id = response.data["id"]
        self._auth(self.printer)
        printed = self.client.post(f"/api/v1/certificates/{certificate_id}/print/")
        self.assertEqual(printed.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status_id, 12)

    def test_print_certificate_then_id_card_completes(self):
        response = self._issue(self.opito_record)
        certificate_id = response.data["id"]
        self._auth(self.printer)
        self.assertEqual(
            self.client.post(f"/api/v1/certificates/{certificate_id}/print/").status_code, 200
        )
        self.opito_record.refresh_from_db()
        self.assertEqual(self.opito_record.status_id, 10)

        issued = self.client.post(
            "/api/v1/id-cards/issue/",
            {"training_record": self.opito_record.pk},
            format="json",
        )
        self.assertEqual(issued.status_code, 201)
        self.assertTrue(issued.data["card_no"].startswith("ID"))
        card_id = issued.data["id"]
        self.assertEqual(
            self.client.post(f"/api/v1/id-cards/{card_id}/generate/").status_code, 200
        )
        self.assertEqual(
            self.client.post(f"/api/v1/id-cards/{card_id}/print/").status_code, 200
        )
        self.opito_record.refresh_from_db()
        self.assertEqual(self.opito_record.status_id, 12)

        download = self.client.get(f"/api/v1/id-cards/{card_id}/document/")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["Content-Type"], "application/pdf")


class PublicCertificateVerificationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)
        cls.course = Course.objects.get(course_code="FIRST-AID")
        cls.learner = Learner.objects.create(
            badge_no="VER01",
            surname="Adeyemi",
            first_name="Tola",
            birth_date=date(1992, 8, 9),
        )
        cls.record = TrainingRecord.objects.create(
            learner=cls.learner,
            course=cls.course,
            status=WorkflowStatus.objects.get(pk=9),
            start_date=date(2026, 1, 13),
        )

    def _certificate(self, number="T2600001", **overrides):
        values = {
            "training_record": self.record,
            "learner": self.learner,
            "certificate_no": number,
            "issued_at": timezone.now(),
            "expiry_date": date.today() + timedelta(days=365),
        }
        values.update(overrides)
        return Certificate.objects.create(**values)

    def _get(self, identifier):
        return self.client.get(f"/api/v1/verify/{identifier}/")

    def test_verifies_by_certificate_number_without_authentication(self):
        self._certificate()
        response = self._get("t2600001")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_valid"])
        self.assertEqual(response.data["status"], "valid")
        self.assertEqual(response.data["full_name"], self.learner.full_name)
        self.assertEqual(response.data["course"], self.course.name)
        self.assertEqual(response.data["certificate_no"], "T2600001")
        self.assertNotIn("learner", response.data)
        self.assertNotIn("training_record", response.data)

    def test_verifies_by_training_record_id_for_axis_compatibility(self):
        self._certificate()
        response = self._get(str(self.record.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["certificate_no"], "T2600001")

    def test_uses_latest_certificate_for_training_record(self):
        self._certificate("T2600001", issued_at=timezone.now() - timedelta(days=2))
        self._certificate("T2600002", issued_at=timezone.now())
        response = self._get(str(self.record.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["certificate_no"], "T2600002")

    def test_reports_expired_certificate_as_invalid(self):
        self._certificate(expiry_date=date.today() - timedelta(days=1))
        response = self._get("T2600001")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_valid"])
        self.assertEqual(response.data["status"], "expired")

    def test_reports_void_certificate_as_invalid(self):
        self._certificate(voided_at=timezone.now(), void_reason="Issued in error")
        response = self._get("T2600001")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_valid"])
        self.assertEqual(response.data["status"], "void")

    def test_reports_unissued_certificate_as_invalid(self):
        self._certificate(issued_at=None)
        response = self._get("T2600001")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_valid"])
        self.assertEqual(response.data["status"], "not_issued")
        self.assertIsNone(response.data["issued"])

    def test_unknown_identifier_returns_not_found(self):
        response = self._get("does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"], "not_found")


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(),
    OPITO_CENTRE_CODE="",
    OPITO_BOOKING_REF="OPITO105",
)
class OpitoFileAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)
        cls.course = Course.objects.get(course_code="BOSIET")
        cls.standard_course = Course.objects.get(course_code="FIRST-AID")
        cls.admin = User.objects.create_user("opitoadmin", password="pw12345678")
        cls.admin.roles.add(Role.objects.get(pk=RoleCode.ADMIN))
        cls.reader = User.objects.create_user("opitoreader", password="pw12345678")
        cls.reader.roles.add(Role.objects.get(pk=RoleCode.DUE_DILIGENCE))
        cls.learner_one = Learner.objects.create(
            badge_no="OP001",
            surname="Okafor",
            first_name="Ada",
            birth_date=date(1990, 5, 6),
            vantage_id="VAN-001",
        )
        cls.learner_two = Learner.objects.create(
            badge_no="OP002",
            surname="Adeyemi",
            first_name="Tola",
            birth_date=date(1992, 7, 8),
        )
        cls.start = date(2026, 2, 2)
        cls.end = date(2026, 2, 6)
        cls.record_one = TrainingRecord.objects.create(
            learner=cls.learner_one,
            course=cls.course,
            status=WorkflowStatus.objects.get(pk=9),
            start_date=cls.start,
            end_date=cls.end,
        )
        cls.record_two = TrainingRecord.objects.create(
            learner=cls.learner_two,
            course=cls.course,
            status=WorkflowStatus.objects.get(pk=9),
            start_date=cls.start,
            end_date=cls.end,
            prev_expiry=date(2026, 3, 3),
        )
        TrainingRecord.objects.create(
            learner=cls.learner_one,
            course=cls.standard_course,
            status=WorkflowStatus.objects.get(pk=9),
            start_date=cls.start,
            end_date=cls.end,
        )
        Certificate.objects.create(
            training_record=cls.record_one,
            learner=cls.learner_one,
            certificate_no="OP-CERT-1",
            opito_learner_id="OP-L-1",
            issued_at=timezone.now(),
        )

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def _cohort_url(self, suffix="", *, use_file_alias=False):
        base = "/api/v1/opito-files/"
        if use_file_alias:
            base += "file/"
        return f"{base}{suffix}"

    def _params(self):
        return f"?course={self.course.pk}&start_date={self.start.isoformat()}"

    def test_lists_only_opito_cohorts_and_exposes_file_alias(self):
        self._auth(self.admin)
        response = self.client.get(self._cohort_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        row = response.data["data"][0]
        self.assertEqual(row["id"], f"{self.start.isoformat()} {self.course.pk}")
        self.assertEqual(row["name"], self.course.name)
        self.assertEqual(row["product_code"], "5700")
        self.assertEqual(row["learners"], 2)
        self.assertEqual(row["fileName"], "")

        alias = self.client.get(self._cohort_url(use_file_alias=True))
        self.assertEqual(alias.status_code, 200)
        self.assertEqual(alias.data["total"], 1)

    def test_validate_vantage_reports_missing_ids(self):
        self._auth(self.admin)
        response = self.client.get(
            self._cohort_url("validate-vantage/") + self._params()
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["valid"])
        self.assertEqual(
            response.data["missingVantageIds"],
            [
                {
                    "learnerId": self.learner_two.pk,
                    "fullName": "Adeyemi Tola",
                    "badge": "OP002",
                }
            ],
        )

    def test_content_returns_expected_opito_rows(self):
        self._auth(self.admin)
        response = self.client.get(self._cohort_url("content/") + self._params())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        first, second = response.data["rows"]
        self.assertEqual(first["last_name"], "Adeyemi")
        self.assertEqual(first["vantage_id"], "")
        self.assertEqual(first["forward_date"], "2026-03-03")
        self.assertEqual(second["last_name"], "Okafor")
        self.assertEqual(second["opito_learner_no"], "OP-L-1")
        self.assertEqual(second["learner_count"], 2)

    def test_generate_and_download_csv(self):
        self._auth(self.admin)
        response = self.client.post(
            self._cohort_url("generate/"),
            {"course": self.course.pk, "start_date": self.start.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["fileName"].endswith(".csv"))
        generated = OpitoFile.objects.get(course=self.course, start_date=self.start)
        self.assertEqual(generated.record_count, 2)

        download = self.client.get(f"/api/v1/opito-files/{generated.pk}/download/")
        self.assertEqual(download.status_code, 200)
        text = b"".join(download.streaming_content).decode()
        reader = csv.DictReader(io.StringIO(text))
        self.assertEqual(
            reader.fieldnames,
            [
                "Start Date",
                "End Date",
                "Centre Code",
                "Product Code",
                "Booking Ref No",
                "Learner Count",
                "OPITO Learner No",
                "Vantage ID",
                "First Name",
                "Last Name",
                "DOB",
                "Forward Date",
            ],
        )
        rows = list(reader)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Last Name"], "Adeyemi")
        self.assertEqual(rows[0]["Start Date"], "02-FEB-2026")
        self.assertEqual(rows[0]["End Date"], "06-FEB-2026")
        self.assertEqual(rows[0]["Booking Ref No"], "OPITO105")
        self.assertEqual(rows[0]["Learner Count"], "2")
        self.assertEqual(rows[0]["DOB"], "08-JUL-1992")
        self.assertEqual(rows[0]["Forward Date"], "03-MAR-2026")
        self.assertEqual(rows[1]["OPITO Learner No"], "OP-L-1")
        self.assertEqual(rows[1]["Vantage ID"], "VAN-001")

    def test_regenerate_replaces_the_previous_csv(self):
        self._auth(self.admin)
        payload = {"course": self.course.pk, "date": self.start.isoformat()}
        first = self.client.post(self._cohort_url("csv/"), payload, format="json")
        self.assertEqual(first.status_code, 201)
        first_key = OpitoFile.objects.get().object_key
        second = self.client.post(self._cohort_url("generate/"), payload, format="json")
        self.assertEqual(second.status_code, 201)
        generated = OpitoFile.objects.get()
        self.assertNotEqual(generated.object_key, first_key)
        self.assertFalse(default_storage.exists(first_key))

    def test_rejects_non_opito_course_and_write_without_role(self):
        self._auth(self.admin)
        response = self.client.post(
            self._cohort_url("generate/"),
            {"course": self.standard_course.pk, "start_date": self.start.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

        self._auth(self.reader)
        self.assertEqual(self.client.get(self._cohort_url()).status_code, 200)
        write = self.client.post(
            self._cohort_url("generate/"),
            {"course": self.course.pk, "start_date": self.start.isoformat()},
            format="json",
        )
        self.assertEqual(write.status_code, 403)
