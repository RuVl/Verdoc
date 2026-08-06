import logging

from django.core.mail import send_mail
from django.http import HttpRequest
from django.utils import translation
from django.utils.translation import gettext as _

from customer.models import Customer

logger = logging.getLogger(__name__)


def send_purchases_link(request: HttpRequest | None, customer: Customer) -> int:
    """
    Mail the customer the single link to their purchases page.

    One link instead of one per file: the page lists every paid order and refreshes its own
    download links, so an e-mail cannot go stale the way a list of file links did.

    The language comes from the Customer, not from the request: this is also called from the
    Plisio webhook, where the only browser involved belongs to Plisio (ADR-0009).
    """

    with translation.override(customer.language):
        message = (
            _("Your purchases are available at:")
            + f"\n{customer.get_purchases_url(request)}\n\n"
            + _(
                "The link is valid for 24 hours and opens ALL of your purchases - do not forward it "
                "to anyone. If it has expired, request a new one through the form on the site.\n"
                "Links to individual files are refreshed on the purchases page itself."
            )
        )
        subject = _("Your order is complete")

    logger.info(f"Sending the purchases link to customer {customer.pk} in {customer.language}")

    return send_mail(subject, message, None, [customer.email])
