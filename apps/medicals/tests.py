from datetime import date

from django.test import TestCase

from apps.learners.models import Learner
from apps.medicals import services as med
from apps.medicals.models import Medical


class MedicalGateTests(TestCase):
    def setUp(self):
        self.learner = Learner.objects.create(badge_no="M001", surname="Med")
        self.on_date = date(2026, 1, 1)

    def test_valid_medical(self):
        Medical.objects.create(
            learner=self.learner,
            issued_date=date(2025, 1, 1),
            expiry_date=date(2027, 1, 1),
            active=True,
        )
        self.assertTrue(med.has_valid_medical(self.learner, self.on_date))

    def test_expired_medical(self):
        Medical.objects.create(
            learner=self.learner,
            issued_date=date(2024, 1, 1),
            expiry_date=date(2025, 1, 1),
            active=True,
        )
        self.assertFalse(med.has_valid_medical(self.learner, self.on_date))

    def test_inactive_medical(self):
        Medical.objects.create(
            learner=self.learner,
            issued_date=date(2025, 1, 1),
            expiry_date=date(2027, 1, 1),
            active=False,
        )
        self.assertFalse(med.has_valid_medical(self.learner, self.on_date))

    def test_assert_raises_when_missing(self):
        with self.assertRaises(med.MedicalGateError):
            med.assert_medical_valid(self.learner, self.on_date)
