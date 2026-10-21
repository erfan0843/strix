"""Shared certificate registry: pure helpers for the bot sync API and the managers' panel.

The Bale bot issues certificates; the server keeps a verified mirror
(:class:`backend.models.CertificateRecord`). Ownership is resolved here, on the
server, from the Bale user id through ``platform_identities`` – never from a
client-supplied account id. Rows whose owner has no server identity are not
stored. There is intentionally no server-side revoke in this phase: the bot
remains the single writer of certificate status.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Mapping
import unicodedata
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .form_quality import gregorian_to_jalali
from .models import (
    AccountProfileRecord,
    AccountRecord,
    CertificateRecord,
    PlatformIdentityRecord,
    PrivateFileRecord,
)

SOURCE = "shared_server_database"
STATUSES = ("issued", "revoked")
SOURCES = ("bot", "bot_legacy")
# ``recording`` (phase 9.2): «پایان محتوای آموزشی ضبط‌شده» issued manually from the
# bot's certificate centre (``certcenter.CERT_KINDS``). It is never an attendance
# certificate and nothing on the server creates it automatically.
KINDS = ("event", "batch", "form", "manual", "center", "recording")
EXTERNAL_KEY_RE = re.compile(r"[A-Za-z0-9:_-]{3,120}")
BALE_USER_ID_RE = re.compile(r"[1-9][0-9]{0,19}")
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}")
_TEXT_FIELDS: dict[str, int] = {
    "serial": 80, "full_code": 120, "doc_no": 80, "person_code": 80, "event_ref": 40,
    "event_title": 200, "title": 200, "holder_name": 160, "issued_on": 32, "expires_on": 32,
    "issued_by_bale_user_id": 40,
}
_ALLOWED_FIELDS = set(_TEXT_FIELDS) | {
    "status", "source", "source_id", "legacy_id", "kind", "issued_at", "revoked_at", "verify_count",
}


class CertificateError(ValueError):
    """Validation failure; ``code`` is the stable API error code."""

    def __init__(self, code: str, status_code: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def today_jalali() -> str:
    """Tehran calendar day as ``YYYY/MM/DD`` (the bot stores expiry dates in this form)."""
    now = datetime.now(timezone(timedelta(hours=3, minutes=30)))
    year, month, day = gregorian_to_jalali(now.year, now.month, now.day)
    return f"{year:04d}/{month:02d}/{day:02d}"


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    utc = _as_utc(value)
    return utc.isoformat() if utc is not None else None


def _parse_datetime(value: Any, field: str) -> datetime | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > 40:
        raise CertificateError(f"invalid_{field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CertificateError(f"invalid_{field}") from None
    return _as_utc(parsed)


def _clean_text(value: Any, field: str, limit: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise CertificateError(f"invalid_{field}")
    text = unicodedata.normalize("NFKC", value).replace("\x00", "").strip()
    if len(text) > limit:
        raise CertificateError(f"invalid_{field}")
    return text


def resolve_owner(db: Session, bale_user_id: str) -> AccountRecord | None:
    """Existing server account for a Bale id; never creates one (no auto-matching)."""
    if not BALE_USER_ID_RE.fullmatch(bale_user_id or ""):
        raise CertificateError("invalid_bale_user_id")
    identity = db.scalar(
        select(PlatformIdentityRecord).where(
            PlatformIdentityRecord.provider == "bale",
            PlatformIdentityRecord.provider_user_id == bale_user_id,
        )
    )
    if identity is None:
        return None
    return db.get(AccountRecord, identity.account_id)


def validate_submission(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize the bot payload; raises :class:`CertificateError` on anything unexpected."""
    if set(payload) - {"bale_user_id", "external_key", "certificate", "file_refs"}:
        raise CertificateError("invalid_certificate_payload", 400)
    if {"bale_user_id", "external_key", "certificate"} - set(payload):
        raise CertificateError("invalid_certificate_payload", 400)
    raw_user_id = payload.get("bale_user_id")
    if isinstance(raw_user_id, bool) or not isinstance(raw_user_id, (str, int)):
        raise CertificateError("invalid_bale_user_id")
    bale_user_id = str(raw_user_id)
    if not BALE_USER_ID_RE.fullmatch(bale_user_id):
        raise CertificateError("invalid_bale_user_id")
    external_key = payload.get("external_key")
    if not isinstance(external_key, str) or not EXTERNAL_KEY_RE.fullmatch(external_key):
        raise CertificateError("invalid_external_key")
    data = payload.get("certificate")
    if not isinstance(data, dict) or set(data) - _ALLOWED_FIELDS:
        raise CertificateError("invalid_certificate_data")
    fields: dict[str, Any] = {}
    status = data.get("status", "issued")
    if status not in STATUSES:
        raise CertificateError("invalid_certificate_status")
    fields["status"] = status
    source = data.get("source", "bot")
    if source not in SOURCES:
        raise CertificateError("invalid_certificate_source")
    fields["source"] = source
    source_id = data.get("source_id", "")
    if source_id not in ("", None) and (not isinstance(source_id, str) or not UUID_RE.fullmatch(source_id)):
        raise CertificateError("invalid_source_id")
    fields["source_id"] = source_id or ""
    legacy_id = data.get("legacy_id")
    if legacy_id is not None and (isinstance(legacy_id, bool) or not isinstance(legacy_id, int) or legacy_id < 1):
        raise CertificateError("invalid_legacy_id")
    fields["legacy_id"] = legacy_id
    kind = data.get("kind", "event")
    if kind not in KINDS:
        raise CertificateError("invalid_certificate_kind")
    fields["kind"] = kind
    verify_count = data.get("verify_count", 0)
    if isinstance(verify_count, bool) or not isinstance(verify_count, int) or verify_count < 0 or verify_count > 1_000_000:
        raise CertificateError("invalid_verify_count")
    fields["verify_count"] = verify_count
    for name, limit in _TEXT_FIELDS.items():
        fields[name] = _clean_text(data.get(name), name, limit)
    if fields["issued_by_bale_user_id"] and not BALE_USER_ID_RE.fullmatch(fields["issued_by_bale_user_id"]):
        raise CertificateError("invalid_issued_by_bale_user_id")
    fields["issued_at"] = _parse_datetime(data.get("issued_at"), "issued_at")
    fields["revoked_at"] = _parse_datetime(data.get("revoked_at"), "revoked_at")
    if status == "revoked" and fields["revoked_at"] is None:
        fields["revoked_at"] = _utc_now()
    if status == "issued":
        fields["revoked_at"] = None
    if not (fields["serial"] or fields["full_code"] or fields["legacy_id"]):
        raise CertificateError("certificate_identity_required")
    file_refs = payload.get("file_refs", {}) or {}
    if not isinstance(file_refs, dict) or set(file_refs) - {"pdf", "png"}:
        raise CertificateError("invalid_file_refs")
    refs: dict[str, str | None] = {}
    for slot in ("pdf", "png"):
        value = file_refs.get(slot)
        if value is None:
            refs[slot] = None
            continue
        if not isinstance(value, str) or not UUID_RE.fullmatch(value):
            raise CertificateError("invalid_file_refs")
        refs[slot] = value
    return {"bale_user_id": bale_user_id, "external_key": external_key, "fields": fields, "file_refs": refs}


