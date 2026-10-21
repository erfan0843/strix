"""ساخت پایگاه SQLite «مصنوعی» با همان اسکیمای واقعی ربات، برای آزمون ممیزی/انتقال.

هیچ دادهٔ واقعی در این فایل نیست: نام‌ها، شماره‌ها و شناسه‌ها ساختگی‌اند و
فقط الگوهای خطا را بازسازی می‌کنند (گواهی بی‌صاحب، سریال تکراری، سهم بدون
شناسهٔ بله، امتیاز بدون دفترکل، …). اسکیما از خود ماژول‌های ربات ساخته می‌شود تا
با کد تولید یکی باشد.

اجرا::

    DB_PATH=/tmp/synth/nora.db python tests/build_synthetic_legacy.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# شناسه‌های ساختگی بله (در هیچ سامانهٔ واقعی وجود ندارند)
U_OK1, U_OK2, U_OK3, U_ORPHAN, U_NOCERT = 910001, 910002, 910003, 919999, 910004


def build(db_path: Path) -> dict[str, int]:
    os.environ["DB_PATH"] = str(db_path)
    os.environ.setdefault("BOT_TOKEN", "000000000:synthetic-not-a-real-token")
    os.environ.setdefault("SUPER_ADMIN_ID", "1")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    import database  # noqa: E402  (از ربات؛ DB_PATH از محیط خوانده می‌شود)
    import attendance  # noqa: E402
    import certgen  # noqa: E402
    import certcenter  # noqa: E402
    import certverify  # noqa: E402
    import club  # noqa: E402
    import events  # noqa: E402
    import occasions  # noqa: E402

    database.init_db()
    events.init_event_tables()
    attendance.init_attendance_tables()
    certgen.init_cert_tables()
    certverify.init_tables()
    certcenter.init_tables()
    club.init_club_tables()
    occasions.init_occasion_tables()
    database.close_db() if hasattr(database, "close_db") else None

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    users = [
        (U_OK1, "کاربر", "یکم", "09120000001", 1, 40, 0),
        (U_OK2, "کاربر", "دوم", "09120000002", 1, 15, 1),
        (U_OK3, "کاربر", "سوم", "09120000003", 1, 0, 0),
        (U_NOCERT, "کاربر", "چهارم", "0912 000 0004", 0, -5, 0),
    ]
    for bale_id, fn, ln, mobile, verified, points, vip in users:
        cur.execute(
            "INSERT INTO users (bale_user_id, first_name, last_name, mobile, phone_verified, "
            "total_points, is_vip, profile_status) VALUES (?,?,?,?,?,?,?,?)",
            (bale_id, fn, ln, mobile, verified, points, vip, "approved"),
        )
    cur.execute("INSERT INTO events (id, title, status) VALUES (1, 'کارگاه ساختگی الف', 'completed')")
    cur.execute("INSERT INTO events (id, title, status) VALUES (2, 'کارگاه ساختگی ب', 'completed')")
    cur.execute("INSERT INTO cert_templates (id, name, kind, is_active) VALUES (1, 'قالب ساختگی', 'docx', 1)")
    cur.execute("INSERT INTO event_certs (id, event_id, template_id, title, is_active) VALUES (1, 1, 1, 'گواهی رویداد الف', 1)")

    certs = [
        # id, event_id, bale, serial, revoked, source, event_cert_id, pdf_path, png_path, doc_no, person_code, full_code, issued_on, expires_on, verify_count
        (1, 1, U_OK1, "NC-0001", 0, "event", 1, "files/certs/1.pdf", "files/certs/1.png", "140501", "A1", "140501-A1", "1405/01/10", "1407/01/10", 2),
        (2, 1, U_OK2, "NC-0002", 0, "event", 1, "files/certs/2.pdf", None, "140501", "A2", "140501-A2", "1405/01/10", "1404/01/10", 0),  # منقضی
        (3, 2, U_OK1, "NC-0003", 1, "manual", 0, None, None, None, None, None, "1405/02/01", None, 0),  # باطل، بدون فایل
        (4, 2, U_ORPHAN, "NC-0004", 0, "batch", 0, "files/certs/4.pdf", None, None, None, None, None, None, 0),  # بی‌صاحب
        (5, 2, None, "NC-0005", 0, "batch", 0, None, None, None, None, None, None, None, 0),  # بدون شناسهٔ بله
        (6, 2, U_OK3, "NC-0001", 0, "form", 0, None, None, None, None, None, None, None, 0),  # سریال تکراری
    ]
    # ایندکس یکتای serial در اسکیمای ربات هست؛ برای بازسازی حالت «تکراری» که در
    # پایگاه‌های قدیمی (پیش از ایندکس) رخ داده، ایندکس را موقتاً برمی‌داریم.
    cur.execute("DROP INDEX IF EXISTS uq_cert_serial")
    for row in certs:
        cur.execute(
            "INSERT INTO certificates (id, event_id, bale_user_id, serial, revoked, source, event_cert_id, "
            "pdf_path, png_path, doc_no, person_code, full_code, issued_on, expires_on, verify_count) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            row,
        )
    cur.execute("INSERT INTO cert_issues (id, title, template_id, audience, status, total, built) VALUES (1, 'طرح ساختگی', 1, 'event', 'published', 3, 1)")
    cur.execute("INSERT INTO cert_issues (id, title, template_id, audience, status) VALUES (2, 'طرح پیش‌نویس', 1, 'manual', 'draft')")
    cur.execute("INSERT INTO cert_shares (issue_id, bale_user_id, full_name, state, cert_id) VALUES (1, ?, 'کاربر یکم', 'built', 1)", (U_OK1,))
    cur.execute("INSERT INTO cert_shares (issue_id, bale_user_id, full_name, state) VALUES (1, ?, 'کاربر دوم', 'ready')", (U_OK2,))
    cur.execute("INSERT INTO cert_shares (issue_id, bale_user_id, full_name, national_id, state) VALUES (1, NULL, 'از اکسل', '0000000000', 'ready')")
    cur.execute("INSERT INTO cert_shares (issue_id, bale_user_id, full_name, state, cert_id) VALUES (1, ?, 'ارجاع شکسته', 'built', 999)", (U_OK3,))
    cur.execute("INSERT INTO cert_batches (id, code, title, template_id, is_active, total, claimed) VALUES (1, 'BATCHX', 'دستهٔ ساختگی', 1, 1, 3, 1)")
    cur.execute("INSERT INTO cert_batch_rows (batch_id, full_name, mobile, status, claimed_by, cert_id) VALUES (1, 'الف', '09120000001', 'issued', ?, 4)", (U_OK1,))
    cur.execute("INSERT INTO cert_batch_rows (batch_id, full_name, mobile, status) VALUES (1, 'ب', '09120000009', 'pending')")
    cur.execute("INSERT INTO cert_batch_rows (batch_id, full_name, national_id, status) VALUES (1, 'ج', '1111111111', 'pending')")
    cur.execute("INSERT INTO cert_verifies (cert_id, full_code, method, result) VALUES (1, '140501-A1', 'qr', 'ok')")

    # باشگاه
    cur.execute("INSERT INTO user_achievements (bale_user_id, achievement_key, points_given) VALUES (?, 'first_step', 5)", (U_OK1,))
    cur.execute("INSERT INTO user_achievements (bale_user_id, achievement_key, points_given) VALUES (?, 'ghost_key', 5)", (U_OK2,))
    cur.execute("INSERT INTO user_achievements (bale_user_id, achievement_key, points_given) VALUES (?, 'first_step', 5)", (U_ORPHAN,))
    cur.execute("INSERT INTO reward_redemptions (bale_user_id, reward_key, reward_title, cost, status) VALUES (?, 'disc10', 'کد تخفیف ۱۰٪', 60, 'done')", (U_OK1,))
    cur.execute("INSERT INTO reward_redemptions (bale_user_id, reward_key, reward_title, cost, status) VALUES (?, 'book', 'کتاب', 200, 'pending')", (U_OK2,))
    # دفترکل ناقص: فقط بخشی از امتیازها در user_actions ثبت شده‌اند
    cur.execute("INSERT INTO user_actions (bale_user_id, action_type, action_data) VALUES (?, 'achievement', ?)", (U_OK1, json.dumps({"key": "first_step", "points": 5})))
    cur.execute("INSERT INTO user_actions (bale_user_id, action_type, action_data) VALUES (?, 'reward_redeem', ?)", (U_OK1, json.dumps({"key": "disc10", "points": 60})))
    cur.execute("INSERT INTO user_actions (bale_user_id, action_type, action_data) VALUES (?, 'point_rule', ?)", (U_OK2, json.dumps({"rule": "x", "points": 10})))
    conn.commit()
    counts = {
        "users": cur.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "certificates": cur.execute("SELECT COUNT(*) FROM certificates").fetchone()[0],
    }
    conn.close()
    return counts


def _has_cols(cur: sqlite3.Cursor, table: str, cols: set[str]) -> bool:
    have = {r[1] for r in cur.execute(f"PRAGMA table_info({table})")}
    return cols <= have


if __name__ == "__main__":
    target = Path(os.environ.get("DB_PATH") or "/tmp/nora-synth/nora.db")
    print(json.dumps(build(target), ensure_ascii=False))
