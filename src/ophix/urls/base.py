"""
ophix.urls.base
~~~~~~~~~~~~~~~
URL patterns that are present on every Ophix Project Server regardless
of which domain plugin is installed.

Includes:
  - Django admin
  - i18n language switching
  - Standard Ophix API endpoints (register, ca-cert, client self-management)
  - Catch-all redirect to /admin/ (must remain last)
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path, include
from django.views.i18n import set_language
from django.views.generic.base import RedirectView
from rest_framework.routers import DefaultRouter

from ophix.core.views import (
    RegisterClientView,
    CACertDownloadView,
    ClientViewSet,
)

router = DefaultRouter()
router.register(r"client/self", ClientViewSet, basename="client-self")

urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),

    # i18n language switching
    path("i18n/setlang/", set_language, name="set_language"),

    # Standard Ophix API — available on every server
    path("api/register/", RegisterClientView.as_view(), name="client-register"),
    path("api/server/ca-cert/", CACertDownloadView.as_view(), name="ca-cert-download"),
    path("api/", include(router.urls)),
]

# OIDC authentication URLs (mozilla-django-oidc)
# Included only when SSO is active (OIDC_RP_CLIENT_ID is set and the package
# is installed).  Provides /oidc/authenticate/, /oidc/callback/, /oidc/logout/.
if getattr(settings, "OIDC_ENABLED", False):
    try:
        import mozilla_django_oidc  # noqa: F401
        urlpatterns += [path("oidc/", include("mozilla_django_oidc.urls"))]
    except ImportError:
        pass

# Serve media files in development.
# In production this is handled by the web server (nginx/apache).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
