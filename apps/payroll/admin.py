from django.contrib import admin

from apps.payroll.models import (
    Account,
    Employee,
    EmployeePayElement,
    Journal,
    JournalLine,
    JournalSequence,
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


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "type", "parent", "active")
    list_filter = ("type", "active")
    search_fields = ("code", "name")


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 0


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ("journal_no", "date", "source", "status", "posted_at")
    list_filter = ("status",)
    search_fields = ("journal_no", "memo")
    inlines = [JournalLineInline]


@admin.register(JournalSequence)
class JournalSequenceAdmin(admin.ModelAdmin):
    list_display = ("year", "last_number")


class EmployeePayElementInline(admin.TabularInline):
    model = EmployeePayElement
    extra = 0


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("staff_no", "full_name", "pay_frequency", "active")
    list_filter = ("pay_frequency", "active")
    search_fields = ("staff_no", "full_name")
    inlines = [EmployeePayElementInline]


@admin.register(PayElement)
class PayElementAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "taxable", "pensionable", "active")
    list_filter = ("kind", "taxable", "pensionable", "active")


class PayslipLineInline(admin.TabularInline):
    model = PayslipLine
    extra = 0
    readonly_fields = ("element", "description", "kind", "quantity", "rate", "amount")


@admin.register(PayRun)
class PayRunAdmin(admin.ModelAdmin):
    list_display = (
        "period",
        "run_date",
        "status",
        "total_gross",
        "total_tax",
        "total_net",
    )
    list_filter = ("status",)


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = (
        "pay_run",
        "employee",
        "gross",
        "tax",
        "pension",
        "net",
    )
    inlines = [PayslipLineInline]


@admin.register(Timesheet)
class TimesheetAdmin(admin.ModelAdmin):
    list_display = ("employee", "period_start", "period_end", "status", "total_hours")
    list_filter = ("status",)


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ("timesheet", "work_date", "hours", "kind", "project")
    list_filter = ("kind",)


@admin.register(Provision)
class ProvisionAdmin(admin.ModelAdmin):
    list_display = ("employee", "kind", "days", "rate", "amount", "as_of")
    list_filter = ("kind",)


@admin.register(TaxBand)
class TaxBandAdmin(admin.ModelAdmin):
    list_display = ("name", "lower", "upper", "rate_pct", "effective_from", "active")
    list_filter = ("active", "effective_from")


@admin.register(PaymentFile)
class PaymentFileAdmin(admin.ModelAdmin):
    list_display = ("filename", "pay_run", "status", "generated_at")
    list_filter = ("status",)
