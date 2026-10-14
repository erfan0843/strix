from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool


BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

import backend.app as backend_app  # noqa: E402
from backend.app import _form_payment_registered_webhook_url, _form_payment_webhook_token, create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import FormPaymentRecord, FormPaymentTransactionRecord, FormResponseRecord  # noqa: E402
from backend.security import hash_password  # noqa: E402


PAYMENT_BOT_TOKEN = "1234567890:" + "A" * 32
PAYMENT_PROVIDER_TOKEN = "provider-test-token-not-a-real-credential"
PAYMENT_WEBHOOK_SECRET = "w" * 48
PAYMENT_WEBHOOK_BASE = "https://forms.nora.ir/api/payments/bale/webhook"
ORIGIN = {"Origin": "http://testserver"}


def valid_settings() -> Settings:
    return Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"),
        session_ttl_seconds=3600,
        cookie_secure=False,
        bot_service_token="b" * 48,
        bale_bot_token="9876543210:" + "B" * 32,
        bale_bot_username="nora_test_bot",
        form_payment_bot_token=PAYMENT_BOT_TOKEN,
        form_payment_provider_token=PAYMENT_PROVIDER_TOKEN,
        form_payment_webhook_secret=PAYMENT_WEBHOOK_SECRET,
        form_payment_webhook_url=PAYMENT_WEBHOOK_BASE,
        form_payment_timeout_seconds=8,
    )


@pytest.fixture
def payment_app(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    backend_app.Base.metadata.create_all(engine)
    settings = valid_settings()
    state = {
        "webhook_url": "",
        "transaction": None,
        "calls": [],
        "pre_checkout": [],
        "invoice_payloads": [],
    }

    def fake_bale_api(config, method, payload):
        assert config.form_payment_bot_token == PAYMENT_BOT_TOKEN
        assert config.form_payment_bot_token != config.bale_bot_token
        state["calls"].append((method, dict(payload)))
        if method == "getWebhookInfo":
            return {"ok": True, "result": {"url": state["webhook_url"]}}
        if method == "setWebhook":
            state["webhook_url"] = payload["url"]
            return {"ok": True, "result": True}
        if method == "createInvoiceLink":
            state["invoice_payloads"].append(payload["payload"])
            return {"ok": True, "result": "https://ble.ir/invoice/test-payment"}
        if method == "answerPreCheckoutQuery":
            state["pre_checkout"].append(dict(payload))
            return {"ok": True, "result": True}
        if method == "inquireTransaction":
            assert state["transaction"] is not None
            return {"ok": True, "result": dict(state["transaction"])}
        raise AssertionError(f"unexpected Bale method: {method}")

    monkeypatch.setattr(backend_app, "call_bale_payment_api", fake_bale_api)
    app = create_app(settings, engine=engine)
    with TestClient(app) as client:
        yield client, settings, state
    engine.dispose()


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "nora-owner", "password": "correct-horse-staple-42"},
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text


def owner_write_headers(client: TestClient, key: str = "wallet-form-create-key-01") -> dict[str, str]:
    return {
        **ORIGIN,
        "X-CSRF-Token": client.cookies.get("nora_csrf", ""),
        "Idempotency-Key": key,
    }


def valid_wallet_form() -> dict:
    return {
        "name": "ثبت‌نام کیف پول بله",
        "model": "registration",
        "need": "reg",
        "slug": "wallet-payment-form",
        "ev": "event-wallet-01",
        "settings": {
            "enabledPaymentMethods": ["bale_wallet"],
            "receiptReviewRequired": False,
            "fin": [{"l": "ورودی نمونه", "p": 650000, "off": 0, "req": True, "d": ""}],
        },
        "fields": [
            {"id": "full-name", "t": "fullname", "l": "نام کامل", "required": True},
            {"id": "city", "t": "text", "l": "شهر", "required": False},
        ],
    }


def create_published_wallet_form(owner: TestClient):
    login(owner)
    created = owner.post(
        "/api/forms",
        json=valid_wallet_form(),
        headers=owner_write_headers(owner),
    )
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    published = owner.post(
        f"/api/forms/{form_id}/publish",
        json={"expected_version": 1},
        headers={**ORIGIN, "X-CSRF-Token": owner.cookies.get("nora_csrf", "")},
    )
    assert published.status_code == 200, published.text

    visitor = TestClient(owner.app)
    public = visitor.get(f"/api/public/forms/{form_id}")
    assert public.status_code == 200, public.text
    assert public.json()["enabledPaymentMethods"] == ["bale_wallet"]
    draft = visitor.get(f"/api/public/forms/{form_id}/draft")
    assert draft.status_code == 200, draft.text
    saved = visitor.patch(
        f"/api/public/forms/{form_id}/draft",
        json={"answers": {"full-name": "نام پرداخت‌کننده"}},
        headers=ORIGIN,
    )
    assert saved.status_code == 200, saved.text
    return form_id, visitor


