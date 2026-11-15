from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from tutor import views
from tutor import otp_views
from tutor.forms import EmailAuthenticationForm


urlpatterns = [
    path("admin/", admin.site.urls),
    path("service-worker.js", views.service_worker, name="service_worker"),
    path("", views.home, name="home"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            authentication_form=EmailAuthenticationForm,
        ),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/signup/", views.signup, name="signup"),
    path(
        "accounts/verify-email/",
        otp_views.verify_registration,
        name="verify_registration",
    ),
    path(
        "accounts/password-reset/",
        otp_views.password_reset_request,
        name="password_reset_request",
    ),
    path(
        "accounts/password-reset/verify/",
        otp_views.password_reset_verify,
        name="password_reset_verify",
    ),
    path(
        "accounts/recovery/",
        otp_views.account_recovery_request,
        name="account_recovery_request",
    ),
    path(
        "accounts/recovery/verify/",
        otp_views.account_recovery_verify,
        name="account_recovery_verify",
    ),
    path(
        "accounts/email/change/",
        otp_views.email_change_request,
        name="email_change_request",
    ),
    path(
        "accounts/email/change/verify/",
        otp_views.verify_email_change,
        name="verify_email_change",
    ),
    path("learn/", include("tutor.urls")),
]
