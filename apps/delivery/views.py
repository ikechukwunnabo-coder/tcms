from apps.common.enums import RoleCode
from apps.common.views import RoleScopedModelViewSet
from apps.delivery import serializers as s
from apps.delivery.models import TrainingInstructor, TrainingItem, TrainingRecord

RECORDS = (
    RoleCode.SYSTEM_ADMIN,
    RoleCode.ADMIN,
    RoleCode.FRONT_DESK,
    RoleCode.TRAINING_COORDINATOR,
    RoleCode.ACCOUNTS,
    RoleCode.DUE_DILIGENCE,
    RoleCode.PRINTER,
)


class TrainingRecordViewSet(RoleScopedModelViewSet):
    queryset = (
        TrainingRecord.objects.select_related("learner", "course", "status")
        .prefetch_related("items")
        .order_by("-created_at")
    )
    serializer_class = s.TrainingRecordSerializer
    required_roles = RECORDS
    write_roles = RECORDS
    filterset_fields = ["learner", "course", "session", "status"]
    search_fields = ["learner__badge_no", "learner__surname", "course__course_code"]
    ordering_fields = ["start_date", "created_at"]


class TrainingItemViewSet(RoleScopedModelViewSet):
    queryset = TrainingItem.objects.select_related("course_item").order_by("id")
    serializer_class = s.TrainingItemSerializer
    required_roles = RECORDS
    write_roles = RECORDS
    filterset_fields = ["training_record", "course_item", "passed"]


class TrainingInstructorViewSet(RoleScopedModelViewSet):
    queryset = TrainingInstructor.objects.all().order_by("id")
    serializer_class = s.TrainingInstructorSerializer
    required_roles = RECORDS
    write_roles = RECORDS
    filterset_fields = ["training_record", "instructor"]
