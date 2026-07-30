from django.conf import settings
from django.db.transaction import atomic
from djmoney.contrib.exchange.models import convert_money
from rest_framework import serializers

from catalog.models import Product
from customer.models import Customer
from sales.models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    """
    OrderItem serializer for OrderSerializer.

    Accepts only passport_id and quantity - the storefront keeps its own wording until R2, hence
    the field name pointing at `product`.
    """

    passport_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source="product",
    )
    quantity = serializers.IntegerField(min_value=1)

    class Meta:
        model = OrderItem
        fields = ["passport_id", "quantity"]

    def validate_quantity(self, value):
        # Read at call time so the cap can be overridden per deployment and in tests.
        if value > settings.MAX_ITEM_QUANTITY:
            raise serializers.ValidationError(f"At most {settings.MAX_ITEM_QUANTITY} units of one product per order")

        return value


class OrderSerializer(serializers.ModelSerializer):
    """
    Order serializer for making an order.

    Accepts only user_email and a list of items; the price is computed here, never taken from the
    client. `user_email` is the API name of the customer's email until R2.
    """

    user_email = serializers.EmailField(write_only=True)
    items = OrderItemSerializer(many=True, allow_empty=False)
    total_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )  # Calculate total_price while validate

    class Meta:
        model = Order
        fields = ["user_email", "items", "total_price"]

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
            available = product.available_count()
            if available < item["quantity"]:
                raise serializers.ValidationError(f"There are not enough products {product.name}")

            item["unit_price_usd"] = convert_money(product.price, "USD").amount
            total_price += item["unit_price_usd"] * item["quantity"]

        data["total_price"] = total_price
        return data

    @atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")
        total_price = validated_data.pop("total_price")
        customer, _ = Customer.objects.get_or_create(email=validated_data.pop("user_email"))

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

    Accepts only email.
    """

    email = serializers.EmailField()
