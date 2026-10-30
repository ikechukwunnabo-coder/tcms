"""Portal auth views — public registration & email verification (design ``04`` §5.1)."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.certification import services as cert_svc
from apps.certification.serializers import CertificateBatchSerializer
from apps.portal import cji as cji_svc
from apps.portal import serializers as s
from apps.portal import services as svc
from apps.scheduling.models import Enrolment


class RegisterRateThrottle(AnonRateThrottle):
    """Limit self-service registration attempts per source address."""

    scope = "register"


@extend_schema(request=s.RegisterSerializer, responses={201: None})
@api_view(["POST"])
@throttle_classes([RegisterRateThrottle])
@permission_classes([AllowAny])
def register(request):
    """Register an individual learner; sends a verification email (BR-1/BR-15)."""
    serializer = s.RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    svc.register_individual(**serializer.validated_data)
    return Response(
        {"detail": "registration received; check your email to verify"},
        status=status.HTTP_201_CREATED,
    )


@extend_schema(request=s.VerifyEmailSerializer, responses={200: s.PortalAccountSerializer})
@api_view(["POST"])
@permission_classes([AllowAny])
def verify_email(request):
    """Consume a single-use token; verifies the email and creates the learner."""
    serializer = s.VerifyEmailSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    account = svc.verify_email(serializer.validated_data["token"])
    return Response(s.PortalAccountSerializer(account).data)


@extend_schema(request=s.ResendVerificationSerializer, responses={200: None})
@api_view(["POST"])
@permission_classes([AllowAny])
def resend_verification(request):
    """Re-send the verification email (rate-limited; no account enumeration)."""
    serializer = s.ResendVerificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    svc.resend_verification(serializer.validated_data["email"])
    return Response({"detail": "if the address is registered and unverified, a new link was sent"})


# ── Corporate accounts & nominees (design ``04`` §5.2, spec §9.6) ─────────────


@extend_schema(
    operation_id="portal_corporate_account_create",
    request=s.CorporateAccountCreateSerializer,
    responses={201: s.PortalCorporateAccountReadSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def corporate_account_create(request):
    """Register the authenticated lead's corporate account (spec §9.6)."""
    serializer = s.CorporateAccountCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    account = svc.create_corporate_account(request.user, **serializer.validated_data)
    return Response(
        s.PortalCorporateAccountReadSerializer(account).data, status=status.HTTP_201_CREATED
    )


@extend_schema(
    request=s.NomineeWriteSerializer,
    responses={200: s.NomineeSerializer(many=True), 201: s.NomineeSerializer},
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def nominees(request):
    """List or add nominees under the lead's corporate account (BR-16)."""
    account = svc.get_lead_account(request.user)
    if request.method == "GET":
        qs = account.nominees.order_by("surname", "first_name")
        return Response(s.NomineeSerializer(qs, many=True).data)
    serializer = s.NomineeWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    learner = svc.add_nominee(account, **serializer.validated_data)
    return Response(s.NomineeSerializer(learner).data, status=status.HTTP_201_CREATED)


@extend_schema(request=s.NomineeUpdateSerializer, responses={200: s.NomineeSerializer})
@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def nominee_detail(request, pk):
    """Edit or remove a nominee (removal blocked if a seat is held, BR-16)."""
    account = svc.get_lead_account(request.user)
    learner = get_object_or_404(account.nominees, pk=pk)
    if request.method == "DELETE":
        svc.remove_nominee(learner)
        return Response(status=status.HTTP_204_NO_CONTENT)
    serializer = s.NomineeUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    learner = svc.update_nominee(learner, **serializer.validated_data)
    return Response(s.NomineeSerializer(learner).data)


# ── Course Joining Instructions (CJI) (spec §9.7, BR-20) ─────────────────────


@extend_schema(responses={200: s.JoiningInstructionSerializer})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def booking_cji(request, pk):
    """The current CJI for the caller's booking (learner or corporate lead)."""
    enrolment = get_object_or_404(Enrolment, pk=pk)
    cji_svc.assert_access(request.user, enrolment)
    ji = cji_svc.current_for(enrolment)
    if ji is None:
        return Response(
            {"error": "cji_not_found", "message": "no CJI has been issued yet"},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(s.JoiningInstructionSerializer(ji).data)


@extend_schema(request=None, responses={200: s.JoiningInstructionSerializer})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def booking_cji_resend(request, pk):
    """Re-render and re-send the current CJI (learner or corporate lead)."""
    enrolment = get_object_or_404(Enrolment, pk=pk)
    cji_svc.assert_access(request.user, enrolment)
    ji = cji_svc.resend(enrolment)
    return Response(s.JoiningInstructionSerializer(ji).data)


# ── Corporate certificate bundle (BR-17a) ────────────────────────────────────


@extend_schema(request=None, responses={200: CertificateBatchSerializer})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def corporate_certificate_bundle(request):
    """Assemble and email the corporate ZIP bundle to the lead."""
    account = svc.get_lead_account(request.user)
    batch = cert_svc.bundle_for_account(account, actor=request.user)
    return Response(CertificateBatchSerializer(batch).data)


@extend_schema(responses={200: CertificateBatchSerializer(many=True)})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def corporate_certificate_batches(request):
    """List certificate ZIP batches for the lead's account."""
    account = svc.get_lead_account(request.user)
    qs = account.certificate_batches.order_by("-created_at")
    return Response(CertificateBatchSerializer(qs, many=True).data)
