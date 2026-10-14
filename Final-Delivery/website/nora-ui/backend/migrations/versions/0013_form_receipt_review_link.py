"""Link a public registration to its shared receipt review task.

Revision ID: 0013_form_receipt_review_link
Revises: 0012_shared_form_tickets
Create Date: 2026-10-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0013_form_receipt_review_link"
down_revision = "0012_shared_form_tickets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "form_responses",
        sa.Column("receipt_review_task_id", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("form_responses", "receipt_review_task_id")
