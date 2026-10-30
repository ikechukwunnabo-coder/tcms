"""Cross-cutting security middleware."""
from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

from apps.common.net import client_ip


class AdminLoginRateLimitMiddleware:
    """Throttle failed Django-admin sign-ins by client IP (fixed window)."""

    path = "/admin/login/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        key = None
        if request.method == "POST" and request.path == self.path:
            ip = client_ip(request) or "unknown"
            key = f"admin-login:{ip}"
            limit = int(getattr(settings, "ADMIN_LOGIN_RATE_LIMIT", 10))
            if cache.get(key, 0) >= limit:
                return HttpResponse(
                    "Too many sign-in attempts. Please try again later.",
                    status=429,
                    content_type="text/plain; charset=utf-8",
                )
        response = self.get_response(request)
        if key is not None:
            if response.status_code == 302:
                cache.delete(key)
            else:
                window = int(getattr(settings, "ADMIN_LOGIN_RATE_WINDOW", 300))
                try:
                    cache.incr(key)
                except ValueError:
                    cache.set(key, 1, window)
        return response
