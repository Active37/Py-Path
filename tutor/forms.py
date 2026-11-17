from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
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
        email = self.cleaned_data["email"].strip().casefold()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email

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
