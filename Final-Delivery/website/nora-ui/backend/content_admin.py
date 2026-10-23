"""Record-level owner/manager management of events and articles in ``site_content``.

The single ``site_content`` JSON document stays the source of truth for the public
site. This module only adds a *lifecycle* on top of the existing rows:

``draft`` → ``published`` ⇄ ``paused`` → ``archived`` (→ ``draft`` to restore)

Rows are stored through the same allowlist sanitisers that the whole-category
PATCH uses (``site_content._event`` / ``_article``), so an edited record can never
carry fields the public projection does not know. Non-public statuses are kept in
the document and filtered out at read time by ``public_site_content`` — the same
boundary the public API and the SEO snapshot already enforce.

Nothing here deletes a row: archiving keeps the record (and its id) in the
document; restoring moves it back to ``draft``.
"""

from __future__ import annotations

import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from . import event_time
from .site_content import (
    MAX_RECORDS,
    SiteContentError,
    _article,
    _event,
    _join_url,
    _number,
    _parts,
    _public_record,
    _public_url,
    _text,
    _text_list,
)

KINDS = ("events", "articles")
STATUSES = ("draft", "published", "paused", "archived")
# Reviewed transitions; anything else is rejected with ``invalid_status_transition``.
TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"published", "archived"}),
    "published": frozenset({"paused", "archived"}),
    "paused": frozenset({"published", "archived"}),
    "archived": frozenset({"draft"}),
}
SORTS = ("updated", "created", "title", "date")
# Panel audit 1405/08/01 (B1): server-side time buckets for the events list, judged on the
# Tehran calendar day so the client never has to guess "today" from the browser clock.
WHEN_FILTERS = ("today", "upcoming", "past")

# Keys the panel may write. Everything else on a stored row (media files, agenda,
# linked forms, partner references …) is preserved from the stored record.
EVENT_EDITABLE = (
    "t", "kind", "d", "on", "when", "time", "place", "mode", "poster", "tags",
    "price", "cap", "past", "sess", "cert", "certMin", "certNote", "tchr", "partnerId",
    # Phase 7: schedule + registration window (Jalali/Tehran or aware ISO input, UTC storage).
    "startsAt", "endsAt", "regOpensAt", "regClosesAt", "regMode", "lifecycle", "conditions",
    # Phase 8: organizer switch for the event-page Q&A (no site-wide Q&A exists).
    "qaClosed",
    # Panel audit 1405/08/01 (B9): per-session schedule rows rendered by event-page.js.
    "parts",
    # Owner decision 1405/08/01 (B19): reminder switches {"h24": bool, "h1": bool} (event_reminders.py).
    "reminders",
    # Final stage 1405/08/01: HTTPS join link for online/hybrid events (never projected publicly).
    "joinUrl",
)
REMINDER_SLOTS = ("h24", "h1")
EVENT_DATETIME_FIELDS = ("startsAt", "endsAt", "regOpensAt", "regClosesAt")
ARTICLE_EDITABLE = ("t", "cat", "lead", "body", "blocks", "cov", "who", "at", "tags", "pin", "min", "tchr")
EDITABLE = {"events": EVENT_EDITABLE, "articles": ARTICLE_EDITABLE}

_RECORD_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
_JALALI = re.compile(r"^(1[3-4]\d{2})/(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ].*)?$")
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

SANITIZERS: dict[str, Callable[[Any], dict[str, Any] | None]] = {"events": _event, "articles": _article}


