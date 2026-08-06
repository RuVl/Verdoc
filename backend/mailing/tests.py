from django.contrib.sites.models import Site
from django.core import mail, signing
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from customer.models import Customer
from mailing.models import Broadcast
from mailing.services import (
    UNSUBSCRIBE_SALT,
    build_broadcast_email,
    get_broadcast_recipients,
    make_unsubscribe_token,
)
from sales.models import Order


def make_buyer(email: str, **kwargs) -> Customer:
    customer = Customer.objects.create(email=email, **kwargs)
    Order.objects.create(customer=customer, total_price=10, paid_at=timezone.now())
    return customer


class RecipientTests(TestCase):
    """Who gets a broadcast is one query, shared with the admin's "bought something" filter."""

    def test_only_paying_customers_are_included(self):
        make_buyer("buyer@example.com")
        Customer.objects.create(email="lead@example.com")

        self.assertEqual(
            set(get_broadcast_recipients().values_list("email", flat=True)),
            {"buyer@example.com"},
        )

    def test_the_opted_out_are_left_alone(self):
        make_buyer("buyer@example.com")
        make_buyer("quiet@example.com", is_subscribed=False)

        self.assertEqual(
            set(get_broadcast_recipients().values_list("email", flat=True)),
            {"buyer@example.com"},
        )

    def test_a_buyer_appears_once_however_many_orders(self):
        customer = make_buyer("buyer@example.com")
        Order.objects.create(customer=customer, total_price=10, paid_at=timezone.now())

        self.assertEqual(get_broadcast_recipients().count(), 1)


class BroadcastEmailTests(TestCase):
    def setUp(self):
        Site.objects.update_or_create(pk=1, defaults={"domain": "testserver", "name": "test"})
        self.broadcast = Broadcast.objects.create(subject="News", body="<p>Hello</p>")
        self.customer = make_buyer("buyer@example.com", language="ru")

    def build(self):
        return build_broadcast_email(None, self.broadcast, self.customer)

    def test_the_footer_carries_a_working_unsubscribe_link(self):
        message = self.build()
        token = make_unsubscribe_token(self.customer.email)

        self.assertIn(f"/unsubscribe/{token}", message.body)
        self.assertIn(f"/unsubscribe/{token}", message.alternatives[0].content)

    def test_the_unsubscribe_link_carries_the_customers_language(self):
        self.assertIn("lang=ru", self.build().body)

    def test_the_list_unsubscribe_header_is_set(self):
        message = self.build()

        self.assertIn("/unsubscribe/", message.extra_headers["List-Unsubscribe"])

    def test_the_plain_part_is_stripped_html(self):
        message = self.build()

        self.assertIn("Hello", message.body)
        self.assertNotIn("<p>", message.body)


class UnsubscribeViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = make_buyer("buyer@example.com")

    def url(self, token: str) -> str:
        return reverse("unsubscribe", args=[token])

    def test_a_valid_token_opts_the_customer_out(self):
        response = self.client.post(self.url(make_unsubscribe_token(self.customer.email)))

        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_subscribed)

    def test_opting_out_twice_is_a_no_op(self):
        token = self.url(make_unsubscribe_token(self.customer.email))
        self.client.post(token)
        self.customer.refresh_from_db()
        first_time = self.customer.unsubscribed_at

        response = self.client.post(token)

        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.unsubscribed_at, first_time)

    def test_a_tampered_token_is_refused(self):
        response = self.client.post(self.url("not-a-real-token"))

        self.assertEqual(response.status_code, 400)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_subscribed)

    def test_a_token_for_a_deleted_customer_still_answers_ok(self):
        token = signing.dumps("gone@example.com", salt=UNSUBSCRIBE_SALT)

        with self.assertLogs("mailing.views", level="INFO"):
            response = self.client.post(self.url(token))

        self.assertEqual(response.status_code, 200)

    def test_get_does_not_unsubscribe(self):
        """Link scanners pre-fetch every URL in a message; only the page in a browser may opt out."""
        response = self.client.get(self.url(make_unsubscribe_token(self.customer.email)))

        self.assertEqual(response.status_code, 405)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_subscribed)

    def test_an_unsubscribed_buyer_is_dropped_from_the_next_run(self):
        self.client.post(self.url(make_unsubscribe_token(self.customer.email)))

        self.assertEqual(get_broadcast_recipients().count(), 0)
        self.assertEqual(len(mail.outbox), 0)
