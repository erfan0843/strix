"""Stored non-public partner rows must never leak publicly and must survive owner-panel saves.

The owner panel only sees and sends the published projection of ``partners``; a category
replace must therefore not destroy rows the panel could never have intended to touch.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
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

NON_PUBLIC = [
    {"id": "np-private", "n": "نهاد خصوصی (دادهٔ تست)", "privacy": "private"},
    {"id": "np-hidden", "n": "نهاد پنهان (دادهٔ تست)", "hidden": True},
    {"id": "np-paused", "n": "نهاد متوقف (دادهٔ تست)", "status": "paused"},
    {"id": "np-pending", "n": "نهاد منتظر (دادهٔ تست)", "pend": True},
    {"id": "np-unpublished", "n": "نهاد منتشرنشده (دادهٔ تست)", "pub": False},
]
NON_PUBLIC_IDS = [row["id"] for row in NON_PUBLIC]
OTHER_CONTENT = {
    "events": [{"id": "ev-1", "t": "رویداد آزمایشی", "d": "۱۴۰۵/۰۸/۰۵", "partnerId": "p-1", "pub": True}],
    "people": [{"id": "pp-1", "n": "مدرس آزمایشی", "kind": "tch", "pub": True}],
    "articles": [{"id": "ar-1", "t": "مطلب آزمایشی", "pub": True}],
    "banners": [{"id": "bn-1", "t": "بنر آزمایشی", "status": "published", "active": True}],
    "library": [],
    "cooperation": [],
}


@pytest.fixture
def env():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"),
        session_ttl_seconds=3600,
        cookie_secure=False,
        bale_bot_username="nora_test_bot",
        bot_service_token="site-content-test-service-token-0123456789",
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


def login(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": "nora-owner", "password": "correct-horse-staple-42"},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200, response.text
    return {"Origin": "http://testserver", "X-CSRF-Token": client.cookies.get("nora_csrf", "")}


def stored(engine) -> dict[str, Any]:
    with Session(engine) as db:
        record = db.get(SiteContentRecord, "public")
        assert record is not None
        return {"content": dict(record.content or {}), "version": record.version}


def inject_non_public(engine) -> None:
    """Simulate rows that reached storage outside the owner API (legacy data, direct DB edits)."""
    with Session(engine) as db:
        record = db.get(SiteContentRecord, "public")
        assert record is not None
        content = dict(record.content or {})
        content["partners"] = list(content.get("partners") or []) + [dict(row) for row in NON_PUBLIC]
        record.content = content
        db.commit()


def public_partner_ids(client: TestClient) -> list[str]:
    response = client.get("/api/public/site-content")
    assert response.status_code == 200, response.text
    return [row["id"] for row in response.json()["content"]["partners"]]


def owner_partners(client: TestClient) -> tuple[list[dict[str, Any]], int]:
    response = client.get("/api/owner/site-content")
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload["content"]["partners"], payload["version"]


def patch_partners(client: TestClient, headers: dict[str, str], rows: list[dict[str, Any]], version: int):
    return client.patch(
        "/api/owner/site-content",
        json={"content": {"partners": rows}, "expected_version": version},
        headers=headers,
    )


def test_stored_non_public_partners_stay_private_and_survive_panel_operations(env):
    client, engine = env
    headers = login(client)
    public_rows = [
        {"id": "p-1", "n": "نهاد یک (دادهٔ تست)", "type": "فرهنگی", "pub": True},
        {"id": "p-2", "n": "نهاد دو (دادهٔ تست)", "type": "آموزشی", "pub": True},
    ]
    first = client.patch(
        "/api/owner/site-content",
        json={"content": {**OTHER_CONTENT, "partners": public_rows}, "expected_version": 0},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    inject_non_public(engine)
    assert set(NON_PUBLIC_IDS) <= {row["id"] for row in stored(engine)["content"]["partners"]}
    others_before = {key: stored(engine)["content"][key] for key in OTHER_CONTENT}

    # read boundary: stored flagged rows are invisible to the public API, the owner view and SEO
    assert public_partner_ids(client) == ["p-1", "p-2"]
    rows, version = owner_partners(client)
    assert [row["id"] for row in rows] == ["p-1", "p-2"]
    for partner_id in NON_PUBLIC_IDS:
        page = client.get(f"/partner.html?id={partner_id}")
        assert page.status_code == 404, partner_id
        assert "دادهٔ تست" not in page.text

    def panel_save(new_rows: list[dict[str, Any]], expected: int, label: str) -> int:
        response = patch_partners(client, headers, new_rows, expected)
        assert response.status_code == 200, f"{label}: {response.text}"
        record = stored(engine)
        kept = {row["id"]: row for row in record["content"]["partners"]}
        for row in NON_PUBLIC:
            assert row["id"] in kept, f"{label}: non-public row {row['id']} was deleted"
            for key, value in row.items():
                assert kept[row["id"]][key] == value, f"{label}: {row['id']}.{key} changed"
        assert public_partner_ids(client) == [row["id"] for row in new_rows], label
        assert [row["id"] for row in owner_partners(client)[0]] == [row["id"] for row in new_rows], label
        for key, before in others_before.items():
            assert record["content"][key] == before, f"{label}: category {key} changed"
        return record["version"]

    # 1) add
    version = panel_save(public_rows + [{"id": "p-3", "n": "نهاد سه (دادهٔ تست)", "pub": True}], version, "add")
    # 2) edit
    edited = [dict(row) for row in public_rows] + [{"id": "p-3", "n": "نهاد سه (ویرایش‌شده)", "pub": True}]
    version = panel_save(edited, version, "edit")
    # 3) reorder
    reordered = [edited[2], edited[0], edited[1]]
    version = panel_save(reordered, version, "reorder")
    # 4) delete a published partner
    version = panel_save([reordered[0], reordered[2]], version, "delete")
    assert "p-1" not in public_partner_ids(client)
    assert stored(engine)["content"]["events"][0]["partnerId"] == "p-1"  # related event untouched

    # 5) stale expected_version → 409, nothing written, retry on the fresh version succeeds
    before = stored(engine)
    stale = patch_partners(client, headers, [reordered[0]], version - 1)
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["current_version"] == version
    assert stored(engine) == before
    assert public_partner_ids(client) == ["p-3", "p-2"]
    version = panel_save([reordered[0]], version, "retry-after-409")

    # 6) an explicit row with the same id as a stored non-public row replaces it (intentional publish)
    response = patch_partners(client, headers, [reordered[0], {"id": "np-paused", "n": "نهاد متوقف → منتشر", "pub": True}], version)
    assert response.status_code == 200, response.text
    kept = {row["id"]: row for row in stored(engine)["content"]["partners"]}
    assert kept["np-paused"]["n"] == "نهاد متوقف → منتشر" and "status" not in kept["np-paused"]
    assert set(NON_PUBLIC_IDS) - {"np-paused"} <= set(kept)
    assert public_partner_ids(client) == ["p-3", "np-paused"]


def test_non_public_partner_rows_cannot_be_created_through_the_owner_api(env):
    client, _engine = env
    headers = login(client)
    response = client.patch(
        "/api/owner/site-content",
        json={"content": {**OTHER_CONTENT, "partners": [
            {"id": "p-1", "n": "نهاد یک (دادهٔ تست)", "pub": True}, *NON_PUBLIC,
        ]}, "expected_version": 0},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert public_partner_ids(client) == ["p-1"]
    assert [row["id"] for row in response.json()["content"]["partners"]] == ["p-1"]
