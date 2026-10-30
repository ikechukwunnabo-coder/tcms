import tempfile
import zipfile
from datetime import date
from io import BytesIO

from django.core import mail
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token

from apps.accounts.models import User
from apps.billing.models import CorporateAccount
from apps.catalogue.models import Course
from apps.certification import services as cert
from apps.certification.models import Certificate
from apps.common.enums import CertificateBatchStatus
from apps.delivery.models import TrainingRecord
from apps.learners.models import Learner
from apps.portal.models import PortalAccount
from apps.workflow.models import WorkflowStatus


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class CertificateBundleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)
        cls.course = Course.objects.get(course_code="BOSIET")
        cls.learner_indiv = Learner.objects.create(
            badge_no="B001", surname="Ind", first_name="Val", birth_date=date(1990, 1, 1)
        )
        cls.record_indiv = TrainingRecord.objects.create(
            learner=cls.learner_indiv,
            course=cls.course,
            status=WorkflowStatus.objects.get(pk=9),
            start_date=date(2026, 1, 13),
        )
        cls.lead_user = User.objects.create_user("corp_lead2", email="lead@acme.com", password="pw")
        cls.lead_user.email_verified = True
        cls.lead_user.save(update_fields=["email_verified"])
        cls.account = CorporateAccount.objects.create(
            name="Acme", lead_user=cls.lead_user, lead_email="lead@acme.com"
        )
        cls.nom1 = Learner.objects.create(
            badge_no="N001", surname="Nom", first_name="One", birth_date=date(1992, 2, 2),
            learner_type="corporate", corporate_account=cls.account,
        )
        cls.nom2 = Learner.objects.create(
            badge_no="N002", surname="Nom", first_name="Two", birth_date=date(1993, 3, 3),
            learner_type="corporate", corporate_account=cls.account,
        )
        cls.rec1 = TrainingRecord.objects.create(
            learner=cls.nom1, course=cls.course, status=WorkflowStatus.objects.get(pk=9),
            start_date=date(2026, 1, 13),
        )
        cls.rec2 = TrainingRecord.objects.create(
            learner=cls.nom2, course=cls.course, status=WorkflowStatus.objects.get(pk=9),
            start_date=date(2026, 1, 13),
        )

    def _cert(self, no, learner, record):
        return Certificate.objects.create(
            training_record=record, learner=learner, certificate_no=no,
            issued_at=timezone.now(), expiry_date=date(2026, 6, 30),
        )

    def test_release_corporate_attaches_to_batch_no_individual_email(self):
        c1 = self._cert("T27001", self.nom1, self.rec1)
        mail.outbox = []
        cert.release(c1)
        c1.refresh_from_db()
        self.assertIsNotNone(c1.released_at)
        self.assertIsNotNone(c1.batch_id)
        self.assertEqual(c1.batch.corporate_account_id, self.account.pk)
        self.assertEqual(len(mail.outbox), 0)

    def test_release_individual_sends_notice(self):
        c1 = self._cert("T27010", self.learner_indiv, self.record_indiv)
        user = User.objects.create_user("ind2", email="ind2@example.com", password="pw")
        user.email_verified = True
        user.save(update_fields=["email_verified"])
        PortalAccount.objects.create(user=user, learner=self.learner_indiv)
        mail.outbox = []
        cert.release(c1)
        self.assertTrue(any("released" in m.subject.lower() for m in mail.outbox))
        self.assertIsNone(c1.batch_id)

    def test_bundle_zero_released_raises(self):
        with self.assertRaises(cert.NoReleasedCertificates):
            cert.bundle_for_account(self.account)

    def test_bundle_assembles_and_delivers_zip(self):
        c1 = self._cert("T27002", self.nom1, self.rec1)
        c2 = self._cert("T27003", self.nom2, self.rec2)
        cert.release(c1)
        cert.release(c2)
        mail.outbox = []
        batch = cert.bundle_for_account(self.account)
        batch.refresh_from_db()
        self.assertEqual(batch.status, CertificateBatchStatus.DELIVERED)
        self.assertEqual(batch.certificate_count, 2)
        self.assertTrue(batch.zip_file_ref)
        self.assertEqual(len(batch.zip_file_hash), 64)
        self.assertEqual(batch.delivered_to, "lead@acme.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(len(mail.outbox[0].attachments) >= 1)
        self.assertTrue(mail.outbox[0].attachments[0][0].endswith(".zip"))
        with default_storage.open(batch.zip_file_ref, "rb") as fh:
            data = fh.read()
        z = zipfile.ZipFile(BytesIO(data))
        names = z.namelist()
        self.assertEqual(len(names), 2)
        self.assertTrue(any("T27002" in n for n in names))
        self.assertTrue(any("T27003" in n for n in names))

    def test_bundle_excludes_unreleased_and_voided(self):
        c1 = self._cert("T27004", self.nom1, self.rec1)
        self._cert("T27005", self.nom2, self.rec2)  # not released
        cert.release(c1)
        c1_void = self._cert("T27006", self.nom1, TrainingRecord.objects.create(
            learner=self.nom1, course=self.course, status=WorkflowStatus.objects.get(pk=9),
            start_date=date(2026, 1, 13),
        ))
        cert.release(c1_void)
        c1_void.voided_at = timezone.now()
        c1_void.save(update_fields=["voided_at"])
        batch = cert.bundle_for_account(self.account)
        batch.refresh_from_db()
        self.assertEqual(batch.certificate_count, 1)

    def test_bundle_creates_new_batch_after_delivery(self):
        c1 = self._cert("T27007", self.nom1, self.rec1)
        cert.release(c1)
        batch1 = cert.bundle_for_account(self.account)
        self.assertEqual(batch1.status, CertificateBatchStatus.DELIVERED)
        c2 = self._cert("T27008", self.nom2, self.rec2)
        cert.release(c2)
        batch2 = cert.bundle_for_account(self.account)
        self.assertNotEqual(batch1.pk, batch2.pk)
        self.assertEqual(batch2.certificate_count, 1)

    def test_batch_endpoint_requires_corporate_lead(self):
        c1 = self._cert("T27009", self.nom1, self.rec1)
        cert.release(c1)
        user, _ = User.objects.get_or_create(username="x2", defaults={"email": "x2@x.com"})
        token, _ = Token.objects.get_or_create(user=user)
        from rest_framework.test import APIClient
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        r = client.post("/api/v1/corporate/certificates/bundle")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["error"], "corporate_account_required")
        r2 = client.get("/api/v1/corporate/certificates/batches")
        self.assertEqual(r2.status_code, 403)
