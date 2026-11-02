"""Operational dashboard aggregates and CSV exports.

The dashboard is deliberately role-aware but not role-restricted: every staff
member sees the same centre-wide operating picture, while the work queue is
scoped to the stages their role can act on.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone

from apps.billing.models import Invoice, Payment
from apps.certification.models import Certificate
from apps.common.enums import (
    BookingState,
    InvoiceStatus,
    PaymentStatus,
    RoleCode,
    SessionStatus,
)
from apps.delivery.models import TrainingRecord
from apps.learners.models import Learner
from apps.medicals.models import Medical
from apps.scheduling.models import CourseSession, Enrolment
from apps.workflow.models import WorkflowStatus

_PENDING_STATES = (
    BookingState.REGISTERED,
    BookingState.PAYMENT_UPLOADED,
    BookingState.PAYMENT_REJECTED,
)
_OUTSTANDING_INVOICE_STATES = (InvoiceStatus.ISSUED, InvoiceStatus.PART_PAID)


def _iso(value):
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _money(value) -> str:
    return f"{Decimal(value or 0):.2f}"


def _month_windows(months: int = 6):
    today = timezone.localdate().replace(day=1)
    windows = []
    for offset in range(months - 1, -1, -1):
        year, month = today.year, today.month - offset
        while month <= 0:
            month += 12
            year -= 1
        start = timezone.make_aware(datetime(year, month, 1))
        if month == 12:
            end = timezone.make_aware(datetime(year + 1, 1, 1))
        else:
            end = timezone.make_aware(datetime(year, month + 1, 1))
        windows.append((start, end, f"{year}-{month:02d}"))
    return windows


def _workflow_counts() -> tuple[list[dict], int]:
    counts = dict(TrainingRecord.objects.values_list("status_id").annotate(c=Count("id")))
    rows = [
        {
            "status": status.id,
            "code": status.code,
            "name": status.name,
            "count": counts.get(status.id, 0),
            "terminal": status.terminal,
            "next_role": status.next_role_id,
        }
        for status in WorkflowStatus.objects.order_by("id")
    ]
    return rows, sum(counts.values())


def _my_stages(user) -> list[dict]:
    role_ids = list(user.roles.values_list("id", flat=True))
    statuses = WorkflowStatus.objects.filter(next_role__isnull=False)
    if not getattr(user, "is_superuser", False):
        statuses = statuses.filter(next_role_id__in=role_ids)
    counts = dict(
        TrainingRecord.objects.values_list("status_id").annotate(c=Count("id"))
    )
    return [
        {
            "status": status.id,
            "code": status.code,
            "name": status.name,
            "count": counts.get(status.id, 0),
            "next_role": status.next_role_id,
        }
        for status in statuses.order_by("id")
    ]


def _trend() -> list[dict]:
    rows = []
    for start, end, label in _month_windows(6):
        enrolments = Enrolment.objects.filter(created_at__gte=start, created_at__lt=end).count()
        certificates = Certificate.objects.filter(
            issued_at__gte=start, issued_at__lt=end, voided_at__isnull=True
        ).count()
        revenue = (
            Payment.objects.filter(
                status=PaymentStatus.CONFIRMED, paid_at__gte=start, paid_at__lt=end
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        rows.append(
            {
                "month": label,
                "enrolments": enrolments,
                "certificates": certificates,
                "revenue": _money(revenue),
            }
        )
    return rows


def _course_mix() -> list[dict]:
    rows = (
        CourseSession.objects.values("course_id", "course__course_code", "course__name")
        .annotate(sessions=Count("id"))
        .order_by("-sessions", "course__course_code")[:6]
    )
    mix = []
    for row in rows:
        enrolments = Enrolment.objects.filter(
            requested_session__course_id=row["course_id"]
        ).count()
        mix.append(
            {
                "course_id": row["course_id"],
                "code": row["course__course_code"],
                "name": row["course__name"],
                "sessions": row["sessions"],
                "enrolments": enrolments,
            }
        )
    return mix


def build_dashboard(user) -> dict:
    today = timezone.localdate()
    now = timezone.now()
    horizon_90 = today + timedelta(days=90)
    horizon_30 = today + timedelta(days=30)

    outstanding = Invoice.objects.filter(status__in=_OUTSTANDING_INVOICE_STATES)
    outstanding_total = outstanding.aggregate(
        total=Sum("total"), paid=Sum("amount_paid")
    )
    outstanding_balance = (outstanding_total["total"] or 0) - (outstanding_total["paid"] or 0)

    upcoming = (
        CourseSession.objects.select_related("course", "venue")
        .filter(
            start_date__gte=today,
            status__in=(SessionStatus.SCHEDULED, SessionStatus.OPEN),
        )
        .order_by("start_date", "id")
    )

    pending = (
        Enrolment.objects.select_related("learner", "requested_session__course")
        .filter(state__in=_PENDING_STATES)
        .order_by("-created_at")
    )

    workflow, workflow_total = _workflow_counts()

    return {
        "generated_at": now.isoformat(),
        "as_of": today.isoformat(),
        "kpis": {
            "learners_total": Learner.objects.count(),
            "learners_active": Learner.objects.filter(active=True).count(),
            "sessions_upcoming": upcoming.count(),
            "enrolments_pending": pending.count(),
            "certificates_issued": Certificate.objects.filter(voided_at__isnull=True).count(),
            "certificates_expiring_90d": Certificate.objects.filter(
                voided_at__isnull=True,
                expiry_date__gte=today,
                expiry_date__lte=horizon_90,
            ).count(),
            "invoices_outstanding_count": outstanding.count(),
            "invoices_outstanding_total": _money(outstanding_balance),
            "revenue_collected_90d": _money(
                Payment.objects.filter(
                    status=PaymentStatus.CONFIRMED,
                    paid_at__gte=now - timedelta(days=90),
                ).aggregate(total=Sum("amount"))["total"]
            ),
            "medicals_expiring_30d": Medical.objects.filter(
                active=True, expiry_date__gte=today, expiry_date__lte=horizon_30
            ).count(),
            "workflow_open": workflow_total,
        },
        "workflow": workflow,
        "my_stages": _my_stages(user),
        "trend": _trend(),
        "course_mix": _course_mix(),
        "upcoming_sessions": [
            {
                "id": session.id,
                "course_code": session.course.course_code,
                "course_name": session.course.name,
                "venue": session.venue.name if session.venue else "",
                "start_date": _iso(session.start_date),
                "end_date": _iso(session.end_date),
                "capacity": session.capacity,
                "seats_taken": session.seats_taken,
                "status": session.status,
            }
            for session in upcoming[:6]
        ],
        "work_queue": {
            "pending_enrolments": [
                {
                    "id": row.id,
                    "booking_ref": row.booking_ref,
                    "learner": row.learner.full_name,
                    "badge_no": row.learner.badge_no,
                    "course_code": row.requested_session.course.course_code
                    if row.requested_session_id
                    else "",
                    "start_date": _iso(
                        row.requested_session.start_date if row.requested_session_id else None
                    ),
                    "state": row.state,
                    "created_at": _iso(row.created_at),
                }
                for row in pending[:6]
            ],
            "unpaid_invoices": [
                {
                    "id": row.id,
                    "invoice_no": row.invoice_no,
                    "issue_date": _iso(row.issue_date),
                    "due_date": _iso(row.due_date),
                    "currency": row.currency,
                    "balance": _money((row.total or 0) - (row.amount_paid or 0)),
                    "status": row.status,
                }
                for row in outstanding.order_by("due_date", "id")[:6]
            ],
            "certificates_awaiting_release": [
                {
                    "id": row.id,
                    "certificate_no": row.certificate_no,
                    "learner": row.learner.full_name,
                    "issued_at": _iso(row.issued_at),
                    "expiry_date": _iso(row.expiry_date),
                    "md_approved": row.md_approved_at is not None,
                }
                for row in Certificate.objects.select_related("learner")
                .filter(voided_at__isnull=True, issued_at__isnull=False, released_at__isnull=True)
                .order_by("-issued_at")[:6]
            ],
        },
    }


# ── CSV exports ──────────────────────────────────────────────────────────────

LEARNER_ROLES = (
    RoleCode.SYSTEM_ADMIN,
    RoleCode.ADMIN,
    RoleCode.FRONT_DESK,
    RoleCode.TRAINING_COORDINATOR,
    RoleCode.ACCOUNTS,
    RoleCode.DUE_DILIGENCE,
    RoleCode.PRINTER,
)
CERTIFICATE_ROLES = LEARNER_ROLES
BILLING_ROLES = (RoleCode.SYSTEM_ADMIN, RoleCode.ADMIN, RoleCode.ACCOUNTS)
REPORTING_ROLES = (RoleCode.SYSTEM_ADMIN, RoleCode.MD, RoleCode.REPORTS)
MEDICAL_ROLES = (
    RoleCode.SYSTEM_ADMIN,
    RoleCode.ADMIN,
    RoleCode.FRONT_DESK,
    RoleCode.MEDIC,
)
ANY_STAFF = tuple(int(role) for role in RoleCode)

DATASET_ROLES = {
    "flow": REPORTING_ROLES,
    "learners": LEARNER_ROLES,
    "sessions": ANY_STAFF,
    "enrolments": ANY_STAFF,
    "certificates": CERTIFICATE_ROLES,
    "invoices": BILLING_ROLES,
    "payments": BILLING_ROLES,
    "medicals": MEDICAL_ROLES,
}


def _learner_rows(params) -> tuple[list[str], list[list]]:
    query = Learner.objects.select_related("company", "nationality", "state", "position")
    search = (params.get("q") or "").strip()
    if search:
        query = query.filter(
            Q(badge_no__icontains=search)
            | Q(surname__icontains=search)
            | Q(first_name__icontains=search)
        )
    if params.get("active") in {"true", "false"}:
        query = query.filter(active=params["active"] == "true")
    headers = [
        "badge_no",
        "surname",
        "first_name",
        "middle_name",
        "sex",
        "birth_date",
        "company",
        "nationality",
        "state",
        "position",
        "active",
    ]
    rows = [
        [
            row.badge_no,
            row.surname,
            row.first_name,
            row.middle_name,
            row.sex,
            _iso(row.birth_date),
            row.company.name if row.company else "",
            row.nationality.nationality if row.nationality else "",
            row.state.name if row.state else "",
            row.position.name if row.position else "",
            row.active,
        ]
        for row in query.order_by("surname", "first_name")[:5000]
    ]
    return headers, rows


def _dataset_rows(dataset: str, params) -> tuple[list[str], list[list]]:
    if dataset == "learners":
        return _learner_rows(params)

    if dataset == "flow":
        workflow, _ = _workflow_counts()
        return (
            ["status", "code", "name", "count", "terminal"],
            [
                [row["status"], row["code"], row["name"], row["count"], row["terminal"]]
                for row in workflow
            ],
        )

    if dataset == "sessions":
        rows = CourseSession.objects.select_related("course", "venue").order_by(
            "-start_date"
        )[:5000]
        return (
            [
                "id",
                "course_code",
                "course_name",
                "venue",
                "start_date",
                "end_date",
                "capacity",
                "seats_taken",
                "status",
            ],
            [
                [
                    row.id,
                    row.course.course_code,
                    row.course.name,
                    row.venue.name if row.venue else "",
                    _iso(row.start_date),
                    _iso(row.end_date),
                    row.capacity,
                    row.seats_taken,
                    row.status,
                ]
                for row in rows
            ],
        )

    if dataset == "enrolments":
        rows = Enrolment.objects.select_related(
            "learner", "requested_session__course", "session__course"
        ).order_by("-created_at")[:5000]
        return (
            [
                "booking_ref",
                "badge_no",
                "learner",
                "course",
                "requested_start",
                "granted_start",
                "state",
                "status",
                "created_at",
            ],
            [
                [
                    row.booking_ref or "",
                    row.learner.badge_no,
                    row.learner.full_name,
                    row.requested_session.course.course_code
                    if row.requested_session_id
                    else "",
                    _iso(row.requested_session.start_date if row.requested_session_id else None),
                    _iso(row.session.start_date if row.session_id else None),
                    row.state,
                    row.status,
                    _iso(row.created_at),
                ]
                for row in rows
            ],
        )

    if dataset == "certificates":
        rows = Certificate.objects.select_related("learner", "training_record__course").order_by(
            "-issued_at"
        )[:5000]
        return (
            [
                "certificate_no",
                "learner",
                "badge_no",
                "course_code",
                "issued_at",
                "expiry_date",
                "md_approved_at",
                "released_at",
                "voided_at",
            ],
            [
                [
                    row.certificate_no,
                    row.learner.full_name,
                    row.learner.badge_no,
                    row.training_record.course.course_code if row.training_record_id else "",
                    _iso(row.issued_at),
                    _iso(row.expiry_date),
                    _iso(row.md_approved_at),
                    _iso(row.released_at),
                    _iso(row.voided_at),
                ]
                for row in rows
            ],
        )

    if dataset == "invoices":
        rows = Invoice.objects.select_related("corporate_account", "learner").order_by(
            "-issue_date"
        )[:5000]
        return (
            [
                "invoice_no",
                "account",
                "learner",
                "issue_date",
                "due_date",
                "currency",
                "total",
                "amount_paid",
                "status",
            ],
            [
                [
                    row.invoice_no,
                    row.corporate_account.name if row.corporate_account else "",
                    row.learner.full_name if row.learner else "",
                    _iso(row.issue_date),
                    _iso(row.due_date),
                    row.currency,
                    _money(row.total),
                    _money(row.amount_paid),
                    row.status,
                ]
                for row in rows
            ],
        )

    if dataset == "payments":
        rows = Payment.objects.select_related("invoice").order_by("-paid_at")[:5000]
        return (
            ["payment_ref", "invoice_no", "amount", "paid_at", "method", "status"],
            [
                [
                    row.payment_ref,
                    row.invoice.invoice_no,
                    _money(row.amount),
                    _iso(row.paid_at),
                    row.method,
                    row.status,
                ]
                for row in rows
            ],
        )

    if dataset == "medicals":
        rows = Medical.objects.select_related("learner").order_by("-issued_date")[:5000]
        return (
            [
                "learner",
                "badge_no",
                "record_no",
                "issued_date",
                "expiry_date",
                "fitness",
                "active",
            ],
            [
                [
                    row.learner.full_name,
                    row.learner.badge_no,
                    row.record_no,
                    _iso(row.issued_date),
                    _iso(row.expiry_date),
                    row.fitness,
                    row.active,
                ]
                for row in rows
            ],
        )

    raise ValueError(f"unknown dataset {dataset!r}")


def csv_response(dataset: str, params) -> HttpResponse:
    headers, rows = _dataset_rows(dataset, params)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="tcms-{dataset}-{timezone.localdate().isoformat()}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(
            [_iso(value) if isinstance(value, (date, datetime)) else value for value in row]
        )
    return response


__all__ = [
    "DATASET_ROLES",
    "build_dashboard",
    "csv_response",
]