class ContentAdminError(ValueError):
    """Validation failure reported to the client as HTTP 422 ``{code, field?}``."""

    def __init__(self, code: str, field: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.field = field


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_record_id(kind: str) -> str:
    prefix = "ev" if kind == "events" else "ar"
    return f"{prefix}-{secrets.token_hex(5)}"


def status_of(row: Any) -> str:
    """Lifecycle status of a stored row, deriving it for legacy rows without ``status``."""
    if not isinstance(row, dict):
        return "draft"
    explicit = _text(row.get("status"), 24, allow_number=False).lower()
    if explicit in STATUSES:
        return explicit
    if explicit in {"private", "hidden", "pending", "unpublished", "rejected"}:
        return "draft"
    return "published" if _public_record(row, require_published=False) and (
        "pub" not in row or _public_record(row, require_published=True)
    ) else "draft"


def normalise_reminders(value: Any) -> dict[str, bool]:
    """``reminders`` payload → ``{"h24": bool, "h1": bool}``; unknown keys/values raise ValueError."""
    if value in (None, ""):
        return {key: False for key in REMINDER_SLOTS}
    if not isinstance(value, dict) or any(key not in REMINDER_SLOTS for key in value):
        raise ValueError("invalid_reminders")
    out: dict[str, bool] = {}
    for key in REMINDER_SLOTS:
        raw = value.get(key, False)
        if raw in (True, 1, "true", "1", "on"):
            out[key] = True
        elif raw in (False, 0, "false", "0", "off", "", None):
            out[key] = False
        else:
            raise ValueError("invalid_reminders")
    return out


def _normalize_digits(value: Any) -> str:
    return _text(value, 40, allow_number=True).translate(_PERSIAN_DIGITS).replace("-", "/").replace(".", "/")


def _validate_event(record: dict[str, Any]) -> None:
    if not _text(record.get("t"), 240):
        raise ContentAdminError("title_required", "t")
    on = _normalize_digits(record.get("on"))
    if on and not _JALALI.fullmatch(on):
        raise ContentAdminError("invalid_jalali_date", "on")
    record["on"] = on
    if not on and not _text(record.get("when"), 120):
        raise ContentAdminError("date_required", "on")
    poster = _text(record.get("poster"), 1_500_000, allow_number=False)
    if poster and not _public_url(poster, image_data=True):
        raise ContentAdminError("invalid_image", "poster")
    join_url = _text(record.get("joinUrl"), 1_000, allow_number=False)
    if join_url and not _join_url(join_url):
        raise ContentAdminError("invalid_link", "joinUrl")
    for key, maximum in (("price", 100_000_000), ("cap", 100_000), ("sess", 500), ("certMin", 100)):
        raw = record.get(key)
        if raw in (None, ""):
            record[key] = 0
            continue
        if isinstance(raw, bool):
            raise ContentAdminError("invalid_number", key)
        try:
            number = int(str(raw).translate(_PERSIAN_DIGITS))
        except ValueError:
            raise ContentAdminError("invalid_number", key) from None
        if number < 0 or number > maximum:
            raise ContentAdminError("invalid_number", key)
        record[key] = number
    if record.get("cert") and record.get("certMin") and record["certMin"] > 100:
        raise ContentAdminError("invalid_number", "certMin")
    for key in ("tchr", "partnerId"):
        value = _text(record.get(key), 100, allow_number=False)
        if value and not _RECORD_ID.fullmatch(value):
            raise ContentAdminError("invalid_reference", key)
    parsed: dict[str, datetime | None] = {}
    for key in EVENT_DATETIME_FIELDS:
        try:
            record[key] = event_time.parse_event_datetime(record.get(key))
        except ValueError:
            raise ContentAdminError("invalid_datetime", key) from None
        moment = event_time.parse_utc(record[key]) if record[key] else None
        if moment is not None and not event_time.clamp_future(moment):
            raise ContentAdminError("invalid_datetime", key)
        parsed[key] = moment
    if parsed["startsAt"] and parsed["endsAt"] and parsed["endsAt"] < parsed["startsAt"]:
        raise ContentAdminError("invalid_datetime_order", "endsAt")
    if parsed["regOpensAt"] and parsed["regClosesAt"] and parsed["regClosesAt"] < parsed["regOpensAt"]:
        raise ContentAdminError("invalid_datetime_order", "regClosesAt")
    reg_mode = _text(record.get("regMode"), 24, allow_number=False).lower()
    if reg_mode and reg_mode not in event_time.REG_MODES:
        raise ContentAdminError("invalid_choice", "regMode")
    record["regMode"] = reg_mode or "auto"
    lifecycle = _text(record.get("lifecycle"), 24, allow_number=False).lower()
    if lifecycle and lifecycle not in event_time.LIFECYCLES:
        raise ContentAdminError("invalid_choice", "lifecycle")
    record["lifecycle"] = lifecycle or "scheduled"
    record["conditions"] = _text(record.get("conditions"), 1_000)
    qa_closed = record.get("qaClosed")
    if qa_closed not in (None, "", True, False, 0, 1, "true", "false"):
        raise ContentAdminError("invalid_choice", "qaClosed")
    record["qaClosed"] = qa_closed in (True, 1, "true")
    record["parts"] = _validate_parts(record.get("parts"))
    try:
        record["reminders"] = normalise_reminders(record.get("reminders"))
    except ValueError:
        raise ContentAdminError("invalid_choice", "reminders") from None


_PART_FIELDS = {"title": 240, "date": 80, "time": 80, "to": 80, "description": 1_200}


def _validate_parts(value: Any) -> list[dict[str, str]]:
    """Session rows: a list (<= 80) of ``{title,date,time,to,description}`` strings (legacy plain
    strings are kept as titles).  Anything else is a field error; the public sanitiser drops rows
    that end up completely empty."""
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > 80:
        raise ContentAdminError("invalid_parts", "parts")
    out: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, str):
            item = {"title": item}
        if not isinstance(item, dict) or set(item) - set(_PART_FIELDS):
            raise ContentAdminError("invalid_parts", "parts")
        row: dict[str, str] = {}
        for key, maximum in _PART_FIELDS.items():
            raw = item.get(key, "")
            if raw is None:
                raw = ""
            if not isinstance(raw, str) or len(raw) > maximum:
                raise ContentAdminError("invalid_parts", "parts")
            row[key] = raw.strip()
        if any(row.values()):
            out.append(row)
    return out


