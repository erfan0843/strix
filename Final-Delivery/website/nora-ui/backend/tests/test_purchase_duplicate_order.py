"""بازیابی پنل (مرحلهٔ C-2): یک سفارش باز برای هر حساب و هر محصول — سمت سرور، مستقل از کوکی مرورگر.

پیش از این، جلوگیری از پاسخ تکراری فقط به پیش‌نویس همان کوکی وابسته بود؛ همان حساب از دستگاه/کوکی دوم
می‌توانست سفارش دوم (و ردیف دفتر دوم) بسازد که باید دستی تطبیق می‌شد (یافتهٔ 9.7).
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend.models import RecordingOrderRecord  # noqa: E402

from test_event_registration_gate import gate_app  # noqa: E402
from test_recordings_api import (  # noqa: E402
    build_sellable_product,
    held_event,
    inbox_decide,
    purchase_form,
    set_status,
    submit_purchase,
    upload_purchase_receipt,
)
from test_workflows_api import bale_login, owner_login, owner_write_headers, signed_init_data  # noqa: E402


def second_device_login(client: TestClient, user_id: int, device: str) -> str:
    """Same Bale user on another device: fresh cookie jar, fresh (non-replayed) init data."""
    response = client.post("/api/auth/bale-mini-app",
                           json={"init_data": signed_init_data(user_id, query_id=f"{device}-{user_id}")},
                           headers={"Origin": "http://testserver"})
    assert response.status_code == 200, response.text
    return str(response.json()["account_id"])


def order_count(engine, account_id: str) -> int:
    with Session(engine) as db:
        return int(db.scalar(select(func.count(RecordingOrderRecord.id)).where(RecordingOrderRecord.account_id == account_id)) or 0)


def test_same_account_cannot_open_a_second_purchase_order_from_another_device():
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            held, _version = held_event(owner, 0)
            product = build_sellable_product(owner, held, price=900_000, payment_card=None)
            recording_id = product["recording"]["id"]
            form_id = purchase_form(owner, recording_id, price=900_000)
            assert set_status(owner, held, "ready").status_code == 200
            assert set_status(owner, held, "published").status_code == 200

            phone = TestClient(app)
            buyer_id = bale_login(phone, 97201)
            first = submit_purchase(phone, form_id)
            assert first.status_code == 200 and first.json()["payment_status"] == "awaiting_receipt"
            assert order_count(engine, buyer_id) == 1

            # Same account, second browser (fresh cookie jar → fresh draft): no parallel order.
            laptop = TestClient(app)
            assert second_device_login(laptop, 97201, "laptop") == buyer_id
            second = submit_purchase(laptop, form_id, name="همان خریدار از لپ‌تاپ")
            assert second.status_code == 409, second.text
            detail = second.json()["detail"]
            assert detail["code"] == "purchase_order_pending" and detail["recording_id"] == recording_id
            assert detail["order_status"] == "awaiting_receipt" and detail["response_id"]
            assert order_count(engine, buyer_id) == 1
            assert owner.get(f"/api/forms/{form_id}/responses").json()["total"] == 1

            # The wallet intent path is guarded by the same rule (even before any intent is created).
            intent = laptop.post(f"/api/public/forms/{form_id}/payment-intents",
                                 json={"method": "bale_wallet", "selection": {"items": [0], "coupon_code": ""}},
                                 headers={"Origin": "http://testserver"})
            assert intent.status_code in (409, 422, 503)
            if intent.status_code == 409:
                assert intent.json()["detail"]["code"] == "purchase_order_pending"

            # Resubmitting from the ORIGINAL draft is still the same order, not a duplicate.
            again = phone.post(f"/api/public/forms/{form_id}/responses",
                               json={"answers": {"full-name": "خریدار آزمایشی"},
                                     "payment": {"method": "card_transfer", "selection": {"items": [0], "coupon_code": ""}}},
                               headers={"Origin": "http://testserver"})
            assert again.status_code == 200, again.text
            assert order_count(engine, buyer_id) == 1

            # After the receipt is uploaded the order is under review: still exactly one, other device still refused.
            sent = upload_purchase_receipt(phone, form_id)
            assert sent.status_code == 200 and sent.json()["review_task_id"]
            blocked = submit_purchase(laptop, form_id)
            assert blocked.status_code == 409 and blocked.json()["detail"]["order_status"] == "receipt_submitted"

            # A different account is unaffected.
            other = TestClient(app)
            other_id = bale_login(other, 97202)
            assert submit_purchase(other, form_id, name="خریدار دیگر").status_code == 200
            assert order_count(engine, other_id) == 1

            # A rejected order is closed history: the buyer may order again (existing 9.1 rule kept).
            rejected = inbox_decide(owner, sent.json()["review_task_id"], "rejected", "مبلغ نمی‌خواند", owner_write_headers(owner))
            assert rejected.status_code == 200, rejected.text
            fresh = submit_purchase(laptop, form_id, name="خریدار · سفارش تازه")
            assert fresh.status_code == 200 and fresh.json()["payment_status"] == "awaiting_receipt"
            assert order_count(engine, buyer_id) == 2
    finally:
        engine.dispose()
