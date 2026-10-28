"""Phase 9.4: event resource bytes may live in the private storage outside the web root.

Additive and reversible:

* ``event_resources.storage_key`` (nullable, server-made key ``YYYY/MM/<hex>``). NULL means the
  legacy inline ``content`` (≤ 8 MiB) is authoritative; a key means the bytes are in
  ``NORA_PRIVATE_STORAGE_DIR`` and ``content`` is NULL. Access checks are unchanged: every read
  still goes through ``GET /api/public/events/{id}/resources/{rid}/download``.
* ``ck_event_resources_size`` is widened: the 8 MiB cap keeps applying to inline rows only; rows
  with a ``storage_key`` are bounded by the storage cap enforced while streaming.

Downgrade restores the strict 8 MiB check and drops the column. That is only possible when no row
holds more than 8 MiB on disk — the downgrade refuses otherwise instead of destroying rows. Files
already on disk are NOT deleted by the migration (an operator decision with its own audit); rows
that pointed to disk lose their bytes for the old code path, which is exactly why
``deployment/PRIVATE-STORAGE-OPERATIONS.fa.md`` asks for a verified file snapshot before any
downgrade.

Revision ID: 0034_private_storage
Revises: 0033_form_aligned_store
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0034_private_storage"
down_revision = "0033_form_aligned_store"
branch_labels = None
depends_on = None


INLINE_MAX = 8 * 1024 * 1024


def upgrade() -> None:
    with op.batch_alter_table("event_resources") as batch:
        batch.add_column(sa.Column("storage_key", sa.String(length=80), nullable=True))
        batch.drop_constraint("ck_event_resources_size", type_="check")
        batch.create_check_constraint(
            "ck_event_resources_size",
            f"content_size >= 0 AND (storage_key IS NOT NULL OR content_size <= {INLINE_MAX})",
        )


def downgrade() -> None:
    bind = op.get_bind()
    oversized = bind.execute(
        sa.text("SELECT COUNT(*) FROM event_resources WHERE content_size > :cap"), {"cap": INLINE_MAX}
    ).scalar()
    if oversized:
        raise RuntimeError(
            f"{oversized} event_resources rows exceed 8 MiB and live in the private store; "
            "move or remove them deliberately before downgrading (no automatic deletion)."
        )
    with op.batch_alter_table("event_resources") as batch:
        batch.drop_constraint("ck_event_resources_size", type_="check")
        batch.create_check_constraint("ck_event_resources_size", f"content_size BETWEEN 0 AND {INLINE_MAX}")
        batch.drop_column("storage_key")
