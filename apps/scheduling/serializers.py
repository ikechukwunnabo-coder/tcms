from rest_framework import serializers

from apps.scheduling import services as svc
from apps.scheduling.models import CourseSession, Enrolment, Instructor, Venue


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ["id", "name", "address", "capacity", "active"]


class InstructorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instructor
        fields = ["id", "full_name", "user", "active"]


class CourseSessionSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source="course.name", read_only=True)
    course_code = serializers.CharField(source="course.course_code", read_only=True)
    seats_available = serializers.SerializerMethodField()

    class Meta:
        model = CourseSession
        fields = [
            "id", "course", "course_name", "course_code", "venue", "start_date", "end_date",
            "capacity", "seats_taken", "seats_available", "reserve_pct", "status",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "seats_taken", "seats_available"]

    def get_seats_available(self, obj) -> int | None:
        return svc.seats_available(obj)


class EnrolmentSerializer(serializers.ModelSerializer):
    course = serializers.IntegerField(source="requested_session.course_id", read_only=True)
    learner_name = serializers.CharField(source="learner.full_name", read_only=True)
    badge_no = serializers.CharField(source="learner.badge_no", read_only=True)
    course_code = serializers.CharField(
        source="requested_session.course.course_code", read_only=True
    )
    session_start = serializers.DateField(source="requested_session.start_date", read_only=True)
    granted_start = serializers.DateField(source="session.start_date", read_only=True)

    class Meta:
        model = Enrolment
        fields = [
            "id", "learner", "learner_name", "badge_no", "course", "course_code",
            "requested_session", "session", "original_session", "session_start",
            "granted_start", "status", "state", "booking_ref", "seat_allocated_at",
            "payment_verified_at", "created_at",
        ]
        read_only_fields = [
            "id", "session", "original_session", "state", "booking_ref",
            "seat_allocated_at", "payment_verified_at", "created_at",
        ]


class BookingCreateSerializer(serializers.Serializer):
    """``POST /bookings`` request body (design ``04`` §5.3)."""

    learner = serializers.IntegerField()
    requested_session = serializers.IntegerField()
