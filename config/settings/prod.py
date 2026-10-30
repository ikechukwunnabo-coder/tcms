"""Production settings: hardened defaults.

All secrets/hosts come from the environment. Set DEBUG=false and provide a
real SECRET_KEY, ALLOWED_HOSTS, DB_*, CELERY_BROKER_URL and SMTP details.
"""
from .base import *  # noqa: F401,F403

DEBUG = False

if not SECRET_KEY or SECRET_KEY in {  # noqa: F405
    "insecure-dev-key-change-me",
    "change-me-in-production",
    "build-only-key",
}:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("SECRET_KEY must be set to a real value in production.")

# Security hardening (enable once TLS termination is in place)
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)  # noqa: F405
# Only trust X-Forwarded-Proto when the app sits behind a trusted TLS proxy.
if env_bool("USE_X_FORWARDED_PROTO", False):  # noqa: F405
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Browser sessions: secure cookies, sliding idle expiry, close-on-exit.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = int(env("SESSION_COOKIE_AGE", "28800"))  # noqa: F405
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = env_bool("SESSION_EXPIRE_AT_BROWSER_CLOSE", True)  # noqa: F405

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Serve collected static assets directly from the app (hashed, compressed).
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# Shared cache so DRF throttles and portal rate limits work across workers.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_CACHE_URL", "redis://localhost:6379/2"),  # noqa: F405
    }
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"format": '{"level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}'}
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

