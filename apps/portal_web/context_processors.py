"""Template context shared by the learner portal."""
from django.conf import settings


def portal_links(request):
    return {
        "api_docs_enabled": bool(
            getattr(settings, "EXPOSE_API_DOCS", False) or settings.DEBUG
        ),
    }
