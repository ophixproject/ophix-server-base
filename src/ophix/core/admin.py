from django.contrib import admin
from django.conf import settings
from django.contrib.auth.models import User, Group
from admin_interface.models import Theme
from admin_interface.admin import ThemeAdmin
from .models import Host, Client


# --- Auth models ---
if not getattr(settings, "SHOW_AUTH_MODELS", False):
    try:
        admin.site.unregister(User)
        admin.site.unregister(Group)
    except admin.sites.NotRegistered:
        pass


# --- Theme ---
# Always unregister the default registration from admin_interface
# and re-register under our control so ADMIN_THEME_EDITABLE is honoured.
# admin_interface is a fixed base dependency so it will always have
# registered Theme before ophix.core loads.
try:
    admin.site.unregister(Theme)
except admin.sites.NotRegistered:
    pass

if getattr(settings, "ADMIN_THEME_EDITABLE", False):
    admin.site.register(Theme, ThemeAdmin)
else:
    class ReadOnlyThemeAdmin(ThemeAdmin):
        def has_add_permission(self, request):
            return False
        def has_change_permission(self, request, obj=None):
            return False
        def has_delete_permission(self, request, obj=None):
            return False

    admin.site.register(Theme, ReadOnlyThemeAdmin)


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