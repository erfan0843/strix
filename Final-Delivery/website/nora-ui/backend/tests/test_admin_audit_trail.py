"""Administrative audit trail, inbox decision history and owner account search.

Runs against an in-memory SQLite database: nothing touches real data.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend import audit as audit_mod  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import AccountProfileRecord, AdminAuditEventRecord, Base  # noqa: E402
from backend.roles import ROLE_MANAGER, ROLE_OWNER  # noqa: E402
from backend.security import hash_password  # noqa: E402

from test_workflows_api import (  # noqa: E402
    BOT_TOKEN,
    SERVICE_TOKEN,
    account_write_headers,
    bale_login,
    owner_login,
    owner_write_headers,
    submit_workflow,
)

MANAGER_PASSWORD = "audit-manager-password-2026"


def audit_app():
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


def events(engine, action: str | None = None) -> list[AdminAuditEventRecord]:
    with Session(engine) as db:
        query = select(AdminAuditEventRecord).order_by(AdminAuditEventRecord.created_at, AdminAuditEventRecord.id)
        if action:
            query = query.where(AdminAuditEventRecord.action == action)
        return list(db.scalars(query).all())


def test_sanitize_details_never_keeps_credential_like_keys_or_nested_values():
    cleaned = audit_mod.sanitize_details(
        {
            "username": "qa.manager",
            "password": "must-not-be-stored",
            "token": "x",
            "bot_token": "x",
            "secret_value": "x",
            "value": "x",
            "csrf": "x",
            "nested": {"password": "x"},
            "ok": True,
            "count": 3,
            "long": "a" * 500,
        }
    )
    assert cleaned == {"username": "qa.manager", "ok": True, "count": 3, "long": "a" * 160}


def test_role_and_credential_changes_are_audited_without_secrets_and_visible_to_owner_only():
    app, engine = audit_app()
    try:
        with TestClient(app) as client:
            account_id = bale_login(client, 73421)
            # A plain account (even with its own CSRF) cannot read the trail.
            assert client.get("/api/owner/audit").status_code == 401

            owner_login(client)
            assert client.get("/api/owner/audit").json()["items"] == []

            role = client.put(
                f"/api/owner/accounts/{account_id}/role",
                json={"role": ROLE_MANAGER},
                headers=owner_write_headers(client),
            )
            assert role.status_code == 200, role.text
            credentials = client.put(
                f"/api/owner/accounts/{account_id}/manager-credentials",
                json={"username": "Audit.Manager", "password": MANAGER_PASSWORD},
                headers=owner_write_headers(client),
            )
            assert credentials.status_code == 200, credentials.text
            removed = client.delete(
                f"/api/owner/accounts/{account_id}/manager-credentials",
                headers=owner_write_headers(client),
            )
            assert removed.status_code == 200
            cleared = client.put(
                f"/api/owner/accounts/{account_id}/role",
                json={"role": None},
                headers=owner_write_headers(client),
            )
            assert cleared.status_code == 200

            trail = client.get("/api/owner/audit")
            assert trail.status_code == 200
            body = trail.json()
            assert body["has_more"] is False
            assert "role.set" in body["actions"]
            actions = [item["action"] for item in body["items"]]
            # Newest first.
            assert actions == ["role.clear", "manager_credentials.remove", "manager_credentials.set", "role.set"]
            for item in body["items"]:
                assert item["actor_kind"] == "owner"
                assert item["actor_id"] == "owner-01"
                assert item["actor_role"] == ROLE_OWNER
                assert item["target_type"] == "account"
                assert item["target_id"] == account_id
                assert item["outcome"] == "ok"
                assert item["created_at"]
                flattened = repr(item).lower()
                assert MANAGER_PASSWORD.lower() not in flattened
                assert "password" not in item["details"]
            by_action = {item["action"]: item for item in body["items"]}
            assert by_action["role.set"]["details"] == {"previous_role": None, "role": ROLE_MANAGER}
            assert by_action["role.clear"]["details"] == {"previous_role": ROLE_MANAGER, "role": None}
            assert by_action["manager_credentials.set"]["details"] == {"username": "audit.manager", "replaced": False}
            assert by_action["manager_credentials.remove"]["details"] == {"had_login": True}

            filtered = client.get("/api/owner/audit?action=role.set")
            assert [item["action"] for item in filtered.json()["items"]] == ["role.set"]
            grouped = client.get("/api/owner/audit?action=role.")
            assert [item["action"] for item in grouped.json()["items"]] == ["role.clear", "role.set"]
            assert client.get("/api/owner/audit?action=manager_credentials.").json()["items"][0]["action"] == "manager_credentials.remove"
            assert client.get("/api/owner/audit?action=nothing.").json()["items"] == []
            assert client.get("/api/owner/audit?action=DROP%20TABLE").status_code == 422

            # Failed requests leave no trail (nothing happened).
            denied = client.put(
                f"/api/owner/accounts/{account_id}/manager-credentials",
                json={"username": "x", "password": "short"},
                headers=owner_write_headers(client),
            )
            assert denied.status_code == 422
            rows = events(engine)
            assert len(rows) == 4
            # Nothing secret in the raw rows either.
            for row in rows:
                assert MANAGER_PASSWORD not in repr(row.details)
    finally:
        engine.dispose()


def test_manager_sees_own_username_decisions_are_audited_and_history_is_listable():
    app, engine = audit_app()
    try:
        with TestClient(app) as client:
            account_id = bale_login(client, 73421)
            owner_login(client)
            assert client.put(
                f"/api/owner/accounts/{account_id}/role",
                json={"role": ROLE_MANAGER},
                headers=owner_write_headers(client),
            ).status_code == 200
            assert client.put(
                f"/api/owner/accounts/{account_id}/manager-credentials",
                json={"username": "inbox.manager", "password": MANAGER_PASSWORD},
                headers=owner_write_headers(client),
            ).status_code == 200
            client.cookies.delete("nora_session")
            client.cookies.delete("nora_csrf")
            staff = client.post(
                "/api/auth/staff-login",
                json={"username": "inbox.manager", "password": MANAGER_PASSWORD},
                headers={"Origin": "http://testserver"},
            )
            assert staff.status_code == 200, staff.text

            me = client.get("/api/account/me")
            assert me.status_code == 200
            assert me.json()["provider"] == "manager-password"
            assert me.json()["manager_username"] == "inbox.manager"
            assert MANAGER_PASSWORD not in repr(me.json())

            created = submit_workflow(
                client, kind="profile_review", key="profile-audit-1", data={"full_name": "سارا رضایی"}
            )
            assert created.status_code == 200, created.text
            task = created.json()["task"]

            pending = client.get("/api/admin/inbox")
            assert [item["id"] for item in pending.json()["items"]] == [task["id"]]
            assert pending.json()["status"] == "pending"
            assert client.get("/api/admin/inbox?status=decided").json()["items"] == []
            assert client.get("/api/admin/inbox?status=bogus").status_code == 422

            decided = client.post(
                f"/api/admin/inbox/{task['id']}/decision",
                json={"decision": "rejected", "reason": "مدرک ناخوانا", "expected_version": 1},
                headers=account_write_headers(client),
            )
            assert decided.status_code == 200, decided.text

            assert client.get("/api/admin/inbox").json()["items"] == []
            history = client.get("/api/admin/inbox?status=decided")
            assert history.status_code == 200
            rows = history.json()["items"]
            assert len(rows) == 1
            assert rows[0]["id"] == task["id"]
            assert rows[0]["status"] == "rejected"
            assert rows[0]["reviewed_by"] == account_id
            assert rows[0]["review_reason"] == "مدرک ناخوانا"
            assert rows[0]["reviewed_at"]
            assert client.get("/api/admin/inbox?status=approved").json()["items"] == []
            assert len(client.get("/api/admin/inbox?status=rejected").json()["items"]) == 1

            # The manager cannot read the owner-only trail, but the decision is in it.
            assert client.get("/api/owner/audit").status_code == 401
            decision_events = events(engine, "workflow.decide")
            assert len(decision_events) == 1
            event = decision_events[0]
            assert event.actor_kind == "account"
            assert event.actor_id == account_id
            assert event.actor_role == ROLE_MANAGER
            assert event.target_type == "admin_task" and event.target_id == task["id"]
            assert event.details == {"kind": "profile_review", "decision": "rejected", "has_reason": True}
    finally:
        engine.dispose()


def test_owner_account_list_exposes_profile_name_and_supports_search_and_role_filter():
    app, engine = audit_app()
    try:
        with TestClient(app) as client:
            named = bale_login(client, 73421)
            with Session(engine) as db:
                db.add(AccountProfileRecord(account_id=named, fields={"fullName": "زهرا کریمی"}))
                db.commit()
            client.cookies.clear()
            other = bale_login(client, 73422)
            client.cookies.clear()
            owner_login(client)
            assert client.put(
                f"/api/owner/accounts/{other}/role",
                json={"role": ROLE_MANAGER},
                headers=owner_write_headers(client),
            ).status_code == 200

            listing = client.get("/api/owner/accounts")
            assert listing.status_code == 200
            rows = {item["account_id"]: item for item in listing.json()["items"]}
            assert rows[named]["display_name"] == "زهرا کریمی"
            assert rows[other]["display_name"] == ""

            by_name = client.get("/api/owner/accounts?q=کریمی").json()
            assert [item["account_id"] for item in by_name["items"]] == [named]
            by_bale_id = client.get("/api/owner/accounts?q=73422").json()
            assert [item["account_id"] for item in by_bale_id["items"]] == [other]
            by_prefix = client.get(f"/api/owner/accounts?q={named[:8]}").json()
            assert [item["account_id"] for item in by_prefix["items"]] == [named]
            assert client.get("/api/owner/accounts?q=nobody-here").json()["items"] == []

            assigned = client.get("/api/owner/accounts?role=assigned").json()
            assert [item["account_id"] for item in assigned["items"]] == [other]
            unassigned = client.get("/api/owner/accounts?role=none").json()
            assert [item["account_id"] for item in unassigned["items"]] == [named]
            assert client.get("/api/owner/accounts?role=owner").status_code == 422
    finally:
        engine.dispose()
