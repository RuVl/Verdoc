from django.db import transaction
from djmoney.contrib.exchange.models import convert_money
from rest_framework import serializers

from order.models import OrderItem, Order
from passport.models import Passport


class OrderItemSerializer(serializers.ModelSerializer):
    """
        OrderItem model serializer for OrderSerializer.\n
        Accepts only passport_id and quantity.
    """

    passport_id = serializers.PrimaryKeyRelatedField(queryset=Passport.objects.filter(quantity__gt=0), source='passport')

    class Meta:
        model = OrderItem
        fields = ['passport_id', 'quantity']

    def validate(self, data):
        passport = data['passport']
        if passport.quantity < data['quantity']:
            raise serializers.ValidationError(detail=f'Not enough available passports for {passport.id}')

        return data


class OrderSerializer(serializers.ModelSerializer):
    """
        Order model serializer for making order.\n
        Accepts only user_email and list of OrderItemsSerializer.
    """

    items = OrderItemSerializer(many=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)  # Calculate total_price while validate

    class Meta:
        model = Order
        fields = ['user_email', 'items', 'total_price']

    def validate(self, data):
        total_price = 0
        items_data = data['items']

        for item in items_data:
            if item['passport'].quantity < item['quantity']:
                raise serializers.ValidationError(f'There are not enough passports {item["passport"].name}')

            amount = convert_money(item['passport'].price, 'USD').amount
            total_price += amount * item['quantity']

        data['total_price'] = total_price  # Добавление total_price в data
        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        total_price = validated_data.pop('total_price')

        with transaction.atomic():
            # Create order and reserve it
            order = Order.objects.create(total_price=total_price, **validated_data)

            # Create and reserve order_items
            for item_data in items_data:
                OrderItem.objects.create(order=order, **item_data).reserve()

            return order


class SendDownloadLinksSerializer(serializers.Serializer):
    """
        Serializer for sending download links.\n
        Accepts only email.
    """

    email = serializers.EmailField()
