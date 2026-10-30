"""Certificate artefact rendering for dispatch/ZIP assembly.

Certificates are drawn on demand with ReportLab; if a stored PDF exists at
``certificate.object_key`` it is returned unchanged. Branding (organisation,
logo, signatory, verification URL) comes from settings so each deployment can
supply its own artwork without code changes.
"""
from __future__ import annotations

import io

from django.conf import settings
from django.core.files.storage import default_storage
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

NAVY = HexColor("#0F2A44")
GOLD = HexColor("#B08D57")
INK = HexColor("#1A1A1A")
MUTED = HexColor("#5A6572")


def certificate_pdf_bytes(certificate) -> bytes:
    """Return the PDF bytes for ``certificate`` (stored artefact or rendered)."""
    if certificate.object_key:
        try:
            with default_storage.open(certificate.object_key, "rb") as fh:
                return fh.read()
        except (FileNotFoundError, OSError):
            pass
    return render_certificate(certificate)


def render_certificate(certificate) -> bytes:
    """Render a branded A4-landscape certificate as PDF bytes."""
    buf = io.BytesIO()
    width, height = landscape(A4)
    page = canvas.Canvas(buf, pagesize=(width, height))
    page.setTitle(f"Certificate {certificate.certificate_no}")
    page.setAuthor(_text(getattr(settings, "CERTIFICATE_ORG_NAME", "Training Centre")))

    _border(page, width, height)
    _logo(page, width, height)

    org = _text(getattr(settings, "CERTIFICATE_ORG_NAME", "Training Centre"))
    address = _text(getattr(settings, "CERTIFICATE_ORG_ADDRESS", ""))
    y = height - 3.4 * cm
    page.setFillColor(NAVY)
    page.setFont("Helvetica-Bold", 18)
    page.drawCentredString(width / 2, y, org)
    if address:
        y -= 0.55 * cm
        page.setFillColor(MUTED)
        page.setFont("Helvetica", 9)
        page.drawCentredString(width / 2, y, address)

    y -= 1.45 * cm
    page.setFillColor(GOLD)
    page.setFont("Helvetica-Bold", 15)
    page.drawCentredString(
        width / 2, y, _text(getattr(settings, "CERTIFICATE_TITLE", "CERTIFICATE OF TRAINING"))
    )

    y -= 0.7 * cm
    page.setStrokeColor(GOLD)
    page.setLineWidth(1.2)
    page.line(width / 2 - 3.2 * cm, y, width / 2 + 3.2 * cm, y)

    y -= 1.6 * cm
    page.setFillColor(MUTED)
    page.setFont("Helvetica", 10)
    page.drawCentredString(width / 2, y, "This is to certify that")

    learner = certificate.learner
    name = getattr(learner, "full_name", "") or (
        f"{learner.first_name} {learner.surname}".strip()
    )
    y -= 1.15 * cm
    page.setFillColor(INK)
    page.setFont("Helvetica-Bold", _fit_size(page, name, "Helvetica-Bold", 30, 18, 24 * cm))
    page.drawCentredString(width / 2, y, _text(name))

    y -= 0.55 * cm
    page.setStrokeColor(NAVY)
    page.setLineWidth(0.8)
    page.line(width / 2 - 6 * cm, y, width / 2 + 6 * cm, y)

    y -= 1.25 * cm
    page.setFillColor(MUTED)
    page.setFont("Helvetica", 10)
    page.drawCentredString(width / 2, y, "has successfully completed the training course")

    course = None
    if certificate.training_record and certificate.training_record.course:
        course = certificate.training_record.course
    if course is not None:
        y -= 1.05 * cm
        page.setFillColor(NAVY)
        page.setFont(
            "Helvetica-Bold", _fit_size(page, course.name, "Helvetica-Bold", 20, 13, 26 * cm)
        )
        page.drawCentredString(width / 2, y, _text(course.name))

    y -= 1.05 * cm
    page.setFont("Helvetica", 9.5)
    page.setFillColor(MUTED)
    details = [f"Certificate No: {certificate.certificate_no}"]
    if certificate.issued_at is not None:
        details.append(f"Issued: {certificate.issued_at.date().isoformat()}")
    if certificate.expiry_date is not None:
        details.append(f"Expires: {certificate.expiry_date.isoformat()}")
    page.drawCentredString(width / 2, y, "   |   ".join(details))

    _signature(page, certificate, width, height)
    _footer(page, certificate, width, height)

    page.showPage()
    page.save()
    return buf.getvalue()


