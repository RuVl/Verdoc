from djmoney.contrib.exchange.models import convert_money
from rest_framework import serializers

from order.models import OrderItem, Order
from passport.models import Passport


class OrderItemSerializer(serializers.ModelSerializer):
    passport_id = serializers.PrimaryKeyRelatedField(
        queryset=Passport.objects.all(), source='passport'
    )

    class Meta:
        model = OrderItem
        fields = ['passport_id', 'quantity']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    total_price = 0  # Calculate total_price while validate

    class Meta:
        model = Order
        fields = ['id', 'user_email', 'items']

    def validate(self, data):
        items_data = data['items']
        for item in items_data:
            if item['passport'].quantity < item['quantity']:
                raise serializers.ValidationError(f'There are not enough passports {item['passport'].name}')

            amount = convert_money(item['passport'].price, 'USD').amount
            self.total_price += amount * item['quantity']

        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        order = Order.objects.create(total_price=self.total_price, **validated_data)

        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)

        return order
