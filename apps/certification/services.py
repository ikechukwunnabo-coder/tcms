"""Certification rules."""
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import EmailMessage, send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.text import get_valid_filename

from apps.audit.services import write_audit
from apps.certification.exceptions import (
    BatchDeliveryError,
    CannotRenewCertificate,
    CertificateDocumentError,
    CertificateDocumentMissing,
    IdCardNotRequired,
    InvalidCertificateDocument,
    NoReleasedCertificates,
    NoReminderRecipient,
)
from apps.certification.models import (
    Certificate,
    CertificateBatch,
    CertificateReminder,
    CertificateSequence,
    IDCard,
)
from apps.certification.rendering import (
    certificate_pdf_bytes,
    render_certificate,
    render_id_card,
)
from apps.common.enums import (
    CertificateBatchStatus,
    CertificateReminderStatus,
    CertificateSource,
    CertificateTypeCode,
    ExpiryTypeCode,
    WorkflowStatusCode,
)
from apps.delivery.models import TrainingRecord
from apps.delivery.services import assert_renewal_allowed, compute_expiry
from apps.documents import services as doc_service
from apps.integration.services import publish_event
from apps.learners.services import assert_min_age
from apps.medicals.services import assert_medical_valid
from apps.scheduling import services as scheduling_services
from apps.workflow import services as workflow_services
from apps.workflow.models import WorkflowStatus


def _yy(value: date) -> str:
    return f"{value.year % 100:02d}"


def interim_certificate_no(training_record, today: date | None = None) -> str:
    """R-CERT-01 — value shown before approval."""
    today = today or date.today()
    birth = training_record.learner.birth_date
    return f"T{_yy(today)}{training_record.pk}{_yy(birth) if birth else '00'}"


@transaction.atomic
def allocate_certificate_number(*, course_year: int, item_id: int, birth_date: date | None) -> str:
    """R-CERT-02 — atomically reserve the next number for (course_year, item_id)."""
    seq, _ = CertificateSequence.objects.select_for_update().get_or_create(
        course_year=course_year, item_id=item_id
    )
    seq.last_number += 1
    seq.save(update_fields=["last_number", "updated_at"])
    b = _yy(birth_date) if birth_date else "00"
    return f"T{course_year % 100:02d}{seq.last_number}{b}"


def compute_certificate_expiry(
    training_record: TrainingRecord, on_date: date | None = None
) -> date | None:
    """Apply the course expiry rule, including FOET previous-expiry rollover."""
    course = training_record.course
    if course.expiry_type == ExpiryTypeCode.NONE:
        return None
    if course.expiry_type == ExpiryTypeCode.FOET and training_record.prev_expiry is not None:
        return compute_expiry(
            training_record.prev_expiry + timedelta(days=1), course.validity_years
        )
    return compute_expiry(training_record.start_date, course.validity_years)


def _interim_certificate_no(training_record: TrainingRecord, on_date: date) -> str:
    """OPITO certificates arrive with an external number; keep issuance unique."""
    return f"OPITO-{on_date.year}-{training_record.pk:06d}"


