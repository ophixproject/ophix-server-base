"""
ophix-manage apply_updates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Convenience command that runs the standard post-upgrade sequence in order:

    1. migrate
    2. collectstatic --noinput
    3. generate_config --append   (updates SERVER_VERSION, adds new .env keys)
    4. update_docs  (optional, --include-docs)

Then prints a reminder to restart the systemd service.

Run this after `pip install --upgrade` whenever any Ophix plugin was among
the updated packages.
"""

from importlib.metadata import entry_points
from importlib.util import find_spec
from pathlib import Path

from django.conf import settings
from django.core import management
from django.core.management.base import BaseCommand

from ophix.core.management.commands.generate_config import _slugify


def _modules_with_docs():
    """Return a list of module names that have a docs/ directory."""
    modules = []

    # ophix.core is not an entry point but always checked first
    spec = find_spec("ophix.core")
    if spec and spec.origin:
        if (Path(spec.origin).parent / "docs").exists():
            modules.append("ophix.core")

    for ep in entry_points(group="ophix.plugins"):
        module_name = ep.value
        spec = find_spec(module_name)
        if spec and spec.origin:
            if (Path(spec.origin).parent / "docs").exists():
                modules.append(module_name)

    return modules


class Command(BaseCommand):
    help = "Run migrate, collectstatic, and generate_config --append after an upgrade."

    def add_arguments(self, parser):
        parser.add_argument(
            "--include-docs",
            action="store_true",
            default=False,
            help="Also run update_docs for all installed modules that have a docs/ directory.",
        )

    def handle(self, *args, **options):
        verbosity = options["verbosity"]

        self.stdout.write(self.style.MIGRATE_HEADING("=== migrate ==="))
        management.call_command("migrate", verbosity=verbosity)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("=== collectstatic ==="))
        management.call_command("collectstatic", interactive=False, verbosity=verbosity)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("=== generate_config --append ==="))
        management.call_command("generate_config", append=True, verbosity=verbosity)

        if options["include_docs"]:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("=== update_docs ==="))
            modules = _modules_with_docs()
            if modules:
                self.stdout.write(f"Modules: {', '.join(modules)}")
                management.call_command(
                    "update_docs",
                    include_app_docs=",".join(modules),
                    verbosity=verbosity,
                )
            else:
                self.stdout.write(self.style.WARNING("No modules with docs/ directories found."))

        # SERVICE_NAME is written to .env by run_install. Fall back to
        # slugifying SERVER_NAME for installs that pre-date this feature.
        service_name = getattr(settings, "SERVICE_NAME", "").strip()
        if not service_name:
            server_name = getattr(settings, "SERVER_NAME", "").strip()
            service_name = _slugify(server_name) if server_name else None

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Updates applied."))
        self.stdout.write("Review .env for any new variables added above, then restart the service:")
        if service_name:
            self.stdout.write(self.style.WARNING(f"    sudo systemctl restart {service_name}"))
        else:
            self.stdout.write(self.style.WARNING("    sudo systemctl restart <service-name>"))
