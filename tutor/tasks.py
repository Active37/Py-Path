import logging
import time
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from kombu.exceptions import OperationalError
from redis.exceptions import RedisError

from .models import EmailOTP
from .otp import OTPDeliveryError, _otp_code_for_challenge, _send_otp_email


logger = logging.getLogger(__name__)

OTP_DELIVERY_MAX_RETRIES = 3
OTP_DELIVERY_RETRY_DELAYS = (5, 15, 30)
OTP_DELIVERY_LEASE = timedelta(seconds=60)
OTP_QUEUE_STALE_AFTER = timedelta(seconds=60)


def _finish_delivery(challenge_id, status, *, error="", consume=False):
    now = timezone.now()
    updates = {
        "delivery_status": status,
        "delivery_error": error[:64],
        "delivery_completed_at": now
        if status in {EmailOTP.DeliveryStatus.ACCEPTED, EmailOTP.DeliveryStatus.FAILED}
        else None,
    }
    if status == EmailOTP.DeliveryStatus.QUEUED:
        updates["delivery_enqueued_at"] = now
    if consume:
        updates["consumed_at"] = now
    EmailOTP.objects.filter(pk=challenge_id).update(**updates)


@shared_task(
    bind=True,
    name="tutor.send_otp_email",
    max_retries=OTP_DELIVERY_MAX_RETRIES,
    acks_late=True,
    reject_on_worker_lost=True,
    ignore_result=True,
)
def send_otp_email_task(self, challenge_id):
    task_started = time.perf_counter()
    now = timezone.now()
    with transaction.atomic():
        challenge = (
            EmailOTP.objects.select_for_update()
            .filter(pk=challenge_id)
            .first()
        )
        if challenge is None:
            logger.warning("OTP email task skipped (reason=challenge_missing)")
            return "challenge_missing"
        if challenge.consumed_at is not None:
            return "challenge_invalidated"
        if challenge.expires_at <= now:
            _finish_delivery(
                challenge.pk,
                EmailOTP.DeliveryStatus.FAILED,
                error="expired",
                consume=True,
            )
            logger.info(
                "OTP email task skipped (user_id=%s purpose=%s reason=expired)",
                challenge.user_id,
                challenge.purpose,
            )
            return "expired"
        if challenge.delivery_status in {
            EmailOTP.DeliveryStatus.ACCEPTED,
            EmailOTP.DeliveryStatus.FAILED,
        }:
            return challenge.delivery_status
        if (
            challenge.delivery_status == EmailOTP.DeliveryStatus.SENDING
            and challenge.delivery_started_at
            and challenge.delivery_started_at > now - OTP_DELIVERY_LEASE
        ):
            logger.info(
                "OTP email task skipped (user_id=%s purpose=%s reason=already_sending)",
                challenge.user_id,
                challenge.purpose,
            )
            return "already_sending"

        challenge.delivery_status = EmailOTP.DeliveryStatus.SENDING
        challenge.delivery_attempts += 1
        challenge.delivery_started_at = now
        challenge.delivery_error = ""
        challenge.save(
            update_fields=[
                "delivery_status",
                "delivery_attempts",
                "delivery_started_at",
                "delivery_error",
            ]
        )

    queue_latency_ms = max(
        0.0,
        (now - challenge.created_at).total_seconds() * 1000,
    )
    logger.info(
        "OTP email task started (user_id=%s purpose=%s attempt=%s queue_latency_ms=%.1f)",
        challenge.user_id,
        challenge.purpose,
        challenge.delivery_attempts,
        queue_latency_ms,
    )
    try:
        _send_otp_email(
            challenge,
            _otp_code_for_challenge(challenge.pk),
        )
    except OTPDeliveryError as error:
        retry_number = self.request.retries
        retry_delay = OTP_DELIVERY_RETRY_DELAYS[
            min(retry_number, len(OTP_DELIVERY_RETRY_DELAYS) - 1)
        ]
        can_retry = (
            error.retryable
            and retry_number < OTP_DELIVERY_MAX_RETRIES
            and timezone.now() + timedelta(seconds=retry_delay) < challenge.expires_at
            and not settings.CELERY_TASK_ALWAYS_EAGER
        )
        if can_retry:
            _finish_delivery(
                challenge.pk,
                EmailOTP.DeliveryStatus.QUEUED,
                error=error.error_code,
            )
            logger.warning(
                "OTP email retry scheduled "
                "(user_id=%s purpose=%s attempt=%s retry_in_seconds=%s error=%s)",
                challenge.user_id,
                challenge.purpose,
                challenge.delivery_attempts,
                retry_delay,
                error.error_code,
            )
            raise self.retry(exc=error, countdown=retry_delay)

        _finish_delivery(
            challenge.pk,
            EmailOTP.DeliveryStatus.FAILED,
            error=error.error_code or error.__class__.__name__.lower(),
            consume=True,
        )
        logger.error(
            "OTP email delivery permanently failed "
            "(user_id=%s purpose=%s attempts=%s error=%s)",
            challenge.user_id,
            challenge.purpose,
            challenge.delivery_attempts,
            error.error_code or error.__class__.__name__,
        )
        raise
    except Exception as error:
        _finish_delivery(
            challenge.pk,
            EmailOTP.DeliveryStatus.FAILED,
            error=error.__class__.__name__.lower(),
            consume=True,
        )
        logger.exception(
            "OTP email task failed unexpectedly (user_id=%s purpose=%s error=%s)",
            challenge.user_id,
            challenge.purpose,
            error.__class__.__name__,
        )
        raise

    _finish_delivery(
        challenge.pk,
        EmailOTP.DeliveryStatus.ACCEPTED,
    )
    provider_accept_latency_ms = max(
        0.0,
        (timezone.now() - challenge.created_at).total_seconds() * 1000,
    )
    logger.info(
        "OTP email task completed "
        "(user_id=%s purpose=%s total_task_ms=%.1f provider_accept_latency_ms=%.1f)",
        challenge.user_id,
        challenge.purpose,
        (time.perf_counter() - task_started) * 1000,
        provider_accept_latency_ms,
    )
    return "accepted"


