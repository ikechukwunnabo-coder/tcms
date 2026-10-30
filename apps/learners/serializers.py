from rest_framework import serializers

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
        read_only_fields = ["id", "uploaded_at", "uploaded_by"]


class LearnerSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    contacts = LearnerContactSerializer(many=True, read_only=True)
    documents = LearnerDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Learner
        fields = [
            "id", "badge_no", "surname", "first_name", "middle_name", "sex",
            "birth_date", "nationality", "state", "position", "company", "title",
            "active", "pertype", "full_name", "contacts", "documents",
        ]
        read_only_fields = ["id", "full_name"]
