"""Request helpers shared by API and portal views."""
from __future__ import annotations

import ipaddress

from django.conf import settings


def client_ip(request) -> str | None:
    """Client IP for audit/limits; trusts X-Forwarded-For only when configured."""
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            candidate = forwarded.split(",")[0].strip()
            try:
                ipaddress.ip_address(candidate)
            except ValueError:
                pass
            else:
                return candidate
    return request.META.get("REMOTE_ADDR") or None