def _owned_file(db: Session, account_id: str, file_id: str | None, content_types: tuple[str, ...]) -> str | None:
    if file_id is None:
        return None
    item = db.get(PrivateFileRecord, file_id)
    if item is None or item.account_id != account_id or item.content_type not in content_types:
        raise CertificateError("file_not_owned_by_certificate_owner")
    return item.id


def upsert(db: Session, submission: Mapping[str, Any]) -> tuple[CertificateRecord, bool]:
    """Create or refresh the mirror row. Owner must already exist; files must belong to the owner."""
    account = resolve_owner(db, submission["bale_user_id"])
    if account is None:
        raise CertificateError("owner_identity_not_found", 404)
    fields = dict(submission["fields"])
    refs = submission["file_refs"]
    file_id = _owned_file(db, account.id, refs.get("pdf"), ("application/pdf",))
    preview_id = _owned_file(db, account.id, refs.get("png"), ("image/png", "image/jpeg", "image/webp"))
    record = db.scalar(select(CertificateRecord).where(CertificateRecord.external_key == submission["external_key"]))
    created = record is None
    if record is None:
        record = CertificateRecord(
            id=str(uuid.uuid4()), account_id=account.id, bale_user_id=submission["bale_user_id"],
            external_key=submission["external_key"],
        )
        db.add(record)
    elif record.account_id != account.id or record.bale_user_id != submission["bale_user_id"]:
        # A key that already belongs to someone else is never silently re-owned.
        raise CertificateError("certificate_owner_mismatch", 409)
    for name, value in fields.items():
        setattr(record, name, value)
    if file_id is not None or created:
        record.file_id = file_id
    if preview_id is not None or created:
        record.preview_file_id = preview_id
    record.synced_at = _utc_now()
    db.flush()
    return record, created


