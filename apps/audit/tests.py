"""Audit trail — append-only writes and System-Admin-only reads (M15)."""
from django.core.management import call_command
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.audit.services import write_audit
from apps.common.enums import RoleCode


class AuditAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        cls.admin = User.objects.create_user("auditor", password="pw12345678")
        cls.admin.roles.add(Role.objects.get(pk=RoleCode.SYSTEM_ADMIN))
        cls.medic = User.objects.create_user("auditmedic", password="pw12345678")
        cls.medic.roles.add(Role.objects.get(pk=RoleCode.MEDIC))

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_audit_events_are_appended(self):
        event = write_audit(
            action="test.event",
            entity="learner",
            entity_id=42,
            actor=self.admin,
            after={"changed": True},
        )
        self.assertIsNotNone(event.pk)
        self.assertEqual(AuditEvent.objects.get(pk=event.pk).after, {"changed": True})

    def test_system_admin_can_read_and_filter(self):
        write_audit(action="one.event", entity="learner", entity_id=1)
        write_audit(action="two.event", entity="learner", entity_id=2)
        self._auth(self.admin)
        response = self.client.get("/api/v1/audit-events/?action=one.event")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["data"][0]["action"], "one.event")

    def test_non_admin_cannot_read_audit_trail(self):
        self._auth(self.medic)
        self.assertEqual(self.client.get("/api/v1/audit-events/").status_code, 403)

    def test_audit_trail_is_read_only(self):
        self._auth(self.admin)
        response = self.client.post(
            "/api/v1/audit-events/", {"action": "forged"}, format="json"
        )
        self.assertIn(response.status_code, (403, 405))
