"""Scheduling domain rules — capacity & booking allocation.

Design ``03-business-logic.md`` §6 (R-BK-01..04) and the approved SAD §7–§8
(three-layer capacity, payment-verified seat allocation, auto carry-forward),
reconciled onto the canonical M5 ``enrolment`` model (design ``04`` §5/§6).

Capacity is enforced in three layers (SAD §3): **Layer 1** venue throughput,
**Layer 2** venue non-overlap, and **Layer 3** session seats with ``reserve_pct``
headroom. Layers 1–2 apply only when a session has a venue and are individually
switchable via ``ENFORCE_FACILITY_CAPACITY`` / ``ENFORCE_VENUE_EXCLUSIVITY``.
All checks are application-layer so they hold on SQLite dev/test and Postgres
alike (Postgres EXCLUDE constraints can be added later, guarded).
"""
from __future__ import annotations

import math
import uuid

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from apps.audit.services import write_audit
from apps.common.enums import BookingState, EnrolmentStatus, SessionStatus
from apps.integration.services import publish_event
from apps.scheduling.models import CourseSession, Enrolment

# States in which an enrolment already holds (or has held) a granted seat.
_SETTLED_STATES = (
    BookingState.CONFIRMED,
    BookingState.ATTENDED,
    BookingState.NO_SHOW,
    BookingState.DENIED,
)

# States terminal for further allocation attempts.
_TERMINAL_STATES = (BookingState.CANCELLED,)


class BookingError(Exception):
    """Base class for booking/capacity rule violations."""


class CapacityError(BookingError):
    """No capacity anywhere — the booking must overflow to refund/waitlist."""


class SeatUnavailable(BookingError):
    """Requested session cannot take the booking in its current state."""


# ── Capacity (SAD §3, Layer 3) ───────────────────────────────────────────────


def effective_capacity(session: CourseSession, *, for_carry_forward: bool = False) -> int | None:
    """Commit ceiling for a session, or ``None`` when unlimited.

    New bookings may not consume the ``reserve_pct`` headroom, which is held for
    carry-forward (SAD §12.1); a carry-forward allocation may use the full
    ``capacity``.
    """
    if session.capacity is None:
        return None
    if for_carry_forward:
        return session.capacity
    reserve = max(int(session.reserve_pct or 0), 0)
    return session.capacity - math.ceil(session.capacity * reserve / 100)


def seats_available(session: CourseSession, *, for_carry_forward: bool = False) -> int | None:
    """Remaining committable seats (``None`` when unlimited)."""
    ceiling = effective_capacity(session, for_carry_forward=for_carry_forward)
    if ceiling is None:
        return None
    return max(ceiling - session.seats_taken, 0)


def _session_end(session: CourseSession):
    return session.end_date or session.start_date


def overlapping_venue_sessions(session: CourseSession):
    """Live sessions sharing ``session.venue`` whose dates overlap it."""
    if session.venue_id is None:
        return CourseSession.objects.none()
    start, end = session.start_date, _session_end(session)
    overlap = Q(start_date__lte=end) & (
        Q(end_date__gte=start) | Q(end_date__isnull=True, start_date__gte=start)
    )
    return (
        CourseSession.objects.filter(overlap, venue_id=session.venue_id)
        .exclude(pk=session.pk)
        .exclude(status=SessionStatus.CLOSED)
    )


def facility_capacity_available(session: CourseSession, extra: int = 1) -> bool:
    """SAD §3 Layer 1: venue throughput (seats across concurrent sessions)."""
    if not getattr(settings, "ENFORCE_FACILITY_CAPACITY", True):
        return True
    venue = session.venue
    if venue is None or venue.capacity is None:
        return True
    committed = (
        overlapping_venue_sessions(session).aggregate(total=Sum("seats_taken"))["total"] or 0
    )
    return session.seats_taken + committed + extra <= venue.capacity


def venue_available(session: CourseSession) -> bool:
    """SAD §3 Layer 2: a venue hosts at most one live session at a time."""
    if not getattr(settings, "ENFORCE_VENUE_EXCLUSIVITY", True):
        return True
    if session.venue_id is None:
        return True
    return not overlapping_venue_sessions(session).exists()


def can_confirm(session: CourseSession, extra: int = 1, *, for_carry_forward: bool = False) -> bool:
    """R-BK-01 / SAD §3: can ``extra`` more seats be committed?"""
    if session.status == SessionStatus.CLOSED:
        return False
    ceiling = effective_capacity(session, for_carry_forward=for_carry_forward)
    if ceiling is not None and session.seats_taken + extra > ceiling:
        return False
    if not facility_capacity_available(session, extra=extra):
        return False
    return venue_available(session)


def availability(session: CourseSession) -> dict:
    """Read-model summary for the portal/staff availability endpoint."""
    venue = session.venue
    facility_ok = facility_capacity_available(session) and venue_available(session)
    return {
        "session_id": session.pk,
        "capacity": session.capacity,
        "seats_taken": session.seats_taken,
        "seats_available": seats_available(session),
        "reserve_pct": session.reserve_pct,
        "venue_capacity": venue.capacity if venue is not None else None,
        "facility_available": facility_ok,
        "open": session.status in (SessionStatus.SCHEDULED, SessionStatus.OPEN)
        and (seats_available(session) is None or seats_available(session) > 0)
        and facility_ok,
    }


