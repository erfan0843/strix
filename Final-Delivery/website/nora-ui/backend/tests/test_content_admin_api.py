"""Record-level event/article management on top of ``site_content``.

In-memory SQLite only. Covers: owner and permitted manager can create/edit/publish,
plain member and anonymous cannot, drafts never reach the public projection,
status lifecycle + version conflicts, audit rows without record bodies.
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

from backend import content_admin  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import Base, SiteContentRecord  # noqa: E402
from backend.security import hash_password  # noqa: E402
from backend.site_content import public_site_content  # noqa: E402

from test_workflows_api import (  # noqa: E402
    BOT_TOKEN,
    SERVICE_TOKEN,
    account_write_headers,
    assign_manager,
    bale_login,
    owner_login,
    owner_write_headers,
)


def content_app():
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


def stored_rows(engine, kind: str) -> list[dict]:
    with Session(engine) as db:
        record = db.get(SiteContentRecord, "public")
        return list((record.content or {}).get(kind) or []) if record else []


EVENT = {
    "t": "کارگاه نگارش علمی",
    "kind": "کارگاه",
    "d": "یک روز تمرین نگارش مقاله.",
    "on": "۱۴۰۵/۰۸/۱۲",
    "time": "۱۰ تا ۱۳",
    "place": "سالن اصلی",
    "mode": "حضوری",
    "price": "250000",
    "cap": 40,
    "tags": ["نگارش", "پژوهش"],
    "cert": True,
    "certMin": 80,
}


def test_lifecycle_owner_create_edit_publish_pause_archive_and_public_projection():
    app, engine = content_app()
    try:
        with TestClient(app) as client:
            owner_login(client)
            empty = client.get("/api/admin/content/events")
            assert empty.status_code == 200
            assert empty.json()["items"] == [] and empty.json()["version"] == 0
            assert empty.json()["can_edit"] is True and empty.json()["can_publish"] is True

            created = client.post(
                "/api/admin/content/events",
                json={"record": EVENT, "expected_version": 0},
                headers=owner_write_headers(client),
            )
            assert created.status_code == 200, created.text
            body = created.json()
            record_id = body["record"]["id"]
            assert body["saved"] is True and body["version"] == 1
            assert body["record"]["status"] == "draft"
            assert body["record"]["on"] == "1405/08/12"
            assert body["record"]["price"] == 250000
            assert body["record"]["public_path"] == ""

            # Drafts are stored in the same document but never projected publicly.
            assert [row["id"] for row in stored_rows(engine, "events")] == [record_id]
            assert client.get("/api/public/site-content").json()["content"]["events"] == []
            assert public_site_content({"events": stored_rows(engine, "events")})["events"] == []

            # Stale version is rejected, nothing changes.
            stale = client.put(
                f"/api/admin/content/events/{record_id}",
                json={"record": {"t": "تغییر"}, "expected_version": 0},
                headers=owner_write_headers(client),
            )
            assert stale.status_code == 409
            assert stale.json()["detail"]["current_version"] == 1

            edited = client.put(
                f"/api/admin/content/events/{record_id}",
                json={"record": {"t": "کارگاه نگارش علمی (ویرایش)", "cap": 50}, "expected_version": 1},
                headers=owner_write_headers(client),
            )
            assert edited.status_code == 200, edited.text
            assert edited.json()["record"]["t"] == "کارگاه نگارش علمی (ویرایش)"
            assert edited.json()["record"]["cap"] == 50
            assert edited.json()["record"]["place"] == "سالن اصلی"  # untouched fields preserved
            assert edited.json()["record"]["status"] == "draft"

            published = client.post(
                f"/api/admin/content/events/{record_id}/status",
                json={"status": "published", "expected_version": 2},
                headers=owner_write_headers(client),
            )
            assert published.status_code == 200, published.text
            assert published.json()["record"]["status"] == "published"
            assert published.json()["record"]["public_path"] == f"event.html?id={record_id}"
            public = client.get("/api/public/site-content").json()["content"]["events"]
            assert [row["id"] for row in public] == [record_id]
            assert public[0]["t"] == "کارگاه نگارش علمی (ویرایش)"
            assert "status" not in public[0] or public[0]["status"] == "published"

            # Invalid transition published -> draft is rejected.
            bad = client.post(
                f"/api/admin/content/events/{record_id}/status",
                json={"status": "draft", "expected_version": 3},
                headers=owner_write_headers(client),
            )
            assert bad.status_code == 422
            assert bad.json()["detail"]["code"] == "invalid_status_transition"

            paused = client.post(
                f"/api/admin/content/events/{record_id}/status",
                json={"status": "paused", "expected_version": 3},
                headers=owner_write_headers(client),
            )
            assert paused.status_code == 200
            assert client.get("/api/public/site-content").json()["content"]["events"] == []

            archived = client.post(
                f"/api/admin/content/events/{record_id}/status",
                json={"status": "archived", "expected_version": 4},
                headers=owner_write_headers(client),
            )
            assert archived.status_code == 200
            # Archive never deletes.
            assert [row["id"] for row in stored_rows(engine, "events")] == [record_id]
            listing = client.get("/api/admin/content/events?status=archived")
            assert listing.json()["total"] == 1
            assert listing.json()["counts"] == {"draft": 0, "published": 0, "paused": 0, "archived": 1}

            restored = client.post(
                f"/api/admin/content/events/{record_id}/status",
                json={"status": "draft", "expected_version": 5},
                headers=owner_write_headers(client),
            )
            assert restored.status_code == 200
            assert restored.json()["record"]["status"] == "draft"

            # Audit trail carries only titles/statuses, never the record body.
            trail = client.get("/api/owner/audit?action=content.")
            actions = [item["action"] for item in trail.json()["items"]]
            assert actions == ["content.status"] * 4 + ["content.update", "content.create"]
            assert trail.json()["items"][0]["details"]["from"] == "archived"
            assert trail.json()["items"][0]["target_id"] == record_id
            assert "d" not in trail.json()["items"][-1]["details"]
    finally:
        engine.dispose()


def test_validation_errors_are_field_specific_and_do_not_persist():
    app, engine = content_app()
    try:
        with TestClient(app) as client:
            owner_login(client)
            cases = [
                ({"t": ""}, "title_required", "t"),
                ({"t": "x", "on": "1405/13/01"}, "invalid_jalali_date", "on"),
                ({"t": "x"}, "date_required", "on"),
                ({"t": "x", "on": "1405/01/01", "price": -1}, "invalid_number", "price"),
                ({"t": "x", "on": "1405/01/01", "poster": "javascript:alert(1)"}, "invalid_image", "poster"),
                ({"t": "x", "on": "1405/01/01", "secret": "y"}, "unexpected_record_fields", "secret"),
            ]
            for record, code, field in cases:
                response = client.post(
                    "/api/admin/content/events",
                    json={"record": record, "expected_version": 0},
                    headers=owner_write_headers(client),
                )
                assert response.status_code == 422, (record, response.text)
                assert response.json()["detail"] == {"code": code, "field": field}
            assert stored_rows(engine, "events") == []
            assert client.get("/api/admin/content/events").json()["version"] == 0

            # Publishing straight away requires a description for events.
            response = client.post(
                "/api/admin/content/events",
                json={"record": {"t": "x", "on": "1405/01/01"}, "expected_version": 0, "status": "published"},
                headers=owner_write_headers(client),
            )
            assert response.status_code == 422
            assert response.json()["detail"]["code"] == "event_description_required"

            # Unknown kind and unknown id are 404 without leaking anything.
            assert client.get("/api/admin/content/people").status_code == 404
            assert client.get("/api/admin/content/events/does-not-exist").status_code == 404
            assert client.get("/api/admin/content/events/../etc").status_code in {404, 422}
    finally:
        engine.dispose()


def test_articles_lifecycle_and_search_sort_pagination():
    app, engine = content_app()
    try:
        with TestClient(app) as client:
            owner_login(client)
            version = 0
            ids = []
            for index in range(3):
                response = client.post(
                    "/api/admin/content/articles",
                    json={
                        "record": {
                            "t": f"مطلب شماره {index}",
                            "cat": "آموزش" if index else "اخبار",
                            "lead": "لید",
                            "body": "بند اول\n\nبند دوم",
                            "at": "2026-10-2%d" % index,
                            "tags": ["t%d" % index],
                        },
                        "expected_version": version,
                        "status": "published" if index == 1 else "draft",
                    },
                    headers=owner_write_headers(client),
                )
                assert response.status_code == 200, response.text
                version = response.json()["version"]
                ids.append(response.json()["record"]["id"])
            body = client.get("/api/admin/content/articles?limit=2&sort=date&order=asc").json()
            assert body["total"] == 3 and body["has_more"] is True
            assert [item["t"] for item in body["items"]] == ["مطلب شماره 0", "مطلب شماره 1"]
            assert body["items"][0]["paragraphs"] == 2
            page2 = client.get("/api/admin/content/articles?limit=2&offset=2&sort=date&order=asc").json()
            assert [item["t"] for item in page2["items"]] == ["مطلب شماره 2"]
            search = client.get("/api/admin/content/articles?q=اخبار").json()
            assert [item["id"] for item in search["items"]] == [ids[0]]
            published = client.get("/api/admin/content/articles?status=published").json()
            assert [item["id"] for item in published["items"]] == [ids[1]]
            public = client.get("/api/public/site-content").json()["content"]["articles"]
            assert [row["id"] for row in public] == [ids[1]]
            assert public[0]["body"] == ["بند اول", "بند دوم"]
            assert public[0]["pub"] is True

            # An article without body cannot be published.
            response = client.post(
                "/api/admin/content/articles",
                json={"record": {"t": "خالی"}, "expected_version": version, "status": "published"},
                headers=owner_write_headers(client),
            )
            assert response.status_code == 422
            assert response.json()["detail"]["code"] == "article_body_required"
    finally:
        engine.dispose()


def test_manager_permissions_member_and_anonymous_are_rejected():
    app, engine = content_app()
    try:
        with TestClient(app) as client:
            # Anonymous.
            assert client.get("/api/admin/content/events").status_code == 401
            # Plain member with its own CSRF.
            member_id = bale_login(client, 81001)
            assert client.get("/api/admin/content/events").status_code == 403
            denied = client.post(
                "/api/admin/content/events",
                json={"record": EVENT, "expected_version": 0},
                headers=account_write_headers(client),
            )
            assert denied.status_code == 403
            assert stored_rows(engine, "events") == []
            client.cookies.clear()

            # Manager (ev_create + ev_publish) can create, edit and publish; CSRF required.
            manager_id = bale_login(client, 81002)
            assert manager_id != member_id
            assign_manager(client, manager_id)
            listing = client.get("/api/admin/content/events")
            assert listing.status_code == 200
            assert listing.json()["can_edit"] is True and listing.json()["can_publish"] is True
            no_csrf = client.post(
                "/api/admin/content/events",
                json={"record": EVENT, "expected_version": 0},
                headers={"Origin": "http://testserver"},
            )
            assert no_csrf.status_code == 403
            created = client.post(
                "/api/admin/content/events",
                json={"record": EVENT, "expected_version": 0},
                headers=account_write_headers(client),
            )
            assert created.status_code == 200, created.text
            record_id = created.json()["record"]["id"]
            published = client.post(
                f"/api/admin/content/events/{record_id}/status",
                json={"status": "published", "expected_version": 1},
                headers=account_write_headers(client),
            )
            assert published.status_code == 200, published.text
            client.cookies.clear()

            # Another plain member still sees nothing through the admin API, and the
            # public site shows exactly the published record.
            bale_login(client, 81003)
            assert client.get(f"/api/admin/content/events/{record_id}").status_code == 403
            public = client.get("/api/public/site-content").json()["content"]["events"]
            assert [row["id"] for row in public] == [record_id]

            # Audit rows name the manager account as actor.
            client.cookies.clear()
            owner_login(client)
            trail = client.get("/api/owner/audit?action=content.").json()["items"]
            assert {item["actor_id"] for item in trail} == {manager_id}
            assert {item["actor_kind"] for item in trail} == {"account"}
    finally:
        engine.dispose()


def test_legacy_rows_keep_working_and_whole_category_patch_retains_drafts():
    """Rows stored by the old whole-category PATCH have no ``status``; drafts survive a PATCH."""
    app, engine = content_app()
    try:
        with TestClient(app) as client:
            owner_login(client)
            legacy = client.patch(
                "/api/owner/site-content",
                json={
                    "content": {
                        "events": [{"id": "legacy-1", "t": "رویداد قدیمی", "d": "شرح", "when": "آبان", "on": "1405/08/01"}],
                        "articles": [{"id": "legacy-a", "t": "مطلب قدیمی", "lead": "لید", "pub": True}],
                    },
                    "expected_version": 0,
                },
                headers=owner_write_headers(client),
            )
            assert legacy.status_code == 200, legacy.text
            listing = client.get("/api/admin/content/events").json()
            assert listing["items"][0]["status"] == "published"
            assert client.get("/api/admin/content/articles").json()["items"][0]["status"] == "published"

            draft = client.post(
                "/api/admin/content/events",
                json={"record": EVENT, "expected_version": 1},
                headers=owner_write_headers(client),
            )
            assert draft.status_code == 200
            draft_id = draft.json()["record"]["id"]

            # A whole-category PATCH from the owner panel (which only sees public rows)
            # must not destroy the draft.
            patched = client.patch(
                "/api/owner/site-content",
                json={
                    "content": {"events": [{"id": "legacy-1", "t": "رویداد قدیمی ۲", "d": "شرح", "on": "1405/08/01"}]},
                    "expected_version": 2,
                },
                headers=owner_write_headers(client),
            )
            assert patched.status_code == 200, patched.text
            ids = {row["id"]: content_admin.status_of(row) for row in stored_rows(engine, "events")}
            assert ids == {"legacy-1": "published", draft_id: "draft"}

            # Pausing a legacy row works and removes it from the public projection.
            paused = client.post(
                "/api/admin/content/events/legacy-1/status",
                json={"status": "paused", "expected_version": 3},
                headers=owner_write_headers(client),
            )
            assert paused.status_code == 200, paused.text
            assert client.get("/api/public/site-content").json()["content"]["events"] == []
    finally:
        engine.dispose()


def test_status_of_and_public_filter_agree_for_every_lifecycle_status():
    for status in content_admin.STATUSES:
        row = {"id": "x", "t": "t", "d": "d", "on": "1405/01/01", "status": status}
        assert content_admin.status_of(row) == status
        assert (public_site_content({"events": [row]})["events"] != []) is (status == "published")
    assert content_admin.status_of({"id": "x", "t": "t", "hidden": True}) == "draft"
    assert content_admin.status_of({"id": "x", "t": "t", "pub": False}) == "draft"
    assert content_admin.status_of({"id": "x", "t": "t"}) == "published"


def test_event_and_article_person_or_partner_references_must_exist_in_the_same_document():
    """B1 of the owner-panel audit (2026-10-22): ``tchr``/``partnerId`` are *ids* into the
    ``people``/``partners`` categories of the same ``site_content`` document. A well-formed but
    unknown id used to be accepted, leaving the public page with a dangling instructor/partner
    link. Existing rows that already carry a stale id must still change status (no data lock-in)."""
    app, engine = content_app()
    try:
        with TestClient(app) as client:
            owner_login(client)
            # Seed one person and one partner through the real owner document route.
            person = {"id": "pp-teacher-1", "n": "مدرس آزمایشی", "kind": "teacher", "r": "مدرس نجوم"}
            partner = {"id": "pt-uni-1", "n": "دانشگاه آزمایشی", "pub": True}
            seeded = client.patch(
                "/api/owner/site-content",
                json={"content": {"people": [person], "partners": [partner]}, "expected_version": 0},
                headers=owner_write_headers(client),
            )
            assert seeded.status_code == 200, seeded.text
            version = seeded.json()["version"]

            def post(kind, record, status="draft"):
                return client.post(
                    f"/api/admin/content/{kind}",
                    json={"record": record, "expected_version": version, "status": status},
                    headers=owner_write_headers(client),
                )

            # Unknown but well-formed ids → 422 on the exact field, nothing stored.
            for kind, record, field in (
                ("events", dict(EVENT, tchr="pp-nobody"), "tchr"),
                ("events", dict(EVENT, partnerId="pt-nobody"), "partnerId"),
                ("articles", {"t": "مطلب", "tchr": "pp-nobody"}, "tchr"),
            ):
                response = post(kind, record)
                assert response.status_code == 422, (kind, field, response.text)
                assert response.json()["detail"] == {"code": "unknown_reference", "field": field}
            assert stored_rows(engine, "events") == [] and stored_rows(engine, "articles") == []

            # Known ids are accepted and stored as given; empty clears the link.
            created = post("events", dict(EVENT, tchr="pp-teacher-1", partnerId="pt-uni-1"))
            assert created.status_code == 200, created.text
            event_id = created.json()["record"]["id"]
            version = created.json()["version"]
            row = stored_rows(engine, "events")[0]
            assert row["tchr"] == "pp-teacher-1" and row["partnerId"] == "pt-uni-1"
            article = post("articles", {"t": "مطلب", "tchr": "pp-teacher-1"})
            assert article.status_code == 200, article.text
            version = article.json()["version"]

            # Editing to an unknown id is refused too (merge path), the stored link survives.
            bad_edit = client.put(
                f"/api/admin/content/events/{event_id}",
                json={"record": {"tchr": "pp-ghost"}, "expected_version": version},
                headers=owner_write_headers(client),
            )
            assert bad_edit.status_code == 422 and bad_edit.json()["detail"]["field"] == "tchr"
            assert stored_rows(engine, "events")[0]["tchr"] == "pp-teacher-1"
            cleared = client.put(
                f"/api/admin/content/events/{event_id}",
                json={"record": {"tchr": ""}, "expected_version": version},
                headers=owner_write_headers(client),
            )
            assert cleared.status_code == 200, cleared.text
            version = cleared.json()["version"]
            assert not stored_rows(engine, "events")[0].get("tchr")

            # A legacy row with a stale id (written before this rule) still moves through the lifecycle.
            with Session(engine) as db:
                record = db.get(SiteContentRecord, "public")
                content = dict(record.content or {})
                rows = list(content["events"])
                rows[0] = dict(rows[0], tchr="pp-legacy-gone")
                content["events"] = rows
                record.content = content
                db.commit()
            published = client.post(
                f"/api/admin/content/events/{event_id}/status",
                json={"status": "published", "expected_version": version},
                headers=owner_write_headers(client),
            )
            assert published.status_code == 200, published.text
            assert stored_rows(engine, "events")[0]["tchr"] == "pp-legacy-gone"
    finally:
        engine.dispose()
