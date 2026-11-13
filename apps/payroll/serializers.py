"""Payroll & finance serializers — service-backed where state changes."""
from rest_framework import serializers

from apps.payroll import services
from apps.payroll.models import (
    Account,
    Employee,
    EmployeePayElement,
    Journal,
    JournalLine,
    PayElement,
    PaymentFile,
    PayRun,
    Payslip,
    PayslipLine,
    Provision,
    TaxBand,
    TimeEntry,
    Timesheet,
)


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ["id", "code", "name", "type", "parent", "active"]


class JournalLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source="account.code", read_only=True)

    class Meta:
        model = JournalLine
        fields = [
            "id",
            "account",
            "account_code",
            "debit",
            "credit",
            "dimension",
            "memo",
        ]


class JournalSerializer(serializers.ModelSerializer):
    lines = JournalLineSerializer(many=True, read_only=True)
    total_debit = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    total_credit = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model = Journal
        fields = [
            "id",
            "journal_no",
            "date",
            "memo",
            "source",
            "status",
            "prepared_by",
            "approved_by",
            "approved_at",
            "posted_at",
            "posted_by",
            "void_reason",
            "total_debit",
            "total_credit",
            "lines",
        ]
        read_only_fields = [
            "id",
            "journal_no",
            "status",
            "prepared_by",
            "approved_by",
            "approved_at",
            "posted_at",
            "posted_by",
            "total_debit",
            "total_credit",
            "lines",
        ]


class JournalLineInputSerializer(serializers.Serializer):
    account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all())
    debit = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=0
    )
    credit = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=0
    )
    dimension = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default=""
    )
    memo = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )


class JournalCreateSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)
    memo = serializers.CharField(required=False, allow_blank=True, default="")
    source = serializers.CharField(required=False, allow_blank=True, default="")
    lines = JournalLineInputSerializer(many=True)

    def create(self, validated_data):
        return services.create_journal(
            actor=self.context["request"].user, **validated_data
        )


class EmployeeSerializer(serializers.ModelSerializer):
    position_name = serializers.CharField(source="position.name", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "staff_no",
            "full_name",
            "learner",
            "user",
            "position",
            "position_name",
            "pay_frequency",
            "basic_salary",
            "hourly_rate",
            "bank_name",
            "bank_code",
            "account_name",
            "bank_account",
            "tax_id",
            "pension_id",
            "active",
        ]


class EmployeeOfficerSerializer(serializers.ModelSerializer):
    """HR Officer view: no salary, hourly rate or bank details."""

    position_name = serializers.CharField(source="position.name", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "staff_no",
            "full_name",
            "learner",
            "user",
            "position",
            "position_name",
            "pay_frequency",
            "tax_id",
            "pension_id",
            "active",
        ]


class EmployeePayElementSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    element_code = serializers.CharField(source="element.code", read_only=True)
    element_name = serializers.CharField(source="element.name", read_only=True)

    class Meta:
        model = EmployeePayElement
        fields = [
            "id",
            "employee",
            "employee_name",
            "element",
            "element_code",
            "element_name",
            "amount",
        ]


class PayElementSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayElement
        fields = [
            "id",
            "code",
            "name",
            "kind",
            "taxable",
            "pensionable",
            "formula",
            "active",
        ]


class PayslipLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayslipLine
        fields = [
            "id",
            "element",
            "description",
            "kind",
            "quantity",
            "rate",
            "amount",
        ]


class PayslipSerializer(serializers.ModelSerializer):
    lines = PayslipLineSerializer(many=True, read_only=True)
    staff_no = serializers.CharField(source="employee.staff_no", read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)

    class Meta:
        model = Payslip
        fields = [
            "id",
            "pay_run",
            "employee",
            "staff_no",
            "employee_name",
            "gross",
            "tax",
            "pension",
            "pension_employer",
            "other_deductions",
            "deductions",
            "net",
            "worked_hours",
            "lines",
        ]


class PayRunSerializer(serializers.ModelSerializer):
    payslip_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = PayRun
        fields = [
            "id",
            "period",
            "run_date",
            "status",
            "total_gross",
            "total_tax",
            "total_pension_employee",
            "total_pension_employer",
            "total_deductions",
            "total_net",
            "prepared_by",
            "approved_by",
            "approved_at",
            "posted_at",
            "journal",
            "payslip_count",
        ]
        read_only_fields = [
            "id",
            "status",
            "total_gross",
            "total_tax",
            "total_pension_employee",
            "total_pension_employer",
            "total_deductions",
            "total_net",
            "prepared_by",
            "approved_by",
            "approved_at",
            "posted_at",
            "journal",
            "payslip_count",
        ]


class PayRunCreateSerializer(serializers.Serializer):
    period = serializers.RegexField(r"^\d{4}-\d{2}$")
    run_date = serializers.DateField(required=False)

    def create(self, validated_data):
        return services.create_pay_run(
            actor=self.context["request"].user, **validated_data
        )


class TimeEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeEntry
        fields = [
            "id",
            "timesheet",
            "work_date",
            "hours",
            "rate",
            "kind",
            "is_holiday",
            "project",
            "job_no",
        ]


class TimeEntryOfficerSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeEntry
        fields = [
            "id",
            "timesheet",
            "work_date",
            "hours",
            "kind",
            "is_holiday",
            "project",
            "job_no",
        ]


_TIMESHEET_FIELDS = [
    "id",
    "employee",
    "staff_no",
    "period_start",
    "period_end",
    "status",
    "total_hours",
    "worked_days",
    "approved_by",
    "approved_at",
    "entries",
]
_TIMESHEET_READ_ONLY = [
    "id",
    "status",
    "total_hours",
    "worked_days",
    "approved_by",
    "approved_at",
    "entries",
]


class TimesheetSerializer(serializers.ModelSerializer):
    entries = TimeEntrySerializer(many=True, read_only=True)
    staff_no = serializers.CharField(source="employee.staff_no", read_only=True)

    class Meta:
        model = Timesheet
        fields = _TIMESHEET_FIELDS
        read_only_fields = _TIMESHEET_READ_ONLY


class TimesheetOfficerSerializer(serializers.ModelSerializer):
    entries = TimeEntryOfficerSerializer(many=True, read_only=True)
    staff_no = serializers.CharField(source="employee.staff_no", read_only=True)

    class Meta:
        model = Timesheet
        fields = _TIMESHEET_FIELDS
        read_only_fields = _TIMESHEET_READ_ONLY


class TimesheetCreateSerializer(serializers.Serializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    period_start = serializers.DateField()
    period_end = serializers.DateField()

    def create(self, validated_data):
        return services.create_timesheet(
            actor=self.context["request"].user, **validated_data
        )


class ProvisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provision
        fields = [
            "id",
            "employee",
            "timesheet",
            "kind",
            "days",
            "rate",
            "amount",
            "as_of",
        ]


class ProvisionCreateSerializer(serializers.Serializer):
    timesheet = serializers.PrimaryKeyRelatedField(queryset=Timesheet.objects.all())
    daily_rate = serializers.DecimalField(max_digits=12, decimal_places=2)
    as_of = serializers.DateField()
    kind = serializers.CharField(required=False, default="leave")

    def create(self, validated_data):
        return services.accrue_provision(
            actor=self.context["request"].user, **validated_data
        )


class TaxBandSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxBand
        fields = [
            "id",
            "name",
            "lower",
            "upper",
            "rate_pct",
            "effective_from",
            "active",
        ]


class PaymentFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentFile
        fields = [
            "id",
            "pay_run",
            "filename",
            "status",
            "generated_at",
            "generated_by",
            "content",
        ]
        read_only_fields = fields
