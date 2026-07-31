import hashlib
import hmac
import json
import logging
from decimal import Decimal

import requests
from django import views
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse, HttpResponseNotFound
from djmoney.money import Money
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from customer.models import Customer
from sales.models import Allocation, Order, PaymentCallbackLog, Transaction
from sales.serializers import OrderSerializer, SendDownloadLinksSerializer
from sales.utils import send_download_links

logger = logging.getLogger(__name__)

# Plisio invoice status -> our order status.
STATUS_MAP = {
    "new": Order.OrderStatus.PENDING,
    "pending": Order.OrderStatus.PENDING,
    "pending internal": Order.OrderStatus.PENDING,
    "completed": Order.OrderStatus.PAID,
    "expired": Order.OrderStatus.EXPIRED,
    "mismatch": Order.OrderStatus.OVERPAID,
    "error": Order.OrderStatus.ERROR,
    "cancelled": Order.OrderStatus.CANCELLED,
    "cancelled duplicate": Order.OrderStatus.PENDING,  # A customer has switched to another cryptocurrency
}


class OrderCreateView(APIView):
    """Create a new order endpoint"""

    def post(self, request, *args, **kwargs):
        serializer = OrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = serializer.save()
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if serializer.reused_order is not None:
            # Same customer, same cart, invoice still alive: send them back to it instead of
            # reserving a second copy of the same units.
            logger.info(f"Order {order.id} reused for a repeated checkout")
            return Response({"redirect_url": order.invoice_url}, status=status.HTTP_201_CREATED)

        if Site.objects.get_current(request).domain == settings.ALLOWED_HOSTS[0]:
            secret_key = settings.PLISIO_SECRET_KEY
        else:
            secret_key = settings.MIRROR_PLISIO_SECRET_KEY

        # Prepare data for plisio invoice
        invoice_data = {
            "order_name": f"Order {order.id}",
            "order_number": order.id,
            "source_currency": order.total_price.currency,
            "source_amount": order.total_price.amount,
            "email": order.customer.email,
            "api_key": secret_key,
            "language": "en_US",
            "expire_min": "60",
        }

        response = requests.get("https://plisio.net/api/v1/invoices/new", params=invoice_data)
        if response.status_code == 200 and response.json().get("status") == "success":
            logger.info(f"Order {order.id} created successfully")
            redirect_url = response.json()["data"]["invoice_url"]

            # Stored so a repeated checkout of the same cart can be sent back to this invoice.
            order.invoice_url = redirect_url
            order.save(update_fields=["invoice_url"])

            return Response({"redirect_url": redirect_url}, status=status.HTTP_201_CREATED)

        logger.info(f"Invoice has not created for order {order.id}")
        # Deleting the order takes its allocations with it, so the units are free again.
        order.delete()

        return Response({"detail": "Error creating invoice"}, status=status.HTTP_400_BAD_REQUEST)


