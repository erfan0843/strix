"""
پنل ادمین + مدیریت کاربران + عضویت اجباری - نسخه 4.1 (فیکس شده)

فیکس‌های مهم:
- SQL Injection در صفحه‌بندی (LIMIT/OFFSET با f-string) بسته شد
- حذف کاربر حالا تأیید دومرحله‌ای دارد (قبلاً یک کلیک = حذف دائمی!)
- سوپرادمین قابل حذف/بلاک/عزل نیست
- گروه/کانال خصوصی با chat_id عددی درست ذخیره و چک می‌شود
- عنوان واقعی کانال از getChat گرفته می‌شود
- خروجی اکسل از کاربران اضافه شد
- state ادمین بعد از جستجو درست پاک می‌شود
"""
from privacy import user_error_message
import json
import os
import re
from datetime import datetime
from pathlib import Path

from config import (
    SUPER_ADMIN_ID, DB_PATH, BACKUP_DIR, IMPORT_DIR,
    USERS_PER_PAGE,
)
from database import db_execute, db_scalar, backup_db, log
from auth import (
    get_user, get_user_by_id, set_state, get_state_data, clear_state,
    get_state_name,
    get_active_channels, get_all_channels, add_force_channel,
    remove_force_channel, toggle_force_channel, set_channel_link,
    log_action, normalize_digits, normalize_mobile, is_admin as _is_admin,
)
from bale_api import (
    send, send_or_edit, send_document, send_photo,
    kb_admin, kb_cancel, kb_remove, kb_settings,
    get_chat, BTN_BACK,
)
import jalali as _jd

STATE_SEARCH = "searching"
STATE_ADD_CHANNEL = "adding_channel"
STATE_CH_LINK = "channel_link"
STATE_BROADCAST = "broadcasting"


def _guard(cid, uid):
    """بررسی دسترسی ادمین"""
    if not _is_admin(uid):
        send(cid, "❌ شما دسترسی ادمین ندارید")
        return False
    return True


def _guard_super(cid, uid):
    if uid != SUPER_ADMIN_ID:
        send(cid, "❌ این بخش فقط برای سوپرادمین است")
        return False
    return True


# ==================== ADMIN PANEL ====================
def _count(sql, params=()):
    """شمارش امن — اگر جدول نبود ۰ برمی‌گرداند"""
    try:
        return db_scalar(sql, params) or 0
    except Exception:
        return 0


def show_admin_panel(cid, uid):
    """
    👨‍💼 پنل ادمین — فاز ۱۳: خلوت و جامع

    ۷ دکمه به‌جای ۱۲ — و هر ادمین فقط چیزی را می‌بیند که
    دسترسی‌اش را دارد.
    """
    if not _guard(cid, uid):
        return
    import permissions as perm

    total = _count("SELECT COUNT(*) FROM users")
    auth = _count("SELECT COUNT(*) FROM users WHERE is_authenticated=1")
    pending = _count("SELECT COUNT(*) FROM profile_submissions "
                     "WHERE status='pending'")
    channels = len(get_active_channels())

    events_total = _count("SELECT COUNT(*) FROM events")
    events_active = _count("SELECT COUNT(*) FROM events "
                           "WHERE status='published'")
    pend_rcp = _count("SELECT COUNT(*) FROM payment_receipts "
                      "WHERE status='pending'")
    n_tk = _count("SELECT COUNT(*) FROM tickets WHERE unread_admin=1")
    n_rw = _count("SELECT COUNT(*) FROM reward_redemptions "
                  "WHERE status='pending'")

    lines = ["👨‍💼 پنل ادمین", "━━━━━━━━━━━━━━", "",
             f"🎭 {perm.role_label(uid)}", ""]

    # آمار فقط برای بخش‌هایی که دسترسی دارد
    if perm.can_section(uid, "users"):
        lines += [f"👥 کاربران: {total}  (✅ احراز: {auth})"]
    if perm.can_section(uid, "events"):
        lines += [f"🎉 رویدادها: {events_total}  (🟢 فعال: {events_active})"]

    todo = []
    if pending and perm.has_perm(uid, "us_approve"):
        todo.append(f"⏳ {pending} درخواست پروفایل")
    if pend_rcp and perm.has_any(uid, "fin_approve", "fin_view"):
        todo.append(f"🧾 {pend_rcp} رسید پرداخت")
    if n_tk and perm.has_perm(uid, "tk_manage"):
        todo.append(f"📱 {n_tk} تیکت خوانده‌نشده")
    if n_rw and perm.has_perm(uid, "club_manage"):
        todo.append(f"🛍️ {n_rw} درخواست پاداش")
    if todo:
        lines += ["", "🔴 کارهای در انتظار شما:"]
        lines += [f"   • {t}" for t in todo]
    if channels and perm.has_perm(uid, "sys_settings"):
        lines += ["", f"🔗 کانال اجباری فعال: {channels}"]

    lines += ["", "از منوی زیر انتخاب کنید:"]

    badges = {"events": events_active, "tickets": n_tk, "rewards": n_rw}
    send_or_edit(cid, "\n".join(lines),
                 kb_admin(pending, pend_rcp, uid=uid, badges=badges))


def show_notify_menu(cid, uid):
    """📢 اطلاع‌رسانی — پیام همگانی + مناسبت‌ها + اعلام رویداد"""
    if not _guard(cid, uid):
        return
    import permissions as perm
    from bale_api import kb_notify_menu

    if not perm.can_section(uid, "notify"):
        return send(cid, "🔒 دسترسی به بخش اطلاع‌رسانی ندارید")

    targets = _count("SELECT COUNT(*) FROM users WHERE is_authenticated=1 "
                     "AND COALESCE(is_blocked,0)=0")
    sent7 = _count("SELECT COUNT(*) FROM user_actions "
                   "WHERE action_type IN ('broadcast','event_broadcast') "
                   "AND created_at >= datetime('now','-7 day')")
    bdays = 0
    try:
        import occasions as oc
        bdays, _ = oc.check_birthdays(dry_run=True)
    except Exception:
        pass

    lines = ["📢 اطلاع‌رسانی", "━━━━━━━━━━━━━━", "",
             f"👥 مخاطبان قابل ارسال: {targets}",
             f"📨 ارسال‌های ۷ روز اخیر: {sent7}"]
    if bdays:
        lines += ["", f"🎂 امروز {bdays} نفر تولد دارند"]
    lines += ["", "از منوی زیر انتخاب کنید:"]

    send_or_edit(cid, "\n".join(lines), kb_notify_menu(uid))


def show_care_menu(cid, uid):
    """💬 پشتیبانی و باشگاه — تیکت + دستاورد + فروشگاه"""
    if not _guard(cid, uid):
        return
    import permissions as perm
    from bale_api import kb_care_menu

    if not perm.can_section(uid, "care"):
        return send(cid, "🔒 دسترسی به این بخش ندارید")

    n_open = _count("SELECT COUNT(*) FROM tickets WHERE status<>'closed'")
    n_unread = _count("SELECT COUNT(*) FROM tickets WHERE unread_admin=1")
    n_rw = _count("SELECT COUNT(*) FROM reward_redemptions "
                  "WHERE status='pending'")
    n_ach = _count("SELECT COUNT(*) FROM user_achievements")
    n_inbox = _count("SELECT COUNT(*) FROM admin_inbox WHERE is_read=0")

    lines = ["💬 پشتیبانی و باشگاه", "━━━━━━━━━━━━━━", ""]
    if perm.has_perm(uid, "tk_manage"):
        lines += [f"📱 تیکت باز: {n_open}",
                  f"🔴 تیکت خوانده‌نشده: {n_unread}",
                  f"📥 پیام جدید در صندوق: {n_inbox}"]
    if perm.has_perm(uid, "club_manage"):
        lines += [f"🎖️ نشان‌های اعطاشده: {n_ach}",
                  f"🛍️ درخواست پاداش در انتظار: {n_rw}"]
    lines += ["", "از منوی زیر انتخاب کنید:"]

    send_or_edit(cid, "\n".join(lines),
                 kb_care_menu(n_unread, n_rw, uid, n_inbox))


# ==================== USER MANAGEMENT ====================
def show_users_menu(cid, uid):
    """
    👥 منوی مدیریت کاربران — فاز ۱۳

    🎯 «درخواست‌های پروفایل هم بره تو مدیریت کاربران» ✅
    همه چیز مربوط به کاربران اینجاست: درخواست پروفایل، لیست، جستجو،
    افزودن، ورودی/خروجی اکسل، برچسب‌ها، ادمین‌ها، مسدودها، گزارش
    """
    if not _guard(cid, uid):
        return
    import permissions as perm
    from bale_api import kb_users_menu

    if not perm.can_section(uid, "users"):
        return send(cid, "🔒 دسترسی به مدیریت کاربران ندارید")

    total = _count("SELECT COUNT(*) FROM users")
    active = _count("SELECT COUNT(*) FROM users WHERE is_authenticated=1 "
                    "AND COALESCE(is_blocked,0)=0")
    vip = _count("SELECT COUNT(*) FROM users WHERE is_vip=1")
    blocked = _count("SELECT COUNT(*) FROM users WHERE is_blocked=1")
    admins = _count("SELECT COUNT(*) FROM users WHERE is_admin=1")
    imported = _count("SELECT COUNT(*) FROM users WHERE imported=1")
    pending = _count("SELECT COUNT(*) FROM profile_submissions "
                     "WHERE status='pending'")

    lines = [
        "👥 مدیریت کاربران", "━━━━━━━━━━━━━━", "",
        "📊 آمار سریع:",
        f"├── 👥 کل کاربران: {total}",
        f"├── 🟢 فعال: {active}",
        f"├── ⭐ VIP: {vip}",
        f"├── 👨‍💼 ادمین: {admins}",
        f"├── 📥 وارد شده از اکسل: {imported}",
        f"└── 🚫 مسدود: {blocked}",
    ]
    if pending:
        lines += ["", f"🔴 {pending} درخواست پروفایل منتظر تأیید شماست"]

    send_or_edit(cid, "\n".join(lines), kb_users_menu(
        {"total": total, "admins": admins, "blocked": blocked,
         "pending": pending}, uid=uid))


def show_admins(cid, uid):
    """
    👨‍💼 مدیریت ادمین‌ها — فاز ۱۳

    🎯 «لاگ فعالیت بره تو قسمت مدیریت ادمین ها» ✅
       لاگ فارسی کامل (lg_list) حالا از همین‌جا باز می‌شود.

    🔒 فقط سوپرادمین (sys_admins در SUPER_ONLY است).
    """
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.require(cid, uid, "sys_admins", send):
        return

    rows = db_execute("""
        SELECT id, bale_user_id, first_name, last_name, mobile,
               admin_type, last_activity_at
        FROM users WHERE is_admin=1 ORDER BY id
    """, fetch="all") or []

    lines = [f"👨‍💼 مدیریت ادمین‌ها ({len(rows)})", "━━━━━━━━━━━━━━", ""]
    btns = []
    for r in rows:
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or "بدون نام"
        tgt = r.get("bale_user_id")
        is_super = tgt == SUPER_ADMIN_ID
        crown = "👑" if is_super else "👨‍💼"
        # تعداد فعالیت ۷ روز اخیر — تا معلوم باشد کدام ادمین فعال است
        acts = _count("SELECT COUNT(*) FROM user_actions WHERE bale_user_id=? "
                      "AND created_at >= datetime('now','-7 day')", (tgt,)) \
            if tgt else 0
        lines += [
            f"{crown} {nm}",
            f"├── 📱 {r.get('mobile') or '-'}",
            f"├── 🎭 {perm.role_label(tgt) if tgt else 'ادمین'}",
            f"├── 📊 فعالیت ۷ روز: {acts}",
            f"└── 🕐 {_jd.fmt(r.get('last_activity_at'), 'datetime')}",
            "",
        ]
        btns.append([{"text": f"{crown} {nm}"[:40],
                      "callback_data": f"pm_view_{r['id']}"}])

    if not rows:
        lines.append("📭 ادمینی ثبت نشده")

    lines += ["", "💡 روی هر ادمین بزنید تا نقش و دسترسی‌هایش را",
              "تغییر دهید یا فعالیتش را ببینید."]

    btns.append([{"text": "➕ افزودن ادمین (جستجو)",
                  "callback_data": "u_search"}])
    btns.append([{"text": "📋 لاگ فعالیت (کامل)", "callback_data": "lg_list"},
                 {"text": "📊 آمار فعالیت", "callback_data": "lg_stats"}])
    btns.append([{"text": "🎭 راهنمای نقش‌ها", "callback_data": "pm_help"}])
    btns.append([{"text": "🔙 مدیریت کاربران", "callback_data": "admin_users"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_role_help(cid, uid):
    """🎭 راهنمای نقش‌ها — هر نقش چه می‌تواند بکند"""
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.require(cid, uid, "sys_admins", send):
        return

    lines = ["🎭 راهنمای نقش‌های ادمین", "━━━━━━━━━━━━━━", ""]
    for key, r in perm.ROLES.items():
        if key in ("super_admin", "custom"):
            continue
        n = len(r.get("perms") or [])
        lines += [f"{r['icon']} {r['name']}  ({n} دسترسی)",
                  f"   {r['desc']}", ""]
    lines += [
        "⚪ سفارشی",
        "   دسترسی‌ها را تک‌تک خودتان انتخاب می‌کنید",
        "",
        "━━━━━━━━━━━━━━",
        "🔒 این‌ها فقط برای سوپرادمین‌اند و به هیچ نقشی داده نمی‌شوند:",
    ]
    for k in sorted(perm.SUPER_ONLY):
        info = perm.PERM_MAP.get(k)
        if info:
            lines.append(f"   {info[1]} {info[2]}")
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 ادمین‌ها", "callback_data": "um_admins"}]]})


def show_admin_log(cid, uid):
    """
    📊 لاگ فعالیت ادمین‌ها (نسخه سریع)

    ⚠️ نسخه کامل با ترجمه فارسی، فیلتر دسته، آمار و خروجی Excel
       در activity_log.py است (دکمه «📋 لاگ فعالیت (کامل)»).
    """
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.has_any(uid, "sys_admins", "rp_logs"):
        return send(cid, "🔒 دسترسی به لاگ ندارید")

    rows = db_execute("""
        SELECT a.action_type, a.action_data, a.created_at,
               u.first_name, u.last_name
        FROM user_actions a LEFT JOIN users u ON u.bale_user_id=a.bale_user_id
        WHERE a.bale_user_id IN (SELECT bale_user_id FROM users WHERE is_admin=1)
          AND a.action_type NOT IN ('start','view_profile','start_unauth')
        ORDER BY a.id DESC LIMIT 25
    """, fetch="all") or []

    # ✅ فاز ۱۳: به‌جای جدول کوچک محلی، از ترجمه فارسی کامل استفاده کن
    try:
        from activity_log import fa_action
    except Exception:
        def fa_action(k):
            return ("▫️", k, "سایر")

    lines = ["📊 لاگ فعالیت ادمین‌ها", "━━━━━━━━━━━━━━", ""]
    if not rows:
        lines.append("📭 فعالیتی ثبت نشده")
    for r in rows:
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or "-"
        icon, fa, _cat = fa_action(r["action_type"])
        lines.append(f"{icon} {fa} — {nm}")
        lines.append(f"   📅 {_jd.fmt(r.get('created_at'), 'datetime')}")
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "📋 لاگ کامل (فیلتر + خروجی)", "callback_data": "lg_list"}],
        [{"text": "🔙 ادمین‌ها", "callback_data": "um_admins"}]]})


