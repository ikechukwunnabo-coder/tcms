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
