"""
🔐 نقش‌ها و سطوح دسترسی ادمین — فاز ۱۲

طبق فایل معماری (خط ۴۶۷۹۵): ۶ نقش آماده + دسترسی سفارشی

  🔴 ادمین کامل      همه‌چیز به‌جز مدیریت ادمین و تنظیمات سیستم
  🟠 ادمین رویدادها   فقط رویداد + حضور و غیاب
  🟡 ادمین فرم‌ساز    فقط فرم و پاسخ‌ها
  🟢 گزارش‌گیر        فقط مشاهده
  🔵 اطلاع‌رسانی      فقط ارسال پیام
  ⚪ سفارشی          دسترسی‌های دلخواه

سوپرادمین همیشه همه دسترسی‌ها را دارد.
"""
import json

from config import SUPER_ADMIN_ID
from database import db_execute, db_scalar, log


# ==================== کاتالوگ دسترسی‌ها ====================
# (کلید، آیکون، نام فارسی، دسته)
PERMISSIONS = [
    # 🎉 رویدادها
    ("ev_create",   "➕", "ایجاد رویداد",              "رویدادها"),
    ("ev_edit",     "✏️", "ویرایش رویداد",             "رویدادها"),
    ("ev_view_all", "👁️", "مشاهده رویدادهای دیگران",   "رویدادها"),
    ("ev_delete",   "🗑️", "حذف رویداد",                "رویدادها"),
    ("ev_cancel",   "⛔", "لغو رویداد",                "رویدادها"),
    ("ev_publish",  "📢", "انتشار رویداد",             "رویدادها"),
    ("attendance",  "✋", "حضور و غیاب",               "رویدادها"),
    ("certificate", "🎓", "صدور گواهینامه",                "رویدادها"),

    # 📝 فرم‌ساز
    ("fm_create",   "➕", "ایجاد فرم",                 "فرم‌ساز"),
    ("fm_edit",     "✏️", "ویرایش فرم",                "فرم‌ساز"),
    ("fm_responses", "📊", "مشاهده پاسخ‌ها",           "فرم‌ساز"),
    ("fm_export",   "📤", "خروجی گرفتن",               "فرم‌ساز"),
    ("fm_delete",   "🗑️", "حذف فرم",                   "فرم‌ساز"),

    # 👥 کاربران
    ("us_view",     "📋", "مشاهده لیست کاربران",       "کاربران"),
    ("us_edit",     "✏️", "ویرایش اطلاعات کاربر",      "کاربران"),
    ("us_approve",  "✅", "تأیید پروفایل",             "کاربران"),
    ("us_block",    "🚫", "مسدود کردن",                "کاربران"),
    ("us_delete",   "🗑️", "حذف کاربر",                 "کاربران"),
    ("us_vip",      "⭐", "مدیریت VIP",                "کاربران"),
    ("us_import",   "📥", "ورود گروهی از اکسل",        "کاربران"),
    ("us_export",   "📤", "خروجی لیست کاربران",        "کاربران"),

    # 💰 مالی
    # 🔴 فاز ۱۳: «مشاهده مالی» و «خروجی مالی» فقط سوپرادمین
    #    (درخواست صریح: جز سوپرادمین کسی به درآمد کل ربات دسترسی نداشته باشد)
    ("fin_view",    "👁️", "مشاهده مالی و درآمد کل",    "مالی"),
    ("fin_approve", "✅", "تأیید رسید پرداخت",         "مالی"),
    ("fin_refund",  "💸", "بازپرداخت",                 "مالی"),
    ("fin_export",  "📤", "خروجی مالی",                "مالی"),
    ("fin_settings", "⚙️", "تنظیمات درگاه و کارت",     "مالی"),

    # 📢 اطلاع‌رسانی
    ("bc_send",     "📢", "ارسال همگانی",              "اطلاع‌رسانی"),
    ("bc_event",    "🎉", "اطلاع‌رسانی رویداد",        "اطلاع‌رسانی"),
    ("occasions",   "🎂", "مناسبت‌ها و تبریک",         "اطلاع‌رسانی"),

    # 📱 پشتیبانی
    ("tk_manage",   "📱", "مدیریت تیکت‌ها",            "پشتیبانی"),
    ("club_manage", "🏅", "مدیریت باشگاه و پاداش",     "پشتیبانی"),

    # 📊 گزارش
    ("rp_view",     "📊", "مشاهده گزارش‌ها",           "گزارش"),
    ("rp_export",   "📤", "خروجی گزارش",               "گزارش"),
    ("rp_logs",     "📋", "مشاهده لاگ فعالیت",         "گزارش"),

    # ⚙️ سیستم (فقط سوپرادمین)
    ("sys_admins",  "👨‍💼", "مدیریت ادمین‌ها",          "سیستم"),
    ("sys_settings", "⚙️", "تنظیمات سیستم",            "سیستم"),
    ("sys_backup",  "💾", "بک‌آپ و دیتابیس",           "سیستم"),
    ("sys_points",  "🏅", "تنظیم قوانین امتیاز",       "سیستم"),
]

