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
            # Stage 2 (pickers): list summaries carry the reference ids so the panel can show the
            # linked person/partner state per row without opening every record.
            listed_event = client.get("/api/admin/content/events").json()["items"][0]
            assert listed_event["tchr"] == "pp-teacher-1" and listed_event["partnerId"] == "pt-uni-1"
            assert client.get("/api/admin/content/articles").json()["items"][0]["tchr"] == "pp-teacher-1"

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


def test_people_or_partners_referenced_by_events_cannot_be_removed_from_the_document():
    """H1 of the owner-panel work (2026-10-22): the people editor replaces the whole ``people``
    category through ``PATCH /api/owner/site-content``. Dropping a row that an event/article still
    points at (``tchr``/``partnerId``) would leave the same dangling link B1 forbids on the other
    side, so the server refuses it with the referencing rows named. Editing a row in place, removing
    an unreferenced row, and ids that never existed in ``people`` are unaffected."""
    app, engine = content_app()
    try:
        with TestClient(app) as client:
            owner_login(client)
            people = [
                {"id": "pp-used", "n": "مدرس وصل‌شده", "kind": "teacher", "r": "مدرس"},
                {"id": "pp-free", "n": "مدرس آزاد", "kind": "teacher", "r": "مدرس"},
            ]
            partners = [{"id": "pt-used", "n": "نهاد وصل‌شده", "pub": True}, {"id": "pt-free", "n": "نهاد آزاد", "pub": True}]
            seeded = client.patch(
                "/api/owner/site-content",
                json={"content": {"people": people, "partners": partners}, "expected_version": 0},
                headers=owner_write_headers(client),
            )
            assert seeded.status_code == 200, seeded.text
            version = seeded.json()["version"]
            created = client.post(
                "/api/admin/content/events",
                json={"record": dict(EVENT, tchr="pp-used", partnerId="pt-used"), "expected_version": version, "status": "draft"},
                headers=owner_write_headers(client),
            )
            assert created.status_code == 200, created.text
            event_id = created.json()["record"]["id"]
            version = created.json()["version"]
            article = client.post(
                "/api/admin/content/articles",
                json={"record": {"t": "مطلب", "tchr": "pp-used"}, "expected_version": version, "status": "draft"},
                headers=owner_write_headers(client),
            )
            assert article.status_code == 200, article.text
            version = article.json()["version"]

            def patch(content):
                return client.patch(
                    "/api/owner/site-content",
                    json={"content": content, "expected_version": version},
                    headers=owner_write_headers(client),
                )

            # Dropping the referenced person (draft event + draft article both point at it) → 422 naming them.
            refused = patch({"people": [people[1]]})
            assert refused.status_code == 422, refused.text
            detail = refused.json()["detail"]
            assert detail["code"] == "reference_in_use" and detail["field"] == "people"
            assert detail["ids"] == ["pp-used"]
            used_by = {(item["kind"], item["id"]) for item in detail["used_by"]}
            assert ("events", event_id) in used_by and len(used_by) == 2
            assert all(item["ref"] == "pp-used" for item in detail["used_by"])
            assert [row["id"] for row in stored_rows(engine, "people")] == ["pp-used", "pp-free"]

            # Same rule for partners.
            refused_partner = patch({"partners": [partners[1]]})
            assert refused_partner.status_code == 422, refused_partner.text
            assert refused_partner.json()["detail"]["code"] == "reference_in_use"
            assert refused_partner.json()["detail"]["field"] == "partners"
            assert refused_partner.json()["detail"]["ids"] == ["pt-used"]

            # Editing the referenced row in place and dropping the free one is fine; version moves on.
            edited = patch({"people": [dict(people[0], r="مدرس ارشد")]})
            assert edited.status_code == 200, edited.text
            assert edited.json()["rejected_rows"] == {}
            version = edited.json()["version"]
            rows = stored_rows(engine, "people")
            assert [row["id"] for row in rows] == ["pp-used"] and rows[0]["r"] == "مدرس ارشد"
            assert stored_rows(engine, "events")[0]["tchr"] == "pp-used"

            # Rows the sanitiser cannot publish are still reported, never silently "saved".
            partial = patch({"people": [people[0], {"n": "بی‌شناسه"}, {"id": "pp-hidden", "n": "پنهان", "hidden": True}]})
            assert partial.status_code == 200, partial.text
            reasons = {item["reason"] for item in partial.json()["rejected_rows"]["people"]}
            assert reasons == {"missing_required_fields", "non_public"}
            version = partial.json()["version"]
            assert [row["id"] for row in stored_rows(engine, "people")] == ["pp-used"]

            # Stale ids that never existed in ``people`` do not lock the category.
            with Session(engine) as db:
                record = db.get(SiteContentRecord, "public")
                content = dict(record.content or {})
                rows = list(content["events"])
                rows[0] = dict(rows[0], tchr="pp-legacy-gone")
                content["events"] = rows
                record.content = content
                db.commit()
            still_ok = patch({"people": [dict(people[0], r="مدرس")]})
            assert still_ok.status_code == 200, still_ok.text
    finally:
        engine.dispose()


