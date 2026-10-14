"""
📊 داشبورد گزارشات — فاز ۱۴

طبق فایل معماری (خط ۴۲۳۱۰):

  🏠 داشبورد اصلی
     ├── کارت‌های آماری با درصد تغییر نسبت به دوره قبل
     ├── ⚡ فعالیت لحظه‌ای
     ├── 💡 هشدارها و توصیه‌های خودکار
     └── 📅 انتخاب دوره زمانی (۱۲ دوره آماده + سفارشی)

  📊 ۹ گزارش تخصصی:
     🎉 رویدادها · 👥 کاربران · 📝 فرم‌ها · ✋ حضور و غیاب
     💰 مالی · 🎓 گواهینامه‌ها · 📢 اطلاع‌رسانی
     👨‍💼 ادمین‌ها · 🏆 برترین‌های ماه

  🎯 ابزارها: خروجی کامل Excel · گزارش زمان‌بندی‌شده

⚠️ همه مبالغ ریال‌اند — نمایش با money() بدون تبدیل.
🔒 گزارش مالی فقط برای سوپرادمین (fin_view در SUPER_ONLY است).
"""
from privacy import user_error_message
from datetime import datetime

from config import SUPER_ADMIN_ID, money, FILES_DIR, CURRENCY_LABEL
from database import db_execute, db_scalar, get_setting, set_setting, log
from auth import log_action, is_admin as _is_admin
from bale_api import send, send_or_edit, send_document
import permissions as perm
import jalali as _jd

PAID = ("paid", "confirmed", "success")


# ==================== دوره‌های زمانی ====================
# کلید → (نام، شرط SQL برای دوره جاری، شرط دوره قبل برای مقایسه)
PERIODS = {
    "today":    ("📅 امروز",
                 "date({c})=date('now')",
                 "date({c})=date('now','-1 day')"),
    "yesterday": ("📅 دیروز",
                  "date({c})=date('now','-1 day')",
                  "date({c})=date('now','-2 day')"),
    "7d":       ("📅 ۷ روز اخیر",
                 "{c} >= datetime('now','-7 day')",
                 "{c} >= datetime('now','-14 day') AND "
                 "{c} < datetime('now','-7 day')"),
    "30d":      ("📅 ۳۰ روز اخیر",
                 "{c} >= datetime('now','-30 day')",
                 "{c} >= datetime('now','-60 day') AND "
                 "{c} < datetime('now','-30 day')"),
    "90d":      ("📅 این فصل (۹۰ روز)",
                 "{c} >= datetime('now','-90 day')",
                 "{c} >= datetime('now','-180 day') AND "
                 "{c} < datetime('now','-90 day')"),
    "year":     ("📅 یک سال اخیر",
                 "{c} >= datetime('now','-365 day')",
                 "{c} >= datetime('now','-730 day') AND "
                 "{c} < datetime('now','-365 day')"),
    "all":      ("📅 از ابتدا", "1=1", "0=1"),
}

DEFAULT_PERIOD = "30d"


def get_period(uid=None):
    """دوره انتخابی ادمین (در تنظیمات ذخیره می‌شود)"""
    p = get_setting(f"rp_period_{uid}" if uid else "rp_period",
                    DEFAULT_PERIOD)
    return p if p in PERIODS else DEFAULT_PERIOD


def set_period(uid, key):
    if key not in PERIODS:
        return False
    set_setting(f"rp_period_{uid}", key, "📅 دوره گزارش", "reports", uid)
    return True


def period_name(key):
    return PERIODS.get(key, PERIODS[DEFAULT_PERIOD])[0]


def _w(key, col="created_at", prev=False):
    """شرط WHERE دوره برای یک ستون مشخص"""
    p = PERIODS.get(key, PERIODS[DEFAULT_PERIOD])
    return (p[2] if prev else p[1]).replace("{c}", col)


def _cnt(table, key, col="created_at", extra="", prev=False, params=()):
    """شمارش امن با فیلتر دوره"""
    where = _w(key, col, prev)
    if extra:
        where = f"({where}) AND ({extra})"
    try:
        return db_scalar(f"SELECT COUNT(*) FROM {table} WHERE {where}",
                         params) or 0
    except Exception:
        return 0


def _sum(table, field, key, col="created_at", extra="", prev=False):
    where = _w(key, col, prev)
    if extra:
        where = f"({where}) AND ({extra})"
    try:
        return db_scalar(f"SELECT COALESCE(SUM({field}),0) FROM {table} "
                         f"WHERE {where}") or 0
    except Exception:
        return 0


def _safe(sql, params=(), default=0):
    try:
        return db_scalar(sql, params) or default
    except Exception:
        return default


def _rows(sql, params=()):
    try:
        return db_execute(sql, params, fetch="all") or []
    except Exception:
        return []


def pct(now, before):
    """درصد تغییر — با آیکون جهت"""
    if not before:
        return "🆕 جدید" if now else "—"
    d = (now - before) * 100.0 / before
    if abs(d) < 0.5:
        return "➖ بدون تغییر"
    return f"{'▲' if d > 0 else '▼'} {abs(d):.1f}%"


def bar(value, total, width=10):
    """نوار پیشرفت متنی"""
    if not total:
        return "░" * width
    n = max(0, min(width, round(value * width / total)))
    return "█" * n + "░" * (width - n)


def _guard(cid, uid):
    if not _is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    if not perm.has_any(uid, "rp_view", "rp_export", "rp_logs"):
        send(cid, "🔒 دسترسی به گزارش‌ها ندارید")
        return False
    return True


