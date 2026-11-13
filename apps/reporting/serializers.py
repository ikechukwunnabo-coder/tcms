from rest_framework import serializers

from apps.accounts.models import Role
from apps.reporting.models import ReportDef, ReportRun


class ReportDefSerializer(serializers.ModelSerializer):
    roles = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Role.objects.all(), required=False
    )

    class Meta:
        model = ReportDef
        fields = ["id", "code", "name", "roles", "sql_view"]


class ReportRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportRun
        fields = ["id", "report_def", "params", "requested_by", "generated_at", "object_key"]
        read_only_fields = ["id", "generated_at", "requested_by"]
