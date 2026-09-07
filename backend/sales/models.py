import logging
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models
from django.db.models import Count, F, ProtectedError, Q, UniqueConstraint, Value
from django.db.models.functions import Coalesce
from django.db.transaction import atomic
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField

from backend.sites import absolute_url
from catalog.models import Product, StockItem

logger = logging.getLogger(__name__)


def protect_held_units(collector, field, sub_objs, using):
    """
    on_delete for Allocation.stock_item: a unit somebody holds cannot be deleted.

    A DELIVERED unit is the file a paying customer downloads, so dropping it would leave the sale
    without anything to hand over; a RESERVED one belongs to a live order. Both are refused.
    RELEASED allocations are history and let the file go, keeping the record with a NULL unit.
    """

    held = [allocation for allocation in sub_objs if allocation.state != Allocation.State.RELEASED]
    if held:
        logger.warning(f"Refused to delete stock items held by allocations {[a.pk for a in held]}")
        raise ProtectedError("Cannot delete a unit that an order holds", held)

    models.SET_NULL(collector, field, sub_objs, using)


class OrderQuerySet(models.QuerySet):
    def paid(self) -> "OrderQuerySet":
        """
        Orders the customer has actually paid for - the only definition, see `CustomerQuerySet`.

        Keyed off `paid_at` and not off `status`: the stamp is written exactly once by
        `mark_paid()`, while the status keeps moving with every callback. Plisio reports the
        invoice a customer abandoned when switching coin as `cancelled duplicate`, which maps back
        to PENDING - filtering by status would drop a delivered order off the purchases page.
        """

        return self.filter(paid_at__isnull=False)

    def reusable(self, email: str, items: list[dict]) -> "Order | None":
        """
        A live invoice of this customer for exactly this cart, or None.

        Handing it back instead of minting a second order is what keeps a double click - or someone
        probing the checkout with the same cart - from reserving another copy of the same units.

        Both halves of the filter carry weight. `paid_at` is the paid test, because it is the only
        stamp written exactly once: a late `cancelled duplicate` callback after the `completed` one
        puts a settled order back at PENDING (`plisio.apply_order_status`), and if `deliver()` had
        failed its units are still RESERVED, so nothing else tells it from a live checkout.
        `status` is what excludes the invoices Plisio has already killed - EXPIRED, CANCELLED,
        ERROR - which `paid_at` alone would let through.
        """

        wanted = sorted((item["product"].pk, item["quantity"]) for item in items)
        wanted_units = sum(quantity for _, quantity in wanted)

        candidates = (
            self.filter(customer__email=email, status=Order.OrderStatus.PENDING, paid_at__isnull=True)
            .exclude(invoice_url="")
            .annotate(reserved=Count("items__allocations", filter=Q(items__allocations__state="RESERVED")))
            .prefetch_related("items__product")
            .order_by("-created_at")
        )

        for order in candidates:
            if order.is_expired() or order.reserved != wanted_units:
                continue

            items_of = list(order.items.all())
            if sorted((item.product_id, item.quantity) for item in items_of) != wanted:
                continue

            # The catalog price must not have moved since, otherwise the old invoice would sell at
            # the old price. Both sides come from the same column, so this compares exactly.
            if all(item.product and item.unit_price == item.product.price for item in items_of):
                return order

        return None


