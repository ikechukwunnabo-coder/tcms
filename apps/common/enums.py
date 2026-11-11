"""Shared enums.

Integer codes mirror the AXIS role/status/cert-type codes so the rebuilt model
stays faithful to the reference (parity — ADR-0003; see design ``02-database.md``
§4, ``03-business-logic.md`` §2). No migration is involved; seeds use these codes.
"""
from django.db import models


class RoleCode(models.IntegerChoices):
    SYSTEM_ADMIN = 1, "System Admin"
    ADMIN = 2, "Admin"
    FRONT_DESK = 3, "Front Desk"
    MEDIC = 4, "Medic"
    TRAINING_COORDINATOR = 5, "Training Coordinator"
    ACCOUNTS = 6, "Accounts"
    DUE_DILIGENCE = 7, "Due Diligence"
    MD = 8, "Managing Director"
    PRINTER = 9, "Printer"
    INSTRUCTOR = 10, "Instructor"
    REPORTS = 11, "Reports"
    VERIFICATION = 12, "Verification"


class WorkflowStatusCode(models.IntegerChoices):
    NEW_RECORD = 1, "New record"
    ADMIN_DONE = 2, "Admin done"
    VERIFICATION_DONE = 3, "Verification done"
    FRONT_DESK_DONE = 4, "Front desk done"
    MEDIC_DONE = 5, "Medic done"
    TRAINING_COORDINATOR_DONE = 6, "Training Coordinator done"
    ACCOUNTS_DONE = 7, "Accounts done"
    DUE_DILIGENCE_DONE = 8, "Due Diligence done"
    MD_DONE = 9, "MD done"
    CERTIFICATE_DONE = 10, "Certificate done"
    ID_CARD_DONE = 11, "ID Card done"
    COMPLETED = 12, "Completed"
    CANCELLED = 13, "Cancelled"
    REJECTED = 14, "Rejected"


class CertificateTypeCode(models.IntegerChoices):
    STANDARD = 1, "Standard"
    NIMASA = 2, "NIMASA"
    OPITO = 4, "OPITO"


class ExpiryTypeCode(models.IntegerChoices):
    NONE = 0, "No expiry"
    CALCULATED = 1, "Calculated automatically"
    FOET = 2, "FOET expiration date calculation"


class CertificateSource(models.TextChoices):
    GENERATED = "generated", "Generated"
    UPLOADED = "uploaded", "Uploaded"


class Sex(models.TextChoices):
    MALE = "M", "Male"
    FEMALE = "F", "Female"


class LearnerType(models.TextChoices):
    INDIVIDUAL = "individual", "Individual"
    CORPORATE = "corporate", "Corporate"


class PortalAccountType(models.TextChoices):
    """Portal identity kind (spec §9.6). Nominees have no login of their own."""

    INDIVIDUAL = "individual", "Individual"
    CORPORATE_LEAD = "corporate_lead", "Corporate lead"
    CORPORATE_NOMINEE = "corporate_nominee", "Corporate nominee"


class Fitness(models.TextChoices):
    FIT = "fit", "Fit"
    FIT_WITH_RESTRICTIONS = "fit_with_restrictions", "Fit with restrictions"
    UNFIT = "unfit", "Unfit"


class EnrolmentStatus(models.TextChoices):
    BOOKED = "booked", "Booked"
    WAITLISTED = "waitlisted", "Waitlisted"
    CANCELLED = "cancelled", "Cancelled"
    ATTENDED = "attended", "Attended"


class BookingState(models.TextChoices):
    """Portal booking lifecycle (approved SAD §7, adapted onto ``enrolment``).

    Reconciliation: the SAD ``course_bookings`` state machine is modelled on the
    canonical M5 ``enrolment`` record (design ``04`` §5/§6) rather than a
    parallel table. ``enrolment.status`` stays the coarse canonical status.
    """

    REGISTERED = "registered", "Registered"
    PAYMENT_UPLOADED = "payment_uploaded", "Payment uploaded"
    PAYMENT_REJECTED = "payment_rejected", "Payment rejected"
    CONFIRMED = "confirmed", "Confirmed"
    SESSION_TRANSFERRED = "session_transferred", "Session transferred"
    OVERFLOW = "overflow", "Overflow"
    CANCELLED = "cancelled", "Cancelled"
    ATTENDED = "attended", "Attended"
    NO_SHOW = "no_show", "No show"
    DENIED = "denied", "Denied"


class SessionStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    OPEN = "open", "Open"
    FULL = "full", "Full"
    RUNNING = "running", "Running"
    CLOSED = "closed", "Closed"


class CJIDeliveryStatus(models.TextChoices):
    """Delivery lifecycle of a Course Joining Instruction (spec §9.7, BR-20)."""

    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    BOUNCED = "bounced", "Bounced"
    SUPERSEDED = "superseded", "Superseded"
    FAILED = "failed", "Failed"


class CertificateReminderStatus(models.TextChoices):
    """Lifecycle of a certificate-expiry reminder (spec §9.9, BR-21)."""

    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    SUPPRESSED = "suppressed", "Suppressed (renewed)"
    FAILED = "failed", "Failed"


class CertificateBatchStatus(models.TextChoices):
    """Corporate ZIP-delivery lifecycle (spec §7.15, BR-17a)."""

    COLLECTING = "collecting", "Collecting"
    ASSEMBLING = "assembling", "Assembling"
    READY = "ready", "Ready"
    DELIVERED = "delivered", "Delivered"
    FAILED = "failed", "Failed"


class DocumentKind(models.TextChoices):
    PASSPORT = "passport", "Passport"
    ID_SCAN = "id_scan", "ID scan"
    PHOTO = "photo", "Photo"
    CERTIFICATE = "certificate", "Certificate"
    CJI = "cji", "Course Joining Instructions"
    FOET_SCAN = "foet_scan", "FOET scan"
    MEDICAL = "medical", "Medical fitness"
    PAYMENT_PROOF = "payment_proof", "Payment proof"
    WELCOME_LETTER = "welcome_letter", "Welcome letter"
    OTHER = "other", "Other"


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ISSUED = "issued", "Issued"
    PART_PAID = "part_paid", "Part paid"
    PAID = "paid", "Paid"
    VOID = "void", "Void"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"


class OutboxStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    DONE = "done", "Done"
    FAILED = "failed", "Failed"


class AccountType(models.TextChoices):
    ASSET = "asset", "Asset"
    LIABILITY = "liability", "Liability"
    EQUITY = "equity", "Equity"
    INCOME = "income", "Income"
    EXPENSE = "expense", "Expense"


class JournalStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    POSTED = "posted", "Posted"
    VOID = "void", "Void"


class PayElementKind(models.TextChoices):
    EARNING = "earning", "Earning"
    DEDUCTION = "deduction", "Deduction"
    EMPLOYER = "employer", "Employer contribution"


class PayFrequency(models.TextChoices):
    MONTHLY = "monthly", "Monthly"
    WEEKLY = "weekly", "Weekly"


class PayRunStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    APPROVED = "approved", "Approved"
    POSTED = "posted", "Posted"
    PAID = "paid", "Paid"
    VOID = "void", "Void"


class TimesheetStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class TimeEntryKind(models.TextChoices):
    REGULAR = "regular", "Regular"
    OT150 = "ot150", "Overtime 1.5x"
    OT200 = "ot200", "Overtime 2.0x"


class PaymentFileStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    GENERATED = "generated", "Generated"
    VOID = "void", "Void"
