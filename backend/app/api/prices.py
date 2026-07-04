"""Price data endpoints."""
import logging
import time

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_session
from ..ratelimit import limiter
from ..schemas import CurrentUser, PricesRequest
from ..security import get_current_user
from ..services import price_cache, yahoo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.post("/prices")
@limiter.limit("120/minute")
def fetch_prices(
    request: Request,
    body: PricesRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    started_at = time.monotonic()
    tickers = price_cache.unique_symbols(body.tickers)
    if not tickers:
        return {}

    account_email = price_cache.account_cache_key(current_user)
    result = price_cache.get_cached_prices(session, account_email, tickers)
    cache_hits = len(result)
    uncached = [ticker for ticker in tickers if ticker not in result]
    recent_failures = set(price_cache.recent_failed_tickers(uncached))
    for ticker in recent_failures:
        result[ticker] = None
    need_fetch = [ticker for ticker in uncached if ticker not in recent_failures]

    if need_fetch:
        fresh = yahoo.download_prices(need_fetch)
        price_cache.record_fetch_results(fresh)
        result.update(fresh)
        price_cache.set_cached_prices(session, account_email, fresh)

    for ticker in tickers:
        result.setdefault(ticker, None)

    logger.info(
        "price fetch requested=%d cache_hits=%d recent_failures=%d yahoo_chart_fetch=%d elapsed=%.2fs",
        len(tickers), cache_hits, len(recent_failures), len(need_fetch),
        time.monotonic() - started_at,
    )
    return result
