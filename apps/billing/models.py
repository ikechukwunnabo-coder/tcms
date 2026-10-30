"""Billing models — M10.

Reconciliation with the portal spec (design ``04`` §5.2, spec §9.6): the portal
``CorporateAccount`` (lead registers once with the company's single verified
email; owns many nominee learners) is unified with the canonical M10
``corporate_account`` table (company/credit-limit/terms/balance, used by
invoices & payments). One row serves both roles: ``lead_user`` +
``lead_email`` are the portal side, ``company`` + the credit fields are the
billing side.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.enums import InvoiceStatus, PaymentStatus
from apps.common.models import TimeStampedModel


class CorporateAccount(TimeStampedModel):
    """Corporate / agency training account (portal lead + billing terms)."""

    name = models.CharField(max_length=200)
    company = models.ForeignKey(
        "reference.Company",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="corporate_accounts",
    )

    # Portal side (spec BR-16): one verified lead email owns N nominees.
    lead_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="corporate_account",
    )
    lead_email = models.EmailField()

    # Billing side (canonical M10).
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    terms_days = models.IntegerField(default=30)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    active = models.BooleanField(default=True)

    class Meta:
        db_table = "corporate_account"

    def __str__(self) -> str:
        return self.name


class InvoiceSequence(models.Model):
    """Invoice numbering — ``INV-<year>-<seq>`` (design ``02`` M10)."""

    year = models.SmallIntegerField(unique=True)
    last_number = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "invoice_sequence"

    def __str__(self) -> str:
        return f"{self.year}={self.last_number}"


class Invoice(TimeStampedModel):
    invoice_no = models.CharField(max_length=32, unique=True)
    corporate_account = models.ForeignKey(
        CorporateAccount,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoices",
    )
    enrolment = models.ForeignKey(
        "scheduling.Enrolment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoices",
    )
    learner = models.ForeignKey(
        "learners.Learner",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoices",
    )
    issue_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="NGN")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(
        max_length=16, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "invoice"
        indexes = [
            models.Index(fields=["corporate_account", "status"]),
            models.Index(fields=["issue_date"]),
        ]

    def __str__(self) -> str:
        return self.invoice_no


class InvoiceLine(TimeStampedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = "invoice_line"


class Payment(TimeStampedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    payment_ref = models.CharField(max_length=64, unique=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    paid_at = models.DateTimeField()
    method = models.CharField(max_length=32, blank=True)
    status = models.CharField(
        max_length=16, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "payment"
        indexes = [
            models.Index(fields=["invoice", "status"]),
        ]

    def __str__(self) -> str:
        return self.payment_ref
