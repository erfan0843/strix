"""بازیابی پنل (مرحلهٔ C-1): تنظیمات مالی فرم فقط با مجوز ``finance`` (مالک) نوشته می‌شود.

پنهان‌کردن کارت‌های مالی در create.html کنترل دسترسی نیست؛ سرور تغییر کلیدهای تجاری
(``fin``/``groups``/``coupon``/``methods``/``enabledPaymentMethods``/``receiptReviewRequired``)
را از ویرایشگر بدون مجوز مالی با ``finance_permission_required`` رد می‌کند و نسخهٔ بدون تغییر را می‌پذیرد.
"""
from __future__ import annotations

import copy
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import AccountRecord, AccountRoleRecord, AccountSessionRecord, Base  # noqa: E402
from backend.security import hash_password, token_digest  # noqa: E402

ORIGIN = {"Origin": "http://testserver"}
MANAGER = "acct-finance-manager"


@pytest.fixture
def client():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None, owner_id="owner-01", owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"), session_ttl_seconds=3600, cookie_secure=False,
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


def owner_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": "nora-owner", "password": "correct-horse-staple-42"}, headers=ORIGIN)
    assert response.status_code == 200, response.text
    return {**ORIGIN, "X-CSRF-Token": client.cookies.get("nora_csrf", "")}


def manager_headers(client: TestClient) -> dict[str, str]:
    client.cookies.clear()
    with client.app.state.session_factory() as db:
        if db.get(AccountRecord, MANAGER) is None:
            db.add(AccountRecord(id=MANAGER))
            db.add(AccountRoleRecord(account_id=MANAGER, role="manager", assigned_by="owner-01"))
            db.add(AccountSessionRecord(
                id=str(uuid.uuid4()), account_id=MANAGER, auth_provider="manager-password",
                token_hash=token_digest("sess-" + MANAGER), csrf_hash=token_digest("csrf-" + MANAGER),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            ))
            db.commit()
    settings = client.app.state.settings
    client.cookies.set(settings.account_cookie_name, "sess-" + MANAGER, path="/")
    client.cookies.set(settings.account_csrf_cookie_name, "csrf-" + MANAGER, path="/")
    return {**ORIGIN, "X-CSRF-Token": "csrf-" + MANAGER}


def paid_form(name: str = "کارگاه پولی") -> dict:
    return {
        "name": name, "model": "registration", "need": "reg", "slug": "", "ev": "",
        "settings": {
            "description": "فرم آزمایشی",
            "fin": [{"l": "بلیت عادی", "p": 250000, "off": 0, "req": True}],
            "groups": [], "coupon": {"code": "", "off": 0, "all": False}, "methods": [],
            "enabledPaymentMethods": [],
        },
        "fields": [{"id": "full-name", "t": "text", "l": "نام کامل", "required": True}],
    }


def test_manager_cannot_create_or_change_money_settings_but_owner_can(client):
    headers = manager_headers(client)
    denied = client.post("/api/forms", json=paid_form(), headers={**headers, "Idempotency-Key": "fin-mgr-create-01"})
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"]["code"] == "finance_permission_required"

    free = paid_form("فرم رایگان مدیر")
    free["settings"]["fin"] = []
    allowed = client.post("/api/forms", json=free, headers={**headers, "Idempotency-Key": "fin-mgr-create-02"})
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["settings"]["fin"] == []

    client.cookies.clear()
    headers = owner_headers(client)
    created = client.post("/api/forms", json=paid_form(), headers={**headers, "Idempotency-Key": "fin-owner-create-01"})
    assert created.status_code == 201, created.text
    form_id, version = created.json()["id"], created.json()["version"]
    assert created.json()["settings"]["fin"][0]["p"] == 250000

    # Manager edits the title and sends the stored money settings unchanged (what create.html does) -> accepted.
    headers = manager_headers(client)
    same_money = copy.deepcopy(paid_form("کارگاه پولی · عنوان تازه"))
    same_money["expected_version"] = version
    renamed = client.put(f"/api/forms/{form_id}", json=same_money, headers=headers)
    assert renamed.status_code == 200, renamed.text
    version = renamed.json()["version"]
    assert renamed.json()["settings"]["fin"][0]["p"] == 250000

    # Manager tries to change the price / add a coupon / enable card transfer -> refused, record unchanged.
    for mutate in (
        lambda s: s["fin"].__setitem__(0, {**s["fin"][0], "p": 1}),
        lambda s: s.__setitem__("coupon", {"code": "FREE100", "off": 100, "all": True}),
        lambda s: s.__setitem__("enabledPaymentMethods", ["card_transfer"]),
        lambda s: s.__setitem__("fin", []),
    ):
        attempt = copy.deepcopy(paid_form("کارگاه پولی · عنوان تازه"))
        mutate(attempt["settings"])
        attempt["expected_version"] = version
        refused = client.put(f"/api/forms/{form_id}", json=attempt, headers=headers)
        assert refused.status_code == 403, refused.text
        assert refused.json()["detail"]["code"] == "finance_permission_required"
    current = client.get(f"/api/forms/{form_id}")
    assert current.status_code == 200
    assert current.json()["version"] == version and current.json()["settings"]["fin"][0]["p"] == 250000

    # Owner (finance) changes the price.
    client.cookies.clear()
    headers = owner_headers(client)
    priced = copy.deepcopy(paid_form("کارگاه پولی · عنوان تازه"))
    priced["settings"]["fin"][0]["p"] = 300000
    priced["expected_version"] = version
    updated = client.put(f"/api/forms/{form_id}", json=priced, headers=headers)
    assert updated.status_code == 200, updated.text
    assert updated.json()["settings"]["fin"][0]["p"] == 300000
