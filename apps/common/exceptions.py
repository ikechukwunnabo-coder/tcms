"""Uniform error model (``04`` §8): ``{error, message, details?}``.

Maps TCMS business-rule exceptions to the documented HTTP codes (422 for
business-rule violations, 409 for state conflicts, 403 for role denial)."""
from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.billing.exceptions import (
    BillingError,
    CorporateCreditError,
    InvoiceError,
    InvoiceStateError,
    OverpaymentError,
    PaymentError,
)
from apps.certification.exceptions import (
    BatchDeliveryError,
    BatchError,
    CannotRenewCertificate,
    CertificateDocumentError,
    CertificateDocumentMissing,
    IdCardNotRequired,
    InvalidCertificateDocument,
    NoReleasedCertificates,
    NoReminderRecipient,
    ReminderError,
    RenewalError,
    RenewalNotPermitted,
)
from apps.delivery.services import RenewalWindowError
from apps.learners.services import AgeError
from apps.medicals.services import MedicalGateError
from apps.payroll.exceptions import (
    JournalError,
    JournalStateError,
    PayrollConfigError,
    PayrollError,
    PayRunError,
    PayRunStateError,
    SegregationOfDutiesError,
    TimesheetError,
    TimesheetStateError,
    UnbalancedJournal,
)
from apps.portal.cji import CJIAccessDenied, CJIError, CJIGateError
from apps.portal.services import (
    CorporateAccountExists,
    CorporateAccountRequired,
    CorporateError,
    DuplicateNominee,
    EmailTaken,
    InvalidToken,
    NomineeHasConfirmedBooking,
    PortalError,
    RateLimited,
    TokenExpired,
    WeakPassword,
)
from apps.scheduling.services import BookingError, CapacityError, SeatUnavailable
from apps.workflow.services import (
    InvalidTransition,
    ReasonRequired,
    RoleNotPermitted,
    WorkflowError,
)

# domain exception -> (http status, error code)
DOMAIN_MAP = (
    (RenewalWindowError, 422, "renewal_window_not_open"),
    (MedicalGateError, 422, "medical_required"),
    (AgeError, 422, "under_min_age"),
    (EmailTaken, 409, "email_taken"),
    (WeakPassword, 422, "weak_password"),
    (InvalidToken, 400, "invalid_token"),
    (TokenExpired, 400, "token_expired"),
    (RateLimited, 429, "rate_limited"),
    (CorporateAccountExists, 409, "corporate_account_exists"),
    (DuplicateNominee, 409, "duplicate_nominee"),
    (NomineeHasConfirmedBooking, 409, "nominee_has_confirmed_booking"),
    (CorporateAccountRequired, 403, "corporate_account_required"),
    (CorporateError, 400, "corporate_error"),
    (PortalError, 400, "portal_error"),
    (CJIGateError, 422, "cji_not_deliverable"),
    (CJIAccessDenied, 403, "cji_access_denied"),
    (CJIError, 400, "cji_error"),
    (CapacityError, 422, "no_forward_capacity"),
    (SeatUnavailable, 409, "capacity_conflict"),
    (BookingError, 400, "booking_error"),
    (RoleNotPermitted, 403, "role_not_permitted"),
    (InvalidTransition, 409, "invalid_transition"),
    (ReasonRequired, 400, "reason_required"),
    (WorkflowError, 400, "workflow_error"),
    (NoReminderRecipient, 422, "no_reminder_recipient"),
    (ReminderError, 400, "reminder_error"),
    (NoReleasedCertificates, 422, "no_released_certificates"),
    (BatchDeliveryError, 502, "batch_delivery_failed"),
    (BatchError, 400, "batch_error"),
    (InvalidCertificateDocument, 422, "invalid_certificate_document"),
    (CertificateDocumentMissing, 404, "certificate_document_missing"),
    (IdCardNotRequired, 422, "id_card_not_required"),
    (CertificateDocumentError, 400, "certificate_document_error"),
    (RenewalWindowError, 422, "renewal_window_not_open"),
    (CannotRenewCertificate, 422, "cannot_renew_certificate"),
    (RenewalNotPermitted, 403, "renewal_not_permitted"),
    (RenewalError, 400, "renewal_error"),
    (InvoiceStateError, 409, "invoice_state_conflict"),
    (OverpaymentError, 422, "overpayment"),
    (CorporateCreditError, 422, "credit_limit_exceeded"),
    (InvoiceError, 400, "invoice_error"),
    (PaymentError, 400, "payment_error"),
    (BillingError, 400, "billing_error"),
    (SegregationOfDutiesError, 403, "segregation_of_duties"),
    (UnbalancedJournal, 422, "journal_not_balanced"),
    (JournalStateError, 409, "journal_state_conflict"),
    (PayRunStateError, 409, "pay_run_state_conflict"),
    (TimesheetStateError, 409, "timesheet_state_conflict"),
    (PayrollConfigError, 422, "payroll_config_error"),
    (JournalError, 400, "journal_error"),
    (PayRunError, 400, "pay_run_error"),
    (TimesheetError, 400, "timesheet_error"),
    (PayrollError, 400, "payroll_error"),
)


def api_exception_handler(exc, context):
    for exc_type, status_code, error_code in DOMAIN_MAP:
        if isinstance(exc, exc_type):
            return Response(
                {"error": error_code, "message": str(exc)}, status=status_code
            )

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    if isinstance(data, dict) and "error" in data:
        return response
    if isinstance(data, dict) and "detail" in data:
        message = data["detail"]
    else:
        message = "request failed"
    return Response(
        {"error": "error", "message": str(message), "details": data},
        status=response.status_code,
    )
