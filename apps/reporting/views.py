from django.db.models import Count
from django.shortcuts import get_object_or_404
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
from apps.delivery.models import TrainingRecord
from apps.reporting import serializers as s
from apps.reporting.analytics import DATASET_ROLES, build_dashboard, csv_response
from apps.reporting.models import ReportDef, ReportRun
from apps.workflow.models import WorkflowStatus

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


class ReportViewSet(ReadOnlyModelViewSet):
    """``/v1/reports/{code}`` + ``/v1/reports/flow-status`` (design ``04`` §6 P-15)."""

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
        counts = dict(
            TrainingRecord.objects.values_list("status_id").annotate(c=Count("id"))
        )
        data = [
            {
                "status": st.id,
                "code": st.code,
                "name": st.name,
                "count": counts.get(st.id, 0),
                "terminal": st.terminal,
            }
            for st in WorkflowStatus.objects.order_by("id")
        ]
        return Response({"data": data, "total": sum(counts.values())})

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
    """Role-scoped CSV export for operational datasets."""

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
                description="Operational dataset to export as CSV.",
            )
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
        return csv_response(dataset, request.query_params)
