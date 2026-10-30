from apps.common.enums import RoleCode
from apps.common.views import RoleScopedModelViewSet
from apps.documents import serializers as s
from apps.documents.models import Document

ACCESS = (
    RoleCode.SYSTEM_ADMIN,
    RoleCode.ADMIN,
    RoleCode.FRONT_DESK,
    RoleCode.TRAINING_COORDINATOR,
    RoleCode.ACCOUNTS,
    RoleCode.DUE_DILIGENCE,
    RoleCode.PRINTER,
)


class DocumentViewSet(RoleScopedModelViewSet):
    """M14 — signed URL delivery is deferred to Phase 2; metadata is served now."""

    queryset = Document.objects.all().order_by("-generated_at")
    serializer_class = s.DocumentSerializer
    required_roles = ACCESS
    write_roles = ACCESS
    filterset_fields = ["kind", "owner_type", "owner_id"]
    search_fields = ["object_key", "sha256"]
