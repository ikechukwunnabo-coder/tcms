"""Portal routes (design ``04-api-contract.md`` §5.1)."""
from django.urls import path

from apps.portal import views

urlpatterns = [
    path("auth/register", views.register, name="portal-register"),
    path("auth/verify-email", views.verify_email, name="portal-verify-email"),
    path("auth/resend-verification", views.resend_verification, name="portal-resend-verification"),
    path("corporate/accounts", views.corporate_account_create, name="corporate-account-create"),
    path("corporate/nominees", views.nominees, name="corporate-nominees"),
    path("corporate/nominees/<int:pk>", views.nominee_detail, name="corporate-nominee-detail"),
    path(
        "corporate/certificates/bundle",
        views.corporate_certificate_bundle,
        name="corporate-certificate-bundle",
    ),
    path(
        "corporate/certificates/batches",
        views.corporate_certificate_batches,
        name="corporate-certificate-batches",
    ),
    path("bookings/<int:pk>/cji", views.booking_cji, name="booking-cji"),
    path("bookings/<int:pk>/cji/resend", views.booking_cji_resend, name="booking-cji-resend"),
]
