from django.test import TestCase

from passport.models import Country, Passport, PassportFile


class PassportReserveTests(TestCase):
    def setUp(self):
        self.country = Country.objects.create(name="Testland", code="tl")
        self.passport = Passport.objects.create(name="Test", country=self.country, price=10)
        for i in range(3):
            PassportFile.objects.create(file_path=f"products/passports/{i}.pdf", passport=self.passport)

    def test_reserve_flips_status_and_decrements_quantity(self):
        self.passport.refresh_from_db()
        reserved = self.passport.reserve(2)

        self.assertEqual(len(reserved), 2)
        self.passport.refresh_from_db()
        self.assertEqual(self.passport.quantity, 1)
        self.assertTrue(all(f.status == PassportFile.PassportFileStatus.RESERVED for f in reserved))

    def test_reserve_more_than_stock_raises(self):
        with self.assertRaises(ValueError):
            self.passport.reserve(10)

    def test_return2stock_restores_quantity(self):
        self.passport.refresh_from_db()
        self.passport.reserve(2)

        self.passport.refresh_from_db()
        returned = self.passport.return2stock(2)

        self.assertEqual(len(returned), 2)
        self.passport.refresh_from_db()
        self.assertEqual(self.passport.quantity, 3)
        self.assertTrue(all(f.status == PassportFile.PassportFileStatus.IN_STOCK for f in returned))

    def test_sell_marks_reserved_files_as_sold(self):
        self.passport.refresh_from_db()
        self.passport.reserve(1)

        sold = self.passport.sell(1)

        self.assertEqual(len(sold), 1)
        self.assertEqual(sold[0].status, PassportFile.PassportFileStatus.SOLD)
