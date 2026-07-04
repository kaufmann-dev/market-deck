"""Watchlist, ticker, and tag CRUD endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Ticker, Watchlist, WatchlistTag
from ..schemas import CurrentUser, TagUpdate, TickerCreate, TickerUpdate, WatchlistCreate, WatchlistUpdate
from ..security import require_admin
from ..seed import normalize_category, normalize_tag

router = APIRouter(prefix="/api")


def _get_watchlist(session: Session, slug: str) -> Watchlist:
    watchlist = session.scalars(select(Watchlist).where(Watchlist.slug == slug)).first()
    if not watchlist:
        raise HTTPException(404, "List not found")
    return watchlist


def _require_watchlist_tag(session: Session, watchlist_id: int, tag: str) -> str:
    normalized_tag = normalize_tag(tag)
    if not normalized_tag:
        raise HTTPException(400, "Tag is required")
    exists = session.scalars(
        select(WatchlistTag.id).where(
            WatchlistTag.watchlist_id == watchlist_id, WatchlistTag.tag == normalized_tag
        )
    ).first()
    if not exists:
        raise HTTPException(400, f"Tag '{normalized_tag}' is not defined for this list")
    return normalized_tag


@router.post("/lists")
def create_list(
    body: WatchlistCreate,
    current_user: CurrentUser = Depends(require_admin),
    session: Session = Depends(get_session),
):
    watchlist = Watchlist(
        slug=body.slug,
        name=body.name,
        short_name=body.short_name,
        category=normalize_category(body.category),
        description=body.description,
        currency=body.currency,
        show_tag=body.show_tag,
    )
    session.add(watchlist)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(400, f"Slug '{body.slug}' already exists") from None
    return {"id": watchlist.id, "slug": body.slug}


@router.put("/lists/{slug}")
def update_list(
    slug: str,
    body: WatchlistUpdate,
    current_user: CurrentUser = Depends(require_admin),
    session: Session = Depends(get_session),
):
    watchlist = _get_watchlist(session, slug)

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    if "category" in updates:
        updates["category"] = normalize_category(updates["category"])

    for key, value in updates.items():
        setattr(watchlist, key, value)
    session.commit()
    return {"ok": True}


@router.delete("/lists/{slug}")
def delete_list(
    slug: str,
    current_user: CurrentUser = Depends(require_admin),
    session: Session = Depends(get_session),
):
    watchlist = _get_watchlist(session, slug)
    session.delete(watchlist)
    session.commit()
    return {"ok": True}


@router.post("/lists/{slug}/tickers")
def add_ticker(
    slug: str,
    body: TickerCreate,
    current_user: CurrentUser = Depends(require_admin),
    session: Session = Depends(get_session),
):
    watchlist = _get_watchlist(session, slug)
    tag = _require_watchlist_tag(session, watchlist.id, body.tag)
    max_order = session.scalar(
        select(func.coalesce(func.max(Ticker.sort_order), -1)).where(Ticker.watchlist_id == watchlist.id)
    )
    ticker = Ticker(
        watchlist_id=watchlist.id,
        symbol=body.symbol,
        name=body.name,
        tag=tag,
        currency=body.currency,
        sort_order=max_order + 1,
    )
    session.add(ticker)
    session.commit()
    return {"id": ticker.id}


@router.put("/tickers/{ticker_id}")
def update_ticker(
    ticker_id: int,
    body: TickerUpdate,
    current_user: CurrentUser = Depends(require_admin),
    session: Session = Depends(get_session),
):
    ticker = session.get(Ticker, ticker_id)
    if not ticker:
        raise HTTPException(404, "Ticker not found")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    if "tag" in updates:
        updates["tag"] = _require_watchlist_tag(session, ticker.watchlist_id, updates["tag"])

    for key, value in updates.items():
        setattr(ticker, key, value)
    session.commit()
    return {"ok": True}


@router.delete("/tickers/{ticker_id}")
def delete_ticker(
    ticker_id: int,
    current_user: CurrentUser = Depends(require_admin),
    session: Session = Depends(get_session),
):
    ticker = session.get(Ticker, ticker_id)
    if not ticker:
        raise HTTPException(404, "Ticker not found")
    session.delete(ticker)
    session.commit()
    return {"ok": True}


@router.post("/lists/{slug}/tags")
def create_list_tag(
    slug: str,
    body: TagUpdate,
    current_user: CurrentUser = Depends(require_admin),
    session: Session = Depends(get_session),
):
    normalized_tag = normalize_tag(body.tag or "")
    if not normalized_tag:
        raise HTTPException(400, "Tag is required")

    watchlist = _get_watchlist(session, slug)
    max_order = session.scalar(
        select(func.coalesce(func.max(WatchlistTag.sort_order), -1)).where(
            WatchlistTag.watchlist_id == watchlist.id
        )
    )
    session.add(
        WatchlistTag(
            watchlist_id=watchlist.id,
            tag=normalized_tag,
            bg=body.bg,
            text=body.text,
            border=body.border,
            sort_order=max_order + 1,
        )
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(400, f"Tag '{normalized_tag}' already exists for this list") from None
    return {"tag": normalized_tag}


@router.put("/lists/{slug}/tags/{tag}")
def update_list_tag(
    slug: str,
    tag: str,
    body: TagUpdate,
    current_user: CurrentUser = Depends(require_admin),
    session: Session = Depends(get_session),
):
    normalized_tag = normalize_tag(tag)
    watchlist = _get_watchlist(session, slug)
    tag_row = session.scalars(
        select(WatchlistTag).where(
            WatchlistTag.watchlist_id == watchlist.id, WatchlistTag.tag == normalized_tag
        )
    ).first()
    if not tag_row:
        raise HTTPException(404, "Tag not found")
    tag_row.bg = body.bg
    tag_row.text = body.text
    tag_row.border = body.border
    session.commit()
    return {"ok": True}


@router.delete("/lists/{slug}/tags/{tag}")
def delete_list_tag(
    slug: str,
    tag: str,
    current_user: CurrentUser = Depends(require_admin),
    session: Session = Depends(get_session),
):
    normalized_tag = normalize_tag(tag)
    watchlist = _get_watchlist(session, slug)
    in_use = session.scalar(
        select(func.count()).select_from(Ticker).where(
            Ticker.watchlist_id == watchlist.id, Ticker.tag == normalized_tag
        )
    )
    if in_use > 0:
        raise HTTPException(400, "Cannot delete a tag while tickers use it")
    result = session.execute(
        delete(WatchlistTag).where(
            WatchlistTag.watchlist_id == watchlist.id, WatchlistTag.tag == normalized_tag
        )
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Tag not found")
    session.commit()
    return {"ok": True}