def test_event_parts_sessions_are_editable_validated_and_projected_publicly():
    """ممیزی پنل ۱۴۰۵/۰۸/۰۱ ردیف B9: جلسه‌های رویداد (``parts``) از پنل قابل ویرایش‌اند، سرور شکل و اندازهٔ آن‌ها
    را می‌سنجد و صفحهٔ عمومی همان فهرست را می‌خواند؛ مقدار نامعتبر ۴۲۲ فیلدی می‌دهد و چیزی ذخیره نمی‌کند."""
    app, engine = content_app()
    try:
        with TestClient(app) as client:
            owner_login(client)
            parts = [
                {"title": "جلسهٔ نخست", "date": "۱۴۰۵/۰۸/۱۲", "time": "۱۰:۰۰", "to": "۱۲:۰۰", "description": "آشنایی"},
                {"title": "", "date": "1405/08/19", "time": "10:00", "to": "", "description": ""},
                {"title": "", "date": "", "time": "", "to": "", "description": ""},
            ]
            created = client.post(
                "/api/admin/content/events",
                json={"record": {**EVENT, "parts": parts}, "expected_version": 0},
                headers=owner_write_headers(client),
            )
            assert created.status_code == 200, created.text
            record_id = created.json()["record"]["id"]
            stored = created.json()["record"]["parts"]
            assert len(stored) == 2, "ردیف کاملاً خالی ذخیره نمی‌شود"
            assert stored[0]["title"] == "جلسهٔ نخست" and stored[0]["to"] == "۱۲:۰۰"
            assert stored[1]["date"] == "1405/08/19" and stored[1]["title"] == ""

            detail = client.get(f"/api/admin/content/events/{record_id}")
            assert detail.status_code == 200 and detail.json()["record"]["parts"] == stored

            for bad in ("متن", [1], [{"title": "x", "unknown": "y"}], [{"title": 5}], [{"title": "a"}] * 81):
                rejected = client.put(
                    f"/api/admin/content/events/{record_id}",
                    json={"record": {"parts": bad}, "expected_version": 1},
                    headers=owner_write_headers(client),
                )
                assert rejected.status_code == 422, (bad, rejected.text)
                assert rejected.json()["detail"]["code"] == "invalid_parts"
                assert rejected.json()["detail"]["field"] == "parts"
            assert client.get(f"/api/admin/content/events/{record_id}").json()["record"]["parts"] == stored

            cleared = client.put(
                f"/api/admin/content/events/{record_id}",
                json={"record": {"parts": []}, "expected_version": 1},
                headers=owner_write_headers(client),
            )
            assert cleared.status_code == 200 and cleared.json()["record"]["parts"] == []

            restored = client.put(
                f"/api/admin/content/events/{record_id}",
                json={"record": {"parts": parts[:1]}, "expected_version": 2},
                headers=owner_write_headers(client),
            )
            assert restored.status_code == 200
            published = client.post(
                f"/api/admin/content/events/{record_id}/status",
                json={"status": "published", "expected_version": 3},
                headers=owner_write_headers(client),
            )
            assert published.status_code == 200, published.text
            public = client.get("/api/public/site-content").json()["content"]["events"]
            assert [row["id"] for row in public] == [record_id]
            assert public[0]["parts"] == [
                {"title": "جلسهٔ نخست", "date": "۱۴۰۵/۰۸/۱۲", "time": "۱۰:۰۰", "to": "۱۲:۰۰", "description": "آشنایی"}
            ]
    finally:
        engine.dispose()


