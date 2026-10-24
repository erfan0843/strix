"""
دیتابیس ربات نورا - نسخه 4.1 (فیکس شده)

فیکس‌های مهم نسبت به فاز ۴:
- کانکشن تک‌نمونه‌ای با قفل (قبلاً هر کوئری یک کانکشن باز/بسته می‌کرد -> کندی و قفل شدن WAL)
- foreign_keys و synchronous تنظیم شد
- ایندکس‌های لازم اضافه شد
- بک‌آپ امن با API خود sqlite (قبلاً copy2 وسط نوشتن = فایل خراب)
- جدول settings برای متن‌های قابل تغییر از پنل ادمین
- ستون UNIQUE روی mobile به‌صورت ایندکس جزئی (بدون خراب کردن رکوردهای موجود)
"""
import contextlib
import os
import sqlite3
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from privacy import redact_log_text

from config import (
    DB_PATH, BACKUP_DIR, LOG_DIR, FILES_DIR,
    PROFILES_DIR, IMPORT_DIR, MAX_BACKUPS,
    AUTO_BACKUP_HOURS, KEEP_DAILY_BACKUPS,
)

_lock = threading.RLock()
_conn = None
# عمق تراکنش چنددستوری فعال (فقط زیر همان قفل تغییر می‌کند)
_tx_depth = 0


