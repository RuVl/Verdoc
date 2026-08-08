"""
Every number the statistics page shows, and nothing else.

Plain functions over a half-open period `[start, end)`, returning data ready to render. No HTTP,
no templates: this is the layer the tests hold, so a change in the page cannot quietly change what
a figure means.

Two conventions run through all of it:

- **Money is the price snapshot.** `OrderItem.unit_price_usd` is what the customer was actually
  charged, so a later edit of the catalogue price cannot rewrite last month's revenue.
- **A sale is `Order.paid_at`.** The same stamp `CustomerQuerySet.buyers()` keys off, written
  exactly once by `Order.mark_paid()`. PAID and OVERPAID are one thing here.

Days are UTC days - the project runs on `TIME_ZONE = "UTC"` and the page says so out loud.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Aggregate, Avg, Count, DecimalField, DurationField, F, Min, Q, Sum
from django.db.models.functions import Coalesce, TruncDay

from catalog.models import Product, StockItem
from customer.models import Customer
from sales.models import Allocation, Order, OrderItem, PaymentCallbackLog, Transaction

# How long an order may take to pay before its reservation is gone and the stock had to be handed
# out again. Taken from the model, not written out again, so the two cannot drift apart.
RESERVATION_WINDOW = Order.RESERVATION_FROM_UPDATED

# The invoices somebody paid. `mismatch` is Plisio's word for a sum that did not match the invoice;
# we hand the files over for it and stamp paid_at, so its revenue is in `gross` - and its
# commission has to be in the total beside it, or the shop looks more profitable than it is.
PAID_INVOICES = (Transaction.TransactionStatus.COMPLETED, Transaction.TransactionStatus.MISMATCH)

# The callback statuses that mean the money is on its way but the chain has not confirmed it yet -
# the middle of the walk from a freshly minted invoice to a paid order.
PENDING_INVOICES = (Transaction.TransactionStatus.PENDING, Transaction.TransactionStatus.PENDING_INTERNAL)

# The window the stock forecast measures the sales rate over, regardless of the page's period:
# "will it last" is a question about now, not about the range being browsed.
SALES_RATE_DAYS = 30

# Days behind each point that the trend line averages over.
TREND_WINDOW = 7

MONEY = DecimalField(max_digits=20, decimal_places=2)


class Median(Aggregate):
    """PERCENTILE_CONT(0.5) - PostgreSQL's ordered-set aggregate, which the ORM has no shortcut for."""

    function = "PERCENTILE_CONT"
    name = "median"
    template = "%(function)s(0.5) WITHIN GROUP (ORDER BY %(expressions)s)"


@dataclass
class Period:
    """The half-open range the page is looking at, plus how it was asked for."""

    start: datetime
    end: datetime
    preset: str = "30"

    @property
    def days(self) -> int:
        return max((self.end - self.start).days, 1)

    @property
    def last_day(self) -> date:
        """The last day inside the range - `end` is exclusive and would read as one day too far."""

        return (self.end - timedelta(days=1)).date()


@dataclass
class MoneyTotals:
    gross: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")
    orders: int = 0

    @property
    def net(self) -> Decimal:
        return self.gross - self.commission

    @property
    def average_order(self) -> Decimal:
        return self.gross / self.orders if self.orders else Decimal("0")

    @property
    def commission_share(self) -> Decimal:
        return self.commission / self.gross * 100 if self.gross else Decimal("0")


@dataclass
class Funnel:
    created: int = 0
    paid: int = 0
    by_status: list[dict] = field(default_factory=list)
    leads: int = 0

    @property
    def conversion(self) -> Decimal:
        return Decimal(self.paid) / Decimal(self.created) * 100 if self.created else Decimal("0")


def first_sale_at() -> datetime | None:
    """
    When the first order was ever paid, or None on an empty shop.

    This is where "all time" starts: an arbitrary earlier date would draw months of flat zero
    before the shop existed and squash every real day into the right-hand edge of the chart.
    """

    return Order.objects.filter(paid_at__isnull=False).aggregate(first=Min("paid_at"))["first"]


