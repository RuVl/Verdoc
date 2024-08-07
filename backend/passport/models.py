import logging

from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField

logger = logging.getLogger(__name__)


class Country(models.Model):
    """
        Model for storing country name and code.

        :param name: Country name.
        :param code: Country code (for flag icon).
    """

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=31, null=True, default=None)

    class Meta:
        verbose_name = _('Country')
        verbose_name_plural = _('Countries')
        ordering = ['name']

    def __str__(self):
        return self.name


class Passport(models.Model):
    """
        Model for storing passport name, price, available quantity.

        :param name: Passport name.
        :param price: Passport price (for one item).
        :param quantity: Available (in stock) quantity.
        :param country: Passport's country.
    """

    name = models.CharField(max_length=255)
    price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    quantity = models.PositiveIntegerField(default=0, editable=False)

    country = models.ForeignKey(Country, related_name='passports', on_delete=models.CASCADE)

    class Meta:
        verbose_name = _('Passport')
        verbose_name_plural = _('Passports')
        ordering = ['name']

    def __str__(self):
        return self.name

    def reserve(self, count) -> list['PassportFile']:
        """ Reserve passport files """

        if self.quantity < count:
            raise ValueError('Passport quantity must be less than or equal to count')

        files = self.files.filter(status=PassportFile.PassportFileStatus.IN_STOCK)[:count]
        assert len(files) == count, 'Passport quantity is incorrect'

        self.quantity -= count
        for file in files:
            file.status = PassportFile.PassportFileStatus.RESERVED

        with transaction.atomic():
            self.save(update_fields=['quantity'])
            PassportFile.objects.bulk_update(files, ['status'])

        return files

    def return2stock(self, count) -> list['PassportFile']:
        """ Returns reserved passport files to stock """

        files = self.files.filter(status=PassportFile.PassportFileStatus.RESERVED)[:count]

        if len(files) != count:
            raise ValueError('Count must be less than or equal to reserved passport files')

        self.quantity += count
        for file in files:
            file.status = PassportFile.PassportFileStatus.IN_STOCK

        with transaction.atomic():
            self.save(update_fields=['quantity'])
            PassportFile.objects.bulk_update(files, ['status'])

        return files

    def sell(self, count) -> list['PassportFile']:
        """ Sell reserved passport files """

        files = self.files.filter(status=PassportFile.PassportFileStatus.RESERVED)[:count]
        assert len(files) == count, 'Not enough reserved passport files'

        for file in files:
            file.status = PassportFile.PassportFileStatus.SOLD

        with transaction.atomic():
            PassportFile.objects.bulk_update(files, ['status'])

        return files


class PassportFile(models.Model):
    """
        Models for storing the path to file and sale status.

        :param file_path: File path for sale.
        :param passport: Passport that defines price and name of its.
        :param status: Sale status (IN_STOCK, RESERVED, SOLD).
    """

    class PassportFileStatus(models.TextChoices):
        IN_STOCK = 'IN_STOCK', _('In stock')
        RESERVED = 'RESERVED', _('Reserved')
        SOLD = 'SOLD', _('Sold')

    file_path = models.FileField(upload_to='products/passports/', unique=True)
    status = models.CharField(max_length=20, choices=PassportFileStatus.choices, default=PassportFileStatus.IN_STOCK, editable=False)

    passport = models.ForeignKey(Passport, related_name='files', on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = _('Passport File')
        verbose_name_plural = _('Passport Files')
        ordering = ['passport', 'file_path']

    def __str__(self):
        return f'{self.passport.name if self.passport else "NULL"} - {self.status}'