def test_legacy_event_parts_with_alias_keys_survive_status_changes():
    """ردیف قدیمی با ``parts`` رشته‌ای یا کلیدهای مستعار (``n``/``d``) باید بدون ۴۲۲ منتشر شود؛ سخت‌گیری فقط روی ورودی تازه است."""
    app, engine = content_app()
    try:
        with Session(engine) as session:
            session.add(SiteContentRecord(id="public", content={"events": [{
                "id": "legacy-parts", "t": "رویداد قدیمی", "on": "1405/09/01", "d": "شرح", "pub": True, "privacy": "public",
                "parts": ["جلسهٔ یک", {"n": "جلسهٔ دو", "d": "توضیح"}],
            }]}, version=1))
            session.commit()
        with TestClient(app) as client:
            owner_login(client)
            detail = client.get("/api/admin/content/events/legacy-parts")
            assert detail.status_code == 200, detail.text
            paused = client.post(
                "/api/admin/content/events/legacy-parts/status",
                json={"status": "paused", "expected_version": 1},
                headers=owner_write_headers(client),
            )
            assert paused.status_code == 200, paused.text
            parts = paused.json()["record"]["parts"]
            assert [row["title"] for row in parts] == ["جلسهٔ یک", "جلسهٔ دو"]
            assert parts[1]["description"] == "توضیح"
    finally:
        engine.dispose()


def test_article_blocks_are_editable_validated_and_projected_publicly():
    """ممیزی پنل ۱۴۰۵/۰۸/۰۱ ردیف B20: بدنهٔ مطلب به‌صورت بلوک (بند/تیتر/نقل‌قول/تصویر/فهرست/کادر/جداکننده) از پنل
    ذخیره می‌شود؛ ``body`` همیشه بندهای متنی همان بلوک‌هاست؛ نوع یا کلید ناشناخته و تصویر با نشانی ناامن ۴۲۲ فیلدی
    می‌دهد و چیزی ذخیره نمی‌کند؛ صفحهٔ عمومی همان بلوک‌ها را می‌گیرد."""
    app, engine = content_app()
    try:
        with TestClient(app) as client:
            owner_login(client)
            blocks = [
                {"ty": "h", "x": "آغاز", "lv": "2"},
                {"ty": "p", "x": "بند نخست"},
                {"ty": "q", "x": "نقل‌قول", "by": "سردبیر"},
                {"ty": "img", "up": "/api/public/media/med-1", "cap": "تصویر", "alt": "جایگزین"},
                {"ty": "ul", "x": "یک\nدو\n\nسه"},
                {"ty": "box", "x": "نکته", "ic": "i-info"},
                {"ty": "hr"},
                {"ty": "p", "x": "   "},
                "بند آخر",
            ]
            created = client.post(
                "/api/admin/content/articles",
                json={"record": {"t": "مطلب بلوکی", "cat": "آموزش", "blocks": blocks}, "expected_version": 0},
                headers=owner_write_headers(client),
            )
            assert created.status_code == 200, created.text
            record = created.json()["record"]
            record_id = record["id"]
            assert [b["ty"] for b in record["blocks"]] == ["h", "p", "q", "img", "ul", "box", "hr", "p"], "بلوک خالی حذف می‌شود"
            assert record["blocks"][0]["lv"] == 2
            assert record["blocks"][4]["x"] == ["یک", "دو", "سه"]
            assert record["blocks"][-1] == {"ty": "p", "x": "بند آخر"}
            assert record["body"] == ["بند نخست", "بند آخر"], "body از بندهای متنی بلوک‌ها مشتق می‌شود"

            for bad, code in (
                ("متن", "invalid_blocks"),
                ([1], "invalid_blocks"),
                ([{"ty": "vid", "src": "https://example.com/v.mp4"}], "invalid_blocks"),
                ([{"ty": "p", "x": "a", "href": "x"}], "invalid_blocks"),
                ([{"ty": "h", "x": "a", "lv": 5}], "invalid_blocks"),
                ([{"ty": "img", "src": "javascript:alert(1)"}], "invalid_image"),
                ([{"ty": "img", "src": "../secret.png"}], "invalid_image"),
                ([{"ty": "p", "x": "a"}] * 101, "invalid_blocks"),
            ):
                rejected = client.put(
                    f"/api/admin/content/articles/{record_id}",
                    json={"record": {"blocks": bad}, "expected_version": 1},
                    headers=owner_write_headers(client),
                )
                assert rejected.status_code == 422, (bad, rejected.text)
                assert rejected.json()["detail"]["code"] == code
                assert rejected.json()["detail"]["field"] == "blocks"
            assert client.get(f"/api/admin/content/articles/{record_id}").json()["record"]["blocks"] == record["blocks"]

            # بدون لید و بدون بند متنی ولی با بلوک تیتر: انتشار مجاز است (بدنه خالی نیست)
            only_heading = client.put(
                f"/api/admin/content/articles/{record_id}",
                json={"record": {"blocks": [{"ty": "h", "x": "فقط تیتر"}], "lead": ""}, "expected_version": 1},
                headers=owner_write_headers(client),
            )
            assert only_heading.status_code == 200, only_heading.text
            assert only_heading.json()["record"]["body"] == []
            published = client.post(
                f"/api/admin/content/articles/{record_id}/status",
                json={"status": "published", "expected_version": 2},
                headers=owner_write_headers(client),
            )
            assert published.status_code == 200, published.text
            public = client.get("/api/public/site-content").json()["content"]["articles"]
            assert [row["id"] for row in public] == [record_id]
            assert public[0]["blocks"] == [{"ty": "h", "x": "فقط تیتر"}]

            # مطلب بدون بلوک ولی با body: هر دو در خروجی عمومی هستند (post.html بندها را بلوک می‌کند)
            legacy = client.post(
                "/api/admin/content/articles",
                json={"record": {"t": "مطلب قدیمی", "body": ["بند ۱", "بند ۲"]}, "expected_version": 3},
                headers=owner_write_headers(client),
            )
            assert legacy.status_code == 200, legacy.text
            assert legacy.json()["record"]["body"] == ["بند ۱", "بند ۲"] and legacy.json()["record"].get("blocks", []) == []
    finally:
        engine.dispose()


