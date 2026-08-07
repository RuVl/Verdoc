"""
Compare what we know about Plisio invoices with what Plisio knows, and repair the difference.

A callback that never arrived - or arrived while the backend was down - leaves a paid order sitting
in PENDING with nothing handed over. `--dry-run` only reports; without it the rows are corrected,
the order follows its invoice, and a sale that turns out to be paid is delivered and mailed.
"""

import json
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.transaction import atomic
from django.utils import timezone

from sales.models import Order, Transaction
from sales.plisio import (
    STATUS_MAP,
    PlisioError,
    api_keys,
    apply_changes,
    apply_order_status,
    diff_transaction,
    fetch_operation_any_key,
    iter_operations,
    operation_to_fields,
)
from sales.utils import send_purchases_link

logger = logging.getLogger(__name__)

DEFAULT_DAYS = 7

# Orders that are over and hold nothing. Moving between them buys nothing and costs the reason.
DEAD_STATUSES = (Order.OrderStatus.EXPIRED, Order.OrderStatus.CANCELLED, Order.OrderStatus.ERROR)


class Command(BaseCommand):
    help = "Compare transactions with the Plisio API and correct the ones that drifted"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only report the differences.")
        parser.add_argument("--txn", action="append", default=[], help="Check this txn_id (repeatable).")
        parser.add_argument("--order", action="append", type=int, default=[], help="Check this order id (repeatable).")
        parser.add_argument("--status", default="", help="Only rows in these Plisio statuses, comma-separated.")
        parser.add_argument(
            "--days",
            type=int,
            default=DEFAULT_DAYS,
            help=f"Only rows touched in the last N days (default {DEFAULT_DAYS}, 0 for all of them).",
        )
        parser.add_argument("--limit", type=int, default=None, help="Stop after N transactions.")
        parser.add_argument("--skip-orders", action="store_true", help="Fix the rows only, never move an order.")
        parser.add_argument("--no-email", action="store_true", help="Deliver silently, without mailing the customer.")
        parser.add_argument(
            "--discover",
            action="store_true",
            help="Also walk Plisio's invoice list for invoices we have no row for at all.",
        )
        parser.add_argument("--raw", action="store_true", help="Print Plisio's answer verbatim, for digging.")
        parser.add_argument("--pages", type=int, default=5, help="Pages of the invoice list to walk (--discover).")
        parser.add_argument("--timeout", type=float, default=30, help="Seconds to wait for one API call.")

    def handle(self, *args, **options):
        if not api_keys():
            raise CommandError("Neither PLISIO_SECRET_KEY nor MIRROR_PLISIO_SECRET_KEY is set")

        self.dry_run = options["dry_run"]
        self.raw = options["raw"]
        self.skip_orders = options["skip_orders"]
        self.no_email = options["no_email"]
        self.timeout = options["timeout"]
        self.verbosity = options["verbosity"]

        if self.dry_run:
            self.stdout.write(self.style.WARNING("Dry run: nothing is written"))

        checked, differing, updated, failed = 0, 0, 0, []
        for txn in self.select(options):
            checked += 1
            try:
                operation = fetch_operation_any_key(txn.txn_id, self.timeout)
            except PlisioError as e:
                failed.append(txn.txn_id)
                self.stdout.write(self.style.ERROR(f"{txn.txn_id}: {e}"))
                continue

            if self.raw:
                # Verbatim, because the interesting part of an odd status is usually a field we do
                # not read: what the row says next to it is one line further down anyway.
                self.stdout.write(f"--- {txn.txn_id} (order {txn.order_id}), we have status={txn.status}")
                self.stdout.write(json.dumps(operation, indent=2, ensure_ascii=False, default=str))

            if self.reconcile(txn, operation_to_fields(operation)):
                differing += 1
                if not self.dry_run:
                    updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"Checked {checked} transaction(s), {differing} differ, {updated} corrected")
        )
        if failed:
            self.stdout.write(self.style.ERROR(f"Could not be read from Plisio: {failed}"))

        if options["discover"]:
            self.discover(options["pages"])

    def select(self, options) -> list[Transaction]:
        """The rows to ask about: an explicit list, or everything recent enough to still move."""

        transactions = Transaction.objects.select_related("order").order_by("pk")

        if options["txn"] or options["order"]:
            # Asked about by name, so neither the age nor the status of the row matters.
            transactions = transactions.filter(txn_id__in=options["txn"]) | transactions.filter(
                order_id__in=options["order"]
            )
        else:
            if options["status"]:
                transactions = transactions.filter(status__in=[s.strip() for s in options["status"].split(",")])
            if options["days"]:
                transactions = transactions.filter(updated_at__gte=timezone.now() - timedelta(days=options["days"]))

        if options["limit"]:
            transactions = transactions[: options["limit"]]

        return list(transactions)

    def reconcile(self, txn: Transaction, fields: dict) -> bool:
        """
        Report - and unless this is a dry run, repair - one transaction. True if it differed.

        Not `check`: that name belongs to BaseCommand, which calls it with no arguments to run
        Django's system checks before every command.
        """

        changes = diff_transaction(txn, fields)
        order = txn.order

        remote_status = fields.get("status") or txn.status
        wanted_status = STATUS_MAP.get(remote_status, Order.OrderStatus.ERROR)
        order_differs = not self.skip_orders and order.status != wanted_status and self.may_move(order, wanted_status)

        claimed_order = fields.get("order_number")
        if claimed_order is not None and claimed_order != order.id:
            # Never rewritten here: an invoice pointing at another order is a mix-up to look at by
            # hand, not something to repair by moving money between customers.
            self.stdout.write(self.style.ERROR(f"{txn.txn_id}: Plisio says order {claimed_order}, we say {order.id}"))

        if not changes and not order_differs:
            if self.verbosity > 1:
                self.stdout.write(f"{txn.txn_id} (order {order.id}): in sync")
            return False

        described = "; ".join(f"{field}: {ours} -> {theirs}" for field, (ours, theirs) in changes.items())
        if order_differs:
            described = "; ".join(filter(None, [described, f"order status: {order.status} -> {wanted_status}"]))
        self.stdout.write(self.style.WARNING(f"{txn.txn_id} (order {order.id}): {described}"))

        if self.dry_run:
            return True

        with atomic():
            apply_changes(txn, changes)
            first_payment, allocations = (False, [])
            if order_differs:
                first_payment, allocations = apply_order_status(order, remote_status)

        if first_payment and allocations:
            self.stdout.write(self.style.SUCCESS(f"Order {order.id} was paid after all: {len(allocations)} file(s)"))
            self.mail(order)

        return True

    def may_move(self, order: Order, wanted: str) -> bool:
        """
        Which order moves this command is allowed to make.

        Two refusals, both for things the callback may do and a sweep over old invoices may not:

        A paid order only ever moves to another paid state. The callback can afford to follow every
        status because it is fed one invoice at a time as it happens; here the row may be the
        cancelled duplicate of a currency switch, and "cancelled duplicate" maps to PENDING -
        following it would un-sell a delivered order.

        And one dead unpaid state does not become another. Plisio stores an unpaid invoice as
        `cancelled` long after it told us `expired`, which is the same nothing: the units went back
        the moment the order died, and EXPIRED is the more precise word for why it did.
        """

        if order.status in DEAD_STATUSES and wanted in DEAD_STATUSES:
            if self.verbosity > 1:
                self.stdout.write(f"Order {order.id} stays {order.status}: {wanted} is the same dead end")
            return False

        if order.paid_at is None or wanted in Order.PAID_STATUSES:
            return True

        self.stdout.write(f"Order {order.id} stays {order.status}: it is paid, the invoice says {wanted}")
        return False

    def mail(self, order: Order):
        """The link the lost callback never sent. A dead SMTP costs the report, not the delivery."""

        if self.no_email:
            self.stdout.write(f"Order {order.id} delivered without an e-mail (--no-email)")
            return

        customer = order.customer
        # Deliberately not a rotation, as in the callback: a link the customer already has must survive.
        customer.ensure_access_token()

        try:
            send_purchases_link(None, customer)
        except Exception as e:
            logger.error(f"Order {order.id} is delivered but the e-mail did not go out: {e}")
            self.stdout.write(self.style.ERROR(f"Order {order.id}: the files are delivered, the e-mail is not ({e})"))

    def discover(self, pages: int):
        """
        Invoices Plisio has and we do not - the callback that never arrived at all.

        Only invoices naming an order we can find get a row; anything else is reported, because a
        transaction without its order would be a number nobody can act on.
        """

        known = set(Transaction.objects.values_list("txn_id", flat=True))
        missing, created = 0, 0

        for api_key in api_keys():
            try:
                operations = list(iter_operations(api_key, timeout=self.timeout, max_pages=pages, type="invoice"))
            except PlisioError as e:
                self.stdout.write(self.style.ERROR(f"Cannot list invoices: {e}"))
                continue

            for operation in operations:
                txn_id = str(operation.get("id") or "")
                if not txn_id or txn_id in known:
                    continue

                known.add(txn_id)
                missing += 1
                created += self.adopt(txn_id, operation_to_fields(operation))

        self.stdout.write(self.style.SUCCESS(f"Unknown invoices: {missing}, rows created: {created}"))

    def adopt(self, txn_id: str, fields: dict) -> bool:
        """Give one unknown invoice a row of its own, and let its order follow it."""

        order = Order.objects.filter(pk=fields.get("order_number")).first()
        if order is None:
            self.stdout.write(self.style.ERROR(f"{txn_id}: unknown to us and names no order of ours, skipped"))
            return False

        if fields.get("amount") is None or not fields.get("currency"):
            # Both columns are required, and a row invented around a missing amount would be worse
            # than no row: the statistics read these numbers.
            self.stdout.write(self.style.ERROR(f"{txn_id}: order {order.id}, but Plisio gave no amount, skipped"))
            return False

        self.stdout.write(self.style.WARNING(f"{txn_id}: no row at all, order {order.id} is {order.status}"))
        if self.dry_run:
            return False

        remote_status = fields.get("status")
        row = {field: value for field, value in fields.items() if field != "order_number" and value is not None}

        with atomic():
            Transaction.objects.create(order=order, txn_id=txn_id, **row)
            first_payment, allocations = (False, [])
            if not self.skip_orders and self.may_move(order, STATUS_MAP.get(remote_status, Order.OrderStatus.ERROR)):
                first_payment, allocations = apply_order_status(order, remote_status)

        if first_payment and allocations:
            self.stdout.write(self.style.SUCCESS(f"Order {order.id} was paid after all: {len(allocations)} file(s)"))
            self.mail(order)

        return True
