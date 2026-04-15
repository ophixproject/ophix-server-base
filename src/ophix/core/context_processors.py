"""
ophix.core.context_processors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Template context processors for Ophix admin templates.
"""

from django.conf import settings


def server_info(request) -> dict:
    """Inject SERVER_NAME and SERVER_VERSION into every template."""
    return {
        "server_name": getattr(settings, "SERVER_NAME", "Ophix Server"),
        "server_version": getattr(settings, "SERVER_VERSION", ""),
    }


def ui_flags(request) -> dict:
    """Inject UI visibility flags into every template."""
    return {
        "display_version_footer": getattr(settings, "DISPLAY_VERSION_FOOTER", False),
        "display_copyright": getattr(settings, "DISPLAY_COPYRIGHT", True),
        "oidc_enabled": getattr(settings, "OIDC_ENABLED", False),
    }
