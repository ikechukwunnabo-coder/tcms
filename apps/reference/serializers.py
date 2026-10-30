from rest_framework import serializers

from apps.reference.models import Company, ContactType, Nationality, Position, State, Title


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "agencode", "name", "email", "active", "is_individual"]
        read_only_fields = ["id"]


class NationalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Nationality
        fields = ["id", "natcode", "country", "nationality"]


class StateSerializer(serializers.ModelSerializer):
    class Meta:
        model = State
        fields = ["id", "code", "name"]


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ["id", "posicode", "name"]


class TitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Title
        fields = ["id", "name"]


class ContactTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactType
        fields = ["id", "name"]
