"""Finance & payroll API — RBAC-scoped, service-backed state transitions."""
from __future__ import annotations

from datetime import date

from django.db.models import Count
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.common.enums import RoleCode
from apps.common.views import RoleScopedModelViewSet, RoleScopedReadOnlyModelViewSet
from apps.payroll import services
from apps.payroll.models import (
    Account,
    Employee,
    EmployeePayElement,
    Journal,
    PayElement,
    PaymentFile,
    PayRun,
    Payslip,
    Provision,
    TaxBand,
    TimeEntry,
    Timesheet,
)
from apps.payroll.serializers import (
    AccountSerializer,
    EmployeeOfficerSerializer,
    EmployeePayElementSerializer,
    EmployeeSerializer,
    JournalCreateSerializer,
    JournalSerializer,
    PayElementSerializer,
    PaymentFileSerializer,
    PayRunCreateSerializer,
    PayRunSerializer,
    PayslipSerializer,
    ProvisionCreateSerializer,
    ProvisionSerializer,
    TaxBandSerializer,
    TimeEntryOfficerSerializer,
    TimeEntrySerializer,
    TimesheetCreateSerializer,
    TimesheetOfficerSerializer,
    TimesheetSerializer,
)

HR_ROLES = (RoleCode.HR_MANAGER, RoleCode.HR_OFFICER)
READ = (
    RoleCode.SYSTEM_ADMIN,
    RoleCode.ADMIN,
    RoleCode.ACCOUNTS,
    RoleCode.MD,
    RoleCode.REPORTS,
)
WRITE = (
    RoleCode.SYSTEM_ADMIN,
    RoleCode.ADMIN,
    RoleCode.ACCOUNTS,
    RoleCode.MD,
)
APPROVE = (RoleCode.SYSTEM_ADMIN, RoleCode.ADMIN, RoleCode.MD)
MANAGER_READ = READ + (RoleCode.HR_MANAGER,)
EMPLOYEE_READ = READ + HR_ROLES
EMPLOYEE_WRITE = WRITE + HR_ROLES
TIMESHEET_READ = READ + HR_ROLES
TIMESHEET_WRITE = WRITE + HR_ROLES
TIMESHEET_APPROVE = APPROVE + (RoleCode.HR_MANAGER,)
_PRIVILEGED = set(READ) | {RoleCode.HR_MANAGER}


