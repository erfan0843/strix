from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend.app import create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import Base, FormRecord  # noqa: E402
from backend.security import hash_password  # noqa: E402


def make_client(*, with_database: bool = True):
    engine = None
    if with_database:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None,
        owner_id="owner-capabilities",
        owner_username="owner",
        owner_password_hash=hash_password("capability-test-password"),
        cookie_secure=False,
    )
    app = create_app(settings, engine=engine)
    return engine, TestClient(app)


def test_public_capability_contract_is_secret_free_and_read_only():
    engine, client = make_client()
    try:
        response = client.get("/api/public/forms/capabilities")
        assert response.status_code == 200
        body = response.json()
        assert body["version"] == 1
        assert body["source"] == "same_application_fastapi"
        assert body["api_configured"] is True
        assert {item["id"] for item in body["models"]} == {
            "registration", "questionnaire", "survey", "contest", "exam",
            "attendance", "datacollect", "order", "election",
        }
        models = {item["id"]: item for item in body["models"]}
        assert models["registration"]["status"] == "server"
        assert models["survey"]["status"] == "limited"
        assert models["order"]["status"] == "unavailable"
        assert models["order"]["publishable"] is False
        assert body["settings"]["capacity"]["status"] == "server"
        assert body["settings"]["waitlist"]["status"] == "server"
        assert body["settings"]["conditional_visibility"]["status"] == "server"
        assert body["settings"]["conditional_visibility"]["max_rules_per_field"] == 10
        assert body["settings"]["schedule"]["status"] == "unavailable"
        assert body["settings"]["one_response_per_person"]["status"] == "unavailable"
        assert body["settings"]["bale_wallet"]["ready"] is False
        assert body["field_types"]["text"]["status"] == "server"
        assert body["field_types"]["imgchoice"]["status"] == "limited"
        assert body["field_types"]["file"]["status"] == "unavailable"
        assert body["field_types"]["coupon"]["status"] == "unavailable"
        assert not any(
            "token" in key.lower() or "secret" in key.lower() or "password" in key.lower()
            for key in body
        )
        with engine.connect() as connection:
            count = connection.scalar(select(func.count()).select_from(FormRecord))
        assert count == 0
    finally:
        client.close()
        if engine is not None:
            engine.dispose()


def test_capability_contract_is_available_but_marks_backend_unconfigured():
    _engine, client = make_client(with_database=False)
    try:
        response = client.get("/api/public/forms/capabilities")
        assert response.status_code == 200
        assert response.json()["api_configured"] is False
        assert response.json()["settings"]["bale_wallet"]["ready"] is False
    finally:
        client.close()


def test_readiness_endpoint_requires_form_permission_and_does_not_mutate_form():
    engine, client = make_client()
    try:
        login = client.post(
            "/api/auth/login",
            json={"username": "owner", "password": "capability-test-password"},
            headers={"Origin": "http://testserver"},
        )
        assert login.status_code == 200, login.text
        create = client.post(
            "/api/forms",
            json={
                "name": "فرم نمونه",
                "model": "registration",
                "need": "reg",
                "slug": "readiness/sample",
                "fields": [{"id": "q1", "t": "text", "l": "نام"}],
                "settings": {"cap": 20, "wait": 5},
            },
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": client.cookies.get("nora_csrf", ""),
                "Idempotency-Key": "readiness-draft-create-01",
            },
        )
        assert create.status_code == 201, create.text
        form = create.json()
        before = (form["status"], form["version"])

        readiness = client.get(f"/api/forms/{form['id']}/readiness")
        assert readiness.status_code == 200, readiness.text
        result = readiness.json()
        assert result["source"] == "same_server_database"
        assert result["publishable"] is True
        assert result["issues"] == []

        refreshed = client.get(f"/api/forms/{form['id']}")
        assert refreshed.status_code == 200
        assert (refreshed.json()["status"], refreshed.json()["version"]) == before
        listed = client.get("/api/forms")
        assert listed.status_code == 200
        item = next(row for row in listed.json()["items"] if row["id"] == form["id"])
        assert item["response_count"] == 0
    finally:
        client.close()
        engine.dispose()


def test_readiness_reports_blockers_without_publishing():
    engine, client = make_client()
    try:
        client.post(
            "/api/auth/login",
            json={"username": "owner", "password": "capability-test-password"},
            headers={"Origin": "http://testserver"},
        )
        create = client.post(
            "/api/forms",
            json={
                "name": "فرم محدودشده",
                "model": "registration",
                "need": "reg",
                "slug": "readiness/blocked",
                "fields": [{"id": "file1", "t": "file", "l": "پیوست"}],
                "settings": {"cap": 10, "wait": 0, "limit": "invite"},
            },
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": client.cookies.get("nora_csrf", ""),
                "Idempotency-Key": "readiness-draft-create-02",
            },
        )
        assert create.status_code == 201, create.text
        form_id = create.json()["id"]
        response = client.get(f"/api/forms/{form_id}/readiness")
        assert response.status_code == 200
        payload = response.json()
        codes = {issue["code"] for issue in payload["issues"]}
        assert payload["publishable"] is False
        assert "external_limit_not_connected" in codes
        assert "field_type_not_supported" in codes
        assert payload["status"] == "draft"
        assert client.get(f"/api/forms/{form_id}").json()["status"] == "draft"
    finally:
        client.close()
        engine.dispose()