def create_payment_intent(visitor: TestClient, form_id: str):
    return visitor.post(
        f"/api/public/forms/{form_id}/payment-intents",
        json={"method": "bale_wallet", "selection": {"items": [0], "coupon_code": ""}},
        headers=ORIGIN,
    )


def webhook_path(settings: Settings) -> str:
    return "/api/payments/bale/webhook/" + _form_payment_webhook_token(settings)


def success_update(
    invoice_payload: str,
    *,
    transaction_id: str = "bale-tx-001",
    charge_id: str = "provider-charge-001",
) -> dict:
    return {
        "update_id": 123,
        "message": {
            "from": {"id": 73421},
            "successful_payment": {
                "invoice_payload": invoice_payload,
                "telegram_payment_charge_id": transaction_id,
                "provider_payment_charge_id": charge_id,
                "currency": "IRR",
                "total_amount": 650000,
            },
        },
    }


def test_wallet_readiness_fails_closed_for_incomplete_or_unsafe_configuration(monkeypatch):
    settings = valid_settings()
    assert settings.form_bale_payments_ready is True
    assert Settings(
        database_url=None, owner_id="", owner_username="", owner_password_hash=""
    ).form_bale_payments_ready is False

    unsafe_settings = [
        replace(settings, form_payment_bot_token=""),
        replace(settings, form_payment_bot_token="not-a-bot-token"),
        replace(settings, form_payment_provider_token=""),
        replace(settings, form_payment_webhook_secret="short"),
        replace(settings, form_payment_webhook_secret="w" * 32 + "\n"),
        replace(settings, form_payment_webhook_url="http://forms.example.test/api/payments/bale/webhook"),
        replace(settings, form_payment_webhook_url="https://forms.example.test/wrong-path"),
        replace(settings, form_payment_webhook_url="https://localhost/api/payments/bale/webhook"),
        replace(settings, form_payment_webhook_url="https://10.0.0.4/api/payments/bale/webhook"),
        replace(settings, form_payment_webhook_url="https://forms.example.test/api/payments/bale/webhook"),
        replace(settings, form_payment_timeout_seconds=9),
    ]
    assert all(config.form_bale_payments_ready is False for config in unsafe_settings)

    monkeypatch.setenv("NORA_FORM_PAYMENT_BOT_TOKEN", PAYMENT_BOT_TOKEN)
    monkeypatch.setenv("NORA_FORM_PAYMENT_PROVIDER_TOKEN", PAYMENT_PROVIDER_TOKEN)
    monkeypatch.setenv("NORA_FORM_PAYMENT_WEBHOOK_SECRET", PAYMENT_WEBHOOK_SECRET)
    monkeypatch.setenv("NORA_FORM_PAYMENT_WEBHOOK_URL", PAYMENT_WEBHOOK_BASE)
    monkeypatch.setenv("NORA_FORM_PAYMENT_TIMEOUT_SECONDS", "8")
    loaded = Settings.from_env()
    assert loaded.form_bale_payments_ready is True
    assert all(secret not in repr(loaded) for secret in (
        PAYMENT_BOT_TOKEN, PAYMENT_PROVIDER_TOKEN, PAYMENT_WEBHOOK_SECRET,
    ))

    monkeypatch.setenv("NORA_FORM_PAYMENT_TIMEOUT_SECONDS", "9")
    with pytest.raises(ValueError, match="NORA_FORM_PAYMENT_TIMEOUT_SECONDS"):
        Settings.from_env()


def test_wallet_method_cannot_be_published_without_full_secure_configuration(payment_app):
    owner, configured, state = payment_app
    owner.app.state.settings = replace(
        configured,
        form_payment_bot_token="",
        form_payment_provider_token="",
        form_payment_webhook_secret="",
        form_payment_webhook_url="",
    )
    login(owner)
    health = owner.get("/api/health")
    assert health.status_code == 200 and health.json()["formBalePaymentsReady"] is False

    created = owner.post(
        "/api/forms",
        json=valid_wallet_form(),
        headers=owner_write_headers(owner),
    )
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    publish = owner.post(
        f"/api/forms/{form_id}/publish",
        json={"expected_version": 1},
        headers={**ORIGIN, "X-CSRF-Token": owner.cookies.get("nora_csrf", "")},
    )
    assert publish.status_code == 422
    assert "bale_payment_not_configured" in {
        issue["code"] for issue in publish.json()["detail"]["issues"]
    }
    assert state["calls"] == []


