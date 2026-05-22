"""
ophix-manage import_hosts
~~~~~~~~~~~~~~~~~~~~~~~~~
Import Host records from a JSON file produced by export_hosts.

Idempotent: hosts are matched by name. Existing hosts are updated only when
a field value differs; identical records are skipped. Safe to run repeatedly
from cron to keep hosts in sync across multiple Ophix servers.

Examples
--------
Import from file:
    ophix-manage import_hosts --input-file hosts.json

Preview without writing:
    ophix-manage import_hosts --input-file hosts.json --dry-run
"""

import ipaddress
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


def _parse_ip(value, version):
    if not value:
        return None
    try:
        addr = ipaddress.ip_address(value)
        expected = ipaddress.IPv4Address if version == 4 else ipaddress.IPv6Address
        if not isinstance(addr, expected):
            raise ValueError
        return str(addr)
    except ValueError:
        raise ValueError(f"Invalid IPv{version} address: {value!r}")


def _ip_str(value):
    return str(value) if value is not None else None


class Command(BaseCommand):
    help = "Import Host records from a JSON file produced by export_hosts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--input-file",
            required=True,
            metavar="FILE",
            help="Source file path (JSON produced by export_hosts).",
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

    def handle(self, *args, **options):
        from ophix.core.models import Host

        input_path = Path(options["input_file"])
        dry_run    = options["dry_run"]
        quiet      = options["quiet"]

        if not input_path.exists():
            raise CommandError(f"Input file not found: {input_path}")

        try:
            records = json.loads(input_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {input_path}: {exc}")

        if not isinstance(records, list):
            raise CommandError("Expected a JSON array at the top level.")

        created = updated = unchanged = skipped = 0

        for i, rec in enumerate(records, 1):
            name = (rec.get("name") or "").strip()
            if not name:
                self.stderr.write(f"  Record {i}: missing 'name' — skipped.")
                skipped += 1
                continue

            # Validate IP addresses.
            try:
                ipv4 = _parse_ip(rec.get("ipv4_address"), 4)
                ipv6 = _parse_ip(rec.get("ipv6_address"), 6)
            except ValueError as exc:
                self.stderr.write(f"  {name}: {exc} — skipped.")
                skipped += 1
                continue

            if not ipv4 and not ipv6:
                self.stderr.write(f"  {name}: at least one IP address is required — skipped.")
                skipped += 1
                continue

            description = rec.get("description") or None
            enabled     = bool(rec.get("enabled", True))

            # Check for IP conflicts with a different host.
            conflict = None
            for field, val in (("ipv4_address", ipv4), ("ipv6_address", ipv6)):
                if val:
                    other = Host.objects.filter(**{field: val}).exclude(name=name).first()
                    if other:
                        conflict = f"{field} {val!r} already assigned to '{other.name}'"
                        break
            if conflict:
                self.stderr.write(f"  {name}: {conflict} — skipped.")
                skipped += 1
                continue

            # Create or update.
            try:
                host = Host.objects.get(name=name)
                changed = {
                    f: v for f, v in (
                        ("ipv4_address", ipv4),
                        ("ipv6_address", ipv6),
                        ("description",  description),
                        ("enabled",      enabled),
                    )
                    if _ip_str(getattr(host, f)) != _ip_str(v)
                }
                if not changed:
                    unchanged += 1
                    if not quiet:
                        self.stdout.write(f"  {name}: unchanged.")
                else:
                    if not quiet:
                        self.stdout.write(f"  {name}: updating {', '.join(changed)}.")
                    if not dry_run:
                        for f, v in changed.items():
                            setattr(host, f, v)
                        host.full_clean()
                        host.save()
                    updated += 1

            except Host.DoesNotExist:
                if not quiet:
                    self.stdout.write(f"  {name}: creating.")
                if not dry_run:
                    host = Host(
                        name=name,
                        ipv4_address=ipv4,
                        ipv6_address=ipv6,
                        description=description,
                        enabled=enabled,
                    )
                    host.full_clean()
                    host.save()
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
