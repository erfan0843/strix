"""Panel «تنظیمات» (1405/08/01): allowlisted owner settings with real server consumers.

Additive and reversible: one small table ``system_settings`` (key → JSON value, who/when).
Only keys listed in ``backend/system_settings.py`` are ever written; secrets never land here.

Revision ID: 0038_system_settings
Revises: 0037_account_status
Create Date: 2026-10-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0038_system_settings"
down_revision = "0037_account_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=80), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(length=120), nullable=False, server_default=""),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
