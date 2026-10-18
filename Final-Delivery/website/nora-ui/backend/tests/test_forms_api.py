from __future__ import annotations

import base64
import json
import sys
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, quote, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool


BACKEND_PARENT = Path(__file__).resolve().parents[2]
ORIGIN = {"Origin": "http://testserver"}
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

import backend.app as backend_app  # noqa: E402
import backend.form_quality as form_quality  # noqa: E402
import backend.responses as response_helpers  # noqa: E402
from backend.app import _form_ticket_name, _ticket_text, create_app  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.models import (  # noqa: E402
    AccountRecord,
    AccountRoleRecord,
    AccountSessionRecord,
    AdminTaskRecord,
    Base,
    FormReceiptUploadRecord,
    FormResponseDraftRecord,
    FormResponseRecord,
    PlatformIdentityRecord,
    PrivateFileRecord,
)
from backend.roles import permissions_for_role  # noqa: E402
from backend.security import hash_password, token_digest  # noqa: E402


@pytest.fixture
def configured_client():
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
        owner_password_hash=hash_password("correct-horse-staple-42"),
        session_ttl_seconds=3600,
        cookie_secure=False,
        bot_service_token="b" * 48,
    )
    app = create_app(settings, engine=engine)
    with TestClient(app) as client:
        yield client, settings
    engine.dispose()


def valid_form() -> dict:
    return {
        "name": "ثبت نام کارگاه",
        "model": "registration",
        "need": "reg",
        "slug": "workshops/spring",
        "ev": "event-2026-01",
        "settings": {"description": "فرم آزمایشی", "confirmation": "ثبت شد"},
        "fields": [
            {"id": "full-name", "t": "text", "l": "نام کامل", "required": True},
            {
                "id": "city",
                "t": "select",
                "l": "شهر",
                "options": ["پاریس", "تهران"],
                "condField": "full-name",
                "condOp": "nempty",
            },
        ],
    }


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "nora-owner", "password": "correct-horse-staple-42"},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "authenticated": True,
        "owner_id": "owner-01",
        "role": "owner",
        "permissions": sorted(permissions_for_role("owner")),
    }


def csrf_headers(client: TestClient) -> dict[str, str]:
    return {
        "Origin": "http://testserver",
        "X-CSRF-Token": client.cookies.get("nora_csrf", ""),
    }


def create_headers(client: TestClient, key: str = "draft-create-key-0001") -> dict[str, str]:
    return {**csrf_headers(client), "Idempotency-Key": key}


def install_web_account_session(client: TestClient, account_id: str) -> None:
    raw_session = "test-web-session-" + account_id
    raw_csrf = "test-web-csrf-" + account_id
    with client.app.state.session_factory() as db:
        db.add(AccountRecord(id=account_id))
        db.add(PlatformIdentityRecord(
            id=str(uuid.uuid4()),
            account_id=account_id,
            provider="phone",
            provider_user_id=token_digest("verified-phone:" + account_id),
        ))
        db.add(AccountSessionRecord(
            id=str(uuid.uuid4()),
            account_id=account_id,
            auth_provider="phone",
            token_hash=token_digest(raw_session),
            csrf_hash=token_digest(raw_csrf),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        db.commit()
    settings = client.app.state.settings
    client.cookies.set(settings.account_cookie_name, raw_session, path="/")
    client.cookies.set(settings.account_csrf_cookie_name, raw_csrf, path="/")


def test_ticket_text_normalizes_whitespace_and_keeps_persian_joiners():
    assert _ticket_text("  کارگاه\tفرهنگ\nایرانی‌ها \x00  ", 160) == "کارگاه فرهنگ ایرانی‌ها"


def test_shared_ticket_name_comes_from_answer_without_a_placeholder():
    answered = SimpleNamespace(
        registrant_name=None,
        form_snapshot={"fields": [
            {"id": "name", "type": "text", "label": "نام کامل"},
        ]},
        answers={"name": "  لیلا   رضایی "},
    )
    unnamed = SimpleNamespace(
        registrant_name=None,
        form_snapshot={"fields": [
            {"id": "city", "type": "text", "label": "شهر"},
        ]},
        answers={"city": "تهران"},
    )
    typed_name = SimpleNamespace(
        registrant_name=None,
        form_snapshot={"fields": [
            {"id": "participant", "type": "fullname", "label": "شرکت‌کننده"},
        ]},
        answers={"participant": "مهتاب نوروزی"},
    )

    assert _form_ticket_name(answered) == "لیلا رضایی"
    assert _form_ticket_name(unnamed) == ""
    assert _form_ticket_name(typed_name) == "مهتاب نوروزی"


def test_public_form_companions_validate_save_submit_and_remain_web_only(configured_client):
    client, settings = configured_client
    login(client)
    payload = valid_form()
    payload["fields"][1]["required"] = True
    payload["fields"].append({"id": "mobile", "t": "mobile", "l": "شمارهٔ همراه", "required": True})
    payload["settings"].update({"guestsOn": True, "maxPer": 3, "compFields": "name-mobile-answers"})
    created = client.post("/api/forms", json=payload, headers=create_headers(client, "companions-create-01"))
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    published = client.post(
        f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=csrf_headers(client)
    )
    assert published.status_code == 200, published.text
    public = client.get(f"/api/public/forms/{form_id}")
    assert public.status_code == 200, public.text
    assert public.json()["guestsOn"] is True
    assert public.json()["maxPer"] == 3
    assert public.json()["compFields"] == "name-mobile-answers"
    assert public.json()["settings"]["compFields"] == "name-mobile-answers"

    service_headers = {"Authorization": "Bearer " + settings.bot_service_token}
    catalog = client.get("/api/bot/forms/public", headers=service_headers)
    assert catalog.status_code == 200
    assert form_id not in {item["id"] for item in catalog.json()["items"]}
    bot_identity = {"bale_user_id": "73421", "session_key": "c" * 43}
    bot_endpoint = f"/api/bot/forms/{form_id}"
    assert client.post(bot_endpoint + "/draft", json=bot_identity, headers=service_headers).status_code == 409
    assert client.patch(
        bot_endpoint + "/draft",
        json={**bot_identity, "field_id": "full-name", "value": "ربات"},
        headers=service_headers,
    ).status_code == 409
    assert client.post(bot_endpoint + "/responses", json=bot_identity, headers=service_headers).status_code == 404

    origin = {"Origin": "http://testserver"}
    first_draft = client.get(f"/api/public/forms/{form_id}/draft")
    assert first_draft.status_code == 200
    assert first_draft.json()["companions"] == []
    primary_answers = {"full-name": "لیلا", "city": "پاریس", "mobile": "09120000000"}
    companions = [
        {
            "name": "مریم همراه", "mobile": "۰۹۱۲۱۲۳۴۵۶۷",
            "answers": {"full-name": "مریم", "city": "تهران", "mobile": "09121234567"},
        },
        {
            "name": "رضا همراه", "mobile": "09121234568",
            "answers": {"full-name": "رضا", "city": "پاریس", "mobile": "09121234568"},
        },
    ]
    saved = client.patch(
        f"/api/public/forms/{form_id}/draft",
        json={"answers": {"full-name": "ل", "mobile": "09"}, "companions": [{
            "name": "م", "mobile": "09", "answers": {"full-name": "م", "mobile": "09"},
        }]},
        headers=origin,
    )
    assert saved.status_code == 200, saved.text
    recovered = client.get(f"/api/public/forms/{form_id}/draft")
    assert recovered.status_code == 200
    assert recovered.json()["answers"]["mobile"] == "09"
    assert recovered.json()["companions"] == [{
        "name": "م", "mobile": "09", "answers": {"full-name": "م", "mobile": "09"},
    }]

    missing_companion_answer = client.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": primary_answers, "companions": [{
            "name": "مریم همراه", "mobile": "09121234567",
            "answers": {"full-name": "مریم", "mobile": "09121234567"},
        }]},
        headers=origin,
    )
    assert missing_companion_answer.status_code == 422
    missing_issue = missing_companion_answer.json()["detail"]["errors"][0]
    assert missing_issue["field_id"] == "city" and missing_issue["companion_index"] == 0

    too_many_companions = client.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": primary_answers, "companions": [
            {"name": f"همراه شماره {index}", "mobile": mobile,
             "answers": {"full-name": f"پاسخ {index}", "city": "تهران", "mobile": mobile}}
            for index, mobile in enumerate(("09121234569", "09121234570", "09121234571"), start=1)
        ]},
        headers=origin,
    )
    assert too_many_companions.status_code == 422
    assert too_many_companions.json()["detail"]["errors"][0]["code"] == "companion_limit_exceeded"

    invalid_duplicate = client.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": primary_answers, "companions": [
            {"name": "مریم همراه", "mobile": "09121234567", "answers": {"full-name": "مریم", "city": "تهران", "mobile": "09121234567"}},
            {"name": "رضا همراه", "mobile": "۰۹۱۲۱۲۳۴۵۶۷", "answers": {"full-name": "رضا", "city": "تهران", "mobile": "09121234567"}},
        ]},
        headers=origin,
    )
    assert invalid_duplicate.status_code == 422
    assert invalid_duplicate.json()["detail"]["errors"][0]["companion_index"] == 1

    submitted = client.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": primary_answers, "companions": companions}, headers=origin,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["accepted"] is True
    assert submitted.json()["registrants_count"] == 3
    restored = client.get(f"/api/public/forms/{form_id}/draft")
    assert restored.json()["submitted"] is True
    assert restored.json()["companions"] == [
        {"name": "مریم همراه", "mobile": "09121234567", "answers": {"full-name": "مریم", "city": "تهران", "mobile": "09121234567"}},
        {"name": "رضا همراه", "mobile": "09121234568", "answers": {"full-name": "رضا", "city": "پاریس", "mobile": "09121234568"}},
    ]
    owner_rows = client.get(f"/api/forms/{form_id}/responses")
    assert owner_rows.status_code == 200
    assert owner_rows.json()["total"] == 3
    primary_row = next(item for item in owner_rows.json()["items"] if item["answers"].get("full-name") == "لیلا")
    companion_row = next(
        item for item in owner_rows.json()["items"] if item.get("registrant_name") == "مریم همراه"
    )
    second_companion = next(
        item for item in owner_rows.json()["items"] if item.get("registrant_name") == "رضا همراه"
    )
    assert primary_row["companions"] == []
    assert companion_row["id"] != primary_row["id"]
    assert companion_row["answers"] == {"full-name": "مریم", "city": "تهران", "mobile": "09121234567"}
    assert companion_row["registrant_mobile"] == "09121234567"
    assert companion_row["added_by_response_id"] == primary_row["id"]
    assert companion_row["added_by_name"] == "لیلا"
    assert companion_row["companion_index"] == 0
    assert second_companion["added_by_response_id"] == primary_row["id"]
    assert second_companion["companion_index"] == 1
    assert second_companion["answers"] == {"full-name": "رضا", "city": "پاریس", "mobile": "09121234568"}

    revised_companions = [{"name": "مریم رضایی", "mobile": "09120000000", "answers": {
        "full-name": "مریم رضایی", "city": "پاریس", "mobile": "09120000000",
    }}]
    revised = client.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": primary_answers, "companions": revised_companions}, headers=origin,
    )
    assert revised.status_code == 200, revised.text
    rows_after_retry = client.get(f"/api/forms/{form_id}/responses").json()
    assert rows_after_retry["total"] == 2
    assert sum(item.get("registrant_name") == "مریم رضایی" for item in rows_after_retry["items"]) == 1
    assert not any(item.get("registrant_name") == "مریم همراه" for item in rows_after_retry["items"])
    revised_companion = next(
        item for item in rows_after_retry["items"] if item.get("registrant_name") == "مریم رضایی"
    )
    assert revised_companion["added_by_name"] == "لیلا"
    assert client.get(f"/api/public/forms/{form_id}/draft").json()["companions"] == revised_companions


def test_public_companion_rows_consume_capacity_per_person(configured_client):
    client, _settings = configured_client
    login(client)
    payload = valid_form()
    payload["fields"].append({"id": "mobile", "t": "mobile", "l": "شمارهٔ همراه", "required": True})
    payload["settings"].update({
        "guestsOn": True,
        "maxPer": 2,
        "compFields": "name-mobile-answers",
        "cap": 1,
        "wait": 1,
    })
    created = client.post("/api/forms", json=payload, headers=create_headers(client, "companion-capacity-01"))
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    published = client.post(
        f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=csrf_headers(client)
    )
    assert published.status_code == 200, published.text
    assert client.get(f"/api/public/forms/{form_id}/draft").status_code == 200

    result = client.post(
        f"/api/public/forms/{form_id}/responses",
        json={
            "answers": {"full-name": "لیلا", "mobile": "09121112222"},
            "companions": [{
                "name": "مریم همراه",
                "mobile": "09121234567",
                "answers": {"full-name": "مریم", "mobile": "09121234567"},
            }],
        },
        headers={"Origin": "http://testserver"},
    )
    assert result.status_code == 200, result.text
    assert result.json()["registrants_count"] == 2
    rows = client.get(f"/api/forms/{form_id}/responses").json()
    assert rows["total"] == 2
    assert {item["status"] for item in rows["items"]} == {"accepted", "waitlisted"}
    companion_row = next(item for item in rows["items"] if item.get("registrant_name"))
    assert companion_row["status"] == "waitlisted"

    client.cookies.clear()
    assert client.get(f"/api/public/forms/{form_id}/draft").status_code == 410


