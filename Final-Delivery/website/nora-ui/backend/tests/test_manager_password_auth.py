from __future__ import annotations

import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import (  # noqa: E402
    AccountRecord,
    AccountRoleRecord,
    AccountSessionRecord,
    Base,
    ManagerCredentialRecord,
    PlatformIdentityRecord,
)
from backend.roles import ROLE_CLUB_SUPERVISOR, ROLE_MANAGER, permissions_for_role  # noqa: E402
from backend.security import hash_password, verify_password  # noqa: E402

ORIGIN = {"Origin": "http://testserver"}
OWNER_PASSWORD = "test-owner-password-2026"
MANAGER_PASSWORD = "test-manager-password-2026"


def make_client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username="nora-owner",
        owner_password_hash=hash_password(OWNER_PASSWORD),
        cookie_secure=False,
    )
    app = create_app(settings, engine=engine)
    return TestClient(app), engine


def seed_account(engine, account_id: str = "manager-account-01") -> str:
    with Session(engine) as db:
        db.add(AccountRecord(id=account_id))
        db.add(PlatformIdentityRecord(
            id=str(uuid.uuid4()), account_id=account_id, provider="bale", provider_user_id="73421"
        ))
        db.commit()
    return account_id


def owner_login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "nora-owner", "password": OWNER_PASSWORD},
        headers=ORIGIN,
    )
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "owner"


def owner_write_headers(client: TestClient, *, include_csrf: bool = True) -> dict[str, str]:
    headers = dict(ORIGIN)
    if include_csrf:
        headers["X-CSRF-Token"] = client.cookies.get("nora_csrf", "")
    return headers


def assign_role(client: TestClient, account_id: str, role: str | None) -> None:
    response = client.put(
        f"/api/owner/accounts/{account_id}/role",
        json={"role": role},
        headers=owner_write_headers(client),
    )
    assert response.status_code == 200, response.text


def set_credentials(client: TestClient, account_id: str, username: str, password: str):
    return client.put(
        f"/api/owner/accounts/{account_id}/manager-credentials",
        json={"username": username, "password": password},
        headers=owner_write_headers(client),
    )


def test_shared_staff_login_uses_server_identity_for_owner_and_manager():
    client, engine = make_client()
    account_id = seed_account(engine)
    try:
        with client:
            owner_login(client)
            assign_role(client, account_id, ROLE_MANAGER)
            configured = set_credentials(client, account_id, "manager.shared", MANAGER_PASSWORD)
            assert configured.status_code == 200, configured.text

            client.cookies.delete("nora_session")
            client.cookies.delete("nora_csrf")
            manager = client.post(
                "/api/auth/staff-login",
                json={"username": "MANAGER.SHARED", "password": MANAGER_PASSWORD},
                headers=ORIGIN,
            )
            assert manager.status_code == 200, manager.text
            assert manager.json() == {
                "authenticated": True,
                "provider": "manager-password",
                "account_id": account_id,
            }
            assert "role" not in manager.json() and "permissions" not in manager.json()
            manager_session = client.get("/api/account/me")
            assert manager_session.status_code == 200
            assert manager_session.json()["provider"] == "manager-password"
            assert manager_session.json()["role"] == ROLE_MANAGER
            assert client.get("/api/forms").status_code == 200
            assert client.get("/api/owner/accounts").status_code == 401

            client.cookies.delete("nora_account_session")
            client.cookies.delete("nora_account_csrf")
            owner = client.post(
                "/api/auth/staff-login",
                json={"username": "nora-owner", "password": OWNER_PASSWORD},
                headers=ORIGIN,
            )
            assert owner.status_code == 200, owner.text
            assert owner.json()["provider"] == "owner"
            assert owner.json()["role"] == "owner"
            assert client.get("/api/auth/me").json()["role"] == "owner"
            assert client.get("/api/account/me").status_code == 401

            cross_origin = client.post(
                "/api/auth/staff-login",
                json={"username": "nora-owner", "password": OWNER_PASSWORD},
                headers={"Origin": "https://attacker.example"},
            )
            assert cross_origin.status_code == 403
    finally:
        client.close()
        engine.dispose()


