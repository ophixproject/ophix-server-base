from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ophix_core', '0003_alter_accesslog_options_alter_client_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PackageUpdateRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('package_name', models.CharField(max_length=200, unique=True, verbose_name='package name')),
                ('installed_version', models.CharField(max_length=100, verbose_name='installed version')),
                ('latest_version', models.CharField(
                    blank=True,
                    help_text='Blank when the package could not be found in the configured index.',
                    max_length=100,
                    verbose_name='latest version',
                )),
                ('update_available', models.BooleanField(default=False, verbose_name='update available')),
                ('first_recorded_at', models.DateTimeField(
                    auto_now_add=True,
                    help_text='When this package was first seen by check_ophix_updates.',
                    verbose_name='first recorded',
                )),
                ('last_checked_at', models.DateTimeField(blank=True, null=True, verbose_name='last checked')),
                ('notice', models.TextField(
                    blank=True,
                    help_text='Optional operator note or notice from the Ophix Project.',
                    verbose_name='notice',
                )),
            ],
            options={
                'verbose_name': 'Package Update Record',
                'verbose_name_plural': 'Package Update Records',
                'ordering': ('package_name',),
            },
        ),
    ]
