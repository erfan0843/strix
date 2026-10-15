from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

UI_ROOT = Path(__file__).resolve().parents[2]
if str(UI_ROOT) not in sys.path:
    sys.path.insert(0, str(UI_ROOT))

import backend.app as app_module  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import (  # noqa: E402
    AccountRoleRecord,
    AccountSessionRecord,
    AccountRecord,
    Base,
    PhoneOTPChallengeRecord,
    PlatformIdentityRecord,
)
from backend.roles import ROLE_MANAGER, permissions_for_role  # noqa: E402
from backend.security import hash_password  # noqa: E402
from backend.otp import generate_otp_code, normalize_iran_phone, otp_digest, phone_digest, send_safir_otp  # noqa: E402


SAFIR_KEY = "server-only-safir-key-for-otp-tests"
BOT_ID = "100000001"
PHONE = "09123456789"
CODE = "042815"
ORIGIN = {"Origin": "http://testserver"}


def make_client(*, configured: bool = True, send_ok: bool = True, monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    calls: list[dict] = []

    def fake_send(**kwargs):
        calls.append(kwargs)
        return send_ok

    monkeypatch.setattr(app_module, "generate_otp_code", lambda: CODE)
    monkeypatch.setattr(app_module, "send_safir_otp", fake_send)
    settings = Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"),
        cookie_secure=False,
        safir_api_key=SAFIR_KEY if configured else "",
        safir_bot_id=BOT_ID if configured else "",
        otp_pepper=SAFIR_KEY if configured else "",
        otp_ttl_seconds=180,
        otp_max_attempts=5,
        otp_resend_seconds=90,
    )
    app = create_app(settings, engine=engine)
    client = TestClient(app)
    return client, engine, calls


def request_code(client: TestClient, phone: str = PHONE):
    return client.post("/api/auth/phone-otp/request", json={"phone": phone}, headers=ORIGIN)


def verify_code(client: TestClient, challenge_id: str, code: str = CODE, phone: str = PHONE):
    return client.post(
        "/api/auth/phone-otp/verify",
        json={"challenge_id": challenge_id, "phone": phone, "code": code},
        headers=ORIGIN,
    )


def test_phone_normalization_hashing_and_code_generation_are_bounded():
    assert normalize_iran_phone("۰۹۱۲ ۳۴۵ ۶۷۸۹") == PHONE
    assert normalize_iran_phone("+98 (912) 345-6789") == PHONE
    assert normalize_iran_phone("00989123456789") == PHONE
    assert normalize_iran_phone("0912345678") is None
    assert normalize_iran_phone("۰۹۱۲۳۴۵۶۷۸۹<script>") is None
    assert all(len(generate_otp_code()) == 6 and generate_otp_code().isdigit() for _ in range(25))
    assert phone_digest(SAFIR_KEY, PHONE) != PHONE
    assert otp_digest(SAFIR_KEY, "challenge", CODE) != CODE


def test_safir_sender_uses_only_approved_https_endpoint_and_existing_payload(monkeypatch):
    requests = []
    monkeypatch.setattr(
        "backend.otp._post_json",
        lambda url, key, payload: (requests.append((url, key, payload)) or (True, 200, {"message_id": "m1"})),
    )
    assert send_safir_otp(
        api_key=SAFIR_KEY,
        bot_id=BOT_ID,
        url="https://safir.bale.ai/api/v3/send_message",
        phone=PHONE,
        code=CODE,
    ) is True
    url, key, payload = requests[0]
    assert url == "https://safir.bale.ai/api/v3/send_message"
    assert key == SAFIR_KEY
    assert payload["phone_number"] == "989123456789"
    assert payload["message_data"] == {"otp_message": {"otp": CODE}}
    assert payload["bot_id"] == int(BOT_ID)
    assert "request_id" in payload

    requests.clear()
    assert send_safir_otp(
        api_key=SAFIR_KEY,
        bot_id=BOT_ID,
        url="https://attacker.example/send_message",
        phone=PHONE,
        code=CODE,
    ) is False
    assert not requests


