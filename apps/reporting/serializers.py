from rest_framework import serializers

from apps.reporting.models import ReportDef, ReportRun


class ReportDefSerializer(serializers.ModelSerializer):
    roles = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = ReportDef
        fields = ["id", "code", "name", "roles", "sql_view"]


class ReportRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportRun
        fields = ["id", "report_def", "params", "requested_by", "generated_at", "object_key"]
        read_only_fields = ["id", "generated_at", "requested_by"]
