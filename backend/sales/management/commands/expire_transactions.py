from django.core.management.base import BaseCommand
from django.db.transaction import atomic

from sales.models import Order


class Command(BaseCommand):
    help = "Expires unpaid orders and releases the stock units they were holding"

    @atomic
    def handle(self, *args, **kwargs):
        pending_orders = Order.objects.filter(status=Order.OrderStatus.PENDING)
        expired_orders = [order for order in pending_orders if order.is_expired()]

        try:
            for order in expired_orders:
                order.status = Order.OrderStatus.EXPIRED
                order.release()

            Order.objects.bulk_update(expired_orders, ["status"])

            self.stdout.write(self.style.SUCCESS("Successfully released expired reservations"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Cannot expire orders:\n{expired_orders}\nError: {e}"))
