"""Yahoo Finance chart/search/summary fetching.

Fetches daily adjusted closes directly from the chart endpoint in parallel —
see docs/bugs/slow-global-ticker-loading.md for why yfinance was dropped.
"""
import logging
import math
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from ..config import (
    PRICE_FETCH_MAX_WORKERS,
    PRICE_FETCH_TIMEOUT_SECONDS,
    PRICE_FETCH_TOTAL_TIMEOUT_SECONDS,
    YAHOO_CHART_BASE_URL,
    YAHOO_FUNDAMENTALS_TIMESERIES_URL,
    YAHOO_QUOTE_SUMMARY_URL,
    YAHOO_SEARCH_URL,
)
from . import yahoo_auth

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_CHART_HEADERS = _HEADERS

Series = list[dict]  # [{"date": "YYYY-MM-DD", "close": float}, ...]
OhlcSeries = list[dict]  # [{"date": "YYYY-MM-DD", "open": float, ...}, ...]


class PriceDownloadResult(dict):
    def __init__(self, *args, permanent_failures: set[str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.permanent_failures = permanent_failures or set()


def is_valid_series(data) -> bool:
    return isinstance(data, list) and len(data) >= 2


def _chart_timezone(meta):
    timezone_name = (meta or {}).get("exchangeTimezoneName") or (meta or {}).get("timezone")
    if not timezone_name:
        return UTC
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return UTC


def _chart_closes(indicators):
    if not isinstance(indicators, dict):
        return []

    adjclose = indicators.get("adjclose") or []
    if adjclose:
        closes = adjclose[0].get("adjclose") if isinstance(adjclose[0], dict) else None
        if closes and any(close is not None for close in closes):
            return closes

    quote_data = indicators.get("quote") or []
    if quote_data:
        closes = quote_data[0].get("close") if isinstance(quote_data[0], dict) else None
        if closes and any(close is not None for close in closes):
            return closes
    return []


def parse_chart_payload(payload) -> Series | None:
    chart = payload.get("chart") if isinstance(payload, dict) else None
    if not isinstance(chart, dict) or chart.get("error"):
        return None

    results = chart.get("result") or []
    if not results or not isinstance(results[0], dict):
        return None

    result = results[0]
    timestamps = result.get("timestamp") or []
    closes = _chart_closes(result.get("indicators"))
    if not timestamps or not closes:
        return None

    tz = _chart_timezone(result.get("meta"))
    points = []
    for timestamp, close in zip(timestamps, closes, strict=False):
        if close is None:
            continue
        try:
            close_value = float(close)
            timestamp_value = int(timestamp)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(close_value):
            continue
        date = datetime.fromtimestamp(timestamp_value, tz).date().isoformat()
        points.append({"date": date, "close": round(close_value, 4)})
    return points if len(points) >= 2 else None


def chart_url(ticker: str) -> str:
    encoded_ticker = quote(ticker, safe="")
    return (
        f"{YAHOO_CHART_BASE_URL}/{encoded_ticker}"
        "?range=2y"
        "&interval=1d&events=history&includeAdjustedClose=true"
    )


def _chart_endpoint(symbol: str) -> str:
    return f"{YAHOO_CHART_BASE_URL}/{quote(symbol, safe='')}"


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _int_value(value) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number


def normalize_chart_meta(meta) -> dict:
    if not isinstance(meta, dict):
        return {}
    name = meta.get("longName") or meta.get("shortName") or meta.get("symbol")
    return {
        "symbol": meta.get("symbol"),
        "name": name,
        "currency": meta.get("currency"),
        "exchangeName": meta.get("exchangeName"),
        "fullExchangeName": meta.get("fullExchangeName"),
        "instrumentType": meta.get("instrumentType"),
        "timezone": meta.get("exchangeTimezoneName") or meta.get("timezone"),
        "regularMarketPrice": _number(meta.get("regularMarketPrice")),
        "previousClose": _number(meta.get("previousClose") or meta.get("chartPreviousClose")),
        "chartPreviousClose": _number(meta.get("chartPreviousClose")),
        "regularMarketDayHigh": _number(meta.get("regularMarketDayHigh")),
        "regularMarketDayLow": _number(meta.get("regularMarketDayLow")),
        "fiftyTwoWeekHigh": _number(meta.get("fiftyTwoWeekHigh")),
        "fiftyTwoWeekLow": _number(meta.get("fiftyTwoWeekLow")),
        "regularMarketVolume": _int_value(meta.get("regularMarketVolume")),
        "regularMarketTime": _int_value(meta.get("regularMarketTime")),
    }


def parse_chart_ohlc_payload(payload) -> dict | None:
    chart = payload.get("chart") if isinstance(payload, dict) else None
    if not isinstance(chart, dict) or chart.get("error"):
        return None

    results = chart.get("result") or []
    if not results or not isinstance(results[0], dict):
        return None

    result = results[0]
    timestamps = result.get("timestamp") or []
    quote_data = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    if not isinstance(quote_data, dict) or not timestamps:
        return None

    opens = quote_data.get("open") or []
    highs = quote_data.get("high") or []
    lows = quote_data.get("low") or []
    closes = quote_data.get("close") or []
    volumes = quote_data.get("volume") or []
    tz = _chart_timezone(result.get("meta"))

    points: OhlcSeries = []
    for i, timestamp in enumerate(timestamps):
        close = _number(closes[i] if i < len(closes) else None)
        if close is None:
            continue
        try:
            timestamp_value = int(timestamp)
        except (TypeError, ValueError):
            continue
        date = datetime.fromtimestamp(timestamp_value, tz).date().isoformat()
        points.append(
            {
                "date": date,
                "open": _number(opens[i] if i < len(opens) else None),
                "high": _number(highs[i] if i < len(highs) else None),
                "low": _number(lows[i] if i < len(lows) else None),
                "close": close,
                "volume": _int_value(volumes[i] if i < len(volumes) else None),
            }
        )

    return {"ohlc": points, "meta": normalize_chart_meta(result.get("meta"))} if len(points) >= 2 else None


def _simplify_yahoo_value(value):
    if isinstance(value, dict):
        if "raw" in value:
            return value["raw"]
        if "fmt" in value and len(value) <= 2:
            return value["fmt"]
        return {key: _simplify_yahoo_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_simplify_yahoo_value(item) for item in value]
    return value


def _normalize_quote(item) -> dict:
    if not isinstance(item, dict):
        return {}
    symbol = str(item.get("symbol") or "").strip().upper()
    return {
        "symbol": symbol,
        "name": item.get("longname") or item.get("shortname") or item.get("name") or symbol,
        "exchange": item.get("exchDisp") or item.get("exchange"),
        "quoteType": item.get("quoteType") or item.get("typeDisp"),
        "type": item.get("typeDisp") or item.get("quoteType"),
        "currency": item.get("currency"),
    }


def _normalize_news(item) -> dict:
    if not isinstance(item, dict):
        return {}
    thumbnail = None
    resolutions = ((item.get("thumbnail") or {}).get("resolutions") or [])
    if resolutions and isinstance(resolutions[0], dict):
        thumbnail = resolutions[0].get("url")
    return {
        "title": item.get("title") or "",
        "publisher": item.get("publisher") or "",
        "link": item.get("link") or "",
        "publishedAt": _int_value(item.get("providerPublishTime")),
        "thumbnail": thumbnail,
    }


def _fetch_one(client: httpx.Client, ticker: str) -> Series | None:
    response = client.get(chart_url(ticker))
    response.raise_for_status()
    return parse_chart_payload(response.json())


def _permanent_chart_failure(exc: Exception) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404


def download_ohlc(symbol: str, range_: str = "1y", interval: str = "1d") -> dict | None:
    params = {
        "range": range_,
        "interval": interval,
        "events": "history",
        "includeAdjustedClose": "true",
    }
    try:
        with httpx.Client(headers=_CHART_HEADERS, timeout=PRICE_FETCH_TIMEOUT_SECONDS) as client:
            response = client.get(_chart_endpoint(symbol), params=params)
            response.raise_for_status()
            return parse_chart_ohlc_payload(response.json())
    except Exception as exc:
        logger.warning("Yahoo OHLC fetch failed for %s: %s", symbol, type(exc).__name__)
        return None


def search_symbols(query: str) -> dict | None:
    params = {
        "q": query,
        "quotesCount": 8,
        "newsCount": 4,
        "enableFuzzyQuery": "false",
    }
    try:
        with httpx.Client(headers=_HEADERS, timeout=PRICE_FETCH_TIMEOUT_SECONDS) as client:
            response = client.get(YAHOO_SEARCH_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.warning("Yahoo search failed for %s: %s", query, type(exc).__name__)
        return None

    quotes = [_normalize_quote(item) for item in payload.get("quotes") or []]
    news = [_normalize_news(item) for item in payload.get("news") or []]
    return {
        "quotes": [quote for quote in quotes if quote.get("symbol")],
        "news": [item for item in news if item.get("title")],
    }


def fetch_quote_summary(symbol: str, modules: list[str]) -> dict | None:
    if not modules:
        return {}
    url = f"{YAHOO_QUOTE_SUMMARY_URL}/{quote(symbol, safe='')}"
    params: dict[str, Any] = {"modules": ",".join(modules), "formatted": "false"}
    with httpx.Client(headers=_HEADERS, timeout=PRICE_FETCH_TIMEOUT_SECONDS) as client:
        response = yahoo_auth.authed_get(client, url, params=params)
    if response is None:
        return None
    if response.status_code >= 400:
        logger.info("Yahoo quoteSummary unavailable for %s: status=%d", symbol, response.status_code)
        return None

    try:
        payload = response.json()
    except ValueError:
        return None
    quote_summary = payload.get("quoteSummary") if isinstance(payload, dict) else None
    if not isinstance(quote_summary, dict) or quote_summary.get("error"):
        return None
    result = quote_summary.get("result") or []
    if not result or not isinstance(result[0], dict):
        return None
    return _simplify_yahoo_value(result[0])


# Yahoo only serves fundamentals from roughly 1985 onward; this epoch is a safe floor.
_FUNDAMENTALS_PERIOD1 = 493590046


def fetch_fundamentals_timeseries(
    symbol: str, types: list[str]
) -> dict[str, list[dict]] | None:
    """Fetch statement line items from Yahoo's fundamentals-timeseries endpoint.

    Returns a mapping of Yahoo type name (e.g. ``annualTotalRevenue``) to a list
    of ``{"date": "YYYY-MM-DD", "value": float | None}`` points, or ``None`` when
    the request fails. The quoteSummary ``*History`` modules no longer populate
    detailed line items, so this endpoint is the source for full statements.
    """
    if not types:
        return {}
    url = f"{YAHOO_FUNDAMENTALS_TIMESERIES_URL}/{quote(symbol, safe='')}"
    params: dict[str, Any] = {
        "symbol": symbol,
        "type": ",".join(types),
        "period1": _FUNDAMENTALS_PERIOD1,
        "period2": int(datetime.now(UTC).timestamp()),
        "merge": "false",
    }
    with httpx.Client(headers=_HEADERS, timeout=PRICE_FETCH_TIMEOUT_SECONDS) as client:
        response = yahoo_auth.authed_get(client, url, params=params)
    if response is None:
        return None
    if response.status_code >= 400:
        logger.info(
            "Yahoo fundamentals-timeseries unavailable for %s: status=%d",
            symbol,
            response.status_code,
        )
        return None

    try:
        payload = response.json()
    except ValueError:
        return None
    timeseries = payload.get("timeseries") if isinstance(payload, dict) else None
    if not isinstance(timeseries, dict) or timeseries.get("error"):
        return None

    out: dict[str, list[dict]] = {}
    for block in timeseries.get("result") or []:
        if not isinstance(block, dict):
            continue
        type_name = ((block.get("meta") or {}).get("type") or [None])[0]
        if not type_name:
            continue
        points = []
        for point in block.get(type_name) or []:
            if not isinstance(point, dict):
                continue
            reported = point.get("reportedValue")
            value = reported.get("raw") if isinstance(reported, dict) else reported
            points.append({"date": point.get("asOfDate"), "value": value})
        out[type_name] = points
    return out


def fetch_news(symbol: str) -> dict | None:
    params = {"q": symbol, "quotesCount": 0, "newsCount": 12}
    try:
        with httpx.Client(headers=_HEADERS, timeout=PRICE_FETCH_TIMEOUT_SECONDS) as client:
            response = client.get(YAHOO_SEARCH_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.warning("Yahoo news fetch failed for %s: %s", symbol, type(exc).__name__)
        return None
    news = [_normalize_news(item) for item in payload.get("news") or []]
    return {"news": [item for item in news if item.get("title")]}


def download_prices(tickers: list[str]) -> PriceDownloadResult:
    if not tickers:
        return PriceDownloadResult()

    result = PriceDownloadResult({ticker: None for ticker in tickers})
    permanent_failures: set[str] = set()

    executor = ThreadPoolExecutor(max_workers=min(PRICE_FETCH_MAX_WORKERS, len(tickers)))
    with httpx.Client(headers=_CHART_HEADERS, timeout=PRICE_FETCH_TIMEOUT_SECONDS) as client:
        futures = {
            executor.submit(_fetch_one, client, ticker): ticker
            for ticker in tickers
        }
        try:
            done, not_done = wait(futures, timeout=PRICE_FETCH_TOTAL_TIMEOUT_SECONDS)
            for future in not_done:
                future.cancel()

            failures = []
            for future in done:
                ticker = futures[future]
                try:
                    result[ticker] = future.result()
                except Exception as exc:
                    if _permanent_chart_failure(exc):
                        permanent_failures.add(ticker)
                    detail = type(exc).__name__
                    if isinstance(exc, httpx.HTTPStatusError):
                        detail = f"{detail}:{exc.response.status_code}"
                    failures.append(f"{ticker}: {detail}")
                    result[ticker] = None
            if failures:
                logger.warning("Yahoo chart failures (%d): %s", len(failures), ", ".join(failures[:8]))
            if not_done:
                logger.warning("Yahoo chart timed out for %d tickers", len(not_done))
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    result.permanent_failures = permanent_failures
    return result
