"""
ophix.core.serializers
~~~~~~~~~~~~~~~~~~~~~~
Serializers for the standard Ophix base API (client self-management).
Domain plugins define their own serializers for artifact types.
"""

from rest_framework import serializers
from .models import Client


class ClientSerializer(serializers.ModelSerializer):
    """
    Read/update serializer for the authenticated client's own record.

    Excludes token_hash (managed via rotate-token endpoint) and
    host (immutable after registration).
    """

    class Meta:
        model = Client
        fields = [
            "name",
            "deployment_ref",
            "venv_name",
            "venv_path",
            "last_token_rotation",
        ]
        read_only_fields = ["name", "last_token_rotation"]
