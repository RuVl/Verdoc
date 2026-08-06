import logging
import time

from django.core.mail import get_connection
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from mailing.models import Broadcast
from mailing.services import build_broadcast_email, get_broadcast_recipients

logger = logging.getLogger(__name__)

# SMTP rate-limit: send in batches with a pause in between.
BATCH_SIZE = 20
BATCH_PAUSE_SECONDS = 1.0


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
            self._send_one(broadcast, test=test, dry_run=dry_run)

    def _resolve_recipients(self, broadcast: Broadcast, test: bool) -> list[str]:
        if test:
            if not broadcast.test_email:
                raise CommandError(f"Broadcast {broadcast.id} has no test_email.")
            return [broadcast.test_email]
        return get_broadcast_recipients()

    def _send_one(self, broadcast: Broadcast, test: bool, dry_run: bool):
        recipients = self._resolve_recipients(broadcast, test)

        if dry_run:
            self.stdout.write(f"[dry-run] Broadcast {broadcast.id}: {len(recipients)} recipients")
            for addr in recipients:
                self.stdout.write(f"  {addr}")
            return

        broadcast.status = Broadcast.Status.SENDING
        broadcast.total_recipients = len(recipients)
        broadcast.sent_count = 0
        broadcast.failed_count = 0
        broadcast.error_log = ""
        broadcast.save(update_fields=["status", "total_recipients", "sent_count", "failed_count", "error_log"])

        errors: list[str] = []
        connection = get_connection()  # opened lazily on first send()
        try:
            for i, addr in enumerate(recipients):
                if i and i % BATCH_SIZE == 0:
                    time.sleep(BATCH_PAUSE_SECONDS)
                try:
                    build_broadcast_email(connection, broadcast, addr).send()
                    broadcast.sent_count += 1
                except Exception as e:  # noqa: BLE001 - one bad address must not stop the run
                    broadcast.failed_count += 1
                    errors.append(f"{addr}: {e}")
                    logger.exception("Broadcast %s failed for %s", broadcast.id, addr)
        finally:
            connection.close()

        broadcast.error_log = "\n".join(errors)
        broadcast.sent_at = timezone.now()
        broadcast.status = Broadcast.Status.FAILED if broadcast.sent_count == 0 else Broadcast.Status.SENT
        broadcast.save(update_fields=["status", "sent_count", "failed_count", "error_log", "sent_at"])

        style = self.style.ERROR if broadcast.status == Broadcast.Status.FAILED else self.style.SUCCESS
        self.stdout.write(
            style(
                f"Broadcast {broadcast.id}: sent {broadcast.sent_count}, "
                f"failed {broadcast.failed_count} of {broadcast.total_recipients}"
            )
        )