def test_server_offline_quality_rules_are_semantic_and_keep_manual_universities(configured_client):
    client, _settings = configured_client
    login(client)
    payload = valid_form()
    payload["fields"] = [
        {"id": "full-name", "t": "text", "l": "نام کامل", "required": True},
        {"id": "mobile", "t": "mobile", "l": "شمارهٔ همراه", "required": True},
        {"id": "birth-date", "t": "date", "l": "تاریخ تولد", "required": False},
        {"id": "event-date", "t": "date", "l": "تاریخ رویداد", "required": False},
        {"id": "university", "t": "uni", "l": "نام دانشگاه", "required": False},
        {"id": "comment", "t": "text", "l": "توضیح آزاد", "required": False},
    ]
    payload["settings"].update({"guestsOn": True, "maxPer": 2, "compFields": "name-mobile-answers"})
    created = client.post(
        "/api/forms", json=payload, headers=create_headers(client, "offline-quality-form-key-01")
    )
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    published = client.post(
        f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=csrf_headers(client)
    )
    assert published.status_code == 200, published.text
    assert client.get(f"/api/public/forms/{form_id}/draft").status_code == 200

    today = form_quality.current_jalali_date()
    today_text = f"{today[0]:04d}/{today[1]:02d}/{today[2]:02d}"
    future_text = f"{today[0] + 1:04d}/01/01"
    answers = {
        "full-name": "رررر",
        "mobile": "09121234567",
        "birth-date": future_text,
        "event-date": future_text,
        "university": "تهران · دانشگاه خارج از فهرست",
        "comment": "poiuytrewq",
    }
    partial = client.patch(
        f"/api/public/forms/{form_id}/draft", json={"answers": answers}, headers=ORIGIN
    )
    assert partial.status_code == 200, partial.text

    repeated_name = client.post(
        f"/api/public/forms/{form_id}/responses", json={"answers": answers}, headers=ORIGIN
    )
    assert repeated_name.status_code == 422
    repeated_issue = repeated_name.json()["detail"]["errors"][0]
    assert repeated_issue["field_id"] == "full-name"
    assert repeated_issue["code"] == "suspicious_repeated_name"
    assert "تکرار یک حرف" in repeated_issue["message"]

    answers["full-name"] = "لیلا رررر"
    repeated_name_token = client.post(
        f"/api/public/forms/{form_id}/responses", json={"answers": answers}, headers=ORIGIN
    )
    assert repeated_name_token.status_code == 422
    assert repeated_name_token.json()["detail"]["errors"][0]["code"] == "suspicious_repeated_name"

    answers["full-name"] = "Test"
    placeholder_name = client.post(
        f"/api/public/forms/{form_id}/responses", json={"answers": answers}, headers=ORIGIN
    )
    assert placeholder_name.status_code == 422
    assert placeholder_name.json()["detail"]["errors"][0]["code"] == "placeholder_name"

    answers["full-name"] = "لیلا"
    future_birth = client.post(
        f"/api/public/forms/{form_id}/responses", json={"answers": answers}, headers=ORIGIN
    )
    assert future_birth.status_code == 422
    birth_issue = future_birth.json()["detail"]["errors"][0]
    assert birth_issue["field_id"] == "birth-date"
    assert birth_issue["code"] == "birth_date_in_future"

    answers["birth-date"] = today_text
    invalid_companion = client.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": answers, "companions": [{
            "name": "رررر", "mobile": "09122223333",
            "answers": {"full-name": "سارا", "mobile": "09122223333"},
        }]},
        headers=ORIGIN,
    )
    assert invalid_companion.status_code == 422
    companion_issue = invalid_companion.json()["detail"]["errors"][0]
    assert companion_issue["code"] == "suspicious_repeated_name"
    assert companion_issue["companion_index"] == 0

    accepted = client.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": answers, "companions": [{
            "name": "سارا همراه", "mobile": "09122223333",
            "answers": {"full-name": "سارا", "mobile": "09122223333"},
        }]},
        headers=ORIGIN,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["accepted"] is True
    assert accepted.json()["registrants_count"] == 2
    saved_answers = client.get(f"/api/forms/{form_id}/responses").json()["items"]
    primary = next(item for item in saved_answers if item["answers"].get("full-name") == "لیلا")
    assert primary["answers"]["birth-date"] == today_text
    assert primary["answers"]["event-date"] == future_text
    assert primary["answers"]["university"] == "تهران · دانشگاه خارج از فهرست"
    assert primary["answers"]["comment"] == "poiuytrewq"


