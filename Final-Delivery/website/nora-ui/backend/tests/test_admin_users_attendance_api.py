"""Managers' user directory (``us_view``) and shared attendance check-in (``attendance``).

In-memory SQLite only. The user directory must never expose phone digests, hashes
or tokens; attendance writes the same ``ticket_checked_in_*`` columns the Bale bot
uses and audits every manual change.
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

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import AccountProfileRecord, Base, FormResponseRecord  # noqa: E402
from backend.security import hash_password  # noqa: E402

from test_identity_scoped_form_history import seed_form, seed_response  # noqa: E402
from test_workflows_api import (  # noqa: E402
    BOT_TOKEN,
    SERVICE_TOKEN,
    account_write_headers,
    assign_manager,
    bale_login,
    owner_login,
    owner_write_headers,
    service_headers,
)


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


def set_profile(engine, account_id: str, **fields: str) -> None:
    with Session(engine) as db:
        record = db.get(AccountProfileRecord, account_id)
        if record is None:
            record = AccountProfileRecord(account_id=account_id, fields={})
            db.add(record)
        record.fields = {**(record.fields or {}), **fields}
        db.commit()


def test_user_directory_search_filter_pagination_and_no_confidential_fields():
    app, engine = make_app()
    try:
        with TestClient(app) as client:
            assert client.get("/api/admin/users").status_code == 401
            member_a = bale_login(client, 91001)
            # A plain member cannot list users at all.
            assert client.get("/api/admin/users").status_code == 403
            assert client.get(f"/api/admin/users/{member_a}").status_code == 403
            client.cookies.clear()
            member_b = bale_login(client, 91002)
            client.cookies.clear()
            manager_id = bale_login(client, 91003)
            set_profile(engine, member_a, fullName="سارا احمدی", city="شیراز", email="sara@example.test", nationalId="0012345678")
            set_profile(engine, member_b, fullName="رضا کریمی", province="تهران")
            seed_form(engine, "form-users-1")
            seed_response(engine, form_id="form-users-1", account_id=member_a)

            assign_manager(client, manager_id)
            listing = client.get("/api/admin/users?limit=2")
            assert listing.status_code == 200, listing.text
            body = listing.json()
            assert body["total"] == 3 and body["has_more"] is True and body["can_open_roles"] is False
            assert len(body["items"]) == 2
            by_id = {item["account_id"]: item for item in client.get("/api/admin/users?limit=100").json()["items"]}
            assert by_id[member_a]["display_name"] == "سارا احمدی"
            assert by_id[member_a]["registrations"] == 1
            assert by_id[member_a]["providers"] == ["bale"]
            assert by_id[member_a]["bale_user_id"] == "91001"
            assert by_id[manager_id]["role"] == "manager"
            for item in by_id.values():
                flattened = repr(item).lower()
                assert "email" not in item  # owner-only
                assert "0012345678" not in flattened
                assert "hash" not in flattened and "token" not in flattened and "phone" not in flattened
                assert "password" not in flattened

            search = client.get("/api/admin/users?q=سارا").json()
            assert [item["account_id"] for item in search["items"]] == [member_a]
            by_prefix = client.get(f"/api/admin/users?q={member_b[:8]}").json()
            assert [item["account_id"] for item in by_prefix["items"]] == [member_b]
            assert client.get("/api/admin/users?role=assigned").json()["total"] == 1
            assert client.get("/api/admin/users?provider=phone").json()["total"] == 0
            assert client.get("/api/admin/users?provider=bale").json()["total"] == 3
            assert client.get("/api/admin/users?role=bogus").status_code == 422

            detail = client.get(f"/api/admin/users/{member_a}")
            assert detail.status_code == 200, detail.text
            data = detail.json()
            assert data["registration_items"][0]["form_name"] == "ثبت نام کارگاه"
            assert data["reviews"] == [] and data["notifications"] == 0
            assert "email" not in data and "manager_username" not in data
            assert client.get("/api/admin/users/not-a-uuid").status_code == 404
            assert client.get("/api/admin/users/00000000-0000-4000-8000-000000000000").status_code == 404

            # Owner additionally sees e-mail and can open the roles module.
            client.cookies.clear()
            owner_login(client)
            owner_view = client.get(f"/api/admin/users/{member_a}").json()
            assert owner_view["email"] == "sara@example.test"
            assert owner_view["manager_username"] is None
            assert "nationalId" not in owner_view and "0012345678" not in repr(owner_view)
            assert client.get("/api/admin/users").json()["can_open_roles"] is True
    finally:
        engine.dispose()


def make_ticket(engine, response_id: str, name: str = "", **snapshot_extra) -> None:
    """Mark a seeded response as a registration ticket (what the public form flow stores)."""
    with Session(engine) as db:
        record = db.scalar(select(FormResponseRecord).where(FormResponseRecord.id == response_id))
        assert record is not None
        if name:
            record.registrant_name = name
        record.form_snapshot = {"name": "ثبت نام کارگاه", "version": 1, "model": "registration", "need": "reg", **snapshot_extra}
        db.commit()


def _checked_in(engine, response_id: str) -> FormResponseRecord:
    with Session(engine) as db:
        record = db.scalar(select(FormResponseRecord).where(FormResponseRecord.id == response_id))
        assert record is not None
        db.expunge(record)
        return record


def test_attendance_lists_shared_tickets_and_manual_check_in_is_audited_and_reversible():
    app, engine = make_app()
    try:
        with TestClient(app) as client:
            seed_form(engine, "form-att-1", title="کارگاه حضوری")
            seed_form(engine, "form-att-2", title="وبینار")
            seed_form(engine, "form-other", model="survey", title="نظرسنجی")
            paid = seed_response(engine, form_id="form-att-1", answers={"full-name": "مینا رستمی"})
            other = seed_response(engine, form_id="form-att-1", answers={"full-name": "امید نادری"})
            seed_response(engine, form_id="form-att-2")
            make_ticket(engine, paid, name="مینا رستمی")
            make_ticket(engine, other)

            assert client.get("/api/admin/attendance/forms").status_code == 401
            member = bale_login(client, 92001)
            assert client.get("/api/admin/attendance/forms").status_code == 403
            denied = client.post(
                f"/api/admin/attendance/responses/{paid}/check-in", json={}, headers=account_write_headers(client)
            )
            assert denied.status_code == 403
            assert _checked_in(engine, paid).ticket_checked_in_at is None
            client.cookies.clear()

            # The bot checks one ticket in through its own API (same columns).
            bot = client.post(
                f"/api/bot/form-tickets/{other}/check-in", json={"bale_user_id": "70001"}, headers=service_headers()
            )
            assert bot.status_code == 200, bot.text

            manager_id = bale_login(client, 92002)
            assert manager_id != member
            assign_manager(client, manager_id)
            forms = client.get("/api/admin/attendance/forms").json()
            assert forms["source"] == "shared_server_database"
            assert {item["form_id"]: (item["people"], item["checked_in"]) for item in forms["items"]} == {
                "form-att-1": (2, 1), "form-att-2": (1, 0),
            }
            assert client.get("/api/admin/attendance/forms?q=وبینار").json()["total"] == 1
            assert client.get("/api/admin/attendance/forms/form-other/people").status_code == 200
            assert client.get("/api/admin/attendance/forms/missing/people").status_code == 404

            people = client.get("/api/admin/attendance/forms/form-att-1/people").json()
            assert people["total"] == 2
            by_id = {item["response_id"]: item for item in people["items"]}
            assert by_id[other]["checked_in"] is True and by_id[other]["checked_in_by"] == {"kind": "bot", "id": "70001"}
            assert by_id[paid]["checked_in"] is False and by_id[paid]["name"] == "مینا رستمی"
            assert "mobile" not in by_id[paid] and by_id[paid]["mobile_hint"] == ""
            assert client.get("/api/admin/attendance/forms/form-att-1/people?state=pending").json()["total"] == 1
            assert client.get("/api/admin/attendance/forms/form-att-1/people?q=مینا").json()["total"] == 1

            # Manual check-in needs CSRF, is idempotent-safe (409 on repeat) and audited.
            no_csrf = client.post(
                f"/api/admin/attendance/responses/{paid}/check-in", json={}, headers={"Origin": "http://testserver"}
            )
            assert no_csrf.status_code == 403
            done = client.post(
                f"/api/admin/attendance/responses/{paid}/check-in",
                json={"reason": "ثبت دستی در ورودی"},
                headers=account_write_headers(client),
            )
            assert done.status_code == 200, done.text
            assert done.json()["person"]["checked_in_by"] == {"kind": "web", "id": manager_id}
            stored = _checked_in(engine, paid)
            assert stored.ticket_checked_in_at is not None
            assert stored.ticket_checked_in_by_account_id == manager_id
            assert stored.ticket_checked_in_by_bale_user_id is None
            again = client.post(
                f"/api/admin/attendance/responses/{paid}/check-in", json={}, headers=account_write_headers(client)
            )
            assert again.status_code == 409 and again.json()["detail"]["code"] == "already_checked_in"

            # Undo requires a reason and keeps the previous actor in the audit row.
            missing_reason = client.post(
                f"/api/admin/attendance/responses/{paid}/undo-check-in", json={}, headers=account_write_headers(client)
            )
            assert missing_reason.status_code == 422
            assert missing_reason.json()["detail"]["code"] == "reason_required"
            undone = client.post(
                f"/api/admin/attendance/responses/{paid}/undo-check-in",
                json={"reason": "اشتباه ثبت شد"},
                headers=account_write_headers(client),
            )
            assert undone.status_code == 200, undone.text
            assert undone.json()["person"]["checked_in"] is False
            assert _checked_in(engine, paid).ticket_checked_in_at is None
            # Unknown / foreign ids leak nothing.
            assert client.post(
                "/api/admin/attendance/responses/00000000-0000-4000-8000-000000000000/check-in",
                json={}, headers=account_write_headers(client),
            ).status_code == 404
            assert client.post(
                "/api/admin/attendance/responses/../x/check-in", json={}, headers=account_write_headers(client)
            ).status_code in {404, 405, 422}

            client.cookies.clear()
            owner_login(client)
            trail = client.get("/api/owner/audit?action=attendance.").json()["items"]
            assert [item["action"] for item in trail] == ["attendance.undo_check_in", "attendance.check_in"]
            assert trail[0]["details"]["reason"] == "اشتباه ثبت شد"
            assert trail[0]["details"]["previous_by"] == f"web:{manager_id}"
            assert trail[1]["details"]["source"] == "web"
            assert {item["actor_id"] for item in trail} == {manager_id}

            # Owner can also check in; the actor is the owner id.
            owner_done = client.post(
                f"/api/admin/attendance/responses/{paid}/check-in", json={}, headers=owner_write_headers(client)
            )
            assert owner_done.status_code == 200, owner_done.text
            assert owner_done.json()["person"]["checked_in_by"] == {"kind": "web", "id": "owner-01"}
    finally:
        engine.dispose()


def test_attendance_check_in_requires_confirmed_payment_like_the_bot():
    app, engine = make_app()
    try:
        with TestClient(app) as client:
            seed_form(engine, "form-att-pay")
            response_id = seed_response(engine, form_id="form-att-pay")
            make_ticket(engine, response_id, receipt_review_required=True)
            owner_login(client)
            people = client.get("/api/admin/attendance/forms/form-att-pay/people").json()
            assert people["items"][0]["payment_approved"] is False
            blocked = client.post(
                f"/api/admin/attendance/responses/{response_id}/check-in", json={}, headers=owner_write_headers(client)
            )
            assert blocked.status_code == 409
            assert blocked.json()["detail"]["code"] == "ticket_payment_not_confirmed"
            assert _checked_in(engine, response_id).ticket_checked_in_at is None
    finally:
        engine.dispose()
