"""Add owner-managed username/password login credentials for managers.

Revision ID: 0016_manager_password_login
Revises: 0015_phone_otp_login
Create Date: 2026-10-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0016_manager_password_login"
down_revision = "0015_phone_otp_login"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manager_credentials",
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("username_key", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
        sa.UniqueConstraint("username_key", name="uq_manager_credentials_username"),
    )


def downgrade() -> None:
    op.drop_table("manager_credentials")