def test_owner_auth_cookies_and_session_revocation(configured_client):
    client, _ = configured_client
    assert client.get("/api/auth/me").status_code == 401

    response = client.post(
        "/api/auth/login",
        json={"username": "nora-owner", "password": "not-the-password"},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_credentials"

    login(client)
    assert client.cookies.get("nora_session")
    assert client.cookies.get("nora_csrf")
    session_cookie = next(c for c in client.cookies.jar if c.name == "nora_session")
    csrf_cookie = next(c for c in client.cookies.jar if c.name == "nora_csrf")
    assert session_cookie.has_nonstandard_attr("HttpOnly")
    assert session_cookie.get_nonstandard_attr("SameSite") == "strict"
    assert not csrf_cookie.has_nonstandard_attr("HttpOnly")
    assert client.get("/api/auth/me").json()["role"] == "owner"

    logout_response = client.post("/api/auth/logout", headers=csrf_headers(client))
    assert logout_response.status_code == 200
    assert logout_response.json() == {"authenticated": False}
    assert client.get("/api/auth/me").status_code == 401


def test_form_draft_create_list_read_and_update_are_owner_and_csrf_protected(configured_client):
    client, _ = configured_client
    assert client.get("/api/forms").status_code == 401
    login(client)

    missing_csrf = client.post("/api/forms", json=valid_form(), headers={"Origin": "http://testserver"})
    assert missing_csrf.status_code == 403

    create = client.post("/api/forms", json=valid_form(), headers=create_headers(client))
    assert create.status_code == 201, create.text
    saved = create.json()
    assert saved["id"]
    assert saved["name"] == "ثبت نام کارگاه"
    assert saved["need"] == "reg"
    assert saved["ev"] == "event-2026-01"
    assert saved["status"] == "draft"
    assert saved["version"] == 1
    assert [field["id"] for field in saved["fields"]] == ["full-name", "city"]
    assert saved["fields"][1]["options"] == ["پاریس", "تهران"]

    listing = client.get("/api/forms")
    assert listing.status_code == 200
    assert len(listing.json()["items"]) == 1
    assert listing.json()["items"][0]["id"] == saved["id"]

    read = client.get(f"/api/forms/{saved['id']}")
    assert read.status_code == 200
    assert read.json()["settings"]["description"] == "فرم آزمایشی"

    updated_payload = valid_form()
    updated_payload["name"] = "ثبت نام کارگاه ویرایش شده"
    updated_payload["expected_version"] = 1
    updated_payload["fields"].append({"id": "note", "t": "textarea", "l": "توضیح"})
    update = client.put(f"/api/forms/{saved['id']}", json=updated_payload, headers=csrf_headers(client))
    assert update.status_code == 200, update.text
    assert update.json()["version"] == 2
    assert update.json()["name"] == "ثبت نام کارگاه ویرایش شده"
    assert len(update.json()["fields"]) == 3

    stale_payload = valid_form()
    stale_payload["expected_version"] = 1
    stale = client.put(f"/api/forms/{saved['id']}", json=stale_payload, headers=csrf_headers(client))
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "version_conflict"
    assert stale.json()["detail"]["current_version"] == 2

    missing_version = valid_form()
    missing_version.pop("expected_version", None)
    no_version = client.put(f"/api/forms/{saved['id']}", json=missing_version, headers=csrf_headers(client))
    assert no_version.status_code == 428


def test_ticket_type_configuration_round_trips_only_on_registration_drafts(configured_client):
    client, _ = configured_client
    login(client)
    payload = valid_form()
    ticketing = {
        "mode": "random",
        "types": [
            {"id": "general", "name": "ورودی عمومی"},
            {"id": "special", "name": "ورودی ویژه"},
            {"id": "guest", "name": "مهمان"},
        ],
    }
    payload["settings"]["ticketing"] = ticketing
    created = client.post(
        "/api/forms",
        json=payload,
        headers=create_headers(client, "ticket-config-create-01"),
    )
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    assert created.json()["settings"]["ticketing"] == ticketing
    assert client.get(f"/api/forms/{form_id}").json()["settings"]["ticketing"] == ticketing

    updated_payload = valid_form()
    updated_payload["expected_version"] = 1
    updated_payload["settings"]["ticketing"] = {
        "mode": "single",
        "types": [{"id": "standard", "name": "ورودی استاندارد"}],
    }
    updated = client.put(
        f"/api/forms/{form_id}",
        json=updated_payload,
        headers=csrf_headers(client),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["settings"]["ticketing"] == updated_payload["settings"]["ticketing"]


def test_ticket_type_configuration_rejects_invalid_modes_names_and_models(configured_client):
    client, _ = configured_client
    login(client)
    cases = [
        (
            {"mode": "random", "types": [{"id": "only", "name": "تکی"}]},
            "invalid_ticket_type_count",
            "registration",
        ),
        (
            {"mode": "single", "types": [
                {"id": "one", "name": "عادی"}, {"id": "two", "name": "ویژه"}
            ]},
            "invalid_ticket_type_count",
            "registration",
        ),
        (
            {"mode": "random", "types": [
                {"id": "one", "name": "عادی"}, {"id": "two", "name": "عادی"}
            ]},
            "duplicate_ticket_type_name",
            "registration",
        ),
        (
            {"mode": "single", "types": [{"id": "bad/id", "name": "عادی"}]},
            "invalid_ticket_type_id",
            "registration",
        ),
        (
            {"mode": "single", "types": [{"id": "one", "name": " "}]},
            "invalid_ticket_type_name",
            "registration",
        ),
        (
            {"mode": "random", "types": [
                {"id": "one", "name": "عادی"}, {"id": "two", "name": "ویژه"}
            ]},
            "ticketing_requires_registration",
            "survey",
        ),
    ]
    for index, (ticketing, expected_code, model) in enumerate(cases):
        payload = valid_form()
        payload["model"] = model
        payload["need"] = "survey" if model == "survey" else "reg"
        payload["settings"]["ticketing"] = ticketing
        response = client.post(
            "/api/forms", json=payload,
            headers=create_headers(client, f"ticket-config-invalid-{index:02d}"),
        )
        assert response.status_code == 422, response.text
        assert response.json()["detail"]["code"] == expected_code


def test_create_is_idempotent_and_payload_cannot_change_under_same_key(configured_client):
    client, _ = configured_client
    login(client)
    key = "create-once-key-000001"
    payload = valid_form()
    first = client.post("/api/forms", json=payload, headers=create_headers(client, key))
    assert first.status_code == 201, first.text

    retry = client.post("/api/forms", json=payload, headers=create_headers(client, key))
    assert retry.status_code == 200
    assert retry.json()["id"] == first.json()["id"]
    assert len(client.get("/api/forms").json()["items"]) == 1

    changed = valid_form()
    changed["name"] = "تلاش برای تغییر کلید"
    conflict = client.post("/api/forms", json=changed, headers=create_headers(client, key))
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"
    assert len(client.get("/api/forms").json()["items"]) == 1


def test_owner_idor_and_client_cannot_publish_or_set_owner(configured_client):
    client, _ = configured_client
    login(client)
    assert client.get("/api/forms/someone-elses-form").status_code == 404

    payload = valid_form()
    payload["owner_id"] = "attacker"
    response = client.post("/api/forms", json=payload, headers=csrf_headers(client))
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unexpected_fields"

    payload = valid_form()
    payload["settings"]["published"] = True
    response = client.post("/api/forms", json=payload, headers=csrf_headers(client))
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "server_owned_setting"


def test_api_accepts_and_round_trips_all_condition_operators(configured_client):
    client, _ = configured_client
    login(client)
    operators = (
        "eq", "ne", "contains", "ncontains", "starts", "nstarts", "ends", "nends",
        "gt", "gte", "lt", "lte", "empty", "nempty",
    )
    fields = [
        {"id": "source-text", "t": "text", "l": "پاسخ متنی"},
        {"id": "source-number", "t": "number", "l": "پاسخ عددی"},
    ]
    values = {
        "eq": "target",
        "ne": "target",
        "contains": "part",
        "ncontains": "part",
        "starts": "pre",
        "nstarts": "pre",
        "ends": "post",
        "nends": "post",
        "gt": "5",
        "gte": "5",
        "lt": "10",
        "lte": "10",
        "empty": "",
        "nempty": "",
    }
    fields.extend(
        {
            "id": f"dependent-{operator}",
            "t": "text",
            "l": f"وابسته به {operator}",
            "condField": "source-number" if operator in {"gt", "gte", "lt", "lte"} else "source-text",
            "condOp": operator,
            "condVal": values[operator],
        }
        for operator in operators
    )
    payload = valid_form()
    payload["fields"] = fields

    response = client.post("/api/forms", json=payload, headers=create_headers(client))

    assert response.status_code == 201, response.text
    saved = response.json()
    dependent_fields = saved["fields"][2:]
    assert [field["condOp"] for field in dependent_fields] == list(operators)
    assert [field["condVal"] for field in dependent_fields] == [values[operator] for operator in operators]
    assert all(len(field["conditions"]) == 1 for field in dependent_fields)
    assert all(field["conditionLogic"] == "all" for field in dependent_fields)


def test_api_accepts_and_rejects_typed_date_time_values(configured_client):
    client, _ = configured_client
    login(client)
    fields = [
        {"id": "date-source", "t": "date", "l": "تاریخ"},
        {"id": "time-source", "t": "time", "l": "زمان"},
        {"id": "datetime-source", "t": "datetime", "l": "تاریخ و زمان"},
        {"id": "date-rule", "t": "text", "l": "قاعدهٔ تاریخ", "conditions": [
            {"field": "date-source", "op": "gte", "value": "۱۴۰۵/۰۷/۰۱"}], "conditionLogic": "all"},
        {"id": "time-rule", "t": "text", "l": "قاعدهٔ زمان", "conditions": [
            {"field": "time-source", "op": "lt", "value": "23:59"}], "conditionLogic": "all"},
        {"id": "datetime-rule", "t": "text", "l": "قاعدهٔ تاریخ‌وزمان", "conditions": [
            {"field": "datetime-source", "op": "eq", "value": "۱۴۰۵/۰۷/۰۱ ۱۸:۳۰"}], "conditionLogic": "all"},
        {"id": "leap-date-rule", "t": "text", "l": "روز پایانی سال کبیسه", "conditions": [
            {"field": "date-source", "op": "eq", "value": "۱۴۰۳/۱۲/۳۰"}], "conditionLogic": "all"},

    ]
    payload = valid_form()
    payload["fields"] = fields
    response = client.post("/api/forms", json=payload, headers=create_headers(client))
    assert response.status_code == 201, response.text
    saved = response.json()["fields"]
    assert [field["conditions"][0]["value"] for field in saved[3:]] == [
        "۱۴۰۵/۰۷/۰۱", "23:59", "۱۴۰۵/۰۷/۰۱ ۱۸:۳۰", "۱۴۰۳/۱۲/۳۰",
    ]

    invalid_values = [
        ("date", "lte", "۱۴۰۵/۰۷/۳۱"),
        ("date", "eq", "۱۴۰۵/۱۲/۳۰"),
        ("time", "gt", "24:00"),
        ("datetime", "eq", "۱۴۰۵/۰۷/۰۱ 18:60"),
    ]
    for field_type, operator, value in invalid_values:
        bad = valid_form()
        bad["fields"] = [
            {"id": "temporal-source", "t": field_type, "l": "مرجع زمان"},
            {"id": "temporal-dependent", "t": "text", "l": "وابسته", "conditions": [
                {"field": "temporal-source", "op": operator, "value": value}], "conditionLogic": "all"},
        ]
        rejected = client.post("/api/forms", json=bad, headers=csrf_headers(client))
        assert rejected.status_code == 422, rejected.text
        assert rejected.json()["detail"]["code"] == "invalid_condition_value"


def test_multi_option_labels_and_selection_limits_are_validated(configured_client):
    client, _ = configured_client
    login(client)

    payload = valid_form()
    payload["fields"] = [{
        "id": "multi-answer",
        "t": "multi",
        "l": "چندانتخابی",
        "options": [" الف ", "ب", "پ"],
        "minSelect": 2,
        "maxSelect": 3,
    }]
    response = client.post(
        "/api/forms",
        json=payload,
        headers=create_headers(client, "multi-options-create-key-0001"),
    )
    assert response.status_code == 201, response.text
    field = response.json()["fields"][0]
    assert field["options"] == ["الف", "ب", "پ"]
    assert field["minSelect"] == 2 and field["maxSelect"] == 3

    unicode_length = valid_form()
    unicode_length["slug"] = "tests/emoji-option-length"
    unicode_length["fields"] = [{
        "id": "multi-answer", "t": "multi", "l": "برچسب ایموجی", "options": ["🙂" * 120],
    }]
    accepted_unicode_length = client.post(
        "/api/forms",
        json=unicode_length,
        headers=create_headers(client, "multi-options-unicode-length-key-0001"),
    )
    assert accepted_unicode_length.status_code == 201, accepted_unicode_length.text
    assert len(accepted_unicode_length.json()["fields"][0]["options"][0]) == 120

    hundred_options = valid_form()
    hundred_options["slug"] = "tests/multi-100-options"
    hundred_options["fields"] = [{
        "id": "multi-answer",
        "t": "multi",
        "l": "حداکثر گزینه‌ها",
        "opts": [f"گزینه {i}" for i in range(100)],
        "maxSelect": 100,
    }]
    accepted_hundred = client.post(
        "/api/forms",
        json=hundred_options,
        headers=create_headers(client, "multi-options-hundred-key-0001"),
    )
    assert accepted_hundred.status_code == 201, accepted_hundred.text
    assert len(accepted_hundred.json()["fields"][0]["opts"]) == 100

    invalid_cases = [
        ("options_required", [], {}),
        ("invalid_options", "not a list", {}),
        ("invalid_option", ["الف", "  "], {}),
        ("invalid_option", ["x" * 121], {}),
        ("invalid_option", ["🙂" * 121], {}),
        ("invalid_option", [chr(9) + "الف"], {}),
        ("invalid_option", [chr(0x85) + "الف"], {}),
        ("invalid_option", [chr(0xD800) + "الف"], {}),
        ("duplicate_option", ["A", " a "], {}),
        ("duplicate_option", ["Straße", "STRASSE"], {}),
        ("duplicate_option", ["Σ", "ς"], {}),
        ("duplicate_option", [chr(0xFEFF) + "A" + chr(0xFEFF), "a"], {}),
        ("duplicate_option", ["Café", "Cafe\u0301"], {}),
        ("too_many_options", [f"گزینه {i}" for i in range(101)], {}),
        ("invalid_selection_limits", ["الف", "ب", "پ"], {"minSelect": 0}),
        ("invalid_selection_limits", ["الف", "ب", "پ"], {"minSelect": True}),
        ("invalid_selection_limits", ["الف", "ب", "پ"], {"minSelect": 1.5}),
        ("invalid_selection_limits", ["الف", "ب", "پ"], {"minSelect": "2"}),
        ("invalid_selection_limits", ["الف", "ب", "پ"], {"maxSelect": 4}),
        ("invalid_selection_limits", ["الف", "ب", "پ"], {"minSelect": 2, "maxSelect": 1}),
    ]
    for index, (expected_code, options, limits) in enumerate(invalid_cases):
        bad = valid_form()
        bad["fields"] = [{
            "id": "multi-answer",
            "t": "multi",
            "l": "چندانتخابی",
            "options": options,
            **limits,
        }]
        rejected = client.post(
            "/api/forms",
            content=json.dumps(bad, ensure_ascii=True).encode("utf-8"),
            headers={**csrf_headers(client), "Content-Type": "application/json"},
        )
        assert rejected.status_code == 422, f"case {index}: {rejected.text}"
        assert rejected.json()["detail"]["code"] == expected_code

    wrong_type = valid_form()
    wrong_type["fields"] = [{"id": "text-answer", "t": "text", "l": "متن", "minSelect": 1}]
    rejected = client.post("/api/forms", json=wrong_type, headers=csrf_headers(client))
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "invalid_selection_limits"


def test_api_round_trips_compound_conditions_and_rejects_invalid_rules(configured_client):
    client, _ = configured_client
    login(client)
    fields = [
        {"id": "text-source", "t": "text", "l": "پاسخ متنی"},
        {"id": "number-source", "t": "number", "l": "پاسخ عددی"},
        {"id": "choice-source", "t": "select", "l": "گزینهٔ مرجع legacy", "options": ["الف", "ب"]},
        {
            "id": "conditional",
            "t": "text",
            "l": "پرسش وابسته",
            "conditionLogic": "any",
            "conditions": [
                {"field": "text-source", "op": "starts", "value": "سلام"},
                {"field": "number-source", "op": "gte", "value": "۰"},
                {"field": "number-source", "op": "gt", "value": "١٫٥"},
                {"field": "choice-source", "op": "eq", "value": "الف"},
            ],
        },
    ]
    payload = valid_form()
    payload["fields"] = fields
    response = client.post("/api/forms", json=payload, headers=create_headers(client))
    assert response.status_code == 201, response.text
    condition = response.json()["fields"][3]
    assert condition["conditionLogic"] == "any"
    assert condition["conditions"] == [
        {"field": "text-source", "op": "starts", "value": "سلام"},
        {"field": "number-source", "op": "gte", "value": "۰"},
        {"field": "number-source", "op": "gt", "value": "١٫٥"},
        {"field": "choice-source", "op": "eq", "value": "الف"},
    ]
    assert condition["condField"] == "" and condition["condOp"] == "eq" and condition["condVal"] == ""

    update_payload = {**payload, "expected_version": 1}
    updated = client.put(
        f"/api/forms/{response.json()['id']}",
        json=update_payload,
        headers=csrf_headers(client),
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["fields"][3]["conditionLogic"] == "any"
    assert updated.json()["fields"][3]["conditions"] == condition["conditions"]

    ten_rules = valid_form()
    ten_rules["fields"] = fields[:3] + [{
        "id": "conditional",
        "t": "text",
        "l": "ده قاعده",
        "conditionLogic": "all",
        "conditions": [{"field": "text-source", "op": "eq", "value": "سلام"}] * 10,
    }]
    accepted_ten = client.post(
        "/api/forms",
        json=ten_rules,
        headers=create_headers(client, "compound-condition-ten-rules-0001"),
    )
    assert accepted_ten.status_code == 201, accepted_ten.text
    assert len(accepted_ten.json()["fields"][3]["conditions"]) == 10

    invalid_cases = [
        ("invalid_condition_logic", [{"field": "text-source", "op": "eq", "value": "سلام"}], "xor"),
        ("invalid_condition_logic", [{"field": "text-source", "op": "eq", "value": "سلام"}], {"mode": "all"}),
        ("invalid_condition_order", [{"field": "conditional", "op": "eq", "value": "x"}], "all"),
        ("invalid_condition_value", [{"field": "number-source", "op": "gt", "value": "عدد"}], "all"),
        ("invalid_condition_value", [{"field": "choice-source", "op": "eq", "value": "گزینهٔ ناموجود"}], "all"),
        ("invalid_condition_operator", [{"field": "number-source", "op": "contains", "value": "x"}], "all"),
        ("too_many_condition_rules", [{"field": "text-source", "op": "eq", "value": "x"}] * 11, "all"),
    ]
    for expected_code, rules, logic in invalid_cases:
        bad = valid_form()
        bad["fields"] = fields[:3] + [{
            "id": "conditional",
            "t": "text",
            "l": "شرط",
            "conditions": rules,
            "conditionLogic": logic,
        }]
        rejected = client.post("/api/forms", json=bad, headers=csrf_headers(client))
        assert rejected.status_code == 422, rejected.text
        assert rejected.json()["detail"]["code"] == expected_code


def test_validation_rejects_secrets_bad_conditions_and_invalid_models(configured_client):
    client, _ = configured_client
    login(client)
    headers = csrf_headers(client)

    cases = []
    secret = valid_form()
    secret["settings"]["bot_token"] = "never-store-this"
    cases.append((secret, "credentials_not_accepted"))

    invalid_model = valid_form()
    invalid_model["model"] = "external-payment"
    cases.append((invalid_model, "invalid_model"))

    condition = valid_form()
    condition["fields"][0]["condField"] = "city"
    cases.append((condition, "invalid_condition_order"))

    duplicate = valid_form()
    duplicate["fields"].append({"id": "city", "t": "text", "l": "تکراری"})
    cases.append((duplicate, "duplicate_field_id"))

    for payload, expected_code in cases:
        response = client.post("/api/forms", json=payload, headers=headers)
        assert response.status_code == 422, response.text
        assert response.json()["detail"]["code"] == expected_code


def test_origin_and_payload_size_guards(configured_client):
    client, _ = configured_client
    login(client)

    wrong_origin = client.post(
        "/api/forms", json=valid_form(),
        headers={"Origin": "https://evil.example", "X-CSRF-Token": client.cookies.get("nora_csrf", "")},
    )
    assert wrong_origin.status_code == 403

    oversized = client.post(
        "/api/forms",
        content=b"{" + b" " * (64 * 1024 + 4) + b"}",
        headers={
            "Origin": "http://testserver",
            "X-CSRF-Token": client.cookies.get("nora_csrf", ""),
            "Content-Type": "application/json",
        },
    )
    assert oversized.status_code == 413


def test_cooperation_requests_are_durable_and_owner_only(configured_client):
    client, _ = configured_client
    payload = {
        "name": "مریم رضایی",
        "organization": "گروه فرهنگی",
        "contact": "+33 6 12 34 56 78",
        "kind": "institution",
        "message": "برای برگزاری یک کارگاه مشترک مایل به گفت‌وگو هستیم.",
        "website": "",
    }
    created = client.post(
        "/api/public/cooperation-requests",
        json=payload,
        headers={"Origin": "http://testserver"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["received"] is True
    assert created.json()["id"]
    assert client.get("/api/cooperation-requests").status_code == 401

    login(client)
    inbox = client.get("/api/cooperation-requests?limit=20&offset=0")
    assert inbox.status_code == 200
    assert inbox.json()["total"] == 1
    item = inbox.json()["items"][0]
    assert item["name"] == payload["name"]
    assert item["organization"] == payload["organization"]
    assert item["contact"] == payload["contact"]
    assert item["kind"] == "institution"
    assert item["status"] == "new"
    assert client.patch(
        f"/api/cooperation-requests/{item['id']}",
        json={"status": "reviewing"},
        headers=csrf_headers(client),
    ).json() == {"id": item["id"], "status": "reviewing"}


def test_cooperation_request_validates_origin_payload_and_honeypot(configured_client):
    client, _ = configured_client
    payload = {
        "name": "نام معتبر",
        "organization": "",
        "contact": "person@example.org",
        "kind": "teaching",
        "message": "درخواست همکاری آموزشی برای دورهٔ آینده.",
        "website": "",
    }
    wrong_origin = client.post(
        "/api/public/cooperation-requests",
        json=payload,
        headers={"Origin": "https://attacker.example"},
    )
    assert wrong_origin.status_code == 403

    invalid = dict(payload, contact="شماره یا ایمیل")
    assert client.post(
        "/api/public/cooperation-requests",
        json=invalid,
        headers={"Origin": "http://testserver"},
    ).status_code == 422

    spam = dict(payload, website="https://spam.example")
    acknowledged = client.post(
        "/api/public/cooperation-requests",
        json=spam,
        headers={"Origin": "http://testserver"},
    )
    assert acknowledged.status_code == 201
    assert acknowledged.json()["received"] is True
    login(client)
    assert client.get("/api/cooperation-requests").json()["total"] == 0


def test_health_and_outbox_do_not_claim_real_delivery(configured_client):
    client, _ = configured_client
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["formsEnabled"] is True
    assert health.json()["deliveryEnabled"] is False

    status = client.get("/api/integrations/status").json()
    assert status["deliveryEnabled"] is False
    assert {item["id"]: item["connectionModel"] for item in status["providers"]} == {
        "bale": "bot-token-plus-mini-app",
        "eitaa": "mini-app-only",
    }

    outbox = client.post("/api/outbox", json={"kind": "certificate", "channel": "bale"})
    assert outbox.status_code == 409
    assert outbox.json()["queued"] is False
    assert outbox.json()["dispatched"] is False
    assert outbox.json()["sendAttempted"] is False


def test_static_ui_is_served_but_backend_and_secrets_are_not(configured_client):
    client, _ = configured_client
    home = client.get("/")
    assert home.status_code == 200
    assert "نورا" in home.text
    assert client.get("/create.html").status_code == 200
    assert client.get("/backend/app.py").status_code == 404
    assert client.get("/.env").status_code == 404
    assert client.get("/backend/requirements.txt").status_code == 404


def test_static_assets_are_compressed_and_version_cached(configured_client):
    client, _ = configured_client
    script = client.get("/admin.js?v=98", headers={"Accept-Encoding": "gzip"})
    assert script.status_code == 200
    assert script.headers.get("content-encoding") == "gzip"
    assert script.headers.get("cache-control") == "public, max-age=31536000, immutable"
    assert "accept-encoding" in script.headers.get("vary", "").lower()
    assert "NORA" in script.text

    page = client.get("/home.html")
    assert page.headers.get("cache-control") == "no-cache, max-age=0, must-revalidate"
    health = client.get("/api/health")
    assert health.headers.get("cache-control") == "no-store"


def test_bot_public_form_catalog_requires_service_auth_and_lists_only_published_forms(
    configured_client,
):
    client, settings = configured_client
    assert client.get("/api/bot/forms/public").status_code == 401
    assert client.get(
        "/api/bot/forms/public", headers={"Authorization": "Bearer wrong-token"}
    ).status_code == 401

    login(client)
    published = client.post("/api/forms", json=valid_form(), headers=create_headers(client))
    assert published.status_code == 201, published.text
    form_id = published.json()["id"]
    assert client.post(
        f"/api/forms/{form_id}/publish",
        json={"expected_version": 1},
        headers=csrf_headers(client),
    ).status_code == 200

    draft_payload = valid_form()
    draft_payload["slug"] = "workshops/unpublished"
    draft_payload["name"] = "پیش‌نویس پنهان"
    draft = client.post(
        "/api/forms", json=draft_payload, headers=create_headers(client, "draft-catalog-key-0001")
    )
    assert draft.status_code == 201, draft.text

    response = client.get(
        "/api/bot/forms/public",
        headers={"Authorization": "Bearer " + settings.bot_service_token},
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("cache-control") == "no-store"
    result = response.json()
    assert result["source"] == "shared_server_database"
    assert len(result["items"]) == 1
    assert result["items"][0] == {
        "id": form_id,
        "name": "ثبت نام کارگاه",
        "model": "registration",
        "need": "reg",
        "version": 2,
    }
    assert "fields" not in result["items"][0]
    assert "settings" not in result["items"][0]


def test_bot_conversation_saves_shared_draft_and_submission_is_idempotent(configured_client):
    client, settings = configured_client
    service_headers = {"Authorization": "Bearer " + settings.bot_service_token}
    owner_route = client.post("/api/forms", json=valid_form(), headers=service_headers)
    assert owner_route.status_code == 401  # service auth cannot create owner forms

    login(client)
    payload = valid_form()
    payload["settings"]["ticketing"] = {
        "mode": "single",
        "types": [{"id": "standard", "name": "ورودی استاندارد"}],
    }
    created = client.post("/api/forms", json=payload, headers=create_headers(client))
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    published = client.post(
        f"/api/forms/{form_id}/publish",
        json={"expected_version": 1},
        headers=csrf_headers(client),
    )
    assert published.status_code == 200, published.text

    identity = {"bale_user_id": "73421", "session_key": "s" * 43}
    endpoint = f"/api/bot/forms/{form_id}"
    assert client.post(endpoint + "/draft", json=identity).status_code == 401
    started = client.post(endpoint + "/draft", json=identity, headers=service_headers)
    assert started.status_code == 200, started.text
    initial = started.json()
    assert initial["source"] == "shared_server_database"
    assert initial["draft"] == {
        "answers": {}, "submitted": False, "status": "draft", "form_version": 2,
    }
    assert initial["visible_field_ids"] == ["full-name"]
    wrong_user = client.post(
        endpoint + "/draft/state",
        json={"bale_user_id": "73422", "session_key": identity["session_key"]},
        headers=service_headers,
    )
    assert wrong_user.status_code == 404
    invalid_session = client.post(
        endpoint + "/draft/state",
        json={"bale_user_id": "73421", "session_key": "short"},
        headers=service_headers,
    )
    assert invalid_session.status_code == 422

    saved_name = client.patch(
        endpoint + "/draft",
        json={**identity, "field_id": "full-name", "value": "لیلا"},
        headers=service_headers,
    )
    assert saved_name.status_code == 200, saved_name.text
    assert saved_name.json()["visible_field_ids"] == ["full-name", "city"]
    assert saved_name.json()["draft"]["answers"] == {"full-name": "لیلا"}

    saved_city = client.patch(
        endpoint + "/draft",
        json={**identity, "field_id": "city", "value": "تهران"},
        headers=service_headers,
    )
    assert saved_city.status_code == 200, saved_city.text
    assert saved_city.json()["draft"]["answers"] == {"full-name": "لیلا", "city": "تهران"}

    submitted = client.post(endpoint + "/responses", json=identity, headers=service_headers)
    assert submitted.status_code == 200, submitted.text
    first_response_id = submitted.json()["response_id"]
    assert submitted.json()["accepted"] is True
    assert submitted.json()["already_submitted"] is False
    assert submitted.json()["status"] == "accepted"
    ticket_path = f"/api/bot/forms/{form_id}/responses/{first_response_id}/ticket"
    assert client.post(
        ticket_path,
        json={"bale_user_id": "73422"},
        headers=service_headers,
    ).status_code == 404
    ticket = client.post(
        ticket_path,
        json={"bale_user_id": "73421"},
        headers=service_headers,
    )
    assert ticket.status_code == 200, ticket.text
    assert ticket.headers.get("cache-control") == "no-store"
    assert ticket.json()["source"] == "shared_server_database"
    assert ticket.json()["response_id"] == first_response_id
    assert ticket.json()["serial"].startswith("NORA-")
    assert ticket.json()["participant_name"] == "لیلا"
    assert ticket.json()["event_title"] == "ثبت نام کارگاه"
    assert ticket.json()["ticket_type"] == {
        "id": "standard", "name": "ورودی استاندارد",
    }
    assert ticket.json()["event_date"] == ""
    assert ticket.json()["event_time"] == ""
    assert "answers" not in ticket.json()

    retried = client.post(endpoint + "/responses", json=identity, headers=service_headers)
    assert retried.status_code == 200, retried.text
    assert retried.json()["already_submitted"] is True
    assert retried.json()["response_id"] == first_response_id
    retried_ticket = client.post(ticket_path, json={"bale_user_id": "73421"}, headers=service_headers)
    assert retried_ticket.status_code == 200
    assert retried_ticket.json()["ticket_type"] == ticket.json()["ticket_type"]
    delete_submitted = client.request(
        "DELETE", endpoint + "/draft", json=identity, headers=service_headers
    )
    assert delete_submitted.status_code == 200
    assert delete_submitted.json() == {"deleted": False, "submitted": True}

    recovered = client.post(endpoint + "/draft", json=identity, headers=service_headers)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["draft"]["submitted"] is True
    assert recovered.json()["draft"]["answers"] == {"full-name": "لیلا", "city": "تهران"}

    rows = client.get(f"/api/forms/{form_id}/responses")
    assert rows.status_code == 200
    assert rows.json()["total"] == 1
    assert rows.json()["items"][0]["answers"] == {"full-name": "لیلا", "city": "تهران"}

    history_path = "/api/bot/forms/mine"
    assert client.get(history_path, params={"bale_user_id": "73421"}).status_code == 401
    history = client.get(
        history_path,
        params={"bale_user_id": "73421", "page": 0},
        headers=service_headers,
    )
    assert history.status_code == 200, history.text
    assert history.headers.get("cache-control") == "no-store"
    history_data = history.json()
    assert history_data["source"] == "shared_server_database"
    assert history_data["total"] == 1 and history_data["page"] == 0
    assert history_data["items"] == [{
        "id": first_response_id,
        "form_id": form_id,
        "form_name": "ثبت نام کارگاه",
        "status": "accepted",
        "form_version": 2,
        "answer_count": 2,
        "created_at": history_data["items"][0]["created_at"],
    }]
    assert client.get(
        history_path,
        params={"bale_user_id": "73422"},
        headers=service_headers,
    ).json()["items"] == []

    detail_path = f"/api/bot/forms/responses/{first_response_id}"
    assert client.get(
        detail_path,
        params={"bale_user_id": "73422"},
        headers=service_headers,
    ).status_code == 404
    detail = client.get(
        detail_path,
        params={"bale_user_id": "73421"},
        headers=service_headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.headers.get("cache-control") == "no-store"
    assert detail.json()["source"] == "shared_server_database"
    assert detail.json()["response"]["answers"] == {
        "full-name": "لیلا", "city": "تهران"
    }
    assert detail.json()["response"]["form_snapshot"]["name"] == "ثبت نام کارگاه"

    manager_user_id = "73423"
    manager_account_id = "manager-account-01"
    with client.app.state.session_factory() as db:
        db.add(AccountRecord(id=manager_account_id))
        db.add(PlatformIdentityRecord(
            id="123e4567-e89b-12d3-a456-426614174002",
            account_id=manager_account_id,
            provider="bale",
            provider_user_id=manager_user_id,
        ))
        db.add(AccountRoleRecord(
            account_id=manager_account_id,
            role="manager",
            assigned_by="owner-01",
        ))
        db.commit()

    admin_forms_path = "/api/bot/admin/forms"
    admin_params = {"bale_user_id": manager_user_id, "page": 0}
    assert client.get(admin_forms_path, params=admin_params).status_code == 401
    admin_forms = client.get(admin_forms_path, params=admin_params, headers=service_headers)
    assert admin_forms.status_code == 200, admin_forms.text
    assert admin_forms.headers.get("cache-control") == "no-store"
    assert admin_forms.json()["items"] == [{
        "id": form_id,
        "name": "ثبت نام کارگاه",
        "status": "published",
        "version": 2,
        "response_count": 1,
    }]
    denied_forms = client.get(
        admin_forms_path,
        params={"bale_user_id": "73422"},
        headers=service_headers,
    )
    assert denied_forms.status_code == 403

    admin_response_list = client.get(
        f"/api/bot/admin/forms/{form_id}/responses",
        params=admin_params,
        headers=service_headers,
    )
    assert admin_response_list.status_code == 200, admin_response_list.text
    assert admin_response_list.headers.get("cache-control") == "no-store"
    assert admin_response_list.json()["total"] == 1
    assert admin_response_list.json()["items"][0]["id"] == first_response_id
    assert "answers" not in admin_response_list.json()["items"][0]

    admin_response = client.get(
        f"/api/bot/admin/responses/{first_response_id}",
        params={"bale_user_id": manager_user_id},
        headers=service_headers,
    )
    assert admin_response.status_code == 200, admin_response.text
    assert admin_response.headers.get("cache-control") == "no-store"
    assert admin_response.json()["response"]["answers"] == {
        "full-name": "لیلا", "city": "تهران"
    }
    denied_response = client.get(
        f"/api/bot/admin/responses/{first_response_id}",
        params={"bale_user_id": "73422"},
        headers=service_headers,
    )
    assert denied_response.status_code == 403


def test_bot_multi_select_allows_partial_saving_but_checks_final_min_and_max(configured_client):
    client, settings = configured_client
    login(client)
    payload = valid_form()
    payload["fields"] = [
        {"id": "full-name", "t": "text", "l": "نام کامل", "required": True},
        {
            "id": "topics", "t": "multi", "l": "موضوع‌ها",
            "options": ["هنر", "ورزش", "علم"], "required": True,
            "minSelect": 2, "maxSelect": 2,
        },
    ]
    created = client.post("/api/forms", json=payload, headers=create_headers(client))
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    published = client.post(
        f"/api/forms/{form_id}/publish",
        json={"expected_version": 1},
        headers=csrf_headers(client),
    )
    assert published.status_code == 200, published.text
    headers = {"Authorization": "Bearer " + settings.bot_service_token}
    endpoint = f"/api/bot/forms/{form_id}"
    identity = {"bale_user_id": "73422", "session_key": "m" * 43}
    assert client.post(endpoint + "/draft", json=identity, headers=headers).status_code == 200
    assert client.patch(
        endpoint + "/draft",
        json={**identity, "field_id": "full-name", "value": "سارا"},
        headers=headers,
    ).status_code == 200

    one_choice = client.patch(
        endpoint + "/draft",
        json={**identity, "field_id": "topics", "value": ["هنر"]},
        headers=headers,
    )
    assert one_choice.status_code == 200, one_choice.text
    assert one_choice.json()["draft"]["answers"]["topics"] == ["هنر"]

    too_many = client.patch(
        endpoint + "/draft",
        json={**identity, "field_id": "topics", "value": ["هنر", "ورزش", "علم"]},
        headers=headers,
    )
    assert too_many.status_code == 422
    not_enough = client.post(endpoint + "/responses", json=identity, headers=headers)
    assert not_enough.status_code == 422
    assert not_enough.json()["detail"]["errors"][0]["field_id"] == "topics"

    two_choices = client.patch(
        endpoint + "/draft",
        json={**identity, "field_id": "topics", "value": ["هنر", "ورزش"]},
        headers=headers,
    )
    assert two_choices.status_code == 200, two_choices.text
    submitted = client.post(endpoint + "/responses", json=identity, headers=headers)
    assert submitted.status_code == 200, submitted.text
    assert client.get(f"/api/forms/{form_id}/responses").json()["total"] == 1


def test_publish_public_form_persist_and_recover_anonymous_response(configured_client):
    client, settings = configured_client
    login(client)
    created = client.post("/api/forms", json=valid_form(), headers=create_headers(client))
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]

    assert client.get(f"/api/public/forms/{form_id}").status_code == 404
    no_csrf = client.post(
        f"/api/forms/{form_id}/publish",
        json={"expected_version": 1},
        headers={"Origin": "http://testserver"},
    )
    assert no_csrf.status_code == 403

    published = client.post(
        f"/api/forms/{form_id}/publish",
        json={"expected_version": 1},
        headers=csrf_headers(client),
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    assert published.json()["version"] == 2

    public = client.get(f"/api/public/forms/{form_id}")
    assert public.status_code == 200, public.text
    public_data = public.json()
    assert public_data["id"] == form_id
    assert public_data["name"] == "ثبت نام کارگاه"
    assert public_data["fields"][0]["id"] == "full-name"
    assert public_data["profilePrefill"] is False
    assert public_data["onePerPerson"] is False
    assert "owner_id" not in public_data
    assert "description" not in public_data["settings"]

    page = client.get(f"/form.html?fid={form_id}&kind=reg")
    assert page.status_code == 200
    assert 'id="nora-public-form-data"' in page.text
    assert '"status":"published"' in page.text
    assert 'id="nora-public-draft-data">null' in page.text

    initial_draft = client.get(f"/api/public/forms/{form_id}/draft")
    assert initial_draft.status_code == 200
    draft_cookie = next(cookie for cookie in client.cookies.jar if cookie.name.startswith("nora_response_draft_"))
    assert draft_cookie.has_nonstandard_attr("HttpOnly")
    assert draft_cookie.get_nonstandard_attr("SameSite") == "strict"
    assert initial_draft.json() == {
        "answers": {}, "companions": [], "submitted": False, "status": "draft", "tracking_code": None,
        "ticket_type": None, "receipt_uploaded": False, "payment_intent": None, "form_version": 2,
    }

    partial = client.patch(
        f"/api/public/forms/{form_id}/draft",
        json={"answers": {"full-name": "لیلا"}},
        headers={"Origin": "http://testserver"},
    )
    assert partial.status_code == 200, partial.text
    assert partial.json()["saved"] is True
    recovered = client.get(f"/api/public/forms/{form_id}/draft")
    assert recovered.json()["answers"] == {"full-name": "لیلا"}

    cross_origin = client.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": {"full-name": "لیلا"}},
        headers={"Origin": "https://attacker.example"},
    )
    assert cross_origin.status_code == 403

    missing_required = client.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": {"city": "تهران"}},
        headers={"Origin": "http://testserver"},
    )
    assert missing_required.status_code == 422
    assert missing_required.json()["detail"]["errors"][0]["field_id"] == "full-name"

    answer = {"full-name": "لیلا", "city": "پاریس"}
    submitted = client.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": answer},
        headers={"Origin": "http://testserver"},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["accepted"] is True
    assert submitted.json()["status"] == "accepted"
    assert submitted.json()["tracking_code"].startswith("NORA-")
    assert submitted.json()["message"] == "اطلاعاتت ثبت شد."

    recovered = client.get(f"/api/public/forms/{form_id}/draft")
    assert recovered.json()["submitted"] is True
    assert recovered.json()["answers"] == answer
    assert recovered.json()["tracking_code"] == submitted.json()["tracking_code"]

    unauthenticated = TestClient(client.app)
    assert unauthenticated.get(f"/api/forms/{form_id}/responses").status_code == 401
    owner_rows = client.get(f"/api/forms/{form_id}/responses")
    assert owner_rows.status_code == 200
    assert owner_rows.json()["total"] == 1
    assert owner_rows.json()["items"][0]["answers"] == answer
    assert owner_rows.json()["items"][0]["form_snapshot"]["version"] == 2

    # The same anonymous capability updates its one response rather than creating a duplicate.
    revised = {"full-name": "لیلا رضایی", "city": "تهران"}
    retry = client.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": revised},
        headers={"Origin": "http://testserver"},
    )
    assert retry.status_code == 200, retry.text
    assert client.get(f"/api/forms/{form_id}/responses").json()["total"] == 1
    assert client.get(f"/api/forms/{form_id}/responses").json()["items"][0]["answers"] == revised
    anonymous_not_in_bot_history = client.get(
        "/api/bot/forms/mine",
        params={"bale_user_id": "73421"},
        headers={"Authorization": "Bearer " + settings.bot_service_token},
    )
    assert anonymous_not_in_bot_history.status_code == 200
    assert anonymous_not_in_bot_history.json()["items"] == []

    paused = client.post(
        f"/api/forms/{form_id}/pause",
        json={"expected_version": 2},
        headers=csrf_headers(client),
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert client.get(f"/api/public/forms/{form_id}").status_code == 404
    stopped = client.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": revised},
        headers={"Origin": "http://testserver"},
    )
    assert stopped.status_code == 409

    locked = valid_form()
    locked["expected_version"] = 3
    locked["name"] = "تغییر پس از پاسخ"
    update = client.put(f"/api/forms/{form_id}", json=locked, headers=csrf_headers(client))
    assert update.status_code == 409
    assert update.json()["detail"]["code"] == "form_has_responses"

    deleted = client.delete(
        f"/api/forms/{form_id}/responses/{owner_rows.json()['items'][0]['id']}",
        headers=csrf_headers(client),
    )
    assert deleted.status_code == 200
    assert client.get(f"/api/forms/{form_id}/responses").json()["total"] == 0


def test_web_account_registration_history_is_session_scoped_and_does_not_guess_old_records(configured_client):
    owner, _settings = configured_client
    login(owner)
    created = owner.post("/api/forms", json=valid_form(), headers=create_headers(owner))
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    published = owner.post(
        f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=csrf_headers(owner)
    )
    assert published.status_code == 200, published.text

    # A guest registration with the same name must not be guessed into any web account.
    guest = TestClient(owner.app)
    assert guest.get(f"/api/public/forms/{form_id}/draft").status_code == 200
    guest_response = guest.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": {"full-name": "لیلا رضایی"}},
        headers=ORIGIN,
    )
    assert guest_response.status_code == 200, guest_response.text

    account_id = str(uuid.uuid4())
    web = TestClient(owner.app)
    install_web_account_session(web, account_id)
    assert web.get(f"/api/public/forms/{form_id}/draft").status_code == 200
    web_response = web.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": {"full-name": "لیلا رضایی"}},
        headers=ORIGIN,
    )
    assert web_response.status_code == 200, web_response.text

    with owner.app.state.session_factory() as db:
        drafts = db.scalars(
            select(FormResponseDraftRecord).where(FormResponseDraftRecord.form_id == form_id)
        ).all()
        assert sorted(draft.account_id or "" for draft in drafts) == sorted(["", account_id])

    anonymous = TestClient(owner.app)
    assert anonymous.get("/api/account/registrations").status_code == 401
    history = web.get("/api/account/registrations?limit=1&offset=0")
    assert history.status_code == 200, history.text
    assert history.headers.get("cache-control") == "no-store"
    assert history.headers.get("vary") == "Cookie"
    result = history.json()
    assert result["source"] == "shared_server_database"
    assert result["total"] == 1 and result["has_more"] is False
    item = result["items"][0]
    assert item["form_name"] == "ثبت نام کارگاه"
    assert item["event_title"] == "ثبت نام کارگاه"
    assert item["status"] == "accepted"
    assert not {"answers", "registrant_name", "registrant_mobile", "account_id"} & set(item)
    assert "لیلا رضایی" not in history.text
    assert web.get("/api/account/registrations?limit=1&offset=1").json()["items"] == []

    other = TestClient(owner.app)
    install_web_account_session(other, str(uuid.uuid4()))
    assert other.get(
        "/api/account/registrations?account_id=" + account_id
    ).json()["items"] == []
    draft_cookie = next(
        cookie for cookie in web.cookies.jar
        if cookie.name.startswith("nora_response_draft_")
    )
    other.cookies.set(draft_cookie.name, draft_cookie.value, path=draft_cookie.path)
    stolen_draft = other.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": {"full-name": "لیلا رضایی"}},
        headers=ORIGIN,
    )
    assert stolen_draft.status_code == 409
    assert stolen_draft.json()["detail"]["code"] == "response_draft_account_mismatch"
    assert web.get("/api/account/registrations").json()["total"] == 1


def test_public_registration_ticket_handoff_is_opaque_claimed_in_bale_and_checked_in_once(  # noqa: PLR0915
    configured_client, monkeypatch,
):
    owner, settings = configured_client
    random_choices = []

    def choose_ticket_type(types):
        random_choices.append([dict(item) for item in types])
        return types[1]

    monkeypatch.setattr(response_helpers.secrets, "choice", choose_ticket_type)
    owner.app.state.settings = replace(
        settings, bale_bot_username="nora_test_bot", owner_bale_user_id="99999"
    )
    login(owner)
    payload = valid_form()
    payload["settings"]["ticketing"] = {
        "mode": "random",
        "types": [
            {"id": "standard", "name": "ورودی استاندارد"},
            {"id": "priority", "name": "ورودی ویژه"},
            {"id": "guest", "name": "مهمان"},
        ],
    }
    created = owner.post("/api/forms", json=payload, headers=create_headers(owner))
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    published = owner.post(
        f"/api/forms/{form_id}/publish",
        json={"expected_version": 1},
        headers=csrf_headers(owner),
    )
    assert published.status_code == 200, published.text
    event_update = owner.patch(
        "/api/owner/site-content",
        json={"content": {"events": [{
            "id": "event-2026-01", "t": "کارگاه فرهنگ ایرانی", "privacy": "public",
            "when": "2026-11-13", "time": "۱۶:۳۰ تا ۱۹:۰۰", "place": "تهران",
        }]}, "expected_version": 0},
        headers=csrf_headers(owner),
    )
    assert event_update.status_code == 200, event_update.text

    visitor = TestClient(owner.app)
    assert visitor.get(f"/form.html?fid={form_id}").status_code == 200
    public_form = visitor.get(f"/api/public/forms/{form_id}")
    assert public_form.status_code == 200, public_form.text
    assert "ticketing" not in public_form.json() and "ticketing" not in public_form.json()["settings"]
    initial_draft = visitor.get(f"/api/public/forms/{form_id}/draft")
    assert initial_draft.status_code == 200 and initial_draft.json()["ticket_type"] is None
    origin = {"Origin": "http://testserver"}
    not_submitted = visitor.post(
        f"/api/public/forms/{form_id}/ticket-link", json={}, headers=origin
    )
    assert not_submitted.status_code == 409
    anonymous_image = TestClient(owner.app).get(f"/api/public/forms/{form_id}/ticket-image")
    assert anonymous_image.status_code == 401
    not_issued_image = visitor.get(f"/api/public/forms/{form_id}/ticket-image")
    assert not_issued_image.status_code == 409
    assert not_issued_image.json()["detail"]["code"] == "ticket_response_not_submitted"
    submitted = visitor.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": {"full-name": "لیلا رضایی"}},
        headers=origin,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "accepted"
    expected_ticket_type = {"id": "priority", "name": "ورودی ویژه"}
    assert submitted.json()["ticket_type"] == expected_ticket_type
    assert random_choices == [payload["settings"]["ticketing"]["types"]]
    assert "response_id" not in submitted.json() and "ticket" not in submitted.json()
    recovered_draft = visitor.get(f"/api/public/forms/{form_id}/draft")
    assert recovered_draft.status_code == 200
    assert recovered_draft.json()["ticket_type"] == expected_ticket_type
    retry = visitor.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": {"full-name": "لیلا رضایی ویرایش‌شده"}},
        headers=origin,
    )
    assert retry.status_code == 200 and retry.json()["ticket_type"] == expected_ticket_type
    assert random_choices == [payload["settings"]["ticketing"]["types"]]

    rendered_images = []
    monkeypatch.setattr(
        backend_app,
        "_render_public_form_ticket_image",
        lambda data: rendered_images.append(dict(data)) or b"shared ticket image",
    )
    preview = visitor.get(f"/api/public/forms/{form_id}/ticket-image")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/jpeg"
    assert preview.headers["content-disposition"].startswith("inline;")
    assert preview.headers["cache-control"] == "no-store"
    assert preview.headers["vary"] == "Cookie"
    assert preview.headers["x-content-type-options"] == "nosniff"
    assert preview.content == b"shared ticket image"
    download = visitor.get(f"/api/public/forms/{form_id}/ticket-image?download=1")
    assert download.status_code == 200 and download.content == preview.content
    assert download.headers["content-disposition"].startswith("attachment;")
    response_id = owner.get(f"/api/forms/{form_id}/responses").json()["items"][0]["id"]
    assert rendered_images[0]["ticket_type_name"] == expected_ticket_type["name"]
    assert rendered_images[0]["name"] == "لیلا رضایی ویرایش‌شده"
    assert rendered_images[0]["serial"] == submitted.json()["tracking_code"]
    assert rendered_images[0]["qr_data"] == f"https://ble.ir/nora_test_bot?start=ftv_{response_id}"
    # The web service names the organization itself instead of reading the Bale bot settings DB.
    assert rendered_images[0]["organization"] == backend_app.ORGANIZATION_NAME
    assert rendered_images[0] == rendered_images[1]
    assert random_choices == [payload["settings"]["ticketing"]["types"]]

    wrong_origin = visitor.post(
        f"/api/public/forms/{form_id}/ticket-link",
        json={},
        headers={"Origin": "https://attacker.example"},
    )
    assert wrong_origin.status_code == 403
    link = visitor.post(f"/api/public/forms/{form_id}/ticket-link", json={}, headers=origin)
    assert link.status_code == 200, link.text
    assert link.headers.get("cache-control") == "no-store"
    assert set(link.json()) == {"delivery_url", "tracking_code", "expires_at"}
    assert link.json()["tracking_code"].startswith("NORA-")
    assert link.json()["tracking_code"] == submitted.json()["tracking_code"]
    delivery_url = link.json()["delivery_url"]
    parsed = urlsplit(delivery_url)
    assert parsed.scheme == "https" and parsed.netloc == "ble.ir"
    assert parsed.path == "/nora_test_bot"
    start = parse_qs(parsed.query)["start"][0]
    assert start.startswith("ft_") and len(start) == 51
    assert "لیلا" not in delivery_url

    response_id = owner.get(f"/api/forms/{form_id}/responses").json()["items"][0]["id"]
    assert response_id not in delivery_url
    raw_token = base64.urlsafe_b64decode(start[3:] + "==")
    assert response_id.encode() not in raw_token
    bot_headers = {"Authorization": "Bearer " + settings.bot_service_token}
    claim_path = "/api/bot/form-tickets/claim"
    unauthorized_claim = visitor.post(
        claim_path, json={"bale_user_id": "73421", "token": start[3:]}
    )
    assert unauthorized_claim.status_code == 401
    claim = owner.post(
        claim_path,
        json={"bale_user_id": "73421", "token": start[3:]},
        headers=bot_headers,
    )
    assert claim.status_code == 200, claim.text
    ticket = claim.json()
    assert ticket["source"] == "shared_server_database"
    assert ticket["response_id"] == response_id
    assert ticket["form_id"] == form_id
    assert ticket["form_title"] == "ثبت نام کارگاه"
    assert ticket["ticket_type"] == expected_ticket_type
    assert ticket["event_title"] == "کارگاه فرهنگ ایرانی"
    assert ticket["event_date"] == "2026-11-13"
    assert ticket["event_time"] == "۱۶:۳۰ تا ۱۹:۰۰"
    assert ticket["participant_name"] == "لیلا رضایی ویرایش‌شده"
    assert ticket["serial"].startswith("NORA-")
    assert ticket["receipt_required"] is False
    assert ticket["receipt_submitted"] is False
    assert "answers" not in ticket and "ticket_claim_nonce_hash" not in ticket
    bot_detail = owner.get(
        f"/api/bot/forms/responses/{response_id}",
        params={"bale_user_id": "73421"},
        headers=bot_headers,
    )
    assert bot_detail.status_code == 200, bot_detail.text
    assert bot_detail.json()["response"]["form_snapshot"]["ticket_type"] == expected_ticket_type

    replay = owner.post(
        claim_path,
        json={"bale_user_id": "73421", "token": start[3:]},
        headers=bot_headers,
    )
    assert replay.status_code == 200 and replay.json()["serial"] == ticket["serial"]
    assert replay.json()["ticket_type"] == expected_ticket_type
    stolen = owner.post(
        claim_path,
        json={"bale_user_id": "73422", "token": start[3:]},
        headers=bot_headers,
    )
    assert stolen.status_code == 409
    reused_link = visitor.post(
        f"/api/public/forms/{form_id}/ticket-link", json={}, headers=origin
    )
    assert reused_link.status_code == 409

    direct = owner.post(
        f"/api/bot/forms/{form_id}/responses/{response_id}/ticket",
        json={"bale_user_id": "73421"},
        headers=bot_headers,
    )
    assert direct.status_code == 200 and direct.json()["serial"] == ticket["serial"]
    assert direct.json()["ticket_type"] == expected_ticket_type
    assert owner.post(
        f"/api/bot/forms/{form_id}/responses/{response_id}/ticket",
        json={"bale_user_id": "73422"},
        headers=bot_headers,
    ).status_code == 404

    verify_path = f"/api/bot/form-tickets/{response_id}/verify"
    forbidden_verify = owner.post(
        verify_path, json={"bale_user_id": "73421"}, headers=bot_headers
    )
    assert forbidden_verify.status_code == 403
    verified = owner.post(verify_path, json={"bale_user_id": "99999"}, headers=bot_headers)
    assert verified.status_code == 200, verified.text
    assert verified.json()["ticket_type"] == expected_ticket_type
    assert verified.json()["checked_in"] is False
    checkin_path = f"/api/bot/form-tickets/{response_id}/check-in"
    entered = owner.post(checkin_path, json={"bale_user_id": "99999"}, headers=bot_headers)
    assert entered.status_code == 200, entered.text
    assert entered.json()["already_checked_in"] is False
    assert entered.json()["checked_in"] is True
    repeated = owner.post(checkin_path, json={"bale_user_id": "99999"}, headers=bot_headers)
    assert repeated.status_code == 200
    assert repeated.json()["already_checked_in"] is True


