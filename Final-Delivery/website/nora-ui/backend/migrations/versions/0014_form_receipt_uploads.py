"""Store public-form receipt uploads before the Bale ticket claim.

Revision ID: 0014_form_receipt_uploads
Revises: 0013_form_receipt_review_link
Create Date: 2026-10-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0014_form_receipt_uploads"
down_revision = "0013_form_receipt_review_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "form_receipt_uploads",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("response_id", sa.String(length=36), nullable=False),
        sa.Column("file_name", sa.String(length=120), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("content_size", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "content_size BETWEEN 1 AND 8388608", name="ck_form_receipt_uploads_size"
        ),
        sa.CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png', 'image/webp', 'application/pdf')",
            name="ck_form_receipt_uploads_type",
        ),
        sa.ForeignKeyConstraint(["response_id"], ["form_responses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("response_id", name="uq_form_receipt_uploads_response"),
    )
    op.create_index(
        "ix_form_receipt_uploads_created", "form_receipt_uploads", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_form_receipt_uploads_created", table_name="form_receipt_uploads")
    op.drop_table("form_receipt_uploads")
