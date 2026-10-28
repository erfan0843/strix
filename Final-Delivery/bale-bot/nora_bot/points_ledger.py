"""دفترکل امتیاز باشگاه — تنها مسیر مجاز تغییر ``users.total_points``.

اصول (سند ``PHASE5-POINTS-LEDGER-DESIGN`` + اصلاحیهٔ فاز ششم):

* هر تغییر موجودی یک ردیف در ``points_ledger`` است؛ ``users.total_points`` فقط
  نسخهٔ cache شدهٔ آخرین ``balance_after`` است و فقط همین ماژول آن را می‌نویسد.
* ``post_points`` درج ردیف و به‌روزرسانی موجودی را در **یک تراکنش** روی همان
  اتصال انجام می‌دهد؛ اگر فراخوان داخل ``db_transaction`` باشد، در همان
  تراکنش شرکت می‌کند تا وضعیت عملیات تجاری هم اتمیک باشد.
* کلید ``(source, ref_key)`` یکتاست؛ تکرار همان رویداد تجاری → ردیف موجود
  برمی‌گردد و موجودی تغییر نمی‌کند (``created=False``).
* ردیف‌ها تغییرناپذیرند (trigger های پایگاه)؛ اصلاح فقط با ردیف ``reversal``.
* نگهبان پایگاه: trigger روی ``users`` هر تغییر ``total_points`` خارج از
  ``post_points`` را رد می‌کند (``points_ledger_guard``).
* این ماژول هیچ قانون امتیازدهی تازه‌ای ندارد؛ مبلغ و شرایط را فراخوان
  (همان کد قبلی) تعیین می‌کند.
"""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Any

from database import db_execute, db_transaction, in_transaction, log

ENTRY_TYPES = ("opening_balance", "award", "spend", "refund", "reversal", "manual_adjust")
SOURCES = (
    "legacy_counter",      # افتتاحیه از شمارندهٔ قدیمی
    "achievement",         # club.check_achievements
    "point_rule",          # occasions.check_point_rules
    "birthday",            # occasions.send_birthday_greetings
    "occasion",            # occasions.send_occasion_greetings
    "event_finished",      # events.set_event_status(finished)
    "attendance_session",  # attendance._award_points (دستی، کد/موقعیت، attendance_auto)
    "survey",              # survey.mark_answered (امتیاز نظرسنجی رویداد)
    "lottery_prize",       # lottery.run_draw
    "reward_redeem",       # club.do_buy
    "reward_reject_refund",  # club.handle_request(reject)
    "payment_spend",       # payments._do_points_payment
    "admin_manual",        # تعدیل دستی سوپرادمین
    "rebaseline",          # baseline مجدد صریح پس از دورهٔ معلق
    "reversal",            # reverse_entry
)
ACTOR_KINDS = ("system", "admin", "user")
SYNC_STATUSES = ("pending", "mirrored", "unmapped", "failed")

