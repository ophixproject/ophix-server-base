"""
ophix.core.management.commands.run_uninstall
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Generate or display the uninstall script for an Ophix server.

Reads .<server_name>.conf and either prints the sudo uninstall commands
or (re)generates the <server_name>_sudo_uninstall.sh file in INSTALL_DIR.

The data directory is never removed automatically — this must be a
deliberate manual step.

Usage::

    ophix-manage run_uninstall credserver
    ophix-manage run_uninstall credserver --print
"""

import configparser
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ophix.core.management.commands.generate_deploy_config import _slugify
from ophix.core.management.commands.run_install import (
    _SUDO_UNINSTALL_TEMPLATE,
    _render_inline,
)


class Command(BaseCommand):
    help = (
        "Regenerate the sudo uninstall script from .<server_name>.conf, "
        "or print the uninstall commands."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "server_name",
            help="Server slug (e.g. credserver)",
        )
        parser.add_argument(
            "--print", dest="print_only", action="store_true",
            help="Print the uninstall commands to stdout instead of writing a file",
        )

    def handle(self, *args, **options):
        server_name = options["server_name"].lower().strip()
        conf_path = Path.cwd() / f".{server_name}.conf"

        if not conf_path.exists():
            raise CommandError(
                f"Configuration file not found: {conf_path}\n"
                f"Run: ophix-manage configure_install {server_name}"
            )

        conf = configparser.ConfigParser()
        conf.read(str(conf_path))

        def _get(section, key, fallback=""):
            return conf.get(section, key, fallback=fallback)

        install_dir = Path(_get("server", "install_dir") or str(Path.cwd()))
        slug = _slugify(server_name)

        ctx = {
            "server_name": server_name,
            "slug":        slug,
            "install_dir": str(install_dir),
        }

        content = _render_inline(_SUDO_UNINSTALL_TEMPLATE, ctx)

        if options["print_only"]:
            self.stdout.write(content)
            return

        script_path = install_dir / f"{slug}_sudo_uninstall.sh"
        script_path.write_text(content, encoding="utf-8")
        try:
            script_path.chmod(0o755)
        except OSError:
            pass
        self.stdout.write(self.style.SUCCESS(f"Written: {script_path}\n\n"))
        self.stdout.write("To uninstall, run as root:\n\n")
        self.stdout.write(f"  sudo bash {script_path}\n\n")
        self.stdout.write(
            self.style.WARNING(
                f"Note: this removes the systemd service and nginx config only.\n"
                f"The install directory ({install_dir}) is NOT removed automatically.\n"
            )
        )
