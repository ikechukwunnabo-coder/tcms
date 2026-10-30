from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import Role, User


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "code", "name"]


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    roles = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Role.objects.all(), required=False
    )
    role_codes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "email",
            "is_active", "is_staff", "password", "roles", "role_codes",
        ]
        read_only_fields = ["id", "role_codes"]

    def get_role_codes(self, obj) -> list[str]:
        return [r.code for r in obj.roles.all()]

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