def test_wallet_invoice_and_precheckout_are_server_owned_and_idempotent(payment_app):
    owner, settings, state = payment_app
    form_id, visitor = create_published_wallet_form(owner)

    intent = create_payment_intent(visitor, form_id)
    assert intent.status_code == 201, intent.text
    first = intent.json()
    assert first["method"] == "bale_wallet"
    assert first["status"] == "pending"
    assert first["amount"] == 650000 and first["currency"] == "IRR"
    assert first["invoice_url"] == "https://ble.ir/invoice/test-payment"
    assert state["webhook_url"] == _form_payment_registered_webhook_url(settings)
    assert state["webhook_url"].startswith(PAYMENT_WEBHOOK_BASE + "/")
    assert PAYMENT_WEBHOOK_SECRET not in state["webhook_url"]
    assert PAYMENT_BOT_TOKEN not in state["webhook_url"]
    assert PAYMENT_PROVIDER_TOKEN not in state["webhook_url"]
    assert sum(method == "setWebhook" for method, _ in state["calls"]) == 1
    assert sum(method == "createInvoiceLink" for method, _ in state["calls"]) == 1
    invoice_call = next(payload for method, payload in state["calls"] if method == "createInvoiceLink")
    assert invoice_call["provider_token"] == PAYMENT_PROVIDER_TOKEN
    assert invoice_call["currency"] == "IRR" and invoice_call["prices"] == [
        {"label": "ثبت‌نام کیف پول بله", "amount": 650000}
    ]

    repeated = create_payment_intent(visitor, form_id)
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["payment_id"] == first["payment_id"]
    assert sum(method == "createInvoiceLink" for method, _ in state["calls"]) == 1
    with owner.app.state.session_factory() as db:
        assert db.scalar(select(func.count(FormPaymentRecord.id))) == 1
        payment = db.get(FormPaymentRecord, first["payment_id"])
        invoice_payload = payment.invoice_payload
        assert payment.transaction_id is None and payment.status == "pending"
        assert db.scalar(select(func.count(FormResponseRecord.id))) == 0

    checkout_body = {
        "pre_checkout_query": {
            "id": "pre-checkout-001",
            "from": {"id": 73421},
            "invoice_payload": invoice_payload,
            "currency": "IRR",
            "total_amount": 650000,
        }
    }
    checkout = owner.post(webhook_path(settings), json=checkout_body)
    assert checkout.status_code == 200 and checkout.json() == {"ok": True}
    assert state["pre_checkout"][-1] == {
        "pre_checkout_query_id": "pre-checkout-001",
        "ok": True,
    }
    rejected_checkout = owner.post(
        webhook_path(settings),
        json={"pre_checkout_query": {
            **checkout_body["pre_checkout_query"],
            "id": "pre-checkout-wrong-amount",
            "total_amount": 650001,
        }},
    )
    assert rejected_checkout.status_code == 200
    assert state["pre_checkout"][-1]["ok"] is False
    assert "error_message" in state["pre_checkout"][-1]
    status_view = visitor.get(
        f"/api/public/forms/{form_id}/payment-intents/{first['payment_id']}"
    )
    assert status_view.status_code == 200 and status_view.json()["status"] == "pending"
    assert status_view.json()["selection"] == {
        "items": [0], "coupon_code": "", "party_count": 1,
    }
    restored_selection = visitor.get(
        f"/api/public/forms/{form_id}/draft"
    ).json()["payment_intent"]["selection"]
    assert restored_selection == status_view.json()["selection"]
    with owner.app.state.session_factory() as db:
        assert db.scalar(select(func.count(FormResponseRecord.id))) == 0


