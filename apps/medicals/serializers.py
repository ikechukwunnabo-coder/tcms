from rest_framework import serializers

from apps.medicals.models import Medical


class MedicalSerializer(serializers.ModelSerializer):
    learner_name = serializers.CharField(source="learner.full_name", read_only=True)
    badge_no = serializers.CharField(source="learner.badge_no", read_only=True)

    class Meta:
        model = Medical
        fields = [
            "id", "learner", "learner_name", "badge_no", "record_no", "issued_date",
            "expiry_date", "systolic", "diastolic", "fitness", "active", "document",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "learner_name", "badge_no"]
