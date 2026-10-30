"""Audit service — append-only writes to ``audit_event`` (R-AUD-01, gap G4)."""
from __future__ import annotations

from apps.audit.middleware import get_current_user
from apps.audit.models import AuditEvent


def write_audit(
    *,
    action: str,
    entity: str = "",
    entity_id: int | None = None,
    actor=None,
    before: dict | None = None,
    after: dict | None = None,
    ip: str | None = None,
) -> AuditEvent:
    """Record an immutable audit event.

    ``actor`` defaults to the user on the current request (thread-local)."""
    if actor is None:
        actor = get_current_user()
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        entity=entity,
        entity_id=entity_id,
        before=before,
        after=after,
        ip=ip,
    )
