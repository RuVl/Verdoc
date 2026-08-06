from django.db import models
from django.db.transaction import atomic
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Broadcast(models.Model):
    """
    An email broadcast to buyers.

    How far it got is not stored here: it is derived from the BroadcastDelivery rows, one per
    recipient, so a run that dies half way can be resumed instead of restarted.

    :param subject: Email subject.
    :param body: HTML email body (edited via a WYSIWYG editor in the admin).
    :param test_email: Optional address for a test run before sending to everyone.
    :param status: Broadcast lifecycle status.
    :param created_at: Creation time.
    :param sent_at: Time the broadcast finished sending.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        QUEUED = "QUEUED", "Queued"
        SENDING = "SENDING", "Sending"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"

    subject = models.CharField(max_length=255)
    body = models.TextField(help_text="HTML email body")
    test_email = models.EmailField(blank=True, help_text="Address for the 'Send test email' action")

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Broadcast")
        verbose_name_plural = _("Broadcasts")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Broadcast {self.id} - {self.subject} ({self.status})"

    @atomic
    def plan(self, recipients) -> int:
        """
        Write a PENDING delivery per recipient and return how many are still owed a message.

        Idempotent: `ignore_conflicts` leans on the unique constraint, so calling it again after
        a crash adds only the people who were not on the list yet and re-counts the rest.
        """

        BroadcastDelivery.objects.bulk_create(
            [BroadcastDelivery(broadcast=self, customer=customer) for customer in recipients],
            ignore_conflicts=True,
        )

        return self.deliveries.outstanding().count()

    def finish(self):
        """Close the run: FAILED only if nothing at all got through, SENT once nothing is owed."""
        outstanding = self.deliveries.outstanding().count()
        sent = self.deliveries.filter(state=BroadcastDelivery.State.SENT).count()

        self.status = self.Status.SENT if not outstanding and sent else self.Status.FAILED
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at"])


class BroadcastDeliveryQuerySet(models.QuerySet):
    def outstanding(self):
        """Everything the sender still owes: never tried, or tried and failed."""
        return self.filter(state__in=(BroadcastDelivery.State.PENDING, BroadcastDelivery.State.FAILED))


class BroadcastDelivery(models.Model):
    """
    One broadcast's fate for one customer.

    This row is what makes the sender resumable: the unique constraint means a repeated run
    cannot mail anyone twice, and re-queueing a broadcast retries only what failed. It also
    answers "did this customer get broadcast X", which counters never could.

    :param state: PENDING until a message goes out, then SENT or FAILED.
    :param error: The exception text of the last failed attempt.
    :param sent_at: When this particular message went out.
    """

    class State(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        SENT = "SENT", _("Sent")
        FAILED = "FAILED", _("Failed")

    broadcast = models.ForeignKey(Broadcast, related_name="deliveries", on_delete=models.CASCADE)
    customer = models.ForeignKey("customer.Customer", related_name="broadcast_deliveries", on_delete=models.CASCADE)

    state = models.CharField(max_length=10, choices=State.choices, default=State.PENDING)
    error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    objects = BroadcastDeliveryQuerySet.as_manager()

    class Meta:
        verbose_name = _("Broadcast delivery")
        verbose_name_plural = _("Broadcast deliveries")
        ordering = ["broadcast", "customer"]
        constraints = [
            models.UniqueConstraint(fields=["broadcast", "customer"], name="one_delivery_per_broadcast_customer"),
        ]

    def __str__(self):
        return f"{self.customer_id} <- broadcast {self.broadcast_id} ({self.state})"

    def mark_sent(self):
        self.state = self.State.SENT
        self.error = ""
        self.sent_at = timezone.now()
        self.save(update_fields=["state", "error", "sent_at"])

    def mark_failed(self, error: str):
        self.state = self.State.FAILED
        self.error = error
        self.save(update_fields=["state", "error"])
