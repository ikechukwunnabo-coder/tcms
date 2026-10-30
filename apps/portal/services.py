"""Portal registration & authentication rules (spec BR-15, design ``04`` §5.1).

Flow: ``register`` creates a portal ``User`` (email unverified) + ``PortalAccount``
and emails a single-use token; ``verify_email`` marks the email verified and
creates the M3 ``Learner`` (parity P-02); staff/portal share ``/auth/login``,
which rejects unverified portal accounts.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.audit.services import write_audit
from apps.billing.models import CorporateAccount
from apps.common.enums import BookingState, LearnerType, PortalAccountType
from apps.integration.services import publish_event
from apps.learners.models import Learner
from apps.learners.services import assert_min_age
from apps.portal.models import EmailVerification, PortalAccount


class PortalError(Exception):
    """Base class for portal registration/verification rule violations."""


class EmailTaken(PortalError):
    pass


class WeakPassword(PortalError):
    pass


class InvalidToken(PortalError):
    pass


class TokenExpired(PortalError):
    pass


class RateLimited(PortalError):
    pass


class CorporateError(PortalError):
    """Base class for corporate-account / nominee rule violations (spec BR-16)."""


class CorporateAccountExists(CorporateError):
    pass


class CorporateAccountRequired(CorporateError):
    pass


class DuplicateNominee(CorporateError):
    pass


class NomineeHasConfirmedBooking(CorporateError):
    pass


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _ttl_hours() -> int:
    return int(getattr(settings, "PORTAL_VERIFY_TTL_HOURS", 24))


def check_rate_limit(key: str, *, limit: int, window: int) -> None:
    """Fixed-window limiter backed by the cache (spec: rate-limited endpoints)."""
    added = cache.add(key, 1, window)
    if added:
        return
    try:
        count = cache.incr(key)
    except ValueError:  # window expired between add and incr
        cache.set(key, 1, window)
        return
    if count > limit:
        raise RateLimited("too many requests, try again later")


def _issue_token(user) -> str:
    token = secrets.token_urlsafe(32)
    EmailVerification.objects.create(
        user=user,
        token_hash=_hash(token),
        expires_at=timezone.now() + timedelta(hours=_ttl_hours()),
    )
    return token


def _send_verification_email(user, token: str) -> None:
    base = getattr(settings, "PORTAL_VERIFY_URL", "") or (
        getattr(settings, "PORTAL_BASE_URL", "http://localhost:3000").rstrip("/")
        + "/verify-email"
    )
    link = f"{base}?token={token}"
    send_mail(
        subject="Verify your TASL training portal email",
        message=(
            f"Hello {user.get_full_name() or user.username},\n\n"
            f"Confirm your email address to activate your account:\n{link}\n\n"
            f"This link expires in {_ttl_hours()} hours."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


@transaction.atomic
def register_individual(
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    birth_date,
    sex: str = "",
    username: str | None = None,
) -> PortalAccount:
    """Register an individual learner (spec BR-1/BR-15).

    Enforces the 18+ gate (gap G6) before creating the account; the ``Learner``
    itself is created only on email verification (parity P-02).
    """
    from django.contrib.auth import get_user_model

    email = (email or "").strip().lower()
    assert_min_age(birth_date)  # raises AgeError -> 422 (gap G6)

    User = get_user_model()
    if User.objects.filter(email__iexact=email).exists() or User.objects.filter(
        username__iexact=email
    ).exists():
        raise EmailTaken(f"an account already exists for {email}")

    user = User(
        username=(username or email).strip(),
        email=email,
        first_name=first_name,
        last_name=last_name,
        is_staff=False,
        is_active=True,
        email_verified=False,
    )
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise WeakPassword(" ".join(exc.messages)) from exc
    user.set_password(password)
    user.save()

    account = PortalAccount.objects.create(
        user=user,
        account_type=PortalAccountType.INDIVIDUAL,
        birth_date=birth_date,
        sex=sex or "",
        age_verified=True,
    )
    token = _issue_token(user)
    _send_verification_email(user, token)
    write_audit(action="portal.register", entity="user", entity_id=user.pk, after={"email": email})
    publish_event("learner.registered", {"user_id": user.pk, "email": email})
    return account


def _learner_from_account(account: PortalAccount) -> Learner:
    user = account.user
    badge = f"WEB{user.pk:05d}"
    if Learner.objects.filter(badge_no=badge).exists():
        badge = f"WEB{user.pk:05d}{secrets.token_hex(2).upper()}"
    return Learner.objects.create(
        badge_no=badge,
        surname=(user.last_name or user.username).strip(),
        first_name=(user.first_name or "").strip(),
        sex=account.sex or "",
        birth_date=account.birth_date,
        active=True,
    )


@transaction.atomic
def verification_token_status(token: str) -> str:
    """Check a verification token without consuming it (``valid``/``expired``/``invalid``).

    Used by the portal GET confirmation page so link scanners cannot burn the
    single-use token before the learner clicks the confirmation button.
    """
    ev = (
        EmailVerification.objects.filter(
            token_hash=_hash(token or ""), used_at__isnull=True
        )
        .order_by("-created_at")
        .first()
    )
    if ev is None:
        return "invalid"
    if ev.expires_at < timezone.now():
        return "expired"
    return "valid"


def verify_email(token: str) -> PortalAccount:
    """Consume a verification token: verify the email and create the learner."""
    ev = (
        EmailVerification.objects.select_related("user")
        .filter(token_hash=_hash(token), used_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if ev is None:
        raise InvalidToken("verification token is invalid or already used")
    if ev.expires_at < timezone.now():
        raise TokenExpired("verification token has expired")

    user = ev.user
    now = timezone.now()
    if not user.email_verified:
        user.email_verified = True
        user.email_verified_at = now
        user.save(update_fields=["email_verified", "email_verified_at"])

    account, _ = PortalAccount.objects.get_or_create(user=user)
    if account.learner_id is None:
        account.learner = _learner_from_account(account)
        account.save(update_fields=["learner"])

    ev.used_at = now
    ev.save(update_fields=["used_at"])

    write_audit(
        action="portal.verify_email",
        entity="user",
        entity_id=user.pk,
        after={"email_verified": True, "learner_id": account.learner_id},
    )
    publish_event("learner.verified", {"user_id": user.pk, "learner_id": account.learner_id})
    return account


def resend_verification(email: str) -> None:
    """Re-issue a verification token (rate-limited). No account enumeration."""
    email = (email or "").strip().lower()
    check_rate_limit(
        f"portal:resend:{email}",
        limit=int(getattr(settings, "PORTAL_RESEND_LIMIT", 5)),
        window=int(getattr(settings, "PORTAL_RESEND_WINDOW", 3600)),
    )
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.filter(email__iexact=email, email_verified=False).first()
    if user is not None:
        token = _issue_token(user)
        _send_verification_email(user, token)


# ── Corporate accounts & nominees (spec §9.6, BR-16) ─────────────────────────

# Nominee states that hold (or held) a seat — such nominees may not be deleted.
_HELD_BOOKING_STATES = (
    BookingState.REGISTERED,
    BookingState.PAYMENT_UPLOADED,
    BookingState.PAYMENT_REJECTED,
    BookingState.CONFIRMED,
    BookingState.SESSION_TRANSFERRED,
    BookingState.OVERFLOW,
    BookingState.ATTENDED,
)

# Nominee bio-data fields the lead may set/edit.
_NOMINEE_FIELDS = (
    "surname",
    "first_name",
    "middle_name",
    "sex",
    "birth_date",
    "nationality",
    "state",
    "position",
    "company",
    "title",
)


def get_lead_account(user) -> CorporateAccount:
    """Return the corporate account led by ``user`` or raise (spec BR-16)."""
    account = CorporateAccount.objects.filter(lead_user=user, active=True).first()
    if account is None:
        raise CorporateAccountRequired("no corporate account is linked to this user")
    return account


@transaction.atomic
def create_corporate_account(
    user,
    *,
    name: str,
    company=None,
    terms_days: int = 30,
) -> CorporateAccount:
    """Register a corporate account for an authenticated lead (spec §9.6).

    The lead's single verified email becomes the contact address for every
    nominee (BR-16). Credit limits are set by staff, never by the lead. One
    lead owns at most one account.
    """
    if not user.email or not getattr(user, "email_verified", False):
        raise CorporateError("a verified email address is required to lead an account")
    if CorporateAccount.objects.filter(lead_user=user).exists():
        raise CorporateAccountExists("this user already leads a corporate account")

    account = CorporateAccount.objects.create(
        name=name.strip(),
        lead_user=user,
        lead_email=user.email.strip().lower(),
        company=company,
        credit_limit=None,
        terms_days=terms_days,
    )

    account_row, _ = PortalAccount.objects.get_or_create(user=user)
    account_row.account_type = PortalAccountType.CORPORATE_LEAD
    account_row.corporate_account = account
    account_row.save(update_fields=["account_type", "corporate_account"])

    write_audit(
        action="corporate.account_created",
        entity="corporate_account",
        entity_id=account.pk,
        after={"name": account.name, "lead_email": account.lead_email},
    )
    publish_event(
        "corporate.account_created",
        {"corporate_account_id": account.pk, "lead_user_id": user.pk},
    )
    return account


def _nominee_badge(account: CorporateAccount) -> str:
    seq = account.nominees.count() + 1
    badge = f"CORP{account.pk:04d}{seq:04d}"
    while Learner.objects.filter(badge_no=badge).exists():
        seq += 1
        badge = f"CORP{account.pk:04d}{seq:04d}"
    return badge


def _assert_not_duplicate_nominee(account: CorporateAccount, surname: str, first_name: str,
                                  birth_date) -> None:
    dup = Learner.objects.filter(
        corporate_account=account,
        surname__iexact=surname.strip(),
        first_name__iexact=(first_name or "").strip(),
        birth_date=birth_date,
    ).exists()
    if dup:
        raise DuplicateNominee("a nominee with the same name and date of birth already exists")


@transaction.atomic
def add_nominee(account: CorporateAccount, **bio) -> Learner:
    """Add a nominee learner under a corporate account (spec §9.6, BR-16).

    Nominees are distinct persons (own bio-data/ID/DOB) with no login of their
    own; the 18+ gate still applies (gap G6).
    """
    birth_date = bio.get("birth_date")
    assert_min_age(birth_date)  # raises AgeError -> 422 (gap G6)
    surname = (bio.get("surname") or "").strip()
    _assert_not_duplicate_nominee(account, surname, bio.get("first_name", ""), birth_date)

    fields = {k: bio.get(k) for k in _NOMINEE_FIELDS if k in bio}
    fields["company"] = bio.get("company") or account.company
    learner = Learner.objects.create(
        badge_no=_nominee_badge(account),
        learner_type=LearnerType.CORPORATE,
        corporate_account=account,
        surname=surname,
        first_name=(fields.get("first_name") or "").strip(),
        middle_name=(fields.get("middle_name") or "").strip(),
        sex=fields.get("sex") or "",
        birth_date=birth_date,
        nationality=fields.get("nationality"),
        state=fields.get("state"),
        position=fields.get("position"),
        title=fields.get("title"),
        company=fields["company"],
        active=True,
    )
    write_audit(
        action="corporate.nominee_added",
        entity="learner",
        entity_id=learner.pk,
        after={"corporate_account_id": account.pk, "badge_no": learner.badge_no},
    )
    publish_event(
        "learner.created",
        {"learner_id": learner.pk, "corporate_account_id": account.pk},
    )
    return learner


@transaction.atomic
def update_nominee(learner: Learner, **changes) -> Learner:
    """Edit a nominee's bio-data (spec §9.6)."""
    if learner.corporate_account_id is None:
        raise CorporateError("learner is not a corporate nominee")

    updates = {k: changes[k] for k in _NOMINEE_FIELDS if k in changes}
    if "birth_date" in updates:
        assert_min_age(updates["birth_date"])  # gap G6
        _assert_not_duplicate_nominee(
            learner.corporate_account,
            updates.get("surname", learner.surname),
            updates.get("first_name", learner.first_name),
            updates["birth_date"],
        )
    for field, value in updates.items():
        setattr(learner, field, value)
    learner.save()
    write_audit(
        action="corporate.nominee_updated",
        entity="learner",
        entity_id=learner.pk,
        after={k: str(v) for k, v in updates.items()},
    )
    return learner


@transaction.atomic
def remove_nominee(learner: Learner) -> None:
    """Remove a nominee, unless they hold a booking/seat (spec §9.6, BR-16)."""
    if learner.corporate_account_id is None:
        raise CorporateError("learner is not a corporate nominee")

    from apps.scheduling.models import Enrolment

    if Enrolment.objects.filter(learner=learner, state__in=_HELD_BOOKING_STATES).exists():
        raise NomineeHasConfirmedBooking(
            "nominee has an active booking and cannot be removed; cancel per policy instead"
        )

    learner_id = learner.pk
    account_id = learner.corporate_account_id
    learner.delete()
    write_audit(
        action="corporate.nominee_removed",
        entity="learner",
        entity_id=learner_id,
        after={"corporate_account_id": account_id},
    )
