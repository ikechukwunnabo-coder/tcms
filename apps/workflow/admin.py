from django.contrib import admin

from .models import Approval, ApprovalHistory, TransactionLog, WorkflowStatus


@admin.register(WorkflowStatus)
class WorkflowStatusAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "next_role", "terminal")
    ordering = ("id",)


class ApprovalHistoryInline(admin.TabularInline):
    model = ApprovalHistory
    extra = 0


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "training_record",
        "step_no",
        "current_status",
        "assigned_role",
        "action",
        "acted_at",
    )
    list_filter = ("action", "current_status", "assigned_role")


@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    list_display = ("id", "entity", "entity_id", "field", "changed_by", "changed_at")
    list_filter = ("entity",)
    search_fields = ("entity", "entity_id")
