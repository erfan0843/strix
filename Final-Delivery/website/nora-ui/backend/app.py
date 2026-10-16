"""FastAPI host for Nora UI, owner form publishing, and anonymous responses.

This is one application: the same ASGI process serves the UI and its API.
No provider is enabled by default: phone OTP can call Safir only when its
server-side settings are present, and Bale Mini App/payment/bot integrations
are opt-in. General outbound dispatch remains disabled.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import html
import json
import logging
import os
import re
import sys
import tempfile
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace as dataclass_replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator, Literal, Mapping, Sequence, TypedDict, cast
from urllib.parse import quote, unquote, urlsplit

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, delete, func, select, text, update
from sqlalchemy.engine import CursorResult, Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload, sessionmaker
from starlette.middleware.gzip import GZipMiddleware

from .accounts import get_or_create_bale_account, get_or_create_phone_account
from .captcha import CaptchaError, issue_captcha, verify_captcha
from .bale_payments import BalePaymentAPIError, call_bale_payment_api, validated_invoice_url
from .secret_box import SecretBoxError, decrypt_secret, encrypt_secret, encryption_configured, secret_hint
from .config import UI_ROOT, Settings
from .financials import (
    PaymentConfigurationError,
    calculate_payment_amount,
    normalize_payment_methods,
)
from .form_capabilities import public_form_capabilities
from .models import (
    AccountProfileRecord,
    AccountRecord,
    AccountRoleRecord,
    AccountSessionRecord,
    AdminTaskRecord,
    Base,
    CooperationRequestRecord,
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
    PublicWriteThrottleRecord,
    PaymentSecretRecord,
    SiteContentRecord,
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
    constant_time_equal,
    hash_password,
    new_token,
    throttle_digest,
    token_digest,
    verify_bale_mini_app_init_data,
    verify_password,
)
from .seo import (
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
    public_site_content,
    resolve_public_delivery_file,
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


_BALE_WALLET_KEY = re.compile(r"[0-9]{5,20}:[A-Za-z0-9_-]{20,128}\Z")


def _payment_settings_response(db: Session, cfg: Settings | None = None) -> dict[str, Any]:
    record = db.get(PaymentSecretRecord, "bale_wallet")
    env_configured = bool(cfg and cfg.form_payment_bot_token)
    return {
        "bale_wallet": {
            "configured": record is not None or env_configured,
            "hint": record.hint if record is not None else "",
            "encryption_ready": encryption_configured(),
            "source": "database" if record is not None else ("environment" if env_configured else "none"),
        }
    }


def _payment_cfg(db: Session, cfg: Settings) -> Settings:
    """Return settings whose Bale payment token comes from the owner's saved key when present."""
    record = db.get(PaymentSecretRecord, "bale_wallet")
    if record is None:
        return cfg
    try:
        token = decrypt_secret(record.ciphertext)
    except SecretBoxError:
        return cfg
    return dataclass_replace(cfg, form_payment_bot_token=token)


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
    if not origin or not host:
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
        "fields": [_field_dict(field) for field in form.fields],
        "settings": form.settings or {},
        "status": form.status,
        "version": form.version,
        "created_at": _as_utc(form.created_at).isoformat(),
        "updated_at": _as_utc(form.updated_at).isoformat(),
    }


