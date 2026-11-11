from django.db import models

from apps.catalogue.models import CertificateType
from apps.common.enums import (
    CertificateBatchStatus,
    CertificateReminderStatus,
    CertificateSource,
)
from apps.common.models import TimeStampedModel
from apps.learners.models import Learner


class CertificateSequence(models.Model):
    """Certificate numbering — mirrors legacy ``tblCertificateNumbers``.

    Number format ``T + YY + seq + YY(birth)`` (design ``03`` §; gap-closure: unique)."""

    course_year = models.SmallIntegerField()
    item_id = models.IntegerField()
    last_number = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "certificate_sequence"
        constraints = [
            models.UniqueConstraint(
                fields=["course_year", "item_id"], name="uq_certificate_sequence"
            )
        ]

    def __str__(self) -> str:
        return f"{self.course_year}/{self.item_id}={self.last_number}"


class Certificate(models.Model):
    training_record = models.ForeignKey(
        "delivery.TrainingRecord", on_delete=models.CASCADE, related_name="certificates"
    )
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="certificates")
    certificate_no = models.CharField(max_length=64, unique=True)
    format = models.ForeignKey(
        CertificateType, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    source = models.CharField(
        max_length=16, choices=CertificateSource.choices, default=CertificateSource.GENERATED
    )
    opito_learner_id = models.CharField(max_length=64, blank=True, default="")
    issued_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    printed_at = models.DateTimeField(null=True, blank=True)
    printed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="r+"
    )
    id_issued_at = models.DateTimeField(null=True, blank=True)
    id_printed_at = models.DateTimeField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    object_key = models.CharField(max_length=512, blank=True, default="")
    md_approved_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="md_approved_certificates",
    )
    md_approved_at = models.DateTimeField(null=True, blank=True)
    signature_applied = models.BooleanField(default=False)
    seal_applied = models.BooleanField(default=False)
    signature_object_key = models.CharField(max_length=512, blank=True, default="")
    seal_object_key = models.CharField(max_length=512, blank=True, default="")
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(blank=True, default="")

    # Portal/certificate-dispatch reconciliation (spec §9.9/§7.14, BR-17/21).
    released_at = models.DateTimeField(
        null=True, blank=True, help_text="Set when the certificate is dispatched (BR-17)."
    )
    renewed_by_certificate = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="renews",
        help_text="The superseding certificate, when this one has been renewed.",
    )
    batch = models.ForeignKey(
        "CertificateBatch",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="certificates",
        help_text="Corporate ZIP batch this certificate ships in (BR-17a).",
    )

    class Meta:
        db_table = "certificate"

    def __str__(self) -> str:
        return self.certificate_no


class CertificateReminder(models.Model):
    """Scheduled certificate-expiry reminder (spec §9.9, BR-21, R-EXP-03).

    One row per ``(certificate, offset_days)`` in the configured offsets
    ``[90, 60, 30, 0]``; delivered by the daily ``run_reminders`` job.
    """

    certificate = models.ForeignKey(
        Certificate, on_delete=models.CASCADE, related_name="reminders"
    )
    offset_days = models.PositiveSmallIntegerField()
    due_on = models.DateField()
    recipient = models.CharField(max_length=255, blank=True, default="")
    channel = models.CharField(max_length=16, default="email")
    status = models.CharField(
        max_length=16,
        choices=CertificateReminderStatus.choices,
        default=CertificateReminderStatus.PENDING,
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "certificate_reminder"
        constraints = [
            models.UniqueConstraint(
                fields=["certificate", "offset_days"], name="uq_certificate_reminder"
            )
        ]
        indexes = [models.Index(fields=["status", "due_on"], name="cert_reminder_due_idx")]

    def __str__(self) -> str:
        return f"reminder:{self.certificate_id}@{self.offset_days}d"


class CertificateBatch(TimeStampedModel):
    """Corporate certificate ZIP delivery (spec §7.15, BR-17a).

    One batch per corporate delivery: released nominee certificates are attached
    on release, assembled into one ZIP, and emailed to the lead.
    """

    corporate_account = models.ForeignKey(
        "billing.CorporateAccount",
        on_delete=models.CASCADE,
        related_name="certificate_batches",
    )
    zip_file_ref = models.CharField(max_length=512, blank=True, default="")
    zip_file_hash = models.CharField(max_length=64, blank=True, default="")
    certificate_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=16,
        choices=CertificateBatchStatus.choices,
        default=CertificateBatchStatus.COLLECTING,
    )
    delivered_to = models.CharField(max_length=254, blank=True, default="")
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "certificate_batch"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"], name="cert_batch_status_idx")]

    def __str__(self) -> str:
        return f"batch:{self.pk} acct={self.corporate_account_id} ({self.status})"


class OpitoFile(TimeStampedModel):
    """Generated OPITO CSV for one course/start-date cohort."""

    course = models.ForeignKey(
        "catalogue.Course", on_delete=models.CASCADE, related_name="opito_files"
    )
    start_date = models.DateField()
    object_key = models.CharField(max_length=512, blank=True, default="")
    record_count = models.PositiveIntegerField(default=0)
    generated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "opito_file"
        constraints = [
            models.UniqueConstraint(
                fields=["course", "start_date"], name="uq_opito_file_cohort"
            )
        ]
        ordering = ["-start_date", "course__name"]

    def __str__(self) -> str:
        return f"opito:{self.course_id}@{self.start_date}"


class IDCard(models.Model):
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="id_cards")
    training_record = models.ForeignKey(
        "delivery.TrainingRecord",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="id_cards",
    )
    card_no = models.CharField(max_length=64, unique=True)
    printed_at = models.DateTimeField(null=True, blank=True)
    printed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    object_key = models.CharField(max_length=512, blank=True, default="")

    class Meta:
        db_table = "id_card"

    def __str__(self) -> str:
        return self.card_no
