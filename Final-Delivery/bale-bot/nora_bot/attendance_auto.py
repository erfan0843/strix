"""
⏰ جلسات خودکار و حضور و غیاب آنلاین — فاز ۳۳

درخواست کاربر (عیناً):
  «حضور و غیاب من باید یه دور دیگه جلسه تعیین کنم برای رویداد
   تا کار کنه اینو اتوماتیک کن و امکانات حضور و غیاب مخصوصا
   برای جلسات انلاین کامل کامل کن»

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 مشکلی که بود

  رویداد `sessions_count` داشت (مثلاً «۶ جلسه») ولی هیچ جلسه‌ای
  ساخته نمی‌شد. ادمین باید دستی یکی‌یکی می‌ساخت وگرنه حضور و
  غیاب اصلاً کار نمی‌کرد.

✅ حالا: به‌محض روشن شدن حضور و غیاب، جلسات از روی اطلاعات
   خودِ رویداد ساخته می‌شوند — تاریخ، ساعت، فاصله، همه.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 حضور و غیاب آنلاین — شش روش

  🔢 کد جلسه        ادمین کد می‌دهد، کاربر وارد می‌کند
  🔗 لینک یک‌بارمصرف  هر نفر لینک اختصاصی
  ⏱️ ماندگاری        باید X دقیقه در جلسه بماند
  🙋 پاسخ به فراخوان  ربات وسط جلسه می‌پرسد «هستی؟»
  🔐 رمز پویا        کد هر چند دقیقه عوض می‌شود
  👨‍💼 دستی           ادمین تیک می‌زند
"""
import json
import random
import re
import secrets
from datetime import datetime, timedelta

from database import db_execute, db_scalar, get_setting, set_setting, log
from bale_api import send, send_or_edit, kb_cancel, kb_remove
from auth import set_state, get_state_data, clear_state

# 🌐 روش‌های ویژهٔ جلسات آنلاین
ONLINE_METHODS = {
    "code":     ("🔢", "کد جلسه",
                 "ادمین کدی می‌دهد، شرکت‌کننده وارد می‌کند"),
    "onelink":  ("🔗", "لینک یک‌بارمصرف",
                 "هر نفر لینک اختصاصی می‌گیرد — قابل انتقال نیست"),
    "dwell":    ("⏱️", "ماندگاری",
                 "باید مدت مشخصی در جلسه بماند"),
    "rollcall": ("🙋", "پاسخ به فراخوان",
                 "ربات وسط جلسه می‌پرسد «هستید؟»"),
    "rotating": ("🔐", "رمز پویا",
                 "کد هر چند دقیقه عوض می‌شود — ضدتقلب"),
    "manual":   ("👨‍💼", "ثبت دستی",
                 "ادمین خودش تیک می‌زند"),
}

# 📅 الگوهای تکرار جلسه
REPEAT = {
    "daily":   ("📆", "هر روز", 1),
    "weekly":  ("🗓️", "هفتگی", 7),
    "biweekly": ("📅", "دو هفته یک‌بار", 14),
    "custom":  ("✏️", "فاصلهٔ دلخواه", 0),
}


