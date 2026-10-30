import os
import secrets

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, User
from apps.common.enums import RoleCode, WorkflowStatusCode
from apps.workflow.models import WorkflowStatus

# next_role per status — design ``03-business-logic.md`` §2 routing table.
# status id -> role code acting to advance out of it (None = auto/terminal/re-enter).
NEXT_ROLE = {
    WorkflowStatusCode.NEW_RECORD: RoleCode.ADMIN,
    WorkflowStatusCode.ADMIN_DONE: RoleCode.VERIFICATION,
    WorkflowStatusCode.VERIFICATION_DONE: RoleCode.FRONT_DESK,
    WorkflowStatusCode.FRONT_DESK_DONE: RoleCode.MEDIC,
    WorkflowStatusCode.MEDIC_DONE: RoleCode.TRAINING_COORDINATOR,
    WorkflowStatusCode.TRAINING_COORDINATOR_DONE: RoleCode.ACCOUNTS,
    WorkflowStatusCode.ACCOUNTS_DONE: RoleCode.DUE_DILIGENCE,
    WorkflowStatusCode.DUE_DILIGENCE_DONE: RoleCode.MD,
    WorkflowStatusCode.MD_DONE: RoleCode.PRINTER,
    WorkflowStatusCode.CERTIFICATE_DONE: RoleCode.PRINTER,
    WorkflowStatusCode.ID_CARD_DONE: None,
    WorkflowStatusCode.COMPLETED: None,
    WorkflowStatusCode.CANCELLED: None,
    WorkflowStatusCode.REJECTED: None,
}
TERMINAL = {WorkflowStatusCode.COMPLETED, WorkflowStatusCode.CANCELLED}


class Command(BaseCommand):
    help = "SEED_ROLES: seed roles (12), workflow statuses (14) and the System-Admin user."

    def add_arguments(self, parser):
        parser.add_argument("--admin-user", default=os.environ.get("SEED_ADMIN_USER", "admin"))
        parser.add_argument("--admin-password", default=os.environ.get("SEED_ADMIN_PASSWORD"))
        parser.add_argument(
            "--admin-email", default=os.environ.get("SEED_ADMIN_EMAIL", "admin@tcms.local")
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        for rc in RoleCode:
            Role.objects.update_or_create(
                id=rc.value, defaults={"code": rc.name.lower(), "name": rc.label}
            )
        self.stdout.write(self.style.SUCCESS(f"roles: {Role.objects.count()}"))

        for wc in WorkflowStatusCode:
            WorkflowStatus.objects.update_or_create(
                id=wc.value,
                defaults={
                    "code": wc.name.lower(),
                    "name": wc.label,
                    "next_role_id": NEXT_ROLE[wc].value if NEXT_ROLE[wc] else None,
                    "terminal": wc in TERMINAL,
                },
            )
        self.stdout.write(
            self.style.SUCCESS(f"workflow_status: {WorkflowStatus.objects.count()}")
        )

        password = opts["admin_password"]
        if password in {"admin", "change-me", "changeme", "password"}:
            raise CommandError(
                "Refusing to use a well-known admin password; pass --admin-password "
                "or set SEED_ADMIN_PASSWORD to a strong secret."
            )
        generated = False
        if not password:
            password = secrets.token_urlsafe(18)
            generated = True

        user, created = User.objects.get_or_create(
            username=opts["admin_user"],
            defaults={
                "email": opts["admin_email"],
                "is_staff": True,
                "is_superuser": True,
                "email_verified": True,
            },
        )
        if created:
            user.set_password(password)
            user.save()
        user.roles.add(Role.objects.get(id=RoleCode.SYSTEM_ADMIN))
        self.stdout.write(
            self.style.SUCCESS(
                f"admin user {'created' if created else 'already present'}: {user.username}"
            )
        )
        if generated and created:
            self.stdout.write(
                self.style.WARNING(
                    "Generated admin password (store it now, it will not be "
                    f"shown again): {password}"
                )
            )
