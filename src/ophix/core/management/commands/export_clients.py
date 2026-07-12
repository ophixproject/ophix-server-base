"""
ophix-manage export_clients
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Export Client records to a JSON file for backup, recovery, or server migration.

Client tokens are included as SHA-256 hashes (the value stored in the database).
A hash is not a usable credential — it cannot be used to authenticate as the client.
Fleet clients reconnect to a restored server using the same plaintext token they
already hold; the server re-hashes on every request.

No passphrase option is provided: there is nothing sensitive to encrypt. The export
file contains topology (host names, IPs, client names) and token hashes. Protect it
with filesystem permissions as you would any configuration file.

Examples
--------
Export all clients:
    ophix-manage export_clients --output-file clients.json

Preview without writing:
    ophix-manage export_clients --output-file clients.json --dry-run
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


def _build_meta(domain: str, command: str) -> dict:
    import datetime
    import os
    import pwd
    import socket
    from django.conf import settings
    try:
        run_by = pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        run_by = os.environ.get("USER") or os.environ.get("LOGNAME")
    ssh_raw = os.environ.get("SSH_CLIENT", "")
    return {
        "created_at":     datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "server_name":    getattr(settings, "SERVER_NAME", None),
        "server_version": getattr(settings, "SERVER_VERSION", None),
        "hostname":       socket.gethostname(),
        "domain":         domain,
        "command":        command,
        "run_by":         run_by,
        "login_user":     os.environ.get("SUDO_USER") or None,
        "ssh_origin":     ssh_raw.split()[0] if ssh_raw else None,
    }


def _serialize(client):
    return {
        "name":               client.name,
        "host":               client.host.name,
        "deployment_ref":     client.deployment_ref,
        "venv_name":          client.venv_name,
        "venv_path":          client.venv_path,
        "enabled":            client.enabled,
        "token_hash":         client.token_hash,
        "last_token_rotation": (
            client.last_token_rotation.isoformat()
            if client.last_token_rotation else None
        ),
    }


class Command(BaseCommand):
    help = "Export Client records to a JSON file for backup or server migration."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-file",
            required=True,
            metavar="FILE",
            help="Destination file path.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many clients would be exported without writing anything.",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress all output.",
        )

    def handle(self, *args, **options):
        from ophix.core.models import Client

        output_path = Path(options["output_file"])
        dry_run     = options["dry_run"]
        quiet       = options["quiet"]

        clients = list(Client.objects.select_related("host").order_by("host__name", "name"))
        count = len(clients)

        if dry_run:
            self.stdout.write(f"Dry run: {count} client(s) would be exported to {output_path}.")
            return

        if count == 0:
            if not quiet:
                self.stdout.write("No clients found — nothing to export.")
            return

        if not output_path.parent.exists():
            raise CommandError(f"Output directory does not exist: {output_path.parent}")

        payload = {
            "version":      2,
            "token_format": "hash",
            "meta":         _build_meta("clients", "export_clients"),
            "clients":      [_serialize(c) for c in clients],
        }

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        if not quiet:
            self.stdout.write(self.style.SUCCESS(
                f"Exported {count} client(s) to {output_path} (tokens as SHA-256 hashes)."
            ))
