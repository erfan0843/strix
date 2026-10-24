"""Shared-backend identity client tests; no bot or SQLite startup is needed."""
from __future__ import annotations

import sys
from pathlib import Path

import requests
import pytest

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

import config
import shared_api


TOKEN = "t" * 48


class FakeResponse:
    def __init__(self, status_code, payload, *, headers=None, content=b""):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.content = content

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def configure(monkeypatch):
    monkeypatch.setattr(config, "SHARED_API_URL", "https://nora.example")
    monkeypatch.setattr(config, "SHARED_API_TOKEN", TOKEN)
    monkeypatch.setattr(config, "SHARED_API_TIMEOUT_SECONDS", 8)


def test_identity_comes_from_shared_api_and_uses_service_auth(monkeypatch):
    configure(monkeypatch)
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(200, {
            "bale_user_id": "73421",
            "account_id": "account-01",
            "role": "club-supervisor",
            "permissions": ["fm_create", "cl_content"],
        })

    monkeypatch.setattr(shared_api.requests, "post", post)
    identity = shared_api.get_identity(73421)

    assert identity.bale_user_id == 73421
    assert identity.account_id == "account-01"
    assert identity.role == "club-supervisor"
    assert identity.is_admin
    assert identity.has_permission("cl_content")
    assert not identity.has_permission("cl_dues")
    assert calls[0][0] == "https://nora.example/api/bot/identity"
    assert calls[0][1]["json"] == {"bale_user_id": "73421"}
    assert calls[0][1]["headers"]["Authorization"] == "Bearer " + TOKEN
    assert calls[0][1]["timeout"] == 8
    assert calls[0][1]["allow_redirects"] is False


def test_bot_startup_requires_the_canonical_shared_owner(monkeypatch):
    configure(monkeypatch)
    role = {"name": "manager"}
    monkeypatch.setattr(
        shared_api.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(200, {
            "bale_user_id": "73421",
            "account_id": "account-01",
            "role": role["name"],
            "permissions": ["fm_responses"],
        }),
    )
    with pytest.raises(shared_api.SharedAPIError) as denied:
        shared_api.require_owner_identity(73421)
    assert (denied.value.status, denied.value.code) == (403, "shared_owner_identity_required")

    role["name"] = "owner"
    identity = shared_api.require_owner_identity(73421)
    assert identity.role == "owner"


def test_public_form_catalog_uses_authenticated_get_and_validates_summary_only(monkeypatch):
    configure(monkeypatch)
    calls = []
    form = {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "name": "ثبت‌نام کارگاه",
        "model": "registration",
        "need": "reg",
        "version": 3,
    }

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(200, {"source": "shared_server_database", "items": [form]})

    monkeypatch.setattr(shared_api.requests, "get", get)
    assert shared_api.list_public_forms() == [form]
    assert calls[0][0] == "https://nora.example/api/bot/forms/public"
    assert calls[0][1]["headers"]["Authorization"] == "Bearer " + TOKEN
    assert calls[0][1]["timeout"] == 8
    assert calls[0][1]["allow_redirects"] is False


@pytest.mark.parametrize("payload", [
    {"source": "local_sqlite", "items": []},
    {"source": "shared_server_database", "items": [{
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "name": "پیش‌نویس", "model": "registration", "need": "reg", "version": 1,
        "fields": [{"id": "private-answer", "l": "پاسخ خصوصی"}],
    }]},
    {"source": "shared_server_database", "items": [{
        "id": "bad-id", "name": "فرم", "model": "registration", "need": "reg", "version": 1,
    }]},
    {"source": "shared_server_database", "items": [{
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "name": "فرم\nنام", "model": "registration", "need": "reg", "version": 1,
    }]},
])
def test_invalid_public_form_catalog_fails_closed(monkeypatch, payload):
    configure(monkeypatch)
    monkeypatch.setattr(
        shared_api.requests, "get", lambda *args, **kwargs: FakeResponse(200, payload)
    )
    with pytest.raises(shared_api.SharedAPIError, match="shared_api_invalid_public"):
        shared_api.list_public_forms()