def test_request_and_verify_issue_one_phone_account_session_without_assigning_a_role(monkeypatch):
    client, engine, sends = make_client(monkeypatch=monkeypatch)
    try:
        assert client.post("/api/auth/phone-otp/request", json={"phone": PHONE}).status_code == 403
        response = request_code(client, "۰۹۱۲۳۴۵۶۷۸۹")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["accepted"] is True
        assert body["expires_in"] == 180 and body["resend_in"] == 90
        challenge_id = body["challenge_id"]
        assert CODE not in response.text and PHONE not in response.text and SAFIR_KEY not in response.text
        assert len(sends) == 1
        assert sends[0]["api_key"] == SAFIR_KEY
        assert sends[0]["bot_id"] == BOT_ID
        assert sends[0]["phone"] == PHONE and sends[0]["code"] == CODE

        with Session(engine) as db:
            challenge = db.get(PhoneOTPChallengeRecord, challenge_id)
            assert challenge is not None
            assert challenge.phone_hash == phone_digest(SAFIR_KEY, PHONE)
            assert challenge.code_hash == otp_digest(SAFIR_KEY, challenge_id, CODE)
            assert challenge.phone_hash != PHONE and challenge.code_hash != CODE
            assert db.scalar(select(func.count()).select_from(AccountRecord)) == 0
            assert db.scalar(select(func.count()).select_from(AccountSessionRecord)) == 0

        wrong = verify_code(client, challenge_id, "111111")
        assert wrong.status_code == 401
        assert wrong.json()["detail"] == "invalid_or_expired_otp"
        with Session(engine) as db:
            challenge = db.get(PhoneOTPChallengeRecord, challenge_id)
            assert challenge.attempts == 1 and challenge.consumed_at is None
            assert db.scalar(select(func.count()).select_from(AccountSessionRecord)) == 0

        verified = verify_code(client, challenge_id)
        assert verified.status_code == 200, verified.text
        assert verified.json()["provider"] == "phone"
        assert "role" not in verified.json()
        assert client.cookies.get("nora_account_session")
        assert client.cookies.get("nora_account_csrf")
        identity = client.get("/api/account/me")
        assert identity.status_code == 200
        assert identity.json()["provider"] == "phone"
        assert identity.json()["role"] is None
        assert identity.json()["permissions"] == []
        assert client.get("/api/forms").status_code == 403

        replay = verify_code(client, challenge_id)
        assert replay.status_code == 401
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(AccountRecord)) == 1
            assert db.scalar(select(func.count()).select_from(PlatformIdentityRecord)) == 1
            identity = db.scalar(select(PlatformIdentityRecord))
            assert identity.provider == "phone"
            assert identity.provider_user_id == phone_digest(SAFIR_KEY, PHONE)
            assert PHONE not in identity.provider_user_id
            assert db.scalar(select(func.count()).select_from(AccountRoleRecord)) == 0
            assert db.scalar(select(func.count()).select_from(AccountSessionRecord)) == 1
    finally:
        client.close()
        engine.dispose()


def test_phone_account_role_is_only_granted_by_owner_and_phone_is_masked(monkeypatch):
    client, engine, _sends = make_client(monkeypatch=monkeypatch)
    try:
        challenge_id = request_code(client).json()["challenge_id"]
        assert verify_code(client, challenge_id).status_code == 200
        account_id = client.get("/api/account/me").json()["account_id"]
        assert client.get("/api/forms").status_code == 403

        owner = client.post(
            "/api/auth/login",
            json={"username": "nora-owner", "password": "correct-horse-staple-42"},
            headers=ORIGIN,
        )
        assert owner.status_code == 200
        listed = client.get("/api/owner/accounts")
        assert listed.status_code == 200
        phone_item = next(item for item in listed.json()["items"] if item["provider"] == "phone")
        assert phone_item["account_id"] == account_id
        assert phone_item["provider_user_id"] == "OTP-" + phone_digest(SAFIR_KEY, PHONE)[:8]
        assert PHONE not in listed.text

        assigned = client.put(
            f"/api/owner/accounts/{account_id}/role",
            json={"role": ROLE_MANAGER},
            headers={"Origin": "http://testserver", "X-CSRF-Token": client.cookies.get("nora_csrf", "")},
        )
        assert assigned.status_code == 200
        assert assigned.json()["role"] == ROLE_MANAGER
        assert set(assigned.json()["permissions"]) == set(permissions_for_role(ROLE_MANAGER))
        client.cookies.delete("nora_session")
        client.cookies.delete("nora_csrf")
        account = client.get("/api/account/me").json()
        assert account["provider"] == "phone"
        assert account["role"] == ROLE_MANAGER
        assert "fm_create" in account["permissions"]
        manager_api = client.get("/api/forms")
        assert manager_api.status_code == 403
        assert manager_api.json()["detail"] == "manager_password_required"

        logout = client.post(
            "/api/auth/account/logout",
            headers={"Origin": "http://testserver", "X-CSRF-Token": client.cookies.get("nora_account_csrf", "")},
        )
        assert logout.status_code == 200
        assert client.get("/api/account/me").status_code == 401
    finally:
        client.close()
        engine.dispose()


