"""FastAPI host for Nora UI, owner form publishing, and anonymous responses.

This is one application: the same ASGI process serves the UI and its API.
No provider is enabled by default: phone OTP can call Safir only when its
server-side settings are present, and Bale Mini App/payment/bot integrations
are opt-in. General outbound dispatch remains disabled.
"""

from __future__ import annotations

import asyncio
import base64
import csv
import hashlib
import io
import hmac
import html
import json
import logging
import os
import re
import secrets
import sys
import tempfile
import unicodedata
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, replace as dataclass_replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator, Iterator, Literal, Mapping, Sequence, TypedDict, cast
from urllib.parse import quote, unquote, urlsplit

from starlette.requests import ClientDisconnect
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import and_, case, create_engine, delete, func, or_, select, text, update
from sqlalchemy.engine import CursorResult, Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload, sessionmaker
from sqlalchemy.sql.elements import ColumnElement
from starlette.middleware.gzip import GZipMiddleware

from .accounts import get_or_create_bale_account, get_or_create_phone_account, phone_account_exists
from .captcha import CAPTCHA_TTL_SECONDS, CaptchaError, captcha_nonce, issue_captcha, verify_captcha
from .bale_payments import BalePaymentAPIError, call_bale_payment_api, validated_invoice_url
from . import data_staging as data_staging_mod
from . import audit as audit_mod
from . import certificates as certificates_mod
from . import notifications as notifications_mod
from . import club_points as club_points_mod
from . import public_media as public_media_mod
from . import content_admin as content_admin_mod
from . import event_interaction as interaction_mod
from . import recordings as recordings_mod
from . import event_reminders as event_reminders_mod
from . import system_settings as system_settings_mod
from . import scheduled_publish as scheduled_publish_mod
from . import integrity as integrity_mod
from . import upload_sessions as upload_mod
from . import event_time
from . import service_settings as service_settings_mod
from .service_probe import probe_bale_bot
from .config import UI_ROOT, Settings
from . import storage as storage_mod
from .financials import (
    PaymentConfigurationError,
    calculate_payment_amount,
    normalize_financial_config,
    normalize_payment_methods,
)
from .form_capabilities import public_form_capabilities
from .models import (
    AccountProfileRecord,
    AccountRecord,
    AccountRoleRecord,
    AccountSessionRecord,
    CertificateRecord,
    AdminAuditEventRecord,
    AdminTaskRecord,
    Base,
    CooperationRequestRecord,
    EventContentReportRecord,
    EventQuestionRecord,
    EventRecordingRecord,
    EventResourceRecord,
    EventReviewRecord,
    FormFieldRecord,
    FormPaymentRecord,
    FormPaymentTransactionRecord,
    FormReceiptUploadRecord,
    FormRecord,
    FormResponseDraftRecord,
    FormResponseRecord,
    LoginThrottleRecord,
    ManagerCredentialRecord,
    MiniAppAuthReplayRecord,
    OwnerSessionRecord,
    PlatformIdentityRecord,
    PhoneOTPChallengeRecord,
    PrivateFileRecord,
    PublicMediaRecord,
    PublicWriteThrottleRecord,
    RecordingAccessRecord,
    RecordingOrderRecord,
    RecordingSessionRecord,
    SiteContentRecord,
    SystemMarkerRecord,
    UploadSessionRecord,
    UserNotificationRecord,
)
from .otp import (
    generate_otp_code,
    normalize_iran_phone,
    otp_digest,
    phone_digest,
    send_safir_otp,
)
from .responses import (
    AnswerValidationError,
    public_form_data,
    publication_issues,
    purchase_form_price,
    purchase_form_selection,
    response_snapshot,
    validate_answers,
    validate_companions,
    visible_field_ids,
)
from .roles import (
    ROLE_KEYS,
    ROLE_OWNER,
    has_permission,
    is_assignable_role,
    permissions_for_role,
)
from .schemas import PayloadError, normalize_form_payload
from .security import (
    BaleMiniAppIdentity,
    constant_time_equal,
    hash_password,
    new_token,
    throttle_digest,
    token_digest,
    verify_bale_mini_app_init_data,
    verify_password,
)
from .seo import (
    ORGANIZATION_NAME,
    SITE_NAME,
    absolute_asset_url,
    apply_page_metadata,
    canonical_path,
    canonical_url,
    default_page_description,
    dynamic_page_values,
    robots_txt,
    sitemap_xml,
    structured_data,
)
from .site_content import (
    CONTENT_KEYS,
    SiteContentError,
    _public_record as is_public_content_row,
    public_site_content,
    resolve_public_delivery_file,
    NON_PUBLIC_RETAINED_KEYS,
    retain_non_public_rows,
    sanitize_site_content,
)


_PUBLIC_SUFFIXES = {
    ".html", ".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".webp",
    ".ico", ".woff", ".woff2", ".ttf", ".otf", ".webmanifest", ".mp3", ".mp4", ".xml", ".txt",
}
_BLOCKED_PREFIXES = ("backend/", "tests/", "__pycache__/")
_BLOCKED_NAMES = {".env", ".env.local", "server.mjs", "integrations.mjs"}
_OUTBOX_POLICY = {
    "certificate": ["bale"],
    "ticket": ["bale"],
    "notification": ["bale", "eitaa"],
}
_OUTBOX_KINDS = set(_OUTBOX_POLICY)
_SECRET_FIELD = re.compile(r"token|secret|authorization|api[_-]?key|password|credential", re.I)
_BOT_FORM_USER_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
_BOT_FORM_SESSION_KEY = re.compile(r"[A-Za-z0-9_-]{32,128}\Z")
_BOT_FORM_RESPONSE_ID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z"
)
_MANAGER_USERNAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{2,63}")
_BOT_FORM_HISTORY_PAGE_SIZE = 6


def _contains_secret_key(value: Any, depth: int = 0) -> bool:
    if depth > 12:
        return True
    if isinstance(value, dict):
        return any(
            _SECRET_FIELD.search(str(key)) or _contains_secret_key(child, depth + 1)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_secret_key(child, depth + 1) for child in value)
    return False


def _private_file_type(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def _form_payment_webhook_token(settings: Settings) -> str:
    """Derive a dedicated, non-guessable webhook path without exposing the secret."""
    return hmac.new(
        settings.form_payment_webhook_secret.encode("utf-8"),
        settings.form_payment_bot_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _form_payment_registered_webhook_url(settings: Settings) -> str:
    return (
        settings.form_payment_webhook_url.rstrip("/")
        + "/"
        + _form_payment_webhook_token(settings)
    )


@dataclass(frozen=True)
class OwnerIdentity:
    session_id: str
    owner_id: str
    csrf_hash: str


@dataclass(frozen=True)
class AccountIdentity:
    session_id: str
    account_id: str
    csrf_hash: str
    role: str | None = None
    owner_id: str = ""
    provider: str = "bale"


def record_audit(
    db: Session,
    identity: "OwnerIdentity | AccountIdentity",
    action: str,
    *,
    target_type: str = "",
    target_id: str = "",
    outcome: str = "ok",
    details: Mapping[str, Any] | None = None,
) -> None:
    """Append an audit row for the acting owner/manager (committed with the caller)."""
    if isinstance(identity, OwnerIdentity):
        audit_mod.record_admin_event(
            db, actor_kind=audit_mod.ACTOR_OWNER, actor_id=identity.owner_id, actor_role=ROLE_OWNER,
            action=action, target_type=target_type, target_id=target_id, outcome=outcome, details=details,
        )
        return
    audit_mod.record_admin_event(
        db, actor_kind=audit_mod.ACTOR_ACCOUNT, actor_id=identity.account_id, actor_role=identity.role or "",
        action=action, target_type=target_type, target_id=target_id, outcome=outcome, details=details,
    )


def _runtime_settings(db: Session, cfg: Settings) -> Settings:
    """Settings as the web process must use them right now.

    ``app.state.settings`` is the raw environment snapshot. Every path that
    depends on a credential or on a readiness flag derived from one (mini-app
    auth, OTP, payment readiness, invoice creation, webhook path and secret)
    reads through this overlay so a value saved in the encrypted store is the
    operative value, not merely a stored one.
    """
    return service_settings_mod.effective_settings(db, cfg)



def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _touch_login_rate_limit(
    db: Session,
    key_hash: str,
    now: datetime,
    *,
    limit: int,
    window: timedelta,
) -> int:
    """Count an authentication attempt without persisting its IP or phone."""
    record = db.get(LoginThrottleRecord, key_hash)
    if record is not None and record.blocked_until and _as_utc(record.blocked_until) > now:
        return max(1, int((_as_utc(record.blocked_until) - now).total_seconds()))
    if record is None:
        record = LoginThrottleRecord(key_hash=key_hash, failures=0, window_started_at=now)
        db.add(record)
    elif now - _as_utc(record.window_started_at) >= window:
        record.failures = 0
        record.window_started_at = now
        record.blocked_until = None
    if record.failures >= limit:
        record.blocked_until = now + window
        return max(1, int(window.total_seconds()))
    record.failures += 1
    if record.failures >= limit:
        record.blocked_until = now + window
    return 0


def _manager_username_key(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not _MANAGER_USERNAME.fullmatch(candidate):
        return None
    return candidate.lower()


def _revoke_manager_password_sessions(db: Session, account_id: str, now: datetime) -> None:
    db.execute(
        update(AccountSessionRecord)
        .where(
            AccountSessionRecord.account_id == account_id,
            AccountSessionRecord.auth_provider == "manager-password",
            AccountSessionRecord.revoked_at.is_(None),
        )
        .values(revoked_at=now)
        .execution_options(synchronize_session=False)
    )


# ── Owner decision 1405/08/01: account status (active/blocked) ──────────────────────────────
# One rule, enforced where identity is resolved: a blocked account never gets a session (any
# provider), an existing session stops resolving, and bot-side registration for a Bale id that
# belongs to a blocked account is refused. Hiding buttons is not access control.
ACCOUNT_STATUS_ACTIVE = "active"
ACCOUNT_STATUS_BLOCKED = "blocked"
ACCOUNT_STATUSES = (ACCOUNT_STATUS_ACTIVE, ACCOUNT_STATUS_BLOCKED)
ACCOUNT_BLOCKED_DETAIL = {"code": "account_blocked"}
_BLOCK_REASON_MIN = 3
_BLOCK_REASON_MAX = 500
_INTERNAL_NOTE_MAX = 2000


def _account_is_blocked(db: Session, account_id: str | None) -> bool:
    if not account_id:
        return False
    account = db.get(AccountRecord, account_id)
    return account is not None and account.status == ACCOUNT_STATUS_BLOCKED


def _bale_user_is_blocked(db: Session, bale_user_id: str | None) -> bool:
    if not bale_user_id:
        return False
    identity = db.scalar(
        select(PlatformIdentityRecord).where(
            PlatformIdentityRecord.provider == "bale",
            PlatformIdentityRecord.provider_user_id == str(bale_user_id),
        )
    )
    return identity is not None and _account_is_blocked(db, identity.account_id)


def _revoke_all_account_sessions(db: Session, account_id: str, now: datetime) -> int:
    result = db.execute(
        update(AccountSessionRecord)
        .where(AccountSessionRecord.account_id == account_id, AccountSessionRecord.revoked_at.is_(None))
        .values(revoked_at=now)
        .execution_options(synchronize_session=False)
    )
    return int(cast(CursorResult[Any], result).rowcount or 0)


def _account_status_view(account: AccountRecord) -> dict[str, Any]:
    """Staff-facing status block (``us_view``); never part of a member/public payload."""
    return {
        "status": account.status or ACCOUNT_STATUS_ACTIVE,
        "blocked_reason": account.blocked_reason or "",
        "blocked_at": _as_utc(account.blocked_at).isoformat() if account.blocked_at else None,
        "blocked_by": account.blocked_by or "",
        "internal_note": account.internal_note or "",
        "note_updated_at": _as_utc(account.note_updated_at).isoformat() if account.note_updated_at else None,
        "note_updated_by": account.note_updated_by or "",
    }


def _new_engine(database_url: str) -> Engine:
    # psycopg 3 is the installed PostgreSQL driver; normalize the common URL form.
    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in database_url:
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool
    return create_engine(database_url, **kwargs)


def _json_response(status: int, error: str, message: str | None = None) -> JSONResponse:
    value: dict[str, Any] = {"error": error}
    if message:
        value["message"] = message
    return JSONResponse(value, status_code=status)


CSP_REPORT_PATH = "/api/csp-report"
CSP_REPORT_MAX_BYTES = 16 * 1024
csp_logger = logging.getLogger("nora.csp")


def _csp_report_summary(body: dict[str, Any]) -> dict[str, str]:
    """Keep only what an operator needs to tune ``frame-src``; strip anything identifying."""
    def origin_only(value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        parsed = urlsplit(text)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return text.split("?", 1)[0][:80]  # keyword values such as ``inline`` / ``eval`` / ``data``
    def path_only(value: object) -> str:
        parsed = urlsplit(str(value or ""))
        return (parsed.path or "/")[:160]
    directive = str(body.get("effective-directive") or body.get("effectiveDirective")
                    or body.get("violated-directive") or body.get("violatedDirective") or "")[:80]
    return {
        "directive": directive,
        "blocked": origin_only(body.get("blocked-uri") or body.get("blockedURL") or body.get("blockedURI")),
        "document": path_only(body.get("document-uri") or body.get("documentURL") or body.get("documentURI")),
        "disposition": str(body.get("disposition") or "")[:16],
    }


async def _read_json_object(request: Request, max_bytes: int) -> dict[str, Any]:
    declared = request.headers.get("content-length")
    if declared:
        try:
            if int(declared) > max_bytes:
                raise HTTPException(413, "request_too_large")
        except ValueError:
            raise HTTPException(400, "invalid_content_length") from None
    raw = await request.body()
    if len(raw) > max_bytes:
        raise HTTPException(413, "request_too_large")
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(415, "application_json_required")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(400, "invalid_json") from None
    if not isinstance(value, dict):
        raise HTTPException(400, "invalid_json_object")
    return value


def _same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    host = request.headers.get("host")
    if not origin:
        # برخی مرورگرها روی پاسخ‌های با Referrer-Policy سخت‌گیرانه Origin را نمی‌فرستند؛
        # در آن حالت Referer باید دقیقاً همین میزبان باشد. نبود هر دو همچنان رد می‌شود.
        referer = request.headers.get("referer")
        if not referer:
            raise HTTPException(403, "same_origin_required")
        try:
            ref = urlsplit(referer)
        except ValueError:
            raise HTTPException(403, "same_origin_required") from None
        if ref.scheme not in {"http", "https"} or not ref.netloc:
            raise HTTPException(403, "same_origin_required")
        origin = f"{ref.scheme}://{ref.netloc}"
    if not host:
        raise HTTPException(403, "same_origin_required")
    try:
        parsed = urlsplit(origin)
    except ValueError:
        raise HTTPException(403, "same_origin_required") from None
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != host.lower():
        raise HTTPException(403, "same_origin_required")


def _cooperation_text(value: Any, field: str, maximum: int, *, minimum: int = 0) -> str:
    if not isinstance(value, str):
        raise HTTPException(422, {"code": "invalid_cooperation_request", "field": field})
    text_value = value.strip()
    if len(text_value) < minimum or len(text_value) > maximum:
        raise HTTPException(422, {"code": "invalid_cooperation_request", "field": field})
    if any(ord(char) < 32 and char not in "\n\r\t" for char in text_value):
        raise HTTPException(422, {"code": "invalid_cooperation_request", "field": field})
    return text_value


def _cooperation_contact(value: Any) -> str:
    contact = _cooperation_text(value, "contact", 254, minimum=5)
    if "@" in contact:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", contact):
            raise HTTPException(422, {"code": "invalid_cooperation_request", "field": "contact"})
        return contact
    normalized = contact.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    compact = re.sub(r"[\s().-]", "", normalized)
    if not re.fullmatch(r"\+?\d{8,15}", compact):
        raise HTTPException(422, {"code": "invalid_cooperation_request", "field": "contact"})
    return contact


def _cooperation_request_dict(record: CooperationRequestRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "organization": record.organization,
        "contact": record.contact,
        "kind": record.kind,
        "message": record.message,
        "status": record.status,
        "created_at": _as_utc(record.created_at).isoformat(),
        "updated_at": _as_utc(record.updated_at).isoformat(),
    }


def _field_dict(field: FormFieldRecord) -> dict[str, Any]:
    return {"id": field.field_key, "t": field.field_type, "l": field.label, **(field.config or {})}


def _samesite(cfg: Settings) -> Literal["lax", "strict", "none"]:
    value = str(getattr(cfg, "cookie_samesite", "strict") or "strict").lower()
    if value == "lax":
        return "lax"
    if value == "none" and bool(cfg.cookie_secure):
        return "none"
    return "strict"


class _CookieOptions(TypedDict):
    secure: bool
    samesite: Literal["lax", "strict", "none"]
    path: str
    max_age: int


def _json_dict_member(source: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = source.get(key)
    return value if isinstance(value, dict) else {}


def _json_list_member(source: Mapping[str, Any], key: str) -> list[Any]:
    value = source.get(key)
    return value if isinstance(value, list) else []


def _form_dict(form: FormRecord | None) -> dict[str, Any]:
    if form is None:
        raise HTTPException(404, "form_not_found")
    return {
        "id": form.id,
        "name": form.title,
        "model": form.model,
        "need": form.need,
        "slug": form.slug or "",
        "ev": form.event_id or "",
        "purpose": form.purpose or "registration",
        "recording_id": form.recording_id if form.purpose == "recording_access" else None,
        "fields": [_field_dict(field) for field in form.fields],
        "settings": form.settings or {},
        "status": form.status,
        "version": form.version,
        "created_at": _as_utc(form.created_at).isoformat(),
        "updated_at": _as_utc(form.updated_at).isoformat(),
    }


def _snapshot_purpose(record: FormResponseRecord) -> str:
    snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
    return "recording_access" if snapshot.get("purpose") == "recording_access" else "registration"


def _form_is_purchase(form: FormRecord) -> bool:
    return form.purpose == "recording_access"


def _form_ticket_eligible(record: FormResponseRecord) -> bool:
    snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
    return (
        record.status == "accepted"
        and snapshot.get("model") == "registration"
        and snapshot.get("need") == "reg"
        # Purchase-form responses never become tickets/registrations.
        and _snapshot_purpose(record) == "registration"
    )


def _form_tracking_code(record: FormResponseRecord) -> str:
    if record.ticket_serial:
        return record.ticket_serial
    compact_id = record.id.replace("-", "").upper()
    return "NORA-" + compact_id[:20]


def _ensure_form_ticket(record: FormResponseRecord) -> str:
    if record.status != "accepted":
        raise HTTPException(409, detail={"code": "ticket_not_accepted"})
    if not _form_ticket_eligible(record):
        raise HTTPException(409, detail={"code": "ticket_not_eligible"})
    if not record.ticket_serial:
        record.ticket_serial = _form_tracking_code(record)
    return record.ticket_serial


def _form_ticket_name(record: FormResponseRecord) -> str:
    if record.registrant_name:
        name = _ticket_text(record.registrant_name, 120)
        if name:
            return name
    snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
    answers = record.answers if isinstance(record.answers, dict) else {}
    fields = _json_list_member(snapshot, "fields")

    def answer_text(field: dict[str, Any]) -> str:
        field_id = field.get("id")
        value = answers.get(field_id) if isinstance(field_id, str) else None
        if isinstance(value, list):
            value = " ".join(str(item) for item in value if isinstance(item, str))
        if not isinstance(value, str):
            return ""
        return " ".join(value.split())[:120]

    name_fields = [
        field for field in fields
        if isinstance(field, dict)
        and (
            field.get("type") == "fullname"
            or isinstance(field.get("label"), str)
            and ("نام کامل" in field["label"] or "نام و نام خانوادگی" in field["label"])
        )
    ]
    for field in name_fields:
        value = answer_text(field)
        if value:
            return value

    first_name = next((
        answer_text(field) for field in fields
        if isinstance(field, dict)
        and isinstance(field.get("label"), str)
        and field["label"].strip() == "نام"
        and answer_text(field)
    ), "")
    family_name = next((
        answer_text(field) for field in fields
        if isinstance(field, dict)
        and isinstance(field.get("label"), str)
        and field["label"].strip() in {"نام خانوادگی", "نام فامیل"}
        and answer_text(field)
    ), "")
    if first_name or family_name:
        return " ".join(part for part in (first_name, family_name) if part)[:120]

    for field in fields:
        if (isinstance(field, dict) and isinstance(field.get("label"), str)
                and "نام" in field["label"] and "خانوادگی" not in field["label"]):
            value = answer_text(field)
            if value:
                return value
    return ""


def _ticket_text(value: Any, maximum: int) -> str:
    if not isinstance(value, str):
        return ""
    text = "".join(
        " " if char.isspace() else char
        for char in value
        if char.isspace() or char in {"\u200c", "\u200d"} or char.isprintable()
    )
    return " ".join(text.split())[:maximum]


def _form_ticket_event_snapshot(db: Session, form: FormRecord) -> dict[str, str] | None:
    """Freeze only public event schedule fields into a newly accepted response."""
    site = db.get(SiteContentRecord, "public")
    if site is None:
        return None
    public_events = public_site_content(site.content or {}).get("events", [])
    for event in public_events:
        if (not isinstance(event, dict) or event.get("privacy") not in (None, "public")
                or event.get("hidden") is True or event.get("status") == "draft"
                or event.get("pub") is False):
            continue
        event_id = str(event.get("id") or "")
        linked_by_event = bool(form.event_id and event_id == str(form.event_id))
        event_forms = _json_list_member(event, "forms")
        linked_by_form = any(
            isinstance(item, dict) and str(item.get("id") or "") == form.id
            for item in event_forms
        )
        if not (linked_by_event or linked_by_form):
            continue
        return {
            "title": _ticket_text(event.get("t") or event.get("n") or form.title, 160),
            "date": _ticket_text(event.get("when") or event.get("on") or "", 120),
            "time": _ticket_text(event.get("time") or "", 120),
        }
    return None


def _form_response_ticket_type(record: FormResponseRecord) -> dict[str, str] | None:
    snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
    value = snapshot.get("ticket_type")
    if not isinstance(value, dict):
        return None
    ticket_type_id = value.get("id")
    ticket_type_name = _ticket_text(value.get("name"), 80)
    if (
        not isinstance(ticket_type_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", ticket_type_id)
        or not ticket_type_name
    ):
        return None
    return {"id": ticket_type_id, "name": ticket_type_name}


def _form_ticket_payload(record: FormResponseRecord) -> dict[str, Any]:
    snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
    event = _json_dict_member(snapshot, "event")
    form_title = str(snapshot.get("name") or "فرم ثبت‌نام")[:160]
    payload: dict[str, Any] = {
        "source": "shared_server_database",
        "response_id": record.id,
        "form_id": record.form_id,
        "serial": record.ticket_serial,
        "form_title": form_title,
        "event_title": _ticket_text(event.get("title") or form_title, 160) or form_title,
        "event_date": _ticket_text(event.get("date") or "", 120),
        "event_time": _ticket_text(event.get("time") or "", 120),
        "participant_name": _form_ticket_name(record),
        "issued_at": _as_utc(record.created_at).isoformat(),
        "receipt_required": snapshot.get("receipt_review_required") is True,
        "receipt_submitted": (
            record.receipt_review_task_id is not None or record.receipt_upload is not None
        ),
        "checked_in": record.ticket_checked_in_at is not None,
        "checked_in_at": (
            _as_utc(record.ticket_checked_in_at).isoformat()
            if record.ticket_checked_in_at is not None else None
        ),
    }
    ticket_type = _form_response_ticket_type(record)
    if ticket_type is not None:
        payload["ticket_type"] = ticket_type
    return payload


def _render_public_form_ticket_image(image_data: dict[str, str]) -> bytes:
    """Render the same shared-form ticket artwork used by the Bale bot."""
    # مسیر پوشه‌ی ربات قابل تنظیم است (NORA_BOT_ROOT)؛ در غیر این صورت
    # ابتدا چیدمان مخزن (nora_bot کنار docs) و سپس چیدمان تحویل (bale-bot کنار website) بررسی می‌شود.
    backend_file = Path(__file__).resolve()
    env_bot_root = os.getenv("NORA_BOT_ROOT", "").strip()
    candidates = [Path(env_bot_root)] if env_bot_root else []
    candidates += [backend_file.parents[4] / "nora_bot", backend_file.parents[3] / "bale-bot" / "nora_bot"]
    bot_root = next(
        (c for c in candidates if (c / "form_ticket_image.py").is_file()),
        candidates[0] if candidates else backend_file.parents[4] / "nora_bot",
    )
    if not (bot_root / "form_ticket_image.py").is_file():
        raise RuntimeError("shared form ticket renderer is not installed")
    bot_root_text = str(bot_root)
    if bot_root_text not in sys.path:
        sys.path.insert(0, bot_root_text)
    from form_ticket_image import build_shared_form_ticket_image  # noqa: PLC0415

    with tempfile.TemporaryDirectory(prefix="nora-public-ticket-") as directory:
        output = Path(directory) / "ticket.jpg"
        rendered = build_shared_form_ticket_image(image_data, out_path=output)
        if not rendered:
            raise RuntimeError("shared form ticket renderer failed")
        content = Path(rendered).read_bytes()
    if not content.startswith(b"\xff\xd8"):
        raise RuntimeError("shared form ticket renderer returned an invalid image")
    return content


def _form_payment_for_response(db: Session, response_id: str) -> FormPaymentRecord | None:
    return db.scalar(
        select(FormPaymentRecord).where(FormPaymentRecord.response_id == response_id)
    )


def _response_payment_approved(db: Session, record: FormResponseRecord) -> bool:
    payment = _form_payment_for_response(db, record.id)
    if payment is None:
        snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
        if snapshot.get("receipt_review_required") is not True:
            return True
        task = db.get(AdminTaskRecord, record.receipt_review_task_id) if record.receipt_review_task_id else None
        return bool(task is not None and task.kind == "receipt_review" and task.status == "approved")
    if payment.method == "bale_wallet":
        return payment.status == "paid"
    if payment.method == "card_transfer":
        return payment.status == "paid_manual"
    return False


def _create_public_form_receipt_task(
    db: Session, record: FormResponseRecord, bale_user_id: str, *,
    account: AccountRecord | None = None, purchase: bool = False,
) -> AdminTaskRecord | None:
    """Move a browser-uploaded receipt into the shared manager inbox.

    Registration forms reach this at Bale ticket-claim time; purchase forms (phase
    9.1) reach it right after the upload with the buyer's own account. ``bale_user_id``
    may be empty for a web-only buyer: the task row then carries ``""`` exactly like
    ``user_notifications`` does for accounts without a Bale identity.
    """
    snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
    if snapshot.get("receipt_review_required") is not True:
        return None
    if record.receipt_review_task_id:
        task = db.get(AdminTaskRecord, record.receipt_review_task_id)
        if task is None:
            raise HTTPException(409, "public_form_receipt_task_unavailable")
        return task
    upload = record.receipt_upload
    if upload is None:
        return None

    if account is None:
        try:
            account = get_or_create_bale_account(db, bale_user_id)
        except ValueError:
            raise HTTPException(422, "invalid_bale_user_id") from None
    db.flush()

    response_key = record.id.replace("-", "").lower()
    task_id = str(uuid.uuid4())
    event_data = snapshot.get("event")
    event_title = event_data.get("title") if isinstance(event_data, dict) else None
    task_payload: dict[str, Any] = {
        "registration_source": "public_form",
        "form_id": record.form_id,
        "form_response_id": record.id,
        "event_title": _ticket_text(event_title or snapshot.get("name") or "ثبت‌نام", 160),
        "ref_code": "F" + response_key[:10].upper(),
        "file_refs": [upload.id],
        "submitted_at": _as_utc(upload.created_at).isoformat(),
    }
    if purchase:
        form_row = db.get(FormRecord, record.form_id)
        recording_row = db.get(EventRecordingRecord, form_row.recording_id or "") if form_row is not None else None
        task_payload.update({
            "purchase_source": "recording_access",
            "recording_id": recording_row.id if recording_row is not None else (form_row.recording_id if form_row else ""),
            "product_title": _ticket_text((recording_row.title if recording_row is not None else "") or snapshot.get("name") or "محتوای ضبط‌شده", 160),
            "event_id": recording_row.event_id if recording_row is not None else "",
        })
    payment_record = db.scalar(
        select(FormPaymentRecord).where(FormPaymentRecord.response_id == record.id)
    )
    if payment_record is not None and payment_record.method == "card_transfer":
        task_payload.update({"amount": payment_record.amount, "currency": payment_record.currency})
    receipt_note = str(upload.note or "").strip()[:500]
    if receipt_note:
        task_payload["note"] = receipt_note
    create_hash = hashlib.sha256(
        json.dumps(
            {"kind": "receipt_review", "payload": task_payload},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    task = AdminTaskRecord(
        id=task_id,
        account_id=account.id,
        bale_user_id=bale_user_id,
        kind="receipt_review",
        payload=task_payload,
        status="pending",
        idempotency_key="public-form-receipt:" + response_key,
        create_hash=create_hash,
        version=1,
    )
    private_file = PrivateFileRecord(
        id=upload.id,
        account_id=account.id,
        bale_user_id=bale_user_id,
        idempotency_key="public-form-receipt-file:" + response_key,
        content_hash=upload.content_hash,
        file_name=upload.file_name,
        content_type=upload.content_type,
        content_size=upload.content_size,
        content=upload.content,
        task_id=task_id,
    )
    db.add(task)
    db.add(private_file)
    record.receipt_review_task_id = task_id
    db.delete(upload)
    db.flush()
    return task


def _ticket_claim_nonce(response_id: str, expires_at: datetime, secret: str) -> bytes:
    expires = int(_as_utc(expires_at).timestamp())
    message = (
        b"nora-form-ticket-nonce-v1\0"
        + response_id.encode("ascii")
        + b"\0"
        + str(expires).encode("ascii")
    )
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()[:16]


def _ticket_claim_token(response_id: str, expires_at: datetime, secret: str) -> tuple[str, str]:
    expires = int(_as_utc(expires_at).timestamp())
    nonce = _ticket_claim_nonce(response_id, expires_at, secret)
    body = nonce + expires.to_bytes(4, "big")
    signature = hmac.new(
        secret.encode("utf-8"), b"nora-form-ticket-claim-v1\0" + body, hashlib.sha256
    ).digest()[:16]
    token = base64.urlsafe_b64encode(body + signature).rstrip(b"=").decode("ascii")
    return token, hashlib.sha256(nonce).hexdigest()


def _decode_ticket_claim(token: Any, secret: str) -> tuple[str, int]:
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{48}", token):
        raise HTTPException(422, "invalid_ticket_claim_token")
    try:
        raw = base64.urlsafe_b64decode(token + "==")
    except (ValueError, TypeError):
        raise HTTPException(422, "invalid_ticket_claim_token") from None
    if len(raw) != 36:
        raise HTTPException(422, "invalid_ticket_claim_token")
    body, signature = raw[:20], raw[20:]
    expected = hmac.new(
        secret.encode("utf-8"), b"nora-form-ticket-claim-v1\0" + body, hashlib.sha256
    ).digest()[:16]
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(404, "ticket_claim_not_found")
    expires = int.from_bytes(body[16:20], "big")
    if expires <= int(_utc_now().timestamp()):
        raise HTTPException(410, "ticket_claim_expired")
    return hashlib.sha256(body[:16]).hexdigest(), expires


def _replace_fields(db: Session, form_id: str, normalized: Any) -> None:
    db.execute(delete(FormFieldRecord).where(FormFieldRecord.form_id == form_id))
    db.flush()
    for position, field in enumerate(normalized.fields):
        db.add(
            FormFieldRecord(
                form_id=form_id,
                field_key=field.key,
                position=position,
                field_type=field.field_type,
                label=field.label,
                config=field.config,
            )
        )


def _public_draft_cookie_name(form_id: str) -> str:
    suffix = hashlib.sha256(form_id.encode("utf-8")).hexdigest()[:16]
    return f"nora_response_draft_{suffix}"


def _json_for_html(value: Any) -> str:
    """Serialize JSON for a non-executable script element without HTML breakouts."""
    return (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _response_counts(db: Session, form_id: str) -> tuple[int, int]:
    rows = db.execute(
        select(FormResponseRecord.status, func.count(FormResponseRecord.id))
        .where(FormResponseRecord.form_id == form_id)
        .group_by(FormResponseRecord.status)
    ).all()
    values = {status: count for status, count in rows}
    return int(values.get("accepted", 0)), int(values.get("waitlisted", 0))


def _active_bale_payment_holds(
    db: Session,
    form_id: str,
    *,
    exclude_payment_id: str | None = None,
    exclude_draft_id: str | None = None,
) -> int:
    now = _utc_now()
    query = select(func.coalesce(func.sum(FormPaymentRecord.party_count), 0)).where(
        FormPaymentRecord.form_id == form_id,
        FormPaymentRecord.method == "bale_wallet",
        FormPaymentRecord.status == "pending",
        FormPaymentRecord.expires_at > now,
    )
    if exclude_payment_id:
        query = query.where(FormPaymentRecord.id != exclude_payment_id)
    if exclude_draft_id:
        query = query.where(FormPaymentRecord.draft_id != exclude_draft_id)
    return int(db.scalar(query) or 0)


def _selected_form_payment_methods(form: FormRecord) -> list[str]:
    settings = form.settings if isinstance(form.settings, dict) else {}
    try:
        return normalize_payment_methods(settings)
    except PaymentConfigurationError:
        return []


def _payment_selection_for_recalculation(
    saved_selection: Any, form_settings: dict[str, Any]
) -> dict[str, Any] | None:
    """Recover the validated input selection from either a current or legacy payment snapshot."""
    if not isinstance(saved_selection, dict):
        return None
    saved_items = saved_selection.get("items")
    if not isinstance(saved_items, list):
        return None
    indexes: list[int] = []
    for item in saved_items:
        index = item.get("index") if isinstance(item, dict) else item
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            return None
        indexes.append(index)
    coupon_code = saved_selection.get("coupon_code")
    if coupon_code is None:
        coupon = _json_dict_member(form_settings, "coupon")
        coupon_code = coupon.get("code", "") if saved_selection.get("coupon_applied") is True else ""
    if not isinstance(coupon_code, str):
        return None
    return {"items": indexes, "coupon_code": coupon_code}


def _form_uses_payment(form: FormRecord) -> bool:
    settings = form.settings if isinstance(form.settings, dict) else {}
    return bool(
        _selected_form_payment_methods(form)
        or settings.get("receiptReviewRequired") is True
        or isinstance(settings.get("fin"), list) and settings.get("fin")
    )


def _count_setting(value: Any, *, fallback: int = 0) -> int:
    if isinstance(value, bool):
        return fallback
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    return max(0, min(100_000, parsed))


def _capacity_is_full(form: FormRecord, accepted: int, waitlisted: int) -> bool:
    settings = form.settings if isinstance(form.settings, dict) else {}
    try:
        cap = _count_setting(settings.get("cap", 0))
        wait = _count_setting(settings.get("wait", 0))
    except (TypeError, ValueError, OverflowError):
        return True
    if cap <= 0 or accepted < cap:
        return False
    return wait <= 0 or waitlisted >= wait


def _event_registration_block(db: Session, form: FormRecord, now: datetime | None = None) -> dict[str, Any] | None:
    """Return the registration status when the event linked to ``form`` does not accept
    new registrations right now (window, manual close, cancellation, ended), else ``None``.

    Capacity is checked by the callers as before; this gate only adds the event-level
    rules so a direct API call cannot bypass what the public pages show.
    """
    if _form_is_purchase(form):
        # Buying the recording of a held event is gated by the product (see
        # ``_purchase_form_block``), never by the event's registration window.
        return None
    site = db.get(SiteContentRecord, "public")
    if site is None:
        return None
    current = now or _utc_now()
    for event in public_site_content(site.content or {}).get("events", []):
        if not isinstance(event, dict):
            continue
        linked = bool(form.event_id and str(event.get("id") or "") == str(form.event_id))
        if not linked:
            linked = any(
                isinstance(item, dict) and str(item.get("id") or "") == form.id
                for item in _json_list_member(event, "forms")
            )
        if not linked:
            continue
        registration = event_time.registration_state(event, now=current, has_form=True)
        if event_time.is_registration_blocked(registration["state"]):
            return {"event_id": str(event.get("id") or ""), **registration}
        return None
    return None


def _purchase_form_block(db: Session, form: FormRecord) -> dict[str, Any] | None:
    """Why a purchase form cannot take responses right now (``None`` = on sale)."""
    if not _form_is_purchase(form):
        return None
    recording = db.get(EventRecordingRecord, form.recording_id or "")
    if recording is None:
        return {"code": "recording_not_found", "status": ""}
    if recording.status != "published":
        return {"code": "recording_not_on_sale", "status": recording.status, "recording_id": recording.id}
    return None


def _raise_if_event_registration_blocked(db: Session, form: FormRecord) -> None:
    purchase_block = _purchase_form_block(db, form)
    if purchase_block is not None:
        raise HTTPException(409, detail=purchase_block)
    blocked = _event_registration_block(db, form)
    if blocked is not None:
        raise HTTPException(409, detail={
            "code": "registration_closed",
            "state": blocked["state"],
            "event_id": blocked["event_id"],
            "opens_at": blocked["opensAt"],
            "closes_at": blocked["closesAt"],
        })


def _response_party_statuses(
    form: FormRecord, accepted: int, waitlisted: int, count: int
) -> list[str]:
    """Allocate capacity per person, not per browser submission."""
    settings = form.settings if isinstance(form.settings, dict) else {}
    cap = _count_setting(settings.get("cap", 0))
    wait_limit = _count_setting(settings.get("wait", 0))
    statuses: list[str] = []
    for _ in range(max(0, count)):
        if cap <= 0 or accepted < cap:
            statuses.append("accepted")
            accepted += 1
        elif waitlisted < wait_limit:
            statuses.append("waitlisted")
            waitlisted += 1
        else:
            raise HTTPException(410, detail={"code": "form_full"})
    return statuses


def _cleanup_expired_public_drafts(db: Session) -> None:
    expired_without_response = (
        select(FormResponseDraftRecord.id)
        .outerjoin(FormResponseRecord, FormResponseRecord.draft_id == FormResponseDraftRecord.id)
        .where(
            FormResponseDraftRecord.expires_at <= _utc_now(),
            FormResponseRecord.id.is_(None),
        )
    )
    db.execute(
        delete(FormResponseDraftRecord)
        .where(FormResponseDraftRecord.id.in_(expired_without_response))
        .execution_options(synchronize_session=False)
    )


def create_app(
    settings: Settings | None = None,
    *,
    engine: Engine | None = None,
    create_schema: bool = False,
) -> FastAPI:
    settings = settings or Settings.from_env()
    owned_engine = engine or (_new_engine(settings.database_url) if settings.database_url else None)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            if owned_engine is not None:
                owned_engine.dispose()

    app = FastAPI(
        title="Nora same-application form API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(GZipMiddleware, minimum_size=500, compresslevel=5)
    app.state.engine = owned_engine
    app.state.session_factory = (
        sessionmaker(bind=owned_engine, autoflush=False, expire_on_commit=False) if owned_engine else None
    )
    app.state.settings = settings
    # Phase 9.4: private storage outside the web root (None = not configured → inline ≤ 8 MiB only).
    app.state.private_storage = (
        storage_mod.LocalPrivateStorage(
            settings.private_storage_dir, max_bytes=settings.private_storage_max_bytes, forbidden_parents=(UI_ROOT,),
        )
        if settings.private_storage_dir else None
    )
    if create_schema and owned_engine:
        Base.metadata.create_all(owned_engine)

    def _seo_public_snapshot() -> dict[str, Any]:
        factory = app.state.session_factory
        if factory is None:
            return {}
        try:
            with factory() as db:
                record = db.get(SiteContentRecord, "public")
                if record is None:
                    return {}
                try:
                    normalized = sanitize_site_content(record.content or {})
                except SiteContentError:
                    return {}
                return public_site_content(normalized)
        except SQLAlchemyError:
            return {}

    def _seo_breadcrumb(label: str, route: str) -> str:
        return (
            '<nav aria-label="مسیر صفحه"><a href="/">خانه</a>'
            '<span aria-hidden="true"> / </span>'
            f'<a href="{route}">{html.escape(label)}</a>'
            '<span aria-hidden="true"> / </span>'
        )

    def _seo_item_fallback(page_name: str, item: dict[str, Any], title: str, description: str) -> str:
        safe_title = html.escape(title)
        safe_description = html.escape(description)
        if page_name == "event":
            return (
                '<article class="seo-server-fallback">'
                + _seo_breadcrumb("رویدادها", "/events.html")
                + f'<span aria-current="page">{html.escape(str(item.get("t") or ""))}</span></nav>'
                + f'<h1>{safe_title}</h1><p>{safe_description}</p></article>'
            )
        if page_name == "post":
            return (
                '<article class="seo-server-fallback">'
                + _seo_breadcrumb("مطالب", "/#articles")
                + f'<span aria-current="page">{html.escape(str(item.get("t") or ""))}</span></nav>'
                + f'<h1>{safe_title}</h1><p>{safe_description}</p></article>'
            )
        if page_name == "partner":
            return (
                '<article class="seo-server-fallback">'
                + _seo_breadcrumb("نهادهای همکار", "/#partners")
                + f'<span aria-current="page">{html.escape(str(item.get("n") or ""))}</span></nav>'
                + f'<h1>{safe_title}</h1><p>{safe_description}</p></article>'
            )
        return (
            '<article class="seo-server-fallback">'
            + _seo_breadcrumb("پروفایل‌ها", "/#teachers")
            + f'<span aria-current="page">{html.escape(str(item.get("n") or ""))}</span></nav>'
            + f'<h1>{safe_title}</h1><p>{safe_description}</p></article>'
        )

    def _seo_missing_fallback(page_name: str) -> str:
        config = {
            "event": ("این رویداد در دسترس نیست", "/events.html", "بازگشت به رویدادها"),
            "post": ("این مطلب در دسترس نیست", "/#articles", "بازگشت به مطالب"),
            "person": ("این پروفایل در دسترس نیست", "/#teachers", "بازگشت به پروفایل‌ها"),
            "partner": ("این نهاد همکار در دسترس نیست", "/#partners", "بازگشت به نهادهای همکار"),
        }
        heading, href, label = config[page_name]
        return (
            '<section class="card paper seo-server-fallback" role="status">'
            f'<h1>{heading}</h1><p>ممکن است این صفحه از محتوای عمومی برداشته شده باشد یا نشانی آن نادرست باشد.</p>'
            f'<a href="{href}">{label}</a></section>'
        )

    def _seo_html_response(
        page_name: str,
        request: Request,
        *,
        status_code: int | None = None,
    ) -> HTMLResponse:
        if not re.fullmatch(r"[a-z0-9_-]{1,80}", page_name):
            page_name = "404"
            status_code = 404
        page_file = UI_ROOT / f"{page_name}.html"
        if not page_file.is_file():
            page_name = "404"
            page_file = UI_ROOT / "404.html"
            status_code = 404
        html_text = page_file.read_text(encoding="utf-8")
        cfg: Settings = request.app.state.settings
        base_url = cfg.public_base_url
        title_match = re.search(r"<title\b[^>]*>(.*?)</title\s*>", html_text, re.I | re.S)
        default_title = html.unescape(re.sub(r"<[^>]+>", "", title_match.group(1))).strip() if title_match else SITE_NAME
        title = {
            "home": "نورا | گروه فرهنگی خط زندگی",
            "index": "نورا | گروه فرهنگی خط زندگی",
            "events": "رویدادها و برنامه‌های نورا | گروه فرهنگی خط زندگی",
            "404": "صفحه پیدا نشد | نورا",
        }.get(page_name, default_title)
        description = default_page_description(page_name)
        robots = (
            "index,follow" if page_name in {"home", "events"}
            else "noindex,nofollow,noarchive" if page_name == "404"
            else "noindex,follow,noarchive"
        )
        path = canonical_path(page_name)
        canonical = canonical_url(base_url, path) if path and page_name in {"home", "index", "events", "support"} else ""
        og_type = "website"
        image = ""
        body_fragment: str | None = None
        data: dict[str, Any] | None = None

        if page_name in {"event", "post", "person", "partner"}:
            item_id = (request.query_params.get("id") or "").strip()
            preview = page_name == "post" and request.query_params.get("d") == "1"
            key = {"event": "events", "post": "articles", "person": "people", "partner": "partners"}[page_name]
            if item_id and not preview:
                rows = _seo_public_snapshot().get(key, [])
                if isinstance(rows, list):
                    data = next((row for row in rows if isinstance(row, dict) and str(row.get("id")) == item_id), None)
            if data is not None:
                title, description, path, schema_type, og_type = dynamic_page_values(page_name, data)
                canonical = canonical_url(base_url, path)
                robots = "index,follow"
                image_value = {
                    "event": data.get("posterUp") or data.get("poster"),
                    "post": data.get("cov"),
                    "person": data.get("photo"),
                    "partner": data.get("logo"),
                }[page_name]
                image = absolute_asset_url(base_url, image_value)
                if (
                    not image
                    and isinstance(image_value, str)
                    and not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", image_value)
                    and not image_value.startswith("//")
                    and ".." not in image_value.split("/")
                ):
                    image = image_value
                body_fragment = _seo_item_fallback(page_name, data, title, description)
                if page_name == "post":
                    data = {**data, "id": item_id}
            elif preview:
                title = "پیش‌نمایش مطلب | نورا"
                description = "پیش‌نمایش خصوصی مطلب؛ محتوای منتشرنشده در نتایج جست‌وجو قرار نمی‌گیرد."
                robots = "noindex,nofollow,noarchive"
                canonical = ""
            else:
                title = {
                    "event": "رویداد پیدا نشد | نورا",
                    "post": "مطلب پیدا نشد | نورا",
                    "person": "پروفایل پیدا نشد | نورا",
                    "partner": "نهاد همکار پیدا نشد | نورا",
                }[page_name]
                description = default_page_description(page_name)
                robots = "noindex,nofollow,noarchive"
                canonical = ""
                body_fragment = _seo_missing_fallback(page_name)
                status_code = 404 if status_code is None else status_code

        if page_name in {"home", "events"}:
            schema_type = "WebPage"
            page_url = canonical_url(base_url, path)
            image = absolute_asset_url(base_url, "/icon-512.png") or "/icon-512.png"
        else:
            schema_type = locals().get("schema_type", "WebPage")
            page_url = canonical

        schema = None
        if page_name in {"home", "events"} or data is not None:
            schema = structured_data(
                base_url=base_url,
                title=title,
                description=description,
                page_url=page_url,
                page_type=schema_type,
                item=data,
                local_business=cfg.seo_local_business,
                profile_entity="Organization" if page_name == "partner" else "Person",
            )
        html_text = apply_page_metadata(
            html_text,
            title=title,
            description=description,
            robots=robots,
            canonical=canonical,
            og_type=og_type,
            image=image,
            json_ld=schema,
            body_fragment=body_fragment,
        )
        if page_name == "404":
            status_code = 404 if status_code is None else status_code
        return HTMLResponse(html_text, status_code=status_code or 200)

    frame_ancestors = os.getenv("NORA_FRAME_ANCESTORS", "").strip()
    if any(ch in frame_ancestors for ch in ";\r\n"):
        frame_ancestors = ""
    csp_frame_src = settings.csp_frame_src
    csp_report_only = settings.csp_report_only

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if frame_ancestors:
            # فقط برای پیش‌نمایش توسعه: NORA_FRAME_ANCESTORS تعیین می‌کند چه میزبانی قاب بزند.
            response.headers["Content-Security-Policy"] = f"frame-ancestors {frame_ancestors}"
        else:
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
        if csp_frame_src and "text/html" in response.headers.get("content-type", ""):
            # فاز ۹.۴ §۵: allowlist صریح قاب‌های ویدیو (یوتیوب/آپارات) فقط وقتی NORA_CSP_FRAME_SRC تنظیم
            # شده؛ پیش‌فرض Report-Only تا staging با مرورگر واقعی بی‌خطا شود، سپس NORA_CSP_REPORT_ONLY=0.
            # پاسخ‌های فایل (CSP «sandbox») HTML نیستند و دست نمی‌خورند.
            # فاز ۹.۶ §۸: نقض‌ها به /api/csp-report می‌روند (فقط لاگ ساخت‌یافتهٔ بدون PII) تا staging بتواند
            # مبدأهای واقعاً لازم را پیش از enforce جمع کند.
            policy = f"frame-src {csp_frame_src}; report-uri {CSP_REPORT_PATH}"
            if csp_report_only:
                response.headers["Content-Security-Policy-Report-Only"] = policy
            elif "Content-Security-Policy" in response.headers:
                response.headers["Content-Security-Policy"] += f"; {policy}"
            else:
                response.headers["Content-Security-Policy"] = policy
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        path = request.url.path.lower()
        if path.startswith("/api/public/media/") and response.status_code in {200, 304}:
            # تصویر عمومی با شناسهٔ ثابت و محتوای تغییرناپذیر؛ هدر کش را خود مسیر تعیین می‌کند.
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        elif path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        elif path in {"/account.html", "/login.html", "/admin.html", "/builder.html", "/create.html", "/form.html"}:
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        elif path.endswith(".html") or path == "/":
            response.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
        elif Path(path).suffix in {".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".woff", ".woff2"} and request.query_params.get("v"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
        return response

    def get_db(request: Request) -> Generator[Session, None, None]:
        factory = request.app.state.session_factory
        if factory is None:
            raise HTTPException(503, "database_not_configured")
        db = factory()
        try:
            yield db
        finally:
            db.close()

    def require_owner(request: Request, db: Session = Depends(get_db)) -> OwnerIdentity:
        cfg: Settings = request.app.state.settings
        token = request.cookies.get(cfg.cookie_name, "")
        if not token:
            raise HTTPException(401, "authentication_required")
        record = db.scalar(
            select(OwnerSessionRecord).where(OwnerSessionRecord.token_hash == token_digest(token))
        )
        if not record or record.revoked_at is not None or _as_utc(record.expires_at) <= _utc_now():
            raise HTTPException(401, "authentication_required")
        if not constant_time_equal(record.owner_id, cfg.owner_id):
            raise HTTPException(403, "owner_required")
        return OwnerIdentity(record.id, record.owner_id, record.csrf_hash)

    def require_owner_write(
        request: Request,
        identity: OwnerIdentity = Depends(require_owner),
    ) -> OwnerIdentity:
        _same_origin(request)
        csrf_cookie = request.cookies.get(request.app.state.settings.csrf_cookie_name, "")
        csrf_header = request.headers.get("x-csrf-token", "")
        if not csrf_cookie or not csrf_header or not constant_time_equal(csrf_cookie, csrf_header):
            raise HTTPException(403, "csrf_check_failed")
        if not constant_time_equal(token_digest(csrf_cookie), identity.csrf_hash):
            raise HTTPException(403, "csrf_check_failed")
        return identity

    def account_identity_from_request(request: Request, db: Session) -> AccountIdentity | None:
        cfg: Settings = request.app.state.settings
        token = request.cookies.get(cfg.account_cookie_name, "")
        if not token:
            return None
        record = db.scalar(
            select(AccountSessionRecord).where(
                AccountSessionRecord.token_hash == token_digest(token)
            )
        )
        if not record or record.revoked_at is not None or _as_utc(record.expires_at) <= _utc_now():
            return None
        if _account_is_blocked(db, record.account_id):
            # Blocked after the session was opened: the cookie no longer resolves to an identity
            # (optional-identity routes see an anonymous visitor; ``require_account`` says why).
            request.state.account_blocked = True
            return None
        role_record = db.get(AccountRoleRecord, record.account_id)
        role = role_record.role if role_record is not None else None
        return AccountIdentity(
            record.id, record.account_id, record.csrf_hash, role, cfg.owner_id, record.auth_provider
        )

    def require_account(request: Request, db: Session = Depends(get_db)) -> AccountIdentity:
        identity = account_identity_from_request(request, db)
        if identity is None:
            if getattr(request.state, "account_blocked", False):
                raise HTTPException(403, ACCOUNT_BLOCKED_DETAIL)
            raise HTTPException(401, "authentication_required")
        return identity

    def public_write_identity(request: Request, db: Session) -> AccountIdentity | None:
        """Optional identity for public *write* routes (form drafts/responses).

        An anonymous visitor is fine; a cookie that belongs to a blocked account is not silently
        downgraded to anonymous (that would let a blocked member register as a guest).
        """
        identity = account_identity_from_request(request, db)
        if identity is None and getattr(request.state, "account_blocked", False):
            raise HTTPException(403, ACCOUNT_BLOCKED_DETAIL)
        return identity

    def bind_public_draft_account(
        draft: FormResponseDraftRecord, identity: AccountIdentity | None, db: Session
    ) -> bool:
        if identity is None or draft.account_id == identity.account_id:
            return False
        if draft.account_id is not None:
            raise HTTPException(409, detail={"code": "response_draft_account_mismatch"})
        result = db.execute(
            update(FormResponseDraftRecord)
            .where(
                FormResponseDraftRecord.id == draft.id,
                FormResponseDraftRecord.account_id.is_(None),
            )
            .values(account_id=identity.account_id)
        )
        if cast(CursorResult[Any], result).rowcount == 1:
            draft.account_id = identity.account_id
            return True
        db.refresh(draft, attribute_names=["account_id"])
        if draft.account_id != identity.account_id:
            raise HTTPException(409, detail={"code": "response_draft_account_mismatch"})
        return False

    def require_account_write(
        request: Request,
        identity: AccountIdentity = Depends(require_account),
    ) -> AccountIdentity:
        cfg: Settings = request.app.state.settings
        _same_origin(request)
        csrf_cookie = request.cookies.get(cfg.account_csrf_cookie_name, "")
        csrf_header = request.headers.get("x-csrf-token", "")
        if not csrf_cookie or not csrf_header or not constant_time_equal(csrf_cookie, csrf_header):
            raise HTTPException(403, "csrf_check_failed")
        if not constant_time_equal(token_digest(csrf_cookie), identity.csrf_hash):
            raise HTTPException(403, "csrf_check_failed")
        return identity

    def require_bot_service(request: Request) -> None:
        cfg: Settings = request.app.state.settings
        expected = cfg.bot_service_token
        if not expected:
            raise HTTPException(503, "bot_api_not_configured")
        authorization = request.headers.get("authorization", "")
        scheme, separator, supplied = authorization.partition(" ")
        if not separator or scheme.lower() != "bearer" or not supplied:
            raise HTTPException(401, "bot_service_authentication_required")
        if not constant_time_equal(supplied, expected):
            raise HTTPException(401, "bot_service_authentication_required")

    def require_any_permission(*permissions: str):
        """Authorize the owner or a manager-password session by current server role."""
        wanted = tuple(dict.fromkeys(permissions))
        def dependency(request: Request, db: Session = Depends(get_db)) -> OwnerIdentity | AccountIdentity:
            try:
                owner = require_owner(request, db)
            except HTTPException:
                owner = None
            role = ROLE_OWNER if owner is not None else None
            account = None
            if owner is None:
                account = require_account(request, db)
                role = account.role
                if role in {"manager", "club-supervisor"} and account.provider != "manager-password":
                    raise HTTPException(403, "manager_password_required")
            if not any(has_permission(role, permission) for permission in wanted):
                raise HTTPException(403, "permission_denied")
            assert owner is not None or account is not None
            return owner if owner is not None else cast(AccountIdentity, account)
        return dependency

    def require_any_permission_write(*permissions: str):
        """Any listed permission plus session-specific same-origin CSRF validation."""
        permitted_actor = require_any_permission(*permissions)
        def dependency(
            request: Request,
            identity: OwnerIdentity | AccountIdentity = Depends(permitted_actor),
        ) -> OwnerIdentity | AccountIdentity:
            cfg: Settings = request.app.state.settings
            _same_origin(request)
            if isinstance(identity, OwnerIdentity):
                csrf_cookie = request.cookies.get(cfg.csrf_cookie_name, "")
            else:
                csrf_cookie = request.cookies.get(cfg.account_csrf_cookie_name, "")
            csrf_header = request.headers.get("x-csrf-token", "")
            if not csrf_cookie or not csrf_header or not constant_time_equal(csrf_cookie, csrf_header):
                raise HTTPException(403, "csrf_check_failed")
            if not constant_time_equal(token_digest(csrf_cookie), identity.csrf_hash):
                raise HTTPException(403, "csrf_check_failed")
            return identity
        return dependency

    def require_permission(permission: str):
        """Authorize an owner or a Bale account using the canonical server policy."""
        return require_any_permission(permission)

    def require_permission_write(permission: str):
        """Permission check plus session-specific same-origin CSRF validation."""
        permitted_actor = require_permission(permission)
        def dependency(
            request: Request,
            identity: OwnerIdentity | AccountIdentity = Depends(permitted_actor),
        ) -> OwnerIdentity | AccountIdentity:
            cfg: Settings = request.app.state.settings
            _same_origin(request)
            if isinstance(identity, OwnerIdentity):
                csrf_cookie = request.cookies.get(cfg.csrf_cookie_name, "")
            else:
                csrf_cookie = request.cookies.get(cfg.account_csrf_cookie_name, "")
            csrf_header = request.headers.get("x-csrf-token", "")
            if not csrf_cookie or not csrf_header or not constant_time_equal(csrf_cookie, csrf_header):
                raise HTTPException(403, "csrf_check_failed")
            if not constant_time_equal(token_digest(csrf_cookie), identity.csrf_hash):
                raise HTTPException(403, "csrf_check_failed")
            return identity
        return dependency

    def bot_account_identity(db: Session, cfg: Settings, bale_user_id: str) -> tuple[str | None, str | None]:
        """Resolve a trusted Bot API ID to canonical account and server role."""
        identity = db.scalar(
            select(PlatformIdentityRecord).where(
                PlatformIdentityRecord.provider == "bale",
                PlatformIdentityRecord.provider_user_id == bale_user_id,
            )
        )
        account_id = identity.account_id if identity is not None else None
        if cfg.owner_bale_user_id and bale_user_id == cfg.owner_bale_user_id:
            return account_id, ROLE_OWNER
        if account_id is None:
            return None, None
        assigned = db.get(AccountRoleRecord, account_id)
        role = assigned.role if assigned is not None else None
        return account_id, role if role in ROLE_KEYS else None

    def verified_bale_ids_for_account(db: Session, account_id: str) -> list[str]:
        """Bale IDs the server itself linked to this account (never client-supplied)."""
        return list(db.scalars(
            select(PlatformIdentityRecord.provider_user_id).where(
                PlatformIdentityRecord.provider == "bale",
                PlatformIdentityRecord.account_id == account_id,
            )
        ))

    def account_form_record_scope(db: Session, account_id: str) -> ColumnElement[bool]:
        """Form-response drafts a signed-in account may read.

        Its own drafts, plus drafts created from the Bale side by a Bale identity that
        the server has verified for this same account. A draft that already names
        another account is never included, even when it carries this account's Bale ID,
        so linking can widen the view to one's own records but never to someone else's.
        """
        own_drafts = FormResponseDraftRecord.account_id == account_id
        bale_ids = verified_bale_ids_for_account(db, account_id)
        if not bale_ids:
            return own_drafts
        return or_(
            own_drafts,
            and_(
                FormResponseDraftRecord.bot_bale_user_id.in_(bale_ids),
                FormResponseDraftRecord.account_id.is_(None),
            ),
        )

    def bot_form_record_scope(db: Session, bale_user_id: str) -> ColumnElement[bool]:
        """Form-response drafts the bot may read on behalf of one Bale user.

        A non-empty `account_id` is the record's explicit owner and wins over any
        Bale tag left on the row: a draft that names another account is never
        returned for this Bale identity, even when it still carries this Bale ID.
        The Bale path therefore only ever reaches *legacy* drafts (no owner yet)
        that carry this Bale ID; a verified link additionally opens the linked
        account's own drafts. An unlinked Bale user gets the legacy drafts only:
        there is no verified account behind the ID, so no owned row may be read
        through it, whichever account the owner happens to be.
        """
        own_untagged = and_(
            FormResponseDraftRecord.bot_bale_user_id == bale_user_id,
            FormResponseDraftRecord.account_id.is_(None),
        )
        linked_account_id = db.scalar(
            select(PlatformIdentityRecord.account_id).where(
                PlatformIdentityRecord.provider == "bale",
                PlatformIdentityRecord.provider_user_id == bale_user_id,
            )
        )
        if linked_account_id is None:
            return own_untagged
        return or_(own_untagged, FormResponseDraftRecord.account_id == linked_account_id)

    def admin_task_view(task: AdminTaskRecord | None) -> dict[str, Any]:
        if task is None:
            raise HTTPException(404, "admin_task_not_found")
        return {
            "id": task.id,
            "account_id": task.account_id,
            "bale_user_id": task.bale_user_id,
            "kind": task.kind,
            "payload": task.payload,
            "status": task.status,
            "version": task.version,
            "projection_status": task.projection_status,
            "projection_attempts": task.projection_attempts,
            "review_reason": task.review_reason,
            "reviewed_by": task.reviewed_by,
            "reviewed_by_bale_user_id": task.reviewed_by_bale_user_id,
            "created_at": _as_utc(task.created_at).isoformat(),
            "reviewed_at": _as_utc(task.reviewed_at).isoformat() if task.reviewed_at else None,
        }

    def admin_inbox_task_views(db: Session, tasks: Sequence[AdminTaskRecord]) -> list[dict[str, Any]]:
        task_accounts = {task.id: task.account_id for task in tasks}
        files = db.scalars(
            select(PrivateFileRecord)
            .where(PrivateFileRecord.task_id.in_(task_accounts))
            .order_by(PrivateFileRecord.created_at, PrivateFileRecord.id)
        ).all() if task_accounts else []
        files_by_task: dict[str, list[dict[str, Any]]] = {}
        for item in files:
            if item.task_id is None or task_accounts.get(item.task_id) != item.account_id:
                continue
            files_by_task.setdefault(item.task_id, []).append({
                "id": item.id,
                "file_name": item.file_name,
                "content_type": item.content_type,
                "content_size": item.content_size,
            })
        # وضعیت تحویل اعلان، جدا از وضعیت تصمیم: از همان صف اعلان سرور خوانده می‌شود،
        # نه از ثبت تصمیم. نبود ردیف اعلان برای کار تصمیم‌گرفته‌شده «نامشخص» گزارش می‌شود.
        decided_ids = [task.id for task in tasks if task.status != "pending"]
        notifications = db.scalars(
            select(UserNotificationRecord)
            .where(UserNotificationRecord.source_task_id.in_(decided_ids))
            .order_by(UserNotificationRecord.created_at, UserNotificationRecord.id)
        ).all() if decided_ids else []
        notification_by_task: dict[str, UserNotificationRecord] = {}
        for outbox in notifications:
            if outbox.source_task_id and outbox.account_id == task_accounts.get(outbox.source_task_id):
                notification_by_task.setdefault(outbox.source_task_id, outbox)
        views = []
        for task in tasks:
            view = admin_task_view(task)
            view["files"] = files_by_task.get(task.id, [])
            if task.status != "pending":
                view["notification"] = task_notification_view(notification_by_task.get(task.id))
            views.append(view)
        return views

    def task_notification_view(item: UserNotificationRecord | None) -> dict[str, Any]:
        """Delivery state of the user's notification for one decided task.

        ``unknown``: no outbox row (older tasks or none queued); ``queued``: waiting
        for the bot; ``retrying``: at least one failed attempt, still pending;
        ``delivered`` / ``failed``: provider acknowledgement recorded by the bot.
        """
        if item is None:
            return {"status": "unknown", "attempts": 0, "delivered_at": None, "last_error": None}
        status = item.delivery_status
        if status == "pending":
            status = "retrying" if item.delivery_attempts > 0 else "queued"
        return {
            "status": status,
            "attempts": item.delivery_attempts,
            "delivered_at": _as_utc(item.delivered_at).isoformat() if item.delivered_at else None,
            "last_error": item.last_delivery_error,
        }

    def user_notification_view(item: UserNotificationRecord) -> dict[str, Any]:
        return {
            "id": item.id,
            "bale_user_id": item.bale_user_id,
            "kind": item.kind,
            "title": item.title,
            "body": item.body,
            "file_refs": item.file_refs,
            "delivery_status": item.delivery_status,
            # Derived outbox state: queued ≠ delivered; retrying = pending after ≥1 failed attempt.
            "delivery_state": interaction_mod.delivery_state(item.delivery_status, item.delivery_attempts),
            "delivery_attempts": item.delivery_attempts,
            "last_delivery_error": item.last_delivery_error or None,
            # Relative in-app page (event/account); never a file URL. NULL for rows older than 9.4.
            "link": item.link or None,
            "created_at": _as_utc(item.created_at).isoformat(),
            "delivered_at": _as_utc(item.delivered_at).isoformat() if item.delivered_at else None,
            "read": item.read_at is not None,
        }

    def workflow_permission(kind: str) -> str:
        if kind == "profile_review":
            return "us_approve"
        if kind == "receipt_review":
            return "receipt_approve"
        raise HTTPException(400, "unsupported_workflow_kind")

    def admin_reports_summary_data(db: Session, role: str | None, period: str) -> dict[str, Any]:
        """Build a privacy-preserving report from records in the shared DB only."""
        allowed_periods = {"today", "yesterday", "7d", "30d", "90d", "365d", "year", "all"}
        if period not in allowed_periods:
            raise HTTPException(422, "invalid_report_period")
        now = _utc_now()
        start = end = cutoff = None
        if period == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period == "yesterday":
            end = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start = end - timedelta(days=1)
        elif period != "all":
            days = {"7d": 7, "30d": 30, "90d": 90, "365d": 365, "year": 365}[period]
            cutoff = now - timedelta(days=days)

        def in_selected_period(query, column):
            if start is not None and end is not None:
                return query.where(column >= start, column < end)
            if cutoff is not None:
                return query.where(column >= cutoff)
            return query

        form_status_rows = db.execute(
            select(FormRecord.status, func.count(FormRecord.id)).group_by(FormRecord.status)
        ).all()
        form_status = {str(status): int(count) for status, count in form_status_rows}
        forms_created = int(db.scalar(in_selected_period(
            select(func.count(FormRecord.id)), FormRecord.created_at
        )) or 0)

        response_query = in_selected_period(select(
            FormResponseRecord.status, func.count(FormResponseRecord.id)
        ).group_by(FormResponseRecord.status), FormResponseRecord.created_at)
        response_status = {
            str(status): int(count) for status, count in db.execute(response_query).all()
        }

        account_total = None
        role_counts = None
        if has_permission(role, "us_view"):
            account_total = int(db.scalar(select(func.count(AccountRecord.id))) or 0)
            role_counts = {
                str(role_key): int(count)
                for role_key, count in db.execute(
                    select(AccountRoleRecord.role, func.count(AccountRoleRecord.account_id))
                    .group_by(AccountRoleRecord.role)
                ).all()
            }

        review_kinds = [
            kind for kind in ("profile_review", "receipt_review")
            if has_permission(role, workflow_permission(kind))
        ]
        reviews_by_kind: dict[str, dict[str, int]] = {}
        if review_kinds:
            review_query = select(
                AdminTaskRecord.kind,
                AdminTaskRecord.status,
                func.count(AdminTaskRecord.id),
            ).where(AdminTaskRecord.kind.in_(review_kinds)).group_by(
                AdminTaskRecord.kind, AdminTaskRecord.status
            )
            review_query = in_selected_period(review_query, AdminTaskRecord.created_at)
            for kind, status, count in db.execute(review_query).all():
                reviews_by_kind.setdefault(str(kind), {})[str(status)] = int(count)

        notification_query = select(
            UserNotificationRecord.delivery_status,
            func.count(UserNotificationRecord.id),
        ).group_by(UserNotificationRecord.delivery_status)
        notification_query = in_selected_period(notification_query, UserNotificationRecord.created_at)
        notifications = {
            str(status): int(count) for status, count in db.execute(notification_query).all()
        }

        cooperation = None
        if has_permission(role, "sp_answer"):
            cooperation_query = select(
                CooperationRequestRecord.status,
                func.count(CooperationRequestRecord.id),
            ).group_by(CooperationRequestRecord.status)
            cooperation_query = in_selected_period(cooperation_query, CooperationRequestRecord.created_at)
            cooperation = {
                str(status): int(count) for status, count in db.execute(cooperation_query).all()
            }

        return {
            "source": "shared_server_database",
            "period": period,
            "generated_at": _utc_now().isoformat(),
            "forms": {
                "total": sum(form_status.values()),
                "created_in_period": forms_created,
                "by_status": form_status,
            },
            "responses": {
                "total": sum(response_status.values()),
                "by_status": response_status,
            },
            "accounts": {"total": account_total, "by_role": role_counts},
            "reviews": {
                "total": sum(sum(statuses.values()) for statuses in reviews_by_kind.values()),
                "by_kind": reviews_by_kind,
            },
            "notifications": {
                "total": sum(notifications.values()),
                "by_delivery_status": notifications,
            },
            "cooperation_requests": (
                None if cooperation is None else {
                    "total": sum(cooperation.values()),
                    "by_status": cooperation,
                }
            ),
            "coverage": {
                "financial_amounts": "not_included",
                "event_attendance": "not_in_shared_api_database",
                "club_records": "not_in_shared_api_database",
            },
        }

    def apply_admin_task_decision(
        db: Session,
        task: AdminTaskRecord,
        decision: str,
        reason: str,
        reviewer_id: str,
        reviewer_bale_user_id: str | None,
    ) -> AdminTaskRecord:
        if task.status != "pending":
            raise HTTPException(409, "workflow_already_reviewed")
        task_payload = task.payload if isinstance(task.payload, dict) else {}
        is_purchase_receipt = (
            task.kind == "receipt_review"
            and task_payload.get("purchase_source") == "recording_access"
        )
        is_public_form_receipt = (
            task.kind == "receipt_review"
            and task_payload.get("registration_source") == "public_form"
            and not is_purchase_receipt
        )
        linked_response = None
        if is_public_form_receipt:
            form_id = task_payload.get("form_id")
            response_id = task_payload.get("form_response_id")
            linked_response = db.scalar(
                select(FormResponseRecord)
                .join(
                    FormResponseDraftRecord,
                    FormResponseDraftRecord.id == FormResponseRecord.draft_id,
                )
                .where(
                    FormResponseRecord.id == response_id,
                    FormResponseRecord.form_id == form_id,
                    FormResponseRecord.status == "accepted",
                    FormResponseRecord.receipt_review_task_id == task.id,
                    FormResponseRecord.ticket_claimed_by_bale_user_id == task.bale_user_id,
                    FormResponseDraftRecord.bot_bale_user_id == task.bale_user_id,
                )
                .with_for_update()
            )
            if linked_response is None:
                raise HTTPException(409, "linked_public_form_response_unavailable")
        purchase_form: FormRecord | None = None
        if is_purchase_receipt:
            # Purchase receipts are tied to the buyer's web account, never to a Bale ticket claim.
            linked_response = db.scalar(
                select(FormResponseRecord)
                .join(FormResponseDraftRecord, FormResponseDraftRecord.id == FormResponseRecord.draft_id)
                .where(
                    FormResponseRecord.id == task_payload.get("form_response_id"),
                    FormResponseRecord.form_id == task_payload.get("form_id"),
                    FormResponseRecord.status == "accepted",
                    FormResponseRecord.receipt_review_task_id == task.id,
                    FormResponseDraftRecord.account_id == task.account_id,
                )
                .with_for_update()
            )
            if linked_response is None:
                raise HTTPException(409, "linked_public_form_response_unavailable")
            purchase_form = db.get(FormRecord, linked_response.form_id)
            if purchase_form is None or not _form_is_purchase(purchase_form):
                raise HTTPException(409, "linked_public_form_response_unavailable")
        now = _utc_now()
        result = db.execute(
            update(AdminTaskRecord)
            .where(
                AdminTaskRecord.id == task.id,
                AdminTaskRecord.status == "pending",
                AdminTaskRecord.version == task.version,
            )
            .values(
                status=decision,
                review_reason=reason or None,
                reviewed_by=reviewer_id,
                reviewed_by_bale_user_id=reviewer_bale_user_id,
                reviewed_at=now,
                updated_at=now,
                version=AdminTaskRecord.version + 1,
            )
        )
        if cast(CursorResult[Any], result).rowcount != 1:
            db.rollback()
            raise HTTPException(409, "workflow_version_conflict")
        db.flush()
        if (is_public_form_receipt or is_purchase_receipt) and linked_response is not None:
            payment_record = db.scalar(
                select(FormPaymentRecord)
                .where(FormPaymentRecord.response_id == linked_response.id)
                .with_for_update()
            )
            if payment_record is not None and payment_record.method == "card_transfer":
                payment_record.status = "paid_manual" if decision == "approved" else "rejected"
                payment_record.updated_at = now
        # Reviewer identity as recorded on the task: the owner id (web or bot owner) or a staff account id.
        actor_kind = audit_mod.ACTOR_OWNER if reviewer_id == settings.owner_id else audit_mod.ACTOR_ACCOUNT
        purchase_actor = (actor_kind, reviewer_id)
        if is_purchase_receipt and linked_response is not None and purchase_form is not None:
            payment_record = db.scalar(
                select(FormPaymentRecord).where(FormPaymentRecord.response_id == linked_response.id)
            )
            if decision == "approved":
                if payment_record is None or payment_record.status != "paid_manual":
                    raise HTTPException(409, "linked_public_form_response_unavailable")
                order, _access = _finalize_purchase(
                    db, form=purchase_form, response=linked_response, payment=payment_record,
                    account_id=task.account_id, now=now, actor=purchase_actor, reason=reason or "receipt_approved",
                )
            else:
                order = _reject_purchase(db, response=linked_response, reason=reason or "receipt_rejected", now=now, actor=purchase_actor)
            audit_mod.record_admin_event(
                db, actor_kind=actor_kind, actor_id=reviewer_id, actor_role="",
                action="recording.order.approve" if decision == "approved" else "recording.order.reject",
                target_type="recording_order", target_id=order.id if order is not None else "",
                details={
                    "task_id": task.id, "form_id": purchase_form.id, "recording_id": purchase_form.recording_id,
                    "account_id": task.account_id, "amount": int(payment_record.amount) if payment_record else None,
                    "status_after": order.status if order is not None else "", "reason": reason, "via": "inbox",
                },
            )
        if (is_public_form_receipt or is_purchase_receipt) and decision == "rejected" and linked_response is not None:
            draft = linked_response.draft
            if draft is not None:
                draft.answers = {}
                draft.companions = []
                draft.bot_bale_user_id = None
            db.delete(linked_response)
            db.flush()
        target_kind = task.kind.removesuffix("_review") + ("_approved" if decision == "approved" else "_rejected")
        approved = decision == "approved"
        if is_purchase_receipt and approved:
            # The access grant already queued «دسترسی فعال شد»; a second message would be noise.
            updated_task = db.get(AdminTaskRecord, task.id)
            if updated_task is None:
                raise HTTPException(404, "admin_task_not_found")
            return updated_task
        if task.kind == "profile_review":
            title = "پروفایل تأیید شد" if approved else "پروفایل نیاز به اصلاح دارد"
            body = "پروفایل شما ثبت شد." if approved else ("پروفایل شما تأیید نشد." + (" دلیل: " + reason if reason else ""))
        elif is_public_form_receipt:
            title = "ثبت‌نامت نهایی شد" if approved else "ثبت‌نامت لغو شد"
            body = (
                "ثبت‌نامت نهایی است و بلیتت در گفت‌وگوی بله در دسترسه."
                if approved else
                "ثبت‌نام قبلی لغو شد. اگر هنوز می‌خوای شرکت کنی، فرم رو دوباره پر کن."
            )
        elif is_purchase_receipt:
            product_title = str(task_payload.get("product_title") or "محتوای ضبط‌شده")
            title = "نتیجهٔ بررسی خرید محتوای ضبط‌شده"
            body = (
                f"رسید خرید «{product_title}» تأیید نشد." + (f"\nدلیل: {reason}" if reason else "")
                + "\nدر صورت نیاز می‌توانید از صفحهٔ همان رویداد دوباره فرم خرید را پر کنید."
            )
        else:
            title = "فیش پرداخت تأیید شد" if approved else "فیش پرداخت تأیید نشد"
            body = "رسید پرداخت شما تأیید شد." if approved else ("رسید پرداخت تأیید نشد." + (" دلیل: " + reason if reason else ""))
        notifications_mod.queue(
            db, account_id=task.account_id, kind=target_kind, title=title, body=body,
            key=notifications_mod.dedupe_key("admin_task", task.id, target_kind),
            bale_ids=[task.bale_user_id] if task.bale_user_id else [],
            link=notifications_mod.account_link("registrations") if is_public_form_receipt
            else notifications_mod.account_link("orders") if is_purchase_receipt else None,
            file_refs=[] if (is_public_form_receipt or is_purchase_receipt) else list(task_payload.get("file_refs", [])),
            source_task_id=task.id,
        )
        updated_task = db.get(AdminTaskRecord, task.id)
        if updated_task is None:
            raise HTTPException(404, "admin_task_not_found")
        return updated_task


    @app.post(CSP_REPORT_PATH, status_code=204)
    async def csp_report(request: Request) -> Response:
        """Report sink for the frame-src policy (phase 9.6 §8): one PII-free WARNING line per violation.

        Accepts the browser formats ``application/csp-report`` (``{"csp-report": {...}}``) and
        ``application/reports+json`` (list of ``{"type": "csp-violation", "body": {...}}``). Nothing is
        stored; ``document-uri`` is reduced to its path and ``blocked-uri`` to its origin, so no query
        string, token or member identifier ever reaches the log. Operators read the journal.
        """
        raw = await request.body()
        if len(raw) > CSP_REPORT_MAX_BYTES:
            raise HTTPException(413, "request_too_large")
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else None
        except (UnicodeDecodeError, ValueError):
            raise HTTPException(400, "invalid_csp_report") from None
        bodies: list[dict[str, Any]] = []
        if isinstance(payload, dict) and isinstance(payload.get("csp-report"), dict):
            bodies.append(payload["csp-report"])
        elif isinstance(payload, list):
            bodies.extend(item["body"] for item in payload[:20]
                          if isinstance(item, dict) and item.get("type") == "csp-violation" and isinstance(item.get("body"), dict))
        else:
            raise HTTPException(400, "invalid_csp_report")
        for body in bodies:
            csp_logger.warning("csp_violation %s", json.dumps(_csp_report_summary(body), ensure_ascii=False, sort_keys=True))
        return Response(status_code=204)

    @app.get("/api/health")
    def health(request: Request):
        factory = request.app.state.session_factory
        if factory is None:
            return JSONResponse(
                {
                    "ok": False,
                    "mode": "same-application",
                    "deliveryEnabled": False,
                    "formsEnabled": False,
                    "responsesEnabled": False,
                    "workflowEnabled": False,
                    "notificationQueueEnabled": False,
                    "privateFileStorageEnabled": False,
                    "formBalePaymentsReady": False,
                },
                status_code=503,
            )
        try:
            with factory() as db:
                db.execute(text("SELECT 1 FROM forms LIMIT 1"))
                db.execute(text("SELECT 1 FROM owner_sessions LIMIT 1"))
                db.execute(text("SELECT 1 FROM form_response_drafts LIMIT 1"))
                db.execute(text("SELECT 1 FROM form_responses LIMIT 1"))
                db.execute(text("SELECT 1 FROM form_payments LIMIT 1"))
                db.execute(text("SELECT 1 FROM form_payment_transactions LIMIT 1"))
                db.execute(text("SELECT 1 FROM public_write_throttles LIMIT 1"))
                db.execute(text("SELECT 1 FROM cooperation_requests LIMIT 1"))
                db.execute(text("SELECT 1 FROM site_content LIMIT 1"))
                db.execute(text("SELECT 1 FROM accounts LIMIT 1"))
                db.execute(text("SELECT 1 FROM platform_identities LIMIT 1"))
                db.execute(text("SELECT 1 FROM account_sessions LIMIT 1"))
                db.execute(text("SELECT 1 FROM miniapp_auth_replays LIMIT 1"))
                db.execute(text("SELECT 1 FROM account_roles LIMIT 1"))
                db.execute(text("SELECT 1 FROM manager_credentials LIMIT 1"))
                db.execute(text("SELECT 1 FROM admin_tasks LIMIT 1"))
                db.execute(text("SELECT 1 FROM user_notifications LIMIT 1"))
                db.execute(text("SELECT 1 FROM private_files LIMIT 1"))
                payments_ready = _runtime_settings(db, request.app.state.settings).form_bale_payments_ready
        except SQLAlchemyError:
            return JSONResponse(
                {
                    "ok": False,
                    "mode": "same-application",
                    "deliveryEnabled": False,
                    "formsEnabled": False,
                    "responsesEnabled": False,
                    "workflowEnabled": False,
                    "notificationQueueEnabled": False,
                    "privateFileStorageEnabled": False,
                    "formBalePaymentsReady": False,
                },
                status_code=503,
            )
        return {
            "ok": True,
            "mode": "same-application",
            "deliveryEnabled": False,
            "formsEnabled": True,
            "responsesEnabled": True,
            "workflowEnabled": True,
            "notificationQueueEnabled": True,
            "privateFileStorageEnabled": True,
            "formBalePaymentsReady": payments_ready,
        }

    @app.get("/api/public/forms/capabilities")
    def form_capabilities(request: Request):
        """Read-only, secret-free feature contract for the web form builder."""
        cfg: Settings = request.app.state.settings
        factory = request.app.state.session_factory
        bale_wallet_ready = False
        if factory is not None:
            try:
                with factory() as db:
                    bale_wallet_ready = _runtime_settings(db, cfg).form_bale_payments_ready
            except SQLAlchemyError:
                bale_wallet_ready = False
        return public_form_capabilities(
            api_configured=factory is not None,
            bale_wallet_ready=bale_wallet_ready,
        )

    def _site_content_response(
        db: Session, content: dict[str, Any], version: int, updated_at: datetime | None, *, owner_view: bool = False
    ):
        public = public_site_content(content)
        now = _utc_now()
        if owner_view:
            try:
                public["banners"] = sanitize_site_content(
                    {"banners": content.get("banners", [])}, partial=True
                ).get("banners", [])
            except SiteContentError:
                public["banners"] = []
        cfg: Settings = _runtime_settings(db, app.state.settings)
        published_forms: Sequence[FormRecord] = db.scalars(
            select(FormRecord)
            .options(selectinload(FormRecord.fields))
            .where(FormRecord.owner_id == cfg.owner_id, FormRecord.status == "published")
        ).all()
        by_id = {
            form.id: form for form in published_forms
            if not publication_issues(form, bale_ready=cfg.form_bale_payments_ready)
        }
        public_form_ids = set(by_id)
        for event in public["events"]:
            declared = {str(item.get("id")) for item in event.get("forms", []) if item.get("id")}
            if event.get("regForm"):
                declared.add(str(event["regForm"]))
            related = []
            for form in published_forms:
                settings_value = form.settings if isinstance(form.settings, dict) else {}
                if form.id not in by_id or form.need != "reg" or settings_value.get("eventVisible") is False:
                    continue
                if _form_is_purchase(form):
                    continue
                if form.event_id and str(form.event_id) != str(event.get("id")):
                    continue
                if str(form.event_id or "") == str(event.get("id")) or form.id in declared:
                    related.append({"id": form.id, "need": form.need, "n": form.title})
            event["forms"] = related
            event.pop("regForm", None)
            # Registration state is computed once here (server clock, linked published form,
            # that form's real capacity) and re-used by the home/list/detail pages and banners.
            primary = by_id.get(related[0]["id"]) if related else None
            form_full = False
            if primary is not None:
                accepted, waitlisted = _response_counts(db, primary.id)
                form_full = _capacity_is_full(
                    primary, accepted + _active_bale_payment_holds(db, primary.id), waitlisted
                )
            event["registration"] = event_time.registration_state(
                event, now=now, has_form=primary is not None, form_full=form_full
            )
        cards = _recording_cards(db, [str(event.get("id")) for event in public["events"] if event.get("id")])
        for event in public["events"]:
            card = cards.get(str(event.get("id")))
            if card is not None:
                event["recording"] = card
        public["banners"] = _public_banner_rows(public["banners"], public["events"], now, owner_view=owner_view)
        for person in public["people"]:
            form_id = str(person.get("form") or "")
            if form_id and form_id not in public_form_ids:
                person["form"] = ""
        public["cooperation"] = [
            {"formId": form_id}
            for record in public["cooperation"][:1]
            if (form_id := str(record.get("formId") or "")) in by_id
            and by_id[form_id].need == "other"
        ]
        bot_username = cfg.bale_bot_username
        delivery_bot_url = f"https://ble.ir/{bot_username}" if re.fullmatch(r"[A-Za-z0-9_]{3,64}", bot_username) else ""
        return {
            "content": public,
            "version": version,
            "updated_at": _as_utc(updated_at).isoformat() if updated_at else None,
            "delivery_bot_url": delivery_bot_url,
            # Reference clock for every countdown; browsers only measure the offset to it.
            "server_time": event_time.to_iso(now),
        }

    def _public_banner_rows(
        banners: list[dict[str, Any]], events: list[dict[str, Any]], now: datetime, *, owner_view: bool
    ) -> list[dict[str, Any]]:
        """Resolve event-linked banners and apply the publish window on the server clock.

        Owner view keeps every row (the editor needs drafts and expired rows) but still
        attaches the resolved event so the panel preview matches the public page.
        """
        by_event = {str(event.get("id")): event for event in events if isinstance(event, dict)}
        rows: list[dict[str, Any]] = []
        for banner in banners:
            if not isinstance(banner, dict):
                continue
            row = dict(banner)
            event = by_event.get(str(row.get("eventId") or "")) if row.get("eventId") else None
            if row.get("eventId") and event is None and not owner_view:
                # Linked event is unpublished/missing: never show a banner that points at it.
                continue
            countdown = str(row.get("countdown") or "")
            resolved, target, expired = "", "", False
            if event is not None:
                registration = event.get("registration") or {}
                state = str(registration.get("state") or "")
                row["event"] = {
                    "id": event.get("id"), "t": event.get("t"), "when": event.get("when"),
                    "startsAt": event.get("startsAt") or "", "regClosesAt": event.get("regClosesAt") or "",
                    "state": state, "lifecycle": registration.get("lifecycle") or "scheduled",
                }
                recording_card = event.get("recording") if isinstance(event.get("recording"), dict) else None
                if recording_card is not None and recording_card.get("sellable"):
                    # The banner of a recorded product leads to its sales section; a countdown
                    # (registration/start) would be a lie for a held event.
                    row["event"]["recording"] = {"sellable": True, "price": recording_card.get("price", 0)}
                    row["href"] = f"event.html?id={event.get('id')}#recording"
                    countdown = ""
                if not row.get("href"):
                    row["href"] = f"event.html?id={event.get('id')}"
                if countdown == "reg_close":
                    if state == "open":
                        resolved, target = "reg_close", str(registration.get("countdownTo") or "")
                    elif state == "not_started":
                        resolved, target = "reg_open", str(registration.get("opensAt") or "")
                    else:
                        resolved, expired = "reg_close", state in {"closed", "full", "ended", "cancelled"}
                elif countdown == "event_start":
                    resolved = "event_start"
                    starts = event_time.parse_utc(event.get("startsAt"))
                    if registration.get("lifecycle") == "cancelled":
                        expired = True
                    elif starts is not None:
                        target, expired = (event_time.to_iso(starts), False) if starts > now else ("", True)
                    else:
                        resolved = ""
            if countdown == "campaign_end":
                ends_at = event_time.parse_utc(row.get("campaignEndsAt"))
                if ends_at is not None:
                    resolved = "campaign_end"
                    target, expired = (event_time.to_iso(ends_at), False) if ends_at > now else ("", True)
            # Only a real server-validated target (or a finished deadline) survives; the
            # client never computes its own deadline from banner text.
            row["countdown"] = resolved
            row["countdownTo"] = target if resolved and not expired else ""
            row["countdownEnded"] = bool(resolved) and expired
            if not owner_view:
                starts = event_time.parse_utc(row.get("startsAt"))
                ends = event_time.parse_utc(row.get("endsAt"))
                if (starts and starts > now) or (ends and ends <= now):
                    continue
                if row["countdownEnded"] and row.get("afterEnd", "hide") == "hide":
                    continue
                if row["countdownEnded"] and event is not None:
                    # After the deadline the primary action may only lead to the detail page.
                    row["href"] = f"event.html?id={event.get('id')}"
            rows.append(row)
        return rows

    @app.get("/api/public/site-content")
    def get_public_site_content(db: Session = Depends(get_db)):
        record = db.get(SiteContentRecord, "public")
        if record is None:
            raise HTTPException(404, "site_content_not_published")
        return _site_content_response(db, record.content or {}, record.version, record.updated_at)

    @app.get("/api/owner/site-content")
    def get_owner_site_content(
        _identity: OwnerIdentity = Depends(require_owner),
        db: Session = Depends(get_db),
    ):
        record = db.get(SiteContentRecord, "public")
        if record is None:
            return _site_content_response(db, {key: [] for key in CONTENT_KEYS}, 0, None, owner_view=True)
        return _site_content_response(db, record.content or {}, record.version, record.updated_at, owner_view=True)

    def _rejected_content_rows(raw_content: Any, accepted: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        """Rows of the raw payload that the sanitiser did not keep, per category, with the reason."""
        rejected: dict[str, list[dict[str, Any]]] = {}
        if not isinstance(raw_content, dict):
            return rejected
        for key in CONTENT_KEYS:
            if key not in accepted or not isinstance(raw_content.get(key), list):
                continue
            kept_ids = {str(row.get("id")) for row in accepted[key] if isinstance(row, dict) and row.get("id")}
            missing: list[dict[str, Any]] = []
            for index, row in enumerate(raw_content[key]):
                row_id = str(row.get("id") or "")[:100] if isinstance(row, dict) else ""
                if row_id and row_id in kept_ids:
                    continue
                reason = "invalid_row" if not isinstance(row, dict) else (
                    "non_public" if not is_public_content_row(row) else "missing_required_fields"
                )
                missing.append({"index": index, "id": row_id, "reason": reason})
            if missing:
                rejected[key] = missing[:100]
        return rejected

    @app.patch("/api/owner/site-content")
    async def update_owner_site_content(
        request: Request,
        _identity: OwnerIdentity = Depends(require_owner_write),
        db: Session = Depends(get_db),
    ):
        payload = await _read_json_object(request, 8 * 1024 * 1024)
        if set(payload) != {"content", "expected_version"}:
            raise HTTPException(400, "invalid_site_content_request")
        expected_version = payload.get("expected_version")
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 0:
            raise HTTPException(422, "invalid_site_content_version")
        try:
            incoming = sanitize_site_content(payload.get("content"), partial=True)
        except SiteContentError as error:
            raise HTTPException(422, {"code": str(error)}) from None
        if not incoming:
            raise HTTPException(422, "empty_site_content_update")
        # H1 (additive diagnostic): the allow-list sanitiser silently skips rows it cannot publish
        # (missing id/name, hidden/draft flags). Report them back so an editor never mistakes a
        # dropped row for a saved one; nothing about what is stored changes.
        rejected_rows = _rejected_content_rows(payload.get("content"), incoming)
        record = db.get(SiteContentRecord, "public")
        current_version = record.version if record else 0
        if expected_version != current_version:
            raise HTTPException(409, {
                "code": "site_content_version_conflict",
                "current_version": current_version,
            })
        current: dict[str, Any] = {key: list((record.content or {}).get(key, [])) for key in CONTENT_KEYS} if record else {
            key: [] for key in CONTENT_KEYS
        }
        current["banner_settings"] = public_site_content(record.content or {}).get("banner_settings") if record else {
            "enabled": True, "auto_rotate": False, "interval_seconds": 7, "show_controls": True
        }
        for key in NON_PUBLIC_RETAINED_KEYS:
            if key in incoming:
                incoming[key] = retain_non_public_rows(current.get(key), incoming[key])
        # H1: a whole-category replace of people/partners must not drop a row that an event or
        # article of the same document still links to (mirror of the B1 ``unknown_reference`` rule).
        for category in ("people", "partners"):
            if category not in incoming:
                continue
            in_use, used_by = content_admin_mod.removed_references_in_use(
                category, current.get(category), incoming[category], current
            )
            if in_use:
                raise HTTPException(422, {
                    "code": "reference_in_use", "field": category, "ids": in_use, "used_by": used_by,
                })
        # Owner decision 1405/08/01 (history tab): people/partners are edited as a whole category,
        # so one extra audit row per changed person makes that person's history filterable by id
        # (target ``content.people``/``content.partners``), the same way event/article rows are.
        row_audits: list[tuple[str, str, str, str]] = []
        for category in ("people", "partners"):
            if category in incoming:
                for action, row_id, title in content_admin_mod.row_changes(current.get(category), incoming[category]):
                    row_audits.append((category, action, row_id, title))
        current.update(incoming)
        if record is None:
            record = SiteContentRecord(id="public", content=current, version=1)
            db.add(record)
        else:
            record.content = current
            record.version = current_version + 1
            record.updated_at = _utc_now()
        record_audit(
            db, _identity, "site_content.update", target_type="site_content", target_id="public",
            details={"keys": ",".join(sorted(str(key) for key in incoming))[:160], "version": current_version + 1},
        )
        for category, action, row_id, title in row_audits[:200]:
            record_audit(
                db, _identity, action, target_type=f"content.{category}", target_id=row_id,
                details={"kind": category, "title": title, "version": current_version + 1},
            )
        db.commit()
        db.refresh(record)
        result = _site_content_response(db, record.content or {}, record.version, record.updated_at, owner_view=True)
        result["rejected_rows"] = rejected_rows
        return result

    # ── مدیریت رکوردی رویداد و مطلب روی همان سند site_content ──
    # منبع حقیقت همان سند است؛ این مسیرها فقط چرخهٔ «پیش‌نویس/منتشر/متوقف/بایگانی»
    # را روی ردیف‌ها می‌افزایند. ویرایش/ساخت با ev_create و تغییر وضعیت با ev_publish.
    _CONTENT_KIND = r"^(events|articles)$"
    _CONTENT_EDIT_PERMS = ("ev_create",)
    _CONTENT_PUBLISH_PERMS = ("ev_publish",)

    def _content_rows(record: SiteContentRecord | None, kind: str) -> list[Any]:
        return list(((record.content if record else None) or {}).get(kind) or [])

    def _content_kind(kind: str) -> str:
        if kind not in content_admin_mod.KINDS:
            raise HTTPException(404, "content_kind_not_found")
        return kind

    def _content_error(error: content_admin_mod.ContentAdminError) -> HTTPException:
        return HTTPException(422, {"code": error.code, "field": error.field})

    def _content_has_form(db: Session, kind: str, row: dict[str, Any]) -> bool | None:
        """Same link rule as the public snapshot: declared on the row or a published
        registration form with ``event_id`` = this event (so panel state == public state)."""
        if kind != "events":
            return None
        if row.get("forms"):
            return True
        event_id = str(row.get("id") or "")
        if not event_id:
            return False
        return db.scalar(
            select(FormRecord.id)
            .where(
                FormRecord.event_id == event_id, FormRecord.status == "published", FormRecord.need == "reg",
                FormRecord.purpose == "registration",
            )
            .limit(1)
        ) is not None

    def _content_registration_summary(db: Session, kind: str, item: dict[str, Any]) -> dict[str, Any] | None:
        """Panel audit 1405/08/01 (A6): capacity/registered for an event card, from the primary linked
        published registration form (same rule as the public snapshot) and real ``form_responses``
        counts. Aggregates only (no registrant data). ``None`` when no published form is linked."""
        if kind != "events":
            return None
        event_id = str(item.get("id") or "")
        if not event_id:
            return None
        declared = [str(form.get("id") or "") for form in (item.get("forms") or []) if isinstance(form, dict)]
        candidates = db.scalars(
            select(FormRecord)
            .where(FormRecord.status == "published", FormRecord.need == "reg", FormRecord.purpose == "registration")
            .where(or_(FormRecord.event_id == event_id, FormRecord.id.in_(declared)) if declared else FormRecord.event_id == event_id)
        ).all()
        primary = None
        for form in candidates:
            if _form_is_purchase(form) or (form.event_id and str(form.event_id) != event_id):
                continue
            if primary is None or (form.id in declared and primary.id not in declared):
                primary = form
        if primary is None:
            return None
        settings_value = primary.settings if isinstance(primary.settings, dict) else {}
        accepted, waitlisted = _response_counts(db, primary.id)
        cap = _count_setting(settings_value.get("cap", 0))
        wait = _count_setting(settings_value.get("wait", 0))
        return {
            "form_id": primary.id,
            "form_name": primary.title,
            "accepted": accepted,
            "waitlisted": waitlisted,
            "cap": cap,
            "wait": wait,
            "full": _capacity_is_full(primary, accepted, waitlisted),
            "source": "form_responses",
        }

    def _content_record_response(
        record: SiteContentRecord, kind: str, row: dict[str, Any], *, saved: bool = False, db: Session | None = None
    ) -> dict[str, Any]:
        out = {
            "kind": kind,
            "record": content_admin_mod.detail(kind, row, has_form=_content_has_form(db, kind, row) if db is not None else None),
            "version": record.version,
            "updated_at": _as_utc(record.updated_at).isoformat() if record.updated_at else None,
            "saved": saved,
        }
        if kind == "events" and db is not None:
            # B19: configured reminder slots, when they fire and what the outbox holds (read model; sending is the timer's job).
            out["reminders"] = event_reminders_mod.preview(db, row, _utc_now(), is_purchase=_form_is_purchase)
        return out

    async def _content_write_payload(request: Request, db: Session, *, need_record: bool) -> tuple[dict[str, Any], SiteContentRecord]:
        payload = await _read_json_object(request, 4 * 1024 * 1024)
        allowed = {"record", "expected_version", "status"} if need_record else {"status", "expected_version"}
        if not set(payload) <= allowed or "expected_version" not in payload or (need_record and "record" not in payload):
            raise HTTPException(400, "invalid_content_request")
        expected_version = payload.get("expected_version")
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 0:
            raise HTTPException(422, "invalid_site_content_version")
        record = db.get(SiteContentRecord, "public")
        current_version = record.version if record else 0
        if expected_version != current_version:
            raise HTTPException(409, {"code": "site_content_version_conflict", "current_version": current_version})
        if record is None:
            record = SiteContentRecord(id="public", content={key: [] for key in CONTENT_KEYS}, version=0)
            db.add(record)
        return payload, record

    def _content_store(record: SiteContentRecord, kind: str, rows: list[Any]) -> None:
        current: dict[str, Any] = {key: list((record.content or {}).get(key, [])) for key in CONTENT_KEYS}
        if isinstance((record.content or {}).get("banner_settings"), dict):
            current["banner_settings"] = dict((record.content or {})["banner_settings"])
        current[kind] = rows
        record.content = current
        record.version = (record.version or 0) + 1
        record.updated_at = _utc_now()

    @app.get("/api/admin/content/{kind}")
    def list_admin_content(
        kind: str,
        response: Response,
        q: str = Query(default="", max_length=80),
        status: str = Query(default="", pattern=r"^(|draft|published|paused|archived)$"),
        sort: str = Query(default="updated", pattern=r"^(updated|created|title|date)$"),
        order: str = Query(default="desc", pattern=r"^(asc|desc)$"),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=100_000),
        when: str = Query(default="", pattern=r"^(|today|upcoming|past)$"),
        mode: str = Query(default="", max_length=80),
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission(*_CONTENT_EDIT_PERMS, *_CONTENT_PUBLISH_PERMS)),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        kind = _content_kind(kind)
        record = db.get(SiteContentRecord, "public")
        try:
            result = content_admin_mod.list_records(
                kind, _content_rows(record, kind), q=q, status=status, sort=sort, order=order, limit=limit, offset=offset,
                when=when, mode=mode,
            )
        except content_admin_mod.ContentAdminError as error:
            raise _content_error(error) from None
        if kind == "events":
            for item in result["items"]:
                item["registration"] = _content_registration_summary(db, kind, item)
        role = ROLE_OWNER if isinstance(identity, OwnerIdentity) else identity.role
        result.update({
            "kind": kind,
            "version": record.version if record else 0,
            "source": "site_content",
            "can_edit": has_permission(role, "ev_create"),
            "can_publish": has_permission(role, "ev_publish"),
            "q": q,
            "status": status,
            "sort": sort,
            "order": order,
        })
        return result

    @app.get("/api/admin/content/{kind}/{record_id}")
    def get_admin_content_record(
        kind: str,
        record_id: str,
        response: Response,
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission(*_CONTENT_EDIT_PERMS, *_CONTENT_PUBLISH_PERMS)),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        kind = _content_kind(kind)
        record = db.get(SiteContentRecord, "public")
        found = content_admin_mod.find_row(_content_rows(record, kind), record_id)
        if record is None or found is None:
            raise HTTPException(404, "content_record_not_found")
        return _content_record_response(record, kind, found[1], db=db)

    @app.post("/api/admin/content/{kind}")
    async def create_admin_content_record(
        kind: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_CONTENT_EDIT_PERMS)),
        db: Session = Depends(get_db),
    ):
        kind = _content_kind(kind)
        payload, record = await _content_write_payload(request, db, need_record=True)
        status = payload.get("status", "draft")
        if status not in {"draft", "published"}:
            raise HTTPException(422, {"code": "invalid_status", "field": "status"})
        role = ROLE_OWNER if isinstance(identity, OwnerIdentity) else identity.role
        if status == "published" and not has_permission(role, "ev_publish"):
            raise HTTPException(403, "permission_denied")
        rows = _content_rows(record, kind)
        try:
            content_admin_mod.ensure_capacity(kind, rows)
            record_id = content_admin_mod.new_record_id(kind)
            while content_admin_mod.find_row(rows, record_id):
                record_id = content_admin_mod.new_record_id(kind)
            row = content_admin_mod.build_record(
                kind, payload.get("record"), existing=None, record_id=record_id, status=status,
                references=content_admin_mod.reference_ids(record.content),
            )
        except content_admin_mod.ContentAdminError as error:
            raise _content_error(error) from None
        rows.append(row)
        _content_store(record, kind, rows)
        record_audit(
            db, identity, "content.create", target_type=f"content.{kind}", target_id=record_id,
            details={"kind": kind, "title": str(row.get("t") or "")[:120], "status": status, "version": record.version},
        )
        db.commit()
        db.refresh(record)
        return _content_record_response(record, kind, row, saved=True, db=db)

    @app.put("/api/admin/content/{kind}/{record_id}")
    async def update_admin_content_record(
        kind: str,
        record_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_CONTENT_EDIT_PERMS)),
        db: Session = Depends(get_db),
    ):
        kind = _content_kind(kind)
        payload, record = await _content_write_payload(request, db, need_record=True)
        if "status" in payload:
            raise HTTPException(400, "invalid_content_request")
        rows = _content_rows(record, kind)
        found = content_admin_mod.find_row(rows, record_id)
        if found is None:
            raise HTTPException(404, "content_record_not_found")
        index, existing = found
        current_status = content_admin_mod.status_of(existing)
        try:
            row = content_admin_mod.build_record(
                kind, payload.get("record"), existing=existing, record_id=record_id, status=current_status,
                references=content_admin_mod.reference_ids(record.content),
            )
        except content_admin_mod.ContentAdminError as error:
            raise _content_error(error) from None
        rows[index] = row
        _content_store(record, kind, rows)
        record_audit(
            db, identity, "content.update", target_type=f"content.{kind}", target_id=record_id,
            details={"kind": kind, "title": str(row.get("t") or "")[:120], "status": current_status, "version": record.version},
        )
        db.commit()
        db.refresh(record)
        return _content_record_response(record, kind, row, saved=True, db=db)

    @app.post("/api/admin/content/{kind}/{record_id}/status")
    async def set_admin_content_status(
        kind: str,
        record_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_CONTENT_PUBLISH_PERMS)),
        db: Session = Depends(get_db),
    ):
        kind = _content_kind(kind)
        payload, record = await _content_write_payload(request, db, need_record=False)
        status = payload.get("status")
        if not isinstance(status, str) or status not in content_admin_mod.STATUSES:
            raise HTTPException(422, {"code": "invalid_status", "field": "status"})
        rows = _content_rows(record, kind)
        found = content_admin_mod.find_row(rows, record_id)
        if found is None:
            raise HTTPException(404, "content_record_not_found")
        index, existing = found
        previous = content_admin_mod.status_of(existing)
        try:
            row = content_admin_mod.apply_status(kind, existing, status)
        except content_admin_mod.ContentAdminError as error:
            raise _content_error(error) from None
        rows[index] = row
        _content_store(record, kind, rows)
        record_audit(
            db, identity, "content.status", target_type=f"content.{kind}", target_id=record_id,
            details={"kind": kind, "title": str(row.get("t") or "")[:120], "from": previous, "status": status, "version": record.version},
        )
        db.commit()
        db.refresh(record)
        return _content_record_response(record, kind, row, saved=True, db=db)

    # ── فهرست کاربران برای مدیران دارای us_view (جدا از «حساب‌ها و نقش‌ها») ──
    # فقط دادهٔ غیرمحرمانه: نام نمایشی پروفایل، نوع ورود، نقش، شمارش سوابق.
    # شمارهٔ تلفن (که فقط digest آن ذخیره است)، hash و توکن هرگز برنمی‌گردند.
    def _user_identity_summary(identities: Sequence[PlatformIdentityRecord]) -> dict[str, Any]:
        providers = sorted({item.provider for item in identities if item.provider in {"bale", "phone"}})
        bale_ids = [item.provider_user_id for item in identities if item.provider == "bale"]
        return {
            "providers": providers,
            "bale_user_id": bale_ids[0] if bale_ids else None,
            "linked": len(providers) > 1,
        }

    def _admin_user_row(
        db: Session, account: AccountRecord, *, role: str | None, profile: AccountProfileRecord | None,
        identities: Sequence[PlatformIdentityRecord], viewer_role: str | None,
    ) -> dict[str, Any]:
        fields = (profile.fields if profile is not None else {}) or {}
        registrations = int(db.scalar(
            select(func.count(FormResponseRecord.id))
            .join(FormResponseDraftRecord, FormResponseDraftRecord.id == FormResponseRecord.draft_id)
            .join(FormRecord, FormRecord.id == FormResponseRecord.form_id)
            .where(
                account_form_record_scope(db, account.id),
                FormResponseRecord.added_by_response_id.is_(None),
                FormRecord.model == "registration",
                FormRecord.purpose == "registration",
            )
        ) or 0)
        pending_reviews = int(db.scalar(
            select(func.count(AdminTaskRecord.id)).where(
                AdminTaskRecord.account_id == account.id, AdminTaskRecord.status == "pending"
            )
        ) or 0)
        row: dict[str, Any] = {
            "account_id": account.id,
            "display_name": str(fields.get("fullName") or "")[:120],
            "city": str(fields.get("city") or "")[:80],
            "province": str(fields.get("province") or "")[:80],
            "role": role,
            **_account_status_view(account),
            "created_at": _as_utc(account.created_at).isoformat(),
            "profile_updated_at": _as_utc(profile.updated_at).isoformat() if profile is not None else None,
            "registrations": registrations,
            "pending_reviews": pending_reviews,
        }
        row.update(_user_identity_summary(identities))
        if viewer_role == ROLE_OWNER:
            row["email"] = str(fields.get("email") or "")[:160]
        return row

    @app.get("/api/admin/users")
    def list_admin_users(
        response: Response,
        q: str = Query(default="", max_length=80),
        provider: str = Query(default="", pattern=r"^(|bale|phone|linked)$"),
        role_filter: str = Query(default="", alias="role", pattern=r"^(|assigned|none)$"),
        status: str = Query(default="", pattern=r"^(|active|blocked)$"),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission("us_view")),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        viewer_role = ROLE_OWNER if isinstance(identity, OwnerIdentity) else identity.role
        query = (
            select(AccountRecord, AccountRoleRecord, AccountProfileRecord)
            .outerjoin(AccountRoleRecord, AccountRoleRecord.account_id == AccountRecord.id)
            .outerjoin(AccountProfileRecord, AccountProfileRecord.account_id == AccountRecord.id)
            .where(AccountRecord.id.in_(
                select(PlatformIdentityRecord.account_id).where(PlatformIdentityRecord.provider.in_(("bale", "phone")))
            ))
        )
        if status:
            # Owner decision 1405/08/01: «مسدودها» is a server-side filter, never a client-side guess.
            query = query.where(AccountRecord.status == status)
        blocked_total = int(db.scalar(
            select(func.count(AccountRecord.id)).where(
                AccountRecord.status == ACCOUNT_STATUS_BLOCKED,
                AccountRecord.id.in_(
                    select(PlatformIdentityRecord.account_id).where(PlatformIdentityRecord.provider.in_(("bale", "phone")))
                ),
            )
        ) or 0)
        if role_filter == "assigned":
            query = query.where(AccountRoleRecord.role.is_not(None))
        elif role_filter == "none":
            query = query.where(AccountRoleRecord.role.is_(None))
        candidates = db.execute(query.order_by(AccountRecord.created_at.desc(), AccountRecord.id).limit(5000)).all()
        account_ids = [account.id for account, _role, _profile in candidates]
        identities_by_account: dict[str, list[PlatformIdentityRecord]] = {}
        if account_ids:
            for item in db.scalars(
                select(PlatformIdentityRecord).where(PlatformIdentityRecord.account_id.in_(account_ids))
            ).all():
                identities_by_account.setdefault(item.account_id, []).append(item)
        needle = unicodedata.normalize("NFKC", q or "").strip().lower()
        selected = []
        for account, role, profile in candidates:
            identities = identities_by_account.get(account.id, [])
            summary = _user_identity_summary(identities)
            if provider == "linked" and not summary["linked"]:
                continue
            if provider in {"bale", "phone"} and provider not in summary["providers"]:
                continue
            if needle:
                name = str(((profile.fields if profile is not None else {}) or {}).get("fullName") or "")
                haystack = " ".join(part for part in (
                    unicodedata.normalize("NFKC", name).lower(),
                    (summary["bale_user_id"] or "").lower(),
                    account.id.lower(),
                ) if part)
                if needle not in haystack:
                    continue
            selected.append((account, role, profile, identities))
        page = selected[offset: offset + limit]
        return {
            "source": "shared_server_database",
            "items": [
                _admin_user_row(
                    db, account, role=role.role if role is not None else None, profile=profile,
                    identities=identities, viewer_role=viewer_role,
                )
                for account, role, profile, identities in page
            ],
            "total": len(selected),
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < len(selected),
            "q": q,
            "provider": provider,
            "role": role_filter,
            "status": status,
            "blocked_total": blocked_total,
            "can_open_roles": viewer_role == ROLE_OWNER,
            "can_block": viewer_role == ROLE_OWNER,
            "can_note": has_permission(viewer_role, "us_notes"),
        }

    @app.get("/api/admin/users/{account_id}")
    def get_admin_user(
        account_id: str,
        request: Request,
        response: Response,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission("us_view")),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        cfg: Settings = request.app.state.settings
        viewer_role = ROLE_OWNER if isinstance(identity, OwnerIdentity) else identity.role
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", account_id or ""):
            raise HTTPException(404, "user_not_found")
        account = db.get(AccountRecord, account_id)
        identities = list(db.scalars(
            select(PlatformIdentityRecord).where(PlatformIdentityRecord.account_id == account_id)
        ).all()) if account is not None else []
        if account is None or not any(item.provider in {"bale", "phone"} for item in identities):
            raise HTTPException(404, "user_not_found")
        role = db.get(AccountRoleRecord, account_id)
        profile = db.get(AccountProfileRecord, account_id)
        row = _admin_user_row(
            db, account, role=role.role if role is not None else None, profile=profile,
            identities=identities, viewer_role=viewer_role,
        )
        registrations = db.execute(
            select(FormResponseRecord, FormPaymentRecord)
            .join(FormResponseDraftRecord, FormResponseDraftRecord.id == FormResponseRecord.draft_id)
            .join(FormRecord, FormRecord.id == FormResponseRecord.form_id)
            .outerjoin(FormPaymentRecord, FormPaymentRecord.response_id == FormResponseRecord.id)
            .where(
                account_form_record_scope(db, account_id),
                FormResponseRecord.added_by_response_id.is_(None),
                FormRecord.model == "registration",
                FormRecord.purpose == "registration",
            )
            .order_by(FormResponseRecord.created_at.desc(), FormResponseRecord.id.desc())
            .limit(50)
        ).all()
        registration_rows = []
        for record, payment in registrations:
            snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
            event = _json_dict_member(snapshot, "event")
            form_name = _ticket_text(snapshot.get("name") or "فرم ثبت‌نام", 160) or "فرم ثبت‌نام"
            registration_rows.append({
                "id": record.id,
                "form_id": record.form_id,
                "form_name": form_name,
                "event_title": _ticket_text(event.get("title") or form_name, 160) or form_name,
                "event_date": _ticket_text(event.get("date") or "", 120),
                "status": record.status,
                "payment_status": payment.status if payment is not None else None,
                "receipt_uploaded": record.receipt_review_task_id is not None or record.receipt_upload is not None,
                "ticket_checked_in": record.ticket_checked_in_at is not None,
                "created_at": _as_utc(record.created_at).isoformat(),
            })
        tasks = db.scalars(
            select(AdminTaskRecord)
            .where(AdminTaskRecord.account_id == account_id)
            .order_by(AdminTaskRecord.created_at.desc())
            .limit(50)
        ).all()
        row["reviews"] = [
            {
                "id": task.id,
                "kind": task.kind,
                "status": task.status,
                "created_at": _as_utc(task.created_at).isoformat(),
                "reviewed_at": _as_utc(task.reviewed_at).isoformat() if task.reviewed_at else None,
            }
            for task in tasks
        ]
        row["registration_items"] = registration_rows
        row["notifications"] = int(db.scalar(
            select(func.count(UserNotificationRecord.id)).where(UserNotificationRecord.account_id == account_id)
        ) or 0)
        row["last_session_at"] = (
            lambda value: _as_utc(value).isoformat() if value else None
        )(db.scalar(
            select(func.max(AccountSessionRecord.created_at)).where(AccountSessionRecord.account_id == account_id)
        ))
        if viewer_role == ROLE_OWNER:
            credential = db.get(ManagerCredentialRecord, account_id)
            row["manager_username"] = credential.username_key if credential is not None else None
        row["source"] = "shared_server_database"
        # Capabilities the panel may *show*; the server re-checks them on every write.
        is_owner_account = bool(cfg.owner_bale_user_id) and any(
            item.provider == "bale" and item.provider_user_id == cfg.owner_bale_user_id for item in identities
        )
        row["can_block"] = viewer_role == ROLE_OWNER and not is_owner_account
        row["can_note"] = has_permission(viewer_role, "us_notes")
        return row

    # ── U4 / U5: پروندهٔ یک حساب — ثبت‌نام‌های صفحه‌بندی‌شده، جزئیات یک پاسخ و اعلان‌های همان حساب ──
    # همان scope سروری پروندهٔ کاربر (``account_form_record_scope``) و همان جدول اعلان‌ها؛ شناسهٔ
    # مسیر فقط «کدام حساب» را می‌گوید و مجوز از نشست (``us_view``) می‌آید. پاسخ حساب دیگر → 404.
    _ADMIN_REGISTRATION_SCOPE_FILTERS = (
        FormResponseRecord.added_by_response_id.is_(None),
        FormRecord.model == "registration",
        FormRecord.purpose == "registration",
    )
    # Answers the panel never receives in clear text (same policy as the user directory and the
    # attendance list: no phone digits, no national id). Everything else is the member's own answer.
    _ADMIN_ANSWER_MASKED_TYPES = {"mobile": "mobile", "nid": "national_id"}
    # Notification kinds that are written for *many* accounts at once (fan-out) versus one account's
    # own decision/transaction. No «global»/«system» broadcast table exists; this is the whole set.
    _NOTIFICATION_AUDIENCE_KINDS = {notifications_mod.KIND_CONTENT_PUBLISHED, event_reminders_mod.KIND}

    def _admin_target_account(db: Session, account_id: str) -> AccountRecord:
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", account_id or ""):
            raise HTTPException(404, "user_not_found")
        account = db.get(AccountRecord, account_id)
        has_login = account is not None and db.scalar(
            select(PlatformIdentityRecord.id).where(
                PlatformIdentityRecord.account_id == account_id,
                PlatformIdentityRecord.provider.in_(("bale", "phone")),
            ).limit(1)
        ) is not None
        if account is None or not has_login:
            raise HTTPException(404, "user_not_found")
        return account

    def _admin_registration_summary(
        record: FormResponseRecord, payment: FormPaymentRecord | None, form_event_id: str | None
    ) -> dict[str, Any]:
        snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
        event = _json_dict_member(snapshot, "event")
        form_name = _ticket_text(snapshot.get("name") or "فرم ثبت‌نام", 160) or "فرم ثبت‌نام"
        return {
            "id": record.id,
            "form_id": record.form_id,
            "form_name": form_name,
            "event_id": str(form_event_id or "")[:120],
            "event_title": _ticket_text(event.get("title") or form_name, 160) or form_name,
            "event_date": _ticket_text(event.get("date") or "", 120),
            "status": record.status,
            "payment_status": payment.status if payment is not None else None,
            "receipt_uploaded": record.receipt_review_task_id is not None or record.receipt_upload is not None,
            "ticket_checked_in": record.ticket_checked_in_at is not None,
            "ticket_type": _form_response_ticket_type(record),
            "created_at": _as_utc(record.created_at).isoformat(),
        }

    @app.get("/api/admin/users/{account_id}/registrations")
    def list_admin_user_registrations(
        account_id: str,
        response: Response,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission("us_view")),
        db: Session = Depends(get_db),
    ):
        """U4 (list): the same rows as ``registration_items`` on the account file, paginated.

        Primary registrations only (companion rows hang off their primary); forms with
        ``model/purpose = registration``. Scope = the target account's own drafts plus legacy Bale
        drafts the server has verified for it — never a row that names another account.
        """
        response.headers["Cache-Control"] = "private, no-store"
        _admin_target_account(db, account_id)
        filters = (account_form_record_scope(db, account_id), *_ADMIN_REGISTRATION_SCOPE_FILTERS)
        total = int(db.scalar(
            select(func.count(FormResponseRecord.id))
            .join(FormResponseDraftRecord, FormResponseDraftRecord.id == FormResponseRecord.draft_id)
            .join(FormRecord, FormRecord.id == FormResponseRecord.form_id)
            .where(*filters)
        ) or 0)
        rows = db.execute(
            select(FormResponseRecord, FormPaymentRecord, FormRecord.event_id)
            .join(FormResponseDraftRecord, FormResponseDraftRecord.id == FormResponseRecord.draft_id)
            .join(FormRecord, FormRecord.id == FormResponseRecord.form_id)
            .outerjoin(FormPaymentRecord, FormPaymentRecord.response_id == FormResponseRecord.id)
            .where(*filters)
            .order_by(FormResponseRecord.created_at.desc(), FormResponseRecord.id.desc())
            .limit(limit + 1)
            .offset(offset)
        ).all()
        return {
            "source": "shared_server_database",
            "account_id": account_id,
            "items": [
                _admin_registration_summary(record, payment, form_event_id)
                for record, payment, form_event_id in rows[:limit]
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }

    @app.get("/api/admin/users/{account_id}/registrations/{response_id}")
    def get_admin_user_registration(
        account_id: str,
        response_id: str,
        response: Response,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission("us_view")),
        db: Session = Depends(get_db),
    ):
        """U4 (detail): one registration of *this* account with its labelled answers.

        The response is looked up **inside** the account's scope, so a response id that belongs to
        someone else is indistinguishable from a missing one (404). Answers are allow-listed by the
        field list frozen in ``form_snapshot`` (unknown keys are dropped); phone and national-id
        answers are masked; amounts/transaction ids appear only for a session that holds ``finance``.
        """
        response.headers["Cache-Control"] = "private, no-store"
        _admin_target_account(db, account_id)
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", response_id or ""):
            raise HTTPException(404, "registration_not_found")
        row = db.execute(
            select(FormResponseRecord, FormPaymentRecord, FormRecord.event_id)
            .join(FormResponseDraftRecord, FormResponseDraftRecord.id == FormResponseRecord.draft_id)
            .join(FormRecord, FormRecord.id == FormResponseRecord.form_id)
            .outerjoin(FormPaymentRecord, FormPaymentRecord.response_id == FormResponseRecord.id)
            .where(
                FormResponseRecord.id == response_id,
                account_form_record_scope(db, account_id),
                *_ADMIN_REGISTRATION_SCOPE_FILTERS,
            )
        ).first()
        if row is None:
            raise HTTPException(404, "registration_not_found")
        record, payment, form_event_id = row
        viewer_role = ROLE_OWNER if isinstance(identity, OwnerIdentity) else identity.role
        with_finance = has_permission(viewer_role, "finance")
        snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
        answers_raw = record.answers if isinstance(record.answers, dict) else {}
        answers: list[dict[str, Any]] = []
        for field in _json_list_member(snapshot, "fields"):
            if not isinstance(field, dict) or not isinstance(field.get("id"), str):
                continue
            field_id = field["id"]
            field_type = str(field.get("type") or "")
            value = answers_raw.get(field_id)
            if value is None or value == "" or value == []:
                continue
            masked = _ADMIN_ANSWER_MASKED_TYPES.get(field_type)
            if masked:
                text = str(value)
                answers.append({
                    "field_id": field_id, "label": _ticket_text(field.get("label") or field_id, 160) or field_id,
                    "type": field_type, "value": None, "masked": masked,
                    "hint": text[-4:] if masked == "mobile" and len(text) >= 4 else "",
                })
                continue
            if isinstance(value, (list, tuple)):
                cleaned: Any = [_ticket_text(item, 4000) for item in value if isinstance(item, (str, int, float))][:100]
            elif isinstance(value, dict):
                cleaned = {str(k)[:80]: _ticket_text(v, 4000) for k, v in list(value.items())[:50] if isinstance(v, (str, int, float))}
            elif isinstance(value, bool):
                cleaned = value
            else:
                cleaned = _ticket_text(value, 4000)
            answers.append({
                "field_id": field_id, "label": _ticket_text(field.get("label") or field_id, 160) or field_id,
                "type": field_type, "value": cleaned, "masked": None,
            })
        companions = db.scalars(
            select(FormResponseRecord)
            .where(FormResponseRecord.added_by_response_id == record.id)
            .order_by(FormResponseRecord.companion_index, FormResponseRecord.id)
            .limit(20)
        ).all()
        receipt_task = db.get(AdminTaskRecord, record.receipt_review_task_id) if record.receipt_review_task_id else None
        payment_view: dict[str, Any] | None = None
        if payment is not None:
            payment_view = {"status": payment.status, "method": payment.method}
            if with_finance:
                payment_view.update({
                    "amount": int(payment.amount), "currency": payment.currency,
                    "transaction_id": payment.transaction_id or None,
                })
        detail = _admin_registration_summary(record, payment, form_event_id)
        detail.update({
            "source": "shared_server_database",
            "account_id": account_id,
            "response_id": record.id,
            "form": {"id": record.form_id, "name": detail["form_name"], "version": record.form_version},
            "event": {"id": detail["event_id"], "title": detail["event_title"], "date": detail["event_date"]} if detail["event_id"] or snapshot.get("event") else None,
            "registrant_name": _form_ticket_name(record),
            "answers": answers,
            "companions": [
                {
                    "id": companion.id,
                    "name": _form_ticket_name(companion),
                    "status": companion.status,
                    "ticket_checked_in": companion.ticket_checked_in_at is not None,
                }
                for companion in companions
            ],
            "payment": payment_view,
            "finance_visible": with_finance,
            "receipt": {
                "uploaded": detail["receipt_uploaded"],
                "task_id": receipt_task.id if receipt_task is not None else None,
                "task_status": receipt_task.status if receipt_task is not None else None,
            },
            "attendance": {
                "checked_in": record.ticket_checked_in_at is not None,
                "checked_in_at": _as_utc(record.ticket_checked_in_at).isoformat() if record.ticket_checked_in_at else None,
                "checked_in_by": _attendance_actor(record),
            },
            "updated_at": _as_utc(record.updated_at).isoformat(),
        })
        return detail

    @app.get("/api/admin/users/{account_id}/notifications")
    def list_admin_user_notifications(
        account_id: str,
        response: Response,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission("us_view")),
        db: Session = Depends(get_db),
    ):
        """U5: read-only outbox rows **of this account only** (``user_notifications.account_id``).

        Not the global queue: the filter is the path account, enforced here. Every row in that table
        is addressed to one account; ``scope`` tells the panel whether the text was written for this
        account alone (``account``) or fanned out to an audience (``audience``). ``delivery_state``
        keeps queued ≠ retrying ≠ delivered ≠ failed, and ``no_bale_identity`` stays a distinct,
        non-network failure. No retry/send action lives on this path.
        """
        response.headers["Cache-Control"] = "private, no-store"
        _admin_target_account(db, account_id)
        total = int(db.scalar(
            select(func.count(UserNotificationRecord.id)).where(UserNotificationRecord.account_id == account_id)
        ) or 0)
        rows = db.scalars(
            select(UserNotificationRecord)
            .where(UserNotificationRecord.account_id == account_id)
            .order_by(UserNotificationRecord.created_at.desc(), UserNotificationRecord.id)
            .offset(offset)
            .limit(limit + 1)
        ).all()
        items = []
        for row in rows[:limit]:
            view = user_notification_view(row)
            view.pop("bale_user_id", None)
            view.pop("file_refs", None)
            view["scope"] = "audience" if row.kind in _NOTIFICATION_AUDIENCE_KINDS else "account"
            view["has_bale_identity"] = bool(row.bale_user_id)
            view["source_task_id"] = row.source_task_id
            items.append(view)
        return {
            "source": "shared_server_database",
            "account_id": account_id,
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }

    # ── حضور و غیاب: همان ستون‌های check-in بلیت که ربات می‌نویسد ──
    # منبع مشترک: form_responses.ticket_checked_in_*؛ پنل فقط همان رکورد را می‌خواند
    # و با مجوز attendance و ثبت دلیل/ممیزی، حضور را ثبت یا اصلاح می‌کند.
    def _attendance_actor(record: FormResponseRecord) -> dict[str, Any] | None:
        if record.ticket_checked_in_at is None:
            return None
        if record.ticket_checked_in_by_account_id:
            return {"kind": "web", "id": record.ticket_checked_in_by_account_id}
        if record.ticket_checked_in_by_bale_user_id:
            return {"kind": "bot", "id": record.ticket_checked_in_by_bale_user_id}
        return {"kind": "unknown", "id": ""}

    def _attendance_person(db: Session, record: FormResponseRecord) -> dict[str, Any]:
        mobile = str(record.registrant_mobile or "")
        return {
            "response_id": record.id,
            "form_id": record.form_id,
            "name": _form_ticket_name(record),
            "companion": record.added_by_response_id is not None,
            "added_by_name": _ticket_text(record.added_by_name or "", 120) if record.added_by_response_id else "",
            "status": record.status,
            "serial": record.ticket_serial,
            "mobile_hint": (mobile[-4:] if len(mobile) >= 4 else ""),
            "payment_approved": _response_payment_approved(db, record),
            "ticket_eligible": _form_ticket_eligible(record),
            "checked_in": record.ticket_checked_in_at is not None,
            "checked_in_at": _as_utc(record.ticket_checked_in_at).isoformat() if record.ticket_checked_in_at else None,
            "checked_in_by": _attendance_actor(record),
            "ticket_type": _form_response_ticket_type(record),
            "created_at": _as_utc(record.created_at).isoformat(),
        }

    @app.get("/api/admin/attendance/forms")
    def list_attendance_forms(
        response: Response,
        q: str = Query(default="", max_length=80),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=100_000),
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission("attendance")),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        forms = db.scalars(
            select(FormRecord)
            .where(
                FormRecord.owner_id == identity.owner_id, FormRecord.model == "registration",
                FormRecord.purpose == "registration",
            )
            .order_by(FormRecord.updated_at.desc(), FormRecord.id)
        ).all()
        needle = unicodedata.normalize("NFKC", q or "").strip().lower()
        if needle:
            forms = [
                form for form in forms
                if needle in unicodedata.normalize("NFKC", f"{form.title} {form.event_id or ''}").lower()
            ]
        page = forms[offset: offset + limit]
        items = []
        for form in page:
            totals = db.execute(
                select(
                    func.count(FormResponseRecord.id),
                    func.sum(case((FormResponseRecord.ticket_checked_in_at.is_not(None), 1), else_=0)),
                    func.sum(case((FormResponseRecord.status == "accepted", 1), else_=0)),
                ).where(FormResponseRecord.form_id == form.id)
            ).one()
            settings_value = form.settings if isinstance(form.settings, dict) else {}
            event = _json_dict_member(settings_value, "event")
            items.append({
                "form_id": form.id,
                "title": form.title,
                "status": form.status,
                "event_id": form.event_id,
                "event_title": _ticket_text(event.get("title") or "", 160),
                "event_date": _ticket_text(event.get("date") or "", 120),
                "event_time": _ticket_text(event.get("time") or "", 120),
                "people": int(totals[0] or 0),
                "accepted": int(totals[2] or 0),
                "checked_in": int(totals[1] or 0),
                "updated_at": _as_utc(form.updated_at).isoformat(),
            })
        return {
            "source": "shared_server_database",
            "items": items,
            "total": len(forms),
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < len(forms),
            "q": q,
        }

    @app.get("/api/admin/attendance/forms/{form_id}/people")
    def list_attendance_people(
        form_id: str,
        response: Response,
        q: str = Query(default="", max_length=80),
        state: str = Query(default="", pattern=r"^(|checked_in|pending)$"),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0, le=100_000),
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission("attendance")),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        form = get_owned_form(db, identity.owner_id, form_id)
        query = select(FormResponseRecord).where(FormResponseRecord.form_id == form.id)
        if state == "checked_in":
            query = query.where(FormResponseRecord.ticket_checked_in_at.is_not(None))
        elif state == "pending":
            query = query.where(FormResponseRecord.ticket_checked_in_at.is_(None))
        records = db.scalars(
            query.order_by(FormResponseRecord.created_at.asc(), FormResponseRecord.id).limit(5000)
        ).all()
        needle = unicodedata.normalize("NFKC", q or "").strip().lower()
        if needle:
            digits = re.sub(r"\D", "", needle.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
            records = [
                record for record in records
                if needle in unicodedata.normalize("NFKC", _form_ticket_name(record)).lower()
                or (record.ticket_serial and needle in record.ticket_serial.lower())
                or (len(digits) >= 4 and str(record.registrant_mobile or "").endswith(digits))
            ]
        page = records[offset: offset + limit]
        return {
            "source": "shared_server_database",
            "form": {"form_id": form.id, "title": form.title, "status": form.status, "event_id": form.event_id},
            "items": [_attendance_person(db, record) for record in page],
            "total": len(records),
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < len(records),
            "q": q,
            "state": state,
        }

    async def _attendance_target(
        request: Request, db: Session, identity: OwnerIdentity | AccountIdentity, response_id: str, *, require_reason: bool
    ) -> tuple[FormResponseRecord, str]:
        if not _BOT_FORM_RESPONSE_ID.fullmatch(response_id or ""):
            raise HTTPException(404, "ticket_not_found")
        payload = await _read_json_object(request, 4096)
        if not set(payload) <= {"reason"}:
            raise HTTPException(400, "invalid_attendance_payload")
        reason = payload.get("reason", "")
        if not isinstance(reason, str) or len(reason) > 300:
            raise HTTPException(422, {"code": "invalid_reason", "field": "reason"})
        reason = reason.strip()
        if require_reason and len(reason) < 3:
            raise HTTPException(422, {"code": "reason_required", "field": "reason"})
        record = db.scalar(
            select(FormResponseRecord)
            .join(FormRecord, FormRecord.id == FormResponseRecord.form_id)
            .where(FormResponseRecord.id == response_id, FormRecord.owner_id == identity.owner_id)
            .options(selectinload(FormResponseRecord.draft))
            .with_for_update()
        )
        if record is None:
            raise HTTPException(404, "ticket_not_found")
        return record, reason

    @app.post("/api/admin/attendance/responses/{response_id}/check-in")
    async def admin_check_in(
        response_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write("attendance")),
        db: Session = Depends(get_db),
    ):
        record, reason = await _attendance_target(request, db, identity, response_id, require_reason=False)
        if record.ticket_checked_in_at is not None:
            raise HTTPException(409, {"code": "already_checked_in", "checked_in_at": _as_utc(record.ticket_checked_in_at).isoformat()})
        if not _response_payment_approved(db, record):
            raise HTTPException(409, {"code": "ticket_payment_not_confirmed"})
        _ensure_form_ticket(record)
        record.ticket_checked_in_at = _utc_now()
        record.ticket_checked_in_by_account_id = (
            identity.owner_id if isinstance(identity, OwnerIdentity) else identity.account_id
        )[:36]
        record.ticket_checked_in_by_bale_user_id = None
        record_audit(
            db, identity, "attendance.check_in", target_type="form_response", target_id=record.id,
            details={"form_id": record.form_id, "reason": reason[:160], "source": "web"},
        )
        db.commit()
        db.refresh(record)
        return {"saved": True, "person": _attendance_person(db, record)}

    @app.post("/api/admin/attendance/responses/{response_id}/undo-check-in")
    async def admin_undo_check_in(
        response_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write("attendance")),
        db: Session = Depends(get_db),
    ):
        record, reason = await _attendance_target(request, db, identity, response_id, require_reason=True)
        if record.ticket_checked_in_at is None:
            raise HTTPException(409, {"code": "not_checked_in"})
        previous = _attendance_actor(record) or {}
        previous_at = _as_utc(record.ticket_checked_in_at).isoformat()
        record.ticket_checked_in_at = None
        record.ticket_checked_in_by_account_id = None
        record.ticket_checked_in_by_bale_user_id = None
        record_audit(
            db, identity, "attendance.undo_check_in", target_type="form_response", target_id=record.id,
            details={
                "form_id": record.form_id, "reason": reason[:160], "previous_at": previous_at,
                "previous_by": f"{previous.get('kind', '')}:{previous.get('id', '')}"[:80],
            },
        )
        db.commit()
        db.refresh(record)
        return {"saved": True, "person": _attendance_person(db, record)}

    # ── گواهی‌ها: آینهٔ تأییدشدهٔ گواهی‌های صادرشده توسط ربات (فقط‌خواندنی برای پنل) ──
    # مالک هر ردیف سمت سرور از شناسهٔ بله حل می‌شود؛ ردیف بدون هویت سرور ذخیره نمی‌شود.
    # در این فاز هیچ عملیات تغییردهنده‌ای (ابطال/ویرایش) از پنل وجود ندارد؛ ربات تنها نویسنده است.

    def _certificate_error(error: certificates_mod.CertificateError) -> HTTPException:
        return HTTPException(error.status_code, error.code)

    @app.get("/api/admin/certificates")
    def list_admin_certificates(
        response: Response,
        q: str = Query(default="", max_length=80),
        status: str = Query(default="", pattern=r"^(|issued|revoked|expired)$"),
        kind: str = Query(default="", pattern=r"^(|event|batch|form|manual|center|recording)$"),
        event_ref: str = Query(default="", max_length=40, pattern=r"^[A-Za-z0-9_.:-]*$"),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission("certificate")),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        result = certificates_mod.list_records(
            db, q=q, status=status, kind=kind, event_ref=event_ref, limit=limit, offset=offset,
            today_jalali=certificates_mod.today_jalali(),
        )
        result["events"] = certificates_mod.event_options(db)
        result["can_revoke"] = False
        return result

    def _admin_certificate(db: Session, certificate_id: str) -> CertificateRecord:
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", certificate_id or ""):
            raise HTTPException(404, "certificate_not_found")
        record = db.get(CertificateRecord, certificate_id)
        if record is None:
            raise HTTPException(404, "certificate_not_found")
        return record

    @app.get("/api/admin/certificates/{certificate_id}")
    def get_admin_certificate(
        certificate_id: str,
        response: Response,
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission("certificate")),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        record = _admin_certificate(db, certificate_id)
        return {
            "source": certificates_mod.SOURCE,
            "certificate": certificates_mod.detail(db, record, today_jalali=certificates_mod.today_jalali()),
            "can_revoke": False,
        }

    # ── امتیاز باشگاه: آینهٔ فقط‌خواندنی دفترکل ربات (هیچ مسیر نوشتن امتیازی در پنل وجود ندارد) ──
    # ربات تنها نویسنده است؛ مالک هر ردیف سمت سرور از شناسهٔ بله حل می‌شود.

    @app.get("/api/admin/club/points")
    def list_admin_club_points(
        response: Response,
        q: str = Query(default="", max_length=80),
        entry_type: str = Query(default="", pattern=r"^(|opening_balance|award|spend|refund|reversal|manual_adjust)$"),
        account_id: str = Query(default="", max_length=36, pattern=r"^[0-9a-fA-F-]*$"),
        bale_user_id: str = Query(default="", max_length=20, pattern=r"^[0-9]*$"),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission("cl_member")),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        return club_points_mod.list_entries(
            db, account_id=account_id, bale_user_id=bale_user_id, entry_type=entry_type,
            q=q, limit=limit, offset=offset,
        )

    @app.get("/api/admin/club/points/members")
    def list_admin_club_points_members(
        response: Response,
        q: str = Query(default="", max_length=80),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission("cl_member")),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        return club_points_mod.list_members(db, q=q, limit=limit, offset=offset)

    @app.get("/api/admin/club/points/members/{account_id}")
    def get_admin_club_points_member(
        account_id: str,
        response: Response,
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission("cl_member")),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", account_id or ""):
            raise HTTPException(404, "member_not_found")
        summary = club_points_mod.member_summary(db, account_id)
        if summary is None:
            raise HTTPException(404, "member_not_found")
        summary["history"] = club_points_mod.list_entries(db, account_id=account_id, limit=100)["items"]
        return summary

    @app.get("/api/admin/certificates/{certificate_id}/file")
    def admin_certificate_file(
        certificate_id: str,
        slot: str = Query(default="pdf", pattern=r"^(pdf|png)$"),
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission("certificate")),
        db: Session = Depends(get_db),
    ):
        record = _admin_certificate(db, certificate_id)
        file_id = record.file_id if slot == "pdf" else record.preview_file_id
        item = db.get(PrivateFileRecord, file_id) if file_id else None
        if item is None or item.account_id != record.account_id:
            raise HTTPException(404, "certificate_file_not_found")
        disposition = "inline" if item.content_type.startswith("image/") else "attachment"
        stem = re.sub(r"[^A-Za-z0-9._-]", "_", record.serial or record.full_code or record.id)[:60] or "certificate"
        extension = "png" if item.content_type.startswith("image/") else "pdf"
        return Response(
            content=item.content,
            media_type=item.content_type,
            headers={
                "Content-Disposition": f'{disposition}; filename="{stem}.{extension}"',
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; sandbox",
            },
        )

    # ── داده‌ها و مهاجرت: بارگذاری نسخهٔ پشتیبان برای ممیزی (بدون تغییر داده) ──
    # فایل فقط در staging خصوصی (بیرون UI_ROOT) ذخیره می‌شود، فقط‌خواندنی
    # بررسی می‌شود و هیچ عملیات نوشتنی روی آن یا روی پایگاه عملیاتی اجرا نمی‌شود.

    data_logger = logging.getLogger("nora.data_staging")

    def _data_store(cfg: Settings) -> data_staging_mod.StagingStore:
        return data_staging_mod.StagingStore(
            cfg.data_staging_dir,
            data_staging_mod.UploadLimits(
                max_bytes=cfg.data_upload_max_bytes,
                retention_hours=cfg.data_staging_retention_hours,
            ),
        )

    def _audit_script(cfg: Settings) -> Path:
        configured = cfg.legacy_audit_script.strip()
        return Path(configured) if configured else data_staging_mod.default_audit_script()

    def _owner_upload_actor(identity: OwnerIdentity | AccountIdentity) -> str:
        return str(getattr(identity, "owner_id", "") or getattr(identity, "account_id", "") or "unknown")

    def _enforce_owner_upload_limit(
        request: Request, db: Session, cfg: Settings, identity: OwnerIdentity | AccountIdentity,
        limit: int = 10,
        scope: str = "data-upload",
    ) -> None:
        """At most ``limit`` uploads per hour per actor; stored, not in-memory only."""
        key_hash = throttle_digest(
            cfg.owner_password_hash or cfg.owner_id or "nora", scope + "\0" + _owner_upload_actor(identity)
        )
        now = _utc_now()
        db.execute(
            delete(PublicWriteThrottleRecord).where(
                PublicWriteThrottleRecord.window_started_at < now - timedelta(days=1)
            )
        )
        record = db.scalar(
            select(PublicWriteThrottleRecord).where(PublicWriteThrottleRecord.key_hash == key_hash)
        )
        if record is None or _as_utc(record.window_started_at) < now - timedelta(hours=1):
            if record is None:
                db.add(PublicWriteThrottleRecord(key_hash=key_hash, attempts=1, window_started_at=now))
            else:
                record.attempts = 1
                record.window_started_at = now
            db.commit()
            return
        if record.attempts >= limit:
            db.commit()
            retry = max(1, int(3600 - (now - _as_utc(record.window_started_at)).total_seconds()))
            raise HTTPException(429, "upload_rate_limited", headers={"Retry-After": str(retry)})
        record.attempts += 1
        db.commit()

    # ── تصاویر عمومی پنل (پوستر رویداد / جلد مطلب) ──
    # بایت‌ها در همان پایگاه مشترک (مثل private_files) می‌مانند؛ نوع واقعی از
    # محتوای فایل تشخیص داده و با Pillow رمزگشایی می‌شود؛ site_content فقط
    # نشانی پایدار /api/public/media/{id} را نگه می‌دارد. هیچ حذف خودکاری نیست.

    def _media_actor(identity: OwnerIdentity | AccountIdentity) -> tuple[str, str]:
        if isinstance(identity, OwnerIdentity):
            return "owner", identity.owner_id
        return "account", identity.account_id

    @app.post("/api/admin/media", status_code=201)
    async def upload_admin_media(
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write("ev_create")),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = request.app.state.settings
        _enforce_owner_upload_limit(request, db, cfg, identity, limit=60, scope="media-upload")
        declared = request.headers.get("x-file-name", "image")
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            if not chunk:
                continue
            size += len(chunk)
            if size > public_media_mod.MAX_BYTES:
                raise HTTPException(413, "image_too_large")
            chunks.append(chunk)
        content = b"".join(chunks)
        actor_kind, actor_id = _media_actor(identity)
        try:
            record, created = public_media_mod.store(
                db, content, declared_name=declared, actor_kind=actor_kind, actor_id=actor_id,
            )
        except public_media_mod.MediaError as error:
            record_audit(
                db, identity, "media.upload", target_type="public_media", outcome="rejected",
                details={"code": error.code, "size": size},
            )
            db.commit()
            raise HTTPException(error.status, error.code) from None
        if created:
            record_audit(
                db, identity, "media.upload", target_type="public_media", target_id=record.id,
                details={"content_type": record.content_type, "size": record.content_size,
                         "width": record.width, "height": record.height},
            )
        db.commit()
        payload = public_media_mod.serialize(record)
        payload["created"] = created
        payload["source"] = public_media_mod.SOURCE
        return payload

    @app.get("/api/admin/media")
    def list_admin_media(
        response: Response,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission("ev_create")),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        return public_media_mod.list_records(db, limit=limit, offset=offset)

    @app.delete("/api/admin/media/{media_id}")
    def delete_admin_media(
        media_id: str,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write("ev_create")),
        db: Session = Depends(get_db),
    ):
        parsed = public_media_mod.parse_id(media_id)
        record = db.get(PublicMediaRecord, parsed) if parsed else None
        if record is None:
            raise HTTPException(404, "media_not_found")
        used_in = public_media_mod.usage_index(db).get(record.id, 0)
        if used_in:
            raise HTTPException(409, {"code": "media_in_use", "used_in": used_in})
        record_audit(
            db, identity, "media.delete", target_type="public_media", target_id=record.id,
            details={"content_type": record.content_type, "size": record.content_size, "file_name": record.file_name},
        )
        db.delete(record)
        db.commit()
        return {"deleted": True, "id": record.id}

    @app.get("/api/public/media/{media_id}")
    def public_media_file(media_id: str, request: Request, db: Session = Depends(get_db)):
        parsed = public_media_mod.parse_id(media_id)
        record = db.get(PublicMediaRecord, parsed) if parsed else None
        if record is None:
            raise HTTPException(404, "media_not_found")
        etag = f'"{record.content_hash[:32]}"'
        headers = {
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": etag,
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Content-Disposition": f'inline; filename="{record.file_name}"',
        }
        if request.headers.get("if-none-match", "") == etag:
            return Response(status_code=304, headers=headers)
        return Response(content=record.content, media_type=record.content_type, headers=headers)

    # ── فاز ۸: منابع، پرسش‌وپاسخ، دیدگاه و گزارش محتوای رویداد ──
    # رویداد از همان سند site_content می‌آید؛ ثبت‌نام/حضور از همان form_responses.
    # هر تصمیم دسترسی در همین‌جا و روی ردیف‌های واقعی گرفته می‌شود، نه در مرورگر.
    _INTERACTION_READ_PERMS = ("ev_create", "ev_publish")
    _INTERACTION_MODERATE_PERMS = ("ev_publish",)
    _INTERACTION_RESOURCE_PERMS = ("ev_create",)
    _UPLOAD_SESSION_LOCKS: dict[str, asyncio.Lock] = {}

    def _interaction_error(error: interaction_mod.InteractionError) -> HTTPException:
        detail: Any = {"code": error.code, "field": error.field} if error.field else error.code
        return HTTPException(error.status, detail)

    _EXTERNAL_VIDEO_KINDS = ("youtube", "aparat")

    def _pop_external_acknowledgement(payload: dict[str, Any]) -> bool:
        """Phase 9.5 §6.4: ``acknowledge_external_exposure`` is a boolean flag outside the stored fields."""
        if "acknowledge_external_exposure" not in payload:
            return False
        value = payload.pop("acknowledge_external_exposure")
        if not isinstance(value, bool):
            raise HTTPException(422, {"code": "invalid_value", "field": "acknowledge_external_exposure"})
        return value

    def _require_external_exposure_ack(
        *, kind: str, before: tuple[str, str] | None, after: tuple[str, str], acknowledged: bool
    ) -> bool:
        """A paid (``purchased``) resource hosted on YouTube/Aparat is *not* protected by Nora.

        Entering the state (published, purchased, external) requires the operator's explicit
        ``acknowledge_external_exposure: true`` (recorded in the audit row); any other change is free.
        Returns True when the acknowledgement was consumed (so the caller can audit it).
        """
        if kind not in _EXTERNAL_VIDEO_KINDS:
            return False
        exposed_after = after == ("published", "purchased")
        exposed_before = before == ("published", "purchased")
        if not exposed_after or exposed_before:
            return False
        if not acknowledged:
            raise HTTPException(409, {"code": "external_exposure_acknowledgement_required", "provider": kind})
        return True

    def _interaction_event(db: Session, event_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """``(public_projection, stored_row)``; the projection is ``None`` unless published."""
        record = db.get(SiteContentRecord, "public")
        found = content_admin_mod.find_row(_content_rows(record, "events"), event_id)
        if found is None:
            return None, None
        stored = found[1]
        projected = public_site_content({"events": [stored]}).get("events") or []
        return (projected[0] if projected else None), stored

    def _interaction_event_titles(db: Session, event_ids: set[str]) -> dict[str, str]:
        if not event_ids:
            return {}
        record = db.get(SiteContentRecord, "public")
        titles: dict[str, str] = {}
        for row in _content_rows(record, "events"):
            if isinstance(row, dict) and str(row.get("id") or "") in event_ids:
                titles[str(row["id"])] = str(row.get("t") or row.get("n") or "")[:160]
        return titles

    def _interaction_staff(request: Request, db: Session) -> OwnerIdentity | AccountIdentity | None:
        try:
            return require_any_permission(*_INTERACTION_READ_PERMS)(request, db)
        except HTTPException:
            return None

    def _interaction_participation(db: Session, account_id: str, event_id: str) -> interaction_mod.Participation:
        return interaction_mod.participation_for(
            db, account_id, event_id,
            scope=account_form_record_scope(db, account_id),
            payment_approved=_response_payment_approved,
        )

    def _interaction_display_name(db: Session, account_id: str) -> str:
        profile = db.get(AccountProfileRecord, account_id)
        fields = profile.fields if profile is not None and isinstance(profile.fields, dict) else {}
        return str(fields.get("fullName") or "")[:120]

    def _interaction_actor(identity: OwnerIdentity | AccountIdentity) -> tuple[str, str]:
        if isinstance(identity, OwnerIdentity):
            return "owner", identity.owner_id
        return "account", identity.account_id

    def _interaction_question_notification(
        db: Session, question: EventQuestionRecord
    ) -> dict[str, Any] | None:
        if not question.notification_id:
            return None
        item = db.get(UserNotificationRecord, question.notification_id)
        if item is None:
            return None
        return {
            "id": item.id,
            "state": interaction_mod.delivery_state(item.delivery_status, item.delivery_attempts),
            "delivery_status": item.delivery_status,
            "attempts": item.delivery_attempts,
            "last_error": item.last_delivery_error or None,
            "has_bale_target": bool(item.bale_user_id),
            "created_at": _as_utc(item.created_at).isoformat(),
            "delivered_at": _as_utc(item.delivered_at).isoformat() if item.delivered_at else None,
        }

    def _queue_question_answer_notification(db: Session, question: EventQuestionRecord, event_title: str) -> UserNotificationRecord:
        """One outbox row per answered question (idempotent via ``notification_id``).

        The answer itself is already persisted; this only enqueues. Accounts without a
        server-verified Bale identity get a web-only row (``failed`` / ``no_bale_identity``)
        so nothing is ever sent to a guessed destination and the state stays honest.
        """
        bale_ids = verified_bale_ids_for_account(db, question.account_id)
        title = "پاسخ برگزارکننده به پرسش شما"
        body = (
            f"پرسش شما دربارهٔ «{event_title}» پاسخ داده شد.\n\n"
            f"پرسش: {question.body[:300]}\n\nپاسخ: {question.answer_body[:900]}"
        )
        item, _created = notifications_mod.queue(
            db, account_id=question.account_id, kind=interaction_mod.NOTIFICATION_KIND, title=title, body=body,
            key=notifications_mod.dedupe_key("event_question", question.id, "answer"), bale_ids=bale_ids,
            link=notifications_mod.event_link(question.event_id, anchor="qa"), refresh=True,
        )
        if question.notification_id != item.id:
            question.notification_id = item.id
            db.flush()
        return item

    @app.get("/api/public/events/{event_id}/interaction")
    def public_event_interaction(event_id: str, request: Request, response: Response, db: Session = Depends(get_db)):
        """Resources, Q&A and reviews of one event for the current viewer (guest, account or staff)."""
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Cookie"
        try:
            event_id = interaction_mod.parse_event_id(event_id)
        except interaction_mod.InteractionError as error:
            raise _interaction_error(error) from None
        staff = _interaction_staff(request, db)
        account = account_identity_from_request(request, db) if staff is None or isinstance(staff, AccountIdentity) else None
        if isinstance(staff, AccountIdentity):
            account = staff
        public_event, stored = _interaction_event(db, event_id)
        if stored is None or (public_event is None and staff is None):
            raise HTTPException(404, "event_not_found")
        source = public_event or {}
        now = _utc_now()
        participation = (
            _interaction_participation(db, account.account_id, event_id) if account is not None else None
        )
        viewer_id = account.account_id if account is not None else None
        recording_row = _recording_for_event(db, event_id)
        recording_viewer = _recording_viewer(
            db, recording_row, account=account, staff=staff is not None, participation=participation, now=now,
        )
        purchased_state = _purchased_state(recording_row, recording_viewer)
        resources = db.scalars(
            select(EventResourceRecord)
            .where(EventResourceRecord.event_id == event_id, EventResourceRecord.status != "removed")
            .order_by(EventResourceRecord.sort_order.asc(), EventResourceRecord.created_at.asc())
        ).all()
        resource_rows = [
            interaction_mod.resource_public_view(
                row, now=now, signed_in=account is not None, participation=participation, staff=staff is not None,
                purchased=purchased_state,
            )
            for row in resources
            # Session files of the recorded product are listed inside its sessions, not in the general list.
            if (staff is not None or interaction_mod.resource_is_live(row, now)) and not row.session_id
        ]
        recording_payload = _recording_public_payload(
            db, request, event_id=event_id, public_event=public_event, account=account, staff=staff is not None, now=now,
        )
        questions = db.scalars(
            select(EventQuestionRecord)
            .where(EventQuestionRecord.event_id == event_id)
            .order_by(EventQuestionRecord.created_at.desc(), EventQuestionRecord.id)
            .limit(300)
        ).all()
        visible_questions = [row for row in questions if interaction_mod.question_visible_to(row, viewer_id)]
        reported_q = interaction_mod.reported_by(db, "question", viewer_id, [row.id for row in visible_questions])
        reviews = db.scalars(
            select(EventReviewRecord)
            .where(EventReviewRecord.event_id == event_id)
            .order_by(EventReviewRecord.created_at.desc(), EventReviewRecord.id)
            .limit(300)
        ).all()
        visible_reviews = [row for row in reviews if interaction_mod.review_visible_to(row, viewer_id)]
        reported_r = interaction_mod.reported_by(db, "review", viewer_id, [row.id for row in visible_reviews])
        mine_review = next((row for row in reviews if viewer_id and row.account_id == viewer_id), None)
        lifecycle = str(source.get("lifecycle") or stored.get("lifecycle") or "scheduled")
        qa_closed = bool(source.get("qaClosed") if public_event else stored.get("qaClosed") is True)
        buyer = recording_viewer.access_state == "active"
        return {
            "source": "shared_server_database",
            "server_time": event_time.to_iso(now),
            "event": {
                "id": event_id,
                "title": str(source.get("t") or stored.get("t") or "")[:240],
                "published": public_event is not None,
                "lifecycle": lifecycle,
                "held": recordings_mod.event_held(source, now) if public_event else False,
                "qa_open": not qa_closed and lifecycle != "cancelled",
                "qa_closed_reason": "cancelled" if lifecycle == "cancelled" else ("closed" if qa_closed else ""),
            },
            "viewer": {
                "signed_in": account is not None,
                "staff": staff is not None,
                "participation": (participation or interaction_mod.Participation()).as_dict(),
                "buyer": buyer,
            },
            "recording": recording_payload,
            "resources": resource_rows,
            "questions": {
                "items": [
                    interaction_mod.question_public_view(row, viewer_account_id=viewer_id, reported=row.id in reported_q)
                    for row in visible_questions
                ],
                "total": len(visible_questions),
                "mine_pending": sum(1 for row in visible_questions if viewer_id and row.account_id == viewer_id and row.status == "pending"),
            },
            "reviews": {
                "eligible": bool(participation and participation.attended) or buyer,
                "badge": "attendee" if participation and participation.attended else ("buyer" if buyer else ""),
                "items": [
                    interaction_mod.review_public_view(row, viewer_account_id=viewer_id, reported=row.id in reported_r)
                    for row in visible_reviews
                ],
                "total": len(visible_reviews),
                "mine": interaction_mod.review_public_view(mine_review, viewer_account_id=viewer_id) if mine_review else None,
            },
        }

    @app.get("/api/public/events/{event_id}/resources/{resource_id}/download")
    def public_event_resource_download(
        event_id: str, resource_id: str, request: Request, db: Session = Depends(get_db)
    ):
        """The only way to read resource bytes; access is decided here per request."""
        try:
            event_id = interaction_mod.parse_event_id(event_id)
        except interaction_mod.InteractionError as error:
            raise _interaction_error(error) from None
        parsed = interaction_mod.parse_row_id(resource_id)
        record = db.get(EventResourceRecord, parsed) if parsed else None
        # The event id in the URL must match: swapping ids across events is a 404, not a bypass.
        if record is None or record.event_id != event_id or record.kind != "file":
            raise HTTPException(404, "resource_not_found")
        staff = _interaction_staff(request, db)
        account = staff if isinstance(staff, AccountIdentity) else (
            account_identity_from_request(request, db) if staff is None else None
        )
        public_event, stored = _interaction_event(db, event_id)
        if stored is None or (public_event is None and staff is None):
            raise HTTPException(404, "resource_not_found")
        now = _utc_now()
        participation = (
            _interaction_participation(db, account.account_id, event_id) if account is not None else None
        )
        purchased_state: tuple[bool, str] | None = None
        preview_open = False
        if record.access == "purchased" or record.session_id:
            recording_row = _recording_for_event(db, event_id)
            viewer = _recording_viewer(
                db, recording_row, account=account, staff=staff is not None, participation=participation, now=now,
            )
            purchased_state = _purchased_state(recording_row, viewer)
            if recording_row is not None and record.session_id and recording_row.status in recordings_mod.SHELF_STATUSES:
                session = db.get(RecordingSessionRecord, record.session_id)
                preview_open = bool(
                    session is not None and session.preview and session.status == "published"
                    and record.access in {"public", "purchased"}
                )
        allowed, reason = interaction_mod.resource_access_state(
            record, now=now, signed_in=account is not None, participation=participation, staff=staff is not None,
            purchased=purchased_state,
        )
        if not allowed and preview_open and interaction_mod.resource_is_live(record, now):
            allowed, reason = True, "preview"
        if not allowed:
            if reason in {"removed", "not_published"}:
                raise HTTPException(404, "resource_not_found")
            if reason.startswith("purchase") or reason.startswith("access_"):
                # Unauthorized attempts on paid content are logged (no bytes, no account data in the row).
                audit_mod.record_admin_event(
                    db, actor_kind=audit_mod.ACTOR_ACCOUNT if account is not None else "guest",
                    actor_id=account.account_id if account is not None else "", actor_role="",
                    action="recording.download.denied", target_type="event_resource", target_id=record.id,
                    outcome="denied", details={"event_id": event_id, "reason": reason},
                )
                db.commit()
            raise HTTPException(
                401 if reason == "login_required" else 403,
                {"code": "resource_access_denied", "reason": reason},
            )
        if not _resource_has_bytes(request, record):
            raise HTTPException(404, "resource_not_found")
        return _resource_file_response(request, record, reason)

    def _private_storage(request: Request) -> storage_mod.LocalPrivateStorage | None:
        return getattr(request.app.state, "private_storage", None)

    def _resource_storage_state(request: Request, record: EventResourceRecord) -> dict[str, Any]:
        """Honest storage view for the panel: where the bytes are and whether they are reachable now."""
        if record.kind != "file":
            return {"backend": "none", "state": "not_file"}
        if record.storage_key:
            store = _private_storage(request)
            if store is None:
                return {"backend": "local_disk", "state": "storage_not_configured"}
            size = store.size(record.storage_key)
            if size is None:
                return {"backend": "local_disk", "state": "missing"}
            return {"backend": "local_disk", "state": "ready" if size == record.content_size else "size_mismatch"}
        return {"backend": "database", "state": "ready" if record.content is not None else "empty"}

    def _resource_limits(request: Request) -> dict[str, Any]:
        store = _private_storage(request)
        status = store.status() if store is not None else storage_mod.unconfigured_status(inline_max_bytes=interaction_mod.MAX_BYTES)
        return {
            "max_bytes": store.max_bytes if store is not None else interaction_mod.MAX_BYTES,
            "inline_max_bytes": interaction_mod.MAX_BYTES,
            "content_types": list(interaction_mod.CONTENT_TYPES),
            "storage": asdict(status),
        }

    def _resource_has_bytes(request: Request, record: EventResourceRecord) -> bool:
        return _resource_storage_state(request, record)["state"] == "ready"

    def _resource_admin_view(request: Request, record: EventResourceRecord) -> dict[str, Any]:
        view = interaction_mod.resource_admin_view(record)
        view["storage"] = _resource_storage_state(request, record)
        return view

    def _resource_file_response(request: Request, record: EventResourceRecord, reason: str) -> Response:
        """Whole file (download) or inline bytes with HTTP Range support (``delivery='view'``).

        Bytes come either from the row (legacy inline, ≤ 8 MiB) or from the private storage, streamed
        in bounded chunks so a long video never sits in the web process' memory. ``Content-Encoding:
        identity`` keeps the gzip middleware away so byte ranges stay exact.
        """
        headers = {
            "Cache-Control": "private, no-store",
            "Vary": "Cookie",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Content-Encoding": "identity",
            "X-Nora-Resource-Access": reason,
        }
        store = _private_storage(request) if record.storage_key else None
        if record.storage_key:
            total = store.size(record.storage_key) if store is not None else None
            if total is None:
                raise HTTPException(409, {"code": "resource_file_unavailable"})

            def reader(start: int, end: int) -> Iterator[bytes]:
                assert store is not None and record.storage_key
                return store.open_range(record.storage_key, start, end)
        else:
            content = record.content or b""
            total = len(content)

            def reader(start: int, end: int) -> Iterator[bytes]:
                for offset in range(start, end + 1, storage_mod.CHUNK_BYTES):
                    yield content[offset:min(offset + storage_mod.CHUNK_BYTES, end + 1)]

        def stream(start: int, end: int, status: int) -> Response:
            headers["Content-Length"] = str(end - start + 1 if total else 0)
            body = reader(start, end) if total else iter(())
            return StreamingResponse(body, status_code=status, media_type=record.content_type, headers=headers)

        if record.delivery != "view":
            headers["Content-Disposition"] = interaction_mod.content_disposition(record.file_name)
            return stream(0, total - 1, 200)
        headers["Content-Disposition"] = interaction_mod.content_disposition(record.file_name).replace("attachment", "inline", 1)
        headers["Accept-Ranges"] = "bytes"
        range_header = request.headers.get("range", "")
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip()) if range_header else None
        if match is None:
            # Multi-range or malformed ranges are answered with the whole body (RFC 9110 §14.2 allows ignoring).
            return stream(0, total - 1, 200)
        start_text, end_text = match.group(1), match.group(2)
        if not start_text and not end_text:
            raise HTTPException(416, "range_not_satisfiable", headers={"Content-Range": f"bytes */{total}"})
        if start_text:
            start = int(start_text)
            end = min(int(end_text), total - 1) if end_text else total - 1
        else:
            suffix = int(end_text)
            start, end = max(0, total - suffix), total - 1
        if start >= total or start > end:
            raise HTTPException(416, "range_not_satisfiable", headers={"Content-Range": f"bytes */{total}"})
        headers["Content-Range"] = f"bytes {start}-{end}/{total}"
        return stream(start, end, 206)

    def _interaction_event_for_write(db: Session, event_id: str) -> tuple[str, dict[str, Any]]:
        try:
            event_id = interaction_mod.parse_event_id(event_id)
        except interaction_mod.InteractionError as error:
            raise _interaction_error(error) from None
        public_event, stored = _interaction_event(db, event_id)
        if public_event is None:
            raise HTTPException(404, "event_not_found")
        return event_id, public_event

    @app.post("/api/account/events/{event_id}/questions", status_code=201)
    async def account_ask_event_question(
        event_id: str,
        request: Request,
        identity: AccountIdentity = Depends(require_account_write),
        db: Session = Depends(get_db),
    ):
        event_id, event = _interaction_event_for_write(db, event_id)
        if event.get("qaClosed") is True or str(event.get("lifecycle") or "") == "cancelled":
            raise HTTPException(409, {"code": "qa_closed", "reason": "cancelled" if event.get("lifecycle") == "cancelled" else "closed"})
        payload = await _read_json_object(request, 16_384)
        if set(payload) - {"body", "session_id"}:
            raise HTTPException(400, "invalid_question")
        try:
            body = interaction_mod.clean_text(
                payload.get("body"), interaction_mod.QUESTION_MAX_CHARS, field="body",
                minimum=interaction_mod.QUESTION_MIN_CHARS, required=True,
            )
        except interaction_mod.InteractionError as error:
            raise _interaction_error(error) from None
        # Phase 9 (optional): bind the question to one published session of this event's recorded product.
        session_id: str | None = None
        raw_session = payload.get("session_id")
        if raw_session not in (None, ""):
            parsed_session = interaction_mod.parse_row_id(raw_session)
            product_row = _recording_for_event(db, event_id)
            session_row = db.get(RecordingSessionRecord, parsed_session) if parsed_session and product_row is not None else None
            if (
                product_row is None or session_row is None or session_row.recording_id != product_row.id
                or session_row.status != "published" or product_row.status not in {"published", "sales_paused"}
            ):
                raise HTTPException(404, {"code": "session_not_found"})
            session_id = session_row.id
        cfg: Settings = request.app.state.settings
        _enforce_owner_upload_limit(
            request, db, cfg, identity, limit=interaction_mod.QUESTIONS_PER_HOUR, scope="event-question",
        )
        digest = interaction_mod.body_hash(body)
        duplicate = db.scalar(
            select(EventQuestionRecord.id).where(
                EventQuestionRecord.event_id == event_id,
                EventQuestionRecord.account_id == identity.account_id,
                EventQuestionRecord.body_hash == digest,
            )
        )
        if duplicate:
            raise HTTPException(409, {"code": "duplicate_question", "id": duplicate})
        open_count = int(db.scalar(
            select(func.count(EventQuestionRecord.id)).where(
                EventQuestionRecord.event_id == event_id,
                EventQuestionRecord.account_id == identity.account_id,
                EventQuestionRecord.answered_at.is_(None),
                EventQuestionRecord.status != "hidden",
            )
        ) or 0)
        if open_count >= interaction_mod.OPEN_QUESTIONS_PER_EVENT:
            raise HTTPException(429, {"code": "too_many_open_questions", "limit": interaction_mod.OPEN_QUESTIONS_PER_EVENT})
        record = EventQuestionRecord(
            id=interaction_mod.new_id(),
            event_id=event_id,
            account_id=identity.account_id,
            author_label=interaction_mod.author_label(_interaction_display_name(db, identity.account_id)),
            body=body,
            body_hash=digest,
            status="pending",
            session_id=session_id,
        )
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, {"code": "duplicate_question"}) from None
        db.refresh(record)
        return interaction_mod.question_public_view(record, viewer_account_id=identity.account_id)

    async def _interaction_report(
        request: Request, db: Session, identity: AccountIdentity, *, event_id: str, kind: str, target_id: str
    ) -> dict[str, Any]:
        event_id, _event = _interaction_event_for_write(db, event_id)
        parsed = interaction_mod.parse_row_id(target_id)
        target: EventQuestionRecord | EventReviewRecord | None = None
        if parsed:
            target = db.get(EventQuestionRecord, parsed) if kind == "question" else db.get(EventReviewRecord, parsed)
        if target is None or target.event_id != event_id or target.account_id == identity.account_id:
            raise HTTPException(404, "report_target_not_found")
        visible = (
            interaction_mod.question_visible_to(target, identity.account_id)
            if isinstance(target, EventQuestionRecord)
            else interaction_mod.review_visible_to(target, identity.account_id)
        )
        if not visible:
            raise HTTPException(404, "report_target_not_found")
        payload = await _read_json_object(request, 4096)
        if set(payload) - {"reason"}:
            raise HTTPException(400, "invalid_report")
        try:
            reason = interaction_mod.clean_text(payload.get("reason"), interaction_mod.REASON_MAX_CHARS, field="reason")
        except interaction_mod.InteractionError as error:
            raise _interaction_error(error) from None
        cfg: Settings = request.app.state.settings
        _enforce_owner_upload_limit(request, db, cfg, identity, limit=20, scope="event-report")
        existing = db.scalar(
            select(EventContentReportRecord).where(
                EventContentReportRecord.target_kind == kind,
                EventContentReportRecord.target_id == target.id,
                EventContentReportRecord.reporter_account_id == identity.account_id,
            )
        )
        if existing is not None:
            return {"reported": True, "id": existing.id, "status": existing.status, "duplicate": True}
        record = EventContentReportRecord(
            id=interaction_mod.new_id(), event_id=event_id, target_kind=kind, target_id=target.id,
            reporter_account_id=identity.account_id, reason=reason, status="open",
        )
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return {"reported": True, "duplicate": True}
        return {"reported": True, "id": record.id, "status": "open", "duplicate": False}

    @app.post("/api/account/events/{event_id}/questions/{question_id}/report", status_code=201)
    async def account_report_event_question(
        event_id: str, question_id: str, request: Request,
        identity: AccountIdentity = Depends(require_account_write), db: Session = Depends(get_db),
    ):
        return await _interaction_report(request, db, identity, event_id=event_id, kind="question", target_id=question_id)

    @app.post("/api/account/events/{event_id}/reviews/{review_id}/report", status_code=201)
    async def account_report_event_review(
        event_id: str, review_id: str, request: Request,
        identity: AccountIdentity = Depends(require_account_write), db: Session = Depends(get_db),
    ):
        return await _interaction_report(request, db, identity, event_id=event_id, kind="review", target_id=review_id)

    @app.post("/api/account/events/{event_id}/reviews", status_code=201)
    async def account_post_event_review(
        event_id: str,
        request: Request,
        identity: AccountIdentity = Depends(require_account_write),
        db: Session = Depends(get_db),
    ):
        event_id, _event = _interaction_event_for_write(db, event_id)
        participation = _interaction_participation(db, identity.account_id, event_id)
        # Phase 9: a verified buyer (active recording access) may review too; the badge is decided here, never by the client.
        recording_row = _recording_for_event(db, event_id)
        recording_viewer = _recording_viewer(
            db, recording_row, account=identity, staff=False, participation=participation, now=_utc_now(),
        )
        buyer = recording_viewer.access_state == "active"
        if not participation.attended and not buyer:
            sellable = recording_row is not None and recording_row.status in {"published", "sales_paused"}
            raise HTTPException(
                403,
                {
                    "code": "review_not_eligible",
                    "reason": "attendance_or_purchase_required" if sellable else "attendance_required",
                    "registered": participation.registered,
                },
            )
        payload = await _read_json_object(request, 16_384)
        if set(payload) - {"body"}:
            raise HTTPException(400, "invalid_review")
        try:
            body = interaction_mod.clean_text(
                payload.get("body"), interaction_mod.REVIEW_MAX_CHARS, field="body",
                minimum=interaction_mod.REVIEW_MIN_CHARS, required=True,
            )
        except interaction_mod.InteractionError as error:
            raise _interaction_error(error) from None
        existing = db.scalar(
            select(EventReviewRecord).where(
                EventReviewRecord.event_id == event_id, EventReviewRecord.account_id == identity.account_id,
            )
        )
        if existing is not None:
            raise HTTPException(409, {"code": "review_exists", "id": existing.id, "status": existing.status})
        record = EventReviewRecord(
            id=interaction_mod.new_id(), event_id=event_id, account_id=identity.account_id,
            response_id=participation.response_id,
            author_label=interaction_mod.author_label(_interaction_display_name(db, identity.account_id)),
            verified_attendee=bool(participation.attended), badge="attendee" if participation.attended else "buyer",
            body=body, status="pending",
        )
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, {"code": "review_exists"}) from None
        db.refresh(record)
        return interaction_mod.review_public_view(record, viewer_account_id=identity.account_id)

    def _own_review(db: Session, identity: AccountIdentity, event_id: str, review_id: str) -> EventReviewRecord:
        parsed = interaction_mod.parse_row_id(review_id)
        record = db.get(EventReviewRecord, parsed) if parsed else None
        if record is None or record.event_id != event_id or record.account_id != identity.account_id:
            raise HTTPException(404, "review_not_found")
        return record

    @app.put("/api/account/events/{event_id}/reviews/{review_id}")
    async def account_edit_event_review(
        event_id: str, review_id: str, request: Request,
        identity: AccountIdentity = Depends(require_account_write), db: Session = Depends(get_db),
    ):
        event_id, _event = _interaction_event_for_write(db, event_id)
        record = _own_review(db, identity, event_id, review_id)
        if record.status in {"hidden", "withdrawn"}:
            raise HTTPException(409, {"code": "review_locked", "status": record.status})
        payload = await _read_json_object(request, 16_384)
        if set(payload) - {"body"}:
            raise HTTPException(400, "invalid_review")
        try:
            body = interaction_mod.clean_text(
                payload.get("body"), interaction_mod.REVIEW_MAX_CHARS, field="body",
                minimum=interaction_mod.REVIEW_MIN_CHARS, required=True,
            )
        except interaction_mod.InteractionError as error:
            raise _interaction_error(error) from None
        if body != record.body:
            record.body = body
            record.edit_count += 1
            record.edited_at = _utc_now()
            # An edited text is a new submission: it leaves the public list until re-approved.
            record.status = "pending"
            db.commit()
            db.refresh(record)
        return interaction_mod.review_public_view(record, viewer_account_id=identity.account_id)

    @app.post("/api/account/events/{event_id}/reviews/{review_id}/withdraw")
    def account_withdraw_event_review(
        event_id: str, review_id: str,
        identity: AccountIdentity = Depends(require_account_write), db: Session = Depends(get_db),
    ):
        event_id, _event = _interaction_event_for_write(db, event_id)
        record = _own_review(db, identity, event_id, review_id)
        if record.status != "withdrawn":
            record.status = "withdrawn"
            db.commit()
            db.refresh(record)
        return interaction_mod.review_public_view(record, viewer_account_id=identity.account_id)

    # ── پنل: منابع ──

    def _admin_event_id(db: Session, event_id: str) -> str:
        try:
            event_id = interaction_mod.parse_event_id(event_id)
        except interaction_mod.InteractionError as error:
            raise _interaction_error(error) from None
        _public, stored = _interaction_event(db, event_id)
        if stored is None:
            raise HTTPException(404, "event_not_found")
        return event_id

    def _check_resource_session(db: Session, event_id: str, fields: dict[str, Any]) -> None:
        """A resource may only hang off a session of *this* event's recorded product."""
        session_id = fields.get("session_id")
        if not session_id:
            return
        session = db.get(RecordingSessionRecord, session_id)
        recording = db.get(EventRecordingRecord, session.recording_id) if session is not None else None
        if session is None or recording is None or recording.event_id != event_id:
            raise HTTPException(404, "session_not_found")

    def _admin_resource(db: Session, event_id: str, resource_id: str) -> EventResourceRecord:
        parsed = interaction_mod.parse_row_id(resource_id)
        record = db.get(EventResourceRecord, parsed) if parsed else None
        if record is None or record.event_id != event_id:
            raise HTTPException(404, "resource_not_found")
        return record

    @app.get("/api/admin/events/{event_id}/resources")
    def admin_list_event_resources(
        event_id: str,
        request: Request,
        response: Response,
        include_removed: bool = Query(default=False),
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission(*_INTERACTION_READ_PERMS)),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        event_id = _admin_event_id(db, event_id)
        query = select(EventResourceRecord).where(EventResourceRecord.event_id == event_id)
        if not include_removed:
            query = query.where(EventResourceRecord.status != "removed")
        rows = db.scalars(query.order_by(EventResourceRecord.sort_order.asc(), EventResourceRecord.created_at.asc())).all()
        return {
            "source": "shared_server_database",
            "event_id": event_id,
            "items": [_resource_admin_view(request, row) for row in rows],
            "limits": _resource_limits(request),
        }

    @app.post("/api/admin/events/{event_id}/resources", status_code=201)
    async def admin_create_event_resource(
        event_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_INTERACTION_RESOURCE_PERMS)),
        db: Session = Depends(get_db),
    ):
        event_id = _admin_event_id(db, event_id)
        payload = await _read_json_object(request, 16_384)
        acknowledged = _pop_external_acknowledgement(payload)
        try:
            fields = interaction_mod.validate_resource_fields(
                payload, existing=None, parse_datetime=event_time.parse_event_datetime
            )
        except interaction_mod.InteractionError as error:
            raise _interaction_error(error) from None
        if fields.get("status") == "published" and fields.get("kind", "file") == "file":
            # A file row cannot be published before its bytes exist.
            raise HTTPException(409, {"code": "resource_file_missing"})
        ack_used = _require_external_exposure_ack(
            kind=str(fields.get("kind", "file")), before=None,
            after=(str(fields.get("status", "draft")), str(fields.get("access", "public"))), acknowledged=acknowledged,
        )
        _check_resource_session(db, event_id, fields)
        actor_kind, actor_id = _interaction_actor(identity)
        record = EventResourceRecord(
            id=interaction_mod.new_id(), event_id=event_id, created_by_kind=actor_kind, created_by_id=actor_id,
            status=fields.pop("status", "draft"), **fields,
        )
        db.add(record)
        create_details: dict[str, Any] = {"event_id": event_id, "kind": record.kind, "access": record.access, "status": record.status}
        if ack_used:
            create_details["external_exposure_acknowledged"] = True
        record_audit(
            db, identity, "event_resource.create", target_type="event_resource", target_id=record.id,
            details=create_details,
        )
        db.commit()
        db.refresh(record)
        return _resource_admin_view(request, record)

    @app.put("/api/admin/events/{event_id}/resources/{resource_id}")
    async def admin_update_event_resource(
        event_id: str,
        resource_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_INTERACTION_RESOURCE_PERMS)),
        db: Session = Depends(get_db),
    ):
        event_id = _admin_event_id(db, event_id)
        record = _admin_resource(db, event_id, resource_id)
        if record.status == "removed":
            raise HTTPException(409, {"code": "resource_removed"})
        payload = await _read_json_object(request, 16_384)
        acknowledged = _pop_external_acknowledgement(payload)
        try:
            fields = interaction_mod.validate_resource_fields(
                payload, existing=record, parse_datetime=event_time.parse_event_datetime
            )
        except interaction_mod.InteractionError as error:
            raise _interaction_error(error) from None
        if "kind" in fields and fields["kind"] != record.kind:
            raise HTTPException(409, {"code": "resource_kind_immutable"})
        if fields.get("status") == "published" and record.kind == "file" and not _resource_has_bytes(request, record):
            raise HTTPException(409, {"code": "resource_file_missing"})
        ack_used = _require_external_exposure_ack(
            kind=record.kind, before=(record.status, record.access),
            after=(str(fields.get("status", record.status)), str(fields.get("access", record.access))), acknowledged=acknowledged,
        )
        _check_resource_session(db, event_id, fields)
        before = {"access": record.access, "status": record.status, "publish_at": interaction_mod.iso(record.publish_at)}
        for key, value in fields.items():
            setattr(record, key, value)
        after = {"access": record.access, "status": record.status, "publish_at": interaction_mod.iso(record.publish_at)}
        changed = sorted(fields)
        # Audit details are flat scalars (see audit.sanitize_details): before/after per watched key.
        details: dict[str, Any] = {"event_id": event_id, "changed": ",".join(changed)[:200]}
        if ack_used:
            details["external_exposure_acknowledged"] = True
        for key in ("access", "status", "publish_at"):
            if before[key] != after[key]:
                details[f"{key}_before"] = before[key]
                details[f"{key}_after"] = after[key]
        if before["status"] == "published" and record.status != "published":
            # Back to draft: a later re-publish is a new announcement decision (dedupe key still guards the outbox).
            record.announced_at = None
        if before["status"] != "published" and record.status == "published" and record.session_id:
            now = _utc_now()
            live_now = record.publish_at is None or _as_utc(record.publish_at) <= now
            product = db.scalar(
                select(EventRecordingRecord).join(RecordingSessionRecord, RecordingSessionRecord.recording_id == EventRecordingRecord.id)
                .where(RecordingSessionRecord.id == record.session_id)
            )
            session_row = db.get(RecordingSessionRecord, record.session_id)
            if live_now and product is not None and session_row is not None and session_row.status == "published":
                details["notified_holders"] = _notify_content_published(
                    db, product, what="resource", target_id=record.id, title_text=record.title, now=now,
                )
                record.announced_at = now
            elif not live_now:
                # Scheduled: nothing is visible yet; the scheduler (timer / manual run) announces at publish_at.
                details["scheduled_announcement"] = True
        record_audit(
            db, identity, "event_resource.update", target_type="event_resource", target_id=record.id,
            details=details,
        )
        db.commit()
        db.refresh(record)
        return _resource_admin_view(request, record)

    @app.put("/api/admin/events/{event_id}/resources/{resource_id}/file")
    async def admin_upload_event_resource_file(
        event_id: str,
        resource_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_INTERACTION_RESOURCE_PERMS)),
        db: Session = Depends(get_db),
    ):
        """Upload or replace the bytes of a file resource (raw body + ``X-File-Name``).

        With the private storage configured the body streams straight to a staged file (hashed on
        the way, never held in memory) up to ``private_storage_max_bytes``; the row only points at
        the new key after the file is fsync-ed and renamed, so an aborted or rejected upload leaves
        the previous bytes untouched. Without it, the legacy inline path (≤ 8 MiB) applies.
        """
        event_id = _admin_event_id(db, event_id)
        record = _admin_resource(db, event_id, resource_id)
        if record.status == "removed" or record.kind != "file":
            raise HTTPException(409, {"code": "resource_not_file"})
        cfg: Settings = request.app.state.settings
        _enforce_owner_upload_limit(request, db, cfg, identity, limit=60, scope="event-resource-upload")
        declared = unquote(request.headers.get("x-file-name", "resource"))
        store = _private_storage(request)
        limit = store.max_bytes if store is not None else interaction_mod.MAX_BYTES

        def rejected(code: str, size: int, status: int) -> HTTPException:
            record_audit(
                db, identity, "event_resource.file", target_type="event_resource", target_id=record.id,
                outcome="rejected", details={"code": code, "size": size, "backend": "local_disk" if store else "database"},
            )
            db.commit()
            return HTTPException(status, code if status == 413 else {"code": code})

        pending: storage_mod.PendingUpload | None = None
        chunks: list[bytes] = []
        size = 0
        try:
            if store is not None:
                pending = store.begin()
            async for chunk in request.stream():
                if not chunk:
                    continue
                size += len(chunk)
                if size > limit:
                    raise rejected("file_too_large", size, 413)
                if pending is not None:
                    pending.write(chunk)
                else:
                    chunks.append(chunk)
            head = pending.head if pending is not None else b"".join(chunks)[:8192]
            try:
                content_type = interaction_mod.sniff_content_type(head, declared)
                if content_type not in interaction_mod.CONTENT_TYPES:
                    raise interaction_mod.InteractionError("file_type_not_allowed", status=415)
                file_name = interaction_mod.safe_file_name(declared, content_type)
            except interaction_mod.InteractionError as error:
                record_audit(
                    db, identity, "event_resource.file", target_type="event_resource", target_id=record.id,
                    outcome="rejected", details={"code": error.code, "size": size},
                )
                db.commit()
                raise _interaction_error(error) from None
            previous_hash, previous_key = record.content_hash, record.storage_key
            if pending is not None:
                stored = pending.commit()
                pending = None
                record.content = None
                record.storage_key = stored.key
                record.content_size = stored.size
                record.content_hash = stored.sha256
            else:
                content = b"".join(chunks)
                record.content = content
                record.storage_key = None
                record.content_size = len(content)
                record.content_hash = hashlib.sha256(content).hexdigest()
            record.content_type = content_type
            record.file_name = file_name
            record_audit(
                db, identity, "event_resource.file", target_type="event_resource", target_id=record.id,
                details={
                    "event_id": event_id, "content_type": content_type, "size": record.content_size,
                    "backend": "local_disk" if record.storage_key else "database",
                    "replaced": bool(previous_hash), "previous_hash": previous_hash[:16],
                    "previous_storage_key": previous_key or "",
                },
            )
            db.commit()
        except storage_mod.StorageError as error:
            if pending is not None:
                pending.abort()
                pending = None
            record_audit(
                db, identity, "event_resource.file", target_type="event_resource", target_id=record.id,
                outcome="rejected", details={"code": error.code, "size": size},
            )
            db.commit()
            raise HTTPException(413 if error.code == "file_too_large" else 503, {"code": error.code}) from None
        finally:
            if pending is not None:  # any other failure (client abort, DB error): no trace on disk
                pending.abort()
        if previous_key and previous_key != record.storage_key and store is not None:
            # Old bytes go only after the row points elsewhere (committed); purchases/access rows are untouched.
            removed = store.delete(previous_key)
            record_audit(
                db, identity, "event_resource.file_pruned", target_type="event_resource", target_id=record.id,
                outcome="ok" if removed else "missing", details={"previous_storage_key": previous_key},
            )
            db.commit()
        db.refresh(record)
        return _resource_admin_view(request, record)

    # ── Phase 9.5 §5.2: resumable upload sessions (internal, limited protocol; see backend/upload_sessions.py) ──

    def _upload_error(error: upload_mod.UploadSessionError) -> HTTPException:
        detail: dict[str, Any] = {"code": error.code}
        detail.update(error.extra)
        return HTTPException(error.status, detail)

    def _upload_store(request: Request) -> storage_mod.LocalPrivateStorage:
        store = _private_storage(request)
        if store is None:
            raise HTTPException(409, {"code": "resumable_requires_private_storage"})
        return store

    def _upload_session_lock(session_id: str) -> asyncio.Lock:
        lock = _UPLOAD_SESSION_LOCKS.get(session_id)
        if lock is None:
            if len(_UPLOAD_SESSION_LOCKS) > 512:  # bounded: forget idle locks (sessions are short-lived)
                for key, candidate in list(_UPLOAD_SESSION_LOCKS.items()):
                    if not candidate.locked():
                        _UPLOAD_SESSION_LOCKS.pop(key, None)
            lock = _UPLOAD_SESSION_LOCKS[session_id] = asyncio.Lock()
        return lock

    def _upload_session_audit(
        db: Session, identity: OwnerIdentity | AccountIdentity, action: str, session: UploadSessionRecord, *,
        outcome: str = "ok", **details: Any,
    ) -> None:
        record_audit(
            db, identity, action, target_type="event_resource", target_id=session.resource_id, outcome=outcome,
            details={"session_id": session.id, "event_id": session.event_id, "status": session.status,
                     "received_bytes": session.received_bytes, "expected_size": session.expected_size, **details},
        )

    @app.post("/api/admin/events/{event_id}/resources/{resource_id}/upload-sessions")
    async def admin_start_upload_session(
        event_id: str,
        resource_id: str,
        request: Request,
        response: Response,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_INTERACTION_RESOURCE_PERMS)),
        db: Session = Depends(get_db),
    ):
        """Open (or resume) a resumable upload for a file resource — private storage only."""
        event_id = _admin_event_id(db, event_id)
        record = _admin_resource(db, event_id, resource_id)
        if record.status == "removed" or record.kind != "file":
            raise HTTPException(409, {"code": "resource_not_file"})
        store = _upload_store(request)
        cfg: Settings = request.app.state.settings
        payload = await _read_json_object(request, min(cfg.max_request_bytes, 4096))
        if set(payload) - {"size", "sha256", "file_name"}:
            raise HTTPException(400, "invalid_upload_session")
        now = _utc_now()
        upload_mod.expire_stale(db, store, now)
        file_name = str(payload.get("file_name") or "resource")
        try:
            session, resumed = upload_mod.start(
                db, store, record=record, event_id=event_id, actor=_interaction_actor(identity),
                size=payload.get("size"), sha256=payload.get("sha256"), file_name=file_name, now=now,
            )
        except upload_mod.UploadSessionError as error:
            record_audit(
                db, identity, "event_resource.upload_session", target_type="event_resource", target_id=record.id,
                outcome="rejected", details={"code": error.code, "event_id": event_id, "size": payload.get("size")},
            )
            db.commit()
            raise _upload_error(error) from None
        if not resumed:
            _enforce_owner_upload_limit(request, db, cfg, identity, limit=60, scope="event-resource-upload")
            _upload_session_audit(db, identity, "event_resource.upload_session", session, file_name=session.declared_name)
        db.commit()
        response.status_code = 200 if resumed else 201
        return upload_mod.view(session, offset=store.part_size(session.part_id) or 0, resumed=resumed)

    @app.get("/api/admin/events/{event_id}/resources/{resource_id}/upload-sessions/{session_id}")
    def admin_upload_session_status(
        event_id: str,
        resource_id: str,
        session_id: str,
        request: Request,
        response: Response,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission(*_INTERACTION_RESOURCE_PERMS)),
        db: Session = Depends(get_db),
    ):
        """The resume point: the offset is the staged file's size on disk (cross-checked with the row)."""
        event_id = _admin_event_id(db, event_id)
        record = _admin_resource(db, event_id, resource_id)
        store = _upload_store(request)
        response.headers["Cache-Control"] = "no-store"
        try:
            session = upload_mod.load_open(db, store, session_id=session_id, record=record, actor=_interaction_actor(identity), now=_utc_now())
            db.commit()
            offset = upload_mod.current_offset(store, session) if session.status in ("open", "completing") else session.received_bytes
        except upload_mod.UploadSessionError as error:
            db.commit()
            raise _upload_error(error) from None
        return upload_mod.view(session, offset=offset)

    @app.patch("/api/admin/events/{event_id}/resources/{resource_id}/upload-sessions/{session_id}")
    async def admin_upload_session_chunk(
        event_id: str,
        resource_id: str,
        session_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_INTERACTION_RESOURCE_PERMS)),
        db: Session = Depends(get_db),
    ):
        """Append one chunk at ``Upload-Offset`` with a mandatory ``Upload-Checksum: sha256 <hex>``.

        The body is bounded by ``MAX_CHUNK_BYTES`` (buffered, then appended + fsync-ed). A stale or
        duplicate offset is refused with the real offset so the client re-syncs; a checksum mismatch
        never leaves bytes behind.
        """
        event_id = _admin_event_id(db, event_id)
        record = _admin_resource(db, event_id, resource_id)
        store = _upload_store(request)
        actor = _interaction_actor(identity)
        try:
            checksum = upload_mod.parse_checksum_header(request.headers.get("upload-checksum"))
            raw_offset = request.headers.get("upload-offset", "")
            if not raw_offset.isdigit():
                raise upload_mod.UploadSessionError("upload_offset_required", 400)
            offset = int(raw_offset)
        except upload_mod.UploadSessionError as error:
            raise _upload_error(error) from None
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > upload_mod.MAX_CHUNK_BYTES:
            raise HTTPException(413, {"code": "chunk_too_large", "max_chunk_bytes": upload_mod.MAX_CHUNK_BYTES})
        pieces: list[bytes] = []
        received = 0
        try:
            async for piece in request.stream():
                if not piece:
                    continue
                received += len(piece)
                if received > upload_mod.MAX_CHUNK_BYTES:
                    raise HTTPException(413, {"code": "chunk_too_large", "max_chunk_bytes": upload_mod.MAX_CHUNK_BYTES})
                pieces.append(piece)
        except ClientDisconnect:
            # Nothing was appended: the next GET returns the unchanged offset and the client resumes.
            raise HTTPException(400, {"code": "client_disconnected"}) from None
        body = b"".join(pieces)
        del pieces
        async with _upload_session_lock(session_id):
            now = _utc_now()
            try:
                session = upload_mod.load_open(db, store, session_id=session_id, record=record, actor=actor, now=now, for_update=True)
                try:
                    new_size = upload_mod.append(store, session, offset=offset, body=body, checksum=checksum, now=now)
                except storage_mod.StorageError as error:
                    upload_mod.fail(store, session, code=error.code, now=now)
                    _upload_session_audit(db, identity, "event_resource.upload_chunk", session, outcome="rejected", code=error.code)
                    db.commit()
                    raise HTTPException(413 if error.code == "file_too_large" else 503, {"code": error.code}) from None
                db.commit()
            except upload_mod.UploadSessionError as error:
                db.commit()
                raise _upload_error(error) from None
        return {"id": session.id, "offset": new_size, "expected_size": session.expected_size,
                "complete": new_size == session.expected_size, "chunk_count": session.chunk_count}

    @app.post("/api/admin/events/{event_id}/resources/{resource_id}/upload-sessions/{session_id}/complete")
    async def admin_upload_session_complete(
        event_id: str,
        resource_id: str,
        session_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_INTERACTION_RESOURCE_PERMS)),
        db: Session = Depends(get_db),
    ):
        """Verify size + sha256 + sniffed type, then switch the resource to the new bytes atomically."""
        event_id = _admin_event_id(db, event_id)
        record = _admin_resource(db, event_id, resource_id)
        if record.status == "removed" or record.kind != "file":
            raise HTTPException(409, {"code": "resource_not_file"})
        store = _upload_store(request)
        cfg: Settings = request.app.state.settings
        payload = await _read_json_object(request, min(cfg.max_request_bytes, 4096))
        if set(payload) - {"sha256"}:
            raise HTTPException(400, "invalid_upload_complete")
        actor = _interaction_actor(identity)
        async with _upload_session_lock(session_id):
            now = _utc_now()
            try:
                session = upload_mod.load_open(db, store, session_id=session_id, record=record, actor=actor, now=now, for_update=True)
                expected_digest = upload_mod.begin_complete(store, session, sha256=payload.get("sha256"), now=now)
                db.commit()  # the lock is visible to everybody from here on (one finalizer only)
            except upload_mod.UploadSessionError as error:
                db.commit()
                raise _upload_error(error) from None

            def reject(code: str, status: int) -> HTTPException:
                upload_mod.fail(store, session, code=code, now=_utc_now())
                _upload_session_audit(db, identity, "event_resource.upload_complete", session, outcome="rejected", code=code)
                db.commit()
                return HTTPException(status, {"code": code})

            try:
                actual_digest = store.part_sha256(session.part_id)
                if actual_digest != expected_digest:
                    raise reject("sha256_mismatch", 422)
                head = store.part_head(session.part_id)
                try:
                    content_type = interaction_mod.sniff_content_type(head, session.declared_name)
                    if content_type not in interaction_mod.CONTENT_TYPES:
                        raise interaction_mod.InteractionError("file_type_not_allowed", status=415)
                    file_name = interaction_mod.safe_file_name(session.declared_name, content_type)
                except interaction_mod.InteractionError as error:
                    raise reject(error.code, error.status) from None
                previous_hash, previous_key = record.content_hash, record.storage_key
                stored = store.commit_part(session.part_id, expected_size=session.expected_size, sha256=actual_digest)
            except storage_mod.StorageError as error:
                raise reject(error.code, 413 if error.code == "file_too_large" else 503) from None
            record.content = None
            record.storage_key = stored.key
            record.content_size = stored.size
            record.content_hash = stored.sha256
            record.content_type = content_type
            record.file_name = file_name
            session.status = "completed"
            session.storage_key = stored.key
            session.completed_at = now
            session.updated_at = now
            record_audit(
                db, identity, "event_resource.file", target_type="event_resource", target_id=record.id,
                details={
                    "event_id": event_id, "content_type": content_type, "size": record.content_size,
                    "backend": "local_disk", "via": "resumable", "session_id": session.id, "chunks": session.chunk_count,
                    "replaced": bool(previous_hash), "previous_hash": (previous_hash or "")[:16],
                    "previous_storage_key": previous_key or "",
                },
            )
            db.commit()
        if previous_key and previous_key != record.storage_key:
            removed = store.delete(previous_key)
            record_audit(
                db, identity, "event_resource.file_pruned", target_type="event_resource", target_id=record.id,
                outcome="ok" if removed else "missing", details={"previous_storage_key": previous_key},
            )
            db.commit()
        db.refresh(record)
        result = _resource_admin_view(request, record)
        result["upload_session"] = upload_mod.view(session)
        return result

    @app.delete("/api/admin/events/{event_id}/resources/{resource_id}/upload-sessions/{session_id}")
    def admin_upload_session_abort(
        event_id: str,
        resource_id: str,
        session_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_INTERACTION_RESOURCE_PERMS)),
        db: Session = Depends(get_db),
    ):
        event_id = _admin_event_id(db, event_id)
        record = _admin_resource(db, event_id, resource_id)
        store = _upload_store(request)
        now = _utc_now()
        try:
            session = upload_mod.load_open(db, store, session_id=session_id, record=record, actor=_interaction_actor(identity), now=now)
        except upload_mod.UploadSessionError as error:
            db.commit()
            raise _upload_error(error) from None
        if session.status in ("open", "completing"):
            session.status = "aborted"
            session.error_code = "aborted_by_client"
            session.updated_at = now
            store.discard_part(session.part_id)
            _upload_session_audit(db, identity, "event_resource.upload_abort", session)
        db.commit()
        return upload_mod.view(session)

    @app.get("/api/admin/storage/health")
    def admin_storage_health(
        request: Request,
        response: Response,
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission(*_INTERACTION_RESOURCE_PERMS)),
        db: Session = Depends(get_db),
    ):
        """Phase 9.5 §5.1: honest storage view — path-free, read-only.

        ``configured``/``free_bytes``/``writable``, referenced rows and bytes, rows whose file is
        missing or has the wrong size, orphan files without a row, incomplete parts (open sessions
        and stale parts), and the last backup/verify markers written by
        ``tools/private-storage-backup.py``. Nothing here deletes or repairs.
        """
        response.headers["Cache-Control"] = "no-store"
        store = _private_storage(request)
        now = _utc_now()
        rows = db.execute(
            select(EventResourceRecord.id, EventResourceRecord.storage_key, EventResourceRecord.content_size, EventResourceRecord.status)
            .where(EventResourceRecord.storage_key.is_not(None))
        ).all()
        inline = db.execute(
            select(func.count(EventResourceRecord.id), func.coalesce(func.sum(EventResourceRecord.content_size), 0))
            .where(EventResourceRecord.storage_key.is_(None), EventResourceRecord.content.is_not(None))
        ).one()
        markers = {
            row.key: {"at": interaction_mod.iso(row.updated_at), **(row.value if isinstance(row.value, dict) else {})}
            for row in db.scalars(select(SystemMarkerRecord).where(SystemMarkerRecord.key.in_(
                ("storage_verify", "storage_snapshot", "storage_restore", "scheduled_publish")
            ))).all()
        }
        sessions = db.execute(
            select(UploadSessionRecord.status, func.count(UploadSessionRecord.id), func.coalesce(func.sum(UploadSessionRecord.received_bytes), 0))
            .group_by(UploadSessionRecord.status)
        ).all()
        session_counts = {status: {"count": int(count), "bytes": int(total)} for status, count, total in sessions}
        base = {
            "generated_at": now.isoformat(),
            "read_only": True,
            "max_bytes": store.max_bytes if store is not None else interaction_mod.MAX_BYTES,
            "inline": {"rows": int(inline[0]), "bytes": int(inline[1]), "max_bytes": interaction_mod.MAX_BYTES},
            "upload_sessions": session_counts,
            "markers": markers,
        }
        if store is None:
            base.update({
                "configured": False, "backend": "database", "free_bytes": None, "writable": None,
                "referenced": {"rows": len(rows), "bytes": int(sum(r.content_size or 0 for r in rows))},
                "missing": {"count": len(rows), "resource_ids": [r.id for r in rows][:50]},
                "size_mismatch": {"count": 0, "resource_ids": []},
                "orphans": {"count": 0, "bytes": 0}, "incomplete": {"parts": 0, "bytes": 0, "stale_parts": 0},
                "state": "not_configured" if rows else "inline_only",
            })
            return base
        status = store.status()
        missing: list[str] = []
        mismatch: list[str] = []
        referenced_bytes = 0
        referenced_keys: set[str] = set()
        for row in rows:
            referenced_keys.add(row.storage_key)
            size = store.size(row.storage_key)
            if size is None:
                missing.append(row.id)
            elif size != (row.content_size or 0):
                mismatch.append(row.id)
            else:
                referenced_bytes += size
        orphan_count = 0
        orphan_bytes = 0
        for key in store.list_keys():
            if key not in referenced_keys:
                orphan_count += 1
                orphan_bytes += store.size(key) or 0
        parts = store.incoming_parts()
        open_part_ids = set(db.scalars(select(UploadSessionRecord.part_id).where(UploadSessionRecord.status.in_(("open", "completing")))).all())
        stale_cutoff = now.timestamp() - upload_mod.SESSION_TTL.total_seconds()
        stale = [p for p in parts if p[0] not in open_part_ids and p[2] < stale_cutoff]
        state = "error" if missing or mismatch else ("warning" if orphan_count or stale or not status.writable else "ok")
        base.update({
            "configured": True, "backend": status.backend, "free_bytes": status.free_bytes, "writable": status.writable,
            "referenced": {"rows": len(rows), "bytes": referenced_bytes},
            "missing": {"count": len(missing), "resource_ids": missing[:50]},
            "size_mismatch": {"count": len(mismatch), "resource_ids": mismatch[:50]},
            "orphans": {"count": orphan_count, "bytes": orphan_bytes},
            "incomplete": {"parts": len(parts), "bytes": int(sum(p[1] for p in parts)), "stale_parts": len(stale),
                           "open_sessions": len(open_part_ids)},
            "state": state,
        })
        return base

    @app.post("/api/admin/events/{event_id}/resources/{resource_id}/remove")
    async def admin_remove_event_resource(
        event_id: str,
        resource_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_INTERACTION_RESOURCE_PERMS)),
        db: Session = Depends(get_db),
    ):
        """Logical removal: the row (and its audit trail) stays; downloads stop immediately."""
        event_id = _admin_event_id(db, event_id)
        record = _admin_resource(db, event_id, resource_id)
        payload = await _read_json_object(request, 4096)
        if set(payload) - {"reason"}:
            raise HTTPException(400, "invalid_removal")
        try:
            reason = interaction_mod.clean_text(payload.get("reason"), interaction_mod.REASON_MAX_CHARS, field="reason")
        except interaction_mod.InteractionError as error:
            raise _interaction_error(error) from None
        if record.status != "removed":
            record.status = "removed"
            record.removed_at = _utc_now()
            record.removed_reason = reason
            record.content = None
            record_audit(
                db, identity, "event_resource.remove", target_type="event_resource", target_id=record.id,
                details={"event_id": event_id, "reason": reason, "size": record.content_size},
            )
            db.commit()
            db.refresh(record)
        return _resource_admin_view(request, record)

    # ── پنل: پرسش‌وپاسخ ──

    def _admin_question(db: Session, event_id: str, question_id: str) -> EventQuestionRecord:
        parsed = interaction_mod.parse_row_id(question_id)
        record = db.get(EventQuestionRecord, parsed) if parsed else None
        if record is None or record.event_id != event_id:
            raise HTTPException(404, "question_not_found")
        return record

    def _admin_question_rows(
        db: Session, rows: Sequence[EventQuestionRecord]
    ) -> list[dict[str, Any]]:
        titles = _interaction_event_titles(db, {row.event_id for row in rows})
        counts = interaction_mod.open_report_counts(db, "question", [row.id for row in rows])
        return [
            interaction_mod.question_admin_view(
                row, notification=_interaction_question_notification(db, row),
                open_reports=counts.get(row.id, 0), event_title=titles.get(row.event_id, ""),
            )
            for row in rows
        ]

    def _question_filters(status: str, answered: str) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = []
        if status:
            if status not in interaction_mod.QUESTION_STATUSES:
                raise HTTPException(422, {"code": "invalid_choice", "field": "status"})
            filters.append(EventQuestionRecord.status == status)
        if answered == "false":
            filters.append(EventQuestionRecord.answered_at.is_(None))
        elif answered == "true":
            filters.append(EventQuestionRecord.answered_at.is_not(None))
        elif answered:
            raise HTTPException(422, {"code": "invalid_choice", "field": "answered"})
        return filters

    @app.get("/api/admin/events/{event_id}/questions")
    def admin_list_event_questions(
        event_id: str,
        response: Response,
        status: str = Query(default="", max_length=16),
        answered: str = Query(default="", max_length=8),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0, le=100_000),
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission(*_INTERACTION_READ_PERMS)),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        event_id = _admin_event_id(db, event_id)
        filters = [EventQuestionRecord.event_id == event_id, *_question_filters(status, answered)]
        total = int(db.scalar(select(func.count(EventQuestionRecord.id)).where(*filters)) or 0)
        rows = db.scalars(
            select(EventQuestionRecord).where(*filters)
            .order_by(EventQuestionRecord.created_at.desc(), EventQuestionRecord.id).limit(limit).offset(offset)
        ).all()
        return {"source": "shared_server_database", "event_id": event_id, "items": _admin_question_rows(db, rows),
                "total": total, "limit": limit, "offset": offset}

    @app.get("/api/admin/event-questions")
    def admin_list_all_event_questions(
        response: Response,
        status: str = Query(default="", max_length=16),
        answered: str = Query(default="false", max_length=8),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0, le=100_000),
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission(*_INTERACTION_READ_PERMS)),
        db: Session = Depends(get_db),
    ):
        """Cross-event work list (unanswered by default) for the existing events section."""
        response.headers["Cache-Control"] = "private, no-store"
        filters = _question_filters(status, answered)
        total = int(db.scalar(select(func.count(EventQuestionRecord.id)).where(*filters)) or 0)
        rows = db.scalars(
            select(EventQuestionRecord).where(*filters)
            .order_by(EventQuestionRecord.created_at.asc(), EventQuestionRecord.id).limit(limit).offset(offset)
        ).all()
        return {"source": "shared_server_database", "items": _admin_question_rows(db, rows),
                "total": total, "limit": limit, "offset": offset}

    @app.post("/api/admin/events/{event_id}/questions/{question_id}/answer")
    async def admin_answer_event_question(
        event_id: str,
        question_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_INTERACTION_MODERATE_PERMS)),
        db: Session = Depends(get_db),
    ):
        """Persist the answer first; the notification is queued afterwards and never blocks it."""
        event_id = _admin_event_id(db, event_id)
        record = _admin_question(db, event_id, question_id)
        payload = await _read_json_object(request, 32_768)
        if set(payload) - {"answer", "official", "publish", "label"}:
            raise HTTPException(400, "invalid_answer")
        try:
            answer = interaction_mod.clean_text(
                payload.get("answer"), interaction_mod.ANSWER_MAX_CHARS, field="answer", required=True, minimum=2,
            )
            label = interaction_mod.clean_text(payload.get("label"), 120, field="label")
        except interaction_mod.InteractionError as error:
            raise _interaction_error(error) from None
        official = payload.get("official", True)
        publish = payload.get("publish", True)
        if not isinstance(official, bool) or not isinstance(publish, bool):
            raise HTTPException(422, {"code": "invalid_choice", "field": "official"})
        actor_kind, actor_id = _interaction_actor(identity)
        first_answer = record.answered_at is None
        record.answer_body = answer
        record.answer_official = official
        record.answered_at = _utc_now()
        record.answered_by_kind = actor_kind
        record.answered_by_id = actor_id
        record.answer_label = label or interaction_mod.ANSWER_LABEL_DEFAULT
        if publish and record.status != "hidden":
            record.status = "published"
        db.flush()
        titles = _interaction_event_titles(db, {event_id})
        notification = _queue_question_answer_notification(db, record, titles.get(event_id, ""))
        record_audit(
            db, identity, "event_question.answer", target_type="event_question", target_id=record.id,
            details={
                "event_id": event_id, "first_answer": first_answer, "official": official,
                "published": record.status == "published", "notification_id": notification.id,
                "notification_state": interaction_mod.delivery_state(notification.delivery_status, notification.delivery_attempts),
            },
        )
        db.commit()
        db.refresh(record)
        return _admin_question_rows(db, [record])[0]

    @app.post("/api/admin/events/{event_id}/questions/{question_id}/status")
    async def admin_set_event_question_status(
        event_id: str,
        question_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_INTERACTION_MODERATE_PERMS)),
        db: Session = Depends(get_db),
    ):
        event_id = _admin_event_id(db, event_id)
        record = _admin_question(db, event_id, question_id)
        payload = await _read_json_object(request, 4096)
        if set(payload) - {"status", "reason"}:
            raise HTTPException(400, "invalid_status")
        try:
            status = interaction_mod.choice(payload.get("status"), interaction_mod.QUESTION_STATUSES, field="status")
            reason = interaction_mod.clean_text(payload.get("reason"), interaction_mod.REASON_MAX_CHARS, field="reason")
        except interaction_mod.InteractionError as error:
            raise _interaction_error(error) from None
        if status == "hidden" and not reason:
            raise HTTPException(422, {"code": "text_required", "field": "reason"})
        previous = record.status
        actor_kind, actor_id = _interaction_actor(identity)
        record.status = status
        record.moderation_reason = reason
        record.moderated_by_kind = actor_kind
        record.moderated_by_id = actor_id
        record.moderated_at = _utc_now()
        if status == "hidden":
            db.execute(
                update(EventContentReportRecord)
                .where(
                    EventContentReportRecord.target_kind == "question",
                    EventContentReportRecord.target_id == record.id,
                    EventContentReportRecord.status == "open",
                )
                .values(status="resolved", resolution_note="hidden", resolved_by_kind=actor_kind,
                        resolved_by_id=actor_id, resolved_at=_utc_now())
            )
        record_audit(
            db, identity, "event_question.status", target_type="event_question", target_id=record.id,
            details={"event_id": event_id, "from": previous, "to": status, "reason": reason},
        )
        db.commit()
        db.refresh(record)
        return _admin_question_rows(db, [record])[0]

    @app.post("/api/admin/events/{event_id}/questions/{question_id}/resend-notification")
    def admin_resend_event_question_notification(
        event_id: str,
        question_id: str,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_INTERACTION_MODERATE_PERMS)),
        db: Session = Depends(get_db),
    ):
        """Re-queue the same outbox row (never a second one); delivered rows are left alone."""
        event_id = _admin_event_id(db, event_id)
        record = _admin_question(db, event_id, question_id)
        if record.answered_at is None:
            raise HTTPException(409, {"code": "question_not_answered"})
        titles = _interaction_event_titles(db, {event_id})
        notification = _queue_question_answer_notification(db, record, titles.get(event_id, ""))
        record_audit(
            db, identity, "event_question.notification_resend", target_type="event_question", target_id=record.id,
            details={
                "event_id": event_id, "notification_id": notification.id,
                "state": interaction_mod.delivery_state(notification.delivery_status, notification.delivery_attempts),
                "attempts": notification.delivery_attempts,
            },
        )
        db.commit()
        db.refresh(record)
        return _admin_question_rows(db, [record])[0]

    # ── پنل: دیدگاه‌ها و گزارش‌ها ──

    def _admin_review_rows(db: Session, rows: Sequence[EventReviewRecord]) -> list[dict[str, Any]]:
        titles = _interaction_event_titles(db, {row.event_id for row in rows})
        counts = interaction_mod.open_report_counts(db, "review", [row.id for row in rows])
        return [
            interaction_mod.review_admin_view(row, open_reports=counts.get(row.id, 0), event_title=titles.get(row.event_id, ""))
            for row in rows
        ]

    @app.get("/api/admin/events/{event_id}/reviews")
    def admin_list_event_reviews(
        event_id: str,
        response: Response,
        status: str = Query(default="", max_length=16),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0, le=100_000),
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission(*_INTERACTION_READ_PERMS)),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        event_id = _admin_event_id(db, event_id)
        filters: list[ColumnElement[bool]] = [EventReviewRecord.event_id == event_id]
        if status:
            if status not in interaction_mod.REVIEW_STATUSES:
                raise HTTPException(422, {"code": "invalid_choice", "field": "status"})
            filters.append(EventReviewRecord.status == status)
        total = int(db.scalar(select(func.count(EventReviewRecord.id)).where(*filters)) or 0)
        rows = db.scalars(
            select(EventReviewRecord).where(*filters)
            .order_by(EventReviewRecord.created_at.desc(), EventReviewRecord.id).limit(limit).offset(offset)
        ).all()
        return {"source": "shared_server_database", "event_id": event_id, "items": _admin_review_rows(db, rows),
                "total": total, "limit": limit, "offset": offset}

    @app.post("/api/admin/events/{event_id}/reviews/{review_id}/status")
    async def admin_set_event_review_status(
        event_id: str,
        review_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_INTERACTION_MODERATE_PERMS)),
        db: Session = Depends(get_db),
    ):
        event_id = _admin_event_id(db, event_id)
        parsed = interaction_mod.parse_row_id(review_id)
        record = db.get(EventReviewRecord, parsed) if parsed else None
        if record is None or record.event_id != event_id:
            raise HTTPException(404, "review_not_found")
        payload = await _read_json_object(request, 4096)
        if set(payload) - {"status", "reason"}:
            raise HTTPException(400, "invalid_status")
        try:
            status = interaction_mod.choice(payload.get("status"), ("pending", "published", "hidden"), field="status")
            reason = interaction_mod.clean_text(payload.get("reason"), interaction_mod.REASON_MAX_CHARS, field="reason")
        except interaction_mod.InteractionError as error:
            raise _interaction_error(error) from None
        if status == "hidden" and not reason:
            raise HTTPException(422, {"code": "text_required", "field": "reason"})
        if record.status == "withdrawn":
            raise HTTPException(409, {"code": "review_withdrawn"})
        previous = record.status
        actor_kind, actor_id = _interaction_actor(identity)
        record.status = status
        record.moderation_reason = reason
        record.moderated_by_kind = actor_kind
        record.moderated_by_id = actor_id
        record.moderated_at = _utc_now()
        if status == "hidden":
            db.execute(
                update(EventContentReportRecord)
                .where(
                    EventContentReportRecord.target_kind == "review",
                    EventContentReportRecord.target_id == record.id,
                    EventContentReportRecord.status == "open",
                )
                .values(status="resolved", resolution_note="hidden", resolved_by_kind=actor_kind,
                        resolved_by_id=actor_id, resolved_at=_utc_now())
            )
        record_audit(
            db, identity, "event_review.status", target_type="event_review", target_id=record.id,
            details={"event_id": event_id, "from": previous, "to": status, "reason": reason},
        )
        db.commit()
        db.refresh(record)
        return _admin_review_rows(db, [record])[0]

    @app.get("/api/admin/event-reports")
    def admin_list_event_reports(
        response: Response,
        status: str = Query(default="open", max_length=16),
        event_id: str = Query(default="", max_length=100),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0, le=100_000),
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission(*_INTERACTION_READ_PERMS)),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        filters: list[ColumnElement[bool]] = []
        if status:
            if status not in interaction_mod.REPORT_STATUSES:
                raise HTTPException(422, {"code": "invalid_choice", "field": "status"})
            filters.append(EventContentReportRecord.status == status)
        if event_id:
            filters.append(EventContentReportRecord.event_id == _admin_event_id(db, event_id))
        total = int(db.scalar(select(func.count(EventContentReportRecord.id)).where(*filters)) or 0)
        rows = db.scalars(
            select(EventContentReportRecord).where(*filters)
            .order_by(EventContentReportRecord.created_at.asc(), EventContentReportRecord.id).limit(limit).offset(offset)
        ).all()
        titles = _interaction_event_titles(db, {row.event_id for row in rows})
        items = []
        for row in rows:
            target: EventQuestionRecord | EventReviewRecord | None = (
                db.get(EventQuestionRecord, row.target_id) if row.target_kind == "question"
                else db.get(EventReviewRecord, row.target_id)
            )
            items.append(interaction_mod.report_admin_view(
                row, excerpt=target.body if target is not None else "", event_title=titles.get(row.event_id, ""),
            ))
        return {"source": "shared_server_database", "items": items, "total": total, "limit": limit, "offset": offset}

    @app.post("/api/admin/event-reports/{report_id}/resolve")
    async def admin_resolve_event_report(
        report_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_INTERACTION_MODERATE_PERMS)),
        db: Session = Depends(get_db),
    ):
        parsed = interaction_mod.parse_row_id(report_id)
        record = db.get(EventContentReportRecord, parsed) if parsed else None
        if record is None:
            raise HTTPException(404, "report_not_found")
        payload = await _read_json_object(request, 4096)
        if set(payload) - {"status", "note"}:
            raise HTTPException(400, "invalid_resolution")
        try:
            status = interaction_mod.choice(payload.get("status"), ("resolved", "dismissed"), field="status")
            note = interaction_mod.clean_text(payload.get("note"), interaction_mod.REASON_MAX_CHARS, field="note")
        except interaction_mod.InteractionError as error:
            raise _interaction_error(error) from None
        actor_kind, actor_id = _interaction_actor(identity)
        previous = record.status
        record.status = status
        record.resolution_note = note
        record.resolved_by_kind = actor_kind
        record.resolved_by_id = actor_id
        record.resolved_at = _utc_now()
        record_audit(
            db, identity, "event_report.resolve", target_type="event_content_report", target_id=record.id,
            details={"event_id": record.event_id, "target_kind": record.target_kind, "from": previous, "to": status, "note": note},
        )
        db.commit()
        return interaction_mod.report_admin_view(record)

    @app.get("/api/admin/event-interaction/summary")
    def admin_event_interaction_summary(
        response: Response,
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission(*_INTERACTION_READ_PERMS)),
        db: Session = Depends(get_db),
    ):
        """Honest counts for the panel badge: real rows, zero when nothing needs action."""
        response.headers["Cache-Control"] = "private, no-store"
        unanswered = int(db.scalar(
            select(func.count(EventQuestionRecord.id)).where(
                EventQuestionRecord.answered_at.is_(None), EventQuestionRecord.status != "hidden",
            )
        ) or 0)
        pending_reviews = int(db.scalar(
            select(func.count(EventReviewRecord.id)).where(EventReviewRecord.status == "pending")
        ) or 0)
        open_reports = int(db.scalar(
            select(func.count(EventContentReportRecord.id)).where(EventContentReportRecord.status == "open")
        ) or 0)
        failed_notifications = int(db.scalar(
            select(func.count(EventQuestionRecord.id))
            .join(UserNotificationRecord, UserNotificationRecord.id == EventQuestionRecord.notification_id)
            .where(UserNotificationRecord.delivery_status == "failed")
        ) or 0)
        per_event: dict[str, dict[str, int]] = {}
        for event_key, count in db.execute(
            select(EventQuestionRecord.event_id, func.count(EventQuestionRecord.id))
            .where(EventQuestionRecord.answered_at.is_(None), EventQuestionRecord.status != "hidden")
            .group_by(EventQuestionRecord.event_id)
        ).all():
            per_event.setdefault(str(event_key), {})["unanswered"] = int(count)
        for event_key, count in db.execute(
            select(EventReviewRecord.event_id, func.count(EventReviewRecord.id))
            .where(EventReviewRecord.status == "pending").group_by(EventReviewRecord.event_id)
        ).all():
            per_event.setdefault(str(event_key), {})["pending_reviews"] = int(count)
        for event_key, count in db.execute(
            select(EventResourceRecord.event_id, func.count(EventResourceRecord.id))
            .where(EventResourceRecord.status != "removed").group_by(EventResourceRecord.event_id)
        ).all():
            per_event.setdefault(str(event_key), {})["resources"] = int(count)
        return {
            "source": "shared_server_database",
            "unanswered_questions": unanswered,
            "pending_reviews": pending_reviews,
            "open_reports": open_reports,
            "failed_notifications": failed_notifications,
            "per_event": per_event,
        }

    # ── فاز ۹: محصول ضبط‌شدهٔ رویداد، سفارش خرید و دسترسی ──
    # محصول به همان رویداد site_content بسته است؛ فایل‌ها همان event_resources هستند
    # (access='purchased' + session_id). دسترسی فقط با ردیف recording_access یا
    # پیش‌نمایش ستاد تصمیم می‌گیرد؛ هیچ داده‌ای از مرورگر مبنای دسترسی نیست.
    _RECORDING_EDIT_PERMS = ("ev_create",)
    _RECORDING_STATUS_PERMS = ("ev_publish",)
    _RECORDING_ORDER_READ_PERMS = ("receipt_approve", "ev_publish", "finance")
    _RECORDING_DECISION_PERMS = ("receipt_approve",)
    _RECORDING_REFUND_PERMS = ("finance",)

    def _recording_error(error: interaction_mod.InteractionError) -> HTTPException:
        return _interaction_error(error)

    def _wallet_ready(db: Session, request: Request) -> bool:
        return bool(_runtime_settings(db, request.app.state.settings).form_bale_payments_ready)

    def _recording_for_event(db: Session, event_id: str, *, for_update: bool = False) -> EventRecordingRecord | None:
        query = select(EventRecordingRecord).where(EventRecordingRecord.event_id == event_id)
        if for_update:
            query = query.with_for_update()
        return db.scalar(query)

    def _recording_sessions(db: Session, recording_id: str) -> list[RecordingSessionRecord]:
        return list(db.scalars(
            select(RecordingSessionRecord)
            .where(RecordingSessionRecord.recording_id == recording_id)
            .order_by(RecordingSessionRecord.sort_order.asc(), RecordingSessionRecord.created_at.asc())
        ).all())

    def _recording_resources(db: Session, event_id: str) -> list[EventResourceRecord]:
        return list(db.scalars(
            select(EventResourceRecord)
            .where(EventResourceRecord.event_id == event_id, EventResourceRecord.status != "removed")
            .order_by(EventResourceRecord.sort_order.asc(), EventResourceRecord.created_at.asc())
        ).all())

    def _recording_viewer(
        db: Session, recording: EventRecordingRecord | None, *, account: AccountIdentity | None,
        staff: bool, participation: interaction_mod.Participation | None, now: datetime,
    ) -> recordings_mod.Viewer:
        account_id = account.account_id if account is not None else None
        access = recordings_mod.access_for(db, recording.id, account_id) if recording is not None else None
        open_order = recordings_mod.open_order_for(db, recording.id, account_id) if recording is not None else None
        if open_order is not None and recordings_mod.expire_open_order(open_order, now):
            db.commit()
            open_order = None
        previous = (
            recordings_mod.latest_closed_order_for(db, recording.id, account_id)
            if recording is not None and open_order is None else None
        )
        return recordings_mod.Viewer(
            signed_in=account is not None, staff=staff, account_id=account_id, participation=participation,
            access=access, access_state=recordings_mod.access_state(access, now),
            open_order=open_order, previous_order=previous,
        )

    def _purchased_state(recording: EventRecordingRecord | None, viewer: recordings_mod.Viewer) -> tuple[bool, str]:
        """``(allowed, reason)`` for ``access='purchased'`` resources, decided by the product layer."""
        if recording is None:
            return False, "purchase_required"
        if recording.status not in recordings_mod.SHELF_STATUSES and not viewer.staff and viewer.access_state != "active":
            return False, "purchase_required"
        return recordings_mod.has_content_access(recording, viewer)

    def _recording_public_payload(
        db: Session, request: Request, *, event_id: str, public_event: dict[str, Any] | None,
        account: AccountIdentity | None, staff: bool, now: datetime,
    ) -> dict[str, Any] | None:
        """The ``recording`` block of the public event page (``None`` when there is no shelf product)."""
        recording = _recording_for_event(db, event_id)
        if recording is None:
            return None
        participation = _interaction_participation(db, account.account_id, event_id) if account is not None else None
        viewer = _recording_viewer(db, recording, account=account, staff=staff, participation=participation, now=now)
        allowed, reason = recordings_mod.has_content_access(recording, viewer)
        keeps_archived = recording.status == "archived" and allowed  # phase 9.3: attendee courtesy survives archiving too
        if recording.status not in recordings_mod.SHELF_STATUSES and not staff and viewer.access_state != "active" and not keeps_archived:
            # Off the shelf (draft/ready/archived): invisible to the public — but a holder of a still-active
            # access (purchased/granted/free, or a checked-in attendee of a courtesy product) keeps the page and
            # the files, exactly like ``_purchased_state`` keeps the downloads (archiving stops listing and
            # sales; it never silently strips an access).
            return None
        sessions = _recording_sessions(db, recording.id)
        resources = _recording_resources(db, event_id)
        by_session: dict[str, list[EventResourceRecord]] = {}
        for row in resources:
            if row.session_id:
                by_session.setdefault(row.session_id, []).append(row)
        session_views: list[dict[str, Any]] = []
        total_minutes = 0
        for session in sessions:
            if session.status != "published" and not staff:
                continue
            rows = [
                recordings_mod.session_resource_view(
                    row, recording=recording, session=session, allowed=allowed, reason=reason, now=now, staff=staff,
                )
                for row in by_session.get(session.id, [])
                if staff or interaction_mod.resource_is_live(row, now)
            ]
            session_views.append(recordings_mod.session_public_view(session, rows, staff=staff))
            if session.status == "published":
                total_minutes += int(session.duration_minutes or 0)
        commerce = recordings_mod.commerce_for(
            recording, recordings_mod.purchase_form_for(db, recording.id), wallet_ready=_wallet_ready(db, request),
        )
        cta = recordings_mod.viewer_cta(recording, viewer, wallet_ready=_wallet_ready(db, request), commerce=commerce)
        return recordings_mod.recording_public_view(
            recording, sessions=session_views, viewer=viewer, cta=cta, total_minutes=total_minutes, staff=staff,
            commerce=commerce,
        )

    def _recording_cards(db: Session, event_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Shelf summaries keyed by event id for the public snapshot (published/paused only)."""
        if not event_ids:
            return {}
        rows = db.scalars(
            select(EventRecordingRecord).where(
                EventRecordingRecord.event_id.in_(event_ids),
                EventRecordingRecord.status.in_(recordings_mod.SHELF_STATUSES),
            )
        ).all()
        stats = recordings_mod.session_stats(db, [row.id for row in rows])
        forms = recordings_mod.purchase_forms_for(db, [row.id for row in rows])
        out: dict[str, dict[str, Any]] = {}
        for row in rows:
            count, minutes = stats.get(row.id, (0, 0))
            commerce = recordings_mod.commerce_for(row, forms.get(row.id), wallet_ready=False)
            out[row.event_id] = recordings_mod.recording_card_view(
                row, session_count=count, total_minutes=minutes, commerce=commerce,
            )
        return out

    def _recording_event_title(db: Session, event_id: str) -> str:
        return _interaction_event_titles(db, {event_id}).get(event_id, "")

    def _queue_recording_access_notification(
        db: Session, access: RecordingAccessRecord, recording: EventRecordingRecord, *, kind_label: str,
        reactivated: bool = False, now: datetime | None = None,
    ) -> UserNotificationRecord:
        """One outbox row per access *activation*; web-only accounts get an honest ``failed`` row.

        Idempotent: a retried webhook / double-submitted review (row already active) maps to the
        key of the original activation and adds nothing. A real re-grant after a revocation or
        expiry (``reactivated``) is a new activation and gets its own row.
        """
        bale_ids = verified_bale_ids_for_account(db, access.account_id)
        target = bale_ids[0] if bale_ids else ""
        title = recording.title or _recording_event_title(db, recording.event_id) or "محتوای ضبط‌شده"
        expiry = interaction_mod.iso(access.expires_at)
        body = f"دسترسی شما به «{title}» فعال شد ({kind_label})."
        if expiry:
            body += f"\nاعتبار دسترسی تا: {event_time.to_local_input(expiry)}"
        body += "\nبرای مشاهده به بخش «محتوای من» در حساب کاربری بروید."
        stamp = (now or _utc_now()).strftime("%Y%m%dT%H%M") if reactivated else "first"
        key = notifications_mod.dedupe_key("recording_access", access.id, access.source, access.order_id or "-", stamp)
        item, _created = notifications_mod.queue(
            db, account_id=access.account_id, kind=recordings_mod.NOTIFICATION_KIND,
            title="دسترسی به محتوای ضبط‌شده", body=body, key=key, bale_ids=bale_ids,
            link=notifications_mod.event_link(recording.event_id, anchor="recording"),
        )
        return item

    def _notify_content_published(
        db: Session, recording: EventRecordingRecord, *, what: str, target_id: str, title_text: str, now: datetime,
    ) -> int:
        """Phase 9.5: thin wrapper over the module-level fan-out shared with the scheduler."""
        return scheduled_publish_mod.notify_content_published(
            db, recording, what=what, target_id=target_id, title_text=title_text, now=now,
            bale_ids_for=lambda account_id: verified_bale_ids_for_account(db, account_id),
            event_title_for=lambda event_id: _recording_event_title(db, event_id),
            payment_approved=_response_payment_approved,
        )

    def _queue_recording_order_notification(
        db: Session, order: RecordingOrderRecord, *, title: str, body: str,
    ) -> UserNotificationRecord:
        """Decision outbox row (reject/refund): same honest delivery states as the access notification."""
        bale_ids = verified_bale_ids_for_account(db, order.account_id)
        product = db.get(EventRecordingRecord, order.recording_id)
        item, _created = notifications_mod.queue(
            db, account_id=order.account_id, kind=recordings_mod.ORDER_NOTIFICATION_KIND, title=title, body=body,
            key=notifications_mod.dedupe_key("recording_order", order.id, order.status, order.refund_reference or "-"),
            bale_ids=bale_ids, link=notifications_mod.event_link(product.event_id) if product else notifications_mod.account_link("orders"),
        )
        return item

    def _grant_recording_access(
        db: Session, recording: EventRecordingRecord, account_id: str, *, source: str, now: datetime,
        order: RecordingOrderRecord | None = None, actor: tuple[str, str] = ("", ""), reason: str = "",
        access_days: int | None = None,
    ) -> tuple[RecordingAccessRecord, bool]:
        """Idempotent: one row per (product, account); re-activates revoked/expired rows."""
        row = recordings_mod.access_for(db, recording.id, account_id)
        created = row is None
        reactivated = row is not None and recordings_mod.access_state(row, now) != "active"
        expires = recordings_mod.access_expiry(recording, now, days=access_days)
        if row is None:
            row = RecordingAccessRecord(
                id=interaction_mod.new_id(), recording_id=recording.id, account_id=account_id,
                source=source, status="active", order_id=order.id if order else None, expires_at=expires,
                granted_by_kind=actor[0], granted_by_id=actor[1], reason=reason,
            )
            db.add(row)
        else:
            row.source = source
            row.status = "active"
            row.order_id = order.id if order else row.order_id
            row.expires_at = expires
            row.granted_by_kind, row.granted_by_id = actor
            row.reason = reason
            row.revoked_at = None
            row.revoked_by_kind = ""
            row.revoked_by_id = ""
            row.revoke_reason = ""
        db.flush()
        label = {"purchase": "خرید", "free": "دسترسی رایگان", "granted": "اعطای دستی"}.get(source, source)
        _queue_recording_access_notification(db, row, recording, kind_label=label, reactivated=reactivated, now=now)
        return row, created

    # ── Phase 9.1: purchase-form finalization (single path for card / wallet / free) ──

    def _purchase_recording_for_form(
        db: Session, form: FormRecord, *, for_update: bool = False,
    ) -> EventRecordingRecord | None:
        if not _form_is_purchase(form) or not form.recording_id:
            return None
        query = select(EventRecordingRecord).where(EventRecordingRecord.id == form.recording_id)
        if for_update:
            query = query.with_for_update()
        return db.scalar(query)

    def _purchase_ledger_for_response(db: Session, response_id: str, *, for_update: bool = False) -> RecordingOrderRecord | None:
        query = select(RecordingOrderRecord).where(RecordingOrderRecord.form_response_id == response_id)
        if for_update:
            query = query.with_for_update()
        return db.scalar(query)

    def _upsert_purchase_ledger(
        db: Session, *, recording: EventRecordingRecord, account_id: str, response: FormResponseRecord,
        payment: FormPaymentRecord, now: datetime,
    ) -> RecordingOrderRecord:
        """One internal ledger row per purchase-form response; amounts copied from the form payment."""
        order = _purchase_ledger_for_response(db, response.id, for_update=True)
        status_map = {
            "awaiting_receipt": "awaiting_receipt", "receipt_submitted": "receipt_submitted", "pending": "pending",
            "paid": "paid", "paid_manual": "paid_manual", "rejected": "rejected", "cancelled": "cancelled",
            "paid_review": "needs_review", "expired": "expired", "refunded": "refunded",
        }
        if order is None:
            order = RecordingOrderRecord(
                id=interaction_mod.new_id(), recording_id=recording.id, account_id=account_id, method=payment.method,
                amount=int(payment.amount), currency=payment.currency,
                idempotency_key="form-purchase:" + response.id, form_response_id=response.id, form_payment_id=payment.id,
            )
            db.add(order)
        order.method = payment.method
        order.amount = int(payment.amount)
        order.currency = payment.currency
        order.form_payment_id = payment.id
        order.status = status_map.get(payment.status, "needs_review")
        order.invoice_payload = payment.invoice_payload
        order.payer_bale_user_id = payment.payer_bale_user_id
        order.expires_at = payment.expires_at if payment.method == "bale_wallet" else None
        order.updated_at = now
        db.flush()
        return order

    def _finalize_purchase(
        db: Session, *, form: FormRecord, response: FormResponseRecord, payment: FormPaymentRecord | None,
        account_id: str, now: datetime, actor: tuple[str, str], reason: str,
    ) -> tuple[RecordingOrderRecord | None, RecordingAccessRecord]:
        """Grant access for one accepted purchase-form response (idempotent).

        * free form (no payment): access ``source='free'`` directly, no ledger row,
          no fake transaction;
        * paid form: the ledger row mirrors the already-verified form payment
          (``paid`` from the webhook inquiry, ``paid_manual`` from the inbox) and the
          access row points at it (``source='purchase'``).
        Never touches ``form_responses`` ticket/check-in columns.
        """
        recording = _purchase_recording_for_form(db, form, for_update=True)
        if recording is None:
            raise HTTPException(409, {"code": "recording_not_found"})
        order: RecordingOrderRecord | None = None
        if payment is None:
            access, _created = _grant_recording_access(
                db, recording, account_id, source="free", now=now, actor=actor, reason=reason,
            )
            return None, access
        if payment.status not in {"paid", "paid_manual"}:
            raise HTTPException(409, {"code": "payment_not_settled", "status": payment.status})
        order = _upsert_purchase_ledger(
            db, recording=recording, account_id=account_id, response=response, payment=payment, now=now,
        )
        order.transaction_id = payment.transaction_id
        order.provider_charge_id = payment.provider_charge_id
        order.paid_at = order.paid_at or now
        if payment.status == "paid_manual":
            order.decided_at = now
            order.decided_by_kind, order.decided_by_id = actor
            order.decision_reason = reason
        access, _created = _grant_recording_access(
            db, recording, account_id, source="purchase", now=now, order=order, actor=actor, reason=reason,
        )
        return order, access

    def _reject_purchase(
        db: Session, *, response: FormResponseRecord, reason: str, now: datetime, actor: tuple[str, str],
    ) -> RecordingOrderRecord | None:
        """Close the ledger row of a rejected purchase receipt; the response itself is removed by the caller."""
        order = _purchase_ledger_for_response(db, response.id, for_update=True)
        if order is None:
            return None
        order.status = "rejected"
        order.decided_at = now
        order.decided_by_kind, order.decided_by_id = actor
        order.decision_reason = reason
        order.form_response_id = None
        order.updated_at = now
        db.flush()
        return order

    def _purchase_state_view(db: Session, form: FormRecord, account_id: str | None, now: datetime) -> dict[str, Any] | None:
        """What form.html shows after a purchase submit: product, access state, ledger status."""
        recording = _purchase_recording_for_form(db, form)
        if recording is None:
            return None
        access = recordings_mod.access_for(db, recording.id, account_id) if account_id else None
        return {
            "recording_id": recording.id,
            "event_id": recording.event_id,
            "title": recording.title,
            "access_state": recordings_mod.access_state(access, now),
        }

    def _require_purchase_account(request: Request, db: Session, form: FormRecord) -> AccountIdentity | None:
        """Purchase forms need a signed-in account because the access right belongs to one."""
        identity = public_write_identity(request, db)
        if _form_is_purchase(form) and identity is None:
            raise HTTPException(401, detail={"code": "account_required", "purpose": "recording_access"})
        return identity

    def _reject_duplicate_purchase_order(
        db: Session, recording: EventRecordingRecord, account_id: str | None, *, own_response_id: str | None = None,
    ) -> None:
        """One open purchase order per account and product (server-side, independent of the browser cookie).

        A second device/cookie of the same signed-in account must resume the pending order
        (``pending``/``awaiting_receipt``/``receipt_submitted``/``needs_review``) instead of
        creating a parallel response + ledger row that staff would have to reconcile by hand.
        The caller's own response (resubmit of the same draft) is never counted as a duplicate.
        """
        if not account_id:
            return
        open_order = recordings_mod.open_order_for(db, recording.id, account_id)
        if open_order is None or (own_response_id and open_order.form_response_id == own_response_id):
            return
        raise HTTPException(409, detail={
            "code": "purchase_order_pending",
            "recording_id": recording.id,
            "order_status": open_order.status,
            "response_id": open_order.form_response_id,
            "message": "برای این محصول یک سفارش باز با همین حساب ثبت شده است؛ همان سفارش را ادامه دهید یا منتظر بازبینی بمانید.",
        })

    def _public_purchase_header(db: Session, request: Request, form: FormRecord) -> dict[str, Any]:
        """The purchase header of form.html: product, server price and the caller's real access state."""
        identity = account_identity_from_request(request, db)
        purchase = _purchase_state_view(db, form, identity.account_id if identity else None, _utc_now()) or {}
        settings_value = form.settings if isinstance(form.settings, dict) else {}
        purchase.update({
            "signed_in": identity is not None,
            "price": purchase_form_price(settings_value),
            "currency": "IRR",
            "selection": purchase_form_selection(settings_value),
        })
        return purchase

    def _recording_admin_counts(db: Session, recording_id: str) -> dict[str, int]:
        now = _utc_now()
        rows = db.execute(
            select(RecordingOrderRecord.status, func.count(RecordingOrderRecord.id))
            .where(RecordingOrderRecord.recording_id == recording_id)
            .group_by(RecordingOrderRecord.status)
        ).all()
        by_status = {str(status): int(count) for status, count in rows}
        access_rows = db.scalars(
            select(RecordingAccessRecord).where(RecordingAccessRecord.recording_id == recording_id)
        ).all()
        return {
            "orders_open": sum(by_status.get(s, 0) for s in recordings_mod.OPEN_ORDER_STATUSES),
            "orders_review": sum(by_status.get(s, 0) for s in recordings_mod.REVIEWABLE_ORDER_STATUSES),
            "orders_paid": sum(by_status.get(s, 0) for s in recordings_mod.PAID_ORDER_STATUSES),
            "orders_refunded": by_status.get("refunded", 0),
            "access_active": sum(1 for row in access_rows if recordings_mod.access_state(row, now) == "active"),
            "access_total": len(access_rows),
        }

    def _recording_admin_payload(
        db: Session, request: Request, recording: EventRecordingRecord, *, event_id: str,
    ) -> dict[str, Any]:
        sessions = _recording_sessions(db, recording.id)
        resources = _recording_resources(db, event_id)
        per_session: dict[str, int] = {}
        for row in resources:
            if row.session_id:
                per_session[row.session_id] = per_session.get(row.session_id, 0) + 1
        public_event, _stored = _interaction_event(db, event_id)
        commerce = recordings_mod.commerce_for(
            recording, recordings_mod.purchase_form_for(db, recording.id), wallet_ready=_wallet_ready(db, request),
        )
        blockers = recordings_mod.publish_blockers(
            recording, public_event, sessions, resources, now=_utc_now(), wallet_ready=_wallet_ready(db, request),
            commerce=commerce, file_ready=lambda row: _resource_has_bytes(request, row),
        )
        return recordings_mod.recording_admin_view(
            recording,
            sessions=[recordings_mod.session_admin_view(s, resource_count=per_session.get(s.id, 0)) for s in sessions],
            blockers=blockers, counts=_recording_admin_counts(db, recording.id),
            event_title=_recording_event_title(db, event_id), commerce=commerce,
        )

    # ── عمومی ──

    @app.get("/api/public/recordings")
    def public_recordings_shelf(
        response: Response,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=100_000),
        db: Session = Depends(get_db),
    ):
        """Published/paused recorded products of published events (store shelf)."""
        response.headers["Cache-Control"] = "private, no-store"
        record = db.get(SiteContentRecord, "public")
        events = {
            str(row.get("id")): row
            for row in (public_site_content({"events": _content_rows(record, "events")}).get("events") or [])
            if isinstance(row, dict) and row.get("id")
        }
        rows = db.scalars(
            select(EventRecordingRecord)
            .where(EventRecordingRecord.status.in_(recordings_mod.SHELF_STATUSES))
            .order_by(EventRecordingRecord.published_at.desc().nullslast(), EventRecordingRecord.updated_at.desc())
        ).all()
        visible = [row for row in rows if row.event_id in events]
        stats = recordings_mod.session_stats(db, [row.id for row in visible])
        forms = recordings_mod.purchase_forms_for(db, [row.id for row in visible])
        items: list[dict[str, Any]] = []
        for row in visible[offset:offset + limit]:
            count, minutes = stats.get(row.id, (0, 0))
            card = recordings_mod.recording_card_view(
                row, session_count=count, total_minutes=minutes,
                commerce=recordings_mod.commerce_for(row, forms.get(row.id), wallet_ready=False),
            )
            event = events[row.event_id]
            card["event"] = {
                "id": row.event_id, "t": event.get("t"), "kind": event.get("kind"), "when": event.get("when"),
                "on": event.get("on"), "img": event.get("img"), "instructor": event.get("by") or event.get("instructor") or "",
                "cat": event.get("cat") or "",
            }
            items.append(card)
        return {
            "source": "shared_server_database", "server_time": event_time.to_iso(_utc_now()),
            "items": items, "total": len(visible), "limit": limit, "offset": offset,
        }

    @app.get("/api/public/events/{event_id}/recording")
    def public_event_recording(event_id: str, request: Request, response: Response, db: Session = Depends(get_db)):
        """The recorded product of one event for the current viewer, with the single server-decided CTA."""
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Cookie"
        try:
            event_id = interaction_mod.parse_event_id(event_id)
        except interaction_mod.InteractionError as error:
            raise _interaction_error(error) from None
        staff = _interaction_staff(request, db)
        account = staff if isinstance(staff, AccountIdentity) else (
            account_identity_from_request(request, db) if staff is None else None
        )
        public_event, stored = _interaction_event(db, event_id)
        if stored is None or (public_event is None and staff is None):
            raise HTTPException(404, "event_not_found")
        now = _utc_now()
        payload = _recording_public_payload(
            db, request, event_id=event_id, public_event=public_event, account=account, staff=staff is not None, now=now,
        )
        if payload is None:
            raise HTTPException(404, "recording_not_found")
        source = public_event or {}
        return {
            "source": "shared_server_database",
            "server_time": event_time.to_iso(now),
            "event": {
                "id": event_id,
                "title": str(source.get("t") or stored.get("t") or "")[:240],
                "published": public_event is not None,
                "held": recordings_mod.event_held(source, now) if public_event else False,
                "lifecycle": str(source.get("lifecycle") or stored.get("lifecycle") or "scheduled"),
            },
            "recording": payload,
        }

    # ── حساب کاربری: دریافت رایگان، سفارش، رسید، کتابخانه ──

    def _account_recording(db: Session, recording_id: str, *, for_update: bool = False) -> EventRecordingRecord:
        parsed = interaction_mod.parse_row_id(recording_id)
        if parsed is None:
            raise HTTPException(404, "recording_not_found")
        query = select(EventRecordingRecord).where(EventRecordingRecord.id == parsed)
        if for_update:
            query = query.with_for_update()
        record = db.scalar(query)
        if record is None:
            raise HTTPException(404, "recording_not_found")
        public_event, _stored = _interaction_event(db, record.event_id)
        if public_event is None:
            raise HTTPException(404, "recording_not_found")
        return record

    def _account_order(db: Session, identity: AccountIdentity, order_id: str, *, for_update: bool = False) -> RecordingOrderRecord:
        parsed = interaction_mod.parse_row_id(order_id)
        if parsed is None:
            raise HTTPException(404, "order_not_found")
        query = select(RecordingOrderRecord).where(RecordingOrderRecord.id == parsed)
        if for_update:
            query = query.with_for_update()
        record = db.scalar(query)
        # Another account's order is a 404, never a 403 (no existence leak).
        if record is None or record.account_id != identity.account_id:
            raise HTTPException(404, "order_not_found")
        return record

    @app.post("/api/account/recordings/{recording_id}/claim", status_code=201)
    def account_claim_free_recording(
        recording_id: str,
        request: Request,
        identity: AccountIdentity = Depends(require_account_write),
        db: Session = Depends(get_db),
    ):
        """Free product → access row directly; no order, no fake transaction."""
        recording = _account_recording(db, recording_id, for_update=True)
        if recording.status != "published":
            raise HTTPException(409, {"code": "recording_not_on_sale", "status": recording.status})
        commerce = recordings_mod.commerce_for(
            recording, recordings_mod.purchase_form_for(db, recording.id), wallet_ready=False,
        )
        if not commerce.free:
            raise HTTPException(409, {"code": "recording_not_free"})
        now = _utc_now()
        existing = recordings_mod.access_for(db, recording.id, identity.account_id)
        if existing is not None and recordings_mod.access_state(existing, now) == "active":
            return {"claimed": True, "created": False, "access": recordings_mod.access_view(existing, now)}
        if existing is not None and existing.status == "revoked":
            raise HTTPException(409, {"code": "access_revoked"})
        cfg: Settings = request.app.state.settings
        _enforce_owner_upload_limit(request, db, cfg, identity, limit=30, scope="recording-claim")
        row, created = _grant_recording_access(
            db, recording, identity.account_id, source="free", now=now, actor=("account", identity.account_id),
            reason="free_claim",
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing_row = recordings_mod.access_for(db, recording.id, identity.account_id)
            if existing_row is None:
                raise HTTPException(409, {"code": "access_conflict"}) from None
            row, created = existing_row, False
        return {"claimed": True, "created": created, "access": recordings_mod.access_view(row, now)}

    async def _ensure_bale_payment_webhook(cfg: Settings) -> None:
        """Make sure Bale posts payment updates to our dedicated webhook path (idempotent)."""
        webhook_info = await asyncio.to_thread(call_bale_payment_api, cfg, "getWebhookInfo", {})
        webhook_result = webhook_info.get("result")
        configured_webhook = webhook_result.get("url", "") if isinstance(webhook_result, dict) else ""
        registered_webhook_url = _form_payment_registered_webhook_url(cfg)
        current_webhook_url = configured_webhook.rstrip("/")
        base_webhook_url = cfg.form_payment_webhook_url.rstrip("/")
        if current_webhook_url == registered_webhook_url:
            return
        if current_webhook_url not in {"", base_webhook_url}:
            raise HTTPException(503, detail={"code": "bale_payment_webhook_conflict"})
        await asyncio.to_thread(call_bale_payment_api, cfg, "setWebhook", {"url": registered_webhook_url})
        verified_webhook_info = await asyncio.to_thread(call_bale_payment_api, cfg, "getWebhookInfo", {})
        verified_result = verified_webhook_info.get("result")
        verified_url = verified_result.get("url", "") if isinstance(verified_result, dict) else ""
        if verified_url.rstrip("/") != registered_webhook_url:
            raise HTTPException(503, detail={"code": "bale_payment_webhook_registration_failed"})

    # Phase 9.1: orders are no longer opened here. A purchase starts from the product's
    # purchase form (form.html?fid=…); the ledger row is created by the server from that
    # form's response/payment. The retired routes answer 410 so old clients fail loudly.
    @app.post("/api/account/recordings/{recording_id}/orders")
    def account_create_recording_order_retired(
        recording_id: str, identity: AccountIdentity = Depends(require_account_write), db: Session = Depends(get_db),
    ):
        recording = _account_recording(db, recording_id)
        form = recordings_mod.purchase_form_for(db, recording.id)
        raise HTTPException(410, {
            "code": "use_purchase_form",
            "form_id": form.id if form is not None and form.status == "published" else None,
        })

    @app.get("/api/account/recording-orders")
    def account_list_recording_orders(
        response: Response,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=100_000),
        identity: AccountIdentity = Depends(require_account),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Cookie"
        now = _utc_now()
        rows = db.scalars(
            select(RecordingOrderRecord)
            .where(RecordingOrderRecord.account_id == identity.account_id)
            .order_by(RecordingOrderRecord.created_at.desc(), RecordingOrderRecord.id.desc())
        ).all()
        changed = False
        for row in rows:
            changed = recordings_mod.expire_open_order(row, now) or changed
        if changed:
            db.commit()
        products = {
            row.id: row for row in db.scalars(
                select(EventRecordingRecord).where(EventRecordingRecord.id.in_({r.recording_id for r in rows} or {""}))
            ).all()
        }
        titles = _interaction_event_titles(db, {p.event_id for p in products.values()})
        purchase_forms = recordings_mod.purchase_forms_for(db, list(products))
        items = []
        for row in rows[offset:offset + limit]:
            view = recordings_mod.order_account_view(row, products.get(row.recording_id))
            product = products.get(row.recording_id)
            view["event_title"] = titles.get(product.event_id, "") if product else ""
            purchase_form = purchase_forms.get(row.recording_id)
            # Phase 9.1: the account page continues/retries a purchase only through the builder's form.
            view["purchase_form_id"] = purchase_form.id if purchase_form is not None and purchase_form.status == "published" else None
            items.append(view)
        return {"source": "shared_server_database", "items": items, "total": len(rows), "limit": limit, "offset": offset}

    @app.get("/api/account/recording-orders/{order_id}")
    def account_get_recording_order(
        order_id: str, response: Response,
        identity: AccountIdentity = Depends(require_account), db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        order = _account_order(db, identity, order_id)
        if recordings_mod.expire_open_order(order, _utc_now()):
            db.commit()
        recording = db.get(EventRecordingRecord, order.recording_id)
        view = recordings_mod.order_account_view(order, recording)
        view["event_title"] = _recording_event_title(db, recording.event_id) if recording else ""
        purchase_form = recordings_mod.purchase_form_for(db, order.recording_id)
        view["purchase_form_id"] = purchase_form.id if purchase_form is not None and purchase_form.status == "published" else None
        return view

    @app.put("/api/account/recording-orders/{order_id}/receipt")
    def account_upload_recording_receipt_retired(
        order_id: str, identity: AccountIdentity = Depends(require_account_write), db: Session = Depends(get_db),
    ):
        order = _account_order(db, identity, order_id)
        recording = db.get(EventRecordingRecord, order.recording_id)
        form = recordings_mod.purchase_form_for(db, recording.id) if recording is not None else None
        raise HTTPException(410, {
            "code": "use_purchase_form",
            "form_id": form.id if form is not None and form.status == "published" else None,
        })

    @app.post("/api/account/recording-orders/{order_id}/cancel")
    def account_cancel_recording_order(
        order_id: str,
        identity: AccountIdentity = Depends(require_account_write),
        db: Session = Depends(get_db),
    ):
        """Only legacy (pre-9.1) open orders can be cancelled here; form-backed rows follow the form payment."""
        order = _account_order(db, identity, order_id, for_update=True)
        now = _utc_now()
        if order.form_response_id is not None or order.form_payment_id is not None:
            raise HTTPException(409, {"code": "order_follows_form_payment", "status": order.status})
        if order.status not in {"pending", "awaiting_receipt"}:
            raise HTTPException(409, {"code": "order_not_cancellable", "status": order.status})
        order.status = "cancelled"
        order.updated_at = now
        db.commit()
        db.refresh(order)
        return recordings_mod.order_account_view(order, db.get(EventRecordingRecord, order.recording_id))

    @app.get("/api/account/recordings")
    def account_recording_library(
        response: Response,
        identity: AccountIdentity = Depends(require_account),
        db: Session = Depends(get_db),
    ):
        """«محتوای من»: every access row of the account with its real state (active/expired/revoked)."""
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Cookie"
        now = _utc_now()
        rows = db.execute(
            select(RecordingAccessRecord, EventRecordingRecord)
            .join(EventRecordingRecord, EventRecordingRecord.id == RecordingAccessRecord.recording_id)
            .where(RecordingAccessRecord.account_id == identity.account_id)
            .order_by(RecordingAccessRecord.created_at.desc())
        ).all()
        # Phase 9.3: products opened to checked-in attendees (``attendee_access``) are part of the
        # member's library too — derived with the same server rule as the product page
        # (``has_content_access`` → ``attended``), never by creating an access row.
        checked_in_event_ids = {
            str(event_id) for (event_id,) in db.execute(
                select(FormRecord.event_id)
                .join(FormResponseRecord, FormResponseRecord.form_id == FormRecord.id)
                .join(FormResponseDraftRecord, FormResponseDraftRecord.id == FormResponseRecord.draft_id)
                .where(
                    account_form_record_scope(db, identity.account_id),
                    FormResponseRecord.added_by_response_id.is_(None),
                    FormResponseRecord.ticket_checked_in_at.is_not(None),
                    FormRecord.model == "registration",
                    FormRecord.purpose == "registration",
                    FormRecord.event_id.is_not(None),
                )
                .distinct()
            ).all()
            if event_id
        }
        active_purchased = {
            recording.id for access, recording in rows if recordings_mod.access_state(access, now) == "active"
        }
        courtesy = [
            recording for recording in recordings_mod.attendee_courtesy_candidates(
                db, event_ids=checked_in_event_ids, exclude_recording_ids=active_purchased,
            )
            if _interaction_participation(db, identity.account_id, recording.event_id).attended
        ]
        courtesy_ids = {recording.id for recording in courtesy}
        all_recordings = [recording for _access, recording in rows] + courtesy
        stats = recordings_mod.session_stats(db, [recording.id for recording in all_recordings])
        titles = _interaction_event_titles(db, {recording.event_id for recording in all_recordings})
        items = []
        for access, recording in rows:
            if recording.id in courtesy_ids:
                continue  # an expired/revoked purchase of an attendee: the page grants «attended», so does the library
            count, minutes = stats.get(recording.id, (0, 0))
            items.append(recordings_mod.library_item_view(
                access, recording, now=now, session_count=count, total_minutes=minutes,
                event_title=titles.get(recording.event_id, ""),
            ))
        for recording in courtesy:
            count, minutes = stats.get(recording.id, (0, 0))
            items.append(recordings_mod.courtesy_library_item_view(
                recording, session_count=count, total_minutes=minutes, event_title=titles.get(recording.event_id, ""),
            ))
        return {"source": "shared_server_database", "server_time": event_time.to_iso(now), "items": items, "total": len(items)}

    # Phase 9.1: the dedicated ``norac_`` wallet branch is gone; recorded-content wallet
    # payments are ordinary purchase-form payments (``nora_`` invoices) and are finalized
    # by ``_finalize_purchase`` inside the shared webhook transaction.

    # ── پنل: محصول، جلسات، وضعیت ──

    def _admin_recording_or_404(db: Session, event_id: str, *, for_update: bool = False) -> EventRecordingRecord:
        record = _recording_for_event(db, event_id, for_update=for_update)
        if record is None:
            raise HTTPException(404, "recording_not_found")
        return record

    @app.get("/api/admin/events/{event_id}/recording")
    def admin_get_event_recording(
        event_id: str, request: Request, response: Response,
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission(*_INTERACTION_READ_PERMS)),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        event_id = _admin_event_id(db, event_id)
        record = _recording_for_event(db, event_id)
        public_event, _stored = _interaction_event(db, event_id)
        now = _utc_now()
        base = {
            "source": "shared_server_database",
            "event_id": event_id,
            "event_held": bool(public_event) and recordings_mod.event_held(public_event or {}, now),
            "event_published": public_event is not None,
            "wallet_ready": _wallet_ready(db, request),
            "limits": {
                **_resource_limits(request),
                "max_price": recordings_mod.MAX_PRICE, "max_access_days": recordings_mod.MAX_ACCESS_DAYS,
                "max_sessions": recordings_mod.MAX_SESSIONS,
                # Files are served as stored (chunked, with HTTP Range); no CDN/DRM/transcoding exists.
                "streaming": "range_file" if _private_storage(request) is not None else "none",
            },
        }
        if record is None:
            return {**base, "recording": None}
        return {**base, "recording": _recording_admin_payload(db, request, record, event_id=event_id)}

    @app.put("/api/admin/events/{event_id}/recording")
    async def admin_upsert_event_recording(
        event_id: str, request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_RECORDING_EDIT_PERMS)),
        db: Session = Depends(get_db),
    ):
        """Create or edit the product fields (never the status)."""
        event_id = _admin_event_id(db, event_id)
        payload = await _read_json_object(request, 64_000)
        record = _recording_for_event(db, event_id, for_update=True)
        try:
            fields = recordings_mod.validate_recording_fields(payload, existing=record)
        except interaction_mod.InteractionError as error:
            raise _recording_error(error) from None
        actor_kind, actor_id = _interaction_actor(identity)
        expected = payload.get("expected_version")
        if record is None:
            record = EventRecordingRecord(
                id=interaction_mod.new_id(), event_id=event_id, status="draft", created_by_kind=actor_kind,
                created_by_id=actor_id, updated_by_kind=actor_kind, updated_by_id=actor_id,
                **{"faq": [], **fields},
            )
            db.add(record)
            record_audit(
                db, identity, "recording.create", target_type="event_recording", target_id=record.id,
                details={"event_id": event_id, "price": record.price},
            )
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(409, {"code": "recording_exists"}) from None
            db.refresh(record)
            return _recording_admin_payload(db, request, record, event_id=event_id)
        if expected is not None and (isinstance(expected, bool) or not isinstance(expected, int) or expected != record.version):
            raise HTTPException(409, {"code": "version_conflict", "version": record.version})
        purchase_form = recordings_mod.purchase_form_for(db, record.id)
        if purchase_form is not None:
            locked = recordings_mod.commercial_fields_changed(fields, record)
            if locked:
                # Price / card / wallet switch live in the purchase form once one is linked.
                raise HTTPException(409, {
                    "code": "commercial_settings_in_form", "fields": locked, "form_id": purchase_form.id,
                })
        if "price" in fields and fields["price"] != record.price:
            open_orders = int(db.scalar(
                select(func.count(RecordingOrderRecord.id)).where(
                    RecordingOrderRecord.recording_id == record.id,
                    RecordingOrderRecord.status.in_(recordings_mod.OPEN_ORDER_STATUSES),
                )
            ) or 0)
            if open_orders:
                raise HTTPException(409, {"code": "open_orders_block_price_change", "open_orders": open_orders})
        changed = sorted(key for key, value in fields.items() if getattr(record, key) != value)
        details: dict[str, Any] = {"event_id": event_id, "changed": ",".join(changed)[:200]}
        for key in ("price", "access_days", "attendee_access", "certificate_policy"):
            if key in changed:
                details[f"{key}_before"] = getattr(record, key)
                details[f"{key}_after"] = fields[key]
        if "payment_card" in changed:
            details["payment_card_changed"] = True
        for key, value in fields.items():
            setattr(record, key, value)
        if changed:
            record.version += 1
            record.updated_by_kind, record.updated_by_id = actor_kind, actor_id
            record_audit(db, identity, "recording.update", target_type="event_recording", target_id=record.id, details=details)
        db.commit()
        db.refresh(record)
        return _recording_admin_payload(db, request, record, event_id=event_id)

    @app.post("/api/admin/events/{event_id}/recording/status")
    async def admin_set_event_recording_status(
        event_id: str, request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_RECORDING_STATUS_PERMS)),
        db: Session = Depends(get_db),
    ):
        event_id = _admin_event_id(db, event_id)
        record = _admin_recording_or_404(db, event_id, for_update=True)
        payload = await _read_json_object(request, 4096)
        if set(payload) - {"status", "reason"}:
            raise HTTPException(400, "invalid_status_change")
        try:
            target = interaction_mod.choice(payload.get("status"), recordings_mod.STATUSES, field="status")
            reason = recordings_mod.validate_reason(
                payload.get("reason"), required=target in recordings_mod.REASON_REQUIRED_STATUSES,
            )
        except interaction_mod.InteractionError as error:
            raise _recording_error(error) from None
        if not recordings_mod.can_transition(record.status, target):
            raise HTTPException(409, {"code": "invalid_transition", "from": record.status, "to": target})
        now = _utc_now()
        if target == "published":
            public_event, _stored = _interaction_event(db, event_id)
            blockers = recordings_mod.publish_blockers(
                record, public_event, _recording_sessions(db, record.id), _recording_resources(db, event_id),
                now=now, wallet_ready=_wallet_ready(db, request),
                commerce=recordings_mod.commerce_for(
                    record, recordings_mod.purchase_form_for(db, record.id), wallet_ready=_wallet_ready(db, request),
                ),
                file_ready=lambda row: _resource_has_bytes(request, row),
            )
            if blockers:
                raise HTTPException(409, {"code": "publish_blocked", "blockers": blockers})
            if record.published_at is None:
                record.published_at = now
        before = record.status
        record.status = target
        record.status_reason = reason
        record.version += 1
        record.updated_by_kind, record.updated_by_id = _interaction_actor(identity)
        record_audit(
            db, identity, "recording.status", target_type="event_recording", target_id=record.id,
            details={"event_id": event_id, "status_before": before, "status_after": target, "reason": reason},
        )
        db.commit()
        db.refresh(record)
        return _recording_admin_payload(db, request, record, event_id=event_id)

    def _admin_session(db: Session, recording: EventRecordingRecord, session_id: str) -> RecordingSessionRecord:
        parsed = interaction_mod.parse_row_id(session_id)
        record = db.get(RecordingSessionRecord, parsed) if parsed else None
        if record is None or record.recording_id != recording.id:
            raise HTTPException(404, "session_not_found")
        return record

    @app.post("/api/admin/events/{event_id}/recording/sessions", status_code=201)
    async def admin_create_recording_session(
        event_id: str, request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_RECORDING_EDIT_PERMS)),
        db: Session = Depends(get_db),
    ):
        event_id = _admin_event_id(db, event_id)
        recording = _admin_recording_or_404(db, event_id)
        payload = await _read_json_object(request, 16_384)
        try:
            fields = recordings_mod.validate_session_fields(payload, existing=None)
        except interaction_mod.InteractionError as error:
            raise _recording_error(error) from None
        count = int(db.scalar(
            select(func.count(RecordingSessionRecord.id)).where(RecordingSessionRecord.recording_id == recording.id)
        ) or 0)
        if count >= recordings_mod.MAX_SESSIONS:
            raise HTTPException(409, {"code": "too_many_sessions", "limit": recordings_mod.MAX_SESSIONS})
        if "sort_order" not in fields:
            fields["sort_order"] = count + 1
        session = RecordingSessionRecord(id=interaction_mod.new_id(), recording_id=recording.id, **fields)
        db.add(session)
        record_audit(
            db, identity, "recording.session.create", target_type="recording_session", target_id=session.id,
            details={"event_id": event_id, "recording_id": recording.id, "title": session.title[:120]},
        )
        db.commit()
        db.refresh(session)
        return recordings_mod.session_admin_view(session)

    @app.put("/api/admin/events/{event_id}/recording/sessions/{session_id}")
    async def admin_update_recording_session(
        event_id: str, session_id: str, request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_RECORDING_EDIT_PERMS)),
        db: Session = Depends(get_db),
    ):
        event_id = _admin_event_id(db, event_id)
        recording = _admin_recording_or_404(db, event_id)
        session = _admin_session(db, recording, session_id)
        payload = await _read_json_object(request, 16_384)
        try:
            fields = recordings_mod.validate_session_fields(payload, existing=session)
        except interaction_mod.InteractionError as error:
            raise _recording_error(error) from None
        before = {"status": session.status, "preview": session.preview}
        for key, value in fields.items():
            setattr(session, key, value)
        details: dict[str, Any] = {"event_id": event_id, "changed": ",".join(sorted(fields))[:200]}
        if before["status"] != session.status:
            details["status_before"], details["status_after"] = before["status"], session.status
        if before["preview"] != session.preview:
            details["preview_after"] = session.preview
        if before["status"] != "published" and session.status == "published":
            details["notified_holders"] = _notify_content_published(
                db, recording, what="session", target_id=session.id, title_text=session.title, now=_utc_now(),
            )
        record_audit(db, identity, "recording.session.update", target_type="recording_session", target_id=session.id, details=details)
        db.commit()
        db.refresh(session)
        resource_count = int(db.scalar(
            select(func.count(EventResourceRecord.id)).where(
                EventResourceRecord.session_id == session.id, EventResourceRecord.status != "removed",
            )
        ) or 0)
        return recordings_mod.session_admin_view(session, resource_count=resource_count)

    @app.delete("/api/admin/events/{event_id}/recording/sessions/{session_id}")
    def admin_delete_recording_session(
        event_id: str, session_id: str,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_RECORDING_EDIT_PERMS)),
        db: Session = Depends(get_db),
    ):
        event_id = _admin_event_id(db, event_id)
        recording = _admin_recording_or_404(db, event_id)
        session = _admin_session(db, recording, session_id)
        attached = int(db.scalar(
            select(func.count(EventResourceRecord.id)).where(
                EventResourceRecord.session_id == session.id, EventResourceRecord.status != "removed",
            )
        ) or 0)
        if attached:
            raise HTTPException(409, {"code": "session_has_resources", "resources": attached})
        record_audit(
            db, identity, "recording.session.delete", target_type="recording_session", target_id=session.id,
            details={"event_id": event_id, "title": session.title[:120]},
        )
        db.delete(session)
        db.commit()
        return {"deleted": True, "id": session.id}

    # ── پنل: سفارش‌ها و دسترسی‌ها ──

    def _admin_order(db: Session, order_id: str, *, for_update: bool = False) -> RecordingOrderRecord:
        parsed = interaction_mod.parse_row_id(order_id)
        if parsed is None:
            raise HTTPException(404, "order_not_found")
        query = select(RecordingOrderRecord).where(RecordingOrderRecord.id == parsed)
        if for_update:
            query = query.with_for_update()
        record = db.scalar(query)
        if record is None:
            raise HTTPException(404, "order_not_found")
        return record

    def _order_duplicates(db: Session, orders: Sequence[RecordingOrderRecord]) -> dict[str, int]:
        """Other orders of the same account for the same product (duplicate payments to review)."""
        if not orders:
            return {}
        keys = {(row.recording_id, row.account_id) for row in orders}
        counts: dict[tuple[str, str], int] = {}
        for recording_id, account_id, count in db.execute(
            select(RecordingOrderRecord.recording_id, RecordingOrderRecord.account_id, func.count(RecordingOrderRecord.id))
            .where(RecordingOrderRecord.recording_id.in_({k[0] for k in keys}))
            .group_by(RecordingOrderRecord.recording_id, RecordingOrderRecord.account_id)
        ).all():
            counts[(str(recording_id), str(account_id))] = int(count)
        return {row.id: max(0, counts.get((row.recording_id, row.account_id), 1) - 1) for row in orders}

    def _admin_order_rows(db: Session, orders: Sequence[RecordingOrderRecord]) -> list[dict[str, Any]]:
        products = {
            row.id: row for row in db.scalars(
                select(EventRecordingRecord).where(EventRecordingRecord.id.in_({o.recording_id for o in orders} or {""}))
            ).all()
        }
        titles = _interaction_event_titles(db, {p.event_id for p in products.values()})
        access_rows = {
            (row.recording_id, row.account_id): row for row in db.scalars(
                select(RecordingAccessRecord).where(RecordingAccessRecord.recording_id.in_({o.recording_id for o in orders} or {""}))
            ).all()
        }
        duplicates = _order_duplicates(db, orders)
        now = _utc_now()
        out = []
        for order in orders:
            product = products.get(order.recording_id)
            out.append(recordings_mod.order_admin_view(
                order, recording=product, event_title=titles.get(product.event_id, "") if product else "",
                access=access_rows.get((order.recording_id, order.account_id)), duplicates=duplicates.get(order.id, 0),
                account_label=_interaction_display_name(db, order.account_id), now=now,
            ))
        return out

    @app.get("/api/admin/recording-orders")
    def admin_list_recording_orders(
        request: Request,
        response: Response,
        status: str = Query(default=""),
        event_id: str = Query(default=""),
        q: str = Query(default="", max_length=120),
        format: str = Query(default=""),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0, le=100_000),
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission(*_RECORDING_ORDER_READ_PERMS)),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        filters: list[ColumnElement[bool]] = []
        if status:
            try:
                filters.append(RecordingOrderRecord.status.in_(recordings_mod.order_filters(status)))
            except interaction_mod.InteractionError as error:
                raise _recording_error(error) from None
        if event_id:
            try:
                parsed_event = interaction_mod.parse_event_id(event_id)
            except interaction_mod.InteractionError as error:
                raise _interaction_error(error) from None
            filters.append(RecordingOrderRecord.recording_id.in_(
                select(EventRecordingRecord.id).where(EventRecordingRecord.event_id == parsed_event)
            ))
        needle = q.strip()
        if needle:
            like = f"%{needle}%"
            filters.append(
                RecordingOrderRecord.id.like(like)
                | RecordingOrderRecord.account_id.like(like)
                | RecordingOrderRecord.transaction_id.like(like)
                | RecordingOrderRecord.recording_id.in_(select(EventRecordingRecord.id).where(EventRecordingRecord.title.like(like)))
            )
        now = _utc_now()
        query = select(RecordingOrderRecord).where(*filters).order_by(
            RecordingOrderRecord.created_at.desc(), RecordingOrderRecord.id.desc()
        )
        if format == "csv":
            # Export is finance-only: it carries account ids and transaction ids.
            require_any_permission(*_RECORDING_REFUND_PERMS)(request, db)
            rows = db.scalars(query.limit(5000)).all()
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["order_id", "event_id", "product", "account_id", "method", "status", "amount", "currency",
                             "created_at", "paid_at", "decided_at", "decision_reason", "refund_reference", "transaction_id"])
            for row in _admin_order_rows(db, rows):
                writer.writerow([row["id"], row["event_id"], row["product_title"], row["account_id"], row["method"], row["status"],
                                 row["amount"], row["currency"], row["created_at"], row["paid_at"], row["decided_at"],
                                 row["decision_reason"], row["refund_reference"], row["transaction_id"]])
            record_audit(db, identity, "recording.orders.export", target_type="recording_orders", details={"rows": len(rows), "status": status})
            db.commit()
            return Response(
                content="\ufeff" + buffer.getvalue(), media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="recording-orders.csv"', "Cache-Control": "private, no-store"},
            )
        total = int(db.scalar(select(func.count(RecordingOrderRecord.id)).where(*filters)) or 0)
        page = db.scalars(query.limit(limit).offset(offset)).all()
        changed = False
        for order in page:
            changed = recordings_mod.expire_open_order(order, now) or changed
        if changed:
            db.commit()
        return {"source": "shared_server_database", "items": _admin_order_rows(db, page), "total": total, "limit": limit, "offset": offset}

    @app.get("/api/admin/recording-orders/{order_id}")
    def admin_get_recording_order(
        order_id: str, response: Response,
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission(*_RECORDING_ORDER_READ_PERMS)),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        order = _admin_order(db, order_id)
        if recordings_mod.expire_open_order(order, _utc_now()):
            db.commit()
        view = _admin_order_rows(db, [order])[0]
        history = db.scalars(
            select(AdminAuditEventRecord)
            .where(AdminAuditEventRecord.target_type == "recording_order", AdminAuditEventRecord.target_id == order.id)
            .order_by(AdminAuditEventRecord.created_at.asc())
        ).all()
        view["history"] = [
            {
                "action": row.action, "actor_kind": row.actor_kind, "actor_role": row.actor_role, "outcome": row.outcome,
                "details": row.details, "at": _as_utc(row.created_at).isoformat(),
            }
            for row in history
        ]
        return view

    @app.get("/api/admin/recording-orders/{order_id}/receipt")
    def admin_get_recording_receipt(
        order_id: str,
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission(*_RECORDING_ORDER_READ_PERMS)),
        db: Session = Depends(get_db),
    ):
        order = _admin_order(db, order_id)
        if order.receipt_content is None:
            raise HTTPException(404, "receipt_not_found")
        headers = {
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Content-Disposition": interaction_mod.content_disposition(order.receipt_file_name or "receipt.bin").replace("attachment", "inline", 1),
        }
        return Response(content=order.receipt_content, media_type=order.receipt_content_type or "application/octet-stream", headers=headers)

    @app.post("/api/admin/recording-orders/{order_id}/decision")
    async def admin_decide_recording_order(
        order_id: str, request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_RECORDING_DECISION_PERMS)),
        db: Session = Depends(get_db),
    ):
        """Approve (→ paid_manual + access) or reject a submitted receipt / flagged order. Reason required."""
        order = _admin_order(db, order_id, for_update=True)
        payload = await _read_json_object(request, 4096)
        if set(payload) - {"decision", "reason"}:
            raise HTTPException(400, "invalid_decision")
        try:
            decision = interaction_mod.choice(payload.get("decision"), ("approve", "reject"), field="decision")
            reason = recordings_mod.validate_reason(payload.get("reason"), required=True)
        except interaction_mod.InteractionError as error:
            raise _recording_error(error) from None
        now = _utc_now()
        if recordings_mod.expire_open_order(order, now):
            db.commit()
        if order.status not in recordings_mod.REVIEWABLE_ORDER_STATUSES:
            raise HTTPException(409, {"code": "order_not_reviewable", "status": order.status})
        if order.form_response_id is not None or order.form_payment_id is not None:
            # Form-backed purchases are decided once, in the shared inbox (receipt_review task).
            response = db.get(FormResponseRecord, order.form_response_id) if order.form_response_id else None
            raise HTTPException(409, {
                "code": "decide_in_inbox",
                "task_id": response.receipt_review_task_id if response is not None else None,
            })
        recording = db.scalar(
            select(EventRecordingRecord).where(EventRecordingRecord.id == order.recording_id).with_for_update()
        )
        if recording is None:
            raise HTTPException(404, "recording_not_found")
        actor = _interaction_actor(identity)
        before = order.status
        order.decided_at = now
        order.decided_by_kind, order.decided_by_id = actor
        order.decision_reason = reason
        order.updated_at = now
        if decision == "approve":
            if order.amount != recording.price and order.method == "card_transfer":
                # Price changed since the order was opened: the reviewer must see the mismatch, never auto-approve.
                order.review_note = f"amount {order.amount} differs from current price {recording.price}"[:300]
            order.status = "paid_manual"
            order.paid_at = now
            _grant_recording_access(
                db, recording, order.account_id, source="purchase", now=now, order=order, actor=actor, reason=reason,
            )
            action = "recording.order.approve"
        else:
            order.status = "rejected"
            action = "recording.order.reject"
            product_title = recording.title or _recording_event_title(db, recording.event_id) or "محتوای ضبط‌شده"
            _queue_recording_order_notification(
                db, order, title="نتیجهٔ بررسی سفارش محتوای ضبط‌شده",
                body=(f"سفارش شما برای «{product_title}» تأیید نشد.\nدلیل: {reason}\n"
                      "در صورت نیاز می‌توانید از صفحهٔ همان رویداد سفارش تازه ثبت کنید؛ جزئیات در بخش «سفارش‌ها و پرداخت‌ها» حساب شماست."),
            )
        record_audit(
            db, identity, action, target_type="recording_order", target_id=order.id,
            details={"recording_id": recording.id, "account_id": order.account_id, "amount": order.amount,
                     "status_before": before, "status_after": order.status, "reason": reason},
        )
        db.commit()
        return _admin_order_rows(db, [order])[0]

    @app.post("/api/admin/recording-orders/{order_id}/refund")
    async def admin_refund_recording_order(
        order_id: str, request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_RECORDING_REFUND_PERMS)),
        db: Session = Depends(get_db),
    ):
        """Record a refund that was really executed (reference required) and revoke the access."""
        order = _admin_order(db, order_id, for_update=True)
        payload = await _read_json_object(request, 4096)
        if set(payload) - {"reference", "reason"}:
            raise HTTPException(400, "invalid_refund")
        try:
            reference = interaction_mod.clean_text(payload.get("reference"), 120, field="reference", required=True, minimum=3)
            reason = recordings_mod.validate_reason(payload.get("reason"), required=True)
        except interaction_mod.InteractionError as error:
            raise _recording_error(error) from None
        if order.status not in recordings_mod.PAID_ORDER_STATUSES:
            raise HTTPException(409, {"code": "order_not_refundable", "status": order.status})
        now = _utc_now()
        actor = _interaction_actor(identity)
        before = order.status
        order.status = "refunded"
        order.refund_reference = reference
        order.refunded_at = now
        order.decision_reason = reason
        order.decided_at = now
        order.decided_by_kind, order.decided_by_id = actor
        order.updated_at = now
        access = recordings_mod.access_for(db, order.recording_id, order.account_id)
        if access is not None and access.status != "revoked":
            access.status = "revoked"
            access.revoked_at = now
            access.revoked_by_kind, access.revoked_by_id = actor
            access.revoke_reason = f"refund:{reference}"[:300]
        refunded_product = db.get(EventRecordingRecord, order.recording_id)
        product_title = (
            (refunded_product.title or _recording_event_title(db, refunded_product.event_id)) if refunded_product else ""
        ) or "محتوای ضبط‌شده"
        _queue_recording_order_notification(
            db, order, title="بازپرداخت سفارش محتوای ضبط‌شده",
            body=(f"بازپرداخت سفارش شما برای «{product_title}» ثبت شد (شمارهٔ پیگیری: {reference}).\n"
                  f"دلیل: {reason}\nدسترسی این سفارش از این پس فعال نیست."),
        )
        record_audit(
            db, identity, "recording.order.refund", target_type="recording_order", target_id=order.id,
            details={"recording_id": order.recording_id, "account_id": order.account_id, "amount": order.amount,
                     "status_before": before, "reference": reference, "reason": reason, "access_revoked": access is not None},
        )
        db.commit()
        return _admin_order_rows(db, [order])[0]

    @app.get("/api/admin/events/{event_id}/recording/access")
    def admin_list_recording_access(
        event_id: str, response: Response,
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission(*_INTERACTION_READ_PERMS)),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        event_id = _admin_event_id(db, event_id)
        recording = _admin_recording_or_404(db, event_id)
        now = _utc_now()
        rows = db.scalars(
            select(RecordingAccessRecord)
            .where(RecordingAccessRecord.recording_id == recording.id)
            .order_by(RecordingAccessRecord.created_at.desc())
        ).all()
        return {
            "source": "shared_server_database", "recording_id": recording.id,
            "items": [recordings_mod.access_view(row, now, account_label=_interaction_display_name(db, row.account_id)) for row in rows],
            "total": len(rows),
        }

    @app.post("/api/admin/events/{event_id}/recording/access", status_code=201)
    async def admin_grant_recording_access(
        event_id: str, request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_RECORDING_STATUS_PERMS)),
        db: Session = Depends(get_db),
    ):
        """Manual grant: existing account id (server-verified), reason, optional scope in days."""
        event_id = _admin_event_id(db, event_id)
        recording = _admin_recording_or_404(db, event_id, for_update=True)
        payload = await _read_json_object(request, 4096)
        if set(payload) - {"account_id", "reason", "access_days"}:
            raise HTTPException(400, "invalid_grant")
        account_id = interaction_mod.parse_row_id(payload.get("account_id"))
        if account_id is None or db.get(AccountRecord, account_id) is None:
            raise HTTPException(404, "account_not_found")
        try:
            reason = recordings_mod.validate_reason(payload.get("reason"), required=True)
            days = payload.get("access_days")
            access_days = None
            if days not in (None, "", 0):
                if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= recordings_mod.MAX_ACCESS_DAYS:
                    raise interaction_mod.InteractionError("invalid_number", field="access_days")
                access_days = days
        except interaction_mod.InteractionError as error:
            raise _recording_error(error) from None
        now = _utc_now()
        row, created = _grant_recording_access(
            db, recording, account_id, source="granted", now=now, actor=_interaction_actor(identity), reason=reason,
            access_days=access_days,
        )
        record_audit(
            db, identity, "recording.access.grant", target_type="recording_access", target_id=row.id,
            details={"recording_id": recording.id, "account_id": account_id, "reason": reason,
                     "access_days": access_days if access_days is not None else (recording.access_days or 0), "created": created},
        )
        db.commit()
        db.refresh(row)
        return {"granted": True, "created": created, "access": recordings_mod.access_view(row, now)}

    @app.post("/api/admin/events/{event_id}/recording/access/{access_id}/revoke")
    async def admin_revoke_recording_access(
        event_id: str, access_id: str, request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write(*_RECORDING_STATUS_PERMS)),
        db: Session = Depends(get_db),
    ):
        event_id = _admin_event_id(db, event_id)
        recording = _admin_recording_or_404(db, event_id)
        parsed = interaction_mod.parse_row_id(access_id)
        row = db.get(RecordingAccessRecord, parsed) if parsed else None
        if row is None or row.recording_id != recording.id:
            raise HTTPException(404, "access_not_found")
        payload = await _read_json_object(request, 4096)
        if set(payload) - {"reason"}:
            raise HTTPException(400, "invalid_revoke")
        try:
            reason = recordings_mod.validate_reason(payload.get("reason"), required=True)
        except interaction_mod.InteractionError as error:
            raise _recording_error(error) from None
        now = _utc_now()
        if row.status != "revoked":
            row.status = "revoked"
            row.revoked_at = now
            row.revoked_by_kind, row.revoked_by_id = _interaction_actor(identity)
            row.revoke_reason = reason
            record_audit(
                db, identity, "recording.access.revoke", target_type="recording_access", target_id=row.id,
                details={"recording_id": recording.id, "account_id": row.account_id, "reason": reason},
            )
            db.commit()
            db.refresh(row)
        return recordings_mod.access_view(row, now)

    @app.get("/api/admin/recordings/summary")
    def admin_recordings_summary(
        response: Response,
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission(*_INTERACTION_READ_PERMS)),
        db: Session = Depends(get_db),
    ):
        """Real counts for the panel badges; zero when nothing needs action."""
        response.headers["Cache-Control"] = "private, no-store"
        by_status = {
            str(status): int(count) for status, count in db.execute(
                select(EventRecordingRecord.status, func.count(EventRecordingRecord.id)).group_by(EventRecordingRecord.status)
            ).all()
        }
        orders = {
            str(status): int(count) for status, count in db.execute(
                select(RecordingOrderRecord.status, func.count(RecordingOrderRecord.id)).group_by(RecordingOrderRecord.status)
            ).all()
        }
        now = _utc_now()
        active_access = sum(
            1 for row in db.scalars(select(RecordingAccessRecord).where(RecordingAccessRecord.status == "active")).all()
            if recordings_mod.access_state(row, now) == "active"
        )
        per_event: dict[str, dict[str, Any]] = {}
        for row in db.scalars(select(EventRecordingRecord)).all():
            per_event[row.event_id] = {"status": row.status, "price": row.price}
        for recording_id, event_id, count in db.execute(
            select(RecordingOrderRecord.recording_id, EventRecordingRecord.event_id, func.count(RecordingOrderRecord.id))
            .join(EventRecordingRecord, EventRecordingRecord.id == RecordingOrderRecord.recording_id)
            .where(RecordingOrderRecord.status.in_(recordings_mod.REVIEWABLE_ORDER_STATUSES))
            .group_by(RecordingOrderRecord.recording_id, EventRecordingRecord.event_id)
        ).all():
            per_event.setdefault(str(event_id), {})["orders_review"] = int(count)
        return {
            "source": "shared_server_database",
            "recordings": by_status,
            "orders_review": sum(orders.get(s, 0) for s in recordings_mod.REVIEWABLE_ORDER_STATUSES),
            "orders_open": sum(orders.get(s, 0) for s in recordings_mod.OPEN_ORDER_STATUSES),
            "orders_paid": sum(orders.get(s, 0) for s in recordings_mod.PAID_ORDER_STATUSES),
            "orders_refunded": orders.get("refunded", 0),
            "active_access": active_access,
            "per_event": per_event,
        }

    @app.get("/api/owner/data/status")
    def get_owner_data_status(
        request: Request,
        _identity: OwnerIdentity | AccountIdentity = Depends(require_permission("sys_backup")),
        db: Session = Depends(get_db),
    ):
        """وضعیت فقط-خواندنی پایگاه عملیاتی و staging؛ هیچ مسیر یا رمزی برنمی‌گردد."""
        cfg: Settings = request.app.state.settings
        store = _data_store(cfg)
        bind = db.get_bind()
        dialect = getattr(getattr(bind, "dialect", None), "name", "") or "unknown"
        try:
            schema_version = str(db.scalar(text("SELECT version_num FROM alembic_version")) or "")
        except SQLAlchemyError:
            schema_version = ""
        response = JSONResponse({
            "database": {"engine": dialect, "schema_version": schema_version},
            "staging": {
                "retention_hours": cfg.data_staging_retention_hours,
                "max_bytes": cfg.data_upload_max_bytes,
                "used_bytes": store.usage_bytes(),
                "outside_webroot": True,
            },
            "audit_tool_available": _audit_script(cfg).is_file(),
            "operational_writes": 0,
        })
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.get("/api/owner/data/uploads")
    def list_owner_data_uploads(
        request: Request,
        _identity: OwnerIdentity | AccountIdentity = Depends(require_permission("sys_backup")),
    ):
        cfg: Settings = request.app.state.settings
        store = _data_store(cfg)
        response = JSONResponse({
            "uploads": store.list_uploads(),
            "limits": {
                "max_bytes": cfg.data_upload_max_bytes,
                "retention_hours": cfg.data_staging_retention_hours,
            },
            "audit_tool_available": _audit_script(cfg).is_file(),
        })
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.post("/api/owner/data/uploads", status_code=201)
    async def create_owner_data_upload(
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_permission_write("sys_backup")),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = request.app.state.settings
        _enforce_owner_upload_limit(request, db, cfg, identity)
        declared = request.headers.get("x-file-name", "backup.db")
        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type not in (
            "", "application/octet-stream", "application/x-sqlite3", "application/vnd.sqlite3",
            "application/x-sqlite", "binary/octet-stream",
        ):
            raise HTTPException(415, "unsupported_backup_content_type")

        store = _data_store(cfg)
        store.ensure_root()
        spool_dir = store.root / "tmp"
        spool_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        spool = spool_dir / f"{uuid.uuid4().hex}.upload"
        size = 0
        try:
            with spool.open("wb") as handle:
                async for chunk in request.stream():
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > cfg.data_upload_max_bytes:
                        raise HTTPException(413, "backup_too_large")
                    handle.write(chunk)
            if size == 0:
                raise HTTPException(422, "empty_backup_file")

            def _chunks():
                with spool.open("rb") as reader:
                    for part in iter(lambda: reader.read(1024 * 1024), b""):
                        yield part

            meta = store.create_upload(_chunks(), declared)
        except data_staging_mod.StagingError as error:
            data_logger.info("backup upload rejected actor=%s code=%s", _owner_upload_actor(identity), error.code)
            status = 413 if error.code in {"backup_too_large", "staging_quota_exceeded"} else 422
            raise HTTPException(status, error.code) from None
        finally:
            spool.unlink(missing_ok=True)
        data_logger.info(
            "backup uploaded id=%s actor=%s sha256=%s size=%s tables=%s",
            meta["id"], _owner_upload_actor(identity), meta["sha256"][:16],
            meta["size_bytes"], meta["structure"].get("table_count"),
        )
        record_audit(
            db, identity, "backup.upload", target_type="backup_upload", target_id=str(meta["id"]),
            details={"size_bytes": int(meta["size_bytes"]), "table_count": meta["structure"].get("table_count")},
        )
        db.commit()
        return {"upload": store.get_upload(meta["id"])}

    @app.get("/api/owner/data/uploads/{upload_id}")
    def get_owner_data_upload(
        upload_id: str,
        request: Request,
        _identity: OwnerIdentity | AccountIdentity = Depends(require_permission("sys_backup")),
    ):
        cfg: Settings = request.app.state.settings
        store = _data_store(cfg)
        try:
            return {"upload": store.get_upload(upload_id), "audit_tool_available": _audit_script(cfg).is_file()}
        except data_staging_mod.StagingError as error:
            raise HTTPException(404, error.code) from None

    @app.post("/api/owner/data/uploads/{upload_id}/audit")
    def audit_owner_data_upload(
        upload_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_permission_write("sys_backup")),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = request.app.state.settings
        store = _data_store(cfg)
        script = _audit_script(cfg)
        if not script.is_file():
            raise HTTPException(503, "audit_tool_not_available")
        try:
            meta = store.run_audit(upload_id, script)
        except data_staging_mod.StagingError as error:
            raise HTTPException(404, error.code) from None
        data_logger.info(
            "backup audit id=%s actor=%s state=%s unchanged=%s",
            upload_id, _owner_upload_actor(identity), meta.get("state"),
            (meta.get("audit") or {}).get("unchanged"),
        )
        record_audit(
            db, identity, "backup.audit", target_type="backup_upload", target_id=upload_id,
            outcome=str(meta.get("state") or "ok"),
            details={"unchanged": (meta.get("audit") or {}).get("unchanged")},
        )
        db.commit()
        return {
            "upload": store.get_upload(upload_id),
            "unchanged": (meta.get("audit") or {}).get("unchanged"),
        }

    @app.delete("/api/owner/data/uploads/{upload_id}")
    def delete_owner_data_upload(
        upload_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_permission_write("sys_backup")),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = request.app.state.settings
        store = _data_store(cfg)
        try:
            removed = store.delete_upload(upload_id)
        except data_staging_mod.StagingError as error:
            raise HTTPException(404, error.code) from None
        data_logger.info("backup deleted id=%s actor=%s removed=%s", upload_id, _owner_upload_actor(identity), removed)
        if not removed:
            raise HTTPException(404, "upload_not_found")
        record_audit(db, identity, "backup.delete", target_type="backup_upload", target_id=upload_id)
        db.commit()
        return {"deleted": True}

    # ── اتصال سرویس‌ها: تنظیمات متمرکز اعتبارنامه‌ها ────────────────────────
    # فقط مالک/مدیر دارای مجوز sys_settings. مقدار محرمانه هرگز برنمی‌گردد؛
    # فقط «سایه» (hint)، منبع (پایگاه/محیط) و زمان آخرین تغییر.

    settings_logger = logging.getLogger("nora.service_settings")

    def _settings_secret_or_404(storage_id: str):
        spec = service_settings_mod.SECRETS_BY_ID.get(storage_id)
        if spec is None:
            raise HTTPException(404, "unknown_service_secret")
        return spec

    # ── پنل «تنظیمات» (۱۴۰۵/۰۸/۰۱): کلیدهای allowlist با مصرف‌کنندهٔ واقعی سمت سرور ──
    @app.get("/api/owner/settings")
    def get_owner_system_settings(
        _identity: OwnerIdentity | AccountIdentity = Depends(require_permission("sys_settings")),
        db: Session = Depends(get_db),
    ):
        response = JSONResponse(system_settings_mod.payload(db))
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.put("/api/owner/settings")
    async def put_owner_system_settings(
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_permission_write("sys_settings")),
        db: Session = Depends(get_db),
    ):
        payload = await _read_json_object(request, 16 * 1024)
        if set(payload) != {"changes"} or not isinstance(payload.get("changes"), dict):
            raise HTTPException(400, detail={"code": "invalid_settings_payload", "message": "بدنه باید فقط «changes» باشد."})
        actor = getattr(identity, "owner_id", "") or getattr(identity, "account_id", "")
        try:
            written = system_settings_mod.apply(db, payload["changes"], actor=str(actor))
        except system_settings_mod.SettingError as error:
            raise HTTPException(422, detail={"code": error.code, "message": error.message}) from None
        if written:
            record_audit(
                db, identity, "system_settings.update", target_type="system_settings",
                target_id=",".join(sorted(written))[:120], details={"changed": ",".join(sorted(written))},
            )
        db.commit()
        response = JSONResponse(system_settings_mod.payload(db))
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.get("/api/owner/service-settings")
    def get_owner_service_settings(
        request: Request,
        _identity: OwnerIdentity | AccountIdentity = Depends(require_permission("sys_settings")),
        db: Session = Depends(get_db),
    ):
        response = JSONResponse(service_settings_mod.status_payload(db, request.app.state.settings))
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.put("/api/owner/service-settings/{storage_id}")
    async def put_owner_service_secret(
        storage_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(
            require_permission_write("sys_settings")
        ),
        db: Session = Depends(get_db),
    ):
        spec = _settings_secret_or_404(storage_id)
        if not spec.editable:
            raise HTTPException(403, "secret_is_read_only")
        payload = await _read_json_object(request, 4 * 1024)
        if set(payload) - {"value", "acknowledge_restart"} or not isinstance(payload.get("value"), str):
            raise HTTPException(400, "invalid_service_secret_payload")
        if spec.acknowledge_restart and payload.get("acknowledge_restart") is not True:
            raise HTTPException(409, "restart_acknowledgement_required")
        try:
            service_settings_mod.set_secret(
                db, spec, payload["value"], request.app.state.settings
            )
        except ValueError as error:
            code = str(error) or "invalid_service_secret"
            status = 503 if code == "settings_encryption_not_configured" else (
                409 if code in {"otp_pepper_required"} else 422
            )
            settings_logger.info(
                "service secret rejected service=%s actor=%s code=%s",
                spec.storage_id,
                getattr(identity, "owner_id", "") or getattr(identity, "account_id", ""),
                code,
            )
            raise HTTPException(status, code) from None
        settings_logger.info(
            "service secret stored service=%s actor=%s", spec.storage_id,
            getattr(identity, "owner_id", "") or getattr(identity, "account_id", ""),
        )
        record_audit(
            db, identity, "service_secret.store", target_type="service_secret", target_id=spec.storage_id,
        )
        db.commit()
        return JSONResponse(service_settings_mod.status_payload(db, request.app.state.settings))

    @app.delete("/api/owner/service-settings/{storage_id}")
    def delete_owner_service_secret(
        storage_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(
            require_permission_write("sys_settings")
        ),
        db: Session = Depends(get_db),
    ):
        spec = _settings_secret_or_404(storage_id)
        if not spec.editable:
            raise HTTPException(403, "secret_is_read_only")
        removed = service_settings_mod.clear_secret(db, spec)
        settings_logger.info(
            "service secret cleared service=%s actor=%s removed=%s",
            spec.storage_id,
            getattr(identity, "owner_id", "") or getattr(identity, "account_id", ""),
            removed,
        )
        record_audit(
            db, identity, "service_secret.clear", target_type="service_secret", target_id=spec.storage_id,
            details={"removed": bool(removed)},
        )
        db.commit()
        return JSONResponse(service_settings_mod.status_payload(db, request.app.state.settings))

    @app.post("/api/owner/service-settings/{storage_id}/test")
    def test_owner_service_secret(
        storage_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(
            require_permission_write("sys_settings")
        ),
        db: Session = Depends(get_db),
    ):
        spec = _settings_secret_or_404(storage_id)
        if spec.probe != "bale_get_me":
            raise HTTPException(409, "connection_test_not_supported")
        cfg = service_settings_mod.effective_settings(db, request.app.state.settings)
        token = str(getattr(cfg, spec.attribute, ""))
        ok, code = probe_bale_bot(token)
        check = service_settings_mod.record_check(db, spec.storage_id, ok, code)
        settings_logger.info("service probe service=%s ok=%s code=%s", spec.storage_id, ok, code)
        record_audit(
            db, identity, "service_secret.test", target_type="service_secret", target_id=spec.storage_id,
            outcome="ok" if ok else "failed", details={"code": code},
        )
        db.commit()
        return {"ok": ok, "code": code, "check": check}

    @app.post("/api/public/cooperation-requests", status_code=201)
    async def submit_cooperation_request(request: Request, db: Session = Depends(get_db)):
        _same_origin(request)
        cfg: Settings = request.app.state.settings
        payload = await _read_json_object(request, cfg.max_request_bytes)
        if set(payload) != {"name", "organization", "contact", "kind", "message", "website"}:
            raise HTTPException(400, "invalid_cooperation_request")
        enforce_public_write_limit(
            request, db, "cooperation-requests", cfg, cfg.cooperation_submit_limit_per_minute
        )
        # The hidden honeypot is intentionally acknowledged without storing anything.
        if payload.get("website") not in ("", None):
            return {"received": True, "message": "درخواست شما دریافت شد."}
        name = _cooperation_text(payload.get("name"), "name", 120, minimum=2)
        organization = _cooperation_text(payload.get("organization"), "organization", 180)
        contact = _cooperation_contact(payload.get("contact"))
        kind = payload.get("kind")
        if kind not in {"teaching", "institution", "other"}:
            raise HTTPException(422, {"code": "invalid_cooperation_request", "field": "kind"})
        message = _cooperation_text(payload.get("message"), "message", 3000, minimum=12)
        if len(name) < 2 or len(message) < 12:
            raise HTTPException(422, "invalid_cooperation_request")
        record = CooperationRequestRecord(
            id=str(uuid.uuid4()),
            name=name,
            organization=organization,
            contact=contact,
            kind=kind,
            message=message,
            status="new",
        )
        db.add(record)
        db.commit()
        return {"received": True, "id": record.id, "message": "درخواست شما در سامانه ثبت شد."}

    @app.post("/api/auth/login")
    async def login(request: Request, response: Response, db: Session = Depends(get_db)):
        _same_origin(request)
        cfg: Settings = request.app.state.settings
        if not cfg.owner_id or not cfg.owner_username or not cfg.owner_password_hash:
            raise HTTPException(503, "owner_login_not_configured")
        payload = await _read_json_object(request, cfg.max_request_bytes)
        username, password = payload.get("username"), payload.get("password")
        if set(payload) != {"username", "password"} or not isinstance(username, str) or not isinstance(password, str):
            raise HTTPException(400, "invalid_login_payload")
        if len(username) > 160 or len(password.encode("utf-8")) > 1024:
            raise HTTPException(400, "invalid_login_payload")

        client_ip = request.client.host if request.client else "unknown"
        throttle_key = throttle_digest(cfg.owner_password_hash, client_ip)
        throttle = db.get(LoginThrottleRecord, throttle_key)
        now = _utc_now()
        if throttle and throttle.blocked_until and _as_utc(throttle.blocked_until) > now:
            retry = max(1, int((_as_utc(throttle.blocked_until) - now).total_seconds()))
            raise HTTPException(429, "login_temporarily_blocked", headers={"Retry-After": str(retry)})

        correct_user = constant_time_equal(username, cfg.owner_username)
        correct_password = verify_password(password, cfg.owner_password_hash)
        if not (correct_user and correct_password):
            if throttle is None:
                throttle = LoginThrottleRecord(
                    key_hash=throttle_key,
                    failures=0,
                    window_started_at=now,
                )
                db.add(throttle)
            if now - _as_utc(throttle.window_started_at) > timedelta(minutes=15):
                throttle.failures = 0
                throttle.window_started_at = now
                throttle.blocked_until = None
            throttle.failures += 1
            if throttle.failures >= 5:
                throttle.blocked_until = now + timedelta(minutes=15)
            db.commit()
            raise HTTPException(401, "invalid_credentials")

        if throttle is not None:
            db.delete(throttle)
        raw_session = new_token()
        raw_csrf = new_token()
        expires = now + timedelta(seconds=cfg.session_ttl_seconds)
        db.add(
            OwnerSessionRecord(
                id=str(uuid.uuid4()),
                owner_id=cfg.owner_id,
                token_hash=token_digest(raw_session),
                csrf_hash=token_digest(raw_csrf),
                expires_at=expires,
            )
        )
        db.commit()
        cookie_options: _CookieOptions = {
            "secure": cfg.cookie_secure,
            "samesite": _samesite(cfg),
            "path": "/",
            "max_age": cfg.session_ttl_seconds,
        }
        response.set_cookie(cfg.cookie_name, raw_session, httponly=True, **cookie_options)
        response.set_cookie(cfg.csrf_cookie_name, raw_csrf, httponly=False, **cookie_options)
        return {
            "authenticated": True,
            "owner_id": cfg.owner_id,
            "role": ROLE_OWNER,
            "permissions": sorted(permissions_for_role(ROLE_OWNER)),
        }

    @app.post("/api/auth/manager-login")
    async def manager_login(request: Request, response: Response, db: Session = Depends(get_db)):
        _same_origin(request)
        cfg: Settings = request.app.state.settings
        if not cfg.owner_password_hash:
            raise HTTPException(503, "manager_login_not_configured")
        payload = await _read_json_object(request, min(cfg.max_request_bytes, 4096))
        username, password = payload.get("username"), payload.get("password")
        if set(payload) != {"username", "password"} or not isinstance(username, str) or not isinstance(password, str):
            raise HTTPException(400, "invalid_login_payload")
        try:
            password_size = len(password.encode("utf-8", errors="strict"))
        except UnicodeError:
            raise HTTPException(400, "invalid_login_payload") from None
        if len(username) > 128 or password_size > 1024:
            raise HTTPException(400, "invalid_login_payload")

        username_key = _manager_username_key(username)
        throttle_user = username_key or "invalid-username"
        client_ip = request.client.host if request.client else "unknown"
        ip_key = throttle_digest(cfg.owner_password_hash, "manager-login-ip:" + client_ip)
        user_key = throttle_digest(
            cfg.owner_password_hash, "manager-login-user:" + throttle_user
        )
        now = _utc_now()
        for throttle_key in (ip_key, user_key):
            throttle = db.get(LoginThrottleRecord, throttle_key)
            if throttle and throttle.blocked_until and _as_utc(throttle.blocked_until) > now:
                retry = max(1, int((_as_utc(throttle.blocked_until) - now).total_seconds()))
                raise HTTPException(429, "login_temporarily_blocked", headers={"Retry-After": str(retry)})

        credential = (
            db.scalar(select(ManagerCredentialRecord).where(ManagerCredentialRecord.username_key == username_key))
            if username_key is not None else None
        )
        # A valid scrypt hash is used for unknown usernames too, avoiding a fast account-enumeration path.
        candidate_hash = credential.password_hash if credential is not None else cfg.owner_password_hash
        correct_password = verify_password(password, candidate_hash)
        role_record = db.get(AccountRoleRecord, credential.account_id) if credential is not None else None
        authenticated = (
            username_key is not None
            and credential is not None
            and role_record is not None
            and role_record.role in {"manager", "club-supervisor"}
            and correct_password
        )
        if not authenticated:
            retry_user = _touch_login_rate_limit(
                db, user_key, now, limit=5, window=timedelta(minutes=15)
            )
            retry_ip = _touch_login_rate_limit(
                db, ip_key, now, limit=20, window=timedelta(minutes=15)
            )
            db.commit()
            retry = max(retry_user, retry_ip)
            if retry:
                raise HTTPException(429, "login_temporarily_blocked", headers={"Retry-After": str(retry)})
            raise HTTPException(401, "invalid_credentials")

        assert credential is not None  # established by the authenticated predicate
        if _account_is_blocked(db, credential.account_id):
            db.commit()
            raise HTTPException(403, ACCOUNT_BLOCKED_DETAIL)
        for throttle_key in (ip_key, user_key):
            throttle = db.get(LoginThrottleRecord, throttle_key)
            if throttle is not None:
                db.delete(throttle)
        raw_session, raw_csrf = new_token(), new_token()
        db.add(
            AccountSessionRecord(
                id=str(uuid.uuid4()),
                account_id=credential.account_id,
                auth_provider="manager-password",
                token_hash=token_digest(raw_session),
                csrf_hash=token_digest(raw_csrf),
                expires_at=now + timedelta(seconds=cfg.session_ttl_seconds),
            )
        )
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(503, "account_session_unavailable") from None
        cookie_options: _CookieOptions = {
            "secure": cfg.cookie_secure,
            "samesite": _samesite(cfg),
            "path": "/",
            "max_age": cfg.session_ttl_seconds,
        }
        response.set_cookie(cfg.account_cookie_name, raw_session, httponly=True, **cookie_options)
        response.set_cookie(cfg.account_csrf_cookie_name, raw_csrf, httponly=False, **cookie_options)
        return {
            "authenticated": True,
            "account_id": credential.account_id,
            "provider": "manager-password",
        }

    @app.post("/api/auth/staff-login")
    async def staff_login(request: Request, response: Response, db: Session = Depends(get_db)):
        """Authenticate an owner or a provisioned manager through one staff form."""
        _same_origin(request)
        cfg: Settings = request.app.state.settings
        if not cfg.owner_password_hash:
            raise HTTPException(503, "staff_login_not_configured")
        payload = await _read_json_object(request, min(cfg.max_request_bytes, 4096))
        username, password = payload.get("username"), payload.get("password")
        if set(payload) != {"username", "password"} or not isinstance(username, str) or not isinstance(password, str):
            raise HTTPException(400, "invalid_login_payload")
        username = username.strip()
        try:
            password_size = len(password.encode("utf-8", errors="strict"))
        except UnicodeError:
            raise HTTPException(400, "invalid_login_payload") from None
        if not username or len(username) > 160 or password_size > 1024:
            raise HTTPException(400, "invalid_login_payload")

        now = _utc_now()
        client_ip = request.client.host if request.client else "unknown"
        ip_key = throttle_digest(cfg.owner_password_hash, "staff-login-ip:" + client_ip)
        user_key = throttle_digest(cfg.owner_password_hash, "staff-login-user:" + username.casefold())
        for throttle_key in (ip_key, user_key):
            throttle = db.get(LoginThrottleRecord, throttle_key)
            if throttle and throttle.blocked_until and _as_utc(throttle.blocked_until) > now:
                retry = max(1, int((_as_utc(throttle.blocked_until) - now).total_seconds()))
                raise HTTPException(429, "login_temporarily_blocked", headers={"Retry-After": str(retry)})

        owner_configured = bool(cfg.owner_id and cfg.owner_username and cfg.owner_password_hash)
        is_owner_username = owner_configured and constant_time_equal(username, cfg.owner_username)
        username_key = _manager_username_key(username)
        credential = (
            db.scalar(select(ManagerCredentialRecord).where(ManagerCredentialRecord.username_key == username_key))
            if username_key is not None and not is_owner_username else None
        )
        # Verify one scrypt hash for both known and unknown usernames to avoid a quick enumeration path.
        candidate_hash = credential.password_hash if credential is not None else cfg.owner_password_hash
        password_valid = verify_password(password, candidate_hash)
        role_record = db.get(AccountRoleRecord, credential.account_id) if credential is not None else None
        manager_role_valid = (
            role_record is not None and role_record.role in {"manager", "club-supervisor"}
        )
        authenticated_owner = bool(is_owner_username and password_valid)
        authenticated_manager = bool(credential is not None and manager_role_valid and password_valid)

        if not authenticated_owner and not authenticated_manager:
            retry_user = _touch_login_rate_limit(
                db, user_key, now, limit=5, window=timedelta(minutes=15)
            )
            retry_ip = _touch_login_rate_limit(
                db, ip_key, now, limit=20, window=timedelta(minutes=15)
            )
            db.commit()
            retry = max(retry_user, retry_ip)
            if retry:
                raise HTTPException(429, "login_temporarily_blocked", headers={"Retry-After": str(retry)})
            raise HTTPException(401, "invalid_credentials")

        for throttle_key in (ip_key, user_key):
            throttle = db.get(LoginThrottleRecord, throttle_key)
            if throttle is not None:
                db.delete(throttle)

        cookie_options: _CookieOptions = {
            "secure": cfg.cookie_secure,
            "samesite": _samesite(cfg),
            "path": "/",
            "max_age": cfg.session_ttl_seconds,
        }
        raw_session, raw_csrf = new_token(), new_token()
        if authenticated_owner:
            db.add(
                OwnerSessionRecord(
                    id=str(uuid.uuid4()),
                    owner_id=cfg.owner_id,
                    token_hash=token_digest(raw_session),
                    csrf_hash=token_digest(raw_csrf),
                    expires_at=now + timedelta(seconds=cfg.session_ttl_seconds),
                )
            )
            try:
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise HTTPException(503, "owner_session_unavailable") from None
            response.set_cookie(cfg.cookie_name, raw_session, httponly=True, **cookie_options)
            response.set_cookie(cfg.csrf_cookie_name, raw_csrf, httponly=False, **cookie_options)
            return {
                "authenticated": True,
                "provider": "owner",
                "owner_id": cfg.owner_id,
                "role": ROLE_OWNER,
                "permissions": sorted(permissions_for_role(ROLE_OWNER)),
            }

        assert credential is not None  # successful manager branch
        if _account_is_blocked(db, credential.account_id):
            db.commit()
            raise HTTPException(403, ACCOUNT_BLOCKED_DETAIL)
        db.add(
            AccountSessionRecord(
                id=str(uuid.uuid4()),
                account_id=credential.account_id,
                auth_provider="manager-password",
                token_hash=token_digest(raw_session),
                csrf_hash=token_digest(raw_csrf),
                expires_at=now + timedelta(seconds=cfg.session_ttl_seconds),
            )
        )
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(503, "account_session_unavailable") from None
        response.set_cookie(cfg.account_cookie_name, raw_session, httponly=True, **cookie_options)
        response.set_cookie(cfg.account_csrf_cookie_name, raw_csrf, httponly=False, **cookie_options)
        return {
            "authenticated": True,
            "provider": "manager-password",
            "account_id": credential.account_id,
        }

    @app.get("/api/auth/me")
    def auth_me(identity: OwnerIdentity = Depends(require_owner)):
        return {
            "authenticated": True,
            "owner_id": identity.owner_id,
            "role": ROLE_OWNER,
            "permissions": sorted(permissions_for_role(ROLE_OWNER)),
        }

    @app.post("/api/auth/logout")
    def logout(
        request: Request,
        response: Response,
        identity: OwnerIdentity = Depends(require_owner_write),
        db: Session = Depends(get_db),
    ):
        record = db.get(OwnerSessionRecord, identity.session_id)
        if record and record.revoked_at is None:
            record.revoked_at = _utc_now()
            db.commit()
        cfg: Settings = request.app.state.settings
        response.delete_cookie(cfg.cookie_name, path="/", secure=cfg.cookie_secure, httponly=True, samesite=_samesite(cfg))
        response.delete_cookie(cfg.csrf_cookie_name, path="/", secure=cfg.cookie_secure, httponly=False, samesite=_samesite(cfg))
        return {"authenticated": False}

    @app.post("/api/auth/bale-mini-app")
    async def bale_mini_app_login(
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ):
        _same_origin(request)
        cfg: Settings = _runtime_settings(db, request.app.state.settings)
        if not cfg.bale_bot_token:
            raise HTTPException(503, "bale_auth_not_configured")
        payload = await _read_json_object(request, min(cfg.max_request_bytes, 12 * 1024))
        if set(payload) != {"init_data"} or not isinstance(payload.get("init_data"), str):
            raise HTTPException(400, "invalid_bale_auth_payload")

        now = _utc_now()
        client_ip = request.client.host if request.client else "unknown"
        throttle_key = throttle_digest(cfg.bale_bot_token, "bale-mini-app\0" + client_ip)
        throttle = db.get(LoginThrottleRecord, throttle_key)
        if throttle and throttle.blocked_until and _as_utc(throttle.blocked_until) > now:
            retry = max(1, int((_as_utc(throttle.blocked_until) - now).total_seconds()))
            raise HTTPException(429, "login_temporarily_blocked", headers={"Retry-After": str(retry)})

        try:
            verified = verify_bale_mini_app_init_data(
                payload["init_data"],
                cfg.bale_bot_token,
                now=int(now.timestamp()),
                max_age_seconds=cfg.bale_init_data_max_age_seconds,
            )
        except ValueError:
            if throttle is None:
                throttle = LoginThrottleRecord(
                    key_hash=throttle_key,
                    failures=0,
                    window_started_at=now,
                )
                db.add(throttle)
            if now - _as_utc(throttle.window_started_at) > timedelta(minutes=15):
                throttle.failures = 0
                throttle.window_started_at = now
                throttle.blocked_until = None
            throttle.failures += 1
            if throttle.failures >= 5:
                throttle.blocked_until = now + timedelta(minutes=15)
            db.commit()
            raise HTTPException(401, "invalid_bale_init_data") from None

        if throttle is not None:
            db.delete(throttle)
        db.execute(
            delete(MiniAppAuthReplayRecord).where(MiniAppAuthReplayRecord.expires_at <= now)
        )
        if db.get(MiniAppAuthReplayRecord, verified.replay_key) is not None:
            raise HTTPException(409, "bale_init_data_replayed")

        account = get_or_create_bale_account(db, verified.user_id)
        if account.status == ACCOUNT_STATUS_BLOCKED:
            db.rollback()
            raise HTTPException(403, ACCOUNT_BLOCKED_DETAIL)
        raw_session, raw_csrf = new_token(), new_token()
        expires = now + timedelta(seconds=cfg.session_ttl_seconds)
        db.add(
            MiniAppAuthReplayRecord(
                replay_key=verified.replay_key,
                expires_at=now + timedelta(seconds=cfg.bale_init_data_max_age_seconds + 60),
            )
        )
        db.add(
            AccountSessionRecord(
                id=str(uuid.uuid4()),
                account_id=account.id,
                token_hash=token_digest(raw_session),
                csrf_hash=token_digest(raw_csrf),
                expires_at=expires,
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if db.get(MiniAppAuthReplayRecord, verified.replay_key) is not None:
                raise HTTPException(409, "bale_init_data_replayed") from None
            raise HTTPException(503, "account_session_unavailable") from None

        cookie_options: _CookieOptions = {
            "secure": cfg.cookie_secure,
            "samesite": _samesite(cfg),
            "path": "/",
            "max_age": cfg.session_ttl_seconds,
        }
        response.set_cookie(cfg.account_cookie_name, raw_session, httponly=True, **cookie_options)
        response.set_cookie(cfg.account_csrf_cookie_name, raw_csrf, httponly=False, **cookie_options)
        return {"authenticated": True, "account_id": account.id, "provider": "bale"}

    @app.get("/api/auth/captcha")
    async def get_login_captcha(request: Request):
        cfg: Settings = request.app.state.settings
        try:
            issued = issue_captcha(cfg.otp_pepper)
        except CaptchaError:
            raise HTTPException(503, "captcha_not_configured")
        return JSONResponse(issued, headers={"Cache-Control": "no-store"})

    @app.post("/api/auth/phone-otp/request")
    async def request_phone_otp(request: Request, db: Session = Depends(get_db)):
        _same_origin(request)
        cfg: Settings = _runtime_settings(db, request.app.state.settings)
        if not cfg.safir_api_key or not cfg.safir_bot_id or not cfg.otp_pepper:
            raise HTTPException(503, "phone_otp_not_configured")
        payload = await _read_json_object(request, 2048)
        if set(payload) != {"phone", "captcha_token", "captcha_answer"} or not isinstance(payload.get("phone"), str):
            raise HTTPException(400, "invalid_phone_otp_payload")
        phone = normalize_iran_phone(payload["phone"])
        if phone is None:
            raise HTTPException(422, "invalid_phone_number")

        now = _utc_now()
        client_ip = request.client.host if request.client else "unknown"
        ip_key = throttle_digest(cfg.otp_pepper, "phone-otp-request-ip\0" + client_ip)
        retry = _touch_login_rate_limit(
            db, ip_key, now, limit=5, window=timedelta(minutes=15)
        )
        if retry:
            db.commit()
            raise HTTPException(429, "login_temporarily_blocked", headers={"Retry-After": str(retry)})

        phone_hash = phone_digest(cfg.otp_pepper, phone)
        phone_key = throttle_digest(cfg.otp_pepper, "phone-otp-request-phone\0" + phone_hash)
        retry = _touch_login_rate_limit(
            db, phone_key, now, limit=5, window=timedelta(hours=1)
        )
        if retry:
            db.commit()
            raise HTTPException(429, "login_temporarily_blocked", headers={"Retry-After": str(retry)})

        # کپچا بعد از محدودیت نرخ بررسی می‌شود: هر حدس تصویر هم در سقف IP/شماره می‌نشیند.
        if not verify_captcha(cfg.otp_pepper, payload.get("captcha_token"), payload.get("captcha_answer"), now=now.timestamp()):
            db.commit()
            raise HTTPException(422, "invalid_captcha")
        # هر کپچای حل‌شده فقط یک بار پذیرفته می‌شود؛ nonce آن تا پایان عمر توکن در همان جدول محدودیت ورود علامت می‌خورد.
        nonce = captcha_nonce(payload.get("captcha_token"))
        captcha_key = throttle_digest(cfg.otp_pepper, "phone-otp-captcha-nonce\0" + (nonce or ""))
        if nonce is None or _touch_login_rate_limit(
            db, captcha_key, now, limit=1, window=timedelta(seconds=CAPTCHA_TTL_SECONDS)
        ):
            db.commit()
            raise HTTPException(422, "invalid_captcha")

        recent = db.scalar(
            select(PhoneOTPChallengeRecord)
            .where(
                PhoneOTPChallengeRecord.phone_hash == phone_hash,
                PhoneOTPChallengeRecord.consumed_at.is_(None),
                PhoneOTPChallengeRecord.expires_at > now,
                PhoneOTPChallengeRecord.created_at > now - timedelta(seconds=cfg.otp_resend_seconds),
            )
            .order_by(PhoneOTPChallengeRecord.created_at.desc())
            .limit(1)
        )
        if recent is not None:
            retry = max(
                1,
                cfg.otp_resend_seconds
                - int((now - _as_utc(recent.created_at)).total_seconds()),
            )
            db.commit()
            raise HTTPException(429, "otp_resend_too_soon", headers={"Retry-After": str(retry)})

        db.execute(
            delete(PhoneOTPChallengeRecord).where(
                PhoneOTPChallengeRecord.expires_at < now - timedelta(days=1)
            )
        )
        db.execute(
            update(PhoneOTPChallengeRecord)
            .where(
                PhoneOTPChallengeRecord.phone_hash == phone_hash,
                PhoneOTPChallengeRecord.consumed_at.is_(None),
            )
            .values(consumed_at=now)
        )
        challenge_id = str(uuid.uuid4())
        code = generate_otp_code()
        challenge = PhoneOTPChallengeRecord(
            id=challenge_id,
            phone_hash=phone_hash,
            code_hash=otp_digest(cfg.otp_pepper, challenge_id, code),
            expires_at=now + timedelta(seconds=cfg.otp_ttl_seconds),
            attempts=0,
            max_attempts=cfg.otp_max_attempts,
            created_at=now,
        )
        db.add(challenge)
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(503, "phone_otp_unavailable") from None

        try:
            delivered = await asyncio.to_thread(
                send_safir_otp,
                api_key=cfg.safir_api_key,
                bot_id=cfg.safir_bot_id,
                url=cfg.safir_url,
                phone=phone,
                code=code,
                include_request_id=cfg.safir_send_request_id,
            )
        except Exception:
            delivered = False
        if not delivered:
            challenge.consumed_at = _utc_now()
            try:
                db.commit()
            except SQLAlchemyError:
                db.rollback()
            raise HTTPException(503, "phone_otp_delivery_unavailable")
        return {
            "accepted": True,
            "challenge_id": challenge_id,
            "expires_in": cfg.otp_ttl_seconds,
            "resend_in": cfg.otp_resend_seconds,
        }

    @app.post("/api/auth/phone-otp/verify")
    async def verify_phone_otp(request: Request, response: Response, db: Session = Depends(get_db)):
        _same_origin(request)
        cfg: Settings = request.app.state.settings
        if not cfg.otp_pepper:
            raise HTTPException(503, "phone_otp_not_configured")
        payload = await _read_json_object(request, 2048)
        if set(payload) != {"challenge_id", "phone", "code"}:
            raise HTTPException(400, "invalid_phone_otp_payload")
        challenge_id, raw_phone, raw_code = (
            payload.get("challenge_id"), payload.get("phone"), payload.get("code")
        )
        challenge_pattern = (
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z"
        )
        if (
            not isinstance(challenge_id, str)
            or not re.fullmatch(challenge_pattern, challenge_id)
            or not isinstance(raw_phone, str)
            or not isinstance(raw_code, str)
        ):
            raise HTTPException(422, "invalid_phone_otp_payload")
        phone = normalize_iran_phone(raw_phone)
        code = raw_code.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        if phone is None or not re.fullmatch(r"[0-9]{6}\Z", code):
            raise HTTPException(422, "invalid_phone_otp_payload")

        now = _utc_now()
        client_ip = request.client.host if request.client else "unknown"
        ip_key = throttle_digest(cfg.otp_pepper, "phone-otp-verify-ip\0" + client_ip)
        retry = _touch_login_rate_limit(
            db, ip_key, now, limit=20, window=timedelta(minutes=15)
        )
        if retry:
            db.commit()
            raise HTTPException(429, "login_temporarily_blocked", headers={"Retry-After": str(retry)})

        submitted_phone_hash = phone_digest(cfg.otp_pepper, phone)
        challenge = db.scalar(
            select(PhoneOTPChallengeRecord)
            .where(PhoneOTPChallengeRecord.id == challenge_id)
            .with_for_update()
        )
        if challenge is None:
            db.commit()
            raise HTTPException(401, "invalid_or_expired_otp")
        if challenge.consumed_at is not None or _as_utc(challenge.expires_at) <= now:
            if challenge.consumed_at is None:
                challenge.consumed_at = now
            db.commit()
            raise HTTPException(401, "invalid_or_expired_otp")
        if challenge.attempts >= challenge.max_attempts:
            challenge.consumed_at = now
            db.commit()
            raise HTTPException(401, "invalid_or_expired_otp")

        expected_code_hash = otp_digest(cfg.otp_pepper, challenge_id, code)
        matches = constant_time_equal(challenge.phone_hash, submitted_phone_hash)
        matches = constant_time_equal(challenge.code_hash, expected_code_hash) and matches
        if not matches:
            challenge.attempts += 1
            if challenge.attempts >= challenge.max_attempts:
                challenge.consumed_at = now
            db.commit()
            raise HTTPException(401, "invalid_or_expired_otp")

        consumed = db.execute(
            update(PhoneOTPChallengeRecord)
            .where(
                PhoneOTPChallengeRecord.id == challenge_id,
                PhoneOTPChallengeRecord.phone_hash == submitted_phone_hash,
                PhoneOTPChallengeRecord.code_hash == expected_code_hash,
                PhoneOTPChallengeRecord.consumed_at.is_(None),
                PhoneOTPChallengeRecord.expires_at > now,
                PhoneOTPChallengeRecord.attempts < PhoneOTPChallengeRecord.max_attempts,
            )
            .values(consumed_at=now)
            .execution_options(synchronize_session=False)
        )
        if cast(CursorResult[Any], consumed).rowcount != 1:
            db.rollback()
            raise HTTPException(401, "invalid_or_expired_otp")

        # Decided server-side, after the code is proven: returning member vs. first login.
        existed = phone_account_exists(db, phone, pepper=cfg.otp_pepper)
        account = get_or_create_phone_account(db, phone, pepper=cfg.otp_pepper)
        if account.status == ACCOUNT_STATUS_BLOCKED:
            # The code is consumed (no replay); the session is simply not opened.
            db.commit()
            raise HTTPException(403, ACCOUNT_BLOCKED_DETAIL)
        profile_saved = db.get(AccountProfileRecord, account.id) is not None
        raw_session, raw_csrf = new_token(), new_token()
        db.add(
            AccountSessionRecord(
                id=str(uuid.uuid4()),
                account_id=account.id,
                auth_provider="phone",
                token_hash=token_digest(raw_session),
                csrf_hash=token_digest(raw_csrf),
                expires_at=now + timedelta(seconds=cfg.session_ttl_seconds),
            )
        )
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(503, "account_session_unavailable") from None

        cookie_options: _CookieOptions = {
            "secure": cfg.cookie_secure,
            "samesite": _samesite(cfg),
            "path": "/",
            "max_age": cfg.session_ttl_seconds,
        }
        response.set_cookie(cfg.account_cookie_name, raw_session, httponly=True, **cookie_options)
        response.set_cookie(cfg.account_csrf_cookie_name, raw_csrf, httponly=False, **cookie_options)
        return {
            "authenticated": True,
            "account_id": account.id,
            "provider": "phone",
            "created": not existed,
            "profile_saved": profile_saved,
        }

    @app.get("/api/account/me")
    def account_me(identity: AccountIdentity = Depends(require_account), db: Session = Depends(get_db)):
        bot_username = app.state.settings.bale_bot_username
        delivery_bot_url = f"https://ble.ir/{bot_username}" if re.fullmatch(r"[A-Za-z0-9_]{3,64}", bot_username) else ""
        payload: dict[str, Any] = {
            "authenticated": True,
            "account_id": identity.account_id,
            "provider": identity.provider,
            "role": identity.role,
            "permissions": sorted(permissions_for_role(identity.role)),
            "delivery_bot_url": delivery_bot_url,
        }
        if identity.provider == "manager-password":
            # Staff sessions show their own login name in the panel header (never the hash).
            credential = db.get(ManagerCredentialRecord, identity.account_id)
            payload["manager_username"] = credential.username_key if credential is not None else None
        return payload

    ACCOUNT_IDENTITY_PROVIDERS = ("phone", "bale")

    def _account_identities(db: Session, account_id: str) -> list[PlatformIdentityRecord]:
        return list(
            db.scalars(
                select(PlatformIdentityRecord)
                .where(PlatformIdentityRecord.account_id == account_id)
                .order_by(PlatformIdentityRecord.created_at, PlatformIdentityRecord.provider)
            ).all()
        )

    @app.get("/api/account/identities")
    def account_identities_list(
        response: Response,
        identity: AccountIdentity = Depends(require_account),
        db: Session = Depends(get_db),
    ):
        """هویت‌های تأییدشدهٔ همین حساب.

        شناسهٔ خام هیچ‌وقت برنمی‌گردد؛ فقط نام سکو و زمان پیوند. همین شکل پاسخ
        برای ربات و وب یکی است تا هر دو یک تصویر از حساب ببینند.
        """
        response.headers["Cache-Control"] = "private, no-store"
        rows = _account_identities(db, identity.account_id)
        return {
            "account_id": identity.account_id,
            "identities": [
                {
                    "provider": row.provider,
                    "linked_at": _as_utc(row.created_at).isoformat() if row.created_at else None,
                }
                for row in rows
            ],
            "available_providers": list(ACCOUNT_IDENTITY_PROVIDERS),
            "bale_link_available": bool(_runtime_settings(db, app.state.settings).bale_bot_token),
        }

    def _consume_mini_app_replay(
        db: Session, verified: BaleMiniAppIdentity, max_age_seconds: int
    ) -> None:
        """اثر انگشت یک‌بارمصرف را ثبت می‌کند؛ استفادهٔ دوباره رد می‌شود."""
        now = _utc_now()
        db.execute(delete(MiniAppAuthReplayRecord).where(MiniAppAuthReplayRecord.expires_at <= now))
        if db.get(MiniAppAuthReplayRecord, verified.replay_key) is not None:
            raise HTTPException(409, "bale_init_data_replayed")
        db.add(
            MiniAppAuthReplayRecord(
                replay_key=verified.replay_key,
                expires_at=now + timedelta(seconds=max_age_seconds + 60),
            )
        )

    @app.post("/api/account/identities/bale")
    async def account_link_bale_identity(
        request: Request,
        identity: AccountIdentity = Depends(require_account_write),
        db: Session = Depends(get_db),
    ):
        """پیوند یک هویت بلهِ اثبات‌شده به همین حساب.

        اثبات مالکیت فقط از راه امضای `initData` انجام می‌شود؛ شناسه‌ای که
        مرورگر بفرستد به‌تنهایی پذیرفته نمی‌شود و نقش از سمت کلاینت خوانده
        نمی‌شود. اگر آن هویت بله از قبل به حساب دیگری وصل باشد، هیچ ادغام
        خودکاری رخ نمی‌دهد و درخواست با ۴۰۹ رد می‌شود تا داده‌ای گم نشود.
        """
        cfg: Settings = _runtime_settings(db, request.app.state.settings)
        if not cfg.bale_bot_token:
            raise HTTPException(503, "bale_auth_not_configured")
        payload = await _read_json_object(request, min(cfg.max_request_bytes, 12 * 1024))
        if set(payload) != {"init_data"} or not isinstance(payload.get("init_data"), str):
            raise HTTPException(400, "invalid_bale_auth_payload")

        try:
            verified = verify_bale_mini_app_init_data(
                payload["init_data"],
                cfg.bale_bot_token,
                now=int(_utc_now().timestamp()),
                max_age_seconds=cfg.bale_init_data_max_age_seconds,
            )
        except ValueError:
            raise HTTPException(401, "invalid_bale_init_data") from None

        subject = str(verified.user_id)
        claimed = db.scalar(
            select(PlatformIdentityRecord).where(
                PlatformIdentityRecord.provider == "bale",
                PlatformIdentityRecord.provider_user_id == subject,
            )
        )
        if claimed is not None:
            if claimed.account_id == identity.account_id:
                return {"linked": True, "provider": "bale", "already_linked": True}
            raise HTTPException(409, detail={"code": "bale_identity_already_linked"})
        if any(row.provider == "bale" for row in _account_identities(db, identity.account_id)):
            raise HTTPException(409, detail={"code": "account_already_has_bale_identity"})

        _consume_mini_app_replay(db, verified, cfg.bale_init_data_max_age_seconds)
        db.add(
            PlatformIdentityRecord(
                id=str(uuid.uuid4()),
                account_id=identity.account_id,
                provider="bale",
                provider_user_id=subject,
            )
        )
        try:
            db.commit()
        except IntegrityError:
            # مسابقهٔ هم‌زمان با ورود/پیوند دیگر؛ همان هویت به حساب دیگری رسید.
            db.rollback()
            raise HTTPException(409, detail={"code": "bale_identity_already_linked"}) from None
        return {"linked": True, "provider": "bale", "already_linked": False}

    @app.delete("/api/account/identities/bale")
    def account_unlink_bale_identity(
        request: Request,
        identity: AccountIdentity = Depends(require_account_write),
        db: Session = Depends(get_db),
    ):
        """برداشتن پیوند بله؛ برگشت‌پذیر و بدون حذف هیچ سابقه‌ای.

        اگر بله تنها هویت حساب باشد رد می‌شود، وگرنه حساب بی‌صاحب می‌ماند.
        نشست‌های دیگری که با provider بله ساخته شده‌اند باطل می‌شوند تا نشست
        کهنه از پیوندِ برداشته‌شده زنده نماند؛ نشست جاری دست‌نخورده می‌ماند.
        """
        record = db.scalar(
            select(PlatformIdentityRecord).where(
                PlatformIdentityRecord.account_id == identity.account_id,
                PlatformIdentityRecord.provider == "bale",
            )
        )
        if record is None:
            raise HTTPException(404, detail={"code": "bale_identity_not_linked"})
        remaining = [
            row for row in _account_identities(db, identity.account_id) if row.id != record.id
        ]
        if not remaining:
            raise HTTPException(409, detail={"code": "last_identity_cannot_be_removed"})
        db.delete(record)
        db.execute(
            update(AccountSessionRecord)
            .where(
                AccountSessionRecord.account_id == identity.account_id,
                AccountSessionRecord.auth_provider == "bale",
                AccountSessionRecord.id != identity.session_id,
                AccountSessionRecord.revoked_at.is_(None),
            )
            .values(revoked_at=_utc_now())
        )
        db.commit()
        return {"linked": False, "provider": "bale"}

    PROFILE_FIELD_KEYS = ("fullName", "nationalId", "birthDate", "gender", "province", "city", "address", "email")

    def _clean_profile_fields(raw: Any) -> dict[str, str]:
        if not isinstance(raw, dict):
            raise HTTPException(422, "profile_invalid")
        out: dict[str, str] = {}
        for key in PROFILE_FIELD_KEYS:
            value = raw.get(key, "")
            if value is None:
                value = ""
            if not isinstance(value, str):
                raise HTTPException(422, "profile_invalid")
            cleaned = re.sub(r"[\u0000-\u001f<>]", "", value).strip()
            if len(cleaned) > 120:
                raise HTTPException(422, "profile_field_too_long")
            out[key] = cleaned
        return out

    @app.get("/api/account/profile")
    def account_profile_get(
        response: Response,
        identity: AccountIdentity = Depends(require_account),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        record = db.get(AccountProfileRecord, identity.account_id)
        fields = {key: "" for key in PROFILE_FIELD_KEYS}
        if record is not None and isinstance(record.fields, dict):
            for key in PROFILE_FIELD_KEYS:
                value = record.fields.get(key, "")
                fields[key] = value if isinstance(value, str) else ""
        return {"fields": fields, "saved": record is not None}

    @app.put("/api/account/profile")
    def account_profile_put(
        payload: dict[str, Any],
        identity: AccountIdentity = Depends(require_account_write),
        db: Session = Depends(get_db),
    ):
        fields = _clean_profile_fields(payload)
        record = db.get(AccountProfileRecord, identity.account_id)
        if record is None:
            record = AccountProfileRecord(account_id=identity.account_id, fields=fields, updated_at=_utc_now())
            db.add(record)
        else:
            record.fields = fields
            record.updated_at = _utc_now()
        db.commit()
        return {"fields": fields, "saved": True}

    @app.get("/api/account/registrations")
    def account_registrations(
        response: Response,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        identity: AccountIdentity = Depends(require_account),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Cookie"
        filters = (
            account_form_record_scope(db, identity.account_id),
            FormResponseRecord.added_by_response_id.is_(None),
            FormRecord.model == "registration",
            FormRecord.purpose == "registration",
        )
        total = int(db.scalar(
            select(func.count(FormResponseRecord.id))
            .join(FormResponseDraftRecord, FormResponseDraftRecord.id == FormResponseRecord.draft_id)
            .join(FormRecord, FormRecord.id == FormResponseRecord.form_id)
            .where(*filters)
        ) or 0)
        rows = db.execute(
            select(FormResponseRecord, FormPaymentRecord, FormRecord.event_id)
            .join(FormResponseDraftRecord, FormResponseDraftRecord.id == FormResponseRecord.draft_id)
            .join(FormRecord, FormRecord.id == FormResponseRecord.form_id)
            .outerjoin(FormPaymentRecord, FormPaymentRecord.response_id == FormResponseRecord.id)
            .where(*filters)
            .order_by(FormResponseRecord.created_at.desc(), FormResponseRecord.id.desc())
            .limit(limit + 1)
            .offset(offset)
        ).all()
        # Phase 9.5 §9 (additive): the live event schedule for the shared countdown — computed with the
        # server clock by the same ``registration_state`` rule the public pages use, so «رویدادهای من»
        # never invents a deadline. Only lifecycle/state and the two ISO targets leave the server.
        site = db.get(SiteContentRecord, "public")
        now = _utc_now()
        live_events: dict[str, dict[str, Any]] = {}
        for live_event in public_site_content(site.content or {}).get("events", []) if site is not None else []:
            if isinstance(live_event, dict) and live_event.get("id"):
                live_events[str(live_event.get("id"))] = live_event

        def _event_schedule(event_id: str) -> dict[str, Any] | None:
            live_event = live_events.get(event_id)
            if live_event is None:
                return None
            registration = event_time.registration_state(live_event, now=now, has_form=True)
            return {
                "state": registration["state"],
                "lifecycle": registration["lifecycle"],
                "startsAt": registration["startsAt"],
                "startsIn": registration["startsIn"],
                "ended": registration["state"] == "ended",
            }

        items = []
        for record, payment, form_event_id in rows[:limit]:
            snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
            event = _json_dict_member(snapshot, "event")
            form_name = _ticket_text(snapshot.get("name") or "فرم ثبت‌نام", 160) or "فرم ثبت‌نام"
            items.append({
                "id": record.id,
                # Phase 9.3 (additive): lets «رویدادهای من» link a held event to the archive the member can
                # already open (the library decides access; this is only the join key, never an access basis).
                "event_id": str(form_event_id or "")[:120],
                "form_name": form_name,
                "event_title": _ticket_text(event.get("title") or form_name, 160) or form_name,
                "event_date": _ticket_text(event.get("date") or "", 120),
                "event_time": _ticket_text(event.get("time") or "", 120),
                "event_schedule": _event_schedule(str(form_event_id or "")) if form_event_id else None,
                "status": record.status,
                "payment_status": payment.status if payment is not None else None,
                "receipt_uploaded": (
                    record.receipt_review_task_id is not None or record.receipt_upload is not None
                ),
                "ticket_checked_in": record.ticket_checked_in_at is not None,
                "ticket_type": _form_response_ticket_type(record),
                "created_at": _as_utc(record.created_at).isoformat(),
            })
        return {
            "source": "shared_server_database",
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }

    @app.post("/api/bot/identity")
    async def bot_identity(
        request: Request,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        payload = await _read_json_object(request, 1024)
        if set(payload) != {"bale_user_id"}:
            raise HTTPException(400, "invalid_bot_identity_payload")
        raw_user_id = payload.get("bale_user_id")
        if isinstance(raw_user_id, bool) or not isinstance(raw_user_id, (str, int)):
            raise HTTPException(422, "invalid_bale_user_id")
        bale_user_id = str(raw_user_id)
        if not re.fullmatch(r"[1-9][0-9]{0,19}", bale_user_id):
            raise HTTPException(422, "invalid_bale_user_id")

        platform_identity = db.scalar(
            select(PlatformIdentityRecord).where(
                PlatformIdentityRecord.provider == "bale",
                PlatformIdentityRecord.provider_user_id == bale_user_id,
            )
        )
        account_id = platform_identity.account_id if platform_identity is not None else None
        role = None
        cfg: Settings = request.app.state.settings
        if bale_user_id == cfg.owner_bale_user_id and cfg.owner_bale_user_id:
            role = ROLE_OWNER
        elif account_id is not None:
            assigned = db.get(AccountRoleRecord, account_id)
            candidate = assigned.role if assigned is not None else None
            role = candidate if candidate in ROLE_KEYS else None
        return {
            "bale_user_id": bale_user_id,
            "account_id": account_id,
            "role": role,
            "permissions": sorted(permissions_for_role(role)),
        }

    @app.post("/api/bot/files")
    async def upload_bot_private_file(
        request: Request,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        raw_user_id = request.headers.get("x-bale-user-id", "")
        if not re.fullmatch(r"[1-9][0-9]{0,19}", raw_user_id):
            raise HTTPException(422, "invalid_bale_user_id")
        idempotency_key = request.headers.get("idempotency-key", "")
        if not re.fullmatch(r"[A-Za-z0-9:_-]{1,120}", idempotency_key):
            raise HTTPException(422, "invalid_idempotency_key")
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > 8 * 1024 * 1024:
                raise HTTPException(413, "private_file_too_large")
        blob = bytes(content)
        content_type = _private_file_type(blob)
        if not content_type:
            raise HTTPException(415, "unsupported_private_file_type")
        declared_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if declared_type not in ("", "application/octet-stream", content_type):
            raise HTTPException(415, "private_file_type_mismatch")
        supplied_name = request.headers.get("x-file-name", "attachment")
        safe_name = "".join(
            char for char in supplied_name.replace("\\", "/").split("/")[-1]
            if char.isprintable() and char not in "\\\"\\'<>"
        )[:120] or "attachment"
        content_hash = hashlib.sha256(blob).hexdigest()
        try:
            account = get_or_create_bale_account(db, raw_user_id)
        except ValueError:
            raise HTTPException(422, "invalid_bale_user_id") from None
        db.flush()
        existing = db.scalar(
            select(PrivateFileRecord).where(
                PrivateFileRecord.account_id == account.id,
                PrivateFileRecord.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.content_hash != content_hash or existing.content_type != content_type:
                raise HTTPException(409, "file_idempotency_key_reused")
            return {
                "id": existing.id,
                "content_type": existing.content_type,
                "size": existing.content_size,
                "created": False,
            }
        item = PrivateFileRecord(
            id=str(uuid.uuid4()),
            account_id=account.id,
            bale_user_id=raw_user_id,
            idempotency_key=idempotency_key,
            content_hash=content_hash,
            file_name=safe_name,
            content_type=content_type,
            content_size=len(blob),
            content=blob,
        )
        db.add(item)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(
                select(PrivateFileRecord).where(
                    PrivateFileRecord.account_id == account.id,
                    PrivateFileRecord.idempotency_key == idempotency_key,
                )
            )
            if existing is None or existing.content_hash != content_hash:
                raise HTTPException(409, "private_file_conflict") from None
            item = existing
            return {"id": item.id, "content_type": item.content_type, "size": item.content_size, "created": False}
        return {"id": item.id, "content_type": item.content_type, "size": item.content_size, "created": True}

    @app.post("/api/bot/certificates")
    async def submit_bot_certificate(
        request: Request,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        """Mirror one bot-issued certificate. Owner is resolved server-side; unmapped owners are not stored."""
        payload = await _read_json_object(request, 16 * 1024)
        try:
            submission = certificates_mod.validate_submission(payload)
            prior_status = db.scalar(
                select(CertificateRecord.status).where(CertificateRecord.external_key == submission["external_key"])
            )
            record, created = certificates_mod.upsert(db, submission)
        except certificates_mod.CertificateError as error:
            raise _certificate_error(error) from None
        # Issued / revoked notifications only on a real state change of the mirrored certificate
        # (the bot center is the issuer; the server never issues). Keyed per certificate+status.
        if record.status in {"issued", "revoked"} and record.status != prior_status:
            label = record.title or record.event_title or "گواهی"
            if record.status == "issued":
                title, body = "گواهی شما صادر شد", f"گواهی «{label}» برای شما صادر شد و در بخش «گواهی‌ها» حساب کاربری قابل مشاهده است."
            else:
                title, body = "گواهی شما باطل شد", f"گواهی «{label}» باطل شد و دیگر معتبر نیست. برای پیگیری با برگزارکننده تماس بگیرید."
            notifications_mod.queue(
                db, account_id=record.account_id, kind=notifications_mod.KIND_CERTIFICATE, title=title, body=body,
                key=notifications_mod.dedupe_key("certificate", record.external_key, record.status),
                bale_ids=[record.bale_user_id] if record.bale_user_id else [],
                link=notifications_mod.account_link("certificates"),
            )
        db.commit()
        return {
            "id": record.id,
            "created": created,
            "status": record.status,
            "account_id": record.account_id,
            "has_file": record.file_id is not None,
            "has_preview": record.preview_file_id is not None,
        }

    @app.post("/api/bot/club/points")
    async def submit_bot_club_points_entry(
        request: Request,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        """Mirror one immutable row of the bot's points ledger. Owner resolved server-side; unmapped owners are not stored."""
        payload = await _read_json_object(request, 8 * 1024)
        try:
            submission = club_points_mod.validate_submission(payload)
            record, created = club_points_mod.upsert(db, submission)
        except club_points_mod.ClubPointsError as error:
            raise HTTPException(error.status_code, error.code) from None
        db.commit()
        return {
            "id": record.id,
            "created": created,
            "external_key": record.external_key,
            "account_id": record.account_id,
            "balance_after": record.balance_after,
        }

    @app.get("/api/bot/files")
    def list_bot_private_files(
        response: Response,
        bale_user_id: str = Query(..., min_length=1, max_length=20),
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "no-store"
        if not re.fullmatch(r"[1-9][0-9]{0,19}", bale_user_id):
            raise HTTPException(422, "invalid_bale_user_id")
        identity = db.scalar(
            select(PlatformIdentityRecord).where(
                PlatformIdentityRecord.provider == "bale",
                PlatformIdentityRecord.provider_user_id == bale_user_id,
            )
        )
        if identity is None:
            return {"items": []}
        items = db.scalars(
            select(PrivateFileRecord)
            .where(PrivateFileRecord.account_id == identity.account_id)
            .order_by(PrivateFileRecord.created_at.desc(), PrivateFileRecord.id)
            .limit(100)
        ).all()
        return {
            "items": [
                {
                    "id": item.id,
                    "file_name": item.file_name,
                    "content_type": item.content_type,
                    "content_size": item.content_size,
                    "created_at": _as_utc(item.created_at).isoformat(),
                }
                for item in items
            ]
        }

    @app.get("/api/bot/files/{file_id}")
    def get_bot_private_file(
        file_id: str,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        item = db.get(PrivateFileRecord, file_id)
        if item is None:
            raise HTTPException(404, "private_file_not_found")
        return Response(
            content=item.content,
            media_type=item.content_type,
            headers={
                "Content-Disposition": "attachment",
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get("/api/bot/content-files/{delivery_id}")
    def get_bot_public_content_file(
        delivery_id: str,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        if not re.fullmatch(r"[0-9a-f]{32}", delivery_id):
            raise HTTPException(422, "invalid_content_delivery_id")
        record = db.get(SiteContentRecord, "public")
        resolved = resolve_public_delivery_file((record.content or {}) if record else {}, delivery_id)
        if resolved is None:
            raise HTTPException(404, "content_delivery_not_found")
        content, content_type, file_name = resolved
        encoded_name = quote(file_name, safe="")
        fallback_name = re.sub(r"[^A-Za-z0-9._-]", "_", file_name)[:100] or "attachment"
        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename=\"{fallback_name}\"; filename*=UTF-8''{encoded_name}",
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.post("/api/bot/workflows")
    async def create_bot_workflow(
        request: Request,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        payload = await _read_json_object(request, 32 * 1024)
        if set(payload) != {"bale_user_id", "kind", "payload", "idempotency_key"}:
            raise HTTPException(400, "invalid_workflow_payload")
        raw_user_id = payload.get("bale_user_id")
        if isinstance(raw_user_id, bool) or not isinstance(raw_user_id, (str, int)):
            raise HTTPException(422, "invalid_bale_user_id")
        bale_user_id = str(raw_user_id)
        if not re.fullmatch(r"[1-9][0-9]{0,19}", bale_user_id):
            raise HTTPException(422, "invalid_bale_user_id")
        kind = payload.get("kind")
        if kind not in {"profile_review", "receipt_review"}:
            raise HTTPException(400, "unsupported_workflow_kind")
        idempotency_key = payload.get("idempotency_key")
        if not isinstance(idempotency_key, str) or not re.fullmatch(r"[A-Za-z0-9:_-]{1,80}", idempotency_key):
            raise HTTPException(422, "invalid_idempotency_key")
        data = payload.get("payload")
        if not isinstance(data, dict) or not data or len(data) > 64 or _contains_secret_key(data):
            raise HTTPException(422, "invalid_workflow_data")
        try:
            encoded_data = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError):
            raise HTTPException(422, "invalid_workflow_data") from None
        if len(encoded_data.encode("utf-8")) > 24 * 1024:
            raise HTTPException(413, "workflow_data_too_large")
        linked_public_response: FormResponseRecord | None = None
        if kind == "profile_review":
            for key, value in data.items():
                if key == "file_refs":
                    if not isinstance(value, list) or len(value) > 16 or any(
                        not isinstance(ref, str) or not re.fullmatch(
                            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}", ref
                        ) for ref in value
                    ):
                        raise HTTPException(422, "invalid_profile_files")
                    continue
                if (
                    not isinstance(key, str)
                    or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", key)
                    or not (value is None or isinstance(value, (str, int, float, bool)))
                    or (isinstance(value, str) and len(value) > 2000)
                ):
                    raise HTTPException(422, "invalid_profile_data")
        else:
            allowed_receipt_fields = {
                "amount", "currency", "event_id", "event_title", "registration_id",
                "transaction_id", "form_id", "form_response_id", "ref_code", "note",
                "submitted_at", "photo_file_id", "proof_file_id", "file_id", "file_refs",
                "paylink_payment_id", "registration_source", "_legacy_receipt_id", "_legacy_source_id",
            }
            if set(data) - allowed_receipt_fields:
                raise HTTPException(422, "invalid_receipt_data")
            amount = data.get("amount")
            if amount is not None and (isinstance(amount, bool) or not isinstance(amount, int) or amount < 0):
                raise HTTPException(422, "invalid_receipt_amount")
            if any(
                not isinstance(value, (str, int, bool)) or (isinstance(value, str) and len(value) > 2000)
                for key, value in data.items()
                if key != "file_refs" and value is not None
            ):
                raise HTTPException(422, "invalid_receipt_data")
            file_refs = data.get("file_refs", [])
            if not isinstance(file_refs, list) or len(file_refs) > 16 or any(
                not isinstance(ref, str) or not re.fullmatch(
                    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}", ref
                ) for ref in file_refs
            ):
                raise HTTPException(422, "invalid_receipt_files")
            source = data.get("registration_source")
            if source is not None:
                if source != "public_form":
                    raise HTTPException(422, "invalid_receipt_registration_source")
                form_id = data.get("form_id")
                response_id = data.get("form_response_id")
                if (
                    not isinstance(form_id, str)
                    or not _BOT_FORM_RESPONSE_ID.fullmatch(form_id)
                    or not isinstance(response_id, str)
                    or not _BOT_FORM_RESPONSE_ID.fullmatch(response_id)
                    or not file_refs
                ):
                    raise HTTPException(422, "invalid_public_form_receipt")
                linked_public_response = db.scalar(
                    select(FormResponseRecord)
                    .join(
                        FormResponseDraftRecord,
                        FormResponseDraftRecord.id == FormResponseRecord.draft_id,
                    )
                    .where(
                        FormResponseRecord.id == response_id,
                        FormResponseRecord.form_id == form_id,
                        FormResponseRecord.status == "accepted",
                        FormResponseRecord.ticket_claimed_by_bale_user_id == bale_user_id,
                        FormResponseDraftRecord.bot_bale_user_id == bale_user_id,
                    )
                    .with_for_update()
                )
                if linked_public_response is None:
                    raise HTTPException(404, "public_form_response_not_claimed")
                snapshot = linked_public_response.form_snapshot if isinstance(linked_public_response.form_snapshot, dict) else {}
                if snapshot.get("receipt_review_required") is not True:
                    raise HTTPException(422, "public_form_receipt_not_required")
        cfg: Settings = request.app.state.settings
        try:
            account = get_or_create_bale_account(db, bale_user_id)
        except ValueError:
            raise HTTPException(422, "invalid_bale_user_id") from None
        db.flush()
        create_hash = hashlib.sha256(
            json.dumps(
                {"kind": kind, "payload": data}, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        prior = db.scalar(
            select(AdminTaskRecord).where(
                AdminTaskRecord.account_id == account.id,
                AdminTaskRecord.kind == kind,
                AdminTaskRecord.idempotency_key == idempotency_key,
            )
        )
        if prior is not None:
            if prior.create_hash != create_hash:
                raise HTTPException(409, "idempotency_key_reused")
            if linked_public_response is not None:
                linked_task_id = linked_public_response.receipt_review_task_id
                if linked_task_id not in (None, prior.id):
                    raise HTTPException(409, "public_form_receipt_already_submitted")
                if linked_task_id is None:
                    linked_public_response.receipt_review_task_id = prior.id
                    db.commit()
            return {"task": admin_task_view(prior), "created": False}
        if linked_public_response is not None and linked_public_response.receipt_review_task_id is not None:
            raise HTTPException(409, "public_form_receipt_already_submitted")
        file_refs = data.get("file_refs", [])
        uploaded_files: Sequence[PrivateFileRecord] = []
        if file_refs:
            uploaded_files = db.scalars(
                select(PrivateFileRecord).where(
                    PrivateFileRecord.account_id == account.id,
                    PrivateFileRecord.id.in_(file_refs),
                )
            ).all()
            if len(uploaded_files) != len(set(file_refs)):
                raise HTTPException(422, "private_file_not_found")
            if any(item.task_id is not None for item in uploaded_files):
                raise HTTPException(409, "private_file_already_attached")
        if kind == "profile_review":
            db.execute(
                update(AdminTaskRecord)
                .where(
                    AdminTaskRecord.account_id == account.id,
                    AdminTaskRecord.kind == kind,
                    AdminTaskRecord.status == "pending",
                )
                .values(status="superseded", version=AdminTaskRecord.version + 1, updated_at=_utc_now())
            )
        task = AdminTaskRecord(
            id=str(uuid.uuid4()),
            account_id=account.id,
            bale_user_id=bale_user_id,
            kind=kind,
            payload=data,
            status="pending",
            idempotency_key=idempotency_key,
            create_hash=create_hash,
            version=1,
        )
        db.add(task)
        if linked_public_response is not None:
            linked_public_response.receipt_review_task_id = task.id
        for item in uploaded_files:
            item.task_id = task.id
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            duplicate = db.scalar(
                select(AdminTaskRecord).where(
                    AdminTaskRecord.account_id == account.id,
                    AdminTaskRecord.kind == kind,
                    AdminTaskRecord.idempotency_key == idempotency_key,
                )
            )
            if duplicate is None or duplicate.create_hash != create_hash:
                raise HTTPException(409, "workflow_conflict") from None
            task = duplicate
            if linked_public_response is not None:
                fresh_response = db.get(FormResponseRecord, linked_public_response.id)
                if fresh_response is not None:
                    linked_task_id = fresh_response.receipt_review_task_id
                    if linked_task_id not in (None, duplicate.id):
                        raise HTTPException(409, "public_form_receipt_already_submitted")
                    fresh_response.receipt_review_task_id = duplicate.id
                    db.commit()
            return {"task": admin_task_view(task), "created": False}
        db.refresh(task)
        return {"task": admin_task_view(task), "created": True}

    @app.get("/api/bot/workflows/projection-pending")
    def bot_workflow_projection_pending(
        limit: int = Query(default=50, ge=1, le=100),
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        tasks = db.scalars(
            select(AdminTaskRecord)
            .where(
                AdminTaskRecord.status.in_(("approved", "rejected")),
                AdminTaskRecord.projection_status == "pending",
            )
            .order_by(AdminTaskRecord.reviewed_at.asc(), AdminTaskRecord.id)
            .limit(limit)
        ).all()
        return {"items": [admin_task_view(task) for task in tasks]}

    @app.post("/api/bot/workflows/{task_id}/projection-applied")
    def bot_workflow_projection_applied(
        task_id: str,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        task = db.get(AdminTaskRecord, task_id)
        if task is None or task.status not in {"approved", "rejected"}:
            raise HTTPException(404, "workflow_decision_not_found")
        if task.projection_status != "applied":
            task.projection_status = "applied"
            task.projection_attempts += 1
            task.last_projection_error = None
            db.commit()
        return {"applied": True}

    @app.post("/api/bot/workflows/{task_id}/projection-failed")
    def bot_workflow_projection_failed(
        task_id: str,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        task = db.get(AdminTaskRecord, task_id)
        if task is None or task.status not in {"approved", "rejected"}:
            raise HTTPException(404, "workflow_decision_not_found")
        if task.projection_status == "pending":
            task.projection_attempts += 1
            task.last_projection_error = "bot_projection_failed"
            if task.projection_attempts >= 5:
                task.projection_status = "failed"
            db.commit()
        return {"recorded": True, "projection_status": task.projection_status}

    @app.get("/api/bot/inbox")
    def bot_workflow_inbox(
        request: Request,
        bale_user_id: str = Query(..., min_length=1, max_length=20),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        if not re.fullmatch(r"[1-9][0-9]{0,19}", bale_user_id):
            raise HTTPException(422, "invalid_bale_user_id")
        cfg: Settings = request.app.state.settings
        _, role = bot_account_identity(db, cfg, bale_user_id)
        if role is None:
            raise HTTPException(403, "permission_denied")
        kinds = [kind for kind in ("profile_review", "receipt_review") if has_permission(role, workflow_permission(kind))]
        if not kinds:
            raise HTTPException(403, "permission_denied")
        tasks = db.scalars(
            select(AdminTaskRecord)
            .where(AdminTaskRecord.status == "pending", AdminTaskRecord.kind.in_(kinds))
            .order_by(AdminTaskRecord.created_at.asc(), AdminTaskRecord.id)
            .offset(offset)
            .limit(limit + 1)
        ).all()
        has_more = len(tasks) > limit
        return {"items": [admin_task_view(task) for task in tasks[:limit]], "has_more": has_more}

    @app.post("/api/bot/workflows/{task_id}/decision")
    async def decide_bot_workflow(
        task_id: str,
        request: Request,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        payload = await _read_json_object(request, 2048)
        if set(payload) != {"bale_user_id", "decision", "reason", "expected_version"}:
            raise HTTPException(400, "invalid_workflow_decision")
        raw_user_id = payload.get("bale_user_id")
        if isinstance(raw_user_id, bool) or not isinstance(raw_user_id, (str, int)):
            raise HTTPException(422, "invalid_bale_user_id")
        bale_user_id = str(raw_user_id)
        if not re.fullmatch(r"[1-9][0-9]{0,19}", bale_user_id):
            raise HTTPException(422, "invalid_bale_user_id")
        decision = payload.get("decision")
        reason = payload.get("reason")
        expected_version = payload.get("expected_version")
        if decision not in {"approved", "rejected"} or not isinstance(reason, str) or len(reason) > 500:
            raise HTTPException(422, "invalid_workflow_decision")
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 1:
            raise HTTPException(422, "invalid_workflow_version")
        task = db.get(AdminTaskRecord, task_id)
        if task is None:
            raise HTTPException(404, "workflow_not_found")
        cfg: Settings = request.app.state.settings
        account_id, role = bot_account_identity(db, cfg, bale_user_id)
        if role is None or not has_permission(role, workflow_permission(task.kind)):
            raise HTTPException(403, "permission_denied")
        if task.status != "pending" or task.version != expected_version:
            raise HTTPException(409, "workflow_version_conflict")
        reviewer_id = cfg.owner_id if role == ROLE_OWNER else str(account_id)
        apply_admin_task_decision(db, task, decision, reason.strip(), reviewer_id, bale_user_id)
        db.commit()
        return {"task": admin_task_view(db.get(AdminTaskRecord, task.id)), "accepted": True}

    @app.get("/api/bot/notifications/pending")
    def bot_pending_notifications(
        limit: int = Query(default=50, ge=1, le=100),
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        items = db.scalars(
            select(UserNotificationRecord)
            .where(
                UserNotificationRecord.delivery_status == "pending",
                # Rows without a Bale destination (web-only accounts) are never handed to the bot.
                UserNotificationRecord.bale_user_id != "",
            )
            .order_by(UserNotificationRecord.created_at.asc(), UserNotificationRecord.id)
            .limit(limit)
        ).all()
        return {"items": [user_notification_view(item) for item in items]}

    @app.get("/api/bot/notifications")
    def bot_notification_queue(
        bale_user_id: str = Query(..., min_length=1, max_length=20),
        limit: int = Query(default=30, ge=1, le=100),
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        if not re.fullmatch(r"[1-9][0-9]{0,19}", bale_user_id):
            raise HTTPException(422, "invalid_bale_user_id")
        identity = db.scalar(
            select(PlatformIdentityRecord).where(
                PlatformIdentityRecord.provider == "bale",
                PlatformIdentityRecord.provider_user_id == bale_user_id,
            )
        )
        if identity is None:
            return {"items": []}
        items = db.scalars(
            select(UserNotificationRecord)
            .where(
                UserNotificationRecord.account_id == identity.account_id,
                UserNotificationRecord.delivery_status == "pending",
            )
            .order_by(UserNotificationRecord.created_at.asc(), UserNotificationRecord.id)
            .limit(limit)
        ).all()
        return {"items": [user_notification_view(item) for item in items]}

    @app.post("/api/bot/notifications/{notification_id}/delivered")
    async def mark_bot_notification_delivered(
        notification_id: str,
        request: Request,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        payload = await _read_json_object(request, 1024)
        if set(payload) != {"bale_user_id"}:
            raise HTTPException(400, "invalid_notification_delivery")
        bale_user_id = str(payload.get("bale_user_id", ""))
        if not re.fullmatch(r"[1-9][0-9]{0,19}", bale_user_id):
            raise HTTPException(422, "invalid_bale_user_id")
        identity = db.scalar(
            select(PlatformIdentityRecord).where(
                PlatformIdentityRecord.provider == "bale",
                PlatformIdentityRecord.provider_user_id == bale_user_id,
            )
        )
        if identity is None:
            raise HTTPException(404, "account_not_found")
        item = db.get(UserNotificationRecord, notification_id)
        if item is None or item.account_id != identity.account_id:
            raise HTTPException(404, "notification_not_found")
        if item.delivery_status != "delivered":
            item.delivery_status = "delivered"
            item.delivery_attempts += 1
            item.delivered_at = _utc_now()
            item.last_delivery_error = None
            db.commit()
        return {"delivered": True}

    @app.post("/api/bot/notifications/{notification_id}/delivery-failed")
    async def mark_bot_notification_failed(
        notification_id: str,
        request: Request,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        payload = await _read_json_object(request, 1024)
        if set(payload) != {"bale_user_id"}:
            raise HTTPException(400, "invalid_notification_delivery")
        bale_user_id = str(payload.get("bale_user_id", ""))
        if not re.fullmatch(r"[1-9][0-9]{0,19}", bale_user_id):
            raise HTTPException(422, "invalid_bale_user_id")
        identity = db.scalar(
            select(PlatformIdentityRecord).where(
                PlatformIdentityRecord.provider == "bale",
                PlatformIdentityRecord.provider_user_id == bale_user_id,
            )
        )
        if identity is None:
            raise HTTPException(404, "account_not_found")
        item = db.get(UserNotificationRecord, notification_id)
        if item is None or item.account_id != identity.account_id:
            raise HTTPException(404, "notification_not_found")
        if item.delivery_status == "pending":
            item.delivery_attempts += 1
            item.last_delivery_error = "provider_delivery_failed"
            if item.delivery_attempts >= 5:
                item.delivery_status = "failed"
            db.commit()
        return {"recorded": True, "delivery_status": item.delivery_status}

    @app.get("/api/account/notifications")
    def account_notifications(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        identity: AccountIdentity = Depends(require_account),
        db: Session = Depends(get_db),
    ):
        items = db.scalars(
            select(UserNotificationRecord)
            .where(UserNotificationRecord.account_id == identity.account_id)
            .order_by(UserNotificationRecord.created_at.desc(), UserNotificationRecord.id)
            .offset(offset)
            .limit(limit + 1)
        ).all()
        return {"items": [user_notification_view(item) for item in items[:limit]], "has_more": len(items) > limit}

    @app.post("/api/account/notifications/{notification_id}/read")
    def mark_account_notification_read(
        notification_id: str,
        identity: AccountIdentity = Depends(require_account_write),
        db: Session = Depends(get_db),
    ):
        item = db.get(UserNotificationRecord, notification_id)
        if item is None or item.account_id != identity.account_id:
            raise HTTPException(404, "notification_not_found")
        if item.read_at is None:
            item.read_at = _utc_now()
            db.commit()
        return {"read": True}

    @app.get("/api/account/files")
    def account_private_files(
        response: Response,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        identity: AccountIdentity = Depends(require_account),
        db: Session = Depends(get_db),
    ):
        items = db.scalars(
            select(PrivateFileRecord)
            .where(PrivateFileRecord.account_id == identity.account_id)
            .order_by(PrivateFileRecord.created_at.desc(), PrivateFileRecord.id)
            .offset(offset)
            .limit(limit + 1)
        ).all()
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Cookie"
        return {
            "items": [
                {
                    "id": item.id,
                    "task_id": item.task_id,
                    "file_name": item.file_name,
                    "content_type": item.content_type,
                    "content_size": item.content_size,
                    "created_at": _as_utc(item.created_at).isoformat(),
                }
                for item in items[:limit]
            ],
            "has_more": len(items) > limit,
        }

    @app.get("/api/account/certificates")
    def account_certificates(
        response: Response,
        identity: AccountIdentity = Depends(require_account),
        db: Session = Depends(get_db),
    ):
        """«گواهینامه‌های من»: only rows the bot mirrored for this account; files come from the bot."""
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Cookie"
        result = certificates_mod.account_records(
            db, identity.account_id, today_jalali=certificates_mod.today_jalali(),
        )
        result["source"] = certificates_mod.SOURCE
        return result

    @app.get("/api/account/files/{file_id}")
    def account_private_file(
        file_id: str,
        identity: AccountIdentity = Depends(require_account),
        db: Session = Depends(get_db),
    ):
        item = db.get(PrivateFileRecord, file_id)
        if item is None or item.account_id != identity.account_id:
            raise HTTPException(404, "private_file_not_found")
        raise HTTPException(410, "file_delivery_via_bale_bot")

    @app.get("/api/admin/reports/summary")
    def admin_reports_summary(
        response: Response,
        period: str = Query(default="30d"),
        identity: OwnerIdentity | AccountIdentity = Depends(require_permission("rp_view")),
        db: Session = Depends(get_db),
    ):
        """Aggregate only data already stored in the shared server database."""
        if period not in {"7d", "30d", "90d", "365d", "all"}:
            raise HTTPException(422, "invalid_report_period")
        role = ROLE_OWNER if isinstance(identity, OwnerIdentity) else identity.role
        response.headers["Cache-Control"] = "private, no-store"
        return admin_reports_summary_data(db, role, period)

    @app.get("/api/admin/integrity/recordings")
    def admin_recording_integrity(
        response: Response,
        _identity: OwnerIdentity | AccountIdentity = Depends(require_permission("rp_view")),
        db: Session = Depends(get_db),
    ):
        """Phase 9.5 §3: read-only purchase-chain audit (form → response → payment → ledger → access).

        Same report as ``tools/recording-access-audit.py``; ids only, never fixes anything.
        """
        response.headers["Cache-Control"] = "no-store"
        return integrity_mod.run(db, _utc_now())

    @app.get("/api/admin/notifications")
    def admin_notifications(
        response: Response,
        state: str = Query(default=""),
        kind: str = Query(default=""),
        limit: int = Query(default=30, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        _identity: OwnerIdentity | AccountIdentity = Depends(require_permission("rp_view")),
        db: Session = Depends(get_db),
    ):
        """Phase 9.4 §8: global outbox view for the panel — queue / retrying / delivered / failed / no-Bale.

        Read-only, ``rp_view`` (same permission as the reports tab). Shows what the server knows:
        recorded ≠ sent ≠ delivered; ``no_bale_identity`` is a distinct, non-network state. Bodies
        never contain private file URLs (enforced at write time), so nothing here leaks access.
        """
        response.headers["Cache-Control"] = "private, no-store"
        if state not in {"", "queued", "retrying", "delivered", "failed", "no_bale_identity"}:
            raise HTTPException(422, "invalid_notification_state")
        if kind and not re.fullmatch(r"[a-z_]{1,40}", kind):
            raise HTTPException(422, "invalid_notification_kind")
        query = select(UserNotificationRecord)
        if kind:
            query = query.where(UserNotificationRecord.kind == kind)
        if state == "queued":
            query = query.where(UserNotificationRecord.delivery_status == "pending", UserNotificationRecord.delivery_attempts == 0)
        elif state == "retrying":
            query = query.where(UserNotificationRecord.delivery_status == "pending", UserNotificationRecord.delivery_attempts > 0)
        elif state == "delivered":
            query = query.where(UserNotificationRecord.delivery_status == "delivered")
        elif state == "failed":
            query = query.where(UserNotificationRecord.delivery_status == "failed", UserNotificationRecord.last_delivery_error != "no_bale_identity")
        elif state == "no_bale_identity":
            query = query.where(UserNotificationRecord.last_delivery_error == "no_bale_identity")
        rows = db.scalars(
            query.order_by(UserNotificationRecord.created_at.desc(), UserNotificationRecord.id).offset(offset).limit(limit + 1)
        ).all()
        counts_rows = db.execute(
            select(UserNotificationRecord.delivery_status, UserNotificationRecord.last_delivery_error, func.count())
            .group_by(UserNotificationRecord.delivery_status, UserNotificationRecord.last_delivery_error)
        ).all()
        counts = {"queued": 0, "retrying": 0, "delivered": 0, "failed": 0, "no_bale_identity": 0}
        retrying = db.scalar(
            select(func.count()).select_from(UserNotificationRecord).where(
                UserNotificationRecord.delivery_status == "pending", UserNotificationRecord.delivery_attempts > 0,
            )
        ) or 0
        for status, error, count in counts_rows:
            if status == "pending":
                counts["queued"] += int(count)
            elif status == "delivered":
                counts["delivered"] += int(count)
            elif error == "no_bale_identity":
                counts["no_bale_identity"] += int(count)
            else:
                counts["failed"] += int(count)
        counts["queued"] -= int(retrying)
        counts["retrying"] = int(retrying)
        items = []
        for row in rows[:limit]:
            view = user_notification_view(row)
            view["account_id"] = row.account_id
            view["account_label"] = _interaction_display_name(db, row.account_id)
            view["has_bale_identity"] = bool(row.bale_user_id)
            view["dedupe_key"] = row.dedupe_key
            view.pop("bale_user_id", None)  # the panel needs the state, not the raw Bale id
            items.append(view)
        return {"source": "shared_server_database", "items": items, "has_more": len(rows) > limit, "counts": counts,
                "limit": limit, "offset": offset}

    @app.post("/api/admin/notifications/{notification_id}/retry")
    def admin_retry_notification(
        notification_id: str,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write("ev_publish")),
        db: Session = Depends(get_db),
    ):
        """Phase 9.5 §8: re-queue a *failed* outbox row — the same row, never a second one.

        The Bale target is re-resolved from the server-side identity table, so a ``no_bale_identity``
        row becomes deliverable only if the account has linked Bale since; otherwise 409 with the
        same honest code. Delivered rows are never touched. Audited with actor and previous state.
        """
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", notification_id):
            raise HTTPException(404, {"code": "notification_not_found"})
        item = db.get(UserNotificationRecord, notification_id)
        if item is None:
            raise HTTPException(404, {"code": "notification_not_found"})
        if item.delivery_status == "delivered":
            raise HTTPException(409, {"code": "already_delivered"})
        if item.delivery_status != "failed":
            raise HTTPException(409, {"code": "notification_not_failed", "state": interaction_mod.delivery_state(item.delivery_status, item.delivery_attempts)})
        if item.kind == event_reminders_mod.KIND and item.last_delivery_error == event_reminders_mod.STALE_ERROR:
            # B19: a reminder withdrawn because the event moved/was cancelled must never be sent later.
            raise HTTPException(409, {"code": "reminder_superseded"})
        bale_ids = verified_bale_ids_for_account(db, item.account_id)
        if not bale_ids:
            raise HTTPException(409, {"code": "no_bale_identity"})
        previous_attempts, previous_error = item.delivery_attempts, (item.last_delivery_error or "")[:80]
        item.bale_user_id = str(bale_ids[0])
        item.delivery_status = "pending"
        item.delivery_attempts = 0
        item.last_delivery_error = None
        record_audit(
            db, identity, "notification.retry", target_type="user_notification", target_id=item.id,
            details={"kind": item.kind, "previous_attempts": previous_attempts, "previous_error": previous_error},
        )
        db.commit()
        db.refresh(item)
        view = user_notification_view(item)
        view.pop("bale_user_id", None)
        view["has_bale_identity"] = True
        view["account_id"] = item.account_id
        return view

    @app.get("/api/admin/scheduled-publish")
    def admin_scheduled_publish_state(
        response: Response,
        _identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission("rp_view")),
        db: Session = Depends(get_db),
    ):
        """Phase 9.5 §8.2: last scheduler run (marker) + how many scheduled rows wait. Read-only."""
        response.headers["Cache-Control"] = "private, no-store"
        now = _utc_now()
        marker = db.get(SystemMarkerRecord, scheduled_publish_mod.MARKER_KEY)
        return {
            "now": now.isoformat(),
            "last_run": ({"at": interaction_mod.iso(marker.updated_at), **(marker.value if isinstance(marker.value, dict) else {})}
                         if marker is not None else None),
            "pending": scheduled_publish_mod.pending_count(db, now),
            "runner": "systemd timer or manual run; the web process does not run a background scheduler",
        }

    @app.post("/api/admin/scheduled-publish/run")
    def admin_scheduled_publish_run(
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write("ev_publish")),
        db: Session = Depends(get_db),
    ):
        """Run one announcement pass now (same function as the timer); idempotent; audited."""
        actor_kind, actor_id = _interaction_actor(identity)
        summary = scheduled_publish_mod.announce_due(db, _utc_now(), actor=f"{actor_kind}:{actor_id}"[:40])
        record_audit(
            db, identity, "scheduled_publish.run", target_type="system_marker", target_id=scheduled_publish_mod.MARKER_KEY,
            details={"due": summary["due"], "announced": summary["announced"], "notified": summary["notified"],
                     "skipped": summary["skipped"], "ok": summary["ok"],
                     "reminders_queued": int((summary.get("reminders") or {}).get("queued") or 0),
                     "reminders_withdrawn": int((summary.get("reminders") or {}).get("withdrawn") or 0)},
        )
        db.commit()
        return summary

    @app.post("/api/bot/reports/summary")
    async def bot_admin_reports_summary(
        request: Request,
        response: Response,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        """Server-to-server aggregate; authorize the Bale user against DB roles."""
        payload = await _read_json_object(request, 1024)
        if set(payload) != {"bale_user_id", "period"}:
            raise HTTPException(400, "invalid_bot_report_request")
        raw_user_id = payload.get("bale_user_id")
        if isinstance(raw_user_id, bool) or not isinstance(raw_user_id, (str, int)):
            raise HTTPException(422, "invalid_bale_user_id")
        bale_user_id = str(raw_user_id)
        if not re.fullmatch(r"[1-9][0-9]{0,19}", bale_user_id):
            raise HTTPException(422, "invalid_bale_user_id")
        period = payload.get("period")
        if not isinstance(period, str):
            raise HTTPException(422, "invalid_report_period")

        cfg: Settings = request.app.state.settings
        _account_id, role = bot_account_identity(db, cfg, bale_user_id)
        if not has_permission(role, "rp_view"):
            raise HTTPException(403, "permission_denied")
        response.headers["Cache-Control"] = "private, no-store"
        return admin_reports_summary_data(db, role, period)

    @app.get("/api/admin/inbox")
    def admin_workflow_inbox(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        status: str = Query(default="pending", pattern=r"^(pending|decided|approved|rejected)$"),
        identity: OwnerIdentity | AccountIdentity = Depends(
            require_any_permission("us_approve", "receipt_approve")
        ),
        db: Session = Depends(get_db),
    ):
        """Shared review inbox. ``status=pending`` (default) lists open work; the
        other values expose the decision history (who decided what, when)."""
        role = ROLE_OWNER if isinstance(identity, OwnerIdentity) else identity.role
        kinds = [kind for kind in ("profile_review", "receipt_review") if has_permission(role, workflow_permission(kind))]
        statuses = ("approved", "rejected") if status == "decided" else (status,)
        query = select(AdminTaskRecord).where(
            AdminTaskRecord.status.in_(statuses), AdminTaskRecord.kind.in_(kinds)
        )
        if status == "pending":
            query = query.order_by(AdminTaskRecord.created_at.asc(), AdminTaskRecord.id)
        else:
            query = query.order_by(AdminTaskRecord.reviewed_at.desc(), AdminTaskRecord.id)
        tasks = db.scalars(query.offset(offset).limit(limit + 1)).all()
        return {
            "items": admin_inbox_task_views(db, tasks[:limit]),
            "has_more": len(tasks) > limit,
            "status": status,
        }

    @app.get("/api/admin/inbox/{task_id}/files/{file_id}")
    def admin_workflow_file(
        task_id: str,
        file_id: str,
        identity: OwnerIdentity | AccountIdentity = Depends(
            require_any_permission("us_approve", "receipt_approve")
        ),
        db: Session = Depends(get_db),
    ):
        task = db.get(AdminTaskRecord, task_id)
        if task is None:
            raise HTTPException(404, "workflow_not_found")
        role = ROLE_OWNER if isinstance(identity, OwnerIdentity) else identity.role
        if not has_permission(role, workflow_permission(task.kind)):
            raise HTTPException(403, "permission_denied")
        if file_id not in ((task.payload or {}).get("file_refs") or []):
            raise HTTPException(404, "private_file_not_found")
        item = db.get(PrivateFileRecord, file_id)
        if item is None or item.account_id != task.account_id or item.task_id != task.id:
            raise HTTPException(404, "private_file_not_found")
        disposition = "inline" if item.content_type.startswith("image/") else "attachment"
        filename = re.sub(r"[^A-Za-z0-9._-]", "_", item.file_name)[:80] or "attachment"
        return Response(
            content=item.content,
            media_type=item.content_type,
            headers={
                "Content-Disposition": f'{disposition}; filename="{filename}"',
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; sandbox",
            },
        )

    @app.post("/api/admin/inbox/{task_id}/decision")
    async def decide_admin_workflow(
        task_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(
            require_any_permission_write("us_approve", "receipt_approve")
        ),
        db: Session = Depends(get_db),
    ):
        payload = await _read_json_object(request, 2048)
        if set(payload) != {"decision", "reason", "expected_version"}:
            raise HTTPException(400, "invalid_workflow_decision")
        decision = payload.get("decision")
        reason = payload.get("reason")
        expected_version = payload.get("expected_version")
        if decision not in {"approved", "rejected"} or not isinstance(reason, str) or len(reason) > 500:
            raise HTTPException(422, "invalid_workflow_decision")
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version < 1:
            raise HTTPException(422, "invalid_workflow_version")
        task = db.get(AdminTaskRecord, task_id)
        if task is None:
            raise HTTPException(404, "workflow_not_found")
        role = ROLE_OWNER if isinstance(identity, OwnerIdentity) else identity.role
        if not has_permission(role, workflow_permission(task.kind)):
            raise HTTPException(403, "permission_denied")
        if task.status != "pending" or task.version != expected_version:
            raise HTTPException(409, "workflow_version_conflict")
        if task.kind == "receipt_review" and len(reason.strip()) < 2:
            # A receipt decision moves money/access state; it is only accepted with a stated, audited reason
            # (the panel asks for confirmation + reason, but the rule lives here).
            raise HTTPException(422, "receipt_decision_reason_required")
        reviewer_id = identity.owner_id if isinstance(identity, OwnerIdentity) else identity.account_id
        reviewer_bale_id = None
        if isinstance(identity, AccountIdentity):
            reviewer_bale_id = db.scalar(
                select(PlatformIdentityRecord.provider_user_id).where(
                    PlatformIdentityRecord.account_id == identity.account_id,
                    PlatformIdentityRecord.provider == "bale",
                )
            )
        apply_admin_task_decision(db, task, decision, reason.strip(), reviewer_id, reviewer_bale_id)
        record_audit(
            db, identity, "workflow.decide", target_type="admin_task", target_id=task.id,
            details={"kind": task.kind, "decision": decision, "has_reason": bool(reason.strip())},
        )
        db.commit()
        refreshed = db.get(AdminTaskRecord, task.id)
        if refreshed is None:
            raise HTTPException(404, "admin_task_not_found")
        return {"task": admin_inbox_task_views(db, [refreshed])[0], "accepted": True}

    @app.get("/api/owner/audit")
    def list_owner_audit_events(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        action: str = Query(default="", max_length=64, pattern=r"^[a-z_.]*$"),
        # ``content.events`` / ``content.people``: dotted target types are the per-record history
        # (owner decision 1405/08/01); the dot was previously rejected, which hid them from the filter.
        target_type: str = Query(default="", max_length=32, pattern=r"^[a-z_.]*$"),
        target_id: str = Query(default="", max_length=120, pattern=r"^[A-Za-z0-9_.:-]*$"),
        _identity: OwnerIdentity = Depends(require_owner),
        db: Session = Depends(get_db),
    ):
        """Owner-only, read-only view of the administrative audit trail."""
        rows, has_more = audit_mod.list_admin_events(
            db, limit=limit, offset=offset, action=action, target_type=target_type, target_id=target_id
        )
        return {
            "items": [audit_mod.audit_event_view(row) for row in rows],
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
            "actions": sorted(audit_mod.ACTIONS),
        }

    @app.get("/api/owner/accounts")
    def list_account_roles(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        q: str = Query(default="", max_length=80),
        role_filter: str = Query(default="", alias="role", pattern=r"^(|assigned|manager|club-supervisor|none)$"),
        _identity: OwnerIdentity = Depends(require_owner),
        db: Session = Depends(get_db),
    ):
        """Verified accounts with their server role.

        Phone numbers are stored only as a peppered digest, so the owner identifies
        an account by the member's own profile name (``display_name``), the Bale id,
        the manager username or the account id prefix. ``q`` matches those fields.
        """
        query = (
            select(AccountRecord, PlatformIdentityRecord, AccountRoleRecord, ManagerCredentialRecord, AccountProfileRecord)
            .join(PlatformIdentityRecord, PlatformIdentityRecord.account_id == AccountRecord.id)
            .outerjoin(AccountRoleRecord, AccountRoleRecord.account_id == AccountRecord.id)
            .outerjoin(ManagerCredentialRecord, ManagerCredentialRecord.account_id == AccountRecord.id)
            .outerjoin(AccountProfileRecord, AccountProfileRecord.account_id == AccountRecord.id)
            .where(PlatformIdentityRecord.provider.in_(("bale", "phone")))
        )
        if role_filter == "assigned":
            query = query.where(AccountRoleRecord.role.is_not(None))
        elif role_filter == "none":
            query = query.where(AccountRoleRecord.role.is_(None))
        elif role_filter:
            query = query.where(AccountRoleRecord.role == role_filter)
        needle = unicodedata.normalize("NFKC", q or "").strip().lower()
        if needle:
            # Profile names live inside JSON; filter in Python over a bounded window
            # so the search stays dialect-agnostic (SQLite + PostgreSQL).
            candidates = db.execute(
                query.order_by(AccountRecord.created_at.desc(), AccountRecord.id).limit(2000)
            ).all()
            def _matches(row: Any) -> bool:
                account, identity, role, credential, profile = row
                name = str(((profile.fields if profile is not None else {}) or {}).get("fullName") or "")
                haystack = " ".join(
                    part for part in (
                        unicodedata.normalize("NFKC", name).lower(),
                        identity.provider_user_id.lower() if identity.provider == "bale" else "",
                        (credential.username_key if credential is not None else ""),
                        account.id.lower(),
                    ) if part
                )
                return needle in haystack
            filtered = [row for row in candidates if _matches(row)]
            records = filtered[offset: offset + limit + 1]
        else:
            records = list(db.execute(
                query.order_by(AccountRecord.created_at.desc(), AccountRecord.id)
                .offset(offset)
                .limit(limit + 1)
            ).all())
        has_more = len(records) > limit
        items = [
            {
                "account_id": account.id,
                "provider": identity.provider,
                "provider_user_id": (
                    identity.provider_user_id
                    if identity.provider == "bale"
                    else "OTP-" + identity.provider_user_id[:8]
                ),
                "display_name": str(((profile.fields if profile is not None else {}) or {}).get("fullName") or "")[:120],
                "role": role.role if role is not None else None,
                "permissions": sorted(permissions_for_role(role.role if role is not None else None)),
                "manager_username": credential.username_key if credential is not None else None,
                "manager_login_enabled": credential is not None,
                "created_at": _as_utc(account.created_at).isoformat(),
            }
            for account, identity, role, credential, profile in records[:limit]
        ]
        return {"items": items, "limit": limit, "offset": offset, "has_more": has_more, "q": q}

    @app.put("/api/owner/accounts/{account_id}/role")
    async def set_account_role(
        account_id: str,
        request: Request,
        _identity: OwnerIdentity = Depends(require_owner_write),
        db: Session = Depends(get_db),
    ):
        payload = await _read_json_object(request, 4096)
        if set(payload) != {"role"}:
            raise HTTPException(400, "invalid_role_payload")
        role = payload["role"]
        if role is not None and not is_assignable_role(role):
            raise HTTPException(422, "invalid_account_role")
        account = db.get(AccountRecord, account_id)
        if account is None:
            raise HTTPException(404, "account_not_found")
        current = db.get(AccountRoleRecord, account_id)
        previous_role = current.role if current is not None else None
        if role is None:
            if current is not None:
                db.delete(current)
            credential = db.get(ManagerCredentialRecord, account_id)
            if credential is not None:
                db.delete(credential)
            _revoke_manager_password_sessions(db, account_id, _utc_now())
        elif current is None:
            db.add(AccountRoleRecord(account_id=account_id, role=role, assigned_by=_identity.owner_id))
        else:
            current.role = role
            current.assigned_by = _identity.owner_id
            current.updated_at = _utc_now()
        record_audit(
            db, _identity, "role.clear" if role is None else "role.set",
            target_type="account", target_id=account_id,
            details={"previous_role": previous_role, "role": role},
        )
        db.commit()
        return {
            "account_id": account_id,
            "role": role,
            "permissions": sorted(permissions_for_role(role)),
        }

    @app.put("/api/owner/accounts/{account_id}/status")
    async def set_account_status(
        account_id: str,
        request: Request,
        _identity: OwnerIdentity = Depends(require_owner_write),
        db: Session = Depends(get_db),
    ):
        """Owner decision 1405/08/01: block (reason mandatory) / re-activate an account.

        The owner's own account (the Bale identity configured as ``owner_bale_user_id``) can never
        be blocked; blocking revokes every open session of the account; both directions are audited
        with actor, time and reason.
        """
        payload = await _read_json_object(request, 4096)
        if not set(payload) <= {"status", "reason"} or "status" not in payload:
            raise HTTPException(400, "invalid_account_status_payload")
        status = payload.get("status")
        if status not in ACCOUNT_STATUSES:
            raise HTTPException(422, {"code": "invalid_account_status", "field": "status"})
        reason_raw = payload.get("reason", "")
        if reason_raw is not None and not isinstance(reason_raw, str):
            raise HTTPException(422, {"code": "invalid_block_reason", "field": "reason"})
        reason = " ".join(str(reason_raw or "").split())
        if status == ACCOUNT_STATUS_BLOCKED and len(reason) < _BLOCK_REASON_MIN:
            raise HTTPException(422, {"code": "block_reason_required", "field": "reason", "min": _BLOCK_REASON_MIN})
        if len(reason) > _BLOCK_REASON_MAX:
            raise HTTPException(422, {"code": "block_reason_too_long", "field": "reason", "max": _BLOCK_REASON_MAX})
        account = db.get(AccountRecord, account_id)
        if account is None:
            raise HTTPException(404, "account_not_found")
        cfg: Settings = request.app.state.settings
        if status == ACCOUNT_STATUS_BLOCKED and cfg.owner_bale_user_id and db.scalar(
            select(PlatformIdentityRecord.id).where(
                PlatformIdentityRecord.account_id == account_id,
                PlatformIdentityRecord.provider == "bale",
                PlatformIdentityRecord.provider_user_id == cfg.owner_bale_user_id,
            )
        ) is not None:
            raise HTTPException(409, {"code": "owner_account_protected"})
        previous = account.status or ACCOUNT_STATUS_ACTIVE
        now = _utc_now()
        revoked = 0
        if previous != status:
            if status == ACCOUNT_STATUS_BLOCKED:
                account.status = ACCOUNT_STATUS_BLOCKED
                account.blocked_reason = reason
                account.blocked_at = now
                account.blocked_by = _identity.owner_id
                revoked = _revoke_all_account_sessions(db, account_id, now)
                record_audit(
                    db, _identity, "account.block", target_type="account", target_id=account_id,
                    details={"previous_status": previous, "status": status, "reason": reason, "sessions_revoked": revoked},
                )
            else:
                previous_reason = account.blocked_reason or ""
                account.status = ACCOUNT_STATUS_ACTIVE
                account.blocked_reason = ""
                account.blocked_at = None
                account.blocked_by = ""
                record_audit(
                    db, _identity, "account.unblock", target_type="account", target_id=account_id,
                    details={"previous_status": previous, "status": status, "reason": reason, "previous_reason": previous_reason},
                )
            db.commit()
            db.refresh(account)
        return {"account_id": account_id, "changed": previous != status, "sessions_revoked": revoked, **_account_status_view(account)}

    @app.put("/api/admin/users/{account_id}/note")
    async def set_account_internal_note(
        account_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission_write("us_notes")),
        db: Session = Depends(get_db),
    ):
        """Staff-only internal note: read with ``us_view``, write with the catalogue's own
        ``us_notes`` («یادداشت روی پرونده»); distinct from the block reason; never member-facing.

        The audit row records only the note length, never its text.
        """
        payload = await _read_json_object(request, 16384)
        if set(payload) != {"note"}:
            raise HTTPException(400, "invalid_note_payload")
        note_raw = payload.get("note")
        if note_raw is not None and not isinstance(note_raw, str):
            raise HTTPException(422, {"code": "invalid_note", "field": "note"})
        note = str(note_raw or "").replace("\r\n", "\n").strip()
        if len(note) > _INTERNAL_NOTE_MAX:
            raise HTTPException(422, {"code": "note_too_long", "field": "note", "max": _INTERNAL_NOTE_MAX})
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", account_id or ""):
            raise HTTPException(404, "user_not_found")
        account = db.get(AccountRecord, account_id)
        if account is None or not db.scalar(
            select(PlatformIdentityRecord.id).where(
                PlatformIdentityRecord.account_id == account_id,
                PlatformIdentityRecord.provider.in_(("bale", "phone")),
            )
        ):
            raise HTTPException(404, "user_not_found")
        actor = identity.owner_id if isinstance(identity, OwnerIdentity) else identity.account_id
        changed = (account.internal_note or "") != note
        if changed:
            account.internal_note = note
            account.note_updated_at = _utc_now()
            account.note_updated_by = actor
            record_audit(
                db, identity, "account.note", target_type="account", target_id=account_id,
                details={"length": len(note), "cleared": not note},
            )
            db.commit()
            db.refresh(account)
        return {"account_id": account_id, "changed": changed, **_account_status_view(account)}

    @app.put("/api/owner/accounts/{account_id}/manager-credentials")
    async def set_manager_credentials(
        account_id: str,
        request: Request,
        _identity: OwnerIdentity = Depends(require_owner_write),
        db: Session = Depends(get_db),
    ):
        payload = await _read_json_object(request, 4096)
        if set(payload) != {"username", "password"}:
            raise HTTPException(400, "invalid_manager_credentials_payload")
        username_key = _manager_username_key(payload.get("username"))
        if username_key is None:
            raise HTTPException(422, "invalid_manager_username")
        cfg: Settings = request.app.state.settings
        if username_key == cfg.owner_username.strip().lower():
            raise HTTPException(422, "manager_username_reserved")
        password = payload.get("password")
        if not isinstance(password, str):
            raise HTTPException(422, "invalid_manager_password")
        try:
            password_size = len(password.encode("utf-8", errors="strict"))
        except UnicodeError:
            raise HTTPException(422, "invalid_manager_password") from None
        if not 12 <= password_size <= 1024:
            raise HTTPException(422, "invalid_manager_password")

        account = db.get(AccountRecord, account_id)
        if account is None:
            raise HTTPException(404, "account_not_found")
        role_record = db.get(AccountRoleRecord, account_id)
        if role_record is None or role_record.role not in {"manager", "club-supervisor"}:
            raise HTTPException(409, "manager_role_required")
        username_taken = db.scalar(
            select(ManagerCredentialRecord.account_id).where(
                ManagerCredentialRecord.username_key == username_key,
                ManagerCredentialRecord.account_id != account_id,
            )
        )
        if username_taken is not None:
            raise HTTPException(409, "manager_username_taken")

        credential = db.get(ManagerCredentialRecord, account_id)
        replaced = credential is not None
        encoded_password = hash_password(password)
        if credential is None:
            credential = ManagerCredentialRecord(
                account_id=account_id,
                username_key=username_key,
                password_hash=encoded_password,
            )
            db.add(credential)
        else:
            credential.username_key = username_key
            credential.password_hash = encoded_password
            credential.updated_at = _utc_now()
        _revoke_manager_password_sessions(db, account_id, _utc_now())
        record_audit(
            db, _identity, "manager_credentials.set", target_type="account", target_id=account_id,
            details={"username": username_key, "replaced": replaced},
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "manager_username_taken") from None
        return {
            "account_id": account_id,
            "username": credential.username_key,
            "configured": True,
        }

    @app.delete("/api/owner/accounts/{account_id}/manager-credentials")
    def remove_manager_credentials(
        account_id: str,
        _identity: OwnerIdentity = Depends(require_owner_write),
        db: Session = Depends(get_db),
    ):
        if db.get(AccountRecord, account_id) is None:
            raise HTTPException(404, "account_not_found")
        credential = db.get(ManagerCredentialRecord, account_id)
        if credential is not None:
            db.delete(credential)
        _revoke_manager_password_sessions(db, account_id, _utc_now())
        record_audit(
            db, _identity, "manager_credentials.remove", target_type="account", target_id=account_id,
            details={"had_login": credential is not None},
        )
        db.commit()
        return {"account_id": account_id, "configured": False}

    @app.post("/api/auth/account/logout")
    def account_logout(
        request: Request,
        response: Response,
        identity: AccountIdentity = Depends(require_account_write),
        db: Session = Depends(get_db),
    ):
        record = db.get(AccountSessionRecord, identity.session_id)
        if record and record.revoked_at is None:
            record.revoked_at = _utc_now()
            db.commit()
        cfg: Settings = request.app.state.settings
        response.delete_cookie(
            cfg.account_cookie_name,
            path="/",
            secure=cfg.cookie_secure,
            httponly=True,
            samesite=_samesite(cfg),
        )
        response.delete_cookie(
            cfg.account_csrf_cookie_name,
            path="/",
            secure=cfg.cookie_secure,
            httponly=False,
            samesite=_samesite(cfg),
        )
        return {"authenticated": False}

    @app.get("/api/cooperation-requests")
    def list_cooperation_requests(
        limit: int = 50,
        offset: int = 0,
        _identity: OwnerIdentity = Depends(require_owner),
        db: Session = Depends(get_db),
    ):
        page_size = max(1, min(100, limit))
        start = max(0, min(1_000_000, offset))
        records = db.scalars(
            select(CooperationRequestRecord)
            .order_by(CooperationRequestRecord.created_at.desc(), CooperationRequestRecord.id.desc())
            .limit(page_size)
            .offset(start)
        ).all()
        total = db.scalar(select(func.count(CooperationRequestRecord.id))) or 0
        return {
            "items": [_cooperation_request_dict(record) for record in records],
            "total": int(total),
            "limit": page_size,
            "offset": start,
        }

    @app.patch("/api/cooperation-requests/{request_id}")
    async def update_cooperation_request(
        request_id: str,
        request: Request,
        _identity: OwnerIdentity = Depends(require_owner_write),
        db: Session = Depends(get_db),
    ):
        payload = await _read_json_object(request, request.app.state.settings.max_request_bytes)
        if set(payload) != {"status"} or payload.get("status") not in {
            "new", "reviewing", "contacted", "closed"
        }:
            raise HTTPException(422, "invalid_cooperation_status")
        record = db.get(CooperationRequestRecord, request_id)
        if record is None:
            raise HTTPException(404, "cooperation_request_not_found")
        previous_status = record.status
        record.status = payload["status"]
        record.updated_at = _utc_now()
        record_audit(
            db, _identity, "cooperation_request.update", target_type="cooperation_request",
            target_id=record.id, details={"from_status": previous_status, "status": record.status},
        )
        db.commit()
        return {"id": record.id, "status": record.status}

    @app.get("/api/forms")
    def list_forms(
        identity: OwnerIdentity | AccountIdentity = Depends(require_any_permission("fm_create", "fm_responses")),
        db: Session = Depends(get_db),
    ):
        records = db.scalars(
            select(FormRecord)
            .options(selectinload(FormRecord.fields))
            .where(FormRecord.owner_id == identity.owner_id)
            .order_by(FormRecord.updated_at.desc(), FormRecord.id)
            .limit(100)
        ).all()
        total = int(db.scalar(
            select(func.count(FormRecord.id)).where(FormRecord.owner_id == identity.owner_id)
        ) or 0)
        response_counts: dict[str, int] = {}
        form_ids = [record.id for record in records]
        if form_ids:
            counts = db.execute(
                select(FormResponseRecord.form_id, func.count(FormResponseRecord.id))
                .where(FormResponseRecord.form_id.in_(form_ids))
                .group_by(FormResponseRecord.form_id)
            ).all()
            response_counts = {form_id: int(count) for form_id, count in counts}
        return {
            "items": [
                {**_form_dict(record), "response_count": response_counts.get(record.id, 0)}
                for record in records
            ],
            "total": total,
            "limit": 100,
            "has_more": total > len(records),
        }

    @app.post("/api/forms", status_code=201)
    async def create_form(
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_permission_write("fm_create")),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = request.app.state.settings
        payload = await _read_json_object(request, cfg.max_request_bytes)
        try:
            normalized = normalize_form_payload(
                payload, max_fields=cfg.max_fields_per_form, updating=False
            )
        except PayloadError as err:
            raise HTTPException(422, detail={"code": err.code, "message": err.message}) from None

        create_key = request.headers.get("idempotency-key", "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", create_key):
            raise HTTPException(428, "idempotency_key_required")
        event_id = _resolve_purchase_link(db, normalized)
        _require_known_form_event(db, normalized, event_id, previous=None)
        _require_finance_for_commercial_change(identity, None, normalized.settings)
        canonical_payload = {
            "name": normalized.title,
            "model": normalized.model,
            "need": normalized.need,
            "slug": normalized.slug,
            "event_id": event_id,
            "purpose": normalized.purpose,
            "recording_id": normalized.recording_id,
            "settings": normalized.settings,
            "fields": [
                {"id": field.key, "t": field.field_type, "l": field.label, "config": field.config}
                for field in normalized.fields
            ],
        }
        payload_hash = hashlib.sha256(
            json.dumps(
                canonical_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        existing = db.scalar(
            select(FormRecord)
            .options(selectinload(FormRecord.fields))
            .where(FormRecord.owner_id == identity.owner_id, FormRecord.create_key == create_key)
        )
        if existing is not None:
            if not constant_time_equal(existing.create_hash or "", payload_hash):
                raise HTTPException(409, detail={"code": "idempotency_conflict"})
            return JSONResponse(_form_dict(existing), status_code=200)

        record = FormRecord(
            id=str(uuid.uuid4()),
            owner_id=identity.owner_id,
            title=normalized.title,
            model=normalized.model,
            need=normalized.need,
            slug=normalized.slug,
            event_id=event_id,
            purpose=normalized.purpose,
            recording_id=normalized.recording_id,
            status="draft",
            create_key=create_key,
            create_hash=payload_hash,
            version=1,
            settings=normalized.settings,
        )
        db.add(record)
        db.flush()
        _replace_fields(db, record.id, normalized)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(
                select(FormRecord)
                .options(selectinload(FormRecord.fields))
                .where(FormRecord.owner_id == identity.owner_id, FormRecord.create_key == create_key)
            )
            if existing is not None and constant_time_equal(existing.create_hash or "", payload_hash):
                return JSONResponse(_form_dict(existing), status_code=200)
            if existing is not None:
                raise HTTPException(409, detail={"code": "idempotency_conflict"}) from None
            raise HTTPException(409, "form_conflict") from None
        db.refresh(record)
        persisted_record = db.scalar(
            select(FormRecord)
            .options(selectinload(FormRecord.fields))
            .where(FormRecord.id == record.id, FormRecord.owner_id == identity.owner_id)
        )
        return _form_dict(persisted_record)

    def get_owned_form(db: Session, owner_id: str, form_id: str) -> FormRecord:
        record = db.scalar(
            select(FormRecord)
            .options(selectinload(FormRecord.fields))
            .where(FormRecord.id == form_id, FormRecord.owner_id == owner_id)
        )
        if record is None:
            raise HTTPException(404, "form_not_found")
        return record

    _FINANCE_SETTING_KEYS = ("fin", "groups", "coupon", "methods", "enabledPaymentMethods", "receiptReviewRequired")

    def _finance_view(settings: Mapping[str, Any] | None) -> dict[str, Any]:
        """Canonical view of the commercial settings so unchanged payloads compare equal."""
        source = settings if isinstance(settings, Mapping) else {}
        raw_coupon = source.get("coupon")
        coupon: Mapping[str, Any] = raw_coupon if isinstance(raw_coupon, Mapping) else {}
        return {
            "fin": source.get("fin") if isinstance(source.get("fin"), list) else [],
            "groups": source.get("groups") if isinstance(source.get("groups"), list) else [],
            "coupon": {"code": str(coupon.get("code") or ""), "off": coupon.get("off") or 0, "all": bool(coupon.get("all"))},
            "methods": source.get("methods") if isinstance(source.get("methods"), list) else [],
            "enabledPaymentMethods": source.get("enabledPaymentMethods") if isinstance(source.get("enabledPaymentMethods"), list) else [],
            "receiptReviewRequired": source.get("receiptReviewRequired") is True,
        }

    def _require_finance_for_commercial_change(
        identity: OwnerIdentity | AccountIdentity, previous: Mapping[str, Any] | None, new: Mapping[str, Any]
    ) -> None:
        """Stage C-1 (panel restore): money settings of a form are written only by the owner or a
        role holding ``finance``. Hiding the finance cards in create.html is not access control, so
        the server rejects any change to the commercial keys from other editors; an unchanged copy
        (what create.html sends for non-finance editors) passes."""
        role = ROLE_OWNER if isinstance(identity, OwnerIdentity) else identity.role
        if has_permission(role, "finance"):
            return
        if _finance_view(previous) != _finance_view(new):
            raise HTTPException(403, detail={
                "code": "finance_permission_required",
                "message": "تنظیم مبلغ، روش پرداخت و تخفیف فقط با مجوز مالی (مالک) ذخیره می‌شود.",
            })

    def _resolve_purchase_link(db: Session, normalized: Any) -> str | None:
        """Validate ``purpose='recording_access'`` against a real product and fix ``event_id``.

        Returns the event id the form must carry (the product's event). Ids are
        looked up server-side; a client cannot point a form at a foreign event.
        """
        if normalized.purpose != "recording_access":
            return normalized.event_id
        recording = db.get(EventRecordingRecord, normalized.recording_id or "")
        if recording is None:
            raise HTTPException(422, detail={"code": "recording_not_found", "message": "محصول ضبط‌شده پیدا نشد."})
        if normalized.event_id and normalized.event_id != recording.event_id:
            raise HTTPException(
                422,
                detail={"code": "purchase_form_event_mismatch", "message": "رویداد فرم با رویداد محصول یکی نیست."},
            )
        return recording.event_id

    def _require_known_form_event(db: Session, normalized: Any, event_id: str | None, *, previous: str | None) -> None:
        """``forms.ev`` must name an event that exists in ``site_content.events`` (any status).

        Checked only when the client sets a *new* non-empty id: a stale id already stored on the form
        (event removed later) never blocks unrelated edits, and purchase forms are exempt because
        their event id is derived from the recording record in :func:`_resolve_purchase_link`.
        """
        value = str(event_id or "").strip()
        if not value or normalized.purpose == "recording_access" or value == str(previous or ""):
            return
        site = db.get(SiteContentRecord, "public")
        content = site.content if site is not None and isinstance(site.content, dict) else {}
        known = {
            str(row.get("id") or "").strip()
            for row in (content.get("events") or [])
            if isinstance(row, dict)
        }
        if value not in known:
            raise HTTPException(
                422,
                detail={"code": "unknown_reference", "field": "ev", "message": "رویدادی با این شناسه در محتوای سایت نیست؛ اول رویداد را بسازید."},
            )

    def _other_published_purchase_form(db: Session, record: FormRecord) -> FormRecord | None:
        if not _form_is_purchase(record):
            return None
        return db.scalar(
            select(FormRecord).where(
                FormRecord.recording_id == record.recording_id,
                FormRecord.purpose == "recording_access",
                FormRecord.status == "published",
                FormRecord.id != record.id,
            )
        )

    @app.get("/api/forms/{form_id}")
    def get_form(
        form_id: str,
        identity: OwnerIdentity | AccountIdentity = Depends(require_permission("fm_create")),
        db: Session = Depends(get_db),
    ):
        return _form_dict(get_owned_form(db, identity.owner_id, form_id))

    @app.get("/api/forms/{form_id}/readiness")
    def get_form_readiness(
        form_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_permission("fm_create")),
        db: Session = Depends(get_db),
    ):
        """Explain publish blockers without changing the form or its status."""
        record = get_owned_form(db, identity.owner_id, form_id)
        issues = publication_issues(
            record, bale_ready=_runtime_settings(db, request.app.state.settings).form_bale_payments_ready
        )
        purchase: dict[str, Any] | None = None
        if _form_is_purchase(record):
            recording = db.get(EventRecordingRecord, record.recording_id or "")
            other = _other_published_purchase_form(db, record)
            if recording is None:
                issues.append({"code": "recording_not_found", "message": "محصول ضبط‌شدهٔ این فرم دیگر وجود ندارد."})
            if other is not None and record.status != "published":
                issues.append({
                    "code": "purchase_form_already_published",
                    "message": f"فرم خرید دیگری («{other.title}») برای این محصول منتشر است؛ ابتدا آن را متوقف کنید.",
                })
            settings_value = record.settings if isinstance(record.settings, dict) else {}
            purchase = {
                "recording_id": record.recording_id,
                "recording_title": recording.title if recording is not None else "",
                "recording_status": recording.status if recording is not None else "",
                "event_id": recording.event_id if recording is not None else record.event_id,
                "price": purchase_form_price(settings_value),
                "other_published_form_id": other.id if other is not None else None,
            }
        publishable_status = record.status in {"draft", "paused"}
        return {
            "source": "same_server_database",
            "form_id": record.id,
            "version": record.version,
            "status": record.status,
            "purpose": record.purpose,
            "purchase": purchase,
            "publishable": publishable_status and not issues,
            "status_issue": None if publishable_status else "فرم باید پیش‌نویس یا متوقف باشد تا منتشر شود.",
            "issues": issues,
        }

    @app.put("/api/forms/{form_id}")
    async def update_form(
        form_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_permission_write("fm_create")),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = request.app.state.settings
        payload = await _read_json_object(request, cfg.max_request_bytes)
        try:
            normalized = normalize_form_payload(
                payload, max_fields=cfg.max_fields_per_form, updating=True
            )
        except PayloadError as err:
            status = 428 if err.code == "version_required" else 422
            raise HTTPException(status, detail={"code": err.code, "message": err.message}) from None

        record = get_owned_form(db, identity.owner_id, form_id)
        if record.status == "published":
            raise HTTPException(
                409,
                detail={"code": "published_form_read_only", "message": "ابتدا دریافت پاسخ را متوقف کنید."},
            )
        response_count = db.scalar(
            select(func.count(FormResponseRecord.id)).where(FormResponseRecord.form_id == form_id)
        ) or 0
        if response_count:
            raise HTTPException(
                409,
                detail={
                    "code": "form_has_responses",
                    "message": "پس از ثبت پاسخ، تعریف فرم تغییرناپذیر است؛ برای نسخهٔ تازه فرم دیگری بسازید.",
                },
            )
        record_id = record.id
        expected_version = normalized.expected_version
        if record.version != expected_version:
            raise HTTPException(
                409,
                detail={"code": "version_conflict", "current_version": record.version},
            )
        event_id = _resolve_purchase_link(db, normalized)
        _require_known_form_event(db, normalized, event_id, previous=record.event_id)
        _require_finance_for_commercial_change(identity, record.settings, normalized.settings)

        # Compare-and-swap at the database, not just in Python: two owners' tabs
        # cannot silently overwrite one another after both read the same version.
        result = db.execute(
            update(FormRecord)
            .where(
                FormRecord.id == record_id,
                FormRecord.owner_id == identity.owner_id,
                FormRecord.version == expected_version,
            )
            .values(
                title=normalized.title,
                model=normalized.model,
                need=normalized.need,
                slug=normalized.slug,
                event_id=event_id,
                purpose=normalized.purpose,
                recording_id=normalized.recording_id,
                settings=normalized.settings,
                version=FormRecord.version + 1,
                updated_at=_utc_now(),
            )
            .execution_options(synchronize_session=False)
        )
        if cast(CursorResult[Any], result).rowcount != 1:
            db.rollback()
            current_version = db.scalar(
                select(FormRecord.version).where(
                    FormRecord.id == record_id,
                    FormRecord.owner_id == identity.owner_id,
                )
            )
            if current_version is None:
                raise HTTPException(404, "form_not_found")
            raise HTTPException(
                409,
                detail={"code": "version_conflict", "current_version": current_version},
            )
        db.expire_all()
        _replace_fields(db, record_id, normalized)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "form_conflict") from None
        persisted_record = db.scalar(
            select(FormRecord)
            .options(selectinload(FormRecord.fields))
            .where(FormRecord.id == record_id, FormRecord.owner_id == identity.owner_id)
        )
        return _form_dict(persisted_record)

    def get_published_form(
        db: Session, form_id: str, *, bale_ready: bool = False
    ) -> FormRecord:
        record = db.scalar(
            select(FormRecord)
            .options(selectinload(FormRecord.fields))
            .where(FormRecord.id == form_id, FormRecord.status == "published")
        )
        if record is None:
            raise HTTPException(404, "public_form_not_found")
        issues = publication_issues(record, bale_ready=bale_ready)
        if issues:
            raise HTTPException(404, "public_form_not_found")
        return record

    def form_has_companions(form: FormRecord) -> bool:
        settings = form.settings if isinstance(form.settings, dict) else {}
        return settings.get("guestsOn") is True

    def get_bot_published_form(
        db: Session, form_id: str, *, bale_ready: bool = False
    ) -> FormRecord:
        form = get_published_form(db, form_id, bale_ready=bale_ready)
        if form_has_companions(form) or _form_uses_payment(form) or _form_is_purchase(form):
            # Purchases start from form.html with a signed-in account (access is granted to it).
            raise HTTPException(404, "bot_form_not_supported")
        return form

    def check_public_write_target(
        db: Session, form_id: str, *, bale_ready: bool = False
    ) -> None:
        status = db.scalar(select(FormRecord.status).where(FormRecord.id == form_id))
        if status is None:
            raise HTTPException(404, "public_form_not_found")
        if status != "published":
            raise HTTPException(409, "form_not_open")
        get_published_form(db, form_id, bale_ready=bale_ready)

    def public_draft_for_cookie(request: Request, db: Session, form_id: str) -> FormResponseDraftRecord | None:
        token = request.cookies.get(_public_draft_cookie_name(form_id), "")
        if not token:
            return None
        record = db.scalar(
            select(FormResponseDraftRecord)
            .where(
                FormResponseDraftRecord.form_id == form_id,
                FormResponseDraftRecord.token_hash == token_digest(token),
            )
            .options(selectinload(FormResponseDraftRecord.response))
        )
        if record is None or _as_utc(record.expires_at) <= _utc_now():
            return None
        return record

    def ensure_public_draft(
        request: Request,
        db: Session,
        form: FormRecord,
    ) -> tuple[FormResponseDraftRecord, str | None]:
        current = public_draft_for_cookie(request, db, form.id)
        if current is not None:
            if current.form_version != form.version:
                current.form_version = form.version
                if current.response is None:
                    current.answers = {}
                    current.companions = []
                    current.has_unsaved_changes = False
                current.expires_at = _utc_now() + timedelta(
                    seconds=request.app.state.settings.response_draft_ttl_seconds
                )
            return current, None
        raw_token = new_token()
        record = FormResponseDraftRecord(
            id=str(uuid.uuid4()),
            form_id=form.id,
            form_version=form.version,
            token_hash=token_digest(raw_token),
            answers={},
            companions=[],
            has_unsaved_changes=False,
            expires_at=_utc_now() + timedelta(
                seconds=request.app.state.settings.response_draft_ttl_seconds
            ),
        )
        db.add(record)
        db.flush()
        return record, raw_token

    def set_public_draft_cookie(response: Response, form_id: str, token: str, cfg: Settings) -> None:
        response.set_cookie(
            _public_draft_cookie_name(form_id),
            token,
            httponly=True,
            secure=cfg.cookie_secure,
            samesite=_samesite(cfg),
            path=f"/api/public/forms/{form_id}",
            max_age=cfg.response_draft_ttl_seconds,
        )

    def clear_public_draft_cookie(response: Response, form_id: str, cfg: Settings) -> None:
        response.delete_cookie(
            _public_draft_cookie_name(form_id),
            path=f"/api/public/forms/{form_id}",
            secure=cfg.cookie_secure,
            httponly=True,
            samesite=_samesite(cfg),
        )

    def enforce_public_write_limit(
        request: Request,
        db: Session,
        form_id: str,
        cfg: Settings,
        limit: int,
    ) -> None:
        if not cfg.owner_password_hash:
            raise HTTPException(503, "public_write_protection_not_configured")
        remote = request.client.host if request.client else "unknown"
        # Requests with different configured budgets use independent buckets; e.g. a
        # receipt/review link must not exhaust the stricter final-submit allowance.
        key_hash = throttle_digest(
            cfg.owner_password_hash,
            form_id + "\0" + remote + "\0" + str(limit),
        )
        now = _utc_now()
        db.execute(
            delete(PublicWriteThrottleRecord).where(
                PublicWriteThrottleRecord.window_started_at < now - timedelta(days=1)
            )
        )
        record = db.scalar(
            select(PublicWriteThrottleRecord)
            .where(PublicWriteThrottleRecord.key_hash == key_hash)
            .with_for_update()
        )
        if record is None:
            record = PublicWriteThrottleRecord(key_hash=key_hash, attempts=1, window_started_at=now)
            db.add(record)
            try:
                db.commit()
                return
            except IntegrityError:
                db.rollback()
                record = db.scalar(
                    select(PublicWriteThrottleRecord)
                    .where(PublicWriteThrottleRecord.key_hash == key_hash)
                    .with_for_update()
                )
                if record is None:
                    raise HTTPException(503, "public_write_protection_unavailable") from None
        if now - _as_utc(record.window_started_at) >= timedelta(minutes=1):
            record.window_started_at = now
            record.attempts = 1
        else:
            record.attempts += 1
        blocked = record.attempts > max(1, limit)
        db.commit()
        if blocked:
            raise HTTPException(429, "public_write_rate_limited", headers={"Retry-After": "60"})

    def draft_answers(db: Session, draft: FormResponseDraftRecord) -> tuple[dict[str, Any], FormResponseRecord | None]:
        response_record = db.scalar(
            select(FormResponseRecord).where(FormResponseRecord.draft_id == draft.id)
        )
        if draft.has_unsaved_changes:
            return dict(draft.answers or {}), response_record
        if response_record is not None:
            return dict(response_record.answers or {}), response_record
        return dict(draft.answers or {}), None

    def draft_companions(
        db: Session, draft: FormResponseDraftRecord, response_record: FormResponseRecord | None
    ) -> list[dict[str, Any]]:
        if draft.has_unsaved_changes or response_record is None:
            return list(draft.companions or [])
        children = db.scalars(
            select(FormResponseRecord)
            .where(FormResponseRecord.added_by_response_id == response_record.id)
            .order_by(
                FormResponseRecord.companion_index,
                FormResponseRecord.created_at,
                FormResponseRecord.id,
            )
        ).all()
        if children:
            return [
                {
                    "name": child.registrant_name or "همراه",
                    "mobile": child.registrant_mobile or "",
                    "answers": child.answers or {},
                }
                for child in children
            ]
        return list(response_record.companions or [])

    def validate_bot_form_user_id(bale_user_id: Any) -> str:
        if isinstance(bale_user_id, bool) or not isinstance(bale_user_id, (str, int)):
            raise HTTPException(422, "invalid_bale_user_id")
        user_id = str(bale_user_id)
        if not _BOT_FORM_USER_ID.fullmatch(user_id):
            raise HTTPException(422, "invalid_bale_user_id")
        return user_id

    def validate_bot_form_identity(bale_user_id: Any, session_key: Any) -> tuple[str, str]:
        user_id = validate_bot_form_user_id(bale_user_id)
        if not isinstance(session_key, str) or not _BOT_FORM_SESSION_KEY.fullmatch(session_key):
            raise HTTPException(422, "invalid_bot_form_session_key")
        return user_id, session_key

    def associate_bot_form_draft(draft: FormResponseDraftRecord, bale_user_id: str) -> bool:
        current_user_id = draft.bot_bale_user_id
        if current_user_id is not None and current_user_id != bale_user_id:
            raise HTTPException(409, "bot_form_draft_identity_conflict")
        if current_user_id is None:
            draft.bot_bale_user_id = bale_user_id
            return True
        return False

    def require_bot_form_response_reader(
        db: Session, cfg: Settings, bale_user_id: Any
    ) -> str:
        user_id = validate_bot_form_user_id(bale_user_id)
        _account_id, role = bot_account_identity(db, cfg, user_id)
        if not has_permission(role, "fm_responses"):
            raise HTTPException(403, "permission_denied")
        return user_id

    def bot_form_token_hash(form_id: str, bale_user_id: str, session_key: str) -> str:
        identity = f"nora-bot-form-v1\0{bale_user_id}\0{form_id}\0{session_key}"
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    def bot_form_draft_for_session(
        db: Session,
        form_id: str,
        bale_user_id: str,
        session_key: str,
        *,
        lock: bool = False,
    ) -> FormResponseDraftRecord | None:
        statement = (
            select(FormResponseDraftRecord)
            .where(
                FormResponseDraftRecord.form_id == form_id,
                FormResponseDraftRecord.token_hash == bot_form_token_hash(
                    form_id, bale_user_id, session_key
                ),
            )
            .options(selectinload(FormResponseDraftRecord.response))
        )
        if lock:
            statement = statement.with_for_update()
        return db.scalar(statement)

    def enforce_bot_form_write_limit(
        db: Session,
        form_id: str,
        bale_user_id: str,
        cfg: Settings,
        limit: int,
    ) -> None:
        if not cfg.bot_service_token:
            raise HTTPException(503, "bot_api_not_configured")
        key_hash = throttle_digest(
            cfg.bot_service_token, "bot-form\0" + form_id + "\0" + bale_user_id
        )
        now = _utc_now()
        db.execute(
            delete(PublicWriteThrottleRecord).where(
                PublicWriteThrottleRecord.window_started_at < now - timedelta(days=1)
            )
        )
        record = db.scalar(
            select(PublicWriteThrottleRecord)
            .where(PublicWriteThrottleRecord.key_hash == key_hash)
            .with_for_update()
        )
        if record is None:
            record = PublicWriteThrottleRecord(key_hash=key_hash, attempts=1, window_started_at=now)
            db.add(record)
            try:
                db.commit()
                return
            except IntegrityError:
                db.rollback()
                record = db.scalar(
                    select(PublicWriteThrottleRecord)
                    .where(PublicWriteThrottleRecord.key_hash == key_hash)
                    .with_for_update()
                )
                if record is None:
                    raise HTTPException(503, "public_write_protection_unavailable") from None
        if now - _as_utc(record.window_started_at) >= timedelta(minutes=1):
            record.window_started_at = now
            record.attempts = 1
        else:
            record.attempts += 1
        blocked = record.attempts > max(1, limit)
        db.commit()
        if blocked:
            raise HTTPException(429, "public_write_rate_limited", headers={"Retry-After": "60"})

    def bot_form_state(db: Session, form: FormRecord, draft: FormResponseDraftRecord) -> dict[str, Any]:
        answers, submitted = draft_answers(db, draft)
        accepted, waitlisted = _response_counts(db, form.id)
        return {
            "source": "shared_server_database",
            "form": public_form_data(form, accepted_count=accepted, waitlisted_count=waitlisted),
            "draft": {
                "answers": answers,
                "submitted": submitted is not None,
                "status": submitted.status if submitted is not None else "draft",
                "form_version": draft.form_version,
            },
            "visible_field_ids": visible_field_ids(form.fields, answers),
        }

    def ensure_writeable_public_form(
        db: Session,
        form_id: str,
        *,
        allow_companions: bool = False,
        allow_payments: bool = False,
        bale_ready: bool = False,
    ) -> FormRecord:
        form = db.scalar(
            select(FormRecord)
            .options(selectinload(FormRecord.fields))
            .where(FormRecord.id == form_id)
            .with_for_update()
        )
        if form is None or form.status != "published":
            raise HTTPException(409, "form_not_open")
        if not allow_payments and _form_uses_payment(form):
            raise HTTPException(409, "paid_form_not_supported_in_bot")
        issues = publication_issues(form, bale_ready=bale_ready)
        if issues or form_has_companions(form) and not allow_companions:
            raise HTTPException(409, "form_not_open")
        _raise_if_event_registration_blocked(db, form)
        return form

    def validate_expected_version(payload: dict[str, Any], record: FormRecord) -> int:
        expected = payload.get("expected_version")
        if set(payload) != {"expected_version"} or isinstance(expected, bool) or not isinstance(expected, int) or expected < 1:
            raise HTTPException(428, "expected_version_required")
        if expected != record.version:
            raise HTTPException(
                409,
                detail={"code": "version_conflict", "current_version": record.version},
            )
        return expected

    @app.post("/api/forms/{form_id}/publish")
    async def publish_form(
        form_id: str,
        request: Request,
        identity: OwnerIdentity = Depends(require_owner_write),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = _runtime_settings(db, request.app.state.settings)
        payload = await _read_json_object(request, cfg.max_request_bytes)
        record = get_owned_form(db, identity.owner_id, form_id)
        validate_expected_version(payload, record)
        if record.status == "published":
            return _form_dict(record)
        if record.status not in {"draft", "paused"}:
            raise HTTPException(409, "form_cannot_be_published")
        issues = publication_issues(record, bale_ready=cfg.form_bale_payments_ready)
        if issues:
            raise HTTPException(
                422,
                detail={"code": "form_not_publishable", "issues": issues},
            )
        if _form_is_purchase(record):
            if db.get(EventRecordingRecord, record.recording_id or "") is None:
                raise HTTPException(422, detail={"code": "form_not_publishable", "issues": [
                    {"code": "recording_not_found", "message": "محصول ضبط‌شدهٔ این فرم دیگر وجود ندارد."},
                ]})
            other = _other_published_purchase_form(db, record)
            if other is not None:
                raise HTTPException(409, detail={
                    "code": "purchase_form_already_published", "form_id": other.id, "title": other.title,
                    "message": "برای این محصول یک فرم خرید منتشرشده وجود دارد؛ ابتدا آن را متوقف کنید.",
                })
        result = db.execute(
            update(FormRecord)
            .where(
                FormRecord.id == form_id,
                FormRecord.owner_id == identity.owner_id,
                FormRecord.version == record.version,
                FormRecord.status.in_(["draft", "paused"]),
            )
            .values(status="published", version=FormRecord.version + 1, updated_at=_utc_now())
            .execution_options(synchronize_session=False)
        )
        if cast(CursorResult[Any], result).rowcount != 1:
            db.rollback()
            raise HTTPException(409, "form_conflict")
        record_audit(
            db, identity, "form.publish", target_type="form", target_id=form_id,
            details={"from_status": record.status, "title": record.title},
        )
        db.commit()
        db.expire_all()
        return _form_dict(get_owned_form(db, identity.owner_id, form_id))

    @app.post("/api/forms/{form_id}/pause")
    async def pause_form(
        form_id: str,
        request: Request,
        identity: OwnerIdentity = Depends(require_owner_write),
        db: Session = Depends(get_db),
    ):
        payload = await _read_json_object(request, request.app.state.settings.max_request_bytes)
        record = get_owned_form(db, identity.owner_id, form_id)
        validate_expected_version(payload, record)
        if record.status == "paused":
            return _form_dict(record)
        if record.status != "published":
            raise HTTPException(409, "form_not_published")
        result = db.execute(
            update(FormRecord)
            .where(
                FormRecord.id == form_id,
                FormRecord.owner_id == identity.owner_id,
                FormRecord.version == record.version,
                FormRecord.status == "published",
            )
            .values(status="paused", version=FormRecord.version + 1, updated_at=_utc_now())
            .execution_options(synchronize_session=False)
        )
        if cast(CursorResult[Any], result).rowcount != 1:
            db.rollback()
            raise HTTPException(409, "form_conflict")
        record_audit(
            db, identity, "form.pause", target_type="form", target_id=form_id,
            details={"title": record.title},
        )
        db.commit()
        db.expire_all()
        return _form_dict(get_owned_form(db, identity.owner_id, form_id))

    @app.post("/api/forms/{form_id}/event")
    async def link_form_event(
        form_id: str,
        request: Request,
        identity: OwnerIdentity | AccountIdentity = Depends(require_permission_write("fm_create")),
        db: Session = Depends(get_db),
    ):
        """Attach an existing warehouse form to an event (or detach it) from the event wizard.

        Only the reference moves: fields/settings stay untouched, so the builder remains the sole
        form editor. Same guards as a full edit: owned form, ``expected_version`` compare-and-swap,
        immutable once responses exist, published forms must be paused first, purchase forms keep
        the event derived from their recording, and the target must be a real ``site_content`` event.
        """
        payload = await _read_json_object(request, request.app.state.settings.max_request_bytes)
        expected = payload.get("expected_version")
        raw_event = payload.get("ev", "")
        if (
            set(payload) - {"expected_version", "ev"}
            or isinstance(expected, bool)
            or not isinstance(expected, int)
            or expected < 1
        ):
            raise HTTPException(428, "expected_version_required")
        if raw_event is not None and not isinstance(raw_event, str):
            raise HTTPException(422, detail={"code": "invalid_event_reference", "field": "ev"})
        event_id = str(raw_event or "").strip()[:120]
        record = get_owned_form(db, identity.owner_id, form_id)
        if expected != record.version:
            raise HTTPException(409, detail={"code": "version_conflict", "current_version": record.version})
        previous = str(record.event_id or "")
        if event_id == previous:
            return _form_dict(record)
        if record.purpose == "recording_access":
            raise HTTPException(
                409,
                detail={"code": "purchase_form_event_fixed", "message": "رویداد فرم خرید از محصول ضبط‌شده می‌آید."},
            )
        if record.status == "published":
            raise HTTPException(
                409,
                detail={"code": "published_form_read_only", "message": "ابتدا دریافت پاسخ را متوقف کنید."},
            )
        response_count = db.scalar(
            select(func.count(FormResponseRecord.id)).where(FormResponseRecord.form_id == form_id)
        ) or 0
        if response_count:
            raise HTTPException(
                409,
                detail={"code": "form_has_responses", "message": "پس از ثبت پاسخ، پیوند رویداد فرم تغییر نمی‌کند."},
            )
        if event_id:
            site = db.get(SiteContentRecord, "public")
            content = site.content if site is not None and isinstance(site.content, dict) else {}
            known = {
                str(row.get("id") or "").strip()
                for row in (content.get("events") or [])
                if isinstance(row, dict)
            }
            if event_id not in known:
                raise HTTPException(
                    422,
                    detail={"code": "unknown_reference", "field": "ev", "message": "رویدادی با این شناسه در محتوای سایت نیست."},
                )
        result = db.execute(
            update(FormRecord)
            .where(
                FormRecord.id == form_id,
                FormRecord.owner_id == identity.owner_id,
                FormRecord.version == expected,
            )
            .values(event_id=event_id or None, version=FormRecord.version + 1, updated_at=_utc_now())
            .execution_options(synchronize_session=False)
        )
        if cast(CursorResult[Any], result).rowcount != 1:
            db.rollback()
            raise HTTPException(409, "form_conflict")
        record_audit(
            db, identity, "form.event_link", target_type="form", target_id=form_id,
            details={"title": record.title, "from_event": previous, "to_event": event_id},
        )
        db.commit()
        db.expire_all()
        return _form_dict(get_owned_form(db, identity.owner_id, form_id))

    @app.get("/api/public/forms/{form_id}")
    def get_public_form(
        form_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        cfg: Settings = _runtime_settings(db, request.app.state.settings)
        form = get_published_form(db, form_id, bale_ready=cfg.form_bale_payments_ready)
        _raise_if_event_registration_blocked(db, form)
        accepted, waitlisted = _response_counts(db, form_id)
        if _capacity_is_full(form, accepted + _active_bale_payment_holds(db, form_id), waitlisted):
            raise HTTPException(410, detail={"code": "form_full"})
        data = public_form_data(
            form,
            accepted_count=accepted,
            waitlisted_count=waitlisted,
            bale_ready=cfg.form_bale_payments_ready,
        )
        if _form_is_purchase(form):
            data["purchase"] = _public_purchase_header(db, request, form)
        return data

    @app.post("/api/public/forms/{form_id}/coupon-check")
    def check_public_coupon(
        form_id: str,
        payload: dict[str, Any],
        request: Request,
        http_response: Response,
        db: Session = Depends(get_db),
    ):
        """Validate a typed discount code without ever exposing the configured code."""
        cfg: Settings = _runtime_settings(db, request.app.state.settings)
        http_response.headers["Cache-Control"] = "no-store"
        if not isinstance(payload, dict) or set(payload) != {"code"} or not isinstance(payload.get("code"), str):
            raise HTTPException(400, detail={"code": "invalid_coupon_payload"})
        typed = payload["code"]
        if len(typed) > 64:
            raise HTTPException(422, detail={"code": "invalid_coupon_code"})
        form = get_published_form(db, form_id, bale_ready=cfg.form_bale_payments_ready)
        enforce_public_write_limit(request, db, form_id, cfg, cfg.response_draft_write_limit_per_minute)
        settings = form.settings if isinstance(form.settings, dict) else {}
        try:
            financial = normalize_financial_config(settings)
        except PaymentConfigurationError:
            return {"valid": False, "off": 0, "all": False}
        coupon = financial["coupon"]
        configured = unicodedata.normalize("NFKC", coupon["code"]).strip().casefold()
        normalized = unicodedata.normalize("NFKC", typed).strip().casefold()
        valid = bool(configured) and coupon["off"] > 0 and bool(financial["fin"]) and secrets.compare_digest(
            configured.encode("utf-8"), normalized.encode("utf-8")
        )
        if not valid:
            return {"valid": False, "off": 0, "all": False}
        return {"valid": True, "off": coupon["off"], "all": coupon["all"]}

    @app.post("/api/public/forms/{form_id}/payment-intents", status_code=201)
    async def create_public_payment_intent(
        form_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        _same_origin(request)
        cfg: Settings = _runtime_settings(db, request.app.state.settings)
        payload = await _read_json_object(request, cfg.max_request_bytes)
        if (
            not isinstance(payload, dict)
            or set(payload) != {"method", "selection"}
            or payload.get("method") != "bale_wallet"
            or not isinstance(payload.get("selection"), dict)
        ):
            raise HTTPException(400, detail={"code": "invalid_payment_payload"})
        check_public_write_target(db, form_id, bale_ready=cfg.form_bale_payments_ready)
        enforce_public_write_limit(request, db, form_id, cfg, cfg.response_submit_limit_per_minute)
        form = ensure_writeable_public_form(
            db, form_id, allow_companions=True, allow_payments=True,
            bale_ready=cfg.form_bale_payments_ready
        )
        if not cfg.form_bale_payments_ready:
            raise HTTPException(503, detail={"code": "bale_payment_not_configured"})
        if form.model != "registration" or "bale_wallet" not in _selected_form_payment_methods(form):
            raise HTTPException(422, detail={"code": "payment_method_not_available"})
        draft = public_draft_for_cookie(request, db, form_id)
        if draft is None:
            raise HTTPException(401, "response_draft_required")
        draft = db.scalar(
            select(FormResponseDraftRecord)
            .where(FormResponseDraftRecord.id == draft.id)
            .with_for_update()
        )
        if draft is None or draft.form_version != form.version:
            raise HTTPException(409, "form_version_changed")
        purchase_identity = _require_purchase_account(request, db, form)
        bind_public_draft_account(draft, purchase_identity, db)
        if _form_is_purchase(form):
            purchase_recording = _purchase_recording_for_form(db, form)
            if purchase_recording is None or purchase_recording.status != "published":
                raise HTTPException(409, detail={"code": "recording_not_on_sale"})
            current_access = recordings_mod.access_for(db, purchase_recording.id, draft.account_id)
            if recordings_mod.access_state(current_access, _utc_now()) == "active":
                raise HTTPException(409, detail={"code": "access_already_active", "recording_id": purchase_recording.id})
            _reject_duplicate_purchase_order(db, purchase_recording, draft.account_id)
        if db.scalar(select(FormResponseRecord.id).where(FormResponseRecord.draft_id == draft.id)):
            raise HTTPException(409, detail={"code": "response_already_submitted"})
        answers, submitted = draft_answers(db, draft)
        if submitted is not None:
            raise HTTPException(409, detail={"code": "response_already_submitted"})
        form_settings = form.settings if isinstance(form.settings, dict) else {}
        try:
            validate_answers(form.fields, answers, partial=False)
            companions = validate_companions(
                form.fields, draft_companions(db, draft, None), form_settings, partial=False
            )
            calculation = calculate_payment_amount(
                form_settings,
                payload["selection"],
                party_count=1 + len(companions),
            )
        except AnswerValidationError as error:
            raise HTTPException(
                422, detail={"code": "answer_validation_failed", "errors": error.errors}
            ) from None
        except PaymentConfigurationError as error:
            raise HTTPException(422, detail={"code": error.code}) from None
        if calculation["amount"] <= 0:
            raise HTTPException(422, detail={"code": "payment_amount_must_be_positive"})
        if calculation["amount"] > cfg.form_payment_max_amount:
            raise HTTPException(422, detail={"code": "payment_amount_exceeds_limit"})
        normalized_selection = {
            "items": sorted(item["index"] for item in calculation["items"]),
            "coupon_code": (
                str((form_settings.get("coupon") or {}).get("code") or "")
                if calculation["coupon_applied"] else ""
            ),
            "party_count": calculation["party_count"],
        }
        now = _utc_now()
        active_intents = db.scalars(
            select(FormPaymentRecord)
            .where(
                FormPaymentRecord.draft_id == draft.id,
                FormPaymentRecord.method == "bale_wallet",
                FormPaymentRecord.status == "pending",
            )
            .with_for_update()
        ).all()
        for intent in active_intents:
            if intent.expires_at is not None and _as_utc(intent.expires_at) <= now:
                intent.status = "expired"
                intent.updated_at = now
            elif (
                intent.amount == calculation["amount"]
                and intent.party_count == calculation["party_count"]
                and _payment_selection_for_recalculation(intent.selection, form_settings)
                == {"items": normalized_selection["items"], "coupon_code": normalized_selection["coupon_code"]}
            ):
                db.commit()
                return {
                    "payment_id": intent.id,
                    "method": intent.method,
                    "status": intent.status,
                    "amount": intent.amount,
                    "currency": intent.currency,
                    "invoice_url": intent.invoice_url,
                    "expires_at": _as_utc(intent.expires_at).isoformat() if intent.expires_at else None,
                }
            else:
                raise HTTPException(409, detail={"code": "payment_intent_already_open"})
        accepted, waitlisted = _response_counts(db, form_id)
        cap = _count_setting(form_settings.get("cap", 0))
        if cap > 0 and accepted + _active_bale_payment_holds(db, form_id) + calculation["party_count"] > cap:
            raise HTTPException(410, detail={"code": "form_full"})

        try:
            await _ensure_bale_payment_webhook(cfg)
            payment_id = str(uuid.uuid4())
            invoice_payload = "nora_" + uuid.uuid4().hex
            title = str(form.title or "ثبت‌نام").strip()[:32] or "ثبت‌نام"
            description = f"پرداخت ثبت‌نام: {str(form.title or 'فرم')[:200]}"[:255]
            invoice_response = await asyncio.to_thread(
                call_bale_payment_api,
                cfg,
                "createInvoiceLink",
                {
                    "title": title,
                    "description": description,
                    "payload": invoice_payload,
                    "provider_token": cfg.form_payment_provider_token,
                    "currency": calculation["currency"],
                    "prices": [{"label": title, "amount": calculation["amount"]}],
                },
            )
            invoice_url = validated_invoice_url(invoice_response.get("result"))
        except HTTPException:
            raise
        except BalePaymentAPIError as error:
            raise HTTPException(503, detail={"code": error.code}) from None

        expires_at = now + timedelta(seconds=cfg.form_payment_ttl_seconds)
        payment = FormPaymentRecord(
            id=payment_id,
            form_id=form_id,
            draft_id=draft.id,
            form_version=form.version,
            method="bale_wallet",
            status="pending",
            amount=calculation["amount"],
            currency=calculation["currency"],
            party_count=calculation["party_count"],
            selection=normalized_selection,
            invoice_payload=invoice_payload,
            invoice_url=invoice_url,
            idempotency_key="form-bale:" + payment_id,
            expires_at=expires_at,
        )
        db.add(payment)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, detail={"code": "payment_intent_conflict"}) from None
        return {
            "payment_id": payment.id,
            "method": payment.method,
            "status": payment.status,
            "amount": payment.amount,
            "currency": payment.currency,
            "invoice_url": payment.invoice_url,
            "expires_at": expires_at.isoformat(),
        }

    @app.get("/api/public/forms/{form_id}/payment-intents/{payment_id}")
    def get_public_payment_intent(
        form_id: str,
        payment_id: str,
        request: Request,
        http_response: Response,
        db: Session = Depends(get_db),
    ):
        cfg: Settings = request.app.state.settings
        http_response.headers["Cache-Control"] = "no-store"
        draft = public_draft_for_cookie(request, db, form_id)
        if draft is None:
            raise HTTPException(401, "response_draft_required")
        try:
            canonical_payment_id = str(uuid.UUID(payment_id))
        except (ValueError, AttributeError):
            raise HTTPException(404, "payment_intent_not_found") from None
        payment = db.scalar(
            select(FormPaymentRecord).where(
                FormPaymentRecord.id == canonical_payment_id,
                FormPaymentRecord.form_id == form_id,
                FormPaymentRecord.draft_id == draft.id,
            )
        )
        if payment is None:
            raise HTTPException(404, "payment_intent_not_found")
        if (
            payment.status == "pending"
            and payment.expires_at is not None
            and _as_utc(payment.expires_at) <= _utc_now()
        ):
            payment.status = "expired"
            payment.updated_at = _utc_now()
            db.commit()
        response = db.get(FormResponseRecord, payment.response_id) if payment.response_id else None
        result = {
            "payment_id": payment.id,
            "method": payment.method,
            "status": payment.status,
            "amount": payment.amount,
            "currency": payment.currency,
            "expires_at": _as_utc(payment.expires_at).isoformat() if payment.expires_at else None,
            "invoice_url": payment.invoice_url if payment.status == "pending" else None,
            "selection": payment.selection if isinstance(payment.selection, dict) else None,
            "transaction_id": payment.transaction_id,
            "tracking_code": _form_tracking_code(response) if response is not None else None,
            "ticket_type": _form_response_ticket_type(response) if response is not None else None,
            "response_status": response.status if response is not None else None,
            "receipt_uploaded": bool(
                response is not None
                and (response.receipt_upload is not None or response.receipt_review_task_id is not None)
            ),
        }
        return result

    @app.delete("/api/public/forms/{form_id}/payment-intents/{payment_id}")
    async def cancel_public_payment_intent(
        form_id: str,
        payment_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        _same_origin(request)
        draft = public_draft_for_cookie(request, db, form_id)
        if draft is None:
            raise HTTPException(401, "response_draft_required")
        try:
            canonical_payment_id = str(uuid.UUID(payment_id))
        except (ValueError, AttributeError):
            raise HTTPException(404, "payment_intent_not_found") from None
        payment = db.scalar(
            select(FormPaymentRecord)
            .where(
                FormPaymentRecord.id == canonical_payment_id,
                FormPaymentRecord.form_id == form_id,
                FormPaymentRecord.draft_id == draft.id,
            )
            .with_for_update()
        )
        if payment is None:
            raise HTTPException(404, "payment_intent_not_found")
        if payment.status == "pending":
            payment.status = "cancelled"
            payment.updated_at = _utc_now()
            db.commit()
        return {"payment_id": payment.id, "status": payment.status}

    @app.post("/api/payments/bale/webhook/{webhook_token}")
    async def bale_payment_webhook(
        webhook_token: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        cfg: Settings = _runtime_settings(db, request.app.state.settings)
        if not cfg.form_bale_payments_ready:
            raise HTTPException(503, detail={"code": "bale_payment_not_configured"})
        if not constant_time_equal(webhook_token, _form_payment_webhook_token(cfg)):
            raise HTTPException(404, "not_found")
        supplied_secret = request.headers.get("x-telegram-bot-api-secret-token", "")
        if supplied_secret and not constant_time_equal(supplied_secret, cfg.form_payment_webhook_secret):
            raise HTTPException(403, detail={"code": "invalid_payment_webhook_secret"})
        payload = await _read_json_object(request, min(cfg.max_request_bytes, 128 * 1024))

        checkout = payload.get("pre_checkout_query")
        if isinstance(checkout, dict):
            query_id = checkout.get("id")
            if not isinstance(query_id, str) or not 1 <= len(query_id) <= 160:
                return {"ok": True}
            invoice_payload = checkout.get("invoice_payload")
            payer = checkout.get("from")
            payer_id = payer.get("id") if isinstance(payer, dict) else None
            amount = checkout.get("total_amount")
            currency = checkout.get("currency")
            payment = None
            if isinstance(invoice_payload, str) and 1 <= len(invoice_payload) <= 128:
                payment = db.scalar(
                    select(FormPaymentRecord)
                    .where(FormPaymentRecord.invoice_payload == invoice_payload)
                    .with_for_update()
                )
            form = db.get(FormRecord, payment.form_id) if payment is not None else None
            now = _utc_now()
            can_checkout = bool(
                isinstance(query_id, str) and 1 <= len(query_id) <= 160
                and payment is not None and payment.method == "bale_wallet"
                and payment.status == "pending" and payment.expires_at is not None
                and _as_utc(payment.expires_at) > now
                and isinstance(amount, int) and not isinstance(amount, bool)
                and payment.amount == amount and payment.currency == currency == "IRR"
                and isinstance(payer_id, (int, str)) and not isinstance(payer_id, bool)
                and _BOT_FORM_USER_ID.fullmatch(str(payer_id))
                and form is not None and form.status == "published"
                and form.version == payment.form_version
                and "bale_wallet" in _selected_form_payment_methods(form)
            )
            answer = {
                "pre_checkout_query_id": query_id,
                "ok": can_checkout,
            }
            if not can_checkout:
                answer["error_message"] = "این صورت‌حساب منقضی یا نامعتبر است؛ دوباره از فرم شروع کنید."
            try:
                await asyncio.to_thread(
                    call_bale_payment_api, cfg, "answerPreCheckoutQuery", answer
                )
            except BalePaymentAPIError as error:
                raise HTTPException(503, detail={"code": error.code}) from None
            return {"ok": True}

        message = payload.get("message")
        successful = message.get("successful_payment") if isinstance(message, dict) else None
        if not isinstance(successful, dict):
            # Other updates are intentionally ignored; this endpoint is dedicated to payments.
            return {"ok": True}
        invoice_payload = successful.get("invoice_payload")
        transaction_id = successful.get("telegram_payment_charge_id")
        provider_charge_id = successful.get("provider_payment_charge_id")
        callback_amount = successful.get("total_amount")
        callback_currency = successful.get("currency")
        sender = message.get("from") if isinstance(message, dict) else None
        payer_id_raw = sender.get("id") if isinstance(sender, dict) else None
        if (
            not isinstance(invoice_payload, str) or not 1 <= len(invoice_payload) <= 128
            or not isinstance(transaction_id, str) or not 1 <= len(transaction_id) <= 160
            or provider_charge_id is not None
            and (not isinstance(provider_charge_id, str) or not 1 <= len(provider_charge_id) <= 160)
            or isinstance(callback_amount, bool) or not isinstance(callback_amount, int)
            or not isinstance(callback_currency, str)
            or not isinstance(payer_id_raw, (int, str)) or isinstance(payer_id_raw, bool)
            or not _BOT_FORM_USER_ID.fullmatch(str(payer_id_raw))
        ):
            return {"ok": True}
        payer_id = str(payer_id_raw)
        payment = db.scalar(
            select(FormPaymentRecord)
            .where(FormPaymentRecord.invoice_payload == invoice_payload)
            .with_for_update()
        )
        if payment is None or payment.method != "bale_wallet":
            return {"ok": True}
        prior_transaction = db.scalar(
            select(FormPaymentTransactionRecord).where(
                FormPaymentTransactionRecord.transaction_id == transaction_id
            )
        )
        if prior_transaction is not None and prior_transaction.payment_id != payment.id:
            return {"ok": True}
        if prior_transaction is not None and prior_transaction.status in {"verified", "duplicate"}:
            return {"ok": True}
        prior_provider_charge = None
        if provider_charge_id:
            prior_provider_charge = db.scalar(
                select(FormPaymentTransactionRecord).where(
                    FormPaymentTransactionRecord.provider_charge_id == provider_charge_id
                )
            )
            if prior_provider_charge is not None and prior_provider_charge.payment_id != payment.id:
                return {"ok": True}
            if prior_provider_charge is not None and prior_provider_charge.status in {"verified", "duplicate"}:
                return {"ok": True}

        try:
            inquiry = await asyncio.to_thread(
                call_bale_payment_api,
                cfg,
                "inquireTransaction",
                {"transaction_id": transaction_id},
            )
        except BalePaymentAPIError as error:
            # Provider outages must be retried by the webhook sender; never infer payment from the callback.
            raise HTTPException(503, detail={"code": error.code}) from None
        transaction = inquiry.get("result")
        if not isinstance(transaction, dict):
            return {"ok": True}
        transaction_status = transaction.get("status")
        transaction_result_id = transaction.get("id")
        provider_user_id = transaction.get("userID")
        provider_amount = transaction.get("amount")
        if transaction_status == "pending":
            raise HTTPException(503, detail={"code": "bale_transaction_pending"})
        if transaction_status != "paid" or str(transaction_result_id) != transaction_id:
            return {"ok": True}

        amount_matches = (
            isinstance(provider_amount, int) and not isinstance(provider_amount, bool)
            and provider_amount == payment.amount == callback_amount
        )
        currency_matches = callback_currency == payment.currency == "IRR"
        payer_matches = str(provider_user_id) == payer_id
        payment_data_matches = amount_matches and currency_matches and payer_matches
        already_paid = payment.status == "paid"
        duplicate_charge = already_paid and payment.transaction_id != transaction_id
        transaction_record = prior_transaction or prior_provider_charge
        transaction_amount = (
            callback_amount if 0 <= callback_amount <= 2_000_000_000 else payment.amount
        )
        transaction_row = transaction_record or FormPaymentTransactionRecord(
            id=str(uuid.uuid4()),
            payment_id=payment.id,
            transaction_id=transaction_id,
            provider_charge_id=provider_charge_id,
            amount=transaction_amount,
            currency=callback_currency[:8],
            payer_bale_user_id=payer_id,
            status="needs_review",
        )
        if transaction_record is None:
            db.add(transaction_row)
        transaction_row.amount = transaction_amount
        transaction_row.currency = callback_currency[:8]
        transaction_row.payer_bale_user_id = payer_id
        if provider_charge_id and transaction_row.provider_charge_id is None:
            transaction_row.provider_charge_id = provider_charge_id

        def finalize_bale_payment() -> bool:
            form = db.scalar(
                select(FormRecord)
                .options(selectinload(FormRecord.fields))
                .where(FormRecord.id == payment.form_id)
                .with_for_update()
            )
            draft = db.scalar(
                select(FormResponseDraftRecord)
                .where(FormResponseDraftRecord.id == payment.draft_id)
                .with_for_update()
            )
            now_inner = _utc_now()
            if (
                form is None or draft is None or form.status != "published"
                or form.version != payment.form_version or draft.form_version != payment.form_version
                or payment.status not in {"pending", "paid_review"}
                or payment.expires_at is None or _as_utc(payment.expires_at) <= now_inner
                or not cfg.form_bale_payments_ready
                or "bale_wallet" not in _selected_form_payment_methods(form)
            ):
                return False
            if db.scalar(select(FormResponseRecord.id).where(FormResponseRecord.draft_id == draft.id)):
                return False
            purchase_recording: EventRecordingRecord | None = None
            if _form_is_purchase(form):
                # The access right needs an account; the product must still be on sale.
                purchase_recording = _purchase_recording_for_form(db, form, for_update=True)
                if draft.account_id is None or purchase_recording is None or purchase_recording.status != "published":
                    return False
            form_settings = form.settings if isinstance(form.settings, dict) else {}
            try:
                normalized_answers = validate_answers(form.fields, draft.answers or {}, partial=False)
                normalized_companions = validate_companions(
                    form.fields, draft.companions or [], form_settings, partial=False
                )
                stored_selection = _payment_selection_for_recalculation(
                    payment.selection, form_settings
                )
                if stored_selection is None:
                    return False
                calculated = calculate_payment_amount(
                    form_settings,
                    stored_selection,
                    party_count=1 + len(normalized_companions),
                )
            except (AnswerValidationError, PaymentConfigurationError):
                return False
            if (
                calculated["amount"] != payment.amount
                or calculated["currency"] != payment.currency
                or calculated["party_count"] != payment.party_count
            ):
                return False
            cap_inner = _count_setting(form_settings.get("cap", 0))
            accepted_inner, _ = _response_counts(db, form.id)
            other_holds = _active_bale_payment_holds(db, form.id, exclude_payment_id=payment.id)
            party_count = 1 + len(normalized_companions)
            if cap_inner > 0 and accepted_inner + other_holds + party_count > cap_inner:
                return False
            child_statuses = _response_party_statuses(
                form, accepted_inner + other_holds, 0, party_count
            )
            paid_summary = dict(calculated)
            paid_summary.update({"method": "bale_wallet", "status": "paid"})
            event_snapshot = _form_ticket_event_snapshot(db, form)
            response_status = child_statuses.pop(0)
            response_record = FormResponseRecord(
                id=str(uuid.uuid4()),
                form_id=form.id,
                draft_id=draft.id,
                form_version=form.version,
                status=response_status,
                answers=normalized_answers,
                companions=[],
                form_snapshot=response_snapshot(
                    form, event=event_snapshot, status=response_status, payment=paid_summary
                ),
            )
            db.add(response_record)
            db.flush()
            added_by_name = _form_ticket_name(response_record)
            for index, (guest, guest_status) in enumerate(zip(normalized_companions, child_statuses)):
                child_draft = FormResponseDraftRecord(
                    id=str(uuid.uuid4()),
                    form_id=form.id,
                    form_version=form.version,
                    token_hash=token_digest(new_token()),
                    answers=guest["answers"],
                    companions=[],
                    has_unsaved_changes=False,
                    expires_at=now_inner + timedelta(seconds=cfg.response_draft_ttl_seconds),
                )
                child_response = FormResponseRecord(
                    id=str(uuid.uuid4()),
                    form_id=form.id,
                    draft_id=child_draft.id,
                    form_version=form.version,
                    status=guest_status,
                    answers=guest["answers"],
                    companions=[],
                    registrant_name=guest["name"],
                    registrant_mobile=guest["mobile"],
                    added_by_response_id=response_record.id,
                    companion_index=index,
                    added_by_name=added_by_name,
                    form_snapshot=response_snapshot(
                        form, event=event_snapshot, status=guest_status, payment=paid_summary
                    ),
                )
                db.add(child_draft)
                db.add(child_response)
            draft.answers = {}
            draft.companions = []
            draft.has_unsaved_changes = False
            draft.updated_at = now_inner
            draft.expires_at = now_inner + timedelta(seconds=cfg.response_draft_ttl_seconds)
            payment.response_id = response_record.id
            payment.status = "paid"
            payment.transaction_id = transaction_id
            payment.provider_charge_id = provider_charge_id
            payment.payer_bale_user_id = payer_id
            payment.updated_at = now_inner
            if purchase_recording is not None and draft.account_id:
                db.flush()
                _finalize_purchase(
                    db, form=form, response=response_record, payment=payment, account_id=draft.account_id,
                    now=now_inner, actor=("system", "bale_webhook"), reason="bale_wallet_verified",
                )
            return True

        if already_paid and payment.transaction_id == transaction_id:
            transaction_row.status = "verified" if payment_data_matches else "needs_review"
            db.commit()
            return {"ok": True}
        if already_paid and duplicate_charge:
            transaction_row.status = "duplicate" if payment_data_matches else "needs_review"
            db.commit()
            return {"ok": True}
        can_finalize = payment_data_matches and finalize_bale_payment()
        if can_finalize:
            transaction_row.status = "verified"
            db.commit()
            return {"ok": True}
        transaction_row.status = "needs_review"
        if payment.status != "paid":
            payment.status = "paid_review"
            payment.transaction_id = transaction_id
            payment.provider_charge_id = provider_charge_id
            payment.payer_bale_user_id = payer_id
            payment.updated_at = _utc_now()
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # Another delivery may have committed this charge first.
        return {"ok": True}

    @app.get("/api/bot/forms/public")
    def list_bot_public_forms(
        request: Request,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        """List only currently open, publishable, free forms for the Bale bot."""
        cfg: Settings = _runtime_settings(db, request.app.state.settings)
        records = db.scalars(
            select(FormRecord)
            .options(selectinload(FormRecord.fields))
            .where(FormRecord.status == "published")
            .order_by(FormRecord.updated_at.desc(), FormRecord.id)
            .limit(100)
        ).all()
        items = []
        for form in records:
            if publication_issues(form, bale_ready=cfg.form_bale_payments_ready) or form_has_companions(form) or _form_uses_payment(form) or _form_is_purchase(form):
                continue
            if _event_registration_block(db, form) is not None:
                continue
            accepted, waitlisted = _response_counts(db, form.id)
            if _capacity_is_full(form, accepted + _active_bale_payment_holds(db, form.id), waitlisted):
                continue
            items.append({
                "id": form.id,
                "name": form.title,
                "model": form.model,
                "need": form.need,
                "version": form.version,
            })
        return {"source": "shared_server_database", "items": items}

    @app.get("/api/bot/forms/mine")
    def list_my_bot_form_responses(
        http_response: Response,
        bale_user_id: str = Query(..., min_length=1, max_length=20),
        page: int = Query(0, ge=0, le=100_000),
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        http_response.headers["Cache-Control"] = "no-store"
        user_id = validate_bot_form_user_id(bale_user_id)
        history_filter = (
            bot_form_record_scope(db, user_id),
            FormResponseRecord.status.in_(("accepted", "waitlisted")),
        )
        joined = select(FormResponseRecord).join(
            FormResponseDraftRecord,
            FormResponseDraftRecord.id == FormResponseRecord.draft_id,
        ).where(*history_filter)
        total = int(db.scalar(
            select(func.count(FormResponseRecord.id))
            .join(
                FormResponseDraftRecord,
                FormResponseDraftRecord.id == FormResponseRecord.draft_id,
            )
            .where(*history_filter)
        ) or 0)
        pages = (total + _BOT_FORM_HISTORY_PAGE_SIZE - 1) // _BOT_FORM_HISTORY_PAGE_SIZE
        page = min(page, max(0, pages - 1))
        records = db.scalars(
            joined.order_by(FormResponseRecord.created_at.desc(), FormResponseRecord.id.desc())
            .limit(_BOT_FORM_HISTORY_PAGE_SIZE)
            .offset(page * _BOT_FORM_HISTORY_PAGE_SIZE)
        ).all()
        items = []
        for record in records:
            snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
            answers = record.answers if isinstance(record.answers, dict) else {}
            items.append({
                "id": record.id,
                "form_id": record.form_id,
                "form_name": snapshot.get("name") if isinstance(snapshot.get("name"), str) else "فرم",
                "status": record.status,
                "form_version": record.form_version,
                "answer_count": len(answers),
                "created_at": _as_utc(record.created_at).isoformat(),
            })
        return {
            "source": "shared_server_database",
            "items": items,
            "total": total,
            "page": page,
            "pages": pages,
            "page_size": _BOT_FORM_HISTORY_PAGE_SIZE,
        }

    @app.get("/api/bot/forms/responses/{response_id}")
    def get_my_bot_form_response(
        response_id: str,
        http_response: Response,
        bale_user_id: str = Query(..., min_length=1, max_length=20),
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        http_response.headers["Cache-Control"] = "no-store"
        user_id = validate_bot_form_user_id(bale_user_id)
        if not _BOT_FORM_RESPONSE_ID.fullmatch(response_id):
            raise HTTPException(422, "invalid_bot_form_response_id")
        record = db.scalar(
            select(FormResponseRecord)
            .join(FormResponseDraftRecord, FormResponseDraftRecord.id == FormResponseRecord.draft_id)
            .where(
                FormResponseRecord.id == response_id,
                bot_form_record_scope(db, user_id),
            )
        )
        if record is None:
            raise HTTPException(404, "bot_form_response_not_found")
        return {
            "source": "shared_server_database",
            "response": {
                "id": record.id,
                "form_id": record.form_id,
                "status": record.status,
                "form_version": record.form_version,
                "created_at": _as_utc(record.created_at).isoformat(),
                "form_snapshot": record.form_snapshot,
                "answers": record.answers,
            },
        }

    @app.get("/api/bot/admin/forms")
    def list_bot_admin_forms(
        http_response: Response,
        request: Request,
        bale_user_id: str = Query(..., min_length=1, max_length=20),
        page: int = Query(0, ge=0, le=100_000),
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = request.app.state.settings
        http_response.headers["Cache-Control"] = "no-store"
        require_bot_form_response_reader(db, cfg, bale_user_id)
        total = int(
            db.scalar(
                select(func.count(FormRecord.id)).where(FormRecord.owner_id == cfg.owner_id)
            )
            or 0
        )
        page_size = _BOT_FORM_HISTORY_PAGE_SIZE
        pages = (total + page_size - 1) // page_size
        page = min(page, max(0, pages - 1))
        forms = db.scalars(
            select(FormRecord)
            .where(FormRecord.owner_id == cfg.owner_id)
            .order_by(FormRecord.updated_at.desc(), FormRecord.id)
            .limit(page_size)
            .offset(page * page_size)
        ).all()
        form_ids = [form.id for form in forms]
        response_counts: dict[str, int] = {}
        if form_ids:
            counts = db.execute(
                select(FormResponseRecord.form_id, func.count(FormResponseRecord.id))
                .where(FormResponseRecord.form_id.in_(form_ids))
                .group_by(FormResponseRecord.form_id)
            ).all()
            response_counts = {form_id: int(count) for form_id, count in counts}
        return {
            "source": "shared_server_database",
            "items": [
                {
                    "id": form.id,
                    "name": form.title,
                    "status": form.status,
                    "version": form.version,
                    "response_count": response_counts.get(form.id, 0),
                }
                for form in forms
            ],
            "total": total,
            "page": page,
            "pages": pages,
            "page_size": page_size,
        }

    @app.get("/api/bot/admin/forms/{form_id}/responses")
    def list_bot_admin_form_responses(
        form_id: str,
        http_response: Response,
        request: Request,
        bale_user_id: str = Query(..., min_length=1, max_length=20),
        page: int = Query(0, ge=0, le=100_000),
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = request.app.state.settings
        http_response.headers["Cache-Control"] = "no-store"
        require_bot_form_response_reader(db, cfg, bale_user_id)
        if not _BOT_FORM_RESPONSE_ID.fullmatch(form_id):
            raise HTTPException(422, "invalid_bot_form_id")
        form = get_owned_form(db, cfg.owner_id, form_id)
        total = int(
            db.scalar(
                select(func.count(FormResponseRecord.id)).where(
                    FormResponseRecord.form_id == form.id
                )
            )
            or 0
        )
        page_size = _BOT_FORM_HISTORY_PAGE_SIZE
        pages = (total + page_size - 1) // page_size
        page = min(page, max(0, pages - 1))
        records = db.scalars(
            select(FormResponseRecord)
            .where(FormResponseRecord.form_id == form.id)
            .order_by(FormResponseRecord.created_at.desc(), FormResponseRecord.id.desc())
            .limit(page_size)
            .offset(page * page_size)
        ).all()
        return {
            "source": "shared_server_database",
            "items": [
                {
                    "id": record.id,
                    "form_id": record.form_id,
                    "form_name": form.title,
                    "status": record.status,
                    "form_version": record.form_version,
                    "answer_count": len(record.answers) if isinstance(record.answers, dict) else 0,
                    "created_at": _as_utc(record.created_at).isoformat(),
                }
                for record in records
            ],
            "total": total,
            "page": page,
            "pages": pages,
            "page_size": page_size,
        }

    @app.get("/api/bot/admin/responses/{response_id}")
    def get_bot_admin_form_response(
        response_id: str,
        http_response: Response,
        request: Request,
        bale_user_id: str = Query(..., min_length=1, max_length=20),
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = request.app.state.settings
        http_response.headers["Cache-Control"] = "no-store"
        require_bot_form_response_reader(db, cfg, bale_user_id)
        if not _BOT_FORM_RESPONSE_ID.fullmatch(response_id):
            raise HTTPException(422, "invalid_bot_form_response_id")
        record = db.get(FormResponseRecord, response_id)
        if record is None:
            raise HTTPException(404, "bot_form_response_not_found")
        get_owned_form(db, cfg.owner_id, record.form_id)
        return {
            "source": "shared_server_database",
            "response": {
                "id": record.id,
                "form_id": record.form_id,
                "status": record.status,
                "form_version": record.form_version,
                "created_at": _as_utc(record.created_at).isoformat(),
                "form_snapshot": record.form_snapshot,
                "answers": record.answers,
            },
        }

    @app.post("/api/bot/forms/{form_id}/draft")
    async def create_bot_form_draft(
        form_id: str,
        request: Request,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = _runtime_settings(db, request.app.state.settings)
        payload = await _read_json_object(request, cfg.max_request_bytes)
        if set(payload) != {"bale_user_id", "session_key"}:
            raise HTTPException(400, "invalid_bot_form_draft_payload")
        bale_user_id, session_key = validate_bot_form_identity(
            payload.get("bale_user_id"), payload.get("session_key")
        )
        if _bale_user_is_blocked(db, bale_user_id):
            raise HTTPException(403, ACCOUNT_BLOCKED_DETAIL)
        enforce_bot_form_write_limit(
            db, form_id, bale_user_id, cfg, cfg.response_draft_write_limit_per_minute
        )
        form = ensure_writeable_public_form(
            db, form_id, bale_ready=cfg.form_bale_payments_ready
        )
        _cleanup_expired_public_drafts(db)
        draft = bot_form_draft_for_session(db, form_id, bale_user_id, session_key, lock=True)
        if draft is None:
            accepted, waitlisted = _response_counts(db, form_id)
            if _capacity_is_full(form, accepted + _active_bale_payment_holds(db, form.id), waitlisted):
                raise HTTPException(410, detail={"code": "form_full"})
            now = _utc_now()
            draft = FormResponseDraftRecord(
                id=str(uuid.uuid4()),
                form_id=form_id,
                form_version=form.version,
                token_hash=bot_form_token_hash(form_id, bale_user_id, session_key),
                bot_bale_user_id=bale_user_id,
                answers={},
                companions=[],
                has_unsaved_changes=False,
                expires_at=now + timedelta(seconds=cfg.response_draft_ttl_seconds),
            )
            db.add(draft)
            db.flush()
        else:
            associate_bot_form_draft(draft, bale_user_id)
            if draft.response is None and draft.form_version != form.version:
                draft.form_version = form.version
                draft.answers = {}
                draft.companions = []
                draft.has_unsaved_changes = False
            draft.updated_at = _utc_now()
            draft.expires_at = _utc_now() + timedelta(seconds=cfg.response_draft_ttl_seconds)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            draft = bot_form_draft_for_session(db, form_id, bale_user_id, session_key, lock=True)
            if draft is None:
                raise HTTPException(409, "bot_form_draft_conflict") from None
            if associate_bot_form_draft(draft, bale_user_id):
                db.commit()
            form = get_bot_published_form(db, form_id, bale_ready=cfg.form_bale_payments_ready)
        return bot_form_state(db, form, draft)

    @app.post("/api/bot/forms/{form_id}/draft/state")
    async def get_bot_form_draft(
        form_id: str,
        request: Request,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = _runtime_settings(db, request.app.state.settings)
        payload = await _read_json_object(request, cfg.max_request_bytes)
        if set(payload) != {"bale_user_id", "session_key"}:
            raise HTTPException(400, "invalid_bot_form_draft_payload")
        bale_user_id, session_key = validate_bot_form_identity(
            payload.get("bale_user_id"), payload.get("session_key")
        )
        form = get_bot_published_form(db, form_id, bale_ready=cfg.form_bale_payments_ready)
        draft = bot_form_draft_for_session(db, form_id, bale_user_id, session_key, lock=True)
        if draft is None:
            raise HTTPException(404, "bot_form_draft_not_found")
        if draft.response is None and _as_utc(draft.expires_at) <= _utc_now():
            raise HTTPException(410, "bot_form_draft_expired")
        draft_changed = associate_bot_form_draft(draft, bale_user_id)
        if draft.response is None and draft.form_version != form.version:
            draft.form_version = form.version
            draft.answers = {}
            draft.companions = []
            draft.has_unsaved_changes = False
            draft.updated_at = _utc_now()
            draft.expires_at = _utc_now() + timedelta(
                seconds=request.app.state.settings.response_draft_ttl_seconds
            )
            draft_changed = True
        if draft_changed:
            db.commit()
        accepted, waitlisted = _response_counts(db, form_id)
        if draft.response is None and _capacity_is_full(
            form, accepted + _active_bale_payment_holds(db, form_id), waitlisted
        ):
            raise HTTPException(410, detail={"code": "form_full"})
        return bot_form_state(db, form, draft)

    @app.patch("/api/bot/forms/{form_id}/draft")
    async def save_bot_form_answer(
        form_id: str,
        request: Request,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = _runtime_settings(db, request.app.state.settings)
        payload = await _read_json_object(request, cfg.max_request_bytes)
        identity_keys = {"bale_user_id", "session_key", "field_id"}
        set_answer = set(payload) == identity_keys | {"value"}
        remove_answer = set(payload) == identity_keys | {"remove"} and payload.get("remove") is True
        if not (set_answer or remove_answer):
            raise HTTPException(400, "invalid_bot_form_answer_payload")
        bale_user_id, session_key = validate_bot_form_identity(
            payload.get("bale_user_id"), payload.get("session_key")
        )
        field_id = payload.get("field_id")
        if not isinstance(field_id, str) or not 1 <= len(field_id) <= 80:
            raise HTTPException(422, "invalid_bot_form_field_id")
        enforce_bot_form_write_limit(
            db, form_id, bale_user_id, cfg, cfg.response_draft_write_limit_per_minute
        )
        form = ensure_writeable_public_form(
            db, form_id, bale_ready=cfg.form_bale_payments_ready
        )
        draft = bot_form_draft_for_session(db, form_id, bale_user_id, session_key, lock=True)
        if draft is None:
            raise HTTPException(404, "bot_form_draft_not_found")
        if draft.response is not None:
            raise HTTPException(409, "bot_form_response_already_submitted")
        if _as_utc(draft.expires_at) <= _utc_now():
            raise HTTPException(410, "bot_form_draft_expired")
        if draft.form_version != form.version:
            raise HTTPException(409, "form_version_changed")
        associate_bot_form_draft(draft, bale_user_id)
        if field_id not in {field.field_key for field in form.fields}:
            raise HTTPException(422, "unknown_answer_field")
        answers, _ = draft_answers(db, draft)
        candidate = dict(answers)
        if remove_answer:
            candidate.pop(field_id, None)
        else:
            candidate[field_id] = payload["value"]
        try:
            normalized = validate_answers(form.fields, candidate, partial=True)
        except AnswerValidationError as error:
            raise HTTPException(
                422,
                detail={"code": "answer_validation_failed", "errors": error.errors},
            ) from None
        now = _utc_now()
        draft.answers = normalized
        draft.has_unsaved_changes = True
        draft.updated_at = now
        draft.expires_at = now + timedelta(seconds=cfg.response_draft_ttl_seconds)
        db.commit()
        return bot_form_state(db, form, draft)

    @app.delete("/api/bot/forms/{form_id}/draft")
    async def delete_bot_form_draft(
        form_id: str,
        request: Request,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = request.app.state.settings
        payload = await _read_json_object(request, cfg.max_request_bytes)
        if set(payload) != {"bale_user_id", "session_key"}:
            raise HTTPException(400, "invalid_bot_form_draft_payload")
        bale_user_id, session_key = validate_bot_form_identity(
            payload.get("bale_user_id"), payload.get("session_key")
        )
        enforce_bot_form_write_limit(
            db, form_id, bale_user_id, cfg, cfg.response_draft_write_limit_per_minute
        )
        draft = bot_form_draft_for_session(db, form_id, bale_user_id, session_key, lock=True)
        if draft is None:
            return {"deleted": False, "submitted": False}
        submitted = draft.response is not None
        if not submitted:
            db.delete(draft)
            db.commit()
        return {"deleted": not submitted, "submitted": submitted}

    @app.post("/api/bot/forms/{form_id}/responses")
    async def submit_bot_form_response(
        form_id: str,
        request: Request,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = _runtime_settings(db, request.app.state.settings)
        payload = await _read_json_object(request, cfg.max_request_bytes)
        if set(payload) != {"bale_user_id", "session_key"}:
            raise HTTPException(400, "invalid_bot_form_response_payload")
        bale_user_id, session_key = validate_bot_form_identity(
            payload.get("bale_user_id"), payload.get("session_key")
        )
        if _bale_user_is_blocked(db, bale_user_id):
            raise HTTPException(403, ACCOUNT_BLOCKED_DETAIL)
        enforce_bot_form_write_limit(
            db, form_id, bale_user_id, cfg, cfg.response_submit_limit_per_minute
        )
        draft = bot_form_draft_for_session(db, form_id, bale_user_id, session_key)
        if draft is None:
            raise HTTPException(404, "bot_form_draft_not_found")
        owner_changed = associate_bot_form_draft(draft, bale_user_id)
        existing = db.scalar(
            select(FormResponseRecord).where(FormResponseRecord.draft_id == draft.id)
        )
        if existing is not None:
            if owner_changed:
                db.commit()
            return {
                "accepted": True,
                "already_submitted": True,
                "response_id": existing.id,
                "status": existing.status,
                "form_version": existing.form_version,
            }
        if _as_utc(draft.expires_at) <= _utc_now():
            raise HTTPException(410, "bot_form_draft_expired")
        form = ensure_writeable_public_form(
            db, form_id, bale_ready=cfg.form_bale_payments_ready
        )
        draft = bot_form_draft_for_session(db, form_id, bale_user_id, session_key, lock=True)
        if draft is None:
            raise HTTPException(404, "bot_form_draft_not_found")
        owner_changed = associate_bot_form_draft(draft, bale_user_id)
        existing = db.scalar(
            select(FormResponseRecord).where(FormResponseRecord.draft_id == draft.id)
        )
        if existing is not None:
            if owner_changed:
                db.commit()
            return {
                "accepted": True,
                "already_submitted": True,
                "response_id": existing.id,
                "status": existing.status,
                "form_version": existing.form_version,
            }
        if _as_utc(draft.expires_at) <= _utc_now():
            raise HTTPException(410, "bot_form_draft_expired")
        if draft.form_version != form.version:
            raise HTTPException(409, "form_version_changed")
        answers, _ = draft_answers(db, draft)
        try:
            normalized = validate_answers(form.fields, answers, partial=False)
        except AnswerValidationError as error:
            raise HTTPException(
                422,
                detail={"code": "answer_validation_failed", "errors": error.errors},
            ) from None

        accepted_count, waitlisted_count = _response_counts(db, form_id)
        if _capacity_is_full(
            form, accepted_count + _active_bale_payment_holds(db, form_id), waitlisted_count
        ):
            raise HTTPException(410, detail={"code": "form_full"})
        settings = form.settings if isinstance(form.settings, dict) else {}
        cap = _count_setting(settings.get("cap", 0), fallback=0)
        wait_limit = _count_setting(settings.get("wait", 0), fallback=0)
        status = "accepted"
        if cap > 0 and accepted_count >= cap:
            if wait_limit <= 0 or waitlisted_count >= wait_limit:
                raise HTTPException(410, detail={"code": "form_full"})
            status = "waitlisted"
        response_record = FormResponseRecord(
            id=str(uuid.uuid4()),
            form_id=form_id,
            draft_id=draft.id,
            form_version=form.version,
            status=status,
            answers=normalized,
            companions=[],
            form_snapshot=response_snapshot(
                form,
                event=_form_ticket_event_snapshot(db, form),
                status=status,
            ),
        )
        now = _utc_now()
        draft.answers = {}
        draft.companions = []
        draft.has_unsaved_changes = False
        draft.updated_at = now
        draft.expires_at = now + timedelta(seconds=cfg.response_draft_ttl_seconds)
        db.add(response_record)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raced_draft = bot_form_draft_for_session(
                db, form_id, bale_user_id, session_key
            )
            raced_response = db.scalar(
                select(FormResponseRecord).where(FormResponseRecord.draft_id == raced_draft.id)
            ) if raced_draft is not None else None
            if raced_response is None:
                raise HTTPException(409, "response_conflict") from None
            response_record = raced_response
            return {
                "accepted": True,
                "already_submitted": True,
                "response_id": response_record.id,
                "status": response_record.status,
                "form_version": response_record.form_version,
            }
        return {
            "accepted": True,
            "already_submitted": False,
            "response_id": response_record.id,
            "status": response_record.status,
            "form_version": response_record.form_version,
        }

    @app.post("/api/bot/forms/{form_id}/responses/{response_id}/ticket")
    async def get_bot_form_ticket(
        form_id: str,
        response_id: str,
        request: Request,
        http_response: Response,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        http_response.headers["Cache-Control"] = "no-store"
        if (
            not _BOT_FORM_RESPONSE_ID.fullmatch(form_id)
            or not _BOT_FORM_RESPONSE_ID.fullmatch(response_id)
        ):
            raise HTTPException(422, "invalid_bot_form_response_id")
        payload = await _read_json_object(request, request.app.state.settings.max_request_bytes)
        if set(payload) != {"bale_user_id"}:
            raise HTTPException(400, "invalid_bot_form_ticket_payload")
        user_id = validate_bot_form_user_id(payload.get("bale_user_id"))
        record = db.scalar(
            select(FormResponseRecord)
            .join(
                FormResponseDraftRecord,
                FormResponseDraftRecord.id == FormResponseRecord.draft_id,
            )
            .where(
                FormResponseRecord.id == response_id,
                FormResponseRecord.form_id == form_id,
                FormResponseDraftRecord.bot_bale_user_id == user_id,
            )
            .options(selectinload(FormResponseRecord.draft))
            .with_for_update()
        )
        if record is None:
            raise HTTPException(404, "bot_form_response_not_found")
        if not _response_payment_approved(db, record):
            raise HTTPException(409, detail={"code": "ticket_payment_not_confirmed"})
        _ensure_form_ticket(record)
        db.commit()
        return _form_ticket_payload(record)

    @app.post("/api/bot/form-tickets/claim")
    async def claim_bot_form_ticket(
        request: Request,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = request.app.state.settings
        payload = await _read_json_object(request, cfg.max_request_bytes)
        if set(payload) != {"bale_user_id", "token"}:
            raise HTTPException(400, "invalid_ticket_claim_payload")
        user_id = validate_bot_form_user_id(payload.get("bale_user_id"))
        if not cfg.bot_service_token:
            raise HTTPException(503, "bot_api_not_configured")
        nonce_hash, token_expiry = _decode_ticket_claim(payload.get("token"), cfg.bot_service_token)
        record = db.scalar(
            select(FormResponseRecord)
            .where(FormResponseRecord.ticket_claim_nonce_hash == nonce_hash)
            .options(selectinload(FormResponseRecord.draft))
            .with_for_update()
        )
        if record is None:
            raise HTTPException(404, "ticket_claim_not_found")
        if (record.ticket_claim_expires_at is None
                or int(_as_utc(record.ticket_claim_expires_at).timestamp()) != token_expiry):
            raise HTTPException(404, "ticket_claim_not_found")
        if _as_utc(record.ticket_claim_expires_at) <= _utc_now():
            raise HTTPException(410, "ticket_claim_expired")
        _ensure_form_ticket(record)
        draft = record.draft
        if draft is None:
            raise HTTPException(404, "ticket_claim_not_found")
        if record.ticket_claimed_by_bale_user_id not in (None, user_id):
            raise HTTPException(409, "ticket_claimed_by_another_account")
        if draft.bot_bale_user_id not in (None, user_id):
            raise HTTPException(409, "ticket_claimed_by_another_account")
        if record.ticket_claimed_by_bale_user_id is None:
            record.ticket_claimed_by_bale_user_id = user_id
            record.ticket_claimed_at = _utc_now()
        if draft.bot_bale_user_id is None:
            draft.bot_bale_user_id = user_id
        _create_public_form_receipt_task(db, record, user_id)
        db.commit()
        if not _response_payment_approved(db, record):
            raise HTTPException(409, detail={"code": "ticket_payment_not_confirmed"})
        return _form_ticket_payload(record)

    @app.post("/api/bot/form-tickets/{response_id}/verify")
    async def verify_bot_form_ticket(
        response_id: str,
        request: Request,
        http_response: Response,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = request.app.state.settings
        http_response.headers["Cache-Control"] = "no-store"
        if not _BOT_FORM_RESPONSE_ID.fullmatch(response_id):
            raise HTTPException(422, "invalid_bot_form_response_id")
        payload = await _read_json_object(request, cfg.max_request_bytes)
        if set(payload) != {"bale_user_id"}:
            raise HTTPException(400, "invalid_bot_form_ticket_payload")
        require_bot_form_response_reader(db, cfg, payload.get("bale_user_id"))
        record = db.scalar(
            select(FormResponseRecord)
            .where(FormResponseRecord.id == response_id)
            .options(selectinload(FormResponseRecord.draft))
            .with_for_update()
        )
        if record is None:
            raise HTTPException(404, "ticket_not_found")
        if not _response_payment_approved(db, record):
            raise HTTPException(409, detail={"code": "ticket_payment_not_confirmed"})
        _ensure_form_ticket(record)
        db.commit()
        result = _form_ticket_payload(record)
        result["checked_in_by_bale_user_id"] = record.ticket_checked_in_by_bale_user_id
        return result

    @app.post("/api/bot/form-tickets/{response_id}/check-in")
    async def check_in_bot_form_ticket(
        response_id: str,
        request: Request,
        http_response: Response,
        _service: None = Depends(require_bot_service),
        db: Session = Depends(get_db),
    ):
        cfg: Settings = request.app.state.settings
        http_response.headers["Cache-Control"] = "no-store"
        if not _BOT_FORM_RESPONSE_ID.fullmatch(response_id):
            raise HTTPException(422, "invalid_bot_form_response_id")
        payload = await _read_json_object(request, cfg.max_request_bytes)
        if set(payload) != {"bale_user_id"}:
            raise HTTPException(400, "invalid_bot_form_ticket_payload")
        user_id = require_bot_form_response_reader(db, cfg, payload.get("bale_user_id"))
        record = db.scalar(
            select(FormResponseRecord)
            .where(FormResponseRecord.id == response_id)
            .options(selectinload(FormResponseRecord.draft))
            .with_for_update()
        )
        if record is None:
            raise HTTPException(404, "ticket_not_found")
        if not _response_payment_approved(db, record):
            raise HTTPException(409, detail={"code": "ticket_payment_not_confirmed"})
        _ensure_form_ticket(record)
        already_checked_in = record.ticket_checked_in_at is not None
        if not already_checked_in:
            record.ticket_checked_in_at = _utc_now()
            record.ticket_checked_in_by_bale_user_id = user_id
        db.commit()
        result = _form_ticket_payload(record)
        result["checked_in_by_bale_user_id"] = record.ticket_checked_in_by_bale_user_id
        result["already_checked_in"] = already_checked_in
        return result

    @app.get("/api/public/forms/{form_id}/draft")
    def get_public_draft(
        form_id: str,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ):
        cfg: Settings = _runtime_settings(db, request.app.state.settings)
        form = get_published_form(db, form_id, bale_ready=cfg.form_bale_payments_ready)
        enforce_public_write_limit(request, db, form_id, cfg, cfg.response_draft_write_limit_per_minute)
        _cleanup_expired_public_drafts(db)
        draft, raw_token = ensure_public_draft(request, db, form)
        bind_public_draft_account(draft, public_write_identity(request, db), db)
        answers, submitted = draft_answers(db, draft)
        companions = draft_companions(db, draft, submitted)
        if submitted is None:
            _raise_if_event_registration_blocked(db, form)
        accepted, waitlisted = _response_counts(db, form_id)
        if submitted is None and _capacity_is_full(
            form,
            accepted + _active_bale_payment_holds(db, form_id, exclude_draft_id=draft.id),
            waitlisted,
        ):
            raise HTTPException(410, detail={"code": "form_full"})
        payment = db.scalar(
            select(FormPaymentRecord)
            .where(FormPaymentRecord.draft_id == draft.id)
            .order_by(FormPaymentRecord.created_at.desc(), FormPaymentRecord.id.desc())
        )
        now = _utc_now()
        if payment is not None and payment.status == "pending" and payment.expires_at and _as_utc(payment.expires_at) <= now:
            payment.status = "expired"
            payment.updated_at = now
        db.commit()
        if raw_token:
            set_public_draft_cookie(response, form_id, raw_token, cfg)
        return {
            "answers": answers,
            "companions": companions,
            "submitted": submitted is not None,
            "status": submitted.status if submitted is not None else "draft",
            "tracking_code": _form_tracking_code(submitted) if submitted is not None else None,
            "ticket_type": _form_response_ticket_type(submitted) if submitted is not None else None,
            "receipt_uploaded": bool(
                submitted is not None
                and (
                    submitted.receipt_review_task_id is not None
                    or submitted.receipt_upload is not None
                )
            ),
            "payment_intent": (
                {
                    "id": payment.id,
                    "method": payment.method,
                    "status": payment.status,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "invoice_url": payment.invoice_url,
                    "selection": payment.selection if isinstance(payment.selection, dict) else None,
                }
                if payment is not None else None
            ),
            "form_version": draft.form_version,
        }

    @app.patch("/api/public/forms/{form_id}/draft")
    async def save_public_draft(
        form_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        _same_origin(request)
        cfg: Settings = _runtime_settings(db, request.app.state.settings)
        payload = await _read_json_object(request, cfg.max_request_bytes)
        if set(payload) not in ({"answers"}, {"answers", "companions"}):
            raise HTTPException(400, "invalid_draft_payload")
        check_public_write_target(db, form_id, bale_ready=cfg.form_bale_payments_ready)
        enforce_public_write_limit(request, db, form_id, cfg, cfg.response_draft_write_limit_per_minute)
        form = ensure_writeable_public_form(
            db, form_id, allow_companions=True, allow_payments=True,
            bale_ready=cfg.form_bale_payments_ready
        )
        draft = public_draft_for_cookie(request, db, form_id)
        if draft is None:
            raise HTTPException(401, "response_draft_required")
        if draft.form_version != form.version:
            raise HTTPException(409, "form_version_changed")
        bind_public_draft_account(draft, public_write_identity(request, db), db)
        active_payment = db.scalar(
            select(FormPaymentRecord).where(
                FormPaymentRecord.draft_id == draft.id,
                FormPaymentRecord.method == "bale_wallet",
                FormPaymentRecord.status == "pending",
                FormPaymentRecord.expires_at > _utc_now(),
            )
        )
        if active_payment is not None:
            raise HTTPException(409, detail={"code": "payment_intent_pending"})
        try:
            normalized = validate_answers(form.fields, payload["answers"], partial=True)
            settings = form.settings if isinstance(form.settings, dict) else {}
            normalized_companions = validate_companions(
                form.fields, payload.get("companions", []), settings, partial=True
            )
        except AnswerValidationError as error:
            raise HTTPException(
                422,
                detail={"code": "answer_validation_failed", "errors": error.errors},
            ) from None
        now = _utc_now()
        draft.answers = normalized
        draft.companions = normalized_companions
        draft.has_unsaved_changes = True
        draft.updated_at = now
        draft.expires_at = now + timedelta(seconds=cfg.response_draft_ttl_seconds)
        db.commit()
        return {"saved": True, "saved_at": now.isoformat(), "form_version": form.version}

    @app.post("/api/public/forms/{form_id}/responses")
    async def submit_public_response(
        form_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        _same_origin(request)
        cfg: Settings = _runtime_settings(db, request.app.state.settings)
        payload = await _read_json_object(request, cfg.max_request_bytes)
        allowed_response_keys = {"answers"}
        if not isinstance(payload, dict) or "answers" not in payload:
            raise HTTPException(400, "invalid_response_payload")
        if "companions" in payload:
            allowed_response_keys.add("companions")
        if "payment" in payload:
            allowed_response_keys.add("payment")
        if set(payload) != allowed_response_keys:
            raise HTTPException(400, "invalid_response_payload")
        check_public_write_target(db, form_id, bale_ready=cfg.form_bale_payments_ready)
        enforce_public_write_limit(request, db, form_id, cfg, cfg.response_submit_limit_per_minute)
        form = ensure_writeable_public_form(
            db, form_id, allow_companions=True, allow_payments=True,
            bale_ready=cfg.form_bale_payments_ready
        )
        draft = public_draft_for_cookie(request, db, form_id)
        if draft is None:
            raise HTTPException(401, "response_draft_required")
        if draft.form_version != form.version:
            raise HTTPException(409, "form_version_changed")
        purchase_identity = _require_purchase_account(request, db, form)
        account_linked = bind_public_draft_account(draft, purchase_identity, db)
        purchase_recording: EventRecordingRecord | None = None
        if _form_is_purchase(form):
            purchase_recording = _purchase_recording_for_form(db, form, for_update=True)
            if purchase_recording is None or purchase_recording.status != "published":
                raise HTTPException(409, detail={"code": "recording_not_on_sale"})
            current_access = recordings_mod.access_for(db, purchase_recording.id, draft.account_id)
            if recordings_mod.access_state(current_access, _utc_now()) == "active":
                raise HTTPException(409, detail={"code": "access_already_active", "recording_id": purchase_recording.id})
        try:
            normalized = validate_answers(form.fields, payload["answers"], partial=False)
            settings = form.settings if isinstance(form.settings, dict) else {}
            normalized_companions = validate_companions(
                form.fields, payload.get("companions", []), settings, partial=False
            )
        except AnswerValidationError as error:
            raise HTTPException(
                422,
                detail={"code": "answer_validation_failed", "errors": error.errors},
            ) from None

        payment_summary: dict[str, Any] | None = None
        payment_payload = payload.get("payment")
        enabled_payment_methods = _selected_form_payment_methods(form)
        financial_settings = form.settings if isinstance(form.settings, dict) else {}
        has_financial_items = bool(
            isinstance(financial_settings.get("fin"), list) and financial_settings.get("fin")
        )
        if payment_payload is not None:
            if (
                not isinstance(payment_payload, dict)
                or set(payment_payload) != {"method", "selection"}
                or payment_payload.get("method") != "card_transfer"
                or "card_transfer" not in enabled_payment_methods
            ):
                raise HTTPException(422, detail={"code": "payment_method_not_available"})
            try:
                payment_summary = calculate_payment_amount(
                    financial_settings,
                    payment_payload.get("selection"),
                    party_count=1 + len(normalized_companions),
                )
            except PaymentConfigurationError as error:
                raise HTTPException(422, detail={"code": error.code}) from None
            if payment_summary["amount"] > cfg.form_payment_max_amount:
                raise HTTPException(422, detail={"code": "payment_amount_exceeds_limit"})
            payment_summary["method"] = "card_transfer"
            payment_summary["status"] = "awaiting_receipt"
            if financial_settings.get("receiptReviewRequired") is not True:
                raise HTTPException(422, detail={"code": "card_transfer_receipt_required"})
        elif has_financial_items:
            raise HTTPException(422, detail={"code": "payment_method_required"})
        elif "card_transfer" in enabled_payment_methods and financial_settings.get("receiptReviewRequired") is True:
            # Free/manual-receipt forms keep the legacy receipt behavior without asserting a payment.
            payment_summary = None

        existing = db.scalar(
            select(FormResponseRecord).where(FormResponseRecord.draft_id == draft.id)
        )
        existing_payment = (
            db.scalar(
                select(FormPaymentRecord)
                .where(FormPaymentRecord.response_id == existing.id)
                .with_for_update()
            )
            if existing is not None else None
        )
        if existing is not None and existing_payment is not None and existing_payment.status in {"receipt_submitted", "paid_manual"}:
            if account_linked:
                db.commit()
            return {
                "accepted": True,
                "status": existing.status,
                "purpose": form.purpose,
                "purchase": _purchase_state_view(db, form, draft.account_id, _utc_now()) if purchase_recording is not None else None,
                "tracking_code": _form_tracking_code(existing),
                "ticket_type": _form_response_ticket_type(existing),
                "receipt_uploaded": existing.receipt_upload is not None or existing.receipt_review_task_id is not None,
                "payment_status": existing_payment.status,
                "payment_id": existing_payment.id,
                "saved_at": _as_utc(existing.updated_at).isoformat(),
                "form_version": existing.form_version,
                "registrants_count": 1 + len(normalized_companions),
                "message": "پاسخ این نشست قبلاً ثبت شده است.",
            }
        if purchase_recording is not None:
            _reject_duplicate_purchase_order(
                db, purchase_recording, draft.account_id, own_response_id=existing.id if existing is not None else None,
            )
        pending_intents = db.scalars(
            select(FormPaymentRecord)
            .where(
                FormPaymentRecord.draft_id == draft.id,
                FormPaymentRecord.method == "bale_wallet",
                FormPaymentRecord.status == "pending",
            )
            .with_for_update()
        ).all()
        for pending_intent in pending_intents:
            pending_intent.status = "cancelled"
            pending_intent.updated_at = _utc_now()
        accepted_count, waitlisted_count = _response_counts(db, form_id)
        previous_children: Sequence[FormResponseRecord] = []
        if existing is not None:
            previous_children = db.scalars(
                select(FormResponseRecord).where(
                    FormResponseRecord.added_by_response_id == existing.id
                )
            ).all()
            accepted_count -= sum(child.status == "accepted" for child in previous_children)
            waitlisted_count -= sum(child.status == "waitlisted" for child in previous_children)

        new_party_count = len(normalized_companions) if existing is not None else len(normalized_companions) + 1
        payment_holds = _active_bale_payment_holds(db, form_id)
        if payment_summary is not None and _count_setting(financial_settings.get("cap", 0)) > 0:
            if max(0, accepted_count) + payment_holds + new_party_count > _count_setting(financial_settings.get("cap", 0)):
                raise HTTPException(410, detail={"code": "form_full"})
        new_child_statuses = _response_party_statuses(
            form,
            max(0, accepted_count) + payment_holds,
            max(0, waitlisted_count),
            new_party_count,
        )
        now = _utc_now()
        event_snapshot = _form_ticket_event_snapshot(db, form)
        if existing is None:
            status = new_child_statuses.pop(0)
            existing = FormResponseRecord(
                id=str(uuid.uuid4()),
                form_id=form_id,
                draft_id=draft.id,
                form_version=form.version,
                status=status,
                answers=normalized,
                companions=[],
                form_snapshot=response_snapshot(form, event=event_snapshot, status=status, payment=payment_summary),
            )
            db.add(existing)
            db.flush()
        else:
            existing.answers = normalized
            existing.companions = []
            existing.form_snapshot = response_snapshot(
                form,
                event=event_snapshot,
                status=existing.status,
                payment=payment_summary,
                ticket_type=_form_response_ticket_type(existing),
                assign_ticket_type=False,
            )
            existing.updated_at = now

        for previous_child in previous_children:
            child_draft = db.get(FormResponseDraftRecord, previous_child.draft_id)
            if child_draft is not None:
                db.delete(child_draft)
            else:
                db.delete(previous_child)
        if previous_children:
            db.flush()
        added_by_name = _form_ticket_name(existing)
        for companion_index, (guest, status) in enumerate(
            zip(normalized_companions, new_child_statuses)
        ):
            child_draft = FormResponseDraftRecord(
                id=str(uuid.uuid4()),
                form_id=form_id,
                form_version=form.version,
                token_hash=token_digest(new_token()),
                answers=guest["answers"],
                companions=[],
                has_unsaved_changes=False,
                expires_at=now + timedelta(seconds=cfg.response_draft_ttl_seconds),
            )
            child_response = FormResponseRecord(
                id=str(uuid.uuid4()),
                form_id=form_id,
                draft_id=child_draft.id,
                form_version=form.version,
                status=status,
                answers=guest["answers"],
                companions=[],
                registrant_name=guest["name"],
                registrant_mobile=guest["mobile"],
                added_by_response_id=existing.id,
                companion_index=companion_index,
                added_by_name=added_by_name,
                form_snapshot=response_snapshot(form, event=event_snapshot, status=status, payment=payment_summary),
            )
            db.add(child_draft)
            db.add(child_response)
        if payment_summary is not None:
            if existing_payment is None:
                existing_payment = FormPaymentRecord(
                    id=str(uuid.uuid4()),
                    form_id=form_id,
                    draft_id=draft.id,
                    response_id=existing.id,
                    form_version=form.version,
                    method="card_transfer",
                    status="awaiting_receipt",
                    amount=payment_summary["amount"],
                    currency=payment_summary["currency"],
                    party_count=payment_summary["party_count"],
                    selection=payment_summary,
                    idempotency_key="form-card:" + existing.id,
                )
                db.add(existing_payment)
            else:
                existing_payment.amount = payment_summary["amount"]
                existing_payment.currency = payment_summary["currency"]
                existing_payment.party_count = payment_summary["party_count"]
                existing_payment.selection = payment_summary
                existing_payment.status = "awaiting_receipt"
                existing_payment.updated_at = now
        purchase_view: dict[str, Any] | None = None
        if purchase_recording is not None and draft.account_id:
            if existing_payment is None:
                # Free product sold through a form: the accepted response is the purchase.
                _finalize_purchase(
                    db, form=form, response=existing, payment=None, account_id=draft.account_id, now=now,
                    actor=("account", draft.account_id), reason="purchase_form_free:" + existing.id,
                )
            else:
                _upsert_purchase_ledger(
                    db, recording=purchase_recording, account_id=draft.account_id, response=existing,
                    payment=existing_payment, now=now,
                )
        draft.answers = {}
        draft.companions = []
        draft.has_unsaved_changes = False
        draft.updated_at = now
        draft.expires_at = now + timedelta(seconds=cfg.response_draft_ttl_seconds)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "response_conflict") from None
        if purchase_recording is not None:
            purchase_view = _purchase_state_view(db, form, draft.account_id, now)
        return {
            "accepted": True,
            "status": existing.status,
            "purpose": form.purpose,
            "purchase": purchase_view,
            "tracking_code": _form_tracking_code(existing),
            "ticket_type": _form_response_ticket_type(existing),
            "receipt_uploaded": (
                existing.receipt_review_task_id is not None or existing.receipt_upload is not None
            ),
            "payment_status": existing_payment.status if existing_payment is not None else None,
            "payment_id": existing_payment.id if existing_payment is not None else None,
            "saved_at": now.isoformat(),
            "form_version": existing.form_version,
            "registrants_count": 1 + len(normalized_companions),
            "message": (
                "اطلاعاتت ثبت شد؛ فعلاً توی فهرست انتظاری."
                if existing.status == "waitlisted"
                else "اطلاعاتت ثبت شد."
            ),
        }

    @app.post("/api/public/forms/{form_id}/receipt")
    async def upload_public_form_receipt(
        form_id: str,
        request: Request,
        http_response: Response,
        db: Session = Depends(get_db),
    ):
        _same_origin(request)
        cfg: Settings = request.app.state.settings
        http_response.headers["Cache-Control"] = "no-store"
        enforce_public_write_limit(
            request, db, form_id, cfg, cfg.response_draft_write_limit_per_minute
        )
        draft = public_draft_for_cookie(request, db, form_id)
        if draft is None:
            raise HTTPException(401, "response_draft_required")
        record = db.scalar(
            select(FormResponseRecord)
            .where(FormResponseRecord.draft_id == draft.id, FormResponseRecord.form_id == form_id)
            .options(selectinload(FormResponseRecord.receipt_upload))
            .with_for_update()
        )
        if record is None:
            raise HTTPException(409, detail={"code": "ticket_response_not_submitted"})
        is_purchase = _snapshot_purpose(record) == "recording_access"
        if is_purchase:
            if record.status != "accepted":
                raise HTTPException(409, detail={"code": "ticket_not_accepted"})
            if draft.account_id is None or account_identity_from_request(request, db) is None:
                raise HTTPException(401, detail={"code": "account_required", "purpose": "recording_access"})
        else:
            _ensure_form_ticket(record)
        snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
        if snapshot.get("receipt_review_required") is not True:
            raise HTTPException(422, "public_form_receipt_not_required")
        if record.receipt_review_task_id is not None:
            raise HTTPException(409, "public_form_receipt_already_submitted")

        encoded_note = request.headers.get("x-receipt-note", "")
        if len(encoded_note) > 4500 or not re.fullmatch(r"(?:[A-Za-z0-9_.!~*'()-]|%[0-9A-Fa-f]{2})*", encoded_note):
            raise HTTPException(422, "invalid_receipt_note")
        try:
            receipt_note = unquote(encoded_note, errors="strict").replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError:
            raise HTTPException(422, "invalid_receipt_note") from None
        receipt_note = "".join(
            char for char in receipt_note if char in "\n\t" or ord(char) >= 32 and ord(char) != 127
        ).strip()
        if len(receipt_note) > 500:
            raise HTTPException(422, "invalid_receipt_note")

        declared_length = request.headers.get("content-length", "")
        if declared_length:
            try:
                if int(declared_length) > 8 * 1024 * 1024:
                    raise HTTPException(413, "private_file_too_large")
            except ValueError:
                raise HTTPException(400, "invalid_content_length") from None
        content_buffer = bytearray()
        async for chunk in request.stream():
            content_buffer.extend(chunk)
            if len(content_buffer) > 8 * 1024 * 1024:
                raise HTTPException(413, "private_file_too_large")
        blob = bytes(content_buffer)
        content_type = _private_file_type(blob)
        if not content_type:
            raise HTTPException(415, "unsupported_private_file_type")
        declared_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if declared_type not in ("", "application/octet-stream", content_type):
            raise HTTPException(415, "private_file_type_mismatch")
        supplied_name = request.headers.get("x-file-name", "receipt")
        safe_name = "".join(
            char for char in supplied_name.replace("\\", "/").split("/")[-1]
            if char.isprintable() and char not in "\\\"'<>"
        )[:120] or "receipt"
        content_hash = hashlib.sha256(blob).hexdigest()
        upload = record.receipt_upload
        created = upload is None
        if (
            upload is not None
            and upload.content_hash == content_hash
            and upload.content_type == content_type
        ):
            payment_record = db.scalar(
                select(FormPaymentRecord).where(FormPaymentRecord.response_id == record.id)
            )
            changed = False
            if upload.note != receipt_note:
                upload.note = receipt_note
                changed = True
            if payment_record is not None and payment_record.status == "awaiting_receipt":
                payment_record.status = "receipt_submitted"
                payment_record.updated_at = _utc_now()
                changed = True
            if changed:
                db.commit()
            return {"uploaded": True, "created": False}
        if upload is None:
            upload = FormReceiptUploadRecord(
                id=str(uuid.uuid4()),
                response_id=record.id,
                file_name=safe_name,
                content_type=content_type,
                content_size=len(blob),
                content_hash=content_hash,
                content=blob,
                note=receipt_note,
            )
            db.add(upload)
            record.receipt_upload = upload
        else:
            upload.file_name = safe_name
            upload.content_type = content_type
            upload.content_size = len(blob)
            upload.content_hash = content_hash
            upload.content = blob
            upload.note = receipt_note
            upload.created_at = _utc_now()
        payment_record = db.scalar(
            select(FormPaymentRecord)
            .where(FormPaymentRecord.response_id == record.id)
            .with_for_update()
        )
        if payment_record is not None and payment_record.status == "awaiting_receipt":
            payment_record.status = "receipt_submitted"
            payment_record.updated_at = _utc_now()
        task_id: str | None = None
        if is_purchase and draft.account_id:
            # Purchases are reviewed in the shared inbox right away (no Bale ticket claim step).
            db.flush()
            account = db.get(AccountRecord, draft.account_id)
            if account is None:
                raise HTTPException(409, detail={"code": "account_required"})
            bale_ids = verified_bale_ids_for_account(db, account.id)
            task = _create_public_form_receipt_task(
                db, record, bale_ids[0] if bale_ids else "", account=account, purchase=True,
            )
            task_id = task.id if task is not None else None
            form_record = db.get(FormRecord, record.form_id)
            recording = _purchase_recording_for_form(db, form_record) if form_record is not None else None
            if recording is not None and payment_record is not None:
                order = _upsert_purchase_ledger(
                    db, recording=recording, account_id=account.id, response=record, payment=payment_record,
                    now=_utc_now(),
                )
                order.receipt_submitted_at = _utc_now()
                order.receipt_file_name = safe_name
                order.receipt_content_type = content_type
                order.receipt_size = len(blob)
                order.receipt_hash = content_hash
                order.receipt_note = receipt_note[:300]
                # Purchase recorded (not paid, not access): one honest row per ledger order.
                product_title = recording.title or _recording_event_title(db, recording.event_id) or "محتوای ضبط‌شده"
                notifications_mod.queue(
                    db, account_id=account.id, kind=notifications_mod.KIND_PURCHASE_RECORDED,
                    title="خرید شما ثبت شد و در انتظار بررسی است",
                    body=(f"سفارش شما برای «{product_title}» به مبلغ {order.amount:,} {order.currency} ثبت و رسید دریافت شد.\n"
                          "پرداخت هنوز تأیید نشده؛ پس از بررسی رسید، نتیجه و فعال‌شدن دسترسی جداگانه اطلاع داده می‌شود."),
                    key=notifications_mod.dedupe_key("recording_order", order.id, "receipt_submitted"),
                    bale_ids=bale_ids, link=notifications_mod.event_link(recording.event_id, anchor="recording"),
                )
        db.commit()
        if is_purchase:
            return {"uploaded": True, "created": created, "review_task_id": task_id}
        return {"uploaded": True, "created": created}

    @app.get("/api/public/forms/{form_id}/ticket-image")
    def get_public_form_ticket_image(
        form_id: str,
        request: Request,
        download: bool = Query(default=False),
        db: Session = Depends(get_db),
    ):
        """Return this accepted response's actual ticket image to its form session only."""
        cfg: Settings = request.app.state.settings
        # Keep image rendering in its own bucket so image views cannot consume draft-write quota.
        enforce_public_write_limit(
            request, db, form_id + "\0ticket-image", cfg, cfg.response_draft_write_limit_per_minute
        )
        draft = public_draft_for_cookie(request, db, form_id)
        if draft is None:
            raise HTTPException(401, "response_draft_required")
        record = draft.response
        if record is None:
            raise HTTPException(409, detail={"code": "ticket_response_not_submitted"})
        if not _response_payment_approved(db, record):
            raise HTTPException(409, detail={"code": "ticket_payment_not_confirmed"})
        serial = _ensure_form_ticket(record)
        snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
        if (
            snapshot.get("receipt_review_required") is True
            and record.receipt_upload is None
            and record.receipt_review_task_id is None
        ):
            raise HTTPException(409, detail={"code": "ticket_receipt_required"})
        db.commit()

        ticket = _form_ticket_payload(record)
        bot_username = str(cfg.bale_bot_username or "").strip().lstrip("@")
        qr_data = (
            f"https://ble.ir/{bot_username}?start=ftv_{record.id}"
            if re.fullmatch(r"[A-Za-z0-9_]{3,64}", bot_username)
            else record.id
        )
        image_data = {
            "event_title": ticket["event_title"],
            "name": ticket["participant_name"],
            "serial": serial,
            "qr_data": qr_data,
            "event_date": ticket["event_date"],
            "event_time": ticket["event_time"],
            # نام سازمان از همین سرویس وب می‌آید تا رندر بلیت مجبور نشود
            # تنظیمات/پایگاه ربات بله را از داخل فرایند وب بخواند.
            "organization": ORGANIZATION_NAME,
        }
        ticket_type = ticket.get("ticket_type")
        if isinstance(ticket_type, dict) and isinstance(ticket_type.get("name"), str):
            image_data["ticket_type_name"] = ticket_type["name"]
        try:
            content = _render_public_form_ticket_image(image_data)
        except Exception:
            logging.getLogger(__name__).exception("Unable to render a public form ticket image")
            raise HTTPException(503, detail={"code": "ticket_image_unavailable"}) from None
        disposition = "attachment" if download else "inline"
        return Response(
            content=content,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": f'{disposition}; filename="nora-ticket.jpg"',
                "X-Content-Type-Options": "nosniff",
                "Vary": "Cookie",
            },
        )

    @app.post("/api/public/forms/{form_id}/ticket-link")
    def create_public_form_ticket_link(
        form_id: str,
        request: Request,
        http_response: Response,
        db: Session = Depends(get_db),
    ):
        _same_origin(request)
        cfg: Settings = request.app.state.settings
        http_response.headers["Cache-Control"] = "no-store"
        if not cfg.bale_bot_username or not cfg.bot_service_token:
            raise HTTPException(503, detail={"code": "ticket_delivery_not_configured"})
        enforce_public_write_limit(
            request, db, form_id, cfg, cfg.response_draft_write_limit_per_minute
        )
        draft = public_draft_for_cookie(request, db, form_id)
        if draft is None:
            raise HTTPException(401, "response_draft_required")
        record = draft.response
        if record is None:
            raise HTTPException(409, detail={"code": "ticket_response_not_submitted"})
        snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
        if (
            snapshot.get("receipt_review_required") is True
            and record.receipt_upload is None
            and record.receipt_review_task_id is None
        ):
            raise HTTPException(409, detail={"code": "ticket_receipt_required"})
        payment_record = _form_payment_for_response(db, record.id)
        receipt_review_is_ready = bool(
            snapshot.get("receipt_review_required") is True
            and (record.receipt_upload is not None or record.receipt_review_task_id is not None)
        )
        receipt_is_ready_for_review = receipt_review_is_ready and (
            payment_record is None
            or payment_record.method == "card_transfer"
            and payment_record.status in {"receipt_submitted", "paid_manual"}
        )
        if not _response_payment_approved(db, record) and not receipt_is_ready_for_review:
            raise HTTPException(409, detail={"code": "ticket_payment_not_confirmed"})
        if record.ticket_claimed_by_bale_user_id is not None and not receipt_is_ready_for_review:
            raise HTTPException(409, detail={"code": "ticket_already_claimed"})
        _ensure_form_ticket(record)

        now = _utc_now().replace(microsecond=0)
        expires_at = record.ticket_claim_expires_at
        if expires_at is None or _as_utc(expires_at) <= now:
            expires_at = (
                now + timedelta(seconds=cfg.response_draft_ttl_seconds)
            ).replace(microsecond=0)
        token, nonce_hash = _ticket_claim_token(record.id, expires_at, cfg.bot_service_token)
        if record.ticket_claim_nonce_hash != nonce_hash:
            record.ticket_claim_nonce_hash = nonce_hash
            record.ticket_claim_expires_at = expires_at
        db.commit()
        return {
            "delivery_url": f"https://ble.ir/{cfg.bale_bot_username}?start=ft_{token}",
            "tracking_code": _form_tracking_code(record),
            "expires_at": _as_utc(expires_at).isoformat(),
        }

    @app.delete("/api/public/forms/{form_id}/draft")
    async def clear_public_draft(
        form_id: str,
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ):
        _same_origin(request)
        cfg: Settings = request.app.state.settings
        draft = public_draft_for_cookie(request, db, form_id)
        if draft is not None:
            enforce_public_write_limit(request, db, form_id, cfg, cfg.response_draft_write_limit_per_minute)
        response_deleted = bool(draft and draft.response is not None)
        if draft is not None:
            db.delete(draft)
            db.commit()
        clear_public_draft_cookie(response, form_id, cfg)
        return {"deleted": draft is not None, "responseDeleted": response_deleted}

    @app.get("/api/forms/{form_id}/responses")
    def list_responses(
        form_id: str,
        request: Request,
        limit: int = 50,
        offset: int = 0,
        format: str = Query(default="", pattern=r"^(|csv)$"),
        identity: OwnerIdentity | AccountIdentity = Depends(require_permission("fm_responses")),
        db: Session = Depends(get_db),
    ):
        form = get_owned_form(db, identity.owner_id, form_id)
        if format == "csv":
            # Real export (panel restore, stage B): same rows as the list, flattened by the form's
            # current field keys. ``fm_export`` is required on top of ``fm_responses``; payment
            # columns are finance-only because they carry amounts and transaction ids.
            require_permission("fm_export")(request, db)
            role = ROLE_OWNER if isinstance(identity, OwnerIdentity) else identity.role
            with_finance = has_permission(role, "finance")
            fields = [
                field for field in sorted(form.fields, key=lambda item: (item.position, item.row_id))
                if (field.config or {}).get("col") is not False
            ]
            rows = db.execute(
                select(FormResponseRecord, FormPaymentRecord)
                .outerjoin(FormPaymentRecord, FormPaymentRecord.response_id == FormResponseRecord.id)
                .where(FormResponseRecord.form_id == form_id)
                .order_by(FormResponseRecord.created_at.desc(), FormResponseRecord.id.desc())
                .limit(5000)
            ).all()
            header = ["response_id", "status", "created_at", "registrant_name", "companion_index", "added_by_name"]
            header += [str(field.label or field.field_key) for field in fields]
            header += ["checked_in_at", "receipt_uploaded"]
            if with_finance:
                header += ["payment_status", "payment_method", "amount", "currency", "transaction_id"]

            def _cell(value: Any) -> str:
                if value is None:
                    return ""
                if isinstance(value, (list, tuple)):
                    return "، ".join(_cell(item) for item in value)
                if isinstance(value, dict):
                    return json.dumps(value, ensure_ascii=False, sort_keys=True)
                text = str(value)
                # Neutralise spreadsheet formula injection on user-supplied answers.
                return "'" + text if text[:1] in ("=", "+", "-", "@") else text

            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(header)
            for record, payment in rows:
                answers = record.answers if isinstance(record.answers, dict) else {}
                line = [record.id, record.status, _as_utc(record.created_at).isoformat(), _cell(record.registrant_name),
                        "" if record.companion_index is None else str(record.companion_index), _cell(record.added_by_name)]
                line += [_cell(answers.get(field.field_key)) for field in fields]
                line += [_as_utc(record.ticket_checked_in_at).isoformat() if record.ticket_checked_in_at is not None else "",
                         "yes" if (record.receipt_review_task_id is not None or record.receipt_upload is not None) else "no"]
                if with_finance:
                    line += [payment.status if payment is not None else "", payment.method if payment is not None else "",
                             str(payment.amount) if payment is not None else "", payment.currency if payment is not None else "",
                             _cell(payment.transaction_id) if payment is not None else ""]
                writer.writerow(line)
            record_audit(
                db, identity, "form.responses.export", target_type="form", target_id=form_id,
                details={"rows": len(rows), "fields": len(fields), "finance_columns": with_finance},
            )
            db.commit()
            safe_name = re.sub(r"[^A-Za-z0-9_-]+", "-", form_id)[:40] or "form"
            return Response(
                content="\ufeff" + buffer.getvalue(), media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="form-{safe_name}-responses.csv"',
                         "Cache-Control": "private, no-store"},
            )
        page_size = max(1, min(100, limit))
        start = max(0, min(1_000_000, offset))
        records = db.scalars(
            select(FormResponseRecord)
            .where(FormResponseRecord.form_id == form_id)
            .order_by(FormResponseRecord.created_at.desc(), FormResponseRecord.id.desc())
            .limit(page_size)
            .offset(start)
        ).all()
        total = db.scalar(
            select(func.count(FormResponseRecord.id)).where(FormResponseRecord.form_id == form_id)
        ) or 0
        return {
            "items": [
                {
                    "id": item.id,
                    "status": item.status,
                    "form_version": item.form_version,
                    "answers": item.answers,
                    "companions": item.companions or [],
                    "registrant_name": item.registrant_name,
                    "registrant_mobile": item.registrant_mobile,
                    "companion_index": item.companion_index,
                    "added_by_response_id": item.added_by_response_id,
                    "added_by_name": item.added_by_name,
                    "form_snapshot": item.form_snapshot,
                    "created_at": _as_utc(item.created_at).isoformat(),
                    "updated_at": _as_utc(item.updated_at).isoformat(),
                }
                for item in records
            ],
            "total": int(total),
            "limit": page_size,
            "offset": start,
        }

    @app.delete("/api/forms/{form_id}/responses/{response_id}")
    def delete_response(
        form_id: str,
        response_id: str,
        identity: OwnerIdentity = Depends(require_owner_write),
        db: Session = Depends(get_db),
    ):
        get_owned_form(db, identity.owner_id, form_id)
        record = db.scalar(
            select(FormResponseRecord).where(
                FormResponseRecord.id == response_id,
                FormResponseRecord.form_id == form_id,
            )
        )
        if record is None:
            raise HTTPException(404, "response_not_found")
        draft = db.get(FormResponseDraftRecord, record.draft_id)
        if draft is not None:
            db.delete(draft)
        else:
            db.delete(record)
        record_audit(
            db, identity, "form.response.delete", target_type="form_response", target_id=response_id,
            details={"form_id": form_id},
        )
        db.commit()
        return {"deleted": True}

    @app.get("/form.html", include_in_schema=False)
    def public_form_page(request: Request):
        query = request.query_params
        form_id = (query.get("fid") or "").strip()
        if query.get("preview") == "1" or not form_id:
            return _seo_html_response("form", request)

        factory = request.app.state.session_factory
        cfg: Settings = request.app.state.settings
        form_data: dict[str, Any] | None = None
        route_error: str | None = None
        if factory is None:
            route_error = "unavailable"
        else:
            try:
                with factory() as db:
                    cfg = _runtime_settings(db, cfg)
                    form = db.scalar(
                        select(FormRecord)
                        .options(selectinload(FormRecord.fields))
                        .where(FormRecord.id == form_id)
                    )
                    if form is None:
                        route_error = "not-found"
                    elif form.status != "published":
                        route_error = "closed" if form.status in {"paused", "archived"} else "draft"
                    elif publication_issues(form, bale_ready=cfg.form_bale_payments_ready):
                        route_error = "invalid-form"
                    elif (purchase_block := _purchase_form_block(db, form)) is not None:
                        # Purchase form of a product that is not on sale right now (draft/paused/archived).
                        route_error = "recording-not-on-sale:" + str(purchase_block.get("recording_id") or "")
                    elif (block := _event_registration_block(db, form)) is not None:
                        # The form itself is published; only the event's registration window/status blocks it.
                        route_error = "registration-closed:" + str(block.get("event_id") or "")
                    else:
                        accepted, waitlisted = _response_counts(db, form_id)
                        if _capacity_is_full(
                            form, accepted + _active_bale_payment_holds(db, form_id), waitlisted
                        ):
                            route_error = "closed"
                        else:
                            form_data = public_form_data(
                                form,
                                accepted_count=accepted,
                                waitlisted_count=waitlisted,
                                bale_ready=cfg.form_bale_payments_ready,
                            )
                            if _form_is_purchase(form):
                                form_data["purchase"] = _public_purchase_header(db, request, form)
            except SQLAlchemyError:
                route_error = "unavailable"

        html = (UI_ROOT / "form.html").read_text(encoding="utf-8")
        html = html.replace("<!--nora-public-form-->", _json_for_html(form_data) if form_data is not None else "null")
        html = html.replace("<!--nora-public-draft-->", "null")
        html = html.replace("<!--nora-public-error-->", _json_for_html(route_error))
        form_title = str(form_data.get("name") or "فرم عمومی") if form_data else "فرم عمومی"
        form_settings = _json_dict_member(form_data, "settings") if form_data else {}
        form_description = str(form_settings.get("intro") or "فرم عمومی نورا؛ هر پاسخ از سرور بررسی می‌شود.")
        html = apply_page_metadata(
            html,
            title=f"{form_title} | نورا",
            description=form_description,
            robots="noindex,nofollow,noarchive",
            canonical="",
        )
        status = 503 if route_error == "unavailable" else 404 if route_error in {"not-found", "draft"} else 200
        return HTMLResponse(html, status_code=status)

    @app.get("/api/integrations/status")
    def integration_status():
        return {
            "mode": "server-scaffold",
            "deliveryEnabled": False,
            "queueEnabled": False,
            "sendAttempted": False,
            "serverScope": "same-application",
            "secretHandling": "same-application-server-only; values and presence are not exposed",
            "providers": [
                {
                    "id": "bale",
                    "name": "بله",
                    "connectionModel": "bot-token-plus-mini-app",
                    "credentialScope": "same-application-server",
                    "connected": False,
                    "state": "not_connected",
                },
                {
                    "id": "eitaa",
                    "name": "ایتا",
                    "connectionModel": "mini-app-only",
                    "credentialScope": "none-in-this-scaffold",
                    "connected": False,
                    "state": "mini_app_not_connected",
                },
            ],
            "policy": {
                "certificate": ["bale"],
                "ticket": ["bale"],
                "notification": ["bale", "eitaa"],
            },
            "ownerApproval": "requires_server_verified_approval",
        }

    @app.post("/api/outbox")
    async def outbox(request: Request):
        payload = await _read_json_object(request, request.app.state.settings.max_request_bytes)
        if _contains_secret_key(payload):
            raise HTTPException(400, "credentials_not_accepted")
        kind, channel = str(payload.get("kind", "")), str(payload.get("channel", ""))
        if kind not in _OUTBOX_KINDS:
            raise HTTPException(400, "unsupported_kind")
        if channel not in _OUTBOX_POLICY[kind]:
            raise HTTPException(400, "channel_not_allowed")
        output_format = str(payload.get("format", "pdf")).lower()
        if kind in {"certificate", "ticket"} and output_format not in {"pdf", "jpg"}:
            raise HTTPException(400, "unsupported_format")
        return JSONResponse(
            {
                "accepted": False,
                "queued": False,
                "dispatched": False,
                "sendAttempted": False,
                "reason": "server_approval_and_provider_adapter_not_configured",
                "channel": channel,
            },
            status_code=409,
        )

    @app.get("/robots.txt", include_in_schema=False)
    def get_robots():
        return Response(robots_txt(settings.public_base_url), media_type="text/plain; charset=utf-8")

    @app.get("/sitemap.xml", include_in_schema=False)
    def get_sitemap():
        if not settings.public_base_url:
            return Response(
                "پیش از انتشار نقشهٔ سایت، دامنهٔ رسمی HTTPS را در NORA_PUBLIC_BASE_URL تنظیم کنید.\n",
                status_code=503,
                media_type="text/plain; charset=utf-8",
                headers={"Retry-After": "3600"},
            )
        try:
            return Response(
                sitemap_xml(settings.public_base_url, _seo_public_snapshot()),
                media_type="application/xml; charset=utf-8",
            )
        except ValueError:
            return Response("تنظیمات نقشهٔ سایت معتبر نیست.\n", status_code=503, media_type="text/plain; charset=utf-8")

    @app.get("/", include_in_schema=False)
    def home(request: Request):
        return _seo_html_response("home", request)

    @app.get("/{page_name}.html", include_in_schema=False)
    def ui_html_page(page_name: str, request: Request):
        return _seo_html_response(page_name, request)

    class SafeStaticFiles(StaticFiles):
        async def get_response(self, path: str, scope):
            normalized = path.replace("\\", "/").lstrip("/")
            parts = normalized.split("/")
            blocked = (
                any(part.startswith(".") for part in parts)
                or any(normalized.startswith(prefix) for prefix in _BLOCKED_PREFIXES)
                or Path(normalized).name.lower() in _BLOCKED_NAMES
                or Path(normalized).suffix.lower() not in _PUBLIC_SUFFIXES
            )
            if blocked:
                return FileResponse(UI_ROOT / "404.html", status_code=404)
            return await super().get_response(normalized, scope)

    app.mount("/", SafeStaticFiles(directory=str(UI_ROOT), html=True), name="ui")

    return app


app = create_app()
