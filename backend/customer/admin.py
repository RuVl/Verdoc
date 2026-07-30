from django.contrib import admin
from django.db.models import Count, Exists, OuterRef, Q

from customer.models import Customer
from sales.models import Order


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

        # Exists() instead of a join, so it cannot interfere with the counts annotated below.
        paid = Order.objects.filter(customer=OuterRef("pk"), paid_at__isnull=False)

        return queryset.filter(Exists(paid)) if value == "yes" else queryset.filter(~Exists(paid))


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["email", "orders_count", "paid_orders_count", "is_subscribed", "has_access", "created_at"]
    list_filter = [HasPurchasesFilter, "is_subscribed", "created_at"]
    search_fields = ["email"]
    readonly_fields = ["access_token", "access_token_expires_at", "created_at", "unsubscribed_at"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                orders_count=Count("orders", distinct=True),
                paid_orders_count=Count("orders", filter=Q(orders__paid_at__isnull=False), distinct=True),
            )
        )

    @admin.display(description="Orders", ordering="orders_count")
    def orders_count(self, obj):
        return obj.orders_count

    @admin.display(description="Paid", ordering="paid_orders_count")
    def paid_orders_count(self, obj):
        return obj.paid_orders_count

    @admin.display(boolean=True, description="Access token valid")
    def has_access(self, obj: Customer):
        return obj.is_access_token_valid()

    def has_add_permission(self, request):
        return False
