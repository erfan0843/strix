"""فاز ۹.۳ — سیاست گواهی حضور رویداد در همان ماژول موجود ``eventcert`` (آفلاین).

* پیش‌فرض شرط صدور «حضور تأییدشده» می‌ماند.
* شرط‌های «فقط ثبت‌نام» و «پرداخت کامل» حذف نمی‌شوند، ولی ادمین هشدار صریح می‌بیند که
  گواهیِ آن‌ها گواهی حضور نیست؛ تغییر شرط با عامل در گزارش فعالیت ثبت می‌شود.
* خرید/پرداخت بدون حضور با شرط پیش‌فرض واجد شرایط نمی‌شود؛ کاربر غیرادمین نمی‌تواند شرط را عوض کند.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _points_fixture import ensure_test_env  # noqa: E402

ensure_test_env()

import bale_api  # noqa: E402
import database  # noqa: E402
import auth  # noqa: E402
import attendance  # noqa: E402
import certgen  # noqa: E402
import events as events_mod  # noqa: E402
import eventcert as ec  # noqa: E402

ADMIN = 7300001
MEMBER, STRANGER = 7301001, 7301002
SENT: list[tuple] = []


def _capture_send(cid, text, kb=None, *a, **k):
    SENT.append((cid, text))
    return {"ok": True, "result": {"message_id": len(SENT)}}


@pytest.fixture()
def db(tmp_path, monkeypatch):
    SENT.clear()
    monkeypatch.setattr(bale_api, "_raw_call", lambda m, p=None, **k: {"ok": True, "result": {}})
    monkeypatch.setattr(bale_api, "api_async", lambda m, p=None: {"ok": True})
    monkeypatch.setattr(bale_api, "send", _capture_send)
    monkeypatch.setattr(bale_api, "send_or_edit", _capture_send)
    monkeypatch.setattr(ec, "send", _capture_send)
    monkeypatch.setattr(ec, "send_or_edit", _capture_send)
    database.close_db()
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "evcert.db"))
    database._conn = None
    database.init_db()
    events_mod.init_event_tables()
    attendance.init_attendance_tables()
    certgen.init_cert_tables()
    database.seed_default_settings()
    database.db_execute(
        "INSERT INTO users (bale_user_id, first_name, last_name, is_authenticated, is_admin) VALUES (?,?,?,1,1)",
        (ADMIN, "مدیر", "آزمایشی"))
    for uid, first in ((MEMBER, "مریم"), (STRANGER, "سارا")):
        database.db_execute(
            "INSERT INTO users (bale_user_id, first_name, last_name, is_authenticated) VALUES (?,?,?,1)",
            (uid, first, "آزمایشی"))
    assert auth.is_admin(ADMIN) and not auth.is_admin(STRANGER)
    yield
    database.close_db()


def _texts():
    return [t for _cid, t in SENT]


def _actions(action):
    return [json.loads(r["action_data"] or "{}") for r in database.db_execute(
        "SELECT action_data FROM user_actions WHERE action_type=? ORDER BY id", (action,), fetch="all") or []]


def test_default_condition_is_attendance_and_payment_alone_never_qualifies(db):
    event_id = database.db_execute(
        "INSERT INTO events (title, event_type, location_type, start_date, status, created_by) VALUES (?,'workshop','onsite','1405/07/01','done',?)", ("کارگاه نجوم", ADMIN))
    row_id, err = ec.add_cert(event_id, "گواهی حضور", uid=ADMIN)
    assert err == "" and row_id
    cert = ec.get_cert(row_id)
    assert (cert.get("condition") or "present") == "present"          # پیش‌فرض = حضور تأییدشده
    assert ec.condition_policy_note(cert.get("condition")) == ""

    # ثبت‌نام + پرداخت کامل ولی بدون حضور → واجد شرایط نیست
    database.db_execute(
        "INSERT INTO event_registrations (event_id, bale_user_id, amount_paid, paid_at) VALUES (?,?,?,datetime('now'))",
        (event_id, MEMBER, 1500000))
    ok, why = ec.eligible(cert, event_id, MEMBER)
    assert not ok and "حضور" in why
    # کسی که اصلاً ثبت‌نام نکرده (مثل خریدار آرشیو) هم نه
    ok, why = ec.eligible(cert, event_id, STRANGER)
    assert not ok and "ثبت‌نام" in why
    # حضور ثبت‌شده → واجد شرایط
    database.db_execute(
        "INSERT INTO attendance_records (event_id, bale_user_id, status) VALUES (?,?,'present')",
        (event_id, MEMBER))
    ok, why = ec.eligible(cert, event_id, MEMBER)
    assert ok and why == ""


def test_non_attendance_conditions_warn_and_are_audited_and_guarded(db):
    event_id = database.db_execute(
        "INSERT INTO events (title, event_type, location_type, start_date, status, created_by) VALUES (?,'workshop','onsite','1405/07/01','done',?)", ("کارگاه تلسکوپ", ADMIN))
    row_id, _err = ec.add_cert(event_id, "گواهی شرکت", uid=ADMIN)

    # انتخاب «فقط ثبت‌نام» توسط ادمین: ذخیره می‌شود، هشدار صریح نشان داده می‌شود، عامل ثبت می‌شود
    SENT.clear()
    ec.set_cond(ADMIN, ADMIN, "none", row_id)
    assert (ec.get_cert(row_id).get("condition") or "") == "none"
    assert any(ec.ATTENDANCE_POLICY_WARNING in t for t in _texts())
    assert any("گواهی حضور» نیست" in t for t in _texts())
    audit = _actions("event_cert_condition")
    assert audit[-1] == {"event_cert": int(row_id), "event": int(event_id), "before": "present",
                         "after": "none", "attendance_proof": False}

    # جزئیات گواهینامه هم همان هشدار را دارد
    SENT.clear()
    ec.show_cert(ADMIN, ADMIN, row_id)
    assert any(ec.ATTENDANCE_POLICY_WARNING in t for t in _texts())

    # «پرداخت کامل» هم غیرحضوری است
    SENT.clear()
    ec.set_cond(ADMIN, ADMIN, "paid", row_id)
    assert _actions("event_cert_condition")[-1]["attendance_proof"] is False
    assert any(ec.ATTENDANCE_POLICY_WARNING in t for t in _texts())

    # بازگشت به حضور تأییدشده: هشدار نیست، عامل ثبت می‌شود
    SENT.clear()
    ec.set_cond(ADMIN, ADMIN, "present", row_id)
    assert _actions("event_cert_condition")[-1] == {"event_cert": int(row_id), "event": int(event_id),
                                                     "before": "paid", "after": "present", "attendance_proof": True}
    assert not any(ec.ATTENDANCE_POLICY_WARNING in t for t in _texts())

    # شرط نامعتبر رد می‌شود و چیزی ثبت نمی‌شود
    n = len(_actions("event_cert_condition"))
    ec.set_cond(ADMIN, ADMIN, "whatever", row_id)
    assert (ec.get_cert(row_id).get("condition") or "") == "present"
    assert len(_actions("event_cert_condition")) == n

    # کاربر غیرادمین نمی‌تواند شرط را عوض کند
    SENT.clear()
    ec.set_cond(STRANGER, STRANGER, "none", row_id)
    assert (ec.get_cert(row_id).get("condition") or "") == "present"
    assert len(_actions("event_cert_condition")) == n
    assert any("دسترسی ندارید" in t for t in _texts())
