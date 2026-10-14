"""
✋ حضور و غیاب هوشمند + 🎓 گواهینامه — فاز ۶

طبق معماری توافق‌شده:
  رویداد ← ثبت‌نام ← پرداخت ← بلیت ← [حضور و غیاب] ← [گواهینامه] ← گزارش

روش‌های ثبت حضور (همه سفارشی و دست ادمین):
  ۱. 🔢 کد جلسه — ادمین کد می‌سازد، شرکت‌کننده وارد می‌کند
  ۲. 🎫 کد بلیت — شرکت‌کننده کد بلیتش را می‌زند
  ۳. 📍 موقعیت مکانی — چک فاصله تا محل رویداد
  ۴. 👨‍💼 دستی — ادمین از لیست تیک می‌زند
  ۵. 🔗 لینک/QR — اسکن یا کلیک
  ۶. ⏰ خودکار — برای وبینار، با ورود به لینک

گواهینامه:
  قالب متنی با متغیرهای قابل تغییر از پنل ادمین
  خروجی: تصویر (Pillow) یا متن
"""
import json
import random
import string
import time
from datetime import datetime
from pathlib import Path

from config import (
    SUPER_ADMIN_ID, FILES_DIR, EVENTS_DIR, CURRENCY_LABEL,
    org_name, bot_name, brand,
)
from database import db_execute, db_scalar, get_setting, set_setting, log
from auth import (
    get_user, get_user_by_id, set_state, get_state_name, get_state_data,
    update_state_data, clear_state, log_action, normalize_digits,
    is_admin as _is_admin,
)
from bale_api import (
    send, send_or_edit, send_photo, send_document, kb_cancel, kb_remove,
    kb_location, BTN_BACK,
)
import jalali as _jd

STATE_ATT_CODE = "att_code"
STATE_ATT_LOC = "att_location"
STATE_ATT_EXCUSE = "att_excuse"   # 🆕 فاز ۱۵ — درخواست غیبت مجاز
STATE_CERT_EDIT = "cert_edit"
STATE_ATT_FIELD = "att_field"     # 🆕 فاز ۲۲ — ویرایش فیلد جلسه
STATE_ATT_SETLOC = "att_setloc"   # 🆕 فاز ۲۲ — ثبت موقعیت محل جلسه

CERT_DIR = Path(FILES_DIR) / "certificates"

ATT_METHODS = {
    "code":     {"icon": "🔢", "name": "کد جلسه"},
    "ticket":   {"icon": "🎫", "name": "کد بلیت"},
    "location": {"icon": "📍", "name": "موقعیت مکانی"},
    "manual":   {"icon": "👨‍💼", "name": "ثبت دستی ادمین"},
    "auto":     {"icon": "⏰", "name": "خودکار"},
}

# 🆕 فاز ۲۲ — چهار وضعیت حضور
#    🔴 جدول از اول چهار وضعیت داشت ولی ادمین فقط می‌توانست
#       بین «حاضر» و «هیچ» جابه‌جا شود.
ATT_STATUS_FA = {
    "present": "حاضر",
    "late": "تأخیر",
    "excused": "غیبت موجه",
    "absent": "غایب",
}

ATT_ICONS = {
    "present": "✅",
    "late": "⏰",
    "excused": "📄",
    "absent": "❌",
}


