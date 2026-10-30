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
