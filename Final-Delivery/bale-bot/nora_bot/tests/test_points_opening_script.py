"""آزمون اسکریپت افتتاحیهٔ دفترکل روی یک نسخهٔ مصنوعی از پایگاه قدیمی.

* dry-run چیزی را تغییر نمی‌دهد (checksum فایل برابر می‌ماند)
* --apply --yes: یک ردیف افتتاحیه برای هر کاربر غیرصفر، پشتیبان معتبر، نگهبان نصب،
  جمع امتیاز و تعداد کاربران بدون تغییر، منفی‌ها فقط علامت‌گذاری
* اجرای دوبارهٔ apply بی‌اثر است
* report / guard-off / guard-on / rebaseline فقط با --apply --yes چیزی می‌نویسند
* startup_check بدون افتتاحیه اجرای ربات را رد می‌کند
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from _points_fixture import ensure_test_env  # noqa: E402

ensure_test_env()

import migrate_points_opening_balance as mig  # noqa: E402


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _legacy_db(tmp_path: Path) -> Path:
    """پایگاه مثل نسخهٔ قدیمی: جدول users پر، بدون هیچ اثری از دفترکل."""
    import database

    path = tmp_path / "legacy.sqlite"
    database.close_db()
    database.DB_PATH = str(path)
    database.init_db()
    database.close_db()
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        DROP TRIGGER IF EXISTS trg_users_points_guard_update;
        DROP TRIGGER IF EXISTS trg_users_points_guard_insert;
        DROP TRIGGER IF EXISTS trg_points_ledger_no_update;
        DROP TRIGGER IF EXISTS trg_points_ledger_no_delete;
        DROP TABLE IF EXISTS points_ledger;
        DROP TABLE IF EXISTS points_ledger_meta;
        """
    )
    rows = [(8101, "الف", 120), (8102, "ب", 0), (8103, "پ", -30), (8104, "ت", 55)]
    for uid, name, pts in rows:
        conn.execute(
            "INSERT INTO users (bale_user_id, first_name, total_points) VALUES (?,?,?)",
            (uid, name, pts))
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    return path


@pytest.fixture
def legacy(tmp_path):
    path = _legacy_db(tmp_path)
    yield path
    import database

    database.close_db()


def test_dry_run_changes_nothing(legacy):
    before = _sha(legacy)
    summary = mig.run_opening(legacy, apply=False, backup_dir=None)
    assert summary["mode"] == "dry-run"
    assert summary["planned_opening_rows"] == 3
    assert summary["negative_flagged"] == 1
    assert summary["before"]["sum_points"] == 145
    assert _sha(legacy) == before
    assert not list(legacy.parent.glob("backups/*"))


def test_startup_check_blocks_without_opening(legacy):
    import database
    import points_ledger as pl

    database.close_db()
    database.DB_PATH = str(legacy)
    database.init_db()
    assert pl.needs_opening() is True
    assert pl.guard_installed() is False
    problems = pl.startup_check()
    assert problems and "افتتاحیه" in problems[0]
    # هیچ امتیازی هم تا پیش از افتتاحیه برای کاربر قدیمی ثبت نمی‌شود
    with pytest.raises(pl.LedgerError) as ei:
        pl.post_points(8101, 5, entry_type="award", source="achievement", ref_key="ach:8101:x")
    assert ei.value.code == "opening_balance_missing"


