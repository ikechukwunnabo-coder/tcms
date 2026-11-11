import shutil
import tempfile
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.common.enums import RoleCode
from apps.learners import services as svc
from apps.learners.models import Learner, LearnerDocument


class AgeGateTests(SimpleTestCase):
    def test_age_on(self):
        self.assertEqual(svc.age_on(date(2000, 6, 15), date(2026, 6, 14)), 25)
        self.assertEqual(svc.age_on(date(2000, 6, 15), date(2026, 6, 15)), 26)

    def test_assert_min_age(self):
        self.assertTrue(svc.assert_min_age(date(2000, 1, 1), date(2026, 1, 1)))
        with self.assertRaises(svc.AgeError):
            svc.assert_min_age(date(2010, 1, 1), date(2026, 1, 1))

    def test_missing_birth_date(self):
        with self.assertRaises(svc.AgeError):
            svc.assert_min_age(None)


class LearnerDocumentAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        cls.admin = User.objects.create_user("docadmin", password="pw12345678")
        cls.admin.roles.add(Role.objects.get(pk=RoleCode.SYSTEM_ADMIN))
        cls.learner = Learner.objects.create(badge_no="DOC001", surname="Doe")

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        token, _ = Token.objects.get_or_create(user=self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_learner_photo_and_id_scan_upload_and_download(self):
        for kind in ("photo", "id_scan"):
            upload = SimpleUploadedFile(
                f"{kind}.jpg", b"image-bytes", content_type="image/jpeg"
            )
            response = self.client.post(
                "/api/v1/learner-documents/upload/",
                {"learner": self.learner.id, "kind": kind, "file": upload},
                format="multipart",
            )
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data["kind"], kind)
            self.assertTrue(response.data["object_key"].startswith("learner-documents/"))

        self.assertEqual(LearnerDocument.objects.count(), 2)
        document = LearnerDocument.objects.get(kind="id_scan")
        download = self.client.get(f"/api/v1/learner-documents/{document.id}/download/")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b"".join(download.streaming_content), b"image-bytes")

    def test_unauthenticated_upload_is_rejected(self):
        self.client.credentials()
        upload = SimpleUploadedFile("photo.jpg", b"image-bytes", content_type="image/jpeg")
        response = self.client.post(
            "/api/v1/learner-documents/upload/",
            {"learner": self.learner.id, "kind": "photo", "file": upload},
            format="multipart",
        )
        self.assertEqual(response.status_code, 401)
