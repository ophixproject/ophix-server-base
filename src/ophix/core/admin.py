from django.contrib import admin, messages
from django.conf import settings
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from importlib import import_module
from .models import Host, Client, AccessLog, PackageUpdateRecord
from django.utils.translation import gettext_lazy as _


class DeleteRedirectToChangelistMixin:
    """
    After a successful delete, redirect to the model's changelist rather than
    admin:index. Django's default falls back to admin:index when
    has_change_permission is False — which hits the custom home page.
    Preserved filters (active sort/filter state) are maintained.
    """
    def response_delete(self, request, obj_display, obj_id):
        opts = self.model._meta
        changelist_url = reverse(
            f"admin:{opts.app_label}_{opts.model_name}_changelist",
            current_app=self.admin_site.name,
        )
        post_url = add_preserved_filters(
            {"preserved_filters": self.get_preserved_filters(request), "opts": opts},
            changelist_url,
        )
        return HttpResponseRedirect(post_url)


class CleanSaveMessageMixin:
    """
    Replaces Django's default linked-object messages with plain text equivalents.
    Covers both response_add and response_change.
    """
    def _clean_msg(self, verb):
        return _("%(verbose_name)s %(verb)s successfully.") % {
            "verbose_name": self.model._meta.verbose_name.capitalize(),
            "verb": verb,
        }

    def response_add(self, request, obj, post_url_continue=None):
        if "_popup" in request.POST:
            return super().response_add(request, obj, post_url_continue)
        self.message_user(request, self._clean_msg("added"), messages.SUCCESS)
        opts = self.model._meta
        if "_continue" in request.POST:
            return HttpResponseRedirect(
                reverse(
                    f"admin:{opts.app_label}_{opts.model_name}_change",
                    args=[obj.pk],
                    current_app=self.admin_site.name,
                )
            )
        if "_addanother" in request.POST:
            return HttpResponseRedirect(
                reverse(
                    f"admin:{opts.app_label}_{opts.model_name}_add",
                    current_app=self.admin_site.name,
                )
            )
        return HttpResponseRedirect(
            reverse(
                f"admin:{opts.app_label}_{opts.model_name}_changelist",
                current_app=self.admin_site.name,
            )
        )

    def response_change(self, request, obj):
        if "_popup" in request.POST:
            return super().response_change(request, obj)
        self.message_user(request, self._clean_msg("saved"), messages.SUCCESS)
        if "_continue" in request.POST:
            return HttpResponseRedirect(request.path)
        if "_save" in request.POST:
            return HttpResponseRedirect(
                reverse(
                    f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist",
                    current_app=self.admin_site.name,
                )
            )
        return super().response_change(request, obj)


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
class HostAdmin(CleanSaveMessageMixin, admin.ModelAdmin):
    menu_order = 100
    list_display = ('name', 'ipv4_address', 'enabled', 'description')
    list_editable = ('enabled',)
    search_fields = ('name', 'ipv4_address', 'description')
    list_filter = ('enabled',)
    actions = None

    _registered_inlines = []
    _registered_meta_columns = []
    _registered_columns = []

    @classmethod
    def register_inline(cls, inline_class):
        cls._registered_inlines.append(inline_class)

    @classmethod
    def register_column(cls, fn, before_domain=False):
        """Register a list_display column contributed by a plugin.
        before_domain=True places it before domain artifact columns (e.g. token status)."""
        setattr(cls, fn.__name__, fn)
        if before_domain:
            cls._registered_meta_columns.append(fn.__name__)
        else:
            cls._registered_columns.append(fn.__name__)

    def get_inlines(self, request, obj=None):
        return self._registered_inlines

    def get_list_display(self, request):
        cols = ['name', 'ipv4_address']
        if getattr(settings, 'SHOW_IPV6_ADDRESS', True):
            cols.append('ipv6_address')
        cols += ['enabled', 'description']
        return cols + self._registered_meta_columns + self._registered_columns

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
class ClientAdmin(CleanSaveMessageMixin, admin.ModelAdmin):
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
    readonly_fields = ('venv_name', 'venv_path', 'last_token_rotation')
    actions = None

    _registered_inlines = []
    _registered_meta_columns = []
    _registered_columns = []

    @classmethod
    def register_inline(cls, inline_class):
        cls._registered_inlines.append(inline_class)

    @classmethod
    def register_column(cls, fn, before_domain=False):
        """Register a list_display column contributed by a plugin.
        before_domain=True places it before domain artifact columns (e.g. token status)."""
        setattr(cls, fn.__name__, fn)
        if before_domain:
            cls._registered_meta_columns.append(fn.__name__)
        else:
            cls._registered_columns.append(fn.__name__)

    def get_inlines(self, request, obj=None):
        return self._registered_inlines

    def get_list_display(self, request):
        return list(self.list_display) + self._registered_meta_columns + self._registered_columns

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return [
                (None, {"fields": ("host", "name", "enabled")}),
                (_("Deployment"), {"fields": ("deployment_ref",)}),
            ]
        return [
            (None, {"fields": ("host", "name", "enabled")}),
            (_("Deployment"), {"fields": ("deployment_ref", "venv_name", "venv_path")}),
            (_("Token"), {"fields": ("api_token_display", "last_token_rotation"), "classes": ("collapse",)}),
        ]

    def get_readonly_fields(self, request, obj=None):
        base = list(self.readonly_fields)
        if obj is not None:
            base.append("api_token_display")
        return base

    def api_token_display(self, obj):
        url = reverse(
            "admin:ophix_core_client_change_token",
            args=[obj.pk],
            current_app=self.admin_site.name,
        )
        return format_html(
            '<span style="font-family:monospace;color:var(--body-quiet-color)">'
            "Token hash (SHA-256) &nbsp;••••••••••••••••••••••••••••••••"
            "</span>"
            "&emsp;"
            '<a href="{}?_popup=1" id="change-token-link-{}" class="ophix-token-action-link" role="button">{}</a>',
            url, obj.pk,
            _("Issue a replacement token"),
        )
    api_token_display.short_description = _("API token")

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path(
                "<path:object_id>/change-token/",
                self.admin_site.admin_view(self.change_token_view),
                name="ophix_core_client_change_token",
            ),
        ]
        return custom + urls

    def change_token_view(self, request, object_id):
        from django.shortcuts import render, get_object_or_404
        from django.core.exceptions import PermissionDenied
        obj = get_object_or_404(Client, pk=object_id)
        if not self.has_change_permission(request, obj):
            raise PermissionDenied
        is_popup = "_popup" in request.GET or "_popup" in request.POST
        change_url = reverse(
            "admin:ophix_core_client_change",
            args=[object_id],
            current_app=self.admin_site.name,
        )
        if request.method == "POST":
            from django.utils import timezone
            from .models import generate_api_token, hash_token
            raw_token = generate_api_token()
            obj.api_token = hash_token(raw_token)
            obj.last_token_rotation = timezone.now()
            obj.save(update_fields=["api_token", "last_token_rotation"])
            return render(request, "admin/ophix_core/client/token_created.html", {
                "client": obj,
                "token": raw_token,
                "change_url": change_url,
                "parent_redirect_url": change_url,
                "is_replacement": True,
                "is_popup": is_popup,
                "title": _("Replacement token issued"),
                "opts": obj._meta,
                "has_view_permission": self.has_view_permission(request, obj),
            })
        return render(request, "admin/ophix_core/client/change_token_confirm.html", {
            "client": obj,
            "change_url": change_url,
            "is_popup": is_popup,
            "title": _("Issue replacement token"),
            "opts": obj._meta,
        })

    def add_view(self, request, form_url="", extra_context=None):
        from .models import generate_api_token
        extra_context = extra_context or {}
        if request.method == "GET":
            raw_token = generate_api_token()
            request.session["_ophix_pending_token"] = raw_token
            extra_context["pending_token"] = raw_token
        else:
            raw_token = request.session.get("_ophix_pending_token")
            if raw_token:
                extra_context["pending_token"] = raw_token
        return super().add_view(request, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        if not change:
            from django.utils import timezone
            from .models import generate_api_token, hash_token
            raw_token = request.session.pop("_ophix_pending_token", None) or generate_api_token()
            obj.api_token = hash_token(raw_token)
            obj.last_token_rotation = timezone.now()
        super().save_model(request, obj, form, change)


# ============================================================
# AccessLogAdmin
# ============================================================

@admin.register(AccessLog)
class AccessLogAdmin(DeleteRedirectToChangelistMixin, admin.ModelAdmin):
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
    change_list_template = "admin/ophix_core/packageupdaterecord/change_list.html"
    list_display = (
        "package_name",
        "category",
        "installed_col",
        "latest_col",
        "up_to_date",
        "last_checked_at",
        "first_recorded_at",
    )
    list_filter = ("category", "update_available",)
    search_fields = ("package_name",)
    ordering = ("sort_order", "package_name")
    readonly_fields = (
        "package_name",
        "category",
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
            "category",
            "installed_version",
            "latest_version",
            "up_to_date",
            "first_recorded_at",
            "last_checked_at",
            "notice_rendered",
        )}),
    )

    @admin.display(description=_("Installed"))
    def installed_col(self, obj):
        return obj.installed_version

    @admin.display(description=_("Latest"))
    def latest_col(self, obj):
        if obj.latest_version == obj.installed_version:
            return "—"
        return obj.latest_version

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

            pkg_key = escape(obj.package_name)
            parts = [
                f'<div class="ophix-release-notes" data-pkg="{pkg_key}">'
                f'<div class="rn-outer-header" role="button">'
                f'<button class="rn-toggle" type="button">▶</button>'
                f'<span class="rn-outer-title">Release Notes</span>'
                f'<span class="rn-count">{ver_label}</span>'
                f'</div>'
                f'<div class="rn-outer-body" style="display:none">'
            ]

            for section in sections:
                heading = section['heading']
                display = 'v' + heading if re.match(r'^\d{4}', heading) else heading
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
                    f'<div class="rn-version-row" data-ver="{escape(heading)}">'
                    f'<div class="rn-version-header" role="button">'
                    f'<div class="rn-version-left">'
                    f'<button class="rn-toggle" type="button">▶</button>'
                    f'<span class="rn-version-name">{escape(display)}</span>'
                    f'</div>'
                    f'<span class="rn-count">{item_label}</span>'
                    f'</div>'
                    f'<div class="rn-version-items" style="display:none">{"".join(items_html)}</div>'
                    f'</div>'
                )

            parts.append('</div></div>')
            parts.append(
                '<script>(function(){'
                'var el=document.querySelector(".ophix-release-notes[data-pkg]");'
                'if(!el)return;'
                'var sk="ophix_rn_"+el.dataset.pkg;'
                'function load(){try{return JSON.parse(localStorage.getItem(sk)||"{}")}catch(e){return{}}}'
                'function save(s){try{localStorage.setItem(sk,JSON.stringify(s))}catch(e){}}'
                'var state=load();'
                # Restore outer state
                'var outerBody=el.querySelector(".rn-outer-body");'
                'var outerBtn=el.querySelector(".rn-outer-header .rn-toggle");'
                'if(state.outer){outerBody.style.display="";outerBtn.textContent="▼";}'
                # Restore version states
                'el.querySelectorAll(".rn-version-row").forEach(function(row){'
                'var ver=row.dataset.ver;'
                'var body=row.querySelector(".rn-version-items");'
                'var btn=row.querySelector(".rn-toggle");'
                'if(state[ver]){body.style.display="";btn.textContent="▼";}});'
                # Outer toggle
                'el.querySelector(".rn-outer-header").addEventListener("click",function(){'
                'var s=load();'
                'var isOpen=outerBody.style.display!=="none";'
                'outerBody.style.display=isOpen?"none":"";'
                'outerBtn.textContent=isOpen?"▶":"▼";'
                's.outer=!isOpen;save(s);});'
                # Version toggles
                'el.querySelectorAll(".rn-version-header").forEach(function(hdr){'
                'hdr.addEventListener("click",function(){'
                'var row=hdr.parentElement;'
                'var ver=row.dataset.ver;'
                'var body=hdr.nextElementSibling;'
                'var btn=hdr.querySelector(".rn-toggle");'
                'var s=load();'
                'var isOpen=body.style.display!=="none";'
                'body.style.display=isOpen?"none":"";'
                'btn.textContent=isOpen?"▶":"▼";'
                's[ver]=!isOpen;save(s);});});'
                '})();</script>'
            )

            return mark_safe(''.join(parts))

        except Exception:
            return _markdown_fallback(obj.notice)

    @admin.display(description=_("Status"))
    def up_to_date(self, obj):
        if not obj.update_available:
            return mark_safe(
                '<span style="color:var(--admin-interface-success-color,#28A745);'
                'font-size:1.2em;font-weight:600">✓</span>'
            )
        return mark_safe(
            '<span style="color:var(--admin-interface-warning-color,#E67E22);'
            'font-size:1.2em;font-weight:600">✗</span>'
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# Hide Plugin Versions unless SHOW_PLUGIN_VERSION_MODEL=True.
hide_models("ophix.core", ["PackageUpdateRecord"], getattr(settings, "SHOW_PLUGIN_VERSION_MODEL", False))