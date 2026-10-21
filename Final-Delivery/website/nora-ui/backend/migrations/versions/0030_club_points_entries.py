"""Read-only mirror of the Bale bot's points ledger for the managers' panel.

The bot's SQLite ``points_ledger`` stays the single source of truth for
club points; this table only stores a verified copy of entries whose owner
resolves server-side through ``platform_identities`` (provider ``bale``).
The bot's stable ``external_key`` (``<source_id>:<ledger_id>``) makes the sync
idempotent; rows are append-only (the ledger itself is immutable). No server
route ever creates, awards or spends points. Additive and fully reversible.

Revision ID: 0030_club_points_entries
Revises: 0029_public_media
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0030_club_points_entries"
down_revision = "0029_public_media"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "club_points_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "account_id", sa.String(length=36),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("bale_user_id", sa.String(length=40), nullable=False),
        sa.Column("external_key", sa.String(length=120), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False, server_default=""),
        sa.Column("ledger_id", sa.Integer(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(length=24), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("ref_key", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("actor_kind", sa.String(length=16), nullable=False, server_default="system"),
        sa.Column("reverses_external_key", sa.String(length=120), nullable=True),
        sa.Column("bot_created_at", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "entry_type IN ('opening_balance', 'award', 'spend', 'refund', 'reversal', 'manual_adjust')",
            name="ck_club_points_entries_entry_type",
        ),
        sa.CheckConstraint("actor_kind IN ('system', 'admin', 'user')", name="ck_club_points_entries_actor_kind"),
        sa.CheckConstraint("ledger_id > 0", name="ck_club_points_entries_ledger_id"),
        sa.CheckConstraint("delta <> 0 OR entry_type = 'opening_balance'", name="ck_club_points_entries_delta"),
        sa.UniqueConstraint("external_key", name="uq_club_points_entries_external_key"),
        sa.UniqueConstraint("source_id", "ledger_id", name="uq_club_points_entries_source_ledger"),
    )
    op.create_index("ix_club_points_entries_account_ledger", "club_points_entries", ["account_id", "ledger_id"])
    op.create_index("ix_club_points_entries_bale_user", "club_points_entries", ["bale_user_id"])
    op.create_index("ix_club_points_entries_type_created", "club_points_entries", ["entry_type", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_club_points_entries_type_created", table_name="club_points_entries")
    op.drop_index("ix_club_points_entries_bale_user", table_name="club_points_entries")
    op.drop_index("ix_club_points_entries_account_ledger", table_name="club_points_entries")
    op.drop_table("club_points_entries")
