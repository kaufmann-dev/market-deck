"""Golden tests for the financial math port (hand-computed expectations)."""
from datetime import date

from app.services.metrics import (
    Point,
    compute_ticker_metrics,
    convert_currency,
    lookback_return,
    month_start_back,
    monthly_returns,
    required_fx_symbols,
    round2,
    shift_months,
)

TODAY = date(2026, 7, 4)


def pts(*pairs):
    return [Point(date.fromisoformat(d), c) for d, c in pairs]


def series(*pairs):
    return [{"date": d, "close": c} for d, c in pairs]


class TestRound2:
    def test_half_away_from_zero(self):
        assert round2(3.126) == 3.13
        assert round2(3.124) == 3.12
        assert round2(-3.126) == -3.13
        assert round2(10.0) == 10.0


class TestShiftMonths:
    def test_js_rollover_not_clamping(self):
        # JS: new Date(2026, 4 - 1, 31) -> "April 31" -> May 1
        assert shift_months(date(2026, 5, 31), 1) == date(2026, 5, 1)
        # JS: "February 31" 2026 (28 days) -> March 3
        assert shift_months(date(2026, 5, 31), 3) == date(2026, 3, 3)

    def test_plain_shift(self):
        assert shift_months(TODAY, 1) == date(2026, 6, 4)
        assert shift_months(TODAY, 12) == date(2025, 7, 4)

    def test_year_wrap(self):
        assert shift_months(date(2026, 1, 15), 2) == date(2025, 11, 15)

    def test_month_start_back(self):
        assert month_start_back(TODAY, 1) == date(2026, 6, 1)
        assert month_start_back(TODAY, 12) == date(2025, 7, 1)


class TestLookbackReturn:
    SERIES = pts(
        ("2025-06-20", 100.0),
        ("2026-06-01", 100.0),
        ("2026-06-10", 110.0),
        ("2026-07-03", 121.0),
    )

    def test_one_month(self):
        result = lookback_return(self.SERIES, TODAY, 1)
        # target 2026-06-04 -> first point on/after is 2026-06-10 @ 110
        assert result == {"ret": 10.0, "basePrice": 110.0, "baseDate": "2026-06-10"}

    def test_twelve_months(self):
        result = lookback_return(self.SERIES, TODAY, 12)
        # target 2025-07-04 -> first point on/after is 2026-06-01 @ 100
        assert result == {"ret": 21.0, "basePrice": 100.0, "baseDate": "2026-06-01"}

    def test_base_equals_current_is_null(self):
        stale = pts(("2025-01-02", 100.0), ("2025-02-01", 110.0))
        result = lookback_return(stale, TODAY, 1)
        assert result == {"ret": None, "basePrice": None, "baseDate": None}


class TestMonthlyReturns:
    def test_twelve_cells_with_gaps(self):
        points = pts(("2026-05-05", 100.0), ("2026-05-20", 105.0), ("2026-06-15", 126.0))
        months = monthly_returns(points, TODAY)
        assert len(months) == 12
        assert months[0] == {"label": "Jul 25", "ret": None}
        by_label = {m["label"]: m["ret"] for m in months}
        assert by_label["May 26"] is None  # April (previous month) has no data
        assert by_label["Jun 26"] == 20.0  # 126 / 105 - 1
        assert by_label["Apr 26"] is None


class TestCurrencyConversion:
    def test_same_currency_untouched(self):
        points = pts(("2026-01-05", 100.0))
        assert convert_currency(points, "EUR", "EUR", None) == points

    def test_usx_divides_without_fx(self):
        points = pts(("2026-01-05", 250.0))
        converted = convert_currency(points, "USX", "EUR", None)
        assert converted[0].close == 2.5

    def test_gbp_pence_uses_fx_over_100(self):
        points = pts(("2026-02-01", 200.0))
        fx = pts(("2026-01-01", 1.15))
        converted = convert_currency(points, "GBp", "EUR", fx)
        assert converted[0].close == 200.0 * 1.15 / 100

    def test_as_of_join(self):
        points = pts(
            ("2026-01-05", 10.0),  # before first FX point -> first rate
            ("2026-01-10", 10.0),
            ("2026-01-19", 10.0),
            ("2026-01-20", 10.0),
            ("2026-02-01", 10.0),
        )
        fx = pts(("2026-01-10", 2.0), ("2026-01-20", 3.0))
        closes = [p.close for p in convert_currency(points, "USD", "EUR", fx)]
        assert closes == [20.0, 20.0, 20.0, 30.0, 30.0]

    def test_missing_fx_leaves_unconverted(self):
        points = pts(("2026-01-05", 100.0))
        assert convert_currency(points, "USD", "EUR", None) == points
        assert convert_currency(points, "USD", "EUR", []) == points


class TestRequiredFxSymbols:
    def test_excludes_base_and_usx_and_dedupes(self):
        symbols = required_fx_symbols(["USD", "EUR", "GBp", "USX", "USD"], "EUR")
        assert symbols == ["USDEUR=X", "GBPEUR=X"]


class TestComputeTickerMetrics:
    def test_insufficient_series_not_ok(self):
        result = compute_ticker_metrics(None, "USD", "EUR", None, TODAY)
        assert result["ok"] is False
        assert result["currentPrice"] is None
        assert result["ret12m"] is None
        assert result["monthly"] == []
        assert set(result["lookbacks"]) == {"1", "3", "6", "12"}

    def test_full_computation(self):
        raw = series(
            ("2025-06-20", 100.0),
            ("2026-06-01", 100.0),
            ("2026-06-10", 110.0),
            ("2026-07-03", 121.0),
        )
        fx = series(("2025-01-01", 2.0))
        result = compute_ticker_metrics(raw, "USD", "EUR", fx, TODAY)
        assert result["ok"] is True
        assert result["currentPrice"] == 242.0
        # conversion with a constant rate leaves returns unchanged
        assert result["lookbacks"]["1"]["ret"] == 10.0
        assert result["lookbacks"]["1"]["basePrice"] == 220.0
        assert result["ret12m"] == result["lookbacks"]["12"]["ret"] == 21.0
        assert len(result["monthly"]) == 12