def _public_receipt_png() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l1sAAAAASUVORK5CYII="
    )


def _upload_public_form_receipt(
    visitor: TestClient, form_id: str, origin: dict[str, str], *, note: str = ""
):
    headers = {
        **origin,
        "Content-Type": "image/png",
        "X-File-Name": "receipt.png",
    }
    if note:
        headers["X-Receipt-Note"] = quote(note, safe="")
    return visitor.post(
        f"/api/public/forms/{form_id}/receipt",
        content=_public_receipt_png(),
        headers=headers,
    )


def _submit_public_registration(owner: TestClient, *, name: str):
    payload = valid_form()
    payload["settings"].update({
        "enabledPaymentMethods": ["card_transfer"],
        "receiptReviewRequired": True,
        "fin": [{"l": "ورودی نمونه", "p": 650000, "off": 0, "req": True, "d": ""}],
        "paymentInstructions": "ابتدا مبلغ را واریز کن.\nشماره پیگیری را نگه دار.\x00",
        "methods": [{
            "id": "pay-by-arrangement",
            "name": "پرداخت با هماهنگی",
            "description": "زمان را با برگزارکننده هماهنگ کن.",
            "type": "gateway",
            "processor_url": "https://private.example.invalid/checkout",
        }],
        "cap": 1,
        "paymentCard": {
            "number": "۴۱۱۱ ۱۱۱۱ ۱۱۱۱ ۱۱۱۱",
            "bank": "بانک نمونه",
            "holder": "حساب سازمان",
            "internal_note": "must-not-be-public",
        },
    })
    created = owner.post("/api/forms", json=payload, headers=create_headers(owner))
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    published = owner.post(
        f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=csrf_headers(owner)
    )
    assert published.status_code == 200, published.text
    visitor = TestClient(owner.app)
    assert visitor.get(f"/form.html?fid={form_id}").status_code == 200
    public_form = visitor.get(f"/api/public/forms/{form_id}")
    assert public_form.status_code == 200, public_form.text
    assert visitor.get(f"/api/public/forms/{form_id}/draft").status_code == 200
    origin = {"Origin": "http://testserver"}
    submitted = visitor.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": {"full-name": name}, "payment": {
            "method": "card_transfer", "selection": {"items": [0], "coupon_code": ""}
        }},
        headers=origin,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "accepted"
    assert submitted.json()["receipt_uploaded"] is False
    assert submitted.json()["payment_id"]
    assert submitted.json()["payment_status"] == "awaiting_receipt"
    response_id = owner.get(f"/api/forms/{form_id}/responses").json()["items"][0]["id"]
    return form_id, response_id, visitor, origin, public_form.json()


