from django.conf import settings
from django.db import models

from apps.catalogue.models import Course
from apps.common.enums import BookingState, EnrolmentStatus, SessionStatus
from apps.learners.models import Learner


class Venue(models.Model):
    name = models.CharField(max_length=150)
    address = models.CharField(max_length=255, blank=True, default="")
    capacity = models.IntegerField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "venue"

    def __str__(self) -> str:
        return self.name


class Instructor(models.Model):
    full_name = models.CharField(max_length=150)
    user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="instructor_profiles",
    )
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "instructor"

    def __str__(self) -> str:
        return self.full_name


class CourseSession(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="sessions")
    venue = models.ForeignKey(
        Venue, null=True, blank=True, on_delete=models.SET_NULL, related_name="sessions"
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    capacity = models.IntegerField(null=True, blank=True)
    seats_taken = models.IntegerField(default=0)
    reserve_pct = models.IntegerField(
        default=settings.CAPACITY_RESERVE_PCT,
        help_text="Carry-forward headroom reserved above committed seats (SAD §8.1).",
    )
    status = models.CharField(
        max_length=16, choices=SessionStatus.choices, default=SessionStatus.SCHEDULED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        db_table = "course_session"

    def __str__(self) -> str:
        return f"{self.course_id}@{self.start_date}"


class SessionInstructor(models.Model):
    session = models.ForeignKey(
        CourseSession, on_delete=models.CASCADE, related_name="session_instructors"
    )
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name="+")

    class Meta:
        db_table = "session_instructor"
        constraints = [
            models.UniqueConstraint(
                fields=["session", "instructor"], name="uq_session_instructor"
            )
        ]


class Enrolment(models.Model):
    """Booking record — canonical M5 ``enrolment`` enriched with the approved
    SAD booking lifecycle (``state``, ``requested_session``/``session``/
    ``original_session``, carry-forward timestamps). Design ``04`` §5/§6.
    """

    learner = models.ForeignKey(Learner, on_delete=models.CASCADE, related_name="enrolments")
    requested_session = models.ForeignKey(
        CourseSession,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="requested_enrolments",
    )
    session = models.ForeignKey(
        CourseSession,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="enrolments",
        help_text="Granted (allocated) seat; null until confirmation.",
    )
    original_session = models.ForeignKey(
        CourseSession,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="First granted session before any carry-forward (SAD §8).",
    )
    status = models.CharField(
        max_length=16, choices=EnrolmentStatus.choices, default=EnrolmentStatus.BOOKED
    )
    state = models.CharField(
        max_length=24, choices=BookingState.choices, default=BookingState.REGISTERED
    )
    booking_ref = models.CharField(max_length=32, unique=True, null=True, blank=True)
    seat_allocated_at = models.DateTimeField(null=True, blank=True)
    payment_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        db_table = "enrolment"
        constraints = [
            models.UniqueConstraint(fields=["learner", "session"], name="uq_learner_session")
        ]

    def __str__(self) -> str:
        return f"{self.booking_ref or self.id}"
