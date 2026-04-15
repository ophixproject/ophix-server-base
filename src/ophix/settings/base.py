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
    # Only persist the generated key if a .env file already exists.
    # On a fresh install with no .env yet, we generate in memory only —
    # the operator copies .env.sample → .env and the key is written on
    # first real startup.  Without this guard, running any management
    # command (e.g. generate_deploy_config) before .env exists would
    # silently create a .env containing only DJANGO_SECRET_KEY, which
    # confuses the bootstrap workflow.
    env_file = find_dotenv(usecwd=True)
    if env_file:
        set_key(env_file, "DJANGO_SECRET_KEY", SECRET_KEY)

DEBUG = get_bool_env("DEBUG", default=False)

ALLOWED_HOSTS = get_list_env("ALLOWED_HOSTS", default=["*"])

# ---------------------------------------------------------------------------
# Server identity
# ---------------------------------------------------------------------------

# Human-readable name for this server instance.
# NOT set here — the installed domain plugin provides the default
# (e.g. ophix-certs sets "certserver", ophix-creds sets "credserver").
# Override in .env to customise for a specific deployment.
# Falls back to "Ophix Server" in the context processor if no domain is installed.

# Machine-readable version string — auto-populated by generate_deploy_config.
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
# Database
# DB_ENGINE: mariadb (default) | mysql | postgres
# ---------------------------------------------------------------------------

_db_engine = os.getenv("DB_ENGINE", "mariadb").lower()
_db_ssl_ca = os.getenv("DB_SSL_CA", "")
_db_ssl_cert = os.getenv("DB_SSL_CERT", "")
_db_ssl_key = os.getenv("DB_SSL_KEY", "")

if _db_engine == "postgres":
    _db_options = {}
    if _db_ssl_ca:
        _db_options["sslmode"] = "verify-ca"
        _db_options["sslrootcert"] = _db_ssl_ca
        if _db_ssl_cert:
            _db_options["sslcert"] = _db_ssl_cert
        if _db_ssl_key:
            _db_options["sslkey"] = _db_ssl_key
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "ophix_db"),
            "USER": os.getenv("DB_USER", "ophixuser"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "OPTIONS": _db_options,
        }
    }
else:
    # mariadb / mysql — the Django MySQL backend handles both
    _db_options = {
        "charset": "utf8mb4",
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
    }
    if _db_ssl_ca:
        _ssl = {"ca": _db_ssl_ca}
        if _db_ssl_cert:
            _ssl["cert"] = _db_ssl_cert
        if _db_ssl_key:
            _ssl["key"] = _db_ssl_key
        _db_options["ssl"] = _ssl
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "ophix_db"),
            "USER": os.getenv("DB_USER", "ophixuser"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "3306"),
            "OPTIONS": _db_options,
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
DISPLAY_COPYRIGHT = get_bool_env("DISPLAY_COPYRIGHT", default=False)
SHOW_THEME_MODEL = get_bool_env("SHOW_THEME_MODEL", default=False)
SHOW_AUTH_MODELS = get_bool_env("SHOW_AUTH_MODELS", default=False)
SHOW_CLIENT_ARTIFACT_MODEL = get_bool_env("SHOW_CLIENT_ARTIFACT_MODEL", default=False)
SHOW_ACCESS_LOGS = get_bool_env("SHOW_ACCESS_LOGS", default=False)

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

# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

# Number of events to accumulate before writing a batch.
AUDIT_BATCH_SIZE = get_int_env("AUDIT_BATCH_SIZE", default=50)

# Maximum seconds to wait before flushing a partial batch.
AUDIT_FLUSH_INTERVAL = get_int_env("AUDIT_FLUSH_INTERVAL", default=5)