# ==================== جداول ====================
SESSIONS_SCHEMA = {
    "event_id": "INTEGER",
    "title": "TEXT",
    "session_no": "INTEGER DEFAULT 1",
    "session_code": "TEXT",
    "method": "TEXT DEFAULT 'code'",
    "lat": "REAL",
    "lon": "REAL",
    "radius_m": "INTEGER DEFAULT 200",
    "opens_at": "TIMESTAMP",
    "closes_at": "TIMESTAMP",
    "is_open": "INTEGER DEFAULT 1",
    # 🆕 فاز ۲۲ — جزئیات جلسه
    "session_date": "TEXT",       # تاریخ شمسی جلسه
    "start_time": "TEXT",         # ساعت شروع
    "late_after": "INTEGER DEFAULT 0",   # دقیقه تا «تأخیر»
    "points": "INTEGER DEFAULT 0",
    # 🌐 فاز ۳۳ — جلسات آنلاین
    "dwell_minutes": "INTEGER DEFAULT 0",   # حداقل ماندگاری
    "online_link": "TEXT",                  # لینک جلسه
    "auto_made": "INTEGER DEFAULT 0",       # خودکار ساخته شده؟
    "created_by": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

RECORDS_SCHEMA = {
    "session_id": "INTEGER",
    "event_id": "INTEGER",
    "user_id": "INTEGER",
    "bale_user_id": "INTEGER",
    "method": "TEXT",
    "status": "TEXT DEFAULT 'present'",
    "lat": "REAL",
    "lon": "REAL",
    "distance_m": "INTEGER",
    "note": "TEXT",
    "recorded_by": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

CERTS_SCHEMA = {
    "event_id": "INTEGER",
    "user_id": "INTEGER",
    "bale_user_id": "INTEGER",
    "serial": "TEXT",
    "template": "TEXT",
    "file_path": "TEXT",
    "issued_by": "INTEGER",
    "issued_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    # 🆕 فاز ۱۹ — گواهینامه از قالب ورد
    "template_id": "INTEGER",     # کدام قالب استفاده شد
    "png_path": "TEXT",           # خروجی تصویری
    "pdf_path": "TEXT",           # خروجی PDF
    "docx_path": "TEXT",          # نسخه ورد شخصی‌سازی‌شده
    "form_id": "INTEGER",         # اگر از فرم صادر شده
    "response_id": "INTEGER",
    "revoked": "INTEGER DEFAULT 0",   # ابطال
    # 🆕 فاز ۳۲ — چند گواهینامه برای یک رویداد
    #
    # 🎯 «بعضی رویدادها همکاری هستن و ممکن یک تا چندین گواهی
    #     مستقل صادر بشه»
    #
    # 🔴 نکتهٔ مهم: قید یکتا از (event_id, bale_user_id) به
    #    (event_id, bale_user_id, event_cert_id) گسترش یافت.
    #    وگرنه نفر دوم گواهینامه‌اش جای اولی را می‌گرفت.
    "event_cert_id": "INTEGER DEFAULT 0",   # کدام گواهینامهٔ رویداد
    "source": "TEXT DEFAULT 'event'",       # event|batch|form|manual
    "batch_id": "INTEGER",                  # اگر از دستهٔ اکسل
    # 🔍 فاز ۳۴ — شناسهٔ دولایه و اعتبار زمانی
    #
    # 🎯 «هر رویداد یدونه شماره ثبت داره — چطوری استعلام‌کننده
    #     اطلاعات همان یک نفر را می‌بیند؟»
    #
    #   doc_no      شمارهٔ نامه  ← مشترک بین همهٔ گواهینامه‌های رویداد
    #   person_code کد فردی      ← یکتا برای هر نفر
    #   full_code   ترکیب هردو   ← مبنای استعلام و محتوای کیوآر
    "doc_no": "TEXT",
    "person_code": "TEXT",
    "full_code": "TEXT",
    "issued_on": "TEXT",            # تاریخ صدور (شمسی)
    "expires_on": "TEXT",           # تاریخ انقضا (شمسی)
    "valid_months": "INTEGER DEFAULT 0",
    "verify_count": "INTEGER DEFAULT 0",
    "last_verified": "TEXT",
}


# 🆕 فاز ۱۵ — درخواست غیبت مجاز (فایل معماری، خط ۵۶۹۵۰)
EXCUSE_SCHEMA = {
    "session_id": "INTEGER",
    "event_id": "INTEGER",
    "bale_user_id": "INTEGER",
    "reason": "TEXT",
    "proof_file_id": "TEXT",
    "status": "TEXT DEFAULT 'pending'",   # pending | approved | rejected
    "reviewed_by": "INTEGER",
    "reviewed_at": "TIMESTAMP",
    "admin_notes": "TEXT",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}


def init_attendance_tables():
    """با مهاجرت خودکار ستون‌های گمشده"""
    from database import ensure_table

    ensure_table("attendance_sessions", SESSIONS_SCHEMA)
    ensure_table("attendance_records", RECORDS_SCHEMA,
                 unique="session_id, bale_user_id")
    # 🎓 قید یکتا شامل event_cert_id است تا یک نفر بتواند از یک
    #    رویداد چند گواهینامهٔ مستقل بگیرد (رویدادهای مشترک)
    ensure_table("certificates", CERTS_SCHEMA,
                 unique="event_id, bale_user_id, event_cert_id")
    # ♻️ مهاجرت: اگر ایندکس قدیمی مانده، برداشته شود
    try:
        from database import db_execute as _dbx
        for _q in ("DROP INDEX IF EXISTS uq_certificates",
                   "DROP INDEX IF EXISTS uq_certs"):
            _dbx(_q)
        _dbx("CREATE UNIQUE INDEX IF NOT EXISTS uq_cert_ev_user_slot "
             "ON certificates(event_id, bale_user_id, event_cert_id)")
    except Exception:
        pass
    ensure_table("excuse_requests", EXCUSE_SCHEMA)

    for q in [
        "CREATE INDEX IF NOT EXISTS idx_att_sess ON attendance_sessions(event_id)",
        "CREATE INDEX IF NOT EXISTS idx_att_rec ON attendance_records(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_att_user ON attendance_records(bale_user_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_att ON attendance_records(session_id, bale_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_cert_user ON certificates(bale_user_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_cert ON certificates(event_id, bale_user_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_cert_serial ON certificates(serial)",
    ]:
        db_execute(q)

    CERT_DIR.mkdir(parents=True, exist_ok=True)


def gen_session_code(n=5):
    return "".join(random.choices(string.digits, k=n))


def gen_serial():
    """
    🔖 شمارهٔ سریال گواهینامه.

    🔴 باگ رفع‌شده (فاز ۴۰): پیشوند «NORA» ثابت بود و تنظیم
       `cert_serial_prefix` که در پنل وجود داشت هیچ اثری
       نداشت — ادمین عوضش می‌کرد و سریال‌ها همان NORA
       می‌ماندند.
    """
    from database import get_setting as _gs
    pref = (_gs("cert_serial_prefix", "NORA") or "NORA").strip()
    pref = "".join(c for c in pref if c.isalnum() or c in "-_")[:12]
    return (f"{pref or 'NORA'}-{datetime.now().strftime('%y%m')}"
            f"-{random.randint(10000, 99999)}")


def _guard(cid, uid):
    if not _is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    return True


# ==================== ادمین: مدیریت جلسات ====================
def show_sessions(cid, uid, eid):
    if not _guard(cid, uid):
        return
    from events import get_event, EVENT_TYPES

    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    rows = db_execute(
        "SELECT * FROM attendance_sessions WHERE event_id=? ORDER BY session_no",
        (eid,), fetch="all") or []

    # ⏰ فاز ۳۳ — اگر جلسه‌ای نیست، همین‌جا خودکار بساز
    #    🎯 «باید یه دور دیگه جلسه تعیین کنم تا کار کنه»
    auto_made = 0
    if not rows and ev.get("has_attendance"):
        try:
            import attendance_auto as _aa
            auto_made = _aa.sync_on_enable(eid, uid)
            if auto_made:
                rows = db_execute(
                    "SELECT * FROM attendance_sessions WHERE event_id=? "
                    "ORDER BY session_no", (eid,), fetch="all") or []
        except Exception as _e:
            log(f"⚠️ ساخت خودکار جلسه: {_e}")

    lines = [f"✋ حضور و غیاب «{ev['title']}»", "━━━━━━━━━━━━━━", ""]
    if auto_made:
        lines += [f"⏰ {auto_made} جلسه خودکار ساخته شد",
                  "   از روی تاریخ و تعداد جلسات رویداد", ""]

    if not rows:
        lines += [
            "📭 هنوز جلسه‌ای تعریف نشده",
            "",
            "💡 برای هر جلسه یک کد می‌سازید و",
            "شرکت‌کنندگان با آن حضورشان را ثبت می‌کنند.",
        ]
    else:
        confirmed = db_scalar(
            "SELECT COUNT(*) FROM event_registrations "
            "WHERE event_id=? AND status IN ('confirmed','attended')", (eid,))
        for s in rows:
            present = db_scalar(
                "SELECT COUNT(*) FROM attendance_records "
                "WHERE session_id=? AND status='present'", (s["id"],))
            rate = f"{present * 100 // confirmed}%" if confirmed else "-"
            m = ATT_METHODS.get(s.get("method") or "code", ATT_METHODS["code"])
            state = "🟢 باز" if s.get("is_open") else "🔴 بسته"
            lines += [
                f"📋 جلسه {s['session_no']}: {s.get('title') or '-'}",
                f"├── {state} | {m['icon']} {m['name']}",
                f"├── 🔢 کد: {s.get('session_code') or '-'}",
                f"└── ✋ حاضر: {present} از {confirmed} ({rate})",
                "",
            ]

    btns = [[{"text": "➕ جلسه جدید", "callback_data": f"att_new_{eid}"}]]
    for s in rows:
        icon = "🔴" if s.get("is_open") else "🟢"
        btns.append([
            {"text": f"📋 جلسه {s['session_no']}"[:20],
             "callback_data": f"att_view_{s['id']}"},
            {"text": icon, "callback_data": f"att_toggle_{s['id']}"},
        ])
    if rows:
        btns.append([{"text": "📊 کارنامه کلی", "callback_data": f"att_report_{eid}"}])
        btns.append([{"text": "📤 خروجی اکسل", "callback_data": f"att_export_{eid}"}])
        if ev.get("has_certificate"):
            btns.append([{"text": "🎓 مرکز صدور گواهینامه",
                          "callback_data": f"cert_bulk_{eid}"}])
    btns.append([{"text": "🔙 رویداد", "callback_data": f"ev_view_{eid}"}])

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def new_session(cid, uid, eid):
    """ساخت سریع جلسه با کد خودکار"""
    if not _guard(cid, uid):
        return
    from events import get_event

    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    last = db_scalar(
        "SELECT COALESCE(MAX(session_no),0) FROM attendance_sessions WHERE event_id=?",
        (eid,))
    no = last + 1
    code = gen_session_code()

    sid = db_execute("""INSERT INTO attendance_sessions
        (event_id, title, session_no, session_code, method, is_open,
         points, created_by)
        VALUES (?,?,?,?,'code',1,?,?)""",
        (eid, f"جلسه {no}", no, code, ev.get("points_reward") or 0, uid))

    if not sid:
        return send(cid, "❌ خطا در ساخت جلسه")

    log_action(uid, "session_created", {"event_id": eid, "session_id": sid})

    send_or_edit(cid, (
        f"✅ جلسه {no} ساخته شد\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🎉 {ev['title']}\n"
        f"🔢 کد حضور: {code}\n\n"
        f"💡 این کد را به شرکت‌کنندگان بگویید.\n"
        f"آن‌ها از «✋ حضور و غیاب» آن را وارد می‌کنند.\n\n"
        f"⚠️ تا وقتی جلسه باز است، حضور ثبت می‌شود."
    ), {"inline_keyboard": [
        [{"text": "📋 کپی کد", "copy_text": {"text": code}}],
        [{"text": "📢 اعلام کد به شرکت‌کنندگان",
          "callback_data": f"att_announce_{sid}"}],
        [{"text": "⚙️ تنظیمات جلسه", "callback_data": f"att_view_{sid}"}],
        [{"text": "🔙 لیست جلسات", "callback_data": f"att_list_{eid}"}],
    ]})


def show_session(cid, uid, sid):
    """
    📋 کارت جلسه — کامل و دقیق.

    🎯 فاز ۲۲: «حضور و غیاب رویداد واقعاً ضعیف و داغونه»
       قبلاً روش ثبت قابل تغییر نبود، وضعیت‌های تأخیر و غیبت
       موجه دیده نمی‌شدند، و غایبان هیچ فهرستی نداشتند.
    """
    if not _guard(cid, uid):
        return
    from events import get_event

    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?", (sid,), fetch="one")
    if not s:
        return send(cid, "❌ جلسه یافت نشد")
    ev = get_event(s["event_id"])

    st = session_stats(sid, s["event_id"])
    m = ATT_METHODS.get(s.get("method") or "code", ATT_METHODS["code"])
    sess_title = s.get("title") or f"جلسه {s.get('session_no') or ''}"

    lines = [
        f"📋 {sess_title}",
        "━━━━━━━━━━━━━━",
        "",
        f"🎉 رویداد: {(ev or {}).get('title') or '-'}",
        f"🔢 کد حضور: {s.get('session_code') or '-'}",
        f"{m['icon']} روش: {m['name']}",
        f"📌 وضعیت: {'🟢 باز' if s.get('is_open') else '🔴 بسته'}",
        f"🏆 امتیاز: {s.get('points') or 0}",
    ]
    if s.get("method") == "location" and s.get("lat"):
        lines.append(f"📍 شعاع مجاز: {s.get('radius_m') or 200} متر")
    if s.get("session_date"):
        lines.append(f"📅 تاریخ: {s['session_date']}")
    if s.get("start_time"):
        lines.append(f"🕐 ساعت: {s['start_time']}")
    if s.get("late_after"):
        lines.append(f"⏰ بعد از {s['late_after']} دقیقه = تأخیر")

    lines += [
        "",
        "📊 آمار:",
        f"├── ✅ حاضر: {st['present']}",
        f"├── ⏰ تأخیر: {st['late']}",
        f"├── 📄 غیبت موجه: {st['excused']}",
        f"├── ❌ غایب: {st['absent']}",
        f"└── 👥 کل ثبت‌نامی: {st['total']}",
    ]
    if st["total"]:
        lines.append(f"📈 نرخ حضور: {st['rate']}٪")

    btns = [
        [{"text": "🔴 بستن جلسه" if s.get("is_open") else "🟢 بازکردن جلسه",
          "callback_data": f"att_toggle_{sid}"}],
        [{"text": f"👥 حاضرین ({st['present'] + st['late']})",
          "callback_data": f"att_who_{sid}_0"}],
        [{"text": f"❌ غایبان ({st['absent']})",
          "callback_data": f"att_abs_{sid}_0"}],
        [{"text": "✍️ ثبت دستی حضور", "callback_data": f"att_manual_{sid}_0"}],
        [{"text": f"{m['icon']} تغییر روش ثبت", "callback_data": f"att_meth_{sid}"},
         {"text": "🌐 آنلاین", "callback_data": f"ao_{sid}"}],
        [{"text": "⚙️ تنظیمات جلسه", "callback_data": f"att_set_{sid}"}],
        [{"text": "📢 اعلام کد", "callback_data": f"att_announce_{sid}"}],
        [{"text": "🔄 کد جدید", "callback_data": f"att_newcode_{sid}"}],
        [{"text": "🗑️ حذف جلسه", "callback_data": f"att_del_{sid}"}],
        [{"text": "🔙 لیست جلسات", "callback_data": f"att_list_{s['event_id']}"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def session_stats(sid, eid=None):
    """
    📊 آمار دقیق یک جلسه.

    🎯 قبلاً فقط «حاضر» و «تأخیر» شمرده می‌شد و غیبت موجه
       اصلاً دیده نمی‌شد — با اینکه جدول excuse_requests داشتیم!
    """
    if eid is None:
        r = db_execute("SELECT event_id FROM attendance_sessions WHERE id=?",
                       (sid,), fetch="one")
        eid = (r or {}).get("event_id")
    present = db_scalar(
        "SELECT COUNT(*) FROM attendance_records "
        "WHERE session_id=? AND status='present'", (sid,)) or 0
    late = db_scalar(
        "SELECT COUNT(*) FROM attendance_records "
        "WHERE session_id=? AND status='late'", (sid,)) or 0
    excused = db_scalar(
        "SELECT COUNT(*) FROM attendance_records "
        "WHERE session_id=? AND status='excused'", (sid,)) or 0
    total = db_scalar(
        "SELECT COUNT(*) FROM event_registrations "
        "WHERE event_id=? AND status IN ('confirmed','attended')",
        (eid,)) or 0
    absent = max(0, total - present - late - excused)
    rate = int((present + late) * 100 / total) if total else 0
    return {"present": present, "late": late, "excused": excused,
            "absent": absent, "total": total, "rate": rate}


def show_methods(cid, uid, sid):
    """
    🔀 تغییر روش ثبت حضور.

    🔴 باگ: ستون method در جدول بود و ۵ روش تعریف شده بود، ولی
       هیچ دکمه‌ای برای تغییرش وجود نداشت — همیشه 'code' می‌ماند.
       یعنی «موقعیت مکانی» و «کد بلیت» عملاً مرده بودند.
    """
    if not _guard(cid, uid):
        return
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (sid,), fetch="one")
    if not s:
        return send(cid, "❌ یافت نشد")
    cur = s.get("method") or "code"

    desc = {
        "code": "کاربر کد جلسه را وارد می‌کند — ساده‌ترین راه",
        "ticket": "کاربر کد بلیت خودش را می‌زند — بدون اعلام کد",
        "location": "کاربر موقعیتش را می‌فرستد — باید در محل باشد",
        "manual": "فقط شما دستی تیک می‌زنید — کاربر کاری نمی‌کند",
        "auto": "هرکس ثبت‌نام دارد خودکار حاضر می‌شود",
    }

    lines = ["🔀 روش ثبت حضور", "━━━━━━━━━━━━━━", "",
             "شرکت‌کنندگان چطور حضورشان را ثبت کنند؟", ""]
    for k, v in ATT_METHODS.items():
        mark = "🔘" if k == cur else "▫️"
        lines.append(f"{mark} {v['icon']} {v['name']}")
        lines.append(f"      {desc.get(k, '')}")

    if cur == "location" and not s.get("lat"):
        lines += ["", "⚠️ برای روش موقعیت، اول مختصات محل را",
                  "   از «⚙️ تنظیمات جلسه» ثبت کنید."]

    btns = [[{"text": f"{'🔘' if k == cur else '▫️'} {v['icon']} {v['name']}",
              "callback_data": f"att_setm_{sid}_{k}"}]
            for k, v in ATT_METHODS.items()]
    btns.append([{"text": "🔙 جلسه", "callback_data": f"att_view_{sid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_method(cid, uid, sid, method):
    """🔀 اعمال روش جدید"""
    if not _guard(cid, uid):
        return
    if method not in ATT_METHODS:
        return send(cid, "❌ نامعتبر")
    db_execute("UPDATE attendance_sessions SET method=? WHERE id=?",
               (method, sid))
    log_action(uid, "session_method_changed",
               {"session_id": sid, "method": method})

    # ⏰ روش خودکار: همه ثبت‌نامی‌ها را حاضر کن
    if method == "auto":
        s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                       (sid,), fetch="one")
        regs = db_execute(
            "SELECT r.bale_user_id, r.user_id FROM event_registrations r "
            "WHERE r.event_id=? AND r.status IN ('confirmed','attended') "
            "AND r.bale_user_id IS NOT NULL", (s["event_id"],),
            fetch="all") or []
        n = 0
        for r in regs:
            got = db_execute("INSERT OR IGNORE INTO attendance_records "
                             "(session_id, event_id, user_id, bale_user_id, "
                             "method, status, recorded_by) "
                             "VALUES (?,?,?,?,'auto','present',?)",
                             (sid, s["event_id"], r.get("user_id"),
                              r["bale_user_id"], uid))
            if got:
                n += 1
        send(cid, f"⏰ {n} نفر خودکار حاضر شدند")
    else:
        send(cid, f"✅ روش: {ATT_METHODS[method]['name']}")
    return show_session(cid, uid, sid)


# ─────────── ⚙️ تنظیمات جلسه ───────────
SESSION_FIELDS = [
    ("title", "📝", "عنوان جلسه", "text", "مثال: جلسه سوم — کارگاه عملی"),
    ("session_date", "📅", "تاریخ جلسه", "text", "مثال: 1404/05/12"),
    ("start_time", "🕐", "ساعت شروع", "text", "مثال: 16:30"),
    ("points", "🏆", "امتیاز حضور", "num", "چند امتیاز به حاضرین؟"),
    ("late_after", "⏰", "دقیقه تا تأخیر", "num",
     "بعد از این دقیقه، حضور «تأخیر» ثبت می‌شود · ۰ = بی‌اثر"),
    ("radius_m", "📍", "شعاع مجاز (متر)", "num",
     "برای روش موقعیت مکانی"),
]


def show_session_settings(cid, uid, sid):
    """⚙️ تنظیمات کامل جلسه"""
    if not _guard(cid, uid):
        return
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (sid,), fetch="one")
    if not s:
        return send(cid, "❌ یافت نشد")

    lines = ["⚙️ تنظیمات جلسه", "━━━━━━━━━━━━━━", ""]
    btns = []
    for key, icon, name, kind, hint in SESSION_FIELDS:
        v = s.get(key)
        shown = str(v) if v not in (None, "", 0) else "—"
        lines.append(f"{icon} {name}: {shown}")
        btns.append([{"text": f"{icon} {name}: {shown[:12]}"[:34],
                      "callback_data": f"att_fld_{sid}_{key}"}])

    lines += ["", "📍 موقعیت مکانی:"]
    if s.get("lat"):
        lines.append(f"   ✅ ثبت شده ({s['lat']:.4f}, {s['lon']:.4f})")
    else:
        lines.append("   ⚪ ثبت نشده")
    btns.append([{"text": "📍 ثبت موقعیت محل جلسه",
                  "callback_data": f"att_loc_{sid}"}])
    btns.append([{"text": "🔙 جلسه", "callback_data": f"att_view_{sid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_field(cid, uid, sid, key):
    """✏️ ویرایش یک فیلد جلسه"""
    if not _guard(cid, uid):
        return
    row = next((r for r in SESSION_FIELDS if r[0] == key), None)
    if not row:
        return send(cid, "❌ نامعتبر")
    _, icon, name, kind, hint = row
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (sid,), fetch="one")
    cur = (s or {}).get(key)
    set_state(uid, STATE_ATT_FIELD, {"sid": sid, "key": key}, merge=False)
    txt = [f"✏️ {icon} {name}", "━━━━━━━━━━━━━━", "",
           f"📄 فعلی: {cur if cur not in (None, '') else '—'}", ""]
    if hint:
        txt += [f"💡 {hint}", ""]
    txt += ["مقدار جدید را بنویسید:", "💡 برای خالی کردن، «-» بفرستید"]
    send(cid, "\n".join(txt), kb_cancel())


def handle_field(message):
    """📥 دریافت مقدار فیلد جلسه"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid)
    sid, key = d.get("sid"), d.get("key")

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_session_settings(cid, uid, sid)

    row = next((r for r in SESSION_FIELDS if r[0] == key), None)
    if not sid or not row:
        clear_state(uid)
        return send(cid, "❌ نامعتبر", kb_remove())

    if raw == "-":
        val = 0 if row[3] == "num" else ""
    elif row[3] == "num":
        digits = "".join(ch for ch in normalize_digits(raw) if ch.isdigit())
        if not digits:
            return send(cid, "⚠️ فقط عدد بفرستید:", kb_cancel())
        val = int(digits)
    else:
        val = normalize_digits(raw)[:120]

    db_execute(f"UPDATE attendance_sessions SET {key}=? WHERE id=?",
               (val, sid))
    clear_state(uid)
    log_action(uid, "session_updated", {"session_id": sid, "field": key})
    send(cid, f"✅ ذخیره شد: {val or '—'}", kb_remove())
    return show_session_settings(cid, uid, sid)


def start_session_location(cid, uid, sid):
    """📍 ثبت موقعیت محل جلسه"""
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_ATT_SETLOC, {"sid": sid}, merge=False)
    send(cid, (
        "📍 موقعیت محل جلسه\n━━━━━━━━━━━━━━\n\n"
        "روی دکمه پایین بزنید و موقعیت محل برگزاری را\n"
        "بفرستید.\n\n"
        "💡 باید همان‌جا باشید، یا روی نقشه نقطه را\n"
        "   دستی انتخاب کنید.\n\n"
        "بعد از این، شرکت‌کنندگان فقط وقتی در شعاع\n"
        "مجاز باشند می‌توانند حضور بزنند."
    ), kb_location())


def handle_session_location(message):
    """📥 دریافت موقعیت محل جلسه از ادمین"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    d = get_state_data(uid)
    sid = d.get("sid")

    txt = (message.get("text") or "").strip()
    if txt in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_session_settings(cid, uid, sid)

    loc = message.get("location")
    if not loc:
        return send(cid, "⚠️ لطفاً موقعیت را بفرستید:", kb_location())

    db_execute("UPDATE attendance_sessions SET lat=?, lon=?, "
               "method='location' WHERE id=?",
               (loc.get("latitude"), loc.get("longitude"), sid))
    clear_state(uid)
    s = db_execute("SELECT radius_m FROM attendance_sessions WHERE id=?",
                   (sid,), fetch="one")
    send(cid, (
        f"✅ موقعیت ثبت شد 💚\n\n"
        f"📍 شعاع مجاز: {(s or {}).get('radius_m') or 200} متر\n"
        f"🔀 روش ثبت هم روی «موقعیت مکانی» تنظیم شد.\n\n"
        f"💡 شعاع را از تنظیمات جلسه تغییر دهید."
    ), kb_remove())
    return show_session_settings(cid, uid, sid)


def toggle_session(cid, uid, sid):
    if not _guard(cid, uid):
        return
    s = db_execute("SELECT is_open, event_id FROM attendance_sessions WHERE id=?",
                   (sid,), fetch="one")
    if not s:
        return send(cid, "❌ یافت نشد")
    new = 0 if s["is_open"] else 1
    db_execute("UPDATE attendance_sessions SET is_open=? WHERE id=?", (new, sid))

    # 🔴 باگ رفع‌شده (فاز ۴۰) — «حضور آنلاین نیمه‌کاره می‌ماند»:
    #    `attendance_auto.close_open_presence()` نوشته شده بود
    #    ولی **هیچ‌جا صدا زده نمی‌شد**. وقتی ادمین جلسهٔ آنلاین
    #    را می‌بست، کسانی که هنوز «داخل» بودند رکورد بازشان
    #    بسته نمی‌شد و ماندگاری‌شان حساب نمی‌شد — یعنی با
    #    وجود حضور کامل، غایب می‌ماندند.
    closed = 0
    if not new:
        try:
            import attendance_auto as _aa
            closed = _aa.close_open_presence(sid) or 0
        except Exception as _e:
            log(f"⚠️ بستن حضورهای باز: {_e}")

    msg = f"✅ جلسه {'باز' if new else 'بسته'} شد"
    if closed:
        msg += f"\n🎯 {closed} حضور آنلاین نهایی شد"
    send(cid, msg)
    show_session(cid, uid, sid)


def new_code(cid, uid, sid):
    if not _guard(cid, uid):
        return
    code = gen_session_code()
    db_execute("UPDATE attendance_sessions SET session_code=? WHERE id=?", (code, sid))
    send_or_edit(cid, f"🔄 کد جدید: {code}", {"inline_keyboard": [
        [{"text": "📋 کپی", "copy_text": {"text": code}}],
        [{"text": "🔙 جلسه", "callback_data": f"att_view_{sid}"}]]})


def delete_session(cid, uid, sid, confirmed=False):
    if not _guard(cid, uid):
        return
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?", (sid,), fetch="one")
    if not s:
        return send(cid, "❌ یافت نشد")
    if not confirmed:
        n = db_scalar("SELECT COUNT(*) FROM attendance_records WHERE session_id=?", (sid,))
        return send_or_edit(cid, (
            f"⚠️ حذف جلسه {s['session_no']}\n\n"
            f"✋ {n} رکورد حضور هم حذف می‌شود.\n\n"
            f"❗ قابل بازگشت نیست!"
        ), {"inline_keyboard": [
            [{"text": "🗑️ بله، حذف کن", "callback_data": f"att_dely_{sid}"}],
            [{"text": "🔙 انصراف", "callback_data": f"att_view_{sid}"}]]})
    eid = s["event_id"]
    db_execute("DELETE FROM attendance_records WHERE session_id=?", (sid,))
    db_execute("DELETE FROM attendance_sessions WHERE id=?", (sid,))
    send(cid, "🗑️ جلسه حذف شد")
    show_sessions(cid, uid, eid)


def announce_code(cid, uid, sid):
    """اعلام کد حضور به همه شرکت‌کنندگان"""
    if not _guard(cid, uid):
        return
    from events import get_event
    import time as _t

    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?", (sid,), fetch="one")
    if not s:
        return send(cid, "❌ یافت نشد")
    ev = get_event(s["event_id"])
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    targets = db_execute("""
        SELECT bale_user_id FROM event_registrations
        WHERE event_id=? AND status IN ('confirmed','attended')
          AND bale_user_id IS NOT NULL
    """, (s["event_id"],), fetch="all") or []

    if not targets:
        return send(cid, "📭 شرکت‌کننده‌ای وجود ندارد")

    text = (
        f"✋ ثبت حضور\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🎉 {ev['title']}\n"
        f"📋 {s.get('title') or 'جلسه'}\n\n"
        f"🔢 کد حضور: {s['session_code']}\n\n"
        f"💡 روی دکمه زیر بزنید و کد را وارد کنید."
    )
    kb = {"inline_keyboard": [
        [{"text": "✋ ثبت حضور من", "callback_data": f"uatt_{s['event_id']}"}]]}

    send(cid, f"⏳ ارسال به {len(targets)} نفر...")
    ok = 0
    for t in targets:
        if t.get("bale_user_id"):
            r = send(t["bale_user_id"], text, kb)
            if r.get("ok"):
                ok += 1
        _t.sleep(0.05)

    send(cid, f"✅ کد به {ok} نفر اعلام شد", {"inline_keyboard": [
        [{"text": "🔙 جلسه", "callback_data": f"att_view_{sid}"}]]})


def show_who(cid, uid, sid, page=0):
    """
    👥 فهرست حاضرین — با صفحه‌بندی واقعی.

    🔴 باگ: پارامتر page گرفته می‌شد ولی کاملاً نادیده گرفته
       می‌شد — همیشه LIMIT 20 ثابت. در جلسه‌ای با ۵۰ نفر،
       ۳۰ نفر آخر اصلاً دیده نمی‌شدند.
    """
    if not _guard(cid, uid):
        return
    per = 10
    total = db_scalar("SELECT COUNT(*) FROM attendance_records "
                      "WHERE session_id=?", (sid,)) or 0
    rows = db_execute("""
        SELECT r.*, u.first_name, u.last_name, u.mobile
        FROM attendance_records r LEFT JOIN users u ON u.id=r.user_id
        WHERE r.session_id=? ORDER BY r.id DESC LIMIT ? OFFSET ?
    """, (sid, per, page * per), fetch="all") or []

    if not rows and page == 0:
        return send_or_edit(cid, (
            "👥 حاضرین\n━━━━━━━━━━━━━━\n\n"
            "📭 هنوز کسی حضور نزده\n\n"
            "💡 کد جلسه را اعلام کنید یا دستی ثبت کنید."
        ), {"inline_keyboard": [
            [{"text": "📢 اعلام کد", "callback_data": f"att_announce_{sid}"}],
            [{"text": "✍️ ثبت دستی", "callback_data": f"att_manual_{sid}_0"}],
            [{"text": "🔙 جلسه", "callback_data": f"att_view_{sid}"}]]})

    pages = max(1, (total + per - 1) // per)
    page = max(0, min(page, pages - 1))
    st = session_stats(sid)

    lines = [f"👥 حاضرین ({total})", "━━━━━━━━━━━━━━", "",
             f"✅ {st['present']}  ⏰ {st['late']}  "
             f"📄 {st['excused']}", ""]
    for i, r in enumerate(rows, page * per + 1):
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or "بدون نام"
        m = ATT_METHODS.get(r.get("method") or "code", {}).get("icon", "•")
        lines.append(f"{i}. {ATT_ICONS.get(r.get('status'), '•')} {nm}  {m}")
        det = f"   📅 {_jd.fmt(r.get('created_at'), 'datetime')}"
        if r.get("distance_m") is not None:
            det += f" · 📍 {r['distance_m']}م"
        lines.append(det)

    btns = []
    for r in rows:
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or "بدون نام"
        btns.append([{"text": f"{ATT_ICONS.get(r.get('status'), '•')} {nm}"[:30],
                      "callback_data":
                          f"attst_{sid}_{r.get('bale_user_id')}_{page}"}])
    nav = []
    if page > 0:
        nav.append({"text": "◀️", "callback_data": f"att_who_{sid}_{page-1}"})
    nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
    if page < pages - 1:
        nav.append({"text": "▶️", "callback_data": f"att_who_{sid}_{page+1}"})
    if len(nav) > 1:
        btns.append(nav)
    btns += [[{"text": "✍️ ثبت دستی", "callback_data": f"att_manual_{sid}_0"}],
             [{"text": "🔙 جلسه", "callback_data": f"att_view_{sid}"}]]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_absent(cid, uid, sid, page=0):
    """
    ❌ فهرست غایبان — قابلیت کاملاً جدید.

    🎯 «حضور و غیاب واقعاً ضعیفه» — تا حالا فقط می‌شد دید چه
       کسی آمده. اینکه چه کسی *نیامده* مهم‌تر است: هم برای
       پیگیری، هم برای گواهینامه.
    """
    if not _guard(cid, uid):
        return
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (sid,), fetch="one")
    if not s:
        return send(cid, "❌ یافت نشد")

    per = 8
    rows = db_execute("""
        SELECT r.bale_user_id, u.first_name, u.last_name, u.mobile
        FROM event_registrations r LEFT JOIN users u ON u.id=r.user_id
        WHERE r.event_id=? AND r.status IN ('confirmed','attended')
          AND r.bale_user_id IS NOT NULL
          AND r.bale_user_id NOT IN (
              SELECT bale_user_id FROM attendance_records
              WHERE session_id=? AND bale_user_id IS NOT NULL)
        ORDER BY u.first_name LIMIT ? OFFSET ?
    """, (s["event_id"], sid, per, page * per), fetch="all") or []

    total = db_scalar("""
        SELECT COUNT(*) FROM event_registrations r
        WHERE r.event_id=? AND r.status IN ('confirmed','attended')
          AND r.bale_user_id IS NOT NULL
          AND r.bale_user_id NOT IN (
              SELECT bale_user_id FROM attendance_records
              WHERE session_id=? AND bale_user_id IS NOT NULL)
    """, (s["event_id"], sid)) or 0

    if not total:
        return send_or_edit(cid, (
            "❌ غایبان\n━━━━━━━━━━━━━━\n\n"
            "🎉 هیچ غایبی نیست — همه حاضرند! 💚"
        ), {"inline_keyboard": [
            [{"text": "🔙 جلسه", "callback_data": f"att_view_{sid}"}]]})

    pages = max(1, (total + per - 1) // per)
    page = max(0, min(page, pages - 1))
    lines = [f"❌ غایبان ({total})", "━━━━━━━━━━━━━━", "",
             "کسانی که هنوز حضور نزده‌اند:", ""]
    btns = []
    for i, r in enumerate(rows, page * per + 1):
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or "بدون نام"
        lines.append(f"{i}. ⬜ {nm}")
        if r.get("mobile"):
            lines.append(f"      📱 {r['mobile']}")
        btns.append([{"text": f"✅ حاضر کن: {nm}"[:34],
                      "callback_data":
                          f"attm_{sid}_{r['bale_user_id']}_0"}])

    nav = []
    if page > 0:
        nav.append({"text": "◀️", "callback_data": f"att_abs_{sid}_{page-1}"})
    nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
    if page < pages - 1:
        nav.append({"text": "▶️", "callback_data": f"att_abs_{sid}_{page+1}"})
    if len(nav) > 1:
        btns.append(nav)
    btns += [[{"text": f"📣 یادآوری به همه غایبان ({total})",
               "callback_data": f"att_remind_{sid}"}],
             [{"text": "🔙 جلسه", "callback_data": f"att_view_{sid}"}]]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def remind_absent(cid, uid, sid):
    """
    📣 یادآوری به غایبان.

    🎯 به‌جای اعلام کد به همه (که حاضرین را هم اذیت می‌کند)،
       فقط به کسانی که نیامده‌اند پیام می‌رود.
    """
    if not _guard(cid, uid):
        return
    from events import get_event
    import time as _t

    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (sid,), fetch="one")
    if not s:
        return send(cid, "❌ یافت نشد")
    if not s.get("is_open"):
        return send(cid, "🔴 جلسه بسته است — اول بازش کنید")
    ev = get_event(s["event_id"])

    rows = db_execute("""
        SELECT r.bale_user_id FROM event_registrations r
        WHERE r.event_id=? AND r.status IN ('confirmed','attended')
          AND r.bale_user_id IS NOT NULL
          AND r.bale_user_id NOT IN (
              SELECT bale_user_id FROM attendance_records
              WHERE session_id=? AND bale_user_id IS NOT NULL)
    """, (s["event_id"], sid), fetch="all") or []

    if not rows:
        return send(cid, "🎉 غایبی نیست!")

    text = (
        f"🌱 یادآوری حضور\n━━━━━━━━━━━━━━\n\n"
        f"🎉 {(ev or {}).get('title') or ''}\n"
        f"📋 {s.get('title') or 'جلسه'}\n\n"
        f"حضور شما هنوز ثبت نشده.\n"
        f"🔢 کد حضور: {s.get('session_code')}\n\n"
        f"💡 روی دکمه پایین بزنید و کد را وارد کنید."
    )
    kb = {"inline_keyboard": [
        [{"text": "✋ ثبت حضور من",
          "callback_data": f"uatt_{s['event_id']}"}]]}

    send(cid, f"⏳ ارسال به {len(rows)} غایب...")
    n = 0
    for r in rows:
        try:
            if send(r["bale_user_id"], text, kb).get("ok"):
                n += 1
        except Exception as e:
            log(f"⚠️ یادآوری حضور: {e}")
        _t.sleep(0.05)
    log_action(uid, "attendance_reminded",
               {"session_id": sid, "count": n})
    send_or_edit(cid, f"📣 به {n} نفر یادآوری شد 💚",
                 {"inline_keyboard": [
                     [{"text": "🔙 جلسه", "callback_data": f"att_view_{sid}"}]]})


def show_status_picker(cid, uid, sid, bale_uid, page=0):
    """
    🔀 تغییر وضعیت یک نفر — حاضر / تأخیر / غیبت موجه / غایب.

    🔴 باگ: toggle_manual فقط دو حالت داشت — حاضر یا هیچ.
       جدول چهار وضعیت پشتیبانی می‌کرد ولی ادمین فقط می‌توانست
       بین دوتاش جابه‌جا شود.
    """
    if not _guard(cid, uid):
        return
    u = get_user(bale_uid) or {}
    nm = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip() \
        or "بدون نام"
    rec = db_execute("SELECT * FROM attendance_records WHERE session_id=? "
                     "AND bale_user_id=?", (sid, bale_uid), fetch="one")
    cur = (rec or {}).get("status") or "absent"

    lines = [f"👤 {nm}", "━━━━━━━━━━━━━━", ""]
    if u.get("mobile"):
        lines.append(f"📱 {u['mobile']}")
    if rec:
        m = ATT_METHODS.get(rec.get("method") or "code", {})
        lines += [f"📅 ثبت: {_jd.fmt(rec.get('created_at'), 'datetime')}",
                  f"{m.get('icon', '•')} روش: {m.get('name', '-')}"]
    lines += ["", f"📌 وضعیت فعلی: {ATT_ICONS.get(cur, '⬜')} "
                  f"{ATT_STATUS_FA.get(cur, 'غایب')}", "",
              "وضعیت جدید را انتخاب کنید:"]

    btns = []
    for k, fa in ATT_STATUS_FA.items():
        mark = "🔘" if k == cur else "▫️"
        btns.append([{"text": f"{mark} {ATT_ICONS.get(k)} {fa}",
                      "callback_data": f"attsv_{sid}_{bale_uid}_{k}_{page}"}])
    btns.append([{"text": "🔙 بازگشت",
                  "callback_data": f"att_who_{sid}_{page}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_status(cid, uid, sid, bale_uid, status, page=0):
    """✅ اعمال وضعیت جدید"""
    if not _guard(cid, uid):
        return
    if status not in ATT_STATUS_FA:
        return send(cid, "❌ نامعتبر")
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (sid,), fetch="one")
    if not s:
        return send(cid, "❌ یافت نشد")

    ex = db_execute("SELECT * FROM attendance_records WHERE session_id=? "
                    "AND bale_user_id=?", (sid, bale_uid), fetch="one")
    if status == "absent":
        if ex:
            db_execute("DELETE FROM attendance_records WHERE id=?",
                       (ex["id"],))
    elif ex:
        db_execute("UPDATE attendance_records SET status=?, "
                   "recorded_by=? WHERE id=?", (status, uid, ex["id"]))
    else:
        u = get_user(bale_uid)
        db_execute("""INSERT OR IGNORE INTO attendance_records
            (session_id, event_id, user_id, bale_user_id, method,
             status, recorded_by) VALUES (?,?,?,?,'manual',?,?)""",
            (sid, s["event_id"], (u or {}).get("id"), bale_uid,
             status, uid))
        if status in ("present", "late"):
            _award_points(bale_uid, s.get("points") or 0)

    log_action(uid, "attendance_status_set",
               {"session_id": sid, "user": bale_uid, "status": status})
    send(cid, f"✅ {ATT_STATUS_FA[status]} ثبت شد")
    return show_status_picker(cid, uid, sid, bale_uid, page)


def manual_list(cid, uid, sid, page=0):
    """لیست ثبت‌نامی‌ها برای تیک زدن دستی"""
    if not _guard(cid, uid):
        return
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?", (sid,), fetch="one")
    if not s:
        return send(cid, "❌ یافت نشد")

    per = 8
    rows = db_execute("""
        SELECT r.user_id, r.bale_user_id, u.first_name, u.last_name,
               (SELECT status FROM attendance_records a
                WHERE a.session_id=? AND a.bale_user_id=r.bale_user_id) AS att
        FROM event_registrations r LEFT JOIN users u ON u.id=r.user_id
        WHERE r.event_id=? AND r.status IN ('confirmed','attended')
        ORDER BY u.first_name LIMIT ? OFFSET ?
    """, (sid, s["event_id"], per, page * per), fetch="all") or []

    total = db_scalar(
        "SELECT COUNT(*) FROM event_registrations "
        "WHERE event_id=? AND status IN ('confirmed','attended')", (s["event_id"],))

    if not rows:
        return send_or_edit(cid, "📭 شرکت‌کننده‌ای نیست", {"inline_keyboard": [
            [{"text": "🔙 جلسه", "callback_data": f"att_view_{sid}"}]]})

    pages = max(1, (total + per - 1) // per)
    btns = []
    for r in rows:
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or "بدون نام"
        mark = "✅" if r.get("att") == "present" else "⬜"
        btns.append([{"text": f"{mark} {nm}"[:40],
                      "callback_data": f"attm_{sid}_{r['bale_user_id']}_{page}"}])

    nav = []
    if page > 0:
        nav.append({"text": "◀️", "callback_data": f"att_manual_{sid}_{page-1}"})
    nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
    if page < pages - 1:
        nav.append({"text": "▶️", "callback_data": f"att_manual_{sid}_{page+1}"})
    if len(nav) > 1:
        btns.append(nav)

    st = session_stats(sid, s["event_id"])
    btns.append([{"text": f"✅ همه را حاضر کن ({st['absent']})",
                  "callback_data": f"att_all_{sid}"}])
    if st["present"] or st["late"]:
        btns.append([{"text": "🧹 پاک کردن همه حضورها",
                      "callback_data": f"att_clr_{sid}"}])
    btns.append([{"text": "🔙 جلسه", "callback_data": f"att_view_{sid}"}])

    send_or_edit(cid, (
        f"✍️ ثبت دستی حضور\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"✅ {st['present']}  ⏰ {st['late']}  "
        f"📄 {st['excused']}  ❌ {st['absent']}\n\n"
        f"روی هر نفر بزنید تا حاضر/غایب شود:\n"
        f"💡 برای «تأخیر» یا «غیبت موجه» از فهرست\n"
        f"   حاضرین روی نام بزنید."
    ), {"inline_keyboard": btns})


def toggle_manual(cid, uid, sid, target_bale, page=0):
    """
    ✍️ تیک زدن سریع حاضر/غایب.

    برای تغییر به «تأخیر» یا «غیبت موجه» از کارت نفر
    (show_status_picker) استفاده کنید.
    """
    if not _guard(cid, uid):
        return
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?", (sid,), fetch="one")
    if not s:
        return
    ex = db_execute(
        "SELECT * FROM attendance_records WHERE session_id=? AND bale_user_id=?",
        (sid, target_bale), fetch="one")
    if ex:
        db_execute("DELETE FROM attendance_records WHERE id=?", (ex["id"],))
    else:
        u = get_user(target_bale)
        db_execute("""INSERT OR IGNORE INTO attendance_records
            (session_id, event_id, user_id, bale_user_id, method, status, recorded_by)
            VALUES (?,?,?,?,'manual','present',?)""",
            (sid, s["event_id"], (u or {}).get("id"), target_bale, uid))
        _award_points(target_bale, s.get("points") or 0)
    manual_list(cid, uid, sid, page)


def mark_all(cid, uid, sid, confirmed=False):
    """
    ✅ همه را یکجا حاضر کن.

    🎯 در جلسه‌ای با ۴۰ نفر، تیک زدن یکی‌یکی آزاردهنده است.
       معمولاً همه می‌آیند و فقط چند نفر غایب‌اند — این دکمه
       همه را حاضر می‌کند و بعد چند غایب را برمی‌دارید.
    """
    if not _guard(cid, uid):
        return
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?",
                   (sid,), fetch="one")
    if not s:
        return send(cid, "❌ یافت نشد")

    todo = db_scalar("""
        SELECT COUNT(*) FROM event_registrations r
        WHERE r.event_id=? AND r.status IN ('confirmed','attended')
          AND r.bale_user_id IS NOT NULL
          AND r.bale_user_id NOT IN (
              SELECT bale_user_id FROM attendance_records
              WHERE session_id=? AND bale_user_id IS NOT NULL)
    """, (s["event_id"], sid)) or 0

    if not todo:
        return send(cid, "🎉 همه از قبل ثبت شده‌اند!")

    if not confirmed:
        return send_or_edit(cid, (
            f"✅ حاضر کردن همه\n━━━━━━━━━━━━━━\n\n"
            f"👥 {todo} نفر که هنوز ثبت نشده‌اند\n"
            f"   «حاضر» علامت می‌خورند.\n\n"
            f"🏆 امتیاز {s.get('points') or 0} هم به هرکدام\n"
            f"   داده می‌شود.\n\n"
            f"💡 بعدش می‌توانید غایبان را تک‌تک بردارید."
        ), {"inline_keyboard": [
            [{"text": f"✅ بله، {todo} نفر را حاضر کن",
              "callback_data": f"att_ally_{sid}"}],
            [{"text": "❌ انصراف", "callback_data": f"att_manual_{sid}_0"}]]})

    rows = db_execute("""
        SELECT r.bale_user_id, r.user_id FROM event_registrations r
        WHERE r.event_id=? AND r.status IN ('confirmed','attended')
          AND r.bale_user_id IS NOT NULL
          AND r.bale_user_id NOT IN (
              SELECT bale_user_id FROM attendance_records
              WHERE session_id=? AND bale_user_id IS NOT NULL)
    """, (s["event_id"], sid), fetch="all") or []

    n = 0
    for r in rows:
        got = db_execute("""INSERT OR IGNORE INTO attendance_records
            (session_id, event_id, user_id, bale_user_id, method,
             status, recorded_by) VALUES (?,?,?,?,'manual','present',?)""",
            (sid, s["event_id"], r.get("user_id"), r["bale_user_id"], uid))
        if got:
            n += 1
            _award_points(r["bale_user_id"], s.get("points") or 0)
    log_action(uid, "attendance_mark_all", {"session_id": sid, "count": n})
    send(cid, f"✅ {n} نفر حاضر شدند 💚")
    return manual_list(cid, uid, sid, 0)


def clear_all(cid, uid, sid, confirmed=False):
    """🧹 پاک کردن همه حضورهای جلسه"""
    if not _guard(cid, uid):
        return
    n = db_scalar("SELECT COUNT(*) FROM attendance_records "
                  "WHERE session_id=?", (sid,)) or 0
    if not n:
        return send(cid, "📭 چیزی برای پاک کردن نیست")
    if not confirmed:
        return send_or_edit(cid, (
            f"🧹 پاک کردن حضورها\n━━━━━━━━━━━━━━\n\n"
            f"⚠️ {n} رکورد حضور این جلسه پاک می‌شود.\n\n"
            f"❗ قابل بازگشت نیست!"
        ), {"inline_keyboard": [
            [{"text": "🧹 بله، پاک کن",
              "callback_data": f"att_clry_{sid}"}],
            [{"text": "❌ انصراف", "callback_data": f"att_view_{sid}"}]]})
    db_execute("DELETE FROM attendance_records WHERE session_id=?", (sid,))
    log_action(uid, "attendance_cleared", {"session_id": sid, "count": n})
    send(cid, f"🧹 {n} رکورد پاک شد")
    return show_session(cid, uid, sid)


def _award_points(bale_id, pts):
    if pts and bale_id:
        db_execute(
            "UPDATE users SET total_points=COALESCE(total_points,0)+? WHERE bale_user_id=?",
            (pts, bale_id))


# ==================== کاربر: ثبت حضور ====================
def user_attendance_menu(cid, uid, eid=None):
    """منوی حضور و غیاب کاربر"""
    if eid:
        return start_check_in(cid, uid, eid)

    rows = db_execute("""
        SELECT DISTINCT e.id, e.title, e.event_type
        FROM event_registrations r JOIN events e ON e.id=r.event_id
        WHERE r.bale_user_id=? AND r.status IN ('confirmed','attended')
          AND e.has_attendance=1 AND e.status IN ('published','closed')
        ORDER BY e.id DESC LIMIT 10
    """, (uid,), fetch="all") or []

    if not rows:
        return send_or_edit(cid, (
            "✋ حضور و غیاب\n"
            "━━━━━━━━━━━━━━\n\n"
            "📭 رویداد فعالی با حضور و غیاب ندارید.\n\n"
            "💡 ابتدا در یک رویداد ثبت‌نام کنید."
        ), {"inline_keyboard": [
            [{"text": "🎉 رویدادها", "callback_data": "u_events"}],
            [{"text": "📊 کارنامه من", "callback_data": "u_att_report"}],
            [{"text": "🔙 منوی اصلی", "callback_data": "back_main"}]]})

    from events import EVENT_TYPES
    btns = []
    for e in rows:
        t = EVENT_TYPES.get(e.get("event_type") or "meeting", EVENT_TYPES["meeting"])
        btns.append([{"text": f"{t['icon']} {e['title']}"[:45],
                      "callback_data": f"uatt_{e['id']}"}])
    btns.append([{"text": "📊 کارنامه من", "callback_data": "u_att_report"},
                 {"text": "📄 غیبت مجاز", "callback_data": "exq_new"}])
    btns.append([{"text": "🔙 منوی اصلی", "callback_data": "back_main"}])

    send_or_edit(cid, (
        "✋ حضور و غیاب\n"
        "━━━━━━━━━━━━━━\n\n"
        "رویداد را انتخاب کنید:"
    ), {"inline_keyboard": btns})


def start_check_in(cid, uid, eid):
    """شروع ثبت حضور برای یک رویداد"""
    from events import get_event

    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    reg = db_execute(
        "SELECT * FROM event_registrations WHERE event_id=? AND bale_user_id=?",
        (eid, uid), fetch="one")
    if not reg or reg.get("status") not in ("confirmed", "attended"):
        return send(cid, "⚠️ شما در این رویداد ثبت‌نام تأییدشده ندارید")

    sessions = db_execute(
        "SELECT * FROM attendance_sessions WHERE event_id=? AND is_open=1 "
        "ORDER BY session_no", (eid,), fetch="all") or []

    if not sessions:
        return send_or_edit(cid, (
            f"✋ {ev['title']}\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"⏳ در حال حاضر جلسه بازی برای ثبت حضور نیست.\n\n"
            f"💡 وقتی جلسه شروع شود، ادمین کد را اعلام می‌کند."
        ), {"inline_keyboard": [
            [{"text": "📊 کارنامه من", "callback_data": f"uatt_rep_{eid}"}],
            [{"text": "🔙 بازگشت", "callback_data": "u_attendance"}]]})

    # اگر فقط یک جلسه باز است، مستقیم برو
    if len(sessions) == 1:
        return ask_code(cid, uid, sessions[0]["id"])

    btns = [[{"text": f"📋 {ss.get('title') or ('جلسه ' + str(ss.get('session_no') or ''))}"[:40],
              "callback_data": f"uatts_{ss['id']}"}] for ss in sessions]
    btns.append([{"text": "🔙 بازگشت", "callback_data": "u_attendance"}])
    send_or_edit(cid, "📋 کدام جلسه؟", {"inline_keyboard": btns})


def ask_code(cid, uid, sid):
    """درخواست کد از کاربر"""
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?", (sid,), fetch="one")
    if not s:
        return send(cid, "❌ جلسه یافت نشد")
    if not s.get("is_open"):
        return send(cid, "🔴 این جلسه بسته شده است")

    ex = db_execute(
        "SELECT * FROM attendance_records WHERE session_id=? AND bale_user_id=?",
        (sid, uid), fetch="one")
    if ex:
        return send(cid, (
            f"✅ حضور شما قبلاً ثبت شده\n\n"
            f"📅 {_jd.fmt(ex.get('created_at'), 'datetime')}"
        ), {"inline_keyboard": [
            [{"text": "🔙 بازگشت", "callback_data": "u_attendance"}]]})

    method = s.get("method") or "code"

    if method == "location":
        set_state(uid, STATE_ATT_LOC, {"sid": sid}, merge=False)
        return send(cid, (
            "📍 ثبت حضور با موقعیت مکانی\n"
            "━━━━━━━━━━━━━━\n\n"
            "روی دکمه پایین بزنید تا موقعیت شما ارسال شود.\n\n"
            "⚠️ باید در محل رویداد باشید."
        ), kb_location())

    set_state(uid, STATE_ATT_CODE, {"sid": sid}, merge=False)
    send(cid, (
        f"✋ ثبت حضور\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"📋 {s.get('title') or 'جلسه'}\n\n"
        f"🔢 کد حضور را وارد کنید:\n"
        f"(کدی که ادمین اعلام کرده)"
    ), kb_cancel())


def handle_code(message):
    """پردازش کد ورودی کاربر"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    if text == BTN_BACK:
        clear_state(uid)
        return user_attendance_menu(cid, uid)

    data = get_state_data(uid)
    sid = data.get("sid")
    if not sid:
        clear_state(uid)
        return send(cid, "⏰ منقضی شد. دوباره تلاش کنید", kb_remove())

    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?", (sid,), fetch="one")
    if not s:
        clear_state(uid)
        return send(cid, "❌ جلسه یافت نشد", kb_remove())
    if not s.get("is_open"):
        clear_state(uid)
        return send(cid, "🔴 این جلسه بسته شد", kb_remove())

    code = normalize_digits(text).strip()

    # کد جلسه یا کد بلیت — هر دو قبول
    valid = False
    method = "code"
    if code == str(s.get("session_code") or ""):
        valid = True
    else:
        reg = db_execute("""SELECT * FROM event_registrations
            WHERE event_id=? AND bale_user_id=? AND UPPER(ticket_code)=?""",
            (s["event_id"], uid, code.upper()), fetch="one")
        if reg:
            valid = True
            method = "ticket"

    if not valid:
        return send(cid, (
            "❌ کد اشتباه است\n\n"
            "💡 کد جلسه یا کد بلیت خودتان را وارد کنید."
        ))

    return record_attendance(cid, uid, s, method)


def record_attendance(cid, uid, s, method, lat=None, lon=None, dist=None):
    """ثبت نهایی حضور"""
    from events import get_event

    u = get_user(uid)
    rid = db_execute("""INSERT OR IGNORE INTO attendance_records
        (session_id, event_id, user_id, bale_user_id, method, status,
         lat, lon, distance_m)
        VALUES (?,?,?,?,?,'present',?,?,?)""",
        (s["id"], s["event_id"], (u or {}).get("id"), uid, method, lat, lon, dist))

    clear_state(uid)

    pts = s.get("points") or 0
    _award_points(uid, pts)

    db_execute("""UPDATE event_registrations
        SET attended=1, attended_at=CURRENT_TIMESTAMP, status='attended'
        WHERE event_id=? AND bale_user_id=?""", (s["event_id"], uid))

    # 🏅 امتیاز شرطی (حضور و کارگاه)
    try:
        import occasions as _oc
        _oc.check_point_rules(uid, "event_attend")
        _oc.check_point_rules(uid, "workshop_attend")
    except Exception as _e:
        log(f"⚠️ امتیاز شرطی: {_e}")

    try:
        import club as _cl
        _cl.check_achievements(uid, "event_attend")
    except Exception as _e:
        log(f"⚠️ دستاورد: {_e}")

    ev = get_event(s["event_id"])
    lines = [
        "✅ حضور شما ثبت شد!",
        "━━━━━━━━━━━━━━",
        "",
        f"🎉 {(ev or {}).get('title') or '-'}",
        f"📋 {s.get('title') or 'جلسه'}",
        f"🕐 {datetime.now().strftime('%H:%M')}",
    ]
    if pts:
        total = (get_user(uid) or {}).get("total_points") or 0
        lines += ["", f"🏆 {pts} امتیاز گرفتید!", f"📊 مجموع امتیاز شما: {total}"]

    btns = [[{"text": "📊 کارنامه من", "callback_data": "u_att_report"}]]
    if ev and ev.get("has_certificate"):
        # 🔒 فاز ۳۹ — دکمهٔ «دریافت گواهینامه» فقط وقتی که
        #    صدور خودسرویس باز باشد.
        #
        #    🎯 «چرا بعد اعلام کد حضور میتونه گواهی خودشو بسازه؟»
        #    پیش‌فرض بسته است، پس به‌جای دکمه فقط یک نوید
        #    مهربان می‌دهیم.
        _self = True
        try:
            import certissue as _ci
            _self = _ci.self_issue_allowed()
        except ImportError:
            pass
        if _self:
            btns.append([{"text": "🎓 دریافت گواهینامه",
                          "callback_data": f"ucert_{s['event_id']}"}])
        else:
            lines += ["", "🎓 گواهینامه‌تان پس از تأیید برگزارکننده",
                      "   صادر و همین‌جا فرستاده می‌شود 💚"]
            btns.append([{"text": "🎓 گواهینامه‌های من",
                          "callback_data": "u_my_certs"}])
    btns.append([{"text": "🔙 منوی اصلی", "callback_data": "back_main"}])

    send(cid, "\n".join(lines), kb_remove())
    send_or_edit(cid, "👇", {"inline_keyboard": btns})
    log_action(uid, "attendance", {"session": s["id"], "method": method})


def handle_location(message):
    """ثبت حضور با موقعیت مکانی"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]

    if (message.get("text") or "").strip() == BTN_BACK:
        clear_state(uid)
        return user_attendance_menu(cid, uid)

    loc = message.get("location")
    if not loc:
        return send(cid, "📍 لطفاً موقعیت خود را از دکمه پایین ارسال کنید")

    data = get_state_data(uid)
    sid = data.get("sid")
    s = db_execute("SELECT * FROM attendance_sessions WHERE id=?", (sid,), fetch="one") \
        if sid else None
    if not s:
        clear_state(uid)
        return send(cid, "⏰ منقضی شد", kb_remove())

    lat, lon = float(loc.get("latitude") or 0), float(loc.get("longitude") or 0)

    if s.get("lat") and s.get("lon"):
        dist = _haversine(lat, lon, s["lat"], s["lon"])
        radius = int(s.get("radius_m") or 200)
        if dist > radius:
            return send(cid, (
                f"❌ شما در محل رویداد نیستید\n\n"
                f"📏 فاصله شما: {int(dist)} متر\n"
                f"✅ حداکثر مجاز: {radius} متر"
            ), kb_remove())
        return record_attendance(cid, uid, s, "location", lat, lon, int(dist))

    record_attendance(cid, uid, s, "location", lat, lon, None)


def _haversine(lat1, lon1, lat2, lon2):
    """فاصله دو نقطه به متر"""
    import math
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ==================== کارنامه ====================
# ══════════════════════════════════════════════════════════
# 📄 فاز ۱۵ — درخواست غیبت مجاز
# ══════════════════════════════════════════════════════════
def start_excuse(cid, uid, eid=None):
    """📄 کاربر درخواست غیبت مجاز می‌دهد"""
    rows = db_execute("""SELECT DISTINCT e.id, e.title FROM events e
        JOIN event_registrations r ON r.event_id=e.id
        WHERE r.bale_user_id=? AND r.status IN ('confirmed','attended')
          AND e.has_attendance=1 AND e.status IN ('published','closed')
        ORDER BY e.id DESC LIMIT 10""", (uid,), fetch="all") or []

    if not rows:
        return send_or_edit(cid, (
            "📄 درخواست غیبت مجاز\n━━━━━━━━━━━━━━\n\n"
            "📭 رویداد فعالی ندارید."
        ), {"inline_keyboard": [
            [{"text": "🔙 بازگشت", "callback_data": "u_attendance"}]]})

    if eid is None:
        btns = [[{"text": r["title"][:42],
                  "callback_data": f"exqe_{r['id']}"}] for r in rows]
        btns.append([{"text": "🔙 بازگشت", "callback_data": "u_attendance"}])
        return send_or_edit(cid, (
            "📄 درخواست غیبت مجاز\n━━━━━━━━━━━━━━\n\n"
            "برای کدام رویداد نمی‌توانید حاضر شوید؟"
        ), {"inline_keyboard": btns})

    ev = db_execute("SELECT * FROM events WHERE id=?", (eid,), fetch="one")
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")
    set_state(uid, STATE_ATT_EXCUSE, {"eid": eid}, merge=False)
    send(cid, (
        f"📄 درخواست غیبت مجاز\n━━━━━━━━━━━━━━\n\n"
        f"🎉 {ev['title']}\n\n"
        f"دلیل غیبت خود را بنویسید:\n\n"
        f"💡 می‌توانید عکس مدرک هم بفرستید."
    ), kb_cancel())


def handle_excuse(message):
    """دریافت دلیل غیبت (متن یا عکس)"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or message.get("caption") or "").strip()
    d = get_state_data(uid)
    eid = d.get("eid")

    if text in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        return send(cid, "❌ لغو شد", kb_remove())

    photo = ""
    if message.get("photo"):
        try:
            photo = max(message["photo"],
                        key=lambda p: p.get("file_size") or 0)["file_id"]
        except (ValueError, KeyError, TypeError):
            photo = ""
    if not text and not photo:
        return send(cid, "⚠️ دلیل غیبت را بنویسید:")

    ev = db_execute("SELECT * FROM events WHERE id=?", (eid,), fetch="one")
    if not ev:
        clear_state(uid)
        return send(cid, "❌ رویداد یافت نشد", kb_remove())

    rid = db_execute("""INSERT INTO excuse_requests
        (event_id, bale_user_id, reason, proof_file_id)
        VALUES (?,?,?,?)""", (eid, uid, text[:1000], photo))
    clear_state(uid)
    log_action(uid, "excuse_request", {"eid": eid})

    send(cid, (
        "✅ درخواست شما ثبت شد\n━━━━━━━━━━━━━━\n\n"
        f"🔖 شماره: #{rid}\n"
        "⏳ پس از بررسی ادمین، به شما اطلاع داده می‌شود."
    ), kb_remove())

    u = get_user(uid) or {}
    nm = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip()
    _notify_admins_excuse(
        f"📄 درخواست غیبت مجاز\n━━━━━━━━━━━━━━\n\n"
        f"🎉 {ev['title']}\n"
        f"👤 {nm or '—'}\n"
        f"📱 {u.get('mobile') or '—'}\n\n"
        f"📝 دلیل:\n{text or '(فقط عکس)'}",
        {"inline_keyboard": [
            [{"text": "✅ تأیید", "callback_data": f"exok_{rid}"},
             {"text": "❌ رد", "callback_data": f"exno_{rid}"}]]})


def _notify_admins_excuse(text, kb=None):
    rows = db_execute("SELECT bale_user_id FROM users WHERE is_admin=1 "
                      "AND bale_user_id IS NOT NULL", fetch="all") or []
    for r in rows:
        try:
            send(r["bale_user_id"], text, kb)
        except Exception as e:
            log(f"⚠️ اعلان غیبت: {e}")


def show_excuses(cid, uid, page=0):
    """📄 لیست درخواست‌های غیبت (ادمین)"""
    if not _guard(cid, uid):
        return
    rows = db_execute("""SELECT x.*, u.first_name, u.last_name, u.mobile,
        e.title ev_title FROM excuse_requests x
        LEFT JOIN users u ON u.bale_user_id=x.bale_user_id
        LEFT JOIN events e ON e.id=x.event_id
        WHERE x.status='pending' ORDER BY x.id DESC LIMIT 20""",
        fetch="all") or []

    lines = ["📄 درخواست‌های غیبت مجاز", "━━━━━━━━━━━━━━", ""]
    btns = []
    if not rows:
        lines.append("✅ درخواست در انتظاری نیست")
    for r in rows:
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
        lines += [f"👤 {nm or '—'} — {str(r.get('ev_title') or '')[:26]}",
                  f"   📝 {str(r.get('reason') or '')[:60]}",
                  f"   📅 {_jd.fmt(r.get('created_at'), 'datetime')}", ""]
        btns.append([
            {"text": f"✅ {nm}"[:20], "callback_data": f"exok_{r['id']}"},
            {"text": "❌ رد", "callback_data": f"exno_{r['id']}"},
        ])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "admin_panel"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def review_excuse(cid, uid, rid, approve=True):
    """✅/❌ بررسی درخواست غیبت"""
    if not _guard(cid, uid):
        return
    try:
        rid = int(rid)
    except (TypeError, ValueError):
        return send(cid, "❌ شناسه نامعتبر")
    r = db_execute("SELECT * FROM excuse_requests WHERE id=?", (rid,),
                   fetch="one")
    if not r:
        return send(cid, "❌ درخواست یافت نشد")
    if r.get("status") != "pending":
        return send(cid, f"ℹ️ قبلاً بررسی شده ({r.get('status')})")

    db_execute("""UPDATE excuse_requests SET status=?, reviewed_by=?,
        reviewed_at=CURRENT_TIMESTAMP WHERE id=?""",
        ("approved" if approve else "rejected", uid, rid))

    # اگر تأیید شد، رکورد حضور با وضعیت «معذور» ثبت شود
    if approve and r.get("event_id"):
        sess = db_execute("""SELECT id FROM attendance_sessions
            WHERE event_id=? ORDER BY id DESC LIMIT 1""",
            (r["event_id"],), fetch="one")
        if sess:
            exists = db_execute("""SELECT id FROM attendance_records
                WHERE session_id=? AND bale_user_id=?""",
                (sess["id"], r["bale_user_id"]), fetch="one")
            if not exists:
                db_execute("""INSERT INTO attendance_records
                    (session_id, event_id, bale_user_id, method, status)
                    VALUES (?,?,?,'manual','excused')""",
                    (sess["id"], r["event_id"], r["bale_user_id"]))

    log_action(uid, "excuse_reviewed", {"rid": rid, "ok": approve})
    send(cid, "✅ درخواست تأیید شد" if approve else "❌ درخواست رد شد")
    if r.get("bale_user_id"):
        try:
            send(r["bale_user_id"],
                 "✅ درخواست غیبت مجاز شما تأیید شد\n\n"
                 "💚 غیبت شما موجه ثبت شد." if approve else
                 "❌ درخواست غیبت مجاز شما تأیید نشد\n\n"
                 "💡 برای اطلاعات بیشتر با پشتیبانی تماس بگیرید.")
        except Exception as e:
            log(f"⚠️ اعلام نتیجه غیبت: {e}")
    return show_excuses(cid, uid)


def user_report(cid, uid, eid=None):
    """کارنامه حضور کاربر"""
    if eid:
        rows = db_execute("""
            SELECT s.session_no, s.title, r.status, r.created_at
            FROM attendance_sessions s
            LEFT JOIN attendance_records r
              ON r.session_id=s.id AND r.bale_user_id=?
            WHERE s.event_id=? ORDER BY s.session_no
        """, (uid, eid), fetch="all") or []
        from events import get_event
        ev = get_event(eid)
        title = (ev or {}).get("title") or "-"
        present = sum(1 for r in rows if r.get("status") == "present")
        lines = [f"📊 کارنامه «{title}»", "━━━━━━━━━━━━━━", ""]
        for r in rows:
            mark = "✅" if r.get("status") == "present" else "❌"
            lines.append(f"{mark} جلسه {r['session_no']}: {r.get('title') or ''}")
        rate = f"{present * 100 // len(rows)}%" if rows else "-"
        lines += ["", f"📈 نرخ حضور: {present} از {len(rows)} ({rate})"]
        back = f"uatt_{eid}"
    else:
        total = db_scalar(
            "SELECT COUNT(*) FROM attendance_records WHERE bale_user_id=? "
            "AND status='present'", (uid,))
        events_n = db_scalar(
            "SELECT COUNT(DISTINCT event_id) FROM attendance_records "
            "WHERE bale_user_id=? AND status='present'", (uid,))
        u = get_user(uid)
        certs = db_scalar("SELECT COUNT(*) FROM certificates WHERE bale_user_id=?", (uid,))

        recent = db_execute("""
            SELECT e.title, s.title AS stitle, r.created_at
            FROM attendance_records r
            JOIN attendance_sessions s ON s.id=r.session_id
            JOIN events e ON e.id=r.event_id
            WHERE r.bale_user_id=? ORDER BY r.id DESC LIMIT 8
        """, (uid,), fetch="all") or []

        lines = [
            "📊 کارنامه حضور من",
            "━━━━━━━━━━━━━━",
            "",
            f"✅ کل حضور: {total} جلسه",
            f"🎉 در {events_n} رویداد",
            f"🏆 امتیاز: {(u or {}).get('total_points') or 0}",
            f"🎓 گواهینامه‌ها: {certs}",
        ]
        if recent:
            lines += ["", "🕐 آخرین حضورها:"]
            for r in recent:
                lines.append(f"• {r['title']} — {_jd.fmt(r.get('created_at'), 'date')}")
        back = "u_attendance"

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": back}]]})


def event_attendance_report(cid, uid, eid):
    """گزارش کلی حضور یک رویداد برای ادمین"""
    if not _guard(cid, uid):
        return
    from events import get_event

    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")

    sessions = db_execute(
        "SELECT * FROM attendance_sessions WHERE event_id=? ORDER BY session_no",
        (eid,), fetch="all") or []
    if not sessions:
        return send(cid, "📭 جلسه‌ای تعریف نشده")

    confirmed = db_scalar(
        "SELECT COUNT(*) FROM event_registrations "
        "WHERE event_id=? AND status IN ('confirmed','attended')", (eid,))

    lines = [f"📊 کارنامه «{ev['title']}»", "━━━━━━━━━━━━━━", "",
             f"👥 ثبت‌نامی: {confirmed}", f"📋 جلسات: {len(sessions)}", ""]

    total_p = 0
    for s in sessions:
        p = db_scalar(
            "SELECT COUNT(*) FROM attendance_records WHERE session_id=? AND status='present'",
            (s["id"],))
        total_p += p
        rate = f"{p * 100 // confirmed}%" if confirmed else "-"
        lines.append(f"📋 جلسه {s['session_no']}: {p}/{confirmed} ({rate})")

    if sessions and confirmed:
        avg = total_p * 100 // (len(sessions) * confirmed)
        lines += ["", f"📈 میانگین حضور: {avg}%"]

    # برترین‌ها
    top = db_execute("""
        SELECT u.first_name, u.last_name, COUNT(*) n
        FROM attendance_records r JOIN users u ON u.id=r.user_id
        WHERE r.event_id=? AND r.status='present'
        GROUP BY r.bale_user_id ORDER BY n DESC LIMIT 5
    """, (eid,), fetch="all") or []
    if top:
        lines += ["", "🥇 منظم‌ترین‌ها:"]
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, t in enumerate(top):
            nm = f"{t.get('first_name') or ''} {t.get('last_name') or ''}".strip()
            lines.append(f"{medals[i]} {nm or 'کاربر'} — {t['n']} جلسه")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "📤 خروجی اکسل", "callback_data": f"att_export_{eid}"}],
        [{"text": "🎓 صدور گواهینامه گروهی", "callback_data": f"cert_bulk_{eid}"}],
        [{"text": "🔙 جلسات", "callback_data": f"att_list_{eid}"}],
    ]})


def export_attendance(cid, uid, eid):
    if not _guard(cid, uid):
        return
    try:
        import openpyxl
        from openpyxl.styles import Font
    except ImportError:
        return send(cid, "❌ openpyxl نصب نیست")

    from events import get_event
    from config import IMPORT_DIR

    ev = get_event(eid)
    sessions = db_execute(
        "SELECT * FROM attendance_sessions WHERE event_id=? ORDER BY session_no",
        (eid,), fetch="all") or []
    regs = db_execute("""
        SELECT r.bale_user_id, u.first_name, u.last_name, u.mobile, u.national_id
        FROM event_registrations r LEFT JOIN users u ON u.id=r.user_id
        WHERE r.event_id=? AND r.status IN ('confirmed','attended')
        ORDER BY u.first_name
    """, (eid,), fetch="all") or []

    if not regs:
        return send(cid, "📭 داده‌ای نیست")

    send(cid, "⏳ در حال ساخت فایل...")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "حضور و غیاب"
    ws.sheet_view.rightToLeft = True

    heads = ["ردیف", "نام", "نام خانوادگی", "موبایل", "کد ملی"]
    heads += [f"جلسه {s['session_no']}" for s in sessions]
    heads += ["مجموع حضور", "درصد"]
    ws.append(heads)
    for c in ws[1]:
        c.font = Font(bold=True)

    for i, r in enumerate(regs, 1):
        row = [i, r.get("first_name") or "", r.get("last_name") or "",
               r.get("mobile") or "", r.get("national_id") or ""]
        cnt = 0
        for s in sessions:
            rec = db_execute(
                "SELECT status FROM attendance_records WHERE session_id=? AND bale_user_id=?",
                (s["id"], r["bale_user_id"]), fetch="one")
            if rec and rec.get("status") == "present":
                row.append("حاضر")
                cnt += 1
            else:
                row.append("غایب")
        row.append(cnt)
        row.append(f"{cnt * 100 // len(sessions)}%" if sessions else "-")
        ws.append(row)

    for i in range(1, len(heads) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = 14
    ws.freeze_panes = "B2"

    Path(IMPORT_DIR).mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in (ev or {}).get("title", "event")
                   if c.isalnum() or c in " -_")[:25]
    out = Path(IMPORT_DIR) / f"attendance_{eid}_{safe}.xlsx"
    wb.save(out)
    send_document(cid, str(out), f"📊 حضور و غیاب «{(ev or {}).get('title')}»")


# ==================== 🎓 گواهینامه ====================
DEFAULT_CERT = """🎓 گواهینامه

بدینوسیله گواهی می‌شود

{name}

در {event}
که در تاریخ {date} برگزار گردید
شرکت نموده است.

{org}
شماره گواهینامه: {serial}"""


def show_cert_settings(cid, uid):
    """تنظیمات قالب گواهینامه"""
    if not _guard(cid, uid):
        return
    tpl = get_setting("cert_template", DEFAULT_CERT)
    total = db_scalar("SELECT COUNT(*) FROM certificates")

    send_or_edit(cid, (
        f"🎓 تنظیمات گواهینامه\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"📄 قالب فعلی:\n\n{tpl[:800]}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"📊 گواهینامه‌های صادرشده: {total}\n\n"
        f"💡 متغیرهای قابل استفاده:\n"
        f"{{name}} نام کامل\n"
        f"{{event}} عنوان رویداد\n"
        f"{{date}} تاریخ رویداد\n"
        f"{{org}} نام سازمان\n"
        f"{{serial}} شماره گواهینامه\n"
        f"{{national_id}} کد ملی\n"
        f"{{sessions}} تعداد جلسات حاضر"
    ), {"inline_keyboard": [
        [{"text": "✏️ ویرایش قالب", "callback_data": "cert_edit"}],
        [{"text": "♻️ بازگردانی پیش‌فرض", "callback_data": "cert_reset"}],
        [{"text": "👁️ پیش‌نمایش", "callback_data": "cert_preview"}],
        [{"text": "🔙 تنظیمات", "callback_data": "admin_settings"}],
    ]})


def start_cert_edit(cid, uid):
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_CERT_EDIT, {}, merge=False)
    send(cid, (
        "✏️ ویرایش قالب گواهینامه\n"
        "━━━━━━━━━━━━━━\n\n"
        "متن جدید را بفرستید.\n\n"
        "💡 متغیرها:\n"
        "{name} {event} {date} {org} {serial} {national_id} {sessions}"
    ), kb_cancel())


def handle_cert_edit(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    if text == BTN_BACK:
        clear_state(uid)
        return show_cert_settings(cid, uid)
    if not text:
        return send(cid, "⚠️ متن خالی است")
    clear_state(uid)
    set_setting("cert_template", text[:3000], "قالب گواهینامه", "certificate", uid)
    send(cid, "✅ قالب گواهینامه ذخیره شد", kb_remove())
    show_cert_settings(cid, uid)


def reset_cert(cid, uid):
    if not _guard(cid, uid):
        return
    set_setting("cert_template", DEFAULT_CERT, "قالب گواهینامه", "certificate", uid)
    send(cid, "♻️ قالب به حالت پیش‌فرض برگشت")
    show_cert_settings(cid, uid)


def render_cert(tpl, **kw):
    out = tpl
    for k, v in kw.items():
        out = out.replace("{" + k + "}", str(v or "-"))
    return out


def preview_cert(cid, uid):
    tpl = get_setting("cert_template", DEFAULT_CERT)
    txt = render_cert(tpl, name="علی محمدی", event="کارگاه مهارت‌های زندگی",
                      date="1404/06/15", org=org_name(), serial="NORA-0406-12345",
                      national_id="1234567890", sessions="4")
    send(cid, "👁️ پیش‌نمایش گواهینامه:\n━━━━━━━━━━━━━━")
    send_or_edit(cid, txt, {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": "cert_settings"}]]})


def issue_certificate(cid, uid, eid, target_uid=None, silent=False):
    """🔒 فاز ۳۹ — دروازهٔ صدور (توضیح کامل در certissue)"""
    # 🛡️ اگر کاربر عادی برای **خودش** می‌خواهد و قفل بسته است
    if target_uid is None and not _is_admin(uid):
        import certissue as _ci
        if not _ci.self_issue_allowed():
            if silent:
                return None
            return _ci.deny_self_issue(cid)
    return _issue_certificate_inner(cid, uid, eid, target_uid, silent)


def _issue_certificate_inner(cid, uid, eid, target_uid=None,
                             silent=False):
    """
    🎓 صدور گواهینامه برای یک نفر.

    🔄 فاز ۲۲: حالا موتور واحد certissue استفاده می‌شود تا
       کاربر و ادمین دقیقاً یک نتیجه بگیرند — با همان قالب،
       همان پارامترها و همان شرط حضور.

    🔴 قبلاً شرط حضور اصلاً بررسی نمی‌شد: هرکس ثبت‌نام کرده بود
       گواهینامه می‌گرفت، حتی اگر در هیچ جلسه‌ای نیامده بود.
    """
    from events import get_event
    import certissue

    target = target_uid or uid
    ev = get_event(eid)
    if not ev:
        return None
    if not ev.get("has_certificate"):
        if not silent:
            send(cid, "⚠️ این رویداد گواهینامه ندارد")
        return None

    reg = db_execute(
        "SELECT * FROM event_registrations WHERE event_id=? AND bale_user_id=?",
        (eid, target), fetch="one")
    if not reg or reg.get("status") not in ("confirmed", "attended"):
        if not silent:
            send(cid, "⚠️ شما در این رویداد شرکت نکرده‌اید")
        return None

    # 🎓 اگر قبلاً صادر شده، همان را بفرست
    ex = db_execute(
        "SELECT * FROM certificates WHERE event_id=? AND bale_user_id=?",
        (eid, target), fetch="one")
    if ex:
        if ex.get("revoked") and not silent:
            send(cid, "🚫 گواهینامه شما باطل شده است.\n\n"
                      "💡 برای پیگیری با پشتیبانی تماس بگیرید.")
            return ex
        if not silent:
            certissue.send_cert_files(target, ex, ev)
        return ex

    # ✅ شرط حضور را بررسی کن — رفع باگ ۲
    ok_list, no_list, ctext = certissue.eligible(eid, ev)
    ok_ids = {r["bale_user_id"] for r in ok_list}
    if target not in ok_ids:
        why = next((r.get("why") for r in no_list
                    if r["bale_user_id"] == target), "")
        if not silent:
            lines = ["🌱 هنوز واجد شرایط نیستید",
                     "━━━━━━━━━━━━━━", "",
                     f"✅ شرط دریافت: {ctext}"]
            if why:
                lines += ["", f"💬 وضعیت شما: {why}"]
            lines += ["", "💡 با حضور در جلسات، گواهینامه‌تان",
                      "   صادر می‌شود. موفق باشید! 💚"]
            send(cid, "\n".join(lines), {"inline_keyboard": [
                [{"text": "📊 کارنامه من",
                  "callback_data": f"uatt_rep_{eid}"}],
                [{"text": "🔙 بازگشت", "callback_data": "u_attendance"}]]})
        return None

    cert, err = certissue.issue_one(eid, target, uid, ev,
                                    send_to_user=not silent)
    if not cert and not silent:
        send(cid, f"❌ خطا در صدور گواهینامه\n\n{err}")
    return cert


def _send_cert(cid, cert, ev):
    """
    📤 ارسال گواهینامه به کاربر.

    🎓 فاز ۱۹: اگر از قالب ورد ساخته شده، تصویر و PDF واقعی
       فرستاده می‌شود؛ وگرنه به نسخه متنی برمی‌گردیم.
    """
    body = cert.get("template") or ""
    title = ev.get("title") if ev else ""
    sent_file = False

    png = cert.get("png_path")
    if png and Path(png).exists():
        send_photo(cid, png, f"🎓 گواهینامه — {title}")
        sent_file = True
    pdf = cert.get("pdf_path")
    if pdf and Path(pdf).exists():
        send_document(cid, pdf, f"📄 گواهینامه (PDF) — {title}")
        sent_file = True
    if not sent_file:
        dx = cert.get("docx_path")
        if dx and Path(dx).exists():
            send_document(cid, dx, f"📄 گواهینامه — {title}")
            sent_file = True
    if not sent_file:
        img = _make_cert_image(body, cert.get("serial"))
        if img:
            send_photo(cid, img, f"🎓 گواهینامه — {title}")

    lines = ["🎓 گواهینامه شما", "━━━━━━━━━━━━━━", ""]
    if not sent_file and body:
        lines += [body, ""]
    lines += [f"🔖 شماره: {cert.get('serial') or '—'}",
              f"📅 صادر شده: {_jd.fmt(cert.get('issued_at'), 'date')}"]

    # ⏰ فاز ۱۹-ب — یادآوری مهلت ذخیره
    #    فایل بعد از مدتی پاک می‌شود تا حافظه پر نشود، ولی
    #    شماره و اعتبارسنجی برای همیشه معتبر می‌ماند.
    try:
        import certgen as _cg
        if sent_file and _cg.autodelete_on() and \
                get_setting("cert_warn_user", "1") == "1":
            _h = _cg.keep_hours()
            if _h > 0:
                _when = (f"{_h} ساعت" if _h < 24
                         else f"{_h // 24} روز")
                lines += ["", f"⏰ لطفاً تا {_when} آینده فایل را ذخیره کنید.",
                          "بعد از آن از سرور پاک می‌شود، ولی نگران نباشید —",
                          "هر وقت خواستید دوباره برایتان می‌سازیم 💚"]
    except Exception:
        pass
    try:
        import certgen
        lines += ["", f"🔗 اعتبارسنجی:\n{certgen.verify_url(cert.get('serial'))}"]
    except Exception:
        pass

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "📋 کپی شماره گواهینامه",
          "copy_text": {"text": cert.get("serial") or ""}}],
        [{"text": "🔙 بازگشت", "callback_data": "u_my_certs"}],
    ]})


def _make_cert_image(text, serial):
    """ساخت تصویر گواهینامه با Pillow (اختیاری)"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    try:
        W, H = 1200, 850
        img = Image.new("RGB", (W, H), (253, 250, 242))
        d = ImageDraw.Draw(img)
        # قاب
        d.rectangle([25, 25, W - 25, H - 25], outline=(184, 148, 74), width=6)
        d.rectangle([42, 42, W - 42, H - 42], outline=(200, 175, 120), width=2)

        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            def shape(t):
                return get_display(arabic_reshaper.reshape(t))
        except ImportError:
            def shape(t):
                return t

        y = 120
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                y += 26
                continue
            t = shape(line)
            try:
                bbox = d.textbbox((0, 0), t)
                w = bbox[2] - bbox[0]
            except Exception:
                w = len(t) * 8
            d.text(((W - w) / 2, y), t, fill=(40, 40, 40))
            y += 38
            if y > H - 90:
                break

        CERT_DIR.mkdir(parents=True, exist_ok=True)
        fp = CERT_DIR / f"{serial or int(time.time())}.jpg"
        img.save(fp, "JPEG", quality=90)
        return str(fp)
    except Exception as e:
        log(f"⚠️ ساخت تصویر گواهینامه: {e}")
        return None


def bulk_certificates(cid, uid, eid, confirmed=False):
    """
    🎓 صدور گروهی — حالا به «مرکز صدور» می‌رود.

    🔴 باگ بزرگی که رفع شد (فاز ۲۲):
       نسخهٔ قبلی این تابع، issue_certificate را با silent=True
       صدا می‌زد — یعنی «فایل نفرست» — و بعد خودش فقط متن خام
       row["template"] را ارسال می‌کرد.

       نتیجه: کل موتور گواهینامه (فاز ۱۹ تا ۲۱) دور زده می‌شد.
       PNG و PDF ساخته می‌شدند، در دیتابیس ذخیره می‌شدند، ولی
       هرگز به دست کاربر نمی‌رسیدند. کاربر گفت:
       «گواهینامه تو مدیریت رویداد صادر نمیشه» — درست می‌گفت.

       حالا certissue.py این کار را می‌کند: با انتخاب قالب،
       شرط حضور، پارامترهای دلخواه و پیش‌نمایش.
    """
    if not _guard(cid, uid):
        return
    import certissue
    if confirmed:
        # سازگاری با نسخهٔ قبل: cert_bulky_ یعنی «همین حالا اجرا کن»
        return certissue.run_bulk(cid, uid, eid)
    return certissue.show_hub(cid, uid, eid)


def my_certificates(cid, uid):
    """گواهینامه‌های کاربر"""
    rows = db_execute("""
        SELECT c.*, e.title FROM certificates c
        LEFT JOIN events e ON e.id=c.event_id
        WHERE c.bale_user_id=? ORDER BY c.id DESC LIMIT 20
    """, (uid,), fetch="all") or []

    # 🏛️ فاز ۳۶ — شاید گواهینامهٔ آماده‌ای داشته باشد که هنوز
    #    ساخته نشده (مرکز صدور آن را رزرو کرده)
    try:
        import certcenter as _cc
        _ready = _cc.pending_for(uid)
    except Exception:
        _ready = []

    if not rows and not _ready:
        return send_or_edit(cid, (
            "🎓 گواهینامه‌های من\n"
            "━━━━━━━━━━━━━━\n\n"
            "📭 هنوز گواهینامه ندارید.\n\n"
            "💡 با شرکت در رویدادها گواهینامه دریافت کنید."
        ), {"inline_keyboard": [
            [{"text": "🎉 رویدادها", "callback_data": "u_events"}],
            [{"text": "🔙 پروفایل", "callback_data": "profile_view"}]]})

    if not rows and _ready:
        _l = ["🎓 گواهینامه‌های من", "━━━━━━━━━━━━━━", "",
              f"✨ {len(_ready)} گواهینامه آمادهٔ دریافت دارید!", ""]
        _b = []
        for s_ in _ready[:10]:
            _l.append(f"   🎁 {s_.get('issue_title') or 'گواهینامه'}")
            _b.append([{"text": f"🎁 دریافت: "
                                f"{(s_.get('issue_title') or 'گواهینامه')}"[:34],
                        "callback_data": f"ccget_{s_['id']}"}])
        _l += ["", "💡 روی هرکدام بزنید تا همان لحظه",
               "   ساخته و برایتان فرستاده شود."]
        _b.append([{"text": "🔙 پروفایل", "callback_data": "profile_view"}])
        return send_or_edit(cid, "\n".join(_l), {"inline_keyboard": _b})

    lines = [f"🎓 گواهینامه‌های من ({len(rows)})", "━━━━━━━━━━━━━━", ""]
    btns = []

    # 🏛️ فاز ۳۶ — گواهینامه‌هایی که آمادهٔ ساخت‌اند
    #    «هروقت کاربر ساخت میره تو پروفایلش میسازه و دانلود میکنه»
    try:
        import certcenter as _cc
        _pend = _cc.pending_for(uid)
    except Exception:
        _pend = []
    if _pend:
        lines += [f"✨ {len(_pend)} گواهینامهٔ آمادهٔ دریافت:", ""]
        for s_ in _pend[:5]:
            lines.append(f"   🎁 {s_.get('issue_title') or 'گواهینامه'}")
            btns.append([{"text": f"🎁 دریافت: "
                                  f"{(s_.get('issue_title') or 'گواهینامه')}"[:34],
                          "callback_data": f"ccget_{s_['id']}"}])
        lines += ["", "━━━━━━━━━━━━━━", ""]
    # 📅 فاز ۳۷ — اعتبار و انقضا هم نشان داده شود
    #    قبلاً فقط شماره و تاریخ صدور بود؛ کاربر نمی‌فهمید
    #    گواهینامه‌اش تا کِی معتبر است یا منقضی شده.
    try:
        import certverify as _cv
    except Exception:
        _cv = None

    n_exp = 0
    for c in rows:
        _ttl = c.get("title") or "گواهینامه"
        _icon = "🎓"
        _exp_line = None
        if _cv and c.get("expires_on"):
            try:
                if _cv.is_expired(c):
                    _icon = "⌛"
                    n_exp += 1
                    _exp_line = ("└── ⌛ منقضی شده در "
                                 f"{_jd.fmt(c['expires_on'], 'date')}")
                else:
                    _left = _jd.days_left(c["expires_on"])
                    _warn = " ⚠️" if 0 <= _left <= 30 else ""
                    _exp_line = (f"└── ⏳ اعتبار تا "
                                 f"{_jd.fmt(c['expires_on'], 'date')}"
                                 f"{_warn}")
            except Exception:
                _exp_line = None

        lines.append(f"{_icon} {_ttl}")
        lines.append(f"├── 📌 {c.get('serial') or '—'}")
        if _exp_line:
            lines.append(f"├── 📅 "
                         f"{_jd.fmt(c.get('issued_at'), 'date')}")
            lines.append(_exp_line)
        else:
            lines.append(f"└── 📅 "
                         f"{_jd.fmt(c.get('issued_at'), 'date')}")
        lines.append("")
        btns.append([{"text": f"{_icon} {_ttl}"[:40],
                      "callback_data": f"ucertv_{c['id']}"}])

    if n_exp:
        lines += [f"⌛ {n_exp} گواهینامه منقضی شده است.", ""]
    btns.append([{"text": "🔙 پروفایل", "callback_data": "profile_view"}])

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def view_certificate(cid, uid, cert_id):
    c = db_execute("SELECT * FROM certificates WHERE id=?", (cert_id,), fetch="one")
    if not c:
        return send(cid, "❌ یافت نشد")
    if c.get("bale_user_id") != uid and not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")

    # ♻️ فاز ۱۹-ب — اگر فایل پاک شده، دوباره بساز
    #    کاربر نباید بفهمد فایلش پاک شده بود.
    _paths = [c.get("png_path"), c.get("pdf_path"), c.get("docx_path")]
    if not any(pp and Path(pp).exists() for pp in _paths):
        try:
            import certgen as _cg
            # 📄 فاز ۳۷: قالبِ **خودِ همین گواهینامه** را بردار،
            #    نه قالب پیش‌فرض. گواهینامه‌های مرکز صدور
            #    ممکن است قالب دیگری داشته باشند و بازتولید
            #    با قالب پیش‌فرض، فایلی متفاوت می‌ساخت.
            _tpl = (_cg.get_template(c.get("template_id"))
                    if c.get("template_id") else None) \
                or _cg.get_template()
            if _tpl:
                send(cid, "⏳ در حال آماده‌سازی گواهینامه شما...")
                _cg.regenerate(c)
                c = db_execute("SELECT * FROM certificates WHERE id=?",
                               (cert_id,), fetch="one") or c
            else:
                send(cid, "🌱 فایل این گواهینامه در دسترس نیست.\n\n"
                          "لطفاً به پشتیبانی اطلاع دهید.")
        except Exception as e:
            log(f"⚠️ بازتولید گواهینامه: {e}")

    from events import get_event
    ev = get_event(c.get("event_id")) or {}
    _send_cert(cid, c, ev)
