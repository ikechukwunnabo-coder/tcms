from rest_framework import serializers

from apps.documents.models import Document


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = [
            "id", "kind", "owner_type", "owner_id", "object_key", "mime",
            "size_bytes", "sha256", "generated_at", "generated_by",
        ]
        read_only_fields = ["id", "generated_at", "generated_by"]
