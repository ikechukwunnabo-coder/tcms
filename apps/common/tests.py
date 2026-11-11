import gzip
import json
import tempfile
from datetime import timedelta
from pathlib import Path

from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.catalogue.models import Course
from apps.common.api import router
from apps.delivery.models import TrainingRecord
from apps.learners.models import Learner
from apps.workflow.models import WorkflowStatus


class APIAuthTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)

    def setUp(self):
        cache.clear()

    def test_login_returns_token(self):
        User.objects.create_user("u1", password="pw")
        response = self.client.post(
            "/api/v1/auth/login", {"username": "u1", "password": "pw"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)

    def test_login_bad_credentials(self):
        response = self.client.post(
            "/api/v1/auth/login", {"username": "x", "password": "y"}, format="json"
        )
        self.assertEqual(response.status_code, 401)
        self.assertTrue(
            AuditEvent.objects.filter(action="auth.api_login_failed").exists()
        )

    def test_unauthenticated_is_rejected(self):
        self.assertEqual(self.client.get("/api/v1/companies/").status_code, 401)

    def test_all_api_collection_routes_require_authentication(self):
        failures = []
        for _prefix, _viewset, basename in router.registry:
            response = self.client.get(reverse(f"{basename}-list"))
            if response.status_code != 401:
                failures.append((basename, response.status_code))
        self.assertEqual(failures, [])

    def test_logout_revokes_the_token(self):
        user = User.objects.create_user("logout", password="pw")
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.post("/api/v1/auth/logout")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())
        self.assertEqual(self.client.get("/api/v1/companies/").status_code, 401)

    def test_expired_token_is_rejected(self):
        user = User.objects.create_user("ttl", password="pw")
        token = Token.objects.create(user=user)
        Token.objects.filter(pk=token.pk).update(
            created=timezone.now() - timedelta(hours=25)
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.assertEqual(self.client.get("/api/v1/companies/").status_code, 401)
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())

    def test_login_is_throttled_after_repeated_failures(self):
        for _ in range(10):
            response = self.client.post(
                "/api/v1/auth/login", {"username": "x", "password": "y"}, format="json"
            )
            self.assertEqual(response.status_code, 401)
        response = self.client.post(
            "/api/v1/auth/login", {"username": "x", "password": "y"}, format="json"
        )
        self.assertEqual(response.status_code, 429)

    def test_login_throttle_ignores_spoofed_forwarded_for(self):
        for i in range(10):
            response = self.client.post(
                "/api/v1/auth/login",
                {"username": "x", "password": "y"},
                format="json",
                HTTP_X_FORWARDED_FOR=f"203.0.113.{i}",
            )
            self.assertEqual(response.status_code, 401)
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "x", "password": "y"},
            format="json",
            HTTP_X_FORWARDED_FOR="198.51.100.7",
        )
        self.assertEqual(response.status_code, 429)

    def test_admin_login_is_throttled_after_repeated_failures(self):
        for _ in range(10):
            response = self.client.post(
                "/admin/login/", {"username": "x", "password": "y"}
            )
            self.assertEqual(response.status_code, 200)
        response = self.client.post("/admin/login/", {"username": "x", "password": "y"})
        self.assertEqual(response.status_code, 429)


class RBACTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)
        cls.admin = User.objects.create_user("adm", password="pw")
        cls.admin.roles.add(Role.objects.get(pk=1))  # System Admin
        cls.medic = User.objects.create_user("med", password="pw")
        cls.medic.roles.add(Role.objects.get(pk=4))  # Medic

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def test_admin_can_list_users_g1(self):
        self._auth(self.admin)
        self.assertEqual(self.client.get("/api/v1/users/").status_code, 200)

    def test_medic_cannot_list_users_g1(self):
        self._auth(self.medic)
        self.assertEqual(self.client.get("/api/v1/users/").status_code, 403)

    def test_medic_can_read_reference(self):
        self._auth(self.medic)
        self.assertEqual(self.client.get("/api/v1/companies/").status_code, 200)

    def test_medic_cannot_write_reference(self):
        self._auth(self.medic)
        response = self.client.post(
            "/api/v1/companies/", {"name": "X"}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_mfa_secret_is_not_exposed_via_api(self):
        self._auth(self.admin)
        response = self.client.get(f"/api/v1/users/{self.admin.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("mfa_secret", response.data)


class WorkflowAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)
        cls.admin = User.objects.create_user("adm2", password="pw")
        cls.admin.roles.add(Role.objects.get(pk=2))  # Admin
        cls.learner = Learner.objects.create(badge_no="A1", surname="X")
        cls.course = Course.objects.get(course_code="BOSIET")
        cls.record = TrainingRecord.objects.create(
            learner=cls.learner, course=cls.course, status=WorkflowStatus.objects.get(pk=1)
        )

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def test_advance_via_api(self):
        self._auth(self.admin)
        response = self.client.post(
            f"/api/v1/approvals/{self.record.pk}/advance/", {"action": "approve"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], 2)

    def test_reject_without_reason_is_400(self):
        self._auth(self.admin)
        response = self.client.post(
            f"/api/v1/approvals/{self.record.pk}/reject/", {}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "reason_required")


class ReportAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def test_flow_status_report_p15(self):
        reporter = User.objects.create_user("rep", password="pw")
        reporter.roles.add(Role.objects.get(pk=11))  # Reports
        self._auth(reporter)
        response = self.client.get("/api/v1/reports/flow-status/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 14)


class BackupAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        cls.system_admin = User.objects.create_user("backup-admin", password="pw")
        cls.system_admin.roles.add(Role.objects.get(pk=1))
        cls.medic = User.objects.create_user("backup-medic", password="pw")
        cls.medic.roles.add(Role.objects.get(pk=4))

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def test_system_admin_can_create_backup_snapshot(self):
        self._auth(self.system_admin)
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(BACKUP_DIR=Path(directory)):
                response = self.client.post("/api/v1/backup/backup")
                self.assertEqual(response.status_code, 201, response.data)
                target = Path(directory) / response.data["file_name"]
                self.assertTrue(target.exists())
                with gzip.open(target, "rt", encoding="utf-8") as handle:
                    payload = json.load(handle)
                self.assertGreater(len(payload), 0)
                self.assertTrue(
                    any(row["model"] == "accounts.user" for row in payload)
                )
        self.assertTrue(
            AuditEvent.objects.filter(
                actor=self.system_admin, action="backup.created"
            ).exists()
        )

    def test_backup_requires_system_admin(self):
        self._auth(self.medic)
        self.assertEqual(self.client.post("/api/v1/backup/backup").status_code, 403)
        self.assertEqual(self.client.post("/api/v1/backup/test").status_code, 403)

    def test_storage_probe_reports_success_and_cleans_up(self):
        self._auth(self.system_admin)
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(BACKUP_DIR=Path(directory)):
                response = self.client.post("/api/v1/backup/test")
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data["status"], "ok")
                self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertTrue(
            AuditEvent.objects.filter(
                actor=self.system_admin, action="backup.tested"
            ).exists()
        )
