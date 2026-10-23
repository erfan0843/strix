"""پروندهٔ رویداد (مأموریت ۱۴۰۵/۰۸/۰۱): نماهای خواندنیِ حول یک رویداد.

* ``overview``: فرم‌های وصل‌شده به همین رویداد (نه رویداد دیگر)، ظرفیت/قیمت از تنظیمات فرم اصلی، شمارنده‌های سروری.
* ``registrations``: فهرست و خلاصه از همان ردیف‌ها؛ صافی‌ها؛ ثبت‌نام رویداد B در A نیست؛ پروندهٔ فرد با شناسهٔ رویداد دیگر ۴۰۴.
* ``payment-decision``: فقط ``receipt_approve``؛ دلیل الزامی؛ تأیید → ``paid_manual``؛ تکرار بدون تغییر؛ رد → لغو ثبت‌نام؛ ممیزی.
* مجوزها: بدون نشست ۴۰۱؛ حساب بی‌نقش ۴۰۳؛ مدیر مبلغ نمی‌بیند (``finance`` فقط مالک).
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import (  # noqa: E402
    AdminAuditEventRecord, Base, FormPaymentRecord, FormRegistrationCancellationRecord, FormResponseRecord,
)
from backend.security import hash_password  # noqa: E402

from test_event_registration_gate import create_published_event  # noqa: E402
from test_form_responses_export import install_account_session  # noqa: E402
from test_forms_api import _public_receipt_png  # noqa: E402
from test_workflows_api import BOT_TOKEN, SERVICE_TOKEN, owner_login, owner_write_headers  # noqa: E402

ORIGIN = {"Origin": "http://testserver"}


def make_client() -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None, owner_id="owner-01", owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"), cookie_secure=False,
        bale_bot_token=BOT_TOKEN, bot_service_token=SERVICE_TOKEN, owner_bale_user_id="70001",
    )
    return TestClient(create_app(settings, engine=engine))


def create_form(client: TestClient, *, event_id: str, key: str, model: str = "registration", need: str = "reg",
                name: str = "فرم ثبت‌نام", settings: dict | None = None, publish: bool = True, fields: list | None = None) -> str:
    payload = {
        "name": name, "model": model, "need": need, "ev": event_id, "settings": settings or {},
        "fields": fields or [{"id": "full-name", "t": "fullname", "l": "نام کامل", "required": True}],
    }
    created = client.post("/api/forms", json=payload, headers={**owner_write_headers(client), "Idempotency-Key": key})
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    if publish:
        published = client.post(f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=owner_write_headers(client))
        assert published.status_code == 200, published.text
    return form_id


def register(app, form_id: str, name: str, *, pay: bool = False, receipt: bool = False) -> tuple[TestClient, dict]:
    visitor = TestClient(app)
    assert visitor.get(f"/api/public/forms/{form_id}/draft").status_code == 200
    body: dict = {"answers": {"full-name": name}}
    if pay:
        body["payment"] = {"method": "card_transfer", "selection": {"items": [0], "coupon_code": ""}}
    submitted = visitor.post(f"/api/public/forms/{form_id}/responses", json=body, headers=ORIGIN)
    assert submitted.status_code == 200, submitted.text
    if receipt:
        uploaded = visitor.post(
            f"/api/public/forms/{form_id}/receipt", content=_public_receipt_png(),
            headers={**ORIGIN, "Content-Type": "image/png", "X-File-Name": "receipt.png"},
        )
        assert uploaded.status_code == 200, uploaded.text
    return visitor, submitted.json()


PAID_SETTINGS = {
    "cap": 3, "wait": 0,
    "enabledPaymentMethods": ["card_transfer"], "receiptReviewRequired": True,
    "fin": [{"l": "ورودی", "p": 500000, "off": 0, "req": True, "d": ""}],
    "paymentCard": {"number": "4111111111111111", "bank": "بانک نمونه", "holder": "حساب سازمان"},
}


def test_overview_scopes_forms_to_the_event_and_reads_capacity_and_price_from_the_form():
    with make_client() as client:
        owner_login(client)
        event_a, version = create_published_event(client, 0, t="رویداد الف", cap=99, price=1)
        event_b, version = create_published_event(client, version, t="رویداد ب")
        reg_a = create_form(client, event_id=event_a, key="ef-reg-a-0000000000000000", settings=PAID_SETTINGS)
        survey_a = create_form(client, event_id=event_a, key="ef-survey-a-0000000000000000", model="survey", need="survey", name="نظرسنجی الف",
                               fields=[{"id": "q1", "t": "choice", "l": "رضایت", "options": ["کم", "زیاد"]}])
        create_form(client, event_id=event_b, key="ef-reg-b-0000000000000000", name="فرم ب")
        create_form(client, event_id="", key="ef-public-0000000000000000", name="فرم عمومی")

        overview = client.get(f"/api/admin/events/{event_a}/overview")
        assert overview.status_code == 200, overview.text
        body = overview.json()
        assert {f["id"] for f in body["forms"]} == {reg_a, survey_a}, "فقط فرم‌های همین رویداد"
        assert {f["type"] for f in body["forms"]} == {"registration", "survey"}
        settings = body["registration_settings"]
        assert settings["form_id"] == reg_a and settings["source"] == "form_settings"
        assert settings["cap"] == 3 and settings["price"]["base"] == 500000 and settings["price"]["paid"] is True
        assert settings["methods"] == ["card_transfer"] and settings["receipt_review_required"] is True
        # مقدار اعلامی رویداد جدا و بازنویسی‌نشده می‌ماند
        assert body["declared"] == {"cap": 99, "price": 1}
        assert body["counts"]["total"] == 0 and body["counts"]["remaining"] == 3 and body["counts"]["cap"] == 3
        # صفحهٔ عمومی همان منبع را نشان می‌دهد (نه مقدار اعلامی رویداد)
        public = next(row for row in client.get("/api/public/site-content").json()["content"]["events"] if row["id"] == event_a)
        assert public["cap"] == 3 and public["price"] == 500000
        assert public["pricing"] == {"source": "form", "form_id": reg_a, "base": 500000, "has_optional": False, "paid": True, "valid": True}
        public_b = next(row for row in client.get("/api/public/site-content").json()["content"]["events"] if row["id"] == event_b)
        assert "pricing" not in public_b or public_b["pricing"]["form_id"] != reg_a
        assert body["event"]["registration"]["state"] == "open"
        assert body["can"]["finance"] is True

        assert client.get("/api/admin/events/no-such-event/overview").status_code == 404
        assert client.get("/api/admin/events/../overview").status_code in (404, 422)

        # فرم رویداد ب را از مسیر رویداد الف نمی‌توان خواند
        other = client.get(f"/api/admin/events/{event_a}/forms/{create_form(client, event_id=event_b, key='ef-survey-b-000000000000000', model='survey', need='survey')}/summary")
        assert other.status_code == 404


def test_registrations_list_summary_filters_person_file_and_cross_event_isolation():
    with make_client() as client:
        owner_login(client)
        event_a, version = create_published_event(client, 0, t="رویداد الف")
        event_b, version = create_published_event(client, version, t="رویداد ب")
        reg_a = create_form(client, event_id=event_a, key="ef-reg-a2-0000000000000000", settings=PAID_SETTINGS)
        reg_b = create_form(client, event_id=event_b, key="ef-reg-b2-0000000000000000")
        register(client.app, reg_a, "سارا پرداخت‌نکرده", pay=True)
        register(client.app, reg_a, "مینا با رسید", pay=True, receipt=True)
        register(client.app, reg_b, "کاربر رویداد ب")

        listed = client.get(f"/api/admin/events/{event_a}/registrations")
        assert listed.status_code == 200, listed.text
        body = listed.json()
        names = {item["name"] for item in body["items"]}
        assert names == {"سارا پرداخت‌نکرده", "مینا با رسید"}, "ثبت‌نام رویداد ب در الف نیست"
        assert body["summary"]["total"] == 2 and body["summary"]["accepted"] == 2
        assert body["summary"]["pending_payment"] == 2 and body["summary"]["paid"] == 0
        assert body["summary"]["remaining"] == 1 and body["summary"]["cap"] == 3
        assert body["finance_visible"] is True and all("amount" in item for item in body["items"])
        by_name = {item["name"]: item for item in body["items"]}
        assert by_name["مینا با رسید"]["receipt_uploaded"] is True and by_name["مینا با رسید"]["payment_status"] == "receipt_submitted"
        assert by_name["سارا پرداخت‌نکرده"]["receipt_uploaded"] is False and by_name["سارا پرداخت‌نکرده"]["payment_status"] == "awaiting_receipt"
        assert "mobile" not in by_name["مینا با رسید"] and "answers" not in by_name["مینا با رسید"]

        assert client.get(f"/api/admin/events/{event_a}/registrations?payment=paid").json()["total"] == 0
        assert client.get(f"/api/admin/events/{event_a}/registrations?payment=unpaid").json()["total"] == 2
        assert client.get(f"/api/admin/events/{event_a}/registrations?q=مینا").json()["total"] == 1
        assert client.get(f"/api/admin/events/{event_a}/registrations?attendance=checked_in").json()["total"] == 0
        assert client.get(f"/api/admin/events/{event_a}/registrations?form_id={reg_b}").status_code == 404
        assert client.get(f"/api/admin/events/{event_a}/registrations?limit=1").json()["has_more"] is True

        rid = by_name["مینا با رسید"]["response_id"]
        detail = client.get(f"/api/admin/events/{event_a}/registrations/{rid}")
        assert detail.status_code == 200, detail.text
        person = detail.json()
        assert person["registrant_name"] == "مینا با رسید" and person["event_id"] == event_a
        assert [a["label"] for a in person["answers"]] == ["نام کامل"]
        assert person["payment"]["status"] == "receipt_submitted" and person["payment"]["amount"] == 500000
        assert person["payment_state"] == "pending" and person["receipt"]["web_file"] is True
        assert person["can"]["payment_decision"] is True and person["can"]["receipt_file"] is True
        assert person["ticket"]["eligible"] is True and person["can"]["ticket_image"] is False, "بلیت پیش از تأیید پرداخت ساخته نمی‌شود"
        # همان شناسه از مسیر رویداد ب ۴۰۴ است (نه ۴۰۳، نه نشت)
        assert client.get(f"/api/admin/events/{event_b}/registrations/{rid}").status_code == 404
        assert client.get(f"/api/admin/events/{event_b}/registrations/{rid}/receipt").status_code == 404
        receipt = client.get(f"/api/admin/events/{event_a}/registrations/{rid}/receipt")
        assert receipt.status_code == 200 and receipt.headers["content-type"].startswith("image/png")
        assert "no-store" in receipt.headers["cache-control"]
        rid_unpaid = by_name["سارا پرداخت‌نکرده"]["response_id"]
        assert client.get(f"/api/admin/events/{event_a}/registrations/{rid_unpaid}/receipt").status_code == 404
        assert client.get(f"/api/admin/events/{event_a}/registrations/{rid}/ticket-image").status_code == 409


def test_payment_decision_is_audited_idempotent_and_updates_counts_and_ticket():
    with make_client() as client:
        owner_login(client)
        event_a, _version = create_published_event(client, 0, t="رویداد الف")
        reg_a = create_form(client, event_id=event_a, key="ef-reg-a3-0000000000000000", settings=PAID_SETTINGS)
        register(client.app, reg_a, "مینا با رسید", pay=True, receipt=True)
        register(client.app, reg_a, "رضا رد‌شده", pay=True, receipt=True)
        rows = {item["name"]: item for item in client.get(f"/api/admin/events/{event_a}/registrations").json()["items"]}
        rid, rid_reject = rows["مینا با رسید"]["response_id"], rows["رضا رد‌شده"]["response_id"]
        url = f"/api/admin/events/{event_a}/registrations/{rid}/payment-decision"

        no_csrf = client.post(url, json={"decision": "approved", "reason": "x"}, headers=ORIGIN)
        assert no_csrf.status_code == 403
        no_reason = client.post(url, json={"decision": "approved", "reason": ""}, headers=owner_write_headers(client))
        assert no_reason.status_code == 422 and no_reason.json()["detail"]["code"] == "reason_required"
        stale = client.post(url, json={"decision": "approved", "reason": "تطبیق شد", "expected_status": "awaiting_receipt"},
                            headers=owner_write_headers(client))
        assert stale.status_code == 409 and stale.json()["detail"]["code"] == "payment_status_changed"

        approved = client.post(url, json={"decision": "approved", "reason": "مبلغ با رسید تطبیق داده شد", "expected_status": "receipt_submitted"},
                               headers=owner_write_headers(client))
        assert approved.status_code == 200, approved.text
        assert approved.json() == {"changed": True, "payment_status": "paid_manual", "via": "payment", "registration_cancelled": False}
        again = client.post(url, json={"decision": "approved", "reason": "تکرار"}, headers=owner_write_headers(client))
        assert again.status_code == 200 and again.json()["changed"] is False, "تکرار درخواست بدون تغییر"
        reverse = client.post(url, json={"decision": "rejected", "reason": "اشتباه"}, headers=owner_write_headers(client))
        assert reverse.status_code == 409, "برگرداندن پرداخت تأییدشده عملیات مالی است و از این‌جا انجام نمی‌شود"

        summary = client.get(f"/api/admin/events/{event_a}/registrations").json()["summary"]
        assert summary["paid"] == 1 and summary["pending_payment"] == 1
        person = client.get(f"/api/admin/events/{event_a}/registrations/{rid}").json()
        assert person["payment_state"] == "paid" and person["payment_approved"] is True and person["can"]["ticket_image"] is True
        assert any(a["action"] == "payment.manual_decision" for a in person["audit"])
        with client.app.state.session_factory() as db:
            audit = db.scalar(select(AdminAuditEventRecord).where(AdminAuditEventRecord.action == "payment.manual_decision"))
            assert audit is not None and audit.details["previous_status"] == "receipt_submitted"
            assert audit.details["new_status"] == "paid_manual" and audit.details["reason"] == "مبلغ با رسید تطبیق داده شد"
        ticket = client.get(f"/api/admin/events/{event_a}/registrations/{rid}/ticket-image")
        assert ticket.status_code in (200, 503), ticket.text  # ۵۰۳ فقط اگر رندرکنندهٔ تصویر در محیط آزمون نباشد
        if ticket.status_code == 200:
            assert ticket.headers["content-type"] == "image/jpeg" and "no-store" in ticket.headers["cache-control"]

        payments = client.get(f"/api/admin/events/{event_a}/payments")
        assert payments.status_code == 200, payments.text
        assert payments.json()["totals"] == {"paid_amount": 500000, "paid": 1, "pending": 1, "failed": 0}
        assert {p["name"] for p in payments.json()["items"]} == {"مینا با رسید", "رضا رد‌شده"}
        assert client.get(f"/api/admin/events/{event_a}/payments?state=paid").json()["total"] == 1

        rejected = client.post(f"/api/admin/events/{event_a}/registrations/{rid_reject}/payment-decision",
                               json={"decision": "rejected", "reason": "رسید ناخوانا"}, headers=owner_write_headers(client))
        assert rejected.status_code == 200 and rejected.json()["registration_cancelled"] is True
        after = client.get(f"/api/admin/events/{event_a}/registrations").json()
        assert after["summary"]["total"] == 1 and after["summary"]["remaining"] == 2, "ظرفیت پس از لغو آزاد می‌شود"
        assert client.get(f"/api/admin/events/{event_a}/registrations/{rid_reject}").status_code == 404
        with client.app.state.session_factory() as db:
            kept = db.scalars(select(FormPaymentRecord).where(FormPaymentRecord.status == "rejected")).all()
            assert len(kept) == 1 and kept[0].response_id is None, "ردیف مالی حذف نمی‌شود؛ فقط از ثبت‌نام جدا می‌شود"
            assert db.scalar(select(FormResponseRecord).where(FormResponseRecord.id == rid_reject)) is None
        assert client.get(f"/api/admin/events/{event_a}/payments").json()["totals"]["failed"] == 1


COMPANION_FIELDS = [
    {"id": "full-name", "t": "fullname", "l": "نام کامل", "required": True},
    {"id": "mobile", "t": "mobile", "l": "شمارهٔ همراه", "required": True},
]


def test_cancelled_registration_keeps_an_auditable_snapshot_and_removes_companions():
    """رد رسید: ردیف زنده حذف و صندلی آزاد می‌شود، همراهان هم می‌روند، اما هویت/پاسخ‌ها/سابقهٔ مالی/رسید
    در عکس‌برداری لغو می‌ماند و فقط با مجوز و با ثبت ممیزی خوانده می‌شود."""
    with make_client() as client:
        owner_login(client)
        event_a, _ = create_published_event(client, 0, t="رویداد همراه‌دار")
        event_b, _ = create_published_event(client, 1, t="رویداد دیگر")
        settings = {**PAID_SETTINGS, "guestsOn": True, "maxPer": 3, "compFields": "name-mobile-answers"}
        reg = create_form(client, event_id=event_a, key="ef-cancel-0000000000000000", settings=settings, fields=COMPANION_FIELDS)

        visitor = TestClient(client.app)
        assert visitor.get(f"/api/public/forms/{reg}/draft").status_code == 200
        submitted = visitor.post(
            f"/api/public/forms/{reg}/responses",
            json={"answers": {"full-name": "سارا اصلی", "mobile": "09121110000"},
                  "companions": [{"name": "نیما همراه", "mobile": "09121234567",
                                  "answers": {"full-name": "نیما همراه", "mobile": "09121234567"}}],
                  "payment": {"method": "card_transfer", "selection": {"items": [0], "coupon_code": ""}}},
            headers=ORIGIN,
        )
        assert submitted.status_code == 200, submitted.text
        receipt_png = _public_receipt_png()
        assert visitor.post(f"/api/public/forms/{reg}/receipt", content=receipt_png,
                            headers={**ORIGIN, "Content-Type": "image/png", "X-File-Name": "receipt.png"}).status_code == 200

        before = client.get(f"/api/admin/events/{event_a}/registrations").json()
        assert before["summary"]["total"] == 2 and {i["companion"] for i in before["items"]} == {True, False}
        rid = next(i["response_id"] for i in before["items"] if not i["companion"])
        assert client.get(f"/api/admin/events/{event_a}/cancellations").json()["total"] == 0

        rejected = client.post(f"/api/admin/events/{event_a}/registrations/{rid}/payment-decision",
                               json={"decision": "rejected", "reason": "رسید ناخوانا"}, headers=owner_write_headers(client))
        assert rejected.status_code == 200 and rejected.json()["registration_cancelled"] is True

        after = client.get(f"/api/admin/events/{event_a}/registrations").json()
        assert after["summary"]["total"] == 0 and after["summary"]["remaining"] == 3, "همراه با ثبت‌نام اصلی می‌رود و صندلی‌ها آزاد می‌شوند"
        with client.app.state.session_factory() as db:
            assert db.scalar(select(FormResponseRecord).where(FormResponseRecord.form_id == reg)) is None
            snap = db.scalar(select(FormRegistrationCancellationRecord).where(FormRegistrationCancellationRecord.response_id == rid))
            assert snap is not None
            assert snap.event_id == event_a and snap.form_id == reg and snap.source == "event_file"
            assert snap.display_name == "سارا اصلی" and snap.answers["mobile"] == "09121110000" and snap.status_before == "accepted"
            assert [c["name"] for c in snap.companions] == ["نیما همراه"] and snap.companions[0]["answers"]["mobile"] == "09121234567"
            assert snap.amount == 1000000 and snap.payment_method == "card_transfer"  # دو نفر × ۵۰۰٬۰۰۰ and snap.payment_status_before == "receipt_submitted"
            assert snap.receipt_content == receipt_png and snap.receipt_content_type == "image/png"
            assert snap.reason == "رسید ناخوانا" and snap.actor_kind == "owner" and snap.actor_role == "owner"
            payment = db.get(FormPaymentRecord, snap.payment_id)
            assert payment is not None and payment.status == "rejected" and payment.response_id is None
            cancel_audit = db.scalar(select(AdminAuditEventRecord).where(AdminAuditEventRecord.action == "registration.cancel"))
            assert cancel_audit is not None and cancel_audit.details["cancellation_id"] == snap.id
            assert cancel_audit.details["companions"] == 1 and cancel_audit.target_id == rid
            snap_id = snap.id

        # ردیف مالی جداشده در فهرست پرداخت‌ها نام و پیوند لغو را از عکس‌برداری می‌گیرد
        pay_rows = client.get(f"/api/admin/events/{event_a}/payments").json()["items"]
        assert len(pay_rows) == 1 and pay_rows[0]["response_id"] is None
        assert pay_rows[0]["name"] == "سارا اصلی" and pay_rows[0]["registration_status"] == "cancelled"
        assert pay_rows[0]["cancellation"]["id"] == snap_id and pay_rows[0]["cancellation"]["reason"] == "رسید ناخوانا"

        # مالک: پاسخ‌ها + مبلغ؛ خواندن ممیزی می‌شود
        listed = client.get(f"/api/admin/events/{event_a}/cancellations")
        assert listed.status_code == 200 and "no-store" in listed.headers["cache-control"]
        item = listed.json()["items"][0]
        assert listed.json()["total"] == 1 and item["id"] == snap_id and item["name"] == "سارا اصلی"
        by_label = {a["label"]: a for a in item["answers"]}
        assert by_label["نام کامل"]["value"] == "سارا اصلی", "پاسخ‌ها با برچسب فارسی فیلد برمی‌گردند"
        assert by_label["شمارهٔ همراه"]["masked"] == "mobile" and by_label["شمارهٔ همراه"]["hint"] == "0000", "شماره مانند پروندهٔ زنده پنهان می‌شود"
        companion_mobile = next(a for a in item["companions"][0]["answers"] if a["field_id"] == "mobile")
        assert companion_mobile["masked"] == "mobile" and companion_mobile["hint"] == "4567"
        assert item["payment"]["amount"] == 1000000 and item["receipt"] == {"stored": True, "web_file": True, "file_refs": []}
        assert client.get(f"/api/admin/events/{event_a}/cancellations?q=سارا").json()["total"] == 1
        assert client.get(f"/api/admin/events/{event_a}/cancellations?q=نیست").json()["total"] == 0
        receipt = client.get(f"/api/admin/events/{event_a}/cancellations/{snap_id}/receipt")
        assert receipt.status_code == 200 and receipt.content == receipt_png and "no-store" in receipt.headers["cache-control"]
        # رویداد دیگر: ۴۰۴ (بدون نشت بین رویدادها)
        assert client.get(f"/api/admin/events/{event_b}/cancellations").json()["total"] == 0
        assert client.get(f"/api/admin/events/{event_b}/cancellations/{snap_id}/receipt").status_code == 404
        with client.app.state.session_factory() as db:
            views = db.scalars(select(AdminAuditEventRecord).where(AdminAuditEventRecord.action == "registration.cancellations.view")).all()
            assert len(views) >= 3 and views[-1].details["with_answers"] is True
            assert db.scalar(select(AdminAuditEventRecord).where(AdminAuditEventRecord.action == "registration.cancellation.receipt_view")) is not None

        # مدیر (بدون مجوز مالی): نام و پاسخ‌ها بله، مبلغ نه؛ حساب بی‌نقش ۴۰۳؛ بدون نشست ۴۰۱
        client.cookies.clear()
        assert client.get(f"/api/admin/events/{event_a}/cancellations").status_code == 401
        assert client.get(f"/api/admin/events/{event_a}/cancellations/{snap_id}/receipt").status_code == 401
        install_account_session(client, "11111111-1111-4111-8111-111111111111", None)
        assert client.get(f"/api/admin/events/{event_a}/cancellations").status_code == 403
        client.cookies.clear()
        install_account_session(client, "22222222-2222-4222-8222-222222222222", "manager")
        as_manager = client.get(f"/api/admin/events/{event_a}/cancellations")
        assert as_manager.status_code == 200 and as_manager.json()["finance_visible"] is False
        manager_item = as_manager.json()["items"][0]
        assert manager_item["name"] == "سارا اصلی" and "amount" not in manager_item["payment"]
        assert [a["label"] for a in manager_item["answers"]] == ["نام کامل", "شمارهٔ همراه"]
        assert client.get(f"/api/admin/events/{event_a}/cancellations/{snap_id}/receipt").status_code == 200


def test_owner_delete_response_also_keeps_the_snapshot():
    with make_client() as client:
        owner_login(client)
        event_a, _ = create_published_event(client, 0, t="رویداد حذف")
        reg = create_form(client, event_id=event_a, key="ef-delete-0000000000000000", settings={"cap": 3, "wait": 0})
        register(client.app, reg, "حذف‌شده")
        rid = client.get(f"/api/admin/events/{event_a}/registrations").json()["items"][0]["response_id"]
        deleted = client.delete(f"/api/forms/{reg}/responses/{rid}", headers=owner_write_headers(client))
        assert deleted.status_code == 200, deleted.text
        assert client.get(f"/api/admin/events/{event_a}/registrations").json()["summary"]["total"] == 0
        listed = client.get(f"/api/admin/events/{event_a}/cancellations").json()
        assert listed["total"] == 1 and listed["items"][0]["source"] == "owner_delete" and listed["items"][0]["name"] == "حذف‌شده"
        assert listed["items"][0]["payment"] is None and listed["items"][0]["receipt"]["stored"] is False


def test_form_summary_aggregates_choices_and_permissions_are_server_side():
    with make_client() as client:
        owner_login(client)
        event_a, _version = create_published_event(client, 0, t="رویداد الف")
        survey = create_form(client, event_id=event_a, key="ef-survey-sum-0000000000000000", model="survey", need="survey", name="نظرسنجی",
                             fields=[{"id": "q1", "t": "choice", "l": "رضایت", "options": ["کم", "زیاد"]},
                                     {"id": "q2", "t": "number", "l": "نمره"}])
        for choice, score in (("زیاد", "4"), ("زیاد", "5"), ("کم", "1")):
            visitor = TestClient(client.app)
            assert visitor.get(f"/api/public/forms/{survey}/draft").status_code == 200
            sent = visitor.post(f"/api/public/forms/{survey}/responses", json={"answers": {"q1": choice, "q2": score}}, headers=ORIGIN)
            assert sent.status_code == 200, sent.text
        summary = client.get(f"/api/admin/events/{event_a}/forms/{survey}/summary")
        assert summary.status_code == 200, summary.text
        body = summary.json()
        assert body["responses"] == 3 and body["scoring"] is None
        q1 = next(f for f in body["fields"] if f["field_id"] == "q1")
        assert q1["options"] == [{"label": "کم", "count": 1}, {"label": "زیاد", "count": 2}]
        q2 = next(f for f in body["fields"] if f["field_id"] == "q2")
        assert q2["kind"] == "numeric" and q2["mean"] == 3.33 and q2["min"] == 1 and q2["max"] == 5
        assert client.get(f"/api/admin/events/{event_a}/forms/missing/summary").status_code == 404

        # مدیر: می‌خواند اما مبلغ و پرداخت‌ها را نه؛ حساب بی‌نقش: ۴۰۳؛ بدون نشست: ۴۰۱
        client.cookies.clear()
        assert client.get(f"/api/admin/events/{event_a}/overview").status_code == 401
        install_account_session(client, "11111111-1111-4111-8111-111111111111", None)
        assert client.get(f"/api/admin/events/{event_a}/overview").status_code == 403
        assert client.get(f"/api/admin/events/{event_a}/registrations").status_code == 403
        client.cookies.clear()
        install_account_session(client, "22222222-2222-4222-8222-222222222222", "manager")
        overview = client.get(f"/api/admin/events/{event_a}/overview")
        assert overview.status_code == 200 and overview.json()["can"]["finance"] is False and overview.json()["can"]["receipts"] is True
        listed = client.get(f"/api/admin/events/{event_a}/registrations")
        assert listed.status_code == 200 and listed.json()["finance_visible"] is False
        assert client.get(f"/api/admin/events/{event_a}/payments").status_code == 403, "مبلغ‌ها فقط با مجوز مالی"
        assert client.get(f"/api/admin/events/{event_a}/forms/{survey}/summary").status_code == 200


def test_phone_user_session_is_locked_out_of_the_event_file(monkeypatch):
    """A signed-in public user (phone OTP) is not staff: every event-file route answers 403, never data.

    Browser coverage of this role is impossible in the sandbox (OTP delivery needs the SMS gateway), so the
    permission boundary is pinned here with the same app wiring the owner/manager tests use."""
    from test_phone_otp_auth import CODE, make_client as make_otp_client, request_code, verify_code

    client, _engine, _sends = make_otp_client(monkeypatch=monkeypatch)
    with client:
        challenge = request_code(client).json()
        assert verify_code(client, challenge["challenge_id"], CODE).status_code == 200
        me = client.get("/api/account/me").json()
        assert me.get("authenticated") is True and me.get("role") not in ("owner", "manager")
        event_id, response_id, form_id = "ev-anything", "resp-anything", "form-anything"
        reads = [
            f"/api/admin/events/{event_id}/overview",
            f"/api/admin/events/{event_id}/registrations",
            f"/api/admin/events/{event_id}/registrations/{response_id}",
            f"/api/admin/events/{event_id}/registrations/{response_id}/receipt",
            f"/api/admin/events/{event_id}/registrations/{response_id}/ticket-image",
            f"/api/admin/events/{event_id}/payments",
            f"/api/admin/events/{event_id}/forms/{form_id}/summary",
        ]
        for path in reads:
            response = client.get(path)
            assert response.status_code == 403, (path, response.status_code, response.text[:200])
            assert "items" not in response.text and "receipt" not in response.headers.get("content-type", "")
        decision = client.post(
            f"/api/admin/events/{event_id}/registrations/{response_id}/payment-decision",
            json={"decision": "approved", "reason": "کاربر عادی"},
            headers={"Origin": "http://testserver", "X-CSRF-Token": client.cookies.get("nora_account_csrf", "")},
        )
        assert decision.status_code == 403, decision.text[:200]
