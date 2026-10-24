"""
📋 لاگ فعالیت ادمین — فاز ۱۲

همه فعالیت‌ها به فارسی روان ثبت و نمایش داده می‌شوند.
قبلاً کلیدهای انگلیسی مثل `event_created` ذخیره می‌شد
که برای ادمین قابل فهم نبود.
"""
import json
from datetime import datetime

from config import SUPER_ADMIN_ID
from database import db_execute, db_scalar, log
from bale_api import send, send_or_edit, send_document
from auth import is_admin as _is_admin
import permissions as perm
import jalali as _jd

LOGS_PER_PAGE = 8


# ==================== ترجمه فارسی فعالیت‌ها ====================
# کلید انگلیسی → (آیکون، متن فارسی، دسته)
ACTION_FA = {
    # کاربر
    "start":             ("🚪", "ورود به ربات", "کاربر"),
    "start_unauth":      ("🔓", "ورود بدون احراز هویت", "کاربر"),
    "authenticated":     ("✅", "احراز هویت انجام شد", "کاربر"),
    "view_profile":      ("👁️", "مشاهده پروفایل", "کاربر"),
    "profile_submitted": ("📝", "ارسال پروفایل برای تأیید", "کاربر"),
    "profile_approved":  ("✅", "تأیید پروفایل", "کاربر"),
    "profile_rejected":  ("❌", "رد پروفایل", "کاربر"),
    "referred_by":       ("👥", "ورود با کد معرف", "کاربر"),
    "delete_user":       ("🗑️", "حذف کاربر", "کاربر"),
    "export_users":      ("📤", "خروجی لیست کاربران", "کاربر"),
    "user_blocked":      ("🚫", "مسدود کردن کاربر", "کاربر"),
    "user_unblocked":    ("🔓", "رفع مسدودی کاربر", "کاربر"),
    "user_vip":          ("⭐", "تغییر وضعیت VIP", "کاربر"),
    "admin_edit_profile": ("✏️", "ویرایش پروفایل کاربر توسط ادمین", "کاربر"),
    "profile_param":     ("⚙️", "تنظیم پارامترهای پروفایل", "کاربر"),
    "inbox_reply":       ("💬", "پاسخ به پیام کاربر", "پشتیبانی"),

    # رویداد
    "event_created":     ("🎉", "ساخت رویداد", "رویداد"),
    "event_deleted":     ("🗑️", "حذف رویداد", "رویداد"),
    "event_cancel":      ("⛔", "لغو رویداد", "رویداد"),
    "event_register":    ("🎫", "ثبت‌نام در رویداد", "رویداد"),
    "event_broadcast":   ("📢", "اطلاع‌رسانی رویداد", "رویداد"),
    "event_published":   ("🚀", "انتشار رویداد", "رویداد"),
    "attendance":        ("✋", "ثبت حضور", "رویداد"),
    "session_created":   ("📋", "ساخت جلسه", "رویداد"),
    "certificate_issued": ("🎓", "صدور گواهینامه", "رویداد"),

    # فرم
    "form_create":       ("📝", "ساخت فرم", "فرم"),
    "form_publish":      ("📢", "انتشار فرم", "فرم"),
    "form_unpublish":    ("🚫", "غیرفعال کردن فرم", "فرم"),
    "form_copy":         ("📋", "کپی فرم", "فرم"),
    "form_delete":       ("🗑️", "حذف فرم", "فرم"),
    "form_submit":       ("📥", "تکمیل فرم", "فرم"),
    "field_add":         ("➕", "افزودن سوال به فرم", "فرم"),
    "form_reviewed":     ("🔀", "بررسی پاسخ فرم (گردش کار)", "فرم"),

    # مالی
    "payment_success":   ("💳", "پرداخت موفق", "مالی"),
    "payment_failed":    ("❌", "پرداخت ناموفق", "مالی"),
    "receipt_sent":      ("📸", "ارسال رسید پرداخت", "مالی"),
    "receipt_approved":  ("✅", "تأیید رسید", "مالی"),
    "receipt_rejected":  ("❌", "رد رسید", "مالی"),
    "refund":            ("💸", "بازپرداخت", "مالی"),
    "discount_used":     ("🎁", "استفاده از کد تخفیف", "مالی"),
    # 🆕 فاز ۱۳ — روش‌های پرداخت پیشرفته
    "onsite_pending":    ("💰", "ثبت‌نام با پرداخت در محل", "مالی"),
    "onsite_confirmed":  ("✅", "تأیید دریافت وجه در محل", "مالی"),
    "points_payment":    ("🏆", "پرداخت با امتیاز", "مالی"),
    "points_spent":      ("🏅", "کسر امتیاز بابت پرداخت", "مالی"),
    "points_refund":     ("↩️", "بازگشت امتیاز", "مالی"),
    "points_manual_adjust": ("🏅", "تعدیل دستی امتیاز (دفترکل)", "مالی"),
    "pay_points_toggle": ("🎛️", "تغییر وضعیت پرداخت با امتیاز", "مالی"),
    "pay_setting":       ("⚙️", "تغییر تنظیمات پرداخت", "مالی"),
    "pay_fee_toggle":    ("💳", "تغییر وضعیت کارمزد درگاه", "مالی"),
    "vpn_warn_toggle":   ("🛡️", "تغییر وضعیت هشدار فیلترشکن", "مالی"),
    "pay_fee_setting":   ("📊", "تغییر مقدار کارمزد درگاه", "مالی"),
    # ═══════════ 🆕 فاز ۱۸-الف — پرداخت مرحله‌ای ═══════════
    "payplan_started":   ("💠", "شروع پرداخت مرحله‌ای", "مالی"),
    "payplan_created":   ("📋", "ساخت طرح پرداخت", "مالی"),
    "payplan_manual_paid": ("✅", "تسویه دستی قسط", "مالی"),
    "installment_paid":  ("💳", "پرداخت قسط", "مالی"),
    # ═══════════ 🆕 فاز ۱۸-الف — پارامترهای پروفایل ═══════════
    "profile_param_added":   ("➕", "افزودن پارامتر پروفایل", "مدیریت"),
    "profile_param_removed": ("🗑️", "حذف پارامتر پروفایل", "مدیریت"),
    "profile_param_text":    ("✏️", "ویرایش متن پرسش پروفایل", "مدیریت"),
    # ═══════════ 🆕 فاز ۱۸-ب — درباره ما ═══════════
    "about_text_edited": ("✏️", "ویرایش متن درباره ما", "مدیریت"),
    "about_link_added":  ("🌐", "افزودن لینک شبکه اجتماعی", "مدیریت"),
    "identity_changed":  ("🏷️", "تغییر هویت ربات", "مدیریت"),
    # ═══════════ 🆕 فاز ۱۹ — گواهینامه ═══════════
    "cert_template_added": ("🎓", "افزودن قالب گواهینامه", "مدیریت"),
    "cert_asset_added":  ("🖼️", "افزودن تصویر گواهینامه", "مدیریت"),
    # ---- 🆕 فاز ۲۲: حضور و غیاب و صدور گواهینامه ----
    "session_method_changed": ("🔀", "تغییر روش ثبت حضور", "رویداد"),
    "session_updated":     ("⚙️", "ویرایش جلسه", "رویداد"),
    "attendance_status_set": ("✋", "تغییر وضعیت حضور", "رویداد"),
    "attendance_mark_all": ("✅", "حاضر کردن همه", "رویداد"),
    "attendance_cleared":  ("🧹", "پاک کردن حضورها", "رویداد"),
    "attendance_reminded": ("📣", "یادآوری به غایبان", "رویداد"),
    "cert_bulk_issued":    ("🎓", "صدور گروهی گواهینامه", "رویداد"),
    "cert_revoked":        ("🚫", "ابطال گواهینامه", "رویداد"),
    "cert_restored":       ("♻️", "بازگردانی گواهینامه", "رویداد"),
    # ---- 🆕 فاز ۲۳: فرم‌ساز ----
    "form_withdraw":       ("🚪", "انصراف از فرم", "فرم"),
    "form_notify":         ("📢", "اطلاع‌رسانی فرم", "فرم"),
    "form_setting":        ("⚙️", "تغییر تنظیمات فرم", "فرم"),
    # ---- 🆕 فاز ۲۴ ----
    "event_reg_restart":   ("🔄", "شروع دوباره ثبت‌نام", "رویداد"),
    # ---- 🆕 فاز ۲۶ ----
    "ticket_asset":        ("🎫", "تغییر تصویر بلیط", "مدیریت"),
    "cert_setting_changed": ("⚙️", "تغییر تنظیمات گواهینامه", "مدیریت"),
    # ═══════════ 🆕 فاز ۲۰ — تبلیغات ═══════════
    "ad_created":        ("📣", "ساخت کمپین تبلیغاتی", "اطلاع‌رسانی"),
    "ad_sent":           ("🚀", "ارسال کمپین تبلیغاتی", "اطلاع‌رسانی"),
    # 🆕 فاز ۱۷ — پرداخت غیرمتمرکز
    "paylink_created":   ("🔗", "ساخت لینک پرداخت", "مالی"),
    "paylink_paid":      ("💰", "پرداخت از طریق لینک", "مالی"),
    "paylink_toggle":    ("🔄", "تغییر وضعیت لینک پرداخت", "مالی"),
    "paylink_deleted":   ("🗑️", "حذف لینک پرداخت", "مالی"),
    "paylink_review":    ("✅", "بررسی رسید لینک پرداخت", "مالی"),
    "paylink_export":    ("📤", "خروجی پرداخت‌های غیرمتمرکز", "مالی"),
    # 🆕 فاز ۱۴ — قرعه‌کشی و گزارش
    "lottery_created":   ("🎲", "تعریف قرعه‌کشی", "رویداد"),
    "lottery_mode":      ("🎯", "تغییر روش انتخاب برنده", "رویداد"),
    "lottery_prize":     ("🎁", "افزودن جایزه قرعه‌کشی", "رویداد"),
    "lottery_draw":      ("🎲", "اجرای قرعه‌کشی", "رویداد"),
    "lottery_reset":     ("🔄", "بازنشانی قرعه‌کشی", "رویداد"),
    "lottery_export":    ("📤", "خروجی برندگان", "رویداد"),
    "event_form_linked": ("🔗", "اتصال فرم به رویداد", "رویداد"),
    # 🆕 فاز ۱۵
    "excuse_request":    ("📄", "درخواست غیبت مجاز", "رویداد"),
    "excuse_reviewed":   ("✅", "بررسی درخواست غیبت", "رویداد"),
    "form_cert":         ("🎓", "دریافت گواهینامه فرم", "فرم"),
    "form_idcard":       ("🆔", "دریافت آیدی کارت", "فرم"),
    "form_contact":      ("💬", "پیام به برگزارکننده فرم", "فرم"),
    "report_export":     ("📊", "خروجی کامل گزارش", "سیستم"),

    # امتیاز
    "point_rule":        ("🏅", "کسب امتیاز شرطی", "امتیاز"),
    "birthday_greeting": ("🎂", "تبریک تولد", "امتیاز"),
    "occasion_greeting": ("🎉", "تبریک مناسبت", "امتیاز"),
    "points_manual":     ("🎯", "تغییر دستی امتیاز", "امتیاز"),

    # باشگاه و پشتیبانی
    "achievement":       ("🎖️", "کسب نشان دستاورد", "امتیاز"),
    "reward_redeem":     ("🛍️", "خرید از فروشگاه پاداش", "امتیاز"),
    "ticket_created":    ("🎫", "ساخت تیکت پشتیبانی", "پشتیبانی"),
    "ticket_status":     ("🔄", "تغییر وضعیت تیکت", "پشتیبانی"),
    "ticket_reply":      ("💬", "پاسخ به تیکت", "پشتیبانی"),

    # سیستم
    "broadcast":         ("📢", "ارسال همگانی", "سیستم"),
    "contact_admin":     ("💬", "پیام به پشتیبانی", "سیستم"),
    "admin_added":       ("👨‍💼", "افزودن ادمین", "سیستم"),
    "admin_removed":     ("🚫", "حذف ادمین", "سیستم"),
    "admin_role":        ("🔐", "تغییر نقش ادمین", "سیستم"),
    "settings_changed":  ("⚙️", "تغییر تنظیمات", "سیستم"),
    "backup":            ("💾", "بک‌آپ دیتابیس", "سیستم"),
}