@transaction.atomic
def issue_certificate(
    training_record,
    *,
    actor=None,
    on_date: date | None = None,
    certificate_no: str | None = None,
    opito_learner_id: str = "",
) -> Certificate:
    """Create a certificate for an approved record, enforcing age + medical gates."""
    on_date = on_date or date.today()
    learner = training_record.learner
    assert_min_age(learner.birth_date, on_date)  # gap G6
    assert_medical_valid(learner, on_date)  # R-CERT-04

    course = training_record.course
    is_opito = course.cert_type_id == CertificateTypeCode.OPITO
    number = (certificate_no or "").strip()
    if not number:
        number = (
            _interim_certificate_no(training_record, on_date)
            if is_opito
            else allocate_certificate_number(
                course_year=on_date.year,
                item_id=course.pk,
                birth_date=learner.birth_date,
            )
        )
    if Certificate.objects.filter(certificate_no=number).exists():
        raise InvalidCertificateDocument(
            {"certificate_no": "A certificate with this number already exists."}
        )
    actor = actor if getattr(actor, "is_authenticated", False) else None
    cert = Certificate.objects.create(
        training_record=training_record,
        learner=learner,
        certificate_no=number,
        format_id=course.cert_type_id or 1,
        source=CertificateSource.GENERATED,
        opito_learner_id=opito_learner_id.strip(),
        issued_at=timezone.now(),
        issued_by=actor,
        expiry_date=compute_certificate_expiry(training_record, on_date),
    )

    # R-REN-05 / spec §9.9: link the superseded certificate so its pending
    # reminders can be suppressed as "renewed".
    if training_record.prev_expiry is not None:
        prev = (
            Certificate.objects.filter(
                learner=learner,
                training_record__course=course,
                expiry_date=training_record.prev_expiry,
            )
            .order_by("-issued_at")
            .first()
        )
        if prev is not None:
            prev.renewed_by_certificate = cert
            prev.save(update_fields=["renewed_by_certificate"])
    return cert


def apply_signature_and_seal(certificate: Certificate, *, actor=None) -> Certificate:
    """R-WF-07 stage-2: MD applies digital signature + seal (gap G2)."""
    actor = actor if getattr(actor, "is_authenticated", False) else None
    certificate.signature_applied = True
    certificate.seal_applied = True
    certificate.md_approved_by = actor
    certificate.md_approved_at = timezone.now()
    certificate.save(
        update_fields=["signature_applied", "seal_applied", "md_approved_by", "md_approved_at"]
    )
    return certificate


# ── Expiry validity, reminders & renewal suppression (spec §9.9, BR-21) ──────



def _safe_file_stem(value: str, fallback: str) -> str:
    return get_valid_filename(value) or fallback


def _certificate_file_key(certificate: Certificate) -> str:
    year = certificate.issued_at.year if certificate.issued_at else timezone.now().year
    stem = _safe_file_stem(certificate.certificate_no, f"certificate-{certificate.pk}")
    return f"certificates/{year}/{stem}.pdf"


def _id_card_file_key(id_card: IDCard) -> str:
    year = timezone.now().year
    if id_card.training_record_id and id_card.training_record.start_date:
        year = id_card.training_record.start_date.year
    stem = _safe_file_stem(id_card.card_no, f"id-card-{id_card.pk}")
    return f"id_cards/{year}/{stem}.pdf"


def _store_certificate_pdf(
    certificate: Certificate,
    data: bytes,
    *,
    actor=None,
    source: str = CertificateSource.GENERATED,
) -> Certificate:
    document = doc_service.store_bytes(
        kind="certificate",
        owner_type="certificate",
        owner_id=certificate.pk,
        key=_certificate_file_key(certificate),
        data=data,
        mime="application/pdf",
        actor=actor,
    )
    certificate.object_key = document.object_key
    certificate.source = source
    certificate.save(update_fields=["object_key", "source"])
    action = (
        "certificate.document_uploaded"
        if source == CertificateSource.UPLOADED
        else "certificate.document_generated"
    )
    write_audit(
        action=action,
        entity="certificate",
        entity_id=certificate.pk,
        actor=actor,
        after={"object_key": certificate.object_key, "source": source},
    )
    return certificate


def _store_id_card_pdf(id_card: IDCard, data: bytes, *, actor=None) -> IDCard:
    document = doc_service.store_bytes(
        kind="id_card",
        owner_type="id_card",
        owner_id=id_card.pk,
        key=_id_card_file_key(id_card),
        data=data,
        mime="application/pdf",
        actor=actor,
    )
    id_card.object_key = document.object_key
    id_card.save(update_fields=["object_key"])
    write_audit(
        action="id_card.document_generated",
        entity="id_card",
        entity_id=id_card.pk,
        actor=actor,
        after={"object_key": id_card.object_key},
    )
    return id_card


