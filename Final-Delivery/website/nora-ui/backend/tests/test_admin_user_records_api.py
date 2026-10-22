"""Account-scoped read APIs for admin user registrations and notifications."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app import create_app
from backend.config import Settings
from backend.models import Base, FormFieldRecord, FormRecord, FormResponseRecord, UserNotificationRecord
from backend.security import hash_password
from test_identity_scoped_form_history import seed_form, seed_response
from test_workflows_api import BOT_TOKEN, SERVICE_TOKEN, assign_manager, bale_login, owner_login


def make_app():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    settings = Settings(database_url=None, owner_id="owner-01", owner_username="nora-owner",
                        owner_password_hash=hash_password("correct-horse-staple-42"), cookie_secure=False,
                        bale_bot_token=BOT_TOKEN, bot_service_token=SERVICE_TOKEN, owner_bale_user_id="70001")
    return create_app(settings, engine=engine), engine


def test_admin_registration_list_detail_are_scoped_paginated_and_exclude_hidden_fields():
    app, engine = make_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            member_a = bale_login(owner, 99101)
            owner.cookies.clear()
            member_b = bale_login(owner, 99102)
            owner.cookies.clear()
            manager_id = bale_login(owner, 99103)
            assign_manager(owner, manager_id)
            owner.cookies.clear()
            owner_login(owner)
            seed_form(engine, "admin-reg-a")
            ids = [seed_response(engine, form_id="admin-reg-a", account_id=member_a, answers={"public": f"A-{i}", "hidden": "secret"}) for i in range(3)]
            other = seed_response(engine, form_id="admin-reg-a", account_id=member_b, answers={"public": "B-private"})
            with Session(engine) as db:
                form = db.get(FormRecord, "admin-reg-a")
                form.fields = [
                    FormFieldRecord(form_id="admin-reg-a", field_key="public", position=0, field_type="text", label="پاسخ عمومی", config={}),
                    FormFieldRecord(form_id="admin-reg-a", field_key="hidden", position=1, field_type="text", label="پاسخ مخفی", config={"col": False}),
                ]
                for response_id in ids:
                    response = db.get(FormResponseRecord, response_id)
                    response.form_snapshot = {"name": "فرم آزمون", "fields": [{"id": "public", "label": "پاسخ عمومی"}, {"id": "hidden", "label": "پاسخ مخفی"}]}
                db.commit()

            assert TestClient(app).get(f"/api/admin/users/{member_a}/registrations").status_code == 401
            # A plain account has no us_view, even if it knows target account and response UUIDs.
            member = TestClient(app)
            bale_login(member, 99104)
            assert member.get(f"/api/admin/users/{member_a}/registrations").status_code == 403
            assert owner.get(f"/api/admin/users/{member_a}/registrations?limit=2&offset=0").status_code == 200
            first = owner.get(f"/api/admin/users/{member_a}/registrations?limit=2&offset=0").json()
            assert first["source"] == "shared_server_database" and first["total"] == 3
            assert len(first["items"]) == 2 and first["has_more"] is True
            second = owner.get(f"/api/admin/users/{member_a}/registrations?limit=2&offset=2").json()
            assert len(second["items"]) == 1 and second["has_more"] is False
            assert {row["id"] for row in first["items"] + second["items"]} == set(ids)
            own_detail = owner.get(f"/api/admin/users/{member_a}/registrations/{ids[0]}")
            assert own_detail.status_code == 200, own_detail.text
            details = own_detail.json()
            assert details["account_id"] == member_a and details["response_id"] == ids[0]
            assert details["form"] == {"id": "admin-reg-a", "name": "فرم آزمون"}
            assert details["answers"] == [{"field_id": "public", "label": "پاسخ عمومی", "value": "A-0"}]
            assert "secret" not in own_detail.text and "registrant_mobile" not in details
            empty_registrations = owner.get(f"/api/admin/users/{manager_id}/registrations").json()
            assert empty_registrations["items"] == [] and empty_registrations["total"] == 0 and empty_registrations["has_more"] is False
            assert owner.get(f"/api/admin/users/{member_a}/registrations/{other}").status_code == 404
            assert owner.get(f"/api/admin/users/{member_b}/registrations/{ids[0]}").status_code == 404
            assert owner.get(f"/api/admin/users/{member_a}/registrations/not-a-uuid").status_code == 404
            assert owner.get("/api/admin/users/00000000-0000-4000-8000-000000000000/registrations").status_code == 404
            manager_client = TestClient(app)
            manager_login = manager_client.post("/api/auth/manager-login", json={"username": "workflow." + manager_id[-4:], "password": "workflow-manager-password-2026"}, headers={"Origin": "http://testserver"})
            assert manager_login.status_code == 200, manager_login.text
            assert manager_client.get(f"/api/admin/users/{member_a}/registrations?limit=1").status_code == 200
            assert manager_client.get(f"/api/admin/users/{member_a}/registrations/{ids[0]}").status_code == 200
            assert "no-store" in owner.get(f"/api/admin/users/{member_a}/registrations?limit=1").headers["cache-control"]
    finally:
        engine.dispose()


def test_admin_user_notifications_only_returns_target_account_rows():
    app, engine = make_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            member_a = bale_login(owner, 99201)
            owner.cookies.clear()
            member_b = bale_login(owner, 99202)
            owner.cookies.clear()
            manager_id = bale_login(owner, 99203)
            assign_manager(owner, manager_id)
            owner.cookies.clear()
            owner_login(owner)
            now = datetime.now(timezone.utc)
            a_ids, b_ids = [], []
            with Session(engine) as db:
                for target, ids in ((member_a, a_ids), (member_b, b_ids)):
                    for index in range(3):
                        row_id = str(uuid4()); ids.append(row_id)
                        db.add(UserNotificationRecord(id=row_id, account_id=target, bale_user_id="", kind="system_notice",
                            title=f"پیام {target}-{index}", body="متن", link=("https://evil.example" if target == member_a and index == 2 else "/account.html#registrations"),
                            delivery_status="delivered" if index == 0 else "pending", delivery_attempts=index,
                            last_delivery_error=None, created_at=now, delivered_at=now if index == 0 else None))
                db.commit()
            assert TestClient(app).get(f"/api/admin/users/{member_a}/notifications").status_code == 401
            plain = TestClient(app); bale_login(plain, 99204)
            assert plain.get(f"/api/admin/users/{member_a}/notifications").status_code == 403
            page = owner.get(f"/api/admin/users/{member_a}/notifications?limit=2&offset=0")
            assert page.status_code == 200, page.text
            empty_target = owner.get(f"/api/admin/users/{manager_id}/notifications").json()
            assert empty_target["items"] == [] and empty_target["total"] == 0 and empty_target["has_more"] is False
            data = page.json()
            assert data["source"] == "shared_server_database" and data["total"] == 3 and data["has_more"] is True
            assert len(data["items"]) == 2 and all(item["scope"] == "account" for item in data["items"])
            assert all(member_a in item["title"] for item in data["items"])
            assert not any(member_b in repr(item) for item in data["items"])
            assert {item["id"] for item in data["items"]}.isdisjoint(set(b_ids))
            all_a = owner.get(f"/api/admin/users/{member_a}/notifications?limit=100").json()["items"]
            assert {item["id"] for item in all_a} == set(a_ids)
            assert all(item["link"] is None or item["link"] == "/account.html#registrations" for item in all_a)
            assert set(item["id"] for item in owner.get(f"/api/admin/users/{member_a}/notifications?limit=2&offset=2").json()["items"]).issubset(set(a_ids))
            assert owner.get(f"/api/admin/users/00000000-0000-4000-8000-000000000000/notifications").status_code == 404
            manager_client = TestClient(app)
            manager_login = manager_client.post("/api/auth/manager-login", json={"username": "workflow." + manager_id[-4:], "password": "workflow-manager-password-2026"}, headers={"Origin": "http://testserver"})
            assert manager_login.status_code == 200, manager_login.text
            manager_page = manager_client.get(f"/api/admin/users/{member_a}/notifications?limit=2")
            assert manager_page.status_code == 200 and manager_page.json()["total"] == 3
            assert "no-store" in owner.get(f"/api/admin/users/{member_a}/notifications").headers["cache-control"]
    finally:
        engine.dispose()
