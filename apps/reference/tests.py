"""Reference data — companies, nationalities, states, positions, titles (M2)."""
from django.core.management import call_command
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.common.enums import RoleCode
from apps.reference.models import Company


class ReferenceAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)
        cls.admin = User.objects.create_user("refadmin", password="pw12345678")
        cls.admin.roles.add(Role.objects.get(pk=RoleCode.SYSTEM_ADMIN))
        cls.medic = User.objects.create_user("refmedic", password="pw12345678")
        cls.medic.roles.add(Role.objects.get(pk=RoleCode.MEDIC))

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_staff_can_read_reference_lists(self):
        self._auth(self.medic)
        for path in (
            "/api/v1/companies/",
            "/api/v1/nationalities/",
            "/api/v1/states/",
            "/api/v1/positions/",
            "/api/v1/titles/",
            "/api/v1/contact-types/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_company_search(self):
        self._auth(self.medic)
        company = Company.objects.first()
        response = self.client.get(f"/api/v1/companies/?search={company.name}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)

    def test_only_system_admin_can_write_reference_data(self):
        payload = {"agencode": "REF01", "name": "Reference Test Ltd"}
        self._auth(self.medic)
        self.assertEqual(
            self.client.post("/api/v1/companies/", payload, format="json").status_code, 403
        )
        self._auth(self.admin)
        response = self.client.post("/api/v1/companies/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(Company.objects.filter(agencode="REF01").exists())
