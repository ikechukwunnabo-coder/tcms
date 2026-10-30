"""Scheduled certification jobs."""
from __future__ import annotations

from celery import shared_task

from apps.certification.services import run_reminders


@shared_task
def send_due_reminders() -> dict:
    """Celery-beat wrapper for the daily certificate-expiry reminder run."""
    return run_reminders()
