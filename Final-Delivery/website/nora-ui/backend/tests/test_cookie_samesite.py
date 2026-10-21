"""SameSite کوکی‌های نشست: پیش‌فرض strict؛ «none» فقط با کوکی امن و فقط از تنظیم صریح (برای پیش‌نمایش داخل iframe)."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app import create_app  # noqa: E402
from backend.config import Settings, _cookie_samesite_env  # noqa: E402
from backend.models import Base  # noqa: E402
from backend.security import hash_password  # noqa: E402

PASSWORD = "owner-pass-for-samesite-2026"


def _client(**overrides):
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    kwargs = dict(database_url=None, owner_id="owner-01", owner_username="nora-owner",
                  owner_password_hash=hash_password(PASSWORD), cookie_secure=False)
    kwargs.update(overrides)
    settings = Settings(**kwargs)
    return TestClient(create_app(settings, engine=engine))


def _login_set_cookie(client: TestClient) -> str:
    response = client.post("/api/auth/staff-login", json={"username": "nora-owner", "password": PASSWORD},
                           headers={"Origin": "http://testserver"})
    assert response.status_code == 200, response.text
    return " | ".join(response.headers.get_list("set-cookie")).lower()


def test_default_is_strict():
    header = _login_set_cookie(_client())
    assert "samesite=strict" in header and "samesite=none" not in header


def test_none_requires_secure_cookie():
    header = _login_set_cookie(_client(cookie_samesite="none"))  # cookie_secure=False → strict می‌ماند
    assert "samesite=strict" in header and "samesite=none" not in header


def test_none_with_secure_cookie_is_honoured():
    header = _login_set_cookie(_client(cookie_samesite="none", cookie_secure=True))
    assert "samesite=none" in header and "; secure" in header


def test_env_parser_is_fail_safe(monkeypatch):
    monkeypatch.delenv("NORA_COOKIE_SAMESITE", raising=False)
    assert _cookie_samesite_env(True) == "strict"
    monkeypatch.setenv("NORA_COOKIE_SAMESITE", "weird")
    assert _cookie_samesite_env(True) == "strict"
    monkeypatch.setenv("NORA_COOKIE_SAMESITE", "none")
    assert _cookie_samesite_env(False) == "strict"
    assert _cookie_samesite_env(True) == "none"
    monkeypatch.setenv("NORA_COOKIE_SAMESITE", "Lax")
    assert _cookie_samesite_env(True) == "lax"
