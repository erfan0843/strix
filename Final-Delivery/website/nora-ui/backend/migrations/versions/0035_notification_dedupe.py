"""Phase 9.4: idempotent user notifications with an in-app link.

Additive and reversible:

* ``user_notifications.dedupe_key`` (nullable, unique) — stable key per business event
  (``recording_access:<id>:…``, ``certificate:<key>:issued``, …). Rows written before this
  migration keep NULL (several NULLs are allowed by the unique constraint on SQLite and
  PostgreSQL) and are never rewritten.
* ``user_notifications.link`` (nullable) — relative in-app page path; validated in code.

Downgrade drops both columns; existing rows and their delivery state are untouched.

Revision ID: 0035_notification_dedupe
Revises: 0034_private_storage
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0035_notification_dedupe"
down_revision = "0034_private_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user_notifications") as batch:
        batch.add_column(sa.Column("dedupe_key", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("link", sa.String(length=200), nullable=True))
        batch.create_unique_constraint("uq_user_notifications_dedupe_key", ["dedupe_key"])


def downgrade() -> None:
    with op.batch_alter_table("user_notifications") as batch:
        batch.drop_constraint("uq_user_notifications_dedupe_key", type_="unique")
        batch.drop_column("link")
        batch.drop_column("dedupe_key")
