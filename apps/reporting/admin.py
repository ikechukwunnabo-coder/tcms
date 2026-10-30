from django.contrib import admin

from .models import ReportDef, ReportRun


@admin.register(ReportDef)
class ReportDefAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "sql_view")
    filter_horizontal = ("roles",)


@admin.register(ReportRun)
class ReportRunAdmin(admin.ModelAdmin):
    list_display = ("id", "report_def", "requested_by", "generated_at")
    list_filter = ("report_def",)
    readonly_fields = ("id", "generated_at")
