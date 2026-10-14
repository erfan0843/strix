from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import (  # noqa: E402
    AccountRecord,
    AccountSessionRecord,
    Base,
    MiniAppAuthReplayRecord,
    PlatformIdentityRecord,
)
from backend.security import verify_bale_mini_app_init_data  # noqa: E402


BOT_TOKEN = "test-only-bale-token"
NOW = int(time.time())


def signed_init_data(*, user_id: int = 73421, auth_date: int = NOW, token: str = BOT_TOKEN) -> str:
    fields = {
        "auth_date": str(auth_date),
        "query_id": "test-query-001",
        "user": json.dumps(
            {"id": user_id, "first_name": "آزمایش", "username": "nora_test"},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    signature = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode([*fields.items(), ("hash", signature)])


@pytest.fixture
def auth_client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None,
        owner_id="",
        owner_username="",
        owner_password_hash="",
        cookie_secure=False,
        bale_bot_token=BOT_TOKEN,
        bale_init_data_max_age_seconds=600,
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


def test_documented_bale_hmac_verification_and_user_extraction():
    verified = verify_bale_mini_app_init_data(
        signed_init_data(), BOT_TOKEN, now=NOW, max_age_seconds=600
    )
    assert verified.user_id == 73421
    assert verified.auth_date == NOW
    assert len(verified.replay_key) == 64


@pytest.mark.parametrize(
    "raw,now",
    [
        (signed_init_data(auth_date=NOW - 601), NOW),
        (signed_init_data(auth_date=NOW + 61), NOW),
        (signed_init_data(user_id=0), NOW),
        (signed_init_data(user_id=-4), NOW),
    ],
)
def test_bale_init_data_rejects_expired_future_or_invalid_users(raw, now):
    with pytest.raises(ValueError, match="invalid_bale_init_data"):
        verify_bale_mini_app_init_data(raw, BOT_TOKEN, now=now, max_age_seconds=600)


def test_bale_init_data_rejects_tampering_duplicate_fields_and_malformed_encoding():
    raw = signed_init_data()
    with pytest.raises(ValueError, match="invalid_bale_init_data"):
        verify_bale_mini_app_init_data(raw.replace("test-query-001", "other"), BOT_TOKEN, now=NOW)
    with pytest.raises(ValueError, match="invalid_bale_init_data"):
        verify_bale_mini_app_init_data(raw + "&auth_date=" + str(NOW), BOT_TOKEN, now=NOW)
    with pytest.raises(ValueError, match="invalid_bale_init_data"):
        verify_bale_mini_app_init_data(raw + "%ZZ", BOT_TOKEN, now=NOW)


def test_login_issues_revocable_account_session_and_rejects_replay(auth_client):
    client, engine = auth_client
    raw = signed_init_data()
    response = client.post(
        "/api/auth/bale-mini-app",
        json={"init_data": raw},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["authenticated"] is True
    assert body["provider"] == "bale"
    assert "role" not in body
    assert client.cookies.get("nora_account_session")
    assert client.cookies.get("nora_account_csrf")

    session_cookie = next(c for c in client.cookies.jar if c.name == "nora_account_session")
    csrf_cookie = next(c for c in client.cookies.jar if c.name == "nora_account_csrf")
    assert session_cookie.has_nonstandard_attr("HttpOnly")
    assert session_cookie.get_nonstandard_attr("SameSite") == "strict"
    assert not csrf_cookie.has_nonstandard_attr("HttpOnly")

    account = client.get("/api/account/me")
    assert account.status_code == 200
    assert account.json() == {
        "authenticated": True,
        "account_id": body["account_id"],
        "provider": "bale",
        "role": None,
        "permissions": [],
        "delivery_bot_url": "",
    }
    assert client.get("/api/forms").status_code == 403

    replay = client.post(
        "/api/auth/bale-mini-app",
        json={"init_data": raw},
        headers={"Origin": "http://testserver"},
    )
    assert replay.status_code == 409
    assert replay.json()["detail"] == "bale_init_data_replayed"

    missing_csrf = client.post(
        "/api/auth/account/logout", headers={"Origin": "http://testserver"}
    )
    assert missing_csrf.status_code == 403
    logout = client.post(
        "/api/auth/account/logout",
        headers={
            "Origin": "http://testserver",
            "X-CSRF-Token": client.cookies.get("nora_account_csrf", ""),
        },
    )
    assert logout.status_code == 200
    assert client.get("/api/account/me").status_code == 401

    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(AccountRecord)) == 1
        assert db.scalar(select(func.count()).select_from(PlatformIdentityRecord)) == 1
        assert db.scalar(select(func.count()).select_from(AccountSessionRecord)) == 1
        assert db.scalar(select(func.count()).select_from(MiniAppAuthReplayRecord)) == 1
        session = db.scalar(select(AccountSessionRecord))
        assert session.revoked_at is not None


def test_bale_login_requires_origin_and_configured_server_token(auth_client):
    client, _ = auth_client
    raw = signed_init_data()
    assert client.post("/api/auth/bale-mini-app", json={"init_data": raw}).status_code == 403

    unconfigured = Settings(
        database_url=None,
        owner_id="",
        owner_username="",
        owner_password_hash="",
        cookie_secure=False,
    )
    unconfigured_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(unconfigured_engine)
    app = create_app(unconfigured, engine=unconfigured_engine)
    with TestClient(app) as unconfigured_client:
        response = unconfigured_client.post(
            "/api/auth/bale-mini-app",
            json={"init_data": raw},
            headers={"Origin": "http://testserver"},
        )
    unconfigured_engine.dispose()
    assert response.status_code == 503
    assert response.json()["detail"] == "bale_auth_not_configured"


def test_invalid_bale_init_data_is_rate_limited(auth_client):
    client, _ = auth_client
    for _ in range(5):
        response = client.post(
            "/api/auth/bale-mini-app",
            json={"init_data": "auth_date=1&user=%7B%7D&hash=" + "0" * 64},
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 401
    blocked = client.post(
        "/api/auth/bale-mini-app",
        json={"init_data": "auth_date=1&user=%7B%7D&hash=" + "0" * 64},
        headers={"Origin": "http://testserver"},
    )
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"]


def test_bale_auth_configuration_is_bounded_and_not_repr_exposed(monkeypatch):
    monkeypatch.setenv("NORA_BALE_BOT_TOKEN", "server-only-test-token")
    monkeypatch.setenv("NORA_BALE_BOT_USERNAME", "@nora_test_bot")
    monkeypatch.setenv("NORA_BALE_INIT_DATA_MAX_AGE_SECONDS", "900")
    monkeypatch.setenv("NORA_SESSION_TTL_SECONDS", "28800")
    configured = Settings.from_env()
    assert configured.bale_bot_token == "server-only-test-token"
    assert configured.bale_bot_username == "nora_test_bot"
    assert configured.bale_init_data_max_age_seconds == 900
    assert "server-only-test-token" not in repr(configured)

    monkeypatch.setenv("NORA_BALE_INIT_DATA_MAX_AGE_SECONDS", "59")
    with pytest.raises(ValueError, match="NORA_BALE_INIT_DATA_MAX_AGE_SECONDS"):
        Settings.from_env()
    monkeypatch.setenv("NORA_BALE_INIT_DATA_MAX_AGE_SECONDS", "3601")
    with pytest.raises(ValueError, match="NORA_BALE_INIT_DATA_MAX_AGE_SECONDS"):
        Settings.from_env()
    monkeypatch.setenv("NORA_BALE_INIT_DATA_MAX_AGE_SECONDS", "600")
    monkeypatch.setenv("NORA_BALE_BOT_USERNAME", "https://ble.ir/nora")
    with pytest.raises(ValueError, match="NORA_BALE_BOT_USERNAME"):
        Settings.from_env()
