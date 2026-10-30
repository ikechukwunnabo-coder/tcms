from rest_framework import serializers

from apps.catalogue.models import CertificateType, Course, CourseItem, CourseModule


class CertificateTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateType
        fields = ["id", "name"]


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = [
            "id", "course_code", "name", "cert_type", "expiry_type", "duration_days",
            "validity_years", "id_card", "foet_required", "opito_reg_code",
            "refresher_course", "active",
        ]


class CourseModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseModule
        fields = ["id", "name", "active"]


class CourseItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseItem
        fields = ["id", "name", "active"]
