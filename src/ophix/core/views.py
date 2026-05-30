"""
ophix.core.views
~~~~~~~~~~~~~~~~
Standard API views present on every Ophix Project Server.

CACertDownloadView      Unauthenticated — serves the internal CA cert.
RegisterClientView      Unauthenticated — registers a new client for a known host.
ClientViewSet           Authenticated  — client self-inspection, update, token rotation.
"""

import os
import ssl
import logging

from django.conf import settings
from django.db import IntegrityError
from django.http import FileResponse, Http404
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ClientTokenAuthentication
from .models import Client, Host, generate_api_token
from .serializers import ClientSerializer
from .utils import get_client_ip, err_response

logger = logging.getLogger(__name__)

MINIMUM_TOKEN_ROTATE_TIME = lambda: getattr(settings, "MINIMUM_TOKEN_ROTATE_TIME", 3600)  # noqa: E731


def _log_client_headers(request) -> None:
    """Log any X-Ophix-* diagnostic headers sent by the client."""
    headers = {
        k: v for k, v in request.headers.items() if k.startswith("X-Ophix-")
    }
    if headers:
        logger.info("client_context: %s", headers)


# ---------------------------------------------------------------------------
# CA Certificate download
# ---------------------------------------------------------------------------

class CACertDownloadView(APIView):
    """
    Serve the internal CA certificate as a downloadable PEM file.

    Unauthenticated — clients need this to bootstrap TLS verification
    before they have a token.
    """

    authentication_classes = []

    def get(self, request):
        _log_client_headers(request)

        ca_cert_path = os.getenv("CA_CERT_FILE")
        if not ca_cert_path or not os.path.isfile(ca_cert_path):
            raise Http404("CA certificate not found")

        # Derive a sensible filename from the cert's CN.
        try:
            cert = ssl._ssl._test_decode_cert(ca_cert_path)
            cn = next(
                (v for item in cert.get("subject", []) for k, v in item if k == "commonName"),
                None,
            )
            filename = f"{cn}.pem" if cn else os.path.basename(ca_cert_path)
        except Exception:
            filename = os.path.basename(ca_cert_path)

        response = FileResponse(
            open(ca_cert_path, "rb"),
            content_type="application/x-pem-file",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


# ---------------------------------------------------------------------------
# Client registration
# ---------------------------------------------------------------------------

class RegisterClientView(APIView):
    """
    Register a new Client for the requesting Host.

    The Host must already exist in the database (created by an admin).
    Registration is identified by the requesting IP address.

    Required JSON fields: name, deployment_ref, venv_name, venv_path
    """

    authentication_classes = []

    def post(self, request):
        _log_client_headers(request)

        payload = request.data or {}
        client_name = payload.get("name")
        deployment_ref = payload.get("deployment_ref")
        venv_name = payload.get("venv_name")
        venv_path = payload.get("venv_path")

        missing = [
            f for f, v in [
                ("name", client_name),
                ("deployment_ref", deployment_ref),
                ("venv_name", venv_name),
                ("venv_path", venv_path),
            ] if not v
        ]
        if missing:
            return Response(
                {"error": f"Missing required field(s): {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        remote_ip = get_client_ip(request)

        try:
            host = Host.objects.get(ipv4_address=remote_ip)
        except Host.DoesNotExist:
            logger.info("Registration blocked: no host for IP %s", remote_ip)
            return Response(
                {"error": "Unknown host"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not host.enabled:
            return Response(
                {"error": err_response("Host disabled")},
                status=status.HTTP_403_FORBIDDEN,
            )

        if Client.objects.filter(host=host, name=client_name).exists():
            return Response(
                {"error": err_response(f"Client '{client_name}' already registered for this host.")},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            client = Client.objects.create(
                host=host,
                name=client_name,
                deployment_ref=deployment_ref,
                venv_name=venv_name,
                venv_path=venv_path,
                api_token=generate_api_token(),
            )
        except IntegrityError:
            return Response(
                {"error": "Registration failed due to a database constraint violation."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "host": host.name,
                "name": client.name,
                "deployment_ref": client.deployment_ref,
                "venv_name": client.venv_name,
                "venv_path": client.venv_path,
                "api_token": client.api_token,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Client self-management
# ---------------------------------------------------------------------------

class ClientViewSet(viewsets.ViewSet):
    """
    Client self-inspection and management.

    GET  /api/client/self/              — return own record
    PATCH /api/client/self/update/      — update venv_name, venv_path, deployment_ref
    POST /api/client/self/rotate-token/ — rotate API token
    """

    authentication_classes = [ClientTokenAuthentication]

    def _client(self, request) -> Client:
        return request.user

    # GET /api/client/self/
    def list(self, request):
        _log_client_headers(request)
        serializer = ClientSerializer(self._client(request))
        return Response(serializer.data)

    # PATCH /api/client/self/update/
    @action(detail=False, methods=["patch"], url_path="update")
    def update_self(self, request):
        _log_client_headers(request)
        client = self._client(request)
        serializer = ClientSerializer(client, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    # POST /api/client/self/rotate-token/
    @action(detail=False, methods=["post"], url_path="rotate-token")
    def rotate_token(self, request):
        _log_client_headers(request)

        client = self._client(request)
        new_token = request.data.get("new_token")

        if not new_token or len(new_token) != 64:
            return Response(
                {"error": err_response("Invalid token format", "Bad request")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Client.objects.filter(api_token=new_token).exists():
            return Response(
                {"error": err_response("Token already in use", "Bad request")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if client.last_token_rotation:
            elapsed = (timezone.now() - client.last_token_rotation).total_seconds()
            if elapsed < MINIMUM_TOKEN_ROTATE_TIME():
                return Response(
                    {"error": err_response("Token rotation too frequent", "Bad request")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        client.api_token = new_token
        client.last_token_rotation = timezone.now()
        client.rotation_required = False
        client.lockout_override = False
        client.save(update_fields=["api_token", "last_token_rotation", "rotation_required", "lockout_override"])

        return Response({"status": "ok"}, status=status.HTTP_200_OK)
