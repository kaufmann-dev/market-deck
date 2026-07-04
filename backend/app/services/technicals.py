"""Pure technical indicator readouts over Yahoo OHLCV points."""
import math
from statistics import fmean, stdev


def _float(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _round(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def _values(points: list[dict], field: str) -> list[float]:
    values = []
    for point in points:
        value = _float(point.get(field))
        if value is not None:
            values.append(value)
    return values


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return fmean(values[-period:])


def ema_series(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    multiplier = 2 / (period + 1)
    current = fmean(values[:period])
    result[period - 1] = current
    for index in range(period, len(values)):
        current = (values[index] - current) * multiplier + current
        result[index] = current
    return result


def ema(values: list[float], period: int) -> float | None:
    series = ema_series(values, period)
    for value in reversed(series):
        if value is not None:
            return value
    return None


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None

    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(change, 0) for change in changes]
    losses = [abs(min(change, 0)) for change in changes]
    avg_gain = fmean(gains[:period])
    avg_loss = fmean(losses[:period])

    for index in range(period, len(changes)):
        avg_gain = ((avg_gain * (period - 1)) + gains[index]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[index]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(values: list[float]) -> dict:
    ema12 = ema_series(values, 12)
    ema26 = ema_series(values, 26)
    macd_values: list[float] = []
    macd_by_index: list[float | None] = []
    for fast, slow in zip(ema12, ema26, strict=False):
        if fast is None or slow is None:
            macd_by_index.append(None)
            continue
        value = fast - slow
        macd_by_index.append(value)
        macd_values.append(value)

    signal_values = ema_series(macd_values, 9)
    signal = next((value for value in reversed(signal_values) if value is not None), None)
    macd_line = next((value for value in reversed(macd_by_index) if value is not None), None)
    histogram = macd_line - signal if macd_line is not None and signal is not None else None
    return {
        "macd": _round(macd_line, 4),
        "signal": _round(signal, 4),
        "histogram": _round(histogram, 4),
    }


def annualized_volatility(values: list[float]) -> float | None:
    returns = []
    for previous, current in zip(values, values[1:], strict=False):
        if previous <= 0 or current <= 0:
            continue
        returns.append(math.log(current / previous))
    if len(returns) < 2:
        return None
    sample = returns[-252:]
    return stdev(sample) * math.sqrt(252) * 100


def compute_technicals(ohlc: list[dict]) -> dict:
    closes = _values(ohlc, "close")
    if not closes:
        return {}

    last_252 = ohlc[-252:]
    highs = [_float(point.get("high")) or _float(point.get("close")) for point in last_252]
    lows = [_float(point.get("low")) or _float(point.get("close")) for point in last_252]
    highs = [value for value in highs if value is not None]
    lows = [value for value in lows if value is not None]
    fifty_two_week_high = max(highs) if highs else None
    fifty_two_week_low = min(lows) if lows else None
    current = closes[-1]
    percent_from_high = (
        ((current / fifty_two_week_high) - 1) * 100
        if fifty_two_week_high and fifty_two_week_high > 0
        else None
    )
    volumes = [value for value in _values(ohlc[-20:], "volume") if value >= 0]

    return {
        "sma20": _round(sma(closes, 20)),
        "sma50": _round(sma(closes, 50)),
        "sma200": _round(sma(closes, 200)),
        "ema12": _round(ema(closes, 12)),
        "ema26": _round(ema(closes, 26)),
        "rsi14": _round(rsi(closes, 14)),
        "macd": macd(closes),
        "fiftyTwoWeekHigh": _round(fifty_two_week_high),
        "fiftyTwoWeekLow": _round(fifty_two_week_low),
        "percentFromHigh": _round(percent_from_high),
        "avgVolume20": _round(fmean(volumes), 0) if volumes else None,
        "annualizedVolatility": _round(annualized_volatility(closes)),
    }
