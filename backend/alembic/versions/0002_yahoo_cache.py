"""Add global Yahoo JSON cache.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-04
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "yahoo_cache",
        sa.Column("cache_key", sa.Text(), primary_key=True),
        sa.Column("data", JSONB(), nullable=False),
        sa.Column("cached_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_yahoo_cache_cached_at", "yahoo_cache", ["cached_at"])


def downgrade() -> None:
    op.drop_table("yahoo_cache")
