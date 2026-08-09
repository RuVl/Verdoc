"""Drop the legacy `passport` and `order` tables and forget the apps ever existed.

The transfer in `0002` has been verified on prod, so the old tables are dead weight. This lives in
`sales` rather than in the legacy apps themselves because those apps leave the codebase in the same
commit - a migration inside an uninstalled app would never run.

Deliberately one-way. `RunSQL.noop` reverses to nothing and there is no data to put back: rolling
this release back means restoring the dump taken right before it, exactly as ADR-0003 says.

On a fresh database the tables were never created, so `IF EXISTS` turns the whole thing into a
no-op - the same shape `0002` already has.
"""

from django.db import migrations

LEGACY_APPS = ("passport", "order")

# Children before parents: order_* carry the FKs into passport_*. CASCADE covers whatever else the
# old schema left behind (indexes, sequences, the constraints between these seven tables).
LEGACY_TABLES = (
    "order_downloadlink",
    "order_transaction",
    "order_orderitem",
    "order_order",
    "passport_passportfile",
    "passport_passport",
    "passport_country",
)


def forget_legacy_apps(apps, schema_editor):
    """
    Clear the bookkeeping rows the apps leave behind.

    Django tolerates recorded migrations of an app that is no longer on disk - they are simply not
    in the graph - but they keep showing up in the table forever, and the content types keep
    generating permissions in the admin. Deleting the ContentType rows takes their auth_permission
    rows with them through the ORM collector.
    """

    content_type = apps.get_model("contenttypes", "ContentType")
    content_type.objects.filter(app_label__in=LEGACY_APPS).delete()

    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DELETE FROM django_migrations WHERE app = ANY(%s)", [list(LEGACY_APPS)])


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0005_allocation_download_count_and_more"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunSQL(
            [f"DROP TABLE IF EXISTS {table} CASCADE" for table in LEGACY_TABLES],
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunPython(forget_legacy_apps, migrations.RunPython.noop),
    ]
