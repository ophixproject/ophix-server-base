"""
ophix-manage create_backup_script
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Generate ophix-backup.sh — a scheduled backup script that exports all server
data to dated JSON files.

The generated script:
  - Lives alongside .env in the directory where this command is run
  - Sources .env at runtime so BACKUP_PATH and BACKUP_PASSPHRASE are read
    from the same place as all other server config
  - Auto-detects which domain exports are available on this server
  - Uses a passphrase for exports that support encryption (when BACKUP_PASSPHRASE
    is set in .env); runs without encryption if the variable is absent or blank
  - Bakes in the ophix-manage path from the running venv so no PATH or
    VENV_NAME configuration is needed

Re-run this command after upgrading or moving the venv to refresh the baked-in
manage path.

Template: ophix/core/deploy_templates/backup.sh.j2

Usage::

    ophix-manage create_backup_script
    ophix-manage create_backup_script --output-file /home/ophix/credserver/credserver-backup.sh
"""

import stat
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ophix.core.management.commands.generate_config import _render_template


class Command(BaseCommand):
    help = "Generate ophix-backup.sh for scheduled server backups."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-file",
            metavar="PATH",
            help=(
                "Where to write the script. "
                "Default: ophix-backup.sh in the current directory."
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

        output_file = options.get("output_file")
        if output_file:
            script_path = Path(output_file).resolve()
        else:
            script_path = Path.cwd() / f"{server_name}-backup.sh"

        ctx = {
            "manage_path": str(manage_path),
            "server_name": server_name,
            "script_path": str(script_path),
        }

        content = _render_template("backup.sh.j2", ctx)

        script_path.write_text(content, encoding="utf-8")
        script_path.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)

        if not quiet:
            self.stdout.write(self.style.SUCCESS(f"Generated: {script_path}"))
            self.stdout.write("")

            # Derive a sensible BACKUP_PATH suggestion from INSTALL_DIR:
            # /home/user/ophix/taskserver  →  /home/user/ophix/backups/taskserver
            install_dir = getattr(settings, "INSTALL_DIR", None)
            if install_dir:
                suggested_backup_path = install_dir.parent / "backups" / install_dir.name
            else:
                suggested_backup_path = Path("/path/to/backup/directory")

            env_file = script_path.parent / ".env"
            missing = []
            if env_file.exists():
                env_text = env_file.read_text(encoding="utf-8")
                if "BACKUP_PATH" not in env_text:
                    missing.append(f"BACKUP_PATH={suggested_backup_path}")
                if "BACKUP_TARGETS" not in env_text:
                    missing.append("BACKUP_TARGETS=hosts,clients,settings")
                if "BACKUP_TARGETS_ENCRYPTED" not in env_text:
                    missing.append(
                        "BACKUP_TARGETS_ENCRYPTED=  "
                        "# see the backup docs for your domain"
                    )
                if "BACKUP_PASSPHRASE" not in env_text:
                    missing.append("BACKUP_PASSPHRASE=your-passphrase")
            else:
                missing = [
                    f"BACKUP_PATH={suggested_backup_path}",
                    "BACKUP_TARGETS=hosts,clients,settings",
                    "BACKUP_TARGETS_ENCRYPTED=  "
                    "# see the backup docs for your domain",
                    "BACKUP_PASSPHRASE=your-passphrase",
                ]

            if missing:
                self.stdout.write("Add to .env:")
                for line in missing:
                    self.stdout.write(f"  {line}")
                self.stdout.write("")

            self.stdout.write("Suggested cron entry (daily at 02:00):")
            self.stdout.write(f"  0 2 * * * {script_path} --compress >> /var/log/ophix-backup.log 2>&1")
