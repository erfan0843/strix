"""Public images uploaded from the managers' panel (event posters, article covers).

Additive and fully reversible. Content lives in the shared database like
``private_files``; ``site_content`` stores only the stable public URL.

Revision ID: 0029_public_media
Revises: 0028_certificates
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0029_public_media"
down_revision = "0028_certificates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_media",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("content_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("height", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("file_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("uploaded_by_kind", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("uploaded_by_id", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("content_size BETWEEN 1 AND 3145728", name="ck_public_media_size"),
        sa.CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="ck_public_media_content_type",
        ),
        sa.UniqueConstraint("content_hash", name="uq_public_media_hash"),
    )
    op.create_index("ix_public_media_created", "public_media", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_public_media_created", table_name="public_media")
    op.drop_table("public_media")
