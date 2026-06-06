"""
0002_hash_client_tokens

Data-only migration: hash all existing Client.api_token values with SHA-256.

No schema change — CharField(max_length=64) holds a 64-char SHA-256 hex
digest exactly as it held a 64-char hex token. The DB column type is unchanged.

After this migration existing fleet clients continue working without any
reconfiguration: they still send their plaintext token; the server now hashes
on lookup before comparing to the stored digest.

The state operation also reflects the renamed verbose_name and changed default
callable on the api_token field.
"""

import hashlib

from django.db import migrations, models
import ophix.core.models


def hash_existing_tokens(apps, schema_editor):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, api_token FROM ophix_core_client")
        rows = cursor.fetchall()

    if not rows:
        return

    with connection.cursor() as cursor:
        for pk, token in rows:
            digest = hashlib.sha256(token.encode()).hexdigest()
            cursor.execute(
                "UPDATE ophix_core_client SET api_token = %s WHERE id = %s",
                [digest, pk],
            )


class Migration(migrations.Migration):

    dependencies = [
        ("ophix_core", "0001_initial"),
    ]

    operations = [
        # State-only: reflect verbose_name + default callable change.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="client",
                    name="api_token",
                    field=models.CharField(
                        default=ophix.core.models._default_api_token,
                        max_length=64,
                        unique=True,
                        verbose_name="API token (SHA-256 hash)",
                    ),
                ),
            ],
            database_operations=[],
        ),
        # Data migration: hash all existing tokens.
        migrations.RunPython(
            hash_existing_tokens,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
