import os
from pathlib import Path
from urllib.parse import urlsplit

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEVELOPMENT_SECRET_KEY = "development-only-change-me"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", DEVELOPMENT_SECRET_KEY)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
if not DEBUG and SECRET_KEY == DEVELOPMENT_SECRET_KEY:
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY when DJANGO_DEBUG=0.")
render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if DEBUG:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
else:
    ALLOWED_HOSTS = [
        host.strip()
        for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    ]
    if render_hostname:
        ALLOWED_HOSTS.append(render_hostname)
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
if not DEBUG and render_hostname:
    CSRF_TRUSTED_ORIGINS.append(f"https://{render_hostname}")
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600
AI_API_BASE_URL = os.environ.get(
    "AI_API_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta",
)
AI_API_KEY = os.environ.get("AI_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "gemini-flash-latest")
AI_API_TIMEOUT = float(os.environ.get("AI_API_TIMEOUT", "60"))
EMAIL_HOST = os.environ.get("EMAIL_HOST", "").strip()
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").strip().lower() in {
    "1",
    "true",
    "yes",
}
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "false").strip().lower() in {
    "1",
    "true",
    "yes",
}
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured("Choose either EMAIL_USE_TLS or EMAIL_USE_SSL, not both.")
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10"))
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    "PyPath <no-reply@pypath.local>",
).strip()
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@pypath.local").strip()
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST or not DEBUG
    else "django.core.mail.backends.console.EmailBackend"
)
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "").strip()
if DEBUG and not CELERY_BROKER_URL:
    CELERY_BROKER_URL = "memory://"
if not DEBUG and not CELERY_BROKER_URL:
    raise ImproperlyConfigured(
        "Set CELERY_BROKER_URL to the private Render Key Value URL."
    )
CELERY_TASK_ALWAYS_EAGER = DEBUG
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_TIMEOUT = 2
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_PUBLISH_RETRY = False
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": 120}
CELERY_TASK_SOFT_TIME_LIMIT = 25
CELERY_TASK_TIME_LIMIT = 35
CODE_RUNNER_URL = os.environ.get("CODE_RUNNER_URL", "")
CODE_RUNNER_API_KEY = os.environ.get("CODE_RUNNER_API_KEY", "")
CODE_RUNNER_LANGUAGE_ID = int(os.environ.get("CODE_RUNNER_LANGUAGE_ID") or "71")
CODE_RUNNER_JAVA_LANGUAGE_ID = int(
    os.environ.get("CODE_RUNNER_JAVA_LANGUAGE_ID") or "62"
)
CODE_RUNNER_TIMEOUT = float(os.environ.get("CODE_RUNNER_TIMEOUT") or "30")
if CODE_RUNNER_URL:
    try:
        parsed_code_runner_url = urlsplit(CODE_RUNNER_URL)
    except ValueError as error:
        raise ImproperlyConfigured("CODE_RUNNER_URL must be a valid HTTP(S) URL.") from error
    if (
        parsed_code_runner_url.scheme not in {"http", "https"}
        or not parsed_code_runner_url.hostname
        or parsed_code_runner_url.username
        or parsed_code_runner_url.password
        or parsed_code_runner_url.query
        or parsed_code_runner_url.fragment
    ):
        raise ImproperlyConfigured(
            "CODE_RUNNER_URL must contain only an HTTP(S) scheme and host, without credentials or query parameters."
        )
    if not DEBUG and parsed_code_runner_url.scheme != "https":
        raise ImproperlyConfigured("CODE_RUNNER_URL must use HTTPS when DJANGO_DEBUG=0.")
    if not DEBUG and not CODE_RUNNER_API_KEY:
        raise ImproperlyConfigured(
            "Set CODE_RUNNER_API_KEY before enabling the code runner in production."
        )
DATA_UPLOAD_MAX_MEMORY_SIZE = 20_000

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "tutor",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "tutor.middleware.RequestAuditMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise ImproperlyConfigured(
        "Set DATABASE_URL to a PostgreSQL connection string in every environment."
    )
try:
    parsed_database_url = urlsplit(DATABASE_URL)
    database_hostname = parsed_database_url.hostname
except ValueError as error:
    raise ImproperlyConfigured(
        "DATABASE_URL is malformed; set the full PostgreSQL connection URL in the hosting environment."
    ) from error
if (
    parsed_database_url.scheme not in {"postgres", "postgresql"}
    or not database_hostname
    or not parsed_database_url.path.strip("/")
):
    raise ImproperlyConfigured(
        "DATABASE_URL must be a full PostgreSQL URL starting with "
        "postgresql:// and containing a host and database name. "
        "Check the hosting environment variable value."
    )

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=0,
        conn_health_checks=True,
        ssl_require=not DEBUG,
    )
}
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("DATABASE_URL must use PostgreSQL.")

AUTHENTICATION_BACKENDS = [
    "tutor.auth.EmailOrLegacyUsernameBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO").upper(),
            "propagate": False,
        },
        "tutor": {
            "handlers": ["console"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO").upper(),
            "propagate": False,
        },
    },
}
