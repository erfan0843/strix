"""Shared account identity foundation for the Nora web app and Bale bot.

Revision ID: 0005_shared_accounts
Revises: 0004_public_site_content
Create Date: 2026-10-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_shared_accounts"
down_revision = "0004_public_site_content"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "platform_identities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_user_id", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "provider_user_id", name="uq_platform_identity_provider_user"
        ),
        sa.UniqueConstraint(
            "account_id", "provider", name="uq_platform_identity_account_provider"
        ),
    )
    op.create_index(
        "ix_platform_identities_account_id", "platform_identities", ["account_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_platform_identities_account_id", table_name="platform_identities")
    op.drop_table("platform_identities")
    op.drop_table("accounts")
