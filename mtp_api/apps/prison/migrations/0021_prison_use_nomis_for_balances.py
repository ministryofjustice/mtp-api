# Generated by Django 2.0.13 on 2020-10-23 11:15

from django.db import migrations, models


def flag_private_estate_as_not_using_nomis_for_balances(apps, schema_editor):
    prison_cls = apps.get_model('prison', 'Prison')
    prison_cls.objects.filter(private_estate=True).update(use_nomis_for_balances=False)


class Migration(migrations.Migration):

    dependencies = [
        ('prison', '0020_auto_20201020_1229'),
    ]

    operations = [
        migrations.AddField(
            model_name='prison',
            name='use_nomis_for_balances',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(
            flag_private_estate_as_not_using_nomis_for_balances,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
