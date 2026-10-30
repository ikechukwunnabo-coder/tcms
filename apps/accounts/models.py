from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class Role(models.Model):
    """Role — mirrors the 12 AXIS roles.

    Design ``02-database.md`` M1, ``03-business-logic.md`` §10.

    The primary key IS the legacy role code (1..12) so seeded data keeps AXIS
    semantics (see ``RoleCode`` in ``apps.common.enums``).
    """

    id = models.SmallAutoField(primary_key=True)
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=64)

    class Meta:
        db_table = "role"

    def __str__(self) -> str:
        return self.name


class User(AbstractUser):
    """System user. ``AbstractUser`` supplies username/password/email/
    ``last_login``/``is_active``; ``mfa_secret`` is the TCMS hardening
    addition (gap G3 — no plaintext credentials).

    ``email_verified`` gates portal login (spec BR-15). Staff accounts are
    provisioned by an administrator and default to verified; portal
    self-registration sets it ``False`` until the verify-email step.
    """

    mfa_secret = models.CharField(max_length=255, blank=True, default="")
    email_verified = models.BooleanField(default=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    roles = models.ManyToManyField(Role, blank=True, related_name="users")

    class Meta:
        db_table = "user"
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                condition=~Q(email=""),
                name="uq_user_email_ci",
            )
        ]

    @property
    def full_name(self) -> str:
        return self.get_full_name() or self.username
