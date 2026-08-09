"""Move everything from the legacy `passport` and `order` apps onto the new schema.

One RunPython on purpose: half-transferred data is worse than none. The legacy tables are only
read here - they stay in place until the transfer is verified on prod and are dropped by a
separate release.

Two things are reconstructed rather than copied, see docs/db-refactoring/data-migration-plan.md:

- the file/order link, which simply did not exist before payment. Units of one product are
  interchangeable, so it is restored by assignment: exact links first (DownloadLink), then leftover
  SOLD files to paid items that are short (this repairs the "sold without a link" rows), then
  RESERVED files to items of pending orders;
- historical prices, which were never stored. Snapshots get today's catalog price, so the
  sum(unit_price_usd * quantity) == total_price invariant only holds for orders made after cutover.

Primary keys of orders are preserved: Plisio invoices carry order_number = Order.id, and callbacks
for invoices issued before the cutover will still arrive with the old numbers. Sequences are reset
afterwards.

Nothing here requires the legacy apps to be installed. Once they are dropped, every lookup below
misses, the migration turns into a no-op and a fresh database can still be built from zero - which
is the whole point of keeping it applyable rather than squashing it away.
"""

import logging
import uuid
from collections import defaultdict

from django.apps import apps as installed_apps
from django.conf import settings
from django.db import migrations

logger = logging.getLogger(__name__)

PAID_STATUSES = ("PAID", "OVERPAID")
PENDING_STATUSES = ("PENDING",)

# Tables whose ids are copied as-is and whose sequences therefore have to be moved past them.
PK_PRESERVED = (
    ("catalog", "Country"),
    ("catalog", "Product"),
    ("catalog", "StockItem"),
    ("sales", "Order"),
    ("sales", "OrderItem"),
    ("sales", "Transaction"),
)


# Only ordering constraints: the legacy tables must be fully migrated before they are read. They
# are dropped from the list along with the apps themselves, and the migration keeps working.
LEGACY_DEPENDENCIES = (
    ("passport", "0011_alter_passport_quantity"),
    ("order", "0005_alter_downloadlink_order_item_alter_order_status_and_more"),
)


def is_installed(app_label: str) -> bool:
    try:
        installed_apps.get_app_config(app_label)
    except LookupError:
        return False

    return True


def legacy_models(apps, *names: tuple[str, str]):
    """The listed historical models, or None if the legacy apps are gone."""

    try:
        return [apps.get_model(app_label, model_name) for app_label, model_name in names]
    except LookupError:
        return None


def to_usd(price):
    """Convert a Money to plain USD amount, falling back to the raw amount if rates are missing."""

    from djmoney.contrib.exchange.models import convert_money

    if price is None:
        return 0

    if str(price.currency) == "USD":
        return price.amount

    try:
        return convert_money(price, "USD").amount
    except Exception as e:  # no Rate rows yet - better an approximate snapshot than a failed migration
        logger.warning(f"Cannot convert {price} to USD, keeping the raw amount: {e}")
        return price.amount


def transfer_catalog(apps):
    legacy = legacy_models(apps, ("passport", "Country"), ("passport", "Passport"), ("passport", "PassportFile"))
    if legacy is None:
        return

    OldCountry, OldPassport, OldFile = legacy
    Country = apps.get_model("catalog", "Country")
    Product = apps.get_model("catalog", "Product")
    StockItem = apps.get_model("catalog", "StockItem")

    Country.objects.bulk_create(
        [
            Country(id=c.id, name=c.name, name_en=c.name_en, name_ru=c.name_ru, code=c.code)
            for c in OldCountry.objects.all()
        ]
    )
    Product.objects.bulk_create(
        [
            Product(
                id=p.id,
                name=p.name,
                name_en=p.name_en,
                name_ru=p.name_ru,
                price=p.price,
                country_id=p.country_id,
            )
            for p in OldPassport.objects.all()
        ]
    )
    # Files on disk are not moved - only the column name changes, the paths stay as they are.
    StockItem.objects.bulk_create(
        [StockItem(id=f.id, file=f.file_path.name, product_id=f.passport_id) for f in OldFile.objects.all()]
    )


