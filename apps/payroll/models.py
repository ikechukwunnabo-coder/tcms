"""Finance & payroll models — M11 (design ``02-database.md`` §M11).

Rules: R-FIN-01 double-entry GL, R-FIN-02 income/expense per account,
R-FIN-03 gross/net payroll, R-FIN-04 PAYE + pension, R-FIN-05 timesheets feed
payroll, R-FIN-06 provisions, R-FIN-07 bank payment files, R-FIN-08 SoD.

The legacy AXIS system delegated PAYE/pension to an external Condor engine and
kept only the SAP journal file (``webserver/AxisNew/SAP_Common.asp``); those
values are configurable here (``PAYROLL_*`` settings + :class:`TaxBand`) and
must be confirmed with the client before parallel run.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.enums import (
    AccountType,
    JournalStatus,
    PayElementKind,
    PayFrequency,
    PaymentFileStatus,
    PayRunStatus,
    TimeEntryKind,
    TimesheetStatus,
)
from apps.common.models import TimeStampedModel


class Account(TimeStampedModel):
    """Chart of accounts (asset/liability/equity/income/expense)."""

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=16, choices=AccountType.choices)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "account"
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"

    @property
    def is_leaf(self) -> bool:
        return not self.children.exists()


class Journal(TimeStampedModel):
    journal_no = models.CharField(max_length=32, unique=True)
    date = models.DateField()
    memo = models.TextField(blank=True)
    source = models.CharField(max_length=32, blank=True)
    status = models.CharField(
        max_length=16, choices=JournalStatus.choices, default=JournalStatus.DRAFT
    )
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    void_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "journal"
        ordering = ["-date", "-id"]

    def __str__(self) -> str:
        return self.journal_no

    @property
    def total_debit(self):
        return self.lines.aggregate(total=models.Sum("debit"))["total"] or 0

    @property
    def total_credit(self):
        return self.lines.aggregate(total=models.Sum("credit"))["total"] or 0


class JournalSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "journal_sequence"


class JournalLine(models.Model):
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="journal_lines")
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    dimension = models.CharField(max_length=64, blank=True)
    memo = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "journal_line"


class Employee(TimeStampedModel):
    staff_no = models.CharField(max_length=32, unique=True)
    full_name = models.CharField(max_length=200)
    learner = models.ForeignKey(
        "learners.Learner", null=True, blank=True, on_delete=models.SET_NULL
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    pay_frequency = models.CharField(
        max_length=16, choices=PayFrequency.choices, default=PayFrequency.MONTHLY
    )
    basic_salary = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    hourly_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bank_name = models.CharField(max_length=100, blank=True)
    bank_code = models.CharField(max_length=16, blank=True)
    account_name = models.CharField(max_length=150, blank=True)
    bank_account = models.CharField(max_length=64, blank=True)
    tax_id = models.CharField(max_length=64, blank=True)
    pension_id = models.CharField(max_length=64, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "employee"
        ordering = ["staff_no"]

    def __str__(self) -> str:
        return f"{self.staff_no} {self.full_name}"


class PayElement(TimeStampedModel):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=16, choices=PayElementKind.choices)
    taxable = models.BooleanField(default=False)
    pensionable = models.BooleanField(default=False)
    formula = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "pay_element"
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class EmployeePayElement(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="pay_elements")
    element = models.ForeignKey(PayElement, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = "employee_pay_element"
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "element"], name="uq_employee_pay_element"
            )
        ]


class PayRun(TimeStampedModel):
    period = models.CharField(max_length=16)  # YYYY-MM
    run_date = models.DateField()
    status = models.CharField(
        max_length=16, choices=PayRunStatus.choices, default=PayRunStatus.DRAFT
    )
    total_gross = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_pension_employee = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_pension_employer = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_net = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    journal = models.OneToOneField(
        Journal, null=True, blank=True, on_delete=models.SET_NULL, related_name="pay_run"
    )

    class Meta:
        db_table = "pay_run"
        ordering = ["-period", "-id"]

    def __str__(self) -> str:
        return f"Pay run {self.period} ({self.status})"


class Payslip(models.Model):
    pay_run = models.ForeignKey(PayRun, on_delete=models.CASCADE, related_name="payslips")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="payslips")
    gross = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    pension = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    pension_employer = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    worked_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    object_key = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "payslip"
        constraints = [
            models.UniqueConstraint(fields=["pay_run", "employee"], name="uq_pay_run_employee")
        ]
        ordering = ["employee__staff_no"]

    def __str__(self) -> str:
        return f"{self.employee.staff_no} {self.pay_run.period}"


class PayslipLine(models.Model):
    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name="lines")
    element = models.ForeignKey(
        PayElement, null=True, blank=True, on_delete=models.SET_NULL
    )
    description = models.CharField(max_length=200)
    kind = models.CharField(max_length=16, choices=PayElementKind.choices)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = "payslip_line"


class Timesheet(TimeStampedModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="timesheets")
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(
        max_length=16, choices=TimesheetStatus.choices, default=TimesheetStatus.DRAFT
    )
    total_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    worked_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "timesheet"
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "period_start", "period_end"],
                name="uq_timesheet_employee_period",
            )
        ]
        ordering = ["-period_start", "employee__staff_no"]

    def __str__(self) -> str:
        return f"{self.employee.staff_no} {self.period_start}–{self.period_end}"


class TimeEntry(models.Model):
    timesheet = models.ForeignKey(Timesheet, on_delete=models.CASCADE, related_name="entries")
    work_date = models.DateField()
    hours = models.DecimalField(max_digits=6, decimal_places=2)
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    kind = models.CharField(
        max_length=16, choices=TimeEntryKind.choices, default=TimeEntryKind.REGULAR
    )
    is_holiday = models.BooleanField(default=False)
    project = models.CharField(max_length=64, blank=True)
    job_no = models.CharField(max_length=64, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        db_table = "time_entry"
        ordering = ["work_date", "id"]


class Provision(TimeStampedModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="provisions")
    timesheet = models.ForeignKey(
        Timesheet, null=True, blank=True, on_delete=models.SET_NULL, related_name="provisions"
    )
    kind = models.CharField(max_length=32)
    days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    as_of = models.DateField()

    class Meta:
        db_table = "provision"
        ordering = ["-as_of", "employee__staff_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "kind", "as_of"], name="uq_provision_employee_kind_date"
            )
        ]


class TaxBand(TimeStampedModel):
    """PAYE band table. ``upper`` is null for the top band (no ceiling)."""

    name = models.CharField(max_length=100)
    lower = models.DecimalField(max_digits=16, decimal_places=2)
    upper = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    rate_pct = models.DecimalField(max_digits=6, decimal_places=3)
    effective_from = models.DateField()
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "tax_band"
        ordering = ["effective_from", "lower"]

    def __str__(self) -> str:
        return f"{self.name} {self.rate_pct}%"


class PaymentFile(TimeStampedModel):
    """Generated bank/payment instruction file (R-FIN-07)."""

    pay_run = models.ForeignKey(PayRun, on_delete=models.CASCADE, related_name="payment_files")
    filename = models.CharField(max_length=200)
    content = models.TextField()
    status = models.CharField(
        max_length=16, choices=PaymentFileStatus.choices, default=PaymentFileStatus.GENERATED
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        db_table = "payment_file"
        ordering = ["-created_at"]
