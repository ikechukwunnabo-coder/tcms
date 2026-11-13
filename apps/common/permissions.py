"""Deny-by-default RBAC (R-RBAC-01, gap G1).

Role sets are declared on the *view* (``required_roles`` for reads,
``write_roles`` for writes, each a tuple of ``RoleCode`` ints). A view with
neither set denies everyone except superusers. django-rules is not installed,
so this reads the ``User.roles`` M2M directly.
"""
from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.common.enums import RoleCode

# All 14 staff roles — "any authenticated staff member" (deny-by-default still
# applies to users holding no role).
ANY_ROLE = tuple(int(r) for r in RoleCode)


class RolePermission(BasePermission):
    message = "You do not have the required role for this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if getattr(user, "is_superuser", False):
            return True

        read_roles = getattr(view, "required_roles", None)
        write_roles = getattr(view, "write_roles", None)
        if request.method in SAFE_METHODS:
            allowed = read_roles if read_roles is not None else write_roles
        else:
            allowed = write_roles if write_roles is not None else read_roles

        if not allowed:
            return False
        return user.roles.filter(id__in=[int(r) for r in allowed]).exists()

    def has_object_permission(self, request, view, obj) -> bool:
        return self.has_permission(request, view)
