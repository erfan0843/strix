"""Owner-published public site content snapshot.

Revision ID: 0004_public_site_content
Revises: 0003_cooperation_requests
Create Date: 2026-09-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_public_site_content"
down_revision = "0003_cooperation_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_content",
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("site_content")
