from uuid import uuid4

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import FileResponse, Http404
from django.utils.text import get_valid_filename
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import write_audit
from apps.common.enums import RoleCode
from apps.common.views import RoleScopedModelViewSet
from apps.documents import services as doc_service
from apps.learners import serializers as s
from apps.learners.models import Learner, LearnerContact, LearnerDocument

MANAGE = (
    RoleCode.SYSTEM_ADMIN,
    RoleCode.ADMIN,
    RoleCode.FRONT_DESK,
    RoleCode.TRAINING_COORDINATOR,
    RoleCode.ACCOUNTS,
    RoleCode.DUE_DILIGENCE,
    RoleCode.PRINTER,
)


class LearnerViewSet(RoleScopedModelViewSet):
    queryset = Learner.objects.all().prefetch_related("contacts", "documents").order_by("surname")
    serializer_class = s.LearnerSerializer
    required_roles = MANAGE
    write_roles = MANAGE
    filterset_fields = ["active", "company", "nationality", "state"]
    search_fields = ["badge_no", "surname", "first_name"]
    ordering_fields = ["surname", "badge_no", "created_at"]


class LearnerContactViewSet(RoleScopedModelViewSet):
    queryset = LearnerContact.objects.all().order_by("id")
    serializer_class = s.LearnerContactSerializer
    required_roles = MANAGE
    write_roles = MANAGE
    filterset_fields = ["learner", "contact_type", "is_primary"]


class LearnerDocumentViewSet(RoleScopedModelViewSet):
    queryset = LearnerDocument.objects.all().order_by("-uploaded_at")
    serializer_class = s.LearnerDocumentSerializer
    required_roles = MANAGE
    write_roles = MANAGE
    filterset_fields = ["learner", "kind"]

    @action(detail=False, methods=["post"])
    def upload(self, request):
        payload = s.LearnerDocumentUploadSerializer(data=request.data)
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

        learner = payload.validated_data["learner"]
        kind = payload.validated_data["kind"]
        name = get_valid_filename(upload.name or "document")
        key = f"learner-documents/{learner.id}/{kind}/{uuid4().hex}_{name}"
        with transaction.atomic():
            stored = doc_service.store_bytes(
                kind=kind,
                owner_type="learner",
                owner_id=learner.id,
                key=key,
                data=upload.read(),
                mime=upload.content_type or "application/octet-stream",
                actor=request.user,
            )
            document = LearnerDocument.objects.create(
                learner=learner,
                kind=kind,
                object_key=stored.object_key,
                mime=stored.mime,
                size_bytes=stored.size_bytes,
                uploaded_by=request.user,
            )
            write_audit(
                action="learners.document_uploaded",
                entity="learner_document",
                entity_id=document.pk,
                after={
                    "learner": learner.id,
                    "kind": kind,
                    "object_key": stored.object_key,
                },
            )
        return Response(
            s.LearnerDocumentSerializer(document).data, status=status.HTTP_201_CREATED
        )

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
