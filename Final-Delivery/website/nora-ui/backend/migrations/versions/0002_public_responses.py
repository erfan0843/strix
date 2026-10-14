"""Published forms, anonymous server drafts, and durable form responses.

Revision ID: 0002_public_responses
Revises: 0001_initial_forms
Create Date: 2026-09-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_public_responses"
down_revision = "0001_initial_forms"
branch_labels = None
depends_on = None

JSON_VALUE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "form_response_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("form_id", sa.String(length=36), nullable=False),
        sa.Column("form_version", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("answers", JSON_VALUE, nullable=False),
        sa.Column("has_unsaved_changes", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["form_id"], ["forms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("form_id", "token_hash", name="uq_response_drafts_form_token"),
    )
    op.create_index("ix_response_drafts_expiry", "form_response_drafts", ["expires_at"], unique=False)
    op.create_index("ix_response_drafts_form_updated", "form_response_drafts", ["form_id", "updated_at"], unique=False)

    op.create_table(
        "form_responses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("form_id", sa.String(length=36), nullable=False),
        sa.Column("draft_id", sa.String(length=36), nullable=False),
        sa.Column("form_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("answers", JSON_VALUE, nullable=False),
        sa.Column("form_snapshot", JSON_VALUE, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('accepted', 'waitlisted')", name="ck_form_responses_status"),
        sa.ForeignKeyConstraint(["form_id"], ["forms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["draft_id"], ["form_response_drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draft_id", name="uq_form_responses_draft"),
    )
    op.create_index("ix_form_responses_form_created", "form_responses", ["form_id", "created_at"], unique=False)
    op.create_index("ix_form_responses_form_status", "form_responses", ["form_id", "status"], unique=False)

    op.create_table(
        "public_write_throttles",
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key_hash"),
    )
    op.create_index(
        "ix_public_write_throttles_window", "public_write_throttles", ["window_started_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_public_write_throttles_window", table_name="public_write_throttles")
    op.drop_table("public_write_throttles")
    op.drop_index("ix_form_responses_form_status", table_name="form_responses")
    op.drop_index("ix_form_responses_form_created", table_name="form_responses")
    op.drop_table("form_responses")
    op.drop_index("ix_response_drafts_form_updated", table_name="form_response_drafts")
    op.drop_index("ix_response_drafts_expiry", table_name="form_response_drafts")
    op.drop_table("form_response_drafts")
