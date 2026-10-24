from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import AccountRoleRecord, Base  # noqa: E402
from backend.roles import (  # noqa: E402
    ROLE_CLUB_SUPERVISOR,
    ROLE_KEYS,
    ROLE_MANAGER,
    ROLE_OWNER,
    has_permission,
    permissions_for_role,
)
from backend.security import hash_password  # noqa: E402
from site_content_seed import seed_site_events  # noqa: E402

BOT_TOKEN = "test-only-bale-token"


def signed_init_data(user_id: int, *, query_id: str) -> str:
    now = int(time.time())
    fields = {
        "auth_date": str(now),
        "query_id": query_id,
        "user": json.dumps({"id": user_id, "first_name": "آزمایش"}, ensure_ascii=False, separators=(",", ":")),
    }
    check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode([*fields.items(), ("hash", signature)])


def auth_client(*, bot_service_token="", owner_bale_user_id=""):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    seed_site_events(engine, ["event-role-test"])
    settings = Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"),
        cookie_secure=False,
        bale_bot_token=BOT_TOKEN,
        bot_service_token=bot_service_token,
        owner_bale_user_id=owner_bale_user_id,
    )
    app = create_app(settings, engine=engine)
    return app, engine


def owner_login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "nora-owner", "password": "correct-horse-staple-42"},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["role"] == ROLE_OWNER


