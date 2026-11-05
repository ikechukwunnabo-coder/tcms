"""Certification domain exceptions."""


class ReminderError(Exception):
    """Base class for certificate-reminder rule violations."""


class NoReminderRecipient(ReminderError):
    """No deliverable address for the certificate owner."""


class RenewalError(Exception):
    """Base class for renewal booking rule violations."""


class CannotRenewCertificate(RenewalError):
    """The certificate is not eligible for renewal."""


class RenewalNotPermitted(RenewalError):
    """Renewal not permitted for this certificate (ownership/status)."""


class BatchError(Exception):
    """Base class for certificate batch / dispatch rule violations."""


class NoReleasedCertificates(BatchError):
    """The batch has no released certificates to assemble/deliver."""


class BatchDeliveryError(BatchError):
    """The corporate ZIP could not be delivered to the lead email."""


class CertificateDocumentError(Exception):
    """Base class for certificate/ID-card artefact rule violations."""


class InvalidCertificateDocument(CertificateDocumentError):
    """The uploaded file is not a valid certificate/ID-card PDF."""


class CertificateDocumentMissing(CertificateDocumentError):
    """The requested artefact has not been generated or uploaded yet."""


class IdCardNotRequired(CertificateDocumentError):
    """The course is not configured to issue an ID card."""