def transfer_customers(apps) -> dict[str, int]:
    """Fold distinct order emails into Customer rows, keeping unsubscribes if there are any."""

    legacy = legacy_models(apps, ("order", "Order"))
    if legacy is None:
        return {}

    (OldOrder,) = legacy
    Customer = apps.get_model("customer", "Customer")

    emails = sorted(set(OldOrder.objects.values_list("user_email", flat=True)))
    Customer.objects.bulk_create([Customer(email=email, access_token=uuid.uuid4()) for email in emails])

    # First order date is a better "customer since" than the migration date.
    for email in emails:
        first_seen = (
            OldOrder.objects.filter(user_email=email).order_by("created_at").values_list("created_at", flat=True)[:1]
        )
        Customer.objects.filter(email=email).update(created_at=first_seen[0])

    try:
        # Only present if feature/add-broadcasting made it to prod before this release.
        Unsubscribe = apps.get_model("mailing", "Unsubscribe")
    except LookupError:
        Unsubscribe = None

    if Unsubscribe is not None:
        for row in Unsubscribe.objects.all():
            # Losing an unsubscribe costs domain reputation, so it is carried over even for people
            # who never ordered - they get a Customer row of their own.
            Customer.objects.update_or_create(
                email=row.email,
                defaults={"is_subscribed": False, "unsubscribed_at": row.created_at},
            )

    return dict(Customer.objects.values_list("email", "id"))


def transfer_orders(apps, customer_ids: dict[str, int]):
    legacy = legacy_models(apps, ("order", "Order"), ("order", "OrderItem"), ("order", "Transaction"))
    if legacy is None:
        return

    OldOrder, OldItem, OldTxn = legacy
    Order = apps.get_model("sales", "Order")
    OrderItem = apps.get_model("sales", "OrderItem")

    # paid_at never existed; the last callback about the order is the closest thing we have.
    paid_at_by_order = dict(OldTxn.objects.values_list("order_id", "updated_at"))

    old_orders = list(OldOrder.objects.all())
    Order.objects.bulk_create(
        [
            Order(
                id=o.id,
                customer_id=customer_ids[o.user_email],
                status=o.status,
                total_price=o.total_price,
                paid_at=paid_at_by_order.get(o.id) if o.status in PAID_STATUSES else None,
            )
            for o in old_orders
        ]
    )
    # auto_now_add / auto_now overwrite whatever bulk_create was given, .update() does not.
    for o in old_orders:
        Order.objects.filter(pk=o.id).update(created_at=o.created_at, updated_at=o.updated_at)

    OrderItem.objects.bulk_create(
        [
            OrderItem(
                id=item.id,
                order_id=item.order_id,
                product_id=item.passport_id,
                # Today's catalog, not the historical one - see the module docstring.
                product_name=item.passport.name if item.passport_id else "(deleted product)",
                unit_price=item.passport.price if item.passport_id else 0,
                unit_price_usd=to_usd(item.passport.price) if item.passport_id else 0,
                quantity=item.quantity,
            )
            for item in OldItem.objects.select_related("passport")
        ]
    )


def transfer_allocations(apps):
    legacy = legacy_models(apps, ("passport", "PassportFile"), ("order", "OrderItem"), ("order", "DownloadLink"))
    if legacy is None:
        return

    OldFile, OldItem, OldLink = legacy
    Allocation = apps.get_model("sales", "Allocation")

    allocations = []
    held_units = set()
    allocated = defaultdict(int)  # order_item_id -> how many units it already has

    # 1. Files with an exact link: transferred one to one, keeping the uuid so links already
    #    emailed out keep working.
    for link in OldLink.objects.select_related("order_item__order"):
        allocations.append(
            Allocation(
                order_item_id=link.order_item_id,
                stock_item_id=link.passport_file_id,
                state="DELIVERED",
                reserved_at=link.order_item.order.created_at,
                delivered_at=link.updated_at,
                token=link.uuid,
                token_expires_at=link.updated_at + settings.DOWNLOAD_TTL,
            )
        )
        held_units.add(link.passport_file_id)
        allocated[link.order_item_id] += 1

    # 2-3. Everything else is handed out per product: same product, same everything.
    free_units = defaultdict(lambda: defaultdict(list))  # product_id -> status -> [file ids]
    for file_id, product_id, status in OldFile.objects.values_list("id", "passport_id", "status").order_by("id"):
        if file_id not in held_units and product_id is not None:
            free_units[product_id][status].append(file_id)

    def hand_out(file_status: str, state: str, order_statuses: tuple[str, ...]):
        # Ordered by order id so a rehearsal on a dump and the real run produce the same assignment.
        items = (
            OldItem.objects.filter(order__status__in=order_statuses).select_related("order").order_by("order_id", "id")
        )

        for item in items:
            if item.passport_id is None:
                continue

            pool = free_units[item.passport_id][file_status]
            missing = item.quantity - allocated[item.id]

            while missing > 0 and pool:
                delivered = state == "DELIVERED"
                allocations.append(
                    Allocation(
                        order_item_id=item.id,
                        stock_item_id=pool.pop(0),
                        state=state,
                        reserved_at=item.order.created_at,
                        delivered_at=item.order.updated_at if delivered else None,
                        # An invariant of the new schema: delivered means there is a token. This one
                        # is most likely already expired, and that is the honest state of things -
                        # the customer asks for a new link through the form.
                        token=uuid.uuid4() if delivered else None,
                        token_expires_at=item.order.updated_at + settings.DOWNLOAD_TTL if delivered else None,
                    )
                )
                allocated[item.id] += 1
                missing -= 1

    hand_out("SOLD", "DELIVERED", PAID_STATUSES)
    hand_out("RESERVED", "RESERVED", PENDING_STATUSES)

    Allocation.objects.bulk_create(allocations)

    # Items of cancelled, expired and errored orders hold nothing on purpose - only live orders count.
    live_items = OldItem.objects.filter(order__status__in=PAID_STATUSES + PENDING_STATUSES).only("id", "quantity")
    short = [item.id for item in live_items if allocated[item.id] < item.quantity]
    if short:
        # Not fatal: these orders were already short of files before the migration.
        logger.warning(f"Order items still short of units after the transfer: {short}")


