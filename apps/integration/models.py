from django.db import models

from apps.common.enums import OutboxStatus


class OutboxEvent(models.Model):
    """Transactional outbox (M16). Handlers are idempotent; at-least-once delivery."""

    topic = models.CharField(max_length=64)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16, choices=OutboxStatus.choices, default=OutboxStatus.PENDING
    )
    attempts = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        db_table = "outbox_event"
        indexes = [models.Index(fields=["status", "created_at"], name="outbox_status_idx")]

    def __str__(self) -> str:
        return f"{self.topic} [{self.status}]"


class WebhookDelivery(models.Model):
    event = models.ForeignKey(OutboxEvent, on_delete=models.CASCADE, related_name="deliveries")
    url = models.CharField(max_length=512)
    status = models.CharField(max_length=16, default="pending")
    attempts = models.IntegerField(default=0)
    last_error = models.TextField(blank=True, default="")

    class Meta:
        db_table = "webhook_delivery"

    def __str__(self) -> str:
        return f"{self.event_id}->{self.url}"


class ExternalRef(models.Model):
    """Maps a TCMS entity to an identifier in an external provider (gateway/SMS)."""

    system = models.CharField(max_length=32)
    entity = models.CharField(max_length=64)
    entity_id = models.BigIntegerField()
    external_id = models.CharField(max_length=255)

    class Meta:
        db_table = "external_ref"
        constraints = [
            models.UniqueConstraint(
                fields=["system", "entity", "external_id"], name="uq_external_ref"
            )
        ]

    def __str__(self) -> str:
        return f"{self.system}:{self.entity}#{self.entity_id}"


class SeedMarker(models.Model):
    """Records which seed tier last provisioned a logical item (M16 / design §8)."""

    tier = models.CharField(max_length=16)
    code = models.CharField(max_length=128)
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "seed_marker"
        constraints = [
            models.UniqueConstraint(fields=["tier", "code"], name="uq_seed_marker")
        ]

    def __str__(self) -> str:
        return f"{self.tier}:{self.code}"
