from io import BytesIO

from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import get_valid_filename
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


def _pdf_response(data: bytes, filename: str, *, head: bool = False):
    safe = get_valid_filename(filename) or "document.pdf"
    headers = {
        "Content-Disposition": f'attachment; filename="{safe}"',
        "Content-Length": str(len(data)),
    }
    if head:
        return HttpResponse(headers=headers, content_type="application/pdf")
    return FileResponse(
        BytesIO(data),
        content_type="application/pdf",
        as_attachment=True,
        filename=safe,
    )


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
        certificate = cert_service.issue_certificate(
            record,
            actor=request.user,
            certificate_no=payload.validated_data.get("certificate_no", ""),
            opito_learner_id=payload.validated_data.get("opito_learner_id", ""),
        )
        return Response(s.CertificateSerializer(certificate).data, status=201)

    @action(detail=True, methods=["get", "head"])
    def document(self, request, pk=None):
        """Return the generated or uploaded certificate PDF."""
        certificate = self.get_object()
        data = cert_service.certificate_document_bytes(certificate, actor=request.user)
        return _pdf_response(
            data,
            f"{certificate.certificate_no}.pdf",
            head=request.method == "HEAD",
        )

    @action(detail=True, methods=["post"])
    def generate(self, request, pk=None):
        certificate = self.get_object()
        cert_service.generate_certificate_document(certificate, actor=request.user)
        certificate.refresh_from_db()
        return Response(s.CertificateSerializer(certificate).data)

    @action(detail=True, methods=["post"])
    def upload(self, request, pk=None):
        certificate = self.get_object()
        payload = s.CertificateUploadSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        cert_service.upload_certificate_document(
            certificate,
            payload.validated_data["file"],
            actor=request.user,
            certificate_no=payload.validated_data.get("certificate_no", ""),
            opito_learner_id=payload.validated_data.get("opito_learner_id", ""),
        )
        certificate.refresh_from_db()
        return Response(s.CertificateSerializer(certificate).data)

    @action(detail=True, methods=["post"])
    def print(self, request, pk=None):
        certificate = self.get_object()
        cert_service.mark_certificate_printed(certificate, actor=request.user)
        certificate.refresh_from_db()
        return Response(s.CertificateSerializer(certificate).data)

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
    queryset = IDCard.objects.select_related("learner", "training_record").order_by("-printed_at")
    serializer_class = s.IDCardSerializer
    required_roles = READ
    write_roles = WRITE
    filterset_fields = ["learner", "training_record"]
    search_fields = ["card_no", "learner__badge_no"]

    @action(detail=False, methods=["post"], url_path="issue")
    def issue(self, request):
        payload = s.IssueIdCardSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        record = get_object_or_404(TrainingRecord, pk=payload.validated_data["training_record"])
        card = cert_service.issue_id_card(record, actor=request.user)
        return Response(s.IDCardSerializer(card).data, status=201)

    @action(detail=True, methods=["get", "head"])
    def document(self, request, pk=None):
        card = self.get_object()
        data = cert_service.id_card_document_bytes(card, actor=request.user)
        return _pdf_response(data, f"{card.card_no}.pdf", head=request.method == "HEAD")

    @action(detail=True, methods=["post"])
    def generate(self, request, pk=None):
        card = self.get_object()
        cert_service.generate_id_card_document(card, actor=request.user)
        card.refresh_from_db()
        return Response(s.IDCardSerializer(card).data)

    @action(detail=True, methods=["post"])
    def print(self, request, pk=None):
        card = self.get_object()
        cert_service.mark_id_card_printed(card, actor=request.user)
        card.refresh_from_db()
        return Response(s.IDCardSerializer(card).data)

    @action(detail=True, methods=["post"])
    def reprint(self, request, pk=None):
        card = self.get_object()
        cert_service.generate_id_card_document(card, actor=request.user)
        card.refresh_from_db()
        return Response(s.IDCardSerializer(card).data)