def _en(text):
    """🔢 ارقام فارسی/عربی → لاتین"""
    return str(text or "").translate(str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def init_tables():
    """🗄️ جدول‌های ویژهٔ حضور آنلاین"""
    from database import ensure_table

    # 🔗 لینک/کد یک‌بارمصرف هر نفر برای هر جلسه
    ensure_table("att_tokens", {
        "session_id": "INTEGER",
        "event_id": "INTEGER",
        "bale_user_id": "INTEGER",
        "token": "TEXT",
        "used": "INTEGER DEFAULT 0",
        "used_at": "TEXT",
        "expires_at": "TEXT",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    })

    # 🙋 فراخوان‌های وسط جلسه
    ensure_table("att_rollcalls", {
        "session_id": "INTEGER",
        "event_id": "INTEGER",
        "asked_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "window_sec": "INTEGER DEFAULT 300",
        "asked_by": "INTEGER",
        "total": "INTEGER DEFAULT 0",
        "answered": "INTEGER DEFAULT 0",
    })
    ensure_table("att_rollcall_answers", {
        "rollcall_id": "INTEGER",
        "bale_user_id": "INTEGER",
        "answered_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    })

    # ⏱️ ورود و خروج برای سنجش ماندگاری
    ensure_table("att_presence", {
        "session_id": "INTEGER",
        "event_id": "INTEGER",
        "bale_user_id": "INTEGER",
        "joined_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "left_at": "TEXT",
        "seconds": "INTEGER DEFAULT 0",
    })

    for q in [
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_atok "
        "ON att_tokens(session_id, bale_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_atok_t ON att_tokens(token)",
        "CREATE INDEX IF NOT EXISTS idx_arc_s "
        "ON att_rollcalls(session_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_arca "
        "ON att_rollcall_answers(rollcall_id, bale_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_apres "
        "ON att_presence(session_id, bale_user_id)",
    ]:
        try:
            db_execute(q)
        except Exception:
            pass
    log("✅ جدول‌های حضور آنلاین آماده شد")


# ══════════════════════════════════════════════════════════
# 📅 ساخت خودکار جلسات
# ══════════════════════════════════════════════════════════
def _jalali_add_days(date_str, days):
    """
    📅 افزودن روز به تاریخ شمسی «۱۴۰۴/۰۷/۲۹».

    از تبدیل به میلادی و برگشت استفاده می‌کند تا ماه‌های
    ۳۱ و ۳۰ روزه و سال کبیسه درست حساب شوند.
    """
    if not date_str:
        return ""
    try:
        parts = re.split(r"[/\-.]", _en(date_str).strip())
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    except Exception:
        return ""
    try:
        import jdatetime
        g = jdatetime.date(y, m, d).togregorian() + timedelta(days=days)
        j = jdatetime.date.fromgregorian(date=g)
        return f"{j.year:04d}/{j.month:02d}/{j.day:02d}"
    except Exception:
        pass
    # 🩹 بدون jdatetime — تقریب با قواعد تقویم شمسی
    try:
        total = d + days
        while total > _jm_days(y, m):
            total -= _jm_days(y, m)
            m += 1
            if m > 12:
                m = 1
                y += 1
        while total < 1:
            m -= 1
            if m < 1:
                m = 12
                y -= 1
            total += _jm_days(y, m)
        return f"{y:04d}/{m:02d}/{total:02d}"
    except Exception:
        return ""


def _jm_days(y, m):
    """تعداد روزهای یک ماه شمسی"""
    if m <= 6:
        return 31
    if m <= 11:
        return 30
    # اسفند: کبیسه؟
    return 30 if ((y + 12) % 33) % 4 == 1 else 29


def plan_sessions(ev):
    """
    🗓️ نقشهٔ جلسات را از روی اطلاعات رویداد می‌سازد.

    خروجی: لیست dict آمادهٔ درج — بدون نوشتن در دیتابیس.
    """
    n = max(1, int(ev.get("sessions_count") or 1))
    start = (ev.get("start_date") or "").strip()
    stime = (ev.get("start_time") or "").strip()
    step_key = (ev.get("session_repeat")
                or get_setting("att_default_repeat", "weekly")
                or "weekly")
    step = REPEAT.get(step_key, REPEAT["weekly"])[2]
    if not step:
        try:
            step = max(1, int(ev.get("session_gap_days") or 7))
        except (TypeError, ValueError):
            step = 7

    online = (ev.get("location_type") or "online") == "online"
    method = (ev.get("att_method")
              or get_setting("att_default_online" if online
                             else "att_default_onsite",
                             "code" if online else "code") or "code")
    try:
        late = int(get_setting("att_default_late", "10") or 10)
    except (TypeError, ValueError):
        late = 10

    out = []
    for i in range(n):
        d = _jalali_add_days(start, step * i) if start else ""
        out.append({
            "session_no": i + 1,
            "title": (f"جلسهٔ {i + 1}" if n > 1
                      else (ev.get("title") or "جلسه")[:60]),
            "session_date": d,
            "start_time": stime,
            "method": method,
            "late_after": late,
            "is_open": 1 if i == 0 else 0,
        })
    return out


def ensure_sessions(eid, force=False, uid=None):
    """
    ⏰ اگر رویداد جلسه ندارد، خودکار بساز.

    🎯 «باید یه دور دیگه جلسه تعیین کنم برای رویداد تا کار کنه
        اینو اتوماتیک کن»

    خروجی: (تعداد ساخته‌شده، پیام)
    """
    from events import get_event
    ev = get_event(eid)
    if not ev:
        return 0, "رویداد پیدا نشد"
    if not ev.get("has_attendance"):
        return 0, "حضور و غیاب این رویداد خاموش است"

    have = db_scalar("SELECT COUNT(*) FROM attendance_sessions "
                     "WHERE event_id=?", (int(eid),)) or 0
    if have and not force:
        return 0, ""

    plan = plan_sessions(ev)
    if have and force:
        # فقط کمبود را بساز — جلسات موجود دست‌نخورده
        plan = plan[have:]
        for i, p in enumerate(plan):
            p["session_no"] = have + i + 1
            p["is_open"] = 0
    if not plan:
        return 0, ""

    made = 0
    for p in plan:
        try:
            db_execute(
                "INSERT INTO attendance_sessions (event_id, title, "
                "session_no, session_code, method, session_date, "
                "start_time, late_after, is_open, created_by) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (int(eid), p["title"], p["session_no"],
                 _new_code(), p["method"], p["session_date"],
                 p["start_time"], p["late_after"], p["is_open"], uid))
            made += 1
        except Exception as e:
            log(f"⚠️ ساخت جلسه {p['session_no']}: {e}")
    if made:
        log(f"⏰ {made} جلسه خودکار برای رویداد #{eid} ساخته شد")
    return made, ""


def _new_code(n=5):
    """🔢 کد جلسهٔ یکتا"""
    for _ in range(20):
        c = "".join(random.choices("0123456789", k=n))
        if not db_scalar("SELECT COUNT(*) FROM attendance_sessions "
                         "WHERE session_code=? AND is_open=1", (c,)):
            return c
    return secrets.token_hex(3).upper()


def sync_on_enable(eid, uid=None):
    """
    🔄 وقتی ادمین «حضور و غیاب» را روشن می‌کند.

    بی‌صدا جلسات را می‌سازد و تعدادشان را برمی‌گرداند.
    """
    if get_setting("att_auto_sessions", "1") != "1":
        return 0
    made, _ = ensure_sessions(eid, uid=uid)
    return made


# ══════════════════════════════════════════════════════════
# 🔗 لینک یک‌بارمصرف
# ══════════════════════════════════════════════════════════
def issue_token(session_id, user_id, ttl_min=None):
    """🔗 ساخت (یا بازیابی) توکن اختصاصی یک نفر برای یک جلسه"""
    row = db_execute(
        "SELECT * FROM att_tokens WHERE session_id=? AND bale_user_id=?",
        (int(session_id), int(user_id)), fetch="one")
    if row and not row.get("used"):
        return row["token"]
    if row and row.get("used"):
        return None

    tok = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]
    try:
        m = int(ttl_min if ttl_min is not None
                else get_setting("att_token_ttl", "120") or 120)
    except (TypeError, ValueError):
        m = 120
    exp = (datetime.now() + timedelta(minutes=m)).isoformat(" ")[:19]
    s = db_execute("SELECT event_id FROM attendance_sessions WHERE id=?",
                   (int(session_id),), fetch="one") or {}
    db_execute(
        "INSERT INTO att_tokens (session_id, event_id, bale_user_id, "
        "token, expires_at) VALUES (?,?,?,?,?)",
        (int(session_id), s.get("event_id"), int(user_id), tok, exp))
    return tok


def token_link(tok):
    """🔗 لینک کامل ثبت حضور"""
    try:
        from config import deep_link
        return deep_link(f"at_{tok}") or f"/start at_{tok}"
    except Exception:
        return f"/start at_{tok}"


def redeem_token(tok, user_id):
    """
    ✅ مصرف توکن و ثبت حضور.

    خروجی: (موفق، پیام)
    """
    r = db_execute("SELECT * FROM att_tokens WHERE token=?",
                   (str(tok),), fetch="one")
    if not r:
        return False, "این لینک معتبر نیست"
    if r.get("used"):
        return False, "این لینک قبلاً استفاده شده"
    if int(r.get("bale_user_id") or 0) != int(user_id):
        return False, "این لینک برای شما صادر نشده"
    exp = (r.get("expires_at") or "").strip()
    if exp:
        try:
            if datetime.now() > datetime.fromisoformat(exp):
                return False, "مهلت این لینک تمام شده"
        except Exception:
            pass

    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (r["session_id"],), fetch="one")
    if not s:
        return False, "جلسه پیدا نشد"
    if not s.get("is_open"):
        return False, "این جلسه بسته است"

    ok, msg = mark_present(s, user_id, method="onelink")
    if ok:
        db_execute("UPDATE att_tokens SET used=1, "
                   "used_at=datetime('now') WHERE id=?", (r["id"],))
    return ok, msg


