"""Two-layer price caching: PostgreSQL rows with a TTL, plus an in-process
failure cooldown so known-bad tickers are not retried immediately.
Both layers are per-process/single-instance by design."""
import time
from datetime import UTC, datetime, timedelta
from threading import Lock

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..config import PRICE_FAILURE_COOLDOWN_SECONDS, get_settings
from ..models import PriceCache
from ..schemas import CurrentUser
from .yahoo import Series, is_valid_series

_failure_cache: dict[str, float] = {}
_failure_cache_lock = Lock()


def unique_symbols(symbols: list[str]) -> list[str]:
    seen = set()
    unique = []
    for symbol in symbols:
        cleaned = " ".join(str(symbol or "").split())
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        unique.append(cleaned)
    return unique


def account_cache_key(current_user: CurrentUser) -> str:
    if current_user.role == "demo":
        return "demo"
    return "admin"


def get_cached_prices(session: Session, account_key: str, tickers: list[str]) -> dict[str, Series]:
    if not tickers:
        return {}

    ttl = get_settings().price_cache_ttl_seconds
    cutoff = datetime.now(UTC) - timedelta(seconds=ttl)
    session.execute(delete(PriceCache).where(PriceCache.cached_at < cutoff))
    rows = session.execute(
        select(PriceCache.ticker, PriceCache.data).where(
            PriceCache.account_key == account_key,
            PriceCache.ticker.in_(tickers),
            PriceCache.cached_at >= cutoff,
        )
    ).all()
    session.commit()

    return {row.ticker: row.data for row in rows if is_valid_series(row.data)}


def set_cached_prices(session: Session, account_key: str, price_data: dict[str, Series | None]) -> None:
    cacheable = {ticker: data for ticker, data in price_data.items() if is_valid_series(data)}
    if not cacheable:
        return

    for ticker, data in cacheable.items():
        stmt = pg_insert(PriceCache).values(
            account_key=account_key,
            ticker=ticker,
            data=data,
            cached_at=datetime.now(UTC),
        )
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=["account_key", "ticker"],
                set_={"data": stmt.excluded.data, "cached_at": stmt.excluded.cached_at},
            )
        )
    session.commit()


def clear_cache(session: Session) -> int:
    deleted = session.execute(delete(PriceCache)).rowcount
    session.commit()
    with _failure_cache_lock:
        _failure_cache.clear()
    return deleted


def recent_failed_tickers(tickers: list[str]) -> list[str]:
    now = time.monotonic()
    recent = []
    with _failure_cache_lock:
        for ticker in tickers:
            failed_at = _failure_cache.get(ticker)
            if failed_at is None:
                continue
            if now - failed_at < PRICE_FAILURE_COOLDOWN_SECONDS:
                recent.append(ticker)
            else:
                _failure_cache.pop(ticker, None)
    return recent


def record_fetch_results(price_data: dict[str, Series | None]) -> None:
    now = time.monotonic()
    permanent_failures = getattr(price_data, "permanent_failures", None)
    with _failure_cache_lock:
        for ticker, data in price_data.items():
            if is_valid_series(data):
                _failure_cache.pop(ticker, None)
            elif permanent_failures is None or ticker in permanent_failures:
                _failure_cache[ticker] = now
            else:
                _failure_cache.pop(ticker, None)
