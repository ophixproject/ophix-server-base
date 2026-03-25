"""
ophix.core.admin
~~~~~~~~~~~~~~~~
Admin registrations for Host and Client.

Domain plugins register their own artifact models and join tables
in their own admin.py.
"""

from django.contrib import admin
from django.conf import settings

from .models import Host, Client


@admin.register(Host)
class HostAdmin(admin.ModelAdmin):
    list_display = ("name", "ipv4_address", "enabled", "description")
    list_filter = ("enabled",)
    search_fields = ("name", "ipv4_address")
    ordering = ("name",)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "host",
        "deployment_ref",
        "venv_name",
        "enabled",
        "last_token_rotation",
    )
    list_filter = ("enabled", "host")
    search_fields = ("name", "deployment_ref", "host__name")
    ordering = ("name",)
    readonly_fields = ("api_token", "last_token_rotation")

    def get_fieldsets(self, request, obj=None):
        return [
            (None, {
                "fields": ("host", "name", "enabled"),
            }),
            ("Deployment", {
                "fields": ("deployment_ref", "venv_name", "venv_path"),
            }),
            ("Token", {
                "fields": ("api_token", "last_token_rotation"),
                "classes": ("collapse",),
            }),
        ]
