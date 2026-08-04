"""
ophix-manage export_hosts
~~~~~~~~~~~~~~~~~~~~~~~~~
Export Host records to a JSON file for transfer to another Ophix server.

The exported file can be imported on any Ophix server using import_hosts.
Combine with a shared network path or cron job to keep hosts in sync across
multiple servers.

Examples
--------
Export all hosts:
    ophix-manage export_hosts --output-file hosts.json

Preview without writing:
    ophix-manage export_hosts --output-file hosts.json --dry-run
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


def _serialize(host):
    return {
        "name":         host.name,
        "ipv4_address": str(host.ipv4_address) if host.ipv4_address else None,
        "ipv6_address": str(host.ipv6_address) if host.ipv6_address else None,
        "description":  host.description,
        "enabled":      host.enabled,
    }


class Command(BaseCommand):
    help = "Export Host records to a JSON file for import on another Ophix server."

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
            help="Show how many hosts would be exported without writing anything.",
        )
        parser.add_argument(
            "--stable",
            action="store_true",
            help="Omit the meta block and sort keys, so re-exporting unchanged data "
                 "produces byte-identical output (used by ophix-revisions).",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress all output.",
        )

    def handle(self, *args, **options):
        from ophix.core.models import Host

        output_path = Path(options["output_file"])
        dry_run     = options["dry_run"]
        stable      = options["stable"]
        quiet       = options["quiet"]

        hosts = list(Host.objects.order_by("name"))
        count = len(hosts)

        if dry_run:
            self.stdout.write(f"Dry run: {count} host(s) would be exported to {output_path}.")
            return

        if count == 0:
            if not quiet:
                self.stdout.write("No hosts found — nothing to export.")
            return

        if not output_path.parent.exists():
            raise CommandError(f"Output directory does not exist: {output_path.parent}")

        payload = {"version": 1}
        if not stable:
            payload["meta"] = _build_meta("hosts", "export_hosts")
        payload["hosts"] = [_serialize(h) for h in hosts]

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=stable)

        if not quiet:
            self.stdout.write(self.style.SUCCESS(f"Exported {count} host(s) to {output_path}."))
