"""SEED_DEMO — a deterministic demo world (design ``02-database.md`` §8).

Contents: venues + sessions, learners (individual & corporate), enrolments,
medical fitness records, training records driven through every one of the 14
workflow states, certificates (with digital signature + seal) and ID cards.

Includes invoices/payments (M10), a posted payroll cycle (M11) and verified
portal logins for UAT/load (individual learner + corporate lead).

Depends on ``seed_roles`` + ``seed_data``. Re-running is a no-op unless
``--reset`` is passed. Deterministic: names/dates are drawn from a fixed RNG.
"""
from __future__ import annotations

import os
import random
import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.billing import services as billing_service
from apps.billing.models import CorporateAccount, Invoice, InvoiceSequence
from apps.catalogue.models import Course, CourseItem, CourseModule
from apps.certification import services as cert_service
from apps.certification.models import IDCard
from apps.common.enums import (
    BookingState,
    DocumentKind,
    EnrolmentStatus,
    Fitness,
    PortalAccountType,
    RoleCode,
    SessionStatus,
    Sex,
    WorkflowStatusCode,
)
from apps.delivery.models import (
    DailyMedicalCheck,
    TrainingInstructor,
    TrainingItem,
    TrainingRecord,
)
from apps.delivery.services import compute_expiry, compute_start_date
from apps.integration.models import SeedMarker
from apps.learners.models import Learner, LearnerContact, LearnerDocument
from apps.medicals.models import Medical
from apps.payroll import services as payroll_service
from apps.payroll.models import (
    Employee,
    EmployeePayElement,
    PayElement,
    PaymentFile,
    PayRun,
    Payslip,
    Provision,
    TimeEntry,
    Timesheet,
)
from apps.portal.models import PortalAccount
from apps.reference.models import Company, ContactType, Nationality, Position, State, Title
from apps.scheduling.models import CourseSession, Enrolment, Instructor, Venue
from apps.workflow import services as workflow
from apps.workflow.models import WorkflowStatus

TIER = "SEED_DEMO"
User = get_user_model()

DEMO_ROLES = [
    RoleCode.ADMIN,
    RoleCode.FRONT_DESK,
    RoleCode.MEDIC,
    RoleCode.TRAINING_COORDINATOR,
    RoleCode.ACCOUNTS,
    RoleCode.DUE_DILIGENCE,
    RoleCode.MD,
    RoleCode.PRINTER,
    RoleCode.VERIFICATION,
    RoleCode.INSTRUCTOR,
    RoleCode.REPORTS,
]

# one record per state, plus a few extra in-flight/completed for volume
TARGETS = [
    WorkflowStatusCode.NEW_RECORD,
    WorkflowStatusCode.ADMIN_DONE,
    WorkflowStatusCode.VERIFICATION_DONE,
    WorkflowStatusCode.FRONT_DESK_DONE,
    WorkflowStatusCode.MEDIC_DONE,
    WorkflowStatusCode.TRAINING_COORDINATOR_DONE,
    WorkflowStatusCode.ACCOUNTS_DONE,
    WorkflowStatusCode.DUE_DILIGENCE_DONE,
    WorkflowStatusCode.MD_DONE,
    WorkflowStatusCode.CERTIFICATE_DONE,
    WorkflowStatusCode.ID_CARD_DONE,
    WorkflowStatusCode.COMPLETED,
    WorkflowStatusCode.CANCELLED,
    WorkflowStatusCode.REJECTED,
    WorkflowStatusCode.COMPLETED,
    WorkflowStatusCode.TRAINING_COORDINATOR_DONE,
    WorkflowStatusCode.ID_CARD_DONE,
]

FIRST_NAMES = [
    "Chinedu", "Aisha", "Emeka", "Ngozi", "Tunde", "Fatima", "Ifeanyi", "Blessing",
    "Segun", "Halima", "Obinna", "Amaka", "Musa", "Chioma", "Yusuf", "Grace",
    "Kelechi", "Zainab", "Dapo", "Rita", "Uche", "Maryam", "Ibrahim", "Ada",
]
LAST_NAMES = [
    "Okafor", "Bello", "Adeyemi", "Nwosu", "Abubakar", "Eze", "Olawale", "Musa",
    "Chukwu", "Sani", "Balogun", "Udo", "Ibrahim", "Okonkwo", "Lawal", "Ekaete",
    "Yakubu", "Obi", "Danjuma", "Afolabi", "Ekpo", "Garba", "Nkemdirim", "Sule",
]