_REF_KEY = re.compile(r"[A-Za-z0-9:_.\-]{1,200}\Z")
_USER_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
_IMMUTABLE_COLUMNS = (
    "id", "bale_user_id", "delta", "balance_after", "entry_type", "source", "ref_key",
    "ref_table", "ref_id", "reason", "actor_kind", "actor_id", "reverses_id", "meta", "created_at",
)
_MIN_REASON = 3
_MAX_REASON = 500
_MAX_META = 2000

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS points_ledger_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""",
    "INSERT OR IGNORE INTO points_ledger_meta(key, value) VALUES ('write_gate', '0')",
    "INSERT OR IGNORE INTO points_ledger_meta(key, value) VALUES ('schema_version', '1')",
    "INSERT OR IGNORE INTO points_ledger_meta(key, value) VALUES "
    "('installed_at', strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
    f"""CREATE TABLE IF NOT EXISTS points_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bale_user_id INTEGER NOT NULL CHECK (bale_user_id > 0),
        delta INTEGER NOT NULL CHECK (delta <> 0),
        balance_after INTEGER NOT NULL,
        entry_type TEXT NOT NULL CHECK (entry_type IN ({",".join("'%s'" % t for t in ENTRY_TYPES)})),
        source TEXT NOT NULL CHECK (source IN ({",".join("'%s'" % s for s in SOURCES)})),
        ref_key TEXT NOT NULL CHECK (length(ref_key) BETWEEN 1 AND 200),
        ref_table TEXT,
        ref_id INTEGER,
        reason TEXT NOT NULL DEFAULT '',
        actor_kind TEXT NOT NULL CHECK (actor_kind IN ('system','admin','user')),
        actor_id INTEGER,
        reverses_id INTEGER UNIQUE REFERENCES points_ledger(id),
        meta TEXT,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        shared_entry_id TEXT,
        shared_status TEXT NOT NULL DEFAULT 'pending'
            CHECK (shared_status IN ('pending','mirrored','unmapped','failed')),
        shared_attempts INTEGER NOT NULL DEFAULT 0,
        shared_error TEXT,
        shared_synced_at TEXT,
        UNIQUE (source, ref_key),
        CHECK (entry_type <> 'reversal' OR reverses_id IS NOT NULL),
        CHECK (entry_type NOT IN ('manual_adjust','reversal') OR length(trim(reason)) >= {_MIN_REASON}),
        CHECK (entry_type <> 'opening_balance' OR source = 'legacy_counter'),
        CHECK ((entry_type IN ('award','refund','opening_balance','manual_adjust','reversal') OR delta < 0)
               AND (entry_type IN ('spend','opening_balance','manual_adjust','reversal') OR delta > 0))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_points_ledger_user ON points_ledger(bale_user_id, id)",
    "CREATE INDEX IF NOT EXISTS idx_points_ledger_sync ON points_ledger(shared_status, id)",
    # تغییرناپذیری: فقط ستون‌های وضعیت همگام‌سازی سرور قابل به‌روزرسانی‌اند.
    f"""CREATE TRIGGER IF NOT EXISTS trg_points_ledger_no_update
        BEFORE UPDATE OF {", ".join(_IMMUTABLE_COLUMNS)} ON points_ledger
        BEGIN SELECT RAISE(ABORT, 'points_ledger_immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS trg_points_ledger_no_delete
        BEFORE DELETE ON points_ledger
        BEGIN SELECT RAISE(ABORT, 'points_ledger_immutable'); END""",
]

_GUARD_TRIGGERS = [
    """CREATE TRIGGER IF NOT EXISTS trg_users_points_guard_update
        BEFORE UPDATE OF total_points ON users
        WHEN COALESCE(NEW.total_points, 0) <> COALESCE(OLD.total_points, 0)
         AND COALESCE((SELECT value FROM points_ledger_meta WHERE key='write_gate'), '0') <> '1'
        BEGIN SELECT RAISE(ABORT, 'points_ledger_guard'); END""",
    """CREATE TRIGGER IF NOT EXISTS trg_users_points_guard_insert
        BEFORE INSERT ON users
        WHEN COALESCE(NEW.total_points, 0) <> 0
         AND COALESCE((SELECT value FROM points_ledger_meta WHERE key='write_gate'), '0') <> '1'
        BEGIN SELECT RAISE(ABORT, 'points_ledger_guard'); END""",
]
_GUARD_NAMES = ("trg_users_points_guard_update", "trg_users_points_guard_insert")


