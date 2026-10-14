"""Private shared attachment storage for profile and receipt reviews.

Revision ID: 0010_private_files
Revises: 0009_workflow_projection
Create Date: 2026-10-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_private_files"
down_revision = "0009_workflow_projection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "private_files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("bale_user_id", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=120), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("content_size", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("content_size BETWEEN 1 AND 8388608", name="ck_private_files_size"),
        sa.CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png', 'image/webp', 'application/pdf')",
            name="ck_private_files_content_type",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["admin_tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "idempotency_key", name="uq_private_files_idempotency"),
    )
    op.create_index("ix_private_files_account_created", "private_files", ["account_id", "created_at"], unique=False)
    op.create_index("ix_private_files_task", "private_files", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_private_files_task", table_name="private_files")
    op.drop_index("ix_private_files_account_created", table_name="private_files")
    op.drop_table("private_files")
