"""The bot's active-form menu is sourced from the shared server catalog only."""
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


def capture(monkeypatch):
    sent = []
    monkeypatch.setattr(
        form_fill,
        "send_or_edit",
        lambda cid, text, keyboard=None: sent.append((cid, text, keyboard)) or "sent",
    )

    def forbid_db(*_args, **_kwargs):
        pytest.fail("public catalog must not read bot SQLite")

    monkeypatch.setattr(form_fill, "db_execute", forbid_db)
    return sent


def form(index: int) -> dict:
    return {
        "id": f"123e4567-e89b-12d3-a456-{index:012d}",
        "name": f"فرم مشترک {index}",
        "model": "registration",
        "need": "reg",
        "version": 2,
    }


def test_catalog_uses_server_items_and_minapp_links_with_pagination(monkeypatch):
    sent = capture(monkeypatch)
    catalog = [form(index) for index in range(1, 8)]
    calls = []
    monkeypatch.setattr(
        shared_api, "list_public_forms", lambda: calls.append("server") or catalog
    )
    monkeypatch.setattr(form_fill, "NORA_WEBAPP_URL", "https://lifeline1.ir")

    assert form_fill.show_public_forms(100, 73421) == "sent"
    assert calls == ["server"]
    _, text, keyboard = sent[-1]
    assert "فرم مشترک 1" in text and "فرم مشترک 6" in text
    assert "فرم مشترک 7" not in text
    buttons = [button for row in keyboard["inline_keyboard"] for button in row]
    form_buttons = [button for button in buttons if "web_app" in button]
    assert len(form_buttons) == 6
    conversation_buttons = [
        button
        for button in buttons
        if str(button.get("callback_data", "")).startswith("bffstart_")
    ]
    assert len(conversation_buttons) == 6
    assert conversation_buttons[0]["callback_data"] == (
        "bffstart_123e4567-e89b-12d3-a456-000000000001"
    )
    assert form_buttons[0]["web_app"]["url"] == (
        "https://lifeline1.ir/form.html?fid=123e4567-e89b-12d3-a456-000000000001"
    )
    assert any(button.get("callback_data") == "ffpg_1" for button in buttons)
    assert not any(str(button.get("callback_data", "")).startswith("ffopen_") for button in buttons)

    form_fill.show_public_forms(100, 73421, 1)
    _, second_page_text, second_keyboard = sent[-1]
    assert "فرم مشترک 7" in second_page_text
    assert sum(
        "web_app" in button
        for row in second_keyboard["inline_keyboard"]
        for button in row
    ) == 1


def test_api_failure_shows_retry_and_never_falls_back_to_sqlite(monkeypatch):
    sent = capture(monkeypatch)
    monkeypatch.setattr(
        shared_api,
        "list_public_forms",
        lambda: (_ for _ in ()).throw(shared_api.SharedAPIError(503, "shared_api_unreachable")),
    )

    form_fill.show_public_forms(100, 73421)
    _, text, keyboard = sent[-1]
    assert "پایگاه مشترک" in text
    assert "جایگزین نمی‌شود" in text
    callbacks = {
        button.get("callback_data")
        for row in keyboard["inline_keyboard"]
        for button in row
    }
    assert "ffpg_0" in callbacks
    assert "ff_myforms" not in callbacks


def test_missing_miniapp_url_does_not_make_a_local_form_button(monkeypatch):
    sent = capture(monkeypatch)
    monkeypatch.setattr(shared_api, "list_public_forms", lambda: [form(1)])
    monkeypatch.setattr(form_fill, "NORA_WEBAPP_URL", "")

    form_fill.show_public_forms(100, 73421)
    _, text, keyboard = sent[-1]
    assert "نشانی وب‌اپ" in text
    assert not any(
        "web_app" in button
        for row in keyboard["inline_keyboard"]
        for button in row
    )


def test_empty_catalog_does_not_show_old_local_forms(monkeypatch):
    sent = capture(monkeypatch)
    monkeypatch.setattr(shared_api, "list_public_forms", list)

    form_fill.show_public_forms(100, 73421)
    _, text, keyboard = sent[-1]
    assert "پایگاه مشترک" in text
    assert "قابل‌پاسخی" in text
    callbacks = {
        button.get("callback_data")
        for row in keyboard["inline_keyboard"]
        for button in row
    }
    # Server response history remains separate from the active-form catalog.
    assert "ff_myforms" in callbacks