def test_apply_is_idempotent_and_keeps_counters(legacy, tmp_path):
    bdir = tmp_path / "bk"
    s1 = mig.run_opening(legacy, apply=True, backup_dir=bdir)
    assert s1["opening_rows_created"] == 3
    assert s1["opening_rows_failed"] == 0
    assert s1["sum_points_unchanged"] and s1["users_unchanged"]
    assert s1["after"]["sum_points"] == 145 and s1["after"]["users_total"] == 4
    assert s1["health"]["ok"] is True
    assert s1["health"]["report"]["negative_balances"] == 1   # علامت خورده، صفر نشده
    assert s1["health"]["warnings"] and s1["health"]["problems"] == []
    assert s1["backup"]["users_total"] == 4 and s1["backup"]["sum_points"] == 145
    bfile = bdir / s1["backup"]["file"]
    assert bfile.is_file() and _sha(bfile) == s1["backup"]["sha256"]
    assert oct(bfile.stat().st_mode & 0o777) == "0o600"
    assert s1["checksum_before"] and s1["checksum_before"] != _sha(legacy)

    conn = sqlite3.connect(legacy)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT bale_user_id, delta, balance_after, ref_key, reason FROM points_ledger ORDER BY bale_user_id").fetchall()
    assert [(r["bale_user_id"], r["delta"], r["balance_after"], r["ref_key"]) for r in rows] == [
        (8101, 120, 120, "opening:8101"), (8103, -30, -30, "opening:8103"), (8104, 55, 55, "opening:8104")]
    assert all(r["reason"] for r in rows)
    meta = dict(conn.execute("SELECT key, value FROM points_ledger_meta").fetchall())
    assert meta.get("opening_applied_at") and meta.get("opening_backup") == bfile.name
    assert meta.get("opening_checksum_before") == s1["checksum_before"]
    trig = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    assert {"trg_users_points_guard_update", "trg_points_ledger_no_update"} <= trig
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE users SET total_points=999 WHERE bale_user_id=8101")
    conn.close()

    # اجرای دوباره: هیچ ردیف تازه‌ای، شمارنده‌ها همان
    s2 = mig.run_opening(legacy, apply=True, backup_dir=bdir)
    assert s2["opening_rows_created"] == 0 and s2["opening_rows_existing"] == 3
    assert s2["after"]["sum_points"] == 145 and s2["after"]["ledger_entries"] == 3

    import database
    import points_ledger as pl

    database.close_db()
    database.DB_PATH = str(legacy)
    database.init_db()
    assert pl.startup_check() == []
    # امتیازدهی تازه پس از افتتاحیه از همان موجودی ادامه می‌یابد
    res = pl.post_points(8101, 5, entry_type="award", source="achievement", ref_key="ach:8101:x")
    assert res.balance_before == 120 and res.balance_after == 125


def test_report_guard_off_rebaseline_guard_on(legacy, tmp_path):
    mig.run_opening(legacy, apply=True, backup_dir=tmp_path / "bk")
    rep = mig.run_report(legacy)
    assert rep["health"]["ok"] is True and rep["counter"]["already_opened"] == 3

    # guard-off بدون دلیل رد می‌شود؛ dry-run هم چیزی نمی‌نویسد
    with pytest.raises(mig.OpeningError, match="reason_required"):
        mig.run_guard(legacy, enable=False, apply=True, reason="", actor_id=1)
    d = mig.run_guard(legacy, enable=False, apply=False, reason="x", actor_id=1)
    assert d["guard_installed_before"] is True and "guard_installed_after" not in d

    off = mig.run_guard(legacy, enable=False, apply=True, reason="بازگشت موقت به نسخهٔ قدیمی", actor_id=1)
    assert off["guard_installed_after"] is False and off["meta"]["guard_disabled_at"]

    # نسخهٔ قدیمی مستقیماً شمارنده را عوض می‌کند
    conn = sqlite3.connect(legacy)
    conn.execute("UPDATE users SET total_points=total_points+10 WHERE bale_user_id=8101")
    conn.execute("UPDATE users SET total_points=7 WHERE bale_user_id=8102")   # کاربر بدون افتتاحیه
    conn.commit()
    conn.close()

    # guard-on بدون rebaseline رد می‌شود
    with pytest.raises(mig.OpeningError, match="reconcile_not_clean"):
        mig.run_guard(legacy, enable=True, apply=True, reason=None, actor_id=1)

    dry = mig.run_rebaseline(legacy, apply=False, reason=None, actor_id=1)
    assert dry["mismatched"] == 1 and dry["users_without_opening"] == 1
    with pytest.raises(mig.OpeningError, match="reason_required"):
        mig.run_rebaseline(legacy, apply=True, reason="", actor_id=1)
    rb = mig.run_rebaseline(legacy, apply=True, reason="تطبیق پس از دورهٔ guard-off", actor_id=1)
    assert rb["rebaseline_rows_created"] == 1 and rb["opening_rows_created"] == 1 and rb["failed"] == 0
    assert rb["health"]["report"]["mismatched"] == 0 and rb["health"]["report"]["users_without_opening"] == 0
    assert rb["health"]["ok"] is False and len(rb["health"]["problems"]) == 1   # فقط: نگهبان هنوز نصب نیست

    on = mig.run_guard(legacy, enable=True, apply=True, reason=None, actor_id=1)
    assert on["guard_installed_after"] is True
    assert mig.run_report(legacy)["health"]["ok"] is True
    conn = sqlite3.connect(legacy)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT delta, balance_after, source, entry_type, reason FROM points_ledger WHERE ref_key LIKE 'rebaseline:8101:%'").fetchone()
    assert (r["delta"], r["balance_after"], r["source"], r["entry_type"]) == (10, 130, "rebaseline", "manual_adjust")
    assert conn.execute("SELECT COUNT(*) FROM points_ledger WHERE bale_user_id=8101").fetchone()[0] == 2
    # اجرای دوبارهٔ rebaseline: چیزی برای ثبت نیست
    conn.close()
    rb2 = mig.run_rebaseline(legacy, apply=True, reason="تطبیق پس از دورهٔ guard-off", actor_id=1)
    assert rb2["rebaseline_rows_created"] == 0 and rb2["mismatched"] == 0


