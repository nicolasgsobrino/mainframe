from __future__ import annotations

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.getenv("DJANGO_DEBUG", "0").lower() in {"1", "true"}
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
RUNNING_TESTS = any("pytest" in arg for arg in sys.argv)
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "carddemo-dev-only-secret-key"
    elif RUNNING_TESTS:
        SECRET_KEY = "carddemo-test-secret-key"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is disabled")
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0").split(",")
    if host.strip()
]
if RUNNING_TESTS and "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "models.apps.ModelsConfig",
    "screens",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "carddemo.urls"
WSGI_APPLICATION = "carddemo.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if os.getenv("CARDDEMO_SQLITE") == "1":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "carddemo.sqlite3",
        }
    }
    MIGRATION_MODULES = {"models": None}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "carddemo"),
            "USER": os.getenv("POSTGRES_USER", "carddemo"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "carddemo"),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Los_Angeles"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]
