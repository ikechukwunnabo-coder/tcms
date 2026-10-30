from datetime import date

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import Role, User
from apps.catalogue.models import Course
from apps.delivery.models import TrainingRecord
from apps.learners.models import Learner
from apps.workflow import services as wf
from apps.workflow.models import WorkflowStatus


class WorkflowEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)
        cls.learner = Learner.objects.create(
            badge_no="W001", surname="Doe", first_name="John", birth_date=date(1990, 1, 1)
        )
        cls.course = Course.objects.get(course_code="BOSIET")
        cls.admin_user = User.objects.create_user("wfadmin", password="x")
        cls.admin_user.roles.add(Role.objects.get(pk=2))  # ADMIN
        cls.nobody = User.objects.create_user("nobody", password="x")

    def _record(self, status_id=1):
        return TrainingRecord.objects.create(
            learner=self.learner,
            course=self.course,
            status=WorkflowStatus.objects.get(pk=status_id),
        )

    def test_advance_by_owner_role_r_wf_01_02(self):
        record = self._record()
        new_status = wf.advance(record, self.admin_user)
        record.refresh_from_db()
        self.assertEqual(new_status.id, 2)
        self.assertEqual(record.status_id, 2)

    def test_wrong_role_rejected_r_wf_02(self):
        record = self._record()
        with self.assertRaises(wf.RoleNotPermitted):
            wf.advance(record, self.nobody)

    def test_reason_required_r_wf_03(self):
        record = self._record()
        with self.assertRaises(wf.ReasonRequired):
            wf.advance(record, self.admin_user, action="reject")

    def test_terminal_cannot_advance_r_wf_04(self):
        record = self._record(status_id=12)
        with self.assertRaises(wf.InvalidTransition):
            wf.advance(record, self.admin_user)

    def test_history_and_audit_written_r_wf_06(self):
        record = self._record()
        wf.advance(record, self.admin_user)
        self.assertEqual(record.approvals.count(), 1)
        self.assertEqual(record.status_history.count(), 1)

    def test_reject_then_reenter_r_wf_05(self):
        record = self._record()
        wf.advance(record, self.admin_user, action="reject", reason="bad docs")
        record.refresh_from_db()
        self.assertEqual(record.status_id, 14)
        self.assertEqual(record.reject_reason, "bad docs")
        wf.reenter(record, self.admin_user)
        record.refresh_from_db()
        self.assertEqual(record.status_id, 1)

    def test_cancel_is_terminal_r_wf_04(self):
        record = self._record()
        wf.advance(record, self.admin_user, action="cancel", reason="duplicate")
        record.refresh_from_db()
        self.assertEqual(record.status_id, 13)
        with self.assertRaises(wf.InvalidTransition):
            wf.advance(record, self.admin_user)
