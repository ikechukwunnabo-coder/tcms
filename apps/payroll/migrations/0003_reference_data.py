"""Seed finance/payroll reference data (provisional until M11 discovery ends).

Chart of accounts codes and PAYE bands are configuration, not law, in this
build; the client confirms them during the parallel run. Bands below are the
Nigeria Tax Act 2025 schedule effective 1 January 2026.
"""
from datetime import date
from decimal import Decimal

from django.db import migrations

ACCOUNTS = [
    ("100000", "Bank", "asset"),
    ("210000", "Net Pay Payable", "liability"),
    ("220000", "PAYE Payable", "liability"),
    ("230000", "Pension Payable", "liability"),
    ("240000", "Other Deductions Payable", "liability"),
    ("500000", "Salaries & Wages", "expense"),
    ("501000", "Employer Pension Expense", "expense"),
]

PAY_ELEMENTS = [
    ("BASIC", "Basic salary", "earning", True, True),
    ("HOUSING", "Housing allowance", "earning", True, True),
    ("TRANSPORT", "Transport allowance", "earning", True, True),
    ("LOAN", "Staff loan repayment", "deduction", False, False),
]

TAX_BANDS = [
    ("Nigeria Tax Act 2025 — 0%", Decimal("0"), Decimal("800000"), Decimal("0")),
    ("Nigeria Tax Act 2025 — 15%", Decimal("800000"), Decimal("3000000"), Decimal("15")),
    ("Nigeria Tax Act 2025 — 18%", Decimal("3000000"), Decimal("12000000"), Decimal("18")),
    ("Nigeria Tax Act 2025 — 21%", Decimal("12000000"), Decimal("25000000"), Decimal("21")),
    ("Nigeria Tax Act 2025 — 23%", Decimal("25000000"), Decimal("50000000"), Decimal("23")),
    ("Nigeria Tax Act 2025 — 25%", Decimal("50000000"), None, Decimal("25")),
]
EFFECTIVE_FROM = date(2026, 1, 1)


def seed(apps, schema_editor):
    Account = apps.get_model("payroll", "Account")
    PayElement = apps.get_model("payroll", "PayElement")
    TaxBand = apps.get_model("payroll", "TaxBand")

    for code, name, account_type in ACCOUNTS:
        Account.objects.get_or_create(
            code=code,
            defaults={"name": name, "type": account_type, "active": True},
        )

    for code, name, kind, taxable, pensionable in PAY_ELEMENTS:
        PayElement.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "kind": kind,
                "taxable": taxable,
                "pensionable": pensionable,
                "active": True,
            },
        )

    for name, lower, upper, rate in TAX_BANDS:
        TaxBand.objects.get_or_create(
            name=name,
            effective_from=EFFECTIVE_FROM,
            defaults={"lower": lower, "upper": upper, "rate_pct": rate, "active": True},
        )


def unseed(apps, schema_editor):
    Account = apps.get_model("payroll", "Account")
    PayElement = apps.get_model("payroll", "PayElement")
    TaxBand = apps.get_model("payroll", "TaxBand")

    Account.objects.filter(code__in=[code for code, _, _ in ACCOUNTS]).delete()
    PayElement.objects.filter(code__in=[code for code, *_ in PAY_ELEMENTS]).delete()
    TaxBand.objects.filter(effective_from=EFFECTIVE_FROM).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("payroll", "0002_journalsequence_paymentfile_payslipline_taxband_and_more"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
