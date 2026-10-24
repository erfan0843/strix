"""Shared copy of bot-issued certificates for the managers' panel.

The Bale bot remains the issuing system. This table only mirrors rows whose
owner is resolvable server-side through ``platform_identities`` (provider
``bale``); the bot's stable ``external_key`` keeps the sync idempotent. Files
reuse the existing ``private_files`` store. Additive and fully reversible.

Revision ID: 0028_certificates
Revises: 0027_ticket_checkin_account
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028_certificates"
down_revision = "0027_ticket_checkin_account"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "certificates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "account_id", sa.String(length=36),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("bale_user_id", sa.String(length=40), nullable=False),
        sa.Column("external_key", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="bot"),
        sa.Column("source_id", sa.String(length=36), nullable=False, server_default=""),
        sa.Column("legacy_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="issued"),
        sa.Column("serial", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("full_code", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("doc_no", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("person_code", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="event"),
        sa.Column("event_ref", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("event_title", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("title", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("holder_name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("issued_on", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("expires_on", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_by_bale_user_id", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("verify_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "file_id", sa.String(length=36),
            sa.ForeignKey("private_files.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "preview_file_id", sa.String(length=36),
            sa.ForeignKey("private_files.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('issued', 'revoked')", name="ck_certificates_status"),
        sa.CheckConstraint("source IN ('bot', 'bot_legacy')", name="ck_certificates_source"),
        sa.UniqueConstraint("external_key", name="uq_certificates_external_key"),
    )
    op.create_index("ix_certificates_account_created", "certificates", ["account_id", "created_at"])
    op.create_index("ix_certificates_status_created", "certificates", ["status", "created_at"])
    op.create_index("ix_certificates_serial", "certificates", ["serial"])
    op.create_index("ix_certificates_full_code", "certificates", ["full_code"])
    op.create_index("ix_certificates_event_ref", "certificates", ["event_ref"])


def downgrade() -> None:
    op.drop_index("ix_certificates_event_ref", table_name="certificates")
    op.drop_index("ix_certificates_full_code", table_name="certificates")
    op.drop_index("ix_certificates_serial", table_name="certificates")
    op.drop_index("ix_certificates_status_created", table_name="certificates")
    op.drop_index("ix_certificates_account_created", table_name="certificates")
    op.drop_table("certificates")
