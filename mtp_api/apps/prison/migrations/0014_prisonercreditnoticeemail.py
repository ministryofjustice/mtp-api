# Generated by Django 1.10.7 on 2017-06-15 14:29
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('prison', '0013_auto_20170117_1335'),
    ]
    operations = [
        migrations.CreateModel(
            name='PrisonerCreditNoticeEmail',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254)),
                ('prison', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='prison.Prison')),
            ],
            options={
                'ordering': ('prison',),
            },
        ),
    ]
