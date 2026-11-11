from datetime import date

from django.core.management import call_command
from django.test import SimpleTestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.accounts.models import Role, User
from apps.catalogue.models import Course, CourseModule
from apps.common.enums import RoleCode
from apps.delivery import services as svc
from apps.delivery.models import DailyMedicalCheck, TrainingInstructor, TrainingRecord
from apps.learners.models import Learner
from apps.reference.models import Company
from apps.scheduling.models import Instructor
from apps.workflow.models import WorkflowStatus
from apps.workflow.services import advance


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

class TrainingWorkspaceAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_roles", verbosity=0)
        call_command("seed_data", verbosity=0)
        cls.admin = User.objects.create_user("workspace_admin", password="pw")
        cls.admin.roles.add(Role.objects.get(pk=RoleCode.ADMIN))
        cls.learner = Learner.objects.create(
            badge_no="WS001",
            surname="Workspace",
            first_name="Learner",
            vantage_id="VAN-WS-001",
            birth_date=date(1990, 1, 1),
        )
        cls.course = Course.objects.get(course_code="BOSIET")
        cls.record = TrainingRecord.objects.create(
            learner=cls.learner,
            course=cls.course,
            status=WorkflowStatus.objects.get(pk=1),
            start_date=date(2026, 3, 2),
        )
        cls.instructor = Instructor.objects.create(full_name="Capt. Test")
        cls.module = CourseModule.objects.get(name="Sea Survival")
        TrainingInstructor.objects.create(
            training_record=cls.record,
            instructor=cls.instructor,
            module=cls.module,
            training_date=date(2026, 3, 2),
        )
        DailyMedicalCheck.objects.create(
            training_record=cls.record,
            check_date=date(2026, 3, 2),
            systolic=120,
            diastolic=80,
            created_by=cls.admin,
        )

    def setUp(self):
        token, _ = Token.objects.get_or_create(user=self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_workspace_exposes_operational_sections(self):
        response = self.client.get(f"/api/v1/training-records/{self.record.pk}/workspace/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["learner_detail"]["vantage_id"], "VAN-WS-001")
        self.assertEqual(response.data["training_instructors"][0]["module_name"], "Sea Survival")
        self.assertEqual(response.data["medical_checks"][0]["systolic"], 120)
        self.assertEqual(response.data["course_detail"]["course_code"], "BOSIET")

    def test_date_and_status_filters(self):
        response = self.client.get(
            "/api/v1/training-records/",
            {"start_date_after": "2026-03-01", "start_date_before": "2026-03-31", "status": 1},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        response = self.client.get("/api/v1/training-records/", {"status": 2})
        self.assertEqual(response.data["total"], 0)

    def test_bulk_workflow_action(self):
        second = TrainingRecord.objects.create(
            learner=self.learner,
            course=self.course,
            status=WorkflowStatus.objects.get(pk=1),
        )
        response = self.client.post(
            "/api/v1/approvals/bulk/",
            {"ids": [self.record.pk, second.pk], "action": "approve"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["succeeded"], 2)
        self.record.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(self.record.status_id, 2)
        self.assertEqual(second.status_id, 2)

    def test_my_activity_returns_recent_actions(self):
        advance(self.record, self.admin)
        response = self.client.get("/api/v1/approvals/my-activity/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["recent"]), 1)
        self.assertEqual(response.data["recent"][0]["training_record"], self.record.pk)

    def test_pending_tasks_supports_search_date_and_pagination(self):
        company = Company.objects.create(agencode="PEND01", name="Pending Company")
        self.learner.company = company
        self.learner.save(update_fields=["company"])
        second = TrainingRecord.objects.create(
            learner=self.learner,
            course=self.course,
            status=WorkflowStatus.objects.get(pk=1),
            start_date=date(2026, 3, 3),
        )

        response = self.client.get(
            "/api/v1/approvals/pending-tasks/",
            {"search": "Pending Company", "date": "2026-03-02"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["data"][0]["company_name"], "Pending Company")
        self.assertEqual(response.data["data"][0]["course_name"], self.course.name)

        response = self.client.get(
            "/api/v1/approvals/pending-tasks/",
            {"search": "no such pending task"},
        )
        self.assertEqual(response.data["total"], 0)

        response = self.client.get(
            "/api/v1/approvals/pending-tasks/",
            {"page": 2, "page_size": 1},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 2)
        self.assertEqual(response.data["page"], 2)
        self.assertEqual(len(response.data["data"]), 1)
        self.assertIn(response.data["data"][0]["id"], {self.record.pk, second.pk})

        response = self.client.get(
            "/api/v1/approvals/pending-tasks/",
            {"date": "not-a-date"},
        )
        self.assertEqual(response.status_code, 400)

    def test_resend_cji_without_enrolment_is_rejected(self):
        response = self.client.post(
            f"/api/v1/training-records/{self.record.pk}/resend-cji/"
        )
        self.assertEqual(response.status_code, 400)

    def test_daily_medical_check_create_and_update(self):
        response = self.client.post(
            "/api/v1/medical-checks/",
            {
                "training_record": self.record.pk,
                "check_date": "2026-03-03",
                "systolic": 118,
                "diastolic": 76,
                "notes": "Fit for water work",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        check_pk = response.data["id"]
        self.assertEqual(response.data["created_by"], self.admin.pk)

        response = self.client.patch(
            f"/api/v1/medical-checks/{check_pk}/",
            {"systolic": 122, "notes": "Rechecked"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["systolic"], 122)
        self.assertEqual(response.data["notes"], "Rechecked")

    def test_daily_medical_check_write_requires_clinical_role(self):
        front_desk = User.objects.create_user("workspace_frontdesk", password="pw")
        front_desk.roles.add(Role.objects.get(pk=RoleCode.FRONT_DESK))
        token, _ = Token.objects.get_or_create(user=front_desk)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.post(
            "/api/v1/medical-checks/",
            {
                "training_record": self.record.pk,
                "check_date": "2026-03-04",
                "systolic": 118,
                "diastolic": 76,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_training_instructor_assignment(self):
        second_instructor = Instructor.objects.create(full_name="Second Instructor")
        response = self.client.post(
            "/api/v1/training-instructors/",
            {
                "training_record": self.record.pk,
                "instructor": second_instructor.pk,
                "module": self.module.pk,
                "training_date": "2026-03-03",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["module_name"], "Sea Survival")
