from datetime import date

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.common.enums import RoleCode, WorkflowStatusCode
from apps.common.permissions import ANY_ROLE, RolePermission
from apps.common.views import RoleScopedModelViewSet
from apps.delivery.models import TrainingRecord
from apps.delivery.serializers import TrainingRecordSerializer
from apps.workflow import serializers as s
from apps.workflow import services as wf
from apps.workflow.models import Approval, ApprovalHistory, TransactionLog, WorkflowStatus

ADMIN_ONLY = (RoleCode.SYSTEM_ADMIN,)


def pending_task_queryset(user):
    role_ids = list(user.roles.values_list("id", flat=True))
    is_system_admin = bool(
        getattr(user, "is_superuser", False) or RoleCode.SYSTEM_ADMIN in role_ids
    )
    pending = TrainingRecord.objects.select_related(
        "learner", "learner__company", "course", "status"
    ).prefetch_related("items")
    if is_system_admin:
        pending = pending.filter(
            Q(status__next_role__isnull=False) | Q(status_id=WorkflowStatusCode.REJECTED)
        )
    else:
        pending = pending.filter(status__next_role_id__in=role_ids)
    return pending.exclude(status__terminal=True).order_by("-created_at")


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

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        payload = s.BulkWorkflowActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        ids = payload.validated_data["ids"]
        action = payload.validated_data["action"]
        reason = payload.validated_data["reason"]
        records = {
            record.pk: record
            for record in TrainingRecord.objects.select_related("status", "learner").filter(
                pk__in=ids
            )
        }
        results = []
        for record_id in ids:
            record = records.get(record_id)
            if record is None:
                results.append(
                    {"id": record_id, "ok": False, "error": "Training record not found."}
                )
                continue
            try:
                new_status = wf.advance(record, request.user, action=action, reason=reason)
            except wf.WorkflowError as exc:
                results.append({"id": record_id, "ok": False, "error": str(exc)})
            else:
                results.append(
                    {
                        "id": record_id,
                        "ok": True,
                        "status": new_status.id,
                        "code": new_status.code,
                    }
                )
        return Response(
            {
                "results": results,
                "succeeded": sum(1 for row in results if row["ok"]),
                "failed": sum(1 for row in results if not row["ok"]),
            }
        )

    @action(detail=False, methods=["get"], url_path="pending-tasks")
    def pending_tasks(self, request):
        pending = pending_task_queryset(request.user)

        search = request.query_params.get("search", "").strip()
        if search:
            query = (
                Q(learner__badge_no__icontains=search)
                | Q(learner__surname__icontains=search)
                | Q(learner__first_name__icontains=search)
                | Q(learner__middle_name__icontains=search)
                | Q(learner__company__name__icontains=search)
                | Q(course__course_code__icontains=search)
                | Q(course__name__icontains=search)
            )
            if search.isdigit():
                query |= Q(pk=int(search))
            pending = pending.filter(query)

        selected_date = request.query_params.get("date", "").strip()
        if selected_date:
            try:
                day = date.fromisoformat(selected_date)
            except ValueError:
                return Response(
                    {"detail": "The date filter must use YYYY-MM-DD."},
                    status=400,
                )
            pending = pending.filter(
                Q(start_date=day)
                | Q(start_date__lte=day, end_date__gte=day)
            )

        try:
            page_size = int(request.query_params.get("page_size", 20))
        except (TypeError, ValueError):
            page_size = 20
        page_size = min(max(page_size, 1), 100)

        paginator = Paginator(pending, page_size)
        page = paginator.get_page(request.query_params.get("page") or 1)
        return Response(
            {
                "data": TrainingRecordSerializer(page.object_list, many=True).data,
                "total": paginator.count,
                "page": page.number,
                "page_size": page_size,
            }
        )

    @action(detail=False, methods=["get"], url_path="my-activity")
    def my_activity(self, request):
        pending = pending_task_queryset(request.user)[:50]

        approvals = (
            Approval.objects.filter(acted_by=request.user)
            .select_related(
                "training_record",
                "training_record__learner",
                "training_record__course",
            )
            .order_by("-acted_at", "-id")[:20]
        )
        recent = [
            {
                "id": approval.id,
                "training_record": approval.training_record_id,
                "record": TrainingRecordSerializer(approval.training_record).data,
                "action": approval.action,
                "reason": approval.reason,
                "acted_at": approval.acted_at,
            }
            for approval in approvals
        ]
        return Response(
            {
                "pending": TrainingRecordSerializer(pending, many=True).data,
                "recent": recent,
            }
        )


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