# ==================== 🏠 داشبورد اصلی ====================
def show_dashboard(cid, uid):
    """📊 داشبورد گزارشات — کارت‌های آماری + هشدار + ۹ گزارش"""
    if not _guard(cid, uid):
        return
    k = get_period(uid)

    # ── کارت‌های آماری ──
    users = _safe("SELECT COUNT(*) FROM users")
    u_new = _cnt("users", k)
    u_prev = _cnt("users", k, prev=True)

    ev_all = _safe("SELECT COUNT(*) FROM events")
    ev_new = _cnt("events", k)
    ev_prev = _cnt("events", k, prev=True)

    regs = _cnt("event_registrations", k, extra="status<>'cancelled'")
    regs_prev = _cnt("event_registrations", k, extra="status<>'cancelled'",
                     prev=True)

    att = _cnt("attendance_records", k, extra="status IN ('present','late')")
    att_prev = _cnt("attendance_records", k,
                    extra="status IN ('present','late')", prev=True)

    fm_all = _safe("SELECT COUNT(*) FROM forms")
    resp = _cnt("form_responses", k,
                extra="status IN ('completed','confirmed')")
    resp_prev = _cnt("form_responses", k,
                     extra="status IN ('completed','confirmed')", prev=True)

    certs = _cnt("certificates", k, "issued_at")
    certs_prev = _cnt("certificates", k, "issued_at", prev=True)

    lines = [
        "📊 داشبورد گزارشات نورا", "━━━━━━━━━━━━━━", "",
        f"📅 دوره: {period_name(k)}", "",
        "📊 آمار کلی:", "",
        f"👥 کاربران: {users}",
        f"   🆕 جدید: {u_new}   {pct(u_new, u_prev)}",
        f"🎉 رویدادها: {ev_all}",
        f"   🆕 جدید: {ev_new}   {pct(ev_new, ev_prev)}",
        f"🎫 ثبت‌نام‌ها: {regs}   {pct(regs, regs_prev)}",
        f"✋ حضور ثبت‌شده: {att}   {pct(att, att_prev)}",
        f"📝 فرم‌ها: {fm_all}",
        f"   📄 پاسخ: {resp}   {pct(resp, resp_prev)}",
        f"🎓 گواهینامه: {certs}   {pct(certs, certs_prev)}",
    ]

    # 💰 درآمد — فقط سوپرادمین
    if perm.has_perm(uid, "fin_view"):
        inc = _sum("transactions", "amount", k,
                   extra=f"status IN {PAID}")
        inc_prev = _sum("transactions", "amount", k,
                        extra=f"status IN {PAID}", prev=True)
        lines += [f"💰 درآمد: {money(inc)}   {pct(inc, inc_prev)}"]

    # ── ⚡ فعالیت لحظه‌ای ──
    online = _safe("SELECT COUNT(*) FROM users WHERE last_activity_at >= "
                   "datetime('now','-15 minute')")
    filling = _safe("SELECT COUNT(*) FROM user_states WHERE state LIKE "
                    "'%fill%' AND updated_at >= datetime('now','-30 minute')")
    paying = _safe("SELECT COUNT(*) FROM transactions WHERE status='pending' "
                   "AND created_at >= datetime('now','-2 hour')")
    lines += ["", "⚡ فعالیت لحظه‌ای:",
              f"   🟢 فعال (۱۵ دقیقه اخیر): {online}",
              f"   📝 در حال پر کردن فرم: {filling}",
              f"   💳 پرداخت در جریان: {paying}"]

    # ── 💡 هشدارها ──
    alerts = _build_alerts(uid)
    if alerts:
        lines += ["", "⚠️ نیاز به توجه:"]
        lines += [f"   • {a}" for a in alerts]

    tips = _build_tips(uid, k)
    if tips:
        lines += ["", "✨ توصیه‌ها:"]
        lines += [f"   • {t}" for t in tips]

    btns = [
        [{"text": f"📅 تغییر دوره ({period_name(k)})",
          "callback_data": "rp_period"}],
        [{"text": "🎉 رویدادها", "callback_data": "rp_events"},
         {"text": "👥 کاربران", "callback_data": "rp_users"}],
        [{"text": "📝 فرم‌ها", "callback_data": "rp_forms"},
         {"text": "✋ حضور و غیاب", "callback_data": "rp_att"}],
    ]
    row = [{"text": "🎓 گواهینامه‌ها", "callback_data": "rp_certs"}]
    if perm.has_perm(uid, "fin_view"):
        row.insert(0, {"text": "💰 مالی", "callback_data": "rp_finance"})
    btns.append(row)
    btns += [
        [{"text": "📢 اطلاع‌رسانی", "callback_data": "rp_notify"},
         {"text": "🏆 برترین‌ها", "callback_data": "rp_top"}],
    ]
    if perm.has_any(uid, "sys_admins", "rp_logs"):
        btns.append([{"text": "👨‍💼 گزارش ادمین‌ها",
                      "callback_data": "rp_admins"}])
    btns.append([{"text": "🎲 قرعه‌کشی‌ها", "callback_data": "lt_all"}])
    if perm.has_perm(uid, "rp_export"):
        btns.append([{"text": "📥 خروجی کامل Excel",
                      "callback_data": "rp_export"}])
    btns.append([{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}])

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def _build_alerts(uid):
    """⚠️ چیزهایی که ادمین باید بهشان برسد"""
    out = []
    n = _safe("SELECT COUNT(*) FROM profile_submissions WHERE status='pending'")
    if n:
        out.append(f"{n} درخواست پروفایل در انتظار تأیید")
    if perm.has_any(uid, "fin_view", "fin_approve"):
        n = _safe("SELECT COUNT(*) FROM payment_receipts "
                  "WHERE status='pending'")
        if n:
            out.append(f"{n} رسید پرداخت در انتظار بررسی")
        n = _safe("SELECT COUNT(*) FROM transactions WHERE status='onsite'")
        if n:
            out.append(f"{n} بدهی پرداخت در محل وصول نشده")
    n = _safe("SELECT COUNT(*) FROM tickets WHERE unread_admin=1")
    if n:
        out.append(f"{n} تیکت پشتیبانی خوانده‌نشده")
    n = _safe("SELECT COUNT(*) FROM reward_redemptions WHERE status='pending'")
    if n:
        out.append(f"{n} درخواست پاداش در انتظار تحویل")
    n = _safe("SELECT COUNT(*) FROM users WHERE is_authenticated=1 "
              "AND COALESCE(complete_profile_percent,0) < 50")
    if n:
        out.append(f"{n} کاربر پروفایل ناقص دارند")

    # رویداد نزدیک به تکمیل ظرفیت
    rows = _rows("""SELECT e.title, e.capacity,
        (SELECT COUNT(*) FROM event_registrations r
         WHERE r.event_id=e.id AND r.status IN ('confirmed','attended')) c
        FROM events e WHERE e.status='published' AND COALESCE(e.capacity,0) > 0""")
    near = [r for r in rows if r["c"] >= int(r["capacity"]) * 0.9]
    if near:
        out.append(f"{len(near)} رویداد نزدیک به تکمیل ظرفیت")

    # قرعه‌کشی معلق
    n = _safe("SELECT COUNT(*) FROM form_lotteries "
              "WHERE status='pending' AND is_active=1")
    if n:
        out.append(f"{n} قرعه‌کشی هنوز اجرا نشده")
    return out[:6]


