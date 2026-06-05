"""
ophix-manage export_clients
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Export Client records to a JSON file for backup, recovery, or server migration.

Client tokens are included so that fleet clients can reconnect to a restored
server without re-registering. Protect the output file accordingly.

Optionally encrypt tokens with a passphrase-derived Fernet key. The salt is
stored in the file; the passphrase is not. Use the same passphrase with
import_clients to decrypt on the receiving server.

Without --passphrase, tokens are exported in plaintext. This is a deliberate
operator choice — the file must be treated as a credential store.

Examples
--------
Export with encrypted tokens (recommended):
    ophix-manage export_clients --output-file clients.json --passphrase "secret"

Export with plaintext tokens:
    ophix-manage export_clients --output-file clients.json

Preview without writing:
    ophix-manage export_clients --output-file clients.json --dry-run
"""

import base64
import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))


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


def _serialize(client, fernet=None):
    token = client.api_token
    if fernet:
        token = fernet.encrypt(token.encode()).decode()
    return {
        "name":               client.name,
        "host":               client.host.name,
        "deployment_ref":     client.deployment_ref,
        "venv_name":          client.venv_name,
        "venv_path":          client.venv_path,
        "enabled":            client.enabled,
        "api_token":          token,
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
        passphrase_group = parser.add_mutually_exclusive_group()
        passphrase_group.add_argument(
            "--passphrase",
            nargs="?",
            const="",
            metavar="PASSPHRASE",
            default=None,
            help="Encrypt client tokens using a passphrase-derived Fernet key. Omit the value to be prompted securely (input is hidden).",
        )
        passphrase_group.add_argument(
            "--passphrase-env",
            metavar="ENVVAR",
            default=None,
            help="Read the passphrase from the named environment variable (for automated use).",
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
        passphrase     = options["passphrase"]
        passphrase_env = options["passphrase_env"]
        if passphrase_env:
            passphrase = os.environ.get(passphrase_env)
            if not passphrase:
                raise CommandError(
                    f"Environment variable '{passphrase_env}' is not set or empty."
                )
        elif passphrase == "":
            import getpass
            while True:
                passphrase = getpass.getpass("Passphrase: ")
                if not passphrase:
                    raise CommandError("Passphrase cannot be empty.")
                confirm = getpass.getpass("Confirm passphrase: ")
                if passphrase == confirm:
                    break
                self.stderr.write("Passphrases do not match — try again.")
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

        fernet = None
        salt_b64 = None
        if passphrase:
            from cryptography.fernet import Fernet
            salt = os.urandom(16)
            salt_b64 = base64.urlsafe_b64encode(salt).decode()
            fernet = Fernet(_derive_key(passphrase, salt))

        if not passphrase and not quiet:
            self.stderr.write(self.style.WARNING(
                "Warning: exporting client tokens in plaintext. "
                "Use --passphrase to encrypt. Protect this file as a credential store."
            ))

        payload = {
            "version":   1,
            "meta":      _build_meta("clients", "export_clients"),
            "encrypted": fernet is not None,
            "salt":      salt_b64,
            "clients":   [_serialize(c, fernet) for c in clients],
        }

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        if not quiet:
            enc_note = " (tokens encrypted)" if fernet else " (tokens plaintext)"
            self.stdout.write(self.style.SUCCESS(
                f"Exported {count} client(s) to {output_path}{enc_note}."
            ))
