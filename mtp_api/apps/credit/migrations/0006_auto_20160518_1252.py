# -*- coding: utf-8 -*-
# Generated by Django 1.9.4 on 2016-05-18 11:52
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('credit', '0005_auto_20160517_1729'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='credit',
            options={'permissions': (('view_credit', 'Can view credit'), ('lock_credit', 'Can lock credit'), ('unlock_credit', 'Can unlock credit'), ('patch_credited_credit', 'Can patch credited credit'))},
        ),
    ]