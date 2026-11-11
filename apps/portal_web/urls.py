"""Public portal routes — mounted at ``/portal/`` by ``config.urls``."""
from django.urls import path

from apps.portal_web import views

app_name = "portal_web"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("verify/", views.verify_certificate, name="verify-certificate"),
    path(
        "verify/<str:identifier>/",
        views.verify_certificate,
        name="verify-certificate-detail",
    ),
    path("register/", views.register, name="register"),
    path("registered/", views.registered, name="registered"),
    path("verify-email/", views.verify_email, name="verify-email"),
    path("verify-email/<str:token>/", views.verify_email, name="verify-email-token"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("password-reset/", views.password_reset_request, name="password-reset"),
    path("password-reset/done/", views.password_reset_done, name="password-reset-done"),
    path(
        "password-reset/<uidb64>/<token>/",
        views.password_reset_confirm,
        name="password-reset-confirm",
    ),
    path("resend-verification/", views.resend_verification_view, name="resend-verification"),
    path(
        "resend-verification/email/",
        views.resend_verification_page,
        name="resend-verification-page",
    ),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile, name="profile"),
    path("corporate/", views.corporate, name="corporate"),
    path(
        "corporate/nominees/<int:pk>/edit/",
        views.nominee_edit,
        name="corporate-nominee-edit",
    ),
    path(
        "corporate/nominees/<int:pk>/remove/",
        views.nominee_remove,
        name="corporate-nominee-remove",
    ),
    path(
        "certificates/<int:pk>/download/",
        views.certificate_download,
        name="certificate-download",
    ),
    path("bookings/<int:pk>/cji/", views.cji_view, name="booking-cji"),
    path("bookings/<int:pk>/cji/resend/", views.cji_resend_view, name="booking-cji-resend"),
]
