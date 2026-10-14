"""Shared manager inbox tasks and user notification delivery state.

Revision ID: 0008_shared_workflows
Revises: 0007_account_roles
Create Date: 2026-10-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_shared_workflows"
down_revision = "0007_account_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("bale_user_id", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("create_hash", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=120), nullable=True),
        sa.Column("reviewed_by_bale_user_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('profile_review', 'receipt_review')", name="ck_admin_tasks_kind"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'superseded')",
            name="ck_admin_tasks_status",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "kind", "idempotency_key", name="uq_admin_tasks_idempotency"),
    )
    op.create_index(
        "ix_admin_tasks_status_kind_created", "admin_tasks", ["status", "kind", "created_at"], unique=False
    )
    op.create_index(
        "ix_admin_tasks_account_created", "admin_tasks", ["account_id", "created_at"], unique=False
    )

    op.create_table(
        "user_notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("bale_user_id", sa.String(length=40), nullable=False),
        sa.Column("source_task_id", sa.String(length=36), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), server_default="", nullable=False),
        sa.Column("file_refs", sa.JSON(), nullable=False),
        sa.Column("delivery_status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("delivery_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_delivery_error", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "delivery_status IN ('pending', 'delivered', 'failed')",
            name="ck_user_notifications_delivery_status",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_task_id"], ["admin_tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_task_id", "kind", name="uq_user_notifications_task_kind"),
    )
    op.create_index(
        "ix_user_notifications_account_created", "user_notifications", ["account_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_user_notifications_delivery", "user_notifications", ["delivery_status", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_user_notifications_delivery", table_name="user_notifications")
    op.drop_index("ix_user_notifications_account_created", table_name="user_notifications")
    op.drop_table("user_notifications")
    op.drop_index("ix_admin_tasks_account_created", table_name="admin_tasks")
    op.drop_index("ix_admin_tasks_status_kind_created", table_name="admin_tasks")
    op.drop_table("admin_tasks")
