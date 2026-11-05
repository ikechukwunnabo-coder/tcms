from rest_framework import serializers

from apps.documents.models import Document


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    kind = serializers.CharField(max_length=32)
    owner_type = serializers.CharField(max_length=64, required=False, allow_blank=True)
    owner_id = serializers.IntegerField(required=False, allow_null=True)


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id", "kind", "owner_type", "owner_id", "object_key", "mime",
            "size_bytes", "sha256", "generated_at", "generated_by",
        ]
        read_only_fields = ["id", "generated_at", "generated_by"]
