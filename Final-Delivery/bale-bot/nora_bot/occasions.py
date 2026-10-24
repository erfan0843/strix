"""
🎂 مناسبت‌ها و تبریک خودکار — فاز ۱۰

  • تبریک تولد خودکار + امتیاز هدیه
  • مناسبت‌های تقویمی (روز دختر، روز مرد، نوروز، ...)
  • فیلتر جنسیت برای مناسبت‌های خاص
  • متن‌های کاملاً قابل ویرایش از پنل ادمین
  • جلوگیری از ارسال تکراری در یک سال
"""
import json
from datetime import datetime

from config import SUPER_ADMIN_ID
from database import db_execute, db_scalar, db_transaction, ensure_table, get_setting, set_setting, log
import points_ledger as pl
from auth import (
    set_state, get_state_data, clear_state, log_action, normalize_digits,
    is_admin as _is_admin,
)
from bale_api import send, send_or_edit, kb_cancel, kb_remove, BTN_BACK
from forms import g2j, jnow, validate_jdatetime
import jalali as _jd

STATE_OC_EDIT = "oc_edit"
STATE_OC_ADD = "oc_add"


# ==================== مناسبت‌های پیش‌فرض ====================
"""
هر مناسبت: (کلید، آیکون، نام، ماه شمسی، روز شمسی، جنسیت هدف، امتیاز)
gender: all / male / female
"""
# 🔴 امتیاز مناسبت‌ها سخت‌گیرانه — تبریک ارزش دارد، نه امتیازش
DEFAULT_OCCASIONS = [
    ("nowruz",      "🌸", "نوروز و سال نو",        1,  1,  "all",    10),
    ("sizdah",      "🌿", "سیزده به در",           1,  13, "all",    0),
    ("mother_day",  "👩", "روز مادر",              11, 20, "female", 5),
    ("father_day",  "👨", "روز پدر",               10, 13, "male",   5),
    ("girl_day",    "🎀", "روز دختر",              7,  10, "female", 5),
    ("boy_day",     "🎽", "روز پسر",               4,  11, "male",   5),
    ("men_day",     "🧔", "روز مرد",               10, 13, "male",   5),
    ("women_day",   "🌷", "روز زن",                11, 20, "female", 5),
    ("teacher_day", "🍎", "روز معلم",              2,  12, "all",    0),
    ("student_day", "🎓", "روز دانشجو",            9,  16, "all",    0),
    ("yalda",       "🍉", "شب یلدا",               9,  30, "all",    5),
    ("ramadan",     "🌙", "آغاز ماه رمضان",        0,  0,  "all",    0),
    ("eid_fitr",    "🕌", "عید فطر",               0,  0,  "all",    10),
    ("quds_day",    "🕊️", "روز قدس",               0,  0,  "all",    0),
]

