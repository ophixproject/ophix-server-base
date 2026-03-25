"""
ophix.core.auth
~~~~~~~~~~~~~~~
DRF authentication class for all Ophix API endpoints.

ClientTokenAuthentication validates two conditions on every request:
  1. The bearer token matches a known, enabled Client.
  2. The request originates from the IP address of that Client's Host.

Both conditions must be true. Failure of either returns 403, with the
error detail controlled by the AUTH_LEAK_INFO setting.

The authenticated Client is returned as request.user so views can
refer to it directly.
"""

import logging

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions

from .models import Client

logger = logging.getLogger(__name__)

_KEYWORD = "Token"


class ClientTokenAuthentication(BaseAuthentication):
    """
    Token + IP authentication for Ophix clients.

    Checks, in order:
      - Authorization header present and well-formed
      - Token matches a Client record
      - Client is enabled
      - Client's Host is enabled
      - Request IP matches Client's Host IP
    """

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith(f"{_KEYWORD} "):
            return None  # No auth attempted — let DRF handle as anonymous.

        token = auth_header[len(f"{_KEYWORD} "):].strip()

        try:
            client = Client.objects.select_related("host").get(api_token=token)
        except Client.DoesNotExist:
            logger.info("Authentication failed: unrecognised token")
            raise exceptions.AuthenticationFailed(self._msg("Invalid token"))

        # Client enabled check
        if not client.enabled:
            logger.info("Access blocked: client %s is disabled", client)
            raise exceptions.AuthenticationFailed(self._msg("Client disabled"))

        # Host enabled check
        if not client.host.enabled:
            logger.info("Access blocked: host %s is disabled", client.host)
            raise exceptions.AuthenticationFailed(self._msg("Host disabled"))

        # IP validation
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        remote_ip = (
            x_forwarded_for.split(",")[0].strip()
            if x_forwarded_for
            else request.META.get("REMOTE_ADDR")
        )

        if remote_ip != client.host.ipv4_address:
            logger.info(
                "Access blocked for client %s: IP mismatch (expected %s, got %s)",
                client,
                client.host.ipv4_address,
                remote_ip,
            )
            raise exceptions.AuthenticationFailed(self._msg("Access blocked"))

        return (client, None)

    @staticmethod
    def _msg(detail: str) -> str:
        """Return detail string or a generic message depending on AUTH_LEAK_INFO."""
        if getattr(settings, "AUTH_LEAK_INFO", False):
            return detail
        return "Access blocked"
