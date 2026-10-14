"""Persist each companion as an independent form response.

Revision ID: 0018_separate_companion_responses
Revises: 0017_form_companions
Create Date: 2026-10-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from backend.migrations.version_table import ensure_postgresql_revision_capacity

revision = "0018_separate_companion_responses"
down_revision = "0017_form_companions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ensure_postgresql_revision_capacity()
    with op.batch_alter_table("form_responses") as batch:
        batch.add_column(sa.Column("registrant_name", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("registrant_mobile", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("added_by_response_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("companion_index", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("added_by_name", sa.String(length=120), nullable=True))
        batch.create_foreign_key(
            "fk_form_responses_added_by_response",
            "form_responses",
            ["added_by_response_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "ix_form_responses_added_by_response",
            ["added_by_response_id", "companion_index"],
        )
        batch.create_unique_constraint(
            "uq_form_responses_added_by_index",
            ["added_by_response_id", "companion_index"],
        )


def downgrade() -> None:
    with op.batch_alter_table("form_responses") as batch:
        batch.drop_constraint("uq_form_responses_added_by_index", type_="unique")
        batch.drop_index("ix_form_responses_added_by_response")
        batch.drop_constraint("fk_form_responses_added_by_response", type_="foreignkey")
        batch.drop_column("added_by_name")
        batch.drop_column("added_by_response_id")
        batch.drop_column("companion_index")
        batch.drop_column("registrant_mobile")
        batch.drop_column("registrant_name")
