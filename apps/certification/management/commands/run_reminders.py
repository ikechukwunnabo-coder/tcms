"""Daily certificate-expiry reminder job (spec §9.9, BR-21).

Schedule from cron / Task Scheduler, e.g. ``0 7 * * *``.
"""
from datetime import date

from django.core.management.base import BaseCommand

from apps.certification.services import run_reminders


class Command(BaseCommand):
    help = "Deliver due certificate-expiry reminders (suppresses renewed certificates)."

    def add_arguments(self, parser):
        parser.add_argument("--date", help="Run as of YYYY-MM-DD (defaults to today).")

    def handle(self, *args, **options):
        on_date = date.fromisoformat(options["date"]) if options.get("date") else None
        result = run_reminders(on_date)
        self.stdout.write(
            self.style.SUCCESS(
                "reminders due={due} sent={sent} suppressed={suppressed} "
                "failed={failed} skipped={skipped}".format(**result)
            )
        )
