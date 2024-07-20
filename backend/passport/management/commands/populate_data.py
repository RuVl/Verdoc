from django.core.management.base import BaseCommand
from djmoney.money import Money

from passport.models import Country, Passport, PassportFile


class Command(BaseCommand):
    help = 'Populates the database with test data'

    def handle(self, *args, **kwargs):
        self.populate_data()

    def populate_data(self):
        # Удалить все предыдущие данные
        Country.objects.all().delete()
        Passport.objects.all().delete()
        PassportFile.objects.all().delete()

        # Создание стран
        usa = Country.objects.create(name='USA', code='us')
        australia = Country.objects.create(name='Australia', code='au')
        argentina = Country.objects.create(name='Argentina', code='ar')

        # Создание паспортов для USA
        passport_usa = Passport.objects.create(country=usa, name='USA Passport', price=Money(123, 'USD'))
        PassportFile.objects.create(passport=passport_usa, file_path='path/to/usa_passport_scan.jpg')

        # Создание паспортов для Australia
        passport_australia = Passport.objects.create(country=australia, name='Australia Passport', price=Money(123, 'USD'))
        PassportFile.objects.create(passport=passport_australia, file_path='path/to/australia_passport_scan.jpg')
        PassportFile.objects.create(passport=passport_australia, file_path='path/to/australia_dl_photo.jpg')
        PassportFile.objects.create(passport=passport_australia, file_path='path/to/drive_safely_card.jpg')
        PassportFile.objects.create(passport=passport_australia, file_path='path/to/medicare_card.jpg')

        # Создание паспортов для Argentina
        passport_argentina = Passport.objects.create(country=argentina, name='Argentina Passport', price=Money(123, 'USD'))
        PassportFile.objects.create(passport=passport_argentina, file_path='path/to/argentina_passport_scan.jpg')

        self.stdout.write(self.style.SUCCESS('Data populated successfully'))
