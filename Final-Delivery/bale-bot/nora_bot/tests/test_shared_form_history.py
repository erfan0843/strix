"""My forms reads conversational responses from the shared server only."""

# ruff: noqa: INP001
from __future__ import annotations

import sys
from pathlib import Path

import pytest


BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

import form_fill  # noqa: E402
import shared_api  # noqa: E402


FORM_ID = "123e4567-e89b-12d3-a456-426614174000"
RESPONSE_ID = "123e4567-e89b-12d3-a456-426614174001"


def item(index: int, *, status: str = "accepted") -> dict:
    return {
        "id": f"123e4567-e89b-12d3-a456-{index:012d}",
        "form_id": FORM_ID,
        "form_name": f"فرم مشترک {index}",
        "status": status,
        "form_version": 2,
        "answer_count": 2,
        "created_at": "2026-10-01T10:00:00+00:00",
    }


def history(items, *, page: int = 0, total: int | None = None, pages: int = 1) -> dict:
    return {
        "source": "shared_server_database",
        "items": items,
        "total": len(items) if total is None else total,
        "page": page,
        "pages": pages,
        "page_size": 6,
    }


def capture(monkeypatch):
    sent = []
    monkeypatch.setattr(
        form_fill,
        "send_or_edit",
        lambda cid, text, keyboard=None: sent.append((cid, text, keyboard)) or "sent",
    )
    monkeypatch.setattr(
        form_fill,
        "send",
        lambda cid, text, keyboard=None: sent.append((cid, text, keyboard)) or "sent",
    )

    def forbid_db(*_args, **_kwargs):
        pytest.fail("shared response history must not fall back to bot SQLite")

    monkeypatch.setattr(form_fill, "db_execute", forbid_db)
    return sent


def callbacks(keyboard) -> set[str]:
    return {
        str(button.get("callback_data"))
        for row in keyboard["inline_keyboard"]
        for button in row
        if button.get("callback_data")
    }


def test_my_forms_lists_paginated_server_responses_and_keeps_legacy_history_separate(monkeypatch):
    sent = capture(monkeypatch)
    pages = {
        0: history([item(index) for index in range(1, 7)], total=7, pages=2),
        1: history([item(7, status="waitlisted")], page=1, total=7, pages=2),
    }
    requested = []
    monkeypatch.setattr(
        shared_api,
        "list_my_bot_form_responses",
        lambda user_id, page: requested.append((user_id, page)) or pages[page],
    )

    assert form_fill.show_my_forms(100, 73421) == "sent"
    _, first_text, first_keyboard = sent[-1]
    first_callbacks = callbacks(first_keyboard)
    assert requested == [(73421, 0)]
    assert "فرم‌های من (7)" in first_text
    assert "فرم مشترک 1" in first_text and "فرم مشترک 6" in first_text
    assert "فرم مشترک 7" not in first_text
    assert "سوابق محلی قدیمی" not in first_text
    assert "ffsr_123e4567-e89b-12d3-a456-000000000001" in first_callbacks
    assert "ffmypg_1" in first_callbacks
    assert "ff_local_forms" in first_callbacks

    assert form_fill.show_my_forms(100, 73421, 1) == "sent"
    _, second_text, second_keyboard = sent[-1]
    assert requested[-1] == (73421, 1)
    assert "فرم مشترک 7" in second_text
    assert "فهرست انتظار" in second_text
    assert "ffmypg_0" in callbacks(second_keyboard)


def test_empty_or_unavailable_shared_history_never_substitutes_local_rows(monkeypatch):
    sent = capture(monkeypatch)
    monkeypatch.setattr(
        shared_api, "list_my_bot_form_responses", lambda *_args: history([], pages=0)
    )

    form_fill.show_my_forms(100, 73421)
    _, empty_text, empty_keyboard = sent[-1]
    assert "پایگاه مشترک" in empty_text
    assert "هنوز پاسخی" in empty_text
    assert "ff_local_forms" in callbacks(empty_keyboard)

    monkeypatch.setattr(
        shared_api,
        "list_my_bot_form_responses",
        lambda *_args: (_ for _ in ()).throw(
            shared_api.SharedAPIError(503, "shared_api_unreachable")
        ),
    )
    form_fill.show_my_forms(100, 73421)
    _, error_text, error_keyboard = sent[-1]
    assert "پایگاه مشترک" in error_text
    assert "جایگزین نمی‌شود" in error_text
    assert "ff_myforms" in callbacks(error_keyboard)
    assert "ff_local_forms" not in callbacks(error_keyboard)


def test_shared_response_detail_shows_server_snapshot_and_waitlist_status(monkeypatch):
    sent = capture(monkeypatch)
    detail = {
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
                "fields": [
                    {"id": "full-name", "type": "text", "label": "نام کامل"},
                    {"id": "city", "type": "select", "label": "شهر"},
                ],
            },
            "answers": {"full-name": "لیلا", "city": "تهران"},
        },
    }
    requested = []
    monkeypatch.setattr(
        shared_api,
        "get_my_bot_form_response",
        lambda user_id, response_id: requested.append((user_id, response_id)) or detail,
    )

    assert form_fill.show_shared_response(100, 73421, RESPONSE_ID) == "sent"
    _, text, keyboard = sent[-1]
    assert requested == [(73421, RESPONSE_ID)]
    assert "فرم مشترک" in text
    assert "فهرست انتظار" in text and "تأیید نهایی نیست" in text
    assert "نام کامل" in text and "لیلا" in text
    assert "شهر" in text and "تهران" in text
    assert "مدل بلیت:" not in text
    assert "ff_myforms" in callbacks(keyboard)

    accepted_detail = {
        **detail,
        "response": {
            **detail["response"],
            "status": "accepted",
            "form_snapshot": {
                **detail["response"]["form_snapshot"],
                "ticket_type": {"id": "priority", "name": "ورودی ویژه"},
            },
        },
    }
    monkeypatch.setattr(
        shared_api,
        "get_my_bot_form_response",
        lambda *_args: accepted_detail,
    )
    form_fill.show_shared_response(100, 73421, RESPONSE_ID)
    assert "مدل بلیت: ورودی ویژه" in sent[-1][1]


def test_shared_response_not_found_and_invalid_id_are_safe(monkeypatch):
    sent = capture(monkeypatch)
    calls = []
    monkeypatch.setattr(
        shared_api,
        "get_my_bot_form_response",
        lambda user_id, response_id: (
            calls.append((user_id, response_id))
            or (_ for _ in ()).throw(shared_api.SharedAPIError(404, "bot_form_response_not_found"))
        ),
    )

    form_fill.show_shared_response(100, 73421, RESPONSE_ID)
    assert "به حساب بلهٔ شما تعلق ندارد" in sent[-1][1]
    assert calls == [(73421, RESPONSE_ID)]

    before = len(calls)
    form_fill.show_shared_response(100, 73421, "../unsafe")
    assert len(calls) == before
    assert "دکمهٔ پاسخ معتبر نیست" in sent[-1][1]