# ══════════════════════════════════════════════════════════
# ✅ ثبت حضور — هستهٔ مشترک
# ══════════════════════════════════════════════════════════
def mark_present(session, user_id, method="code", status=None):
    """
    ✅ ثبت حضور یک نفر — با تشخیص خودکار تأخیر.

    خروجی: (موفق، پیام)
    """
    sid = session["id"]
    eid = session.get("event_id")

    old = db_execute(
        "SELECT id, status FROM attendance_records WHERE session_id=? "
        "AND bale_user_id=?", (int(sid), int(user_id)), fetch="one")
    if old and (old.get("status") or "") in ("present", "late"):
        return False, "حضور شما قبلاً ثبت شده است"

    st = status or "present"
    if not status:
        late_min = int(session.get("late_after") or 0)
        if late_min > 0 and session.get("start_time"):
            try:
                hh, mm = _en(session["start_time"]).split(":")[:2]
                now = datetime.now()
                sched = now.replace(hour=int(hh), minute=int(mm),
                                    second=0, microsecond=0)
                if now > sched + timedelta(minutes=late_min):
                    st = "late"
            except Exception:
                pass

    if old:
        db_execute("UPDATE attendance_records SET status=?, method=? "
                   "WHERE id=?", (st, method, old["id"]))
    else:
        db_execute(
            "INSERT INTO attendance_records (session_id, event_id, "
            "bale_user_id, method, status) VALUES (?,?,?,?,?)",
            (int(sid), eid, int(user_id), method, st))

    # 🏆 امتیاز جلسه
    pts = int(session.get("points") or 0)
    if pts and st == "present":
        # 🔴 باگ رفع‌شده (فاز ۴۰) — «امتیاز جلسه داده نمی‌شد»:
        #    `club.add_points` **وجود ندارد**. چون داخل
        #    try/except بود، ImportError بی‌صدا بلعیده می‌شد و
        #    کاربر با وجود حضور، هیچ امتیازی نمی‌گرفت.
        #    تابع درست `attendance._award_points` است.
        try:
            from attendance import _award_points
            _award_points(user_id, pts)
        except Exception as _e:
            log(f"⚠️ امتیاز حضور {user_id}: {_e}")

    return True, ("✅ حضور شما ثبت شد" if st == "present"
                  else "⏰ حضور شما با تأخیر ثبت شد")


