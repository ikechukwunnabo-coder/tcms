"""Integration hub services — transactional outbox publisher (design ``04`` §7).

Domain events are written to ``outbox_event`` inside the caller's transaction;
Celery handlers deliver them at-least-once. Publishing is intentionally a plain
insert — the outbox is the durability boundary.
"""
from __future__ import annotations

from apps.integration.models import OutboxEvent


def publish_event(topic: str, payload: dict | None = None) -> OutboxEvent:
    """Queue a domain event for delivery (e.g. ``booking.allocated``)."""
    return OutboxEvent.objects.create(topic=topic, payload=payload or {})
