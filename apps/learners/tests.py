from datetime import date

from django.test import SimpleTestCase

from apps.learners import services as svc


class AgeGateTests(SimpleTestCase):
    def test_age_on(self):
        self.assertEqual(svc.age_on(date(2000, 6, 15), date(2026, 6, 14)), 25)
        self.assertEqual(svc.age_on(date(2000, 6, 15), date(2026, 6, 15)), 26)

    def test_assert_min_age(self):
        self.assertTrue(svc.assert_min_age(date(2000, 1, 1), date(2026, 1, 1)))
        with self.assertRaises(svc.AgeError):
            svc.assert_min_age(date(2010, 1, 1), date(2026, 1, 1))

    def test_missing_birth_date(self):
        with self.assertRaises(svc.AgeError):
            svc.assert_min_age(None)
