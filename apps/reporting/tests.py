"""Reporting — definitions, runs and the flow-status view (M12)."""
from django.core.management import call_command
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.common.enums import RoleCode
from apps.reporting.models import ReportDef, ReportRun


class ReportingAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        cls.admin = User.objects.create_user("repadmin", password="pw12345678")
        cls.admin.roles.add(Role.objects.get(pk=RoleCode.SYSTEM_ADMIN))
        cls.md = User.objects.create_user("repmd", password="pw12345678")
        cls.md.roles.add(Role.objects.get(pk=RoleCode.MD))
        cls.medic = User.objects.create_user("repmedic", password="pw12345678")
        cls.medic.roles.add(Role.objects.get(pk=RoleCode.MEDIC))
        cls.definition = ReportDef.objects.create(
            code="training.flow", name="Training flow", sql_view="v_training_flow"
        )
        cls.definition.roles.add(Role.objects.get(pk=RoleCode.MD))
        ReportRun.objects.create(report_def=cls.definition, object_key="reports/flow.csv")

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_reporting_roles_can_read_definitions_and_runs(self):
        self._auth(self.md)
        self.assertEqual(self.client.get("/api/v1/report-defs/").status_code, 200)
        runs = self.client.get("/api/v1/report-runs/")
        self.assertEqual(runs.status_code, 200)
        self.assertEqual(runs.data["total"], 1)

    def test_report_retrieve_by_code(self):
        self._auth(self.md)
        response = self.client.get("/api/v1/reports/training.flow/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["code"], "training.flow")

    def test_flow_status_returns_all_statuses(self):
        self._auth(self.md)
        response = self.client.get("/api/v1/reports/flow-status/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data["data"]), 14)
        self.assertIn("total", response.data)

    def test_non_reporting_role_is_denied(self):
        self._auth(self.medic)
        for path in (
            "/api/v1/report-defs/",
            "/api/v1/report-runs/",
            "/api/v1/reports/",
            "/api/v1/reports/flow-status/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)

    def test_only_system_admin_can_write_definitions(self):
        payload = {"code": "new.report", "name": "New report"}
        self._auth(self.md)
        self.assertEqual(
            self.client.post("/api/v1/report-defs/", payload, format="json").status_code,
            403,
        )
        self._auth(self.admin)
        response = self.client.post("/api/v1/report-defs/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)
