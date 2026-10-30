"""Root URL configuration.

API is versioned under /api/v1/. OpenAPI schema + Swagger UI are exposed for
contract-first development.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("portal/", include("apps.portal_web.urls")),
    path("api/v1/", include("apps.common.urls")),
    path("api/v1/", include("apps.portal.urls")),
]

if settings.DEBUG or settings.EXPOSE_API_DOCS:
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "api/docs/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
