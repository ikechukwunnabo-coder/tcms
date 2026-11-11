from datetime import date

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.common.enums import RoleCode
from apps.common.permissions import ANY_ROLE, RolePermission
from apps.common.views import RoleScopedModelViewSet
from apps.reporting import serializers as s
from apps.reporting.analytics import (
    DATASET_ROLES,
    build_dashboard,
    course_month_rows,
    course_type_rows,
    delegate_month_rows,
    export_response,
    flow_status_payload,
    opito_monthly_rows,
    report_year_range,
    role_activity_earliest_date,
    role_activity_roles,
    role_activity_rows,
    role_activity_summary,
    top_course_rows,
    training_record_rows,
)
from apps.reporting.models import ReportDef, ReportRun

REPORTING = (RoleCode.SYSTEM_ADMIN, RoleCode.MD, RoleCode.REPORTS)


class ReportDefViewSet(RoleScopedModelViewSet):
    queryset = ReportDef.objects.all().order_by("code")
    serializer_class = s.ReportDefSerializer
    required_roles = REPORTING
    write_roles = (RoleCode.SYSTEM_ADMIN,)
    filterset_fields = ["code"]
    search_fields = ["code", "name"]


class ReportRunViewSet(ReadOnlyModelViewSet):
    queryset = ReportRun.objects.all().order_by("-generated_at")
    serializer_class = s.ReportRunSerializer
    permission_classes = [RolePermission]
    required_roles = REPORTING
    write_roles = ()
    filterset_fields = ["report_def"]


def _year_param(request):
    value = request.query_params.get("year")
    if value in (None, ""):
        return timezone.localdate().year
    year = int(value)
    if year < 1900 or year > 2200:
        raise ValueError("year must be between 1900 and 2200")
    return year


def _date_param(request, key):
    value = request.query_params.get(key)
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{key} must be an ISO date (YYYY-MM-DD)") from exc


def _role_param(request):
    value = request.query_params.get("role")
    if value in (None, ""):
        return None
    return int(value)


def _bad_request(message):
    return Response(
        {"error": "invalid_parameters", "message": message},
        status=status.HTTP_400_BAD_REQUEST,
    )


class ReportViewSet(ReadOnlyModelViewSet):
    """``/v1/reports/{code}`` plus the reporting intelligence endpoints."""

    queryset = ReportDef.objects.all()
    serializer_class = s.ReportDefSerializer
    permission_classes = [RolePermission]
    required_roles = REPORTING
    write_roles = ()
    lookup_field = "code"
    # Report codes are dotted (e.g. ``training.flow``); the default DRF lookup
    # regex excludes dots, so allow everything except a path separator.
    lookup_value_regex = "[^/]+"

    @action(detail=False, methods=["get"], url_path="flow-status")
    def flow_status(self, request):
        return Response(flow_status_payload())

    @action(detail=False, methods=["get"], url_path="year-range")
    def year_range(self, request):
        return Response(report_year_range())

    @action(detail=False, methods=["get"], url_path="training-records")
    def training_records(self, request):
        try:
            rows = training_record_rows(request.query_params)
        except (TypeError, ValueError) as exc:
            return _bad_request(str(exc))
        return Response({"data": rows, "total": len(rows)})

    @action(detail=False, methods=["get"], url_path="course-by-month")
    def course_by_month(self, request):
        try:
            year = _year_param(request)
        except (TypeError, ValueError) as exc:
            return _bad_request(str(exc))
        return Response({"year": year, "data": course_month_rows(year)})

    @action(detail=False, methods=["get"], url_path="delegates-by-month")
    def delegates_by_month(self, request):
        try:
            year = _year_param(request)
        except (TypeError, ValueError) as exc:
            return _bad_request(str(exc))
        return Response({"year": year, "data": delegate_month_rows(year)})

    @action(detail=False, methods=["get"], url_path="courses-treemap")
    def courses_treemap(self, request):
        try:
            year = _year_param(request)
        except (TypeError, ValueError) as exc:
            return _bad_request(str(exc))
        return Response({"year": year, "data": course_type_rows(year)})

    @action(detail=False, methods=["get"], url_path="top-courses")
    def top_courses(self, request):
        try:
            year = _year_param(request)
        except (TypeError, ValueError) as exc:
            return _bad_request(str(exc))
        return Response({"year": year, "data": top_course_rows(year)})

    @action(detail=False, methods=["get"], url_path="role-activity")
    def role_activity(self, request):
        try:
            role = _role_param(request)
            start = _date_param(request, "from")
            end = _date_param(request, "to")
        except (TypeError, ValueError) as exc:
            return _bad_request(str(exc))
        rows = role_activity_rows(role, start, end)
        return Response({"data": rows, "total": len(rows)})

    @action(detail=False, methods=["get"], url_path="role-activity/summary")
    def role_activity_summary(self, request):
        try:
            role = _role_param(request)
            start = _date_param(request, "from")
            end = _date_param(request, "to")
        except (TypeError, ValueError) as exc:
            return _bad_request(str(exc))
        rows = role_activity_summary(role, start, end)
        return Response({"data": rows, "total": len(rows)})

    @action(detail=False, methods=["get"], url_path="role-activity/roles")
    def role_activity_roles(self, request):
        return Response({"data": role_activity_roles()})

    @action(detail=False, methods=["get"], url_path="role-activity/earliest-date")
    def role_activity_earliest_date(self, request):
        return Response({"date": role_activity_earliest_date()})

    @action(detail=False, methods=["get"], url_path="opito-monthly")
    def opito_monthly(self, request):
        try:
            start = _date_param(request, "from")
            end = _date_param(request, "to")
        except ValueError as exc:
            return _bad_request(str(exc))
        rows = opito_monthly_rows(start, end)
        return Response({"data": rows, "total": len(rows)})

    def retrieve(self, request, code=None):
        definition = get_object_or_404(ReportDef, code=code)
        return Response(s.ReportDefSerializer(definition).data)


class DashboardView(APIView):
    """One call powering the staff operations board."""

    permission_classes = [RolePermission]
    required_roles = ANY_ROLE
    write_roles = ()

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(build_dashboard(request.user))


class ReportExportView(APIView):
    """Role-scoped CSV, XLSX and PDF export for operational datasets."""

    permission_classes = [RolePermission]
    required_roles = ANY_ROLE
    write_roles = ()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "dataset",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                required=True,
                description="Operational dataset to export.",
            ),
            OpenApiParameter(
                "format",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                required=False,
                description="csv (default), xlsx or pdf.",
            ),
        ],
        responses={
            200: OpenApiTypes.BINARY,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
    )
    def get(self, request):
        dataset = request.query_params.get("dataset", "").strip()
        allowed = DATASET_ROLES.get(dataset)
        if allowed is None:
            return Response(
                {
                    "error": "unknown_dataset",
                    "message": "Choose one of: " + ", ".join(sorted(DATASET_ROLES)),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        if not (
            getattr(user, "is_superuser", False)
            or user.roles.filter(id__in=[int(role) for role in allowed]).exists()
        ):
            return Response(
                {
                    "error": "forbidden",
                    "message": "You do not have the required role for this export.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        fmt = request.query_params.get("format", "csv").strip().lower()
        if fmt not in {"csv", "xlsx", "pdf"}:
            return Response(
                {
                    "error": "unknown_format",
                    "message": "format must be csv, xlsx or pdf",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            return export_response(dataset, request.query_params, fmt)
        except (TypeError, ValueError) as exc:
            return _bad_request(str(exc))
