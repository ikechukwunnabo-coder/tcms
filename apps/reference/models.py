from django.db import models

from apps.common.models import TimeStampedModel


class Company(TimeStampedModel):
    """Company / agency — mirrors legacy ``tblAgencies`` (``agencode`` preserved)."""

    agencode = models.CharField(max_length=32, unique=True, null=True, blank=True)
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, default="")
    active = models.BooleanField(default=True)
    is_individual = models.BooleanField(default=False)

    class Meta:
        db_table = "company"
        verbose_name_plural = "companies"

    def __str__(self) -> str:
        return self.name


class Nationality(models.Model):
    natcode = models.CharField(max_length=16, unique=True)
    country = models.CharField(max_length=100)
    nationality = models.CharField(max_length=100)

    class Meta:
        db_table = "nationality"
        verbose_name_plural = "nationalities"

    def __str__(self) -> str:
        return self.nationality


class State(models.Model):
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "state"

    def __str__(self) -> str:
        return self.name


class Position(models.Model):
    posicode = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=150)

    class Meta:
        db_table = "position"

    def __str__(self) -> str:
        return self.name


class Title(models.Model):
    id = models.SmallAutoField(primary_key=True)
    name = models.CharField(max_length=64)

    class Meta:
        db_table = "title"

    def __str__(self) -> str:
        return self.name


class ContactType(models.Model):
    id = models.SmallAutoField(primary_key=True)
    name = models.CharField(max_length=64)

    class Meta:
        db_table = "contact_type"

    def __str__(self) -> str:
        return self.name
