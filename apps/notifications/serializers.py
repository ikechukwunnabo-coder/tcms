from rest_framework import serializers

from apps.notifications.models import Notification, NotificationTemplate


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = ["id", "code", "channel", "subject", "body"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id", "template_code", "recipient", "channel", "payload",
            "status", "sent_at", "error",
        ]
        read_only_fields = ["id", "sent_at"]