def certificate_document_bytes(certificate: Certificate, *, actor=None) -> bytes:
    """Return the stored certificate PDF, lazily rendering non-OPITO records."""
    if certificate.object_key:
        try:
            return doc_service.read_bytes(certificate.object_key)
        except (FileNotFoundError, OSError):
            pass
    if certificate.format_id == CertificateTypeCode.OPITO:
        raise CertificateDocumentMissing("Upload the OPITO certificate PDF first.")
    data = render_certificate(certificate)
    _store_certificate_pdf(certificate, data, actor=actor)
    return data


def generate_certificate_document(certificate: Certificate, *, actor=None) -> Certificate:
    """Render and persist a generated certificate. OPITO must use upload."""
    if certificate.format_id == CertificateTypeCode.OPITO:
        raise InvalidCertificateDocument(
            {"file": "OPITO certificates must be uploaded, not generated."}
        )
    data = render_certificate(certificate)
    return _store_certificate_pdf(
        certificate,
        data,
        actor=actor,
        source=CertificateSource.GENERATED,
    )


def _read_pdf_upload(upload) -> bytes:
    limit = int(getattr(settings, "CERTIFICATE_UPLOAD_MAX_BYTES", 10 * 1024 * 1024))
    if upload.size > limit:
        raise InvalidCertificateDocument({"file": f"PDF must be {limit} bytes or smaller."})
    name = (upload.name or "").lower()
    mime = (getattr(upload, "content_type", "") or "").lower()
    if not name.endswith(".pdf") or mime not in ("application/pdf", "application/x-pdf"):
        raise InvalidCertificateDocument({"file": "A PDF file is required."})
    data = upload.read()
    if not data.startswith(b"%PDF-"):
        raise InvalidCertificateDocument({"file": "The uploaded file is not a PDF."})
    return data


def upload_certificate_document(
    certificate: Certificate,
    upload,
    *,
    actor=None,
    certificate_no: str = "",
    opito_learner_id: str = "",
) -> Certificate:
    """Store an externally issued PDF and update OPITO identifiers."""
    data = _read_pdf_upload(upload)
    number = (certificate_no or "").strip()
    if number and number != certificate.certificate_no:
        if Certificate.objects.filter(certificate_no=number).exclude(pk=certificate.pk).exists():
            raise InvalidCertificateDocument(
                {"certificate_no": "A certificate with this number already exists."}
            )
        certificate.certificate_no = number
    learner_id = (opito_learner_id or "").strip()
    if learner_id:
        certificate.opito_learner_id = learner_id
    certificate.save(update_fields=["certificate_no", "opito_learner_id"])
    return _store_certificate_pdf(
        certificate,
        data,
        actor=actor,
        source=CertificateSource.UPLOADED,
    )


@transaction.atomic
def mark_certificate_printed(certificate: Certificate, *, actor=None) -> Certificate:
    """Stamp the certificate and move the workflow to the ID-card stage."""
    record = certificate.training_record
    if record.status_id < WorkflowStatusCode.MD_DONE:
        raise CertificateDocumentError("MD approval is required before printing.")
    actor = actor if getattr(actor, "is_authenticated", False) else None
    certificate.printed_at = timezone.now()
    certificate.printed_by = actor
    certificate.save(update_fields=["printed_at", "printed_by"])

    if record.status_id == WorkflowStatusCode.MD_DONE:
        workflow_services.advance(record, actor)
    if (
        record.status_id == WorkflowStatusCode.CERTIFICATE_DONE
        and not record.course.id_card
    ):
        workflow_services.advance(record, actor)
        workflow_services.advance(record, actor)
    write_audit(
        action="certificate.print",
        entity="certificate",
        entity_id=certificate.pk,
        actor=actor,
    )
    return certificate


