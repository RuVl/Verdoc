from io import StringIO
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core import mail, signing
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from customer.models import Customer
from mailing.models import Broadcast, BroadcastDelivery
from mailing.services import (
    UNSUBSCRIBE_SALT,
    build_broadcast_email,
    get_broadcast_recipients,
    make_unsubscribe_token,
)
from sales.models import Order


def make_buyer(email: str, **kwargs) -> Customer:
    customer = Customer.objects.create(email=email, **kwargs)
    Order.objects.create(customer=customer, total_price=10, paid_at=timezone.now())
    return customer


class RecipientTests(TestCase):
    """Who gets a broadcast is one query, shared with the admin's "bought something" filter."""

    def test_only_paying_customers_are_included(self):
        make_buyer("buyer@example.com")
        Customer.objects.create(email="lead@example.com")

        self.assertEqual(
            set(get_broadcast_recipients().values_list("email", flat=True)),
            {"buyer@example.com"},
        )

    def test_the_opted_out_are_left_alone(self):
        make_buyer("buyer@example.com")
        make_buyer("quiet@example.com", is_subscribed=False)

        self.assertEqual(
            set(get_broadcast_recipients().values_list("email", flat=True)),
            {"buyer@example.com"},
        )

    def test_a_buyer_appears_once_however_many_orders(self):
        customer = make_buyer("buyer@example.com")
        Order.objects.create(customer=customer, total_price=10, paid_at=timezone.now())

        self.assertEqual(get_broadcast_recipients().count(), 1)


class BroadcastEmailTests(TestCase):
    def setUp(self):
        Site.objects.update_or_create(pk=1, defaults={"domain": "testserver", "name": "test"})
        self.broadcast = Broadcast.objects.create(subject="News", body="<p>Hello</p>")
        self.customer = make_buyer("buyer@example.com", language="ru")

    def build(self):
        return build_broadcast_email(None, self.broadcast, self.customer)

    def test_the_footer_carries_a_working_unsubscribe_link(self):
        message = self.build()
        token = make_unsubscribe_token(self.customer.email)

        self.assertIn(f"/unsubscribe/{token}", message.body)
        self.assertIn(f"/unsubscribe/{token}", message.alternatives[0].content)

    def test_the_unsubscribe_link_carries_the_customers_language(self):
        self.assertIn("lang=ru", self.build().body)

    def test_the_list_unsubscribe_header_is_set(self):
        message = self.build()

        self.assertIn("/unsubscribe/", message.extra_headers["List-Unsubscribe"])

    def test_the_plain_part_is_stripped_html(self):
        message = self.build()

        self.assertIn("Hello", message.body)
        self.assertNotIn("<p>", message.body)

    def test_the_footer_is_in_the_customers_language(self):
        self.assertIn("Отписаться от рассылки", self.build().body)

    def test_a_customer_gets_the_translation_of_their_language(self):
        self.broadcast.subject_ru = "Новости"
        self.broadcast.body_ru = "<p>Привет</p>"
        self.broadcast.save()

        message = self.build()

        self.assertEqual(message.subject, "Новости")
        self.assertIn("Привет", message.body)

    def test_an_untranslated_broadcast_falls_back_to_the_site_default(self):
        """A language the author left empty must still reach its readers, in the other language."""
        message = self.build()

        self.assertEqual(message.subject, "News")
        self.assertIn("Hello", message.body)


