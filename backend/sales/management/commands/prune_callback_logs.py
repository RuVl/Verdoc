import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from sales.models import PaymentCallbackLog

logger = logging.getLogger(__name__)

# Long enough to debug a sale somebody complains about weeks later, short enough that the table
# does not grow forever - Plisio sends several callbacks per invoice and retries the failed ones.
DEFAULT_RETENTION_DAYS = 180


class Command(BaseCommand):
    help = "Delete raw Plisio callback payloads older than the retention window"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=DEFAULT_RETENTION_DAYS, help="Keep this many days.")
        parser.add_argument("--dry-run", action="store_true", help="Only report how many would go.")

    def handle(self, *args, **options):
        days = options["days"]
        if days < 1:
            # Nothing here is worth a command that empties the table in one keystroke.
            self.stderr.write(self.style.ERROR("--days must be at least 1"))
            return

        cutoff = timezone.now() - timedelta(days=days)
        stale = PaymentCallbackLog.objects.filter(received_at__lt=cutoff)

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"Dry run: {stale.count()} callback(s) older than {cutoff:%Y-%m-%d}"))
            return

        deleted, _ = stale.delete()
        if deleted:
            logger.info(f"Pruned {deleted} payment callback log(s) older than {days} days")

        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} callback(s) older than {cutoff:%Y-%m-%d}"))