# ══════════════════════════════════════════════════════════
# 🙋 فراخوان وسط جلسه
# ══════════════════════════════════════════════════════════
def start_rollcall(session_id, uid=None, window_sec=None):
    """
    🙋 ربات از همهٔ شرکت‌کنندگان می‌پرسد «هستید؟»

    خروجی: (شناسهٔ فراخوان، تعداد گیرنده)
    """
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (int(session_id),), fetch="one")
    if not s:
        return None, 0
    try:
        win = int(window_sec if window_sec is not None
                  else get_setting("att_rollcall_sec", "300") or 300)
    except (TypeError, ValueError):
        win = 300

    people = db_execute(
        "SELECT bale_user_id FROM event_registrations WHERE event_id=? "
        "AND status NOT IN ('cancelled','rejected')",
        (s["event_id"],), fetch="all") or []
    rid = db_execute(
        "INSERT INTO att_rollcalls (session_id, event_id, window_sec, "
        "asked_by, total) VALUES (?,?,?,?,?)",
        (int(session_id), s["event_id"], win, uid, len(people)))

    mins = max(1, win // 60)
    txt = (f"🙋 فراخوان حضور\n━━━━━━━━━━━━━━\n\n"
           f"📋 {s.get('title') or 'جلسه'}\n\n"
           f"اگر در جلسه هستید، تا {mins} دقیقهٔ دیگر\n"
           f"دکمهٔ زیر را بزنید.\n\n"
           f"💚 این کار فقط چند ثانیه طول می‌کشد.")
    kb = {"inline_keyboard": [
        [{"text": "🙋 بله، حاضرم", "callback_data": f"arc_{rid}"}]]}
    sent = 0
    for p in people:
        try:
            send(p["bale_user_id"], txt, kb)
            sent += 1
        except Exception:
            pass
    log(f"🙋 فراخوان #{rid} برای {sent} نفر")
    return rid, sent


def answer_rollcall(rollcall_id, user_id):
    """✅ پاسخ به فراخوان"""
    rc = db_execute("SELECT * FROM att_rollcalls WHERE id=?",
                    (int(rollcall_id),), fetch="one")
    if not rc:
        return False, "این فراخوان پیدا نشد"

    try:
        asked = datetime.fromisoformat(str(rc["asked_at"])[:19])
        if datetime.now() > asked + timedelta(
                seconds=int(rc.get("window_sec") or 300)):
            return False, "مهلت پاسخ به این فراخوان تمام شد"
    except Exception:
        pass

    if db_execute("SELECT id FROM att_rollcall_answers WHERE rollcall_id=? "
                  "AND bale_user_id=?", (int(rollcall_id), int(user_id)),
                  fetch="one"):
        return False, "قبلاً پاسخ داده‌اید"

    db_execute("INSERT INTO att_rollcall_answers (rollcall_id, "
               "bale_user_id) VALUES (?,?)",
               (int(rollcall_id), int(user_id)))
    db_execute("UPDATE att_rollcalls SET answered=answered+1 WHERE id=?",
               (int(rollcall_id),))

    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (rc["session_id"],), fetch="one")
    if s:
        mark_present(s, user_id, method="rollcall")
    return True, "✅ ممنون — حضور شما ثبت شد"


