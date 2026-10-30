from rest_framework import serializers

from apps.integration.models import ExternalRef, OutboxEvent, SeedMarker, WebhookDelivery


class OutboxEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboxEvent
        fields = [
            "id", "topic", "payload", "status", "attempts",
            "created_at", "processed_at", "error",
        ]
        read_only_fields = ["id", "created_at", "attempts"]


class WebhookDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookDelivery
        fields = ["id", "event", "url", "status", "attempts", "last_error"]


class ExternalRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalRef
        fields = ["id", "system", "entity", "entity_id", "external_id"]


class SeedMarkerSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeedMarker
        fields = ["id", "tier", "code", "applied_at"]
