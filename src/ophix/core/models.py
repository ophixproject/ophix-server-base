"""
ophix.core.models
~~~~~~~~~~~~~~~~~
Base models shared by all Ophix Project Servers.

Host
    A trusted machine, identified by its IPv4 address.

Client
    A named automation or script running on a Host.
    Each Client has a unique API token used for authentication.

ClientArtifactBase
    Abstract join model linking a Client to an artifact.
    Domain plugins subclass this to create their own concrete join tables,
    adding a ForeignKey to their specific artifact model.

    Permission flags on the join record:
        enabled     — client can read the artifact (synonym: can_read)
        can_update  — client can overwrite the artifact
        can_delete  — client can delete the artifact
        can_share   — placeholder: future client-driven sharing
"""

import secrets
from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# Token generator
# ---------------------------------------------------------------------------

def generate_api_token() -> str:
    """Generate a cryptographically secure 64-character hex token."""
    return secrets.token_hex(32)


# ---------------------------------------------------------------------------
# Host
# ---------------------------------------------------------------------------

class Host(models.Model):
    name = models.CharField(max_length=100, unique=True)
    ipv4_address = models.GenericIPAddressField(protocol="IPv4", unique=True)
    description = models.TextField(blank=True, null=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name} ({self.ipv4_address})"


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class Client(models.Model):
    host = models.ForeignKey(
        Host,
        on_delete=models.CASCADE,
        related_name="clients",
    )
    name = models.CharField(max_length=100)
    deployment_ref = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Deployment reference (repository name or similar identifier)",
    )
    venv_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Name of the Python virtual environment",
    )
    venv_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Absolute path to the Python virtual environment",
    )
    enabled = models.BooleanField(default=True)
    api_token = models.CharField(
        max_length=64,
        unique=True,
        default=generate_api_token,
    )
    last_token_rotation = models.DateTimeField(null=True, blank=True, default=None)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["host", "name"],
                name="unique_client_per_host",
            )
        ]

    def __str__(self) -> str:
        return f"{self.host.name}:{self.name}"


# ---------------------------------------------------------------------------
# ClientArtifactBase
# ---------------------------------------------------------------------------

class ClientArtifactBase(models.Model):
    """
    Abstract base for the join table between a Client and a domain artifact.

    Subclass this in each domain plugin and add a ForeignKey to the
    artifact model::

        class ClientCredential(ClientArtifactBase):
            credential = models.ForeignKey(
                Credential, on_delete=models.CASCADE, related_name="client_links"
            )

            class Meta(ClientArtifactBase.Meta):
                unique_together = ("client", "credential")

    Permission semantics
    --------------------
    ``enabled``     Client can read the artifact.  Setting this False
                    blocks all access regardless of the other flags.
    ``can_update``  Client may overwrite artifact content (PUT).
    ``can_delete``  Client may delete the artifact (DELETE).
                    Effective only when ENABLE_ARTIFACT_DELETE=true in .env.
    ``can_share``   Reserved for future client-driven sharing workflows.
                    Currently unused; stored as False.

    When a client creates a new artifact via POST the auto-created join
    record is initialised with enabled=True, can_update=True, can_delete=True
    to preserve the "creator owns their artifact" behaviour from cred-server.
    Admin-created join records default all flags to False and must be
    granted explicitly.
    """

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="+",  # subclasses define their own related_name
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Client can read this artifact (can_read).",
    )
    can_update = models.BooleanField(
        default=False,
        help_text="Client may overwrite this artifact.",
    )
    can_delete = models.BooleanField(
        default=False,
        help_text="Client may delete this artifact.",
    )
    can_share = models.BooleanField(
        default=False,
        help_text="Reserved: future client-driven sharing. Currently unused.",
    )
    notes = models.TextField(null=True, blank=True)

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# AccessLog
# ---------------------------------------------------------------------------

class AccessLog(models.Model):
    """
    Immutable record of a client artifact access event.

    client and host are SET_NULL FKs — the log survives client/host deletion.
    artifact_id is a bare integer (not a FK) — the log survives artifact deletion.
    artifact_name snapshots the artifact name at access time, so renames and
    deletions do not retroactively alter the audit trail.
    timestamp is set at event creation (not at DB insert time) so that batch
    writes preserve the actual time of access.
    """

    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    host = models.ForeignKey(
        Host,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    operation = models.CharField(max_length=10)
    artifact_type = models.CharField(max_length=100)
    artifact_name = models.CharField(max_length=200, blank=True)
    artifact_id = models.IntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(db_index=True, default=timezone.now)

    class Meta:
        ordering = ("-timestamp",)

    def __str__(self) -> str:
        return (
            f"{self.timestamp:%Y-%m-%d %H:%M:%S} "
            f"{self.operation} "
            f"{self.artifact_type}/{self.artifact_name}"
        )