class BroadcastCommandTests(TestCase):
    """The ledger is what makes the sender resumable - these are the invariants it buys."""

    def setUp(self):
        Site.objects.update_or_create(pk=1, defaults={"domain": "testserver", "name": "test"})
        self.broadcast = Broadcast.objects.create(
            subject="News", body="<p>Hello</p>", status=Broadcast.Status.QUEUED, test_email="tester@example.com"
        )
        self.first = make_buyer("one@example.com")
        self.second = make_buyer("two@example.com")

    def run_broadcast(self, **options):
        call_command("broadcast", stdout=StringIO(), **options)
        self.broadcast.refresh_from_db()

    def test_every_recipient_gets_one_message(self):
        self.run_broadcast()

        self.assertEqual(
            {address for message in mail.outbox for address in message.to},
            {"one@example.com", "two@example.com"},
        )
        self.assertEqual(self.broadcast.status, Broadcast.Status.SENT)
        self.assertEqual(self.broadcast.deliveries.filter(state=BroadcastDelivery.State.SENT).count(), 2)

    def test_a_second_run_does_not_send_again(self):
        self.run_broadcast()
        mail.outbox.clear()

        self.run_broadcast(id=self.broadcast.id)

        self.assertEqual(mail.outbox, [])

    def test_an_interrupted_run_resumes_where_it_stopped(self):
        # First recipient goes out, then the world ends.
        with (
            patch("mailing.management.commands.broadcast.build_broadcast_email") as build,
            self.assertLogs("mailing.management.commands.broadcast", level="ERROR"),
        ):
            build.side_effect = [Mock(), RuntimeError("smtp died")]
            self.run_broadcast()

        self.assertEqual(self.broadcast.deliveries.outstanding().count(), 1)
        self.assertEqual(self.broadcast.status, Broadcast.Status.FAILED)

        mail.outbox.clear()
        self.run_broadcast(id=self.broadcast.id)

        # Only the one that failed is retried, and the broadcast closes clean.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.broadcast.status, Broadcast.Status.SENT)

    def test_a_failure_is_recorded_against_the_recipient(self):
        with patch("mailing.management.commands.broadcast.build_broadcast_email") as build:
            build.side_effect = RuntimeError("mailbox full")
            with self.assertLogs("mailing.management.commands.broadcast", level="ERROR"):
                self.run_broadcast()

        delivery = self.broadcast.deliveries.first()
        self.assertEqual(delivery.state, BroadcastDelivery.State.FAILED)
        self.assertIn("mailbox full", delivery.error)

    def test_someone_who_opted_out_after_the_plan_is_still_skipped_next_time(self):
        self.first.unsubscribe()

        self.run_broadcast()

        self.assertEqual([message.to for message in mail.outbox], [["two@example.com"]])
        self.assertEqual(self.broadcast.deliveries.count(), 1)

    def test_a_test_run_writes_no_ledger_rows(self):
        self.run_broadcast(test=True)

        self.assertEqual({address for message in mail.outbox for address in message.to}, {"tester@example.com"})
        self.assertEqual(BroadcastDelivery.objects.count(), 0)

    def test_a_test_run_sends_one_message_per_language(self):
        self.broadcast.subject_ru = "Новости"
        self.broadcast.save()

        self.run_broadcast(test=True)

        self.assertEqual({message.subject for message in mail.outbox}, {"News", "Новости"})

    def test_each_customer_is_written_to_in_their_own_language(self):
        self.broadcast.subject_ru = "Новости"
        self.broadcast.save()
        self.first.set_language("ru")

        self.run_broadcast()

        by_address = {message.to[0]: message.subject for message in mail.outbox}
        self.assertEqual(by_address, {"one@example.com": "Новости", "two@example.com": "News"})

    def test_a_dry_run_sends_nothing_and_plans_nothing(self):
        self.run_broadcast(dry_run=True)

        self.assertEqual(mail.outbox, [])
        self.assertEqual(BroadcastDelivery.objects.count(), 0)
        self.assertEqual(self.broadcast.status, Broadcast.Status.QUEUED)

    def test_only_queued_broadcasts_are_picked_up(self):
        Broadcast.objects.create(subject="Draft", body="<p>x</p>")

        self.run_broadcast()

        self.assertEqual(len(mail.outbox), 2)


