# Generated by Django 2.0.13 on 2020-02-12 15:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mtp_auth', '0013_roles_have_login_urls'),
    ]

    operations = [
        migrations.CreateModel(
            name='JobInformation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_title', models.CharField(max_length=50)),
                ('prison_location', models.CharField(max_length=50)),
                ('job_tasks', models.CharField(max_length=50)),
            ],
        ),
    ]