class Order(models.Model):
    """
    One checkout: what the customer asked for and how the payment went.

    :param customer: Who bought.
    :param status: Order status (PENDING, PAID, OVERPAID, EXPIRED, ERROR, CANCELLED).
    :param total_price: Total price of the order, in USD as sent to Plisio.
    :param invoice_url: Plisio invoice this order was sent to, empty until the invoice is minted.
    :param created_at: When the order was created.
    :param updated_at: When the order was last touched.
    :param paid_at: When the order first became paid; stamped once, gates the delivery email.
    """

    class OrderStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        OVERPAID = "OVERPAID", "Overpaid"
        EXPIRED = "EXPIRED", "Expired"
        ERROR = "ERROR", "Error"
        CANCELLED = "CANCELLED", "Cancelled"

    # How long a reservation lives. The invoice Plisio mints expires in 60 minutes, so an order
    # gets that from its last move plus ten minutes of grace from creation. Read these instead of
    # writing the number again - `statistics.time_to_pay` counts late payments against them.
    RESERVATION_FROM_CREATED = timedelta(hours=1, minutes=10)
    RESERVATION_FROM_UPDATED = timedelta(hours=1)

    customer = models.ForeignKey("customer.Customer", related_name="orders", on_delete=models.PROTECT)
    status = models.CharField(max_length=15, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    total_price = MoneyField(max_digits=10, decimal_places=2, default_currency="USD")
    invoice_url = models.URLField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    objects = OrderQuerySet.as_manager()

    # Annotated with the queryset, see catalog.models.
    if TYPE_CHECKING:
        items: models.QuerySet["OrderItem"]
        transactions: models.QuerySet["Transaction"]
        callback_logs: models.QuerySet["PaymentCallbackLog"]

    class Meta:
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order {self.id} - {self.customer.email if self.customer_id else 'NULL'}"

    def is_expired(self):
        now = timezone.now()

        return (
            now > self.created_at + self.RESERVATION_FROM_CREATED
            or now > self.updated_at + self.RESERVATION_FROM_UPDATED
        )

    def mark_paid(self) -> bool:
        """
        Stamp paid_at, but only the first time.

        One UPDATE decides it, so a duplicate Plisio callback loses the race instead of sending a
        second email - the delivery itself is idempotent anyway.
        """

        now = timezone.now()
        stamped = Order.objects.filter(pk=self.pk, paid_at__isnull=True).update(paid_at=now)
        if stamped:
            self.paid_at = now
            logger.info(f"Order {self.pk} marked as paid at {now:%Y-%m-%d %H:%M:%S}")
        else:
            logger.info(f"Order {self.pk} was already paid at {self.paid_at}, not sending a second email")

        return bool(stamped)

    @atomic
    def deliver(self) -> list["Allocation"]:
        """Hand over every item. Safe to repeat and tops up what the reservation lost."""

        allocations = []
        for order_item in self.items.all():
            allocations.extend(order_item.deliver())

        return allocations

    @atomic
    def release(self) -> list["Allocation"]:
        """Give the reserved units back. Idempotent."""

        allocations = []
        for order_item in self.items.all():
            allocations.extend(order_item.release())

        return allocations


class OrderItem(models.Model):
    """
    A wanted quantity of one product, with the price frozen at checkout.

    The snapshot fields answer "what did this cost back then" - the catalog is free to change
    afterwards, and the product may even be deleted.

    :param order: Order this item belongs to.
    :param product: Product bought, NULL once it leaves the catalog.
    :param product_name: Product name as of checkout.
    :param unit_price: Price of one unit as of checkout, in the product's own currency.
    :param unit_price_usd: The same price converted to USD at the exchange rate of that day. Not
        derivable from `unit_price` afterwards - a RUB-priced product converts differently every
        day, and this is the number `Order.total_price` was built from and Plisio was billed for.
    :param quantity: How many units.
    """

    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="order_items", on_delete=models.SET_NULL, null=True)

    product_name = models.CharField(max_length=255)
    unit_price = MoneyField(max_digits=10, decimal_places=2, default_currency="USD")
    unit_price_usd = models.DecimalField(max_digits=10, decimal_places=2)

    quantity = models.PositiveIntegerField()

    if TYPE_CHECKING:
        allocations: models.QuerySet["Allocation"]

    class Meta:
        verbose_name = _("Order item")
        verbose_name_plural = _("Order items")

    def __str__(self):
        return f"{self.quantity} x {self.product_name} - {self.order}"

    @atomic
    def _allocate(self, count: int) -> list["Allocation"]:
        """Take `count` free units of the product and reserve them for this item."""

        if count <= 0:
            return []

        if self.product_id is None:
            logger.error(f"Order item {self.pk} has no product to allocate from")
            raise ValueError(f"Order item {self.pk} has no product to allocate from")

        # Lock the product row so concurrent checkouts of the same product queue up here instead of
        # picking the same units. The partial unique index on Allocation is the hard backstop.
        Product.objects.select_for_update().filter(pk=self.product_id).exists()

        units = list(StockItem.objects.available().filter(product_id=self.product_id)[:count])
        if len(units) != count:
            logger.error(
                f"Order item {self.pk} (order {self.order_id}) is out of stock for product "
                f"{self.product_id}: need {count}, have {len(units)}"
            )
            raise ValueError(f"Not enough stock for product {self.product_id}: need {count}, have {len(units)}")

        logger.info(f"Order item {self.pk} reserved units {[unit.pk for unit in units]}")
        now = timezone.now()
        return Allocation.objects.bulk_create(
            [
                Allocation(order_item=self, stock_item=unit, state=Allocation.State.RESERVED, reserved_at=now)
                for unit in units
            ]
        )

    @atomic
    def reserve(self) -> list["Allocation"]:
        """Reserve the whole quantity at checkout."""

        if self.allocations.exclude(state=Allocation.State.RELEASED).exists():
            logger.error(f"Order item {self.pk} (order {self.order_id}) already holds units, refusing to reserve again")
            raise ValueError(f"Order item {self.pk} cannot be reserved twice")

        return self._allocate(self.quantity)

    @atomic
    def deliver(self) -> list["Allocation"]:
        """
        Turn the reservation into a delivery: RESERVED -> DELIVERED with a fresh token.

        Repeating this is a no-op, and a late payment is no longer a special case: if the reservation
        was already released, the missing units are allocated again from current stock. Running out-of-stock
        raises, and the caller rolls the callback back so Plisio can retry.
        """

        delivered = list(self.allocations.filter(state=Allocation.State.DELIVERED))
        reserved = list(self.allocations.select_for_update().filter(state=Allocation.State.RESERVED))

        missing = self.quantity - len(delivered) - len(reserved)
        if missing > 0:
            # Late payment: the reservation had already expired, so we buy the units back now.
            logger.warning(f"Order item {self.pk} lost {missing} unit(s) before payment, re-allocating from stock")
            reserved.extend(self._allocate(missing))

        now = timezone.now()
        for allocation in reserved:
            allocation.state = Allocation.State.DELIVERED
            allocation.delivered_at = now
            allocation.issue_token(commit=False)

        Allocation.objects.bulk_update(reserved, ["state", "delivered_at", "token", "token_expires_at"])
        return delivered + reserved

    @atomic
    def release(self) -> list["Allocation"]:
        """Return reserved units to stock. Delivered ones are never touched."""

        reserved = list(self.allocations.select_for_update().filter(state=Allocation.State.RESERVED))

        now = timezone.now()
        for allocation in reserved:
            allocation.state = Allocation.State.RELEASED
            allocation.released_at = now

        Allocation.objects.bulk_update(reserved, ["state", "released_at"])
        if reserved:
            logger.info(f"Order item {self.pk} released units {[a.stock_item_id for a in reserved]}")

        return reserved


