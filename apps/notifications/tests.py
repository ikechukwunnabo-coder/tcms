"""Notifications — templates, delivery records and RBAC (M13)."""
from django.core.management import call_command
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.common.enums import RoleCode
from apps.notifications.models import Notification, NotificationTemplate


class NotificationAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        cls.admin = User.objects.create_user("notifadmin", password="pw12345678")
        cls.admin.roles.add(Role.objects.get(pk=RoleCode.ADMIN))
        cls.medic = User.objects.create_user("notifmedic", password="pw12345678")
        cls.medic.roles.add(Role.objects.get(pk=RoleCode.MEDIC))

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_admin_can_manage_templates(self):
        self._auth(self.admin)
        response = self.client.post(
            "/api/v1/notification-templates/",
            {"code": "learner.welcome", "channel": "email", "subject": "Welcome"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(
            NotificationTemplate.objects.filter(code="learner.welcome").exists()
        )
        self.assertEqual(
            self.client.get("/api/v1/notification-templates/").status_code, 200
        )

    def test_medic_cannot_read_or_write_notifications(self):
        self._auth(self.medic)
        self.assertEqual(
            self.client.get("/api/v1/notification-templates/").status_code, 403
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/notification-templates/",
                {"code": "x", "channel": "email"},
                format="json",
            ).status_code,
            403,
        )

    def test_admin_can_record_and_filter_notifications(self):
        Notification.objects.create(
            template_code="certificate.released",
            recipient="learner@example.com",
            status="sent",
        )
        Notification.objects.create(
            template_code="certificate.reminder",
            recipient="learner@example.com",
            status="queued",
        )
        self._auth(self.admin)
        response = self.client.get("/api/v1/notifications/?status=sent")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(
            response.data["data"][0]["template_code"], "certificate.released"
        )

    def test_notification_creation_ignores_client_sent_at(self):
        self._auth(self.admin)
        response = self.client.post(
            "/api/v1/notifications/",
            {
                "template_code": "test",
                "recipient": "a@example.com",
                "sent_at": "2000-01-01T00:00:00Z",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(Notification.objects.get(pk=response.data["id"]).sent_at)
