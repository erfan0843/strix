"""Phase 9.5: resumable uploads, operations markers, one-shot content announcements.

Additive and reversible:

* ``upload_sessions`` — one row per resumable upload of a file resource (random id bound to the
  actor, expected size/sha256, received bytes, status machine
  ``open → completing → completed | aborted | expired | failed``). The staged bytes live in the
  private storage's ``.incoming`` directory; the row only records what the server verified.
* ``system_markers`` — key/value markers written by server jobs/CLIs (last backup verify,
  last scheduled-publish run) and read by the health endpoints.
* ``event_resources.announced_at`` — set exactly once when the "new content" notification for
  a resource is queued (immediately or by the scheduled-publish announcer), so a restart or a
  second run never announces twice. Existing rows keep NULL and are treated as "not announced";
  the announcer only considers rows that went live after this migration (see
  ``backend/scheduled_publish.py``).

Downgrade drops the two tables and the column; event resources and their bytes are untouched.
Open upload sessions lose their bookkeeping — their ``.part`` files stay on disk and show up as
stale parts in ``tools/private-storage-backup.py verify`` (an operator decision, never deleted
by the migration).

Revision ID: 0036_upload_sessions
Revises: 0035_notification_dedupe
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0036_upload_sessions"
down_revision = "0035_notification_dedupe"
branch_labels = None
depends_on = None

JSON_VALUE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("resource_id", sa.String(length=36), sa.ForeignKey("event_resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("owner_kind", sa.String(length=16), nullable=False),
        sa.Column("owner_id", sa.String(length=120), nullable=False),
        sa.Column("part_id", sa.String(length=32), nullable=False, unique=True),
        sa.Column("declared_name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("expected_size", sa.BigInteger(), nullable=False),
        sa.Column("expected_sha256", sa.String(length=64), nullable=True),
        sa.Column("received_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("error_code", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("storage_key", sa.String(length=80), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('open', 'completing', 'completed', 'aborted', 'expired', 'failed')",
            name="ck_upload_sessions_status",
        ),
        sa.CheckConstraint(
            "expected_size > 0 AND received_bytes >= 0 AND received_bytes <= expected_size",
            name="ck_upload_sessions_bytes",
        ),
    )
    op.create_index("ix_upload_sessions_resource_status", "upload_sessions", ["resource_id", "status"])
    op.create_index("ix_upload_sessions_expires", "upload_sessions", ["expires_at"])
    op.create_table(
        "system_markers",
        sa.Column("key", sa.String(length=80), primary_key=True),
        sa.Column("value", JSON_VALUE, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table("event_resources") as batch:
        batch.add_column(sa.Column("announced_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("event_resources") as batch:
        batch.drop_column("announced_at")
    op.drop_table("system_markers")
    op.drop_index("ix_upload_sessions_expires", table_name="upload_sessions")
    op.drop_index("ix_upload_sessions_resource_status", table_name="upload_sessions")
    op.drop_table("upload_sessions")
