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

Delete all records:
    ophix-manage prune_access_log --all

Preview how many records would be removed without deleting:
    ophix-manage prune_access_log --dry-run
    ophix-manage prune_access_log --days 30 --dry-run
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Delete AccessLog records older than N days (default: PRUNE_ACCESS_LOG_DAYS setting, or 90)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            metavar="N",
            help="Delete records older than this many days (default: PRUNE_ACCESS_LOG_DAYS setting, or 90).",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            dest="prune_all",
            help="Delete all records regardless of age. Overrides --days and PRUNE_ACCESS_LOG_DAYS.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many records would be deleted without deleting them.",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress all output. Useful when running from cron.",
        )

    def handle(self, *args, **options):
        from django.conf import settings
        from ophix.core.models import AccessLog

        days      = options["days"]
        prune_all = options["prune_all"]
        dry_run   = options["dry_run"]
        quiet     = options["quiet"]

        if prune_all:
            qs = AccessLog.objects.all()
            qualifier = "all"
        else:
            if days is None:
                days = getattr(settings, "PRUNE_ACCESS_LOG_DAYS", 90)
            cutoff = timezone.now() - timedelta(days=days)
            qs = AccessLog.objects.filter(timestamp__lt=cutoff)
            qualifier = f"older than {days} days"

        count = qs.count()

        if dry_run:
            self.stdout.write(
                f"Dry run: {count} record(s) {qualifier} would be deleted."
            )
            return

        if count == 0:
            if not quiet:
                self.stdout.write(f"No access log records {qualifier} found.")
            return

        qs.delete()
        if not quiet:
            self.stdout.write(
                self.style.SUCCESS(f"Deleted {count} access log record(s) {qualifier}.")
            )