def rollcall_stats(session_id):
    """📊 آمار فراخوان‌های یک جلسه"""
    rows = db_execute(
        "SELECT * FROM att_rollcalls WHERE session_id=? ORDER BY id",
        (int(session_id),), fetch="all") or []
    out = []
    for r in rows:
        t, a = int(r.get("total") or 0), int(r.get("answered") or 0)
        out.append({"id": r["id"], "total": t, "answered": a,
                    "pct": round(a * 100.0 / t) if t else 0,
                    "at": str(r.get("asked_at") or "")[:16]})
    return out


# ══════════════════════════════════════════════════════════
# ⏱️ ماندگاری
# ══════════════════════════════════════════════════════════
def join(session_id, user_id):
    """⏱️ ثبت ورود به جلسه"""
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (int(session_id),), fetch="one")
    if not s:
        return False, "جلسه پیدا نشد"
    if not s.get("is_open"):
        return False, "این جلسه هنوز باز نشده"
    open_row = db_execute(
        "SELECT id FROM att_presence WHERE session_id=? AND "
        "bale_user_id=? AND (left_at IS NULL OR left_at='')",
        (int(session_id), int(user_id)), fetch="one")
    if open_row:
        return True, "شما از قبل در جلسه هستید"
    db_execute("INSERT INTO att_presence (session_id, event_id, "
               "bale_user_id) VALUES (?,?,?)",
               (int(session_id), s.get("event_id"), int(user_id)))
    return True, "✅ ورود شما ثبت شد — تا پایان جلسه بمانید"


def leave(session_id, user_id):
    """⏱️ ثبت خروج و سنجش ماندگاری"""
    r = db_execute(
        "SELECT * FROM att_presence WHERE session_id=? AND bale_user_id=? "
        "AND (left_at IS NULL OR left_at='') ORDER BY id DESC LIMIT 1",
        (int(session_id), int(user_id)), fetch="one")
    if not r:
        return False, "ورودی ثبت‌نشده‌ای پیدا نشد"
    try:
        j = datetime.fromisoformat(str(r["joined_at"])[:19])
        sec = int((datetime.now() - j).total_seconds())
    except Exception:
        sec = 0
    db_execute("UPDATE att_presence SET left_at=datetime('now'), "
               "seconds=? WHERE id=?", (sec, r["id"]))

    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (int(session_id),), fetch="one")
    need = _dwell_need(s)
    total = total_seconds(session_id, user_id)
    if total >= need:
        mark_present(s, user_id, method="dwell")
        return True, (f"✅ حضور شما ثبت شد "
                      f"({total // 60} دقیقه در جلسه بودید)")
    kam = max(0, need - total)
    return False, (f"⏳ {total // 60} دقیقه در جلسه بودید — "
                   f"{kam // 60} دقیقهٔ دیگر لازم است")


def total_seconds(session_id, user_id):
    """⏱️ مجموع زمان حضور (چند بار ورود و خروج هم حساب می‌شود)"""
    return int(db_scalar(
        "SELECT COALESCE(SUM(seconds),0) FROM att_presence "
        "WHERE session_id=? AND bale_user_id=?",
        (int(session_id), int(user_id))) or 0)


def _dwell_need(session):
    """⏱️ چند ثانیه ماندن لازم است؟"""
    try:
        m = int((session or {}).get("dwell_minutes") or 0)
    except (TypeError, ValueError):
        m = 0
    if not m:
        try:
            m = int(get_setting("att_dwell_min", "20") or 20)
        except (TypeError, ValueError):
            m = 20
    return max(60, m * 60)


def close_open_presence(session_id):
    """🔒 وقتی جلسه بسته می‌شود، همهٔ حضورهای باز را ببند"""
    rows = db_execute(
        "SELECT * FROM att_presence WHERE session_id=? AND "
        "(left_at IS NULL OR left_at='')", (int(session_id),),
        fetch="all") or []
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (int(session_id),), fetch="one")
    need = _dwell_need(s)
    n = 0
    for r in rows:
        try:
            j = datetime.fromisoformat(str(r["joined_at"])[:19])
            sec = int((datetime.now() - j).total_seconds())
        except Exception:
            sec = 0
        db_execute("UPDATE att_presence SET left_at=datetime('now'), "
                   "seconds=? WHERE id=?", (sec, r["id"]))
        if s and total_seconds(session_id, r["bale_user_id"]) >= need:
            mark_present(s, r["bale_user_id"], method="dwell")
            n += 1
    return n


