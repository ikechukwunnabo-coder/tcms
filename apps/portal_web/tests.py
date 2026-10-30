"""Public portal (web) — registration, verification, sign-in, dashboard tests."""
import re
from datetime import date

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.catalogue.models import Course
from apps.certification.models import Certificate
from apps.common.enums import BookingState, EnrolmentStatus, SessionStatus
from apps.delivery.models import TrainingRecord
from apps.learners.models import Learner
from apps.portal.models import PortalAccount
from apps.scheduling.models import CourseSession, Enrolment
from apps.workflow.models import WorkflowStatus


def verification_token(index: int = -1) -> str:
    """Pull the token out of the last verification email."""
    body = mail.outbox[index].body
    match = re.search(r"token=([\w\-]+)", body)
    assert match, "no token in the verification email"
    return match.group(1)


def register_payload(email="ada@example.com", birth_date=date(1990, 1, 1)):
    return {
        "first_name": "Ada",
        "last_name": "Okafor",
        "email": email,
        "birth_date": birth_date,
        "sex": "F",
        "password": "strongpass123",
    }


class PublicPageTests(TestCase):
    def test_landing_page_is_public(self):
        response = self.client.get(reverse("portal_web:landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Training Centre")

    def test_register_page_renders(self):
        response = self.client.get(reverse("portal_web:register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create your learner account")

    def test_login_page_renders(self):
        response = self.client.get(reverse("portal_web:login"))
        self.assertEqual(response.status_code, 200)

    def test_pages_expose_accessibility_basics(self):
        response = self.client.get(reverse("portal_web:login"))
        self.assertContains(response, 'lang="en"')
        self.assertContains(response, "skip-link")
        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'autocomplete="current-password"')

    def test_portal_sets_a_strict_content_security_policy(self):
        response = self.client.get(reverse("portal_web:login"))
        csp = response["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("object-src 'none'", csp)

    def test_resend_page_renders(self):
        response = self.client.get(reverse("portal_web:resend-verification-page"))
        self.assertEqual(response.status_code, 200)


class RegistrationFlowTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_registration_creates_unverified_user_and_sends_email(self):
        response = self.client.post(reverse("portal_web:register"), register_payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("portal_web:registered"))
        user = User.objects.get(email="ada@example.com")
        self.assertFalse(user.email_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("ada@example.com", mail.outbox[0].to)

    def test_registration_under_18_is_rejected(self):
        payload = register_payload(birth_date=date(date.today().year - 10, 6, 1))
        response = self.client.post(reverse("portal_web:register"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "18 or older")
        self.assertFalse(User.objects.filter(email="ada@example.com").exists())

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user("ada", email="ada@example.com", password="strongpass123")
        response = self.client.post(reverse("portal_web:register"), register_payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")

    def test_short_password_is_rejected(self):
        payload = register_payload()
        payload["password"] = "short"
        response = self.client.post(reverse("portal_web:register"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, "id_password_error")
        self.assertFalse(User.objects.filter(email="ada@example.com").exists())

    def test_weak_password_is_rejected(self):
        payload = register_payload()
        payload["password"] = "password123"
        response = self.client.post(reverse("portal_web:register"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "too common")
        self.assertFalse(User.objects.filter(email="ada@example.com").exists())

    @override_settings(PORTAL_REGISTER_RATE_LIMIT=2)
    def test_registration_is_rate_limited(self):
        for index in range(2):
            payload = register_payload(email=f"reg{index}@example.com")
            response = self.client.post(reverse("portal_web:register"), payload)
            self.assertEqual(response.status_code, 302)
        payload = register_payload(email="reg2@example.com")
        response = self.client.post(reverse("portal_web:register"), payload)
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Too many registration attempts", status_code=429)
        self.assertFalse(User.objects.filter(email="reg2@example.com").exists())

    def test_verification_link_activates_account_after_confirmation(self):
        self.client.post(reverse("portal_web:register"), register_payload())
        token = verification_token()
        response = self.client.get(reverse("portal_web:verify-email-token", args=[token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm your email address")
        self.assertFalse(User.objects.get(email="ada@example.com").email_verified)

        response = self.client.post(
            reverse("portal_web:verify-email-token", args=[token]), {"token": token}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "email is verified")
        user = User.objects.get(email="ada@example.com")
        self.assertTrue(user.email_verified)
        self.assertIsNotNone(user.portal_account.learner_id)

    def test_verification_get_does_not_consume_the_token(self):
        self.client.post(reverse("portal_web:register"), register_payload())
        token = verification_token()
        for _ in range(2):
            response = self.client.get(
                reverse("portal_web:verify-email-token", args=[token])
            )
            self.assertEqual(response.status_code, 200)
        self.client.post(
            reverse("portal_web:verify-email-token", args=[token]), {"token": token}
        )
        self.assertTrue(User.objects.get(email="ada@example.com").email_verified)

    def test_token_cannot_be_reused(self):
        self.client.post(reverse("portal_web:register"), register_payload())
        token = verification_token()
        self.client.post(
            reverse("portal_web:verify-email-token", args=[token]), {"token": token}
        )
        response = self.client.get(reverse("portal_web:verify-email-token", args=[token]))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "not valid", status_code=400)

    def test_invalid_verification_token_is_reported(self):
        response = self.client.get(reverse("portal_web:verify-email-token", args=["nope"]))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "not valid", status_code=400)

    def test_emailed_link_uses_the_query_token_form(self):
        self.client.post(reverse("portal_web:register"), register_payload())
        body = mail.outbox[0].body
        self.assertIn("/portal/verify-email/?token=", body)
        token = verification_token()
        response = self.client.get(reverse("portal_web:verify-email"), {"token": token})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm your email address")
        response = self.client.post(
            reverse("portal_web:verify-email"), {"token": token}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "email is verified")


class ResendVerificationTests(TestCase):
    def test_resend_sends_a_new_email(self):
        self.client.post(reverse("portal_web:register"), register_payload())
        mail.outbox.clear()
        response = self.client.post(
            reverse("portal_web:resend-verification"), {"email": "ada@example.com"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_does_not_leak_account_existence(self):
        response = self.client.post(
            reverse("portal_web:resend-verification"), {"email": "nobody@example.com"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)


class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            "ada", email="ada@example.com", password="strongpass123", email_verified=True
        )

    def _request(self, email="ada@example.com"):
        return self.client.post(
            reverse("portal_web:password-reset"), {"email": email}
        )

    def _link(self):
        body = mail.outbox[-1].body
        match = re.search(r"/portal/password-reset/([^/]+)/([^/\s]+)/", body)
        assert match, "no reset link in email"
        return match.groups()

    def test_reset_request_sends_a_link(self):
        response = self._request()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/portal/password-reset/", mail.outbox[0].body)

    def test_unknown_email_does_not_reveal_account_existence(self):
        response = self._request("nobody@example.com")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_confirm_sets_password_and_token_is_single_use(self):
        self._request()
        uidb64, token = self._link()
        url = reverse(
            "portal_web:password-reset-confirm",
            kwargs={"uidb64": uidb64, "token": token},
        )
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(
            url, {"password": "Newstrongpass456", "confirm_password": "Newstrongpass456"}
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Newstrongpass456"))
        self.assertEqual(self.client.get(url).status_code, 400)

    def test_invalid_reset_token_is_rejected(self):
        response = self.client.get(
            reverse(
                "portal_web:password-reset-confirm",
                kwargs={"uidb64": "bad", "token": "bad"},
            )
        )
        self.assertEqual(response.status_code, 400)


class LoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            "ada", email="ada@example.com", password="strongpass123", email_verified=True
        )
        learner = Learner.objects.create(badge_no="WEB1", surname="Okafor")
        PortalAccount.objects.create(user=self.user, learner=learner)

    def test_login_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("portal_web:login"),
            {"email": "ada@example.com", "password": "strongpass123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("portal_web:dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_is_case_insensitive_on_email(self):
        response = self.client.post(
            reverse("portal_web:login"),
            {"email": "ADA@example.com", "password": "strongpass123"},
        )
        self.assertEqual(response.status_code, 302)

    def test_wrong_password_is_rejected(self):
        response = self.client.post(
            reverse("portal_web:login"),
            {"email": "ada@example.com", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email address or password")
        self.assertTrue(AuditEvent.objects.filter(action="auth.login_failed").exists())

    @override_settings(TRUST_X_FORWARDED_FOR=True)
    def test_forwarded_client_ip_is_used_when_trusted(self):
        self.client.post(
            reverse("portal_web:login"),
            {"email": "ada@example.com", "password": "wrong-password"},
            HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.1",
        )
        event = AuditEvent.objects.get(action="auth.login_failed")
        self.assertEqual(event.ip, "203.0.113.9")

    def test_unverified_account_cannot_sign_in(self):
        self.user.email_verified = False
        self.user.save(update_fields=["email_verified"])
        response = self.client.post(
            reverse("portal_web:login"),
            {"email": "ada@example.com", "password": "strongpass123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "verify your email")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("portal_web:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/login/", response.url)

    def test_logout_clears_the_session(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("portal_web:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_repeated_failed_logins_are_throttled(self):
        for _ in range(10):
            response = self.client.post(
                reverse("portal_web:login"),
                {"email": "ada@example.com", "password": "wrong-password"},
            )
            self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse("portal_web:login"),
            {"email": "ada@example.com", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Too many sign-in attempts", status_code=429)


class DashboardTests(TestCase):
    def setUp(self):
        call_command("seed_data", verbosity=0)
        self.user = User.objects.create_user(
            "ada", email="ada@example.com", password="strongpass123", email_verified=True
        )
        self.learner = Learner.objects.create(
            badge_no="WEB1", surname="Okafor", first_name="Ada", birth_date=date(1990, 1, 1)
        )
        self.account = PortalAccount.objects.create(user=self.user, learner=self.learner)
        self.course = Course.objects.create(course_code="WEB", name="Web course", duration_days=1)
        self.session = CourseSession.objects.create(
            course=self.course,
            start_date=date(2026, 5, 4),
            end_date=date(2026, 5, 4),
            capacity=10,
            reserve_pct=0,
            status=SessionStatus.OPEN,
        )
        self.enrolment = Enrolment.objects.create(
            learner=self.learner,
            session=self.session,
            requested_session=self.session,
            original_session=self.session,
            status=EnrolmentStatus.BOOKED,
            state=BookingState.CONFIRMED,
            booking_ref="WEBREF1",
        )
        self.client.force_login(self.user)

    def test_dashboard_lists_bookings(self):
        response = self.client.get(reverse("portal_web:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Web course")
        self.assertContains(response, "Confirmed")
        self.assertContains(response, "Your course bookings")
        self.assertContains(response, "Your certificates")

    def test_dashboard_lists_certificates(self):
        status = WorkflowStatus.objects.create(code="certified", name="Certified")
        record = TrainingRecord.objects.create(
            learner=self.learner,
            course=self.course,
            session=self.session,
            status=status,
            start_date=date(2026, 5, 4),
        )
        Certificate.objects.create(
            training_record=record,
            learner=self.learner,
            certificate_no="TC-1",
            issued_at=timezone.now(),
            expiry_date=date(2030, 5, 5),
        )
        response = self.client.get(reverse("portal_web:dashboard"))
        self.assertContains(response, "TC-1")
        self.assertContains(response, "Valid")
        self.assertContains(response, "Your certificates")

    def test_dashboard_hides_other_learners_bookings(self):
        other_user = User.objects.create_user(
            "eve", email="eve@example.com", password="strongpass123", email_verified=True
        )
        other_learner = Learner.objects.create(badge_no="WEB2", surname="Eve")
        PortalAccount.objects.create(user=other_user, learner=other_learner)
        self.client.force_login(other_user)
        response = self.client.get(reverse("portal_web:dashboard"))
        self.assertNotContains(response, "Web course")

    def test_cji_is_not_visible_to_another_learner(self):
        other_user = User.objects.create_user(
            "eve", email="eve@example.com", password="strongpass123", email_verified=True
        )
        other_learner = Learner.objects.create(badge_no="WEB2", surname="Eve")
        PortalAccount.objects.create(user=other_user, learner=other_learner)
        self.client.force_login(other_user)
        response = self.client.get(reverse("portal_web:booking-cji", args=[self.enrolment.pk]))
        self.assertEqual(response.status_code, 403)
