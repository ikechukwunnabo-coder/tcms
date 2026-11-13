"""Operational dashboard aggregates and CSV exports.

The dashboard is deliberately role-aware but not role-restricted: every staff
member sees the same centre-wide operating picture, while the work queue is
scoped to the stages their role can act on.
"""
from __future__ import annotations

import calendar
import csv
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO

from django.db.models import Count, Max, Min, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.utils import timezone

from apps.accounts.models import Role
from apps.billing.models import Invoice, Payment
from apps.certification.models import Certificate
from apps.common.enums import (
    BookingState,
    CertificateTypeCode,
    InvoiceStatus,
    PaymentStatus,
    RoleCode,
    SessionStatus,
)
from apps.delivery.models import TrainingRecord
from apps.learners.models import Learner
from apps.medicals.models import Medical
from apps.scheduling.models import CourseSession, Enrolment
from apps.workflow.models import Approval, WorkflowStatus

_PENDING_STATES = (
    BookingState.REGISTERED,
    BookingState.PAYMENT_UPLOADED,
    BookingState.PAYMENT_REJECTED,
)
_OUTSTANDING_INVOICE_STATES = (InvoiceStatus.ISSUED, InvoiceStatus.PART_PAID)
_MONTHS = [calendar.month_abbr[month] for month in range(1, 13)]
_WORKFLOW_BACKLOG = 15
_WORKFLOW_CRITICAL = 25
_WORKFLOW_ACTIONS = ("approve", "reject", "cancel")


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


def _trend(include_revenue: bool = True) -> list[dict]:
    rows = []
    for start, end, label in _month_windows(6):
        enrolments = Enrolment.objects.filter(created_at__gte=start, created_at__lt=end).count()
        certificates = Certificate.objects.filter(
            issued_at__gte=start, issued_at__lt=end, voided_at__isnull=True
        ).count()
        revenue = 0
        if include_revenue:
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

    role_ids = set(user.roles.values_list("id", flat=True))
    finance_visible = getattr(user, "is_superuser", False) or not (
        role_ids and role_ids <= {RoleCode.HR_MANAGER, RoleCode.HR_OFFICER}
    )

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
            "invoices_outstanding_count": (
                outstanding.count() if finance_visible else 0
            ),
            "invoices_outstanding_total": (
                _money(outstanding_balance) if finance_visible else "0.00"
            ),
            "revenue_collected_90d": (
                _money(
                    Payment.objects.filter(
                        status=PaymentStatus.CONFIRMED,
                        paid_at__gte=now - timedelta(days=90),
                    ).aggregate(total=Sum("amount"))["total"]
                )
                if finance_visible
                else "0.00"
            ),
            "medicals_expiring_30d": Medical.objects.filter(
                active=True, expiry_date__gte=today, expiry_date__lte=horizon_30
            ).count(),
            "workflow_open": workflow_total,
        },
        "workflow": workflow,
        "my_stages": _my_stages(user),
        "trend": _trend(include_revenue=finance_visible),
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
            "unpaid_invoices": (
                [
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
                ]
                if finance_visible
                else []
            ),
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

def _year(value, fallback=None):
    if value in (None, ""):
        return timezone.localdate().year if fallback is None else fallback
    year = int(value)
    if year < 1900 or year > 2200:
        raise ValueError("year must be between 1900 and 2200")
    return year


