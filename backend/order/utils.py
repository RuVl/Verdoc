from django.core.mail import send_mail
from django.http import HttpRequest

from order.models import DownloadLink


def send_download_links(
    request: HttpRequest, download_links: list[DownloadLink], user_email: str
) -> int:
    """Send download links to email"""

    message = "Скачайте ваши файлы по ссылке:\n"

    for i, download_link in enumerate(download_links):
        assert not download_link.is_expired(), "Download link should not be expired"
        message += f"{i + 1}) {download_link.get_link(request)} - {download_link.order_item.passport.name}\n"

    message += "Ссылки будут действительны в течение 24 часов. После этого необходимо запросить доступ повторно через форму на сайте."
    return send_mail("Ваш заказ выполнен", message, None, [user_email])
