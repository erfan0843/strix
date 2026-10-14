"""Initial owner sessions and form-draft tables.

Revision ID: 0001_initial_forms
Revises:
Create Date: 2026-09-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_forms"
down_revision = None
branch_labels = None
depends_on = None

JSON_VALUE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "forms",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("model", sa.String(length=40), nullable=False),
        sa.Column("need", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=True),
        sa.Column("event_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("create_key", sa.String(length=80), nullable=True),
        sa.Column("create_hash", sa.String(length=64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("settings", JSON_VALUE, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'paused', 'archived')",
            name="ck_forms_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "create_key", name="uq_forms_owner_create_key"),
    )
    op.create_index("ix_forms_owner_updated", "forms", ["owner_id", "updated_at"], unique=False)

    op.create_table(
        "form_fields",
        sa.Column("row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("form_id", sa.String(length=36), nullable=False),
        sa.Column("field_key", sa.String(length=80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("field_type", sa.String(length=48), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("config", JSON_VALUE, nullable=False),
        sa.ForeignKeyConstraint(["form_id"], ["forms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("row_id"),
        sa.UniqueConstraint("form_id", "field_key", name="uq_form_fields_key"),
        sa.UniqueConstraint("form_id", "position", name="uq_form_fields_position"),
    )
    op.create_index("ix_form_fields_form_position", "form_fields", ["form_id", "position"], unique=False)

    op.create_table(
        "owner_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=120), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_owner_sessions_expiry", "owner_sessions", ["expires_at"], unique=False)

    op.create_table(
        "login_throttles",
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("key_hash"),
    )


def downgrade() -> None:
    op.drop_table("login_throttles")
    op.drop_index("ix_owner_sessions_expiry", table_name="owner_sessions")
    op.drop_table("owner_sessions")
    op.drop_index("ix_form_fields_form_position", table_name="form_fields")
    op.drop_table("form_fields")
    op.drop_index("ix_forms_owner_updated", table_name="forms")
    op.drop_table("forms")
