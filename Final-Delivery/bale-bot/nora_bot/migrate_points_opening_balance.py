"""راه‌اندازی کنترل‌شدهٔ دفترکل امتیاز روی پایگاه ربات (L1) + ابزارهای بازگشت.

پیش‌فرض **dry-run** است و هیچ چیزی نمی‌نویسد. برای هر تغییری ``--apply --yes`` لازم است.

عمل‌ها (``--action``):
* ``opening`` (پیش‌فرض): برای هر کاربر با ``total_points<>0`` و شناسهٔ بلهٔ معتبر که
  هیچ ردیف دفترکل ندارد، دقیقاً یک ردیف ``opening_balance`` با کلید ``opening:{uid}``
  می‌نویسد؛ ``users.total_points`` دست نمی‌خورد؛ موجودی منفی صفر نمی‌شود (فقط
  علامت می‌خورد)؛ در پایان نگهبان ``total_points`` نصب و تطبیق چاپ می‌شود.
  اجرای دوباره بی‌اثر است (idempotent).
* ``report``: فقط گزارش سلامت/تطبیق (بدون تغییر).
* ``guard-off``: حذف آگاهانهٔ نگهبان برای اجرای نسخهٔ قدیمی (``--reason`` اجباری؛ ثبت در meta).
* ``guard-on``: نصب دوبارهٔ نگهبان (فقط اگر تطبیق صفر اختلاف باشد یا ``--force``).
* ``rebaseline``: پس از دورهٔ guard-off، اختلاف شمارنده با دفترکل را برای هر کاربر به‌صورت
  یک ردیف ``manual_adjust/rebaseline`` با دلیل اجباری ثبت می‌کند؛ شمارنده تغییر نمی‌کند.

پیش‌شرط‌های ``--apply``: ربات متوقف (قفل ``.bot.lock`` زنده نباشد)، پشتیبان تازه در
``--backup-dir`` گرفته و اعتبارسنجی شود (integrity_check + شمارش کاربران و جمع امتیاز برابر)،
checksum فایل پیش از تغییر ثبت شود.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import stat
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

_USER_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
OPENING_REASON = "موجودی شمارندهٔ قدیمی در لحظهٔ راه‌اندازی دفترکل؛ تاریخچهٔ پیش از آن بازسازی‌پذیر نیست"


class OpeningError(RuntimeError):
    """خطای امن بدون دادهٔ شخصی."""


# ───────────────────────── ابزارهای فایل ─────────────────────────
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _bot_running() -> str | None:
    lock = BASE / ".bot.lock"
    if not lock.exists():
        return None
    try:
        pid = lock.read_text(encoding="utf-8").strip().split("|")[0]
        os.kill(int(pid), 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        return None
    except OSError:
        return None


def _backup_database(database_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(backup_dir, 0o700)
    except OSError:
        pass
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = backup_dir / f"nora-before-points-ledger-{stamp}-{uuid.uuid4().hex[:8]}.sqlite"
    source = sqlite3.connect(database_path.as_uri() + "?mode=ro", uri=True)
    target = None
    try:
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        target = sqlite3.connect(destination)
        source.backup(target)
        target.commit()
        target.close()
        target = None
        os.chmod(destination, stat.S_IRUSR | stat.S_IWUSR)
        return destination
    except Exception:
        if target is not None:
            target.close()
        destination.unlink(missing_ok=True)
        raise
    finally:
        source.close()


def _counter_snapshot(path: Path) -> dict[str, Any]:
    """شمارش کاربران و جمع امتیاز (فقط‌خواندنی)."""
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        out: dict[str, Any] = {"integrity": integrity, "users_total": 0, "users_nonzero": 0,
                               "sum_points": 0, "negative": 0, "invalid_ids": 0, "ledger_installed": False,
                               "ledger_entries": 0, "already_opened": 0}
        if "total_points" not in cols or "bale_user_id" not in cols:
            out["users_table"] = "missing_columns"
            return out
        for r in conn.execute("SELECT bale_user_id, COALESCE(total_points,0) AS tp FROM users").fetchall():
            out["users_total"] += 1
            tp = int(r["tp"])
            raw = r["bale_user_id"]
            if tp != 0:
                out["users_nonzero"] += 1
                out["sum_points"] += tp
                if raw is None or not _USER_ID.fullmatch(str(raw)):
                    out["invalid_ids"] += 1
            if tp < 0:
                out["negative"] += 1
        has = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='points_ledger'").fetchone()
        if has:
            out["ledger_installed"] = True
            out["ledger_entries"] = int(conn.execute("SELECT COUNT(*) FROM points_ledger").fetchone()[0])
            out["already_opened"] = int(conn.execute(
                "SELECT COUNT(*) FROM points_ledger WHERE entry_type='opening_balance'").fetchone()[0])
            out["needs_opening"] = int(conn.execute(
                """SELECT COUNT(*) FROM users u WHERE COALESCE(u.total_points,0)<>0 AND u.bale_user_id IS NOT NULL
                   AND NOT EXISTS (SELECT 1 FROM points_ledger l WHERE l.bale_user_id=u.bale_user_id)""").fetchone()[0])
        else:
            out["needs_opening"] = out["users_nonzero"] - out["invalid_ids"]
        return out
    finally:
        conn.close()


# ───────────────────────── اتصال ماژول ربات به پایگاه هدف ─────────────────────────
def _bind_database(path: Path):
    import database

    database.close_db()
    database.DB_PATH = str(path)
    database._conn = None
    return database


# ───────────────────────── عمل‌ها ─────────────────────────
def run_opening(database_path: str | Path, *, apply: bool, backup_dir: str | Path | None) -> dict[str, Any]:
    path = Path(database_path).expanduser().resolve()
    if not path.is_file():
        raise OpeningError("database_not_found")
    summary: dict[str, Any] = {"action": "opening", "mode": "apply" if apply else "dry-run",
                               "database": path.name}
    before = _counter_snapshot(path)
    summary["before"] = before
    if before["integrity"] != "ok":
        raise OpeningError("integrity_check_failed")
    if before.get("users_table") == "missing_columns":
        raise OpeningError("users_table_incompatible")
    summary["planned_opening_rows"] = int(before.get("needs_opening") or 0)
    summary["skipped_invalid_ids"] = before["invalid_ids"]
    summary["negative_flagged"] = before["negative"]
    if not apply:
        summary["note"] = "dry-run: هیچ تغییری اعمال نشد"
        return summary

    pid = _bot_running()
    if pid:
        raise OpeningError("bot_is_running")
    summary["checksum_before"] = _sha256(path)
    bdir = Path(backup_dir).expanduser() if backup_dir else path.parent / "backups"
    backup = _backup_database(path, bdir)
    verify = _counter_snapshot(backup)
    if verify["integrity"] != "ok" or verify["users_total"] != before["users_total"] \
            or verify["sum_points"] != before["sum_points"]:
        backup.unlink(missing_ok=True)
        raise OpeningError("backup_verification_failed")
    summary["backup"] = {"file": backup.name, "sha256": _sha256(backup),
                         "users_total": verify["users_total"], "sum_points": verify["sum_points"]}

    database = _bind_database(path)
    import points_ledger as pl

    database.init_db()            # مهاجرت استاندارد + جدول دفترکل (بدون نگهبان تا پایان)
    created = existing = failed = 0
    failures: dict[str, int] = {}
    rows = database.db_execute(
        "SELECT bale_user_id, COALESCE(total_points,0) AS tp FROM users "
        "WHERE COALESCE(total_points,0)<>0 AND bale_user_id IS NOT NULL ORDER BY id", fetch="all") or []
    for r in rows:
        raw = r["bale_user_id"]
        if not _USER_ID.fullmatch(str(raw)):
            continue
        try:
            res = pl.post_opening_balance(int(raw), reason=OPENING_REASON)
        except pl.LedgerError as exc:
            if exc.code == "opening_balance_conflict":
                existing += 1          # کاربر از قبل ردیف دارد (اجرای دوباره)
                continue
            failed += 1
            failures[exc.code] = failures.get(exc.code, 0) + 1
            continue
        if res.created:
            created += 1
        else:
            existing += 1
    with database.db_transaction() as conn:
        for q in pl._GUARD_TRIGGERS:
            conn.execute(q)
        pl._meta_set(conn, "opening_applied_at", pl._now_sql(conn))
        pl._meta_set(conn, "opening_backup", backup.name)
        pl._meta_set(conn, "opening_checksum_before", summary["checksum_before"])
    summary["opening_rows_created"] = created
    summary["opening_rows_existing"] = existing
    summary["opening_rows_failed"] = failed
    summary["failures"] = failures
    database.close_db()
    summary["after"] = _counter_snapshot(path)
    summary["sum_points_unchanged"] = summary["after"]["sum_points"] == before["sum_points"]
    summary["users_unchanged"] = summary["after"]["users_total"] == before["users_total"]
    database = _bind_database(path)
    summary["health"] = pl.health_report()
    database.close_db()
    return summary


def run_report(database_path: str | Path) -> dict[str, Any]:
    path = Path(database_path).expanduser().resolve()
    if not path.is_file():
        raise OpeningError("database_not_found")
    snap = _counter_snapshot(path)
    out: dict[str, Any] = {"action": "report", "database": path.name, "counter": snap}
    if snap["ledger_installed"]:
        database = _bind_database(path)
        import points_ledger as pl
        out["health"] = pl.health_report()
        database.close_db()
    return out


def run_guard(database_path: str | Path, *, enable: bool, apply: bool, reason: str | None,
              actor_id: int | None, force: bool = False) -> dict[str, Any]:
    path = Path(database_path).expanduser().resolve()
    if not path.is_file():
        raise OpeningError("database_not_found")
    out: dict[str, Any] = {"action": "guard-on" if enable else "guard-off",
                           "mode": "apply" if apply else "dry-run", "database": path.name}
    database = _bind_database(path)
    import points_ledger as pl
    try:
        out["guard_installed_before"] = pl.guard_installed()
        if not apply:
            out["note"] = "dry-run: هیچ تغییری اعمال نشد"
            return out
        if _bot_running():
            raise OpeningError("bot_is_running")
        if enable:
            rep = pl.reconcile()
            if (rep["mismatched"] or rep["users_without_opening"]) and not force:
                out["reconcile"] = {k: rep[k] for k in ("mismatched", "users_without_opening")}
                raise OpeningError("reconcile_not_clean_use_rebaseline")
            pl.enable_guard()
        else:
            if not reason or len(reason.strip()) < 5:
                raise OpeningError("reason_required")
            pl.disable_guard(reason=reason, actor_id=actor_id)
        out["guard_installed_after"] = pl.guard_installed()
        out["meta"] = pl.reconcile()["meta"]
        return out
    finally:
        database.close_db()


def run_rebaseline(database_path: str | Path, *, apply: bool, reason: str | None,
                   actor_id: int | None) -> dict[str, Any]:
    path = Path(database_path).expanduser().resolve()
    if not path.is_file():
        raise OpeningError("database_not_found")
    out: dict[str, Any] = {"action": "rebaseline", "mode": "apply" if apply else "dry-run",
                           "database": path.name}
    database = _bind_database(path)
    import points_ledger as pl
    try:
        rep = pl.reconcile(limit_examples=10_000_000)
        if not rep["installed"]:
            raise OpeningError("ledger_not_installed")
        out["mismatched"] = rep["mismatched"]
        out["users_without_opening"] = rep["users_without_opening"]
        if not apply:
            out["note"] = "dry-run: هیچ تغییری اعمال نشد"
            return out
        if _bot_running():
            raise OpeningError("bot_is_running")
        if not reason or len(reason.strip()) < 5:
            raise OpeningError("reason_required")
        stamp = pl.meta_get("guard_disabled_at") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        tag = re.sub(r"[^A-Za-z0-9]", "", stamp)
        created = failed = 0
        failures: dict[str, int] = {}
        for ex in rep["examples"]["mismatched"]:
            uid = int(ex["bale_user_id"])
            delta = int(ex["total_points"]) - int(ex["ledger"])
            try:
                res = pl.post_points(
                    uid, delta, entry_type="manual_adjust", source="rebaseline",
                    ref_key=f"rebaseline:{uid}:{tag}", reason=reason.strip(),
                    actor_kind="admin", actor_id=actor_id,
                    meta={"counter": int(ex["total_points"]), "ledger_before": int(ex["ledger"])})
                created += int(res.created)
            except pl.LedgerError as exc:
                failed += 1
                failures[exc.code] = failures.get(exc.code, 0) + 1
        # افتتاحیه برای کاربرانی که در دورهٔ معلق اولین امتیازشان را گرفتند
        opened = 0
        for ex in rep["examples"]["without_opening"]:
            try:
                opened += int(pl.post_opening_balance(int(ex["bale_user_id"]), reason=OPENING_REASON).created)
            except pl.LedgerError as exc:
                failed += 1
                failures[exc.code] = failures.get(exc.code, 0) + 1
        out.update({"rebaseline_rows_created": created, "opening_rows_created": opened,
                    "failed": failed, "failures": failures})
        out["health"] = pl.health_report()
        return out
    finally:
        database.close_db()


def _print(summary: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
        return
    print(f"🏅 دفترکل امتیاز — {summary.get('action')} ({summary.get('mode', 'report')})")
    for k, v in summary.items():
        if k in ("action", "mode"):
            continue
        if isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                if isinstance(vv, (dict, list)):
                    print(f"    {kk}: {json.dumps(vv, ensure_ascii=False, default=str)[:400]}")
                else:
                    print(f"    {kk}: {vv}")
        else:
            print(f"  {k}: {v}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="راه‌اندازی/بازگشت دفترکل امتیاز روی پایگاه ربات؛ پیش‌فرض فقط‌خواندنی (dry-run).")
    parser.add_argument("--database", required=True, help="مسیر فایل SQLite ربات (نسخهٔ آزمایشی یا با تصمیم صریح مالک)")
    parser.add_argument("--action", choices=("opening", "report", "guard-off", "guard-on", "rebaseline"),
                        default="opening")
    parser.add_argument("--backup-dir", help="مسیر پشتیبان خصوصی برای --apply (پیش‌فرض: کنار پایگاه/backups)")
    parser.add_argument("--reason", help="دلیل (برای guard-off و rebaseline اجباری)")
    parser.add_argument("--actor-id", type=int, help="شناسهٔ بلهٔ مالک که عملیات را تأیید کرده (پیش‌فرض SUPER_ADMIN_ID)")
    parser.add_argument("--force", action="store_true", help="guard-on حتی با تطبیق ناتمام (توصیه نمی‌شود)")
    parser.add_argument("--apply", action="store_true", help="اعمال واقعی تغییرات")
    parser.add_argument("--yes", action="store_true", help="تأیید صریح برای --apply")
    parser.add_argument("--json", action="store_true", help="خروجی JSON بدون دادهٔ شخصی")
    args = parser.parse_args(argv)
    if args.yes and not args.apply:
        parser.error("--yes فقط همراه --apply مجاز است")
    if args.apply and not args.yes:
        parser.error("برای هر تغییری، هم --apply و هم --yes لازم است")
    actor = args.actor_id
    if actor is None:
        try:
            import config
            actor = int(config.SUPER_ADMIN_ID) or None
        except Exception:
            actor = None
    try:
        if args.action == "opening":
            summary = run_opening(args.database, apply=args.apply, backup_dir=args.backup_dir)
        elif args.action == "report":
            summary = run_report(args.database)
        elif args.action == "guard-off":
            summary = run_guard(args.database, enable=False, apply=args.apply, reason=args.reason, actor_id=actor)
        elif args.action == "guard-on":
            summary = run_guard(args.database, enable=True, apply=args.apply, reason=None, actor_id=actor,
                                force=args.force)
        else:
            summary = run_rebaseline(args.database, apply=args.apply, reason=args.reason, actor_id=actor)
    except OpeningError as exc:
        print(f"❌ انجام نشد: {exc}")
        return 2
    except Exception as exc:  # هرگز پیام خام با دادهٔ شخصی چاپ نمی‌شود
        print(f"❌ انجام نشد: {type(exc).__name__}")
        return 2
    _print(summary, args.json)
    health = summary.get("health")
    if isinstance(health, dict) and not health.get("ok", True):
        return 1
    if summary.get("opening_rows_failed") or summary.get("failed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
