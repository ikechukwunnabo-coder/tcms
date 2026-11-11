from rest_framework import serializers

from apps.catalogue.serializers import CourseSerializer
from apps.certification.serializers import CertificateSerializer, IDCardSerializer
from apps.delivery.models import (
    DailyMedicalCheck,
    TrainingInstructor,
    TrainingItem,
    TrainingRecord,
)
from apps.documents.serializers import DocumentSerializer
from apps.learners.serializers import LearnerSerializer
from apps.medicals.serializers import MedicalSerializer
from apps.portal.serializers import JoiningInstructionSerializer
from apps.workflow.serializers import ApprovalHistorySerializer, WorkflowStatusSerializer


class TrainingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingItem
        fields = ["id", "training_record", "course_item", "passed", "score"]


class TrainingInstructorSerializer(serializers.ModelSerializer):
    module_name = serializers.CharField(source="module.name", read_only=True)

    class Meta:
        model = TrainingInstructor
        fields = [
            "id",
            "training_record",
            "instructor",
            "module",
            "module_name",
            "training_date",
        ]


class DailyMedicalCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyMedicalCheck
        fields = [
            "id",
            "training_record",
            "check_date",
            "systolic",
            "diastolic",
            "notes",
            "created_at",
            "created_by",
        ]
        read_only_fields = ["id", "created_at", "created_by"]


class TrainingRecordSerializer(serializers.ModelSerializer):
    learner_name = serializers.CharField(source="learner.full_name", read_only=True)
    badge_no = serializers.CharField(source="learner.badge_no", read_only=True)
    company_name = serializers.SerializerMethodField()
    course_name = serializers.CharField(source="course.name", read_only=True)
    course_code = serializers.CharField(source="course.course_code", read_only=True)
    status_code = serializers.CharField(source="status.code", read_only=True)
    items = TrainingItemSerializer(many=True, read_only=True)
    training_instructors = TrainingInstructorSerializer(many=True, read_only=True)
    medical_checks = DailyMedicalCheckSerializer(many=True, read_only=True)

    class Meta:
        model = TrainingRecord
        fields = [
            "id",
            "learner",
            "learner_name",
            "badge_no",
            "company_name",
            "course",
            "course_name",
            "course_code",
            "session",
            "enrolment",
            "start_date",
            "end_date",
            "prev_expiry",
            "status",
            "status_code",
            "reject_reason",
            "instructor",
            "foet_scan",
            "payment_proof",
            "welcome_letter",
            "items",
            "training_instructors",
            "medical_checks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "status", "reject_reason"]

    def get_company_name(self, obj) -> str:
        company = getattr(obj.learner, "company", None)
        return company.name if company is not None else "Individual"


class TrainingRecordWorkspaceSerializer(TrainingRecordSerializer):
    learner_detail = LearnerSerializer(source="learner", read_only=True)
    course_detail = CourseSerializer(source="course", read_only=True)
    status_detail = WorkflowStatusSerializer(source="status", read_only=True)
    foet_scan_document = DocumentSerializer(source="foet_scan", read_only=True)
    payment_proof_document = DocumentSerializer(source="payment_proof", read_only=True)
    welcome_letter_document = DocumentSerializer(source="welcome_letter", read_only=True)
    medicals = MedicalSerializer(source="learner.medicals", many=True, read_only=True)
    certificates = CertificateSerializer(many=True, read_only=True)
    id_cards = IDCardSerializer(many=True, read_only=True)
    status_history = ApprovalHistorySerializer(many=True, read_only=True)
    joining_instruction = serializers.SerializerMethodField()

    class Meta(TrainingRecordSerializer.Meta):
        fields = TrainingRecordSerializer.Meta.fields + [
            "learner_detail",
            "course_detail",
            "status_detail",
            "foet_scan_document",
            "payment_proof_document",
            "welcome_letter_document",
            "medicals",
            "certificates",
            "id_cards",
            "status_history",
            "joining_instruction",
        ]

    def get_joining_instruction(self, obj):
        if not obj.enrolment_id:
            return None
        joining_instruction = (
            obj.enrolment.joining_instructions.filter(is_current=True)
            .select_related("session")
            .first()
        )
        return (
            JoiningInstructionSerializer(joining_instruction).data
            if joining_instruction is not None
            else None
        )
