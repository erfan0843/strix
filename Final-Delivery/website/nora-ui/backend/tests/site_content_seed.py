"""Shared test helper: seed ``site_content.events`` so ``forms.ev`` can name a real event.

Since the ``forms.ev`` reference check, a form may only point at an event that exists in the
owner's content document. Suites that exercise forms (not content) seed the ids they use here,
straight into the table the API reads, before the app serves its first request.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.models import SiteContentRecord  # noqa: E402


def seed_site_events(engine: Engine, event_ids: Iterable[str] | Mapping[str, str], *, version: int = 1) -> None:
    """Create (or extend) the ``public`` site-content row with public events for ``event_ids``.

    ``event_ids`` may be a mapping ``id -> title`` when a test asserts on the event title."""
    titles = dict(event_ids) if isinstance(event_ids, Mapping) else {event_id: "" for event_id in event_ids}
    with Session(engine) as session:
        record = session.get(SiteContentRecord, "public")
        content = dict(record.content or {}) if record is not None else {}
        events = [row for row in (content.get("events") or []) if isinstance(row, dict)]
        known = {str(row.get("id") or "") for row in events}
        for event_id, title in titles.items():
            if event_id in known:
                continue
            events.append({
                "id": event_id, "t": title or f"رویداد آزمایشی {event_id}", "privacy": "public",
                "when": "2026-11-13", "time": "۱۶:۳۰ تا ۱۹:۰۰", "place": "تهران",
            })
        content["events"] = events
        if record is None:
            session.add(SiteContentRecord(id="public", content=content, version=version))
        else:
            record.content = content
        session.commit()