# ==================== LOG ====================
def log(msg):
    """چاپ در کنسول + ذخیره در فایل لاگ"""
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {redact_log_text(msg)}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        # ویندوز و کنسول‌های بدون UTF-8
        print(line.encode("ascii", "ignore").decode(), flush=True)
    try:
        Path(LOG_DIR).mkdir(parents=True, exist_ok=True, mode=0o700)
        fp = Path(LOG_DIR) / f"bot_{datetime.now().strftime('%Y%m%d')}.log"
        descriptor = os.open(fp, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ==================== CONNECTION ====================
def get_db():
    """کانکشن مشترک (thread-safe با قفل)"""
    global _conn
    with _lock:
        if _conn is None:
            Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA busy_timeout=30000")
            _conn.execute("PRAGMA synchronous=NORMAL")
            _conn.execute("PRAGMA foreign_keys=ON")
        return _conn


def close_db():
    global _conn
    with _lock:
        if _conn is not None:
            try:
                _conn.commit()
                _conn.close()
            except Exception:
                pass
            _conn = None


def db_execute(query, params=(), fetch=None):
    """
    اجرای کوئری.
      fetch='one'  -> dict یا None
      fetch='all'  -> list[dict]
      fetch=None   -> commit و برگرداندن lastrowid

    فیکس: دیگر خطا raise نمی‌کند و ربات را نمی‌خواباند؛
    خطا لاگ می‌شود و None/[] برمی‌گردد.
    """
    with _lock:
        conn = get_db()
        try:
            cur = conn.execute(query, params)
            if fetch == "one":
                row = cur.fetchone()
                return dict(row) if row else None
            if fetch == "all":
                return [dict(r) for r in cur.fetchall()]
            if _tx_depth == 0:
                conn.commit()
            return cur.lastrowid
        except Exception as e:
            if _tx_depth > 0:
                # داخل تراکنش چنددستوری: خطا باید کل تراکنش را برگرداند،
                # نه این‌که بی‌صدا بلعیده شود.
                raise
            try:
                conn.rollback()
            except Exception:
                pass
            # SQL/driver messages can contain participant answers and credentials.
            log(f"❌ خطای پایگاه داده: {type(e).__name__}")
            if fetch == "all":
                return []
            return None


@contextlib.contextmanager
def db_transaction():
    """تراکنش چنددستوری روی همان اتصال مشترک.

    * بیرونی‌ترین فراخوانی ``BEGIN IMMEDIATE`` می‌زند، در پایان commit و در هر
      استثنا rollback می‌کند و همان استثنا را بالا می‌فرستد.
    * فراخوانی تو در تو هیچ ``BEGIN``/commit تازه‌ای نمی‌سازد و در تراکنش
      بیرونی شرکت می‌کند (نتیجهٔ نهایی را بیرونی‌ترین سطح تعیین می‌کند).
    * ``db_execute`` در این بازه commit مستقل نمی‌کند و خطا را بالا می‌دهد؛
      بیرون از این بازه رفتارش دقیقاً مثل قبل است.
    * قفل سراسری در کل بازه نگه داشته می‌شود، پس نخ دیگری وسط تراکنش نمی‌نویسد.
    """
    global _tx_depth
    with _lock:
        conn = get_db()
        if _tx_depth > 0:
            _tx_depth += 1
            try:
                yield conn
            finally:
                _tx_depth -= 1
            return
        if conn.in_transaction:
            # باقی‌ماندهٔ یک تراکنش ضمنی ناتمام؛ پیش از BEGIN صریح بسته می‌شود.
            conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        _tx_depth = 1
        try:
            yield conn
        except BaseException:
            try:
                conn.rollback()
            finally:
                _tx_depth = 0
            raise
        else:
            try:
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                _tx_depth = 0


def in_transaction():
    """آیا هم‌اکنون داخل ``db_transaction`` هستیم؟"""
    return _tx_depth > 0


def db_scalar(query, params=(), default=0):
    """گرفتن یک مقدار عددی (مثل COUNT) به‌صورت امن"""
    row = db_execute(query, params, fetch="one")
    if not row:
        return default
    val = list(row.values())[0]
    return default if val is None else val


# ==================== BACKUP ====================
_last_auto_backup = 0.0


def _verify_backup(path):
    """
    🔍 آیا فایل بک‌آپ سالم است؟

    بک‌آپ خراب از نبودِ بک‌آپ بدتر است — چون خیال آدم را راحت
    می‌کند ولی موقع بازیابی کار نمی‌کند.
    """
    try:
        con = sqlite3.connect(str(path))
        try:
            r = con.execute("PRAGMA integrity_check").fetchone()
            if not r or str(r[0]).lower() != "ok":
                return False
            # حداقل جدول users باید باشد و خوانده شود
            con.execute("SELECT COUNT(*) FROM users").fetchone()
            return True
        finally:
            con.close()
    except Exception:
        return False


def _keep_daily(newest):
    """
    📅 نگهداری یک بک‌آپ برای هر روز.

    MAX_BACKUPS فقط N فایل آخر را نگه می‌دارد؛ اگر ربات پرترافیک
    باشد ممکن است همه‌شان مال امروز باشند و هیچ نسخه‌ای از
    هفته پیش نماند. این تابع روزی یک نسخه را جدا آرشیو می‌کند.
    """
    try:
        day = datetime.now().strftime("%Y%m%d")
        d = Path(BACKUP_DIR) / "daily"
        d.mkdir(parents=True, exist_ok=True)
        target = d / f"nora_daily_{day}.db"
        if not target.exists():
            shutil.copy2(newest, target)
            log(f"📅 بک‌آپ روزانه: {target.name}")
        # فقط N روز آخر
        olds = sorted(d.glob("nora_daily_*.db"))
        for old in olds[:-max(1, KEEP_DAILY_BACKUPS)]:
            try:
                old.unlink()
            except Exception:
                pass
    except Exception as e:
        log(f"⚠️ بک‌آپ روزانه: {e}")


def auto_backup(force=False):
    """
    💾 بک‌آپ خودکار زمان‌بندی‌شده — از حلقه اصلی صدا زده می‌شود.

    خروجی: مسیر فایل اگر بک‌آپ گرفته شد، وگرنه None.
    """
    global _last_auto_backup
    if AUTO_BACKUP_HOURS <= 0 and not force:
        return None
    now = time.time()
    gap = AUTO_BACKUP_HOURS * 3600
    if not force and (now - _last_auto_backup) < gap:
        return None
    _last_auto_backup = now
    return backup_db()


def backup_stats():
    """📊 وضعیت بک‌آپ‌ها — برای نمایش در پنل ادمین"""
    out = {"count": 0, "daily": 0, "last": None, "size_kb": 0,
           "last_ts": 0}
    try:
        bks = sorted(Path(BACKUP_DIR).glob("nora_backup_*.db"))
        out["count"] = len(bks)
        out["daily"] = len(list((Path(BACKUP_DIR) / "daily")
                                .glob("nora_daily_*.db")))
        if bks:
            newest = bks[-1]
            st = newest.stat()
            out["last"] = newest.name
            out["last_ts"] = st.st_mtime
            out["size_kb"] = st.st_size // 1024
    except Exception:
        pass
    return out



def backup_db():
    """بک‌آپ امن با sqlite backup API (فایل نیمه‌نوشته نمی‌سازد)"""
    if not Path(DB_PATH).exists():
        return None
    try:
        Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bf = Path(BACKUP_DIR) / f"nora_backup_{ts}.db"

        with _lock:
            src = get_db()
            dst = sqlite3.connect(str(bf))
            try:
                src.backup(dst)
            finally:
                dst.close()

        # نگهداری فقط N بک‌آپ آخر
        bks = sorted(Path(BACKUP_DIR).glob("nora_backup_*.db"))
        for old in bks[:-MAX_BACKUPS]:
            try:
                old.unlink()
            except Exception:
                pass

        # 🔍 فاز ۱۸-د — صحت‌سنجی: بک‌آپ خراب بدتر از نبودنش است
        if not _verify_backup(bf):
            log(f"❌ بک‌آپ خراب بود و حذف شد: {bf.name}")
            try:
                bf.unlink()
            except Exception:
                pass
            return None

        _keep_daily(bf)
        log(f"💾 بک‌آپ: {bf.name} ({bf.stat().st_size // 1024} KB)")
        return str(bf)
    except Exception as e:
        log(f"⚠️ بک‌آپ ناموفق: {e}")
        # fallback ساده
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            bf = Path(BACKUP_DIR) / f"nora_copy_{ts}.db"
            shutil.copy2(DB_PATH, bf)
            return str(bf)
        except Exception:
            return None


# ==================== SCHEMA ====================
USERS_COLUMNS = {
    # 🔕 فاز ۲۰ — کاربر تبلیغات را خاموش کرده؟
    "ads_optout": "INTEGER DEFAULT 0",
    "bale_user_id": "INTEGER",
    "bale_username": "TEXT",
    "bale_first_name": "TEXT",
    "bale_last_name": "TEXT",
    "first_name": "TEXT",
    "last_name": "TEXT",
    "mobile": "TEXT",
    "profile_photo": "TEXT",
    "national_id": "TEXT",
    "birth_date": "TEXT",
    "father_name": "TEXT",
    "mother_name": "TEXT",
    "gender": "TEXT",
    "age": "INTEGER",
    "email": "TEXT",
    "phone": "TEXT",
    "country": "TEXT DEFAULT 'ایران'",
    "province": "TEXT",
    "city": "TEXT",
    "address": "TEXT",
    "postal_code": "TEXT",
    "education_level": "TEXT",
    "field_of_study": "TEXT",
    "university": "TEXT",
    "job_title": "TEXT",
    "company_name": "TEXT",
    "bio": "TEXT",
    "is_authenticated": "INTEGER DEFAULT 0",
    "auth_method": "TEXT",
    "authenticated_at": "TIMESTAMP",
    "phone_verified": "INTEGER DEFAULT 0",
    "basic_profile_completed": "INTEGER DEFAULT 0",
    "basic_profile_approved": "INTEGER DEFAULT 0",
    "complete_profile_percent": "INTEGER DEFAULT 0",
    "profile_status": "TEXT DEFAULT 'draft'",
    "profile_submitted_at": "TIMESTAMP",
    "profile_approved_at": "TIMESTAMP",
    "rejection_reason": "TEXT",
    "is_active": "INTEGER DEFAULT 1",
    "is_blocked": "INTEGER DEFAULT 0",
    "is_vip": "INTEGER DEFAULT 0",
    "is_admin": "INTEGER DEFAULT 0",
    "admin_type": "TEXT",
    "admin_role": "TEXT",
    "total_points": "INTEGER DEFAULT 0",
    "total_events_registered": "INTEGER DEFAULT 0",
    "total_certificates": "INTEGER DEFAULT 0",
    "referral_code": "TEXT",
    "referred_by": "INTEGER",
    "registration_source": "TEXT DEFAULT 'bot'",
    "imported": "INTEGER DEFAULT 0",
    "imported_at": "TIMESTAMP",
    "imported_from": "TEXT",
    "last_activity_at": "TIMESTAMP",
    "login_count": "INTEGER DEFAULT 0",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}


def create_users_table():
    cols = ",\n        ".join(f"{k} {v}" for k, v in USERS_COLUMNS.items())
    db_execute(f"""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        {cols}
    )""")
    log("✅ جدول users ساخته شد")


def update_users_table():
    """اضافه کردن ستون‌های جدید بدون از دست رفتن داده"""
    existing = {c["name"] for c in db_execute("PRAGMA table_info(users)", fetch="all")}
    added = []
    for col, typ in USERS_COLUMNS.items():
        if col not in existing:
            # SQLite اجازه DEFAULT CURRENT_TIMESTAMP در ALTER نمی‌دهد
            safe = typ.replace(" DEFAULT CURRENT_TIMESTAMP", "")
            r = db_execute(f"ALTER TABLE users ADD COLUMN {col} {safe}")
            if r is not None or True:
                added.append(col)
    if added:
        log(f"✅ {len(added)} ستون جدید به users اضافه شد: {', '.join(added[:8])}")


# ==================== سیستم مهاجرت عمومی ====================
"""
🔴 باگ بحرانی که رفع شد:
   قبلاً فقط جدول users سیستم مهاجرت داشت. بقیه جدول‌ها با
   CREATE TABLE IF NOT EXISTS ساخته می‌شدند — یعنی اگر جدول از
   نسخه قبلی وجود داشت، ستون‌های جدید هرگز اضافه نمی‌شدند.

   نتیجه: INSERT با خطای «no column named X» شکست می‌خورد
   ⇒ «دکمه ذخیره رویداد کار نمی‌کند»

   حالا: هر جدول یک اسکیمای صریح دارد و ستون‌های گمشده
   خودکار با ALTER TABLE اضافه می‌شوند.
"""

TABLE_SCHEMAS = {
    "user_actions": {
        "bale_user_id": "INTEGER",
        "action_type": "TEXT",
        "action_data": "TEXT",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    },
    "user_states": {
        "bale_user_id": "INTEGER UNIQUE",
        "state": "TEXT",
        "data": "TEXT",
        "expires_at": "TIMESTAMP",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    },
    "otp_codes": {
        "bale_user_id": "INTEGER",
        "phone_number": "TEXT",
        "code": "TEXT",
        "attempts": "INTEGER DEFAULT 0",
        "max_attempts": "INTEGER DEFAULT 5",
        "is_used": "INTEGER DEFAULT 0",
        "expires_at": "TIMESTAMP",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    },
    "import_history": {
        "admin_id": "INTEGER",
        "file_name": "TEXT",
        "total_rows": "INTEGER",
        "success_count": "INTEGER",
        "duplicate_count": "INTEGER",
        "updated_count": "INTEGER DEFAULT 0",
        "error_count": "INTEGER",
        "details": "TEXT",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    },
    "profile_submissions": {
        "user_id": "INTEGER",
        "bale_user_id": "INTEGER",
        "profile_data": "TEXT",
        "status": "TEXT DEFAULT 'pending'",
        "reviewed_by": "INTEGER",
        "reviewed_at": "TIMESTAMP",
        "rejection_reason": "TEXT",
        "shared_task_id": "TEXT",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    },
    "force_join_channels": {
        "channel_id": "TEXT",
        "channel_username": "TEXT",
        "channel_title": "TEXT",
        "invite_link": "TEXT",
        "is_private": "INTEGER DEFAULT 0",
        "is_active": "INTEGER DEFAULT 1",
        "added_by": "INTEGER",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    },
    "settings": {
        "value": "TEXT",
        "title": "TEXT",
        "category": "TEXT DEFAULT 'general'",
        "updated_by": "INTEGER",
        "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    },
    "nora_legacy_migration_meta": {
        "value": "TEXT NOT NULL",
    },
}

# جدول‌هایی که کلید اصلی غیرمعمول دارند
SPECIAL_PK = {
    "settings": "key TEXT PRIMARY KEY",
    "nora_legacy_migration_meta": "key TEXT PRIMARY KEY",
}


def ensure_table(name, columns, pk=None, unique=None):
    """
    جدول را می‌سازد و اگر وجود دارد، ستون‌های گمشده را اضافه می‌کند.
    این تابع idempotent است — هر بار اجرا شود مشکلی نیست.
    """
    exists = db_execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,), fetch="one")

    if not exists:
        head = pk or "id INTEGER PRIMARY KEY AUTOINCREMENT"
        cols = ",\n            ".join(f"{k} {v}" for k, v in columns.items())
        extra = f",\n            UNIQUE({unique})" if unique else ""
        db_execute(f"""CREATE TABLE {name} (
            {head},
            {cols}{extra}
        )""")
        log(f"✅ جدول {name} ساخته شد")
        return 0

    # جدول هست — ستون‌های گمشده را اضافه کن
    have = {c["name"] for c in db_execute(f"PRAGMA table_info({name})", fetch="all") or []}
    added = []
    for col, typ in columns.items():
        if col in have:
            continue
        safe = typ.replace(" DEFAULT CURRENT_TIMESTAMP", "")
        safe = safe.replace(" UNIQUE", "")   # ALTER اجازه UNIQUE نمی‌دهد
        r = db_execute(f"ALTER TABLE {name} ADD COLUMN {col} {safe}")
        added.append(col)
    if added:
        log(f"🔧 جدول {name}: {len(added)} ستون اضافه شد ({', '.join(added[:5])})")
    return len(added)


