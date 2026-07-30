from django.contrib import admin
from django.db.models import Count

from customer.models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["email", "orders_count", "is_subscribed", "has_access", "created_at"]
    list_filter = ["is_subscribed", "created_at"]
    search_fields = ["email"]
    readonly_fields = ["access_token", "access_token_expires_at", "created_at", "unsubscribed_at"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(orders_count=Count("orders"))

    @admin.display(description="Orders", ordering="orders_count")
    def orders_count(self, obj):
        return obj.orders_count

    @admin.display(boolean=True, description="Access token valid")
    def has_access(self, obj: Customer):
        return obj.is_access_token_valid()

    def has_add_permission(self, request):
        return False
