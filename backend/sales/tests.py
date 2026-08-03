import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from unittest.mock import patch

import dns.resolver
import requests
from django.conf import settings
from django.contrib.sites.models import Site
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.db.models import ProtectedError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from catalog.models import Country, Product, StockItem
from customer.models import Customer
from sales.models import Allocation, Order, OrderItem, PaymentCallbackLog, Transaction
from sales.utils import send_download_links


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


def sign_plisio_payload(data: dict) -> dict:
    ordered_data = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    verify_hash = hmac.new(settings.PLISIO_SECRET_KEY.encode(), ordered_data.encode(), hashlib.sha1).hexdigest()
    return {**data, "verify_hash": verify_hash}


class PlisioCallbackTests(OrderItemFactoryMixin, TestCase):
    """The callback is the part that broke in the 2026-07-28 incident."""

    def setUp(self):
        super().setUp()
        self.product = self.make_product(2)
        self.item = self.make_item(self.product, quantity=1)
        self.item.reserve()

        self.client = APIClient()
        self.url = reverse("plisio-callback")
        self.payload = {
            "order_number": str(self.order.id),
            "status": "completed",
            "txn_id": "txn-1",
            "amount": "0.0005",
            "currency": "BTC",
            "merchant": "Verdoc",
            "merchant_id": "1",
            "comment": "",
        }

    def post_callback(self, **overrides):
        return self.client.post(self.url, sign_plisio_payload({**self.payload, **overrides}), format="json")

    def test_paid_callback_delivers_and_emails_once(self):
        response = self.post_callback()

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.PAID)
        self.assertIsNotNone(self.order.paid_at)
        self.assertEqual(self.item.allocations.filter(state=Allocation.State.DELIVERED).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_duplicate_callback_is_absorbed(self):
        """It used to answer 409 and roll the whole thing back; now the second one is simply a no-op."""

        self.post_callback()
        second = self.post_callback()

        self.assertEqual(second.status_code, 200)
        self.assertEqual(self.item.allocations.filter(state=Allocation.State.DELIVERED).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_late_callback_after_expiry_still_delivers(self):
        self.post_callback(status="expired", txn_id="txn-expired")
        self.assertEqual(self.item.allocations.filter(state=Allocation.State.RELEASED).count(), 1)

        response = self.post_callback()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.item.allocations.filter(state=Allocation.State.DELIVERED).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_late_callback_returns_409_when_stock_ran_out(self):
        self.post_callback(status="expired", txn_id="txn-expired")

        # Both units get sold to somebody else while the payment was pending.
        other_order = Order.objects.create(customer=self.customer, total_price=10)
        self.make_item(self.product, quantity=2, order=other_order).reserve()

        response = self.post_callback()

        self.assertEqual(response.status_code, 409)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.EXPIRED)  # rolled back
        self.assertEqual(len(mail.outbox), 0)

    def test_currency_switch_keeps_both_invoices(self):
        """Plisio mints a new invoice on a currency switch - the old schema overwrote it."""

        self.post_callback(status="cancelled duplicate", txn_id="txn-btc")
        self.post_callback(txn_id="txn-ltc")

        self.assertEqual(Transaction.objects.filter(order=self.order).count(), 2)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.PAID)

    def test_every_callback_is_logged_without_the_hash(self):
        self.post_callback()

        log = PaymentCallbackLog.objects.get()
        self.assertEqual(log.order_id, self.order.id)
        self.assertEqual(log.txn_id, "txn-1")
        self.assertNotIn("verify_hash", log.payload)

    def test_bad_hash_is_rejected(self):
        response = self.client.post(self.url, {**self.payload, "verify_hash": "nope"}, format="json")

        self.assertEqual(response.status_code, 422)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.PENDING)

    def test_unknown_order_is_logged_and_404(self):
        response = self.post_callback(order_number="999999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(PaymentCallbackLog.objects.filter(order__isnull=True).count(), 1)


class DownloadTests(OrderItemFactoryMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.item = self.make_item(self.make_product(1), quantity=1)
        self.item.reserve()
        self.allocation = self.item.deliver()[0]

    def download(self, email: str, token) -> int:
        return self.client.get(reverse("download-file", args=[email, token])).status_code

    def test_expired_token_is_not_served(self):
        self.allocation.token_expires_at = timezone.now() - timedelta(seconds=1)
        self.allocation.save(update_fields=["token_expires_at"])

        self.assertEqual(self.download(self.customer.email, self.allocation.token), 404)

    def test_someone_elses_email_is_not_served(self):
        self.assertEqual(self.download("other@example.com", self.allocation.token), 404)

    def test_unknown_token_is_not_served(self):
        self.assertEqual(self.download(self.customer.email, uuid.uuid4()), 404)

    def test_malformed_token_is_not_served(self):
        self.assertEqual(self.download(self.customer.email, "not-a-uuid"), 404)


class SendDownloadLinksTests(OrderItemFactoryMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.item = self.make_item(self.make_product(2), quantity=1)
        self.item.reserve()
        self.item.deliver()
        self.order.status = Order.OrderStatus.PAID
        self.order.save(update_fields=["status"])

        self.client = APIClient()
        self.url = reverse("send-links")

    def test_links_are_reissued_and_emailed(self):
        old_token = self.item.allocations.get().token

        response = self.client.post(self.url, {"email": self.customer.email}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotEqual(self.item.allocations.get().token, old_token)

    def test_undelivered_paid_item_is_topped_up(self):
        """The blind "grab any sold file" workaround is gone: missing units are allocated properly."""

        self.item.allocations.all().delete()

        response = self.client.post(self.url, {"email": self.customer.email}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.item.allocations.filter(state=Allocation.State.DELIVERED).count(), 1)

    def test_unknown_email_is_404(self):
        response = self.client.post(self.url, {"email": "nobody@example.com"}, format="json")

        self.assertEqual(response.status_code, 404)


@override_settings(VALIDATE_EMAIL_MX=False)
class CheckoutTests(OrderItemFactoryMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.product = self.make_product(3)
        self.client = APIClient()
        self.url = reverse("order-create")

    def payload(self, quantity: int = 2):
        return {
            "user_email": "new@example.com",
            "items": [{"passport_id": self.product.id, "quantity": quantity}],
        }

    def test_order_over_stock_is_rejected(self):
        response = self.client.post(self.url, self.payload(quantity=99), format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Allocation.objects.count(), 0)

    def test_checkout_reserves_and_snapshots(self):
        with patch("sales.views.requests.get") as plisio:
            plisio.return_value.status_code = 200
            plisio.return_value.json.return_value = {
                "status": "success",
                "data": {"invoice_url": "https://plisio.net/invoice/1"},
            }

            response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["redirect_url"], "https://plisio.net/invoice/1")

        item = OrderItem.objects.get(order__customer__email="new@example.com")
        self.assertEqual(item.product_name, self.product.name)
        self.assertEqual(item.unit_price, self.product.price)
        self.assertEqual(item.allocations.filter(state=Allocation.State.RESERVED).count(), 2)
        self.assertEqual(self.product.available_count(), 1)

    def test_failed_invoice_releases_everything(self):
        with patch("sales.views.requests.get") as plisio:
            plisio.return_value.status_code = 500
            plisio.return_value.json.return_value = {"status": "error"}

            with self.assertLogs("sales.views", level="ERROR"):
                response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(Order.objects.filter(customer__email="new@example.com").count(), 0)
        self.assertEqual(self.product.available_count(), 3)

    def test_failed_invoice_passes_the_provider_reason_on(self):
        with patch("sales.views.requests.get") as plisio:
            plisio.return_value.status_code = 200
            plisio.return_value.json.return_value = {
                "status": "error",
                "data": {"message": "Shop is not active", "code": 401},
            }

            with self.assertLogs("sales.views", level="ERROR"):
                response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Shop is not active")
        self.assertEqual(response.data["code"], "invoice_failed")
        self.assertEqual(response.data["provider_code"], 401)

    def test_unreachable_plisio_does_not_leave_a_reservation(self):
        with (
            patch("sales.views.requests.get", side_effect=requests.ConnectionError("no route")),
            self.assertLogs("sales.views", level="ERROR"),
        ):
            response = self.client.post(self.url, self.payload(), format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Error creating invoice")
        self.assertEqual(Order.objects.filter(customer__email="new@example.com").count(), 0)
        self.assertEqual(self.product.available_count(), 3)


@override_settings(VALIDATE_EMAIL_MX=False)
class CheckoutReuseTests(OrderItemFactoryMixin, TestCase):
    """A repeated checkout of the same cart must land on the same invoice, not reserve a second copy."""

    def setUp(self):
        super().setUp()
        self.product = self.make_product(3)
        self.client = APIClient()
        self.url = reverse("order-create")

    def payload(self, quantity: int = 1, product: Product | None = None):
        return {
            "user_email": "new@example.com",
            "items": [{"passport_id": (product or self.product).id, "quantity": quantity}],
        }

    def checkout(self, payload, invoice_url: str = "https://plisio.net/invoice/1"):
        with patch("sales.views.requests.get") as plisio:
            plisio.return_value.status_code = 200
            plisio.return_value.json.return_value = {"status": "success", "data": {"invoice_url": invoice_url}}
            response = self.client.post(self.url, payload, format="json")
            return response, plisio

    def test_second_checkout_returns_the_first_invoice(self):
        first, _ = self.checkout(self.payload())
        second, plisio = self.checkout(self.payload(), invoice_url="https://plisio.net/invoice/2")

        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.data["redirect_url"], first.data["redirect_url"])
        plisio.assert_not_called()  # no second invoice was minted
        self.assertEqual(Order.objects.filter(customer__email="new@example.com").count(), 1)
        self.assertEqual(Allocation.objects.count(), 1)
        self.assertEqual(self.product.available_count(), 2)

    def test_reuse_works_when_the_order_holds_the_last_unit(self):
        # The availability check used to refuse the customer their own reservation here.
        product = self.make_product(1, name="Single")
        first, _ = self.checkout(self.payload(product=product))
        second, _ = self.checkout(self.payload(product=product))

        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.data["redirect_url"], first.data["redirect_url"])
        self.assertEqual(Allocation.objects.count(), 1)

    def test_a_different_cart_gets_its_own_order(self):
        self.checkout(self.payload(quantity=1))
        second, plisio = self.checkout(self.payload(quantity=2), invoice_url="https://plisio.net/invoice/2")

        self.assertEqual(second.data["redirect_url"], "https://plisio.net/invoice/2")
        plisio.assert_called_once()
        self.assertEqual(Order.objects.filter(customer__email="new@example.com").count(), 2)
        self.assertEqual(self.product.available_count(), 0)

    def test_a_changed_price_gets_its_own_order(self):
        self.checkout(self.payload())
        Product.objects.filter(pk=self.product.pk).update(price=99)

        second, _ = self.checkout(self.payload(), invoice_url="https://plisio.net/invoice/2")

        self.assertEqual(second.data["redirect_url"], "https://plisio.net/invoice/2")
        self.assertEqual(Order.objects.filter(customer__email="new@example.com").count(), 2)

    def test_an_expired_order_is_not_reused(self):
        self.checkout(self.payload())
        stale = timezone.now() - timedelta(hours=3)
        Order.objects.filter(customer__email="new@example.com").update(created_at=stale, updated_at=stale)

        second, _ = self.checkout(self.payload(), invoice_url="https://plisio.net/invoice/2")

        self.assertEqual(second.data["redirect_url"], "https://plisio.net/invoice/2")
        self.assertEqual(Order.objects.filter(customer__email="new@example.com").count(), 2)

    def test_a_released_order_is_not_reused(self):
        self.checkout(self.payload())
        order = Order.objects.get(customer__email="new@example.com")
        order.release()

        second, _ = self.checkout(self.payload(), invoice_url="https://plisio.net/invoice/2")

        self.assertEqual(second.data["redirect_url"], "https://plisio.net/invoice/2")
        self.assertEqual(Order.objects.filter(customer__email="new@example.com").count(), 2)

    def test_another_customer_does_not_reuse_the_invoice(self):
        self.checkout(self.payload())
        other = self.payload() | {"user_email": "other@example.com"}

        second, plisio = self.checkout(other, invoice_url="https://plisio.net/invoice/2")

        self.assertEqual(second.data["redirect_url"], "https://plisio.net/invoice/2")
        plisio.assert_called_once()
        self.assertEqual(Allocation.objects.count(), 2)

    def test_a_failed_invoice_leaves_nothing_to_reuse(self):
        with patch("sales.views.requests.get") as plisio:
            plisio.return_value.status_code = 500
            plisio.return_value.json.return_value = {"status": "error"}
            self.client.post(self.url, self.payload(), format="json")

        second, plisio = self.checkout(self.payload(), invoice_url="https://plisio.net/invoice/2")

        self.assertEqual(second.data["redirect_url"], "https://plisio.net/invoice/2")
        plisio.assert_called_once()


@override_settings(VALIDATE_EMAIL_MX=False)
class CheckoutLimitTests(OrderItemFactoryMixin, TestCase):
    """One request must not be able to lock a whole product or spawn a huge order."""

    def setUp(self):
        super().setUp()
        self.product = self.make_product(50)
        self.client = APIClient()
        self.url = reverse("order-create")

    def post(self, items):
        return self.client.post(self.url, {"user_email": "new@example.com", "items": items}, format="json")

    @override_settings(VALIDATE_EMAIL_MX=True)
    def test_an_undeliverable_email_domain_is_rejected(self):
        cache.clear()
        with patch.object(dns.resolver.Resolver, "resolve", side_effect=dns.resolver.NXDOMAIN):
            response = self.post([{"passport_id": self.product.id, "quantity": 1}])

        self.assertEqual(response.status_code, 400)
        self.assertIn("user_email", response.data)
        self.assertEqual(Customer.objects.filter(email="new@example.com").count(), 0)

    def test_quantity_over_the_cap_is_rejected(self):
        response = self.post([{"passport_id": self.product.id, "quantity": settings.MAX_ITEM_QUANTITY + 1}])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Allocation.objects.count(), 0)

    def test_zero_quantity_is_rejected(self):
        response = self.post([{"passport_id": self.product.id, "quantity": 0}])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(OrderItem.objects.count(), 0)

    def test_empty_order_is_rejected(self):
        self.assertEqual(self.post([]).status_code, 400)
        self.assertEqual(Order.objects.filter(customer__email="new@example.com").count(), 0)

    def test_too_many_lines_are_rejected(self):
        items = [
            {"passport_id": self.make_product(1, name=f"P{i}").id, "quantity": 1}
            for i in range(settings.MAX_ORDER_ITEMS + 1)
        ]

        self.assertEqual(self.post(items).status_code, 400)
        self.assertEqual(Allocation.objects.count(), 0)

    def test_the_same_product_twice_is_rejected(self):
        # Splitting the cart into two lines used to slip past both the per-item cap and the
        # availability check, which each looked at one line at a time.
        cap = settings.MAX_ITEM_QUANTITY
        response = self.post(
            [
                {"passport_id": self.product.id, "quantity": cap},
                {"passport_id": self.product.id, "quantity": cap},
            ]
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Allocation.objects.count(), 0)


class ExpireCommandTests(OrderItemFactoryMixin, TestCase):
    def test_expired_pending_order_releases_its_units(self):
        product = self.make_product(2)
        item = self.make_item(product, quantity=1)
        item.reserve()
        Order.objects.filter(pk=self.order.pk).update(
            created_at=timezone.now() - timedelta(hours=3),
            updated_at=timezone.now() - timedelta(hours=3),
        )

        call_command("expire_transactions")

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.EXPIRED)
        self.assertEqual(product.available_count(), 2)

    def test_fresh_pending_order_is_left_alone(self):
        product = self.make_product(2)
        self.make_item(product, quantity=1).reserve()

        call_command("expire_transactions")

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.PENDING)
        self.assertEqual(product.available_count(), 1)

    def test_one_broken_order_does_not_hold_up_the_others(self):
        product = self.make_product(4)
        self.make_item(product, quantity=1).reserve()
        other = Order.objects.create(customer=self.customer, total_price=10)
        self.make_item(product, quantity=1, order=other).reserve()

        stale = timezone.now() - timedelta(hours=3)
        Order.objects.all().update(created_at=stale, updated_at=stale)

        def release(self):
            if self.pk == other.pk:
                raise ValueError("boom")
            return original(self)

        original = Order.release
        with patch.object(Order, "release", release), self.assertLogs("sales", level="ERROR"):
            call_command("expire_transactions")

        self.order.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.EXPIRED)
        self.assertEqual(other.status, Order.OrderStatus.PENDING)
        # Only the healthy order gave its unit back; the broken one still holds its own.
        self.assertEqual(product.available_count(), 3)


