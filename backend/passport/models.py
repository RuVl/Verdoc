from django.db import models
from djmoney.models.fields import MoneyField


class Country(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=31, null=True, default=None)


class Passport(models.Model):
    country = models.ForeignKey('Country', related_name='passports', on_delete=models.CASCADE)

    name = models.CharField(max_length=255)
    price = MoneyField(max_digits=10, decimal_places=2, default_currency='USD')
    quantity = models.PositiveIntegerField(default=0, editable=False)


class PassportFile(models.Model):
    passport = models.ForeignKey('Passport', related_name='files', on_delete=models.CASCADE)
    file_path = models.FileField(upload_to='passports/', unique=True)
