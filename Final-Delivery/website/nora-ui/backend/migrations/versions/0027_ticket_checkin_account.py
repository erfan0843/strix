"""Record which web-panel account performed a ticket check-in.

The Bale bot already stores ``ticket_checked_in_by_bale_user_id``; the managers'
panel now shares the same attendance columns and needs to name its own actor
without pretending to be a Bale id. Additive and reversible: one nullable column.

Revision ID: 0027_ticket_checkin_account
Revises: 0026_admin_audit_events
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0027_ticket_checkin_account"
down_revision = "0026_admin_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("form_responses") as batch:
        batch.add_column(sa.Column("ticket_checked_in_by_account_id", sa.String(length=36), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("form_responses") as batch:
        batch.drop_column("ticket_checked_in_by_account_id")
