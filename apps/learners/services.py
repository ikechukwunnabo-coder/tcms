"""Learner domain rules — age gate (gap G6)."""
from __future__ import annotations

from datetime import date

from django.conf import settings


class AgeError(Exception):
    """Raised when a learner fails the minimum-age gate (gap G6)."""


def age_on(birth_date: date, on_date: date | None = None) -> int:
    on_date = on_date or date.today()
    years = on_date.year - birth_date.year
    if (on_date.month, on_date.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def assert_min_age(
    birth_date: date | None, on_date: date | None = None, minimum: int | None = None
) -> bool:
    """Gap G6: learners must be at least ``MIN_LEARNER_AGE`` (default 18)."""
    if birth_date is None:
        raise AgeError("birth_date required for age gate")
    minimum = minimum or getattr(settings, "MIN_LEARNER_AGE", 18)
    if age_on(birth_date, on_date) < minimum:
        raise AgeError(f"learner must be at least {minimum}")
    return True
