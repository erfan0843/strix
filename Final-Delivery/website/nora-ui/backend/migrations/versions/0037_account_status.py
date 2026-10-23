"""Owner decision 1405/08/01: account status (active/blocked), block reason, staff-only internal note.

Additive and reversible; no row is rewritten:

* ``accounts.status`` — ``active`` (server default, so every existing account stays active) or
  ``blocked``. A blocked account cannot open a session through any provider (phone OTP, Bale
  mini-app, manager password), an existing session stops resolving, and every authenticated
  write (registration, questions, …) is refused with ``account_blocked``.
* ``accounts.blocked_reason`` / ``blocked_at`` / ``blocked_by`` — mandatory reason + who/when;
  staff-facing only.
* ``accounts.internal_note`` / ``note_updated_at`` / ``note_updated_by`` — free text for staff with
  ``us_view``; never part of a member-facing or public payload.

Downgrade drops the seven columns (the audit trail keeps the block/unblock/note events).

Revision ID: 0037_account_status
Revises: 0036_upload_sessions
Create Date: 2026-10-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0037_account_status"
down_revision = "0036_upload_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.add_column(sa.Column("status", sa.String(length=16), nullable=False, server_default="active"))
        batch.add_column(sa.Column("blocked_reason", sa.String(length=500), nullable=False, server_default=""))
        batch.add_column(sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("blocked_by", sa.String(length=120), nullable=False, server_default=""))
        batch.add_column(sa.Column("internal_note", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("note_updated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("note_updated_by", sa.String(length=120), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch:
        batch.drop_column("note_updated_by")
        batch.drop_column("note_updated_at")
        batch.drop_column("internal_note")
        batch.drop_column("blocked_by")
        batch.drop_column("blocked_at")
        batch.drop_column("blocked_reason")
        batch.drop_column("status")
