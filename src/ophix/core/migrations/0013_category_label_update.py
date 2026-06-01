from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):

    dependencies = [
        ("ophix_core", "0012_remove_help_text"),
    ]

    operations = [
        migrations.AlterField(
            model_name="packageupdaterecord",
            name="category",
            field=models.CharField(
                blank=True,
                choices=[
                    ("core",     _("Core")),
                    ("module",   _("Module")),
                    ("addon",    _("Add-on")),
                    ("auth",     _("Authentication")),
                    ("dbengine", _("Database")),
                    ("theme",    _("Theme")),
                    ("language", _("Language")),
                ],
                max_length=20,
                verbose_name=_("category"),
            ),
        ),
    ]
