from django.conf import settings
from django.contrib import admin, messages
from django.db.models import QuerySet
from django.db.transaction import atomic
from django.urls import reverse
from django.utils.html import format_html
from django.utils.module_loading import import_string
from djmoney.contrib.exchange.models import ExchangeBackend, Rate

from sales.models import Allocation, Order, OrderItem, PaymentCallbackLog, Transaction

# Disable django-money's Rate admin model
admin.site.unregister(Rate)


# Setup custom Rate admin model
@admin.register(Rate)
class CustomRateAdmin(admin.ModelAdmin):
    list_display = ("currency", "value", "last_update", "backend")
    search_fields = ("currency",)
    ordering = ("currency", "backend__last_update")
    actions = ["update_exchange_rates"]

    @admin.display(description="Last update")
    def last_update(self, instance: Rate):
        return instance.backend.last_update

    @admin.action(description="Update exchange rates")
    @atomic
    def update_exchange_rates(self, request, queryset: QuerySet[Rate]):
        currencies = queryset.values_list("currency", flat=True)

        backend = import_string(settings.EXCHANGE_BACKEND)()
        backend_model, _ = ExchangeBackend.objects.update_or_create(
            name=backend.name,
            defaults={"base_currency": settings.BASE_CURRENCY},
        )

        params = backend.get_params()
        params.update(base_currency=settings.BASE_CURRENCY, symbols=",".join(currencies))
        rates = backend.get_rates(**params)

        try:
            queryset.delete()
            Rate.objects.bulk_create(
                [Rate(currency=currency, value=value, backend=backend_model) for currency, value in rates.items()],
            )
            self.message_user(request, "Exchange rates updates successfully", messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"Error while updating exchange rates: {e}", messages.ERROR)


class ReadOnlyAdmin(admin.ModelAdmin):
    """Sales data is written by the checkout and the payment callback, never by hand."""

    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class DeliveredColumnMixin:
    """How much of an item has actually been handed over - shown both inline and standalone."""

    @admin.display(description="Delivered")
    def delivered(self, obj: OrderItem):
        return f"{obj.allocations.filter(state=Allocation.State.DELIVERED).count()} / {obj.quantity}"


class OrderItemInline(DeliveredColumnMixin, admin.TabularInline):
    model = OrderItem
    fields = ["product", "product_name", "quantity", "unit_price", "unit_price_usd", "delivered"]
    readonly_fields = fields
    extra = 0
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


class TransactionInline(admin.TabularInline):
    """An order can have several invoices - a currency switch mints a new one (ADR-0006)."""

    model = Transaction
    fields = ["txn_id", "status", "amount", "currency", "source_price", "commission", "created_at"]
    readonly_fields = fields
    extra = 0
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(ReadOnlyAdmin):
    list_display = ("id", "customer", "status", "total_price", "created_at", "paid_at")
    list_filter = ("status", "created_at", "paid_at")
    search_fields = ("customer__email", "id")
    list_select_related = ("customer",)
    readonly_fields = ("customer", "status", "total_price", "invoice_url", "created_at", "updated_at", "paid_at")
    inlines = [OrderItemInline, TransactionInline]


@admin.register(OrderItem)
class OrderItemAdmin(DeliveredColumnMixin, ReadOnlyAdmin):
    list_display = ("order", "product_name", "quantity", "delivered", "order_status")
    list_filter = ("order__status", "product__country")
    search_fields = ("order__customer__email", "product_name")
    list_select_related = ("order", "product")
    # The USD snapshot is only interesting next to the order total, so it stays on the Order page
    # (OrderItemInline) and is left out here.
    fields = ("order", "product", "product_name", "unit_price", "quantity")
    readonly_fields = fields

    @admin.display(description="Order status")
    def order_status(self, obj: OrderItem):
        return obj.order.get_status_display()


@admin.register(Allocation)
class AllocationAdmin(ReadOnlyAdmin):
    list_display = ("id", "order_item", "stock_item", "state", "is_downloadable", "download_count", "download_link")
    list_filter = ("state", "reserved_at", "order_item__order__status")
    search_fields = ("order_item__order__customer__email", "order_item__product_name", "token")
    list_select_related = ("order_item", "order_item__order", "order_item__order__customer", "stock_item")
    readonly_fields = (
        "order_item",
        "stock_item",
        "state",
        "reserved_at",
        "delivered_at",
        "released_at",
        "token_expires_at",
        "download_link",
        "download_count",
        "first_downloaded_at",
        "last_downloaded_at",
    )
    exclude = ("token",)

    @admin.display(boolean=True, description="Downloadable")
    def is_downloadable(self, obj: Allocation):
        return obj.is_token_valid()

    @admin.display(description="Download link")
    def download_link(self, obj: Allocation):
        """
        The customer's own link, relative.

        Relative rather than absolute so it needs no request: the previous version stashed one on
        the ModelAdmin, which is a single instance shared by every thread of the process. The admin
        is served from the same origin as the API, so the href resolves either way, and following
        it does not move `download_count` - see DownloadFileView.
        """

        if obj.token is None:
            return "-"

        return format_html("<a href='{url}'>{text}</a>", url=reverse("download-file", args=[obj.token]), text=obj.token)


@admin.register(Transaction)
class TransactionAdmin(ReadOnlyAdmin):
    fields = (
        "order",
        "status",
        "txn_id",
        "amount",
        "currency",
        "pending_amount",
        "tx_urls",
        "source_price",
        "source_rate",
        "commission",
        "confirmations",
        "created_at",
        "updated_at",
        "comment",
        "merchant",
        "merchant_id",
    )
    readonly_fields = fields
    list_display = ("id", "order", "amount", "currency", "status", "pending_amount", "commission", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("order__customer__email", "txn_id")
    list_select_related = ("order", "order__customer")


@admin.register(PaymentCallbackLog)
class PaymentCallbackLogAdmin(ReadOnlyAdmin):
    list_display = ("id", "received_at", "txn_id", "order", "callback_status")
    list_filter = ("received_at",)
    search_fields = ("txn_id", "order__id", "order__customer__email")
    list_select_related = ("order",)
    readonly_fields = ("order", "txn_id", "payload", "received_at")

    @admin.display(description="Status")
    def callback_status(self, obj: PaymentCallbackLog):
        return obj.payload.get("status", "-") if isinstance(obj.payload, dict) else "-"