def _form_ticket_eligible(record: FormResponseRecord) -> bool:
    snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
    return (
        record.status == "accepted"
        and snapshot.get("model") == "registration"
        and snapshot.get("need") == "reg"
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
    db: Session, record: FormResponseRecord, bale_user_id: str
) -> AdminTaskRecord | None:
    """Move a browser-uploaded receipt into the shared manager inbox at Bale claim time."""
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

        if page_name in {"event", "post", "person"}:
            item_id = (request.query_params.get("id") or "").strip()
            preview = page_name == "post" and request.query_params.get("d") == "1"
            key = {"event": "events", "post": "articles", "person": "people"}[page_name]
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

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if frame_ancestors:
            # فقط برای پیش‌نمایش توسعه: NORA_FRAME_ANCESTORS تعیین می‌کند چه میزبانی قاب بزند.
            response.headers["Content-Security-Policy"] = f"frame-ancestors {frame_ancestors}"
        else:
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        path = request.url.path.lower()
        if path.startswith("/api/"):
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
        role_record = db.get(AccountRoleRecord, record.account_id)
        role = role_record.role if role_record is not None else None
        return AccountIdentity(
            record.id, record.account_id, record.csrf_hash, role, cfg.owner_id, record.auth_provider
        )

    def require_account(request: Request, db: Session = Depends(get_db)) -> AccountIdentity:
        identity = account_identity_from_request(request, db)
        if identity is None:
            raise HTTPException(401, "authentication_required")
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
        views = []
        for task in tasks:
            view = admin_task_view(task)
            view["files"] = files_by_task.get(task.id, [])
            views.append(view)
        return views

    def user_notification_view(item: UserNotificationRecord) -> dict[str, Any]:
        return {
            "id": item.id,
            "bale_user_id": item.bale_user_id,
            "kind": item.kind,
            "title": item.title,
            "body": item.body,
            "file_refs": item.file_refs,
            "delivery_status": item.delivery_status,
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
        is_public_form_receipt = (
            task.kind == "receipt_review"
            and task_payload.get("registration_source") == "public_form"
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
        if is_public_form_receipt and linked_response is not None:
            payment_record = db.scalar(
                select(FormPaymentRecord)
                .where(FormPaymentRecord.response_id == linked_response.id)
                .with_for_update()
            )
            if payment_record is not None and payment_record.method == "card_transfer":
                payment_record.status = "paid_manual" if decision == "approved" else "rejected"
                payment_record.updated_at = now
        if is_public_form_receipt and decision == "rejected" and linked_response is not None:
            draft = linked_response.draft
            if draft is not None:
                draft.answers = {}
                draft.companions = []
                draft.bot_bale_user_id = None
            db.delete(linked_response)
            db.flush()
        target_kind = task.kind.removesuffix("_review") + ("_approved" if decision == "approved" else "_rejected")
        approved = decision == "approved"
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
        else:
            title = "فیش پرداخت تأیید شد" if approved else "فیش پرداخت تأیید نشد"
            body = "رسید پرداخت شما تأیید شد." if approved else ("رسید پرداخت تأیید نشد." + (" دلیل: " + reason if reason else ""))
        notification = UserNotificationRecord(
            id=str(uuid.uuid4()),
            account_id=task.account_id,
            bale_user_id=task.bale_user_id,
            source_task_id=task.id,
            kind=target_kind,
            title=title,
            body=body,
            file_refs=[] if is_public_form_receipt else list(task_payload.get("file_refs", [])),
            delivery_status="pending",
        )
        db.add(notification)
        db.flush()
        updated_task = db.get(AdminTaskRecord, task.id)
        if updated_task is None:
            raise HTTPException(404, "admin_task_not_found")
        return updated_task

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
            "formBalePaymentsReady": request.app.state.settings.form_bale_payments_ready,
        }

    @app.get("/api/public/forms/capabilities")
    def form_capabilities(request: Request):
        """Read-only, secret-free feature contract for the web form builder."""
        cfg: Settings = request.app.state.settings
        return public_form_capabilities(
            api_configured=request.app.state.session_factory is not None,
            bale_wallet_ready=cfg.form_bale_payments_ready,
        )

    def _site_content_response(
        db: Session, content: dict[str, Any], version: int, updated_at: datetime | None, *, owner_view: bool = False
    ):
        public = public_site_content(content)
        if owner_view:
            try:
                public["banners"] = sanitize_site_content(
                    {"banners": content.get("banners", [])}, partial=True
                ).get("banners", [])
            except SiteContentError:
                public["banners"] = []
        cfg: Settings = app.state.settings
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
                if form.event_id and str(form.event_id) != str(event.get("id")):
                    continue
                if str(form.event_id or "") == str(event.get("id")) or form.id in declared:
                    related.append({"id": form.id, "need": form.need, "n": form.title})
            event["forms"] = related
            event.pop("regForm", None)
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
        }

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
        current.update(incoming)
        if record is None:
            record = SiteContentRecord(id="public", content=current, version=1)
            db.add(record)
        else:
            record.content = current
            record.version = current_version + 1
            record.updated_at = _utc_now()
        db.commit()
        db.refresh(record)
        return _site_content_response(db, record.content or {}, record.version, record.updated_at, owner_view=True)

    @app.get("/api/owner/payment-settings")
    def get_owner_payment_settings(
        request: Request,
        _identity: OwnerIdentity = Depends(require_owner),
        db: Session = Depends(get_db),
    ):
        return _payment_settings_response(db, request.app.state.settings)

    @app.put("/api/owner/payment-settings/bale-wallet")
    async def set_owner_bale_wallet_key(
        request: Request,
        _identity: OwnerIdentity = Depends(require_owner_write),
        db: Session = Depends(get_db),
    ):
        payload = await _read_json_object(request, 4 * 1024)
        if set(payload) != {"api_key"} or not isinstance(payload.get("api_key"), str):
            raise HTTPException(400, "invalid_payment_settings_request")
        value = payload["api_key"].strip()
        if not _BALE_WALLET_KEY.fullmatch(value):
            raise HTTPException(422, "invalid_bale_wallet_key_format")
        if not encryption_configured():
            raise HTTPException(503, "settings_encryption_not_configured")
        try:
            ciphertext = encrypt_secret(value)
        except SecretBoxError as error:
            raise HTTPException(503, error.code) from None
        record = db.get(PaymentSecretRecord, "bale_wallet")
        if record is None:
            db.add(PaymentSecretRecord(id="bale_wallet", ciphertext=ciphertext, hint=secret_hint(value)))
        else:
            record.ciphertext = ciphertext
            record.hint = secret_hint(value)
        db.commit()
        return _payment_settings_response(db, request.app.state.settings)

    @app.delete("/api/owner/payment-settings/bale-wallet")
    def clear_owner_bale_wallet_key(
        request: Request,
        _identity: OwnerIdentity = Depends(require_owner_write),
        db: Session = Depends(get_db),
    ):
        record = db.get(PaymentSecretRecord, "bale_wallet")
        if record is not None:
            db.delete(record)
            db.commit()
        return _payment_settings_response(db, request.app.state.settings)

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
            "samesite": "strict",
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
            "samesite": "strict",
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
            "samesite": "strict",
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
        response.delete_cookie(cfg.cookie_name, path="/", secure=cfg.cookie_secure, httponly=True, samesite="strict")
        response.delete_cookie(cfg.csrf_cookie_name, path="/", secure=cfg.cookie_secure, httponly=False, samesite="strict")
        return {"authenticated": False}

    @app.post("/api/auth/bale-mini-app")
    async def bale_mini_app_login(
        request: Request,
        response: Response,
        db: Session = Depends(get_db),
    ):
        _same_origin(request)
        cfg: Settings = request.app.state.settings
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
            "samesite": "strict",
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
        cfg: Settings = request.app.state.settings
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

        account = get_or_create_phone_account(db, phone, pepper=cfg.otp_pepper)
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
            "samesite": "strict",
            "path": "/",
            "max_age": cfg.session_ttl_seconds,
        }
        response.set_cookie(cfg.account_cookie_name, raw_session, httponly=True, **cookie_options)
        response.set_cookie(cfg.account_csrf_cookie_name, raw_csrf, httponly=False, **cookie_options)
        return {"authenticated": True, "account_id": account.id, "provider": "phone"}

    @app.get("/api/account/me")
    def account_me(identity: AccountIdentity = Depends(require_account)):
        bot_username = app.state.settings.bale_bot_username
        delivery_bot_url = f"https://ble.ir/{bot_username}" if re.fullmatch(r"[A-Za-z0-9_]{3,64}", bot_username) else ""
        return {
            "authenticated": True,
            "account_id": identity.account_id,
            "provider": identity.provider,
            "role": identity.role,
            "permissions": sorted(permissions_for_role(identity.role)),
            "delivery_bot_url": delivery_bot_url,
        }

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
            FormResponseDraftRecord.account_id == identity.account_id,
            FormResponseRecord.added_by_response_id.is_(None),
            FormRecord.model == "registration",
        )
        total = int(db.scalar(
            select(func.count(FormResponseRecord.id))
            .join(FormResponseDraftRecord, FormResponseDraftRecord.id == FormResponseRecord.draft_id)
            .join(FormRecord, FormRecord.id == FormResponseRecord.form_id)
            .where(*filters)
        ) or 0)
        rows = db.execute(
            select(FormResponseRecord, FormPaymentRecord)
            .join(FormResponseDraftRecord, FormResponseDraftRecord.id == FormResponseRecord.draft_id)
            .join(FormRecord, FormRecord.id == FormResponseRecord.form_id)
            .outerjoin(FormPaymentRecord, FormPaymentRecord.response_id == FormResponseRecord.id)
            .where(*filters)
            .order_by(FormResponseRecord.created_at.desc(), FormResponseRecord.id.desc())
            .limit(limit + 1)
            .offset(offset)
        ).all()
        items = []
        for record, payment in rows[:limit]:
            snapshot = record.form_snapshot if isinstance(record.form_snapshot, dict) else {}
            event = _json_dict_member(snapshot, "event")
            form_name = _ticket_text(snapshot.get("name") or "فرم ثبت‌نام", 160) or "فرم ثبت‌نام"
            items.append({
                "id": record.id,
                "form_name": form_name,
                "event_title": _ticket_text(event.get("title") or form_name, 160) or form_name,
                "event_date": _ticket_text(event.get("date") or "", 120),
                "event_time": _ticket_text(event.get("time") or "", 120),
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
            .where(UserNotificationRecord.delivery_status == "pending")
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
        identity: OwnerIdentity | AccountIdentity = Depends(
            require_any_permission("us_approve", "receipt_approve")
        ),
        db: Session = Depends(get_db),
    ):
        role = ROLE_OWNER if isinstance(identity, OwnerIdentity) else identity.role
        kinds = [kind for kind in ("profile_review", "receipt_review") if has_permission(role, workflow_permission(kind))]
        tasks = db.scalars(
            select(AdminTaskRecord)
            .where(AdminTaskRecord.status == "pending", AdminTaskRecord.kind.in_(kinds))
            .order_by(AdminTaskRecord.created_at.asc(), AdminTaskRecord.id)
            .offset(offset)
            .limit(limit + 1)
        ).all()
        return {"items": admin_inbox_task_views(db, tasks[:limit]), "has_more": len(tasks) > limit}

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
        db.commit()
        return {"task": admin_task_view(db.get(AdminTaskRecord, task.id)), "accepted": True}

    @app.get("/api/owner/accounts")
    def list_account_roles(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=1_000_000),
        _identity: OwnerIdentity = Depends(require_owner),
        db: Session = Depends(get_db),
    ):
        records = db.execute(
            select(AccountRecord, PlatformIdentityRecord, AccountRoleRecord, ManagerCredentialRecord)
            .join(PlatformIdentityRecord, PlatformIdentityRecord.account_id == AccountRecord.id)
            .outerjoin(AccountRoleRecord, AccountRoleRecord.account_id == AccountRecord.id)
            .outerjoin(ManagerCredentialRecord, ManagerCredentialRecord.account_id == AccountRecord.id)
            .where(PlatformIdentityRecord.provider.in_(("bale", "phone")))
            .order_by(AccountRecord.created_at.desc(), AccountRecord.id)
            .offset(offset)
            .limit(limit + 1)
        ).all()
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
                "role": role.role if role is not None else None,
                "permissions": sorted(permissions_for_role(role.role if role is not None else None)),
                "manager_username": credential.username_key if credential is not None else None,
                "manager_login_enabled": credential is not None,
                "created_at": _as_utc(account.created_at).isoformat(),
            }
            for account, identity, role, credential in records[:limit]
        ]
        return {"items": items, "limit": limit, "offset": offset, "has_more": has_more}

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
        db.commit()
        return {
            "account_id": account_id,
            "role": role,
            "permissions": sorted(permissions_for_role(role)),
        }

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
            samesite="strict",
        )
        response.delete_cookie(
            cfg.account_csrf_cookie_name,
            path="/",
            secure=cfg.cookie_secure,
            httponly=False,
            samesite="strict",
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
        record.status = payload["status"]
        record.updated_at = _utc_now()
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
        canonical_payload = {
            "name": normalized.title,
            "model": normalized.model,
            "need": normalized.need,
            "slug": normalized.slug,
            "event_id": normalized.event_id,
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
            event_id=normalized.event_id,
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
            record, bale_ready=request.app.state.settings.form_bale_payments_ready
        )
        publishable_status = record.status in {"draft", "paused"}
        return {
            "source": "same_server_database",
            "form_id": record.id,
            "version": record.version,
            "status": record.status,
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
                event_id=normalized.event_id,
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
        if form_has_companions(form) or _form_uses_payment(form):
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
            samesite="strict",
            path=f"/api/public/forms/{form_id}",
            max_age=cfg.response_draft_ttl_seconds,
        )

    def clear_public_draft_cookie(response: Response, form_id: str, cfg: Settings) -> None:
        response.delete_cookie(
            _public_draft_cookie_name(form_id),
            path=f"/api/public/forms/{form_id}",
            secure=cfg.cookie_secure,
            httponly=True,
            samesite="strict",
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
        cfg: Settings = request.app.state.settings
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
        db.commit()
        db.expire_all()
        return _form_dict(get_owned_form(db, identity.owner_id, form_id))

    @app.get("/api/public/forms/{form_id}")
    def get_public_form(
        form_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        cfg: Settings = request.app.state.settings
        form = get_published_form(db, form_id, bale_ready=cfg.form_bale_payments_ready)
        accepted, waitlisted = _response_counts(db, form_id)
        if _capacity_is_full(form, accepted + _active_bale_payment_holds(db, form_id), waitlisted):
            raise HTTPException(410, detail={"code": "form_full"})
        return public_form_data(
            form,
            accepted_count=accepted,
            waitlisted_count=waitlisted,
            bale_ready=cfg.form_bale_payments_ready,
        )

    @app.post("/api/public/forms/{form_id}/payment-intents", status_code=201)
    async def create_public_payment_intent(
        form_id: str,
        request: Request,
        db: Session = Depends(get_db),
    ):
        _same_origin(request)
        cfg: Settings = request.app.state.settings
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
        bind_public_draft_account(draft, account_identity_from_request(request, db), db)
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
            webhook_info = await asyncio.to_thread(call_bale_payment_api, _payment_cfg(db, cfg), "getWebhookInfo", {})
            webhook_result = webhook_info.get("result")
            configured_webhook = (
                webhook_result.get("url", "") if isinstance(webhook_result, dict) else ""
            )
            registered_webhook_url = _form_payment_registered_webhook_url(cfg)
            current_webhook_url = configured_webhook.rstrip("/")
            base_webhook_url = cfg.form_payment_webhook_url.rstrip("/")
            if current_webhook_url != registered_webhook_url:
                if current_webhook_url not in {"", base_webhook_url}:
                    raise HTTPException(503, detail={"code": "bale_payment_webhook_conflict"})
                await asyncio.to_thread(
                    call_bale_payment_api,
                    _payment_cfg(db, cfg),
                    "setWebhook",
                    {"url": registered_webhook_url},
                )
                verified_webhook_info = await asyncio.to_thread(
                    call_bale_payment_api, _payment_cfg(db, cfg), "getWebhookInfo", {}
                )
                verified_result = verified_webhook_info.get("result")
                verified_url = verified_result.get("url", "") if isinstance(verified_result, dict) else ""
                if verified_url.rstrip("/") != registered_webhook_url:
                    raise HTTPException(503, detail={"code": "bale_payment_webhook_registration_failed"})
            payment_id = str(uuid.uuid4())
            invoice_payload = "nora_" + uuid.uuid4().hex
            title = str(form.title or "ثبت‌نام").strip()[:32] or "ثبت‌نام"
            description = f"پرداخت ثبت‌نام: {str(form.title or 'فرم')[:200]}"[:255]
            invoice_response = await asyncio.to_thread(
                call_bale_payment_api,
                _payment_cfg(db, cfg),
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
        cfg: Settings = request.app.state.settings
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
                    call_bale_payment_api, _payment_cfg(db, cfg), "answerPreCheckoutQuery", answer
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
                _payment_cfg(db, cfg),
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
        cfg: Settings = request.app.state.settings
        records = db.scalars(
            select(FormRecord)
            .options(selectinload(FormRecord.fields))
            .where(FormRecord.status == "published")
            .order_by(FormRecord.updated_at.desc(), FormRecord.id)
            .limit(100)
        ).all()
        items = []
        for form in records:
            if publication_issues(form, bale_ready=cfg.form_bale_payments_ready) or form_has_companions(form) or _form_uses_payment(form):
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
            FormResponseDraftRecord.bot_bale_user_id == user_id,
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
                FormResponseDraftRecord.bot_bale_user_id == user_id,
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
        cfg: Settings = request.app.state.settings
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
        cfg: Settings = request.app.state.settings
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
        cfg: Settings = request.app.state.settings
        payload = await _read_json_object(request, cfg.max_request_bytes)
        if set(payload) != {"bale_user_id", "session_key"}:
            raise HTTPException(400, "invalid_bot_form_response_payload")
        bale_user_id, session_key = validate_bot_form_identity(
            payload.get("bale_user_id"), payload.get("session_key")
        )
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
        cfg: Settings = request.app.state.settings
        form = get_published_form(db, form_id, bale_ready=cfg.form_bale_payments_ready)
        enforce_public_write_limit(request, db, form_id, cfg, cfg.response_draft_write_limit_per_minute)
        _cleanup_expired_public_drafts(db)
        draft, raw_token = ensure_public_draft(request, db, form)
        bind_public_draft_account(draft, account_identity_from_request(request, db), db)
        answers, submitted = draft_answers(db, draft)
        companions = draft_companions(db, draft, submitted)
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
        cfg: Settings = request.app.state.settings
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
        bind_public_draft_account(draft, account_identity_from_request(request, db), db)
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
        cfg: Settings = request.app.state.settings
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
        account_linked = bind_public_draft_account(draft, account_identity_from_request(request, db), db)
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
        return {
            "accepted": True,
            "status": existing.status,
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
        db.commit()
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
        limit: int = 50,
        offset: int = 0,
        identity: OwnerIdentity | AccountIdentity = Depends(require_permission("fm_responses")),
        db: Session = Depends(get_db),
    ):
        get_owned_form(db, identity.owner_id, form_id)
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
