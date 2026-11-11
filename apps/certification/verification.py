"""Public certificate verification.

Accepts either a certificate number or an Axis-style training-record id and
returns only the fields needed to confirm that a certificate was issued.
"""
from __future__ import annotations

from datetime import date

from apps.certification.models import Certificate
from apps.certification.services import validity_status


class CertificateVerificationNotFound(LookupError):
    """No certificate matches the supplied public identifier."""


def _find_certificate(identifier: str) -> Certificate:
    value = (identifier or "").strip()
    if not value:
        raise CertificateVerificationNotFound("Certificate not found.")
    queryset = Certificate.objects.select_related(
        "learner", "training_record__course"
    )
    certificate = queryset.filter(certificate_no__iexact=value).first()
    if certificate is not None:
        return certificate
    if value.isdigit():
        certificate = (
            queryset.filter(training_record_id=int(value))
            .order_by("-issued_at", "-id")
            .first()
        )
    if certificate is None:
        raise CertificateVerificationNotFound("Certificate not found.")
    return certificate


def verify_certificate(identifier: str, *, today: date | None = None) -> dict:
    certificate = _find_certificate(identifier)
    today = today or date.today()
    if certificate.voided_at is not None:
        status = "void"
    elif certificate.issued_at is None:
        status = "not_issued"
    else:
        status = validity_status(certificate, today)
    return {
        "is_valid": status in {"valid", "expiring_soon"},
        "status": status,
        "certificate_no": certificate.certificate_no,
        "full_name": certificate.learner.full_name,
        "course": certificate.training_record.course.name,
        "issued": certificate.issued_at.date().isoformat()
        if certificate.issued_at
        else None,
        "expiry": certificate.expiry_date.isoformat()
        if certificate.expiry_date
        else None,
    }
