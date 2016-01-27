# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-01-26 15:59
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transaction', '0023_transaction_payment_outcome'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='transaction',
            name='payment_outcome',
        ),
        migrations.AlterField(
            model_name='transaction',
            name='category',
            field=models.CharField(choices=[('debit', 'Debit'), ('credit', 'Credit'), ('non_payment_credit', 'Non-payment credit'), ('online_credit', 'Online credit')], max_length=50),
        ),
    ]
