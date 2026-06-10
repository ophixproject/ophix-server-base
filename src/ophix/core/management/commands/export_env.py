"""
ophix-manage export_env
~~~~~~~~~~~~~~~~~~~~~~~
Export the server .env file to an encrypted backup.

The .env contains sensitive values including the Django secret key, database
credentials, and encryption keys. A passphrase is always required — there is
no plaintext export option.

Use import_env on the receiving server to restore. The passphrase used here
must be supplied to import_env.

Examples
--------
Export with passphrase (prompted securely):
    ophix-manage export_env --output-file env.json --passphrase

Export with passphrase from environment variable (for automated/cron use):
    ophix-manage export_env --output-file env.json --passphrase-env BACKUP_PASSPHRASE

Preview without writing:
    ophix-manage export_env --output-file env.json --passphrase --dry-run
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


def _build_meta(command: str) -> dict:
    import datetime
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
        "command":        command,
        "run_by":         run_by,
        "login_user":     os.environ.get("SUDO_USER") or None,
        "ssh_origin":     ssh_raw.split()[0] if ssh_raw else None,
    }


class Command(BaseCommand):
    help = "Export the server .env file to an encrypted backup."

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
            help=(
                "Passphrase for encryption. "
                "Omit the value to be prompted securely (input is hidden). "
                "Either --passphrase or --passphrase-env is required."
            ),
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
            help="Show what would be exported without writing anything.",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress all output.",
        )

    def handle(self, *args, **options):
        from cryptography.fernet import Fernet
        from dotenv import find_dotenv

        output_path    = Path(options["output_file"])
        passphrase     = options["passphrase"]
        passphrase_env = options["passphrase_env"]
        dry_run        = options["dry_run"]
        quiet          = options["quiet"]

        # Passphrase is always required for export_env
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
        elif passphrase is None:
            raise CommandError(
                "A passphrase is required for export_env. "
                "Use --passphrase or --passphrase-env ENVVAR."
            )

        # Find .env (same lookup as settings.py)
        env_path_str = find_dotenv(usecwd=True)
        if not env_path_str:
            raise CommandError(
                "No .env file found in the current directory or its parents. "
                "Run this command from the server install directory."
            )
        env_path = Path(env_path_str)

        if dry_run:
            if not quiet:
                self.stdout.write(
                    f"Dry run: would export {env_path} to {output_path} (encrypted)."
                )
            return

        if not output_path.parent.exists():
            raise CommandError(f"Output directory does not exist: {output_path.parent}")

        env_content = env_path.read_text(encoding="utf-8")

        salt = os.urandom(16)
        salt_b64 = base64.urlsafe_b64encode(salt).decode()
        fernet = Fernet(_derive_key(passphrase, salt))
        encrypted_content = fernet.encrypt(env_content.encode()).decode()

        payload = {
            "version":   1,
            "meta":      _build_meta("export_env"),
            "env_path":  str(env_path),
            "encrypted": True,
            "salt":      salt_b64,
            "content":   encrypted_content,
        }

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        if not quiet:
            self.stdout.write(self.style.SUCCESS(
                f"Exported {env_path} to {output_path} (encrypted)."
            ))
