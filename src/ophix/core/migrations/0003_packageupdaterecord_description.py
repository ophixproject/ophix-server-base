from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ophix_core", "0002_hash_client_tokens"),
    ]

    operations = [
        migrations.AddField(
            model_name="packageupdaterecord",
            name="description",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Package summary from importlib.metadata, populated by check_updates.",
                verbose_name="description",
            ),
            preserve_default=False,
        ),
    ]
