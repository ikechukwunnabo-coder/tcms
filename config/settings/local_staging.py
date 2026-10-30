from .prod import *  # noqa: F401,F403

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'tcms-local-staging',
    }
}
