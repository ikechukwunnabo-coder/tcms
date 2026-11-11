from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import (
    action,
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import Role, User
from apps.accounts.serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    RoleSerializer,
    UserRoleSerializer,
    UserSerializer,
)
from apps.audit.services import write_audit
from apps.common.enums import RoleCode
from apps.common.net import client_ip
from apps.common.permissions import RolePermission
from apps.common.relations import parse_relation_pairs
from apps.common.views import RoleScopedModelViewSet

ADMIN_ONLY = (RoleCode.SYSTEM_ADMIN,)


class LoginRateThrottle(AnonRateThrottle):
    """Brute-force guard for the shared API sign-in endpoint."""

    scope = "login"


class RoleViewSet(RoleScopedModelViewSet):
    queryset = Role.objects.all().order_by("id")
    serializer_class = RoleSerializer
    required_roles = ADMIN_ONLY
    write_roles = ADMIN_ONLY


class UserViewSet(RoleScopedModelViewSet):
    queryset = User.objects.all().order_by("id").prefetch_related("roles")
    serializer_class = UserSerializer
    required_roles = ADMIN_ONLY
    write_roles = ADMIN_ONLY
    filterset_fields = ["is_active", "is_staff"]
    search_fields = ["username", "first_name", "last_name", "email"]
    ordering_fields = ["username", "date_joined"]

    def destroy(self, request, *args, **kwargs):
        target = self.get_object()
        if target.pk == request.user.pk:
            return Response(
                {"detail": "You cannot delete your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if target.roles.filter(pk=RoleCode.SYSTEM_ADMIN).exists():
            other_admin = (
                User.objects.filter(
                    roles__pk=RoleCode.SYSTEM_ADMIN, is_active=True
                )
                .exclude(pk=target.pk)
                .exists()
            )
            if not other_admin:
                return Response(
                    {"detail": "The last active System Admin cannot be deleted."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        write_audit(
            action="accounts.user_deleted",
            entity="user",
            entity_id=target.pk,
            actor=request.user,
            after={"username": target.username, "email": target.email},
            ip=client_ip(request),
        )
        return super().destroy(request, *args, **kwargs)

    @extend_schema(request=None, responses={200: None})
    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        target = self.get_object()
        if not target.email:
            return Response(
                {"detail": "This account has no email address."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        uid = urlsafe_base64_encode(force_bytes(target.pk))
        token = default_token_generator.make_token(target)
        link = request.build_absolute_uri(
            reverse(
                "portal_web:password-reset-confirm",
                kwargs={"uidb64": uid, "token": token},
            )
        )
        try:
            send_mail(
                "Reset your TASL Training Centre password",
                (
                    "An administrator sent you a password reset link.\n\n"
                    f"Choose a new password here: {link}\n\n"
                    "If you did not expect this, contact your administrator."
                ),
                settings.DEFAULT_FROM_EMAIL,
                [target.email],
                fail_silently=False,
            )
        except Exception:
            return Response(
                {"detail": "The password reset email could not be sent."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        write_audit(
            action="accounts.password_reset_link_sent",
            entity="user",
            entity_id=target.pk,
            actor=request.user,
            after={"email": target.email},
            ip=client_ip(request),
        )
        return Response({"message": f"Password reset link sent to {target.email}."})


@extend_schema(request=LoginSerializer, responses={200: UserSerializer})
@api_view(["POST"])
@throttle_classes([LoginRateThrottle])
@permission_classes([AllowAny])
def login(request):
    """R-API-AUTH-01: username/password -> token + roles (token auth; JWT is â—‹)."""
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(
        username=serializer.validated_data["identifier"],
        password=serializer.validated_data["password"],
    )
    if user is None:
        write_audit(
            action="auth.api_login_failed",
            entity="user",
            after={"identifier": serializer.validated_data["identifier"]},
            ip=client_ip(request),
        )
        return Response(
            {"error": "invalid_credentials", "message": "Invalid username or password."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    if not user.is_active:
        write_audit(
            action="auth.api_login_inactive",
            entity="user",
            entity_id=user.pk,
            ip=client_ip(request),
        )
        return Response(
            {"error": "inactive", "message": "Account is inactive."},
            status=status.HTTP_403_FORBIDDEN,
        )
    if not getattr(user, "email_verified", True):
        return Response(
            {"error": "email_not_verified", "message": "Please verify your email address."},
            status=status.HTTP_403_FORBIDDEN,
        )
    token, _ = Token.objects.get_or_create(user=user)
    return Response(
        {
            "user": UserSerializer(user).data,
            "roles": [r.code for r in user.roles.all()],
            "token": token.key,
        }
    )


@extend_schema(request=ChangePasswordSerializer, responses={204: None})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Self-service password change for the authenticated staff account."""
    serializer = ChangePasswordSerializer(
        data=request.data, context={"user": request.user}
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    if isinstance(request.auth, Token):
        Token.objects.filter(user=request.user).exclude(pk=request.auth.pk).delete()
    write_audit(
        action="auth.password_changed",
        entity="user",
        entity_id=request.user.pk,
        actor=request.user,
        ip=client_ip(request),
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(request=None, responses={204: None})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    """R-API-AUTH-02: revoke the current token (or session)."""
    if isinstance(request.auth, Token):
        request.auth.delete()
    else:
        auth_logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


def _delete_user_role(relation_id):
    relation = get_object_or_404(
        User.roles.through.objects.select_related("role"), pk=relation_id
    )
    user_id, role_id = relation.user_id, relation.role_id
    if role_id == RoleCode.SYSTEM_ADMIN:
        return Response(
            {"detail": "The System Admin role cannot be removed."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    relation.delete()
    write_audit(
        action="accounts.user_role_removed",
        entity="user_role",
        entity_id=relation_id,
        after={"user": user_id, "role": role_id},
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


class UserRoleCollectionView(APIView):
    """Axis-compatible ``/user-role`` assignment endpoint."""

    permission_classes = [RolePermission]
    required_roles = ADMIN_ONLY
    write_roles = ADMIN_ONLY

    @extend_schema(request=RoleSerializer, responses={201: None})
    def post(self, request):
        pairs = parse_relation_pairs(request.data, parent_key="user")
        through = User.roles.through
        created = []
        with transaction.atomic():
            for user_id, role_id in pairs:
                user = get_object_or_404(User, pk=user_id)
                role = get_object_or_404(Role, pk=role_id)
                relation, is_new = through.objects.get_or_create(
                    user=user, role=role
                )
                if is_new:
                    write_audit(
                        action="accounts.user_role_added",
                        entity="user_role",
                        entity_id=relation.pk,
                        after={"user": user_id, "role": role_id},
                    )
                created.append(relation)
        return Response(
            UserRoleSerializer(created, many=True).data, status=status.HTTP_201_CREATED
        )


class UserRoleDetailView(APIView):
    permission_classes = [RolePermission]
    required_roles = ADMIN_ONLY
    write_roles = ADMIN_ONLY

    @extend_schema(responses={200: None})
    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        rows = (
            User.roles.through.objects.filter(user=user)
            .select_related("role")
            .order_by("role_id")
        )
        return Response(UserRoleSerializer(rows, many=True).data)

    @extend_schema(responses={204: None})
    def delete(self, request, user_id):
        return _delete_user_role(user_id)


class UserRoleAvailableView(APIView):
    permission_classes = [RolePermission]
    required_roles = ADMIN_ONLY
    write_roles = ADMIN_ONLY

    @extend_schema(responses={200: RoleSerializer(many=True)})
    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        assigned = user.roles.values_list("id", flat=True)
        rows = Role.objects.exclude(id__in=assigned).order_by("id")
        return Response(RoleSerializer(rows, many=True).data)


class UserRoleDeleteView(APIView):
    permission_classes = [RolePermission]
    required_roles = ADMIN_ONLY
    write_roles = ADMIN_ONLY

    @extend_schema(responses={204: None})
    def delete(self, request, relation_id):
        return _delete_user_role(relation_id)
