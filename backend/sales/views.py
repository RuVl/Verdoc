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
from django.db.models import Prefetch
from django.http import FileResponse, HttpResponseNotFound
from djmoney.money import Money
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from customer.models import Customer
from sales.models import Allocation, Order, PaymentCallbackLog, Transaction
from sales.serializers import (
    AllocationSerializer,
    OrderSerializer,
    PurchaseOrderSerializer,
    SendDownloadLinksSerializer,
)
from sales.utils import send_purchases_link

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

# Our language codes -> the locales Plisio names its checkout in. Anything else falls back to en_US.
PLISIO_LANGUAGES = {
    "en": "en_US",
    "ru": "ru_RU",
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
            "language": PLISIO_LANGUAGES.get(order.customer.language, "en_US"),
            "expire_min": "60",
        }

        response, payload = None, {}
        try:
            response = requests.get("https://plisio.net/api/v1/invoices/new", params=invoice_data, timeout=30)
            payload = response.json()
        except ValueError as e:
            # Includes requests' JSONDecodeError - the call went through, the body is not JSON.
            logger.error(f"Plisio answered order {order.id} with something that is not JSON: {e}")
        except requests.RequestException as e:
            logger.error(f"Plisio is unreachable for order {order.id}: {e}")

        if response is not None and response.status_code == 200 and payload.get("status") == "success":
            logger.info(f"Order {order.id} created successfully")
            redirect_url = payload["data"]["invoice_url"]

            # Stored so a repeated checkout of the same cart can be sent back to this invoice.
            order.invoice_url = redirect_url
            order.save(update_fields=["invoice_url"])

            return Response({"redirect_url": redirect_url}, status=status.HTTP_201_CREATED)

        # Plisio puts its own diagnosis in data.{message,code}; pass it on so the storefront can say
        # more than "something went wrong", and log the raw answer for us.
        error = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        http_status = response.status_code if response is not None else None
        logger.error(f"Invoice not created for order {order.id}: HTTP {http_status}, payload {payload}")

        # Deleting the order takes its allocations with it, so the units are free again.
        order.delete()

        return Response(
            {
                "detail": error.get("message") or "Error creating invoice",
                "code": "invoice_failed",
                "provider_code": error.get("code"),
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )


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
            # Deliberately not a rotation: a second purchase must not revoke the link the customer
            # got with the first one and may still have open.
            customer.ensure_access_token()

            try:
                send_purchases_link(request, customer)
            except Exception as e:
                # The sale itself went through and the files are allocated - failing the callback
                # here would only make Plisio retry, and the retry sends nothing because paid_at is
                # already stamped. The customer gets their link from the form on the site.
                logger.error(f"Order {order.id} is delivered but the e-mail did not go out: {e}")

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


def serve_allocation(allocation: Allocation):
    """Stream the file behind an allocation, or 404 - never say which of the checks failed."""

    if not allocation.is_token_valid():
        return HttpResponseNotFound("Expired download link")

    if allocation.stock_item is None:
        logger.error(f"Allocation {allocation.id} has no file to serve")
        return HttpResponseNotFound()

    return FileResponse(open(allocation.stock_item.file.path, "rb"), as_attachment=True)


class DownloadFileView(views.View):
    """Download one delivered file by its token alone."""

    def get(self, request, *args, **kwargs):
        token = self.kwargs.get("uuid")
        if token is None:
            return HttpResponseNotFound()

        try:
            allocation = Allocation.objects.select_related("stock_item").downloadable().get(token=token)
        except (Allocation.DoesNotExist, ValidationError, ValueError):
            return HttpResponseNotFound()

        return serve_allocation(allocation)


class LegacyDownloadLinksView(views.View):
    """
    The pre-R2 download route, `/api/order/file/<email>/<uuid>/`.

    Kept for one release: links from e-mails sent before R2 are still in customers' inboxes and
    have to keep working until their tokens expire.
    """

    def get(self, request, *args, **kwargs):
        email = self.kwargs.get("email")
        token = self.kwargs.get("uuid")

        if email is None or token is None:
            return HttpResponseNotFound()

        try:
            allocation = (
                Allocation.objects.select_related("stock_item")
                .downloadable()
                .get(
                    token=token,
                    order_item__order__customer__email=email,
                )
            )
        except (Allocation.DoesNotExist, ValidationError, ValueError):
            return HttpResponseNotFound()

        return serve_allocation(allocation)


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

        # They are asking from the site right now, so this is the language to answer in.
        customer.set_language(serializer.validated_data.get("language"))

        try:
            with transaction.atomic():
                for order in orders:
                    # Idempotent, and it tops up anything an old sale failed to hand over.
                    order.deliver()

                # This is the "revoke the old link" mechanism: whoever holds the previous purchases
                # URL loses it here. File tokens are left alone - the page refreshes them itself.
                customer.rotate_access_token()
        except ValueError as e:
            logger.warning(f"Cannot re-issue links for {user_email}: {e}")
            return Response({"detail": "Order processing conflict"}, status=status.HTTP_409_CONFLICT)

        try:
            send_purchases_link(request, customer)
        except Exception as e:
            # The token was already rotated, so the previous link is gone either way - the customer
            # has to be told to try again rather than left staring at a success message.
            logger.error(f"Cannot mail the purchases link to {user_email}: {e}")
            return Response({"detail": "Cannot send the e-mail right now"}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({"detail": "The link is sent"}, status=status.HTTP_200_OK)


# One answer for an unknown, malformed or expired token: the page must not confirm that a token
# exists, and the customer's next step is the same either way.
PURCHASES_GONE = "This link is no longer valid - request a new one from the site."


def customer_by_token(token) -> Customer | None:
    """Resolve a purchases-page token, or None if it is unusable for any reason."""

    try:
        customer = Customer.objects.get(access_token=token)
    except (Customer.DoesNotExist, ValidationError, ValueError):
        return None

    return customer if customer.is_access_token_valid() else None


class PurchasesView(APIView):
    """Everything this customer has paid for, with the state of every download link."""

    def get(self, request, *args, **kwargs):
        customer = customer_by_token(kwargs.get("token"))
        if customer is None:
            return Response({"detail": PURCHASES_GONE}, status=status.HTTP_404_NOT_FOUND)

        orders = (
            customer.orders.filter(status__in=Order.PAID_STATUSES)
            .prefetch_related(
                "items",
                Prefetch("items__allocations", queryset=Allocation.objects.downloadable()),
            )
            .order_by("-paid_at", "-created_at")
        )

        serializer = PurchaseOrderSerializer(orders, many=True, context={"request": request})
        return Response({"email": customer.email, "orders": serializer.data})


class RefreshAllocationView(APIView):
    """New token for one file - what the "refresh link" button calls."""

    def post(self, request, *args, **kwargs):
        customer = customer_by_token(kwargs.get("token"))
        if customer is None:
            return Response({"detail": PURCHASES_GONE}, status=status.HTTP_404_NOT_FOUND)

        # Scoped to the customer, so a valid token cannot be used to refresh somebody else's file.
        allocations = Allocation.objects.downloadable().of_customer(customer).filter(pk=kwargs.get("allocation_id"))
        refreshed = allocations.reissue_tokens()
        if not refreshed:
            return Response({"detail": "No such file in your purchases"}, status=status.HTTP_404_NOT_FOUND)

        serializer = AllocationSerializer(refreshed[0], context={"request": request})
        return Response(serializer.data)


class RefreshAllAllocationsView(APIView):
    """New tokens for every file of this customer, in one go."""

    def post(self, request, *args, **kwargs):
        customer = customer_by_token(kwargs.get("token"))
        if customer is None:
            return Response({"detail": PURCHASES_GONE}, status=status.HTTP_404_NOT_FOUND)

        refreshed = Allocation.objects.downloadable().of_customer(customer).reissue_tokens()
        serializer = AllocationSerializer(refreshed, many=True, context={"request": request})
        return Response(serializer.data)
