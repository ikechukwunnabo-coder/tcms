"""Server-side database snapshot helpers for the staff backup console."""
from __future__ import annotations

import gzip
import io
import shutil
import uuid
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

EXCLUDED_MODELS = [
    "contenttypes",
    "auth.permission",
    "sessions",
    "admin.logentry",
]


def _backup_dir() -> Path:
    directory = Path(settings.BACKUP_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def create_backup() -> dict:
    """Write a timestamped, gzipped JSON snapshot to ``settings.BACKUP_DIR``."""
    directory = _backup_dir()
    now = timezone.localtime()
    stem = f"tcms-backup-{now:%Y%m%d-%H%M%S}"
    target = directory / f"{stem}.json.gz"
    suffix = 1
    while target.exists():
        target = directory / f"{stem}-{suffix}.json.gz"
        suffix += 1

    buffer = io.StringIO()
    call_command(
        "dumpdata",
        exclude=EXCLUDED_MODELS,
        indent=2,
        stdout=buffer,
    )
    payload = buffer.getvalue().encode("utf-8")

    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        with gzip.open(temporary, "wb") as handle:
            handle.write(payload)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)

    return {
        "file_name": target.name,
        "bytes": target.stat().st_size,
        "created_at": now.isoformat(),
    }


def test_backup_storage() -> dict:
    """Verify that the backup directory can be written and read."""
    directory = _backup_dir()
    probe = directory / f".backup-test-{uuid.uuid4().hex}"
    try:
        probe.write_text("tcms backup storage probe", encoding="utf-8")
        if probe.read_text(encoding="utf-8") != "tcms backup storage probe":
            raise OSError("Backup storage read-back did not match.")
    finally:
        probe.unlink(missing_ok=True)

    free = shutil.disk_usage(directory).free
    return {
        "status": "ok",
        "message": "Backup storage is writable.",
        "free_bytes": free,
        "checked_at": timezone.now().isoformat(),
    }
