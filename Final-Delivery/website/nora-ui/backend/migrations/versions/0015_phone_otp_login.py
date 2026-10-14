"""Add verified phone OTP challenges and account session provider metadata.

Revision ID: 0015_phone_otp_login
Revises: 0014_form_receipt_uploads
Create Date: 2026-10-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015_phone_otp_login"
down_revision = "0014_form_receipt_uploads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "account_sessions",
        sa.Column("auth_provider", sa.String(length=32), server_default="bale", nullable=False),
    )
    op.create_table(
        "phone_otp_challenges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("phone_hash", sa.String(length=64), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempts >= 0", name="ck_phone_otp_attempts_nonnegative"),
        sa.CheckConstraint("max_attempts BETWEEN 1 AND 10", name="ck_phone_otp_max_attempts"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_phone_otp_phone_created",
        "phone_otp_challenges",
        ["phone_hash", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_phone_otp_expiry",
        "phone_otp_challenges",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_phone_otp_expiry", table_name="phone_otp_challenges")
    op.drop_index("ix_phone_otp_phone_created", table_name="phone_otp_challenges")
    op.drop_table("phone_otp_challenges")
    op.drop_column("account_sessions", "auth_provider")
