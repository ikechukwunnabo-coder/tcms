from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.urls import path

from apps.accounts.views import (
    UserRoleAvailableView,
    UserRoleCollectionView,
    UserRoleDeleteView,
    UserRoleDetailView,
    change_password,
    login,
    logout,
)
from apps.catalogue.views import (
    CourseItemRelationAvailableView,
    CourseItemRelationDeleteView,
    CourseItemRelationDetailView,
    CourseItemRelationView,
    CourseModuleRelationAvailableView,
    CourseModuleRelationDeleteView,
    CourseModuleRelationDetailView,
    CourseModuleRelationView,
)
from apps.certification.views import verify_certificate
from apps.common.api import router
from apps.common.backup_views import BackupCreateView, BackupTestView
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
    path("auth/password", change_password, name="change-password"),
    path("backup/backup", BackupCreateView.as_view(), name="backup-create"),
    path("backup/test", BackupTestView.as_view(), name="backup-test"),
    path("course-item-rel", CourseItemRelationView.as_view(), name="course-item-rel"),
    path(
        "course-item-rel/<int:parent_id>",
        CourseItemRelationDetailView.as_view(),
        name="course-item-rel-detail",
    ),
    path(
        "course-item-rel/<int:parent_id>/available",
        CourseItemRelationAvailableView.as_view(),
        name="course-item-rel-available",
    ),
    path(
        "course-item-rel/<int:relation_id>/delete",
        CourseItemRelationDeleteView.as_view(),
        name="course-item-rel-delete",
    ),
    path("course-module-rel", CourseModuleRelationView.as_view(), name="course-module-rel"),
    path(
        "course-module-rel/<int:parent_id>",
        CourseModuleRelationDetailView.as_view(),
        name="course-module-rel-detail",
    ),
    path(
        "course-module-rel/<int:parent_id>/available",
        CourseModuleRelationAvailableView.as_view(),
        name="course-module-rel-available",
    ),
    path(
        "course-module-rel/<int:relation_id>/delete",
        CourseModuleRelationDeleteView.as_view(),
        name="course-module-rel-delete",
    ),
    path("user-role", UserRoleCollectionView.as_view(), name="user-role"),
    path(
        "user-role/<int:user_id>",
        UserRoleDetailView.as_view(),
        name="user-role-detail",
    ),
    path(
        "user-role/<int:user_id>/available",
        UserRoleAvailableView.as_view(),
        name="user-role-available",
    ),
    path(
        "user-role/<int:relation_id>/delete",
        UserRoleDeleteView.as_view(),
        name="user-role-delete",
    ),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path(
        "verify/<str:identifier>/",
        verify_certificate,
        name="certificate-verify",
    ),
    path("reports/export/", ReportExportView.as_view(), name="report-export"),
    path(
        "integration/health/",
        OutboxEventViewSet.as_view({"get": "health"}),
        name="integration-health",
    ),
]
urlpatterns += router.urls
