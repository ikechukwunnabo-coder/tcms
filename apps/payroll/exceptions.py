"""Payroll & finance domain exceptions — mapped in ``apps.common.exceptions``."""
from __future__ import annotations


class PayrollError(Exception):
    """Base payroll error (400)."""


class PayrollConfigError(PayrollError):
    """Missing chart of accounts / tax table / settings (500-class misuse -> 422)."""


class JournalError(PayrollError):
    """Invalid journal content (400)."""


class UnbalancedJournal(JournalError):
    """Debits do not equal credits (422)."""


class JournalStateError(PayrollError):
    """Illegal journal state transition (409)."""


class PayRunError(PayrollError):
    """Invalid pay-run content (400)."""


class PayRunStateError(PayrollError):
    """Illegal pay-run state transition (409)."""


class SegregationOfDutiesError(PayrollError):
    """Preparer and approver must differ (R-FIN-08, 403)."""


class TimesheetError(PayrollError):
    """Invalid timesheet content (400)."""


class TimesheetStateError(PayrollError):
    """Illegal timesheet state transition (409)."""