# ویرایشگر بلوکی پنل (ممیزی ۱۴۰۵/۰۸/۰۱، B20): فقط همین انواع ساده که post.html بدون منبع بیرونی رسم می‌کند.
# ویدیو/صدا/فایل/پیوند بیرونی عمداً نیست: نیازمند تصمیم منبع معتبر (فایل نورا/آپارات/یوتیوب با شناسهٔ سرور) است.
_BLOCK_TEXT_FIELDS: dict[str, int] = {"x": 8_000, "t": 240, "cap": 500, "alt": 300, "by": 200, "ic": 40}
_BLOCK_TYPES: dict[str, frozenset[str]] = {
    "p": frozenset({"x"}),
    "h": frozenset({"x", "lv"}),
    "q": frozenset({"x", "by"}),
    "img": frozenset({"up", "src", "cap", "alt"}),
    "ul": frozenset({"x"}),
    "ol": frozenset({"x"}),
    "box": frozenset({"x", "ic"}),
    "tog": frozenset({"x", "t"}),
    "hr": frozenset(),
}
_BLOCK_LIST_TYPES = frozenset({"ul", "ol"})


def _normalize_blocks(value: Any) -> list[dict[str, Any]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > 100:
        raise ContentAdminError("invalid_blocks", "blocks")
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            item = {"ty": "p", "x": item}
        if not isinstance(item, dict) or not isinstance(item.get("ty"), str):
            raise ContentAdminError("invalid_blocks", "blocks")
        block_type = item["ty"]
        allowed = _BLOCK_TYPES.get(block_type)
        if allowed is None or set(item) - allowed - {"ty"}:
            raise ContentAdminError("invalid_blocks", "blocks")
        row: dict[str, Any] = {"ty": block_type}
        for key in allowed:
            raw = item.get(key)
            if raw in (None, ""):
                continue
            if key == "x" and block_type in _BLOCK_LIST_TYPES:
                if isinstance(raw, str):
                    raw = raw.replace("\r", "").split("\n")
                if not isinstance(raw, list) or len(raw) > 100 or any(not isinstance(part, str) or len(part) > 1_000 for part in raw):
                    raise ContentAdminError("invalid_blocks", "blocks")
                items = [part.strip() for part in raw if part.strip()]
                if items:
                    row["x"] = items
                continue
            if key == "lv":
                if isinstance(raw, bool) or str(raw) not in ("2", "3"):
                    raise ContentAdminError("invalid_blocks", "blocks")
                row["lv"] = int(str(raw))
                continue
            if key in ("up", "src"):
                if not isinstance(raw, str) or len(raw) > 1_500 or not _public_url(raw):
                    raise ContentAdminError("invalid_image", "blocks")
                row[key] = raw.strip()
                continue
            limit = _BLOCK_TEXT_FIELDS[key]
            if not isinstance(raw, str) or len(raw) > limit:
                raise ContentAdminError("invalid_blocks", "blocks")
            if raw.strip():
                row[key] = raw.strip()
        if block_type == "hr" or block_type == "img" and (row.get("up") or row.get("src")) or row.get("x"):
            out.append(row)
    return out


def _validate_article(record: dict[str, Any]) -> None:
    if not _text(record.get("t"), 240):
        raise ContentAdminError("title_required", "t")
    body = record.get("body")
    if isinstance(body, str):
        body = [part.strip() for part in body.replace("\r", "").split("\n\n") if part.strip()]
        record["body"] = body
    if body is not None and not isinstance(body, list):
        raise ContentAdminError("invalid_body", "body")
    if "blocks" in record:
        record["blocks"] = _normalize_blocks(record.get("blocks"))
        # «body» همیشه بندهای متنی همان بلوک‌هاست تا فهرست/جست‌وجو/شمارش بندها یک منبع داشته باشند.
        if record["blocks"]:
            record["body"] = [str(block["x"]) for block in record["blocks"] if block["ty"] == "p" and block.get("x")]
    cover = _text(record.get("cov"), 1_500_000, allow_number=False)
    if cover and not _public_url(cover, image_data=True):
        raise ContentAdminError("invalid_image", "cov")
    at = _text(record.get("at"), 80)
    if at:
        if not _ISO_DATE.fullmatch(at.translate(_PERSIAN_DIGITS)):
            raise ContentAdminError("invalid_date", "at")
        record["at"] = at.translate(_PERSIAN_DIGITS)
    minutes = record.get("min")
    if minutes not in (None, ""):
        if isinstance(minutes, bool):
            raise ContentAdminError("invalid_number", "min")
        try:
            record["min"] = int(str(minutes).translate(_PERSIAN_DIGITS))
        except ValueError:
            raise ContentAdminError("invalid_number", "min") from None
        if record["min"] < 0 or record["min"] > 10_000:
            raise ContentAdminError("invalid_number", "min")
    tchr = _text(record.get("tchr"), 100, allow_number=False)
    if tchr and not _RECORD_ID.fullmatch(tchr):
        raise ContentAdminError("invalid_reference", "tchr")


VALIDATORS = {"events": _validate_event, "articles": _validate_article}


def _publishable(kind: str, record: dict[str, Any]) -> None:
    """Extra rules before a record becomes visible on the public site."""
    if kind == "articles" and not (
        _text(record.get("lead"), 1000) or _text_list(record.get("body"), 100, 8000)
        or (isinstance(record.get("blocks"), list) and record["blocks"])
    ):
        raise ContentAdminError("article_body_required", "body")
    if kind == "events" and not _text(record.get("d"), 10_000):
        raise ContentAdminError("event_description_required", "d")


REFERENCE_FIELDS: dict[str, dict[str, str]] = {
    # record field -> site_content category the id must exist in
    "events": {"tchr": "people", "partnerId": "partners"},
    "articles": {"tchr": "people"},
}


def reference_ids(content: Any) -> dict[str, set[str]]:
    """Ids of the categories that events/articles may point at, read from the *same*
    ``site_content`` document (hidden/draft rows included: an owner may link before publishing)."""
    out: dict[str, set[str]] = {}
    source = content if isinstance(content, dict) else {}
    for category in {target for mapping in REFERENCE_FIELDS.values() for target in mapping.values()}:
        ids: set[str] = set()
        for row in source.get(category) or []:
            if isinstance(row, dict):
                value = _text(row.get("id"), 100, allow_number=False)
                if value:
                    ids.add(value)
        out[category] = ids
    return out


def row_changes(stored_rows: Any, final_rows: Any) -> list[tuple[str, str, str]]:
    """Per-row diff of a whole-category replace (people/partners), for the audit trail.

    Owner decision 1405/08/01 (history tab): changes to a person must be findable by that
    person's id, exactly like event/article rows (``content.<kind>`` + record id). Returns
    ``(action, id, title)`` tuples with action ``content.create`` / ``content.update`` /
    ``content.remove``; rows without an id are ignored (the sanitiser drops them anyway).
    """
    def by_id(rows: Any) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict):
                value = _text(row.get("id"), 100, allow_number=False)
                if value and value not in out:
                    out[value] = row
        return out

    def title_of(row: dict[str, Any]) -> str:
        return _text(row.get("n") or row.get("t") or row.get("name"), 120, allow_number=False)

    before, after = by_id(stored_rows), by_id(final_rows)
    changes: list[tuple[str, str, str]] = []
    for row_id, row in after.items():
        if row_id not in before:
            changes.append(("content.create", row_id, title_of(row)))
        elif before[row_id] != row:
            changes.append(("content.update", row_id, title_of(row)))
    for row_id, row in before.items():
        if row_id not in after:
            changes.append(("content.remove", row_id, title_of(row)))
    return changes


