"""Server-enforced roles for shared Bale accounts.

Revision ID: 0007_account_roles
Revises: 0006_bale_account_sessions
Create Date: 2026-10-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_account_roles"
down_revision = "0006_bale_account_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_roles",
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("assigned_by", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "role IN ('manager', 'club-supervisor')",
            name="ck_account_roles_assignable_role",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
    )
    op.create_index("ix_account_roles_role", "account_roles", ["role"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_account_roles_role", table_name="account_roles")
    op.drop_table("account_roles")
