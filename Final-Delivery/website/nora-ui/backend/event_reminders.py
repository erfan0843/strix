"""Owner decision 1405/08/01 (B19): event reminders on the *existing* scheduler + outbox.

No parallel scheduler, table or sender: ``scheduled_publish.announce_due`` (systemd timer /
manual run) calls :func:`enqueue_due` in the same pass, and every reminder is one
``user_notifications`` row written through :mod:`notifications` (the in-app list reads it, the
bot drains it to Bale with the existing retry policy — a Bale failure marks *delivery* failed and
never removes the in-app row).

Rules (all server-side):

* per-event settings ``reminders = {"h24": bool, "h1": bool}`` on the event row, independent;
* recipients = accounts behind **accepted** registrations (``form_responses.status`` is only ever
  ``accepted`` / ``waitlisted``; a cancelled registration has no row) of the primary registration
  form linked to *that* event (same form selection as the panel's registration summary),
  excluding waitlisted rows, companion rows (no own account), purchases whose payment is not
  approved yet (``_response_payment_approved``) and drafts without a resolvable account; other
  events are never touched;
* a slot is due only inside its window computed from the *current* ``startsAt`` (stored UTC,
  entered in Asia/Tehran) — ``h24``: [start−24h, start−1h), ``h1``: [start−1h, start). A
  cancelled/postponed or unpublished event, or one without a start time, has no due slot;
* idempotent per ``(event, slot, start time, account)`` through the outbox dedupe key, so a timer
  restart, a double manual run or a racing second runner never duplicates a reminder; a changed
  start time yields a fresh key and :func:`cancel_stale` withdraws still-undelivered rows of the
  old time (or of a cancelled event) in the outbox instead of letting the bot send them;
* text = title + start time (Jalali, Tehran) + place/mode; no SMS channel exists here.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import content_admin, event_time
from . import notifications as notifications_mod
from .models import (
    FormRecord,
    FormResponseDraftRecord,
    FormResponseRecord,
    PlatformIdentityRecord,
    SiteContentRecord,
    UserNotificationRecord,
)

KIND = "event_reminder"
SLOT_KEYS = ("h24", "h1")
# slot → (offset before start, length of the sending window)
SLOT_WINDOWS: dict[str, tuple[timedelta, timedelta]] = {
    "h24": (timedelta(hours=24), timedelta(hours=23)),
    "h1": (timedelta(hours=1), timedelta(hours=1)),
}
SLOT_LABEL = {"h24": "فردا", "h1": "تا یک ساعت دیگر"}
STALE_ERROR = "reminder_superseded"
STALE_BODY_HEAD = "این یادآوری دیگر معتبر نیست (زمان رویداد تغییر کرده یا رویداد لغو/به‌تعویق افتاده است)؛ زمان تازه را در صفحهٔ رویداد ببینید."


class ReminderSettingsError(ValueError):
    """``reminders`` is not an object of the two known boolean switches."""


def normalise_settings(value: Any) -> dict[str, bool]:
    """Validate the panel payload: missing → both off; unknown keys/values → error."""
    try:
        return content_admin.normalise_reminders(value)
    except ValueError as error:
        raise ReminderSettingsError(str(error)) from None


def settings_of(row: Any) -> dict[str, bool]:
    """Stored settings of an event row (never raises; legacy rows → both off)."""
    try:
        return normalise_settings(row.get("reminders") if isinstance(row, dict) else None)
    except ReminderSettingsError:
        return {key: False for key in SLOT_KEYS}


def start_of(row: Any) -> datetime | None:
    return event_time.parse_utc(row.get("startsAt")) if isinstance(row, dict) else None


def is_active(row: dict[str, Any]) -> bool:
    """Published and still scheduled (not cancelled/postponed)."""
    return content_admin.status_of(row) == "published" and str(row.get("lifecycle") or "scheduled") == "scheduled"


def due_slots(row: dict[str, Any], now: datetime) -> list[str]:
    """Slots whose window contains ``now`` for a published, scheduled event with a start time."""
    if not is_active(row):
        return []
    starts = start_of(row)
    if starts is None or starts <= now:
        return []
    enabled = settings_of(row)
    due: list[str] = []
    for slot in SLOT_KEYS:
        if not enabled[slot]:
            continue
        offset, length = SLOT_WINDOWS[slot]
        opens = starts - offset
        if opens <= now < opens + length:
            due.append(slot)
    return due


def primary_registration_form(db: Session, row: dict[str, Any], *, is_purchase: Callable[[FormRecord], bool]) -> FormRecord | None:
    """The one published registration form of this event (declared on the row wins over a
    form that merely points at the event); purchase forms and other events' forms never qualify."""
    event_id = str(row.get("id") or "")
    if not event_id:
        return None
    declared = [str(form.get("id") or "") for form in (row.get("forms") or []) if isinstance(form, dict)]
    candidates = db.scalars(
        select(FormRecord)
        .where(FormRecord.status == "published", FormRecord.need == "reg", FormRecord.purpose == "registration")
        .where(or_(FormRecord.event_id == event_id, FormRecord.id.in_(declared)) if declared else FormRecord.event_id == event_id)
    ).all()
    primary: FormRecord | None = None
    for form in candidates:
        if is_purchase(form) or (form.event_id and str(form.event_id) != event_id):
            continue
        if primary is None or (form.id in declared and primary.id not in declared):
            primary = form
    return primary