def issue_id_card(
    training_record: TrainingRecord, *, actor=None, on_date: date | None = None
) -> IDCard:
    """Create the ID card record for a course that requires one."""
    if not training_record.course.id_card:
        raise IdCardNotRequired("This course does not issue an ID card.")
    existing = IDCard.objects.filter(training_record=training_record).first()
    if existing is not None:
        return existing
    on_date = on_date or date.today()
    card_no = f"ID{_yy(on_date)}{training_record.pk:06d}"
    actor = actor if getattr(actor, "is_authenticated", False) else None
    card = IDCard.objects.create(
        training_record=training_record,
        learner=training_record.learner,
        card_no=card_no,
    )
    write_audit(
        action="id_card.issue",
        entity="id_card",
        entity_id=card.pk,
        actor=actor,
        after={"card_no": card_no},
    )
    return card


def id_card_document_bytes(id_card: IDCard, *, actor=None) -> bytes:
    """Return the stored ID-card PDF, lazily rendering when absent."""
    if id_card.object_key:
        try:
            return doc_service.read_bytes(id_card.object_key)
        except (FileNotFoundError, OSError):
            pass
    data = render_id_card(id_card)
    _store_id_card_pdf(id_card, data, actor=actor)
    return data


def generate_id_card_document(id_card: IDCard, *, actor=None) -> IDCard:
    data = render_id_card(id_card)
    return _store_id_card_pdf(id_card, data, actor=actor)


@transaction.atomic
def mark_id_card_printed(id_card: IDCard, *, actor=None) -> IDCard:
    """Stamp the ID card and complete the final print stage."""
    record = id_card.training_record
    if record is None:
        raise CertificateDocumentError("ID card is not linked to a training record.")
    certificate = record.certificates.filter(printed_at__isnull=False).first()
    if certificate is None and record.status_id < WorkflowStatusCode.CERTIFICATE_DONE:
        raise CertificateDocumentError("Print the certificate before the ID card.")

    actor = actor if getattr(actor, "is_authenticated", False) else None
    id_card.printed_at = timezone.now()
    id_card.printed_by = actor
    id_card.save(update_fields=["printed_at", "printed_by"])

    if record.status_id in (
        WorkflowStatusCode.MD_DONE,
        WorkflowStatusCode.CERTIFICATE_DONE,
        WorkflowStatusCode.ID_CARD_DONE,
    ):
        while record.status_id in (
            WorkflowStatusCode.MD_DONE,
            WorkflowStatusCode.CERTIFICATE_DONE,
            WorkflowStatusCode.ID_CARD_DONE,
        ):
            workflow_services.advance(record, actor)
    write_audit(
        action="id_card.print",
        entity="id_card",
        entity_id=id_card.pk,
        actor=actor,
    )
    return id_card


def expiring_soon_days() -> int:
    return int(getattr(settings, "RENEWAL_WINDOW_DAYS", 90))


def validity_status(certificate: Certificate, today: date | None = None) -> str:
    """Derived validity: renewed / valid / expiring_soon / expired (spec §9.9)."""
    if certificate.renewed_by_certificate_id is not None:
        return "renewed"
    if certificate.expiry_date is None:
        return "valid"
    today = today or date.today()
    if today > certificate.expiry_date:
        return "expired"
    if today >= certificate.expiry_date - timedelta(days=expiring_soon_days()):
        return "expiring_soon"
    return "valid"


def resolve_reminder_recipient(certificate: Certificate) -> str:
    """Owner's verified email — corporate nominees route to the lead email (BR-16).

    An unverified address is never returned (BR-20): delivery is skipped/failed
    rather than sent to an unverified inbox.
    """
    learner = certificate.learner
    account = learner.corporate_account
    if account is not None:
        lead = account.lead_user
        if lead is None or not lead.email_verified or not lead.email:
            return ""
        return lead.email
    portal = getattr(learner, "portal_account", None)
    if portal is not None and portal.user.email_verified and portal.user.email:
        return portal.user.email
    return ""


