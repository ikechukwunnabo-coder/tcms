"""Course Joining Instructions (CJI) — generation & delivery (spec §9.7, BR-20).

The CJI describes the *granted/final* session of a confirmed booking and is
delivered to the learner's verified email — or, for corporate nominees, to the
lead email only (BR-16). It is regenerated (new ``version``, the previous row
marked ``superseded``) whenever the granted session changes (SAD §9.3
carry-forward/transfer, AC-10/AC-23). Delivery must never target an unverified
address; an undeliverable CJI is recorded (``failed``) rather than raising, so a
missing contact can never roll back a confirmed seat.
"""
from __future__ import annotations

from urllib.parse import quote

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template import Context, Template
from django.utils import timezone

from apps.audit.services import write_audit
from apps.common.enums import CJIDeliveryStatus
from apps.integration.services import publish_event
from apps.portal.models import JoiningInstruction


class CJIError(Exception):
    """Base class for CJI rule violations."""


class CJIGateError(CJIError):
    """No verified delivery address — delivery must not proceed (BR-20)."""


class CJIAccessDenied(CJIError):
    """The caller does not own this booking's CJI."""


_TEMPLATE = """<html><body>
<h2>Course Joining Instructions</h2>
<p>Dear {{ learner_name }},</p>
<p>Your seat is confirmed. Please find your joining instructions below.</p>
<table>
  <tr><td>Course</td><td>{{ course_name }} ({{ course_code }})</td></tr>
  <tr><td>Date</td><td>{{ course_date }}</td></tr>
  <tr><td>Time</td><td>{{ course_time }}</td></tr>
  <tr><td>Location</td><td>{{ course_location }}</td></tr>
  <tr><td>Duration</td><td>{{ course_duration }}</td></tr>
</table>
{% if map_link %}<p>Map: <a href="{{ map_link }}">{{ map_link }}</a></p>{% endif %}
<p>What to bring:</p><ul>{% for item in required_items %}<li>{{ item }}</li>{% endfor %}</ul>
<p>Coordinator: {{ coordinator_name }} &mdash; {{ coordinator_phone }}
   &mdash; {{ coordinator_email }}</p>
<p><a href="{{ portal_link }}">Open the portal</a> &middot;
<a href="{{ privacy_policy_link }}">Privacy</a> &middot;
<a href="{{ contact_link }}">Contact</a> &middot;
<a href="{{ unsubscribe_link }}">Unsubscribe</a></p>
<p>Issued {{ issued_at }} (v{{ version }})</p>
</body></html>"""


def resolve_recipient(enrolment) -> str:
    """Delivery address for a booking's CJI (spec §9.7 ``resolve_cji_recipient``).

    Corporate nominees go only to the verified lead email (BR-16); everyone else
    to their verified portal email. Raises ``CJIGateError`` when none is usable.
    """
    learner = enrolment.learner
    account = learner.corporate_account
    if account is not None:
        lead = account.lead_user
        if lead is None or not lead.email_verified or not lead.email:
            raise CJIGateError("corporate account has no verified lead email")
        return lead.email

    portal = getattr(learner, "portal_account", None)
    if portal is not None and portal.user.email_verified and portal.user.email:
        return portal.user.email

    raise CJIGateError("booking has no verified delivery address")


def _render_merge(enrolment, session, version: int) -> dict:
    learner = enrolment.learner
    course = session.course
    venue = session.venue
    location = ""
    if venue is not None:
        location = venue.name + (f", {venue.address}" if venue.address else "")
    return {
        "learner_name": learner.full_name,
        "course_name": course.name,
        "course_code": course.course_code,
        "course_date": session.start_date.isoformat() if session.start_date else "",
        "course_time": getattr(settings, "CJI_COURSE_TIME", "09:00"),
        "course_location": location,
        "course_duration": f"{course.duration_days} day(s)" if course.duration_days else "",
        "map_link": f"https://maps.google.com/?q={quote(location)}" if location else "",
        "required_items": list(getattr(settings, "CJI_REQUIRED_ITEMS", [])),
        "coordinator_name": getattr(settings, "CJI_COORDINATOR_NAME", ""),
        "coordinator_phone": getattr(settings, "CJI_COORDINATOR_PHONE", ""),
        "coordinator_email": getattr(settings, "CJI_COORDINATOR_EMAIL", ""),
        "portal_link": getattr(settings, "PORTAL_WEB_BASE_URL", "")
        + getattr(settings, "PORTAL_WEB_PATH", "/portal/"),
        "logo_url": getattr(settings, "CJI_LOGO_URL", ""),
        "privacy_policy_link": getattr(settings, "PORTAL_PRIVACY_LINK", ""),
        "contact_link": getattr(settings, "PORTAL_CONTACT_LINK", ""),
        "unsubscribe_link": getattr(settings, "PORTAL_UNSUBSCRIBE_LINK", ""),
        "version": version,
    }


