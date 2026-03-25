"""
ophix.urls.plugins
~~~~~~~~~~~~~~~~~~
Includes URL patterns contributed by installed Ophix plugins.

Each plugin that wants to register URLs provides a ``urls`` module
at ``<plugin_module>.urls`` containing a ``urlpatterns`` list.
The settings/plugins.py discovery step populates
``settings.OPHIX_PLUGIN_URL_MODULES`` with the list of such modules.

This module builds the corresponding ``include()`` entries.
"""

from django.conf import settings
from django.urls import path, include


def get_plugin_urlpatterns() -> list:
    """
    Return a list of url() entries for all plugin URL modules.
    Plugins contribute their patterns at the root — they are responsible
    for namespacing their own paths (e.g. api/credentials/, api/configs/).
    """
    patterns = []
    for module_name in getattr(settings, "OPHIX_PLUGIN_URL_MODULES", []):
        try:
            patterns.append(path("", include(module_name)))
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).warning(
                "Failed to include URLs from plugin %s: %s", module_name, exc
            )
    return patterns