# ══════════════════════════════════════════════════════════
# 🔐 رمز پویا
# ══════════════════════════════════════════════════════════
def rotating_code(session_id, window=None):
    """
    🔐 کدی که هر چند دقیقه خودش عوض می‌شود.

    ضدتقلب: کسی نمی‌تواند کد را برای دوستش بفرستد چون
    تا برسد منقضی شده.
    """
    try:
        w = int(window if window is not None
                else get_setting("att_rot_sec", "180") or 180)
    except (TypeError, ValueError):
        w = 180
    slot = int(datetime.now().timestamp()) // max(30, w)
    seed = f"{session_id}-{slot}-{get_setting('att_rot_salt', 'nora')}"
    h = 0
    for ch in seed:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return f"{h % 1000000:06d}", w - (int(datetime.now().timestamp()) % w)


def check_rotating(session_id, code):
    """🔐 بررسی کد پویا — اسلات قبلی هم قبول است (تحمل تأخیر)"""
    try:
        w = int(get_setting("att_rot_sec", "180") or 180)
    except (TypeError, ValueError):
        w = 180
    now_slot = int(datetime.now().timestamp()) // max(30, w)
    salt = get_setting("att_rot_salt", "nora")
    for slot in (now_slot, now_slot - 1):
        seed = f"{session_id}-{slot}-{salt}"
        h = 0
        for ch in seed:
            h = (h * 131 + ord(ch)) & 0xFFFFFFFF
        if f"{h % 1000000:06d}" == str(code).strip():
            return True
    return False


# ══════════════════════════════════════════════════════════
# 🖥️ پنل ادمین — حضور و غیاب آنلاین
# ══════════════════════════════════════════════════════════
def _guard(cid, uid):
    """🛡️ بررسی ادمین — منطق مشترک در helpers"""
    from helpers import guard_admin
    return guard_admin(cid, uid)


def _fa(n):
    """🔢 ارقام فارسی — منطق مشترک در helpers"""
    from helpers import fa
    return fa(n)


