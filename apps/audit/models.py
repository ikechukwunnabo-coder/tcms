from django.db import models


class AuditEvent(models.Model):
    """Append-only audit trail (M15) — mirrors legacy ``empTransactions``.

    No update/delete is expected: this table is the compliance record (design
    ``02-database.md`` §9; gap G4)."""

    actor = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    action = models.CharField(max_length=64)
    entity = models.CharField(max_length=64, blank=True, default="")
    entity_id = models.BigIntegerField(null=True, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_event"
        indexes = [models.Index(fields=["entity", "entity_id"], name="audit_entity_idx")]

    def __str__(self) -> str:
        return f"{self.action} {self.entity}#{self.entity_id}"
