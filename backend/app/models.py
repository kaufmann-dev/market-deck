"""ORM models mirroring the production schema (see alembic/versions/0001_initial.py)."""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'demo')", name="users_role_check"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    short_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False, server_default="Other")
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="USD")
    show_tag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    tickers: Mapped[list["Ticker"]] = relationship(
        back_populates="watchlist",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Ticker.sort_order",
    )
    tags: Mapped[list["WatchlistTag"]] = relationship(
        back_populates="watchlist",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="(WatchlistTag.sort_order, WatchlistTag.tag)",
    )


class Ticker(Base):
    __tablename__ = "tickers"
    __table_args__ = (Index("idx_tickers_watchlist_id", "watchlist_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    tag: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="USD")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    watchlist: Mapped[Watchlist] = relationship(back_populates="tickers")


class WatchlistTag(Base):
    __tablename__ = "watchlist_tags"
    __table_args__ = (
        UniqueConstraint("watchlist_id", "tag", name="watchlist_tags_watchlist_id_tag_key"),
        Index("idx_watchlist_tags_watchlist_id", "watchlist_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False
    )
    tag: Mapped[str] = mapped_column(Text, nullable=False)
    bg: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    border: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    watchlist: Mapped[Watchlist] = relationship(back_populates="tags")


class PriceCache(Base):
    __tablename__ = "price_cache"
    __table_args__ = (Index("idx_price_cache_cached_at", "cached_at"),)

    account_email: Mapped[str] = mapped_column(Text, primary_key=True)
    ticker: Mapped[str] = mapped_column(Text, primary_key=True)
    data: Mapped[list] = mapped_column(JSONB, nullable=False)
    cached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
