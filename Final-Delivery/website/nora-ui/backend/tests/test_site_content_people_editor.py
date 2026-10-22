"""H1 — «اساتید و کارکنان» editor contract on the single ``site_content`` document.

Pins the *real* behaviour the panel editor relies on (no second data source):

* read: ``GET /api/owner/site-content`` (owner session only) returns the **published projection**
  of ``people`` — stored hidden/draft rows are not part of it;
* write: ``PATCH /api/owner/site-content`` ``{content:{people:[...]}, expected_version}`` with
  ``require_owner_write`` (CSRF + Origin) — a manager session is refused;
* people have **no draft state**: every accepted row is public on ``/api/public/site-content`` in the
  same request; rows with hidden/draft flags or without id+name are not stored and are reported in
  ``rejected_rows`` (never a silent save), stored non-public rows survive untouched;
* CAS: stale ``expected_version`` → 409 with ``current_version``; duplicate id → 422;
  other categories are not modified by a ``people``-only save.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import Base, SiteContentRecord  # noqa: E402
from backend.security import hash_password  # noqa: E402

from test_workflows_api import BOT_TOKEN, SERVICE_TOKEN, assign_manager, bale_login, owner_login  # noqa: E402

TEACHER = {
    "id": "pp-teacher-1", "n": "مدرس آزمایشی", "kind": "teacher", "r": "مدرس نجوم", "role2": "", "bio": "زندگی‌نامهٔ عمومی",
    "quote": "", "where": "رصدخانه", "yrs": "۵", "courses": "۳", "rate": "", "tag": "نجوم", "exp": ["رصد"],
    "links": [{"k": "mail", "v": "teacher@example.test"}], "photo": "", "g": "", "form": "", "formTxt": "",
}
STAFF = {"id": "pp-staff-1", "n": "کارمند آزمایشی", "kind": "staff", "r": "هماهنگی"}
EVENT = {"id": "ev-keep", "t": "رویداد موجود", "on": "1405/08/09", "pub": True}


def make_app():
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


def owner_headers(client: TestClient) -> dict[str, str]:
    return {"Origin": "http://testserver", "X-CSRF-Token": client.cookies.get("nora_csrf", "")}


def account_headers(client: TestClient) -> dict[str, str]:
    return {"Origin": "http://testserver", "X-CSRF-Token": client.cookies.get("nora_account_csrf", "")}


def people_ids(payload: dict) -> list[str]:
    return [row["id"] for row in payload["content"]["people"]]


def test_people_editor_reads_published_projection_and_saves_through_the_single_document():
    app, engine = make_app()
    try:
        with TestClient(app) as client:
            # Anonymous / member / manager: no owner read, no owner write.
            assert client.get("/api/owner/site-content").status_code == 401
            manager_id = bale_login(client, 91003)
            assert client.get("/api/owner/site-content").status_code == 401
            client.cookies.clear()
            assign_manager(client, manager_id)
            assert client.get("/api/owner/site-content").status_code == 401
            denied = client.patch("/api/owner/site-content", json={"content": {"people": [TEACHER]}, "expected_version": 0}, headers=account_headers(client))
            assert denied.status_code == 401
            client.cookies.clear()

            owner_login(client)
            empty = client.get("/api/owner/site-content")
            assert empty.status_code == 200 and empty.json()["version"] == 0 and empty.json()["content"]["people"] == []
            # Write without CSRF header → 403 (require_owner_write), nothing stored.
            assert client.patch("/api/owner/site-content", json={"content": {"people": [TEACHER]}, "expected_version": 0}, headers={"Origin": "http://testserver"}).status_code == 403
            # Seed another category first so a people-only save can be shown not to touch it.
            seeded = client.patch("/api/owner/site-content", json={"content": {"events": [EVENT]}, "expected_version": 0}, headers=owner_headers(client))
            assert seeded.status_code == 200 and seeded.json()["version"] == 1
            # A stored hidden person (legacy/direct write) must neither be shown nor destroyed.
            with Session(engine) as db:
                record = db.get(SiteContentRecord, "public")
                content = dict(record.content or {})
                content["people"] = [{"id": "pp-hidden", "n": "فرد پنهان", "kind": "teacher", "hidden": True}]
                record.content = content
                db.commit()
            owner_view = client.get("/api/owner/site-content").json()
            assert people_ids(owner_view) == [] and owner_view["version"] == 1

            # Save two people (editor payload) → version 2, immediately public, nothing else changed.
            saved = client.patch("/api/owner/site-content", json={"content": {"people": [TEACHER, STAFF]}, "expected_version": 1}, headers=owner_headers(client))
            assert saved.status_code == 200, saved.text
            body = saved.json()
            assert body["version"] == 2 and body["rejected_rows"] == {}
            assert people_ids(body) == ["pp-teacher-1", "pp-staff-1"]
            teacher = body["content"]["people"][0]
            assert teacher["kind"] == "teacher" and teacher["r"] == "مدرس نجوم" and teacher["links"] == [{"k": "mail", "v": "mailto:teacher@example.test"}]
            assert body["content"]["people"][1]["kind"] == "staff" and body["content"]["people"][1]["ini"] == "ک"
            assert [row["id"] for row in body["content"]["events"]] == ["ev-keep"]
            public = client.get("/api/public/site-content").json()
            assert people_ids(public) == ["pp-teacher-1", "pp-staff-1"] and public["version"] == 2
            assert "pp-hidden" not in repr(public) and "فرد پنهان" not in repr(body)
            with Session(engine) as db:
                stored = {row["id"]: row for row in db.get(SiteContentRecord, "public").content["people"]}
            assert set(stored) == {"pp-teacher-1", "pp-staff-1", "pp-hidden"} and stored["pp-hidden"]["hidden"] is True

            # Stale version → 409 with the current version; nothing changes.
            stale = client.patch("/api/owner/site-content", json={"content": {"people": [TEACHER]}, "expected_version": 1}, headers=owner_headers(client))
            assert stale.status_code == 409 and stale.json()["detail"] == {"code": "site_content_version_conflict", "current_version": 2}
            # Duplicate id → 422; unknown top-level field → 422; wrong version type → 422; empty object → 422.
            dup = client.patch("/api/owner/site-content", json={"content": {"people": [TEACHER, {**STAFF, "id": "pp-teacher-1"}]}, "expected_version": 2}, headers=owner_headers(client))
            assert dup.status_code == 422 and dup.json()["detail"] == {"code": "duplicate_site_content_id"}
            assert client.patch("/api/owner/site-content", json={"content": {"staff": []}, "expected_version": 2}, headers=owner_headers(client)).status_code == 422
            assert client.patch("/api/owner/site-content", json={"content": {"people": []}, "expected_version": "2"}, headers=owner_headers(client)).status_code == 422
            assert client.patch("/api/owner/site-content", json={"content": {}, "expected_version": 2}, headers=owner_headers(client)).status_code == 422
            assert client.patch("/api/owner/site-content", json={"content": {"people": "x"}, "expected_version": 2}, headers=owner_headers(client)).status_code == 422
            assert client.get("/api/owner/site-content").json()["version"] == 2

            # No draft state for people: hidden / draft / nameless rows are NOT stored and are reported,
            # the rest of the payload is saved. A hidden flag on an existing public id removes it from
            # the public list (it is not kept as a hidden copy) — the editor must not offer «hide».
            mixed = client.patch("/api/owner/site-content", json={"content": {"people": [
                TEACHER,
                {**STAFF, "hidden": True},
                {"id": "pp-draft", "n": "پیش‌نویس", "status": "draft"},
                {"id": "pp-noname", "kind": "staff"},
                "garbage",
            ]}, "expected_version": 2}, headers=owner_headers(client))
            assert mixed.status_code == 200, mixed.text
            result = mixed.json()
            assert result["version"] == 3 and people_ids(result) == ["pp-teacher-1"]
            assert result["rejected_rows"] == {"people": [
                {"index": 1, "id": "pp-staff-1", "reason": "non_public"},
                {"index": 2, "id": "pp-draft", "reason": "non_public"},
                {"index": 3, "id": "pp-noname", "reason": "missing_required_fields"},
                {"index": 4, "id": "", "reason": "invalid_row"},
            ]}
            assert people_ids(client.get("/api/public/site-content").json()) == ["pp-teacher-1"]
            with Session(engine) as db:
                stored = {row["id"] for row in db.get(SiteContentRecord, "public").content["people"]}
            assert stored == {"pp-teacher-1", "pp-hidden"}  # legacy hidden row still retained

            # Removal = omit the id; an empty list clears the public roster but never the hidden legacy row.
            cleared = client.patch("/api/owner/site-content", json={"content": {"people": []}, "expected_version": 3}, headers=owner_headers(client))
            assert cleared.status_code == 200 and cleared.json()["version"] == 4 and people_ids(cleared.json()) == []
            with Session(engine) as db:
                content = db.get(SiteContentRecord, "public").content
            assert [row["id"] for row in content["people"]] == ["pp-hidden"] and [row["id"] for row in content["events"]] == ["ev-keep"]
            # Private contact fields never enter the document through the person sanitiser.
            leaky = client.patch("/api/owner/site-content", json={"content": {"people": [{**TEACHER, "mobile": "09120000000", "email": "p@example.test", "token": "x"}]}, "expected_version": 4}, headers=owner_headers(client))
            assert leaky.status_code == 200 and "0912" not in repr(leaky.json()) and "p@example.test" not in repr(leaky.json())
            with Session(engine) as db:
                assert "0912" not in repr(db.get(SiteContentRecord, "public").content["people"])
    finally:
        engine.dispose()