OCCASION_SCHEMA = {
    "key": "TEXT",
    "icon": "TEXT DEFAULT '🎉'",
    "name": "TEXT NOT NULL",
    "jmonth": "INTEGER DEFAULT 0",
    "jday": "INTEGER DEFAULT 0",
    "gender": "TEXT DEFAULT 'all'",
    "points": "INTEGER DEFAULT 0",
    "message": "TEXT",
    "is_active": "INTEGER DEFAULT 1",
    "is_builtin": "INTEGER DEFAULT 0",
    "last_sent_year": "INTEGER DEFAULT 0",
    "total_sent": "INTEGER DEFAULT 0",
    "created_by": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

# لاگ ارسال — جلوگیری از تبریک تکراری
GREETING_LOG_SCHEMA = {
    "bale_user_id": "INTEGER NOT NULL",
    "kind": "TEXT NOT NULL",          # birthday / occasion / rule
    "ref_key": "TEXT",                 # کلید مناسبت یا قانون
    "jyear": "INTEGER",
    "points_given": "INTEGER DEFAULT 0",
    "sent_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}


# ==================== 🏅 امتیاز شرطی ====================
"""
امتیاز فقط برای تولد نیست — ادمین می‌تواند شرط بگذارد:
«اگر در اولین کارگاه شرکت کنی، ۱۰۰ امتیاز می‌گیری»

هر قانون یک trigger دارد + یک شرط عددی (threshold).
"""
POINT_RULES_SCHEMA = {
    "key": "TEXT",
    "title": "TEXT NOT NULL",
    "trigger": "TEXT NOT NULL",
    "threshold": "INTEGER DEFAULT 1",
    "event_type": "TEXT",
    "points": "INTEGER DEFAULT 0",
    "message": "TEXT",
    "once_only": "INTEGER DEFAULT 1",
    "is_active": "INTEGER DEFAULT 1",
    "total_awarded": "INTEGER DEFAULT 0",
    "created_by": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

# رویدادهایی که می‌توانند امتیاز شرطی بدهند
TRIGGERS = {
    "event_register": {
        "icon": "📝", "name": "ثبت‌نام در رویداد",
        "desc": "وقتی کاربر در رویداد ثبت‌نام کند",
        "unit": "امین ثبت‌نام"},
    "event_attend": {
        "icon": "✋", "name": "حضور در رویداد",
        "desc": "وقتی حضور کاربر تأیید شود",
        "unit": "امین حضور"},
    "workshop_attend": {
        "icon": "🎓", "name": "حضور در کارگاه",
        "desc": "حضور در رویدادی از نوع کارگاه",
        "unit": "امین کارگاه"},
    "form_submit": {
        "icon": "📋", "name": "تکمیل فرم",
        "desc": "وقتی کاربر فرمی را کامل کند",
        "unit": "امین فرم"},
    "profile_complete": {
        "icon": "👤", "name": "تکمیل پروفایل",
        "desc": "وقتی پروفایل به درصد مشخص برسد",
        "unit": "درصد تکمیل"},
    "invite_friend": {
        "icon": "👥", "name": "دعوت دوست",
        "desc": "وقتی دعوت تأییدشده ثبت شود",
        "unit": "امین دعوت"},
    "certificate": {
        "icon": "🎓", "name": "دریافت گواهینامه",
        "desc": "وقتی گواهینامه برای کاربر صادر شود",
        "unit": "امین گواهینامه"},
    "payment_done": {
        "icon": "💳", "name": "پرداخت موفق",
        "desc": "وقتی پرداختی با موفقیت انجام شود",
        "unit": "امین پرداخت"},
}

# 🔴 نظام امتیازدهی سخت‌گیرانه
#
# فلسفه: امتیاز باید «کمیاب» باشد تا ارزش داشته باشد.
#   • حضور واقعی ارزشمندتر از ثبت‌نام صرف است
#   • فقط دستاوردهای معنادار امتیاز می‌گیرند
#   • ثبت‌نام تنها (بدون حضور) امتیازی ندارد
DEFAULT_RULES = [
    ("first_workshop", "🎓 اولین کارگاه", "workshop_attend", 1, 20,
     "در اولین کارگاه شرکت کردی!"),
    ("loyal_5", "🏅 پنج حضور", "event_attend", 5, 30,
     "در ۵ رویداد حاضر شدی؛ عالیه!"),
    ("loyal_15", "🎖️ پانزده حضور", "event_attend", 15, 75,
     "۱۵ بار حضور — از اعضای وفادار ما هستی!"),
    ("profile_100", "👤 پروفایل کامل", "profile_complete", 100, 10,
     "پروفایلت را کامل کردی."),
    ("inviter_5", "🌟 پنج دعوت", "invite_friend", 5, 25,
     "۵ نفر را به جمع ما دعوت کردی!"),
    ("inviter_20", "💎 بیست دعوت", "invite_friend", 20, 100,
     "۲۰ نفر با دعوت تو به ما پیوستند!"),
]


# ==================== متن‌های قابل ویرایش ====================
OCCASION_TEXTS = [
    ("oc_txt_birthday", "🎂 پیام تبریک تولد",
     "🎂🎈 تولدت مبارک {dear}! 🎈🎂\n"
     "━━━━━━━━━━━━━━\n\n"
     "امروز روز خاصیه، چون روز توئه! 🌟\n\n"
     "آرزو می‌کنیم سال تازه زندگیت پر باشه از\n"
     "لبخند، سلامتی و آرزوهایی که برآورده می‌شن. 💐\n\n"
     "🎁 {points} امتیاز هدیه تولد تقدیم شما شد!\n\n"
     "با مهر و احترام 💚\n{org}"),

    ("oc_txt_occasion", "🎉 پیام مناسبت عمومی",
     "{icon} {occasion} بر شما مبارک، {dear}! {icon}\n"
     "━━━━━━━━━━━━━━\n\n"
     "{custom}\n\n"
     "🎁 به همین مناسبت {points} امتیاز تقدیم شما شد.\n\n"
     "با آرزوی بهترین‌ها 💚\n{org}"),

    ("oc_txt_no_points", "🎉 پیام مناسبت بدون امتیاز",
     "{icon} {occasion} بر شما مبارک، {dear}! {icon}\n"
     "━━━━━━━━━━━━━━\n\n"
     "{custom}\n\n"
     "با آرزوی بهترین‌ها 💚\n{org}"),

    ("oc_txt_cond_points", "🏅 پیام امتیاز شرطی",
     "🏅 آفرین {dear}!\n"
     "━━━━━━━━━━━━━━\n\n"
     "{reason}\n\n"
     "🎁 {points} امتیاز به حساب شما اضافه شد.\n"
     "🏆 مجموع امتیاز شما: {total}\n\n"
     "به همین روال ادامه بده 💪\n{org}"),
]

# 🌸 پیام‌های شیرین متنوع — هر بار یکی تصادفی انتخاب می‌شود
BIRTHDAY_WISHES = [
    "امروز روز خاصیه، چون روز توئه! 🌟",
    "یک سال دیگر از قصه قشنگ زندگیت ورق خورد. 📖",
    "امیدواریم امسال بهترین سال زندگیت باشه. 🌈",
    "تولدت مبارک؛ شادی‌هات بی‌پایان باشه. 🎊",
]


def seed_occasion_texts():
    for key, title, default in OCCASION_TEXTS:
        if not db_execute("SELECT key FROM settings WHERE key=?", (key,), fetch="one"):
            set_setting(key, default, title, "occasions")


def render(key, **kw):
    """جایگزینی متغیرها — هرگز KeyError نمی‌دهد"""
    from config import org_name, bot_name
    default = next((d for k, t, d in OCCASION_TEXTS if k == key), "")
    txt = get_setting(key, default) or default
    kw.setdefault("org", org_name())
    kw.setdefault("bot", bot_name())
    kw.setdefault("custom", "")
    kw.setdefault("dear", "دوست عزیز")
    kw.setdefault("wish", "")
    kw.setdefault("reason", "")
    kw.setdefault("total", 0)
    try:
        return txt.format(**kw)
    except (KeyError, IndexError, ValueError):
        out = txt
        for k, v in kw.items():
            out = out.replace("{" + k + "}", str(v))
        return out


# ==================== راه‌اندازی ====================
def init_occasion_tables():
    ensure_table("occasions", OCCASION_SCHEMA)
    ensure_table("greeting_log", GREETING_LOG_SCHEMA)
    ensure_table("point_rules", POINT_RULES_SCHEMA)
    db_execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_rule_key ON point_rules(key) "
               "WHERE key IS NOT NULL AND key<>''")
    for key, title, trg, thr, pts, msgt in DEFAULT_RULES:
        if not db_execute("SELECT id FROM point_rules WHERE key=?", (key,),
                          fetch="one"):
            db_execute("""INSERT INTO point_rules
                (key, title, trigger, threshold, points, message, is_active)
                VALUES (?,?,?,?,?,?,1)""", (key, title, trg, thr, pts, msgt))
    for q in [
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_oc_key ON occasions(key) "
        "WHERE key IS NOT NULL AND key<>''",
        "CREATE INDEX IF NOT EXISTS idx_greet_user ON greeting_log(bale_user_id, kind)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_greet ON greeting_log"
        "(bale_user_id, kind, ref_key, jyear)",
    ]:
        db_execute(q)

    # مناسبت‌های پیش‌فرض
    for key, icon, name, jm, jd, gender, pts in DEFAULT_OCCASIONS:
        if not db_execute("SELECT id FROM occasions WHERE key=?", (key,), fetch="one"):
            db_execute("""INSERT INTO occasions
                (key, icon, name, jmonth, jday, gender, points, is_builtin, is_active)
                VALUES (?,?,?,?,?,?,?,1,?)""",
                (key, icon, name, jm, jd, gender, pts, 1 if jm else 0))

    seed_occasion_texts()
    log("✅ جدول‌های مناسبت آماده شد")


def _guard(cid, uid):
    if not _is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    return True


def get_occasion(oid):
    """
    خواندن امن مناسبت — با ورودی خراب (None، 'abc'، خالی) کرش نمی‌کند.

    ⚠️ روتر وقتی عدد را نتواند بخواند None می‌دهد؛
       بدون این محافظ int(None) خطا می‌داد.
    """
    try:
        n = int(oid)
    except (TypeError, ValueError):
        return None
    return db_execute("SELECT * FROM occasions WHERE id=?", (n,), fetch="one")


def today_jalali():
    """(سال، ماه، روز) شمسی امروز"""
    g = datetime.now()
    return g2j(g.year, g.month, g.day)


# ==================== موتور ارسال ====================
def _already_sent(uid, kind, ref_key, jyear):
    return bool(db_execute(
        "SELECT id FROM greeting_log WHERE bale_user_id=? AND kind=? "
        "AND ref_key=? AND jyear=?", (uid, kind, ref_key or "", jyear), fetch="one"))


def _mark_sent(uid, kind, ref_key, jyear, points):
    """ثبت ارسال تبریک؛ شناسهٔ ردیف greeting_log را برمی‌گرداند (موجود یا تازه)."""
    db_execute("""INSERT OR IGNORE INTO greeting_log
        (bale_user_id, kind, ref_key, jyear, points_given) VALUES (?,?,?,?,?)""",
        (uid, kind, ref_key or "", jyear, points))
    # lastrowid پس از INSERT OR IGNORE قابل اتکا نیست؛ شناسه را صریح می‌خوانیم
    return (db_execute("SELECT id FROM greeting_log WHERE bale_user_id=? AND kind=? "
                       "AND ref_key=? AND jyear=?", (uid, kind, ref_key or "", jyear),
                       fetch="one") or {}).get("id")


# ==================== 🔴 سیاست سخت‌گیرانه امتیاز ====================
"""
امتیاز باید کمیاب باشد تا ارزش داشته باشد.

سقف‌ها از تنظیمات قابل تغییرند ولی پیش‌فرض سخت‌گیرانه است:
  • هر امتیاز واحد حداکثر ۱۰۰
  • هر کاربر حداکثر ۵۰ امتیاز در روز
  • مجموع امتیاز قابل کسب در ماه: ۳۰۰
"""
POINTS_MAX_SINGLE = 100
POINTS_MAX_DAILY = 50
POINTS_MAX_MONTHLY = 300


def points_earned(uid, days=1):
    """امتیاز کسب‌شده در N روز اخیر"""
    return db_scalar(
        f"""SELECT COALESCE(SUM(points_given),0) FROM greeting_log
        WHERE bale_user_id=? AND sent_at >= datetime('now','-{int(days)} days')""",
        (uid,)) or 0


def cap_points(uid, points):
    """
    اعمال سقف‌های سخت‌گیرانه.
    خروجی: (امتیاز مجاز، دلیل کاهش)
    """
    p = int(points or 0)
    if p <= 0:
        return 0, ""

    mx = int(get_setting("points_max_single", str(POINTS_MAX_SINGLE)) or 0)
    if mx and p > mx:
        p = mx

    daily_cap = int(get_setting("points_max_daily", str(POINTS_MAX_DAILY)) or 0)
    if daily_cap:
        used = points_earned(uid, 1)
        if used >= daily_cap:
            return 0, "سقف روزانه امتیاز پر شده"
        p = min(p, daily_cap - used)

    monthly_cap = int(get_setting("points_max_monthly",
                                  str(POINTS_MAX_MONTHLY)) or 0)
    if monthly_cap:
        used_m = points_earned(uid, 30)
        if used_m >= monthly_cap:
            return 0, "سقف ماهانه امتیاز پر شده"
        p = min(p, monthly_cap - used_m)

    return max(0, p), ""


def _give_points(uid, points, *, source, ref_key, ref_id=None, reason=""):
    """اعطای امتیاز تبریک/قانون از طریق دفترکل؛ کلید = همان رویداد تجاری.

    خروجی: True اگر ردیف تازه ثبت شد (تکرار → False، بدون تغییر موجودی).
    """
    try:
        points = int(points or 0)
    except (TypeError, ValueError):
        points = 0
    if points <= 0:
        return False
    res = pl.post_points(uid, points, entry_type="award", source=source, ref_key=ref_key,
                         ref_table="greeting_log", ref_id=ref_id, reason=reason)
    return res.created


def _user_name(u):
    n = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip()
    return n or "دوست عزیز"


def polite_name(u):
    """
    🌸 خطاب مودبانه و صمیمی: «اسم کوچک + عزیز / خانم»

      مرد  → «علی عزیز»
      زن   → «سارا خانم»
      نامشخص → «علی عزیز»  (خنثی و محترمانه)
      بی‌نام → «دوست عزیز»
    """
    first = (u.get("first_name") or "").strip()
    # اگر نام کامل در first_name آمده، فقط بخش اول را بردار
    if first:
        first = first.split()[0]
    if not first:
        return "دوست عزیز"

    g = (u.get("gender") or "").strip()
    if g in ("زن", "female", "خانم"):
        return f"{first} خانم"
    return f"{first} عزیز"


# ==================== 🏅 موتور امتیاز شرطی ====================
def _rule_progress(uid, trigger, event_type=None):
    """پیشرفت فعلی کاربر برای یک trigger"""
    try:
        if trigger == "event_register":
            return db_scalar("""SELECT COUNT(*) FROM event_registrations
                WHERE bale_user_id=? AND status IN ('confirmed','attended')""", (uid,))
        if trigger == "event_attend":
            return db_scalar("""SELECT COUNT(*) FROM event_registrations
                WHERE bale_user_id=? AND attended=1""", (uid,))
        if trigger == "workshop_attend":
            return db_scalar("""SELECT COUNT(*) FROM event_registrations r
                JOIN events e ON e.id=r.event_id
                WHERE r.bale_user_id=? AND r.attended=1
                  AND e.event_type=?""", (uid, event_type or "workshop"))
        if trigger == "form_submit":
            return db_scalar("""SELECT COUNT(*) FROM form_responses
                WHERE bale_user_id=? AND status IN ('completed','confirmed')""", (uid,))
        if trigger == "profile_complete":
            row = db_execute("SELECT complete_profile_percent FROM users "
                             "WHERE bale_user_id=?", (uid,), fetch="one")
            return int((row or {}).get("complete_profile_percent") or 0)
        if trigger == "invite_friend":
            return db_scalar("""SELECT COUNT(*) FROM users
                WHERE referred_by=? AND is_authenticated=1
                  AND COALESCE(complete_profile_percent,0) >= 30""", (uid,))
        if trigger == "certificate":
            return db_scalar("SELECT COUNT(*) FROM certificates "
                             "WHERE bale_user_id=?", (uid,))
        if trigger == "payment_done":
            return db_scalar("""SELECT COUNT(*) FROM transactions
                WHERE bale_user_id=? AND status IN ('paid','confirmed','success')""",
                (uid,))
    except Exception as e:
        log(f"⚠️ محاسبه پیشرفت قانون: {e}")
    return 0


def check_point_rules(uid, trigger=None, silent=False):
    """
    🏅 بررسی قوانین امتیاز شرطی و اعطای امتیاز.

    بعد از هر رویداد مهم (ثبت‌نام، حضور، فرم، دعوت) صدا زده می‌شود.
    خروجی: (تعداد قانون اجراشده، مجموع امتیاز داده‌شده)
    """
    if get_setting("rules_enabled", "1") != "1":
        return 0, 0

    where = "is_active=1"
    params = []
    if trigger:
        where += " AND trigger=?"
        params.append(trigger)
    rules = db_execute(f"SELECT * FROM point_rules WHERE {where}",
                       tuple(params), fetch="all") or []
    if not rules:
        return 0, 0

    u = db_execute("SELECT * FROM users WHERE bale_user_id=?", (uid,), fetch="one")
    if not u:
        return 0, 0

    n_fired = total_pts = 0
    for r in rules:
        key = r.get("key") or f"rule{r['id']}"
        # یک‌بار مصرف؟
        if r.get("once_only", 1) and db_execute(
                "SELECT id FROM greeting_log WHERE bale_user_id=? AND kind='rule' "
                "AND ref_key=?", (uid, key), fetch="one"):
            continue

        need = int(r.get("threshold") or 1)
        have = _rule_progress(uid, r.get("trigger"), r.get("event_type"))
        if have < need:
            continue

        pts, capped_why = cap_points(uid, r.get("points"))
        if capped_why:
            log(f"🔴 سقف امتیاز: {uid} — {capped_why}")
        # کلید دفترکل: قانون یک‌بارمصرف = (قانون، کاربر)؛ قانون تکرارشونده =
        # (قانون، کاربر، شمارهٔ پیشرفتی که آن را فعال کرد) تا تکرار همان رخداد دو بار نشمرد
        lkey = f"rule:{uid}:{key}" if r.get("once_only", 1) else f"rule:{uid}:{key}:n{have}"
        try:
            with db_transaction():
                gl = _mark_sent(uid, "rule", key, 0, pts)
                created = _give_points(uid, pts, source="point_rule", ref_key=lkey, ref_id=gl,
                                       reason=f"قانون امتیاز {key}")
                if created or not pts:
                    db_execute("UPDATE point_rules SET total_awarded="
                               "COALESCE(total_awarded,0)+1 WHERE id=?", (r["id"],))
        except pl.LedgerError as e:
            log(f"❌ امتیاز قانون {key} برای {uid}: {e.code}")
            continue
        pl.sync_pending(limit=5)

        if not silent and pts:
            fresh = db_execute("SELECT total_points FROM users WHERE bale_user_id=?",
                               (uid,), fetch="one") or {}
            txt = render("oc_txt_cond_points",
                         dear=polite_name(u), name=_user_name(u),
                         reason=r.get("message") or r.get("title") or "",
                         points=pts, total=int(fresh.get("total_points") or 0))
            try:
                send(uid, txt)
            except Exception as e:
                log(f"⚠️ ارسال امتیاز شرطی: {e}")

        log_action(uid, "point_rule", {"rule": key, "points": pts})
        n_fired += 1
        total_pts += pts
    return n_fired, total_pts


def check_birthdays(dry_run=False):
    """
    🎂 تبریک تولد — کاربرانی که امروز تولدشان است.
    خروجی: (تعداد ارسال، لیست نام‌ها)
    """
    if get_setting("oc_birthday_enabled", "1") != "1":
        return 0, []

    jy, jm, jd = today_jalali()
    points = int(get_setting("oc_birthday_points", "15") or 0)

    rows = db_execute("""SELECT bale_user_id, first_name, last_name, gender, birth_date
        FROM users WHERE bale_user_id IS NOT NULL
          AND birth_date IS NOT NULL AND birth_date<>''
          AND (is_blocked IS NULL OR is_blocked=0)""", fetch="all") or []

    sent, names = 0, []
    for u in rows:
        bd = normalize_digits(str(u.get("birth_date") or "")).replace("-", "/")
        parts = bd.split("/")
        if len(parts) != 3:
            continue
        try:
            bm, bdd = int(parts[1]), int(parts[2])
        except (ValueError, TypeError):
            continue
        if bm != jm or bdd != jd:
            continue

        uid = u["bale_user_id"]
        if _already_sent(uid, "birthday", "", jy):
            continue
        if dry_run:
            sent += 1
            names.append(_user_name(u))
            continue

        import random as _r
        pts_b, _ = cap_points(uid, points)
        txt = render("oc_txt_birthday", name=_user_name(u),
                     dear=polite_name(u), points=pts_b,
                     wish=_r.choice(BIRTHDAY_WISHES))
        res = send(uid, txt)
        if res and res.get("ok"):
            try:
                with db_transaction():
                    gl = _mark_sent(uid, "birthday", "", jy, pts_b)
                    _give_points(uid, pts_b, source="birthday", ref_key=f"birthday:{uid}:{jy}",
                                 ref_id=gl, reason=f"تبریک تولد {jy}")
            except pl.LedgerError as e:
                log(f"❌ امتیاز تولد {uid}: {e.code}")
                continue
            log_action(uid, "birthday_greeting", {"points": pts_b})
            sent += 1
            names.append(_user_name(u))
    pl.sync_pending(limit=20)
    return sent, names


def check_occasions(dry_run=False):
    """
    🎉 مناسبت‌های امروز — با فیلتر جنسیت.
    خروجی: (تعداد ارسال، لیست نام مناسبت‌ها)
    """
    if get_setting("oc_enabled", "1") != "1":
        return 0, []

    jy, jm, jd = today_jalali()
    occs = db_execute("""SELECT * FROM occasions WHERE is_active=1
        AND jmonth=? AND jday=?""", (jm, jd), fetch="all") or []

    total, fired = 0, []
    for oc in occs:
        if oc.get("last_sent_year") == jy and not dry_run:
            continue

        gender = (oc.get("gender") or "all").strip()
        where = ["bale_user_id IS NOT NULL", "(is_blocked IS NULL OR is_blocked=0)"]
        params = []
        if gender == "male":
            where.append("gender IN ('مرد','male','آقا')")
        elif gender == "female":
            where.append("gender IN ('زن','female','خانم')")

        rows = db_execute(
            f"SELECT bale_user_id, first_name, last_name, gender FROM users "
            f"WHERE {' AND '.join(where)}", tuple(params), fetch="all") or []

        pts = int(oc.get("points") or 0)
        key = oc.get("key") or f"oc{oc['id']}"
        n = 0
        for u in rows:
            uid = u["bale_user_id"]
            if _already_sent(uid, "occasion", key, jy):
                continue
            if dry_run:
                n += 1
                continue
            tkey = "oc_txt_occasion" if pts else "oc_txt_no_points"
            txt = render(tkey, name=_user_name(u), dear=polite_name(u),
                         occasion=oc["name"],
                         icon=oc.get("icon") or "🎉", points=pts,
                         custom=oc.get("message") or "")
            res = send(uid, txt)
            if res and res.get("ok"):
                pts_c, _ = cap_points(uid, pts)
                try:
                    with db_transaction():
                        gl = _mark_sent(uid, "occasion", key, jy, pts_c)
                        _give_points(uid, pts_c, source="occasion",
                                     ref_key=f"occasion:{uid}:{key}:{jy}", ref_id=gl,
                                     reason=f"مناسبت {key} {jy}")
                except pl.LedgerError as e:
                    log(f"❌ امتیاز مناسبت {key} برای {uid}: {e.code}")
                    continue
                n += 1
        pl.sync_pending(limit=20)

        if n and not dry_run:
            db_execute("UPDATE occasions SET last_sent_year=?, "
                       "total_sent=COALESCE(total_sent,0)+? WHERE id=?",
                       (jy, n, oc["id"]))
        if n:
            total += n
            fired.append(f"{oc.get('icon','🎉')} {oc['name']} ({n} نفر)")
    return total, fired


def run_daily(force=False):
    """
    اجرای روزانه — از حلقه اصلی ربات صدا زده می‌شود.
    فقط یک بار در روز اجرا می‌شود.
    """
    jy, jm, jd = today_jalali()
    stamp = f"{jy:04d}/{jm:02d}/{jd:02d}"
    if not force and get_setting("oc_last_run", "") == stamp:
        return 0, 0

    set_setting("oc_last_run", stamp, "آخرین اجرای مناسبت‌ها", "occasions")
    b, _ = check_birthdays()
    o, _ = check_occasions()
    if b or o:
        log(f"🎉 مناسبت‌ها: {b} تولد، {o} تبریک مناسبتی")
    return b, o


# ==================== پنل ادمین ====================
def show_panel(cid, uid):
    if not _guard(cid, uid):
        return
    jy, jm, jd = today_jalali()
    total = db_scalar("SELECT COUNT(*) FROM occasions")
    active = db_scalar("SELECT COUNT(*) FROM occasions WHERE is_active=1")
    sent = db_scalar("SELECT COUNT(*) FROM greeting_log")
    bday_on = get_setting("oc_birthday_enabled", "1") == "1"
    oc_on = get_setting("oc_enabled", "1") == "1"

    # تولدهای امروز
    nb, names = check_birthdays(dry_run=True)
    no, fired = check_occasions(dry_run=True)

    lines = [
        "🎂 مناسبت‌ها و تبریک خودکار",
        "━━━━━━━━━━━━━━",
        "",
        f"📅 امروز: {jy}/{jm:02d}/{jd:02d}",
        "",
        f"🎂 تبریک تولد: {'✅ فعال' if bday_on else '❌ خاموش'}",
        f"🎉 مناسبت‌ها: {'✅ فعال' if oc_on else '❌ خاموش'}",
        f"📋 مناسبت‌های تعریف‌شده: {total} (فعال: {active})",
        f"📤 مجموع تبریک ارسال‌شده: {sent}",
        "",
    ]
    if nb:
        lines.append(f"🎂 امروز {nb} نفر تولد دارند:")
        for n in names[:5]:
            lines.append(f"   • {n}")
        lines.append("")
    if fired:
        lines.append("🎉 مناسبت امروز:")
        for x in fired:
            lines.append(f"   • {x}")
        lines.append("")
    if not nb and not fired:
        lines.append("📭 امروز تولد یا مناسبتی نیست.")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": f"🎂 تبریک تولد {'✅' if bday_on else '❌'}",
          "callback_data": "oc_tog_birthday"},
         {"text": f"🎉 مناسبت‌ها {'✅' if oc_on else '❌'}",
          "callback_data": "oc_tog_enabled"}],
        [{"text": "📋 لیست مناسبت‌ها", "callback_data": "oc_list"}],
        [{"text": "➕ مناسبت جدید", "callback_data": "oc_add"}],
        [{"text": "🎁 امتیاز تولد", "callback_data": "oc_bpoints"}],
        [{"text": "🏅 امتیازهای شرطی", "callback_data": "pr_list"}],
        [{"text": "📝 متن‌های تبریک", "callback_data": "oc_texts"}],
        [{"text": "▶️ اجرای دستی همین حالا", "callback_data": "oc_run"}],
        [{"text": "📊 تاریخچه ارسال", "callback_data": "oc_history"}],
        [{"text": "🔙 مدیریت کاربران", "callback_data": "admin_users"}],
    ]})


