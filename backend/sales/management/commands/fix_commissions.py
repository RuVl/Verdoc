"""
Fill in the commission Plisio kept, for the old invoices whose callback never told us.

A one-off, meant to be deleted once it has been run: new invoices carry `invoice_commission` in the
callback, and nothing can recover the number for the old ones - Plisio's `operations` endpoint
answers with nine fields unless White Label is on, and it is not. So this computes the commission
from Plisio's published price list and writes it as if it were reported, which for those old sales
it effectively is: the tariff is what Plisio charged.

Two numbers of the invoice do the work: the amount in cryptocurrency and the same amount in fiat.
The percentage applies to the fiat one, because that is where the dollar minimums are written, and
the ratio between the two carries the result back into crypto - the unit `commission` is stored in.
Doing it as a ratio deliberately avoids `source_rate`, whose direction Plisio never documents.

Everything lives in this one file on purpose - deleting it leaves no trace behind.
"""

import logging
from collections import Counter
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.core.management.base import BaseCommand

from sales.models import Transaction

logger = logging.getLogger(__name__)

# The invoices somebody actually paid. The rest never cost a commission.
PAID_INVOICES = (Transaction.TransactionStatus.COMPLETED, Transaction.TransactionStatus.MISMATCH)

# https://plisio.net/faq/fee-information, the "API" column (White Label is not enabled on this
# account, and its 1.5% column does not apply). Read 2026-08-07.
API_PERCENT = Decimal("0.5")

# Transaction.commission has ten decimal places, and so does the number Plisio sends.
CRYPTO_PLACES = Decimal("0.0000000001")


@dataclass(frozen=True)
class Fee:
    """`percent` of the invoice, but never less than `minimum_usd`."""

    percent: Decimal
    minimum_usd: Decimal = Decimal("0")


# Keyed by Plisio's own currency code (psys_cid), which is what `Transaction.currency` holds.
# Coins that share a fee still get their own line: the table is meant to be checked against
# Plisio's page one row at a time, not deduplicated.
FEES = {
    # Own blockchain, flat 0.5%.
    "BTC": Fee(API_PERCENT),
    "ETH": Fee(API_PERCENT),
    "ETH_BASE": Fee(API_PERCENT),  # ETH Layer-2 Base
    "LTC": Fee(API_PERCENT),
    "DASH": Fee(API_PERCENT),
    "DOGE": Fee(API_PERCENT),
    "ZEC": Fee(API_PERCENT),
    "TZEC": Fee(API_PERCENT),  # Plisio's own code for Zcash
    "BCH": Fee(API_PERCENT),
    "XMR": Fee(API_PERCENT),
    "ETC": Fee(API_PERCENT),
    "TRX": Fee(API_PERCENT),
    "BNB": Fee(API_PERCENT),
    "SOL": Fee(API_PERCENT),
    # ERC-20: 0.5%, at least $0.5.
    "USDT": Fee(API_PERCENT, Decimal("0.5")),
    "USDT_ETH": Fee(API_PERCENT, Decimal("0.5")),
    "USDC": Fee(API_PERCENT, Decimal("0.5")),
    "TUSD": Fee(API_PERCENT, Decimal("0.5")),
    "SHIB": Fee(API_PERCENT, Decimal("0.5")),
    # TRC-20: 0.5%, at least $1.5.
    "USDT_TRX": Fee(API_PERCENT, Decimal("1.5")),
    "BTT": Fee(API_PERCENT, Decimal("1.5")),
    # BEP-20: 1%, no minimum.
    "USDT_BSC": Fee(Decimal("1")),
    "USDC_BSC": Fee(Decimal("1")),
    "BUSD": Fee(Decimal("1")),
    # TON: 5%, at least $1. Yes, ten times the rest - that is what the page says.
    "TON": Fee(Decimal("5"), Decimal("1")),
    "USDT_TON": Fee(Decimal("5"), Decimal("1")),
    # Solana SPL: 0.5%, at least $0.5.
    "USDT_SOL": Fee(API_PERCENT, Decimal("0.5")),
}

# Coins worth a dollar. On these the invoice's two amounts should be nearly the same number, so a
# gap between them means one of the two is not describing this invoice - see `suspicious()`.
STABLECOINS = {"USDT", "USDT_ETH", "USDT_TRX", "USDT_BSC", "USDT_TON", "USDT_SOL", "USDC", "USDC_BSC", "TUSD", "BUSD"}
PEG_TOLERANCE = Decimal("0.02")  # The peg itself never moves this far; rounding moves far less.


