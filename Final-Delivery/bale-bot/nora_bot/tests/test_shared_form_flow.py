"""Conversational form flow keeps answers in the shared API draft only."""
# ruff: noqa: INP001, RUF001

from __future__ import annotations

import sys
from pathlib import Path


BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

import shared_api  # noqa: E402
import shared_form_flow as flow  # noqa: E402


FORM_ID = "123e4567-e89b-12d3-a456-426614174000"
SESSION_KEY = "s" * 43


def result(*, answers=None, visible=None, fields=None, submitted=False, status="draft"):
    fields = fields or [
        {"id": "full-name", "t": "text", "l": "نام کامل", "req": True},
        {"id": "city", "t": "select", "l": "شهر", "options": ["تهران", "پاریس"]},
    ]
    return {
        "source": "shared_server_database",
        "form": {
            "id": FORM_ID,
            "name": "فرم گفتگومحور",
            "model": "registration",
            "need": "reg",
            "status": "published",
            "version": 2,
            "fields": fields,
        },
        "draft": {
            "answers": answers or {},
            "submitted": submitted,
            "status": status,
            "form_version": 2,
        },
        "visible_field_ids": visible or ["full-name"],
    }


def harness(monkeypatch):
    stored = {"state": None, "data": {}}
    messages = []

    monkeypatch.setattr(flow, "get_state_name", lambda _uid: stored["state"])
    monkeypatch.setattr(flow, "get_state_data", lambda _uid: dict(stored["data"]))

    def set_state(_uid, state, data=None, merge=True):
        stored["state"] = state
        if merge:
            stored["data"].update(data or {})
        else:
            stored["data"] = dict(data or {})
        return dict(stored["data"])

    def update_state_data(_uid, patch):
        stored["data"].update(patch or {})
        return dict(stored["data"])

    def clear_state(_uid):
        stored["state"] = None
        stored["data"] = {}

    monkeypatch.setattr(flow, "set_state", set_state)
    monkeypatch.setattr(flow, "update_state_data", update_state_data)
    monkeypatch.setattr(flow, "clear_state", clear_state)
    monkeypatch.setattr(
        flow,
        "send",
        lambda cid, text, keyboard=None: messages.append((cid, text, keyboard)) or "sent",
    )
    monkeypatch.setattr(
        flow,
        "send_or_edit",
        lambda cid, text, keyboard=None: messages.append((cid, text, keyboard)) or "sent",
    )
    return stored, messages


def test_user_facing_recovery_copy_avoids_auth_session_jargon(monkeypatch):
    stored, messages = harness(monkeypatch)
    copy = [flow._api_error_text(shared_api.SharedAPIError(404, "draft_not_found"))]
    flow._starting_notice(100)
    flow._load(100, 73421)
    flow.cancel(100, 73421)
    flow.submit(100, 73421)
    copy.extend(message for _chat_id, message, _keyboard in messages)
    assert copy and all("نشست" not in message for message in copy)
    assert "فرایند پاسخ‌گویی" in copy[0]
    assert stored["state"] is None


def test_shared_conversation_tracks_only_pointer_and_follows_server_visibility(monkeypatch):
    stored, messages = harness(monkeypatch)
    server = {"value": result()}
    calls = []

    def start(user_id, form_id, session_key):
        calls.append(("start", user_id, form_id, session_key))
        return server["value"]

    def get_draft(user_id, form_id, session_key):
        calls.append(("get", user_id, form_id, session_key))
        return server["value"]

    def save(user_id, form_id, _session_key, field_id, value=None, *, remove=False):
        calls.append(("save", user_id, form_id, field_id, value, remove))
        answers = dict(server["value"]["draft"]["answers"])
        if remove:
            answers.pop(field_id, None)
        else:
            answers[field_id] = value
        server["value"] = result(
            answers=answers,
            visible=["full-name", "city"] if answers.get("full-name") else ["full-name"],
        )
        return server["value"]

    monkeypatch.setattr(shared_api, "start_bot_form_draft", start)
    monkeypatch.setattr(shared_api, "get_bot_form_draft", get_draft)
    monkeypatch.setattr(shared_api, "save_bot_form_answer", save)

    assert flow.start(100, 73421, FORM_ID) == "sent"
    assert calls[0] == ("start", 73421, FORM_ID, SESSION_KEY) or calls[0][:3] == (
        "start",
        73421,
        FORM_ID,
    )
    assert stored["state"] == flow.STATE
    assert stored["data"]["current_field_id"] == "full-name"
    assert "answers" not in stored["data"]
    assert "لیلا" not in str(stored["data"])

    assert flow.handle_input(100, 73421, "لیلا") == "sent"
    assert calls[-1] == ("save", 73421, FORM_ID, "full-name", "لیلا", False)
    assert stored["data"]["current_field_id"] == "city"
    assert "answers" not in stored["data"]
    assert "شهر" in messages[-1][1]
    assert server["value"]["visible_field_ids"] == ["full-name", "city"]


def test_repeated_start_refreshes_the_active_server_draft(monkeypatch):
    stored, _messages = harness(monkeypatch)
    server = result()
    created_sessions = []
    refreshed_sessions = []

    def start(_user_id, _form_id, session_key):
        created_sessions.append(session_key)
        return server

    def get_draft(_user_id, _form_id, session_key):
        refreshed_sessions.append(session_key)
        return server

    monkeypatch.setattr(shared_api, "start_bot_form_draft", start)
    monkeypatch.setattr(shared_api, "get_bot_form_draft", get_draft)
    flow.start(100, 73421, FORM_ID)
    first_session = stored["data"]["session_key"]
    flow.start(100, 73421, FORM_ID)

    assert created_sessions == [first_session]
    assert refreshed_sessions == [first_session]
    assert stored["data"]["session_key"] == first_session