def paid_orders(period: Period):
    """Orders that became paid inside the period - the base of every money figure."""

    return Order.objects.filter(paid_at__gte=period.start, paid_at__lt=period.end)


def sold_items(period: Period):
    return OrderItem.objects.filter(order__paid_at__gte=period.start, order__paid_at__lt=period.end)


def _line_total():
    return Sum(F("unit_price_usd") * F("quantity"), output_field=MONEY)


def revenue_by_day(period: Period) -> list[dict]:
    """
    Gross revenue per day, with the empty days filled in.

    A day with no sales has no rows to group, and leaving it out would let the chart draw a
    straight line across a dead week as if it had been trading.
    """

    rows = (
        sold_items(period)
        .annotate(day=TruncDay("order__paid_at"))
        .values("day")
        .annotate(revenue=_line_total())
        .order_by("day")
    )
    revenue: dict[date, Decimal] = {row["day"].date(): row["revenue"] for row in rows}

    days = []
    cursor = period.start.date()
    while cursor < period.end.date():
        days.append({"day": cursor, "revenue": revenue.get(cursor, Decimal("0"))})
        cursor += timedelta(days=1)

    return days


def moving_average(rows: list[dict], window: int = TREND_WINDOW) -> list[Decimal | None]:
    """
    A trailing average over `window` days, aligned to `rows`.

    Daily revenue on a shop this size is mostly noise - a day with two orders next to a day with
    none says nothing about the trend. The first days carry None rather than an average of a
    shorter window, which would start the line at whatever the first day happened to be.
    """

    values = [row["revenue"] for row in rows]

    return [
        (sum(values[index + 1 - window : index + 1]) / window) if index + 1 >= window else None
        for index in range(len(values))
    ]


def money_totals(period: Period) -> MoneyTotals:
    """Gross from the snapshots, what Plisio kept, and how many orders it took."""

    gross = sold_items(period).aggregate(total=Coalesce(_line_total(), Decimal("0"), output_field=MONEY))["total"]

    # The commission arrives in the invoice's cryptocurrency, and source_rate says how much of that
    # currency one dollar buys - so the fiat value is the commission *divided* by the rate. Both
    # numbers are optional in the callback, and a zero rate would divide by nothing, so an invoice
    # missing either is left out rather than counted as free.
    commission = (
        Transaction.objects.filter(
            order__paid_at__gte=period.start,
            order__paid_at__lt=period.end,
            status__in=PAID_INVOICES,
            commission__isnull=False,
            source_rate__isnull=False,
        )
        .exclude(source_rate=0)
        .aggregate(total=Coalesce(Sum(F("commission") / F("source_rate"), output_field=MONEY), Decimal("0")))["total"]
    )

    return MoneyTotals(gross=gross, commission=commission, orders=paid_orders(period).count())


def top_products(period: Period, limit: int | None = 10) -> list[dict]:
    """
    Best sellers by revenue, or every product sold when `limit` is None (the CSV takes that one).

    Grouped by the snapshot `product_name`, not by the live product: renaming a product in the
    catalogue must not silently merge or split what was sold under the old name.
    """

    return list(
        sold_items(period)
        .values("product_name")
        .annotate(revenue=_line_total(), units=Sum("quantity"))
        .order_by("-revenue")[:limit]
    )


def top_countries(period: Period, limit: int = 10) -> list[dict]:
    """Same cut by country. Items whose product was deleted have no country and are dropped."""

    return list(
        sold_items(period)
        .filter(product__country__isnull=False)
        .values("product__country__name")
        .annotate(revenue=_line_total(), units=Sum("quantity"))
        .order_by("-revenue")[:limit]
    )


