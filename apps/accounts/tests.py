"""Identity — users, roles, login and RBAC (design 02 M1; R-API-AUTH)."""
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
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
        self.assertEqual(response.data["full_name"], "newstaff")

    def test_system_admin_role_cannot_be_removed(self):
        self._auth(self.admin)
        relation = User.roles.through.objects.get(
            user=self.admin, role_id=RoleCode.SYSTEM_ADMIN
        )
        response = self.client.delete(f"/api/v1/user-role/{relation.pk}/delete")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(self.admin.roles.filter(pk=RoleCode.SYSTEM_ADMIN).exists())

        update = self.client.patch(
            f"/api/v1/users/{self.admin.pk}/",
            {"roles": [int(RoleCode.ACCOUNTS)]},
            format="json",
        )
        self.assertEqual(update.status_code, 400)
        self.assertIn("roles", update.data["details"])

    def test_cannot_delete_own_account(self):
        self._auth(self.admin)
        response = self.client.delete(f"/api/v1/users/{self.admin.pk}/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_password_reset_link_is_emailed(self):
        self.medic.email = "medic@example.com"
        self.medic.save(update_fields=["email"])
        self._auth(self.admin)
        response = self.client.post(f"/api/v1/users/{self.medic.pk}/reset-password/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/portal/password-reset/", mail.outbox[0].body)
        self.assertTrue(
            AuditEvent.objects.filter(
                actor=self.admin, action="accounts.password_reset_link_sent"
            ).exists()
        )

    def test_password_reset_requires_an_email_address(self):
        self._auth(self.admin)
        response = self.client.post(f"/api/v1/users/{self.medic.pk}/reset-password/")
        self.assertEqual(response.status_code, 400)

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

    def test_authenticated_user_can_change_password(self):
        token, _ = Token.objects.get_or_create(user=self.medic)
        self._auth(self.medic)
        response = self.client.post(
            "/api/v1/auth/password",
            {
                "current_password": "pw12345678",
                "new_password": "Str0ngPass!23",
                "confirm_password": "Str0ngPass!23",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 204, response.data)
        self.medic.refresh_from_db()
        self.assertTrue(self.medic.check_password("Str0ngPass!23"))
        self.assertFalse(self.medic.check_password("pw12345678"))
        self.assertEqual(Token.objects.filter(user=self.medic).count(), 1)
        self.assertTrue(
            AuditEvent.objects.filter(
                actor=self.medic, action="auth.password_changed"
            ).exists()
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        logout = self.client.post("/api/v1/auth/logout")
        self.assertEqual(logout.status_code, 204, logout.data)

    def test_password_change_rejects_wrong_current_password(self):
        self._auth(self.medic)
        response = self.client.post(
            "/api/v1/auth/password",
            {
                "current_password": "wrong-password",
                "new_password": "Str0ngPass!23",
                "confirm_password": "Str0ngPass!23",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("current_password", response.data["details"])

    def test_password_change_rejects_mismatch_and_reuse(self):
        self._auth(self.medic)
        mismatch = self.client.post(
            "/api/v1/auth/password",
            {
                "current_password": "pw12345678",
                "new_password": "Str0ngPass!23",
                "confirm_password": "Str0ngPass!24",
            },
            format="json",
        )
        self.assertEqual(mismatch.status_code, 400)
        self.assertIn("confirm_password", mismatch.data["details"])
        reused = self.client.post(
            "/api/v1/auth/password",
            {
                "current_password": "pw12345678",
                "new_password": "pw12345678",
                "confirm_password": "pw12345678",
            },
            format="json",
        )
        self.assertEqual(reused.status_code, 400)
        self.assertIn("new_password", reused.data["details"])

    def test_password_change_requires_authentication(self):
        response = self.client.post(
            "/api/v1/auth/password",
            {
                "current_password": "pw12345678",
                "new_password": "Str0ngPass!23",
                "confirm_password": "Str0ngPass!23",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_axis_user_role_relation_lifecycle(self):
        role = Role.objects.get(pk=RoleCode.ACCOUNTS)
        self._auth(self.admin)
        response = self.client.post(
            "/api/v1/user-role", [[self.medic.id, role.id]], format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        relation_id = response.data[0]["id"]
        self.assertEqual(response.data[0]["user"], self.medic.id)
        self.assertEqual(response.data[0]["role"], role.id)
        self.assertEqual(response.data[0]["code"], "accounts")

        assigned = self.client.get(f"/api/v1/user-role/{self.medic.id}")
        self.assertEqual(assigned.status_code, 200)
        self.assertIn(role.id, [row["role"] for row in assigned.data])
        available = self.client.get(f"/api/v1/user-role/{self.medic.id}/available")
        self.assertNotIn(role.id, [row["id"] for row in available.data])

        self._auth(self.medic)
        self.assertEqual(
            self.client.post(
                "/api/v1/user-role",
                [[self.medic.id, int(RoleCode.ACCOUNTS)]],
                format="json",
            ).status_code,
            403,
        )

        self._auth(self.admin)
        response = self.client.delete(f"/api/v1/user-role/{relation_id}")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(self.medic.roles.filter(id=role.id).exists())
