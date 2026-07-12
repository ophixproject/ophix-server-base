"""
0004_rename_api_token_to_token_hash

Renames Client.api_token to Client.token_hash.

The field has stored a SHA-256 hash (not a live credential) since migration
0002. The field name was never updated to reflect that, which left export
files and admin UI with no visual cue that the value is a hash rather than
a usable token. This migration is a plain column rename (RenameField issues
ALTER TABLE ... RENAME COLUMN) — no data transformation, existing values are
preserved as-is.

Fleet clients are unaffected: they never read this field, they only ever
send their plaintext token in the Authorization header, which the server
hashes on lookup before comparing against the (renamed) column.
"""

from django.db import migrations, models
import ophix.core.models


class Migration(migrations.Migration):

    dependencies = [
        ("ophix_core", "0003_packageupdaterecord_description"),
    ]

    operations = [
        migrations.RenameField(
            model_name="client",
            old_name="api_token",
            new_name="token_hash",
        ),
        migrations.AlterField(
            model_name="client",
            name="token_hash",
            field=models.CharField(
                default=ophix.core.models._default_api_token,
                max_length=64,
                unique=True,
                verbose_name="token hash (SHA-256)",
            ),
        ),
    ]
