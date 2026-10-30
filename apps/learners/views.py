from apps.common.enums import RoleCode
from apps.common.views import RoleScopedModelViewSet
from apps.learners import serializers as s
from apps.learners.models import Learner, LearnerContact, LearnerDocument

MANAGE = (
    RoleCode.SYSTEM_ADMIN,
    RoleCode.ADMIN,
    RoleCode.FRONT_DESK,
    RoleCode.TRAINING_COORDINATOR,
    RoleCode.ACCOUNTS,
    RoleCode.DUE_DILIGENCE,
    RoleCode.PRINTER,
)


class LearnerViewSet(RoleScopedModelViewSet):
    queryset = Learner.objects.all().prefetch_related("contacts", "documents").order_by("surname")
    serializer_class = s.LearnerSerializer
    required_roles = MANAGE
    write_roles = MANAGE
    filterset_fields = ["active", "company", "nationality", "state"]
    search_fields = ["badge_no", "surname", "first_name"]
    ordering_fields = ["surname", "badge_no", "created_at"]


class LearnerContactViewSet(RoleScopedModelViewSet):
    queryset = LearnerContact.objects.all().order_by("id")
    serializer_class = s.LearnerContactSerializer
    required_roles = MANAGE
    write_roles = MANAGE
    filterset_fields = ["learner", "contact_type", "is_primary"]


class LearnerDocumentViewSet(RoleScopedModelViewSet):
    queryset = LearnerDocument.objects.all().order_by("-uploaded_at")
    serializer_class = s.LearnerDocumentSerializer
    required_roles = MANAGE
    write_roles = MANAGE
    filterset_fields = ["learner", "kind"]
