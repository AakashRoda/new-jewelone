"""Settings for the store app.

Configuration comes from environment variables so that the same code runs in
the local demo, in tests and (later) in a deployed environment. Nothing in
this file is a business rule; see docs/register.md for those.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable {name}")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


# DEMO_MODE marks an environment that holds synthetic data and demo roles.
# It defaults to on because no production deployment has been agreed (O12).
DEMO_MODE = env_bool("STOREAPP_DEMO_MODE", True)

DEBUG = env_bool("STOREAPP_DEBUG", False)

SECRET_KEY = os.environ.get("STOREAPP_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEMO_MODE:
        raise RuntimeError("STOREAPP_SECRET_KEY must be set when STOREAPP_DEMO_MODE is off")
    SECRET_KEY = "demo-only-insecure-key-do-not-use-with-real-stock"

ALLOWED_HOSTS = [h.strip() for h in env("STOREAPP_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("STOREAPP_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
    "audit",
    "masters",
    "inventory",
    "purchasing",
    "demo",
]
# django.contrib.admin is deliberately not installed: it would allow direct
# edits and deletes of receipts and stock history outside the audited
# commands (C11: no silent administrator rewrite).

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
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
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context.app_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("STOREAPP_DB_NAME", "storeapp"),
        "USER": env("STOREAPP_DB_USER", "storeapp"),
        "PASSWORD": env("STOREAPP_DB_PASSWORD", "storeapp"),
        "HOST": env("STOREAPP_DB_HOST", "127.0.0.1"),
        "PORT": env("STOREAPP_DB_PORT", "5432"),
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "stock-overview"
LOGOUT_REDIRECT_URL = "login"

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# Lets the local demo serve CSS and JS without a collectstatic step.
WHITENOISE_USE_FINDERS = DEBUG or DEMO_MODE

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if not DEBUG and not DEMO_MODE:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
