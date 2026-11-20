"""
ophix.core.utils
~~~~~~~~~~~~~~~~
Shared utilities for Ophix domain plugin views.

assert_artifact_access
    The single entry point for checking whether a client may perform
    a given operation on a named artifact.  Domain plugin views call
    this rather than reimplementing the 4-layer check each time.
"""

import ipaddress
import logging

from django.http import Http404
from django.utils.translation import gettext_lazy as _
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
    """
    Return the connecting client's IP address, normalised to canonical form.

    This is the ONLY place in Ophix that decides a request's source IP:
    token+IP authentication and client/DNS-server registration all call it.
    Never parse X-Forwarded-For anywhere else.

    The value comes from the X-Real-IP header, which the bundled nginx
    config sets unconditionally to ``$remote_addr``, overwriting anything
    the client sent.  X-Forwarded-For is deliberately ignored: it is a
    client-supplied, append-only chain, and trusting any entry in it lets a
    caller choose its own apparent source IP.

    When Ophix runs behind a load balancer or other upstream proxy, the
    decision about which proxies to trust is made in nginx (the realip
    module: ``set_real_ip_from`` / ``real_ip_header`` / ``real_ip_recursive``,
    rendered from the ``[nginx] trusted_proxies`` setting), so ``$remote_addr``
    (and therefore X-Real-IP) is already the true client address by the
    time the request reaches Django.

    Falls back to REMOTE_ADDR when X-Real-IP is absent (e.g. ``runserver``
    during development).  Gunicorn listens only on a unix socket that nginx
    owns, so clients cannot reach it directly to forge X-Real-IP.

    IPv4-mapped IPv6 addresses (``::ffff:10.0.0.5``) are reduced to their
    IPv4 form so they compare equal to a Host's ``ipv4_address``.  Returns
    ``""`` if no valid address is available.
    """
    return normalise_ip(
        request.META.get("HTTP_X_REAL_IP")
        or request.META.get("REMOTE_ADDR")
        or ""
    )


def normalise_ip(value: str) -> str:
    """
    Return ``value`` as a canonical IP address string, or ``""`` if invalid.

    IPv6 is compressed and lower-cased; IPv4-mapped IPv6 is reduced to IPv4.
    Use this before comparing any externally supplied IP string against
    ``get_client_ip()`` or a Host's stored address.
    """
    try:
        addr = ipaddress.ip_address((value or "").strip())
    except ValueError:
        return ""
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return str(addr)


def get_host_for_ip(ip: str):
    """
    Return the Host registered with this IP address (IPv4 or IPv6), or None.

    ``ip`` should come from ``get_client_ip()`` so it is already normalised.
    Both address fields are unique, so at most one Host can match.
    """
    from .models import Host  # local import: models must not depend on utils

    if not ip:
        return None
    field = "ipv6_address" if ":" in ip else "ipv4_address"
    return Host.objects.filter(**{field: ip}).first()


def parse_trusted_proxies(value) -> list:
    """
    Parse a comma/whitespace-separated list of trusted upstream proxy
    addresses or CIDRs (the ``[nginx] trusted_proxies`` setting).

    Returns a list of normalised network strings suitable for nginx's
    ``set_real_ip_from`` directive.  Raises ``ValueError`` naming the first
    invalid entry.  Blank input returns an empty list (no proxies trusted,
    the safe default for a server clients connect to directly).
    """
    if not value:
        return []
    networks = []
    for item in value.replace(",", " ").split():
        try:
            networks.append(str(ipaddress.ip_network(item, strict=False)))
        except ValueError:
            raise ValueError(f"Not a valid IP address or CIDR: {item!r}")
    return networks


def err_response(detail: str, fallback: str = None) -> str:
    """
    Return *detail* if AUTH_LEAK_INFO is enabled, otherwise *fallback*.

    Use in view error responses to avoid leaking internal state in
    production while preserving useful messages in development::

        return Response(
            {"error": err_response(_("Credential already exists"), _("Conflict"))},
            status=status.HTTP_409_CONFLICT,
        )
    """
    from django.conf import settings
    if fallback is None:
        fallback = _("Access blocked")
    if getattr(settings, "AUTH_LEAK_INFO", False):
        return detail
    return fallback
