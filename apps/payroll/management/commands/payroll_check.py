"""Validate payroll reference data before go-live or a parallel run."""
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.payroll import services


class Command(BaseCommand):
    help = "Check PAYE bands, pension rates and GL account mappings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            help="Evaluate the tax schedule effective on this date (YYYY-MM-DD).",
        )

    def handle(self, *args, **options):
        on_date = date.fromisoformat(options["date"]) if options["date"] else None
        result = services.validate_configuration(on_date)
        for error in result["errors"]:
            self.stderr.write(self.style.ERROR(error))
        if not result["ok"]:
            raise CommandError("payroll configuration is incomplete")
        self.stdout.write(
            self.style.SUCCESS(
                f"payroll configuration OK ({result['tax_bands']} tax bands, "
                f"pension {result['pension_employee_pct']}% / "
                f"{result['pension_employer_pct']}%)"
            )
        )
