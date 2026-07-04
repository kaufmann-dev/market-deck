"""Golden tests for stock technical indicator readouts."""
import pytest

from app.services.technicals import compute_technicals, ema, macd, rsi, sma


def ohlc(count: int) -> list[dict]:
    return [
        {
            "date": f"2026-01-{(index % 28) + 1:02d}",
            "open": float(index + 1),
            "high": float(index + 2),
            "low": float(index),
            "close": float(index + 1),
            "volume": 1000 + index,
        }
        for index in range(count)
    ]


def test_basic_moving_averages():
    values = [float(value) for value in range(1, 31)]
    assert sma(values, 20) == pytest.approx(20.5)
    assert ema(values, 12) == pytest.approx(24.5)


def test_rsi_and_macd_for_rising_series():
    values = [float(value) for value in range(1, 60)]
    assert rsi(values, 14) == 100.0
    signal = macd(values)
    assert signal["macd"] == pytest.approx(7.0)
    assert signal["signal"] == pytest.approx(7.0)
    assert signal["histogram"] == pytest.approx(0.0)


def test_compute_technicals_readouts():
    result = compute_technicals(ohlc(260))
    assert result["sma20"] == 250.5
    assert result["sma50"] == 235.5
    assert result["sma200"] == 160.5
    assert result["rsi14"] == 100.0
    assert result["fiftyTwoWeekHigh"] == 261.0
    assert result["fiftyTwoWeekLow"] == 8.0
    assert result["percentFromHigh"] == -0.38
    assert result["avgVolume20"] == 1250.0
    assert result["annualizedVolatility"] is not None
