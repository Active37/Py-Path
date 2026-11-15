import logging
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import (
    EmailAddressForm,
    EmailChangeRequestForm,
    LearnerCreationForm,
    OTPCodeForm,
    PasswordResetOTPForm,
)
from .models import EmailOTP
from .otp import (
    OTPDeliveryError,
    OTPRequestLimited,
    issue_otp,
    latest_otp,
    mask_email,
    verify_otp,
)


logger = logging.getLogger(__name__)
User = get_user_model()

_PENDING_REGISTRATION_EMAIL = "pending_registration_email"
_PENDING_REGISTRATION_USER_ID = "pending_registration_user_id"
_PENDING_REGISTRATION_STARTED = "pending_registration_started"
_PENDING_REGISTRATION_USERNAME = "pending_registration_username"
_PENDING_REGISTRATION_PASSWORD = "pending_registration_password"


def _request_otp_safely(user, purpose, email, request):
    try:
        issue_otp(user, purpose, target_email=email, request=request)
    except OTPRequestLimited as error:
        logger.info(
            "OTP request limited (user_id=%s purpose=%s retry_after=%s)",
            user.pk,
            purpose,
            error.retry_after,
        )
        return "limited"
    except OTPDeliveryError as error:
        logger.warning(
            "OTP request failed (user_id=%s purpose=%s error=%s)",
            user.pk,
            purpose,
            error,
        )
        return "failed"
    return "accepted"


def _email_otp_context(user, purpose, email, *, fallback_started_at=None):
    now = timezone.now()
    challenge = latest_otp(user, purpose, email) if user else None
    expires_at = challenge.expires_at if challenge else now + timedelta(minutes=5)
    if challenge:
        resend_at = challenge.created_at + timedelta(seconds=60)
    elif fallback_started_at:
        resend_at = datetime.fromtimestamp(
            fallback_started_at,
            tz=timezone.get_current_timezone(),
        ) + timedelta(seconds=60)
    else:
        resend_at = now
    return {
        "email": mask_email(email),
        "expires_at_ms": int(expires_at.timestamp() * 1000),
        "resend_at_ms": int(resend_at.timestamp() * 1000),
    }


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = LearnerCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        request.session.pop(_PENDING_REGISTRATION_USER_ID, None)
        request.session.pop(_PENDING_REGISTRATION_USERNAME, None)
        request.session.pop(_PENDING_REGISTRATION_PASSWORD, None)
        request.session[_PENDING_REGISTRATION_EMAIL] = email
        request.session[_PENDING_REGISTRATION_STARTED] = timezone.now().timestamp()

        user = User.objects.filter(email__iexact=email).first()
        if user and (user.is_active or user.is_staff or user.is_superuser):
            user = None
        if user is None and not User.objects.filter(email__iexact=email).exists():
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.is_active = False
                    user.save()
            except IntegrityError:
                if User.objects.filter(email__iexact=email).exists():
                    user = None
                else:
                    raise

        if user is not None:
            request.session[_PENDING_REGISTRATION_USER_ID] = user.pk
            request.session[_PENDING_REGISTRATION_USERNAME] = form.cleaned_data[
                "username"
            ]
            request.session[_PENDING_REGISTRATION_PASSWORD] = make_password(
                form.cleaned_data["password1"]
            )
            delivery_status = _request_otp_safely(
                user,
                EmailOTP.Purpose.REGISTRATION,
                email,
                request,
            )
            logger.info(
                "Registration verification request processed "
                "(user_id=%s otp_delivery=%s)",
                user.pk,
                delivery_status,
            )
        else:
            logger.info("Registration request processed (otp_delivery=not_eligible)")

        return redirect("verify_registration")

    return render(request, "registration/signup.html", {"form": form})


def _registration_user(request, email):
    user_id = request.session.get(_PENDING_REGISTRATION_USER_ID)
    if not user_id:
        return None
    return User.objects.filter(
        pk=user_id,
        email__iexact=email,
        is_active=False,
        is_staff=False,
        is_superuser=False,
    ).first()