class BroadcastAdminTests(TestCase):
    """The counters are annotations now, so the list page is what proves they still add up."""

    def setUp(self):
        Site.objects.update_or_create(pk=1, defaults={"domain": "testserver", "name": "test"})
        self.broadcast = Broadcast.objects.create(subject="News", body="<p>Hello</p>", status=Broadcast.Status.QUEUED)
        make_buyer("one@example.com")
        make_buyer("two@example.com")

        admin_user = User.objects.create_superuser("admin", "admin@example.com", "pw")
        self.client.force_login(admin_user)

    def test_every_language_gets_its_own_editor(self):
        """TranslationAdmin copies the form's widget onto each language field - proof it still does."""
        response = self.client.get(reverse("admin:mailing_broadcast_add"))
        page = response.content.decode()

        self.assertContains(response, 'name="body_en"')
        self.assertContains(response, 'name="body_ru"')
        # The editor is what `data-mce-conf` marks; the class attribute also carries
        # modeltranslation's own classes, so it is not the thing to match on.
        self.assertEqual(page.count("data-mce-conf"), 2)
        self.assertIn("tinymce.min.js", page)

    def test_the_counts_follow_the_delivery_rows(self):
        with patch("mailing.management.commands.broadcast.build_broadcast_email") as build:
            build.side_effect = [Mock(), RuntimeError("smtp died")]
            with self.assertLogs("mailing.management.commands.broadcast", level="ERROR"):
                call_command("broadcast", stdout=StringIO())

        response = self.client.get(reverse("admin:mailing_broadcast_changelist"))
        row = response.context["cl"].result_list[0]

        self.assertEqual(row.recipients_count, 2)
        self.assertEqual(row.sent_count, 1)
        self.assertEqual(row.failed_count, 1)


class UnsubscribeViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = make_buyer("buyer@example.com")

    def url(self, token: str) -> str:
        return reverse("unsubscribe", args=[token])

    def test_a_valid_token_opts_the_customer_out(self):
        response = self.client.post(self.url(make_unsubscribe_token(self.customer.email)))

        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_subscribed)

    def test_opting_out_twice_is_a_no_op(self):
        token = self.url(make_unsubscribe_token(self.customer.email))
        self.client.post(token)
        self.customer.refresh_from_db()
        first_time = self.customer.unsubscribed_at

        response = self.client.post(token)

        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.unsubscribed_at, first_time)

    def test_a_tampered_token_is_refused(self):
        response = self.client.post(self.url("not-a-real-token"))

        self.assertEqual(response.status_code, 400)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_subscribed)

    def test_a_token_for_a_deleted_customer_still_answers_ok(self):
        token = signing.dumps("gone@example.com", salt=UNSUBSCRIBE_SALT)

        with self.assertLogs("mailing.views", level="INFO"):
            response = self.client.post(self.url(token))

        self.assertEqual(response.status_code, 200)

    def test_get_only_reads_the_token(self):
        """Opening the link - by hand or by a mail scanner pre-fetching it - must change nothing."""
        response = self.client.get(self.url(make_unsubscribe_token(self.customer.email)))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"email": "buyer@example.com", "is_subscribed": True})
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_subscribed)

    def test_get_reports_someone_already_opted_out(self):
        self.customer.unsubscribe()

        response = self.client.get(self.url(make_unsubscribe_token(self.customer.email)))

        self.assertFalse(response.data["is_subscribed"])

    def test_get_refuses_a_tampered_token(self):
        response = self.client.get(self.url("not-a-real-token"))

        self.assertEqual(response.status_code, 400)

    def test_get_for_a_deleted_customer_reads_as_already_done(self):
        token = signing.dumps("gone@example.com", salt=UNSUBSCRIBE_SALT)

        response = self.client.get(self.url(token))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"email": "gone@example.com", "is_subscribed": False})

    def test_an_unsubscribed_buyer_is_dropped_from_the_next_run(self):
        self.client.post(self.url(make_unsubscribe_token(self.customer.email)))

        self.assertEqual(get_broadcast_recipients().count(), 0)
        self.assertEqual(len(mail.outbox), 0)