def stock_forecast(now: datetime) -> list[dict]:
    """
    What is left of each product and how long it lasts at the recent rate.

    The only block on the page that is about right now rather than about the period: the answer to
    "what do I buy next" cannot depend on which range somebody happens to be browsing.
    """

    since = now - timedelta(days=SALES_RATE_DAYS)
    sold = (
        OrderItem.objects.filter(order__paid_at__gte=since)
        .values("product_id")
        .annotate(units=Sum("quantity"))
        .order_by()
    )
    sold_by_product = {row["product_id"]: row["units"] for row in sold}

    rows = []
    for product in Product.objects.with_available().select_related("country"):
        units = sold_by_product.get(product.pk, 0)
        rate = Decimal(units) / Decimal(SALES_RATE_DAYS)
        rows.append(
            {
                "product": product.name,
                "country": product.country.name if product.country_id else "-",
                "available": product.available,
                "sold": units,
                "rate": rate,
                # Nothing selling means nothing running out - an infinite runway, not a crash.
                "days_left": (Decimal(product.available) / rate) if rate else None,
            }
        )

    # Sorted by what it costs to ignore the row. Anything that still sells comes first, soonest
    # to run out at the top - a sold-out seller is a zero and heads the list. Products that have
    # not sold in the window have no runway to compare, so they follow, most stock first: that is
    # money sitting still. A product that is both out of stock and not selling is last - there is
    # nothing to lose and nothing to buy.
    return sorted(
        rows,
        key=lambda row: (
            row["days_left"] is None,
            row["days_left"] if row["days_left"] is not None else 0,
            -row["available"],
        ),
    )


def stock_age(now: datetime) -> dict:
    """
    How long the units currently in stock have been sitting there.

    Units that predate the field carry the date of the migration, so the oldest age reads as "at
    least this long" until that generation is sold through.
    """

    units = StockItem.objects.available()
    oldest = units.order_by("created_at").values_list("created_at", flat=True).first()

    return {
        "available": units.count(),
        "oldest_days": (now - oldest).days if oldest else None,
    }


def funnel(period: Period) -> Funnel:
    """Orders opened in the period, and how many of them ended up paid."""

    orders = Order.objects.filter(created_at__gte=period.start, created_at__lt=period.end)
    counts = orders.aggregate(created=Count("pk"), paid=Count("pk", filter=Q(paid_at__isnull=False)))

    by_status = list(orders.values("status").annotate(count=Count("pk")).order_by("-count"))

    return Funnel(
        created=counts["created"],
        paid=counts["paid"],
        by_status=by_status,
        # Customers who have never paid for anything - the same definition the admin list uses.
        leads=Customer.objects.leads().filter(created_at__gte=period.start, created_at__lt=period.end).count(),
    )


def time_to_pay(period: Period) -> dict:
    """
    How long customers take to pay, and how many took longer than the reservation lasts.

    A late payment is not a lost sale - `Order.deliver()` re-allocates from stock - but every one
    of them is a unit that sat locked and then had to be found again.
    """

    orders = paid_orders(period).annotate(took=F("paid_at") - F("created_at"))
    stats = orders.aggregate(
        median=Median("took", output_field=DurationField()),
        average=Avg("took"),
        late=Count("pk", filter=Q(took__gt=RESERVATION_WINDOW)),
        total=Count("pk"),
    )

    return {
        # PERCENTILE_CONT interpolates, so both come back with microseconds nobody can act on.
        "median": _to_seconds(stats["median"]),
        "average": _to_seconds(stats["average"]),
        "late": stats["late"],
        "late_share": Decimal(stats["late"]) / Decimal(stats["total"]) * 100 if stats["total"] else Decimal("0"),
    }


