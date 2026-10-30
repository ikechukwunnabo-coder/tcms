"""Development settings: zero-setup local run (SQLite by default)."""
from .base import *  # noqa: F401,F403

DEBUG = env_bool("DEBUG", True)  # noqa: F405
ALLOWED_HOSTS = ["*"]

# Console email unless Mailpit is running
EMAIL_BACKEND = env(  # noqa: F405
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)

INTERNAL_IPS = ["127.0.0.1"]
