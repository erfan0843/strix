"""تنظیمات متمرکز اتصال سرویس‌ها: ذخیرهٔ رمزنگاری‌شده، ماسک‌شدن و مرز مجوز.

این آزمون‌ها همان چیزهایی را می‌سنجند که در رابط کاربری دیده می‌شود، ولی از
سمت سرور: مقدار محرمانه هرگز برنمی‌گردد، فقط مالک/دارندهٔ `sys_settings`
می‌تواند بخواند یا بنویسد، تعویض یک کلید کلیدهای دیگر را پاک نمی‌کند، و
«آزمایش اتصال» فقط با یک فراخوانی واقعیِ بی‌اثر (getMe) ثبت می‌شود.
"""
from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

import backend.app as backend_app_module  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import (  # noqa: E402
    AccountRecord,
    AccountRoleRecord,
    AccountSessionRecord,
    Base,
    PaymentSecretRecord,
    ServiceCheckRecord,
)
from backend.security import hash_password, token_digest  # noqa: E402

OWNER_USER = "nora-owner"
OWNER_PASS = "correct-horse-staple-42"
SESSION = "service-settings-session"
CSRF = "service-settings-csrf"
ORIGIN = {"Origin": "http://testserver"}
WALLET_TOKEN = "123456789:" + "A" * 32
BALE_TOKEN = "987654321:" + "B" * 32


