import hashlib
import hmac
import json

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from order.models import DownloadLink, Order, OrderItem
from passport.models import Country, Passport, PassportFile


def sign_plisio_payload(data: dict) -> dict:
    ordered_data = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    verify_hash = hmac.new(settings.PLISIO_SECRET_KEY.encode(), ordered_data.encode(), hashlib.sha1).hexdigest()
    return {**data, "verify_hash": verify_hash}


class OrderSellIntegrationTests(TestCase):
    """Integration-style: checkout reserve -> payment callback sell -> DownloadLink."""

    def setUp(self):
        country = Country.objects.create(name="Testland", code="tl")
        self.passport = Passport.objects.create(name="Test", country=country, price=10)
        PassportFile.objects.create(file_path="products/passports/a.pdf", passport=self.passport)

    def test_full_reserve_then_sell_creates_download_link(self):
        order = Order.objects.create(user_email="buyer@example.com", total_price=10)
        item = OrderItem.objects.create(order=order, passport=self.passport, quantity=1)

        item.reserve()
        self.passport.refresh_from_db()
        self.assertEqual(self.passport.quantity, 0)
        self.assertTrue(item.is_reserved)

        links = item.sell()

        self.assertEqual(len(links), 1)
        self.assertFalse(item.is_reserved)

    def test_reserve_twice_raises(self):
        order = Order.objects.create(user_email="buyer@example.com", total_price=10)
        item = OrderItem.objects.create(order=order, passport=self.passport, quantity=1)
        item.reserve()

        with self.assertRaises(ValueError):
            item.reserve()

    def test_reset_reservation_returns_files_to_stock(self):
        order = Order.objects.create(user_email="buyer@example.com", total_price=10)
        item = OrderItem.objects.create(order=order, passport=self.passport, quantity=1)
        item.reserve()

        item.reset_reservation()

        self.passport.refresh_from_db()
        self.assertEqual(self.passport.quantity, 1)
        self.assertFalse(item.is_reserved)


class LatePaymentTests(TestCase):
    """Regression test for the 2026-07-28 incident: the Plisio invoice expires after 60 min and
    releases the reservation, then the crypto payment confirms hours later. The late PAID callback
    must re-reserve from stock instead of leaving the order paid-but-undelivered."""

    def setUp(self):
        country = Country.objects.create(name="Testland", code="tl")
        self.passport = Passport.objects.create(name="Test", country=country, price=10)
        for i in range(2):
            PassportFile.objects.create(file_path=f"products/passports/{i}.pdf", passport=self.passport)

        self.order = Order.objects.create(user_email="buyer@example.com", total_price=10)
        self.item = OrderItem.objects.create(order=self.order, passport=self.passport, quantity=1)

    def test_sell_after_expired_reservation_reserves_again(self):
        self.item.reserve()
        self.item.reset_reservation()  # invoice expired callback

        links = self.item.sell()  # late "completed" callback

        self.assertEqual(len(links), 1)
        self.assertEqual(DownloadLink.objects.filter(order_item=self.item).count(), 1)
        self.passport.refresh_from_db()
        self.assertEqual(self.passport.quantity, 1)

    def test_sell_after_expired_reservation_raises_when_out_of_stock(self):
        self.item.reserve()
        self.item.reset_reservation()
        self.passport.refresh_from_db()
        self.passport.reserve(2)  # everything got resold while the payment was pending

        with self.assertRaises(ValueError):
            self.item.sell()

        self.assertEqual(DownloadLink.objects.filter(order_item=self.item).count(), 0)


class PlisioCallbackIdempotencyTests(TestCase):
    """Regression test for the 2026-07-28 incident: a duplicate PAID callback must not
    leave the order stuck - see docs/incidents/2026-07-28-order-652-stuck-paid-order.md."""

    def setUp(self):
        country = Country.objects.create(name="Testland", code="tl")
        self.passport = Passport.objects.create(name="Test", country=country, price=10)
        PassportFile.objects.create(file_path="products/passports/a.pdf", passport=self.passport)

        self.order = Order.objects.create(user_email="buyer@example.com", total_price=10)
        self.item = OrderItem.objects.create(order=self.order, passport=self.passport, quantity=1)
        self.item.reserve()

        self.client = APIClient()
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

    def test_duplicate_paid_callback_does_not_crash_or_duplicate_links(self):
        url = reverse("plisio-callback")

        first = self.client.post(url, sign_plisio_payload(self.payload), format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(DownloadLink.objects.filter(order_item=self.item).count(), 1)

        second = self.client.post(url, sign_plisio_payload(self.payload), format="json")

        self.assertEqual(second.status_code, 409)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.OrderStatus.PAID)
        self.assertEqual(DownloadLink.objects.filter(order_item=self.item).count(), 1)
