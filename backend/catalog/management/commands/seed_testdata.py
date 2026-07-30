"""Seed the catalog with test data for local/manual UI testing.

Creates countries and products covering normal and edge cases (long/short/
unbreakable names, cheap/expensive prices, low/high stock). StockItems are
bulk-created with placeholder paths (no real files on disk); stock is derived
from the units themselves, there is no counter to keep in sync.
"""

from django.core.management.base import BaseCommand
from django.db.transaction import atomic

from catalog.models import Country, Product, StockItem

# Each country: code, (name_en, name_ru), list of products.
# Product: (name_en, name_ru, price, currency, in_stock_count).
SEED = [
    (
        "us",
        ("United States", "США"),
        [
            ("USA Passport scan", "США Паспорт скан", "123.00", "USD", 24),
            ("USA Driver License (front)", "США Водительские права (лицевая)", "89.50", "USD", 12),
            (
                "USA DL front + back + selfie + SSN card + Medicare card + proof of address bundle",
                "США ВУ лицевая + оборот + селфи + карта SSN + карта Medicare + подтверждение адреса (комплект)",
                "349.99",
                "USD",
                5,
            ),
            ("USA SSN card", "США карта SSN", "0.99", "USD", 1),  # cheapest + lowest stock
            ("USA Green Card", "США Грин-карта", "12345.67", "USD", 3),  # most expensive
            ("USA Utility bill", "США счёт за коммуналку", "19.00", "USD", 999),  # highest stock
            ("USA Bank statement", "США банковская выписка", "45.00", "RUB", 40),
        ],
    ),
    (
        "gb",
        ("United Kingdom", "Великобритания"),
        [
            ("UK Passport scan", "Великобритания Паспорт скан", "150.00", "USD", 30),
            ("UK Driving Licence", "Великобритания Водительские права", "110.00", "USD", 18),
            ("UK Proof of address", "Великобритания подтверждение адреса", "25.00", "USD", 7),
            ("UK Bank statement", "Великобритания банковская выписка", "40.00", "USD", 60),
            ("UK BRP card", "Великобритания карта BRP", "95.00", "RUB", 9),
        ],
    ),
    (
        "de",
        ("Germany", "Германия"),
        [
            ("Germany Passport scan", "Германия Паспорт скан", "140.00", "USD", 22),
            ("Germany ID card (Personalausweis)", "Германия удостоверение личности", "120.00", "USD", 15),
            ("Germany Driver License", "Германия Водительские права", "115.00", "USD", 11),
            ("Germany Anmeldung", "Германия Anmeldung (регистрация)", "30.00", "USD", 50),
            ("Germany Bank statement (Kontoauszug)", "Германия банковская выписка", "42.00", "USD", 33),
            (
                "Reisepass+Personalausweis+Fuehrerschein+Selfie+Meldebescheinigung+Kontoauszug",
                "Reisepass+Personalausweis+Fuehrerschein+Selfie+Meldebescheinigung+Kontoauszug",
                "299.00",
                "USD",
                4,
            ),  # long unbreakable token, no spaces
        ],
    ),
    (
        "fr",
        ("France", "Франция"),
        [
            ("France Passport scan", "Франция Паспорт скан", "135.00", "USD", 20),
            ("France ID card (CNI)", "Франция удостоверение личности", "118.00", "USD", 14),
            ("France Driver License", "Франция Водительские права", "112.00", "USD", 10),
            ("France Proof of address (justificatif)", "Франция подтверждение адреса", "28.00", "USD", 45),
            ("France RIB (bank details)", "Франция реквизиты банка (RIB)", "35.00", "RUB", 25),
            ("France Titre de sejour", "Франция вид на жительство", "160.00", "USD", 6),
        ],
    ),
    (
        "ca",
        ("Canada", "Канада"),
        [
            ("Canada Passport scan", "Канада Паспорт скан", "145.00", "USD", 26),
            ("Canada Driver License", "Канада Водительские права", "108.00", "USD", 17),
            ("Canada PR card", "Канада карта PR", "155.00", "USD", 8),
            ("Canada SIN document", "Канада документ SIN", "60.00", "USD", 30),
            ("Canada Utility bill", "Канада счёт за коммуналку", "22.00", "USD", 70),
        ],
    ),
    (
        "au",
        ("Australia", "Австралия"),
        [
            ("Australia Passport scan", "Австралия Паспорт скан", "138.00", "USD", 21),
            ("Australia Driver License", "Австралия Водительские права", "105.00", "USD", 13),
            ("Australia Medicare card", "Австралия карта Medicare", "70.00", "USD", 16),
            ("Australia Proof of age card", "Австралия карта подтверждения возраста", "55.00", "USD", 28),
            ("Australia Bank statement", "Австралия банковская выписка", "38.00", "RUB", 34),
            (
                "Australia DL (both sides) + selfie + passport + selfie + Medicare card combo",
                "Австралия ВУ (обе стороны) + селфи + паспорт + селфи + карта Medicare (комплект)",
                "260.00",
                "USD",
                5,
            ),
        ],
    ),
    (
        "jp",
        ("Japan", "Япония"),
        [
            ("Japan Passport scan", "Япония Паспорт скан", "142.00", "USD", 19),
            ("Japan Driver License", "Япония Водительские права", "109.00", "USD", 12),
            ("Japan Residence card (Zairyu)", "Япония карта резидента (Zairyu)", "125.00", "USD", 9),
            ("Japan My Number card", "Япония карта My Number", "80.00", "USD", 24),
            ("Japan Bank book (Tsucho)", "Япония банковская книжка (Tsucho)", "48.00", "USD", 31),
        ],
    ),
    (
        "br",
        ("Brazil", "Бразилия"),
        [
            ("Brazil Passport scan", "Бразилия Паспорт скан", "130.00", "USD", 18),
            ("Brazil RG (identity card)", "Бразилия удостоверение личности (RG)", "100.00", "USD", 15),
            ("Brazil CPF document", "Бразилия документ CPF", "58.00", "USD", 40),
            ("Brazil Driver License (CNH)", "Бразилия Водительские права (CNH)", "104.00", "USD", 11),
            ("Brazil Proof of address (comprovante)", "Бразилия подтверждение адреса", "24.00", "RUB", 52),
            ("Brazil Out-of-stock sample (hidden)", "Бразилия образец без остатка (скрыт)", "77.00", "USD", 0),
        ],
    ),
]