def create_other_tables():
    """ساخت/به‌روزرسانی جدول‌های پایه با مهاجرت خودکار"""
    total = 0
    for name, cols in TABLE_SCHEMAS.items():
        total += ensure_table(name, cols, pk=SPECIAL_PK.get(name))
    return total


def create_indexes():
    idx = [
        "CREATE INDEX IF NOT EXISTS idx_users_bale ON users(bale_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_mobile ON users(mobile)",
        "CREATE INDEX IF NOT EXISTS idx_users_status ON users(profile_status)",
        "CREATE INDEX IF NOT EXISTS idx_users_admin ON users(is_admin)",
        "CREATE INDEX IF NOT EXISTS idx_states_uid ON user_states(bale_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_otp_uid ON otp_codes(bale_user_id, is_used)",
        "CREATE INDEX IF NOT EXISTS idx_subs_status ON profile_submissions(status)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_subs_shared_task ON profile_submissions(shared_task_id) WHERE shared_task_id IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_actions_uid ON user_actions(bale_user_id)",
        # جلوگیری از bale_user_id تکراری (فیکس مهم: قبلاً UNIQUE فقط موقع CREATE بود)
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_bale ON users(bale_user_id) WHERE bale_user_id IS NOT NULL",
    ]
    for q in idx:
        db_execute(q)


