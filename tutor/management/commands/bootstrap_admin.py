import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Create the initial site administrator from environment variables."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        values = (username, email, password)

        if not any(values):
            self.stdout.write(
                self.style.WARNING(
                    "Initial admin bootstrap skipped; set all DJANGO_SUPERUSER_* "
                    "variables in the hosting environment to create the account."
                )
            )
            return
        if not all(values):
            raise CommandError(
                "Set DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, and "
                "DJANGO_SUPERUSER_PASSWORD together, or leave all three unset."
            )

        User = get_user_model()
        existing_user = User.objects.filter(username=username).first()
        if existing_user:
            if existing_user.is_superuser:
                self.stdout.write(
                    "Initial admin already exists; account and password left unchanged."
                )
                return
            raise CommandError(
                "The configured admin username already belongs to a non-superuser."
            )
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(
                "The configured admin email is already used by another account."
            )

        candidate = User(username=username, email=email)
        try:
            validate_password(password, user=candidate)
        except ValidationError as error:
            raise CommandError(
                "The configured admin password does not meet the password policy: "
                + "; ".join(error.messages)
            ) from error

        with transaction.atomic():
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
            )
        self.stdout.write(self.style.SUCCESS("Initial site administrator created."))
