from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Count, Prefetch, Q
from django.forms import BaseInlineFormSet
from modeltranslation.admin import TranslationAdmin

from catalog.forms import CountryForm
from catalog.models import Country, Product, StockItem
from sales.models import Allocation


def active_allocations() -> Prefetch:
    """Prefetch of the allocations that actually hold a unit, so a list does not query per row."""

    return Prefetch(
        "allocations",
        queryset=Allocation.objects.exclude(state=Allocation.State.RELEASED),
        to_attr="held_by",
    )


class ProductInline(admin.TabularInline):
    model = Product
    fields = ["name", "price"]
    extra = 0
    show_change_link = True


@admin.register(Country)
class CountryAdmin(TranslationAdmin):
    form = CountryForm
    list_display = ["flag", "name", "code"]
    search_fields = ["name", "code"]
    inlines = [ProductInline]


class StockItemInlineFormSet(BaseInlineFormSet):
    """
    Refuses to delete a unit an order holds.

    `has_delete_permission` cannot do this: an inline is asked about the parent object (the
    Product), never about the row, so it can only turn the checkbox off for the whole table.
    The model refuses the delete anyway (`protect_held_units`), but as a ProtectedError - this
    turns it into a form error the admin can show.
    """

    def clean(self):
        super().clean()

        for form in self.deleted_forms:
            unit = form.instance
            if unit.pk and not unit.is_available():
                raise ValidationError(f"{unit.file.name} is held by an order - it cannot be deleted")


class StockItemStateMixin:
    """The "who holds this unit" column, shown both on the Product page and standalone."""

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related(active_allocations())

    @admin.display(description="State")
    def state(self, obj: StockItem):
        return stock_item_state(obj)


class StockItemInline(StockItemStateMixin, admin.TabularInline):
    model = StockItem
    formset = StockItemInlineFormSet
    fields = ["file", "state", "created_at"]
    # created_at is editable=False, so it can only appear here as a read-only column.
    readonly_fields = ["state", "created_at"]
    extra = 0
    show_change_link = True


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
    """
    Human-readable state of a unit: it belongs to the allocation holding it, if any.

    "Available" means nobody holds it - a RESERVED unit of an unpaid order shows as Reserved and
    is not for sale until that order expires.
    """

    held = getattr(obj, "held_by", None)
    if held is None:
        held = list(obj.allocations.exclude(state=Allocation.State.RELEASED)[:1])

    return held[0].get_state_display() if held else "Available"


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
class StockItemAdmin(StockItemStateMixin, admin.ModelAdmin):
    list_display = ["id", "product", "file", "state", "created_at"]
    list_filter = [AvailabilityFilter, "product__country", "created_at"]
    search_fields = ["product__name", "file"]
    list_select_related = ["product"]
    date_hierarchy = "created_at"
    readonly_fields = ["created_at"]

    def has_delete_permission(self, request, obj=None):
        # A unit somebody holds is part of an order - deleting it would break that order's history.
        if obj and not obj.is_available():
            return False
        return super().has_delete_permission(request, obj)