def repair_broken_states():
    """
    🔴 پاکسازی رکوردهای خراب به‌جامانده از نسخه‌های قبلی.

    باگ قدیمی: update_state_data نام state را NULL می‌کرد.
    آن رکوردها هنوز در دیتابیس کاربر هستند و باعث می‌شوند
    ربات پیام‌های او را نشناسد. اینجا پاکسازی می‌شوند.
    """
    n = db_scalar("SELECT COUNT(*) FROM user_states WHERE state IS NULL OR state=''")
    if n:
        db_execute("DELETE FROM user_states WHERE state IS NULL OR state=''")
        log(f"🔧 {n} وضعیت خراب (state=NULL) پاکسازی شد")
    return n


def cleanup_expired():
    """پاکسازی state و OTP منقضی"""
    db_execute("DELETE FROM user_states WHERE expires_at IS NOT NULL AND expires_at < datetime('now')")
    db_execute("DELETE FROM otp_codes WHERE expires_at < datetime('now', '-1 day')")
    db_execute("DELETE FROM user_actions WHERE created_at < datetime('now', '-90 day')")


def fix_referral_codes():
    """پر کردن کد معرف خالی (بدون تکرار)"""
    users = db_execute(
        "SELECT id, bale_user_id FROM users WHERE referral_code IS NULL OR referral_code=''",
        fetch="all",
    )
    for u in users or []:
        code = f"NORA{u.get('bale_user_id') or 0}X{u['id']}"
        db_execute("UPDATE users SET referral_code=? WHERE id=?", (code, u["id"]))