LOG_CATS = ["همه", "کاربر", "رویداد", "فرم", "مالی", "امتیاز",
            "پشتیبانی", "سیستم"]

# فعالیت‌هایی که فقط ادمین انجام می‌دهد (برای فیلتر «فقط ادمین‌ها»)
ADMIN_ACTIONS = {
    "event_created", "event_deleted", "event_cancel", "event_broadcast",
    "event_published", "session_created", "certificate_issued",
    "form_create", "form_publish", "form_unpublish", "form_delete",
    "field_add", "receipt_approved", "receipt_rejected", "refund",
    "profile_approved", "profile_rejected", "delete_user", "export_users",
    "user_blocked", "user_unblocked", "user_vip", "broadcast",
    "admin_added", "admin_removed", "admin_role", "settings_changed",
    "backup", "points_manual", "ticket_status",
}


def fa_action(key):
    """ترجمه فارسی یک فعالیت — همیشه چیزی برمی‌گرداند"""
    return ACTION_FA.get(key, ("▫️", key or "نامشخص", "سایر"))


def describe(row):
    """
    توصیف کامل فارسی یک رکورد لاگ.
    جزئیات JSON هم به فارسی خوانا تبدیل می‌شود.
    """
    icon, name, _ = fa_action(row.get("action_type"))
    extra = ""
    raw = row.get("action_data")
    if raw:
        try:
            d = json.loads(raw)
        except (ValueError, TypeError):
            d = None
        if isinstance(d, dict):
            parts = []
            if d.get("event_id"):
                t = db_execute("SELECT title FROM events WHERE id=?",
                               (d["event_id"],), fetch="one")
                parts.append(f"رویداد: {(t or {}).get('title') or d['event_id']}")
            if d.get("fid"):
                t = db_execute("SELECT title FROM forms WHERE id=?",
                               (d["fid"],), fetch="one")
                parts.append(f"فرم: {(t or {}).get('title') or d['fid']}")
            if d.get("points"):
                parts.append(f"{d['points']} امتیاز")
            if d.get("amount"):
                from config import money
                parts.append(money(d["amount"]))
            if d.get("count"):
                parts.append(f"{d['count']} مورد")
            if d.get("role"):
                r = perm.ROLES.get(d["role"], {})
                parts.append(f"نقش: {r.get('name', d['role'])}")
            if d.get("reason"):
                parts.append(f"دلیل: {d['reason']}")
            if parts:
                extra = " — " + " | ".join(str(x) for x in parts[:3])
    return f"{icon} {name}{extra}"


