from django.db import models


class Broadcast(models.Model):
    """
    An email broadcast to buyers.

    :param subject: Email subject.
    :param body: HTML email body (edited via a WYSIWYG editor in the admin).
    :param test_email: Optional address for a test run before sending to everyone.
    :param status: Broadcast lifecycle status.
    :param total_recipients: Number of recipients resolved at send time.
    :param sent_count: Successfully sent messages.
    :param failed_count: Failed messages.
    :param error_log: Per-address error summary.
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
    total_recipients = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    error_log = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Broadcast {self.id} - {self.subject} ({self.status})"


class Unsubscribe(models.Model):
    """Suppression list: buyers who opted out of broadcasts."""

    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email