def test_expired_challenge_cannot_create_an_account_or_session(monkeypatch):
    clock = [datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)]
    monkeypatch.setattr(app_module, "_utc_now", lambda: clock[0])
    client, engine, _sends = make_client(monkeypatch=monkeypatch)
    try:
        challenge_id = request_code(client).json()["challenge_id"]
        clock[0] += timedelta(seconds=181)
        response = verify_code(client, challenge_id)
        assert response.status_code == 401
        with Session(engine) as db:
            challenge = db.get(PhoneOTPChallengeRecord, challenge_id)
            assert challenge.consumed_at is not None
            assert db.scalar(select(func.count()).select_from(AccountRecord)) == 0
            assert db.scalar(select(func.count()).select_from(AccountSessionRecord)) == 0
    finally:
        client.close()
        engine.dispose()


def test_otp_attempts_expire_and_delivery_failure_fail_closed(monkeypatch):
    client, engine, sends = make_client(monkeypatch=monkeypatch)
    try:
        challenge_id = request_code(client).json()["challenge_id"]
        for _ in range(5):
            response = verify_code(client, challenge_id, "999999")
            assert response.status_code == 401
        assert verify_code(client, challenge_id).status_code == 401
        with Session(engine) as db:
            challenge = db.get(PhoneOTPChallengeRecord, challenge_id)
            assert challenge.attempts == 5 and challenge.consumed_at is not None
            assert db.scalar(select(func.count()).select_from(AccountRecord)) == 0
    finally:
        client.close()
        engine.dispose()

    failed_client, failed_engine, _ = make_client(monkeypatch=monkeypatch, send_ok=False)
    try:
        failure = request_code(failed_client)
        assert failure.status_code == 503
        assert failure.json()["detail"] == "phone_otp_delivery_unavailable"
        assert CODE not in failure.text
        with Session(failed_engine) as db:
            challenge = db.scalar(select(PhoneOTPChallengeRecord))
            assert challenge is not None and challenge.consumed_at is not None
        challenge_id = challenge.id
        assert verify_code(failed_client, challenge_id).status_code == 401
    finally:
        failed_client.close()
        failed_engine.dispose()


def test_unconfigured_delivery_invalid_numbers_cooldown_and_origin_checks_fail_closed(monkeypatch):
    client, engine, sends = make_client(configured=False, monkeypatch=monkeypatch)
    try:
        assert request_code(client).status_code == 503
        assert sends == []
    finally:
        client.close()
        engine.dispose()

    client, engine, sends = make_client(monkeypatch=monkeypatch)
    try:
        invalid = request_code(client, "00000000000")
        assert invalid.status_code == 422
        assert invalid.json()["detail"] == "invalid_phone_number"
        first = request_code(client)
        assert first.status_code == 200
        limited = request_code(client)
        assert limited.status_code == 429
        assert limited.headers.get("Retry-After")
        assert len(sends) == 1
    finally:
        client.close()
        engine.dispose()


def test_settings_load_safir_and_bounded_otp_environment(monkeypatch):
    monkeypatch.setenv("SAFIR_API_KEY", SAFIR_KEY)
    monkeypatch.setenv("NORA_OTP_PEPPER", "stable-otp-pepper-for-tests-0123456789")
    monkeypatch.setenv("SAFIR_BOT_ID", BOT_ID)
    monkeypatch.setenv("SAFIR_URL", "https://safir.bale.ai/api/v3/send_message")
    monkeypatch.setenv("SAFIR_SEND_REQUEST_ID", "false")
    monkeypatch.setenv("OTP_TTL_MINUTES", "4")
    monkeypatch.setenv("OTP_MAX_ATTEMPTS", "6")
    monkeypatch.setenv("OTP_RESEND_SECONDS", "120")
    settings = Settings.from_env()
    assert settings.safir_api_key == SAFIR_KEY
    assert settings.otp_pepper == "stable-otp-pepper-for-tests-0123456789"
    assert settings.safir_bot_id == BOT_ID
    assert settings.safir_url == "https://safir.bale.ai/api/v3/send_message"
    assert settings.safir_send_request_id is False
    assert settings.otp_ttl_seconds == 240
    assert settings.otp_max_attempts == 6
    assert settings.otp_resend_seconds == 120
    assert SAFIR_KEY not in repr(settings)

    monkeypatch.setenv("SAFIR_URL", "https://attacker.example/steal")
    with pytest.raises(ValueError, match="SAFIR_URL"):
        Settings.from_env()
    monkeypatch.setenv("SAFIR_URL", "https://safir.bale.ai/api/v3/send_message")
    monkeypatch.setenv("OTP_TTL_MINUTES", "16")
    with pytest.raises(ValueError, match="OTP_TTL_MINUTES"):
        Settings.from_env()
