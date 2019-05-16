# Generated by Django 2.0.13 on 2019-04-29 14:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0009_auto_20190402_1201'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['-triggered_at', 'id'], name='notificatio_trigger_ccb935_idx'),
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['rule'], name='notificatio_rule_0b334e_idx'),
        ),
    ]