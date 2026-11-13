from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalogue.models import CertificateType, Course, CourseItem, CourseModule
from apps.integration.models import SeedMarker
from apps.reference.models import Company, ContactType, Nationality, Position, State, Title

TIER = "SEED_DATA"

NATIONALITIES = [
    ("NG", "Nigeria", "Nigerian"),
    ("GH", "Ghana", "Ghanaian"),
    ("ZA", "South Africa", "South African"),
    ("GB", "United Kingdom", "British"),
    ("US", "United States", "American"),
    ("IN", "India", "Indian"),
    ("PH", "Philippines", "Filipino"),
    ("FR", "France", "French"),
]

STATES = [
    ("AB", "Abia"), ("AD", "Adamawa"), ("AK", "Akwa Ibom"), ("AN", "Anambra"),
    ("BA", "Bauchi"), ("BY", "Bayelsa"), ("BE", "Benue"), ("BO", "Borno"),
    ("CR", "Cross River"), ("DE", "Delta"), ("EB", "Ebonyi"), ("ED", "Edo"),
    ("EK", "Ekiti"), ("EN", "Enugu"), ("FC", "FCT Abuja"), ("GO", "Gombe"),
    ("IM", "Imo"), ("JI", "Jigawa"), ("KD", "Kaduna"), ("KN", "Kano"),
    ("KT", "Katsina"), ("KB", "Kebbi"), ("KO", "Kogi"), ("KW", "Kwara"),
    ("LA", "Lagos"), ("NA", "Nasarawa"), ("NI", "Niger"), ("OG", "Ogun"),
    ("ON", "Ondo"), ("OS", "Osun"), ("OY", "Oyo"), ("PL", "Plateau"),
    ("RI", "Rivers"), ("SO", "Sokoto"), ("TA", "Taraba"), ("YO", "Yobe"),
    ("ZA", "Zamfara"), ("FR", "- Foreigner -"),
]

POSITIONS = [
    ("POS001", "Rigger"), ("POS002", "Electrician"), ("POS003", "Welder"),
    ("POS004", "Crane Operator"), ("POS005", "Deckhand"), ("POS006", "Engineer"),
    ("POS007", "Supervisor"), ("POS008", "Safety Officer"), ("POS009", "Diver"),
    ("POS010", "Technician"), ("POS011", "HR Manager"),
    ("POS012", "HR Officer / Generalist"),
]

TITLES = ["Mr", "Mrs", "Ms", "Miss", "Dr", "Engr", "Capt", "Chief"]

CONTACT_TYPES = [(1, "Phone"), (2, "Mobile"), (3, "E-mail"), (4, "Fax")]

COMPANIES = [
    ("INDIVIDUAL", "INDIVIDUAL", "", True),
    ("TASL", "Tolmann Allied Services Ltd", "info@tasl.example", False),
    ("SHELL", "Shell Nigeria Exploration", "training@shell.example", False),
    ("CHEVRON", "Chevron Nigeria Ltd", "hse@chevron.example", False),
    ("TOTAL", "TotalEnergies EP Nigeria", "ops@total.example", False),
    ("NIMASA", "Nigerian Maritime Admin", "cert@nimasa.example", False),
]

CERT_TYPES = [(1, "Standard"), (2, "NIMASA"), (4, "OPITO")]

MODULES = [
    "Sea Survival", "Fire Fighting", "First Aid", "Helicopter Safety",
    "Hazard Awareness", "Manual Handling",
]

ITEMS = [
    "Theory Assessment", "Practical Assessment", "Medical Screening",
    "Escape Training", "Fire Drill", "Rescue Exercise",
]

# course_code, name, cert_type_id, duration_days, validity_years, id_card, foet, opito, refresher
COURSES = [
    (
        "BOSIET",
        "Basic Offshore Safety Induction & Emergency Training",
        4,
        4,
        4,
        True,
        True,
        "5700",
        None,
    ),
    ("BOSIET-R", "BOSIET Refresher", 4, 3, 4, True, True, "5701", "BOSIET"),
    ("HUET", "Helicopter Underwater Escape Training", 4, 2, 4, True, True, "5095", None),
    ("FOET", "Further Offshore Emergency Training", 4, 2, 4, True, True, "5858", "BOSIET"),
    ("H2S", "H2S & Breathing Apparatus", 1, 1, 2, False, False, "", None),
    ("FIRST-AID", "Basic First Aid", 1, 1, 3, False, False, "", None),
    ("WELD-6G", "6G Welding Certification", 2, 5, 2, True, False, "", None),
    ("SEA-SURV", "Sea Survival", 1, 1, 3, False, False, "", None),
]


class Command(BaseCommand):
    help = "SEED_DATA: reference data (M2) + course catalogue (M4). Idempotent."

    @transaction.atomic
    def handle(self, *args, **options):
        self._reference()
        self._catalogue()
        SeedMarker.objects.get_or_create(tier=TIER, code="reference")
        SeedMarker.objects.get_or_create(tier=TIER, code="catalogue")
        self.stdout.write(self.style.SUCCESS("SEED_DATA complete"))

    def _reference(self):
        for code, country, nationality in NATIONALITIES:
            Nationality.objects.update_or_create(
                natcode=code, defaults={"country": country, "nationality": nationality}
            )
        for code, name in STATES:
            State.objects.update_or_create(code=code, defaults={"name": name})
        for code, name in POSITIONS:
            Position.objects.update_or_create(posicode=code, defaults={"name": name})
        for i, name in enumerate(TITLES, start=1):
            Title.objects.update_or_create(id=i, defaults={"name": name})
        for cid, name in CONTACT_TYPES:
            ContactType.objects.update_or_create(id=cid, defaults={"name": name})
        for agencode, name, email, is_individual in COMPANIES:
            Company.objects.update_or_create(
                agencode=agencode,
                defaults={
                    "name": name,
                    "email": email,
                    "is_individual": is_individual,
                    "active": True,
                },
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"reference: {Nationality.objects.count()} nationalities, "
                f"{State.objects.count()} states, {Position.objects.count()} positions, "
                f"{Company.objects.count()} companies"
            )
        )

    def _catalogue(self):
        for cid, name in CERT_TYPES:
            CertificateType.objects.update_or_create(id=cid, defaults={"name": name})
        for name in MODULES:
            CourseModule.objects.update_or_create(name=name, defaults={"active": True})
        for name in ITEMS:
            CourseItem.objects.update_or_create(name=name, defaults={"active": True})

        # pass 1: courses without refresher link
        for code, name, cert, dur, val, idc, foet, opito, _ref in COURSES:
            Course.objects.update_or_create(
                course_code=code,
                defaults={
                    "name": name,
                    "cert_type_id": cert,
                    "expiry_type": 2 if code == "FOET" else 1,
                    "duration_days": dur,
                    "validity_years": val,
                    "id_card": idc,
                    "foet_required": foet,
                    "opito_reg_code": opito,
                    "active": True,
                },
            )
        # pass 2: refresher links
        for code, _n, _c, _d, _v, _i, _f, _o, ref in COURSES:
            if ref:
                Course.objects.filter(course_code=code).update(
                    refresher_course=Course.objects.get(course_code=ref)
                )
        self.stdout.write(
            self.style.SUCCESS(
                f"catalogue: {Course.objects.count()} courses, "
                f"{CourseModule.objects.count()} modules, {CourseItem.objects.count()} items"
            )
        )
