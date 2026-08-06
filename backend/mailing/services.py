from django.conf import settings
from django.contrib.sites.models import Site
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.http import HttpRequest
from django.utils import translation
from django.utils.html import strip_tags
from django.utils.translation import gettext as _

from customer.models import Customer

from .models import Broadcast

UNSUBSCRIBE_SALT = "broadcast-unsubscribe"

# Frontend route, not a Django one - keep it in step with the Vue router (`/unsubscribe/:token`).
UNSUBSCRIBE_PATH = "/unsubscribe/{token}?lang={language}"


def make_unsubscribe_token(email: str) -> str:
    return signing.dumps(email, salt=UNSUBSCRIBE_SALT)


def read_unsubscribe_token(token: str) -> str:
    """Return the email encoded in the token. Raises signing.BadSignature on tamper."""
    return signing.loads(token, salt=UNSUBSCRIBE_SALT)


def make_unsubscribe_url(customer: Customer, request: HttpRequest | None = None) -> str:
    """
    Absolute link to the unsubscribe page.

    The language rides along in the query string because the page is opened from an inbox, with
    no idea of what the customer picked on the site - the router reads `?lang=` on every route.
    """

    path = UNSUBSCRIBE_PATH.format(token=make_unsubscribe_token(customer.email), language=customer.language)
    domain = Site.objects.get_current(request).domain

    return f"{settings.SITE_SCHEME}://{domain}{path}"


def get_broadcast_recipients():
    """Buyers who have not opted out. One row per person, so there is nothing to de-duplicate."""
    return Customer.objects.subscribed_buyers()


def build_broadcast_email(
    connection,
    broadcast: Broadcast,
    customer: Customer,
    request: HttpRequest | None = None,
) -> EmailMultiAlternatives:
    """
    Build a per-recipient email with an unsubscribe footer and List-Unsubscribe header.

    Everything is read under the customer's language, so `subject` and `body` resolve to their
    translation - one broadcast reaches a bilingual audience in both languages, and a language
    the author left empty falls back to the site default.
    """

    unsubscribe_url = make_unsubscribe_url(customer, request)

    with translation.override(customer.language):
        unsubscribe_label = _("Unsubscribe from this mailing list")
        subject, body = broadcast.subject, broadcast.body

    # The body is HTML (WYSIWYG); derive a plain-text alternative from it.
    text_body = f"{strip_tags(body)}\n\n--\n{unsubscribe_label}: {unsubscribe_url}"
    html_body = (
        f'{body}<hr><p style="font-size:12px;color:#888"><a href="{unsubscribe_url}">{unsubscribe_label}</a></p>'
    )

    # from_email=None -> settings.DEFAULT_FROM_EMAIL
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=None,
        to=[customer.email],
        connection=connection,
        headers={"List-Unsubscribe": f"<{unsubscribe_url}>"},
    )
    message.attach_alternative(html_body, "text/html")

    return message
