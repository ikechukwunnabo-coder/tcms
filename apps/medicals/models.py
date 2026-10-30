from django.db import models

from apps.common.enums import Fitness
from apps.learners.models import Learner, LearnerDocument


class Medical(models.Model):
    """Medical fitness record — mirrors legacy ``empMedical`` (medical gating, M8)."""

    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="medicals")
    record_no = models.CharField(max_length=64, blank=True, default="")
    issued_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    systolic = models.IntegerField(null=True, blank=True)
    diastolic = models.IntegerField(null=True, blank=True)
    fitness = models.CharField(max_length=32, choices=Fitness.choices, blank=True, default="")
    active = models.BooleanField(default=True)
    document = models.ForeignKey(
        LearnerDocument, null=True, blank=True, on_delete=models.SET_NULL, related_name="medicals"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        db_table = "medical"
        indexes = [
            models.Index(fields=["learner", "expiry_date"], name="medical_learner_expiry_idx"),
        ]

    def __str__(self) -> str:
        return f"MED#{self.pk} {self.learner_id}"
