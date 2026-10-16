from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import Base  # noqa: E402
from backend.security import hash_password  # noqa: E402


def _client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None,
        owner_id="owner-referer",
        owner_username="owner",
        owner_password_hash=hash_password("referer-test-password"),
        cookie_secure=False,
    )
    return TestClient(create_app(settings, engine=engine))


BODY = {"phone": "09123456789", "captcha_token": "x", "captcha_answer": "1234"}


def test_same_origin_referer_is_accepted_when_origin_is_absent():
    client = _client()
    # بدون Origin و با Referer هم‌مبدأ از بررسی same-origin عبور می‌کند.
    # (پیکربندی OTP نشده، پس پاسخ 503 با کد دقیق است، نه 403.)
    response = client.post(
        "/api/auth/phone-otp/request", json=BODY,
        headers={"Host": "nora.test", "Referer": "https://nora.test/login.html"},
    )
    assert response.status_code == 503, response.text
    assert response.json()["detail"] == "phone_otp_not_configured"


def test_cross_origin_referer_is_rejected_when_origin_is_absent():
    client = _client()
    response = client.post(
        "/api/auth/phone-otp/request", json=BODY,
        headers={"Host": "nora.test", "Referer": "https://evil.example/page"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "same_origin_required"


def test_missing_origin_and_referer_is_rejected():
    client = _client()
    response = client.post("/api/auth/phone-otp/request", json=BODY, headers={"Host": "nora.test"})
    assert response.status_code == 403
    assert response.json()["detail"] == "same_origin_required"
