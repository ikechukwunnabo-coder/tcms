"""Finance & payroll tests — PAYE, journals, pay runs, timesheets, bank files."""
from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.common.enums import (
    JournalStatus,
    PayRunStatus,
    RoleCode,
    TimeEntryKind,
    TimesheetStatus,
)
from apps.payroll import services
from apps.payroll.exceptions import (
    JournalError,
    PayrollConfigError,
    PayRunError,
    PayRunStateError,
    SegregationOfDutiesError,
    UnbalancedJournal,
)
from apps.payroll.models import (
    Account,
    Employee,
    EmployeePayElement,
    PayElement,
    PaymentFile,
    PayRun,
    Payslip,
    Provision,
    TaxBand,
    TimeEntry,
)


def staff(username: str, role: RoleCode) -> User:
    user = User.objects.create_user(
        username=username, email=f"{username}@payroll.test", password="pw12345678"
    )
    user.roles.add(Role.objects.get(pk=int(role)))
    return user


def pay_element(code: str) -> PayElement:
    return PayElement.objects.get(code=code)


class PayeTests(TestCase):
    def test_seeded_bands_are_effective_in_2026(self):
        bands = services.effective_tax_bands(date(2026, 6, 30))
        self.assertEqual(len(bands), 6)
        self.assertEqual(bands[0].rate_pct, Decimal("0.000"))

    def test_annual_below_threshold_is_zero(self):
        self.assertEqual(services.annual_paye(Decimal("800000")), Decimal("0.00"))

    def test_annual_fifteen_percent_band(self):
        self.assertEqual(services.annual_paye(Decimal("3000000")), Decimal("330000.00"))

    def test_annual_third_band(self):
        self.assertEqual(services.annual_paye(Decimal("12000000")), Decimal("1950000.00"))

    def test_annual_top_band(self):
        tax = services.annual_paye(Decimal("60000000"))
        self.assertEqual(tax, Decimal("12930000.00"))

    def test_monthly_paye_is_annualised_and_divided(self):
        monthly = services.monthly_paye(
            taxable_gross=Decimal("300000"),
            pension_employee=Decimal("22500"),
            on_date=date(2026, 6, 30),
        )
        self.assertEqual(monthly, Decimal("32450.00"))

    def test_pension_rates_default_to_contributory_minimum(self):
        employee, employer = services.pension_rates()
        self.assertEqual(employee, Decimal("7.5"))
        self.assertEqual(employer, Decimal("7.5"))

    def test_missing_bands_raise(self):
        TaxBand.objects.all().delete()
        with self.assertRaises(PayrollConfigError):
            services.annual_paye(Decimal("1000000"))


class PayrollConfigTests(TestCase):
    def test_seeded_configuration_is_valid(self):
        result = services.validate_configuration(date(2026, 6, 30))
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["tax_bands"], 6)

    def test_missing_gl_account_is_reported(self):
        Account.objects.filter(code="500000").delete()
        result = services.validate_configuration(date(2026, 6, 30))
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("PAYROLL_GL_SALARY_EXPENSE" in error for error in result["errors"])
        )

    def test_missing_bands_are_reported(self):
        TaxBand.objects.all().delete()
        result = services.validate_configuration(date(2026, 6, 30))
        self.assertFalse(result["ok"])
        self.assertIn("paye_bands_missing", result["errors"])


class JournalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        cls.preparer = staff("prep", RoleCode.ACCOUNTS)
        cls.approver = staff("approver", RoleCode.MD)
        cls.expense = Account.objects.get(code="500000")
        cls.payable = Account.objects.get(code="210000")

    def _journal(self):
        return services.create_journal(
            lines=[
                {"account": self.expense, "debit": Decimal("1000")},
                {"account": self.payable, "credit": Decimal("1000")},
            ],
            date=date(2026, 5, 31),
            memo="Test",
            actor=self.preparer,
        )

    def test_balanced_journal_posts(self):
        journal = self._journal()
        self.assertEqual(journal.status, JournalStatus.DRAFT)
        journal = services.post_journal(journal, actor=self.approver)
        self.assertEqual(journal.status, JournalStatus.POSTED)
        self.assertEqual(journal.approved_by, self.approver)

    def test_unbalanced_journal_is_rejected(self):
        with self.assertRaises(UnbalancedJournal):
            services.create_journal(
                lines=[
                    {"account": self.expense, "debit": Decimal("1000")},
                    {"account": self.payable, "credit": Decimal("900")},
                ],
                actor=self.preparer,
            )

    def test_line_needs_exactly_one_side(self):
        with self.assertRaises(JournalError):
            services.create_journal(
                lines=[
                    {"account": self.expense, "debit": Decimal("1000")},
                    {"account": self.payable, "debit": Decimal("1000")},
                ],
                actor=self.preparer,
            )

    def test_preparer_cannot_post_own_journal(self):
        journal = self._journal()
        with self.assertRaises(SegregationOfDutiesError):
            services.post_journal(journal, actor=self.preparer)

    def test_trial_balance_only_includes_posted_journals(self):
        journal = self._journal()
        self.assertEqual(services.trial_balance(as_of=date(2026, 5, 31)), [])
        services.post_journal(journal, actor=self.approver)
        rows = {row["code"]: row for row in services.trial_balance(as_of=date(2026, 5, 31))}
        self.assertEqual(rows["500000"]["debit"], Decimal("1000.00"))
        self.assertEqual(rows["210000"]["credit"], Decimal("1000.00"))


class PayrollFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        cls.preparer = staff("payroll_prep", RoleCode.ACCOUNTS)
        cls.approver = staff("payroll_md", RoleCode.MD)
        cls.employee_one = Employee.objects.create(
            staff_no="TASL001",
            full_name="Ada Okafor",
            basic_salary=Decimal("450000"),
            hourly_rate=Decimal("5000"),
            bank_account="0123456789",
            bank_name="GTBank",
            bank_code="058",
            account_name="Ada Okafor",
        )
        cls.employee_two = Employee.objects.create(
            staff_no="TASL002",
            full_name="Bola Adeyemi",
            basic_salary=Decimal("300000"),
            hourly_rate=Decimal("4000"),
            bank_account="0234567891",
            bank_name="Access Bank",
            bank_code="044",
            account_name="Bola Adeyemi",
        )
        for employee, basic, housing, transport in (
            (cls.employee_one, "450000", "90000", "50000"),
            (cls.employee_two, "300000", "60000", "50000"),
        ):
            EmployeePayElement.objects.create(
                employee=employee, element=pay_element("BASIC"), amount=Decimal(basic)
            )
            EmployeePayElement.objects.create(
                employee=employee, element=pay_element("HOUSING"), amount=Decimal(housing)
            )
            EmployeePayElement.objects.create(
                employee=employee, element=pay_element("TRANSPORT"), amount=Decimal(transport)
            )
        EmployeePayElement.objects.create(
            employee=cls.employee_two, element=pay_element("LOAN"), amount=Decimal("25000")
        )


