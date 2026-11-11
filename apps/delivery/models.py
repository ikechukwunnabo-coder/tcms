from django.db import models

from apps.catalogue.models import Course, CourseItem, CourseModule
from apps.common.models import TimeStampedModel
from apps.learners.models import Learner


class TrainingRecord(TimeStampedModel):
    """Delivery record — mirrors legacy ``empTraining``.

    ``instructor`` is the legacy free-text snapshot; ``training_instructor`` (FK)
    is the authoritative link (gap G7). ``status`` drives the 14-stage chain (M9).
    """

    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="training_records")
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="training_records")
    session = models.ForeignKey(
        "scheduling.CourseSession",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="training_records",
    )
    enrolment = models.ForeignKey(
        "scheduling.Enrolment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="training_records",
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True, help_text="Certificate expiry")
    prev_expiry = models.DateField(null=True, blank=True)
    status = models.ForeignKey(
        "workflow.WorkflowStatus", on_delete=models.PROTECT, related_name="training_records"
    )
    reject_reason = models.TextField(blank=True, default="")
    instructor = models.CharField(max_length=150, blank=True, default="")
    foet_scan = models.ForeignKey(
        "documents.Document",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    payment_proof = models.ForeignKey(
        "documents.Document",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    welcome_letter = models.ForeignKey(
        "documents.Document",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        db_table = "training_record"
        indexes = [
            models.Index(fields=["status", "start_date"], name="training_status_start_idx"),
        ]

    def __str__(self) -> str:
        return f"TR#{self.pk} {self.learner_id}/{self.course_id}"


class TrainingItem(models.Model):
    training_record = models.ForeignKey(
        TrainingRecord, on_delete=models.CASCADE, related_name="items"
    )
    course_item = models.ForeignKey(CourseItem, on_delete=models.PROTECT, related_name="+")
    passed = models.BooleanField(null=True, blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = "training_item"
        constraints = [
            models.UniqueConstraint(
                fields=["training_record", "course_item"], name="uq_training_item"
            )
        ]


class TrainingInstructor(models.Model):
    training_record = models.ForeignKey(
        TrainingRecord, on_delete=models.CASCADE, related_name="training_instructors"
    )
    instructor = models.ForeignKey(
        "scheduling.Instructor", on_delete=models.PROTECT, related_name="+"
    )
    module = models.ForeignKey(
        CourseModule, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    training_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "training_instructor"
        constraints = [
            models.UniqueConstraint(
                fields=["training_record", "instructor"], name="uq_training_instructor"
            )
        ]


class DailyMedicalCheck(models.Model):
    """Per-day blood-pressure reading captured during a course."""

    training_record = models.ForeignKey(
        TrainingRecord, on_delete=models.CASCADE, related_name="medical_checks"
    )
    check_date = models.DateField()
    systolic = models.IntegerField(null=True, blank=True)
    diastolic = models.IntegerField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        db_table = "daily_medical_check"
        ordering = ("check_date", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["training_record", "check_date"], name="uq_daily_medical_check"
            )
        ]

    def __str__(self) -> str:
        return f"BP#{self.training_record_id}@{self.check_date}"
