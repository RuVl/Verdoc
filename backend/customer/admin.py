from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html

from customer.models import Customer


class HasPurchasesFilter(admin.SimpleListFilter):
    """
    Splits buyers from leads, and shows buyers by default.

    A Customer row appears at checkout, before the payment, so an abandoned or probed checkout
    leaves one behind. Those rows are kept - they are the only record of the conversion funnel -
    but they should not be what you see when you open the list.
    """

    title = "purchases"
    parameter_name = "purchases"
    default = "yes"

    def lookups(self, request, model_admin):
        return [("yes", "Bought something"), ("no", "Never paid"), ("all", "Everyone")]

    def choices(self, changelist):
        # No "All" entry of its own: an empty parameter means "yes" here, so it would lie.
        for lookup, title in self.lookup_choices:
            yield {
                "selected": (self.value() or self.default) == lookup,
                "query_string": changelist.get_query_string({self.parameter_name: lookup}),
                "display": title,
            }

    def queryset(self, request, queryset):
        value = self.value() or self.default
        if value == "all":
            return queryset

        return queryset.buyers() if value == "yes" else queryset.leads()


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["email", "orders_count", "has_access", "is_subscribed", "created_at"]
    list_filter = [HasPurchasesFilter, "language", "is_subscribed", "created_at"]
    search_fields = ["email"]
    fields = [
        "email",
        "access_token_url",
        "access_token_expires_at",
        "is_subscribed",
        "unsubscribed_at",
        "language",
        "created_at",
    ]
    readonly_fields = fields

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        self._request = None

    def get_queryset(self, request):
        self._request = request
        return (
            super()
            .get_queryset(request)
            .annotate(
                orders_count=Count("orders", distinct=True),
                paid_orders_count=Count("orders", filter=Q(orders__paid_at__isnull=False), distinct=True),
            )
        )

    @admin.display(description="Completed orders", ordering="orders_count")
    def orders_count(self, obj):
        return f"{obj.paid_orders_count}/{obj.orders_count}"

    @admin.display(boolean=True, description="URL unexpired")
    def has_access(self, obj: Customer):
        return obj.is_access_token_valid()

    @admin.display(description="Access url")
    def access_token_url(self, obj: Customer):
        return format_html(
            '<a href="{url}">{text}</a>', url=obj.get_purchases_url(self._request), text=obj.access_token
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
