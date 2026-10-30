from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.certification import serializers as s
from apps.certification import services as cert_service
from apps.certification.models import Certificate, CertificateSequence, IDCard
from apps.common.enums import RoleCode
from apps.common.views import RoleScopedModelViewSet, RoleScopedReadOnlyModelViewSet
from apps.delivery.models import TrainingRecord

READ = (
    RoleCode.SYSTEM_ADMIN,
    RoleCode.ADMIN,
    RoleCode.FRONT_DESK,
    RoleCode.TRAINING_COORDINATOR,
    RoleCode.ACCOUNTS,
    RoleCode.DUE_DILIGENCE,
    RoleCode.PRINTER,
)
WRITE = (RoleCode.SYSTEM_ADMIN, RoleCode.ADMIN, RoleCode.PRINTER)
MD = (RoleCode.SYSTEM_ADMIN, RoleCode.MD)
ADMIN = (RoleCode.SYSTEM_ADMIN, RoleCode.ADMIN)


class CertificateViewSet(RoleScopedReadOnlyModelViewSet):
    queryset = Certificate.objects.select_related("learner").order_by("-issued_at")
    serializer_class = s.CertificateSerializer
    required_roles = READ
    write_roles = WRITE
    filterset_fields = ["learner", "training_record", "format", "voided_at"]
    search_fields = ["certificate_no", "learner__badge_no", "learner__surname"]

    @action(detail=False, methods=["post"], url_path="issue")
    def issue(self, request):
        """R-CERT-02/04: allocate a number and create the certificate (gated)."""
        payload = s.IssueCertificateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        record = get_object_or_404(TrainingRecord, pk=payload.validated_data["training_record"])
        certificate = cert_service.issue_certificate(record, actor=request.user)
        return Response(s.CertificateSerializer(certificate).data, status=201)

    @action(detail=True, methods=["post"], url_path="md-approve")
    def md_approve(self, request, pk=None):
        """R-WF-07 stage-2 (gap G2): apply digital signature + seal."""
        certificate = self.get_object()
        cert_service.apply_signature_and_seal(certificate, actor=request.user)
        certificate.refresh_from_db()
        return Response(s.CertificateSerializer(certificate).data)

    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        """BR-17: dispatch the certificate and schedule its expiry reminders."""
        certificate = self.get_object()
        cert_service.release(certificate, actor=request.user)
        certificate.refresh_from_db()
        return Response(s.CertificateSerializer(certificate).data)

    @action(detail=True, methods=["get"])
    def reminders(self, request, pk=None):
        """Scheduled expiry reminders for a certificate (§9.9)."""
        certificate = self.get_object()
        rows = certificate.reminders.order_by("offset_days")
        return Response(s.CertificateReminderSerializer(rows, many=True).data)

    @action(detail=True, methods=["post"], url_path="remind")
    def remind(self, request, pk=None):
        """Send an immediate expiry reminder to the owner (§9.9)."""
        certificate = self.get_object()
        result = cert_service.send_reminder_now(certificate, actor=request.user)
        return Response(s.ReminderResultSerializer(result).data)

    @action(detail=True, methods=["post"])
    def renew(self, request, pk=None):
        """Request renewal for an eligible certificate (R-REN-01/02/03)."""
        certificate = self.get_object()
        payload = s.RenewalRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        record = cert_service.request_renewal(
            certificate, session_id=payload.validated_data.get("session_id"), actor=request.user
        )
        return Response(
            {
                "training_record_id": record.pk,
                "enrolment_id": getattr(record, "enrolment_id", None),
            },
            status=201,
        )

    def get_permissions(self):
        if self.action == "md_approve":
            self.write_roles = MD
        elif self.action in ("release", "remind"):
            self.write_roles = ADMIN
        return super().get_permissions()


class CertificateSequenceViewSet(RoleScopedModelViewSet):
    queryset = CertificateSequence.objects.all().order_by("course_year", "item_id")
    serializer_class = s.CertificateSequenceSerializer
    required_roles = (RoleCode.SYSTEM_ADMIN,)
    write_roles = (RoleCode.SYSTEM_ADMIN,)
    filterset_fields = ["course_year", "item_id"]


class IDCardViewSet(RoleScopedModelViewSet):
    queryset = IDCard.objects.all().order_by("-printed_at")
    serializer_class = s.IDCardSerializer
    required_roles = READ
    write_roles = WRITE
    filterset_fields = ["learner", "training_record"]
    search_fields = ["card_no", "learner__badge_no"]
