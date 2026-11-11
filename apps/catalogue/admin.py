from django.contrib import admin

from .models import (
    CertificateType,
    Course,
    CourseItem,
    CourseItemRelation,
    CourseModule,
    CourseModuleItem,
    CourseModuleRelation,
)


class CourseModuleItemInline(admin.TabularInline):
    model = CourseModuleItem
    extra = 0


class CourseModuleRelationInline(admin.TabularInline):
    model = CourseModuleRelation
    extra = 0
    fk_name = "course"


class CourseItemRelationInline(admin.TabularInline):
    model = CourseItemRelation
    extra = 0
    fk_name = "course"


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "course_code",
        "name",
        "cert_type",
        "expiry_type",
        "validity_years",
        "id_card",
        "active",
    )
    list_filter = ("active", "cert_type", "expiry_type", "id_card")
    search_fields = ("course_code", "name", "opito_reg_code")
    inlines = (CourseModuleItemInline, CourseModuleRelationInline, CourseItemRelationInline)


@admin.register(CertificateType)
class CertificateTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name")


admin.site.register(CourseModule)
admin.site.register(CourseItem)