class StockItemDeletionTests(OrderItemFactoryMixin, TestCase):
    """A unit an order holds is the thing the customer paid for - it must not be deletable."""

    def test_delivered_unit_cannot_be_deleted(self):
        product = self.make_product(1)
        item = self.make_item(product, quantity=1)
        item.reserve()
        item.deliver()
        unit = StockItem.objects.get(product=product)

        with self.assertRaises(ProtectedError), self.assertLogs("sales.models", level="WARNING"):
            unit.delete()

        self.assertTrue(StockItem.objects.filter(pk=unit.pk).exists())

    def test_reserved_unit_cannot_be_deleted(self):
        product = self.make_product(1)
        self.make_item(product, quantity=1).reserve()
        unit = StockItem.objects.get(product=product)

        with self.assertRaises(ProtectedError), self.assertLogs("sales.models", level="WARNING"):
            unit.delete()

        self.assertTrue(StockItem.objects.filter(pk=unit.pk).exists())

    def test_released_unit_can_be_deleted_and_keeps_the_record(self):
        product = self.make_product(1)
        item = self.make_item(product, quantity=1)
        item.reserve()
        item.release()
        unit = StockItem.objects.get(product=product)

        unit.delete()

        allocation = Allocation.objects.get(order_item=item)
        self.assertIsNone(allocation.stock_item_id)
        self.assertEqual(allocation.state, Allocation.State.RELEASED)

    def test_a_free_unit_is_deletable(self):
        product = self.make_product(1)
        unit = StockItem.objects.get(product=product)

        unit.delete()

        self.assertFalse(StockItem.objects.filter(pk=unit.pk).exists())


class DownloadLinkMailTests(OrderItemFactoryMixin, TestCase):
    def setUp(self):
        super().setUp()
        # get_current() resolves either by SITE_ID or by the request host - this covers both.
        Site.objects.update_or_create(pk=1, defaults={"domain": "testserver", "name": "test"})

    def test_a_stale_token_is_reissued_instead_of_breaking_the_mail(self):
        product = self.make_product(1)
        item = self.make_item(product, quantity=1)
        item.reserve()
        allocations = item.deliver()

        expired = timezone.now() - timedelta(hours=1)
        Allocation.objects.filter(pk=allocations[0].pk).update(token_expires_at=expired)
        allocations[0].token_expires_at = expired

        request = RequestFactory().post("/api/send-links/")
        with self.assertLogs("sales.utils", level="WARNING"):
            send_download_links(request, allocations, self.customer.email)

        allocations[0].refresh_from_db()
        self.assertTrue(allocations[0].is_token_valid())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(str(allocations[0].token), mail.outbox[0].body)
