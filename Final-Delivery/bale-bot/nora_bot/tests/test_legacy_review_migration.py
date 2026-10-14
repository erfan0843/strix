import contextlib
import io
import sqlite3
import stat
import tempfile
import unittest
import uuid
from pathlib import Path

from nora_bot.legacy_review_projection import project_legacy_review
from nora_bot.migrate_legacy_reviews import main, run_migration


OWNER_ID = "990001"
MEMBER_ID = "990002"


class OfflineSharedAPI:
    def __init__(self):
        self.uploads = []
        self.submissions = []

    def upload_private_file(self, bale_user_id, content, filename, idempotency_key):
        file_id = str(uuid.uuid4())
        self.uploads.append((str(bale_user_id), content, filename, idempotency_key, file_id))
        return file_id

    def submit_workflow(self, bale_user_id, kind, payload, idempotency_key):
        task_id = str(uuid.uuid4())
        self.submissions.append((str(bale_user_id), kind, dict(payload), idempotency_key, task_id))
        return {"task": {"id": task_id}, "created": True}


def _legacy_db(tmp_path: Path) -> tuple[Path, Path]:
    media = tmp_path / "media"
    media.mkdir()
    receipt_image = media / "receipt.jpg"
    receipt_image.write_bytes(b"\xff\xd8\xffoffline-test-image")
    database = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(database)
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            bale_user_id INTEGER,
            profile_photo TEXT
        );
        CREATE TABLE profile_submissions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            bale_user_id INTEGER,
            profile_data TEXT,
            status TEXT,
            created_at TEXT
        );
        CREATE TABLE payment_receipts (
            id INTEGER PRIMARY KEY,
            transaction_id INTEGER,
            event_id INTEGER,
            registration_id INTEGER,
            form_response_id INTEGER,
            bale_user_id INTEGER,
            amount INTEGER,
            photo_path TEXT,
            photo_file_id TEXT,
            ref_code TEXT,
            status TEXT,
            shared_task_id TEXT,
            created_at TEXT
        );
        CREATE TABLE events (id INTEGER PRIMARY KEY, title TEXT);
        INSERT INTO users VALUES (1, 990002, NULL);
        INSERT INTO users VALUES (2, 990001, NULL);
        INSERT INTO profile_submissions VALUES
            (11, 1, 990002, '{"full_name":"عضو آزمایشی","city":"تهران"}', 'pending', '2026-04-01');
        INSERT INTO profile_submissions VALUES
            (12, 2, 990001, '{"full_name":"مالک","mobile":"OWNER_CONTACT_REDACTED"}', 'pending', '2026-04-02');
        INSERT INTO payment_receipts VALUES
            (21, NULL, 5, NULL, NULL, 990002, 50000, '""', NULL, 'REF-21', 'pending', NULL, '2026-04-03');
        INSERT INTO payment_receipts VALUES
            (22, NULL, 5, NULL, NULL, 990002, 50000, NULL, NULL, 'REF-22', 'pending', 'already-linked', '2026-04-04');
        INSERT INTO events VALUES (5, 'رویداد آزمایشی');
        """
    )
    conn.execute("UPDATE payment_receipts SET photo_path=? WHERE id=21", (str(receipt_image),))
    conn.commit()
    conn.close()
    return database, media


class LegacyReviewMigrationTests(unittest.TestCase):
    def setUp(self):
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._temporary_directory.name)

    def tearDown(self):
        self._temporary_directory.cleanup()

    def test_dry_run_is_read_only_and_withholds_counts_and_details(self):
        database, media = _legacy_db(self.tmp_path)
        before = database.read_bytes()

        result = run_migration(
            database,
            owner_bale_user_id=OWNER_ID,
            allowed_roots=(media,),
        )

        self.assertEqual(
            result,
            {
                "mode": "dry-run",
                "pending_legacy_found": True,
                "details_withheld": True,
                "server_owner_authorization_required": True,
                "migrated": 0,
                "failed": 0,
                "backup": None,
            },
        )
        self.assertEqual(database.read_bytes(), before)
        conn = sqlite3.connect(database)
        self.assertNotIn(
            "nora_legacy_migration_meta",
            {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")},
        )
        self.assertNotIn(
            "shared_task_id",
            {row[1] for row in conn.execute("PRAGMA table_info(profile_submissions)")},
        )
        conn.close()

    def test_apply_backups_migrates_pending_only_and_never_decides(self):
        database, media = _legacy_db(self.tmp_path)
        api = OfflineSharedAPI()
        backups = self.tmp_path / "protected-backups"

        result = run_migration(
            database,
            apply=True,
            owner_bale_user_id=OWNER_ID,
            allowed_roots=(media,),
            backup_dir=backups,
            api_client=api,
        )

        self.assertEqual(result["mode"], "apply")
        self.assertEqual(result["pending_profiles"], 2)
        self.assertEqual(result["pending_receipts"], 2)
        self.assertEqual(result["already_linked"], 1)
        self.assertEqual(result["ready"], 2)
        self.assertEqual(result["migrated"], 2)
        self.assertEqual(result["failed"], 0)
        self.assertTrue(result["backup"] and (backups / result["backup"]).is_file())
        self.assertEqual(stat.S_IMODE((backups / result["backup"]).stat().st_mode), 0o600)
        backup_conn = sqlite3.connect(backups / result["backup"])
        self.assertNotIn(
            "shared_task_id",
            {row[1] for row in backup_conn.execute("PRAGMA table_info(profile_submissions)")},
        )
        backup_conn.close()
        self.assertEqual(len(api.uploads), 1)
        self.assertEqual(len(api.submissions), 2)

        profile = next(item for item in api.submissions if item[1] == "profile_review")
        receipt = next(item for item in api.submissions if item[1] == "receipt_review")
        self.assertEqual(profile[0], MEMBER_ID)
        self.assertEqual(profile[2]["_legacy_profile_submission_id"], 11)
        self.assertTrue(profile[2]["_legacy_source_id"])
        self.assertEqual(profile[2]["_legacy_created_at"], "2026-04-01")
        self.assertNotIn("mobile", profile[2])
        self.assertEqual(receipt[0], MEMBER_ID)
        self.assertEqual(receipt[2]["_legacy_receipt_id"], 21)
        self.assertEqual(receipt[2]["event_title"], "رویداد آزمایشی")
        self.assertEqual(receipt[2]["file_refs"], [api.uploads[0][4]])
        self.assertTrue(api.uploads[0][1].startswith(b"\xff\xd8\xff"))

        conn = sqlite3.connect(database)
        profile_rows = conn.execute(
            "SELECT id, status, shared_task_id FROM profile_submissions ORDER BY id"
        ).fetchall()
        receipt_rows = conn.execute(
            "SELECT id, status, shared_task_id FROM payment_receipts ORDER BY id"
        ).fetchall()
        conn.close()
        self.assertEqual(profile_rows[0][1], "pending")
        self.assertTrue(profile_rows[0][2])
        self.assertEqual(profile_rows[1][1], "pending")
        self.assertIsNone(profile_rows[1][2])
        self.assertEqual(receipt_rows[0][1], "pending")
        self.assertTrue(receipt_rows[0][2])
        self.assertEqual(receipt_rows[1][1], "pending")
        self.assertEqual(receipt_rows[1][2], "already-linked")
        self.assertTrue(all(item[0] != OWNER_ID for item in api.submissions))
        self.assertNotIn("OWNER_CONTACT_REDACTED", repr(api.submissions))

    def test_apply_rejects_unsafe_attachment_without_sending_it(self):
        database, media = _legacy_db(self.tmp_path)
        outside = self.tmp_path.parent / "outside-receipt.jpg"
        outside.write_bytes(b"\xff\xd8\xffexternal")
        conn = sqlite3.connect(database)
        conn.execute("UPDATE payment_receipts SET photo_path=? WHERE id=21", (str(outside),))
        conn.commit()
        conn.close()
        api = OfflineSharedAPI()

        result = run_migration(
            database,
            apply=True,
            owner_bale_user_id=OWNER_ID,
            allowed_roots=(media,),
            backup_dir=self.tmp_path / "backups",
            api_client=api,
        )

        self.assertEqual(result["migrated"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["skipped"], 2)  # owner profile and unsafe receipt are withheld
        self.assertEqual(result["issues"]["owner_profile_skipped"], 1)
        self.assertEqual(result["issues"]["local_attachment_outside_allowed_roots"], 1)
        self.assertFalse(any(item[1] == "receipt_review" for item in api.submissions))
        self.assertEqual(api.uploads, [])

    def test_server_decisions_project_only_to_the_matching_imported_rows(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE nora_legacy_migration_meta (key TEXT PRIMARY KEY, value TEXT);
            INSERT INTO nora_legacy_migration_meta VALUES ('source_id', 'source-123');
            CREATE TABLE profile_submissions (
                id INTEGER PRIMARY KEY, status TEXT, reviewed_by INTEGER,
                reviewed_at TEXT, rejection_reason TEXT, shared_task_id TEXT
            );
            INSERT INTO profile_submissions VALUES (11, 'pending', NULL, NULL, NULL, NULL);
            CREATE TABLE payment_receipts (
                id INTEGER PRIMARY KEY, status TEXT, reviewed_by INTEGER,
                reviewed_at TEXT, reject_reason TEXT, shared_task_id TEXT
            );
            INSERT INTO payment_receipts VALUES (21, 'pending', NULL, NULL, NULL, NULL);
            """
        )

        def execute(query, params=(), fetch=None):
            cursor = conn.execute(query, params or ())
            if fetch == "one":
                row = cursor.fetchone()
                return dict(row) if row else None
            if fetch == "all":
                return [dict(row) for row in cursor.fetchall()]
            conn.commit()
            return cursor.rowcount

        profile_task = {
            "id": "profile-task",
            "payload": {
                "_legacy_source_id": "source-123",
                "_legacy_profile_submission_id": 11,
            },
            "reviewed_by_bale_user_id": 700,
            "review_reason": "",
        }
        receipt_task = {
            "id": "receipt-task",
            "payload": {
                "_legacy_source_id": "source-123",
                "_legacy_receipt_id": 21,
            },
            "reviewed_by_bale_user_id": 700,
            "review_reason": "",
        }

        self.assertTrue(project_legacy_review("profile_review", profile_task, "approved", db_execute=execute))
        self.assertTrue(project_legacy_review("receipt_review", receipt_task, "approved", db_execute=execute))
        self.assertFalse(project_legacy_review("profile_review", profile_task, "approved", db_execute=execute))
        self.assertEqual(
            execute("SELECT status, shared_task_id FROM profile_submissions WHERE id=11", fetch="one"),
            {"status": "approved", "shared_task_id": "profile-task"},
        )
        self.assertEqual(
            execute("SELECT status, shared_task_id FROM payment_receipts WHERE id=21", fetch="one"),
            {"status": "approved", "shared_task_id": "receipt-task"},
        )

        wrong_source_task = {
            **profile_task,
            "payload": {**profile_task["payload"], "_legacy_source_id": "other-db"},
            "id": "unrelated-task",
        }
        self.assertFalse(
            project_legacy_review("profile_review", wrong_source_task, "rejected", db_execute=execute)
        )
        conn.close()

    def test_projection_write_failure_is_not_silently_accepted(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE nora_legacy_migration_meta (key TEXT PRIMARY KEY, value TEXT);
            INSERT INTO nora_legacy_migration_meta VALUES ('source_id', 'source-123');
            CREATE TABLE profile_submissions (
                id INTEGER PRIMARY KEY, status TEXT, reviewed_by INTEGER,
                reviewed_at TEXT, rejection_reason TEXT, shared_task_id TEXT
            );
            INSERT INTO profile_submissions VALUES (11, 'pending', NULL, NULL, NULL, NULL);
            """
        )

        def execute(query, params=(), fetch=None):
            if query.lstrip().startswith("UPDATE profile_submissions"):
                return None
            cursor = conn.execute(query, params or ())
            if fetch == "one":
                row = cursor.fetchone()
                return dict(row) if row else None
            conn.commit()
            return cursor.rowcount

        task = {
            "id": "profile-task",
            "payload": {
                "_legacy_source_id": "source-123",
                "_legacy_profile_submission_id": 11,
            },
        }
        with self.assertRaisesRegex(RuntimeError, "legacy_review_projection_failed"):
            project_legacy_review("profile_review", task, "rejected", db_execute=execute)
        conn.close()

    def test_cli_dry_run_warns_without_disclosing_counts_or_record_data(self):
        database, _ = _legacy_db(self.tmp_path)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main([
                "--database", str(database), "--owner-id", OWNER_ID,
                "--attachment-root", str(self.tmp_path / "media"),
            ])
        self.assertEqual(result, 0)
        report = output.getvalue()
        self.assertIn("درخواست قدیمیِ pending", report)
        self.assertIn("تعداد و جزئیات", report)
        self.assertNotIn("پروفایل‌های در انتظار", report)
        self.assertNotIn("2026-04", report)
        self.assertNotIn("عضو آزمایشی", report)

    def test_cli_requires_both_apply_and_yes(self):
        database, _ = _legacy_db(self.tmp_path)
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                main(["--database", str(database), "--apply"])
        self.assertEqual(raised.exception.code, 2)
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                main(["--database", str(database), "--yes"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
