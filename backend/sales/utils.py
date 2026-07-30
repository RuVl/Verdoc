from django.core.mail import send_mail
from django.http import HttpRequest

from sales.models import Allocation


def send_download_links(request: HttpRequest, allocations: list[Allocation], user_email: str) -> int:
    """Send download links to email"""

    message = "Скачайте ваши файлы по ссылке:\n"

    for i, allocation in enumerate(allocations):
        assert allocation.is_token_valid(), "Download link should not be expired"
        message += f"{i + 1}) {allocation.get_download_url(request)} - {allocation.order_item.product_name}\n"

    message += (
        "Ссылки будут действительны в течение 24 часов. "
        "После этого необходимо запросить доступ повторно через форму на сайте."
    )
    return send_mail("Ваш заказ выполнен", message, None, [user_email])
