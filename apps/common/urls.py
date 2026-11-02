from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.urls import path

from apps.accounts.views import login, logout
from apps.common.api import router
from apps.integration.views import OutboxEventViewSet
from apps.reporting.views import DashboardView, ReportExportView


def health(_request):
    """Liveness/readiness probe — fails (503) when a dependency is down."""
    checks = {"database": "ok", "cache": "ok"}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        checks["database"] = "error"

    try:
        cache.set("tcms:health", "ok", timeout=5)
        if cache.get("tcms:health") != "ok":
            checks["cache"] = "error"
    except Exception:
        checks["cache"] = "error"

    healthy = all(value == "ok" for value in checks.values())
    return JsonResponse(
        {"status": "ok" if healthy else "error", "service": "tcms", "checks": checks},
        status=200 if healthy else 503,
    )


urlpatterns = [
    path("health/", health, name="health"),
    path("auth/login", login, name="login"),
    path("auth/logout", logout, name="logout"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("reports/export/", ReportExportView.as_view(), name="report-export"),
    path(
        "integration/health/",
        OutboxEventViewSet.as_view({"get": "health"}),
        name="integration-health",
    ),
]
urlpatterns += router.urls