def render(enrolment, session, version: int) -> tuple[str, dict]:
    merge = _render_merge(enrolment, session, version)
    merge["issued_at"] = timezone.now().isoformat()
    html = Template(_TEMPLATE).render(Context(merge))
    return html, merge


def _deliver(ji: JoiningInstruction) -> None:
    """Send a rendered CJI; record the outcome (never raises)."""
    try:
        to = resolve_recipient(ji.enrolment)
    except CJIGateError:
        ji.delivery_status = CJIDeliveryStatus.FAILED
        ji.save(update_fields=["delivery_status"])
        return

    ji.sent_to = to
    try:
        send_mail(
            subject=f"Course Joining Instructions — {ji.session.course.name}",
            message=ji.merge_data.get("course_location", ""),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to],
            html_message=ji.payload,
            fail_silently=False,
        )
        ji.delivery_status = CJIDeliveryStatus.SENT
        ji.sent_at = timezone.now()
    except Exception:  # delivery transport failure -> retryable
        ji.delivery_status = CJIDeliveryStatus.FAILED
    ji.save(update_fields=["sent_to", "delivery_status", "sent_at"])


@transaction.atomic
def regenerate_and_send(enrolment, session=None) -> JoiningInstruction | None:
    """(Re)generate and send the CJI for the granted session (spec §9.7).

    Idempotent for the same session; a changed session supersedes the previous
    CJI and issues the next version (carry-forward/transfer, AC-10/AC-23).
    """
    session = session or enrolment.session
    if session is None:
        return None

    current = (
        JoiningInstruction.objects.select_for_update()
        .filter(enrolment=enrolment, is_current=True)
        .first()
    )
    if current is not None and current.session_id == session.id:
        return current  # nothing changed — idempotent

    if current is not None:
        current.is_current = False
        current.delivery_status = CJIDeliveryStatus.SUPERSEDED
        current.save(update_fields=["is_current", "delivery_status"])

    version = (current.version + 1) if current is not None else 1
    html, merge = render(enrolment, session, version)
    ji = JoiningInstruction.objects.create(
        enrolment=enrolment,
        session=session,
        version=version,
        is_current=True,
        delivery_status=CJIDeliveryStatus.PENDING,
        payload=html,
        merge_data=merge,
    )
    _deliver(ji)
    write_audit(
        action="cji.issued",
        entity="enrolment",
        entity_id=enrolment.pk,
        after={"cji_id": ji.pk, "version": version, "session_id": session.pk},
    )
    publish_event(
        "cji.issued",
        {"enrolment_id": enrolment.pk, "cji_id": ji.pk, "version": version},
    )
    return ji


def current_for(enrolment) -> JoiningInstruction | None:
    return JoiningInstruction.objects.filter(enrolment=enrolment, is_current=True).first()


@transaction.atomic
def resend(enrolment) -> JoiningInstruction:
    """Re-render and re-send the current CJI (no version bump, spec §9.7)."""
    ji = current_for(enrolment)
    if ji is None:
        raise CJIError("no current CJI to resend")
    html, merge = render(enrolment, ji.session, ji.version)
    ji.payload = html
    ji.merge_data = merge
    ji.delivery_status = CJIDeliveryStatus.PENDING
    _deliver(ji)
    write_audit(
        action="cji.resent",
        entity="enrolment",
        entity_id=enrolment.pk,
        after={"cji_id": ji.pk, "version": ji.version},
    )
    return ji


def mark_bounced(enrolment) -> JoiningInstruction | None:
    """Record a bounce and alert Front Desk to re-send (spec §9.7)."""
    ji = current_for(enrolment)
    if ji is None:
        return None
    ji.delivery_status = CJIDeliveryStatus.BOUNCED
    ji.save(update_fields=["delivery_status"])
    publish_event(
        "cji.bounced",
        {"enrolment_id": enrolment.pk, "cji_id": ji.pk, "sent_to": ji.sent_to},
    )
    return ji


def assert_access(user, enrolment) -> None:
    """Learner (own booking) or corporate lead (nominee) may view/resend (BR-16)."""
    learner = enrolment.learner
    account = learner.corporate_account
    if account is not None and account.lead_user_id == user.pk:
        return
    portal = getattr(learner, "portal_account", None)
    if portal is not None and portal.user_id == user.pk:
        return
    raise CJIAccessDenied("you do not have access to this booking's CJI")
