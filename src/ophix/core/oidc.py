"""
ophix.core.oidc — REMOVED
~~~~~~~~~~~~~~~~~~~~~~~~~
The OphixOIDCBackend has moved to the ophix-auth-oidc plugin package.

    pip install ophix-auth-oidc

This file is retained only to produce a clear ImportError message if any
code still references the old path.
"""

raise ImportError(
    "ophix.core.oidc has been removed. "
    "Install ophix-auth-oidc and update any references to use "
    "ophix_auth_oidc.backend.OphixOIDCBackend."
)