class AllocationQuerySet(models.QuerySet):
    def downloadable(self) -> "AllocationQuerySet":
        """Units already handed over - the only ones the purchases page lists."""

        return self.filter(state=Allocation.State.DELIVERED)

    def of_customer(self, customer) -> "AllocationQuerySet":
        return self.filter(order_item__order__customer=customer)

    @atomic
    def reissue_tokens(self) -> list["Allocation"]:
        """Give every selected unit a fresh token, resetting DOWNLOAD_TTL. Idempotent by nature."""

        allocations = list(self.select_for_update())
        for allocation in allocations:
            allocation.issue_token(commit=False)

        Allocation.objects.bulk_update(allocations, ["token", "token_expires_at"])
        return allocations


class Allocation(models.Model):
    """
    The link between one stock unit and one order item - the single source of truth about who
    holds a unit and whether it was handed over (ADR-0001).

    Its existence in a non-RELEASED state is what makes a unit unavailable, so "reserved by
    nobody" cannot happen and neither can "sold without a download link".

    :param order_item: Item this unit was allocated to.
    :param stock_item: The unit; only ever NULL for a RELEASED allocation, see `protect_held_units`.
    :param state: RESERVED (held), DELIVERED (handed over), RELEASED (given back).
    :param reserved_at: When the unit was taken.
    :param delivered_at: When the unit was handed over.
    :param released_at: When the unit was given back.
    :param token: Opens this single file; rotated on request, see DOWNLOAD_TTL.
    :param token_expires_at: When the token stops working.
    :param download_count: How many times the file behind this allocation was served.
    :param first_downloaded_at: When the customer first took the file.
    :param last_downloaded_at: When the customer last took the file.
    """

    class State(models.TextChoices):
        RESERVED = "RESERVED", _("Reserved")
        DELIVERED = "DELIVERED", _("Delivered")
        RELEASED = "RELEASED", _("Released")

    order_item = models.ForeignKey(OrderItem, related_name="allocations", on_delete=models.CASCADE)
    stock_item = models.ForeignKey(StockItem, related_name="allocations", on_delete=protect_held_units, null=True)

    state = models.CharField(max_length=15, choices=State.choices, default=State.RESERVED)

    reserved_at = models.DateTimeField(default=timezone.now)
    delivered_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)

    token = models.UUIDField(null=True, blank=True, unique=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)

    # Written only by `record_download`, which is the one place a download touches the database.
    download_count = models.PositiveIntegerField(default=0)
    first_downloaded_at = models.DateTimeField(null=True, blank=True)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)

    objects = AllocationQuerySet.as_manager()

    class Meta:
        verbose_name = _("Allocation")
        verbose_name_plural = _("Allocations")
        ordering = ["-reserved_at"]
        constraints = [
            # One file - one buyer. Released units are free again, so they stay out of the index.
            UniqueConstraint(
                fields=["stock_item"],
                condition=~Q(state="RELEASED"),
                name="one_active_allocation_per_stock_item",
            ),
        ]

    def __str__(self):
        return f"{self.state} {self.stock_item_id} for {self.order_item_id}"

    def is_token_valid(self) -> bool:
        return self.token is not None and self.token_expires_at is not None and timezone.now() <= self.token_expires_at

    def issue_token(self, commit: bool = True):
        """Mint a new download token and reset its TTL, killing the previous one."""

        self.token = uuid.uuid4()
        self.token_expires_at = timezone.now() + settings.DOWNLOAD_TTL
        if commit:
            self.save(update_fields=["token", "token_expires_at"])

    def record_download(self):
        """
        Count one served download.

        An UPDATE with F() rather than a save(): two browsers pulling the same link at once must
        add up to two, and nothing else on the row may be written back from a stale instance.
        """

        now = timezone.now()
        Allocation.objects.filter(pk=self.pk).update(
            download_count=F("download_count") + 1,
            first_downloaded_at=Coalesce("first_downloaded_at", Value(now)),
            last_downloaded_at=now,
        )

    def get_download_url(self, request: HttpRequest | None) -> str:
        """
        Absolute link to this one file.

        The token alone identifies it - the e-mail used to be part of the path and proved nothing,
        since it travelled in the same message as the token.
        """

        return absolute_url(reverse("download-file", args=[self.token]), request)