class Command(BaseCommand):
    help = "Seed the catalog with test countries and products for manual UI testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all existing countries, products and stock items before seeding",
        )

    @atomic
    def handle(self, *args, **options):
        if options["flush"]:
            deleted = Country.objects.all().delete()
            StockItem.objects.filter(product__isnull=True).delete()
            self.stdout.write(self.style.WARNING(f"Flushed existing catalog: {deleted}"))

        countries = 0
        products = 0
        units = 0
        for code, (name_en, name_ru), items in SEED:
            country, _ = Country.objects.get_or_create(
                code=code,
                defaults={"name_en": name_en, "name_ru": name_ru},
            )
            country.name_en = name_en
            country.name_ru = name_ru
            country.save()
            countries += 1

            for name_en_p, name_ru_p, price, currency, stock in items:
                product = Product.objects.create(
                    name_en=name_en_p,
                    name_ru=name_ru_p,
                    price=price,
                    price_currency=currency,
                    country=country,
                )
                products += 1

                if stock:
                    StockItem.objects.bulk_create(
                        StockItem(file=f"products/seed-{product.id}-{i}.jpg", product=product) for i in range(stock)
                    )
                    units += stock

        self.stdout.write(self.style.SUCCESS(f"Seeded {countries} countries, {products} products, {units} units."))