@shared_task(
    name="tutor.requeue_stale_otp_emails",
    ignore_result=True,
)
def requeue_stale_otp_emails():
    now = timezone.now()
    stale_before = now - OTP_QUEUE_STALE_AFTER
    expired_jobs = EmailOTP.objects.filter(
        delivery_status__in=[
            EmailOTP.DeliveryStatus.QUEUED,
            EmailOTP.DeliveryStatus.SENDING,
        ],
        consumed_at__isnull=True,
        expires_at__lte=now,
    ).update(
        delivery_status=EmailOTP.DeliveryStatus.FAILED,
        delivery_completed_at=now,
        delivery_error="expired",
        consumed_at=now,
    )
    if expired_jobs:
        logger.warning("Expired OTP email jobs marked failed (count=%s)", expired_jobs)

    challenges = EmailOTP.objects.filter(
        delivery_status=EmailOTP.DeliveryStatus.QUEUED,
        consumed_at__isnull=True,
        expires_at__gt=now,
    ).filter(
        Q(delivery_enqueued_at__isnull=True)
        | Q(delivery_enqueued_at__lte=stale_before)
    ).order_by("created_at").values_list("pk", "expires_at")[:100]

    enqueued = 0
    for challenge_id, expires_at in challenges:
        try:
            send_otp_email_task.apply_async(
                args=[str(challenge_id)],
                task_id=f"otp-{challenge_id}",
                expires=expires_at,
            )
        except (OperationalError, RedisError, OSError) as error:
            logger.error(
                "Stale OTP email could not be requeued "
                "(challenge_id=%s error=%s)",
                challenge_id,
                error.__class__.__name__,
            )
            continue
        updated = EmailOTP.objects.filter(
            pk=challenge_id,
            delivery_status=EmailOTP.DeliveryStatus.QUEUED,
            consumed_at__isnull=True,
        ).update(delivery_enqueued_at=now)
        enqueued += updated

    if enqueued:
        logger.warning("Stale OTP email jobs requeued (count=%s)", enqueued)
    return enqueued