def test_shared_staff_login_is_same_origin_generic_and_rate_limited():
    client, engine = make_client()
    try:
        with client:
            cross_origin = client.post(
                "/api/auth/staff-login",
                json={"username": "nora-owner", "password": OWNER_PASSWORD},
                headers={"Origin": "https://attacker.example"},
            )
            assert cross_origin.status_code == 403

            unknown = client.post(
                "/api/auth/staff-login",
                json={"username": "unknown.staff", "password": "not-a-real-password"},
                headers=ORIGIN,
            )
            wrong_owner = client.post(
                "/api/auth/staff-login",
                json={"username": "nora-owner", "password": "not-a-real-password"},
                headers=ORIGIN,
            )
            assert unknown.status_code == wrong_owner.status_code == 401
            assert unknown.json()["detail"] == wrong_owner.json()["detail"] == "invalid_credentials"

            for _ in range(5):
                failed = client.post(
                    "/api/auth/staff-login",
                    json={"username": "blocked.staff", "password": "incorrect-password"},
                    headers=ORIGIN,
                )
                assert failed.status_code == 401
            blocked = client.post(
                "/api/auth/staff-login",
                json={"username": "blocked.staff", "password": "incorrect-password"},
                headers=ORIGIN,
            )
            assert blocked.status_code == 429
            assert blocked.headers.get("Retry-After")
            assert client.get("/api/auth/me").status_code == 401
            assert client.get("/api/account/me").status_code == 401
    finally:
        client.close()
        engine.dispose()


def test_manager_password_login_is_owner_provisioned_server_role_gated_and_revocable():
    client, engine = make_client()
    account_id = seed_account(engine)
    try:
        with client:
            owner_login(client)
            path = f"/api/owner/accounts/{account_id}/manager-credentials"

            no_role = set_credentials(client, account_id, "manager.one", MANAGER_PASSWORD)
            assert no_role.status_code == 409
            assert no_role.json()["detail"] == "manager_role_required"
            assert client.post(
                "/api/auth/manager-login",
                json={"username": "manager.one", "password": MANAGER_PASSWORD},
                headers=ORIGIN,
            ).status_code == 401

            assign_role(client, account_id, ROLE_MANAGER)
            missing_csrf = client.put(
                path,
                json={"username": "manager.one", "password": MANAGER_PASSWORD},
                headers=owner_write_headers(client, include_csrf=False),
            )
            assert missing_csrf.status_code == 403
            assert set_credentials(client, account_id, "nora-owner", MANAGER_PASSWORD).status_code == 422
            assert set_credentials(client, account_id, "ab", MANAGER_PASSWORD).status_code == 422
            assert set_credentials(client, account_id, "manager.one", "too-short").status_code == 422

            created = set_credentials(client, account_id, "Manager.One", MANAGER_PASSWORD)
            assert created.status_code == 200, created.text
            assert created.json() == {
                "account_id": account_id,
                "username": "manager.one",
                "configured": True,
            }
            assert MANAGER_PASSWORD not in created.text
            listing = client.get("/api/owner/accounts")
            assert listing.status_code == 200
            listed = listing.json()["items"][0]
            assert listed["manager_login_enabled"] is True
            assert listed["manager_username"] == "manager.one"
            assert "password_hash" not in listing.text and MANAGER_PASSWORD not in listing.text
            with Session(engine) as db:
                credential = db.get(ManagerCredentialRecord, account_id)
                assert credential is not None
                assert credential.password_hash != MANAGER_PASSWORD
                assert verify_password(MANAGER_PASSWORD, credential.password_hash)

            # Account sessions cannot provision/reset manager credentials.
            client.cookies.delete("nora_session")
            client.cookies.delete("nora_csrf")
            account_login = client.post(
                "/api/auth/manager-login",
                json={"username": " MANAGER.ONE ", "password": MANAGER_PASSWORD},
                headers=ORIGIN,
            )
            assert account_login.status_code == 200, account_login.text
            assert account_login.json()["provider"] == "manager-password"
            assert "role" not in account_login.json() and "permissions" not in account_login.json()
            manager_session_token = client.cookies.get("nora_account_session")
            assert manager_session_token
            account = client.get("/api/account/me")
            assert account.status_code == 200
            assert account.json()["provider"] == "manager-password"
            assert account.json()["role"] == ROLE_MANAGER
            assert set(account.json()["permissions"]) == set(permissions_for_role(ROLE_MANAGER))
            assert client.get("/api/forms").status_code == 200
            assert client.get("/api/owner/accounts").status_code == 401
            forbidden_reset = client.put(
                path,
                json={"username": "manager.one", "password": MANAGER_PASSWORD},
                headers={
                    "Origin": "http://testserver",
                    "X-CSRF-Token": client.cookies.get("nora_account_csrf", ""),
                },
            )
            assert forbidden_reset.status_code == 401

            # A reset replaces the verifier and invalidates all earlier password sessions.
            owner_login(client)
            replacement_password = "replacement-manager-password-2026"
            replaced = set_credentials(client, account_id, "manager.one", replacement_password)
            assert replaced.status_code == 200, replaced.text
            client.cookies.delete("nora_session")
            client.cookies.delete("nora_csrf")
            assert client.get("/api/account/me").status_code == 401
            old_password = client.post(
                "/api/auth/manager-login",
                json={"username": "manager.one", "password": MANAGER_PASSWORD},
                headers=ORIGIN,
            )
            assert old_password.status_code == 401
            new_password = client.post(
                "/api/auth/manager-login",
                json={"username": "MANAGER.ONE", "password": replacement_password},
                headers=ORIGIN,
            )
            assert new_password.status_code == 200, new_password.text
            assert client.get("/api/account/me").json()["role"] == ROLE_MANAGER

            # Removing the role also deletes the credential and revokes its active session.
            owner_login(client)
            assign_role(client, account_id, None)
            client.cookies.delete("nora_session")
            client.cookies.delete("nora_csrf")
            assert client.get("/api/account/me").status_code == 401
            assert client.post(
                "/api/auth/manager-login",
                json={"username": "manager.one", "password": replacement_password},
                headers=ORIGIN,
            ).status_code == 401
            with Session(engine) as db:
                assert db.get(ManagerCredentialRecord, account_id) is None
                sessions = db.scalars(select(AccountSessionRecord).where(
                    AccountSessionRecord.account_id == account_id,
                    AccountSessionRecord.auth_provider == "manager-password",
                )).all()
                assert sessions and all(session.revoked_at is not None for session in sessions)
    finally:
        client.close()
        engine.dispose()


