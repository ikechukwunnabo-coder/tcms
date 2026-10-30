from django.contrib import admin

from .models import CertificateType, Course, CourseItem, CourseModule, CourseModuleItem


class CourseModuleItemInline(admin.TabularInline):
    model = CourseModuleItem
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("course_code", "name", "cert_type", "validity_years", "id_card", "active")
    list_filter = ("active", "cert_type", "id_card")
    search_fields = ("course_code", "name", "opito_reg_code")
    inlines = (CourseModuleItemInline,)


@admin.register(CertificateType)
class CertificateTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name")


admin.site.register(CourseModule)
admin.site.register(CourseItem)