def _claim_public_form_ticket(
    owner: TestClient,
    settings: Settings,
    form_id: str,
    visitor: TestClient,
    origin: dict[str, str],
    *,
    expected_status: int = 200,
):
    link = visitor.post(f"/api/public/forms/{form_id}/ticket-link", json={}, headers=origin)
    assert link.status_code == 200, link.text
    start = parse_qs(urlsplit(link.json()["delivery_url"]).query)["start"][0]
    claim = owner.post(
        "/api/bot/form-tickets/claim",
        json={"bale_user_id": "73421", "token": start[3:]},
        headers={"Authorization": "Bearer " + settings.bot_service_token},
    )
    assert claim.status_code == expected_status, claim.text
    if expected_status == 409:
        assert claim.json()["detail"]["code"] == "ticket_payment_not_confirmed"
    return claim, start[3:]


def test_public_form_receipt_upload_precedes_ticket_and_rejection_cancels_registration(
    configured_client,
):
    owner, settings = configured_client
    owner.app.state.settings = replace(
        settings, bale_bot_username="nora_test_bot", owner_bale_user_id="99999"
    )
    login(owner)
    form_id, response_id, visitor, origin, public_form = _submit_public_registration(
        owner, name="لیلا رضایی"
    )

    assert public_form["receiptUploadRequired"] is True
    assert public_form["enabledPaymentMethods"] == ["card_transfer"]
    assert public_form["settings"]["enabledPaymentMethods"] == ["card_transfer"]
    assert public_form["paymentCard"] == {
        "number": "4111111111111111",
        "bank": "بانک نمونه",
        "holder": "حساب سازمان",
    }
    assert public_form["settings"]["paymentCard"] == public_form["paymentCard"]
    assert public_form["paymentInstructions"] == "ابتدا مبلغ را واریز کن.\nشماره پیگیری را نگه دار."
    assert public_form["settings"]["paymentInstructions"] == public_form["paymentInstructions"]
    assert public_form["settings"]["methods"] == [{
        "id": "pay-by-arrangement",
        "name": "پرداخت با هماهنگی",
        "description": "زمان را با برگزارکننده هماهنگ کن.",
        "type": "gateway",
    }]
    assert public_form["methods"] == public_form["settings"]["methods"]
    assert "processor_url" not in str(public_form) and "private.example.invalid" not in str(public_form)
    blocked_link = visitor.post(f"/api/public/forms/{form_id}/ticket-link", json={}, headers=origin)
    assert blocked_link.status_code == 409
    assert blocked_link.json()["detail"]["code"] == "ticket_receipt_required"
    blocked_image = visitor.get(f"/api/public/forms/{form_id}/ticket-image")
    assert blocked_image.status_code == 409
    assert blocked_image.json()["detail"]["code"] == "ticket_payment_not_confirmed"

    invalid_note = _upload_public_form_receipt(visitor, form_id, origin, note="ت" * 501)
    assert invalid_note.status_code == 422 and invalid_note.json()["detail"] == "invalid_receipt_note"
    participant_note = "واریز برای ثبت‌نام لیلا"
    uploaded = _upload_public_form_receipt(visitor, form_id, origin, note=participant_note)
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json() == {"uploaded": True, "created": True}
    updated_note = "توضیح تازه برای کارشناس"
    repeated = _upload_public_form_receipt(visitor, form_id, origin, note=updated_note)
    assert repeated.status_code == 200 and repeated.json() == {"uploaded": True, "created": False}
    restored = visitor.get(f"/api/public/forms/{form_id}/draft")
    assert restored.status_code == 200 and restored.json()["receipt_uploaded"] is True
    assert restored.json()["payment_intent"]["method"] == "card_transfer"
    assert restored.json()["payment_intent"]["status"] == "receipt_submitted"
    blocked_image_after_upload = visitor.get(f"/api/public/forms/{form_id}/ticket-image")
    assert blocked_image_after_upload.status_code == 409
    assert blocked_image_after_upload.json()["detail"]["code"] == "ticket_payment_not_confirmed"

    claim, claim_token = _claim_public_form_ticket(
        owner, settings, form_id, visitor, origin, expected_status=409
    )
    assert claim.json()["detail"]["code"] == "ticket_payment_not_confirmed"
    service_headers = {"Authorization": "Bearer " + settings.bot_service_token}
    ticket = owner.post(
        f"/api/bot/forms/{form_id}/responses/{response_id}/ticket",
        json={"bale_user_id": "73421"},
        headers=service_headers,
    )
    assert ticket.status_code == 409
    assert ticket.json()["detail"]["code"] == "ticket_payment_not_confirmed"
    reopened = visitor.post(f"/api/public/forms/{form_id}/ticket-link", json={}, headers=origin)
    assert reopened.status_code == 200, reopened.text
    reopened_start = parse_qs(urlsplit(reopened.json()["delivery_url"]).query)["start"][0]
    assert reopened_start[3:] == claim_token
    retried_claim = owner.post(
        "/api/bot/form-tickets/claim",
        json={"bale_user_id": "73421", "token": claim_token},
        headers=service_headers,
    )
    assert retried_claim.status_code == 409
    assert retried_claim.json()["detail"]["code"] == "ticket_payment_not_confirmed"

    with owner.app.state.session_factory() as db:
        response = db.get(FormResponseRecord, response_id)
        task = db.query(AdminTaskRecord).filter_by(kind="receipt_review").one()
        private_file = db.query(PrivateFileRecord).filter_by(task_id=task.id).one()
        assert task.status == "pending"
        assert task.bale_user_id == "73421"
        assert task.payload["registration_source"] == "public_form"
        assert task.payload["form_response_id"] == response_id
        assert task.payload["file_refs"] == [private_file.id]
        assert task.payload["note"] == updated_note
        assert private_file.content == _public_receipt_png()
        assert response.receipt_review_task_id == task.id
        assert response.receipt_upload is None
        assert db.query(FormReceiptUploadRecord).count() == 0
        task_id = task.id

    inbox = owner.get("/api/admin/inbox")
    assert inbox.status_code == 200
    assert any(item["id"] == task_id and item["payload"].get("note") == updated_note for item in inbox.json()["items"])

    rejected = owner.post(
        f"/api/admin/inbox/{task_id}/decision",
        json={"decision": "rejected", "reason": "فیش نامعتبر", "expected_version": 1},
        headers=csrf_headers(owner),
    )
    assert rejected.status_code == 200, rejected.text
    assert owner.get(f"/api/forms/{form_id}/responses").json()["total"] == 0
    verify = owner.post(
        f"/api/bot/form-tickets/{response_id}/verify",
        json={"bale_user_id": "99999"},
        headers=service_headers,
    )
    assert verify.status_code == 404
    notice = owner.get("/api/bot/notifications?bale_user_id=73421", headers=service_headers)
    assert notice.status_code == 200 and len(notice.json()["items"]) == 1
    assert notice.json()["items"][0]["title"] == "ثبت‌نامت لغو شد"
    assert "دوباره پر کن" in notice.json()["items"][0]["body"]
    assert "در انتظار تأیید" not in notice.json()["items"][0]["body"]

    restored = visitor.get(f"/api/public/forms/{form_id}/draft")
    assert restored.status_code == 200 and restored.json()["submitted"] is False
    assert restored.json()["answers"] == {}
    again = visitor.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": {"full-name": "لیلا رضایی"}, "payment": {
            "method": "card_transfer", "selection": {"items": [0], "coupon_code": ""}
        }},
        headers=origin,
    )
    assert again.status_code == 200 and again.json()["status"] == "accepted"
    renewed_id = owner.get(f"/api/forms/{form_id}/responses").json()["items"][0]["id"]
    assert renewed_id != response_id


