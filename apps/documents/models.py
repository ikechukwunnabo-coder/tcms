from django.db import models


class Document(models.Model):
    """Generated/stored artefact (certificate, ID card, invoice PDF) — M14."""

    kind = models.CharField(max_length=32)
    owner_type = models.CharField(max_length=64, blank=True, default="")
    owner_id = models.BigIntegerField(null=True, blank=True)
    object_key = models.CharField(max_length=512)
    mime = models.CharField(max_length=128, blank=True, default="")
    size_bytes = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, default="")
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        db_table = "document"

    def __str__(self) -> str:
        return f"{self.kind}:{self.object_key}"
