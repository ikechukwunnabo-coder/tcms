"""Portal identity & registration models.

Reconciled onto the canonical model (design ``04`` §5.1, parity P-02): a portal
``User`` (auth principal) is linked 1:1 to the M3 ``Learner`` created on email
verification. Corporate leads are Users; nominees are Learner rows with no login
of their own (spec §9.6) — that linkage arrives in the corporate slice.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.enums import CJIDeliveryStatus, PortalAccountType, Sex
from apps.learners.models import Learner


class PortalAccount(models.Model):
    """Portal-side state for an authenticating user.

    Pending profile (``birth_date``/``sex``) is held here until email
    verification materialises the ``Learner`` (parity P-02).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portal_account",
    )
    learner = models.OneToOneField(
        Learner,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="portal_account",
    )
    account_type = models.CharField(
        max_length=24,
        choices=PortalAccountType.choices,
        default=PortalAccountType.INDIVIDUAL,
    )
    birth_date = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=1, choices=Sex.choices, blank=True, default="")
    age_verified = models.BooleanField(default=False)
    corporate_account = models.ForeignKey(
        "billing.CorporateAccount",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_accounts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "portal_account"

    def __str__(self) -> str:
        return f"portal:{self.user_id}"


class EmailVerification(models.Model):
    """Single-use, time-limited email-verification token (spec BR-15).

    Only the SHA-256 hash of the token is stored.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_verifications",
    )
    token_hash = models.CharField(max_length=64, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_verification"
        indexes = [models.Index(fields=["user", "created_at"], name="emailverify_user_idx")]

    def __str__(self) -> str:
        return f"verify:{self.user_id}"


class JoiningInstruction(models.Model):
    """Course Joining Instructions (CJI) — spec §9.7, BR-20.

    Rendered for the *granted* session of a confirmed booking; regenerated (new
    ``version``, previous row ``superseded``) whenever the granted session changes
    (carry-forward/transfer, SAD §9.3). Exactly one ``is_current`` row per booking.
    """

    enrolment = models.ForeignKey(
        "scheduling.Enrolment",
        on_delete=models.CASCADE,
        related_name="joining_instructions",
    )
    session = models.ForeignKey(
        "scheduling.CourseSession",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="joining_instructions",
    )
    version = models.PositiveIntegerField(default=1)
    is_current = models.BooleanField(default=True)
    delivery_status = models.CharField(
        max_length=16, choices=CJIDeliveryStatus.choices, default=CJIDeliveryStatus.PENDING
    )
    payload = models.TextField(blank=True, default="")
    merge_data = models.JSONField(default=dict, blank=True)
    sent_to = models.EmailField(blank=True, default="")
    sent_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "joining_instruction"
        indexes = [
            models.Index(fields=["enrolment", "is_current"], name="cji_current_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["enrolment"],
                condition=Q(is_current=True),
                name="uq_cji_current_per_enrolment",
            )
        ]

    def __str__(self) -> str:
        return f"cji:{self.enrolment_id}v{self.version}"
