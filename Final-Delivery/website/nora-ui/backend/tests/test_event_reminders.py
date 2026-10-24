"""Owner decision 1405/08/01 (B19): event reminders on the existing scheduler + outbox.

Covers: both slots (24h / 1h) independently; recipients = accepted registrations of the event's
own form only (not waitlisted, not other events, not events with reminders off); idempotency
across repeated/restarted runs; start-time change (stale pending rows withdrawn, fresh window
once); cancellation (pending rows withdrawn, nothing new); in-app row survives a Bale delivery
failure; outbox visibility and permissions; scheduler summary/marker; payload validation.
Test DB + signed test Bale init-data only — no real message leaves the process.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend import event_reminders as reminders_mod  # noqa: E402
from backend import event_time  # noqa: E402
from backend import scheduled_publish as scheduled_publish_mod  # noqa: E402
from backend.models import SystemMarkerRecord, UserNotificationRecord  # noqa: E402
from test_event_interaction_api import register  # noqa: E402
from test_event_registration_gate import (  # noqa: E402
    ORIGIN,
    create_published_event,
    event_payload,
    gate_app,
    update_event,
)
from test_workflows_api import (  # noqa: E402
    assign_manager,
    bale_login,
    owner_login,
    owner_write_headers,
    service_headers,
)

M1, M2, M3, M4 = 81001, 81002, 81003, 81004


def publish_form(client: TestClient, *, event_id: str, key: str, cap: int = 0, wait: int = 0) -> str:
    payload = {
        "name": "فرم ثبت‌نام یادآور",
        "model": "registration",
        "need": "reg",
        "ev": event_id,
        "settings": {"cap": cap, "wait": wait} if cap else {},
        "fields": [{"id": "full-name", "t": "fullname", "l": "نام کامل", "required": True}],
    }
    created = client.post("/api/forms", json=payload, headers={**owner_write_headers(client), "Idempotency-Key": key})
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    published = client.post(f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=owner_write_headers(client))
    assert published.status_code == 200, published.text
    return form_id


def reminder_rows(engine, *, event_id: str | None = None) -> list[UserNotificationRecord]:
    with Session(engine) as db:
        rows = list(db.scalars(
            select(UserNotificationRecord).where(UserNotificationRecord.kind == reminders_mod.KIND)
            .order_by(UserNotificationRecord.created_at, UserNotificationRecord.id)
        ).all())
        if event_id:
            rows = [row for row in rows if (row.dedupe_key or "").startswith(reminders_mod.key_prefix(event_id))]
        for row in rows:
            db.expunge(row)
        return rows


def run(engine, now: datetime) -> dict:
    with Session(engine) as db:
        return scheduled_publish_mod.announce_due(db, now, actor="test")


def test_reminders_slots_recipients_idempotency_time_change_and_cancellation():
    app, engine = gate_app()
    owner = TestClient(app)
    try:
        owner_login(owner)
        base = datetime.now(timezone.utc).replace(microsecond=0)
        start_a = base + timedelta(days=5)
        start_b = base + timedelta(days=5, hours=2)
        # A: both slots on, cap 2 → third registrant waitlisted. B: other event, both on. C: reminders off.
        event_a, version = create_published_event(
            owner, 0, t="کارگاه یادآور", startsAt=event_time.to_iso(start_a), place="سالن یک", reminders={"h24": True, "h1": True},
        )
        event_b, version = create_published_event(owner, version, t="رویداد دیگر", startsAt=event_time.to_iso(start_b), reminders={"h24": True, "h1": True})
        event_c, version = create_published_event(owner, version, t="بدون یادآور", startsAt=event_time.to_iso(start_a))
        detail = owner.get(f"/api/admin/content/events/{event_a}").json()
        assert detail["record"]["reminders"] == {"h24": True, "h1": True}
        assert [slot["state"] for slot in detail["reminders"]["slots"]] == ["scheduled", "scheduled"]
        assert detail["reminders"]["channels"] == ["in_app", "bale"]
        assert owner.get(f"/api/admin/content/events/{event_c}").json()["record"]["reminders"] == {"h24": False, "h1": False}
        form_a = publish_form(owner, event_id=event_a, key="reminder-form-a-000000001", cap=2, wait=5)
        form_b = publish_form(owner, event_id=event_b, key="reminder-form-b-000000001")
        publish_form(owner, event_id=event_c, key="reminder-form-c-000000001")

        members = {}
        for marker, bale_id in (("m1", M1), ("m2", M2), ("m3", M3), ("m4", M4)):
            client = TestClient(app)
            members[marker] = (client, bale_login(client, bale_id))
        register(members["m1"][0], form_a, "عضو یک")
        register(members["m2"][0], form_a, "عضو دو")
        register(members["m3"][0], form_b, "عضو سه")
        # m4 → waitlisted on A (cap 2): the only non-accepted status form_responses can hold.
        assert members["m4"][0].get(f"/api/public/forms/{form_a}/draft").status_code == 200
        waitlisted = members["m4"][0].post(f"/api/public/forms/{form_a}/responses", json={"answers": {"full-name": "عضو چهار"}}, headers=ORIGIN)
        assert waitlisted.status_code == 200 and waitlisted.json()["status"] == "waitlisted", waitlisted.text

        # Too early: nothing.
        summary = run(engine, start_a - timedelta(hours=25))
        assert summary["ok"] is True and summary["reminders"]["queued"] == 0
        assert reminder_rows(engine) == []

        # 24h window open for A (not yet for B, which starts 2h later): only m1 + m2, only event A.
        summary = run(engine, start_a - timedelta(hours=23, minutes=30))
        assert summary["reminders"]["ok"] is True and summary["reminders"]["queued"] == 2 and summary["reminders"]["existing"] == 0
        rows = reminder_rows(engine)
        assert sorted(row.account_id for row in rows) == sorted([members["m1"][1], members["m2"][1]])
        assert all(row.dedupe_key.startswith(f"event_reminder:{event_a}:h24:") for row in rows)
        assert all(row.delivery_status == "pending" and row.bale_user_id for row in rows)
        assert all("کارگاه یادآور" in row.title and "فردا" in row.body and "سالن یک" in row.body for row in rows)
        assert all(event_time.to_local_input(event_time.to_iso(start_a)) in row.body for row in rows)
        assert all(row.link == f"/event.html?id={event_a}" for row in rows)

        # Restart / second runner / manual run in the same window: nothing new.
        again = run(engine, start_a - timedelta(hours=23, minutes=10))  # still before B's 24h window
        assert again["reminders"]["queued"] == 0 and again["reminders"]["existing"] == 2
        assert len(reminder_rows(engine)) == 2

        # B's own 24h window: only m3, only event B; A gets nothing extra.
        run(engine, start_b - timedelta(hours=23))
        b_rows = reminder_rows(engine, event_id=event_b)
        assert [row.account_id for row in b_rows] == [members["m3"][1]]
        assert len(reminder_rows(engine, event_id=event_a)) == 2

        # 1h slot for A: two new rows; 24h rows untouched; event C never appears.
        summary = run(engine, start_a - timedelta(minutes=30))
        assert summary["reminders"]["queued"] == 2
        a_rows = reminder_rows(engine, event_id=event_a)
        assert len(a_rows) == 4 and sum(":h1:" in row.dedupe_key for row in a_rows) == 2
        assert all("تا یک ساعت دیگر" in row.body for row in a_rows if ":h1:" in row.dedupe_key)
        assert reminder_rows(engine, event_id=event_c) == []
        # After the start nothing fires.
        assert run(engine, start_a + timedelta(minutes=5))["reminders"]["queued"] == 0
        preview = owner.get(f"/api/admin/content/events/{event_a}").json()["reminders"]
        assert [slot["queued"] for slot in preview["slots"]] == [2, 2]

        # Start time moves: pending rows of the old time are withdrawn (outbox shows why, bot never
        # sends them), the old window yields nothing, the new window yields fresh rows exactly once.
        new_start = base + timedelta(days=12)
        version = update_event(owner, event_a, version, startsAt=event_time.to_iso(new_start))
        moved = run(engine, start_a - timedelta(minutes=20))
        assert moved["reminders"]["queued"] == 0 and moved["reminders"]["withdrawn"] == 4
        old_rows = reminder_rows(engine, event_id=event_a)
        assert all(row.delivery_status == "failed" and row.last_delivery_error == reminders_mod.STALE_ERROR for row in old_rows)
        # The member's in-app row is kept but no longer promises the old time.
        assert all(row.body.startswith(reminders_mod.STALE_BODY_HEAD) for row in old_rows)
        assert members["m1"][0].get("/api/account/notifications").json()["items"][0]["body"].startswith(reminders_mod.STALE_BODY_HEAD)
        bot_pending = {item["id"] for item in owner.get("/api/bot/notifications/pending", headers=service_headers()).json()["items"]}
        assert bot_pending.isdisjoint({row.id for row in old_rows})  # withdrawn rows never reach the bot
        retry = owner.post(f"/api/admin/notifications/{old_rows[0].id}/retry", headers=owner_write_headers(owner))
        assert retry.status_code == 409 and retry.json()["detail"]["code"] == "reminder_superseded"
        summary = run(engine, new_start - timedelta(hours=23))
        assert summary["reminders"]["queued"] == 2 and summary["reminders"]["withdrawn"] == 0
        a_rows = reminder_rows(engine, event_id=event_a)
        fresh = [row for row in a_rows if row.delivery_status == "pending"]
        assert len(a_rows) == 6 and len(fresh) == 2
        assert all(event_time.to_local_input(event_time.to_iso(new_start)) in row.body for row in fresh)
        assert run(engine, new_start - timedelta(hours=22))["reminders"]["queued"] == 0
        preview = owner.get(f"/api/admin/content/events/{event_a}").json()["reminders"]
        assert preview["slots"][0]["queued"] == 2 and preview["slots"][0]["superseded"] == 2 and preview["slots"][1]["superseded"] == 2

        # Cancelled event: pending 24h row of B is withdrawn and no 1h reminder is ever queued.
        version = update_event(owner, event_b, version, lifecycle="cancelled")
        cancelled = run(engine, start_b - timedelta(minutes=30))
        assert cancelled["reminders"]["queued"] == 0 and cancelled["reminders"]["withdrawn"] == 1
        b_rows = reminder_rows(engine, event_id=event_b)
        assert len(b_rows) == 1 and b_rows[0].delivery_status == "failed" and b_rows[0].last_delivery_error == reminders_mod.STALE_ERROR
        preview = owner.get(f"/api/admin/content/events/{event_b}").json()["reminders"]
        assert [slot["state"] for slot in preview["slots"]] == ["inactive", "inactive"]

        # Switch a slot on independently: only that one fires.
        start_d = base + timedelta(days=20)
        event_d, version = create_published_event(owner, version, t="فقط یک ساعت", startsAt=event_time.to_iso(start_d), reminders={"h1": True})
        form_d = publish_form(owner, event_id=event_d, key="reminder-form-d-000000001")
        register(members["m2"][0], form_d, "عضو دو")
        assert run(engine, start_d - timedelta(hours=23))["reminders"]["queued"] == 0
        assert run(engine, start_d - timedelta(minutes=50))["reminders"]["queued"] == 1

        # Scheduler marker carries the reminder counters (panel/monitoring) and the state route exposes it.
        with Session(engine) as db:
            marker = db.get(SystemMarkerRecord, scheduled_publish_mod.MARKER_KEY)
            assert marker is not None and marker.value["reminders"]["ok"] is True and "queued" in marker.value["reminders"]
        state = owner.get("/api/admin/scheduled-publish").json()
        assert state["last_run"]["reminders"]["queued"] == 1
    finally:
        engine.dispose()


def test_in_app_row_survives_bale_failure_and_outbox_visibility_follows_permissions():
    app, engine = gate_app()
    owner = TestClient(app)
    try:
        owner_login(owner)
        base = datetime.now(timezone.utc).replace(microsecond=0)
        start = base + timedelta(days=3)
        event_id, version = create_published_event(owner, 0, t="رویداد با خطای بله", startsAt=event_time.to_iso(start), reminders={"h24": True})
        form_id = publish_form(owner, event_id=event_id, key="reminder-form-f-000000001")
        member = TestClient(app)
        bale_login(member, M1)
        register(member, form_id, "عضو یک")
        other = TestClient(app)
        bale_login(other, M2)
        run(engine, start - timedelta(hours=23))
        rows = reminder_rows(engine, event_id=event_id)
        assert len(rows) == 1
        notification_id = rows[0].id

        # The bot's pending list carries it (Bale path); the in-app list shows it immediately
        # (queued ≠ delivered); the other member sees nothing.
        pending = owner.get("/api/bot/notifications/pending", headers=service_headers())
        assert pending.status_code == 200 and notification_id in {item["id"] for item in pending.json()["items"]}
        mine = member.get("/api/account/notifications").json()["items"]
        assert [item["kind"] for item in mine] == [reminders_mod.KIND]
        assert mine[0]["title"].startswith("یادآوری رویداد")
        assert other.get("/api/account/notifications").json()["items"] == []

        # Bale delivery keeps failing: existing retry policy (5 attempts → failed); in-app row stays.
        for _attempt in range(5):
            failed = owner.post(f"/api/bot/notifications/{notification_id}/delivery-failed", json={"bale_user_id": str(M1)}, headers=service_headers())
            assert failed.status_code == 200, failed.text
        assert failed.json()["delivery_status"] == "failed"
        mine = member.get("/api/account/notifications").json()["items"]
        assert len(mine) == 1 and mine[0]["id"] == notification_id
        # Re-running the scheduler neither duplicates nor resurrects the delivery state.
        run(engine, start - timedelta(hours=22))
        assert len(reminder_rows(engine, event_id=event_id)) == 1
        with Session(engine) as db:
            assert db.get(UserNotificationRecord, notification_id).delivery_status == "failed"

        # Outbox: owner sees both paths' state (audience scope + Bale failure), manager with rp_view too, members never.
        outbox = owner.get(f"/api/admin/notifications?kind={reminders_mod.KIND}&limit=20")
        assert outbox.status_code == 200, outbox.text
        items = outbox.json()["items"]
        assert [item["id"] for item in items] == [notification_id]
        assert items[0]["delivery_status"] == "failed" and items[0]["dedupe_key"].startswith(reminders_mod.key_prefix(event_id))
        assert items[0]["has_bale_identity"] is True and "bale_user_id" not in items[0]
        # U5 per-account view classifies reminders as audience fan-out (same as publish announcements).
        per_account = owner.get(f"/api/admin/users/{rows[0].account_id}/notifications").json()["items"]
        assert [item["scope"] for item in per_account] == ["audience"]
        assert items[0]["last_delivery_error"] == "provider_delivery_failed"
        preview = owner.get(f"/api/admin/content/events/{event_id}").json()["reminders"]
        assert preview["slots"][0]["delivery"] == {"pending": 0, "delivered": 0, "failed": 1}
        # The existing manual retry re-queues the very same row (Bale path), never a second one.
        retry = owner.post(f"/api/admin/notifications/{notification_id}/retry", headers=owner_write_headers(owner))
        assert retry.status_code == 200, retry.text
        assert len(reminder_rows(engine, event_id=event_id)) == 1 and len(member.get("/api/account/notifications").json()["items"]) == 1
        manager = TestClient(app)
        manager_id = bale_login(manager, M3)
        assign_manager(manager, manager_id)
        as_manager = manager.get(f"/api/admin/notifications?kind={reminders_mod.KIND}&limit=20")
        assert as_manager.status_code == 200 and [item["id"] for item in as_manager.json()["items"]] == [notification_id]
        assert member.get(f"/api/admin/notifications?kind={reminders_mod.KIND}").status_code in {401, 403}
        assert TestClient(app).get(f"/api/admin/notifications?kind={reminders_mod.KIND}").status_code == 401
    finally:
        engine.dispose()


def test_reminder_settings_are_validated_and_default_off():
    app, engine = gate_app()
    owner = TestClient(app)
    try:
        owner_login(owner)
        bad = owner.post(
            "/api/admin/content/events",
            json={"record": {**event_payload(startsAt=None), "reminders": {"h24": "maybe"}}, "expected_version": 0},
            headers=owner_write_headers(owner),
        )
        assert bad.status_code == 422 and bad.json()["detail"]["field"] == "reminders", bad.text
        unknown = owner.post(
            "/api/admin/content/events",
            json={"record": {**event_payload(startsAt=None), "reminders": {"sms": True}}, "expected_version": 0},
            headers=owner_write_headers(owner),
        )
        assert unknown.status_code == 422, unknown.text
        created = owner.post(
            "/api/admin/content/events",
            json={"record": event_payload(startsAt=None), "expected_version": 0},
            headers=owner_write_headers(owner),
        )
        assert created.status_code == 200, created.text
        assert created.json()["record"]["reminders"] == {"h24": False, "h1": False}
        assert [slot["state"] for slot in created.json()["reminders"]["slots"]] == ["off", "off"]
        # Switch on without a start time: honest "needs_start_time", never due.
        edited = owner.put(
            f"/api/admin/content/events/{created.json()['record']['id']}",
            json={"record": {"reminders": {"h24": True, "h1": False}}, "expected_version": created.json()["version"]},
            headers=owner_write_headers(owner),
        )
        assert edited.status_code == 200, edited.text
        assert [slot["state"] for slot in edited.json()["reminders"]["slots"]] == ["needs_start_time", "off"]
        assert reminders_mod.due_slots(edited.json()["record"], datetime.now(timezone.utc)) == []
        # Legacy rows without the key are read as both-off (safe default for existing events).
        assert reminders_mod.settings_of({"id": "legacy", "t": "x"}) == {"h24": False, "h1": False}
    finally:
        engine.dispose()
