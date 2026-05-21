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

        server_name = getattr(settings, "SERVER_NAME", "").strip()
        slug = _slugify(server_name) if server_name else None

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Updates applied. Restart the service to complete the upgrade:"))
        if slug:
            self.stdout.write(self.style.WARNING(f"    sudo systemctl restart {slug}"))
        else:
            self.stdout.write(self.style.WARNING("    sudo systemctl restart <service-name>"))
