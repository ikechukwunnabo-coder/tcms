from rest_framework import serializers

from apps.workflow.models import Approval, ApprovalHistory, TransactionLog, WorkflowStatus


class WorkflowStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowStatus
        fields = ["id", "code", "name", "next_role", "terminal"]


class ApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Approval
        fields = [
            "id", "training_record", "current_status", "step_no", "assigned_role",
            "action", "reason", "acted_by", "acted_at", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ApprovalHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalHistory
        fields = ["id", "training_record", "status", "full_name", "updated_at"]


class TransactionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionLog
        fields = [
            "id", "entity", "entity_id", "field", "old_value", "new_value",
            "changed_by", "changed_at", "approved_by", "approved_at",
        ]


class WorkflowActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=["approve", "reject", "cancel"], default="approve"
    )
    reason = serializers.CharField(required=False, allow_blank=True, default="")