def test_unassigned_bale_account_is_not_an_admin(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(shared_api.requests, "post", lambda *a, **k: FakeResponse(200, {
        "bale_user_id": "73422", "account_id": "account-02", "role": None, "permissions": [],
    }))

    identity = shared_api.get_identity("73422")
    assert identity.role is None
    assert not identity.is_admin
    assert not identity.has_permission("fm_create")


def test_missing_configuration_and_invalid_user_id_fail_closed(monkeypatch):
    monkeypatch.setattr(config, "SHARED_API_URL", "")
    monkeypatch.setattr(config, "SHARED_API_TOKEN", "")
    with pytest.raises(shared_api.SharedAPIError) as missing:
        shared_api.get_identity(73421)
    assert (missing.value.status, missing.value.code) == (503, "shared_api_not_configured")

    configure(monkeypatch)
    with pytest.raises(shared_api.SharedAPIError) as invalid:
        shared_api.get_identity(True)
    assert invalid.value.code == "invalid_bale_user_id"


def test_insecure_remote_url_and_short_secret_are_rejected(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(config, "SHARED_API_URL", "http://nora.example")
    with pytest.raises(shared_api.SharedAPIError) as insecure:
        shared_api.get_identity(73421)
    assert insecure.value.code == "shared_api_url_invalid"

    monkeypatch.setattr(config, "SHARED_API_URL", "https://nora.example")
    monkeypatch.setattr(config, "SHARED_API_TOKEN", "short")
    with pytest.raises(shared_api.SharedAPIError) as short:
        shared_api.get_identity(73421)
    assert short.value.code == "shared_api_token_too_short"


def test_network_errors_and_bad_server_identity_never_use_local_permissions(monkeypatch):
    configure(monkeypatch)

    def fail(*args, **kwargs):
        raise requests.Timeout("secret should not appear in bot response")

    monkeypatch.setattr(shared_api.requests, "post", fail)
    with pytest.raises(shared_api.SharedAPIError) as offline:
        shared_api.get_identity(73421)
    assert (offline.value.status, offline.value.code) == (0, "shared_api_unreachable")
    assert TOKEN not in str(offline.value)

    monkeypatch.setattr(shared_api.requests, "post", lambda *a, **k: FakeResponse(200, {
        "bale_user_id": "73422", "account_id": None, "role": "manager", "permissions": ["fm_create"],
    }))
    with pytest.raises(shared_api.SharedAPIError) as mismatch:
        shared_api.get_identity(73421)
    assert mismatch.value.code == "shared_api_identity_mismatch"


def test_redirect_and_unknown_roles_are_denied(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(shared_api.requests, "post", lambda *a, **k: FakeResponse(307, {}))
    with pytest.raises(shared_api.SharedAPIError) as redirect:
        shared_api.get_identity(73421)
    assert redirect.value.status == 307

    monkeypatch.setattr(shared_api.requests, "post", lambda *a, **k: FakeResponse(200, {
        "bale_user_id": "73421", "account_id": "account-01", "role": "full_admin", "permissions": ["*"],
    }))
    with pytest.raises(shared_api.SharedAPIError) as invalid_role:
        shared_api.get_identity(73421)
    assert invalid_role.value.code == "shared_api_invalid_role"


def _bot_form_state(*, answers=None, visible=None, submitted=False, status="draft"):
    return {
        "source": "shared_server_database",
        "form": {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "فرم مشترک",
            "model": "registration",
            "need": "reg",
            "status": "published",
            "version": 2,
            "fields": [
                {"id": "full-name", "t": "text", "l": "نام کامل", "req": True},
                {"id": "city", "t": "select", "l": "شهر", "options": ["تهران", "پاریس"]},
            ],
        },
        "draft": {
            "answers": answers or {},
            "submitted": submitted,
            "status": status,
            "form_version": 2,
        },
        "visible_field_ids": visible or ["full-name"],
    }


def _bot_form_history_item(response_id="123e4567-e89b-12d3-a456-426614174001"):
    return {
        "id": response_id,
        "form_id": "123e4567-e89b-12d3-a456-426614174000",
        "form_name": "فرم مشترک",
        "status": "accepted",
        "form_version": 2,
        "answer_count": 2,
        "created_at": "2026-10-01T10:00:00+00:00",
    }


def _bot_form_response_detail(response_id="123e4567-e89b-12d3-a456-426614174001"):
    return {
        "source": "shared_server_database",
        "response": {
            "id": response_id,
            "form_id": "123e4567-e89b-12d3-a456-426614174000",
            "status": "accepted",
            "form_version": 2,
            "created_at": "2026-10-01T10:00:00+00:00",
            "form_snapshot": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "فرم مشترک",
                "model": "registration",
                "need": "reg",
                "version": 2,
                "receipt_review_required": False,
                "event": {"title": "کارگاه فرهنگ ایرانی", "date": "2026-11-13", "time": "۱۶:۳۰"},
                "ticket_type": {"id": "priority", "name": "ورودی ویژه"},
                "fields": [
                    {"id": "full-name", "type": "text", "label": "نام کامل"},
                    {"id": "city", "type": "select", "label": "شهر"},
                ],
            },
            "answers": {"full-name": "لیلا", "city": "تهران"},
        },
    }


def test_my_bot_form_history_uses_shared_api_and_validates_ownership_payload(monkeypatch):
    configure(monkeypatch)
    calls = []
    history = {
        "source": "shared_server_database",
        "items": [_bot_form_history_item()],
        "total": 1,
        "page": 0,
        "pages": 1,
        "page_size": 6,
    }
    detail = _bot_form_response_detail()

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(200, history if url.endswith("/mine") else detail)

    monkeypatch.setattr(shared_api.requests, "get", get)
    result = shared_api.list_my_bot_form_responses(73421, 0)
    assert result["items"][0]["id"] == _bot_form_history_item()["id"]
    assert calls[0][0] == "https://nora.example/api/bot/forms/mine"
    assert calls[0][1]["params"] == {"bale_user_id": "73421", "page": 0}
    assert calls[0][1]["headers"]["Authorization"] == "Bearer " + TOKEN
    assert calls[0][1]["allow_redirects"] is False

    response = shared_api.get_my_bot_form_response(73421, _bot_form_history_item()["id"])
    assert response["response"]["answers"] == {"full-name": "لیلا", "city": "تهران"}
    assert response["response"]["form_snapshot"]["ticket_type"] == {
        "id": "priority", "name": "ورودی ویژه",
    }
    assert calls[1][0].endswith(f"/api/bot/forms/responses/{_bot_form_history_item()['id']}")
    assert calls[1][1]["params"] == {"bale_user_id": "73421"}


def test_my_bot_form_history_rejects_malformed_server_data(monkeypatch):
    configure(monkeypatch)
    bad_history = {
        "source": "local_sqlite",
        "items": [_bot_form_history_item()],
        "total": 1,
        "page": 0,
        "pages": 1,
        "page_size": 6,
    }
    monkeypatch.setattr(
        shared_api.requests,
        "get",
        lambda *_args, **_kwargs: FakeResponse(200, bad_history),
    )
    with pytest.raises(shared_api.SharedAPIError, match="shared_api_invalid_bot_form_history"):
        shared_api.list_my_bot_form_responses(73421)

    detail = _bot_form_response_detail()
    detail["response"]["form_snapshot"]["fields"][0]["label"] = "نام\nگمراه‌کننده"
    monkeypatch.setattr(
        shared_api.requests,
        "get",
        lambda *_args, **_kwargs: FakeResponse(200, detail),
    )
    with pytest.raises(shared_api.SharedAPIError, match="shared_api_invalid_bot_form_snapshot_field"):
        shared_api.get_my_bot_form_response(73421, _bot_form_history_item()["id"])

    invalid_ticket = _bot_form_response_detail()
    invalid_ticket["response"]["form_snapshot"]["ticket_type"] = {
        "id": "bad/id", "name": "ورودی ویژه",
    }
    monkeypatch.setattr(
        shared_api.requests,
        "get",
        lambda *_args, **_kwargs: FakeResponse(200, invalid_ticket),
    )
    with pytest.raises(shared_api.SharedAPIError, match="shared_api_invalid_bot_form_snapshot"):
        shared_api.get_my_bot_form_response(73421, _bot_form_history_item()["id"])


def test_bot_admin_form_reports_use_authenticated_shared_api(monkeypatch):
    configure(monkeypatch)
    form_id = "123e4567-e89b-12d3-a456-426614174000"
    response_id = _bot_form_history_item()["id"]
    catalog = {
        "source": "shared_server_database",
        "items": [{
            "id": form_id,
            "name": "فرم مشترک",
            "status": "published",
            "version": 2,
            "response_count": 1,
        }],
        "total": 1,
        "page": 0,
        "pages": 1,
        "page_size": 6,
    }
    response_list = {
        "source": "shared_server_database",
        "items": [_bot_form_history_item(response_id)],
        "total": 1,
        "page": 0,
        "pages": 1,
        "page_size": 6,
    }
    detail = _bot_form_response_detail()
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/api/bot/admin/forms"):
            payload = catalog
        elif url.endswith(f"/api/bot/admin/forms/{form_id}/responses"):
            payload = response_list
        else:
            payload = detail
        return FakeResponse(200, payload)

    monkeypatch.setattr(shared_api.requests, "get", get)
    assert shared_api.list_bot_admin_forms(73423)["items"] == catalog["items"]
    assert shared_api.list_bot_admin_form_responses(73423, form_id)["total"] == 1
    assert shared_api.get_bot_admin_form_response(73423, response_id)["response"]["id"] == response_id

    assert calls[0][0] == "https://nora.example/api/bot/admin/forms"
    assert calls[0][1]["params"] == {"bale_user_id": "73423", "page": 0}
    assert calls[1][0] == f"https://nora.example/api/bot/admin/forms/{form_id}/responses"
    assert calls[1][1]["params"] == {"bale_user_id": "73423", "page": 0}
    assert calls[2][0] == f"https://nora.example/api/bot/admin/responses/{response_id}"
    assert calls[2][1]["params"] == {"bale_user_id": "73423"}
    assert all(call[1]["headers"]["Authorization"] == "Bearer " + TOKEN for call in calls)
    assert all(call[1]["allow_redirects"] is False for call in calls)


def test_bot_admin_form_reports_reject_malformed_catalog(monkeypatch):
    configure(monkeypatch)
    invalid = {
        "source": "local_sqlite",
        "items": [],
        "total": 0,
        "page": 0,
        "pages": 0,
        "page_size": 6,
    }
    monkeypatch.setattr(
        shared_api.requests, "get", lambda *_args, **_kwargs: FakeResponse(200, invalid)
    )
    with pytest.raises(shared_api.SharedAPIError, match="shared_api_invalid_bot_admin_forms"):
        shared_api.list_bot_admin_forms(73423)

    invalid["source"] = "shared_server_database"
    invalid["items"] = [{
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "name": "فرم",
        "status": [],
        "version": 1,
        "response_count": 0,
    }]
    invalid.update({"total": 1, "pages": 1})
    with pytest.raises(shared_api.SharedAPIError, match="shared_api_invalid_bot_admin_form_item"):
        shared_api.list_bot_admin_forms(73423)


def test_bot_form_draft_and_response_calls_use_shared_api_with_strict_validation(monkeypatch):
    configure(monkeypatch)
    form_id = "123e4567-e89b-12d3-a456-426614174000"
    session_key = "s" * 43
    calls = []
    state = _bot_form_state()

    def post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        if url.endswith("/responses"):
            return FakeResponse(200, {
                "accepted": True,
                "already_submitted": False,
                "response_id": "123e4567-e89b-12d3-a456-426614174001",
                "status": "accepted",
                "form_version": 2,
            })
        return FakeResponse(200, state)

    def patch(url, **kwargs):
        calls.append(("PATCH", url, kwargs))
        return FakeResponse(200, _bot_form_state(
            answers={"full-name": "لیلا"}, visible=["full-name", "city"]
        ))

    def delete(url, **kwargs):
        calls.append(("DELETE", url, kwargs))
        return FakeResponse(200, {"deleted": True, "submitted": False})

    monkeypatch.setattr(shared_api.requests, "post", post)
    monkeypatch.setattr(shared_api.requests, "patch", patch)
    monkeypatch.setattr(shared_api.requests, "delete", delete)

    started = shared_api.start_bot_form_draft(73421, form_id, session_key)
    assert started["draft"]["answers"] == {}
    assert calls[-1][0:2] == ("POST", f"https://nora.example/api/bot/forms/{form_id}/draft")
    assert calls[-1][2]["json"] == {"bale_user_id": "73421", "session_key": session_key}
    assert calls[-1][2]["headers"]["Authorization"] == "Bearer " + TOKEN

    saved = shared_api.save_bot_form_answer(
        73421, form_id, session_key, "full-name", "لیلا"
    )
    assert saved["draft"]["answers"] == {"full-name": "لیلا"}
    assert saved["visible_field_ids"] == ["full-name", "city"]
    assert calls[-1][0] == "PATCH"
    assert calls[-1][2]["json"] == {
        "bale_user_id": "73421", "session_key": session_key,
        "field_id": "full-name", "value": "لیلا",
    }

    recovered = shared_api.get_bot_form_draft(73421, form_id, session_key)
    assert recovered["form"]["id"] == form_id
    assert calls[-1][1].endswith("/draft/state")

    deleted = shared_api.delete_bot_form_draft(73421, form_id, session_key)
    assert deleted == {"deleted": True, "submitted": False}
    assert calls[-1][0] == "DELETE"
    assert calls[-1][2]["json"]["session_key"] == session_key

    submitted = shared_api.submit_bot_form_response(73421, form_id, session_key)
    assert submitted["response_id"].endswith("4001")
    assert calls[-1][1].endswith("/responses")

    with pytest.raises(shared_api.SharedAPIError, match="invalid_bot_form_session_key"):
        shared_api.start_bot_form_draft(73421, form_id, "short")
    with pytest.raises(shared_api.SharedAPIError, match="invalid_public_form_id"):
        shared_api.start_bot_form_draft(73421, "not-a-form", session_key)


def _shared_ticket_payload(response_id="123e4567-e89b-12d3-a456-426614174001"):
    return {
        "source": "shared_server_database",
        "response_id": response_id,
        "form_id": "123e4567-e89b-12d3-a456-426614174000",
        "serial": "NORA-123E4567E89B12D3A456",
        "form_title": "فرم ثبت‌نام",
        "event_title": "فرم ثبت‌نام",
        "event_date": "",
        "event_time": "",
        "participant_name": "لیلا رضایی",
        "ticket_type": {"id": "priority", "name": "ورودی ویژه"},
        "issued_at": "2026-10-01T10:00:00+00:00",
        "receipt_required": False,
        "receipt_submitted": False,
        "checked_in": False,
        "checked_in_at": None,
    }


def test_shared_form_ticket_calls_are_authenticated_and_strictly_validated(monkeypatch):
    configure(monkeypatch)
    form_id = "123e4567-e89b-12d3-a456-426614174000"
    response_id = "123e4567-e89b-12d3-a456-426614174001"
    token = "T" * 48
    base = _shared_ticket_payload(response_id)
    verified = {**base, "checked_in_by_bale_user_id": None}
    checked_in = {
        **base,
        "checked_in": True,
        "checked_in_at": "2026-10-01T11:00:00+00:00",
        "checked_in_by_bale_user_id": "73423",
        "already_checked_in": False,
    }
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/claim") or url.endswith("/ticket"):
            return FakeResponse(200, base)
        if url.endswith("/verify"):
            return FakeResponse(200, verified)
        return FakeResponse(200, checked_in)

    monkeypatch.setattr(shared_api.requests, "post", post)
    assert shared_api.get_bot_form_ticket(73421, form_id, response_id) == base
    assert shared_api.claim_bot_form_ticket(73421, token) == base
    assert shared_api.verify_bot_form_ticket(73423, response_id) == verified
    assert shared_api.check_in_bot_form_ticket(73423, response_id) == checked_in

    assert calls[0][0] == f"https://nora.example/api/bot/forms/{form_id}/responses/{response_id}/ticket"
    assert calls[0][1]["json"] == {"bale_user_id": "73421"}
    assert calls[1][0] == "https://nora.example/api/bot/form-tickets/claim"
    assert calls[1][1]["json"] == {"bale_user_id": "73421", "token": token}
    assert calls[2][0] == f"https://nora.example/api/bot/form-tickets/{response_id}/verify"
    assert calls[3][0] == f"https://nora.example/api/bot/form-tickets/{response_id}/check-in"
    assert all(call[1]["headers"]["Authorization"] == "Bearer " + TOKEN for call in calls)
    assert all(call[1]["allow_redirects"] is False for call in calls)

    invalid = {**base, "source": "local_sqlite"}
    monkeypatch.setattr(
        shared_api.requests,
        "post",
        lambda *_args, **_kwargs: FakeResponse(200, invalid),
    )
    with pytest.raises(shared_api.SharedAPIError, match="shared_api_invalid_form_ticket"):
        shared_api.get_bot_form_ticket(73421, form_id, response_id)

    legacy_payload = {key: item for key, item in base.items() if key != "ticket_type"}
    assert shared_api._validate_form_ticket(legacy_payload) == legacy_payload
    invalid_type = {**base, "ticket_type": {"id": "bad/id", "name": "ورودی ویژه"}}
    monkeypatch.setattr(
        shared_api.requests,
        "post",
        lambda *_args, **_kwargs: FakeResponse(200, invalid_type),
    )
    with pytest.raises(shared_api.SharedAPIError, match="shared_api_invalid_form_ticket"):
        shared_api.get_bot_form_ticket(73421, form_id, response_id)

    with pytest.raises(shared_api.SharedAPIError, match="invalid_ticket_claim_token"):
        shared_api.claim_bot_form_ticket(73421, "short")


def test_bot_form_api_rejects_local_sources_and_invalid_server_answer_state(monkeypatch):
    configure(monkeypatch)
    form_id = "123e4567-e89b-12d3-a456-426614174000"
    monkeypatch.setattr(
        shared_api.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(200, {
            **_bot_form_state(), "source": "local_sqlite",
        }),
    )
    with pytest.raises(shared_api.SharedAPIError, match="shared_api_invalid_bot_form_state"):
        shared_api.start_bot_form_draft(73421, form_id, "s" * 43)

    invalid = _bot_form_state(answers={"not-a-field": "محلی"})
    monkeypatch.setattr(
        shared_api.requests, "post", lambda *args, **kwargs: FakeResponse(200, invalid)
    )
    with pytest.raises(shared_api.SharedAPIError, match="shared_api_invalid_bot_form_answers"):
        shared_api.get_bot_form_draft(73421, form_id, "s" * 43)


def _report_summary(period="30d"):
    return {
        "source": "shared_server_database",
        "period": period,
        "generated_at": "2026-10-01T00:00:00+00:00",
        "forms": {"total": 3, "created_in_period": 1, "by_status": {"published": 2, "draft": 1}},
        "responses": {"total": 8, "by_status": {"accepted": 6, "waitlisted": 2}},
        "accounts": {"total": 12, "by_role": {"manager": 2, "club-supervisor": 1}},
        "reviews": {"total": 2, "by_kind": {
            "profile_review": {"pending": 1}, "receipt_review": {"approved": 1},
        }},
        "notifications": {"total": 5, "by_delivery_status": {"delivered": 4, "pending": 1}},
        "cooperation_requests": {"total": 2, "by_status": {"new": 2}},
        "coverage": {"financial_amounts": "not_included", "event_attendance": "not_in_shared_api_database"},
    }


def test_report_summary_uses_service_api_and_strict_aggregate_shape(monkeypatch):
    configure(monkeypatch)
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(200, _report_summary())

    monkeypatch.setattr(shared_api.requests, "post", post)
    result = shared_api.get_report_summary(73421, "30d")

    assert result["forms"]["total"] == 3
    assert result["reviews"]["by_kind"]["receipt_review"]["approved"] == 1
    assert calls[0][0] == "https://nora.example/api/bot/reports/summary"
    assert calls[0][1]["json"] == {"bale_user_id": "73421", "period": "30d"}
    assert calls[0][1]["headers"]["Authorization"] == "Bearer " + TOKEN
    assert calls[0][1]["allow_redirects"] is False

    with pytest.raises(shared_api.SharedAPIError, match="invalid_report_period"):
        shared_api.get_report_summary(73421, "this-month")
    with pytest.raises(shared_api.SharedAPIError, match="invalid_bale_user_id"):
        shared_api.get_report_summary(True, "30d")

    monkeypatch.setattr(shared_api.requests, "post", lambda *a, **k: FakeResponse(200, {
        **_report_summary(), "payload": {"amount": 900000},
    }))
    with pytest.raises(shared_api.SharedAPIError, match="shared_api_invalid_report"):
        shared_api.get_report_summary(73421, "30d")


def _task(task_id, kind="profile_review", status="pending"):
    return {
        "id": task_id,
        "account_id": "account-01",
        "bale_user_id": "73421",
        "kind": kind,
        "payload": {"full_name": "آزمایش"},
        "status": status,
        "version": 1,
        "created_at": "2026-10-01T00:00:00+00:00",
        "reviewed_at": None,
    }


def test_shared_workflow_submission_and_inbox_use_authenticated_api(monkeypatch):
    import uuid

    configure(monkeypatch)
    task_id = str(uuid.uuid4())
    calls = []

    def post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        return FakeResponse(200, {"task": _task(task_id), "created": True})

    def get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        return FakeResponse(200, {"items": [_task(task_id)], "has_more": False})

    monkeypatch.setattr(shared_api.requests, "post", post)
    monkeypatch.setattr(shared_api.requests, "get", get)

    submitted = shared_api.submit_workflow(
        73421, "profile_review", {"full_name": "آزمایش"}, "profile-key-0001"
    )
    assert submitted["created"] is True
    assert submitted["task"]["id"] == task_id
    assert calls[0][1] == "https://nora.example/api/bot/workflows"
    assert calls[0][2]["json"]["idempotency_key"] == "profile-key-0001"
    assert calls[0][2]["headers"]["Authorization"] == "Bearer " + TOKEN

    inbox = shared_api.list_workflows(73421)
    assert inbox["items"][0]["id"] == task_id
    assert calls[1][1] == "https://nora.example/api/bot/inbox"
    assert calls[1][2]["params"]["bale_user_id"] == "73421"


def test_shared_workflow_decision_and_notification_ack_fail_closed(monkeypatch):
    import uuid

    configure(monkeypatch)
    task_id = str(uuid.uuid4())
    notification_id = str(uuid.uuid4())
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/decision"):
            return FakeResponse(200, {"task": _task(task_id, status="approved"), "accepted": True})
        return FakeResponse(200, {"delivered": True})

    def get(url, **kwargs):
        return FakeResponse(200, {"items": [{
            "id": notification_id,
            "kind": "profile_approved",
            "title": "پروفایل تأیید شد",
            "body": "پروفایل شما ثبت شد.",
            "file_refs": [],
            "delivery_status": "pending",
        }]})

    monkeypatch.setattr(shared_api.requests, "post", post)
    monkeypatch.setattr(shared_api.requests, "get", get)

    decision = shared_api.decide_workflow(
        task_id, 73421, "approved", expected_version=1
    )
    assert decision["accepted"] is True
    assert decision["task"]["status"] == "approved"
    assert calls[0][1]["json"]["expected_version"] == 1
    assert shared_api.list_notifications(73421)[0]["id"] == notification_id
    assert shared_api.mark_notification_delivered(notification_id, 73421)
    assert calls[-1][1]["json"] == {"bale_user_id": "73421"}


def test_invalid_workflow_payload_and_shared_api_failure_never_fall_back(monkeypatch):
    import uuid

    configure(monkeypatch)
    with pytest.raises(shared_api.SharedAPIError, match="invalid_workflow_id"):
        shared_api.decide_workflow("not-an-id", 73421, "approved", expected_version=1)

    monkeypatch.setattr(shared_api.requests, "post", lambda *a, **k: FakeResponse(503, {"detail": "database_unavailable"}))
    with pytest.raises(shared_api.SharedAPIError) as failed:
        shared_api.submit_workflow(73421, "profile_review", {"full_name": "آزمایش"}, "retry-1")
    assert failed.value.status == 503
    assert failed.value.code == "database_unavailable"
    assert TOKEN not in str(failed.value)


def test_private_file_upload_and_download_use_shared_api(monkeypatch):
    import uuid

    configure(monkeypatch)
    file_id = str(uuid.uuid4())
    png = b"\x89PNG\r\n\x1a\nfile-bytes"
    calls = []

    def post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        return FakeResponse(200, {
            "id": file_id,
            "content_type": "image/png",
            "size": len(png),
            "created": True,
        })

    def get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        return FakeResponse(200, {}, headers={"content-type": "image/png"}, content=png)

    monkeypatch.setattr(shared_api.requests, "post", post)
    monkeypatch.setattr(shared_api.requests, "get", get)

    uploaded = shared_api.upload_private_file(73421, png, "profile.png", "profile-file:one")
    assert uploaded == file_id
    assert calls[0][1] == "https://nora.example/api/bot/files"
    assert calls[0][2]["data"] == png
    assert calls[0][2]["headers"]["X-Bale-User-Id"] == "73421"
    assert calls[0][2]["headers"]["Authorization"] == "Bearer " + TOKEN

    content, content_type = shared_api.download_private_file(file_id)
    assert content == png and content_type == "image/png"
    assert calls[1][1] == f"https://nora.example/api/bot/files/{file_id}"



def test_private_file_listing_and_published_delivery_download(monkeypatch):
    import uuid

    configure(monkeypatch)
    private_id = str(uuid.uuid4())
    file_id = "a" * 32
    content = b"%PDF-1.7\npublic content\n%%EOF"
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/api/bot/files"):
            return FakeResponse(200, {"items": [{
                "id": private_id, "file_name": "رسید.pdf", "content_type": "application/pdf",
                "content_size": 100, "created_at": "2026-09-30T10:00:00+00:00",
            }]})
        return FakeResponse(200, {}, headers={
            "content-type": "application/pdf",
            "content-disposition": "attachment; filename=\"book.pdf\"; filename*=UTF-8''%D9%85%D8%B9%D8%B1%D9%81%DB%8C.pdf",
        }, content=content)

    monkeypatch.setattr(shared_api.requests, "get", get)
    files = shared_api.list_private_files(73421)
    assert files[0]["id"] == private_id and files[0]["file_name"] == "رسید.pdf"
    assert calls[0][0] == "https://nora.example/api/bot/files"
    assert calls[0][1]["params"] == {"bale_user_id": "73421"}
    assert calls[0][1]["headers"]["Authorization"] == "Bearer " + TOKEN

    data, content_type, file_name = shared_api.download_content_file(file_id)
    assert data == content and content_type == "application/pdf" and file_name == "معرفی.pdf"
    assert calls[1][0] == f"https://nora.example/api/bot/content-files/{file_id}"
    assert calls[1][1]["allow_redirects"] is False
    with pytest.raises(shared_api.SharedAPIError, match="invalid_content_delivery_id"):
        shared_api.download_content_file("../unsafe")


def test_notification_file_refs_are_delivered_through_bale(monkeypatch):
    import shared_workflows

    file_id = "00000000-0000-4000-8000-000000000111"
    item = {"id": "00000000-0000-4000-8000-000000000211", "bale_user_id": "73421",
            "title": "گواهی آماده است", "body": "از بات دریافت کن.", "file_refs": [file_id]}
    listed = [{"id": file_id, "file_name": "گواهی.pdf", "content_type": "application/pdf",
               "content_size": 10, "created_at": "2026-09-30T10:00:00+00:00"}]
    sent_messages, sent_files, delivered = [], [], []
    monkeypatch.setattr(shared_workflows.shared_api, "list_pending_notifications", lambda limit=50: [item])
    monkeypatch.setattr(shared_workflows.shared_api, "list_private_files", lambda user_id: listed)
    monkeypatch.setattr(shared_workflows.shared_api, "download_private_file", lambda file_id: (b"%PDF-1.7\n", "application/pdf"))
    monkeypatch.setattr(shared_workflows.shared_api, "mark_notification_delivered",
                        lambda notice_id, user_id: delivered.append((notice_id, str(user_id))) or True)
    monkeypatch.setattr(shared_workflows.shared_api, "mark_notification_failed", lambda *args: "failed")
    monkeypatch.setattr(shared_workflows, "send", lambda user_id, text: sent_messages.append((str(user_id), text)) or {"ok": True})
    monkeypatch.setattr(shared_workflows, "send_document",
                        lambda cid, path, **kwargs: sent_files.append((str(cid), Path(path).read_bytes(), kwargs)) or {"ok": True})

    assert shared_workflows.deliver_pending_notifications() == 1
    assert sent_messages == [("73421", "گواهی آماده است\n\nاز بات دریافت کن.")]
    assert sent_files[0][0:2] == ("73421", b"%PDF-1.7\n")
    assert sent_files[0][2]["filename"] == "گواهی.pdf"
    assert delivered == [(item["id"], "73421")]



def test_private_deep_link_rechecks_bale_identity_and_file_ownership(monkeypatch):
    import shared_workflows

    file_id = "00000000-0000-4000-8000-000000000111"
    listed = [{"id": file_id, "file_name": "profile.png", "content_type": "image/png",
               "content_size": 8, "created_at": "2026-09-30T10:00:00+00:00"}]
    sent, warnings = [], []
    monkeypatch.setattr(shared_workflows.shared_api, "list_private_files", lambda user_id: listed)
    monkeypatch.setattr(shared_workflows.shared_api, "download_private_file",
                        lambda requested: (b"\x89PNG\r\n\x1a\n", "image/png"))
    monkeypatch.setattr(shared_workflows, "send_photo",
                        lambda cid, path, **kwargs: sent.append((str(cid), Path(path).read_bytes(), kwargs)) or {"ok": True})
    monkeypatch.setattr(shared_workflows, "send", lambda cid, text, *args: warnings.append((str(cid), text)) or {"ok": True})

    assert shared_workflows.send_account_file(73421, 73421, file_id) is True
    assert sent[0][0:2] == ("73421", b"\x89PNG\r\n\x1a\n")
    assert sent[0][2]["filename"] == "profile.png"
    assert shared_workflows.send_account_file(73422, 73421, file_id) is False
    assert warnings and len(sent) == 1
    assert shared_workflows.send_account_file(73421, 73421, "00000000-0000-4000-8000-000000000999") is False
    assert len(sent) == 1


def test_bot_drains_shared_notifications_and_acknowledges_delivery(monkeypatch):
    import shared_workflows

    pending = [
        {"id": "notice-delivered", "bale_user_id": "73421", "title": "پروفایل تأیید شد",
         "body": "پروفایل شما ثبت شد.", "delivery_status": "pending"},
        {"id": "notice-failed", "bale_user_id": "73422", "title": "فیش نیاز به اصلاح دارد",
         "body": "تصویر خوانا نیست.", "delivery_status": "pending"},
    ]
    sent = []
    delivered = []
    failed = []
    monkeypatch.setattr(shared_workflows.shared_api, "list_pending_notifications", lambda limit=50: pending)
    monkeypatch.setattr(shared_workflows.shared_api, "mark_notification_delivered",
                        lambda notice_id, user_id: delivered.append((notice_id, str(user_id))) or True)
    monkeypatch.setattr(shared_workflows.shared_api, "mark_notification_failed",
                        lambda notice_id, user_id: failed.append((notice_id, str(user_id))) or "pending")

    def send_message(user_id, text):
        sent.append((str(user_id), text))
        return {"ok": str(user_id) == "73421"}

    monkeypatch.setattr(shared_workflows, "send", send_message)
    assert shared_workflows.deliver_pending_notifications(limit=25) == 1
    assert delivered == [("notice-delivered", "73421")]
    assert failed == [("notice-failed", "73422")]
    assert sent == [
        ("73421", "پروفایل تأیید شد\n\nپروفایل شما ثبت شد."),
        ("73422", "فیش نیاز به اصلاح دارد\n\nتصویر خوانا نیست."),
    ]


def test_workflow_projection_queue_and_ack_methods(monkeypatch):
    import uuid

    configure(monkeypatch)
    task_id = str(uuid.uuid4())
    task = _task(task_id, status="approved")
    task["projection_status"] = "pending"
    task["projection_attempts"] = 0
    get_calls = []
    post_calls = []

    def get(url, **kwargs):
        get_calls.append((url, kwargs))
        return FakeResponse(200, {"items": [task]})

    def post(url, **kwargs):
        post_calls.append((url, kwargs))
        if url.endswith("projection-applied"):
            return FakeResponse(200, {"applied": True})
        return FakeResponse(200, {"recorded": True, "projection_status": "pending"})

    monkeypatch.setattr(shared_api.requests, "get", get)
    monkeypatch.setattr(shared_api.requests, "post", post)

    items = shared_api.list_workflow_projections()
    assert items[0]["id"] == task_id
    assert shared_api.mark_workflow_projection_applied(task_id)
    assert shared_api.mark_workflow_projection_failed(task_id) == "pending"
    assert get_calls[0][0].endswith("/api/bot/workflows/projection-pending")
    assert post_calls[0][0].endswith(f"/{task_id}/projection-applied")
    assert post_calls[1][0].endswith(f"/{task_id}/projection-failed")


def test_notification_link_becomes_a_webapp_button_only_for_relative_pages(monkeypatch):
    """فاز ۹.۴: پیوند نسبی سرور + وب‌اپ تنظیم‌شده → دکمهٔ مینی‌اپ؛ بدون وب‌اپ یا با نشانی ناامن → فقط متن."""
    import shared_workflows

    sent = []
    delivered = []
    monkeypatch.setattr(shared_workflows.shared_api, "mark_notification_delivered",
                        lambda notice_id, user_id: delivered.append(notice_id) or True)
    monkeypatch.setattr(shared_workflows.shared_api, "mark_notification_failed", lambda *args: "failed")
    monkeypatch.setattr(shared_workflows, "send", lambda user_id, text, kb=None: sent.append((str(user_id), text, kb)) or {"ok": True})

    def items(link):
        return [{"id": "00000000-0000-4000-8000-000000000311", "bale_user_id": "73421", "kind": "recording_content",
                 "title": "محتوای تازه", "body": "جلسهٔ دوم منتشر شد.", "file_refs": [], "link": link}]

    monkeypatch.setattr(shared_workflows, "NORA_WEBAPP_URL", "https://nora.example")
    monkeypatch.setattr(shared_workflows.shared_api, "list_pending_notifications", lambda limit=50: items("/event.html?id=ev-1#recording"))
    assert shared_workflows.deliver_pending_notifications() == 1
    assert sent[-1][2] == {"inline_keyboard": [[{"text": "🔗 باز کردن در مینی‌اپ",
                                                 "web_app": {"url": "https://nora.example/event.html?id=ev-1#recording"}}]]}
    for unsafe in ("https://evil.example/x", "//evil.example/x", "/api/public/events/e/resources/r/download", None):
        monkeypatch.setattr(shared_workflows.shared_api, "list_pending_notifications", lambda limit=50, u=unsafe: items(u))
        assert shared_workflows.deliver_pending_notifications() == 1
        assert sent[-1][2] is None, unsafe
    monkeypatch.setattr(shared_workflows, "NORA_WEBAPP_URL", "")
    monkeypatch.setattr(shared_workflows.shared_api, "list_pending_notifications", lambda limit=50: items("/account.html#certificates"))
    assert shared_workflows.deliver_pending_notifications() == 1
    assert sent[-1][2] is None and sent[-1][1] == "محتوای تازه\n\nجلسهٔ دوم منتشر شد."
    assert len(delivered) == 6  # every attempt acknowledged to the server; text-only is still a delivery
