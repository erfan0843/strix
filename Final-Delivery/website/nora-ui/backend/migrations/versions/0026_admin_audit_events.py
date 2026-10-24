"""Append-only audit trail for administrative actions (no secret material).

Revision ID: 0026_admin_audit_events
Revises: 0025_service_checks
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026_admin_audit_events"
down_revision = "0025_service_checks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_audit_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("actor_kind", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=120), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("target_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("outcome", sa.String(length=32), nullable=False, server_default="ok"),
        sa.Column(
            "details",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.CheckConstraint(
            "actor_kind IN ('owner', 'account')",
            name="ck_admin_audit_events_actor_kind",
        ),
    )
    op.create_index("ix_admin_audit_events_created", "admin_audit_events", ["created_at"])
    op.create_index(
        "ix_admin_audit_events_action_created", "admin_audit_events", ["action", "created_at"]
    )
    op.create_index(
        "ix_admin_audit_events_target", "admin_audit_events", ["target_type", "target_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_admin_audit_events_target", table_name="admin_audit_events")
    op.drop_index("ix_admin_audit_events_action_created", table_name="admin_audit_events")
    op.drop_index("ix_admin_audit_events_created", table_name="admin_audit_events")
    op.drop_table("admin_audit_events")
