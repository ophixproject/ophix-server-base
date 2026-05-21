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

Release notes are read from an ``OPHIX_RELEASE_NOTES.md`` file in each
package's installed directory, if present, and stored in the notice field.

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
from importlib.util import find_spec
from pathlib import Path

from packaging.version import Version, InvalidVersion

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.translation import gettext as _

from ophix.core.management.commands.list_ophix_plugins import (
    _get_plugin_version,
    ENTRY_POINT_GROUP,
)

# Internal status tokens — plain strings used for logic and comparison.
# Translated labels are applied only at display time.
_STATUS_OK          = "ok"
_STATUS_UPDATE      = "update"
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


def _format_ophix_version(version: str) -> str:
    """Restore leading zeros stripped by PEP 440 normalisation.

    Our format is always YYYY.MM.DD.NN. pip normalises 2026.05.18.03 to
    2026.5.18.3 — this puts the leading zeros back on the last three parts.
    Passes through unchanged if the string doesn't match the 4-part pattern.
    """
    parts = version.split(".")
    if len(parts) == 4 and parts[0].isdigit() and len(parts[0]) == 4:
        try:
            year, month, day, seq = parts
            return f"{year}.{int(month):02d}.{int(day):02d}.{int(seq):02d}"
        except ValueError:
            pass
    return version


def _compare(installed: str, latest: str) -> str:
    try:
        if Version(latest) > Version(installed):
            return _STATUS_UPDATE
        return _STATUS_OK
    except InvalidVersion:
        return _STATUS_UNKNOWN if installed != latest else _STATUS_OK


def _read_release_notes(module_name: str) -> str:
    """Read OPHIX_RELEASE_NOTES.md from the package's installed directory.

    Returns the file contents stripped of leading/trailing whitespace,
    or an empty string if the file is absent or unreadable.
    """
    try:
        spec = find_spec(module_name)
        if spec and spec.origin:
            notes_file = Path(spec.origin).parent / "OPHIX_RELEASE_NOTES.md"
            if notes_file.exists():
                return notes_file.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