@require_http_methods(["GET", "POST"])
def verify_registration(request):
    email = request.session.get(_PENDING_REGISTRATION_EMAIL)
    if not email:
        return redirect("signup")

    user = _registration_user(request, email)
    if request.method == "POST":
        if request.POST.get("action") == "resend":
            if user:
                _request_otp_safely(
                    user,
                    EmailOTP.Purpose.REGISTRATION,
                    email,
                    request,
                )
            messages.info(
                request,
                "If a code is available for this address, it will arrive by email. "
                "You can request another after the timer.",
            )
            return redirect("verify_registration")

        form = OTPCodeForm(request.POST)
        if form.is_valid() and user:
            pending_password = request.session.get(_PENDING_REGISTRATION_PASSWORD)
            pending_username = request.session.get(_PENDING_REGISTRATION_USERNAME)
            if not pending_password or not pending_username:
                form.add_error("code", "Restart sign up to verify this account.")
                status = "missing_session"
            else:
                with transaction.atomic():
                    locked_user = (
                        User.objects.select_for_update()
                        .filter(pk=user.pk, email__iexact=email, is_active=False)
                        .first()
                    )
                    status, _challenge = (
                        verify_otp(
                            locked_user,
                            EmailOTP.Purpose.REGISTRATION,
                            email,
                            form.cleaned_data["code"],
                        )
                        if locked_user
                        else ("invalid", None)
                    )
                    if status == "valid":
                        locked_user.is_active = True
                        locked_user.username = pending_username
                        locked_user.password = pending_password
                        locked_user.save(
                            update_fields=["is_active", "username", "password"]
                        )
                        user = locked_user
            if status == "valid":
                request.session.pop(_PENDING_REGISTRATION_EMAIL, None)
                request.session.pop(_PENDING_REGISTRATION_USER_ID, None)
                request.session.pop(_PENDING_REGISTRATION_STARTED, None)
                request.session.pop(_PENDING_REGISTRATION_USERNAME, None)
                request.session.pop(_PENDING_REGISTRATION_PASSWORD, None)
                messages.success(request, "Your email is verified. Welcome to PyPath!")
                login(
                    request,
                    user,
                    backend="tutor.auth.EmailOrLegacyUsernameBackend",
                )
                logger.info("Registration email verified (user_id=%s)", user.pk)
                return redirect("dashboard")
            elif status == "expired":
                form.add_error("code", "That code has expired. Request a new one.")
            elif status == "locked":
                form.add_error("code", "Too many incorrect attempts. Request a new code.")
            elif status != "missing_session":
                form.add_error("code", "That code is incorrect or no longer valid.")
        elif form.is_valid():
            form.add_error("code", "That code is incorrect or no longer valid.")
    else:
        form = OTPCodeForm()

    context = _email_otp_context(
        user,
        EmailOTP.Purpose.REGISTRATION,
        email,
        fallback_started_at=request.session.get(_PENDING_REGISTRATION_STARTED),
    )
    context.update(
        {
            "form": form,
            "title": "Verify your email",
            "intro": (
                "Enter the six-digit verification code if it arrived. "
                "If you do not receive one, request another after the timer."
            ),
            "verify_url": reverse("verify_registration"),
            "resend_url": reverse("verify_registration"),
            "show_resend": True,
            "show_password_fields": False,
        }
    )
    return render(request, "registration/otp_verify.html", context)


def _request_account_otp(request, purpose, verify_url_name, heading):
    form = EmailAddressForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        session_key = f"pending_{purpose}_email"
        request.session[session_key] = email
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            _request_otp_safely(user, purpose, email, request)
        messages.success(
            request,
            "If an active account matches that address, a code may arrive by email.",
        )
        return redirect(verify_url_name)
    return render(
        request,
        "registration/otp_request.html",
        {
            "form": form,
            "title": heading,
            "submit_label": "Send verification code",
            "login_url": reverse("login"),
        },
    )


def password_reset_request(request):
    return _request_account_otp(
        request,
        EmailOTP.Purpose.PASSWORD_RESET,
        "password_reset_verify",
        "Reset your password",
    )


def account_recovery_request(request):
    return _request_account_otp(
        request,
        EmailOTP.Purpose.ACCOUNT_RECOVERY,
        "account_recovery_verify",
        "Recover your account",
    )


def _verify_password_otp(request, purpose, request_url_name, heading):
    session_key = f"pending_{purpose}_email"
    email = request.session.get(session_key)
    if not email:
        return redirect(request_url_name)

    user = User.objects.filter(email__iexact=email, is_active=True).first()
    form = PasswordResetOTPForm(request.POST or None, user=user)
    if request.method == "POST":
        if request.POST.get("action") == "resend":
            if user:
                _request_otp_safely(user, purpose, email, request)
            messages.info(
                request,
                "If an active account matches that address, a code may arrive by email.",
            )
            return redirect(request.path)

        if form.is_valid() and user:
            with transaction.atomic():
                locked_user = (
                    User.objects.select_for_update()
                    .filter(pk=user.pk, email__iexact=email, is_active=True)
                    .first()
                )
                status, _challenge = (
                    verify_otp(
                        locked_user,
                        purpose,
                        email,
                        form.cleaned_data["code"],
                    )
                    if locked_user
                    else ("invalid", None)
                )
                if status == "valid":
                    locked_user.set_password(form.cleaned_data["new_password1"])
                    locked_user.save(update_fields=["password"])
                    user = locked_user

            if status == "valid":
                request.session.pop(session_key, None)
                logger.info("Account password reset by email OTP (user_id=%s)", user.pk)
                messages.success(request, "Your password was updated. Sign in to continue.")
                return redirect("login")
            if status == "expired":
                form.add_error("code", "That code has expired. Request a new one.")
            elif status == "locked":
                form.add_error("code", "Too many incorrect attempts. Request a new code.")
            else:
                form.add_error("code", "That code is incorrect or no longer valid.")
        elif form.is_valid():
            form.add_error("code", "That code is incorrect or no longer valid.")

    challenge = latest_otp(user, purpose, email) if user else None
    expires_at = (
        challenge.expires_at
        if challenge
        else timezone.now() + timedelta(minutes=5)
    )
    resend_at = (
        challenge.created_at + timedelta(seconds=60)
        if challenge
        else timezone.now()
    )
    return render(
        request,
        "registration/otp_password_reset.html",
        {
            "form": form,
            "title": heading,
            "email": mask_email(email),
            "expires_at_ms": int(expires_at.timestamp() * 1000),
            "resend_at_ms": int(resend_at.timestamp() * 1000),
            "resend_url": request.path,
        },
    )