def _date(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def report_year_range():
    bounds = TrainingRecord.objects.filter(start_date__isnull=False).aggregate(
        earliest=Min("start_date"), latest=Max("start_date")
    )
    if bounds["earliest"] is None:
        bounds = CourseSession.objects.filter(start_date__isnull=False).aggregate(
            earliest=Min("start_date"), latest=Max("start_date")
        )
    today = timezone.localdate()
    earliest = bounds["earliest"] or today
    latest = bounds["latest"] or today
    return {
        "min": min(earliest.year, latest.year),
        "max": max(earliest.year, latest.year),
        "default": latest.year,
    }


def _latest_certificate(record):
    certificates = list(record.certificates.all())
    certificates.sort(key=lambda cert: cert.issued_at or timezone.now(), reverse=True)
    return next((cert for cert in certificates if cert.voided_at is None), None)


def _training_record_queryset(params):
    queryset = TrainingRecord.objects.select_related(
        "learner", "course", "course__cert_type"
    ).prefetch_related("certificates")
    course = params.get("course")
    if course not in (None, ""):
        queryset = queryset.filter(course_id=int(course))
    company = params.get("company")
    if company not in (None, ""):
        queryset = queryset.filter(learner__company_id=int(company))
    start = _date(params.get("from"))
    end = _date(params.get("to"))
    if start:
        queryset = queryset.filter(start_date__gte=start)
    if end:
        queryset = queryset.filter(start_date__lte=end)
    year = params.get("year")
    if year not in (None, ""):
        queryset = queryset.filter(start_date__year=_year(year))
    search = str(params.get("q") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(learner__surname__icontains=search)
            | Q(learner__first_name__icontains=search)
            | Q(learner__badge_no__icontains=search)
        )
    return queryset.order_by("-start_date", "-id")


def training_record_rows(params):
    today = timezone.localdate()
    rows = []
    for index, record in enumerate(_training_record_queryset(params)[:5000], start=1):
        certificate = _latest_certificate(record)
        expiry = certificate.expiry_date if certificate else record.end_date
        days = (expiry - today).days if expiry else ""
        rows.append(
            {
                "row_num": index,
                "id": record.id,
                "first_name": record.learner.first_name,
                "last_name": record.learner.surname,
                "badge_no": record.learner.badge_no,
                "birth_date": _iso(record.learner.birth_date),
                "company": str(record.learner.company or ""),
                "course": record.course.name,
                "course_code": record.course.course_code,
                "start": _iso(record.start_date),
                "end": _iso(record.end_date),
                "expiry": _iso(expiry),
                "days": days,
                "certificate": certificate.certificate_no if certificate else "",
            }
        )
    return rows


def course_month_rows(year):
    records = (
        TrainingRecord.objects.filter(start_date__year=year, start_date__isnull=False)
        .annotate(month=TruncMonth("start_date"))
        .values("course_id", "course__course_code", "course__name", "month")
        .annotate(value=Count("id"))
        .order_by("course__name", "month")
    )
    rows = []
    for record in records:
        month = record["month"]
        rows.append(
            {
                "c": record["course_id"],
                "course": record["course__name"],
                "course_code": record["course__course_code"],
                "month": _MONTHS[month.month - 1],
                "month_no": month.month,
                "value": record["value"],
            }
        )
    return rows


def delegate_month_rows(year):
    values = {
        record["month"].month: record["value"]
        for record in (
            TrainingRecord.objects.filter(
                start_date__year=year, start_date__isnull=False
            )
            .annotate(month=TruncMonth("start_date"))
            .values("month")
            .annotate(value=Count("learner", distinct=True))
        )
    }
    return [
        {"month": _MONTHS[month - 1], "month_no": month, "value": values.get(month, 0)}
        for month in range(1, 13)
    ]


def course_type_rows(year):
    records = (
        TrainingRecord.objects.filter(start_date__year=year)
        .values("course__cert_type__name", "course__name")
        .annotate(count=Count("id"))
        .order_by("course__cert_type__name", "course__name")
    )
    return [
        {
            "type": record["course__cert_type__name"] or "Unclassified",
            "course": record["course__name"],
            "count": record["count"],
        }
        for record in records
    ]


def top_course_rows(year, limit=10):
    rows = course_month_rows(year)
    totals = {}
    for row in rows:
        totals[row["c"]] = totals.get(row["c"], 0) + row["value"]
    top_ids = {
        course_id
        for course_id, _ in sorted(
            totals.items(), key=lambda item: (-item[1], item[0])
        )[:limit]
    }
    rows = [row for row in rows if row["c"] in top_ids]
    for row in rows:
        row["course_total"] = totals[row["c"]]
    return rows


def flow_status_payload():
    counts = dict(
        TrainingRecord.objects.values_list("status_id")
        .annotate(count=Count("id"))
        .order_by()
    )
    statuses = list(WorkflowStatus.objects.select_related("next_role").order_by("id"))
    data = []
    next_roles = {}
    for status in statuses:
        count = counts.get(status.id, 0)
        if status.terminal:
            level = "terminal"
        elif count >= _WORKFLOW_CRITICAL:
            level = "critical"
        elif count >= _WORKFLOW_BACKLOG:
            level = "backlog"
        else:
            level = "normal"
        data.append(
            {
                "id": status.id,
                "status": status.name,
                "code": status.code,
                "name": status.name,
                "count": count,
                "terminal": status.terminal,
                "level": level,
                "next_role": status.next_role_id,
                "next_role_name": status.next_role.name if status.next_role else "",
            }
        )
        if not status.terminal and status.next_role_id:
            bucket = next_roles.setdefault(
                status.next_role_id,
                {
                    "role": status.next_role_id,
                    "name": status.next_role.name,
                    "count": 0,
                    "stages": [],
                },
            )
            bucket["count"] += count
            bucket["stages"].append(status.name)
    active = [row for row in data if not row["terminal"]]
    terminal = [row for row in data if row["terminal"]]
    return {
        "data": data,
        "total": sum(row["count"] for row in data),
        "summary": {
            "active_records": sum(row["count"] for row in active),
            "terminal_records": sum(row["count"] for row in terminal),
            "backlog_records": sum(
                row["count"] for row in active if row["level"] == "backlog"
            ),
            "critical_records": sum(
                row["count"] for row in active if row["level"] == "critical"
            ),
            "backlog_stages": sum(
                1 for row in active if row["level"] == "backlog"
            ),
            "critical_stages": sum(
                1 for row in active if row["level"] == "critical"
            ),
        },
        "thresholds": {"backlog": _WORKFLOW_BACKLOG, "critical": _WORKFLOW_CRITICAL},
        "next_roles": sorted(
            next_roles.values(), key=lambda item: (-item["count"], item["name"])
        ),
    }


def _role_activity_queryset(role_id=None, start=None, end=None):
    queryset = Approval.objects.select_related(
        "training_record__learner",
        "training_record__course",
        "acted_by",
        "current_status",
    ).filter(action__in=_WORKFLOW_ACTIONS, acted_at__isnull=False)
    if role_id:
        queryset = queryset.filter(acted_by__roles__id=role_id)
    if start:
        queryset = queryset.filter(acted_at__date__gte=start)
    if end:
        queryset = queryset.filter(acted_at__date__lte=end)
    return queryset.distinct().order_by("-acted_at", "-id")


def role_activity_rows(role_id=None, start=None, end=None):
    rows = []
    for approval in _role_activity_queryset(role_id, start, end)[:5000]:
        learner = approval.training_record.learner
        actor = approval.acted_by
        actor_name = ""
        if actor:
            actor_name = actor.get_full_name().strip() or actor.username
        rows.append(
            {
                "id": approval.id,
                "user_id": approval.acted_by_id,
                "user": actor_name,
                "training_record": approval.training_record_id,
                "badge_no": learner.badge_no,
                "learner": learner.full_name,
                "course": approval.training_record.course.name,
                "step": approval.current_status.name,
                "action": approval.action,
                "completed": _iso(approval.acted_at),
            }
        )
    return rows


def role_activity_summary(role_id=None, start=None, end=None):
    summaries = (
        _role_activity_queryset(role_id, start, end)
        .values(
            "acted_by_id",
            "acted_by__username",
            "acted_by__first_name",
            "acted_by__last_name",
        )
        .annotate(count=Count("id", distinct=True))
        .order_by("-count", "acted_by__username")
    )
    return [
        {
            "user_id": row["acted_by_id"],
            "username": row["acted_by__username"],
            "name": (
                f"{row['acted_by__first_name']} {row['acted_by__last_name']}".strip()
                or row["acted_by__username"]
            ),
            "count": row["count"],
        }
        for row in summaries
    ]


def role_activity_roles():
    return [
        {"id": role.id, "code": role.code, "name": role.name}
        for role in Role.objects.order_by("name", "id")
    ]


def role_activity_earliest_date():
    earliest = Approval.objects.filter(
        action__in=_WORKFLOW_ACTIONS, acted_at__isnull=False
    ).aggregate(earliest=Min("acted_at"))["earliest"]
    return earliest.date().isoformat() if earliest else None


def opito_monthly_rows(start=None, end=None):
    queryset = TrainingRecord.objects.select_related(
        "learner", "course"
    ).prefetch_related("certificates").filter(
        Q(course__cert_type_id=CertificateTypeCode.OPITO)
        | ~Q(course__opito_reg_code="")
    )
    if start:
        queryset = queryset.filter(start_date__gte=start)
    if end:
        queryset = queryset.filter(start_date__lte=end)
    rows = []
    for record in queryset.order_by("course__name", "start_date", "id"):
        certificate = _latest_certificate(record)
        learner = record.learner
        opito_id = ""
        if certificate and certificate.opito_learner_id:
            opito_id = certificate.opito_learner_id
        elif learner.vantage_id:
            opito_id = learner.vantage_id
        else:
            opito_id = learner.badge_no
        rows.append(
            {
                "id": record.id,
                "course": record.course.name,
                "course_code": record.course.course_code,
                "opito_reg_code": record.course.opito_reg_code,
                "learner": learner.full_name,
                "badge_no": learner.badge_no,
                "opito_learner_id": opito_id,
                "start": _iso(record.start_date),
                "end": _iso(record.end_date),
                "completed": _iso(record.start_date),
            }
        )
    return rows


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
    "training-records": REPORTING_ROLES,
    "course-by-month": REPORTING_ROLES,
    "delegates-by-month": REPORTING_ROLES,
    "courses-treemap": REPORTING_ROLES,
    "top-courses": REPORTING_ROLES,
    "role-activity": REPORTING_ROLES,
    "opito-monthly": REPORTING_ROLES,
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
    if dataset == "training-records":
        rows = training_record_rows(params)
        return (
            [
                "#",
                "first_name",
                "last_name",
                "birth_date",
                "company",
                "course",
                "start",
                "end",
                "expiry",
                "days",
                "certificate",
            ],
            [
                [
                    row["row_num"],
                    row["first_name"],
                    row["last_name"],
                    row["birth_date"],
                    row["company"],
                    row["course"],
                    row["start"],
                    row["end"],
                    row["expiry"],
                    row["days"],
                    row["certificate"],
                ]
                for row in rows
            ],
        )

    if dataset == "course-by-month":
        rows = course_month_rows(_year(params.get("year")))
        return (
            ["course_code", "course", "month", "value"],
            [
                [row["course_code"], row["course"], row["month"], row["value"]]
                for row in rows
            ],
        )

    if dataset == "delegates-by-month":
        rows = delegate_month_rows(_year(params.get("year")))
        return (
            ["month", "value"],
            [[row["month"], row["value"]] for row in rows],
        )

    if dataset == "courses-treemap":
        rows = course_type_rows(_year(params.get("year")))
        return (
            ["type", "course", "count"],
            [[row["type"], row["course"], row["count"]] for row in rows],
        )

    if dataset == "top-courses":
        rows = top_course_rows(_year(params.get("year")))
        return (
            ["course_code", "course", "month", "value"],
            [
                [row["course_code"], row["course"], row["month"], row["value"]]
                for row in rows
            ],
        )

    if dataset == "role-activity":
        role = params.get("role")
        rows = role_activity_rows(
            int(role) if role not in (None, "") else None,
            _date(params.get("from")),
            _date(params.get("to")),
        )
        return (
            [
                "user",
                "training_record",
                "badge_no",
                "learner",
                "course",
                "step",
                "action",
                "completed",
            ],
            [
                [
                    row["user"],
                    row["training_record"],
                    row["badge_no"],
                    row["learner"],
                    row["course"],
                    row["step"],
                    row["action"],
                    row["completed"],
                ]
                for row in rows
            ],
        )

    if dataset == "opito-monthly":
        rows = opito_monthly_rows(
            _date(params.get("from")), _date(params.get("to"))
        )
        return (
            [
                "course",
                "course_code",
                "opito_reg_code",
                "learner",
                "badge_no",
                "opito_learner_id",
                "start",
                "end",
                "completed",
            ],
            [
                [
                    row["course"],
                    row["course_code"],
                    row["opito_reg_code"],
                    row["learner"],
                    row["badge_no"],
                    row["opito_learner_id"],
                    row["start"],
                    row["end"],
                    row["completed"],
                ]
                for row in rows
            ],
        )

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


def _filename(dataset: str, extension: str) -> str:
    return (
        f"tcms-{dataset}-{timezone.localdate().isoformat()}.{extension}"
    )


def _export_title(dataset: str) -> str:
    return {
        "flow": "Workflow flow status",
        "training-records": "Training records",
        "course-by-month": "Courses by month",
        "delegates-by-month": "Delegates by month",
        "courses-treemap": "Course mix",
        "top-courses": "Top training courses",
        "role-activity": "Role activity",
        "opito-monthly": "OPITO monthly reconciliation",
    }.get(dataset, dataset.replace("-", " ").title())


def _cell_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def csv_response(dataset: str, params) -> HttpResponse:
    headers, rows = _dataset_rows(dataset, params)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{_filename(dataset, "csv")}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_cell_value(value) for value in row])
    return response


