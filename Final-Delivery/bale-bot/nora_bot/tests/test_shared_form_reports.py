"""Admin form response views use only the authorized shared API."""

# ruff: noqa: INP001, RUF001
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

import shared_api  # noqa: E402
import shared_form_reports  # noqa: E402


FORM_ID = "123e4567-e89b-12d3-a456-426614174000"
RESPONSE_ID = "123e4567-e89b-12d3-a456-426614174001"


def form(index: int) -> dict:
    return {
        "id": FORM_ID if index == 1 else f"123e4567-e89b-12d3-a456-{index:012d}",
        "name": f"فرم مشترک {index}",
        "status": "published",
        "version": 2,
        "response_count": index,
    }


def catalog(items, *, page=0, total=None, pages=1):
    return {
        "source": "shared_server_database",
        "items": items,
        "total": len(items) if total is None else total,
        "page": page,
        "pages": pages,
        "page_size": 6,
    }


def response_item(index: int, *, status="accepted") -> dict:
    return {
        "id": RESPONSE_ID if index == 1 else f"123e4567-e89b-12d3-a456-{index:012d}",
        "form_id": FORM_ID,
        "form_name": "فرم مشترک",
        "status": status,
        "form_version": 2,
        "answer_count": 2,
        "created_at": "2026-10-01T10:00:00+00:00",
    }


def history(items, *, page=0, total=None, pages=1):
    return {
        "source": "shared_server_database",
        "items": items,
        "total": len(items) if total is None else total,
        "page": page,
        "pages": pages,
        "page_size": 6,
    }


def detail() -> dict:
    return {
        "source": "shared_server_database",
        "response": {
            "id": RESPONSE_ID,
            "form_id": FORM_ID,
            "status": "waitlisted",
            "form_version": 2,
            "created_at": "2026-10-01T10:00:00+00:00",
            "form_snapshot": {
                "id": FORM_ID,
                "name": "فرم مشترک",
                "model": "registration",
                "need": "reg",
                "version": 2,
                "ticket_type": {"id": "priority", "name": "ورودی ویژه"},
                "fields": [
                    {"id": "full-name", "type": "text", "label": "نام کامل"},
                    {"id": "city", "type": "select", "label": "شهر"},
                ],
            },
            "answers": {"full-name": "لیلا", "city": "تهران"},
        },
    }


def capture(monkeypatch):
    sent = []
    monkeypatch.setattr(
        shared_form_reports,
        "send_or_edit",
        lambda cid, text, keyboard=None: sent.append((cid, text, keyboard)) or "sent",
    )
    return sent


def allow_read(monkeypatch, allowed=True):
    monkeypatch.setattr(
        shared_api,
        "get_identity",
        lambda _uid: SimpleNamespace(has_permission=lambda key: allowed and key == "fm_responses"),
    )


def callbacks(keyboard) -> set[str]:
    return {
        str(button.get("callback_data"))
        for row in keyboard["inline_keyboard"]
        for button in row
        if button.get("callback_data")
    }


def test_server_form_and_response_pages_are_read_only_and_paginated(monkeypatch):
    sent = capture(monkeypatch)
    allow_read(monkeypatch)
    forms = {
        0: catalog([form(index) for index in range(1, 7)], total=7, pages=2),
        1: catalog([form(7)], page=1, total=7, pages=2),
    }
    form_calls = []
    monkeypatch.setattr(
        shared_api,
        "list_bot_admin_forms",
        lambda uid, page: form_calls.append((uid, page)) or forms[page],
    )

    assert shared_form_reports.show_forms(100, 73423) == "sent"
    _, first_text, first_keyboard = sent[-1]
    assert "فرم‌های سرور (7)" in first_text
    assert "فرم مشترک 1" in first_text and "فرم مشترک 6" in first_text
    assert "فرم مشترک 7" not in first_text
    assert "sfrf_" + FORM_ID in callbacks(first_keyboard)
    assert "sfrl_1" in callbacks(first_keyboard)
    assert form_calls == [(73423, 0)]

    shared_api_responses = {
        0: history([response_item(index) for index in range(1, 7)], total=7, pages=2),
        1: history([response_item(7, status="waitlisted")], page=1, total=7, pages=2),
    }
    response_calls = []
    monkeypatch.setattr(
        shared_api,
        "list_bot_admin_form_responses",
        lambda uid, form_id, page: (
            response_calls.append((uid, form_id, page)) or shared_api_responses[page]
        ),
    )

    assert shared_form_reports.show_responses(100, 73423, FORM_ID) == "sent"
    _, response_text, response_keyboard = sent[-1]
    assert "فرم مشترک" in response_text and "ثبت‌شده" in response_text
    assert "sfrd_" + RESPONSE_ID in callbacks(response_keyboard)
    assert f"sfrp_{FORM_ID}_1" in callbacks(response_keyboard)

    shared_form_reports.show_responses(100, 73423, FORM_ID, 1)
    assert "فهرست انتظار" in sent[-1][1]
    assert f"sfrp_{FORM_ID}_0" in callbacks(sent[-1][2])
    assert form_calls == [(73423, 0)]
    assert response_calls == [(73423, FORM_ID, 0), (73423, FORM_ID, 1)]


