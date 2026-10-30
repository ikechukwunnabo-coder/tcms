from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.common.enums import RoleCode
from apps.common.permissions import ANY_ROLE, RolePermission
from apps.common.views import RoleScopedModelViewSet
from apps.delivery.models import TrainingRecord
from apps.workflow import serializers as s
from apps.workflow import services as wf
from apps.workflow.models import Approval, ApprovalHistory, TransactionLog, WorkflowStatus

ADMIN_ONLY = (RoleCode.SYSTEM_ADMIN,)


class WorkflowStatusViewSet(RoleScopedModelViewSet):
    queryset = WorkflowStatus.objects.all().order_by("id")
    serializer_class = s.WorkflowStatusSerializer
    required_roles = ANY_ROLE
    write_roles = ADMIN_ONLY


class ApprovalViewSet(RoleScopedModelViewSet):
    """``/v1/approvals`` lists approval rows; ``{pk}`` in the advance/reject
    actions is the **training record** id (design ``04`` §4, R-WF-01..03)."""

    queryset = (
        Approval.objects.select_related("current_status", "assigned_role").order_by("-created_at")
    )
    serializer_class = s.ApprovalSerializer
    required_roles = ANY_ROLE
    write_roles = ANY_ROLE
    filterset_fields = ["training_record", "current_status", "action", "assigned_role"]

    @action(detail=True, methods=["post"], url_path="advance")
    def advance(self, request, pk=None):
        payload = s.WorkflowActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        record = get_object_or_404(TrainingRecord, pk=pk)
        new_status = wf.advance(
            record,
            request.user,
            action=payload.validated_data["action"],
            reason=payload.validated_data["reason"],
        )
        return Response({"status": new_status.id, "code": new_status.code})

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        payload = s.WorkflowActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        record = get_object_or_404(TrainingRecord, pk=pk)
        new_status = wf.advance(
            record, request.user, action="reject", reason=payload.validated_data["reason"]
        )
        return Response({"status": new_status.id, "code": new_status.code})


class ApprovalHistoryViewSet(ReadOnlyModelViewSet):
    queryset = ApprovalHistory.objects.select_related("status").order_by("-updated_at")
    serializer_class = s.ApprovalHistorySerializer
    permission_classes = [RolePermission]
    required_roles = ANY_ROLE
    write_roles = ()
    filterset_fields = ["training_record", "status"]


class TransactionLogViewSet(ReadOnlyModelViewSet):
    queryset = TransactionLog.objects.all().order_by("-changed_at")
    serializer_class = s.TransactionLogSerializer
    permission_classes = [RolePermission]
    required_roles = ADMIN_ONLY
    write_roles = ()
    filterset_fields = ["entity", "entity_id"]
