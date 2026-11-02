from rest_framework import serializers

from apps.certification.models import (
    Certificate,
    CertificateBatch,
    CertificateReminder,
    CertificateSequence,
    IDCard,
)


class CertificateSerializer(serializers.ModelSerializer):
    learner_name = serializers.CharField(source="learner.full_name", read_only=True)
    badge_no = serializers.CharField(source="learner.badge_no", read_only=True)
    course_code = serializers.CharField(
        source="training_record.course.course_code", read_only=True
    )

    class Meta:
        model = Certificate
        fields = [
            "id", "training_record", "learner", "learner_name", "badge_no",
            "course_code", "certificate_no",
            "format", "issued_at", "issued_by", "printed_at", "printed_by",
            "id_issued_at", "id_printed_at", "expiry_date", "object_key",
            "md_approved_by", "md_approved_at", "signature_applied", "seal_applied",
            "signature_object_key", "seal_object_key", "voided_at", "void_reason",
            "released_at", "renewed_by_certificate", "batch",
        ]
        read_only_fields = fields


class IssueCertificateSerializer(serializers.Serializer):
    """``POST /certificates/issue`` — issue for an approved training record."""

    training_record = serializers.IntegerField()


class CertificateReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateReminder
        fields = [
            "id", "certificate", "offset_days", "due_on", "recipient",
            "channel", "status", "sent_at", "created_at",
        ]
        read_only_fields = fields


class CertificateBatchSerializer(serializers.ModelSerializer):
    corporate_account_name = serializers.CharField(
        source="corporate_account.name", read_only=True
    )

    class Meta:
        model = CertificateBatch
        fields = [
            "id",
            "corporate_account",
            "corporate_account_name",
            "zip_file_ref",
            "zip_file_hash",
            "certificate_count",
            "status",
            "delivered_to",
            "delivered_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CertificateSequenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateSequence
        fields = ["id", "course_year", "item_id", "last_number", "updated_at"]


class IDCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = IDCard
        fields = [
            "id",
            "learner",
            "training_record",
            "card_no",
            "printed_at",
            "printed_by",
            "object_key",
        ]
        read_only_fields = ["id", "printed_at", "printed_by"]


class ReminderResultSerializer(serializers.Serializer):
    recipient = serializers.EmailField(allow_blank=True)
    sent = serializers.BooleanField()
    validity = serializers.CharField()


class RenewalRequestSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(required=False, allow_null=True)


class RenewalResultSerializer(serializers.Serializer):
    training_record_id = serializers.IntegerField()
    enrolment_id = serializers.IntegerField(required=False, allow_null=True)
