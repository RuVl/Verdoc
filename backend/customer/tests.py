from datetime import timedelta
from unittest.mock import patch

import dns.exception
import dns.resolver
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from customer.models import Customer
from customer.validators import validate_email_domain
from sales.models import Order


class CustomerAccessTokenTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(email="buyer@example.com")

    def test_fresh_customer_has_no_valid_token(self):
        """The token exists from the start, but only issuing it sets a lifetime."""
        self.assertIsNotNone(self.customer.access_token)
        self.assertFalse(self.customer.is_access_token_valid())

    def test_rotate_replaces_the_token_and_sets_ttl(self):
        old_token = self.customer.access_token

        self.customer.rotate_access_token()

        self.assertNotEqual(self.customer.access_token, old_token)
        self.assertTrue(self.customer.is_access_token_valid())

    def test_expired_token_is_invalid(self):
        self.customer.rotate_access_token()
        self.customer.access_token_expires_at = timezone.now() - timedelta(seconds=1)

        self.assertFalse(self.customer.is_access_token_valid())


class CustomerSubscriptionTests(TestCase):
    def test_unsubscribe_keeps_the_first_timestamp(self):
        customer = Customer.objects.create(email="buyer@example.com")

        customer.unsubscribe()
        first_time = customer.unsubscribed_at
        customer.unsubscribe()

        self.assertFalse(customer.is_subscribed)
        self.assertEqual(customer.unsubscribed_at, first_time)


class CustomerLanguageTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(email="buyer@example.com")

    def test_defaults_to_the_site_language(self):
        self.assertEqual(self.customer.language, settings.LANGUAGE_CODE)

    def test_set_language_stores_and_persists(self):
        self.customer.set_language("ru")

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.language, "ru")

    def test_set_language_ignores_an_empty_value(self):
        """A client that sends nothing must not reset a language we already know."""
        self.customer.set_language("ru")

        self.customer.set_language(None)

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.language, "ru")


class CustomerQuerySetTests(TestCase):
    """One definition of "a buyer" - the admin filter and the broadcast list share it."""

    def setUp(self):
        self.buyer = Customer.objects.create(email="buyer@example.com")
        self.lead = Customer.objects.create(email="lead@example.com")
        self.unsubscribed = Customer.objects.create(email="quiet@example.com", is_subscribed=False)

        Order.objects.create(customer=self.buyer, total_price=10, paid_at=timezone.now())
        Order.objects.create(customer=self.lead, total_price=10)
        Order.objects.create(customer=self.unsubscribed, total_price=10, paid_at=timezone.now())

    def test_buyers_are_the_ones_with_a_paid_at_stamp(self):
        self.assertEqual(
            set(Customer.objects.buyers().values_list("email", flat=True)),
            {"buyer@example.com", "quiet@example.com"},
        )

    def test_leads_are_everyone_else(self):
        self.assertEqual(set(Customer.objects.leads().values_list("email", flat=True)), {"lead@example.com"})

    def test_subscribed_buyers_drop_the_opted_out(self):
        self.assertEqual(
            set(Customer.objects.subscribed_buyers().values_list("email", flat=True)), {"buyer@example.com"}
        )

    def test_a_buyer_is_counted_once_however_many_orders(self):
        Order.objects.create(customer=self.buyer, total_price=10, paid_at=timezone.now())

        self.assertEqual(Customer.objects.buyers().filter(email="buyer@example.com").count(), 1)


class CustomerAdminFilterTests(TestCase):
    """The list must open on buyers, because an abandoned checkout also leaves a Customer row."""

    def setUp(self):
        self.buyer = Customer.objects.create(email="buyer@example.com")
        self.lead = Customer.objects.create(email="lead@example.com")
        Order.objects.create(customer=self.buyer, total_price=10, paid_at=timezone.now())
        Order.objects.create(customer=self.lead, total_price=10)

        admin_user = User.objects.create_superuser("admin", "admin@example.com", "pw")
        self.client.force_login(admin_user)
        self.url = reverse("admin:customer_customer_changelist")

    def emails(self, query: str = ""):
        response = self.client.get(self.url + query)
        self.assertEqual(response.status_code, 200)
        return {customer.email for customer in response.context["cl"].result_list}

    def test_buyers_are_shown_by_default(self):
        self.assertEqual(self.emails(), {"buyer@example.com"})

    def test_leads_can_be_listed(self):
        self.assertEqual(self.emails("?purchases=no"), {"lead@example.com"})

    def test_everyone_can_be_listed(self):
        self.assertEqual(self.emails("?purchases=all"), {"buyer@example.com", "lead@example.com"})

    def test_the_order_counts_are_not_skewed_by_the_filter(self):
        Order.objects.create(customer=self.buyer, total_price=10)  # unpaid, on top of the paid one

        response = self.client.get(self.url)
        row = next(c for c in response.context["cl"].result_list if c.email == "buyer@example.com")

        self.assertEqual(row.orders_count, 2)
        self.assertEqual(row.paid_orders_count, 1)


@override_settings(VALIDATE_EMAIL_MX=True)
class EmailDomainValidatorTests(TestCase):
    """A made-up domain is rejected, but DNS trouble never blocks a sale."""

    def setUp(self):
        cache.clear()  # the validator caches per domain

    def resolve(self, side_effect):
        return patch.object(dns.resolver.Resolver, "resolve", side_effect=side_effect)

    def test_domain_with_mx_passes(self):
        with self.resolve(lambda *a, **kw: ["mx.example.net"]):
            validate_email_domain("buyer@example.net")

    def test_unknown_domain_is_rejected(self):
        with self.resolve(dns.resolver.NXDOMAIN), self.assertRaises(ValidationError) as caught:
            validate_email_domain("buyer@nope.invalid")

        self.assertEqual(caught.exception.code, "undeliverable_domain")

    def test_no_mx_but_an_a_record_passes(self):
        # RFC 5321 delivers to the A record when there is no MX.
        calls = []

        def resolve(name, rdtype="A", *args, **kwargs):
            calls.append(rdtype)
            if rdtype == "MX":
                raise dns.resolver.NoAnswer
            return ["203.0.113.1"]

        with self.resolve(resolve):
            validate_email_domain("buyer@a-only.example")

        self.assertEqual(calls, ["MX", "A"])

    def test_domain_without_mx_and_without_a_is_rejected(self):
        with self.resolve(dns.resolver.NoAnswer), self.assertRaises(ValidationError):
            validate_email_domain("buyer@empty.example")

    def test_dns_failure_lets_the_address_through(self):
        with self.resolve(dns.exception.Timeout):
            validate_email_domain("buyer@example.net")

    def test_the_answer_is_cached_per_domain(self):
        with self.resolve(lambda *a, **kw: ["mx.example.net"]) as mocked:
            validate_email_domain("buyer@example.net")
            validate_email_domain("someone-else@example.net")

        mocked.assert_called_once()

    def test_the_check_can_be_turned_off(self):
        with override_settings(VALIDATE_EMAIL_MX=False), self.resolve(dns.resolver.NXDOMAIN) as mocked:
            validate_email_domain("buyer@nope.invalid")

        mocked.assert_not_called()
