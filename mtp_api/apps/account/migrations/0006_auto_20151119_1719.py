# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0005_auto_20151118_1440'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Balance',
        ),
    ]
