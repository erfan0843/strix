"""دفترکل امتیاز — هستهٔ تراکنشی، idempotency، تغییرناپذیری، نگهبان، تطبیق، آینهٔ سرور.

کاملاً آفلاین: پایگاه SQLite موقت، بدون شبکه، بدون بله.
"""
from __future__ import annotations

import ast
import re
import sqlite3
import sys
import threading
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _points_fixture import ensure_test_env, set_balance  # noqa: E402

ensure_test_env()

import database  # noqa: E402
import points_ledger as pl  # noqa: E402
import club  # noqa: E402

U1, U2 = 7001001, 7001002


@pytest.fixture()
def db(tmp_path, monkeypatch):
    database.close_db()
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "ledger.db"))
    database._conn = None
    database.init_db()
    club.init_club_tables()
    for uid in (U1, U2):
        database.db_execute("INSERT INTO users (bale_user_id, first_name) VALUES (?, ?)", (uid, f"u{uid}"))
    yield database
    database.close_db()


def _tp(uid):
    return int(database.db_execute(
        "SELECT COALESCE(total_points,0) AS tp FROM users WHERE bale_user_id=?", (uid,), fetch="one")["tp"])


def _count():
    return int(database.db_execute("SELECT COUNT(*) AS c FROM points_ledger", fetch="one")["c"])


def _award(uid, pts, key, **kw):
    kw.setdefault("ref_table", "user_achievements")
    kw.setdefault("ref_id", 1)
    return pl.post_points(uid, pts, entry_type="award", source="achievement", ref_key=key, **kw)


# ───────────────────────── idempotency / atomicity ─────────────────────────
def test_same_business_event_twice_changes_balance_once(db):
    first = _award(U1, 10, f"ach:{U1}:first")
    second = _award(U1, 10, f"ach:{U1}:first")
    assert first.created and not second.created
    assert second.entry_id == first.entry_id
    assert _tp(U1) == 10 and pl.balance(U1) == 10 and _count() == 1


def test_concurrent_posts_with_same_key_produce_one_row(db):
    results = []

    def worker():
        results.append(pl.post_points(U2, 7, entry_type="award", source="lottery_prize",
                                      ref_key=f"lot:1:1:{U2}", ref_table="lottery_winners", ref_id=1).created)

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [False] * 11 + [True]
    assert _tp(U2) == 7 and _count() == 1


