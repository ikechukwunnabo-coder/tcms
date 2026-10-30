"""Billing — invoice/payment services and API (design ``03`` §8, M10)."""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.billing import services as svc
from apps.billing.exceptions import InvoiceStateError, OverpaymentError
from apps.billing.models import CorporateAccount, Payment
from apps.common.enums import InvoiceStatus, PaymentStatus, RoleCode
from apps.integration.models import OutboxEvent


def make_account(**kwargs):
    defaults = {
        "name": "Acme Offshore",
        "lead_email": "lead@acme.test",
        "terms_days": 30,
        "credit_limit": Decimal("1000.00"),
    }
    defaults.update(kwargs)
    return CorporateAccount.objects.create(**defaults)


def make_invoice(account=None, amount="100.00", **kwargs):
    return svc.create_invoice(
        lines=[{"description": "BOSIET course", "quantity": 1, "unit_price": amount}],
        corporate_account=account,
        issue_date=kwargs.pop("issue_date", date(2026, 3, 2)),
        **kwargs,
    )


class InvoiceServiceTests(TestCase):
    def test_create_invoice_computes_totals_and_number(self):
        account = make_account()
        invoice = make_invoice(account, amount="100.00")
        self.assertEqual(invoice.invoice_no, "INV-2026-000001")
        self.assertEqual(invoice.subtotal, Decimal("100.00"))
        self.assertEqual(invoice.tax, Decimal("0.00"))
        self.assertEqual(invoice.total, Decimal("100.00"))
        self.assertEqual(invoice.status, InvoiceStatus.DRAFT)
        self.assertEqual(invoice.due_date, date(2026, 3, 2) + timedelta(days=30))
        self.assertEqual(invoice.lines.count(), 1)

    def test_invoice_numbers_are_sequential(self):
        first = make_invoice()
        second = make_invoice()
        self.assertEqual(first.invoice_no, "INV-2026-000001")
        self.assertEqual(second.invoice_no, "INV-2026-000002")

    @override_settings(BILLING_TAX_PCT="7.5")
    def test_tax_rate_is_configurable(self):
        invoice = make_invoice(amount="100.00")
        self.assertEqual(invoice.subtotal, Decimal("100.00"))
        self.assertEqual(invoice.tax, Decimal("7.50"))
        self.assertEqual(invoice.total, Decimal("107.50"))

    @override_settings(BILLING_TAX_PCT="0")
    def test_tax_rate_defaults_to_zero(self):
        invoice = make_invoice(amount="100.00")
        self.assertEqual(invoice.tax, Decimal("0.00"))

    def test_issue_sets_status_balance_and_event(self):
        account = make_account()
        invoice = make_invoice(account)
        svc.issue_invoice(invoice)
        invoice.refresh_from_db()
        account.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertEqual(account.balance, Decimal("100.00"))
        self.assertTrue(OutboxEvent.objects.filter(topic="invoice.issued").exists())

    def test_manual_tax_percentage(self):
        invoice = make_invoice(amount="200.00", tax_pct=Decimal("7.50"))
        self.assertEqual(invoice.tax, Decimal("15.00"))
        self.assertEqual(invoice.total, Decimal("215.00"))


class PaymentServiceTests(TestCase):
    def setUp(self):
        self.account = make_account()
        self.invoice = make_invoice(self.account)
        svc.issue_invoice(self.invoice)

    def test_partial_payment_moves_to_part_paid(self):
        svc.record_payment(invoice=self.invoice, amount="40.00", payment_ref="P1")
        self.invoice.refresh_from_db()
        self.account.refresh_from_db()
        self.assertEqual(self.invoice.amount_paid, Decimal("40.00"))
        self.assertEqual(self.invoice.status, InvoiceStatus.PART_PAID)
        self.assertEqual(self.account.balance, Decimal("60.00"))

    def test_full_payment_closes_invoice(self):
        payment = svc.record_payment(invoice=self.invoice, amount="100.00", payment_ref="P2")
        self.invoice.refresh_from_db()
        self.account.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.CONFIRMED)
        self.assertEqual(self.invoice.status, InvoiceStatus.PAID)
        self.assertEqual(self.account.balance, Decimal("0.00"))
        self.assertTrue(OutboxEvent.objects.filter(topic="payment.confirmed").exists())

    def test_overpayment_is_rejected_and_rolled_back(self):
        svc.record_payment(invoice=self.invoice, amount="60.00", payment_ref="P3")
        with self.assertRaises(OverpaymentError):
            svc.record_payment(invoice=self.invoice, amount="50.00", payment_ref="P4")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.amount_paid, Decimal("60.00"))
        self.assertEqual(Payment.objects.count(), 1)

    def test_pending_payment_does_not_apply_until_confirmed(self):
        payment = svc.record_payment(
            invoice=self.invoice, amount="100.00", payment_ref="P5", confirm=False
        )
        self.invoice.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.PENDING)
        self.assertEqual(self.invoice.status, InvoiceStatus.ISSUED)

        svc.confirm_payment(payment)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatus.PAID)

    def test_payment_on_draft_invoice_is_rejected(self):
        draft = make_invoice(self.account, amount="10.00")
        with self.assertRaises(InvoiceStateError):
            svc.record_payment(invoice=draft, amount="10.00", payment_ref="P6")

    def test_void_paid_invoice_is_rejected(self):
        svc.record_payment(invoice=self.invoice, amount="100.00", payment_ref="P7")
        with self.assertRaises(InvoiceStateError):
            svc.void_invoice(self.invoice)


class InvoiceAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("accounts1", password="strongpass123")
        role, _ = Role.objects.get_or_create(
            id=RoleCode.ACCOUNTS, defaults={"code": "accounts", "name": "Accounts"}
        )
        self.user.roles.add(role)
        self.no_role = User.objects.create_user("norole", password="strongpass123")

    def _create(self, **overrides):
        payload = {
            "issue_date": "2026-03-02",
            "currency": "NGN",
            "lines": [
                {"description": "BOSIET course", "quantity": "1", "unit_price": "150.00"}
            ],
        }
        payload.update(overrides)
        return self.client.post("/api/v1/invoices/", payload, format="json")

    def test_accounts_user_can_create_and_list_invoice(self):
        self.client.force_authenticate(self.user)
        response = self._create()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "draft")
        self.assertEqual(response.data["total"], "150.00")
        listing = self.client.get("/api/v1/invoices/")
        self.assertEqual(listing.status_code, 200)

    def test_issue_action_transitions_invoice(self):
        self.client.force_authenticate(self.user)
        invoice_id = self._create().data["id"]
        response = self.client.post(f"/api/v1/invoices/{invoice_id}/issue/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "issued")

    def test_payment_action_marks_invoice_paid(self):
        self.client.force_authenticate(self.user)
        invoice_id = self._create().data["id"]
        self.client.post(f"/api/v1/invoices/{invoice_id}/issue/")
        payment = self.client.post(
            "/api/v1/payments/",
            {"invoice": invoice_id, "amount": "150.00", "payment_ref": "API-1"},
            format="json",
        )
        self.assertEqual(payment.status_code, 201, payment.data)
        self.assertEqual(payment.data["status"], "confirmed")
        invoice = self.client.get(f"/api/v1/invoices/{invoice_id}/")
        self.assertEqual(invoice.data["status"], "paid")

    def test_roleless_user_denied(self):
        self.client.force_authenticate(self.no_role)
        self.assertEqual(self.client.get("/api/v1/invoices/").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/payments/").status_code, 403)