class Command(BaseCommand):
    help = "Fill the missing Plisio commissions from the published fee table"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only report what would be written.")
        parser.add_argument("--txn", action="append", default=[], help="Only this txn_id (repeatable).")
        parser.add_argument("--limit", type=int, default=None, help="Stop after N transactions.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: nothing is written"))

        # A commission Plisio reported is a fact, so only the empty column is ever filled.
        transactions = (
            Transaction.objects.select_related("order")
            .filter(status__in=PAID_INVOICES, commission__isnull=True)
            .order_by("pk")
        )
        if options["txn"]:
            transactions = transactions.filter(txn_id__in=options["txn"])
        if options["limit"]:
            transactions = transactions[: options["limit"]]

        written, skipped, unknown_currencies, doubted = 0, Counter(), Counter(), Counter()

        for txn in transactions:
            fee = FEES.get((txn.currency or "").strip().upper())
            if fee is None:
                # Guessing a fee for a code we cannot find on Plisio's page would be worse than
                # leaving the column empty, so these are named at the end instead.
                skipped["unknown currency"] += 1
                unknown_currencies[txn.currency] += 1
                continue

            amount_usd, from_order = self.invoice_usd(txn)
            if amount_usd is None or amount_usd <= 0 or not txn.amount or txn.amount <= 0:
                skipped["no amount to take a percentage of"] += 1
                self.stdout.write(self.style.ERROR(f"{txn.txn_id}: no usable amounts, skipped"))
                continue

            commission_usd = max(fee.minimum_usd, amount_usd * fee.percent / 100)
            commission = (txn.amount * commission_usd / amount_usd).quantize(CRYPTO_PLACES, rounding=ROUND_HALF_UP)

            binding = " (the minimum)" if amount_usd * fee.percent / 100 < fee.minimum_usd else ""
            doubts = self.doubts(txn, amount_usd, from_order)
            line = (
                f"{txn.txn_id} (order {txn.order_id}): ${amount_usd} in {txn.currency} at {fee.percent}%{binding}"
                f" -> {commission:f} {txn.currency}{''.join(f' [{label}{detail}]' for label, detail in doubts)}"
            )
            self.stdout.write(self.style.WARNING(line) if doubts else line)
            doubted.update(label for label, _ in doubts)

            if not dry_run:
                txn.commission = commission
                txn.save(update_fields=["commission", "updated_at"])
                logger.info(f"Transaction {txn.txn_id} got a commission of {commission} {txn.currency} from the tariff")

            written += 1

        self.report(written, skipped, unknown_currencies, doubted, dry_run)

    @staticmethod
    def invoice_usd(txn: Transaction) -> tuple[Decimal | None, bool]:
        """
        What the invoice was worth in fiat, and whether that number came from the order.

        The invoice's own `source_price` first - it is what Plisio billed - and the order's total
        as the fallback, which is what we asked Plisio to bill in the first place (`Order.
        total_price` is USD by construction). The fallback can disagree with the invoice, so the
        caller says so out loud rather than quietly averaging two different things.
        """

        if txn.source_price is not None and str(txn.source_price.currency) == "USD":
            return txn.source_price.amount, False

        if txn.order_id and txn.order.total_price is not None:
            return txn.order.total_price.amount, True

        return None, False

    @staticmethod
    def doubts(txn: Transaction, amount_usd: Decimal, from_order: bool) -> list[str]:
        """
        Why this row might be worth a second look before it is believed.

        Nothing here stops the write - the number is still the best we can compute - but the
        arithmetic carries a dollar minimum into crypto through the invoice's own two amounts, and
        that only holds while both describe the same invoice.
        """

        notes = []
        if from_order:
            notes.append(("the invoice carries no fiat amount, the order's is used", ""))

        currency = (txn.currency or "").strip().upper()
        if currency in STABLECOINS and abs(txn.amount - amount_usd) > amount_usd * PEG_TOLERANCE:
            notes.append((f"a {currency} invoice is off its dollar peg", f": {txn.amount:f} for ${amount_usd}"))

        return notes

    def report(self, written: int, skipped: Counter, unknown_currencies: Counter, doubted: Counter, dry_run: bool):
        verb = "would get" if dry_run else "got"
        self.stdout.write(self.style.SUCCESS(f"{written} invoice(s) {verb} a commission from the tariff"))

        for reason, count in skipped.most_common():
            self.stdout.write(self.style.ERROR(f"Skipped, {reason}: {count}"))

        for reason, count in doubted.most_common():
            self.stdout.write(self.style.WARNING(f"Written but worth a look, {reason}: {count}"))

        if unknown_currencies:
            listed = ", ".join(f"{code or '(empty)'} x{count}" for code, count in unknown_currencies.most_common())
            self.stdout.write(self.style.ERROR(f"Not on the price list we know: {listed}"))

        still_blind = Transaction.objects.filter(
            status=Transaction.TransactionStatus.COMPLETED, source_rate__isnull=True
        ).count()
        if still_blind:
            # money_totals() converts the commission through source_rate and drops the row without
            # one, so filling the commission alone does not necessarily show up on the dashboard.
            self.stdout.write(
                self.style.WARNING(f"{still_blind} completed invoice(s) still have no source_rate - see statistics.py")
            )