class PayRunTests(PayrollFixture):
    def _run(self):
        pay_run = services.create_pay_run(
            period="2026-05", run_date=date(2026, 5, 31), actor=self.preparer
        )
        return services.compute_pay_run(pay_run, actor=self.preparer)

    def test_compute_builds_payslips_and_totals(self):
        pay_run = self._run()
        self.assertEqual(pay_run.payslips.count(), 2)
        self.assertEqual(pay_run.total_gross, Decimal("1000000.00"))
        self.assertEqual(pay_run.total_tax, Decimal("131500.00"))
        self.assertEqual(pay_run.total_pension_employee, Decimal("75000.00"))
        self.assertEqual(pay_run.total_pension_employer, Decimal("75000.00"))
        self.assertEqual(pay_run.total_deductions, Decimal("231500.00"))
        self.assertEqual(pay_run.total_net, Decimal("768500.00"))

    def test_individual_payslip_breakdown(self):
        self._run()
        payslip = Payslip.objects.get(employee=self.employee_one)
        self.assertEqual(payslip.gross, Decimal("590000.00"))
        self.assertEqual(payslip.tax, Decimal("80735.00"))
        self.assertEqual(payslip.pension, Decimal("44250.00"))
        self.assertEqual(payslip.pension_employer, Decimal("44250.00"))
        self.assertEqual(payslip.net, Decimal("465015.00"))
        self.assertTrue(payslip.lines.filter(description="PAYE").exists())

    def test_other_deductions_reduce_net(self):
        self._run()
        payslip = Payslip.objects.get(employee=self.employee_two)
        self.assertEqual(payslip.other_deductions, Decimal("25000.00"))
        self.assertEqual(payslip.net, Decimal("303485.00"))

    def test_preparer_cannot_approve(self):
        pay_run = self._run()
        with self.assertRaises(SegregationOfDutiesError):
            services.approve_pay_run(pay_run, actor=self.preparer)

    def test_approve_requires_payslips(self):
        pay_run = services.create_pay_run(
            period="2026-05", run_date=date(2026, 5, 31), actor=self.preparer
        )
        with self.assertRaises(PayRunError):
            services.approve_pay_run(pay_run, actor=self.approver)

    def test_post_creates_balanced_journal(self):
        pay_run = self._run()
        services.approve_pay_run(pay_run, actor=self.approver)
        pay_run = services.post_pay_run(pay_run, actor=self.approver)
        self.assertEqual(pay_run.status, PayRunStatus.POSTED)
        self.assertIsNotNone(pay_run.journal_id)
        journal = pay_run.journal
        self.assertEqual(journal.total_debit, journal.total_credit)
        self.assertEqual(journal.total_debit, Decimal("1075000.00"))

    def test_bank_file_contains_net_pay_rows(self):
        pay_run = self._run()
        services.approve_pay_run(pay_run, actor=self.approver)
        services.post_pay_run(pay_run, actor=self.approver)
        payment_file = services.generate_bank_file(pay_run, actor=self.preparer)
        self.assertIsInstance(payment_file, PaymentFile)
        self.assertIn("TASL001", payment_file.content)
        self.assertIn("465015.00", payment_file.content)
        self.assertEqual(len(payment_file.content.strip().splitlines()), 3)

    def test_bank_file_requires_posted_run(self):
        pay_run = self._run()
        with self.assertRaises(PayRunStateError):
            services.generate_bank_file(pay_run, actor=self.preparer)

    def test_bank_file_neutralises_formula_injection(self):
        self.employee_two.account_name = "=cmd|' /C calc'!A0"
        self.employee_two.save(update_fields=["account_name"])
        pay_run = self._run()
        services.approve_pay_run(pay_run, actor=self.approver)
        services.post_pay_run(pay_run, actor=self.approver)
        payment_file = services.generate_bank_file(pay_run, actor=self.preparer)
        self.assertIn("'=cmd", payment_file.content)
        self.assertNotIn("\n=cmd", payment_file.content)

    def test_duplicate_period_is_rejected(self):
        self._run()
        with self.assertRaises(PayRunError):
            services.create_pay_run(
                period="2026-05", run_date=date(2026, 5, 31), actor=self.preparer
            )

    def test_bad_period_is_rejected(self):
        with self.assertRaises(PayRunError):
            services.create_pay_run(period="2026/05", actor=self.preparer)


class TimesheetTests(PayrollFixture):
    def _timesheet(self):
        timesheet = services.create_timesheet(
            employee=self.employee_one,
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
            actor=self.preparer,
        )
        for day in range(1, 6):
            TimeEntry.objects.create(
                timesheet=timesheet,
                work_date=date(2026, 6, day),
                hours=Decimal("8"),
                rate=Decimal("5000"),
            )
        TimeEntry.objects.create(
            timesheet=timesheet,
            work_date=date(2026, 6, 6),
            hours=Decimal("4"),
            rate=Decimal("5000"),
            kind=TimeEntryKind.OT150,
        )
        return timesheet

    def test_submit_computes_totals(self):
        timesheet = services.submit_timesheet(self._timesheet(), actor=self.preparer)
        self.assertEqual(timesheet.status, TimesheetStatus.SUBMITTED)
        self.assertEqual(timesheet.total_hours, Decimal("44.00"))
        self.assertEqual(timesheet.worked_days, Decimal("6"))

    def test_approve_requires_a_different_user(self):
        timesheet = services.submit_timesheet(self._timesheet(), actor=self.preparer)
        with self.assertRaises(SegregationOfDutiesError):
            services.approve_timesheet(timesheet, actor=self.preparer)
        timesheet = services.approve_timesheet(timesheet, actor=self.approver)
        self.assertEqual(timesheet.status, TimesheetStatus.APPROVED)

    def test_timesheet_hours_feed_pay_run_with_overtime(self):
        timesheet = services.submit_timesheet(self._timesheet(), actor=self.preparer)
        services.approve_timesheet(timesheet, actor=self.approver)
        pay_run = services.create_pay_run(
            period="2026-06", run_date=date(2026, 6, 30), actor=self.preparer
        )
        pay_run = services.compute_pay_run(pay_run, actor=self.preparer)
        payslip = PayRun.objects.get(pk=pay_run.pk).payslips.get(
            employee=self.employee_one
        )
        self.assertEqual(payslip.worked_hours, Decimal("44.00"))
        self.assertEqual(payslip.gross, Decimal("820000.00"))
        self.assertEqual(payslip.net, Decimal("653615.00"))

    def test_provision_accrues_worked_days(self):
        timesheet = services.submit_timesheet(self._timesheet(), actor=self.preparer)
        timesheet = services.approve_timesheet(timesheet, actor=self.approver)
        provision = services.accrue_provision(
            timesheet=timesheet,
            daily_rate=Decimal("16000"),
            as_of=date(2026, 6, 30),
            actor=self.preparer,
        )
        self.assertEqual(provision.days, Decimal("6.00"))
        self.assertEqual(provision.amount, Decimal("96000.00"))
        self.assertTrue(Provision.objects.filter(pk=provision.pk).exists())


