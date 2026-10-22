"""Phase 9.4 §7: idempotent user notifications (outbox) for the real data paths.

Proved here, nothing more:

* ``backend.notifications.queue`` is insert-or-find by a stable key: a retry, a duplicate webhook
  or a double click adds no second row; a race on the unique key is absorbed (savepoint);
* ``link`` only ever points at an in-app page — API/download/absolute URLs are refused;
* recorded ≠ sent ≠ delivered: new rows are ``pending`` (queued) — accounts without a
  server-linked Bale identity get an honest ``failed/no_bale_identity`` row, not a network error;
* real paths: purchase recorded, access activated (retry-safe, re-grant after revoke = new row),
  new session/resource published → one row per *active* holder only, certificate issued/revoked
  (mirror state change only), receipt decision, organizer answer (refresh, same row);
* the bot drains the same rows (``/api/bot/notifications/pending``), acks delivery, and a send
  failure never deletes the business row;
* migration 0035 round-trips on existing rows.

Real Bale sending is impossible here (no token, no internet) — the bot path is «صف و ساختار اعلان».
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT.parent))

from backend import notifications as notifications_mod  # noqa: E402
from backend.models import AccountRecord, RecordingAccessRecord, UserNotificationRecord  # noqa: E402
from test_certificates_api import base_certificate, make_app as certificate_app, submit as submit_certificate  # noqa: E402
from test_event_registration_gate import gate_app  # noqa: E402
from test_recordings_api import (  # noqa: E402
    build_sellable_product, held_event, inbox_decide, notifications, purchase_form, set_status, submit_purchase,
    upload_purchase_receipt,
)
from test_workflows_api import SERVICE_TOKEN, bale_login, owner_login, owner_write_headers  # noqa: E402


def service_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {SERVICE_TOKEN}"}


def order_id(engine, account_id: str) -> str:
    from backend.models import RecordingOrderRecord
    with Session(engine) as db:
        return str(db.scalar(select(RecordingOrderRecord.id).where(RecordingOrderRecord.account_id == account_id)))


def rows(engine, account_id: str) -> dict[str, list[UserNotificationRecord]]:
    out: dict[str, list[UserNotificationRecord]] = {}
    for item in notifications(engine, account_id):
        out.setdefault(item.kind, []).append(item)
    return out


# ── unit: the write path itself ──


def test_queue_is_insert_or_find_and_links_are_in_app_pages_only():
    app, engine = gate_app()
    try:
        with Session(engine) as db:
            db.add(AccountRecord(id="acc-web-only"))
            db.add(AccountRecord(id="acc-bale"))
            db.commit()
            first, created = notifications_mod.queue(
                db, account_id="acc-bale", kind="x", title="t", body="b", key="k:1", bale_ids=["91001"],
                link="/event.html?id=ev-1#recording",
            )
            again, created_again = notifications_mod.queue(
                db, account_id="acc-bale", kind="x", title="other", body="other", key="k:1", bale_ids=["91001"],
            )
            assert created is True and created_again is False and again.id == first.id and again.title == "t"
            assert first.delivery_status == "pending" and first.bale_user_id == "91001" and first.link == "/event.html?id=ev-1#recording"
            refreshed, _ = notifications_mod.queue(
                db, account_id="acc-bale", kind="x", title="edited", body="edited", key="k:1", bale_ids=["91001"], refresh=True,
            )
            assert refreshed.id == first.id and refreshed.title == "edited" and refreshed.delivery_status == "pending"
            honest, _ = notifications_mod.queue(
                db, account_id="acc-web-only", kind="x", title="t", body="b", key="k:2", bale_ids=[],
            )
            assert honest.delivery_status == "failed" and honest.last_delivery_error == "no_bale_identity" and honest.bale_user_id == ""
            db.commit()
            assert db.scalar(select(func.count(UserNotificationRecord.id))) == 2
            for bad in ("https://example.com/event.html", "//evil/event.html", "/api/public/events/x/resources/y/download",
                        "/event.html?id=../../x", "/files/secret.mp4", "event.html", "/event.html\\x", "/admin.html"):
                with pytest.raises(notifications_mod.NotificationLinkError):
                    notifications_mod.safe_link(bad)
            assert notifications_mod.safe_link("/account.html#certificates") == "/account.html#certificates"
            assert notifications_mod.safe_link(None) is None
            with pytest.raises(ValueError):
                notifications_mod.dedupe_key("")
    finally:
        engine.dispose()


# ── HTTP: real data paths ──


def test_access_activation_is_retry_safe_but_a_regrant_after_revoke_is_a_new_row():
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_id, _v = held_event(owner, 0)
            product = build_sellable_product(owner, event_id, price=0, payment_card=None)
            assert set_status(owner, event_id, "ready").status_code == 200
            assert set_status(owner, event_id, "published").status_code == 200
            holder = TestClient(app)
            holder_id = bale_login(holder, 97101)
            grant_url = f"/api/admin/events/{event_id}/recording/access"
            first = owner.post(grant_url, json={"account_id": holder_id, "reason": "اعطای اول"}, headers=owner_write_headers(owner))
            assert first.status_code == 201, first.text
            # Double click / retried request while the access is already active → same single row.
            second = owner.post(grant_url, json={"account_id": holder_id, "reason": "دوباره"}, headers=owner_write_headers(owner))
            assert second.status_code in (200, 201)
            queued = rows(engine, holder_id)
            assert len(queued["recording_access"]) == 1
            assert queued["recording_access"][0].dedupe_key.endswith(":first") and queued["recording_access"][0].link == f"/event.html?id={event_id}#recording"
            access_id = first.json()["access"]["id"]
            assert owner.post(f"{grant_url}/{access_id}/revoke", json={"reason": "آزمون"}, headers=owner_write_headers(owner)).status_code == 200
            third = owner.post(grant_url, json={"account_id": holder_id, "reason": "بازگردانی"}, headers=owner_write_headers(owner))
            assert third.status_code in (200, 201)
            queued = rows(engine, holder_id)
            assert len(queued["recording_access"]) == 2  # a real re-activation is a new notification
            assert len({row.dedupe_key for row in queued["recording_access"]}) == 2

            # Web-only account (no Bale identity): honest failed row, never a fake "sent".
            with Session(engine) as db:
                db.add(AccountRecord(id="5f0c2d1e-9b8a-4c7d-8e6f-1a2b3c4d5e6f"))
                db.commit()
            granted = owner.post(grant_url, json={"account_id": "5f0c2d1e-9b8a-4c7d-8e6f-1a2b3c4d5e6f", "reason": "مهمان وب"}, headers=owner_write_headers(owner))
            assert granted.status_code == 201, granted.text
            web_rows = notifications(engine, "5f0c2d1e-9b8a-4c7d-8e6f-1a2b3c4d5e6f")
            assert len(web_rows) == 1 and web_rows[0].delivery_status == "failed" and web_rows[0].last_delivery_error == "no_bale_identity"
            pending = owner.get("/api/bot/notifications/pending", headers=service_headers()).json()["items"]
            assert all(item["bale_user_id"] for item in pending)  # rows without a destination are never handed to the bot
            assert all(item["link"] in (None, f"/event.html?id={event_id}#recording") for item in pending)
    finally:
        engine.dispose()


def test_new_session_or_resource_notifies_only_active_holders_once_and_only_when_live():
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_id, _v = held_event(owner, 0)
            product = build_sellable_product(owner, event_id, price=0, payment_card=None)
            assert set_status(owner, event_id, "ready").status_code == 200
            assert set_status(owner, event_id, "published").status_code == 200
            active, revoked, stranger = TestClient(app), TestClient(app), TestClient(app)
            active_id, revoked_id = bale_login(active, 97201), bale_login(revoked, 97202)
            stranger_id = bale_login(stranger, 97203)
            grant_url = f"/api/admin/events/{event_id}/recording/access"
            for account_id in (active_id, revoked_id):
                assert owner.post(grant_url, json={"account_id": account_id, "reason": "اعطای آزمون"}, headers=owner_write_headers(owner)).status_code == 201
            with Session(engine) as db:
                revoked_access = db.scalar(select(RecordingAccessRecord).where(RecordingAccessRecord.account_id == revoked_id))
            assert owner.post(f"{grant_url}/{revoked_access.id}/revoke", json={"reason": "لغو آزمون"}, headers=owner_write_headers(owner)).status_code == 200

            # New session: draft → published.
            session = owner.post(f"/api/admin/events/{event_id}/recording/sessions",
                                 json={"title": "جلسهٔ دوم: تمرین", "duration_minutes": 40}, headers=owner_write_headers(owner))
            assert session.status_code == 201
            session_id = session.json()["id"]
            session_url = f"/api/admin/events/{event_id}/recording/sessions/{session_id}"
            assert owner.put(session_url, json={"status": "published"}, headers=owner_write_headers(owner)).status_code == 200
            assert owner.put(session_url, json={"status": "draft"}, headers=owner_write_headers(owner)).status_code == 200
            assert owner.put(session_url, json={"status": "published"}, headers=owner_write_headers(owner)).status_code == 200  # again
            assert len(rows(engine, active_id).get("recording_content", [])) == 1  # once, despite the round trip
            assert "recording_content" not in rows(engine, revoked_id)
            assert notifications(engine, stranger_id) == []
            note = rows(engine, active_id)["recording_content"][0]
            assert "جلسهٔ دوم: تمرین" in note.body and note.link == f"/event.html?id={event_id}#recording" and "/api/" not in note.body

            # New resource in that session: published with a future publish_at → nothing (not visible yet);
            # published live → one more row for the active holder only.
            resource = owner.post(f"/api/admin/events/{event_id}/resources",
                                  json={"title": "جزوهٔ جلسهٔ دوم", "access": "purchased", "session_id": session_id, "kind": "link",
                                        "link_url": "https://example.org/notes"}, headers=owner_write_headers(owner))
            assert resource.status_code == 201, resource.text
            res_url = f"/api/admin/events/{event_id}/resources/{resource.json()['id']}"
            scheduled = owner.put(res_url, json={"status": "published", "publish_at": "2099-01-01T10:00:00+00:00"}, headers=owner_write_headers(owner))
            assert scheduled.status_code == 200, scheduled.text
            assert len(rows(engine, active_id)["recording_content"]) == 1
            assert owner.put(res_url, json={"status": "draft"}, headers=owner_write_headers(owner)).status_code == 200
            live = owner.put(res_url, json={"status": "published", "publish_at": None}, headers=owner_write_headers(owner))
            assert live.status_code == 200, live.text
            assert len(rows(engine, active_id)["recording_content"]) == 2
            assert "recording_content" not in rows(engine, revoked_id)
    finally:
        engine.dispose()


def test_receipt_flow_purchase_recorded_then_decision_without_duplicates():
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_id, _v = held_event(owner, 0)
            product = build_sellable_product(owner, event_id, price=900_000)
            form_id = purchase_form(owner, product["recording"]["id"], price=900_000)
            assert set_status(owner, event_id, "ready").status_code == 200
            assert set_status(owner, event_id, "published").status_code == 200
            buyer = TestClient(app)
            buyer_id = bale_login(buyer, 97301)
            assert submit_purchase(buyer, form_id).status_code == 200
            sent = upload_purchase_receipt(buyer, form_id)
            assert sent.status_code == 200, sent.text
            recorded = rows(engine, buyer_id)
            assert list(recorded) == ["recording_purchase"] and recorded["recording_purchase"][0].delivery_status == "pending"
            assert "۹۰۰" in recorded["recording_purchase"][0].body or "900" in recorded["recording_purchase"][0].body
            mine = buyer.get("/api/account/notifications").json()["items"]
            assert mine[0]["kind"] == "recording_purchase" and mine[0]["link"] == f"/event.html?id={event_id}#recording"
            assert mine[0]["delivery_state"] == "queued"
            task_id = sent.json()["review_task_id"]
            approved = inbox_decide(owner, task_id, "approved", "", owner_write_headers(owner))
            assert approved.status_code == 200, approved.text
            # A second decision on the same task is rejected by the version gate; even so, rows are unique per task+kind.
            inbox_decide(owner, task_id, "approved", "", owner_write_headers(owner))
            after = rows(engine, buyer_id)
            # Approval = «دسترسی فعال شد» (one row); a separate "receipt approved" message would be noise (9.1 decision).
            assert sorted(after) == ["recording_access", "recording_purchase"]
            assert all(len(items) == 1 for items in after.values())
            assert after["recording_access"][0].dedupe_key.endswith(":first")
            assert after["recording_purchase"][0].dedupe_key == f"recording_order:{order_id(engine, buyer_id)}:receipt_submitted"

            # Bot path: pending rows drain through the service API; a failed attempt keeps the business rows.
            pending = owner.get("/api/bot/notifications/pending", headers=service_headers()).json()["items"]
            ids = {item["id"] for item in pending}
            assert {row.id for items in after.values() for row in items} <= ids
            target = after["recording_access"][0]
            failed = owner.post(f"/api/bot/notifications/{target.id}/delivery-failed", json={"bale_user_id": "97301"}, headers=service_headers())
            assert failed.status_code == 200
            state = next(i for i in buyer.get("/api/account/notifications").json()["items"] if i["id"] == target.id)
            assert state["delivery_state"] == "retrying" and state["delivery_attempts"] == 1
            assert buyer.get("/api/account/recordings").json()["items"][0]["access"]["state"] == "active"  # op untouched
            delivered = owner.post(f"/api/bot/notifications/{target.id}/delivered", json={"bale_user_id": "97301"}, headers=service_headers())
            assert delivered.status_code == 200
            state = next(i for i in buyer.get("/api/account/notifications").json()["items"] if i["id"] == target.id)
            assert state["delivery_state"] == "delivered"
    finally:
        engine.dispose()


def test_certificate_mirror_notifies_on_issue_and_revoke_only_once_each():
    app, engine = certificate_app()
    try:
        with TestClient(app) as client:
            member = TestClient(app)
            member_id = bale_login(member, 97401)
            issued = submit_certificate(client, bale_user_id="97401", key="cert-9-4-1", certificate=base_certificate())
            assert issued.status_code == 200, issued.text
            assert submit_certificate(client, bale_user_id="97401", key="cert-9-4-1", certificate=base_certificate(verify_count=3)).status_code == 200
            after_issue = rows(engine, member_id)
            assert list(after_issue) == ["certificate"] and len(after_issue["certificate"]) == 1
            assert after_issue["certificate"][0].dedupe_key == "certificate:cert-9-4-1:issued"
            assert after_issue["certificate"][0].link == "/account.html#certificates" and "صادر شد" in after_issue["certificate"][0].title
            revoked = submit_certificate(
                client, bale_user_id="97401", key="cert-9-4-1",
                certificate=base_certificate(status="revoked", revoked_at="2026-05-01T10:00:00+00:00"),
            )
            assert revoked.status_code == 200, revoked.text
            submit_certificate(client, bale_user_id="97401", key="cert-9-4-1",
                               certificate=base_certificate(status="revoked", revoked_at="2026-05-01T10:00:00+00:00"))
            after_revoke = rows(engine, member_id)["certificate"]
            assert sorted(row.dedupe_key for row in after_revoke) == ["certificate:cert-9-4-1:issued", "certificate:cert-9-4-1:revoked"]
            account_view = member.get("/api/account/notifications").json()["items"]
            assert {item["kind"] for item in account_view} == {"certificate"} and all("/api/" not in item["body"] for item in account_view)
    finally:
        engine.dispose()


# ── migration ──


def test_notification_dedupe_migration_round_trip(tmp_path, monkeypatch):
    from sqlalchemy.exc import IntegrityError

    database_url = f"sqlite+pysqlite:///{tmp_path / 'legacy-notifications.db'}"
    monkeypatch.setenv("NORA_DATABASE_URL", database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    command.upgrade(config, "0034_private_storage")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO accounts (id) VALUES ('acc-n-1')"))
            connection.execute(text(
                "INSERT INTO user_notifications (id, account_id, bale_user_id, kind, title, body, file_refs, delivery_status, delivery_attempts) "
                "VALUES ('n-old-1', 'acc-n-1', '91001', 'receipt_approved', 't', 'b', '[]', 'delivered', 1), "
                "('n-old-2', 'acc-n-1', '', 'recording_access', 't', 'b', '[]', 'failed', 0)"
            ))
        assert "dedupe_key" not in {c["name"] for c in inspect(engine).get_columns("user_notifications")}
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        columns = {c["name"] for c in inspect(engine).get_columns("user_notifications")}
        assert {"dedupe_key", "link"} <= columns
        assert "uq_user_notifications_dedupe_key" in {u["name"] for u in inspect(engine).get_unique_constraints("user_notifications")}
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0036_upload_sessions"
            # Old rows: NULL key (several NULLs allowed), delivery state untouched.
            assert connection.scalar(text("SELECT COUNT(*) FROM user_notifications WHERE dedupe_key IS NULL")) == 2
            assert connection.scalar(text("SELECT delivery_status FROM user_notifications WHERE id = 'n-old-1'")) == "delivered"
            connection.execute(text(
                "INSERT INTO user_notifications (id, account_id, bale_user_id, kind, title, body, file_refs, delivery_status, delivery_attempts, dedupe_key, link) "
                "VALUES ('n-new', 'acc-n-1', '91001', 'recording_purchase', 't', 'b', '[]', 'pending', 0, 'recording_order:o1:receipt_submitted', '/event.html?id=ev-1')"
            ))
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                with pytest.raises(IntegrityError):
                    connection.execute(text(
                        "INSERT INTO user_notifications (id, account_id, bale_user_id, kind, title, body, file_refs, delivery_status, delivery_attempts, dedupe_key) "
                        "VALUES ('n-dup', 'acc-n-1', '91001', 'recording_purchase', 't', 'b', '[]', 'pending', 0, 'recording_order:o1:receipt_submitted')"
                    ))
            finally:
                transaction.rollback()
    finally:
        engine.dispose()

    command.downgrade(config, "0034_private_storage")
    engine = create_engine(database_url)
    try:
        assert not {"dedupe_key", "link"} & {c["name"] for c in inspect(engine).get_columns("user_notifications")}
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT COUNT(*) FROM user_notifications")) == 3  # nothing deleted
    finally:
        engine.dispose()
    command.upgrade(config, "head")


# ── panel: global outbox list (rp_view) ──


def test_admin_notification_list_shows_states_counts_and_never_raw_bale_ids_or_file_urls():
    from backend.roles import ROLE_CLUB_SUPERVISOR
    from test_workflows_api import assign_manager

    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_id, _v = held_event(owner, 0)
            build_sellable_product(owner, event_id, price=0, payment_card=None)
            assert set_status(owner, event_id, "ready").status_code == 200
            assert set_status(owner, event_id, "published").status_code == 200
            holder = TestClient(app)
            holder_id = bale_login(holder, 97501)
            grant_url = f"/api/admin/events/{event_id}/recording/access"
            assert owner.post(grant_url, json={"account_id": holder_id, "reason": "اعطای آزمون"}, headers=owner_write_headers(owner)).status_code == 201
            with Session(engine) as db:
                db.add(AccountRecord(id="7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"))
                db.commit()
            assert owner.post(grant_url, json={"account_id": "7a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d", "reason": "حساب وب"},
                              headers=owner_write_headers(owner)).status_code == 201

            # Guest and plain member: no access to the global outbox.
            assert TestClient(app).get("/api/admin/notifications").status_code == 401
            assert holder.get("/api/admin/notifications").status_code == 403

            listing = owner.get("/api/admin/notifications")
            assert listing.status_code == 200, listing.text
            data = listing.json()
            assert data["counts"] == {"queued": 1, "retrying": 0, "delivered": 0, "failed": 0, "no_bale_identity": 1}
            assert {item["delivery_state"] for item in data["items"]} == {"queued", "failed"}
            for item in data["items"]:
                assert "bale_user_id" not in item and isinstance(item["has_bale_identity"], bool) and isinstance(item["account_label"], str)
                assert "/api/" not in item["body"] and item["link"] == f"/event.html?id={event_id}#recording"
            web_only = next(item for item in data["items"] if item["has_bale_identity"] is False)
            assert web_only["last_delivery_error"] == "no_bale_identity" and web_only["delivery_state"] == "failed"
            assert owner.get("/api/admin/notifications?state=no_bale_identity").json()["items"][0]["id"] == web_only["id"]
            assert owner.get("/api/admin/notifications?state=queued").json()["items"][0]["has_bale_identity"] is True
            assert owner.get("/api/admin/notifications?state=bogus").status_code == 422
            assert owner.get("/api/admin/notifications?kind=recording_access").json()["counts"]["queued"] == 1
            assert owner.get("/api/admin/notifications?kind=certificate").json()["items"] == []

            # Attempts and errors are visible: one provider failure → retrying with attempts=1.
            queued_id = owner.get("/api/admin/notifications?state=queued").json()["items"][0]["id"]
            assert owner.post(f"/api/bot/notifications/{queued_id}/delivery-failed", json={"bale_user_id": "97501"},
                              headers=service_headers()).status_code == 200
            after = owner.get("/api/admin/notifications?state=retrying").json()
            assert after["counts"]["retrying"] == 1 and after["counts"]["queued"] == 0
            assert after["items"][0]["delivery_attempts"] == 1 and after["items"][0]["last_delivery_error"]

            # Manager (rp_view) may read; a member without any role stays at 403 even after being an access holder.
            # Role model is unchanged: club supervisor = manager ∪ club permissions, so it also reads.
            manager = TestClient(app)
            manager_id = bale_login(manager, 97502)
            assign_manager(manager, manager_id)
            assert manager.get("/api/admin/notifications").status_code == 200
            assert holder.get("/api/admin/notifications?state=queued").status_code == 403
            assert ROLE_CLUB_SUPERVISOR  # imported to document the role-model decision above
    finally:
        engine.dispose()
