"""Initial data seeding. Users are seeded idempotently on every start;
watchlist data is seeded only when the watchlists table is empty."""
import logging

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .config import DEMO_AUTH_DISABLED, DEMO_USER_ID, get_settings
from .models import Setting, Ticker, User, Watchlist, WatchlistTag
from .security import hash_password
from .seed_data import SEED_SETTINGS, SEED_TAG_COLORS, SEED_TICKERS, SEED_WATCHLISTS

logger = logging.getLogger(__name__)


def normalize_category(category: str | None) -> str:
    cleaned = " ".join((category or "").split())
    return (cleaned or "Other").upper()


def normalize_tag(tag: str | None) -> str:
    cleaned = " ".join(str(tag or "").split())
    return cleaned.upper()


def tag_color_defaults(tag: str) -> dict:
    normalized_tag = normalize_tag(tag)
    seeded = {normalize_tag(name): colors for name, colors in SEED_TAG_COLORS.items()}
    if normalized_tag == "GLOBAL":
        return {
            "bg": "rgba(99, 102, 241, .1)",
            "text": "#818cf8",
            "border": "rgba(99, 102, 241, .3)",
        }
    return seeded.get(normalized_tag, seeded["OTHER"])


def seed_users(session: Session) -> None:
    settings = get_settings()
    session.execute(
        pg_insert(User)
        .values(email=DEMO_USER_ID, password_hash=DEMO_AUTH_DISABLED, role="demo")
        .on_conflict_do_nothing(index_elements=["email"])
    )
    session.execute(
        pg_insert(User)
        .values(
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            role="admin",
        )
        .on_conflict_do_nothing(index_elements=["email"])
    )
    session.commit()


def seed_initial_data(session: Session) -> None:
    if session.scalar(select(func.count()).select_from(Watchlist)) > 0:
        return

    for key, value in SEED_SETTINGS.items():
        session.execute(
            pg_insert(Setting).values(key=key, value=value).on_conflict_do_nothing(index_elements=["key"])
        )

    watchlist_ids: dict[str, int] = {}
    for watchlist in SEED_WATCHLISTS:
        obj = Watchlist(
            slug=watchlist["slug"],
            name=watchlist["name"],
            short_name=watchlist["short_name"],
            category=normalize_category(watchlist.get("category")),
            description=watchlist.get("description", ""),
            currency=watchlist.get("currency", "USD"),
            show_tag=watchlist.get("show_tag", True),
        )
        session.add(obj)
        session.flush()
        watchlist_ids[watchlist["slug"]] = obj.id

    sort_orders: dict[str, int] = {}
    for ticker in SEED_TICKERS:
        watchlist_id = watchlist_ids.get(ticker["watchlist_slug"])
        if watchlist_id is None:
            continue
        sort_order = sort_orders.get(ticker["watchlist_slug"], 0)
        sort_orders[ticker["watchlist_slug"]] = sort_order + 1
        session.add(
            Ticker(
                watchlist_id=watchlist_id,
                symbol=ticker["symbol"],
                name=ticker["name"],
                tag=normalize_tag(ticker.get("tag", "")),
                currency=ticker.get("currency", "USD"),
                sort_order=sort_order,
            )
        )
    session.commit()
    logger.info("seed complete: initial Market Deck data inserted")


def sync_watchlist_tags(session: Session) -> None:
    """Ensure every tag used by a ticker has a watchlist_tags row (with default colors)."""
    session.execute(
        text(r"UPDATE tickers SET tag = UPPER(REGEXP_REPLACE(BTRIM(tag), '\s+', ' ', 'g'))")
    )
    for watchlist_id in session.scalars(select(Watchlist.id).order_by(Watchlist.id)):
        rows = session.execute(
            select(
                Ticker.tag,
                func.min(Ticker.sort_order).label("first_sort"),
                func.min(Ticker.id).label("first_id"),
            )
            .where(Ticker.watchlist_id == watchlist_id, func.btrim(Ticker.tag) != "")
            .group_by(Ticker.tag)
            .order_by("first_sort", "first_id")
        ).all()
        for sort_order, row in enumerate(rows):
            tag = normalize_tag(row.tag)
            colors = tag_color_defaults(tag)
            session.execute(
                pg_insert(WatchlistTag)
                .values(
                    watchlist_id=watchlist_id,
                    tag=tag,
                    bg=colors["bg"],
                    text=colors["text"],
                    border=colors["border"],
                    sort_order=sort_order,
                )
                .on_conflict_do_nothing(index_elements=["watchlist_id", "tag"])
            )
    session.commit()


def run_seed(session: Session) -> None:
    seed_users(session)
    seed_initial_data(session)
    sync_watchlist_tags(session)
