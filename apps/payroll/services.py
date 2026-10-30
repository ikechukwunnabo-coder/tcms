"""Finance & payroll services — M11.

Rules implemented:
  R-FIN-01  every journal balances (Σ debit = Σ credit) before it posts.
  R-FIN-02  income/expense post to chart-of-accounts codes from settings.
  R-FIN-03  gross = Σ earnings; net = gross − PAYE − pension − deductions.
  R-FIN-04  PAYE from effective :class:`TaxBand` rows; pension rates from
            settings (7.5% / 7.5% minimum per the Contributory Pension Scheme).
  R-FIN-05  approved timesheets feed the pay run (hours × rate by kind).
  R-FIN-06  provisions accrue worked days × daily rate.
  R-FIN-07  bank payment file generated per pay run.
  R-FIN-08  preparer ≠ approver for journals and pay runs.

Legacy note: AXIS itself never computed PAYE/pension — the external Condor
engine did (``ReadPaySlipFile.asp``) and AXIS only produced the SAP journal
(``SAP_Common.asp``). Rates, bands and GL codes are therefore configuration.
:func:`validate_configuration` (also exposed as ``manage.py payroll_check``)
verifies them before a go-live or parallel run.
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from io import StringIO

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit.services import write_audit
from apps.common.enums import (
    JournalStatus,
    PayElementKind,
    PaymentFileStatus,
    PayRunStatus,
    TimeEntryKind,
    TimesheetStatus,
)
from apps.integration.services import publish_event
from apps.payroll.exceptions import (
    JournalError,
    JournalStateError,
    PayrollConfigError,
    PayRunError,
    PayRunStateError,
    SegregationOfDutiesError,
    TimesheetError,
    TimesheetStateError,
    UnbalancedJournal,
)
from apps.payroll.models import (
    Account,
    Employee,
    Journal,
    JournalLine,
    JournalSequence,
    PaymentFile,
    PayRun,
    Payslip,
    PayslipLine,
    Provision,
    TaxBand,
    Timesheet,
)

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


def _q(value) -> Decimal:
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _setting(name: str, default):
    return getattr(settings, name, default)


def _require_account(code: str) -> Account:
    account = Account.objects.filter(code=code, active=True).first()
    if account is None:
        raise PayrollConfigError(f"payroll_account_missing:{code}")
    return account


def _require_separate(preparer, actor, label: str = "journal") -> None:
    if preparer is not None and actor is not None and preparer.pk == actor.pk:
        raise SegregationOfDutiesError(
            f"{label}_preparer_cannot_approve"
        )


# ── Chart of accounts & journals ─────────────────────────────────────────────


@transaction.atomic
def _next_journal_no(year: int) -> str:
    seq, _ = JournalSequence.objects.select_for_update().get_or_create(year=year)
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    return f"JV-{year}-{seq.last_number:06d}"


def _validate_lines(lines: list[dict]) -> tuple[Decimal, Decimal]:
    if not lines:
        raise JournalError("journal_requires_lines")
    total_debit = ZERO
    total_credit = ZERO
    for index, line in enumerate(lines, start=1):
        debit = _q(line.get("debit") or 0)
        credit = _q(line.get("credit") or 0)
        if debit < 0 or credit < 0:
            raise JournalError(f"journal_line_{index}_negative")
        if (debit > 0) == (credit > 0):
            raise JournalError(f"journal_line_{index}_needs_one_side")
        total_debit += debit
        total_credit += credit
    if total_debit != total_credit:
        raise UnbalancedJournal(
            f"journal_not_balanced: debit={total_debit} credit={total_credit}"
        )
    return total_debit, total_credit


@transaction.atomic
def create_journal(
    *,
    lines: list[dict],
    date: date | None = None,
    memo: str = "",
    source: str = "",
    actor=None,
) -> Journal:
    """Create a balanced draft journal. Each line: account/code, debit, credit."""
    _validate_lines(lines)
    journal_date = date or timezone.localdate()
    journal = Journal.objects.create(
        journal_no=_next_journal_no(journal_date.year),
        date=journal_date,
        memo=memo,
        source=source,
        status=JournalStatus.DRAFT,
        prepared_by=actor,
        created_by=actor,
    )
    for line in lines:
        account = line["account"]
        if isinstance(account, str):
            account = _require_account(account)
        JournalLine.objects.create(
            journal=journal,
            account=account,
            debit=_q(line.get("debit") or 0),
            credit=_q(line.get("credit") or 0),
            dimension=line.get("dimension", ""),
            memo=line.get("memo", ""),
        )
    write_audit(
        action="journal.create",
        entity="journal",
        entity_id=journal.pk,
        actor=actor,
        after={"journal_no": journal.journal_no, "source": source},
    )
    return journal


@transaction.atomic
def post_journal(journal: Journal, *, actor=None) -> Journal:
    """Post a draft journal; preparer and poster must differ (R-FIN-08)."""
    if journal.status != JournalStatus.DRAFT:
        raise JournalStateError("journal_not_draft")
    _require_separate(journal.prepared_by, actor)
    lines = list(journal.lines.all())
    _validate_lines(
        [
            {"debit": line.debit, "credit": line.credit}
            for line in lines
        ]
    )
    now = timezone.now()
    journal.status = JournalStatus.POSTED
    journal.approved_by = actor
    journal.approved_at = now
    journal.posted_by = actor
    journal.posted_at = now
    journal.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "posted_by",
            "posted_at",
            "updated_at",
        ]
    )
    write_audit(
        action="journal.post",
        entity="journal",
        entity_id=journal.pk,
        actor=actor,
        after={"journal_no": journal.journal_no},
    )
    return journal


@transaction.atomic
def void_journal(journal: Journal, *, actor=None, reason: str = "") -> Journal:
    """Void a journal that has not been posted."""
    if journal.status == JournalStatus.POSTED:
        raise JournalStateError("journal_already_posted")
    if journal.status == JournalStatus.VOID:
        raise JournalStateError("journal_already_void")
    journal.status = JournalStatus.VOID
    journal.void_reason = reason
    journal.save(update_fields=["status", "void_reason", "updated_at"])
    write_audit(
        action="journal.void",
        entity="journal",
        entity_id=journal.pk,
        actor=actor,
        after={"reason": reason},
    )
    return journal


# ── PAYE & pension ───────────────────────────────────────────────────────────


def effective_tax_bands(on_date: date | None = None) -> list[TaxBand]:
    """Bands for the latest schedule effective on ``on_date``."""
    on_date = on_date or timezone.localdate()
    latest = (
        TaxBand.objects.filter(active=True, effective_from__lte=on_date)
        .order_by("-effective_from")
        .values_list("effective_from", flat=True)
        .first()
    )
    if latest is None:
        return []
    return list(
        TaxBand.objects.filter(active=True, effective_from=latest).order_by("lower")
    )


def annual_paye(taxable_income, bands: list[TaxBand] | None = None) -> Decimal:
    """Progressive PAYE on annual taxable income (R-FIN-04)."""
    if not bands:
        bands = effective_tax_bands()
    if not bands:
        raise PayrollConfigError("paye_bands_missing")
    income = _q(taxable_income)
    tax = ZERO
    for band in bands:
        lower = _q(band.lower)
        if income <= lower:
            break
        upper = _q(band.upper) if band.upper is not None else None
        slice_top = income if upper is None else min(income, upper)
        slice_amount = slice_top - lower
        if slice_amount > 0:
            tax += slice_amount * Decimal(str(band.rate_pct)) / Decimal("100")
    return _q(tax)


def monthly_paye(
    *,
    taxable_gross,
    pension_employee,
    on_date: date | None = None,
    annual_relief=None,
) -> Decimal:
    """Annualise, apply the bands, then return the monthly PAYE."""
    on_date = on_date or timezone.localdate()
    relief = (
        Decimal(str(annual_relief))
        if annual_relief is not None
        else Decimal(str(_setting("PAYROLL_PAYE_ANNUAL_RELIEF", 0)))
    )
    annual_taxable = max(
        ZERO, (_q(taxable_gross) - _q(pension_employee)) * Decimal("12") - relief
    )
    return _q(annual_paye(annual_taxable, effective_tax_bands(on_date)) / Decimal("12"))


def pension_rates() -> tuple[Decimal, Decimal]:
    employee = Decimal(str(_setting("PAYROLL_PENSION_EMPLOYEE_PCT", "7.5")))
    employer = Decimal(str(_setting("PAYROLL_PENSION_EMPLOYER_PCT", "7.5")))
    return employee, employer


_GL_SETTINGS = (
    "PAYROLL_GL_SALARY_EXPENSE",
    "PAYROLL_GL_EMPLOYER_PENSION",
    "PAYROLL_GL_NET_PAY",
    "PAYROLL_GL_PAYE",
    "PAYROLL_GL_PENSION",
    "PAYROLL_GL_DEDUCTIONS",
)


def validate_configuration(on_date: date | None = None) -> dict:
    """Check PAYE bands, pension rates and GL mappings before a pay run.

    Returns ``{"ok": bool, "errors": [...], ...}`` rather than raising so the
    management command can print every problem at once.
    """
    errors: list[str] = []
    bands = effective_tax_bands(on_date)
    if not bands:
        errors.append("paye_bands_missing")
    else:
        expected_lower = ZERO
        open_ended = False
        for band in bands:
            lower = _q(band.lower)
            if lower != expected_lower:
                errors.append(f"paye_band_gap_at:{lower}")
            rate = Decimal(str(band.rate_pct))
            if rate < 0 or rate > 100:
                errors.append(f"paye_band_rate_out_of_range:{band.pk}")
            if band.upper is None:
                open_ended = True
                expected_lower = None
            else:
                expected_lower = _q(band.upper)
        if not open_ended:
            errors.append("paye_bands_no_open_ended_top")
        if not bands[0].lower == 0:
            errors.append("paye_bands_must_start_at_zero")

    employee, employer = pension_rates()
    for label, rate in (("employee", employee), ("employer", employer)):
        if rate < 0 or rate > 100:
            errors.append(f"pension_{label}_rate_out_of_range")

    missing_accounts = []
    for name in _GL_SETTINGS:
        code = _setting(name, "")
        if not code or not Account.objects.filter(code=code, active=True).exists():
            missing_accounts.append(f"{name}={code}")
    errors.extend(f"gl_account_missing:{item}" for item in missing_accounts)

    return {
        "ok": not errors,
        "errors": errors,
        "tax_bands": len(bands),
        "pension_employee_pct": str(employee),
        "pension_employer_pct": str(employer),
    }


# ── Timesheets ───────────────────────────────────────────────────────────────


@transaction.atomic
def create_timesheet(
    *,
    employee: Employee,
    period_start: date,
    period_end: date,
    actor=None,
) -> Timesheet:
    if period_end < period_start:
        raise TimesheetError("timesheet_period_end_before_start")
    if Timesheet.objects.filter(
        employee=employee, period_start=period_start, period_end=period_end
    ).exists():
        raise TimesheetError("timesheet_already_exists")
    return Timesheet.objects.create(
        employee=employee,
        period_start=period_start,
        period_end=period_end,
        status=TimesheetStatus.DRAFT,
        created_by=actor,
    )


def _recompute_timesheet(timesheet: Timesheet) -> Timesheet:
    entries = list(timesheet.entries.all())
    timesheet.total_hours = _q(sum((entry.hours for entry in entries), ZERO))
    worked = {entry.work_date for entry in entries if entry.hours > 0}
    timesheet.worked_days = Decimal(len(worked))
    timesheet.save(update_fields=["total_hours", "worked_days", "updated_at"])
    return timesheet


@transaction.atomic
def submit_timesheet(timesheet: Timesheet, *, actor=None) -> Timesheet:
    if timesheet.status not in (TimesheetStatus.DRAFT, TimesheetStatus.REJECTED):
        raise TimesheetStateError("timesheet_not_submittable")
    _recompute_timesheet(timesheet)
    timesheet.status = TimesheetStatus.SUBMITTED
    timesheet.save(update_fields=["status", "updated_at"])
    write_audit(
        action="timesheet.submit",
        entity="timesheet",
        entity_id=timesheet.pk,
        actor=actor,
        after={"status": timesheet.status},
    )
    return timesheet


@transaction.atomic
def approve_timesheet(timesheet: Timesheet, *, actor=None) -> Timesheet:
    if timesheet.status != TimesheetStatus.SUBMITTED:
        raise TimesheetStateError("timesheet_not_submitted")
    _require_separate(timesheet.created_by, actor, "timesheet")
    timesheet.status = TimesheetStatus.APPROVED
    timesheet.approved_by = actor
    timesheet.approved_at = timezone.now()
    timesheet.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    for entry in timesheet.entries.all():
        entry.approved_by = actor
        entry.save(update_fields=["approved_by"])
    write_audit(
        action="timesheet.approve",
        entity="timesheet",
        entity_id=timesheet.pk,
        actor=actor,
        after={"status": timesheet.status},
    )
    return timesheet


@transaction.atomic
def reject_timesheet(timesheet: Timesheet, *, actor=None, reason: str = "") -> Timesheet:
    if timesheet.status != TimesheetStatus.SUBMITTED:
        raise TimesheetStateError("timesheet_not_submitted")
    timesheet.status = TimesheetStatus.REJECTED
    timesheet.save(update_fields=["status", "updated_at"])
    write_audit(
        action="timesheet.reject",
        entity="timesheet",
        entity_id=timesheet.pk,
        actor=actor,
        after={"reason": reason},
    )
    return timesheet


# ── Pay runs ─────────────────────────────────────────────────────────────────


def _month_bounds(period: str) -> tuple[date, date]:
    try:
        year, month = (int(part) for part in period.split("-"))
        start = date(year, month, 1)
    except (ValueError, TypeError):
        raise PayRunError("period_must_be_yyyy_mm") from None
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


@transaction.atomic
def create_pay_run(*, period: str, run_date: date | None = None, actor=None) -> PayRun:
    start, end = _month_bounds(period)
    if PayRun.objects.filter(period=period).exclude(
        status__in=[PayRunStatus.VOID]
    ).exists():
        raise PayRunError("pay_run_exists_for_period")
    return PayRun.objects.create(
        period=period,
        run_date=run_date or end,
        status=PayRunStatus.DRAFT,
        prepared_by=actor,
        created_by=actor,
    )


TIMESHEET_MULTIPLIERS = {
    TimeEntryKind.REGULAR: Decimal("1"),
    TimeEntryKind.OT150: Decimal("1.5"),
    TimeEntryKind.OT200: Decimal("2"),
}


def _timesheet_earnings(employee: Employee, start: date, end: date) -> list[dict]:
    lines = []
    timesheets = Timesheet.objects.filter(
        employee=employee,
        status=TimesheetStatus.APPROVED,
        period_start__gte=start,
        period_end__lte=end,
    ).prefetch_related("entries")
    totals: dict[str, dict] = {}
    for timesheet in timesheets:
        for entry in timesheet.entries.all():
            if entry.hours <= 0:
                continue
            kind = entry.kind
            rate = _q(entry.rate if entry.rate else employee.hourly_rate)
            bucket = totals.setdefault(
                kind,
                {"hours": ZERO, "rate": rate},
            )
            bucket["hours"] += Decimal(entry.hours)
    for kind, bucket in totals.items():
        if bucket["hours"] <= 0:
            continue
        effective_rate = _q(bucket["rate"] * TIMESHEET_MULTIPLIERS.get(kind, Decimal("1")))
        lines.append(
            {
                "element": None,
                "description": f"Timesheet {kind}",
                "kind": PayElementKind.EARNING,
                "quantity": _q(bucket["hours"]),
                "rate": effective_rate,
                "amount": _q(bucket["hours"] * effective_rate),
                "taxable": True,
                "pensionable": bool(_setting("PAYROLL_TIMESHEET_PENSIONABLE", False)),
            }
        )
    return lines


def _employee_payslip(employee: Employee, run: PayRun) -> dict | None:
    start, end = _month_bounds(run.period)
    lines: list[dict] = []

    for assignment in employee.pay_elements.select_related("element"):
        element = assignment.element
        if not element.active:
            continue
        lines.append(
            {
                "element": element,
                "description": element.name,
                "kind": element.kind,
                "quantity": Decimal("1"),
                "rate": _q(assignment.amount),
                "amount": _q(assignment.amount),
                "taxable": element.taxable,
                "pensionable": element.pensionable,
            }
        )
    lines.extend(_timesheet_earnings(employee, start, end))

    earnings = [line for line in lines if line["kind"] == PayElementKind.EARNING]
    deductions = [line for line in lines if line["kind"] == PayElementKind.DEDUCTION]
    employer_items = [line for line in lines if line["kind"] == PayElementKind.EMPLOYER]

    gross = _q(sum((line["amount"] for line in earnings), ZERO))
    if gross == 0 and not deductions:
        return None

    taxable_gross = _q(
        sum((line["amount"] for line in earnings if line["taxable"]), ZERO)
    )
    pension_base = _q(
        sum((line["amount"] for line in earnings if line["pensionable"]), ZERO)
    )
    employee_rate, employer_rate = pension_rates()
    pension_employee = _q(pension_base * employee_rate / Decimal("100"))
    pension_employer = _q(pension_base * employer_rate / Decimal("100"))
    tax = monthly_paye(
        taxable_gross=taxable_gross,
        pension_employee=pension_employee,
        on_date=run.run_date,
    )
    other_deductions = _q(sum((line["amount"] for line in deductions), ZERO))
    total_deductions = _q(tax + pension_employee + other_deductions)
    net = _q(gross - total_deductions)
    worked_hours = _q(
        sum(
            (
                line["quantity"]
                for line in earnings
                if line["element"] is None and line["description"].startswith("Timesheet")
            ),
            ZERO,
        )
    )

    return {
        "employee": employee,
        "gross": gross,
        "tax": tax,
        "pension": pension_employee,
        "pension_employer": pension_employer,
        "other_deductions": other_deductions,
        "deductions": total_deductions,
        "net": net,
        "worked_hours": worked_hours,
        "lines": lines,
        "employer_items": employer_items,
    }


@transaction.atomic
def compute_pay_run(pay_run: PayRun, *, actor=None) -> PayRun:
    """Rebuild payslips for a draft pay run (R-FIN-03/04/05)."""
    if pay_run.status != PayRunStatus.DRAFT:
        raise PayRunStateError("pay_run_not_draft")

    pay_run.payslips.all().delete()
    totals = {
        "gross": ZERO,
        "tax": ZERO,
        "pension_employee": ZERO,
        "pension_employer": ZERO,
        "deductions": ZERO,
        "net": ZERO,
    }
    employees = Employee.objects.filter(active=True).prefetch_related(
        "pay_elements__element"
    )
    for employee in employees:
        data = _employee_payslip(employee, pay_run)
        if data is None:
            continue
        payslip = Payslip.objects.create(
            pay_run=pay_run,
            employee=employee,
            gross=data["gross"],
            tax=data["tax"],
            pension=data["pension"],
            pension_employer=data["pension_employer"],
            other_deductions=data["other_deductions"],
            deductions=data["deductions"],
            net=data["net"],
            worked_hours=data["worked_hours"],
        )
        for line in data["lines"]:
            PayslipLine.objects.create(
                payslip=payslip,
                element=line["element"],
                description=line["description"],
                kind=line["kind"],
                quantity=line["quantity"],
                rate=line["rate"],
                amount=line["amount"],
            )
        if data["pension"]:
            PayslipLine.objects.create(
                payslip=payslip,
                description="Pension (employee)",
                kind=PayElementKind.DEDUCTION,
                amount=data["pension"],
            )
        if data["tax"]:
            PayslipLine.objects.create(
                payslip=payslip,
                description="PAYE",
                kind=PayElementKind.DEDUCTION,
                amount=data["tax"],
            )
        if data["pension_employer"]:
            PayslipLine.objects.create(
                payslip=payslip,
                description="Pension (employer)",
                kind=PayElementKind.EMPLOYER,
                amount=data["pension_employer"],
            )
        for line in data["employer_items"]:
            PayslipLine.objects.create(
                payslip=payslip,
                element=line["element"],
                description=line["description"],
                kind=PayElementKind.EMPLOYER,
                amount=line["amount"],
            )
        totals["gross"] += data["gross"]
        totals["tax"] += data["tax"]
        totals["pension_employee"] += data["pension"]
        totals["pension_employer"] += data["pension_employer"]
        totals["deductions"] += data["deductions"]
        totals["net"] += data["net"]

    pay_run.total_gross = _q(totals["gross"])
    pay_run.total_tax = _q(totals["tax"])
    pay_run.total_pension_employee = _q(totals["pension_employee"])
    pay_run.total_pension_employer = _q(totals["pension_employer"])
    pay_run.total_deductions = _q(totals["deductions"])
    pay_run.total_net = _q(totals["net"])
    pay_run.save(
        update_fields=[
            "total_gross",
            "total_tax",
            "total_pension_employee",
            "total_pension_employer",
            "total_deductions",
            "total_net",
            "updated_at",
        ]
    )
    write_audit(
        action="pay_run.compute",
        entity="pay_run",
        entity_id=pay_run.pk,
        actor=actor,
        after={"period": pay_run.period, "total_net": str(pay_run.total_net)},
    )
    return pay_run


@transaction.atomic
def approve_pay_run(pay_run: PayRun, *, actor=None) -> PayRun:
    if pay_run.status != PayRunStatus.DRAFT:
        raise PayRunStateError("pay_run_not_draft")
    if not pay_run.payslips.exists():
        raise PayRunError("pay_run_has_no_payslips")
    if actor is None:
        raise SegregationOfDutiesError("pay_run_approver_required")
    _require_separate(pay_run.prepared_by, actor, "pay_run")
    pay_run.status = PayRunStatus.APPROVED
    pay_run.approved_by = actor
    pay_run.approved_at = timezone.now()
    pay_run.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    write_audit(
        action="pay_run.approve",
        entity="pay_run",
        entity_id=pay_run.pk,
        actor=actor,
        after={"period": pay_run.period},
    )
    return pay_run


def _pay_run_journal_lines(pay_run: PayRun) -> list[dict]:
    other_deductions = _q(
        pay_run.total_deductions - pay_run.total_tax - pay_run.total_pension_employee
    )
    lines = [
        {
            "account": _setting("PAYROLL_GL_SALARY_EXPENSE", "500000"),
            "debit": pay_run.total_gross,
            "memo": f"Salaries {pay_run.period}",
        }
    ]
    if pay_run.total_pension_employer:
        lines.append(
            {
                "account": _setting("PAYROLL_GL_EMPLOYER_PENSION", "501000"),
                "debit": pay_run.total_pension_employer,
                "memo": f"Employer pension {pay_run.period}",
            }
        )
    lines.append(
        {
            "account": _setting("PAYROLL_GL_NET_PAY", "210000"),
            "credit": pay_run.total_net,
            "memo": f"Net pay {pay_run.period}",
        }
    )
    if pay_run.total_tax:
        lines.append(
            {
                "account": _setting("PAYROLL_GL_PAYE", "220000"),
                "credit": pay_run.total_tax,
                "memo": f"PAYE {pay_run.period}",
            }
        )
    pension_total = _q(pay_run.total_pension_employee + pay_run.total_pension_employer)
    if pension_total:
        lines.append(
            {
                "account": _setting("PAYROLL_GL_PENSION", "230000"),
                "credit": pension_total,
                "memo": f"Pension {pay_run.period}",
            }
        )
    if other_deductions:
        lines.append(
            {
                "account": _setting("PAYROLL_GL_DEDUCTIONS", "240000"),
                "credit": other_deductions,
                "memo": f"Other deductions {pay_run.period}",
            }
        )
    return lines


@transaction.atomic
def post_pay_run(pay_run: PayRun, *, actor=None) -> PayRun:
    """Post the approved pay run to the GL as one balanced journal."""
    if pay_run.status != PayRunStatus.APPROVED:
        raise PayRunStateError("pay_run_not_approved")
    if pay_run.journal_id:
        raise PayRunStateError("pay_run_already_posted")

    journal = create_journal(
        lines=_pay_run_journal_lines(pay_run),
        date=pay_run.run_date,
        memo=f"Payroll {pay_run.period}",
        source=f"payrun:{pay_run.pk}",
        actor=pay_run.prepared_by,
    )
    post_journal(journal, actor=actor)
    pay_run.status = PayRunStatus.POSTED
    pay_run.posted_at = timezone.now()
    pay_run.journal = journal
    pay_run.save(update_fields=["status", "posted_at", "journal", "updated_at"])
    publish_event(
        "pay_run.posted",
        {"pay_run_id": pay_run.pk, "period": pay_run.period},
    )
    return pay_run


@transaction.atomic
def mark_pay_run_paid(pay_run: PayRun, *, actor=None) -> PayRun:
    if pay_run.status != PayRunStatus.POSTED:
        raise PayRunStateError("pay_run_not_posted")
    pay_run.status = PayRunStatus.PAID
    pay_run.save(update_fields=["status", "updated_at"])
    write_audit(
        action="pay_run.paid",
        entity="pay_run",
        entity_id=pay_run.pk,
        actor=actor,
        after={"period": pay_run.period},
    )
    return pay_run


@transaction.atomic
def void_pay_run(pay_run: PayRun, *, actor=None, reason: str = "") -> PayRun:
    if pay_run.status not in (PayRunStatus.DRAFT, PayRunStatus.APPROVED):
        raise PayRunStateError("pay_run_cannot_be_voided")
    pay_run.status = PayRunStatus.VOID
    pay_run.save(update_fields=["status", "updated_at"])
    write_audit(
        action="pay_run.void",
        entity="pay_run",
        entity_id=pay_run.pk,
        actor=actor,
        after={"reason": reason},
    )
    return pay_run


# ── Provisions ───────────────────────────────────────────────────────────────


@transaction.atomic
def accrue_provision(
    *,
    timesheet: Timesheet,
    daily_rate,
    as_of: date,
    kind: str = "leave",
    actor=None,
) -> Provision:
    """R-FIN-06: accrue worked days × daily rate for an approved timesheet."""
    if timesheet.status != TimesheetStatus.APPROVED:
        raise TimesheetStateError("timesheet_not_approved")
    days = Decimal(timesheet.worked_days)
    rate = _q(daily_rate)
    provision, _ = Provision.objects.update_or_create(
        employee=timesheet.employee,
        kind=kind,
        as_of=as_of,
        defaults={
            "timesheet": timesheet,
            "days": days,
            "rate": rate,
            "amount": _q(days * rate),
            "created_by": actor,
        },
    )
    write_audit(
        action="provision.accrue",
        entity="provision",
        entity_id=provision.pk,
        actor=actor,
        after={"employee": timesheet.employee_id, "amount": str(provision.amount)},
    )
    return provision


# ── Bank payment file ────────────────────────────────────────────────────────


BANK_FILE_COLUMNS = [
    "staff_no",
    "account_name",
    "bank_name",
    "bank_code",
    "account_number",
    "amount",
    "narration",
]


def _csv_text(value) -> str:
    """Neutralise spreadsheet formula injection in free-text bank-file cells."""
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


@transaction.atomic
def generate_bank_file(pay_run: PayRun, *, actor=None) -> PaymentFile:
    """R-FIN-07: CSV bank instruction for the net pay of a posted run."""
    if pay_run.status not in (PayRunStatus.POSTED, PayRunStatus.PAID):
        raise PayRunStateError("pay_run_not_posted")

    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(BANK_FILE_COLUMNS)
    for payslip in pay_run.payslips.select_related("employee").order_by(
        "employee__staff_no"
    ):
        if payslip.net <= 0:
            continue
        employee = payslip.employee
        writer.writerow(
            [
                _csv_text(employee.staff_no),
                _csv_text(employee.account_name or employee.full_name),
                _csv_text(employee.bank_name),
                _csv_text(employee.bank_code),
                _csv_text(employee.bank_account),
                f"{payslip.net:.2f}",
                _csv_text(f"Salary {pay_run.period}"),
            ]
        )
    content = buffer.getvalue()
    filename = f"PAYROLL-{pay_run.period}-BANK.csv"
    payment_file = PaymentFile.objects.create(
        pay_run=pay_run,
        filename=filename,
        content=content,
        status=PaymentFileStatus.GENERATED,
        generated_at=timezone.now(),
        generated_by=actor,
        created_by=actor,
    )
    write_audit(
        action="payment_file.generate",
        entity="payment_file",
        entity_id=payment_file.pk,
        actor=actor,
        after={"pay_run": pay_run.pk, "filename": filename},
    )
    return payment_file


# ── Reporting helpers ────────────────────────────────────────────────────────


def trial_balance(*, as_of: date | None = None) -> list[dict]:
    """Net debit/credit per account for posted journals up to ``as_of``."""
    journals = Journal.objects.filter(status=JournalStatus.POSTED)
    if as_of is not None:
        journals = journals.filter(date__lte=as_of)
    rows = (
        JournalLine.objects.filter(journal__in=journals)
        .values("account__code", "account__name", "account__type")
        .annotate(debit=Sum("debit"), credit=Sum("credit"))
        .order_by("account__code")
    )
    return [
        {
            "code": row["account__code"],
            "name": row["account__name"],
            "type": row["account__type"],
            "debit": _q(row["debit"] or 0),
            "credit": _q(row["credit"] or 0),
            "balance": _q((row["debit"] or 0) - (row["credit"] or 0)),
        }
        for row in rows
    ]
