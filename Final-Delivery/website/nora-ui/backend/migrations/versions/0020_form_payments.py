"""Create shared, idempotent form payment intents.

Revision ID: 0020_form_payments
Revises: 0019_form_receipt_notes
Create Date: 2026-10-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0020_form_payments"
down_revision = "0019_form_receipt_notes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "form_payments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("form_id", sa.String(length=36), nullable=False),
        sa.Column("draft_id", sa.String(length=36), nullable=False),
        sa.Column("response_id", sa.String(length=36), nullable=True),
        sa.Column("form_version", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="IRR"),
        sa.Column("party_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("selection", sa.JSON(), nullable=False),
        sa.Column("invoice_payload", sa.String(length=128), nullable=True),
        sa.Column("invoice_url", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("transaction_id", sa.String(length=160), nullable=True),
        sa.Column("provider_charge_id", sa.String(length=160), nullable=True),
        sa.Column("payer_bale_user_id", sa.String(length=40), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "method IN ('card_transfer', 'bale_wallet')", name="ck_form_payments_method"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'paid_review', 'awaiting_receipt', 'receipt_submitted', 'paid_manual', 'rejected', 'cancelled', 'expired')",
            name="ck_form_payments_status",
        ),
        sa.CheckConstraint("amount BETWEEN 0 AND 2000000000", name="ck_form_payments_amount"),
        sa.ForeignKeyConstraint(["form_id"], ["forms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["draft_id"], ["form_response_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["response_id"], ["form_responses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_payload", name="uq_form_payments_invoice_payload"),
        sa.UniqueConstraint("idempotency_key", name="uq_form_payments_idempotency"),
        sa.UniqueConstraint("transaction_id", name="uq_form_payments_transaction"),
        sa.UniqueConstraint("provider_charge_id", name="uq_form_payments_provider_charge"),
        sa.UniqueConstraint("response_id", name="uq_form_payments_response"),
    )
    op.create_index(
        "ix_form_payments_form_status_expiry",
        "form_payments",
        ["form_id", "status", "expires_at"],
    )
    op.create_index(
        "ix_form_payments_draft_created", "form_payments", ["draft_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_form_payments_draft_created", table_name="form_payments")
    op.drop_index("ix_form_payments_form_status_expiry", table_name="form_payments")
    op.drop_table("form_payments")
