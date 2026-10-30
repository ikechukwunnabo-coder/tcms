from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.certification.models import Certificate, IDCard
from apps.common.enums import WorkflowStatusCode
from apps.delivery.models import TrainingRecord
from apps.integration.models import SeedMarker
from apps.learners.models import Learner
from apps.payroll.models import Employee
from apps.portal.models import PortalAccount


class SeedDemoTests(TestCase):
    def setUp(self):
        call_command("seed_roles")
        call_command("seed_data")

    def test_builds_full_chain(self):
        call_command("seed_demo")
        self.assertGreaterEqual(Learner.objects.count(), len(list(WorkflowStatusCode)))
        states = set(TrainingRecord.objects.values_list("status_id", flat=True))
        self.assertEqual(states, {int(c) for c in WorkflowStatusCode})
        self.assertTrue(Certificate.objects.exists())
        self.assertTrue(
            Certificate.objects.filter(signature_applied=True, seal_applied=True).exists()
        )
        self.assertTrue(IDCard.objects.exists())
        self.assertTrue(SeedMarker.objects.filter(tier="SEED_DEMO").exists())
        self.assertEqual(PortalAccount.objects.count(), 2)
        self.assertTrue(
            PortalAccount.objects.filter(
                account_type="individual", user__email_verified=True, learner__isnull=False
            ).exists()
        )
        self.assertTrue(
            PortalAccount.objects.filter(
                account_type="corporate_lead", corporate_account__isnull=False
            ).exists()
        )
        self.assertTrue(User.objects.filter(username="demo_corporate@tcms.local").exists())
        self.assertTrue(User.objects.filter(username="demo_reports").exists())

    def test_idempotent_and_reset(self):
        call_command("seed_demo")
        count = TrainingRecord.objects.count()
        call_command("seed_demo")
        self.assertEqual(TrainingRecord.objects.count(), count)
        call_command("seed_demo", "--reset")
        self.assertEqual(TrainingRecord.objects.count(), count)
        self.assertEqual(
            set(TrainingRecord.objects.values_list("status_id", flat=True)),
            {int(c) for c in WorkflowStatusCode},
        )


class SeedLoadTests(TestCase):
    def setUp(self):
        call_command("seed_roles")
        call_command("seed_data")

    def test_creates_and_resets_volume(self):
        call_command("seed_load", learners=5, records=12, employees=2, verbosity=0)
        self.assertEqual(Learner.objects.filter(badge_no__startswith="LOAD-").count(), 5)
        self.assertEqual(
            TrainingRecord.objects.filter(learner__badge_no__startswith="LOAD-").count(),
            12,
        )
        self.assertEqual(Employee.objects.filter(staff_no__startswith="LOAD-").count(), 2)

        call_command("seed_load", "--reset", verbosity=0)
        self.assertFalse(Learner.objects.filter(badge_no__startswith="LOAD-").exists())
        self.assertFalse(TrainingRecord.objects.filter(learner__badge_no__startswith="LOAD-").exists())
        self.assertFalse(Employee.objects.filter(staff_no__startswith="LOAD-").exists())
