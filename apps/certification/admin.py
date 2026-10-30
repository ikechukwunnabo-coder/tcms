from django.contrib import admin

from .models import Certificate, CertificateBatch, CertificateReminder, CertificateSequence, IDCard


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        "certificate_no",
        "learner",
        "format",
        "issued_at",
        "expiry_date",
        "released_at",
        "batch",
        "voided_at",
    )
    list_filter = ("format", "signature_applied", "seal_applied")
    search_fields = ("certificate_no", "learner__badge_no", "learner__surname")


@admin.register(CertificateReminder)
class CertificateReminderAdmin(admin.ModelAdmin):
    list_display = ("certificate", "offset_days", "due_on", "status", "sent_at")
    list_filter = ("status", "offset_days")
    search_fields = ("certificate__certificate_no", "recipient")


@admin.register(CertificateBatch)
class CertificateBatchAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "corporate_account",
        "status",
        "certificate_count",
        "delivered_to",
        "delivered_at",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("corporate_account__lead_email", "delivered_to")


admin.site.register(CertificateSequence)
admin.site.register(IDCard)
