from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ophix_core", "0005_host_ipv6_address"),
    ]

    operations = [
        migrations.AlterField(
            model_name="packageupdaterecord",
            name="notice",
            field=models.TextField(
                blank=True,
                help_text="Package release notes read from OPHIX_RELEASE_NOTES.md at last check.",
                verbose_name="release notes",
            ),
        ),
        migrations.AlterModelOptions(
            name="packageupdaterecord",
            options={
                "ordering": ("package_name",),
                "verbose_name": "Plugin",
                "verbose_name_plural": "Plugin Versions",
            },
        ),
    ]
