"""
What the dashboard's numbers mean.

Kept apart from `tests.py` because these hold the arithmetic, not the checkout invariants: the
page may be rearranged freely, but a figure changing meaning has to break a test here.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Country, Product, StockItem
from customer.models import Customer
from sales import statistics
from sales.models import Allocation, Order, OrderItem, PaymentCallbackLog, Transaction
from sales.statistics import Period


class StatisticsFactoryMixin:
    def setUp(self):
        self.country = Country.objects.create(name="Testland", code="tl")
        self.product = Product.objects.create(name="Test passport", country=self.country, price=10)
        self.customer = Customer.objects.create(email="buyer@example.com")

        # A fixed window, so nothing here depends on when the suite runs.
        self.start = datetime(2026, 3, 1, tzinfo=UTC)
        self.end = datetime(2026, 3, 31, tzinfo=UTC)
        self.period = Period(start=self.start, end=self.end)

    def make_stock(self, count: int, product: Product | None = None):
        product = product or self.product
        for i in range(count):
            StockItem.objects.create(file=f"products/{product.pk}-{i}-{StockItem.objects.count()}.pdf", product=product)

    def make_sale(
        self,
        paid_at,
        price="10",
        quantity=1,
        customer=None,
        product=None,
        created_at=None,
    ) -> Order:
        """A paid order with one item. auto_now_add ignores what we pass, so dates are set after."""

        order = Order.objects.create(customer=customer or self.customer, total_price=Decimal(price) * quantity)
        Order.objects.filter(pk=order.pk).update(
            status=Order.OrderStatus.PAID,
            created_at=created_at or paid_at,
            paid_at=paid_at,
        )
        OrderItem.objects.create(
            order=order,
            product=product or self.product,
            product_name=(product or self.product).name,
            unit_price=Decimal(price),
            unit_price_usd=Decimal(price),
            quantity=quantity,
        )
        return Order.objects.get(pk=order.pk)

    def make_invoice(self, order, commission="0.001", rate="0.0005", status=Transaction.TransactionStatus.COMPLETED):
        return Transaction.objects.create(
            order=order,
            txn_id=f"txn-{order.pk}-{Transaction.objects.count()}",
            amount=Decimal("0.05"),
            currency="BTC",
            status=status,
            commission=Decimal(commission) if commission is not None else None,
            source_rate=Decimal(rate) if rate is not None else None,
        )


class PeriodBoundaryTests(StatisticsFactoryMixin, TestCase):
    """The range is half-open: `start` is inside, `end` is not."""

    def test_an_order_paid_exactly_at_the_start_counts(self):
        self.make_sale(self.start)

        self.assertEqual(statistics.money_totals(self.period).orders, 1)

    def test_an_order_paid_exactly_at_the_end_does_not(self):
        self.make_sale(self.end)

        self.assertEqual(statistics.money_totals(self.period).orders, 0)

    def test_an_unpaid_order_is_not_revenue(self):
        order = Order.objects.create(customer=self.customer, total_price=10)
        Order.objects.filter(pk=order.pk).update(created_at=self.start)
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            unit_price=10,
            unit_price_usd=10,
            quantity=1,
        )

        totals = statistics.money_totals(self.period)

        self.assertEqual(totals.gross, Decimal("0"))
        self.assertEqual(totals.orders, 0)
        # It is still a checkout, so the funnel sees it and the conversion drops.
        self.assertEqual(statistics.funnel(self.period).created, 1)
        self.assertEqual(statistics.funnel(self.period).conversion, Decimal("0"))


class RevenueTests(StatisticsFactoryMixin, TestCase):
    def test_gross_is_the_price_snapshot_times_quantity(self):
        self.make_sale(self.start + timedelta(days=1), price="12.50", quantity=3)

        self.assertEqual(statistics.money_totals(self.period).gross, Decimal("37.50"))

    def test_a_catalogue_price_change_does_not_move_past_revenue(self):
        self.make_sale(self.start + timedelta(days=1), price="10")

        self.product.price = 999
        self.product.save(update_fields=["price"])

        self.assertEqual(statistics.money_totals(self.period).gross, Decimal("10"))

    def test_days_without_sales_are_present_as_zero(self):
        self.make_sale(self.start + timedelta(days=2))

        days = statistics.revenue_by_day(self.period)

        self.assertEqual(len(days), 30)
        self.assertEqual(days[0]["revenue"], Decimal("0"))
        self.assertEqual(days[2]["revenue"], Decimal("10"))

    def test_the_trend_line_starts_only_once_the_window_is_full(self):
        # One 70-dollar day, then nothing: the trend has to spread it over the window, not spike.
        self.make_sale(self.start, price="70")
        rows = statistics.revenue_by_day(self.period)

        trend = statistics.moving_average(rows, window=7)

        self.assertEqual(trend[:6], [None] * 6)
        self.assertEqual(trend[6], Decimal(10))
        self.assertEqual(trend[7], Decimal(0))

    def test_an_empty_period_has_no_averages_to_divide(self):
        totals = statistics.money_totals(self.period)

        self.assertEqual(totals.gross, Decimal("0"))
        self.assertEqual(totals.average_order, Decimal("0"))
        self.assertEqual(totals.commission_share, Decimal("0"))
        self.assertEqual(totals.net, Decimal("0"))


class CommissionTests(StatisticsFactoryMixin, TestCase):
    """
    Plisio reports the commission in the invoice's cryptocurrency; source_rate makes it USD.

    The rate is how much crypto one dollar buys, so the conversion divides. Every case below uses
    0.002 of a coin at 0.0005 per dollar, which is $4 - a rate above one would come out the same
    under either operation and would prove nothing.
    """

    def test_commission_is_converted_through_the_source_rate(self):
        self.make_invoice(self.make_sale(self.start + timedelta(days=1)), commission="0.002", rate="0.0005")

        self.assertEqual(statistics.money_totals(self.period).commission, Decimal("4.00"))

    def test_a_currency_switch_is_charged_once(self):
        """Switching coin mints a second invoice for the same order; only the completed one paid."""

        order = self.make_sale(self.start + timedelta(days=1))
        self.make_invoice(order, commission="0.002", rate="0.0005")
        cancelled = Transaction.TransactionStatus.CANCELLED_DUPLICATE
        self.make_invoice(order, commission="0.5", rate="0.004", status=cancelled)

        self.assertEqual(statistics.money_totals(self.period).commission, Decimal("4.00"))

    def test_an_overpaid_invoice_pays_a_commission_like_any_other(self):
        """Its revenue is in gross - `mismatch` is delivered and stamped paid - so its fee counts."""

        mismatch = Transaction.TransactionStatus.MISMATCH
        self.make_invoice(self.make_sale(self.start + timedelta(days=1)), commission="0.002", status=mismatch)

        self.assertEqual(statistics.money_totals(self.period).commission, Decimal("4.00"))

    def test_an_invoice_without_a_commission_is_left_out_not_counted_as_free(self):
        self.make_invoice(self.make_sale(self.start + timedelta(days=1)), commission=None)
        self.make_invoice(self.make_sale(self.start + timedelta(days=2)), commission="0.002", rate="0.0005")

        self.assertEqual(statistics.money_totals(self.period).commission, Decimal("4.00"))

    def test_an_invoice_without_a_rate_is_left_out_too(self):
        self.make_invoice(self.make_sale(self.start + timedelta(days=1)), commission="0.002", rate=None)

        self.assertEqual(statistics.money_totals(self.period).commission, Decimal("0"))

    def test_a_zero_rate_is_left_out_rather_than_dividing_by_it(self):
        self.make_invoice(self.make_sale(self.start + timedelta(days=1)), commission="0.002", rate="0")

        self.assertEqual(statistics.money_totals(self.period).commission, Decimal("0"))

    def test_net_is_gross_minus_commission(self):
        self.make_invoice(self.make_sale(self.start + timedelta(days=1)), commission="0.002", rate="0.0005")

        totals = statistics.money_totals(self.period)

        self.assertEqual(totals.net, totals.gross - totals.commission)


class TopListTests(StatisticsFactoryMixin, TestCase):
    def test_products_are_grouped_by_the_name_they_were_sold_under(self):
        self.make_sale(self.start + timedelta(days=1), quantity=2)
        self.product.name = "Renamed afterwards"
        self.product.save(update_fields=["name"])
        self.make_sale(self.start + timedelta(days=2), quantity=1)

        rows = statistics.top_products(self.period)

        self.assertEqual(
            {row["product_name"]: row["units"] for row in rows},
            {"Test passport": 2, "Renamed afterwards": 1},
        )

    def test_countries_add_up_across_products(self):
        other = Product.objects.create(name="Second", country=self.country, price=5)
        self.make_sale(self.start + timedelta(days=1), price="10")
        self.make_sale(self.start + timedelta(days=2), price="5", product=other)

        rows = statistics.top_countries(self.period)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["revenue"], Decimal("15"))


class StockForecastTests(StatisticsFactoryMixin, TestCase):
    def test_days_left_follows_the_recent_sales_rate(self):
        now = timezone.now()
        self.make_stock(30)
        # One sale a day over the 30-day window, so 30 units left is exactly 30 days of runway.
        # The orders carry no allocations, so nothing is taken off the shelf here.
        for day in range(30):
            self.make_sale(now - timedelta(days=day, hours=1))

        row = next(row for row in statistics.stock_forecast(now) if row["product"] == self.product.name)

        self.assertEqual(row["available"], 30)
        self.assertEqual(row["sold"], 30)
        self.assertEqual(row["days_left"], Decimal(30))

    def test_a_product_that_never_sells_has_no_runway_instead_of_a_division_by_zero(self):
        self.make_stock(5)

        row = statistics.stock_forecast(timezone.now())[0]

        self.assertEqual(row["available"], 5)
        self.assertIsNone(row["days_left"])

    def test_sold_out_reads_as_zero_days_not_as_never(self):
        now = timezone.now()
        self.make_stock(1)
        order = self.make_sale(now - timedelta(days=1))
        item = order.items.first()
        item.reserve()
        item.deliver()

        row = statistics.stock_forecast(now)[0]

        self.assertEqual(row["available"], 0)
        self.assertEqual(row["days_left"], Decimal(0))

    def test_a_sold_out_seller_outranks_everything_that_still_has_a_runway(self):
        now = timezone.now()
        stocked = Product.objects.create(name="Still has some", country=self.country, price=10)
        self.make_stock(10, product=stocked)
        self.make_sale(now - timedelta(days=1), product=stocked)
        # Sold its only unit and is still selling: every day it stays empty is a sale not made.
        self.make_stock(1)
        item = self.make_sale(now - timedelta(days=1)).items.first()
        item.reserve()
        item.deliver()

        rows = statistics.stock_forecast(now)

        self.assertEqual(rows[0]["product"], self.product.name)
        self.assertEqual(rows[0]["days_left"], Decimal(0))
        self.assertEqual(rows[1]["product"], stocked.name)

    def test_nothing_selling_sinks_below_the_runways_and_empty_shelves_go_last(self):
        # Neither sells, so neither has a runway to compare. The one with stock is money sitting
        # still and worth a look; the empty one is nothing to lose and nothing to buy.
        self.make_stock(5)
        empty = Product.objects.create(name="Sold out and dead", country=self.country, price=10)

        rows = statistics.stock_forecast(timezone.now())

        self.assertEqual([row["product"] for row in rows], [self.product.name, empty.name])
        self.assertIsNone(rows[-1]["days_left"])
        self.assertEqual(rows[-1]["available"], 0)

    def test_the_age_is_of_the_oldest_unit_still_on_the_shelf(self):
        self.make_stock(3)
        oldest = StockItem.objects.first()
        StockItem.objects.filter(pk=oldest.pk).update(created_at=timezone.now() - timedelta(days=40))

        age = statistics.stock_age(timezone.now())

        self.assertEqual(age["available"], 3)
        self.assertEqual(age["oldest_days"], 40)


class TimeToPayTests(StatisticsFactoryMixin, TestCase):
    def pay_after(self, minutes: int):
        paid_at = self.start + timedelta(days=1)
        self.make_sale(paid_at, created_at=paid_at - timedelta(minutes=minutes))

    def test_the_median_of_an_odd_number_of_orders(self):
        for minutes in (10, 20, 30):
            self.pay_after(minutes)

        self.assertEqual(statistics.time_to_pay(self.period)["median"], timedelta(minutes=20))

    def test_the_median_of_an_even_number_of_orders_interpolates(self):
        for minutes in (10, 20, 30, 40):
            self.pay_after(minutes)

        self.assertEqual(statistics.time_to_pay(self.period)["median"], timedelta(minutes=25))

    def test_orders_paid_after_the_reservation_expired_are_flagged(self):
        self.pay_after(10)
        self.pay_after(120)

        stats = statistics.time_to_pay(self.period)

        self.assertEqual(stats["late"], 1)
        self.assertEqual(stats["late_share"], Decimal(50))

    def test_the_median_is_rounded_to_whole_seconds(self):
        # PERCENTILE_CONT interpolates between the two middle orders, and half a microsecond of
        # "time to pay" is noise on the page.
        paid_at = self.start + timedelta(days=1)
        for microseconds in (1, 2, 3, 500001):
            self.make_sale(paid_at, created_at=paid_at - timedelta(minutes=5, microseconds=microseconds))

        stats = statistics.time_to_pay(self.period)

        self.assertEqual(stats["median"].microseconds, 0)
        self.assertEqual(stats["average"].microseconds, 0)

    def test_no_orders_means_no_median_and_no_division(self):
        stats = statistics.time_to_pay(self.period)

        self.assertIsNone(stats["median"])
        self.assertEqual(stats["late_share"], Decimal("0"))


class PaymentStageTests(StatisticsFactoryMixin, TestCase):
    """The split of the wait into new -> pending and pending -> completed."""

    def make_callback(self, order, status, received_at):
        """auto_now_add ignores what we pass, so received_at is set afterwards."""

        log = PaymentCallbackLog.objects.create(
            order=order,
            txn_id=f"txn-{order.pk}",
            payload={"txn_id": f"txn-{order.pk}", "status": status, "order_number": str(order.pk)},
        )
        PaymentCallbackLog.objects.filter(pk=log.pk).update(received_at=received_at)

        return log

    def make_paid_order(self, minutes_to_pending: int, minutes_confirming: int) -> Order:
        created_at = self.start + timedelta(days=1)
        pending_at = created_at + timedelta(minutes=minutes_to_pending)
        paid_at = pending_at + timedelta(minutes=minutes_confirming)

        order = self.make_sale(paid_at, created_at=created_at)
        self.make_callback(order, Transaction.TransactionStatus.PENDING, pending_at)

        return order

    def test_the_two_legs_add_up_to_the_time_to_pay(self):
        self.make_paid_order(minutes_to_pending=10, minutes_confirming=20)

        stages = statistics.payment_stages(self.period)

        self.assertEqual(stages["covered"], 1)
        self.assertEqual(stages["waiting_median"], timedelta(minutes=10))
        self.assertEqual(stages["confirming_median"], timedelta(minutes=20))
        self.assertEqual(
            stages["waiting_median"] + stages["confirming_median"],
            statistics.time_to_pay(self.period)["median"],
        )

    def test_the_median_interpolates_and_the_average_is_its_own_number(self):
        self.make_paid_order(minutes_to_pending=10, minutes_confirming=1)
        self.make_paid_order(minutes_to_pending=20, minutes_confirming=1)
        self.make_paid_order(minutes_to_pending=60, minutes_confirming=1)
        self.make_paid_order(minutes_to_pending=90, minutes_confirming=1)

        stages = statistics.payment_stages(self.period)

        self.assertEqual(stages["waiting_median"], timedelta(minutes=40))
        self.assertEqual(stages["waiting_average"], timedelta(minutes=45))

    def test_pending_internal_counts_as_the_middle_stamp(self):
        created_at = self.start + timedelta(days=1)
        order = self.make_sale(created_at + timedelta(minutes=30), created_at=created_at)
        self.make_callback(order, Transaction.TransactionStatus.PENDING_INTERNAL, created_at + timedelta(minutes=5))

        stages = statistics.payment_stages(self.period)

        self.assertEqual(stages["covered"], 1)
        self.assertEqual(stages["waiting_median"], timedelta(minutes=5))

    def test_the_earliest_pending_callback_wins_over_its_repeats(self):
        created_at = self.start + timedelta(days=1)
        order = self.make_sale(created_at + timedelta(minutes=30), created_at=created_at)
        for minutes in (25, 5, 15):
            self.make_callback(order, Transaction.TransactionStatus.PENDING, created_at + timedelta(minutes=minutes))

        stages = statistics.payment_stages(self.period)

        self.assertEqual(stages["waiting_median"], timedelta(minutes=5))
        self.assertEqual(stages["confirming_median"], timedelta(minutes=25))

    def test_an_order_without_a_pending_callback_is_left_out_not_counted_as_instant(self):
        # A payment first seen in a confirmed block skips the state, and old callbacks are pruned.
        created_at = self.start + timedelta(days=1)
        order = self.make_sale(created_at + timedelta(minutes=30), created_at=created_at)
        self.make_callback(order, Transaction.TransactionStatus.COMPLETED, created_at + timedelta(minutes=30))
        self.make_paid_order(minutes_to_pending=10, minutes_confirming=20)

        stages = statistics.payment_stages(self.period)

        self.assertEqual(stages["covered"], 1)
        self.assertEqual(stages["waiting_median"], timedelta(minutes=10))

    def test_a_pending_callback_later_than_the_payment_does_not_go_negative(self):
        created_at = self.start + timedelta(days=1)
        paid_at = created_at + timedelta(minutes=30)
        order = self.make_sale(paid_at, created_at=created_at)
        self.make_callback(order, Transaction.TransactionStatus.PENDING, paid_at + timedelta(minutes=5))

        stages = statistics.payment_stages(self.period)

        self.assertEqual(stages["confirming_median"], timedelta(0))

    def test_no_callbacks_means_no_figures_and_no_division(self):
        self.make_sale(self.start + timedelta(days=1))

        stages = statistics.payment_stages(self.period)

        self.assertEqual(stages["covered"], 0)
        self.assertIsNone(stages["waiting_median"])
        self.assertIsNone(stages["confirming_average"])


class RepeatCustomerTests(StatisticsFactoryMixin, TestCase):
    def test_a_second_order_makes_a_returning_buyer(self):
        other = Customer.objects.create(email="second@example.com")
        self.make_sale(self.start + timedelta(days=1), price="10")
        self.make_sale(self.start + timedelta(days=2), price="30")
        self.make_sale(self.start + timedelta(days=3), price="20", customer=other)

        stats = statistics.repeat_customers(self.period)

        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["returning"], 1)
        self.assertEqual(stats["returning_share"], Decimal(50))
        self.assertEqual(stats["average_ltv"], Decimal("30.00"))
        self.assertEqual(stats["top"][0]["email"], self.customer.email)
        self.assertEqual(stats["top"][0]["spent"], Decimal("40.00"))

    def test_someone_who_never_paid_is_not_a_buyer(self):
        Customer.objects.create(email="lead@example.com")

        self.assertEqual(statistics.repeat_customers(self.period)["total"], 0)


class DownloadRateTests(StatisticsFactoryMixin, TestCase):
    def deliver(self, downloads: int):
        self.make_stock(1)
        order = self.make_sale(self.start + timedelta(days=1))
        item = order.items.first()
        item.reserve()
        allocation = item.deliver()[0]
        Allocation.objects.filter(pk=allocation.pk).update(
            delivered_at=self.start + timedelta(days=1),
            download_count=downloads,
        )

    def test_the_share_is_of_files_taken_not_of_downloads(self):
        self.deliver(0)
        self.deliver(3)

        stats = statistics.download_rate(self.period)

        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["taken"], 1)
        self.assertEqual(stats["downloads"], 3)
        self.assertEqual(stats["share"], Decimal(50))

    def test_nothing_delivered_does_not_divide_by_zero(self):
        self.assertEqual(statistics.download_rate(self.period)["share"], Decimal("0"))


class StaffClientMixin(StatisticsFactoryMixin):
    def setUp(self):
        super().setUp()
        self.url = reverse("admin:stats")
        self.client.force_login(User.objects.create_user("staff", password="pw", is_staff=True, is_superuser=True))


class AllTimePeriodTests(StaffClientMixin, TestCase):
    def test_all_time_starts_on_the_day_of_the_first_sale(self):
        first = timezone.now() - timedelta(days=200)
        self.make_sale(first)
        self.make_sale(timezone.now() - timedelta(days=1))

        period = self.client.get(self.url, {"preset": "all"}).context["period"]

        self.assertEqual(period.start.date(), first.date())

    def test_all_time_on_a_shop_that_never_sold_anything_is_the_default_window(self):
        period = self.client.get(self.url, {"preset": "all"}).context["period"]

        self.assertEqual(period.days, 30)


class ChartLinkTests(StaffClientMixin, TestCase):
    def test_a_point_links_to_the_orders_paid_that_day(self):
        today = self.make_sale(timezone.now())
        self.make_sale(timezone.now() - timedelta(days=3))

        chart = self.client.get(self.url).context["chart"]
        # The changelist has to accept the lookups the link carries - it only does because
        # `paid_at` is in OrderAdmin.list_filter, and this is the test that notices if it goes.
        changelist = self.client.get(chart["links"][-1])

        self.assertEqual(changelist.status_code, 200)
        self.assertEqual([order.pk for order in changelist.context["cl"].result_list], [today.pk])


class StockPaginationTests(StaffClientMixin, TestCase):
    def setUp(self):
        super().setUp()
        for i in range(25):
            self.make_stock(1, product=Product.objects.create(name=f"Product {i}", country=self.country, price=10))

    def test_the_forecast_is_paginated_not_truncated(self):
        first = self.client.get(self.url).context["stock_page"]
        second = self.client.get(self.url, {"stock_page": "2"}).context["stock_page"]

        # 25 products with stock, plus the mixin's own, which has none.
        self.assertEqual(first.paginator.count, 26)
        self.assertEqual(len(first.object_list), 20)
        self.assertEqual(len(second.object_list), 6)
        self.assertNotEqual(first.object_list[0]["product"], second.object_list[0]["product"])

    def test_a_page_that_does_not_exist_shows_the_last_one(self):
        page = self.client.get(self.url, {"stock_page": "nonsense"}).context["stock_page"]
        beyond = self.client.get(self.url, {"stock_page": "99"}).context["stock_page"]

        self.assertEqual(page.number, 1)
        self.assertEqual(beyond.number, 2)

    def test_paging_keeps_the_period(self):
        response = self.client.get(self.url, {"preset": "7"})

        second = next(item for item in response.context["stock_page_numbers"] if item["number"] == 2)

        self.assertIn("preset=7", second["url"])
        self.assertIn("stock_page=2", second["url"])


class StatisticsPageTests(TestCase):
    """The page itself: who may open it, and that the period parser cannot be tripped up."""

    def setUp(self):
        self.url = reverse("admin:stats")
        self.export_url = reverse("admin:stats-export")
        self.staff = User.objects.create_user("staff", password="pw", is_staff=True, is_superuser=True)

    def test_an_anonymous_visitor_is_sent_to_the_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_staff_get_the_page(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/sales/statistics.html")

    def test_the_dashboard_is_linked_from_the_admin_index(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("admin:index"))

        self.assertContains(response, self.url)

    def test_a_nonsense_preset_falls_back_to_the_default(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.url, {"preset": "'; DROP TABLE"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["period"].preset, "30")

    def test_a_backwards_custom_range_falls_back_too(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.url, {"from": "2026-03-31", "to": "2026-03-01"})

        self.assertEqual(response.context["period"].preset, "30")

    def test_a_custom_range_includes_its_last_day(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.url, {"from": "2026-03-01", "to": "2026-03-31"})
        period = response.context["period"]

        self.assertEqual(period.preset, "custom")
        self.assertEqual(period.last_day.isoformat(), "2026-03-31")
        self.assertEqual(period.end, datetime(2026, 4, 1, tzinfo=UTC))

    def test_the_csv_carries_a_bom_and_the_totals(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.export_url, {"preset": "7"})
        body = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertTrue(body.startswith("﻿"), "Excel needs the BOM to read UTF-8")
        self.assertIn("Revenue by day (UTC)", body)
        self.assertIn("plisio_commission_usd", body)


class CsvCoverageTests(StaffClientMixin, TestCase):
    """The page is cut down to what fits a screen; the export is not."""

    def test_every_product_sold_is_in_the_export_not_just_the_top_ten(self):
        for i in range(12):
            product = Product.objects.create(name=f"Product {i}", country=self.country, price=10)
            self.make_sale(timezone.now() - timedelta(days=1), product=product, price=str(i + 1))

        body = self.client.get(reverse("admin:stats-export")).content.decode("utf-8")

        for i in range(12):
            self.assertIn(f"Product {i}", body)

    def test_the_export_carries_the_whole_stock_forecast(self):
        self.make_stock(3, product=Product.objects.create(name="Never sold", country=self.country, price=10))

        body = self.client.get(reverse("admin:stats-export")).content.decode("utf-8")

        self.assertIn("Stock right now", body)
        # Nothing selling has no runway, and the cell is left empty rather than reading as zero.
        self.assertIn("Never sold,Testland,3,0,\r\n", body)
