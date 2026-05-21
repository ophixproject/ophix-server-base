"""
ophix-manage apply_updates
~~~~~~~~~~~~~~~~~~~~~~~~~~
Convenience command that runs the standard post-upgrade sequence in order:

    1. migrate
    2. collectstatic --noinput
    3. generate_deploy_config --append   (updates SERVER_VERSION, adds new .env keys)

Then prints a reminder to restart the systemd service.

Run this after `pip install --upgrade` whenever any Ophix plugin was among
the updated packages.
"""

from django.conf import settings
from django.core import management
from django.core.management.base import BaseCommand

from ophix.core.management.commands.generate_deploy_config import _slugify


class Command(BaseCommand):
    help = "Run migrate, collectstatic, and generate_deploy_config --append after an upgrade."

    def handle(self, *args, **options):
        verbosity = options["verbosity"]

        self.stdout.write(self.style.MIGRATE_HEADING("=== migrate ==="))
        management.call_command("migrate", verbosity=verbosity)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("=== collectstatic ==="))
        management.call_command("collectstatic", interactive=False, verbosity=verbosity)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("=== generate_deploy_config --append ==="))
        management.call_command("generate_deploy_config", append=True, verbosity=verbosity)

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
