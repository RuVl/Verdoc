from django.conf import settings
from django.db.transaction import atomic
from djmoney.contrib.exchange.models import convert_money
from rest_framework import serializers

from catalog.models import Product
from customer.models import Customer
from customer.validators import validate_email_domain
from sales.models import Allocation, Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    """OrderItem serializer for OrderSerializer. Accepts only product_id and quantity."""

    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source="product",
    )
    quantity = serializers.IntegerField(min_value=1)

    class Meta:
        model = OrderItem
        fields = ["product_id", "quantity"]

    def validate_quantity(self, value):
        # Read at call time so the cap can be overridden per deployment and in tests.
        if value > settings.MAX_ITEM_QUANTITY:
            raise serializers.ValidationError(f"At most {settings.MAX_ITEM_QUANTITY} units of one product per order")

        return value


class OrderSerializer(serializers.ModelSerializer):
    """
    Order serializer for making an order.

    Accepts only email, a list of items and the site language; the price is computed here,
    never taken from the client.
    """

    email = serializers.EmailField(write_only=True, validators=[validate_email_domain])
    language = serializers.ChoiceField(choices=settings.LANGUAGES, write_only=True, required=False)
    items = OrderItemSerializer(many=True, allow_empty=False)
    total_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )  # Calculate total_price while validate

    class Meta:
        model = Order
        fields = ["email", "language", "items", "total_price"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set by validate() when the customer already has a live invoice for this cart.
        self.reused_order: Order | None = None

    def validate_items(self, items):
        if len(items) > settings.MAX_ORDER_ITEMS:
            raise serializers.ValidationError(f"At most {settings.MAX_ORDER_ITEMS} different products per order")

        product_ids = [item["product"].pk for item in items]
        if len(set(product_ids)) != len(product_ids):
            # Two lines of the same product would each pass the per-item cap and the availability
            # check on their own, while together they exceed both.
            raise serializers.ValidationError("Each product may appear only once - use quantity instead")

        return items

    def validate(self, data):
        total_price = 0

        for item in data["items"]:
            product = item["product"]
            item["unit_price_usd"] = convert_money(product.price, "USD").amount
            total_price += item["unit_price_usd"] * item["quantity"]

        data["total_price"] = total_price

        self.reused_order = Order.objects.reusable(data["email"], data["items"])
        if self.reused_order is not None:
            # Its units are already reserved - an availability check here would refuse the customer
            # their own reservation.
            return data

        for item in data["items"]:
            product = item["product"]
            if product.available_count() < item["quantity"]:
                raise serializers.ValidationError(f"There are not enough products {product.name}")

        return data

    @atomic
    def create(self, validated_data):
        language = validated_data.pop("language", None)

        if self.reused_order is not None:
            # Still worth recording: they may have switched the site language since the invoice.
            self.reused_order.customer.set_language(language)
            return self.reused_order

        items_data = validated_data.pop("items")
        total_price = validated_data.pop("total_price")
        customer, _ = Customer.objects.get_or_create(email=validated_data.pop("email"))
        customer.set_language(language)

        order = Order.objects.create(customer=customer, total_price=total_price, **validated_data)

        for item_data in items_data:
            product = item_data["product"]
            OrderItem.objects.create(
                order=order,
                product=product,
                # Snapshot: the catalog is free to change afterwards, this order is not.
                product_name=product.name,
                unit_price=product.price,
                unit_price_usd=item_data["unit_price_usd"],
                quantity=item_data["quantity"],
            ).reserve()

        return order


class SendDownloadLinksSerializer(serializers.Serializer):
    """
    Serializer for sending download links.

    Accepts the email and, optionally, the site language to answer in.
    """

    email = serializers.EmailField()
    language = serializers.ChoiceField(choices=settings.LANGUAGES, required=False)


class AllocationSerializer(serializers.ModelSerializer):
    """One downloadable file on the purchases page."""

    is_downloadable = serializers.BooleanField(source="is_token_valid", read_only=True)
    download_url = serializers.SerializerMethodField()
    expires_at = serializers.DateTimeField(source="token_expires_at", read_only=True)

    class Meta:
        model = Allocation
        fields = ["id", "is_downloadable", "download_url", "expires_at"]

    def get_download_url(self, obj: Allocation) -> str | None:
        # No link at all rather than a dead one: an expired token has to be refreshed first.
        if not obj.is_token_valid():
            return None

        return obj.get_download_url(self.context.get("request"))


class PurchaseItemSerializer(serializers.ModelSerializer):
    """A bought position, named and priced as of the day it was bought."""

    allocations = AllocationSerializer(many=True, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product_name", "unit_price", "unit_price_currency", "quantity", "allocations"]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    """One paid order with everything the customer can download from it."""

    items = PurchaseItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ["id", "status", "total_price", "total_price_currency", "created_at", "paid_at", "items"]
