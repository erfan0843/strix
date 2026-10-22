"""U4 / U5 — the account file in the managers' panel: registrations of one account (list + detail)
and the account's own outbox rows.

In-memory SQLite only. The path account id is a *selector*, never an authorisation: the session
needs ``us_view``; rows are selected inside the server-side ownership scope of the target account,
so another account's response id is a 404; phone/national-id answers are masked; amounts and
transaction ids are visible only with ``finance``; the global outbox stays untouched.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend import notifications as notifications_mod  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import (  # noqa: E402
    AdminTaskRecord,
    Base,
    FormPaymentRecord,
    FormRecord,
    FormResponseDraftRecord,
    FormResponseRecord,
    UserNotificationRecord,
)
from backend.security import hash_password  # noqa: E402

from test_identity_scoped_form_history import seed_form, seed_response  # noqa: E402
from test_workflows_api import (  # noqa: E402
    BOT_TOKEN,
    SERVICE_TOKEN,
    assign_manager,
    bale_login,
    owner_login,
    signed_init_data,
)

TARGET = "00000000-0000-4000-8000-00000000aaaa"
SNAPSHOT_FIELDS = [
    {"id": "full-name", "type": "fullname", "label": "نام و نام خانوادگی"},
    {"id": "mobile", "type": "mobile", "label": "شمارهٔ همراه"},
    {"id": "nid", "type": "nid", "label": "کد ملی"},
    {"id": "city", "type": "text", "label": "شهر"},
    {"id": "topics", "type": "multi", "label": "موضوع‌ها"},
]


def relogin(client: TestClient, user_id: int, tag: str) -> None:
    """Second Bale login of the same user needs a fresh ``query_id`` (replay protection)."""
    response = client.post(
        "/api/auth/bale-mini-app",
        json={"init_data": signed_init_data(user_id, query_id=f"file-{tag}-{user_id}")},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200, response.text


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


def enrich(engine, response_id: str, *, name: str = "سارا احمدی", event: dict | None = None, payment: dict | None = None, receipt_task: bool = False) -> None:
    """Give a seeded response the snapshot the public flow stores (fields, event) + optional payment."""
    with Session(engine) as db:
        record = db.scalar(select(FormResponseRecord).where(FormResponseRecord.id == response_id))
        assert record is not None
        snapshot = dict(record.form_snapshot or {})
        snapshot["fields"] = SNAPSHOT_FIELDS
        if event:
            snapshot["event"] = event
        record.form_snapshot = snapshot
        record.registrant_name = name
        if payment:
            db.add(FormPaymentRecord(
                id=str(uuid.uuid4()), form_id=record.form_id, draft_id=record.draft_id, response_id=record.id,
                form_version=1, method=payment.get("method", "card_transfer"), status=payment["status"],
                amount=payment.get("amount", 1_500_000), currency="IRR", party_count=1, selection={},
                idempotency_key="pay-" + response_id[:8], transaction_id=payment.get("transaction_id"),
            ))
        if receipt_task:
            task = AdminTaskRecord(
                id=str(uuid.uuid4()), kind="receipt_review", status="pending", account_id=TARGET_OF[response_id], bale_user_id="91001",
                idempotency_key="task-" + response_id[:8], create_hash="0" * 64,
                payload={"response_id": response_id, "amount": 1_500_000},
            )
            db.add(task)
            db.flush()
            record.receipt_review_task_id = task.id
        db.commit()


TARGET_OF: dict[str, str] = {}


def test_registrations_list_and_detail_are_scoped_to_the_target_account():
    app, engine = make_app()
    try:
        with TestClient(app) as client:
            member_a = bale_login(client, 91001)
            client.cookies.clear()
            member_b = bale_login(client, 91002)
            client.cookies.clear()
            manager_id = bale_login(client, 91003)
            client.cookies.clear()

            seed_form(engine, "form-file-1")
            seed_form(engine, "form-file-2", title="نشست پاییز")
            # 3 primary registrations for A (one per page later), 1 for B — B's must never show under A.
            answers = {"full-name": "سارا احمدی", "mobile": "09121234567", "nid": "0012345678", "city": "شیراز",
                       "topics": ["نجوم", "عکاسی"], "ignored-key": "not in snapshot"}
            a1 = seed_response(engine, form_id="form-file-1", account_id=member_a, answers=answers)
            a2 = seed_response(engine, form_id="form-file-2", account_id=member_a)
            a3 = seed_response(engine, form_id="form-file-1", account_id=member_a, status="waitlisted")
            b1 = seed_response(engine, form_id="form-file-1", account_id=member_b, answers={"full-name": "رضا کریمی", "nid": "9876543210"})
            TARGET_OF.update({a1: member_a, b1: member_b})
            enrich(engine, a1, event={"id": "ev-1", "title": "کارگاه نجوم", "date": "۱۴۰۵/۰۸/۱۰"},
                   payment={"status": "receipt_submitted", "transaction_id": "TRX-SECRET-1"}, receipt_task=True)
            enrich(engine, b1, name="رضا کریمی")

            # 401 without a session, 403 for a plain member (even for their own id).
            assert client.get(f"/api/admin/users/{member_a}/registrations").status_code == 401
            assert client.get(f"/api/admin/users/{member_a}/registrations/{a1}").status_code == 401
            relogin(client, 91001, "reg")
            assert client.get(f"/api/admin/users/{member_a}/registrations").status_code == 403
            assert client.get(f"/api/admin/users/{member_a}/registrations/{a1}").status_code == 403
            client.cookies.clear()

            assign_manager(client, manager_id)  # manager: us_view, no finance
            listing = client.get(f"/api/admin/users/{member_a}/registrations?limit=2")
            assert listing.status_code == 200, listing.text
            body = listing.json()
            assert body["source"] == "shared_server_database" and body["account_id"] == member_a
            assert body["total"] == 3 and body["has_more"] is True and len(body["items"]) == 2
            assert "no-store" in listing.headers["cache-control"]
            page2 = client.get(f"/api/admin/users/{member_a}/registrations?limit=2&offset=2").json()
            assert page2["total"] == 3 and page2["has_more"] is False and len(page2["items"]) == 1
            ids = {item["id"] for item in body["items"]} | {item["id"] for item in page2["items"]}
            assert ids == {a1, a2, a3} and b1 not in ids
            by_id = {item["id"]: item for item in body["items"] + page2["items"]}
            assert by_id[a1]["event_title"] == "کارگاه نجوم" and by_id[a1]["event_id"] == ""  # snapshot event, form has no event_id
            assert by_id[a1]["payment_status"] == "receipt_submitted" and by_id[a1]["receipt_uploaded"] is True
            assert by_id[a3]["status"] == "waitlisted" and by_id[a2]["form_id"] == "form-file-2"  # name comes from the frozen snapshot
            for item in by_id.values():
                flat = repr(item)
                assert "answers" not in item and "0912" not in flat and "0012345678" not in flat and "TRX-SECRET" not in flat
            # Empty account (B has one, manager has none) and pagination guards.
            assert client.get(f"/api/admin/users/{manager_id}/registrations").json() == {
                "source": "shared_server_database", "account_id": manager_id, "items": [], "total": 0,
                "limit": 20, "offset": 0, "has_more": False,
            }
            assert client.get(f"/api/admin/users/{member_a}/registrations?limit=0").status_code == 422
            assert client.get(f"/api/admin/users/{member_a}/registrations?limit=101").status_code == 422
            assert client.get("/api/admin/users/not-a-uuid/registrations").status_code == 404
            assert client.get(f"/api/admin/users/{TARGET}/registrations").status_code == 404

            # Detail: labelled answers from the frozen snapshot only; phone/national id masked;
            # finance fields hidden for a manager without ``finance``.
            detail = client.get(f"/api/admin/users/{member_a}/registrations/{a1}")
            assert detail.status_code == 200, detail.text
            data = detail.json()
            assert data["response_id"] == a1 and data["account_id"] == member_a
            assert data["form"] == {"id": "form-file-1", "name": "ثبت نام کارگاه", "version": 1}
            assert data["event"] == {"id": "", "title": "کارگاه نجوم", "date": "۱۴۰۵/۰۸/۱۰"}
            assert data["registrant_name"] == "سارا احمدی"
            answers_by_field = {row["field_id"]: row for row in data["answers"]}
            assert list(answers_by_field) == ["full-name", "mobile", "nid", "city", "topics"]  # snapshot order, unknown key dropped
            assert answers_by_field["full-name"] == {"field_id": "full-name", "label": "نام و نام خانوادگی", "type": "fullname", "value": "سارا احمدی", "masked": None}
            assert answers_by_field["mobile"]["value"] is None and answers_by_field["mobile"]["masked"] == "mobile" and answers_by_field["mobile"]["hint"] == "4567"
            assert answers_by_field["nid"]["value"] is None and answers_by_field["nid"]["masked"] == "national_id" and answers_by_field["nid"]["hint"] == ""
            assert answers_by_field["topics"]["value"] == ["نجوم", "عکاسی"]
            flat = repr(data)
            assert "09121234567" not in flat and "0012345678" not in flat and "ignored-key" not in flat and "not in snapshot" not in flat
            assert data["payment"] == {"status": "receipt_submitted", "method": "card_transfer"} and data["finance_visible"] is False
            assert "TRX-SECRET" not in flat and "1500000" not in flat.replace(",", "")
            assert data["receipt"]["uploaded"] is True and data["receipt"]["task_status"] == "pending"
            assert data["attendance"] == {"checked_in": False, "checked_in_at": None, "checked_in_by": None}
            assert data["companions"] == []
            # A response that exists but belongs to B is a 404 under A's path (no existence leak)…
            assert client.get(f"/api/admin/users/{member_a}/registrations/{b1}").status_code == 404
            # …and B's own path shows it, with B's data only.
            own = client.get(f"/api/admin/users/{member_b}/registrations/{b1}").json()
            assert own["account_id"] == member_b and "رضا" in own["registrant_name"] and "سارا" not in repr(own)
            assert client.get(f"/api/admin/users/{member_a}/registrations/{uuid.uuid4()}").status_code == 404
            assert client.get(f"/api/admin/users/{member_a}/registrations/not-a-uuid").status_code == 404
            assert client.get(f"/api/admin/users/{TARGET}/registrations/{a1}").status_code == 404

            # Owner (holds ``finance``) sees amount/currency/transaction id; masking is unchanged.
            client.cookies.clear()
            owner_login(client)
            owner_view = client.get(f"/api/admin/users/{member_a}/registrations/{a1}").json()
            assert owner_view["finance_visible"] is True
            assert owner_view["payment"] == {"status": "receipt_submitted", "method": "card_transfer", "amount": 1_500_000, "currency": "IRR", "transaction_id": "TRX-SECRET-1"}
            assert "09121234567" not in repr(owner_view) and "0012345678" not in repr(owner_view)
            # Existing account-file endpoint is unchanged (summary rows, no answers).
            legacy = client.get(f"/api/admin/users/{member_a}").json()
            assert len(legacy["registration_items"]) == 3 and "answers" not in repr(legacy["registration_items"])
    finally:
        engine.dispose()


def test_registration_list_excludes_companions_and_non_registration_forms_but_includes_verified_bale_legacy_rows():
    app, engine = make_app()
    try:
        with TestClient(app) as client:
            member_a = bale_login(client, 91001)
            client.cookies.clear()
            manager_id = bale_login(client, 91003)
            client.cookies.clear()
            seed_form(engine, "form-file-reg")
            seed_form(engine, "form-file-survey", model="survey", title="نظرسنجی")
            primary = seed_response(engine, form_id="form-file-reg", account_id=member_a)
            seed_response(engine, form_id="form-file-survey", account_id=member_a)
            # Legacy Bale-side row (no account yet) carrying A's verified Bale id → part of A's file.
            legacy = seed_response(engine, form_id="form-file-reg", bale_user_id="91001")
            # Legacy row of another Bale user → never in A's file.
            foreign = seed_response(engine, form_id="form-file-reg", bale_user_id="91002")
            with Session(engine) as db:
                companion = db.scalar(select(FormResponseRecord).where(FormResponseRecord.id == primary))
                # Companions get their own (ownerless) draft, exactly like the public flow.
                child_draft = FormResponseDraftRecord(
                    id=str(uuid.uuid4()), form_id=companion.form_id, form_version=1, token_hash=uuid.uuid4().hex * 2,
                    answers={}, companions=[], expires_at=datetime.now(timezone.utc) + timedelta(days=1),
                )
                db.add(child_draft)
                db.flush()
                db.add(FormResponseRecord(
                    id=str(uuid.uuid4()), form_id=companion.form_id, draft_id=child_draft.id, form_version=1,
                    status="accepted", answers={}, companions=[], form_snapshot=companion.form_snapshot,
                    added_by_response_id=primary, companion_index=1, added_by_name="همراه یک", registrant_name="همراه یک",
                ))
                db.commit()
            assign_manager(client, manager_id)
            listing = client.get(f"/api/admin/users/{member_a}/registrations").json()
            assert {item["id"] for item in listing["items"]} == {primary, legacy} and listing["total"] == 2
            assert foreign not in {item["id"] for item in listing["items"]}
            detail = client.get(f"/api/admin/users/{member_a}/registrations/{primary}").json()
            assert [row["name"] for row in detail["companions"]] == ["همراه یک"] and detail["companions"][0]["ticket_checked_in"] is False
            # The companion row itself is not addressable as a registration of the account.
            companion_id = detail["companions"][0]["id"]
            assert client.get(f"/api/admin/users/{member_a}/registrations/{companion_id}").status_code == 404
            assert client.get(f"/api/admin/users/{member_a}/registrations/{foreign}").status_code == 404
            with Session(engine) as db:
                assert db.scalar(select(FormRecord).where(FormRecord.id == "form-file-reg")).version == 1  # read-only path
    finally:
        engine.dispose()


def test_account_notifications_are_filtered_by_path_account_with_scope_and_delivery_state():
    app, engine = make_app()
    try:
        with TestClient(app) as client:
            member_a = bale_login(client, 91001)
            client.cookies.clear()
            member_b = bale_login(client, 91002)
            client.cookies.clear()
            manager_id = bale_login(client, 91003)
            client.cookies.clear()
            with Session(engine) as db:
                notifications_mod.queue(db, account_id=member_a, kind="receipt_approved", title="فیش تأیید شد",
                                        body="پرداخت شما ثبت شد.", key="t:a:1", bale_ids=["91001"], link="/account.html#registrations")
                fan = notifications_mod.fan_out(
                    db, account_ids=[member_a, member_b], kind=notifications_mod.KIND_CONTENT_PUBLISHED,
                    title="محتوای تازه", body="جلسهٔ تازه منتشر شد.", key_for=lambda acc: f"t:content:{acc}",
                    bale_ids_for=lambda acc: ["91001"] if acc == member_a else ["91002"], link="/event.html?id=ev-1#recording",
                )
                assert len(fan) == 2
                notifications_mod.queue(db, account_id=member_b, kind="profile_rejected", title="پروفایل رد شد",
                                        body="مدرک ناخوانا بود — فقط برای ب.", key="t:b:1", bale_ids=["91002"])
                # A row without a Bale identity stays an honest, distinct failure.
                orphan, _ = notifications_mod.queue(db, account_id=member_a, kind="certificate", title="گواهی",
                                                    body="گواهی صادر شد.", key="t:a:2", bale_ids=[])
                orphan_id = orphan.id
                delivered = db.scalar(select(UserNotificationRecord).where(UserNotificationRecord.dedupe_key == "t:a:1"))
                delivered.delivery_status = "delivered"
                delivered.delivery_attempts = 1
                db.commit()

            assert client.get(f"/api/admin/users/{member_a}/notifications").status_code == 401
            relogin(client, 91001, "notif")
            assert client.get(f"/api/admin/users/{member_a}/notifications").status_code == 403  # own id, no us_view
            client.cookies.clear()
            assign_manager(client, manager_id)
            listing = client.get(f"/api/admin/users/{member_a}/notifications?limit=2")
            assert listing.status_code == 200, listing.text
            body = listing.json()
            assert body["account_id"] == member_a and body["total"] == 3 and body["has_more"] is True and len(body["items"]) == 2
            assert "no-store" in listing.headers["cache-control"]
            rest = client.get(f"/api/admin/users/{member_a}/notifications?limit=2&offset=2").json()
            assert rest["has_more"] is False and len(rest["items"]) == 1
            rows = {row["kind"]: row for row in body["items"] + rest["items"]}
            assert set(rows) == {"receipt_approved", "recording_content", "certificate"}
            assert rows["receipt_approved"]["scope"] == "account" and rows["receipt_approved"]["delivery_state"] == "delivered"
            assert rows["receipt_approved"]["delivered_at"] is None and rows["receipt_approved"]["link"] == "/account.html#registrations"
            assert rows["recording_content"]["scope"] == "audience" and rows["recording_content"]["delivery_state"] == "queued"
            assert rows["certificate"]["delivery_state"] == "failed" and rows["certificate"]["last_delivery_error"] == "no_bale_identity"
            assert rows["certificate"]["has_bale_identity"] is False and rows["receipt_approved"]["has_bale_identity"] is True
            flat = repr(body) + repr(rest)
            assert "فقط برای ب" not in flat and "profile_rejected" not in flat  # B's private row never appears under A
            for row in rows.values():
                assert "bale_user_id" not in row and "file_refs" not in row and "account_label" not in row
            # B sees only B's rows (its private one + the audience one), nothing of A.
            b_rows = client.get(f"/api/admin/users/{member_b}/notifications").json()
            assert {row["kind"] for row in b_rows["items"]} == {"profile_rejected", "recording_content"} and b_rows["total"] == 2
            assert "فیش تأیید شد" not in repr(b_rows)
            # Empty, unknown, invalid.
            assert client.get(f"/api/admin/users/{manager_id}/notifications").json()["items"] == []
            assert client.get(f"/api/admin/users/{TARGET}/notifications").status_code == 404
            assert client.get("/api/admin/users/nope/notifications").status_code == 404
            assert client.get(f"/api/admin/users/{member_a}/notifications?limit=0").status_code == 422
            # Read-only: nothing changed, and the global queue (rp_view) still lists every row.
            with Session(engine) as db:
                assert db.scalar(select(UserNotificationRecord).where(UserNotificationRecord.id == orphan_id)).delivery_status == "failed"
            assert len(client.get("/api/admin/notifications?limit=100").json()["items"]) == 5
    finally:
        engine.dispose()
