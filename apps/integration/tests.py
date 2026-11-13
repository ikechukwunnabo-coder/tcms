from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.certification.models import Certificate, IDCard
from apps.common.enums import RoleCode, WorkflowStatusCode
from apps.delivery.models import TrainingRecord
from apps.integration.models import SeedMarker
from apps.learners.models import Learner
from apps.payroll.models import Employee
from apps.portal.models import PortalAccount


class SeedDemoTests(TestCase):
    def setUp(self):
        call_command("seed_roles")
        call_command("seed_data")

    def test_builds_full_chain(self):
        call_command("seed_demo")
        self.assertGreaterEqual(Learner.objects.count(), len(list(WorkflowStatusCode)))
        states = set(TrainingRecord.objects.values_list("status_id", flat=True))
        self.assertEqual(states, {int(c) for c in WorkflowStatusCode})
        self.assertTrue(Certificate.objects.exists())
        self.assertTrue(
            Certificate.objects.filter(signature_applied=True, seal_applied=True).exists()
        )
        self.assertTrue(IDCard.objects.exists())
        self.assertTrue(SeedMarker.objects.filter(tier="SEED_DEMO").exists())
        self.assertEqual(PortalAccount.objects.count(), 2)
        self.assertTrue(
            PortalAccount.objects.filter(
                account_type="individual", user__email_verified=True, learner__isnull=False
            ).exists()
        )
        self.assertTrue(
            PortalAccount.objects.filter(
                account_type="corporate_lead", corporate_account__isnull=False
            ).exists()
        )
        self.assertTrue(User.objects.filter(username="demo_corporate@tcms.local").exists())
        self.assertTrue(User.objects.filter(username="demo_reports").exists())
        self.assertTrue(User.objects.filter(username="demo_hr_manager").exists())
        self.assertTrue(User.objects.filter(username="demo_hr_officer").exists())

    def test_idempotent_and_reset(self):
        call_command("seed_demo")
        count = TrainingRecord.objects.count()
        call_command("seed_demo")
        self.assertEqual(TrainingRecord.objects.count(), count)
        call_command("seed_demo", "--reset")
        self.assertEqual(TrainingRecord.objects.count(), count)
        self.assertEqual(
            set(TrainingRecord.objects.values_list("status_id", flat=True)),
            {int(c) for c in WorkflowStatusCode},
        )


class DemoRoleSmokeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)
        call_command("seed_demo", verbosity=0)

    def _client(self, role: RoleCode) -> APIClient:
        user = User.objects.filter(roles__id=int(role)).first()
        self.assertIsNotNone(user, f"missing demo user for {role.name}")
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_hr_officer_people_flow_and_sensitive_denials(self):
        officer = self._client(RoleCode.HR_OFFICER)
        employees = officer.get("/api/v1/payroll-employees/")
        self.assertEqual(employees.status_code, 200, employees.data)
        employee_id = employees.data["data"][0]["id"]

        detail = officer.get(f"/api/v1/payroll-employees/{employee_id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("tax_id", detail.data)
        self.assertNotIn("basic_salary", detail.data)
        self.assertNotIn("bank_account", detail.data)

        for path in (
            "/api/v1/payslips/",
            "/api/v1/pay-elements/",
            "/api/v1/provisions/",
            "/api/v1/tax-bands/",
            "/api/v1/payment-files/",
            "/api/v1/pay-runs/",
            "/api/v1/accounts/",
            "/api/v1/corporate-accounts/",
        ):
            with self.subTest(path=path):
                self.assertEqual(officer.get(path).status_code, 403)

        created = officer.post(
            "/api/v1/timesheets/",
            {
                "employee": employee_id,
                "period_start": "2026-11-01",
                "period_end": "2026-11-30",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        timesheet_id = created.data["id"]
        self.assertEqual(
            officer.post(
                f"/api/v1/timesheets/{timesheet_id}/submit/", {}, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(
            officer.post(
                f"/api/v1/timesheets/{timesheet_id}/approve/", {}, format="json"
            ).status_code,
            403,
        )

        dashboard = officer.get("/api/v1/dashboard/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.data["kpis"]["revenue_collected_90d"], "0.00")
        self.assertEqual(dashboard.data["work_queue"]["unpaid_invoices"], [])

    def test_hr_manager_pay_access_and_timesheet_approval(self):
        manager = self._client(RoleCode.HR_MANAGER)
        employee_id = manager.get("/api/v1/payroll-employees/").data["data"][0]["id"]
        detail = manager.get(f"/api/v1/payroll-employees/{employee_id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("basic_salary", detail.data)

        for path in (
            "/api/v1/payslips/",
            "/api/v1/provisions/",
            "/api/v1/employee-pay-elements/",
        ):
            with self.subTest(path=path):
                self.assertEqual(manager.get(path).status_code, 200)

        for path in (
            "/api/v1/pay-runs/",
            "/api/v1/pay-elements/",
            "/api/v1/tax-bands/",
            "/api/v1/accounts/",
            "/api/v1/corporate-accounts/",
        ):
            with self.subTest(path=path):
                self.assertEqual(manager.get(path).status_code, 403)

        officer = self._client(RoleCode.HR_OFFICER)
        created = officer.post(
            "/api/v1/timesheets/",
            {
                "employee": employee_id,
                "period_start": "2026-12-01",
                "period_end": "2026-12-31",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        timesheet_id = created.data["id"]
        self.assertEqual(
            officer.post(
                f"/api/v1/timesheets/{timesheet_id}/submit/", {}, format="json"
            ).status_code,
            200,
        )
        approved = manager.post(
            f"/api/v1/timesheets/{timesheet_id}/approve/", {}, format="json"
        )
        self.assertEqual(approved.status_code, 200, approved.data)
        self.assertEqual(approved.data["status"], "approved")

    def test_finance_and_admin_workspaces_are_reachable(self):
        finance = self._client(RoleCode.ACCOUNTS)
        for path in (
            "/api/v1/accounts/",
            "/api/v1/journal-entries/",
            "/api/v1/journal-entries/trial-balance/",
            "/api/v1/pay-runs/",
            "/api/v1/payslips/",
            "/api/v1/payment-files/",
            "/api/v1/pay-elements/",
            "/api/v1/tax-bands/",
        ):
            with self.subTest(path=path):
                self.assertEqual(finance.get(path).status_code, 200)

        admin = self._client(RoleCode.SYSTEM_ADMIN)
        for path in (
            "/api/v1/notifications/",
            "/api/v1/notification-templates/",
            "/api/v1/documents/",
            "/api/v1/audit-events/",
            "/api/v1/workflow-statuses/",
            "/api/v1/approvals/",
            "/api/v1/outbox-events/",
            "/api/v1/outbox-events/health/",
            "/api/v1/webhook-deliveries/",
            "/api/v1/external-refs/",
            "/api/v1/seed-markers/",
            "/api/v1/certificate-sequences/",
            "/api/v1/report-defs/",
            "/api/v1/roles/",
        ):
            with self.subTest(path=path):
                self.assertEqual(admin.get(path).status_code, 200)


class SeedLoadTests(TestCase):
    def setUp(self):
        call_command("seed_roles")
        call_command("seed_data")

    def test_creates_and_resets_volume(self):
        call_command("seed_load", learners=5, records=12, employees=2, verbosity=0)
        self.assertEqual(Learner.objects.filter(badge_no__startswith="LOAD-").count(), 5)
        self.assertEqual(
            TrainingRecord.objects.filter(learner__badge_no__startswith="LOAD-").count(),
            12,
        )
        self.assertEqual(Employee.objects.filter(staff_no__startswith="LOAD-").count(), 2)

        call_command("seed_load", "--reset", verbosity=0)
        self.assertFalse(Learner.objects.filter(badge_no__startswith="LOAD-").exists())
        self.assertFalse(TrainingRecord.objects.filter(learner__badge_no__startswith="LOAD-").exists())
        self.assertFalse(Employee.objects.filter(staff_no__startswith="LOAD-").exists())
