"""OPITO CSV export helpers.

The HUB expects one CSV per ``(course, course start date)`` cohort.  The
header and date formats below follow OPITO's *Registering and Certifying
Learners* guide (DD-MON-YYYY, Booking Ref ``OPITO105``).
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.audit.services import write_audit
from apps.catalogue.models import Course
from apps.certification.models import Certificate, OpitoFile
from apps.common.enums import CertificateTypeCode, WorkflowStatusCode
from apps.delivery.models import TrainingRecord

OPITO_CSV_HEADERS = [
    "Start Date",
    "End Date",
    "Centre Code",
    "Product Code",
    "Booking Ref No",
    "Learner Count",
    "OPITO Learner No",
    "Vantage ID",
    "First Name",
    "Last Name",
    "DOB",
    "Forward Date",
]

CANCELLED_STATUS_IDS = (
    int(WorkflowStatusCode.CANCELLED),
    int(WorkflowStatusCode.REJECTED),
)


class OpitoCohortError(ValueError):
    """Raised when a cohort cannot be resolved or exported."""


def _opito_course_filter() -> Q:
    return Q(course__cert_type_id=CertificateTypeCode.OPITO) | ~Q(
        course__opito_reg_code=""
    )


def opito_cohorts() -> list[dict]:
    """Return all OPITO training cohorts and any generated CSV metadata."""
    rows = (
        TrainingRecord.objects.filter(_opito_course_filter(), start_date__isnull=False)
        .exclude(status_id__in=CANCELLED_STATUS_IDS)
        .values(
            "course_id",
            "course__course_code",
            "course__name",
            "course__opito_reg_code",
            "start_date",
        )
        .annotate(learners=Count("id"))
        .order_by("-start_date", "course__name")
    )
    files = {
        (item.course_id, item.start_date): item
        for item in OpitoFile.objects.filter(
            course_id__in={row["course_id"] for row in rows}
        )
    }
    cohorts = []
    for row in rows:
        generated = files.get((row["course_id"], row["start_date"]))
        cohorts.append(
            {
                "id": f"{row['start_date'].isoformat()} {row['course_id']}",
                "name": row["course__name"],
                "course": row["course_id"],
                "course_code": row["course__course_code"],
                "product_code": row["course__opito_reg_code"],
                "start": row["start_date"].isoformat(),
                "start_date": row["start_date"],
                "learners": row["learners"],
                "record_count": row["learners"],
                "object_key": generated.object_key if generated else "",
                "file_name": Path(generated.object_key).name if generated else "",
                "fileName": Path(generated.object_key).name if generated else "",
                "file_id": generated.pk if generated else None,
                "generated_at": generated.generated_at if generated else None,
            }
        )
    return cohorts


def get_opito_course(course_id: int) -> Course:
    course = Course.objects.filter(pk=course_id).first()
    if course is None:
        raise OpitoCohortError("Course not found.")
    if course.cert_type_id != CertificateTypeCode.OPITO and not course.opito_reg_code.strip():
        raise OpitoCohortError("The selected course is not an OPITO course.")
    return course


def opito_records(course: Course, start_date: date):
    return (
        TrainingRecord.objects.select_related("learner", "course")
        .filter(course=course, start_date=start_date)
        .exclude(status_id__in=CANCELLED_STATUS_IDS)
        .order_by("learner__surname", "learner__first_name", "pk")
    )


def missing_vantage_ids(course: Course, start_date: date) -> list[dict]:
    return [
        {
            "learnerId": record.learner_id,
            "fullName": record.learner.full_name,
            "badge": record.learner.badge_no,
        }
        for record in opito_records(course, start_date)
        if not record.learner.vantage_id.strip()
    ]


def _opito_learner_numbers(records) -> dict[int, str]:
    learner_ids = {record.learner_id for record in records}
    if not learner_ids:
        return {}
    mapping: dict[int, str] = {}
    certificates = (
        Certificate.objects.filter(
            learner_id__in=learner_ids,
            opito_learner_id__gt="",
            voided_at__isnull=True,
        )
        .order_by("learner_id", "-issued_at", "-pk")
        .values_list("learner_id", "opito_learner_id")
    )
    for learner_id, learner_no in certificates:
        mapping.setdefault(learner_id, learner_no)
    return mapping


def _format_date(value: date | datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%d-%b-%Y").upper()


def opito_rows(course: Course, start_date: date) -> list[dict]:
    records = list(opito_records(course, start_date))
    if not records:
        raise OpitoCohortError("No OPITO training records found for that course and date.")
    learner_numbers = _opito_learner_numbers(records)
    count = len(records)
    rows = []
    for record in records:
        learner = record.learner
        rows.append(
            {
                "training_record": record.pk,
                "start_date": record.start_date,
                "end_date": record.end_date or record.start_date,
                "centre_code": getattr(settings, "OPITO_CENTRE_CODE", ""),
                "product_code": course.opito_reg_code,
                "booking_ref": getattr(settings, "OPITO_BOOKING_REF", "OPITO105"),
                "learner_count": count,
                "opito_learner_no": learner_numbers.get(learner.pk, ""),
                "vantage_id": learner.vantage_id,
                "first_name": learner.first_name,
                "last_name": learner.surname,
                "dob": learner.birth_date,
                "forward_date": record.prev_expiry,
            }
        )
    return rows


def opito_csv_bytes(course: Course, start_date: date) -> tuple[bytes, int]:
    rows = opito_rows(course, start_date)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(OPITO_CSV_HEADERS)
    for row in rows:
        writer.writerow(
            [
                _format_date(row["start_date"]),
                _format_date(row["end_date"]),
                row["centre_code"],
                row["product_code"],
                row["booking_ref"],
                row["learner_count"],
                row["opito_learner_no"],
                row["vantage_id"],
                row["first_name"],
                row["last_name"],
                _format_date(row["dob"]),
                _format_date(row["forward_date"]),
            ]
        )
    return buffer.getvalue().encode("utf-8"), len(rows)


@transaction.atomic
def generate_opito_file(course: Course, start_date: date, *, actor=None) -> OpitoFile:
    data, count = opito_csv_bytes(course, start_date)
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S%f")
    stem = f"{course.course_code or course.pk}-{start_date.isoformat()}-{timestamp}"
    object_key = default_storage.save(f"opito/{stem}.csv", ContentFile(data))

    generated, created = OpitoFile.objects.get_or_create(
        course=course, start_date=start_date
    )
    previous_key = generated.object_key
    generated.object_key = object_key
    generated.record_count = count
    generated.generated_at = timezone.now()
    generated.updated_by = actor if getattr(actor, "is_authenticated", False) else None
    if created:
        generated.created_by = generated.updated_by
    generated.save()
    if previous_key and previous_key != object_key:
        default_storage.delete(previous_key)
    write_audit(
        action="opito.file_generated",
        entity="opito_file",
        entity_id=generated.pk,
        actor=actor,
        after={"course": course.pk, "start_date": start_date.isoformat(), "records": count},
    )
    return generated
