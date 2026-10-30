from datetime import date

from django.test import SimpleTestCase

from apps.delivery import services as svc


class ExpiryRuleTests(SimpleTestCase):
    def test_start_date_r_exp_02(self):
        self.assertEqual(svc.compute_start_date(date(2026, 1, 10), 4), date(2026, 1, 13))
        self.assertEqual(svc.compute_start_date(date(2026, 1, 10), 1), date(2026, 1, 10))
        self.assertIsNone(svc.compute_start_date(None, 4))

    def test_expiry_r_exp_01_r_cert_07(self):
        self.assertEqual(svc.compute_expiry(date(2026, 1, 13), 4), date(2030, 1, 12))
        self.assertEqual(svc.compute_expiry(date(2026, 1, 13), 1), date(2027, 1, 12))
        self.assertIsNone(svc.compute_expiry(date(2026, 1, 13), None))

    def test_expiry_leap_year(self):
        self.assertEqual(svc.compute_expiry(date(2024, 3, 1), 1), date(2025, 2, 28))

    def test_reminder_buckets_r_exp_03(self):
        self.assertEqual(svc.reminder_bucket(-1), "expired")
        self.assertEqual(svc.reminder_bucket(10), 30)
        self.assertEqual(svc.reminder_bucket(45), 60)
        self.assertEqual(svc.reminder_bucket(80), 90)
        self.assertIsNone(svc.reminder_bucket(200))


class RenewalWindowTests(SimpleTestCase):
    def setUp(self):
        self.today = date(2026, 1, 1)

    def test_window_inside(self):
        self.assertTrue(svc.is_within_renewal_window(date(2026, 3, 1), self.today))  # 59 days
        self.assertTrue(svc.is_within_renewal_window(date(2026, 1, 1), self.today))  # 0 days

    def test_window_outside(self):
        self.assertFalse(svc.is_within_renewal_window(date(2026, 6, 1), self.today))  # 151 days
        self.assertFalse(svc.is_within_renewal_window(date(2025, 12, 31), self.today))

    def test_assert_renewal_r_ren_02_03(self):
        self.assertTrue(svc.assert_renewal_allowed(None, self.today))
        self.assertTrue(svc.assert_renewal_allowed(date(2026, 2, 1), self.today))
        with self.assertRaises(svc.RenewalWindowError):
            svc.assert_renewal_allowed(date(2025, 12, 31), self.today)  # expired
        with self.assertRaises(svc.RenewalWindowError):
            svc.assert_renewal_allowed(date(2026, 6, 1), self.today)  # window not open
