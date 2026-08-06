from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0004_alter_allocation_stock_item"),
    ]

    operations = [
        migrations.AddField(
            model_name="allocation",
            name="download_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="allocation",
            name="first_downloaded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="allocation",
            name="last_downloaded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
