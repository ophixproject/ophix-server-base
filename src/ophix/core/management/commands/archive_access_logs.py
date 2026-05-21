"""
ophix-manage archive_access_logs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Export AccessLog records to a file for long-term retention or compliance.

By default writes a JSON array.  Use --append for incremental cron runs —
that mode writes newline-delimited JSON (NDJSON) so records can be appended
to the same file indefinitely without reading it first.

Combine with prune_access_log to archive-then-purge:

    ophix-manage archive_access_logs --output-file archive.ndjson --days 90 --append
    ophix-manage prune_access_log --days 90

Examples
--------
Archive all records to a JSON array:
    ophix-manage archive_access_logs --output-file access_logs.json

Archive records older than 90 days to a JSON array:
    ophix-manage archive_access_logs --output-file access_logs.json --days 90

Incremental cron-safe append (NDJSON):
    ophix-manage archive_access_logs --output-file access_logs.ndjson --days 90 --append

Preview without writing:
    ophix-manage archive_access_logs --output-file access_logs.json --dry-run
"""

import json
from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


def _serialize(record):
    client = record.client
    host = record.host
    return {
        "id":            record.id,
        "timestamp":     record.timestamp.isoformat(),
        "operation":     record.operation,
        "artifact_type": record.artifact_type,
        "artifact_name": record.artifact_name,
        "artifact_id":   record.artifact_id,
        "client_id":     record.client_id,
        "client_name":   client.name if client else None,
        "host_id":       record.host_id,
        "host_ip":       str(host.ipv4_address or host.ipv6_address) if host else None,
    }


class Command(BaseCommand):
    help = "Export AccessLog records to a file for long-term retention or compliance."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-file",
            required=True,
            metavar="FILE",
            help="Destination file path. Use .json for array output, .ndjson for append mode.",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            metavar="N",
            help=(
                "Only export records older than N days. If omitted, falls back to the "
                "PRUNE_ACCESS_LOG_DAYS setting, then to 90 days. Use --all to export "
                "every record regardless of age."
            ),
        )
        parser.add_argument(
            "--all",
            action="store_true",
            dest="export_all",
            help=(
                "Export all records regardless of age. Use for incident snapshots or "
                "full compliance dumps. Overrides --days and PRUNE_ACCESS_LOG_DAYS."
            ),
        )
        parser.add_argument(
            "--append",
            action="store_true",
            help=(
                "Append records as newline-delimited JSON (NDJSON) rather than "
                "writing a JSON array. Safe to use from cron — grows one file "
                "indefinitely without reading existing content."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many records would be exported without writing anything.",
        )

    def handle(self, *args, **options):
        from ophix.core.models import AccessLog

        from django.conf import settings

        output_path = Path(options["output_file"])
        days        = options["days"]
        append      = options["append"]
        dry_run     = options["dry_run"]
        export_all  = options["export_all"]

        if not export_all:
            if days is None:
                days = getattr(settings, "PRUNE_ACCESS_LOG_DAYS", 90)

        qs = AccessLog.objects.select_related("client", "host").order_by("timestamp")
        if not export_all and days is not None:
            cutoff = timezone.now() - timedelta(days=days)
            qs = qs.filter(timestamp__lt=cutoff)

        count = qs.count()

        if dry_run:
            qualifier = "total" if export_all else f"older than {days} days"
            self.stdout.write(
                f"Dry run: {count} record(s) {qualifier} would be exported to {output_path}."
            )
            return

        if count == 0:
            qualifier = "" if export_all else f"older than {days} days "
            self.stdout.write(f"No access log records {qualifier}found — nothing to export.")
            return

        if not dry_run and not output_path.parent.exists():
            raise CommandError(f"Output directory does not exist: {output_path.parent}")

        if append:
            with output_path.open("a", encoding="utf-8") as f:
                for record in qs.iterator():
                    f.write(json.dumps(_serialize(record), default=str) + "\n")
        else:
            records = [_serialize(r) for r in qs.iterator()]
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, default=str)

        mode = "appended (NDJSON)" if append else "written (JSON array)"
        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {count} record(s) to {output_path} [{mode}]."
            )
        )
