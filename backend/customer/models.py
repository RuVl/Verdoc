import uuid
from typing import TYPE_CHECKING

from django.apps import apps
from django.conf import settings
from django.contrib.sites.models import Site
from django.db import models
from django.db.models import Exists, OuterRef
from django.http import HttpRequest
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from sales.models import OrderQuerySet

# Frontend route, not a Django one - keep it in step with the Vue router (`/purchases/:token`).
PURCHASES_PATH = "/purchases/{token}"


class CustomerQuerySet(models.QuerySet):
    """
    The one definition of "a buyer", shared by the admin and the broadcast recipient list.

    Paid means `paid_at` is stamped, not `status in PAID_STATUSES`: the stamp is written exactly
    once by `Order.mark_paid()`, while the status can still move afterwards.
    """

    def _paid_orders(self):
        # apps.get_model() instead of an import - sales already imports customer.
        order_model = apps.get_model("sales", "Order")
        return order_model.objects.filter(customer=OuterRef("pk"), paid_at__isnull=False)

    def buyers(self):
        # Exists() instead of a join, so it cannot interfere with counts annotated by the caller.
        return self.filter(Exists(self._paid_orders()))

    def leads(self):
        """Checkouts that never got paid. Kept as funnel data - see ADR-0008."""
        return self.filter(~Exists(self._paid_orders()))

    def subscribed_buyers(self):
        return self.buyers().filter(is_subscribed=True)


class Customer(models.Model):
    """
    Somebody who reached the checkout, identified by email.

    Replaces the bare `Order.user_email` string, so purchases, access and mailing preferences
    have one owner (ADR-0004). The row is written at checkout, before the payment, so a customer
    without a paid order is a lead and not a buyer - see the admin filter and ADR-0008.

    :param email: Customer's email, the natural key.
    :param access_token: Opens the purchases page with every paid order of this customer.
    :param access_token_expires_at: When the token stops working, PURCHASES_PAGE_TTL after issue.
    :param language: The site language this customer last used; every e-mail to them is in it.
    :param is_subscribed: False after unsubscribing from broadcasts (replaces the Unsubscribe table).
    :param unsubscribed_at: When the customer unsubscribed.
    :param created_at: First seen, i.e. the first order.
    """

    email = models.EmailField(unique=True)

    access_token = models.UUIDField(default=uuid.uuid4, unique=True)
    access_token_expires_at = models.DateTimeField(null=True, blank=True)

    # Stored rather than read off the request: the delivery e-mail is sent from the Plisio
    # webhook, where the customer's browser is nowhere in sight (ADR-0009).
    language = models.CharField(max_length=5, choices=settings.LANGUAGES, default=settings.LANGUAGE_CODE)

    is_subscribed = models.BooleanField(default=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = CustomerQuerySet.as_manager()

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

    def set_language(self, language: str | None):
        """Remember the site language the customer is using, so the next e-mail speaks it."""
        if not language or language == self.language:
            return

        self.language = language
        self.save(update_fields=["language"])

    def unsubscribe(self):
        """Opt out of broadcasts. Idempotent - keeps the first opt-out timestamp."""
        if not self.is_subscribed:
            return

        self.is_subscribed = False
        self.unsubscribed_at = timezone.now()
        self.save(update_fields=["is_subscribed", "unsubscribed_at"])
