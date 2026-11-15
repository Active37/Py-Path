import os

from celery import Celery
from celery.schedules import schedule


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("pypath")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.conf.beat_schedule = {
    "requeue-stale-otp-emails": {
        "task": "tutor.requeue_stale_otp_emails",
        "schedule": schedule(30.0),
    }
}