PERM_KEYS = [p[0] for p in PERMISSIONS]
PERM_MAP = {p[0]: p for p in PERMISSIONS}

PERM_CATS = []
for _p in PERMISSIONS:
    if _p[3] not in PERM_CATS:
        PERM_CATS.append(_p[3])

# دسترسی‌هایی که فقط سوپرادمین دارد
#
# 🔴 فاز ۱۳ — درخواست صریح کاربر:
#    «جز سوپر ادمین کسی دسترسی به مالی و درآمد کل ربات نداشته باشد»
#
#    پس fin_view (داشبورد درآمد + لیست تراکنش‌ها) و fin_export
#    (خروجی Excel مالی) و fin_settings (کارت/درگاه) قفل سوپرادمین شدند.
#
#    ⚠️ fin_approve و fin_refund عمداً بیرون ماندند: این‌ها «عملیات»
#       روی یک رسید مشخص‌اند نه دیدن درآمد کل، و ادمین رسیدها
#       باید بتواند کار روزمره را انجام دهد.
SUPER_ONLY = {
    "sys_admins", "sys_settings", "sys_backup", "sys_points",
    "fin_view", "fin_export", "fin_settings",
}


# ==================== نقش‌های آماده ====================
def _all_except(*excluded):
    return [k for k in PERM_KEYS if k not in set(excluded) | SUPER_ONLY]


ROLES = {
    "super_admin": {
        "icon": "👑", "name": "سوپرادمین",
        "desc": "همه دسترسی‌ها بدون استثنا",
        "perms": list(PERM_KEYS),
    },
    "full_admin": {
        "icon": "🔴", "name": "ادمین کامل",
        "desc": "همه دسترسی‌ها به‌جز مدیریت ادمین‌ها و تنظیمات سیستم",
        "perms": _all_except(),
    },
    "event_admin": {
        "icon": "🟠", "name": "ادمین رویدادها",
        "desc": "فقط رویدادها + حضور و غیاب",
        "perms": ["ev_create", "ev_edit", "ev_view_all", "ev_publish",
                  "ev_cancel", "attendance", "certificate", "bc_event",
                  "us_view", "rp_view"],
    },
    "form_admin": {
        "icon": "🟡", "name": "ادمین فرم‌ساز",
        "desc": "فقط فرم‌ها + پاسخ‌ها",
        "perms": ["fm_create", "fm_edit", "fm_responses", "fm_export",
                  "us_view", "rp_view"],
    },
    "report_admin": {
        "icon": "🟢", "name": "ادمین گزارش‌گیر",
        "desc": "فقط مشاهده گزارش‌ها (بدون مالی، بدون تغییر)",
        "perms": ["rp_view", "rp_export", "rp_logs", "us_view",
                  "fm_responses"],
    },
    "broadcast_admin": {
        "icon": "🔵", "name": "ادمین اطلاع‌رسانی",
        "desc": "فقط ارسال پیام‌ها",
        "perms": ["bc_send", "bc_event", "occasions", "us_view", "tk_manage"],
    },
    "finance_admin": {
        "icon": "💰", "name": "ادمین رسیدها",
        "desc": "تأیید رسید و بازپرداخت — بدون دیدن درآمد کل",
        "perms": ["fin_approve", "fin_refund", "us_view", "rp_view"],
    },
    "custom": {
        "icon": "⚪", "name": "سفارشی",
        "desc": "دسترسی‌های دلخواه — خودتان انتخاب کنید",
        "perms": [],
    },
}


