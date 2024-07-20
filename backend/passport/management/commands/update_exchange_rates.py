from django.core.management.base import BaseCommand
from djmoney.contrib.exchange.backends import OpenExchangeRatesBackend


class Command(BaseCommand):
    help = 'Update exchange rates from OpenExchangeRates'

    def handle(self, *args, **kwargs):
        backend = OpenExchangeRatesBackend()
        backend.update_rates()
        self.stdout.write(self.style.SUCCESS('Successfully updated exchange rates'))