def show_blocked(cid, uid):
    """🚫 کاربران مسدود"""
    if not _guard(cid, uid):
        return
    rows = db_execute("""
        SELECT id, first_name, last_name, mobile FROM users
        WHERE is_blocked=1 ORDER BY id DESC LIMIT 30
    """, fetch="all") or []

    lines = [f"🚫 کاربران مسدود ({len(rows)})", "━━━━━━━━━━━━━━", ""]
    btns = []
    if not rows:
        lines.append("✅ کاربر مسدودی وجود ندارد")
    for r in rows:
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or "بدون نام"
        lines.append(f"🚫 {nm} — {r.get('mobile') or '-'}")
        btns.append([
            {"text": f"👤 {nm}"[:30], "callback_data": f"uv_{r['id']}"},
            {"text": "✅ رفع", "callback_data": f"uub_{r['id']}"},
        ])
    btns.append([{"text": "🔙 مدیریت کاربران", "callback_data": "admin_users"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_users_report(cid, uid):
    """📊 گزارش کاربران"""
    if not _guard(cid, uid):
        return
    total = db_scalar("SELECT COUNT(*) FROM users")
    auth = db_scalar("SELECT COUNT(*) FROM users WHERE is_authenticated=1")
    approved = db_scalar("SELECT COUNT(*) FROM users WHERE profile_status='approved'")
    male = db_scalar("SELECT COUNT(*) FROM users WHERE gender='مرد'")
    female = db_scalar("SELECT COUNT(*) FROM users WHERE gender='زن'")
    today = db_scalar("SELECT COUNT(*) FROM users WHERE date(created_at)=date('now')")
    week = db_scalar("SELECT COUNT(*) FROM users "
                     "WHERE created_at >= datetime('now','-7 day')")
    month = db_scalar("SELECT COUNT(*) FROM users "
                      "WHERE created_at >= datetime('now','-30 day')")
    act24 = db_scalar("SELECT COUNT(*) FROM users "
                      "WHERE last_activity_at >= datetime('now','-1 day')")
    avg = db_scalar("SELECT COALESCE(AVG(complete_profile_percent),0) FROM users")

    cities = db_execute("""SELECT city, COUNT(*) n FROM users
        WHERE city IS NOT NULL AND city!='' GROUP BY city
        ORDER BY n DESC LIMIT 8""", fetch="all") or []
    edu = db_execute("""SELECT education_level, COUNT(*) n FROM users
        WHERE education_level IS NOT NULL AND education_level!=''
        GROUP BY education_level ORDER BY n DESC LIMIT 6""", fetch="all") or []

    lines = [
        "📊 گزارش کاربران", "━━━━━━━━━━━━━━", "",
        "👥 کلی:",
        f"├── کل: {total}",
        f"├── احراز شده: {auth}",
        f"├── پروفایل تأیید شده: {approved}",
        f"└── میانگین تکمیل: {float(avg):.0f}%",
        "",
        "📈 رشد:",
        f"├── امروز: {today}",
        f"├── ۷ روز: {week}",
        f"├── ۳۰ روز: {month}",
        f"└── فعال ۲۴ساعت: {act24}",
        "",
        "👤 جنسیت:",
        f"├── 👨 مرد: {male}",
        f"└── 👩 زن: {female}",
    ]
    if cities:
        lines += ["", "🏙️ شهرهای برتر:"]
        for i, c in enumerate(cities):
            mark = "└──" if i == len(cities) - 1 else "├──"
            lines.append(f"{mark} {c['city']}: {c['n']}")
    if edu:
        lines += ["", "🎓 تحصیلات:"]
        for i, e in enumerate(edu):
            mark = "└──" if i == len(edu) - 1 else "├──"
            lines.append(f"{mark} {e['education_level']}: {e['n']}")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "📤 خروجی اکسل", "callback_data": "admin_export"}],
        [{"text": "🔙 مدیریت کاربران", "callback_data": "admin_users"}],
    ]})


STATE_ADD_USER = "adding_user"


def start_add_user(cid, uid):
    """➕ افزودن کاربر دستی"""
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_ADD_USER, {"step": 0}, merge=False)
    send(cid, (
        "➕ افزودن کاربر دستی\n"
        "━━━━━━━━━━━━━━\n\n"
        "📱 شماره موبایل را بفرستید:\n\n"
        "مثال: 09121234567"
    ), kb_cancel())


