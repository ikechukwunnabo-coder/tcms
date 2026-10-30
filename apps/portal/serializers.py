from rest_framework import serializers

from apps.billing.models import CorporateAccount
from apps.common.enums import PortalAccountType, Sex
from apps.learners.models import Learner
from apps.portal.models import JoiningInstruction
from apps.reference.models import Company, Nationality, Position, State, Title


class RegisterSerializer(serializers.Serializer):
    """``POST /auth/register`` (design ``04`` §5.1)."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    birth_date = serializers.DateField()
    sex = serializers.ChoiceField(choices=Sex.choices, required=False, allow_blank=True)
    username = serializers.CharField(max_length=150, required=False, allow_blank=True)


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField()


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PortalAccountSerializer(serializers.Serializer):
    """Read representation of the verified portal account."""

    user_id = serializers.IntegerField()
    email = serializers.EmailField(source="user.email")
    account_type = serializers.ChoiceField(choices=PortalAccountType.choices)
    learner_id = serializers.IntegerField(allow_null=True)
    email_verified = serializers.BooleanField(source="user.email_verified")


# ── Corporate accounts & nominees (design ``04`` §5.2, spec §9.6) ────────────


class PortalCorporateAccountReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = CorporateAccount
        fields = [
            "id",
            "name",
            "company",
            "lead_email",
            "credit_limit",
            "terms_days",
            "balance",
            "active",
            "created_at",
        ]
        read_only_fields = fields


class CorporateAccountCreateSerializer(serializers.Serializer):
    """``POST /corporate/accounts`` (lead creates its account, spec §9.6)."""

    name = serializers.CharField(max_length=200)
    company = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), required=False, allow_null=True
    )
    terms_days = serializers.IntegerField(required=False, min_value=0)


class NomineeSerializer(serializers.ModelSerializer):
    """Read representation of a corporate nominee (a ``Learner``, no login)."""

    full_name = serializers.CharField(read_only=True)
    corporate_account = serializers.IntegerField(source="corporate_account_id", read_only=True)

    class Meta:
        model = Learner
        fields = [
            "id",
            "badge_no",
            "surname",
            "first_name",
            "middle_name",
            "full_name",
            "sex",
            "birth_date",
            "nationality",
            "state",
            "position",
            "company",
            "title",
            "learner_type",
            "corporate_account",
            "active",
            "created_at",
        ]
        read_only_fields = fields


class NomineeWriteSerializer(serializers.Serializer):
    """Create/edit a nominee's bio-data (spec §9.6)."""

    surname = serializers.CharField(max_length=100)
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    sex = serializers.ChoiceField(choices=Sex.choices, required=False, allow_blank=True)
    birth_date = serializers.DateField()
    nationality = serializers.PrimaryKeyRelatedField(
        queryset=Nationality.objects.all(), required=False, allow_null=True
    )
    state = serializers.PrimaryKeyRelatedField(
        queryset=State.objects.all(), required=False, allow_null=True
    )
    position = serializers.PrimaryKeyRelatedField(
        queryset=Position.objects.all(), required=False, allow_null=True
    )
    company = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), required=False, allow_null=True
    )
    title = serializers.PrimaryKeyRelatedField(
        queryset=Title.objects.all(), required=False, allow_null=True
    )


class NomineeUpdateSerializer(NomineeWriteSerializer):
    """PATCH a nominee — every field optional."""

    surname = serializers.CharField(max_length=100, required=False)
    birth_date = serializers.DateField(required=False)


class JoiningInstructionSerializer(serializers.ModelSerializer):
    """Read representation of a CJI (spec §9.7)."""

    session_id = serializers.IntegerField(source="session.id", allow_null=True)

    class Meta:
        model = JoiningInstruction
        fields = [
            "id",
            "enrolment",
            "session_id",
            "version",
            "is_current",
            "delivery_status",
            "sent_to",
            "sent_at",
            "issued_at",
            "payload",
        ]
        read_only_fields = fields
