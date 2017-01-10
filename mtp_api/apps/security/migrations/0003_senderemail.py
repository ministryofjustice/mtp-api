# -*- coding: utf-8 -*-
# Generated by Django 1.9.12 on 2017-01-10 11:38
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0002_profile_verbose_names'),
    ]

    operations = [
        migrations.CreateModel(
            name='SenderEmail',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.CharField(max_length=250)),
                ('debit_card_sender_details', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sender_emails', related_query_name='sender_email', to='security.DebitCardSenderDetails')),
            ],
        ),
    ]
