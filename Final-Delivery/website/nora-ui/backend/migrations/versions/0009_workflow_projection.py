"""Track bot-side effects for decisions made in either client.

Revision ID: 0009_workflow_projection
Revises: 0008_shared_workflows
Create Date: 2026-10-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0009_workflow_projection"
down_revision = "0008_shared_workflows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("admin_tasks") as batch_op:
        batch_op.add_column(
            sa.Column("projection_status", sa.String(length=16), server_default="pending", nullable=False)
        )
        batch_op.add_column(
            sa.Column("projection_attempts", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(sa.Column("last_projection_error", sa.String(length=160), nullable=True))
        batch_op.create_check_constraint(
            "ck_admin_tasks_projection_status",
            "projection_status IN ('pending', 'applied', 'failed')",
        )


def downgrade() -> None:
    with op.batch_alter_table("admin_tasks") as batch_op:
        batch_op.drop_constraint("ck_admin_tasks_projection_status", type_="check")
        batch_op.drop_column("last_projection_error")
        batch_op.drop_column("projection_attempts")
        batch_op.drop_column("projection_status")
