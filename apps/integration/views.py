from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.common.enums import OutboxStatus, RoleCode
from apps.common.permissions import RolePermission
from apps.common.views import RoleScopedModelViewSet
from apps.integration import serializers as s
from apps.integration.models import ExternalRef, OutboxEvent, SeedMarker, WebhookDelivery

ADMIN_ONLY = (RoleCode.SYSTEM_ADMIN,)


class OutboxEventViewSet(RoleScopedModelViewSet):
    queryset = OutboxEvent.objects.all().order_by("-created_at")
    serializer_class = s.OutboxEventSerializer
    required_roles = ADMIN_ONLY
    write_roles = ADMIN_ONLY
    filterset_fields = ["status", "topic"]

    @action(detail=False, methods=["get"], url_path="health")
    def health(self, request):
        """``/v1/integration/health`` (design ``04`` §4/§6)."""
        pending = OutboxEvent.objects.filter(status=OutboxStatus.PENDING).count()
        failed = OutboxEvent.objects.filter(status=OutboxStatus.FAILED).count()
        return Response(
            {"status": "ok", "service": "tcms", "outbox_pending": pending, "outbox_failed": failed}
        )


class WebhookDeliveryViewSet(ReadOnlyModelViewSet):
    queryset = WebhookDelivery.objects.all().order_by("-id")
    serializer_class = s.WebhookDeliverySerializer
    permission_classes = [RolePermission]
    required_roles = ADMIN_ONLY
    write_roles = ()


class ExternalRefViewSet(RoleScopedModelViewSet):
    queryset = ExternalRef.objects.all().order_by("-id")
    serializer_class = s.ExternalRefSerializer
    required_roles = ADMIN_ONLY
    write_roles = ADMIN_ONLY
    filterset_fields = ["system", "entity", "entity_id"]


class SeedMarkerViewSet(ReadOnlyModelViewSet):
    queryset = SeedMarker.objects.all().order_by("tier", "code")
    serializer_class = s.SeedMarkerSerializer
    permission_classes = [RolePermission]
    required_roles = ADMIN_ONLY
    write_roles = ()