VENUES = [
    ("Lagos Training Centre", "Apapa, Lagos", 60),
    ("Port Harcourt Base", "Rumuokoro, Port Harcourt", 40),
    ("Onne Offshore Academy", "Onne, Rivers", 30),
]
INSTRUCTOR_NAMES = [
    "Capt. S. Adeyemi", "Engr. B. Ossai", "Dr. H. Lawal", "Mr. K. Etim",
]
CONTACT_DOMAINS = ["example.com"]


def _add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


class Command(BaseCommand):
    help = (
        "SEED_DEMO: deterministic demo world — venues, sessions, learners, "
        "enrolments, medicals, 14-state training records, certificates, ID cards."
    )

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete & rebuild demo world")
        parser.add_argument("--seed", type=int, default=20261019)

    @transaction.atomic
    def handle(self, *args, **options):
        self.rng = random.Random(options["seed"])
        self.today = date.today()
        self.demo_password = os.environ.get("DEMO_PASSWORD") or secrets.token_urlsafe(12)
        self.admin_username = os.environ.get("SEED_ADMIN_USER", "admin")

        if SeedMarker.objects.filter(tier=TIER).exists() and not options["reset"]:
            self.stdout.write(
                self.style.WARNING("SEED_DEMO already applied — pass --reset to rebuild.")
            )
            return

        self._prereqs()
        if options["reset"]:
            self._reset()

        admin = User.objects.get(username=self.admin_username)
        self._users()
        venues = self._venues()
        instructors = self._instructors()
        sessions = self._sessions(venues, admin)
        learners = self._learners()
        self._medicals(learners, admin)
        records = self._records(sessions, learners, instructors, admin)
        self._certificates(records, admin)
        invoices, payments = self._billing(learners, records, admin)
        portal_accounts = self._portal(learners)
        payroll_employees, payroll_payslips = self._payroll(admin)

        SeedMarker.objects.get_or_create(tier=TIER, code="demo")
        self.stdout.write(
            self.style.SUCCESS(
                f"SEED_DEMO complete: {Venue.objects.count()} venues, "
                f"{CourseSession.objects.count()} sessions, {Learner.objects.count()} learners, "
                f"{TrainingRecord.objects.count()} records, {Medical.objects.count()} medicals, "
                f"{invoices} invoices, {payments} payments, "
                f"{portal_accounts} portal accounts, "
                f"{payroll_employees} payroll employees, {payroll_payslips} payslips"
            )
        )

    # -- prerequisites / reset ------------------------------------------------

    def _prereqs(self):
        if WorkflowStatus.objects.count() != len(WorkflowStatusCode):
            raise CommandError("Run 'seed_roles' first (workflow statuses missing).")
        if not Course.objects.exists() or not State.objects.exists():
            raise CommandError("Run 'seed_data' first (catalogue / reference missing).")
        if not User.objects.filter(username=os.environ.get("SEED_ADMIN_USER", "admin")).exists():
            raise CommandError("Run 'seed_roles' first (admin user missing).")

    def _reset(self):
        demousers = User.objects.filter(username__startswith="demo_")
        PaymentFile.objects.all().delete()
        Provision.objects.all().delete()
        TimeEntry.objects.all().delete()
        Timesheet.objects.all().delete()
        Payslip.objects.all().delete()
        PayRun.objects.all().delete()
        Employee.objects.all().delete()
        Invoice.objects.all().delete()  # invoices ride on learners/sessions (SET_NULL)
        CorporateAccount.objects.filter(lead_email__endswith="@demo.tcms").delete()
        InvoiceSequence.objects.all().delete()
        Learner.objects.all().delete()  # cascades enrolments-independent records/certs
        CourseSession.objects.all().delete()  # cascades enrolments + session_instructors
        Venue.objects.all().delete()
        Instructor.objects.all().delete()
        demousers.delete()
        SeedMarker.objects.filter(tier=TIER).delete()
        self.stdout.write(self.style.WARNING("SEED_DEMO: existing demo world removed."))

    # -- demo users (RBAC exercisable) ---------------------------------------

    def _users(self):
        for rc in DEMO_ROLES:
            role = Role.objects.get(pk=rc)
            user, created = User.objects.get_or_create(
                username=f"demo_{role.code}",
                defaults={
                    "email": f"demo-{role.code.lower()}@demo.tcms",
                    "first_name": role.name,
                },
            )
            if created:
                user.set_password(self.demo_password)
                user.save()
            user.roles.add(role)
        self.stdout.write(f"demo users: {len(DEMO_ROLES)}")

    # -- scheduling -----------------------------------------------------------

    def _venues(self):
        venues = []
        for name, address, capacity in VENUES:
            v, _ = Venue.objects.get_or_create(
                name=name, defaults={"address": address, "capacity": capacity, "active": True}
            )
            venues.append(v)
        return venues

    def _instructors(self):
        users = {u.username: u for u in User.objects.filter(username__startswith="demo_")}
        instructors = []
        for i, full_name in enumerate(INSTRUCTOR_NAMES):
            ins, _ = Instructor.objects.get_or_create(
                full_name=full_name,
                defaults={"active": True, "user": users.get("demo_instructor") if i == 0 else None},
            )
            instructors.append(ins)
        return instructors

    def _sessions(self, venues, admin):
        sessions = []
        for ci, course in enumerate(Course.objects.order_by("course_code")):
            for k in range(2):
                idx = ci * 2 + k
                start = self.today + timedelta(days=(idx - 12) * 7)
                end = start + timedelta(days=max((course.duration_days or 1) - 1, 0))
                session, _ = CourseSession.objects.get_or_create(
                    course=course,
                    start_date=start,
                    defaults={
                        "venue": venues[idx % len(venues)],
                        "capacity": 20,
                        "seats_taken": 0,
                        "status": SessionStatus.OPEN if start >= self.today
                        else SessionStatus.CLOSED,
                        "end_date": end,
                        "created_by": admin,
                    },
                )
                sessions.append(session)
        return sessions

    # -- learners -------------------------------------------------------------

    def _learners(self):
        nationalities = list(Nationality.objects.all())
        states = list(State.objects.all())
        positions = list(Position.objects.all())
        companies = list(Company.objects.all())
        titles = list(Title.objects.all())
        contact_types = list(ContactType.objects.all())
        individual = Company.objects.filter(agencode="INDIVIDUAL").first()

        learners = []
        for i in range(len(TARGETS)):
            sex = Sex.MALE if i % 2 == 0 else Sex.FEMALE
            surname = LAST_NAMES[i % len(LAST_NAMES)]
            first = FIRST_NAMES[i % len(FIRST_NAMES)]
            badge = f"TASL{1000 + i:05d}"
            birth = date(1976 + (i * 3) % 25, (i % 12) + 1, (i % 27) + 1)
            corporate = i % 3 == 0
            learner, created = Learner.objects.get_or_create(
                badge_no=badge,
                defaults={
                    "surname": surname,
                    "first_name": first,
                    "sex": sex.value,
                    "birth_date": birth,
                    "nationality": nationalities[i % len(nationalities)],
                    "state": states[i % len(states)],
                    "position": positions[i % len(positions)],
                    "title": titles[i % len(titles)],
                    "company": companies[(i % (len(companies) - 1)) + 1]
                    if corporate
                    else individual,
                    "active": True,
                    "vantage_id": f"VAN{1000 + i:05d}",
                },
            )
            if created:
                LearnerContact.objects.create(
                    learner=learner,
                    contact_type=contact_types[i % len(contact_types)],
                    value=f"+23480{10000000 + i}",
                    is_primary=True,
                )
                LearnerContact.objects.create(
                    learner=learner,
                    contact_type=contact_types[2] if len(contact_types) > 2 else None,
                    value=f"{first.lower()}.{surname.lower()}@{CONTACT_DOMAINS[0]}",
                    is_primary=False,
                )
                LearnerDocument.objects.create(
                    learner=learner,
                    kind=DocumentKind.PASSPORT,
                    object_key=f"demo/learners/{badge}/passport.pdf",
                    mime="application/pdf",
                    size_bytes=120000,
                )
            learners.append(learner)
        return learners

    def _medicals(self, learners, admin):
        for i, learner in enumerate(learners):
            Medical.objects.get_or_create(
                learner=learner,
                record_no=f"MED{2000 + i}",
                defaults={
                    "issued_date": self.today - timedelta(days=150),
                    "expiry_date": self.today + timedelta(days=210),
                    "systolic": 118 + (i % 10),
                    "diastolic": 76 + (i % 8),
                    "fitness": Fitness.FIT,
                    "active": True,
                    "created_by": admin,
                },
            )

    # -- training records driven through the chain ---------------------------

    def _records(self, sessions, learners, instructors, admin):
        courses = list(Course.objects.order_by("course_code"))
        items = list(CourseItem.objects.order_by("id"))
        modules = list(CourseModule.objects.order_by("id"))
        new_status = WorkflowStatus.objects.get(pk=WorkflowStatusCode.NEW_RECORD)
        results = []
        for i, target in enumerate(TARGETS):
            course = courses[i % len(courses)]
            session = sessions[i % len(sessions)]
            learner = learners[i % len(learners)]
            start = compute_start_date(session.start_date, course.duration_days)
            record, created = TrainingRecord.objects.get_or_create(
                learner=learner,
                course=course,
                session=session,
                defaults={
                    "enrolment": self._enrol(learner, session, admin),
                    "start_date": start,
                    "end_date": compute_expiry(start, course.validity_years),
                    "status": new_status,
                    "instructor": instructors[i % len(instructors)].full_name,
                },
            )
            if created:
                for it in items[:2]:
                    TrainingItem.objects.create(
                        training_record=record,
                        course_item=it,
                        passed=True,
                        score=70 + (i % 25),
                    )
                TrainingInstructor.objects.create(
                    training_record=record,
                    instructor=instructors[i % len(instructors)],
                    module=modules[i % len(modules)] if modules else None,
                    training_date=start,
                )
                if start:
                    for offset, systolic, diastolic in (
                        (0, 118 + (i % 10), 76 + (i % 8)),
                        (1, 120 + (i % 8), 78 + (i % 6)),
                    ):
                        DailyMedicalCheck.objects.create(
                            training_record=record,
                            check_date=start + timedelta(days=offset),
                            systolic=systolic,
                            diastolic=diastolic,
                            notes="Routine course medical check.",
                            created_by=admin,
                        )
            self._drive(record, admin, int(target))
            results.append(record)
        return results

    def _enrol(self, learner, session, admin):
        attended = session.start_date < self.today
        enrolment, _ = Enrolment.objects.get_or_create(
            learner=learner,
            session=session,
            defaults={
                "requested_session": session,
                "original_session": session,
                "status": EnrolmentStatus.ATTENDED if attended else EnrolmentStatus.BOOKED,
                "state": BookingState.ATTENDED if attended else BookingState.CONFIRMED,
                "booking_ref": f"ENR{session.pk:04d}{learner.pk:05d}",
                "seat_allocated_at": timezone.now(),
                "payment_verified_at": timezone.now(),
                "created_by": admin,
            },
        )
        return enrolment

    def _drive(self, record, admin, target: int):
        if target == WorkflowStatusCode.NEW_RECORD:
            return
        if target == WorkflowStatusCode.CANCELLED:
            workflow.advance(record, admin, action="approve")
            workflow.advance(record, admin, action="cancel", reason="Withdrawn by client")
            return
        if target == WorkflowStatusCode.REJECTED:
            workflow.advance(record, admin)
            workflow.advance(record, admin)
            workflow.advance(record, admin, action="reject", reason="Documentation incomplete")
            return
        guard = 0
        while record.status_id < target and guard < 20:
            workflow.advance(record, admin)
            guard += 1

    # -- certificates + ID cards ---------------------------------------------

    def _certificates(self, records, admin):
        issued = 0
        for record in records:
            if record.status_id not in (
                WorkflowStatusCode.CERTIFICATE_DONE,
                WorkflowStatusCode.ID_CARD_DONE,
                WorkflowStatusCode.COMPLETED,
            ):
                continue
            if record.certificates.exists():
                continue
            certificate = cert_service.issue_certificate(
                record, actor=admin, on_date=self.today
            )
            cert_service.apply_signature_and_seal(certificate, actor=admin)
            issued += 1
            if record.course.id_card:
                IDCard.objects.get_or_create(
                    learner=record.learner,
                    training_record=record,
                    defaults={"card_no": f"IDC{record.learner.badge_no}", "printed_by": admin},
                )
        self.stdout.write(f"certificates issued: {issued}")

    # -- billing (M10) --------------------------------------------------------

    def _billing(self, learners, records, admin):
        corporate = [ln for ln in learners if ln.company and ln.company.agencode != "INDIVIDUAL"]
        accounts = {}
        for learner in corporate:
            company = learner.company
            if company.pk in accounts:
                continue
            account, _ = CorporateAccount.objects.get_or_create(
                name=company.name,
                defaults={
                    "company": company,
                    "lead_email": f"accounts@{company.pk}.demo.tcms",
                    "terms_days": 30,
                    "credit_limit": Decimal("500000.00"),
                    "active": True,
                    "created_by": admin,
                },
            )
            accounts[company.pk] = account

        skip = {int(WorkflowStatusCode.CANCELLED), int(WorkflowStatusCode.REJECTED)}
        invoices = payments = 0
        for record in records:
            if record.status_id < int(WorkflowStatusCode.ACCOUNTS_DONE):
                continue
            if record.status_id in skip:
                continue
            if record.enrolment_id and Invoice.objects.filter(
                enrolment_id=record.enrolment_id
            ).exists():
                continue

            learner = record.learner
            account = accounts.get(learner.company_id) if learner.company_id else None
            if account is not None:
                learner.corporate_account = account
                learner.corporate_account_id = account.pk
                learner.save(update_fields=["corporate_account"])

            amount = Decimal("45000.00") + Decimal(record.course_id % 5) * Decimal("5000.00")
            issue_date = record.start_date or self.today
            invoice = billing_service.create_invoice(
                lines=[
                    {
                        "description": f"{record.course.course_code} — {record.course.name}",
                        "quantity": 1,
                        "unit_price": amount,
                    }
                ],
                corporate_account=account,
                enrolment=record.enrolment,
                learner=learner,
                issue_date=issue_date,
                notes="Demo invoice (SEED_DEMO)",
                actor=admin,
            )
            billing_service.issue_invoice(invoice, actor=admin)
            invoices += 1

            if invoices % 2 == 0:
                billing_service.record_payment(
                    invoice=invoice,
                    amount=amount,
                    paid_at=timezone.make_aware(
                        datetime.combine(issue_date + timedelta(days=7), time(12, 0))
                    ),
                    method="transfer",
                    payment_ref=f"DEMO-PAY-{invoice.pk}",
                    received_by=admin,
                )
                payments += 1

        self.stdout.write(f"invoices issued: {invoices}, payments: {payments}")
        return invoices, payments

    # -- portal logins (UAT / load testing) ----------------------------------

    def _portal(self, learners):
        """Verified portal logins for UAT/load: one learner and one corporate lead."""
        learner = learners[0]
        learner_email = "demo_learner@tcms.local"
        learner_user, _ = User.objects.get_or_create(
            username=learner_email, defaults={"email": learner_email}
        )
        learner_user.email = learner_email
        learner_user.first_name = learner.first_name
        learner_user.last_name = learner.surname
        learner_user.email_verified = True
        learner_user.is_active = True
        learner_user.set_password(self.demo_password)
        learner_user.save()
        PortalAccount.objects.update_or_create(
            user=learner_user,
            defaults={
                "learner": learner,
                "account_type": PortalAccountType.INDIVIDUAL,
                "birth_date": learner.birth_date,
                "sex": learner.sex,
                "age_verified": True,
            },
        )

        count = 1
        corporate = CorporateAccount.objects.order_by("pk").first()
        if corporate is not None:
            lead_email = "demo_corporate@tcms.local"
            lead, _ = User.objects.get_or_create(
                username=lead_email, defaults={"email": lead_email}
            )
            lead.email = lead_email
            lead.first_name = "Demo"
            lead.last_name = "Corporate Lead"
            lead.email_verified = True
            lead.is_active = True
            lead.set_password(self.demo_password)
            lead.save()
            PortalAccount.objects.update_or_create(
                user=lead,
                defaults={
                    "account_type": PortalAccountType.CORPORATE_LEAD,
                    "corporate_account": corporate,
                },
            )
            count += 1
        self.stdout.write(f"portal accounts: {count} (password {self.demo_password})")
        return count

    # -- payroll (M11) --------------------------------------------------------

    def _payroll(self, admin):
        users = {u.username: u for u in User.objects.filter(username__startswith="demo_")}
        elements = {element.code: element for element in PayElement.objects.all()}
        if not elements:
            self.stdout.write(self.style.WARNING("payroll: pay elements missing — skipped"))
            return 0, 0

        staff = [
            ("TASL001", "Ada Okafor", "0123456789", "GTBank", "058", Decimal("450000.00")),
            ("TASL002", "Bola Adeyemi", "0234567891", "Access Bank", "044", Decimal("380000.00")),
            ("TASL003", "Chinedu Eze", "0345678912", "Zenith Bank", "057", Decimal("520000.00")),
            ("TASL004", "Damilola Bello", "0456789123", "UBA", "033", Decimal("300000.00")),
            ("TASL005", "Emeka Nwosu", "0567891234", "Fidelity Bank", "070", Decimal("400000.00")),
        ]
        employees = []
        for staff_no, full_name, account, bank, bank_code, basic in staff:
            employee, created = Employee.objects.get_or_create(
                staff_no=staff_no,
                defaults={
                    "full_name": full_name,
                    "basic_salary": basic,
                    "hourly_rate": Decimal("5000.00"),
                    "bank_name": bank,
                    "bank_code": bank_code,
                    "account_name": full_name,
                    "bank_account": account,
                    "active": True,
                    "created_by": admin,
                },
            )
            employees.append(employee)
            if created:
                EmployeePayElement.objects.create(
                    employee=employee, element=elements["BASIC"], amount=basic
                )
                EmployeePayElement.objects.create(
                    employee=employee,
                    element=elements["HOUSING"],
                    amount=(basic * Decimal("0.20")).quantize(Decimal("0.01")),
                )
                EmployeePayElement.objects.create(
                    employee=employee,
                    element=elements["TRANSPORT"],
                    amount=Decimal("50000.00"),
                )
                if employee.staff_no == "TASL002":
                    EmployeePayElement.objects.create(
                        employee=employee,
                        element=elements["LOAN"],
                        amount=Decimal("25000.00"),
                    )

        prepared_by = users.get("demo_accounts") or admin
        approver = users.get("demo_md") or admin
        first_of_month = self.today.replace(day=1)
        prev_end = first_of_month - timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        period = f"{prev_start:%Y-%m}"

        timesheet = payroll_service.create_timesheet(
            employee=employees[0],
            period_start=prev_start,
            period_end=prev_end,
            actor=prepared_by,
        )
        for offset in range(10):
            TimeEntry.objects.create(
                timesheet=timesheet,
                work_date=prev_start + timedelta(days=offset),
                hours=Decimal("8.00"),
                rate=Decimal("5000.00"),
                project="DEMO",
            )
        payroll_service.submit_timesheet(timesheet, actor=prepared_by)
        payroll_service.approve_timesheet(timesheet, actor=approver)
        payroll_service.accrue_provision(
            timesheet=timesheet,
            daily_rate=Decimal("16000.00"),
            as_of=prev_end,
            kind="leave",
            actor=prepared_by,
        )

        pay_run = payroll_service.create_pay_run(
            period=period, run_date=prev_end, actor=prepared_by
        )
        payroll_service.compute_pay_run(pay_run, actor=prepared_by)
        payroll_service.approve_pay_run(pay_run, actor=approver)
        payroll_service.post_pay_run(pay_run, actor=approver)
        payroll_service.generate_bank_file(pay_run, actor=prepared_by)

        self.stdout.write(
            f"payroll: {len(employees)} employees, pay run {period} posted "
            f"({pay_run.payslips.count()} payslips, net {pay_run.total_net})"
        )
        return len(employees), pay_run.payslips.count()
