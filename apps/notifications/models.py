from django.db import models


class NotificationTemplate(models.Model):
    code = models.CharField(max_length=64, unique=True)
    channel = models.CharField(max_length=16, default="email")
    subject = models.CharField(max_length=255, blank=True, default="")
    body = models.TextField(blank=True, default="")

    class Meta:
        db_table = "notification_template"

    def __str__(self) -> str:
        return self.code


class Notification(models.Model):
    template_code = models.CharField(max_length=64)
    recipient = models.CharField(max_length=255)
    channel = models.CharField(max_length=16, default="email")
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, default="queued")
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")

    class Meta:
        db_table = "notification"
        indexes = [models.Index(fields=["status", "template_code"], name="notif_status_idx")]

    def __str__(self) -> str:
        return f"{self.template_code}->{self.recipient}"
