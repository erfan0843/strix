"""Phase 8: event resources, Q&A, attendee reviews and content reports.

Events stay inside the versioned ``site_content`` document (stable ``ev-…`` ids);
these four tables hold what must not live in that single public document:
access-controlled files/links (``event_resources``), user questions with the
organizer's answer (``event_questions``), text feedback from verified attendees
(``event_reviews``, no numeric rating) and user reports (``event_content_reports``).

Purely additive: no existing table or column changes. ``event_questions.notification_id``
references the existing ``user_notifications`` outbox (SET NULL) and is the
idempotency anchor of the answer notification. Fully reversible.

Revision ID: 0031_event_interaction
Revises: 0030_club_points_entries
Create Date: 2026-10-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031_event_interaction"
down_revision = "0030_club_points_entries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_resources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False, server_default="file"),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=800), nullable=False, server_default=""),
        sa.Column("access", sa.String(length=16), nullable=False, server_default="public"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("publish_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publisher_label", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("link_url", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("file_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("content_type", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("content_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("content", sa.LargeBinary(), nullable=True),
        sa.Column("created_by_kind", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("created_by_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_reason", sa.String(length=300), nullable=False, server_default=""),
        sa.CheckConstraint("kind IN ('file', 'link')", name="ck_event_resources_kind"),
        sa.CheckConstraint(
            "access IN ('public', 'registered', 'attended', 'staff')", name="ck_event_resources_access"
        ),
        sa.CheckConstraint("status IN ('draft', 'published', 'removed')", name="ck_event_resources_status"),
        sa.CheckConstraint("content_size BETWEEN 0 AND 8388608", name="ck_event_resources_size"),
    )
    op.create_index(
        "ix_event_resources_event_status", "event_resources", ["event_id", "status", "sort_order"]
    )

    op.create_table(
        "event_questions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column(
            "account_id", sa.String(length=36),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("author_label", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("body_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("answer_body", sa.Text(), nullable=False, server_default=""),
        sa.Column("answer_official", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_by_kind", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("answered_by_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("answer_label", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("moderation_reason", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("moderated_by_kind", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("moderated_by_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "notification_id", sa.String(length=36),
            sa.ForeignKey("user_notifications.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('pending', 'published', 'hidden')", name="ck_event_questions_status"),
        sa.UniqueConstraint("event_id", "account_id", "body_hash", name="uq_event_questions_dedupe"),
    )
    op.create_index(
        "ix_event_questions_event_status_created", "event_questions", ["event_id", "status", "created_at"]
    )
    op.create_index("ix_event_questions_account_created", "event_questions", ["account_id", "created_at"])
    op.create_index("ix_event_questions_unanswered", "event_questions", ["answered_at", "status", "created_at"])

    op.create_table(
        "event_reviews",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column(
            "account_id", sa.String(length=36),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "response_id", sa.String(length=36),
            sa.ForeignKey("form_responses.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("author_label", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("verified_attendee", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("edit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("moderation_reason", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("moderated_by_kind", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("moderated_by_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending', 'published', 'hidden', 'withdrawn')", name="ck_event_reviews_status"
        ),
        sa.UniqueConstraint("event_id", "account_id", name="uq_event_reviews_account_event"),
    )
    op.create_index(
        "ix_event_reviews_event_status_created", "event_reviews", ["event_id", "status", "created_at"]
    )

    op.create_table(
        "event_content_reports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("target_kind", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column(
            "reporter_account_id", sa.String(length=36),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("reason", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("resolution_note", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("resolved_by_kind", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("resolved_by_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("target_kind IN ('question', 'review')", name="ck_event_content_reports_kind"),
        sa.CheckConstraint(
            "status IN ('open', 'resolved', 'dismissed')", name="ck_event_content_reports_status"
        ),
        sa.UniqueConstraint(
            "target_kind", "target_id", "reporter_account_id", name="uq_event_content_reports_once"
        ),
    )
    op.create_index(
        "ix_event_content_reports_status_created", "event_content_reports", ["status", "created_at"]
    )
    op.create_index("ix_event_content_reports_event", "event_content_reports", ["event_id"])


def downgrade() -> None:
    op.drop_index("ix_event_content_reports_event", table_name="event_content_reports")
    op.drop_index("ix_event_content_reports_status_created", table_name="event_content_reports")
    op.drop_table("event_content_reports")
    op.drop_index("ix_event_reviews_event_status_created", table_name="event_reviews")
    op.drop_table("event_reviews")
    op.drop_index("ix_event_questions_unanswered", table_name="event_questions")
    op.drop_index("ix_event_questions_account_created", table_name="event_questions")
    op.drop_index("ix_event_questions_event_status_created", table_name="event_questions")
    op.drop_table("event_questions")
    op.drop_index("ix_event_resources_event_status", table_name="event_resources")
    op.drop_table("event_resources")
