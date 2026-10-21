"""Phase 8: event resources, Q&A, attendee reviews and content reports.

Pure rules shared by the HTTP routes in ``app.py``:

* **participation** – what one signed-in account really is for one event, read from
  the same ``form_responses`` rows that registration, payment review and check-in
  write (``accepted`` + approved payment = registered, ``ticket_checked_in_at`` =
  attended). No client-supplied flag is ever consulted.
* **resource access** – the server decides, per download, whether the caller may
  read a resource (``public`` / ``registered`` / ``attended`` / ``staff``), whether
  it is published yet (``status`` + ``publish_at``) and never leaks removed rows.
* **validation** – size/type/filename rules for uploads, text rules for questions
  and reviews (length, duplicates by hash, control characters).
* **serialisation** – public rows never contain account ids, phone numbers or raw
  staff identifiers; the author is a display snapshot.

Everything here is side-effect free apart from the SQLAlchemy session passed in.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlsplit

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from .models import (
    EVENT_RESOURCE_CONTENT_TYPES,
    EVENT_RESOURCE_MAX_BYTES,
    EventContentReportRecord,
    EventQuestionRecord,
    EventResourceRecord,
    EventReviewRecord,
    FormRecord,
    FormResponseDraftRecord,
    FormResponseRecord,
)

ACCESS_LEVELS: tuple[str, ...] = ("public", "registered", "attended", "staff")
RESOURCE_KINDS: tuple[str, ...] = ("file", "link")
RESOURCE_STATUSES: tuple[str, ...] = ("draft", "published", "removed")
QUESTION_STATUSES: tuple[str, ...] = ("pending", "published", "hidden")
REVIEW_STATUSES: tuple[str, ...] = ("pending", "published", "hidden", "withdrawn")
REPORT_STATUSES: tuple[str, ...] = ("open", "resolved", "dismissed")
REPORT_KINDS: tuple[str, ...] = ("question", "review")

MAX_BYTES = EVENT_RESOURCE_MAX_BYTES
CONTENT_TYPES = EVENT_RESOURCE_CONTENT_TYPES
QUESTION_MIN_CHARS = 5
QUESTION_MAX_CHARS = 1000
ANSWER_MAX_CHARS = 2000
REVIEW_MIN_CHARS = 10
REVIEW_MAX_CHARS = 1500
REASON_MAX_CHARS = 300
TITLE_MAX_CHARS = 160
DESCRIPTION_MAX_CHARS = 800
LINK_MAX_CHARS = 2048
QUESTIONS_PER_HOUR = 5
OPEN_QUESTIONS_PER_EVENT = 3
NOTIFICATION_KIND = "event_qa_answer"
ANSWER_LABEL_DEFAULT = "برگزارکننده"
AUTHOR_LABEL_DEFAULT = "کاربر نورا"

_EXTENSIONS: dict[str, str] = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/zip": "zip",
    "audio/mpeg": "mp3",
    "text/plain": "txt",
}
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"ID3", "audio/mpeg"),
    (b"\xff\xfb", "audio/mpeg"),
    (b"\xff\xf3", "audio/mpeg"),
    (b"\xff\xf2", "audio/mpeg"),
)
_OOXML_MARKERS: dict[str, str] = {
    "ppt/": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "word/": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xl/": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
_EXECUTABLE_PREFIXES: tuple[bytes, ...] = (b"MZ", b"\x7fELF", b"#!", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SAFE_NAME = re.compile(r"[^0-9A-Za-z\u0600-\u06FF._ -]+")
_EVENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
_ROW_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class InteractionError(ValueError):
    def __init__(self, code: str, *, status: int = 422, field: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.field = field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def iso(value: datetime | None) -> str:
    moment = as_utc(value)
    return moment.isoformat().replace("+00:00", "Z") if moment else ""


def new_id() -> str:
    return str(uuid.uuid4())


def parse_event_id(value: Any) -> str:
    text = str(value or "").strip()
    if not _EVENT_ID.fullmatch(text):
        raise InteractionError("invalid_event_id", status=404)
    return text


def parse_row_id(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text if _ROW_ID.fullmatch(text) else None


def clean_text(value: Any, limit: int, *, field: str, minimum: int = 0, required: bool = False) -> str:
    if value is None:
        text = ""
    elif isinstance(value, (bool, int, float, list, dict)):
        raise InteractionError("invalid_text", field=field)
    else:
        text = unicodedata.normalize("NFC", str(value))
    text = _CONTROL.sub("", text).replace("\r\n", "\n").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    if required and not text:
        raise InteractionError("text_required", field=field)
    if text and len(text) < minimum:
        raise InteractionError("text_too_short", field=field)
    if len(text) > limit:
        raise InteractionError("text_too_long", field=field)
    return text


def body_hash(text: str) -> str:
    folded = re.sub(r"\s+", " ", text).strip().casefold()
    return hashlib.sha256(folded.encode("utf-8")).hexdigest()


def choice(value: Any, allowed: tuple[str, ...], *, field: str, default: str | None = None) -> str:
    if value in (None, "") and default is not None:
        return default
    text = str(value or "").strip().lower()
    if text not in allowed:
        raise InteractionError("invalid_choice", field=field)
    return text


def safe_link(value: Any) -> str:
    text = clean_text(value, LINK_MAX_CHARS, field="link_url", required=True)
    parts = urlsplit(text)
    if parts.scheme not in {"https", "http"} or not parts.netloc or any(ch.isspace() for ch in text):
        raise InteractionError("invalid_link", field="link_url")
    return text


# ── participation (registration / attendance) ──


@dataclass(frozen=True)
class Participation:
    registered: bool = False
    attended: bool = False
    pending: bool = False
    response_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"registered": self.registered, "attended": self.attended, "pending": self.pending}


def participation_for(
    db: Session,
    account_id: str,
    event_id: str,
    *,
    scope: ColumnElement[bool],
    payment_approved: Callable[[Session, FormResponseRecord], bool],
) -> Participation:
    """Registration/attendance of ``account_id`` for ``event_id`` from the shared rows.

    ``scope`` is the server-built ownership filter (own drafts + verified Bale ids);
    only primary rows (not companions) on registration forms linked to the event
    count. ``registered`` needs ``accepted`` **and** an approved payment (or no
    payment requirement); ``attended`` needs the check-in column. Waitlisted or
    unpaid rows surface as ``pending`` so the page can say why access is missing.
    """
    rows = db.scalars(
        select(FormResponseRecord)
        .join(FormResponseDraftRecord, FormResponseDraftRecord.id == FormResponseRecord.draft_id)
        .join(FormRecord, FormRecord.id == FormResponseRecord.form_id)
        .where(
            scope,
            FormResponseRecord.added_by_response_id.is_(None),
            FormRecord.model == "registration",
            FormRecord.event_id == event_id,
        )
        .order_by(FormResponseRecord.created_at.asc(), FormResponseRecord.id.asc())
    ).all()
    registered = False
    attended = False
    pending = False
    response_id: str | None = None
    for record in rows:
        confirmed = record.status == "accepted" and payment_approved(db, record)
        if not confirmed:
            pending = True
            continue
        registered = True
        if response_id is None:
            response_id = record.id
        if record.ticket_checked_in_at is not None:
            attended = True
            response_id = record.id
    return Participation(registered=registered, attended=attended, pending=pending and not registered, response_id=response_id)


# ── resources ──


def sniff_content_type(content: bytes, declared_name: str) -> str:
    """Decide the stored type from the bytes themselves (plus the extension for text/zip)."""
    if not content:
        raise InteractionError("file_empty", status=400)
    if content.startswith(_EXECUTABLE_PREFIXES):
        raise InteractionError("file_type_not_allowed", status=415)
    for prefix, content_type in _SIGNATURES:
        if content.startswith(prefix):
            return content_type
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"PK\x03\x04"):
        head = content[:4096]
        for marker, content_type in _OOXML_MARKERS.items():
            if marker.encode("ascii") in head:
                return content_type
        if b"[Content_Types].xml" in head:
            # OOXML container without a recognised part in the first entries.
            extension = declared_name.rsplit(".", 1)[-1].lower() if "." in declared_name else ""
            for content_type, ext in _EXTENSIONS.items():
                if ext == extension and content_type in _OOXML_MARKERS.values():
                    return content_type
        return "application/zip"
    extension = declared_name.rsplit(".", 1)[-1].lower() if "." in declared_name else ""
    if extension == "txt":
        try:
            content[:65536].decode("utf-8")
        except UnicodeDecodeError:
            raise InteractionError("file_type_not_allowed", status=415) from None
        return "text/plain"
    raise InteractionError("file_type_not_allowed", status=415)


def safe_file_name(declared: str, content_type: str) -> str:
    """Server-built download name: the declared stem (sanitised) plus the real extension."""
    extension = _EXTENSIONS[content_type]
    stem = str(declared or "").replace("\\", "/").rsplit("/", 1)[-1]
    stem = stem.rsplit(".", 1)[0] if "." in stem else stem
    stem = _SAFE_NAME.sub("", unicodedata.normalize("NFC", stem)).strip(" .-_")[:60]
    return f"{stem or 'resource'}.{extension}"


def content_disposition(file_name: str) -> str:
    """``attachment`` header that stays latin-1 safe (ASCII fallback + RFC 5987 UTF-8 name)."""
    extension = file_name.rsplit(".", 1)[-1] if "." in file_name else "bin"
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", file_name).strip("._") or f"resource.{extension}"
    if not ascii_name.endswith("." + extension):
        ascii_name = f"{ascii_name}.{extension}"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(file_name, safe='')}"


def validate_upload(content: bytes, declared_name: str) -> tuple[str, str, str]:
    """Return ``(content_type, file_name, sha256)`` or raise ``InteractionError``."""
    if len(content) > MAX_BYTES:
        raise InteractionError("file_too_large", status=413)
    content_type = sniff_content_type(content, declared_name)
    if content_type not in CONTENT_TYPES:
        raise InteractionError("file_type_not_allowed", status=415)
    return content_type, safe_file_name(declared_name, content_type), hashlib.sha256(content).hexdigest()


def resource_is_live(record: EventResourceRecord, now: datetime) -> bool:
    if record.status != "published":
        return False
    publish_at = as_utc(record.publish_at)
    return publish_at is None or publish_at <= now


def resource_access_state(
    record: EventResourceRecord,
    *,
    now: datetime,
    signed_in: bool,
    participation: Participation | None,
    staff: bool,
) -> tuple[bool, str]:
    """``(allowed, reason)``; ``reason`` is the user-facing state key when not allowed.

    Staff may always read (preview of drafts and scheduled rows). Everyone else:
    the row must be live, and the access level must be satisfied by the caller's
    real participation. Reasons: ``not_published``, ``login_required``,
    ``registration_required``, ``attendance_required``, ``staff_only``.
    """
    if staff:
        return True, "staff"
    if record.status == "removed":
        return False, "removed"
    if not resource_is_live(record, now):
        return False, "not_published"
    access = record.access
    if access == "public":
        return True, "public"
    if access == "staff":
        return False, "staff_only"
    if not signed_in:
        return False, "login_required"
    part = participation or Participation()
    if access == "registered":
        return (True, "registered") if part.registered else (False, "registration_required")
    if access == "attended":
        return (True, "attended") if part.attended else (False, "attendance_required")
    return False, "staff_only"


def resource_public_view(
    record: EventResourceRecord,
    *,
    now: datetime,
    signed_in: bool,
    participation: Participation | None,
    staff: bool,
) -> dict[str, Any]:
    allowed, reason = resource_access_state(
        record, now=now, signed_in=signed_in, participation=participation, staff=staff
    )
    live = resource_is_live(record, now)
    view: dict[str, Any] = {
        "id": record.id,
        "kind": record.kind,
        "title": record.title,
        "description": record.description,
        "access": record.access,
        "status": record.status if staff else ("published" if live else "scheduled"),
        "publish_at": iso(record.publish_at),
        "published": live,
        "publisher": record.publisher_label,
        "file_name": record.file_name if record.kind == "file" else "",
        "content_type": record.content_type if record.kind == "file" else "",
        "size": record.content_size if record.kind == "file" else 0,
        "allowed": allowed,
        "reason": reason,
        "updated_at": iso(record.updated_at),
    }
    if allowed and record.kind == "link":
        view["link_url"] = record.link_url
    return view


def resource_admin_view(record: EventResourceRecord) -> dict[str, Any]:
    now = utc_now()
    return {
        "id": record.id,
        "event_id": record.event_id,
        "kind": record.kind,
        "title": record.title,
        "description": record.description,
        "access": record.access,
        "status": record.status,
        "live": resource_is_live(record, now),
        "publish_at": iso(record.publish_at),
        "publisher": record.publisher_label,
        "sort_order": record.sort_order,
        "link_url": record.link_url if record.kind == "link" else "",
        "file_name": record.file_name,
        "content_type": record.content_type,
        "size": record.content_size,
        "content_hash": record.content_hash[:16],
        "created_by_kind": record.created_by_kind,
        "created_at": iso(record.created_at),
        "updated_at": iso(record.updated_at),
        "removed_at": iso(record.removed_at),
        "removed_reason": record.removed_reason,
    }


def validate_resource_fields(
    payload: Mapping[str, Any], *, existing: EventResourceRecord | None, parse_datetime: Callable[[Any], str]
) -> dict[str, Any]:
    """Editable metadata (title, description, access, status, publish_at, link, order)."""
    allowed = {"kind", "title", "description", "access", "status", "publish_at", "link_url", "sort_order", "publisher"}
    unknown = set(payload) - allowed
    if unknown:
        raise InteractionError("unexpected_fields", field=",".join(sorted(str(key) for key in unknown))[:80])
    out: dict[str, Any] = {}
    if "kind" in payload or existing is None:
        out["kind"] = choice(payload.get("kind"), RESOURCE_KINDS, field="kind", default="file")
    kind = out.get("kind", existing.kind if existing else "file")
    if "title" in payload or existing is None:
        out["title"] = clean_text(payload.get("title"), TITLE_MAX_CHARS, field="title", required=True, minimum=2)
    if "description" in payload:
        out["description"] = clean_text(payload.get("description"), DESCRIPTION_MAX_CHARS, field="description")
    if "publisher" in payload:
        out["publisher_label"] = clean_text(payload.get("publisher"), 120, field="publisher")
    if "access" in payload or existing is None:
        out["access"] = choice(payload.get("access"), ACCESS_LEVELS, field="access", default="public")
    if "status" in payload:
        status = choice(payload.get("status"), ("draft", "published"), field="status")
        out["status"] = status
    if "publish_at" in payload:
        raw = payload.get("publish_at")
        if raw in (None, ""):
            out["publish_at"] = None
        else:
            try:
                stored = parse_datetime(raw)
            except ValueError:
                raise InteractionError("invalid_datetime", field="publish_at") from None
            if not stored:
                out["publish_at"] = None
            else:
                moment = datetime.fromisoformat(stored.replace("Z", "+00:00"))
                out["publish_at"] = as_utc(moment)
    if kind == "link" and ("link_url" in payload or existing is None or existing.kind != "link"):
        out["link_url"] = safe_link(payload.get("link_url"))
    if "sort_order" in payload:
        raw_order = payload.get("sort_order")
        if isinstance(raw_order, bool) or not isinstance(raw_order, int) or not 0 <= raw_order <= 10_000:
            raise InteractionError("invalid_number", field="sort_order")
        out["sort_order"] = raw_order
    return out


# ── questions ──


def author_label(display_name: str) -> str:
    """Public byline: first name(s) only, never a phone number or id."""
    text = clean_text(display_name, 120, field="author")
    if not text or re.search(r"\d{4,}", text):
        return AUTHOR_LABEL_DEFAULT
    parts = text.split()
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0]}."


def question_public_view(
    record: EventQuestionRecord, *, viewer_account_id: str | None, reported: bool = False
) -> dict[str, Any]:
    mine = viewer_account_id is not None and record.account_id == viewer_account_id
    return {
        "id": record.id,
        "event_id": record.event_id,
        "author": record.author_label or AUTHOR_LABEL_DEFAULT,
        "mine": mine,
        "body": record.body,
        "status": record.status,
        "answered": bool(record.answered_at),
        "answer": record.answer_body if record.answered_at else "",
        "answer_official": bool(record.answer_official) if record.answered_at else False,
        "answer_label": (record.answer_label or ANSWER_LABEL_DEFAULT) if record.answered_at else "",
        "answered_at": iso(record.answered_at),
        "created_at": iso(record.created_at),
        "reported": reported,
    }


def question_admin_view(
    record: EventQuestionRecord, *, notification: Mapping[str, Any] | None, open_reports: int = 0,
    event_title: str = "",
) -> dict[str, Any]:
    view = question_public_view(record, viewer_account_id=None)
    view.update({
        "event_title": event_title,
        "moderation_reason": record.moderation_reason,
        "moderated_by_kind": record.moderated_by_kind,
        "moderated_at": iso(record.moderated_at),
        "answered_by_kind": record.answered_by_kind,
        "notification": dict(notification) if notification else None,
        "open_reports": open_reports,
        "updated_at": iso(record.updated_at),
    })
    return view


def question_visible_to(record: EventQuestionRecord, viewer_account_id: str | None) -> bool:
    if record.status == "published":
        return True
    return viewer_account_id is not None and record.account_id == viewer_account_id


# ── reviews ──


def review_public_view(record: EventReviewRecord, *, viewer_account_id: str | None, reported: bool = False) -> dict[str, Any]:
    mine = viewer_account_id is not None and record.account_id == viewer_account_id
    return {
        "id": record.id,
        "event_id": record.event_id,
        "author": record.author_label or AUTHOR_LABEL_DEFAULT,
        "mine": mine,
        "verified_attendee": bool(record.verified_attendee),
        "body": record.body,
        "status": record.status,
        "edited": record.edit_count > 0,
        "created_at": iso(record.created_at),
        "updated_at": iso(record.updated_at),
        "reported": reported,
    }


def review_admin_view(record: EventReviewRecord, *, open_reports: int = 0, event_title: str = "") -> dict[str, Any]:
    view = review_public_view(record, viewer_account_id=None)
    view.update({
        "event_title": event_title,
        "response_id": record.response_id,
        "edit_count": record.edit_count,
        "moderation_reason": record.moderation_reason,
        "moderated_by_kind": record.moderated_by_kind,
        "moderated_at": iso(record.moderated_at),
        "open_reports": open_reports,
    })
    return view


def review_visible_to(record: EventReviewRecord, viewer_account_id: str | None) -> bool:
    if record.status == "published":
        return True
    if record.status == "withdrawn":
        return viewer_account_id is not None and record.account_id == viewer_account_id
    return viewer_account_id is not None and record.account_id == viewer_account_id


# ── reports ──


def report_admin_view(record: EventContentReportRecord, *, excerpt: str = "", event_title: str = "") -> dict[str, Any]:
    return {
        "id": record.id,
        "event_id": record.event_id,
        "event_title": event_title,
        "target_kind": record.target_kind,
        "target_id": record.target_id,
        "excerpt": excerpt[:160],
        "reason": record.reason,
        "status": record.status,
        "resolution_note": record.resolution_note,
        "resolved_by_kind": record.resolved_by_kind,
        "resolved_at": iso(record.resolved_at),
        "created_at": iso(record.created_at),
    }


def open_report_counts(db: Session, kind: str, target_ids: list[str]) -> dict[str, int]:
    if not target_ids:
        return {}
    counts: dict[str, int] = {}
    for target_id in db.scalars(
        select(EventContentReportRecord.target_id).where(
            EventContentReportRecord.target_kind == kind,
            EventContentReportRecord.status == "open",
            EventContentReportRecord.target_id.in_(target_ids),
        )
    ):
        counts[target_id] = counts.get(target_id, 0) + 1
    return counts


def reported_by(db: Session, kind: str, account_id: str | None, target_ids: list[str]) -> set[str]:
    if not account_id or not target_ids:
        return set()
    return set(db.scalars(
        select(EventContentReportRecord.target_id).where(
            EventContentReportRecord.target_kind == kind,
            EventContentReportRecord.reporter_account_id == account_id,
            EventContentReportRecord.target_id.in_(target_ids),
        )
    ))


# ── notification state ──


def delivery_state(status: str, attempts: int) -> str:
    """``queued`` / ``retrying`` / ``delivered`` / ``failed`` – queued is never shown as delivered."""
    if status == "delivered":
        return "delivered"
    if status == "failed":
        return "failed"
    return "retrying" if attempts > 0 else "queued"


__all__ = [
    "ACCESS_LEVELS",
    "ANSWER_MAX_CHARS",
    "CONTENT_TYPES",
    "InteractionError",
    "MAX_BYTES",
    "NOTIFICATION_KIND",
    "OPEN_QUESTIONS_PER_EVENT",
    "Participation",
    "QUESTIONS_PER_HOUR",
    "QUESTION_MAX_CHARS",
    "QUESTION_MIN_CHARS",
    "REVIEW_MAX_CHARS",
    "REVIEW_MIN_CHARS",
    "author_label",
    "body_hash",
    "choice",
    "clean_text",
    "content_disposition",
    "delivery_state",
    "iso",
    "new_id",
    "open_report_counts",
    "parse_event_id",
    "parse_row_id",
    "participation_for",
    "question_admin_view",
    "question_public_view",
    "question_visible_to",
    "report_admin_view",
    "reported_by",
    "resource_access_state",
    "resource_admin_view",
    "resource_is_live",
    "resource_public_view",
    "review_admin_view",
    "review_public_view",
    "review_visible_to",
    "utc_now",
    "validate_resource_fields",
    "validate_upload",
]
