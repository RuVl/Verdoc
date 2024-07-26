import hashlib
import hmac
import json
import logging
from decimal import Decimal
from smtplib import SMTPException

import requests
from django import views
from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponseNotFound, FileResponse
from django.shortcuts import get_object_or_404
from djmoney.money import Money
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from passport.models import PassportFile
from .models import Order, Transaction, DownloadLink
from .serializers import OrderSerializer

logger = logging.getLogger(__name__)


class OrderCreateView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = OrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        order = serializer.save()

        # Подготовка данных для инвойса в Plisio
        invoice_data = {
            'order_name': f'Order {order.id}',
            'order_number': order.id,
            'source_currency': order.total_price.currency,
            'source_amount': order.total_price.amount,
            'callback_url': request.build_absolute_uri('/api/orders/status/'),
            'email': order.user_email,
            'api_key': settings.PLISIO_SECRET_KEY,
            'language': 'en_US',
            'expire_min': '60'
        }

        response = requests.get('https://plisio.net/api/v1/invoices/new', params=invoice_data)
        if response.status_code == 200 and response.json().get('status') == 'success':
            logger.info(f'Order {order.id} created successfully')
            redirect_url = response.json()['data']['invoice_url']
            return Response({'redirect_url': redirect_url}, status=status.HTTP_201_CREATED)
        else:
            return Response({'detail': 'Error creating invoice'}, status=status.HTTP_400_BAD_REQUEST)


class PlisioCallbackView(APIView):
    @staticmethod
    def validate_hash(data, received_hash):
        secret_key = settings.PLISIO_SECRET_KEY
        ordered_data = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        calculated_hash = hmac.new(secret_key.encode('utf-8'), ordered_data.encode('utf-8'), hashlib.sha1).hexdigest()
        return calculated_hash == received_hash

    def post(self, request, *args, **kwargs):
        data = request.data
        verify_hash = data.pop('verify_hash', None)

        if not self.validate_hash(data, verify_hash):
            logger.warning(f'Hash verification failed for transaction {data.get("txn_id")}')
            return Response({'detail': 'Invalid verify_hash'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        order_number = data.get('order_number')
        order = get_object_or_404(Order, id=order_number)

        status_map = {
            'new': 'PENDING',
            'pending': 'PENDING',
            'pending internal': 'PENDING',
            'completed': 'PAID',
            'expired': 'EXPIRED',
            'mismatch': 'OVERPAID',
            'error': 'ERROR',
            'cancelled': 'CANCELLED',
        }

        new_status = status_map.get(data.get('status'), 'ERROR')
        order.status = new_status
        order.save()

        source_price = None
        if data.get('source_currency') and data.get('source_amount'):
            source_price = Money(currency=Decimal(data.get('source_currency')), amount=data.get('source_amount'))

        transaction, created = Transaction.objects.update_or_create(
            order=order,
            defaults={
                'txn_id': data.get('txn_id'),
                'status': data.get('status'),
                'amount': Decimal(data.get('amount')),
                'currency': data.get('currency'),
                'source_price': source_price,
                'source_rate': Decimal(data.get('source_rate')) if data.get('source_rate') else None,
                'confirmations': int(data.get('confirmations')) if data.get('confirmations') else None,
                'commission': Decimal(data.get('invoice_commission')) if data.get('invoice_commission') else None,
            }
        )

        logger.info(f'Transaction {transaction.id} {'created' if created else 'updated'} to status {data.get('status')}')

        if transaction.status in [Transaction.TransactionStatus.COMPLETED, Transaction.TransactionStatus.MISMATCH]:
            self.sell_order(order)
            self.send_download_link(order)

        return Response({'detail': 'Order and transaction status updated'}, status=status.HTTP_200_OK)

    def sell_order(self, order: Order):
        download_links = []
        for order_item in order.items:
            # Get reserved passport_files
            passport_files = PassportFile.objects.filter(
                passport=order_item.passport,
                status=PassportFile.PassportFileStatus.RESERVED
            )[:order_item.quantity]

            if len(passport_files) < order_item.quantity:
                logger.warning(f'Not enough ({len(passport_files)} < {order_item.quantity}) passport files for order_item {order_item.id}')

            # Set passport_files status to "sold" and create DownloadLink
            for passport_file in passport_files:
                passport_file.status = PassportFile.PassportFileStatus.SOLD
                download_links.append(DownloadLink.objects.create(
                    order_item=order_item,
                    file_path=passport_file
                ))

    def send_download_link(self, order: Order):
        """ Отправка email ссылок на скачивание """
        download_links = DownloadLink.objects.filter(order=order).prefetch_related('order_item').order_by('order_item')

        message = f"Скачайте ваши файлы по ссылке:\n"

        for i, download_link in enumerate(download_links):
            message += f"{i}) {download_link.get_link()} - {download_link.order_item.passport.name}\n"

        message += "Ссылки будут действительны в течение 24 часов. После этого необходимо запросить доступ повторно через форму на сайте."

        try:
            send_mail(
                'Ваш заказ выполнен',
                message,
                None,
                [order.user_email]
            )
        except SMTPException as e:
            logger.error(f'Error sending mail to {order.user_email}: {str(e)}')


class DownloadLinksView(views.View):
    def get(self, request, *args, **kwargs):
        email = self.kwargs.get('email')
        uuid = self.kwargs.get('uuid')

        if email is None or uuid is None:
            return HttpResponseNotFound()

        try:
            download_link = DownloadLink.objects.get(uuid=uuid, order_item__order__user_email=email)
        except DownloadLink.DoesNotExist:
            return HttpResponseNotFound()

        if download_link.is_expired():
            return HttpResponseNotFound()

        return FileResponse(open(download_link.passport_file.file_path.path, 'rb'), as_attachment=True)
