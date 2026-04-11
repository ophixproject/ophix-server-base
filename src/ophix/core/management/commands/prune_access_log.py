"""
ophix-manage prune_access_log
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete AccessLog records older than N days.

Intended to be run periodically via cron to keep the access log table
from growing unbounded. Operates in a single DELETE query.

Examples
--------
Delete records older than 90 days (default):
    ophix-manage prune_access_log

Delete records older than 30 days:
    ophix-manage prune_access_log --days 30

Preview how many records would be removed without deleting:
    ophix-manage prune_access_log --dry-run
    ophix-manage prune_access_log --days 30 --dry-run
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Delete AccessLog records older than N days (default 90)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            metavar="N",
            help="Delete records older than this many days (default: 90).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many records would be deleted without deleting them.",
        )

    def handle(self, *args, **options):
        from ophix.core.models import AccessLog

        days = options["days"]
        dry_run = options["dry_run"]

        cutoff = timezone.now() - timedelta(days=days)
        qs = AccessLog.objects.filter(timestamp__lt=cutoff)
        count = qs.count()

        if dry_run:
            self.stdout.write(
                f"Dry run: {count} record(s) older than {days} days would be deleted "
                f"(cutoff: {cutoff:%Y-%m-%d %H:%M:%S} UTC)."
            )
            return

        if count == 0:
            self.stdout.write(f"No access log records older than {days} days found.")
            return

        qs.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {count} access log record(s) older than {days} days."
            )
        )
