# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-11-22 16:42
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('credit', '0012_creditingtime'),
    ]

    operations = [
        migrations.AddField(
            model_name='credit',
            name='blocked',
            field=models.BooleanField(default=False),
        ),
    ]