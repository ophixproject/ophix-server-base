from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):

    dependencies = [
        ("ophix_core", "0011_packageupdaterecord_category_sort_order"),
    ]

    operations = [
        migrations.AlterField(
            model_name="packageupdaterecord",
            name="latest_version",
            field=models.CharField(
                blank=True,
                max_length=100,
                verbose_name=_("latest version"),
            ),
        ),
        migrations.AlterField(
            model_name="packageupdaterecord",
            name="category",
            field=models.CharField(
                blank=True,
                choices=[
                    ("core", _("Core")),
                    ("module", _("Module")),
                    ("addon", _("Add-on")),
                    ("auth", _("Authentication")),
                    ("dbengine", _("Database Engine")),
                    ("theme", _("Theme")),
                    ("language", _("Language Pack")),
                ],
                max_length=20,
                verbose_name=_("category"),
            ),
        ),
    ]