def effective_status(record: CertificateRecord, today_jalali: str | None = None) -> str:
    """``revoked`` beats everything; ``expired`` only when a comparable Jalali date is stored."""
    if record.status == "revoked":
        return "revoked"
    if record.expires_on and today_jalali and _jalali_key(record.expires_on) and _jalali_key(record.expires_on) < _jalali_key(today_jalali):
        return "expired"
    return "issued"


def _jalali_key(value: str) -> str:
    digits = re.sub(r"[^0-9]", "", unicodedata.normalize("NFKC", value or "").translate(_DIGIT_MAP))
    return digits if len(digits) == 8 else ""


_DIGIT_MAP = {ord(c): str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")} | {ord(c): str(i) for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")}


def _holder(db: Session, record: CertificateRecord) -> dict[str, Any]:
    profile = db.get(AccountProfileRecord, record.account_id)
    profile_name = str(((profile.fields if profile is not None else {}) or {}).get("fullName") or "")[:120]
    return {
        "account_id": record.account_id,
        "bale_user_id": record.bale_user_id,
        "display_name": profile_name or record.holder_name,
        "name_source": "profile" if profile_name else ("certificate" if record.holder_name else "none"),
    }


def row(db: Session, record: CertificateRecord, *, today_jalali: str | None = None) -> dict[str, Any]:
    return {
        "id": record.id,
        "external_key": record.external_key,
        "source": record.source,
        "legacy_id": record.legacy_id,
        "kind": record.kind,
        "status": record.status,
        "effective_status": effective_status(record, today_jalali),
        "serial": record.serial,
        "full_code": record.full_code,
        "doc_no": record.doc_no,
        "person_code": record.person_code,
        "event_ref": record.event_ref,
        "event_title": record.event_title,
        "title": record.title,
        "issued_on": record.issued_on,
        "expires_on": record.expires_on,
        "issued_at": _iso(record.issued_at),
        "revoked_at": _iso(record.revoked_at),
        "verify_count": record.verify_count,
        "has_file": record.file_id is not None,
        "has_preview": record.preview_file_id is not None,
        "synced_at": _iso(record.synced_at),
        "created_at": _iso(record.created_at),
        "holder": _holder(db, record),
    }


def detail(db: Session, record: CertificateRecord, *, today_jalali: str | None = None) -> dict[str, Any]:
    data = row(db, record, today_jalali=today_jalali)
    data["issued_by_bale_user_id"] = record.issued_by_bale_user_id or None
    data["source_id"] = record.source_id or None
    data["files"] = [
        {"slot": slot, "file_id": file_id}
        for slot, file_id in (("pdf", record.file_id), ("png", record.preview_file_id))
        if file_id is not None
    ]
    return data


def account_row(record: CertificateRecord, *, today_jalali: str | None = None) -> dict[str, Any]:
    """What the holder sees in «حساب من»: own record only, no issuer/account identifiers."""
    return {
        "id": record.id,
        "kind": record.kind,
        "status": record.status,
        "effective_status": effective_status(record, today_jalali),
        "serial": record.serial,
        "full_code": record.full_code,
        "doc_no": record.doc_no,
        "person_code": record.person_code,
        "event_ref": record.event_ref,
        "event_title": record.event_title,
        "title": record.title,
        "issued_on": record.issued_on,
        "expires_on": record.expires_on,
        "issued_at": _iso(record.issued_at),
        "revoked_at": _iso(record.revoked_at),
        "has_file": record.file_id is not None,
        "has_preview": record.preview_file_id is not None,
    }


