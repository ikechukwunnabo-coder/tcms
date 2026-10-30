"""Backfill the enriched enrolment columns for pre-existing rows.

Pre-existing enrolments (seed/legacy) carried only ``session`` (a granted seat)
and the coarse ``status``. Mirror them into the new booking fields so the SAD
state machine has a consistent baseline.
"""
from django.db import migrations


def backfill(apps, schema_editor):
    Enrolment = apps.get_model("scheduling", "Enrolment")
    for enr in Enrolment.objects.filter(requested_session__isnull=True).iterator():
        enr.requested_session_id = enr.session_id
        enr.original_session_id = enr.session_id
        enr.state = "attended" if enr.status == "attended" else "confirmed"
        enr.seat_allocated_at = enr.created_at
        enr.payment_verified_at = enr.created_at
        enr.save(
            update_fields=[
                "requested_session",
                "original_session",
                "state",
                "seat_allocated_at",
                "payment_verified_at",
            ]
        )


def unbackfill(apps, schema_editor):
    Enrolment = apps.get_model("scheduling", "Enrolment")
    Enrolment.objects.update(
        requested_session=None, original_session=None, seat_allocated_at=None,
        payment_verified_at=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("scheduling", "0002_coursesession_reserve_pct_enrolment_original_session_and_more"),
    ]

    operations = [migrations.RunPython(backfill, unbackfill)]
