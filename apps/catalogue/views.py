from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import write_audit
from apps.catalogue import serializers as s
from apps.catalogue.models import (
    CertificateType,
    Course,
    CourseItem,
    CourseItemRelation,
    CourseModule,
    CourseModuleRelation,
)
from apps.common.enums import RoleCode
from apps.common.permissions import ANY_ROLE, RolePermission
from apps.common.relations import parse_relation_pairs
from apps.common.views import RoleScopedModelViewSet

WRITE = (RoleCode.SYSTEM_ADMIN,)


class CourseViewSet(RoleScopedModelViewSet):
    queryset = Course.objects.all().order_by("course_code")
    serializer_class = s.CourseSerializer
    required_roles = ANY_ROLE
    write_roles = WRITE
    filterset_fields = ["active", "cert_type", "id_card", "foet_required"]
    search_fields = ["course_code", "name", "opito_reg_code"]


class CourseModuleViewSet(RoleScopedModelViewSet):
    queryset = CourseModule.objects.all().order_by("name")
    serializer_class = s.CourseModuleSerializer
    required_roles = ANY_ROLE
    write_roles = WRITE
    filterset_fields = ["active"]
    search_fields = ["name"]


class CourseItemViewSet(RoleScopedModelViewSet):
    queryset = CourseItem.objects.all().order_by("name")
    serializer_class = s.CourseItemSerializer
    required_roles = ANY_ROLE
    write_roles = WRITE
    filterset_fields = ["active"]
    search_fields = ["name"]


class CertificateTypeViewSet(RoleScopedModelViewSet):
    queryset = CertificateType.objects.all().order_by("id")
    serializer_class = s.CertificateTypeSerializer
    required_roles = ANY_ROLE
    write_roles = WRITE


class CourseRelationMixin:
    permission_classes = [RolePermission]
    required_roles = ANY_ROLE
    write_roles = WRITE

    relation_model = None
    parent_model = Course
    child_model = None
    parent_field = "course"
    child_field = ""
    child_serializer_class = None
    relation_serializer_class = None
    audit_prefix = ""

    def parent(self, parent_id):
        return get_object_or_404(self.parent_model, pk=parent_id)

    def relation_filter(self, parent_id):
        return {f"{self.parent_field}_id": parent_id}

    def delete_relation(self, relation_id):
        relation = get_object_or_404(self.relation_model, pk=relation_id)
        parent_id = getattr(relation, f"{self.parent_field}_id")
        child_id = getattr(relation, f"{self.child_field}_id")
        relation.delete()
        write_audit(
            action=f"catalogue.{self.audit_prefix}_relation_removed",
            entity=f"{self.audit_prefix}_relation",
            entity_id=relation_id,
            after={self.parent_field: parent_id, self.child_field: child_id},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class CourseRelationCollectionView(CourseRelationMixin, APIView):
    @extend_schema(request=s.RelationCreateSerializer, responses={201: None})
    def post(self, request):
        pairs = parse_relation_pairs(request.data, parent_key=self.parent_field)
        created = []
        with transaction.atomic():
            for parent_id, child_id in pairs:
                parent = self.parent(parent_id)
                child = get_object_or_404(self.child_model, pk=child_id)
                relation, is_new = self.relation_model.objects.get_or_create(
                    **{self.parent_field: parent, self.child_field: child},
                    defaults={
                        "created_by": request.user
                        if request.user.is_authenticated
                        else None
                    },
                )
                if is_new:
                    write_audit(
                        action=f"catalogue.{self.audit_prefix}_relation_added",
                        entity=f"{self.audit_prefix}_relation",
                        entity_id=relation.pk,
                        after={
                            self.parent_field: parent_id,
                            self.child_field: child_id,
                        },
                    )
                created.append(relation)
        return Response(
            self.relation_serializer_class(created, many=True).data,
            status=status.HTTP_201_CREATED,
        )


class CourseRelationDetailView(CourseRelationMixin, APIView):
    @extend_schema(responses={200: None})
    def get(self, request, parent_id):
        self.parent(parent_id)
        rows = (
            self.relation_model.objects.filter(**self.relation_filter(parent_id))
            .select_related(self.child_field)
            .order_by(f"{self.child_field}__name")
        )
        return Response(self.relation_serializer_class(rows, many=True).data)

    @extend_schema(responses={204: None})
    def delete(self, request, parent_id):
        return self.delete_relation(parent_id)


class CourseRelationAvailableView(CourseRelationMixin, APIView):
    @extend_schema(responses={200: None})
    def get(self, request, parent_id):
        self.parent(parent_id)
        used = self.relation_model.objects.filter(
            **self.relation_filter(parent_id)
        ).values_list(f"{self.child_field}_id", flat=True)
        rows = self.child_model.objects.filter(active=True).exclude(id__in=used).order_by("name")
        return Response(self.child_serializer_class(rows, many=True).data)


class CourseRelationDeleteView(CourseRelationMixin, APIView):
    @extend_schema(responses={204: None})
    def delete(self, request, relation_id):
        return self.delete_relation(relation_id)


class CourseItemRelationView(CourseRelationCollectionView):
    relation_model = CourseItemRelation
    child_model = CourseItem
    child_field = "item"
    child_serializer_class = s.CourseItemSerializer
    relation_serializer_class = s.CourseItemRelationSerializer
    audit_prefix = "course_item"


class CourseItemRelationDetailView(CourseRelationDetailView):
    relation_model = CourseItemRelation
    child_model = CourseItem
    child_field = "item"
    child_serializer_class = s.CourseItemSerializer
    relation_serializer_class = s.CourseItemRelationSerializer
    audit_prefix = "course_item"


class CourseItemRelationAvailableView(CourseRelationAvailableView):
    relation_model = CourseItemRelation
    child_model = CourseItem
    child_field = "item"
    child_serializer_class = s.CourseItemSerializer
    relation_serializer_class = s.CourseItemRelationSerializer
    audit_prefix = "course_item"


class CourseItemRelationDeleteView(CourseRelationDeleteView):
    relation_model = CourseItemRelation
    child_model = CourseItem
    child_field = "item"
    child_serializer_class = s.CourseItemSerializer
    relation_serializer_class = s.CourseItemRelationSerializer
    audit_prefix = "course_item"


class CourseModuleRelationView(CourseRelationCollectionView):
    relation_model = CourseModuleRelation
    child_model = CourseModule
    child_field = "module"
    child_serializer_class = s.CourseModuleSerializer
    relation_serializer_class = s.CourseModuleRelationSerializer
    audit_prefix = "course_module"


class CourseModuleRelationDetailView(CourseRelationDetailView):
    relation_model = CourseModuleRelation
    child_model = CourseModule
    child_field = "module"
    child_serializer_class = s.CourseModuleSerializer
    relation_serializer_class = s.CourseModuleRelationSerializer
    audit_prefix = "course_module"


class CourseModuleRelationAvailableView(CourseRelationAvailableView):
    relation_model = CourseModuleRelation
    child_model = CourseModule
    child_field = "module"
    child_serializer_class = s.CourseModuleSerializer
    relation_serializer_class = s.CourseModuleRelationSerializer
    audit_prefix = "course_module"


class CourseModuleRelationDeleteView(CourseRelationDeleteView):
    relation_model = CourseModuleRelation
    child_model = CourseModule
    child_field = "module"
    child_serializer_class = s.CourseModuleSerializer
    relation_serializer_class = s.CourseModuleRelationSerializer
    audit_prefix = "course_module"
