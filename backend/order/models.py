import uuid

from django.conf import settings
from django.contrib.sites.models import Site
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from djmoney.models.fields import MoneyField


class Order(models.Model):
    """
        Model for storing order information.

        :param user_email: Recipient's email address of the order.
        :param status: Order status (PENDING, PAID, OVERPAID, EXPIRED, ERROR, CANCELLED).
        :param total_price: Total price of the order.
        :param created_at: Date and time when the order was created.
        :param updated_at: Date and time when the order was last updated.
    """

    class OrderStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PAID = 'PAID', 'Paid'
        OVERPAID = 'OVERPAID', 'Overpaid'
        EXPIRED = 'EXPIRED', 'Expired'
        ERROR = 'ERROR', 'Error'
        CANCELLED = 'CANCELLED', 'Cancelled'

    user_email = models.EmailField()
    status = models.CharField(max_length=15, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    total_price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Order {self.id} - {self.user_email}'

    def reset_reservation(self):
        with transaction.atomic():
            for order_item in self.items.all():
                order_item.reset_reservation()

    def sell(self) -> list['DownloadLink']:
        download_links = []
        for order_item in self.items.all():
            download_links.extend(order_item.sell())

        return download_links


class OrderItem(models.Model):
    """
        Model for storing order information for one passport.

        :param order: Order which this item belongs to.
        :param passport: Order's passport.
        :param quantity: Quantity of the passport files.
        :param is_reserved: Boolean flag to indicate whether the files are reserved.
    """

    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    passport = models.ForeignKey('passport.Passport', on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    is_reserved = models.BooleanField(default=False, editable=False)

    def __str__(self):
        return f'{self.quantity} x {self.passport.name if self.passport else 'NULL'}'

    def reserve(self):
        if self.is_reserved:
            raise ValueError('Order item cannot be reserved twice.')

        self.is_reserved = True

        with transaction.atomic():
            self.passport.reserve(self.quantity)
            self.save()

    def reset_reservation(self):
        if not self.is_reserved:
            raise ValueError('Cannot reset unreserved order item.')

        self.is_reserved = False

        with transaction.atomic():
            self.passport.return2stock(self.quantity)
            self.save()

    def sell(self) -> list['DownloadLink']:
        if not self.is_reserved:
            raise ValueError('Cannot sell unreserved order item.')

        self.is_reserved = False

        with transaction.atomic():
            passport_files = self.passport.sell(self.quantity)
            download_links = [
                DownloadLink.objects.create(order_item=self, file_path=passport_file)
                for passport_file in passport_files
            ]
            self.save()

        return download_links


class DownloadLink(models.Model):
    """
        A model for storing unique links to download files after purchase.

        :param order_item: Order which this link belongs to.
        :param passport_file: Passport file to download.
        :param uuid: Unique identifier for the download link.
        :param updated_at: Date and time when the download link was last updated.
    """

    order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE)
    passport_file = models.OneToOneField('passport.PassportFile', on_delete=models.PROTECT)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Link for {str(self.order_item)}'

    def is_expired(self):
        """ Checks if the link has expired. Links are valid for 24 hours. """
        return timezone.now() > self.updated_at + timezone.timedelta(hours=24)

    def update_link(self):
        self.uuid = uuid.uuid4()
        self.updated_at = timezone.now()
        self.save()

    def get_link(self):
        relative_path = reverse('download-file', args=[self.order_item.order.user_email, self.uuid])
        scheme = settings.SITE_SCHEME
        domain = Site.objects.get_current().domain
        return f'{scheme}://{domain}{relative_path}'


class Transaction(models.Model):
    # noinspection GrazieInspection
    """
        Model for storing transaction information.

        :param order: Order which this transaction belongs to.
        :param txn_id: Unique identifier for the transaction (changes when a customer switches currency).
        :param amount: Amount of the transaction's cryptocurrency.
        :param currency: Currency of the transaction.
        :param source_price: Source amount and currency of the transaction (if provided).
        :param source_rate: Exchange rate currency to source_currency (if source_currency provided).
        :param commission: Commission amount of the transaction.
        :param status: Status of the transaction: new, pending, pending internal, expired, completed, mismatch, error, cancelled, cancelled duplicate.
        :param confirmations: Number of confirmations of the crypto transaction.
        :param created_at: Date and time of the transaction create.
        :param updated_at: Date and time of the last transaction update.
        :param merchant: Merchant name (from api settings).
        :param merchant_id: Merchant ID (from api settings).
        :param comment: Transaction comment (if provided).
    """

    class TransactionStatus(models.TextChoices):
        NEW = 'new', 'New'
        PENDING = 'pending', 'Pending'
        PENDING_INTERNAL = 'pending internal', 'Pending Internal'
        EXPIRED = 'expired', 'Expired'
        COMPLETED = 'completed', 'Completed'
        MISMATCH = 'mismatch', 'Mismatch'
        ERROR = 'error', 'Error'
        CANCELLED = 'cancelled', 'Cancelled'
        CANCELLED_DUPLICATE = 'cancelled duplicate', 'Cancelled Duplicate'

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='transaction')
    txn_id = models.CharField(max_length=100, null=True, blank=True)

    amount = models.DecimalField(max_digits=20, decimal_places=10)
    currency = models.CharField(max_length=10)

    source_price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD', null=True, blank=True)  # source_amount and source_currency
    source_rate = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    commission = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)

    status = models.CharField(max_length=30, choices=TransactionStatus.choices, default=TransactionStatus.NEW)
    confirmations = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    merchant = models.CharField(max_length=127, null=True, blank=True)
    merchant_id = models.CharField(max_length=63, null=True, blank=True)
    comment = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f'Transaction {self.id} - {self.order.user_email}'
