"""پیوند امن هویت بله به حساب شماره‌ای، بدون ادغام خودکار و بدون از دست رفتن سابقه.

این آزمون‌ها همان چیزی را می‌سنجند که برای «یک حساب، چند هویت» لازم است:
مالکیت هر دو طرف اثبات شود، شناسهٔ سمت کلاینت معتبر نباشد، پیوند متعارض رد شود،
و سوابق کاربر پس از پیوند دست‌نخورده بمانند.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
import uuid
from dataclasses import replace as dataclass_replace
from datetime import datetime, timedelta, timezone
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
    AccountProfileRecord,
    AccountRecord,
    AccountRoleRecord,
    AccountSessionRecord,
    Base,
    MiniAppAuthReplayRecord,
    PlatformIdentityRecord,
)
from backend.security import token_digest  # noqa: E402

BOT_TOKEN = "test-only-bale-token"
BALE_USER_ID = 73421
PHONE_PROVIDER = "phone"
PHONE_SUBJECT = "a" * 64
SESSION_TOKEN = "s" * 64
CSRF_TOKEN = "c" * 64


def signed_init_data(
    *,
    user_id: int = BALE_USER_ID,
    auth_date: int | None = None,
    query_id: str = "link-query-001",
    token: str = BOT_TOKEN,
) -> str:
    fields = {
        "auth_date": str(int(time.time()) if auth_date is None else auth_date),
        "query_id": query_id,
        "user": json.dumps(
            {"id": user_id, "first_name": "آزمایش", "username": "nora_test"},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    fields["hash"] = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return urlencode(list(fields.items()))


def make_client(engine) -> TestClient:
    settings = Settings(
        database_url=None,
        owner_id="owner-1",
        owner_username="",
        owner_password_hash="",
        cookie_secure=False,
        bale_bot_token=BOT_TOKEN,
        bale_init_data_max_age_seconds=600,
    )
    return TestClient(create_app(settings, engine=engine))


def seed_phone_account(
    engine,
    *,
    account_id: str = "acct-phone",
    profile: dict | None = None,
) -> str:
    """یک حساب تأییدشده با شماره و یک نشست فعال می‌سازد (همان کاری که OTP می‌کند)."""
    with Session(engine) as db:
        db.add(AccountRecord(id=account_id))
        db.add(
            PlatformIdentityRecord(
                id=str(uuid.uuid4()),
                account_id=account_id,
                provider=PHONE_PROVIDER,
                provider_user_id=PHONE_SUBJECT,
            )
        )
        db.add(
            AccountSessionRecord(
                id=str(uuid.uuid4()),
                account_id=account_id,
                auth_provider=PHONE_PROVIDER,
                token_hash=token_digest(SESSION_TOKEN),
                csrf_hash=token_digest(CSRF_TOKEN),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
            )
        )
        if profile is not None:
            db.add(AccountProfileRecord(account_id=account_id, fields=profile))
        db.commit()
    return account_id


@pytest.fixture
def link_env():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    client = make_client(engine)
    with client:
        client.cookies.set("nora_account_session", SESSION_TOKEN)
        client.cookies.set("nora_account_csrf", CSRF_TOKEN)
        yield client, engine
    engine.dispose()


def link(client: TestClient, init_data: str, **kwargs):
    headers = {"Origin": "http://testserver", "X-CSRF-Token": CSRF_TOKEN}
    headers.update(kwargs.pop("headers", {}))
    return client.post(
        "/api/account/identities/bale", json={"init_data": init_data}, headers=headers, **kwargs
    )


def identities_of(engine, account_id: str) -> set[str]:
    with Session(engine) as db:
        return {
            row.provider
            for row in db.scalars(
                select(PlatformIdentityRecord).where(
                    PlatformIdentityRecord.account_id == account_id
                )
            )
        }


def test_verified_bale_identity_extends_the_same_phone_account(link_env):
    client, engine = link_env
    account_id = seed_phone_account(engine, profile={"fullName": "کاربر آزمایشی"})

    response = link(client, signed_init_data())
    assert response.status_code == 200, response.text
    assert response.json() == {"linked": True, "provider": "bale", "already_linked": False}

    # همان حساب، حالا دو هویت دارد؛ حساب تازه‌ای ساخته نشده است.
    assert identities_of(engine, account_id) == {PHONE_PROVIDER, "bale"}
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(AccountRecord)) == 1
        bale = db.scalar(
            select(PlatformIdentityRecord).where(PlatformIdentityRecord.provider == "bale")
        )
        assert bale.account_id == account_id
        assert bale.provider_user_id == str(BALE_USER_ID)

    # سابقهٔ کاربر پس از پیوند سرِ جایش است.
    profile = client.get("/api/account/profile")
    assert profile.status_code == 200
    assert profile.json()["fields"]["fullName"] == "کاربر آزمایشی"


def test_linking_is_idempotent_for_the_same_identity(link_env):
    client, engine = link_env
    account_id = seed_phone_account(engine)
    assert link(client, signed_init_data()).status_code == 200

    # initData تازه (اثر انگشت تازه) برای همان کاربر بله.
    again = link(client, signed_init_data(query_id="link-query-002"))
    assert again.status_code == 200, again.text
    assert again.json()["already_linked"] is True
    assert identities_of(engine, account_id) == {PHONE_PROVIDER, "bale"}


def test_tampered_expired_and_unsigned_init_data_never_link(link_env):
    client, engine = link_env
    account_id = seed_phone_account(engine)
    good = signed_init_data()

    tampered = good.replace("link-query-001", "other-query")
    assert link(client, tampered).status_code == 401
    assert link(client, signed_init_data(auth_date=int(time.time()) - 3600)).status_code == 401
    assert link(client, "auth_date=1&user=%7B%7D&hash=" + "0" * 64).status_code == 401
    assert link(client, signed_init_data(user_id=0)).status_code == 401
    # initData امضاشده با توکن دیگری نباید معتبر باشد.
    assert link(client, signed_init_data(token="attacker-token")).status_code == 401

    assert identities_of(engine, account_id) == {PHONE_PROVIDER}


def test_client_cannot_dictate_which_identity_gets_linked(link_env):
    """شناسهٔ کاربر بله فقط از داخل initData تأییدشده خوانده می‌شود."""
    client, engine = link_env
    account_id = seed_phone_account(engine)

    smuggled = client.post(
        "/api/account/identities/bale",
        json={"init_data": signed_init_data(), "user_id": 999999, "account_id": "other"},
        headers={"Origin": "http://testserver", "X-CSRF-Token": CSRF_TOKEN},
    )
    assert smuggled.status_code == 400
    assert smuggled.json()["detail"] == "invalid_bale_auth_payload"
    assert identities_of(engine, account_id) == {PHONE_PROVIDER}

    # با دادهٔ امضاشدهٔ معتبر، همان شناسهٔ *داخل امضا* پیوند می‌شود، نه چیز دیگری.
    assert link(client, signed_init_data(user_id=880011)).status_code == 200
    with Session(engine) as db:
        bale = db.scalar(
            select(PlatformIdentityRecord).where(PlatformIdentityRecord.provider == "bale")
        )
        assert bale.provider_user_id == "880011"


def test_conflicting_link_is_refused_and_nothing_is_merged(link_env):
    """هویت بلهٔ متعلق به حساب دیگر نباید خودکار ادغام شود."""
    client, engine = link_env
    phone_account = seed_phone_account(engine)
    with Session(engine) as db:
        db.add(AccountRecord(id="acct-bale-owner"))
        db.add(
            PlatformIdentityRecord(
                id=str(uuid.uuid4()),
                account_id="acct-bale-owner",
                provider="bale",
                provider_user_id=str(BALE_USER_ID),
            )
        )
        db.commit()

    response = link(client, signed_init_data(query_id="conflict-query"))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "bale_identity_already_linked"

    # هیچ‌چیز جابه‌جا نشده است.
    assert identities_of(engine, phone_account) == {PHONE_PROVIDER}
    assert identities_of(engine, "acct-bale-owner") == {"bale"}


def test_linking_requires_same_origin_csrf_and_a_session(link_env):
    client, engine = link_env
    account_id = seed_phone_account(engine)
    raw = signed_init_data()

    no_origin = client.post(
        "/api/account/identities/bale",
        json={"init_data": raw},
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert no_origin.status_code == 403

    no_csrf = client.post(
        "/api/account/identities/bale",
        json={"init_data": raw},
        headers={"Origin": "http://testserver"},
    )
    assert no_csrf.status_code == 403
    assert no_csrf.json()["detail"] == "csrf_check_failed"

    client.cookies.clear()
    anonymous = link(client, raw)
    assert anonymous.status_code == 401
    assert anonymous.json()["detail"] == "authentication_required"
    assert identities_of(engine, account_id) == {PHONE_PROVIDER}


def test_replaying_init_data_grants_nothing_new(link_env):
    """تکرار `initData` برای هویتی که همین حالا به همین حساب وصل است، بی‌اثر است.

    این حالت عمداً idempotent است (پاسخ گم‌شده/دوبار کلیک کاربر)، ولی هیچ
    هویت تازه، حساب تازه یا مصرف دوبارهٔ اثر انگشت تولید نمی‌کند. حالت خطرناک
    (هویتِ متعلق به حساب دیگر) همیشه ۴۰۹ می‌گیرد و در آزمون جدا سنجیده شده است.
    """
    client, engine = link_env
    account_id = seed_phone_account(engine)
    raw = signed_init_data()
    assert link(client, raw).status_code == 200

    client.cookies.set("nora_account_session", SESSION_TOKEN)
    client.cookies.set("nora_account_csrf", CSRF_TOKEN)
    again = link(client, raw)
    assert again.status_code == 200
    assert again.json()["already_linked"] is True

    assert identities_of(engine, account_id) == {PHONE_PROVIDER, "bale"}
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(AccountRecord)) == 1
        assert db.scalar(select(func.count()).select_from(PlatformIdentityRecord)) == 2
        # اثر انگشت دوباره مصرف نمی‌شود، پس ردیف تازه‌ای اضافه نمی‌شود.
        assert db.scalar(select(func.count()).select_from(MiniAppAuthReplayRecord)) == 1


def test_linking_never_grants_a_server_role(link_env):
    """نقش از پایگاه‌داده می‌آید؛ پیوند هویت نقشی نمی‌سازد."""
    client, engine = link_env
    account_id = seed_phone_account(engine)
    assert link(client, signed_init_data()).status_code == 200

    me = client.get("/api/account/me")
    assert me.status_code == 200
    assert me.json()["role"] is None
    assert me.json()["permissions"] == []
    assert client.get("/api/forms").status_code == 403
    with Session(engine) as db:
        assert db.get(AccountRoleRecord, account_id) is None


def test_identity_list_exposes_no_raw_identifiers(link_env):
    client, engine = link_env
    account_id = seed_phone_account(engine)
    assert link(client, signed_init_data()).status_code == 200

    listed = client.get("/api/account/identities")
    assert listed.status_code == 200
    body = listed.json()
    assert body["account_id"] == account_id
    assert {item["provider"] for item in body["identities"]} == {PHONE_PROVIDER, "bale"}
    assert body["bale_link_available"] is True
    serialized = json.dumps(body, ensure_ascii=False)
    assert str(BALE_USER_ID) not in serialized
    assert PHONE_SUBJECT not in serialized
    # میان‌افزار، همهٔ مسیرهای /api/ را no-store می‌کند؛ پاسخِ هویت هم نباید کش شود.
    assert "no-store" in listed.headers["cache-control"]


def test_unlinking_keeps_the_other_identity_and_the_records(link_env):
    client, engine = link_env
    account_id = seed_phone_account(engine, profile={"fullName": "بمان"})
    assert link(client, signed_init_data()).status_code == 200

    removed = client.delete(
        "/api/account/identities/bale",
        headers={"Origin": "http://testserver", "X-CSRF-Token": CSRF_TOKEN},
    )
    assert removed.status_code == 200, removed.text
    assert removed.json() == {"linked": False, "provider": "bale"}
    assert identities_of(engine, account_id) == {PHONE_PROVIDER}

    # حساب و سابقه‌اش باقی می‌مانند و نشست جاری باطل نمی‌شود.
    assert client.get("/api/account/me").status_code == 200
    assert client.get("/api/account/profile").json()["fields"]["fullName"] == "بمان"

    # نشست‌های بلهِ همان حساب دیگر زنده نیستند.
    with Session(engine) as db:
        live = db.scalars(
            select(AccountSessionRecord).where(
                AccountSessionRecord.account_id == account_id,
                AccountSessionRecord.revoked_at.is_(None),
            )
        ).all()
        assert [row.auth_provider for row in live] == [PHONE_PROVIDER]


def test_last_identity_cannot_be_removed(link_env):
    """حسابی که فقط با بله ساخته شده نباید بی‌هویت شود."""
    client, engine = link_env
    with Session(engine) as db:
        db.add(AccountRecord(id="acct-bale-only"))
        db.add(
            PlatformIdentityRecord(
                id=str(uuid.uuid4()),
                account_id="acct-bale-only",
                provider="bale",
                provider_user_id=str(BALE_USER_ID),
            )
        )
        db.add(
            AccountSessionRecord(
                id=str(uuid.uuid4()),
                account_id="acct-bale-only",
                auth_provider="bale",
                token_hash=token_digest(SESSION_TOKEN),
                csrf_hash=token_digest(CSRF_TOKEN),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
            )
        )
        db.commit()

    refused = client.delete(
        "/api/account/identities/bale",
        headers={"Origin": "http://testserver", "X-CSRF-Token": CSRF_TOKEN},
    )
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "last_identity_cannot_be_removed"
    assert identities_of(engine, "acct-bale-only") == {"bale"}


def test_unlinking_something_never_linked_is_a_clean_404(link_env):
    client, engine = link_env
    seed_phone_account(engine)
    response = client.delete(
        "/api/account/identities/bale",
        headers={"Origin": "http://testserver", "X-CSRF-Token": CSRF_TOKEN},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "bale_identity_not_linked"


def test_linking_is_closed_without_the_server_only_bot_token():
    """بدون `NORA_BALE_BOT_TOKEN` روی سرور، امکان اثبات مالکیت وجود ندارد پس پیوند بسته است."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    seed_phone_account(engine)
    client = make_client(engine)
    client.app.state.settings = dataclass_replace(  # type: ignore[attr-defined]
        client.app.state.settings, bale_bot_token=""
    )
    with client:
        client.cookies.set("nora_account_session", SESSION_TOKEN)
        client.cookies.set("nora_account_csrf", CSRF_TOKEN)
        listed = client.get("/api/account/identities")
        assert listed.json()["bale_link_available"] is False

        response = link(client, signed_init_data())
        assert response.status_code == 503
        assert response.json()["detail"] == "bale_auth_not_configured"
    engine.dispose()
