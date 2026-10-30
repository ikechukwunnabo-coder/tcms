from apps.catalogue import serializers as s
from apps.catalogue.models import CertificateType, Course, CourseItem, CourseModule
from apps.common.enums import RoleCode
from apps.common.permissions import ANY_ROLE
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
