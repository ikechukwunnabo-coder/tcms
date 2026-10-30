"""Billing domain exceptions — mapped to HTTP codes in ``apps.common.exceptions``."""
from __future__ import annotations


class BillingError(Exception):
    """Base billing error (400)."""


class InvoiceError(BillingError):
    """Invalid invoice content/shape (400)."""


class InvoiceStateError(BillingError):
    """Illegal invoice/payment state transition (409)."""


class PaymentError(BillingError):
    """Invalid payment content (400)."""


class OverpaymentError(BillingError):
    """Payment exceeds the outstanding invoice balance (422)."""


class CorporateCreditError(BillingError):
    """Credit limit / terms violation (422)."""