# ==================== دیتابیس ====================
ADMIN_PERMS_SCHEMA = {
    "bale_user_id": "INTEGER NOT NULL",
    "role": "TEXT DEFAULT 'custom'",
    "perms": "TEXT",
    "note": "TEXT",
    "granted_by": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}


def init_permission_tables():
    from database import ensure_table
    ensure_table("admin_permissions", ADMIN_PERMS_SCHEMA)
    db_execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_admperm "
               "ON admin_permissions(bale_user_id)")
    log("✅ جدول دسترسی ادمین آماده شد")


# ==================== هسته بررسی دسترسی ====================
_cache = {}


def clear_cache(uid=None):
    if uid is None:
        _cache.clear()
    else:
        _cache.pop(uid, None)


def get_admin_role(uid):
    """نقش ادمین — خروجی: (role_key, perms_list)"""
    if uid == SUPER_ADMIN_ID:
        return "super_admin", list(PERM_KEYS)

    if uid in _cache:
        return _cache[uid]

    row = db_execute("SELECT role, perms FROM admin_permissions "
                     "WHERE bale_user_id=?", (uid,), fetch="one")
    if not row:
        # ادمین قدیمی بدون رکورد → ادمین کامل (سازگاری با نسخه قبل)
        u = db_execute("SELECT is_admin FROM users WHERE bale_user_id=?",
                       (uid,), fetch="one")
        if u and u.get("is_admin"):
            res = ("full_admin", list(ROLES["full_admin"]["perms"]))
        else:
            res = (None, [])
        _cache[uid] = res
        return res

    role = row.get("role") or "custom"
    if role == "custom":
        try:
            perms = json.loads(row.get("perms") or "[]")
            perms = [p for p in perms if p in PERM_KEYS]
        except (ValueError, TypeError):
            perms = []
    else:
        perms = list(ROLES.get(role, {}).get("perms") or [])

    res = (role, perms)
    _cache[uid] = res
    return res


def has_perm(uid, perm):
    """
    آیا این ادمین دسترسی مشخصی دارد؟

    ⚠️ سوپرادمین همیشه True.
       دسترسی‌های سیستمی فقط برای سوپرادمین.
    """
    if uid == SUPER_ADMIN_ID:
        return True
    if perm in SUPER_ONLY:
        return False
    _, perms = get_admin_role(uid)
    return perm in perms


def require(cid, uid, perm, send_fn=None):
    """
    گارد دسترسی — اگر نداشت پیام می‌دهد و False برمی‌گرداند.
    """
    if has_perm(uid, perm):
        return True
    if send_fn:
        info = PERM_MAP.get(perm)
        nm = f"{info[1]} {info[2]}" if info else perm
        send_fn(cid, (
            "🔒 دسترسی کافی ندارید\n"
            "━━━━━━━━━━━━━━\n\n"
            f"این بخش نیاز به دسترسی «{nm}» دارد.\n\n"
            "💡 از سوپرادمین بخواهید دسترسی بدهد."
        ))
    return False


