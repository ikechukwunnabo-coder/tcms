"""Catalogue — courses, modules, items and certificate types (M4)."""
from django.core.management import call_command
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.catalogue.models import CertificateType, Course
from apps.common.enums import RoleCode


class CatalogueAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)
        cls.admin = User.objects.create_user("catadmin", password="pw12345678")
        cls.admin.roles.add(Role.objects.get(pk=RoleCode.SYSTEM_ADMIN))
        cls.medic = User.objects.create_user("catmedic", password="pw12345678")
        cls.medic.roles.add(Role.objects.get(pk=RoleCode.MEDIC))

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_any_staff_role_can_read_courses(self):
        self._auth(self.medic)
        response = self.client.get("/api/v1/courses/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["total"], 8)

    def test_course_search_matches_code(self):
        self._auth(self.medic)
        response = self.client.get("/api/v1/courses/?search=BOSIET")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["total"], 1)
        self.assertIn(
            "BOSIET", [row["course_code"] for row in response.data["data"]]
        )

    def test_only_system_admin_can_create_courses(self):
        self._auth(self.medic)
        payload = {"course_code": "NEW01", "name": "New course", "duration_days": 2}
        self.assertEqual(
            self.client.post("/api/v1/courses/", payload, format="json").status_code, 403
        )
        self._auth(self.admin)
        response = self.client.post("/api/v1/courses/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(Course.objects.filter(course_code="NEW01").exists())

    def test_certificate_types_are_readable(self):
        self._auth(self.medic)
        response = self.client.get("/api/v1/certificate-types/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["total"], 2)
        self.assertEqual(
            CertificateType.objects.filter(id__in=[1, 2]).count(), 2
        )

    def test_modules_and_items_are_readable(self):
        self._auth(self.medic)
        self.assertEqual(self.client.get("/api/v1/course-modules/").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/course-items/").status_code, 200)
