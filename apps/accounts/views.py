from django.contrib.auth import authenticate
from django.contrib.auth import logout as auth_logout
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.accounts.models import Role, User
from apps.accounts.serializers import LoginSerializer, RoleSerializer, UserSerializer
from apps.audit.services import write_audit
from apps.common.enums import RoleCode
from apps.common.net import client_ip
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


@extend_schema(request=LoginSerializer, responses={200: UserSerializer})
@api_view(["POST"])
@throttle_classes([LoginRateThrottle])
@permission_classes([AllowAny])
def login(request):
    """R-API-AUTH-01: username/password -> token + roles (token auth; JWT is ○)."""
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
