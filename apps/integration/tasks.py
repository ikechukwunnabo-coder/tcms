"""Celery consumers for the transactional outbox (M16).

``dispatch_outbox`` is run by Celery beat; it fans pending events out to
``deliver_outbox_event`` workers. Delivery is at-least-once and idempotent per
webhook target: a ``WebhookDelivery`` row records every attempt.
"""
from __future__ import annotations

import hashlib
import hmac
import json

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.enums import OutboxStatus
from apps.integration.models import OutboxEvent, WebhookDelivery

MAX_ATTEMPTS = int(getattr(settings, "OUTBOX_MAX_ATTEMPTS", 8))


@shared_task
def dispatch_outbox(limit: int = 100) -> int:
    """Queue pending outbox events for delivery. Returns the number queued."""
    ids = list(
        OutboxEvent.objects.filter(status=OutboxStatus.PENDING)
        .order_by("created_at")
        .values_list("id", flat=True)[:limit]
    )
    for event_id in ids:
        deliver_outbox_event.delay(event_id)
    return len(ids)


def _signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@shared_task(bind=True, max_retries=MAX_ATTEMPTS, default_retry_delay=30)
def deliver_outbox_event(self, event_id: int) -> bool:
    """Deliver one event to every configured webhook URL."""
    with transaction.atomic():
        try:
            event = OutboxEvent.objects.select_for_update().get(
                pk=event_id, status=OutboxStatus.PENDING
            )
        except OutboxEvent.DoesNotExist:
            return True  # already processed by another worker
        event.status = OutboxStatus.PROCESSING
        event.attempts += 1
        event.error = ""
        event.save(update_fields=["status", "attempts", "error"])

    urls = list(getattr(settings, "OUTBOX_WEBHOOK_URLS", []))
    if not urls:
        _mark_done(event)
        return True

    # Imported lazily so local tooling does not require the HTTP client.
    import requests

    body = json.dumps(
        {"id": event.pk, "topic": event.topic, "payload": event.payload},
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    secret = getattr(settings, "WEBHOOK_SIGNING_SECRET", "")
    headers = {"Content-Type": "application/json", "X-TCMS-Topic": event.topic}
    if secret:
        headers["X-TCMS-Signature"] = _signature(secret, body)

    failed = False
    for url in urls:
        delivery, _ = WebhookDelivery.objects.get_or_create(
            event=event, url=url[:512], defaults={"status": "pending"}
        )
        delivery.attempts += 1
        try:
            response = requests.post(
                url,
                data=body,
                headers=headers,
                timeout=int(getattr(settings, "WEBHOOK_TIMEOUT", 10)),
            )
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code}")
        except Exception as exc:  # transport or non-2xx
            delivery.status = "failed"
            delivery.last_error = str(exc)[:2000]
            delivery.save(update_fields=["status", "last_error", "attempts"])
            failed = True
        else:
            delivery.status = "delivered"
            delivery.last_error = ""
            delivery.save(update_fields=["status", "last_error", "attempts"])

    if failed:
        event.status = OutboxStatus.PENDING
        event.error = "one or more webhook deliveries failed"
        event.save(update_fields=["status", "error"])
        if self.request.retries < MAX_ATTEMPTS:
            raise self.retry(exc=RuntimeError(event.error))
        event.status = OutboxStatus.FAILED
        event.save(update_fields=["status"])
        return False

    _mark_done(event)
    return True


def _mark_done(event: OutboxEvent) -> None:
    event.status = OutboxStatus.DONE
    event.processed_at = timezone.now()
    event.error = ""
    event.save(update_fields=["status", "processed_at", "error"])
