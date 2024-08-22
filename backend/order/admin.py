from django.conf import settings
from django.contrib import admin, messages
from django.db.models import QuerySet
from django.db.transaction import atomic
from django.utils.html import format_html
from django.utils.module_loading import import_string
from djmoney.contrib.exchange.models import Rate, ExchangeBackend

from .models import Order, OrderItem, DownloadLink, Transaction

# Disable django-money's Rate admin model
admin.site.unregister(Rate)


# Setup custom Rate admin model
@admin.register(Rate)
class CustomRateAdmin(admin.ModelAdmin):
    list_display = ("currency", "value", "last_update", "backend")
    search_fields = ("currency",)
    ordering = ("currency",)
    actions = ['update_exchange_rates']

    @admin.display(description='Last update')
    def last_update(self, instance):
        return instance.backend.last_update

    @admin.action(description='Update exchange rates')
    @atomic
    def update_exchange_rates(self, request, queryset: QuerySet[Rate]):
        currencies = queryset.values_list('currency', flat=True)

        backend = import_string(settings.EXCHANGE_BACKEND)()
        backend_model, _ = ExchangeBackend.objects.update_or_create(name=backend.name, defaults={"base_currency": settings.BASE_CURRENCY})

        params = backend.get_params()
        params.update(base_currency=settings.BASE_CURRENCY, symbols=','.join(currencies))
        rates = backend.get_rates(**params)

        try:
            queryset.delete()
            Rate.objects.bulk_create([
                Rate(currency=currency, value=value, backend=backend_model)
                for currency, value in rates.items()
            ])
            self.message_user(request, "Exchange rates updates successfully", messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"Error while updating exchange rates: {e}", messages.ERROR)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_email', 'status', 'total_price', 'created_at', 'updated_at')
    readonly_fields = ('user_email', 'status', 'total_price', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at', 'updated_at')
    search_fields = ('user_email', 'id')
    actions = None  # Disable any actions

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'passport', 'quantity')
    readonly_fields = ('order', 'passport', 'quantity')
    exclude = ('is_reserved',)
    list_filter = ('order',)
    search_fields = ('order__user_email', 'passport__name')
    actions = None  # Disable any actions

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DownloadLink)
class DownloadLinkAdmin(admin.ModelAdmin):
    list_display = ('order_item', 'passport_file', 'link', 'is_valid')
    readonly_fields = ('order_item', 'passport_file', 'link')
    exclude = ('uuid',)
    list_filter = ('order_item__order',)
    search_fields = ('order_item__order__user_email', 'passport_file__name')
    actions = None  # Disable any actions

    @admin.display(boolean=True, description='Valid')
    def is_valid(self, obj: DownloadLink):
        return not obj.is_expired()

    @admin.display(description='Download link')
    def link(self, obj: DownloadLink):
        return format_html("<a href='{url}'>{text}</a>", url=obj.get_link(), text=obj.uuid)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    fields = ('order', 'status', 'txn_id', 'amount', 'currency', 'source_price', 'source_rate', 'commission', 'confirmations', 'created_at',
              'updated_at', 'comment')
    list_display = ('id', 'order', 'amount', 'currency', 'status', 'created_at', 'commission')
    readonly_fields = ('order', 'txn_id', 'amount', 'currency', 'source_price', 'source_rate', 'status', 'confirmations', 'created_at',
                       'updated_at', 'commission', 'comment', 'merchant', 'merchant_id')
    list_filter = ('status', 'created_at')
    search_fields = ('order__user_email', 'txn_id')
    actions = None  # Disable any actions

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