class PlisioCallbackView(APIView):
    """Endpoint for plisio callback"""

    @staticmethod
    def validate_hash(data):
        received_hash = data.pop("verify_hash", None)

        for secret_key in (
            settings.PLISIO_SECRET_KEY,
            settings.MIRROR_PLISIO_SECRET_KEY,
        ):
            ordered_data = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            calculated_hash = hmac.new(
                secret_key.encode("utf-8"), ordered_data.encode("utf-8"), hashlib.sha1
            ).hexdigest()

            if calculated_hash == received_hash:
                return True

        return False

    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        if not self.validate_hash(data):
            logger.warning(f"Hash verification failed for transaction {data.get('txn_id')}")
            return Response(
                {"detail": "Invalid verify_hash"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        order = Order.objects.filter(id=data.get("order_number")).first()

        # Logged before the atomic block on purpose: a rolled-back callback still leaves a trace.
        # validate_hash() has already popped verify_hash, so no secret-derived value is stored.
        PaymentCallbackLog.objects.create(order=order, txn_id=data.get("txn_id"), payload=dict(data))

        if order is None:
            logger.warning(f"Callback for unknown order {data.get('order_number')}")
            return Response({"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

        allocations = []
        first_payment = False

        try:
            with transaction.atomic():
                self.upsert_transaction(order, data)

                match order.status:
                    case Order.OrderStatus.PAID | Order.OrderStatus.OVERPAID:
                        first_payment = order.mark_paid()
                        allocations = order.deliver()
                    case Order.OrderStatus.EXPIRED | Order.OrderStatus.CANCELLED:
                        order.release()
        except ValueError as e:
            # Only one thing raises here now: the order is paid but stock ran out while the payment
            # was pending. Everything rolls back, so Plisio can retry once stock is refilled.
            logger.warning(f"Callback for order {order.id} could not be applied: {e}")
            return Response({"detail": "Order processing conflict"}, status=status.HTTP_409_CONFLICT)

        # A duplicate callback delivers nothing new and must not send a second email.
        if first_payment and allocations:
            customer = order.customer
            customer.rotate_access_token()
            send_download_links(request, allocations, customer.email)

        return Response(
            {"detail": "Order and transaction status updated"},
            status=status.HTTP_200_OK,
        )

    def upsert_transaction(self, order: Order, data: dict) -> Transaction:
        """Store the invoice this callback is about and move the order to the matching status."""

        order.status = STATUS_MAP.get(data.get("status"), Order.OrderStatus.ERROR)

        update_data = {
            "order": order,
            "status": data.get("status"),
            "amount": Decimal(data.get("amount")),
            "currency": data.get("currency"),
            "merchant": data.get("merchant"),
            "merchant_id": data.get("merchant_id"),
            "comment": data.get("comment"),
        }

        if data.get("source_currency") and data.get("source_amount"):
            update_data["source_price"] = Money(
                currency=data.get("source_currency"),
                amount=Decimal(data.get("source_amount")),
            )

        if data.get("source_rate"):
            update_data["source_rate"] = Decimal(data["source_rate"])

        if data.get("confirmations"):
            update_data["confirmations"] = int(data["confirmations"])

        if data.get("invoice_commission"):
            update_data["commission"] = Decimal(data["invoice_commission"])

        if data.get("pending_amount"):
            update_data["pending_amount"] = Decimal(data["pending_amount"])

        if data.get("tx_urls"):
            update_data["tx_urls"] = data["tx_urls"]

        order.save(update_fields=["status", "updated_at"])
        # Keyed by txn_id, not by order: switching cryptocurrency mints a new invoice for the same
        # order, and the old schema overwrote the previous one. A payload without an invoice id is
        # not expected - it gets a stable synthetic one instead of a second nameless row.
        txn_id = data.get("txn_id") or f"unknown-{order.id}"
        txn, _ = Transaction.objects.update_or_create(txn_id=txn_id, defaults=update_data)

        return txn


class DownloadLinksView(views.View):
    """Download delivered files view"""

    def get(self, request, *args, **kwargs):
        email = self.kwargs.get("email")
        token = self.kwargs.get("uuid")

        if email is None or token is None:
            return HttpResponseNotFound()

        try:
            allocation = Allocation.objects.select_related("stock_item").get(
                token=token,
                state=Allocation.State.DELIVERED,
                order_item__order__customer__email=email,
            )
        except (Allocation.DoesNotExist, ValidationError, ValueError):
            return HttpResponseNotFound()

        if not allocation.is_token_valid():
            return HttpResponseNotFound("Expired download link")

        if allocation.stock_item is None:
            logger.error(f"Allocation {allocation.id} has no file to serve")
            return HttpResponseNotFound()

        return FileResponse(open(allocation.stock_item.file.path, "rb"), as_attachment=True)


class SendDownloadLinksView(APIView):
    """Refresh download links and send them to customer's email"""

    def post(self, request, *args, **kwargs):
        serializer = SendDownloadLinksSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_email = serializer.validated_data["email"]
        customer = Customer.objects.filter(email=user_email).first()
        orders = list(customer.orders.filter(status__in=Order.PAID_STATUSES)) if customer else []

        if not orders:
            return HttpResponseNotFound()

        allocations = []
        try:
            with transaction.atomic():
                for order in orders:
                    # Idempotent, and it tops up anything an old sale failed to hand over.
                    order.deliver()
                    allocations.extend(order.refresh_download_tokens())

                customer.rotate_access_token()
        except ValueError as e:
            logger.warning(f"Cannot re-issue links for {user_email}: {e}")
            return Response({"detail": "Order processing conflict"}, status=status.HTTP_409_CONFLICT)

        send_download_links(request, allocations, user_email)
        return Response({"detail": "All links are sent"}, status=status.HTTP_200_OK)