@pytest.fixture
def settings_env(monkeypatch):
    monkeypatch.setenv("NORA_SETTINGS_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username=OWNER_USER,
        owner_password_hash=hash_password(OWNER_PASS),
        cookie_secure=False,
        otp_pepper="p" * 40,
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as client:
        yield client, engine, app
    engine.dispose()


def owner_headers(client: TestClient) -> dict[str, str]:
    login = client.post(
        "/api/auth/login",
        json={"username": OWNER_USER, "password": OWNER_PASS},
        headers=ORIGIN,
    )
    assert login.status_code == 200, login.text
    return {
        **ORIGIN,
        "X-CSRF-Token": client.cookies.get("nora_csrf", ""),
    }


def install_manager_session(client: TestClient, account_id: str) -> None:
    with client.app.state.session_factory() as db:
        db.add(AccountRecord(id=account_id))
        db.add(AccountRoleRecord(account_id=account_id, role="manager", assigned_by="owner-01"))
        db.add(
            AccountSessionRecord(
                id=str(uuid.uuid4()),
                account_id=account_id,
                auth_provider="manager-password",
                token_hash=token_digest(SESSION + account_id),
                csrf_hash=token_digest(CSRF + account_id),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.commit()
    settings = client.app.state.settings
    client.cookies.set(settings.account_cookie_name, SESSION + account_id, path="/")
    client.cookies.set(settings.account_csrf_cookie_name, CSRF + account_id, path="/")


def manager_headers(client: TestClient, account_id: str) -> dict[str, str]:
    return {**ORIGIN, "X-CSRF-Token": CSRF + account_id}


def service(service_key: str) -> dict:
    return next(item for item in client_state["services"] if item["key"] == service_key)


def field_of(service_key: str, storage_id: str) -> dict:
    return next(
        item for item in service(service_key)["fields"] if item["key"] == storage_id
    )


client_state: dict = {}


def refresh(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.get("/api/owner/service-settings", headers=headers)
    assert response.status_code == 200, response.text
    client_state.clear()
    client_state.update(response.json())
    return client_state


# ---------------------------------------------------------------------------
# مجوزها
# ---------------------------------------------------------------------------

def test_owner_sees_the_settings_map_and_managers_cannot(settings_env):
    client, _engine, _app = settings_env
    assert client.get("/api/owner/service-settings").status_code == 401

    anonymous_post = client.put(
        "/api/owner/service-settings/bale_wallet", json={"value": WALLET_TOKEN}, headers=ORIGIN
    )
    assert anonymous_post.status_code == 401

    install_manager_session(client, "acct-manager")
    denied = client.get("/api/owner/service-settings")
    assert denied.status_code == 403
    assert denied.json()["detail"] == "permission_denied"
    denied_write = client.put(
        "/api/owner/service-settings/bale_wallet",
        json={"value": WALLET_TOKEN},
        headers=manager_headers(client, "acct-manager"),
    )
    assert denied_write.status_code == 403


def test_owner_map_has_three_services_and_no_secret_values(settings_env):
    client, _engine, _app = settings_env
    headers = owner_headers(client)
    payload = refresh(client, headers)
    assert payload["encryption_ready"] is True
    assert [item["key"] for item in payload["services"]] == ["bale", "sms", "payment"]
    assert {item["state"] for item in payload["services"]} == {"unconfigured"}
    for item in payload["services"]:
        for secret_field in item["fields"]:
            assert "value" not in secret_field, "پاسخ API نباید هیچ مقدار محرمانه‌ای داشته باشد"
    # نام متغیرها از کد استخراج شده‌اند، نه ساخته‌شده.
    assert field_of("payment", "bale_wallet")["env_name"] == "NORA_FORM_PAYMENT_BOT_TOKEN"
    assert field_of("sms", "safir_api_key")["env_name"] == "SAFIR_API_KEY"
    assert field_of("bale", "bale_bot")["env_name"] == "NORA_BALE_BOT_TOKEN"


# ---------------------------------------------------------------------------
# ذخیره، ماسک و تعویض
# ---------------------------------------------------------------------------

def test_saving_encrypts_and_never_echoes_the_secret(settings_env, caplog):
    client, engine, _app = settings_env
    headers = owner_headers(client)
    caplog.set_level(logging.INFO, logger="nora.service_settings")

    saved = client.put(
        "/api/owner/service-settings/bale_wallet",
        json={"value": WALLET_TOKEN},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    assert WALLET_TOKEN not in saved.text
    client_state.clear()
    client_state.update(saved.json())
    field = field_of("payment", "bale_wallet")
    assert field["configured"] is True
    assert field["source"] == "database"
    assert field["hint"].endswith(WALLET_TOKEN[-4:])
    assert field["updated_at"]

    with Session(engine) as db:
        record = db.get(PaymentSecretRecord, "bale_wallet")
        assert record is not None
        assert WALLET_TOKEN not in record.ciphertext
        assert record.hint == field["hint"]

    assert WALLET_TOKEN not in caplog.text
    assert "bale_wallet" in caplog.text


def test_rotating_one_secret_keeps_the_others(settings_env):
    client, engine, _app = settings_env
    headers = owner_headers(client)
    assert client.put(
        "/api/owner/service-settings/payment_provider",
        json={"value": "provider-token-1"},
        headers=headers,
    ).status_code == 200
    assert client.put(
        "/api/owner/service-settings/bale_wallet",
        json={"value": WALLET_TOKEN},
        headers=headers,
    ).status_code == 200
    rotated = client.put(
        "/api/owner/service-settings/bale_wallet",
        json={"value": "123456789:" + "C" * 32},
        headers=headers,
    )
    assert rotated.status_code == 200
    client_state.clear()
    client_state.update(rotated.json())
    assert field_of("payment", "payment_provider")["configured"] is True
    assert field_of("payment", "payment_provider")["hint"] == "…en-1"
    with Session(engine) as db:
        assert {row.id for row in db.scalars(select(PaymentSecretRecord))} == {
            "payment_provider",
            "bale_wallet",
        }


def test_empty_or_invalid_values_are_refused_without_touching_storage(settings_env):
    client, engine, _app = settings_env
    headers = owner_headers(client)
    for payload, expected in (
        ({"value": "   "}, "empty_secret_value"),
        ({"value": "not-a-token"}, "invalid_payment_bot_token"),
        ({"value": WALLET_TOKEN, "extra": 1}, "invalid_service_secret_payload"),
    ):
        response = client.put(
            "/api/owner/service-settings/bale_wallet", json=payload, headers=headers
        )
        assert response.status_code in (400, 422), response.text
        assert expected in response.text
    with Session(engine) as db:
        assert db.get(PaymentSecretRecord, "bale_wallet") is None


def test_csrf_is_required_for_writes(settings_env):
    client, _engine, _app = settings_env
    owner_headers(client)
    without_csrf = client.put(
        "/api/owner/service-settings/bale_wallet",
        json={"value": WALLET_TOKEN},
        headers=ORIGIN,
    )
    assert without_csrf.status_code == 403
    assert without_csrf.json()["detail"] == "csrf_check_failed"


def test_deleting_a_secret_falls_back_to_environment(settings_env):
    client, engine, _app = settings_env
    headers = owner_headers(client)
    client.put(
        "/api/owner/service-settings/bale_wallet", json={"value": WALLET_TOKEN}, headers=headers
    )
    removed = client.delete("/api/owner/service-settings/bale_wallet", headers=headers)
    assert removed.status_code == 200
    client_state.clear()
    client_state.update(removed.json())
    field = field_of("payment", "bale_wallet")
    assert field["configured"] is False
    assert field["source"] == "none"
    with Session(engine) as db:
        assert db.get(PaymentSecretRecord, "bale_wallet") is None


def test_read_only_secrets_are_not_writable(settings_env):
    client, _engine, _app = settings_env
    headers = owner_headers(client)
    response = client.put(
        "/api/owner/service-settings/bot_service",
        json={"value": "x" * 40},
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "unknown_service_secret"


def test_without_the_encryption_key_writes_are_refused(settings_env, monkeypatch):
    client, engine, _app = settings_env
    headers = owner_headers(client)
    monkeypatch.delenv("NORA_SETTINGS_ENCRYPTION_KEY", raising=False)
    response = client.put(
        "/api/owner/service-settings/bale_wallet", json={"value": WALLET_TOKEN}, headers=headers
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "settings_encryption_not_configured"
    with Session(engine) as db:
        assert db.get(PaymentSecretRecord, "bale_wallet") is None


def test_restart_acknowledgement_is_required_for_the_bot_token(settings_env):
    client, _engine, _app = settings_env
    headers = owner_headers(client)
    refused = client.put(
        "/api/owner/service-settings/bale_bot", json={"value": BALE_TOKEN}, headers=headers
    )
    assert refused.status_code == 409
    assert refused.json()["detail"] == "restart_acknowledgement_required"
    accepted = client.put(
        "/api/owner/service-settings/bale_bot",
        json={"value": BALE_TOKEN, "acknowledge_restart": True},
        headers=headers,
    )
    assert accepted.status_code == 200


def test_safir_key_rotation_requires_an_independent_pepper(settings_env):
    client, engine, app = settings_env
    headers = owner_headers(client)
    # پروندهٔ Settings این fixture فلفل مستقل دارد.
    allowed = client.put(
        "/api/owner/service-settings/safir_api_key",
        json={"value": "safir-key-0123456789"},
        headers=headers,
    )
    assert allowed.status_code == 200, allowed.text
    # بدون فلفل مستقل، چرخش کلید رد می‌شود تا هویت‌های شماره‌ای پس از restart باطل نشوند.
    app.state.settings = Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username=OWNER_USER,
        owner_password_hash=hash_password(OWNER_PASS),
        cookie_secure=False,
        otp_pepper="",
    )
    blocked = client.put(
        "/api/owner/service-settings/safir_api_key",
        json={"value": "safir-key-9876543210"},
        headers=headers,
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "otp_pepper_required"


# ---------------------------------------------------------------------------
# اثر واقعی روی مسیرهای مصرف‌کننده
# ---------------------------------------------------------------------------

def test_saved_bale_token_enables_mini_app_linking_without_restart(settings_env):
    client, engine, app = settings_env
    headers = owner_headers(client)
    assert app.state.settings.bale_bot_token == ""
    anonymous = TestClient(client.app)
    account_id = "acct-linked"
    with Session(engine) as db:
        db.add(AccountRecord(id=account_id))
        db.add(AccountSessionRecord(
            id=str(uuid.uuid4()),
            account_id=account_id,
            auth_provider="phone",
            token_hash=token_digest(SESSION + account_id),
            csrf_hash=token_digest(CSRF + account_id),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        db.commit()
    anonymous.cookies.set(app.state.settings.account_cookie_name, SESSION + account_id, path="/")
    assert anonymous.get("/api/account/identities").json()["bale_link_available"] is False

    assert client.put(
        "/api/owner/service-settings/bale_bot",
        json={"value": BALE_TOKEN, "acknowledge_restart": True},
        headers=headers,
    ).status_code == 200
    assert anonymous.get("/api/account/identities").json()["bale_link_available"] is True


# ---------------------------------------------------------------------------
# آزمایش اتصال
# ---------------------------------------------------------------------------

def test_connection_test_is_persisted_and_registered_only_when_real(settings_env, monkeypatch):
    client, engine, _app = settings_env
    headers = owner_headers(client)
    client.put(
        "/api/owner/service-settings/bale_wallet", json={"value": WALLET_TOKEN}, headers=headers
    )
    calls: list[str] = []

    def fake_probe(token: str):
        calls.append(token)
        return True, "bot_api_ok"

    monkeypatch.setattr(backend_app_module, "probe_bale_bot", fake_probe)
    tested = client.post("/api/owner/service-settings/bale_wallet/test", headers=headers)
    assert tested.status_code == 200, tested.text
    assert tested.json()["ok"] is True
    assert calls == [WALLET_TOKEN]
    with Session(engine) as db:
        check = db.get(ServiceCheckRecord, "bale_wallet")
        assert check is not None and check.ok is True
    client_state.clear()
    client_state.update(client.get("/api/owner/service-settings", headers=headers).json())
    assert field_of("payment", "bale_wallet")["check"]["ok"] is True
    assert service("payment")["state"] == "verified"

    # شکست واقعی هم ثبت می‌شود و وضعیت را به failed می‌برد.
    monkeypatch.setattr(
        backend_app_module, "probe_bale_bot", lambda token: (False, "bot_token_rejected")
    )
    failed = client.post("/api/owner/service-settings/bale_wallet/test", headers=headers)
    assert failed.status_code == 200
    assert failed.json()["ok"] is False
    assert failed.json()["code"] == "bot_token_rejected"
    client_state.clear()
    client_state.update(client.get("/api/owner/service-settings", headers=headers).json())
    assert service("payment")["state"] == "failed"


def test_services_without_a_safe_probe_say_so(settings_env):
    client, _engine, _app = settings_env
    headers = owner_headers(client)
    client.put(
        "/api/owner/service-settings/safir_api_key",
        json={"value": "safir-key-0123456789"},
        headers=headers,
    )
    response = client.post("/api/owner/service-settings/safir_api_key/test", headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "connection_test_not_supported"


def test_a_new_value_invalidates_the_previous_test(settings_env, monkeypatch):
    client, engine, _app = settings_env
    headers = owner_headers(client)
    client.put(
        "/api/owner/service-settings/bale_wallet", json={"value": WALLET_TOKEN}, headers=headers
    )
    monkeypatch.setattr(backend_app_module, "probe_bale_bot", lambda token: (True, "bot_api_ok"))
    client.post("/api/owner/service-settings/bale_wallet/test", headers=headers)
    client.put(
        "/api/owner/service-settings/bale_wallet",
        json={"value": "123456789:" + "D" * 32},
        headers=headers,
    )
    with Session(engine) as db:
        assert db.get(ServiceCheckRecord, "bale_wallet") is None
    client_state.clear()
    client_state.update(client.get("/api/owner/service-settings", headers=headers).json())
    assert field_of("payment", "bale_wallet")["check"]["checked"] is False
    assert service("payment")["state"] == "configured"
