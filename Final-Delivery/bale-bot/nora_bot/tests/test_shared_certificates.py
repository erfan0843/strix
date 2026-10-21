"""آینهٔ گواهی‌ها در سرور مشترک و اسکریپت انتقال گواهی‌های قدیمی — کاملاً آفلاین.

* هیچ اتصال شبکه‌ای برقرار نمی‌شود (API جعلی در حافظه).
* پایگاه ربات فقط دو ستون پیوند و یک جدول meta می‌گیرد؛ هیچ ردیفی حذف یا
  بازنویسی نمی‌شود.
* مالک بدون هویت سرور («unmapped») هرگز به‌صورت خودکار نگاشت نمی‌شود.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import sqlite3
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import migrate_legacy_certificates as migration  # noqa: E402
import shared_certificates as sc  # noqa: E402


class OfflineSharedAPI:
    """شبیه‌ساز رفتار سرور: فقط شناسه‌های موجود در ``known`` هویت دارند."""

    def __init__(self, known: set[str]):
        self.known = known
        self.uploads: list[tuple] = []
        self.submissions: list[tuple] = []
        self.records: dict[str, dict] = {}

    def upload_private_file(self, bale_user_id, content, filename, idempotency_key):
        file_id = str(uuid.uuid4())
        self.uploads.append((str(bale_user_id), content, filename, idempotency_key, file_id))
        return file_id

    def submit_certificate(self, bale_user_id, external_key, certificate, file_refs=None):
        if str(bale_user_id) not in self.known:
            raise _ApiError(404, "owner_identity_not_found")
        created = external_key not in self.records
        record = self.records.setdefault(external_key, {"id": str(uuid.uuid4()), "owner": str(bale_user_id)})
        record.update(certificate=dict(certificate), file_refs=dict(file_refs or {}) or record.get("file_refs", {}))
        self.submissions.append((str(bale_user_id), external_key, dict(certificate), dict(file_refs or {})))
        return {
            "id": record["id"], "created": created, "status": certificate["status"],
            "has_file": "pdf" in record["file_refs"], "has_preview": "png" in record["file_refs"],
        }


class _ApiError(Exception):
    def __init__(self, status, code):
        super().__init__(code)
        self.status = status
        self.code = code


def build_db(tmp: Path) -> tuple[Path, Path]:
    files = tmp / "files" / "certificates"
    files.mkdir(parents=True)
    (files / "1.pdf").write_bytes(b"%PDF-1.4\n%offline\n%%EOF\n")
    (files / "1.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    (files / "3.pdf").write_bytes(b"not a pdf at all")
    outside = tmp / "outside.pdf"
    outside.write_bytes(b"%PDF-1.4\n%outside\n%%EOF\n")
    db = tmp / "nora.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        f"""
        CREATE TABLE users (id INTEGER PRIMARY KEY, bale_user_id INTEGER, first_name TEXT, last_name TEXT,
            bale_first_name TEXT, bale_last_name TEXT, mobile TEXT);
        CREATE TABLE events (id INTEGER PRIMARY KEY, title TEXT);
        CREATE TABLE event_certs (id INTEGER PRIMARY KEY, event_id INTEGER, title TEXT);
        CREATE TABLE cert_templates (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE certificates (
            id INTEGER PRIMARY KEY, event_id INTEGER, user_id INTEGER, bale_user_id INTEGER, serial TEXT,
            template TEXT, file_path TEXT, issued_by INTEGER, issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            template_id INTEGER, png_path TEXT, pdf_path TEXT, docx_path TEXT, form_id INTEGER, response_id INTEGER,
            revoked INTEGER DEFAULT 0, event_cert_id INTEGER DEFAULT 0, source TEXT DEFAULT 'event', batch_id INTEGER,
            doc_no TEXT, person_code TEXT, full_code TEXT, issued_on TEXT, expires_on TEXT, valid_months INTEGER DEFAULT 0,
            verify_count INTEGER DEFAULT 0, last_verified TEXT
        );
        INSERT INTO users VALUES (1, 910001, 'زهرا', 'موسوی', NULL, NULL, '09120000001');
        INSERT INTO users VALUES (2, 910002, NULL, NULL, 'علی', 'رضایی', '09120000002');
        INSERT INTO events VALUES (17, 'کارگاه نجوم'), (18, 'دورهٔ تلسکوپ');
        INSERT INTO event_certs VALUES (1, 17, 'گواهی حضور');
        INSERT INTO cert_templates VALUES (5, 'قالب پایه');
        INSERT INTO certificates (id, event_id, bale_user_id, serial, issued_by, issued_at, template_id, png_path, pdf_path,
            revoked, event_cert_id, source, doc_no, person_code, full_code, issued_on, expires_on, verify_count)
        VALUES (1, 17, 910001, 'NC-0001', 70001, '2026-04-01 10:00:00', 5, 'files/certificates/1.png',
                'files/certificates/1.pdf', 0, 1, 'event', '1421', 'A7K2M9', '1421/A7K2M9', '1405/01/12', '', 3);
        INSERT INTO certificates (id, event_id, bale_user_id, serial, issued_at, revoked, source)
        VALUES (2, 18, 910002, 'NC-0002', '2026-04-02 10:00:00', 1, 'manual');
        INSERT INTO certificates (id, event_id, bale_user_id, serial, pdf_path, source)
        VALUES (3, 18, 919999, 'NC-0003', 'files/certificates/3.pdf', 'batch');
        INSERT INTO certificates (id, event_id, bale_user_id, serial, source) VALUES (4, 18, NULL, 'NC-0004', 'batch');
        INSERT INTO certificates (id, event_id, bale_user_id, serial, pdf_path, source)
        VALUES (5, 17, 910001, 'NC-0005', '{outside}', 'center');
        """
    )
    conn.commit()
    conn.close()
    return db, tmp / "files"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SharedCertificateSyncTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nora-cert-sync-")
        self.tmp = Path(self._tmp.name)
        self.db, self.files_root = build_db(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self):
        conn = sqlite3.connect(self.db)
        return conn, sc.connection_executor(conn)

    def test_payload_uses_only_stable_fields_and_no_phone(self):
        conn, run = self._run()
        try:
            cert = sc.load_certificate(run, 1)
            payload = sc.build_payload(run, cert, source="bot", source_key="0c7f7f5e-9c1e-4a7e-8a1c-2b3d4e5f6a7b")
            self.assertEqual(payload["status"], "issued")
            self.assertEqual(payload["legacy_id"], 1)
            self.assertEqual(payload["event_ref"], "17")
            self.assertEqual(payload["event_title"], "کارگاه نجوم")
            self.assertEqual(payload["title"], "گواهی حضور")
            self.assertEqual(payload["holder_name"], "زهرا موسوی")
            self.assertEqual(payload["issued_at"], "2026-04-01T10:00:00+00:00")
            self.assertEqual(payload["issued_by_bale_user_id"], "70001")
            self.assertEqual(payload["verify_count"], 3)
            self.assertNotIn("0912", repr(payload))
            self.assertNotIn("bale_user_id", payload)
            fallback = sc.build_payload(run, sc.load_certificate(run, 2), source="bot", source_key="")
            self.assertEqual(fallback["status"], "revoked")
            self.assertEqual(fallback["kind"], "manual")
            self.assertEqual(fallback["holder_name"], "علی رضایی")
            self.assertEqual(fallback["title"], "")
            # فاز ۹.۲ — گواهی پایان محتوای ضبط‌شده: kind جدا؛ بدون جدول‌های مرکز، عنوان به نام قالب برمی‌گردد
            run("INSERT INTO certificates (id, event_id, bale_user_id, serial, template_id, source) "
                "VALUES (6, NULL, 910001, 'NC-0006', 5, 'recording')")
            recording = sc.build_payload(run, sc.load_certificate(run, 6), source="bot", source_key="")
            self.assertEqual(recording["kind"], "recording")
            self.assertEqual(recording["event_ref"], "")
            self.assertEqual(recording["title"], "قالب پایه")
        finally:
            conn.close()

    def test_sync_mirrors_files_and_marks_row_without_touching_other_rows(self):
        api = OfflineSharedAPI(known={"910001", "910002"})
        conn, run = self._run()
        try:
            before = {row["id"]: dict(row) for row in run("SELECT * FROM certificates", fetch="all")}
            outcome = sc.sync_certificate(1, run=run, api_client=api, allowed_roots=(self.files_root,), base_dir=self.db.parent)
            self.assertEqual(outcome["outcome"], "mirrored")
            self.assertTrue(outcome["created"])
            self.assertEqual(len(api.uploads), 2)
            self.assertEqual({item[2] for item in api.uploads}, {"certificate-1.pdf", "certificate-1.png"})
            self.assertTrue(all(item[3].startswith("cert-file:") for item in api.uploads))
            # دو ارسال: اول بدون فایل (بررسی مالک)، دوم با مرجع فایل‌های همان مالک
            self.assertEqual(len(api.submissions), 2)
            self.assertEqual(api.submissions[0][3], {})
            self.assertEqual(set(api.submissions[1][3]), {"pdf", "png"})
            source_key = sc.source_id(run, create=False)
            self.assertIsNotNone(source_key)
            self.assertEqual(api.submissions[0][1], f"{source_key}:1")
            row = sc.load_certificate(run, 1)
            self.assertEqual(row["shared_certificate_id"], outcome["shared_id"])
            self.assertTrue(row["shared_synced_at"])
            # سایر ردیف‌ها بدون تغییر (جز ستون‌های پیوند تازه که خالی‌اند)
            for cert_id, old in before.items():
                if cert_id == 1:
                    continue
                current = sc.load_certificate(run, cert_id)
                self.assertEqual({k: v for k, v in current.items() if k in old}, old)
                self.assertIsNone(current["shared_certificate_id"])
            # ارسال دوباره idempotent است و ردیف تکراری نمی‌سازد
            again = sc.sync_certificate(1, run=run, api_client=api, allowed_roots=(self.files_root,), base_dir=self.db.parent)
            self.assertEqual(again["outcome"], "mirrored")
            self.assertFalse(again["created"])
            self.assertEqual(again["shared_id"], outcome["shared_id"])
            self.assertEqual(len(api.records), 1)
            # ابطال → همان کلید، وضعیت جدید
            run("UPDATE certificates SET revoked=1 WHERE id=1")
            revoked = sc.sync_certificate(1, run=run, api_client=api, allowed_roots=(self.files_root,), base_dir=self.db.parent)
            self.assertEqual(revoked["outcome"], "mirrored")
            self.assertEqual(api.submissions[-1][2]["status"], "revoked")
        finally:
            conn.close()

    def test_unmapped_owner_missing_key_and_unsafe_files(self):
        api = OfflineSharedAPI(known={"910001"})
        conn, run = self._run()
        try:
            # مالک بدون هویت سرور: ارسال می‌شود، سرور رد می‌کند، هیچ نگاشتی ساخته نمی‌شود
            unmapped = sc.sync_certificate(3, run=run, api_client=api, allowed_roots=(self.files_root,), base_dir=self.db.parent)
            self.assertEqual(unmapped["outcome"], "unmapped")
            self.assertEqual(unmapped["code"], "owner_identity_not_found")
            self.assertEqual(api.uploads, [])
            self.assertIsNone(sc.load_certificate(run, 3)["shared_certificate_id"])
            # بدون کلید مالک: حتی به سرور نمی‌رود
            no_key = sc.sync_certificate(4, run=run, api_client=api, allowed_roots=(self.files_root,), base_dir=self.db.parent)
            self.assertEqual(no_key["outcome"], "unmapped")
            self.assertEqual(no_key["code"], "certificate_without_owner_key")
            self.assertEqual(api.submissions, [])
            # فایل بیرون از ریشهٔ مجاز بارگذاری نمی‌شود ولی خود گواهی آینه می‌شود
            outside = sc.sync_certificate(5, run=run, api_client=api, allowed_roots=(self.files_root,), base_dir=self.db.parent)
            self.assertEqual(outside["outcome"], "mirrored")
            self.assertEqual(api.uploads, [])
            # فایلی که PDF واقعی نیست (sniff) بارگذاری نمی‌شود
            api.known.add("919999")
            sniffed = sc.sync_certificate(3, run=run, api_client=api, allowed_roots=(self.files_root,), base_dir=self.db.parent)
            self.assertEqual(sniffed["outcome"], "mirrored")
            self.assertEqual(api.uploads, [])
            missing = sc.sync_certificate(999, run=run, api_client=api, allowed_roots=(), base_dir=self.db.parent)
            self.assertEqual(missing["outcome"], "missing")
        finally:
            conn.close()

    def test_network_failure_is_reported_not_raised(self):
        class BrokenAPI:
            def submit_certificate(self, *args, **kwargs):
                raise _ApiError(0, "shared_api_unreachable")

        conn, run = self._run()
        try:
            outcome = sc.sync_certificate(1, run=run, api_client=BrokenAPI(), allowed_roots=(), base_dir=self.db.parent)
            self.assertEqual(outcome, {"outcome": "failed", "shared_id": None, "code": "shared_api_unreachable"})
            self.assertIsNone(sc.load_certificate(run, 1)["shared_certificate_id"])
        finally:
            conn.close()


class LegacyCertificateMigrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nora-cert-migrate-")
        self.tmp = Path(self._tmp.name)
        self.db, self.files_root = build_db(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def test_dry_run_is_read_only_and_counts_without_pii(self):
        before = digest(self.db)
        summary = migration.run_migration(self.db, allowed_roots=(self.files_root,))
        self.assertEqual(summary["mode"], "dry-run")
        self.assertEqual(summary["total"], 5)
        self.assertEqual(summary["candidates"], 4)
        self.assertEqual(summary["without_owner_key"], 1)
        self.assertEqual(summary["revoked_candidates"], 1)
        # ردیف ۱ و ۳ مسیر PDF داخل ریشه دارند (محتوای ۳ هنگام ارسال sniff و رد می‌شود)؛ ردیف ۵ خارج ریشه است
        self.assertEqual(summary["with_pdf"], 2)
        self.assertEqual(summary["with_png"], 1)
        self.assertEqual(summary["file_unavailable"], 1)
        self.assertEqual(summary["mirrored"], 0)
        self.assertEqual(digest(self.db), before)
        self.assertNotIn("0912", repr(summary))
        self.assertNotIn("زهرا", repr(summary))
        conn = sqlite3.connect(self.db)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(certificates)")}
        conn.close()
        self.assertNotIn("shared_certificate_id", columns)

    def test_apply_requires_owner_and_links_rows_idempotently(self):
        api = OfflineSharedAPI(known={"910001", "910002"})
        with self.assertRaises(migration.MigrationError):
            migration.run_migration(self.db, apply=True, api_client=api, allowed_roots=(self.files_root,))
        summary = migration.run_migration(
            self.db, apply=True, owner_bale_user_id="70001", api_client=api,
            allowed_roots=(self.files_root,), backup_dir=self.tmp / "bk",
        )
        self.assertEqual(summary["mode"], "apply")
        self.assertEqual(summary["mirrored"], 3)
        self.assertEqual(summary["unmapped"], 1)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["issues"], {"owner_identity_not_found": 1})
        self.assertTrue(summary["backup"] and (self.tmp / "bk" / summary["backup"]).is_file())
        self.assertEqual(sorted(path.name for path in (self.tmp / "bk").iterdir()), [summary["backup"]])
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        rows = {row["id"]: dict(row) for row in conn.execute("SELECT * FROM certificates ORDER BY id")}
        meta = conn.execute("SELECT value FROM nora_legacy_migration_meta WHERE key='source_id'").fetchone()[0]
        conn.close()
        self.assertEqual(len(rows), 5)
        self.assertTrue(rows[1]["shared_certificate_id"] and rows[2]["shared_certificate_id"] and rows[5]["shared_certificate_id"])
        self.assertIsNone(rows[3]["shared_certificate_id"])
        self.assertIsNone(rows[4]["shared_certificate_id"])
        self.assertEqual(rows[3]["bale_user_id"], 919999)  # ردیف جدا مانده، دست‌نخورده
        self.assertEqual(rows[1]["serial"], "NC-0001")
        self.assertEqual(api.submissions[0][1], f"{meta}:1")
        self.assertTrue(all(sub[2]["source"] == "bot_legacy" for sub in api.submissions))
        # اجرای دوباره: ردیف‌های متصل رد می‌شوند و فقط unmapped دوباره امتحان می‌شود
        second = migration.run_migration(
            self.db, apply=True, owner_bale_user_id="70001", api_client=api,
            allowed_roots=(self.files_root,), backup_dir=self.tmp / "bk",
        )
        self.assertEqual(second["already_linked"], 3)
        self.assertEqual(second["candidates"], 1)
        self.assertEqual(second["mirrored"], 0)
        self.assertEqual(second["unmapped"], 1)
        self.assertEqual(len(api.records), 3)
        skip = migration.run_migration(
            self.db, apply=True, owner_bale_user_id="70001", api_client=OfflineSharedAPI(known=set()),
            allowed_roots=(self.files_root,), include_revoked=False,
        )
        self.assertEqual(skip["unmapped"], 1)

    def test_cli_refuses_apply_without_yes_and_prints_safe_summary(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                migration.main(["--database", str(self.db), "--apply"])
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                migration.main(["--database", str(self.db), "--yes"])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = migration.main(["--database", str(self.db), "--json", "--file-root", str(self.files_root)])
        self.assertEqual(code, 0)
        self.assertIn('"mode": "dry-run"', out.getvalue())
        self.assertNotIn("0912", out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = migration.main(["--database", str(self.tmp / "missing.db")])
        self.assertEqual(code, 2)
        self.assertIn("database_file_not_found", out.getvalue())


if __name__ == "__main__":
    unittest.main()
