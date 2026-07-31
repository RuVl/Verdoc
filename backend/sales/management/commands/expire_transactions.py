import logging

from django.core.management.base import BaseCommand
from django.db.transaction import atomic

from sales.models import Order

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Expires unpaid orders and releases the stock units they were holding"

    def handle(self, *args, **kwargs):
        pending = Order.objects.filter(status=Order.OrderStatus.PENDING).order_by("pk")
        expired = [order for order in pending if order.is_expired()]

        released, failed = 0, []
        for order in expired:
            # One transaction per order: a single broken order must not keep every other order's
            # units locked until the next run.
            try:
                with atomic():
                    order.status = Order.OrderStatus.EXPIRED
                    order.release()
                    order.save(update_fields=["status"])
            except Exception as e:
                failed.append(order.pk)
                logger.exception(f"Cannot expire order {order.pk}: {e}")
            else:
                released += 1

        self.stdout.write(self.style.SUCCESS(f"Released {released} of {len(expired)} expired orders"))
        if failed:
            self.stdout.write(self.style.ERROR(f"Failed to expire orders: {failed}"))
