"""مسیرهای واقعی امتیاز (۱۱ مسیر فعال) از طریق دفترکل — آفلاین، بدون بله.

هر مسیر: رفتار قبلی حفظ شده (همان مبلغ، همان شرط)، دقیقاً یک ردیف دفترکل،
و تکرار همان رویداد تجاری اثر دوم ندارد.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _points_fixture import ensure_test_env, set_balance  # noqa: E402

ensure_test_env()

import bale_api  # noqa: E402
import database  # noqa: E402
import points_ledger as pl  # noqa: E402
from config import SUPER_ADMIN_ID  # noqa: E402

import admin  # noqa: E402
import attendance  # noqa: E402
import attendance_auto  # noqa: E402
import auth  # noqa: E402
import club  # noqa: E402
import events  # noqa: E402
import forms  # noqa: E402
import lottery  # noqa: E402
import occasions  # noqa: E402
import payments  # noqa: E402
import permissions  # noqa: E402
import survey  # noqa: E402

ADMIN = SUPER_ADMIN_ID
U1, U2 = 7101001, 7101002
SENT: list[tuple] = []


def _fake_raw_call(method, params=None, **_kw):
    SENT.append((method, dict(params or {})))
    return {"ok": True, "result": {"message_id": len(SENT), "status": "member"}}


@pytest.fixture()
def db(tmp_path, monkeypatch):
    SENT.clear()
    monkeypatch.setattr(bale_api, "_raw_call", _fake_raw_call)
    monkeypatch.setattr(bale_api, "api_async", lambda m, p=None: {"ok": True})
    database.close_db()
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "paths.db"))
    database._conn = None
    database.init_db()
    events.init_event_tables()
    attendance.init_attendance_tables()
    payments.init_payment_tables()
    forms.init_form_tables()
    occasions.init_occasion_tables()
    permissions.init_permission_tables()
    club.init_club_tables()
    lottery.init_lottery_tables()
    attendance_auto.init_tables()
    survey.init_tables()
    database.seed_default_settings()
    auth.ensure_super_admin(ADMIN)
    for uid in (U1, U2):
        database.db_execute("INSERT INTO users (bale_user_id, first_name, last_name, is_authenticated) "
                            "VALUES (?,?,?,1)", (uid, f"u{uid}", "t"))
    yield database
    database.close_db()


def _tp(uid):
    return int(database.db_execute(
        "SELECT COALESCE(total_points,0) AS tp FROM users WHERE bale_user_id=?", (uid,), fetch="one")["tp"])


def _rows(source, uid=None):
    q, p = "SELECT * FROM points_ledger WHERE source=?", [source]
    if uid is not None:
        q += " AND bale_user_id=?"
        p.append(uid)
    return database.db_execute(q + " ORDER BY id", tuple(p), fetch="all") or []


def _texts():
    return [p.get("text", "") for m, p in SENT if m == "sendMessage"]


def _event(points_reward=0, price=0, survey_points=0):
    eid = database.db_execute(
        "INSERT INTO events (title, status, points_reward, price, survey_points, created_by) "
        "VALUES ('رویداد آزمایشی','published',?,?,?,?)", (points_reward, price, survey_points, ADMIN))
    return int(eid)


def _register(eid, uid, status="confirmed"):
    return int(database.db_execute(
        "INSERT INTO event_registrations (event_id, bale_user_id, status) VALUES (?,?,?)", (eid, uid, status)))


# ───────────── ۱) نشان‌ها ─────────────
def test_achievement_awards_once_per_user_and_key(db):
    database.db_execute(
        "INSERT INTO achievements (key, title, trigger, threshold, points, is_active) "
        "VALUES ('first_reg','اولین ثبت‌نام','event_register',1,20,1)")
    eid = _event()
    _register(eid, U1)
    assert club.check_achievements(U1, "event_register", silent=True) == (1, 20)
    assert club.check_achievements(U1, "event_register", silent=True) == (0, 0)
    assert _tp(U1) == 20
    rows = _rows("achievement", U1)
    assert len(rows) == 1 and rows[0]["ref_key"] == f"ach:{U1}:first_reg" and rows[0]["ref_table"] == "user_achievements"
    assert database.db_execute("SELECT COUNT(*) AS c FROM user_achievements WHERE bale_user_id=?", (U1,), fetch="one")["c"] == 1


# ───────────── ۲) قوانین امتیاز / تبریک ─────────────
def test_point_rule_once_only_single_row_and_repeatable_keyed_by_progress(db):
    database.db_execute(
        "INSERT INTO point_rules (key, title, trigger, threshold, points, once_only, is_active) "
        "VALUES ('reg1','ثبت‌نام','event_register',1,10,1,1)")
    eid = _event()
    _register(eid, U1)
    assert occasions.check_point_rules(U1, "event_register", silent=True) == (1, 10)
    assert occasions.check_point_rules(U1, "event_register", silent=True) == (0, 0)
    assert _tp(U1) == 10 and len(_rows("point_rule", U1)) == 1
    assert _rows("point_rule", U1)[0]["ref_key"] == f"rule:{U1}:reg1"


def test_birthday_and_occasion_award_once_per_year(db, monkeypatch):
    # تبریک تولد: ارسال موفق → یک ردیف؛ اجرای دوباره همان سال → بدون ردیف تازه
    jy, jm, jd = occasions.today_jalali()
    database.db_execute("UPDATE users SET birth_date=? WHERE bale_user_id=?", (f"1370/{jm:02d}/{jd:02d}", U1))
    database.set_setting("oc_birthday_points", "15")
    sent1, _ = occasions.check_birthdays()
    sent2, _ = occasions.check_birthdays()
    assert sent1 == 1 and sent2 == 0
    rows = _rows("birthday", U1)
    assert len(rows) == 1 and rows[0]["ref_key"] == f"birthday:{U1}:{jy}" and _tp(U1) == rows[0]["delta"]


# ───────────── ۳) پایان رویداد ─────────────
def test_event_finish_rerun_does_not_double_award_but_completes_missing(db):
    eid = _event(points_reward=30)
    _register(eid, U1)
    _register(eid, U2)
    events.set_event_status(ADMIN, ADMIN, eid, "finished")
    assert _tp(U1) == 30 and _tp(U2) == 30
    events.set_event_status(ADMIN, ADMIN, eid, "finished")
    assert _tp(U1) == 30 and _tp(U2) == 30 and len(_rows("event_finished")) == 2
    assert any("قبلاً امتیاز این رویداد" in t for t in _texts())
    # نفر تازه‌ای که دیرتر تأیید شد: اجرای دوبارهٔ «پایان» فقط او را تکمیل می‌کند
    database.db_execute("INSERT INTO users (bale_user_id, first_name) VALUES (7101003,'c')")
    _register(eid, 7101003)
    events.set_event_status(ADMIN, ADMIN, eid, "finished")
    assert _tp(7101003) == 30 and _tp(U1) == 30 and len(_rows("event_finished")) == 3
    assert all(r["ref_table"] == "event_registrations" and r["ref_id"] for r in _rows("event_finished"))


# ───────────── ۴) حضور و غیاب ─────────────
def _session(eid, points=5):
    return int(database.db_execute(
        "INSERT INTO attendance_sessions (event_id, title, session_code, points, is_open) VALUES (?,?,?,?,1)",
        (eid, "جلسه", "ABC123", points)))


def test_attendance_clear_and_remark_same_session_awards_once(db):
    database.set_setting("club_enabled", "0")   # نشان پیش‌فرض «اولین قدم» را از این سنجش جدا می‌کند
    eid = _event()
    _register(eid, U1)
    sid = _session(eid, points=5)
    s = database.db_execute("SELECT * FROM attendance_sessions WHERE id=?", (sid,), fetch="one")
    attendance.record_attendance(U1, U1, s, "code")
    assert _tp(U1) == 5
    attendance.record_attendance(U1, U1, s, "code")          # ثبت دوبارهٔ خود کاربر
    assert _tp(U1) == 5
    attendance.clear_all(ADMIN, ADMIN, sid, confirmed=True)   # پاک‌کردن رکوردها
    assert database.db_execute("SELECT COUNT(*) AS c FROM attendance_records WHERE session_id=?", (sid,), fetch="one")["c"] == 0
    attendance.toggle_manual(ADMIN, ADMIN, sid, U1, 0)       # ثبت دوباره توسط ادمین
    assert _tp(U1) == 5 and len(_rows("attendance_session", U1)) == 1
    assert _rows("attendance_session", U1)[0]["ref_key"] == f"att:{sid}:{U1}"
    # ثبت خودکار (attendance_auto) همان جلسه هم کلید مشترک دارد
    attendance.clear_all(ADMIN, ADMIN, sid, confirmed=True)
    ok, _msg = attendance_auto.mark_present(s, U1, method="code", status="present")
    assert ok and _tp(U1) == 5 and len(_rows("attendance_session", U1)) == 1
    # جلسهٔ دیگر = رویداد تجاری دیگر
    sid2 = _session(eid, points=7)
    attendance.toggle_manual(ADMIN, ADMIN, sid2, U1, 0)
    assert _tp(U1) == 12


def test_mark_all_awards_each_registrant_once(db):
    eid = _event()
    _register(eid, U1)
    _register(eid, U2)
    sid = _session(eid, points=3)
    attendance.mark_all(ADMIN, ADMIN, sid, confirmed=True)
    attendance.mark_all(ADMIN, ADMIN, sid, confirmed=True)
    assert _tp(U1) == 3 and _tp(U2) == 3 and len(_rows("attendance_session")) == 2


# ───────────── ۵) جایزهٔ قرعه‌کشی ─────────────
def test_lottery_prize_points_once_per_winner(db):
    eid = _event()
    _register(eid, U1)
    lid = int(database.db_execute(
        "INSERT INTO form_lotteries (title, source, event_id, status, winner_mode, created_by) "
        "VALUES ('قرعه','event',?,'pending','random',?)", (eid, ADMIN)))
    pid = int(database.db_execute(
        "INSERT INTO lottery_prizes (lottery_id, title, winner_count, points_reward) VALUES (?,?,1,25)", (lid, "جایزه")))
    lottery.run_draw(ADMIN, ADMIN, lid, silent=True)
    assert _tp(U1) == 25
    rows = _rows("lottery_prize", U1)
    assert len(rows) == 1 and rows[0]["ref_key"] == f"lot:{lid}:{pid}:{U1}" and rows[0]["ref_table"] == "lottery_winners"
    # اجرای دوباره: قفل وضعیت جلوی آن را می‌گیرد؛ حتی با بازنشانی وضعیت، کلید دفترکل مانع امتیاز دوباره است
    lottery.run_draw(ADMIN, ADMIN, lid, silent=True)
    database.db_execute("UPDATE form_lotteries SET status='pending' WHERE id=?", (lid,))
    lottery.run_draw(ADMIN, ADMIN, lid, silent=True)
    assert _tp(U1) == 25 and len(_rows("lottery_prize", U1)) == 1


# ───────────── ۶ و ۷) خرید پاداش و رد/برگشت ─────────────
def _reward(cost=40, rtype="custom", stock=0, per_user_limit=0):
    return int(database.db_execute(
        "INSERT INTO rewards (key, title, cost, reward_type, is_active, stock, per_user_limit) "
        "VALUES (?,?,?,?,1,?,?)", (f"rw{cost}{rtype}", "پاداش", cost, rtype, stock, per_user_limit)))


def test_buy_is_atomic_and_double_tap_charges_once(db):
    set_balance(U1, 100)
    rid = _reward(cost=40)
    club.do_buy(U1, U1, rid, "abc123def4")
    club.do_buy(U1, U1, rid, "abc123def4")   # همان دکمه، دو بار
    assert _tp(U1) == 60
    reds = database.db_execute("SELECT * FROM reward_redemptions WHERE bale_user_id=?", (U1,), fetch="all")
    assert len(reds) == 1 and reds[0]["status"] == "pending"
    rows = _rows("reward_redeem", U1)
    assert len(rows) == 1 and rows[0]["ref_id"] == reds[0]["id"] and rows[0]["actor_kind"] == "user"
    assert any("قبلاً ثبت شده" in t for t in _texts())
    # تأیید تازه = خرید تازه
    club.do_buy(U1, U1, rid, "zzz999yyy8")
    assert _tp(U1) == 20
    # موجودی ناکافی: نه درخواست، نه کسر
    club.do_buy(U1, U1, rid, "nnn000mmm1")
    assert _tp(U1) == 20
    assert database.db_execute("SELECT COUNT(*) AS c FROM reward_redemptions", fetch="one")["c"] == 2
    assert database.db_execute("SELECT sold FROM rewards WHERE id=?", (rid,), fetch="one")["sold"] == 2
    # دکمهٔ قدیمی بدون nonce → بازگشت به مرحلهٔ تأیید (بدون کسر)
    club.do_buy(U1, U1, rid, None)
    assert _tp(U1) == 20


def test_discount_reward_delivery_failure_rolls_back_charge(db, monkeypatch):
    set_balance(U1, 100)
    rid = _reward(cost=10, rtype="discount")
    database.db_execute("DROP TABLE IF EXISTS event_discount_codes")  # شبیه‌سازی خطای تحویل
    club.do_buy(U1, U1, rid, "disc00fail")
    assert _tp(U1) == 100
    assert database.db_execute("SELECT COUNT(*) AS c FROM reward_redemptions", fetch="one")["c"] == 0
    assert _rows("reward_redeem") == []


def test_reject_refunds_once_even_when_handled_twice(db):
    set_balance(U1, 100)
    rid = _reward(cost=40)
    club.do_buy(U1, U1, rid, "buy1buy1aa")
    red = database.db_execute("SELECT * FROM reward_redemptions WHERE bale_user_id=?", (U1,), fetch="one")
    assert _tp(U1) == 60
    club.handle_request(ADMIN, ADMIN, red["id"], approve=False)
    club.handle_request(ADMIN, ADMIN, red["id"], approve=False)
    assert _tp(U1) == 100
    refunds = _rows("reward_reject_refund", U1)
    spend = _rows("reward_redeem", U1)[0]
    assert len(refunds) == 1 and refunds[0]["reverses_id"] == spend["id"] and refunds[0]["entry_type"] == "refund"
    assert database.db_execute("SELECT status FROM reward_redemptions WHERE id=?", (red["id"],), fetch="one")["status"] == "rejected"
    assert database.db_execute("SELECT sold FROM rewards WHERE id=?", (rid,), fetch="one")["sold"] == 0
    # درخواستِ پیش از دفترکل (بدون ردیف spend) هم فقط یک‌بار برمی‌گردد، بدون reverses_id
    old = int(database.db_execute(
        "INSERT INTO reward_redemptions (bale_user_id, reward_key, reward_title, cost, code, status) "
        "VALUES (?,?,?,?,?,?)", (U1, "legacy", "قدیمی", 5, "RWOLD", "pending")))
    club.handle_request(ADMIN, ADMIN, old, approve=False)
    club.handle_request(ADMIN, ADMIN, old, approve=False)
    assert _tp(U1) == 105
    legacy = [r for r in _rows("reward_reject_refund", U1) if r["ref_id"] == old]
    assert len(legacy) == 1 and legacy[0]["reverses_id"] is None


# ───────────── ۸) پرداخت با امتیاز ─────────────
def test_points_payment_is_atomic_with_transaction_and_retry_safe(db, monkeypatch):
    database.set_setting("pay_points_enabled", "1")
    database.set_setting("pay_points_rate", "10000")
    set_balance(U1, 100)
    eid = _event(price=500000)
    rid = _register(eid, U1, status="pending")
    ev = events.get_event(eid)
    monkeypatch.setattr(payments, "finish_target", lambda *a, **k: None)
    q = payments.points_quote(U1, 500000)
    assert q["ok"] and q["full"] and q["use"] == 50
    payments._do_points_payment(U1, U1, ev, rid, 500000, q)
    assert _tp(U1) == 50
    txs = database.db_execute("SELECT * FROM transactions WHERE bale_user_id=? AND method='points'", (U1,), fetch="all")
    assert len(txs) == 1 and txs[0]["amount"] == 500000 and txs[0]["points_used"] == 50
    rows = _rows("payment_spend", U1)
    assert len(rows) == 1 and rows[0]["ref_table"] == "transactions" and rows[0]["ref_id"] == txs[0]["id"]
    assert '"covered_rial": 500000' in rows[0]["meta"] and txs[0]["transaction_id"] in rows[0]["meta"]
    assert database.db_execute("SELECT amount_paid FROM event_registrations WHERE id=?", (rid,), fetch="one")["amount_paid"] == 500000
    # تکرار همان درخواست (دو بار زدن دکمه با همان quote): نه تراکنش دوم، نه کسر دوم
    database.db_execute("UPDATE event_registrations SET amount_paid=0 WHERE id=?", (rid,))  # حتی اگر mark_paid نرسیده باشد
    payments._do_points_payment(U1, U1, ev, rid, 500000, q)
    assert _tp(U1) == 50
    assert database.db_execute("SELECT COUNT(*) AS c FROM transactions WHERE method='points'", fetch="one")["c"] == 1
    assert any("قبلاً ثبت شده" in t for t in _texts())
    # قسط/پرداخت بعدی با وضعیت متفاوت (مبلغ پرداخت‌شدهٔ قبلی فرق دارد) کلید تازه می‌گیرد
    database.db_execute("UPDATE event_registrations SET amount_paid=500000 WHERE id=?", (rid,))
    q2 = payments.points_quote(U1, 100000)
    payments._do_points_payment(U1, U1, ev, rid, 100000, q2)
    assert _tp(U1) == 40 and len(_rows("payment_spend", U1)) == 2


def test_points_payment_failure_rolls_back_transaction_row(db, monkeypatch):
    database.set_setting("pay_points_enabled", "1")
    database.set_setting("pay_points_rate", "10000")
    set_balance(U1, 100)
    eid = _event(price=200000)
    rid = _register(eid, U1, status="pending")
    ev = events.get_event(eid)
    q = payments.points_quote(U1, 200000)
    # خرابی بین ساخت تراکنش و کسر امتیاز
    conn = database.get_db()
    conn.execute("CREATE TEMP TRIGGER boom BEFORE INSERT ON points_ledger BEGIN SELECT RAISE(ABORT,'boom'); END")
    payments._do_points_payment(U1, U1, ev, rid, 200000, q)
    conn.execute("DROP TRIGGER boom")
    assert _tp(U1) == 100
    assert database.db_execute("SELECT COUNT(*) AS c FROM transactions WHERE method='points'", fetch="one")["c"] == 0
    assert any("ناموفق" in t for t in _texts())
    # تلاش دوباره پس از رفع خرابی کامل می‌شود
    payments._do_points_payment(U1, U1, ev, rid, 200000, q)
    assert _tp(U1) == 80


def test_legacy_spend_refund_helpers_do_not_touch_balance(db):
    set_balance(U1, 50)
    assert payments.spend_points(U1, 10) == (False, 50)
    assert payments.refund_points(U1, 10) is False
    assert _tp(U1) == 50


# ───────────── ۹) نظرسنجی رویداد ─────────────
def test_survey_points_once_per_event(db):
    eid = _event(survey_points=8)
    database.db_execute("INSERT INTO survey_sends (event_id, form_id, bale_user_id, answered) VALUES (?,?,?,0)", (eid, 1, U1))
    assert survey.mark_answered(eid, U1, response_id=11) is True
    assert survey.mark_answered(eid, U1, response_id=11) is False
    assert _tp(U1) == 8 and len(_rows("survey", U1)) == 1
    assert _rows("survey", U1)[0]["ref_key"] == f"survey:{eid}:{U1}"


# ───────────── ۱۰) تعدیل دستی ادمین ─────────────
def _msg(uid, text):
    return {"from": {"id": uid}, "chat": {"id": uid}, "text": text}


def test_manual_adjust_fail_closed_without_cap(db, monkeypatch):
    monkeypatch.setattr(admin, "POINTS_MANUAL_ADJUST_MAX", 0)
    tid = database.db_execute("SELECT id FROM users WHERE bale_user_id=?", (U1,), fetch="one")["id"]
    admin.start_points_adjust(ADMIN, ADMIN, tid)
    assert any("غیرفعال" in t for t in _texts())
    assert auth.get_state_name(ADMIN) != admin.STATE_POINTS_ADJUST


def test_manual_adjust_requires_superadmin_delta_reason_and_confirm(db, monkeypatch):
    monkeypatch.setattr(admin, "POINTS_MANUAL_ADJUST_MAX", 200)
    set_balance(U1, 30)
    tid = database.db_execute("SELECT id FROM users WHERE bale_user_id=?", (U1,), fetch="one")["id"]
    # ادمین عادی (غیر مالک) → رد
    database.db_execute("UPDATE users SET is_admin=1 WHERE bale_user_id=?", (U2,))
    admin.start_points_adjust(U2, U2, tid)
    assert any("فقط برای مالک" in t for t in _texts())
    admin.confirm_points_adjust(U2, U2, tid, True)
    assert _tp(U1) == 30
    # مالک: دلتا → دلیل → تأیید
    admin.start_points_adjust(ADMIN, ADMIN, tid)
    admin.handle_points_adjust(_msg(ADMIN, "0"))
    admin.handle_points_adjust(_msg(ADMIN, "+500"))       # بیش از سقف
    admin.handle_points_adjust(_msg(ADMIN, "+۴۵"))        # ارقام فارسی
    admin.handle_points_adjust(_msg(ADMIN, "کم"))         # دلیل کوتاه
    assert _tp(U1) == 30
    admin.handle_points_adjust(_msg(ADMIN, "جبران خطای ثبت حضور جلسهٔ دوم"))
    assert _tp(U1) == 30   # هنوز تأیید نشده
    admin.confirm_points_adjust(ADMIN, ADMIN, tid, True)
    assert _tp(U1) == 75
    rows = _rows("admin_manual", U1)
    manual = [r for r in rows if r["ref_key"].startswith("manual:") and "fixture" not in r["ref_key"]]
    assert len(manual) == 1
    row = manual[0]
    assert row["actor_kind"] == "admin" and row["actor_id"] == ADMIN
    assert row["reason"] == "جبران خطای ثبت حضور جلسهٔ دوم" and '"before": 30' in row["meta"] and '"after": 75' in row["meta"]
    # تأیید دوباره پس از پایان جریان: وضعیت پاک شده → بدون اثر
    admin.confirm_points_adjust(ADMIN, ADMIN, tid, True)
    assert _tp(U1) == 75
    # کاهش بیش از موجودی → رد (بدون موجودی منفی)
    admin.start_points_adjust(ADMIN, ADMIN, tid)
    admin.handle_points_adjust(_msg(ADMIN, "-100"))
    admin.handle_points_adjust(_msg(ADMIN, "اصلاح به درخواست کاربر"))
    admin.confirm_points_adjust(ADMIN, ADMIN, tid, True)
    assert _tp(U1) == 75 and any("منفی مجاز نیست" in t for t in _texts())


def test_profile_editor_cannot_write_points(db):
    tid = database.db_execute("SELECT id FROM users WHERE bale_user_id=?", (U1,), fetch="one")["id"]
    admin.start_edit_profile_field(ADMIN, ADMIN, "total_points", tid)
    assert any("فیلد نامعتبر" in t for t in _texts())
    assert _tp(U1) == 0
