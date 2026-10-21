"""Phase 7: shared event time/registration state, server-side registration gate and
event-linked banners.

In-memory SQLite only. Covers: Jalali/Tehran input → UTC storage → panel fill-back,
registration state priority, the same state in the public snapshot and in every
public form entry point (GET form, draft, responses, /form.html, bot listing),
banner/event linking with server-clock windows, and backend permission checks.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend import event_time  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import Base  # noqa: E402
from backend.security import hash_password  # noqa: E402

from test_workflows_api import (  # noqa: E402
    BOT_TOKEN,
    SERVICE_TOKEN,
    account_write_headers,
    assign_manager,
    bale_login,
    owner_login,
    owner_write_headers,
)

ORIGIN = {"Origin": "http://testserver"}


def gate_app():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"),
        cookie_secure=False,
        bale_bot_token=BOT_TOKEN,
        bot_service_token=SERVICE_TOKEN,
        owner_bale_user_id="70001",
    )
    return create_app(settings, engine=engine), engine


def iso(delta: timedelta) -> str:
    return event_time.to_iso(datetime.now(timezone.utc) + delta)


def event_payload(**overrides) -> dict:
    base = {
        "t": "کارگاه آزمایشی فاز ۷",
        "kind": "کارگاه",
        "d": "رویداد آزمایشی برای دروازهٔ ثبت‌نام.",
        "on": "۱۴۰۵/۰۸/۱۲",
        "time": "۱۰ تا ۱۳",
        "place": "سالن اصلی",
        "mode": "حضوری",
        "startsAt": iso(timedelta(days=20)),
        "regClosesAt": iso(timedelta(days=10)),
    }
    base.update(overrides)
    return base


def create_published_event(client: TestClient, version: int, **overrides) -> tuple[str, int]:
    created = client.post(
        "/api/admin/content/events",
        json={"record": event_payload(**overrides), "expected_version": version, "status": "published"},
        headers=owner_write_headers(client),
    )
    assert created.status_code == 200, created.text
    return created.json()["record"]["id"], created.json()["version"]


def update_event(client: TestClient, event_id: str, version: int, **fields) -> int:
    edited = client.put(
        f"/api/admin/content/events/{event_id}",
        json={"record": fields, "expected_version": version},
        headers=owner_write_headers(client),
    )
    assert edited.status_code == 200, edited.text
    return edited.json()["version"]


def create_published_form(client: TestClient, *, event_id: str | None, key: str) -> str:
    payload = {
        "name": "فرم ثبت‌نام آزمایشی",
        "model": "registration",
        "need": "reg",
        "settings": {},
        "fields": [{"id": "full-name", "t": "fullname", "l": "نام کامل", "required": True}],
    }
    if event_id:
        payload["ev"] = event_id
    created = client.post(
        "/api/forms", json=payload, headers={**owner_write_headers(client), "Idempotency-Key": key},
    )
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    published = client.post(
        f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=owner_write_headers(client),
    )
    assert published.status_code == 200, published.text
    return form_id


def public_event(client: TestClient, event_id: str) -> dict:
    snapshot = client.get("/api/public/site-content")
    assert snapshot.status_code == 200, snapshot.text
    body = snapshot.json()
    assert event_time.parse_utc(body["server_time"]) is not None
    rows = [row for row in body["content"]["events"] if row["id"] == event_id]
    assert rows, body["content"]["events"]
    return rows[0]


# ── event_time unit rules ──

def test_jalali_tehran_input_is_stored_as_utc_and_filled_back_in_tehran():
    assert event_time.parse_event_datetime("۱۴۰۵/۰۸/۱۲ ۱۰:۰۰") == "2026-11-03T06:30:00Z"
    assert event_time.parse_event_datetime("1405/08/12") == "2026-11-02T20:30:00Z"
    assert event_time.parse_event_datetime("2026-11-03T06:30:00Z") == "2026-11-03T06:30:00Z"
    assert event_time.parse_event_datetime("2026-11-03T10:00:00+03:30") == "2026-11-03T06:30:00Z"
    assert event_time.parse_event_datetime("") == "" and event_time.parse_event_datetime(None) == ""
    assert event_time.to_local_input("2026-11-03T06:30:00Z") == "1405/08/12 10:00"
    for bad in ("2026-11-03T10:00:00", "1405/13/01", "1404/12/30", "1405/08/12 24:00", "فردا"):
        try:
            event_time.parse_event_datetime(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted invalid datetime {bad!r}")
    # 1403 is a leap year (30 Esfand), 1404 is not.
    assert event_time.parse_event_datetime("1403/12/30")
    assert event_time.gregorian_to_jalali(2026, 3, 21) == (1405, 1, 1)


def test_registration_state_priority_and_countdown_targets():
    now = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
    future, past = event_time.to_iso(now + timedelta(days=3)), event_time.to_iso(now - timedelta(days=1))

    def state(**event):
        has_form = event.pop("has_form", True)
        form_full = event.pop("form_full", False)
        return event_time.registration_state(event, now=now, has_form=has_form, form_full=form_full)

    assert state(regClosesAt=future)["state"] == "open"
    assert state(regClosesAt=future)["countdownTo"] == future
    assert state(regClosesAt=past)["state"] == "closed"
    assert state(regClosesAt=past)["countdownTo"] == ""
    assert state(regMode="closed", regClosesAt=future)["state"] == "closed"
    assert state(regMode="full", regClosesAt=future)["state"] == "full"
    assert state(form_full=True, regClosesAt=future)["state"] == "full"
    opens = state(regOpensAt=future, regClosesAt=event_time.to_iso(now + timedelta(days=9)))
    assert opens["state"] == "not_started" and opens["countdownTo"] == future
    assert state(has_form=False, regClosesAt=future)["state"] == "none"
    assert state(has_form=False, regClosesAt=past)["state"] == "closed"  # deadline wins over missing form
    assert state(startsAt=past)["state"] == "closed" and state(startsAt=past)["reason"] == "started"
    assert state(endsAt=past, regClosesAt=future)["state"] == "ended"
    assert state(past=True, regClosesAt=future)["state"] == "ended"
    assert state(lifecycle="cancelled", regClosesAt=future)["state"] == "cancelled"
    postponed = state(lifecycle="postponed", regClosesAt=future)
    assert postponed["state"] == "open" and postponed["reason"] == "postponed"
    # No valid deadline → no countdown target, state still honest.
    plain = state()
    assert plain["state"] == "open" and plain["countdownTo"] == "" and plain["startsIn"] == ""


# ── API: same state everywhere + gate ──

def test_public_snapshot_and_form_entry_points_share_the_registration_state():
    app, _engine = gate_app()
    try:
        with TestClient(app) as client:
            owner_login(client)
            event_id, version = create_published_event(client, 0)
            detail = client.get(f"/api/admin/content/events/{event_id}").json()["record"]
            assert detail["local_times"]["regClosesAt"].startswith("14")
            assert detail["registration"]["state"] == "none"  # published but no form yet

            # Unlinked form must stay untouched by the gate.
            free_form = create_published_form(client, event_id=None, key="phase7-free-form")
            form_id = create_published_form(client, event_id=event_id, key="phase7-event-form")

            event = public_event(client, event_id)
            assert event["registration"]["state"] == "open"
            assert event["registration"]["countdownTo"] == event["regClosesAt"]
            assert event["forms"][0]["id"] == form_id
            assert event["lifecycle"] == "scheduled" and event["regMode"] == "auto"

            visitor = TestClient(app)
            assert visitor.get(f"/api/public/forms/{form_id}").status_code == 200
            assert visitor.get(f"/form.html?fid={form_id}").status_code == 200
            assert "nora-public-error" not in visitor.get(f"/form.html?fid={form_id}").text or \
                '"closed"' not in visitor.get(f"/form.html?fid={form_id}").text
            draft = visitor.get(f"/api/public/forms/{form_id}/draft")
            assert draft.status_code == 200, draft.text

            # Owner moves the deadline into the past → every surface flips, publication unchanged.
            version = update_event(client, event_id, version, regClosesAt=iso(timedelta(minutes=-5)))
            event = public_event(client, event_id)  # still published
            assert event["registration"]["state"] == "closed"
            assert event["registration"]["reason"] == "deadline"
            assert event["registration"]["countdownTo"] == ""

            closed = visitor.get(f"/api/public/forms/{form_id}")
            assert closed.status_code == 409 and closed.json()["detail"]["code"] == "registration_closed"
            assert closed.json()["detail"]["state"] == "closed"
            assert visitor.get(f"/api/public/forms/{form_id}/draft").status_code == 409
            submit = visitor.post(
                f"/api/public/forms/{form_id}/responses",
                json={"answers": {"full-name": "کاربر آزمایشی"}}, headers=ORIGIN,
            )
            assert submit.status_code == 409, submit.text
            assert submit.json()["detail"]["code"] == "registration_closed"
            page = visitor.get(f"/form.html?fid={form_id}")
            assert page.status_code == 200 and '"closed"' in page.text
            bot = client.get("/api/bot/forms/public", headers={"Authorization": f"Bearer {SERVICE_TOKEN}"})
            assert bot.status_code == 200
            listed = {item["id"] for item in bot.json()["items"]}
            assert form_id not in listed and free_form in listed
            assert visitor.get(f"/api/public/forms/{free_form}").status_code == 200

            # Not started yet → blocked too, with the opening time exposed.
            version = update_event(
                client, event_id, version,
                regOpensAt=iso(timedelta(days=1)), regClosesAt=iso(timedelta(days=5)),
            )
            assert public_event(client, event_id)["registration"]["state"] == "not_started"
            pending = visitor.get(f"/api/public/forms/{form_id}")
            assert pending.status_code == 409 and pending.json()["detail"]["state"] == "not_started"
            assert pending.json()["detail"]["opens_at"]

            # Manual full / cancelled / postponed.
            version = update_event(client, event_id, version, regOpensAt="", regMode="full")
            assert public_event(client, event_id)["registration"]["state"] == "full"
            assert visitor.get(f"/api/public/forms/{form_id}").status_code == 409
            version = update_event(client, event_id, version, regMode="auto", lifecycle="cancelled")
            assert public_event(client, event_id)["registration"]["state"] == "cancelled"
            assert visitor.get(f"/api/public/forms/{form_id}/draft").status_code == 409
            version = update_event(client, event_id, version, lifecycle="postponed")
            postponed = public_event(client, event_id)["registration"]
            assert postponed["state"] == "open" and postponed["reason"] == "postponed"
            assert visitor.get(f"/api/public/forms/{form_id}").status_code == 200

            # Panel validation: bad datetime / order / choice are field-specific and do not persist.
            for record, field in (
                ({"regClosesAt": "فردا"}, "regClosesAt"),
                ({"startsAt": iso(timedelta(days=3)), "endsAt": iso(timedelta(days=2))}, "endsAt"),
                ({"regOpensAt": iso(timedelta(days=3)), "regClosesAt": iso(timedelta(days=2))}, "regClosesAt"),
                ({"regMode": "maybe"}, "regMode"),
                ({"lifecycle": "lost"}, "lifecycle"),
            ):
                rejected = client.put(
                    f"/api/admin/content/events/{event_id}",
                    json={"record": record, "expected_version": version},
                    headers=owner_write_headers(client),
                )
                assert rejected.status_code == 422, rejected.text
                assert rejected.json()["detail"]["field"] == field
            assert public_event(client, event_id)["registration"]["reason"] == "postponed"
    finally:
        app.state.engine.dispose() if hasattr(app.state, "engine") else None


def test_event_linked_banners_follow_the_event_and_server_clock():
    app, _engine = gate_app()
    try:
        with TestClient(app) as client:
            owner_login(client)
            event_id, version = create_published_event(client, 0)
            create_published_form(client, event_id=event_id, key="phase7-banner-form")
            site_version = client.get("/api/owner/site-content").json()["version"]
            banners = [
                {"id": "qa-reg", "status": "published", "t": "[QA] ثبت‌نام باز", "eventId": event_id,
                 "countdown": "reg_close", "afterEnd": "message", "afterEndText": "مهلت تمام شد"},
                {"id": "qa-start", "status": "published", "t": "[QA] تا شروع", "eventId": event_id,
                 "countdown": "event_start", "href": "events.html"},
                {"id": "qa-campaign-live", "status": "published", "t": "[QA] کمپین", "countdown": "campaign_end",
                 "campaignEndsAt": iso(timedelta(hours=2)), "href": "events.html", "primaryLabel": "ببین"},
                {"id": "qa-campaign-done", "status": "published", "t": "[QA] کمپین تمام", "countdown": "campaign_end",
                 "campaignEndsAt": iso(timedelta(hours=-2)), "afterEnd": "hide"},
                {"id": "qa-campaign-done-msg", "status": "published", "t": "[QA] کمپین تمام با پیام",
                 "countdown": "campaign_end", "campaignEndsAt": iso(timedelta(hours=-2)), "afterEnd": "message"},
                {"id": "qa-scheduled", "status": "published", "t": "[QA] آینده", "startsAt": iso(timedelta(days=1))},
                {"id": "qa-expired", "status": "published", "t": "[QA] منقضی", "endsAt": iso(timedelta(days=-1))},
                {"id": "qa-off", "status": "published", "active": False, "t": "[QA] خاموش"},
                {"id": "qa-draft", "status": "draft", "t": "[QA] پیش‌نویس"},
                {"id": "qa-ghost", "status": "published", "t": "[QA] رویداد ناموجود", "eventId": "ev-missing"},
            ]
            saved = client.patch(
                "/api/owner/site-content",
                json={"content": {"banners": banners}, "expected_version": site_version},
                headers=owner_write_headers(client),
            )
            assert saved.status_code == 200, saved.text
            version = saved.json()["version"]  # the document version is shared with events
            # Owner view keeps every row (editor) but resolves the event.
            owner_rows = {row["id"]: row for row in saved.json()["content"]["banners"]}
            assert set(owner_rows) == {row["id"] for row in banners}
            assert owner_rows["qa-reg"]["event"]["id"] == event_id

            public = {row["id"]: row for row in client.get("/api/public/site-content").json()["content"]["banners"]}
            assert set(public) == {"qa-reg", "qa-start", "qa-campaign-live", "qa-campaign-done-msg"}
            event = public_event(client, event_id)
            assert public["qa-reg"]["href"] == f"event.html?id={event_id}"
            assert public["qa-reg"]["countdown"] == "reg_close"
            assert public["qa-reg"]["countdownTo"] == event["regClosesAt"]
            assert public["qa-reg"]["countdownEnded"] is False
            assert public["qa-reg"]["event"]["state"] == "open"
            assert public["qa-start"]["countdownTo"] == event["startsAt"]
            assert public["qa-start"]["href"] == "events.html"  # explicit link kept while live
            assert public["qa-campaign-live"]["countdown"] == "campaign_end"
            assert public["qa-campaign-done-msg"]["countdownEnded"] is True
            assert public["qa-campaign-done-msg"]["countdownTo"] == ""

            # Deadline passes → event-linked banner shows the "ended" state and may only
            # lead to the detail page; the one with afterEnd=hide disappears.
            version = update_event(client, event_id, version, regClosesAt=iso(timedelta(minutes=-1)))
            public = {row["id"]: row for row in client.get("/api/public/site-content").json()["content"]["banners"]}
            assert public["qa-reg"]["countdownEnded"] is True and public["qa-reg"]["countdownTo"] == ""
            assert public["qa-reg"]["href"] == f"event.html?id={event_id}"
            assert public["qa-reg"]["event"]["state"] == "closed"
            assert "qa-start" in public  # event start still ahead

            # Pausing the event removes every banner that points at it (no draft leak).
            paused = client.post(
                f"/api/admin/content/events/{event_id}/status",
                json={"status": "paused", "expected_version": version},
                headers=owner_write_headers(client),
            )
            assert paused.status_code == 200, paused.text
            public = {row["id"]: row for row in client.get("/api/public/site-content").json()["content"]["banners"]}
            assert "qa-reg" not in public and "qa-start" not in public
            assert "qa-campaign-live" in public
    finally:
        pass


def test_banner_writes_require_the_owner_in_the_backend():
    app, _engine = gate_app()
    try:
        with TestClient(app) as client:
            payload = {"content": {"banners": [{"id": "x", "status": "published", "t": "نفوذ"}]}, "expected_version": 0}
            assert client.patch("/api/owner/site-content", json=payload, headers=ORIGIN).status_code == 401
            member_id = bale_login(client, 82001)
            # A member session is not a staff session at all (401); a manager is staff but not owner (403).
            assert client.patch(
                "/api/owner/site-content", json=payload, headers=account_write_headers(client),
            ).status_code in (401, 403)
            client.cookies.clear()
            manager_id = bale_login(client, 82002)
            assert manager_id != member_id
            assign_manager(client, manager_id)
            assert client.get("/api/admin/content/events").status_code == 200  # manager session works
            denied = client.patch("/api/owner/site-content", json=payload, headers=owner_write_headers(client))
            assert denied.status_code in (401, 403), denied.text  # owner-only route rejects the manager session
            assert client.get("/api/public/site-content").status_code == 404  # nothing was published
    finally:
        pass
