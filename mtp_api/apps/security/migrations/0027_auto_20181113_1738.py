# Generated by Django 2.0.8 on 2018-11-13 17:38

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('security', '0026_auto_20181106_1641'),
    ]

    operations = [
        migrations.AddField(
            model_name='bankaccount',
            name='monitoring_users',
            field=models.ManyToManyField(related_name='monitored_bank_accounts', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='debitcardsenderdetails',
            name='monitoring_users',
            field=models.ManyToManyField(related_name='monitored_debit_cards', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='prisonerprofile',
            name='monitoring_users',
            field=models.ManyToManyField(related_name='monitored_prisoners', to=settings.AUTH_USER_MODEL),
        ),
    ]
