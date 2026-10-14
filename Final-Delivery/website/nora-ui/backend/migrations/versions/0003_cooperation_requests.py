"""Durable cooperation request inbox.

Revision ID: 0003_cooperation_requests
Revises: 0002_public_responses
Create Date: 2026-09-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_cooperation_requests"
down_revision = "0002_public_responses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cooperation_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("organization", sa.String(length=180), server_default="", nullable=False),
        sa.Column("contact", sa.String(length=254), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="new", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('new', 'reviewing', 'contacted', 'closed')",
            name="ck_cooperation_requests_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cooperation_requests_created", "cooperation_requests", ["created_at"], unique=False)
    op.create_index(
        "ix_cooperation_requests_status_created",
        "cooperation_requests",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_cooperation_requests_status_created", table_name="cooperation_requests")
    op.drop_index("ix_cooperation_requests_created", table_name="cooperation_requests")
    op.drop_table("cooperation_requests")
