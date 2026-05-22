from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Disabled on Ophix servers."
    hidden = True

    def handle(self, *args, **options):
        raise CommandError(
            "The 'dbshell' command is disabled on Ophix servers for security reasons."
        )
