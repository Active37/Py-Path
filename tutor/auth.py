from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrLegacyUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = username or kwargs.get("email")
        if not identifier or password is None:
            return None

        user_model = get_user_model()
        if "@" in identifier:
            try:
                user = user_model._default_manager.get(email__iexact=identifier)
            except user_model.DoesNotExist:
                user_model().set_password(password)
                return None
        else:
            matches = user_model._default_manager.filter(
                username__iexact=identifier
            )
            if matches.count() != 1:
                user_model().set_password(password)
                return None
            user = matches.first()

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