def test_response_details_show_snapshot_and_server_answers(monkeypatch):
    sent = capture(monkeypatch)
    allow_read(monkeypatch)
    requested = []
    monkeypatch.setattr(
        shared_api,
        "get_bot_admin_form_response",
        lambda uid, response_id: requested.append((uid, response_id)) or detail(),
    )

    assert shared_form_reports.show_response(100, 73423, RESPONSE_ID) == "sent"
    _, text, keyboard = sent[-1]
    assert requested == [(73423, RESPONSE_ID)]
    assert "فرم مشترک" in text
    assert "فهرست انتظار" in text
    assert "مدل بلیت: ورودی ویژه" in text
    assert "نام کامل" in text and "لیلا" in text
    assert "شهر" in text and "تهران" in text
    assert f"sfrp_{FORM_ID}_0" in callbacks(keyboard)


def test_missing_permission_and_api_errors_never_substitute_local_rows(monkeypatch):
    sent = capture(monkeypatch)
    allow_read(monkeypatch, allowed=False)
    monkeypatch.setattr(
        shared_api,
        "list_bot_admin_forms",
        lambda *_args: pytest.fail("API must not be called without fm_responses"),
    )

    shared_form_reports.show_forms(100, 73422)
    assert "مجوز فرم‌ها فعال نیست" in sent[-1][1]

    allow_read(monkeypatch)
    monkeypatch.setattr(
        shared_api,
        "list_bot_admin_forms",
        lambda *_args: (_ for _ in ()).throw(
            shared_api.SharedAPIError(503, "shared_api_unreachable")
        ),
    )
    shared_form_reports.show_forms(100, 73423)
    _, text, keyboard = sent[-1]
    assert "پایگاه مشترک" in text
    assert "جایگزین نمی‌شود" in text
    assert "sfr_forms" in callbacks(keyboard)
    assert "rp_forms" in callbacks(keyboard)


def test_response_api_error_retries_shared_detail_without_local_fallback(monkeypatch):
    sent = capture(monkeypatch)
    allow_read(monkeypatch)
    monkeypatch.setattr(
        shared_api,
        "get_bot_admin_form_response",
        lambda *_args: (_ for _ in ()).throw(
            shared_api.SharedAPIError(503, "shared_api_unreachable")
        ),
    )

    shared_form_reports.show_response(100, 73423, RESPONSE_ID)
    _, text, keyboard = sent[-1]
    assert "پایگاه مشترک" in text and "جایگزین نمی‌شود" in text
    assert f"sfrd_{RESPONSE_ID}" in callbacks(keyboard)


def test_invalid_ids_do_not_call_response_api(monkeypatch):
    sent = capture(monkeypatch)
    allow_read(monkeypatch)
    monkeypatch.setattr(
        shared_api,
        "get_bot_admin_form_response",
        lambda *_args: pytest.fail("invalid response IDs must be rejected in the bot"),
    )

    shared_form_reports.show_response(100, 73423, "../other-user")
    assert "دکمهٔ گزارش معتبر نیست" in sent[-1][1]
    shared_form_reports.show_responses(100, 73423, "not-a-form-id")
    assert "دکمهٔ گزارش معتبر نیست" in sent[-1][1]
