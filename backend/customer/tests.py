from datetime import timedelta
from unittest.mock import patch

import dns.exception
import dns.resolver
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from customer.models import Customer
from customer.validators import validate_email_domain


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
