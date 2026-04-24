from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class OphixCoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ophix.core"
    label = "ophix_core"
    verbose_name = _("Clients & Hosts")
