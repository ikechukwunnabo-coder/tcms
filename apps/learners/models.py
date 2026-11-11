from django.db import models

from apps.common.enums import DocumentKind, LearnerType, Sex
from apps.common.models import TimeStampedModel
from apps.reference.models import Company, ContactType, Nationality, Position, State, Title


class Learner(TimeStampedModel):
    """Personnel / delegate — mirrors legacy ``tblPersonnel`` (``badgeno`` preserved)."""

    badge_no = models.CharField(max_length=32, unique=True)
    surname = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100, blank=True, default="")
    middle_name = models.CharField(max_length=100, blank=True, default="")
    sex = models.CharField(max_length=1, choices=Sex.choices, blank=True, default="")
    birth_date = models.DateField(null=True, blank=True)

    nationality = models.ForeignKey(
        Nationality, null=True, blank=True, on_delete=models.SET_NULL, related_name="learners"
    )
    state = models.ForeignKey(
        State, null=True, blank=True, on_delete=models.SET_NULL, related_name="learners"
    )
    position = models.ForeignKey(
        Position, null=True, blank=True, on_delete=models.SET_NULL, related_name="learners"
    )
    company = models.ForeignKey(
        Company, null=True, blank=True, on_delete=models.SET_NULL, related_name="learners"
    )
    title = models.ForeignKey(
        Title, null=True, blank=True, on_delete=models.SET_NULL, related_name="learners"
    )

    active = models.BooleanField(default=True)
    pertype = models.CharField(max_length=8, default="TRN")
    vantage_id = models.CharField(max_length=64, blank=True, default="")

    # Portal/corporate reconciliation (spec BR-16): nominees are Learner rows
    # under a corporate account, with no login of their own.
    learner_type = models.CharField(
        max_length=16, choices=LearnerType.choices, default=LearnerType.INDIVIDUAL
    )
    corporate_account = models.ForeignKey(
        "billing.CorporateAccount",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="nominees",
    )

    class Meta:
        db_table = "learner"
        indexes = [
            models.Index(fields=["surname", "first_name", "badge_no"], name="learner_name_fts"),
        ]

    def __str__(self) -> str:
        return f"{self.badge_no} {self.surname} {self.first_name}".strip()

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.surname, self.first_name, self.middle_name) if p)


class LearnerContact(models.Model):
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="contacts")
    contact_type = models.ForeignKey(
        ContactType, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    value = models.CharField(max_length=255)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "learner_contact"

    def __str__(self) -> str:
        return f"{self.learner_id}:{self.value}"


class LearnerDocument(models.Model):
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=32, choices=DocumentKind.choices)
    object_key = models.CharField(max_length=512)
    mime = models.CharField(max_length=128, blank=True, default="")
    size_bytes = models.BigIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "learner_document"

    def __str__(self) -> str:
        return f"{self.learner_id}:{self.kind}"
