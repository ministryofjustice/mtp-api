# Generated by Django 1.10.5 on 2017-03-01 14:58
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('security', '0010_prisoner_profile_uniqueness'),
        ('credit', '0015_auto_20161214_1603'),
    ]
    operations = [
        migrations.AddField(
            model_name='credit',
            name='prisoner_profile',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='credits', to='security.PrisonerProfile'),
        ),
        migrations.AddField(
            model_name='credit',
            name='sender_profile',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='credits', to='security.SenderProfile'),
        ),
    ]
