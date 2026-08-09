from django import forms
from django.contrib import admin, messages
from django.db.models import Count, Q, QuerySet
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html_join
from modeltranslation.admin import TranslationAdmin
from tinymce.widgets import TinyMCE

from .models import Broadcast, BroadcastDelivery
from .services import send_broadcast_test

# The whole error log used to live on the Broadcast row; now it is one row per failed recipient,
# so the form shows a readable head of it instead of everything.
FAILURES_SHOWN = 20

# Shown at the top of the add/edit form so the sending flow is not a mystery.
HELP_HTML = (
    "<p><b>How sending works.</b> Creating a broadcast only saves a <b>draft</b> - it does not send. "
    "Flow:</p>"
    "<ol>"
    "<li>Fill in subject and body <b>for every language</b>, save the draft. A language you leave "
    "empty falls back to the site default, so those customers get the wrong one silently.</li>"
    "<li>Select it in the list and run <b>Send test email</b> - one message per language lands "
    "on <code>test_email</code>.</li>"
    "<li>Run <b>Queue / re-queue selected for sending</b>. A cron job sends the queue about every 15 minutes.</li>"
    "<li>One email per recipient goes to every paid buyer who has not opted out. "
    "Watch <code>status</code> and the sent / failed counts.</li>"
    "<li>If a broadcast ends up <b>FAILED</b>, fix the issue and run <b>Queue / re-queue</b> again - "
    "the sender only retries the recipients it did not reach.</li>"
    "</ol>"
)


class BroadcastAdminForm(forms.ModelForm):
    class Meta:
        model = Broadcast
        fields = "__all__"
        # Keyed by the untranslated name on purpose: TranslationAdmin copies this widget onto
        # every language field, so each of body_en / body_ru gets its own editor.
        widgets = {"body": TinyMCE(attrs={"cols": 80, "rows": 20})}


@admin.register(Broadcast)
class BroadcastAdmin(TranslationAdmin):
    form = BroadcastAdminForm
    list_display = (
        "id",
        "subject",
        "status",
        "recipients_count",
        "sent_count",
        "failed_count",
        "created_at",
        "sent_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("subject_en", "subject_ru")
    readonly_fields = (
        "status",
        "recipients_count",
        "sent_count",
        "failed_count",
        "failures",
        "created_at",
        "sent_at",
    )
    fieldsets = (
        (None, {"description": HELP_HTML, "fields": ("subject", "body", "test_email")}),
        (
            "Status",
            {
                "classes": ("collapse",),
                "fields": (
                    "status",
                    "recipients_count",
                    "sent_count",
                    "failed_count",
                    "failures",
                    "created_at",
                    "sent_at",
                ),
            },
        ),
    )
    actions = ["send_test", "queue_for_sending"]

    def get_queryset(self, request):
        # The counters are derived from the delivery rows - there is nothing to keep in sync.
        return (
            super()
            .get_queryset(request)
            .annotate(
                recipients_count=Count("deliveries", distinct=True),
                sent_count=Count("deliveries", filter=Q(deliveries__state=BroadcastDelivery.State.SENT), distinct=True),
                failed_count=Count(
                    "deliveries", filter=Q(deliveries__state=BroadcastDelivery.State.FAILED), distinct=True
                ),
            )
        )

    @admin.display(description="Recipients", ordering="recipients_count")
    def recipients_count(self, obj):
        return obj.recipients_count

    @admin.display(description="Sent", ordering="sent_count")
    def sent_count(self, obj):
        return obj.sent_count

    @admin.display(description="Failed", ordering="failed_count")
    def failed_count(self, obj):
        return obj.failed_count

    @admin.display(description="Failures")
    def failures(self, obj):
        rows = obj.deliveries.filter(state=BroadcastDelivery.State.FAILED).select_related("customer")[:FAILURES_SHOWN]
        if not rows:
            return "-"

        return format_html_join("\n", "<div>{}: {}</div>", ((row.customer.email, row.error) for row in rows))

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        # Creating/editing a broadcast is never a "send" - drop the confusing extra save buttons.
        extra_context = extra_context or {}
        extra_context["show_save_and_add_another"] = False
        extra_context["show_save_and_continue"] = False
        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            func, name, _ = actions["delete_selected"]
            actions["delete_selected"] = (func, name, "Delete broadcasts")
        return actions

    # --- Shared send/queue logic (used by both bulk actions and the form buttons) ---

    def _send_test_one(self, request, broadcast: Broadcast):
        if not broadcast.test_email:
            self.message_user(request, f"Broadcast {broadcast.id}: no test_email set", messages.WARNING)
            return

        try:
            send_broadcast_test(broadcast, request)
        except Exception as e:  # noqa: BLE001 - report the failure to the admin
            self.message_user(request, f"Broadcast {broadcast.id}: test failed: {e}", messages.ERROR)
            return

        self.message_user(request, f"Broadcast {broadcast.id}: test sent to {broadcast.test_email}", messages.SUCCESS)

    def _queue_one(self, request, broadcast: Broadcast):
        if broadcast.status in (Broadcast.Status.DRAFT, Broadcast.Status.FAILED):
            broadcast.status = Broadcast.Status.QUEUED
            broadcast.save(update_fields=["status"])
            self.message_user(
                request, f"Broadcast {broadcast.id}: queued. Cron will send it (~15 min).", messages.SUCCESS
            )
        else:
            self.message_user(
                request, f"Broadcast {broadcast.id}: not queued (status {broadcast.status}).", messages.WARNING
            )

    # --- Form submit buttons (Send test email / Queue for sending) ---

    def _handle_form_buttons(self, request, obj):
        """Return a redirect response if a send/queue button was pressed, else None."""
        if "_send_test" in request.POST:
            self._send_test_one(request, obj)
        elif "_queue" in request.POST:
            self._queue_one(request, obj)
        else:
            return None
        url = reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk])
        return HttpResponseRedirect(url)

    def response_add(self, request, obj, post_url_continue=None):
        return self._handle_form_buttons(request, obj) or super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        return self._handle_form_buttons(request, obj) or super().response_change(request, obj)

    @admin.action(description="Send test email to test_email")
    def send_test(self, request, queryset: QuerySet[Broadcast]):
        for broadcast in queryset:
            self._send_test_one(request, broadcast)

    @admin.action(description="Queue / re-queue selected for sending")
    def queue_for_sending(self, request, queryset: QuerySet[Broadcast]):
        for broadcast in queryset:
            self._queue_one(request, broadcast)


@admin.register(BroadcastDelivery)
class BroadcastDeliveryAdmin(admin.ModelAdmin):
    """
    Read-only: this is the sender's ledger, written by the `broadcast` command.

    Editing a row by hand would either resend a message or hide one that never went out.
    """

    list_display = ("broadcast", "customer", "state", "sent_at")
    list_filter = ("state", "broadcast")
    search_fields = ("customer__email",)
    list_select_related = ("broadcast", "customer")
    readonly_fields = ("broadcast", "customer", "state", "error", "created_at", "sent_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
