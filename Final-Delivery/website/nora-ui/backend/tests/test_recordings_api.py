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
    RecordingAccessRecord,
    RecordingOrderRecord,
    UserNotificationRecord,
)
from backend.security import hash_password  # noqa: E402

from test_event_interaction_api import audit_actions, interaction  # noqa: E402
from test_event_registration_gate import (  # noqa: E402
    create_published_event,
    gate_app,
    iso,
    public_event,
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


def notifications(engine, account_id: str) -> list[UserNotificationRecord]:
    with Session(engine) as db:
        return list(db.scalars(select(UserNotificationRecord).where(UserNotificationRecord.account_id == account_id)))


# ── card transfer: full purchase path, access, refund, sales states ──


def test_card_transfer_purchase_is_reviewed_server_side_and_access_is_decided_per_download():
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

            # Publishing is blocked until the product is really complete.
            created = put_recording(owner, event_id, title="نسخهٔ ضبط‌شدهٔ کارگاه", price=1_500_000)
            assert created.status_code == 200 and created.json()["status"] == "draft"
            assert set(created.json()["publish_blockers"]) == {"no_published_session", "no_live_resource", "no_payment_method"}
            assert set_status(owner, event_id, "published").status_code == 409  # draft → published is not a transition
            ready = set_status(owner, event_id, "ready")
            assert ready.status_code == 200 and ready.json()["status"] == "ready"
            blocked = set_status(owner, event_id, "published")
            assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "publish_blocked"
            assert "no_payment_method" in blocked.json()["detail"]["blockers"]

            # A session file may only hang off a session of this event's own product.
            foreign = owner.post(f"/api/admin/events/{other_event}/resources",
                                 json={"title": "فایل بیگانه", "access": "purchased", "session_id": "00000000-0000-0000-0000-000000000000"},
                                 headers=owner_write_headers(owner))
            assert foreign.status_code == 404

            product = build_sellable_product(owner, event_id)
            session_id, resource_id = product["_session_id"], product["_resource_id"]
            assert product["recording"]["publish_blockers"] == [] and product["recording"]["payment_card"]["number"] == CARD["number"]
            # Session with files cannot be deleted silently.
            blocked_delete = owner.delete(f"{base}/sessions/{session_id}", headers=owner_write_headers(owner))
            assert blocked_delete.status_code == 409 and blocked_delete.json()["detail"]["code"] == "session_has_resources"

            # Still not public while 'ready'.
            guest = TestClient(app)
            assert guest.get(f"/api/public/events/{event_id}/recording").status_code == 404
            assert "recording" not in public_event(guest, event_id)
            assert guest.get("/api/public/recordings").json()["total"] == 0

            published = set_status(owner, event_id, "published")
            assert published.status_code == 200 and published.json()["status"] == "published"
            assert published.json()["published_at"]

            # Shelf + snapshot: honest numbers only (one session, 55 minutes), card never public.
            shelf = guest.get("/api/public/recordings").json()
            assert shelf["total"] == 1 and shelf["items"][0]["event"]["id"] == event_id
            assert shelf["items"][0]["session_count"] == 1 and shelf["items"][0]["total_minutes"] == 55
            assert "payment_card" not in shelf["items"][0] and "buyers" not in shelf["items"][0]
            snapshot_event = public_event(guest, event_id)
            assert snapshot_event["recording"]["sellable"] is True and snapshot_event["recording"]["price"] == 1_500_000
            assert snapshot_event["registration"]["state"] == "ended"

            # Guest: CTA = login, download denied with 401, no bytes anywhere in the payload.
            view = recording_view(guest, event_id)
            assert view["viewer"]["cta"]["kind"] == "login" and view["viewer"]["access"]["state"] == "none"
            assert "payment_card" not in view and view["sessions"][0]["resources"][0]["allowed"] is False
            assert view["sessions"][0]["resources"][0]["reason"] == "login_required"
            download = f"/api/public/events/{event_id}/resources/{resource_id}/download"
            assert guest.get(download).status_code == 401
            # The general resource list no longer duplicates session files.
            assert all(row["id"] != resource_id for row in interaction(guest, event_id)["resources"])

            # Member without access: CTA = buy (card only, wallet not configured), direct URL → 403 + audit.
            member = TestClient(app)
            member_id = bale_login(member, 94001)
            view = recording_view(member, event_id)
            assert view["viewer"]["cta"] == {"kind": "buy", "reason": "purchase_required", "methods": ["card_transfer"]}
            denied = member.get(download)
            assert denied.status_code == 403 and denied.json()["detail"]["reason"] == "purchase_required"
            assert "recording.download.denied" in audit_actions(engine)
            # Free claim is refused for a paid product; wallet order refused when the wallet is unconfigured.
            paid = member.post(f"/api/account/recordings/{view['id']}/claim", headers=account_write_headers(member))
            assert paid.status_code == 409 and paid.json()["detail"]["code"] == "recording_not_free"
            wallet = member.post(f"/api/account/recordings/{view['id']}/orders", json={"method": "bale_wallet"},
                                 headers=account_write_headers(member))
            assert wallet.status_code == 503 and wallet.json()["detail"]["code"] == "payment_method_not_available"

            # Card order: server amount, card destination, idempotent re-POST.
            order = member.post(f"/api/account/recordings/{view['id']}/orders", json={"method": "card_transfer"},
                                headers=account_write_headers(member))
            assert order.status_code == 201, order.text
            order_id = order.json()["id"]
            assert order.json()["status"] == "awaiting_receipt" and order.json()["amount"] == 1_500_000
            assert order.json()["card"]["number"] == CARD["number"]
            again = member.post(f"/api/account/recordings/{view['id']}/orders", json={"method": "card_transfer"},
                                headers=account_write_headers(member))
            assert again.status_code == 200 and again.json()["id"] == order_id
            view = recording_view(member, event_id)
            assert view["viewer"]["cta"]["kind"] == "order_open" and view["viewer"]["cta"]["order"]["id"] == order_id
            # An open order blocks a price change (the buyer was quoted the old amount).
            price_change = put_recording(owner, event_id, price=1_200_000)
            assert price_change.status_code == 409 and price_change.json()["detail"]["code"] == "open_orders_block_price_change"

            # Receipt rules: executables/HTML refused, oversize refused, image accepted; still no access.
            receipt = f"/api/account/recording-orders/{order_id}/receipt"
            assert member.put(receipt, content=b"MZ\x90\x00", headers={**account_write_headers(member), "X-File-Name": "a.png"}).status_code == 415
            assert member.put(receipt, content=b"<html>", headers={**account_write_headers(member), "X-File-Name": "a.html"}).status_code == 415
            big = member.put(receipt, content=PNG + b"0" * recordings.RECEIPT_MAX_BYTES, headers={**account_write_headers(member), "X-File-Name": "big.png"})
            assert big.status_code == 413
            ok = member.put(receipt, content=PNG, headers={**account_write_headers(member), "X-File-Name": quote("../رسید.exe.png"), "X-Receipt-Note": quote("واریز شد")})
            assert ok.status_code == 200 and ok.json()["status"] == "receipt_submitted" and ok.json()["receipt_file_name"] == "رسید.exe.png"
            assert member.get(download).status_code == 403  # a receipt alone never opens the content
            assert member.get("/api/account/recordings").json()["items"] == []
            mine = member.get("/api/account/recording-orders").json()
            assert mine["total"] == 1 and mine["items"][0]["status"] == "receipt_submitted" and mine["items"][0]["title"]

            # Another account never sees this order (404, not 403); cancelling after submission is refused.
            stranger = TestClient(app)
            bale_login(stranger, 94002)
            assert stranger.get(f"/api/account/recording-orders/{order_id}").status_code == 404
            assert stranger.put(receipt, content=PNG, headers={**account_write_headers(stranger), "X-File-Name": "x.png"}).status_code == 404
            cancel = member.post(f"/api/account/recording-orders/{order_id}/cancel", headers=account_write_headers(member))
            assert cancel.status_code == 409

            # Manager (receipt_approve) reviews: reason required, approval grants access once.
            manager_id = bale_login(TestClient(app), 94003)
            manager = TestClient(app)
            assign_manager(manager, manager_id)  # separate client: ends logged in as the manager (owner stays owner)
            queue = manager.get("/api/admin/recording-orders?status=review")
            assert queue.status_code == 200 and queue.json()["total"] == 1
            row = queue.json()["items"][0]
            assert row["id"] == order_id and row["has_receipt"] is True and row["duplicates"] == 0 and row["event_title"]
            assert manager.get(f"/api/admin/recording-orders/{order_id}/receipt").status_code == 200
            assert manager.get(f"/api/admin/recording-orders?q={quote('نسخهٔ ضبط')}").json()["total"] == 1
            assert manager.get(f"/api/admin/recording-orders?event_id={other_event}").json()["total"] == 0
            no_reason = manager.post(f"/api/admin/recording-orders/{order_id}/decision", json={"decision": "approve"},
                                     headers=account_write_headers(manager))
            assert no_reason.status_code == 422
            approved = manager.post(f"/api/admin/recording-orders/{order_id}/decision",
                                    json={"decision": "approve", "reason": "رسید با مبلغ تطبیق داده شد"},
                                    headers=account_write_headers(manager))
            assert approved.status_code == 200, approved.text
            assert approved.json()["status"] == "paid_manual" and approved.json()["access"]["state"] == "active"
            repeat = manager.post(f"/api/admin/recording-orders/{order_id}/decision",
                                  json={"decision": "approve", "reason": "دوباره"}, headers=account_write_headers(manager))
            assert repeat.status_code == 409 and repeat.json()["detail"]["code"] == "order_not_reviewable"
            history = manager.get(f"/api/admin/recording-orders/{order_id}").json()["history"]
            assert [item["action"] for item in history] == ["recording.order.approve"]
            assert history[0]["details"]["reason"] == "رسید با مبلغ تطبیق داده شد"

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
            # Buyer may review (badge = buyer), attendance still false: purchase ≠ attendance.
            page = interaction(member, event_id)
            assert page["viewer"]["participation"]["attended"] is False and page["viewer"]["buyer"] is True
            assert page["reviews"]["eligible"] is True and page["reviews"]["badge"] == "buyer"

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
            # The buyer is told about the refund through the same outbox (recorded ≠ delivered), reason + reference included.
            after_refund = notifications(engine, member_id)
            assert [item.kind for item in after_refund] == ["recording_access", "recording_order"]
            assert "TRX-REF-2026-01" in after_refund[1].body and "انصراف خریدار" in after_refund[1].body and after_refund[1].delivery_status == "pending"
            # Export carries ids → finance only.
            assert manager.get("/api/admin/recording-orders?format=csv").status_code == 403
            export = owner.get("/api/admin/recording-orders?format=csv")
            assert export.status_code == 200 and "order_id" in export.text and order_id in export.text

            # Sales states: pausing needs a reason; paused = off_sale CTA; archived = gone from public.
            assert set_status(owner, event_id, "sales_paused").status_code == 422
            paused = set_status(owner, event_id, "sales_paused", "به‌روزرسانی ویدیوها")
            assert paused.status_code == 200 and paused.json()["status_reason"] == "به‌روزرسانی ویدیوها"
            assert recording_view(member, event_id)["viewer"]["cta"]["kind"] == "off_sale"
            assert member.post(f"/api/account/recordings/{view['id']}/orders", json={"method": "card_transfer"},
                               headers=account_write_headers(member)).status_code == 409
            assert public_event(guest, event_id)["recording"]["sellable"] is False
            assert set_status(owner, event_id, "archived", "پایان فروش").status_code == 200
            assert guest.get(f"/api/public/events/{event_id}/recording").status_code == 404
            assert "recording" not in public_event(guest, event_id)
            assert owner.get(base).json()["recording"]["status"] == "archived"  # staff still see it

            summary = owner.get("/api/admin/recordings/summary").json()
            assert summary["recordings"] == {"archived": 1} and summary["orders_refunded"] == 1 and summary["active_access"] == 0
            actions = audit_actions(engine)
            for action in ("recording.create", "recording.update", "recording.status", "recording.session.create",
                           "recording.order.approve", "recording.order.refund", "recording.orders.export"):
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
            assert view["free"] is True and view["viewer"]["cta"] == {"kind": "free", "reason": "free", "methods": []}
            assert member.get(download).status_code == 403
            assert member.post(f"/api/account/recordings/{recording_id}/orders", json={"method": "card_transfer"},
                               headers=account_write_headers(member)).status_code == 409
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

            # Draft product stays invisible to the public but is previewable by staff.
            draft_event, version = held_event(owner, version, t="کارگاه پیش‌نویس")
            draft = build_sellable_product(owner, draft_event, price=250_000)
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
    app, engine, settings, state = wallet_app
    hook = "/api/payments/bale/webhook/" + _form_payment_webhook_token(settings)
    secret = {"X-Telegram-Bot-Api-Secret-Token": PAYMENT_WEBHOOK_SECRET}
    with TestClient(app) as owner:
        owner_login(owner)
        event_id, _version = held_event(owner, 0)
        product = build_sellable_product(owner, event_id, price=900_000, payment_card=None, bale_enabled=True)
        assert product["recording"]["publish_blockers"] == []  # wallet is configured → a payment method exists
        assert set_status(owner, event_id, "ready").status_code == 200
        assert set_status(owner, event_id, "published").status_code == 200
        recording_id, resource_id = product["recording"]["id"], product["_resource_id"]
        download = f"/api/public/events/{event_id}/resources/{resource_id}/download"

        buyer = TestClient(app)
        buyer_id = bale_login(buyer, 96001)
        assert recording_view(buyer, event_id)["viewer"]["cta"]["methods"] == ["bale_wallet"]
        order = buyer.post(f"/api/account/recordings/{recording_id}/orders", json={"method": "bale_wallet"}, headers=account_write_headers(buyer))
        assert order.status_code == 201, order.text
        order_id = order.json()["id"]
        assert order.json()["status"] == "pending" and order.json()["invoice_url"] == "https://ble.ir/invoice/test-recording"
        payload = state["payloads"][-1]
        assert payload.startswith("norac_") and state["webhook_url"].endswith(_form_payment_webhook_token(settings))
        invoice_call = next(call for call in state["calls"] if call[0] == "createInvoiceLink")[1]
        assert invoice_call["prices"] == [{"label": "نسخهٔ ضبط‌شدهٔ کارگاه", "amount": 900_000}] and invoice_call["currency"] == "IRR"
        # Coming back from the invoice page changes nothing: no access until the webhook verifies.
        assert buyer.get(f"/api/account/recording-orders/{order_id}").json()["status"] == "pending"
        assert buyer.get(download).status_code == 403

        # Pre-checkout: wrong amount / other payer refused, exact match accepted.
        def precheckout(amount: int, payer: int, query_id: str) -> None:
            response = buyer.post(hook, json={"update_id": 1, "pre_checkout_query": {
                "id": query_id, "from": {"id": payer}, "currency": "IRR", "total_amount": amount, "invoice_payload": payload}}, headers=secret)
            assert response.status_code == 200
        precheckout(900_000, 96002, "pcq-other")
        precheckout(1, 96001, "pcq-amount")
        precheckout(900_000, 96001, "pcq-ok")
        assert [item["ok"] for item in state["pre_checkout"]] == [False, False, True]

        # Settlement with a provider that still says pending → 503 (Bale retries), nothing granted.
        state["transaction"] = {"id": "tx-1", "status": "pending", "amount": 900_000, "userID": 96001}
        assert buyer.post(hook, json=settlement(payload, payer=96001, amount=900_000, transaction_id="tx-1"), headers=secret).status_code == 503
        assert buyer.get(download).status_code == 403
        # Tampered callback: amount mismatch between provider inquiry and the order → needs_review, no access.
        state["transaction"] = {"id": "tx-1", "status": "paid", "amount": 1, "userID": 96001}
        assert buyer.post(hook, json=settlement(payload, payer=96001, amount=900_000, transaction_id="tx-1"), headers=secret).status_code == 200
        flagged = buyer.get(f"/api/account/recording-orders/{order_id}").json()
        assert flagged["status"] == "needs_review" and buyer.get(download).status_code == 403
        assert recording_view(buyer, event_id)["viewer"]["cta"]["kind"] == "order_open"
        # The owner (receipt_approve) resolves the flagged order with a reason; access follows.
        decided = owner.post(f"/api/admin/recording-orders/{order_id}/decision", json={"decision": "approve", "reason": "تراکنش در پنل بله تأیید شد"},
                             headers=owner_write_headers(owner))
        assert decided.status_code == 200 and decided.json()["status"] == "paid_manual"
        assert buyer.get(download).status_code == 200

        # Second buyer: clean settlement grants once; duplicate deliveries and a second charge never double-grant.
        second = TestClient(app)
        second_id = bale_login(second, 96003)
        order2 = second.post(f"/api/account/recordings/{recording_id}/orders", json={"method": "bale_wallet"}, headers=account_write_headers(second))
        assert order2.status_code == 201
        payload2 = state["payloads"][-1]
        state["transaction"] = {"id": "tx-2", "status": "paid", "amount": 900_000, "userID": 96003}
        for _ in range(3):
            assert second.post(hook, json=settlement(payload2, payer=96003, amount=900_000, transaction_id="tx-2"), headers=secret).status_code == 200
        paid = second.get(f"/api/account/recording-orders/{order2.json()['id']}").json()
        assert paid["status"] == "paid" and paid["paid_at"]
        state["transaction"] = {"id": "tx-3", "status": "paid", "amount": 900_000, "userID": 96003}
        assert second.post(hook, json=settlement(payload2, payer=96003, amount=900_000, transaction_id="tx-3"), headers=secret).status_code == 200
        # A settlement whose payer is not the account's verified Bale identity never grants.
        with Session(engine) as db:
            rows = db.scalars(select(RecordingAccessRecord).where(RecordingAccessRecord.account_id == second_id)).all()
            assert len(rows) == 1 and rows[0].source == "purchase" and rows[0].order_id == order2.json()["id"]
            assert db.scalar(select(RecordingOrderRecord).where(RecordingOrderRecord.id == order2.json()["id"])).transaction_id == "tx-2"
            assert len(db.scalars(select(UserNotificationRecord).where(UserNotificationRecord.account_id == second_id)).all()) == 1
        assert second.get(download).status_code == 200
        assert recording_view(second, event_id)["viewer"]["cta"]["kind"] == "view"
        # Guest cannot reach the file with the same URL; the order list of the buyer shows the real state.
        assert TestClient(app).get(download).status_code == 401
        listed = second.get("/api/account/recording-orders").json()["items"]
        assert [item["status"] for item in listed] == ["paid"] and "invoice_url" not in listed[0]
        assert buyer_id != second_id
        queue = owner.get("/api/admin/recording-orders?status=paid").json()
        assert queue["total"] == 2 and {row["status"] for row in queue["items"]} == {"paid", "paid_manual"}


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
    """Phase 9 §7/§8: a rejection is a reviewed decision with a reason; the buyer learns about it through the
    same outbox (recorded ≠ delivered), gains no access, sees the previous order on the CTA and may order again."""
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            held, _version = held_event(owner, 0)
            # FAQ supplied on the very first PUT (regression: the create path used to pass ``faq`` twice).
            product = build_sellable_product(owner, held, price=1_200_000,
                                             faq=[{"q": "دانلود دارد؟", "a": "فقط جزوه."}])
            assert product["recording"]["faq"] == [{"q": "دانلود دارد؟", "a": "فقط جزوه."}]
            assert set_status(owner, held, "ready").status_code == 200
            assert set_status(owner, held, "published").status_code == 200
            recording_id = product["recording"]["id"]
            download = f"/api/public/events/{held}/resources/{product['_resource_id']}/download"

            buyer = TestClient(app)
            buyer_id = bale_login(buyer, 97101)
            order = buyer.post(f"/api/account/recordings/{recording_id}/orders", json={"method": "card_transfer"}, headers=account_write_headers(buyer))
            assert order.status_code == 201
            order_id = order.json()["id"]
            sent = buyer.put(f"/api/account/recording-orders/{order_id}/receipt", content=PNG,
                             headers={**account_write_headers(buyer), "X-File-Name": "receipt.png"})
            assert sent.status_code == 200 and sent.json()["status"] == "receipt_submitted"
            assert notifications(engine, buyer_id) == []

            rejected = owner.post(f"/api/admin/recording-orders/{order_id}/decision",
                                  json={"decision": "reject", "reason": "مبلغ واریزی با سفارش نمی‌خواند"}, headers=owner_write_headers(owner))
            assert rejected.status_code == 200 and rejected.json()["status"] == "rejected" and rejected.json()["access"] is None
            assert buyer.get(download).status_code == 403
            queued = notifications(engine, buyer_id)
            assert [item.kind for item in queued] == ["recording_order"]
            assert "مبلغ واریزی با سفارش نمی‌خواند" in queued[0].body and queued[0].delivery_status == "pending" and queued[0].delivery_attempts == 0
            mine = buyer.get(f"/api/account/recording-orders/{order_id}").json()
            assert mine["status"] == "rejected" and mine["decision_reason"] == "مبلغ واریزی با سفارش نمی‌خواند" and mine["open"] is False
            cta = recording_view(buyer, held)["viewer"]["cta"]
            assert cta["kind"] == "buy" and cta["previous"] == {"status": "rejected", "id": order_id}
            again = buyer.post(f"/api/account/recordings/{recording_id}/orders", json={"method": "card_transfer"}, headers=account_write_headers(buyer))
            assert again.status_code == 201 and again.json()["id"] != order_id
            assert "recording.order.reject" in audit_actions(engine)
    finally:
        engine.dispose()
