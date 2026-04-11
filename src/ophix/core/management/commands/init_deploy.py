"""
ophix.core.management.commands.init_deploy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Initialise the INSTALL_DIR runtime directory structure for an Ophix server.

Creates the subdirectories that the server needs at runtime and sets ownership
and permissions where the running user has sufficient privileges.  Prints the
equivalent shell commands for any steps that require root.

Usage::

    ophix-manage init_deploy
    ophix-manage init_deploy --install-dir /var/lib/credserver
    ophix-manage init_deploy --dry-run
"""

import os
import stat
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


# ---------------------------------------------------------------------------
# Directory specification
# (relative path, octal mode, note shown in --dry-run output)
# ---------------------------------------------------------------------------

SUBDIRS = [
    ("logs",         0o2770, "service user + nginx/www-data group — shared log access"),
    ("media",        0o2770, "service user + nginx/www-data group — uploaded file access"),
    ("run",          0o2755, "socket directory — readable by nginx"),
    ("ssl",          0o750,  "SSL root — service user only"),
    ("ssl/certs",    0o750,  "certificates — service user only"),
    ("ssl/private",  0o750,  "private keys — service user only"),
]


class Command(BaseCommand):
    help = (
        "Initialise the INSTALL_DIR runtime directory structure "
        "(logs, media, run, ssl). Prints sudo commands for steps requiring root."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--install-dir", metavar="DIR",
            help=(
                "Override INSTALL_DIR from settings. "
                "Defaults to the INSTALL_DIR setting from .env."
            ),
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Print what would be done without making any changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # Resolve install dir
        if options.get("install_dir"):
            install_dir = Path(options["install_dir"])
        else:
            install_dir = getattr(settings, "INSTALL_DIR", None)
            if not install_dir:
                raise CommandError(
                    "INSTALL_DIR is not set. Either set it in .env or pass --install-dir."
                )
            install_dir = Path(install_dir)

        self.stdout.write(f"\nInitialising deploy directory: {install_dir}\n")
        if dry_run:
            self.stdout.write(self.style.WARNING("  Dry-run mode — no changes will be made.\n"))
        self.stdout.write("\n")

        # Create top-level install dir
        self._ensure_dir(install_dir, None, dry_run)

        # Create each subdir
        for rel, mode, note in SUBDIRS:
            self._ensure_dir(install_dir / rel, mode, dry_run, note=note)

        self.stdout.write("\n")

        # Print post-creation ownership guidance
        self._print_ownership_guide(install_dir, dry_run)

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS("\nDirectory structure ready.\n")
            )
            self.stdout.write(
                "Next: set ownership (see commands above), place SSL certificates, "
                "then run:\n"
                "  ophix-manage migrate\n"
                "  ophix-manage collectstatic --noinput\n"
                "  ophix-manage createsuperuser\n"
            )

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _ensure_dir(self, path: Path, mode: int | None, dry_run: bool, note: str = "") -> None:
        note_str = f"  # {note}" if note else ""
        mode_str = oct(mode) if mode is not None else ""

        if dry_run:
            action = "exists" if path.exists() else "create"
            self.stdout.write(
                f"  [{action:6}] {path}{note_str}\n"
            )
            if mode is not None:
                self.stdout.write(f"           chmod {oct(mode)[2:]}  {path}\n")
            return

        created = False
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
                created = True
            except PermissionError:
                self.stdout.write(
                    self.style.ERROR(f"  FAILED (permission denied): {path}\n")
                    + f"  Run manually: sudo mkdir -p {path}\n"
                )
                return

        if mode is not None:
            try:
                path.chmod(mode)
            except PermissionError:
                self.stdout.write(
                    self.style.WARNING(f"  Cannot chmod {path} — run manually: sudo chmod {oct(mode)[2:]} {path}\n")
                )

        label = "Created" if created else "Exists "
        self.stdout.write(
            self.style.SUCCESS(f"  {label}: {path}")
            + (f"  ({note})" if note else "")
            + "\n"
        )

    def _print_ownership_guide(self, install_dir: Path, dry_run: bool) -> None:
        """Print the chown commands the operator needs to run as root."""
        prefix = "[would run] " if dry_run else ""
        self.stdout.write("Ownership — run these as root after directory creation:\n\n")

        # Top-level and most dirs: service user owns everything
        self.stdout.write(
            f"  # Replace <service-user> and <service-group> with your values\n"
            f"  # (e.g. ophix:ophix, or ophix:www-data if nginx needs shared access)\n\n"
            f"  {prefix}sudo chown -R <service-user>:<service-group> {install_dir}\n\n"
        )

        # Shared dirs that nginx also needs to read
        for rel in ("logs", "media", "run"):
            p = install_dir / rel
            self.stdout.write(
                f"  # {rel}/ — nginx user needs read access for logs/media/socket\n"
                f"  {prefix}sudo chown <service-user>:<nginx-group> {p}\n"
                f"  {prefix}sudo chmod 2770 {p}\n\n"
            )

        # SSL — service user only
        self.stdout.write(
            f"  # ssl/ — private keys must NOT be readable by nginx\n"
            f"  {prefix}sudo chown -R <service-user>:<service-group> {install_dir / 'ssl'}\n"
            f"  {prefix}sudo chmod 750 {install_dir / 'ssl'}\n"
            f"  {prefix}sudo chmod 750 {install_dir / 'ssl' / 'certs'}\n"
            f"  {prefix}sudo chmod 750 {install_dir / 'ssl' / 'private'}\n\n"
        )

        # SSL cert/key permissions once placed
        self.stdout.write(
            f"  # Once SSL files are placed:\n"
            f"  {prefix}sudo chmod 644 {install_dir / 'ssl' / 'certs' / '<slug>.crt'}\n"
            f"  {prefix}sudo chmod 640 {install_dir / 'ssl' / 'private' / '<slug>.key'}\n"
        )
