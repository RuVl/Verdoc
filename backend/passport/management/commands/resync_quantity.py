"""Recompute Passport.quantity from its PassportFile rows.

The post_save/post_delete signal in passport.signals keeps Passport.quantity
(the IN_STOCK count) in sync. If files were added while the signal was not
connected, quantity drifts. This command recomputes it for every Passport and
reports the IN_STOCK / RESERVED / SOLD breakdown.

Use --dry-run to preview without writing.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from passport.models import Passport, PassportFile

Status = PassportFile.PassportFileStatus


class Command(BaseCommand):
    help = "Recompute Passport.quantity (IN_STOCK count) from PassportFile rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without saving.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        passports = Passport.objects.annotate(
            in_stock=Count("files", filter=Q(files__status=Status.IN_STOCK)),
            reserved=Count("files", filter=Q(files__status=Status.RESERVED)),
            sold=Count("files", filter=Q(files__status=Status.SOLD)),
        )

        fixed = 0
        for passport in passports:
            correct = passport.in_stock
            if passport.quantity != correct:
                self.stdout.write(
                    f"Passport #{passport.pk} '{passport.name}': "
                    f"quantity {passport.quantity} -> {correct} "
                    f"(in_stock={passport.in_stock}, reserved={passport.reserved}, sold={passport.sold})"
                )
                if not dry_run:
                    Passport.objects.filter(pk=passport.pk).update(quantity=correct)
                fixed += 1

        if fixed == 0:
            self.stdout.write(self.style.SUCCESS("All Passport quantities already correct."))
        elif dry_run:
            self.stdout.write(self.style.WARNING(f"{fixed} passport(s) would be updated (dry run, nothing saved)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated {fixed} passport(s)."))