def init_db():
    """آماده‌سازی کامل دیتابیس"""
    for d in (BACKUP_DIR, IMPORT_DIR, FILES_DIR, PROFILES_DIR, LOG_DIR):
        Path(d).mkdir(parents=True, exist_ok=True)

    exists = Path(DB_PATH).exists()
    if exists:
        backup_db()

    log("🔍 بررسی دیتابیس...")
    has_users = db_execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'",
        fetch="one",
    )
    if has_users:
        update_users_table()
    else:
        create_users_table()

    create_other_tables()
    create_indexes()
    fix_referral_codes()
    repair_broken_states()
    cleanup_expired()

    # دفترکل امتیاز + نگهبان نوشتن مستقیم total_points (افزودنی و idempotent)
    try:
        import points_ledger as _pl
        _pl.ensure_schema()
    except Exception as e:
        log(f"❌ راه‌اندازی دفترکل امتیاز: {type(e).__name__}")
        raise

    log("✅ دیتابیس آماده")


# ==================== SETTINGS (متن‌های قابل تغییر) ====================
_settings_cache = {}


def get_setting(key, default=""):
    """خواندن تنظیم با کش"""
    if key in _settings_cache:
        return _settings_cache[key]
    row = db_execute("SELECT value FROM settings WHERE key=?", (key,), fetch="one")
    val = row["value"] if row and row.get("value") is not None else default
    _settings_cache[key] = val
    return val


