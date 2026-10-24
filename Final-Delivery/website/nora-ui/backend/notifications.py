"""Phase 9.4 §7: one idempotent write path for ``user_notifications`` (the outbox the bot drains).

Rules enforced here, not in the callers:

* a notification is created only from a caller that already holds a valid operation state
  (purchase recorded, access granted, …) — this module never decides business state;
* every row carries a stable ``dedupe_key``; a retry, a duplicate webhook or a double click finds
  the existing row instead of adding a second one (unique constraint + savepoint for races);
* ``recorded ≠ sent ≠ delivered``: a new row is ``pending`` (queued) or, for accounts without a
  server-linked Bale identity, an honest ``failed/no_bale_identity`` — never a fake success;
* ``link`` is a relative in-app page only (event/account pages); private file URLs or anything
  with a host, scheme, ``..`` or a download path are refused so a notification body can never
  become a permanent access path.
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Callable, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import UserNotificationRecord

# Kinds introduced in 9.4 (existing ones stay: receipt_review, event_qa_answer, recording_access, recording_order).
KIND_PURCHASE_RECORDED = "recording_purchase"
KIND_CONTENT_PUBLISHED = "recording_content"
KIND_CERTIFICATE = "certificate"

DEDUPE_MAX = 120
LINK_MAX = 200
_LINK_RE = re.compile(r"\A/(?:event|events|account|certificate)\.html(?:\?[A-Za-z0-9_=&%.-]{0,120})?(?:#[A-Za-z0-9_-]{0,40})?\Z")
_FORBIDDEN_IN_LINK = ("/api/", "download", "//", "..", "\\")


class NotificationLinkError(ValueError):
    """The link is not an allowed in-app page path."""


def safe_link(candidate: str | None) -> str | None:
    """Return the link if it is an allowed in-app page path, else raise.

    Only relative paths to the product/account pages are accepted; no scheme, host, API or
    download path can ever end up in a notification.
    """
    if candidate is None or candidate == "":
        return None
    text = str(candidate).strip()
    if len(text) > LINK_MAX or any(bad in text for bad in _FORBIDDEN_IN_LINK) or not _LINK_RE.fullmatch(text):
        raise NotificationLinkError("notification_link_not_allowed")
    return text


def event_link(event_id: str, *, anchor: str = "") -> str:
    """Link to the public event page (the product entry point); anchor optional (e.g. ``recording``)."""
    return safe_link(f"/event.html?id={event_id}" + (f"#{anchor}" if anchor else "")) or ""


def account_link(section: str = "") -> str:
    return safe_link("/account.html" + (f"#{section}" if section else "")) or ""


def dedupe_key(*parts: Any) -> str:
    """Stable key from caller-provided identifiers; never from free text."""
    text = ":".join(str(part) for part in parts if part is not None and str(part) != "")
    if not text or len(text) > DEDUPE_MAX:
        raise ValueError("invalid_dedupe_key")
    return text


def find(db: Session, key: str) -> UserNotificationRecord | None:
    return db.scalar(select(UserNotificationRecord).where(UserNotificationRecord.dedupe_key == key))


def queue(
    db: Session,
    *,
    account_id: str,
    kind: str,
    title: str,
    body: str,
    key: str,
    bale_ids: Sequence[str],
    link: str | None = None,
    file_refs: list[Any] | None = None,
    source_task_id: str | None = None,
    refresh: bool = False,
) -> tuple[UserNotificationRecord, bool]:
    """Insert-or-find by ``key``. Returns ``(row, created)``.

    ``bale_ids`` must come from the server-side identity table (never from the client). With
    ``refresh=True`` an existing, not-yet-delivered row gets the new title/body (used when an
    organizer edits an answer); delivered rows are never rewritten.
    """
    target = str(bale_ids[0]) if bale_ids else ""
    link_value = safe_link(link)
    existing = find(db, key)
    if existing is not None:
        if refresh:
            existing.title = title[:160]
            existing.body = body
            if link_value is not None:
                existing.link = link_value
            if existing.delivery_status != "delivered":
                existing.bale_user_id = target
                existing.delivery_status = "pending" if target else "failed"
                existing.last_delivery_error = None if target else "no_bale_identity"
            db.flush()
        return existing, False
    row = UserNotificationRecord(
        id=str(uuid.uuid4()),
        account_id=account_id,
        bale_user_id=target,
        source_task_id=source_task_id,
        kind=kind,
        title=title[:160],
        body=body,
        link=link_value,
        dedupe_key=key,
        file_refs=list(file_refs or []),
        delivery_status="pending" if target else "failed",
        delivery_attempts=0,
        last_delivery_error=None if target else "no_bale_identity",
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        # Lost a race on the unique key: the other writer's row is the notification.
        winner = find(db, key)
        if winner is None:  # pragma: no cover - only if the constraint fired for another reason
            raise
        return winner, False
    return row, True


def fan_out(
    db: Session,
    *,
    account_ids: Sequence[str],
    kind: str,
    title: str,
    body: str,
    key_for: Callable[[str], str],
    bale_ids_for: Callable[[str], Sequence[str]],
    link: str | None = None,
) -> list[UserNotificationRecord]:
    """Same notification for many accounts (e.g. every active access holder); one row per account per key."""
    created: list[UserNotificationRecord] = []
    for account_id in dict.fromkeys(account_ids):
        row, is_new = queue(
            db, account_id=account_id, kind=kind, title=title, body=body, key=key_for(account_id),
            bale_ids=bale_ids_for(account_id), link=link,
        )
        if is_new:
            created.append(row)
    return created
