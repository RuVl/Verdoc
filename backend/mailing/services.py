from django.conf import settings
from django.contrib.sites.models import Site
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import strip_tags

from order.models import Order

from .models import Broadcast, Unsubscribe

UNSUBSCRIBE_SALT = "broadcast-unsubscribe"


def make_unsubscribe_token(email: str) -> str:
    return signing.dumps(email, salt=UNSUBSCRIBE_SALT)


def read_unsubscribe_token(token: str) -> str:
    """Return the email encoded in the token. Raises signing.BadSignature on tamper."""
    return signing.loads(token, salt=UNSUBSCRIBE_SALT)


def make_unsubscribe_url(email: str, request: HttpRequest | None = None) -> str:
    relative_path = reverse("unsubscribe", args=[make_unsubscribe_token(email)])
    scheme = settings.SITE_SCHEME
    domain = Site.objects.get_current(request).domain
    return f"{scheme}://{domain}{relative_path}"


def get_broadcast_recipients() -> list[str]:
    """Unique emails of paid buyers, excluding those who unsubscribed."""
    paid_statuses = [Order.OrderStatus.PAID, Order.OrderStatus.OVERPAID]
    unsubscribed = Unsubscribe.objects.values_list("email", flat=True)
    return list(
        Order.objects.filter(status__in=paid_statuses)
        .exclude(user_email__in=unsubscribed)
        .values_list("user_email", flat=True)
        .distinct()
    )


def build_broadcast_email(
    connection,
    broadcast: Broadcast,
    addr: str,
    request: HttpRequest | None = None,
) -> EmailMultiAlternatives:
    """Build a per-recipient email with an unsubscribe footer and List-Unsubscribe header."""
    unsubscribe_url = make_unsubscribe_url(addr, request)

    # broadcast.body is HTML (WYSIWYG); derive a plain-text alternative from it.
    text_body = f"{strip_tags(broadcast.body)}\n\n--\nОтписаться от рассылки: {unsubscribe_url}"
    html_body = (
        f"{broadcast.body}"
        f'<hr><p style="font-size:12px;color:#888">'
        f'<a href="{unsubscribe_url}">Отписаться от рассылки</a></p>'
    )

    # from_email=None -> settings.DEFAULT_FROM_EMAIL
    message = EmailMultiAlternatives(
        subject=broadcast.subject,
        body=text_body,
        from_email=None,
        to=[addr],
        connection=connection,
        headers={"List-Unsubscribe": f"<{unsubscribe_url}>"},
    )
    message.attach_alternative(html_body, "text/html")

    return message