def _border(page: canvas.Canvas, width: float, height: float) -> None:
    page.setFillColor(white)
    page.rect(0, 0, width, height, stroke=0, fill=1)
    page.setStrokeColor(NAVY)
    page.setLineWidth(5)
    page.rect(0.9 * cm, 0.9 * cm, width - 1.8 * cm, height - 1.8 * cm)
    page.setStrokeColor(GOLD)
    page.setLineWidth(1)
    page.rect(1.15 * cm, 1.15 * cm, width - 2.3 * cm, height - 2.3 * cm)


def _logo(page: canvas.Canvas, width: float, height: float) -> None:
    key = getattr(settings, "CERTIFICATE_LOGO_KEY", "")
    if not key:
        return
    image = _open_image(key)
    if image is None:
        return
    size = 2.0 * cm
    page.drawImage(
        image,
        width / 2 - size / 2,
        height - 3.1 * cm,
        width=size,
        height=size,
        preserveAspectRatio=True,
        anchor="c",
        mask="auto",
    )


def _signature(page: canvas.Canvas, certificate, width: float, height: float) -> None:
    base_y = 4.2 * cm
    sig_w, sig_h = 5.2 * cm, 2.4 * cm
    left_x = width / 2 - 7.2 * cm
    right_x = width / 2 + 2.0 * cm

    drawn = False
    if certificate.signature_applied and certificate.signature_object_key:
        image = _open_image(certificate.signature_object_key)
        if image is not None:
            page.drawImage(
                image,
                left_x,
                base_y + 0.55 * cm,
                width=sig_w,
                height=sig_h,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
            drawn = True
    if not drawn:
        page.setStrokeColor(INK)
        page.setLineWidth(0.8)
        page.line(left_x, base_y + 0.6 * cm, left_x + sig_w, base_y + 0.6 * cm)

    page.setFillColor(MUTED)
    page.setFont("Helvetica", 9)
    page.drawCentredString(
        left_x + sig_w / 2,
        base_y + 0.2 * cm,
        _text(getattr(settings, "CERTIFICATE_SIGNATORY_NAME", "Managing Director")),
    )
    page.setFont("Helvetica-Oblique", 8)
    page.drawCentredString(
        left_x + sig_w / 2,
        base_y - 0.2 * cm,
        _text(getattr(settings, "CERTIFICATE_SIGNATORY_TITLE", "Managing Director")),
    )

    seal_drawn = False
    if certificate.seal_applied and certificate.seal_object_key:
        image = _open_image(certificate.seal_object_key)
        if image is not None:
            size = 2.6 * cm
            page.drawImage(
                image,
                right_x + sig_w / 2 - size / 2,
                base_y - 0.3 * cm,
                width=size,
                height=size,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
            seal_drawn = True
    if not seal_drawn:
        page.setStrokeColor(GOLD)
        page.setLineWidth(0.9)
        page.circle(right_x + sig_w / 2, base_y + 0.9 * cm, 1.15 * cm)
        page.setFillColor(GOLD)
        page.setFont("Helvetica-Bold", 7)
        page.drawCentredString(right_x + sig_w / 2, base_y + 0.75 * cm, "OFFICIAL")
        page.setFont("Helvetica", 6.5)
        page.drawCentredString(right_x + sig_w / 2, base_y + 0.4 * cm, "SEAL")


def _footer(page: canvas.Canvas, certificate, width: float, height: float) -> None:
    verify_url = getattr(settings, "CERTIFICATE_VERIFY_URL", "")
    line = f"Verify: {verify_url}" if verify_url else ""
    if certificate.signature_applied and certificate.seal_applied:
        state = "Digitally signed and sealed"
    elif certificate.signature_applied:
        state = "Digitally signed"
    elif certificate.seal_applied:
        state = "Seal applied"
    else:
        state = ""
    left = "   |   ".join(part for part in (state, line) if part)
    if left:
        page.setFillColor(MUTED)
        page.setFont("Helvetica", 7.5)
        page.drawString(1.6 * cm, 1.55 * cm, _text(left))
    page.setFillColor(MUTED)
    page.setFont("Helvetica", 7.5)
    page.drawRightString(
        width - 1.6 * cm, 1.55 * cm, _text(f"Certificate No: {certificate.certificate_no}")
    )


def _open_image(key: str):
    try:
        with default_storage.open(key, "rb") as fh:
            return ImageReader(io.BytesIO(fh.read()))
    except Exception:
        return None


def _fit_size(
    page: canvas.Canvas,
    value: str,
    font: str,
    maximum: float,
    minimum: float,
    max_width: float,
) -> float:
    size = maximum
    text = _text(value)
    while size > minimum and page.stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def _text(value) -> str:
    return str(value or "").encode("latin-1", "replace").decode("latin-1")
