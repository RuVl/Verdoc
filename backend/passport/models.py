from django.db import models
from djmoney.models.fields import MoneyField


class Country(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=31, null=True, default=None)


class Passport(models.Model):
    country = models.ForeignKey(Country, related_name='passports', on_delete=models.CASCADE)

    name = models.CharField(max_length=255)
    price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    quantity = models.PositiveIntegerField(default=0, editable=False)


class PassportFile(models.Model):
    class PassportFileStatus(models.TextChoices):
        IN_STOCK = 'IN_STOCK', 'In stock'
        RESERVED = 'RESERVED', 'Reserved'
        SOLD = 'SOLD', 'Sold'

    passport = models.ForeignKey(Passport, related_name='files', on_delete=models.SET_NULL, null=True)
    file_path = models.FileField(upload_to='passports/', unique=True)
    status = models.CharField(max_length=20, choices=PassportFileStatus.choices, default=PassportFileStatus.IN_STOCK, editable=False)