@require_http_methods(["GET", "POST"])
def password_reset_verify(request):
    return _verify_password_otp(
        request,
        EmailOTP.Purpose.PASSWORD_RESET,
        "password_reset_request",
        "Reset your password",
    )


@require_http_methods(["GET", "POST"])
def account_recovery_verify(request):
    return _verify_password_otp(
        request,
        EmailOTP.Purpose.ACCOUNT_RECOVERY,
        "account_recovery_request",
        "Recover your account",
    )


@require_http_methods(["GET", "POST"])
@login_required
def email_change_request(request):
    form = EmailChangeRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["new_email"]
        if not request.user.check_password(form.cleaned_data["current_password"]):
            form.add_error("current_password", "Enter your current password.")
        elif email == request.user.email.casefold():
            form.add_error("new_email", "That is already your current email address.")
        elif User.objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists():
            form.add_error("new_email", "That email address cannot be used.")
        else:
            request.session["pending_email_change_email"] = email
            try:
                issue_otp(
                    request.user,
                    EmailOTP.Purpose.EMAIL_CHANGE,
                    target_email=email,
                    request=request,
                )
            except OTPRequestLimited as error:
                messages.error(
                    request,
                    f"Please wait {error.retry_after} seconds before requesting another code.",
                )
            except OTPDeliveryError as error:
                logger.warning(
                    "OTP delivery unavailable (user_id=%s purpose=%s error=%s)",
                    request.user.pk,
                    EmailOTP.Purpose.EMAIL_CHANGE,
                    error.__class__.__name__,
                )
                messages.error(
                    request,
                    "We could not send the verification email. Please try again later.",
                )
            else:
                messages.success(
                    request,
                    "The email provider accepted the message. Check your inbox and spam folder.",
                )
            return redirect("verify_email_change")

    return render(
        request,
        "registration/email_change_request.html",
        {"form": form},
    )


@require_http_methods(["GET", "POST"])
@login_required
def verify_email_change(request):
    email = request.session.get("pending_email_change_email")
    if not email:
        return redirect("profile")

    if request.method == "POST" and request.POST.get("action") == "resend":
        try:
            issue_otp(
                request.user,
                EmailOTP.Purpose.EMAIL_CHANGE,
                target_email=email,
                request=request,
            )
        except OTPRequestLimited as error:
            messages.error(
                request,
                f"Please wait {error.retry_after} seconds before requesting another code.",
            )
        except OTPDeliveryError as error:
            logger.warning(
                "OTP delivery unavailable (user_id=%s purpose=%s error=%s)",
                request.user.pk,
                EmailOTP.Purpose.EMAIL_CHANGE,
                error.__class__.__name__,
            )
            messages.error(
                request,
                "We could not send the verification email. Please try again later.",
            )
        else:
            messages.success(
                request,
                "The email provider accepted the message. Check your inbox and spam folder.",
            )
        return redirect("verify_email_change")

    form = OTPCodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        status = "invalid"
        try:
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=request.user.pk)
                if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                    status = "email_taken"
                else:
                    status, _challenge = verify_otp(
                        user,
                        EmailOTP.Purpose.EMAIL_CHANGE,
                        email,
                        form.cleaned_data["code"],
                    )
                    if status == "valid":
                        user.email = email
                        user.save(update_fields=["email"])
        except IntegrityError:
            status = "email_taken"

        if status == "valid":
            request.session.pop("pending_email_change_email", None)
            logger.info("Account email verified (user_id=%s)", request.user.pk)
            messages.success(request, "Your email address has been updated.")
            return redirect("profile")
        if status == "expired":
            form.add_error("code", "That code has expired. Request a new one.")
        elif status == "locked":
            form.add_error("code", "Too many incorrect attempts. Request a new code.")
        elif status == "email_taken":
            form.add_error("code", "That address can no longer be used. Start again with another.")
        else:
            form.add_error("code", "That code is incorrect or no longer valid.")

    context = _email_otp_context(
        request.user,
        EmailOTP.Purpose.EMAIL_CHANGE,
        email,
    )
    context.update(
        {
            "form": form,
            "title": "Confirm your new email",
            "intro": "Enter the code sent to your new email address. Your current address stays active until verification.",
            "verify_url": reverse("verify_email_change"),
            "resend_url": reverse("verify_email_change"),
            "show_resend": True,
            "show_password_fields": False,
        }
    )
    return render(request, "registration/otp_verify.html", context)
