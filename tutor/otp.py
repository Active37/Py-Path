import hashlib
import hmac
import logging
import re
import smtplib
import time
from email.utils import parseaddr
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import transaction
from django.db.models import Count, Min
from django.template.loader import render_to_string
from django.utils import timezone
from kombu.exceptions import OperationalError
from redis.exceptions import RedisError

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
    def __init__(self, message, *, retryable=False, error_code="delivery_failed"):
        self.retryable = retryable
        self.error_code = error_code
        super().__init__(message)


def _ensure_email_is_configured():
    if settings.DEBUG and not settings.EMAIL_HOST:
        return
    sender_address = parseaddr(settings.DEFAULT_FROM_EMAIL)[1].lower()
    support_address = parseaddr(settings.SUPPORT_EMAIL)[1].lower()
    missing_settings = []
    if not settings.EMAIL_HOST:
        missing_settings.append("EMAIL_HOST")
    if (
        settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
        and not settings.EMAIL_HOST_USER
    ):
        missing_settings.append("EMAIL_HOST_USER")
    if (
        settings.EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
        and not settings.EMAIL_HOST_PASSWORD
    ):
        missing_settings.append("EMAIL_HOST_PASSWORD")
    if "@" not in sender_address or sender_address.endswith(".local"):
        missing_settings.append("DEFAULT_FROM_EMAIL")
    if "@" not in support_address or support_address.endswith(".local"):
        missing_settings.append("SUPPORT_EMAIL")
    if missing_settings:
        raise OTPDeliveryError(
            f"Email delivery is missing valid configuration: {', '.join(missing_settings)}."
        )


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


def _otp_code_for_challenge(challenge_id):
    key = settings.SECRET_KEY.encode("utf-8")
    counter = 0
    sample_limit = (1 << 64) - ((1 << 64) % 1_000_000)
    while True:
        message = f"pypath-email-otp:{challenge_id}:{counter}".encode("utf-8")
        digest = hmac.new(key, message, hashlib.sha256).digest()
        sample = int.from_bytes(digest[:8], "big")
        if sample < sample_limit:
            return f"{sample % 1_000_000:06d}"
        counter += 1


def _smtp_failure_details(error):
    smtp_code = getattr(error, "smtp_code", None)
    smtp_response = getattr(error, "smtp_error", None)
    if isinstance(error, smtplib.SMTPRecipientsRefused) and error.recipients:
        smtp_code, smtp_response = next(iter(error.recipients.values()))
    if isinstance(smtp_response, bytes):
        smtp_response = smtp_response.decode("utf-8", errors="replace")
    if not isinstance(smtp_response, str):
        smtp_response = ""

    smtp_response = re.sub(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "[redacted-email]",
        smtp_response,
        flags=re.IGNORECASE,
    )
    for secret in (settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD):
        if secret:
            smtp_response = smtp_response.replace(secret, "[redacted]")
    smtp_response = re.sub(r"[\r\n\t]+", " ", smtp_response).strip()[:240]
    return smtp_code, smtp_response


def _smtp_error_code(error, smtp_code):
    if isinstance(error, smtplib.SMTPServerDisconnected):
        return "connection_error"
    if smtp_code:
        return f"smtp_{int(smtp_code)}"
    if isinstance(error, (TimeoutError, OSError)) and not isinstance(
        error,
        smtplib.SMTPException,
    ):
        return "connection_error"
    return error.__class__.__name__.lower()[:64]


def _smtp_error_is_retryable(error, smtp_code):
    if isinstance(error, smtplib.SMTPServerDisconnected):
        return True
    if isinstance(error, smtplib.SMTPException):
        return smtp_code is not None and 400 <= int(smtp_code) < 500
    if isinstance(error, (TimeoutError, OSError)):
        return True
    return smtp_code is not None and 400 <= int(smtp_code) < 500


def _send_otp_email(challenge, code):
    try:
        _ensure_email_is_configured()
    except OTPDeliveryError as error:
        logger.error(
            "OTP email delivery blocked by configuration "
            "(user_id=%s purpose=%s detail=%s)",
            challenge.user_id,
            challenge.purpose,
            error,
        )
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
    connection = get_connection(fail_silently=False)
    connection_started = time.perf_counter()
    connection_ms = None
    provider_response_ms = None
    logger.info(
        "OTP email send attempted (user_id=%s purpose=%s)",
        challenge.user_id,
        challenge.purpose,
    )
    try:
        connection.open()
        connection_ms = (time.perf_counter() - connection_started) * 1000
        provider_started = time.perf_counter()
        email.connection = connection
        accepted = email.send(fail_silently=False)
        provider_response_ms = (time.perf_counter() - provider_started) * 1000
        if accepted != 1:
            raise smtplib.SMTPException("Email provider did not accept the message.")
    except (OSError, ValueError, smtplib.SMTPException) as error:
        if connection_ms is None:
            connection_ms = (time.perf_counter() - connection_started) * 1000
        smtp_code, smtp_response = _smtp_failure_details(error)
        error_code = _smtp_error_code(error, smtp_code)
        logger.error(
            "OTP email delivery failed "
            "(user_id=%s purpose=%s error=%s smtp_code=%s smtp_response=%s "
            "smtp_connect_ms=%.1f provider_response_ms=%s)",
            challenge.user_id,
            challenge.purpose,
            error.__class__.__name__,
            smtp_code or "unavailable",
            smtp_response or "unavailable",
            connection_ms,
            (
                f"{provider_response_ms:.1f}"
                if provider_response_ms is not None
                else "unavailable"
            ),
        )
        raise OTPDeliveryError(
            "We could not send the verification email.",
            retryable=_smtp_error_is_retryable(error, smtp_code),
            error_code=error_code,
        ) from error
    finally:
        connection.close()
    logger.info(
        "OTP email accepted by provider "
        "(user_id=%s purpose=%s smtp_connect_ms=%.1f provider_response_ms=%.1f)",
        challenge.user_id,
        challenge.purpose,
        connection_ms,
        provider_response_ms,
    )