def test_cli_requires_apply_and_yes_together(legacy, capsys):
    with pytest.raises(SystemExit):
        mig.main(["--database", str(legacy), "--apply"])
    with pytest.raises(SystemExit):
        mig.main(["--database", str(legacy), "--yes"])
    assert mig.main(["--database", str(legacy), "--json"]) == 0
    out = capsys.readouterr().out
    assert '"mode": "dry-run"' in out and "الف" not in out
    assert mig.main(["--database", str(legacy / "missing")]) == 2


def test_apply_refuses_when_bot_lock_alive(legacy, tmp_path, monkeypatch):
    lock = mig.BASE / ".bot.lock"
    existed = lock.exists()
    if existed:
        pytest.skip("قفل واقعی ربات وجود دارد")
    lock.write_text(f"{os.getpid()}|now", encoding="utf-8")
    try:
        with pytest.raises(mig.OpeningError, match="bot_is_running"):
            mig.run_opening(legacy, apply=True, backup_dir=tmp_path / "bk")
    finally:
        lock.unlink(missing_ok=True)
    assert not (tmp_path / "bk").exists()


def test_legacy_audit_reports_ledger_without_fixing(legacy, tmp_path):
    import legacy_data_audit as audit

    pre = audit.run_audit(legacy)["legacy"]["club"]["points_ledger"]
    assert pre == {"installed": False, "note": pre["note"]}
    mig.run_opening(legacy, apply=True, backup_dir=tmp_path / "bk")
    import database

    database.close_db()
    before = _sha(legacy)
    rep = audit.run_audit(legacy)["legacy"]["club"]["points_ledger"]
    assert rep["installed"] and rep["opening_rows"] == 3 and rep["entries"] == 3
    assert rep["counter_vs_ledger_mismatched_users"] == 0 and rep["users_nonzero_without_opening"] == 0
    assert rep["negative_balances"] == 1 and rep["duplicate_keys"] == 0 and rep["chain_breaks"] == 0
    assert rep["reconciled"] is True and rep["guard_installed"] and rep["immutability_installed"]
    assert rep["sync"] == {"pending": 3}
    assert "opening_applied_at" in rep["meta"]
    assert _sha(legacy) == before          # ممیزی فقط‌خواندنی است