def record(uid, action, data=None):
    """ثبت فعالیت (جایگزین log_action با ترجمه)"""
    db_execute(
        "INSERT INTO user_actions (bale_user_id, action_type, action_data) "
        "VALUES (?,?,?)",
        (uid, action, json.dumps(data, ensure_ascii=False) if data else None))


# ==================== نمایش لاگ ====================
def show_logs(cid, uid, page=0, cat="همه", only_admins=0):
    """📋 لاگ فعالیت — کاملاً فارسی"""
    if not perm.require(cid, uid, "rp_logs", send):
        return

    where, params = [], []
    if cat and cat != "همه":
        keys = [k for k, v in ACTION_FA.items() if v[2] == cat]
        if keys:
            where.append(f"a.action_type IN ({','.join('?' * len(keys))})")
            params += keys
    if only_admins:
        where.append(f"a.action_type IN "
                     f"({','.join('?' * len(ADMIN_ACTIONS))})")
        params += list(ADMIN_ACTIONS)

    sql = """SELECT a.*, u.first_name, u.last_name, u.is_admin
        FROM user_actions a
        LEFT JOIN users u ON u.bale_user_id = a.bale_user_id"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY a.id DESC LIMIT 300"
    rows = db_execute(sql, tuple(params), fetch="all") or []

    total = db_scalar("SELECT COUNT(*) FROM user_actions")
    today = db_scalar("SELECT COUNT(*) FROM user_actions "
                      "WHERE date(created_at)=date('now')")

    if not rows:
        return send_or_edit(cid, (
            "📋 لاگ فعالیت\n━━━━━━━━━━━━━━\n\n📭 فعالیتی ثبت نشده."
        ), {"inline_keyboard": [
            [{"text": "🎛️ همه دسته‌ها", "callback_data": "lg_c_همه_0"}],
            [{"text": "🔙 بازگشت", "callback_data": "admin_panel"}]]})

    per = LOGS_PER_PAGE
    pages = max(1, (len(rows) + per - 1) // per)
    page = max(0, min(int(page or 0), pages - 1))
    chunk = rows[page * per:(page + 1) * per]

    head = f"📋 لاگ فعالیت — {cat}"
    if only_admins:
        head += " (فقط ادمین‌ها)"
    lines = [head, "━━━━━━━━━━━━━━",
             f"📊 کل: {total}  |  📅 امروز: {today}", ""]

    for r in chunk:
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
        nm = nm or f"کاربر {r.get('bale_user_id') or '?'}"
        badge = "👨‍💼" if r.get("is_admin") else "👤"
        when = _jd.fmt(r.get('created_at'), 'datetime')
        lines.append(f"{badge} {nm}")
        lines.append(f"   {describe(r)}")
        lines.append(f"   🕐 {when}")
        lines.append("")

    btns = []
    if pages > 1:
        nav = []
        if page > 0:
            nav.append({"text": "⬅️", "callback_data": f"lg_p_{page-1}_{cat}"})
        nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
        if page < pages - 1:
            nav.append({"text": "➡️", "callback_data": f"lg_p_{page+1}_{cat}"})
        btns.append(nav)

    btns.append([{"text": "🎛️ فیلتر دسته", "callback_data": "lg_cats"},
                 {"text": ("👥 همه" if only_admins else "👨‍💼 فقط ادمین‌ها"),
                  "callback_data": f"lg_adm_{0 if only_admins else 1}"}])
    btns.append([{"text": "📊 آمار فعالیت", "callback_data": "lg_stats"},
                 {"text": "📤 خروجی Excel", "callback_data": "lg_export"}])
    btns.append([{"text": "🧹 پاکسازی لاگ قدیمی", "callback_data": "lg_clean"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "admin_panel"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_categories(cid, uid):
    if not perm.require(cid, uid, "rp_logs", send):
        return
    btns = []
    for c in LOG_CATS:
        n = (db_scalar("SELECT COUNT(*) FROM user_actions") if c == "همه"
             else db_scalar(
                 f"""SELECT COUNT(*) FROM user_actions WHERE action_type IN
                 ({','.join('?' * len([k for k, v in ACTION_FA.items()
                                       if v[2] == c]))})""",
                 tuple(k for k, v in ACTION_FA.items() if v[2] == c))
             if any(v[2] == c for v in ACTION_FA.values()) else 0)
        btns.append([{"text": f"{c} ({n})", "callback_data": f"lg_c_{c}_0"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "lg_list"}])
    send_or_edit(cid, "🎛️ دسته فعالیت را انتخاب کنید:",
                 {"inline_keyboard": btns})


def show_stats(cid, uid):
    """📊 آمار فعالیت — پرکارترین ادمین‌ها و پرتکرارترین کارها"""
    if not perm.require(cid, uid, "rp_logs", send):
        return

    total = db_scalar("SELECT COUNT(*) FROM user_actions")
    today = db_scalar("SELECT COUNT(*) FROM user_actions "
                      "WHERE date(created_at)=date('now')")
    week = db_scalar("SELECT COUNT(*) FROM user_actions "
                     "WHERE created_at >= datetime('now','-7 days')")

    lines = ["📊 آمار فعالیت", "━━━━━━━━━━━━━━", "",
             f"📈 کل فعالیت‌ها: {total}",
             f"📅 امروز: {today}",
             f"🗓️ هفته اخیر: {week}", ""]

    tops = db_execute("""SELECT action_type, COUNT(*) n FROM user_actions
        GROUP BY action_type ORDER BY n DESC LIMIT 8""", fetch="all") or []
    if tops:
        lines.append("🔝 پرتکرارترین فعالیت‌ها:")
        for t in tops:
            icon, name, _ = fa_action(t["action_type"])
            lines.append(f"   {icon} {name}: {t['n']}")
        lines.append("")

    admins = db_execute("""SELECT a.bale_user_id, u.first_name, u.last_name,
        COUNT(*) n FROM user_actions a
        JOIN users u ON u.bale_user_id=a.bale_user_id
        WHERE u.is_admin=1 GROUP BY a.bale_user_id
        ORDER BY n DESC LIMIT 5""", fetch="all") or []
    if admins:
        lines.append("👨‍💼 فعال‌ترین ادمین‌ها:")
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, a in enumerate(admins):
            nm = f"{a.get('first_name') or ''} {a.get('last_name') or ''}".strip()
            lines.append(f"   {medals[i] if i < len(medals) else '•'} "
                         f"{nm or a['bale_user_id']}: {a['n']} کار")
        lines.append("")

    by_cat = {}
    for k, v in ACTION_FA.items():
        n = db_scalar("SELECT COUNT(*) FROM user_actions WHERE action_type=?", (k,))
        if n:
            by_cat[v[2]] = by_cat.get(v[2], 0) + n
    if by_cat:
        lines.append("📂 به تفکیک دسته:")
        for c, n in sorted(by_cat.items(), key=lambda x: -x[1]):
            pct = n * 100 / total if total else 0
            lines.append(f"   • {c}: {n} ({pct:.0f}%)")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "📋 لیست لاگ", "callback_data": "lg_list"}],
        [{"text": "🔙 بازگشت", "callback_data": "admin_panel"}]]})


def export_logs(cid, uid):
    """📤 خروجی Excel لاگ فعالیت — فارسی"""
    if not perm.require(cid, uid, "rp_logs", send):
        return
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        return send(cid, "❌ openpyxl نصب نیست:\npy -m pip install openpyxl")

    rows = db_execute("""SELECT a.*, u.first_name, u.last_name, u.mobile,
        u.is_admin FROM user_actions a
        LEFT JOIN users u ON u.bale_user_id=a.bale_user_id
        ORDER BY a.id DESC LIMIT 5000""", fetch="all") or []
    if not rows:
        return send(cid, "📭 لاگی برای خروجی نیست")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "لاگ فعالیت"
    ws.sheet_view.rightToLeft = True
    head = ["ردیف", "تاریخ و ساعت", "کاربر", "موبایل", "نقش",
            "دسته", "فعالیت", "جزئیات"]
    ws.append(head)
    bold = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="4472C4")
    for i in range(1, len(head) + 1):
        c = ws.cell(row=1, column=i)
        c.font = bold
        c.fill = fill
        c.alignment = Alignment(horizontal="center")

    for n, r in enumerate(rows, 1):
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
        icon, name, cat = fa_action(r.get("action_type"))
        ws.append([
            n, _jd.fmt(r.get('created_at'), 'datetime'),
            nm or str(r.get("bale_user_id") or ""),
            r.get("mobile") or "",
            "ادمین" if r.get("is_admin") else "کاربر",
            cat, f"{icon} {name}",
            describe(r),
        ])
    for i, h in enumerate(head, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = \
            max(12, min(40, len(h) + 12))
    ws.freeze_panes = "A2"

    from pathlib import Path
    from config import FILES_DIR
    d = Path(FILES_DIR) / "exports"
    d.mkdir(parents=True, exist_ok=True)
    fp = d / f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    try:
        wb.save(fp)
    except Exception as e:
        log(f"❌ ذخیره لاگ: {e}")
        return send(cid, "❌ خطا در ساخت فایل")

    res = send_document(cid, str(fp), f"📋 لاگ فعالیت ({len(rows)} رکورد)")
    if not res.get("ok"):
        send(cid, f"⚠️ ارسال ناموفق\n📁 {fp}")
    return send(cid, "✅ خروجی آماده شد", {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": "lg_list"}]]})


def clean_logs(cid, uid, confirmed=False):
    """🧹 پاکسازی لاگ‌های قدیمی‌تر از ۹۰ روز"""
    if not perm.require(cid, uid, "rp_logs", send):
        return
    old = db_scalar("SELECT COUNT(*) FROM user_actions "
                    "WHERE created_at < datetime('now','-90 days')")
    if not confirmed:
        return send_or_edit(cid, (
            f"🧹 پاکسازی لاگ قدیمی\n━━━━━━━━━━━━━━\n\n"
            f"📊 لاگ‌های قدیمی‌تر از ۹۰ روز: {old}\n\n"
            f"⚠️ این عمل بازگشت‌پذیر نیست."
        ), {"inline_keyboard": [
            [{"text": "🧹 بله، پاک کن", "callback_data": "lg_cleany"}],
            [{"text": "❌ انصراف", "callback_data": "lg_list"}]]})
    db_execute("DELETE FROM user_actions "
               "WHERE created_at < datetime('now','-90 days')")
    record(uid, "settings_changed", {"count": old, "reason": "پاکسازی لاگ"})
    send(cid, f"🧹 {old} رکورد قدیمی پاک شد")
    return show_logs(cid, uid, 0)
