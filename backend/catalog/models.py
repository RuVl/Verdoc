from typing import TYPE_CHECKING

from django.apps import apps
from django.db import models
from django.db.models import Count, Exists, IntegerField, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField

if TYPE_CHECKING:
    from sales.models import Allocation


class Country(models.Model):
    """
    Group of products, usually a country (the code drives the flag icon).

    :param name: Country name (translated).
    :param code: Country code, "-" when the group is not a country.
    """

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=31, null=True, default=None)

    if TYPE_CHECKING:
        products: "ProductQuerySet"

    @property
    def flag(self) -> str:
        return self.code2flag(self.code) if self.code != "-" else "-"

    class Meta:
        verbose_name = _("Country")
        verbose_name_plural = _("Countries")
        ordering = ["name"]

    def __str__(self):
        return f"{self.flag} - {self.name}"

    @staticmethod
    def code2flag(code: str | None) -> str:
        """Return emoji flag from country code (e.g. 'al' -> '🇦🇱')."""
        return "".join(chr(0x1F1E6 + (ord(c.upper()) - ord("A"))) for c in code) if code else ""


class StockItemQuerySet(models.QuerySet):
    def available(self):
        """Units nobody holds: no allocation at all, or every allocation is RELEASED (see ADR-0002)."""

        # Imported lazily - sales points at catalog by FK, a module-level import would close the loop.
        allocation = apps.get_model("sales", "Allocation")
        held = allocation.objects.filter(stock_item=OuterRef("pk")).exclude(state=allocation.State.RELEASED)
        return self.filter(~Exists(held))


class ProductQuerySet(models.QuerySet):
    def with_available(self):
        """Annotate `available` - how many units of the product nobody holds."""

        free = (
            StockItem.objects.available()
            .filter(product=OuterRef("pk"))
            .order_by()
            .values("product")
            .annotate(count=Count("pk"))
            .values("count")
        )
        return self.annotate(available=Coalesce(Subquery(free, output_field=IntegerField()), 0))


class Product(models.Model):
    """
    Sellable position of the catalog: a name, a price and a pile of interchangeable units.

    :param name: Product name (translated).
    :param price: Price of one unit.
    :param country: Group this product belongs to.
    """

    name = models.CharField(max_length=255)
    price = MoneyField(max_digits=10, decimal_places=2, default_currency="USD")

    country = models.ForeignKey(Country, related_name="products", on_delete=models.CASCADE)

    objects = ProductQuerySet.as_manager()

    if TYPE_CHECKING:
        stock_items: StockItemQuerySet

    class Meta:
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def available_count(self) -> int:
        """Stock left. Prefer `Product.objects.with_available()` for lists - this is one query per product."""
        return self.stock_items.available().count()


class StockItem(models.Model):
    """
    One unit of a product: one file that can be sold exactly once.

    Has no status of its own - who holds it (if anybody) is a question about Allocation, see ADR-0001.

    :param file: Path to the file being sold.
    :param product: Product that gives the unit its name and price.
    :param created_at: When the unit was added to stock.
    """

    file = models.FileField(upload_to="products/", unique=True)

    product = models.ForeignKey(Product, related_name="stock_items", on_delete=models.SET_NULL, null=True)

    # Units that predate the field carry the deploy date: it is not when they arrived, but every
    # row having a date keeps the age figures from needing a second, "unknown" bucket.
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    objects = StockItemQuerySet.as_manager()

    if TYPE_CHECKING:
        allocations: models.QuerySet["Allocation"]

    class Meta:
        verbose_name = _("Stock item")
        verbose_name_plural = _("Stock items")
        ordering = ["product", "file"]

    def __str__(self):
        return f"{self.product.name if self.product else 'NULL'} - {self.file.name}"

    def is_available(self) -> bool:
        """
        Same rule as `StockItemQuerySet.available()`, for a single row.

        Held means held by anybody: a RESERVED unit of an unpaid order is just as unavailable as a
        DELIVERED one. Only RELEASED allocations leave the unit free. One query per call - use the
        queryset for lists.
        """

        allocation = apps.get_model("sales", "Allocation")
        return not self.allocations.exclude(state=allocation.State.RELEASED).exists()
