"""
ophix-manage check_ophix_updates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Check all installed Ophix plugins against the configured pip index and
report whether newer versions are available.

Uses ``pip index versions`` under the hood, so every pip source configured
for this environment (local mirror, private index, PyPI, etc.) is respected
automatically.  No extra network configuration is needed.

Results are stored in the PackageUpdateRecord table and optionally displayed
on screen.  Use --quiet to suppress output (suitable for cron jobs).

Examples
--------
    ophix-manage check_ophix_updates
    ophix-manage check_ophix_updates --timeout 60
    ophix-manage check_ophix_updates --quiet   # cron-friendly, DB only
"""

import re
import subprocess
import sys
from importlib.metadata import entry_points, metadata as dist_metadata

from packaging.version import Version, InvalidVersion

from django.core.management.base import BaseCommand
from django.utils import timezone

from ophix.core.management.commands.list_ophix_plugins import (
    _get_plugin_version,
    ENTRY_POINT_GROUP,
)

_STATUS_OK          = "OK"
_STATUS_UPDATE      = "UPDATE AVAILABLE"
_STATUS_UNAVAILABLE = "unavailable"
_STATUS_UNKNOWN     = "unknown"


def _get_latest_version(pip_name: str, timeout: int) -> str | None:
    """
    Ask pip for the available versions of *pip_name* and return the newest.

    Returns None if the index cannot be reached or the package is not listed.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "index", "versions", pip_name],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        match = re.search(r"Available versions:\s*(.+)", result.stdout)
        if match:
            versions = [v.strip() for v in match.group(1).split(",") if v.strip()]
            return versions[0] if versions else None
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    return None


def _compare(installed: str, latest: str) -> str:
    try:
        if Version(latest) > Version(installed):
            return _STATUS_UPDATE
        return _STATUS_OK
    except InvalidVersion:
        return _STATUS_UNKNOWN if installed != latest else _STATUS_OK


class Command(BaseCommand):
    help = (
        "Check all installed Ophix plugins against the configured pip index "
        "and report whether newer versions are available."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=30,
            metavar="SECONDS",
            help="Per-package pip query timeout in seconds (default: 30).",
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress table output. Results are still written to the database.",
        )

    def handle(self, *args, **options):
        timeout = options["timeout"]
        quiet = options["quiet"]

        # --- Collect (plugin_name, pip_package, installed_version) rows -----
        rows = []

        # ophix-server-base itself
        try:
            meta = dist_metadata("ophix-server-base")
            pip_name = meta["Name"]
            installed = meta["Version"]
        except Exception:
            pip_name = "ophix-server-base"
            installed = _get_plugin_version("ophix", ep=None)
        rows.append(("ophix-server-base", pip_name, installed))

        for ep in sorted(entry_points(group=ENTRY_POINT_GROUP), key=lambda e: e.name):
            pip_name = ep.dist.metadata["Name"] if ep.dist else ep.name
            installed = _get_plugin_version(ep.value, ep)
            rows.append((ep.name, pip_name, installed))

        # --- Query pip for latest versions (one at a time) -------------------
        results = []
        total = len(rows)
        for i, (plugin_name, pip_name, installed) in enumerate(rows, 1):
            self.stderr.write(f"  Checking {pip_name} ({i}/{total})...\r", ending="")
            self.stderr.flush()
            latest = _get_latest_version(pip_name, timeout)
            if latest is None:
                status = _STATUS_UNAVAILABLE
            else:
                status = _compare(installed, latest)
            results.append((plugin_name, pip_name, installed, latest or "—", status))

        self.stderr.write(" " * 60 + "\r", ending="")  # clear progress line

        # --- Upsert PackageUpdateRecord rows ---------------------------------
        from ophix.core.models import PackageUpdateRecord
        now = timezone.now()
        for plugin_name, pip_name, installed, latest, status in results:
            PackageUpdateRecord.objects.update_or_create(
                package_name=pip_name,
                defaults={
                    "installed_version": installed,
                    "latest_version": latest if latest != "—" else "",
                    "update_available": status == _STATUS_UPDATE,
                    "last_checked_at": now,
                },
            )

        if quiet:
            return

        # --- Format and print table ------------------------------------------
        w_plugin    = max(len("Plugin"),    max(len(r[0]) for r in results))
        w_package   = max(len("Package"),   max(len(r[1]) for r in results))
        w_installed = max(len("Installed"), max(len(r[2]) for r in results))
        w_latest    = max(len("Latest"),    max(len(r[3]) for r in results))
        w_status    = max(len("Status"),    max(len(r[4]) for r in results))

        header = (
            f"{'Plugin':<{w_plugin}}  "
            f"{'Package':<{w_package}}  "
            f"{'Installed':<{w_installed}}  "
            f"{'Latest':<{w_latest}}  "
            f"{'Status':<{w_status}}"
        )
        divider = "  ".join([
            "-" * w_plugin,
            "-" * w_package,
            "-" * w_installed,
            "-" * w_latest,
            "-" * w_status,
        ])

        self.stdout.write(header)
        self.stdout.write(divider)

        updates_available = 0
        unavailable = 0
        for plugin_name, pip_name, installed, latest, status in results:
            if status == _STATUS_UPDATE:
                updates_available += 1
                styled_status = self.style.WARNING(status)
            elif status == _STATUS_UNAVAILABLE:
                unavailable += 1
                styled_status = self.style.NOTICE(status)
            elif status == _STATUS_OK:
                styled_status = self.style.SUCCESS(status)
            else:
                styled_status = status

            self.stdout.write(
                f"{plugin_name:<{w_plugin}}  "
                f"{pip_name:<{w_package}}  "
                f"{installed:<{w_installed}}  "
                f"{latest:<{w_latest}}  "
                + styled_status
            )

        self.stdout.write("")
        if updates_available:
            self.stdout.write(self.style.WARNING(
                f"{updates_available} update(s) available."
            ))
        else:
            self.stdout.write(self.style.SUCCESS("All packages are up to date."))
        if unavailable:
            self.stdout.write(self.style.NOTICE(
                f"{unavailable} package(s) could not be checked "
                f"(not found in configured index or index unreachable)."
            ))
