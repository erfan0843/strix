"""Record the outcome of real service-connection tests.

Revision ID: 0025_service_checks
Revises: 0024_account_profiles
Create Date: 2026-10-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_service_checks"
down_revision = "0024_account_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_checks",
        sa.Column("storage_id", sa.String(length=32), primary_key=True),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False, server_default=""),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("service_checks")