def issue_otp(user, purpose, target_email=None, request=None):
    started = time.perf_counter()
    now = timezone.now()
    email = (target_email or user.email).strip().casefold()
    ip_hash = _ip_fingerprint(request)
    user_model = get_user_model()
    challenge_id = uuid4()
    generation_started = time.perf_counter()
    code = _otp_code_for_challenge(challenge_id)
    generation_ms = (time.perf_counter() - generation_started) * 1000

    persistence_started = time.perf_counter()
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
        user_request_stats = EmailOTP.objects.filter(
            user=locked_user,
            created_at__gte=one_hour_ago,
        ).aggregate(count=Count("pk"), oldest=Min("created_at"))
        if user_request_stats["count"] >= OTP_MAX_USER_REQUESTS_PER_HOUR:
            raise OTPRequestLimited(
                (
                    user_request_stats["oldest"] + timedelta(hours=1) - now
                ).total_seconds()
            )

        if ip_hash:
            ip_request_stats = EmailOTP.objects.filter(
                request_ip_hash=ip_hash,
                created_at__gte=one_hour_ago,
            ).aggregate(count=Count("pk"), oldest=Min("created_at"))
            if ip_request_stats["count"] >= OTP_MAX_IP_REQUESTS_PER_HOUR:
                raise OTPRequestLimited(
                    (
                        ip_request_stats["oldest"] + timedelta(hours=1) - now
                    ).total_seconds()
                )

        EmailOTP.objects.filter(
            user=locked_user,
            purpose=purpose,
            consumed_at__isnull=True,
        ).update(consumed_at=now)

        challenge = EmailOTP.objects.create(
            id=challenge_id,
            user=locked_user,
            purpose=purpose,
            target_email=email,
            otp_hash=_otp_digest(challenge_id, code),
            expires_at=now + OTP_LIFETIME,
            request_ip_hash=ip_hash,
            delivery_status=EmailOTP.DeliveryStatus.QUEUED,
        )
    persistence_ms = (time.perf_counter() - persistence_started) * 1000

    logger.info(
        "OTP generated and persisted "
        "(user_id=%s purpose=%s generation_ms=%.1f persistence_ms=%.1f)",
        locked_user.pk,
        purpose,
        generation_ms,
        persistence_ms,
    )
    queue_started = time.perf_counter()
    from .tasks import send_otp_email_task

    try:
        send_otp_email_task.apply_async(args=[str(challenge.pk)])
    except (OperationalError, RedisError, OSError) as error:
        _finish_time = timezone.now()
        EmailOTP.objects.filter(
            pk=challenge.pk,
            consumed_at__isnull=True,
        ).update(
            delivery_status=EmailOTP.DeliveryStatus.FAILED,
            delivery_completed_at=_finish_time,
            delivery_error="queue_unavailable",
            consumed_at=_finish_time,
        )
        elapsed_ms = (time.perf_counter() - queue_started) * 1000
        logger.error(
            "OTP email could not be queued "
            "(user_id=%s purpose=%s error=%s queue_publish_ms=%.1f)",
            locked_user.pk,
            purpose,
            error.__class__.__name__,
            elapsed_ms,
        )
        raise OTPDeliveryError(
            "The verification email could not be queued. Please try again.",
            error_code="queue_unavailable",
        ) from error

    if settings.CELERY_TASK_ALWAYS_EAGER:
        challenge.refresh_from_db(fields=["delivery_status"])
    EmailOTP.objects.filter(
        pk=challenge.pk,
        delivery_status=EmailOTP.DeliveryStatus.QUEUED,
        consumed_at__isnull=True,
    ).update(delivery_enqueued_at=timezone.now())
    queue_publish_ms = (time.perf_counter() - queue_started) * 1000
    delivery_status = (
        challenge.delivery_status
        if settings.CELERY_TASK_ALWAYS_EAGER
        else EmailOTP.DeliveryStatus.QUEUED
    )
    logger.info(
        "OTP email submission completed "
        "(user_id=%s purpose=%s status=%s submission_ms=%.1f total_ms=%.1f)",
        locked_user.pk,
        purpose,
        delivery_status,
        queue_publish_ms,
        (time.perf_counter() - started) * 1000,
    )
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
