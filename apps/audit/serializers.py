from rest_framework import serializers

from apps.audit.models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = [
            "id", "actor", "action", "entity", "entity_id", "before", "after", "ip", "at",
        ]
        read_only_fields = fields
