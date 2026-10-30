from django.contrib import admin

from .models import Medical


@admin.register(Medical)
class MedicalAdmin(admin.ModelAdmin):
    list_display = ("id", "learner", "issued_date", "expiry_date", "fitness", "active")
    list_filter = ("fitness", "active")
    search_fields = ("learner__badge_no", "learner__surname", "record_no")