def recipient_accounts(
    db: Session,
    form_id: str,
    *,
    payment_approved: Callable[[Session, FormResponseRecord], bool],
) -> tuple[list[str], dict[str, int]]:
    """Account ids of accepted, paid/approved primary registrations of ``form_id``.

    Bot-side registrations (draft without ``account_id``) resolve through the server-verified
    Bale identity table only; anything unresolvable is counted, not guessed.
    Returns ``(account_ids, counters)``.
    """
    rows = db.execute(
        select(FormResponseRecord, FormResponseDraftRecord)
        .join(FormResponseDraftRecord, FormResponseDraftRecord.id == FormResponseRecord.draft_id)
        .where(FormResponseRecord.form_id == form_id, FormResponseRecord.added_by_response_id.is_(None))
        .order_by(FormResponseRecord.created_at, FormResponseRecord.id)
    ).all()
    counters = {"accepted": 0, "waitlisted": 0, "unpaid": 0, "no_account": 0}
    accounts: list[str] = []
    for record, draft in rows:
        if record.status != "accepted":
            counters["waitlisted"] += 1
            continue
        if not payment_approved(db, record):
            counters["unpaid"] += 1
            continue
        account_id = draft.account_id
        if not account_id and draft.bot_bale_user_id:
            account_id = db.scalar(
                select(PlatformIdentityRecord.account_id).where(
                    PlatformIdentityRecord.provider == "bale",
                    PlatformIdentityRecord.provider_user_id == str(draft.bot_bale_user_id),
                )
            )
        if not account_id:
            counters["no_account"] += 1
            continue
        counters["accepted"] += 1
        accounts.append(account_id)
    return list(dict.fromkeys(accounts)), counters


def key_prefix(event_id: str) -> str:
    return f"event_reminder:{event_id}:"


def dedupe_key(event_id: str, slot: str, starts: datetime, account_id: str) -> str:
    stamp = int(starts.astimezone(timezone.utc).timestamp())
    return notifications_mod.dedupe_key("event_reminder", event_id, slot, stamp, account_id)


def message_for(row: dict[str, Any], slot: str, starts: datetime) -> tuple[str, str]:
    title = str(row.get("t") or row.get("n") or "رویداد")[:120]
    when = event_time.to_local_input(event_time.to_iso(starts))
    place = str(row.get("place") or "").strip()
    mode = str(row.get("mode") or "").strip()
    where = " · ".join(part for part in (place, {"online": "برخط", "onsite": "حضوری", "hybrid": "حضوری و برخط"}.get(mode, mode)) if part)
    head = f"یادآوری: «{title}» {SLOT_LABEL[slot]} برگزار می‌شود."
    body = f"{head}\nزمان شروع: {when} (به وقت تهران)" + (f"\nمکان: {where}" if where else "") + "\nجزئیات و تغییرات احتمالی در صفحهٔ رویداد."
    return (f"یادآوری رویداد: {title}"[:160], body)


def cancel_stale(db: Session, row: dict[str, Any]) -> int:
    """Withdraw reminders of this event that no longer match its current data.

    Only rows the bot has **not delivered yet** are touched: they become ``failed`` with
    ``reminder_superseded`` (visible in the outbox, excluded from the bot's pending list and from
    the manual retry). Stale = the event is no longer active (cancelled/postponed/unpublished) or
    the row was keyed for a start time other than the current one. Delivered rows are history.
    Returns the number of rows withdrawn.
    """
    event_id = str(row.get("id") or "")
    if not event_id:
        return 0
    starts = start_of(row) if is_active(row) else None
    valid = {dedupe_key(event_id, slot, starts, "") for slot in SLOT_KEYS} if starts else set()
    rows = db.scalars(
        select(UserNotificationRecord).where(
            UserNotificationRecord.kind == KIND,
            UserNotificationRecord.dedupe_key.like(key_prefix(event_id) + "%"),
            UserNotificationRecord.delivery_status == "pending",
        )
    ).all()
    withdrawn = 0
    for item in rows:
        key = item.dedupe_key or ""
        if any(key.startswith(prefix) for prefix in valid):
            continue
        item.delivery_status = "failed"
        item.last_delivery_error = STALE_ERROR
        # The in-app row stays (nothing is deleted) but must not keep promising the old time:
        # the member reads the same row with an explicit "superseded" head.
        if not (item.body or "").startswith(STALE_BODY_HEAD):
            item.body = (STALE_BODY_HEAD + "\n" + (item.body or ""))[:2000]
        withdrawn += 1
    return withdrawn


