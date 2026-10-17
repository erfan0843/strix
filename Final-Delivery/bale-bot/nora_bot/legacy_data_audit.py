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

REPORT_VERSION = 1

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

        return {
            "path": database.name,
            "size_bytes": database.stat().st_size,
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

    return {
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