def test_failure_between_ledger_insert_and_balance_update_rolls_back(db):
    conn = database.get_db()
    conn.execute("""CREATE TEMP TRIGGER boom BEFORE UPDATE OF total_points ON users
                    BEGIN SELECT RAISE(ABORT, 'boom'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        _award(U1, 5, f"ach:{U1}:boom")
    assert _count() == 0 and _tp(U1) == 0
    assert not conn.in_transaction
    conn.execute("DROP TRIGGER boom")
    assert _award(U1, 5, f"ach:{U1}:boom").created  # تلاش دوباره کامل می‌شود
    assert _count() == 1 and _tp(U1) == 5


def test_outer_transaction_failure_rolls_back_ledger_and_balance(db):
    with pytest.raises(RuntimeError):
        with database.db_transaction():
            _award(U1, 9, f"ach:{U1}:outer")
            database.db_execute("UPDATE users SET first_name='x' WHERE bale_user_id=?", (U1,))
            raise RuntimeError("business step failed")
    assert _count() == 0 and _tp(U1) == 0
    assert database.db_execute("SELECT first_name AS n FROM users WHERE bale_user_id=?", (U1,), fetch="one")["n"] != "x"


def test_db_execute_inside_transaction_raises_instead_of_swallowing(db):
    with pytest.raises(sqlite3.OperationalError):
        with database.db_transaction():
            database.db_execute("INSERT INTO no_such_table VALUES (1)")
    # بیرون از تراکنش رفتار قدیمی (بلعیدن خطا و None) حفظ شده است
    assert database.db_execute("INSERT INTO no_such_table VALUES (1)") is None


def test_insufficient_balance_rejected_and_nothing_written(db):
    _award(U1, 10, f"ach:{U1}:a")
    with pytest.raises(pl.InsufficientPoints) as exc:
        pl.post_points(U1, -11, entry_type="spend", source="reward_redeem", ref_key="redeem:x",
                       ref_table="reward_redemptions", ref_id=1)
    assert exc.value.have == 10 and exc.value.need == 11
    assert _tp(U1) == 10 and _count() == 1


# ───────────────────────── DB-level protection ─────────────────────────
def test_direct_total_points_writes_are_blocked_by_guard(db):
    _award(U1, 10, f"ach:{U1}:g")
    conn = database.get_db()
    with pytest.raises(sqlite3.IntegrityError, match="points_ledger_guard"):
        conn.execute("UPDATE users SET total_points=total_points+5 WHERE bale_user_id=?", (U1,))
    with pytest.raises(sqlite3.IntegrityError, match="points_ledger_guard"):
        conn.execute("INSERT INTO users (bale_user_id, first_name, total_points) VALUES (1, 'x', 5)")
    # db_execute قدیمی: خطا لاگ می‌شود و None برمی‌گردد؛ موجودی دست‌نخورده
    assert database.db_execute("UPDATE users SET total_points=0 WHERE bale_user_id=?", (U1,)) is None
    assert _tp(U1) == 10
    # به‌روزرسانی ستون‌های دیگر آزاد است
    assert database.db_execute("UPDATE users SET first_name='ok', total_points=total_points WHERE bale_user_id=?", (U1,))
    assert pl.meta_get("write_gate") == "0"


def test_ledger_rows_are_immutable_except_sync_columns(db):
    e = _award(U1, 10, f"ach:{U1}:imm")
    conn = database.get_db()
    for q in ("UPDATE points_ledger SET delta=1 WHERE id=?", "UPDATE points_ledger SET reason='x' WHERE id=?",
              "DELETE FROM points_ledger WHERE id=?"):
        with pytest.raises(sqlite3.IntegrityError, match="points_ledger_immutable"):
            conn.execute(q, (e.entry_id,))
    conn.execute("UPDATE points_ledger SET shared_status='failed', shared_error='x' WHERE id=?", (e.entry_id,))
    assert pl.get_entry(e.entry_id)["shared_status"] == "failed"


def test_constraints_reject_invalid_rows(db):
    with pytest.raises(pl.LedgerError, match="zero_delta"):
        _award(U1, 0, "ach:z")
    with pytest.raises(pl.LedgerError, match="delta_sign_mismatch"):
        _award(U1, -1, "ach:neg")
    with pytest.raises(pl.LedgerError, match="invalid_source"):
        pl.post_points(U1, 1, entry_type="award", source="made_up", ref_key="k")
    with pytest.raises(pl.LedgerError, match="invalid_ref_key"):
        pl.post_points(U1, 1, entry_type="award", source="achievement", ref_key="bad key!")
    with pytest.raises(pl.LedgerError, match="reason_required"):
        pl.post_points(U1, 1, entry_type="manual_adjust", source="admin_manual", ref_key=pl.new_manual_key(),
                       actor_kind="admin", actor_id=1)
    with pytest.raises(pl.LedgerError, match="user_not_found"):
        _award(424242, 1, "ach:nouser")
    assert _count() == 0


# ───────────────────────── opening balance ─────────────────────────
def test_legacy_counter_without_opening_row_fails_closed(db):
    pl.disable_guard(reason="test: شبیه‌سازی شمارندهٔ قدیمی", actor_id=1)
    database.db_execute("UPDATE users SET total_points=40 WHERE bale_user_id=?", (U1,))
    database.db_execute("UPDATE users SET total_points=-3 WHERE bale_user_id=?", (U2,))
    pl.enable_guard()
    with pytest.raises(pl.LedgerError, match="opening_balance_missing"):
        _award(U1, 5, f"ach:{U1}:pre")
    assert _tp(U1) == 40 and _count() == 0
    rep = pl.reconcile()
    assert rep["users_without_opening"] == 2 and rep["negative_balances"] == 1 and not rep["ok"]

    o1 = pl.post_opening_balance(U1, reason="موجودی شمارندهٔ قدیمی")
    o2 = pl.post_opening_balance(U2, reason="موجودی شمارندهٔ قدیمی")
    assert (o1.delta, o1.balance_after, o2.delta, o2.balance_after) == (40, 40, -3, -3)
    assert "negative_opening" in (pl.get_entry(o2.entry_id)["meta"] or "")
    assert _tp(U1) == 40 and _tp(U2) == -3  # افتتاحیه شمارنده را تغییر نمی‌دهد
    # اجرای دوباره بی‌اثر است
    assert not pl.post_opening_balance(U1, reason="x").created
    with pytest.raises(pl.LedgerError, match="opening_balance_conflict"):
        pl.post_points(U1, 40, entry_type="opening_balance", source="legacy_counter", ref_key="opening:other")
    assert _award(U1, 5, f"ach:{U1}:post").balance_after == 45
    assert pl.reconcile()["ok"]


def test_counter_changed_outside_ledger_is_detected_not_fixed(db):
    _award(U1, 10, f"ach:{U1}:x")
    pl.disable_guard(reason="test: دورهٔ guard-off", actor_id=1)
    assert not pl.guard_installed()
    database.db_execute("UPDATE users SET total_points=25 WHERE bale_user_id=?", (U1,))
    rep = pl.health_report()
    assert not rep["ok"]
    assert rep["report"]["mismatched"] == 1 and rep["report"]["examples"]["mismatched"][0]["ledger"] == 10
    assert any("نگهبان" in p for p in rep["problems"])
    assert _tp(U1) == 25  # گزارش چیزی را اصلاح نمی‌کند
    pl.enable_guard()
    with pytest.raises(pl.LedgerError, match="balance_out_of_sync"):
        _award(U1, 1, f"ach:{U1}:y")
    assert "guard_disabled_at" in pl.reconcile()["meta"]


# ───────────────────────── reversal ─────────────────────────
def test_reversal_once_only_and_never_for_reversals(db):
    e = _award(U1, 10, f"ach:{U1}:r")
    with pytest.raises(pl.LedgerError, match="reason_required"):
        pl.reverse_entry(e.entry_id, reason="", actor_id=1)
    r = pl.reverse_entry(e.entry_id, reason="ثبت اشتباه", actor_id=1)
    assert r.created and r.delta == -10 and _tp(U1) == 0
    assert pl.get_entry(r.entry_id)["reverses_id"] == e.entry_id
    with pytest.raises(pl.LedgerError, match="already_reversed"):
        pl.reverse_entry(e.entry_id, reason="دوباره", actor_id=1)
    with pytest.raises(pl.LedgerError, match="cannot_reverse_entry_type"):
        pl.reverse_entry(r.entry_id, reason="برگشتِ برگشت", actor_id=1)
    assert _count() == 2 and _tp(U1) == 0


def test_manual_adjust_records_before_after_actor_reason(db):
    set_balance(U1, 30)
    res = pl.post_points(U1, -12, entry_type="manual_adjust", source="admin_manual",
                         ref_key=pl.new_manual_key(), reason="اصلاح به درخواست مالک",
                         actor_kind="admin", actor_id=100000001, meta={"before": 30, "after": 18})
    row = pl.get_entry(res.entry_id)
    assert (row["actor_kind"], row["actor_id"], row["reason"]) == ("admin", 100000001, "اصلاح به درخواست مالک")
    assert res.balance_before == 30 and res.balance_after == 18 and _tp(U1) == 18


# ───────────────────────── server mirror (offline fake API) ─────────────────────────
class _ApiError(Exception):
    def __init__(self, status, code):
        super().__init__(code)
        self.status = status
        self.code = code


class FakePointsAPI:
    def __init__(self, known, fail_times=0):
        self.known = set(known)
        self.records = {}
        self.calls = 0
        self.fail_times = fail_times

    def submit_points_entry(self, bale_user_id, external_key, entry):
        self.calls += 1
        if self.fail_times > 0:
            self.fail_times -= 1
            raise _ApiError(0, "shared_api_unreachable")
        if str(bale_user_id) not in self.known:
            raise _ApiError(404, "owner_identity_not_found")
        created = external_key not in self.records
        rec = self.records.setdefault(external_key, {"id": str(uuid.uuid4()), "entry": entry})
        return {"id": rec["id"], "created": created}


def test_sync_states_and_retry_without_duplicates(db):
    api = FakePointsAPI(known={str(U1)}, fail_times=1)
    e1 = _award(U1, 10, f"ach:{U1}:s1")
    e2 = _award(U2, 4, f"ach:{U2}:s2")
    # تلاش اول: شبکه قطع → failed (قابل تکرار)؛ ردیف دست‌نخورده
    assert pl.sync_entry(e1.entry_id, api_client=api)["outcome"] == "failed"
    row = pl.get_entry(e1.entry_id)
    assert row["shared_status"] == "failed" and row["shared_attempts"] == 1 and row["delta"] == 10
    # تلاش دوم: موفق؛ تلاش سوم: بدون درخواست تازه (قبلاً mirrored)
    assert pl.sync_entry(e1.entry_id, api_client=api)["outcome"] == "mirrored"
    calls = api.calls
    assert pl.sync_entry(e1.entry_id, api_client=api)["outcome"] == "mirrored" and api.calls == calls
    assert len(api.records) == 1
    key = next(iter(api.records))
    assert re.fullmatch(r"[0-9a-f-]{36}:%d" % e1.entry_id, key)
    payload = api.records[key]["entry"]
    assert payload["ledger_id"] == e1.entry_id and payload["delta"] == 10 and "actor_id" not in payload
    # کاربر بدون هویت سرور → unmapped، بدون نگاشت خودکار
    assert pl.sync_entry(e2.entry_id, api_client=api)["outcome"] == "unmapped"
    assert pl.get_entry(e2.entry_id)["shared_status"] == "unmapped"
    counts = pl.sync_pending(api_client=api, include_unmapped=True)
    assert counts["unmapped"] == 1 and counts["mirrored"] == 0
    # پس از لینک‌شدن هویت، تکرار همان کلید فقط یک ردیف سرور می‌سازد
    api.known.add(str(U2))
    assert pl.sync_pending(api_client=api, include_unmapped=True)["mirrored"] == 1
    assert len(api.records) == 2
    rep = pl.reconcile()
    assert rep["sync"] == {"pending": 0, "mirrored": 2, "unmapped": 0, "failed": 0}