def test_approved_public_form_receipt_unlocks_ticket_only_after_manual_review(configured_client):
    owner, settings = configured_client
    owner.app.state.settings = replace(
        settings, bale_bot_username="nora_test_bot", owner_bale_user_id="99999"
    )
    login(owner)
    form_id, response_id, visitor, origin, _public_form = _submit_public_registration(
        owner, name="سارا رضایی"
    )
    uploaded = _upload_public_form_receipt(visitor, form_id, origin)
    assert uploaded.status_code == 200 and uploaded.json()["uploaded"] is True

    claim, claim_token = _claim_public_form_ticket(
        owner, settings, form_id, visitor, origin, expected_status=409
    )
    assert claim.json()["detail"]["code"] == "ticket_payment_not_confirmed"
    service_headers = {"Authorization": "Bearer " + settings.bot_service_token}
    blocked_ticket = owner.post(
        f"/api/bot/forms/{form_id}/responses/{response_id}/ticket",
        json={"bale_user_id": "73421"},
        headers=service_headers,
    )
    assert blocked_ticket.status_code == 409
    assert blocked_ticket.json()["detail"]["code"] == "ticket_payment_not_confirmed"
    blocked_image = visitor.get(f"/api/public/forms/{form_id}/ticket-image")
    assert blocked_image.status_code == 409
    assert blocked_image.json()["detail"]["code"] == "ticket_payment_not_confirmed"

    with owner.app.state.session_factory() as db:
        task = db.query(AdminTaskRecord).filter_by(kind="receipt_review").one()
        assert task.status == "pending"
        assert task.bale_user_id == "73421"
        assert task.payload["form_response_id"] == response_id
        task_id = task.id
    approved = owner.post(
        f"/api/admin/inbox/{task_id}/decision",
        json={"decision": "approved", "reason": "", "expected_version": 1},
        headers=csrf_headers(owner),
    )
    assert approved.status_code == 200, approved.text
    responses = owner.get(f"/api/forms/{form_id}/responses")
    assert responses.status_code == 200 and responses.json()["total"] == 1
    payment = visitor.get(f"/api/public/forms/{form_id}/draft").json()["payment_intent"]
    assert payment["status"] == "paid_manual"

    ticket = owner.post(
        "/api/bot/form-tickets/claim",
        json={"bale_user_id": "73421", "token": claim_token},
        headers=service_headers,
    )
    assert ticket.status_code == 200, ticket.text
    assert ticket.json()["response_id"] == response_id
    assert ticket.json()["participant_name"] == "سارا رضایی"
    assert ticket.json()["receipt_submitted"] is True
    assert ticket.json()["serial"]

    reissued = visitor.post(f"/api/public/forms/{form_id}/ticket-link", json={}, headers=origin)
    assert reissued.status_code == 200, reissued.text
    new_token = parse_qs(urlsplit(reissued.json()["delivery_url"]).query)["start"][0][3:]
    assert new_token == claim_token
    reused = owner.post(
        "/api/bot/form-tickets/claim",
        json={"bale_user_id": "73421", "token": new_token},
        headers=service_headers,
    )
    assert reused.status_code == 200 and reused.json()["serial"] == ticket.json()["serial"]
    stolen = owner.post(
        "/api/bot/form-tickets/claim",
        json={"bale_user_id": "73422", "token": new_token},
        headers=service_headers,
    )
    assert stolen.status_code == 409

    image = visitor.get(f"/api/public/forms/{form_id}/ticket-image")
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    direct = owner.post(
        f"/api/bot/forms/{form_id}/responses/{response_id}/ticket",
        json={"bale_user_id": "73421"},
        headers=service_headers,
    )
    assert direct.status_code == 200 and direct.json()["serial"] == ticket.json()["serial"]
    notice = owner.get("/api/bot/notifications?bale_user_id=73421", headers=service_headers)
    assert notice.status_code == 200 and notice.json()["items"][0]["title"] == "ثبت‌نامت نهایی شد"


