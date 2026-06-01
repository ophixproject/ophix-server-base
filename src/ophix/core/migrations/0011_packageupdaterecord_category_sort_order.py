from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ophix_core", "0010_client_lockout_override"),
    ]

    operations = [
        migrations.AddField(
            model_name="packageupdaterecord",
            name="category",
            field=models.CharField(
                blank=True,
                choices=[
                    ("core", "Core"),
                    ("module", "Module"),
                    ("addon", "Add-on"),
                    ("auth", "Authentication"),
                    ("dbengine", "Database Engine"),
                    ("theme", "Theme"),
                    ("language", "Language Pack"),
                ],
                help_text="Plugin category declared by the package (core, module, addon, etc.).",
                max_length=20,
                verbose_name="category",
            ),
        ),
        migrations.AddField(
            model_name="packageupdaterecord",
            name="sort_order",
            field=models.IntegerField(
                default=999,
                help_text="Display order within the plugin list. Declared by the package.",
                verbose_name="sort order",
            ),
        ),
        migrations.AlterModelOptions(
            name="packageupdaterecord",
            options={
                "ordering": ("sort_order", "package_name"),
                "verbose_name": "Plugin",
                "verbose_name_plural": "Plugin Versions",
            },
        ),
    ]