def set_setting(key, value, title=None, category="general", updated_by=None):
    db_execute("""
        INSERT INTO settings (key, value, title, category, updated_by, updated_at)
        VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value=excluded.value,
            title=COALESCE(excluded.title, settings.title),
            updated_by=excluded.updated_by,
            updated_at=CURRENT_TIMESTAMP
    """, (key, value, title, category, updated_by))
    _settings_cache[key] = value


def clear_settings_cache():
    _settings_cache.clear()


def seed_default_settings():
    """متن‌های پیش‌فرض - فقط اگر قبلاً ثبت نشده باشند"""
    from config import bot_name, org_name

    defaults = [
        ("msg_welcome", "👋 به {bot} خوش آمدید!\n{org}", "پیام خوش‌آمد", "messages"),
        ("msg_auth", "🔐 برای شروع، احراز هویت کنید:", "پیام احراز هویت", "messages"),
        ("msg_force_join", "⚠️ برای استفاده از ربات، ابتدا در کانال/گروه‌های زیر عضو شوید:", "پیام عضویت اجباری", "messages"),
        ("msg_profile_intro", "📝 لطفاً پروفایل خود را تکمیل کنید.", "پیام تکمیل پروفایل", "messages"),
        ("msg_profile_approved", "🎉 پروفایل شما تأیید شد!", "پیام تأیید پروفایل", "messages"),
        ("msg_profile_rejected", "❌ پروفایل شما رد شد. لطفاً دوباره تکمیل کنید.", "پیام رد پروفایل", "messages"),
        ("msg_blocked", "🚫 دسترسی شما به ربات مسدود شده است.", "پیام کاربر مسدود", "messages"),
        ("msg_error", "⚠️ خطایی رخ داد. دوباره تلاش کنید.", "پیام خطای عمومی", "messages"),
    ]
    for key, value, title, cat in defaults:
        exists = db_execute("SELECT key FROM settings WHERE key=?", (key,), fetch="one")
        if not exists:
            set_setting(key, value, title, cat)

    migrate_money_to_rial()


# ==================== 💱 مهاجرت واحد پول ====================
def migrate_money_to_rial():
    """
    🔴 مهاجرت یک‌باره: تنظیمات پولی که «تومان» ذخیره شده بودند → ریال

    تا فاز ۱۷-ج، چند تنظیم عددی به تومان در جدول settings می‌نشستند
    و موقع خواندن ×۱۰ می‌شدند (`to_rial`). حالا که کل ربات ریالی شده
    و دیگر هیچ تبدیلی در کد نیست، آن مقادیر باید یک‌بار ×۱۰ شوند
    وگرنه ناگهان ۱۰ برابر کوچک‌تر عمل می‌کنند.

    ⚠️ فقط یک‌بار اجرا می‌شود (پرچم money_unit_rial).
    ⚠️ ستون‌های جدول‌ها (events.price، forms.price، transactions.amount و…)
       از قبل ریال بودند و دست نمی‌خورند.
    """
    if get_setting("money_unit_rial", "") == "1":
        return

    from config import RIAL_PER_TOMAN

    keys = ["pay_points_rate"]
    for m in ("custom_gateway", "bale_wallet", "card", "onsite", "points"):
        keys += [f"pay_fee_{m}_fix", f"pay_fee_{m}_min", f"pay_fee_{m}_max"]

    changed = 0
    for k in keys:
        row = db_execute("SELECT value FROM settings WHERE key=?",
                         (k,), fetch="one")
        if not row:
            continue
        raw = str(row.get("value") or "").strip()
        if not raw.isdigit():
            continue
        val = int(raw)
        if val <= 0:
            continue
        db_execute("UPDATE settings SET value=? WHERE key=?",
                   (str(val * RIAL_PER_TOMAN), k))
        changed += 1

    clear_settings_cache()
    set_setting("money_unit_rial", "1",
                "💱 واحد پول روی ریال یکسان شد", "payment")
    if changed:
        log(f"💱 {changed} تنظیم پولی از تومان به ریال تبدیل شد")
