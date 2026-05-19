from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_package_update_record"),
    ]

    operations = [
        # Allow ipv4_address to be null so IPv6-only hosts are valid.
        migrations.AlterField(
            model_name="host",
            name="ipv4_address",
            field=models.GenericIPAddressField(
                blank=True,
                null=True,
                protocol="IPv4",
                unique=True,
                verbose_name="IPv4 address",
            ),
        ),
        migrations.AddField(
            model_name="host",
            name="ipv6_address",
            field=models.GenericIPAddressField(
                blank=True,
                null=True,
                protocol="IPv6",
                unique=True,
                verbose_name="IPv6 address",
            ),
        ),
    ]
