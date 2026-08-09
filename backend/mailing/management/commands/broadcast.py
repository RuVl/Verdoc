import logging
import time

from django.core.mail import get_connection
from django.core.management.base import BaseCommand, CommandError

from mailing.models import Broadcast
from mailing.services import build_broadcast_email, get_broadcast_recipients, send_broadcast_test

logger = logging.getLogger(__name__)

# SMTP rate-limit: send in batches with a pause in between.
BATCH_SIZE = 20
BATCH_PAUSE_SECONDS = 5.0


class Command(BaseCommand):
    help = "Send queued broadcasts to paid buyers (excluding unsubscribed)."

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, default=None, help="Send a specific broadcast by id.")
        parser.add_argument("--test", action="store_true", help="Send only to broadcast.test_email.")
        parser.add_argument("--dry-run", action="store_true", help="Print recipients without sending.")

    def handle(self, *args, **options):
        broadcast_id = options["id"]
        test = options["test"]
        dry_run = options["dry_run"]

        if broadcast_id is not None:
            try:
                broadcasts = [Broadcast.objects.get(pk=broadcast_id)]
            except Broadcast.DoesNotExist:
                raise CommandError(f"Broadcast {broadcast_id} not found.") from None
        else:
            broadcasts = list(Broadcast.objects.filter(status=Broadcast.Status.QUEUED))

        if not broadcasts:
            self.stdout.write(self.style.WARNING("No broadcasts to send."))
            return

        for broadcast in broadcasts:
            if test:
                self._send_test(broadcast, dry_run=dry_run)
            else:
                self._send_one(broadcast, dry_run=dry_run)

    def _send_test(self, broadcast: Broadcast, dry_run: bool):
        """A test run never touches the delivery ledger - the address need not be a customer."""

        if not broadcast.test_email:
            raise CommandError(f"Broadcast {broadcast.id} has no test_email.")

        if dry_run:
            self.stdout.write(f"[dry-run] Broadcast {broadcast.id}: test to {broadcast.test_email}")
            return

        send_broadcast_test(broadcast)

        self.stdout.write(self.style.SUCCESS(f"Broadcast {broadcast.id}: test sent to {broadcast.test_email}"))

    def _send_one(self, broadcast: Broadcast, dry_run: bool):
        if dry_run:
            recipients = get_broadcast_recipients()
            self.stdout.write(f"[dry-run] Broadcast {broadcast.id}: {recipients.count()} recipients")
            for customer in recipients:
                self.stdout.write(f"  {customer.email}")
            return

        # Phase one: write down who is owed a message. Repeat runs add newcomers and change
        # nothing else, so an interrupted send resumes instead of starting over.
        outstanding = broadcast.plan(get_broadcast_recipients())
        if not outstanding:
            self.stdout.write(self.style.WARNING(f"Broadcast {broadcast.id}: nobody to send to."))
            broadcast.finish()
            return

        broadcast.status = Broadcast.Status.SENDING
        broadcast.save(update_fields=["status"])

        # Phase two: work the ledger down. Each row is closed the moment its message is out, so
        # a crash costs at most the one in flight.
        sent, failed = 0, 0
        connection = get_connection()  # opened lazily on first send()
        try:
            deliveries = broadcast.deliveries.outstanding().select_related("customer")
            for i, delivery in enumerate(deliveries.iterator()):
                if i and i % BATCH_SIZE == 0:
                    time.sleep(BATCH_PAUSE_SECONDS)
                try:
                    build_broadcast_email(connection, broadcast, delivery.customer).send()
                    delivery.mark_sent()
                    sent += 1
                except Exception as e:  # noqa: BLE001 - one bad address must not stop the run
                    delivery.mark_failed(str(e))
                    failed += 1
                    logger.exception("Broadcast %s failed for %s", broadcast.id, delivery.customer.email)
        finally:
            connection.close()

        broadcast.finish()

        style = self.style.ERROR if broadcast.status == Broadcast.Status.FAILED else self.style.SUCCESS
        self.stdout.write(style(f"Broadcast {broadcast.id}: sent {sent}, failed {failed} of {outstanding}"))
