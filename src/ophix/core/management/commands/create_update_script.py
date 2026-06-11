"""
ophix-manage create_update_script
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Generate <server_name>-update.sh — a convenience script that runs the full
server upgrade sequence in a single command.

The generated script:
  - Changes to INSTALL_DIR so it can be run from anywhere
  - Activates the venv (safe even if already active)
  - Runs venv-cmds check_updates to discover available updates (skipped
    with a warning if venv-cmds is not installed in the venv)
  - Runs pip install -r updates.txt to apply any updates found
  - Runs ophix-manage apply_updates --include-docs
  - Runs ophix-manage check_updates --quiet to refresh the plugin versions table
  - Runs ophix-manage purge_docs --deleted (skipped if ophix-docs is not installed)
  - Deactivates the venv and prints the systemctl restart command

Paths are baked in at generation time. Re-run this command after moving
the venv or changing INSTALL_DIR.

Template: ophix/core/deploy_templates/update.sh.j2

Usage::

    ophix-manage create_update_script
    ophix-manage create_update_script --output-file /home/ophix/credserver/credserver-update.sh
"""

import stat
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ophix.core.management.commands.generate_config import _render_template, _slugify


class Command(BaseCommand):
    help = "Generate <server_name>-update.sh for running the full upgrade sequence."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-file",
            metavar="PATH",
            help=(
                "Where to write the script. "
                "Default: <server_name>-update.sh in the current directory."
            ),
        )
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress output.",
        )

    def handle(self, *args, **options):
        quiet = options["quiet"]

        manage_path = Path(sys.executable).parent / "ophix-manage"
        if not manage_path.exists():
            raise CommandError(
                f"ophix-manage not found at {manage_path}. "
                "Run this command from the server venv."
            )

        server_name = getattr(settings, "SERVER_NAME", "ophix")

        # SERVICE_NAME is written to .env by run_install. Fall back to slugifying
        # SERVER_NAME for installs that pre-date that feature.
        service_name = getattr(settings, "SERVICE_NAME", "").strip()
        if not service_name:
            service_name = _slugify(server_name) if server_name else server_name

        install_dir = getattr(settings, "INSTALL_DIR", None)

        output_file = options.get("output_file")
        if output_file:
            script_path = Path(output_file).resolve()
        else:
            script_path = Path.cwd() / f"{server_name}-update.sh"

        ctx = {
            "manage_path": str(manage_path),
            "venv_path": sys.prefix,
            "server_name": server_name,
            "service_name": service_name,
            "install_dir": str(install_dir) if install_dir else str(Path.cwd()),
            "script_path": str(script_path),
        }

        content = _render_template("update.sh.j2", ctx)

        script_path.write_text(content, encoding="utf-8")
        script_path.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)

        if not quiet:
            self.stdout.write(self.style.SUCCESS(f"Generated: {script_path}"))
            self.stdout.write("")
            self.stdout.write("Run this script after any package update. Then restart the service:")
            self.stdout.write(self.style.WARNING(f"    sudo systemctl restart {service_name}"))