def _build_tips(uid, k):
    """✨ تحلیل خودکار روند"""
    out = []
    u_new, u_prev = _cnt("users", k), _cnt("users", k, prev=True)
    if u_prev and u_new > u_prev * 1.2:
        out.append(f"رشد کاربران {pct(u_new, u_prev)} — عالی!")
    elif u_prev and u_new < u_prev * 0.7:
        out.append(f"کاهش کاربران جدید {pct(u_new, u_prev)} — بررسی کنید")

    # نرخ حضور
    conf = _cnt("event_registrations", k, extra="status IN ('confirmed','attended')")
    att = _cnt("attendance_records", k, extra="status IN ('present','late')")
    if conf >= 10:
        rate = att * 100 // conf if conf else 0
        if rate < 50:
            out.append(f"نرخ حضور {rate}% — یادآوری‌ها را فعال کنید")
        elif rate >= 80:
            out.append(f"نرخ حضور {rate}% — بسیار خوب!")

    if perm.has_perm(uid, "fin_view"):
        inc = _sum("transactions", "amount", k, extra=f"status IN {PAID}")
        prev = _sum("transactions", "amount", k, extra=f"status IN {PAID}",
                    prev=True)
        if prev and inc > prev * 1.15:
            out.append(f"درآمد {pct(inc, prev)} نسبت به دوره قبل")

    n_vip = _cnt("users", k, extra="is_vip=1")
    if n_vip:
        out.append(f"{n_vip} کاربر VIP جدید")
    return out[:4]


