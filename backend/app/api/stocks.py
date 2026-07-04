"""Single-stock search, overview, chart, news, and fundamentals endpoints."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_session
from ..ratelimit import limiter
from ..schemas import CurrentUser
from ..security import get_current_user
from ..services import stock_cache, yahoo
from ..services.technicals import compute_technicals

router = APIRouter(prefix="/api")

SUMMARY_MODULES = [
    "price",
    "summaryProfile",
    "assetProfile",
    "summaryDetail",
    "defaultKeyStatistics",
    "financialData",
    "calendarEvents",
    "recommendationTrend",
    "earnings",
    "earningsTrend",
]

# Statement line items pulled from Yahoo's fundamentals-timeseries endpoint. Each
# base name is prefixed with "annual"/"quarterly" per period. Order here defines
# column order in the UI (endDate is prepended). Keep each list at 7 so a table
# shows at most 8 columns.
INCOME_METRICS = [
    "TotalRevenue",
    "CostOfRevenue",
    "GrossProfit",
    "OperatingIncome",
    "NetIncome",
    "EBITDA",
    "DilutedEPS",
]
BALANCE_METRICS = [
    "TotalAssets",
    "TotalLiabilitiesNetMinorityInterest",
    "StockholdersEquity",
    "CashAndCashEquivalents",
    "TotalDebt",
    "CurrentAssets",
    "CurrentLiabilities",
]
CASHFLOW_METRICS = [
    "OperatingCashFlow",
    "InvestingCashFlow",
    "FinancingCashFlow",
    "FreeCashFlow",
    "CapitalExpenditure",
    "EndCashPosition",
    "NetIncome",
]
STATEMENT_METRICS = [*INCOME_METRICS, *BALANCE_METRICS, *CASHFLOW_METRICS]


def _symbol(value: str) -> str:
    symbol = " ".join(str(value or "").split()).upper()
    if not symbol:
        raise HTTPException(400, "Symbol is required")
    return symbol


def _search_query(value: str) -> str:
    query = " ".join(str(value or "").split())
    if not query:
        raise HTTPException(400, "Search query is required")
    return query


def _cached_chart(session: Session, symbol: str, range_: str, interval: str) -> dict | None:
    settings = get_settings()
    key = f"chart:{symbol}:{range_.lower()}:{interval.lower()}"
    cached = stock_cache.get_json(session, key, settings.stock_chart_cache_ttl_seconds)
    if isinstance(cached, dict):
        return cached

    data = yahoo.download_ohlc(symbol, range_, interval)
    if data:
        stock_cache.set_json(session, key, data)
    return data


def _cached_summary(session: Session, symbol: str) -> dict | None:
    settings = get_settings()
    key = f"summary:{symbol}"
    cached = stock_cache.get_json(session, key, settings.fundamentals_cache_ttl_seconds)
    if isinstance(cached, dict):
        return cached

    data = yahoo.fetch_quote_summary(symbol, SUMMARY_MODULES)
    if data:
        stock_cache.set_json(session, key, data)
    return data


def _quote_from(chart: dict | None, summary: dict | None, symbol: str) -> dict:
    meta = chart.get("meta") if isinstance(chart, dict) else {}
    price = (summary or {}).get("price") or {}
    details = (summary or {}).get("summaryDetail") or {}
    key_stats = (summary or {}).get("defaultKeyStatistics") or {}
    financial_data = (summary or {}).get("financialData") or {}

    current = (
        price.get("regularMarketPrice")
        or meta.get("regularMarketPrice")
        or price.get("postMarketPrice")
        or price.get("preMarketPrice")
    )
    previous = (
        price.get("regularMarketPreviousClose")
        or details.get("previousClose")
        or meta.get("previousClose")
        or meta.get("chartPreviousClose")
    )
    change = price.get("regularMarketChange")
    if change is None and current is not None and previous:
        change = current - previous
    change_percent = price.get("regularMarketChangePercent")
    if change_percent is None and change is not None and previous:
        change_percent = (change / previous) * 100

    return {
        "symbol": symbol,
        "name": price.get("longName") or price.get("shortName") or meta.get("name") or symbol,
        "exchange": price.get("exchangeName") or meta.get("exchangeName"),
        "fullExchangeName": price.get("fullExchangeName") or meta.get("fullExchangeName"),
        "currency": price.get("currency") or meta.get("currency"),
        "regularMarketPrice": current,
        "previousClose": previous,
        "dayChange": change,
        "dayChangePercent": change_percent,
        "marketCap": price.get("marketCap") or key_stats.get("marketCap"),
        "trailingPE": details.get("trailingPE") or key_stats.get("trailingPE"),
        "dividendYield": details.get("dividendYield"),
        "fiftyTwoWeekHigh": details.get("fiftyTwoWeekHigh") or meta.get("fiftyTwoWeekHigh"),
        "fiftyTwoWeekLow": details.get("fiftyTwoWeekLow") or meta.get("fiftyTwoWeekLow"),
        "volume": price.get("regularMarketVolume") or meta.get("regularMarketVolume"),
        "averageVolume": details.get("averageVolume"),
        "targetMeanPrice": financial_data.get("targetMeanPrice"),
    }


def _date_to_unix(as_of_date: str | None) -> int | None:
    try:
        return int(
            datetime.strptime(as_of_date, "%Y-%m-%d").replace(tzinfo=UTC).timestamp()
        )
    except (TypeError, ValueError):
        return None


def _metric_key(base: str) -> str:
    # Lowercase the leading char for normal words (TotalRevenue -> totalRevenue)
    # but leave leading acronyms intact (EBITDA stays EBITDA).
    if len(base) >= 2 and base[1].isupper():
        return base
    return base[:1].lower() + base[1:]


def _statement_rows(
    timeseries: dict[str, list[dict]], prefix: str, metrics: list[str]
) -> list[dict]:
    """Build period rows for one statement from timeseries data.

    Only metrics that returned data are included as columns, preserving the order
    in ``metrics``. Rows are one per reporting period, most recent first, each
    keyed by ``endDate`` plus the present metric keys.
    """
    per_metric: dict[str, dict[str, float | None]] = {}
    present: list[str] = []
    dates: set[str] = set()
    for base in metrics:
        points = timeseries.get(f"{prefix}{base}") or []
        by_date = {
            point["date"]: point.get("value")
            for point in points
            if point.get("date") is not None
        }
        if not by_date:
            continue
        present.append(base)
        per_metric[base] = by_date
        dates.update(by_date)

    rows = []
    for as_of_date in sorted(dates, reverse=True):
        row: dict = {"endDate": _date_to_unix(as_of_date)}
        for base in present:
            row[_metric_key(base)] = per_metric[base].get(as_of_date)
        rows.append(row)
    return rows


@router.get("/search")
@limiter.limit("120/minute")
def search(
    request: Request,
    q: str = Query(min_length=1, max_length=80),
    _current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    query = _search_query(q)
    settings = get_settings()
    key = f"search:{query.lower()}"
    cached = stock_cache.get_json(session, key, settings.search_cache_ttl_seconds)
    if isinstance(cached, dict) and (cached.get("quotes") or cached.get("news")):
        return cached
    data = yahoo.search_symbols(query)
    if data is None:
        return {"quotes": [], "news": []}
    stock_cache.set_json(session, key, data)
    return data


@router.get("/stocks/{symbol}")
@limiter.limit("120/minute")
def stock_overview(
    request: Request,
    symbol: str,
    _current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    normalized = _symbol(symbol)
    chart = _cached_chart(session, normalized, "5d", "1d")
    if not chart:
        raise HTTPException(404, "Stock not found")

    summary = _cached_summary(session, normalized)
    return {
        "quote": _quote_from(chart, summary, normalized),
        "profile": (summary or {}).get("summaryProfile") or (summary or {}).get("assetProfile"),
        "keyStats": (summary or {}).get("defaultKeyStatistics"),
        "financialData": (summary or {}).get("financialData"),
        "calendar": (summary or {}).get("calendarEvents"),
        "recommendation": (summary or {}).get("recommendationTrend"),
        "earnings": (summary or {}).get("earnings"),
        "earningsTrend": (summary or {}).get("earningsTrend"),
        "currency": _quote_from(chart, summary, normalized).get("currency"),
        "fundamentalsAvailable": summary is not None,
    }


@router.get("/stocks/{symbol}/chart")
@limiter.limit("120/minute")
def stock_chart(
    request: Request,
    symbol: str,
    range_: str = Query(default="1y", alias="range", max_length=8),
    interval: str = Query(default="1d", max_length=8),
    _current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    normalized = _symbol(symbol)
    data = _cached_chart(session, normalized, range_, interval)
    if not data:
        raise HTTPException(404, "Stock chart not found")
    return {**data, "technicals": compute_technicals(data["ohlc"])}


@router.get("/stocks/{symbol}/news")
@limiter.limit("120/minute")
def stock_news(
    request: Request,
    symbol: str,
    _current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    normalized = _symbol(symbol)
    settings = get_settings()
    key = f"news:{normalized}"
    cached = stock_cache.get_json(session, key, settings.news_cache_ttl_seconds)
    if isinstance(cached, dict) and cached.get("news"):
        return cached
    data = yahoo.fetch_news(normalized)
    if data is None:
        return {"news": []}
    stock_cache.set_json(session, key, data)
    return data


@router.get("/stocks/{symbol}/financials")
@limiter.limit("120/minute")
def stock_financials(
    request: Request,
    symbol: str,
    _current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    normalized = _symbol(symbol)
    settings = get_settings()
    key = f"financials:{normalized}"
    cached = stock_cache.get_json(session, key, settings.fundamentals_cache_ttl_seconds)
    if isinstance(cached, dict):
        return cached

    types = [
        f"{prefix}{base}"
        for prefix in ("annual", "quarterly")
        for base in STATEMENT_METRICS
    ]
    timeseries = yahoo.fetch_fundamentals_timeseries(normalized, types)
    if timeseries is None:
        return {
            "financialsAvailable": False,
            "incomeAnnual": [],
            "incomeQuarterly": [],
            "balanceAnnual": [],
            "balanceQuarterly": [],
            "cashflowAnnual": [],
            "cashflowQuarterly": [],
        }

    data = {
        "financialsAvailable": True,
        "incomeAnnual": _statement_rows(timeseries, "annual", INCOME_METRICS),
        "incomeQuarterly": _statement_rows(timeseries, "quarterly", INCOME_METRICS),
        "balanceAnnual": _statement_rows(timeseries, "annual", BALANCE_METRICS),
        "balanceQuarterly": _statement_rows(timeseries, "quarterly", BALANCE_METRICS),
        "cashflowAnnual": _statement_rows(timeseries, "annual", CASHFLOW_METRICS),
        "cashflowQuarterly": _statement_rows(timeseries, "quarterly", CASHFLOW_METRICS),
    }
    stock_cache.set_json(session, key, data)
    return data
