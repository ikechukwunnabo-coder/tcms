"""API authentication with an optional token lifetime."""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ExpiringTokenAuthentication(TokenAuthentication):
    """DRF token auth that enforces ``API_TOKEN_TTL_HOURS`` (0 disables expiry)."""

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        ttl_hours = int(getattr(settings, "API_TOKEN_TTL_HOURS", 0) or 0)
        if ttl_hours > 0 and token.created < timezone.now() - timedelta(hours=ttl_hours):
            token.delete()
            raise AuthenticationFailed("Token has expired. Please sign in again.")
        return user, token
