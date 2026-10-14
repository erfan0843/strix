"""Store an optional participant note with public-form receipt uploads.

Revision ID: 0019_form_receipt_notes
Revises: 0018_separate_companion_responses
Create Date: 2026-10-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0019_form_receipt_notes"
down_revision = "0018_separate_companion_responses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "form_receipt_uploads",
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
    )
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("form_receipt_uploads", "note", server_default=None)


def downgrade() -> None:
    op.drop_column("form_receipt_uploads", "note")
