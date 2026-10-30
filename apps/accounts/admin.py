from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Role, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name")
    ordering = ("id",)


@admin.register(User)
class TCMSUserAdmin(UserAdmin):
    list_display = ("username", "email", "is_staff", "is_active")
    fieldsets = UserAdmin.fieldsets + (("TCMS", {"fields": ("mfa_secret", "roles")}),)
    filter_horizontal = ("roles",)
