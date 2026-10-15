"""Owner-managed Bale wallet key: encrypted storage, masked reads, and payment wiring.

Test keys are generated per run and fake; no real provider token is used.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import Base, PaymentSecretRecord  # noqa: E402
from backend.secret_box import decrypt_secret  # noqa: E402
from backend.security import hash_password  # noqa: E402

PASSWORD = "correct-horse-staple-42"
FAKE_KEY = "123456789:AAFakeWalletKeyForTestsOnly_0123456789"
FAKE_KEY_2 = "987654321:BBAnotherFakeKeyForTests_9876543210"


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine, monkeypatch):
    monkeypatch.setenv("NORA_SETTINGS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    settings = Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username="nora-owner",
        owner_password_hash=hash_password(PASSWORD),
        session_ttl_seconds=3600,
        cookie_secure=False,
        bale_bot_username="nora_test_bot",
        bot_service_token="payment-secrets-test-service-token-0123456789",
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "nora-owner", "password": PASSWORD},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200, response.text


def write_headers(client: TestClient) -> dict[str, str]:
    return {"Origin": "http://testserver", "X-CSRF-Token": client.cookies.get("nora_csrf", "")}


def test_settings_read_requires_owner(client):
    response = client.get("/api/owner/payment-settings")
    assert response.status_code in {401, 403}


def test_saving_key_requires_owner_session(client):
    response = client.put(
        "/api/owner/payment-settings/bale-wallet",
        json={"api_key": FAKE_KEY},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code in {401, 403}


def test_save_stores_only_ciphertext_and_returns_hint(client, engine):
    login(client)
    response = client.put(
        "/api/owner/payment-settings/bale-wallet",
        json={"api_key": FAKE_KEY},
        headers=write_headers(client),
    )
    assert response.status_code == 200, response.text
    body = response.json()["bale_wallet"]
    assert body["configured"] is True
    assert body["source"] == "database"
    assert body["hint"].endswith(FAKE_KEY[-4:])
    assert FAKE_KEY not in response.text

    from sqlalchemy.orm import Session

    with Session(engine) as session:
        record = session.get(PaymentSecretRecord, "bale_wallet")
        assert record is not None
        assert FAKE_KEY not in record.ciphertext
        assert decrypt_secret(record.ciphertext) == FAKE_KEY


def test_get_never_returns_full_key(client):
    login(client)
    client.put(
        "/api/owner/payment-settings/bale-wallet",
        json={"api_key": FAKE_KEY},
        headers=write_headers(client),
    )
    response = client.get("/api/owner/payment-settings")
    assert response.status_code == 200
    assert FAKE_KEY not in response.text
    assert response.json()["bale_wallet"]["encryption_ready"] is True


def test_invalid_format_is_rejected(client):
    login(client)
    response = client.put(
        "/api/owner/payment-settings/bale-wallet",
        json={"api_key": "not-a-key"},
        headers=write_headers(client),
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "invalid_bale_wallet_key_format"


def test_save_refused_without_encryption_key(client, monkeypatch):
    monkeypatch.delenv("NORA_SETTINGS_ENCRYPTION_KEY", raising=False)
    login(client)
    response = client.put(
        "/api/owner/payment-settings/bale-wallet",
        json={"api_key": FAKE_KEY},
        headers=write_headers(client),
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "settings_encryption_not_configured"


def test_clear_removes_saved_key(client):
    login(client)
    client.put(
        "/api/owner/payment-settings/bale-wallet",
        json={"api_key": FAKE_KEY},
        headers=write_headers(client),
    )
    response = client.delete("/api/owner/payment-settings/bale-wallet", headers=write_headers(client))
    assert response.status_code == 200
    assert response.json()["bale_wallet"]["configured"] is False


def test_payment_config_prefers_saved_key(client, engine):
    from sqlalchemy.orm import Session

    from backend.app import _payment_cfg
    from backend.config import Settings as _S
    from backend.secret_box import encrypt_secret

    base = _S(
        database_url=None,
        owner_id="owner-01",
        owner_username="nora-owner",
        owner_password_hash=hash_password(PASSWORD),
        session_ttl_seconds=3600,
        cookie_secure=False,
        bale_bot_username="nora_test_bot",
        bot_service_token="payment-secrets-test-service-token-0123456789",
    )
    with Session(engine) as session:
        assert _payment_cfg(session, base).form_payment_bot_token == ""
        session.add(PaymentSecretRecord(id="bale_wallet", ciphertext=encrypt_secret(FAKE_KEY_2), hint="x"))
        session.commit()
        assert _payment_cfg(session, base).form_payment_bot_token == FAKE_KEY_2
