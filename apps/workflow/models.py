from django.db import models

from apps.accounts.models import Role


class WorkflowStatus(models.Model):
    """The 14-stage approval chain (design ``02-database.md`` M9, ``03-business-logic.md`` §2).

    ``next_role`` is the role that acts to advance a record out of this status;
    it is NULL for terminal states (12 Completed, 13 Cancelled), for status 11
    (ID Card done → auto-completes) and for status 14 (Rejected → re-enters at
    the rejecting step, gap G7).
    """

    id = models.SmallAutoField(primary_key=True)
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    next_role = models.ForeignKey(
        Role, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    terminal = models.BooleanField(default=False)

    class Meta:
        db_table = "workflow_status"

    def __str__(self) -> str:
        return f"{self.id} {self.name}"


class Approval(models.Model):
    """One actionable step on a training record — the 14-stage funnel (M9).

    ``assigned_role`` mirrors AXIS ``next_role``; ``action`` is approve/reject/cancel."""

    training_record = models.ForeignKey(
        "delivery.TrainingRecord", on_delete=models.CASCADE, related_name="approvals"
    )
    current_status = models.ForeignKey(
        WorkflowStatus, on_delete=models.PROTECT, related_name="approvals"
    )
    step_no = models.IntegerField(default=1)
    assigned_role = models.ForeignKey(
        Role, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    action = models.CharField(max_length=16, blank=True, default="")
    reason = models.TextField(blank=True, default="")
    acted_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    acted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "approval"
        ordering = ("training_record", "step_no")

    def __str__(self) -> str:
        return f"TR#{self.training_record_id} step {self.step_no}: {self.action}"


class ApprovalHistory(models.Model):
    """Status trail for a training record — mirrors AXIS ``tracking[]``."""

    training_record = models.ForeignKey(
        "delivery.TrainingRecord", on_delete=models.CASCADE, related_name="status_history"
    )
    status = models.ForeignKey(WorkflowStatus, on_delete=models.PROTECT, related_name="+")
    full_name = models.CharField(max_length=200, blank=True, default="")
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "approval_history"
        ordering = ("training_record", "updated_at")

    def __str__(self) -> str:
        return f"TR#{self.training_record_id} -> {self.status_id}"


class TransactionLog(models.Model):
    """Field-level change log — mirrors legacy ``empTransactions`` (M15 user-facing)."""

    entity = models.CharField(max_length=64)
    entity_id = models.BigIntegerField()
    field = models.CharField(max_length=64, blank=True, default="")
    old_value = models.TextField(blank=True, default="")
    new_value = models.TextField(blank=True, default="")
    changed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "transaction_log"
        indexes = [models.Index(fields=["entity", "entity_id"], name="txn_entity_idx")]

    def __str__(self) -> str:
        return f"{self.entity}#{self.entity_id}.{self.field}"
