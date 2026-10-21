"""Persistent records for owner-authenticated form definitions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


JSON_VALUE = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class FormRecord(Base):
    __tablename__ = "forms"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'paused', 'archived')",
            name="ck_forms_status",
        ),
        UniqueConstraint("owner_id", "create_key", name="uq_forms_owner_create_key"),
        Index("ix_forms_owner_updated", "owner_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    model: Mapped[str] = mapped_column(String(40), nullable=False)
    need: Mapped[str] = mapped_column(String(40), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(180), nullable=True)
    event_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    create_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    create_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    fields: Mapped[list["FormFieldRecord"]] = relationship(
        back_populates="form",
        cascade="all, delete-orphan",
        order_by="FormFieldRecord.position",
        lazy="selectin",
    )


class FormFieldRecord(Base):
    __tablename__ = "form_fields"
    __table_args__ = (
        UniqueConstraint("form_id", "field_key", name="uq_form_fields_key"),
        UniqueConstraint("form_id", "position", name="uq_form_fields_position"),
        Index("ix_form_fields_form_position", "form_id", "position"),
    )

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    form_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("forms.id", ondelete="CASCADE"), nullable=False
    )
    field_key: Mapped[str] = mapped_column(String(80), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    field_type: Mapped[str] = mapped_column(String(48), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False, default=dict)

    form: Mapped[FormRecord] = relationship(back_populates="fields")


class OwnerSessionRecord(Base):
    __tablename__ = "owner_sessions"
    __table_args__ = (Index("ix_owner_sessions_expiry", "expires_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(120), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LoginThrottleRecord(Base):
    __tablename__ = "login_throttles"

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FormResponseDraftRecord(Base):
    """Anonymous, browser-capability-protected draft for one published form."""

    __tablename__ = "form_response_drafts"
    __table_args__ = (
        UniqueConstraint("form_id", "token_hash", name="uq_response_drafts_form_token"),
        Index("ix_response_drafts_expiry", "expires_at"),
        Index("ix_response_drafts_form_updated", "form_id", "updated_at"),
        Index("ix_response_drafts_bot_bale_user", "bot_bale_user_id", "updated_at"),
        Index("ix_response_drafts_account_updated", "account_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    form_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("forms.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    form_version: Mapped[int] = mapped_column(Integer, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    bot_bale_user_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    answers: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False, default=dict)
    companions: Mapped[list[dict[str, Any]]] = mapped_column(JSON_VALUE, nullable=False, default=list)
    has_unsaved_changes: Mapped[bool] = mapped_column(nullable=False, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    form: Mapped[FormRecord] = relationship()
    response: Mapped["FormResponseRecord | None"] = relationship(
        back_populates="draft", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )


class FormResponseRecord(Base):
    """Durable answer set in the same forms repository; never a delivery job."""

    __tablename__ = "form_responses"
    __table_args__ = (
        CheckConstraint("status IN ('accepted', 'waitlisted')", name="ck_form_responses_status"),
        UniqueConstraint("draft_id", name="uq_form_responses_draft"),
        UniqueConstraint("ticket_serial", name="uq_form_responses_ticket_serial"),
        UniqueConstraint("ticket_claim_nonce_hash", name="uq_form_responses_ticket_claim_nonce"),
        Index("ix_form_responses_form_created", "form_id", "created_at"),
        Index("ix_form_responses_form_status", "form_id", "status"),
        Index("ix_form_responses_ticket_claim_expiry", "ticket_claim_expires_at"),
        Index("ix_form_responses_added_by_response", "added_by_response_id", "companion_index"),
        UniqueConstraint(
            "added_by_response_id", "companion_index", name="uq_form_responses_added_by_index"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    form_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("forms.id", ondelete="CASCADE"), nullable=False
    )
    draft_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("form_response_drafts.id", ondelete="CASCADE"), nullable=False
    )
    form_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    answers: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False, default=dict)
    companions: Mapped[list[dict[str, Any]]] = mapped_column(JSON_VALUE, nullable=False, default=list)
    registrant_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    registrant_mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    added_by_response_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("form_responses.id", ondelete="SET NULL"), nullable=True
    )
    companion_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    added_by_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    form_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False, default=dict)
    ticket_serial: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ticket_claim_nonce_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ticket_claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ticket_claimed_by_bale_user_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ticket_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ticket_checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ticket_checked_in_by_bale_user_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ticket_checked_in_by_account_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    receipt_review_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    draft: Mapped[FormResponseDraftRecord] = relationship(back_populates="response")
    receipt_upload: Mapped["FormReceiptUploadRecord | None"] = relationship(
        back_populates="response", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )


class FormReceiptUploadRecord(Base):
    """Temporary receipt uploaded through the anonymous public-form session."""

    __tablename__ = "form_receipt_uploads"
    __table_args__ = (
        UniqueConstraint("response_id", name="uq_form_receipt_uploads_response"),
        CheckConstraint("content_size BETWEEN 1 AND 8388608", name="ck_form_receipt_uploads_size"),
        CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png', 'image/webp', 'application/pdf')",
            name="ck_form_receipt_uploads_type",
        ),
        Index("ix_form_receipt_uploads_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    response_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("form_responses.id", ondelete="CASCADE"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(120), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    response: Mapped[FormResponseRecord] = relationship(back_populates="receipt_upload")


class PublicWriteThrottleRecord(Base):
    """Minute window keyed only by an HMAC of form ID and client IP."""

    __tablename__ = "public_write_throttles"
    __table_args__ = (Index("ix_public_write_throttles_window", "window_started_at"),)

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SiteContentRecord(Base):
    """Owner-managed public content snapshot consumed by the static UI."""

    __tablename__ = "site_content"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PaymentSecretRecord(Base):
    """Owner-entered provider secret, stored encrypted (see secret_box.py)."""

    __tablename__ = "payment_secrets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    hint: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ServiceCheckRecord(Base):
    """Last real connection test for one service credential (no secret material)."""

    __tablename__ = "service_checks"

    storage_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ok: Mapped[bool] = mapped_column(nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CooperationRequestRecord(Base):
    """Private, durable inbox entry submitted through the public cooperation form."""

    __tablename__ = "cooperation_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'reviewing', 'contacted', 'closed')",
            name="ck_cooperation_requests_status",
        ),
        Index("ix_cooperation_requests_created", "created_at"),
        Index("ix_cooperation_requests_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    organization: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    contact: Mapped[str] = mapped_column(String(254), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AccountRecord(Base):
    """Canonical account shared by the web app and verified platform identities."""

    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    identities: Mapped[list["PlatformIdentityRecord"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        order_by="PlatformIdentityRecord.created_at",
        lazy="selectin",
    )
    sessions: Mapped[list["AccountSessionRecord"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
        order_by="AccountSessionRecord.created_at",
        lazy="selectin",
    )


class PlatformIdentityRecord(Base):
    """A verified external account identifier; never a login credential."""

    __tablename__ = "platform_identities"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_user_id", name="uq_platform_identity_provider_user"
        ),
        UniqueConstraint(
            "account_id", "provider", name="uq_platform_identity_account_provider"
        ),
        Index("ix_platform_identities_account_id", "account_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    account: Mapped[AccountRecord] = relationship(back_populates="identities")


class AccountSessionRecord(Base):
    """Revocable server-side session for a verified platform account."""

    __tablename__ = "account_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_account_sessions_token_hash"),
        Index("ix_account_sessions_expiry", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    auth_provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="bale", server_default="bale"
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped[AccountRecord] = relationship(back_populates="sessions")


class AccountRoleRecord(Base):
    """Single server-assigned administrative role for a shared account.

    The owner remains the separately authenticated system owner; account roles
    are limited to manager and club supervisor and cannot promote an account
    to owner.
    """

    __tablename__ = "account_roles"
    __table_args__ = (
        CheckConstraint(
            "role IN ('manager', 'club-supervisor')",
            name="ck_account_roles_assignable_role",
        ),
        Index("ix_account_roles_role", "role"),
    )

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ManagerCredentialRecord(Base):
    """Owner-provisioned password credential for an already role-assigned account."""

    __tablename__ = "manager_credentials"
    __table_args__ = (
        UniqueConstraint("username_key", name="uq_manager_credentials_username"),
    )

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    username_key: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MiniAppAuthReplayRecord(Base):
    """One-time HMAC fingerprint consumed during Mini App account login."""

    __tablename__ = "miniapp_auth_replays"
    __table_args__ = (Index("ix_miniapp_auth_replays_expiry", "expires_at"),)

    replay_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PhoneOTPChallengeRecord(Base):
    """One-time phone-login challenge; stores HMAC digests, never the code or phone."""

    __tablename__ = "phone_otp_challenges"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="ck_phone_otp_attempts_nonnegative"),
        CheckConstraint("max_attempts BETWEEN 1 AND 10", name="ck_phone_otp_max_attempts"),
        Index("ix_phone_otp_phone_created", "phone_hash", "created_at"),
        Index("ix_phone_otp_expiry", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdminTaskRecord(Base):
    """Durable approval task shared by the website and the bot inbox."""

    __tablename__ = "admin_tasks"
    __table_args__ = (
        CheckConstraint("kind IN ('profile_review', 'receipt_review')", name="ck_admin_tasks_kind"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'superseded')",
            name="ck_admin_tasks_status",
        ),
        UniqueConstraint("account_id", "kind", "idempotency_key", name="uq_admin_tasks_idempotency"),
        Index("ix_admin_tasks_status_kind_created", "status", "kind", "created_at"),
        Index("ix_admin_tasks_account_created", "account_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    bale_user_id: Mapped[str] = mapped_column(String(40), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    create_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    projection_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    projection_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_projection_error: Mapped[str | None] = mapped_column(String(160), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reviewed_by_bale_user_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserNotificationRecord(Base):
    """User-facing notification/outbox record; delivery is acknowledged by the bot."""

    __tablename__ = "user_notifications"
    __table_args__ = (
        CheckConstraint(
            "delivery_status IN ('pending', 'delivered', 'failed')",
            name="ck_user_notifications_delivery_status",
        ),
        Index("ix_user_notifications_account_created", "account_id", "created_at"),
        Index("ix_user_notifications_delivery", "delivery_status", "created_at"),
        UniqueConstraint("source_task_id", "kind", name="uq_user_notifications_task_kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    bale_user_id: Mapped[str] = mapped_column(String(40), nullable=False)
    source_task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("admin_tasks.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    file_refs: Mapped[list[Any]] = mapped_column(JSON_VALUE, nullable=False, default=list)
    delivery_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    delivery_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_delivery_error: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FormPaymentRecord(Base):
    """Idempotent payment intent and provider settlement for one public form draft."""

    __tablename__ = "form_payments"
    __table_args__ = (
        CheckConstraint(
            "method IN ('card_transfer', 'bale_wallet')",
            name="ck_form_payments_method",
        ),
        CheckConstraint(
            "status IN ('pending', 'paid', 'paid_review', 'awaiting_receipt', 'receipt_submitted', 'paid_manual', 'rejected', 'cancelled', 'expired')",
            name="ck_form_payments_status",
        ),
        CheckConstraint("amount BETWEEN 0 AND 2000000000", name="ck_form_payments_amount"),
        UniqueConstraint("invoice_payload", name="uq_form_payments_invoice_payload"),
        UniqueConstraint("idempotency_key", name="uq_form_payments_idempotency"),
        UniqueConstraint("transaction_id", name="uq_form_payments_transaction"),
        UniqueConstraint("provider_charge_id", name="uq_form_payments_provider_charge"),
        UniqueConstraint("response_id", name="uq_form_payments_response"),
        Index("ix_form_payments_form_status_expiry", "form_id", "status", "expires_at"),
        Index("ix_form_payments_draft_created", "draft_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    form_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("forms.id", ondelete="CASCADE"), nullable=False
    )
    draft_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("form_response_drafts.id", ondelete="CASCADE"), nullable=False
    )
    response_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("form_responses.id", ondelete="SET NULL"), nullable=True
    )
    form_version: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="IRR")
    party_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    selection: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False, default=dict)
    invoice_payload: Mapped[str | None] = mapped_column(String(128), nullable=True)
    invoice_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    transaction_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    provider_charge_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    payer_bale_user_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class FormPaymentTransactionRecord(Base):
    """Provider callbacks retained once per charge, including duplicates needing review."""

    __tablename__ = "form_payment_transactions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('verified', 'needs_review', 'duplicate')",
            name="ck_form_payment_transactions_status",
        ),
        CheckConstraint("amount BETWEEN 0 AND 2000000000", name="ck_form_payment_transactions_amount"),
        UniqueConstraint("transaction_id", name="uq_form_payment_transactions_transaction"),
        UniqueConstraint("provider_charge_id", name="uq_form_payment_transactions_provider_charge"),
        Index("ix_form_payment_transactions_payment_created", "payment_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("form_payments.id", ondelete="CASCADE"), nullable=False
    )
    transaction_id: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_charge_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    payer_bale_user_id: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="needs_review")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PrivateFileRecord(Base):
    """Privately stored attachment uploaded by the trusted bot service."""

    __tablename__ = "private_files"
    __table_args__ = (
        CheckConstraint("content_size BETWEEN 1 AND 8388608", name="ck_private_files_size"),
        CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png', 'image/webp', 'application/pdf')",
            name="ck_private_files_content_type",
        ),
        UniqueConstraint("account_id", "idempotency_key", name="uq_private_files_idempotency"),
        Index("ix_private_files_account_created", "account_id", "created_at"),
        Index("ix_private_files_task", "task_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("admin_tasks.id", ondelete="SET NULL"), nullable=True
    )
    bale_user_id: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str] = mapped_column(String(120), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PublicMediaRecord(Base):
    """Public image uploaded from the managers' panel for events/articles.

    Stored in the shared database exactly like ``private_files`` (no filesystem
    paths, no client-chosen names). Served read-only at ``/api/public/media/{id}``;
    ``site_content`` only keeps that stable URL. Deduplicated by content hash.
    """

    __tablename__ = "public_media"
    __table_args__ = (
        CheckConstraint("content_size BETWEEN 1 AND 3145728", name="ck_public_media_size"),
        CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="ck_public_media_content_type",
        ),
        UniqueConstraint("content_hash", name="uq_public_media_hash"),
        Index("ix_public_media_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    uploaded_by_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    uploaded_by_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CertificateRecord(Base):
    """Certificate issued by the Bale bot, mirrored to the shared server for the managers' panel.

    The bot stays the issuing system; this table is a verified copy whose owner
    is resolved server-side from the Bale user id through ``platform_identities``
    (never from a client-sent account id). ``external_key`` is the bot's stable
    identity for the row (``<source_id>:<legacy_id>``) and makes sync idempotent.
    Rows whose owner has no server identity are not stored here at all.
    """

    __tablename__ = "certificates"
    __table_args__ = (
        CheckConstraint("status IN ('issued', 'revoked')", name="ck_certificates_status"),
        CheckConstraint("source IN ('bot', 'bot_legacy')", name="ck_certificates_source"),
        UniqueConstraint("external_key", name="uq_certificates_external_key"),
        Index("ix_certificates_account_created", "account_id", "created_at"),
        Index("ix_certificates_status_created", "status", "created_at"),
        Index("ix_certificates_serial", "serial"),
        Index("ix_certificates_full_code", "full_code"),
        Index("ix_certificates_event_ref", "event_ref"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    bale_user_id: Mapped[str] = mapped_column(String(40), nullable=False)
    external_key: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="bot")
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="issued")
    serial: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    full_code: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    doc_no: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    person_code: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="event")
    event_ref: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    event_title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    holder_name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    issued_on: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    expires_on: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_by_bale_user_id: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    verify_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("private_files.id", ondelete="SET NULL"), nullable=True
    )
    preview_file_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("private_files.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AccountProfileRecord(Base):
    """Member-entered profile fields; one row per verified platform account."""

    __tablename__ = "account_profiles"

    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    fields: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )



class AdminAuditEventRecord(Base):
    """Append-only trail of administrative actions (who did what, to which record, when).

    Stores identifiers and outcomes only. Secret values, passwords, tokens and
    uploaded content never enter ``details``; callers pass a small whitelisted
    dictionary and :func:`backend.audit.record_admin_event` drops any key that
    looks like credential material.
    """

    __tablename__ = "admin_audit_events"
    __table_args__ = (
        CheckConstraint(
            "actor_kind IN ('owner', 'account')",
            name="ck_admin_audit_events_actor_kind",
        ),
        Index("ix_admin_audit_events_created", "created_at"),
        Index("ix_admin_audit_events_action_created", "action", "created_at"),
        Index("ix_admin_audit_events_target", "target_type", "target_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    target_id: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="ok")
    details: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False, default=dict)


class ClubPointsEntryRecord(Base):
    """Read-only mirror of one row of the Bale bot's points ledger.

    The bot's ``points_ledger`` is the single source of truth; this copy exists
    so the managers' panel can show history without a second write path. The
    owner is resolved server-side from the Bale user id through
    ``platform_identities`` (never from a client-sent account id); entries of
    people without a server identity are not stored. ``external_key`` is the
    bot's stable identity (``<source_id>:<ledger_id>``) and makes sync
    idempotent. Rows are append-only: a differing payload for an existing key
    is rejected, mirroring the ledger's own immutability.
    """

    __tablename__ = "club_points_entries"
    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('opening_balance', 'award', 'spend', 'refund', 'reversal', 'manual_adjust')",
            name="ck_club_points_entries_entry_type",
        ),
        CheckConstraint("actor_kind IN ('system', 'admin', 'user')", name="ck_club_points_entries_actor_kind"),
        CheckConstraint("ledger_id > 0", name="ck_club_points_entries_ledger_id"),
        CheckConstraint("delta <> 0 OR entry_type = 'opening_balance'", name="ck_club_points_entries_delta"),
        UniqueConstraint("external_key", name="uq_club_points_entries_external_key"),
        UniqueConstraint("source_id", "ledger_id", name="uq_club_points_entries_source_ledger"),
        Index("ix_club_points_entries_account_ledger", "account_id", "ledger_id"),
        Index("ix_club_points_entries_bale_user", "bale_user_id"),
        Index("ix_club_points_entries_type_created", "entry_type", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    bale_user_id: Mapped[str] = mapped_column(String(40), nullable=False)
    external_key: Mapped[str] = mapped_column(String(120), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    ledger_id: Mapped[int] = mapped_column(Integer, nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    ref_key: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="system")
    reverses_external_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bot_created_at: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ── فاز ۸: منابع، پرسش‌وپاسخ، دیدگاه و گزارش محتوای رویداد ──
# Events themselves stay in the versioned ``site_content`` document (``ev-…`` ids);
# these row tables hold user-generated or access-controlled content that must not
# live inside that single public document (per-row ACL, PII, concurrent writes).

EVENT_RESOURCE_CONTENT_TYPES = (
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/zip",
    "audio/mpeg",
    "text/plain",
)
EVENT_RESOURCE_MAX_BYTES = 8388608


class EventResourceRecord(Base):
    """File or link published for one event with a server-enforced access level.

    Binary content is stored in the shared database exactly like ``private_files``
    and ``public_media`` (no filesystem path, no client-chosen storage name), so
    path traversal is impossible by construction. ``access`` is evaluated by the
    download endpoint against the caller's real registration/attendance rows;
    the public snapshot never contains the bytes or a bypassable direct URL.
    Removal is logical (``status='removed'``) so event history stays intact.
    """

    __tablename__ = "event_resources"
    __table_args__ = (
        CheckConstraint("kind IN ('file', 'link')", name="ck_event_resources_kind"),
        CheckConstraint(
            "access IN ('public', 'registered', 'attended', 'staff')",
            name="ck_event_resources_access",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'removed')", name="ck_event_resources_status"
        ),
        CheckConstraint("content_size BETWEEN 0 AND 8388608", name="ck_event_resources_size"),
        Index("ix_event_resources_event_status", "event_id", "status", "sort_order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False, default="file")
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(String(800), nullable=False, default="")
    access: Mapped[str] = mapped_column(String(16), nullable=False, default="public")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publisher_label: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    link_url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    file_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    content_type: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    content_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_by_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    created_by_id: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    removed_reason: Mapped[str] = mapped_column(String(300), nullable=False, default="")


class EventQuestionRecord(Base):
    """One question asked by a signed-in account about one event, plus the organizer's answer.

    Ownership comes from the server session (``account_id``); the browser never
    names the author. ``author_label`` is a display snapshot (profile name or a
    neutral label) so the public API never exposes phone numbers or account ids.
    ``body_hash`` blocks exact duplicates per event/account. ``notification_id``
    is the idempotency anchor for the answer notification: one outbox row per
    answer, retries re-queue that same row instead of inserting another.
    """

    __tablename__ = "event_questions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'published', 'hidden')", name="ck_event_questions_status"
        ),
        UniqueConstraint("event_id", "account_id", "body_hash", name="uq_event_questions_dedupe"),
        Index("ix_event_questions_event_status_created", "event_id", "status", "created_at"),
        Index("ix_event_questions_account_created", "account_id", "created_at"),
        Index("ix_event_questions_unanswered", "answered_at", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(100), nullable=False)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    author_label: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    body_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    answer_body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer_official: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_by_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    answered_by_id: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    answer_label: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    moderation_reason: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    moderated_by_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    moderated_by_id: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notification_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user_notifications.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class EventReviewRecord(Base):
    """Text feedback from a verified attendee of one event (no numeric rating).

    Eligibility is decided server-side from the attendee's own ``form_responses``
    row (``ticket_checked_in_at``); ``response_id`` records which attendance
    qualified the review. One review per account and event (DB unique → a
    concurrent duplicate fails). Submitting and being shown publicly are two
    distinct states (``pending`` → ``published``); hiding keeps the row and
    records the actor and reason; the author may withdraw without deleting it.
    """

    __tablename__ = "event_reviews"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'published', 'hidden', 'withdrawn')",
            name="ck_event_reviews_status",
        ),
        UniqueConstraint("event_id", "account_id", name="uq_event_reviews_account_event"),
        Index("ix_event_reviews_event_status_created", "event_id", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(100), nullable=False)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    response_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("form_responses.id", ondelete="SET NULL"), nullable=True
    )
    author_label: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    verified_attendee: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    edit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moderation_reason: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    moderated_by_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    moderated_by_id: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class EventContentReportRecord(Base):
    """A signed-in user's report of an inappropriate question or review; handled in the panel."""

    __tablename__ = "event_content_reports"
    __table_args__ = (
        CheckConstraint("target_kind IN ('question', 'review')", name="ck_event_content_reports_kind"),
        CheckConstraint(
            "status IN ('open', 'resolved', 'dismissed')", name="ck_event_content_reports_status"
        ),
        UniqueConstraint(
            "target_kind", "target_id", "reporter_account_id", name="uq_event_content_reports_once"
        ),
        Index("ix_event_content_reports_status_created", "status", "created_at"),
        Index("ix_event_content_reports_event", "event_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(100), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reporter_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    resolution_note: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    resolved_by_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    resolved_by_id: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
