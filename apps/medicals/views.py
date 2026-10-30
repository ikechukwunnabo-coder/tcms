from apps.common.enums import RoleCode
from apps.common.views import RoleScopedModelViewSet
from apps.medicals import serializers as s
from apps.medicals.models import Medical

READ = (RoleCode.SYSTEM_ADMIN, RoleCode.ADMIN, RoleCode.FRONT_DESK, RoleCode.MEDIC)
WRITE = (RoleCode.SYSTEM_ADMIN, RoleCode.ADMIN, RoleCode.MEDIC)


class MedicalViewSet(RoleScopedModelViewSet):
    queryset = Medical.objects.select_related("learner").order_by("-expiry_date")
    serializer_class = s.MedicalSerializer
    required_roles = READ
    write_roles = WRITE
    filterset_fields = ["learner", "active", "fitness"]
    search_fields = ["learner__badge_no", "learner__surname", "record_no"]
    ordering_fields = ["issued_date", "expiry_date"]