def toggle_flag(cid, uid, key):
    if not _guard(cid, uid):
        return
    skey = "oc_birthday_enabled" if key == "birthday" else "oc_enabled"
    cur = get_setting(skey, "1")
    set_setting(skey, "0" if cur == "1" else "1",
                "تبریک تولد" if key == "birthday" else "مناسبت‌ها",
                "occasions", uid)
    return show_panel(cid, uid)


def show_list(cid, uid, page=0):
    if not _guard(cid, uid):
        return
    rows = db_execute("SELECT * FROM occasions ORDER BY jmonth, jday, id",
                      fetch="all") or []
    if not rows:
        return send_or_edit(cid, "📭 مناسبتی تعریف نشده", {"inline_keyboard": [
            [{"text": "➕ افزودن", "callback_data": "oc_add"}],
            [{"text": "🔙 بازگشت", "callback_data": "oc_panel"}]]})

    per = 8
    pages = max(1, (len(rows) + per - 1) // per)
    page = max(0, min(int(page or 0), pages - 1))
    chunk = rows[page * per:(page + 1) * per]

    gmap = {"all": "👥 همه", "male": "👨 آقایان", "female": "👩 خانم‌ها"}
    lines = [f"📋 مناسبت‌ها ({len(rows)})", "━━━━━━━━━━━━━━", ""]
    btns = []
    for oc in chunk:
        st = "🟢" if oc.get("is_active") else "⚫"
        when = (f"{oc['jmonth']}/{oc['jday']:02d}" if oc.get("jmonth")
                else "— (تاریخ ندارد)")
        lines.append(f"{st} {oc.get('icon','🎉')} {oc['name']}")
        lines.append(f"   📅 {when} | {gmap.get(oc.get('gender'), '👥 همه')}"
                     f" | 🎁 {oc.get('points') or 0} امتیاز")
        btns.append([{"text": f"{st} {oc.get('icon','🎉')} {oc['name'][:28]}",
                      "callback_data": f"oc_v_{oc['id']}"}])

    if pages > 1:
        nav = []
        if page > 0:
            nav.append({"text": "⬅️", "callback_data": f"oc_pg_{page-1}"})
        nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
        if page < pages - 1:
            nav.append({"text": "➡️", "callback_data": f"oc_pg_{page+1}"})
        btns.append(nav)
    btns.append([{"text": "➕ مناسبت جدید", "callback_data": "oc_add"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "oc_panel"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def view_occasion(cid, uid, oid):
    if not _guard(cid, uid):
        return
    oc = get_occasion(oid)
    if not oc:
        return send(cid, "❌ یافت نشد")
    gmap = {"all": "👥 همه", "male": "👨 فقط آقایان", "female": "👩 فقط خانم‌ها"}
    when = f"{oc['jmonth']}/{oc['jday']:02d}" if oc.get("jmonth") else "— تعیین نشده"

    lines = [
        f"{oc.get('icon','🎉')} {oc['name']}",
        "━━━━━━━━━━━━━━", "",
        f"📅 تاریخ: {when} (شمسی)",
        f"👥 گیرندگان: {gmap.get(oc.get('gender'), '👥 همه')}",
        f"🎁 امتیاز: {oc.get('points') or 0}",
        f"📊 وضعیت: {'🟢 فعال' if oc.get('is_active') else '⚫ غیرفعال'}",
        f"📤 ارسال‌شده: {oc.get('total_sent') or 0} بار",
    ]
    if oc.get("message"):
        lines += ["", f"📝 پیام سفارشی:\n{oc['message'][:300]}"]

    btns = [
        [{"text": "📅 تغییر تاریخ", "callback_data": f"oc_date_{oid}"}],
        [{"text": "🎁 تغییر امتیاز", "callback_data": f"oc_pts_{oid}"}],
        [{"text": "👥 گیرندگان", "callback_data": f"oc_gen_{oid}"}],
        [{"text": "📝 پیام سفارشی", "callback_data": f"oc_msg_{oid}"}],
        [{"text": ("⚫ غیرفعال کردن" if oc.get("is_active") else "🟢 فعال کردن"),
          "callback_data": f"oc_tg_{oid}"}],
        [{"text": "🧪 تست (ارسال به خودم)", "callback_data": f"oc_test_{oid}"}],
    ]
    if not oc.get("is_builtin"):
        btns.append([{"text": "🗑️ حذف", "callback_data": f"oc_del_{oid}"}])
    btns.append([{"text": "🔙 لیست", "callback_data": "oc_list"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_occasion(cid, uid, oid):
    if not _guard(cid, uid):
        return
    oc = get_occasion(oid)
    if not oc:
        return send(cid, "❌ یافت نشد")
    db_execute("UPDATE occasions SET is_active=? WHERE id=?",
               (0 if oc.get("is_active") else 1, oc["id"]))
    return view_occasion(cid, uid, oid)


def delete_occasion(cid, uid, oid, confirmed=False):
    if not _guard(cid, uid):
        return
    oc = get_occasion(oid)
    if not oc:
        return send(cid, "❌ یافت نشد")
    if oc.get("is_builtin"):
        send(cid, "⚠️ مناسبت پیش‌فرض حذف نمی‌شود — می‌توانید غیرفعالش کنید")
        return view_occasion(cid, uid, oid)
    if not confirmed:
        return send_or_edit(cid, (
            f"🗑️ حذف «{oc['name']}»؟\n\nاین عمل بازگشت‌پذیر نیست."
        ), {"inline_keyboard": [
            [{"text": "🗑️ بله، حذف کن", "callback_data": f"oc_dely_{oid}"}],
            [{"text": "❌ انصراف", "callback_data": f"oc_v_{oid}"}]]})
    db_execute("DELETE FROM occasions WHERE id=?", (oc["id"],))
    send(cid, "🗑️ حذف شد")
    return show_list(cid, uid, 0)


def show_gender(cid, uid, oid, g=None):
    if not _guard(cid, uid):
        return
    if g is not None:
        if g not in ("all", "male", "female"):
            return send(cid, "❌ نامعتبر")
        if not get_occasion(oid):
            return send(cid, "❌ یافت نشد")
        db_execute("UPDATE occasions SET gender=? WHERE id=?", (g, int(oid)))
        return view_occasion(cid, uid, oid)
    oc = get_occasion(oid)
    if not oc:
        return send(cid, "❌ یافت نشد")
    cur = oc.get("gender") or "all"
    opts = [("all", "👥 همه کاربران"), ("male", "👨 فقط آقایان"),
            ("female", "👩 فقط خانم‌ها")]
    btns = [[{"text": f"{'🔘' if k == cur else '⚪'} {n}",
              "callback_data": f"oc_gens_{k}_{oid}"}] for k, n in opts]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"oc_v_{oid}"}])
    send_or_edit(cid, "👥 این تبریک برای چه کسانی ارسال شود؟",
                 {"inline_keyboard": btns})


# ==================== ورودی‌های متنی ====================
def start_edit(cid, uid, oid, key):
    if not _guard(cid, uid):
        return
    oc = get_occasion(oid)
    if not oc:
        return send(cid, "❌ یافت نشد")

    prompts = {
        "date": ("📅 تاریخ مناسبت",
                 f"فعلی: {oc['jmonth']}/{oc['jday']:02d}\n\n"
                 "ماه و روز شمسی را بنویسید:\n\nمثال: 7/10  (یعنی ۱۰ مهر)"),
        "pts": ("🎁 امتیاز هدیه",
                f"فعلی: {oc.get('points') or 0}\n\nامتیاز جدید (۰ = بدون امتیاز):"),
        "msg": ("📝 پیام سفارشی",
                f"فعلی: {oc.get('message') or '—'}\n\n"
                "متنی که در تبریک اضافه شود:\n\n💡 «-» = حذف"),
    }
    if key not in prompts:
        return send(cid, "❌ نامعتبر")
    title, body = prompts[key]
    set_state(uid, STATE_OC_EDIT, {"oid": int(oid), "key": key}, merge=False)
    send(cid, f"{title}\n━━━━━━━━━━━━━━\n\n{body}", kb_cancel())


def handle_edit(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    data = get_state_data(uid)
    oid = data.get("oid")
    key = data.get("key")

    # 🏅 ویرایش فیلدهای قانون امتیاز
    if key == "rule":
        return handle_rule_field(message)

    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return view_occasion(cid, uid, oid)

    if key == "date":
        t = normalize_digits(text).replace("-", "/").replace(" ", "")
        parts = t.split("/")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            return send(cid, "⚠️ فرمت نامعتبر — مثال: 7/10", kb_cancel())
        m, d = int(parts[0]), int(parts[1])
        if not (1 <= m <= 12 and 1 <= d <= 31):
            return send(cid, "⚠️ ماه ۱ تا ۱۲ و روز ۱ تا ۳۱", kb_cancel())
        if m > 6 and d > 30:
            return send(cid, "⚠️ ماه‌های دوم سال ۳۰ روزه‌اند", kb_cancel())
        clear_state(uid)
        db_execute("UPDATE occasions SET jmonth=?, jday=? WHERE id=?", (m, d, oid))
        send(cid, f"✅ تاریخ: {m}/{d:02d}", kb_remove())
        return view_occasion(cid, uid, oid)

    if key == "pts":
        d = "".join(ch for ch in normalize_digits(text) if ch.isdigit())
        if not d:
            return send(cid, "⚠️ عدد وارد کنید:", kb_cancel())
        clear_state(uid)
        db_execute("UPDATE occasions SET points=? WHERE id=?", (int(d), oid))
        send(cid, f"✅ امتیاز: {int(d)}", kb_remove())
        return view_occasion(cid, uid, oid)

    if key == "msg":
        clear_state(uid)
        val = "" if text == "-" else text[:1000]
        db_execute("UPDATE occasions SET message=? WHERE id=?", (val, oid))
        send(cid, "✅ ذخیره شد", kb_remove())
        return view_occasion(cid, uid, oid)

    clear_state(uid)
    return send(cid, "⚠️ نامعتبر", kb_remove())


def start_add(cid, uid):
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_OC_ADD, {}, merge=False)
    send(cid, (
        "➕ مناسبت جدید\n━━━━━━━━━━━━━━\n\n"
        "در یک خط بنویسید:\n\n"
        "نام | ماه/روز | امتیاز\n\n"
        "مثال:\n"
        "روز کتاب | 8/24 | 20\n\n"
        "💡 تاریخ شمسی است. امتیاز اختیاری."
    ), kb_cancel())


def handle_add(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    if get_state_data(uid).get("mode") == "rule":
        return handle_add_rule(message)

    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_list(cid, uid, 0)

    parts = [p.strip() for p in text.replace("،", "|").split("|")]
    name = parts[0] if parts else ""
    if not name:
        return send(cid, "⚠️ نام مناسبت را بنویسید:", kb_cancel())

    jm = jd = 0
    if len(parts) > 1:
        t = normalize_digits(parts[1]).replace("-", "/").replace(" ", "")
        sub = t.split("/")
        if len(sub) == 2 and all(x.isdigit() for x in sub):
            jm, jd = int(sub[0]), int(sub[1])
    if not (1 <= jm <= 12 and 1 <= jd <= 31):
        return send(cid, "⚠️ تاریخ نامعتبر — مثال: روز کتاب | 8/24 | 20",
                    kb_cancel())

    pts = 0
    if len(parts) > 2:
        d = "".join(ch for ch in normalize_digits(parts[2]) if ch.isdigit())
        pts = int(d) if d else 0

    clear_state(uid)
    oid = db_execute("""INSERT INTO occasions
        (key, icon, name, jmonth, jday, gender, points, is_active, created_by)
        VALUES (?,?,?,?,?, 'all', ?, 1, ?)""",
        (f"custom{int(datetime.now().timestamp())}", "🎉", name[:60],
         jm, jd, pts, uid))
    send(cid, f"✅ «{name}» اضافه شد\n📅 {jm}/{jd:02d}\n🎁 {pts} امتیاز",
         kb_remove())
    return view_occasion(cid, uid, oid) if oid else show_list(cid, uid, 0)


def start_bpoints(cid, uid):
    if not _guard(cid, uid):
        return
    cur = get_setting("oc_birthday_points", "15")
    set_state(uid, STATE_OC_EDIT, {"key": "bpoints"}, merge=False)
    send(cid, (
        f"🎁 امتیاز هدیه تولد\n━━━━━━━━━━━━━━\n\n"
        f"فعلی: {cur}\n\nامتیاز جدید:"
    ), kb_cancel())


def handle_bpoints(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_panel(cid, uid)
    d = "".join(ch for ch in normalize_digits(text) if ch.isdigit())
    if not d:
        return send(cid, "⚠️ عدد وارد کنید:", kb_cancel())
    clear_state(uid)
    set_setting("oc_birthday_points", d, "امتیاز تولد", "occasions", uid)
    send(cid, f"✅ امتیاز تولد: {d}", kb_remove())
    return show_panel(cid, uid)


# ==================== متن‌ها ====================
def show_texts(cid, uid):
    if not _guard(cid, uid):
        return
    lines = ["📝 متن‌های تبریک", "━━━━━━━━━━━━━━", "",
             "متغیرها: {name} {points} {occasion} {icon} {custom} {org}", ""]
    # کلید کوتاه می‌فرستیم تا callback_data دوبار پیشوند نگیرد
    btns = [[{"text": t, "callback_data": "octx_" + k.replace("oc_txt_", "")}]
            for k, t, _ in OCCASION_TEXTS]
    btns.append([{"text": "🔙 بازگشت", "callback_data": "oc_panel"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_edit_text(cid, uid, key):
    if not _guard(cid, uid):
        return
    item = next((x for x in OCCASION_TEXTS if x[0] == key), None)
    if not item:
        return send(cid, "❌ نامعتبر")
    _, title, default = item
    cur = get_setting(key, default)
    set_state(uid, STATE_OC_EDIT, {"key": "text", "tkey": key}, merge=False)
    send(cid, (
        f"{title}\n━━━━━━━━━━━━━━\n\n"
        f"📄 فعلی:\n{cur}\n\n✍️ متن جدید:\n\n💡 «-» = پیش‌فرض"
    ), kb_cancel())


def handle_edit_text(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    data = get_state_data(uid)
    tkey = data.get("tkey")
    clear_state(uid)
    if text in (BTN_BACK, "🔙 بازگشت"):
        send(cid, "❌ لغو شد", kb_remove())
        return show_texts(cid, uid)
    item = next((x for x in OCCASION_TEXTS if x[0] == tkey), None)
    if not item:
        return send(cid, "❌ نامعتبر", kb_remove())
    _, title, default = item
    set_setting(tkey, default if text == "-" else text[:2000],
                title, "occasions", uid)
    send(cid, "✅ ذخیره شد", kb_remove())
    return show_texts(cid, uid)


# ==================== اجرا و تاریخچه ====================
def run_now(cid, uid):
    if not _guard(cid, uid):
        return
    b, o = run_daily(force=True)
    send(cid, (
        f"▶️ اجرا شد\n━━━━━━━━━━━━━━\n\n"
        f"🎂 تبریک تولد: {b}\n"
        f"🎉 تبریک مناسبت: {o}\n\n"
        + ("📭 امروز کسی نبود." if not (b or o) else "✅ ارسال شد.")
    ))
    return show_panel(cid, uid)


def test_occasion(cid, uid, oid):
    """🧪 ارسال تستی به خود ادمین"""
    if not _guard(cid, uid):
        return
    oc = get_occasion(oid)
    if not oc:
        return send(cid, "❌ یافت نشد")
    u = db_execute("SELECT * FROM users WHERE bale_user_id=?", (uid,), fetch="one") or {}
    pts = int(oc.get("points") or 0)
    tkey = "oc_txt_occasion" if pts else "oc_txt_no_points"
    txt = render(tkey, name=_user_name(u), dear=polite_name(u),
                 occasion=oc["name"],
                 icon=oc.get("icon") or "🎉", points=pts,
                 custom=oc.get("message") or "")
    send(cid, "🧪 پیش‌نمایش:\n\n" + txt)
    return view_occasion(cid, uid, oid)


# ==================== 🏅 پنل امتیاز شرطی ====================
def get_rule(rid):
    try:
        return db_execute("SELECT * FROM point_rules WHERE id=?", (int(rid),),
                          fetch="one")
    except (TypeError, ValueError):
        return None


def show_rules(cid, uid, page=0):
    if not _guard(cid, uid):
        return
    rows = db_execute("SELECT * FROM point_rules ORDER BY is_active DESC, id",
                      fetch="all") or []
    on = get_setting("rules_enabled", "1") == "1"
    given = db_scalar("SELECT COALESCE(SUM(points_given),0) FROM greeting_log "
                      "WHERE kind='rule'")

    lines = ["🏅 امتیازهای شرطی", "━━━━━━━━━━━━━━", "",
             f"وضعیت سیستم: {'✅ فعال' if on else '❌ خاموش'}",
             f"🎁 مجموع امتیاز داده‌شده: {given}", "",
             "💡 «اگر در اولین کارگاه شرکت کنی، ۱۰۰ امتیاز می‌گیری»", ""]
    btns = [[{"text": f"{'❌ خاموش کردن' if on else '✅ روشن کردن'} سیستم",
              "callback_data": "pr_toggle_sys"}]]
    if rows:
        for r in rows:
            t = TRIGGERS.get(r.get("trigger"), {})
            st = "🟢" if r.get("is_active") else "⚫"
            lines.append(f"{st} {r['title']}")
            lines.append(f"   {t.get('icon','🎯')} {t.get('name', r.get('trigger'))}"
                         f" ≥ {r.get('threshold')} → 🎁 {r.get('points')} امتیاز"
                         f"  (اجرا: {r.get('total_awarded') or 0})")
            btns.append([{"text": f"{st} {r['title'][:30]}",
                          "callback_data": f"pr_v_{r['id']}"}])
    else:
        lines.append("📭 قانونی تعریف نشده")
    btns.append([{"text": "➕ قانون جدید", "callback_data": "pr_add"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "oc_panel"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_rules_system(cid, uid):
    if not _guard(cid, uid):
        return
    cur = get_setting("rules_enabled", "1")
    set_setting("rules_enabled", "0" if cur == "1" else "1",
                "سیستم امتیاز شرطی", "occasions", uid)
    return show_rules(cid, uid)


def view_rule(cid, uid, rid):
    if not _guard(cid, uid):
        return
    r = get_rule(rid)
    if not r:
        return send(cid, "❌ یافت نشد")
    t = TRIGGERS.get(r.get("trigger"), {})
    lines = [
        f"🏅 {r['title']}", "━━━━━━━━━━━━━━", "",
        f"🎯 شرط: {t.get('icon','')} {t.get('name', r.get('trigger'))}",
        f"📊 حد نصاب: {r.get('threshold')} {t.get('unit', '')}",
        f"🎁 امتیاز: {r.get('points')}",
        f"🔁 تکرار: {'فقط یک بار' if r.get('once_only', 1) else 'هر بار'}",
        f"📈 تا حالا اجرا شده: {r.get('total_awarded') or 0} بار",
        f"📊 وضعیت: {'🟢 فعال' if r.get('is_active') else '⚫ غیرفعال'}",
    ]
    if r.get("message"):
        lines += ["", f"📝 پیام: {r['message']}"]
    if t.get("desc"):
        lines += ["", f"💡 {t['desc']}"]

    btns = [
        [{"text": "🎯 تغییر شرط", "callback_data": f"pr_trg_{rid}"}],
        [{"text": "📊 حد نصاب", "callback_data": f"prn_threshold_{rid}"},
         {"text": "🎁 امتیاز", "callback_data": f"prn_points_{rid}"}],
        [{"text": "✏️ عنوان", "callback_data": f"prt_title_{rid}"},
         {"text": "📝 پیام", "callback_data": f"prt_message_{rid}"}],
        [{"text": f"🔁 تکرار: {'یک بار' if r.get('once_only', 1) else 'هر بار'}",
          "callback_data": f"pr_once_{rid}"}],
        [{"text": ("⚫ غیرفعال کردن" if r.get("is_active") else "🟢 فعال کردن"),
          "callback_data": f"pr_tg_{rid}"}],
        [{"text": "🗑️ حذف", "callback_data": f"pr_del_{rid}"}],
        [{"text": "🔙 لیست", "callback_data": "pr_list"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def pick_trigger(cid, uid, rid, trg=None):
    if not _guard(cid, uid):
        return
    r = get_rule(rid)
    if not r:
        return send(cid, "❌ یافت نشد")
    if trg is not None:
        if trg not in TRIGGERS:
            return send(cid, "❌ نامعتبر")
        db_execute("UPDATE point_rules SET trigger=? WHERE id=?", (trg, r["id"]))
        return view_rule(cid, uid, rid)
    cur = r.get("trigger")
    lines = ["🎯 شرط کسب امتیاز", "━━━━━━━━━━━━━━", ""]
    btns = []
    for k, v in TRIGGERS.items():
        lines.append(f"{v['icon']} {v['name']} — {v['desc']}")
        btns.append([{"text": f"{'🔘' if k == cur else '⚪'} {v['icon']} {v['name']}",
                      "callback_data": f"prtg_{k}_{rid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"pr_v_{rid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_rule(cid, uid, rid):
    if not _guard(cid, uid):
        return
    r = get_rule(rid)
    if not r:
        return send(cid, "❌ یافت نشد")
    db_execute("UPDATE point_rules SET is_active=? WHERE id=?",
               (0 if r.get("is_active") else 1, r["id"]))
    return view_rule(cid, uid, rid)


def toggle_once(cid, uid, rid):
    if not _guard(cid, uid):
        return
    r = get_rule(rid)
    if not r:
        return send(cid, "❌ یافت نشد")
    db_execute("UPDATE point_rules SET once_only=? WHERE id=?",
               (0 if r.get("once_only", 1) else 1, r["id"]))
    return view_rule(cid, uid, rid)


def delete_rule(cid, uid, rid, confirmed=False):
    if not _guard(cid, uid):
        return
    r = get_rule(rid)
    if not r:
        return send(cid, "❌ یافت نشد")
    if not confirmed:
        return send_or_edit(cid, (
            f"🗑️ حذف قانون «{r['title']}»؟\n\nاین عمل بازگشت‌پذیر نیست."
        ), {"inline_keyboard": [
            [{"text": "🗑️ بله، حذف کن", "callback_data": f"pr_dely_{rid}"}],
            [{"text": "❌ انصراف", "callback_data": f"pr_v_{rid}"}]]})
    db_execute("DELETE FROM point_rules WHERE id=?", (r["id"],))
    send(cid, "🗑️ حذف شد")
    return show_rules(cid, uid)


def start_rule_field(cid, uid, rid, key, is_num=False):
    if not _guard(cid, uid):
        return
    r = get_rule(rid)
    if not r:
        return send(cid, "❌ یافت نشد")
    titles = {"title": ("✏️ عنوان قانون", "عنوان جدید:"),
              "message": ("📝 پیام تبریک", "پیامی که هنگام کسب امتیاز نشان داده شود:"),
              "threshold": ("📊 حد نصاب", "عدد لازم برای فعال شدن قانون:"),
              "points": ("🎁 امتیاز", "چند امتیاز داده شود؟")}
    if key not in titles:
        return send(cid, "❌ نامعتبر")
    t, prompt = titles[key]
    set_state(uid, STATE_OC_EDIT,
              {"key": "rule", "rkey": key, "rid": r["id"], "num": 1 if is_num else 0},
              merge=False)
    send(cid, f"{t}\n━━━━━━━━━━━━━━\n\n📌 فعلی: {r.get(key) or '—'}\n\n{prompt}",
         kb_cancel())


def handle_rule_field(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    d = get_state_data(uid)
    rid, key = d.get("rid"), d.get("rkey")

    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return view_rule(cid, uid, rid)

    if key not in ("title", "message", "threshold", "points"):
        clear_state(uid)
        return send(cid, "⚠️ نامعتبر", kb_remove())

    if d.get("num"):
        digits = "".join(ch for ch in normalize_digits(text) if ch.isdigit())
        if not digits:
            return send(cid, "⚠️ فقط عدد وارد کنید:", kb_cancel())
        val = int(digits)
    else:
        if not text:
            return send(cid, "⚠️ متن خالی است:", kb_cancel())
        val = text[:300]

    clear_state(uid)
    db_execute(f"UPDATE point_rules SET {key}=? WHERE id=?", (val, rid))
    send(cid, "✅ ذخیره شد", kb_remove())
    return view_rule(cid, uid, rid)


def start_add_rule(cid, uid):
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_OC_ADD, {"mode": "rule"}, merge=False)
    lst = "\n".join(f"   {v['icon']} {k} — {v['name']}" for k, v in TRIGGERS.items())
    send(cid, (
        "➕ قانون امتیاز جدید\n━━━━━━━━━━━━━━\n\n"
        "در یک خط بنویسید:\n\n"
        "عنوان | شرط | حد نصاب | امتیاز\n\n"
        "مثال:\n"
        "اولین کارگاه | workshop_attend | 1 | 100\n\n"
        f"🎯 شرط‌های موجود:\n{lst}"
    ), kb_cancel())


def handle_add_rule(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_rules(cid, uid)

    parts = [p.strip() for p in text.replace("،", "|").split("|")]
    if len(parts) < 2:
        return send(cid, "⚠️ فرمت: عنوان | شرط | حد نصاب | امتیاز", kb_cancel())
    title = parts[0][:80]
    trg = parts[1]
    if trg not in TRIGGERS:
        return send(cid, f"⚠️ شرط نامعتبر.\n\nمجاز: {', '.join(TRIGGERS)}",
                    kb_cancel())

    def _n(x, dflt):
        dd = "".join(ch for ch in normalize_digits(x or "") if ch.isdigit())
        return int(dd) if dd else dflt

    thr = _n(parts[2] if len(parts) > 2 else "", 1)
    pts = _n(parts[3] if len(parts) > 3 else "", 0)

    clear_state(uid)
    rid = db_execute("""INSERT INTO point_rules
        (key, title, trigger, threshold, points, is_active, created_by)
        VALUES (?,?,?,?,?,1,?)""",
        (f"custom{int(datetime.now().timestamp())}", title, trg, thr, pts, uid))
    send(cid, f"✅ قانون «{title}» ساخته شد\n🎁 {pts} امتیاز", kb_remove())
    return view_rule(cid, uid, rid) if rid else show_rules(cid, uid)


def show_history(cid, uid):
    if not _guard(cid, uid):
        return
    rows = db_execute("""SELECT g.*, u.first_name, u.last_name
        FROM greeting_log g LEFT JOIN users u ON u.bale_user_id=g.bale_user_id
        ORDER BY g.id DESC LIMIT 20""", fetch="all") or []
    total = db_scalar("SELECT COUNT(*) FROM greeting_log")
    pts = db_scalar("SELECT COALESCE(SUM(points_given),0) FROM greeting_log")

    lines = ["📊 تاریخچه تبریک‌ها", "━━━━━━━━━━━━━━", "",
             f"📤 مجموع: {total}", f"🎁 امتیاز داده‌شده: {pts}", ""]
    if rows:
        for r in rows:
            nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or "—"
            kind = "🎂 تولد" if r["kind"] == "birthday" else f"🎉 {r.get('ref_key') or ''}"
            when = _jd.fmt(r.get('sent_at'), 'date')
            lines.append(f"• {nm} — {kind} ({when})")
    else:
        lines.append("📭 هنوز تبریکی ارسال نشده")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": "oc_panel"}]]})
