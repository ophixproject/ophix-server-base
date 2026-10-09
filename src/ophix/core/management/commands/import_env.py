"""
ophix-manage import_env
~~~~~~~~~~~~~~~~~~~~~~~
Restore a .env file from a backup produced by export_env.

Bootstrap constraint: import_env is a management command, so Django needs a
minimal .env to start. Use configure_install to generate a skeleton .env first,
then run import_env to overwrite it with the backed-up version.

Typical restore sequence on a fresh machine:
    1. pip install <packages>
    2. ophix-manage configure_install <slug>   (generates skeleton .env)
    3. ophix-manage import_env --input-file env.json --passphrase
    4. sudo systemctl restart <slug>           (Django now has correct keys/DB)
    5. ophix-manage migrate
    6. ophix-manage import_hosts, import_clients, import_<domain>

If the INSTALL_DIR path differs on the new machine, use --install-dir to patch
it in place so you don't need to manually edit the restored .env.

Examples
--------
Restore from encrypted backup (prompted securely):
    ophix-manage import_env --input-file env.json --passphrase

Restore with INSTALL_DIR patched to a different path:
    ophix-manage import_env --input-file env.json --passphrase --install-dir /srv/ophix/credserver

Restore with passphrase from environment variable:
    ophix-manage import_env --input-file env.json --passphrase-env BACKUP_PASSPHRASE

Preview decrypted content without writing:
    ophix-manage import_env --input-file env.json --passphrase --dry-run
"""

import json
import os
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ophix.core import crypto


class Command(BaseCommand):
    help = "Restore a .env file from a backup produced by export_env."

    def add_arguments(self, parser):
        parser.add_argument(
            "--input-file",
            metavar="FILE",
            required=True,
            help="Source file (JSON produced by export_env).",
        )
        passphrase_group = parser.add_mutually_exclusive_group()
        passphrase_group.add_argument(
            "--passphrase",
            nargs="?",
            const="",
            metavar="PASSPHRASE",
            default=None,
            help="Passphrase to decrypt. Omit the value to be prompted securely (input is hidden).",
        )
        passphrase_group.add_argument(
            "--passphrase-env",
            metavar="ENVVAR",
            default=None,
            help="Read the passphrase from the named environment variable.",
        )
        parser.add_argument(
            "--output-file",
            metavar="FILE",
            default=None,
            help="Where to write the restored .env (default: .env in the current directory).",
        )
        parser.add_argument(
            "--install-dir",
            metavar="PATH",
            default=None,
            help=(
                "Override INSTALL_DIR in the restored .env. "
                "Use this when restoring to a machine where the install path differs."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Decrypt and show what would be written without making any changes.",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress all output.",
        )

    def handle(self, *args, **options):
        input_path     = Path(options["input_file"])
        passphrase     = options["passphrase"]
        passphrase_env = options["passphrase_env"]
        output_file    = options["output_file"]
        install_dir    = options["install_dir"]
        dry_run        = options["dry_run"]
        quiet          = options["quiet"]

        if not input_path.exists():
            raise CommandError(f"Input file not found: {input_path}")

        try:
            with input_path.open(encoding="utf-8") as f:
                payload = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            raise CommandError(f"Cannot read input file: {exc}") from exc

        if payload.get("version") != 1:
            raise CommandError(
                f"Unsupported file version: {payload.get('version')}. "
                "This file may have been produced by a newer version of export_env."
            )

        if not payload.get("encrypted"):
            raise CommandError(
                "This file does not appear to be an export_env backup — "
                "export_env always produces encrypted output."
            )

        # Resolve passphrase
        if passphrase_env:
            passphrase = os.environ.get(passphrase_env)
            if not passphrase:
                raise CommandError(
                    f"Environment variable '{passphrase_env}' is not set or empty."
                )
        elif passphrase == "":
            import getpass
            passphrase = getpass.getpass("Passphrase: ")
            if not passphrase:
                raise CommandError("Passphrase cannot be empty.")
        elif passphrase is None:
            raise CommandError(
                "A passphrase is required. Use --passphrase or --passphrase-env ENVVAR."
            )

        # Decrypt
        try:
            cipher = crypto.build_import_cipher(
                payload.get("cipher"), passphrase, payload.get("salt")
            )
            env_content = cipher.decrypt(payload["content"])
        except (crypto.DecryptionError, KeyError, Exception) as exc:
            raise CommandError(
                "Decryption failed — wrong passphrase or corrupt file."
            ) from exc

        # Patch INSTALL_DIR if requested
        if install_dir:
            env_content, count = re.subn(
                r"^(INSTALL_DIR\s*=\s*).*$",
                lambda m: m.group(1) + install_dir,
                env_content,
                flags=re.MULTILINE,
            )
            if count == 0 and not quiet:
                self.stderr.write(self.style.WARNING(
                    "Warning: INSTALL_DIR not found in the .env — --install-dir had no effect."
                ))

        # Resolve output path
        output_path = Path(output_file) if output_file else Path.cwd() / ".env"

        if dry_run:
            if not quiet:
                self.stdout.write(f"Dry run: would write restored .env to {output_path}.")
                if install_dir:
                    self.stdout.write(f"  INSTALL_DIR would be patched to: {install_dir}")
            return

        # Warn if INSTALL_DIR in the restored content doesn't exist on this machine
        m = re.search(r"^INSTALL_DIR\s*=\s*(.+)$", env_content, re.MULTILINE)
        if m:
            install_dir_value = m.group(1).strip().strip('"').strip("'")
            if install_dir_value and not Path(install_dir_value).exists():
                if not quiet:
                    self.stderr.write(self.style.WARNING(
                        f"Warning: INSTALL_DIR={install_dir_value!r} does not exist on this machine. "
                        "Edit .env before restarting, or re-run with --install-dir <path> "
                        "to patch it automatically."
                    ))

        output_path.write_text(env_content, encoding="utf-8")

        if not quiet:
            self.stdout.write(self.style.SUCCESS(f"Restored .env to {output_path}."))
            self.stdout.write("Restart the service for changes to take effect.")