def test_manager_login_is_same_origin_generic_and_rate_limited():
    client, engine = make_client()
    account_id = seed_account(engine)
    try:
        with client:
            owner_login(client)
            assign_role(client, account_id, ROLE_CLUB_SUPERVISOR)
            created = set_credentials(client, account_id, "club.lead", MANAGER_PASSWORD)
            assert created.status_code == 200
            client.cookies.delete("nora_session")
            client.cookies.delete("nora_csrf")

            cross_origin = client.post(
                "/api/auth/manager-login",
                json={"username": "club.lead", "password": MANAGER_PASSWORD},
                headers={"Origin": "https://attacker.example"},
            )
            assert cross_origin.status_code == 403
            missing_user = client.post(
                "/api/auth/manager-login",
                json={"username": "unknown.user", "password": "not-a-real-password"},
                headers=ORIGIN,
            )
            wrong_password = client.post(
                "/api/auth/manager-login",
                json={"username": "club.lead", "password": "not-a-real-password"},
                headers=ORIGIN,
            )
            assert missing_user.status_code == wrong_password.status_code == 401
            assert missing_user.json()["detail"] == wrong_password.json()["detail"] == "invalid_credentials"

            for _ in range(4):
                failed = client.post(
                    "/api/auth/manager-login",
                    json={"username": "club.lead", "password": "incorrect-password"},
                    headers=ORIGIN,
                )
                assert failed.status_code == 401
            blocked = client.post(
                "/api/auth/manager-login",
                json={"username": "club.lead", "password": MANAGER_PASSWORD},
                headers=ORIGIN,
            )
            assert blocked.status_code == 429
            assert blocked.headers.get("Retry-After")
            assert client.get("/api/account/me").status_code == 401
    finally:
        client.close()
        engine.dispose()
