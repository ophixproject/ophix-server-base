"""
ophix.urls
~~~~~~~~~~
Final URL configuration for all Ophix Project Servers.

Assembly order:
  1. base patterns     — admin, i18n, standard Ophix API
  2. plugin patterns   — contributed by installed domain plugins
  3. catch-all         — redirect everything else to /admin/
                         (must be absolutely last)
"""

from django.urls import re_path
from django.views.generic.base import RedirectView

from .base import urlpatterns as base_patterns
from .plugins import get_plugin_urlpatterns

urlpatterns = (
    base_patterns
    + get_plugin_urlpatterns()
    + [
        # Catch-all — redirect unmatched paths to admin.
        # Must be the final entry.
        re_path(r"^.*$", RedirectView.as_view(url="/admin/", permanent=False)),
    ]
)
