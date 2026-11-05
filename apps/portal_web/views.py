"""Public learner portal — pages for registration, verification, sign-in and
the learner dashboard (bookings, certificates, CJI).

Session-based; every rule lives in ``apps.portal`` / ``apps.certification``
services so the API and the web portal behave identically.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.text import get_valid_filename
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import write_audit
from apps.certification import services as cert_service
from apps.certification.exceptions import CertificateDocumentMissing
from apps.certification.models import Certificate
from apps.common.net import client_ip
from apps.learners.services import AgeError
from apps.portal import cji as cji_svc
from apps.portal import services as portal_svc
from apps.portal.models import JoiningInstruction, PortalAccount
from apps.portal.services import EmailTaken, InvalidToken, TokenExpired, WeakPassword
from apps.portal_web.forms import (
    LoginForm,
    PasswordResetRequestForm,
    RegisterForm,
    SetNewPasswordForm,
)
from apps.scheduling.models import Enrolment

User = get_user_model()

AUTH_BACKEND = "django.contrib.auth.backends.ModelBackend"
LOGIN_URL = reverse_lazy("portal_web:login")


# ── Public pages ─────────────────────────────────────────────────────────────


def _mark_invalid(form):
    """Flag fields that failed validation for screen readers (WCAG 3.3.1)."""
    for field in form:
        if field.errors:
            field.field.widget.attrs["aria-invalid"] = "true"
            field.field.widget.attrs["aria-describedby"] = f"{field.id_for_label}_error"


def landing(request):
    """Public landing page (marketing + entry points)."""
    if request.user.is_authenticated:
        return redirect("portal_web:dashboard")
    return render(request, "portal/landing.html")


def register(request):
    """Individual learner registration (BR-1/BR-15)."""
    if request.user.is_authenticated:
        return redirect("portal_web:dashboard")

    form = RegisterForm(request.POST or None)
    if request.method == "POST":
        key = f"portal-register:{client_ip(request)}"
        try:
            portal_svc.check_rate_limit(
                key,
                limit=int(getattr(settings, "PORTAL_REGISTER_RATE_LIMIT", 20)),
                window=int(getattr(settings, "PORTAL_REGISTER_RATE_WINDOW", 3600)),
            )
        except portal_svc.RateLimited:
            messages.error(
                request, "Too many registration attempts. Please try again later."
            )
            return render(request, "portal/register.html", {"form": form}, status=429)
    if request.method == "POST" and form.is_valid():
        try:
            portal_svc.register_individual(
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                birth_date=form.cleaned_data["birth_date"],
                sex=form.cleaned_data.get("sex", ""),
            )
        except AgeError:
            form.add_error("birth_date", "You must be 18 or older to register.")
        except EmailTaken:
            form.add_error("email", "An account already exists for this email address.")
        except WeakPassword as exc:
            form.add_error("password", str(exc))
        else:
            return redirect("portal_web:registered")
    _mark_invalid(form)
    return render(request, "portal/register.html", {"form": form})


def registered(request):
    """Post-registration page — the verification link is on its way."""
    return render(request, "portal/registered.html")


@require_http_methods(["GET", "POST"])
def verify_email(request, token=None):
    """Confirm then consume a single-use verification token (BR-15).

    GET only previews the token so email link scanners cannot activate the
    account; the learner must submit the confirmation form (POST) to consume
    it. Accepts the token either in the path or as ``?token=...``.
    """
    token = token or (request.POST.get("token") or request.GET.get("token") or "").strip()
    if not token:
        return render(
            request,
            "portal/verify.html",
            {"ok": False, "invalid": True},
            status=400,
        )

    status = portal_svc.verification_token_status(token)
    if status == "invalid":
        return render(request, "portal/verify.html", {"ok": False, "invalid": True}, status=400)
    if status == "expired":
        return render(request, "portal/verify.html", {"ok": False, "expired": True}, status=400)

    if request.method == "POST":
        try:
            portal_svc.verify_email(token)
        except InvalidToken:
            return render(
                request, "portal/verify.html", {"ok": False, "invalid": True}, status=400
            )
        except TokenExpired:
            return render(
                request, "portal/verify.html", {"ok": False, "expired": True}, status=400
            )
        return render(request, "portal/verify.html", {"ok": True})

    return render(request, "portal/verify_confirm.html", {"token": token})


def login_view(request):
    """Sign in with email + password (staff and portal share the account)."""
    if request.user.is_authenticated:
        return redirect("portal_web:dashboard")

    form = LoginForm(request.POST or None)
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        key = f"portal-login:{client_ip(request)}:{email}"
        try:
            portal_svc.check_rate_limit(
                key,
                limit=int(getattr(settings, "PORTAL_LOGIN_RATE_LIMIT", 10)),
                window=int(getattr(settings, "PORTAL_LOGIN_RATE_WINDOW", 300)),
            )
        except portal_svc.RateLimited:
            messages.error(
                request, "Too many sign-in attempts. Please try again in a few minutes."
            )
            _mark_invalid(form)
            return render(request, "portal/login.html", {"form": form}, status=429)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]
        user = User.objects.filter(email__iexact=email).first()
        password_ok = user.check_password(password) if user is not None else False
        if user is None:
            make_password(password)
        if not password_ok:
            write_audit(
                action="auth.login_failed",
                entity="user",
                after={"email": email},
                ip=client_ip(request),
            )
            messages.error(request, "Invalid email address or password.")
        elif not user.is_active:
            write_audit(
                action="auth.login_inactive",
                entity="user",
                entity_id=user.pk,
                ip=client_ip(request),
            )
            messages.error(request, "This account has been deactivated.")
        elif not user.email_verified:
            messages.error(
                request,
                "Please verify your email address before signing in. "
                "Check your inbox for the verification link.",
            )
        else:
            auth_login(request, user, backend=AUTH_BACKEND)
            return redirect("portal_web:dashboard")
    _mark_invalid(form)
    return render(request, "portal/login.html", {"form": form})


@require_POST
def logout_view(request):
    """Sign out."""
    auth_logout(request)
    return redirect("portal_web:landing")


@require_POST
def resend_verification_view(request):
    """Re-send the verification email (rate-limited)."""
    email = (request.POST.get("email") or "").strip().lower()
    if email:
        try:
            portal_svc.resend_verification(email)
        except portal_svc.RateLimited:
            messages.error(request, "Too many requests. Please try again later.")
    messages.info(request, "If that address is registered and unverified, a new link was sent.")
    return redirect("portal_web:login")


def resend_verification_page(request):
    """Standalone page for requesting a new verification link."""
    return render(request, "portal/resend.html")


def _password_reset_link(request, user) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return request.build_absolute_uri(
        reverse(
            "portal_web:password-reset-confirm",
            kwargs={"uidb64": uid, "token": token},
        )
    )


def password_reset_request(request):
    """Request a password-reset link (no account enumeration)."""
    if request.user.is_authenticated:
        return redirect("portal_web:dashboard")

    form = PasswordResetRequestForm(request.POST or None)
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        key = f"portal-password-reset:{client_ip(request)}:{email}"
        try:
            portal_svc.check_rate_limit(
                key,
                limit=int(getattr(settings, "PORTAL_RESET_RATE_LIMIT", 5)),
                window=int(getattr(settings, "PORTAL_RESET_RATE_WINDOW", 3600)),
            )
        except portal_svc.RateLimited:
            messages.error(request, "Too many reset requests. Please try again later.")
            _mark_invalid(form)
            return render(
                request, "portal/password_reset.html", {"form": form}, status=429
            )
        if form.is_valid():
            user = User.objects.filter(
                email__iexact=form.cleaned_data["email"], is_active=True
            ).first()
            if user is not None and user.email:
                link = _password_reset_link(request, user)
                send_mail(
                    "Reset your TASL Training Centre password",
                    (
                        "A password reset was requested for your account.\n\n"
                        f"Choose a new password here: {link}\n\n"
                        "If you did not request this, you can ignore this email."
                    ),
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=True,
                )
            return redirect("portal_web:password-reset-done")
        _mark_invalid(form)
    return render(request, "portal/password_reset.html", {"form": form})


def password_reset_done(request):
    return render(request, "portal/password_reset_done.html")


@require_http_methods(["GET", "POST"])
def password_reset_confirm(request, uidb64, token):
    """Set a new password from a single-use, time-limited token."""
    user = None
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.filter(pk=user_id, is_active=True).first()
    except (TypeError, ValueError, OverflowError):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        return render(request, "portal/password_reset_invalid.html", status=400)

    form = SetNewPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user.set_password(form.cleaned_data["password"])
        user.save(update_fields=["password"])
        write_audit(
            action="auth.password_reset",
            entity="user",
            entity_id=user.pk,
            ip=client_ip(request),
        )
        messages.success(request, "Your password has been updated. Please sign in.")
        return redirect("portal_web:login")

    _mark_invalid(form)
    return render(
        request, "portal/password_reset_confirm.html", {"form": form, "validlink": True}
    )


# ── Authenticated pages ──────────────────────────────────────────────────────


def _portal_learners(user):
    """The learners a signed-in user may see (own record, or corporate nominees)."""
    account = (
        PortalAccount.objects.filter(user=user)
        .select_related("learner", "corporate_account")
        .first()
    )
    if account is None:
        return account, []
    if account.corporate_account_id is not None:
        nominees = list(account.corporate_account.nominees.all())
        if account.learner_id:
            nominees.append(account.learner)
        return account, nominees
    if account.learner_id:
        return account, [account.learner]
    return account, []


@login_required(login_url=LOGIN_URL)
def dashboard(request):
    """Learner dashboard — bookings, certificates and joining instructions."""
    account, learners = _portal_learners(request.user)

    enrolments = []
    certificates = []
    if learners:
        enrolments = list(
            Enrolment.objects.filter(learner__in=learners)
            .select_related(
                "session",
                "session__course",
                "session__venue",
                "requested_session",
                "learner",
            )
            .order_by("-created_at")
        )
        certificates = list(
            Certificate.objects.filter(learner__in=learners)
            .select_related("training_record")
            .order_by("-issued_at", "-id")
        )

    cji_map = {}
    if enrolments:
        for ji in JoiningInstruction.objects.filter(
            enrolment__in=enrolments, is_current=True
        ):
            cji_map[ji.enrolment_id] = ji

    today = date.today()
    bookings = []
    for enrolment in enrolments:
        bookings.append(
            {
                "enrolment": enrolment,
                "session": enrolment.session or enrolment.requested_session,
                "course": (enrolment.session or enrolment.requested_session).course
                if (enrolment.session or enrolment.requested_session)
                else None,
                "venue": enrolment.session.venue if enrolment.session else None,
                "cji": cji_map.get(enrolment.pk),
            }
        )

    cert_rows = []
    for cert in certificates:
        days_left = (cert.expiry_date - today).days if cert.expiry_date else None
        cert_rows.append(
            {
                "cert": cert,
                "days_left": days_left,
                "state": _certificate_state(cert, today),
            }
        )

    is_lead = bool(account and account.corporate_account_id)
    return render(
        request,
        "portal/dashboard.html",
        {
            "account": account,
            "learners": learners,
            "bookings": bookings,
            "certificates": cert_rows,
            "is_lead": is_lead,
        },
    )


def _certificate_state(cert, today) -> str:
    """Valid / expiring-soon / expired / void — for the dashboard pill."""
    if cert.voided_at:
        return "void"
    if not cert.expiry_date:
        return "valid"
    days_left = (cert.expiry_date - today).days
    if days_left < 0:
        return "expired"
    if days_left <= 90:
        return "expiring"
    return "valid"


@login_required(login_url=LOGIN_URL)
def certificate_download(request, pk):
    """Download a learner/ nominee certificate PDF (authenticated portal access)."""
    certificate = get_object_or_404(Certificate, pk=pk)
    _, learners = _portal_learners(request.user)
    if not any(learner.pk == certificate.learner_id for learner in learners):
        return render(
            request,
            "portal/error.html",
            {"message": "You do not have access to this certificate."},
            status=403,
        )
    try:
        data = cert_service.certificate_document_bytes(certificate, actor=request.user)
    except CertificateDocumentMissing:
        return render(
            request,
            "portal/error.html",
            {"message": "This certificate PDF has not been uploaded yet."},
            status=404,
        )
    filename = get_valid_filename(f"{certificate.certificate_no}.pdf") or "certificate.pdf"
    return FileResponse(
        BytesIO(data),
        content_type="application/pdf",
        as_attachment=True,
        filename=filename,
    )


@login_required(login_url=LOGIN_URL)
def cji_view(request, pk):
    """The current Course Joining Instructions for a booking (BR-20)."""
    enrolment = get_object_or_404(Enrolment, pk=pk)
    try:
        cji_svc.assert_access(request.user, enrolment)
    except cji_svc.CJIAccessDenied:
        return render(
            request,
            "portal/error.html",
            {"message": "You do not have access to this booking."},
            status=403,
        )

    ji = cji_svc.current_for(enrolment)
    if ji is None:
        return render(
            request,
            "portal/error.html",
            {"message": "No joining instructions have been issued for this booking yet."},
            status=404,
        )
    return HttpResponse(ji.payload, content_type="text/html; charset=utf-8")


@login_required(login_url=LOGIN_URL)
@require_POST
def cji_resend_view(request, pk):
    """Re-send the current CJI to the verified address (BR-20)."""
    enrolment = get_object_or_404(Enrolment, pk=pk)
    try:
        cji_svc.assert_access(request.user, enrolment)
    except cji_svc.CJIAccessDenied:
        return render(
            request,
            "portal/error.html",
            {"message": "You do not have access to this booking."},
            status=403,
        )

    try:
        cji_svc.resend(enrolment)
    except cji_svc.CJIGateError:
        messages.error(request, "No verified delivery address is on file for this booking.")
    except cji_svc.CJIError:
        messages.error(request, "There is no joining instruction to resend yet.")
    else:
        messages.success(request, "Joining instructions have been re-sent to your email.")
    return redirect("portal_web:dashboard")
