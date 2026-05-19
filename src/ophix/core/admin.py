from django.contrib import admin
from django.conf import settings
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from importlib import import_module
from .models import Host, Client, AccessLog, PackageUpdateRecord
from django.utils.translation import gettext_lazy as _


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
hide_models("admin_interface", ["Theme", "ThemeColor"], getattr(settings, "SHOW_THEME_MODEL", False))

# Hide Django auth models if toggle is off
hide_models("django.contrib.auth", ["User", "Group"], getattr(settings, "SHOW_AUTH_MODELS", False))


# ============================================================
# HostAdmin
# ============================================================

@admin.register(Host)
class HostAdmin(admin.ModelAdmin):
    list_display = (
        'name',          # identity
        'ipv4_address',  # context
        'enabled',       # state (consistent position)
        'description',   # human context
    )
    list_editable = ('enabled',)
    search_fields = ('name', 'ipv4_address', 'description')
    list_filter = ('enabled',)
    actions = None

    _registered_inlines = []
    _registered_columns = []

    @classmethod
    def register_inline(cls, inline_class):
        cls._registered_inlines.append(inline_class)

    @classmethod
    def register_column(cls, fn):
        """Register a list_display column contributed by a domain plugin.
        fn must be a callable taking (self, obj) — it is attached as a method."""
        setattr(cls, fn.__name__, fn)
        cls._registered_columns.append(fn.__name__)

    def get_inlines(self, request, obj=None):
        return self._registered_inlines

    def get_list_display(self, request):
        return list(self.list_display) + self._registered_columns


# ============================================================
# ClientAdmin
# ============================================================

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'host',
        'venv_name',
        'enabled',
        'deployment_ref',
        'last_token_rotation',
    )
    list_editable = ('enabled',)
    list_filter = ('enabled', 'host')
    search_fields = ('name', 'deployment_ref', 'host__name')
    ordering = ('name',)
    readonly_fields = ('api_token', 'venv_name', 'venv_path', 'last_token_rotation')
    actions = None

    _registered_inlines = []
    _registered_columns = []

    @classmethod
    def register_inline(cls, inline_class):
        cls._registered_inlines.append(inline_class)

    @classmethod
    def register_column(cls, fn):
        """Register a list_display column contributed by a domain plugin.
        fn must be a callable taking (self, obj) — it is attached as a method."""
        setattr(cls, fn.__name__, fn)
        cls._registered_columns.append(fn.__name__)

    def get_inlines(self, request, obj=None):
        return self._registered_inlines

    def get_list_display(self, request):
        return list(self.list_display) + self._registered_columns

    def get_fieldsets(self, request, obj=None):
        return [
            (None, {"fields": ("host", "name", "enabled")}),
            (_("Deployment"), {"fields": ("deployment_ref", "venv_name", "venv_path")}),
            (_("Token"), {"fields": ("api_token", "last_token_rotation"), "classes": ("collapse",)}),
        ]


# ============================================================
# AccessLogAdmin
# ============================================================

@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "client",
        "host",
        "operation",
        "artifact_type",
        "artifact_name",
        "artifact_id",
    )
    list_filter = (
        "operation",
        "artifact_type",
        "client",
        "host",
        ("timestamp", admin.DateFieldListFilter),
    )
    search_fields = ("artifact_name", "client__name", "host__name")
    ordering = ("-timestamp",)
    date_hierarchy = "timestamp"

    # Read-only: no add, change, or delete
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# Hide Access Logs unless SHOW_ACCESS_LOGS=True.
# Must come after AccessLogAdmin is registered above.
hide_models("ophix.core", ["AccessLog"], getattr(settings, "SHOW_ACCESS_LOGS", False))


# ============================================================
# PackageUpdateRecordAdmin
# ============================================================

@admin.register(PackageUpdateRecord)
class PackageUpdateRecordAdmin(admin.ModelAdmin):
    list_display = (
        "package_name",
        "installed_version",
        "latest_version",
        "up_to_date",
        "last_checked_at",
        "first_recorded_at",
    )
    list_filter = ("update_available",)
    search_fields = ("package_name",)
    ordering = ("package_name",)
    readonly_fields = (
        "package_name",
        "installed_version",
        "latest_version",
        "up_to_date",
        "first_recorded_at",
        "last_checked_at",
        "notice_rendered",
    )
    fieldsets = (
        (None, {"fields": (
            "package_name",
            "installed_version",
            "latest_version",
            "up_to_date",
            "first_recorded_at",
            "last_checked_at",
        )}),
        (_("Release Notes"), {"fields": ("notice_rendered",)}),
    )

    @admin.display(description=_("Release Notes"))
    def notice_rendered(self, obj):
        if not obj.notice:
            return "—"
        import markdown
        html = markdown.markdown(obj.notice, extensions=["fenced_code"])
        return mark_safe(f'<div class="ophix-release-notes">{html}</div>')

    @admin.display(description=_("Up To Date"))
    def up_to_date(self, obj):
        if not obj.update_available:
            return mark_safe(
                '<span style="color:var(--admin-interface-generic-link-hover-color);'
                'font-size:1.2em">✓</span>'
            )
        return format_html(
            '<span style="color:var(--admin-interface-warning-color,#E67E22);'
            'font-weight:bold">⬆ {}</span>',
            _("Update available"),
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# Hide Plugin Versions unless SHOW_PLUGIN_VERSION_MODEL=True.
hide_models("ophix.core", ["PackageUpdateRecord"], getattr(settings, "SHOW_PLUGIN_VERSION_MODEL", False))