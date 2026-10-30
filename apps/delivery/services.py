"""Delivery domain rules — expiry, renewal window, reminders (design ``03`` §4).

  R-EXP-01 ending = DATEADD(year, validity, DATEADD(day, -1, starting))
  R-EXP-02 starting = session_start + (duration - 1) days
  R-EXP-03 reminder buckets [90, 60, 30, 0]
  R-REN-01/02 renewal only inside the 90-day window before expiry
  R-REN-03 one day after expiry -> fresh full course (no grace)
"""
from __future__ import annotations

from datetime import date, timedelta

from django.conf import settings


class RenewalWindowError(Exception):
    """Raised when a renewal booking is outside the permitted window (R-REN-02/03)."""


def _add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:  # 29 Feb -> 28 Feb on non-leap target
        return value.replace(year=value.year + years, day=28)


def compute_start_date(session_start: date, duration_days: int | None) -> date | None:
    """R-EXP-02."""
    if session_start is None:
        return None
    return session_start + timedelta(days=max((duration_days or 0) - 1, 0))


def compute_expiry(start_date: date | None, validity_years: int | None) -> date | None:
    """R-EXP-01 / R-CERT-07."""
    if start_date is None or not validity_years:
        return None
    return _add_years(start_date - timedelta(days=1), validity_years)


def days_until(expiry: date, today: date | None = None) -> int:
    return (expiry - (today or date.today())).days


def reminder_bucket(days_to_expiry: int) -> int | str | None:
    """R-EXP-03: map remaining days to a reminder bucket [90, 60, 30, 0]."""
    if days_to_expiry < 0:
        return "expired"
    if days_to_expiry < 30:
        return 30
    if days_to_expiry < 60:
        return 60
    if days_to_expiry < 90:
        return 90
    return None


def is_within_renewal_window(expiry: date, today: date | None = None) -> bool:
    """R-REN-01: 0 <= days remaining <= window."""
    window = getattr(settings, "RENEWAL_WINDOW_DAYS", 90)
    remaining = days_until(expiry, today)
    return 0 <= remaining <= window


def assert_renewal_allowed(prev_expiry: date | None, today: date | None = None) -> bool:
    """R-REN-01/02/03. No-op when there is no previous expiry (first issue)."""
    if prev_expiry is None:
        return True
    remaining = days_until(prev_expiry, today)
    if remaining < 0:
        raise RenewalWindowError("expired_requires_full_course")
    if remaining > getattr(settings, "RENEWAL_WINDOW_DAYS", 90):
        raise RenewalWindowError("renewal_window_not_open")
    return True
