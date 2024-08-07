import hashlib
import hmac
import json
import logging
from decimal import Decimal

import requests
from django import views
from django.conf import settings
from django.db import transaction
from django.http import HttpResponseNotFound, FileResponse
from django.shortcuts import get_object_or_404
from djmoney.money import Money
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from passport.models import PassportFile
from .models import Order, Transaction, DownloadLink, OrderItem
from .serializers import OrderSerializer, SendDownloadLinksSerializer
from .utils import send_download_links

logger = logging.getLogger(__name__)


class OrderCreateView(APIView):
    """ Create a new order endpoint """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.reserved_files: list[PassportFile] = []

    def post(self, request, *args, **kwargs):
        serializer = OrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = serializer.save()
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Prepare data for plisio invoice
        invoice_data = {
            'order_name': f'Order {order.id}',
            'order_number': order.id,
            'source_currency': order.total_price.currency,
            'source_amount': order.total_price.amount,
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
            logger.info(f'Invoice has not created for order {order.id}')
            try:
                with transaction.atomic():
                    for order_item in order.items.all():
                        order_item.passport.return2stock(order_item.quantity)
                    order.delete()
            except ValueError as e:
                logger.warning(str(e))  # Silence errors

            return Response({'detail': 'Error creating invoice'}, status=status.HTTP_400_BAD_REQUEST)


class PlisioCallbackView(APIView):
    """ Endpoint for plisio callback """

    @staticmethod
    def validate_hash(data):
        received_hash = data.pop('verify_hash', None)
        secret_key = settings.PLISIO_SECRET_KEY

        ordered_data = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        calculated_hash = hmac.new(secret_key.encode('utf-8'), ordered_data.encode('utf-8'), hashlib.sha1).hexdigest()

        return calculated_hash == received_hash

    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        if not self.validate_hash(data):
            logger.warning(f'Hash verification failed for transaction {data.get("txn_id")}')
            return Response({'detail': 'Invalid verify_hash'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        order = get_object_or_404(Order, id=data.get('order_number'))
        self.update_order_status(order, data)

        match order.status:
            case Order.OrderStatus.PAID | Order.OrderStatus.OVERPAID:
                download_links = order.sell()
                send_download_links(download_links, order.user_email)
            case Order.OrderStatus.EXPIRED | Order.OrderStatus.CANCELLED:
                order.reset_reservation()

        return Response({'detail': 'Order and transaction status updated'}, status=status.HTTP_200_OK)

    def update_order_status(self, order: Order, data: dict) -> Transaction:
        """ Update order and transaction status """

        status_map = {
            'new': Order.OrderStatus.PENDING,
            'pending': Order.OrderStatus.PENDING,
            'pending internal': Order.OrderStatus.PENDING,
            'completed': Order.OrderStatus.PAID,
            'expired': Order.OrderStatus.EXPIRED,
            'mismatch': Order.OrderStatus.OVERPAID,
            'error': Order.OrderStatus.ERROR,
            'cancelled': Order.OrderStatus.CANCELLED,
            'cancelled duplicate': Order.OrderStatus.PENDING  # A customer has switched to another cryptocurrency
        }

        order.status = status_map.get(data.get('status'), Order.OrderStatus.ERROR)

        update_data = {
            'txn_id': data.get('txn_id'),
            'status': data.get('status'),
            'amount': Decimal(data.get('amount')),
            'currency': data.get('currency'),
            'merchant': data.get('merchant'),
            'merchant_id': data.get('merchant_id'),
            'comment': data.get('comment')
        }

        if data.get('source_currency') and data.get('source_amount'):
            update_data['source_price'] = Money(currency=data.get('source_currency'), amount=Decimal(data.get('source_amount')))

        if data.get('source_rate'):
            update_data['source_rate'] = Decimal(data['source_rate'])

        if data.get('confirmations'):
            update_data['confirmations'] = int(data['confirmations'])

        if data.get('invoice_commission'):
            update_data['commission'] = Decimal(data['invoice_commission'])

        with transaction.atomic():
            order.save()
            t, _ = Transaction.objects.update_or_create(order=order, defaults=update_data)

        return t


class DownloadLinksView(views.View):
    """ Download sold files view """

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


class SendDownloadLinksView(APIView):
    """ Update download links expiration and send them to customer's email """

    def post(self, request, *args, **kwargs):
        serializer = SendDownloadLinksSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_email = serializer.validated_data['email']
        orders = Order.objects.filter(
            user_email=user_email,
            status__in=[Order.OrderStatus.PAID, Order.OrderStatus.OVERPAID]
        ).prefetch_related('items').all()

        if not orders:
            return HttpResponseNotFound()

        download_links = []
        for order in orders:
            for order_item in order.items.all():
                download_links.extend(self.get_order_item_links(order_item))

        send_download_links(download_links, user_email)
        return Response({'detail': 'All links are sent'}, status=status.HTTP_200_OK)

    def get_order_item_links(self, order_item: OrderItem) -> list[DownloadLink]:
        item_links = list(DownloadLink.objects.filter(order_item=order_item))

        if len(item_links) < order_item.quantity:
            logger.warning(f'Not enough download links for order item {order_item.id}')

            # Try to create download links for sold product files
            sold_files_without_link = PassportFile.objects.filter(
                passport=order_item.passport,
                status=PassportFile.PassportFileStatus.SOLD,
                downloadlink__isnull=True
            )

            created_download_links = [
                DownloadLink.objects.create(
                    order_item=order_item,
                    passport_file=passport_file
                )
                for passport_file in sold_files_without_link
            ]

            item_links.extend(created_download_links)

            if len(item_links) < order_item.quantity:
                raise ValueError(f'Not enough download links for order item {order_item.id}')

        #
        for item_link in item_links:
            item_link.update_link()

        return item_links
