from apps.common.enums import RoleCode
from apps.common.views import RoleScopedModelViewSet
from apps.notifications import serializers as s
from apps.notifications.models import Notification, NotificationTemplate

OPS = (RoleCode.SYSTEM_ADMIN, RoleCode.ADMIN)


class NotificationTemplateViewSet(RoleScopedModelViewSet):
    queryset = NotificationTemplate.objects.all().order_by("code")
    serializer_class = s.NotificationTemplateSerializer
    required_roles = OPS
    write_roles = OPS
    filterset_fields = ["channel"]
    search_fields = ["code", "subject"]


class NotificationViewSet(RoleScopedModelViewSet):
    queryset = Notification.objects.all().order_by("-id")
    serializer_class = s.NotificationSerializer
    required_roles = OPS
    write_roles = OPS
    filterset_fields = ["status", "channel", "template_code"]
    search_fields = ["recipient", "template_code"]
