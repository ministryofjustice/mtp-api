# Generated by Django 2.2.22 on 2021-05-18 16:57

from django.db import migrations, models


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('payment', '0023_add_index_to_payment_on_card_fields'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='billingaddress',
                    name='postcode',
                    field=models.CharField(blank=True, db_index=True, max_length=250, null=True),
                ),
            ],

            database_operations=[
                migrations.RunSQL(
                    'CREATE INDEX CONCURRENTLY "payment_billingaddress_postcode_414d3f10" '
                    'ON "payment_billingaddress" ("postcode");',
                    reverse_sql='DROP INDEX "payment_billingaddress_postcode_414d3f10";',
                ),
                migrations.RunSQL(
                    'CREATE INDEX CONCURRENTLY "payment_billingaddress_postcode_414d3f10_like" '
                    'ON "payment_billingaddress" ("postcode" varchar_pattern_ops);',
                    reverse_sql='DROP INDEX "payment_billingaddress_postcode_414d3f10_like";',
                ),
            ],
        )
    ]
