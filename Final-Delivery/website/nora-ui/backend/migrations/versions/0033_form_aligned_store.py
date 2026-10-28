"""Phase 9.1: the form builder becomes the commercial source of truth of recorded products.

Additive and reversible:

* ``forms.purpose`` (``registration`` | ``recording_access``, default ``registration``)
  and ``forms.recording_id`` (nullable FK → ``event_recordings``). A form with
  purpose ``recording_access`` is the purchase entry of one recorded product: price,
  payment methods and card destination live in its settings exactly like any paid
  form; the server never turns its responses into tickets/attendance.
* ``recording_orders.form_response_id`` / ``form_payment_id`` (nullable, unique) tie
  the internal ledger row to the form response/payment that produced it.
* ``event_recordings.certificate_policy`` (``none`` | ``manual``; no automatic mode
  because the server has no trusted completion/scoring data).
* ``event_resources.kind`` check widened to ``file | link | youtube | aparat``;
  for the two embed kinds ``link_url`` holds the canonical public URL of the video
  and the embed URL is derived by the server, never stored HTML.

Downgrade folds ``youtube``/``aparat`` resources to ``link`` (URL preserved, still
subject to the same access check) before restoring the old check, then drops the
new columns. Every ``purpose``/``policy`` default equals the pre-9.1 behaviour.

Revision ID: 0033_form_aligned_store
Revises: 0032_recorded_content
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0033_form_aligned_store"
down_revision = "0032_recorded_content"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("forms") as batch:
        batch.add_column(
            sa.Column("purpose", sa.String(length=24), nullable=False, server_default="registration")
        )
        batch.add_column(sa.Column("recording_id", sa.String(length=36), nullable=True))
        batch.create_check_constraint("ck_forms_purpose", "purpose IN ('registration', 'recording_access')")
        batch.create_foreign_key(
            "fk_forms_recording", "event_recordings", ["recording_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index("ix_forms_recording", ["recording_id"])

    with op.batch_alter_table("event_recordings") as batch:
        batch.add_column(
            sa.Column("certificate_policy", sa.String(length=12), nullable=False, server_default="none")
        )
        batch.create_check_constraint(
            "ck_event_recordings_certificate_policy", "certificate_policy IN ('none', 'manual')"
        )

    with op.batch_alter_table("recording_orders") as batch:
        batch.add_column(sa.Column("form_response_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("form_payment_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_recording_orders_form_response", "form_responses", ["form_response_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_foreign_key(
            "fk_recording_orders_form_payment", "form_payments", ["form_payment_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_unique_constraint("uq_recording_orders_form_response", ["form_response_id"])
        batch.create_unique_constraint("uq_recording_orders_form_payment", ["form_payment_id"])

    with op.batch_alter_table("event_resources") as batch:
        batch.drop_constraint("ck_event_resources_kind", type_="check")
        batch.create_check_constraint(
            "ck_event_resources_kind", "kind IN ('file', 'link', 'youtube', 'aparat')"
        )


def downgrade() -> None:
    # Embedded videos keep their canonical URL as a plain link (same access check).
    op.execute("UPDATE event_resources SET kind = 'link' WHERE kind IN ('youtube', 'aparat')")
    with op.batch_alter_table("event_resources") as batch:
        batch.drop_constraint("ck_event_resources_kind", type_="check")
        batch.create_check_constraint("ck_event_resources_kind", "kind IN ('file', 'link')")

    with op.batch_alter_table("recording_orders") as batch:
        batch.drop_constraint("uq_recording_orders_form_payment", type_="unique")
        batch.drop_constraint("uq_recording_orders_form_response", type_="unique")
        batch.drop_constraint("fk_recording_orders_form_payment", type_="foreignkey")
        batch.drop_constraint("fk_recording_orders_form_response", type_="foreignkey")
        batch.drop_column("form_payment_id")
        batch.drop_column("form_response_id")

    with op.batch_alter_table("event_recordings") as batch:
        batch.drop_constraint("ck_event_recordings_certificate_policy", type_="check")
        batch.drop_column("certificate_policy")

    with op.batch_alter_table("forms") as batch:
        batch.drop_index("ix_forms_recording")
        batch.drop_constraint("fk_forms_recording", type_="foreignkey")
        batch.drop_constraint("ck_forms_purpose", type_="check")
        batch.drop_column("recording_id")
        batch.drop_column("purpose")