def handle_add_user(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    if text == BTN_BACK:
        clear_state(uid)
        return show_users_menu(cid, uid)

    from auth import normalize_mobile, split_full_name
    d = get_state_data(uid)
    step = int(d.get("step") or 0)

    if step == 0:
        m = normalize_mobile(text)
        if not m:
            return send(cid, "❌ شماره نامعتبر\n\nمثال: 09121234567")
        dup = db_execute("SELECT id FROM users WHERE mobile=?", (m,), fetch="one")
        if dup:
            clear_state(uid)
            send(cid, "⚠️ این شماره قبلاً ثبت شده", kb_remove())
            return show_user_detail(cid, uid, dup["id"])
        set_state(uid, STATE_ADD_USER, {"step": 1, "mobile": m}, merge=True)
        return send(cid, "👤 نام و نام خانوادگی:\n\nمثال: علی محمدی", kb_cancel())

    if step == 1:
        first, last = split_full_name(text)
        if not first:
            return send(cid, "❌ نام معتبر بنویسید")
        d = get_state_data(uid)
        clear_state(uid)
        rid = db_execute("""INSERT INTO users
            (mobile, first_name, last_name, registration_source,
             auth_method, referral_code)
            VALUES (?,?,?,'manual','manual',?)""",
            (d.get("mobile"), first, last or "",
             f"MAN{int(__import__('time').time())}"))
        if rid:
            send(cid, (
                f"✅ کاربر اضافه شد\n\n"
                f"👤 {first} {last or ''}\n"
                f"📱 {d.get('mobile')}\n\n"
                f"💡 وقتی با این شماره در ربات احراز هویت کند،\n"
                f"به همین رکورد وصل می‌شود."
            ), kb_remove())
        else:
            send(cid, "❌ خطا در ثبت", kb_remove())
        return show_users_menu(cid, uid)


def show_tags(cid, uid):
    """🏷️ برچسب‌ها و دسته‌بندی"""
    if not _guard(cid, uid):
        return
    vip = db_scalar("SELECT COUNT(*) FROM users WHERE is_vip=1")
    approved = db_scalar("SELECT COUNT(*) FROM users WHERE profile_status='approved'")
    imported = db_scalar("SELECT COUNT(*) FROM users WHERE imported=1")
    blocked = db_scalar("SELECT COUNT(*) FROM users WHERE is_blocked=1")
    admins = db_scalar("SELECT COUNT(*) FROM users WHERE is_admin=1")

    send_or_edit(cid, (
        f"🏷️ برچسب‌ها و دسته‌بندی\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"دسته‌بندی‌های فعلی:\n\n"
        f"⭐ VIP: {vip} کاربر\n"
        f"✅ پروفایل تأیید شده: {approved}\n"
        f"📥 وارد شده از اکسل: {imported}\n"
        f"👨‍💼 ادمین: {admins}\n"
        f"🚫 مسدود: {blocked}\n\n"
        f"💡 برای فیلتر کردن در اطلاع‌رسانی همگانی\n"
        f"از همین دسته‌بندی‌ها استفاده می‌شود."
    ), {"inline_keyboard": [
        [{"text": f"⭐ لیست VIP ({vip})", "callback_data": "um_vip"}],
        [{"text": "📢 اطلاع‌رسانی به یک دسته",
          "callback_data": "admin_broadcast"}],
        [{"text": "🔙 مدیریت کاربران", "callback_data": "admin_users"}],
    ]})


def show_vip(cid, uid):
    if not _guard(cid, uid):
        return
    rows = db_execute("""SELECT id, first_name, last_name, mobile
        FROM users WHERE is_vip=1 ORDER BY id DESC LIMIT 30""", fetch="all") or []
    lines = [f"⭐ کاربران VIP ({len(rows)})", "━━━━━━━━━━━━━━", ""]
    btns = []
    if not rows:
        lines.append("📭 کاربر VIP وجود ندارد")
    for r in rows:
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or "بدون نام"
        lines.append(f"⭐ {nm} — {r.get('mobile') or '-'}")
        btns.append([{"text": f"⭐ {nm}"[:38], "callback_data": f"uv_{r['id']}"}])
    btns.append([{"text": "🔙 برچسب‌ها", "callback_data": "um_tags"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_user_list(cid, uid, page=0):
    if not _guard(cid, uid):
        return

    page = max(0, int(page or 0))
    per = USERS_PER_PAGE
    total = db_scalar("SELECT COUNT(*) FROM users")
    if total == 0:
        return send(cid, "📭 هنوز کاربری ثبت نشده است", kb_admin(uid=uid))

    total_pages = max(1, (total + per - 1) // per)
    page = min(page, total_pages - 1)

    # ✅ فیکس SQL Injection: پارامتری به‌جای f-string
    users = db_execute(
        "SELECT id, first_name, last_name, mobile, is_blocked, is_vip, is_admin, profile_status "
        "FROM users ORDER BY id DESC LIMIT ? OFFSET ?",
        (per, page * per), fetch="all",
    )

    btns = []
    for u in users:
        nm = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip() or "بدون نام"
        badge = ""
        if u.get("is_blocked"):
            badge += "🚫"
        if u.get("is_vip"):
            badge += "⭐"
        if u.get("is_admin"):
            badge += "👑"
        if u.get("profile_status") == "pending":
            badge += "⏳"
        label = f"{badge}👤 {nm}"
        if u.get("mobile"):
            label += f" — {u['mobile']}"
        btns.append([{"text": label[:60], "callback_data": f"uv_{u['id']}"}])

    nav = []
    if page > 0:
        nav.append({"text": "◀️ قبلی", "callback_data": f"up_{page-1}"})
    nav.append({"text": f"{page+1}/{total_pages}", "callback_data": "noop"})
    if page < total_pages - 1:
        nav.append({"text": "بعدی ▶️", "callback_data": f"up_{page+1}"})
    btns.append(nav)

    btns.append([{"text": "🔍 جستجو", "callback_data": "u_search"}])
    btns.append([{"text": "🔙 مدیریت کاربران", "callback_data": "admin_users"}])

    send_or_edit(cid, f"👥 مدیریت کاربران ({total} نفر)\n\nروی هر کاربر بزنید:",
                 {"inline_keyboard": btns})


def show_user_detail(cid, admin_id, target_id):
    if not _guard(cid, admin_id):
        return

    u = get_user_by_id(target_id)
    if not u:
        return send(cid, "❌ کاربر یافت نشد")

    is_super_target = (u.get("bale_user_id") == SUPER_ADMIN_ID)

    flags = []
    if u.get("is_blocked"):
        flags.append("🚫 مسدود")
    if u.get("is_vip"):
        flags.append("⭐ VIP")
    if is_super_target:
        flags.append("👑 سوپرادمین")
    elif u.get("is_admin"):
        flags.append("👨‍💼 ادمین")

    fields = [
        ("📛 نام", u.get("first_name")),
        ("📛 نام خانوادگی", u.get("last_name")),
        ("📱 موبایل", u.get("mobile")),
        ("🆔 کد ملی", u.get("national_id")),
        ("📅 تاریخ تولد", u.get("birth_date")),
        ("👤 جنسیت", u.get("gender")),
        ("👨 نام پدر", u.get("father_name")),
        ("🗺️ استان", u.get("province")),
        ("🏙️ شهر", u.get("city")),
        ("🏠 آدرس", u.get("address")),
        ("📧 ایمیل", u.get("email")),
        ("🎓 مقطع", u.get("education_level")),
        ("💼 شغل", u.get("job_title")),
    ]

    lines = [
        f"👤 جزئیات کاربر  {' '.join(flags)}",
        "━━━━━━━━━━━━━━",
        "",
        f"🔢 شناسه داخلی: {u['id']}",
        f"🆔 آیدی بله: {u.get('bale_user_id') or '— (وارد نشده)'}",
        "",
    ]
    for label, val in fields:
        lines.append(f"{label}: {str(val).strip() if val else '—'}")

    lines += [
        "",
        "📊 وضعیت:",
        f"├── احراز هویت: {'✅' if u.get('is_authenticated') else '❌'}",
        f"├── پروفایل: {u.get('profile_status') or 'draft'}",
        f"├── درصد تکمیل: {u.get('complete_profile_percent') or 0}%",
        f"├── منبع: {u.get('registration_source') or '-'}",
        f"└── آخرین فعالیت: {_jd.fmt(u.get('last_activity_at'), 'datetime')}",
        "",
        f"📅 عضویت: {_jd.fmt(u.get('created_at'), 'datetime')}",
    ]

    btns = []
    if not is_super_target:
        if u.get("is_blocked"):
            btns.append([{"text": "✅ رفع مسدودی", "callback_data": f"uub_{target_id}"}])
        else:
            btns.append([{"text": "🚫 مسدود کردن", "callback_data": f"ub_{target_id}"}])
        btns.append([
            {"text": "⭐ تغییر VIP", "callback_data": f"uvip_{target_id}"},
            {"text": "👑 تغییر ادمین", "callback_data": f"uadm_{target_id}"},
        ])
        if admin_id == SUPER_ADMIN_ID:
            if u.get("is_admin"):
                btns.append([{"text": "🔐 نقش و دسترسی‌ها",
                              "callback_data": f"pm_view_{target_id}"}])
            btns.append([{"text": "🗑️ حذف کاربر", "callback_data": f"udq_{target_id}"}])
    else:
        btns.append([{"text": "🔒 سوپرادمین قابل تغییر نیست", "callback_data": "noop"}])

    # ✏️ فاز ۱۷ — ویرایش کامل پروفایل توسط ادمین
    btns.insert(0, [{"text": "✏️ ویرایش پروفایل کاربر",
                     "callback_data": f"upe_{target_id}"}])
    btns.append([{"text": "🔙 لیست کاربران", "callback_data": "um_list"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ══════════════════════════════════════════════════════════
# ✏️ فاز ۱۷ — ویرایش ریز جزئیات پروفایل کاربر توسط ادمین
#
# درخواست کاربر: «ریز جزییات پروفایل کاربران رو تو بخش مدیریت
#   کاربران برام قابل تغییر و تنظیم کن»
# ══════════════════════════════════════════════════════════
STATE_EDIT_PROFILE = "adm_edit_profile"

# فیلدهای قابل ویرایش — (کلید، برچسب، نوع)
#   text | choice | date | num
PROFILE_EDIT_FIELDS = [
    ("first_name",      "👤 نام",              "text"),
    ("last_name",       "👤 نام خانوادگی",     "text"),
    ("mobile",          "📱 موبایل",           "mobile"),
    ("national_id",     "🆔 کد ملی",           "text"),
    ("birth_date",      "📅 تاریخ تولد",       "date"),
    ("gender",          "🚻 جنسیت",            "choice"),
    ("father_name",     "👨 نام پدر",          "text"),
    ("mother_name",     "👩 نام مادر",         "text"),
    ("province",        "🗺️ استان",            "text"),
    ("city",            "🏙️ شهر",              "text"),
    ("address",         "🏠 آدرس",             "text"),
    ("postal_code",     "📮 کد پستی",          "text"),
    ("education_level", "🎓 مقطع تحصیلی",      "choice"),
    ("field_of_study",  "📚 رشته",             "text"),
    ("university",      "🏫 دانشگاه",          "text"),
    ("job_title",       "💼 شغل",              "text"),
    ("company_name",    "🏢 محل کار",          "text"),
    ("email",           "📧 ایمیل",            "text"),
    ("bio",             "📝 بیو",              "text"),
    ("total_points",    "🏅 امتیاز",           "num"),
]

PROFILE_EDIT_MAP = {k: (lbl, t) for k, lbl, t in PROFILE_EDIT_FIELDS}

GENDER_OPTS = ["مرد", "زن"]

EDU_OPTS = ["زیر دیپلم", "دیپلم", "فوق دیپلم", "کارشناسی",
            "کارشناسی ارشد", "دکتری", "حوزوی"]


def show_profile_editor(cid, admin_id, target_id, page=0):
    """✏️ ویرایشگر پروفایل — همه فیلدها یکجا"""
    if not _guard(cid, admin_id):
        return
    import permissions as perm
    if not perm.require(cid, admin_id, "us_edit", send):
        return

    u = get_user_by_id(target_id)
    if not u:
        return send(cid, "❌ کاربر یافت نشد")
    if u.get("bale_user_id") == SUPER_ADMIN_ID and admin_id != SUPER_ADMIN_ID:
        return send(cid, "🔒 پروفایل سوپرادمین قابل تغییر نیست")

    nm = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip()
    filled = sum(1 for k, _, _ in PROFILE_EDIT_FIELDS
                 if str(u.get(k) or "").strip())

    lines = [
        f"✏️ ویرایش پروفایل — {nm or 'بدون نام'}",
        "━━━━━━━━━━━━━━", "",
        f"📊 {filled} از {len(PROFILE_EDIT_FIELDS)} فیلد پر شده",
        f"📈 درصد تکمیل: {u.get('complete_profile_percent') or 0}%",
        f"📋 وضعیت: {u.get('profile_status') or 'draft'}", "",
        "روی هر فیلد بزنید تا تغییرش دهید:", "",
    ]

    btns = []
    for key, label, _t in PROFILE_EDIT_FIELDS:
        val = str(u.get(key) or "").strip()
        show = (val[:18] + "…") if len(val) > 18 else (val or "—")
        lines.append(f"{label}: {val or '—'}")
        btns.append([{"text": f"{label}: {show}"[:44],
                      "callback_data": f"upf_{key}_{target_id}"}])

    st = u.get("profile_status") or "draft"
    btns.append([{"text": ("✅ تأیید پروفایل" if st != "approved"
                           else "↩️ لغو تأیید"),
                  "callback_data": f"upst_{target_id}"}])
    btns.append([{"text": "🔄 محاسبه مجدد درصد",
                  "callback_data": f"uprc_{target_id}"}])
    btns.append([{"text": "🔙 جزئیات کاربر",
                  "callback_data": f"uv_{target_id}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_edit_profile_field(cid, admin_id, key, target_id):
    """شروع ویرایش یک فیلد"""
    if not _guard(cid, admin_id):
        return
    import permissions as perm
    if not perm.require(cid, admin_id, "us_edit", send):
        return
    if key not in PROFILE_EDIT_MAP:
        return send(cid, "❌ فیلد نامعتبر")

    u = get_user_by_id(target_id)
    if not u:
        return send(cid, "❌ کاربر یافت نشد")
    if u.get("bale_user_id") == SUPER_ADMIN_ID and admin_id != SUPER_ADMIN_ID:
        return send(cid, "🔒 پروفایل سوپرادمین قابل تغییر نیست")

    label, ftype = PROFILE_EDIT_MAP[key]
    cur = str(u.get(key) or "").strip() or "—"

    # فیلدهای انتخابی → دکمه
    if ftype == "choice":
        opts = GENDER_OPTS if key == "gender" else EDU_OPTS
        btns = [[{"text": ("✅ " if o == u.get(key) else "") + o,
                  "callback_data": f"upv_{key}_{i}_{target_id}"}]
                for i, o in enumerate(opts)]
        btns.append([{"text": "🗑️ خالی کردن",
                      "callback_data": f"upv_{key}_x_{target_id}"}])
        btns.append([{"text": "🔙 بازگشت",
                      "callback_data": f"upe_{target_id}"}])
        return send_or_edit(cid, f"{label}\n━━━━━━━━━━━━━━\n\n"
                                 f"📄 فعلی: {cur}\n\nیکی را انتخاب کنید:",
                            {"inline_keyboard": btns})

    hint = {
        "mobile": "شماره موبایل:\n\nمثال: 09121234567",
        "date": "تاریخ شمسی:\n\nمثال: 1370/05/12",
        "num": "عدد جدید:",
    }.get(ftype, "مقدار جدید را بنویسید:")

    set_state(admin_id, STATE_EDIT_PROFILE,
              {"tid": target_id, "key": key}, merge=False)
    send(cid, (f"✏️ {label}\n━━━━━━━━━━━━━━\n\n"
               f"📄 مقدار فعلی: {cur}\n\n{hint}\n\n"
               f"💡 «-» = خالی کردن"), kb_cancel())


def set_profile_choice(cid, admin_id, key, idx, target_id):
    """ثبت مقدار فیلد انتخابی"""
    if not _guard(cid, admin_id):
        return
    import permissions as perm
    if not perm.require(cid, admin_id, "us_edit", send):
        return
    if key not in PROFILE_EDIT_MAP:
        return send(cid, "❌ فیلد نامعتبر")
    u = get_user_by_id(target_id)
    if not u:
        return send(cid, "❌ کاربر یافت نشد")

    opts = GENDER_OPTS if key == "gender" else EDU_OPTS
    if idx == "x":
        val = None
    else:
        try:
            val = opts[int(idx)]
        except (ValueError, IndexError, TypeError):
            return send(cid, "❌ گزینه نامعتبر")

    db_execute(f"UPDATE users SET {key}=?, updated_at=CURRENT_TIMESTAMP "
               "WHERE id=?", (val, target_id))
    _recalc_percent(target_id)
    log_action(admin_id, "admin_edit_profile",
               {"target": target_id, "field": key})
    return show_profile_editor(cid, admin_id, target_id)


def handle_edit_profile(message):
    """دریافت مقدار متنی جدید"""
    admin_id = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    d = get_state_data(admin_id)
    tid, key = d.get("tid"), d.get("key")

    if text in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(admin_id)
        send(cid, "❌ لغو شد", kb_remove())
        return show_profile_editor(cid, admin_id, tid)

    if key not in PROFILE_EDIT_MAP:
        clear_state(admin_id)
        return send(cid, "❌ فیلد نامعتبر", kb_remove())

    label, ftype = PROFILE_EDIT_MAP[key]

    if text == "-":
        val = None
    elif ftype == "mobile":
        val = normalize_mobile(text)
        if not val:
            return send(cid, "⚠️ شماره معتبر نیست.\nمثال: 09121234567")
        dup = db_execute("SELECT id FROM users WHERE mobile=? AND id<>?",
                         (val, tid), fetch="one")
        if dup:
            return send(cid, "⚠️ این شماره برای کاربر دیگری ثبت شده است")
    elif ftype == "date":
        t = normalize_digits(text).replace("-", "/")
        if not re.match(r"^1[34]\d{2}/\d{1,2}/\d{1,2}$", t):
            return send(cid, "⚠️ قالب درست نیست.\nمثال: 1370/05/12")
        val = t
    elif ftype == "num":
        digits = re.sub(r"[^\d]", "", normalize_digits(text))
        if not digits:
            return send(cid, "⚠️ فقط عدد بفرستید:")
        val = min(1000000, int(digits))
    else:
        val = text[:500]
        if key == "national_id":
            nid = re.sub(r"[^\d]", "", normalize_digits(text))
            if nid and len(nid) != 10:
                return send(cid, "⚠️ کد ملی باید ۱۰ رقم باشد:")
            val = nid or None
        elif key == "email" and val and "@" not in val:
            return send(cid, "⚠️ ایمیل معتبر نیست:")

    db_execute(f"UPDATE users SET {key}=?, updated_at=CURRENT_TIMESTAMP "
               "WHERE id=?", (val, tid))
    _recalc_percent(tid)
    clear_state(admin_id)
    log_action(admin_id, "admin_edit_profile", {"target": tid, "field": key})
    send(cid, f"✅ {label} ذخیره شد", kb_remove())
    return show_profile_editor(cid, admin_id, tid)


def _recalc_percent(target_id):
    """🔄 محاسبه مجدد درصد تکمیل پروفایل"""
    u = get_user_by_id(target_id)
    if not u:
        return 0
    try:
        from profile import DB_FIELDS
        keys = DB_FIELDS
    except Exception:
        keys = [k for k, _, _ in PROFILE_EDIT_FIELDS if k != "total_points"]
    filled = sum(1 for k in keys if str(u.get(k) or "").strip())
    pct = int(filled * 100 / len(keys)) if keys else 0
    db_execute("UPDATE users SET complete_profile_percent=? WHERE id=?",
               (pct, target_id))
    return pct


def recalc_profile(cid, admin_id, target_id):
    """دکمه محاسبه مجدد"""
    if not _guard(cid, admin_id):
        return
    pct = _recalc_percent(target_id)
    send(cid, f"🔄 درصد تکمیل به‌روز شد: {pct}%")
    return show_profile_editor(cid, admin_id, target_id)


def toggle_profile_status(cid, admin_id, target_id):
    """✅ تأیید / لغو تأیید پروفایل"""
    if not _guard(cid, admin_id):
        return
    import permissions as perm
    if not perm.require(cid, admin_id, "us_approve", send):
        return
    u = get_user_by_id(target_id)
    if not u:
        return send(cid, "❌ کاربر یافت نشد")

    new = "draft" if (u.get("profile_status") == "approved") else "approved"
    db_execute("""UPDATE users SET profile_status=?,
        profile_approved_at=CASE WHEN ?='approved'
            THEN CURRENT_TIMESTAMP ELSE NULL END,
        updated_at=CURRENT_TIMESTAMP WHERE id=?""", (new, new, target_id))
    log_action(admin_id, "profile_approved" if new == "approved"
               else "profile_rejected", {"target": target_id})

    if u.get("bale_user_id"):
        try:
            send(u["bale_user_id"],
                 "✅ پروفایل شما توسط ادمین تأیید شد" if new == "approved"
                 else "ℹ️ وضعیت تأیید پروفایل شما تغییر کرد")
        except Exception as e:
            log(f"⚠️ اعلام تغییر پروفایل: {e}")

    send(cid, "✅ پروفایل تأیید شد" if new == "approved"
              else "↩️ تأیید پروفایل لغو شد")
    return show_profile_editor(cid, admin_id, target_id)


# ══════════════════════════════════════════════════════════
# ⚙️ فاز ۱۷-ج — تنظیم پارامترهای پروفایل کاربران
#
# ادمین تعیین می‌کند چه فیلدهایی از کاربر پرسیده شود
# و کدام‌ها اجباری باشند.
# ══════════════════════════════════════════════════════════
def show_profile_params(cid, uid):
    """⚙️ پارامترهای پروفایل — کدام فیلد پرسیده شود؟"""
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.require(cid, uid, "sys_settings", send):
        return

    from profile import FORM_STEPS, LABELS, field_on, field_required

    n_on = sum(1 for st in FORM_STEPS
               if st["key"] == "full_name" or field_on(st["key"]))
    n_req = sum(1 for st in FORM_STEPS
                if st["key"] == "full_name" or
                (field_on(st["key"]) and
                 field_required(st["key"], st["required"])))

    lines = [
        "⚙️ پارامترهای پروفایل کاربران", "━━━━━━━━━━━━━━", "",
        "تعیین کنید هنگام تکمیل پروفایل، چه اطلاعاتی",
        "از کاربر پرسیده شود و کدام‌ها اجباری باشند.", "",
        f"📊 فعال: {n_on} فیلد  |  ⭐ اجباری: {n_req}", "",
        "🟢 = پرسیده می‌شود   ⚪ = پرسیده نمی‌شود",
        "⭐ = اجباری          ○ = اختیاری", "",
    ]

    from profile import MEDIA_TYPES, prompt_of

    btns = []
    for st in FORM_STEPS:
        k = st["key"]
        nm = LABELS.get(k, k) if k != "full_name" else "👤 نام و نام خانوادگی"
        if k == "full_name":
            lines.append(f"🔒 {nm} — همیشه فعال و اجباری")
            continue
        on = field_on(k)
        req = field_required(k, st["required"])
        mark = "🟢" if on else "⚪"
        star = " ⭐" if (on and req) else (" ○" if on else "")
        # 🖼️ نشانهٔ رسانه‌ای بودن
        media = ""
        if st.get("ftype") in MEDIA_TYPES:
            media = f" {MEDIA_TYPES[st['ftype']][0]}"
        lines.append(f"{mark} {nm}{media}{star}")
        row = [{"text": f"{mark} {nm}"[:24],
                "callback_data": f"pfo_{k}"}]
        if on:
            row.append({"text": "⭐" if req else "○",
                        "callback_data": f"pfr_{k}"})
        # ✏️ فاز ۳۸ — ویرایش متن سؤال
        row.append({"text": "✏️", "callback_data": f"pfv_{k}"})
        btns.append(row)

    # ➕ فاز ۱۸-الف — پارامترهای سفارشی (از کاتالوگ فرم‌ساز)
    from profile import custom_fields
    cf = custom_fields()
    if cf:
        lines += ["", "➕ پارامترهای سفارشی:"]
        for c in cf:
            k = c.get("key")
            on = field_on(k)
            req = field_required(k, bool(c.get("required")))
            mark = "🟢" if on else "⚪"
            star = " ⭐" if (on and req) else (" ○" if on else "")
            nm = f"{c.get('icon','▫️')} {c.get('name') or k}"
            media = ""
            if c.get("ftype") in MEDIA_TYPES:
                media = f" {MEDIA_TYPES[c['ftype']][0]}"
            lines.append(f"{mark} {nm}{media}{star}")
            row = [{"text": f"{mark} {nm}"[:22],
                    "callback_data": f"pfo_{k}"}]
            if on:
                row.append({"text": "⭐" if req else "○",
                            "callback_data": f"pfr_{k}"})
            row.append({"text": "✏️", "callback_data": f"pfv_{k}"})
            row.append({"text": "🗑️", "callback_data": f"pfdel_{k}"})
            btns.append(row)

    lines += ["", "💡 نام فیلد = روشن/خاموش  ·  ⭐/○ = اجباری",
              "✏️ = ویرایش متن سؤال  ·  🗑️ = حذف"]
    btns.append([{"text": "📝 افزودن پرسش متنی",
                  "callback_data": "pfnew_text"},
                 {"text": "🖼️ افزودن رسانه",
                  "callback_data": "pfnew_media"}])
    btns.append([{"text": "➕ افزودن از کاتالوگ فرم‌ساز",
                  "callback_data": "pfadd"}])
    btns.append([{"text": "♻️ بازگشت به پیش‌فرض",
                  "callback_data": "pf_reset"}])
    btns.append([{"text": "🔙 مدیریت کاربران", "callback_data": "admin_users"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ══════════════════════════════════════════════════════════
# ➕ فاز ۱۸-الف — افزودن پارامتر سفارشی به پروفایل
#
# 🎯 «اضافه کردن پارامتر هم بزار، از پارامتر های فرم ساز هم
#     میتونی استفاده کنی»
# ══════════════════════════════════════════════════════════
def show_add_param(cid, uid, cat=None):
    """کاتالوگ فیلدهای فرم‌ساز برای افزودن به پروفایل"""
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.require(cid, uid, "sys_settings", send):
        return

    from forms import FIELD_TYPES, FIELD_CATS, POPULAR_FIELDS
    from profile import custom_fields, FORM_STEPS

    taken = {c.get("key") for c in custom_fields()}
    taken |= {st["key"] for st in FORM_STEPS}

    if not cat:
        lines = ["➕ افزودن پارامتر به پروفایل", "━━━━━━━━━━━━━━", "",
                 "از کاتالوگ فرم‌ساز یک فیلد انتخاب کنید.", "",
                 "⚡ پرکاربردها:"]
        btns = []
        row = []
        for k in POPULAR_FIELDS:
            if k in taken:
                continue
            m = FIELD_TYPES.get(k)
            if not m:
                continue
            row.append({"text": f"{m['icon']} {m['name']}"[:20],
                        "callback_data": f"pfadd_{k}"})
            if len(row) == 2:
                btns.append(row)
                row = []
        if row:
            btns.append(row)
        btns.append([{"text": "📂 همه دسته‌ها", "callback_data": "pfcat"}])
        btns.append([{"text": "🔙 پارامترها",
                      "callback_data": "admin_profile_params"}])
        return send_or_edit(cid, "\n".join(lines),
                            {"inline_keyboard": btns})

    if cat == "_list":
        btns = [[{"text": f"{ic} {nm}", "callback_data": f"pfcat_{key}"}]
                for key, ic, nm in FIELD_CATS]
        btns.append([{"text": "🔙 بازگشت", "callback_data": "pfadd"}])
        return send_or_edit(cid, "📂 دسته‌بندی فیلدها:",
                            {"inline_keyboard": btns})

    info = next((c for c in FIELD_CATS if c[0] == cat), None)
    btns = []
    for k, m in FIELD_TYPES.items():
        if m.get("cat") != cat or k in taken:
            continue
        btns.append([{"text": f"{m['icon']} {m['name']}"[:34],
                      "callback_data": f"pfadd_{k}"}])
    if not btns:
        btns.append([{"text": "— همه اضافه شده‌اند —",
                      "callback_data": "noop"}])
    btns.append([{"text": "🔙 دسته‌ها", "callback_data": "pfcat"}])
    ttl = f"{info[1]} {info[2]}" if info else cat
    return send_or_edit(cid, f"📂 {ttl}\n━━━━━━━━━━━━━━\n\nیک فیلد انتخاب کنید:",
                        {"inline_keyboard": btns})


def add_param(cid, uid, ftype):
    """فیلد انتخاب‌شده را به پروفایل اضافه می‌کند"""
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.require(cid, uid, "sys_settings", send):
        return

    from forms import FIELD_TYPES
    from profile import custom_fields, save_custom_fields, FORM_STEPS
    from database import set_setting as _ss

    m = FIELD_TYPES.get(ftype)
    if not m:
        return send(cid, "❌ فیلد نامعتبر")

    items = custom_fields()
    if any(c.get("key") == ftype for c in items) or \
            any(st["key"] == ftype for st in FORM_STEPS):
        return send(cid, "ℹ️ این پارامتر از قبل هست")

    items.append({
        "key": ftype,
        "name": m.get("name") or ftype,
        "icon": m.get("icon") or "▫️",
        "ftype": ftype,
        "prompt": f"{m.get('icon','▫️')} {m.get('q') or m.get('name')}:",
        "required": False,
    })
    save_custom_fields(items)
    _ss(f"pf_{ftype}_on", "1", "پارامتر سفارشی", "profile", uid)
    log_action(uid, "profile_param_added", {"key": ftype})
    send(cid, f"✅ «{m.get('icon','')} {m.get('name')}» به پروفایل اضافه شد")
    return show_profile_params(cid, uid)


def del_param(cid, uid, key):
    """حذف یک پارامتر سفارشی"""
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.require(cid, uid, "sys_settings", send):
        return
    from profile import custom_fields, save_custom_fields
    items = [c for c in custom_fields() if c.get("key") != key]
    save_custom_fields(items)
    log_action(uid, "profile_param_removed", {"key": key})
    send(cid, "🗑️ پارامتر حذف شد")
    return show_profile_params(cid, uid)


def toggle_profile_field(cid, uid, key):
    """🟢/⚪ روشن یا خاموش کردن یک فیلد پروفایل"""
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.require(cid, uid, "sys_settings", send):
        return
    from profile import FORM_STEPS, field_on
    from database import set_setting as _ss

    valid = {st["key"] for st in FORM_STEPS if st["key"] != "full_name"}
    if key not in valid:
        return send(cid, "❌ فیلد نامعتبر")

    new = "0" if field_on(key) else "1"
    _ss(f"pf_{key}_on", new, f"پروفایل: {key}", "profile", uid)
    log_action(uid, "profile_param", {"field": key, "on": new})
    return show_profile_params(cid, uid)


def toggle_profile_required(cid, uid, key):
    """⭐/○ اجباری یا اختیاری کردن یک فیلد"""
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.require(cid, uid, "sys_settings", send):
        return
    from profile import FORM_STEPS, field_required, field_on
    from database import set_setting as _ss

    st = next((x for x in FORM_STEPS if x["key"] == key), None)
    if not st or key == "full_name":
        return send(cid, "❌ فیلد نامعتبر")
    if not field_on(key):
        send(cid, "⚠️ ابتدا این فیلد را فعال کنید")
        return show_profile_params(cid, uid)

    cur = field_required(key, st["required"])
    _ss(f"pf_{key}_req", "0" if cur else "1",
        f"پروفایل اجباری: {key}", "profile", uid)
    log_action(uid, "profile_param", {"field": key, "req": not cur})
    return show_profile_params(cid, uid)


def reset_profile_params(cid, uid):
    """♻️ بازگشت همه پارامترها به پیش‌فرض"""
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.require(cid, uid, "sys_settings", send):
        return
    # 🔴 فاز ۳۸: متن‌های سفارشی پرسش (pf_*_q) هم باید پاک شوند،
    #    وگرنه «بازگشت به پیش‌فرض» نیمه‌کاره بود و سؤال‌های
    #    دست‌کاری‌شده سر جایشان می‌ماندند.
    db_execute("DELETE FROM settings WHERE key LIKE 'pf_%_on' "
               "OR key LIKE 'pf_%_req' OR key LIKE 'pf_%_q'")
    from database import clear_settings_cache
    clear_settings_cache()
    log_action(uid, "profile_param", {"reset": True})
    send(cid, "♻️ پارامترهای پروفایل به حالت پیش‌فرض برگشت")
    return show_profile_params(cid, uid)


def handle_user_action(cid, admin_id, data):
    if not _guard(cid, admin_id):
        return

    def _tid(prefix):
        try:
            return int(data[len(prefix):])
        except (ValueError, TypeError):
            return None

    # --- مسدود ---
    if data.startswith("ub_"):
        tid = _tid("ub_")
        t = get_user_by_id(tid) if tid else None
        if not t:
            return send(cid, "❌ کاربر یافت نشد")
        if t.get("bale_user_id") == SUPER_ADMIN_ID:
            return send(cid, "⛔ سوپرادمین را نمی‌توان مسدود کرد")
        db_execute("UPDATE users SET is_blocked=1 WHERE id=?", (tid,))
        send(cid, "🚫 کاربر مسدود شد")
        return show_user_detail(cid, admin_id, tid)

    # --- رفع مسدودی ---
    if data.startswith("uub_"):
        tid = _tid("uub_")
        db_execute("UPDATE users SET is_blocked=0 WHERE id=?", (tid,))
        send(cid, "✅ مسدودی برداشته شد")
        return show_user_detail(cid, admin_id, tid)

    # --- VIP ---
    if data.startswith("uvip_"):
        tid = _tid("uvip_")
        t = get_user_by_id(tid)
        if not t:
            return send(cid, "❌ کاربر یافت نشد")
        new = 0 if t.get("is_vip") else 1
        db_execute("UPDATE users SET is_vip=? WHERE id=?", (new, tid))
        send(cid, f"⭐ VIP: {'فعال شد' if new else 'غیرفعال شد'}")
        return show_user_detail(cid, admin_id, tid)

    # --- ادمین ---
    if data.startswith("uadm_"):
        tid = _tid("uadm_")
        t = get_user_by_id(tid)
        if not t:
            return send(cid, "❌ کاربر یافت نشد")
        if t.get("bale_user_id") == SUPER_ADMIN_ID:
            return send(cid, "⛔ سوپرادمین همیشه ادمین است")
        if admin_id != SUPER_ADMIN_ID:
            return send(cid, "⛔ فقط سوپرادمین می‌تواند ادمین تعیین کند")
        new = 0 if t.get("is_admin") else 1
        db_execute(
            "UPDATE users SET is_admin=?, admin_type=? WHERE id=?",
            (new, "admin" if new else None, tid),
        )
        send(cid, f"👑 دسترسی ادمین: {'داده شد' if new else 'گرفته شد'}")
        if t.get("bale_user_id"):
            send(t["bale_user_id"],
                 "🎉 شما به‌عنوان ادمین انتخاب شدید!\n\n/start را بزنید."
                 if new else "ℹ️ دسترسی ادمین شما برداشته شد.")
        return show_user_detail(cid, admin_id, tid)

    # --- درخواست حذف (تأیید دومرحله‌ای) ---
    if data.startswith("udq_"):
        tid = _tid("udq_")
        t = get_user_by_id(tid)
        if not t:
            return send(cid, "❌ کاربر یافت نشد")
        nm = f"{t.get('first_name') or ''} {t.get('last_name') or ''}".strip() or "بدون نام"
        return send_or_edit(cid, (
            f"⚠️ حذف دائمی کاربر\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"👤 {nm}\n"
            f"📱 {t.get('mobile') or '-'}\n\n"
            f"❗ این عمل قابل بازگشت نیست!"
        ), {"inline_keyboard": [
            [{"text": "🗑️ بله، حذف کن", "callback_data": f"udy_{tid}"}],
            [{"text": "🔙 انصراف", "callback_data": f"uv_{tid}"}],
        ]})

    # --- حذف نهایی ---
    if data.startswith("udy_"):
        if admin_id != SUPER_ADMIN_ID:
            return send(cid, "⛔ فقط سوپرادمین")
        tid = _tid("udy_")
        t = get_user_by_id(tid)
        if not t:
            return send(cid, "❌ کاربر یافت نشد")
        if t.get("bale_user_id") == SUPER_ADMIN_ID:
            return send(cid, "⛔ سوپرادمین قابل حذف نیست")

        bale_id = t.get("bale_user_id")
        db_execute("DELETE FROM users WHERE id=?", (tid,))
        if bale_id:
            db_execute("DELETE FROM user_states WHERE bale_user_id=?", (bale_id,))
            db_execute("DELETE FROM otp_codes WHERE bale_user_id=?", (bale_id,))
            db_execute("DELETE FROM profile_submissions WHERE bale_user_id=?", (bale_id,))
        # حذف عکس
        if t.get("profile_photo"):
            try:
                Path(t["profile_photo"]).unlink(missing_ok=True)
            except Exception:
                pass
        log_action(admin_id, "delete_user", {"target": tid})
        send(cid, "🗑️ کاربر حذف شد")
        return show_user_list(cid, admin_id, 0)


def start_search(cid, uid):
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_SEARCH, {}, merge=False)
    send(cid, (
        "🔍 جستجوی کاربر\n"
        "━━━━━━━━━━━━━━\n\n"
        "نام، نام خانوادگی، موبایل، کد ملی یا آیدی بله را بفرستید:"
    ), kb_cancel())


def handle_search(message):
    user = message.get("from", {})
    cid = message["chat"]["id"]
    uid = user["id"]
    text = (message.get("text") or "").strip()

    if text == BTN_BACK:
        clear_state(uid)
        return show_admin_panel(cid, uid)

    if len(text) < 2:
        return send(cid, "⚠️ حداقل ۲ کاراکتر وارد کنید")

    q = f"%{normalize_digits(text)}%"
    users = db_execute("""
        SELECT id, first_name, last_name, mobile FROM users
        WHERE first_name LIKE ? OR last_name LIKE ? OR mobile LIKE ?
           OR national_id LIKE ? OR CAST(bale_user_id AS TEXT) LIKE ?
        ORDER BY id DESC LIMIT 20
    """, (q, q, q, q, q), fetch="all")

    clear_state(uid)

    if not users:
        return send(cid, f"❌ نتیجه‌ای برای «{text}» پیدا نشد", {"inline_keyboard": [
            [{"text": "🔍 جستجوی دوباره", "callback_data": "u_search"}],
            [{"text": "🔙 لیست کاربران", "callback_data": "um_list"}],
        ]})

    btns = []
    for u in users:
        nm = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip() or "بدون نام"
        btns.append([{"text": f"👤 {nm} — {u.get('mobile') or '-'}"[:60],
                      "callback_data": f"uv_{u['id']}"}])
    btns.append([{"text": "🔙 لیست کاربران", "callback_data": "um_list"}])

    send(cid, f"🔍 {len(users)} نتیجه پیدا شد:", {"inline_keyboard": btns})


# ==================== PROFILE SUBMISSIONS ====================
def show_pending_subs(cid, uid):
    """نمایش پروفایل‌های در انتظار از کارتابل مرکزی."""
    from shared_workflows import show_inbox
    return show_inbox(cid, uid, kind="profile_review")

# ==================== FORCE JOIN ====================
def show_force_join_settings(cid, uid):
    if not _guard(cid, uid):
        return

    channels = get_all_channels()

    lines = ["🔗 عضویت اجباری", "━━━━━━━━━━━━━━", ""]
    if not channels:
        lines += [
            "📭 هیچ کانال/گروهی تعریف نشده",
            "",
            "💡 کاربران بدون محدودیت وارد ربات می‌شوند.",
            "",
            "📌 می‌توانید کانال عمومی (@username)",
            "یا گروه/کانال خصوصی (آیدی عددی) اضافه کنید.",
        ]
    else:
        active = sum(1 for c in channels if c.get("is_active"))
        lines.append(f"📊 مجموع: {len(channels)} — فعال: {active}")
        lines.append("")
        for ch in channels:
            status = "🟢 فعال" if ch.get("is_active") else "🔴 غیرفعال"
            title = ch.get("channel_title") or "بدون عنوان"
            if ch.get("is_private"):
                lines.append(f"🔒 {title}")
                lines.append(f"├── آیدی: {ch.get('channel_id')}")
            else:
                lines.append(f"📢 {title}")
                lines.append(f"├── یوزرنیم: {ch.get('channel_username')}")
            link = ch.get("invite_link")
            lines.append(f"├── لینک: {link if link else '— (تنظیم نشده)'}")
            lines.append(f"└── وضعیت: {status}")
            lines.append("")

    btns = [[{"text": "➕ افزودن کانال/گروه", "callback_data": "fj_add"}]]
    for ch in channels:
        title = (ch.get("channel_title") or ch.get("channel_username") or str(ch.get("channel_id")))[:18]
        icon = "🔴" if ch.get("is_active") else "🟢"
        btns.append([
            {"text": f"{icon} {title}", "callback_data": f"fj_toggle_{ch['id']}"},
            {"text": "🔗", "callback_data": f"fj_link_{ch['id']}"},
            {"text": "🗑️", "callback_data": f"fj_del_{ch['id']}"},
        ])
    btns.append([{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}])

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def handle_force_join_callback(cid, uid, data):
    if not _guard(cid, uid):
        return

    if data == "fj_add":
        set_state(uid, STATE_ADD_CHANNEL, {}, merge=False)
        return send(cid, (
            "➕ افزودن کانال / گروه\n"
            "━━━━━━━━━━━━━━\n\n"
            "📢 کانال یا گروه عمومی:\n"
            "یوزرنیم را بفرستید\n"
            "مثال: @lifeline_channel\n\n"
            "🔒 کانال یا گروه خصوصی:\n"
            "آیدی عددی را بفرستید\n"
            "مثال: -1001234567890\n\n"
            "⚠️ ربات حتماً باید ادمین آن کانال/گروه باشد،\n"
            "وگرنه نمی‌تواند عضویت را بررسی کند.\n\n"
            "💡 برای گرفتن آیدی گروه خصوصی:\n"
            "ربات را به گروه اضافه کنید و دستور /chatid را در گروه بفرستید."
        ), kb_cancel())

    if data.startswith("fj_toggle_"):
        try:
            ch_id = int(data.replace("fj_toggle_", ""))
        except ValueError:
            return
        new = toggle_force_channel(ch_id)
        if new is not None:
            send(cid, f"✅ وضعیت تغییر کرد: {'فعال' if new else 'غیرفعال'}")
        return show_force_join_settings(cid, uid)

    if data.startswith("fj_del_"):
        try:
            ch_id = int(data.replace("fj_del_", ""))
        except ValueError:
            return
        remove_force_channel(ch_id)
        send(cid, "🗑️ حذف شد")
        return show_force_join_settings(cid, uid)

    if data.startswith("fj_link_"):
        try:
            ch_id = int(data.replace("fj_link_", ""))
        except ValueError:
            return
        set_state(uid, STATE_CH_LINK, {"ch_id": ch_id}, merge=False)
        return send(cid, (
            "🔗 تنظیم لینک عضویت\n"
            "━━━━━━━━━━━━━━\n\n"
            "لینک دعوت این کانال/گروه را بفرستید:\n"
            "مثال: https://ble.ir/join/xxxxx\n\n"
            "💡 برای گروه خصوصی، این لینک به کاربر نمایش داده می‌شود.\n"
            "برای پاک کردن لینک بنویسید: -"
        ), kb_cancel())


def handle_add_channel(message):
    """
    افزودن کانال/گروه.
    ✅ فیکس: خصوصی (آیدی منفی) در ستون channel_id و
    عمومی در channel_username ذخیره می‌شود؛ عنوان واقعی از getChat گرفته می‌شود.
    """
    user = message.get("from", {})
    cid = message["chat"]["id"]
    uid = user["id"]
    text = normalize_digits((message.get("text") or "").strip())

    if text == BTN_BACK:
        clear_state(uid)
        return show_force_join_settings(cid, uid)

    if not text:
        return send(cid, "⚠️ یوزرنیم یا آیدی عددی را بفرستید")

    is_private = False
    identifier = text

    # تشخیص آیدی عددی منفی
    cleaned = text.replace(" ", "")
    if cleaned.startswith("-") and cleaned[1:].isdigit():
        is_private = True
        identifier = cleaned
    else:
        identifier = "@" + cleaned.lstrip("@")
        if len(identifier) < 4:
            return send(cid, (
                "❌ ورودی نامعتبر است.\n\n"
                "📢 عمومی: @channel_name\n"
                "🔒 خصوصی: -1001234567890"
            ))

    # گرفتن عنوان واقعی + بررسی دسترسی ربات
    title = identifier
    warn = ""
    info = get_chat(identifier)
    if info.get("ok"):
        res = info.get("result") or {}
        title = res.get("title") or res.get("username") or identifier
        if res.get("invite_link"):
            pass
    else:
        warn = ("\n\n⚠️ ربات نتوانست به این کانال/گروه دسترسی پیدا کند.\n"
                "مطمئن شوید ربات آنجا ادمین است.")
        title = f"{'گروه خصوصی' if is_private else identifier}"

    row_id = add_force_channel(identifier, title, uid, is_private=is_private)
    clear_state(uid)

    if row_id is None:
        send(cid, "⚠️ این کانال/گروه قبلاً اضافه شده است")
    else:
        msg = "✅ اضافه شد\n\n"
        msg += f"{'🔒 آیدی: ' if is_private else '📢 '}{identifier}\n"
        msg += f"📛 عنوان: {title}"
        if is_private:
            msg += "\n\n💡 برای این گروه خصوصی، حتماً با دکمه 🔗 یک لینک دعوت ثبت کنید."
        msg += warn
        send(cid, msg)

    show_force_join_settings(cid, uid)


def handle_channel_link(message):
    """ثبت لینک دعوت برای کانال"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    if text == BTN_BACK:
        clear_state(uid)
        return show_force_join_settings(cid, uid)

    data = get_state_data(uid)
    ch_id = data.get("ch_id")
    clear_state(uid)

    if not ch_id:
        return send(cid, "⚠️ کانال یافت نشد")

    link = "" if text in ("-", "—") else text
    if link and not link.startswith("http"):
        return send(cid, "❌ لینک باید با http شروع شود")

    set_channel_link(int(ch_id), link)
    send(cid, "✅ لینک ذخیره شد" if link else "🗑️ لینک پاک شد")
    show_force_join_settings(cid, uid)


# ==================== STATS ====================
def show_stats(cid, uid):
    if not _guard(cid, uid):
        return

    total = db_scalar("SELECT COUNT(*) FROM users")
    auth = db_scalar("SELECT COUNT(*) FROM users WHERE is_authenticated=1")
    imported = db_scalar("SELECT COUNT(*) FROM users WHERE imported=1")
    approved = db_scalar("SELECT COUNT(*) FROM users WHERE profile_status='approved'")
    pending_p = db_scalar("SELECT COUNT(*) FROM users WHERE profile_status='pending'")
    pending_s = db_scalar("SELECT COUNT(*) FROM profile_submissions WHERE status='pending'")
    vip = db_scalar("SELECT COUNT(*) FROM users WHERE is_vip=1")
    blocked = db_scalar("SELECT COUNT(*) FROM users WHERE is_blocked=1")
    admins = db_scalar("SELECT COUNT(*) FROM users WHERE is_admin=1")
    today = db_scalar("SELECT COUNT(*) FROM users WHERE date(created_at)=date('now')")
    week = db_scalar("SELECT COUNT(*) FROM users WHERE created_at >= datetime('now','-7 day')")
    active24 = db_scalar("SELECT COUNT(*) FROM users WHERE last_activity_at >= datetime('now','-1 day')")
    avg = db_scalar("SELECT COALESCE(AVG(complete_profile_percent),0) FROM users")

    text = (
        f"📊 آمار سیستم\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"👥 کاربران:\n"
        f"├── کل: {total}\n"
        f"├── احراز شده: {auth}\n"
        f"├── وارد شده از اکسل: {imported}\n"
        f"├── ⭐ VIP: {vip}\n"
        f"├── 👑 ادمین: {admins}\n"
        f"└── 🚫 مسدود: {blocked}\n\n"
        f"📝 پروفایل‌ها:\n"
        f"├── تأیید شده: {approved}\n"
        f"├── در انتظار: {pending_p}\n"
        f"├── درخواست باز: {pending_s}\n"
        f"└── میانگین تکمیل: {float(avg):.0f}%\n\n"
        f"📈 فعالیت:\n"
        f"├── امروز عضو شدند: {today}\n"
        f"├── ۷ روز اخیر: {week}\n"
        f"└── فعال ۲۴ ساعت: {active24}\n\n"
        f"🔗 کانال اجباری فعال: {len(get_active_channels())}"
    )
    send_or_edit(cid, text, kb_admin(uid=uid))


# ==================== DB INFO ====================
def show_dbinfo(cid, uid):
    if not _guard_super(cid, uid):
        return

    tables = db_execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
        fetch="all",
    )
    lines = ["🗄️ اطلاعات دیتابیس", "━━━━━━━━━━━━━━", ""]
    for t in tables:
        name = t["name"]
        cols = len(db_execute(f"PRAGMA table_info({name})", fetch="all") or [])
        recs = db_scalar(f"SELECT COUNT(*) FROM {name}")
        lines.append(f"📋 {name}: {cols} ستون، {recs} رکورد")

    try:
        size = os.path.getsize(DB_PATH) / (1024 * 1024)
        lines += ["", f"💾 حجم فایل: {size:.2f} مگابایت"]
    except OSError:
        pass

    bks = sorted(Path(BACKUP_DIR).glob("nora_backup_*.db")) if Path(BACKUP_DIR).exists() else []
    lines.append(f"🗂️ بک‌آپ‌ها: {len(bks)}")
    send_or_edit(cid, "\n".join(lines), kb_admin(uid=uid))


# ==================== BACKUP ====================
def show_backup_panel(cid, uid):
    """
    💾 فاز ۱۸-د — پنل بک‌آپ

    🎯 «اتوماتیک داره سیو میکنه دیگه؟ بکاپ بگیره و حافظش از بین نره»
    """
    if not _guard_super(cid, uid):
        return
    from database import backup_stats
    from config import (AUTO_BACKUP_HOURS, MAX_BACKUPS,
                        KEEP_DAILY_BACKUPS, DB_PATH)
    from datetime import datetime as _dt

    st = backup_stats()
    try:
        db_kb = os.path.getsize(DB_PATH) // 1024
    except Exception:
        db_kb = 0

    lines = ["💾 بک‌آپ و ایمنی داده‌ها", "━━━━━━━━━━━━━━", ""]
    if AUTO_BACKUP_HOURS > 0:
        lines.append(f"🟢 بک‌آپ خودکار: هر {AUTO_BACKUP_HOURS} ساعت")
    else:
        lines.append("🔴 بک‌آپ خودکار: خاموش")
    lines += [
        f"📅 بک‌آپ روزانه: {st['daily']} روز اخیر "
        f"(نگهداری {KEEP_DAILY_BACKUPS} روز)",
        f"🗂️ بک‌آپ‌های عادی: {st['count']} (سقف {MAX_BACKUPS})",
        f"🗄️ حجم دیتابیس: {db_kb} کیلوبایت",
        "",
    ]
    if st["last"]:
        try:
            ago = int((_dt.now().timestamp() - st["last_ts"]) / 60)
            when = (f"{ago} دقیقه پیش" if ago < 60
                    else f"{ago // 60} ساعت پیش")
        except Exception:
            when = "—"
        lines += [f"🕐 آخرین بک‌آپ: {when}",
                  f"   📁 {st['last']} ({st['size_kb']} KB)", ""]
    else:
        lines += ["⚠️ هنوز بک‌آپی گرفته نشده", ""]

    lines += [
        "━━━━━━━━━━━━━━",
        "🛡️ داده‌های شما با آپدیت از بین نمی‌رود:",
        "   ✅ قبل از هر بار بالا آمدن ربات، بک‌آپ گرفته می‌شود",
        "   ✅ ستون‌های جدید اضافه می‌شوند، چیزی حذف نمی‌شود",
        "   ✅ صحت هر بک‌آپ بررسی می‌شود (فایل خراب ذخیره نمی‌ماند)",
        "",
        "💡 برای تغییر زمان‌بندی، در .env بگذارید:",
        "   AUTO_BACKUP_HOURS=6",
    ]

    btns = [
        [{"text": "💾 بک‌آپ گرفتن و دریافت فایل",
          "callback_data": "admin_backup_now"}],
        [{"text": "📥 دریافت آخرین بک‌آپ",
          "callback_data": "admin_backup_last"}],
        [{"text": "🗄️ اطلاعات دیتابیس", "callback_data": "admin_dbinfo"}],
        [{"text": "🔙 تنظیمات", "callback_data": "admin_settings"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def send_last_backup(cid, uid):
    """📥 ارسال آخرین بک‌آپ موجود بدون گرفتن بک‌آپ جدید"""
    if not _guard_super(cid, uid):
        return
    bks = sorted(Path(BACKUP_DIR).glob("nora_backup_*.db")) \
        if Path(BACKUP_DIR).exists() else []
    if not bks:
        return send(cid, "⚠️ هنوز بک‌آپی وجود ندارد")
    path = str(bks[-1])
    send(cid, f"📥 در حال ارسال {Path(path).name} ...")
    r = send_document(cid, path, "💾 آخرین بک‌آپ دیتابیس")
    if not r.get("ok"):
        send(cid, f"⚠️ ارسال ناموفق — فایل در سرور هست:\n{path}")
    return show_backup_panel(cid, uid)


def do_backup(cid, uid):
    if not _guard_super(cid, uid):
        return

    path = backup_db()
    if not path:
        return send(cid, "❌ بک‌آپ ناموفق بود")

    size = os.path.getsize(path) / 1024
    bks = sorted(Path(BACKUP_DIR).glob("nora_*.db"))
    send(cid, (
        f"💾 بک‌آپ گرفته شد\n\n"
        f"📁 {Path(path).name}\n"
        f"📏 {size:.0f} کیلوبایت\n"
        f"🗂️ مجموع بک‌آپ‌ها: {len(bks)}\n\n"
        f"⏳ در حال ارسال فایل..."
    ))
    r = send_document(cid, path, "💾 بک‌آپ دیتابیس نورا")
    if not r.get("ok"):
        send(cid, f"⚠️ ارسال فایل ناموفق بود، اما بک‌آپ در سرور ذخیره شد:\n{path}", kb_admin(uid=uid))
    else:
        send(cid, "✅ فایل ارسال شد", kb_admin(uid=uid))


# ==================== EXPORT ====================
def export_users(cid, uid):
    """خروجی اکسل از همه کاربران"""
    if not _guard(cid, uid):
        return

    try:
        import openpyxl
    except ImportError:
        return send(cid, "❌ openpyxl نصب نیست:\npy -m pip install openpyxl")

    send(cid, "⏳ در حال ساخت فایل اکسل...")

    rows = db_execute("""
        SELECT id, bale_user_id, first_name, last_name, mobile, national_id,
               birth_date, gender, father_name, mother_name, province, city,
               address, postal_code, email, education_level, field_of_study,
               university, job_title, company_name, profile_status,
               complete_profile_percent, is_vip, is_blocked, is_admin,
               registration_source, created_at
        FROM users ORDER BY id
    """, fetch="all")

    if not rows:
        return send(cid, "📭 کاربری برای خروجی وجود ندارد")

    headers = [
        "ردیف", "آیدی بله", "نام", "نام خانوادگی", "موبایل", "کد ملی",
        "تاریخ تولد", "جنسیت", "نام پدر", "نام مادر", "استان", "شهر",
        "آدرس", "کد پستی", "ایمیل", "مقطع", "رشته", "دانشگاه",
        "شغل", "محل کار", "وضعیت پروفایل", "درصد تکمیل",
        "VIP", "مسدود", "ادمین", "منبع", "تاریخ عضویت",
    ]
    keys = [
        "id", "bale_user_id", "first_name", "last_name", "mobile", "national_id",
        "birth_date", "gender", "father_name", "mother_name", "province", "city",
        "address", "postal_code", "email", "education_level", "field_of_study",
        "university", "job_title", "company_name", "profile_status",
        "complete_profile_percent", "is_vip", "is_blocked", "is_admin",
        "registration_source", "created_at",
    ]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "کاربران"
    ws.sheet_view.rightToLeft = True
    ws.append(headers)

    from openpyxl.styles import Font
    for c in ws[1]:
        c.font = Font(bold=True)

    for r in rows:
        ws.append([r.get(k) if r.get(k) is not None else "" for k in keys])

    for i, h in enumerate(headers, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = max(12, min(28, len(h) + 6))
    ws.freeze_panes = "A2"

    Path(IMPORT_DIR).mkdir(parents=True, exist_ok=True)
    out = Path(IMPORT_DIR) / f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    try:
        wb.save(out)
    except Exception as e:
        return send(cid, f"❌ خطا در ساخت فایل: {user_error_message(e)}")

    r = send_document(cid, str(out), f"📤 خروجی کاربران ({len(rows)} نفر)")
    if not r.get("ok"):
        send(cid, f"⚠️ ارسال ناموفق. فایل در سرور:\n{out}", kb_admin(uid=uid))
    else:
        send(cid, f"✅ {len(rows)} کاربر خروجی گرفته شد", kb_admin(uid=uid))
    log_action(uid, "export_users", {"count": len(rows)})


# ==================== اطلاع‌رسانی همگانی (با فیلتر) ====================
"""
فیکس کامل:
  🐛 قبلاً هیچ فیلتری نبود — فقط «همه کاربران»
  🐛 state با merge اشتباه ذخیره می‌شد و ready گم می‌شد
  ✅ حالا: فیلتر بر اساس نقش، پروفایل، جنسیت، شهر، VIP، رویداد
  ✅ پیش‌نمایش تعداد دقیق قبل از ارسال
  ✅ گزارش زنده + مدیریت کاربرانی که ربات را بلاک کرده‌اند
"""

BC_FILTERS = {
    "all":        {"icon": "👥", "name": "همه کاربران"},
    "everyone":   {"icon": "🌐", "name": "هرکس ربات را استارت زده"},
    "approved":   {"icon": "✅", "name": "فقط پروفایل تأییدشده"},
    "incomplete": {"icon": "📝", "name": "پروفایل ناقص"},
    "vip":        {"icon": "⭐", "name": "فقط اعضای VIP"},
    "male":       {"icon": "👨", "name": "فقط آقایان"},
    "female":     {"icon": "👩", "name": "فقط خانم‌ها"},
    "city":       {"icon": "🏙️", "name": "بر اساس شهر"},
    "event":      {"icon": "🎉", "name": "شرکت‌کنندگان یک رویداد"},
    "active":     {"icon": "🔥", "name": "فعال ۳۰ روز اخیر"},
    "inactive":   {"icon": "😴", "name": "غیرفعال بیش از ۳۰ روز"},
    "admins":     {"icon": "👨‍💼", "name": "فقط ادمین‌ها"},
}

# 🔴 فاز ۱۷ — درخواست کاربر:
#   «هرکسی که از اول ربات رو استارت زده تا الان تو اطلاع‌رسانی
#    همگانی براش پیام بره»
#
# «همه کاربران» = احراز هویت‌شده‌ها (رفتار قبلی، امن‌تر)
# «هرکس استارت زده» = همه، حتی بدون احراز هویت
_BASE_WHERE = ("bale_user_id IS NOT NULL AND is_authenticated=1 "
               "AND COALESCE(is_blocked,0)=0")

_ALL_WHERE = "bale_user_id IS NOT NULL AND COALESCE(is_blocked,0)=0"


def _bc_query(f, value=None):
    """(sql_where, params) بر اساس فیلتر"""
    # 🌐 هرکس ربات را استارت زده — بدون شرط احراز هویت
    if f == "everyone":
        return _ALL_WHERE, []

    w, prm = _BASE_WHERE, []
    if f == "approved":
        w += " AND profile_status='approved'"
    elif f == "incomplete":
        w += " AND COALESCE(profile_status,'draft')!='approved'"
    elif f == "vip":
        w += " AND COALESCE(is_vip,0)=1"
    elif f == "male":
        w += " AND gender='مرد'"
    elif f == "female":
        w += " AND gender='زن'"
    elif f == "admins":
        w += " AND COALESCE(is_admin,0)=1"
    elif f == "active":
        w += " AND last_activity_at >= datetime('now','-30 day')"
    elif f == "inactive":
        w += (" AND (last_activity_at IS NULL "
              "OR last_activity_at < datetime('now','-30 day'))")
    elif f == "city" and value:
        w += " AND city LIKE ?"
        prm.append(f"%{value}%")
    elif f == "event" and value:
        w += (" AND id IN (SELECT user_id FROM event_registrations "
              "WHERE event_id=? AND status IN ('confirmed','attended'))")
        prm.append(int(value))
    return w, prm


def bc_count(f, value=None):
    w, prm = _bc_query(f, value)
    return db_scalar(f"SELECT COUNT(*) FROM users WHERE {w}", tuple(prm))


def bc_targets(f, value=None):
    w, prm = _bc_query(f, value)
    return db_execute(
        f"SELECT bale_user_id, first_name FROM users WHERE {w}",
        tuple(prm), fetch="all") or []


def start_broadcast(cid, uid):
    """گام ۱: انتخاب مخاطبان"""
    if not _guard(cid, uid):
        return
    import permissions as _pm
    if not _pm.require(cid, uid, "bc_send", send):
        return

    total = bc_count("all")
    if total == 0:
        return send(cid, "📭 کاربری برای ارسال وجود ندارد", kb_admin(uid=uid))

    set_state(uid, STATE_BROADCAST, {"stage": "filter"}, merge=False)

    btns = []
    for key, meta in BC_FILTERS.items():
        if key in ("city", "event"):
            continue
        n = bc_count(key)
        btns.append([{"text": f"{meta['icon']} {meta['name']} ({n})",
                      "callback_data": f"bcf_{key}"}])
    btns.append([{"text": "🏙️ بر اساس شهر", "callback_data": "bcf_city"}])

    has_ev = db_execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='events'",
        fetch="one")
    if has_ev and db_scalar("SELECT COUNT(*) FROM events"):
        btns.append([{"text": "🎉 شرکت‌کنندگان یک رویداد",
                      "callback_data": "bcf_event"}])

    btns.append([{"text": "❌ انصراف", "callback_data": "admin_panel"}])

    send_or_edit(cid, (
        f"📢 اطلاع‌رسانی همگانی\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"👥 کل کاربران فعال: {total}\n\n"
        f"🎯 مخاطبان پیام را انتخاب کنید:"
    ), {"inline_keyboard": btns})


def choose_filter(cid, uid, f):
    """گام ۲: تنظیم فیلتر"""
    if not _guard(cid, uid):
        return

    if f == "city":
        set_state(uid, STATE_BROADCAST, {"stage": "city"}, merge=True)
        cities = db_execute(
            f"SELECT city, COUNT(*) n FROM users WHERE {_BASE_WHERE} "
            "AND city IS NOT NULL AND city!='' GROUP BY city ORDER BY n DESC LIMIT 10",
            fetch="all") or []
        txt = "🏙️ نام شهر را بنویسید:\n\n"
        if cities:
            txt += "پرتکرارترین شهرها:\n"
            for c in cities:
                txt += f"• {c['city']} ({c['n']} نفر)\n"
        return send(cid, txt, kb_cancel())

    if f == "event":
        evs = db_execute(
            "SELECT id, title FROM events ORDER BY id DESC LIMIT 10", fetch="all") or []
        if not evs:
            return send(cid, "📭 رویدادی وجود ندارد")
        btns = [[{"text": f"🎉 {e['title']}"[:45],
                  "callback_data": f"bce_{e['id']}"}] for e in evs]
        btns.append([{"text": "🔙 بازگشت", "callback_data": "admin_broadcast"}])
        return send_or_edit(cid, "🎉 کدام رویداد؟", {"inline_keyboard": btns})

    n = bc_count(f)
    if n == 0:
        return send_or_edit(cid, "📭 هیچ کاربری با این فیلتر پیدا نشد", {"inline_keyboard": [
            [{"text": "🔙 انتخاب دوباره", "callback_data": "admin_broadcast"}]]})

    set_state(uid, STATE_BROADCAST,
              {"stage": "compose", "filter": f, "value": None, "count": n}, merge=True)
    meta = BC_FILTERS.get(f, BC_FILTERS["all"])
    send_or_edit(cid, (
        f"📢 نوشتن پیام\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🎯 مخاطب: {meta['icon']} {meta['name']}\n"
        f"👥 تعداد: {n} نفر\n\n"
        f"📝 متن پیام را بنویسید:\n"
        f"(یا عکس با کپشن بفرستید)"
    ))
    send(cid, "⌨️ منتظر پیام شما...", kb_cancel())


def choose_filter_event(cid, uid, eid):
    if not _guard(cid, uid):
        return
    n = bc_count("event", eid)
    ev = db_execute("SELECT title FROM events WHERE id=?", (eid,), fetch="one")
    if n == 0:
        return send_or_edit(cid, "📭 این رویداد شرکت‌کننده تأییدشده ندارد",
                    {"inline_keyboard": [
                        [{"text": "🔙 بازگشت", "callback_data": "admin_broadcast"}]]})
    set_state(uid, STATE_BROADCAST,
              {"stage": "compose", "filter": "event", "value": eid, "count": n},
              merge=True)
    send_or_edit(cid, (
        f"📢 نوشتن پیام\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🎯 مخاطب: شرکت‌کنندگان «{(ev or {}).get('title')}»\n"
        f"👥 تعداد: {n} نفر\n\n"
        f"📝 متن پیام را بنویسید:"
    ))
    send(cid, "⌨️ منتظر پیام شما...", kb_cancel())


def handle_broadcast_text(message):
    """گام ۳: دریافت متن/عکس/شهر"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or message.get("caption") or "").strip()

    if text == BTN_BACK:
        clear_state(uid)
        return show_admin_panel(cid, uid)

    data = get_state_data(uid)
    stage = data.get("stage")

    # مرحله وارد کردن شهر
    if stage == "city":
        if not text:
            return send(cid, "⚠️ نام شهر را بنویسید")
        n = bc_count("city", text)
        if n == 0:
            return send(cid, f"📭 کاربری در «{text}» پیدا نشد\n\nنام دیگری بنویسید:")
        set_state(uid, STATE_BROADCAST,
                  {"stage": "compose", "filter": "city", "value": text, "count": n},
                  merge=True)
        return send(cid, (
            f"✅ شهر: {text}\n"
            f"👥 تعداد: {n} نفر\n\n"
            f"📝 حالا متن پیام را بنویسید:"
        ), kb_cancel())

    # مرحله نوشتن پیام
    photo_id = None
    if "photo" in message:
        photos = message.get("photo") or []
        if photos:
            try:
                best = max(photos, key=lambda x: (x.get("file_size") or 0,
                                                  x.get("width") or 0))
            except (ValueError, TypeError):
                best = photos[-1]
            photo_id = best.get("file_id")

    if not text and not photo_id:
        return send(cid, "⚠️ متن یا عکس بفرستید")

    f = data.get("filter") or "all"
    val = data.get("value")
    n = bc_count(f, val)

    # ✅ فیکس: ready و همه اطلاعات یکجا با merge ذخیره می‌شوند
    set_state(uid, STATE_BROADCAST, {
        "stage": "confirm", "text": text, "photo": photo_id,
        "filter": f, "value": val, "count": n, "ready": 1,
    }, merge=True)

    meta = BC_FILTERS.get(f, BC_FILTERS["all"])
    label = meta["name"]
    if f == "city":
        label = f"شهر {val}"
    elif f == "event":
        ev = db_execute("SELECT title FROM events WHERE id=?", (val,), fetch="one")
        label = f"شرکت‌کنندگان «{(ev or {}).get('title')}»"

    prev = ["👁️ پیش‌نمایش نهایی", "━━━━━━━━━━━━━━", ""]
    if photo_id:
        prev.append("🖼️ (عکس پیوست دارد)")
    if text:
        prev += ["📄 متن:", text[:1200], ""]
    prev += [
        f"🎯 مخاطب: {meta['icon']} {label}",
        f"👥 گیرندگان: {n} نفر",
        f"⏱️ زمان تقریبی: {max(1, n // 20)} ثانیه",
        "",
        "⚠️ ارسال شود؟",
    ]

    send(cid, "\n".join(prev), {"inline_keyboard": [
        [{"text": f"📢 بله، ارسال به {n} نفر", "callback_data": "bc_go"}],
        [{"text": "✏️ ویرایش متن", "callback_data": "bc_edit"}],
        [{"text": "🎯 تغییر مخاطب", "callback_data": "admin_broadcast"}],
        [{"text": "❌ انصراف", "callback_data": "admin_panel"}],
    ]})


def edit_broadcast(cid, uid):
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_BROADCAST, {"stage": "compose", "ready": 0}, merge=True)
    send(cid, "📝 متن جدید را بنویسید:", kb_cancel())


def do_broadcast(cid, uid):
    """گام ۴: ارسال واقعی"""
    if not _guard(cid, uid):
        return
    from config import BROADCAST_RATE
    import time as _t

    data = get_state_data(uid)
    if not data.get("ready"):
        clear_state(uid)
        return send(cid, (
            "⏰ اطلاعات ارسال پیدا نشد.\n\n"
            "💡 دوباره از «📢 اطلاع‌رسانی همگانی» شروع کنید."
        ), kb_admin(uid=uid))

    text = data.get("text") or ""
    photo = data.get("photo")
    f = data.get("filter") or "all"
    val = data.get("value")
    clear_state(uid)

    targets = bc_targets(f, val)
    if not targets:
        return send(cid, "📭 گیرنده‌ای پیدا نشد", kb_admin(uid=uid))

    total = len(targets)
    send(cid, f"⏳ شروع ارسال به {total} نفر...\n\n💡 لطفاً صبر کنید.")

    ok = fail = blocked = 0
    delay = 1.0 / max(1, min(BROADCAST_RATE, 30))
    t0 = _t.time()

    for i, r in enumerate(targets, 1):
        target = r.get("bale_user_id")
        if not target:
            continue
        try:
            if photo:
                res = send_photo(target, photo, text or None)
            else:
                res = send(target, text)
            if res.get("ok"):
                ok += 1
            else:
                d = str(res.get("description", "")).lower()
                if any(k in d for k in ("blocked", "forbidden", "chat not found",
                                        "deactivated")):
                    blocked += 1
                    # کاربری که ربات را بلاک کرده، از ارسال بعدی حذف شود
                    db_execute(
                        "UPDATE users SET is_active=0 WHERE bale_user_id=?", (target,))
                else:
                    fail += 1
        except Exception:
            fail += 1
        _t.sleep(delay)
        if i % 50 == 0:
            send(cid, f"📊 {i}/{total} — ✅{ok} ❌{fail} 🚫{blocked}")

    dur = int(_t.time() - t0)
    log_action(uid, "broadcast",
               {"filter": f, "ok": ok, "fail": fail, "blocked": blocked})

    meta = BC_FILTERS.get(f, BC_FILTERS["all"])
    send(cid, (
        f"✅ اطلاع‌رسانی تمام شد\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🎯 مخاطب: {meta['name']}\n"
        f"👥 کل: {total}\n"
        f"├── ✅ ارسال شد: {ok}\n"
        f"├── 🚫 ربات را بلاک کرده‌اند: {blocked}\n"
        f"└── ❌ خطا: {fail}\n\n"
        f"⏱️ مدت: {dur} ثانیه"
    ), kb_admin(uid=uid))


# ═══════════════════════════════════════════════════════════
# 🔐 نقش و سطح دسترسی ادمین — فاز ۱۲
# ═══════════════════════════════════════════════════════════
import permissions as _perm


def _target_uid(tid):
    """شناسه داخلی → bale_user_id"""
    try:
        r = db_execute("SELECT bale_user_id FROM users WHERE id=?",
                       (int(tid),), fetch="one")
    except (TypeError, ValueError):
        return None
    return (r or {}).get("bale_user_id")


def show_admin_perms(cid, uid, tid):
    """🔐 نمایش نقش و دسترسی‌های یک ادمین"""
    if uid != SUPER_ADMIN_ID:
        return send(cid, "🔒 فقط سوپرادمین می‌تواند دسترسی‌ها را تغییر دهد")
    target = _target_uid(tid)
    if not target:
        return send(cid, "❌ کاربر یافت نشد")

    u = db_execute("SELECT * FROM users WHERE bale_user_id=?", (target,),
                   fetch="one") or {}
    nm = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip() or "—"
    role, perms = _perm.get_admin_role(target)

    lines = [f"🔐 دسترسی‌های {nm}", "━━━━━━━━━━━━━━", "",
             f"🎭 نقش: {_perm.role_label(target)}",
             f"🔑 تعداد دسترسی: {len(perms)}", ""]

    if target == SUPER_ADMIN_ID:
        lines.append("👑 سوپرادمین — همه دسترسی‌ها بدون استثنا")
        return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
            [{"text": "🔙 بازگشت", "callback_data": f"uv_{tid}"}]]})

    if perms:
        by_cat = {}
        for k in perms:
            info = _perm.PERM_MAP.get(k)
            if info:
                by_cat.setdefault(info[3], []).append(f"{info[1]} {info[2]}")
        for c, items in by_cat.items():
            lines.append(f"📂 {c}:")
            for it in items[:6]:
                lines.append(f"   ✅ {it}")
            if len(items) > 6:
                lines.append(f"   … و {len(items)-6} مورد دیگر")
            lines.append("")
    else:
        lines.append("⚠️ هیچ دسترسی‌ای ندارد")

    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🎭 تغییر نقش", "callback_data": f"pm_roles_{tid}"}],
        [{"text": "⚙️ دسترسی‌های تکی", "callback_data": f"pm_cats_{tid}"}],
        [{"text": "🚫 سلب دسترسی ادمین", "callback_data": f"pm_revoke_{tid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"uv_{tid}"}],
    ]})


def show_role_picker(cid, uid, tid):
    """🎭 انتخاب نقش آماده"""
    if uid != SUPER_ADMIN_ID:
        return send(cid, "🔒 فقط سوپرادمین")
    target = _target_uid(tid)
    if not target:
        return send(cid, "❌ کاربر یافت نشد")
    cur, _ = _perm.get_admin_role(target)

    lines = ["🎭 انتخاب نقش", "━━━━━━━━━━━━━━", ""]
    btns = []
    for k, r in _perm.ROLES.items():
        if k == "super_admin":
            continue
        n = len(r["perms"])
        lines.append(f"{r['icon']} {r['name']}")
        lines.append(f"   {r['desc']}"
                     + (f"  ({n} دسترسی)" if k != "custom" else ""))
        lines.append("")
        btns.append([{"text": f"{'🔘' if k == cur else '⚪'} {r['icon']} {r['name']}",
                      "callback_data": f"pm_setr_{k}_{tid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"pm_view_{tid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_admin_role(cid, uid, tid, role):
    """تعیین نقش"""
    if uid != SUPER_ADMIN_ID:
        return send(cid, "🔒 فقط سوپرادمین")
    target = _target_uid(tid)
    if not target:
        return send(cid, "❌ کاربر یافت نشد")
    if target == SUPER_ADMIN_ID:
        return send(cid, "⛔ نقش سوپرادمین قابل تغییر نیست")
    if role not in _perm.ROLES or role == "super_admin":
        return send(cid, "❌ نقش نامعتبر")

    _perm.set_role(target, role, granted_by=uid)
    r = _perm.ROLES[role]
    try:
        import activity_log as _al
        _al.record(uid, "admin_role", {"role": role, "target": target})
    except Exception:
        pass
    send(cid, f"✅ نقش تنظیم شد: {r['icon']} {r['name']}")
    try:
        send(target, (
            f"🔐 سطح دسترسی شما تغییر کرد\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"🎭 نقش جدید: {r['icon']} {r['name']}\n"
            f"📄 {r['desc']}"
        ))
    except Exception:
        pass
    return show_admin_perms(cid, uid, tid)


def show_perm_cats(cid, uid, tid):
    """⚙️ دسته‌های دسترسی"""
    if uid != SUPER_ADMIN_ID:
        return send(cid, "🔒 فقط سوپرادمین")
    target = _target_uid(tid)
    if not target:
        return send(cid, "❌ کاربر یافت نشد")
    _, perms = _perm.get_admin_role(target)

    btns = []
    for c in _perm.PERM_CATS:
        keys = [k for k, _i, _n, cat in _perm.PERMISSIONS if cat == c]
        have = sum(1 for k in keys if k in perms)
        lock = " 🔒" if c == "سیستم" else ""
        btns.append([{"text": f"📂 {c} ({have}/{len(keys)}){lock}",
                      "callback_data": f"pm_cat_{c}_{tid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"pm_view_{tid}"}])
    return send_or_edit(cid, (
        "⚙️ دسترسی‌های تکی\n━━━━━━━━━━━━━━\n\n"
        "یک دسته را باز کنید و دسترسی‌ها را روشن/خاموش کنید.\n\n"
        "🔒 دسترسی‌های سیستمی فقط برای سوپرادمین است."
    ), {"inline_keyboard": btns})


def show_perm_cat(cid, uid, tid, cat):
    """⚙️ دسترسی‌های یک دسته"""
    if uid != SUPER_ADMIN_ID:
        return send(cid, "🔒 فقط سوپرادمین")
    target = _target_uid(tid)
    if not target:
        return send(cid, "❌ کاربر یافت نشد")
    _, perms = _perm.get_admin_role(target)

    items = [(k, i, n) for k, i, n, c in _perm.PERMISSIONS if c == cat]
    if not items:
        return show_perm_cats(cid, uid, tid)

    lines = [f"📂 {cat}", "━━━━━━━━━━━━━━", ""]
    btns = []
    for k, i, n in items:
        if k in _perm.SUPER_ONLY:
            lines.append(f"🔒 {i} {n} — فقط سوپرادمین")
            continue
        on = k in perms
        lines.append(f"{'✅' if on else '⬜'} {i} {n}")
        btns.append([{"text": f"{'✅' if on else '⬜'} {i} {n}",
                      "callback_data": f"pm_tog_{k}_{tid}"}])
    btns.append([{"text": "🔙 دسته‌ها", "callback_data": f"pm_cats_{tid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_admin_perm(cid, uid, tid, key):
    """روشن/خاموش کردن یک دسترسی"""
    if uid != SUPER_ADMIN_ID:
        return send(cid, "🔒 فقط سوپرادمین")
    target = _target_uid(tid)
    if not target:
        return send(cid, "❌ کاربر یافت نشد")
    if target == SUPER_ADMIN_ID:
        return send(cid, "⛔ دسترسی سوپرادمین قابل تغییر نیست")
    if key in _perm.SUPER_ONLY:
        return send(cid, "🔒 این دسترسی فقط برای سوپرادمین است")
    if key not in _perm.PERM_KEYS:
        return send(cid, "❌ دسترسی نامعتبر")

    _perm.toggle_perm(target, key, granted_by=uid)
    info = _perm.PERM_MAP.get(key)
    cat = info[3] if info else _perm.PERM_CATS[0]
    return show_perm_cat(cid, uid, tid, cat)


def revoke_admin_perms(cid, uid, tid):
    """🚫 سلب کامل دسترسی ادمین"""
    if uid != SUPER_ADMIN_ID:
        return send(cid, "🔒 فقط سوپرادمین")
    target = _target_uid(tid)
    if not target:
        return send(cid, "❌ کاربر یافت نشد")
    if target == SUPER_ADMIN_ID:
        return send(cid, "⛔ سوپرادمین قابل سلب نیست")

    _perm.revoke_admin(target)
    try:
        import activity_log as _al
        _al.record(uid, "admin_removed", {"target": target})
    except Exception:
        pass
    send(cid, "🚫 دسترسی ادمین سلب شد")
    try:
        send(target, "🔐 دسترسی ادمین شما لغو شد.")
    except Exception:
        pass
    return show_users_menu(cid, uid)


# ══════════════════════════════════════════════════════════
# ✏️ فاز ۳۸ — ویرایش متن پرسش و افزودن پارامتر دلخواه
#
# 🎯 «قسمت پارامترهای پروفایل بشه متن و رسانه هم بهش سوالات
#     پروفایل اضافه کرد — این مورد هم برای سوالات پیش‌فرض هم
#     برای سوالاتی که از لیست اضافه میکنم»
# ══════════════════════════════════════════════════════════
STATE_PF_TEXT = "pf_edit_text"
STATE_PF_NEW = "pf_new_field"


def show_param_edit(cid, uid, key):
    """🔎 صفحهٔ یک پارامتر — همه‌چیزش یکجا"""
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.require(cid, uid, "sys_settings", send):
        return

    from profile import (FORM_STEPS, LABELS, custom_fields, field_on,
                         field_required, prompt_of, MEDIA_TYPES)

    st = next((x for x in FORM_STEPS if x["key"] == key), None)
    cf = next((c for c in custom_fields() if c.get("key") == key), None)
    if not st and not cf:
        return send(cid, "❌ پارامتر یافت نشد")

    if st:
        nm = LABELS.get(key, key)
        dflt = st["prompt"]
        ftype = st.get("ftype") or "short_text"
        req_d = st["required"]
        is_custom = False
    else:
        nm = f"{cf.get('icon', '▫️')} {cf.get('name') or key}"
        dflt = cf.get("prompt") or f"{nm}:"
        ftype = cf.get("ftype") or "short_text"
        req_d = bool(cf.get("required"))
        is_custom = True

    on = True if key == "full_name" else field_on(key)
    req = True if key == "full_name" else field_required(key, req_d)
    cur = prompt_of(key, dflt)
    custom_txt = cur != dflt

    kind = "📝 متنی"
    if ftype in MEDIA_TYPES:
        ic, tn, _ = MEDIA_TYPES[ftype]
        kind = f"{ic} {tn}"

    lines = [f"⚙️ {nm}", "━━━━━━━━━━━━━━", "",
             f"🧩 نوع: {kind}",
             f"{'🟢 فعال' if on else '⚪ غیرفعال'}"
             f"   ·   {'⭐ اجباری' if req else '○ اختیاری'}", "",
             "💬 متن پرسش:", f"   {cur}", ""]
    if custom_txt:
        lines += ["✏️ این متن را خودتان تغییر داده‌اید", ""]
    if key == "full_name":
        lines += ["🔒 این فیلد همیشه فعال و اجباری است.", ""]

    btns = []
    if key != "full_name":
        btns.append([
            {"text": "🟢 فعال" if on else "⚪ غیرفعال",
             "callback_data": f"pfo_{key}"},
            {"text": "⭐ اجباری" if req else "○ اختیاری",
             "callback_data": f"pfr_{key}"},
        ])
    btns.append([{"text": "✏️ تغییر متن پرسش",
                  "callback_data": f"pfq_{key}"}])
    if custom_txt:
        btns.append([{"text": "♻️ بازگشت به متن پیش‌فرض",
                      "callback_data": f"pfqr_{key}"}])
    if is_custom:
        btns.append([{"text": "🗑️ حذف این پارامتر",
                      "callback_data": f"pfdel_{key}"}])
    btns.append([{"text": "🔙 پارامترها",
                  "callback_data": "admin_profile_params"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_param_text(cid, uid, key):
    """✏️ گرفتن متن تازهٔ پرسش"""
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.require(cid, uid, "sys_settings", send):
        return
    from profile import (FORM_STEPS, custom_fields, prompt_of,
                         MEDIA_TYPES)
    st = next((x for x in FORM_STEPS if x["key"] == key), None)
    cf = next((c for c in custom_fields() if c.get("key") == key), None)
    if not st and not cf:
        return send(cid, "❌ پارامتر یافت نشد")
    dflt = (st or {}).get("prompt") or (cf or {}).get("prompt") or ""
    ftype = (st or cf or {}).get("ftype") or "short_text"

    set_state(uid, STATE_PF_TEXT, {"key": key}, merge=False)
    tip = ("💡 مثال: 📸 یک عکس واضح از خودتان بفرستید:"
           if ftype in MEDIA_TYPES
           else "💡 مثال: 📧 ایمیلتان را بنویسید:")
    send(cid, (
        "✏️ متن پرسش\n"
        "━━━━━━━━━━━━━━\n\n"
        f"📄 متن فعلی:\n   {prompt_of(key, dflt)}\n\n"
        f"{tip}\n\n"
        "متن تازه را بنویسید:\n\n"
        "♻️ برای بازگشت به پیش‌فرض «-» بفرستید."
    ), kb_cancel())


def _forget_setting(key):
    """
    🗑️ حذف کامل یک تنظیم — از جدول **و** از کش.

    🔴 باگ رفع‌شده (فاز ۳۸): `get_setting` یک کش درون‌حافظه‌ای
       دارد. حذف مستقیم با DELETE کش را دست نمی‌زند، پس مقدار
       قدیمی تا ریستارت بعدی برمی‌گشت — کاربر می‌زد «بازگشت به
       پیش‌فرض» و هیچ اتفاقی نمی‌افتاد.
    """
    from database import db_execute as _dx, _settings_cache
    _dx("DELETE FROM settings WHERE key=?", (key,))
    _settings_cache.pop(key, None)


def reset_param_text(cid, uid, key):
    """♻️ متن پرسش به پیش‌فرض"""
    if not _guard(cid, uid):
        return
    _forget_setting(f"pf_{key}_q")
    send(cid, "♻️ متن پرسش به حالت پیش‌فرض برگشت")
    return show_param_edit(cid, uid, key)


def start_new_param(cid, uid, kind="text"):
    """
    ➕ افزودن پرسش دلخواه — متنی یا رسانه‌ای

    🎯 «بشه متن و رسانه هم بهش سوالات پروفایل اضافه کرد»
    """
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.require(cid, uid, "sys_settings", send):
        return

    if kind == "media":
        from profile import MEDIA_TYPES
        lines = ["🖼️ افزودن پرسش رسانه‌ای", "━━━━━━━━━━━━━━", "",
                 "چه نوع فایلی از کاربر خواسته شود؟", ""]
        btns = []
        for k, (ic, nm, _) in MEDIA_TYPES.items():
            lines.append(f"{ic} {nm}")
            btns.append([{"text": f"{ic} {nm}",
                          "callback_data": f"pfnm_{k}"}])
        btns.append([{"text": "🔙 پارامترها",
                      "callback_data": "admin_profile_params"}])
        return send_or_edit(cid, "\n".join(lines),
                            {"inline_keyboard": btns})

    set_state(uid, STATE_PF_NEW, {"ftype": "short_text"}, merge=False)
    send(cid, (
        "📝 افزودن پرسش متنی\n"
        "━━━━━━━━━━━━━━\n\n"
        "نام این پرسش را بنویسید:\n\n"
        "مثال: کد پرسنلی\n"
        "مثال: نام سازمان معرف\n\n"
        "💡 بعد می‌توانید متن کامل سؤال، اجباری‌بودن و\n"
        "   روشن/خاموش بودنش را تنظیم کنید."
    ), kb_cancel())


def start_new_media(cid, uid, mtype):
    """🖼️ نوع رسانه انتخاب شد — حالا نامش"""
    if not _guard(cid, uid):
        return
    from profile import MEDIA_TYPES
    if mtype not in MEDIA_TYPES:
        return send(cid, "❌ نوع نامعتبر")
    ic, nm, _ = MEDIA_TYPES[mtype]
    set_state(uid, STATE_PF_NEW, {"ftype": mtype}, merge=False)
    send(cid, (
        f"{ic} افزودن پرسش {nm}\n"
        "━━━━━━━━━━━━━━\n\n"
        "نام این پرسش را بنویسید:\n\n"
        f"مثال: {'کارت ملی' if mtype == 'photo' else 'رزومه'}\n"
        f"مثال: {'عکس پرسنلی' if mtype == 'photo' else 'مدرک تحصیلی'}\n\n"
        f"💡 کاربر باید یک {nm} بفرستد."
    ), kb_cancel())


def handle_param_text(message):
    """📝 ورودی متنی پنل پارامترها"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    txt = (message.get("text") or "").strip()
    st = get_state_name(uid)
    if st not in (STATE_PF_TEXT, STATE_PF_NEW):
        return False

    if txt in (BTN_BACK, "❌ انصراف", "انصراف", "/cancel"):
        clear_state(uid)
        send(cid, "✅ لغو شد", kb_remove())
        show_profile_params(cid, uid)
        return True

    data = get_state_data(uid) or {}

    # ── ویرایش متن یک پرسش ──
    if st == STATE_PF_TEXT:
        key = data.get("key")
        from profile import set_prompt
        if txt == "-":
            _forget_setting(f"pf_{key}_q")
            clear_state(uid)
            send(cid, "♻️ به متن پیش‌فرض برگشت", kb_remove())
        else:
            if len(txt) < 3:
                send(cid, "⚠️ متن خیلی کوتاه است — دست‌کم ۳ حرف")
                return True
            set_prompt(key, txt, uid)
            clear_state(uid)
            send(cid, "✅ متن پرسش ثبت شد", kb_remove())
        log_action(uid, "profile_param_text", {"key": key})
        show_param_edit(cid, uid, key)
        return True

    # ── افزودن پرسش تازه ──
    if st == STATE_PF_NEW:
        if len(txt) < 2:
            send(cid, "⚠️ نام خیلی کوتاه است")
            return True
        from profile import (custom_fields, save_custom_fields,
                             FORM_STEPS, MEDIA_TYPES)
        from database import set_setting as _ss
        import re as _re

        ftype = data.get("ftype") or "short_text"
        # 🔑 کلید یکتا از روی نام
        base = _re.sub(r"[^a-z0-9]+", "_",
                       txt.lower().strip())[:20].strip("_")
        if not base or not _re.match(r"^[a-z]", base):
            base = "field"
        items = custom_fields()
        taken = {c.get("key") for c in items} | \
                {x["key"] for x in FORM_STEPS}
        key = base
        i = 2
        while key in taken:
            key = f"{base}{i}"
            i += 1

        icon = "▫️"
        if ftype in MEDIA_TYPES:
            icon = MEDIA_TYPES[ftype][0]

        items.append({
            "key": key,
            "name": txt[:40],
            "icon": icon,
            "ftype": ftype,
            "prompt": f"{icon} {txt[:40]}:",
            "required": False,
        })
        save_custom_fields(items)
        _ss(f"pf_{key}_on", "1", "پارامتر سفارشی", "profile", uid)
        clear_state(uid)
        log_action(uid, "profile_param_added", {"key": key})
        send(cid, f"✅ «{icon} {txt[:40]}» اضافه شد", kb_remove())
        show_param_edit(cid, uid, key)
        return True

    return False
