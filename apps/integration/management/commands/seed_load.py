"""Deterministic volume seed for load/performance testing (not for production).

Creates synthetic learners, training records and payroll employees in bulk so a
staging load test exercises realistic table sizes. All rows are prefixed with
``LOAD-`` so ``--reset`` can remove them without touching seeded or UAT data.

    python manage.py seed_load                 # 10k learners / 85k records / 1k employees
    python manage.py seed_load --reset
"""
from __future__ import annotations

import time
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalogue.models import Course
from apps.common.enums import WorkflowStatusCode
from apps.delivery.models import TrainingRecord
from apps.learners.models import Learner
from apps.payroll.models import Employee
from apps.workflow.models import WorkflowStatus

PREFIX = "LOAD-"
BATCH = 2000


class Command(BaseCommand):
    help = "SEED_LOAD: synthetic volume for staging load tests (prefix LOAD-)."

    def add_arguments(self, parser):
        parser.add_argument("--learners", type=int, default=10000)
        parser.add_argument("--records", type=int, default=85000)
        parser.add_argument("--employees", type=int, default=1000)
        parser.add_argument(
            "--reset", action="store_true", help="Remove LOAD- rows and exit."
        )

    def handle(self, *args, **opts):
        if opts["reset"]:
            with transaction.atomic():
                TrainingRecord.objects.filter(learner__badge_no__startswith=PREFIX).delete()
                Employee.objects.filter(staff_no__startswith=PREFIX).delete()
                Learner.objects.filter(badge_no__startswith=PREFIX).delete()
            self.stdout.write(self.style.SUCCESS("SEED_LOAD: volume rows removed."))
            return

        if opts["learners"] < 1:
            raise CommandError("--learners must be at least 1")
        if not Course.objects.exists():
            raise CommandError("Run SEED_DATA before SEED_LOAD (no courses found).")
        status = WorkflowStatus.objects.get(pk=WorkflowStatusCode.COMPLETED)

        started = time.monotonic()
        with transaction.atomic():
            TrainingRecord.objects.filter(learner__badge_no__startswith=PREFIX).delete()
            Employee.objects.filter(staff_no__startswith=PREFIX).delete()
            Learner.objects.filter(badge_no__startswith=PREFIX).delete()

            learners = [
                Learner(
                    badge_no=f"{PREFIX}{i:06d}",
                    surname=f"Load{i:05d}",
                    first_name="Synthetic",
                    active=True,
                )
                for i in range(1, opts["learners"] + 1)
            ]
            Learner.objects.bulk_create(learners, batch_size=BATCH)
            learner_ids = list(
                Learner.objects.filter(badge_no__startswith=PREFIX)
                .order_by("pk")
                .values_list("pk", flat=True)
            )

            course_ids = list(Course.objects.values_list("pk", flat=True))
            today = date.today()
            remaining = opts["records"]
            created = 0
            while remaining:
                size = min(BATCH, remaining)
                records = []
                for _ in range(size):
                    learner_id = learner_ids[created % len(learner_ids)]
                    course_id = course_ids[created % len(course_ids)]
                    start = today - timedelta(days=created % 365)
                    records.append(
                        TrainingRecord(
                            learner_id=learner_id,
                            course_id=course_id,
                            status=status,
                            start_date=start,
                            end_date=start + timedelta(days=365),
                            instructor="Load Test",
                        )
                    )
                    created += 1
                TrainingRecord.objects.bulk_create(records, batch_size=BATCH)
                remaining -= size

            employees = [
                Employee(
                    staff_no=f"{PREFIX}E{i:05d}",
                    full_name=f"Load Employee {i:05d}",
                    basic_salary=800000,
                    active=True,
                )
                for i in range(1, opts["employees"] + 1)
            ]
            Employee.objects.bulk_create(employees, batch_size=BATCH)

        elapsed = time.monotonic() - started
        self.stdout.write(
            self.style.SUCCESS(
                f"SEED_LOAD: {opts['learners']} learners, {opts['records']} records, "
                f"{opts['employees']} employees in {elapsed:.1f}s. "
                "Remove with: manage.py seed_load --reset"
            )
        )
