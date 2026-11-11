"""Backup API matching the observable Axis backup console."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import write_audit
from apps.common.backup import create_backup, test_backup_storage
from apps.common.enums import RoleCode
from apps.common.net import client_ip
from apps.common.permissions import RolePermission


class BackupResultSerializer(serializers.Serializer):
    file_name = serializers.CharField()
    bytes = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class BackupTestSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField()
    free_bytes = serializers.IntegerField()
    checked_at = serializers.DateTimeField()


class BackupCreateView(APIView):
    permission_classes = [RolePermission]
    required_roles = (RoleCode.SYSTEM_ADMIN,)

    @extend_schema(request=None, responses={201: BackupResultSerializer})
    def post(self, request):
        result = create_backup()
        write_audit(
            action="backup.created",
            entity="backup",
            after={"file_name": result["file_name"], "bytes": result["bytes"]},
            actor=request.user,
            ip=client_ip(request),
        )
        return Response(result, status=status.HTTP_201_CREATED)


class BackupTestView(APIView):
    permission_classes = [RolePermission]
    required_roles = (RoleCode.SYSTEM_ADMIN,)

    @extend_schema(request=None, responses={200: BackupTestSerializer})
    def post(self, request):
        result = test_backup_storage()
        write_audit(
            action="backup.tested",
            entity="backup",
            after={"status": result["status"]},
            actor=request.user,
            ip=client_ip(request),
        )
        return Response(result)
