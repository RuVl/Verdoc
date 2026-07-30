from django.contrib import admin
from django.db.models import Count, Q
from modeltranslation.admin import TranslationAdmin

from catalog.forms import CountryForm
from catalog.models import Country, Product, StockItem
from sales.models import Allocation


class ProductInline(admin.TabularInline):
    model = Product
    fields = ["name", "price"]
    extra = 0


@admin.register(Country)
class CountryAdmin(TranslationAdmin):
    form = CountryForm
    list_display = ["flag", "name", "code"]
    search_fields = ["name", "code"]
    inlines = [ProductInline]


class StockItemInline(admin.TabularInline):
    model = StockItem
    fields = ["file", "state"]
    readonly_fields = ["state"]
    extra = 0

    @admin.display(description="State")
    def state(self, obj: StockItem):
        return stock_item_state(obj)

    def has_delete_permission(self, request, obj=None):
        if isinstance(obj, StockItem) and not obj.is_available():
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Product)
class ProductAdmin(TranslationAdmin):
    list_display = ["name", "price", "available", "reserved", "delivered", "country"]
    list_filter = ["country"]
    search_fields = ["name"]
    inlines = [StockItemInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .with_available()
            .annotate(
                reserved=Count(
                    "stock_items__allocations",
                    filter=Q(stock_items__allocations__state=Allocation.State.RESERVED),
                    distinct=True,
                ),
                delivered=Count(
                    "stock_items__allocations",
                    filter=Q(stock_items__allocations__state=Allocation.State.DELIVERED),
                    distinct=True,
                ),
            )
        )

    @admin.display(description="In stock", ordering="available")
    def available(self, obj):
        return obj.available

    @admin.display(description="Reserved", ordering="reserved")
    def reserved(self, obj):
        return obj.reserved

    @admin.display(description="Delivered", ordering="delivered")
    def delivered(self, obj):
        return obj.delivered


def stock_item_state(obj: StockItem) -> str:
    """Human-readable state of a unit: it belongs to the allocation holding it, if any."""

    allocation = obj.allocations.exclude(state=Allocation.State.RELEASED).first()
    return allocation.get_state_display() if allocation else "Available"


class AvailabilityFilter(admin.SimpleListFilter):
    title = "Availability"
    parameter_name = "availability"

    def lookups(self, request, model_admin):
        return [
            ("available", "Available"),
            ("reserved", "Reserved"),
            ("delivered", "Delivered"),
        ]

    def queryset(self, request, queryset):
        match self.value():
            case "available":
                return queryset.available()
            case "reserved":
                return queryset.filter(allocations__state=Allocation.State.RESERVED)
            case "delivered":
                return queryset.filter(allocations__state=Allocation.State.DELIVERED)

        return queryset


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ["id", "product", "file", "state"]
    list_filter = [AvailabilityFilter, "product__country"]
    search_fields = ["product__name", "file"]
    list_select_related = ["product"]

    @admin.display(description="State")
    def state(self, obj: StockItem):
        return stock_item_state(obj)

    def has_delete_permission(self, request, obj=None):
        # A unit somebody holds is part of an order - deleting it would break that order's history.
        if obj and not obj.is_available():
            return False
        return super().has_delete_permission(request, obj)
