# Generated by Django 2.0.13 on 2020-08-10 14:36

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_token'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Token',
        ),
    ]