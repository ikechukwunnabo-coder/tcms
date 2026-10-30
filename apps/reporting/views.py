from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.common.enums import RoleCode
from apps.common.permissions import RolePermission
from apps.common.views import RoleScopedModelViewSet
from apps.delivery.models import TrainingRecord
from apps.reporting import serializers as s
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