def schedule_reminders(certificate: Certificate, *, offsets=None) -> list[CertificateReminder]:
    """Create the pending reminder rows for a certificate (idempotent).

    ``due_on = expiry_date - offset_days``; ``offset 0`` is the on-expiry notice.
    No-op for certificates that never expire (spec §9.9, R-EXP-03).
    """
    if certificate.expiry_date is None:
        return []
    offsets = offsets if offsets is not None else getattr(
        settings, "CERTIFICATE_REMINDER_WINDOWS", [90, 60, 30, 0]
    )
    recipient = resolve_reminder_recipient(certificate)
    rows = []
    for offset in offsets:
        row, _ = CertificateReminder.objects.get_or_create(
            certificate=certificate,
            offset_days=offset,
            defaults={
                "due_on": certificate.expiry_date - timedelta(days=offset),
                "recipient": recipient,
            },
        )
        rows.append(row)
    return rows


def _is_corporate(certificate: Certificate) -> bool:
    return bool(getattr(certificate.learner, "corporate_account_id", None))


def _open_batch(account):
    batch = (
        CertificateBatch.objects.filter(
            corporate_account=account,
            status__in=[
                CertificateBatchStatus.COLLECTING,
                CertificateBatchStatus.READY,
                CertificateBatchStatus.FAILED,
                CertificateBatchStatus.ASSEMBLING,
            ],
        )
        .order_by("-created_at")
        .first()
    )
    if batch is None:
        batch = CertificateBatch.objects.create(
            corporate_account=account, status=CertificateBatchStatus.COLLECTING
        )
    if batch.status in (CertificateBatchStatus.READY, CertificateBatchStatus.FAILED):
        batch.status = CertificateBatchStatus.COLLECTING
        batch.save(update_fields=["status"])
    return batch


def _attach_to_batch(certificate: Certificate) -> CertificateBatch:
    account = certificate.learner.corporate_account
    batch = _open_batch(account)
    if certificate.batch_id != batch.pk:
        certificate.batch = batch
        certificate.save(update_fields=["batch"])
    return batch


def _safe_name(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in value)


def _certificate_artefact(certificate: Certificate) -> bytes:
    return certificate_pdf_bytes(certificate)


