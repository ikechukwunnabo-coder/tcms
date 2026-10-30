from rest_framework import serializers

from apps.delivery.models import TrainingInstructor, TrainingItem, TrainingRecord


class TrainingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingItem
        fields = ["id", "training_record", "course_item", "passed", "score"]


class TrainingInstructorSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingInstructor
        fields = ["id", "training_record", "instructor"]


class TrainingRecordSerializer(serializers.ModelSerializer):
    learner_name = serializers.CharField(source="learner.full_name", read_only=True)
    badge_no = serializers.CharField(source="learner.badge_no", read_only=True)
    course_code = serializers.CharField(source="course.course_code", read_only=True)
    status_code = serializers.CharField(source="status.code", read_only=True)
    items = TrainingItemSerializer(many=True, read_only=True)

    class Meta:
        model = TrainingRecord
        fields = [
            "id", "learner", "learner_name", "badge_no", "course", "course_code",
            "session", "enrolment", "start_date", "end_date", "prev_expiry",
            "status", "status_code", "reject_reason", "instructor", "items",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "status", "reject_reason"]
