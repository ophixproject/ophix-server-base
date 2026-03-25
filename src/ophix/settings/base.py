"""
ophix.settings.base
~~~~~~~~~~~~~~~~~~~
Core Django settings for all Ophix Project Servers.

These settings are intentionally complete and self-contained.
Server-specific overrides belong in the server's own .env file,
not in this module.
"""

import os
from pathlib import Path

from django.core.management.utils import get_random_secret_key
from dotenv import load_dotenv, set_key, find_dotenv

from .utils import get_bool_env, get_list_env, get_int_env, get_path_env

# ---------------------------------------------------------------------------
# Load environment
# ---------------------------------------------------------------------------

load_dotenv(find_dotenv(usecwd=True))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# The Django project lives inside the installed ophix package.
# INSTALL_DIR is where persistent runtime data (media, fixtures, etc.) lives
# outside the package — survives version upgrades.
BASE_DIR = Path(__file__).resolve().parent.parent

INSTALL_DIR = get_path_env("INSTALL_DIR", "/home/websites/ophix")

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = get_random_secret_key()
    env_file = find_dotenv(usecwd=True) or ".env"
    set_key(env_file, "DJANGO_SECRET_KEY", SECRET_KEY)

DEBUG = get_bool_env("DEBUG", default=False)

ALLOWED_HOSTS = get_list_env("ALLOWED_HOSTS", default=["*"])

# ---------------------------------------------------------------------------
# Server identity
# ---------------------------------------------------------------------------

# Human-readable name shown in the admin header and footer.
# Each deployed server sets this in .env — e.g. "CredServer", "ConfServer".
SERVER_NAME = os.getenv("SERVER_NAME", "Ophix Server")

# Machine-readable version string set by deploy_release.sh.
SERVER_VERSION = os.getenv("SERVER_VERSION", "")

# ---------------------------------------------------------------------------
# Applications
# Plugins append to this list via ophix.settings.plugins.
# Order matters: apptemplates and admin_interface must precede django.contrib.admin.
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    # Admin interface overrides — must be first
    "apptemplates",
    "admin_interface",
    "colorfield",

    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",

    # Ophix base — Host, Client, token auth, standard API
    "ophix.core",
]

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ---------------------------------------------------------------------------
# URLs & WSGI/ASGI
# ---------------------------------------------------------------------------

ROOT_URLCONF = "ophix.urls"
WSGI_APPLICATION = "ophix.wsgi.application"
ASGI_APPLICATION = "ophix.asgi.application"
APPEND_SLASH = True

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "core" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "ophix.core.context_processors.server_info",
                "ophix.core.context_processors.ui_flags",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database — MariaDB via MySQL backend
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME", "ophix_db"),
        "USER": os.getenv("DB_USER", "ophixuser"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "en-au")

LANGUAGES = [
    ("en-au", "Australian English"),
    ("en-us", "American English"),
]

# Locale files from all installed apps are discovered automatically via APP_DIRS.
LOCALE_PATHS = [
    BASE_DIR / "core" / "locale",
]

TIME_ZONE = os.getenv("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    d for d in [BASE_DIR / "core" / "static"]
    if d.exists()
]

MEDIA_URL = "/media/"
MEDIA_ROOT = get_path_env("DJANGO_MEDIA_ROOT", INSTALL_DIR / "media")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_DIRS = [
    BASE_DIR / "core" / "fixtures",
    INSTALL_DIR / "fixtures",
]

# ---------------------------------------------------------------------------
# Primary key type
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Django REST Framework
# Authentication and permission classes are empty at the framework level —
# each view declares its own via authentication_classes / permission_classes.
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
}

# ---------------------------------------------------------------------------
# Admin interface (django-admin-interface)
# ---------------------------------------------------------------------------

X_FRAME_OPTIONS = "SAMEORIGIN"
SILENCED_SYSTEM_CHECKS = ["security.W019"]

# UI flags — control visibility of various admin sections.
# All default to False (hidden); enable in .env as required.
DISPLAY_VERSION_FOOTER = get_bool_env("DISPLAY_VERSION_FOOTER", default=False)
DISPLAY_COPYRIGHT = get_bool_env("DISPLAY_COPYRIGHT", default=True)
ADMIN_THEME_EDITABLE = get_bool_env("ADMIN_THEME_EDITABLE", default=False)
SHOW_AUTH_MODELS = get_bool_env("SHOW_AUTH_MODELS", default=False)
SHOW_CLIENT_ARTIFACT_MODEL = get_bool_env("SHOW_CLIENT_ARTIFACT_MODEL", default=False)

# ---------------------------------------------------------------------------
# Ophix base API settings
# ---------------------------------------------------------------------------

# When True, error responses include detail messages that may leak information
# about internal state (useful in development, should be False in production).
AUTH_LEAK_INFO = get_bool_env("AUTH_LEAK_INFO", default=False)

# Minimum seconds between token rotations to prevent abuse. Default: 1 hour.
MINIMUM_TOKEN_ROTATE_TIME = get_int_env("MINIMUM_TOKEN_ROTATE_TIME", default=3600)

# Allow clients to delete artifacts they own. Disabled by default.
ENABLE_ARTIFACT_DELETE = get_bool_env("ENABLE_ARTIFACT_DELETE", default=False)