def test_events_time_filter_is_judged_on_the_server_calendar_day():
    """Panel audit 1405/08/01 (B1): ``when=today|upcoming|past`` buckets events by their Jalali
    ``on`` day against the Tehran date; undated rows are counted but never guessed into a bucket."""
    # Pure helper first: deterministic "today".
    today = "1405/08/01"
    assert content_admin.event_time_bucket({"on": "۱۴۰۵/۰۸/۰۱"}, today) == "today"
    assert content_admin.event_time_bucket({"on": "1405/8/2"}, today) == "upcoming"
    assert content_admin.event_time_bucket({"on": "1404/12/29"}, today) == "past"
    assert content_admin.event_time_bucket({"on": "پاییز"}, today) == ""
    assert content_admin.event_time_bucket({}, today) == ""
    rows = [
        {"id": "ev-a", "t": "گذشته", "on": "1405/07/30", "status": "published"},
        {"id": "ev-b", "t": "امروز", "on": "۱۴۰۵/۰۸/۰۱", "status": "draft"},
        {"id": "ev-c", "t": "آینده", "on": "1405/08/15", "status": "published"},
        {"id": "ev-d", "t": "بدون تاریخ", "when": "به‌زودی", "status": "draft"},
    ]
    listing = content_admin.list_records("events", rows, when="upcoming", today=today)
    assert [item["id"] for item in listing["items"]] == ["ev-c"]
    assert listing["when"] == "upcoming" and listing["today"] == today
    assert listing["when_counts"] == {"today": 1, "upcoming": 1, "past": 1, "undated": 1}
    assert [item["id"] for item in content_admin.list_records("events", rows, when="past", today=today)["items"]] == ["ev-a"]
    assert [item["id"] for item in content_admin.list_records("events", rows, when="today", today=today)["items"]] == ["ev-b"]
    # Filters combine (status AND when); no filter keeps undated rows.
    assert content_admin.list_records("events", rows, when="upcoming", status="draft", today=today)["total"] == 0
    assert content_admin.list_records("events", rows, today=today)["total"] == 4
    assert content_admin.list_records("articles", [{"id": "ar-1", "t": "x", "at": "2026-10-01"}])["when_counts"] == {}
    try:
        content_admin.list_records("articles", [], when="past")
        raise AssertionError("articles must reject when=")
    except content_admin.ContentAdminError as error:
        assert error.code == "invalid_when" and error.field == "when"
    try:
        content_admin.list_records("events", rows, when="soon", today=today)
        raise AssertionError("unknown bucket must be rejected")
    except content_admin.ContentAdminError as error:
        assert error.code == "invalid_when"

    # HTTP surface: real Tehran "today" from the server, far-future and far-past rows.
    app, engine = content_app()
    try:
        with TestClient(app) as client:
            owner_login(client)
            version = 0
            for title, on in (("دور گذشته", "1399/01/15"), ("دور آینده", "1450/01/15")):
                response = client.post(
                    "/api/admin/content/events",
                    json={"record": dict(EVENT, t=title, on=on), "expected_version": version},
                    headers=owner_write_headers(client),
                )
                assert response.status_code == 200, response.text
                version = response.json()["version"]
            body = client.get("/api/admin/content/events?when=upcoming&sort=date").json()
            assert [item["t"] for item in body["items"]] == ["دور آینده"]
            assert body["when"] == "upcoming" and len(body["today"]) == 10
            assert body["when_counts"]["past"] == 1 and body["when_counts"]["upcoming"] == 1
            past = client.get("/api/admin/content/events?when=past").json()
            assert [item["t"] for item in past["items"]] == ["دور گذشته"]
            assert client.get("/api/admin/content/events?when=soon").status_code == 422
            assert client.get("/api/admin/content/articles?when=past").status_code == 422
            # Permission unchanged: anonymous still blocked on the filtered list.
            anonymous = TestClient(app)
            assert anonymous.get("/api/admin/content/events?when=past").status_code == 401
    finally:
        engine.dispose()