class Transaction(models.Model):
    # noinspection GrazieInspection
    """
    One Plisio invoice of an order.

    An order can have several: switching cryptocurrency mints a new invoice with a new txn_id while
    order_number stays ours, so this is a FK and not a OneToOne (ADR-0006).

    :param order: Order being paid for.
    :param txn_id: Plisio invoice id.
    :param amount: Amount in the invoice's cryptocurrency.
    :param currency: Cryptocurrency of the invoice.
    :param pending_amount: What is still missing when the customer underpaid.
    :param tx_urls: Blockchain transactions of this invoice, as sent by Plisio.
    :param source_price: Source amount and currency (if provided) - the fiat side of the invoice.
    :param source_rate: How much of `currency` one unit of `source_currency` buys, so that
        `amount / source_rate` is the fiat value. It divides, it never multiplies - Plisio's own
        example has 0.0104 ETH at a rate of 0.00052 for $20.
    :param commission: What Plisio kept, quoted in the invoice's cryptocurrency, not in fiat.
    :param status: Status of the invoice: new, pending, pending internal, expired, completed,
        mismatch, error, cancelled, cancelled duplicate.
    :param confirmations: Number of confirmations of the crypto transaction.
    :param created_at: When we first saw the invoice.
    :param updated_at: When we last got a callback about it.
    :param merchant: Merchant name (from api settings).
    :param merchant_id: Merchant ID (from api settings).
    :param comment: Invoice comment (if provided).
    """

    class TransactionStatus(models.TextChoices):
        NEW = "new", "New"
        PENDING = "pending", "Pending"
        PENDING_INTERNAL = "pending internal", "Pending Internal"
        EXPIRED = "expired", "Expired"
        COMPLETED = "completed", "Completed"
        MISMATCH = "mismatch", "Mismatch"
        ERROR = "error", "Error"
        CANCELLED = "cancelled", "Cancelled"
        CANCELLED_DUPLICATE = "cancelled duplicate", "Cancelled Duplicate"

    order = models.ForeignKey(Order, related_name="transactions", on_delete=models.CASCADE)
    txn_id = models.CharField(max_length=100, unique=True)

    amount = models.DecimalField(max_digits=20, decimal_places=10)
    currency = models.CharField(max_length=10)

    pending_amount = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    tx_urls = models.JSONField(null=True, blank=True)

    source_price = MoneyField(
        max_digits=10,
        decimal_places=2,
        default_currency="USD",
        null=True,
        blank=True,
    )  # source_amount and source_currency
    source_rate = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    commission = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)

    status = models.CharField(max_length=30, choices=TransactionStatus.choices, default=TransactionStatus.NEW)
    confirmations = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    merchant = models.CharField(max_length=127, null=True, blank=True)
    merchant_id = models.CharField(max_length=63, null=True, blank=True)
    comment = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = _("Transaction")
        verbose_name_plural = _("Transactions")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Transaction {self.txn_id} - order {self.order_id}"


class PaymentCallbackLog(models.Model):
    """
    Raw Plisio callback, exactly as it arrived.

    Written after the hash check but before the atomic block, so a rolled-back callback still
    leaves a trace - the old schema overwrote invoice history and left nothing to debug with.

    :param order: Order the callback claims to be about, NULL if we could not find one.
    :param txn_id: Plisio invoice id from the payload.
    :param payload: The payload itself, minus verify_hash.
    :param received_at: When it arrived.
    """

    order = models.ForeignKey(Order, related_name="callback_logs", on_delete=models.SET_NULL, null=True, blank=True)
    txn_id = models.CharField(max_length=100, null=True, blank=True)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Payment callback")
        verbose_name_plural = _("Payment callbacks")
        ordering = ["-received_at"]

    def __str__(self):
        return f"Callback {self.txn_id or '?'} at {self.received_at:%Y-%m-%d %H:%M:%S}"
