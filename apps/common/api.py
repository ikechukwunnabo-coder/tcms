"""Central DRF router — registers every primary Phase 1 viewset under /api/v1/."""
from rest_framework.routers import DefaultRouter

from apps.accounts.views import RoleViewSet, UserViewSet
from apps.audit.views import AuditEventViewSet
from apps.billing.views import CorporateAccountViewSet, InvoiceViewSet, PaymentViewSet
from apps.catalogue.views import (
    CertificateTypeViewSet,
    CourseItemViewSet,
    CourseModuleViewSet,
    CourseViewSet,
)
from apps.certification.views import (
    CertificateSequenceViewSet,
    CertificateViewSet,
    IDCardViewSet,
    OpitoFileViewSet,
)
from apps.delivery.views import (
    DailyMedicalCheckViewSet,
    TrainingInstructorViewSet,
    TrainingItemViewSet,
    TrainingRecordViewSet,
)
from apps.documents.views import DocumentViewSet
from apps.integration.views import (
    ExternalRefViewSet,
    OutboxEventViewSet,
    SeedMarkerViewSet,
    WebhookDeliveryViewSet,
)
from apps.learners.views import LearnerContactViewSet, LearnerDocumentViewSet, LearnerViewSet
from apps.medicals.views import MedicalViewSet
from apps.notifications.views import NotificationTemplateViewSet, NotificationViewSet
from apps.payroll.views import (
    AccountViewSet,
    EmployeeViewSet,
    JournalViewSet,
    PayElementViewSet,
    PaymentFileViewSet,
    PayRunViewSet,
    PayslipViewSet,
    ProvisionViewSet,
    TaxBandViewSet,
    TimeEntryViewSet,
    TimesheetViewSet,
)
from apps.reference.views import (
    CompanyViewSet,
    ContactTypeViewSet,
    NationalityViewSet,
    PositionViewSet,
    StateViewSet,
    TitleViewSet,
)
from apps.reporting.views import ReportDefViewSet, ReportRunViewSet, ReportViewSet
from apps.scheduling.views import (
    CourseSessionViewSet,
    EnrolmentViewSet,
    InstructorViewSet,
    VenueViewSet,
)
from apps.workflow.views import (
    ApprovalHistoryViewSet,
    ApprovalViewSet,
    TransactionLogViewSet,
    WorkflowStatusViewSet,
)

router = DefaultRouter()

# M1 Identity
router.register("users", UserViewSet, basename="users")
router.register("roles", RoleViewSet, basename="roles")

# M2 Reference
router.register("companies", CompanyViewSet, basename="companies")
router.register("nationalities", NationalityViewSet, basename="nationalities")
router.register("states", StateViewSet, basename="states")
router.register("positions", PositionViewSet, basename="positions")
router.register("titles", TitleViewSet, basename="titles")
router.register("contact-types", ContactTypeViewSet, basename="contact-types")

# M3 Learners
router.register("learners", LearnerViewSet, basename="learners")
router.register("learner-contacts", LearnerContactViewSet, basename="learner-contacts")
router.register("learner-documents", LearnerDocumentViewSet, basename="learner-documents")

# M4 Catalogue
router.register("courses", CourseViewSet, basename="courses")
router.register("course-modules", CourseModuleViewSet, basename="course-modules")
router.register("course-items", CourseItemViewSet, basename="course-items")
router.register("certificate-types", CertificateTypeViewSet, basename="certificate-types")

# M5 Scheduling
router.register("venues", VenueViewSet, basename="venues")
router.register("sessions", CourseSessionViewSet, basename="sessions")
router.register("enrolments", EnrolmentViewSet, basename="enrolments")
router.register("instructors", InstructorViewSet, basename="instructors")

# M6 Delivery
router.register("training-records", TrainingRecordViewSet, basename="training-records")
router.register("training-items", TrainingItemViewSet, basename="training-items")
router.register("training-instructors", TrainingInstructorViewSet, basename="training-instructors")
router.register(
    "medical-checks", DailyMedicalCheckViewSet, basename="medical-checks"
)

# M7 Certification
router.register("certificates", CertificateViewSet, basename="certificates")
router.register(
    "certificate-sequences", CertificateSequenceViewSet, basename="certificate-sequences"
)
router.register("id-cards", IDCardViewSet, basename="id-cards")
router.register("opito-files", OpitoFileViewSet, basename="opito-files")

# M8 Medicals
router.register("medicals", MedicalViewSet, basename="medicals")

# M9 Workflow
router.register("workflow-statuses", WorkflowStatusViewSet, basename="workflow-statuses")
router.register("approvals", ApprovalViewSet, basename="approvals")
router.register("approval-history", ApprovalHistoryViewSet, basename="approval-history")
router.register("transaction-logs", TransactionLogViewSet, basename="transaction-logs")

# M10 Billing
router.register("corporate-accounts", CorporateAccountViewSet, basename="corporate-accounts")
router.register("invoices", InvoiceViewSet, basename="invoices")
router.register("payments", PaymentViewSet, basename="payments")

# M11 Finance & Payroll
router.register("accounts", AccountViewSet, basename="accounts")
router.register("journal-entries", JournalViewSet, basename="journal-entries")
router.register("payroll-employees", EmployeeViewSet, basename="payroll-employees")
router.register("pay-elements", PayElementViewSet, basename="pay-elements")
router.register("pay-runs", PayRunViewSet, basename="pay-runs")
router.register("payslips", PayslipViewSet, basename="payslips")
router.register("timesheets", TimesheetViewSet, basename="timesheets")
router.register("time-entries", TimeEntryViewSet, basename="time-entries")
router.register("provisions", ProvisionViewSet, basename="provisions")
router.register("tax-bands", TaxBandViewSet, basename="tax-bands")
router.register("payment-files", PaymentFileViewSet, basename="payment-files")

# M12 Reporting
router.register("reports", ReportViewSet, basename="reports")
router.register("report-defs", ReportDefViewSet, basename="report-defs")
router.register("report-runs", ReportRunViewSet, basename="report-runs")

# M13 Notifications
router.register("notifications", NotificationViewSet, basename="notifications")
router.register(
    "notification-templates", NotificationTemplateViewSet, basename="notification-templates"
)

# M14 Documents
router.register("documents", DocumentViewSet, basename="documents")

# M15 Audit
router.register("audit-events", AuditEventViewSet, basename="audit-events")

# M16 Integration & Seed
router.register("outbox-events", OutboxEventViewSet, basename="outbox-events")
router.register("webhook-deliveries", WebhookDeliveryViewSet, basename="webhook-deliveries")
router.register("external-refs", ExternalRefViewSet, basename="external-refs")
router.register("seed-markers", SeedMarkerViewSet, basename="seed-markers")
