from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from customer.models import Customer


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
