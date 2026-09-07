"""
The statistics page and its CSV twin.

Both are wired into `VerdocAdminSite.get_urls` and wrapped in `admin_view()`, which is where the
login check, `never_cache` and CSRF protection come from - there is no permission handling here.
"""

import csv
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from django.contrib import admin
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import urlencode

from sales import statistics
from sales.statistics import Period

# Presets offered above the page, as (value, label). "all" starts at the first sale.
PRESETS = [("7", "7 days"), ("30", "30 days"), ("90", "90 days"), ("365", "Year"), ("all", "All time")]
DEFAULT_PRESET = "30"

# Rows of the stock forecast per page; the page is picked with `?stock_page=`.
STOCK_PER_PAGE = 20


def parse_period(request) -> Period:
    """
    Read the period off the querystring: `?from=&to=` wins, otherwise `?preset=`.

    Anything unparseable falls back to the default silently. This is a dashboard, not a form -
    a typo in a bookmarked URL should show the last 30 days, not an error page.
    """

    start = parse_date(request.GET.get("from", "") or "")
    end = parse_date(request.GET.get("to", "") or "")
    if start and end and start <= end:
        return Period(start=_as_utc(start), end=_as_utc(end) + timedelta(days=1), preset="custom")

    preset = request.GET.get("preset", DEFAULT_PRESET)
    if preset not in dict(PRESETS):
        preset = DEFAULT_PRESET

    # The end is tomorrow midnight, so everything paid today is inside the half-open range.
    end_at = _as_utc(timezone.now().date()) + timedelta(days=1)
    start_at = _all_time_start(end_at) if preset == "all" else end_at - timedelta(days=int(preset))

    return Period(start=start_at, end=end_at, preset=preset)


def _all_time_start(end_at: datetime) -> datetime:
    """The day of the first sale. A shop that has never sold anything gets the default window."""

    first = statistics.first_sale_at()
    if first is None:
        return end_at - timedelta(days=int(DEFAULT_PRESET))

    return _as_utc(first.astimezone(UTC).date())


def _as_utc(day) -> datetime:
    """Midnight of that day, UTC - the project runs on UTC and the page says so."""

    return datetime.combine(day, time.min, tzinfo=UTC)


def _collect(period: Period) -> dict:
    now = timezone.now()
    return {
        "period": period,
        "presets": PRESETS,
        "totals": statistics.money_totals(period),
        "revenue": statistics.revenue_by_day(period),
        "top_products": statistics.top_products(period),
        "top_countries": statistics.top_countries(period),
        "stock": statistics.stock_forecast(now),
        "stock_age": statistics.stock_age(now),
        "funnel": statistics.funnel(period),
        "time_to_pay": statistics.time_to_pay(period),
        "stages": statistics.payment_stages(period),
        "customers": statistics.repeat_customers(period),
        "downloads": statistics.download_rate(period),
        "sales_rate_days": statistics.SALES_RATE_DAYS,
    }


def statistics_view(request):
    period = parse_period(request)
    context = _collect(period)

    trend = statistics.moving_average(context["revenue"])
    context["chart"] = {
        "labels": [row["day"].isoformat() for row in context["revenue"]],
        "values": [float(row["revenue"]) for row in context["revenue"]],
        # None keeps the first days of the window out of the line instead of flattening it.
        "trend": [float(value) if value is not None else None for value in trend],
        "links": [_orders_of(row["day"]) for row in context["revenue"]],
    }
    context["trend_window"] = statistics.TREND_WINDOW
    context["has_sales"] = context["totals"].orders > 0
    context["query"] = request.GET.urlencode()

    # The forecast is sorted by urgency, so page one is the part that needs acting on - but a
    # catalogue of a thousand products has to be walkable, not truncated.
    context.update(_paginate_stock(request, context["stock"]))

    return TemplateResponse(request, "admin/sales/statistics.html", {**admin.site.each_context(request), **context})