def _send_release_notice(certificate: Certificate, *, today: date | None = None) -> bool:
    """Notify the individual owner when their certificate is released (BR-17)."""
    today = today or date.today()
    recipient = resolve_reminder_recipient(certificate)
    if not recipient:
        return False
    course = certificate.training_record.course
    learner = certificate.learner
    subject = f"Certificate released — {course.name}"
    body = (
        f"Dear {learner.full_name},\n\n"
        f"Your {course.name} certificate {certificate.certificate_no} has been released.\n"
        f"Sign in to the portal: {getattr(settings, 'PORTAL_BASE_URL', '')}\n\n"
        f"Issued: {certificate.issued_at.date().isoformat() if certificate.issued_at else ''}\n"
        f"Expires: {certificate.expiry_date.isoformat() if certificate.expiry_date else ''}\n"
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:
        return False
    from apps.notifications.models import Notification

    Notification.objects.create(
        template_code="certificate.released",
        recipient=recipient,
        channel="email",
        payload={
            "certificate_id": certificate.pk,
            "certificate_no": certificate.certificate_no,
        },
        status="sent",
        sent_at=timezone.now(),
    )
    return True


@transaction.atomic
def assemble_batch(batch: CertificateBatch) -> CertificateBatch:
    """Assemble all released, unvoided certificates in ``batch`` into one ZIP."""
    certs = list(
        batch.certificates.filter(released_at__isnull=False, voided_at__isnull=True)
        .select_related("learner", "training_record__course")
        .order_by("learner__surname", "learner__first_name", "id")
    )
    if not certs:
        raise NoReleasedCertificates("no released certificates to assemble for this batch")
    batch.status = CertificateBatchStatus.ASSEMBLING
    batch.save(update_fields=["status"])
    buf = BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as zf:
        for cert in certs:
            arcname = f"{_safe_name(cert.certificate_no)}_{_safe_name(cert.learner.surname)}.pdf"
            zf.writestr(arcname, _certificate_artefact(cert))
    data = buf.getvalue()
    if batch.zip_file_ref:
        try:
            default_storage.delete(batch.zip_file_ref)
        except Exception:
            pass
    key = f"corporate_batches/{batch.pk}/{timezone.now():%Y%m%d_%H%M%S}.zip"
    saved = default_storage.save(key, ContentFile(data))
    batch.zip_file_ref = saved
    batch.zip_file_hash = hashlib.sha256(data).hexdigest()
    batch.certificate_count = len(certs)
    batch.status = CertificateBatchStatus.READY
    batch.save(
        update_fields=[
            "zip_file_ref",
            "zip_file_hash",
            "certificate_count",
            "status",
        ]
    )
    return batch


@transaction.atomic
def deliver_batch(batch: CertificateBatch, *, actor=None) -> CertificateBatch:
    """Email the assembled ZIP to the corporate lead (BR-17a)."""
    if batch.status == CertificateBatchStatus.DELIVERED:
        return batch
    if not batch.zip_file_ref or batch.certificate_count == 0:
        assemble_batch(batch)
    if batch.certificate_count == 0:
        raise NoReleasedCertificates("batch has no released certificates to deliver")
    account = batch.corporate_account
    lead = account.lead_user
    if lead is None or not lead.email_verified or not lead.email:
        raise BatchDeliveryError("corporate account has no verified lead email")
    lead_email = lead.email
    batch.status = CertificateBatchStatus.ASSEMBLING
    batch.save(update_fields=["status"])
    try:
        with default_storage.open(batch.zip_file_ref, "rb") as fh:
            data = fh.read()
    except Exception as exc:
        batch.status = CertificateBatchStatus.FAILED
        batch.save(update_fields=["status"])
        raise BatchDeliveryError(str(exc)) from exc
    try:
        message = EmailMessage(
            subject=f"Certificate bundle — {batch.corporate_account.name}",
            body=(
                f"Dear {batch.corporate_account.name},\n\n"
                f"Your corporate training certificates are attached in a single ZIP.\n"
                f"Certificate count: {batch.certificate_count}\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[lead_email],
        )
        message.attach(f"certificates-{batch.pk}.zip", data, "application/zip")
        message.send(fail_silently=False)
    except Exception as exc:
        batch.status = CertificateBatchStatus.FAILED
        batch.save(update_fields=["status"])
        raise BatchDeliveryError(str(exc)) from exc
    batch.status = CertificateBatchStatus.DELIVERED
    batch.delivered_to = lead_email
    batch.delivered_at = timezone.now()
    batch.save(update_fields=["status", "delivered_to", "delivered_at"])
    write_audit(
        action="certificate.batch_delivered",
        entity="certificate_batch",
        entity_id=batch.pk,
        actor=actor,
        after={"certificate_count": batch.certificate_count, "delivered_to": lead_email},
    )
    publish_event(
        "certificate.batch_delivered",
        {"batch_id": batch.pk, "corporate_account_id": batch.corporate_account_id},
    )
    from apps.notifications.models import Notification

    Notification.objects.create(
        template_code="certificate.batch",
        recipient=lead_email,
        channel="email",
        payload={
            "batch_id": batch.pk,
            "certificate_count": batch.certificate_count,
            "zip_file_ref": batch.zip_file_ref,
        },
        status="sent",
        sent_at=timezone.now(),
    )
    return batch


@transaction.atomic
def bundle_for_account(account, *, actor=None) -> CertificateBatch:
    """Assemble and deliver all released nominee certificates for ``account``."""
    batch = _open_batch(account)
    unbatched = Certificate.objects.filter(
        learner__corporate_account=account,
        released_at__isnull=False,
        voided_at__isnull=True,
        batch__isnull=True,
    )
    for cert in unbatched:
        cert.batch = batch
        cert.save(update_fields=["batch"])
    # If no released certs attached to any relevant batch, raise.
    if not batch.certificates.filter(released_at__isnull=False, voided_at__isnull=True).exists():
        raise NoReleasedCertificates("no released certificates to bundle for this account")
    assemble_batch(batch)
    deliver_batch(batch, actor=actor)
    return batch


@transaction.atomic
def release(certificate: Certificate, *, actor=None, now=None) -> Certificate:
    """Mark a certificate released/dispatched and schedule its reminders (BR-17)."""
    now = now or timezone.now()
    if certificate.released_at is None:
        certificate.released_at = now
        certificate.save(update_fields=["released_at"])
        write_audit(
            action="certificate.released",
            entity="certificate",
            entity_id=certificate.pk,
            actor=actor,
            after={"certificate_no": certificate.certificate_no},
        )
        publish_event(
            "certificate.released",
            {"certificate_id": certificate.pk, "learner_id": certificate.learner_id},
        )
    schedule_reminders(certificate)
    if _is_corporate(certificate):
        _attach_to_batch(certificate)
    else:
        _send_release_notice(certificate)
    return certificate


def _reminder_body(certificate: Certificate, today: date) -> tuple[str, str]:
    course = certificate.training_record.course
    learner = certificate.learner
    days_left = (certificate.expiry_date - today).days if certificate.expiry_date else None
    subject = f"Certificate expiry reminder — {course.name}"
    when = certificate.expiry_date.isoformat() if certificate.expiry_date else "n/a"
    if days_left is not None and days_left > 0:
        lead = f"expires in {days_left} day(s) on {when}"
    elif days_left == 0:
        lead = f"expires today ({when})"
    else:
        lead = f"expired on {when}"
    body = (
        f"Dear {learner.full_name},\n\n"
        f"Your {course.name} certificate {lead}.\n"
        f"Renewal is available within {expiring_soon_days()} days before expiry; "
        f"after expiry a fresh full course is required.\n\n"
        f"Certificate no: {certificate.certificate_no}\n"
        f"Portal: {getattr(settings, 'PORTAL_BASE_URL', '')}\n"
    )
    return subject, body


def _send_reminder(certificate: Certificate, recipient: str, today: date) -> bool:
    subject, body = _reminder_body(certificate, today)
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:
        return False
    # In-app "profile" channel (spec §9.9 `channel = [email, profile]`).
    from apps.notifications.models import Notification

    Notification.objects.create(
        template_code="certificate.reminder",
        recipient=recipient,
        channel="profile",
        payload={
            "certificate_id": certificate.pk,
            "certificate_no": certificate.certificate_no,
            "expiry_date": certificate.expiry_date.isoformat()
            if certificate.expiry_date
            else None,
        },
        status="sent",
        sent_at=timezone.now(),
    )
    return True


@transaction.atomic
def run_reminders(today: date | None = None) -> dict:
    """Daily job: deliver due reminders, suppress renewed, record outcomes (§9.9)."""
    today = today or date.today()
    due = list(
        CertificateReminder.objects.select_related(
            "certificate__learner__corporate_account",
            "certificate__training_record__course",
        ).filter(status=CertificateReminderStatus.PENDING, due_on__lte=today)
    )
    sent = suppressed = failed = skipped = 0
    for row in due:
        certificate = row.certificate
        if certificate.released_at is None:
            skipped += 1  # not dispatched yet — reminders begin at release (BR-17)
            continue
        if validity_status(certificate, today) == "renewed":
            row.status = CertificateReminderStatus.SUPPRESSED
            row.save(update_fields=["status"])
            suppressed += 1
            continue

        recipient = resolve_reminder_recipient(certificate)
        row.recipient = recipient or row.recipient
        if not recipient:
            row.status = CertificateReminderStatus.FAILED
            row.save(update_fields=["status", "recipient"])
            failed += 1
            continue

        if _send_reminder(certificate, recipient, today):
            row.status = CertificateReminderStatus.SENT
            row.sent_at = timezone.now()
            row.save(update_fields=["status", "recipient", "sent_at"])
            write_audit(
                action="certificate.reminded",
                entity="certificate",
                entity_id=certificate.pk,
                after={"offset_days": row.offset_days, "recipient": recipient},
            )
            publish_event(
                "certificate.reminder_sent",
                {"certificate_id": certificate.pk, "offset_days": row.offset_days},
            )
            sent += 1
        else:
            row.status = CertificateReminderStatus.FAILED
            row.save(update_fields=["status", "recipient"])
            failed += 1
    return {
        "due": len(due),
        "sent": sent,
        "suppressed": suppressed,
        "failed": failed,
        "skipped": skipped,
    }


def send_reminder_now(certificate: Certificate, *, actor=None, today: date | None = None) -> dict:
    """Manual/escalation reminder (``POST /certificates/{id}/remind``)."""
    today = today or date.today()
    recipient = resolve_reminder_recipient(certificate)
    if not recipient:
        raise NoReminderRecipient("no verified address for the certificate owner")
    ok = _send_reminder(certificate, recipient, today)
    if ok:
        write_audit(
            action="certificate.reminded_manually",
            entity="certificate",
            entity_id=certificate.pk,
            actor=actor,
            after={"recipient": recipient},
        )
    return {"recipient": recipient, "sent": ok, "validity": validity_status(certificate, today)}


@transaction.atomic
def request_renewal(
    certificate: Certificate,
    *,
    session_id: int | None = None,
    actor=None,
    today: date | None = None,
) -> TrainingRecord:
    """Request renewal for a released certificate (R-REN-01/02/03, R-REN-04)."""
    today = today or date.today()
    if certificate.released_at is None:
        raise CannotRenewCertificate("certificate_not_released")
    if certificate.voided_at is not None:
        raise CannotRenewCertificate("certificate_voided")
    existing = (
        TrainingRecord.objects.filter(
            learner=certificate.learner,
            course=certificate.training_record.course,
            prev_expiry=certificate.expiry_date,
        )
        .exclude(status__code__in=["CANCELLED", "REJECTED"])
        .first()
    )
    if existing is not None:
        raise CannotRenewCertificate("renewal_already_requested")

    prev_expiry = certificate.expiry_date
    assert_renewal_allowed(prev_expiry, today)

    course = certificate.training_record.course
    renewal_course = course.refresher_course or course

    enrolment = None
    if session_id is not None:
        from apps.scheduling.models import CourseSession

        session = CourseSession.objects.get(pk=session_id)
        enrolment = scheduling_services.book(certificate.learner, session)
    else:
        from apps.scheduling.models import CourseSession

        session = (
            CourseSession.objects.filter(course=renewal_course, start_date__gte=today)
            .order_by("start_date")
            .first()
        )
        if session is None:
            raise CannotRenewCertificate("no_available_renewal_session")
        enrolment = scheduling_services.book(certificate.learner, session)

    status = WorkflowStatus.objects.filter(code="NEW").first() or WorkflowStatus.objects.first()
    sess = getattr(enrolment, "granted_session", None) or getattr(enrolment, "session", None)
    record = TrainingRecord.objects.create(
        learner=certificate.learner,
        course=renewal_course,
        session=sess,
        enrolment=enrolment,
        start_date=compute_expiry(sess.start_date, renewal_course.duration_days) if sess else None,
        prev_expiry=prev_expiry,
        status=status,
    )
    write_audit(
        action="certificate.renewal_requested",
        entity="certificate",
        entity_id=certificate.pk,
        actor=actor,
        after={"renewal_training_record_id": record.pk, "renewal_course_id": renewal_course.pk},
    )
    publish_event(
        "certificate.renewal_requested",
        {"certificate_id": certificate.pk, "training_record_id": record.pk},
    )
    return record
