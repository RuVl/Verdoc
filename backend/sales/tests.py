from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from catalog.models import Country, Product, StockItem
from customer.models import Customer
from sales.models import Allocation, Order, OrderItem


class OrderItemFactoryMixin:
    def make_product(self, stock: int, name: str = "Test") -> Product:
        product = Product.objects.create(name=name, country=self.country, price=10)
        for i in range(stock):
            StockItem.objects.create(file=f"products/{name}-{i}.pdf", product=product)
        return product

    def make_item(self, product: Product, quantity: int = 1, order: Order | None = None) -> OrderItem:
        return OrderItem.objects.create(
            order=order or self.order,
            product=product,
            product_name=product.name,
            unit_price=product.price,
            unit_price_usd=10,
            quantity=quantity,
        )

    def setUp(self):
        self.country = Country.objects.create(name="Testland", code="tl")
        self.customer = Customer.objects.create(email="buyer@example.com")
        self.order = Order.objects.create(customer=self.customer, total_price=10)


class ReserveTests(OrderItemFactoryMixin, TestCase):
    def test_reserve_takes_exactly_the_wanted_quantity(self):
        item = self.make_item(self.make_product(3), quantity=2)

        allocations = item.reserve()

        self.assertEqual(len(allocations), 2)
        self.assertTrue(all(a.state == Allocation.State.RESERVED for a in allocations))
        self.assertTrue(all(a.delivered_at is None and a.token is None for a in allocations))

    def test_reserve_more_than_stock_raises(self):
        item = self.make_item(self.make_product(1), quantity=5)

        with self.assertRaises(ValueError):
            item.reserve()

        self.assertEqual(Allocation.objects.count(), 0)

    def test_reserve_twice_raises(self):
        item = self.make_item(self.make_product(3), quantity=1)
        item.reserve()

        with self.assertRaises(ValueError):
            item.reserve()

        self.assertEqual(item.allocations.count(), 1)


class DeliverTests(OrderItemFactoryMixin, TestCase):
    def test_deliver_issues_a_token_per_unit(self):
        item = self.make_item(self.make_product(3), quantity=2)
        item.reserve()

        allocations = item.deliver()

        self.assertEqual(len(allocations), 2)
        self.assertTrue(all(a.state == Allocation.State.DELIVERED for a in allocations))
        self.assertTrue(all(a.is_token_valid() for a in allocations))
        self.assertEqual(len({a.token for a in allocations}), 2)

    def test_deliver_is_idempotent(self):
        item = self.make_item(self.make_product(3), quantity=2)
        item.reserve()

        first = item.deliver()
        second = item.deliver()

        self.assertEqual(len(second), 2)
        self.assertEqual(Allocation.objects.filter(state=Allocation.State.DELIVERED).count(), 2)
        self.assertEqual({a.token for a in first}, {a.token for a in second})

    def test_deliver_after_released_reservation_allocates_again(self):
        """Regression, incident 2026-07-28: the invoice expired and released the reservation, then
        the crypto payment confirmed hours later. The late callback must deliver anyway."""

        product = self.make_product(2)
        item = self.make_item(product, quantity=1)
        item.reserve()
        item.release()

        allocations = item.deliver()

        self.assertEqual(len(allocations), 1)
        self.assertEqual(allocations[0].state, Allocation.State.DELIVERED)
        self.assertTrue(allocations[0].is_token_valid())
        self.assertEqual(product.available_count(), 1)

    def test_deliver_after_released_reservation_raises_when_out_of_stock(self):
        product = self.make_product(1)
        item = self.make_item(product, quantity=1)
        item.reserve()
        item.release()

        # Everything got resold while the payment was pending.
        other_order = Order.objects.create(customer=self.customer, total_price=10)
        self.make_item(product, quantity=1, order=other_order).reserve()

        with self.assertRaises(ValueError):
            item.deliver()

        self.assertEqual(item.allocations.filter(state=Allocation.State.DELIVERED).count(), 0)

    def test_deliver_tops_up_a_partially_delivered_item(self):
        """The old schema could leave an order paid with fewer files than bought - now the missing
        units are simply allocated on the next delivery."""

        product = self.make_product(3)
        item = self.make_item(product, quantity=2)
        item.reserve()
        item.allocations.first().delete()  # simulate a half-finished legacy sale

        allocations = item.deliver()

        self.assertEqual(len(allocations), 2)
        self.assertEqual(item.allocations.filter(state=Allocation.State.DELIVERED).count(), 2)


class ReleaseTests(OrderItemFactoryMixin, TestCase):
    def test_release_returns_units_to_stock(self):
        product = self.make_product(3)
        item = self.make_item(product, quantity=2)
        item.reserve()

        released = item.release()

        self.assertEqual(len(released), 2)
        self.assertEqual(product.available_count(), 3)

    def test_release_is_idempotent(self):
        item = self.make_item(self.make_product(3), quantity=2)
        item.reserve()
        item.release()

        self.assertEqual(item.release(), [])

    def test_release_does_not_touch_delivered_units(self):
        product = self.make_product(3)
        item = self.make_item(product, quantity=1)
        item.reserve()
        item.deliver()

        self.assertEqual(item.release(), [])
        self.assertEqual(item.allocations.filter(state=Allocation.State.DELIVERED).count(), 1)
        self.assertEqual(product.available_count(), 2)


class OrderStateTests(OrderItemFactoryMixin, TestCase):
    def test_mark_paid_stamps_once(self):
        self.assertTrue(self.order.mark_paid())
        stamped_at = self.order.paid_at

        self.assertFalse(self.order.mark_paid())
        self.order.refresh_from_db()
        self.assertEqual(self.order.paid_at, stamped_at)

    def test_order_deliver_covers_every_item(self):
        self.make_item(self.make_product(2, name="A"), quantity=2).reserve()
        self.make_item(self.make_product(1, name="B"), quantity=1).reserve()

        allocations = self.order.deliver()

        self.assertEqual(len(allocations), 3)
        self.assertTrue(all(a.is_token_valid() for a in allocations))

    def test_order_release_covers_every_item(self):
        product_a = self.make_product(2, name="A")
        product_b = self.make_product(1, name="B")
        self.make_item(product_a, quantity=2).reserve()
        self.make_item(product_b, quantity=1).reserve()

        self.order.release()

        self.assertEqual(product_a.available_count(), 2)
        self.assertEqual(product_b.available_count(), 1)

    def test_refresh_download_tokens_rotates_delivered_only(self):
        item = self.make_item(self.make_product(2), quantity=1)
        item.reserve()
        delivered = item.deliver()[0]
        old_token = delivered.token

        refreshed = self.order.refresh_download_tokens()

        self.assertEqual(len(refreshed), 1)
        self.assertNotEqual(refreshed[0].token, old_token)
        self.assertTrue(refreshed[0].is_token_valid())

    def test_expired_token_is_invalid(self):
        item = self.make_item(self.make_product(2), quantity=1)
        item.reserve()
        allocation = item.deliver()[0]

        allocation.token_expires_at = timezone.now() - timedelta(seconds=1)

        self.assertFalse(allocation.is_token_valid())
