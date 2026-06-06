from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ophix_core", "0007_packageupdaterecord_verbose_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="packageupdaterecord",
            name="first_recorded_at",
            field=models.DateTimeField(
                auto_now_add=True,
                verbose_name="first recorded",
                help_text="When this package was first seen by check_updates.",
            ),
        ),
    ]
