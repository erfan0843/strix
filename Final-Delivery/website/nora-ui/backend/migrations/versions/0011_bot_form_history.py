"""Associate conversational bot responses with their Bale account for history.

Revision ID: 0011_bot_form_history
Revises: 0010_private_files
Create Date: 2026-10-01
"""

# ruff: noqa: INP001
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0011_bot_form_history"
down_revision = "0010_private_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "form_response_drafts",
        sa.Column("bot_bale_user_id", sa.String(length=40), nullable=True),
    )
    op.create_index(
        "ix_response_drafts_bot_bale_user",
        "form_response_drafts",
        ["bot_bale_user_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_response_drafts_bot_bale_user",
        table_name="form_response_drafts",
    )
    op.drop_column("form_response_drafts", "bot_bale_user_id")
