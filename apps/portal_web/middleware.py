"""Security headers for the public learner portal."""
from __future__ import annotations

PORTAL_PATH_PREFIX = "/portal/"
PORTAL_CSP = "; ".join(
    [
        "default-src 'self'",
        "base-uri 'self'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "img-src 'self' data:",
        "style-src 'self'",
        "script-src 'self'",
        "font-src 'self'",
        "object-src 'none'",
    ]
)


class PortalContentSecurityPolicyMiddleware:
    """Apply a strict CSP to portal pages only (admin/docs keep their own needs)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(PORTAL_PATH_PREFIX):
            response.headers.setdefault("Content-Security-Policy", PORTAL_CSP)
        return response
