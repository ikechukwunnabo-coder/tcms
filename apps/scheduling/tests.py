"""Scheduling — capacity & booking allocation tests (design 03 §6; SAD §7–§8)."""
from datetime import date

from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.catalogue.models import Course
from apps.common.enums import BookingState, EnrolmentStatus, SessionStatus
from apps.integration.models import OutboxEvent
from apps.learners.models import Learner
from apps.scheduling import services as svc
from apps.scheduling.models import CourseSession, Venue


def make_course(code="TEST"):
    return Course.objects.create(course_code=code, name=f"{code} course", duration_days=1)


def make_session(
    course, start, capacity=10, reserve_pct=0, status=SessionStatus.OPEN, venue=None, end=None
):
    return CourseSession.objects.create(
        course=course,
        start_date=start,
        end_date=end or start,
        capacity=capacity,
        reserve_pct=reserve_pct,
        status=status,
        venue=venue,
    )


def make_learner(badge="L1"):
    return Learner.objects.create(badge_no=badge, surname="Tester")


class CapacityServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_data", verbosity=0)

    def test_reserve_headroom_reduces_commit_ceiling(self):
        session = make_session(make_course(), date(2026, 3, 2), capacity=10, reserve_pct=10)
        # 10 seats, 10% reserve -> new bookings capped at 9
        self.assertEqual(svc.effective_capacity(session), 9)
        self.assertEqual(svc.effective_capacity(session, for_carry_forward=True), 10)
        self.assertEqual(svc.seats_available(session), 9)

    def test_unlimited_capacity(self):
        session = make_session(make_course(), date(2026, 3, 2), capacity=None)
        self.assertIsNone(svc.effective_capacity(session))
        self.assertIsNone(svc.seats_available(session))
        self.assertTrue(svc.can_confirm(session))

    def test_can_confirm_boundary(self):
        # 5 seats, 10% reserve -> new bookings capped at 4, carry-forward may use the 5th.
        session = make_session(make_course(), date(2026, 3, 2), capacity=5, reserve_pct=10)
        session.seats_taken = 4
        session.save(update_fields=["seats_taken"])
        self.assertFalse(svc.can_confirm(session))  # would eat the reserve
        self.assertTrue(svc.can_confirm(session, for_carry_forward=True))

    def test_availability_read_model(self):
        session = make_session(make_course(), date(2026, 3, 2), capacity=4, reserve_pct=0)
        data = svc.availability(session)
        self.assertEqual(data["seats_available"], 4)
        self.assertTrue(data["open"])


class FacilityCapacityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_data", verbosity=0)
        cls.course = make_course()
        cls.venue = Venue.objects.create(name="Hall A", capacity=5)

    @override_settings(ENFORCE_VENUE_EXCLUSIVITY=False)
    def test_venue_throughput_limits_concurrent_seats(self):
        first = make_session(
            self.course, date(2026, 3, 2), capacity=10, venue=self.venue
        )
        CourseSession.objects.filter(pk=first.pk).update(seats_taken=5)
        first.refresh_from_db()
        second = make_session(
            self.course, date(2026, 3, 2), capacity=10, venue=self.venue
        )
        self.assertFalse(svc.facility_capacity_available(second))
        self.assertFalse(svc.can_confirm(second))
        self.assertTrue(svc.facility_capacity_available(second, extra=0))

    @override_settings(ENFORCE_FACILITY_CAPACITY=False)
    def test_venue_exclusivity_blocks_overlapping_sessions(self):
        make_session(self.course, date(2026, 3, 2), end=date(2026, 3, 4), venue=self.venue)
        overlapping = make_session(
            self.course, date(2026, 3, 4), end=date(2026, 3, 6), venue=self.venue
        )
        self.assertFalse(svc.venue_available(overlapping))
        self.assertFalse(svc.can_confirm(overlapping))

    @override_settings(ENFORCE_FACILITY_CAPACITY=False)
    def test_venue_exclusivity_allows_non_overlapping_sessions(self):
        make_session(self.course, date(2026, 3, 2), end=date(2026, 3, 4), venue=self.venue)
        later = make_session(
            self.course, date(2026, 3, 5), end=date(2026, 3, 6), venue=self.venue
        )
        self.assertTrue(svc.venue_available(later))
        self.assertTrue(svc.can_confirm(later))

    def test_availability_reports_facility_state(self):
        session = make_session(self.course, date(2026, 3, 2), capacity=4, venue=self.venue)
        data = svc.availability(session)
        self.assertEqual(data["venue_capacity"], 5)
        self.assertTrue(data["facility_available"])
        self.assertTrue(data["open"])


class BookingAllocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_data", verbosity=0)

    def setUp(self):
        self.course = make_course()

    def test_book_creates_registered_enrolment(self):
        session = make_session(self.course, date(2026, 3, 2))
        learner = make_learner()
        enrolment = svc.book(learner, session)
        self.assertEqual(enrolment.state, BookingState.REGISTERED)
        self.assertEqual(enrolment.status, EnrolmentStatus.BOOKED)
        self.assertIsNone(enrolment.session)
        self.assertEqual(enrolment.requested_session_id, session.pk)
        self.assertTrue(enrolment.booking_ref)

    def test_confirm_secures_requested_session(self):
        session = make_session(self.course, date(2026, 3, 2), capacity=10)
        enrolment = svc.book(make_learner(), session)
        svc.confirm(enrolment)
        enrolment.refresh_from_db()
        session.refresh_from_db()
        self.assertEqual(enrolment.state, BookingState.CONFIRMED)
        self.assertEqual(enrolment.session_id, session.pk)
        self.assertEqual(enrolment.original_session_id, session.pk)
        self.assertIsNotNone(enrolment.seat_allocated_at)
        self.assertIsNotNone(enrolment.payment_verified_at)
        self.assertEqual(session.seats_taken, 1)
        self.assertTrue(OutboxEvent.objects.filter(topic="booking.allocated").exists())

    def test_carry_forward_when_requested_full(self):
        requested = make_session(self.course, date(2026, 3, 2), capacity=1, reserve_pct=0)
        requested.seats_taken = 1  # full
        requested.save(update_fields=["seats_taken"])
        later = make_session(self.course, date(2026, 3, 9), capacity=5)

        enrolment = svc.book(make_learner(), requested)
        svc.confirm(enrolment)
        enrolment.refresh_from_db()
        later.refresh_from_db()
        self.assertEqual(enrolment.state, BookingState.CONFIRMED)
        self.assertEqual(enrolment.session_id, later.pk)
        self.assertEqual(enrolment.original_session_id, requested.pk)  # SAD §8
        self.assertEqual(later.seats_taken, 1)

    def test_overflow_when_no_forward_capacity(self):
        requested = make_session(self.course, date(2026, 3, 2), capacity=1, reserve_pct=0)
        requested.seats_taken = 1
        requested.save(update_fields=["seats_taken"])

        enrolment = svc.book(make_learner(), requested)
        svc.confirm(enrolment)
        enrolment.refresh_from_db()
        self.assertEqual(enrolment.state, BookingState.OVERFLOW)
        self.assertEqual(enrolment.status, EnrolmentStatus.WAITLISTED)
        self.assertTrue(OutboxEvent.objects.filter(topic="booking.overflow").exists())

    def test_cannot_confirm_twice(self):
        session = make_session(self.course, date(2026, 3, 2))
        enrolment = svc.book(make_learner(), session)
        svc.confirm(enrolment)
        with self.assertRaises(svc.SeatUnavailable):
            svc.confirm(enrolment)


class BookingAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)
        cls.course = make_course()
        cls.accounts = User.objects.create_user("acct", password="pw")
        cls.accounts.roles.add(Role.objects.get(pk=6))  # Accounts
        cls.medic = User.objects.create_user("med", password="pw")
        cls.medic.roles.add(Role.objects.get(pk=4))  # Medic

    def _auth(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def test_account_officer_can_confirm(self):
        session = make_session(self.course, date(2026, 3, 2))
        enrolment = svc.book(make_learner(), session)
        self._auth(self.accounts)
        response = self.client.post(f"/api/v1/enrolments/{enrolment.pk}/confirm/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["state"], "confirmed")

    def test_medic_cannot_confirm(self):
        session = make_session(self.course, date(2026, 3, 2))
        enrolment = svc.book(make_learner(), session)
        self._auth(self.medic)
        response = self.client.post(f"/api/v1/enrolments/{enrolment.pk}/confirm/")
        self.assertEqual(response.status_code, 403)

    def test_availability_endpoint(self):
        session = make_session(self.course, date(2026, 3, 2), capacity=8, reserve_pct=0)
        self._auth(self.accounts)
        response = self.client.get(f"/api/v1/sessions/{session.pk}/availability/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["seats_available"], 8)
