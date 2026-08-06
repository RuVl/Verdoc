"""
The statistics page and its CSV twin.

Both are wired into `VerdocAdminSite.get_urls` and wrapped in `admin_view()`, which is where the
login check, `never_cache` and CSRF protection come from - there is no permission handling here.
"""

import csv
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from django.contrib import admin
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.dateparse import parse_date

from sales import statistics
from sales.statistics import Period

# Presets offered above the page, as (value, label). "all" spans everything ever recorded.
PRESETS = [("7", "7 days"), ("30", "30 days"), ("90", "90 days"), ("365", "Year"), ("all", "All time")]
DEFAULT_PRESET = "30"

# Far enough back to predate any order; used as the start of the "all time" range.
EPOCH = datetime(2020, 1, 1, tzinfo=UTC)


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
    start_at = EPOCH if preset == "all" else end_at - timedelta(days=int(preset))

    return Period(start=start_at, end=end_at, preset=preset)


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
        "customers": statistics.repeat_customers(period),
        "downloads": statistics.download_rate(period),
        "sales_rate_days": statistics.SALES_RATE_DAYS,
    }


def statistics_view(request):
    period = parse_period(request)
    context = _collect(period)

    context["chart"] = {
        "labels": [row["day"].isoformat() for row in context["revenue"]],
        "values": [float(row["revenue"]) for row in context["revenue"]],
    }
    context["has_sales"] = context["totals"].orders > 0
    context["query"] = request.GET.urlencode()

    return TemplateResponse(request, "admin/sales/statistics.html", {**admin.site.each_context(request), **context})


def statistics_csv_view(request):
    """The same period, as two blocks in one file: revenue by day, then sales by product."""

    period = parse_period(request)
    data = _collect(period)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="verdoc-stats-{period.start.date()}-{period.last_day}.csv"'
    # Excel reads a BOM-less UTF-8 file as the local codepage and mangles every non-ASCII name.
    response.write("﻿")

    writer = csv.writer(response)
    writer.writerow(["Revenue by day (UTC)"])
    writer.writerow(["date", "gross_usd"])
    for row in data["revenue"]:
        writer.writerow([row["day"].isoformat(), _money(row["revenue"])])

    writer.writerow([])
    writer.writerow(["Sales by product"])
    writer.writerow(["product", "units", "gross_usd"])
    for row in data["top_products"]:
        writer.writerow([row["product_name"], row["units"], _money(row["revenue"])])

    writer.writerow([])
    writer.writerow(["gross_usd", "plisio_commission_usd", "net_usd", "paid_orders"])
    totals = data["totals"]
    writer.writerow([_money(totals.gross), _money(totals.commission), _money(totals.net), totals.orders])

    return response


def _money(value: Decimal) -> str:
    return f"{value:.2f}"
