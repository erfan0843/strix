"""Persistent records for owner-authenticated form definitions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
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
