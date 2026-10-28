"""Phase 9.5 §8.2 — scheduled publish is explicit, idempotent and monitored; §8 outbox retry.

Proved here:
* a resource published with a future ``publish_at`` is not visible and not announced (unchanged);
* ``scheduled_publish.announce_due`` announces it exactly once when the time comes (timer / manual
  run / repeated runs / restart all converge), sets ``announced_at`` and writes the
  ``scheduled_publish`` marker; an immediately published resource is announced by the publish
  route and the scheduler never duplicates it (dedupe key + ``announced_at``);
* back to draft resets ``announced_at``; event-level or unpublished-product rows are skipped, not
  announced;
* admin routes: ``GET /api/admin/scheduled-publish`` (rp_view) and ``POST …/run`` (ev_publish,
  audited); guest 401 / plain member 403;
* ``POST /api/admin/notifications/{id}/retry``: failed → pending on the *same* row, delivered and
  pending rows refused, ``no_bale_identity`` refused unless the account linked Bale since; audited;
* the CLI ``python -m backend.scheduled_publish --once`` runs the same function against the
  configured database.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT.parent))

from backend import scheduled_publish  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import (  # noqa: E402
    AdminAuditEventRecord, Base, EventResourceRecord, RecordingAccessRecord, SystemMarkerRecord, UserNotificationRecord,
)
from backend.security import hash_password  # noqa: E402
from test_event_registration_gate import gate_app  # noqa: E402
from test_recordings_api import build_sellable_product, held_event, notifications, purchase_form, set_status  # noqa: E402
from test_workflows_api import BOT_TOKEN, SERVICE_TOKEN, bale_login, owner_login, owner_write_headers  # noqa: E402

FUTURE = "2099-01-01T10:00:00+00:00"
AFTER = datetime(2099, 1, 1, 10, 0, 1, tzinfo=timezone.utc)


def content_rows(engine, account_id: str) -> list[UserNotificationRecord]:
    return [n for n in notifications(engine, account_id) if n.kind == "recording_content"]


def resource(engine, resource_id: str) -> EventResourceRecord:
    with Session(engine) as db:
        row = db.get(EventResourceRecord, resource_id)
        assert row is not None
        db.expunge(row)
        return row


def audit(engine, action: str) -> list[AdminAuditEventRecord]:
    with Session(engine) as db:
        rows = list(db.scalars(select(AdminAuditEventRecord).where(AdminAuditEventRecord.action == action).order_by(AdminAuditEventRecord.created_at)))
        for row in rows:
            db.expunge(row)
        return rows


def setup_product(owner: TestClient, app) -> tuple[str, str, str, TestClient]:
    event_id, _v = held_event(owner, 0)
    product = build_sellable_product(owner, event_id, price=0, payment_card=None)
    assert set_status(owner, event_id, "ready").status_code == 200
    assert set_status(owner, event_id, "published").status_code == 200
    holder = TestClient(app)
    holder_id = bale_login(holder, 97301)
    grant = owner.post(f"/api/admin/events/{event_id}/recording/access", json={"account_id": holder_id, "reason": "اعطای آزمون"},
                       headers=owner_write_headers(owner))
    assert grant.status_code == 201, grant.text
    return event_id, product["_session_id"], holder_id, holder


def test_scheduled_resource_is_announced_exactly_once_when_due_and_the_run_is_monitored():
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_id, session_id, holder_id, holder = setup_product(owner, app)
            h = owner_write_headers(owner)
            base = f"/api/admin/events/{event_id}/resources"
            before = len(content_rows(engine, holder_id))

            created = owner.post(base, json={"title": "جزوهٔ زمان‌بندی‌شده", "access": "purchased", "session_id": session_id,
                                             "kind": "link", "link_url": "https://example.org/notes"}, headers=h)
            assert created.status_code == 201, created.text
            rid = created.json()["id"]
            scheduled = owner.put(f"{base}/{rid}", json={"status": "published", "publish_at": FUTURE}, headers=h)
            assert scheduled.status_code == 200, scheduled.text
            # Not visible to the holder, not announced, audit says "scheduled".
            public = holder.get(f"/api/public/events/{event_id}/recording").json()["recording"]
            assert rid not in {r["id"] for s in public["sessions"] for r in s["resources"]}
            assert len(content_rows(engine, holder_id)) == before
            assert resource(engine, rid).announced_at is None
            assert audit(engine, "event_resource.update")[-1].details.get("scheduled_announcement") is True

            # State endpoint: one future row, nothing due, no run yet.
            state = owner.get("/api/admin/scheduled-publish")
            assert state.status_code == 200 and state.json()["last_run"] is None
            assert state.json()["pending"] == {"future": 1, "due_unannounced": 0}

            # Timer before the time: nothing to do, but the marker proves the run happened.
            with Session(engine) as db:
                early = scheduled_publish.announce_due(db, datetime.now(timezone.utc), actor="timer")
            assert early["ok"] and early["due"] == 0 and early["announced"] == 0
            assert len(content_rows(engine, holder_id)) == before
            with Session(engine) as db:
                marker = db.get(SystemMarkerRecord, "scheduled_publish")
                assert marker is not None and marker.value["actor"] == "timer" and marker.value["due"] == 0

            # The time has come: exactly one announcement for the active holder; repeated runs add nothing.
            with Session(engine) as db:
                due = scheduled_publish.announce_due(db, AFTER, actor="timer")
            assert due == {**due, "ok": True, "due": 1, "announced": 1, "notified": 1, "skipped": 0}
            rows = content_rows(engine, holder_id)
            assert len(rows) == before + 1 and "جزوهٔ زمان‌بندی‌شده" in rows[-1].body
            assert rows[-1].dedupe_key == f"recording_content:resource:{rid}:{holder_id}"
            assert resource(engine, rid).announced_at is not None
            for _ in range(2):  # restart / overlapping timer / manual run
                with Session(engine) as db:
                    again = scheduled_publish.announce_due(db, AFTER + timedelta(hours=1), actor="timer")
                assert again["due"] == 0 and again["announced"] == 0
            assert len(content_rows(engine, holder_id)) == before + 1

            # Immediate publish is announced by the route and marked; the scheduler never re-announces it.
            live = owner.post(base, json={"title": "فایل فوری", "access": "purchased", "session_id": session_id,
                                          "kind": "link", "link_url": "https://example.org/now"}, headers=h)
            live_id = live.json()["id"]
            assert owner.put(f"{base}/{live_id}", json={"status": "published"}, headers=h).status_code == 200
            assert len(content_rows(engine, holder_id)) == before + 2 and resource(engine, live_id).announced_at is not None
            with Session(engine) as db:
                assert scheduled_publish.announce_due(db, AFTER)["due"] == 0
            assert len(content_rows(engine, holder_id)) == before + 2

            # Back to draft resets the flag; re-publishing live hits the dedupe key → still no duplicate.
            assert owner.put(f"{base}/{live_id}", json={"status": "draft"}, headers=h).status_code == 200
            assert resource(engine, live_id).announced_at is None
            assert owner.put(f"{base}/{live_id}", json={"status": "published"}, headers=h).status_code == 200
            assert len(content_rows(engine, holder_id)) == before + 2

            # Event-level scheduled row (no product holders) is skipped, never announced, and not rescanned.
            general = owner.post(base, json={"title": "گزارش عمومی", "access": "registered", "kind": "link",
                                             "link_url": "https://example.org/report", "status": "published", "publish_at": FUTURE}, headers=h)
            assert general.status_code == 201, general.text
            with Session(engine) as db:
                run = scheduled_publish.announce_due(db, AFTER)
            assert run["due"] == 1 and run["skipped"] == 1 and run["announced"] == 0
            assert len(content_rows(engine, holder_id)) == before + 2
            assert resource(engine, general.json()["id"]).announced_at is not None

            # Manual run from the panel: same function, audited, state shows the run.
            manual = owner.post("/api/admin/scheduled-publish/run", headers=h)
            assert manual.status_code == 200 and manual.json()["ok"] is True and manual.json()["due"] == 0
            assert manual.json()["actor"].startswith("owner:")
            assert audit(engine, "scheduled_publish.run")[-1].details["due"] == 0
            state = owner.get("/api/admin/scheduled-publish").json()
            assert state["last_run"]["actor"].startswith("owner:") and state["pending"] == {"future": 0, "due_unannounced": 0}

            # Authorization: guest 401, plain member 403 on both routes.
            guest = TestClient(app)
            assert guest.get("/api/admin/scheduled-publish").status_code == 401
            assert guest.post("/api/admin/scheduled-publish/run").status_code in (401, 403)
            assert holder.get("/api/admin/scheduled-publish").status_code == 403
            assert holder.post("/api/admin/scheduled-publish/run", headers={"X-CSRF-Token": "x"}).status_code == 403
    finally:
        engine.dispose()


def test_failed_notification_retry_requeues_the_same_row_only():
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_id, session_id, holder_id, holder = setup_product(owner, app)
            h = owner_write_headers(owner)
            rows = notifications(engine, holder_id)
            assert rows, "the access grant queues one outbox row for the holder"
            note_id = rows[0].id
            total_before = len(notifications(engine, holder_id))

            # pending → refused; delivered → refused.
            pending = owner.post(f"/api/admin/notifications/{note_id}/retry", headers=h)
            assert pending.status_code == 409 and pending.json()["detail"]["code"] == "notification_not_failed"
            with Session(engine) as db:
                row = db.get(UserNotificationRecord, note_id)
                row.delivery_status = "delivered"
                db.commit()
            delivered = owner.post(f"/api/admin/notifications/{note_id}/retry", headers=h)
            assert delivered.status_code == 409 and delivered.json()["detail"]["code"] == "already_delivered"

            # failed after provider errors → pending again, attempts reset, same id, no new row; audited.
            with Session(engine) as db:
                row = db.get(UserNotificationRecord, note_id)
                row.delivery_status, row.delivery_attempts, row.last_delivery_error = "failed", 5, "provider_delivery_failed"
                db.commit()
            retried = owner.post(f"/api/admin/notifications/{note_id}/retry", headers=h)
            assert retried.status_code == 200, retried.text
            body = retried.json()
            assert body["id"] == note_id and body["delivery_status"] == "pending" and body["delivery_attempts"] == 0
            assert body["delivery_state"] == "queued" and "bale_user_id" not in body
            assert len(notifications(engine, holder_id)) == total_before
            entry = audit(engine, "notification.retry")[-1]
            assert entry.target_id == note_id and entry.details["previous_attempts"] == 5 and entry.details["previous_error"] == "provider_delivery_failed"
            # The bot sees it in the pending drain again.
            drained = owner.get("/api/bot/notifications/pending", headers={"Authorization": f"Bearer {SERVICE_TOKEN}"})
            assert drained.status_code == 200 and note_id in {item["id"] for item in drained.json()["items"]}

            # Web-only account: no_bale_identity row cannot be retried (honest 409, no network).
            with Session(engine) as db:
                web_only = UserNotificationRecord(
                    id="11111111-2222-4333-8444-555555555555", account_id=holder_id, bale_user_id="", kind="recording_content",
                    title="t", body="b", dedupe_key="test:web-only", delivery_status="failed", delivery_attempts=0,
                    last_delivery_error="no_bale_identity",
                )
                db.add(web_only)
                db.commit()
                from backend.models import PlatformIdentityRecord
                db.query(PlatformIdentityRecord).filter(PlatformIdentityRecord.account_id == holder_id).delete()
                db.commit()
            refused = owner.post("/api/admin/notifications/11111111-2222-4333-8444-555555555555/retry", headers=h)
            assert refused.status_code == 409 and refused.json()["detail"]["code"] == "no_bale_identity"
            assert owner.post("/api/admin/notifications/not-a-uuid/retry", headers=h).status_code == 404
            assert holder.post(f"/api/admin/notifications/{note_id}/retry", headers={"X-CSRF-Token": "x"}).status_code in (401, 403)
    finally:
        engine.dispose()


def test_cli_once_runs_the_same_pass_against_the_configured_database(tmp_path, monkeypatch, capsys):
    db_url = f"sqlite+pysqlite:///{tmp_path / 'nora.db'}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None, owner_id="owner-01", owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"), cookie_secure=False,
        bale_bot_token=BOT_TOKEN, bot_service_token=SERVICE_TOKEN, owner_bale_user_id="70001",
    )
    app = create_app(settings, engine=engine)
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_id, session_id, holder_id, _holder = setup_product(owner, app)
            h = owner_write_headers(owner)
            created = owner.post(f"/api/admin/events/{event_id}/resources",
                                 json={"title": "جزوهٔ تایمر", "access": "purchased", "session_id": session_id, "kind": "link",
                                       "link_url": "https://example.org/timer", "status": "published",
                                       "publish_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}, headers=h)
            assert created.status_code == 201, created.text
            # Created directly as published with a past publish_at: the create route does not announce
            # (only transitions do) → this is exactly the row the timer must pick up.
            before = len(content_rows(engine, holder_id))
            monkeypatch.setenv("NORA_DATABASE_URL", db_url)
            assert scheduled_publish.main(["--once", "--json"]) == 0
            out = capsys.readouterr().out
            assert '"announced": 1' in out and '"actor": "cli"' in out
            assert len(content_rows(engine, holder_id)) == before + 1
            assert scheduled_publish.main(["--once"]) == 0
            assert "announced=0" in capsys.readouterr().out
            assert len(content_rows(engine, holder_id)) == before + 1
            monkeypatch.delenv("NORA_DATABASE_URL")
            try:
                scheduled_publish.main(["--once"])
            except SystemExit as stop:
                assert "NORA_DATABASE_URL" in str(stop)
            else:  # pragma: no cover
                raise AssertionError("missing database url must fail loudly")
    finally:
        engine.dispose()


def test_checked_in_attendees_of_a_courtesy_product_are_announced_once_without_an_access_row():
    """§8.2 gap closed in 9.5: attendee access is *derived* (no ``recording_access`` row), so the content
    announcement must reach checked-in attendees too — once, and never the registrant who was absent."""
    from test_event_registration_gate import ORIGIN, create_published_event, create_published_form, iso, update_event  # noqa: PLC0415

    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_id, version = create_published_event(owner, 0, t="کارگاه حضوری با آرشیو حاضران", startsAt=iso(timedelta(days=3)))
            registration_form = create_published_form(owner, event_id=event_id, key="sched-attendee-reg-0001")
            attendee, absent = TestClient(app), TestClient(app)
            attendee_id, absent_id = bale_login(attendee, 97401), bale_login(absent, 97402)
            for client, name in ((attendee, "حاضر واقعی"), (absent, "ثبت‌نامی غایب")):
                assert client.get(f"/api/public/forms/{registration_form}/draft").status_code == 200
                assert client.post(f"/api/public/forms/{registration_form}/responses",
                                   json={"answers": {"full-name": name}}, headers=ORIGIN).status_code == 200
            response_id = attendee.get("/api/account/registrations").json()["items"][0]["id"]
            assert owner.post(f"/api/admin/attendance/responses/{response_id}/check-in", json={},
                              headers=owner_write_headers(owner)).status_code == 200
            version = update_event(owner, event_id, version, startsAt=iso(timedelta(days=-9)), endsAt=iso(timedelta(days=-8)),
                                   regClosesAt=iso(timedelta(days=-10)), past=True)
            product = build_sellable_product(owner, event_id, price=900_000, payment_card=None, attendee_access=True)
            purchase_form(owner, product["recording"]["id"], price=900_000)  # paid product publishes only with its form
            assert set_status(owner, event_id, "ready").status_code == 200
            assert set_status(owner, event_id, "published").status_code == 200
            with Session(engine) as db:
                assert db.scalar(select(RecordingAccessRecord).where(RecordingAccessRecord.account_id == attendee_id)) is None

            h = owner_write_headers(owner)
            base = f"/api/admin/events/{event_id}/resources"
            created = owner.post(base, json={"title": "اسلایدهای حاضران", "access": "attended", "session_id": product["_session_id"],
                                             "kind": "link", "link_url": "https://example.org/slides"}, headers=h)
            assert created.status_code == 201, created.text
            rid = created.json()["id"]
            assert owner.put(f"{base}/{rid}", json={"status": "published", "publish_at": FUTURE}, headers=h).status_code == 200
            assert content_rows(engine, attendee_id) == [] and content_rows(engine, absent_id) == []

            later = datetime(2099, 1, 1, 10, 0, 1, tzinfo=timezone.utc)
            with Session(engine) as db:
                first = scheduled_publish.announce_due(db, later, actor="test")
                second = scheduled_publish.announce_due(db, later, actor="test")
            assert (first["due"], first["announced"], first["notified"]) == (1, 1, 1), first
            assert (second["due"], second["announced"], second["notified"]) == (0, 0, 0), second
            mine = content_rows(engine, attendee_id)
            assert len(mine) == 1 and "آرشیو حاضران" in mine[0].title and mine[0].dedupe_key == f"recording_content:resource:{rid}:{attendee_id}"
            assert content_rows(engine, absent_id) == [], "registration without check-in is not an entitlement"
            # Visibility always follows the real server clock: still hidden while publish_at is in the future.
            assert rid not in {r["id"] for s in attendee.get(f"/api/public/events/{event_id}/recording").json()["recording"]["sessions"] for r in s["resources"]}
            # Owner moves the time back → live now; the attendee really sees it (derived access), the absent
            # registrant does not, and the already-announced row is not duplicated by the immediate-publish path.
            assert owner.put(f"{base}/{rid}", json={"publish_at": iso(timedelta(minutes=-1))}, headers=h).status_code == 200
            assert len(content_rows(engine, attendee_id)) == 1
            seen = attendee.get(f"/api/public/events/{event_id}/recording").json()["recording"]
            assert rid in {r["id"] for s in seen["sessions"] for r in s["resources"]}
            other = absent.get(f"/api/public/events/{event_id}/recording").json()["recording"]
            assert other["viewer"]["cta"]["kind"] == "buy", "registered-but-absent member has no derived access"
            notes = attendee.get("/api/account/notifications?limit=50&offset=0").json()["items"]
            assert [n["kind"] for n in notes].count("recording_content") == 1
    finally:
        app.state.engine.dispose() if hasattr(app.state, "engine") else None


def test_several_due_rows_in_one_pass_are_announced_oldest_first_and_a_far_past_time_is_just_due():
    """Phase 9.6 §7: three rows become due in the same pass (two products, one with a publish_at years in the
    past — a clock jump or a long outage): one run announces all three, oldest first, every holder gets exactly
    one row per resource, and a second pass (double timer run) has nothing left to do."""
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_a, session_a, holder_a_id, holder_a = setup_product(owner, app)
            event_b, _v = held_event(owner, 1, t="کارگاه دوم")
            product_b = build_sellable_product(owner, event_b, price=0, payment_card=None)
            assert set_status(owner, event_b, "ready").status_code == 200 and set_status(owner, event_b, "published").status_code == 200
            holder_b = TestClient(app)
            holder_b_id = bale_login(holder_b, 97302)
            assert owner.post(f"/api/admin/events/{event_b}/recording/access", json={"account_id": holder_b_id, "reason": "اعطای آزمون"},
                              headers=owner_write_headers(owner)).status_code == 201
            h = owner_write_headers(owner)

            def schedule(event_id: str, session_id: str, title: str, publish_at: str) -> str:
                created = owner.post(f"/api/admin/events/{event_id}/resources", json={"title": title, "access": "purchased", "session_id": session_id,
                                                                                      "kind": "link", "link_url": "https://example.org/" + publish_at[:4]}, headers=h)
                assert created.status_code == 201, created.text
                rid = created.json()["id"]
                assert owner.put(f"/api/admin/events/{event_id}/resources/{rid}", json={"status": "published", "publish_at": publish_at}, headers=h).status_code == 200
                return rid

            rid_old = schedule(event_a, session_a, "منبع قدیمی", "2099-01-01T08:00:00+00:00")
            rid_a = schedule(event_a, session_a, "منبع الف", "2099-01-01T09:00:00+00:00")
            rid_b = schedule(event_b, product_b["_session_id"], "منبع ب", "2099-01-01T09:30:00+00:00")
            assert content_rows(engine, holder_a_id) == [] and content_rows(engine, holder_b_id) == []
            # Long outage / clock jump: the first row's time is now years in the past while the timer never ran.
            # (Publishing through the API with a past time is announced immediately by the publish route itself —
            # that path is covered by test_cli_once…; here the row must be picked up by the scheduler.)
            with Session(engine) as db:
                db.get(EventResourceRecord, rid_old).publish_at = datetime(2001, 6, 15, 8, 0, tzinfo=timezone.utc)
                db.commit()
            # The far-past row is visible right away (visibility = server clock), the 2099 rows are not.
            visible = {r["id"] for s in holder_a.get(f"/api/public/events/{event_a}/recording").json()["recording"]["sessions"] for r in s["resources"]}
            assert rid_old in visible and rid_a not in visible
            with Session(engine) as db:
                assert scheduled_publish.pending_count(db, datetime.now(timezone.utc)) == {"future": 2, "due_unannounced": 1}
                assert [r.id for r in scheduled_publish.due_resources(db, AFTER)] == [rid_old, rid_a, rid_b]  # oldest first
                run = scheduled_publish.announce_due(db, AFTER, actor="timer")
                again = scheduled_publish.announce_due(db, AFTER + timedelta(minutes=5), actor="timer")
                assert scheduled_publish.pending_count(db, AFTER) == {"future": 0, "due_unannounced": 0}
            assert run["ok"] is True and (run["due"], run["announced"], run["notified"], run["skipped"], run["errors"]) == (3, 3, 3, 0, 0), run
            assert (again["due"], again["announced"], again["notified"]) == (0, 0, 0), again
            mine_a = content_rows(engine, holder_a_id)
            assert sorted(n.dedupe_key for n in mine_a) == sorted(f"recording_content:resource:{rid}:{holder_a_id}" for rid in (rid_old, rid_a))
            mine_b = content_rows(engine, holder_b_id)
            assert [n.dedupe_key for n in mine_b] == [f"recording_content:resource:{rid_b}:{holder_b_id}"]
            for rid in (rid_old, rid_a, rid_b):
                assert resource(engine, rid).announced_at is not None
            # The marker of the last pass is what the panel and the CLI report; the UTC instant is explicit.
            state = owner.get("/api/admin/scheduled-publish").json()
            assert state["last_run"]["due"] == 0 and state["last_run"]["at"] == "2099-01-01T10:05:01Z" and state["last_run"]["actor"] == "timer"
    finally:
        engine.dispose()
