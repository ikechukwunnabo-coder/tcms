from rest_framework import serializers

from apps.common.enums import DocumentKind
from apps.learners.models import Learner, LearnerContact, LearnerDocument


class LearnerContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearnerContact
        fields = ["id", "learner", "contact_type", "value", "is_primary"]


class LearnerDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearnerDocument
        fields = [
            "id", "learner", "kind", "object_key", "mime", "size_bytes",
            "uploaded_at", "uploaded_by", "verified_at",
        ]
        read_only_fields = [
            "id", "object_key", "mime", "size_bytes", "uploaded_at",
            "uploaded_by",
        ]


class LearnerDocumentUploadSerializer(serializers.Serializer):
    learner = serializers.PrimaryKeyRelatedField(queryset=Learner.objects.all())
    kind = serializers.ChoiceField(choices=DocumentKind.choices)
    file = serializers.FileField()


class LearnerLinkSerializer(serializers.ModelSerializer):
    """Minimal learner payload for HR employee linking (no documents)."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Learner
        fields = [
            "id", "badge_no", "surname", "first_name", "middle_name",
            "full_name", "company", "position", "active",
        ]


class LearnerSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    contacts = LearnerContactSerializer(many=True, read_only=True)
    documents = LearnerDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Learner
        fields = [
            "id", "badge_no", "surname", "first_name", "middle_name", "sex",
            "birth_date", "nationality", "state", "position", "company", "title",
            "active", "pertype", "vantage_id", "full_name", "contacts", "documents",
        ]
        read_only_fields = ["id", "full_name"]
