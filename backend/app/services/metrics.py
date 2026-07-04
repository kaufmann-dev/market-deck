"""Financial metrics computed over daily close series.

Faithful port of the legacy client-side math (static/app.js getScored /
getMonthlyReturns). Two deliberate quirks are preserved:

- Month arithmetic replicates JavaScript's Date rollover (May 31 - 1 month
  lands on May 1 via "April 31"), NOT calendar clamping.
- "USX" (US cents) is divided by 100 and then left in USD even when the base
  currency differs — known issue, kept for parity.

All functions take `today` explicitly so results are deterministic in tests.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from math import isnan

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

LOOKBACK_MONTHS = (1, 3, 6, 12)


@dataclass(frozen=True)
class Point:
    date: date
    close: float


def round2(value: float) -> float:
    """JS `+x.toFixed(2)` equivalent: half away from zero (Python round() is banker's)."""
    return float(Decimal(repr(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_points(series) -> list[Point]:
    """Convert a cached [{'date': iso, 'close': float}] series into Points."""
    if not isinstance(series, list):
        return []
    points = []
    for entry in series:
        close = entry.get("close")
        if close is None or (isinstance(close, float) and isnan(close)):
            continue
        points.append(Point(date.fromisoformat(entry["date"]), float(close)))
    return points


def has_enough_points(points: list[Point]) -> bool:
    return len(points) >= 2


def shift_months(today: date, months_back: int) -> date:
    """JS `new Date(y, m - n, d)`: month shift with day rollover, not clamping."""
    year_delta, month_index = divmod(today.month - 1 - months_back, 12)
    first_of_month = date(today.year + year_delta, month_index + 1, 1)
    return first_of_month + timedelta(days=today.day - 1)


def month_start_back(today: date, months_back: int) -> date:
    year_delta, month_index = divmod(today.month - 1 - months_back, 12)
    return date(today.year + year_delta, month_index + 1, 1)


def fx_symbol(currency: str, base_currency: str) -> str:
    prefix = "GBP" if currency == "GBp" else currency
    return f"{prefix}{base_currency}=X"


def required_fx_symbols(currencies: list[str], base_currency: str) -> list[str]:
    foreign = []
    for currency in currencies:
        if currency and currency != base_currency and currency != "USX" and currency not in foreign:
            foreign.append(currency)
    return [fx_symbol(currency, base_currency) for currency in foreign]


def convert_currency(
    points: list[Point], currency: str, base_currency: str, fx_points: list[Point] | None
) -> list[Point]:
    """Convert closes into the base currency using an as-of join on FX dates.

    Points dated before the first FX point use the first FX rate. A missing or
    empty FX series leaves the series unconverted (legacy behavior).
    """
    if not currency or currency == base_currency:
        return points
    if currency == "USX":
        return [Point(p.date, p.close / 100) for p in points]
    if not fx_points:
        return points

    fx_idx = 0
    converted = []
    for point in points:
        while fx_idx < len(fx_points) - 1 and fx_points[fx_idx + 1].date <= point.date:
            fx_idx += 1
        rate = fx_points[fx_idx].close
        if currency == "GBp":
            rate /= 100
        converted.append(Point(point.date, point.close * rate))
    return converted


def _closest_after(points: list[Point], target: date) -> Point:
    for point in points:
        if point.date >= target:
            return point
    return points[-1]


def lookback_return(points: list[Point], today: date, months_back: int) -> dict:
    """Return over the given lookback window, plus the base point used."""
    target = shift_months(today, months_back)
    base_point = _closest_after(points, target)
    current_point = points[-1]
    if base_point is current_point:
        return {"ret": None, "basePrice": None, "baseDate": None}
    return {
        "ret": round2((current_point.close / base_point.close - 1) * 100),
        "basePrice": base_point.close,
        "baseDate": base_point.date.isoformat(),
    }


def monthly_returns(points: list[Point], today: date) -> list[dict]:
    """12 calendar-month returns, oldest first. A month without data (or whose
    previous month has no data) yields ret=None."""
    months = []
    for months_back in range(12, 0, -1):
        start = month_start_back(today, months_back)
        label = f"{MONTH_LABELS[start.month - 1]} {str(start.year)[2:]}"
        next_start = month_start_back(today, months_back - 1)
        prev_start = month_start_back(today, months_back + 1)

        in_month = [p for p in points if start <= p.date < next_start]
        if not in_month:
            months.append({"label": label, "ret": None})
            continue
        in_prev = [p for p in points if prev_start <= p.date < start]
        if not in_prev:
            months.append({"label": label, "ret": None})
            continue
        months.append(
            {"label": label, "ret": round2((in_month[-1].close / in_prev[-1].close - 1) * 100)}
        )
    return months


def _empty_metrics() -> dict:
    return {
        "ok": False,
        "currentPrice": None,
        "lookbacks": {
            str(n): {"ret": None, "basePrice": None, "baseDate": None} for n in LOOKBACK_MONTHS
        },
        "ret12m": None,
        "monthly": [],
    }


def compute_ticker_metrics(
    series,
    currency: str,
    base_currency: str,
    fx_series,
    today: date,
) -> dict:
    """Full metrics payload for one ticker from raw cached series."""
    points = parse_points(series)
    if not has_enough_points(points):
        return _empty_metrics()

    fx_points = parse_points(fx_series) if fx_series else None
    converted = convert_currency(points, currency, base_currency, fx_points)

    lookbacks = {str(n): lookback_return(converted, today, n) for n in LOOKBACK_MONTHS}
    return {
        "ok": True,
        "currentPrice": converted[-1].close,
        "lookbacks": lookbacks,
        "ret12m": lookbacks["12"]["ret"],
        "monthly": monthly_returns(converted, today),
    }
