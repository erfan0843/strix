"""«ساخت از روی این فرم» — ``POST /api/forms/{id}/duplicate``.

A published form that already has responses is immutable (PUT -> 409); the safe path to change it is a
NEW draft copied from it. The copy must carry structure only: never responses, payments, publication
state, the public link, or a foreign owner's form.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import (  # noqa: E402
    AccountRecord,
    AccountRoleRecord,
    AccountSessionRecord,
    Base,
    FormFieldRecord,
    FormRecord,
    FormResponseRecord,
)
from backend.security import hash_password, token_digest  # noqa: E402
from site_content_seed import seed_site_events  # noqa: E402

MANAGER = "acct-duplicate-manager"
MEMBER = "acct-duplicate-member"


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    seed_site_events(engine, {"event-dup-01": "کارگاه نمونه"})
    settings = Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"),
        cookie_secure=False,
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


def owner_headers(client: TestClient) -> dict[str, str]:
    login = client.post(
        "/api/auth/login",
        json={"username": "nora-owner", "password": "correct-horse-staple-42"},
        headers={"Origin": "http://testserver"},
    )
    assert login.status_code == 200, login.text
    return {"Origin": "http://testserver", "X-CSRF-Token": client.cookies.get("nora_csrf", "")}


def account_headers(client: TestClient, account_id: str, role: str | None) -> dict[str, str]:
    raw_session, raw_csrf = "sess-" + account_id, "csrf-" + account_id
    with client.app.state.session_factory() as db:
        db.add(AccountRecord(id=account_id))
        if role:
            db.add(AccountRoleRecord(account_id=account_id, role=role, assigned_by="owner-01"))
        db.add(AccountSessionRecord(
            id=str(uuid.uuid4()), account_id=account_id, auth_provider="manager-password",
            token_hash=token_digest(raw_session), csrf_hash=token_digest(raw_csrf),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        db.commit()
    settings = client.app.state.settings
    client.cookies.clear()
    client.cookies.set(settings.account_cookie_name, raw_session, path="/")
    client.cookies.set(settings.account_csrf_cookie_name, raw_csrf, path="/")
    return {"Origin": "http://testserver", "X-CSRF-Token": raw_csrf}


def source_form() -> dict:
    return {
        "name": "ثبت‌نام کارگاه پاییز",
        "model": "registration",
        "need": "reg",
        "slug": "workshops/autumn",
        "ev": "event-dup-01",
        "settings": {"description": "فرم مبدأ", "cap": 30, "wait": 5, "companions": {"enabled": False}},
        "fields": [
            {"id": "full-name", "t": "text", "l": "نام کامل", "required": True},
            {"id": "mobile", "t": "mobile", "l": "موبایل", "required": True},
            {"id": "city", "t": "select", "l": "شهر", "options": ["تهران", "شیراز"], "condField": "full-name", "condOp": "nempty"},
        ],
    }


def test_duplicate_makes_a_fresh_draft_without_responses_or_publication(client):
    headers = owner_headers(client)
    created = client.post("/api/forms", json=source_form(), headers={**headers, "Idempotency-Key": "dup-source-create-01"})
    assert created.status_code == 201, created.text
    source_id = created.json()["id"]
    published = client.post(f"/api/forms/{source_id}/publish", json={"expected_version": 1}, headers=headers)
    assert published.status_code == 200, published.text

    # A real public response (draft cookie first, like form.html) makes the source immutable.
    assert client.get(f"/api/public/forms/{source_id}/draft").status_code == 200
    submitted = client.post(
        f"/api/public/forms/{source_id}/responses",
        json={"answers": {"full-name": "لیلا پاسخ‌دهنده", "mobile": "09121234567", "city": "تهران"}},
        headers={"Origin": "http://testserver"},
    )
    assert submitted.status_code == 200, submitted.text
    assert client.get(f"/api/forms/{source_id}/responses").json()["total"] == 1
    locked = client.put(f"/api/forms/{source_id}", json={**source_form(), "expected_version": 2}, headers=headers)
    assert locked.status_code == 409, locked.text

    copied = client.post(
        f"/api/forms/{source_id}/duplicate", json={}, headers={**headers, "Idempotency-Key": "dup-copy-key-000001"}
    )
    assert copied.status_code == 201, copied.text
    copy = copied.json()
    assert copy["id"] != source_id
    assert copy["status"] == "draft" and copy["version"] == 1
    assert copy["name"] == "نسخهٔ جدید از ثبت‌نام کارگاه پاییز"
    assert copy["model"] == "registration" and copy["ev"] == "event-dup-01"
    assert copy["slug"] != "workshops/autumn" and copy["slug"].startswith("workshops/autumn-")
    assert [field["id"] for field in copy["fields"]] == ["full-name", "mobile", "city"]
    assert copy["fields"][2]["condField"] == "full-name" and copy["fields"][2]["options"] == ["تهران", "شیراز"]
    assert copy["settings"]["cap"] == 30 and copy["settings"]["wait"] == 5
    assert copy["settings"]["source_form_id"] == source_id and copy["settings"]["source_form_version"] == 2
    assert copy.get("response_count", 0) == 0
    assert client.get(f"/api/forms/{copy['id']}/responses").json()["total"] == 0
    # The copy is a normal draft: editable with expected_version, publishable only through the real checks.
    edited = client.put(
        f"/api/forms/{copy['id']}", json={**source_form(), "name": "نسخهٔ ویرایش‌شده", "expected_version": 1}, headers=headers
    )
    assert edited.status_code == 200, edited.text
    assert client.get(f"/api/public/forms/{copy['id']}").status_code == 404

    # Source is untouched: still published, same version, same single response.
    refreshed = client.get(f"/api/forms/{source_id}").json()
    assert refreshed["status"] == "published" and refreshed["version"] == 2
    assert client.get(f"/api/forms/{source_id}/responses").json()["total"] == 1
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(FormResponseRecord)) == 1
        assert db.scalar(select(func.count()).select_from(FormRecord)) == 2
        assert db.scalar(select(func.count()).select_from(FormFieldRecord).where(FormFieldRecord.form_id == copy["id"])) == 3

    # Same Idempotency-Key -> same copy (200), never a third form.
    retry = client.post(
        f"/api/forms/{source_id}/duplicate", json={}, headers={**headers, "Idempotency-Key": "dup-copy-key-000001"}
    )
    assert retry.status_code == 200 and retry.json()["id"] == copy["id"]
    assert len(client.get("/api/forms").json()["items"]) == 2

    # Optional name; unknown keys refused; missing key -> 428.
    named = client.post(
        f"/api/forms/{source_id}/duplicate", json={"name": "کارگاه زمستان"}, headers={**headers, "Idempotency-Key": "dup-copy-key-000002"}
    )
    assert named.status_code == 201 and named.json()["name"] == "کارگاه زمستان"
    assert client.post(
        f"/api/forms/{source_id}/duplicate", json={"status": "published"}, headers={**headers, "Idempotency-Key": "dup-copy-key-000003"}
    ).status_code == 422
    assert client.post(f"/api/forms/{source_id}/duplicate", json={}, headers=headers).status_code == 428


def test_duplicate_requires_form_permission_csrf_and_ownership(client):
    headers = owner_headers(client)
    created = client.post("/api/forms", json=source_form(), headers={**headers, "Idempotency-Key": "dup-source-create-02"})
    assert created.status_code == 201, created.text
    source_id = created.json()["id"]

    # Missing CSRF/origin -> refused before any copy exists.
    assert client.post(f"/api/forms/{source_id}/duplicate", json={}, headers={"Idempotency-Key": "dup-copy-nocsrf-0001"}).status_code in (401, 403)

    # Unknown / foreign form id -> 404, nothing leaks.
    assert client.post(
        f"/api/forms/{uuid.uuid4()}/duplicate", json={}, headers={**headers, "Idempotency-Key": "dup-copy-foreign-001"}
    ).status_code == 404

    # Member without a role: no fm_create -> 403.
    member_headers = account_headers(client, MEMBER, None)
    denied = client.post(f"/api/forms/{source_id}/duplicate", json={}, headers={**member_headers, "Idempotency-Key": "dup-copy-member-0001"})
    assert denied.status_code == 403, denied.text

    # Manager (fm_create, no finance) may copy a free form; the copy is a draft and publishing stays owner-only.
    manager_headers = account_headers(client, MANAGER, "manager")
    allowed = client.post(f"/api/forms/{source_id}/duplicate", json={}, headers={**manager_headers, "Idempotency-Key": "dup-copy-manager-001"})
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["status"] == "draft"
    assert client.post(
        f"/api/forms/{allowed.json()['id']}/publish", json={"expected_version": 1}, headers=manager_headers
    ).status_code in (401, 403)
    assert len(client.get("/api/forms").json()["items"]) == 2
