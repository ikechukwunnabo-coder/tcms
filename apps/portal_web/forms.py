"""Portal web forms — registration, verification resend and login."""
from __future__ import annotations

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.common.enums import Sex
from apps.reference.models import Company, Nationality, Position, State, Title

REFERENCE_FIELDS = ("nationality", "state", "position", "company", "title")


class CorporateAccountForm(forms.Form):
    """Create the signed-in lead's corporate account (spec §9.6)."""

    name = forms.CharField(max_length=200, label="Account name")
    company = forms.ModelChoiceField(
        queryset=Company.objects.all(), required=False, empty_label="Not linked"
    )
    terms_days = forms.IntegerField(min_value=0, initial=30, label="Payment terms (days)")


class ProfileForm(forms.Form):
    """Portal self-service profile — account names plus learner bio-data."""

    surname = forms.CharField(max_length=150, label="Surname")
    first_name = forms.CharField(max_length=150, required=False)
    middle_name = forms.CharField(max_length=150, required=False)
    sex = forms.ChoiceField(
        choices=[("", "Select..."), (Sex.MALE.value, "Male"), (Sex.FEMALE.value, "Female")],
        required=False,
    )
    birth_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    nationality = forms.ModelChoiceField(
        queryset=Nationality.objects.all(), required=False, empty_label="Not set"
    )
    state = forms.ModelChoiceField(
        queryset=State.objects.all(), required=False, empty_label="Not set"
    )
    position = forms.ModelChoiceField(
        queryset=Position.objects.all(), required=False, empty_label="Not set"
    )
    company = forms.ModelChoiceField(
        queryset=Company.objects.all(), required=False, empty_label="Not set"
    )
    title = forms.ModelChoiceField(
        queryset=Title.objects.all(), required=False, empty_label="Not set"
    )


class NomineeForm(forms.Form):
    """Corporate nominee bio-data (spec §9.6)."""

    surname = forms.CharField(max_length=100, label="Surname")
    first_name = forms.CharField(max_length=100, required=False)
    middle_name = forms.CharField(max_length=100, required=False)
    sex = forms.ChoiceField(
        choices=[("", "Select..."), (Sex.MALE.value, "Male"), (Sex.FEMALE.value, "Female")],
        required=False,
    )
    birth_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    nationality = forms.ModelChoiceField(
        queryset=Nationality.objects.all(), required=False, empty_label="Not set"
    )
    state = forms.ModelChoiceField(
        queryset=State.objects.all(), required=False, empty_label="Not set"
    )
    position = forms.ModelChoiceField(
        queryset=Position.objects.all(), required=False, empty_label="Not set"
    )
    company = forms.ModelChoiceField(
        queryset=Company.objects.all(), required=False, empty_label="Not set"
    )
    title = forms.ModelChoiceField(
        queryset=Title.objects.all(), required=False, empty_label="Not set"
    )

    def cleaned_bio(self) -> dict:
        return {name: self.cleaned_data.get(name) for name in (
            "surname", "first_name", "middle_name", "sex", "birth_date",
            *REFERENCE_FIELDS,
        )}


class RegisterForm(forms.Form):
    """Individual learner registration (spec BR-1/BR-15)."""

    first_name = forms.CharField(
        max_length=150,
        label="First name",
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        max_length=150,
        label="Surname",
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )
    email = forms.EmailField(
        label="Email address", widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    birth_date = forms.DateField(
        label="Date of birth",
        widget=forms.DateInput(attrs={"type": "date", "autocomplete": "bday"}),
        help_text="You must be 18 or older to register.",
    )
    sex = forms.ChoiceField(
        label="Sex",
        choices=[("", "Select..."), (Sex.MALE.value, "Male"), (Sex.FEMALE.value, "Female")],
        required=False,
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        min_length=8,
        help_text="At least 8 characters.",
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class LoginForm(forms.Form):
    """Portal sign-in — email + password (staff and portal share the account)."""

    email = forms.EmailField(
        label="Email address", widget=forms.EmailInput(attrs={"autocomplete": "username"})
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class ResendVerificationForm(forms.Form):
    email = forms.EmailField(
        label="Email address", widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label="Email address", widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class SetNewPasswordForm(forms.Form):
    password = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        min_length=8,
    )
    confirm_password = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        min_length=8,
    )

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirm = cleaned.get("confirm_password")
        if password and confirm and password != confirm:
            self.add_error("confirm_password", "The two passwords do not match.")
        if password:
            try:
                validate_password(password)
            except ValidationError as exc:
                self.add_error("password", exc)
        return cleaned
