"""Phase 9: recorded-content products of held events, orders and access rights.

Three concepts stay separate: the event and its attendance (``site_content`` +
``form_responses``), the recorded product tied to that event (``event_recordings``
+ ``recording_sessions``) and the right of one account to that product
(``recording_access``), which is created by a verified payment (``recording_orders``),
a free claim or an audited manual grant — never by attendance alone.

``recording_orders`` is deliberately separate from ``form_payments``: that table
requires a form/draft and its finalization creates a registration response, which a
purchase must never do. Additive on existing tables: ``event_resources`` gains
``session_id``/``delivery`` and the access value ``purchased``; ``event_questions``
gains ``session_id``; ``event_reviews`` gains ``badge``. Reversible: the downgrade
folds ``purchased`` resources to ``staff`` (they stay invisible to the public)
before the old check constraint is restored, then drops the new tables.

Revision ID: 0032_recorded_content
Revises: 0031_event_interaction
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0032_recorded_content"
down_revision = "0031_event_interaction"
branch_labels = None
depends_on = None

JSON_VALUE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "event_recordings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("title", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("outcomes", sa.Text(), nullable=False, server_default=""),
        sa.Column("audience", sa.Text(), nullable=False, server_default=""),
        sa.Column("access_terms", sa.Text(), nullable=False, server_default=""),
        sa.Column("refund_policy", sa.Text(), nullable=False, server_default=""),
        sa.Column("faq", JSON_VALUE, nullable=False),
        sa.Column("price", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="IRR"),
        sa.Column("access_days", sa.Integer(), nullable=True),
        sa.Column("attendee_access", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("download_default", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("bale_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("payment_card", JSON_VALUE, nullable=True),
        sa.Column("cover_url", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("status_reason", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by_kind", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("created_by_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("updated_by_kind", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("updated_by_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('draft', 'ready', 'published', 'sales_paused', 'archived')",
            name="ck_event_recordings_status",
        ),
        sa.CheckConstraint("price BETWEEN 0 AND 2000000000", name="ck_event_recordings_price"),
        sa.CheckConstraint(
            "access_days IS NULL OR access_days BETWEEN 1 AND 3650", name="ck_event_recordings_access_days"
        ),
        sa.UniqueConstraint("event_id", name="uq_event_recordings_event"),
    )
    op.create_index("ix_event_recordings_status", "event_recordings", ["status", "published_at"])

    op.create_table(
        "recording_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "recording_id",
            sa.String(length=36),
            sa.ForeignKey("event_recordings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("preview", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft', 'published', 'hidden')", name="ck_recording_sessions_status"),
        sa.CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes BETWEEN 1 AND 6000", name="ck_recording_sessions_duration"
        ),
    )
    op.create_index(
        "ix_recording_sessions_recording_order", "recording_sessions", ["recording_id", "sort_order"]
    )

    op.create_table(
        "recording_orders",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "recording_id",
            sa.String(length=36),
            sa.ForeignKey("event_recordings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id", sa.String(length=36), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="IRR"),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("invoice_payload", sa.String(length=128), nullable=True),
        sa.Column("invoice_url", sa.Text(), nullable=True),
        sa.Column("transaction_id", sa.String(length=160), nullable=True),
        sa.Column("provider_charge_id", sa.String(length=160), nullable=True),
        sa.Column("payer_bale_user_id", sa.String(length=40), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("receipt_content", sa.LargeBinary(), nullable=True),
        sa.Column("receipt_content_type", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("receipt_file_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("receipt_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("receipt_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("receipt_note", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("receipt_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_kind", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("decided_by_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("decision_reason", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("review_note", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("refund_reference", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("method IN ('card_transfer', 'bale_wallet')", name="ck_recording_orders_method"),
        sa.CheckConstraint(
            "status IN ('pending', 'awaiting_receipt', 'receipt_submitted', 'paid', 'paid_manual', "
            "'needs_review', 'rejected', 'cancelled', 'expired', 'refunded')",
            name="ck_recording_orders_status",
        ),
        sa.CheckConstraint("amount BETWEEN 0 AND 2000000000", name="ck_recording_orders_amount"),
        sa.CheckConstraint("receipt_size BETWEEN 0 AND 8388608", name="ck_recording_orders_receipt_size"),
        sa.UniqueConstraint("idempotency_key", name="uq_recording_orders_idempotency"),
        sa.UniqueConstraint("invoice_payload", name="uq_recording_orders_invoice_payload"),
        sa.UniqueConstraint("transaction_id", name="uq_recording_orders_transaction"),
        sa.UniqueConstraint("provider_charge_id", name="uq_recording_orders_provider_charge"),
    )
    op.create_index(
        "ix_recording_orders_recording_status", "recording_orders", ["recording_id", "status", "created_at"]
    )
    op.create_index("ix_recording_orders_account_created", "recording_orders", ["account_id", "created_at"])
    op.create_index("ix_recording_orders_status_created", "recording_orders", ["status", "created_at"])

    op.create_table(
        "recording_access",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "recording_id",
            sa.String(length=36),
            sa.ForeignKey("event_recordings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id", sa.String(length=36), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column(
            "order_id", sa.String(length=36), sa.ForeignKey("recording_orders.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by_kind", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("granted_by_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("reason", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_kind", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("revoked_by_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("revoke_reason", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("source IN ('purchase', 'free', 'granted')", name="ck_recording_access_source"),
        sa.CheckConstraint("status IN ('active', 'expired', 'revoked')", name="ck_recording_access_status"),
        sa.UniqueConstraint("recording_id", "account_id", name="uq_recording_access_account"),
    )
    op.create_index("ix_recording_access_account", "recording_access", ["account_id", "status"])

    # Existing phase-8 tables: additive columns + widened access check.
    with op.batch_alter_table("event_resources") as batch:
        batch.add_column(sa.Column("session_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("delivery", sa.String(length=10), nullable=False, server_default="download"))
        batch.create_foreign_key(
            "fk_event_resources_session", "recording_sessions", ["session_id"], ["id"], ondelete="SET NULL"
        )
        batch.drop_constraint("ck_event_resources_access", type_="check")
        batch.create_check_constraint(
            "ck_event_resources_access",
            "access IN ('public', 'registered', 'attended', 'purchased', 'staff')",
        )
        batch.create_check_constraint("ck_event_resources_delivery", "delivery IN ('download', 'view')")
        batch.create_index("ix_event_resources_session", ["session_id"])
    with op.batch_alter_table("event_questions") as batch:
        batch.add_column(sa.Column("session_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_event_questions_session", "recording_sessions", ["session_id"], ["id"], ondelete="SET NULL"
        )
    with op.batch_alter_table("event_reviews") as batch:
        batch.add_column(sa.Column("badge", sa.String(length=16), nullable=False, server_default=""))


def downgrade() -> None:
    # Purchased-only files must not become public when the access value disappears:
    # fold them to 'staff' (still never served to members) before narrowing the check.
    op.execute("UPDATE event_resources SET access = 'staff' WHERE access = 'purchased'")
    with op.batch_alter_table("event_reviews") as batch:
        batch.drop_column("badge")
    with op.batch_alter_table("event_questions") as batch:
        batch.drop_constraint("fk_event_questions_session", type_="foreignkey")
        batch.drop_column("session_id")
    with op.batch_alter_table("event_resources") as batch:
        batch.drop_index("ix_event_resources_session")
        batch.drop_constraint("ck_event_resources_delivery", type_="check")
        batch.drop_constraint("ck_event_resources_access", type_="check")
        batch.create_check_constraint(
            "ck_event_resources_access", "access IN ('public', 'registered', 'attended', 'staff')"
        )
        batch.drop_constraint("fk_event_resources_session", type_="foreignkey")
        batch.drop_column("delivery")
        batch.drop_column("session_id")
    op.drop_index("ix_recording_access_account", table_name="recording_access")
    op.drop_table("recording_access")
    op.drop_index("ix_recording_orders_status_created", table_name="recording_orders")
    op.drop_index("ix_recording_orders_account_created", table_name="recording_orders")
    op.drop_index("ix_recording_orders_recording_status", table_name="recording_orders")
    op.drop_table("recording_orders")
    op.drop_index("ix_recording_sessions_recording_order", table_name="recording_sessions")
    op.drop_table("recording_sessions")
    op.drop_index("ix_event_recordings_status", table_name="event_recordings")
    op.drop_table("event_recordings")
