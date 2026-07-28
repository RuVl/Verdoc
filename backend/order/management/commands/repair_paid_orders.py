"""Repair PAID orders that were never delivered (temporary, incident-driven command).

Finds PAID/OVERPAID orders whose items have fewer DownloadLinks than their quantity and
issues the missing files: from the item's own reservation if it still holds one, otherwise
from current stock. Does NOT send any email - use the /purchases form afterwards, it
refreshes the links and mails them.

Background: docs/incidents/2026-07-28-order-652-stuck-paid-order.md. Once the fixes from
that incident have been in production long enough, this command can be deleted.
"""

from django.core.management.base import BaseCommand
from django.db.transaction import atomic

from order.models import DownloadLink, Order, OrderItem
from passport.models import PassportFile


class Command(BaseCommand):
    help = "Issue missing DownloadLinks for paid but undelivered orders"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="report what would change, touch nothing")
        parser.add_argument("--order", type=int, default=None, help="repair a single order by id")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        order_id = options["order"]

        orders = Order.objects.filter(
            status__in=[Order.OrderStatus.PAID, Order.OrderStatus.OVERPAID],
        ).prefetch_related("items__passport")

        if order_id is not None:
            orders = orders.filter(id=order_id)

        repaired, skipped, failed = 0, 0, 0

        for order in orders:
            for item in order.items.all():
                missing = item.quantity - DownloadLink.objects.filter(order_item=item).count()
                if missing <= 0:
                    continue

                label = f"order {order.id} / item {item.id} ({item.passport}) - missing {missing} of {item.quantity}"

                if dry_run:
                    if self.report_plan(item, missing, label):
                        skipped += 1
                    else:
                        failed += 1
                    continue

                try:
                    self.repair_item(item, missing)
                    self.stdout.write(self.style.SUCCESS(f"{label}: issued {missing} link(s)"))
                    repaired += 1
                except (ValueError, AssertionError) as e:
                    self.stdout.write(self.style.ERROR(f"{label}: {e}"))
                    failed += 1

        summary = f"repaired: {repaired}, planned: {skipped}, failed: {failed}"
        self.stdout.write(self.style.WARNING(f"DRY RUN - nothing was changed. {summary}") if dry_run else summary)

    def report_plan(self, item: OrderItem, missing: int, label: str) -> bool:
        """Describe what repair_item() would do, without touching anything. False if it would fail."""

        source = (
            PassportFile.PassportFileStatus.RESERVED if item.is_reserved else PassportFile.PassportFileStatus.IN_STOCK
        )
        verb = "sell" if item.is_reserved else "reserve"
        available = item.passport.files.filter(status=source).count()
        feasible = available >= missing

        style = self.style.SUCCESS if feasible else self.style.ERROR
        self.stdout.write(style(f"{label}: would {verb} {missing} ({available} {source.lower()} available)"))

        return feasible

    @atomic
    def repair_item(self, item: OrderItem, missing: int) -> list[DownloadLink]:
        """Issue the `missing` files for one order item, reusing its reservation when it still holds one."""

        if not item.is_reserved:
            item.passport.reserve(missing)

        passport_files = item.passport.sell(missing)
        links = [DownloadLink.objects.create(order_item=item, passport_file=f) for f in passport_files]

        item.is_reserved = False
        item.save(update_fields=["is_reserved"])

        return links