def xlsx_response(dataset: str, params) -> HttpResponse:
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter

    headers, rows = _dataset_rows(dataset, params)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = dataset[:31]
    sheet.append(headers)
    for row in rows:
        sheet.append([_cell_value(value) for value in row])
    sheet.freeze_panes = "A2"
    if headers:
        sheet.auto_filter.ref = sheet.dimensions
    for index, header in enumerate(headers, start=1):
        width = len(str(header))
        for row in rows[:200]:
            width = max(width, len(str(_cell_value(row[index - 1]))))
        sheet.column_dimensions[get_column_letter(index)].width = min(
            max(width + 2, 10), 45
        )
    stream = BytesIO()
    workbook.save(stream)
    response = HttpResponse(
        stream.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{_filename(dataset, "xlsx")}"'
    )
    return response


def pdf_response(dataset: str, params) -> HttpResponse:
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    headers, rows = _dataset_rows(dataset, params)
    stream = BytesIO()
    page_size = landscape(A4)
    doc = SimpleDocTemplate(
        stream,
        pagesize=page_size,
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )
    styles = getSampleStyleSheet()
    cell_style = styles["BodyText"].clone("ReportCell", fontSize=7, leading=9)
    header_style = styles["BodyText"].clone(
        "ReportHeader", fontName="Helvetica-Bold", fontSize=7, leading=9
    )
    table_rows = [
        [Paragraph(escape(str(value)), header_style) for value in headers]
    ] + [
        [Paragraph(escape(str(_cell_value(value))), cell_style) for value in row]
        for row in rows
    ]
    page_width = page_size[0] - 16 * mm
    column_width = page_width / max(len(headers), 1)
    table = Table(table_rows, colWidths=[column_width] * len(headers), repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12313a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5da")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7f8")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    doc.build(
        [
            Paragraph(_export_title(dataset), styles["Heading2"]),
            Spacer(1, 4 * mm),
            table,
        ]
    )
    response = HttpResponse(stream.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{_filename(dataset, "pdf")}"'
    )
    return response


def export_response(dataset: str, params, fmt: str = "csv") -> HttpResponse:
    if fmt == "xlsx":
        return xlsx_response(dataset, params)
    if fmt == "pdf":
        return pdf_response(dataset, params)
    return csv_response(dataset, params)


__all__ = [
    "DATASET_ROLES",
    "build_dashboard",
    "course_month_rows",
    "course_type_rows",
    "csv_response",
    "delegate_month_rows",
    "export_response",
    "flow_status_payload",
    "opito_monthly_rows",
    "pdf_response",
    "report_year_range",
    "role_activity_earliest_date",
    "role_activity_roles",
    "role_activity_rows",
    "role_activity_summary",
    "top_course_rows",
    "training_record_rows",
    "xlsx_response",
]