def removed_references_in_use(
    category: str, stored_rows: Any, final_rows: Any, content: Any
) -> tuple[list[str], list[dict[str, str]]]:
    """Ids of ``category`` (people/partners) that a whole-category replace would drop although an
    event/article row of the same document still points at them (any lifecycle status).

    Returns ``(removed_ids_in_use, used_by)`` where ``used_by`` names each referencing row with
    ``kind``/``id``/``t``/``ref``. Ids that never existed in the stored category are not reported:
    a stale legacy link must not lock the category (same stance as ``_check_references``)."""
    def ids_of(rows: Any) -> set[str]:
        out: set[str] = set()
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict):
                value = _text(row.get("id"), 100, allow_number=False)
                if value:
                    out.add(value)
        return out

    removed = ids_of(stored_rows) - ids_of(final_rows)
    if not removed:
        return [], []
    source = content if isinstance(content, dict) else {}
    in_use: list[str] = []
    used_by: list[dict[str, str]] = []
    for kind, mapping in REFERENCE_FIELDS.items():
        fields = [field for field, target in mapping.items() if target == category]
        if not fields:
            continue
        for row in source.get(kind) or []:
            if not isinstance(row, dict):
                continue
            for field in fields:
                ref = _text(row.get(field), 100, allow_number=False)
                if ref and ref in removed:
                    if ref not in in_use:
                        in_use.append(ref)
                    used_by.append({
                        "kind": kind,
                        "id": _text(row.get("id"), 100, allow_number=False),
                        "t": _text(row.get("t"), 160),
                        "ref": ref,
                    })
                    if len(used_by) >= 40:
                        return in_use, used_by
    return in_use, used_by


