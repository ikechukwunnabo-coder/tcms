"""Portal registration & authentication tests (design 04 §5.1; spec BR-1/BR-15)."""
import re
from datetime import date, timedelta

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.billing.models import CorporateAccount
from apps.common.enums import LearnerType, PortalAccountType
from apps.learners.models import Learner
from apps.portal import services as svc
from apps.portal.models import EmailVerification, PortalAccount

ADULT = date(1990, 1, 1)
MINOR = str(date.today().replace(year=date.today().year - 10))


def token_from_outbox(index: int = -1) -> str:
    match = re.search(r"token=([\w\-]+)", mail.outbox[index].body)
    assert match, "no token in verification email"
    return match.group(1)


class RegistrationTests(APITestCase):
    def setUp(self):
        cache.clear()

    def _register(self, **overrides):
        payload = {
            "email": "alice@example.com",
            "password": "strongpass123",
            "first_name": "Alice",
            "last_name": "Ade",
            "birth_date": "1990-01-01",
        }
        payload.update(overrides)
        return self.client.post("/api/v1/auth/register", payload, format="json")

    def test_register_creates_unverified_user_and_sends_email(self):
        response = self._register()
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="alice@example.com")
        self.assertFalse(user.email_verified)
        self.assertTrue(PortalAccount.objects.filter(user=user).exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_register_under_18_is_422(self):
        response = self._register(birth_date=MINOR)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["error"], "under_min_age")
        self.assertFalse(User.objects.filter(email="alice@example.com").exists())

    def test_register_duplicate_email_is_409(self):
        self._register()
        response = self._register()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"], "email_taken")

    def test_register_weak_password_is_422(self):
        response = self._register(password="password123")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["error"], "weak_password")
        self.assertFalse(User.objects.filter(email="alice@example.com").exists())

    def test_register_is_rate_limited(self):
        for index in range(20):
            response = self._register(email=f"bulk{index}@example.com")
            self.assertEqual(response.status_code, 201)
        response = self._register(email="bulk20@example.com")
        self.assertEqual(response.status_code, 429)


class VerifyAndLoginTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client.post(
            "/api/v1/auth/register",
            {
                "email": "bob@example.com",
                "password": "strongpass123",
                "first_name": "Bob",
                "last_name": "Bello",
                "birth_date": "1988-05-05",
            },
            format="json",
        )
        self.token = token_from_outbox()

    def _login(self):
        return self.client.post(
            "/api/v1/auth/login",
            {"email": "bob@example.com", "password": "strongpass123"},
            format="json",
        )

    def test_login_blocked_before_verification(self):
        response = self._login()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"], "email_not_verified")

    def test_verify_creates_learner_and_unblocks_login(self):
        response = self.client.post(
            "/api/v1/auth/verify-email", {"token": self.token}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        account = PortalAccount.objects.get(user__email="bob@example.com")
        self.assertIsNotNone(account.learner_id)
        self.assertTrue(account.learner.badge_no.startswith("WEB"))
        self.assertEqual(account.learner.surname, "Bello")
        self.assertTrue(User.objects.get(email="bob@example.com").email_verified)

        login = self._login()
        self.assertEqual(login.status_code, 200)
        self.assertIn("token", login.data)

    def test_token_is_single_use(self):
        self.client.post("/api/v1/auth/verify-email", {"token": self.token}, format="json")
        again = self.client.post(
            "/api/v1/auth/verify-email", {"token": self.token}, format="json"
        )
        self.assertEqual(again.status_code, 400)
        self.assertEqual(again.data["error"], "invalid_token")

    def test_invalid_token_is_400(self):
        response = self.client.post(
            "/api/v1/auth/verify-email", {"token": "nonsense"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "invalid_token")

    def test_expired_token_is_400(self):
        user = User.objects.get(email="bob@example.com")
        EmailVerification.objects.filter(user=user).update(
            expires_at=timezone.now() - timedelta(days=1)
        )
        response = self.client.post(
            "/api/v1/auth/verify-email", {"token": self.token}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "token_expired")


class ResendVerificationTests(APITestCase):
    def setUp(self):
        cache.clear()

    @override_settings(PORTAL_RESEND_LIMIT=2)
    def test_resend_sends_new_token_and_is_rate_limited(self):
        svc.register_individual(
            email="carol@example.com",
            password="strongpass123",
            first_name="Carol",
            last_name="Cole",
            birth_date=ADULT,
        )
        self.assertEqual(len(mail.outbox), 1)
        response = self.client.post(
            "/api/v1/auth/resend-verification", {"email": "carol@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)

        # second + third calls exceed the limit of 2 within the window
        self.client.post(
            "/api/v1/auth/resend-verification", {"email": "carol@example.com"}, format="json"
        )
        third = self.client.post(
            "/api/v1/auth/resend-verification", {"email": "carol@example.com"}, format="json"
        )
        self.assertEqual(third.status_code, 429)

    def test_resend_unknown_email_is_generic_200(self):
        response = self.client.post(
            "/api/v1/auth/resend-verification", {"email": "nobody@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)


class StaffLoginUnchangedTests(APITestCase):
    def test_staff_user_logs_in_with_username(self):
        User.objects.create_user("staffer", password="strongpass123")
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "staffer", "password": "strongpass123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)


class CorporateAccountTests(APITestCase):
    """Corporate accounts & nominees (spec §9.6, BR-16)."""

    def setUp(self):
        self.lead = User.objects.create_user(
            "lead@corp.com", email="lead@corp.com", password="strongpass123"
        )
        PortalAccount.objects.create(user=self.lead)
        self.client.force_authenticate(self.lead)

    def _create_account(self, **overrides):
        payload = {"name": "Acme Marine Ltd", "terms_days": 30}
        payload.update(overrides)
        return self.client.post("/api/v1/corporate/accounts", payload, format="json")

    def _add_nominee(self, **overrides):
        payload = {
            "surname": "Okafor",
            "first_name": "Chidi",
            "sex": "M",
            "birth_date": "1992-06-15",
        }
        payload.update(overrides)
        return self.client.post("/api/v1/corporate/nominees", payload, format="json")

    def test_create_account_requires_auth(self):
        self.client.force_authenticate(None)
        self.assertEqual(self._create_account().status_code, 401)

    def test_create_account_upgrades_lead_and_links_portal(self):
        response = self._create_account()
        self.assertEqual(response.status_code, 201)
        account = CorporateAccount.objects.get()
        self.assertEqual(account.lead_user, self.lead)
        self.assertEqual(account.lead_email, "lead@corp.com")
        self.assertEqual(account.terms_days, 30)
        pa = PortalAccount.objects.get(user=self.lead)
        self.assertEqual(pa.account_type, PortalAccountType.CORPORATE_LEAD)
        self.assertEqual(pa.corporate_account, account)

    def test_second_account_for_same_lead_is_409(self):
        self._create_account()
        again = self._create_account()
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.data["error"], "corporate_account_exists")

    def test_nominees_require_a_corporate_account(self):
        response = self.client.get("/api/v1/corporate/nominees")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"], "corporate_account_required")

    def test_add_nominee_creates_corporate_learner(self):
        self._create_account()
        response = self._add_nominee()
        self.assertEqual(response.status_code, 201)
        learner = Learner.objects.get(surname="Okafor")
        self.assertEqual(learner.learner_type, LearnerType.CORPORATE)
        self.assertEqual(learner.corporate_account, CorporateAccount.objects.get())
        self.assertTrue(learner.badge_no.startswith("CORP"))

    def test_add_under_18_nominee_is_422(self):
        self._create_account()
        response = self._add_nominee(birth_date=str(MINOR))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["error"], "under_min_age")

    def test_duplicate_nominee_is_409(self):
        self._create_account()
        self._add_nominee()
        response = self._add_nominee()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"], "duplicate_nominee")

    def test_list_and_update_nominee(self):
        self._create_account()
        nominee_id = self._add_nominee().data["id"]
        listing = self.client.get("/api/v1/corporate/nominees")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.data), 1)

        updated = self.client.patch(
            f"/api/v1/corporate/nominees/{nominee_id}",
            {"first_name": "Chidiebere"},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["first_name"], "Chidiebere")

    def test_remove_nominee(self):
        self._create_account()
        nominee_id = self._add_nominee().data["id"]
        response = self.client.delete(f"/api/v1/corporate/nominees/{nominee_id}")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Learner.objects.filter(pk=nominee_id).exists())

    def test_remove_nominee_with_held_booking_is_409(self):
        from apps.common.enums import BookingState
        from apps.scheduling.models import Enrolment

        self._create_account()
        nominee_id = self._add_nominee().data["id"]
        Enrolment.objects.create(
            learner_id=nominee_id, state=BookingState.CONFIRMED
        )
        response = self.client.delete(f"/api/v1/corporate/nominees/{nominee_id}")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"], "nominee_has_confirmed_booking")
        self.assertTrue(Learner.objects.filter(pk=nominee_id).exists())

    def test_lead_cannot_touch_another_accounts_nominee(self):
        self._create_account()
        other_lead = User.objects.create_user("other@corp.com", password="strongpass123")
        other_account = CorporateAccount.objects.create(
            name="Other Ltd", lead_user=other_lead, lead_email="other@corp.com"
        )
        nominee = Learner.objects.create(
            badge_no="CORPX0001", surname="Eze", corporate_account=other_account
        )
        response = self.client.delete(f"/api/v1/corporate/nominees/{nominee.pk}")
        self.assertEqual(response.status_code, 404)


class CorporateAccountViewSetTests(APITestCase):
    """Canonical M10 ``/v1/corporate-accounts`` (admin/accounts RBAC)."""

    def setUp(self):
        self.admin = User.objects.create_user("admin", password="strongpass123")
        role, _ = Role.objects.get_or_create(id=2, defaults={"code": "admin", "name": "Admin"})
        self.admin.roles.add(role)
        self.no_role = User.objects.create_user("norole", password="strongpass123")

    def test_admin_can_list(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/v1/corporate-accounts/")
        self.assertEqual(response.status_code, 200)

    def test_roleless_user_denied(self):
        self.client.force_authenticate(self.no_role)
        response = self.client.get("/api/v1/corporate-accounts/")
        self.assertEqual(response.status_code, 403)


# ── Course Joining Instructions (spec §9.7, BR-20) ───────────────────────────


def _make_course(code="CJI"):
    from apps.catalogue.models import Course

    return Course.objects.create(course_code=code, name=f"{code} course", duration_days=2)


def _make_session(course, start, capacity=10):
    from apps.common.enums import SessionStatus
    from apps.scheduling.models import CourseSession

    return CourseSession.objects.create(
        course=course, start_date=start, end_date=start, capacity=capacity,
        reserve_pct=0, status=SessionStatus.OPEN,
    )


def _verified_learner(email="lrn@example.com", badge="L900"):
    user = User.objects.create_user(email, email=email, password="strongpass123")
    learner = Learner.objects.create(badge_no=badge, surname="Learner")
    PortalAccount.objects.create(user=user, learner=learner)
    return user, learner


class CJITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_data", verbosity=0)

    def setUp(self):
        from datetime import date

        self.course = _make_course()
        self.session = _make_session(self.course, date(2026, 4, 6))

    def _confirm(self, learner, session=None):
        from apps.scheduling import services as sched

        enrolment = sched.book(learner, session or self.session)
        return sched.confirm(enrolment)

    def test_confirm_issues_cji_to_verified_learner_email(self):
        from apps.portal.models import JoiningInstruction

        user, learner = _verified_learner()
        enrolment = self._confirm(learner)
        ji = JoiningInstruction.objects.get(enrolment=enrolment, is_current=True)
        self.assertEqual(ji.delivery_status, "sent")
        self.assertEqual(ji.sent_to, "lrn@example.com")
        self.assertEqual(ji.version, 1)
        self.assertIn("CJI course", ji.payload)
        self.assertEqual(len(mail.outbox), 1)

    def test_nominee_cji_goes_only_to_lead_email(self):
        from apps.portal.models import JoiningInstruction

        lead = User.objects.create_user("lead@corp.com", email="lead@corp.com")
        account = CorporateAccount.objects.create(
            name="Acme Ltd", lead_user=lead, lead_email="lead@corp.com"
        )
        nominee = Learner.objects.create(
            badge_no="CORP0001", surname="Okafor", corporate_account=account
        )
        enrolment = self._confirm(nominee)
        ji = JoiningInstruction.objects.get(enrolment=enrolment, is_current=True)
        self.assertEqual(ji.sent_to, "lead@corp.com")

    def test_regenerate_same_session_is_idempotent(self):
        from apps.portal import cji
        from apps.portal.models import JoiningInstruction

        _, learner = _verified_learner()
        enrolment = self._confirm(learner)
        first = cji.regenerate_and_send(enrolment, self.session)
        self.assertEqual(JoiningInstruction.objects.filter(enrolment=enrolment).count(), 1)
        self.assertEqual(first.version, 1)

    def test_changed_session_supersedes_and_bumps_version(self):
        from datetime import date

        from apps.portal import cji
        from apps.portal.models import JoiningInstruction

        _, learner = _verified_learner()
        enrolment = self._confirm(learner)
        new_session = _make_session(self.course, date(2026, 5, 6))
        second = cji.regenerate_and_send(enrolment, new_session)
        self.assertEqual(second.version, 2)
        self.assertTrue(second.is_current)
        self.assertEqual(
            JoiningInstruction.objects.filter(enrolment=enrolment, is_current=True).count(), 1
        )
        old = JoiningInstruction.objects.get(enrolment=enrolment, version=1)
        self.assertFalse(old.is_current)
        self.assertEqual(old.delivery_status, "superseded")

    def test_undeliverable_booking_records_failed_without_raising(self):
        from apps.portal.models import JoiningInstruction

        learner = Learner.objects.create(badge_no="NOEMAIL", surname="Silent")
        enrolment = self._confirm(learner)
        ji = JoiningInstruction.objects.get(enrolment=enrolment, is_current=True)
        self.assertEqual(ji.delivery_status, "failed")
        self.assertEqual(ji.sent_to, "")
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_rerenders_without_version_bump(self):
        from apps.portal import cji
        from apps.portal.models import JoiningInstruction

        _, learner = _verified_learner()
        enrolment = self._confirm(learner)
        ji = cji.resend(enrolment)
        self.assertEqual(ji.version, 1)
        self.assertEqual(ji.delivery_status, "sent")
        self.assertEqual(JoiningInstruction.objects.filter(enrolment=enrolment).count(), 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_mark_bounced_sets_status(self):
        from apps.portal import cji

        _, learner = _verified_learner()
        enrolment = self._confirm(learner)
        ji = cji.mark_bounced(enrolment)
        self.assertEqual(ji.delivery_status, "bounced")

    def test_owner_can_fetch_cji_via_portal(self):
        user, learner = _verified_learner()
        enrolment = self._confirm(learner)
        self.client.force_authenticate(user)
        response = self.client.get(f"/api/v1/bookings/{enrolment.pk}/cji")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["version"], 1)

    def test_lead_can_fetch_nominee_cji(self):
        lead = User.objects.create_user("lead2@corp.com", email="lead2@corp.com")
        account = CorporateAccount.objects.create(
            name="Acme2", lead_user=lead, lead_email="lead2@corp.com"
        )
        nominee = Learner.objects.create(
            badge_no="CORP0002", surname="Eze", corporate_account=account
        )
        enrolment = self._confirm(nominee)
        self.client.force_authenticate(lead)
        response = self.client.get(f"/api/v1/bookings/{enrolment.pk}/cji")
        self.assertEqual(response.status_code, 200)

    def test_stranger_cannot_fetch_cji(self):
        _, learner = _verified_learner()
        enrolment = self._confirm(learner)
        stranger = User.objects.create_user("stranger", password="strongpass123")
        self.client.force_authenticate(stranger)
        response = self.client.get(f"/api/v1/bookings/{enrolment.pk}/cji")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"], "cji_access_denied")

    def test_front_desk_resends_and_roleless_denied(self):
        _, learner = _verified_learner()
        enrolment = self._confirm(learner)

        fd = User.objects.create_user("frontdesk", password="strongpass123")
        role, _ = Role.objects.get_or_create(
            id=3, defaults={"code": "front_desk", "name": "Front Desk"}
        )
        fd.roles.add(role)
        self.client.force_authenticate(fd)
        get_resp = self.client.get(f"/api/v1/enrolments/{enrolment.pk}/cji/")
        self.assertEqual(get_resp.status_code, 200)
        post_resp = self.client.post(f"/api/v1/enrolments/{enrolment.pk}/cji/resend/")
        self.assertEqual(post_resp.status_code, 200)

        norole = User.objects.create_user("norole2", password="strongpass123")
        self.client.force_authenticate(norole)
        denied = self.client.post(f"/api/v1/enrolments/{enrolment.pk}/cji/resend/")
        self.assertEqual(denied.status_code, 403)
