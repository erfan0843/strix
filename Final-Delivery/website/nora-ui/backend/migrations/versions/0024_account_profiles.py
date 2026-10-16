"""Store member profile fields entered on the account page.

Revision ID: 0024_account_profiles
Revises: 0023_payment_secrets
Create Date: 2026-10-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024_account_profiles"
down_revision = "0023_payment_secrets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_profiles",
        sa.Column(
            "account_id",
            sa.String(length=36),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("account_profiles")
