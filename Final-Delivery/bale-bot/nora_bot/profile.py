"""
پروفایل کاربر - فرم چند مرحله‌ای + پیش‌نمایش + عکس - نسخه 4.1 (فیکس شده)

🐛 باگ ۱ (پیش‌نمایش خالی) — رفع شد:
   ریشه: ask_step با set_state(uid,"form_filling",{'step':n}) کل data را جایگزین می‌کرد.
   حالا از update_state_data استفاده می‌شود که merge می‌کند.

🐛 باگ ۲ (ارسال خالی به ادمین) — رفع شد:
   همان ریشه + submit_profile حالا داده را از state می‌خواند و
   اگر خالی بود، خطای واضح می‌دهد به جای ارسال پیام خالی.

فیکس‌های اضافه:
- دکمه «بازگشت» داخل فرم به مرحله قبل برمی‌گردد (نه خروج کامل)
- مقادیر قبلی پروفایل به‌عنوان پیش‌فرض در فرم بارگذاری می‌شوند
- اعتبارسنجی تاریخ تولد و کد ملی
- ارسال به همه ادمین‌ها (نه فقط سوپرادمین)
- رد کردن با دلیل
- import دایره‌ای main حذف شد
"""
import io
import json
import os
import time
from datetime import datetime
from pathlib import Path

from config import SUPER_ADMIN_ID, PROFILES_DIR
from database import db_execute, get_setting, log
from auth import (
    get_user, get_user_by_id, set_state, get_state, get_state_name,
    get_state_data, update_state_data, clear_state,
    update_percent, split_full_name, log_action,
    normalize_digits, validate_national_id, validate_email, validate_birth_date,
)
from bale_api import (
    send, send_or_edit, send_photo, get_file_info, download_file,
    kb_cancel, kb_skip, kb_gender, kb_education,
    kb_remove, kb_profile, BTN_BACK, BTN_SKIP,
)
import jalali as _jd

STATE_FORM = "form_filling"
STATE_PREVIEW = "form_preview"
STATE_PHOTO = "waiting_photo"
STATE_REJECT = "reject_reason"


# ==================== FORM DEFINITION ====================
FORM_STEPS = [
    {"key": "full_name",        "prompt": "📝 نام و نام خانوادگی:\n\nمثال: علی محمدی",  "required": True},
    {"key": "national_id",      "prompt": "🆔 کد ملی (۱۰ رقم):",                        "required": True},
    {"key": "birth_date",       "prompt": "📅 تاریخ تولد (شمسی):\n\nمثال: 1370/01/15",  "required": True},
    {"key": "gender",           "prompt": "👤 جنسیت:",              "kb": "gender",     "required": False},
    {"key": "father_name",      "prompt": "👨 نام پدر:",                                "required": False},
    {"key": "mother_name",      "prompt": "👩 نام مادر:",                               "required": False},
    {"key": "province",         "prompt": "🗺️ استان:",                                  "required": True},
    {"key": "city",             "prompt": "🏙️ شهر:",                                    "required": True},
    {"key": "address",          "prompt": "🏠 آدرس دقیق:",                              "required": False},
    {"key": "postal_code",      "prompt": "📮 کد پستی (۱۰ رقم):",                       "required": False},
    {"key": "education_level",  "prompt": "🎓 مقطع تحصیلی:",        "kb": "education",  "required": False},
    {"key": "field_of_study",   "prompt": "📚 رشته تحصیلی:",                            "required": False},
    {"key": "university",       "prompt": "🏫 دانشگاه / مدرسه:",                        "required": False},
    {"key": "job_title",        "prompt": "💼 شغل:",                                    "required": False},
    {"key": "company_name",     "prompt": "🏢 محل کار / سازمان:",                       "required": False},
    {"key": "email",            "prompt": "📧 ایمیل:\n\nمثال: name@example.com",        "required": False},
    {"key": "bio",              "prompt": "📝 معرفی کوتاه (بیو):",                      "required": False},
    # 📸 فاز ۳۸ — عکس پروفایل حالا یک «مرحلهٔ رسانه‌ای» است
    #
    # 🎯 «افزودن عکس تو منو پروفایل من بره زیرمجموعهٔ تکمیل
    #     پروفایل و تنظیمات و کنترلش بره تو قسمت مربوطه تو
    #     مدیریت کاربران»
    #
    # پیش‌تر عکس یک دکمهٔ جدا در منو بود و ادمین هیچ کنترلی
    # رویش نداشت — نه می‌شد خاموشش کرد، نه اجباری‌اش کرد، نه
    # متنش را عوض کرد. حالا مثل بقیهٔ پارامترهاست.
    {"key": "profile_photo",    "prompt": "📸 عکس پروفایل:",
     "required": False, "ftype": "photo"},
]

# ══════════════════════════════════════════════════════════
# ⚙️ فاز ۱۷-ج — پارامترهای پروفایل قابل تنظیم توسط ادمین
#
# درخواست: «تعیین پارامترهای پروفایل کاربران و تنظیم جزئیات»
#
# ادمین می‌تواند هر فیلد را:
#   • روشن/خاموش کند (اصلاً پرسیده نشود)
#   • اجباری/اختیاری کند
# تنظیمات در settings با کلید pf_<key>_on و pf_<key>_req ذخیره می‌شود.
# ══════════════════════════════════════════════════════════
def _required_label():
    """متن فارسی فیلدهای اجباری — برای نمایش در راهنما"""
    names = []
    for st in active_steps():
        if not st.get("required"):
            continue
        k = st["key"]
        nm = LABELS.get(k, k)
        for ch in "👤🆔📅🗺️🏙️🏠📮🎓📚🏫💼🏢📧📝👨👩":
            nm = nm.replace(ch, "")
        names.append(nm.strip())
    return "، ".join(names) if names else "—"


def field_on(key):
    """آیا این فیلد در فرم پروفایل پرسیده شود؟"""
    from database import get_setting as _gs
    return _gs(f"pf_{key}_on", "1") == "1"


def field_required(key, fallback=False):
    """آیا این فیلد اجباری است؟"""
    from database import get_setting as _gs
    v = _gs(f"pf_{key}_req", "")
    if v == "":
        return fallback
    return v == "1"