def _check_references(kind: str, incoming: dict[str, Any], references: dict[str, set[str]] | None) -> None:
    """Only ids the client is sending now are checked: a stale id already stored on a legacy row
    must not block status changes or unrelated edits (no silent rewrite of stored data either)."""
    if references is None:
        return
    for field, category in REFERENCE_FIELDS.get(kind, {}).items():
        if field not in incoming:
            continue
        value = _text(incoming.get(field), 100, allow_number=False)
        if value and value not in references.get(category, set()):
            raise ContentAdminError("unknown_reference", field)


def build_record(
    kind: str,
    incoming: Any,
    *,
    existing: dict[str, Any] | None,
    record_id: str,
    status: str,
    references: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    """Merge editable fields onto the stored row and run the canonical sanitiser.

    ``references`` (from :func:`reference_ids`) makes ``tchr``/``partnerId`` real foreign keys into
    the same document; ``None`` keeps the format-only check (status changes, legacy callers)."""
    if kind not in KINDS:
        raise ContentAdminError("invalid_content_kind")
    if not isinstance(incoming, dict):
        raise ContentAdminError("invalid_record")
    unknown = set(incoming) - set(EDITABLE[kind])
    if unknown:
        raise ContentAdminError("unexpected_record_fields", ",".join(sorted(str(key) for key in unknown))[:80])
    merged: dict[str, Any] = dict(existing or {})
    merged.update({key: incoming[key] for key in EDITABLE[kind] if key in incoming})
    merged["id"] = record_id
    if kind == "events" and "parts" not in incoming and merged.get("parts"):
        # Legacy rows (plain strings / alias keys) are normalised leniently; only *incoming* parts are strict.
        merged["parts"] = _parts(merged.get("parts"))
    VALIDATORS[kind](merged)
    _check_references(kind, incoming, references)
    # Force the public flags on a scratch copy so the sanitiser keeps the row; the
    # lifecycle status is re-applied below and decides visibility at read time.
    probe = dict(merged)
    probe.pop("hidden", None)
    probe.pop("pend", None)
    probe["privacy"] = "public"
    probe["pub"] = True
    probe["status"] = "published"
    clean = SANITIZERS[kind](probe)
    if clean is None:
        raise ContentAdminError("invalid_record")
    if status == "published":
        _publishable(kind, clean)
    clean["status"] = status
    created = _text((existing or {}).get("created_at"), 40, allow_number=False)
    clean["created_at"] = created or _now_iso()
    clean["updated_at"] = _now_iso()
    return clean


def apply_status(kind: str, row: dict[str, Any], status: str) -> dict[str, Any]:
    if status not in STATUSES:
        raise ContentAdminError("invalid_status", "status")
    current = status_of(row)
    if status == current:
        raise ContentAdminError("status_unchanged", "status")
    if status not in TRANSITIONS[current]:
        raise ContentAdminError("invalid_status_transition", "status")
    rebuilt = build_record(kind, {}, existing=row, record_id=str(row.get("id")), status=status)
    return rebuilt


def _strip_bytes(row: dict[str, Any]) -> dict[str, Any]:
    """Panel detail without embedded media bytes (they are served by delivery ids)."""
    out = dict(row)
    media = []
    for item in out.get("media") or []:
        if not isinstance(item, dict):
            continue
        slim = {key: value for key, value in item.items() if key not in {"file_data", "src", "url"} or (
            isinstance(value, str) and not value.startswith("data:")
        )}
        slim["has_file"] = bool(item.get("file_data") or str(item.get("src") or "").startswith("data:"))
        media.append(slim)
    if "media" in out:
        out["media"] = media
    return out


def detail(kind: str, row: dict[str, Any], *, has_form: bool | None = None) -> dict[str, Any]:
    """``has_form`` lets the API pass the real link (forms declared on the row *or* a
    published form whose ``event_id`` points here) so the panel state matches the public one."""
    out = _strip_bytes(row)
    out["status"] = status_of(row)
    out["created_at"] = _text(row.get("created_at"), 40, allow_number=False)
    out["updated_at"] = _text(row.get("updated_at"), 40, allow_number=False)
    out["public_path"] = (
        f"event.html?id={row.get('id')}" if kind == "events" else f"post.html?id={row.get('id')}"
    ) if out["status"] == "published" else ""
    if kind == "events":
        # Panel fill-back in the reference zone; the stored value stays UTC.
        out["local_times"] = {key: event_time.to_local_input(row.get(key)) for key in EVENT_DATETIME_FIELDS}
        out["registration"] = event_time.registration_state(
            row, now=datetime.now(timezone.utc),
            has_form=bool(row.get("forms")) if has_form is None else has_form,
        )
    return out


def summary(kind: str, row: dict[str, Any]) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": _text(row.get("id"), 100, allow_number=False),
        "t": _text(row.get("t") or row.get("title") or row.get("n"), 240),
        "status": status_of(row),
        "created_at": _text(row.get("created_at"), 40, allow_number=False),
        "updated_at": _text(row.get("updated_at"), 40, allow_number=False),
        "tags": _text_list(row.get("tags"), 20, 80),
    }
    if kind == "events":
        base.update({
            "kind": _text(row.get("kind"), 80),
            "on": _text(row.get("on"), 40),
            "when": _text(row.get("when"), 120),
            "time": _text(row.get("time"), 120),
            "place": _text(row.get("place"), 240),
            "mode": _text(row.get("mode"), 80),
            "price": _number(row.get("price"), maximum=100_000_000),
            "cap": _number(row.get("cap"), maximum=100_000),
            "past": bool(row.get("past")),
            "cert": bool(row.get("cert")),
            "certMin": _number(row.get("certMin"), maximum=100),
            "sess": _number(row.get("sess"), maximum=500),
            "has_poster": bool(_text(row.get("poster") or row.get("posterUp"), 1_500_000, allow_number=False)),
            "lifecycle": _text(row.get("lifecycle"), 24, allow_number=False) or "scheduled",
            "regMode": _text(row.get("regMode"), 24, allow_number=False) or "auto",
            "startsAt": _text(row.get("startsAt"), 40, allow_number=False),
            "regClosesAt": _text(row.get("regClosesAt"), 40, allow_number=False),
            "forms": [
                {"id": _text(item.get("id"), 120, allow_number=False), "n": _text(item.get("n"), 160)}
                for item in (row.get("forms") or []) if isinstance(item, dict)
            ][:10],
            "tchr": _text(row.get("tchr"), 100, allow_number=False),
            "partnerId": _text(row.get("partnerId"), 100, allow_number=False),
        })
    else:
        base.update({
            "cat": _text(row.get("cat"), 80),
            "lead": _text(row.get("lead"), 240),
            "who": _text(row.get("who") or row.get("author"), 160),
            "at": _text(row.get("at"), 80),
            "pin": bool(row.get("pin")),
            "has_cover": bool(_text(row.get("cov"), 1_500_000, allow_number=False)),
            "paragraphs": len(_text_list(row.get("body"), 100, 8000)),
            "tchr": _text(row.get("tchr"), 100, allow_number=False),
        })
    return base


