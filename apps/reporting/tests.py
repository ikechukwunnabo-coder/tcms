"""Reporting — definitions, runs and the flow-status view (M12)."""
from datetime import date

from django.core.management import call_command
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.catalogue.models import CertificateType, Course
from apps.certification.models import Certificate
from apps.common.enums import CertificateTypeCode, RoleCode
from apps.delivery.models import TrainingRecord
from apps.learners.models import Learner
from apps.reporting.models import ReportDef, ReportRun
from apps.workflow.models import Approval, WorkflowStatus


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


class DashboardAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        cls.admin = User.objects.create_user("dashadmin", password="pw12345678")
        cls.admin.roles.add(Role.objects.get(pk=RoleCode.SYSTEM_ADMIN))
        cls.medic = User.objects.create_user("dashmedic", password="pw12345678")
        cls.medic.roles.add(Role.objects.get(pk=RoleCode.MEDIC))

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_dashboard_available_to_every_staff_role(self):
        self._auth(self.medic)
        response = self.client.get("/api/v1/dashboard/")
        self.assertEqual(response.status_code, 200)
        for key in ("kpis", "workflow", "my_stages", "trend", "course_mix", "work_queue"):
            self.assertIn(key, response.data)
        self.assertEqual(len(response.data["trend"]), 6)

    def test_dashboard_denied_anonymously(self):
        self.client.credentials()
        self.assertEqual(self.client.get("/api/v1/dashboard/").status_code, 401)

    def test_flow_csv_export_is_reporting_scoped(self):
        self._auth(self.admin)
        response = self.client.get("/api/v1/reports/export/?dataset=flow")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("status,code,name,count,terminal", response.content.decode())

        self._auth(self.medic)
        self.assertEqual(
            self.client.get("/api/v1/reports/export/?dataset=flow").status_code, 403
        )

    def test_learners_csv_export_and_unknown_dataset(self):
        self._auth(self.admin)
        response = self.client.get("/api/v1/reports/export/?dataset=learners")
        self.assertEqual(response.status_code, 200)
        self.assertIn("badge_no,surname", response.content.decode())

        unknown = self.client.get("/api/v1/reports/export/?dataset=nope")
        self.assertEqual(unknown.status_code, 400)


class ReportingIntelligenceAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        cls.standard_type, _ = CertificateType.objects.get_or_create(
            id=CertificateTypeCode.STANDARD, defaults={"name": "Standard"}
        )
        cls.opito_type, _ = CertificateType.objects.get_or_create(
            id=CertificateTypeCode.OPITO, defaults={"name": "OPITO"}
        )
        cls.md = User.objects.create_user("intelmd", password="pw12345678")
        cls.md.roles.add(Role.objects.get(pk=RoleCode.MD))
        cls.medic = User.objects.create_user("intelmedic", password="pw12345678")
        cls.medic.roles.add(Role.objects.get(pk=RoleCode.MEDIC))
        cls.opito_course = Course.objects.create(
            course_code="INT-OPITO",
            name="OPITO Basic",
            cert_type=cls.opito_type,
            opito_reg_code="OP-101",
        )
        cls.standard_course = Course.objects.create(
            course_code="INT-STD",
            name="Standard Safety",
            cert_type=cls.standard_type,
        )
        cls.learner = Learner.objects.create(
            badge_no="INT001",
            surname="Adeyemi",
            first_name="Tola",
            birth_date=date(1990, 5, 1),
            vantage_id="V-100",
        )
        cls.opito_record = TrainingRecord.objects.create(
            learner=cls.learner,
            course=cls.opito_course,
            status=WorkflowStatus.objects.get(pk=1),
            start_date=date(2025, 3, 10),
            end_date=date(2028, 3, 10),
        )
        cls.standard_record = TrainingRecord.objects.create(
            learner=cls.learner,
            course=cls.standard_course,
            status=WorkflowStatus.objects.get(pk=1),
            start_date=date(2025, 3, 12),
            end_date=date(2027, 3, 12),
        )
        Certificate.objects.create(
            training_record=cls.opito_record,
            learner=cls.learner,
            certificate_no="INT-CERT-1",
            opito_learner_id="OP-L-1",
            issued_at=timezone.now(),
            expiry_date=date(2028, 3, 10),
        )
        Approval.objects.create(
            training_record=cls.opito_record,
            current_status=WorkflowStatus.objects.get(pk=1),
            step_no=1,
            assigned_role=Role.objects.get(pk=RoleCode.ADMIN),
            action="approve",
            acted_by=cls.md,
            acted_at=timezone.now(),
        )

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_year_range_and_training_records(self):
        self._auth(self.md)
        year_range = self.client.get("/api/v1/reports/year-range/")
        self.assertEqual(year_range.status_code, 200)
        self.assertEqual(year_range.data, {"min": 2025, "max": 2025, "default": 2025})

        response = self.client.get("/api/v1/reports/training-records/?year=2025")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 2)
        opito_row = next(
            row
            for row in response.data["data"]
            if row["course"] == "OPITO Basic"
        )
        self.assertEqual(opito_row["certificate"], "INT-CERT-1")
        self.assertGreaterEqual(opito_row["days"], 0)

        filtered = self.client.get(
            f"/api/v1/reports/training-records/?course={self.opito_course.id}"
        )
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.data["total"], 1)
        self.assertEqual(
            self.client.get(
                "/api/v1/reports/training-records/?from=not-a-date"
            ).status_code,
            400,
        )

    def test_month_reports_and_top_courses(self):
        self._auth(self.md)
        by_month = self.client.get("/api/v1/reports/course-by-month/?year=2025")
        self.assertEqual(by_month.status_code, 200)
        self.assertEqual(len(by_month.data["data"]), 2)
        self.assertEqual(by_month.data["data"][0]["month"], "Mar")

        delegates = self.client.get("/api/v1/reports/delegates-by-month/?year=2025")
        self.assertEqual(delegates.status_code, 200)
        self.assertEqual(len(delegates.data["data"]), 12)
        self.assertEqual(delegates.data["data"][2]["value"], 1)

        treemap = self.client.get("/api/v1/reports/courses-treemap/?year=2025")
        self.assertEqual(treemap.status_code, 200)
        self.assertEqual(
            {row["type"] for row in treemap.data["data"]}, {"OPITO", "Standard"}
        )

        top = self.client.get("/api/v1/reports/top-courses/?year=2025")
        self.assertEqual(top.status_code, 200)
        self.assertEqual(len(top.data["data"]), 2)

    def test_role_activity_and_opito_monthly(self):
        self._auth(self.md)
        roles = self.client.get("/api/v1/reports/role-activity/roles/")
        self.assertEqual(roles.status_code, 200)
        self.assertIn("md", {role["code"] for role in roles.data["data"]})

        earliest = self.client.get("/api/v1/reports/role-activity/earliest-date/")
        self.assertEqual(earliest.status_code, 200)
        self.assertEqual(earliest.data["date"], timezone.localdate().isoformat())

        md_role = Role.objects.get(pk=RoleCode.MD)
        activity = self.client.get(
            f"/api/v1/reports/role-activity/?role={md_role.id}"
        )
        self.assertEqual(activity.status_code, 200)
        self.assertEqual(activity.data["total"], 1)
        self.assertEqual(activity.data["data"][0]["learner"], "Adeyemi Tola")

        summary = self.client.get(
            f"/api/v1/reports/role-activity/summary/?role={md_role.id}"
        )
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.data["data"][0]["count"], 1)

        opito = self.client.get(
            "/api/v1/reports/opito-monthly/?from=2025-01-01&to=2025-12-31"
        )
        self.assertEqual(opito.status_code, 200)
        self.assertEqual(opito.data["total"], 1)
        self.assertEqual(opito.data["data"][0]["opito_learner_id"], "OP-L-1")

    def test_flow_status_summary_and_thresholds(self):
        self._auth(self.md)
        response = self.client.get("/api/v1/reports/flow-status/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["active_records"], 2)
        self.assertEqual(response.data["thresholds"], {"backlog": 15, "critical": 25})
        self.assertTrue(response.data["next_roles"])

    def test_xlsx_pdf_and_invalid_format_exports(self):
        self._auth(self.md)
        xlsx = self.client.get(
            "/api/v1/reports/export/?dataset=course-by-month&year=2025&format=xlsx"
        )
        self.assertEqual(xlsx.status_code, 200)
        self.assertIn("spreadsheetml", xlsx["Content-Type"])
        self.assertEqual(xlsx.content[:2], b"PK")

        pdf = self.client.get(
            "/api/v1/reports/export/?dataset=training-records&year=2025&format=pdf"
        )
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))

        bad = self.client.get(
            "/api/v1/reports/export/?dataset=course-by-month&format=docx"
        )
        self.assertEqual(bad.status_code, 400)

    def test_new_reports_are_reporting_scoped(self):
        self._auth(self.medic)
        for path in (
            "/api/v1/reports/year-range/",
            "/api/v1/reports/training-records/",
            "/api/v1/reports/course-by-month/",
            "/api/v1/reports/delegates-by-month/",
            "/api/v1/reports/courses-treemap/",
            "/api/v1/reports/top-courses/",
            "/api/v1/reports/role-activity/",
            "/api/v1/reports/role-activity/roles/",
            "/api/v1/reports/opito-monthly/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