def enqueue_due(
    db: Session,
    now: datetime,
    *,
    is_purchase: Callable[[FormRecord], bool],
    payment_approved: Callable[[Session, FormResponseRecord], bool],
    bale_ids_for: Callable[[str], list[str]],
) -> dict[str, Any]:
    """One pass over the event rows: withdraw stale reminders, then queue every due
    (event, slot, recipient) exactly once.

    Called inside the scheduler's transaction; the caller commits. Never raises for a single
    event's data problem (counted in ``skipped``).
    """
    summary: dict[str, Any] = {"events": 0, "slots": 0, "queued": 0, "existing": 0, "skipped": 0, "recipients": 0, "withdrawn": 0}
    record = db.get(SiteContentRecord, "public")
    rows = ((record.content if record else None) or {}).get("events") or []
    for row in rows:
        if not isinstance(row, dict):
            continue
        summary["withdrawn"] += cancel_stale(db, row)
        slots = due_slots(row, now)
        if not slots:
            continue
        summary["events"] += 1
        starts = start_of(row)
        if starts is None:  # pragma: no cover - due_slots already requires it
            continue
        form = primary_registration_form(db, row, is_purchase=is_purchase)
        if form is None:
            summary["skipped"] += 1
            continue
        accounts, _counters = recipient_accounts(db, form.id, payment_approved=payment_approved)
        summary["recipients"] += len(accounts)
        event_id = str(row.get("id") or "")
        link = notifications_mod.event_link(event_id)
        for slot in slots:
            summary["slots"] += 1
            title, body = message_for(row, slot, starts)
            for account_id in accounts:
                _row, created = notifications_mod.queue(
                    db, account_id=account_id, kind=KIND, title=title, body=body,
                    key=dedupe_key(event_id, slot, starts, account_id), bale_ids=bale_ids_for(account_id), link=link,
                )
                summary["queued" if created else "existing"] += 1
    return summary


def preview(db: Session, row: dict[str, Any], now: datetime, *, is_purchase: Callable[[FormRecord], bool]) -> dict[str, Any]:
    """Panel read model: what is configured, when each slot fires and what the outbox holds (no sending)."""
    starts = start_of(row)
    enabled = settings_of(row)
    form = primary_registration_form(db, row, is_purchase=is_purchase) if starts else None
    event_id = str(row.get("id") or "")
    queued = db.scalars(
        select(UserNotificationRecord).where(
            UserNotificationRecord.kind == KIND, UserNotificationRecord.dedupe_key.like(key_prefix(event_id) + "%"),
        )
    ).all() if event_id else []
    slots = []
    for slot in SLOT_KEYS:
        offset, length = SLOT_WINDOWS[slot]
        fire_at = starts - offset if starts else None
        state = "off"
        if enabled[slot] and fire_at is not None:
            if not is_active(row):
                state = "inactive"
            elif now >= fire_at + length:
                state = "window_passed"
            elif now >= fire_at:
                state = "due"
            else:
                state = "scheduled"
        elif enabled[slot]:
            state = "needs_start_time"
        mine = [item for item in queued if f":{slot}:" in (item.dedupe_key or "")]
        current = [item for item in mine if starts and item.dedupe_key and item.dedupe_key.startswith(dedupe_key(event_id, slot, starts, ""))]
        counts = {status: sum(1 for item in current if item.delivery_status == status) for status in ("pending", "delivered", "failed")}
        slots.append({
            "slot": slot, "enabled": enabled[slot], "fire_at": fire_at.isoformat() if fire_at else None,
            # Jalali/Tehran text, same helper the event editor shows for startsAt (panel never converts dates itself).
            "fire_at_local": event_time.to_local_input(event_time.to_iso(fire_at)) if fire_at else None, "state": state,
            "queued": len(current), "delivery": counts, "superseded": sum(1 for item in mine if item.last_delivery_error == STALE_ERROR),
        })
    return {
        "enabled": enabled,
        "starts_at": starts.isoformat() if starts else None,
        "form_id": form.id if form else None,
        "slots": slots,
        "channels": ["in_app", "bale"],
        "runner": "scheduled_publish timer / manual run",
    }