class LedgerError(RuntimeError):
    """خطای دفترکل با کد پایدار (بدون دادهٔ حساس)."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code if not detail else f"{code}: {detail}")
        self.code = code
        self.detail = detail


class InsufficientPoints(LedgerError):
    def __init__(self, have: int, need: int):
        super().__init__("insufficient_points")
        self.have = int(have)
        self.need = int(need)


@dataclass(frozen=True)
class PostResult:
    created: bool          # ردیف تازه ثبت شد (False = تکرار همان رویداد)
    entry_id: int
    delta: int
    balance_before: int
    balance_after: int

    @property
    def duplicate(self) -> bool:
        return not self.created


# ───────────────────────── schema ─────────────────────────
def ensure_schema(*, guard: bool | None = None) -> None:
    """جدول‌ها، قیدها و trigger ها را (idempotent) می‌سازد.

    نگهبان ``users.total_points`` فقط وقتی نصب می‌شود که پایگاه نیاز به افتتاحیه
    نداشته باشد (پایگاه تازه، یا افتتاحیه اجرا شده)؛ وگرنه اجرای ``doctor`` یا
    نسخهٔ تازه روی پایگاهی که هنوز ربات قدیمی رویش کار می‌کند، امتیازدهی قدیمی را
    پیش از زمان برنامه‌ریزی‌شده متوقف می‌کرد. اسکریپت افتتاحیه پس از ``--apply``
    نگهبان را نصب می‌کند.
    """
    with db_transaction() as conn:
        for q in _SCHEMA:
            conn.execute(q)
        if guard is None:
            guard = meta_get("guard_disabled_at") is None and not needs_opening()
        if guard:
            for q in _GUARD_TRIGGERS:
                conn.execute(q)


def needs_opening() -> bool:
    """آیا کاربری با ``total_points<>0`` و بدون هیچ ردیف دفترکل وجود دارد؟"""
    row = db_execute(
        """SELECT COUNT(*) AS c FROM users u
           WHERE COALESCE(u.total_points,0) <> 0 AND u.bale_user_id IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM points_ledger l WHERE l.bale_user_id = u.bale_user_id)""",
        fetch="one")
    return bool(row and int(row["c"]) > 0)


def startup_check() -> list[str]:
    """پیش‌شرط‌های اجرای ربات با دفترکل؛ لیست خطاها (خالی = مجاز)."""
    problems: list[str] = []
    if needs_opening():
        problems.append(
            "کاربرانی با موجودی غیرصفر و بدون ردیف افتتاحیهٔ دفترکل وجود دارند؛ "
            "ابتدا با ربات متوقف و پشتیبان معتبر، اسکریپت migrate_points_opening_balance.py را "
            "(dry-run و سپس --apply --yes) اجرا کنید.")
    if not guard_installed():
        if meta_get("guard_disabled_at"):
            problems.append(
                "نگهبان total_points آگاهانه حذف شده (guard-off)؛ پیش از اجرای نسخهٔ دفترکل، "
                "rebaseline و نصب دوبارهٔ نگهبان لازم است "
                "(migrate_points_opening_balance.py rebaseline / guard-on).")
        else:
            problems.append("نگهبان total_points نصب نیست.")
    return problems


def guard_installed() -> bool:
    rows = db_execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND name IN (?,?)",
        _GUARD_NAMES, fetch="all") or []
    return len(rows) == len(_GUARD_NAMES)


def meta_get(key: str, default: str | None = None) -> str | None:
    row = db_execute("SELECT value FROM points_ledger_meta WHERE key=?", (key,), fetch="one")
    return str(row["value"]) if row else default


def _meta_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO points_ledger_meta(key, value) VALUES (?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def disable_guard(*, reason: str, actor_id: int | None) -> None:
    """حذف آگاهانهٔ نگهبان (فقط برای بازگشت اضطراری؛ ثبت‌شده در meta)."""
    reason = _clean_reason(reason, required=True)
    with db_transaction() as conn:
        for name in _GUARD_NAMES:
            conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        _meta_set(conn, "guard_disabled_at", _now_sql(conn))
        _meta_set(conn, "guard_disabled_reason", reason)
        _meta_set(conn, "guard_disabled_by", str(int(actor_id)) if actor_id else "")


def enable_guard() -> None:
    with db_transaction() as conn:
        for q in _GUARD_TRIGGERS:
            conn.execute(q)
        _meta_set(conn, "guard_enabled_at", _now_sql(conn))


def _now_sql(conn: sqlite3.Connection) -> str:
    return str(conn.execute("SELECT strftime('%Y-%m-%dT%H:%M:%SZ','now')").fetchone()[0])


# ───────────────────────── validation ─────────────────────────
def _int(value: Any, code: str) -> int:
    if isinstance(value, bool):
        raise LedgerError(code)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise LedgerError(code) from None


def _user_id(value: Any) -> int:
    if value is None or not _USER_ID.fullmatch(str(value).strip()):
        raise LedgerError("invalid_user_id")
    return int(str(value).strip())


def _clean_reason(reason: Any, *, required: bool) -> str:
    text = "" if reason is None else str(reason).replace("\x00", "").strip()
    if required and len(text) < _MIN_REASON:
        raise LedgerError("reason_required")
    return text[:_MAX_REASON]


def _clean_meta(meta: Any) -> str | None:
    if meta is None:
        return None
    if not isinstance(meta, dict):
        raise LedgerError("invalid_meta")
    text = json.dumps(meta, ensure_ascii=False, sort_keys=True, default=str)
    if len(text) > _MAX_META:
        raise LedgerError("invalid_meta")
    return text


def new_manual_key() -> str:
    return f"manual:{uuid.uuid4()}"


# ───────────────────────── reads ─────────────────────────
def last_entry(bale_user_id: int) -> dict[str, Any] | None:
    return db_execute(
        "SELECT * FROM points_ledger WHERE bale_user_id=? ORDER BY id DESC LIMIT 1",
        (int(bale_user_id),), fetch="one")


def balance(bale_user_id: int) -> int:
    row = last_entry(bale_user_id)
    return int(row["balance_after"]) if row else 0


def find_entry(source: str, ref_key: str) -> dict[str, Any] | None:
    return db_execute(
        "SELECT * FROM points_ledger WHERE source=? AND ref_key=?",
        (source, ref_key), fetch="one")


def get_entry(entry_id: int) -> dict[str, Any] | None:
    return db_execute("SELECT * FROM points_ledger WHERE id=?", (int(entry_id),), fetch="one")


def list_entries(bale_user_id: int, limit: int = 20, before_id: int | None = None) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    if before_id:
        return db_execute(
            "SELECT * FROM points_ledger WHERE bale_user_id=? AND id<? ORDER BY id DESC LIMIT ?",
            (int(bale_user_id), int(before_id), limit), fetch="all") or []
    return db_execute(
        "SELECT * FROM points_ledger WHERE bale_user_id=? ORDER BY id DESC LIMIT ?",
        (int(bale_user_id), limit), fetch="all") or []


# ───────────────────────── write path ─────────────────────────
def post_points(
    bale_user_id: int,
    delta: int,
    *,
    entry_type: str,
    source: str,
    ref_key: str,
    reason: str = "",
    actor_kind: str = "system",
    actor_id: int | None = None,
    ref_table: str | None = None,
    ref_id: int | None = None,
    reverses_id: int | None = None,
    meta: dict[str, Any] | None = None,
    allow_negative: bool = False,
) -> PostResult:
    """ثبت یک تغییر موجودی؛ اتمیک و idempotent روی ``(source, ref_key)``.

    * تکرار همان کلید → ``PostResult(created=False)`` بدون هیچ تغییری.
    * موجودی منفی (به‌جز افتتاحیه یا ``allow_negative``) → ``InsufficientPoints`` و rollback.
    * کاربر بدون ردیف دفترکل ولی با ``total_points<>0`` → ``opening_balance_missing``
      (ترتیب نادرست راه‌اندازی به‌جای تاریخچهٔ ناسازگار، شکست صریح می‌دهد).
    """
    uid = _user_id(bale_user_id)
    delta = _int(delta, "invalid_delta")
    if entry_type not in ENTRY_TYPES:
        raise LedgerError("invalid_entry_type")
    if source not in SOURCES:
        raise LedgerError("invalid_source")
    if not isinstance(ref_key, str) or not _REF_KEY.fullmatch(ref_key):
        raise LedgerError("invalid_ref_key")
    if actor_kind not in ACTOR_KINDS:
        raise LedgerError("invalid_actor")
    actor_id = None if actor_id is None else _int(actor_id, "invalid_actor")
    ref_id = None if ref_id is None else _int(ref_id, "invalid_ref")
    if ref_table is not None and (not isinstance(ref_table, str) or not re.fullmatch(r"[a-z_]{1,60}", ref_table)):
        raise LedgerError("invalid_ref")
    reverses_id = None if reverses_id is None else _int(reverses_id, "invalid_reverses_id")
    reason = _clean_reason(reason, required=entry_type in ("manual_adjust", "reversal"))
    meta_text = _clean_meta(meta)
    if delta == 0:
        raise LedgerError("zero_delta")
    if entry_type == "award" or entry_type == "refund":
        if delta < 0:
            raise LedgerError("delta_sign_mismatch")
    elif entry_type == "spend" and delta > 0:
        raise LedgerError("delta_sign_mismatch")
    if entry_type == "reversal" and reverses_id is None:
        raise LedgerError("reverses_id_required")
    if entry_type == "opening_balance" and source != "legacy_counter":
        raise LedgerError("invalid_source")

    with db_transaction() as conn:
        existing = conn.execute(
            "SELECT id, delta, balance_after FROM points_ledger WHERE source=? AND ref_key=?",
            (source, ref_key)).fetchone()
        if existing:
            d = int(existing["delta"])
            after = int(existing["balance_after"])
            return PostResult(False, int(existing["id"]), d, after - d, after)

        user = conn.execute(
            "SELECT COALESCE(total_points, 0) AS tp FROM users WHERE bale_user_id=?", (uid,)).fetchone()
        if not user:
            raise LedgerError("user_not_found")
        current = int(user["tp"])
        last = conn.execute(
            "SELECT id, balance_after FROM points_ledger WHERE bale_user_id=? ORDER BY id DESC LIMIT 1",
            (uid,)).fetchone()

        if entry_type == "opening_balance":
            if last is not None:
                raise LedgerError("opening_balance_conflict")
            if delta != current:
                raise LedgerError("opening_balance_mismatch")
            new_balance = current
        elif source == "rebaseline":
            # baseline مجدد صریح: اختلاف شمارنده با دفترکل را به‌عنوان یک ردیف
            # قابل ممیزی ثبت می‌کند؛ شمارنده تغییر نمی‌کند.
            if entry_type != "manual_adjust":
                raise LedgerError("invalid_entry_type")
            base = int(last["balance_after"]) if last is not None else 0
            if base + delta != current:
                raise LedgerError("rebaseline_mismatch")
            new_balance = current
        else:
            if last is None and current != 0:
                raise LedgerError("opening_balance_missing")
            if last is not None and int(last["balance_after"]) != current:
                # شمارنده بیرون از دفترکل تغییر کرده (مثلاً در دورهٔ guard-off)
                raise LedgerError("balance_out_of_sync")
            new_balance = current + delta
            if new_balance < 0 and not allow_negative:
                raise InsufficientPoints(current, -delta)

        if reverses_id is not None:
            orig = conn.execute(
                "SELECT id, bale_user_id, delta, entry_type FROM points_ledger WHERE id=?",
                (reverses_id,)).fetchone()
            if not orig:
                raise LedgerError("reverses_unknown")
            if int(orig["bale_user_id"]) != uid:
                raise LedgerError("reverses_other_user")
            if orig["entry_type"] in ("reversal", "opening_balance"):
                raise LedgerError("cannot_reverse_entry_type")
            if conn.execute("SELECT 1 FROM points_ledger WHERE reverses_id=?", (reverses_id,)).fetchone():
                raise LedgerError("already_reversed")
            if entry_type == "reversal" and delta != -int(orig["delta"]):
                raise LedgerError("reversal_delta_mismatch")

        try:
            cur = conn.execute(
                """INSERT INTO points_ledger
                   (bale_user_id, delta, balance_after, entry_type, source, ref_key,
                    ref_table, ref_id, reason, actor_kind, actor_id, reverses_id, meta)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (uid, delta, new_balance, entry_type, source, ref_key, ref_table, ref_id,
                 reason, actor_kind, actor_id, reverses_id, meta_text))
        except sqlite3.IntegrityError as exc:
            raise LedgerError("ledger_constraint", type(exc).__name__) from None
        entry_id = int(cur.lastrowid)

        if entry_type != "opening_balance" and new_balance != current:
            conn.execute("UPDATE points_ledger_meta SET value='1' WHERE key='write_gate'")
            try:
                res = conn.execute(
                    "UPDATE users SET total_points=? WHERE bale_user_id=? AND COALESCE(total_points,0)=?",
                    (new_balance, uid, current))
                if res.rowcount != 1:
                    raise LedgerError("balance_update_failed")
            finally:
                conn.execute("UPDATE points_ledger_meta SET value='0' WHERE key='write_gate'")
        return PostResult(True, entry_id, delta, current, new_balance)


