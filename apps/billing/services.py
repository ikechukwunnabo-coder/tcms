"""Billing services — invoices, payments, corporate balance (design ``03`` §8).

Rules implemented:
  R-BILL-01  invoice lines drive subtotal; tax applied as a percentage.
  R-BILL-02  corporate clients are invoiced on credit terms (``terms_days``).
  R-BILL-03  payments are recorded against an issued invoice; status derives
             from ``amount_paid`` vs ``total`` (issued/part_paid/paid/void).
  R-BILL-04  a payment may never exceed the outstanding invoice balance.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.audit.services import write_audit
from apps.billing.exceptions import (
    CorporateCreditError,
    InvoiceError,
    InvoiceStateError,
    OverpaymentError,
    PaymentError,
)
from apps.billing.models import (
    CorporateAccount,
    Invoice,
    InvoiceLine,
    InvoiceSequence,
    Payment,
)
from apps.common.enums import InvoiceStatus, PaymentStatus
from apps.integration.services import publish_event

TWO_PLACES = Decimal("0.01")


def _q(value) -> Decimal:
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _tax_pct() -> Decimal:
    return Decimal(str(getattr(settings, "BILLING_TAX_PCT", 0)))


@transaction.atomic
def _next_invoice_no(year: int) -> str:
    seq, _ = InvoiceSequence.objects.select_for_update().get_or_create(year=year)
    seq.last_number += 1
    seq.save(update_fields=["last_number", "updated_at"])
    return f"INV-{year}-{seq.last_number:06d}"


def _next_payment_ref() -> str:
    return f"PAY-{timezone.now():%Y%m%d}-{uuid4().hex[:8].upper()}"


def compute_totals(lines: list[dict], tax_pct: Decimal | None = None):
    """Return ``(subtotal, tax, total)`` for a list of line dicts."""
    subtotal = Decimal("0")
    for line in lines:
        subtotal += _q(line["quantity"]) * _q(line["unit_price"])
    subtotal = _q(subtotal)
    tax = _q(subtotal * (tax_pct if tax_pct is not None else _tax_pct()) / Decimal("100"))
    return subtotal, tax, _q(subtotal + tax)


@transaction.atomic
def create_invoice(
    *,
    lines: list[dict],
    corporate_account: CorporateAccount | None = None,
    enrolment=None,
    learner=None,
    issue_date: date | None = None,
    due_date: date | None = None,
    currency: str = "NGN",
    tax_pct: Decimal | None = None,
    notes: str = "",
    actor=None,
) -> Invoice:
    """Create a draft invoice from line dicts (``description/quantity/unit_price``)."""
    if not lines:
        raise InvoiceError("invoice_requires_lines")
    issue_date = issue_date or date.today()
    if due_date is None and corporate_account is not None:
        due_date = issue_date + timedelta(days=corporate_account.terms_days or 0)

    subtotal, tax, total = compute_totals(lines, tax_pct)
    invoice = Invoice.objects.create(
        invoice_no=_next_invoice_no(issue_date.year),
        corporate_account=corporate_account,
        enrolment=enrolment,
        learner=learner,
        issue_date=issue_date,
        due_date=due_date,
        currency=currency,
        subtotal=subtotal,
        tax=tax,
        total=total,
        status=InvoiceStatus.DRAFT,
        notes=notes,
        created_by=actor,
    )
    for line in lines:
        InvoiceLine.objects.create(
            invoice=invoice,
            description=line["description"],
            quantity=_q(line["quantity"]),
            unit_price=_q(line["unit_price"]),
            amount=_q(_q(line["quantity"]) * _q(line["unit_price"])),
        )
    write_audit(
        action="invoice.create",
        entity="invoice",
        entity_id=invoice.pk,
        actor=actor,
        after={"invoice_no": invoice.invoice_no, "total": str(total)},
    )
    return invoice


@transaction.atomic
def issue_invoice(invoice: Invoice, *, actor=None) -> Invoice:
    """Move a draft invoice to issued and raise the corporate balance."""
    if invoice.status != InvoiceStatus.DRAFT:
        raise InvoiceStateError("invoice_not_draft")
    if not invoice.lines.exists():
        raise InvoiceError("invoice_has_no_lines")

    invoice.status = InvoiceStatus.ISSUED
    invoice.save(update_fields=["status", "updated_at"])
    refresh_corporate_balance(invoice.corporate_account)
    write_audit(
        action="invoice.issue",
        entity="invoice",
        entity_id=invoice.pk,
        actor=actor,
        after={"status": invoice.status},
    )
    publish_event(
        "invoice.issued",
        {"invoice_id": invoice.pk, "invoice_no": invoice.invoice_no, "total": str(invoice.total)},
    )
    return invoice


@transaction.atomic
def void_invoice(invoice: Invoice, *, actor=None, reason: str = "") -> Invoice:
    """Void a draft/issued invoice; paid invoices can never be voided."""
    if invoice.status == InvoiceStatus.PAID:
        raise InvoiceStateError("invoice_already_paid")
    if invoice.status == InvoiceStatus.VOID:
        raise InvoiceStateError("invoice_already_void")
    if invoice.payments.filter(status=PaymentStatus.CONFIRMED).exists():
        raise InvoiceStateError("invoice_has_payments")

    previous = invoice.status
    invoice.status = InvoiceStatus.VOID
    invoice.save(update_fields=["status", "updated_at"])
    refresh_corporate_balance(invoice.corporate_account)
    write_audit(
        action="invoice.void",
        entity="invoice",
        entity_id=invoice.pk,
        actor=actor,
        before={"status": previous},
        after={"status": invoice.status, "reason": reason},
    )
    return invoice


def _apply_payment(invoice: Invoice, actor=None) -> Invoice:
    confirmed = invoice.payments.filter(status=PaymentStatus.CONFIRMED).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0")
    paid = _q(confirmed)
    if paid > invoice.total:
        raise OverpaymentError("payment_exceeds_invoice_total")

    invoice.amount_paid = paid
    if paid <= 0:
        invoice.status = InvoiceStatus.ISSUED
    elif paid < invoice.total:
        invoice.status = InvoiceStatus.PART_PAID
    else:
        invoice.status = InvoiceStatus.PAID
    invoice.save(update_fields=["amount_paid", "status", "updated_at"])
    refresh_corporate_balance(invoice.corporate_account)
    write_audit(
        action="invoice.payment_applied",
        entity="invoice",
        entity_id=invoice.pk,
        actor=actor,
        after={"amount_paid": str(invoice.amount_paid), "status": invoice.status},
    )
    return invoice


@transaction.atomic
def record_payment(
    *,
    invoice: Invoice,
    amount,
    paid_at=None,
    method: str = "",
    payment_ref: str = "",
    received_by=None,
    notes: str = "",
    confirm: bool = True,
) -> Payment:
    """Record a payment receipt; confirmed payments immediately update the invoice."""
    if invoice.status == InvoiceStatus.VOID:
        raise InvoiceStateError("invoice_void")
    if invoice.status == InvoiceStatus.DRAFT:
        raise InvoiceStateError("invoice_not_issued")

    amount = _q(amount)
    if amount <= 0:
        raise PaymentError("amount_must_be_positive")
    if payment_ref and Payment.objects.filter(payment_ref=payment_ref).exists():
        raise PaymentError("duplicate_payment_ref")

    payment = Payment.objects.create(
        invoice=invoice,
        payment_ref=payment_ref or _next_payment_ref(),
        amount=amount,
        paid_at=paid_at or timezone.now(),
        method=method,
        status=PaymentStatus.CONFIRMED if confirm else PaymentStatus.PENDING,
        received_by=received_by,
        notes=notes,
        created_by=received_by,
    )
    if confirm:
        _apply_payment(invoice, actor=received_by)
        publish_event(
            "payment.confirmed",
            {
                "payment_id": payment.pk,
                "invoice_id": invoice.pk,
                "amount": str(payment.amount),
            },
        )
    write_audit(
        action="payment.record",
        entity="payment",
        entity_id=payment.pk,
        actor=received_by,
        after={"amount": str(payment.amount), "status": payment.status},
    )
    return payment


@transaction.atomic
def confirm_payment(payment: Payment, *, actor=None) -> Payment:
    """Confirm a pending payment and recompute the invoice."""
    if payment.status != PaymentStatus.PENDING:
        raise InvoiceStateError("payment_not_pending")
    payment.status = PaymentStatus.CONFIRMED
    payment.save(update_fields=["status", "updated_at"])
    _apply_payment(payment.invoice, actor=actor)
    publish_event(
        "payment.confirmed",
        {
            "payment_id": payment.pk,
            "invoice_id": payment.invoice_id,
            "amount": str(payment.amount),
        },
    )
    return payment


@transaction.atomic
def fail_payment(payment: Payment, *, actor=None, reason: str = "") -> Payment:
    """Mark a pending payment as failed."""
    if payment.status != PaymentStatus.PENDING:
        raise InvoiceStateError("payment_not_pending")
    payment.status = PaymentStatus.FAILED
    payment.notes = (payment.notes + "\n" + reason).strip() if reason else payment.notes
    payment.save(update_fields=["status", "notes", "updated_at"])
    write_audit(
        action="payment.fail",
        entity="payment",
        entity_id=payment.pk,
        actor=actor,
        after={"status": payment.status, "reason": reason},
    )
    return payment


def refresh_corporate_balance(account: CorporateAccount | None) -> Decimal:
    """Recompute outstanding balance across issued/part-paid invoices."""
    if account is None:
        return Decimal("0")
    outstanding = Invoice.objects.filter(
        corporate_account=account,
        status__in=[InvoiceStatus.ISSUED, InvoiceStatus.PART_PAID],
    ).aggregate(total=Sum(F("total") - F("amount_paid")))["total"] or Decimal("0")
    account.balance = _q(outstanding)
    account.save(update_fields=["balance", "updated_at"])
    return account.balance


def assert_within_credit_limit(account: CorporateAccount, additional) -> None:
    """R-BILL-02: guard corporate invoicing against the agreed credit limit."""
    if account is None or account.credit_limit is None:
        return
    projected = _q(account.balance) + _q(additional)
    if projected > _q(account.credit_limit):
        raise CorporateCreditError("credit_limit_exceeded")
