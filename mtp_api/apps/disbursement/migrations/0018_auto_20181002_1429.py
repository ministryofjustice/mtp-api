# Generated by Django 2.0.8 on 2018-10-02 13:29

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0017_auto_20180914_1613'),
        ('disbursement', '0017_disbursement_invoice_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='disbursement',
            name='prisoner_profile',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='disbursements', to='security.PrisonerProfile'),
        ),
        migrations.AddField(
            model_name='disbursement',
            name='recipient_profile',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='disbursements', to='security.RecipientProfile'),
        ),
    ]