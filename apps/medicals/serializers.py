from rest_framework import serializers

from apps.medicals.models import Medical


class MedicalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medical
        fields = [
            "id", "learner", "record_no", "issued_date", "expiry_date",
            "systolic", "diastolic", "fitness", "active", "document", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