def _fold(value: Any) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).replace("ي", "ی").replace("ك", "ک").lower()


def _sort_key(kind: str, sort: str) -> Callable[[dict[str, Any]], Any]:
    if sort == "title":
        return lambda row: _fold(row.get("t"))
    if sort == "created":
        return lambda row: str(row.get("created_at") or "")
    if sort == "date":
        if kind == "events":
            def _event_date(row: dict[str, Any]) -> str:
                raw = _normalize_digits(row.get("on"))
                match = _JALALI.fullmatch(raw)
                return f"{match.group(1)}/{int(match.group(2)):02d}/{int(match.group(3)):02d}" if match else ""
            return _event_date
        return lambda row: str(row.get("at") or "")
    return lambda row: str(row.get("updated_at") or row.get("created_at") or "")


def event_day_key(row: dict[str, Any]) -> str:
    """``YYYY/MM/DD`` (zero-padded Jalali) for an event row, or ``""`` when ``on`` is not a date."""
    match = _JALALI.fullmatch(_normalize_digits(row.get("on")))
    return f"{match.group(1)}/{int(match.group(2)):02d}/{int(match.group(3)):02d}" if match else ""


def today_jalali_key() -> str:
    """Tehran calendar day as zero-padded ``YYYY/MM/DD`` (same convention as ``event_day_key``)."""
    now = datetime.now(timezone(timedelta(hours=3, minutes=30)))
    year, month, day = event_time.gregorian_to_jalali(now.year, now.month, now.day)
    return f"{year:04d}/{month:02d}/{day:02d}"


