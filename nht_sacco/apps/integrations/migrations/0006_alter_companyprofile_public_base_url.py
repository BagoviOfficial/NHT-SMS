# Generated manually for internal public verification URL configuration

from django.db import migrations, models


def clear_legacy_external_public_base_url(apps, schema_editor):
    CompanyProfile = apps.get_model('integrations', 'CompanyProfile')
    CompanyProfile.objects.filter(public_base_url='https://nhtsms.bagovi.com').update(public_base_url='')


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0005_alter_companyprofile_footer_text'),
    ]

    operations = [
        migrations.AlterField(
            model_name='companyprofile',
            name='public_base_url',
            field=models.URLField(
                blank=True,
                default='',
                help_text='Optional base URL for QR compliance verification links; leave blank to use the internal endpoint',
                verbose_name='Public Verification Base URL',
            ),
        ),
        migrations.RunPython(clear_legacy_external_public_base_url, migrations.RunPython.noop),
    ]
