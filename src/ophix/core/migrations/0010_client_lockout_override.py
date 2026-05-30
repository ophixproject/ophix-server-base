from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ophix_core", "0009_client_rotation_required"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="lockout_override",
            field=models.BooleanField(
                default=False,
                verbose_name="lockout override",
                help_text=(
                    "Set by the token-policy Unlock action. Allows a locked-out client to "
                    "authenticate once so it can rotate its token. Cleared automatically on "
                    "successful token rotation."
                ),
            ),
        ),
    ]