class PayrollAPITests(PayrollFixture, APITestCase):
    def setUp(self):
        self.accounts_user = staff("api_accounts", RoleCode.ACCOUNTS)
        self.md_user = staff("api_md", RoleCode.MD)
        self.nobody = User.objects.create_user(
            username="api_nobody", email="nobody@payroll.test", password="pw12345678"
        )

    def test_unauthenticated_is_rejected(self):
        response = self.client.get(reverse("pay-runs-list"))
        self.assertEqual(response.status_code, 401)

    def test_user_without_role_is_forbidden(self):
        self.client.force_authenticate(self.nobody)
        response = self.client.get(reverse("pay-runs-list"))
        self.assertEqual(response.status_code, 403)

    def test_pay_run_lifecycle_over_api(self):
        self.client.force_authenticate(self.accounts_user)
        response = self.client.post(
            reverse("pay-runs-list"), {"period": "2026-08"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        pay_run_id = response.data["id"]

        response = self.client.post(
            reverse("pay-runs-compute", args=[pay_run_id]), format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_net"], "768500.00")

        response = self.client.post(
            reverse("pay-runs-approve", args=[pay_run_id]), format="json"
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(self.md_user)
        response = self.client.post(
            reverse("pay-runs-approve", args=[pay_run_id]), format="json"
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse("pay-runs-post", args=[pay_run_id]), format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["journal"])

        response = self.client.post(
            reverse("pay-runs-bank-file", args=[pay_run_id]), format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("PAYROLL-2026-08-BANK.csv", response.data["filename"])

        response = self.client.get(
            reverse("payment-files-download", args=[response.data["id"]])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])

    def test_unbalanced_journal_api_returns_422(self):
        self.client.force_authenticate(self.accounts_user)
        expense = Account.objects.get(code="500000")
        payable = Account.objects.get(code="210000")
        response = self.client.post(
            reverse("journal-entries-list"),
            {
                "date": "2026-06-30",
                "memo": "bad",
                "lines": [
                    {"account": expense.pk, "debit": "100.00"},
                    {"account": payable.pk, "credit": "90.00"},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["error"], "journal_not_balanced")

    def test_trial_balance_endpoint(self):
        self.client.force_authenticate(self.accounts_user)
        expense = Account.objects.get(code="500000")
        payable = Account.objects.get(code="210000")
        journal = services.create_journal(
            lines=[
                {"account": expense, "debit": Decimal("500")},
                {"account": payable, "credit": Decimal("500")},
            ],
            date=date(2026, 6, 30),
            actor=self.accounts_user,
        )
        services.post_journal(journal, actor=self.md_user)
        response = self.client.get(
            reverse("journal-entries-trial-balance"), {"as_of": "2026-06-30"}
        )
        self.assertEqual(response.status_code, 200)
        rows = {row["code"]: row for row in response.data}
        self.assertEqual(rows["500000"]["debit"], Decimal("500.00"))
