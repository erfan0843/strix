"""آزمون ابزار ممیزی دادهٔ legacy — فقط خواندن، بدون تغییر داده.

این آزمون‌ها سه چیز را می‌سنجند:
  ۱) ابزار روی دادهٔ واقعی‌نما، شمارش و ناسازگاری‌ها را درست پیدا می‌کند؛
  ۲) هیچ نوشتنی رخ نمی‌دهد (چک‌سام فایل و متن ابزار)؛
  ۳) خروجی هیچ شماره، نام یا مسیری را لو نمی‌دهد.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from nora_bot import legacy_data_audit as audit  # noqa: E402

PEPPER = "test-pepper-0123456789abcdefghijklmnop"


def build_legacy(path: Path) -> None:
    """پایگاه legacy کوچک اما واقعی‌نما با یک درس‌نامهٔ کامل از خطاها."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            bale_user_id INTEGER,
            first_name TEXT, last_name TEXT,
            mobile TEXT, phone TEXT,
            phone_verified INTEGER DEFAULT 0,
            is_blocked INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0
        );
        CREATE TABLE events (id INTEGER PRIMARY KEY, title TEXT);
        CREATE TABLE forms (id INTEGER PRIMARY KEY, title TEXT, event_id INTEGER);
        CREATE TABLE form_responses (
            id INTEGER PRIMARY KEY, form_id INTEGER, bale_user_id INTEGER, qr_code TEXT
        );
        CREATE TABLE event_registrations (
            id INTEGER PRIMARY KEY, event_id INTEGER, bale_user_id INTEGER, status TEXT
        );
        CREATE TABLE certificates (
            id INTEGER PRIMARY KEY, event_id INTEGER, bale_user_id INTEGER, serial TEXT
        );
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY, bale_user_id INTEGER, amount INTEGER, status TEXT
        );
        CREATE TABLE payment_receipts (
            id INTEGER PRIMARY KEY, bale_user_id INTEGER, amount INTEGER,
            photo_path TEXT, status TEXT
        );
        CREATE TABLE attendance_records (
            id INTEGER PRIMARY KEY, session_id INTEGER, bale_user_id INTEGER, status TEXT
        );
        CREATE TABLE user_extra (
            id INTEGER PRIMARY KEY, bale_user_id INTEGER, field_key TEXT, value TEXT
        );
        """
    )
    users = [
        (1, 101, "زهرا", "الف", "09120000001", None, 1, 0, 0),
        (2, 102, "علی", "ب", "+989120000002", None, 1, 0, 0),
        (3, 103, "سارا", "ج", "۰۹۱۲۰۰۰۰۰۰۱", None, 0, 0, 0),   # موبایل تکراری
        (4, 104, "بدون", "موبایل", "", None, 0, 0, 0),
        (5, 105, "شمارهٔ", "خراب", "12345", None, 0, 0, 0),      # غیرقابل نرمال‌سازی
        (6, 101, "تکراری", "بله", "09120000009", None, 0, 1, 0),  # bale_user_id تکراری
    ]
    conn.executemany("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?)", users)
    conn.execute("INSERT INTO events VALUES (1,'رویداد یک')")
    conn.executemany(
        "INSERT INTO forms VALUES (?,?,?)",
        [(1, "فرم ثبت‌نام", 1), (2, "فرم نظرسنجی", None)],
    )
    # دو ردیف با کاربر موجود، دو ردیف بی‌صاحب (bale_user_id=999).
    conn.executemany(
        "INSERT INTO form_responses VALUES (?,?,?,?)",
        [(1, 1, 101, "q1"), (2, 1, 102, "q2"), (3, 1, 999, "q3"), (4, 2, 999, "q4")],
    )
    conn.executemany(
        "INSERT INTO event_registrations VALUES (?,?,?,?)",
        [(1, 1, 101, "confirmed"), (2, 1, 777, "waiting")],
    )
    conn.executemany(
        "INSERT INTO certificates VALUES (?,?,?,?)",
        [(1, 1, 101, "N-0001"), (2, 1, 888, "N-0002")],
    )
    conn.execute("INSERT INTO transactions VALUES (1,101,500000,'paid')")
    conn.executemany(
        "INSERT INTO payment_receipts VALUES (?,?,?,?,?)",
        [(1, 101, 500000, "files/r1.jpg", "pending"),
         (2, 999, 250000, "files/r2.jpg", "pending")],
    )
    conn.execute("INSERT INTO attendance_records VALUES (1,1,101,'present')")
    conn.execute("INSERT INTO user_extra VALUES (1,101,'bio','متن')")
    conn.commit()
    conn.close()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LegacyAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory(prefix="nora-audit-")
        self.tmp = Path(self._tmp.name)
        self.db = self.tmp / "legacy.db"
        build_legacy(self.db)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # ── شمارش و ناسازگاری ──────────────────────────────────────────────
    def test_counts_and_domains_are_reported(self):
        report = audit.run_audit(self.db)
        self.assertEqual(report["mode"], "dry-run")
        self.assertEqual(report["legacy"]["users"]["total"], 6)
        self.assertEqual(report["legacy"]["counts"]["forms"]["form_responses"], 4)
        self.assertEqual(report["legacy"]["counts"]["events"]["event_registrations"], 2)
        self.assertEqual(report["legacy"]["counts"]["certificates"]["certificates"], 2)
        self.assertEqual(report["legacy"]["counts"]["payments"]["payment_receipts"], 2)

    def test_orphans_are_detected_per_table(self):
        report = audit.run_audit(self.db)
        orphans = report["legacy"]["orphans_by_bale_user_id"]
        self.assertEqual(orphans["form_responses"], 2)
        self.assertEqual(orphans["event_registrations"], 1)
        self.assertEqual(orphans["certificates"], 1)
        self.assertEqual(orphans["payment_receipts"], 1)
        self.assertEqual(orphans["transactions"], 0)
        self.assertEqual(orphans["attendance_records"], 0)
        self.assertIn("orphan_rows", [b["code"] for b in report["blockers"]])

    def test_duplicate_and_invalid_mobiles_are_counted(self):
        report = audit.run_audit(self.db)
        users = report["legacy"]["users"]
        # 09120000001 و ۰۹۱۲۰۰۰۰۰۰۱ یک شماره‌اند؛ تکرار پس از نرمال‌سازی
        # شمرده می‌شود تا تعارضِ پنهان در شکل‌های مختلف رقم از دست نرود.
        self.assertEqual(users["duplicate_mobiles"], 1)
        # "12345" نرمال نمی‌شود؛ رشتهٔ خالی جداگانه در without_mobile شمرده شد.
        self.assertEqual(users["mobile_not_normalizable"], 1)
        self.assertEqual(users["without_mobile"], 1)
        self.assertEqual(users["duplicate_bale_ids"], 1)
        codes = {b["code"] for b in report["blockers"]}
        self.assertIn("duplicate_mobile", codes)
        self.assertIn("invalid_mobile", codes)
        self.assertIn("duplicate_bale_identity", codes)

    def test_missing_required_table_is_reported(self):
        conn = sqlite3.connect(self.db)
        conn.execute("DROP TABLE certificates")
        conn.commit()
        conn.close()
        report = audit.run_audit(self.db)
        self.assertIn("certificates", report["legacy"]["missing_required_tables"])
        self.assertFalse(report["ready"])

    # ── فقط خواندن ─────────────────────────────────────────────────────
    def test_audit_never_modifies_the_database(self):
        before = file_digest(self.db)
        before_mtime = self.db.stat().st_mtime_ns
        audit.run_audit(self.db)
        audit.run_audit(self.db, include_identifiers=True)
        self.assertEqual(file_digest(self.db), before)
        self.assertEqual(self.db.stat().st_mtime_ns, before_mtime)

    def test_tool_source_contains_no_write_sql(self):
        source = Path(audit.__file__).read_text(encoding="utf-8").upper()
        for keyword in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ",
                        "CREATE TABLE", "ATTACH ", "REPLACE INTO"):
            self.assertNotIn(keyword, source, f"ابزار نباید «{keyword.strip()}» داشته باشد")

    def test_readonly_connection_rejects_writes(self):
        conn = audit._open_readonly(self.db)
        try:
            with self.assertRaises(sqlite3.Error):
                conn.execute("DELETE FROM users")
        finally:
            conn.close()
        self.assertEqual(audit.run_audit(self.db)["legacy"]["users"]["total"], 6)

    # ── حریم خصوصی خروجی ──────────────────────────────────────────────
    def test_report_contains_no_phone_or_names(self):
        report = audit.run_audit(self.db, include_identifiers=True)
        blob = json.dumps(report, ensure_ascii=False)
        for secret in ("0912000000", "98912", "زهرا", "سارا", "12345", "files/r1.jpg"):
            self.assertNotIn(secret, blob)
        # شناسهٔ بله فقط با درخواست صریح می‌آید و آن هم عدد است، نه دادهٔ شخصی.
        self.assertIn("101", report["legacy"]["bale_ids"])

    # ── هم‌بستگی با پایگاه سرور ────────────────────────────────────────
    def test_phone_digest_matches_backend_rule(self):
        try:
            sys.path.insert(0, str(ROOT.parent / "website" / "nora-ui"))
            from backend.otp import normalize_iran_phone, phone_digest  # noqa: E402
        except Exception:  # pragma: no cover - درخت سرور در دسترس نیست
            self.skipTest("backend tree unavailable")
        for raw in ("09120000001", "۰۹۱۲۰۰۰۰۰۰۱", "+989120000001", "00989120000001"):
            self.assertEqual(audit.normalize_iran_phone(raw), normalize_iran_phone(raw))
            self.assertEqual(
                audit.phone_digest(PEPPER, audit.normalize_iran_phone(raw)),
                phone_digest(PEPPER, normalize_iran_phone(raw)),
            )

    def test_correlation_finds_matching_phone_identity(self):
        try:
            server = audit.audit_server("sqlite:///" + str(self._server_db()))
        except audit.AuditError as exc:
            self.skipTest(f"server audit unavailable: {exc}")
        legacy = audit.audit_legacy(self.db)
        legacy["bale_ids"] = audit.collect_legacy_bale_ids(self.db)
        correlation = audit.correlate(
            legacy, server,
            legacy_mobiles=audit.collect_legacy_mobiles(self.db),
            pepper=PEPPER,
        )
        # در پایگاه سرور فقط یک هویت شماره‌ای (09120000001) وجود دارد، ولی دو
        # کاربر محلی (با ارقام فارسی و لاتین) به همان هویت می‌رسند — همان
        # تعارضی که باید پیش از مهاجرت دیده شود.
        self.assertEqual(correlation["legacy_phones_matching_a_server_phone_identity"], 2)
        self.assertEqual(correlation["distinct_server_phone_identities_matched"], 1)
        self.assertEqual(correlation["collisions_on_same_phone_identity"], 1)
        # فقط 101 در سرور هست؛ بقیهٔ شناسه‌های محلی هنوز به سرور نرسیده‌اند.
        self.assertEqual(correlation["legacy_bale_ids_present_in_server"], 1)
        self.assertGreaterEqual(correlation["legacy_bale_ids_absent_from_server"], 4)

    def _server_db(self) -> Path:
        path = self.tmp / "server.db"
        sys.path.insert(0, str(ROOT.parent / "website" / "nora-ui"))
        from backend.models import (  # noqa: E402
            AccountRecord,
            Base,
            PlatformIdentityRecord,
        )
        from sqlalchemy import create_engine  # noqa: E402
        from sqlalchemy.orm import Session  # noqa: E402

        engine = create_engine("sqlite:///" + str(path))
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(AccountRecord(id="acct-1"))
            db.add(PlatformIdentityRecord(id="ident-1", account_id="acct-1",
                                          provider="phone",
                                          provider_user_id=audit.phone_digest(
                                              PEPPER, "09120000001")))
            db.add(AccountRecord(id="acct-2"))
            db.add(PlatformIdentityRecord(id="ident-2", account_id="acct-2",
                                          provider="bale", provider_user_id="101"))
            db.commit()
        engine.dispose()
        return path

    # ── CLI ───────────────────────────────────────────────────────────
    def test_cli_json_output_is_machine_readable(self):
        import contextlib
        import io

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = audit.main(["--database", str(self.db), "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["legacy"]["users"]["total"], 6)
        self.assertEqual(payload["tool"], "legacy_data_audit")

    def test_cli_missing_database_returns_2_without_traceback(self):
        import contextlib
        import io

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = audit.main(["--database", str(self.tmp / "nope.db")])
        self.assertEqual(code, 2)
        self.assertIn("database_not_found", buffer.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
