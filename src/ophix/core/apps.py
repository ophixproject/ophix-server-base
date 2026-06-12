from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class OphixCoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ophix.core"
    label = "ophix_core"
    verbose_name = _("Server Core")
    admin_order = 100

    def ready(self):
        _patch_admin_ordering()
        _suppress_view_site_link()


def _suppress_view_site_link():
    """Remove the 'View site' link from the admin header.

    The admin is the site — there is no separate front-end to link to.
    Setting site_url to '' makes {% if site_url %} false in Django's own
    userlinks template block, so the link is never rendered.
    """
    from django.contrib import admin
    admin.site.site_url = ""


def _patch_admin_ordering():
    """Patch AdminSite.get_app_list to sort sections and models by numeric order.

    Sections declare order via AppConfig.admin_order (default 999).
    Models declare order via ModelAdmin.menu_order (default 999).
    Numeric ties fall back to alphabetical. Language-independent.
    """
    from django.contrib.admin import AdminSite
    from django.apps import apps as django_apps

    if getattr(AdminSite, '_ophix_ordering_applied', False):
        return

    _original = AdminSite.get_app_list

    def get_app_list(self, request, app_label=None):
        app_list = _original(self, request, app_label)
        for app in app_list:
            try:
                cfg = django_apps.get_app_config(app['app_label'])
                app_order = getattr(cfg, 'admin_order', 999)
            except LookupError:
                app_order = 999
            for model_dict in app['models']:
                model_admin = self._registry.get(model_dict['model'])
                model_dict['_menu_order'] = getattr(model_admin, 'menu_order', 999)
            app['models'].sort(key=lambda m: (m['_menu_order'], m['name']))
            app['_admin_order'] = app_order
        app_list.sort(key=lambda a: (a['_admin_order'], a['name']))
        return app_list

    AdminSite.get_app_list = get_app_list
    AdminSite._ophix_ordering_applied = True
