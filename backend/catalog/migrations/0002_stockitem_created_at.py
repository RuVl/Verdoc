import django.utils.timezone
from django.db import migrations, models


def blank_out_existing(apps, schema_editor):
    """
    AddField stamps every existing row with the field default, i.e. the moment of the migration.

    That date would be a lie: nobody knows when those units were actually put in stock. Blank them
    out so the turnover figures are computed over the rows that carry a real date, and NULL reads
    as "predates the field" rather than "arrived on deploy day".
    """

    apps.get_model("catalog", "StockItem").objects.update(created_at=None)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockitem",
            name="created_at",
            field=models.DateTimeField(blank=True, default=django.utils.timezone.now, editable=False, null=True),
        ),
        migrations.RunPython(blank_out_existing, migrations.RunPython.noop),
    ]