# ══════════════════════════════════════════════════════════
# ➕ فاز ۱۸-الف — پارامترهای سفارشی پروفایل
#
# 🎯 «قسمت پارامتر های پروفایل در قسمت مدیریت کاربران، اضافه کردن
#     پارامتر هم بزار — از پارامتر های فرم ساز هم میتونی استفاده کنی»
#
# ادمین می‌تواند از کاتالوگ ۸۱ فیلد فرم‌ساز، فیلد جدیدی به پروفایل
# اضافه کند. مقدارش در جدول user_extra ذخیره می‌شود (نه ستون جدید،
# تا schema کاربران شلوغ و شکننده نشود).
# ══════════════════════════════════════════════════════════
EXTRA_SCHEMA = {
    "bale_user_id": "INTEGER",
    "field_key": "TEXT",
    "value": "TEXT",
    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}


def init_profile_extra():
    from database import ensure_table
    ensure_table("user_extra", EXTRA_SCHEMA)
    try:
        from database import db_execute as _dx
        _dx("CREATE UNIQUE INDEX IF NOT EXISTS uq_user_extra "
            "ON user_extra(bale_user_id, field_key)")
    except Exception:
        pass


def custom_fields():
    """پارامترهای سفارشی که ادمین اضافه کرده — لیست dict"""
    import json as _j
    from database import get_setting as _gs
    try:
        raw = _gs("pf_custom_fields", "") or "[]"
        out = _j.loads(raw)
        return out if isinstance(out, list) else []
    except Exception:
        return []


def save_custom_fields(items):
    import json as _j
    from database import set_setting as _ss
    _ss("pf_custom_fields", _j.dumps(items, ensure_ascii=False),
        "پارامترهای سفارشی پروفایل", "profile")


def get_extra(uid, key, default=""):
    from database import db_execute as _dx
    r = _dx("SELECT value FROM user_extra WHERE bale_user_id=? "
            "AND field_key=?", (uid, key), fetch="one")
    return (r or {}).get("value") or default


def set_extra(uid, key, value):
    from database import db_execute as _dx
    _dx("""INSERT INTO user_extra (bale_user_id, field_key, value)
        VALUES (?,?,?)
        ON CONFLICT(bale_user_id, field_key) DO UPDATE SET
            value=excluded.value, updated_at=CURRENT_TIMESTAMP""",
        (uid, key, str(value or "")[:500]))


def prompt_of(key, dflt=""):
    """
    💬 متن سؤال یک پارامتر — از پنل قابل تغییر.

    🎯 «مثل بقیه پارامترها متن ... قابل تغییر و تنظیم باشه»

    اگر ادمین متنی ننوشته باشد، متن پیش‌فرض برمی‌گردد.
    """
    from database import get_setting as _gs
    v = (_gs(f"pf_{key}_q", "") or "").strip()
    return v or dflt


def set_prompt(key, text, uid=None):
    """✏️ ثبت متن دلخواه سؤال"""
    from database import set_setting as _ss
    _ss(f"pf_{key}_q", (text or "").strip()[:300],
        f"متن پرسش {key}", "profile", uid)


def field_type(key, dflt="short_text"):
    """🧩 نوع یک پارامتر (متنی یا رسانه‌ای)"""
    for st in FORM_STEPS:
        if st["key"] == key:
            return st.get("ftype") or dflt
    for c in custom_fields():
        if c.get("key") == key:
            return c.get("ftype") or dflt
    return dflt


def active_steps():
    """
    مراحل فعال فرم پروفایل — با اعمال تنظیمات ادمین.
    نام و نام خانوادگی همیشه فعال و اجباری است.

    🆕 فاز ۱۸-الف: پارامترهای سفارشی ادمین هم به انتهای فرم اضافه
       می‌شوند (از کاتالوگ فرم‌ساز).
    """
    out = []
    for st in FORM_STEPS:
        k = st["key"]
        # 💬 فاز ۳۸ — متن سؤال از پنل قابل تغییر است
        _p = prompt_of(k, st["prompt"])
        if k == "full_name":
            out.append(dict(st, required=True, prompt=_p))
            continue
        if not field_on(k):
            continue
        out.append(dict(st, prompt=_p,
                        required=field_required(k, st["required"])))

    # ➕ پارامترهای سفارشی
    for c in custom_fields():
        k = c.get("key")
        if not k or not field_on(k):
            continue
        _d = c.get("prompt") or (f"{c.get('icon','▫️')} "
                                 f"{c.get('name') or k}:")
        out.append({
            "key": k,
            "prompt": prompt_of(k, _d),
            "required": field_required(k, bool(c.get("required"))),
            "custom": True,
            "ftype": c.get("ftype") or "short_text",
        })
    return out


LABELS = {
    # 🔴 فاز ۱۸-الف — باگ رفع‌شده: کلید full_name در LABELS نبود، پس
    #    _required_label() کلمه خام «full_name» را به کاربر نشان می‌داد
    #    («جلو اجباری نوشته فول نیم»).
    "full_name": "👤 نام و نام خانوادگی",
    "first_name": "👤 نام",
    "last_name": "👤 نام خانوادگی",
    "national_id": "🆔 کد ملی",
    "birth_date": "📅 تاریخ تولد",
    "gender": "👤 جنسیت",
    "father_name": "👨 نام پدر",
    "mother_name": "👩 نام مادر",
    "province": "🗺️ استان",
    "city": "🏙️ شهر",
    "address": "🏠 آدرس",
    "postal_code": "📮 کد پستی",
    "education_level": "🎓 مقطع",
    "field_of_study": "📚 رشته",
    "university": "🏫 دانشگاه",
    "job_title": "💼 شغل",
    "company_name": "🏢 محل کار",
    "email": "📧 ایمیل",
    "bio": "📝 بیو",
    "profile_photo": "📸 عکس پروفایل",
}

# فیلدهایی که در دیتابیس ذخیره می‌شوند
# ⚠️ full_name ستون دیتابیسی نیست — به first_name/last_name تقسیم می‌شود
# ⚠️ profile_photo ستون دیتابیسی هست ولی **متنی** نیست —
#    مسیر فایل در آن ذخیره می‌شود و از مسیر رسانه پر می‌شود.
DB_FIELDS = [k for k in LABELS.keys()
             if k not in ("full_name", "profile_photo")]

# 🖼️ پارامترهایی که به‌جای متن، فایل می‌گیرند
MEDIA_TYPES = {
    "photo":    ("📸", "عکس", ("photo",)),
    "document": ("📎", "فایل", ("document",)),
    "voice":    ("🎤", "صدا", ("voice", "audio")),
    "video":    ("🎬", "ویدیو", ("video", "video_note")),
}


