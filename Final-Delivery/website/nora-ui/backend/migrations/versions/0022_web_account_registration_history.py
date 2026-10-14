"""Link public form responses to a verified web account session.

Revision ID: 0022_web_account_registration_history
Revises: 0021_form_payment_transactions
Create Date: 2026-10-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from backend.migrations.version_table import ensure_postgresql_revision_capacity


revision = "0022_web_account_registration_history"
down_revision = "0021_form_payment_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ensure_postgresql_revision_capacity()
    with op.batch_alter_table("form_response_drafts") as batch:
        batch.add_column(sa.Column("account_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_response_drafts_account",
            "accounts",
            ["account_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "ix_response_drafts_account_updated", ["account_id", "updated_at"]
        )


def downgrade() -> None:
    with op.batch_alter_table("form_response_drafts") as batch:
        batch.drop_index("ix_response_drafts_account_updated")
        batch.drop_constraint("fk_response_drafts_account", type_="foreignkey")
        batch.drop_column("account_id")
