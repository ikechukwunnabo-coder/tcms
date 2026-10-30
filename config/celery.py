"""Celery application for TCMS.

Broker/backend come from settings (CELERY_BROKER_URL / CELERY_RESULT_BACKEND).
Autodiscovers `tasks.py` in every installed app.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

app = Celery("tcms")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> str:  # pragma: no cover - diagnostic helper
    return f"request: {self.request!r}"