def show_online(cid, uid, sid):
    """🌐 پنل امکانات آنلاین یک جلسه"""
    if not _guard(cid, uid):
        return
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (int(sid),), fetch="one")
    if not s:
        return send(cid, "❌ جلسه پیدا نشد")

    m = (s.get("method") or "code").strip()
    icon, name, desc = ONLINE_METHODS.get(m, ("▫️", m, ""))
    n_present = db_scalar(
        "SELECT COUNT(*) FROM attendance_records WHERE session_id=? "
        "AND status IN ('present','late')", (int(sid),)) or 0
    n_reg = db_scalar(
        "SELECT COUNT(*) FROM event_registrations WHERE event_id=? "
        "AND status NOT IN ('cancelled','rejected')",
        (s.get("event_id"),)) or 0

    lines = [f"🌐 حضور آنلاین — {s.get('title') or 'جلسه'}",
             "━━━━━━━━━━━━━━", "",
             f"{icon} روش: {name}",
             f"   {desc}", "",
             f"👥 {_fa(n_present)} از {_fa(n_reg)} حاضر",
             f"{'🟢 باز' if s.get('is_open') else '🔴 بسته'}", ""]

    if m == "code":
        lines += [f"🔢 کد جلسه: {s.get('session_code') or '—'}", ""]
    elif m == "rotating":
        code, left = rotating_code(sid)
        lines += [f"🔐 کد فعلی: {code}",
                  f"   ⏳ {_fa(left)} ثانیه تا تغییر", ""]
    elif m == "dwell":
        need = _dwell_need(s) // 60
        lines += [f"⏱️ حداقل ماندگاری: {_fa(need)} دقیقه", ""]
    elif m == "rollcall":
        rc = rollcall_stats(sid)
        if rc:
            lines.append("🙋 فراخوان‌ها:")
            for r in rc[-3:]:
                lines.append(f"   {r['at']} — {_fa(r['answered'])}"
                             f"/{_fa(r['total'])} ({_fa(r['pct'])}٪)")
        else:
            lines.append("🙋 هنوز فراخوانی نداده‌اید")
        lines.append("")

    btns = [[{"text": f"{icon} روش: {name}",
              "callback_data": f"ao_m_{sid}"}]]
    if m == "rotating":
        btns.append([{"text": "🔄 نمایش کد تازه",
                      "callback_data": f"ao_rot_{sid}"}])
    if m == "onelink":
        btns.append([{"text": "🔗 ارسال لینک به همه",
                      "callback_data": f"ao_send_{sid}"}])
    if m == "rollcall":
        btns.append([{"text": "🙋 فراخوان حضور بگیر",
                      "callback_data": f"ao_rc_{sid}"}])
    if m == "dwell":
        btns.append([{"text": "⏱️ حداقل ماندگاری",
                      "callback_data": f"ao_dw_{sid}"}])
        btns.append([{"text": "📊 گزارش ماندگاری",
                      "callback_data": f"ao_dwr_{sid}"}])
    btns.append([{"text": "🔗 لینک جلسه",
                  "callback_data": f"ao_link_{sid}"}])
    btns.append([{"text": "🔙 جلسه",
                  "callback_data": f"att_view_{sid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_methods(cid, uid, sid):
    """🌐 انتخاب روش حضور"""
    if not _guard(cid, uid):
        return
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (int(sid),), fetch="one")
    if not s:
        return send(cid, "❌ جلسه پیدا نشد")
    cur = (s.get("method") or "code").strip()

    lines = ["🌐 روش ثبت حضور", "━━━━━━━━━━━━━━", "",
             "شرکت‌کننده چطور حضورش را ثبت کند؟", ""]
    btns = []
    for k, (ic, nm, ds) in ONLINE_METHODS.items():
        mark = "🔘" if k == cur else "▫️"
        lines.append(f"{mark} {ic} {nm}")
        lines.append(f"     {ds}")
        btns.append([{"text": f"{mark} {ic} {nm}",
                      "callback_data": f"aom_{k}_{sid}"}])
    lines += ["", "💡 برای جلسات آنلاین، «رمز پویا» و «ماندگاری»",
              "   از همه مطمئن‌ترند."]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"ao_{sid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_method(cid, uid, method, sid):
    if not _guard(cid, uid):
        return
    if method not in ONLINE_METHODS:
        return send(cid, "❌ نامعتبر")
    db_execute("UPDATE attendance_sessions SET method=? WHERE id=?",
               (method, int(sid)))
    return show_online(cid, uid, sid)


def show_rotating(cid, uid, sid):
    """🔐 نمایش کد پویای فعلی"""
    if not _guard(cid, uid):
        return
    code, left = rotating_code(sid)
    send(cid, (f"🔐 کد فعلی\n━━━━━━━━━━━━━━\n\n"
               f"          {code}\n\n"
               f"⏳ تا {_fa(left)} ثانیهٔ دیگر عوض می‌شود\n\n"
               f"💡 این کد را در جلسه بگویید یا در چت بگذارید."))
    return show_online(cid, uid, sid)


def send_links(cid, uid, sid):
    """🔗 ارسال لینک یک‌بارمصرف به همهٔ شرکت‌کنندگان"""
    if not _guard(cid, uid):
        return
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (int(sid),), fetch="one")
    if not s:
        return send(cid, "❌ جلسه پیدا نشد")
    people = db_execute(
        "SELECT bale_user_id FROM event_registrations WHERE event_id=? "
        "AND status NOT IN ('cancelled','rejected')",
        (s["event_id"],), fetch="all") or []
    if not people:
        return send(cid, "📭 هنوز کسی ثبت‌نام نکرده")

    send(cid, f"⏳ در حال ارسال به {_fa(len(people))} نفر…")
    ok = skip = 0
    for p in people:
        u = p["bale_user_id"]
        tok = issue_token(sid, u)
        if not tok:
            skip += 1
            continue
        try:
            send(u, (f"🔗 ثبت حضور\n━━━━━━━━━━━━━━\n\n"
                     f"📋 {s.get('title') or 'جلسه'}\n\n"
                     f"برای ثبت حضورتان روی لینک زیر بزنید:\n\n"
                     f"{token_link(tok)}\n\n"
                     f"⚠️ این لینک فقط برای شماست و یک بار کار می‌کند."))
            ok += 1
        except Exception:
            skip += 1
    send(cid, (f"✅ ارسال شد\n\n"
               f"📤 {_fa(ok)} نفر\n"
               f"⏭️ {_fa(skip)} نفر (قبلاً ثبت شده یا خطا)"))
    return show_online(cid, uid, sid)


def do_rollcall(cid, uid, sid):
    """🙋 گرفتن فراخوان"""
    if not _guard(cid, uid):
        return
    rid, n = start_rollcall(sid, uid)
    if not rid:
        return send(cid, "❌ جلسه پیدا نشد")
    if not n:
        return send(cid, "📭 هنوز کسی ثبت‌نام نکرده")
    try:
        win = int(get_setting("att_rollcall_sec", "300") or 300)
    except (TypeError, ValueError):
        win = 300
    send(cid, (f"🙋 فراخوان فرستاده شد\n━━━━━━━━━━━━━━\n\n"
               f"📤 {_fa(n)} نفر\n"
               f"⏳ مهلت پاسخ: {_fa(max(1, win // 60))} دقیقه\n\n"
               f"💡 هرکس پاسخ دهد، حضورش خودکار ثبت می‌شود."))
    return show_online(cid, uid, sid)


def start_dwell(cid, uid, sid):
    if not _guard(cid, uid):
        return
    set_state(uid, "ao_dwell", {"sid": int(sid)})
    send(cid, ("⏱️ حداقل ماندگاری\n━━━━━━━━━━━━━━\n\n"
               "شرکت‌کننده چند دقیقه باید در جلسه بماند\n"
               "تا حضورش ثبت شود؟\n\n"
               "یک عدد بنویسید (مثلاً ۲۰)"), kb_cancel())


def show_dwell_report(cid, uid, sid):
    """📊 گزارش ماندگاری"""
    if not _guard(cid, uid):
        return
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (int(sid),), fetch="one")
    need = _dwell_need(s) // 60
    rows = db_execute(
        "SELECT bale_user_id, SUM(seconds) sec FROM att_presence "
        "WHERE session_id=? GROUP BY bale_user_id ORDER BY sec DESC",
        (int(sid),), fetch="all") or []
    lines = ["📊 گزارش ماندگاری", "━━━━━━━━━━━━━━", "",
             f"⏱️ حداقل لازم: {_fa(need)} دقیقه", ""]
    if not rows:
        lines.append("📭 هنوز کسی وارد جلسه نشده")
    else:
        for r in rows[:20]:
            mins = int(r["sec"] or 0) // 60
            icon = "✅" if mins >= need else "⏳"
            try:
                from auth import get_user
                u = get_user(r["bale_user_id"]) or {}
                nm = f"{u.get('first_name') or ''} " \
                     f"{u.get('last_name') or ''}".strip()
            except Exception:
                nm = ""
            lines.append(f"{icon} {nm or r['bale_user_id']} — "
                         f"{_fa(mins)} دقیقه")
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": f"ao_{sid}"}]]})


