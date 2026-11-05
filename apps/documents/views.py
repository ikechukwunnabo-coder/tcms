from uuid import uuid4

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.utils.text import get_valid_filename
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.enums import RoleCode
from apps.common.views import RoleScopedModelViewSet
from apps.documents import serializers as s
from apps.documents import services as doc_service
from apps.documents.models import Document

ACCESS = (
    RoleCode.SYSTEM_ADMIN,
    RoleCode.ADMIN,
    RoleCode.FRONT_DESK,
    RoleCode.TRAINING_COORDINATOR,
    RoleCode.ACCOUNTS,
    RoleCode.DUE_DILIGENCE,
    RoleCode.PRINTER,
)


class DocumentViewSet(RoleScopedModelViewSet):
    """M14 — stored artefact metadata plus upload/download primitives."""

    queryset = Document.objects.all().order_by("-generated_at")
    serializer_class = s.DocumentSerializer
    required_roles = ACCESS
    write_roles = ACCESS
    filterset_fields = ["kind", "owner_type", "owner_id"]
    search_fields = ["object_key", "sha256"]

    @action(detail=False, methods=["post"])
    def upload(self, request):
        payload = s.DocumentUploadSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        upload = payload.validated_data["file"]
        limit = int(getattr(settings, "DOCUMENT_UPLOAD_MAX_BYTES", 10 * 1024 * 1024))
        if upload.size > limit:
            return Response(
                {
                    "error": "document_too_large",
                    "message": f"Documents must be {limit} bytes or smaller.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        kind = payload.validated_data["kind"]
        name = get_valid_filename(upload.name or "document")
        key = f"documents/{kind}/{uuid4().hex}_{name}"
        document = doc_service.store_bytes(
            kind=kind,
            owner_type=payload.validated_data.get("owner_type", ""),
            owner_id=payload.validated_data.get("owner_id"),
            key=key,
            data=upload.read(),
            mime=upload.content_type or "application/octet-stream",
            actor=request.user,
        )
        return Response(s.DocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "head"])
    def download(self, request, pk=None):
        document = self.get_object()
        if not doc_service.exists(document.object_key):
            raise Http404("document file not found")
        handle = default_storage.open(document.object_key, "rb")
        return FileResponse(
            handle,
            content_type=document.mime or "application/octet-stream",
            as_attachment=True,
            filename=document.object_key.rsplit("/", 1)[-1],
        )
