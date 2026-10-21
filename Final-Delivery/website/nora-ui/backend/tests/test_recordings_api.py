"""Phase 9: recorded-content products, orders, access rights and the Bale webhook branch.

The suite exercises the acceptance scenarios of the phase-9 brief end to end over
the HTTP API: a held workshop gets a product (sessions + purchased-only files),
goes on sale only once the server-side blockers are cleared, a non-attendee buys
access by card transfer (receipt → reviewer decision) or Bale wallet (verified
webhook only), access is decided per download on the server, refunds revoke,
free products are claimed without a fake transaction, manual grants are audited,
drafts stay invisible and other accounts never see each other's orders.

Everything runs against an in-memory SQLite database with synthetic accounts;
the Bale payment API is replaced by an in-process fake (no outbound calls).
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend import app as backend_app  # noqa: E402
from backend import recordings  # noqa: E402
from backend.app import _form_payment_webhook_token, create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import (  # noqa: E402
    AdminAuditEventRecord,
    Base,
    FormResponseRecord,
    RecordingAccessRecord,
    RecordingOrderRecord,
    UserNotificationRecord,
)
from backend.security import hash_password  # noqa: E402

from test_event_interaction_api import audit_actions, interaction  # noqa: E402
from test_event_registration_gate import (  # noqa: E402
    create_published_event,
    create_published_form,
    gate_app,
    iso,
    public_event,
    update_event,
)
from test_workflows_api import (  # noqa: E402
    BOT_TOKEN,
    SERVICE_TOKEN,
    account_write_headers,
    assign_manager,
    bale_login,
    owner_login,
    owner_write_headers,
)

MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64
PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
CARD = {"number": "6037997599999993", "bank": "بانک آزمایشی", "holder": "نورا"}
PAYMENT_BOT_TOKEN = "1234567890:" + "A" * 32
PAYMENT_PROVIDER_TOKEN = "provider-test-token-not-a-real-credential"
PAYMENT_WEBHOOK_SECRET = "w" * 48
PAYMENT_WEBHOOK_BASE = "https://forms.nora.ir/api/payments/bale/webhook"


def held_event(owner: TestClient, version: int, **overrides) -> tuple[str, int]:
    base = {"t": "کارگاه برگزارشدهٔ فاز ۹", "startsAt": iso(timedelta(days=-9)), "endsAt": iso(timedelta(days=-8)),
            "regClosesAt": iso(timedelta(days=-10)), "past": True}
    base.update(overrides)
    return create_published_event(owner, version, **base)


def put_recording(owner: TestClient, event_id: str, **fields):
    return owner.put(f"/api/admin/events/{event_id}/recording", json=fields, headers=owner_write_headers(owner))


def set_status(client: TestClient, event_id: str, status: str, reason: str = "", headers=None):
    body = {"status": status}
    if reason:
        body["reason"] = reason
    return client.post(f"/api/admin/events/{event_id}/recording/status", json=body, headers=headers or owner_write_headers(client))


def build_sellable_product(owner: TestClient, event_id: str, **fields) -> dict:
    """Product + one published session + one live purchased-only video; returns the admin view."""
    defaults = {"title": "نسخهٔ ضبط‌شدهٔ کارگاه", "summary": "سه ساعت ویدیو و جزوه", "price": 1_500_000, "payment_card": CARD,
                "access_terms": "دسترسی نامحدود، قابل مشاهده در صفحهٔ رویداد", "refund_policy": "تا ۴۸ ساعت پس از خرید"}
    defaults.update(fields)
    created = put_recording(owner, event_id, **defaults)
    assert created.status_code == 200, created.text
    session = owner.post(f"/api/admin/events/{event_id}/recording/sessions",
                         json={"title": "جلسهٔ اول: مقدمات", "duration_minutes": 55}, headers=owner_write_headers(owner))
    assert session.status_code == 201, session.text
    session_id = session.json()["id"]
    resource = owner.post(f"/api/admin/events/{event_id}/resources",
                          json={"title": "ویدیوی جلسهٔ اول", "access": "purchased", "session_id": session_id, "delivery": "view"},
                          headers=owner_write_headers(owner))
    assert resource.status_code == 201, resource.text
    resource_id = resource.json()["id"]
    uploaded = owner.put(f"/api/admin/events/{event_id}/resources/{resource_id}/file", content=MP4,
                         headers={**owner_write_headers(owner), "X-File-Name": quote("جلسه ۱.mp4")})
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["content_type"] == "video/mp4" and uploaded.json()["file_name"] == "جلسه ۱.mp4"
    assert owner.put(f"/api/admin/events/{event_id}/resources/{resource_id}", json={"status": "published"},
                     headers=owner_write_headers(owner)).status_code == 200
    assert owner.put(f"/api/admin/events/{event_id}/recording/sessions/{session_id}", json={"status": "published"},
                     headers=owner_write_headers(owner)).status_code == 200
    view = owner.get(f"/api/admin/events/{event_id}/recording").json()
    view["_session_id"] = session_id
    view["_resource_id"] = resource_id
    return view


def recording_view(client: TestClient, event_id: str) -> dict:
    response = client.get(f"/api/public/events/{event_id}/recording")
    assert response.status_code == 200, response.text
    return response.json()["recording"]


PURCHASE_FORM_KEYS = iter(range(1000))


def purchase_form(owner: TestClient, recording_id: str, *, price: int, methods=("card_transfer",), card=CARD,
                  publish: bool = True, **overrides) -> str:
    """Phase 9.1: the purchase entry of a product is a builder form (purpose=recording_access).

    The builder owns price, methods and card destination; the product never stores them twice.
    """
    settings = {"enabledPaymentMethods": list(methods)}
    if price > 0:
        settings["fin"] = [{"l": "دسترسی به نسخهٔ ضبط‌شده", "p": price, "off": 0, "req": True, "d": ""}]
    if "card_transfer" in methods:
        settings["receiptReviewRequired"] = True
        settings["paymentCard"] = dict(card)
        settings["paymentInstructions"] = "مبلغ را واریز کنید و رسید را در همین صفحه بارگذاری کنید."
    settings.update(overrides.pop("settings", {}))
    payload = {
        "name": "خرید نسخهٔ ضبط‌شده", "model": "registration", "need": "reg", "purpose": "recording_access",
        "recording_id": recording_id, "settings": settings,
        "fields": [{"id": "full-name", "t": "fullname", "l": "نام کامل", "required": True}],
    }
    payload.update(overrides)
    created = owner.post("/api/forms", json=payload,
                         headers={**owner_write_headers(owner), "Idempotency-Key": f"purchase-form-key-{next(PURCHASE_FORM_KEYS):04d}"})
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    assert created.json()["purpose"] == "recording_access" and created.json()["recording_id"] == recording_id
    if publish:
        published = owner.post(f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=owner_write_headers(owner))
        assert published.status_code == 200, published.text
    return form_id


ORIGIN = {"Origin": "http://testserver"}


def submit_purchase(client: TestClient, form_id: str, *, name: str = "خریدار آزمایشی", paid: bool = True):
    body: dict = {"answers": {"full-name": name}}
    if paid:
        body["payment"] = {"method": "card_transfer", "selection": {"items": [0], "coupon_code": ""}}
    assert client.get(f"/api/public/forms/{form_id}/draft").status_code == 200
    return client.post(f"/api/public/forms/{form_id}/responses", json=body, headers=ORIGIN)


def upload_purchase_receipt(client: TestClient, form_id: str, *, content: bytes = PNG, name: str = "receipt.png",
                            content_type: str = "image/png", note: str = ""):
    headers = {**ORIGIN, "Content-Type": content_type, "X-File-Name": quote(name)}
    if note:
        headers["X-Receipt-Note"] = quote(note, safe="")
    return client.post(f"/api/public/forms/{form_id}/receipt", content=content, headers=headers)


def inbox_decide(staff: TestClient, task_id: str, decision: str, reason: str, headers: dict[str, str]):
    item = next((row for row in staff.get("/api/admin/inbox").json()["items"] if row["id"] == task_id), None)
    version = item["version"] if item else 1  # already-decided tasks leave the pending inbox → stale version
    return staff.post(f"/api/admin/inbox/{task_id}/decision",
                      json={"decision": decision, "reason": reason, "expected_version": version}, headers=headers)


def notifications(engine, account_id: str) -> list[UserNotificationRecord]:
    with Session(engine) as db:
        return list(db.scalars(select(UserNotificationRecord).where(UserNotificationRecord.account_id == account_id)))


# ── card transfer: full purchase path, access, refund, sales states ──



def test_card_transfer_purchase_is_reviewed_server_side_and_access_is_decided_per_download():
    """Phase 9.1: the purchase form of the builder is the only sales entry; the product carries no
    second price/card; receipts are reviewed in the shared inbox; access is decided per download."""
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_id, version = held_event(owner, 0)
            other_event, version = held_event(owner, version, t="کارگاه دیگر")
            base = f"/api/admin/events/{event_id}/recording"

            # No product yet; the panel learns the event is held and what the limits are.
            empty = owner.get(base)
            assert empty.status_code == 200 and empty.json()["recording"] is None
            assert empty.json()["event_held"] is True and empty.json()["limits"]["streaming"] == "none"
            assert "video/mp4" in empty.json()["limits"]["content_types"]

            # Validation: unknown field, bad card, bad price.
            assert put_recording(owner, event_id, title="x", buyers=12).status_code == 422
            bad_card = put_recording(owner, event_id, title="نسخهٔ ضبط‌شده", payment_card={"number": "1234"})
            assert bad_card.status_code == 422 and bad_card.json()["detail"]["code"] == "invalid_payment_card"
            assert put_recording(owner, event_id, title="نسخهٔ ضبط‌شده", price=-5).status_code == 422

            # Publishing is blocked until the product is really complete — and, for a paid product, until a
            # purchase form exists in the builder (the legacy product card alone is not a payment method).
            created = put_recording(owner, event_id, title="نسخهٔ ضبط‌شدهٔ کارگاه", price=1_500_000)
            assert created.status_code == 200 and created.json()["status"] == "draft"
            assert set(created.json()["publish_blockers"]) == {"no_published_session", "no_live_resource", "purchase_form_required"}
            assert created.json()["commerce"]["source"] == "product" and created.json()["commerce"]["form_id"] is None
            assert set_status(owner, event_id, "published").status_code == 409  # draft → published is not a transition
            ready = set_status(owner, event_id, "ready")
            assert ready.status_code == 200 and ready.json()["status"] == "ready"
            blocked = set_status(owner, event_id, "published")
            assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "publish_blocked"
            assert "purchase_form_required" in blocked.json()["detail"]["blockers"]

            # A session file may only hang off a session of this event's own product.
            foreign = owner.post(f"/api/admin/events/{other_event}/resources",
                                 json={"title": "فایل بیگانه", "access": "purchased", "session_id": "00000000-0000-0000-0000-000000000000"},
                                 headers=owner_write_headers(owner))
            assert foreign.status_code == 404

            product = build_sellable_product(owner, event_id)
            session_id, resource_id = product["_session_id"], product["_resource_id"]
            recording_id = product["recording"]["id"]
            assert product["recording"]["publish_blockers"] == ["purchase_form_required"]
            # Session with files cannot be deleted silently.
            blocked_delete = owner.delete(f"{base}/sessions/{session_id}", headers=owner_write_headers(owner))
            assert blocked_delete.status_code == 409 and blocked_delete.json()["detail"]["code"] == "session_has_resources"

            # Purchase form: ids are validated server-side (unknown product, foreign event, registration-only keys).
            missing = owner.post("/api/forms", json={
                "name": "فرم خرید", "model": "registration", "need": "reg", "purpose": "recording_access",
                "recording_id": "00000000-0000-0000-0000-000000000000", "settings": {}, "fields": [{"id": "full-name", "t": "fullname", "l": "نام کامل", "required": True}]},
                headers={**owner_write_headers(owner), "Idempotency-Key": "purchase-form-missing-0001"})
            assert missing.status_code == 422 and missing.json()["detail"]["code"] == "recording_not_found"
            mismatch = owner.post("/api/forms", json={
                "name": "فرم خرید", "model": "registration", "need": "reg", "purpose": "recording_access",
                "recording_id": recording_id, "ev": other_event, "settings": {}, "fields": [{"id": "full-name", "t": "fullname", "l": "نام کامل", "required": True}]},
                headers={**owner_write_headers(owner), "Idempotency-Key": "purchase-form-mismatch-001"})
            assert mismatch.status_code == 422 and mismatch.json()["detail"]["code"] == "purchase_form_event_mismatch"
            with_tickets = owner.post("/api/forms", json={
                "name": "فرم خرید", "model": "registration", "need": "reg", "purpose": "recording_access",
                "recording_id": recording_id, "settings": {"guestsOn": True}, "fields": [{"id": "full-name", "t": "fullname", "l": "نام کامل", "required": True}]},
                headers={**owner_write_headers(owner), "Idempotency-Key": "purchase-form-guests-0001"})
            assert with_tickets.status_code == 422
            # A draft purchase form is not enough: the product still cannot be published.
            draft_form = purchase_form(owner, recording_id, price=1_500_000, publish=False)
            assert owner.get(base).json()["recording"]["publish_blockers"] == ["purchase_form_not_published"]
            assert owner.get(f"/api/forms/{draft_form}").json()["ev"] == event_id  # event fixed by the product
            assert owner.post(f"/api/forms/{draft_form}/publish", json={"expected_version": 1}, headers=owner_write_headers(owner)).status_code == 200
            admin_view = owner.get(base).json()["recording"]
            assert admin_view["publish_blockers"] == [] and admin_view["commerce"] == {
                "source": "form", "price": 1_500_000, "currency": "IRR", "free": False, "methods": ["card_transfer"],
                "form_id": draft_form, "form_status": "published", "form_title": "خرید نسخهٔ ضبط‌شده", "valid": True, "on_sale": True}
            form_id = draft_form
            # One published purchase form per product.
            second_form = purchase_form(owner, recording_id, price=1_000, publish=False)
            dup = owner.post(f"/api/forms/{second_form}/publish", json={"expected_version": 1}, headers=owner_write_headers(owner))
            assert dup.status_code == 409 and dup.json()["detail"]["code"] == "purchase_form_already_published"
            # Price / card now live in the form: the product refuses a second copy.
            locked = put_recording(owner, event_id, price=1_200_000)
            assert locked.status_code == 409 and locked.json()["detail"]["code"] == "commercial_settings_in_form"
            assert locked.json()["detail"]["form_id"] == form_id and "price" in locked.json()["detail"]["fields"]
            assert put_recording(owner, event_id, summary="خلاصهٔ تازه").status_code == 200  # non-commercial edits still fine

            # Still not public while 'ready'.
            guest = TestClient(app)
            assert guest.get(f"/api/public/events/{event_id}/recording").status_code == 404
            assert "recording" not in public_event(guest, event_id)
            assert guest.get("/api/public/recordings").json()["total"] == 0

            published = set_status(owner, event_id, "published")
            assert published.status_code == 200 and published.json()["status"] == "published"
            assert published.json()["published_at"]

            # Shelf + snapshot: honest numbers only (one session, 55 minutes), card never public, price from the form.
            shelf = guest.get("/api/public/recordings").json()
            assert shelf["total"] == 1 and shelf["items"][0]["event"]["id"] == event_id
            assert shelf["items"][0]["session_count"] == 1 and shelf["items"][0]["total_minutes"] == 55
            assert shelf["items"][0]["price"] == 1_500_000 and shelf["items"][0]["purchase_form_id"] == form_id
            assert "payment_card" not in shelf["items"][0] and "buyers" not in shelf["items"][0]
            snapshot_event = public_event(guest, event_id)
            assert snapshot_event["recording"]["sellable"] is True and snapshot_event["recording"]["price"] == 1_500_000
            assert snapshot_event["registration"]["state"] == "ended"

            # Guest: CTA = login, download denied with 401, the purchase form refuses anonymous buyers.
            view = recording_view(guest, event_id)
            assert view["viewer"]["cta"]["kind"] == "login" and view["viewer"]["access"]["state"] == "none"
            assert view["purchase"] == {"form_id": form_id, "source": "form", "methods": ["card_transfer"], "on_sale": True}
            assert "payment_card" not in view and view["sessions"][0]["resources"][0]["allowed"] is False
            assert view["sessions"][0]["resources"][0]["reason"] == "login_required"
            download = f"/api/public/events/{event_id}/resources/{resource_id}/download"
            assert guest.get(download).status_code == 401
            assert all(row["id"] != resource_id for row in interaction(guest, event_id)["resources"])
            public_form = guest.get(f"/api/public/forms/{form_id}")
            assert public_form.status_code == 200 and public_form.json()["purpose"] == "recording_access"
            assert public_form.json()["purchase"]["signed_in"] is False and public_form.json()["purchase"]["price"] == 1_500_000
            assert public_form.json()["purchase"]["recording_id"] == recording_id and public_form.json()["purchase"]["access_state"] == "none"
            # The HTML entry (form.html) bootstraps the same purchase header — the UI reads price/state from it.
            page = guest.get(f"/form.html?fid={form_id}&kind=reg")
            assert page.status_code == 200 and '"purpose": "recording_access"' in page.text.replace('":"', '": "')
            assert "\"signed_in\": false" in page.text.replace('":', '": ') and "\"event_id\": \"" + event_id in page.text.replace('":', '": ')
            assert 'id="nora-public-error-data">null<' in page.text
            # The event deadline is long gone, yet the purchase form stays open: it is not a registration form.
            anonymous = submit_purchase(guest, form_id)
            assert anonymous.status_code == 401 and anonymous.json()["detail"]["code"] == "account_required"

            # Member without access: CTA = buy via the form, direct URL → 403 + audit; retired account routes answer 410.
            member = TestClient(app)
            member_id = bale_login(member, 94001)
            view = recording_view(member, event_id)
            assert view["viewer"]["cta"] == {"kind": "buy", "reason": "purchase_required", "methods": ["card_transfer"], "form_id": form_id}
            denied = member.get(download)
            assert denied.status_code == 403 and denied.json()["detail"]["reason"] == "purchase_required"
            assert "recording.download.denied" in audit_actions(engine)
            paid = member.post(f"/api/account/recordings/{recording_id}/claim", headers=account_write_headers(member))
            assert paid.status_code == 409 and paid.json()["detail"]["code"] == "recording_not_free"
            retired = member.post(f"/api/account/recordings/{recording_id}/orders", json={"method": "card_transfer"},
                                  headers=account_write_headers(member))
            assert retired.status_code == 410 and retired.json()["detail"] == {"code": "use_purchase_form", "form_id": form_id}

            # Card purchase through the form: amount from the builder, ledger row mirrors the form payment.
            assert member.get(f"/api/public/forms/{form_id}/draft").status_code == 200
            no_payment = member.post(f"/api/public/forms/{form_id}/responses", json={"answers": {"full-name": "خریدار"}}, headers=ORIGIN)
            assert no_payment.status_code == 422 and no_payment.json()["detail"]["code"] == "payment_method_required"
            bought = submit_purchase(member, form_id, name="خریدار اول")
            assert bought.status_code == 200, bought.text
            assert bought.json()["purpose"] == "recording_access" and bought.json()["payment_status"] == "awaiting_receipt"
            assert bought.json()["purchase"] == {"recording_id": recording_id, "event_id": event_id, "title": "نسخهٔ ضبط‌شدهٔ کارگاه", "access_state": "none"}
            assert bought.json()["ticket_type"] in (None, "")
            mine = member.get("/api/account/recording-orders").json()
            assert mine["total"] == 1 and mine["items"][0]["status"] == "awaiting_receipt" and mine["items"][0]["amount"] == 1_500_000
            order_id = mine["items"][0]["id"]
            with Session(engine) as db:
                ledger = db.get(RecordingOrderRecord, order_id)
                assert ledger.form_response_id and ledger.form_payment_id and ledger.idempotency_key == "form-purchase:" + ledger.form_response_id
                # The purchase is not a registration: the response never qualifies for a ticket / check-in.
                purchase_response = db.get(FormResponseRecord, ledger.form_response_id)
                assert purchase_response.form_snapshot["purpose"] == "recording_access"
                assert backend_app._form_ticket_eligible(purchase_response) is False
                assert purchase_response.ticket_serial is None and purchase_response.ticket_checked_in_at is None
            assert recording_view(member, event_id)["viewer"]["cta"]["kind"] == "order_open"
            assert interaction(member, event_id)["viewer"]["participation"]["registered"] is False
            assert member.get(download).status_code == 403
            # Receipt rules: executables/HTML refused, image accepted → inbox task; still no access.
            assert upload_purchase_receipt(member, form_id, content=b"MZ\x90\x00", content_type="application/octet-stream").status_code == 415
            assert upload_purchase_receipt(member, form_id, content=b"<html>", name="a.html", content_type="text/html").status_code == 415
            assert member.put(f"/api/account/recording-orders/{order_id}/receipt", content=PNG,
                              headers={**account_write_headers(member), "X-File-Name": "a.png"}).status_code == 410
            ok = upload_purchase_receipt(member, form_id, note="واریز شد")
            assert ok.status_code == 200 and ok.json()["uploaded"] is True and ok.json()["review_task_id"]
            task_id = ok.json()["review_task_id"]
            assert member.get(download).status_code == 403  # a receipt alone never opens the content
            assert member.get("/api/account/recordings").json()["items"] == []
            mine = member.get("/api/account/recording-orders").json()
            assert mine["total"] == 1 and mine["items"][0]["status"] == "receipt_submitted" and mine["items"][0]["title"]
            assert mine["items"][0]["purchase_form_id"] == form_id and "card" not in mine["items"][0]  # account page continues in the form
            assert member.get(f"/api/account/recording-orders/{order_id}").json()["purchase_form_id"] == form_id

            # Another account never sees this order (404, not 403); cancelling a form-backed order is refused.
            stranger = TestClient(app)
            bale_login(stranger, 94002)
            assert stranger.get(f"/api/account/recording-orders/{order_id}").status_code == 404
            cancel = member.post(f"/api/account/recording-orders/{order_id}/cancel", headers=account_write_headers(member))
            assert cancel.status_code == 409 and cancel.json()["detail"]["code"] == "order_follows_form_payment"

            # Manager (receipt_approve) reviews in the shared inbox: the legacy order decision points there.
            manager_id = bale_login(TestClient(app), 94003)
            manager = TestClient(app)
            assign_manager(manager, manager_id)  # separate client: ends logged in as the manager (owner stays owner)
            queue = manager.get("/api/admin/recording-orders?status=review")
            assert queue.status_code == 200 and queue.json()["total"] == 1
            row = queue.json()["items"][0]
            assert row["id"] == order_id and row["event_title"]
            assert manager.get(f"/api/admin/recording-orders?q={quote('نسخهٔ ضبط')}").json()["total"] == 1
            assert manager.get(f"/api/admin/recording-orders?event_id={other_event}").json()["total"] == 0
            redirected = manager.post(f"/api/admin/recording-orders/{order_id}/decision",
                                      json={"decision": "approve", "reason": "رسید درست است"}, headers=account_write_headers(manager))
            assert redirected.status_code == 409 and redirected.json()["detail"] == {"code": "decide_in_inbox", "task_id": task_id}
            inbox_item = next(item for item in manager.get("/api/admin/inbox").json()["items"] if item["id"] == task_id)
            assert inbox_item["payload"]["purchase_source"] == "recording_access" and inbox_item["payload"]["recording_id"] == recording_id
            assert inbox_item["payload"]["note"] == "واریز شد" and inbox_item["kind"] == "receipt_review"
            approved = inbox_decide(manager, task_id, "approved", "رسید با مبلغ تطبیق داده شد", account_write_headers(manager))
            assert approved.status_code == 200, approved.text
            repeat = inbox_decide(manager, task_id, "approved", "دوباره", account_write_headers(manager))
            assert repeat.status_code == 409
            ledger_view = manager.get(f"/api/admin/recording-orders/{order_id}").json()
            assert ledger_view["status"] == "paid_manual" and ledger_view["decision_reason"] == "رسید با مبلغ تطبیق داده شد"
            assert ledger_view["access"]["state"] == "active"

            # Buyer: CTA switches to viewing, bytes flow inline with Range support, library + notification exist.
            view = recording_view(member, event_id)
            assert view["viewer"]["cta"]["kind"] == "view" and view["viewer"]["access"] == {
                "state": "active", "allowed": True, "reason": "purchased", "source": "purchase", "expires_at": ""}
            served = member.get(download)
            assert served.status_code == 200 and served.content == MP4 and served.headers["x-nora-resource-access"] == "purchased"
            assert served.headers["content-disposition"].startswith("inline;") and served.headers["accept-ranges"] == "bytes"
            partial = member.get(download, headers={"Range": "bytes=4-7"})
            assert partial.status_code == 206 and partial.content == b"ftyp" and partial.headers["content-range"] == f"bytes 4-7/{len(MP4)}"
            assert member.get(download, headers={"Range": f"bytes={len(MP4) + 5}-"}).status_code == 416
            library = member.get("/api/account/recordings").json()["items"]
            assert len(library) == 1 and library[0]["access"]["state"] == "active" and library[0]["progress"] is None
            queued = notifications(engine, member_id)
            assert [item.kind for item in queued] == ["recording_access"] and queued[0].delivery_status == "pending"
            # Buyer may review (badge = buyer); attendance and registration still false: purchase ≠ registration ≠ attendance.
            page = interaction(member, event_id)
            assert page["viewer"]["participation"]["attended"] is False and page["viewer"]["participation"]["registered"] is False
            assert page["viewer"]["buyer"] is True and page["reviews"]["eligible"] is True and page["reviews"]["badge"] == "buyer"
            # A second purchase of an active right is refused by the form itself.
            twice = submit_purchase(member, form_id)
            assert twice.status_code == 409 and twice.json()["detail"]["code"] == "access_already_active"

            # Refund: finance only (manager 403), reference required, access revoked consistently.
            refund_url = f"/api/admin/recording-orders/{order_id}/refund"
            assert manager.post(refund_url, json={"reference": "ref-1", "reason": "x"}, headers=account_write_headers(manager)).status_code == 403
            assert owner.post(refund_url, json={"reason": "انصراف خریدار"}, headers=owner_write_headers(owner)).status_code == 422
            refunded = owner.post(refund_url, json={"reference": "TRX-REF-2026-01", "reason": "انصراف خریدار"}, headers=owner_write_headers(owner))
            assert refunded.status_code == 200 and refunded.json()["status"] == "refunded" and refunded.json()["access"]["state"] == "revoked"
            denied = member.get(download)
            assert denied.status_code == 403 and denied.json()["detail"]["reason"] == "access_revoked"
            assert member.get("/api/account/recordings").json()["items"][0]["access"]["state"] == "revoked"
            assert recording_view(member, event_id)["viewer"]["cta"]["kind"] == "buy"
            assert owner.post(refund_url, json={"reference": "again", "reason": "دوباره"}, headers=owner_write_headers(owner)).status_code == 409
            after_refund = notifications(engine, member_id)
            assert [item.kind for item in after_refund] == ["recording_access", "recording_order"]
            assert "TRX-REF-2026-01" in after_refund[1].body and "انصراف خریدار" in after_refund[1].body and after_refund[1].delivery_status == "pending"
            assert manager.get("/api/admin/recording-orders?format=csv").status_code == 403
            export = owner.get("/api/admin/recording-orders?format=csv")
            assert export.status_code == 200 and "order_id" in export.text and order_id in export.text

            # Sales states: pausing needs a reason; paused = off_sale CTA and the form refuses; archived = gone from public.
            assert set_status(owner, event_id, "sales_paused").status_code == 422
            paused = set_status(owner, event_id, "sales_paused", "به‌روزرسانی ویدیوها")
            assert paused.status_code == 200 and paused.json()["status_reason"] == "به‌روزرسانی ویدیوها"
            assert recording_view(member, event_id)["viewer"]["cta"]["kind"] == "off_sale"
            off_sale = submit_purchase(member, form_id)
            assert off_sale.status_code == 409 and off_sale.json()["detail"]["code"] == "recording_not_on_sale"
            assert public_event(guest, event_id)["recording"]["sellable"] is False
            paused_page = member.get(f"/form.html?fid={form_id}&kind=reg")
            assert paused_page.status_code == 200 and f"recording-not-on-sale:{recording_id}" in paused_page.text
            assert 'id="nora-public-form-data">null<' in paused_page.text  # no price/card bootstrap while off sale
            assert set_status(owner, event_id, "archived", "پایان فروش").status_code == 200
            assert guest.get(f"/api/public/events/{event_id}/recording").status_code == 404
            assert "recording" not in public_event(guest, event_id)
            assert owner.get(base).json()["recording"]["status"] == "archived"  # staff still see it

            summary = owner.get("/api/admin/recordings/summary").json()
            assert summary["recordings"] == {"archived": 1} and summary["orders_refunded"] == 1 and summary["active_access"] == 0
            actions = audit_actions(engine)
            for action in ("recording.create", "recording.update", "recording.status", "recording.session.create",
                           "recording.order.approve", "workflow.decide", "recording.order.refund", "recording.orders.export"):
                assert action in actions, action
    finally:
        engine.dispose()


# ── free product, attendee courtesy, manual grant/revoke, drafts, not-held blocker ──


def test_free_claim_manual_grant_and_draft_visibility_follow_server_rules():
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            upcoming, version = create_published_event(owner, 0, t="کارگاه آینده", startsAt=iso(timedelta(days=5)))
            held, version = held_event(owner, version)

            # A product of an event that has not been held can never go on sale.
            put_recording(owner, upcoming, title="ضبط آینده", price=0)
            build = build_sellable_product(owner, upcoming, price=0)
            assert "event_not_held" in build["recording"]["publish_blockers"]
            assert set_status(owner, upcoming, "ready").status_code == 200
            blocked = set_status(owner, upcoming, "published")
            assert blocked.status_code == 409 and blocked.json()["detail"]["blockers"] == ["event_not_held"]
            guest = TestClient(app)
            assert public_event(guest, upcoming)["registration"]["state"] in {"open", "none"}
            assert "recording" not in public_event(guest, upcoming)

            # Free product of a held event: claim creates the access row, no order, idempotent.
            product = build_sellable_product(owner, held, price=0, payment_card=None, attendee_access=True)
            assert product["recording"]["publish_blockers"] == []  # free: no payment method needed
            assert set_status(owner, held, "ready").status_code == 200
            assert set_status(owner, held, "published").status_code == 200
            recording_id = product["recording"]["id"]
            resource_id = product["_resource_id"]
            download = f"/api/public/events/{held}/resources/{resource_id}/download"

            member = TestClient(app)
            member_id = bale_login(member, 95001)
            view = recording_view(member, held)
            assert view["free"] is True and view["viewer"]["cta"] == {"kind": "free", "reason": "free", "methods": [], "form_id": None}
            assert member.get(download).status_code == 403
            retired = member.post(f"/api/account/recordings/{recording_id}/orders", json={"method": "card_transfer"},
                                  headers=account_write_headers(member))
            assert retired.status_code == 410 and retired.json()["detail"] == {"code": "use_purchase_form", "form_id": None}
            claimed = member.post(f"/api/account/recordings/{recording_id}/claim", headers=account_write_headers(member))
            assert claimed.status_code == 201 and claimed.json()["created"] is True and claimed.json()["access"]["source"] == "free"
            again = member.post(f"/api/account/recordings/{recording_id}/claim", headers=account_write_headers(member))
            assert again.status_code == 201 and again.json()["created"] is False
            with Session(engine) as db:
                assert db.scalar(select(RecordingOrderRecord.id)) is None  # no fake transaction
                assert len(db.scalars(select(RecordingAccessRecord)).all()) == 1
            assert member.get(download).status_code == 200
            assert recording_view(member, held)["viewer"]["cta"]["kind"] == "view"
            assert member.get("/api/account/recording-orders").json()["total"] == 0

            # Manual grant (ev_publish): account must exist, reason required, scope in days, audited; revoke keeps the row.
            other = TestClient(app)
            other_id = bale_login(other, 95002)
            grant_url = f"/api/admin/events/{held}/recording/access"
            assert owner.post(grant_url, json={"account_id": "00000000-0000-0000-0000-000000000000", "reason": "x"},
                              headers=owner_write_headers(owner)).status_code == 404
            assert owner.post(grant_url, json={"account_id": other_id}, headers=owner_write_headers(owner)).status_code == 422
            granted = owner.post(grant_url, json={"account_id": other_id, "reason": "مهمان مدرس", "access_days": 30},
                                 headers=owner_write_headers(owner))
            assert granted.status_code == 201, granted.text
            access_id = granted.json()["access"]["id"]
            assert granted.json()["access"]["source"] == "granted" and granted.json()["access"]["expires_at"]
            listed = owner.get(grant_url).json()
            assert listed["total"] == 2 and {row["source"] for row in listed["items"]} == {"free", "granted"}
            assert other.get(download).status_code == 200
            other_view = recording_view(other, held)
            assert other_view["viewer"]["access"]["state"] == "active" and other_view["viewer"]["access"]["expires_at"]
            assert other.get("/api/account/recordings").json()["items"][0]["access"]["source"] == "granted"
            revoked = owner.post(f"{grant_url}/{access_id}/revoke", json={"reason": "اشتباه در اعطا"}, headers=owner_write_headers(owner))
            assert revoked.status_code == 200 and revoked.json()["state"] == "revoked"
            assert other.get(download).status_code == 403
            assert other.get("/api/account/recordings").json()["items"][0]["access"]["state"] == "revoked"
            regrant = owner.post(grant_url, json={"account_id": other_id, "reason": "تأیید مجدد"}, headers=owner_write_headers(owner))
            assert regrant.status_code == 201 and regrant.json()["created"] is False and regrant.json()["access"]["state"] == "active"
            assert len(notifications(engine, other_id)) == 2  # one per grant, delivery honest (pending → bot)
            actions = audit_actions(engine)
            assert "recording.access.grant" in actions and "recording.access.revoke" in actions
            with Session(engine) as db:
                grant_rows = db.scalars(select(AdminAuditEventRecord).where(AdminAuditEventRecord.action == "recording.access.grant")).all()
                assert all(row.details.get("reason") for row in grant_rows)

            # Free product sold through a *free purchase form* (price 0 in the builder): the accepted response is the
            # purchase — access ``source='free'``, no ledger row, no fake transaction, idempotent re-submit.
            free_event, version = held_event(owner, version, t="کارگاه رایگان با فرم")
            free_product = build_sellable_product(owner, free_event, price=0, payment_card=None)
            free_form = purchase_form(owner, free_product["recording"]["id"], price=0, methods=())
            assert owner.get(f"/api/admin/events/{free_event}/recording").json()["recording"]["commerce"]["free"] is True
            assert set_status(owner, free_event, "ready").status_code == 200
            assert set_status(owner, free_event, "published").status_code == 200
            free_download = f"/api/public/events/{free_event}/resources/{free_product['_resource_id']}/download"
            assert recording_view(member, free_event)["viewer"]["cta"] == {"kind": "free", "reason": "free", "methods": [], "form_id": free_form}
            taken = submit_purchase(member, free_form, paid=False)
            assert taken.status_code == 200, taken.text
            assert taken.json()["payment_status"] is None and taken.json()["purchase"]["access_state"] == "active"
            with Session(engine) as db:
                assert db.scalar(select(RecordingOrderRecord.id)) is None  # still no fake transaction anywhere
                free_rows = db.scalars(select(RecordingAccessRecord).where(RecordingAccessRecord.recording_id == free_product["recording"]["id"])).all()
                assert len(free_rows) == 1 and free_rows[0].source == "free" and free_rows[0].order_id is None
            assert member.get(free_download).status_code == 200
            again_free = submit_purchase(member, free_form, paid=False)
            assert again_free.status_code == 409 and again_free.json()["detail"]["code"] == "access_already_active"
            # The same product also accepts the one-click claim; both paths converge on the same single access row.
            assert member.post(f"/api/account/recordings/{free_product['recording']['id']}/claim", headers=account_write_headers(member)).json()["created"] is False

            # Draft product stays invisible to the public but is previewable by staff.
            draft_event, version = held_event(owner, version, t="کارگاه پیش‌نویس")
            draft = build_sellable_product(owner, draft_event, price=0, payment_card=None)
            assert draft["recording"]["status"] == "draft"
            assert guest.get(f"/api/public/events/{draft_event}/recording").status_code == 404
            assert "recording" not in public_event(guest, draft_event)
            draft_resource = f"/api/public/events/{draft_event}/resources/{draft['_resource_id']}/download"
            assert guest.get(draft_resource).status_code == 401
            assert member.get(draft_resource).status_code == 403
            staff_view = owner.get(f"/api/public/events/{draft_event}/recording")
            assert staff_view.status_code == 200 and staff_view.json()["recording"]["viewer"]["cta"]["kind"] == "staff_preview"
            assert owner.get(draft_resource).status_code == 200

            # Sessions marked as preview open their files to everyone; others stay locked.
            preview_session = owner.put(f"/api/admin/events/{draft_event}/recording/sessions/{draft['_session_id']}",
                                        json={"preview": True}, headers=owner_write_headers(owner))
            assert preview_session.status_code == 200
            assert set_status(owner, draft_event, "ready").status_code == 200
            assert set_status(owner, draft_event, "published").status_code == 200
            preview_view = recording_view(guest, draft_event)
            assert preview_view["sessions"][0]["resources"][0]["preview"] is True
            assert preview_view["sessions"][0]["resources"][0]["allowed"] is True
            assert guest.get(draft_resource).status_code == 200
            assert guest.get(draft_resource).headers["x-nora-resource-access"] == "preview"
    finally:
        engine.dispose()


# ── Bale wallet: invoice, pre-checkout, verified settlement, duplicates, tampering ──


@pytest.fixture
def wallet_app(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None, owner_id="owner-01", owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"), cookie_secure=False,
        bale_bot_token=BOT_TOKEN, bot_service_token=SERVICE_TOKEN, owner_bale_user_id="70001",
        form_payment_bot_token=PAYMENT_BOT_TOKEN, form_payment_provider_token=PAYMENT_PROVIDER_TOKEN,
        form_payment_webhook_secret=PAYMENT_WEBHOOK_SECRET, form_payment_webhook_url=PAYMENT_WEBHOOK_BASE,
        form_payment_timeout_seconds=8,
    )
    state: dict = {"webhook_url": "", "transaction": None, "calls": [], "pre_checkout": [], "payloads": []}

    def fake_bale_api(config, method, payload):
        assert config.form_payment_bot_token == PAYMENT_BOT_TOKEN
        state["calls"].append((method, dict(payload)))
        if method == "getWebhookInfo":
            return {"ok": True, "result": {"url": state["webhook_url"]}}
        if method == "setWebhook":
            state["webhook_url"] = payload["url"]
            return {"ok": True, "result": True}
        if method == "createInvoiceLink":
            state["payloads"].append(payload["payload"])
            return {"ok": True, "result": "https://ble.ir/invoice/test-recording"}
        if method == "answerPreCheckoutQuery":
            state["pre_checkout"].append(dict(payload))
            return {"ok": True, "result": True}
        if method == "inquireTransaction":
            assert state["transaction"] is not None
            return {"ok": True, "result": dict(state["transaction"])}
        raise AssertionError(f"unexpected Bale method: {method}")

    monkeypatch.setattr(backend_app, "call_bale_payment_api", fake_bale_api)
    app = create_app(settings, engine=engine)
    try:
        yield app, engine, settings, state
    finally:
        engine.dispose()


def settlement(invoice_payload: str, *, payer: int, amount: int, transaction_id: str, charge_id: str | None = None) -> dict:
    return {
        "update_id": 7,
        "message": {
            "from": {"id": payer},
            "successful_payment": {
                "invoice_payload": invoice_payload, "telegram_payment_charge_id": transaction_id,
                "provider_payment_charge_id": charge_id or f"charge-{transaction_id}", "currency": "IRR", "total_amount": amount,
            },
        },
    }



def test_wallet_orders_grant_access_only_from_the_verified_webhook_and_stay_idempotent(wallet_app):
    """Phase 9.1: the Bale wallet runs through the builder's payment-intent path; access is granted only inside
    the verified webhook (inquiry match), duplicate deliveries / second charges never double-grant, and a
    tampered settlement leaves the payment flagged without a response, a ledger row or an access right."""
    app, engine, settings, state = wallet_app
    hook = "/api/payments/bale/webhook/" + _form_payment_webhook_token(settings)
    secret = {"X-Telegram-Bot-Api-Secret-Token": PAYMENT_WEBHOOK_SECRET}
    with TestClient(app) as owner:
        owner_login(owner)
        event_id, _version = held_event(owner, 0)
        product = build_sellable_product(owner, event_id, price=900_000, payment_card=None, bale_enabled=True)
        recording_id, resource_id = product["recording"]["id"], product["_resource_id"]
        assert product["recording"]["publish_blockers"] == ["purchase_form_required"]  # the product flag alone sells nothing
        form_id = purchase_form(owner, recording_id, price=900_000, methods=("bale_wallet",))
        assert owner.get(f"/api/admin/events/{event_id}/recording").json()["recording"]["publish_blockers"] == []
        assert set_status(owner, event_id, "ready").status_code == 200
        assert set_status(owner, event_id, "published").status_code == 200
        download = f"/api/public/events/{event_id}/resources/{resource_id}/download"

        def intent(client: TestClient):
            return client.post(f"/api/public/forms/{form_id}/payment-intents",
                               json={"method": "bale_wallet", "selection": {"items": [0], "coupon_code": ""}}, headers=ORIGIN)

        # Anonymous visitors may read the form but cannot open a purchase intent.
        visitor = TestClient(app)
        assert visitor.get(f"/api/public/forms/{form_id}/draft").status_code == 200
        assert visitor.patch(f"/api/public/forms/{form_id}/draft", json={"answers": {"full-name": "مهمان"}}, headers=ORIGIN).status_code == 200
        anonymous = intent(visitor)
        assert anonymous.status_code == 401 and anonymous.json()["detail"]["code"] == "account_required"

        buyer = TestClient(app)
        buyer_id = bale_login(buyer, 96001)
        assert recording_view(buyer, event_id)["viewer"]["cta"] == {"kind": "buy", "reason": "purchase_required", "methods": ["bale_wallet"], "form_id": form_id}
        assert buyer.get(f"/api/public/forms/{form_id}/draft").status_code == 200
        assert buyer.patch(f"/api/public/forms/{form_id}/draft", json={"answers": {"full-name": "خریدار کیف پول"}}, headers=ORIGIN).status_code == 200
        opened = intent(buyer)
        assert opened.status_code == 201, opened.text
        payment_id = opened.json()["payment_id"]
        assert opened.json()["status"] == "pending" and opened.json()["invoice_url"] == "https://ble.ir/invoice/test-recording"
        payload = state["payloads"][-1]
        assert payload.startswith("nora_") and state["webhook_url"].endswith(_form_payment_webhook_token(settings))
        invoice_call = next(call for call in state["calls"] if call[0] == "createInvoiceLink")[1]
        assert invoice_call["prices"][0]["amount"] == 900_000 and invoice_call["currency"] == "IRR"
        # Coming back from the invoice page changes nothing: no response, no ledger, no access until the webhook verifies.
        assert buyer.get(f"/api/public/forms/{form_id}/payment-intents/{payment_id}").json()["status"] == "pending"
        assert buyer.get(download).status_code == 403 and buyer.get("/api/account/recording-orders").json()["total"] == 0

        # Pre-checkout: wrong amount refused, exact match accepted.
        def precheckout(amount: int, payer: int, query_id: str) -> None:
            response = buyer.post(hook, json={"update_id": 1, "pre_checkout_query": {
                "id": query_id, "from": {"id": payer}, "currency": "IRR", "total_amount": amount, "invoice_payload": payload}}, headers=secret)
            assert response.status_code == 200
        precheckout(1, 96001, "pcq-amount")
        precheckout(900_000, 96001, "pcq-ok")
        assert [item["ok"] for item in state["pre_checkout"]] == [False, True]

        # Settlement with a provider that still says pending → 503 (Bale retries), nothing granted.
        state["transaction"] = {"id": "tx-1", "status": "pending", "amount": 900_000, "userID": 96001}
        assert buyer.post(hook, json=settlement(payload, payer=96001, amount=900_000, transaction_id="tx-1"), headers=secret).status_code == 503
        assert buyer.get(download).status_code == 403
        # Tampered callback: amount mismatch between provider inquiry and the payment → flagged, no response, no access.
        state["transaction"] = {"id": "tx-1", "status": "paid", "amount": 1, "userID": 96001}
        assert buyer.post(hook, json=settlement(payload, payer=96001, amount=900_000, transaction_id="tx-1"), headers=secret).status_code == 200
        flagged = buyer.get(f"/api/public/forms/{form_id}/payment-intents/{payment_id}").json()
        assert flagged["status"] == "paid_review" and buyer.get(download).status_code == 403
        with Session(engine) as db:
            assert db.scalar(select(RecordingOrderRecord.id)) is None and db.scalar(select(RecordingAccessRecord.id)) is None
        assert owner.get(f"/api/forms/{form_id}/responses").json()["total"] == 0
        # Staff resolve a flagged wallet payment outside the webhook: the audited manual grant (reason required).
        granted = owner.post(f"/api/admin/events/{event_id}/recording/access",
                             json={"account_id": buyer_id, "reason": "تراکنش tx-1 در پنل بله بررسی و تأیید شد"}, headers=owner_write_headers(owner))
        assert granted.status_code == 201 and granted.json()["access"]["source"] == "granted"
        assert buyer.get(download).status_code == 200

        # Second buyer: clean settlement grants once; duplicate deliveries and a second charge never double-grant.
        second = TestClient(app)
        second_id = bale_login(second, 96003)
        assert second.get(f"/api/public/forms/{form_id}/draft").status_code == 200
        assert second.patch(f"/api/public/forms/{form_id}/draft", json={"answers": {"full-name": "خریدار دوم"}}, headers=ORIGIN).status_code == 200
        opened2 = intent(second)
        assert opened2.status_code == 201, opened2.text
        payload2 = state["payloads"][-1]
        state["transaction"] = {"id": "tx-2", "status": "paid", "amount": 900_000, "userID": 96003}
        for _ in range(3):
            assert second.post(hook, json=settlement(payload2, payer=96003, amount=900_000, transaction_id="tx-2"), headers=secret).status_code == 200
        state["transaction"] = {"id": "tx-3", "status": "paid", "amount": 900_000, "userID": 96003}
        assert second.post(hook, json=settlement(payload2, payer=96003, amount=900_000, transaction_id="tx-3"), headers=secret).status_code == 200
        paid = second.get("/api/account/recording-orders").json()
        assert paid["total"] == 1 and paid["items"][0]["status"] == "paid" and paid["items"][0]["paid_at"] and paid["items"][0]["method"] == "bale_wallet"
        order2_id = paid["items"][0]["id"]
        with Session(engine) as db:
            rows = db.scalars(select(RecordingAccessRecord).where(RecordingAccessRecord.account_id == second_id)).all()
            assert len(rows) == 1 and rows[0].source == "purchase" and rows[0].order_id == order2_id
            order_row = db.get(RecordingOrderRecord, order2_id)
            assert order_row.transaction_id == "tx-2" and order_row.form_response_id and order_row.form_payment_id
            assert db.scalar(select(FormResponseRecord.id).where(FormResponseRecord.id == order_row.form_response_id))
            assert len(db.scalars(select(UserNotificationRecord).where(UserNotificationRecord.account_id == second_id)).all()) == 1
            # The verified response is a purchase, never a registration/ticket.
            response_row = db.get(FormResponseRecord, order_row.form_response_id)
            assert response_row.form_snapshot["purpose"] == "recording_access" and response_row.ticket_checked_in_at is None
        assert second.get(download).status_code == 200
        assert recording_view(second, event_id)["viewer"]["cta"]["kind"] == "view"
        # Guest cannot reach the file with the same URL; the order list of the buyer shows the real state.
        assert TestClient(app).get(download).status_code == 401
        listed = second.get("/api/account/recording-orders").json()["items"]
        assert [item["status"] for item in listed] == ["paid"] and "invoice_url" not in listed[0]
        assert buyer_id != second_id
        queue = owner.get("/api/admin/recording-orders?status=paid").json()
        assert queue["total"] == 1 and queue["items"][0]["id"] == order2_id


def test_buyers_review_with_server_badge_and_questions_can_anchor_to_a_published_session():
    """Phase 9 §9: a verified buyer may review (badge 'buyer', never 'attendee'); a non-buyer non-attendee is
    refused with a reason that names the real options; questions may reference one published session of the
    same event's product and nothing else (foreign/draft/unknown sessions → 404)."""
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            held, version = held_event(owner, 0)
            other_held, version = held_event(owner, version, t="کارگاه دیگر")
            product = build_sellable_product(owner, held, price=0, payment_card=None)
            assert set_status(owner, held, "ready").status_code == 200
            assert set_status(owner, held, "published").status_code == 200
            recording_id, session_id = product["recording"]["id"], product["_session_id"]
            draft_session = owner.post(f"/api/admin/events/{held}/recording/sessions",
                                       json={"title": "جلسهٔ پیش‌نویس"}, headers=owner_write_headers(owner))
            assert draft_session.status_code == 201
            foreign = build_sellable_product(owner, other_held, price=0, payment_card=None)

            member = TestClient(app)
            bale_login(member, 97001)
            headers = account_write_headers(member)
            # Not attended, not a buyer: refused with the real options.
            refused = member.post(f"/api/account/events/{held}/reviews", json={"body": "دیدگاه پیش از خرید"}, headers=headers)
            assert refused.status_code == 403 and refused.json()["detail"]["reason"] == "attendance_or_purchase_required"
            before = interaction(member, held)["reviews"]
            assert (before["eligible"], before["badge"]) == (False, "")
            # Claim the free product → buyer → may review; badge decided server-side.
            assert member.post(f"/api/account/recordings/{recording_id}/claim", headers=headers).status_code == 201
            payload = interaction(member, held)
            assert payload["viewer"]["buyer"] is True and (payload["reviews"]["eligible"], payload["reviews"]["badge"]) == (True, "buyer")
            review = member.post(f"/api/account/events/{held}/reviews", json={"body": "دیدگاه خریدار دربارهٔ محتوای ضبط‌شده"}, headers=headers)
            assert review.status_code == 201, review.text
            assert review.json()["badge"] == "buyer" and review.json()["verified_attendee"] is False
            mine = interaction(member, held)["reviews"]["mine"]
            assert mine["badge"] == "buyer" and mine["status"] == "pending"

            # Session-level question: only a published session of this event's product.
            ask = f"/api/account/events/{held}/questions"
            assert member.post(ask, json={"body": "سؤال دربارهٔ جلسهٔ یکم که مفصل است", "session_id": session_id}, headers=headers).status_code == 201
            assert member.post(ask, json={"body": "سؤال دربارهٔ جلسهٔ پیش‌نویس که مفصل است", "session_id": draft_session.json()["id"]},
                               headers=headers).status_code == 404
            assert member.post(ask, json={"body": "سؤال دربارهٔ جلسهٔ رویداد دیگر که مفصل است", "session_id": foreign["_session_id"]},
                               headers=headers).status_code == 404
            assert member.post(ask, json={"body": "سؤال با شناسهٔ نامعتبر که مفصل است", "session_id": "nope"}, headers=headers).status_code == 404
            assert member.post(ask, json={"body": "سؤال عمومی بدون جلسه که مفصل است", "session_id": None}, headers=headers).status_code == 201
            questions = interaction(member, held)["questions"]["items"]
            assert {q["session_id"] for q in questions} == {session_id, None}
            # The admin list carries the session title so moderators see the anchor.
            listed = owner.get(f"/api/admin/events/{held}/questions").json()["items"]
            anchored = [q for q in listed if q["session_id"] == session_id]
            assert len(anchored) == 1
    finally:
        engine.dispose()



