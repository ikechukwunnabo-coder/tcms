from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.enums import RoleCode
from apps.common.permissions import ANY_ROLE
from apps.common.views import RoleScopedModelViewSet
from apps.portal import cji as cji_svc
from apps.portal.serializers import JoiningInstructionSerializer
from apps.scheduling import serializers as s
from apps.scheduling import services as svc
from apps.scheduling.models import CourseSession, Enrolment, Instructor, Venue

WRITE = (RoleCode.SYSTEM_ADMIN, RoleCode.ADMIN, RoleCode.TRAINING_COORDINATOR)
# Payment verification / seat allocation is owned by the Account Department (SAD §9).
ENROLMENT_WRITE = WRITE + (RoleCode.ACCOUNTS,)
# Front Desk may resend a current CJI (spec §9.7).
CJI_WRITE = ENROLMENT_WRITE + (RoleCode.FRONT_DESK,)


class VenueViewSet(RoleScopedModelViewSet):
    queryset = Venue.objects.all().order_by("name")
    serializer_class = s.VenueSerializer
    required_roles = ANY_ROLE
    write_roles = WRITE
    filterset_fields = ["active"]
    search_fields = ["name", "address"]


class InstructorViewSet(RoleScopedModelViewSet):
    queryset = Instructor.objects.all().order_by("full_name")
    serializer_class = s.InstructorSerializer
    required_roles = ANY_ROLE
    write_roles = WRITE
    filterset_fields = ["active"]
    search_fields = ["full_name"]


class CourseSessionViewSet(RoleScopedModelViewSet):
    queryset = CourseSession.objects.select_related("course", "venue").order_by("-start_date")
    serializer_class = s.CourseSessionSerializer
    required_roles = ANY_ROLE
    write_roles = WRITE
    filterset_fields = ["course", "venue", "status", "start_date"]
    search_fields = ["course__course_code", "course__name"]
    ordering_fields = ["start_date", "end_date"]

    @action(detail=True, methods=["get"])
    def availability(self, request, pk=None):
        """Seat availability for a session (SAD §3 Layer 3)."""
        return Response(svc.availability(self.get_object()))


class EnrolmentViewSet(RoleScopedModelViewSet):
    queryset = Enrolment.objects.select_related(
        "learner", "requested_session", "session"
    ).order_by("-created_at")
    serializer_class = s.EnrolmentSerializer
    required_roles = ANY_ROLE
    write_roles = ENROLMENT_WRITE
    filterset_fields = ["learner", "session", "requested_session", "status", "state"]
    search_fields = ["booking_ref", "learner__badge_no", "learner__surname"]

    def create(self, request, *args, **kwargs):
        """Create a booking request through the domain service (booking ref,
        initial state, creator and overbooking checks)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = serializer.validated_data.get("requested_session")
        if session is None:
            return Response(
                {
                    "error": "requested_session_required",
                    "message": "Choose the session the learner is booking.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        enrolment = svc.book(
            serializer.validated_data["learner"],
            session,
            created_by=request.user,
        )
        return Response(
            self.get_serializer(enrolment).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """Verify payment and secure a seat, with auto carry-forward (SAD §8)."""
        enrolment = svc.confirm(self.get_object(), verified_by=request.user)
        return Response(self.get_serializer(enrolment).data)

    def get_permissions(self):
        if self.action == "cji_resend":
            self.write_roles = CJI_WRITE
        return super().get_permissions()

    @action(detail=True, methods=["get"], url_path="cji")
    def cji(self, request, pk=None):
        """Current Course Joining Instructions for this booking (spec §9.7)."""
        ji = cji_svc.current_for(self.get_object())
        if ji is None:
            return Response(
                {"error": "cji_not_found", "message": "no CJI has been issued yet"},
                status=404,
            )
        return Response(JoiningInstructionSerializer(ji).data)

    @action(detail=True, methods=["post"], url_path="cji/resend")
    def cji_resend(self, request, pk=None):
        """Re-render and re-send the current CJI (Front Desk, spec §9.7)."""
        ji = cji_svc.resend(self.get_object())
        return Response(JoiningInstructionSerializer(ji).data)
