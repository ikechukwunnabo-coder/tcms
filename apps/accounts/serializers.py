from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import Role, User
from apps.common.enums import RoleCode


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "code", "name"]


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    roles = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Role.objects.all(), required=False
    )
    full_name = serializers.CharField(read_only=True)
    role_codes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "full_name", "email",
            "is_active", "is_staff", "password", "roles", "role_codes",
        ]
        read_only_fields = ["id", "full_name", "role_codes"]

    def get_role_codes(self, obj) -> list[str]:
        return [r.code for r in obj.roles.all()]

    def validate(self, attrs):
        if self.instance is None:
            return attrs

        roles = attrs.get("roles")
        if roles is not None:
            has_system_admin = self.instance.roles.filter(
                pk=RoleCode.SYSTEM_ADMIN
            ).exists()
            keeps_system_admin = any(role.pk == RoleCode.SYSTEM_ADMIN for role in roles)
            if has_system_admin and not keeps_system_admin:
                raise serializers.ValidationError(
                    {"roles": "The System Admin role cannot be removed."}
                )

        deactivating = attrs.get("is_active") is False and self.instance.is_active
        if deactivating and self.instance.roles.filter(pk=RoleCode.SYSTEM_ADMIN).exists():
            other_admin = (
                User.objects.filter(
                    roles__pk=RoleCode.SYSTEM_ADMIN, is_active=True
                )
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if not other_admin:
                raise serializers.ValidationError(
                    {"is_active": "The last active System Admin cannot be deactivated."}
                )
        return attrs

    def validate_email(self, value: str) -> str:
        value = (value or "").strip().lower()
        if not value:
            return value
        qs = User.objects.filter(email__iexact=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("an account with this email already exists")
        return value

    def validate_password(self, value: str) -> str:
        if not value:
            return value
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        roles = validated_data.pop("roles", [])
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        user.roles.set(roles)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        roles = validated_data.pop("roles", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        instance.save()
        if roles is not None:
            instance.roles.set(roles)
        return instance


class UserRoleSerializer(serializers.Serializer):
    """Axis-compatible relation row returned by ``/user-role/{user_id}``."""

    id = serializers.IntegerField()
    user = serializers.IntegerField(source="user_id")
    role = serializers.IntegerField(source="role_id")
    name = serializers.CharField(source="role.name")
    code = serializers.CharField(source="role.code")


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value: str) -> str:
        user = self.context["user"]
        if not user.check_password(value):
            raise serializers.ValidationError("Current password not matching.")
        return value

    def validate_new_password(self, value: str) -> str:
        user = self.context["user"]
        if user.check_password(value):
            raise serializers.ValidationError(
                "Passwords are all the same. Nothing to change."
            )
        try:
            validate_password(value, user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return attrs

    def save(self, **kwargs):
        user = self.context["user"]
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class LoginSerializer(serializers.Serializer):
    """Staff log in by username; portal users by email (their username is the
    email, so either field is accepted). At least one is required."""

    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = (attrs.get("username") or attrs.get("email") or "").strip()
        if not identifier:
            raise serializers.ValidationError({"username": "username or email is required"})
        attrs["identifier"] = identifier
        return attrs