def payment_stages(period: Period) -> dict:
    """
    Where the wait between a minted invoice and a paid order goes: new -> pending -> completed.

    Two legs, and they add up to `time_to_pay`: `waiting` is the customer deciding and sending
    (new -> pending), `confirming` is the chain (pending -> completed). Only the middle stamp has
    to be found, and it comes from the raw callbacks - a `Transaction` keeps one `updated_at`, which
    the paid callback overwrites - while the end is `paid_at`, written once by `Order.mark_paid()`.

    An order with no pending callback is left out of both legs rather than counted as instant: the
    state can be skipped entirely (a payment first seen in a confirmed block), and callbacks are
    pruned after `prune_callback_logs.DEFAULT_RETENTION_DAYS`, so a period older than the retention
    window reports on however many are left. `covered` is how many orders the figures are of.
    """

    rows = (
        PaymentCallbackLog.objects.filter(order__paid_at__gte=period.start, order__paid_at__lt=period.end)
        .values("order_id")
        .annotate(
            # Grouped by order, so both order columns are constant inside the group - Min() is only
            # how a GROUP BY query is allowed to carry them along.
            created=Min("order__created_at"),
            paid=Min("order__paid_at"),
            pending=Min("received_at", filter=Q(payload__status__in=PENDING_INVOICES)),
        )
        .order_by()
    )

    waiting, confirming = [], []
    for row in rows:
        if row["pending"] is None:
            continue

        waiting.append(row["pending"] - row["created"])
        # A pending callback that arrived after paid_at was stamped - a repeat, or a message
        # overtaken by the paid one - would make the chain read as negative time.
        confirming.append(max(row["paid"] - row["pending"], timedelta(0)))

    return {
        "covered": len(waiting),
        "waiting_median": _median(waiting),
        "waiting_average": _average(waiting),
        "confirming_median": _median(confirming),
        "confirming_average": _average(confirming),
    }


def _median(values: list[timedelta]) -> timedelta | None:
    """
    The middle value, interpolating over an even count - the reading `Median` gives in SQL.

    In Python because the two legs are assembled here anyway, and importing the standard library's
    `statistics` into a module of this name would read like a bug.
    """

    if not values:
        return None

    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return _to_seconds(ordered[middle])

    return _to_seconds((ordered[middle - 1] + ordered[middle]) / 2)


def _average(values: list[timedelta]) -> timedelta | None:
    return _to_seconds(sum(values, timedelta()) / len(values)) if values else None


def _to_seconds(value: timedelta | None) -> timedelta | None:
    return timedelta(seconds=round(value.total_seconds())) if value is not None else None


def repeat_customers(period: Period, limit: int = 10) -> dict:
    """
    Who comes back, and what a customer is worth.

    Counted over everyone who has ever paid, not over the period: a second purchase in March by
    somebody who first bought in January is exactly the fact worth having, and clipping the
    history would hide it.
    """

    buyers = Customer.objects.buyers().annotate(
        paid_orders=Count("orders", filter=Q(orders__paid_at__isnull=False), distinct=True),
        spent=Coalesce(
            Sum(
                F("orders__items__unit_price_usd") * F("orders__items__quantity"),
                filter=Q(orders__paid_at__isnull=False),
                output_field=MONEY,
            ),
            Decimal("0"),
            output_field=MONEY,
        ),
    )

    totals = buyers.aggregate(
        total=Count("pk", distinct=True),
        returning=Count("pk", filter=Q(paid_orders__gt=1), distinct=True),
        average_ltv=Avg("spent"),
    )

    new_buyers = (
        Customer.objects.buyers()
        .filter(orders__paid_at__gte=period.start, orders__paid_at__lt=period.end)
        .distinct()
        .count()
    )

    return {
        "total": totals["total"],
        "returning": totals["returning"],
        "returning_share": (
            Decimal(totals["returning"]) / Decimal(totals["total"]) * 100 if totals["total"] else Decimal("0")
        ),
        "average_ltv": totals["average_ltv"] or Decimal("0"),
        "active": new_buyers,
        "top": list(buyers.order_by("-spent").values("email", "spent", "paid_orders")[:limit]),
    }


def download_rate(period: Period) -> dict:
    """
    How much of what was handed over was actually collected.

    The counter only exists from the release that added it, so allocations delivered before then
    read as never downloaded. The page says as much next to the figure.
    """

    delivered = Allocation.objects.filter(
        state=Allocation.State.DELIVERED,
        delivered_at__gte=period.start,
        delivered_at__lt=period.end,
    )
    stats = delivered.aggregate(
        total=Count("pk"),
        taken=Count("pk", filter=Q(download_count__gt=0)),
        downloads=Coalesce(Sum("download_count"), 0),
    )
    stats["share"] = Decimal(stats["taken"]) / Decimal(stats["total"]) * 100 if stats["total"] else Decimal("0")

    return stats