def test_waitlisted_shared_form_never_gets_a_ticket(configured_client):
    owner, settings = configured_client
    owner.app.state.settings = replace(settings, bale_bot_username="nora_test_bot")
    login(owner)
    payload = valid_form()
    payload["settings"]["cap"] = 1
    payload["settings"]["wait"] = 1
    payload["settings"]["ticketing"] = {
        "mode": "random",
        "types": [
            {"id": "general", "name": "عمومی"},
            {"id": "special", "name": "ویژه"},
        ],
    }
    created = owner.post("/api/forms", json=payload, headers=create_headers(owner))
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    published = owner.post(
        f"/api/forms/{form_id}/publish",
        json={"expected_version": 1},
        headers=csrf_headers(owner),
    )
    assert published.status_code == 200

    accepted = TestClient(owner.app)
    assert accepted.get(f"/form.html?fid={form_id}").status_code == 200
    assert accepted.get(f"/api/public/forms/{form_id}/draft").status_code == 200
    origin = {"Origin": "http://testserver"}
    first = accepted.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": {"full-name": "پذیرفته‌شده"}},
        headers=origin,
    )
    assert first.status_code == 200 and first.json()["status"] == "accepted"
    assert first.json()["ticket_type"] in payload["settings"]["ticketing"]["types"]

    waiting = TestClient(owner.app)
    assert waiting.get(f"/form.html?fid={form_id}").status_code == 200
    assert waiting.get(f"/api/public/forms/{form_id}/draft").status_code == 200
    second = waiting.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": {"full-name": "فهرست انتظار"}},
        headers=origin,
    )
    assert second.status_code == 200 and second.json()["status"] == "waitlisted"
    assert second.json()["ticket_type"] is None
    assert waiting.get(f"/api/public/forms/{form_id}/draft").json()["ticket_type"] is None
    image = waiting.get(f"/api/public/forms/{form_id}/ticket-image")
    assert image.status_code == 409
    assert image.json()["detail"]["code"] == "ticket_not_accepted"
    link = waiting.post(f"/api/public/forms/{form_id}/ticket-link", json={}, headers=origin)
    assert link.status_code == 409
    assert link.json()["detail"]["code"] == "ticket_not_accepted"


