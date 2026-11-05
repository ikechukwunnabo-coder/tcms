"""Base settings shared by all environments.

Values come from environment variables (see ``.env.example``). Twelve-factor:
nothing environment-specific is hard-coded here.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    return str(os.environ.get(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


# ── Core ────────────────────────────────────────────────────────────────────
SECRET_KEY = env("SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = env_bool("DEBUG", False)
# API schema/Swagger are always available with DEBUG; enable explicitly elsewhere.
EXPOSE_API_DOCS = env_bool("EXPOSE_API_DOCS", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# ── Applications ────────────────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework.authtoken",
    "django_filters",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.reference",
    "apps.billing",
    "apps.payroll",
    "apps.learners",
    "apps.catalogue",
    "apps.scheduling",
    "apps.delivery",
    "apps.certification",
    "apps.medicals",
    "apps.workflow",
    "apps.reporting",
    "apps.documents",
    "apps.notifications",
    "apps.audit",
    "apps.integration",
    "apps.portal",
    "apps.portal_web",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.common.middleware.AdminLoginRateLimitMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.audit.middleware.CurrentUserMiddleware",
    "apps.portal_web.middleware.PortalContentSecurityPolicyMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.portal_web.context_processors.portal_links",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ── Database ────────────────────────────────────────────────────────────────
if env_bool("USE_SQLITE", False):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "tcms"),
            "USER": env("DB_USER", "tcms"),
            "PASSWORD": env("DB_PASSWORD", "tcms"),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }

# ── Auth ────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── i18n / tz ───────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

# ── Static / media ──────────────────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
WHITENOISE_MAX_AGE = int(env("WHITENOISE_MAX_AGE", "31536000"))

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# ── Object storage (S3 / MinIO) ─────────────────────────────────────────────
USE_S3_STORAGE = env_bool("USE_S3_STORAGE", False)
if USE_S3_STORAGE:
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": env("AWS_ACCESS_KEY_ID"),
            "secret_key": env("AWS_SECRET_ACCESS_KEY"),
            "bucket_name": env("AWS_STORAGE_BUCKET_NAME", "tcms-documents"),
            "endpoint_url": env("AWS_S3_ENDPOINT_URL") or None,
            "region_name": env("AWS_S3_REGION_NAME", "us-east-1"),
            "default_acl": None,
            "file_overwrite": False,
            "querystring_auth": True,
            "querystring_expire": int(env("AWS_QUERYSTRING_EXPIRE", "3600")),
            "addressing_style": env("AWS_S3_ADDRESSING_STYLE", "path"),
        },
    }

if env("AWS_S3_CUSTOM_DOMAIN"):
    STORAGES["default"].setdefault("OPTIONS", {})["custom_domain"] = env("AWS_S3_CUSTOM_DOMAIN")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── DRF ─────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.ExpiringTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # 0 = always identify clients by REMOTE_ADDR (ignore spoofable headers).
    # Set to the number of trusted proxies when deployed behind a reverse proxy.
    "NUM_PROXIES": int(env("DRF_NUM_PROXIES", "0")),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "login": env("API_LOGIN_RATE", "10/min"),
        "register": env("API_REGISTER_RATE", "20/hour"),
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "TCMS API",
    "DESCRIPTION": "TASL Training Centre Management System API",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "PayElementKindEnum": "apps.common.enums.PayElementKind",
        "TimeEntryKindEnum": "apps.common.enums.TimeEntryKind",
    },
}

# ── Celery ──────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_TIME_LIMIT = 600
CELERY_TASK_TRACK_STARTED = True
CELERY_BEAT_SCHEDULE = {
    "dispatch-outbox": {
        "task": "apps.integration.tasks.dispatch_outbox",
        "schedule": int(env("OUTBOX_DISPATCH_SECONDS", "60")),
    },
    "certificate-reminders": {
        "task": "apps.certification.tasks.send_due_reminders",
        "schedule": int(env("REMINDER_JOB_SECONDS", "3600")),
    },
}

# ── Outbox / webhooks ───────────────────────────────────────────────────────
OUTBOX_WEBHOOK_URLS = env_list("OUTBOX_WEBHOOK_URLS")
WEBHOOK_SIGNING_SECRET = env("WEBHOOK_SIGNING_SECRET", "")
WEBHOOK_TIMEOUT = int(env("WEBHOOK_TIMEOUT", "10"))
OUTBOX_MAX_ATTEMPTS = int(env("OUTBOX_MAX_ATTEMPTS", "8"))

# ── Email ───────────────────────────────────────────────────────────────────
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "1025"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = int(env("EMAIL_TIMEOUT", "10"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@tcms.local")

# ── Domain: workflow config (see design 03-business-logic.md) ────────────────
CERTIFICATE_REMINDER_WINDOWS = [90, 60, 30, 0]  # days before expiry
RENEWAL_WINDOW_DAYS = 90
MIN_LEARNER_AGE = 18
CAPACITY_RESERVE_PCT = 10  # default carry-forward headroom (SAD §8.1)

# ── Domain: certificate presentation ────────────────────────────────────────
# Branding is deployment-specific. Image keys point at files in the configured
# default storage (local media or S3/MinIO); leave blank to draw text fallbacks.
DOCUMENT_UPLOAD_MAX_BYTES = int(env("DOCUMENT_UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)))
CERTIFICATE_UPLOAD_MAX_BYTES = int(
    env("CERTIFICATE_UPLOAD_MAX_BYTES", str(DOCUMENT_UPLOAD_MAX_BYTES))
)
CERTIFICATE_ORG_NAME = env("CERTIFICATE_ORG_NAME", "TASL Training Centre")
CERTIFICATE_ORG_ADDRESS = env("CERTIFICATE_ORG_ADDRESS", "")
CERTIFICATE_TITLE = env("CERTIFICATE_TITLE", "CERTIFICATE OF TRAINING")
CERTIFICATE_LOGO_KEY = env("CERTIFICATE_LOGO_KEY", "")
CERTIFICATE_SIGNATORY_NAME = env("CERTIFICATE_SIGNATORY_NAME", "Managing Director")
CERTIFICATE_SIGNATORY_TITLE = env("CERTIFICATE_SIGNATORY_TITLE", "Managing Director")
# Optional public verification URL printed in the certificate footer.
CERTIFICATE_VERIFY_URL = env("CERTIFICATE_VERIFY_URL", "")

# ── Domain: billing (see design 02-database.md M10) ──────────────────────────
# VAT percentage applied to taxable invoice lines. Defaults to 0 so the system
# is safe until Finance confirms the applicable rate; set BILLING_TAX_PCT (e.g.
# "7.5") in the environment for production.
BILLING_TAX_PCT = env("BILLING_TAX_PCT", "0")

# ── Domain: scheduling capacity rules ───────────────────────────────────────
# Layer 1: total seats committed across concurrent sessions may not exceed the
# venue capacity. Layer 2: a venue hosts at most one live session at a time.
ENFORCE_FACILITY_CAPACITY = env_bool("ENFORCE_FACILITY_CAPACITY", True)
ENFORCE_VENUE_EXCLUSIVITY = env_bool("ENFORCE_VENUE_EXCLUSIVITY", True)

# ── Domain: finance & payroll (M11; provisional until parallel run) ──────────
# Pension minimums are the Nigerian Contributory Pension Scheme floor (7.5/7.5).
PAYROLL_PENSION_EMPLOYEE_PCT = env("PAYROLL_PENSION_EMPLOYEE_PCT", "7.5")
PAYROLL_PENSION_EMPLOYER_PCT = env("PAYROLL_PENSION_EMPLOYER_PCT", "7.5")
PAYROLL_PAYE_ANNUAL_RELIEF = env("PAYROLL_PAYE_ANNUAL_RELIEF", "0")
PAYROLL_TIMESHEET_PENSIONABLE = env("PAYROLL_TIMESHEET_PENSIONABLE", "false").lower() == "true"
PAYROLL_GL_SALARY_EXPENSE = env("PAYROLL_GL_SALARY_EXPENSE", "500000")
PAYROLL_GL_EMPLOYER_PENSION = env("PAYROLL_GL_EMPLOYER_PENSION", "501000")
PAYROLL_GL_NET_PAY = env("PAYROLL_GL_NET_PAY", "210000")
PAYROLL_GL_PAYE = env("PAYROLL_GL_PAYE", "220000")
PAYROLL_GL_PENSION = env("PAYROLL_GL_PENSION", "230000")
PAYROLL_GL_DEDUCTIONS = env("PAYROLL_GL_DEDUCTIONS", "240000")

# ── API tokens (DRF token auth; 0 disables expiry) ──────────────────────────
API_TOKEN_TTL_HOURS = int(env("API_TOKEN_TTL_HOURS", "24"))

# Trust X-Forwarded-For for portal rate limiting/audit only behind a proxy that
# overwrites the header (never enable on a directly exposed host).
TRUST_X_FORWARDED_FOR = env_bool("TRUST_X_FORWARDED_FOR", False)

# Shared rate-limit window for Django-admin sign-in failures.
ADMIN_LOGIN_RATE_LIMIT = int(env("ADMIN_LOGIN_RATE_LIMIT", "10"))
ADMIN_LOGIN_RATE_WINDOW = int(env("ADMIN_LOGIN_RATE_WINDOW", "300"))

# ── Domain: portal (see design 04-api-contract.md §5, spec BR-15) ────────────
PORTAL_BASE_URL = env("PORTAL_BASE_URL", "http://localhost:3000")
PORTAL_WEB_BASE_URL = env("PORTAL_WEB_BASE_URL", "http://127.0.0.1:8000")
PORTAL_WEB_PATH = env("PORTAL_WEB_PATH", "/portal/")
# Where the verification email points. The Django-rendered portal accepts both
# /portal/verify-email/?token=... (the emailed link) and /portal/verify-email/<token>/.
PORTAL_VERIFY_URL = env(
    "PORTAL_VERIFY_URL", f"{PORTAL_WEB_BASE_URL.rstrip('/')}/portal/verify-email/"
)
PORTAL_VERIFY_TTL_HOURS = int(env("PORTAL_VERIFY_TTL_HOURS", "24"))
PORTAL_RESEND_LIMIT = int(env("PORTAL_RESEND_LIMIT", "5"))
PORTAL_RESEND_WINDOW = int(env("PORTAL_RESEND_WINDOW", "3600"))  # seconds
PORTAL_LOGIN_RATE_LIMIT = int(env("PORTAL_LOGIN_RATE_LIMIT", "10"))
PORTAL_LOGIN_RATE_WINDOW = int(env("PORTAL_LOGIN_RATE_WINDOW", "300"))  # seconds
PORTAL_REGISTER_RATE_LIMIT = int(env("PORTAL_REGISTER_RATE_LIMIT", "20"))
PORTAL_REGISTER_RATE_WINDOW = int(env("PORTAL_REGISTER_RATE_WINDOW", "3600"))  # seconds

# ── Domain: CJI (Course Joining Instructions — spec §9.7, SAD §8.2) ──────────
CJI_COURSE_TIME = env("CJI_COURSE_TIME", "09:00")
CJI_COORDINATOR_NAME = env("CJI_COORDINATOR_NAME", "Training Coordinator")
CJI_COORDINATOR_PHONE = env("CJI_COORDINATOR_PHONE", "")
CJI_COORDINATOR_EMAIL = env("CJI_COORDINATOR_EMAIL", "")
CJI_LOGO_URL = env("CJI_LOGO_URL", "")
CJI_REQUIRED_ITEMS = [
    "Valid photo ID / passport",
    "Medical fitness certificate",
    "Two passport photographs",
    "Safety boots / PPE",
]
PORTAL_PRIVACY_LINK = env("PORTAL_PRIVACY_LINK", "")
PORTAL_CONTACT_LINK = env("PORTAL_CONTACT_LINK", "")
PORTAL_UNSUBSCRIBE_LINK = env("PORTAL_UNSUBSCRIBE_LINK", "")

# NOTE (ADR-0003): AXIS is a read-only reference (parity oracle + schema mirror),
# never a runtime dependency. No AXIS_BASE_URL/credentials exist here by design —
# see design 01-architecture.md §6.1 and README v1.1 strategy.
