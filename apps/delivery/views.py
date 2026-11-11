import django_filters
from django.db.models import Prefetch
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.certification.models import Certificate, IDCard
from apps.common.enums import RoleCode
from apps.common.views import RoleScopedModelViewSet
from apps.delivery import serializers as s
from apps.delivery.models import (
    DailyMedicalCheck,
    TrainingInstructor,
    TrainingItem,
    TrainingRecord,
)
from apps.portal import cji as cji_svc
from apps.portal.serializers import JoiningInstructionSerializer
from apps.workflow.models import ApprovalHistory

RECORDS = (
    RoleCode.SYSTEM_ADMIN,
    RoleCode.ADMIN,
    RoleCode.FRONT_DESK,
    RoleCode.MEDIC,
    RoleCode.TRAINING_COORDINATOR,
    RoleCode.ACCOUNTS,
    RoleCode.DUE_DILIGENCE,
    RoleCode.MD,
    RoleCode.PRINTER,
    RoleCode.VERIFICATION,
    RoleCode.REPORTS,
)


class TrainingRecordFilter(django_filters.FilterSet):
    status = django_filters.NumberFilter(field_name="status_id")
    start_date_after = django_filters.DateFilter(field_name="start_date", lookup_expr="gte")
    start_date_before = django_filters.DateFilter(field_name="start_date", lookup_expr="lte")

    class Meta:
        model = TrainingRecord
        fields = ["learner", "course", "session", "status"]


class TrainingRecordViewSet(RoleScopedModelViewSet):
    queryset = (
        TrainingRecord.objects.select_related("learner", "course", "status")
        .prefetch_related("items", "training_instructors__module", "medical_checks")
        .order_by("-created_at")
    )
    serializer_class = s.TrainingRecordSerializer
    required_roles = RECORDS
    write_roles = RECORDS
    filterset_class = TrainingRecordFilter
    search_fields = ["learner__badge_no", "learner__surname", "course__course_code"]
    ordering_fields = ["start_date", "created_at"]

    @action(detail=True, methods=["get"])
    def workspace(self, request, pk=None):
        record = (
            self.get_queryset()
            .select_related("enrolment", "enrolment__session", "learner")
            .prefetch_related(
                "learner__contacts",
                "learner__documents",
                "learner__medicals",
                Prefetch(
                    "certificates",
                    queryset=Certificate.objects.select_related(
                        "learner", "training_record__course"
                    ).order_by("-issued_at"),
                ),
                Prefetch(
                    "id_cards",
                    queryset=IDCard.objects.select_related(
                        "learner", "training_record__course"
                    ).order_by("-id"),
                ),
                Prefetch(
                    "status_history",
                    queryset=ApprovalHistory.objects.select_related("status").order_by(
                        "updated_at"
                    ),
                ),
            )
            .get(pk=self.get_object().pk)
        )
        return Response(s.TrainingRecordWorkspaceSerializer(record).data)

    @action(detail=True, methods=["post"], url_path="resend-cji")
    def resend_cji(self, request, pk=None):
        record = self.get_object()
        if not record.enrolment_id:
            return Response(
                {"error": "cji_not_deliverable", "message": "This record has no enrolment."},
                status=400,
            )
        joining_instruction = cji_svc.resend(record.enrolment)
        return Response(JoiningInstructionSerializer(joining_instruction).data)


class TrainingItemViewSet(RoleScopedModelViewSet):
    queryset = TrainingItem.objects.select_related("course_item").order_by("id")
    serializer_class = s.TrainingItemSerializer
    required_roles = RECORDS
    write_roles = RECORDS
    filterset_fields = ["training_record", "course_item", "passed"]


class TrainingInstructorViewSet(RoleScopedModelViewSet):
    queryset = TrainingInstructor.objects.select_related("instructor", "module").order_by("id")
    serializer_class = s.TrainingInstructorSerializer
    required_roles = RECORDS
    write_roles = RECORDS
    filterset_fields = ["training_record", "instructor", "module"]


MEDICAL_WRITE = (RoleCode.SYSTEM_ADMIN, RoleCode.ADMIN, RoleCode.MEDIC)


class DailyMedicalCheckViewSet(RoleScopedModelViewSet):
    queryset = DailyMedicalCheck.objects.select_related("created_by").order_by(
        "check_date", "id"
    )
    serializer_class = s.DailyMedicalCheckSerializer
    required_roles = RECORDS
    write_roles = MEDICAL_WRITE
    filterset_fields = ["training_record"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
