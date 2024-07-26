import uuid

from django.db import models
from django.urls import reverse
from django.utils import timezone
from djmoney.models.fields import MoneyField


class Order(models.Model):
    """ Модель для хранения информации о заказах. """

    class OrderStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PAID = 'PAID', 'Paid'
        OVERPAID = 'OVERPAID', 'Overpaid'
        EXPIRED = 'EXPIRED', 'Expired'
        ERROR = 'ERROR', 'Error'
        CANCELLED = 'CANCELLED', 'Cancelled'

    user_email = models.EmailField()
    status = models.CharField(max_length=10, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    total_price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Order {self.id} - {self.user_email}'


class OrderItem(models.Model):
    """ Модель для хранения информации о товарах в заказе. """
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    passport = models.ForeignKey('passport.Passport', on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f'{self.quantity} x {self.passport.name if self.passport else 'NULL'}'


class DownloadLink(models.Model):
    """ Модель для хранения уникальных ссылок на скачивание файлов после покупки. """
    order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE)
    passport_file = models.OneToOneField('passport.PassportFile', on_delete=models.PROTECT)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Link for {str(self.order_item)}'

    def is_expired(self):
        """ Проверяет, истекла ли ссылка. Ссылки действуют 24 часа. """
        return timezone.now() > self.updated_at + timezone.timedelta(hours=24)

    def get_link(self):
        return reverse('download-file', args=[self.order_item.order.user_email, self.uuid])


class Transaction(models.Model):
    """ Модель для хранения информации о транзакциях. """

    class TransactionStatus(models.TextChoices):
        NEW = 'new', 'New'
        PENDING = 'pending', 'Pending'
        PENDING_INTERNAL = 'pending internal', 'Pending Internal'
        EXPIRED = 'expired', 'Expired'
        COMPLETED = 'completed', 'Completed'
        MISMATCH = 'mismatch', 'Mismatch'
        ERROR = 'error', 'Error'
        CANCELLED = 'cancelled', 'Cancelled'

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='transaction')
    txn_id = models.CharField(max_length=100, null=True, blank=True)
    amount = models.DecimalField(max_digits=20, decimal_places=10)
    currency = models.CharField(max_length=10)
    source_price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', null=True, blank=True)
    source_rate = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    status = models.CharField(max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.NEW)
    confirmations = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    commission = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)

    def __str__(self):
        return f'Transaction {self.id} - {self.order.user_email}'
