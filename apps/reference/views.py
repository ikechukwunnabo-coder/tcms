from apps.common.enums import RoleCode
from apps.common.permissions import ANY_ROLE
from apps.common.views import RoleScopedModelViewSet
from apps.reference import serializers as s
from apps.reference.models import Company, ContactType, Nationality, Position, State, Title

WRITE = (RoleCode.SYSTEM_ADMIN,)


class CompanyViewSet(RoleScopedModelViewSet):
    queryset = Company.objects.all().order_by("name")
    serializer_class = s.CompanySerializer
    required_roles = ANY_ROLE
    write_roles = WRITE
    filterset_fields = ["active", "is_individual"]
    search_fields = ["agencode", "name", "email"]


class NationalityViewSet(RoleScopedModelViewSet):
    queryset = Nationality.objects.all().order_by("nationality")
    serializer_class = s.NationalitySerializer
    required_roles = ANY_ROLE
    write_roles = WRITE
    search_fields = ["natcode", "country", "nationality"]


class StateViewSet(RoleScopedModelViewSet):
    queryset = State.objects.all().order_by("name")
    serializer_class = s.StateSerializer
    required_roles = ANY_ROLE
    write_roles = WRITE
    search_fields = ["code", "name"]


class PositionViewSet(RoleScopedModelViewSet):
    queryset = Position.objects.all().order_by("name")
    serializer_class = s.PositionSerializer
    required_roles = ANY_ROLE
    write_roles = WRITE
    search_fields = ["posicode", "name"]


class TitleViewSet(RoleScopedModelViewSet):
    queryset = Title.objects.all().order_by("id")
    serializer_class = s.TitleSerializer
    required_roles = ANY_ROLE
    write_roles = WRITE


class ContactTypeViewSet(RoleScopedModelViewSet):
    queryset = ContactType.objects.all().order_by("id")
    serializer_class = s.ContactTypeSerializer
    required_roles = ANY_ROLE
    write_roles = WRITE
