"""ممیزی فقط-خواندنی دادهٔ legacy نورا — بدون هیچ تغییری در داده.

این ابزار برای مرحلهٔ «قبل از مهاجرت» است: می‌گوید چه داده‌ای کجاست، چه
رکوردهایی به کاربرِ ناموجود وصل‌اند، چه هویت‌هایی با هم تعارض دارند، و کدام
بخش‌ها آمادهٔ انتقال‌اند. هیچ جا نمی‌نویسد:

  • پایگاه SQLite با `mode=ro` باز می‌شود؛ اگر فایل قابل‌نوشتن باشد هم ابزار
    فقط SELECT می‌فرستد.
  • سمت سرور اختیاری است و فقط با `select()` کار می‌کند؛ هرگز `text()` یا DML.
  • خروجی هیچ شمارهٔ موبایل، نام، نشانی یا مسیر فایلی را چاپ نمی‌کند — فقط
    شمارش، شناسهٔ مبهم و کد وضعیت.

نمونهٔ اجرا::

    python legacy_data_audit.py --database /srv/nora/nora.db
    python legacy_data_audit.py --database nora.db --json
    python legacy_data_audit.py --database nora.db \\
        --server-database-url sqlite:////tmp/copy-of-server.db

برای هم‌بستگی هویت شماره‌ای، فلفل OTP لازم است؛ اگر داده نشود، آن بخش با
وضعیت «انجام نشد» گزارش می‌شود، نه با حدس.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable

REPORT_VERSION = 2

# دامنه‌ها فقط برای گروه‌بندی گزارش‌اند؛ منبع حقیقت همان جدول‌ها هستند.
_DOMAINS: dict[str, tuple[str, ...]] = {
    "users": ("users",),
    "profile": ("profile_submissions", "user_extra", "user_field_cache"),
    "forms": ("forms", "form_fields", "form_answers", "form_responses", "form_admins"),
    "events": ("events", "event_registrations", "event_ratings", "event_discount_usage"),
    "payments": (
        "transactions",
        "payment_receipts",
        "payment_links",
        "paylink_payments",
        "payment_schedules",
        "payment_gateways",
        "bank_cards",
    ),
    "attendance": (
        "attendance_sessions",
        "attendance_records",
        "att_presence",
        "att_rollcalls",
        "att_rollcall_answers",
        "att_tokens",
        "excuse_requests",
    ),
    "certificates": (
        "certificates",
        "cert_issues",
        "cert_batches",
        "cert_batch_rows",
        "cert_shares",
        "cert_templates",
        "cert_assets",
        "cert_verifies",
        "event_certs",
    ),
    "notifications": ("greeting_log", "survey_sends", "admin_inbox"),
    "support": ("tickets", "ticket_messages"),
    "content": ("about_links", "about_people", "occasions", "ads", "ad_campaigns", "rewards"),
}

# جدول‌هایی که باید برای مهاجرت سالم وجود داشته باشند.
_REQUIRED_TABLES = ("users", "forms", "form_responses", "events",
                    "event_registrations", "certificates", "transactions")

# جدول‌هایی که ردیف‌شان با bale_user_id به کاربر وصل است.
_BALE_LINKED_TABLES = (
    "form_responses",
    "event_registrations",
    "certificates",
    "transactions",
    "payment_receipts",
    "attendance_records",
    "att_presence",
    "tickets",
    "user_extra",
    "user_actions",
    "survey_sends",
    "greeting_log",
)

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


class AuditError(RuntimeError):
    """خطای preflight با کد کوتاه و بدون دادهٔ شخصی."""


# ───────────────────────────── ابزار پایه ─────────────────────────────

def _open_readonly(path: Path) -> sqlite3.Connection:
    if not path.exists() or not path.is_file():
        raise AuditError("database_not_found")
    # mode=ro تضمین می‌کند حتی یک نوشتن هم ممکن نباشد.
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _IDENT.fullmatch(table):
        raise AuditError("invalid_table_name")
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _count(conn: sqlite3.Connection, table: str) -> int:
    if not _IDENT.fullmatch(table):
        raise AuditError("invalid_table_name")
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0]) if row else 0


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row[0] or 0) if row else 0


def phone_digest(pepper: str, phone: str) -> str:
    """همان قاعدهٔ سرور: HMAC-SHA256(pepper, "phone:"+phone) — برای هم‌بستگی."""
    return hmac.new(pepper.encode("utf-8"), ("phone:" + phone).encode("ascii"),
                    hashlib.sha256).hexdigest()


def normalize_iran_phone(value: object) -> str | None:
    """نرمال‌سازی به ۰۹xxxxxxxxx؛ همان قاعدهٔ otp.py سرور (فقط خواندنی)."""
    if not isinstance(value, str):
        return None
    digits = "".join(ch for ch in value.translate(_DIGIT_MAP) if ch.isdigit())
    if not digits:
        return None
    if digits.startswith("0098"):
        digits = "0" + digits[4:]
    elif digits.startswith("98") and len(digits) == 12:
        digits = "0" + digits[2:]
    elif digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits
    elif digits.startswith("098"):
        digits = "0" + digits[3:]
    if len(digits) != 11 or not digits.startswith("09"):
        return None
    return digits


_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


# ───────────────────────────── بخش legacy ─────────────────────────────

def audit_legacy(database: Path) -> dict[str, Any]:
    conn = _open_readonly(database)
    try:
        tables = _tables(conn)
        if "users" not in tables:
            raise AuditError("legacy_database_without_users_table")

        counts = {
            domain: {name: _count(conn, name) for name in names if name in tables}
            for domain, names in _DOMAINS.items()
        }

        orphans: dict[str, int] = {}
        for table in _BALE_LINKED_TABLES:
            if table not in tables:
                continue
            cols = _columns(conn, table)
            if "bale_user_id" not in cols:
                continue
            orphans[table] = _scalar(
                conn,
                f"SELECT COUNT(*) FROM {table} t "
                f"WHERE t.bale_user_id IS NOT NULL AND t.bale_user_id <> '' "
                f"AND NOT EXISTS (SELECT 1 FROM users u WHERE u.bale_user_id = t.bale_user_id)",
            )

        users_n = _count(conn, "users")
        no_mobile = _scalar(
            conn, "SELECT COUNT(*) FROM users WHERE mobile IS NULL OR TRIM(mobile) = ''"
        )
        # تکرار باید روی «شمارهٔ نرمال‌شده» سنجیده شود، نه رشتهٔ خام؛ وگرنه
        # ۰۹۱۲... و 0912... دو کاربر جدا شمرده می‌شوند و تعارض پنهان می‌ماند.
        normalized_counts: dict[str, int] = {}
        for row in conn.execute(
            "SELECT mobile FROM users WHERE mobile IS NOT NULL AND TRIM(mobile) <> ''"
        ):
            normalized = normalize_iran_phone(row[0])
            if normalized is not None:
                normalized_counts[normalized] = normalized_counts.get(normalized, 0) + 1
        dup_mobiles = sum(1 for n in normalized_counts.values() if n > 1)
        dup_bale_ids = _scalar(
            conn,
            "SELECT COUNT(*) FROM (SELECT bale_user_id FROM users "
            "WHERE bale_user_id IS NOT NULL GROUP BY bale_user_id HAVING COUNT(*) > 1)",
        )
        # شماره‌هایی که نرمال‌سازی سرور را رد می‌کنند، در مهاجرت قابل تطبیق نیستند.
        bad_mobile = 0
        rows = conn.execute(
            "SELECT mobile FROM users WHERE mobile IS NOT NULL AND TRIM(mobile) <> ''"
        ).fetchall()
        for row in rows:
            if normalize_iran_phone(row[0]) is None:
                bad_mobile += 1

        profile_flags = {}
        if "users" in tables:
            user_cols = _columns(conn, "users")
            for flag in ("phone_verified", "is_blocked", "is_admin"):
                if flag in user_cols:
                    profile_flags[flag] = _scalar(
                        conn, f"SELECT COUNT(*) FROM users WHERE {flag} NOT IN (0, NULL)"
                    )

        certificates = audit_certificates(conn, tables)
        club = audit_club(conn, tables)

        return {
            "path": database.name,
            "size_bytes": database.stat().st_size,
            "certificates": certificates,
            "club": club,
            "tables": len(tables),
            "missing_required_tables": [t for t in _REQUIRED_TABLES if t not in tables],
            "counts": counts,
            "users": {
                "total": users_n,
                "without_mobile": no_mobile,
                "mobile_not_normalizable": bad_mobile,
                "duplicate_mobiles": dup_mobiles,
                "duplicate_bale_ids": dup_bale_ids,
                "flags": profile_flags,
            },
            "orphans_by_bale_user_id": orphans,
        }
    finally:
        conn.close()


# ───────────────────────── گواهی‌ها و باشگاه (فاز سوم) ─────────────────────────

# کنش‌هایی از user_actions که به امتیاز مربوط‌اند؛ علامت = جهت اثر روی total_points.
_POINT_ACTIONS: dict[str, int] = {
    "achievement": +1,
    "point_rule": +1,
    "birthday_greeting": +1,
    "points_refund": +1,
    "reward_redeem": -1,
    "points_spent": -1,
    "points_payment": -1,
}
# تغییرهایی که در کد قدیمی ربات امتیاز می‌دادند ولی هیچ ردیفی در user_actions نمی‌نوشتند
# (attendance._award_points، events بستن رویداد، lottery). فقط برای مستندسازی دورهٔ قبل از
# دفترکل؛ از فاز ششم همهٔ مسیرها در points_ledger ردیف دارند (بخش points_ledger همین گزارش).
_POINT_WRITERS_WITHOUT_LEDGER = ("attendance._award_points", "events.status_change", "lottery.prize")


def _has(conn: sqlite3.Connection, tables: set[str], table: str, *cols: str) -> bool:
    return table in tables and set(cols) <= _columns(conn, table)


def _group(conn: sqlite3.Connection, table: str, column: str, *, limit: int = 12) -> dict[str, int]:
    """شمارش بر حسب یک ستون وضعیت؛ مقدارها کوتاه و فقط حروف/عدد تا چیزی شخصی چاپ نشود."""
    if not _IDENT.fullmatch(table) or not _IDENT.fullmatch(column):
        raise AuditError("invalid_table_name")
    out: dict[str, int] = {}
    for row in conn.execute(
        f"SELECT COALESCE(CAST({column} AS TEXT), '') v, COUNT(*) n FROM {table} "
        f"GROUP BY v ORDER BY n DESC LIMIT {int(limit)}"
    ):
        key = str(row[0])[:24]
        key = key if re.fullmatch(r"[A-Za-z0-9_.-]*", key) else "other"
        out[key or "empty"] = out.get(key or "empty", 0) + int(row[1])
    return out


def audit_certificates(conn: sqlite3.Connection, tables: set[str]) -> dict[str, Any]:
    """ساختار و سلامت دادهٔ گواهی‌ها — فقط شمارش و کد وضعیت."""
    out: dict[str, Any] = {"present": "certificates" in tables}
    if "certificates" not in tables:
        return out
    cols = _columns(conn, "certificates")
    out["columns"] = sorted(cols)
    out["total"] = _count(conn, "certificates")
    has_bale = "bale_user_id" in cols
    out["owner_key"] = "bale_user_id" if has_bale else "none"
    if has_bale:
        out["with_bale_user_id"] = _scalar(
            conn, "SELECT COUNT(*) FROM certificates WHERE bale_user_id IS NOT NULL AND bale_user_id <> ''")
        out["without_bale_user_id"] = out["total"] - out["with_bale_user_id"]
        out["owner_in_users"] = _scalar(
            conn, "SELECT COUNT(*) FROM certificates c WHERE c.bale_user_id IS NOT NULL AND c.bale_user_id <> '' "
                  "AND EXISTS (SELECT 1 FROM users u WHERE u.bale_user_id = c.bale_user_id)")
        out["owner_missing_from_users"] = out["with_bale_user_id"] - out["owner_in_users"]
    if "revoked" in cols:
        out["revoked"] = _scalar(conn, "SELECT COUNT(*) FROM certificates WHERE COALESCE(revoked,0) <> 0")
        out["active"] = out["total"] - out["revoked"]
    if "source" in cols:
        out["by_source"] = _group(conn, "certificates", "source")
    if "serial" in cols:
        out["duplicate_serials"] = _scalar(
            conn, "SELECT COUNT(*) FROM (SELECT serial FROM certificates WHERE serial IS NOT NULL AND serial <> '' "
                  "GROUP BY serial HAVING COUNT(*) > 1)")
        out["without_serial"] = _scalar(conn, "SELECT COUNT(*) FROM certificates WHERE serial IS NULL OR serial = ''")
    if "full_code" in cols:
        out["with_full_code"] = _scalar(conn, "SELECT COUNT(*) FROM certificates WHERE full_code IS NOT NULL AND full_code <> ''")
        out["duplicate_full_codes"] = _scalar(
            conn, "SELECT COUNT(*) FROM (SELECT full_code FROM certificates WHERE full_code IS NOT NULL AND full_code <> '' "
                  "GROUP BY full_code HAVING COUNT(*) > 1)")
    if {"event_id", "bale_user_id", "event_cert_id"} <= cols:
        out["duplicate_event_user_slot"] = _scalar(
            conn, "SELECT COUNT(*) FROM (SELECT event_id, bale_user_id, COALESCE(event_cert_id,0) FROM certificates "
                  "WHERE bale_user_id IS NOT NULL GROUP BY 1,2,3 HAVING COUNT(*) > 1)")
    file_cols = [c for c in ("pdf_path", "png_path", "docx_path", "file_path") if c in cols]
    out["file_columns"] = file_cols
    if file_cols:
        any_file = " OR ".join(f"({c} IS NOT NULL AND {c} <> '')" for c in file_cols)
        out["with_file_path"] = _scalar(conn, f"SELECT COUNT(*) FROM certificates WHERE {any_file}")
        out["without_file_path"] = out["total"] - out["with_file_path"]
        unsafe = " OR ".join(f"({c} LIKE '%..%' OR {c} LIKE '/%' OR {c} LIKE '%:\\%')" for c in file_cols)
        out["file_paths_outside_relative_root"] = _scalar(conn, f"SELECT COUNT(*) FROM certificates WHERE {unsafe}")
    if "expires_on" in cols:
        out["with_expiry"] = _scalar(conn, "SELECT COUNT(*) FROM certificates WHERE expires_on IS NOT NULL AND expires_on <> ''")
    if "event_id" in cols and "events" in tables:
        out["event_missing"] = _scalar(
            conn, "SELECT COUNT(*) FROM certificates c WHERE c.event_id IS NOT NULL AND c.event_id <> 0 "
                  "AND NOT EXISTS (SELECT 1 FROM events e WHERE e.id = c.event_id)")
    if "verify_count" in cols:
        out["verified_at_least_once"] = _scalar(conn, "SELECT COUNT(*) FROM certificates WHERE COALESCE(verify_count,0) > 0")

    # طرح‌ها و سهم‌ها (مرکز صدور): سهم = رزرو، نه گواهی صادرشده
    if _has(conn, tables, "cert_issues", "status"):
        out["issues_by_status"] = _group(conn, "cert_issues", "status")
    if "cert_shares" in tables:
        scols = _columns(conn, "cert_shares")
        shares: dict[str, Any] = {"total": _count(conn, "cert_shares")}
        if "state" in scols:
            shares["by_state"] = _group(conn, "cert_shares", "state")
        if "bale_user_id" in scols:
            shares["without_bale_user_id"] = _scalar(
                conn, "SELECT COUNT(*) FROM cert_shares WHERE bale_user_id IS NULL OR bale_user_id = ''")
        if "cert_id" in scols:
            shares["built_with_missing_certificate"] = _scalar(
                conn, "SELECT COUNT(*) FROM cert_shares s WHERE s.cert_id IS NOT NULL "
                      "AND NOT EXISTS (SELECT 1 FROM certificates c WHERE c.id = s.cert_id)")
        out["shares"] = shares
    if "cert_batches" in tables:
        bcols = _columns(conn, "cert_batches")
        batches: dict[str, Any] = {"total": _count(conn, "cert_batches")}
        if "is_active" in bcols:
            batches["active"] = _scalar(conn, "SELECT COUNT(*) FROM cert_batches WHERE COALESCE(is_active,0) <> 0")
        if "match_by" in bcols:
            batches["by_match_key"] = _group(conn, "cert_batches", "match_by")
        out["batches"] = batches
    if "cert_batch_rows" in tables:
        rcols = _columns(conn, "cert_batch_rows")
        rows: dict[str, Any] = {"total": _count(conn, "cert_batch_rows")}
        if "status" in rcols:
            rows["by_status"] = _group(conn, "cert_batch_rows", "status")
        if "claimed_by" in rcols:
            rows["unclaimed_without_bale_user_id"] = _scalar(
                conn, "SELECT COUNT(*) FROM cert_batch_rows WHERE claimed_by IS NULL OR claimed_by = ''")
        if "cert_id" in rcols:
            rows["claimed_with_missing_certificate"] = _scalar(
                conn, "SELECT COUNT(*) FROM cert_batch_rows r WHERE r.cert_id IS NOT NULL "
                      "AND NOT EXISTS (SELECT 1 FROM certificates c WHERE c.id = r.cert_id)")
        out["batch_rows"] = rows
    for table, key in (("event_certs", "event_cert_definitions"), ("cert_templates", "templates"),
                       ("cert_verifies", "verification_log")):
        if table in tables:
            entry: dict[str, Any] = {"total": _count(conn, table)}
            if "is_active" in _columns(conn, table):
                entry["active"] = _scalar(conn, f"SELECT COUNT(*) FROM {table} WHERE COALESCE(is_active,0) <> 0")
            out[key] = entry
    return out


def _audit_points_ledger(conn: sqlite3.Connection, tables: set[str], ucols: set[str]) -> dict[str, Any]:
    """دفترکل امتیاز فاز ششم (points_ledger): فقط گزارش، بدون هیچ اصلاحی.

    * اختلاف شمارندهٔ users.total_points با آخرین balance_after هر کاربر
    * کاربران غیرصفر بدون ردیف افتتاحیه، موجودی‌های منفی
    * ردیف‌های تکراری/نامعتبر (کلید تکراری، زنجیرهٔ موجودی شکسته، بدون مرجع تجاری)
    * وضعیت همگام‌سازی با سرور (pending/mirrored/unmapped/failed)
    * کاربرانی که شناسهٔ بلهٔ قابل‌پیوندی ندارند
    """
    if "points_ledger" not in tables:
        return {"installed": False,
                "note": "جدول points_ledger وجود ندارد؛ این نسخهٔ پایگاه پیش از راه‌اندازی دفترکل است."}
    lcols = _columns(conn, "points_ledger")
    need = {"bale_user_id", "delta", "balance_after", "entry_type", "source", "ref_key"}
    if not need <= lcols:
        return {"installed": True, "status": "unexpected_schema"}
    out: dict[str, Any] = {"installed": True, "entries": _count(conn, "points_ledger")}
    out["by_entry_type"] = _group(conn, "points_ledger", "entry_type")
    out["opening_rows"] = _scalar(conn, "SELECT COUNT(*) FROM points_ledger WHERE entry_type='opening_balance'")
    out["duplicate_keys"] = _scalar(
        conn, "SELECT COUNT(*) FROM (SELECT source, ref_key FROM points_ledger GROUP BY source, ref_key HAVING COUNT(*) > 1)")
    out["missing_business_ref"] = _scalar(
        conn, "SELECT COUNT(*) FROM points_ledger WHERE entry_type IN ('award','spend','refund') "
              "AND (ref_key IS NULL OR ref_key = '' OR ref_table IS NULL)" if "ref_table" in lcols else
              "SELECT COUNT(*) FROM points_ledger WHERE entry_type IN ('award','spend','refund') "
              "AND (ref_key IS NULL OR ref_key = '')")
    out["orphan_entries"] = _scalar(
        conn, "SELECT COUNT(*) FROM points_ledger l WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.bale_user_id = l.bale_user_id)")
    # زنجیرهٔ موجودی: balance_after هر ردیف = balance_after ردیف قبلی همان کاربر + delta
    chain_breaks = 0
    last: dict[int, int] = {}
    for uid, delta, after in conn.execute(
            "SELECT bale_user_id, delta, balance_after FROM points_ledger ORDER BY bale_user_id, id"):
        prev = last.get(int(uid), 0)
        if prev + int(delta) != int(after):
            chain_breaks += 1
        last[int(uid)] = int(after)
    out["chain_breaks"] = chain_breaks
    if "total_points" in ucols:
        mismatched = without_opening = negative = unlinkable = 0
        for raw, tp in conn.execute("SELECT bale_user_id, COALESCE(total_points,0) FROM users"):
            tp = int(tp)
            if raw is None or not re.fullmatch(r"[1-9][0-9]{0,19}", str(raw)):
                if tp != 0:
                    unlinkable += 1
                continue
            uid = int(raw)
            if tp < 0:
                negative += 1
            if uid in last:
                if last[uid] != tp:
                    mismatched += 1
            elif tp != 0:
                without_opening += 1
        out["counter_vs_ledger_mismatched_users"] = mismatched
        out["users_nonzero_without_opening"] = without_opening
        out["negative_balances"] = negative
        out["users_with_points_but_unlinkable_bale_id"] = unlinkable
        out["reconciled"] = mismatched == 0 and without_opening == 0 and chain_breaks == 0 and out["duplicate_keys"] == 0
    if "shared_status" in lcols:
        out["sync"] = _group(conn, "points_ledger", "shared_status")
    if "points_ledger_meta" in tables:
        meta = {str(k): str(v) for k, v in conn.execute(
            "SELECT key, value FROM points_ledger_meta WHERE key IN "
            "('opening_applied_at','guard_disabled_at','guard_enabled_at','opening_backup')")}
        out["meta"] = meta
    trig = {str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    out["guard_installed"] = {"trg_users_points_guard_update", "trg_users_points_guard_insert"} <= trig
    out["immutability_installed"] = {"trg_points_ledger_no_update", "trg_points_ledger_no_delete"} <= trig
    return out


def audit_club(conn: sqlite3.Connection, tables: set[str]) -> dict[str, Any]:
    """امتیاز و باشگاه: شمارنده روی users، دستاوردها، پاداش‌ها و کامل‌بودن دفترکل."""
    out: dict[str, Any] = {}
    ucols = _columns(conn, "users") if "users" in tables else set()
    points: dict[str, Any] = {"storage": "users.total_points" if "total_points" in ucols else "none"}
    if "total_points" in ucols:
        points["users_with_points"] = _scalar(conn, "SELECT COUNT(*) FROM users WHERE COALESCE(total_points,0) > 0")
        points["users_with_negative_points"] = _scalar(conn, "SELECT COUNT(*) FROM users WHERE COALESCE(total_points,0) < 0")
        points["sum_recorded"] = _scalar(conn, "SELECT COALESCE(SUM(total_points),0) FROM users")
        points["max_recorded"] = _scalar(conn, "SELECT COALESCE(MAX(total_points),0) FROM users")
    if "is_vip" in ucols:
        points["vip_users"] = _scalar(conn, "SELECT COUNT(*) FROM users WHERE COALESCE(is_vip,0) <> 0")
    # دفترکل: user_actions فقط بخشی از تغییرها را دارد و پس از ۹۰ روز پاک می‌شود.
    ledger: dict[str, Any] = {"table": "user_actions", "retention_days_in_code": 90,
                              "writers_without_ledger_row": list(_POINT_WRITERS_WITHOUT_LEDGER)}
    if _has(conn, tables, "user_actions", "action_type", "action_data"):
        by_type: dict[str, int] = {}
        net = 0
        parsed = 0
        for row in conn.execute(
            "SELECT action_type, action_data FROM user_actions WHERE action_type IN (%s)"
            % ",".join("?" * len(_POINT_ACTIONS)), tuple(_POINT_ACTIONS)):
            kind = str(row[0])
            by_type[kind] = by_type.get(kind, 0) + 1
            try:
                data = json.loads(row[1] or "{}")
                value = int(data.get("points") or 0)
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
            parsed += 1
            net += _POINT_ACTIONS[kind] * value
        ledger["rows_by_type"] = by_type
        ledger["rows_parsed"] = parsed
        ledger["net_points_in_ledger"] = net
        if "total_points" in ucols:
            ledger["counter_minus_ledger"] = int(points["sum_recorded"]) - net
            ledger["reconstructible"] = ledger["counter_minus_ledger"] == 0
    else:
        ledger["status"] = "user_actions_missing"
    out["points"] = points
    out["ledger"] = ledger
    out["points_ledger"] = _audit_points_ledger(conn, tables, ucols)
    if "achievements" in tables:
        ach: dict[str, Any] = {"definitions": _count(conn, "achievements")}
        if "is_active" in _columns(conn, "achievements"):
            ach["active_definitions"] = _scalar(conn, "SELECT COUNT(*) FROM achievements WHERE COALESCE(is_active,0) <> 0")
        if _has(conn, tables, "user_achievements", "bale_user_id", "achievement_key"):
            ach["earned_rows"] = _count(conn, "user_achievements")
            ach["earned_distinct_users"] = _scalar(conn, "SELECT COUNT(DISTINCT bale_user_id) FROM user_achievements")
            ach["earned_orphans"] = _scalar(
                conn, "SELECT COUNT(*) FROM user_achievements a WHERE NOT EXISTS "
                      "(SELECT 1 FROM users u WHERE u.bale_user_id = a.bale_user_id)")
            ach["earned_unknown_key"] = _scalar(
                conn, "SELECT COUNT(*) FROM user_achievements a WHERE NOT EXISTS "
                      "(SELECT 1 FROM achievements d WHERE d.key = a.achievement_key)")
        out["achievements"] = ach
    if "rewards" in tables:
        rw: dict[str, Any] = {"definitions": _count(conn, "rewards")}
        if _has(conn, tables, "reward_redemptions", "status", "bale_user_id"):
            rw["redemptions"] = _count(conn, "reward_redemptions")
            rw["redemptions_by_status"] = _group(conn, "reward_redemptions", "status")
            rw["redemption_orphans"] = _scalar(
                conn, "SELECT COUNT(*) FROM reward_redemptions r WHERE NOT EXISTS "
                      "(SELECT 1 FROM users u WHERE u.bale_user_id = r.bale_user_id)")
        out["rewards"] = rw
    if "point_rules" in tables:
        pr: dict[str, Any] = {"definitions": _count(conn, "point_rules")}
        pcols = _columns(conn, "point_rules")
        if "is_active" in pcols:
            pr["active"] = _scalar(conn, "SELECT COUNT(*) FROM point_rules WHERE COALESCE(is_active,0) <> 0")
        if "total_awarded" in pcols:
            pr["sum_total_awarded"] = _scalar(conn, "SELECT COALESCE(SUM(total_awarded),0) FROM point_rules")
        out["point_rules"] = pr
    out["membership_level"] = {
        "status": "not_a_data_field",
        "note": "tier فقط صفت تعریف دستاورد است؛ سطح عضویت ذخیره‌شده‌ای برای کاربر وجود ندارد (فقط is_vip).",
    }
    return out


def collect_legacy_cert_bale_ids(database: Path) -> list[str]:
    conn = _open_readonly(database)
    try:
        tables = _tables(conn)
        if not _has(conn, tables, "certificates", "bale_user_id"):
            return []
        return [str(r[0]) for r in conn.execute(
            "SELECT bale_user_id FROM certificates WHERE bale_user_id IS NOT NULL AND bale_user_id <> ''"
        )]
    finally:
        conn.close()


# ───────────────────────────── بخش سرور (اختیاری) ─────────────────────

def audit_server(database_url: str) -> dict[str, Any]:
    """فقط SELECT؛ برای همین باید به یک «کپی» از پایگاه سرور اشاره کند."""
    try:
        from sqlalchemy import create_engine, func, select
        from sqlalchemy.orm import Session
    except Exception as exc:  # pragma: no cover - محیط بدون sqlalchemy
        raise AuditError("sqlalchemy_unavailable") from exc

    try:
        from backend.models import (  # type: ignore[import-not-found]
            AccountRecord,
            PlatformIdentityRecord,
        )
    except ImportError:
        # ابزار در درخت ربات است و مدل‌های سرور در درخت وب‌اپ؛ هر دو سمت
        # همین تحویل‌اند. مسیر را فقط برای خواندن مدل اضافه می‌کنیم.
        candidates = [
            Path(__file__).resolve().parents[2] / "website" / "nora-ui",
            Path.cwd(),
        ]
        for candidate in candidates:
            if (candidate / "backend" / "models.py").is_file():
                sys.path.insert(0, str(candidate))
                break
        try:
            from backend.models import (  # type: ignore[import-not-found]
                AccountRecord,
                PlatformIdentityRecord,
            )
        except ImportError as exc:
            raise AuditError("backend_models_unavailable") from exc

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            phone_n = int(db.scalar(
                select(func.count()).select_from(PlatformIdentityRecord).where(
                    PlatformIdentityRecord.provider == "phone"
                )
            ) or 0)
            bale_n = int(db.scalar(
                select(func.count()).select_from(PlatformIdentityRecord).where(
                    PlatformIdentityRecord.provider == "bale"
                )
            ) or 0)
            accounts = int(db.scalar(select(func.count()).select_from(AccountRecord)) or 0)
            # حساب‌هایی که هر دو هویت را دارند.
            both = int(db.scalar(
                select(func.count()).select_from(
                    select(PlatformIdentityRecord.account_id)
                    .group_by(PlatformIdentityRecord.account_id)
                    .having(func.count(PlatformIdentityRecord.provider) >= 2)
                    .subquery()
                )
            ) or 0)
            bale_ids = [
                str(row) for row in db.scalars(
                    select(PlatformIdentityRecord.provider_user_id).where(
                        PlatformIdentityRecord.provider == "bale"
                    )
                ).all()
            ]
            phone_subjects = [
                str(row) for row in db.scalars(
                    select(PlatformIdentityRecord.provider_user_id).where(
                        PlatformIdentityRecord.provider == "phone"
                    )
                ).all()
            ]
        return {
            "accounts": accounts,
            "identities": {"phone": phone_n, "bale": bale_n},
            "accounts_with_both_identities": both,
            "accounts_phone_only": accounts - both,
            "accounts_bale_only": accounts - both,
            "bale_subject_ids": bale_ids,
            "phone_subjects": phone_subjects,
        }
    finally:
        engine.dispose()


def correlate(legacy: dict[str, Any], server: dict[str, Any], *,
              legacy_mobiles: Iterable[str], pepper: str) -> dict[str, Any]:
    """هم‌بستگی فقط-خواندنی بین هویت بله و هویت شماره‌ای در دو پایگاه."""
    server_bale = set(server.get("bale_subject_ids") or ())
    server_phone = set(server.get("phone_subjects") or ())
    legacy_bale_ids = {str(v) for v in legacy.get("bale_ids") or ()}

    present = legacy_bale_ids & server_bale
    absent = legacy_bale_ids - server_bale

    matched_users = 0
    matched_subjects: set[str] = set()
    for mobile in legacy_mobiles:
        normalized = normalize_iran_phone(mobile)
        if normalized is None:
            continue
        digest = phone_digest(pepper, normalized)
        if digest in server_phone:
            matched_users += 1
            matched_subjects.add(digest)

    cert_ids = [str(v) for v in legacy.get("certificate_bale_ids") or ()]
    cert_mapped = sum(1 for v in cert_ids if v in server_bale)

    return {
        "certificate_rows_with_server_bale_identity": cert_mapped,
        "certificate_rows_without_server_identity": len(cert_ids) - cert_mapped,
        "legacy_bale_ids_present_in_server": len(present),
        "legacy_bale_ids_absent_from_server": len(absent),
        "legacy_phones_matching_a_server_phone_identity": matched_users,
        "distinct_server_phone_identities_matched": len(matched_subjects),
        # اگر چند کاربر محلی به یک هویت شماره‌ای سرور برسند، یک تعارض واقعی است.
        "collisions_on_same_phone_identity": matched_users - len(matched_subjects),
    }


# ───────────────────────────── خروجی ─────────────────────────────

_BLOCKER_TEXT = {
    "missing_required_tables": "جدول‌های لازم برای مهاجرت کامل نیستند",
    "orphan_rows": "ردیف‌هایی هست که به کاربر موجود وصل نیستند",
    "duplicate_mobile": "شمارهٔ موبایل تکراری بین کاربران وجود دارد",
    "invalid_mobile": "شماره‌هایی هست که با قاعدهٔ سرور نرمال نمی‌شوند",
    "duplicate_bale_identity": "یک شناسهٔ بله به چند کاربر محلی وصل است",
    "certificate_owner_missing": "گواهی‌هایی هست که شناسهٔ بلهٔ آن‌ها در users نیست",
    "certificate_without_owner_key": "گواهی‌هایی بدون شناسهٔ بله هست؛ مالک قابل‌اثبات ندارند",
    "certificate_duplicate_serial": "سریال گواهی تکراری وجود دارد",
}


def build_blockers(report: dict[str, Any]) -> list[dict[str, Any]]:
    legacy = report["legacy"]
    blockers: list[dict[str, Any]] = []
    if legacy["missing_required_tables"]:
        blockers.append({"code": "missing_required_tables",
                         "count": len(legacy["missing_required_tables"]),
                         "text": _BLOCKER_TEXT["missing_required_tables"]})
    orphan_total = sum(legacy["orphans_by_bale_user_id"].values())
    if orphan_total:
        blockers.append({"code": "orphan_rows", "count": orphan_total,
                         "text": _BLOCKER_TEXT["orphan_rows"]})
    if legacy["users"]["duplicate_mobiles"]:
        blockers.append({"code": "duplicate_mobile",
                         "count": legacy["users"]["duplicate_mobiles"],
                         "text": _BLOCKER_TEXT["duplicate_mobile"]})
    if legacy["users"]["mobile_not_normalizable"]:
        blockers.append({"code": "invalid_mobile",
                         "count": legacy["users"]["mobile_not_normalizable"],
                         "text": _BLOCKER_TEXT["invalid_mobile"]})
    certs = legacy.get("certificates") or {}
    if certs.get("owner_missing_from_users"):
        blockers.append({"code": "certificate_owner_missing",
                         "count": certs["owner_missing_from_users"],
                         "text": _BLOCKER_TEXT["certificate_owner_missing"]})
    if certs.get("without_bale_user_id"):
        blockers.append({"code": "certificate_without_owner_key",
                         "count": certs["without_bale_user_id"],
                         "text": _BLOCKER_TEXT["certificate_without_owner_key"]})
    if certs.get("duplicate_serials"):
        blockers.append({"code": "certificate_duplicate_serial",
                         "count": certs["duplicate_serials"],
                         "text": _BLOCKER_TEXT["certificate_duplicate_serial"]})
    if legacy["users"]["duplicate_bale_ids"]:
        blockers.append({"code": "duplicate_bale_identity",
                         "count": legacy["users"]["duplicate_bale_ids"],
                         "text": _BLOCKER_TEXT["duplicate_bale_identity"]})
    return blockers


def collect_legacy_bale_ids(database: Path) -> list[str]:
    conn = _open_readonly(database)
    try:
        if "users" not in _tables(conn):
            return []
        return [str(r[0]) for r in conn.execute(
            "SELECT bale_user_id FROM users WHERE bale_user_id IS NOT NULL"
        )]
    finally:
        conn.close()


def collect_legacy_mobiles(database: Path) -> list[str]:
    conn = _open_readonly(database)
    try:
        if "users" not in _tables(conn):
            return []
        return [str(r[0]) for r in conn.execute(
            "SELECT mobile FROM users WHERE mobile IS NOT NULL AND TRIM(mobile) <> ''"
        )]
    finally:
        conn.close()


def run_audit(database: Path, *, server_database_url: str | None = None,
              pepper: str | None = None,
              include_identifiers: bool = False) -> dict[str, Any]:
    legacy = audit_legacy(database)
    report: dict[str, Any] = {
        "tool": "legacy_data_audit",
        "version": REPORT_VERSION,
        "mode": "dry-run",
        "legacy": legacy,
        "server": None,
        "correlation": None,
    }
    if include_identifiers:
        legacy["bale_ids"] = collect_legacy_bale_ids(database)
        legacy["certificate_bale_ids"] = collect_legacy_cert_bale_ids(database)
    if server_database_url:
        server = audit_server(server_database_url)
        if not include_identifiers:
            server.pop("bale_subject_ids", None)
            server.pop("phone_subjects", None)
        report["server"] = server
        if pepper:
            report["correlation"] = correlate(
                legacy, server,
                legacy_mobiles=collect_legacy_mobiles(database),
                pepper=pepper,
            )
        else:
            report["correlation"] = {"status": "skipped_missing_pepper"}
    report["blockers"] = build_blockers(report)
    report["ready"] = not report["blockers"]
    return report


def _print_human(report: dict[str, Any]) -> None:
    legacy = report["legacy"]
    print("ممیزی دادهٔ legacy نورا (فقط خواندنی)")
    print("=" * 58)
    print(f"فایل: {legacy['path']}  ({legacy['size_bytes']:,} بایت)")
    print(f"جدول‌ها: {legacy['tables']}")
    if legacy["missing_required_tables"]:
        print(f"⚠️ جدول‌های لازمِ غایب: {', '.join(legacy['missing_required_tables'])}")
    print()
    print("شمارش به تفکیک دامنه:")
    for domain, items in legacy["counts"].items():
        if not items:
            continue
        total = sum(items.values())
        print(f"  {domain:14s} {total:>9,}")
    print()
    users = legacy["users"]
    print("کاربران:")
    print(f"  کل: {users['total']:,}")
    print(f"  بدون موبایل: {users['without_mobile']:,}")
    print(f"  موبایل غیرقابل‌نرمال‌سازی: {users['mobile_not_normalizable']:,}")
    print(f"  موبایل تکراری: {users['duplicate_mobiles']:,}")
    print(f"  شناسهٔ بله تکراری: {users['duplicate_bale_ids']:,}")
    if legacy["orphans_by_bale_user_id"]:
        orphans = ", ".join(f"{k}={v:,}" for k, v in legacy["orphans_by_bale_user_id"].items() if v)
        if orphans:
            print(f"  ردیف‌های بی‌صاحب: {orphans}")
    certs = legacy.get("certificates") or {}
    if certs.get("present"):
        print()
        print("گواهی‌ها:")
        print(f"  کل: {certs.get('total', 0):,} | فعال: {certs.get('active', 0):,} | باطل: {certs.get('revoked', 0):,}")
        print(f"  با شناسهٔ بله: {certs.get('with_bale_user_id', 0):,} | بدون شناسه: {certs.get('without_bale_user_id', 0):,}"
              f" | مالک غایب از users: {certs.get('owner_missing_from_users', 0):,}")
        print(f"  سریال تکراری: {certs.get('duplicate_serials', 0):,} | با فایل: {certs.get('with_file_path', 0):,}"
              f" | بی‌فایل: {certs.get('without_file_path', 0):,}")
        if certs.get("shares"):
            print(f"  سهم‌های مرکز صدور (رزرو، نه صادرشده): {certs['shares'].get('total', 0):,}")
        if certs.get("batch_rows"):
            print(f"  ردیف‌های دستهٔ اکسل: {certs['batch_rows'].get('total', 0):,}")
    club = legacy.get("club") or {}
    if club:
        pts = club.get("points") or {}
        ledger = club.get("ledger") or {}
        print()
        print("باشگاه:")
        print(f"  کاربران دارای امتیاز: {pts.get('users_with_points', 0):,} | جمع شمارنده: {pts.get('sum_recorded', 0):,}"
              f" | VIP: {pts.get('vip_users', 0):,}")
        if "reconstructible" in ledger:
            print(f"  دفترکل امتیاز: {'کامل' if ledger['reconstructible'] else 'ناقص'} "
                  f"(شمارنده − دفترکل = {ledger.get('counter_minus_ledger', 0):,})")
    if report.get("server"):
        srv = report["server"]
        print()
        print("پایگاه مشترک:")
        print(f"  حساب‌ها: {srv['accounts']:,} | هویت شماره: {srv['identities']['phone']:,} "
              f"| هویت بله: {srv['identities']['bale']:,}")
        print(f"  هر دو هویت: {srv['accounts_with_both_identities']:,}")
    if report.get("correlation") and "status" not in report["correlation"]:
        corr = report["correlation"]
        print()
        print("هم‌بستگی legacy ↔ سرور:")
        print(f"  شناسهٔ بله موجود در سرور: {corr['legacy_bale_ids_present_in_server']:,}")
        print(f"  شناسهٔ بله غایب از سرور: {corr['legacy_bale_ids_absent_from_server']:,}")
        print(f"  شماره‌های منطبق با هویت سرور: "
              f"{corr['legacy_phones_matching_a_server_phone_identity']:,}")
        print(f"  گواهی‌های با هویت بلهٔ موجود در سرور: {corr['certificate_rows_with_server_bale_identity']:,}"
              f" | بدون هویت سرور: {corr['certificate_rows_without_server_identity']:,}")
    print()
    if report["blockers"]:
        print("موانع:")
        for item in report["blockers"]:
            print(f"  • [{item['code']}] {item['count']:,} — {item['text']}")
    else:
        print("موانع: هیچ مانع ساختاری پیدا نشد.")
    print()
    print("هیچ داده‌ای نوشته یا تغییر داده نشد.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="ممیزی فقط-خواندنی دادهٔ legacy نورا (بدون تغییر داده)"
    )
    parser.add_argument("--database", required=True, help="مسیر فایل SQLite قدیمی")
    parser.add_argument("--server-database-url", default=None,
                        help="نشانی پایگاه سرور؛ بهتر است کپی باشد (فقط SELECT)")
    parser.add_argument("--pepper-env", default="NORA_OTP_PEPPER",
                        help="نام متغیر محیطی فلفل OTP برای هم‌بستگی شماره")
    parser.add_argument("--json", action="store_true", help="خروجی JSON")
    parser.add_argument("--with-identifiers", action="store_true",
                        help="شناسهٔ بله را در خروجی بیاور (برای ابزار بعدی)")
    args = parser.parse_args(argv)

    import os

    pepper = os.getenv(args.pepper_env) or None
    try:
        report = run_audit(
            Path(args.database),
            server_database_url=args.server_database_url,
            pepper=pepper,
            include_identifiers=args.with_identifiers,
        )
    except AuditError as exc:
        print(f"❌ ممیزی انجام نشد: {exc}")
        return 2
    except Exception:
        # هیچ پیام خام (ممکن است مسیر یا داده داشته باشد) چاپ نمی‌شود.
        print("❌ ممیزی انجام نشد: unexpected_error")
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        _print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