def account_records(db: Session, account_id: str, *, today_jalali: str | None = None) -> dict[str, Any]:
    """Certificates mirrored for one account – ownership is the server-side ``account_id`` only.

    Revoked rows stay visible with their real status; nothing is hidden or
    synthesised. Files are delivered by the Bale bot (same policy as private files).
    """
    rows = list(db.scalars(
        select(CertificateRecord)
        .where(CertificateRecord.account_id == account_id)
        .order_by(CertificateRecord.created_at.desc(), CertificateRecord.id)
        .limit(500)
    ).all())
    items = [account_row(record, today_jalali=today_jalali) for record in rows]
    counts = {"issued": 0, "revoked": 0, "expired": 0}
    for item in items:
        counts[item["effective_status"]] = counts.get(item["effective_status"], 0) + 1
    return {"items": items, "total": len(items), "counts": counts, "delivery": "bale_bot"}


def list_records(
    db: Session, *, q: str = "", status: str = "", kind: str = "", event_ref: str = "",
    limit: int = 20, offset: int = 0, today_jalali: str | None = None,
) -> dict[str, Any]:
    query = select(CertificateRecord)
    if status in STATUSES:
        query = query.where(CertificateRecord.status == status)
    if kind in KINDS:
        query = query.where(CertificateRecord.kind == kind)
    if event_ref:
        query = query.where(CertificateRecord.event_ref == event_ref)
    needle = unicodedata.normalize("NFKC", q or "").strip().lower()
    candidates = list(db.scalars(
        query.order_by(CertificateRecord.created_at.desc(), CertificateRecord.id).limit(5000)
    ).all())
    selected: list[CertificateRecord] = []
    names: dict[str, str] = {}
    if needle and candidates:
        for account_id, fields in db.execute(
            select(AccountProfileRecord.account_id, AccountProfileRecord.fields).where(
                AccountProfileRecord.account_id.in_({item.account_id for item in candidates})
            )
        ).all():
            names[account_id] = unicodedata.normalize("NFKC", str((fields or {}).get("fullName") or "")).lower()
    for item in candidates:
        if needle:
            haystack = " ".join(part for part in (
                item.serial.lower(), item.full_code.lower(), item.doc_no.lower(), item.person_code.lower(),
                unicodedata.normalize("NFKC", item.holder_name).lower(),
                unicodedata.normalize("NFKC", item.event_title).lower(),
                unicodedata.normalize("NFKC", item.title).lower(),
                names.get(item.account_id, ""), item.bale_user_id, item.account_id.lower(), item.id.lower(),
            ) if part)
            if needle not in haystack:
                continue
        if status == "expired" and effective_status(item, today_jalali) != "expired":
            continue
        if status == "issued" and effective_status(item, today_jalali) != "issued":
            continue
        selected.append(item)
    page = selected[offset: offset + limit]
    counts = {
        name: int(count)
        for name, count in db.execute(
            select(CertificateRecord.status, func.count(CertificateRecord.id)).group_by(CertificateRecord.status)
        ).all()
    }
    return {
        "source": SOURCE,
        "items": [row(db, item, today_jalali=today_jalali) for item in page],
        "total": len(selected),
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < len(selected),
        "q": q,
        "status": status,
        "kind": kind,
        "event_ref": event_ref,
        "counts": {"issued": counts.get("issued", 0), "revoked": counts.get("revoked", 0)},
    }


def event_options(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        select(CertificateRecord.event_ref, CertificateRecord.event_title, func.count(CertificateRecord.id))
        .where(CertificateRecord.event_ref != "")
        .group_by(CertificateRecord.event_ref, CertificateRecord.event_title)
        .order_by(func.count(CertificateRecord.id).desc())
        .limit(200)
    ).all()
    return [{"event_ref": ref, "event_title": title, "count": int(count)} for ref, title, count in rows]
