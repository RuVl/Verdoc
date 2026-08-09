import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    AddField stamps every existing row with the field default, i.e. the moment of the migration.

    That is not when those units actually arrived - nobody knows that - but it is the day from
    which their age is measurable, and it keeps the column non-nullable so no figure needs an
    "unknown" bucket. Reversing this drops the column and the dates with it.
    """

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockitem",
            name="created_at",
            field=models.DateTimeField(default=django.utils.timezone.now, editable=False),
        ),
    ]
