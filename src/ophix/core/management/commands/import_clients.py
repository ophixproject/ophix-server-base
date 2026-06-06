"""
ophix-manage import_clients
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Import Client records from a JSON file produced by export_clients.

Idempotent: clients are matched by host name + client name. Existing clients
are updated only when a field value differs; identical records are skipped.
The api_token hash is always written — this is intentional for migration/recovery
so that fleet clients can reconnect to a restored server without re-registering.

Referenced hosts must already exist on the target server. Run import_hosts
first if restoring a complete server from scratch.

Examples
--------
Import clients:
    ophix-manage import_clients --input-file clients.json

Preview without writing:
    ophix-manage import_clients --input-file clients.json --dry-run
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


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
                "Bypass token uniqueness checks. Use when a token hash in the import "
                "file is already assigned to a differently-named client on this server."
            ),
        )

    def handle(self, *args, **options):
        from ophix.core.models import Client, Host

        input_path = Path(options["input_file"])
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

        if payload.get("token_format") != "hash":
            raise CommandError(
                "This file was produced by an older version of export_clients "
                "and contains plaintext or encrypted tokens. Re-export from the "
                "source server using the current version before importing."
            )

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

            try:
                host = Host.objects.get(name=host_name)
            except Host.DoesNotExist:
                self.stderr.write(
                    f"  {host_name}/{name}: host '{host_name}' not found — skipped. "
                    "Run import_hosts first."
                )
                skipped += 1
                continue

            token_hash = rec.get("api_token", "")
            if not token_hash:
                self.stderr.write(f"  {host_name}/{name}: missing api_token — skipped.")
                skipped += 1
                continue

            if not force:
                conflict = (
                    Client.objects.filter(api_token=token_hash)
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

            ltr = None
            if rec.get("last_token_rotation"):
                from django.utils.dateparse import parse_datetime
                ltr = parse_datetime(rec["last_token_rotation"])

            fields = {
                "deployment_ref":      rec.get("deployment_ref") or None,
                "venv_name":           rec.get("venv_name") or None,
                "venv_path":           rec.get("venv_path") or None,
                "enabled":             bool(rec.get("enabled", True)),
                "api_token":           token_hash,
                "last_token_rotation": ltr,
            }

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