def event_time_bucket(row: dict[str, Any], today: str) -> str:
    """``today`` / ``upcoming`` / ``past`` by the event's Jalali day; ``""`` when the row has no parsable date."""
    key = event_day_key(row)
    if not key:
        return ""
    if key == today:
        return "today"
    return "upcoming" if key > today else "past"


def list_records(
    kind: str,
    rows: Any,
    *,
    q: str = "",
    status: str = "",
    sort: str = "updated",
    order: str = "desc",
    limit: int = 20,
    offset: int = 0,
    when: str = "",
    today: str | None = None,
    mode: str = "",
) -> dict[str, Any]:
    if kind not in KINDS:
        raise ContentAdminError("invalid_content_kind")
    if status and status not in STATUSES:
        raise ContentAdminError("invalid_status", "status")
    if sort not in SORTS:
        raise ContentAdminError("invalid_sort", "sort")
    if when and (when not in WHEN_FILTERS or kind != "events"):
        raise ContentAdminError("invalid_when", "when")
    mode_needle = _fold(mode).strip() if kind == "events" else ""
    if mode and (kind != "events" or not mode_needle):
        raise ContentAdminError("invalid_mode", "mode")
    today_key = today or today_jalali_key()
    source = [row for row in (rows if isinstance(rows, list) else []) if isinstance(row, dict) and row.get("id")]
    counts = {name: 0 for name in STATUSES}
    for row in source:
        counts[status_of(row)] += 1
    needle = _fold(q).strip()
    when_counts = {name: 0 for name in WHEN_FILTERS}
    when_counts["undated"] = 0
    mode_counts: dict[str, int] = {}
    if kind == "events":
        for row in source:
            when_counts[event_time_bucket(row, today_key) or "undated"] += 1
            mode_label = _text(row.get("mode"), 80).strip()
            if mode_label:
                mode_counts[mode_label] = mode_counts.get(mode_label, 0) + 1
    selected = []
    for row in source:
        if status and status_of(row) != status:
            continue
        if when and event_time_bucket(row, today_key) != when:
            continue
        if mode_needle and _fold(row.get("mode")).strip() != mode_needle:
            continue
        if needle:
            haystack = " ".join(
                _fold(part) for part in (
                    row.get("id"), row.get("t"), row.get("kind"), row.get("cat"), row.get("place"),
                    row.get("when"), row.get("on"), row.get("lead"), row.get("who"), row.get("tchr"),
                    " ".join(_text_list(row.get("tags"), 40, 180)),
                ) if part
            )
            if needle not in haystack:
                continue
        selected.append(row)
    selected.sort(key=_sort_key(kind, sort), reverse=(order != "asc"))
    page = selected[offset: offset + limit]
    return {
        "items": [summary(kind, row) for row in page],
        "total": len(selected),
        "counts": counts,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < len(selected),
        "when": when,
        "today": today_key if kind == "events" else "",
        "when_counts": when_counts if kind == "events" else {},
        "mode": mode if kind == "events" else "",
        "mode_counts": mode_counts,
    }


def find_row(rows: Any, record_id: str) -> tuple[int, dict[str, Any]] | None:
    if not _RECORD_ID.fullmatch(record_id or ""):
        return None
    for index, row in enumerate(rows if isinstance(rows, list) else []):
        if isinstance(row, dict) and str(row.get("id") or "") == record_id:
            return index, row
    return None


def ensure_capacity(kind: str, rows: Any) -> None:
    if len(rows if isinstance(rows, list) else []) >= MAX_RECORDS[kind]:
        raise ContentAdminError("content_limit_reached")


__all__ = [
    "ARTICLE_EDITABLE",
    "ContentAdminError",
    "EVENT_EDITABLE",
    "KINDS",
    "SORTS",
    "STATUSES",
    "SiteContentError",
    "TRANSITIONS",
    "apply_status",
    "build_record",
    "detail",
    "ensure_capacity",
    "find_row",
    "list_records",
    "new_record_id",
    "status_of",
    "summary",
]
