"""Initial schema — matches the production database as created by the legacy server.py.

Revision ID: 0001
Revises:
Create Date: 2026-07-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('admin', 'demo')", name="users_role_check"),
    )
    op.create_table(
        "settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )
    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("short_name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False, server_default="Other"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("currency", sa.Text(), nullable=False, server_default="USD"),
        sa.Column("show_tag", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_table(
        "tickers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "watchlist_id",
            sa.Integer(),
            sa.ForeignKey("watchlists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("tag", sa.Text(), nullable=False, server_default=""),
        sa.Column("currency", sa.Text(), nullable=False, server_default="USD"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("idx_tickers_watchlist_id", "tickers", ["watchlist_id"])
    op.create_table(
        "watchlist_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "watchlist_id",
            sa.Integer(),
            sa.ForeignKey("watchlists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tag", sa.Text(), nullable=False),
        sa.Column("bg", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("border", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("watchlist_id", "tag", name="watchlist_tags_watchlist_id_tag_key"),
    )
    op.create_index("idx_watchlist_tags_watchlist_id", "watchlist_tags", ["watchlist_id"])
    op.create_table(
        "price_cache",
        sa.Column("account_email", sa.Text(), primary_key=True),
        sa.Column("ticker", sa.Text(), primary_key=True),
        sa.Column("data", JSONB(), nullable=False),
        sa.Column("cached_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_price_cache_cached_at", "price_cache", ["cached_at"])


def downgrade() -> None:
    op.drop_table("price_cache")
    op.drop_table("watchlist_tags")
    op.drop_table("tickers")
    op.drop_table("watchlists")
    op.drop_table("settings")
    op.drop_table("users")