def test_start_retry_reuses_the_session_key_after_a_lost_api_response(monkeypatch):
    stored, _messages = harness(monkeypatch)
    server = result()
    attempts = []

    def start(_user_id, _form_id, session_key):
        attempts.append(session_key)
        if len(attempts) == 1:
            raise shared_api.SharedAPIError(0, "shared_api_unreachable")
        return server

    monkeypatch.setattr(shared_api, "start_bot_form_draft", start)
    flow.start(100, 73421, FORM_ID)
    pending_session = stored["data"]["session_key"]
    assert stored["data"]["starting"] is True
    assert "answers" not in stored["data"]

    flow.handle_callback(100, 73421, "bff_refresh")

    assert attempts == [pending_session, pending_session]
    assert "starting" not in stored["data"]
    assert stored["data"]["session_key"] == pending_session


def test_multi_choice_tap_retries_are_set_operations_not_duplicate_toggles(monkeypatch):
    stored, messages = harness(monkeypatch)
    multi_fields = [
        {
            "id": "topics",
            "t": "multi",
            "l": "موضوع‌ها",
            "options": ["هنر", "علم"],
            "req": True,
        }
    ]
    server = {"value": result(fields=multi_fields, visible=["topics"])}
    saved_values = []

    monkeypatch.setattr(shared_api, "start_bot_form_draft", lambda *_args: server["value"])
    monkeypatch.setattr(shared_api, "get_bot_form_draft", lambda *_args: server["value"])

    def save(_user, _form, _session, field_id, value=None, *, remove=False):
        assert field_id == "topics" and not remove
        saved_values.append(list(value))
        server["value"] = result(
            fields=multi_fields,
            answers={"topics": list(value)},
            visible=["topics"],
        )
        return server["value"]

    monkeypatch.setattr(shared_api, "save_bot_form_answer", save)
    flow.start(100, 73421, FORM_ID)

    flow.handle_callback(100, 73421, "bffmadd_0")
    flow.handle_callback(100, 73421, "bffmadd_0")
    assert saved_values == [["هنر"], ["هنر"]]
    assert server["value"]["draft"]["answers"]["topics"] == ["هنر"]
    assert "answers" not in stored["data"]
    assert any("موضوع‌ها" in message[1] for message in messages)


def test_optional_multi_choice_can_continue_with_no_selection(monkeypatch):
    stored, messages = harness(monkeypatch)
    fields = [
        {
            "id": "topics",
            "t": "multi",
            "l": "موضوع‌ها",
            "options": ["هنر", "علم"],
            "req": False,
        }
    ]
    server = result(fields=fields, visible=["topics"])
    saves = []

    monkeypatch.setattr(shared_api, "start_bot_form_draft", lambda *_args: server)
    monkeypatch.setattr(shared_api, "get_bot_form_draft", lambda *_args: server)

    def save(_user, _form, _session, field_id, value=None, *, remove=False):
        saves.append((field_id, value, remove))
        return server

    monkeypatch.setattr(shared_api, "save_bot_form_answer", save)
    flow.start(100, 73421, FORM_ID)
    flow.handle_callback(100, 73421, "bff_multi_done")

    assert saves == [("topics", None, True)]
    assert stored["data"]["skipped_fields"] == ["topics"]
    assert "رد شده" in messages[-1][1]
    assert "answers" not in stored["data"]


def test_api_failure_does_not_copy_typed_answer_into_local_state(monkeypatch):
    stored, messages = harness(monkeypatch)
    server = result()
    monkeypatch.setattr(shared_api, "start_bot_form_draft", lambda *_args: server)
    monkeypatch.setattr(shared_api, "get_bot_form_draft", lambda *_args: server)

    def fail_save(*_args, **_kwargs):
        raise shared_api.SharedAPIError(0, "shared_api_unreachable")

    monkeypatch.setattr(shared_api, "save_bot_form_answer", fail_save)
    flow.start(100, 73421, FORM_ID)
    flow.handle_input(100, 73421, "پاسخ خصوصی")

    assert "answers" not in stored["data"]
    assert "پاسخ خصوصی" not in str(stored["data"])
    assert "پاسخ محلی ذخیره نشده" in messages[-1][1]


def test_submit_message_clears_pointer_only_after_server_confirmation(monkeypatch):
    stored, messages = harness(monkeypatch)
    server = result()
    calls = []
    ticket_calls = []
    monkeypatch.setattr(
        flow.shared_form_ticket,
        "deliver_response",
        lambda *args: ticket_calls.append(args) or "ticket-sent",
    )
    monkeypatch.setattr(shared_api, "start_bot_form_draft", lambda *_args: server)
    monkeypatch.setattr(
        shared_api,
        "submit_bot_form_response",
        lambda *args: (
            calls.append(args)
            or {
                "accepted": True,
                "already_submitted": False,
                "response_id": "123e4567-e89b-12d3-a456-426614174001",
                "status": "accepted",
                "form_version": 2,
            }
        ),
    )

    flow.start(100, 73421, FORM_ID)
    assert flow.submit(100, 73421) == "sent"
    assert calls == [(73421, FORM_ID, SESSION_KEY)] or (
        len(calls) == 1 and calls[0][0:2] == (73421, FORM_ID)
    )
    assert stored == {"state": None, "data": {}}
    assert "پایگاه مشترک" in messages[-1][1]
    assert ticket_calls == [(100, 73421, FORM_ID, "123e4567-e89b-12d3-a456-426614174001")]