def reverse_entry(
    entry_id: int,
    *,
    reason: str,
    actor_kind: str = "admin",
    actor_id: int | None = None,
    allow_negative: bool = False,
) -> PostResult:
    """ردیف اصلاحی معکوس (تنها راه «ویرایش»). هر ردیف فقط یک‌بار قابل برگشت است."""
    entry_id = _int(entry_id, "invalid_entry_id")
    with db_transaction():
        orig = get_entry(entry_id)
        if not orig:
            raise LedgerError("reverses_unknown")
        if db_execute("SELECT id FROM points_ledger WHERE reverses_id=?", (entry_id,), fetch="one"):
            raise LedgerError("already_reversed")
        return post_points(
            int(orig["bale_user_id"]), -int(orig["delta"]),
            entry_type="reversal", source="reversal", ref_key=f"rev:{entry_id}",
            reason=reason, actor_kind=actor_kind, actor_id=actor_id,
            ref_table="points_ledger", ref_id=entry_id, reverses_id=entry_id,
            allow_negative=allow_negative)


def post_opening_balance(bale_user_id: int, *, reason: str, meta: dict[str, Any] | None = None) -> PostResult:
    """ردیف افتتاحیه برای یک کاربر با ``total_points<>0`` (اسکریپت راه‌اندازی L1)."""
    uid = _user_id(bale_user_id)
    row = db_execute("SELECT COALESCE(total_points,0) AS tp FROM users WHERE bale_user_id=?", (uid,), fetch="one")
    if not row:
        raise LedgerError("user_not_found")
    current = int(row["tp"])
    if current == 0:
        raise LedgerError("zero_delta")
    flags = dict(meta or {})
    if current < 0:
        flags["flag"] = "negative_opening"
    return post_points(
        uid, current, entry_type="opening_balance", source="legacy_counter",
        ref_key=f"opening:{uid}", reason=reason, actor_kind="system", meta=flags or None)


