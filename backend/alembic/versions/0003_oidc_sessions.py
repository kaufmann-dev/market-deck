"""Replace local users with OIDC-backed application sessions.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-20
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("token_hash", sa.String(length=64), primary_key=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("id_token", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'demo')", name="auth_sessions_role_check"),
        sa.CheckConstraint(
            "(role = 'admin' AND subject IS NOT NULL AND id_token IS NOT NULL) OR "
            "(role = 'demo' AND subject IS NULL AND display_name IS NULL AND id_token IS NULL)",
            name="auth_sessions_identity_check",
        ),
    )
    op.create_index("idx_auth_sessions_last_seen_at", "auth_sessions", ["last_seen_at"])
    op.create_index(
        "idx_auth_sessions_absolute_expires_at",
        "auth_sessions",
        ["absolute_expires_at"],
    )
    op.alter_column("price_cache", "account_email", new_column_name="account_key")
    op.drop_table("users")


def downgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('admin', 'demo')", name="users_role_check"),
    )
    op.alter_column("price_cache", "account_key", new_column_name="account_email")
    op.drop_table("auth_sessions")
