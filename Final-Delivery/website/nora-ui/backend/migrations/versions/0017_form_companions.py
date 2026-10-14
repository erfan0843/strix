"""Persist companion identities and their independent form answers.

Revision ID: 0017_form_companions
Revises: 0016_manager_password_login
Create Date: 2026-10-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0017_form_companions"
down_revision = "0016_manager_password_login"
branch_labels = None
depends_on = None

JSON_VALUE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column(
        "form_response_drafts",
        sa.Column("companions", JSON_VALUE, nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "form_responses",
        sa.Column("companions", JSON_VALUE, nullable=False, server_default=sa.text("'[]'")),
    )
    with op.batch_alter_table("form_response_drafts") as batch:
        batch.alter_column("companions", server_default=None)
    with op.batch_alter_table("form_responses") as batch:
        batch.alter_column("companions", server_default=None)


def downgrade() -> None:
    op.drop_column("form_responses", "companions")
    op.drop_column("form_response_drafts", "companions")