def test_capacity_waitlist_full_page_and_existing_response_are_consistent(configured_client):
    owner, _ = configured_client
    login(owner)
    payload = valid_form()
    payload["settings"]["cap"] = 1
    payload["settings"]["wait"] = 1
    created = owner.post("/api/forms", json=payload, headers=create_headers(owner))
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    published = owner.post(
        f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=csrf_headers(owner)
    )
    assert published.status_code == 200, published.text

    first = TestClient(owner.app)
    assert first.get(f"/form.html?fid={form_id}").status_code == 200
    assert first.get(f"/api/public/forms/{form_id}/draft").status_code == 200
    accepted = first.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": {"full-name": "پذیرفته"}},
        headers={"Origin": "http://testserver"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    second = TestClient(owner.app)
    assert second.get(f"/form.html?fid={form_id}").status_code == 200
    assert second.get(f"/api/public/forms/{form_id}/draft").status_code == 200
    waitlisted = second.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": {"full-name": "صف انتظار"}},
        headers={"Origin": "http://testserver"},
    )
    assert waitlisted.status_code == 200
    assert waitlisted.json()["status"] == "waitlisted"

    catalog = owner.get(
        "/api/bot/forms/public",
        headers={"Authorization": "Bearer " + owner.app.state.settings.bot_service_token},
    )
    assert catalog.status_code == 200
    assert all(item["id"] != form_id for item in catalog.json()["items"])

    public_status = owner.get(f"/api/public/forms/{form_id}")
    assert public_status.status_code == 410
    third = TestClient(owner.app)
    # The page remains routable so an existing submitter can recover the capability cookie.
    assert third.get(f"/form.html?fid={form_id}").status_code == 200
    full = third.get(f"/api/public/forms/{form_id}/draft")
    assert full.status_code == 410
    assert full.json()["detail"]["code"] == "form_full"

    existing = first.get(f"/api/public/forms/{form_id}/draft")
    assert existing.status_code == 200
    assert existing.json()["submitted"] is True
    assert existing.json()["status"] == "accepted"
    rows = owner.get(f"/api/forms/{form_id}/responses").json()
    assert rows["total"] == 2
    assert {row["status"] for row in rows["items"]} == {"waitlisted", "accepted"}


def test_publication_refuses_unconnected_money_invites_uploads_and_verification(configured_client):
    client, _ = configured_client
    login(client)
    cases = []

    money = valid_form()
    money["settings"]["fin"] = [{"l": "ورودی نمونه", "p": 1000}]
    cases.append((money, "payment_method_required"))

    nora_pay = valid_form()
    nora_pay["settings"]["noraPayEnabled"] = True
    cases.append((nora_pay, "nora_pay_not_connected"))

    invalid_nora_pay = valid_form()
    invalid_nora_pay["settings"]["noraPayEnabled"] = "true"
    cases.append((invalid_nora_pay, "invalid_nora_pay_setting"))

    receipt_without_card = valid_form()
    receipt_without_card["settings"]["receiptReviewRequired"] = True
    cases.append((receipt_without_card, "payment_card_required"))

    receipt_invalid_card = valid_form()
    receipt_invalid_card["settings"].update({
        "receiptReviewRequired": True,
        "paymentCard": {"number": "4111111111111112", "bank": "بانک نمونه", "holder": "حساب نمونه"},
    })
    cases.append((receipt_invalid_card, "payment_card_required"))

    invited = valid_form()
    invited["settings"]["limit"] = "invite"
    cases.append((invited, "external_limit_not_connected"))

    upload = valid_form()
    upload["fields"] = [{"id": "receipt", "t": "file", "l": "فایل پیوست"}]
    cases.append((upload, "file_or_financial_field_not_connected"))

    identity = valid_form()
    identity["fields"] = [{"id": "mobile", "t": "mobile", "l": "شماره", "verify": True}]
    cases.append((identity, "verification_not_connected"))

    invalid_range = valid_form()
    invalid_range["fields"] = [{"id": "amount", "t": "number", "l": "مقدار", "min": 10, "max": 1}]
    cases.append((invalid_range, "invalid_numeric_range"))

    invalid_flag = valid_form()
    invalid_flag["fields"][0]["required"] = "true"
    cases.append((invalid_flag, "invalid_field_configuration"))

    invalid_capacity = valid_form()
    invalid_capacity["settings"]["cap"] = 1.5
    cases.append((invalid_capacity, "invalid_capacity"))

    wait_without_capacity = valid_form()
    wait_without_capacity["settings"]["wait"] = 2
    cases.append((wait_without_capacity, "waitlist_requires_capacity"))

    companions_without_mobile = valid_form()
    companions_without_mobile["settings"].update({
        "guestsOn": True, "maxPer": 2, "compFields": "name-mobile-answers",
    })
    cases.append((companions_without_mobile, "companion_identity_questions_required"))

    for index, (payload, expected_issue) in enumerate(cases):
        created = client.post(
            "/api/forms",
            json=payload,
            headers=create_headers(client, f"publish-guard-create-{index:04d}"),
        )
        assert created.status_code == 201, created.text
        result = client.post(
            f"/api/forms/{created.json()['id']}/publish",
            json={"expected_version": 1},
            headers=csrf_headers(client),
        )
        assert result.status_code == 422, result.text
        assert result.json()["detail"]["code"] == "form_not_publishable"
        assert expected_issue in {issue["code"] for issue in result.json()["detail"]["issues"]}
        assert client.get(f"/api/public/forms/{created.json()['id']}").status_code == 404


def test_server_draft_cookie_is_form_scoped_and_clear_deletes_submitted_data(configured_client):
    client, _ = configured_client
    login(client)
    created = client.post("/api/forms", json=valid_form(), headers=create_headers(client))
    form_id = created.json()["id"]
    assert client.post(
        f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=csrf_headers(client)
    ).status_code == 200
    page = client.get(f"/form.html?fid={form_id}")
    assert page.status_code == 200
    assert client.get(f"/api/public/forms/{form_id}/draft").status_code == 200

    other_client = TestClient(client.app)
    other_client.get(f"/form.html?fid={form_id}")
    assert other_client.get(f"/api/public/forms/{form_id}/draft").json()["answers"] == {}
    assert client.patch(
        f"/api/public/forms/{form_id}/draft",
        json={"answers": {"full-name": "کاربر"}},
        headers={"Origin": "http://testserver"},
    ).status_code == 200
    assert client.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": {"full-name": "کاربر"}},
        headers={"Origin": "http://testserver"},
    ).status_code == 200

    no_origin = client.delete(f"/api/public/forms/{form_id}/draft")
    assert no_origin.status_code == 403
    cleared = client.delete(
        f"/api/public/forms/{form_id}/draft", headers={"Origin": "http://testserver"}
    )
    assert cleared.status_code == 200
    assert cleared.json() == {"deleted": True, "responseDeleted": True}
    assert client.get(f"/api/forms/{form_id}/responses").json()["total"] == 0


def test_public_html_bootstrap_escapes_form_text_and_never_exposes_owner_settings(configured_client):
    client, _ = configured_client
    login(client)
    payload = valid_form()
    payload["name"] = "فرم </script><script>alert(1)</script>"
    payload["settings"]["notify"] = {"on": False, "to": "private-destination"}
    payload["settings"]["paymentCard"] = {
        "number": "4111111111111111", "bank": "بانک نمونه", "holder": "حساب نمونه"
    }
    payload["settings"]["paymentInstructions"] = "این متن فقط برای مدیر است"
    created = client.post("/api/forms", json=payload, headers=create_headers(client))
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    assert client.post(
        f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=csrf_headers(client)
    ).status_code == 200
    page = client.get(f"/form.html?fid={form_id}")
    assert page.status_code == 200
    public_form = client.get(f"/api/public/forms/{form_id}")
    assert public_form.status_code == 200 and "paymentCard" not in public_form.json()
    assert "paymentCard" not in public_form.json()["settings"]
    assert "paymentInstructions" not in public_form.json()
    assert "paymentInstructions" not in public_form.json()["settings"]
    assert "این متن فقط برای مدیر است" not in page.text
    assert "</script><script>alert(1)</script>" not in page.text
    assert "private-destination" not in page.text
    assert "\\u003c/script\\u003e" in page.text


def test_response_retention_and_rate_limits_are_configurable_with_safe_bounds(monkeypatch):
    monkeypatch.setenv("NORA_RESPONSE_DRAFT_TTL_SECONDS", "86400")
    monkeypatch.setenv("NORA_RESPONSE_DRAFT_WRITE_LIMIT_PER_MINUTE", "45")
    monkeypatch.setenv("NORA_RESPONSE_SUBMIT_LIMIT_PER_MINUTE", "7")
    settings = Settings.from_env()
    assert settings.response_draft_ttl_seconds == 86400
    assert settings.response_draft_write_limit_per_minute == 45
    assert settings.response_submit_limit_per_minute == 7

    monkeypatch.setenv("NORA_RESPONSE_SUBMIT_LIMIT_PER_MINUTE", "0")
    with pytest.raises(ValueError, match="NORA_RESPONSE_SUBMIT_LIMIT_PER_MINUTE"):
        Settings.from_env()


def test_api_is_explicitly_unavailable_without_database():
    settings = Settings(
        database_url=None,
        owner_id="owner-01",
        owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"),
        cookie_secure=False,
    )
    with TestClient(create_app(settings)) as client:
        health = client.get("/api/health")
        assert health.status_code == 503
        assert health.json()["formsEnabled"] is False


def test_public_form_never_exposes_coupon_code_and_validates_it_server_side(configured_client):
    owner, _settings = configured_client
    login(owner)
    payload = valid_form()
    payload["settings"].update({
        "enabledPaymentMethods": ["card_transfer"],
        "receiptReviewRequired": True,
        "fin": [{"l": "ورودی نمونه", "p": 1000000, "off": 0, "req": True, "d": ""}],
        "coupon": {"code": "Secret-Code-20", "off": 20, "all": False},
        "paymentCard": {"number": "4111111111111111", "bank": "بانک نمونه", "holder": "حساب سازمان"},
    })
    created = owner.post("/api/forms", json=payload, headers=create_headers(owner))
    assert created.status_code == 201, created.text
    form_id = created.json()["id"]
    origin = {"Origin": "http://testserver"}
    visitor = TestClient(owner.app)

    # Unpublished forms do not leak anything, not even whether a coupon exists.
    assert visitor.post(
        f"/api/public/forms/{form_id}/coupon-check", json={"code": "Secret-Code-20"}, headers=origin
    ).status_code == 404

    published = owner.post(
        f"/api/forms/{form_id}/publish", json={"expected_version": 1}, headers=csrf_headers(owner)
    )
    assert published.status_code == 200, published.text

    public_form = visitor.get(f"/api/public/forms/{form_id}")
    assert public_form.status_code == 200, public_form.text
    assert "Secret-Code-20" not in public_form.text
    assert public_form.json()["coupon"] == {"code": "", "off": 20, "all": False, "enabled": True}
    assert public_form.json()["settings"]["coupon"]["code"] == ""

    check = visitor.post(f"/api/public/forms/{form_id}/coupon-check", json={"code": "secret-code-20"}, headers=origin)
    assert check.status_code == 200, check.text
    assert check.json() == {"valid": True, "off": 20, "all": False}
    assert check.headers["cache-control"] == "no-store"
    wrong = visitor.post(f"/api/public/forms/{form_id}/coupon-check", json={"code": "secret-code-21"}, headers=origin)
    assert wrong.status_code == 200
    assert wrong.json() == {"valid": False, "off": 0, "all": False}
    assert visitor.post(
        f"/api/public/forms/{form_id}/coupon-check", json={"code": ""}, headers=origin
    ).json()["valid"] is False
    assert visitor.post(
        f"/api/public/forms/{form_id}/coupon-check", json={"codes": "x"}, headers=origin
    ).status_code == 400
    assert visitor.post(
        f"/api/public/forms/{form_id}/coupon-check", json={"code": "x" * 65}, headers=origin
    ).status_code == 422

    # The recorded amount is recalculated on the server: a forged code gives no discount,
    # the real code is honoured even though the browser never learned it from the API.
    assert visitor.get(f"/api/public/forms/{form_id}/draft").status_code == 200
    forged = visitor.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": {"full-name": "نمونه"}, "payment": {
            "method": "card_transfer", "selection": {"items": [0], "coupon_code": "HACK99"}
        }},
        headers=origin,
    )
    assert forged.status_code == 200, forged.text
    responses = owner.get(f"/api/forms/{form_id}/responses")
    assert responses.status_code == 200
    payment = responses.json()["items"][0]["form_snapshot"]["payment"]
    assert payment["amount"] == 1000000 and payment["coupon_applied"] is False

    honest = TestClient(owner.app)
    assert honest.get(f"/api/public/forms/{form_id}/draft").status_code == 200
    accepted = honest.post(
        f"/api/public/forms/{form_id}/responses",
        json={"answers": {"full-name": "نمونهٔ دوم"}, "payment": {
            "method": "card_transfer", "selection": {"items": [0], "coupon_code": "SECRET-CODE-20"}
        }},
        headers=origin,
    )
    assert accepted.status_code == 200, accepted.text
    items = owner.get(f"/api/forms/{form_id}/responses").json()["items"]
    amounts = sorted(item["form_snapshot"]["payment"]["amount"] for item in items)
    assert amounts == [800000, 1000000]
