"""
Plisio, in the words our models use.

Callbacks are the only thing that ever writes a `Transaction`, so a webhook that was lost, refused
or answered while we were down leaves the database quietly wrong - and an order stuck PENDING is a
customer who paid and got nothing. This module is the read side of Plisio's REST API plus the one
place an invoice status turns into stock movement, shared by the callback view and the
`sync_transactions` command so the two cannot drift apart.
"""

import json
import logging
from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from typing import Any

import requests
from django.conf import settings
from django.db.transaction import atomic
from djmoney.money import Money

from sales.models import Allocation, Order, Transaction

logger = logging.getLogger(__name__)

API_ROOT = "https://api.plisio.net/api/v1"
DEFAULT_TIMEOUT = 30
PAGE_SIZE = 100

# Plisio invoice status -> our order status.
STATUS_MAP = {
    "new": Order.OrderStatus.PENDING,
    "pending": Order.OrderStatus.PENDING,
    "pending internal": Order.OrderStatus.PENDING,
    "completed": Order.OrderStatus.PAID,
    "expired": Order.OrderStatus.EXPIRED,
    "mismatch": Order.OrderStatus.OVERPAID,
    "error": Order.OrderStatus.ERROR,
    "cancelled": Order.OrderStatus.CANCELLED,
    "cancelled duplicate": Order.OrderStatus.PENDING,  # A customer has switched to another cryptocurrency
}

# What we are willing to take from Plisio and write onto a Transaction row.
COMPARED_FIELDS = (
    "status",
    "currency",
    "amount",
    "source_price",
    "source_rate",
    "commission",
    "pending_amount",
    "confirmations",
    "tx_urls",
)


class PlisioError(RuntimeError):
    """Plisio could not be reached, or answered something we cannot use."""


def api_keys() -> list[str]:
    """
    Both shops' secret keys, primary first.

    An invoice belongs to one of the two (the mirror domain bills through its own shop) and the row
    does not say which, so a lookup simply asks both.
    """

    keys = [settings.PLISIO_SECRET_KEY, settings.MIRROR_PLISIO_SECRET_KEY]
    return list(dict.fromkeys(key for key in keys if key))


def _get(path: str, params: dict, timeout: float) -> dict:
    """One GET against the API, unwrapped to its `data` object or raised as a PlisioError."""

    try:
        response = requests.get(f"{API_ROOT}/{path}", params=params, timeout=timeout)
        payload = response.json()
    except ValueError as e:
        # Includes requests' JSONDecodeError - the call went through, the body is not JSON.
        raise PlisioError(f"{path}: answer is not JSON ({e})") from e
    except requests.RequestException as e:
        raise PlisioError(f"{path}: Plisio is unreachable ({e})") from e

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if response.status_code != 200 or payload.get("status") != "success":
        raise PlisioError(f"{path}: HTTP {response.status_code}, {data.get('message') or payload}")

    return data


