"""Legacy review buttons and rejection states must never write local decisions."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

_TMP = tempfile.mkdtemp(prefix="nora_shared_review_")
os.environ.update({
    "BOT_TOKEN": "1095412158:T",
    "SUPER_ADMIN_ID": "100000001",
    "SAFIR_API_KEY": "test-key",
    "SAFIR_BOT_ID": "317041514",
    "PAYMENT_PROVIDER_TOKEN": "WALLET-TEST-1111111111111111",
    "DB_PATH": f"{_TMP}/nora.db",
    "BACKUP_DIR": f"{_TMP}/backup",
    "IMPORT_DIR": f"{_TMP}/import",
    "FILES_DIR": f"{_TMP}/files",
    "PROFILES_DIR": f"{_TMP}/files/profiles",
    "EVENTS_DIR": f"{_TMP}/files/events",
    "LOG_DIR": f"{_TMP}/logs",
})

import main as bot  # noqa: E402


def _prepare_callback_router(monkeypatch):
    monkeypatch.setattr(bot, "_menu_flags", lambda _uid: (False, False))
    monkeypatch.setattr(bot, "set_context", lambda *a, **k: None)
    monkeypatch.setattr(bot, "answer_callback", lambda *_: None)
    monkeypatch.setattr(bot, "log", lambda *_: None)
    monkeypatch.setattr(bot, "is_blocked", lambda _uid: False)


def _callback(callback_data):
    return {
        "id": "callback-1",
        "from": {"id": 456},
        "data": callback_data,
        "message": {"message_id": 9, "chat": {"id": 456}},
    }


def test_startup_refuses_non_owner_before_initializing_local_database(monkeypatch):
    import shared_api

    monkeypatch.setenv("NORA_BOT_ALLOW_LEGACY_SQLITE", "1")
    monkeypatch.setattr(bot.guard, "check_files", lambda _log: [])
    monkeypatch.setattr(bot.guard, "check_new_features", lambda: {})
    monkeypatch.setattr(bot.guard, "code_fingerprint", lambda: ("test", 0, 0))
    monkeypatch.setattr(bot.guard, "acquire_lock", lambda _log: (True, ""))
    monkeypatch.setattr(bot.guard, "release_lock", lambda: None)
    monkeypatch.setattr(bot, "check_config", lambda: [])
    monkeypatch.setattr(bot, "log", lambda *_args: None)
    monkeypatch.setattr(
        shared_api,
        "require_owner_identity",
        lambda _uid: (_ for _ in ()).throw(
            shared_api.SharedAPIError(403, "shared_owner_identity_required")
        ),
    )
    monkeypatch.setattr(
        bot,
        "init_db",
        lambda: pytest.fail("SQLite must not initialize for a non-owner operator"),
    )

    assert bot.main() == 1


@pytest.mark.parametrize(
    ("callback_data", "handler_name", "expected_args"),
    [
        ("admin_stats", "show_dashboard", (456, 456)),
        ("admin_stats_old", "show_dashboard", (456, 456)),
        ("rp_period", "show_periods", (456, 456)),
        ("rp_p_7d", "pick_period", (456, 456, "7d")),
        ("rp_users", "show_section", (456, 456, "rp_users")),
        ("rp_forms", "show_section", (456, 456, "rp_forms")),
        ("rp_finance", "show_section", (456, 456, "rp_finance")),
        ("rp_export", "show_section", (456, 456, "rp_export")),
    ],
)
def test_bot_report_callbacks_use_shared_report_handlers(
    monkeypatch, callback_data, handler_name, expected_args
):
    calls = []
    _prepare_callback_router(monkeypatch)
    for name in ("show_dashboard", "show_periods", "pick_period", "show_section"):
        monkeypatch.setattr(
            bot.shared_reports_mod,
            name,
            lambda *args, _name=name: calls.append((_name, args)) or "shared-report",
        )

    result = bot.handle_callback(_callback(callback_data))

    assert result == "shared-report"
    assert calls == [(handler_name, expected_args)]


@pytest.mark.parametrize(
    ("callback_data", "handler_name", "expected_args"),
    [
        ("sfr_forms", "show_forms", (456, 456, 0)),
        ("sfrl_2", "show_forms", (456, 456, 2)),
        ("sfrl_bad", "show_forms", (456, 456, -1)),
        (
            "sfrf_123e4567-e89b-12d3-a456-426614174000",
            "show_responses",
            (456, 456, "123e4567-e89b-12d3-a456-426614174000", 0),
        ),
        (
            "sfrp_123e4567-e89b-12d3-a456-426614174000_3",
            "show_responses",
            (456, 456, "123e4567-e89b-12d3-a456-426614174000", 3),
        ),
        (
            "sfrd_123e4567-e89b-12d3-a456-426614174001",
            "show_response",
            (456, 456, "123e4567-e89b-12d3-a456-426614174001"),
        ),
    ],
)
def test_server_form_report_callbacks_reach_read_only_handlers(
    monkeypatch, callback_data, handler_name, expected_args
):
    calls = []
    _prepare_callback_router(monkeypatch)
    for name in ("show_forms", "show_responses", "show_response", "invalid_callback"):
        monkeypatch.setattr(
            bot.shared_form_reports_mod,
            name,
            lambda *args, _name=name: calls.append((_name, args)) or "shared-form-report",
        )

    result = bot.handle_callback(_callback(callback_data))

    assert result == "shared-form-report"
    assert calls == [(handler_name, expected_args)]


@pytest.mark.parametrize(
    ("callback_data", "kind", "legacy_action"),
    [
        ("admin_subs", "profile_review", False),
        ("sa_23", "profile_review", True),
        ("sr_23", "profile_review", True),
        ("pay_receipts", "receipt_review", False),
        ("rcpok_23", "receipt_review", True),
        ("rcpno_23", "receipt_review", True),
    ],
)
def test_legacy_review_callbacks_only_open_shared_inbox(
    monkeypatch, callback_data, kind, legacy_action
):
    calls = []
    _prepare_callback_router(monkeypatch)
    monkeypatch.setattr(
        bot, "_show_shared_review_inbox",
        lambda cid, uid, actual_kind, **kwargs:
            calls.append((cid, uid, actual_kind, kwargs.get("legacy_action", False))) or "shared",
    )

    result = bot.handle_callback(_callback(callback_data))

    assert result == "shared"
    assert calls == [(456, 456, kind, legacy_action)]


@pytest.mark.parametrize(
    ("state_name", "kind"),
    [
        (bot.profile_mod.STATE_REJECT, "profile_review"),
        ("rcp_reject", "receipt_review"),
    ],
)
def test_legacy_rejection_states_are_cleared_without_local_handlers(
    monkeypatch, state_name, kind
):
    cleared = []
    opened = []
    sent = []
    monkeypatch.setattr(bot, "log", lambda *_: None)
    monkeypatch.setattr(bot, "clear_context", lambda *_: None)
    monkeypatch.setattr(bot, "_menu_flags", lambda _uid: (False, False))
    monkeypatch.setattr(bot, "set_context", lambda *a, **k: None)
    monkeypatch.setattr(bot, "is_blocked", lambda _uid: False)
    monkeypatch.setattr(bot, "get_state_name", lambda _uid: state_name)
    monkeypatch.setattr(bot, "clear_state", lambda uid: cleared.append(uid))
    monkeypatch.setattr(bot, "send", lambda cid, text, *a, **k: sent.append((cid, text)))
    monkeypatch.setattr(
        bot, "_show_shared_review_inbox",
        lambda cid, uid, actual_kind: opened.append((cid, uid, actual_kind)) or "shared",
    )
    monkeypatch.setattr(
        bot.profile_mod, "handle_reject_reason",
        lambda *_: pytest.fail("legacy profile rejection handler was called"),
    )
    monkeypatch.setattr(
        bot.pay_mod, "handle_reject_receipt",
        lambda *_: pytest.fail("legacy receipt rejection handler was called"),
    )

    result = bot.process_message({
        "from": {"id": 456, "first_name": "Tester"},
        "chat": {"id": 456, "type": "private"},
        "text": "رد قدیمی",
    })

    assert result == "shared"
    assert cleared == [456]
    assert opened == [(456, 456, kind)]
    assert sent and "SQLite" in sent[0][1]


def test_legacy_module_decision_functions_fail_closed_without_sqlite_writes(monkeypatch):
    inbox = []
    notices = []
    cleared = []

    def forbidden_sql(*_args, **_kwargs):
        pytest.fail("legacy review function accessed the local decision tables")

    monkeypatch.setattr(bot.profile_mod, "db_execute", forbidden_sql)
    monkeypatch.setattr(bot.pay_mod, "db_execute", forbidden_sql)
    monkeypatch.setattr(bot.profile_mod, "set_state", forbidden_sql)
    monkeypatch.setattr(bot.pay_mod, "set_state", forbidden_sql)
    monkeypatch.setattr(
        bot.profile_mod, "clear_state", lambda uid: cleared.append(("profile", uid))
    )
    monkeypatch.setattr(
        bot.pay_mod, "clear_state", lambda uid: cleared.append(("receipt", uid))
    )
    monkeypatch.setattr(
        bot.profile_mod, "send", lambda cid, text, *a, **k: notices.append(text)
    )
    monkeypatch.setattr(
        bot.pay_mod, "send", lambda cid, text, *a, **k: notices.append(text)
    )
    monkeypatch.setattr(
        bot.shared_workflows_mod, "show_inbox",
        lambda cid, uid, *, kind=None: inbox.append((cid, uid, kind)) or "shared",
    )

    assert bot.profile_mod.approve_sub(456, 456, 11) == "shared"
    assert bot.profile_mod.start_reject(456, 456, 11) == "shared"
    assert bot.profile_mod.reject_sub(456, 456, 11, "reason") == "shared"
    assert bot.profile_mod.handle_reject_reason({
        "from": {"id": 456}, "chat": {"id": 456}, "text": "reason",
    }) == "shared"
    assert bot.pay_mod.approve_receipt(456, 456, 12) == "shared"
    assert bot.pay_mod.start_reject_receipt(456, 456, 12) == "shared"
    assert bot.pay_mod.handle_reject_receipt({
        "from": {"id": 456}, "chat": {"id": 456}, "text": "reason",
    }) == "shared"

    assert inbox == [(456, 456, "profile_review")] * 4 + [
        (456, 456, "receipt_review")
    ] * 3
    assert cleared == [("profile", 456), ("receipt", 456)]
    assert len(notices) == 7


def test_shared_inbox_warns_about_unmigrated_local_items_but_never_decides(monkeypatch):
    queries = []
    inbox = []
    monkeypatch.setattr(
        bot, "db_scalar",
        lambda query, default=0: queries.append(query) or 2,
    )
    monkeypatch.setattr(
        bot.shared_workflows_mod, "show_inbox",
        lambda cid, uid, *, kind=None, pre_list_notice=None, unavailable_notice=None:
            inbox.append((cid, uid, kind, pre_list_notice, unavailable_notice)) or "inbox",
    )

    result = bot._show_shared_review_inbox(456, 456, "receipt_review")

    assert result == "inbox"
    assert queries == [
        "SELECT COUNT(*) FROM payment_receipts "
        "WHERE status='pending' AND COALESCE(shared_task_id,'')=''"
    ]
    assert "در SQLite ربات مانده" in inbox[0][3]
    assert inbox[0][:3] == (456, 456, "receipt_review")
    assert "درخواست‌های قدیمی" in inbox[0][4]


def test_unavailable_server_gives_clear_read_only_legacy_message(monkeypatch):
    sent = []

    def unavailable(_uid):
        raise bot.shared_workflows_mod.shared_api.SharedAPIError(
            503, "shared_api_not_configured"
        )

    monkeypatch.setattr(
        bot.shared_workflows_mod.shared_api, "get_identity", unavailable
    )
    monkeypatch.setattr(
        bot.shared_workflows_mod, "send",
        lambda cid, text, *a, **k: sent.append(text),
    )
    monkeypatch.setattr(bot, "db_scalar", lambda *_a, **_k: 5)

    bot._show_shared_review_inbox(456, 456, "receipt_review")

    assert any("درخواست‌های قدیمی" in text for text in sent)
    assert any("کارتابل در دسترس نیست" in text for text in sent)
    assert all("5" not in text for text in sent)


def test_legacy_count_is_not_disclosed_without_server_permission(monkeypatch):
    from types import SimpleNamespace

    sent = []
    monkeypatch.setattr(
        bot.shared_workflows_mod.shared_api, "get_identity",
        lambda _uid: SimpleNamespace(has_permission=lambda _permission: False),
    )
    monkeypatch.setattr(
        bot.shared_workflows_mod.shared_api, "list_workflows",
        lambda *_a, **_k: pytest.fail("unauthorized inbox queried"),
    )
    monkeypatch.setattr(bot, "send", lambda cid, text, *a, **k: sent.append(text))
    monkeypatch.setattr(
        bot.shared_workflows_mod, "send",
        lambda cid, text, *a, **k: sent.append(text),
    )
    monkeypatch.setattr(bot, "db_scalar", lambda *_a, **_k: 5)

    bot._show_shared_review_inbox(456, 456, "receipt_review")

    assert sent and "دسترسی این بخش" in sent[-1]
    assert all("5" not in text and "SQLite ربات مانده" not in text for text in sent)


@pytest.mark.parametrize(
    ("callback_data", "approved"),
    [("plrok_23", True), ("plrno_23", False)],
)
def test_paylink_receipt_routes_remain_separate(monkeypatch, callback_data, approved):
    calls = []
    _prepare_callback_router(monkeypatch)
    monkeypatch.setattr(
        bot.pay_mod, "approve_paylink_receipt",
        lambda cid, uid, receipt_id, decision:
            calls.append((cid, uid, receipt_id, decision)) or "paylink",
    )

    result = bot.handle_callback(_callback(callback_data))

    assert result == "paylink"
    assert calls == [(456, 456, 23, approved)]
