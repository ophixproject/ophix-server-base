from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("ophix_core", "0006_packageupdaterecord_notice_labels"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="packageupdaterecord",
            options={
                "ordering": ("package_name",),
                "verbose_name": "Plugin",
                "verbose_name_plural": "Plugin Versions",
            },
        ),
    ]
