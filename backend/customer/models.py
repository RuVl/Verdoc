import uuid
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.sites.models import Site
from django.db import models
from django.http import HttpRequest
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from sales.models import OrderQuerySet

# Frontend route, not a Django one - keep it in step with the Vue router (`/purchases/:token`).
PURCHASES_PATH = "/purchases/{token}"


class Customer(models.Model):
    """
    Somebody who reached the checkout, identified by email.

    Replaces the bare `Order.user_email` string, so purchases, access and mailing preferences
    have one owner (ADR-0004). The row is written at checkout, before the payment, so a customer
    without a paid order is a lead and not a buyer - see the admin filter and ADR-0008.

    :param email: Customer's email, the natural key.
    :param access_token: Opens the purchases page with every paid order of this customer.
    :param access_token_expires_at: When the token stops working, PURCHASES_PAGE_TTL after issue.
    :param is_subscribed: False after unsubscribing from broadcasts (replaces the Unsubscribe table).
    :param unsubscribed_at: When the customer unsubscribed.
    :param created_at: First seen, i.e. the first order.
    """

    email = models.EmailField(unique=True)

    access_token = models.UUIDField(default=uuid.uuid4, unique=True)
    access_token_expires_at = models.DateTimeField(null=True, blank=True)

    is_subscribed = models.BooleanField(default=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    if TYPE_CHECKING:
        orders: "OrderQuerySet"

    class Meta:
        verbose_name = _("Customer")
        verbose_name_plural = _("Customers")
        ordering = ["email"]

    def __str__(self):
        return self.email

    def rotate_access_token(self):
        """Issue a new purchases-page token and reset its TTL, revoking the previous one."""
        self.access_token = uuid.uuid4()
        self.access_token_expires_at = timezone.now() + settings.PURCHASES_PAGE_TTL
        self.save(update_fields=["access_token", "access_token_expires_at"])

    def ensure_access_token(self):
        """
        Make sure the purchases page can be opened, without revoking a link already sent.

        The delivery e-mail uses this instead of `rotate_access_token()`: a second purchase must
        not kill the link from the first one, which the customer may still be using.
        """

        if not self.is_access_token_valid():
            self.rotate_access_token()

    def is_access_token_valid(self) -> bool:
        return self.access_token_expires_at is not None and timezone.now() <= self.access_token_expires_at

    def get_purchases_url(self, request: HttpRequest | None) -> str:
        """Absolute link to the purchases page - the single link the delivery e-mail carries."""

        domain = Site.objects.get_current(request).domain
        return f"{settings.SITE_SCHEME}://{domain}{PURCHASES_PATH.format(token=self.access_token)}"

    def unsubscribe(self):
        """Opt out of broadcasts. Idempotent - keeps the first opt-out timestamp."""
        if not self.is_subscribed:
            return

        self.is_subscribed = False
        self.unsubscribed_at = timezone.now()
        self.save(update_fields=["is_subscribed", "unsubscribed_at"])
