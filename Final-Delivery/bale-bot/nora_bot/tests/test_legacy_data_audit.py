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


class CertificateAndClubAuditTests(unittest.TestCase):
    """بخش فاز سوم: ساختار گواهی‌ها و باشگاه — فقط شمارش، بدون داده‌ٔ شخصی."""

    def setUp(self) -> None:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory(prefix="nora-audit-cert-")
        self.tmp = Path(self._tmp.name)
        self.db = self.tmp / "legacy.db"
        build_legacy(self.db)
        conn = sqlite3.connect(self.db)
        conn.executescript(
            """
            DROP TABLE certificates;
            CREATE TABLE certificates (
                id INTEGER PRIMARY KEY, event_id INTEGER, bale_user_id INTEGER, serial TEXT,
                revoked INTEGER DEFAULT 0, source TEXT DEFAULT 'event', event_cert_id INTEGER DEFAULT 0,
                pdf_path TEXT, png_path TEXT, full_code TEXT, expires_on TEXT, verify_count INTEGER DEFAULT 0
            );
            CREATE TABLE cert_issues (id INTEGER PRIMARY KEY, title TEXT, status TEXT);
            CREATE TABLE cert_shares (id INTEGER PRIMARY KEY, issue_id INTEGER, bale_user_id INTEGER,
                full_name TEXT, state TEXT, cert_id INTEGER);
            CREATE TABLE cert_batches (id INTEGER PRIMARY KEY, code TEXT, is_active INTEGER, match_by TEXT);
            CREATE TABLE cert_batch_rows (id INTEGER PRIMARY KEY, batch_id INTEGER, full_name TEXT, mobile TEXT,
                status TEXT, claimed_by INTEGER, cert_id INTEGER);
            CREATE TABLE achievements (id INTEGER PRIMARY KEY, key TEXT, is_active INTEGER DEFAULT 1);
            CREATE TABLE user_achievements (id INTEGER PRIMARY KEY, bale_user_id INTEGER, achievement_key TEXT, points_given INTEGER);
            CREATE TABLE rewards (id INTEGER PRIMARY KEY, key TEXT);
            CREATE TABLE reward_redemptions (id INTEGER PRIMARY KEY, bale_user_id INTEGER, reward_key TEXT, status TEXT);
            CREATE TABLE point_rules (id INTEGER PRIMARY KEY, key TEXT, is_active INTEGER DEFAULT 1, total_awarded INTEGER DEFAULT 0);
            CREATE TABLE user_actions (id INTEGER PRIMARY KEY, bale_user_id INTEGER, action_type TEXT, action_data TEXT);
            ALTER TABLE users ADD COLUMN total_points INTEGER DEFAULT 0;
            ALTER TABLE users ADD COLUMN is_vip INTEGER DEFAULT 0;
            UPDATE users SET total_points = 40, is_vip = 1 WHERE id = 1;
            UPDATE users SET total_points = 10 WHERE id = 2;
            """
        )
        conn.executemany(
            "INSERT INTO certificates (id, event_id, bale_user_id, serial, revoked, source, pdf_path, full_code, expires_on, verify_count)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (1, 1, 101, "N-0001", 0, "event", "files/certs/1.pdf", "140501-A1", "1407/01/01", 2),
                (2, 1, 102, "N-0002", 0, "event", None, "140501-A2", None, 0),
                (3, 1, 888, "N-0003", 1, "batch", "files/certs/3.pdf", None, None, 0),   # بی‌صاحب + باطل
                (4, 1, None, "N-0001", 0, "batch", None, None, None, 0),                # بدون شناسه + سریال تکراری
                (5, 9, 101, "N-0005", 0, "manual", "../../etc/x.pdf", None, None, 0),   # رویداد غایب + مسیر ناامن
            ],
        )
        conn.executemany("INSERT INTO cert_issues VALUES (?,?,?)", [(1, "طرح", "published"), (2, "طرح۲", "draft")])
        conn.executemany(
            "INSERT INTO cert_shares VALUES (?,?,?,?,?,?)",
            [(1, 1, 101, "زهرا", "built", 1), (2, 1, None, "اکسلی", "ready", None), (3, 1, 102, "علی", "built", 999)],
        )
        conn.execute("INSERT INTO cert_batches VALUES (1, 'B1', 1, 'mobile')")
        conn.executemany(
            "INSERT INTO cert_batch_rows VALUES (?,?,?,?,?,?,?)",
            [(1, 1, "الف", "09120000001", "issued", 101, 1), (2, 1, "ب", "09120000007", "pending", None, None)],
        )
        conn.execute("INSERT INTO achievements (key) VALUES ('first_step')")
        conn.executemany(
            "INSERT INTO user_achievements (bale_user_id, achievement_key, points_given) VALUES (?,?,?)",
            [(101, "first_step", 5), (102, "ghost", 5), (999, "first_step", 5)],
        )
        conn.execute("INSERT INTO rewards (key) VALUES ('disc10')")
        conn.executemany(
            "INSERT INTO reward_redemptions (bale_user_id, reward_key, status) VALUES (?,?,?)",
            [(101, "disc10", "done"), (999, "disc10", "pending")],
        )
        conn.execute("INSERT INTO point_rules (key, total_awarded) VALUES ('r1', 30)")
        conn.executemany(
            "INSERT INTO user_actions (bale_user_id, action_type, action_data) VALUES (?,?,?)",
            [(101, "achievement", '{"key":"first_step","points":5}'),
             (101, "reward_redeem", '{"key":"disc10","points":60}'),
             (102, "point_rule", '{"rule":"r1","points":10}'),
             (102, "profile_edit", '{"field":"bio"}')],
        )
        conn.commit()
        conn.close()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_certificate_structure_and_ownership_counts(self):
        report = audit.run_audit(self.db)
        certs = report["legacy"]["certificates"]
        self.assertTrue(certs["present"])
        self.assertEqual(certs["owner_key"], "bale_user_id")
        self.assertEqual(certs["total"], 5)
        self.assertEqual(certs["with_bale_user_id"], 4)
        self.assertEqual(certs["without_bale_user_id"], 1)
        self.assertEqual(certs["owner_in_users"], 3)
        self.assertEqual(certs["owner_missing_from_users"], 1)
        self.assertEqual(certs["revoked"], 1)
        self.assertEqual(certs["active"], 4)
        self.assertEqual(certs["by_source"], {"event": 2, "batch": 2, "manual": 1})
        self.assertEqual(certs["duplicate_serials"], 1)
        self.assertEqual(certs["with_full_code"], 2)
        self.assertEqual(certs["with_file_path"], 3)
        self.assertEqual(certs["without_file_path"], 2)
        self.assertEqual(certs["file_paths_outside_relative_root"], 1)
        self.assertEqual(certs["event_missing"], 1)
        self.assertEqual(certs["verified_at_least_once"], 1)
        self.assertEqual(certs["issues_by_status"], {"published": 1, "draft": 1})
        self.assertEqual(certs["shares"]["by_state"], {"built": 2, "ready": 1})
        self.assertEqual(certs["shares"]["without_bale_user_id"], 1)
        self.assertEqual(certs["shares"]["built_with_missing_certificate"], 1)
        self.assertEqual(certs["batch_rows"]["by_status"], {"issued": 1, "pending": 1})
        self.assertEqual(certs["batch_rows"]["unclaimed_without_bale_user_id"], 1)

    def test_club_points_ledger_is_reported_as_incomplete(self):
        report = audit.run_audit(self.db)
        club = report["legacy"]["club"]
        self.assertEqual(club["points"]["storage"], "users.total_points")
        self.assertEqual(club["points"]["users_with_points"], 2)
        self.assertEqual(club["points"]["sum_recorded"], 50)
        self.assertEqual(club["points"]["vip_users"], 1)
        ledger = club["ledger"]
        self.assertEqual(ledger["rows_by_type"], {"achievement": 1, "reward_redeem": 1, "point_rule": 1})
        self.assertEqual(ledger["net_points_in_ledger"], 5 - 60 + 10)
        self.assertEqual(ledger["counter_minus_ledger"], 50 - (5 - 60 + 10))
        self.assertFalse(ledger["reconstructible"])
        self.assertEqual(ledger["retention_days_in_code"], 90)
        self.assertEqual(club["achievements"]["earned_orphans"], 1)
        self.assertEqual(club["achievements"]["earned_unknown_key"], 1)
        self.assertEqual(club["rewards"]["redemption_orphans"], 1)
        self.assertEqual(club["point_rules"]["sum_total_awarded"], 30)
        self.assertEqual(club["membership_level"]["status"], "not_a_data_field")

    def test_certificate_blockers_and_privacy(self):
        before = file_digest(self.db)
        report = audit.run_audit(self.db, include_identifiers=True)
        codes = {item["code"] for item in report["blockers"]}
        self.assertIn("certificate_owner_missing", codes)
        self.assertIn("certificate_without_owner_key", codes)
        self.assertIn("certificate_duplicate_serial", codes)
        blob = json.dumps(report, ensure_ascii=False)
        for secret in ("0912000000", "زهرا", "علی", "اکسلی", "files/certs", "etc/x.pdf", "N-0001", "140501-A1"):
            self.assertNotIn(secret, blob)
        self.assertEqual(sorted(report["legacy"]["certificate_bale_ids"]), ["101", "101", "102", "888"])
        self.assertEqual(file_digest(self.db), before)

    def test_correlation_counts_certificate_rows_with_server_identity(self):
        legacy = {"bale_ids": ["101", "102", "888"], "certificate_bale_ids": ["101", "101", "102", "888"]}
        server = {"bale_subject_ids": ["101", "888"], "phone_subjects": []}
        corr = audit.correlate(legacy, server, legacy_mobiles=[], pepper=PEPPER)
        self.assertEqual(corr["certificate_rows_with_server_bale_identity"], 3)
        self.assertEqual(corr["certificate_rows_without_server_identity"], 1)
