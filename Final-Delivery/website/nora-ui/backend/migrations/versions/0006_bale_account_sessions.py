"""Verified Bale Mini App sessions with one-time initData replay protection.

Revision ID: 0006_bale_account_sessions
Revises: 0005_shared_accounts
Create Date: 2026-10-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_bale_account_sessions"
down_revision = "0005_shared_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_account_sessions_token_hash"),
    )
    op.create_index("ix_account_sessions_expiry", "account_sessions", ["expires_at"], unique=False)

    op.create_table(
        "miniapp_auth_replays",
        sa.Column("replay_key", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("replay_key"),
    )
    op.create_index(
        "ix_miniapp_auth_replays_expiry", "miniapp_auth_replays", ["expires_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_miniapp_auth_replays_expiry", table_name="miniapp_auth_replays")
    op.drop_table("miniapp_auth_replays")
    op.drop_index("ix_account_sessions_expiry", table_name="account_sessions")
    op.drop_table("account_sessions")
