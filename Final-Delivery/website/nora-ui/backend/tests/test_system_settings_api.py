"""Panel «تنظیمات» (1405/08/01): allowlisted owner settings with real consumers.

Covers: owner read/write + audit, default-reset removes the row, unknown key / bad value → 422
without partial writes, manager without ``sys_settings`` → 403, missing CSRF → 400, and the
reminder consumer (``texts.reminder_head``) reaching ``event_reminders.message_for``.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend import event_reminders, system_settings  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import (  # noqa: E402
    AccountRecord,
    AccountRoleRecord,
    AccountSessionRecord,
    AdminAuditEventRecord,
    Base,
    SystemSettingRecord,
)
from backend.security import hash_password, token_digest  # noqa: E402

OWNER_USER = "nora-owner"
OWNER_PASS = "correct-horse-staple-42"
ORIGIN = {"Origin": "http://testserver"}
SESSION = "sys-settings-session"
CSRF = "sys-settings-csrf"


@pytest.fixture
def env():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username=OWNER_USER,
        owner_password_hash=hash_password(OWNER_PASS),
        cookie_secure=False,
        otp_pepper="p" * 40,
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


def owner_headers(client: TestClient) -> dict[str, str]:
    login = client.post("/api/auth/login", json={"username": OWNER_USER, "password": OWNER_PASS}, headers=ORIGIN)
    assert login.status_code == 200, login.text
    return {**ORIGIN, "X-CSRF-Token": client.cookies.get("nora_csrf", "")}


def install_manager(client: TestClient, account_id: str) -> dict[str, str]:
    with client.app.state.session_factory() as db:
        db.add(AccountRecord(id=account_id))
        db.add(AccountRoleRecord(account_id=account_id, role="manager", assigned_by="owner-01"))
        db.add(AccountSessionRecord(
            id=str(uuid.uuid4()), account_id=account_id, auth_provider="manager-password",
            token_hash=token_digest(SESSION + account_id), csrf_hash=token_digest(CSRF + account_id),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        db.commit()
    cfg = client.app.state.settings
    client.cookies.set(cfg.account_cookie_name, SESSION + account_id, path="/")
    client.cookies.set(cfg.account_csrf_cookie_name, CSRF + account_id, path="/")
    return {**ORIGIN, "X-CSRF-Token": CSRF + account_id}


def items_by_key(payload: dict) -> dict[str, dict]:
    return {item["key"]: item for item in payload["items"]}


def test_owner_reads_defaults_and_writes_with_audit(env):
    client, engine = env
    headers = owner_headers(client)

    read = client.get("/api/owner/settings", headers=headers)
    assert read.status_code == 200, read.text
    assert "no-store" in read.headers["cache-control"]
    before = items_by_key(read.json())
    assert set(before) == {spec.key for spec in system_settings.SPECS}
    assert before["texts.reminder_head"]["value"] == ""
    assert before["texts.reminder_head"]["custom"] is False
    assert before["events.reminders_default"]["value"] == {"h24": False, "h1": False}
    assert all(item["consumer"] for item in before.values())

    write = client.put(
        "/api/owner/settings",
        json={"changes": {"texts.reminder_head": "  فردا «{رویداد}» {زمان} شروع می‌شود \n", "events.reminders_default": {"h24": True, "h1": False}}},
        headers=headers,
    )
    assert write.status_code == 200, write.text
    after = items_by_key(write.json())
    assert after["texts.reminder_head"]["value"] == "فردا «{رویداد}» {زمان} شروع می‌شود"
    assert after["texts.reminder_head"]["custom"] is True
    assert after["texts.reminder_head"]["updated_by"] == "owner-01"
    assert after["events.reminders_default"]["value"] == {"h24": True, "h1": False}

    again = items_by_key(client.get("/api/owner/settings", headers=headers).json())
    assert again["texts.reminder_head"]["value"] == "فردا «{رویداد}» {زمان} شروع می‌شود"

    with Session(engine) as db:
        rows = db.scalars(select(AdminAuditEventRecord).where(AdminAuditEventRecord.action == "system_settings.update")).all()
        assert len(rows) == 1
        assert rows[0].target_type == "system_settings"
        assert rows[0].details["changed"] == "events.reminders_default,texts.reminder_head"

    # Writing the default again removes the row: no stale "custom" marker.
    reset = client.put("/api/owner/settings", json={"changes": {"texts.reminder_head": ""}}, headers=headers)
    assert reset.status_code == 200
    assert items_by_key(reset.json())["texts.reminder_head"]["custom"] is False
    with Session(engine) as db:
        assert db.get(SystemSettingRecord, "texts.reminder_head") is None
        assert db.get(SystemSettingRecord, "events.reminders_default") is not None


def test_unknown_key_or_bad_value_rejects_whole_request(env):
    client, engine = env
    headers = owner_headers(client)

    unknown = client.put(
        "/api/owner/settings",
        json={"changes": {"texts.reminder_head": "x", "money.installments": True}},
        headers=headers,
    )
    assert unknown.status_code == 422
    assert unknown.json()["detail"]["code"] == "unknown_setting"

    bad = client.put(
        "/api/owner/settings",
        json={"changes": {"texts.reminder_head": "x", "events.reminders_default": {"h24": "yes"}}},
        headers=headers,
    )
    assert bad.status_code == 422
    assert bad.json()["detail"]["code"] == "invalid_reminders_default"

    too_long = client.put("/api/owner/settings", json={"changes": {"texts.reminder_head": "ا" * 301}}, headers=headers)
    assert too_long.status_code == 422
    assert too_long.json()["detail"]["code"] == "text_too_long"

    shape = client.put("/api/owner/settings", json={"texts.reminder_head": "x"}, headers=headers)
    assert shape.status_code == 400

    with Session(engine) as db:
        assert db.scalars(select(SystemSettingRecord)).all() == []
        assert db.scalars(select(AdminAuditEventRecord)).all() == []


def test_manager_without_sys_settings_is_refused_and_csrf_is_required(env):
    client, _engine = env
    headers = install_manager(client, "acc-manager-1")
    assert client.get("/api/owner/settings").status_code == 403
    assert client.put("/api/owner/settings", json={"changes": {"texts.reminder_head": "x"}}, headers=headers).status_code == 403

    client.cookies.clear()
    owner = owner_headers(client)
    no_csrf = client.put("/api/owner/settings", json={"changes": {"texts.reminder_head": "x"}}, headers=ORIGIN)
    assert no_csrf.status_code in (400, 403)
    assert client.put("/api/owner/settings", json={"changes": {"texts.reminder_head": "x"}}, headers=owner).status_code == 200


def test_reminder_head_template_reaches_message(env):
    _client, engine = env
    row = {"id": "ev-1", "t": "نشست کتاب", "place": "سالن", "mode": "onsite"}
    starts = datetime(2026, 11, 3, 6, 30, tzinfo=timezone.utc)
    default_title, default_body = event_reminders.message_for(row, "h24", starts)
    assert default_body.startswith("یادآوری: «نشست کتاب»")

    with Session(engine) as db:
        system_settings.apply(db, {"texts.reminder_head": "دوست عزیز، «{رویداد}» {زمان} برگزار می‌شود"}, actor="owner-01")
        db.commit()
        head = system_settings.get_value(db, "texts.reminder_head")
    title, body = event_reminders.message_for(row, "h1", starts, head_template=head)
    assert title == default_title.replace("یادآوری رویداد: نشست کتاب", "یادآوری رویداد: نشست کتاب")
    assert body.splitlines()[0] == "دوست عزیز، «نشست کتاب» " + event_reminders.SLOT_LABEL["h1"] + " برگزار می‌شود"
    assert "زمان شروع:" in body and "مکان: سالن · حضوری" in body
