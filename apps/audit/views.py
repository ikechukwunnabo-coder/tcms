from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.audit import serializers as s
from apps.audit.models import AuditEvent
from apps.common.enums import RoleCode
from apps.common.permissions import RolePermission


class AuditEventViewSet(ReadOnlyModelViewSet):
    """M15 — append-only audit trail, readable by System Admin only."""

    queryset = AuditEvent.objects.all().order_by("-at")
    serializer_class = s.AuditEventSerializer
    permission_classes = [RolePermission]
    required_roles = (RoleCode.SYSTEM_ADMIN,)
    write_roles = ()
    filterset_fields = ["action", "entity", "entity_id", "actor"]
    search_fields = ["action", "entity"]
