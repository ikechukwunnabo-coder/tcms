from rest_framework import serializers

from apps.catalogue.models import (
    CertificateType,
    Course,
    CourseItem,
    CourseItemRelation,
    CourseModule,
    CourseModuleRelation,
)


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
            "front_id_text", "back_id_text", "refresher_course", "active",
        ]


class CourseModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseModule
        fields = ["id", "name", "active"]


class CourseItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseItem
        fields = ["id", "name", "active"]


class RelationCreateSerializer(serializers.Serializer):
    """Documented object form; Axis-style pair arrays are also accepted."""

    parent = serializers.IntegerField(required=False)
    children = serializers.ListField(child=serializers.IntegerField(), required=False)
    pairs = serializers.ListField(
        child=serializers.ListField(child=serializers.IntegerField()), required=False
    )


class CourseModuleRelationSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="module.name", read_only=True)

    class Meta:
        model = CourseModuleRelation
        fields = ["id", "course", "module", "name"]
        read_only_fields = fields


class CourseItemRelationSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="item.name", read_only=True)

    class Meta:
        model = CourseItemRelation
        fields = ["id", "course", "item", "name"]
        read_only_fields = fields
