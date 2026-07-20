"""Server-computed list metrics (FX conversion, lookback and monthly returns)."""
import logging
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_session
from ..models import Setting, Watchlist
from ..ratelimit import limiter
from ..schemas import CurrentUser
from ..security import get_current_user, require_admin
from ..services import price_cache, yahoo
from ..services.metrics import compute_ticker_metrics, fx_symbol, required_fx_symbols

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

DEFAULT_BASE_CURRENCY = "EUR"


def _load_series(session: Session, account_key: str, symbols: list[str]) -> dict:
    """Cache-first load of price series; fetches misses from Yahoo in parallel."""
    result = price_cache.get_cached_prices(session, account_key, symbols)
    cache_hits = len(result)
    uncached = [symbol for symbol in symbols if symbol not in result]
    recent_failures = set(price_cache.recent_failed_tickers(uncached))
    for symbol in recent_failures:
        result[symbol] = None
    need_fetch = [symbol for symbol in uncached if symbol not in recent_failures]

    if need_fetch:
        fresh = yahoo.download_prices(need_fetch)
        price_cache.record_fetch_results(fresh)
        result.update(fresh)
        price_cache.set_cached_prices(session, account_key, fresh)

    logger.info(
        "price load requested=%d cache_hits=%d recent_failures=%d yahoo_chart_fetch=%d",
        len(symbols), cache_hits, len(recent_failures), len(need_fetch),
    )
    return result


@router.get("/lists/{slug}/metrics")
@limiter.limit("120/minute")
def list_metrics(
    request: Request,
    slug: str,
    base: str | None = Query(default=None, max_length=8),
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    started_at = time.monotonic()
    watchlist = session.scalars(
        select(Watchlist).options(selectinload(Watchlist.tickers)).where(Watchlist.slug == slug)
    ).first()
    if not watchlist:
        raise HTTPException(404, "List not found")

    if base:
        base_currency = base.strip()
    else:
        setting = session.get(Setting, "GLOBAL_BASE_CURRENCY")
        base_currency = setting.value if setting else DEFAULT_BASE_CURRENCY

    stock_symbols = price_cache.unique_symbols([t.symbol for t in watchlist.tickers])
    fx_symbols = required_fx_symbols([t.currency for t in watchlist.tickers], base_currency)

    account_key = price_cache.account_cache_key(current_user)
    series = _load_series(session, account_key, stock_symbols + fx_symbols)

    today = datetime.now(UTC).date()
    tickers = []
    failed = []
    for ticker in watchlist.tickers:
        fx_series = None
        if ticker.currency and ticker.currency not in (base_currency, "USX"):
            fx_series = series.get(fx_symbol(ticker.currency, base_currency))
        metrics = compute_ticker_metrics(
            series.get(ticker.symbol), ticker.currency, base_currency, fx_series, today
        )
        if not metrics["ok"]:
            failed.append(ticker.symbol)
        tickers.append(
            {
                "id": ticker.id,
                "symbol": ticker.symbol,
                "name": ticker.name,
                "tag": ticker.tag,
                "currency": ticker.currency,
                **metrics,
            }
        )

    logger.info(
        "metrics list=%s base=%s tickers=%d failed=%d elapsed=%.2fs",
        slug, base_currency, len(tickers), len(failed), time.monotonic() - started_at,
    )
    return {
        "baseCurrency": base_currency,
        "asOf": today.isoformat(),
        "tickers": tickers,
        "failed": failed,
    }


@router.delete("/prices/cache")
def clear_price_cache(
    current_user: CurrentUser = Depends(require_admin),
    session: Session = Depends(get_session),
):
    deleted = price_cache.clear_cache(session)
    return {"ok": True, "deleted": deleted}