def test_rejected_card_orders_notify_the_buyer_with_the_reason_and_allow_a_fresh_order():
    """Phase 9.1 §7/§8: a rejection is a reviewed inbox decision with a reason; the buyer learns about it through
    the same outbox (recorded ≠ delivered), gains no access, the response is removed (no stale registration
    look-alike), the ledger row stays as history and the buyer may fill the purchase form again."""
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            held, _version = held_event(owner, 0)
            # FAQ supplied on the very first PUT (regression: the create path used to pass ``faq`` twice).
            product = build_sellable_product(owner, held, price=1_200_000, payment_card=None,
                                             faq=[{"q": "دانلود دارد؟", "a": "فقط جزوه."}])
            assert product["recording"]["faq"] == [{"q": "دانلود دارد؟", "a": "فقط جزوه."}]
            recording_id = product["recording"]["id"]
            form_id = purchase_form(owner, recording_id, price=1_200_000)
            assert set_status(owner, held, "ready").status_code == 200
            assert set_status(owner, held, "published").status_code == 200
            download = f"/api/public/events/{held}/resources/{product['_resource_id']}/download"

            buyer = TestClient(app)
            buyer_id = bale_login(buyer, 97101)
            bought = submit_purchase(buyer, form_id)
            assert bought.status_code == 200 and bought.json()["payment_status"] == "awaiting_receipt"
            sent = upload_purchase_receipt(buyer, form_id)
            assert sent.status_code == 200 and sent.json()["review_task_id"]
            task_id = sent.json()["review_task_id"]
            order_id = buyer.get("/api/account/recording-orders").json()["items"][0]["id"]
            assert buyer.get(f"/api/account/recording-orders/{order_id}").json()["status"] == "receipt_submitted"
            assert notifications(engine, buyer_id) == []
            # The receipt itself is a private file: only reviewers read it, through the task.
            assert owner.get(f"/api/admin/recording-orders/{order_id}/receipt").status_code in (200, 404)

            rejected = inbox_decide(owner, task_id, "rejected", "مبلغ واریزی با سفارش نمی‌خواند", owner_write_headers(owner))
            assert rejected.status_code == 200, rejected.text
            assert buyer.get(download).status_code == 403
            queued = notifications(engine, buyer_id)
            assert [item.kind for item in queued] == ["receipt_rejected"]
            assert "مبلغ واریزی با سفارش نمی‌خواند" in queued[0].body and "نسخهٔ ضبط‌شدهٔ کارگاه" in queued[0].body
            assert queued[0].delivery_status == "pending" and queued[0].delivery_attempts == 0  # queued ≠ delivered
            mine = buyer.get(f"/api/account/recording-orders/{order_id}").json()
            assert mine["status"] == "rejected" and mine["decision_reason"] == "مبلغ واریزی با سفارش نمی‌خواند" and mine["open"] is False
            assert owner.get(f"/api/forms/{form_id}/responses").json()["total"] == 0  # the rejected response is gone
            with Session(engine) as db:
                ledger = db.get(RecordingOrderRecord, order_id)
                assert ledger.form_response_id is None and ledger.status == "rejected"
                assert db.scalar(select(RecordingAccessRecord.id)) is None
            cta = recording_view(buyer, held)["viewer"]["cta"]
            assert cta["kind"] == "buy" and cta["previous"] == {"status": "rejected", "id": order_id} and cta["form_id"] == form_id
            again = submit_purchase(buyer, form_id, name="خریدار (بار دوم)")
            assert again.status_code == 200 and again.json()["payment_status"] == "awaiting_receipt"
            orders = buyer.get("/api/account/recording-orders").json()
            assert orders["total"] == 2 and {row["status"] for row in orders["items"]} == {"rejected", "awaiting_receipt"}
            assert "recording.order.reject" in audit_actions(engine)
    finally:
        engine.dispose()




