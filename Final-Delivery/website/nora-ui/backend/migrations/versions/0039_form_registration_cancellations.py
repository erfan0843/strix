"""Cancelled registrations keep an auditable snapshot (1405/08/02).

Until now a rejected receipt (inbox or event file) and the owner's «حذف پاسخ» hard-deleted the
``form_responses`` row: the person's identity and answers, the companions and the web receipt file
vanished, leaving only an orphaned ``form_payments`` row (``response_id`` → NULL) and an audit line.
This revision adds one additive, reversible table that receives an immutable snapshot at that moment
(identity, answers, companions, payment reference, receipt bytes or private-file refs, actor, reason,
source). The live row is still removed, so capacity and the re-registration rule are unchanged.

Revision ID: 0039_form_registration_cancellations
Revises: 0038_system_settings
Create Date: 2026-10-24
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0039_form_registration_cancellations"
down_revision = "0038_system_settings"
branch_labels = None
depends_on = None

JSON_VALUE = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "form_registration_cancellations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("form_id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=120), nullable=True),
        sa.Column("response_id", sa.String(length=36), nullable=False),
        sa.Column("draft_id", sa.String(length=36), nullable=True),
        sa.Column("account_id", sa.String(length=36), nullable=True),
        sa.Column("bale_user_id", sa.String(length=40), nullable=True),
        sa.Column("display_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("status_before", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("ticket_serial", sa.String(length=32), nullable=True),
        sa.Column("form_fields", JSON_VALUE, nullable=False),
        sa.Column("answers", JSON_VALUE, nullable=False),
        sa.Column("companions", JSON_VALUE, nullable=False),
        sa.Column("payment_id", sa.String(length=36), nullable=True),
        sa.Column("payment_method", sa.String(length=32), nullable=True),
        sa.Column("payment_status_before", sa.String(length=24), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("receipt_file_name", sa.String(length=120), nullable=True),
        sa.Column("receipt_content_type", sa.String(length=80), nullable=True),
        sa.Column("receipt_content_size", sa.Integer(), nullable=True),
        sa.Column("receipt_content_hash", sa.String(length=64), nullable=True),
        sa.Column("receipt_content", sa.LargeBinary(), nullable=True),
        sa.Column("receipt_file_refs", JSON_VALUE, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=24), nullable=False, server_default=""),
        sa.Column("actor_kind", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("actor_id", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("actor_role", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_form_reg_cancellations_event_created", "form_registration_cancellations", ["event_id", "created_at"])
    op.create_index("ix_form_reg_cancellations_form_created", "form_registration_cancellations", ["form_id", "created_at"])
    op.create_index("ix_form_reg_cancellations_payment", "form_registration_cancellations", ["payment_id"])
    op.create_index("ix_form_reg_cancellations_response", "form_registration_cancellations", ["response_id"])


def downgrade() -> None:
    op.drop_index("ix_form_reg_cancellations_response", table_name="form_registration_cancellations")
    op.drop_index("ix_form_reg_cancellations_payment", table_name="form_registration_cancellations")
    op.drop_index("ix_form_reg_cancellations_form_created", table_name="form_registration_cancellations")
    op.drop_index("ix_form_reg_cancellations_event_created", table_name="form_registration_cancellations")
    op.drop_table("form_registration_cancellations")
