"""Bot report menus must read authorized aggregates from the shared API only."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

import shared_api
import shared_reports


@pytest.fixture(autouse=True)
def reset_periods():
    shared_reports._SELECTED_PERIOD.clear()
    yield
    shared_reports._SELECTED_PERIOD.clear()


def report(period="30d"):
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
        "coverage": {"financial_amounts": "not_included"},
    }


def identity(role="manager", permissions=None):
    granted = set({"rp_view", "rp_export"} if permissions is None else permissions)
    return SimpleNamespace(role=role, has_permission=lambda key: key in granted)


def capture(monkeypatch):
    sent = []
    monkeypatch.setattr(
        shared_reports, "send_or_edit",
        lambda cid, text, keyboard=None: sent.append((cid, text, keyboard)) or "sent",
    )
    return sent


def test_dashboard_reads_only_aggregate_from_shared_api(monkeypatch):
    sent = capture(monkeypatch)
    calls = []
    monkeypatch.setattr(shared_api, "get_identity", lambda uid: identity())
    monkeypatch.setattr(
        shared_api, "get_report_summary",
        lambda uid, period: calls.append((uid, period)) or report(period),
    )

    assert shared_reports.show_dashboard(100, 73421) == "sent"
    assert calls == [(73421, "30d")]
    text = sent[0][1]
    assert "گزارش‌های زندهٔ پایگاه مشترک" in text
    assert "پاسخ‌های نهایی این دوره: ۸" in text
    assert "درخواست‌های بررسی این دوره: ۲" in text
    assert "SQLite ربات جایگزین نمی‌شود" in text
    assert "987654" not in text
    callbacks = {
        button["callback_data"]
        for row in sent[0][2]["inline_keyboard"]
        for button in row
    }
    assert {"rp_users", "rp_forms", "rp_notify", "rp_period"} <= callbacks
    assert "rp_finance" not in callbacks  # canonical manager role has no finance report access


def test_bot_period_selection_uses_server_periods_without_local_database(monkeypatch):
    sent = capture(monkeypatch)
    calls = []
    monkeypatch.setattr(shared_api, "get_identity", lambda uid: identity())
    monkeypatch.setattr(
        shared_api, "get_report_summary",
        lambda uid, period: calls.append((uid, period)) or report(period),
    )

    shared_reports.show_periods(100, 73421)
    period_buttons = [
        button["callback_data"]
        for row in sent[-1][2]["inline_keyboard"]
        for button in row
        if button["callback_data"].startswith("rp_p_")
    ]
    assert period_buttons == [
        "rp_p_today", "rp_p_yesterday", "rp_p_7d", "rp_p_30d",
        "rp_p_90d", "rp_p_year", "rp_p_all",
    ]

    shared_reports.pick_period(100, 73421, "today")
    assert calls == [(73421, "today")]
    assert "امروز" in sent[-1][1]
    assert shared_reports.pick_period(100, 73421, "custom") == "sent"
    assert calls == [(73421, "today")]


def test_supported_detail_views_are_aggregate_and_other_domains_fail_closed(monkeypatch):
    sent = capture(monkeypatch)
    calls = []
    monkeypatch.setattr(
        shared_api, "get_identity", lambda uid: identity(permissions={"rp_view", "rp_export", "fm_responses"})
    )
    monkeypatch.setattr(
        shared_api, "get_report_summary",
        lambda uid, period: calls.append((uid, period)) or report(period),
    )

    shared_reports.show_section(100, 73421, "rp_forms")
    assert calls == [(73421, "30d")]
    assert "کل فرم‌های سرور: ۳" in sent[-1][1]
    assert "پروفایل" in sent[-1][1] and "فیش" in sent[-1][1]
    assert "amount" not in sent[-1][1]
    assert any(
        button.get("callback_data") == "sfr_forms"
        for row in sent[-1][2]["inline_keyboard"]
        for button in row
    )

    calls.clear()
    for key in ("rp_events", "rp_att", "rp_certs", "rp_top", "rp_export"):
        shared_reports.show_section(100, 73421, key)
        assert "هنوز در پایگاه مشترک ثبت نمی‌شود" in sent[-1][1]
    for key in ("rp_finance", "rp_admins"):
        shared_reports.show_section(100, 73421, key)
        assert "فقط برای مالک" in sent[-1][1]
    assert calls == []


def test_missing_server_permission_and_api_failure_never_fall_back(monkeypatch):
    sent = capture(monkeypatch)
    report_calls = []
    monkeypatch.setattr(shared_api, "get_identity", lambda uid: identity(permissions=set()))
    monkeypatch.setattr(
        shared_api, "get_report_summary",
        lambda *args: report_calls.append(args) or pytest.fail("unauthorized report request"),
    )

    shared_reports.show_dashboard(100, 73421)
    assert "دسترسی به داشبورد" in sent[-1][1]
    assert report_calls == []

    monkeypatch.setattr(shared_api, "get_identity", lambda uid: identity())
    monkeypatch.setattr(
        shared_api, "get_report_summary",
        lambda *args: (_ for _ in ()).throw(shared_api.SharedAPIError(0, "shared_api_unreachable")),
    )
    shared_reports.show_dashboard(100, 73421)
    assert "پایگاه مشترک در دسترس نیست" in sent[-1][1]
    assert "محلی" in sent[-1][1]


def test_server_form_response_link_is_hidden_without_fm_responses(monkeypatch):
    sent = capture(monkeypatch)
    monkeypatch.setattr(shared_api, "get_identity", lambda uid: identity())
    monkeypatch.setattr(shared_api, "get_report_summary", lambda uid, period: report(period))

    shared_reports.show_section(100, 73421, "rp_forms")
    callbacks = {
        button.get("callback_data")
        for row in sent[-1][2]["inline_keyboard"]
        for button in row
    }
    assert "sfr_forms" not in callbacks
