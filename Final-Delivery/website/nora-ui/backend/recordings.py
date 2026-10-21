"""Phase 9: recorded-content products of held events, orders and access rights.

Pure rules shared by the HTTP routes in ``app.py``. Three concepts never merge:

* **event + attendance** – from ``site_content`` and ``form_responses`` (phase 7/8);
  attendance is *read* here only to decide the ``attendee_access`` courtesy and the
  review badge, never written.
* **recorded product** – ``event_recordings`` (one per event) with ordered
  ``recording_sessions``; files/handouts are ordinary ``event_resources`` rows that
  carry ``session_id`` and ``access='purchased'``.
* **access right** – ``recording_access`` per account, created by a verified
  payment (``recording_orders``), a free claim or an audited manual grant.

Everything here is side-effect free apart from the SQLAlchemy session passed in;
no route trusts a client-supplied access flag, price or account id.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping
from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import video_sources
from .event_interaction import (
    EMBED_KINDS,
    InteractionError,
    Participation,
    as_utc,
    choice,
    clean_text,
    iso,
    resource_is_live,
    utc_now,
)
from .financials import PaymentConfigurationError, normalize_payment_methods
from .models import (
    RECORDING_ACCESS_SOURCES,
    RECORDING_ACCESS_STATUSES,
    RECORDING_ORDER_METHODS,
    RECORDING_ORDER_STATUSES,
    RECORDING_SESSION_STATUSES,
    RECORDING_STATUSES,
    EventRecordingRecord,
    EventResourceRecord,
    FormRecord,
    RecordingAccessRecord,
    RecordingOrderRecord,
    RecordingSessionRecord,
)
from .responses import public_payment_card, purchase_form_price

STATUSES = RECORDING_STATUSES
SESSION_STATUSES = RECORDING_SESSION_STATUSES
ORDER_METHODS = RECORDING_ORDER_METHODS
ORDER_STATUSES = RECORDING_ORDER_STATUSES
ACCESS_SOURCES = RECORDING_ACCESS_SOURCES
ACCESS_STATUSES = RECORDING_ACCESS_STATUSES

# Public shelf: on sale or paused (paused is shown as off-sale, never as a dead button).
SHELF_STATUSES: tuple[str, ...] = ("published", "sales_paused")
OPEN_ORDER_STATUSES: tuple[str, ...] = ("pending", "awaiting_receipt", "receipt_submitted", "needs_review")
PAID_ORDER_STATUSES: tuple[str, ...] = ("paid", "paid_manual")
CLOSED_ORDER_STATUSES: tuple[str, ...] = ("rejected", "cancelled", "expired", "refunded")
REVIEWABLE_ORDER_STATUSES: tuple[str, ...] = ("receipt_submitted", "needs_review")
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("ready", "archived"),
    "ready": ("draft", "published", "archived"),
    "published": ("sales_paused", "archived"),
    "sales_paused": ("published", "archived"),
    "archived": ("ready",),
}
REASON_REQUIRED_STATUSES: tuple[str, ...] = ("sales_paused", "archived")

MAX_PRICE = 2_000_000_000
MAX_ACCESS_DAYS = 3650
MAX_FAQ = 12
MAX_SESSIONS = 60
TITLE_MAX = 160
SHORT_TEXT_MAX = 2000
LONG_TEXT_MAX = 6000
REASON_MAX = 300
NOTE_MAX = 300
RECEIPT_MAX_BYTES = 8 * 1024 * 1024
CARD_ORDER_TTL = timedelta(days=3)
WALLET_ORDER_TTL_SECONDS_DEFAULT = 900
INVOICE_PREFIX = "norac_"
NOTIFICATION_KIND = "recording_access"
ORDER_NOTIFICATION_KIND = "recording_order"
CURRENCY = "IRR"
# Completion-certificate policy of a recorded product. There is deliberately no automatic mode:
# the server has no trustworthy completion/scoring signal (the form builder does not grade
# answers server-side and play events are browser values), so ``manual`` only records that the
# organiser *may* issue a certificate through the existing bot issuance path (permission +
# action log + shared mirror).  Purchase alone never yields a certificate of any kind.
CERTIFICATE_POLICIES: tuple[str, ...] = ("none", "manual")
CERTIFICATE_KIND = "recording_completion"
PURCHASE_FORM_PURPOSE = "recording_access"

_SAFE_RELATIVE = re.compile(r"^/api/public/media/[0-9a-f-]{36}$")
_RECEIPT_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"%PDF-", "application/pdf"),
)


def new_order_idempotency_key(recording_id: str, account_id: str, nonce: str) -> str:
    return f"rec:{recording_id[:8]}:{account_id[:8]}:{nonce}"[:80]


# ── event facts ──


def event_held(event: Mapping[str, Any], now: datetime) -> bool:
    """True once the event has really taken place according to the server clock.

    ``past`` is the editor's explicit flag; otherwise the end time, or the start
    time when no end is recorded. Cancelled events are never "held".
    """
    if str(event.get("lifecycle") or "") == "cancelled":
        return False
    if event.get("past") is True:
        return True
    registration = event.get("registration") if isinstance(event.get("registration"), Mapping) else {}
    ends = _parse(event.get("endsAt")) or _parse(registration.get("endsAt") if registration else None)
    starts = _parse(event.get("startsAt")) or _parse(registration.get("startsAt") if registration else None)
    if ends is not None:
        return ends <= now
    return starts is not None and starts <= now


def _parse(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


# ── validation ──


def _flag(value: Any, *, field: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise InteractionError("invalid_flag", field=field)


def _price(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        if isinstance(value, str) and re.fullmatch(r"\d{1,10}", value.strip()):
            value = int(value.strip())
        else:
            raise InteractionError("invalid_number", field="price")
    if not 0 <= value <= MAX_PRICE:
        raise InteractionError("invalid_number", field="price")
    return value


def _access_days(value: Any) -> int | None:
    if value in (None, "", 0):
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_ACCESS_DAYS:
        raise InteractionError("invalid_number", field="access_days")
    return value


def _faq(value: Any) -> list[dict[str, str]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or len(value) > MAX_FAQ:
        raise InteractionError("invalid_faq", field="faq")
    out: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) - {"q", "a"}:
            raise InteractionError("invalid_faq", field="faq")
        question = clean_text(item.get("q"), 300, field="faq", required=True, minimum=3)
        answer = clean_text(item.get("a"), SHORT_TEXT_MAX, field="faq", required=True, minimum=2)
        out.append({"q": question, "a": answer})
    return out


def _cover(value: Any) -> str:
    text = clean_text(value, 2048, field="cover_url")
    if not text:
        return ""
    if _SAFE_RELATIVE.fullmatch(text):
        return text
    parts = urlsplit(text)
    if parts.scheme != "https" or not parts.netloc or any(ch.isspace() for ch in text):
        raise InteractionError("invalid_link", field="cover_url")
    return text


def _payment_card(value: Any) -> dict[str, str] | None:
    if value in (None, "", {}):
        return None
    if not isinstance(value, Mapping):
        raise InteractionError("invalid_payment_card", field="payment_card")
    card = public_payment_card({"paymentCard": dict(value)})
    if card is None:
        raise InteractionError("invalid_payment_card", field="payment_card")
    return card


def validate_recording_fields(payload: Mapping[str, Any], *, existing: EventRecordingRecord | None) -> dict[str, Any]:
    """Editable product fields; status changes go through ``transition`` only."""
    allowed = {
        "title", "summary", "outcomes", "audience", "access_terms", "refund_policy", "faq", "price",
        "access_days", "attendee_access", "download_default", "bale_enabled", "payment_card", "cover_url",
        "expected_version", "certificate_policy",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise InteractionError("unexpected_fields", field=",".join(sorted(str(key) for key in unknown))[:80])
    out: dict[str, Any] = {}
    if "title" in payload or existing is None:
        out["title"] = clean_text(payload.get("title"), TITLE_MAX, field="title", minimum=2)
    for key, limit in (
        ("summary", SHORT_TEXT_MAX), ("outcomes", SHORT_TEXT_MAX), ("audience", SHORT_TEXT_MAX),
        ("access_terms", SHORT_TEXT_MAX), ("refund_policy", LONG_TEXT_MAX),
    ):
        if key in payload:
            out[key] = clean_text(payload.get(key), limit, field=key)
    if "faq" in payload:
        out["faq"] = _faq(payload.get("faq"))
    if "price" in payload or existing is None:
        out["price"] = _price(payload.get("price", 0))
    if "access_days" in payload:
        out["access_days"] = _access_days(payload.get("access_days"))
    for key, default in (("attendee_access", False), ("download_default", True), ("bale_enabled", True)):
        if key in payload:
            out[key] = _flag(payload.get(key), field=key, default=default)
    if "payment_card" in payload:
        out["payment_card"] = _payment_card(payload.get("payment_card"))
    if "cover_url" in payload:
        out["cover_url"] = _cover(payload.get("cover_url"))
    if "certificate_policy" in payload:
        out["certificate_policy"] = choice(payload.get("certificate_policy"), CERTIFICATE_POLICIES, field="certificate_policy")
    return out


COMMERCIAL_FIELDS: tuple[str, ...] = ("price", "payment_card", "bale_enabled")


def commercial_fields_changed(fields: Mapping[str, Any], existing: EventRecordingRecord) -> list[str]:
    """Which product-level commercial fields a PUT tries to change (refused once a form is linked)."""
    changed: list[str] = []
    for key in COMMERCIAL_FIELDS:
        if key in fields and fields[key] != getattr(existing, key):
            changed.append(key)
    return changed


def validate_session_fields(payload: Mapping[str, Any], *, existing: RecordingSessionRecord | None) -> dict[str, Any]:
    allowed = {"title", "description", "sort_order", "duration_minutes", "status", "preview"}
    unknown = set(payload) - allowed
    if unknown:
        raise InteractionError("unexpected_fields", field=",".join(sorted(str(key) for key in unknown))[:80])
    out: dict[str, Any] = {}
    if "title" in payload or existing is None:
        out["title"] = clean_text(payload.get("title"), TITLE_MAX, field="title", required=True, minimum=2)
    if "description" in payload:
        out["description"] = clean_text(payload.get("description"), SHORT_TEXT_MAX, field="description")
    if "sort_order" in payload:
        raw = payload.get("sort_order")
        if isinstance(raw, bool) or not isinstance(raw, int) or not 0 <= raw <= 10_000:
            raise InteractionError("invalid_number", field="sort_order")
        out["sort_order"] = raw
    if "duration_minutes" in payload:
        raw = payload.get("duration_minutes")
        if raw in (None, "", 0):
            out["duration_minutes"] = None
        elif isinstance(raw, bool) or not isinstance(raw, int) or not 1 <= raw <= 6000:
            raise InteractionError("invalid_number", field="duration_minutes")
        else:
            out["duration_minutes"] = raw
    if "status" in payload:
        out["status"] = choice(payload.get("status"), SESSION_STATUSES, field="status")
    if "preview" in payload:
        out["preview"] = _flag(payload.get("preview"), field="preview", default=False)
    return out


def validate_reason(value: Any, *, required: bool) -> str:
    return clean_text(value, REASON_MAX, field="reason", required=required, minimum=3 if required else 0)


def sniff_receipt(content: bytes) -> str:
    if not content:
        raise InteractionError("file_empty", status=400)
    if len(content) > RECEIPT_MAX_BYTES:
        raise InteractionError("file_too_large", status=413)
    for prefix, content_type in _RECEIPT_SIGNATURES:
        if content.startswith(prefix):
            return content_type
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    raise InteractionError("file_type_not_allowed", status=415)


def safe_receipt_name(declared: str, content_type: str) -> str:
    extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "application/pdf": "pdf"}[content_type]
    stem = str(declared or "").replace("\\", "/").rsplit("/", 1)[-1]
    stem = stem.rsplit(".", 1)[0] if "." in stem else stem
    stem = re.sub(r"[^0-9A-Za-z\u0600-\u06FF._ -]+", "", unicodedata.normalize("NFC", stem)).strip(" .-_")[:60]
    return f"{stem or 'receipt'}.{extension}"


# ── status machine ──


def can_transition(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, ())


def publish_blockers(
    recording: EventRecordingRecord,
    event: Mapping[str, Any] | None,
    sessions: list[RecordingSessionRecord],
    resources: list[EventResourceRecord],
    *,
    now: datetime,
    wallet_ready: bool,
    commerce: Commerce | None = None,
) -> list[str]:
    """Why the product cannot go on sale right now (empty list = may publish)."""
    blockers: list[str] = []
    if event is None:
        blockers.append("event_not_published")
    else:
        if str(event.get("lifecycle") or "") == "cancelled":
            blockers.append("event_cancelled")
        elif not event_held(event, now):
            blockers.append("event_not_held")
    if not recording.title.strip():
        blockers.append("no_title")
    published_sessions = {row.id for row in sessions if row.status == "published"}
    if not published_sessions:
        blockers.append("no_published_session")
    if not any(
        row.session_id in published_sessions and row.status == "published" and (row.kind != "file" or row.content is not None)
        for row in resources
    ):
        blockers.append("no_live_resource")
    if commerce is None:
        commerce = commerce_for(recording, None, wallet_ready=wallet_ready)
    if commerce.source != "form":
        if commerce.price > 0:
            # Paid products sell only through a purchase form built in the form builder.
            blockers.append("purchase_form_required")
    elif not commerce.valid:
        blockers.append("purchase_form_invalid_price")
    elif commerce.form_status != "published":
        blockers.append("purchase_form_not_published")
    elif commerce.price > 0 and not commerce.methods:
        blockers.append("no_payment_method")
    return blockers


# ── access ──


def access_state(row: RecordingAccessRecord | None, now: datetime) -> str:
    """``active`` / ``expired`` / ``revoked`` / ``none`` — evaluated on every request."""
    if row is None:
        return "none"
    if row.status == "revoked":
        return "revoked"
    expires = as_utc(row.expires_at)
    if expires is not None and expires <= now:
        return "expired"
    return "active" if row.status == "active" else row.status


def access_for(db: Session, recording_id: str, account_id: str | None) -> RecordingAccessRecord | None:
    if not account_id:
        return None
    return db.scalar(
        select(RecordingAccessRecord).where(
            RecordingAccessRecord.recording_id == recording_id, RecordingAccessRecord.account_id == account_id,
        )
    )


def open_order_for(db: Session, recording_id: str, account_id: str | None) -> RecordingOrderRecord | None:
    if not account_id:
        return None
    return db.scalar(
        select(RecordingOrderRecord)
        .where(
            RecordingOrderRecord.recording_id == recording_id,
            RecordingOrderRecord.account_id == account_id,
            RecordingOrderRecord.status.in_(OPEN_ORDER_STATUSES),
        )
        .order_by(RecordingOrderRecord.created_at.desc())
    )


def latest_closed_order_for(db: Session, recording_id: str, account_id: str | None) -> RecordingOrderRecord | None:
    if not account_id:
        return None
    return db.scalar(
        select(RecordingOrderRecord)
        .where(
            RecordingOrderRecord.recording_id == recording_id,
            RecordingOrderRecord.account_id == account_id,
            RecordingOrderRecord.status.in_(("rejected", "cancelled", "expired")),
        )
        .order_by(RecordingOrderRecord.created_at.desc())
    )


def expire_open_order(order: RecordingOrderRecord, now: datetime) -> bool:
    """Lazily expire a timed-out open order (returns True when the row changed)."""
    expires = as_utc(order.expires_at)
    if order.status in OPEN_ORDER_STATUSES and order.status != "needs_review" and expires is not None and expires <= now:
        order.status = "expired"
        order.updated_at = now
        return True
    return False


def access_expiry(recording: EventRecordingRecord, now: datetime, *, days: int | None = None) -> datetime | None:
    span = days if days is not None else recording.access_days
    return now + timedelta(days=span) if span else None


@dataclass(frozen=True)
class Viewer:
    signed_in: bool
    staff: bool
    account_id: str | None
    participation: Participation | None
    access: RecordingAccessRecord | None
    access_state: str
    open_order: RecordingOrderRecord | None
    previous_order: RecordingOrderRecord | None


@dataclass(frozen=True)
class Commerce:
    """Where the product's price / payment methods come from (phase 9.1).

    ``source='form'``: a purchase form (``forms.purpose='recording_access'``) is
    linked to the product and its builder settings are authoritative. ``source=
    'product'``: no purchase form exists; the product may only be free (claim) —
    a paid product without a published purchase form cannot be published.
    """

    source: str
    price: int
    currency: str
    methods: tuple[str, ...]
    form_id: str | None
    form_status: str
    form_title: str
    valid: bool

    @property
    def free(self) -> bool:
        return self.valid and self.price <= 0

    @property
    def on_sale(self) -> bool:
        return self.source != "form" or self.form_status == "published"


def purchase_form_for(db: Session, recording_id: str) -> FormRecord | None:
    """The purchase form of a product: the published one, else the most recent one."""
    rows = list(db.scalars(
        select(FormRecord)
        .where(FormRecord.recording_id == recording_id, FormRecord.purpose == PURCHASE_FORM_PURPOSE)
        .order_by(FormRecord.updated_at.desc(), FormRecord.id.desc())
    ).all())
    for row in rows:
        if row.status == "published":
            return row
    return rows[0] if rows else None


def purchase_forms_for(db: Session, recording_ids: list[str]) -> dict[str, FormRecord]:
    out: dict[str, FormRecord] = {}
    if not recording_ids:
        return out
    rows = db.scalars(
        select(FormRecord)
        .where(FormRecord.recording_id.in_(recording_ids), FormRecord.purpose == PURCHASE_FORM_PURPOSE)
        .order_by(FormRecord.updated_at.desc(), FormRecord.id.desc())
    ).all()
    for row in rows:
        current = out.get(str(row.recording_id))
        if current is None or (current.status != "published" and row.status == "published"):
            out[str(row.recording_id)] = row
    return out


def commerce_for(recording: EventRecordingRecord, form: FormRecord | None, *, wallet_ready: bool) -> Commerce:
    """Derive price and methods from the purchase form when one exists (never from both)."""
    if form is None:
        methods: list[str] = []
        if recording.payment_card is not None:
            methods.append("card_transfer")
        if recording.bale_enabled and wallet_ready:
            methods.append("bale_wallet")
        return Commerce(
            source="product", price=int(recording.price), currency=recording.currency, methods=tuple(methods),
            form_id=None, form_status="", form_title="", valid=True,
        )
    settings = form.settings if isinstance(form.settings, dict) else {}
    price = purchase_form_price(settings)
    try:
        selected = normalize_payment_methods(settings)
    except PaymentConfigurationError:
        selected = []
    methods = []
    if price is not None and price > 0:
        if "card_transfer" in selected and settings.get("receiptReviewRequired") is True and public_payment_card(settings) is not None:
            methods.append("card_transfer")
        if "bale_wallet" in selected and wallet_ready:
            methods.append("bale_wallet")
    return Commerce(
        source="form", price=price if price is not None else 0, currency=CURRENCY, methods=tuple(methods),
        form_id=form.id, form_status=form.status, form_title=form.title, valid=price is not None,
    )


def commerce_view(commerce: Commerce) -> dict[str, Any]:
    return {
        "source": commerce.source,
        "price": commerce.price,
        "currency": commerce.currency,
        "free": commerce.free,
        "methods": list(commerce.methods),
        "form_id": commerce.form_id,
        "form_status": commerce.form_status,
        "form_title": commerce.form_title,
        "valid": commerce.valid,
        "on_sale": commerce.on_sale,
    }


def has_content_access(recording: EventRecordingRecord, viewer: Viewer) -> tuple[bool, str]:
    """Server-side decision whether the viewer may read purchased-only resources."""
    if viewer.staff:
        return True, "staff"
    if viewer.access_state == "active":
        return True, "purchased"
    if recording.attendee_access and viewer.participation is not None and viewer.participation.attended:
        return True, "attended"
    if viewer.access_state in {"expired", "revoked"}:
        return False, f"access_{viewer.access_state}"
    if not viewer.signed_in:
        return False, "login_required"
    return False, "purchase_required"


def viewer_cta(
    recording: EventRecordingRecord, viewer: Viewer, *, wallet_ready: bool, commerce: Commerce | None = None,
) -> dict[str, Any]:
    """The single call to action the page may show; nothing else is derived client-side.

    ``form_id`` (when present) is the purchase form: the page sends the member to
    ``form.html?fid=…`` and never to a parallel checkout.
    """
    if commerce is None:
        commerce = commerce_for(recording, None, wallet_ready=wallet_ready)
    allowed, reason = has_content_access(recording, viewer)
    methods = list(commerce.methods)
    form_id = commerce.form_id
    if allowed:
        kind = "staff_preview" if reason == "staff" and viewer.access_state != "active" else "view"
        return {"kind": kind, "reason": reason, "methods": methods, "form_id": form_id}
    if recording.status not in SHELF_STATUSES:
        return {"kind": "unavailable", "reason": recording.status, "methods": [], "form_id": form_id}
    if recording.status == "sales_paused":
        return {"kind": "off_sale", "reason": "sales_paused", "methods": [], "form_id": form_id}
    if commerce.source == "form" and (not commerce.valid or commerce.form_status != "published"):
        return {"kind": "off_sale", "reason": "purchase_form_not_published", "methods": [], "form_id": form_id}
    if not viewer.signed_in:
        return {"kind": "login", "reason": "login_required", "methods": methods, "form_id": form_id}
    if viewer.open_order is not None:
        return {
            "kind": "order_open", "reason": viewer.open_order.status, "methods": methods, "form_id": form_id,
            "order": order_account_view(viewer.open_order, recording),
        }
    if commerce.price <= 0:
        return {"kind": "free", "reason": "free", "methods": [], "form_id": form_id}
    if commerce.source != "form":
        return {"kind": "off_sale", "reason": "purchase_form_required", "methods": [], "form_id": None}
    if not methods:
        return {"kind": "off_sale", "reason": "no_payment_method", "methods": [], "form_id": form_id}
    out: dict[str, Any] = {"kind": "buy", "reason": reason, "methods": methods, "form_id": form_id}
    if viewer.previous_order is not None:
        out["previous"] = {"status": viewer.previous_order.status, "id": viewer.previous_order.id}
    return out


# ── views ──


def _text_block(value: str) -> str:
    return value or ""


def payment_card_view(card: Mapping[str, Any] | None, *, masked: bool) -> dict[str, str] | None:
    if not card:
        return None
    number = str(card.get("number") or "")
    return {
        "number": (number[:4] + "******" + number[-4:]) if masked and len(number) == 16 else number,
        "bank": str(card.get("bank") or ""),
        "holder": str(card.get("holder") or ""),
    }


def session_public_view(
    session: RecordingSessionRecord, resources: list[dict[str, Any]], *, staff: bool
) -> dict[str, Any]:
    view: dict[str, Any] = {
        "id": session.id,
        "title": session.title,
        "description": session.description,
        "sort_order": session.sort_order,
        "duration_minutes": session.duration_minutes,
        "preview": session.preview,
        "resources": resources,
    }
    if staff:
        view["status"] = session.status
    return view


def session_admin_view(session: RecordingSessionRecord, *, resource_count: int = 0) -> dict[str, Any]:
    return {
        "id": session.id,
        "recording_id": session.recording_id,
        "title": session.title,
        "description": session.description,
        "sort_order": session.sort_order,
        "duration_minutes": session.duration_minutes,
        "status": session.status,
        "preview": session.preview,
        "resource_count": resource_count,
        "created_at": iso(session.created_at),
        "updated_at": iso(session.updated_at),
    }


def session_resource_view(
    resource: EventResourceRecord, *, recording: EventRecordingRecord, session: RecordingSessionRecord,
    allowed: bool, reason: str, now: datetime, staff: bool,
) -> dict[str, Any]:
    """Per-file state inside a session: preview files are open to everyone, the rest follow access."""
    live = resource_is_live(resource, now)
    preview = bool(session.preview)
    open_to_all = preview and resource.access in {"public", "purchased"}
    final_allowed = staff or (live and (allowed or open_to_all))
    final_reason = "staff" if staff else ("preview" if open_to_all and not allowed else reason)
    if not live and not staff:
        final_allowed, final_reason = False, "not_published"
    video = video_sources.from_stored(resource.kind, resource.link_url) if resource.kind in EMBED_KINDS else None
    playable = (resource.kind == "file" and resource.content_type in {"video/mp4", "audio/mpeg"}) or video is not None
    view: dict[str, Any] = {
        "id": resource.id,
        "kind": resource.kind,
        "title": resource.title,
        "description": resource.description,
        "access": resource.access,
        "delivery": resource.delivery,
        "file_name": resource.file_name if resource.kind == "file" else "",
        "content_type": resource.content_type if resource.kind == "file" else "",
        "size": resource.content_size if resource.kind == "file" else 0,
        "published": live,
        "publish_at": iso(resource.publish_at),
        "allowed": final_allowed,
        "reason": final_reason,
        "playable": playable,
        "downloadable": resource.delivery == "download" and resource.kind == "file",
        "preview": open_to_all,
    }
    if staff:
        view["status"] = resource.status
    if final_allowed and resource.kind == "link":
        view["link_url"] = resource.link_url
    if resource.kind in EMBED_KINDS:
        # External embed (YouTube/Aparat): not private hosting, no DRM; the id is public once allowed.
        view["external"] = True
        if final_allowed:
            view["video"] = video.as_dict() if video is not None else None
            view["link_url"] = video.watch_url if video is not None else ""
    return view


def certificate_view(recording: EventRecordingRecord) -> dict[str, Any]:
    """Honest certificate statement for one recorded product.

    * ``kind`` is the completion certificate («پایان محتوای آموزشی ضبط‌شده»), never the event's
      attendance certificate — buying or watching a recording is not attendance.
    * ``automatic`` is always ``False``: nothing on the server issues a certificate from a
      purchase, an access grant or a play event.
    * ``manual_issue_only`` mirrors the organiser's explicit per-product toggle.
    """
    return {
        "kind": CERTIFICATE_KIND,
        "policy": recording.certificate_policy,
        "automatic": False,
        "manual_issue_only": recording.certificate_policy == "manual",
        "counts_as_attendance": False,
    }


def recording_public_view(
    recording: EventRecordingRecord,
    *,
    sessions: list[dict[str, Any]],
    viewer: Viewer,
    cta: dict[str, Any],
    total_minutes: int,
    staff: bool,
    commerce: Commerce | None = None,
) -> dict[str, Any]:
    allowed, reason = has_content_access(recording, viewer)
    if commerce is None:
        commerce = commerce_for(recording, None, wallet_ready=False)
    view: dict[str, Any] = {
        "id": recording.id,
        "event_id": recording.event_id,
        "status": recording.status,
        "title": recording.title,
        "summary": _text_block(recording.summary),
        "outcomes": _text_block(recording.outcomes),
        "audience": _text_block(recording.audience),
        "access_terms": _text_block(recording.access_terms),
        "refund_policy": _text_block(recording.refund_policy),
        "faq": list(recording.faq or []),
        # Price/method come from the purchase form when one is linked (single source).
        "price": commerce.price,
        "currency": commerce.currency,
        "free": commerce.free,
        "purchase": {
            "form_id": commerce.form_id,
            "source": commerce.source,
            "methods": list(commerce.methods),
            "on_sale": commerce.on_sale and recording.status == "published",
        },
        "certificate_policy": recording.certificate_policy,
        "certificate": certificate_view(recording),
        "access_days": recording.access_days,
        "attendee_access": recording.attendee_access,
        "download_default": recording.download_default,
        "cover_url": recording.cover_url,
        "published_at": iso(recording.published_at),
        "session_count": len(sessions),
        "total_minutes": total_minutes,
        "sessions": sessions,
        "viewer": {
            "signed_in": viewer.signed_in,
            "staff": staff,
            "access": {
                "state": viewer.access_state,
                "allowed": allowed,
                "reason": reason,
                "source": viewer.access.source if viewer.access is not None else "",
                "expires_at": iso(viewer.access.expires_at) if viewer.access is not None else "",
            },
            "cta": cta,
        },
    }
    if staff:
        view["status_reason"] = recording.status_reason
    return view


def recording_admin_view(
    recording: EventRecordingRecord,
    *,
    sessions: list[dict[str, Any]],
    blockers: list[str],
    counts: Mapping[str, int],
    event_title: str = "",
    commerce: Commerce | None = None,
) -> dict[str, Any]:
    if commerce is None:
        commerce = commerce_for(recording, None, wallet_ready=False)
    return {
        "id": recording.id,
        "event_id": recording.event_id,
        "event_title": event_title,
        "status": recording.status,
        "status_reason": recording.status_reason,
        "title": recording.title,
        "summary": recording.summary,
        "outcomes": recording.outcomes,
        "audience": recording.audience,
        "access_terms": recording.access_terms,
        "refund_policy": recording.refund_policy,
        "faq": list(recording.faq or []),
        # Stored product fields (legacy / free-claim only once a purchase form exists).
        "price": recording.price,
        "currency": recording.currency,
        # Effective commercial settings: the purchase form wins when linked.
        "commerce": commerce_view(commerce),
        "certificate_policy": recording.certificate_policy,
        "certificate": certificate_view(recording),
        "access_days": recording.access_days,
        "attendee_access": recording.attendee_access,
        "download_default": recording.download_default,
        "bale_enabled": recording.bale_enabled,
        "payment_card": payment_card_view(recording.payment_card, masked=False),
        "cover_url": recording.cover_url,
        "published_at": iso(recording.published_at),
        "version": recording.version,
        "sessions": sessions,
        "publish_blockers": blockers,
        "transitions": list(TRANSITIONS.get(recording.status, ())),
        "counts": dict(counts),
        "created_at": iso(recording.created_at),
        "updated_at": iso(recording.updated_at),
    }


def recording_card_view(
    recording: EventRecordingRecord, *, session_count: int, total_minutes: int, commerce: Commerce | None = None,
) -> dict[str, Any]:
    """Compact, secret-free summary attached to the public event snapshot."""
    if commerce is None:
        commerce = commerce_for(recording, None, wallet_ready=False)
    return {
        "id": recording.id,
        "status": recording.status,
        "sellable": recording.status == "published" and commerce.on_sale,
        "title": recording.title,
        "summary": recording.summary[:300],
        "price": commerce.price,
        "currency": commerce.currency,
        "free": commerce.free,
        "purchase_form_id": commerce.form_id,
        "access_days": recording.access_days,
        "cover_url": recording.cover_url,
        "session_count": session_count,
        "total_minutes": total_minutes,
        "published_at": iso(recording.published_at),
    }


def order_account_view(order: RecordingOrderRecord, recording: EventRecordingRecord | None = None) -> dict[str, Any]:
    view: dict[str, Any] = {
        "id": order.id,
        "recording_id": order.recording_id,
        "method": order.method,
        "status": order.status,
        "open": order.status in OPEN_ORDER_STATUSES,
        "paid": order.status in PAID_ORDER_STATUSES,
        "amount": order.amount,
        "currency": order.currency,
        "expires_at": iso(order.expires_at),
        "receipt_submitted": order.receipt_submitted_at is not None,
        "receipt_submitted_at": iso(order.receipt_submitted_at),
        "receipt_file_name": order.receipt_file_name,
        "paid_at": iso(order.paid_at),
        "decided_at": iso(order.decided_at),
        "decision_reason": order.decision_reason if order.status in {"rejected", "refunded"} else "",
        "refunded_at": iso(order.refunded_at),
        "form_response_id": order.form_response_id,
        "form_payment_id": order.form_payment_id,
        "created_at": iso(order.created_at),
        "updated_at": iso(order.updated_at),
    }
    if order.method == "bale_wallet" and order.status == "pending" and order.invoice_url:
        view["invoice_url"] = order.invoice_url
    if recording is not None:
        view["event_id"] = recording.event_id
        view["title"] = recording.title
        if (
            order.method == "card_transfer" and order.status in {"awaiting_receipt", "receipt_submitted"}
            and order.form_payment_id is None
        ):
            # Legacy (pre-9.1) order: the destination card lived on the product.
            view["card"] = payment_card_view(recording.payment_card, masked=False)
    return view


def order_admin_view(
    order: RecordingOrderRecord,
    *,
    recording: EventRecordingRecord | None,
    event_title: str = "",
    access: RecordingAccessRecord | None = None,
    duplicates: int = 0,
    account_label: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    moment = now or utc_now()
    return {
        "id": order.id,
        "recording_id": order.recording_id,
        "event_id": recording.event_id if recording is not None else "",
        "event_title": event_title,
        "product_title": recording.title if recording is not None else "",
        "account_id": order.account_id,
        "account_label": account_label,
        "method": order.method,
        "status": order.status,
        "open": order.status in OPEN_ORDER_STATUSES,
        "reviewable": order.status in REVIEWABLE_ORDER_STATUSES,
        "amount": order.amount,
        "currency": order.currency,
        "expires_at": iso(order.expires_at),
        "payer_bale_user_id": order.payer_bale_user_id or "",
        "transaction_id": order.transaction_id or "",
        "has_receipt": order.receipt_content is not None,
        "receipt_file_name": order.receipt_file_name,
        "receipt_content_type": order.receipt_content_type,
        "receipt_size": order.receipt_size,
        "receipt_note": order.receipt_note,
        "receipt_submitted_at": iso(order.receipt_submitted_at),
        "paid_at": iso(order.paid_at),
        "decided_at": iso(order.decided_at),
        "decided_by_kind": order.decided_by_kind,
        "decision_reason": order.decision_reason,
        "review_note": order.review_note,
        "refund_reference": order.refund_reference,
        "refunded_at": iso(order.refunded_at),
        "duplicates": duplicates,
        "form_response_id": order.form_response_id,
        "form_payment_id": order.form_payment_id,
        "access": access_view(access, moment) if access is not None else None,
        "created_at": iso(order.created_at),
        "updated_at": iso(order.updated_at),
    }


def access_view(row: RecordingAccessRecord, now: datetime, *, account_label: str = "") -> dict[str, Any]:
    return {
        "id": row.id,
        "recording_id": row.recording_id,
        "account_id": row.account_id,
        "account_label": account_label,
        "source": row.source,
        "status": row.status,
        "state": access_state(row, now),
        "order_id": row.order_id,
        "expires_at": iso(row.expires_at),
        "granted_by_kind": row.granted_by_kind,
        "reason": row.reason,
        "revoked_at": iso(row.revoked_at),
        "revoke_reason": row.revoke_reason,
        "created_at": iso(row.created_at),
        "updated_at": iso(row.updated_at),
    }


def library_item_view(
    row: RecordingAccessRecord, recording: EventRecordingRecord, *, now: datetime, session_count: int,
    total_minutes: int, event_title: str,
) -> dict[str, Any]:
    state = access_state(row, now)
    return {
        "recording_id": recording.id,
        "event_id": recording.event_id,
        "title": recording.title or event_title,
        "event_title": event_title,
        "cover_url": recording.cover_url,
        "status": recording.status,
        "session_count": session_count,
        "total_minutes": total_minutes,
        "access": {
            "state": state,
            "source": row.source,
            "expires_at": iso(row.expires_at),
            "granted_at": iso(row.created_at),
            "revoked_at": iso(row.revoked_at),
        },
        "certificate": certificate_view(recording),
        # Watch progress is not recorded anywhere yet: the page must not pretend otherwise.
        "progress": None,
    }


# ── aggregates ──


def session_stats(db: Session, recording_ids: list[str]) -> dict[str, tuple[int, int]]:
    """``{recording_id: (published_session_count, total_minutes)}``."""
    if not recording_ids:
        return {}
    rows = db.execute(
        select(
            RecordingSessionRecord.recording_id,
            func.count(RecordingSessionRecord.id),
            func.coalesce(func.sum(RecordingSessionRecord.duration_minutes), 0),
        )
        .where(
            RecordingSessionRecord.recording_id.in_(recording_ids),
            RecordingSessionRecord.status == "published",
        )
        .group_by(RecordingSessionRecord.recording_id)
    ).all()
    return {str(recording_id): (int(count), int(minutes or 0)) for recording_id, count, minutes in rows}


def order_filters(status: str) -> tuple[str, ...]:
    if status == "review":
        return REVIEWABLE_ORDER_STATUSES
    if status == "open":
        return OPEN_ORDER_STATUSES
    if status == "paid":
        return PAID_ORDER_STATUSES
    if status == "closed":
        return CLOSED_ORDER_STATUSES
    if status in ORDER_STATUSES:
        return (status,)
    raise InteractionError("invalid_choice", field="status")
