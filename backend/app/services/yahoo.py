"""Yahoo Finance chart-JSON price fetching.

Fetches daily adjusted closes directly from the chart endpoint in parallel —
see docs/bugs/slow-global-ticker-loading.md for why yfinance was dropped.
"""
import logging
import math
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from ..config import (
    PRICE_FETCH_MAX_WORKERS,
    PRICE_FETCH_TIMEOUT_SECONDS,
    PRICE_FETCH_TOTAL_TIMEOUT_SECONDS,
    PRICE_HISTORY_DAYS,
    YAHOO_CHART_BASE_URL,
)

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "Mozilla/5.0"}

Series = list[dict]  # [{"date": "YYYY-MM-DD", "close": float}, ...]


def is_valid_series(data) -> bool:
    return isinstance(data, list) and len(data) >= 2


def _chart_timezone(meta):
    timezone_name = (meta or {}).get("exchangeTimezoneName") or (meta or {}).get("timezone")
    if not timezone_name:
        return timezone.utc
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone.utc


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
    for timestamp, close in zip(timestamps, closes):
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


def chart_url(ticker: str, period1: int, period2: int) -> str:
    encoded_ticker = quote(ticker, safe="")
    return (
        f"{YAHOO_CHART_BASE_URL}/{encoded_ticker}"
        f"?period1={period1}&period2={period2}"
        "&interval=1d&events=history&includeAdjustedClose=true"
    )


def _fetch_one(client: httpx.Client, ticker: str, period1: int, period2: int) -> Series | None:
    response = client.get(chart_url(ticker, period1, period2))
    response.raise_for_status()
    return parse_chart_payload(response.json())


def download_prices(tickers: list[str]) -> dict[str, Series | None]:
    if not tickers:
        return {}

    now = datetime.now(timezone.utc)
    period1 = int((now - timedelta(days=PRICE_HISTORY_DAYS)).timestamp())
    period2 = int(now.timestamp())
    result: dict[str, Series | None] = {ticker: None for ticker in tickers}

    executor = ThreadPoolExecutor(max_workers=min(PRICE_FETCH_MAX_WORKERS, len(tickers)))
    with httpx.Client(headers=_HEADERS, timeout=PRICE_FETCH_TIMEOUT_SECONDS) as client:
        futures = {
            executor.submit(_fetch_one, client, ticker, period1, period2): ticker
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
                    failures.append(f"{ticker}: {type(exc).__name__}")
                    result[ticker] = None
            if failures:
                logger.warning("Yahoo chart failures (%d): %s", len(failures), ", ".join(failures[:8]))
            if not_done:
                logger.warning("Yahoo chart timed out for %d tickers", len(not_done))
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    return result