def bale_login(client: TestClient, user_id: int = 73421) -> str:
    response = client.post(
        "/api/auth/bale-mini-app",
        json={"init_data": signed_init_data(user_id, query_id=f"query-{user_id}")},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200, response.text
    return response.json()["account_id"]


def owner_write_headers(client: TestClient, *, csrf: bool = True) -> dict[str, str]:
    headers = {"Origin": "http://testserver"}
    if csrf:
        headers["X-CSRF-Token"] = client.cookies.get("nora_csrf", "")
    return headers


def test_role_matrix_has_only_three_roles_and_keeps_ambiguous_grants_unassigned():
    assert set(ROLE_KEYS) == {ROLE_OWNER, ROLE_MANAGER, ROLE_CLUB_SUPERVISOR}
    manager = permissions_for_role(ROLE_MANAGER)
    club = permissions_for_role(ROLE_CLUB_SUPERVISOR)
    owner = permissions_for_role(ROLE_OWNER)

    assert {"ev_create", "fm_create", "us_edit", "qa_report", "rp_export"} <= manager
    assert not {"cl_member", "cl_session", "cl_cert", "cl_content", "cl_dues", "sys_points"} & manager
    assert manager <= club
    assert {"cl_member", "cl_session", "cl_cert", "cl_content"} <= club
    assert not {"cl_dues", "sys_points"} & club
    assert {"finance", "role_assign", "sys_settings", "sys_backup", "cl_dues", "sys_points"} <= owner
    assert has_permission(ROLE_OWNER, "cl_dues")
    assert not has_permission(ROLE_MANAGER, "cl_dues")
    assert not has_permission(ROLE_CLUB_SUPERVISOR, "sys_points")
    assert permissions_for_role(None) == frozenset()
    assert permissions_for_role("unknown") == frozenset()


def test_role_assignment_is_owner_only_csrf_protected_and_shared_with_account_session():
    app, engine = auth_client()
    try:
        with TestClient(app) as client:
            account_id = bale_login(client)
            initial = client.get("/api/account/me")
            assert initial.status_code == 200
            assert initial.json()["role"] is None
            assert initial.json()["permissions"] == []
            assert client.get("/api/owner/accounts").status_code == 401

            owner_login(client)
            listing = client.get("/api/owner/accounts")
            assert listing.status_code == 200
            assert len(listing.json()["items"]) == 1
            listed = listing.json()["items"][0]
            assert listed["account_id"] == account_id
            assert listed["provider"] == "bale"
            assert listed["provider_user_id"] == "73421"
            assert listed["role"] is None and listed["permissions"] == []
            assert listed["created_at"]
            assert listing.json()["has_more"] is False

            path = f"/api/owner/accounts/{account_id}/role"
            missing_csrf = client.put(path, json={"role": ROLE_MANAGER}, headers=owner_write_headers(client, csrf=False))
            assert missing_csrf.status_code == 403
            cross_origin = client.put(
                path,
                json={"role": ROLE_MANAGER},
                headers={"Origin": "https://attacker.example", "X-CSRF-Token": client.cookies.get("nora_csrf", "")},
            )
            assert cross_origin.status_code == 403

            assigned = client.put(path, json={"role": ROLE_MANAGER}, headers=owner_write_headers(client))
            assert assigned.status_code == 200
            assert assigned.json()["role"] == ROLE_MANAGER
            assert "fm_create" in assigned.json()["permissions"]
            assert "cl_member" not in assigned.json()["permissions"]

            account = client.get("/api/account/me").json()
            assert account["role"] == ROLE_MANAGER
            assert set(account["permissions"]) == set(permissions_for_role(ROLE_MANAGER))

            club = client.put(path, json={"role": ROLE_CLUB_SUPERVISOR}, headers=owner_write_headers(client))
            assert club.status_code == 200
            account = client.get("/api/account/me").json()
            assert account["role"] == ROLE_CLUB_SUPERVISOR
            assert "cl_content" in account["permissions"]
            assert "cl_dues" not in account["permissions"]
            assert "sys_points" not in account["permissions"]

            invalid_owner = client.put(path, json={"role": ROLE_OWNER}, headers=owner_write_headers(client))
            assert invalid_owner.status_code == 422
            invalid_payload = client.put(path, json={"role": ROLE_MANAGER, "owner_id": "attacker"}, headers=owner_write_headers(client))
            assert invalid_payload.status_code == 400

            removed = client.put(path, json={"role": None}, headers=owner_write_headers(client))
            assert removed.status_code == 200
            assert removed.json()["role"] is None
            assert client.get("/api/account/me").json()["permissions"] == []
            with Session(engine) as db:
                assert db.scalar(select(AccountRoleRecord)) is None
    finally:
        engine.dispose()


def valid_role_form() -> dict:
    return {
        "name": "فرم آزمون نقش",
        "model": "registration",
        "need": "reg",
        "slug": "role-tests/manager-form",
        "ev": "event-role-test",
        "settings": {"description": "آزمون مجوز سروری"},
        "fields": [{"id": "full-name", "t": "text", "l": "نام کامل", "required": True}],
    }


def test_server_permission_gates_manager_form_access_and_keeps_publish_owner_only():
    app, engine = auth_client()
    try:
        with TestClient(app) as client:
            account_id = bale_login(client)
            assert client.get("/api/forms").status_code == 403
            owner_login(client)
            assigned = client.put(
                f"/api/owner/accounts/{account_id}/role",
                json={"role": ROLE_MANAGER},
                headers=owner_write_headers(client),
            )
            assert assigned.status_code == 200

            client.cookies.delete("nora_session")
            client.cookies.delete("nora_csrf")
            assert client.get("/api/owner/accounts").status_code == 401
            assert client.get("/api/forms").status_code == 403

            owner_login(client)
            manager_password = "role-test-manager-password-2026"
            provisioned = client.put(
                f"/api/owner/accounts/{account_id}/manager-credentials",
                json={"username": "role.manager", "password": manager_password},
                headers=owner_write_headers(client),
            )
            assert provisioned.status_code == 200, provisioned.text
            client.cookies.delete("nora_session")
            client.cookies.delete("nora_csrf")
            manager_login = client.post(
                "/api/auth/manager-login",
                json={"username": "role.manager", "password": manager_password},
                headers={"Origin": "http://testserver"},
            )
            assert manager_login.status_code == 200, manager_login.text
            assert client.get("/api/account/me").json()["provider"] == "manager-password"
            forms = client.get("/api/forms")
            assert forms.status_code == 200
            assert forms.json()["items"] == []
            assert forms.json()["total"] == 0
            assert forms.json()["limit"] == 100
            assert forms.json()["has_more"] is False
            form_path = "/api/forms"
            write_headers = {
                "Origin": "http://testserver",
                "X-CSRF-Token": client.cookies.get("nora_account_csrf", ""),
                "Idempotency-Key": "role-create-key-0001",
            }
            no_csrf = client.post(form_path, json=valid_role_form(), headers={"Origin": "http://testserver", "Idempotency-Key": "role-create-key-0002"})
            assert no_csrf.status_code == 403
            created = client.post(form_path, json=valid_role_form(), headers=write_headers)
            assert created.status_code == 201, created.text
            form_id = created.json()["id"]
            assert client.get(f"/api/forms/{form_id}").status_code == 200
            assert client.get(f"/api/forms/{form_id}/responses").json()["total"] == 0

            updated_payload = valid_role_form()
            updated_payload["name"] = "فرم به‌روزشدهٔ مدیر"
            updated_payload["expected_version"] = 1
            updated = client.put(
                f"/api/forms/{form_id}",
                json=updated_payload,
                headers={"Origin": "http://testserver", "X-CSRF-Token": client.cookies.get("nora_account_csrf", "")},
            )
            assert updated.status_code == 200, updated.text
            assert updated.json()["version"] == 2

            publish = client.post(
                f"/api/forms/{form_id}/publish",
                json={"expected_version": 2},
                headers={"Origin": "http://testserver", "X-CSRF-Token": client.cookies.get("nora_account_csrf", "")},
            )
            assert publish.status_code == 401
    finally:
        engine.dispose()


def test_bale_account_cannot_list_or_change_roles_even_with_its_own_csrf():
    app, engine = auth_client()
    try:
        with TestClient(app) as client:
            account_id = bale_login(client)
            path = f"/api/owner/accounts/{account_id}/role"
            headers = {
                "Origin": "http://testserver",
                "X-CSRF-Token": client.cookies.get("nora_account_csrf", ""),
            }
            assert client.get("/api/owner/accounts").status_code == 401
            denied = client.put(path, json={"role": ROLE_MANAGER}, headers=headers)
            assert denied.status_code == 401
            assert client.get("/api/account/me").json()["role"] is None
    finally:
        engine.dispose()


def test_bot_identity_requires_service_token_and_resolves_server_roles():
    service_token = "bot-service-test-credential-0123456789abcdef"
    app, engine = auth_client(bot_service_token=service_token, owner_bale_user_id="900001")
    try:
        with TestClient(app) as client:
            account_id = bale_login(client, user_id=73421)
            owner_login(client)
            path = f"/api/owner/accounts/{account_id}/role"
            assigned = client.put(
                path,
                json={"role": ROLE_MANAGER},
                headers=owner_write_headers(client),
            )
            assert assigned.status_code == 200

            endpoint = "/api/bot/identity"
            assert client.post(endpoint, json={"bale_user_id": "73421"}).status_code == 401
            assert client.post(
                endpoint,
                json={"bale_user_id": "73421"},
                headers={"Authorization": "Bearer wrong-service-token"},
            ).status_code == 401

            headers = {"Authorization": f"Bearer {service_token}"}
            manager = client.post(endpoint, json={"bale_user_id": 73421}, headers=headers)
            assert manager.status_code == 200, manager.text
            assert manager.json()["account_id"] == account_id
            assert manager.json()["role"] == ROLE_MANAGER
            assert set(manager.json()["permissions"]) == set(permissions_for_role(ROLE_MANAGER))
            assert "cl_content" not in manager.json()["permissions"]
            assert "cl_dues" not in manager.json()["permissions"]
            assert "sys_points" not in manager.json()["permissions"]

            assigned = client.put(
                path,
                json={"role": ROLE_CLUB_SUPERVISOR},
                headers=owner_write_headers(client),
            )
            assert assigned.status_code == 200
            club = client.post(endpoint, json={"bale_user_id": "73421"}, headers=headers)
            assert club.status_code == 200
            assert club.json()["role"] == ROLE_CLUB_SUPERVISOR
            assert "cl_content" in club.json()["permissions"]
            assert "cl_dues" not in club.json()["permissions"]
            assert "sys_points" not in club.json()["permissions"]

            owner = client.post(endpoint, json={"bale_user_id": "900001"}, headers=headers)
            assert owner.status_code == 200
            assert owner.json()["account_id"] is None
            assert owner.json()["role"] == ROLE_OWNER
            assert set(owner.json()["permissions"]) == set(permissions_for_role(ROLE_OWNER))

            unassigned = client.post(endpoint, json={"bale_user_id": "900002"}, headers=headers)
            assert unassigned.status_code == 200
            assert unassigned.json()["role"] is None
            assert unassigned.json()["permissions"] == []
            assert client.post(endpoint, json={"bale_user_id": True}, headers=headers).status_code == 422
            assert client.post(endpoint, json={"bale_user_id": "0"}, headers=headers).status_code == 422
            assert client.post(endpoint, json={"bale_user_id": "73421", "role": ROLE_OWNER}, headers=headers).status_code == 400
    finally:
        engine.dispose()


def test_bot_identity_is_disabled_without_service_secret():
    app, engine = auth_client()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/bot/identity",
                json={"bale_user_id": "73421"},
                headers={"Authorization": "Bearer unused"},
            )
            assert response.status_code == 503
            assert response.json()["detail"] == "bot_api_not_configured"
    finally:
        engine.dispose()