def is_media_step(step):
    """آیا این مرحله فایل می‌خواهد؟"""
    return (step or {}).get("ftype") in MEDIA_TYPES

# گروه‌بندی برای نمایش پیش‌نمایش
PREVIEW_GROUPS = [
    ("📝 اطلاعات پایه", ["first_name", "last_name", "national_id", "birth_date", "gender"]),
    ("👨‍👩‍👦 خانواده", ["father_name", "mother_name"]),
    ("🗺️ آدرس", ["province", "city", "address", "postal_code"]),
    ("🎓 تحصیلات", ["education_level", "field_of_study", "university"]),
    ("💼 شغل و تماس", ["job_title", "company_name", "email", "bio"]),
]


def _required_keys():
    """
    کلیدهای دیتابیسی فیلدهای اجباری.

    ⚠️ فاز ۱۷-ج: حالا تنظیمات ادمین را می‌خواند، پس هر بار
       تازه محاسبه می‌شود (نه یک بار در import).
    """
    out = []
    for s in active_steps():
        if not s["required"]:
            continue
        if s["key"] == "full_name":
            out += ["first_name", "last_name"]
        elif s["key"] in DB_FIELDS:
            # 🔴 باگ رفع‌شده (فاز ۳۸): فقط ستون‌های **متنیِ**
            #    جدول users اینجا برمی‌گردند.
            #
            #    عکس و پارامترهای سفارشی در جای دیگری ذخیره
            #    می‌شوند (ستون profile_photo و جدول user_extra)
            #    و در دیکشنری `profile` نیستند — پس اگر اینجا
            #    برمی‌گشتند، **همیشه** «خالی» شمرده می‌شدند و
            #    کاربر با وجود ارسال عکس، نمی‌توانست پروفایلش
            #    را ثبت کند.
            #
            #    بررسی آن‌ها جداگانه در `submit_profile` انجام
            #    می‌شود که مقدار واقعی را از منبع درست می‌خواند.
            out.append(s["key"])
    return out


# سازگاری با کد قبلی — ولی جاهای حساس از _required_keys() استفاده کنند
REQUIRED_KEYS = [k for k in
                 (["first_name", "last_name"] +
                  [s["key"] for s in FORM_STEPS
                   if s["required"] and s["key"] != "full_name"])]