def set_role(uid, role, granted_by=None, perms=None, note=None):
    """تعیین نقش ادمین"""
    if role not in ROLES:
        return False
    plist = perms if role == "custom" else ROLES[role]["perms"]
    plist = [p for p in (plist or []) if p in PERM_KEYS]

    exists = db_execute("SELECT id FROM admin_permissions WHERE bale_user_id=?",
                        (uid,), fetch="one")
    payload = json.dumps(plist, ensure_ascii=False)
    if exists:
        db_execute("""UPDATE admin_permissions SET role=?, perms=?, note=?,
            granted_by=?, updated_at=CURRENT_TIMESTAMP WHERE bale_user_id=?""",
            (role, payload, note, granted_by, uid))
    else:
        db_execute("""INSERT INTO admin_permissions
            (bale_user_id, role, perms, note, granted_by)
            VALUES (?,?,?,?,?)""", (uid, role, payload, note, granted_by))

    db_execute("UPDATE users SET is_admin=1, admin_type=? WHERE bale_user_id=?",
               (role, uid))
    clear_cache(uid)
    return True


def toggle_perm(uid, perm, granted_by=None):
    """روشن/خاموش کردن یک دسترسی (نقش خودکار custom می‌شود)"""
    if perm not in PERM_KEYS or perm in SUPER_ONLY:
        return False
    role, perms = get_admin_role(uid)
    perms = list(perms)
    if perm in perms:
        perms.remove(perm)
    else:
        perms.append(perm)
    return set_role(uid, "custom", granted_by, perms)


def revoke_admin(uid):
    """سلب کامل دسترسی ادمین"""
    if uid == SUPER_ADMIN_ID:
        return False
    db_execute("DELETE FROM admin_permissions WHERE bale_user_id=?", (uid,))
    db_execute("UPDATE users SET is_admin=0, admin_type=NULL "
               "WHERE bale_user_id=?", (uid,))
    clear_cache(uid)
    return True


def role_label(uid):
    """برچسب نمایشی نقش"""
    role, perms = get_admin_role(uid)
    if not role:
        return "کاربر عادی"
    r = ROLES.get(role, {})
    if role == "custom":
        return f"⚪ سفارشی ({len(perms)} دسترسی)"
    return f"{r.get('icon', '')} {r.get('name', role)}"


def perms_by_cat(perms):
    """گروه‌بندی دسترسی‌ها بر اساس دسته — برای نمایش"""
    out = {}
    for key, icon, name, cat in PERMISSIONS:
        out.setdefault(cat, []).append((key, icon, name, key in perms))
    return out


# ==================== فاز ۱۳: کمکی منو ====================
def is_super(uid):
    """آیا سوپرادمین است؟"""
    return uid == SUPER_ADMIN_ID


def is_full_admin(uid):
    """
    آیا «ادمین کامل» یا سوپرادمین است؟

    🔴 درخواست کاربر (فاز ۱۳):
       «کلاً منوی کاربر معمولی به سوپر ادمین و ادمین کامل نشان نده»
       این تابع تعیین می‌کند چه کسی منوی پایینِ ادمینی بگیرد.
    """
    if uid == SUPER_ADMIN_ID:
        return True
    role, _ = get_admin_role(uid)
    return role in ("super_admin", "full_admin")


def has_any(uid, *perms):
    """آیا حداقل یکی از این دسترسی‌ها را دارد؟"""
    return any(has_perm(uid, p) for p in perms)


# کدام بخش پنل ادمین با کدام دسترسی‌ها باز می‌شود
SECTION_PERMS = {
    "events":   ("ev_create", "ev_edit", "ev_view_all", "ev_publish",
                 "ev_cancel", "ev_delete", "attendance", "certificate"),
    "forms":    ("fm_create", "fm_edit", "fm_responses", "fm_export",
                 "fm_delete"),
    "users":    ("us_view", "us_edit", "us_approve", "us_block",
                 "us_delete", "us_vip", "us_import", "us_export"),
    "notify":   ("bc_send", "bc_event", "occasions"),
    "care":     ("tk_manage", "club_manage"),
    "reports":  ("rp_view", "rp_export", "rp_logs"),
    "settings": ("sys_settings", "sys_backup", "sys_points",
                 "fin_view", "fin_settings"),
}


def can_section(uid, section):
    """آیا این ادمین بخشی از پنل را می‌بیند؟"""
    return has_any(uid, *SECTION_PERMS.get(section, ()))
