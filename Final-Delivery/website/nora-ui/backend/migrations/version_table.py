"""Keep published revision identifiers compatible with PostgreSQL.

Alembic creates a VARCHAR(32) version column, but existing Nora revision IDs
are longer. Widen only that metadata column; never rename a revision, shrink
an existing column, or change application records. The conditional SQL also
works in offline migration scripts and with a non-default search_path.
"""
from __future__ import annotations

from alembic import op


def ensure_postgresql_revision_capacity() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    # PostgreSQL's VARCHAR typmod includes four bytes of bookkeeping. regclass
    # follows the same search_path as Alembic's unqualified version table.
    op.execute(
        """
        DO $nora_version_width$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_catalog.pg_attribute
                WHERE attrelid = 'alembic_version'::regclass
                  AND attname = 'version_num'
                  AND atttypid = 'character varying'::regtype
                  AND atttypmod > 0
                  AND atttypmod < 68
            ) THEN
                ALTER TABLE alembic_version
                    ALTER COLUMN version_num TYPE VARCHAR(64);
            END IF;
        END
        $nora_version_width$;
        """
    )