# ── Booking request (SAD §7 REGISTERED) ──────────────────────────────────────


def _booking_ref(learner_id: int) -> str:
    return f"BK{learner_id:05d}{uuid.uuid4().hex[:8].upper()}"


def book(learner, requested_session: CourseSession, *, created_by=None) -> Enrolment:
    """Create a booking request.

    The training record is only created at allocation (R-BK-02); a seat is not
    secured until payment is verified (SAD §8.2).
    """
    return Enrolment.objects.create(
        learner=learner,
        requested_session=requested_session,
        session=None,
        status=EnrolmentStatus.BOOKED,
        state=BookingState.REGISTERED,
        booking_ref=_booking_ref(learner.pk),
        created_by=created_by,
    )


def submit_payment_proof(enrolment: Enrolment) -> Enrolment:
    """Move REGISTERED / PAYMENT_REJECTED -> PAYMENT_UPLOADED (SAD §9)."""
    if enrolment.state in _SETTLED_STATES or enrolment.state in _TERMINAL_STATES:
        raise SeatUnavailable(f"cannot upload payment in state {enrolment.state}")
    enrolment.state = BookingState.PAYMENT_UPLOADED
    enrolment.save(update_fields=["state"])
    return enrolment


# ── Allocation (SAD §8) ──────────────────────────────────────────────────────


def _next_available_session(enrolment: Enrolment) -> CourseSession | None:
    """Earliest forward session of the same course with reserve headroom.

    Auto-assigned, never pre-emptive, ordered by ``start_date`` (SAD §8.1).
    """
    requested = enrolment.requested_session
    if requested is None:
        return None
    candidates = (
        CourseSession.objects.select_for_update()
        .filter(course_id=requested.course_id, start_date__gte=requested.start_date)
        .exclude(pk=requested.pk)
        .exclude(status=SessionStatus.CLOSED)
        .order_by("start_date", "id")
    )
    for candidate in candidates:
        if can_confirm(candidate, for_carry_forward=True):
            return candidate
    return None


def _secure(
    enrolment: Enrolment, session: CourseSession, *, carry_forward: bool, now, actor=None
) -> Enrolment:
    first_grant = enrolment.original_session_id is None
    enrolment.session = session
    if first_grant:
        enrolment.original_session = enrolment.requested_session
    enrolment.state = BookingState.CONFIRMED
    enrolment.status = EnrolmentStatus.BOOKED
    enrolment.seat_allocated_at = now
    enrolment.payment_verified_at = now
    enrolment.save(
        update_fields=[
            "session",
            "original_session",
            "state",
            "status",
            "seat_allocated_at",
            "payment_verified_at",
        ]
    )
    CourseSession.objects.filter(pk=session.pk).update(seats_taken=F("seats_taken") + 1)
    session.refresh_from_db(fields=["seats_taken"])

    write_audit(
        action="booking.transferred" if carry_forward else "booking.allocated",
        entity="enrolment",
        entity_id=enrolment.pk,
        actor=actor,
        after={"session_id": session.pk, "state": enrolment.state, "carry_forward": carry_forward},
    )
    publish_event(
        "booking.allocated",
        {
            "enrolment_id": enrolment.pk,
            "learner_id": enrolment.learner_id,
            "session_id": session.pk,
            "carry_forward": carry_forward,
        },
    )

    # CJI: (re)issue for the granted session (spec §9.7, BR-20). Delivery never
    # raises, so a missing contact cannot roll back a confirmed seat. Lazy import
    # keeps scheduling decoupled from the portal layer.
    from apps.portal import cji

    cji.regenerate_and_send(enrolment, session)
    return enrolment


@transaction.atomic
def confirm(enrolment: Enrolment, *, verified_by=None, now=None) -> Enrolment:
    """Payment verified -> secure a seat atomically (SAD §8).

    Prefers the requested session; on overflow, auto-carries forward to the
    earliest forward session with headroom; if none, the booking moves to
    ``OVERFLOW`` for refund/waitlist.
    """
    if enrolment.state in _SETTLED_STATES or enrolment.state in _TERMINAL_STATES:
        raise SeatUnavailable(f"enrolment already {enrolment.state}")
    if enrolment.requested_session_id is None:
        raise BookingError("booking has no requested session")

    now = now or timezone.now()
    requested = (
        CourseSession.objects.select_for_update()
        .select_related("course")
        .get(pk=enrolment.requested_session_id)
    )

    if can_confirm(requested):
        return _secure(enrolment, requested, carry_forward=False, now=now, actor=verified_by)

    target = _next_available_session(enrolment)
    if target is None:
        enrolment.state = BookingState.OVERFLOW
        enrolment.status = EnrolmentStatus.WAITLISTED
        enrolment.save(update_fields=["state", "status"])
        write_audit(
            action="booking.overflow",
            entity="enrolment",
            entity_id=enrolment.pk,
            actor=verified_by,
            after={"state": enrolment.state},
        )
        publish_event(
            "booking.overflow",
            {"enrolment_id": enrolment.pk, "learner_id": enrolment.learner_id},
        )
        return enrolment

    return _secure(enrolment, target, carry_forward=True, now=now, actor=verified_by)


def reserve_pct_default() -> int:
    """Configured default reserve headroom (SAD §8.1)."""
    return getattr(settings, "CAPACITY_RESERVE_PCT", 10)
