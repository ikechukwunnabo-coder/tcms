"""Medical rules — validity + gating (design ``03`` §5)."""
from __future__ import annotations

from datetime import date

from apps.medicals.models import Medical


class MedicalGateError(Exception):
    """Raised when a valid medical is missing (R-MED-02)."""


def latest_valid_medical(learner, on_date: date | None = None) -> Medical | None:
    on_date = on_date or date.today()
    return (
        Medical.objects.filter(
            learner=learner,
            active=True,
            issued_date__lte=on_date,
            expiry_date__gte=on_date,
        )
        .order_by("-expiry_date")
        .first()
    )


def has_valid_medical(learner, on_date: date | None = None) -> bool:
    return latest_valid_medical(learner, on_date) is not None


def assert_medical_valid(learner, on_date: date | None = None) -> bool:
    """R-MED-02: gates day-1 admission and certificate issuance."""
    if not has_valid_medical(learner, on_date):
        raise MedicalGateError("a valid medical is required (R-MED-02)")
    return True