def test_registration_and_purchase_forms_of_one_event_stay_separate():
    """Phase 9.1 §1: the registration form follows the event window and feeds participation; the purchase form
    follows the product, never creates a registration, is excluded from the bot catalogue and keeps working
    after the registration deadline."""
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            # Event with an open registration window first, so a real registrant exists.
            event_id, version = create_published_event(
                owner, 0, t="کارگاه با دو فرم", startsAt=iso(timedelta(days=3)), endsAt=iso(timedelta(days=3, hours=3)),
                regClosesAt=iso(timedelta(days=2)))
            registration_form = create_published_form(owner, event_id=event_id, key="separate-forms-reg-0001")
            registrant = TestClient(app)
            registrant_id = bale_login(registrant, 98001)
            assert registrant.get(f"/api/public/forms/{registration_form}/draft").status_code == 200
            registered = registrant.post(f"/api/public/forms/{registration_form}/responses",
                                         json={"answers": {"full-name": "شرکت‌کنندهٔ واقعی"}}, headers=ORIGIN)
            assert registered.status_code == 200 and registered.json()["purpose"] == "registration" and registered.json()["purchase"] is None
            assert interaction(registrant, event_id)["viewer"]["participation"]["registered"] is True

            # The event is held; its product goes on sale through a purchase form.
            version = update_event(owner, event_id, version, startsAt=iso(timedelta(days=-9)), endsAt=iso(timedelta(days=-8)),
                                   regClosesAt=iso(timedelta(days=-10)), past=True)
            product = build_sellable_product(owner, event_id, price=700_000, payment_card=None)
            recording_id = product["recording"]["id"]
            form_id = purchase_form(owner, recording_id, price=700_000)
            assert set_status(owner, event_id, "ready").status_code == 200
            assert set_status(owner, event_id, "published").status_code == 200

            # Registration form: closed by the event window (API cannot bypass). Purchase form: open.
            late = TestClient(app)
            bale_login(late, 98002)
            closed_draft = late.get(f"/api/public/forms/{registration_form}/draft")
            assert closed_draft.status_code == 409 and closed_draft.json()["detail"]["code"] == "registration_closed"
            closed = late.post(f"/api/public/forms/{registration_form}/responses",
                               json={"answers": {"full-name": "دیررسیده"}}, headers=ORIGIN)
            assert closed.status_code in (401, 409)  # no draft can even be opened for a closed registration
            bought = submit_purchase(late, form_id, name="خریدار دیررسیده")
            assert bought.status_code == 200 and bought.json()["purpose"] == "recording_access"
            # The buyer is still not a registrant; the registrant is still not a buyer.
            assert interaction(late, event_id)["viewer"]["participation"]["registered"] is False
            registrant_page = interaction(registrant, event_id)["viewer"]
            assert registrant_page["participation"]["registered"] is True and registrant_page["buyer"] is False
            assert recording_view(registrant, event_id)["viewer"]["cta"]["kind"] == "buy"
            # Form lists: the registration list of the event does not contain the purchase response and vice versa.
            assert owner.get(f"/api/forms/{registration_form}/responses").json()["total"] == 1
            assert owner.get(f"/api/forms/{form_id}/responses").json()["total"] == 1
            assert owner.get(f"/api/forms/{form_id}").json()["purpose"] == "recording_access"
            # The bot catalogue (free, ticket-oriented forms) never lists a purchase form.
            catalogue = owner.get("/api/bot/forms/public", headers={"Authorization": "Bearer " + SERVICE_TOKEN})
            assert catalogue.status_code == 200 and form_id not in {row["id"] for row in catalogue.json()["items"]}
            # A registration form cannot be turned into a purchase form by relabeling it through the API.
            current = owner.get(f"/api/forms/{registration_form}").json()
            relabel = owner.put(f"/api/forms/{registration_form}",
                                json={"name": current["name"], "model": current["model"], "need": current["need"],
                                      "settings": current["settings"], "fields": current["fields"],
                                      "purpose": "recording_access", "recording_id": recording_id,
                                      "expected_version": current["version"]},
                                headers=owner_write_headers(owner))
            assert relabel.status_code == 409 and relabel.json()["detail"]["code"] in {"published_form_read_only", "form_has_responses"}
            assert owner.get(f"/api/forms/{registration_form}").json()["purpose"] == "registration"
            assert registrant_id
    finally:
        engine.dispose()
