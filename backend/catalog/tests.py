from django.forms import inlineformset_factory
from django.test import TestCase

from catalog.admin import StockItemInlineFormSet, stock_item_state
from catalog.models import Country, Product, StockItem
from customer.models import Customer
from sales.models import Allocation, Order, OrderItem


class DerivedStockTests(TestCase):
    """Stock is derived from allocations, so there is no counter that can drift (ADR-0002)."""

    def setUp(self):
        self.country = Country.objects.create(name="Testland", code="tl")
        self.product = Product.objects.create(name="Test", country=self.country, price=10)
        for i in range(3):
            StockItem.objects.create(file=f"products/{i}.pdf", product=self.product)

        customer = Customer.objects.create(email="buyer@example.com")
        self.order = Order.objects.create(customer=customer, total_price=10)
        self.item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=self.product.price,
            unit_price_usd=10,
            quantity=2,
        )

    def test_untouched_units_are_available(self):
        self.assertEqual(StockItem.objects.available().count(), 3)
        self.assertEqual(self.product.available_count(), 3)
        self.assertEqual(Product.objects.with_available().get(pk=self.product.pk).available, 3)

    def test_reserved_units_leave_stock(self):
        self.item.reserve()

        self.assertEqual(self.product.available_count(), 1)
        self.assertEqual(Product.objects.with_available().get(pk=self.product.pk).available, 1)

    def test_delivered_units_stay_out_of_stock(self):
        self.item.reserve()
        self.item.deliver()

        self.assertEqual(self.product.available_count(), 1)

    def test_released_units_come_back(self):
        self.item.reserve()
        self.item.release()

        self.assertEqual(self.product.available_count(), 3)
        self.assertTrue(all(unit.is_available() for unit in StockItem.objects.all()))

    def test_with_available_reports_zero_for_empty_product(self):
        empty = Product.objects.create(name="Empty", country=self.country, price=10)

        self.assertEqual(Product.objects.with_available().get(pk=empty.pk).available, 0)

    def test_stock_of_other_products_is_not_counted(self):
        other = Product.objects.create(name="Other", country=self.country, price=10)
        StockItem.objects.create(file="products/other.pdf", product=other)

        self.assertEqual(self.product.available_count(), 3)
        self.assertEqual(other.available_count(), 1)


class CountryFlagTests(TestCase):
    def test_code2flag(self):
        self.assertEqual(Country.code2flag("al"), "🇦🇱")
        self.assertEqual(Country.code2flag(None), "")

    def test_non_country_group_has_no_flag(self):
        self.assertEqual(Country(name="Other", code="-").flag, "-")


class AllocationConstraintTests(TestCase):
    """The partial unique index is what makes "one file - one buyer" physically true."""

    def setUp(self):
        country = Country.objects.create(name="Testland", code="tl")
        self.product = Product.objects.create(name="Test", country=country, price=10)
        self.unit = StockItem.objects.create(file="products/a.pdf", product=self.product)

        customer = Customer.objects.create(email="buyer@example.com")
        self.order = Order.objects.create(customer=customer, total_price=10)

    def _make_item(self):
        return OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=self.product.price,
            unit_price_usd=10,
            quantity=1,
        )

    def test_second_active_allocation_of_the_same_unit_is_rejected(self):
        first = self._make_item()
        first.reserve()

        second = self._make_item()
        with self.assertRaises(ValueError):
            # Nothing left to allocate: the only unit is held by the first item.
            second.reserve()

    def test_released_unit_can_be_allocated_again(self):
        first = self._make_item()
        first.reserve()
        first.release()

        second = self._make_item()
        second.reserve()

        self.assertEqual(Allocation.objects.filter(state=Allocation.State.RESERVED).count(), 1)
        self.assertEqual(Allocation.objects.count(), 2)


class StockItemAdminTests(TestCase):
    """The Product page lists units inline, and that table must not be a way around the FK guard."""

    def setUp(self):
        self.country = Country.objects.create(name="Testland", code="tl")
        self.product = Product.objects.create(name="Test", country=self.country, price=10)
        self.unit = StockItem.objects.create(file="products/held.pdf", product=self.product)

        customer = Customer.objects.create(email="buyer@example.com")
        order = Order.objects.create(customer=customer, total_price=10)
        self.item = OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            unit_price=self.product.price,
            unit_price_usd=10,
            quantity=1,
        )

    def formset(self, delete: bool):
        # The same formset the Product page builds for its StockItem inline.
        formset_cls = inlineformset_factory(
            Product, StockItem, formset=StockItemInlineFormSet, fields=["file"], extra=0
        )
        data = {
            "stock_items-TOTAL_FORMS": "1",
            "stock_items-INITIAL_FORMS": "1",
            "stock_items-MIN_NUM_FORMS": "0",
            "stock_items-MAX_NUM_FORMS": "1000",
            "stock_items-0-id": str(self.unit.pk),
            "stock_items-0-product": str(self.product.pk),
            "stock_items-0-file": self.unit.file.name,
        }
        if delete:
            data["stock_items-0-DELETE"] = "on"

        return formset_cls(data=data, instance=self.product, prefix="stock_items")

    def test_deleting_a_held_unit_is_rejected(self):
        Allocation.objects.create(order_item=self.item, stock_item=self.unit, state=Allocation.State.DELIVERED)

        formset = self.formset(delete=True)

        self.assertFalse(formset.is_valid())
        self.assertIn("held by an order", str(formset.non_form_errors()))

    def test_deleting_a_free_unit_is_allowed(self):
        self.assertTrue(self.formset(delete=True).is_valid())

    def test_state_column_calls_a_reserved_unit_reserved(self):
        Allocation.objects.create(order_item=self.item, stock_item=self.unit, state=Allocation.State.RESERVED)

        self.assertEqual(stock_item_state(self.unit), "Reserved")
        self.assertFalse(self.unit.is_available())


class CountryApiTests(TestCase):
    """The storefront payload. R2 dropped the passport-era key names, so their shape is pinned here."""

    def setUp(self):
        self.country = Country.objects.create(name="Testland", code="tl")
        self.product = Product.objects.create(name="Test", country=self.country, price=10)
        for i in range(2):
            StockItem.objects.create(file=f"products/{i}.pdf", product=self.product)

    def test_countries_carry_products_with_their_available_count(self):
        response = self.client.get("/api/countries/")

        self.assertEqual(response.status_code, 200)
        country = response.json()[0]
        self.assertNotIn("passports", country)

        product = country["products"][0]
        self.assertEqual(product["available"], 2)
        self.assertNotIn("quantity", product)

    def test_a_product_nobody_can_buy_is_hidden(self):
        empty = Product.objects.create(name="Empty", country=self.country, price=10)

        names = [p["name_en"] for p in self.client.get("/api/countries/").json()[0]["products"]]

        self.assertNotIn(empty.name, names)
