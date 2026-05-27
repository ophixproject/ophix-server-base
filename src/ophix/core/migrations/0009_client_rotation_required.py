from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ophix_core", "0008_packageupdaterecord_first_recorded_at_helptext"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="rotation_required",
            field=models.BooleanField(default=False, verbose_name="rotation required"),
        ),
    ]
