"""Shared DRF view base — RBAC-scoped ModelViewSet."""
from __future__ import annotations

from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.common.permissions import RolePermission


class RoleScopedModelViewSet(ModelViewSet):
    """ModelViewSet guarded by :class:`RolePermission`.

    Subclasses set ``required_roles`` / ``write_roles`` (tuples of RoleCode)."""

    permission_classes = [RolePermission]
    required_roles: tuple = ()
    write_roles: tuple = ()


class RoleScopedReadOnlyModelViewSet(ReadOnlyModelViewSet):
    """Read-only ModelViewSet guarded by :class:`RolePermission`."""

    permission_classes = [RolePermission]
    required_roles: tuple = ()
    write_roles: tuple = ()
