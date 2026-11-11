from datetime import date
from io import BytesIO

from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import default_storage
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import get_valid_filename
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.certification import opito
from apps.certification import opito_serializers as os
from apps.certification import serializers as s
from apps.certification import services as cert_service
from apps.certification.models import Certificate, CertificateSequence, IDCard, OpitoFile
from apps.certification.verification import CertificateVerificationNotFound
from apps.certification.verification import verify_certificate as verify_certificate_record
from apps.common.enums import RoleCode
from apps.common.permissions import RolePermission
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


class CertificateVerifyThrottle(AnonRateThrottle):
    scope = "verify"


@extend_schema(responses={200: s.CertificateVerificationSerializer})
@api_view(["GET"])
@authentication_classes([])
@throttle_classes([CertificateVerifyThrottle])
@permission_classes([AllowAny])
def verify_certificate(request, identifier):
    """Public certificate check by certificate number or training-record id."""
    try:
        result = verify_certificate_record(identifier)
    except CertificateVerificationNotFound:
        return Response(
            {"error": "not_found", "message": "Certificate not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(s.CertificateVerificationSerializer(result).data)


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


class OpitoFileViewSet(viewsets.GenericViewSet):
    """OPITO CSV cohorts: list, validate, preview content, generate and download."""

    queryset = OpitoFile.objects.select_related("course")
    serializer_class = os.OpitoFileSerializer
    permission_classes = [RolePermission]
    required_roles = READ
    write_roles = WRITE

    @staticmethod
    def _cohort_params(request):
        raw_course = request.query_params.get("course")
        raw_date = request.query_params.get("start_date") or request.query_params.get("date")
        if raw_course in (None, ""):
            raise ValidationError({"course": "This query parameter is required."})
        if raw_date in (None, ""):
            raise ValidationError({"start_date": "This query parameter is required."})
        try:
            course_id = int(raw_course)
        except (TypeError, ValueError) as exc:
            raise ValidationError({"course": "A valid course id is required."}) from exc
        try:
            start_date = date.fromisoformat(raw_date)
        except (TypeError, ValueError) as exc:
            raise ValidationError({"start_date": "Use YYYY-MM-DD."}) from exc
        try:
            course = opito.get_opito_course(course_id)
        except opito.OpitoCohortError as exc:
            raise ValidationError({"course": str(exc)}) from exc
        return course, start_date

    def _cohort_response(self):
        rows = opito.opito_cohorts()
        data = os.OpitoCohortSerializer(rows, many=True).data
        return Response({"data": data, "total": len(data)})

    def list(self, request):
        return self._cohort_response()

    @action(detail=False, methods=["get"], url_path="file")
    def file(self, request):
        return self._cohort_response()

    @action(detail=False, methods=["get"], url_path="validate-vantage")
    def validate_vantage(self, request):
        course, start_date = self._cohort_params(request)
        missing = opito.missing_vantage_ids(course, start_date)
        return Response(
            os.OpitoValidateSerializer(
                {"valid": not missing, "missingVantageIds": missing}
            ).data
        )

    @action(detail=False, methods=["get"])
    def content(self, request):
        course, start_date = self._cohort_params(request)
        try:
            rows = opito.opito_rows(course, start_date)
        except opito.OpitoCohortError as exc:
            raise ValidationError(str(exc)) from exc
        data = os.OpitoContentRowSerializer(rows, many=True).data
        return Response(os.OpitoContentSerializer({"rows": data, "count": len(data)}).data)

    @action(detail=False, methods=["post"])
    def generate(self, request):
        payload = os.OpitoGenerateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            course = opito.get_opito_course(payload.validated_data["course"])
            generated = opito.generate_opito_file(
                course,
                payload.validated_data["start_date"],
                actor=request.user,
            )
        except opito.OpitoCohortError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(
            os.OpitoFileSerializer(generated, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="csv")
    def csv(self, request):
        return self.generate(request)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        generated = self.get_object()
        if not generated.object_key:
            raise ValidationError({"detail": "No CSV has been generated for this cohort."})
        try:
            handle = default_storage.open(generated.object_key, "rb")
        except (FileNotFoundError, SuspiciousFileOperation, OSError) as exc:
            raise ValidationError({"detail": "The generated CSV is no longer available."}) from exc
        filename = f"OPITO_{generated.course.course_code}_{generated.start_date.isoformat()}.csv"
        return FileResponse(
            handle,
            content_type="text/csv",
            as_attachment=True,
            filename=filename,
        )
