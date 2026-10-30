"""Document metadata — RBAC and CRUD (M14)."""
from django.core.management import call_command
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.common.enums import RoleCode
from apps.documents.models import Document


class DocumentAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        cls.accounts = User.objects.create_user("docacct", password="pw12345678")
        cls.accounts.roles.add(Role.objects.get(pk=RoleCode.ACCOUNTS))
        cls.medic = User.objects.create_user("docmedic", password="pw12345678")
        cls.medic.roles.add(Role.objects.get(pk=RoleCode.MEDIC))
        cls.document = Document.objects.create(
            kind="certificate", object_key="certificates/a.pdf", mime="application/pdf"
        )

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_permitted_role_can_read_metadata(self):
        self._auth(self.accounts)
        response = self.client.get("/api/v1/documents/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["data"][0]["object_key"], "certificates/a.pdf")

    def test_unpermitted_role_is_denied(self):
        self._auth(self.medic)
        self.assertEqual(self.client.get("/api/v1/documents/").status_code, 403)

    def test_permitted_role_can_register_document(self):
        self._auth(self.accounts)
        response = self.client.post(
            "/api/v1/documents/",
            {"kind": "medical", "object_key": "medical/b.pdf", "size_bytes": 12},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(Document.objects.filter(object_key="medical/b.pdf").exists())

    def test_filter_by_kind(self):
        Document.objects.create(kind="photo", object_key="photos/c.jpg")
        self._auth(self.accounts)
        response = self.client.get("/api/v1/documents/?kind=certificate")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
