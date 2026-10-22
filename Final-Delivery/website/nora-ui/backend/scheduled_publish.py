"""Phase 9.5 §8.2 — explicit, idempotent, monitored announcement of scheduled content.

Visibility of a scheduled resource is *computed* on every request (``event_interaction.is_live``:
``status == published`` **and** ``publish_at <= now``), so a future ``publish_at`` is never public
and nothing here flips visibility. What needs a clock is the **announcement** to access holders:
the "new content" outbox rows are only correct once the content is really visible.

* ``notify_content_published`` is the single fan-out used by the admin routes (immediate publish)
  and by ``announce_due`` (scheduled publish). Dedupe key
  ``recording_content:<session|resource>:<id>:<account>`` makes both paths idempotent.
* ``announce_due`` marks each row ``announced_at`` exactly once and writes the
  ``scheduled_publish`` system marker (read by the storage health view / panel) so a stalled
  timer is visible instead of silently missing announcements.
* The CLI (``python -m backend.scheduled_publish --once``) is meant for a systemd timer; the
  admin route ``POST /api/admin/scheduled-publish/run`` runs the very same function on demand.

Failures of the notification layer never roll back the publish itself: this module only touches
``announced_at`` / outbox rows / the marker, inside its own transaction.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import notifications as notifications_mod
from . import recordings as recordings_mod
from .models import (
    EventRecordingRecord,
    EventResourceRecord,
    PlatformIdentityRecord,
    RecordingSessionRecord,
    SiteContentRecord,
    SystemMarkerRecord,
)

MARKER_KEY = "scheduled_publish"


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def verified_bale_ids(db: Session, account_id: str) -> list[str]:
    """Bale IDs the server itself linked to the account (never client-supplied)."""
    return list(db.scalars(
        select(PlatformIdentityRecord.provider_user_id).where(
            PlatformIdentityRecord.provider == "bale", PlatformIdentityRecord.account_id == account_id,
        )
    ))


def event_title(db: Session, event_id: str) -> str:
    record = db.get(SiteContentRecord, "public")
    rows = list(((record.content if record else None) or {}).get("events") or [])
    for row in rows:
        if isinstance(row, dict) and str(row.get("id") or "") == event_id:
            return str(row.get("t") or row.get("n") or "")[:160]
    return ""


def notify_content_published(
    db: Session,
    recording: EventRecordingRecord,
    *,
    what: str,
    target_id: str,
    title_text: str,
    now: datetime,
    bale_ids_for: Callable[[str], Sequence[str]] | None = None,
    event_title_for: Callable[[str], str] | None = None,
) -> int:
    """New session/resource went live for a published product: one outbox row per *active* holder.

    Real data path only: the product must be published. Key
    ``recording_content:<what>:<id>:<account>`` so re-publishing after a draft round-trip, a double
    click, or the scheduler running after an immediate publish never duplicates a row.
    Returns the number of rows actually created.
    """
    if recording.status != "published":
        return 0
    holders = recordings_mod.active_holders(db, recording.id, now)
    if not holders:
        return 0
    titles = event_title_for or (lambda event_id: event_title(db, event_id))
    product = recording.title or titles(recording.event_id) or "محتوای ضبط‌شده"
    noun = "جلسهٔ تازه" if what == "session" else "فایل/منبع تازه"
    body = (f"{noun} «{title_text}» برای «{product}» منتشر شد.\n"
            "برای مشاهده به صفحهٔ همان رویداد یا بخش «محتوای من» در حساب کاربری بروید.")
    created = notifications_mod.fan_out(
        db, account_ids=holders, kind=notifications_mod.KIND_CONTENT_PUBLISHED,
        title="محتوای تازه در محصول خریداری‌شده", body=body,
        key_for=lambda account_id: notifications_mod.dedupe_key("recording_content", what, target_id, account_id),
        bale_ids_for=bale_ids_for or (lambda account_id: verified_bale_ids(db, account_id)),
        link=notifications_mod.event_link(recording.event_id, anchor="recording"),
    )
    return len(created)


def due_resources(db: Session, now: datetime) -> list[EventResourceRecord]:
    """Published, scheduled, now live, not yet announced — oldest first."""
    rows = db.scalars(
        select(EventResourceRecord).where(
            EventResourceRecord.status == "published",
            EventResourceRecord.publish_at.is_not(None),
            EventResourceRecord.announced_at.is_(None),
        ).order_by(EventResourceRecord.publish_at, EventResourceRecord.id)
    ).all()
    return [row for row in rows if (as_utc(row.publish_at) or now) <= now]


def write_marker(db: Session, now: datetime, value: dict[str, Any]) -> None:
    row = db.get(SystemMarkerRecord, MARKER_KEY)
    if row is None:
        db.add(SystemMarkerRecord(key=MARKER_KEY, value=value, updated_at=now))
    else:
        row.value = value
        row.updated_at = now


def announce_due(db: Session, now: datetime | None = None, *, actor: str = "timer") -> dict[str, Any]:
    """One pass: announce every due resource exactly once; commit; record the marker.

    Safe to run as often as wanted (timer + manual run + restart): a row is claimed by setting
    ``announced_at`` in the same transaction as its outbox rows, and the dedupe key guards the
    outbox even if two runners race.
    """
    now = now or datetime.now(timezone.utc)
    summary: dict[str, Any] = {"ok": True, "actor": actor, "due": 0, "announced": 0, "notified": 0, "skipped": 0, "errors": 0}
    try:
        for resource in due_resources(db, now):
            summary["due"] += 1
            product: EventRecordingRecord | None = None
            session = db.get(RecordingSessionRecord, resource.session_id) if resource.session_id else None
            if session is not None and session.status == "published":
                product = db.get(EventRecordingRecord, session.recording_id)
            if product is None or product.status != "published":
                # Event-level rows (no product holders) and rows of unpublished products/sessions have
                # nobody to announce to; they are marked so the scheduler does not re-scan them forever.
                # If the product is published later, its own publish path announces the live content.
                resource.announced_at = now
                summary["skipped"] += 1
                continue
            summary["notified"] += notify_content_published(
                db, product, what="resource", target_id=resource.id, title_text=resource.title, now=now,
            )
            resource.announced_at = now
            summary["announced"] += 1
        db.commit()
    except Exception as error:  # noqa: BLE001 - recorded in the marker; the caller decides what to do
        db.rollback()
        summary["ok"] = False
        summary["errors"] = 1
        summary["error_type"] = type(error).__name__
    summary["at"] = now.isoformat()
    write_marker(db, now, {k: v for k, v in summary.items() if k != "at"})
    db.commit()
    return summary


def pending_count(db: Session, now: datetime) -> dict[str, int]:
    """Panel/monitoring: how many scheduled rows are still in the future vs. due-but-unannounced."""
    rows = db.scalars(
        select(EventResourceRecord).where(
            EventResourceRecord.status == "published", EventResourceRecord.publish_at.is_not(None),
            EventResourceRecord.announced_at.is_(None),
        )
    ).all()
    future = sum(1 for row in rows if (as_utc(row.publish_at) or now) > now)
    return {"future": future, "due_unannounced": len(rows) - future}


def _database_url() -> str:
    url = os.environ.get("NORA_DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("NORA_DATABASE_URL is required (same value as the web service)")
    return url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--once", action="store_true", required=True, help="run one pass and exit (use a systemd timer for periodic runs)")
    parser.add_argument("--json", action="store_true", help="machine-readable summary")
    args = parser.parse_args(argv)
    from sqlalchemy import create_engine  # noqa: PLC0415

    engine = create_engine(_database_url(), pool_pre_ping=True)
    try:
        with Session(engine) as db:
            summary = announce_due(db, actor="cli")
    finally:
        engine.dispose()
    if args.json:
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print(f"scheduled-publish: due={summary['due']} announced={summary['announced']} notified={summary['notified']} "
              f"skipped={summary['skipped']} ok={summary['ok']}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
