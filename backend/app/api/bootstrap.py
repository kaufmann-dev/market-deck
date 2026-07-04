"""App bootstrap (/api/init) and settings endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from ..db import get_session
from ..models import Setting, Watchlist
from ..schemas import CurrentUser, SettingUpdate
from ..security import get_current_user, require_admin

router = APIRouter(prefix="/api")


def _settings_map(session: Session) -> dict[str, str]:
    return {row.key: row.value for row in session.scalars(select(Setting))}


@router.get("/init")
def api_init(
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    watchlists = session.scalars(
        select(Watchlist)
        .options(selectinload(Watchlist.tags), selectinload(Watchlist.tickers))
        .order_by(Watchlist.id)
    ).all()

    lists = {
        wl.slug: {
            "id": wl.id,
            "name": wl.name,
            "shortName": wl.short_name,
            "category": wl.category,
            "description": wl.description,
            "currency": wl.currency,
            "showTag": bool(wl.show_tag),
            "tags": [
                {"tag": t.tag, "bg": t.bg, "text": t.text, "border": t.border, "sortOrder": t.sort_order}
                for t in wl.tags
            ],
            "items": [
                {"id": t.id, "ticker": t.symbol, "name": t.name, "tag": t.tag, "currency": t.currency}
                for t in wl.tickers
            ],
        }
        for wl in watchlists
    }
    return {"settings": _settings_map(session), "lists": lists}


@router.get("/settings")
def get_settings_endpoint(
    current_user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return _settings_map(session)


@router.put("/settings/{key}")
def update_setting(
    key: str,
    body: SettingUpdate,
    current_user: CurrentUser = Depends(require_admin),
    session: Session = Depends(get_session),
):
    stmt = pg_insert(Setting).values(key=key, value=body.value)
    session.execute(
        stmt.on_conflict_do_update(index_elements=["key"], set_={"value": stmt.excluded.value})
    )
    session.commit()
    return {"key": key, "value": body.value}