# ───────────────────────── health / reconcile ─────────────────────────
def reconcile(limit_examples: int = 20) -> dict[str, Any]:
    """تطبیق شمارنده با دفترکل؛ **فقط گزارش**، هیچ اصلاحی انجام نمی‌دهد."""
    out: dict[str, Any] = {
        "installed": False,
        "guard_installed": False,
        "users_total": 0,
        "users_nonzero": 0,
        "users_with_ledger": 0,
        "users_without_opening": 0,      # total_points<>0 و هیچ ردیفی
        "mismatched": 0,                 # total_points != آخرین balance_after
        "negative_balances": 0,
        "invalid_user_ids": 0,
        "entries": 0,
        "chain_breaks": 0,               # balance_after - delta != balance قبلی
        "missing_business_ref": 0,       # award/spend/refund بدون ref_table/ref_id
        "orphan_entries": 0,             # ردیف بدون کاربر
        "sync": {s: 0 for s in SYNC_STATUSES},
        "by_entry_type": {},
        "examples": {"mismatched": [], "without_opening": [], "chain_breaks": []},
        "meta": {},
    }
    installed = db_execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='points_ledger'", fetch="one")
    out["installed"] = bool(installed)
    if not installed:
        return out
    out["guard_installed"] = guard_installed()
    for k in ("installed_at", "schema_version", "guard_disabled_at", "guard_disabled_reason",
              "guard_enabled_at", "opening_applied_at"):
        v = meta_get(k)
        if v is not None:
            out["meta"][k] = v

    users = db_execute(
        "SELECT bale_user_id, COALESCE(total_points,0) AS tp FROM users", fetch="all") or []
    lasts = {int(r["bale_user_id"]): int(r["balance_after"]) for r in (db_execute(
        """SELECT l.bale_user_id, l.balance_after FROM points_ledger l
           JOIN (SELECT bale_user_id, MAX(id) AS mid FROM points_ledger GROUP BY bale_user_id) m
             ON m.mid = l.id""", fetch="all") or [])}
    out["users_total"] = len(users)
    out["users_with_ledger"] = len(lasts)
    for u in users:
        raw = u.get("bale_user_id")
        tp = int(u["tp"])
        if raw is None or not _USER_ID.fullmatch(str(raw)):
            out["invalid_user_ids"] += 1
            continue
        uid = int(raw)
        if tp != 0:
            out["users_nonzero"] += 1
        if tp < 0:
            out["negative_balances"] += 1
        if uid in lasts:
            if lasts[uid] != tp:
                out["mismatched"] += 1
                if len(out["examples"]["mismatched"]) < limit_examples:
                    out["examples"]["mismatched"].append(
                        {"bale_user_id": uid, "total_points": tp, "ledger": lasts[uid]})
        elif tp != 0:
            out["users_without_opening"] += 1
            if len(out["examples"]["without_opening"]) < limit_examples:
                out["examples"]["without_opening"].append({"bale_user_id": uid, "total_points": tp})

    out["entries"] = int(db_execute("SELECT COUNT(*) AS c FROM points_ledger", fetch="one")["c"])
    for r in db_execute(
            "SELECT entry_type, COUNT(*) AS c, SUM(delta) AS s FROM points_ledger GROUP BY entry_type",
            fetch="all") or []:
        out["by_entry_type"][r["entry_type"]] = {"count": int(r["c"]), "sum": int(r["s"] or 0)}
    for r in db_execute(
            "SELECT shared_status, COUNT(*) AS c FROM points_ledger GROUP BY shared_status",
            fetch="all") or []:
        out["sync"][str(r["shared_status"])] = int(r["c"])
    out["missing_business_ref"] = int(db_execute(
        """SELECT COUNT(*) AS c FROM points_ledger
           WHERE entry_type IN ('award','spend','refund') AND (ref_table IS NULL OR ref_id IS NULL)""",
        fetch="one")["c"])
    out["orphan_entries"] = int(db_execute(
        """SELECT COUNT(*) AS c FROM points_ledger l
           WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.bale_user_id = l.bale_user_id)""",
        fetch="one")["c"])
    # زنجیرهٔ موجودی هر کاربر
    prev: dict[int, int] = {}
    for r in db_execute(
            "SELECT id, bale_user_id, delta, balance_after, entry_type FROM points_ledger ORDER BY id",
            fetch="all") or []:
        uid = int(r["bale_user_id"])
        before = prev.get(uid, 0)
        expected = before if r["entry_type"] == "opening_balance" else before + int(r["delta"])
        if r["entry_type"] == "opening_balance":
            expected = int(r["delta"])
        if int(r["balance_after"]) != expected:
            out["chain_breaks"] += 1
            if len(out["examples"]["chain_breaks"]) < limit_examples:
                out["examples"]["chain_breaks"].append({"id": int(r["id"]), "bale_user_id": uid})
        prev[uid] = int(r["balance_after"])
    out["ok"] = (
        out["mismatched"] == 0 and out["users_without_opening"] == 0 and out["chain_breaks"] == 0
        and out["orphan_entries"] == 0 and out["guard_installed"]
    )
    return out


