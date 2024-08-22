from django.core.management.base import BaseCommand
from django.db.transaction import atomic

from order.models import Order


class Command(BaseCommand):
    help = 'Expires unpaid transactions and remove reservation of ProductFiles'

    @atomic
    def handle(self, *args, **kwargs):
        pending_orders = Order.objects.filter(status__in=[Order.OrderStatus.PENDING])
        expired_orders = [
            order
            for order in pending_orders
            if order.is_expired()
        ]

        try:
            for order in expired_orders:
                order.status = Order.OrderStatus.EXPIRED
                order.reset_reservation()

            Order.objects.bulk_update(expired_orders, ['status'])

            self.stdout.write(self.style.SUCCESS('Successfully updated exchange rates'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Cannot delete unpaid transactions: {e}'))
