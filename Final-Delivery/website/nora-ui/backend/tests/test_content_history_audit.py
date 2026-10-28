"""Per-record change history for events, articles and people (owner decision 1405/08/01).

The panel's «تاریخچه» tab reads **only** the existing audit trail through
``GET /api/owner/audit?target_type=content.<kind>&target_id=<record>``; no revision table, no
snapshots, no restore. This pins what that tab relies on:

* every content write (create / update / status) leaves a row targeted at **that record**;
* a whole-category ``people`` save through ``PATCH /api/owner/site-content`` leaves one row
  per changed person (``content.create`` / ``content.update`` / ``content.remove``) so a person's
  history is filterable by id — the untouched person gets no row;
* the dotted ``target_type`` is accepted by the filter and the result never contains another
  record's rows;
* only the owner session can read it: manager (with ev_create) and plain member get 401.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from test_content_admin_api import EVENT, content_app  # noqa: E402
from test_workflows_api import (  # noqa: E402
    account_write_headers,
    assign_manager,
    bale_login,
    owner_login,
    owner_write_headers,
)

ARTICLE = {"t": "مطلب تاریخچه", "cat": "یادداشت", "lead": "خلاصه", "body": "متن مطلب برای آزمون تاریخچه."}

TEACHER = {"id": "pp-hist-1", "n": "مدرس تاریخچه", "kind": "teacher", "r": "مدرس"}
STAFF = {"id": "pp-hist-2", "n": "کارمند تاریخچه", "kind": "staff", "r": "هماهنگی"}


def history(client: TestClient, target_type: str, target_id: str):
    return client.get(
        "/api/owner/audit", params={"target_type": target_type, "target_id": target_id, "limit": 50}
    )


def test_history_rows_are_per_record_owner_only_and_cover_people_edits():
    app, _engine = content_app()
    try:
        with TestClient(app) as client:
            owner_login(client)
            # Two events + one article → three independent histories.
            first = client.post(
                "/api/admin/content/events",
                json={"record": EVENT, "expected_version": 0},
                headers=owner_write_headers(client),
            )
            assert first.status_code == 200, first.text
            first_id = first.json()["record"]["id"]
            version = first.json()["version"]
            second = client.post(
                "/api/admin/content/events",
                json={"record": {**EVENT, "t": "رویداد دوم"}, "expected_version": version},
                headers=owner_write_headers(client),
            )
            assert second.status_code == 200, second.text
            second_id = second.json()["record"]["id"]
            version = second.json()["version"]
            article = client.post(
                "/api/admin/content/articles",
                json={"record": ARTICLE, "expected_version": version},
                headers=owner_write_headers(client),
            )
            assert article.status_code == 200, article.text
            article_id = article.json()["record"]["id"]
            version = article.json()["version"]
            # Edit + publish the first event only.
            edited = client.put(
                f"/api/admin/content/events/{first_id}",
                json={"record": {**EVENT, "t": "رویداد ویرایش‌شده"}, "expected_version": version},
                headers=owner_write_headers(client),
            )
            assert edited.status_code == 200, edited.text
            version = edited.json()["version"]
            published = client.post(
                f"/api/admin/content/events/{first_id}/status",
                json={"status": "published", "expected_version": version},
                headers=owner_write_headers(client),
            )
            assert published.status_code == 200, published.text
            version = published.json()["version"]

            # History of the first event: create → update → status, newest first, nothing else.
            rows = history(client, "content.events", first_id)
            assert rows.status_code == 200, rows.text
            items = rows.json()["items"]
            assert [row["action"] for row in items] == ["content.status", "content.update", "content.create"]
            assert {row["target_id"] for row in items} == {first_id}
            assert {row["target_type"] for row in items} == {"content.events"}
            assert items[0]["details"]["status"] == "published" and items[0]["details"]["from"] == "draft"
            assert items[1]["details"]["title"] == "رویداد ویرایش‌شده"
            assert all(row["actor_kind"] == "owner" and row["outcome"] == "ok" for row in items)
            assert all("version" in row["details"] for row in items)
            # The second event and the article each see only their own creation row.
            other = history(client, "content.events", second_id).json()["items"]
            assert [row["action"] for row in other] == ["content.create"] and other[0]["target_id"] == second_id
            art = history(client, "content.articles", article_id).json()["items"]
            assert [row["action"] for row in art] == ["content.create"] and art[0]["target_type"] == "content.articles"
            # A wrong kind for a real id is empty (filter is exact on both fields).
            assert history(client, "content.articles", first_id).json()["items"] == []
            # Rejected filter characters are still refused (no LIKE wildcards reach the query).
            assert client.get("/api/owner/audit", params={"target_type": "content.%"}).status_code == 422

            # People are saved as a whole category: one row per *changed* person.
            saved = client.patch(
                "/api/owner/site-content",
                json={"content": {"people": [TEACHER, STAFF]}, "expected_version": version},
                headers=owner_write_headers(client),
            )
            assert saved.status_code == 200, saved.text
            version = saved.json()["version"]
            teacher_rows = history(client, "content.people", TEACHER["id"]).json()["items"]
            assert [row["action"] for row in teacher_rows] == ["content.create"]
            assert teacher_rows[0]["details"] == {"kind": "people", "title": "مدرس تاریخچه", "version": version}
            # Edit the teacher, keep the staff member unchanged, then drop the staff member.
            renamed = client.patch(
                "/api/owner/site-content",
                json={"content": {"people": [{**TEACHER, "n": "مدرس تاریخچه ۲"}, STAFF]}, "expected_version": version},
                headers=owner_write_headers(client),
            )
            assert renamed.status_code == 200, renamed.text
            version = renamed.json()["version"]
            assert [row["action"] for row in history(client, "content.people", TEACHER["id"]).json()["items"]] == [
                "content.update", "content.create",
            ]
            assert [row["action"] for row in history(client, "content.people", STAFF["id"]).json()["items"]] == [
                "content.create",
            ], "an untouched person must not get a history row"
            removed = client.patch(
                "/api/owner/site-content",
                json={"content": {"people": [{**TEACHER, "n": "مدرس تاریخچه ۲"}]}, "expected_version": version},
                headers=owner_write_headers(client),
            )
            assert removed.status_code == 200, removed.text
            staff_rows = history(client, "content.people", STAFF["id"]).json()["items"]
            assert [row["action"] for row in staff_rows] == ["content.remove", "content.create"]
            assert staff_rows[0]["details"]["title"] == "کارمند تاریخچه"
            # The document-level row is still written once per save (unchanged contract).
            doc_rows = history(client, "site_content", "public").json()["items"]
            assert len(doc_rows) == 3 and {row["action"] for row in doc_rows} == {"site_content.update"}
            # No person id leaks into another person's history, and content rows never carry a person.
            assert all(row["target_id"] == STAFF["id"] for row in staff_rows)
            assert all(row["target_type"] != "content.people" for row in history(client, "content.events", first_id).json()["items"])
            client.cookies.clear()

            # Manager with ev_create can *edit* events but cannot read the history endpoint.
            manager_id = bale_login(client, 83001)
            assign_manager(client, manager_id)
            mine = client.put(
                f"/api/admin/content/events/{second_id}",
                json={"record": {**EVENT, "t": "ویرایش مدیر"}, "expected_version": version + 1},
                headers=account_write_headers(client),
            )
            assert mine.status_code == 200, mine.text
            assert history(client, "content.events", second_id).status_code == 401
            client.cookies.clear()
            bale_login(client, 83002)
            assert history(client, "content.events", second_id).status_code == 401
            client.cookies.clear()
            assert history(client, "content.events", second_id).status_code == 401

            # …but the manager's edit is in the record's history for the owner, with actor = account.
            owner_login(client)
            second_rows = history(client, "content.events", second_id).json()["items"]
            assert [row["action"] for row in second_rows] == ["content.update", "content.create"]
            assert second_rows[0]["actor_kind"] == "account" and second_rows[0]["actor_id"] == manager_id
            assert second_rows[0]["actor_role"] == "manager"
    finally:
        _engine.dispose()