def test_successful_payment_is_verified_and_duplicate_webhooks_do_not_duplicate_response(payment_app):
    owner, settings, state = payment_app
    form_id, visitor = create_published_wallet_form(owner)
    created = create_payment_intent(visitor, form_id)
    assert created.status_code == 201, created.text
    payment_id = created.json()["payment_id"]
    with owner.app.state.session_factory() as db:
        payment = db.get(FormPaymentRecord, payment_id)
        invoice_payload = payment.invoice_payload

    state["transaction"] = {
        "id": "bale-tx-001", "status": "paid", "userID": 73421, "amount": 650000,
    }
    callback = success_update(invoice_payload)
    first = owner.post(webhook_path(settings), json=callback)
    assert first.status_code == 200, first.text
    intent = visitor.get(f"/api/public/forms/{form_id}/payment-intents/{payment_id}")
    assert intent.status_code == 200
    assert intent.json()["status"] == "paid"
    assert intent.json()["response_status"] == "accepted"
    assert intent.json()["tracking_code"]
    link = visitor.post(f"/api/public/forms/{form_id}/ticket-link", json={}, headers=ORIGIN)
    assert link.status_code == 200, link.text
    assert link.json()["delivery_url"].startswith("https://ble.ir/nora_test_bot?start=ft_")

    duplicate_delivery = owner.post(webhook_path(settings), json=callback)
    assert duplicate_delivery.status_code == 200
    assert sum(method == "inquireTransaction" for method, _ in state["calls"]) == 1

    state["transaction"] = {
        "id": "bale-tx-002", "status": "paid", "userID": 73421, "amount": 650000,
    }
    duplicate_charge = owner.post(
        webhook_path(settings),
        json=success_update(invoice_payload, transaction_id="bale-tx-002", charge_id="provider-charge-002"),
    )
    assert duplicate_charge.status_code == 200
    with owner.app.state.session_factory() as db:
        payment = db.get(FormPaymentRecord, payment_id)
        transaction_rows = db.scalars(
            select(FormPaymentTransactionRecord).order_by(FormPaymentTransactionRecord.transaction_id)
        ).all()
        assert payment.status == "paid" and payment.response_id
        assert len(transaction_rows) == 2
        assert [row.status for row in transaction_rows] == ["verified", "duplicate"]
        assert db.scalar(select(func.count(FormResponseRecord.id))) == 1
    assert visitor.get(
        f"/api/public/forms/{form_id}/payment-intents/{payment_id}"
    ).json()["status"] == "paid"


def test_success_callback_with_mismatched_provider_payer_is_quarantined(payment_app):
    owner, settings, state = payment_app
    form_id, visitor = create_published_wallet_form(owner)
    created = create_payment_intent(visitor, form_id)
    assert created.status_code == 201, created.text
    payment_id = created.json()["payment_id"]
    with owner.app.state.session_factory() as db:
        invoice_payload = db.get(FormPaymentRecord, payment_id).invoice_payload

    state["transaction"] = {
        "id": "bale-tx-wrong-payer", "status": "paid", "userID": 99999, "amount": 650000,
    }
    callback = success_update(
        invoice_payload,
        transaction_id="bale-tx-wrong-payer",
        charge_id="provider-charge-wrong-payer",
    )
    response = owner.post(webhook_path(settings), json=callback)
    assert response.status_code == 200, response.text
    payment_status = visitor.get(
        f"/api/public/forms/{form_id}/payment-intents/{payment_id}"
    ).json()
    assert payment_status["status"] == "paid_review"
    assert payment_status["response_status"] is None
    assert visitor.get(f"/api/public/forms/{form_id}/draft").json()["submitted"] is False
    with owner.app.state.session_factory() as db:
        payment = db.get(FormPaymentRecord, payment_id)
        transaction = db.scalar(select(FormPaymentTransactionRecord))
        assert payment.status == "paid_review" and payment.response_id is None
        assert transaction.status == "needs_review"
        assert db.scalar(select(func.count(FormResponseRecord.id))) == 0
        assert db.scalar(select(func.count(FormPaymentTransactionRecord.id))) == 1


def test_pending_provider_transaction_never_confirms_payment(payment_app):
    owner, settings, state = payment_app
    form_id, visitor = create_published_wallet_form(owner)
    created = create_payment_intent(visitor, form_id)
    assert created.status_code == 201, created.text
    payment_id = created.json()["payment_id"]
    with owner.app.state.session_factory() as db:
        invoice_payload = db.get(FormPaymentRecord, payment_id).invoice_payload
    state["transaction"] = {
        "id": "bale-tx-pending", "status": "pending", "userID": 73421, "amount": 650000,
    }
    response = owner.post(
        webhook_path(settings),
        json=success_update(
            invoice_payload,
            transaction_id="bale-tx-pending",
            charge_id="provider-charge-pending",
        ),
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "bale_transaction_pending"
    assert visitor.get(
        f"/api/public/forms/{form_id}/payment-intents/{payment_id}"
    ).json()["status"] == "pending"
    with owner.app.state.session_factory() as db:
        assert db.scalar(select(func.count(FormResponseRecord.id))) == 0
        assert db.scalar(select(func.count(FormPaymentTransactionRecord.id))) == 0