def health_report() -> dict[str, Any]:
    """خلاصهٔ قابل‌چاپ برای doctor/ممیزی (فقط گزارش)."""
    rep = reconcile()
    problems: list[str] = []
    if not rep["installed"]:
        problems.append("جدول points_ledger وجود ندارد (دفترکل نصب نشده)")
        return {"ok": False, "problems": problems, "report": rep}
    if not rep["guard_installed"]:
        problems.append("نگهبان total_points نصب نیست (دورهٔ guard-off؛ شمارنده ممکن است جدا افتاده باشد)")
    if rep["users_without_opening"]:
        problems.append(f"{rep['users_without_opening']} کاربر با موجودی غیرصفر و بدون ردیف افتتاحیه")
    if rep["mismatched"]:
        problems.append(f"{rep['mismatched']} کاربر: total_points با آخرین balance_after فرق دارد")
    if rep["chain_breaks"]:
        problems.append(f"{rep['chain_breaks']} ردیف با زنجیرهٔ موجودی شکسته")
    if rep["orphan_entries"]:
        problems.append(f"{rep['orphan_entries']} ردیف بدون کاربر")
    if rep["missing_business_ref"]:
        problems.append(f"{rep['missing_business_ref']} ردیف award/spend/refund بدون مرجع تجاری")
    # هشدارها: سازگاری دفترکل را نمی‌شکنند ولی باید جداگانه بررسی و تصمیم‌گیری شوند
    warnings: list[str] = []
    if rep["negative_balances"]:
        warnings.append(f"{rep['negative_balances']} کاربر با موجودی منفی (گزارش؛ اصلاح خودکار نمی‌شود)")
    if rep["invalid_user_ids"]:
        warnings.append(f"{rep['invalid_user_ids']} کاربر با شناسهٔ بله نامعتبر (قابل همگام‌سازی نیست)")
    return {"ok": rep["ok"] and not problems, "problems": problems, "warnings": warnings, "report": rep}


