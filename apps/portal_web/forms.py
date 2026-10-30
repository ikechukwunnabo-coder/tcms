"""Portal web forms — registration, verification resend and login."""
from __future__ import annotations

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.common.enums import Sex


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
