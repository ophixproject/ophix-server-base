"""
ophix.core.utils
~~~~~~~~~~~~~~~~
Shared utilities for Ophix domain plugin views.

assert_artifact_access
    The single entry point for checking whether a client may perform
    a given operation on a named artifact.  Domain plugin views call
    this rather than reimplementing the 4-layer check each time.
"""

import logging

from django.http import Http404
from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


def assert_artifact_access(
    client,
    artifact,
    link_model,
    artifact_fk_field: str,
    *,
    require_update: bool = False,
    require_delete: bool = False,
):
    """
    Assert that *client* may access *artifact* and return the join record.

    Layer checks (all four must pass):
      1. artifact.enabled         — the artifact itself is active
      2. Join record exists       — client is linked to the artifact
      3. link.enabled (can_read)  — the link is active
      4. Optional flags           — can_update / can_delete if required

    Note: Host.enabled and Client.enabled are already validated by
    ClientTokenAuthentication before any view is reached.

    Parameters
    ----------
    client
        The authenticated Client (request.user).
    artifact
        The artifact model instance to check access against.
    link_model
        The concrete ClientArtifact join model class (e.g. ClientCredential).
    artifact_fk_field
        The name of the ForeignKey field on *link_model* that points to the
        artifact (e.g. ``"credential"``).
    require_update
        If True, also check link.can_update.
    require_delete
        If True, also check link.can_delete.

    Returns
    -------
    The join record instance.

    Raises
    ------
    Http404
        If the artifact is not enabled or no join record exists.
    PermissionDenied
        If the join record exists but the required permission flag is False.
    """
    # Layer 3: artifact enabled
    if not artifact.enabled:
        raise Http404

    # Layer 4a: join record exists
    try:
        link = link_model.objects.select_related("client").get(
            client=client,
            **{artifact_fk_field: artifact},
        )
    except link_model.DoesNotExist:
        raise Http404

    # Layer 4b: link enabled (can_read)
    if not link.enabled:
        logger.info(
            "Access blocked: client %s link to %s is disabled",
            client,
            artifact,
        )
        raise PermissionDenied

    # Optional permission flag checks
    if require_update and not link.can_update:
        logger.info(
            "Update blocked: client %s does not have can_update on %s",
            client,
            artifact,
        )
        raise PermissionDenied

    if require_delete and not link.can_delete:
        logger.info(
            "Delete blocked: client %s does not have can_delete on %s",
            client,
            artifact,
        )
        raise PermissionDenied

    return link


def get_client_ip(request) -> str:
    """Extract the real client IP, respecting X-Forwarded-For."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def err_response(detail: str, fallback: str = "Access blocked") -> str:
    """
    Return *detail* if AUTH_LEAK_INFO is enabled, otherwise *fallback*.

    Use in view error responses to avoid leaking internal state in
    production while preserving useful messages in development::

        return Response(
            {"error": err_response("Credential already exists", "Conflict")},
            status=status.HTTP_409_CONFLICT,
        )
    """
    from django.conf import settings
    if getattr(settings, "AUTH_LEAK_INFO", False):
        return detail
    return fallback
