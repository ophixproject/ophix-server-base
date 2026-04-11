import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ophix_core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccessLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "client",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="ophix_core.client",
                    ),
                ),
                (
                    "host",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="ophix_core.host",
                    ),
                ),
                ("operation", models.CharField(max_length=10)),
                ("artifact_type", models.CharField(max_length=100)),
                ("artifact_name", models.CharField(blank=True, max_length=200)),
                ("artifact_id", models.IntegerField(blank=True, null=True)),
                (
                    "timestamp",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                    ),
                ),
            ],
            options={
                "ordering": ("-timestamp",),
            },
        ),
    ]
