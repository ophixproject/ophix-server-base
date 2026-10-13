"""
ophix-manage prune_access_logs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete AccessLog records older than N days, optionally narrowed to a
specific host, client, and/or artifact name.

Intended to be run periodically via cron to keep the access log table
from growing unbounded, but also useful interactively once a subset of
records has been identified by eye (e.g. in the admin) and needs
clearing regardless of age. Operates in a single DELETE query.

--host/--client/--name are independent filters, combined with AND when
more than one is given, and apply on top of whichever age constraint is
in effect (--days, the PRUNE_ACCESS_LOG_DAYS setting, or --all). --all
only overrides the age constraint (same as today) -- it does not bypass
--host/--client/--name.

Examples
--------
Delete records older than 90 days (default):
    ophix-manage prune_access_logs

Delete records older than 30 days:
    ophix-manage prune_access_logs --days 30

Delete all records:
    ophix-manage prune_access_logs --all

Delete every record for a specific client, regardless of age:
    ophix-manage prune_access_logs --all --client cred-client-01

Delete records older than 30 days for one artifact on one host:
    ophix-manage prune_access_logs --days 30 --host dbhost01 --name DB_PASSWORD

Preview how many records would be removed without deleting:
    ophix-manage prune_access_logs --dry-run
    ophix-manage prune_access_logs --days 30 --dry-run
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Delete AccessLog records older than N days (default: PRUNE_ACCESS_LOG_DAYS "
        "setting, or 90), optionally narrowed by --host/--client/--name."
    )

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
            help="Delete regardless of age. Overrides --days and PRUNE_ACCESS_LOG_DAYS "
                 "only -- still narrowed by --host/--client/--name if given.",
        )
        parser.add_argument(
            "--host",
            type=str,
            default=None,
            metavar="NAME",
            help="Only delete records for this host (matched by Host.name).",
        )
        parser.add_argument(
            "--client",
            type=str,
            default=None,
            metavar="NAME",
            help="Only delete records for this client (matched by Client.name).",
        )
        parser.add_argument(
            "--name",
            type=str,
            default=None,
            metavar="NAME",
            help="Only delete records for this artifact, matched against the "
                 "snapshotted artifact name -- works across every domain, since "
                 "every artifact type has a name.",
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
        host      = options["host"]
        client    = options["client"]
        name      = options["name"]

        if prune_all:
            qs = AccessLog.objects.all()
            qualifier_parts = ["all"]
        else:
            if days is None:
                days = getattr(settings, "PRUNE_ACCESS_LOG_DAYS", 90)
            cutoff = timezone.now() - timedelta(days=days)
            qs = AccessLog.objects.filter(timestamp__lt=cutoff)
            qualifier_parts = [f"older than {days} days"]

        if host:
            qs = qs.filter(host__name=host)
            qualifier_parts.append(f"host='{host}'")
        if client:
            qs = qs.filter(client__name=client)
            qualifier_parts.append(f"client='{client}'")
        if name:
            qs = qs.filter(artifact_name=name)
            qualifier_parts.append(f"name='{name}'")

        qualifier = ", ".join(qualifier_parts)

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
