from django.db import models
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField


class Country(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=31, null=True, default=None)

    class Meta:
        verbose_name = _('Country')
        verbose_name_plural = _('Countries')
        ordering = ['name']

    def __str__(self):
        return self.name


class Passport(models.Model):
    country = models.ForeignKey(Country, related_name='passports', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    quantity = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        verbose_name = _('Passport')
        verbose_name_plural = _('Passports')
        ordering = ['name']

    def __str__(self):
        return self.name


class PassportFile(models.Model):
    class PassportFileStatus(models.TextChoices):
        IN_STOCK = 'IN_STOCK', _('In stock')
        RESERVED = 'RESERVED', _('Reserved')
        SOLD = 'SOLD', _('Sold')

    passport = models.ForeignKey(Passport, related_name='files', on_delete=models.SET_NULL, null=True)
    file_path = models.FileField(upload_to='passports/', unique=True)
    status = models.CharField(max_length=20, choices=PassportFileStatus.choices, default=PassportFileStatus.IN_STOCK, editable=False)

    class Meta:
        verbose_name = _('Passport File')
        verbose_name_plural = _('Passport Files')
        ordering = ['passport', 'file_path']

    def __str__(self):
        return f'{self.passport.name if self.passport else "NULL"} - {self.status}'