# ==================== SHOW PROFILE ====================
def show_profile(cid, uid):
    u = get_user(uid)
    if not u:
        return send(cid, "⚠️ ابتدا /start را بزنید")

    percent = int(u.get("complete_profile_percent") or 0)
    blocks = max(0, min(10, percent // 10))
    bar = "▓" * blocks + "░" * (10 - blocks)

    if uid == SUPER_ADMIN_ID:
        role = "سوپرادمین 👑"
    elif u.get("is_admin"):
        role = "ادمین 👨‍💼"
    else:
        role = "کاربر 👤"

    status_map = {
        "draft": "📝 تکمیل نشده",
        "pending": "⏳ در انتظار تأیید ادمین",
        "approved": "✅ تأیید شده",
        "rejected": "❌ رد شده",
    }
    status = status_map.get(u.get("profile_status") or "draft", "نامشخص")

    lines = [
        "👤 پروفایل من",
        "━━━━━━━━━━━━━━",
        "",
        f"📊 تکمیل: {percent}%",
        bar,
        "",
        f"🎭 نقش: {role}",
        f"📌 وضعیت: {status}",
        f"🎁 کد معرفی: {u.get('referral_code') or 'ندارد'}",
        f"📱 موبایل: {u.get('mobile') or '❌ ثبت نشده'}",
        "",
    ]

    if u.get("profile_status") == "rejected" and u.get("rejection_reason"):
        lines += [f"📄 دلیل رد: {u['rejection_reason']}", ""]

    # 📋 فاز ۳۸ — فقط فیلدهای **فعال** نشان داده شوند
    #
    # 🔴 مشکل قبل: همهٔ ۱۹ فیلد چاپ می‌شدند حتی آن‌هایی که
    #    ادمین خاموششان کرده بود — کاربر ده‌ها خط «— ثبت نشده»
    #    می‌دید که هرگز قرار نبود پر شوند. اینجا بود که پیام
    #    «شلخته» می‌شد.
    _live = {st["key"] for st in active_steps()}
    _live.update({"first_name", "last_name"})   # از full_name می‌آیند

    for title, keys in PREVIEW_GROUPS:
        rows = [k for k in keys if k in _live]
        if not rows:
            continue
        vals = [(k, str(u.get(k) or "").strip()) for k in rows]
        # اگر کل گروه خالی است، فقط یک خط خلاصه
        if not any(v for _, v in vals):
            lines.append(f"{title}: — تکمیل نشده")
            continue
        lines.append(title + ":")
        for i, (k, val) in enumerate(vals):
            mark = "└──" if i == len(vals) - 1 else "├──"
            lines.append(f"{mark} {LABELS[k]}: "
                         f"{val if val else '—'}")
        lines.append("")

    # 🧩 پارامترهای سفارشی ادمین
    _cf = [c for c in custom_fields() if field_on(c.get("key"))]
    if _cf:
        _shown = []
        for c in _cf:
            v = str(get_extra(uid, c.get("key")) or "").strip()
            if c.get("ftype") in MEDIA_TYPES:
                v = "✅ ارسال شده" if v else ""
            _shown.append((c, v))
        if any(v for _, v in _shown):
            lines.append("🧩 اطلاعات تکمیلی:")
            for i, (c, v) in enumerate(_shown):
                mark = "└──" if i == len(_shown) - 1 else "├──"
                lines.append(f"{mark} {c.get('icon', '▫️')} "
                             f"{c.get('name') or c.get('key')}: "
                             f"{v if v else '—'}")
            lines.append("")

    # 🎓 فاز ۳۷ — شمارندهٔ گواهینامه از **خود جدول** خوانده شود
    #    ستون `total_certificates` یک کش است و در پنج مسیر
    #    مختلف صدور به‌روز می‌شد؛ اگر یکی از قلم می‌افتاد،
    #    عدد پروفایل برای همیشه غلط می‌ماند.
    #    شمردن مستقیم همیشه درست است.
    try:
        _n_cert = db_execute(
            "SELECT COUNT(*) AS n FROM certificates "
            "WHERE bale_user_id=? AND COALESCE(revoked,0)=0",
            (uid,), fetch="one")
        _n_cert = (_n_cert or {}).get("n")
        if _n_cert is None:
            _n_cert = u.get("total_certificates") or 0
    except Exception:
        _n_cert = u.get("total_certificates") or 0

    # ✨ گواهینامه‌های آمادهٔ دریافت (مرکز صدور)
    try:
        import certcenter as _cc
        _n_ready = len(_cc.pending_for(uid))
    except Exception:
        _n_ready = 0

    _cert_line = f"└── 🎓 گواهینامه‌ها: {_n_cert}"
    if _n_ready:
        _cert_line = (f"├── 🎓 گواهینامه‌ها: {_n_cert}\n"
                      f"└── ✨ آمادهٔ دریافت: {_n_ready}")

    lines += [
        "📊 آمار:",
        f"├── 🎯 امتیاز: {u.get('total_points') or 0}",
        f"├── 🎉 رویدادها: {u.get('total_events_registered') or 0}",
        _cert_line,
        "",
        f"📅 تاریخ عضویت: {_jd.fmt(u.get('created_at'), 'datetime')}",
    ]

    photo = u.get("profile_photo")
    has_photo = bool(photo and Path(photo).exists())

    # 📸 فاز ۳۸ — وضعیت عکس داخل متن، نه یک دکمهٔ جدا
    if field_on("profile_photo"):
        lines.insert(len(lines) - 1,
                     f"📸 عکس پروفایل: "
                     f"{'✅ ثبت شده' if has_photo else '— ثبت نشده'}")

    # 🔢 نشان روی دکمه‌ها — چند تا دارم؟
    _b = {}
    try:
        _b["certs"] = db_execute(
            "SELECT COUNT(*) AS n FROM certificates WHERE "
            "bale_user_id=? AND COALESCE(revoked,0)=0",
            (uid,), fetch="one").get("n") or 0
    except Exception:
        _b["certs"] = 0
    try:
        _b["tickets"] = db_execute(
            "SELECT COUNT(*) AS n FROM event_registrations WHERE "
            "bale_user_id=? AND status IN ('confirmed','attended')",
            (uid,), fetch="one").get("n") or 0
    except Exception:
        _b["tickets"] = 0
    try:
        _b["tk"] = db_execute(
            "SELECT COUNT(*) AS n FROM tickets WHERE "
            "bale_user_id=? AND status<>'closed'",
            (uid,), fetch="one").get("n") or 0
    except Exception:
        _b["tk"] = 0

    if has_photo:
        send_photo(cid, photo, "📸 عکس پروفایل شما")

    # اگر عکس فرستادیم، ویرایش پیام قبلی بی‌معنی است → پیام جدید
    send_or_edit(cid, "\n".join(lines),
                 kb_profile(has_photo,
                            u.get("profile_status") or "draft", _b),
                 force_new=has_photo)
    log_action(uid, "view_profile")


# ==================== START FORM ====================
def start_form(cid, uid):
    """
    شروع فرم. مقادیر فعلی پروفایل به‌عنوان پیش‌فرض بارگذاری می‌شوند
    تا کاربر برای ویرایش مجبور نباشد همه چیز را دوباره بنویسد.
    """
    u = get_user(uid)
    if not u:
        return send(cid, "⚠️ ابتدا /start را بزنید")

    if u.get("profile_status") == "pending":
        return send(cid, (
            "⏳ پروفایل شما در انتظار تأیید ادمین است.\n\n"
            "💡 بعد از بررسی، نتیجه به شما اطلاع داده می‌شود.\n"
            "اگر می‌خواهید اطلاعات را عوض کنید، تا بعد از بررسی صبر کنید."
        ), kb_profile(bool(u.get("profile_photo")), "pending"))

    prefill = {k: str(u.get(k) or "").strip() for k in DB_FIELDS if str(u.get(k) or "").strip()}

    intro = get_setting("msg_profile_intro", "📝 لطفاً پروفایل خود را تکمیل کنید.")
    text = (
        f"{intro}\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"📋 تعداد مراحل: {len(active_steps())}\n"
        f"⭐ اجباری: {_required_label()}\n"
        f"⏭️ بقیه فیلدها اختیاری هستند\n\n"
        f"💡 راهنما:\n"
        f"• «{BTN_SKIP}» = رد کردن فیلد اختیاری\n"
        f"• «{BTN_BACK}» = برگشت به مرحله قبل\n\n"
        f"⚠️ در پایان، اطلاعات برای تأیید به ادمین ارسال می‌شود."
    )
    if prefill:
        text += f"\n\n♻️ {len(prefill)} فیلد از پروفایل فعلی شما بارگذاری شد."

    # merge=False چون شروع تازه است، اما prefill را نگه می‌داریم
    set_state(uid, STATE_FORM, {"step": 0, **prefill}, merge=False)

    send(cid, text, {"inline_keyboard": [
        [{"text": "✅ شروع", "callback_data": "form_go"}],
        [{"text": "🔙 بازگشت", "callback_data": "profile_view"}],
    ]})


# ==================== ASK STEP ====================
def ask_step(cid, uid, step_idx):
    """
    پرسیدن یک مرحله.
    ✅ فیکس اصلی: به‌جای set_state(...,{'step':n}) که داده را پاک می‌کرد،
       از update_state_data استفاده می‌شود که فقط step را عوض می‌کند.
    """
    if step_idx < 0:
        step_idx = 0

    _steps = active_steps()
    if step_idx >= len(_steps):
        show_preview(cid, uid)
        return

    step = _steps[step_idx]

    # ✅ حفظ داده‌های قبلی
    data = update_state_data(uid, {"step": step_idx})
    set_state(uid, STATE_FORM, {"step": step_idx}, merge=True)

    header = f"📝 مرحله {step_idx + 1} از {len(_steps)}"
    body = step["prompt"]

    # نمایش مقدار فعلی (اگر از قبل پر شده)
    current = ""
    if step["key"] == "full_name":
        fn = str(data.get("first_name") or "").strip()
        ln = str(data.get("last_name") or "").strip()
        current = f"{fn} {ln}".strip()
    else:
        current = str(data.get(step["key"]) or "").strip()

    text = f"{header}\n━━━━━━━━━━━━━━\n\n{body}"
    if current:
        text += f"\n\n♻️ مقدار فعلی: {current}\n(برای حفظ همین مقدار «{BTN_SKIP}» را بزنید)"

    if step["required"]:
        text += "\n\n⭐ این فیلد اجباری است"
    else:
        text += f"\n\n💡 اختیاری — با «{BTN_SKIP}» رد کنید"

    # 🖼️ فاز ۳۸ — مرحلهٔ رسانه‌ای (عکس/فایل/صدا/ویدیو)
    if is_media_step(step):
        ic, nm, _ = MEDIA_TYPES[step["ftype"]]
        text = f"{header}\n━━━━━━━━━━━━━━\n\n{body}"
        if current:
            text += (f"\n\n♻️ الان یک {nm} ثبت شده"
                     f"\n(برای حفظش «{BTN_SKIP}» را بزنید)")
        if step["required"]:
            text += f"\n\n⭐ ارسال {nm} اجباری است"
        else:
            text += f"\n\n💡 اختیاری — با «{BTN_SKIP}» رد کنید"
        text += f"\n\n{ic} یک {nm} بفرستید."
        if step["ftype"] == "photo":
            text += "\n💡 خودکار فشرده می‌شود."
        send(cid, text,
             kb_skip() if (not step["required"] or current)
             else kb_cancel())
        return

    if step.get("kb") == "gender":
        kb = kb_gender()
    elif step.get("kb") == "education":
        kb = kb_education()
    elif not step["required"] or current:
        kb = kb_skip()
    else:
        kb = kb_cancel()

    send(cid, text, kb)


# ==================== HANDLE INPUT ====================
def handle_form_input(message):
    """پردازش پاسخ کاربر در فرم"""
    user = message.get("from", {})
    cid = message["chat"]["id"]
    uid = user["id"]
    raw = (message.get("text") or "").strip()

    data = get_state_data(uid)
    si = int(data.get("step") or 0)

    _steps = active_steps()
    if si >= len(_steps):
        return show_preview(cid, uid)

    step = _steps[si]
    key = step["key"]

    # ---- بازگشت به مرحله قبل (فیکس: قبلاً کل فرم را می‌بست) ----
    if raw == BTN_BACK:
        if si == 0:
            clear_state(uid)
            send(cid, "❌ تکمیل پروفایل لغو شد.", kb_remove())
            show_profile(cid, uid)
            return
        ask_step(cid, uid, si - 1)
        return

    # ---- رد کردن ----
    if raw == BTN_SKIP:
        has_value = bool(str(data.get("first_name") or "").strip()) if key == "full_name" \
            else bool(str(data.get(key) or "").strip())
        if step["required"] and not has_value:
            send(cid, "⛔ این فیلد اجباری است و نمی‌توانید آن را رد کنید.")
            return
        ask_step(cid, uid, si + 1)
        return

    # 🖼️ فاز ۳۸ — مرحلهٔ رسانه‌ای متن قبول نمی‌کند
    if is_media_step(step):
        ic, nm, _ = MEDIA_TYPES[step["ftype"]]
        send(cid, f"⚠️ اینجا باید {ic} یک {nm} بفرستید"
                  f"\n\n💡 یا با «{BTN_SKIP}» رد کنید.")
        return

    if not raw:
        send(cid, "⚠️ لطفاً متن وارد کنید.")
        return

    text = normalize_digits(raw)
    patch = {}

    # ---- اعتبارسنجی هر فیلد ----
    if key == "full_name":
        first, last = split_full_name(text)
        if not first or not last:
            send(cid, "❌ هم نام و هم نام خانوادگی را بنویسید.\n\nمثال: علی محمدی")
            return
        patch["first_name"] = first
        patch["last_name"] = last

    elif key == "national_id":
        code = text.replace("-", "").replace(" ", "")
        if not validate_national_id(code):
            send(cid, "❌ کد ملی نامعتبر است.\n\n💡 باید دقیقاً ۱۰ رقم باشد.")
            return
        patch[key] = code

    elif key == "birth_date":
        norm = validate_birth_date(text)
        if not norm:
            send(cid, "❌ تاریخ نامعتبر است.\n\n💡 فرمت درست: 1370/01/15")
            return
        patch[key] = norm

    elif key == "postal_code":
        code = text.replace("-", "").replace(" ", "")
        if not code.isdigit() or len(code) != 10:
            send(cid, "❌ کد پستی باید دقیقاً ۱۰ رقم باشد.")
            return
        patch[key] = code

    elif key == "email":
        if not validate_email(text):
            send(cid, "❌ ایمیل نامعتبر است.\n\nمثال: name@example.com")
            return
        patch[key] = text.strip()

    elif key == "gender":
        if "مرد" in text or "👨" in raw:
            patch[key] = "مرد"
        elif "زن" in text or "👩" in raw:
            patch[key] = "زن"
        else:
            send(cid, "❌ لطفاً از دکمه‌های زیر انتخاب کنید.", kb_gender())
            return

    elif key == "bio":
        if len(text) > 500:
            send(cid, "❌ بیو نباید بیشتر از ۵۰۰ کاراکتر باشد.")
            return
        patch[key] = text

    else:
        if len(text) > 250:
            send(cid, "❌ متن خیلی طولانی است (حداکثر ۲۵۰ کاراکتر).")
            return
        patch[key] = text

    # ✅ ذخیره merge شده - داده قبلی حفظ می‌شود
    update_state_data(uid, patch)
    ask_step(cid, uid, si + 1)


# ==================== PREVIEW ====================
def show_preview(cid, uid):
    """
    ✅ باگ ۱ رفع شد: چون داده در state حفظ می‌شود،
    فیلدهای پرشده درست نمایش داده می‌شوند.
    """
    data = get_state_data(uid)
    clean = {k: str(v).strip() for k, v in data.items()
             if k in DB_FIELDS and str(v or "").strip()}

    if not clean:
        clear_state(uid)
        send(cid, (
            "⚠️ اطلاعاتی ثبت نشده است.\n\n"
            "💡 لطفاً دوباره از «📝 تکمیل پروفایل» شروع کنید."
        ))
        return show_profile(cid, uid)

    missing = [LABELS[k] for k in REQUIRED_KEYS if not clean.get(k)]

    lines = [
        "👁️ پیش‌نمایش پروفایل",
        "━━━━━━━━━━━━━━",
        "",
        f"📊 تکمیل شده: {len(clean)} از {len(DB_FIELDS)} فیلد",
        "",
    ]

    # 📋 فاز ۳۸ — فقط فیلدهای فعال در پیش‌نمایش
    _steps = active_steps()
    _live = {st["key"] for st in _steps}
    _live.update({"first_name", "last_name"})

    for title, keys in PREVIEW_GROUPS:
        rows = [k for k in keys if k in _live]
        if not rows:
            continue
        lines.append(title + ":")
        for i, k in enumerate(rows):
            val = clean.get(k, "")
            mark = "└──" if i == len(rows) - 1 else "├──"
            if val:
                lines.append(f"{mark} ✅ {LABELS[k]}: {val}")
            else:
                is_req = k in REQUIRED_KEYS
                lines.append(f"{mark} {'❌' if is_req else '⏭️'} "
                             f"{LABELS[k]}: "
                             f"{'وارد نشده' if is_req else 'رد شده'}")
        lines.append("")

    # 📸 مرحله‌های رسانه‌ای
    _media = [st for st in _steps if is_media_step(st)]
    if _media:
        lines.append("🖼️ فایل‌ها:")
        for i, st in enumerate(_media):
            k = st["key"]
            ic, tn, _ = MEDIA_TYPES[st["ftype"]]
            got = bool(str(data.get(k) or "").strip())
            if not got and k == "profile_photo":
                _u0 = get_user(uid) or {}
                got = bool(_u0.get("profile_photo"))
            mark = "└──" if i == len(_media) - 1 else "├──"
            nm = LABELS.get(k) or st.get("prompt", k).rstrip(":")
            lines.append(f"{mark} {'✅' if got else '⏭️'} {nm}: "
                         f"{'ارسال شد' if got else 'رد شده'}")
        lines.append("")

    # 🧩 پارامترهای سفارشی متنی
    _cust = [st for st in _steps
             if st.get("custom") and not is_media_step(st)]
    if _cust:
        lines.append("🧩 اطلاعات تکمیلی:")
        for i, st in enumerate(_cust):
            k = st["key"]
            val = str(data.get(k) or "").strip()
            mark = "└──" if i == len(_cust) - 1 else "├──"
            nm = st.get("prompt", k).rstrip(":")
            lines.append(f"{mark} {'✅' if val else '⏭️'} {nm}: "
                         f"{val or 'رد شده'}")
        lines.append("")

    if missing:
        lines += ["⛔ فیلدهای اجباری ناقص:", "، ".join(missing), ""]
        kb = {"inline_keyboard": [
            [{"text": "🔄 تکمیل مجدد", "callback_data": "profile_fill"}],
            [{"text": "❌ انصراف", "callback_data": "back_main"}],
        ]}
    else:
        lines.append("⚠️ اطلاعات بالا صحیح است؟")
        kb = {"inline_keyboard": [
            [{"text": "✅ ارسال برای تأیید ادمین", "callback_data": "form_submit"}],
            [{"text": "✏️ ویرایش از اول", "callback_data": "profile_fill"}],
            [{"text": "❌ انصراف", "callback_data": "back_main"}],
        ]}

    # نگه داشتن state با نام preview (داده حفظ می‌شود)
    set_state(uid, STATE_PREVIEW, {}, merge=True)
    send(cid, "\n".join(lines), kb)


# ==================== SUBMIT ====================
def notify_admins(text, kb=None, exclude=None):
    """ارسال به همه ادمین‌ها (فیکس: قبلاً فقط سوپرادمین خبردار می‌شد)"""
    rows = db_execute(
        "SELECT DISTINCT bale_user_id FROM users WHERE is_admin=1 AND bale_user_id IS NOT NULL",
        fetch="all",
    ) or []
    ids = {r["bale_user_id"] for r in rows if r.get("bale_user_id")}
    if SUPER_ADMIN_ID:
        ids.add(SUPER_ADMIN_ID)
    if exclude:
        ids.discard(exclude)
    for aid in ids:
        send(aid, text, kb)


def submit_profile(cid, uid):
    """
    ✅ باگ ۲ رفع شد: داده کامل از state خوانده و به ادمین ارسال می‌شود.
    اگر داده خالی بود، پیام خطای واضح داده می‌شود (نه ارسال پیام خالی).
    """
    data = get_state_data(uid)
    profile = {k: str(v).strip() for k, v in data.items()
               if k in DB_FIELDS and str(v or "").strip()}

    # ➕ فاز ۱۸-الف — پارامترهای سفارشی در جدول user_extra ذخیره می‌شوند
    try:
        _ckeys = {c.get("key") for c in custom_fields() if c.get("key")}
        for k in _ckeys:
            v = str(data.get(k) or "").strip()
            if v:
                set_extra(uid, k, v)
    except Exception as e:
        log(f"⚠️ ذخیره پارامتر سفارشی: {e}")

    if not profile:
        clear_state(uid)
        send(cid, "❌ اطلاعاتی برای ارسال وجود ندارد.\n\n💡 دوباره پروفایل را تکمیل کنید.")
        return show_profile(cid, uid)

    missing = [LABELS.get(k, k) for k in _required_keys()
               if not profile.get(k)]

    # 🧩 فاز ۳۸ — پارامترهای سفارشی و رسانه‌ای هم اگر اجباری‌اند
    #    باید بررسی شوند.
    #
    # 🔴 باگ رفع‌شده: `_required_keys()` فقط ستون‌های جدول users
    #    را برمی‌گرداند. پارامتر سفارشی (در user_extra) و عکس
    #    هرچقدر هم «اجباری» علامت می‌خوردند، بی‌سروصدا رد
    #    می‌شدند — یعنی گزینهٔ «اجباری» برایشان بی‌اثر بود.
    for st in active_steps():
        k = st["key"]
        if not st.get("required") or k in DB_FIELDS or k == "full_name":
            continue
        got = str(data.get(k) or "").strip()
        if not got and k == "profile_photo":
            got = str((get_user(uid) or {}).get("profile_photo") or "")
        if not got:
            nm = LABELS.get(k) or st.get("prompt", k).rstrip(":")
            missing.append(nm)

    if missing:
        send(cid, "⛔ این فیلدهای اجباری خالی هستند:\n"
                  + "، ".join(missing))
        return show_preview(cid, uid)

    db_user = get_user(uid)
    if not db_user:
        clear_state(uid)
        return send(cid, "⚠️ حساب شما یافت نشد. /start را بزنید.")

    # درخواست بررسی در کارتابل مشترک ثبت می‌شود؛ SQLite فقط نمای عملیاتی ربات است.
    import uuid
    import shared_api

    shared_profile = dict(profile)
    for step in active_steps():
        key = step["key"]
        if step.get("custom") and not is_media_step(step):
            value = str(data.get(key) or "").strip()
            if value:
                shared_profile[key] = value
    # مسیرهای محلی عکس در نصب دیگر قابل دسترسی نیستند و به API فرستاده نمی‌شوند.
    shared_profile.pop("profile_photo", None)
    if not shared_profile:
        return send(cid, "❌ اطلاعاتی برای ثبت پیدا نشد. دوباره تلاش کنید.")

    idempotency_key = data.get("_shared_idempotency_key")
    if not isinstance(idempotency_key, str) or not idempotency_key:
        idempotency_key = f"profile:{uid}:{uuid.uuid4().hex}"
        update_state_data(uid, {"_shared_idempotency_key": idempotency_key})
    photo_path = data.get("profile_photo") or db_user.get("profile_photo")
    if photo_path and Path(str(photo_path)).is_file():
        try:
            file_ref = shared_api.upload_private_file(
                uid,
                Path(str(photo_path)).read_bytes(),
                Path(str(photo_path)).name or "profile.jpg",
                "profile-file:" + idempotency_key,
            )
            shared_profile["file_refs"] = [file_ref]
        except (OSError, shared_api.SharedAPIError) as exc:
            code = getattr(exc, "code", "profile_file_unavailable")
            log(f"⚠️ بارگذاری عکس پروفایل انجام نشد: {code}")
            return send(cid, "عکس پروفایل بارگذاری نشد؛ اتصال سرویس مشترک را بررسی کنید و دوباره بفرستید.")
    try:
        result = shared_api.submit_workflow(
            uid, "profile_review", shared_profile, idempotency_key
        )
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ ثبت پروفایل در API مشترک انجام نشد: {exc.code}")
        return send(cid, "پروفایل ثبت نشد؛ اتصال سرویس مشترک را بررسی کنید و دوباره بفرستید.")

    task = result["task"]
    db_execute("""UPDATE users SET profile_status='pending',
        basic_profile_completed=1,
        profile_submitted_at=CURRENT_TIMESTAMP,
        updated_at=CURRENT_TIMESTAMP
        WHERE bale_user_id=?""", (uid,))
    send(cid, (
        "✅ پروفایل شما برای بررسی ثبت شد.\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🔢 کد پیگیری: {task['id'][:8]}\n"
        f"📊 {len(shared_profile)} فیلد ثبت شد\n"
        "⏳ نتیجه پس از بررسی به شما اطلاع داده می‌شود."
    ), kb_remove())

    clear_state(uid)
    log_action(uid, "profile_submitted", {"task_id": task["id"], "fields": len(shared_profile)})
    return task["id"]

def apply_shared_review_projection(task):
    """Mirror an already-decided shared profile into bot-only legacy features."""
    if not isinstance(task, dict) or task.get("kind") != "profile_review":
        raise ValueError("invalid_shared_profile_task")
    try:
        target = int(task.get("bale_user_id"))
    except (TypeError, ValueError):
        raise ValueError("invalid_shared_profile_user") from None
    if target <= 0:
        raise ValueError("invalid_shared_profile_user")
    data = task.get("payload") or {}
    user = get_user(target)
    if not user:
        raise RuntimeError("profile_projection_user_missing")

    status = task.get("status")
    if status == "approved":
        updates = {
            key: str(value).strip()
            for key, value in data.items()
            if key in DB_FIELDS and value is not None and str(value).strip()
        }
        if data.get("full_name") and not (data.get("first_name") or data.get("last_name")):
            first, last = split_full_name(str(data["full_name"]))
            if first:
                updates["first_name"] = first
            if last:
                updates["last_name"] = last
        if updates:
            columns = ", ".join(f"{key}=?" for key in updates)
            result = db_execute(
                f"UPDATE users SET {columns}, updated_at=CURRENT_TIMESTAMP WHERE bale_user_id=?",
                [*updates.values(), target],
            )
            if result is None:
                raise RuntimeError("profile_projection_update_failed")
        db_execute("""UPDATE users SET profile_status='approved',
            basic_profile_approved=1, basic_profile_completed=1,
            rejection_reason=NULL, profile_approved_at=CURRENT_TIMESTAMP,
            updated_at=CURRENT_TIMESTAMP WHERE bale_user_id=?""", (target,))
        try:
            custom_keys = {field.get("key") for field in custom_fields() if field.get("key")}
            for key in custom_keys:
                value = data.get(key)
                if value not in (None, ""):
                    set_extra(target, key, str(value))
        except Exception as exc:
            log(f"⚠️ همگام‌سازی فیلدهای تکمیلی پروفایل: {type(exc).__name__}")
        update_percent(target)
        log_action(target, "profile_approved", {"shared_task": task.get("id")})
    elif status == "rejected":
        reason = str(task.get("review_reason") or "")[:500]
        db_execute("""UPDATE users SET profile_status='rejected',
            rejection_reason=?, updated_at=CURRENT_TIMESTAMP
            WHERE bale_user_id=?""", (reason or None, target))
        log_action(target, "profile_rejected", {"shared_task": task.get("id"), "reason": reason})
    else:
        raise ValueError("shared_profile_task_not_decided")

    from legacy_review_projection import project_legacy_review

    project_legacy_review(
        "profile_review", task, status, db_execute=db_execute
    )


# ==================== APPROVE / REJECT ====================
def _legacy_profile_review_redirect(cid, uid, *, clear_legacy_state=False):
    """Fail closed for legacy SQLite decisions; only the shared API can review."""
    if clear_legacy_state:
        clear_state(uid)
    send(
        cid,
        "بررسی محلی پروفایل غیرفعال است؛ تصمیم فقط در کارتابل مشترک ثبت می‌شود. "
        "درخواست‌های قدیمیِ خارج از کارتابل به انتقال کنترل‌شده نیاز دارند.",
        kb_remove(),
    )
    from shared_workflows import show_inbox
    return show_inbox(cid, uid, kind="profile_review")


def approve_sub(cid, admin_id, sub_id):
    return _legacy_profile_review_redirect(cid, admin_id)


def start_reject(cid, admin_id, sub_id):
    return _legacy_profile_review_redirect(cid, admin_id)


def reject_sub(cid, admin_id, sub_id, reason=None):
    return _legacy_profile_review_redirect(cid, admin_id)


def handle_reject_reason(message):
    """Close a stale local reject state without recording a local decision."""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    return _legacy_profile_review_redirect(cid, uid, clear_legacy_state=True)


# ==================== PHOTO ====================
def ask_photo(cid, uid):
    set_state(uid, STATE_PHOTO, {}, merge=False)
    send(cid, (
        "📸 عکس پروفایل (اختیاری)\n"
        "━━━━━━━━━━━━━━\n\n"
        "🖼️ یک عکس ارسال کنید.\n\n"
        "💡 عکس به‌صورت خودکار فشرده می‌شود."
    ), kb_cancel())


def _save_photo_file(cid, uid, message):
    """
    📥 دریافت و ذخیرهٔ عکس — هستهٔ مشترک.

    خروجی: مسیر فایل یا None (پیام خطا خودش فرستاده می‌شود)
    """
    photos = message.get("photo") or []
    if not photos:
        send(cid, "❌ لطفاً یک عکس ارسال کنید.")
        return None
    try:
        best = max(photos, key=lambda p: (p.get("file_size") or 0,
                                          p.get("width") or 0))
    except (ValueError, TypeError):
        best = photos[-1]
    fid = best.get("file_id")
    if not fid:
        send(cid, "❌ فایل نامعتبر")
        return None

    send(cid, "⏳ در حال پردازش عکس...")
    fi = get_file_info(fid)
    if not fi.get("ok"):
        send(cid, "❌ خطا در دریافت فایل از بله", kb_remove())
        return None
    file_path = (fi.get("result") or {}).get("file_path")
    if not file_path:
        send(cid, "❌ مسیر فایل نامعتبر", kb_remove())
        return None
    content = download_file(file_path)
    if not content:
        send(cid, "❌ خطا در دانلود عکس", kb_remove())
        return None

    u = get_user(uid)
    if not u:
        send(cid, "⚠️ /start را بزنید", kb_remove())
        return None

    new_path = compress_photo(content, u["id"])
    if not new_path:
        send(cid, ("❌ خطا در ذخیره عکس.\n\n"
                   "💡 اگر Pillow نصب نیست:\npy -m pip install Pillow"),
             kb_remove())
        return None

    # 🗑️ عکس قبلی را **بعد از** موفقیت پاک کن
    old_p = u.get("profile_photo")
    if old_p and old_p != new_path:
        try:
            Path(old_p).unlink(missing_ok=True)
        except Exception:
            pass

    db_execute("UPDATE users SET profile_photo=?, "
               "updated_at=CURRENT_TIMESTAMP WHERE bale_user_id=?",
               (new_path, uid))
    update_percent(uid)
    return new_path


def handle_form_photo(message):
    """
    📸 فاز ۳۸ — عکس در جریان تکمیل پروفایل.

    🎯 «افزودن عکس ... بره زیرمجموعهٔ تکمیل پروفایل»

    وقتی کاربر وسط فرم است و مرحلهٔ جاری از نوع عکس است،
    این تابع آن را می‌گیرد و به مرحلهٔ بعد می‌برد.

    خروجی: True اگر رسیدگی شد
    """
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    if get_state_name(uid) != STATE_FORM:
        return False

    data = get_state_data(uid)
    si = int(data.get("step") or 0)
    steps = active_steps()
    if si >= len(steps):
        return False
    step = steps[si]
    if not is_media_step(step) or step.get("ftype") != "photo":
        return False

    path = _save_photo_file(cid, uid, message)
    if not path:
        return True

    # 🧩 پارامتر سفارشی رسانه‌ای → در user_extra
    if step.get("custom"):
        set_extra(uid, step["key"], path)
    update_state_data(uid, {step["key"]: path})

    size_kb = os.path.getsize(path) / 1024
    send(cid, f"✅ عکس ثبت شد ({size_kb:.0f} کیلوبایت)", kb_remove())
    ask_step(cid, uid, si + 1)
    return True


def handle_photo(message):
    user = message.get("from", {})
    cid = message["chat"]["id"]
    uid = user["id"]

    # 📝 فاز ۳۸ — اگر وسط فرم است، همان‌جا رسیدگی شود
    if handle_form_photo(message):
        return

    if get_state_name(uid) != STATE_PHOTO:
        return

    # ♻️ فاز ۳۸ — منطق تکراری به `_save_photo_file` منتقل شد
    #    تا مسیر فرم و مسیر مستقل دقیقاً یکسان رفتار کنند.
    new_path = _save_photo_file(cid, uid, message)
    clear_state(uid)
    if not new_path:
        return

    size_kb = os.path.getsize(new_path) / 1024
    send(cid, f"✅ عکس پروفایل ذخیره شد!\n"
              f"📸 حجم: {size_kb:.0f} کیلوبایت", kb_remove())
    time.sleep(0.5)
    show_profile(cid, uid)


def delete_photo(cid, uid):
    u = get_user(uid)
    if not u or not u.get("profile_photo"):
        return send(cid, "⚠️ عکسی ثبت نشده است")
    try:
        Path(u["profile_photo"]).unlink(missing_ok=True)
    except Exception:
        pass
    db_execute("UPDATE users SET profile_photo=NULL WHERE bale_user_id=?", (uid,))
    update_percent(uid)
    send(cid, "🗑️ عکس پروفایل حذف شد")
    show_profile(cid, uid)


def compress_photo(content, user_id):
    """فشرده‌سازی و ذخیره عکس در ساختار سال/ماه"""
    try:
        from PIL import Image
    except ImportError:
        log("❌ Pillow نصب نیست: py -m pip install Pillow")
        return None

    try:
        now = datetime.now()
        d = Path(PROFILES_DIR) / now.strftime("%Y") / now.strftime("%m")
        d.mkdir(parents=True, exist_ok=True)
        fp = d / f"user_{user_id}_{now.strftime('%Y%m%d_%H%M%S')}.jpg"

        img = Image.open(io.BytesIO(content))

        if img.mode in ("RGBA", "LA", "P"):
            if img.mode == "P":
                img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            alpha = img.split()[-1] if img.mode in ("RGBA", "LA") else None
            bg.paste(img, mask=alpha)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1)
        img.thumbnail((800, 800), resample)
        img.save(fp, "JPEG", quality=85, optimize=True)

        log(f"📸 عکس ذخیره شد: {fp.name} ({os.path.getsize(fp)/1024:.0f}KB)")
        return str(fp).replace("\\", "/")
    except Exception as e:
        log(f"❌ فشرده‌سازی عکس: {e}")
        return None