class Command(BaseCommand):
    help = _("Check installed Ophix plugins against the configured pip index and report available updates.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=30,
            metavar="SECONDS",
            help=_("Per-package pip query timeout in seconds (default: 30)."),
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help=_("Suppress table output. Results are still written to the database."),
        )
        parser.add_argument(
            "--prune",
            action="store_true",
            help=_("Remove PackageUpdateRecord rows for packages no longer installed."),
        )

    def handle(self, *args, **options):
        timeout = options["timeout"]
        quiet = options["quiet"]
        prune = options["prune"]

        # --- Collect (plugin_name, pip_name, module_name, installed) rows ----
        rows = []

        # ophix-server-base itself
        try:
            meta = dist_metadata("ophix-server-base")
            pip_name = meta["Name"]
            installed = meta["Version"]
        except Exception:
            pip_name = "ophix-server-base"
            installed = _get_plugin_version("ophix", ep=None)
        rows.append(("ophix-server-base", pip_name, "ophix", installed))

        for ep in sorted(entry_points(group=ENTRY_POINT_GROUP), key=lambda e: e.name):
            pip_name = ep.dist.metadata["Name"] if ep.dist else ep.name
            installed = _get_plugin_version(ep.value, ep)
            rows.append((ep.name, pip_name, ep.value, installed))

        # --- Query pip + read release notes (one package at a time) ----------
        results = []
        total = len(rows)
        for i, (plugin_name, pip_name, module_name, installed) in enumerate(rows, 1):
            self.stderr.write(
                str(_("  Checking %(name)s (%(i)d/%(total)d)...\r")) % {
                    "name": pip_name, "i": i, "total": total,
                },
                ending="",
            )
            self.stderr.flush()

            installed_fmt = _format_ophix_version(installed)
            latest_raw    = _get_latest_version(pip_name, timeout)
            latest_fmt    = _format_ophix_version(latest_raw) if latest_raw else None
            notes         = _read_release_notes(module_name)

            if latest_fmt is None:
                status = _STATUS_UNAVAILABLE
            else:
                status = _compare(installed, latest_raw)

            results.append((plugin_name, pip_name, installed_fmt, latest_fmt or "—", status, notes))

        self.stderr.write(" " * 60 + "\r", ending="")  # clear progress line

        # --- Upsert PackageUpdateRecord rows ---------------------------------
        from ophix.core.models import PackageUpdateRecord
        now = timezone.now()
        for plugin_name, pip_name, installed, latest, status, notes in results:
            PackageUpdateRecord.objects.update_or_create(
                package_name=pip_name,
                defaults={
                    "installed_version": installed,
                    "latest_version": latest if latest != "—" else "",
                    "update_available": status == _STATUS_UPDATE,
                    "last_checked_at": now,
                    "notice": notes,
                },
            )

        # --- Prune stale rows ------------------------------------------------
        if prune:
            known = {pip_name for _, pip_name, _, _, _, _ in results}
            deleted = PackageUpdateRecord.objects.exclude(
                package_name__in=known
            ).delete()[0]
            if deleted and not quiet:
                self.stdout.write(self.style.WARNING(
                    str(_("Removed %(count)d stale package record(s).")) % {"count": deleted}
                ))

        if quiet:
            return

        # --- Translate status tokens for display -----------------------------
        _status_labels = {
            _STATUS_OK:          str(_("OK")),
            _STATUS_UPDATE:      str(_("Update available")),
            _STATUS_UNAVAILABLE: str(_("unavailable")),
            _STATUS_UNKNOWN:     str(_("unknown")),
        }

        # --- Format and print table ------------------------------------------
        col_plugin    = str(_("Plugin"))
        col_package   = str(_("Package"))
        col_installed = str(_("Installed"))
        col_latest    = str(_("Latest"))
        col_status    = str(_("Status"))

        display = [
            (r[0], r[1], r[2], r[3], _status_labels.get(r[4], r[4]), r[4])
            for r in results
        ]

        w_plugin    = max(len(col_plugin),    max(len(r[0]) for r in display))
        w_package   = max(len(col_package),   max(len(r[1]) for r in display))
        w_installed = max(len(col_installed), max(len(r[2]) for r in display))
        w_latest    = max(len(col_latest),    max(len(r[3]) for r in display))
        w_status    = max(len(col_status),    max(len(r[4]) for r in display))

        header = (
            f"{col_plugin:<{w_plugin}}  "
            f"{col_package:<{w_package}}  "
            f"{col_installed:<{w_installed}}  "
            f"{col_latest:<{w_latest}}  "
            f"{col_status:<{w_status}}"
        )
        divider = "  ".join([
            "-" * w_plugin, "-" * w_package,
            "-" * w_installed, "-" * w_latest, "-" * w_status,
        ])

        self.stdout.write(header)
        self.stdout.write(divider)

        updates_available = 0
        unavailable = 0
        for plugin_name, pip_name, installed, latest, label, raw_status in display:
            if raw_status == _STATUS_UPDATE:
                updates_available += 1
                styled = self.style.WARNING(label)
            elif raw_status == _STATUS_UNAVAILABLE:
                unavailable += 1
                styled = self.style.NOTICE(label)
            elif raw_status == _STATUS_OK:
                styled = self.style.SUCCESS(label)
            else:
                styled = label

            self.stdout.write(
                f"{plugin_name:<{w_plugin}}  "
                f"{pip_name:<{w_package}}  "
                f"{installed:<{w_installed}}  "
                f"{latest:<{w_latest}}  "
                + styled
            )

        self.stdout.write("")
        if updates_available:
            self.stdout.write(self.style.WARNING(
                str(_("%(count)d update(s) available.")) % {"count": updates_available}
            ))
        else:
            self.stdout.write(self.style.SUCCESS(str(_("All packages are up to date."))))
        if unavailable:
            self.stdout.write(self.style.NOTICE(
                str(_("%(count)d package(s) could not be checked (not found in configured index or index unreachable).")) % {"count": unavailable}
            ))
