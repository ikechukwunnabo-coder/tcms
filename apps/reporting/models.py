import uuid

from django.db import models


class ReportDef(models.Model):
    """Report catalogue entry (M12). ``roles`` gates visibility (R-RBAC-01)."""

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    roles = models.ManyToManyField("accounts.Role", blank=True, related_name="report_defs")
    sql_view = models.CharField(max_length=128, blank=True, default="")

    class Meta:
        db_table = "report_def"

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class ReportRun(models.Model):
    """One generated report instance (M12)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report_def = models.ForeignKey(ReportDef, on_delete=models.CASCADE, related_name="runs")
    params = models.JSONField(default=dict, blank=True)
    requested_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    object_key = models.CharField(max_length=512, blank=True, default="")

    class Meta:
        db_table = "report_run"
        ordering = ("-generated_at",)

    def __str__(self) -> str:
        return f"{self.report_def_id}@{self.generated_at:%Y-%m-%d}"