def show_session_link(cid, uid, sid):
    """🔗 لینک جلسهٔ آنلاین"""
    if not _guard(cid, uid):
        return
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (int(sid),), fetch="one")
    if not s:
        return send(cid, "❌ جلسه پیدا نشد")
    cur = (s.get("online_link") or "").strip()
    lines = ["🔗 لینک جلسهٔ آنلاین", "━━━━━━━━━━━━━━", "",
             (f"لینک فعلی:\n{cur}" if cur else "📭 لینکی ثبت نشده"), "",
             "💡 این لینک همراه یادآوری جلسه فرستاده می‌شود."]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "✏️ تغییر لینک", "callback_data": f"ao_lnke_{sid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"ao_{sid}"}]]})


def start_link(cid, uid, sid):
    if not _guard(cid, uid):
        return
    set_state(uid, "ao_link", {"sid": int(sid)})
    send(cid, "🔗 لینک جلسه را بفرستید:", kb_cancel())


def handle_text(message):
    """📝 ورودی متنی"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    txt = (message.get("text") or "").strip()
    st, data = get_state_data(uid)
    if not st or not st.startswith("ao_"):
        return False
    if txt in ("انصراف", "❌ انصراف", "/cancel"):
        clear_state(uid)
        send(cid, "✅ لغو شد", kb_remove())
        return True

    sid = data.get("sid")
    if st == "ao_dwell":
        try:
            v = max(1, int(_en(txt)))
        except Exception:
            send(cid, "⚠️ یک عدد بنویسید")
            return True
        db_execute("UPDATE attendance_sessions SET dwell_minutes=? "
                   "WHERE id=?", (v, int(sid)))
        clear_state(uid)
        send(cid, f"✅ حداقل ماندگاری {_fa(v)} دقیقه شد", kb_remove())
        show_online(cid, uid, sid)
        return True

    if st == "ao_link":
        db_execute("UPDATE attendance_sessions SET online_link=? "
                   "WHERE id=?", (txt[:300], int(sid)))
        clear_state(uid)
        send(cid, "✅ لینک ذخیره شد", kb_remove())
        show_online(cid, uid, sid)
        return True
    return False


# ══════════════════════════════════════════════════════════
# 👤 سمت کاربر
# ══════════════════════════════════════════════════════════
def user_answer_rollcall(cid, uid, rid):
    """🙋 کاربر به فراخوان پاسخ داد"""
    ok, msg = answer_rollcall(rid, uid)
    return send(cid, ("✅ " if ok else "🌱 ") + msg)


def user_token(cid, uid, tok):
    """🔗 کاربر لینک یک‌بارمصرف را باز کرد"""
    ok, msg = redeem_token(tok, uid)
    return send(cid, ("✅ " if ok else "🌱 ") + msg)


def user_join(cid, uid, sid):
    """⏱️ کاربر وارد جلسه شد"""
    ok, msg = join(sid, uid)
    kb = {"inline_keyboard": [
        [{"text": "🚪 خروج از جلسه", "callback_data": f"aol_{sid}"}]]}
    return send(cid, ("✅ " if ok else "🌱 ") + msg, kb)


def user_leave(cid, uid, sid):
    """⏱️ کاربر از جلسه خارج شد"""
    ok, msg = leave(sid, uid)
    return send(cid, ("✅ " if ok else "⏳ ") + msg)
