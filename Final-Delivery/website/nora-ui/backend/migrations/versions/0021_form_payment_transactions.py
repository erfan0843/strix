"""Record each provider charge once, including duplicate/exceptional charges.

Revision ID: 0021_form_payment_transactions
Revises: 0020_form_payments
Create Date: 2026-10-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0021_form_payment_transactions"
down_revision = "0020_form_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "form_payment_transactions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("payment_id", sa.String(length=36), nullable=False),
        sa.Column("transaction_id", sa.String(length=160), nullable=False),
        sa.Column("provider_charge_id", sa.String(length=160), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("payer_bale_user_id", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="needs_review"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('verified', 'needs_review', 'duplicate')",
            name="ck_form_payment_transactions_status",
        ),
        sa.CheckConstraint("amount BETWEEN 0 AND 2000000000", name="ck_form_payment_transactions_amount"),
        sa.ForeignKeyConstraint(["payment_id"], ["form_payments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_id", name="uq_form_payment_transactions_transaction"),
        sa.UniqueConstraint("provider_charge_id", name="uq_form_payment_transactions_provider_charge"),
    )
    op.create_index(
        "ix_form_payment_transactions_payment_created",
        "form_payment_transactions",
        ["payment_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_form_payment_transactions_payment_created", table_name="form_payment_transactions")
    op.drop_table("form_payment_transactions")
