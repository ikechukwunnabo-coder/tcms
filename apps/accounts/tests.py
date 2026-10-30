"""Identity — users, roles, login and RBAC (design 02 M1; R-API-AUTH)."""
from django.core.cache import cache
from django.core.management import call_command
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.common.enums import RoleCode


class AccountAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        cls.admin = User.objects.create_user("sysadmin", password="pw12345678")
        cls.admin.roles.add(Role.objects.get(pk=RoleCode.SYSTEM_ADMIN))
        cls.medic = User.objects.create_user("medic", password="pw12345678")
        cls.medic.roles.add(Role.objects.get(pk=RoleCode.MEDIC))

    def setUp(self):
        cache.clear()

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_system_admin_can_list_users(self):
        self._auth(self.admin)
        response = self.client.get("/api/v1/users/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["total"], 2)

    def test_non_admin_cannot_list_users(self):
        self._auth(self.medic)
        self.assertEqual(self.client.get("/api/v1/users/").status_code, 403)

    def test_only_system_admin_can_list_roles(self):
        self._auth(self.admin)
        self.assertEqual(self.client.get("/api/v1/roles/").status_code, 200)
        self._auth(self.medic)
        self.assertEqual(self.client.get("/api/v1/roles/").status_code, 403)

    def test_create_user_hashes_password_and_assigns_roles(self):
        self._auth(self.admin)
        response = self.client.post(
            "/api/v1/users/",
            {
                "username": "newstaff",
                "email": "New.Staff@Example.com",
                "password": "Str0ngPass!23",
                "roles": [int(RoleCode.ACCOUNTS)],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn("password", response.data)
        user = User.objects.get(username="newstaff")
        self.assertEqual(user.email, "new.staff@example.com")
        self.assertTrue(user.check_password("Str0ngPass!23"))
        self.assertEqual(list(user.roles.values_list("id", flat=True)), [RoleCode.ACCOUNTS])
        self.assertEqual(response.data["role_codes"], ["accounts"])

    def test_duplicate_email_is_rejected_case_insensitively(self):
        User.objects.create_user("existing", email="dup@example.com", password="pw12345678")
        self._auth(self.admin)
        response = self.client.post(
            "/api/v1/users/",
            {"username": "another", "email": "DUP@example.com", "password": "Str0ngPass!23"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data["details"])

    def test_login_accepts_email_identifier(self):
        User.objects.create_user(
            "portal@example.com",
            email="portal@example.com",
            password="Str0ngPass!23",
        )
        response = self.client.post(
            "/api/v1/auth/login",
            {"email": "portal@example.com", "password": "Str0ngPass!23"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)

    def test_unverified_user_cannot_login(self):
        User.objects.create_user(
            "unverified",
            email="unverified@example.com",
            password="Str0ngPass!23",
            email_verified=False,
        )
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "unverified", "password": "Str0ngPass!23"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"], "email_not_verified")

    def test_login_rejects_missing_identifier(self):
        response = self.client.post(
            "/api/v1/auth/login", {"password": "x"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
