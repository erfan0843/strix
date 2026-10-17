"""تنظیمات ذخیره‌شده باید واقعاً مصرف شوند، نه فقط ذخیره.

این آزمون‌ها ثابت می‌کنند که مقدارِ رمزنگاری‌شده در پایگاه (و نه فقط متغیر
محیطی) مبنای رفتار مسیرهای عملیاتی وب است:

- آمادگی پرداخت (`/api/health`، `/api/public/forms/capabilities`، readiness و
  انتشار فرم) از مقادیر مؤثر نتیجه می‌گیرد، حتی وقتی env خالی است.
- `createInvoiceLink` با توکن ربات پرداختِ ذخیره‌شده فراخوانی می‌شود و
  `provider_token` همان توکن کیف پول ذخیره‌شده است؛ هیچ کپی خودکاری بین این دو نیست.
- نشانی وب‌هوک و تأیید درخواست بازگشتی از یک پیکربندی مؤثر ساخته و سنجیده می‌شوند.
- با تنظیمات ناقص، مسیر پرداخت رد می‌شود و پنل «آماده» ادعا نمی‌کند.
- هیچ مقدار محرمانه‌ای در پاسخ API یا لاگ ظاهر نمی‌شود.
- توکن با شکل Bot API در فیلد Provider Token پذیرفته نمی‌شود و برعکس.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

import backend.app as backend_app  # noqa: E402
from backend.app import _form_payment_registered_webhook_url, _form_payment_webhook_token, create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import Base, FormPaymentRecord, PaymentSecretRecord  # noqa: E402
from backend.security import hash_password  # noqa: E402
from backend.service_settings import effective_settings  # noqa: E402

OWNER_USER = "nora-owner"
OWNER_PASS = "correct-horse-staple-42"
ORIGIN = {"Origin": "http://testserver"}
WEBHOOK_BASE = "https://forms.nora.ir/api/payments/bale/webhook"

# مقادیر ساختگی آزمون؛ هیچ‌کدام اعتبارنامهٔ واقعی نیستند.
DB_PAYMENT_BOT_TOKEN = "555555555:" + "P" * 32
DB_PROVIDER_TOKEN = "WALLET-provider-token-test-only-0001"
DB_WEBHOOK_SECRET = "s" * 40
ENV_ONLY_BOT_TOKEN = "444444444:" + "E" * 32


def base_settings() -> Settings:
    """env بدون هیچ اعتبارنامهٔ پرداخت؛ فقط نشانی وب‌هوک (فقط‌خواندنی) تنظیم است."""
    return Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username=OWNER_USER,
        owner_password_hash=hash_password(OWNER_PASS),
        cookie_secure=False,
        bot_service_token="b" * 48,
        form_payment_webhook_url=WEBHOOK_BASE,
        form_payment_timeout_seconds=8,
    )


@pytest.fixture
def runtime_env(monkeypatch):
    monkeypatch.setenv("NORA_SETTINGS_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    state: dict = {"webhook_url": "", "calls": []}

    def fake_bale_api(config, method, payload):
        state["calls"].append((method, dict(payload), config.form_payment_bot_token))
        if method == "getWebhookInfo":
            return {"ok": True, "result": {"url": state["webhook_url"]}}
        if method == "setWebhook":
            state["webhook_url"] = payload["url"]
            return {"ok": True, "result": True}
        if method == "createInvoiceLink":
            return {"ok": True, "result": "https://ble.ir/invoice/test-payment"}
        if method == "answerPreCheckoutQuery":
            return {"ok": True, "result": True}
        raise AssertionError(f"unexpected Bale method: {method}")

    monkeypatch.setattr(backend_app, "call_bale_payment_api", fake_bale_api)
    settings = base_settings()
    app = create_app(settings, engine=engine)
    with TestClient(app) as client:
        yield client, settings, state
    engine.dispose()


def login(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login", json={"username": OWNER_USER, "password": OWNER_PASS}, headers=ORIGIN
    )
    assert response.status_code == 200, response.text
    return {**ORIGIN, "X-CSRF-Token": client.cookies.get("nora_csrf", "")}


def store(client: TestClient, headers: dict[str, str], storage_id: str, value: str) -> dict:
    response = client.put(
        f"/api/owner/service-settings/{storage_id}", json={"value": value}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def store_full_payment_config(client: TestClient, headers: dict[str, str]) -> dict:
    store(client, headers, "bale_wallet", DB_PAYMENT_BOT_TOKEN)
    store(client, headers, "payment_provider", DB_PROVIDER_TOKEN)
    return store(client, headers, "payment_webhook", DB_WEBHOOK_SECRET)


def payment_service(payload: dict) -> dict:
    return next(item for item in payload["services"] if item["key"] == "payment")


def wallet_form() -> dict:
    return {
        "name": "ثبت‌نام با کیف پول",
        "model": "registration",
        "need": "reg",
        "slug": "wallet-runtime-form",
        "ev": "event-wallet-runtime",
        "settings": {
            "enabledPaymentMethods": ["bale_wallet"],
            "receiptReviewRequired": False,
            "fin": [{"l": "ورودی", "p": 120000, "off": 0, "req": True, "d": ""}],
        },
        "fields": [{"id": "full-name", "t": "fullname", "l": "نام کامل", "required": True}],
    }


def create_wallet_form(client: TestClient, headers: dict[str, str]) -> str:
    created = client.post(
        "/api/forms", json=wallet_form(), headers={**headers, "Idempotency-Key": "runtime-form-create-key-01"}
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def publish(client: TestClient, headers: dict[str, str], form_id: str):
    return client.post(f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=headers)


def visitor_with_draft(client: TestClient, form_id: str) -> TestClient:
    visitor = TestClient(client.app)
    assert visitor.get(f"/api/public/forms/{form_id}/draft").status_code == 200
    saved = visitor.patch(
        f"/api/public/forms/{form_id}/draft", json={"answers": {"full-name": "پرداخت‌کننده"}}, headers=ORIGIN
    )
    assert saved.status_code == 200, saved.text
    return visitor


def intent(visitor: TestClient, form_id: str):
    return visitor.post(
        f"/api/public/forms/{form_id}/payment-intents",
        json={"method": "bale_wallet", "selection": {"items": [0], "coupon_code": ""}},
        headers=ORIGIN,
    )


SECRETS = (DB_PAYMENT_BOT_TOKEN, DB_PROVIDER_TOKEN, DB_WEBHOOK_SECRET)


# ---------------------------------------------------------------------------
# ۱ — با env خالی، مسیر پرداخت بسته است و پنل آمادگی ادعا نمی‌کند
# ---------------------------------------------------------------------------

def test_unconfigured_payment_is_refused_everywhere_and_panel_says_so(runtime_env):
    client, settings, state = runtime_env
    assert settings.form_bale_payments_ready is False
    headers = login(client)

    status = client.get("/api/owner/service-settings", headers=headers).json()
    runtime = payment_service(status)["runtime"]
    assert runtime["ready"] is False
    assert runtime["scope"] == "web"
    assert set(runtime["missing"]) == {
        "NORA_FORM_PAYMENT_BOT_TOKEN",
        "NORA_FORM_PAYMENT_PROVIDER_TOKEN",
        "NORA_FORM_PAYMENT_WEBHOOK_SECRET",
    }
    assert payment_service(status)["state"] == "unconfigured"

    assert client.get("/api/health").json()["formBalePaymentsReady"] is False
    capabilities = client.get("/api/public/forms/capabilities").json()
    assert capabilities["settings"]["bale_wallet"]["status"] == "unavailable"

    form_id = create_wallet_form(client, headers)
    readiness = client.get(f"/api/forms/{form_id}/readiness", headers=headers).json()
    assert readiness["issues"], readiness
    blocked = publish(client, headers, form_id)
    assert blocked.status_code == 422, blocked.text

    # وب‌هوک با پیکربندی ناقص اصلاً باز نمی‌شود.
    webhook = client.post(
        "/api/payments/bale/webhook/" + "0" * 64, json={"update_id": 1}, headers=ORIGIN
    )
    assert webhook.status_code == 503
    assert state["calls"] == []


# ---------------------------------------------------------------------------
# ۲ — پایگاه، منبع معتبر وب است حتی بدون env؛ invoice با توکن‌های ذخیره‌شده
# ---------------------------------------------------------------------------

def test_database_values_drive_readiness_invoice_and_webhook_without_env(runtime_env, caplog):
    client, settings, state = runtime_env
    headers = login(client)
    caplog.set_level(logging.INFO)

    status = store_full_payment_config(client, headers)
    runtime = payment_service(status)["runtime"]
    assert runtime == {"ready": True, "missing": [], "scope": "web"}
    # «فعال در وب» ≠ «آزمایش‌شده»: هنوز هیچ آزمایش اتصالی ثبت نشده است.
    assert payment_service(status)["state"] == "configured"

    # متغیرهای محیطی همچنان خالی‌اند؛ فقط لایهٔ مؤثر مقدار دارد.
    assert settings.form_payment_bot_token == ""
    assert settings.form_payment_provider_token == ""
    assert settings.form_payment_webhook_secret == ""
    with client.app.state.session_factory() as db:
        effective = effective_settings(db, settings)
    assert effective.form_payment_bot_token == DB_PAYMENT_BOT_TOKEN
    assert effective.form_payment_provider_token == DB_PROVIDER_TOKEN
    assert effective.form_payment_webhook_secret == DB_WEBHOOK_SECRET
    assert effective.form_bale_payments_ready is True

    assert client.get("/api/health").json()["formBalePaymentsReady"] is True
    capabilities = client.get("/api/public/forms/capabilities").json()
    assert capabilities["settings"]["bale_wallet"]["status"] == "server"

    form_id = create_wallet_form(client, headers)
    readiness = client.get(f"/api/forms/{form_id}/readiness", headers=headers).json()
    assert readiness["issues"] == []
    published = publish(client, headers, form_id)
    assert published.status_code == 200, published.text
    public = client.get(f"/api/public/forms/{form_id}")
    assert public.status_code == 200 and public.json()["enabledPaymentMethods"] == ["bale_wallet"]

    visitor = visitor_with_draft(client, form_id)
    created = intent(visitor, form_id)
    assert created.status_code == 201, created.text

    # هر فراخوانی Bot API با توکن ربات پرداختِ ذخیره‌شده انجام شد.
    assert state["calls"], "no Bale API call was made"
    assert {token for _method, _payload, token in state["calls"]} == {DB_PAYMENT_BOT_TOKEN}
    invoice = next(payload for method, payload, _ in state["calls"] if method == "createInvoiceLink")
    assert invoice["provider_token"] == DB_PROVIDER_TOKEN
    assert invoice["provider_token"] != DB_PAYMENT_BOT_TOKEN

    # نشانی وب‌هوک ثبت‌شده از همان پیکربندی مؤثر ساخته شده، نه از env خالی.
    assert state["webhook_url"] == _form_payment_registered_webhook_url(effective)
    assert state["webhook_url"].startswith(WEBHOOK_BASE + "/")
    for secret in SECRETS:
        assert secret not in state["webhook_url"]

    # تأیید درخواست بازگشتی با همان مرز: مسیر مؤثر + راز ذخیره‌شده.
    effective_path = "/api/payments/bale/webhook/" + _form_payment_webhook_token(effective)
    wrong_secret = client.post(
        effective_path,
        json={"update_id": 1},
        headers={**ORIGIN, "x-telegram-bot-api-secret-token": "not-the-secret-" + "x" * 20},
    )
    assert wrong_secret.status_code == 403
    accepted = client.post(
        effective_path,
        json={"update_id": 2},
        headers={**ORIGIN, "x-telegram-bot-api-secret-token": DB_WEBHOOK_SECRET},
    )
    assert accepted.status_code == 200, accepted.text
    env_only_path = "/api/payments/bale/webhook/" + _form_payment_webhook_token(settings)
    assert env_only_path != effective_path
    assert client.post(env_only_path, json={"update_id": 3}, headers=ORIGIN).status_code == 404

    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count(FormPaymentRecord.id))) == 1

    # هیچ مقدار محرمانه‌ای در هیچ پاسخ API یا لاگی ظاهر نشد.
    exposed_bodies = [
        client.get("/api/owner/service-settings", headers=headers).text,
        created.text,
        public.text,
        readiness and str(readiness),
    ]
    for body in exposed_bodies:
        for secret in SECRETS:
            assert secret not in body
    for secret in SECRETS:
        assert secret not in caplog.text


# ---------------------------------------------------------------------------
# ۳ — تنظیمات ناقص (فقط توکن ربات) → رد مسیر پرداخت، بدون ادعای آمادگی
# ---------------------------------------------------------------------------

def test_partial_configuration_keeps_payment_closed(runtime_env):
    client, _settings, state = runtime_env
    headers = login(client)
    status = store(client, headers, "bale_wallet", DB_PAYMENT_BOT_TOKEN)
    runtime = payment_service(status)["runtime"]
    assert runtime["ready"] is False
    assert "NORA_FORM_PAYMENT_PROVIDER_TOKEN" in runtime["missing"]
    assert "NORA_FORM_PAYMENT_WEBHOOK_SECRET" in runtime["missing"]
    assert "NORA_FORM_PAYMENT_BOT_TOKEN" not in runtime["missing"]
    # فیلد «تنظیم‌شده» است اما سرویس «آماده» نیست.
    bot_field = next(f for f in payment_service(status)["fields"] if f["key"] == "bale_wallet")
    assert bot_field["configured"] is True
    assert client.get("/api/health").json()["formBalePaymentsReady"] is False

    form_id = create_wallet_form(client, headers)
    assert publish(client, headers, form_id).status_code == 422
    assert state["calls"] == []


# ---------------------------------------------------------------------------
# ۴ — تفکیک دو توکن: هیچ کپی خودکاری؛ شکل اشتباه در فیلد اشتباه رد می‌شود
# ---------------------------------------------------------------------------

def test_payment_tokens_are_distinct_fields_with_distinct_contracts(runtime_env):
    client, _settings, _state = runtime_env
    headers = login(client)
    status = client.get("/api/owner/service-settings", headers=headers).json()
    fields = {f["key"]: f for f in payment_service(status)["fields"]}
    assert fields["bale_wallet"]["env_name"] == "NORA_FORM_PAYMENT_BOT_TOKEN"
    assert fields["bale_wallet"]["label"] == "توکن ربات پرداخت"
    assert fields["payment_provider"]["env_name"] == "NORA_FORM_PAYMENT_PROVIDER_TOKEN"
    assert "Provider Token" in fields["payment_provider"]["label"]
    assert fields["bale_wallet"]["consumers"] == ["web"]
    assert fields["payment_provider"]["consumers"] == ["web"]

    # توکن کیف پول در فیلد توکن ربات پذیرفته نمی‌شود.
    wrong = client.put(
        "/api/owner/service-settings/bale_wallet", json={"value": DB_PROVIDER_TOKEN}, headers=headers
    )
    assert wrong.status_code == 422 and wrong.json()["detail"] == "invalid_payment_bot_token"
    # توکن با شکل Bot API در فیلد Provider Token پذیرفته نمی‌شود.
    wrong2 = client.put(
        "/api/owner/service-settings/payment_provider",
        json={"value": DB_PAYMENT_BOT_TOKEN},
        headers=headers,
    )
    assert wrong2.status_code == 422
    assert wrong2.json()["detail"] == "provider_token_must_not_be_bot_token"
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count(PaymentSecretRecord.id))) == 0

    # ذخیرهٔ یکی، دیگری را پر نمی‌کند.
    store(client, headers, "bale_wallet", DB_PAYMENT_BOT_TOKEN)
    with client.app.state.session_factory() as db:
        effective = effective_settings(db, base_settings())
        assert effective.form_payment_bot_token == DB_PAYMENT_BOT_TOKEN
        assert effective.form_payment_provider_token == ""
        assert db.get(PaymentSecretRecord, "payment_provider") is None


# ---------------------------------------------------------------------------
# ۵ — دامنهٔ اثر هر اعتبارنامه برای پنل اعلام می‌شود (وب / وب+ربات)
# ---------------------------------------------------------------------------

def test_each_credential_declares_which_process_consumes_it(runtime_env):
    client, _settings, _state = runtime_env
    headers = login(client)
    status = client.get("/api/owner/service-settings", headers=headers).json()
    by_key = {f["key"]: f for s in status["services"] for f in s["fields"]}
    assert by_key["bale_bot"]["consumers"] == ["web", "bot"]
    assert by_key["bale_bot"]["bot_env_name"] == "BOT_TOKEN"
    assert by_key["safir_api_key"]["consumers"] == ["web", "bot"]
    assert by_key["safir_api_key"]["bot_env_name"] == "SAFIR_API_KEY"
    for key in ("bale_wallet", "payment_provider", "payment_webhook"):
        assert by_key[key]["consumers"] == ["web"]
        assert by_key[key]["bot_env_name"] == ""
    for service in status["services"]:
        assert service["runtime"]["scope"] == "web"
    # ذخیرهٔ توکن ربات اصلی، فرایند ربات را تغییر نمی‌دهد: فقط لایهٔ مؤثر وب.
    stored = client.put(
        "/api/owner/service-settings/bale_bot",
        json={"value": ENV_ONLY_BOT_TOKEN, "acknowledge_restart": True},
        headers=headers,
    )
    assert stored.status_code == 200, stored.text
    bale = next(s for s in stored.json()["services"] if s["key"] == "bale")
    assert bale["runtime"] == {"ready": True, "missing": [], "scope": "web"}
