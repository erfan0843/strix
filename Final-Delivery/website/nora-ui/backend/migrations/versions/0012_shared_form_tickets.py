"""Persist shared-form ticket delivery and one-time admission state.

Revision ID: 0012_shared_form_tickets
Revises: 0011_bot_form_history
Create Date: 2026-10-01
"""

# ruff: noqa: INP001
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0012_shared_form_tickets"
down_revision = "0011_bot_form_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("form_responses", sa.Column("ticket_serial", sa.String(length=32), nullable=True))
    op.add_column(
        "form_responses",
        sa.Column("ticket_claim_nonce_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "form_responses",
        sa.Column("ticket_claim_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "form_responses",
        sa.Column("ticket_claimed_by_bale_user_id", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "form_responses",
        sa.Column("ticket_claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "form_responses",
        sa.Column("ticket_checked_in_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "form_responses",
        sa.Column("ticket_checked_in_by_bale_user_id", sa.String(length=40), nullable=True),
    )
    op.create_index(
        "uq_form_responses_ticket_serial",
        "form_responses",
        ["ticket_serial"],
        unique=True,
    )
    op.create_index(
        "uq_form_responses_ticket_claim_nonce",
        "form_responses",
        ["ticket_claim_nonce_hash"],
        unique=True,
    )
    op.create_index(
        "ix_form_responses_ticket_claim_expiry",
        "form_responses",
        ["ticket_claim_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_form_responses_ticket_claim_expiry", table_name="form_responses")
    op.drop_index("uq_form_responses_ticket_claim_nonce", table_name="form_responses")
    op.drop_index("uq_form_responses_ticket_serial", table_name="form_responses")
    op.drop_column("form_responses", "ticket_checked_in_by_bale_user_id")
    op.drop_column("form_responses", "ticket_checked_in_at")
    op.drop_column("form_responses", "ticket_claimed_at")
    op.drop_column("form_responses", "ticket_claimed_by_bale_user_id")
    op.drop_column("form_responses", "ticket_claim_expires_at")
    op.drop_column("form_responses", "ticket_claim_nonce_hash")
    op.drop_column("form_responses", "ticket_serial")
