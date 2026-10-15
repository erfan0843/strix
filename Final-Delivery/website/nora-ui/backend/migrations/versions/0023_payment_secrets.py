"""Store owner-entered payment provider secrets encrypted at rest.

Revision ID: 0023_payment_secrets
Revises: 0022_web_account_registration_history
Create Date: 2026-10-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0023_payment_secrets"
down_revision = "0022_web_account_registration_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_secrets",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("hint", sa.String(length=16), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("payment_secrets")