def test_events_list_carries_real_registration_counts_from_the_linked_published_form():
    """Panel audit 1405/08/01 (A6): the admin events list reports capacity/accepted/waitlisted of the
    primary linked published registration form from ``form_responses`` (aggregates only); events
    without a published registration form get ``registration: null`` (never a guessed number)."""
    import uuid
    from datetime import datetime, timedelta, timezone

    from backend.models import FormRecord, FormResponseDraftRecord, FormResponseRecord

    app, engine = content_app()
    try:
        with TestClient(app) as client:
            owner_login(client)
            created = client.post(
                "/api/admin/content/events",
                json={"record": dict(EVENT, t="با فرم"), "expected_version": 0, "status": "published"},
                headers=owner_write_headers(client),
            )
            assert created.status_code == 200, created.text
            event_id = created.json()["record"]["id"]
            version = created.json()["version"]
            bare = client.post(
                "/api/admin/content/events",
                json={"record": dict(EVENT, t="بدون فرم"), "expected_version": version},
                headers=owner_write_headers(client),
            )
            assert bare.status_code == 200, bare.text
            with Session(engine) as db:
                db.add(FormRecord(id="fm-reg", owner_id="owner-01", title="ثبت‌نام کارگاه", model="registration", need="reg",
                                  status="published", version=1, settings={"cap": 3, "wait": 1}, event_id=event_id))
                # A draft form and a survey linked to the same event must not be chosen.
                db.add(FormRecord(id="fm-draft", owner_id="owner-01", title="پیش‌نویس", model="registration", need="reg",
                                  status="draft", version=1, settings={"cap": 99}, event_id=event_id))
                db.add(FormRecord(id="fm-survey", owner_id="owner-01", title="نظرسنجی", model="survey", need="other",
                                  status="published", version=1, settings={}, event_id=event_id))
                moment = datetime.now(timezone.utc)
                for status in ("accepted", "accepted", "waitlisted"):
                    draft_id = str(uuid.uuid4())
                    db.add(FormResponseDraftRecord(id=draft_id, form_id="fm-reg", form_version=1, token_hash=uuid.uuid4().hex * 2,
                                                   answers={}, companions=[], expires_at=moment + timedelta(days=1)))
                    db.add(FormResponseRecord(id=str(uuid.uuid4()), form_id="fm-reg", draft_id=draft_id, form_version=1,
                                              status=status, answers={}, companions=[], form_snapshot={"name": "x", "version": 1}))
                db.commit()
            body = client.get("/api/admin/content/events?sort=title&order=asc").json()
            by_title = {item["t"]: item for item in body["items"]}
            reg = by_title["با فرم"]["registration"]
            assert reg["form_id"] == "fm-reg" and reg["form_name"] == "ثبت‌نام کارگاه"
            assert (reg["accepted"], reg["waitlisted"], reg["cap"], reg["wait"], reg["full"]) == (2, 1, 3, 1, False)
            assert reg["source"] == "form_responses"
            assert by_title["بدون فرم"]["registration"] is None
            # No registrant data leaks through the list.
            assert not any(key in reg for key in ("answers", "registrant_name", "items", "responses"))
            # Articles are untouched.
            assert "registration" not in client.get("/api/admin/content/articles").json()
    finally:
        engine.dispose()
