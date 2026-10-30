from django.contrib import admin

from apps.billing.models import CorporateAccount, Invoice, InvoiceLine, Payment


@admin.register(CorporateAccount)
class CorporateAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "lead_email", "company", "terms_days", "balance", "active")
    search_fields = ("name", "lead_email")


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_no",
        "corporate_account",
        "learner",
        "issue_date",
        "total",
        "amount_paid",
        "status",
    )
    list_filter = ("status", "issue_date")
    search_fields = ("invoice_no",)
    inlines = [InvoiceLineInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("payment_ref", "invoice", "amount", "paid_at", "status", "method")
    list_filter = ("status",)
    search_fields = ("payment_ref",)
