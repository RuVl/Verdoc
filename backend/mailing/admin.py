from django import forms
from django.contrib import admin, messages
from django.core.mail import get_connection
from django.db.models import QuerySet
from django.http import HttpResponseRedirect
from django.urls import reverse
from tinymce.widgets import TinyMCE

from customer.models import Customer

from .models import Broadcast
from .services import build_broadcast_email

# Shown at the top of the add/edit form so the sending flow is not a mystery.
HELP_HTML = (
    "<p><b>How sending works.</b> Creating a broadcast only saves a <b>draft</b> - it does not send. "
    "Flow:</p>"
    "<ol>"
    "<li>Fill in subject and body, save the draft.</li>"
    "<li>Select it in the list and run <b>Send test email</b> to preview it on <code>test_email</code>.</li>"
    "<li>Run <b>Queue / re-queue selected for sending</b>. A cron job sends the queue about every 15 minutes.</li>"
    "<li>One email per recipient goes to all paid buyers, minus the unsubscribe list. "
    "Watch <code>status</code> and <code>sent_count</code> / <code>failed_count</code>.</li>"
    "<li>If a broadcast ends up <b>FAILED</b>, fix the issue and run <b>Queue / re-queue</b> again.</li>"
    "</ol>"
)


class BroadcastAdminForm(forms.ModelForm):
    class Meta:
        model = Broadcast
        fields = "__all__"
        widgets = {"body": TinyMCE(attrs={"cols": 80, "rows": 20})}


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    form = BroadcastAdminForm
    list_display = (
        "id",
        "subject",
        "status",
        "total_recipients",
        "sent_count",
        "failed_count",
        "created_at",
        "sent_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("subject",)
    readonly_fields = (
        "status",
        "total_recipients",
        "sent_count",
        "failed_count",
        "error_log",
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
                    "total_recipients",
                    "sent_count",
                    "failed_count",
                    "error_log",
                    "created_at",
                    "sent_at",
                ),
            },
        ),
    )
    actions = ["send_test", "queue_for_sending"]

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
        # Unsaved stand-in: the test address is an arbitrary inbox, not necessarily a customer.
        recipient = Customer(email=broadcast.test_email)

        connection = get_connection()  # opened lazily on first send()
        try:
            build_broadcast_email(connection, broadcast, recipient, request).send()
            self.message_user(
                request, f"Broadcast {broadcast.id}: test sent to {broadcast.test_email}", messages.SUCCESS
            )
        except Exception as e:  # noqa: BLE001 - report the failure to the admin
            self.message_user(request, f"Broadcast {broadcast.id}: test failed: {e}", messages.ERROR)
        finally:
            connection.close()

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