def fetch_operation(txn_id: str, api_key: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """One invoice by its Plisio id - the very same value the callback calls `txn_id`."""

    return _get(f"operations/{txn_id}", {"api_key": api_key}, timeout)


def fetch_operation_any_key(txn_id: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """The invoice, asking each shop in turn until one of them owns it."""

    errors = []
    for api_key in api_keys():
        try:
            return fetch_operation(txn_id, api_key, timeout)
        except PlisioError as e:
            errors.append(str(e))

    raise PlisioError(f"no shop knows invoice {txn_id}: {'; '.join(errors) or 'no API key is configured'}")


def iter_operations(
    api_key: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    max_pages: int | None = None,
    **filters,
) -> Iterator[dict]:
    """Walk one shop's operations newest first, page by page, until Plisio runs out or max_pages."""

    page = 1
    while True:
        params = {"api_key": api_key, "page": page, "limit": PAGE_SIZE, **filters}
        data = _get("operations", params, timeout)

        operations = data.get("operations") or []
        yield from operations

        page_count = (data.get("_meta") or {}).get("pageCount") or 0
        if not operations or page >= page_count or (max_pages is not None and page >= max_pages):
            return

        page += 1


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _urls(value: Any) -> list[str]:
    """
    Blockchain links as a set of strings.

    They reach us as a list from the API, as a JSON-encoded list from the callback and occasionally
    as one bare URL; sorting drops the ordering, which carries no meaning either.
    """

    if value in (None, ""):
        return []

    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return [value]

    if isinstance(value, dict):
        value = list(value.values())

    if not isinstance(value, list):
        return [str(value)]

    return sorted({str(url) for url in value if url})


def operation_to_fields(operation: dict) -> dict[str, Any]:
    """
    A Plisio operation in the words `Transaction` uses.

    Only what Plisio actually said: a key it left out stays None here, and `diff_transaction` skips
    it rather than erasing a value the callback once carried - the callback payload is the richer
    of the two, and repairing a row must not cost it data.
    """

    params = operation.get("params") if isinstance(operation.get("params"), dict) else {}

    def either(*names: str) -> Any:
        for name in names:
            for source in (operation, params):
                value = source.get(name)
                if value not in (None, ""):
                    return value
        return None

    source_currency = either("source_currency")
    source_amount = _decimal(either("source_amount"))

    return {
        "status": either("status"),
        "amount": _decimal(either("amount")),
        "currency": either("currency", "psys_cid"),
        "source_price": (
            Money(amount=source_amount, currency=source_currency)
            if source_amount is not None and source_currency
            else None
        ),
        "source_rate": _decimal(either("source_rate")),
        "commission": _decimal(either("commission", "invoice_commission")),
        "pending_amount": _decimal(either("pending_sum", "pending_amount")),
        "confirmations": _int(either("confirmations")),
        "tx_urls": _urls(either("tx_url", "tx_urls")) or None,
        # Not a Transaction field: the order this invoice claims to be for, checked but never rewritten.
        "order_number": _int(either("order_number")),
    }


def _comparable(field: str, value: Any) -> Any:
    """Both sides in one shape, so that 0.0005 equals 0.00050000 and link order means nothing."""

    if value is None:
        return None

    if field == "tx_urls":
        return _urls(value)

    if field == "source_price":
        return str(value.currency), _decimal(value.amount)

    if field in ("amount", "source_rate", "commission", "pending_amount"):
        return _decimal(value)

    if field == "confirmations":
        return _int(value)

    return str(value)


def diff_transaction(txn: Transaction, fields: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    """What Plisio says that the row does not, as {field: (ours, theirs)}."""

    changes = {}
    for field in COMPARED_FIELDS:
        remote = fields.get(field)
        if remote is None:
            continue

        current = getattr(txn, field)
        if _comparable(field, current) != _comparable(field, remote):
            changes[field] = (current, remote)

    return changes


def apply_changes(txn: Transaction, changes: dict[str, tuple[Any, Any]]) -> list[str]:
    """Write the differing fields back, and nothing else on the row."""

    if not changes:
        return []

    for field, (_, remote) in changes.items():
        setattr(txn, field, remote)

    update_fields = set(changes) | {"updated_at"}
    if "source_price" in changes:
        # A MoneyField is two columns, and assigning Money filled both of them.
        update_fields.add("source_price_currency")

    txn.save(update_fields=sorted(update_fields))
    logger.info(f"Transaction {txn.txn_id} corrected from Plisio: {sorted(changes)}")

    return sorted(changes)


@atomic
def apply_order_status(order: Order, plisio_status: str | None) -> tuple[bool, list[Allocation]]:
    """
    Move the order to what Plisio says about its invoice, handing over or releasing accordingly.

    Returns (this is the first payment, allocations delivered) - the caller decides about the
    e-mail, because only the first payment may send one.
    """

    order.status = STATUS_MAP.get(plisio_status, Order.OrderStatus.ERROR)
    order.save(update_fields=["status", "updated_at"])

    first_payment, allocations = False, []
    match order.status:
        case Order.OrderStatus.PAID | Order.OrderStatus.OVERPAID:
            first_payment = order.mark_paid()
            allocations = order.deliver()
        case Order.OrderStatus.EXPIRED | Order.OrderStatus.CANCELLED:
            order.release()

    return first_payment, allocations
