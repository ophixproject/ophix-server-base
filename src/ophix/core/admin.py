from django.contrib import admin
from django.conf import settings
from django.contrib.auth.models import User, Group
from admin_interface.models import Theme
from admin_interface.admin import ThemeAdmin
from importlib import import_module
from .models import Host, Client


def hide_models(app_label, model_names, toggle: bool):
    """
    Hides models from Django admin unless toggle is True.
    - app_label: Django app label (e.g., 'admin_interface', 'auth')
    - model_names: list of model class names as strings
    - toggle: if True, models remain visible; if False, models are hidden
    """
    if toggle:
        return  # leave models visible

    try:
        app_models = import_module(f"{app_label}.models")
    except ModuleNotFoundError:
        return

    for name in model_names:
        try:
            model = getattr(app_models, name)
            admin.site.unregister(model)
        except (AttributeError, admin.sites.NotRegistered):
            pass

# Hide Theme models if toggle is off 
hide_models("admin_interface", ["Theme", "ThemeColor"], getattr(settings, "ADMIN_THEME_EDITABLE", False))

# Hide Django auth models if toggle is off
hide_models("django.contrib.auth", ["User", "Group"], getattr(settings, "SHOW_AUTH_MODELS", False))


# --- Auth models ---
#if not getattr(settings, "SHOW_AUTH_MODELS", False):
#    try:
#        admin.site.unregister(User)
#        admin.site.unregister(Group)
#    except admin.sites.NotRegistered:
#        pass


# --- Theme ---
# Always unregister the default registration from admin_interface
# and re-register under our control so ADMIN_THEME_EDITABLE is honoured.
# admin_interface is a fixed base dependency so it will always have
# registered Theme before ophix.core loads.
#try:
#    admin.site.unregister(Theme)
#except admin.sites.NotRegistered:
#    pass

#if getattr(settings, "ADMIN_THEME_EDITABLE", False):
#    admin.site.register(Theme, ThemeAdmin)
#else:
#    class ReadOnlyThemeAdmin(ThemeAdmin):
#        def has_add_permission(self, request):
#            return False
#        def has_change_permission(self, request, obj=None):
#            return False
#        def has_delete_permission(self, request, obj=None):
#            return False

#    admin.site.register(Theme, ReadOnlyThemeAdmin)


# --- Host ---
@admin.register(Host)
class HostAdmin(admin.ModelAdmin):
    list_display = ("name", "ipv4_address", "enabled", "description")
    list_filter = ("enabled",)
    search_fields = ("name", "ipv4_address")
    ordering = ("name",)


# --- Client ---
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "name", "host", "deployment_ref",
        "venv_name", "enabled", "last_token_rotation",
    )
    list_filter = ("enabled", "host")
    search_fields = ("name", "deployment_ref", "host__name")
    ordering = ("name",)
    readonly_fields = ("api_token", "last_token_rotation")

    def get_fieldsets(self, request, obj=None):
        return [
            (None, {"fields": ("host", "name", "enabled")}),
            ("Deployment", {"fields": ("deployment_ref", "venv_name", "venv_path")}),
            ("Token", {"fields": ("api_token", "last_token_rotation"), "classes": ("collapse",)}),
        ]