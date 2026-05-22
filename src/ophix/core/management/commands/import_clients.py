"""
ophix-manage import_clients
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Import Client records from a JSON file produced by export_clients.

Idempotent: clients are matched by host name + client name. Existing clients
are updated only when a field value differs; identical records are skipped.
The api_token is always written — this is intentional for migration/recovery
so that fleet clients can reconnect without re-registering.

Referenced hosts must already exist on the target server. Run import_hosts
first if restoring a complete server from scratch.

If the file was exported with --passphrase, provide the same passphrase here.
The passphrase is validated before any database changes are made.

Examples
--------
Import from encrypted file:
    ophix-manage import_clients --input-file clients.json --passphrase "secret"

Import from plaintext file:
    ophix-manage import_clients --input-file clients.json

Preview without writing:
    ophix-manage import_clients --input-file clients.json --passphrase "secret" --dry-run
"""

import base64
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))


class Command(BaseCommand):
    help = "Import Client records from a JSON file produced by export_clients."

    def add_arguments(self, parser):
        parser.add_argument(
            "--input-file",
            required=True,
            metavar="FILE",
            help="Source file path (JSON produced by export_clients).",
        )
        parser.add_argument(
            "--passphrase",
            metavar="PASSPHRASE",
            default=None,
            help="Passphrase to decrypt tokens (required if file was exported with --passphrase).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created or updated without making any changes.",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress per-record output. Summary line is always shown.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Bypass token uniqueness checks. Use when a token in the import file "
                "is already assigned to a differently-named client on this server. "
                "The database constraint is still enforced — conflicts that cannot be "
                "resolved are skipped with an error."
            ),
        )

    def handle(self, *args, **options):
        from ophix.core.models import Client, Host

        input_path = Path(options["input_file"])
        passphrase = options["passphrase"]
        dry_run    = options["dry_run"]
        quiet      = options["quiet"]
        force      = options["force"]

        if not input_path.exists():
            raise CommandError(f"Input file not found: {input_path}")

        try:
            payload = json.loads(input_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {input_path}: {exc}")

        if not isinstance(payload, dict) or "clients" not in payload:
            raise CommandError("Unrecognised file format — expected export_clients output.")

        encrypted = payload.get("encrypted", False)

        # Validate passphrase and build Fernet instance before touching the DB.
        fernet = None
        if encrypted:
            if not passphrase:
                raise CommandError(
                    "This file contains encrypted tokens. Provide --passphrase to import."
                )
            try:
                from cryptography.fernet import Fernet, InvalidToken
                salt = base64.urlsafe_b64decode(payload["salt"])
                fernet = Fernet(_derive_key(passphrase, salt))
                # Validate key against the first token we can find.
                for rec in payload["clients"]:
                    if rec.get("api_token"):
                        fernet.decrypt(rec["api_token"].encode())
                        break
            except InvalidToken:
                raise CommandError("Incorrect passphrase — could not decrypt tokens.")
            except Exception as exc:
                raise CommandError(f"Failed to initialise decryption: {exc}")
        elif passphrase and not quiet:
            self.stderr.write(self.style.WARNING(
                "Warning: file is not encrypted but --passphrase was provided — ignoring."
            ))

        records = payload["clients"]
        if not isinstance(records, list):
            raise CommandError("Expected 'clients' to be a JSON array.")

        created = updated = unchanged = skipped = 0

        for i, rec in enumerate(records, 1):
            name      = (rec.get("name") or "").strip()
            host_name = (rec.get("host") or "").strip()

            if not name or not host_name:
                self.stderr.write(f"  Record {i}: missing 'name' or 'host' — skipped.")
                skipped += 1
                continue

            # Resolve host.
            try:
                host = Host.objects.get(name=host_name)
            except Host.DoesNotExist:
                self.stderr.write(
                    f"  {host_name}/{name}: host '{host_name}' not found — skipped. "
                    "Run import_hosts first."
                )
                skipped += 1
                continue

            # Decrypt token if needed.
            raw_token = rec.get("api_token", "")
            if fernet and raw_token:
                try:
                    from cryptography.fernet import InvalidToken
                    raw_token = fernet.decrypt(raw_token.encode()).decode()
                except InvalidToken:
                    self.stderr.write(f"  {host_name}/{name}: token decryption failed — skipped.")
                    skipped += 1
                    continue

            if not raw_token:
                self.stderr.write(f"  {host_name}/{name}: missing api_token — skipped.")
                skipped += 1
                continue

            # Check for token conflict with a different client.
            if not force:
                conflict = (
                    Client.objects.filter(api_token=raw_token)
                    .exclude(name=name, host=host)
                    .first()
                )
                if conflict:
                    self.stderr.write(
                        f"  {host_name}/{name}: token already assigned to "
                        f"'{conflict.host.name}/{conflict.name}' — skipped. "
                        "Use --force to override."
                    )
                    skipped += 1
                    continue

            # Parse last_token_rotation.
            ltr = None
            if rec.get("last_token_rotation"):
                from django.utils.dateparse import parse_datetime
                ltr = parse_datetime(rec["last_token_rotation"])

            fields = {
                "deployment_ref":     rec.get("deployment_ref") or None,
                "venv_name":          rec.get("venv_name") or None,
                "venv_path":          rec.get("venv_path") or None,
                "enabled":            bool(rec.get("enabled", True)),
                "api_token":          raw_token,
                "last_token_rotation": ltr,
            }

            # Create or update.
            try:
                client = Client.objects.get(name=name, host=host)
                changed = {
                    f: v for f, v in fields.items()
                    if str(getattr(client, f)) != str(v)
                }
                if not changed:
                    unchanged += 1
                    if not quiet:
                        self.stdout.write(f"  {host_name}/{name}: unchanged.")
                else:
                    if not quiet:
                        visible = [f for f in changed if f != "api_token"]
                        token_note = " + token" if "api_token" in changed else ""
                        label = (", ".join(visible) + token_note) if visible else "token"
                        self.stdout.write(f"  {host_name}/{name}: updating {label}.")
                    if not dry_run:
                        try:
                            for f, v in changed.items():
                                setattr(client, f, v)
                            client.full_clean()
                            client.save()
                        except Exception as exc:
                            self.stderr.write(f"  {host_name}/{name}: save failed — {exc}")
                            skipped += 1
                            continue
                    updated += 1

            except Client.DoesNotExist:
                if not quiet:
                    self.stdout.write(f"  {host_name}/{name}: creating.")
                if not dry_run:
                    try:
                        client = Client(name=name, host=host, **fields)
                        client.full_clean()
                        client.save()
                    except Exception as exc:
                        self.stderr.write(f"  {host_name}/{name}: save failed — {exc}")
                        skipped += 1
                        continue
                created += 1

        parts = []
        if created:
            parts.append(f"{created} created")
        if updated:
            parts.append(f"{updated} updated")
        if unchanged:
            parts.append(f"{unchanged} unchanged")
        if skipped:
            parts.append(f"{skipped} skipped")
        summary = ", ".join(parts) if parts else "nothing to do"

        if dry_run:
            self.stdout.write(f"Dry run: {summary}.")
        else:
            self.stdout.write(self.style.SUCCESS(f"{summary.capitalize()}."))