def transfer_transactions(apps):
    legacy = legacy_models(apps, ("order", "Transaction"))
    if legacy is None:
        return

    (OldTxn,) = legacy
    Transaction = apps.get_model("sales", "Transaction")

    rows = []
    seen_txn_ids = set()
    old_rows = list(OldTxn.objects.all())

    for t in old_rows:
        # txn_id used to be nullable, but it is the invoice identity now and has to be unique.
        txn_id = t.txn_id or f"legacy-{t.order_id}"
        while txn_id in seen_txn_ids:
            txn_id = f"{txn_id}-{t.id}"
        seen_txn_ids.add(txn_id)

        rows.append(
            Transaction(
                id=t.id,
                order_id=t.order_id,
                txn_id=txn_id,
                amount=t.amount,
                currency=t.currency,
                source_price=t.source_price,
                source_rate=t.source_rate,
                commission=t.commission,
                status=t.status,
                confirmations=t.confirmations,
                merchant=t.merchant,
                merchant_id=t.merchant_id,
                comment=t.comment,
            )
        )

    Transaction.objects.bulk_create(rows)
    for t in old_rows:
        Transaction.objects.filter(pk=t.id).update(created_at=t.created_at, updated_at=t.updated_at)


def reset_sequences(apps, schema_editor):
    for app_label, model_name in PK_PRESERVED:
        # noinspection PyProtectedMember
        table = apps.get_model(app_label, model_name)._meta.db_table
        schema_editor.execute(
            f"SELECT setval("
            f"  pg_get_serial_sequence('{table}', 'id'),"
            f"  COALESCE((SELECT MAX(id) FROM {table}), 1),"
            f"  (SELECT MAX(id) IS NOT NULL FROM {table})"
            f")"
        )


def transfer(apps, schema_editor):
    transfer_catalog(apps)
    customer_ids = transfer_customers(apps)
    transfer_orders(apps, customer_ids)
    transfer_allocations(apps)
    transfer_transactions(apps)
    reset_sequences(apps, schema_editor)


def rollback(apps, schema_editor):
    """Empty the new tables. The legacy ones were only read, so nothing is lost."""

    for app_label, model_name in (
        ("sales", "PaymentCallbackLog"),
        ("sales", "Allocation"),
        ("sales", "Transaction"),
        ("sales", "OrderItem"),
        ("sales", "Order"),
        ("customer", "Customer"),
        ("catalog", "StockItem"),
        ("catalog", "Product"),
        ("catalog", "Country"),
    ):
        apps.get_model(app_label, model_name).objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0001_initial"),
        ("catalog", "0001_initial"),
        ("customer", "0001_initial"),
        # Only while the legacy apps are still installed - a dependency on an app that is gone
        # would make every migration plan unresolvable, including on a fresh database.
        *((app_label, migration) for app_label, migration in LEGACY_DEPENDENCIES if is_installed(app_label)),
    ]

    operations = [
        migrations.RunPython(transfer, rollback),
    ]