# ───────────────────────── server mirror ─────────────────────────
def _mark_sync(entry_id: int, status: str, *, shared_id: str | None = None, error: str | None = None) -> None:
    if status not in SYNC_STATUSES:
        raise LedgerError("invalid_sync_status")
    db_execute(
        """UPDATE points_ledger SET shared_status=?, shared_entry_id=COALESCE(?, shared_entry_id),
           shared_attempts=shared_attempts+1, shared_error=?,
           shared_synced_at=CASE WHEN ?='mirrored' THEN strftime('%Y-%m-%dT%H:%M:%SZ','now')
                                 ELSE shared_synced_at END
           WHERE id=?""",
        (status, shared_id, (error or "")[:80] or None, status, int(entry_id)))


def build_sync_payload(entry: dict[str, Any], *, source_key: str) -> dict[str, Any]:
    """دادهٔ آینه برای سرور؛ بدون شناسهٔ خام ادمین، بدون توکن."""
    return {
        "ledger_id": int(entry["id"]),
        "delta": int(entry["delta"]),
        "balance_after": int(entry["balance_after"]),
        "entry_type": str(entry["entry_type"]),
        "source": str(entry["source"]),
        "ref_key": str(entry["ref_key"]),
        "reason": str(entry.get("reason") or "")[:_MAX_REASON],
        "actor_kind": str(entry.get("actor_kind") or "system"),
        "reverses_external_key": (
            f"{source_key}:{int(entry['reverses_id'])}" if entry.get("reverses_id") else None),
        "created_at": str(entry.get("created_at") or ""),
    }


