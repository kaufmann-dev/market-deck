"""Global JSON cache for Yahoo-backed stock endpoints."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..models import YahooCache


def get_json(session: Session, key: str, ttl: int) -> dict | list | None:
    cutoff = datetime.now(UTC) - timedelta(seconds=ttl)
    session.execute(delete(YahooCache).where(YahooCache.cached_at < cutoff))
    row = session.execute(
        select(YahooCache.data).where(YahooCache.cache_key == key, YahooCache.cached_at >= cutoff)
    ).first()
    session.commit()
    return row.data if row else None


def set_json(session: Session, key: str, data: dict | list) -> None:
    stmt = pg_insert(YahooCache).values(
        cache_key=key,
        data=data,
        cached_at=datetime.now(UTC),
    )
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=["cache_key"],
            set_={"data": stmt.excluded.data, "cached_at": stmt.excluded.cached_at},
        )
    )
    session.commit()