# ==================== 📅 انتخاب دوره ====================
def show_periods(cid, uid):
    if not _guard(cid, uid):
        return
    cur = get_period(uid)
    lines = ["📅 انتخاب دوره زمانی", "━━━━━━━━━━━━━━", "",
             "همه گزارش‌ها بر اساس این دوره محاسبه می‌شوند:", ""]
    btns = []
    for k, (nm, _, _) in PERIODS.items():
        mark = "🔘" if k == cur else "⚪"
        lines.append(f"{mark} {nm}")
        btns.append([{"text": f"{mark} {nm}", "callback_data": f"rp_p_{k}"}])
    lines += ["", "💡 مقایسه با دوره مشابه قبل خودکار انجام می‌شود."]
    btns.append([{"text": "🔙 داشبورد", "callback_data": "admin_stats"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def pick_period(cid, uid, key):
    if not _guard(cid, uid):
        return
    if not set_period(uid, key):
        return send(cid, "❌ دوره نامعتبر")
    return show_dashboard(cid, uid)


def _hdr(title, k):
    return [title, "━━━━━━━━━━━━━━", f"📅 دوره: {period_name(k)}", ""]


def _back(extra=None):
    btns = list(extra or [])
    btns.append([{"text": "🔙 داشبورد", "callback_data": "admin_stats"}])
    return {"inline_keyboard": btns}


# ==================== ۱️⃣ گزارش رویدادها ====================
def report_events(cid, uid):
    if not _guard(cid, uid):
        return
    k = get_period(uid)
    from events import EVENT_TYPES, LOCATION_TYPES

    w = _w(k, "created_at")
    total = _cnt("events", k)
    done = _cnt("events", k, extra="status='finished'")
    live = _cnt("events", k, extra="status='published'")
    draft = _cnt("events", k, extra="status='draft'")
    closed = _cnt("events", k, extra="status='closed'")
    cancel = _cnt("events", k, extra="status='cancelled'")

    lines = _hdr("🎉 گزارش رویدادها", k)
    lines += ["📊 آمار کلی:",
              f"   🎉 کل رویدادها: {total}",
              f"   ├── ✅ برگزار شده: {done}",
              f"   ├── 🟢 در حال ثبت‌نام: {live}",
              f"   ├── 📝 پیش‌نویس: {draft}",
              f"   ├── 🔴 بسته: {closed}",
              f"   └── ⛔ لغو شده: {cancel}", ""]

    # تفکیک بر اساس نوع
    rows = _rows(f"SELECT event_type, COUNT(*) c FROM events WHERE {w} "
                 "GROUP BY event_type ORDER BY c DESC")
    if rows:
        lines.append("📊 تفکیک بر اساس نوع:")
        for r in rows:
            t = EVENT_TYPES.get(r["event_type"] or "meeting",
                                EVENT_TYPES["meeting"])
            p = r["c"] * 100 // total if total else 0
            lines.append(f"   {t['icon']} {t['name']}: {r['c']} ({p}%)")
            lines.append(f"      {bar(r['c'], total)}")
        lines.append("")

    # نحوه برگزاری
    rows = _rows(f"SELECT location_type, COUNT(*) c FROM events WHERE {w} "
                 "GROUP BY location_type ORDER BY c DESC")
    if rows:
        lines.append("📍 نحوه برگزاری:")
        for r in rows:
            t = LOCATION_TYPES.get(r["location_type"] or "physical",
                                   LOCATION_TYPES["physical"])
            lines.append(f"   {t['icon']} {t['name']}: {r['c']}")
        lines.append("")

    # ثبت‌نام و ظرفیت
    regs = _cnt("event_registrations", k, extra="status<>'cancelled'")
    wait = _cnt("event_registrations", k, extra="status='waitlist'")
    lines += ["🎫 ثبت‌نام:",
              f"   👥 کل ثبت‌نام: {regs}",
              f"   📋 لیست انتظار: {wait}",
              f"   📊 میانگین هر رویداد: {regs // total if total else 0}", ""]

    # پرطرفدارترین
    rows = _rows(f"""SELECT e.title, e.capacity,
        (SELECT COUNT(*) FROM event_registrations r WHERE r.event_id=e.id
         AND r.status IN ('confirmed','attended')) c
        FROM events e WHERE {w.replace('created_at', 'e.created_at')}
        ORDER BY c DESC LIMIT 5""")
    rows = [r for r in rows if r["c"]]
    if rows:
        lines.append("🔥 پرطرفدارترین رویدادها:")
        for i, r in enumerate(rows, 1):
            cap = f" از {r['capacity']}" if int(r.get("capacity") or 0) else ""
            lines.append(f"   {i}. {str(r['title'])[:30]} — {r['c']} نفر{cap}")
        lines.append("")

    # رویدادهای پیش رو
    up = _rows("""SELECT title, start_date FROM events
        WHERE status='published' ORDER BY id DESC LIMIT 5""")
    if up:
        lines.append("📅 رویدادهای فعال:")
        for r in up:
            lines.append(f"   • {str(r['title'])[:30]} — "
                         f"{r.get('start_date') or '—'}")

    send_or_edit(cid, "\n".join(lines), _back())


# ==================== ۲️⃣ گزارش کاربران ====================
def report_users(cid, uid):
    if not _guard(cid, uid):
        return
    k = get_period(uid)

    total = _safe("SELECT COUNT(*) FROM users")
    new = _cnt("users", k)
    prev = _cnt("users", k, prev=True)
    auth = _safe("SELECT COUNT(*) FROM users WHERE is_authenticated=1")
    appr = _safe("SELECT COUNT(*) FROM users WHERE profile_status='approved'")
    vip = _safe("SELECT COUNT(*) FROM users WHERE is_vip=1")
    blocked = _safe("SELECT COUNT(*) FROM users WHERE is_blocked=1")
    imported = _safe("SELECT COUNT(*) FROM users WHERE imported=1")
    male = _safe("SELECT COUNT(*) FROM users WHERE gender='مرد'")
    female = _safe("SELECT COUNT(*) FROM users WHERE gender='زن'")
    avg = _safe("SELECT COALESCE(AVG(complete_profile_percent),0) FROM users")

    lines = _hdr("👥 گزارش کاربران", k)
    lines += ["📊 آمار کلی:",
              f"   👥 کل: {total}",
              f"   🆕 جدید در این دوره: {new}   {pct(new, prev)}",
              f"   ✅ احراز هویت شده: {auth}",
              f"   📋 پروفایل تأییدشده: {appr}",
              f"   ⭐ VIP: {vip}",
              f"   📥 وارد شده از اکسل: {imported}",
              f"   🚫 مسدود: {blocked}", "",
              "🚻 جنسیت:",
              f"   👨 آقایان: {male} ({male * 100 // total if total else 0}%)",
              f"   {bar(male, total)}",
              f"   👩 خانم‌ها: {female} ({female * 100 // total if total else 0}%)",
              f"   {bar(female, total)}", "",
              f"📊 میانگین تکمیل پروفایل: {float(avg):.0f}%", ""]

    # فعالیت
    a1 = _safe("SELECT COUNT(*) FROM users WHERE last_activity_at >= "
               "datetime('now','-1 day')")
    a7 = _safe("SELECT COUNT(*) FROM users WHERE last_activity_at >= "
               "datetime('now','-7 day')")
    a30 = _safe("SELECT COUNT(*) FROM users WHERE last_activity_at >= "
                "datetime('now','-30 day')")
    lines += ["📈 فعالیت:",
              f"   🟢 ۲۴ ساعت اخیر: {a1}",
              f"   🔵 ۷ روز اخیر: {a7}",
              f"   ⚪ ۳۰ روز اخیر: {a30}",
              f"   😴 غیرفعال: {max(0, total - a30)}", ""]

    # شهرها
    rows = _rows("""SELECT city, COUNT(*) c FROM users
        WHERE city IS NOT NULL AND city<>'' GROUP BY city
        ORDER BY c DESC LIMIT 7""")
    if rows:
        lines.append("🏙️ شهرهای برتر:")
        for r in rows:
            lines.append(f"   • {r['city']}: {r['c']}")
        lines.append("")

    # مقاطع تحصیلی
    rows = _rows("""SELECT education_level, COUNT(*) c FROM users
        WHERE education_level IS NOT NULL AND education_level<>''
        GROUP BY education_level ORDER BY c DESC LIMIT 5""")
    if rows:
        lines.append("🎓 مقطع تحصیلی:")
        for r in rows:
            lines.append(f"   • {r['education_level']}: {r['c']}")
        lines.append("")

    # منبع عضویت
    ref = _safe("SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL")
    lines += ["🔗 منبع عضویت:",
              f"   👥 با دعوت دوستان: {ref}",
              f"   📥 ورود گروهی: {imported}",
              f"   🤖 مستقیم: {max(0, total - ref - imported)}"]

    send_or_edit(cid, "\n".join(lines), _back())


# ==================== ۳️⃣ گزارش فرم‌ها ====================
def report_forms(cid, uid):
    if not _guard(cid, uid):
        return
    k = get_period(uid)
    from forms import FORM_TYPES

    total = _safe("SELECT COUNT(*) FROM forms")
    new = _cnt("forms", k)
    active = _safe("SELECT COUNT(*) FROM forms WHERE status='active'")
    resp = _cnt("form_responses", k,
                extra="status IN ('completed','confirmed')")
    resp_prev = _cnt("form_responses", k,
                     extra="status IN ('completed','confirmed')", prev=True)
    partial = _cnt("form_responses", k, extra="status='draft'")
    pending = _safe("SELECT COUNT(*) FROM form_responses "
                    "WHERE status='pending_review'")

    lines = _hdr("📝 گزارش فرم‌ها", k)
    lines += ["📊 آمار کلی:",
              f"   📝 کل فرم‌ها: {total}",
              f"   🆕 ساخته‌شده در این دوره: {new}",
              f"   🟢 فعال: {active}",
              f"   📄 پاسخ کامل: {resp}   {pct(resp, resp_prev)}",
              f"   ⏳ ناتمام: {partial}",
              f"   👨‍💼 منتظر تأیید: {pending}", ""]

    # نرخ تکمیل
    started = resp + partial
    if started:
        rate = resp * 100 // started
        lines += [f"📊 نرخ تکمیل: {rate}%", f"   {bar(resp, started)}", ""]

    # تفکیک بر اساس نوع
    rows = _rows("SELECT form_type, COUNT(*) c FROM forms "
                 "GROUP BY form_type ORDER BY c DESC")
    if rows:
        lines.append("📊 تفکیک بر اساس نوع:")
        for r in rows:
            t = FORM_TYPES.get(r["form_type"] or "questionnaire",
                               FORM_TYPES["questionnaire"])
            lines.append(f"   {t['icon']} {t['name']}: {r['c']}")
        lines.append("")

    # پرپاسخ‌ترین
    rows = _rows("""SELECT f.title, f.form_type,
        (SELECT COUNT(*) FROM form_responses r WHERE r.form_id=f.id
         AND r.status IN ('completed','confirmed')) c
        FROM forms f ORDER BY c DESC LIMIT 5""")
    rows = [r for r in rows if r["c"]]
    if rows:
        lines.append("🔥 پرپاسخ‌ترین فرم‌ها:")
        for i, r in enumerate(rows, 1):
            t = FORM_TYPES.get(r["form_type"] or "questionnaire",
                               FORM_TYPES["questionnaire"])
            lines.append(f"   {i}. {t['icon']} {str(r['title'])[:28]} — "
                         f"{r['c']} پاسخ")
        lines.append("")

    # بازدید
    views = _safe("SELECT COALESCE(SUM(views_count),0) FROM forms")
    if views:
        conv = resp * 100 // views if views else 0
        lines += ["👁️ بازدید و تبدیل:",
                  f"   👁️ کل بازدید: {views}",
                  f"   📊 نرخ تبدیل: {conv}%"]

    send_or_edit(cid, "\n".join(lines), _back())


# ==================== ۴️⃣ گزارش حضور و غیاب ====================
def report_attendance(cid, uid):
    if not _guard(cid, uid):
        return
    k = get_period(uid)

    sessions = _cnt("attendance_sessions", k)
    present = _cnt("attendance_records", k, extra="status='present'")
    late = _cnt("attendance_records", k, extra="status='late'")
    absent = _cnt("attendance_records", k, extra="status='absent'")
    excused = _cnt("attendance_records", k, extra="status='excused'")
    total = present + late + absent + excused

    lines = _hdr("✋ گزارش حضور و غیاب", k)
    lines += ["📊 آمار کلی:",
              f"   📋 جلسات برگزارشده: {sessions}",
              f"   📝 کل رکوردها: {total}", ""]
    if total:
        lines += ["📊 وضعیت حضور:",
                  f"   ✅ حاضر: {present} ({present * 100 // total}%)",
                  f"      {bar(present, total)}",
                  f"   ⏰ تأخیر: {late} ({late * 100 // total}%)",
                  f"      {bar(late, total)}",
                  f"   ❌ غایب: {absent} ({absent * 100 // total}%)",
                  f"      {bar(absent, total)}"]
        if excused:
            lines += [f"   📄 معذور: {excused} ({excused * 100 // total}%)"]
        rate = (present + late) * 100 // total
        lines += ["", f"🎯 نرخ حضور کلی: {rate}%"]
        if rate >= 80:
            lines.append("   ✨ عالی!")
        elif rate < 50:
            lines.append("   ⚠️ پایین — یادآوری‌ها را فعال کنید")
        lines.append("")
    else:
        lines += ["📭 در این دوره حضوری ثبت نشده", ""]

    # روش‌های ثبت
    rows = _rows(f"SELECT method, COUNT(*) c FROM attendance_records "
                 f"WHERE {_w(k)} GROUP BY method ORDER BY c DESC")
    if rows:
        names = {"code": "🔢 کد جلسه", "qr": "📷 QR", "location": "📍 موقعیت",
                 "manual": "✍️ دستی", "selfie": "🤳 سلفی",
                 "auto": "⚙️ خودکار"}
        lines.append("🔧 روش ثبت حضور:")
        for r in rows:
            lines.append(f"   {names.get(r['method'], r['method'] or '—')}: "
                         f"{r['c']}")
        lines.append("")

    # پرحضورترین‌ها
    rows = _rows(f"""SELECT a.bale_user_id, u.first_name, u.last_name,
        COUNT(*) c FROM attendance_records a
        LEFT JOIN users u ON u.bale_user_id=a.bale_user_id
        WHERE a.status IN ('present','late') AND {_w(k, 'a.created_at')}
        GROUP BY a.bale_user_id ORDER BY c DESC LIMIT 5""")
    if rows:
        lines.append("🏆 پرحضورترین اعضا:")
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, r in enumerate(rows):
            nm = f"{r.get('first_name') or ''} " \
                 f"{r.get('last_name') or ''}".strip() or "—"
            lines.append(f"   {medals[i]} {nm} — {r['c']} جلسه")
        lines.append("")

    # رویدادهای با بهترین حضور
    rows = _rows("""SELECT e.title,
        (SELECT COUNT(*) FROM attendance_records a
         JOIN attendance_sessions s ON s.id=a.session_id
         WHERE s.event_id=e.id AND a.status IN ('present','late')) c
        FROM events e ORDER BY c DESC LIMIT 3""")
    rows = [r for r in rows if r["c"]]
    if rows:
        lines.append("🎉 رویدادهای با بیشترین حضور:")
        for r in rows:
            lines.append(f"   • {str(r['title'])[:30]} — {r['c']} حضور")

    send_or_edit(cid, "\n".join(lines), _back())


# ==================== ۵️⃣ گزارش مالی ====================
def report_finance(cid, uid):
    """🔒 فقط سوپرادمین"""
    if not _guard(cid, uid):
        return
    if not perm.has_perm(uid, "fin_view"):
        return send(cid, "🔒 گزارش مالی فقط برای سوپرادمین است")
    k = get_period(uid)

    inc = _sum("transactions", "amount", k, extra=f"status IN {PAID}")
    prev = _sum("transactions", "amount", k, extra=f"status IN {PAID}",
                prev=True)
    n_paid = _cnt("transactions", k, extra=f"status IN {PAID}")
    n_all = _cnt("transactions", k)
    n_pend = _cnt("transactions", k, extra="status='pending'")
    amt_pend = _sum("transactions", "amount", k, extra="status='pending'")
    n_fail = _cnt("transactions", k, extra="status='failed'")
    n_ons = _cnt("transactions", k, extra="status='onsite'")
    amt_ons = _sum("transactions", "amount", k, extra="status='onsite'")
    pts = _sum("transactions", "points_used", k)

    lines = _hdr("💰 گزارش مالی", k)
    lines += ["📊 درآمد:",
              f"   💵 مجموع: {money(inc)}",
              f"   📈 نسبت به دوره قبل: {pct(inc, prev)}",
              f"   💳 میانگین تراکنش: "
              f"{money(inc // n_paid if n_paid else 0)}", "",
              "🧾 تراکنش‌ها:",
              f"   ✅ موفق: {n_paid}",
              f"   ⏳ در انتظار: {n_pend} ({money(amt_pend)})",
              f"   ❌ ناموفق: {n_fail}"]
    if n_ons:
        lines.append(f"   💰 بدهی در محل: {n_ons} ({money(amt_ons)})")
    if n_all:
        lines.append(f"   📊 نرخ موفقیت: {n_paid * 100 // n_all}%")
    if pts:
        lines.append(f"   🏆 امتیاز مصرف‌شده: {pts}")
    lines.append("")

    # روش پرداخت
    rows = _rows(f"""SELECT COALESCE(method,'wallet') m, COUNT(*) c,
        COALESCE(SUM(amount),0) s FROM transactions
        WHERE status IN {PAID} AND {_w(k)}
        GROUP BY m ORDER BY s DESC""")
    if rows:
        names = {"points": "🏆 امتیاز", "onsite": "💰 در محل",
                 "card": "💳 کارت", "wallet": "🏦 کیف پول",
                 "gateway": "🔗 درگاه"}
        lines.append("💳 به تفکیک روش:")
        for r in rows:
            lines.append(f"   {names.get(r['m'], r['m'])}: "
                         f"{money(r['s'])} ({r['c']} تراکنش)")
        lines.append("")

    # درآمد رویدادها
    rows = _rows(f"""SELECT e.title, COALESCE(SUM(t.amount),0) s,
        COUNT(t.id) c FROM events e
        JOIN transactions t ON t.event_id=e.id AND t.status IN {PAID}
        WHERE {_w(k, 't.created_at')}
        GROUP BY e.id ORDER BY s DESC LIMIT 5""")
    if rows:
        lines.append("🎉 پردرآمدترین رویدادها:")
        for i, r in enumerate(rows, 1):
            lines.append(f"   {i}. {str(r['title'])[:28]} — {money(r['s'])}")
        lines.append("")

    # رسیدها
    n_rcp = _safe("SELECT COUNT(*) FROM payment_receipts "
                  "WHERE status='pending'")
    n_ref = _cnt("transactions", k, extra="status='refunded'")
    if n_rcp or n_ref:
        lines.append("📋 سایر:")
        if n_rcp:
            lines.append(f"   🧾 رسید در انتظار: {n_rcp}")
        if n_ref:
            amt = _sum("transactions", "amount", k, extra="status='refunded'")
            lines.append(f"   💸 بازپرداخت: {n_ref} ({money(amt)})")

    send_or_edit(cid, "\n".join(lines), _back([
        [{"text": "💰 داشبورد مالی کامل", "callback_data": "fin_dash"}]]))


# ==================== ۶️⃣ گزارش گواهینامه‌ها ====================
def report_certs(cid, uid):
    if not _guard(cid, uid):
        return
    k = get_period(uid)

    total = _safe("SELECT COUNT(*) FROM certificates")
    new = _cnt("certificates", k, "issued_at")
    prev = _cnt("certificates", k, "issued_at", prev=True)

    lines = _hdr("🎓 گزارش گواهینامه‌ها", k)
    lines += ["📊 آمار کلی:",
              f"   🎓 کل صادرشده: {total}",
              f"   🆕 در این دوره: {new}   {pct(new, prev)}", ""]

    # به تفکیک رویداد
    rows = _rows(f"""SELECT e.title, COUNT(c.id) n FROM certificates c
        LEFT JOIN events e ON e.id=c.event_id
        WHERE {_w(k, 'c.issued_at')}
        GROUP BY c.event_id ORDER BY n DESC LIMIT 8""")
    if rows:
        lines.append("🎉 به تفکیک رویداد:")
        for r in rows:
            lines.append(f"   • {str(r.get('title') or '—')[:30]}: {r['n']}")
        lines.append("")
    else:
        lines += ["📭 در این دوره گواهینامه صادر نشده", ""]

    # کاربران با بیشترین گواهینامه
    rows = _rows("""SELECT c.bale_user_id, u.first_name, u.last_name,
        COUNT(*) n FROM certificates c
        LEFT JOIN users u ON u.bale_user_id=c.bale_user_id
        GROUP BY c.bale_user_id ORDER BY n DESC LIMIT 5""")
    if rows:
        lines.append("🏆 بیشترین گواهینامه:")
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, r in enumerate(rows):
            nm = f"{r.get('first_name') or ''} " \
                 f"{r.get('last_name') or ''}".strip() or "—"
            lines.append(f"   {medals[i]} {nm} — {r['n']} گواهینامه")
        lines.append("")

    # رویدادهای دارای گواهینامه که هنوز صادر نشده
    rows = _rows("""SELECT e.title,
        (SELECT COUNT(*) FROM event_registrations r WHERE r.event_id=e.id
         AND r.status IN ('confirmed','attended')) c,
        (SELECT COUNT(*) FROM certificates ct WHERE ct.event_id=e.id) n
        FROM events e WHERE e.has_certificate=1 AND e.status='finished'""")
    pend = [r for r in rows if r["c"] > r["n"]]
    if pend:
        lines.append("⚠️ گواهینامه صادرنشده:")
        for r in pend[:5]:
            lines.append(f"   • {str(r['title'])[:28]} — "
                         f"{r['c'] - r['n']} نفر")

    send_or_edit(cid, "\n".join(lines), _back())


# ==================== ۷️⃣ گزارش اطلاع‌رسانی ====================
def report_notify(cid, uid):
    if not _guard(cid, uid):
        return
    k = get_period(uid)

    bc = _cnt("user_actions", k, extra="action_type='broadcast'")
    evbc = _cnt("user_actions", k, extra="action_type='event_broadcast'")
    bday = _cnt("user_actions", k, extra="action_type='birthday_greeting'")
    occ = _cnt("user_actions", k, extra="action_type='occasion_greeting'")

    reach = _safe("SELECT COUNT(*) FROM users WHERE is_authenticated=1 "
                  "AND COALESCE(is_blocked,0)=0")
    blocked = _safe("SELECT COUNT(*) FROM users WHERE is_blocked=1")

    lines = _hdr("📢 گزارش اطلاع‌رسانی", k)
    lines += ["📊 پیام‌های ارسالی:",
              f"   📢 اطلاع‌رسانی همگانی: {bc}",
              f"   🎉 اعلام رویداد: {evbc}",
              f"   🎂 تبریک تولد: {bday}",
              f"   🎊 تبریک مناسبت: {occ}",
              f"   📨 مجموع: {bc + evbc + bday + occ}", "",
              "👥 مخاطبان:",
              f"   ✅ قابل ارسال: {reach}",
              f"   🚫 مسدود: {blocked}", ""]

    # مناسبت‌های پیش رو
    try:
        import occasions as oc
        n_bd, names = oc.check_birthdays(dry_run=True)
        if n_bd:
            lines += [f"🎂 امروز {n_bd} نفر تولد دارند:",
                      "   " + "، ".join(names[:5]), ""]
    except Exception:
        pass

    # تاریخچه تبریک‌ها
    rows = _rows("""SELECT kind, COUNT(*) c FROM greeting_log
        GROUP BY kind ORDER BY c DESC LIMIT 6""")
    if rows:
        lines.append("🎊 تاریخچه تبریک‌ها:")
        for r in rows:
            lines.append(f"   • {r.get('kind') or '—'}: {r['c']}")
        lines.append("")

    # تیکت‌ها
    n_tk = _cnt("tickets", k)
    n_open = _safe("SELECT COUNT(*) FROM tickets WHERE status<>'closed'")
    if n_tk or n_open:
        lines += ["📱 پشتیبانی:",
                  f"   🎫 تیکت جدید: {n_tk}",
                  f"   🟢 باز: {n_open}"]

    send_or_edit(cid, "\n".join(lines), _back())


# ==================== ۸️⃣ گزارش ادمین‌ها ====================
def report_admins(cid, uid):
    if not _guard(cid, uid):
        return
    if not perm.has_any(uid, "sys_admins", "rp_logs"):
        return send(cid, "🔒 دسترسی ندارید")
    k = get_period(uid)

    admins = _rows("SELECT bale_user_id, first_name, last_name, "
                   "last_activity_at FROM users WHERE is_admin=1")

    lines = _hdr("👨‍💼 گزارش ادمین‌ها", k)
    lines += [f"👥 تعداد ادمین: {len(admins)}", ""]

    rank = []
    for a in admins:
        tgt = a.get("bale_user_id")
        if not tgt:
            continue
        n = _safe(f"SELECT COUNT(*) FROM user_actions WHERE bale_user_id=? "
                  f"AND {_w(k)} AND action_type NOT IN "
                  "('start','view_profile','start_unauth')", (tgt,))
        rank.append((n, a, tgt))
    rank.sort(key=lambda x: -x[0])

    if rank:
        lines.append("📊 فعالیت ادمین‌ها:")
        for n, a, tgt in rank:
            nm = f"{a.get('first_name') or ''} " \
                 f"{a.get('last_name') or ''}".strip() or "—"
            crown = "👑" if tgt == SUPER_ADMIN_ID else "👨‍💼"
            lines += [f"   {crown} {nm} — {perm.role_label(tgt)}",
                      f"      📊 {n} فعالیت | "
                      f"🕐 {_jd.fmt(a.get('last_activity_at'), 'datetime')}"]
        lines.append("")

    # کارهای انجام‌شده
    kinds = [
        ("event_created", "🎉 رویداد ساخته"),
        ("form_create", "📝 فرم ساخته"),
        ("profile_approved", "✅ پروفایل تأیید"),
        ("receipt_approved", "🧾 رسید تأیید"),
        ("broadcast", "📢 پیام همگانی"),
        ("certificate_issued", "🎓 گواهینامه صادر"),
        ("attendance", "✋ حضور ثبت"),
        ("lottery_draw", "🎲 قرعه‌کشی اجرا"),
    ]
    done = []
    for key, label in kinds:
        n = _cnt("user_actions", k, extra=f"action_type='{key}'")
        if n:
            done.append(f"   {label}: {n}")
    if done:
        lines += ["📋 کارهای انجام‌شده:"] + done + [""]

    # توزیع نقش‌ها
    roles = {}
    for a in admins:
        tgt = a.get("bale_user_id")
        if tgt:
            r, _ = perm.get_admin_role(tgt)
            roles[r] = roles.get(r, 0) + 1
    if roles:
        lines.append("🎭 توزیع نقش‌ها:")
        for r, n in sorted(roles.items(), key=lambda x: -x[1]):
            info = perm.ROLES.get(r, {})
            lines.append(f"   {info.get('icon', '⚪')} "
                         f"{info.get('name', r)}: {n}")

    send_or_edit(cid, "\n".join(lines), _back([
        [{"text": "📋 لاگ فعالیت کامل", "callback_data": "lg_list"}]]))


# ==================== ۹️⃣ برترین‌ها ====================
def report_top(cid, uid):
    if not _guard(cid, uid):
        return
    k = get_period(uid)
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    lines = _hdr("🏆 برترین‌های دوره", k)

    # امتیاز
    rows = _rows("""SELECT first_name, last_name, total_points FROM users
        WHERE COALESCE(total_points,0) > 0
        ORDER BY total_points DESC LIMIT 5""")
    if rows:
        lines += ["🏅 بیشترین امتیاز:"]
        for i, r in enumerate(rows):
            nm = f"{r.get('first_name') or ''} " \
                 f"{r.get('last_name') or ''}".strip() or "—"
            lines.append(f"   {medals[i]} {nm} — {r['total_points']} امتیاز")
        lines.append("")

    # حضور
    rows = _rows(f"""SELECT u.first_name, u.last_name, COUNT(*) c
        FROM attendance_records a
        LEFT JOIN users u ON u.bale_user_id=a.bale_user_id
        WHERE a.status IN ('present','late') AND {_w(k, 'a.created_at')}
        GROUP BY a.bale_user_id ORDER BY c DESC LIMIT 5""")
    if rows:
        lines += ["✋ پرحضورترین:"]
        for i, r in enumerate(rows):
            nm = f"{r.get('first_name') or ''} " \
                 f"{r.get('last_name') or ''}".strip() or "—"
            lines.append(f"   {medals[i]} {nm} — {r['c']} جلسه")
        lines.append("")

    # ثبت‌نام
    rows = _rows(f"""SELECT u.first_name, u.last_name, COUNT(*) c
        FROM event_registrations r
        LEFT JOIN users u ON u.bale_user_id=r.bale_user_id
        WHERE r.status<>'cancelled' AND {_w(k, 'r.created_at')}
        GROUP BY r.bale_user_id ORDER BY c DESC LIMIT 5""")
    if rows:
        lines += ["🎫 فعال‌ترین در ثبت‌نام:"]
        for i, r in enumerate(rows):
            nm = f"{r.get('first_name') or ''} " \
                 f"{r.get('last_name') or ''}".strip() or "—"
            lines.append(f"   {medals[i]} {nm} — {r['c']} رویداد")
        lines.append("")

    # دعوت
    rows = _rows("""SELECT u.first_name, u.last_name,
        (SELECT COUNT(*) FROM users x WHERE x.referred_by=u.bale_user_id) c
        FROM users u ORDER BY c DESC LIMIT 5""")
    rows = [r for r in rows if r["c"]]
    if rows:
        lines += ["👥 بیشترین دعوت:"]
        for i, r in enumerate(rows):
            nm = f"{r.get('first_name') or ''} " \
                 f"{r.get('last_name') or ''}".strip() or "—"
            lines.append(f"   {medals[i]} {nm} — {r['c']} نفر")
        lines.append("")

    # نشان‌ها
    rows = _rows("""SELECT u.first_name, u.last_name, COUNT(*) c
        FROM user_achievements a
        LEFT JOIN users u ON u.bale_user_id=a.bale_user_id
        GROUP BY a.bale_user_id ORDER BY c DESC LIMIT 3""")
    if rows:
        lines += ["🎖️ بیشترین نشان:"]
        for i, r in enumerate(rows):
            nm = f"{r.get('first_name') or ''} " \
                 f"{r.get('last_name') or ''}".strip() or "—"
            lines.append(f"   {medals[i]} {nm} — {r['c']} نشان")
        lines.append("")

    if len(lines) <= 4:
        lines.append("📭 هنوز داده‌ای برای رتبه‌بندی نیست")

    send_or_edit(cid, "\n".join(lines), _back([
        [{"text": "🏆 جدول رتبه‌بندی کامل", "callback_data": "cl_bd_points"}]]))


# ==================== 📥 خروجی کامل Excel ====================
def export_all(cid, uid):
    """📥 خروجی کامل — چند شیت"""
    if not _guard(cid, uid):
        return
    if not perm.has_perm(uid, "rp_export"):
        return send(cid, "🔒 دسترسی خروجی گرفتن ندارید")

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        return send(cid, "⚠️ نیاز به openpyxl:\npip install openpyxl")

    k = get_period(uid)
    send(cid, "⏳ در حال ساخت گزارش کامل...")

    wb = Workbook()
    show_money = perm.has_perm(uid, "fin_view")

    def sheet(title, heads, rows, color="1565C0"):
        ws = wb.create_sheet(title[:30])
        ws.sheet_view.rightToLeft = True
        ws.append(heads)
        for i, _ in enumerate(heads, 1):
            c = ws.cell(row=1, column=i)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor=color)
            c.alignment = Alignment(horizontal="center")
        for r in rows:
            ws.append(r)
        for i, h in enumerate(heads, 1):
            ws.column_dimensions[chr(64 + i)].width = max(12, min(32,
                                                                  len(str(h)) + 8))
        ws.freeze_panes = "A2"
        return ws

    # خلاصه
    ws = wb.active
    ws.title = "خلاصه"
    ws.sheet_view.rightToLeft = True
    summary = [
        ["گزارش کامل ربات نورا", ""],
        ["دوره", period_name(k)],
        ["تاریخ تهیه", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["", ""],
        ["کل کاربران", _safe("SELECT COUNT(*) FROM users")],
        ["کاربران جدید", _cnt("users", k)],
        ["احراز هویت شده",
         _safe("SELECT COUNT(*) FROM users WHERE is_authenticated=1")],
        ["کل رویدادها", _safe("SELECT COUNT(*) FROM events")],
        ["ثبت‌نام‌ها", _cnt("event_registrations", k,
                            extra="status<>'cancelled'")],
        ["کل فرم‌ها", _safe("SELECT COUNT(*) FROM forms")],
        ["پاسخ فرم", _cnt("form_responses", k,
                          extra="status IN ('completed','confirmed')")],
        ["حضور ثبت‌شده", _cnt("attendance_records", k,
                              extra="status IN ('present','late')")],
        ["گواهینامه صادرشده", _cnt("certificates", k, "issued_at")],
    ]
    if show_money:
        summary.append([f"درآمد ({CURRENCY_LABEL})",
                        money(_sum("transactions", "amount", k,
                                   extra=f"status IN {PAID}"),
                              with_unit=False)])
    for row in summary:
        ws.append(row)
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 26

    # کاربران
    sheet("کاربران",
          ["نام", "موبایل", "جنسیت", "شهر", "امتیاز", "تکمیل%",
           "وضعیت", "عضویت"],
          [[f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip(),
            r.get("mobile") or "", r.get("gender") or "",
            r.get("city") or "", r.get("total_points") or 0,
            r.get("complete_profile_percent") or 0,
            r.get("profile_status") or "", _jd.fmt(r.get('created_at'), 'datetime')]
           for r in _rows("SELECT * FROM users ORDER BY id DESC LIMIT 3000")],
          "2E7D32")

    # رویدادها
    sheet("رویدادها",
          ["عنوان", "نوع", "وضعیت", "تاریخ", "ظرفیت", "ثبت‌نام", "حضور"],
          [[r.get("title"), r.get("event_type"), r.get("status"),
            r.get("start_date") or "", r.get("capacity") or 0,
            _safe("SELECT COUNT(*) FROM event_registrations WHERE event_id=? "
                  "AND status IN ('confirmed','attended')", (r["id"],)),
            _safe("SELECT COUNT(*) FROM attendance_records a JOIN "
                  "attendance_sessions s ON s.id=a.session_id WHERE "
                  "s.event_id=? AND a.status IN ('present','late')",
                  (r["id"],))]
           for r in _rows("SELECT * FROM events ORDER BY id DESC LIMIT 1000")],
          "6A1B9A")

    # فرم‌ها
    sheet("فرم‌ها", ["عنوان", "نوع", "وضعیت", "پاسخ", "بازدید"],
          [[r.get("title"), r.get("form_type"), r.get("status"),
            r.get("responses_count") or 0, r.get("views_count") or 0]
           for r in _rows("SELECT * FROM forms ORDER BY id DESC LIMIT 1000")],
          "EF6C00")

    # حضور
    sheet("حضور و غیاب",
          ["کاربر", "جلسه", "وضعیت", "روش", "تاریخ"],
          [[f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip(),
            r.get("stitle") or "", r.get("status"), r.get("method") or "",
            _jd.fmt(r.get('created_at'), 'datetime')]
           for r in _rows("""SELECT a.*, u.first_name, u.last_name,
               s.title stitle FROM attendance_records a
               LEFT JOIN users u ON u.bale_user_id=a.bale_user_id
               LEFT JOIN attendance_sessions s ON s.id=a.session_id
               ORDER BY a.id DESC LIMIT 3000""")],
          "00838F")

    # مالی — فقط سوپرادمین
    if show_money:
        sheet("مالی",
              ["کاربر", "رویداد", f"مبلغ({CURRENCY_LABEL})", "روش", "وضعیت",
               "امتیاز", "تاریخ"],
              [[f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip(),
                r.get("ev_title") or "",
                money(r.get("amount") or 0, with_unit=False),
                r.get("method") or "wallet", r.get("status"),
                r.get("points_used") or 0, _jd.fmt(r.get('created_at'), 'datetime')]
               for r in _rows("""SELECT t.*, u.first_name, u.last_name,
                   e.title ev_title FROM transactions t
                   LEFT JOIN users u ON u.bale_user_id=t.bale_user_id
                   LEFT JOIN events e ON e.id=t.event_id
                   ORDER BY t.id DESC LIMIT 3000""")],
              "AD1457")

    # گواهینامه
    sheet("گواهینامه‌ها", ["کاربر", "رویداد", "سریال", "تاریخ"],
          [[f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip(),
            r.get("ev_title") or "", r.get("serial") or "",
            _jd.fmt(r.get('issued_at'), 'datetime')]
           for r in _rows("""SELECT c.*, u.first_name, u.last_name,
               e.title ev_title FROM certificates c
               LEFT JOIN users u ON u.bale_user_id=c.bale_user_id
               LEFT JOIN events e ON e.id=c.event_id
               ORDER BY c.id DESC LIMIT 2000""")],
          "4527A0")

    from pathlib import Path
    from config import IMPORT_DIR
    Path(IMPORT_DIR).mkdir(parents=True, exist_ok=True)
    out = Path(IMPORT_DIR) / \
        f"nora_report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    try:
        wb.save(out)
    except Exception as e:
        return send(cid, f"❌ خطا در ساخت فایل: {user_error_message(e)}")

    n_sheets = len(wb.sheetnames)
    r = send_document(cid, str(out),
                      f"📊 گزارش کامل نورا — {period_name(k)}\n"
                      f"📑 {n_sheets} شیت")
    if not r or not r.get("ok"):
        send(cid, f"⚠️ ارسال ناموفق. فایل در سرور:\n{out}")
    log_action(uid, "report_export", {"period": k})