def _paginate_stock(request, rows: list[dict]) -> dict:
    """
    One page of the stock forecast, plus the links to walk it.

    `get_page` swallows a missing, non-numeric or out-of-range page the way the rest of the
    querystring is handled here: a bookmarked URL shows a page, never an error.
    """

    paginator = Paginator(rows, STOCK_PER_PAGE)
    page = paginator.get_page(request.GET.get("stock_page"))

    # The same elided range the admin's own changelist paginator is built from, so the markup
    # below it can reuse the admin's .paginator styles and behave the way a changelist does.
    numbers = [
        {"number": number, "url": "" if number == paginator.ELLIPSIS else _with_param(request, stock_page=number)}
        for number in paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1)
    ]

    return {"stock_page": page, "stock_page_numbers": numbers, "stock_ellipsis": paginator.ELLIPSIS}


def _orders_of(day: date) -> str:
    """
    The order changelist, filtered down to what was paid on that day.

    The changelist only accepts these two lookups because `paid_at` is in `OrderAdmin.list_filter`.
    Aware datetimes, in the same shape Django's own date filter builds - a bare date arrives naive
    and every click would warn about it.
    """

    start = _as_utc(day)
    query = urlencode({"paid_at__gte": start, "paid_at__lt": start + timedelta(days=1)})

    return f"{reverse('admin:sales_order_changelist')}?{query}"


def _with_param(request, **params) -> str:
    """The current querystring with a parameter added, so a link keeps the period it was clicked on."""

    query = request.GET.copy()
    for name, value in params.items():
        # Assignment, not update(): a QueryDict's update appends to the existing values.
        query[name] = value

    return f"?{query.urlencode()}"


def statistics_csv_view(request):
    """
    The same period as the page, in four blocks.

    The page shows the top ten and one page of stock because a screen has to be readable; the
    export is where the whole catalogue goes, because that is what a spreadsheet is for.
    """

    period = parse_period(request)
    revenue = statistics.revenue_by_day(period)
    trend = statistics.moving_average(revenue)
    totals = statistics.money_totals(period)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="verdoc-stats-{period.start.date()}-{period.last_day}.csv"'
    # Excel reads a BOM-less UTF-8 file as the local codepage and mangles every non-ASCII name.
    response.write("﻿")

    writer = csv.writer(response)
    writer.writerow(["Revenue by day (UTC)"])
    writer.writerow(["date", "gross_usd", f"average_{statistics.TREND_WINDOW}d_usd"])
    for row, average in zip(revenue, trend, strict=True):
        # An empty cell means "no window yet", so a genuine zero has to print as 0.00 - the column
        # beside it does the same, and the two must not disagree about a dead week.
        trend_cell = _money(average) if average is not None else ""
        writer.writerow([row["day"].isoformat(), _money(row["revenue"]), trend_cell])

    writer.writerow([])
    writer.writerow(["Sales by product - every product sold in the period"])
    writer.writerow(["product", "units", "gross_usd"])
    for row in statistics.top_products(period, limit=None):
        writer.writerow([row["product_name"], row["units"], _money(row["revenue"])])

    writer.writerow([])
    writer.writerow([f"Stock right now - every product, at the last {statistics.SALES_RATE_DAYS} days of sales"])
    writer.writerow(["product", "country", "available", f"sold_{statistics.SALES_RATE_DAYS}d", "days_left"])
    for row in statistics.stock_forecast(timezone.now()):
        # An empty cell, not a zero: nothing selling means no runway to report, and a 0 there
        # would read as "out tomorrow" - the opposite.
        days_left = f"{row['days_left']:.0f}" if row["days_left"] is not None else ""
        writer.writerow([row["product"], row["country"], row["available"], row["sold"], days_left])

    writer.writerow([])
    writer.writerow(["gross_usd", "plisio_commission_usd", "net_usd", "paid_orders"])
    writer.writerow([_money(totals.gross), _money(totals.commission), _money(totals.net), totals.orders])

    return response


def _money(value: Decimal) -> str:
    return f"{value:.2f}"