def sync_entry(entry_id: int, *, api_client=None) -> dict[str, Any]:
    """یک ردیف را به سرور می‌فرستد (idempotent روی external_key پایدار).

    خروجی: ``{"outcome": mirrored|unmapped|failed|missing|skipped, "code": str|None}``.
    هرگز استثنا به بیرون نمی‌دهد؛ شکست شبکه = ``failed`` و قابل تکرار.
    """
    entry = get_entry(entry_id)
    if not entry:
        return {"outcome": "missing", "code": "entry_not_found"}
    if entry.get("shared_status") == "mirrored":
        return {"outcome": "mirrored", "code": None}
    if in_transaction():
        return {"outcome": "skipped", "code": "inside_transaction"}
    try:
        if api_client is None:
            import shared_api as api_client  # noqa: PLC0415
        import shared_certificates as sc  # noqa: PLC0415
        source_key = sc.source_id(db_execute, create=True) or ""
        external_key = f"{source_key}:{int(entry['id'])}"
        payload = build_sync_payload(entry, source_key=source_key)
        result = api_client.submit_points_entry(str(entry["bale_user_id"]), external_key, payload)
    except Exception as exc:  # SharedAPIError یا شبکه
        code = str(getattr(exc, "code", None) or type(exc).__name__)[:80]
        if code == "owner_identity_not_found":
            _mark_sync(entry_id, "unmapped", error=code)
            return {"outcome": "unmapped", "code": code}
        _mark_sync(entry_id, "failed", error=code)
        return {"outcome": "failed", "code": code}
    shared_id = result.get("id") if isinstance(result, dict) else None
    _mark_sync(entry_id, "mirrored", shared_id=str(shared_id) if shared_id else None, error=None)
    return {"outcome": "mirrored", "code": None}


def sync_pending(limit: int = 50, *, api_client=None, include_unmapped: bool = False) -> dict[str, int]:
    """تلاش دوباره برای ردیف‌های ارسال‌نشده/ناموفق (و در صورت درخواست، unmapped)."""
    from config import SHARED_API_URL  # noqa: PLC0415
    counts = {"mirrored": 0, "unmapped": 0, "failed": 0, "skipped": 0}
    if api_client is None and not SHARED_API_URL:
        return counts
    statuses = ["pending", "failed"] + (["unmapped"] if include_unmapped else [])
    rows = db_execute(
        f"SELECT id FROM points_ledger WHERE shared_status IN ({','.join('?' * len(statuses))}) "
        "ORDER BY id LIMIT ?", (*statuses, max(1, min(int(limit), 500))), fetch="all") or []
    for r in rows:
        res = sync_entry(int(r["id"]), api_client=api_client)
        counts[res["outcome"] if res["outcome"] in counts else "failed"] += 1
    return counts


def sync_after_commit(entry_id: int | None) -> None:
    """ارسال بهینه پس از commit؛ خطا فقط لاگ می‌شود و جریان ربات را نمی‌شکند."""
    if not entry_id or in_transaction():
        return
    try:
        from config import SHARED_API_URL  # noqa: PLC0415
        if not SHARED_API_URL:
            return
        res = sync_entry(int(entry_id))
        if res["outcome"] == "failed":
            log(f"⚠️ همگام‌سازی دفترکل {entry_id}: {res['code']}")
    except Exception as exc:
        log(f"⚠️ همگام‌سازی دفترکل {entry_id}: {type(exc).__name__}")
