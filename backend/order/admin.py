from django.contrib import admin
from django.utils.html import format_html

from .models import DownloadLink, Order, OrderItem, Transaction

# The Rate admin moved to sales/admin.py - this app is on its way out.


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    fields = ["passport"]
    readonly_fields = fields
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_email",
        "status",
        "total_price",
        "created_at",
        "updated_at",
    )
    readonly_fields = (
        "user_email",
        "status",
        "total_price",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "created_at", "updated_at")
    search_fields = ("user_email", "id")
    actions = None  # Disable any actions
    inlines = [OrderItemInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "passport", "quantity", "is_reserved", "order__status")
    readonly_fields = ("order", "passport", "quantity", "is_reserved", "order_status")
    list_filter = ("is_reserved", "order__status", "order")
    search_fields = ("order__user_email", "passport__name")
    actions = None  # Disable any actions

    @admin.display(description="Order status")
    def order_status(self, obj):
        return obj.order.get_status_display()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DownloadLink)
class DownloadLinkAdmin(admin.ModelAdmin):
    list_display = ("order_item", "passport_file", "link", "is_valid")
    readonly_fields = ("order_item", "passport_file", "link")
    exclude = ("uuid",)
    list_filter = ("order_item__order",)
    search_fields = ("order_item__order__user_email", "passport_file__passport__name")
    actions = None  # Disable any actions

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = None

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        self.request = request
        return qs

    @admin.display(boolean=True, description="Valid")
    def is_valid(self, obj: DownloadLink):
        return not obj.is_expired()

    @admin.display(description="Download link")
    def link(self, obj: DownloadLink):
        return format_html("<a href='{url}'>{text}</a>", url=obj.get_link(self.request), text=obj.uuid)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    fields = (
        "order",
        "status",
        "txn_id",
        "amount",
        "currency",
        "source_price",
        "source_rate",
        "commission",
        "confirmations",
        "created_at",
        "updated_at",
        "comment",
    )
    list_display = (
        "id",
        "order",
        "amount",
        "currency",
        "status",
        "created_at",
        "commission",
    )
    readonly_fields = (
        "order",
        "txn_id",
        "amount",
        "currency",
        "source_price",
        "source_rate",
        "status",
        "confirmations",
        "created_at",
        "updated_at",
        "commission",
        "comment",
        "merchant",
        "merchant_id",
    )
    list_filter = ("status", "created_at")
    search_fields = ("order__user_email", "txn_id")
    actions = None  # Disable any actions

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