def _officer_only(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return False
    role_ids = set(user.roles.values_list("id", flat=True))
    return RoleCode.HR_OFFICER in role_ids and not (role_ids & _PRIVILEGED)


def _require_timesheet_approver(user) -> None:
    if not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentication required.")
    if getattr(user, "is_superuser", False):
        return
    if not user.roles.filter(id__in=[int(r) for r in TIMESHEET_APPROVE]).exists():
        raise PermissionDenied("Only finance leads and HR Managers may approve timesheets.")


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError({"as_of": "expected YYYY-MM-DD"}) from None


class AccountViewSet(RoleScopedModelViewSet):
    queryset = Account.objects.select_related("parent").order_by("code")
    serializer_class = AccountSerializer
    required_roles = READ
    write_roles = WRITE
    filterset_fields = ["type", "active"]


class JournalViewSet(RoleScopedModelViewSet):
    queryset = Journal.objects.prefetch_related("lines__account").order_by("-date", "-id")
    serializer_class = JournalSerializer
    required_roles = READ
    write_roles = WRITE
    filterset_fields = ["status", "source"]

    def create(self, request, *args, **kwargs):
        serializer = JournalCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        journal = serializer.save()
        return Response(JournalSerializer(journal).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="post")
    def post_journal_entry(self, request, pk=None):
        journal = services.post_journal(self.get_object(), actor=request.user)
        return Response(JournalSerializer(journal).data)

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        journal = services.void_journal(
            self.get_object(),
            actor=request.user,
            reason=request.data.get("reason", ""),
        )
        return Response(JournalSerializer(journal).data)

    @action(detail=False, methods=["get"], url_path="trial-balance")
    def trial_balance(self, request):
        as_of = _parse_date(request.query_params.get("as_of"))
        return Response(services.trial_balance(as_of=as_of))


class EmployeeViewSet(RoleScopedModelViewSet):
    queryset = Employee.objects.select_related(
        "learner", "user", "position"
    ).order_by("staff_no")
    serializer_class = EmployeeSerializer
    required_roles = EMPLOYEE_READ
    write_roles = EMPLOYEE_WRITE
    filterset_fields = ["active", "pay_frequency", "position"]

    def get_serializer_class(self):
        if _officer_only(self.request.user):
            return EmployeeOfficerSerializer
        return EmployeeSerializer


class EmployeePayElementViewSet(RoleScopedModelViewSet):
    queryset = EmployeePayElement.objects.select_related(
        "employee", "element"
    ).order_by("employee__staff_no", "element__code")
    serializer_class = EmployeePayElementSerializer
    required_roles = MANAGER_READ
    write_roles = WRITE + (RoleCode.HR_MANAGER,)
    filterset_fields = ["employee", "element"]


class PayElementViewSet(RoleScopedModelViewSet):
    queryset = PayElement.objects.order_by("code")
    serializer_class = PayElementSerializer
    required_roles = READ
    write_roles = WRITE
    filterset_fields = ["kind", "active", "taxable", "pensionable"]


class PayRunViewSet(RoleScopedModelViewSet):
    queryset = (
        PayRun.objects.annotate(payslip_count=Count("payslips"))
        .select_related("journal")
        .order_by("-period", "-id")
    )
    serializer_class = PayRunSerializer
    required_roles = READ
    write_roles = WRITE
    filterset_fields = ["status", "period"]

    def create(self, request, *args, **kwargs):
        serializer = PayRunCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        pay_run = serializer.save()
        pay_run = PayRun.objects.annotate(payslip_count=Count("payslips")).get(
            pk=pay_run.pk
        )
        return Response(PayRunSerializer(pay_run).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def compute(self, request, pk=None):
        pay_run = services.compute_pay_run(self.get_object(), actor=request.user)
        return Response(PayRunSerializer(self._fresh(pay_run)).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        pay_run = services.approve_pay_run(self.get_object(), actor=request.user)
        return Response(PayRunSerializer(self._fresh(pay_run)).data)

    @action(detail=True, methods=["post"])
    def post(self, request, pk=None):
        pay_run = services.post_pay_run(self.get_object(), actor=request.user)
        return Response(PayRunSerializer(self._fresh(pay_run)).data)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        pay_run = services.mark_pay_run_paid(self.get_object(), actor=request.user)
        return Response(PayRunSerializer(self._fresh(pay_run)).data)

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        pay_run = services.void_pay_run(
            self.get_object(),
            actor=request.user,
            reason=request.data.get("reason", ""),
        )
        return Response(PayRunSerializer(self._fresh(pay_run)).data)

    @action(detail=True, methods=["post"], url_path="bank-file")
    def bank_file(self, request, pk=None):
        payment_file = services.generate_bank_file(self.get_object(), actor=request.user)
        return Response(PaymentFileSerializer(payment_file).data)

    def _fresh(self, pay_run):
        return (
            PayRun.objects.annotate(payslip_count=Count("payslips"))
            .select_related("journal")
            .get(pk=pay_run.pk)
        )


class PayslipViewSet(RoleScopedReadOnlyModelViewSet):
    queryset = Payslip.objects.select_related("employee", "pay_run").prefetch_related(
        "lines"
    )
    serializer_class = PayslipSerializer
    required_roles = MANAGER_READ
    write_roles = WRITE + (RoleCode.HR_MANAGER,)
    filterset_fields = ["pay_run", "employee"]


class TimesheetViewSet(RoleScopedModelViewSet):
    queryset = Timesheet.objects.select_related("employee").prefetch_related("entries")
    serializer_class = TimesheetSerializer
    required_roles = TIMESHEET_READ
    write_roles = TIMESHEET_WRITE
    filterset_fields = ["status", "employee"]

    def get_serializer_class(self):
        if _officer_only(self.request.user):
            return TimesheetOfficerSerializer
        return TimesheetSerializer

    def create(self, request, *args, **kwargs):
        serializer = TimesheetCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        timesheet = serializer.save()
        output = self.get_serializer_class()(timesheet)
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        timesheet = services.submit_timesheet(self.get_object(), actor=request.user)
        return Response(self.get_serializer_class()(timesheet).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        _require_timesheet_approver(request.user)
        timesheet = services.approve_timesheet(self.get_object(), actor=request.user)
        return Response(self.get_serializer_class()(timesheet).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        _require_timesheet_approver(request.user)
        timesheet = services.reject_timesheet(
            self.get_object(),
            actor=request.user,
            reason=request.data.get("reason", ""),
        )
        return Response(self.get_serializer_class()(timesheet).data)


class TimeEntryViewSet(RoleScopedModelViewSet):
    queryset = TimeEntry.objects.select_related("timesheet__employee")
    serializer_class = TimeEntrySerializer
    required_roles = TIMESHEET_READ
    write_roles = TIMESHEET_WRITE
    filterset_fields = ["timesheet", "kind"]

    def get_serializer_class(self):
        if _officer_only(self.request.user):
            return TimeEntryOfficerSerializer
        return TimeEntrySerializer


class ProvisionViewSet(RoleScopedModelViewSet):
    queryset = Provision.objects.select_related("employee", "timesheet")
    serializer_class = ProvisionSerializer
    required_roles = MANAGER_READ
    write_roles = WRITE + (RoleCode.HR_MANAGER,)
    filterset_fields = ["employee", "kind"]

    def create(self, request, *args, **kwargs):
        serializer = ProvisionCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        provision = serializer.save()
        return Response(
            ProvisionSerializer(provision).data, status=status.HTTP_201_CREATED
        )


class TaxBandViewSet(RoleScopedModelViewSet):
    queryset = TaxBand.objects.order_by("effective_from", "lower")
    serializer_class = TaxBandSerializer
    required_roles = READ
    write_roles = WRITE
    filterset_fields = ["active", "effective_from"]


class PaymentFileViewSet(RoleScopedReadOnlyModelViewSet):
    queryset = PaymentFile.objects.select_related("pay_run")
    serializer_class = PaymentFileSerializer
    required_roles = READ
    write_roles = WRITE
    filterset_fields = ["pay_run", "status"]

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        payment_file = self.get_object()
        response = HttpResponse(
            payment_file.content, content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{payment_file.filename}"'
        )
        return response
