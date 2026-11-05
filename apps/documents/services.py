"""Shared document persistence for generated and uploaded artefacts."""
from __future__ import annotations

import hashlib

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from apps.documents.models import Document


def store_bytes(
    *,
    kind: str,
    owner_type: str,
    owner_id: int | None,
    key: str,
    data: bytes,
    mime: str,
    actor=None,
) -> Document:
    """Persist ``data`` and register its metadata in ``Document``."""
    if default_storage.exists(key):
        default_storage.delete(key)
    saved = default_storage.save(key, ContentFile(data))
    return Document.objects.create(
        kind=kind,
        owner_type=owner_type,
        owner_id=owner_id,
        object_key=saved,
        mime=mime,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        generated_by=actor if getattr(actor, "is_authenticated", False) else None,
    )


def read_bytes(key: str) -> bytes:
    with default_storage.open(key, "rb") as fh:
        return fh.read()


def exists(key: str) -> bool:
    return bool(key) and default_storage.exists(key)
