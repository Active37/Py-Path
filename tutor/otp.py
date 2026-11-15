import hashlib
import hmac
import logging
import secrets
import smtplib
from email.utils import parseaddr
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import EmailOTP


logger = logging.getLogger(__name__)

OTP_LIFETIME = timedelta(minutes=5)
OTP_RESEND_COOLDOWN = timedelta(seconds=60)
OTP_MAX_ATTEMPTS = 5
OTP_MAX_USER_REQUESTS_PER_HOUR = 5
OTP_MAX_IP_REQUESTS_PER_HOUR = 20


class OTPRequestLimited(Exception):
    def __init__(self, retry_after):
        self.retry_after = max(1, int(retry_after))
        super().__init__("OTP request limit reached.")


class OTPDeliveryError(Exception):
    pass


def _ensure_email_is_configured():
    if settings.DEBUG and not settings.EMAIL_HOST:
        return
    sender_address = parseaddr(settings.DEFAULT_FROM_EMAIL)[1].lower()
    support_address = parseaddr(settings.SUPPORT_EMAIL)[1].lower()
    if (
        not settings.EMAIL_HOST
        or "@" not in sender_address
        or sender_address.endswith(".local")
        or "@" not in support_address
        or support_address.endswith(".local")
    ):
        raise OTPDeliveryError("Production email delivery is not configured.")


def _invalidate_challenge(challenge):
    EmailOTP.objects.filter(
        pk=challenge.pk,
        consumed_at__isnull=True,
    ).update(consumed_at=timezone.now())


def _ip_fingerprint(request):
    if request is None:
        return ""
    ip_address = request.META.get("REMOTE_ADDR", "").strip()
    if not ip_address:
        return ""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        ip_address.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _otp_digest(challenge_id, code):
    message = f"{challenge_id}:{code}".encode("utf-8")
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def _send_otp_email(challenge, code):
    try:
        _ensure_email_is_configured()
    except OTPDeliveryError:
        _invalidate_challenge(challenge)
        raise

    purpose_labels = {
        EmailOTP.Purpose.REGISTRATION: "verify your email address",
        EmailOTP.Purpose.PASSWORD_RESET: "reset your password",
        EmailOTP.Purpose.EMAIL_CHANGE: "confirm your new email address",
        EmailOTP.Purpose.ACCOUNT_RECOVERY: "recover your PyPath account",
    }
    purpose_label = purpose_labels[challenge.purpose]
    context = {
        "code": code,
        "purpose_label": purpose_label,
        "support_email": parseaddr(settings.SUPPORT_EMAIL)[1],
    }
    subject = f"Your PyPath code to {purpose_label}"
    text_body = render_to_string("emails/email_otp.txt", context)
    html_body = render_to_string("emails/email_otp.html", context)
    email = EmailMultiAlternatives(
        subject,
        text_body,
        settings.DEFAULT_FROM_EMAIL,
        [challenge.target_email],
    )
    email.attach_alternative(html_body, "text/html")
    try:
        if email.send(fail_silently=False) != 1:
            raise smtplib.SMTPException("Email provider did not accept the message.")
    except (OSError, ValueError, smtplib.SMTPException) as error:
        _invalidate_challenge(challenge)
        logger.error(
            "OTP email delivery failed (purpose=%s, error=%s)",
            challenge.purpose,
            error.__class__.__name__,
        )
        raise OTPDeliveryError("We could not send the verification email.") from error


def issue_otp(user, purpose, target_email=None, request=None):
    now = timezone.now()
    email = (target_email or user.email).strip().casefold()
    ip_hash = _ip_fingerprint(request)
    user_model = get_user_model()

    with transaction.atomic():
        locked_user = user_model._default_manager.select_for_update().get(pk=user.pk)
        latest = EmailOTP.objects.filter(
            user=locked_user,
            purpose=purpose,
        ).order_by("-created_at").first()
        if latest and now < latest.created_at + OTP_RESEND_COOLDOWN:
            raise OTPRequestLimited(
                (latest.created_at + OTP_RESEND_COOLDOWN - now).total_seconds()
            )

        one_hour_ago = now - timedelta(hours=1)
        user_request_count = EmailOTP.objects.filter(
            user=locked_user,
            created_at__gte=one_hour_ago,
        ).count()
        if user_request_count >= OTP_MAX_USER_REQUESTS_PER_HOUR:
            oldest_user_request = EmailOTP.objects.filter(
                user=locked_user,
                created_at__gte=one_hour_ago,
            ).order_by("created_at").first()
            raise OTPRequestLimited(
                (oldest_user_request.created_at + timedelta(hours=1) - now).total_seconds()
            )

        if ip_hash:
            ip_request_count = EmailOTP.objects.filter(
                request_ip_hash=ip_hash,
                created_at__gte=one_hour_ago,
            ).count()
            if ip_request_count >= OTP_MAX_IP_REQUESTS_PER_HOUR:
                oldest_ip_request = EmailOTP.objects.filter(
                    request_ip_hash=ip_hash,
                    created_at__gte=one_hour_ago,
                ).order_by("created_at").first()
                raise OTPRequestLimited(
                    (oldest_ip_request.created_at + timedelta(hours=1) - now).total_seconds()
                )

        EmailOTP.objects.filter(
            user=locked_user,
            purpose=purpose,
            consumed_at__isnull=True,
        ).update(consumed_at=now)

        code = f"{secrets.randbelow(1_000_000):06d}"
        challenge_id = uuid4()
        challenge = EmailOTP.objects.create(
            id=challenge_id,
            user=locked_user,
            purpose=purpose,
            target_email=email,
            otp_hash=_otp_digest(challenge_id, code),
            expires_at=now + OTP_LIFETIME,
            request_ip_hash=ip_hash,
        )

    _send_otp_email(challenge, code)
    return challenge


def verify_otp(user, purpose, target_email, submitted_code):
    now = timezone.now()
    with transaction.atomic():
        challenge = (
            EmailOTP.objects.select_for_update()
            .filter(
                user=user,
                purpose=purpose,
                target_email__iexact=target_email,
                consumed_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )
        if challenge is None:
            return "invalid", None
        if challenge.expires_at <= now:
            challenge.consumed_at = now
            challenge.save(update_fields=["consumed_at"])
            return "expired", challenge

        valid_code = (
            isinstance(submitted_code, str)
            and len(submitted_code) == 6
            and submitted_code.isascii()
            and submitted_code.isdigit()
            and hmac.compare_digest(
                _otp_digest(challenge.pk, submitted_code),
                challenge.otp_hash,
            )
        )
        if not valid_code:
            challenge.attempts += 1
            update_fields = ["attempts"]
            if challenge.attempts >= OTP_MAX_ATTEMPTS:
                challenge.consumed_at = now
                update_fields.append("consumed_at")
            challenge.save(update_fields=update_fields)
            return (
                "locked" if challenge.consumed_at is not None else "invalid",
                challenge,
            )

        challenge.consumed_at = now
        challenge.save(update_fields=["consumed_at"])
        return "valid", challenge


def latest_otp(user, purpose, target_email):
    return (
        EmailOTP.objects.filter(
            user=user,
            purpose=purpose,
            target_email__iexact=target_email,
        )
        .order_by("-created_at")
        .first()
    )


def mask_email(email):
    try:
        local_part, domain = email.rsplit("@", 1)
    except ValueError:
        return ""
    visible = local_part[:1]
    return f"{visible}{'*' * max(2, min(len(local_part) - 1, 6))}@{domain}"
