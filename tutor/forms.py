from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class LearnerCreationForm(UserCreationForm):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(max_length=254, required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if not username:
            raise ValidationError("Enter a username.")
        return username

    def clean_email(self):
        return self.cleaned_data["email"].strip().casefold()

    def validate_unique(self):
        exclude = self._get_validation_exclusions()
        exclude.add("username")
        try:
            self.instance.validate_unique(exclude=exclude)
        except ValidationError as error:
            self._update_errors(error)


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Email address (or existing username)",
        max_length=254,
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )


class EmailAddressForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().casefold()


class OTPCodeForm(forms.Form):
    code = forms.CharField(
        label="Six-digit code",
        max_length=64,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "one-time-code",
                "class": "otp-code-input",
                "inputmode": "numeric",
                "pattern": "[0-9]{6}",
                "maxlength": "6",
                "aria-label": "Six-digit verification code",
            }
        ),
    )


class PasswordResetOTPForm(OTPCodeForm):
    new_password1 = forms.CharField(
        label="New password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("new_password1")
        password2 = cleaned_data.get("new_password2")
        if password1 and password2 and password1 != password2:
            self.add_error("new_password2", "The passwords do not match.")
        if password1:
            try:
                validate_password(password1, self.user)
            except ValidationError as error:
                self.add_error("new_password1", error)
        return cleaned_data


class EmailChangeRequestForm(forms.Form):
    new_email = forms.EmailField(
        label="New email address",
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    current_password = forms.CharField(
        label="Current password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def clean_new_email(self):
        return self.cleaned_data["new_email"].strip().casefold()
