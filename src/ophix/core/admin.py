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
    menu_order = 100
    list_display = ('name', 'ipv4_address', 'enabled', 'description')
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
        cols = ['name', 'ipv4_address']
        if getattr(settings, 'SHOW_IPV6_ADDRESS', True):
            cols.append('ipv6_address')
        cols += ['enabled', 'description']
        return cols + self._registered_columns

    def get_search_fields(self, request):
        fields = ['name', 'ipv4_address', 'description']
        if getattr(settings, 'SHOW_IPV6_ADDRESS', True):
            fields.append('ipv6_address')
        return fields

    def get_fields(self, request, obj=None):
        fields = ['name', 'ipv4_address']
        if getattr(settings, 'SHOW_IPV6_ADDRESS', True):
            fields.append('ipv6_address')
        fields += ['description', 'enabled']
        return fields


# ============================================================
# ClientAdmin
# ============================================================

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    menu_order = 200
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
    menu_order = 500
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
    menu_order = 600
    list_display = (
        "package_name",
        "category_display",
        "installed_version",
        "latest_version",
        "up_to_date",
        "last_checked_at",
        "first_recorded_at",
    )
    list_filter = ("category", "update_available",)
    search_fields = ("package_name",)
    ordering = ("sort_order", "package_name")
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
            "notice_rendered",
        )}),
    )

    @admin.display(description=_("Category"), ordering="sort_order")
    def category_display(self, obj):
        return obj.get_category_display() if obj.category else "—"

    @admin.display(description=_("Release Notes"))
    def notice_rendered(self, obj):
        if not obj.notice:
            return "—"

        import markdown as _markdown

        def _markdown_fallback(text):
            html = _markdown.markdown(text, extensions=["fenced_code"])
            return mark_safe(f'<div class="ophix-release-notes">{html}</div>')

        try:
            import re
            from django.utils.html import escape

            lines = obj.notice.splitlines()
            sections = []
            current_section = None
            current_category = None

            for line in lines:
                stripped = line.strip()
                if stripped.startswith('## '):
                    heading = stripped[3:].strip()
                    current_section = {'heading': heading, 'items': []}
                    current_category = None
                    sections.append(current_section)
                elif stripped.startswith('### ') and current_section is not None:
                    current_category = stripped[4:].strip()
                elif (stripped.startswith('- ') or stripped.startswith('* ')) and current_section is not None:
                    current_section['items'].append({
                        'text': stripped[2:].strip(),
                        'category': current_category,
                    })

            if not sections:
                return _markdown_fallback(obj.notice)

            def render_inline(text):
                text = escape(text)
                text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
                text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
                return text

            ver_count = len(sections)
            ver_label = f'{ver_count} version{"s" if ver_count != 1 else ""}'

            parts = [
                f'<div class="ophix-release-notes">'
                f'<div class="rn-outer-header" role="button">'
                f'<button class="rn-toggle" type="button">▼</button>'
                f'<span class="rn-outer-title">Release Notes</span>'
                f'<span class="rn-count">{ver_label}</span>'
                f'</div>'
                f'<div class="rn-outer-body">'
            ]

            for i, section in enumerate(sections):
                heading = section['heading']
                display = 'v' + heading if re.match(r'^\d{4}', heading) else heading
                toggle = '▼' if i == 0 else '▶'
                hidden = '' if i == 0 else ' style="display:none"'
                item_count = len(section['items'])
                item_label = f'{item_count} change{"s" if item_count != 1 else ""}'

                items_html = []
                last_cat = None
                for item in section['items']:
                    cat = item['category']
                    if cat and cat != last_cat:
                        items_html.append(f'<span class="rn-category">{escape(cat)}</span>')
                        last_cat = cat
                    items_html.append(f'<span class="rn-item">{render_inline(item["text"])}</span>')

                parts.append(
                    f'<div class="rn-version-row">'
                    f'<div class="rn-version-header" role="button">'
                    f'<div class="rn-version-left">'
                    f'<button class="rn-toggle" type="button">{toggle}</button>'
                    f'<span class="rn-version-name">{escape(display)}</span>'
                    f'</div>'
                    f'<span class="rn-count">{item_label}</span>'
                    f'</div>'
                    f'<div class="rn-version-items"{hidden}>{"".join(items_html)}</div>'
                    f'</div>'
                )

            parts.append('</div></div>')
            parts.append(
                '<script>(function(){'
                # Outer collapse
                'var outerHdr=document.querySelector(".rn-outer-header");'
                'if(outerHdr){'
                'outerHdr.addEventListener("click",function(){'
                'var btn=outerHdr.querySelector(".rn-toggle");'
                'var body=outerHdr.nextElementSibling;'
                'var open=body.style.display!=="none";'
                'body.style.display=open?"none":"";'
                'btn.textContent=open?"▶":"▼";'
                '});}'
                # Version collapses
                'document.querySelectorAll(".rn-version-header").forEach(function(hdr){'
                'hdr.addEventListener("click",function(){'
                'var btn=hdr.querySelector(".rn-toggle");'
                'var body=hdr.nextElementSibling;'
                'var open=body.style.display!=="none";'
                'body.style.display=open?"none":"";'
                'btn.textContent=open?"▶":"▼";'
                '});});})();</script>'
            )

            return mark_safe(''.join(parts))

        except Exception:
            return _markdown_fallback(obj.notice)

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