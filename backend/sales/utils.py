import logging

from django.core.mail import send_mail
from django.http import HttpRequest

from customer.models import Customer

logger = logging.getLogger(__name__)


def send_purchases_link(request: HttpRequest | None, customer: Customer) -> int:
    """
    Mail the customer the single link to their purchases page.

    One link instead of one per file: the page lists every paid order and refreshes its own
    download links, so an e-mail cannot go stale the way a list of file links did.
    """

    message = (
        "Ваши покупки доступны по ссылке:\n"
        f"{customer.get_purchases_url(request)}\n\n"
        "Ссылка действует 24 часа и открывает ВСЕ ваши покупки - не пересылайте её никому. "
        "Если срок истёк, запросите новую через форму на сайте.\n"
        "Ссылки на отдельные файлы обновляются прямо на странице покупок."
    )
    logger.info(f"Sending the purchases link to customer {customer.pk}")

    return send_mail("Ваш заказ выполнен", message, None, [customer.email])
