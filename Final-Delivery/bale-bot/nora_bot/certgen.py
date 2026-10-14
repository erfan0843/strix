"""
🎓 موتور گواهینامه — فاز ۱۹

درخواست کاربر:
  «از فایل ورد خام گواهینامه، قسمت‌هایی مثل نام و نام خانوادگی خالی بود،
   اون از دیتا و دستوراتی که بهش میدادم، فایل ورد رو با مشخصات
   شخصی‌سازی شده تبدیل میکرد به PNG و PDF و میداد به کاربر...
   حتی جای کیوآرکد اعتبارسنجی رو من در ورد معلوم میکنم...
   ادمین بتونه فایل ورد بده با جای خالی پارامترهای مورد نیاز و ربات
   سیو کنه به عنوان قالب گواهینامه‌ها»

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 جریان کار

  ۱) ادمین فایل .docx می‌فرستد که در آن نوشته:
        «گواهی می‌شود جناب {نام} با کدملی {کدملی} در کارگاه
         {رویداد} به مدت {ساعت} ساعت شرکت نموده است.»
     و هرجا خواست QR باشد می‌نویسد {کیوآر}

  ۲) ربات قالب را ذخیره می‌کند و پارامترهای داخلش را می‌شناسد

  ۳) موقع صدور، جای خالی‌ها با داده واقعی پر می‌شود
     → خروجی: DOCX شخصی‌سازی‌شده + PDF + PNG

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🖨️ موتور تبدیل (دو لایه — هر کدام در دسترس بود)

  ۱. LibreOffice  → عیناً طرح ورد (لوگو، رنگ، فونت) — بهترین کیفیت
  ۲. تصویر پس‌زمینه → PNG خام + نوشتن متن روی آن با Pillow

اگر هیچ‌کدام نبود، حداقل فایل DOCX شخصی‌سازی‌شده تحویل می‌شود.
"""
from privacy import user_error_message
import copy
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

from config import FILES_DIR, org_name, bot_name
from database import (db_execute, db_scalar, get_setting, set_setting,
                      ensure_table, log)

CERT_TPL_DIR = Path(FILES_DIR) / "cert_templates"
CERT_OUT_DIR = Path(FILES_DIR) / "certificates"
CERT_ASSET_DIR = Path(FILES_DIR) / "cert_assets"


# ══════════════════════════════════════════════════════════
# 🏷️ پارامترهای قابل استفاده در قالب ورد
#
# هم فارسی هم انگلیسی پشتیبانی می‌شود تا ادمین راحت باشد.
# ══════════════════════════════════════════════════════════
PLACEHOLDERS = {
    # ─────────── 👤 هویت دریافت‌کننده ───────────
    "name":        (["نام", "نام و نام خانوادگی", "name", "fullname"],
                    "نام کامل دریافت‌کننده", "👤"),
    "first_name":  (["نام کوچک", "first_name"], "فقط نام", "👤"),
    "last_name":   (["نام خانوادگی", "last_name"], "فقط نام خانوادگی", "👤"),
    "father_name": (["نام پدر", "father_name"], "نام پدر", "👨"),
    "national_id": (["کدملی", "کد ملی", "national_id", "nid"],
                    "کد ملی دریافت‌کننده", "🆔"),
    "birth_date":  (["تاریخ تولد", "birth_date"], "تاریخ تولد", "🎂"),
    "gender":      (["جنسیت", "gender"], "مرد / زن", "⚧"),
    "gender_title": (["خطاب", "جناب/سرکار", "title", "salutation"],
                     "جناب آقای / سرکار خانم (خودکار)", "🎩"),
    "mobile":      (["موبایل", "شماره موبایل", "mobile", "phone"],
                    "شماره موبایل", "📱"),
    "email":       (["ایمیل", "email"], "پست الکترونیک", "📧"),
    "member_id":   (["شماره عضویت", "کد کاربری", "member_id"],
                    "شناسه عضویت در ربات", "🎫"),
    "education":   (["مقطع", "تحصیلات", "education"],
                    "مقطع تحصیلی", "🎓"),
    "field_study": (["رشته", "رشته تحصیلی", "field_study"],
                    "رشته تحصیلی", "📚"),
    "university":  (["دانشگاه", "مدرسه", "university"],
                    "دانشگاه یا مدرسه", "🏫"),
    "job":         (["شغل", "job"], "عنوان شغلی", "💼"),
    "company":     (["محل کار", "سازمان محل کار", "company"],
                    "سازمان محل کار", "🏢"),
    "city":        (["شهر", "city"], "شهر", "🏙️"),
    "province":    (["استان", "province"], "استان", "🗺️"),

    # ─────────── 🎓 اطلاعات دوره ───────────
    "event":       (["رویداد", "دوره", "کارگاه", "عنوان", "event", "course"],
                    "عنوان رویداد یا دوره", "🎉"),
    "event_type":  (["نوع دوره", "event_type"],
                    "کارگاه / همایش / دوره", "🏷️"),
    "event_desc":  (["توضیح دوره", "event_desc"], "توضیح کوتاه دوره", "📄"),
    "date":        (["تاریخ", "date"], "تاریخ برگزاری (شمسی)", "📅"),
    "start_date":  (["تاریخ شروع", "start_date"], "تاریخ شروع", "🟢"),
    "end_date":    (["تاریخ پایان", "end_date"], "تاریخ پایان", "🔴"),
    "date_range":  (["بازه تاریخ", "date_range"],
                    "از ... تا ... (خودکار)", "📆"),
    "issue_date":  (["تاریخ صدور", "issue_date"],
                    "تاریخ صدور گواهینامه", "🗓️"),
    "expire_date": (["تاریخ انقضا", "اعتبار تا", "expire_date"],
                    "تاریخ انقضای اعتبار", "⏳"),
    "hours":       (["ساعت", "مدت", "hours", "duration"],
                    "مدت دوره به ساعت", "⏱️"),
    "sessions":    (["جلسات", "تعداد جلسات", "sessions"],
                    "تعداد جلسات حضور", "📊"),
    "total_sessions": (["کل جلسات", "total_sessions"],
                       "تعداد کل جلسات دوره", "📋"),
    "attendance_pct": (["درصد حضور", "attendance_pct"],
                       "درصد حضور در جلسات", "📈"),
    "score":       (["نمره", "score"], "نمره کسب‌شده", "💯"),
    "max_score":   (["نمره کل", "max_score"], "نمره کامل", "💯"),
    "grade":       (["رتبه", "درجه", "grade"], "رتبه یا درجه", "🏅"),
    "rank":        (["رتبه عددی", "rank"], "رتبه بین شرکت‌کنندگان", "🥇"),
    "result":      (["نتیجه", "وضعیت", "result"],
                    "قبول / مردود (خودکار)", "✅"),
    "location":    (["محل", "مکان", "location"], "محل برگزاری", "📍"),
    "mode":        (["نحوه برگزاری", "شیوه", "mode"], "حضوری / برخط", "🌐"),
    "teacher":     (["مدرس", "استاد", "teacher", "instructor"],
                    "نام مدرس دوره", "👨‍🏫"),
    "organizer":   (["برگزارکننده", "organizer"], "برگزارکننده", "🏛️"),

    # ─────────── 🏢 هویت سازمان ───────────
    "org":         (["سازمان", "مجموعه", "org"], "نام مجموعه", "🏢"),
    "org_en":      (["نام لاتین", "org_en"], "نام انگلیسی مجموعه", "🔤"),
    "org_address": (["آدرس سازمان", "org_address"], "آدرس مجموعه", "🗺️"),
    "org_phone":   (["تلفن سازمان", "org_phone"], "تلفن تماس", "☎️"),
    "org_site":    (["وبسایت", "org_site"], "آدرس وب‌سایت", "🌍"),

    # ─────────── ✍️ امضای اول ───────────
    "signer":      (["امضاکننده", "نام امضاکننده", "signer"],
                    "نام فرد امضاکننده", "✍️"),
    "org_role":    (["سمت", "سمت امضاکننده", "signer_role", "role"],
                    "سمت امضاکننده", "🎖️"),
    "sign_img":    (["امضا", "تصویر امضا", "signature", "sign"],
                    "🖼️ تصویر امضای اول", "✒️"),

    # ─────────── ✍️ امضای دوم (دو امضایی) ───────────
    "signer2":     (["امضاکننده دوم", "signer2"],
                    "نام امضاکننده دوم", "✍️"),
    "role2":       (["سمت دوم", "role2", "signer2_role"],
                    "سمت امضاکننده دوم", "🎖️"),
    "sign_img2":   (["امضا دوم", "تصویر امضا دوم", "signature2", "sign2"],
                    "🖼️ تصویر امضای دوم", "✒️"),

    # ─────────── ✍️ امضای سوم ───────────
    "signer3":     (["امضاکننده سوم", "signer3"],
                    "نام امضاکننده سوم", "✍️"),
    "role3":       (["سمت سوم", "role3"], "سمت امضاکننده سوم", "🎖️"),
    "sign_img3":   (["امضا سوم", "signature3", "sign3"],
                    "🖼️ تصویر امضای سوم", "✒️"),

    # ─────────── 🖼️ تصاویر و نشان‌ها ───────────
    "logo":        (["لوگو", "آرم", "logo"], "🖼️ لوگوی اصلی", "🏛️"),
    "logo2":       (["لوگو دوم", "آرم دوم", "logo2"],
                    "🖼️ لوگوی دوم (همکار)", "🏛️"),
    "logo3":       (["لوگو سوم", "logo3"], "🖼️ لوگوی سوم", "🏛️"),
    "stamp":       (["مهر", "مهر سازمان", "stamp", "seal"],
                    "🖼️ مهر سازمان", "🔴"),
    "badge":       (["نشان", "مدال", "badge"], "🖼️ نشان یا مدال", "🎖️"),
    "photo":       (["عکس", "عکس پرسنلی", "photo", "avatar"],
                    "🖼️ عکس دریافت‌کننده", "📷"),
    "watermark":   (["واترمارک", "watermark"], "🖼️ واترمارک", "💧"),

    # ─────────── 🔖 شناسه و اعتبارسنجی ───────────
    "serial":      (["شماره", "سریال", "شماره گواهینامه", "serial", "number"],
                    "شماره یکتای گواهینامه", "🔖"),
    "reg_number":  (["شماره ثبت", "reg_number"],
                    "شماره ثبت اداری", "📑"),
    # 🔍 فاز ۳۴ — شناسهٔ دولایه و اعتبار
    "doc_no":      (["شماره نامه", "شمارهٔ نامه", "شماره مکاتبه",
                     "doc_no", "letter_no"],
                    "شماره نامهٔ رویداد (مشترک)", "📄"),
    "issued_on":   (["تاریخ صدور", "صدور", "issued_on", "issue_date"],
                    "تاریخ صدور گواهینامه", "📅"),
    "expires_on":  (["تاریخ انقضا", "انقضا", "اعتبار تا",
                     "expires_on", "expiry"],
                    "تاریخ پایان اعتبار", "⏳"),
    "qr":          (["کیوآر", "کیو آر", "کیوآرکد", "کیو آر کد",
                     "کد کیوآر", "کد qr", "qr", "qrcode", "qr_code",
                     "qr code", "کیوارکد", "کیوار", "بارکد دوبعدی",
                     "کد دوبعدی", "کدqr", "تصویر کیوآر"],
                    "🔳 تصویر QR اعتبارسنجی", "🔳"),
    "barcode":     (["بارکد", "barcode", "بار کد", "کد میله‌ای",
                     "بارکد خطی"], "🖼️ بارکد خطی", "▌"),
    "verify_url":  (["لینک اعتبارسنجی", "verify_url", "link"],
                    "لینک بررسی اصالت", "🔗"),
    "verify_code": (["کد اعتبارسنجی", "verify_code"],
                    "کد کوتاه بررسی", "🔑"),
    "bot_name":    (["نام ربات", "bot_name"], "نام ربات", "🤖"),

    # ─────────── 📝 آزاد ───────────
    "note":        (["یادداشت", "توضیحات", "note"],
                    "یادداشت آزاد", "📝"),
    "custom1":     (["دلخواه۱", "custom1"], "متن دلخواه ۱", "✏️"),
    "custom2":     (["دلخواه۲", "custom2"], "متن دلخواه ۲", "✏️"),
    "custom3":     (["دلخواه۳", "custom3"], "متن دلخواه ۳", "✏️"),
}

# 📂 دسته‌بندی برای نمایش مرتب در پنل ادمین
PH_GROUPS = [
    ("👤 هویت دریافت‌کننده",
     ["name", "first_name", "last_name", "father_name", "national_id",
      "birth_date", "gender", "gender_title", "mobile", "email",
      "member_id", "education", "field_study", "university", "job",
      "company", "city", "province"]),
    ("🎓 اطلاعات دوره",
     ["event", "event_type", "event_desc", "date", "start_date",
      "end_date", "date_range", "issue_date", "expire_date", "hours",
      "sessions", "total_sessions", "attendance_pct", "score",
      "max_score", "grade", "rank", "result", "location", "mode",
      "teacher", "organizer"]),
    ("🏢 هویت سازمان",
     ["org", "org_en", "org_address", "org_phone", "org_site"]),
    ("✍️ امضاها",
     ["signer", "org_role", "sign_img", "signer2", "role2", "sign_img2",
      "signer3", "role3", "sign_img3"]),
    ("🖼️ تصاویر و نشان‌ها",
     ["logo", "logo2", "logo3", "stamp", "badge", "photo", "watermark"]),
    ("🔖 شناسه و اعتبارسنجی",
     ["serial", "reg_number", "doc_no", "qr", "barcode", "verify_url",
      "verify_code", "issued_on", "expires_on", "bot_name"]),
    ("📝 متن آزاد", ["note", "custom1", "custom2", "custom3"]),
]

# کلیدهایی که تصویر می‌شوند (نه متن)
IMAGE_KEYS = {
    "qr", "barcode",
    "sign_img", "sign_img2", "sign_img3",
    "logo", "logo2", "logo3",
    "stamp", "badge", "photo", "watermark",
}

# 📐 اندازه پیش‌فرض هر تصویر (میلی‌متر) — از پنل قابل تغییر
IMAGE_MM = {
    "qr": 25, "barcode": 40,
    "sign_img": 35, "sign_img2": 35, "sign_img3": 35,
    "logo": 30, "logo2": 25, "logo3": 25,
    "stamp": 30, "badge": 25, "photo": 28, "watermark": 90,
}


def _norm(s):
    """نرمال‌سازی نام پارامتر برای مقایسه"""
    s = str(s or "").strip().lower()
    s = s.replace("ي", "ی").replace("ك", "ک")
    s = s.replace("\u200c", " ")          # نیم‌فاصله → فاصله
    s = re.sub(r"[\s_\-]+", " ", s)
    return s.strip()


_ALIAS = {}
for _k, _v in PLACEHOLDERS.items():
    for _n in _v[0]:
        _ALIAS[_norm(_n)] = _k


def ph_label(key):
    """برچسب فارسی یک پارامتر"""
    v = PLACEHOLDERS.get(key)
    return v[0][0] if v else key


def ph_desc(key):
    v = PLACEHOLDERS.get(key)
    return v[1] if v else ""


def ph_icon(key):
    v = PLACEHOLDERS.get(key)
    return (v[2] if len(v) > 2 else "▫️") if v else "▫️"


# 🔤 ریشه‌هایی که هر جور نوشته شوند باز هم شناخته می‌شوند
_FUZZY_ROOTS = [
    ("qr", ("کیوآر", "کیوار", "کیو آر", "qr", "qrcode",
            "دوبعدی", "دو بعدی")),
    ("barcode", ("بارکد", "بار کد", "barcode", "میله")),
]


def resolve_key(raw):
    """
    نام داخل {} را به کلید داخلی تبدیل می‌کند.

    🔴 فاز ۲۴: کاربر می‌نویسد «{کیوآرکد}» یا «{کد QR}» و هیچ
       اتفاقی نمی‌افتاد — چون دقیقاً در فهرست مترادف‌ها نبود و
       آکولاد خام روی گواهینامه می‌ماند.
       حالا اگر تطابق دقیق نبود، دنبال ریشه می‌گردیم.
    """
    n = _norm(raw)
    if not n:
        return None
    hit = _ALIAS.get(n)
    if hit:
        return hit

    # حذف واژه‌های زائد رایج
    cleaned = n
    for w in ("تصویر ", "عکس ", "کد ", "image ", "img "):
        if cleaned.startswith(w):
            cleaned = cleaned[len(w):].strip()
    if cleaned != n:
        hit = _ALIAS.get(cleaned)
        if hit:
            return hit

    compact = n.replace(" ", "")
    for key, roots in _FUZZY_ROOTS:
        for r in roots:
            if r.replace(" ", "") in compact:
                return key
    return None


# الگوی پیدا کردن {پارامتر} و {{پارامتر}}
_PH_RE = re.compile(r"\{\{?\s*([^{}]{1,40}?)\s*\}?\}")


def find_placeholders(text):
    """همه پارامترهای داخل یک متن — خروجی: set از کلیدهای داخلی"""
    out = set()
    for m in _PH_RE.finditer(str(text or "")):
        k = resolve_key(m.group(1))
        if k:
            out.add(k)
    return out


def init_cert_tables():
    from database import ensure_table
    ensure_table("cert_templates", {
        "name": "TEXT",
        "file_path": "TEXT",
        "kind": "TEXT DEFAULT 'docx'",     # docx | image
        "placeholders": "TEXT",            # JSON لیست کلیدها
        "qr_x": "INTEGER DEFAULT 0",       # موقعیت QR در حالت تصویری
        "qr_y": "INTEGER DEFAULT 0",
        "qr_size": "INTEGER DEFAULT 150",
        "boxes": "TEXT",                   # JSON مختصات متن‌ها (تصویری)
        "is_default": "INTEGER DEFAULT 0",
        "is_active": "INTEGER DEFAULT 1",
        "created_by": "INTEGER",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    })
    # 🖼️ فاز ۱۹-ب — تصاویر گواهینامه (امضا، مهر، لوگو، …)
    ensure_table("cert_assets", {
        "key": "TEXT",              # sign_img | stamp | logo | …
        "title": "TEXT",
        "file_path": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "created_by": "INTEGER",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    })
    # 🎓 فاز ۳۲ — چند گواهینامه برای یک رویداد
    #
    # 🎯 «بعضی رویدادها همکاری هستن و ممکن یک تا چندین گواهی
    #     مستقل صادر بشه»
    #
    # هر ردیف = یک گواهینامهٔ مستقل که به رویداد وصل است.
    # مثلاً همایش مشترک با دو سازمان → دو گواهینامهٔ جدا.
    ensure_table("event_certs", {
        "event_id": "INTEGER",
        "template_id": "INTEGER",
        "title": "TEXT",              # «گواهینامهٔ دانشگاه فرهنگیان»
        "issuer": "TEXT",             # نام سازمان صادرکننده
        "issuer_logo": "TEXT",        # مسیر لوگوی آن سازمان
        "note": "TEXT",               # توضیح برای شرکت‌کننده
        "auto_issue": "INTEGER DEFAULT 1",   # خودکار بعد از رویداد
        "condition": "TEXT",          # شرط اختصاصی این گواهینامه
        "min_sessions": "INTEGER DEFAULT 0",
        "min_score": "INTEGER DEFAULT 0",
        "show_in_ad": "INTEGER DEFAULT 1",   # در تبلیغ رویداد دیده شود
        "position": "INTEGER DEFAULT 0",     # ترتیب نمایش
        "is_active": "INTEGER DEFAULT 1",
        "created_by": "INTEGER",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    })

    # 🎟️ فاز ۳۲ — صدور گروهی با لینک اشتراکی
    #
    # 🎯 «با فایل اکسل گواهینامه بزنی و من بتونم با لینک
    #     اشتراکش بزارم، طرف بیاد ربات استارت بزنه پروفشو
    #     تکمیل کنه و گواهیشو بگیره»
    ensure_table("cert_batches", {
        "code": "TEXT",               # کد یکتای لینک
        "title": "TEXT",
        "template_id": "INTEGER",
        "event_id": "INTEGER",        # اختیاری
        "params": "TEXT",             # JSON مقادیر مشترک
        "match_by": "TEXT DEFAULT 'mobile'",   # mobile | national_id | code
        "require_profile": "INTEGER DEFAULT 1",
        "expires_at": "TEXT",
        "max_claims": "INTEGER DEFAULT 0",     # ۰ = نامحدود
        "claimed": "INTEGER DEFAULT 0",
        "total": "INTEGER DEFAULT 0",
        "is_active": "INTEGER DEFAULT 1",
        "created_by": "INTEGER",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    })

    # 👤 ردیف‌های هر دسته — یک نفر در هر ردیف
    ensure_table("cert_batch_rows", {
        "batch_id": "INTEGER",
        "full_name": "TEXT",
        "mobile": "TEXT",
        "national_id": "TEXT",
        "claim_code": "TEXT",         # کد اختصاصی این نفر
        "extra": "TEXT",              # JSON ستون‌های اضافه اکسل
        "status": "TEXT DEFAULT 'pending'",   # pending|claimed|issued
        "claimed_by": "INTEGER",      # bale_user_id
        "cert_id": "INTEGER",
        "claimed_at": "TEXT",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    })

    for q in [
        "CREATE INDEX IF NOT EXISTS idx_evcert_ev "
        "ON event_certs(event_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_batch_code "
        "ON cert_batches(code)",
        "CREATE INDEX IF NOT EXISTS idx_brow_batch "
        "ON cert_batch_rows(batch_id)",
        "CREATE INDEX IF NOT EXISTS idx_brow_mobile "
        "ON cert_batch_rows(mobile)",
        "CREATE INDEX IF NOT EXISTS idx_brow_nid "
        "ON cert_batch_rows(national_id)",
    ]:
        try:
            db_execute(q)
        except Exception:
            pass

    CERT_TPL_DIR.mkdir(parents=True, exist_ok=True)
    CERT_OUT_DIR.mkdir(parents=True, exist_ok=True)
    CERT_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    log("✅ جدول قالب گواهینامه آماده شد")


# ══════════════════════════════════════════════════════════
# 🖼️ تصاویر ثابت گواهینامه — امضا، مهر، لوگو
# ══════════════════════════════════════════════════════════
def get_asset(key):
    """مسیر تصویر ثبت‌شده برای یک کلید"""
    r = db_execute("SELECT * FROM cert_assets WHERE key=? AND is_active=1 "
                   "ORDER BY id DESC LIMIT 1", (key,), fetch="one")
    if not r:
        return None
    fp = r.get("file_path")
    return fp if fp and Path(fp).exists() else None


def all_assets():
    """همه تصاویر فعال — dict {key: path}"""
    out = {}
    for r in db_execute("SELECT * FROM cert_assets WHERE is_active=1 "
                        "ORDER BY id", fetch="all") or []:
        fp = r.get("file_path")
        if fp and Path(fp).exists():
            out[r["key"]] = fp
    return out


def set_asset(key, path, title=None, uid=None):
    db_execute("UPDATE cert_assets SET is_active=0 WHERE key=?", (key,))
    return db_execute(
        "INSERT INTO cert_assets (key, title, file_path, created_by) "
        "VALUES (?,?,?,?)",
        (key, title or ph_label(key), str(path), uid))


def del_asset(key):
    rows = db_execute("SELECT file_path FROM cert_assets WHERE key=?",
                      (key,), fetch="all") or []
    db_execute("DELETE FROM cert_assets WHERE key=?", (key,))
    for r in rows:
        try:
            Path(r["file_path"]).unlink(missing_ok=True)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════
# 📄 خواندن و تحلیل فایل ورد
# ══════════════════════════════════════════════════════════
def docx_available():
    try:
        import docx  # noqa
        return True
    except ImportError:
        return False


def scan_docx(path):
    """
    🔍 پارامترهای داخل یک فایل ورد را پیدا می‌کند.

    همه جا را می‌گردد: پاراگراف‌ها، جدول‌ها، هدر و فوتر و
    حتی text-box ها (که خیلی از قالب‌های گرافیکی از آن استفاده می‌کنند).
    """
    try:
        import docx
    except ImportError:
        return set(), "کتابخانه python-docx نصب نیست"

    try:
        d = docx.Document(str(path))
    except Exception as e:
        return set(), f"فایل ورد خوانده نشد: {user_error_message(e)}"

    found = set()
    for txt in _iter_all_text(d):
        found |= find_placeholders(txt)
    return found, ""


def _iter_all_text(d):
    """همه متن‌های یک سند ورد (پاراگراف، جدول، هدر، فوتر، تکست‌باکس)"""
    for p in d.paragraphs:
        yield p.text
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                yield c.text
                for p in c.paragraphs:
                    yield p.text
    for sec in d.sections:
        for part in (sec.header, sec.footer,
                     getattr(sec, "first_page_header", None),
                     getattr(sec, "first_page_footer", None)):
            if not part:
                continue
            for p in part.paragraphs:
                yield p.text
            for t in part.tables:
                for row in t.rows:
                    for c in row.cells:
                        yield c.text
    # 📦 تکست‌باکس‌ها — قالب‌های گرافیکی معمولاً اینجا متن دارند
    try:
        from docx.oxml.ns import qn
        body = d.element.body
        for node in body.iter(qn("w:t")):
            if node.text:
                yield node.text
    except Exception:
        pass


def _replace_in_paragraph(par, mapping):
    """
    جایگزینی امن داخل یک پاراگراف.

    🔴 چرا پیچیده است؟ ورد یک عبارت را به چند «run» می‌شکند
       (مثلاً «{نا» + «م}»). اگر run به run جایگزین کنیم، پارامتر
       پیدا نمی‌شود. پس کل متن پاراگراف را می‌گیریم، جایگزین می‌کنیم
       و در run اول می‌نویسیم — ولی قالب‌بندی run اول حفظ می‌شود.
    """
    full = "".join(r.text or "" for r in par.runs)
    if not full or "{" not in full:
        return False
    new = _apply_mapping(full, mapping)
    if new == full:
        return False
    if par.runs:
        par.runs[0].text = new
        for r in par.runs[1:]:
            r.text = ""
    return True


def _apply_mapping(text, mapping):
    """{پارامتر} را با مقدار واقعی عوض می‌کند"""
    def sub(m):
        k = resolve_key(m.group(1))
        if k is None:
            return m.group(0)          # ناشناخته → دست نخورده
        if k in IMAGE_KEYS:
            return ""                  # تصویر جداگانه جاگذاری می‌شود
        v = mapping.get(k)
        return "" if v is None else str(v)
    return _PH_RE.sub(sub, text)


def fill_docx(tpl_path, out_path, mapping, qr_png=None, images=None):
    """
    📝 قالب ورد را با داده پر می‌کند.

    qr_png: مسیر تصویر QR (سازگاری با نسخه قبل)
    images: dict {"sign_img": "/path.png", "stamp": "...", "logo": "..."}
            همه تصاویر گواهینامه — امضا، مهر، لوگو، عکس و…
    """
    images = dict(images or {})
    if qr_png:
        images.setdefault("qr", qr_png)
    # 🔳 کدام تصویرها اگر جایشان در قالب نبود، باید ته صفحه اضافه شوند
    _must = {k.strip() for k in
             (get_setting("cert_force_images", "qr") or "").split(",")
             if k.strip()}
    try:
        import docx
        from docx.shared import Mm
    except ImportError:
        return None, "python-docx نصب نیست"

    try:
        d = docx.Document(str(tpl_path))
    except Exception as e:
        return None, f"باز کردن قالب ناموفق: {user_error_message(e)}"

    # 📐 ۰) پس‌زمینه را دقیقاً روی صفحه بنشان
    if get_setting("cert_fit_bg", "1") == "1":
        try:
            _fit_background(d)
        except Exception as e:
            log(f"⚠️ تنظیم پس‌زمینه: {e}")

    # 🖼️ ۱) اول تصاویر — قبل از اینکه متن‌ها جایگزین شوند!
    #    🔴 باگ رفع‌شده: اگر اول متن‌ها را جایگزین می‌کردیم،
    #       {کیوآر} و {امضا} پاک می‌شدند و جایی برای تصویر نمی‌ماند.
    _orphans = []
    # 🎯 فاز ۳۵ — جای کادرهای قالب را **قبل از** پاک شدن متن‌ها
    #    ذخیره کن. مرحلهٔ ۲/۳ پایین همهٔ {پارامتر}ها را حذف
    #    می‌کنند و بعد از آن دیگر نمی‌شود فهمید ادمین کیوآر را
    #    کجا خواسته بود.
    _pos = {}
    if get_setting("cert_pos_from_tpl", "1") == "1":
        for _key in images:
            try:
                _c = _textbox_anchor(d, _key)
                if _c:
                    _pos[_key] = _c
            except Exception as e:
                log(f"⚠️ خواندن جای {_key}: {e}")

    for _key, _path in images.items():
        if not _path or not Path(_path).exists():
            continue
        if not _place_image(d, _key, _path):
            # 🔴 باگ رفع‌شده: قبلاً فقط لاگ می‌زد و رد می‌شد.
            #    اگر ادمین در قالبش نه {کیوآر} نوشته بود و نه تصویر
            #    نمونه گذاشته بود، کیوآر **هرگز** ساخته نمی‌شد و
            #    کاربر فکر می‌کرد ربات خراب است.
            #    حالا: تصویرهای ضروری ته سند اضافه می‌شوند.
            if _key in _must:
                _orphans.append((_key, _path))
                if _key in _pos:
                    # 🎯 جایش در قالب **هست** (کادر) — فقط نمی‌شود
                    #    داخل تکست‌باکس تصویر گذاشت، پس شناور
                    #    دقیقاً روی همان مختصات می‌نشیند.
                    log(f"🎯 {ph_label(_key)} روی کادر قالب "
                        f"می‌نشیند")
                else:
                    log(f"🔳 جای {{{ph_label(_key)}}} در قالب نبود — "
                        f"شناور در جای پیش‌فرض")
            else:
                log(f"💡 جای {{{ph_label(_key)}}} در قالب نبود")

    # ۲) متن‌ها
    def walk(container):
        for p in getattr(container, "paragraphs", []):
            _replace_in_paragraph(p, mapping)
        for t in getattr(container, "tables", []):
            for row in t.rows:
                for c in row.cells:
                    walk(c)

    walk(d)
    for sec in d.sections:
        for part in (sec.header, sec.footer):
            if part:
                walk(part)

    # ۳) تکست‌باکس‌ها (w:t مستقیم)
    try:
        from docx.oxml.ns import qn
        for node in d.element.body.iter(qn("w:t")):
            if node.text and "{" in node.text:
                node.text = _apply_mapping(node.text, mapping)
    except Exception as e:
        log(f"⚠️ جایگزینی تکست‌باکس: {e}")

    # 🔳 ۴) تصویرهای ضروری که جایشان در قالب نبود
    if _orphans:
        _append_orphan_images(d, _orphans, _pos)

    # 📄 ۵) 🆕 فاز ۳۵ — نگهبان تک‌صفحه‌ای
    #    گواهینامه باید **یک صفحه** بماند. اگر جایی پاراگراف
    #    خالی اضافه شده باشد (نسخه‌های قبلی، یا قالبی که ته‌اش
    #    خط خالی دارد) صفحهٔ دوم باز می‌شود و کیوآر آنجا می‌افتد.
    if get_setting("cert_one_page", "1") == "1":
        try:
            _drop_trailing_blanks(d)
        except Exception as e:
            log(f"⚠️ نگهبان تک‌صفحه: {e}")

    try:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        d.save(str(out_path))
        return str(out_path), ""
    except Exception as e:
        return None, f"ذخیره ناموفق: {user_error_message(e)}"


# 📍 جای پیش‌فرض تصویرهای شناور — درصدی از صفحه
#    (۰٬۰ = گوشهٔ بالا-چپ · ۱۰۰٬۱۰۰ = پایین-راست)
FLOAT_POS = {
    "qr":       {"x": 82, "y": 62, "anchor": "br"},
    "barcode":  {"x": 50, "y": 88, "anchor": "bc"},
    "stamp":    {"x": 20, "y": 70, "anchor": "bl"},
    "sign_img": {"x": 30, "y": 72, "anchor": "bl"},
    "logo":     {"x": 10, "y": 8,  "anchor": "tl"},
    "photo":    {"x": 85, "y": 12, "anchor": "tr"},
}

# 🎯 نام فارسی گوشه‌ها — برای پنل
ANCHOR_FA = {
    "tl": "↖️ بالا-چپ", "tc": "⬆️ بالا-وسط", "tr": "↗️ بالا-راست",
    "cl": "⬅️ وسط-چپ", "cc": "🎯 وسط", "cr": "➡️ وسط-راست",
    "bl": "↙️ پایین-چپ", "bc": "⬇️ پایین-وسط", "br": "↘️ پایین-راست",
}


def _float_cfg(key):
    """📍 موقعیت شناور یک تصویر — از پنل قابل تغییر"""
    d = FLOAT_POS.get(key, {"x": 50, "y": 50, "anchor": "cc"})
    def _n(part, dflt):
        try:
            return float(get_setting(f"cert_pos_{key}_{part}", "") or dflt)
        except (TypeError, ValueError):
            return float(dflt)
    return {"x": _n("x", d["x"]), "y": _n("y", d["y"]),
            "anchor": (get_setting(f"cert_pos_{key}_anchor", "")
                       or d["anchor"]).strip()}


def _page_mm(d):
    """📐 اندازهٔ صفحه بر حسب میلی‌متر"""
    try:
        sec = d.sections[0]
        return (int(sec.page_width) / 36000.0,
                int(sec.page_height) / 36000.0)
    except Exception:
        return 297.0, 210.0


def _drop_trailing_blanks(d):
    """
    🧹 پاراگراف‌های خالیِ ته سند را حذف می‌کند تا صفحهٔ دوم
       باز نشود.

    🎯 «برده صفحهٔ دوم»

    🔴 قالب گواهینامه دقیقاً یک صفحهٔ A4 افقی است و تا لبه پر
       شده. حتی **یک** پاراگراف خالیِ اضافه، ارتفاع خط را
       سرریز می‌کند و ورد صفحهٔ دوم می‌سازد.

    ⚠️ پاراگرافی که تصویر یا شکل دارد هرگز حذف نمی‌شود، حتی
       اگر متنش خالی باشد — وگرنه خودِ کیوآر پاک می‌شد.
    """
    from docx.oxml.ns import qn

    removed = 0
    for p in reversed(list(d.paragraphs)):
        if (p.text or "").strip():
            break
        el = p._element
        # 🛡️ محتوای غیرمتنی دارد؟ دست نزن
        if (el.find(".//" + qn("w:drawing")) is not None
                or el.find(".//" + qn("w:pict")) is not None
                or el.find(".//" + qn("w:object")) is not None
                or el.find(".//" + qn("w:br")) is not None):
            break
        parent = el.getparent()
        if parent is None:
            break
        parent.remove(el)
        removed += 1

    if removed:
        log(f"🧹 {removed} پاراگراف خالی ته سند حذف شد "
            f"(جلوگیری از صفحهٔ دوم)")
    return removed


def _first_body_paragraph(d):
    """
    📄 یک پاراگرافِ **موجود در صفحهٔ اول** برمی‌گرداند تا تصویر
       شناور به آن لنگر بیندازد.

    🎯 «کیوآرکد صادر میکنه ولی نمیزاره سرجاش، برده صفحهٔ دوم»

    🔴 چرا مهم است؟ تصویر شناور در ورد همیشه به یک پاراگراف
       لنگر می‌اندازد. اگر آن پاراگراف در صفحهٔ ۲ باشد، تصویر
       هم — با وجود مختصات مطلق — در صفحهٔ ۲ رسم می‌شود.

    ترتیب انتخاب:
      ۱) اولین پاراگرافی که تصویر دارد (پس‌زمینه — قطعاً صفحهٔ ۱)
      ۲) اولین پاراگراف غیرخالی
      ۳) اولین پاراگراف موجود
      ۴) اگر سند اصلاً پاراگراف ندارد → ناچار یکی می‌سازیم
    """
    from docx.oxml.ns import qn

    pars = list(d.paragraphs)

    # ۱) پاراگرافی که خودش تصویر دارد → مطمئن‌ترین لنگر صفحهٔ اول
    for p in pars:
        if p._element.find(".//" + qn("w:drawing")) is not None:
            return p
        if p._element.find(".//" + qn("w:pict")) is not None:
            return p

    # ۲) اولین پاراگراف غیرخالی
    for p in pars:
        if (p.text or "").strip():
            return p

    # ۳) اولین پاراگراف موجود
    if pars:
        return pars[0]

    # ۴) سند خالی — ناچار
    return d.add_paragraph()


def _strip_placeholder_text(d, key):
    """
    🧹 اگر {کیوآر} داخل تکست‌باکس بود، متنش را پاک می‌کند.

    🔴 باگ رفع‌شده (فاز ۳۵): `_place_image` فقط پاراگراف‌های
       معمولی را می‌گردد و تکست‌باکس‌ها (w:txbxContent) را
       نمی‌بیند. پس در قالب‌های حرفه‌ای که همه‌چیز داخل
       تکست‌باکس است، تصویر «یتیم» حساب می‌شد و **هم** شناور
       اضافه می‌شد **هم** نوشتهٔ خام «{کیوآر}» روی گواهینامه
       باقی می‌ماند.
    """
    from docx.oxml.ns import qn
    n = 0
    try:
        for node in d.element.body.iter(qn("w:t")):
            t = node.text or ""
            if "{" not in t:
                continue
            new = _PH_RE.sub(
                lambda m: "" if resolve_key(m.group(1)) == key
                else m.group(0), t)
            if new != t:
                node.text = new
                n += 1
    except Exception as e:
        log(f"⚠️ پاکسازی جای‌نمای {key}: {e}")
    return n


def _textbox_anchor(d, key):
    """
    🎯 اگر {کیوآر} داخل تکست‌باکس باشد، **جای دقیقی** که ادمین
       در ورد تعیین کرده را (بر حسب درصد صفحه) بیرون می‌کشد.

    🎯 «چرا نمیتونه بزاره جایی که تعیین کردم بدون بهم ریختن فرم؟»

    ادمین در ورد یک کادر می‌گذارد و داخلش می‌نویسد {کیوآر}.
    ما مختصات همان کادر را می‌خوانیم و تصویر شناور را دقیقاً
    همان‌جا می‌نشانیم — نه در گوشهٔ پیش‌فرض.

    خروجی: dict با x/y درصدی و anchor="tl" یا None
    """
    from docx.oxml.ns import qn

    pw_mm, ph_mm = _page_mm(d)
    if pw_mm <= 0 or ph_mm <= 0:
        return None

    def _pct(off_emu, size_mm):
        return max(0.0, min(100.0, (off_emu / 36000.0) / size_mm * 100.0))

    try:
        # هر شکل/تکست‌باکسی که متنش شامل این کلید است
        for anc in d.element.body.iter(qn("wp:anchor")):
            txt = "".join(t.text or "" for t in anc.iter(qn("w:t")))
            if "{" not in txt:
                continue
            if not any(resolve_key(m.group(1)) == key
                       for m in _PH_RE.finditer(txt)):
                continue
            hp = anc.find(qn("wp:positionH"))
            vp = anc.find(qn("wp:positionV"))
            if hp is None or vp is None:
                continue
            hx = hp.find(qn("wp:posOffset"))
            vy = vp.find(qn("wp:posOffset"))
            if hx is None or vy is None:
                continue
            if (hp.get("relativeFrom") or "") not in ("page", "margin",
                                                      "column", ""):
                continue
            x_emu = int((hx.text or "0").strip() or 0)
            y_emu = int((vy.text or "0").strip() or 0)

            # 📐 اندازهٔ کادر → تصویر را وسطش می‌گذاریم
            ext = anc.find(qn("wp:extent"))
            cw_mm = ch_mm = 0.0
            if ext is not None:
                try:
                    cw_mm = int(ext.get("cx") or 0) / 36000.0
                    ch_mm = int(ext.get("cy") or 0) / 36000.0
                except (TypeError, ValueError):
                    pass

            cx_mm = x_emu / 36000.0 + cw_mm / 2.0
            cy_mm = y_emu / 36000.0 + ch_mm / 2.0
            return {"x": max(0.0, min(100.0, cx_mm / pw_mm * 100.0)),
                    "y": max(0.0, min(100.0, cy_mm / ph_mm * 100.0)),
                    "anchor": "cc", "src": "textbox"}
    except Exception as e:
        log(f"⚠️ خواندن جای تکست‌باکس {key}: {e}")

    # 🅱️ حالت دوم — تکست‌باکس قدیمی VML (v:shape)
    #    قالب‌هایی که با ورد ۲۰۰۳/۲۰۰۷ یا مبدل‌های آنلاین ساخته
    #    شده‌اند از این استفاده می‌کنند. مختصات در ویژگی style
    #    به‌صورت CSS است: "position:absolute;left:520pt;top:390pt"
    try:
        # ⚠️ qn("v:shape") کار نمی‌کند — python-docx پیشوند «v»
        #    (VML) را در جدول namespace خود ثبت نکرده و
        #    KeyError می‌دهد. پس URI را مستقیم می‌نویسیم.
        _VML = "{urn:schemas-microsoft-com:vml}shape"
        for sh in d.element.body.iter(_VML):
            txt = "".join(t.text or "" for t in sh.iter(qn("w:t")))
            if "{" not in txt:
                continue
            if not any(resolve_key(m.group(1)) == key
                       for m in _PH_RE.finditer(txt)):
                continue
            style = sh.get("style") or ""
            css = {}
            for part in style.split(";"):
                if ":" in part:
                    k2, v2 = part.split(":", 1)
                    css[k2.strip().lower()] = v2.strip().lower()

            def _mm(val):
                """CSS ورد → میلی‌متر"""
                if not val:
                    return None
                try:
                    if val.endswith("pt"):
                        return float(val[:-2]) * 25.4 / 72.0
                    if val.endswith("in"):
                        return float(val[:-2]) * 25.4
                    if val.endswith("mm"):
                        return float(val[:-2])
                    if val.endswith("cm"):
                        return float(val[:-2]) * 10.0
                    if val.endswith("px"):
                        return float(val[:-2]) * 25.4 / 96.0
                    return float(val) * 25.4 / 72.0     # بدون واحد = pt
                except (TypeError, ValueError):
                    return None

            lx, ty = _mm(css.get("left")), _mm(css.get("top"))
            if lx is None or ty is None:
                continue
            wd = _mm(css.get("width")) or 0.0
            ht = _mm(css.get("height")) or 0.0
            return {"x": max(0.0, min(100.0,
                                      (lx + wd / 2) / pw_mm * 100.0)),
                    "y": max(0.0, min(100.0,
                                      (ty + ht / 2) / ph_mm * 100.0)),
                    "anchor": "cc", "src": "vml"}
    except Exception as e:
        log(f"⚠️ خواندن جای کادر VML {key}: {e}")

    return None


def _add_floating_image(d, key, img_path, cfg=None):
    """
    🎈 تصویر را **شناور و روی همه‌چیز** می‌گذارد.

    🎯 «کیوآر کد رو میسازه ولی اونجا که باید قرار نمیده،
        میندازه پشت بکگراند گواهینامه»

    🔴 چرا پاراگراف معمولی جواب نمی‌داد؟
       قالب‌های حرفه‌ای یک تصویر پس‌زمینهٔ تمام‌صفحه دارند که
       خودش شناور است. هر تصویری که با پاراگراف اضافه شود در
       «لایهٔ متن» می‌نشیند — یعنی **زیر** پس‌زمینه. در PDF
       خروجی دیدیم که اصلاً فراخوانی نمی‌شد.

    ✅ راه درست: لنگر شناور (anchor) با:
         • مختصات مطلق نسبت به صفحه
         • behindDoc="0"  → جلوی همه‌چیز
         • relativeFrom="page" → مستقل از متن و حاشیه
    """
    from docx.shared import Mm, Emu
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    import copy as _cp

    size_mm = image_mm(key)

    # 🎯 اولویت ۱: جایی که ادمین خودش در ورد تعیین کرده
    #    (کادر/تکست‌باکسی که داخلش {کیوآر} نوشته)
    #    اولویت ۲: تنظیم دستی پنل  ·  اولویت ۳: پیش‌فرض
    # 🔴 باگ ترتیبی رفع‌شده (فاز ۳۵):
    #    جای کادر **باید قبل از جایگزینی متن‌ها** خوانده شود.
    #    مرحلهٔ ۲ و ۳ در fill_docx همهٔ {پارامتر}ها را پاک
    #    می‌کنند؛ اگر اینجا تازه بگردیم، دیگر «{کیوآر}» وجود
    #    ندارد و بی‌صدا به گوشهٔ پیش‌فرض برمی‌گشتیم.
    #    پس fill_docx مختصات را زودتر می‌گیرد و به ما می‌دهد.
    if cfg is None and get_setting("cert_pos_from_tpl", "1") == "1":
        cfg = _textbox_anchor(d, key)
    if cfg:
        log(f"🎯 جای {key} از خود قالب: "
            f"{cfg['x']:.0f}٪،{cfg['y']:.0f}٪")
        _strip_placeholder_text(d, key)
    else:
        cfg = _float_cfg(key)
    pw, ph = _page_mm(d)

    # 📐 اندازهٔ واقعی تصویر برای حفظ نسبت
    try:
        from PIL import Image as _I
        with _I.open(img_path) as _im:
            ratio = _im.height / max(1, _im.width)
    except Exception:
        ratio = 1.0
    w_mm = size_mm
    h_mm = size_mm * ratio

    # 📍 مختصات گوشهٔ بالا-چپ تصویر
    cx = pw * cfg["x"] / 100.0
    cy = ph * cfg["y"] / 100.0
    a = cfg["anchor"]
    if a[1:2] == "c":
        cx -= w_mm / 2
    elif a[1:2] == "r":
        cx -= w_mm
    if a[0:1] == "c":
        cy -= h_mm / 2
    elif a[0:1] == "b":
        cy -= h_mm

    # 🛡️ داخل صفحه بماند
    cx = max(0.0, min(cx, pw - w_mm))
    cy = max(0.0, min(cy, ph - h_mm))

    # 1️⃣ اول تصویر را عادی درج کن تا رابطه (rId) ساخته شود
    #
    # 🔴 باگ رفع‌شده (فاز ۳۵) — «کیوآر رو میبره صفحهٔ دوم»:
    #    قبلاً اینجا `d.add_paragraph()` بود؛ یعنی یک پاراگرافِ
    #    تازه **ته سند** ساخته می‌شد. قالب گواهینامه دقیقاً یک
    #    صفحه است و تا آخرین میلی‌متر پر شده، پس هر پاراگراف
    #    اضافه سرریز می‌کرد و ورد/لیبره **صفحهٔ دوم** باز می‌کرد.
    #    تصویر شناور هم چون لنگرش در آن پاراگراف بود، با آن به
    #    صفحهٔ دوم می‌رفت — همان چیزی که در PDF دیدیم:
    #      صفحهٔ ۱ → Im4 (پس‌زمینه) · Im7 · Im8
    #      صفحهٔ ۲ → Im20 (کیوآر) تنها
    #
    # ✅ راه درست: تصویرِ شناور باید به یکی از پاراگراف‌های
    #    **موجودِ صفحهٔ اول** لنگر بیندازد. تصویر شناور ارتفاع
    #    اشغال نمی‌کند، پس هیچ چیزی جابه‌جا نمی‌شود و «فرم به هم
    #    نمی‌ریزد» — مختصاتش هم مطلق و نسبت به صفحه است.
    host = _first_body_paragraph(d)
    run = host.add_run()
    run.add_picture(str(img_path), width=Mm(w_mm))
    inline = run._element.find(qn("wp:inline") if False else
                               ".//" + qn("wp:inline"))
    if inline is None:
        # ساختار غیرمنتظره — همان درج عادی می‌ماند
        return True

    # 2️⃣ inline را به anchor شناور تبدیل کن
    anchor = OxmlElement("wp:anchor")
    for k, v in {
        "distT": "0", "distB": "0", "distL": "0", "distR": "0",
        # 🔴 hash() پایتون بین اجراها عوض می‌شود (PYTHONHASHSEED)
        #    → لایهٔ تصویر هر بار فرق می‌کرد. قطعی‌اش کردیم.
        "simplePos": "0",
        "relativeHeight": str(251650000 + (sum(map(ord, key)) % 1000)),
        "behindDoc": "0",          # 🔑 جلوی همه‌چیز، نه پشت
        "locked": "0", "layoutInCell": "1", "allowOverlap": "1",
    }.items():
        anchor.set(k, v)

    sp = OxmlElement("wp:simplePos")
    sp.set("x", "0")
    sp.set("y", "0")
    anchor.append(sp)

    hp = OxmlElement("wp:positionH")
    hp.set("relativeFrom", "page")        # 🔑 نسبت به خودِ صفحه
    off = OxmlElement("wp:posOffset")
    off.text = str(int(Emu(Mm(cx))))
    hp.append(off)
    anchor.append(hp)

    vp = OxmlElement("wp:positionV")
    vp.set("relativeFrom", "page")
    off = OxmlElement("wp:posOffset")
    off.text = str(int(Emu(Mm(cy))))
    vp.append(off)
    anchor.append(vp)

    # 📐 ترتیب عناصر طبق استاندارد OOXML — اجباری است
    #
    # 🔴 باگ رفع‌شده: قبلاً wrapNone را با insert(3) قبل از
    #    extent می‌گذاشتم. Word گذشت می‌کند ولی LibreOffice
    #    سخت‌گیر است و **کل تصویر را نادیده می‌گیرد** — در PDF
    #    خروجی، Im20 در فایل بود ولی هرگز رسم نمی‌شد.
    #
    #    ترتیب درست:
    #      simplePos → positionH → positionV → extent →
    #      effectExtent → wrapNone → docPr → cNvGraphicFramePr
    #      → a:graphic
    for tag in ("wp:extent", "wp:effectExtent"):
        el = inline.find(qn(tag))
        if el is not None:
            anchor.append(_cp.deepcopy(el))

    anchor.append(OxmlElement("wp:wrapNone"))   # بدون دورگیری

    for tag in ("wp:docPr", "wp:cNvGraphicFramePr", "a:graphic"):
        el = inline.find(qn(tag))
        if el is not None:
            anchor.append(_cp.deepcopy(el))

    drawing = inline.getparent()
    drawing.remove(inline)
    drawing.append(anchor)
    return True


def _fit_background(d):
    """
    📐 تصویر پس‌زمینهٔ تمام‌صفحه را دقیقاً روی صفحه می‌نشاند.

    🎯 «همچنان صفحه سفید بالا بک گراند وجود داره»

    🔴 ریشهٔ مشکل — از روی PDF واقعی کاربر پیدا شد:
         صفحه:     ۸۴۱.۹ × ۵۹۵.۳ pt
         پس‌زمینه: ۸۴۰.۹ × ۵۹۴.۰ در y = −۲۱.۰

       یعنی طرح ۲۱ پوینت پایین‌تر از کف نشسته بود و بالای
       صفحه ۲۲ پوینت (۸ میلی‌متر) سفید می‌ماند.

    ✅ راه‌حل: هر تصویر شناوری که ≥ ۸۰٪ صفحه را می‌پوشاند،
       پس‌زمینه حساب می‌شود و دقیقاً روی (۰،۰) تا (عرض،ارتفاع)
       کشیده می‌شود.
    """
    from docx.shared import Mm, Emu
    from docx.oxml.ns import qn

    pw_mm, ph_mm = _page_mm(d)
    pw_emu, ph_emu = int(Emu(Mm(pw_mm))), int(Emu(Mm(ph_mm)))
    fixed = 0

    def _resize(el):
        """اندازهٔ extent و a:ext را دقیقاً صفحه کن"""
        el.set("cx", str(pw_emu))
        el.set("cy", str(ph_emu))

    # ── حالت ۱: تصویر شناور (wp:anchor) ──
    for anc in list(d.element.body.iter(qn("wp:anchor"))):
        ext = anc.find(qn("wp:extent"))
        if ext is None:
            continue
        try:
            cx, cy = int(ext.get("cx") or 0), int(ext.get("cy") or 0)
        except (TypeError, ValueError):
            continue
        if not cx or not cy:
            continue
        if cx < pw_emu * 0.80 or cy < ph_emu * 0.80:
            continue

        _resize(ext)
        for e2 in anc.iter(qn("a:ext")):
            _resize(e2)

        for tag in ("wp:positionH", "wp:positionV"):
            pos = anc.find(qn(tag))
            if pos is None:
                continue
            pos.set("relativeFrom", "page")
            for child in list(pos):
                pos.remove(child)
            off = pos.makeelement(qn("wp:posOffset"), {})
            off.text = "0"
            pos.append(off)

        anc.set("behindDoc", "1")
        fixed += 1

    # ── حالت ۲: تصویر درون‌خطی (wp:inline) ──
    #    🔴 قالب‌های واقعی معمولاً همین‌اند: یک تصویر بزرگ در
    #       پاراگراف اول. اگر کمی کوچک‌تر از صفحه باشد، نوار
    #       سفید می‌ماند. اینجا فقط اندازه‌اش را دقیق می‌کنیم
    #       و حاشیهٔ صفحه را صفر تا لبه‌به‌لبه بنشیند.
    for inl in list(d.element.body.iter(qn("wp:inline"))):
        ext = inl.find(qn("wp:extent"))
        if ext is None:
            continue
        try:
            cx, cy = int(ext.get("cx") or 0), int(ext.get("cy") or 0)
        except (TypeError, ValueError):
            continue
        if not cx or not cy:
            continue
        if cx < pw_emu * 0.80 or cy < ph_emu * 0.80:
            continue

        _resize(ext)
        for e2 in inl.iter(qn("a:ext")):
            _resize(e2)
        fixed += 1

        # حاشیهٔ صفحه را صفر کن تا تصویر جا شود
        try:
            for sec in d.sections:
                sec.left_margin = sec.right_margin = Mm(0)
                sec.top_margin = sec.bottom_margin = Mm(0)
        except Exception:
            pass

    if fixed:
        log(f"📐 {fixed} پس‌زمینه روی صفحه تنظیم شد "
            f"({pw_mm:.0f}×{ph_mm:.0f}mm)")
    return fixed


def _append_orphan_images(d, orphans, positions=None):
    """
    🔳 تصویرهای ضروری را که جایشان در قالب نبود، شناور می‌گذارد.

    🎯 «یه کاری کن اون قشنگ بیفته اونجا که تعیین شده و نره
        بیفته پشت»

    به‌جای پاراگراف ته سند (که زیر پس‌زمینه گم می‌شد)، حالا
    با مختصات دقیق و روی همهٔ لایه‌ها می‌نشیند.
    """
    positions = positions or {}
    for key, path in orphans:
        try:
            c = positions.get(key)
            _add_floating_image(d, key, path, cfg=c)
            c = c or _float_cfg(key)
            log(f"🎈 {key} شناور در {c['x']:.0f}٪،{c['y']:.0f}٪ "
                f"({ANCHOR_FA.get(c['anchor'], c['anchor'])})")
        except Exception as e:
            log(f"⚠️ جاگذاری شناور {key}: {e} — تلاش با روش ساده")
            try:
                from docx.shared import Mm
                from docx.enum.text import WD_ALIGN_PARAGRAPH
                p = d.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.add_run().add_picture(str(path),
                                        width=Mm(image_mm(key)))
            except Exception as e2:
                log(f"⚠️ افزودن {key}: {e2}")


def image_mm(key):
    """📐 اندازه یک تصویر — از پنل ادمین قابل تغییر"""
    dflt = IMAGE_MM.get(key, 30)
    try:
        return float(get_setting(f"cert_mm_{key}", "") or dflt)
    except (TypeError, ValueError):
        return float(dflt)


def _place_image(d, key, img_path):
    """
    🖼️ جاگذاری یک تصویر (QR، امضا، مهر، لوگو، عکس، …)

    دو روش — هر دو پشتیبانی می‌شود:
      ۱) پاراگرافی که {نام پارامتر} دارد → تصویر جایش می‌نشیند
      ۲) تصویر پلیس‌هولدر که نام فایلش شامل کلید است
         (اندازه و جای دقیق ورد حفظ می‌شود)
    """
    from docx.shared import Mm
    size = image_mm(key)

    # روش ۱ — run ای که پارامتر در آن است
    #
    # 🔴 باگ رفع‌شده: قبلاً کل پاراگراف پاک می‌شد. اگر چند تصویر در
    #    یک خط بودند («{امضا} {امضا دوم} {مهر}»)، اولی بقیه را
    #    نابود می‌کرد و فقط یک تصویر درج می‌شد.
    #    حالا فقط همان run دست می‌خورد و بقیه پارامترها سالم می‌مانند.
    for p in _all_paragraphs(d):
        raw = "".join(r.text or "" for r in p.runs)
        if not raw or "{" not in raw:
            continue
        if not any(resolve_key(m.group(1)) == key
                   for m in _PH_RE.finditer(raw)):
            continue

        # ابتدا سعی کن run دقیقی که پارامتر کامل در آن است پیدا شود
        for r in p.runs:
            t = r.text or ""
            if "{" not in t:
                continue
            hit_here = any(resolve_key(m.group(1)) == key
                           for m in _PH_RE.finditer(t))
            if not hit_here:
                continue
            rest = _PH_RE.sub(
                lambda m: "" if resolve_key(m.group(1)) == key
                else m.group(0), t)
            # 🔴 تصویر را در run تازه می‌گذاریم، نه همان run.
            #    اگر روی همان run بنویسیم، تصویری که قبلاً درج شده
            #    (مثلاً {لوگو}) پاک می‌شود و فقط آخری می‌ماند.
            try:
                new_r = copy.deepcopy(r._element)
                r._element.addnext(new_r)
                from docx.text.run import Run
                holder = Run(new_r, p)
                holder.text = ""
                holder.add_picture(str(img_path), width=Mm(size))
                r.text = rest
                return True
            except Exception as e:
                log(f"⚠️ درج تصویر {key}: {e}")
                return False

        # پارامتر بین چند run شکسته → متن را یکجا کن و جای آن تصویر بگذار
        rest = _PH_RE.sub(
            lambda m: "" if resolve_key(m.group(1)) == key else m.group(0),
            raw)
        try:
            first = p.runs[0]
            for r in p.runs[1:]:
                r.text = ""
            new_r = copy.deepcopy(first._element)
            first._element.addnext(new_r)
            from docx.text.run import Run
            holder = Run(new_r, p)
            holder.text = ""
            holder.add_picture(str(img_path), width=Mm(size))
            first.text = rest
            return True
        except Exception as e:
            log(f"⚠️ درج تصویر {key}: {e}")
            return False

    # روش ۲ — جایگزینی تصویر پلیس‌هولدر
    try:
        if _swap_placeholder_image(d, img_path, key):
            return True
    except Exception as e:
        log(f"⚠️ جایگزینی تصویر {key}: {e}")

    # روش ۳ — 🆕 فاز ۳۵: پارامتر داخل تکست‌باکس
    #
    # 🔴 باگ رفع‌شده: قالب‌های حرفهٔ گواهینامه همه‌چیز را داخل
    #    تکست‌باکس می‌گذارند. روش ۱ فقط `d.paragraphs` را
    #    می‌گردد و تکست‌باکس‌ها آنجا نیستند، پس {کیوآر} هرگز
    #    پیدا نمی‌شد → تصویر «یتیم» می‌شد و ته سند می‌افتاد
    #    (که خودش صفحهٔ دوم می‌ساخت).
    #
    #    اینجا فقط خبر می‌دهیم که «جایش هست»؛ خودِ درج را
    #    `_add_floating_image` با مختصات دقیق همان کادر
    #    انجام می‌دهد — چون داخل تکست‌باکس نمی‌شود drawing
    #    درج کرد (ورد فایل را خراب اعلام می‌کند).
    try:
        if _textbox_anchor(d, key):
            log(f"📦 جای {{{ph_label(key)}}} داخل کادر قالب پیدا شد")
            return False
    except Exception as e:
        log(f"⚠️ بررسی کادر {key}: {e}")
    return False


def _all_paragraphs(d):
    """همه پاراگراف‌های سند، شامل جدول‌ها"""
    for p in d.paragraphs:
        yield p
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    yield p
    for sec in d.sections:
        for part in (sec.header, sec.footer):
            if part:
                for p in part.paragraphs:
                    yield p


# نام‌هایی که در فایل تصویر ورد دنبالشان می‌گردیم
_IMG_HINTS = {
    "qr": ("qr",),
    "barcode": ("barcode", "bcode"),
    "sign_img": ("sign", "signature", "emza", "emzaa"),
    "sign_img2": ("sign2", "signature2", "emza2"),
    "sign_img3": ("sign3", "signature3", "emza3"),
    "logo": ("logo", "arm"),
    "logo2": ("logo2", "arm2"),
    "logo3": ("logo3", "arm3"),
    "stamp": ("stamp", "seal", "mohr"),
    "badge": ("badge", "medal", "neshan"),
    "photo": ("photo", "avatar", "aks"),
    "watermark": ("watermark", "wm"),
}


def _trim_border(im, bg_tol=28):
    """
    ✂️ حاشیهٔ یکدست دور تصویر را می‌برد.

    🔴 چرا لازم است؟ کاربر معمولاً QR را وسط یک بوم سفید بزرگ
       می‌گذارد یا اسکرین‌شات با حاشیه می‌فرستد. آن‌وقت نسبت
       تیرگی کل تصویر خیلی کم می‌شود (dark=0.01) و ربات فکر
       می‌کند این QR نیست. حالا اول حاشیه را می‌بریم و بعد
       فقط خودِ نقش را تحلیل می‌کنیم.
    """
    try:
        from PIL import Image, ImageChops
        w, h = im.size
        if w < 8 or h < 8:
            return im
        # رنگ گوشه‌ها = رنگ پس‌زمینه
        corners = [im.getpixel((0, 0)), im.getpixel((w - 1, 0)),
                   im.getpixel((0, h - 1)), im.getpixel((w - 1, h - 1))]
        bg = max(set(corners), key=corners.count)
        bgim = Image.new("RGB", im.size, bg)
        diff = ImageChops.difference(im, bgim).convert("L")
        box = diff.point(lambda p: 255 if p > bg_tol else 0).getbbox()
        if not box:
            return im
        x0, y0, x1, y1 = box
        if (x1 - x0) < 8 or (y1 - y0) < 8:
            return im
        # اگر تقریباً چیزی بریده نشد، همان اصل را برگردان
        if (x1 - x0) > w * 0.94 and (y1 - y0) > h * 0.94:
            return im
        return im.crop(box)
    except Exception:
        return im


def _image_fingerprint(blob, trim=True):
    """
    🔬 تحلیل محتوای یک تصویر — برای تشخیص خودکار نوعش.

    🔴 چرا لازم است؟ ورد نام اصلی فایل را دور می‌ریزد!
       عکسی که شما «my_qr.png» گذاشته‌اید، داخل فایل ورد
       «image2.png» می‌شود. پس تشخیص با نام غیرممکن است و
       باید از روی خودِ تصویر بفهمیم چیست.

    🆕 فاز ۲۴: حاشیه بریده می‌شود و «دورنگ بودن» هم سنجیده
       می‌شود تا QR رنگی هم شناخته شود.
    """
    try:
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(blob)).convert("RGB")
        w0, h0 = im.size
        if trim:
            im = _trim_border(im)
        w, h = im.size
        sm = im.resize((32, 32))
        px = list(sm.getdata())
        n = max(1, len(px))
        dark = sum(1 for r, g, b in px if r < 80 and g < 80 and b < 80) / n
        light = sum(1 for r, g, b in px
                    if r > 200 and g > 200 and b > 200) / n
        gray = sum(1 for r, g, b in px
                   if abs(r - g) < 25 and abs(g - b) < 25) / n

        # 🎨 «دورنگ» بودن — QR رنگی هم فقط دو رنگ دارد:
        #    یک رنگ روشن (زمینه) و یک رنگ تیره‌تر (نقش)
        lum = [(0.299 * r + 0.587 * g + 0.114 * b) for r, g, b in px]
        thr = (max(lum) + min(lum)) / 2 if lum else 128
        lo = [v for v in lum if v <= thr]
        hi = [v for v in lum if v > thr]
        two_tone = 0.0
        ink = 0.0
        if lo and hi:
            spread_lo = (max(lo) - min(lo)) / 255
            spread_hi = (max(hi) - min(hi)) / 255
            # هرچه دو خوشه فشرده‌تر، دورنگ‌تر
            two_tone = max(0.0, 1.0 - (spread_lo + spread_hi) / 2)
            ink = len(lo) / n          # نسبت بخش تیره‌تر

        # 🔲 چگالی لبه — QR پر از تغییر سیاه/سفید است
        edges = 0
        for y in range(32):
            row = lum[y * 32:(y + 1) * 32]
            for x in range(31):
                if abs(row[x] - row[x + 1]) > 60:
                    edges += 1
        edge_ratio = edges / (32 * 31)

        return {"w": w, "h": h, "ar": w / max(1, h),
                "dark": dark, "light": light, "gray": gray,
                "two_tone": two_tone, "ink": ink,
                "edges": edge_ratio, "w0": w0, "h0": h0}
    except Exception:
        return None


def looks_like_qr(blob):
    """
    🔳 آیا این تصویر یک کیوآرکد است؟

    🎯 «کیوآر کد رو به صورت تصویری میزارم تو ورد تشخیص نمیده»

    🔴 نسخهٔ قبل فقط QR سیاه‌وسفیدِ بدون حاشیه را می‌شناخت.
       این‌ها رد می‌شدند:
         • QR رنگی (آبی/سبز)      → gray پایین بود
         • QR کوچک وسط بوم بزرگ   → dark خیلی کم می‌شد
         • QR با قاب و حاشیه       → نسبت ابعاد به‌هم می‌ریخت

       حالا: اول حاشیه بریده می‌شود، بعد «دورنگ بودن» و
       «چگالی لبه» سنجیده می‌شود — نه فقط سیاه‌وسفید بودن.
    """
    f = _image_fingerprint(blob)
    if not f:
        return False

    # تقریباً مربع (با کمی رواداری برای قاب)
    if not (0.72 <= f["ar"] <= 1.38):
        return False
    # نقش باید سهم معقولی داشته باشد
    if not (0.06 <= f["ink"] <= 0.80):
        return False
    # QR پر از لبه است — عکس و لوگو این‌قدر لبه ندارند
    if f["edges"] < 0.06:
        return False

    # مسیر ۱ — QR کلاسیک سیاه‌وسفید
    classic = (f["gray"] > 0.80 and 0.08 < f["dark"] < 0.80
               and f["light"] > 0.15)
    # مسیر ۲ — QR رنگی: دورنگ + پر لبه
    #    آستانه سخاوتمند است چون خطای «تشخیص ندادن» آزاردهنده‌تر
    #    از خطای «تشخیص اشتباه» است — عکس‌های واقعی به‌خاطر
    #    شرط edges و ink از قبل رد شده‌اند.
    colored = f["two_tone"] > 0.40 and f["edges"] > 0.18
    return bool(classic or colored)


def find_qr_placeholder(d):
    """
    🔍 پیدا کردن تصویر نمونه کیوآرکد داخل قالب ورد.

    🎯 «یه عکس کیوآرکد خودم میزارم تو فایل برا نمونه، ربات تشخیص
        نمیده تا دقیق کیوآرکد رو رو اون بزنه»

    اولویت:
      ۱) نام فایل شامل qr (اگر ورد نگه داشته باشد)
      ۲) تحلیل محتوا — تصویر مربعی سیاه‌وسفید
    """
    cands = []
    for rel in list(d.part.rels.values()):
        if "image" not in rel.reltype:
            continue
        tgt = str(getattr(rel, "target_ref", "")).lower()
        try:
            blob = rel.target_part.blob
        except Exception:
            continue
        if "qr" in tgt:
            return rel                      # اسمش گویاست
        if looks_like_qr(blob):
            cands.append(rel)
    return cands[0] if len(cands) == 1 else (cands[0] if cands else None)


def _swap_placeholder_image(d, img_path, key="qr"):
    """
    🖼️ تصویر پلیس‌هولدر را با تصویر واقعی عوض می‌کند.

    ادمین در ورد یک تصویر می‌گذارد که نام فایلش مثلاً sign.png است؛
    ربات محتوایش را عوض می‌کند و **اندازه و جای دقیق حفظ می‌شود**.

    ⚠️ برای کلیدهای شماره‌دار (logo2) اول دقیق می‌گردیم بعد کلی،
       وگرنه logo2 اشتباهاً روی logo می‌نشست.
    """
    data = Path(img_path).read_bytes()
    hints = _IMG_HINTS.get(key, (key,))

    # 🔳 برای QR: اگر با نام پیدا نشد، از روی محتوا تشخیص بده
    if key == "qr":
        rel = find_qr_placeholder(d)
        if rel is not None:
            try:
                rel.target_part._blob = data
                log("🔳 تصویر نمونه کیوآرکد در قالب پیدا و جایگزین شد")
                return True
            except Exception as e:
                log(f"⚠️ جایگزینی تصویر QR: {e}")

    def _try(exact):
        done = False
        for rel in list(d.part.rels.values()):
            if "image" not in rel.reltype:
                continue
            tgt = str(getattr(rel, "target_ref", "")).lower()
            base = tgt.rsplit("/", 1)[-1]
            ok = (any(base.startswith(h) for h in hints) if exact
                  else any(h in base for h in hints))
            if ok:
                try:
                    rel.target_part._blob = data
                    done = True
                except Exception:
                    pass
        return done

    return _try(True) or _try(False)


# ══════════════════════════════════════════════════════════
# 🖨️ تبدیل به PDF و PNG
# ══════════════════════════════════════════════════════════
_LO_BIN = None
_LO_AT = 0.0            # ⏱️ کِی آخرین‌بار گشتیم
_LO_TTL = 90            # ثانیه — بعدش دوباره می‌گردیم
_LO_WHY = []            # 📋 گزارش «کجاها را گشتم» برای پنل


def _lo_exe_names():
    """نام فایل اجرایی بسته به سیستم‌عامل"""
    if os.name == "nt":
        return ("soffice.exe", "soffice.com", "soffice.bin")
    return ("soffice", "libreoffice", "soffice.bin", "libreoffice7.6",
            "libreoffice7.5", "libreoffice24.2", "libreoffice25.2")


def _lo_from_registry():
    """
    🪟 مطمئن‌ترین راه روی ویندوز — رجیستری.

    🔴 چرا لازم است؟ نصب‌کنندهٔ رسمی LibreOffice خودش را به PATH
       اضافه نمی‌کند. کاربر می‌گوید «نصب دارم» و راست می‌گوید،
       ولی `shutil.which("soffice")` هیچ‌وقت پیدایش نمی‌کند.
       رجیستری همیشه مسیر واقعی نصب را دارد — حتی روی درایو E:.
    """
    if os.name != "nt":
        return []
    found = []
    try:
        import winreg
    except ImportError:
        return []

    # (کلید ریشه, مسیر, نام مقدار, نوع)
    spots = [
        (r"SOFTWARE\LibreOffice\UNO\InstallPath", None),
        (r"SOFTWARE\LibreOffice\LibreOffice", None),
        (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
         r"\soffice.exe", None),
        (r"SOFTWARE\Classes\LibreOffice.WriterDocument.1\shell\open"
         r"\command", None),
    ]
    import winreg as _wr
    roots = [_wr.HKEY_LOCAL_MACHINE, _wr.HKEY_CURRENT_USER]
    views = [0]
    for flag in (getattr(_wr, "KEY_WOW64_64KEY", 0),
                 getattr(_wr, "KEY_WOW64_32KEY", 0)):
        if flag:
            views.append(flag)

    for root in roots:
        for view in views:
            for path, _ in spots:
                try:
                    with _wr.OpenKey(root, path, 0,
                                     _wr.KEY_READ | view) as k:
                        val, _t = _wr.QueryValueEx(k, "")
                except OSError:
                    continue
                except Exception:
                    continue
                if not val:
                    continue
                v = str(val).strip().strip('"')
                # اگر خط فرمان بود، فقط قسمت exe را بردار
                if ".exe" in v.lower():
                    v = v[:v.lower().index(".exe") + 4].strip('"')
                p = Path(v)
                if p.is_dir():
                    for nm in _lo_exe_names():
                        if (p / nm).exists():
                            found.append(str(p / nm))
                        if (p / "program" / nm).exists():
                            found.append(str(p / "program" / nm))
                elif p.exists():
                    found.append(str(p))

            # نسخه‌های ثبت‌شده زیر SOFTWARE\LibreOffice
            try:
                with _wr.OpenKey(root, r"SOFTWARE\LibreOffice", 0,
                                 _wr.KEY_READ | view) as k:
                    n = _wr.QueryInfoKey(k)[0]
                    for idx in range(n):
                        try:
                            sub = _wr.EnumKey(k, idx)
                            with _wr.OpenKey(k, sub) as k2:
                                val, _t = _wr.QueryValueEx(k2, "Path")
                            p = Path(str(val).strip().strip('"'))
                            if p.exists():
                                found.append(str(p))
                        except Exception:
                            continue
            except Exception:
                pass
    return found


def _lo_candidates():
    """📂 همهٔ جاهایی که ممکن است LibreOffice آنجا باشد"""
    import glob as _g
    cands = []

    # 1️⃣ مسیر دستی ادمین — بالاترین اولویت
    manual = (get_setting("cert_soffice_path", "") or "").strip().strip('"')
    if manual:
        mp = Path(manual)
        if mp.is_dir():                      # پوشه داد نه فایل
            for nm in _lo_exe_names():
                cands += [str(mp / nm), str(mp / "program" / nm)]
        else:
            cands.append(manual)

    # 2️⃣ متغیر محیطی
    env = (os.environ.get("SOFFICE_PATH") or "").strip().strip('"')
    if env:
        cands.append(env)

    # 3️⃣ PATH
    for nm in _lo_exe_names():
        p = shutil.which(nm)
        if p:
            cands.append(p)

    if os.name == "nt":
        # 4️⃣ رجیستری — مهم‌ترین منبع روی ویندوز
        cands += _lo_from_registry()

        # 5️⃣ همهٔ درایوها × الگوهای رایج
        #    🎯 کاربر ربات را روی E:\nora_bot دارد — بعید نیست
        #       لیبره را هم روی درایو دیگری نصب کرده باشد.
        pats = [
            r"{d}:\Program Files\LibreOffice\program\soffice.exe",
            r"{d}:\Program Files (x86)\LibreOffice\program\soffice.exe",
            r"{d}:\LibreOffice\program\soffice.exe",
            r"{d}:\Program Files\LibreOffice *\program\soffice.exe",
        ]
        drives = []
        for d in "CDEFGHIJKLMNOPQRSTUVWXYZAB":
            try:
                if Path(f"{d}:\\").exists():
                    drives.append(d)
            except Exception:
                continue
        for d in drives[:8]:                 # حداکثر ۸ درایو — سرعت
            for pat in pats:
                s = pat.format(d=d)
                if "*" in s:
                    try:
                        cands += _g.glob(s)
                    except Exception:
                        pass
                else:
                    cands.append(s)

        # 6️⃣ نصب کاربری (بدون ادمین)
        for base in (os.environ.get("LOCALAPPDATA"),
                     os.environ.get("PROGRAMFILES"),
                     os.environ.get("PROGRAMFILES(X86)"),
                     os.environ.get("PROGRAMW6432")):
            if base:
                cands.append(str(Path(base) / "LibreOffice" / "program"
                                 / "soffice.exe"))
        # 7️⃣ نسخهٔ پرتابل کنار خود ربات
        try:
            here = Path(__file__).parent
            for sub in ("LibreOffice", "libreoffice", "lo",
                        "LibreOfficePortable"):
                cands.append(str(here / sub / "program" / "soffice.exe"))
                cands.append(str(here / sub / "App" / "libreoffice"
                                 / "program" / "soffice.exe"))
        except Exception:
            pass
    else:
        cands += [
            "/usr/bin/soffice", "/usr/bin/libreoffice",
            "/usr/lib/libreoffice/program/soffice",
            "/usr/local/bin/soffice", "/opt/libreoffice/program/soffice",
            "/snap/bin/libreoffice",
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        ]
        try:
            cands += _g.glob("/opt/libreoffice*/program/soffice")
        except Exception:
            pass

    # یکتاسازی با حفظ ترتیب
    seen, out = set(), []
    for c in cands:
        c = str(c).strip()
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def libreoffice_bin(force=False):
    """
    🔍 مسیر LibreOffice — اگر نصب باشد.

    🔴 باگی که کاربر گزارش کرد: «لیبره نصب دارم ولی بات می‌گه نصب نیست»

       سه علت داشت و هر سه رفع شد:
         ۱) نتیجهٔ منفی برای همیشه کش می‌شد — اگر ربات قبل از نصب
            لیبره بالا آمده بود، تا ری‌استارت می‌گفت «نصب نیست».
            حالا کش فقط ۹۰ ثانیه عمر دارد و دکمهٔ «بررسی دوباره»
            آن را فوراً پاک می‌کند.
         ۲) فقط PATH و سه مسیر ثابت گشته می‌شد. نصب‌کنندهٔ رسمی
            LibreOffice خودش را به PATH اضافه نمی‌کند! حالا
            رجیستری ویندوز + همهٔ درایوها + نصب کاربری هم گشته
            می‌شود.
         ۳) فایل پیداشده تست نمی‌شد. حالا واقعاً اجرا می‌شود
            (--version) تا مطمئن شویم سالم است.
    """
    global _LO_BIN, _LO_AT, _LO_WHY
    now = time.time()
    if force:
        _LO_BIN, _LO_AT = None, 0.0
    # کش مثبت: تا وقتی فایل هست معتبر
    if _LO_BIN:
        try:
            if Path(_LO_BIN).exists():
                return _LO_BIN
        except Exception:
            pass
        _LO_BIN = None
    # کش منفی: فقط ۹۰ ثانیه
    if _LO_BIN == "" and (now - _LO_AT) < _LO_TTL:
        return None

    _LO_WHY = []
    for p in _lo_candidates():
        try:
            if not Path(p).exists():
                continue
        except Exception:
            continue
        _LO_WHY.append(p)
        if _lo_works(p):
            _LO_BIN, _LO_AT = p, now
            log(f"✅ LibreOffice پیدا شد: {p}")
            return p
    _LO_BIN, _LO_AT = "", now
    return None


def _lo_works(path):
    """
    ✅ واقعاً اجرا می‌شود؟

    🎯 صرفِ وجود فایل کافی نیست — نصب ناقص یا میان‌بر شکسته
       باعث می‌شود تبدیل وسط کار بترکد. یک‌بار --version می‌گیریم.
    """
    try:
        r = subprocess.run([path, "--version"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=25,
                           creationflags=_no_window())
        out = (r.stdout or b"") + (r.stderr or b"")
        return b"LibreOffice" in out or b"OpenOffice" in out or r.returncode == 0
    except subprocess.TimeoutExpired:
        # کند است ولی هست — قبولش می‌کنیم
        return True
    except Exception:
        return False


def _no_window():
    """🪟 پنجرهٔ سیاه کنسول باز نشود (فقط ویندوز)"""
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def lo_diagnose():
    """
    🩺 گزارش دقیق «چرا پیدا نشد» — برای پنل ادمین.

    🎯 کاربر گفت «نصب دارم ولی می‌گه نصب نیست». به‌جای اینکه
       فقط بگوییم نه، نشان می‌دهیم کجاها را گشتیم.
    """
    lo = libreoffice_bin(force=True)
    cands = _lo_candidates()
    existing = []
    for p in cands:
        try:
            if Path(p).exists():
                existing.append(p)
        except Exception:
            continue

    return {
        "found": bool(lo),
        "path": lo or "",
        "manual": (get_setting("cert_soffice_path", "") or "").strip(),
        "checked": len(cands),
        "existing": existing,
        "on_path": bool(shutil.which("soffice") or
                        shutil.which("soffice.exe") or
                        shutil.which("libreoffice")),
        "registry": _lo_from_registry() if os.name == "nt" else [],
    }


def _profile_uri(d):
    """
    📁 مسیر پروفایل موقت → URI معتبر.

    🔴 باگ: کد قبلی می‌نوشت f"file://{prof}" — روی ویندوز
       می‌شد file://C:\\Users\\... که URI نامعتبر است و
       LibreOffice آن را رد می‌کند. نتیجه: حتی وقتی لیبره
       نصب بود، تبدیل شکست می‌خورد.
       درست: file:///C:/Users/...  →  Path.as_uri()
    """
    try:
        return Path(d).resolve().as_uri()
    except Exception:
        s = str(d).replace("\\", "/")
        if not s.startswith("/"):
            s = "/" + s
        return "file://" + s


def _word_com_to_pdf(docx_path, out_pdf):
    """
    🪟 تبدیل با خودِ Microsoft Word روی ویندوز.

    🎯 خیلی از کاربران ویندوز LibreOffice ندارند ولی Word دارند.
       این راه بدون نصب هیچ چیز اضافه کار می‌کند.
    """
    if os.name != "nt":
        return None
    try:
        import win32com.client  # noqa
    except ImportError:
        return None
    word = None
    try:
        import win32com.client
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        doc = word.Documents.Open(str(Path(docx_path).resolve()),
                                  ReadOnly=1)
        doc.SaveAs(str(Path(out_pdf).resolve()), FileFormat=17)  # 17=PDF
        doc.Close(False)
        return str(out_pdf) if Path(out_pdf).exists() else None
    except Exception as e:
        log(f"⚠️ تبدیل با Word: {e}")
        return None
    finally:
        try:
            if word:
                word.Quit()
        except Exception:
            pass


_LAST_PDF_ERR = ""          # 📝 آخرین خطای واقعی تبدیل — برای پنل


def last_pdf_error():
    return _LAST_PDF_ERR


def docx_to_pdf(docx_path, out_dir=None):
    """
    DOCX → PDF

    دو موتور: LibreOffice (لینوکس/ویندوز) یا Microsoft Word (ویندوز)

    🔴 اصلاح: قبلاً هر خطایی بی‌صدا None برمی‌گرداند و کاربر فقط
       می‌دید «موتور در دسترس نیست». حالا پیام واقعی لیبره ذخیره
       می‌شود تا در پنل «وضعیت نصب» دیده شود.
    """
    global _LAST_PDF_ERR
    _LAST_PDF_ERR = ""
    out_dir_p = Path(out_dir or Path(docx_path).parent)
    out_dir_p.mkdir(parents=True, exist_ok=True)
    target = out_dir_p / (Path(docx_path).stem + ".pdf")

    lo = libreoffice_bin()
    if not lo:
        _LAST_PDF_ERR = "LibreOffice پیدا نشد"
        # 🪟 روی ویندوز، Word را امتحان کن
        pdf = _word_com_to_pdf(docx_path, target)
        if not pdf:
            _LAST_PDF_ERR = "نه LibreOffice پیدا شد نه Word"
        return pdf

    try:
        with tempfile.TemporaryDirectory(prefix="nora_lo_") as prof:
            # 🔴 فاز ۲۵ — PDF بدون تگ صادر شود
            #
            #    خطای کاربر: «MuPDF error: No common ancestor in
            #    structure tree»
            #
            #    لیبره پیش‌فرض PDF «تگ‌دار» می‌سازد (برای
            #    دسترس‌پذیری). اگر ورد جدول تودرتو یا تکست‌باکس
            #    داشته باشد، درخت ساختار ناقص می‌شود و MuPDF
            #    موقع خواندن می‌ایستد → تصویر ساخته نمی‌شود.
            #
            #    UseTaggedPDF=false این درخت را کلاً نمی‌سازد.
            #    ظاهر PDF هیچ فرقی نمی‌کند.
            filt = ('pdf:writer_pdf_Export:{"UseTaggedPDF":'
                    '{"type":"boolean","value":"false"},'
                    '"ExportBookmarks":'
                    '{"type":"boolean","value":"false"},'
                    '"ReduceImageResolution":'
                    '{"type":"boolean","value":"false"}}')
            cmd = [lo, "--headless", "--invisible", "--nologo",
                   "--nodefault", "--nolockcheck", "--norestore",
                   f"-env:UserInstallation={_profile_uri(prof)}",
                   "--convert-to", filt,
                   "--outdir", str(out_dir_p), str(Path(docx_path).resolve())]
            r = subprocess.run(cmd,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=180, check=False,
                               creationflags=_no_window())
            # ♻️ نسخه‌های قدیمی لیبره فیلتر پیشرفته را نمی‌شناسند
            if not target.exists():
                cmd[cmd.index(filt)] = "pdf"
                r = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=180, check=False,
                    creationflags=_no_window())
        if target.exists():
            return str(target)

        # 🔁 گاهی لیبره نام خروجی را جور دیگری می‌گذارد
        for f in sorted(out_dir_p.glob("*.pdf"),
                        key=lambda x: x.stat().st_mtime, reverse=True):
            if abs(f.stat().st_mtime - time.time()) < 180:
                return str(f)

        msg = ((r.stderr or b"") + (r.stdout or b"")).decode(
            "utf-8", "ignore").strip()
        _LAST_PDF_ERR = msg[:300] or f"کد خروج {r.returncode}"
        log(f"⚠️ تبدیل PDF ناموفق: {_LAST_PDF_ERR}")

        # 🪟 لیبره شکست خورد؟ Word را امتحان کن
        pdf = _word_com_to_pdf(docx_path, target)
        if pdf:
            return pdf
    except subprocess.TimeoutExpired:
        _LAST_PDF_ERR = ("تبدیل بیش از ۳ دقیقه طول کشید — "
                         "شاید پنجرهٔ LibreOffice باز است")
        log("⚠️ " + _LAST_PDF_ERR)
    except FileNotFoundError:
        _LAST_PDF_ERR = "فایل اجرایی LibreOffice اجرا نشد"
        log("⚠️ " + _LAST_PDF_ERR)
    except Exception as e:
        _LAST_PDF_ERR = str(e)[:300]
        log(f"⚠️ تبدیل PDF: {e}")
    return None


def pdf_to_png(pdf_path, out_png=None, dpi=150):
    """
    PDF → PNG (صفحه اول).

    چهار راه به ترتیب: pdftoppm · PyMuPDF · pdf2image · pypdfium2

    🔴 نکتهٔ ویندوز: هیچ‌کدام از این‌ها روی ویندوز به‌طور پیش‌فرض
       نیستند! برای همین وقتی لیبره هست، بهتر است مستقیم از خودِ
       لیبره PNG بگیریم (تابع docx_to_png_lo) — نه از مسیر PDF.
    """
    out_png = str(out_png or (Path(pdf_path).with_suffix(".png")))

    # ۱) pdftoppm (سبک‌ترین، معمولاً کنار poppler هست)
    exe = shutil.which("pdftoppm")
    if exe:
        try:
            base = str(Path(out_png).with_suffix(""))
            subprocess.run([exe, "-png", "-r", str(dpi), "-f", "1", "-l", "1",
                            "-singlefile", str(pdf_path), base],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=90, check=False,
                           creationflags=_no_window())
            if Path(out_png).exists():
                return out_png
        except Exception as e:
            log(f"⚠️ pdftoppm: {e}")

    # ۲) PyMuPDF
    #
    # 🔴 فاز ۲۵ — خطای کاربر:
    #    «MuPDF error: format error: No common ancestor in structure tree»
    #
    #    MuPDF روی PDF تگ‌دارِ ناقص گیر می‌کند. دو کار می‌کنیم:
    #      • پیام‌های خطای داخلی MuPDF را خاموش می‌کنیم
    #      • اگر باز هم نشد، دلیلش را ثبت می‌کنیم (نه سکوت)
    try:
        import fitz
        try:
            # 🔇 جلوی چاپ خطاهای داخلی روی کنسول را بگیر
            fitz.TOOLS.mupdf_display_errors(False)
        except Exception:
            pass
        doc = fitz.open(str(pdf_path))
        try:
            page = doc.load_page(0)
            pix = page.get_pixmap(dpi=dpi)
            pix.save(out_png)
        finally:
            doc.close()
        if Path(out_png).exists():
            return out_png
    except Exception as e:
        log(f"⚠️ PyMuPDF: {str(e)[:120]}")

    # ۳) pdf2image
    try:
        from pdf2image import convert_from_path
        imgs = convert_from_path(str(pdf_path), dpi=dpi,
                                 first_page=1, last_page=1)
        if imgs:
            imgs[0].save(out_png, "PNG")
            return out_png
    except Exception as e:
        log(f"⚠️ pdf2image: {str(e)[:100]}")

    # ۴) pypdfium2 — چرخ آماده دارد، روی ویندوز بدون دردسر نصب می‌شود
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(pdf_path))
        page = pdf[0]
        img = page.render(scale=dpi / 72).to_pil()
        img.save(out_png, "PNG")
        pdf.close()
        if Path(out_png).exists():
            return out_png
    except Exception as e:
        log(f"⚠️ pypdfium2: {str(e)[:100]}")

    # ۵) 🆘 خود LibreOffice — وقتی همه شکست خوردند
    #    (مثلاً MuPDF روی PDF تگ‌دار گیر کرده)
    try:
        got = pdf_to_png_lo(pdf_path, out_png, dpi)
        if got:
            return got
    except Exception as e:
        log(f"⚠️ PDF→PNG لیبره: {str(e)[:100]}")

    log("⚠️ هیچ موتوری نتوانست PDF را به تصویر تبدیل کند")
    return None


def docx_to_png_lo(docx_path, out_png, dpi=150):
    """
    🖼️ DOCX → PNG مستقیم با LibreOffice — بدون نیاز به poppler.

    🔴 چرا لازم بود؟ روی ویندوز کاربر لیبره را نصب کرده ولی
       pdftoppm/PyMuPDF ندارد. مسیر قبلی «ورد → PDF → PNG» در
       مرحلهٔ آخر گیر می‌کرد و ربات به موتور داخلیِ ساده برمی‌گشت.
       نتیجه: کاربر لیبره داشت ولی کیفیت پایین می‌گرفت.

       خود LibreOffice مستقیم PNG می‌دهد — این مسیر را اول
       امتحان می‌کنیم.
    """
    lo = libreoffice_bin()
    if not lo:
        return None
    out_png = Path(out_png)
    out_dir = out_png.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    # 📐 ابعاد را از خودِ سند بخوان — نه فرض A4 عمودی
    #
    # 🔴 باگ رفع‌شده: قبلاً PixelHeight = PixelWidth × ۱.۴۱۴ بود.
    #    این فقط برای صفحهٔ **عمودی** درست است. روی قالب افقی
    #    (که اکثر گواهینامه‌ها هستند) بومی به ارتفاع دو برابر
    #    لازم می‌ساخت و لیبره محتوا را بالای آن می‌چید —
    #    نتیجه: نوار سفید بزرگ و طرح جابه‌جا.
    ratio = 1.0 / 1.414                      # پیش‌فرض: A4 عمودی
    try:
        import docx as _dx
        _sec = _dx.Document(str(docx_path)).sections[0]
        _pw, _ph = _sec.page_width, _sec.page_height
        if _pw and _ph and int(_pw) > 0:
            ratio = float(int(_ph)) / float(int(_pw))
    except Exception:
        pass
    try:
        base = float(dpi or 150)
    except (TypeError, ValueError):
        base = 150.0
    # پهنا بر حسب اینچِ واقعی صفحه
    try:
        inches = float(int(_pw)) / 914400.0 if _pw else 11.7
    except Exception:
        inches = 11.7
    px = max(600, min(4000, int(round(inches * base))))
    py = max(600, min(4000, int(round(px * ratio))))

    # 🔴 فاز ۲۵ — فیلتر درست برای سند متنی
    #    «impress_png_Export» مال اسلاید است، نه Writer.
    #    روی فایل ورد یا خطا می‌داد یا نادیده گرفته می‌شد.
    #    فیلتر درست: writer_png_Export
    filt = (f'png:writer_png_Export:{{"PixelWidth":{{"type":"long",'
            f'"value":{px}}},"PixelHeight":{{"type":"long",'
            f'"value":{py}}}}}')
    for conv in (filt, "png"):
        try:
            with tempfile.TemporaryDirectory(prefix="nora_lo_") as prof:
                subprocess.run(
                    [lo, "--headless", "--invisible", "--nologo",
                     "--nodefault", "--nolockcheck", "--norestore",
                     f"-env:UserInstallation={_profile_uri(prof)}",
                     "--convert-to", conv, "--outdir", str(out_dir),
                     str(Path(docx_path).resolve())],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=180, check=False,
                    creationflags=_no_window())
            made = out_dir / (Path(docx_path).stem + ".png")
            if made.exists():
                if made.resolve() != out_png.resolve():
                    try:
                        shutil.move(str(made), str(out_png))
                    except Exception:
                        return str(made)
                return str(out_png)
        except subprocess.TimeoutExpired:
            log("⚠️ PNG با لیبره: زمان تمام شد")
        except Exception as e:
            log(f"⚠️ PNG با لیبره: {e}")
    return None


def trim_page_margin(png_path, tol=6, keep=0.35):
    """
    ✂️ نوار سفید اضافهٔ دور تصویر گواهینامه را می‌برد.

    🎯 «چرا وقتی از رو قالب میسازه، یه فضا سفیدی جا میزاره؟»

    گاهی موتور تبدیل (LibreOffice/Word) بومی بزرگ‌تر از خودِ
    صفحه می‌سازد و طرح در گوشه‌ای از آن می‌نشیند. نتیجه: نوار
    سفید پهن در یک یا چند طرف و به‌هم‌ریختن ظاهر.

    ⚠️ محافظه‌کارانه عمل می‌کند:
       • فقط نوارهایی که واقعاً یکدست سفیدند
       • اگر برش بیش از `keep` از تصویر را ببرد، انصراف
         (یعنی احتمالاً تشخیص اشتباه بوده)
    """
    if get_setting("cert_trim_margin", "1") != "1":
        return png_path
    try:
        from PIL import Image
    except ImportError:
        return png_path
    try:
        im = Image.open(png_path).convert("RGB")
        W, H = im.size
        if W < 50 or H < 50:
            return png_path
        px = im.load()

        def row_blank(y):
            step = max(1, W // 160)
            for x in range(0, W, step):
                r, g, b = px[x, y]
                if r < 255 - tol or g < 255 - tol or b < 255 - tol:
                    return False
            return True

        def col_blank(x):
            step = max(1, H // 160)
            for y in range(0, H, step):
                r, g, b = px[x, y]
                if r < 255 - tol or g < 255 - tol or b < 255 - tol:
                    return False
            return True

        top = 0
        while top < H - 1 and row_blank(top):
            top += 1
        bot = H - 1
        while bot > top and row_blank(bot):
            bot -= 1
        left = 0
        while left < W - 1 and col_blank(left):
            left += 1
        right = W - 1
        while right > left and col_blank(right):
            right -= 1

        # 🛡️ نوار باریک را دست نزن — بخشی از طرح است، نه خطای موتور.
        #    فقط نوارهای پهن (بیش از ۴٪ هر بُعد) بریده می‌شوند.
        min_w = max(4, int(W * 0.04))
        min_h = max(4, int(H * 0.04))
        if top < min_h:
            top = 0
        if left < min_w:
            left = 0
        if H - 1 - bot < min_h:
            bot = H - 1
        if W - 1 - right < min_w:
            right = W - 1

        nw, nh = right - left + 1, bot - top + 1
        if nw <= 0 or nh <= 0:
            return png_path
        # چیزی برای بریدن نبود
        if top == 0 and left == 0 and bot == H - 1 and right == W - 1:
            return png_path
        # برش خیلی بزرگ = تشخیص اشتباه
        if nw < W * (1 - keep) or nh < H * (1 - keep):
            log("💡 برش حاشیه رد شد — بیش از حد بزرگ بود")
            return png_path

        im.crop((left, top, right + 1, bot + 1)).save(png_path)
        log(f"✂️ حاشیهٔ سفید بریده شد: {W}×{H} → {nw}×{nh}")
        return png_path
    except Exception as e:
        log(f"⚠️ برش حاشیه: {e}")
        return png_path


def pdf_to_png_lo(pdf_path, out_png, dpi=150):
    """
    🖼️ PDF → PNG با خودِ LibreOffice.

    🎯 فاز ۲۵ — راه نجات وقتی PyMuPDF روی PDF گیر می‌کند
       («No common ancestor in structure tree»). لیبره خودش
       PDF را می‌خواند و تصویر می‌دهد — بدون MuPDF.
    """
    lo = libreoffice_bin()
    if not lo:
        return None
    out_png = Path(out_png)
    out_dir = out_png.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    # 📐 ابعاد را از خود PDF بخوان — نه فرض A4 عمودی
    #
    # 🔴 همان باگ docx_to_png_lo: فرمول px×۱.۴۱۴ فقط برای صفحهٔ
    #    عمودی درست است. روی گواهینامهٔ افقی بوم دو برابر بلند
    #    می‌ساخت و نوار سفید پهن می‌ماند.
    pw_pt, ph_pt = 595.0, 842.0          # پیش‌فرض: A4 عمودی
    try:
        from pypdf import PdfReader
        _bx = PdfReader(str(pdf_path)).pages[0].mediabox
        pw_pt = float(_bx.width) or pw_pt
        ph_pt = float(_bx.height) or ph_pt
    except Exception:
        pass
    try:
        base = float(dpi or 150)
    except (TypeError, ValueError):
        base = 150.0
    px = max(600, min(4000, int(round(pw_pt / 72.0 * base))))
    py = max(600, min(4000, int(round(px * (ph_pt / pw_pt)))))
    filt = (f'png:draw_png_Export:{{"PixelWidth":{{"type":"long",'
            f'"value":{px}}},"PixelHeight":{{"type":"long",'
            f'"value":{py}}}}}')
    for conv in (filt, "png"):
        try:
            with tempfile.TemporaryDirectory(prefix="nora_lo_") as prof:
                subprocess.run(
                    [lo, "--headless", "--invisible", "--nologo",
                     "--nodefault", "--nolockcheck", "--norestore",
                     f"-env:UserInstallation={_profile_uri(prof)}",
                     "--convert-to", conv, "--outdir", str(out_dir),
                     str(Path(pdf_path).resolve())],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=180, check=False,
                    creationflags=_no_window())
            made = out_dir / (Path(pdf_path).stem + ".png")
            if made.exists():
                if made.resolve() != out_png.resolve():
                    try:
                        shutil.move(str(made), str(out_png))
                    except Exception:
                        return str(made)
                return str(out_png)
        except Exception as e:
            log(f"⚠️ PDF→PNG با لیبره: {str(e)[:100]}")
    return None


def _emu_to_px(v, dpi=150):
    """EMU (واحد ورد) → پیکسل"""
    try:
        return int(float(v) / 914400.0 * dpi)
    except (TypeError, ValueError):
        return 0


def _par_align(par):
    """
    ↔️ ترازبندی پاراگراف — راست / وسط / چپ.

    اگر ورد چیزی نگفته باشد، برای متن فارسی «راست» فرض می‌کنیم.
    """
    try:
        a = par.alignment
        if a is not None:
            n = int(a)
            return {0: "left", 1: "center", 2: "right",
                    3: "justify"}.get(n, "right")
    except Exception:
        pass
    try:
        pf = par.paragraph_format
        if pf is not None and pf.alignment is not None:
            n = int(pf.alignment)
            return {0: "left", 1: "center", 2: "right",
                    3: "justify"}.get(n, "right")
    except Exception:
        pass
    # جهت پاراگراف
    try:
        from docx.oxml.ns import qn
        ppr = par._p.find(qn("w:pPr"))
        if ppr is not None and ppr.find(qn("w:bidi")) is not None:
            return "right"
    except Exception:
        pass
    return "right"


def _run_style(run, par, base=34):
    """
    🎨 اندازه، بولد و رنگ یک run را از ورد بخوان.

    🔴 نسخهٔ قبل همه چیز را نادیده می‌گرفت: اولین خط ۶۴ و بقیه
       همه ۴۰ — یعنی طرح شما هرچه بود، خروجی یک شکل می‌شد.
    """
    size = None
    bold = False
    color = None
    try:
        if run.font.size is not None:
            size = int(run.font.size.pt)
    except Exception:
        pass
    try:
        bold = bool(run.bold)
    except Exception:
        bold = False
    try:
        c = run.font.color
        if c is not None and c.rgb is not None:
            color = "#" + str(c.rgb)
    except Exception:
        color = None

    # از سبک پاراگراف (مثلاً Heading 1)
    if size is None:
        try:
            st = par.style
            if st is not None:
                if st.font is not None and st.font.size is not None:
                    size = int(st.font.size.pt)
                nm = (st.name or "").lower()
                if size is None and "head" in nm:
                    size = {"heading 1": 26, "heading 2": 20,
                            "heading 3": 16, "title": 30}.get(nm, 22)
                if "head" in nm or nm == "title":
                    bold = True
        except Exception:
            pass
    if size is None:
        size = 14
    return size, bold, color


def _par_images(par, doc):
    """
    🖼️ تصاویری که *داخل همین پاراگراف* هستند — به ترتیب.

    🔴 چرا لازم است؟ fill_docx جای {کیوآر} را با تصویر واقعی عوض
       می‌کند. پس موقع رسم، دیگر متنِ {کیوآر} وجود ندارد و
       تشخیص با الگوی متنی شکست می‌خورد → کیوآر ته صفحه می‌افتاد.
       حالا خودِ تصویرِ درج‌شده را در همان پاراگراف پیدا می‌کنیم.
    """
    out = []
    try:
        from docx.oxml.ns import qn
        for blip in par._p.iter(qn("a:blip")):
            rid = blip.get(qn("r:embed")) or blip.get(qn("r:link"))
            if not rid:
                continue
            try:
                part = doc.part.rels[rid].target_part
                out.append(part.blob)
            except Exception:
                continue
    except Exception:
        pass
    return out


def docx_to_png_fallback(docx_path, out_png, mapping=None):
    """
    🖼️ ساخت PNG از فایل ورد **بدون هیچ نصب اضافه‌ای**.

    🔴 فاز ۲۷ — بازنویسی کامل. کاربر گفت فرمت گواهینامه به‌هم می‌ریزد
       و حق داشت. نسخهٔ قبل فقط *متن* را برمی‌داشت و همه را
       وسط‌چین با دو اندازهٔ ثابت می‌نوشت.

       حالا از خود ورد می‌خوانیم:
         ↔️ ترازبندی هر پاراگراف (راست/وسط/چپ)
         🔠 اندازهٔ واقعی هر run (بر حسب pt)
         🅱️ بولد بودن
         🎨 رنگ متن
         📏 حاشیه و اندازهٔ صفحه
         🔳 جای دقیق {کیوآر} در متن — نه گوشهٔ ثابت
    """
    try:
        import docx
        from PIL import Image, ImageDraw
        import io
    except ImportError:
        return None
    try:
        d = docx.Document(str(docx_path))
    except Exception as e:
        log(f"⚠️ خواندن ورد برای PNG: {e}")
        return None

    try:
        try:
            dpi = int(get_setting("cert_dpi", "150") or 150)
        except (TypeError, ValueError):
            dpi = 150
        dpi = max(96, min(300, dpi))

        # 📏 اندازهٔ واقعی صفحه از خود ورد
        W = H = 0
        ml = mr = mt = 0
        try:
            sec = d.sections[0]
            W = _emu_to_px(sec.page_width, dpi)
            H = _emu_to_px(sec.page_height, dpi)
            ml = _emu_to_px(sec.left_margin, dpi)
            mr = _emu_to_px(sec.right_margin, dpi)
            mt = _emu_to_px(sec.top_margin, dpi)
        except Exception:
            pass
        if W < 200 or H < 200:
            W, H = int(11.7 * dpi), int(8.27 * dpi)   # A4 افقی
        ml = ml or int(W * 0.06)
        mr = mr or int(W * 0.06)
        mt = mt or int(H * 0.07)

        bg = get_setting("cert_png_bg", "#FFFDF7") or "#FFFDF7"
        img = Image.new("RGB", (W, H), bg)
        dr = ImageDraw.Draw(img)

        if get_setting("cert_png_border", "1") == "1":
            col = get_setting("cert_png_border_color", "#B8944A")
            pad = max(10, int(W * 0.013))
            dr.rectangle([pad, pad, W - pad, H - pad],
                         outline=col, width=max(3, int(W * 0.004)))
            pad2 = pad + max(6, int(W * 0.009))
            dr.rectangle([pad2, pad2, W - pad2, H - pad2],
                         outline=col, width=max(1, int(W * 0.001)))

        # 🖼️ تصاویر سند — کیوآر جدا می‌شود
        #    هرچه داخل پاراگراف‌ها کشیده شود از این فهرست
        #    برداشته می‌شود تا دوبار رسم نشود.
        qr_im = None
        others = []
        used_blobs = set()
        for rel in d.part.rels.values():
            if "image" not in rel.reltype:
                continue
            try:
                blob = rel.target_part.blob
                im = Image.open(io.BytesIO(blob))
                if qr_im is None and looks_like_qr(blob):
                    qr_im = im
                else:
                    others.append((blob, im))
            except Exception:
                continue

        # pt → پیکسل
        def px(pt):
            return max(8, int(pt * dpi / 72.0))

        content_w = W - ml - mr
        y = mt
        qr_drawn = False

        # 📏 پخش عمودی: اول ارتفاع کل محتوا را تخمین بزن، بعد
        #    فاصلهٔ سطرها را طوری تنظیم کن که صفحه پر شود.
        #    🔴 قبلاً همه چیز از بالا شروع و نصف صفحه خالی می‌ماند.
        _stretch = get_setting("cert_png_stretch", "1") == "1"

        def draw_line(text, size_pt, bold, color, align):
            """یک خط را با تراز درست بکش"""
            nonlocal y
            f = _find_font(px(size_pt))
            sh = _shape_fa(text)
            _kw = fa_text_kw()
            try:
                bb = dr.textbbox((0, 0), sh, font=f, **_kw)
                tw, th = bb[2] - bb[0], bb[3] - bb[1]
            except Exception:
                try:
                    bb = dr.textbbox((0, 0), sh, font=f)
                    tw, th = bb[2] - bb[0], bb[3] - bb[1]
                except Exception:
                    tw, th = len(sh) * px(size_pt) // 2, px(size_pt)
            if align == "center":
                x = ml + (content_w - tw) / 2
            elif align == "left":
                x = ml
            else:
                x = ml + content_w - tw     # راست‌چین
            fill = color or get_setting("cert_png_text", "#1a1a1a")
            _safe_text(dr, (x, y), sh, f, fill)
            # 🅱️ بولد ساختگی — یک‌بار دیگر با جابه‌جایی کوچک
            if bold:
                off = max(1, px(size_pt) // 28)
                _safe_text(dr, (x + off, y), sh, f, fill)
            y += th + max(6, int(px(size_pt) * 0.45)) + _extra
            return th

        def draw_qr_inline(size_pt, align):
            """🔳 کیوآر را همان‌جا که در متن بوده بکش"""
            nonlocal y, qr_drawn
            if qr_im is None:
                return
            mm = image_mm("qr")
            sz = max(60, int(mm / 25.4 * dpi))
            sz = min(sz, int(min(W, H) * 0.42))
            if align == "center":
                x = int(ml + (content_w - sz) / 2)
            elif align == "left":
                x = ml
            else:
                x = int(ml + content_w - sz)
            try:
                q2 = qr_im.convert("RGB").resize((sz, sz))
                img.paste(q2, (x, int(y)))
                y += sz + max(8, int(H * 0.012))
                qr_drawn = True
            except Exception as e:
                log(f"⚠️ درج کیوآر: {e}")

        # 📐 تخمین ارتفاع کل محتوا برای پخش یکنواخت
        _n_rows = 0
        _est = 0
        try:
            for par in d.paragraphs:
                _t = (par.text or "").strip()
                _im = _par_images(par, d)
                if not _t and not _im:
                    _est += max(8, int(H * 0.014))
                    continue
                _n_rows += 1
                if _im:
                    _est += int(image_mm("qr") / 25.4 * dpi)
                if _t:
                    _sz = 14
                    try:
                        _rs = [r for r in par.runs if (r.text or "").strip()]
                        if _rs:
                            _sz = max(_run_style(r, par)[0] for r in _rs)
                    except Exception:
                        pass
                    _est += px(_sz) + max(6, int(px(_sz) * 0.45))
        except Exception:
            _est = 0
        _avail = H - mt * 2
        _extra = 0
        if _stretch and _n_rows > 1 and 0 < _est < _avail:
            _extra = int((_avail - _est) / max(1, _n_rows))
            _extra = min(_extra, int(H * 0.05))

        # 📝 پاراگراف‌ها — با تراز و اندازهٔ واقعی
        for par in d.paragraphs:
            raw = par.text or ""
            align = _par_align(par)

            # 🔴 مهم: پاراگرافِ بدون متن ممکن است تصویر داشته باشد
            #    (fill_docx جای {کیوآر} تصویر گذاشته و متن پاک شده)
            #    نسخهٔ قبل همین‌جا رد می‌شد و کیوآر ته صفحه می‌افتاد.
            if not raw.strip() and not _par_images(par, d):
                y += max(8, int(H * 0.014))
                continue

            # 🔳 جای کیوآر — دو حالت:
            #    الف) هنوز متنِ {کیوآر} هست (قالب پر نشده)
            #    ب) fill_docx تصویر را درج کرده → خود تصویر را ببین
            has_qr = any(resolve_key(m.group(1)) == "qr"
                         for m in _PH_RE.finditer(raw))
            par_imgs = _par_images(par, d)
            inline_qr = None
            if par_imgs:
                for blob in par_imgs:
                    if looks_like_qr(blob):
                        try:
                            inline_qr = Image.open(io.BytesIO(blob))
                            has_qr = True
                            break
                        except Exception:
                            continue

            # بزرگ‌ترین run پاراگراف تعیین‌کنندهٔ اندازه است
            size_pt, bold, color = 14, False, None
            try:
                runs = [r for r in par.runs if (r.text or "").strip()]
                if runs:
                    picks = [_run_style(r, par) for r in runs]
                    size_pt = max(p[0] for p in picks)
                    bold = any(p[1] for p in picks)
                    color = next((p[2] for p in picks if p[2]), None)
                else:
                    size_pt, bold, color = _run_style(
                        par.runs[0] if par.runs else None, par)
            except Exception:
                pass

            clean = _PH_RE.sub(
                lambda m: "" if resolve_key(m.group(1)) in IMAGE_KEYS
                else m.group(0), raw).strip()

            if clean:
                draw_line(clean, size_pt, bold, color, align)
            if has_qr and not qr_drawn:
                if inline_qr is not None:
                    qr_im = inline_qr
                draw_qr_inline(size_pt, align if not clean else "center")
            elif par_imgs:
                # 🖼️ تصویر غیرکیوآر داخل پاراگراف (امضا، مهر، لوگو)
                #    همان‌جا و با همان تراز کشیده شود
                _drew = False
                for blob in par_imgs:
                    try:
                        im0 = Image.open(io.BytesIO(blob))
                    except Exception:
                        continue
                    if qr_im is not None and looks_like_qr(blob):
                        continue
                    used_blobs.add(blob[:2000])
                    try:
                        ih = max(50, int(H * 0.09))
                        iw = max(1, int(im0.width * ih
                                        / max(1, im0.height)))
                        if align == "center":
                            ix = int(ml + (content_w - iw) / 2)
                        elif align == "left":
                            ix = ml
                        else:
                            ix = int(ml + content_w - iw)
                        im2 = im0.convert("RGBA").resize((iw, ih))
                        img.paste(im2, (ix, int(y)), im2)
                        y += ih + max(6, int(H * 0.01))
                        _drew = True
                    except Exception:
                        continue

            if y > H - mt:
                break

        # 📊 جدول‌ها
        for tb in d.tables:
            for row in tb.rows:
                cells = [c.text.strip() for c in row.cells
                         if c.text.strip()]
                if not cells:
                    continue
                draw_line("   ".join(cells), 12, False, None, "center")
                if y > H - mt:
                    break

        # 🔳 اگر جای کیوآر در متن نبود، پایین وسط بگذار
        #    (نه گوشهٔ چپ — آنجا زشت می‌افتاد)
        if qr_im is not None and not qr_drawn:
            mm = image_mm("qr")
            sz = max(60, int(mm / 25.4 * dpi))
            sz = min(sz, int(min(W, H) * 0.30))
            try:
                q2 = qr_im.convert("RGB").resize((sz, sz))
                qy = max(int(y) + 10, H - sz - int(H * 0.10))
                qy = min(qy, H - sz - int(H * 0.06))
                img.paste(q2, (int((W - sz) / 2), qy))
            except Exception as e:
                log(f"⚠️ درج کیوآر پایانی: {e}")

        # 🖼️ لوگو و بقیه تصاویر — بالا، بدون تداخل با متن
        x_off = W - mr
        left = [(b, im) for b, im in others
                if b[:2000] not in used_blobs]
        for blob, im in left[:3]:
            try:
                th = max(60, int(H * 0.10))
                tw = max(1, int(im.width * th / max(1, im.height)))
                im2 = im.convert("RGBA").resize((tw, th))
                x_off -= tw + int(W * 0.01)
                img.paste(im2, (max(ml, x_off), int(mt * 0.25)), im2)
            except Exception:
                continue

        Path(out_png).parent.mkdir(parents=True, exist_ok=True)
        img.save(str(out_png), "PNG")
        return str(out_png)
    except Exception as e:
        log(f"⚠️ ساخت PNG از ورد: {e}")
        return None


def _to_bytes(im):
    """تصویر PIL → بایت PNG (برای تحلیل)"""
    import io
    b = io.BytesIO()
    im.convert("RGB").save(b, "PNG")
    return b.getvalue()


def make_qr(data, path, box=10):
    """🔳 ساخت تصویر QR — اگر کتابخانه نبود None"""
    try:
        import qrcode
    except ImportError:
        return None
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        qr = qrcode.QRCode(box_size=box, border=2,
                           error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(str(data))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(str(path))
        return str(path)
    except Exception as e:
        log(f"⚠️ ساخت QR: {e}")
        return None


# ══════════════════════════════════════════════════════════
# 🖼️ موتور جایگزین: پس‌زمینه تصویری + نوشتن متن
# ══════════════════════════════════════════════════════════
_BIDI_MODE = None


def _detect_bidi_mode():
    """
    🔍 تشخیص مسیر درست شکل‌دهی متن فارسی.

    🔴 باگ فاز ۲۸ (رفع‌شده):
       نسخهٔ قبلی این‌طور حدس می‌زد:
           mode = "reshape" if get_display(x) != x else "both"

       ولی `get_display` **همیشه** ترتیب را عوض می‌کند — کارش
       دقیقاً همین است. پس شرط همیشه درست بود، همیشه "reshape"
       برمی‌گشت، و `get_display` **هرگز اجرا نمی‌شد**.
       نتیجه: هر متنی روی بلیط و گواهینامه برعکس می‌افتاد
       («سوپرادمین» ← «ﻦﯿﻣﺩﺍﺮﭘﻮﺳ»).

    ✅ راه درست: حدس نزن — **رندر کن و پیکسل‌ها را بشمار.**
       متنی می‌کشیم که یک طرفش پر و طرف دیگرش خالی است، بعد
       نگاه می‌کنیم جوهر کدام سمت افتاده. این روی هر نسخه‌ای
       از هر کتابخانه‌ای درست جواب می‌دهد.
    """
    global _BIDI_MODE
    if _BIDI_MODE is not None:
        return _BIDI_MODE
    try:
        import arabic_reshaper                      # noqa: F401
    except Exception:
        _BIDI_MODE = "raw"
        return _BIDI_MODE
    try:
        from bidi.algorithm import get_display      # noqa: F401
    except Exception:
        _BIDI_MODE = "reshape"
        return _BIDI_MODE

    # ✅ قاعدهٔ قطعی — بدون حدس و بدون رندر آزمایشی:
    #
    #    RAQM دارد  → متن خام می‌دهیم، خودش می‌چیند.
    #                 (این تابع اصلاً صدا زده نمی‌شود)
    #    RAQM ندارد → موتور BASIC نویسه‌ها را چپ‌به‌راست می‌چیند،
    #                 پس باید خودمان هم شکل بدهیم (reshape) و هم
    #                 ترتیب را معکوس کنیم (get_display) → "both"
    #
    # 🔴 نسخه‌های قبلی سعی می‌کردند این را «تشخیص» بدهند و هر بار
    #    اشتباه می‌کردند. تشخیص لازم نیست — قاعده ساده و قطعی است.
    _BIDI_MODE = "reshape" if _has_raqm() else "both"
    return _BIDI_MODE


_RAQM_OK = None


def _has_raqm():
    """
    🔍 آیا Pillow با موتور RAQM ساخته شده؟

    اگر بله، خودش حروف فارسی را می‌چسباند و راست‌به‌چپ
    می‌کند — بهترین کیفیت و بدون هیچ حدس‌وگمانی.

    🎛️ با تنظیم `fa_engine` می‌شود دستی مجبورش کرد:
       auto (پیش‌فرض) · raqm · basic
    """
    global _RAQM_OK
    # 🔧 اگر کاربر دستی تعیین کرده، همان حاکم است
    try:
        forced = (get_setting("fa_engine", "auto") or "auto").strip().lower()
    except Exception:
        forced = "auto"
    if forced == "raqm":
        return True
    if forced == "basic":
        return False

    if _RAQM_OK is None:
        try:
            from PIL import features
            _RAQM_OK = bool(features.check("raqm"))
        except Exception:
            _RAQM_OK = False
    return _RAQM_OK


def fa_text_kw():
    """🎯 پارامترهای رسم راست‌به‌چپ برای ImageDraw.text"""
    return {"direction": "rtl", "language": "fa"} if _has_raqm() else {}


def _safe_text(dr, xy, txt, font, fill, anchor=None):
    """
    🖌️ رسم متن با جهت درست — با بازگشت امن.

    اگر RAQM نصب نباشد یا خطا بدهد، بدون پارامتر جهت
    دوباره تلاش می‌کند تا هرگز تصویر خراب نشود.
    """
    kw = {"font": font, "fill": fill}
    if anchor:
        kw["anchor"] = anchor
    try:
        dr.text(xy, txt, **kw, **fa_text_kw())
        return True
    except Exception:
        try:
            dr.text(xy, txt, **kw)
            return True
        except Exception:
            return False


def _shape_fa(t):
    """
    ✍️ شکل‌دهی درست متن فارسی برای نوشتن روی تصویر.

    🔴 اگر RAQM هست، متن را **دست‌نخورده** برمی‌گردانیم.
       دستکاری اضافه روی متنی که Pillow خودش می‌چیند،
       باعث برعکس شدن می‌شود («سوپرادمین» ← «ﻦﯿﻣﺩﺍﺮﭘﻮﺳ»).
    """
    t = str(t)
    if _has_raqm():
        return t
    try:
        import arabic_reshaper
    except Exception:
        return t
    try:
        mode = _detect_bidi_mode()
        shaped = arabic_reshaper.reshape(t)
        if mode == "both":
            from bidi.algorithm import get_display
            return get_display(shaped)
        return shaped
    except Exception:
        return t


def _find_font(size):
    """
    🔤 فونت فارسی برای رسم روی تصویر.

    ⚠️ ترتیب مهم است: فونت‌های فارسی **قبل از** فونت‌های
       سیستمی می‌آیند. DejaVu حروف فارسی را نمی‌چسباند و
       Tahoma هم کیفیت خوبی ندارد — فقط آخرین چاره‌اند.
    """
    from PIL import ImageFont
    fd = Path(FILES_DIR) / "fonts"
    cands = [
        get_setting("cert_font_path", "").strip(),
        # 🟢 فونت‌های فارسی — اولویت اول
        str(fd / "Vazirmatn-Regular.ttf"),
        str(fd / "Vazirmatn-Medium.ttf"),
        str(fd / "Vazir.ttf"),
        str(fd / "IRANSans.ttf"),
        str(fd / "Sahel.ttf"),
        # 🪟 فونت‌های فارسی ویندوز
        "C:/Windows/Fonts/IRANSans.ttf",
        "C:/Windows/Fonts/Vazirmatn-Regular.ttf",
        # 🐧 فونت‌های فارسی لینوکس
        "/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Regular.ttf",
        # 🩹 آخرین چاره — کیفیت پایین ولی بهتر از هیچ
        "C:/Windows/Fonts/tahoma.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    # ⚙️ موتور چیدمان باید با روش آماده‌سازی متن هماهنگ باشد،
    #    وگرنه متنِ از پیش معکوس‌شده دوباره برعکس می‌شود.
    try:
        eng = (ImageFont.Layout.RAQM if _has_raqm()
               else ImageFont.Layout.BASIC)
    except Exception:
        eng = None

    for c in cands:
        if c and Path(c).exists():
            try:
                return ImageFont.truetype(c, size, layout_engine=eng)
            except Exception:
                try:
                    return ImageFont.truetype(c, size)
                except Exception:
                    continue
    try:
        return ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default()


def make_barcode(data, path):
    """▌ بارکد خطی ساده (Code128 اگر کتابخانه باشد، وگرنه None)"""
    try:
        import barcode
        from barcode.writer import ImageWriter
    except ImportError:
        return None
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        code = barcode.get("code128", str(data), writer=ImageWriter())
        out = code.save(str(Path(path).with_suffix("")))
        return out
    except Exception as e:
        log(f"⚠️ ساخت بارکد: {e}")
        return None


def render_on_image(bg_path, boxes, mapping, out_png, qr_png=None,
                    qr_box=None, images=None):
    """
    🖼️ نوشتن مقادیر روی یک تصویر پس‌زمینه.

    boxes: [{"key":"name","x":800,"y":580,"size":48,"color":"#1a1a1a",
             "align":"center"}]
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    try:
        img = Image.open(str(bg_path)).convert("RGB")
        d = ImageDraw.Draw(img)
        for b in (boxes or []):
            k = b.get("key")
            val = mapping.get(k)
            if val in (None, ""):
                continue
            f = _find_font(int(b.get("size") or 40))
            txt = _shape_fa(val)
            x, y = int(b.get("x") or 0), int(b.get("y") or 0)
            color = b.get("color") or "#1a1a1a"
            align = (b.get("align") or "center").lower()
            if align in ("center", "right"):
                try:
                    bb = d.textbbox((0, 0), txt, font=f, **fa_text_kw())
                    w = bb[2] - bb[0]
                except Exception:
                    try:
                        bb = d.textbbox((0, 0), txt, font=f)
                        w = bb[2] - bb[0]
                    except Exception:
                        w = len(txt) * int(b.get("size") or 40) // 2
                x = x - w // 2 if align == "center" else x - w
            _safe_text(d, (x, y), txt, f, color)

        # 🖼️ تصاویر با مختصات مشخص در boxes
        for b in (boxes or []):
            k = b.get("key")
            if k not in IMAGE_KEYS:
                continue
            src_img = (images or {}).get(k) or (qr_png if k == "qr" else None)
            if not src_img or not Path(src_img).exists():
                continue
            try:
                ov = Image.open(str(src_img))
                w = int(b.get("w") or b.get("size") or 150)
                h = int(b.get("h") or 0) or int(
                    ov.height * w / max(1, ov.width))
                ov = ov.resize((w, h))
                pos = (int(b.get("x") or 0), int(b.get("y") or 0))
                if ov.mode in ("RGBA", "LA"):
                    img.paste(ov, pos, ov)     # شفافیت امضا حفظ شود
                else:
                    img.paste(ov, pos)
            except Exception as e:
                log(f"⚠️ درج تصویر {k}: {e}")

        # 🔳 QR با تنظیم جدا (سازگاری با نسخه قبل)
        if qr_png and Path(qr_png).exists() and qr_box and \
                not any(b.get("key") == "qr" for b in (boxes or [])):
            q = Image.open(str(qr_png))
            sz = int(qr_box.get("size") or 150)
            q = q.resize((sz, sz))
            img.paste(q, (int(qr_box.get("x") or 0),
                          int(qr_box.get("y") or 0)))

        Path(out_png).parent.mkdir(parents=True, exist_ok=True)
        img.save(str(out_png), "PNG", quality=95)
        return str(out_png)
    except Exception as e:
        log(f"⚠️ رندر روی تصویر: {e}")
        return None


def image_to_pdf(png_path, out_pdf):
    """PNG → PDF با Pillow"""
    try:
        from PIL import Image
        img = Image.open(str(png_path)).convert("RGB")
        Path(out_pdf).parent.mkdir(parents=True, exist_ok=True)
        img.save(str(out_pdf), "PDF", resolution=150.0)
        return str(out_pdf)
    except Exception as e:
        log(f"⚠️ تبدیل PNG به PDF: {e}")
        return None


# ══════════════════════════════════════════════════════════
# 🎓 تولید نهایی گواهینامه
# ══════════════════════════════════════════════════════════
def get_template(tid=None):
    """قالب فعال — اگر tid ندهید، قالب پیش‌فرض"""
    if tid:
        return db_execute("SELECT * FROM cert_templates WHERE id=?",
                          (tid,), fetch="one")
    row = db_execute("SELECT * FROM cert_templates WHERE is_active=1 "
                     "AND is_default=1 ORDER BY id DESC LIMIT 1",
                     fetch="one")
    if row:
        return row
    return db_execute("SELECT * FROM cert_templates WHERE is_active=1 "
                      "ORDER BY id DESC LIMIT 1", fetch="one")


def verify_url(serial):
    """
    🔗 لینک اعتبارسنجی گواهینامه — پشت کیوآرکد.

    با اسکن، ربات باز می‌شود و گواهینامه اعتبارسنجی می‌گردد:
        https://ble.ir/<username>?start=cert_<serial>

    یوزرنیم از `config.deep_link` می‌آید که ترتیب
    «.env ← پنل ← getMe» را رعایت می‌کند. پس اگر آیدی یا
    توکن ربات عوض شود، لینک‌های تازه خودکار درست می‌شوند.
    """
    try:
        from config import deep_link
        u = deep_link(f"cert_{serial}")
        if u:
            return u
    except Exception:
        pass
    # 🩹 اگر یوزرنیم هنوز معلوم نیست، دستور متنی بده
    return f"/start cert_{serial}"


_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_EN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
                           "01234567890123456789")

# 🔤 کلیدهایی که اعدادشان باید لاتین بماند
#    (شماره سریال و لینک اعتبارسنجی — چون باید اسکن/کپی شوند)
NO_FA_KEYS = {"serial", "verify_url", "verify_code", "qr", "barcode",
              "doc_no",
              "mobile", "org_site", "org_phone"}


def fa_digits(text):
    """
    🔢 تبدیل اعداد لاتین به فارسی.

    🎯 «اعداد به فارسی باشه تو گواهینامه»
    """
    try:
        return str(text).translate(_FA_DIGITS)
    except Exception:
        return str(text)


def en_digits(text):
    """۰۱۲ → 012 (برای مقایسه و ذخیره)"""
    try:
        return str(text).translate(_EN_DIGITS)
    except Exception:
        return str(text)


def fa_digits_on():
    """آیا اعداد فارسی شوند؟ — از پنل قابل خاموش کردن"""
    return get_setting("cert_fa_digits", "1") == "1"


def build_mapping(**kw):
    """
    📋 ساخت دیکشنری مقادیر — همه کلیدها پر می‌شوند تا
    جای خالی در گواهینامه نماند.
    """
    m = {k: "" for k in PLACEHOLDERS}
    m.update({k: v for k, v in kw.items() if v is not None})

    # 🏢 هویت سازمان — از تنظیمات، اگر دستی نداده باشند
    if not m.get("org"):
        m["org"] = org_name()
    if not m.get("bot_name"):
        m["bot_name"] = bot_name()
    for k, sk in (("org_en", "cert_org_en"),
                  ("org_address", "cert_org_address"),
                  ("org_phone", "cert_org_phone"),
                  ("org_site", "cert_org_site")):
        if not m.get(k):
            m[k] = get_setting(sk, "") or ""

    # ✍️ امضاها — پیش‌فرض از تنظیمات
    for k, sk in (("signer", "cert_signer"), ("org_role", "cert_role"),
                  ("signer2", "cert_signer2"), ("role2", "cert_role2"),
                  ("signer3", "cert_signer3"), ("role3", "cert_role3")):
        if not m.get(k):
            m[k] = get_setting(sk, "") or ""

    # 📅 تاریخ صدور
    #
    # 🔴 باگ رفع‌شده (فاز ۳۷): fallback تاریخ **میلادی** چاپ
    #    می‌کرد («2026/07/29») اگر forms.jnow به هر دلیل
    #    شکست می‌خورد. حالا از ماژول اختصاصی jalali استفاده
    #    می‌کنیم که هیچ وابستگی بیرونی ندارد و همیشه شمسی
    #    برمی‌گرداند.
    if not m.get("issue_date"):
        try:
            import jalali as _j
            m["issue_date"] = _j.today_str()
        except Exception:
            try:
                from forms import jnow
                m["issue_date"] = jnow()[:10]
            except Exception:
                m["issue_date"] = ""

    # 🔁 نام‌های هم‌معنی که resolve_key برمی‌گرداند
    #    «{تاریخ صدور}» → issued_on  ·  «{تاریخ انقضا}» → expires_on
    if not m.get("issued_on"):
        m["issued_on"] = m.get("issue_date") or ""
    if not m.get("expires_on"):
        m["expires_on"] = m.get("expire_date") or ""
    if not m.get("today"):
        try:
            import jalali as _j
            m["today"] = _j.today_str()
        except Exception:
            m["today"] = m.get("issue_date") or ""

    # 👤 نام کامل از دو تکه
    if not m.get("name"):
        nm = f"{m.get('first_name') or ''} {m.get('last_name') or ''}".strip()
        if nm:
            m["name"] = nm

    # 🎩 خطاب محترمانه بر اساس جنسیت
    if not m.get("gender_title"):
        g = str(m.get("gender") or "").strip()
        if "مرد" in g or g.lower() in ("male", "m"):
            m["gender_title"] = get_setting("cert_title_male",
                                            "جناب آقای")
        elif "زن" in g or g.lower() in ("female", "f"):
            m["gender_title"] = get_setting("cert_title_female",
                                            "سرکار خانم")
        else:
            m["gender_title"] = get_setting("cert_title_none",
                                            "جناب آقای / سرکار خانم")

    # 📆 بازه تاریخ
    if not m.get("date_range"):
        a, b = m.get("start_date"), m.get("end_date")
        if a and b:
            m["date_range"] = f"از {a} تا {b}"
        elif a or b or m.get("date"):
            m["date_range"] = a or b or m.get("date")

    # 📈 درصد حضور
    if not m.get("attendance_pct"):
        try:
            done = int(m.get("sessions") or 0)
            tot = int(m.get("total_sessions") or 0)
            if tot > 0:
                m["attendance_pct"] = f"{round(done * 100 / tot)}٪"
        except (TypeError, ValueError):
            pass

    # ✅ نتیجه قبولی
    if not m.get("result"):
        try:
            sc = float(m.get("score") or 0)
            mx = float(m.get("max_score") or 0)
            need = float(get_setting("cert_pass_score", "0") or 0)
            if need and sc:
                m["result"] = get_setting("cert_txt_pass", "قبول") \
                    if sc >= need else get_setting("cert_txt_fail", "مردود")
            elif mx and sc:
                m["result"] = (get_setting("cert_txt_pass", "قبول")
                               if sc >= mx / 2 else
                               get_setting("cert_txt_fail", "مردود"))
        except (TypeError, ValueError):
            pass

    # ⏳ تاریخ انقضا
    #
    # 🔴 باگ رفع‌شده (فاز ۳۷): پیش‌فرض اینجا «۰» بود، یعنی
    #    «بدون انقضا» — در حالی که فاز ۳۴ پیش‌فرض کل سیستم را
    #    ۲۴ ماه کرد و در CERT_SETTINGS هم «۲۴» ثبت است.
    #    نتیجه: تا وقتی ادمین دستی وارد تنظیمات نمی‌شد و مقدار
    #    را ذخیره نمی‌کرد، کلید در دیتابیس وجود نداشت و این خط
    #    «۰» می‌گرفت → روی گواهینامه هیچ تاریخ انقضایی چاپ
    #    نمی‌شد و ستون expires_on خالی می‌ماند.
    if not m.get("expire_date"):
        try:
            months = int(get_setting("cert_valid_months", "24") or 0)
            if months and m.get("issue_date"):
                m["expire_date"] = _add_months_jalali(m["issue_date"],
                                                      months)
        except Exception:
            pass
    if not m.get("expires_on"):
        m["expires_on"] = m.get("expire_date") or ""

    # 🔖 اعتبارسنجی
    if m.get("serial"):
        if not m.get("verify_url"):
            m["verify_url"] = verify_url(m["serial"])
        if not m.get("verify_code"):
            m["verify_code"] = str(m["serial"]).split("-")[-1]

    # 🔢 اعداد فارسی — آخرین مرحله، بعد از پر شدن همه مقادیر
    #    🎯 «اعداد به فارسی باشه تو گواهینامه»
    #    ⚠️ شماره سریال و لینک اعتبارسنجی لاتین می‌مانند چون
    #       باید اسکن و کپی شوند.
    if fa_digits_on():
        for k, v in list(m.items()):
            if k in NO_FA_KEYS or k in IMAGE_KEYS:
                continue
            if isinstance(v, (str, int, float)) and str(v).strip():
                m[k] = fa_digits(v)
    return m


def _add_months_jalali(jdate, months):
    """➕ افزودن ماه به تاریخ شمسی (ساده و امن)"""
    try:
        parts = [int(x) for x in str(jdate).replace("-", "/").split("/")[:3]]
        if len(parts) < 3:
            return ""
        y, mo, d = parts
        mo += int(months)
        y += (mo - 1) // 12
        mo = (mo - 1) % 12 + 1
        if mo > 6 and d > 30:
            d = 30
        return f"{y}/{mo:02d}/{d:02d}"
    except Exception:
        return ""


def generate(mapping, tpl=None, want=None):
    """
    🎓 تولید گواهینامه.

    خروجی: dict {"docx":..., "pdf":..., "png":..., "engine":..., "error":...}

    🔴 باگ رفع‌شده (فاز ۴۰): `want` پیش‌فرض ثابت ("png","pdf")
       بود و سه تنظیم پنل — `cert_out_png`، `cert_out_pdf` و
       `cert_out_docx` — هیچ اثری نداشتند. ادمین «ارسال فایل
       PDF» را خاموش می‌کرد و باز هم PDF ساخته و فرستاده
       می‌شد.

       حالا اگر `want` داده نشود، از تنظیمات پنل خوانده
       می‌شود. اگر ادمین همه را خاموش کند، دست‌کم PNG می‌ماند
       تا کاربر بی‌گواهینامه نماند.
    """
    if want is None:
        want = tuple(k for k, sk in (("png", "cert_out_png"),
                                     ("pdf", "cert_out_pdf"),
                                     ("docx", "cert_out_docx"))
                     if get_setting(sk, "1" if k != "docx" else "0")
                     == "1")
        if not want:
            want = ("png",)
    out = {"docx": None, "pdf": None, "png": None,
           "engine": None, "error": ""}
    tpl = tpl or get_template()
    if not tpl:
        out["error"] = "قالبی تعریف نشده"
        return out

    src = tpl.get("file_path")
    if not src or not Path(src).exists():
        out["error"] = "فایل قالب پیدا نشد"
        return out

    serial = mapping.get("serial") or f"C{int(time.time())}"
    safe = re.sub(r"[^A-Za-z0-9_\-]", "_", str(serial))
    stamp = f"{safe}_{int(time.time()) % 100000}"
    CERT_OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 🖼️ همه تصاویر گواهینامه
    imgs = dict(all_assets())          # امضا، مهر، لوگو از پنل ادمین

    # 🔳 QR اعتبارسنجی (پویا برای هر نفر)
    if get_setting("cert_qr_on", "1") == "1":
        q = make_qr(mapping.get("verify_url") or verify_url(serial),
                    CERT_OUT_DIR / f"qr_{stamp}.png")
        if q:
            imgs["qr"] = q
    # ▌ بارکد خطی (اختیاری)
    if get_setting("cert_barcode_on", "0") == "1":
        b = make_barcode(serial, CERT_OUT_DIR / f"bc_{stamp}.png")
        if b:
            imgs["barcode"] = b
    # 📷 عکس شخص (اگر داده شده)
    if mapping.get("_photo") and Path(str(mapping["_photo"])).exists():
        imgs["photo"] = str(mapping["_photo"])

    qr_png = imgs.get("qr")
    kind = (tpl.get("kind") or "docx").lower()

    # ═══ مسیر ۱: قالب ورد ═══
    if kind == "docx":
        dx = CERT_OUT_DIR / f"cert_{stamp}.docx"
        got, err = fill_docx(src, dx, mapping, qr_png, images=imgs)
        if not got:
            out["error"] = err or "پر کردن قالب ناموفق"
            return out
        out["docx"] = got
        out["engine"] = "docx"

        try:
            dpi = int(get_setting("cert_dpi", "150") or 150)
        except (TypeError, ValueError):
            dpi = 150

        pdf = docx_to_pdf(got, CERT_OUT_DIR)
        if pdf:
            out["pdf"] = pdf
            out["engine"] = "office"
            if "png" in want:
                png = pdf_to_png(pdf, CERT_OUT_DIR / f"cert_{stamp}.png",
                                 dpi=dpi)
                if png:
                    out["png"] = trim_page_margin(png)

        # 🖼️ PDF شد ولی PNG نه؟ (ویندوز بدون poppler)
        #    مستقیم از لیبره PNG بگیر — طرح ورد حفظ می‌شود
        if "png" in want and not out.get("png") and libreoffice_bin():
            png = docx_to_png_lo(got, CERT_OUT_DIR / f"cert_{stamp}.png",
                                 dpi=dpi)
            if png:
                out["png"] = trim_page_margin(png)
                out["engine"] = "office"

        # 🖼️ اگر PNG نداریم، خودمان از روی ورد بکشیم
        #    🎯 کاربر همیشه باید تصویر بگیرد، حتی بدون LibreOffice
        if "png" in want and not out.get("png") and \
                get_setting("cert_png_fallback", "1") == "1":
            png = docx_to_png_fallback(
                got, CERT_OUT_DIR / f"cert_{stamp}.png", mapping)
            if png:
                out["png"] = png
                if not out.get("engine") or out["engine"] == "docx":
                    out["engine"] = "builtin"

        # 📄 اگر PDF نداریم ولی PNG داریم → PDF از تصویر
        if "pdf" in want and not out.get("pdf") and out.get("png"):
            out["pdf"] = image_to_pdf(
                out["png"], CERT_OUT_DIR / f"cert_{stamp}.pdf")

        if not pdf:
            lo_here = bool(libreoffice_bin())
            why = last_pdf_error()
            if lo_here:
                # 🔴 لیبره هست ولی کار نکرد — دقیق بگو چرا،
                #    نه اینکه بگویی «نصب کنید» (کاربر نصب کرده!)
                out["error"] = ("⚠️ LibreOffice پیدا شد ولی تبدیل انجام "
                                "نشد" + (f"\n📄 پیام: {why}" if why else ""))
            elif out.get("png"):
                out["error"] = ("💡 برای کیفیت بهتر، LibreOffice یا "
                                "Microsoft Word نصب کنید")
            else:
                out["error"] = ("موتور تبدیل در دسترس نیست — فقط فایل "
                                "ورد شخصی‌سازی‌شده تحویل شد")
        return out

    # ═══ مسیر ۲: قالب تصویری ═══
    boxes = []
    try:
        boxes = json.loads(tpl.get("boxes") or "[]")
    except Exception:
        boxes = []
    qr_box = None
    if tpl.get("qr_size"):
        qr_box = {"x": tpl.get("qr_x") or 0, "y": tpl.get("qr_y") or 0,
                  "size": tpl.get("qr_size") or 150}
    png = render_on_image(src, boxes, mapping,
                          CERT_OUT_DIR / f"cert_{stamp}.png",
                          qr_png, qr_box, images=imgs)
    if not png:
        out["error"] = "رندر تصویر ناموفق"
        return out
    out["png"] = png
    out["engine"] = "image"
    if "pdf" in want:
        out["pdf"] = image_to_pdf(png, CERT_OUT_DIR / f"cert_{stamp}.pdf")
    return out


def install_guide():
    """
    📦 راهنمای نصب — دقیقاً برای سیستمی که ربات روی آن اجرا می‌شود.

    🔴 چرا لازم است؟ کاربر در PowerShell ویندوز `apt install` زد و
       خطا گرفت — چون apt مال لینوکس است. حالا ربات خودش تشخیص
       می‌دهد روی چه سیستمی است و دستور درست را می‌دهد.
    """
    st = engine_status()
    win = os.name == "nt"
    lines = ["📦 راهنمای نصب", "━━━━━━━━━━━━━━", "",
             f"💻 سیستم شما: {'🪟 ویندوز' if win else '🐧 لینوکس'}", ""]

    miss_py = []
    if not st["docx"]:
        miss_py.append("python-docx")
    if not st["qr"]:
        miss_py.append("qrcode")
    if not st["fa_shape"]:
        miss_py += ["arabic-reshaper", "python-bidi"]

    if miss_py:
        lines += ["⚠️ این پکیج‌ها نصب نیستند:", ""]
        if win:
            lines += ["در PowerShell بزنید:", "",
                      f"   py -m pip install {' '.join(miss_py)}", ""]
        else:
            lines += [f"   pip3 install {' '.join(miss_py)}", ""]
    else:
        lines += ["✅ همه پکیج‌های پایتون نصب‌اند", ""]

    lines += ["━━━━━━━━━━━━━━", "🖨️ تبدیل به PDF:", ""]
    if st["libreoffice"]:
        lines.append("✅ LibreOffice پیدا شد — کیفیت عالی")
        if st.get("lo_path"):
            lines.append(f"   📂 {st['lo_path']}")
    elif win and st.get("word"):
        lines.append("✅ Microsoft Word پیدا شد — کیفیت عالی")
    else:
        lines.append("⚠️ پیدا نشد — از موتور داخلی استفاده می‌شود")
        lines.append("   (خروجی PNG و PDF می‌گیرید، ولی طرح ورد")
        lines.append("    دقیقاً حفظ نمی‌شود)")
        lines.append("")
        if win:
            lines += ["🔎 اگر مطمئنید LibreOffice نصب است:", "",
                      "   نصب‌کنندهٔ لیبره خودش را به PATH اضافه",
                      "   نمی‌کند. دکمهٔ «🩺 عیب‌یابی» را بزنید تا",
                      "   ببینید ربات کجاها را گشته — یا مسیر را",
                      "   دستی بدهید (چند ثانیه بیشتر نیست).", "",
                      "🪟 اگر واقعاً نصب نیست، یکی از این دو:", "",
                      "۱️⃣ اگر Microsoft Word دارید:", "",
                      "   py -m pip install pywin32", "",
                      "۲️⃣ یا LibreOffice رایگان:", "",
                      "   از libreoffice.org دانلود و نصب کنید",
                      "   (نصب عادی ویندوز — next next finish)", "",
                      "⚠️ دستور «apt install» مال لینوکس است،",
                      "   در ویندوز کار نمی‌کند."]
        else:
            lines += ["🐧 روی سرور لینوکس:", "",
                      "   sudo apt install libreoffice-writer "
                      "poppler-utils"]

    if win and st["libreoffice"] and not st["png"]:
        lines += ["", "💡 برای تصویر بهتر (اختیاری):",
                  "   py -m pip install pypdfium2"]

    lines += ["", "━━━━━━━━━━━━━━",
              "💡 بدون هیچ نصبی هم ربات کار می‌کند —",
              "   فقط طرح گرافیکی ورد ساده‌تر می‌شود."]
    return "\n".join(lines)


def word_available():
    """🪟 آیا Microsoft Word در دسترس است؟"""
    if os.name != "nt":
        return False
    try:
        import win32com.client  # noqa
        return True
    except ImportError:
        return False


def engine_status(force=False):
    """
    📊 وضعیت موتورهای تبدیل — برای نمایش در پنل

    force=True یعنی کش را دور بزن و از نو بگرد (دکمهٔ «بررسی دوباره»)
    """
    lo = libreoffice_bin(force=force)
    return {
        "docx": docx_available(),
        "libreoffice": bool(lo),
        "lo_path": lo or "",
        "word": word_available(),
        # 🖼️ اگر لیبره هست، خودش PNG می‌دهد — poppler لازم نیست
        "png": bool(lo) or bool(shutil.which("pdftoppm")) or _has("fitz")
               or _has("pdf2image") or _has("pypdfium2"),
        "png_builtin": docx_available() and _has("PIL"),
        "qr": _has("qrcode"),
        "fa_shape": _has("arabic_reshaper") and _has("bidi"),
    }


def _has(mod):
    try:
        __import__(mod)
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════════════════
# ⚙️ پنل ادمین — مدیریت قالب‌های گواهینامه
# ══════════════════════════════════════════════════════════
STATE_CT_UPLOAD = "ct_upload"
STATE_CT_NAME = "ct_name"
STATE_CT_BOX = "ct_box"

from auth import (  # noqa: E402
    set_state, get_state_data, clear_state, log_action,
    normalize_digits, is_admin as _is_admin,
)
from bale_api import (  # noqa: E402
    send, send_or_edit, send_document, send_photo,
    kb_cancel, kb_remove, BTN_BACK,
)


def _guard(cid, uid):
    if not _is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    import permissions as perm
    if not perm.has_perm(uid, "sys_settings"):
        send(cid, "🔒 این بخش فقط برای سوپرادمین است")
        return False
    return True


def _ph_help(group=None):
    """
    📋 راهنمای پارامترها — دسته‌بندی‌شده.

    اگر group بدهید فقط همان دسته، وگرنه فهرست دسته‌ها.
    """
    lines = []
    for title, keys in PH_GROUPS:
        if group and title != group:
            continue
        lines.append(title)
        for k in keys:
            if k not in PLACEHOLDERS:
                continue
            img = " 🖼️" if k in IMAGE_KEYS else ""
            lines.append(f"   {{{ph_label(k)}}}{img} — {ph_desc(k)}")
        lines.append("")
    lines += ["💡 هم {نام} کار می‌کند هم {{نام}}",
              "💡 نام انگلیسی هم قبول است: {name}",
              "🖼️ = تصویر است، نه متن"]
    return "\n".join(lines)


def show_panel(cid, uid):
    """🎓 پنل قالب‌های گواهینامه"""
    if not _guard(cid, uid):
        return

    rows = db_execute("SELECT * FROM cert_templates WHERE is_active=1 "
                      "ORDER BY is_default DESC, id DESC", fetch="all") or []
    total = db_scalar("SELECT COUNT(*) FROM certificates") or 0
    st = engine_status()

    lines = ["🎓 قالب‌های گواهینامه", "━━━━━━━━━━━━━━", ""]
    if not rows:
        lines += ["🌱 هنوز قالبی ثبت نکرده‌اید.", "",
                  "📄 فایل ورد گواهینامه‌تان را بفرستید — جای",
                  "   پارامترها را با {نام} مشخص کنید.", ""]
    else:
        lines.append(f"📋 {len(rows)} قالب فعال:")
        for r in rows:
            mark = "⭐" if r.get("is_default") else "▫️"
            kind = "📄 ورد" if (r.get("kind") or "docx") == "docx" \
                else "🖼️ تصویر"
            try:
                phs = json.loads(r.get("placeholders") or "[]")
            except Exception:
                phs = []
            lines.append(f"{mark} {r.get('name')} — {kind} "
                         f"({len(phs)} پارامتر)")
        lines.append("")

    lines += [f"🎓 گواهینامه‌های صادرشده: {total}", "",
              "━━━━━━━━━━━━━━", "🖨️ موتور تبدیل:"]
    lines.append(f"   {'✅' if st['docx'] else '❌'} خواندن فایل ورد")
    if st["libreoffice"]:
        lines.append("   ✅ LibreOffice — کیفیت کامل")
    elif st.get("word"):
        lines.append("   ✅ Microsoft Word — کیفیت کامل")
    elif st.get("png_builtin"):
        lines.append("   🟡 موتور داخلی — PNG و PDF می‌سازد")
        lines.append("      (طرح گرافیکی ورد ساده‌تر می‌شود)")
        lines.append("   💡 LibreOffice نصب دارید ولی دیده نمی‌شود؟")
        lines.append("      «🩺 عیب‌یابی» را بزنید")
    else:
        lines.append("   ⚠️ فقط فایل ورد تحویل می‌شود")
    lines.append(f"   {'✅' if st['qr'] else '⚠️'} کیوآرکد")
    lines.append(f"   {'✅' if st['fa_shape'] else '⚠️'} فارسی‌نویسی تصویر")

    btns = [[{"text": "📄 افزودن قالب ورد", "callback_data": "ct_new_docx"}],
            [{"text": "🖼️ افزودن قالب تصویری",
              "callback_data": "ct_new_img"}]]
    for r in rows[:8]:
        mark = "⭐" if r.get("is_default") else "▫️"
        btns.append([{"text": f"{mark} {r.get('name')}"[:30],
                      "callback_data": f"ctv_{r['id']}"}])
    btns.append([{"text": "📋 راهنمای پارامترها",
                  "callback_data": "ct_help"}])
    if not (st["libreoffice"] or st.get("word")) or not st["qr"]:
        btns.append([{"text": "🩺 موتور تبدیل — عیب‌یابی",
                      "callback_data": "ct_engine"}])
        btns.append([{"text": "📦 راهنمای نصب (کیفیت بهتر)",
                      "callback_data": "ct_install"}])
    else:
        btns.append([{"text": "📦 وضعیت نصب و موتور",
                      "callback_data": "ct_engine"}])
    btns.append([{"text": "🔙 گواهینامه و بلیط",
                  "callback_data": "ct_hub"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_install(cid, uid, force=False):
    """📦 راهنمای نصب متناسب با سیستم"""
    if not _guard(cid, uid):
        return
    if force:
        # 🔄 «بررسی دوباره» یعنی واقعاً از نو بگرد
        global _LO_BIN, _LO_AT
        _LO_BIN, _LO_AT = None, 0.0
        libreoffice_bin(force=True)
    st = engine_status()
    btns = [[{"text": "🔄 بررسی دوباره (جست‌وجوی کامل)",
              "callback_data": "ct_recheck"}],
            [{"text": "🩺 موتور تبدیل — عیب‌یابی",
              "callback_data": "ct_engine"}]]
    if not st["libreoffice"]:
        btns.append([{"text": "🖨️ دادن مسیر LibreOffice دستی",
                      "callback_data": "ctse_cert_soffice_path"}])
    btns.append([{"text": "🔙 قالب‌ها", "callback_data": "ct_panel"}])
    send_or_edit(cid, install_guide(), {"inline_keyboard": btns})


def show_engine(cid, uid, force=True):
    """
    🩺 عیب‌یابی موتور تبدیل.

    🎯 کاربر گفت: «لیبره نصب دارم ولی بات میگه نصب نیست»
       به‌جای یک «نه» خشک، اینجا نشان می‌دهیم دقیقاً کجاها را
       گشتیم و چه دیدیم — و راه حل می‌دهیم.
    """
    if not _guard(cid, uid):
        return
    if force:
        global _LO_BIN, _LO_AT
        _LO_BIN, _LO_AT = None, 0.0
    d = lo_diagnose()
    st = engine_status()
    win = os.name == "nt"

    lines = ["🩺 موتور تبدیل گواهینامه", "━━━━━━━━━━━━━━", ""]

    if d["found"]:
        lines += ["✅ LibreOffice پیدا شد و کار می‌کند 💚", "",
                  f"📂 {d['path']}", "",
                  "🎨 طرح فایل ورد شما عیناً حفظ می‌شود.", ""]
        err = last_pdf_error()
        if err:
            lines += ["⚠️ ولی آخرین تبدیل خطا داد:", f"   {err}", ""]
    else:
        lines += ["🔴 LibreOffice پیدا نشد", "",
                  f"🔍 {d['checked']} مسیر بررسی شد", ""]
        if d["existing"]:
            lines += ["📂 این فایل‌ها بودند ولی اجرا نشدند:"]
            for p in d["existing"][:4]:
                lines.append(f"   • {p}")
            lines += ["", "💡 یعنی نصب ناقص است — دوباره نصب کنید.", ""]
        if win and d["registry"]:
            lines += ["🗂️ در رجیستری ویندوز ثبت شده ولی فایلش نبود:"]
            for p in d["registry"][:3]:
                lines.append(f"   • {p}")
            lines.append("")
        if d["manual"]:
            lines += [f"✏️ مسیر دستی شما: {d['manual']}",
                      "   ⚠️ این مسیر درست نیست", ""]
        lines += ["━━━━━━━━━━━━━━", "🔧 راه حل:", ""]
        if win:
            lines += ["۱️⃣ مطمئن شوید واقعاً نصب است:",
                      "   منوی Start → بنویسید LibreOffice", "",
                      "۲️⃣ مسیر را دستی بدهید (مطمئن‌ترین راه):",
                      "   روی میان‌بر LibreOffice راست‌کلیک →",
                      "   Properties → مقدار Target را کپی کنید",
                      "   بعد دکمهٔ «🖨️ دادن مسیر دستی» را بزنید", "",
                      "۳️⃣ معمولاً اینجاست:",
                      "   C:\\Program Files\\LibreOffice\\program"
                      "\\soffice.exe", ""]
        else:
            lines += ["   sudo apt install libreoffice-writer", ""]

    lines += ["━━━━━━━━━━━━━━", "📊 وضعیت کامل:", ""]
    lines.append(f"   {'✅' if st['docx'] else '❌'} خواندن ورد "
                 f"(python-docx)")
    lines.append(f"   {'✅' if st['libreoffice'] else '⚪'} LibreOffice")
    if win:
        lines.append(f"   {'✅' if st.get('word') else '⚪'} "
                     f"Microsoft Word (pywin32)")
    lines.append(f"   {'✅' if st['png'] else '⚪'} تبدیل به تصویر")
    lines.append(f"   {'✅' if st.get('png_builtin') else '⚪'} "
                 f"موتور داخلی (پشتیبان)")
    lines.append(f"   {'✅' if st['qr'] else '⚠️'} کیوآرکد")
    lines.append(f"   {'✅' if st['fa_shape'] else '⚠️'} فارسی‌نویسی")

    lines += ["", "━━━━━━━━━━━━━━"]
    if d["found"]:
        lines.append("🎉 همه‌چیز آمادهٔ کار است!")
    elif st.get("word"):
        lines.append("💚 Word هست — کیفیت کامل می‌گیرید")
    elif st.get("png_builtin"):
        lines += ["💛 موتور داخلی فعال است — گواهینامه ساخته",
                  "   می‌شود ولی طرح ورد ساده‌تر می‌شود."]
    else:
        lines.append("🔴 فقط فایل ورد تحویل می‌شود")

    btns = [[{"text": "🔄 دوباره بگرد", "callback_data": "ct_engine"}],
            [{"text": "🖨️ دادن مسیر دستی",
              "callback_data": "ctse_cert_soffice_path"}]]
    if d["found"]:
        btns.append([{"text": "🧪 تست واقعی تبدیل",
                      "callback_data": "ct_engtest"}])
    btns += [[{"text": "📦 راهنمای نصب", "callback_data": "ct_install"}],
             [{"text": "🔙 گواهینامه و بلیط", "callback_data": "ct_hub"}]]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def engine_test(cid, uid):
    """
    🧪 تست واقعی — یک ورد کوچک می‌سازد و تبدیل می‌کند.

    🎯 «نصب هست» با «کار می‌کند» فرق دارد. این دکمه واقعاً
       یک فایل می‌سازد تا خیال ادمین راحت شود.
    """
    if not _guard(cid, uid):
        return
    send(cid, "🧪 در حال تست... چند لحظه صبر کنید 🌱")

    import uuid as _uu
    tmpd = Path(tempfile.gettempdir()) / f"nora_test_{_uu.uuid4().hex[:6]}"
    tmpd.mkdir(parents=True, exist_ok=True)
    dx = tmpd / "test.docx"
    ok_docx = False
    try:
        import docx as _dx
        doc = _dx.Document()
        doc.add_heading("تست موتور تبدیل نورا", 0)
        doc.add_paragraph("گواهی می‌شود این فایل درست تبدیل شد. 💚")
        doc.add_paragraph("۱۴۰۴ — خط زندگی")
        doc.save(str(dx))
        ok_docx = dx.exists()
    except Exception as e:
        return send(cid, f"❌ ساخت فایل تست ناموفق: {user_error_message(e)}")

    t0 = time.time()
    pdf = docx_to_pdf(str(dx), tmpd) if ok_docx else None
    png = None
    if ok_docx:
        png = pdf_to_png(pdf, tmpd / "test.png") if pdf else None
        if not png:
            png = docx_to_png_lo(str(dx), tmpd / "test.png")
    dt = round(time.time() - t0, 1)

    lines = ["🧪 نتیجهٔ تست", "━━━━━━━━━━━━━━", "",
             f"{'✅' if ok_docx else '❌'} ساخت فایل ورد",
             f"{'✅' if pdf else '❌'} تبدیل به PDF",
             f"{'✅' if png else '❌'} تبدیل به تصویر", "",
             f"⏱️ زمان: {dt} ثانیه"]
    err = last_pdf_error()
    if err and not pdf:
        lines += ["", f"📄 پیام خطا:", f"   {err}"]
    if pdf and png:
        lines += ["", "🎉 عالی! موتور تبدیل سالم است.",
                  "   گواهینامه‌ها با کیفیت کامل ساخته می‌شوند 💚"]
    elif pdf:
        lines += ["", "💛 PDF ساخته شد ولی تصویر نه.",
                  "   ربات از موتور داخلی برای PNG استفاده می‌کند."]
    else:
        lines += ["", "💛 موتور داخلی جایگزین می‌شود —",
                  "   گواهینامه ساخته می‌شود ولی ساده‌تر."]

    if png and Path(png).exists():
        try:
            send_photo(cid, str(png), "🖼️ نمونهٔ خروجی تست")
        except Exception:
            pass

    try:
        shutil.rmtree(tmpd, ignore_errors=True)
    except Exception:
        pass
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔄 تست دوباره", "callback_data": "ct_engtest"}],
        [{"text": "🩺 عیب‌یابی", "callback_data": "ct_engine"}],
        [{"text": "🔙 گواهینامه و بلیط", "callback_data": "ct_hub"}]]})


def show_help(cid, uid):
    if not _guard(cid, uid):
        return
    send_or_edit(cid, (
        "📋 راهنمای ساخت قالب گواهینامه\n━━━━━━━━━━━━━━\n\n"
        "۱️⃣ فایل ورد گواهینامه‌تان را باز کنید\n"
        "۲️⃣ هرجا می‌خواهید داده بنشیند، بنویسید {نام پارامتر}\n"
        "۳️⃣ فایل را همینجا بفرستید\n\n"
        + _ph_help() +
        "\n\n🔳 برای کیوآرکد اعتبارسنجی:\n"
        "   یا بنویسید {کیوآر}\n"
        "   یا یک تصویر بگذارید که نامش qr باشد\n\n"
        "✍️ مثال متن داخل ورد:\n"
        "«گواهی می‌شود {نام} با کدملی {کدملی} در دوره\n"
        " {رویداد} به مدت {ساعت} ساعت شرکت نموده است.»"
    ), {"inline_keyboard": [
        [{"text": "📄 حالا فایل ورد را بفرست",
          "callback_data": "ct_new_docx"}],
        [{"text": "🔙 بازگشت", "callback_data": "ct_panel"}]]})


def start_upload(cid, uid, kind="docx"):
    """منتظر دریافت فایل قالب"""
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_CT_UPLOAD, {"kind": kind}, merge=False)
    if kind == "docx":
        send(cid, (
            "📄 ارسال قالب ورد\n━━━━━━━━━━━━━━\n\n"
            "فایل .docx گواهینامه را بفرستید.\n\n"
            "💡 جای پارامترها را اینطور بنویسید: {نام}\n"
            "💡 جای کیوآرکد: {کیوآر}\n\n"
            "📋 برای دیدن همه پارامترها «راهنما» را بزنید."
        ), kb_cancel())
    else:
        send(cid, (
            "🖼️ ارسال قالب تصویری\n━━━━━━━━━━━━━━\n\n"
            "تصویر خام گواهینامه (بدون نام و مشخصات) را\n"
            "به صورت **فایل** بفرستید تا کیفیت حفظ شود.\n\n"
            "بعد جای هر پارامتر را تعیین می‌کنیم."
        ), kb_cancel())


def handle_upload(message):
    """📥 دریافت فایل قالب"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    d = get_state_data(uid)
    kind = d.get("kind") or "docx"

    txt = (message.get("text") or "").strip()
    if txt in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_panel(cid, uid)

    doc = message.get("document")
    photo = message.get("photo")
    if not doc and not photo:
        return send(cid, "⚠️ لطفاً فایل را بفرستید:", kb_cancel())

    from bale_api import get_file_info, download_file

    if doc:
        fname = str(doc.get("file_name") or "template")
        fid = doc.get("file_id")
    else:
        best = sorted(photo, key=lambda p: p.get("file_size") or 0)[-1]
        fname = "template.png"
        fid = best.get("file_id")

    low = fname.lower()
    if kind == "docx" and not low.endswith(".docx"):
        if low.endswith(".doc"):
            return send(cid, (
                "⚠️ فرمت .doc قدیمی است\n\n"
                "لطفاً در ورد «Save As» بزنید و .docx ذخیره کنید."
            ), kb_cancel())
        return send(cid, "⚠️ فقط فایل .docx قبول است:", kb_cancel())

    info = get_file_info(fid)
    if not info.get("ok"):
        return send(cid, "❌ دریافت فایل ناموفق بود")
    path = (info.get("result") or {}).get("file_path")
    data = download_file(path) if path else None
    if not data:
        return send(cid, "❌ دانلود فایل ناموفق بود")

    CERT_TPL_DIR.mkdir(parents=True, exist_ok=True)
    ext = ".docx" if kind == "docx" else (
        ".png" if not low.endswith((".jpg", ".jpeg")) else ".jpg")
    # 🔴 uuid لازم است: دو آپلود در یک ثانیه فایل هم را overwrite می‌کردند
    import uuid as _uu
    dest = (CERT_TPL_DIR /
            f"tpl_{uid}_{int(time.time())}_{_uu.uuid4().hex[:6]}{ext}")
    try:
        dest.write_bytes(data)
    except Exception as e:
        return send(cid, f"❌ ذخیره فایل ناموفق: {user_error_message(e)}")

    found = set()
    if kind == "docx":
        found, err = scan_docx(dest)
        if err:
            try:
                dest.unlink()
            except Exception:
                pass
            return send(cid, f"❌ {err}", kb_remove())
        if not found:
            # فایل بی‌مصرف روی دیسک نماند
            try:
                dest.unlink(missing_ok=True)
            except Exception:
                pass
            return send(cid, (
                "⚠️ هیچ پارامتری در فایل پیدا نشد\n"
                "━━━━━━━━━━━━━━\n\n"
                "مطمئن شوید جای خالی‌ها را با آکولاد نوشته‌اید،\n"
                "مثلاً: {نام}\n\n"
                "📋 «راهنمای پارامترها» را ببینید و دوباره بفرستید."
            ), kb_cancel())

    set_state(uid, STATE_CT_NAME,
              {"file": str(dest), "kind": kind,
               "phs": sorted(found)}, merge=False)

    lines = ["✅ فایل دریافت شد", "━━━━━━━━━━━━━━", ""]
    if found:
        lines.append(f"🔍 {len(found)} پارامتر شناسایی شد:")
        for k in sorted(found):
            lines.append(f"   ✔️ {ph_icon(k)} {ph_label(k)} — {ph_desc(k)}")
        missing = [k for k in ("name", "serial") if k not in found]
        if missing:
            lines += ["", "💡 پیشنهاد: این‌ها را هم اضافه کنید:"]
            for k in missing:
                lines.append(f"   ▫️ {{{ph_label(k)}}}")
        lines.append("")
    lines.append("یک نام برای این قالب بنویسید:")
    lines.append("مثال: گواهینامه دوره‌های آموزشی")
    send(cid, "\n".join(lines), kb_cancel())


def handle_name(message):
    """نام‌گذاری و ذخیره نهایی قالب"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid)

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_panel(cid, uid)
    if len(raw) < 2:
        return send(cid, "⚠️ نام حداقل ۲ حرف:", kb_cancel())

    n_before = db_scalar("SELECT COUNT(*) FROM cert_templates "
                         "WHERE is_active=1") or 0
    tid = db_execute("""INSERT INTO cert_templates
        (name, file_path, kind, placeholders, is_default, is_active,
         created_by)
        VALUES (?,?,?,?,?,1,?)""",
        (raw[:60], d.get("file"), d.get("kind") or "docx",
         json.dumps(d.get("phs") or [], ensure_ascii=False),
         1 if n_before == 0 else 0, uid))
    clear_state(uid)
    if not tid:
        return send(cid, "❌ ذخیره ناموفق", kb_remove())

    log_action(uid, "cert_template_added", {"id": tid})
    send(cid, f"✅ قالب «{raw[:40]}» ذخیره شد", kb_remove())
    return show_template(cid, uid, tid)


def show_template(cid, uid, tid):
    """👁️ جزئیات یک قالب"""
    if not _guard(cid, uid):
        return
    t = get_template(tid)
    if not t:
        return send(cid, "❌ یافت نشد")
    try:
        phs = json.loads(t.get("placeholders") or "[]")
    except Exception:
        phs = []
    used = db_scalar("SELECT COUNT(*) FROM certificates "
                     "WHERE template_id=?", (tid,)) or 0
    exists = Path(t.get("file_path") or "").exists()

    lines = [f"🎓 {t.get('name')}", "━━━━━━━━━━━━━━", "",
             f"📎 نوع: {'📄 ورد' if (t.get('kind') or 'docx') == 'docx' else '🖼️ تصویر'}",
             f"📁 فایل: {'✅ موجود' if exists else '❌ پیدا نشد!'}",
             f"⭐ پیش‌فرض: {'بله' if t.get('is_default') else 'خیر'}",
             f"🎓 صادرشده با این قالب: {used}", ""]
    if phs:
        lines.append(f"🔍 پارامترها ({len(phs)}):")
        for k in phs:
            if k in PLACEHOLDERS:
                lines.append(f"   ✔️ {ph_icon(k)} {ph_label(k)}")
    else:
        lines.append("⚠️ پارامتری ثبت نشده")

    btns = [
        [{"text": "👁️ پیش‌نمایش با داده نمونه",
          "callback_data": f"ctprev_{tid}"}],
        [{"text": "🩺 بررسی قالب (چرا نمی‌سازد؟)",
          "callback_data": f"ctdiag_{tid}"}],
        [{"text": "🧪 تست ساخت واقعی",
          "callback_data": f"cttest_{tid}"}],
        [{"text": "📥 دریافت فایل قالب",
          "callback_data": f"ctget_{tid}"}],
    ]
    if not t.get("is_default"):
        btns.append([{"text": "⭐ پیش‌فرض کن",
                      "callback_data": f"ctdef_{tid}"}])
    if (t.get("kind") or "docx") == "image":
        btns.append([{"text": "📐 تنظیم جای پارامترها",
                      "callback_data": f"ctbox_{tid}"}])
    btns.append([{"text": "🗑️ حذف", "callback_data": f"ctdel_{tid}"}])
    btns.append([{"text": "🔙 قالب‌ها", "callback_data": "ct_panel"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def diagnose_template(tid):
    """
    🩺 کالبدشکافی قالب ورد — دقیقاً چه چیزی داخلش هست؟

    🎯 فاز ۲۵ — کاربر گفت «نمیتونم بهت فایل ورد بفرستم».
       پس خود ربات فایل را می‌کاود و گزارش می‌دهد: چند تصویر،
       کدام‌شان کیوآر تشخیص داده شده، چه پارامترهایی هست، و
       کدام‌ها شناخته نشده‌اند.

    خروجی: dict
    """
    out = {"ok": False, "err": "", "images": [], "phs": [],
           "unknown": [], "qr_img": None, "qr_text": False,
           "texts": 0, "tables": 0, "boxes": 0,
           "pw_mm": 0, "ph_mm": 0, "orient": "", "page": ""}
    t = get_template(tid)
    if not t:
        out["err"] = "قالب پیدا نشد"
        return out
    src = t.get("file_path")
    if not src or not Path(src).exists():
        out["err"] = "فایل قالب روی دیسک نیست"
        return out
    if (t.get("kind") or "docx") != "docx":
        out["err"] = "این قالب تصویری است، نه ورد"
        return out
    try:
        import docx
    except ImportError:
        out["err"] = "python-docx نصب نیست"
        return out
    try:
        d = docx.Document(str(src))
    except Exception as e:
        out["err"] = f"باز کردن فایل ناموفق: {str(e)[:90]}"
        return out

    # 📐 ابعاد صفحه — منشأ «فضای سفید اضافه»
    try:
        _sec = d.sections[0]
        out["pw_mm"] = round(int(_sec.page_width) / 36000.0)
        out["ph_mm"] = round(int(_sec.page_height) / 36000.0)
        out["orient"] = ("افقی" if out["pw_mm"] > out["ph_mm"]
                         else "عمودی")
        _known = {(297, 210): "A4 افقی", (210, 297): "A4 عمودی",
                  (210, 148): "A5 افقی", (148, 210): "A5 عمودی",
                  (279, 216): "Letter افقی", (216, 279): "Letter عمودی"}
        out["page"] = _known.get((out["pw_mm"], out["ph_mm"]), "دلخواه")
    except Exception:
        pass

    # 📝 متن‌ها و پارامترها
    body = []
    for p in _all_paragraphs(d):
        if p.text:
            body.append(p.text)
    out["texts"] = len(body)
    out["tables"] = len(d.tables)
    try:
        from docx.oxml.ns import qn
        raw_all = "\n".join(body)
        for node in d.element.body.iter(qn("w:t")):
            if node.text:
                raw_all += "\n" + node.text
    except Exception:
        raw_all = "\n".join(body)

    seen, unknown = [], []
    for m in _PH_RE.finditer(raw_all):
        name = m.group(1).strip()
        k = resolve_key(name)
        if k:
            if k not in seen:
                seen.append(k)
            if k == "qr":
                out["qr_text"] = True
        elif name and name not in unknown:
            unknown.append(name)
    out["phs"] = seen
    out["unknown"] = unknown[:12]

    # 🖼️ تصاویر
    for rel in list(d.part.rels.values()):
        if "image" not in rel.reltype:
            continue
        try:
            blob = rel.target_part.blob
        except Exception:
            continue
        name = str(getattr(rel, "target_ref", "") or "").split("/")[-1]
        f = _image_fingerprint(blob) or {}
        is_qr = looks_like_qr(blob)
        out["images"].append({
            "name": name, "kb": len(blob) // 1024,
            "w": f.get("w0") or f.get("w") or 0,
            "h": f.get("h0") or f.get("h") or 0,
            "ar": round(f.get("ar", 0), 2),
            "gray": round(f.get("gray", 0), 2),
            "two_tone": round(f.get("two_tone", 0), 2),
            "edges": round(f.get("edges", 0), 2),
            "ink": round(f.get("ink", 0), 2),
            "is_qr": is_qr,
        })
        if is_qr and out["qr_img"] is None:
            out["qr_img"] = name
    out["ok"] = True
    return out


def show_diagnose(cid, uid, tid):
    """
    🩺 گزارش کالبدشکافی قالب — برای ادمین.

    🎯 «نمیتونم بهت فایل ورد بفرستم» → ربات خودش گزارش می‌دهد.
    """
    if not _guard(cid, uid):
        return
    d = diagnose_template(tid)
    t = get_template(tid)

    lines = ["🩺 بررسی قالب ورد", "━━━━━━━━━━━━━━", ""]
    if not d["ok"]:
        lines += [f"❌ {d['err']}"]
        return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
            [{"text": "🔙 قالب", "callback_data": f"ctv_{tid}"}]]})

    lines += [f"📄 {(t or {}).get('name') or '—'}", "",
              f"📝 پاراگراف: {d['texts']}  |  📊 جدول: {d['tables']}"]

    # ═══ ابعاد صفحه ═══
    #    🎯 «چرا یه فضا سفیدی جا میزاره؟» — معمولاً ریشه‌اش اینجاست
    if d.get("pw_mm"):
        lines.append(f"📐 صفحه: {fa_digits(d['pw_mm'])}×"
                     f"{fa_digits(d['ph_mm'])} میلی‌متر "
                     f"({d['page']} · {d['orient']})")
        if d["page"] == "دلخواه":
            lines += ["   ⚠️ اندازهٔ صفحه استاندارد نیست.",
                      "   💡 اگر حاشیهٔ سفید دیدید، در ورد",
                      "      Layout ← Size ← A4 را بزنید."]
    lines.append("")

    # ═══ کیوآر ═══
    lines.append("🔳 وضعیت کیوآرکد:")
    if d["qr_text"]:
        lines.append("   ✅ پارامتر متنی {کیوآر} پیدا شد")
    if d["qr_img"]:
        lines.append(f"   ✅ تصویر نمونه شناسایی شد ({d['qr_img']})")
    if not d["qr_text"] and not d["qr_img"]:
        lines += ["   🟡 جای مشخصی برای کیوآر نیست", "",
                  "   ✅ نگران نباشید — کیوآر ته صفحه اضافه",
                  "      می‌شود. ولی برای جای دقیق‌تر:",
                  "      ۱) هرجا خواستید بنویسید: {کیوآر}",
                  "      ۲) یا یک عکس کیوآر همان‌جا بگذارید"]
    lines.append("")

    # ═══ تصاویر ═══
    if d["images"]:
        lines.append(f"🖼️ تصاویر داخل فایل ({len(d['images'])}):")
        for im in d["images"][:6]:
            mark = "🔳 کیوآر" if im["is_qr"] else "▫️"
            lines.append(f"   {mark} {im['name']} — "
                         f"{im['w']}×{im['h']} ({im['kb']}KB)")
            if not im["is_qr"]:
                lines.append(f"      نسبت={im['ar']} خاکستری={im['gray']} "
                             f"دورنگ={im['two_tone']} لبه={im['edges']}")
        if len(d["images"]) > 6:
            lines.append(f"   … و {len(d['images']) - 6} تصویر دیگر")
    else:
        lines.append("🖼️ هیچ تصویری داخل فایل نیست")
    lines.append("")

    # ═══ پارامترها ═══
    if d["phs"]:
        lines.append(f"✅ پارامترهای شناخته‌شده ({len(d['phs'])}):")
        lines.append("   " + " · ".join(ph_label(k) for k in d["phs"][:14]))
    else:
        lines.append("⚠️ هیچ پارامتر شناخته‌شده‌ای نیست!")
    if d["unknown"]:
        lines += ["", f"🔴 شناخته نشد ({len(d['unknown'])}):"]
        for u in d["unknown"]:
            lines.append(f"   ❓ {{{u}}}")
        lines += ["", "   💡 این‌ها روی گواهینامه خام می‌مانند.",
                  "   از «📋 راهنمای پارامترها» نام درست را ببینید."]

    btns = [[{"text": "🧪 تست ساخت واقعی",
              "callback_data": f"cttest_{tid}"}],
            [{"text": "📋 راهنمای پارامترها", "callback_data": "ct_help"}],
            [{"text": "🩺 موتور تبدیل", "callback_data": "ct_engine"}],
            [{"text": "🔙 قالب", "callback_data": f"ctv_{tid}"}]]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def test_build(cid, uid, tid):
    """
    🧪 تست ساخت واقعی — هر مرحله جدا گزارش می‌شود.

    🎯 وقتی «نمیسازه»، باید بدانیم دقیقاً کدام مرحله شکست خورد.
    """
    if not _guard(cid, uid):
        return
    t = get_template(tid)
    if not t:
        return send(cid, "❌ قالب پیدا نشد")
    send(cid, "🧪 در حال تست... چند لحظه صبر کنید 🌱")

    import uuid as _uu
    stamp = _uu.uuid4().hex[:6]
    mp = build_mapping(name="نمونه — امیر نعمتی",
                       national_id="0010247165",
                       event="کارگاه آزمایشی", serial=f"TEST-{stamp}")
    steps = []
    res = {}
    t0 = time.time()
    try:
        res = generate(mp, t)
    except Exception as e:
        steps.append(("💥 اجرای موتور", False, str(e)[:110]))
    dt = round(time.time() - t0, 1)

    if res:
        steps.append(("📝 پر کردن قالب ورد", bool(res.get("docx")), ""))
        steps.append(("📄 تبدیل به PDF", bool(res.get("pdf")),
                      last_pdf_error()[:90] if not res.get("pdf") else ""))
        steps.append(("🖼️ تبدیل به تصویر", bool(res.get("png")), ""))

    lines = ["🧪 نتیجه تست ساخت", "━━━━━━━━━━━━━━", ""]
    for name, ok, why in steps:
        lines.append(f"{'✅' if ok else '❌'} {name}")
        if why:
            lines.append(f"      📄 {why}")
    lines += ["", f"⏱️ {dt} ثانیه"]

    if res.get("engine"):
        eng = {"office": "LibreOffice/Word (کیفیت کامل)",
               "builtin": "موتور داخلی (ساده)",
               "docx": "فقط ورد", "image": "قالب تصویری"}
        lines.append(f"⚙️ موتور: {eng.get(res['engine'], res['engine'])}")
    if res.get("error"):
        lines += ["", f"💡 {res['error']}"]

    # 🔳 آیا کیوآر واقعاً درج شد؟
    if res.get("docx") and Path(res["docx"]).exists():
        try:
            import docx as _dx
            dd = _dx.Document(res["docx"])
            n_img = sum(1 for r in dd.part.rels.values()
                        if "image" in r.reltype)
            body = "\n".join(p.text for p in _all_paragraphs(dd))
            left = find_placeholders(body)
            lines += ["", f"🖼️ تصاویر در خروجی: {n_img}"]
            if left:
                lines.append(f"🔴 جای خالی پرنشده: "
                             f"{'، '.join(list(left)[:5])}")
            else:
                lines.append("✅ همه جای خالی‌ها پر شدند")
        except Exception as e:
            log(f"⚠️ بررسی خروجی تست: {e}")

    # 📤 فایل‌ها را بفرست
    for key, cap in (("png", "🖼️ تصویر تست"),
                     ("pdf", "📄 PDF تست"),
                     ("docx", "📝 ورد تست")):
        p = res.get(key)
        if p and Path(p).exists():
            try:
                if key == "png":
                    send_photo(cid, p, cap)
                else:
                    send_document(cid, p, cap)
            except Exception as e:
                log(f"⚠️ ارسال فایل تست: {e}")

    # 🧹 پاکسازی
    for key in ("png", "pdf", "docx"):
        p = res.get(key)
        if p:
            try:
                Path(p).unlink(missing_ok=True)
            except OSError:
                pass

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔄 تست دوباره", "callback_data": f"cttest_{tid}"}],
        [{"text": "🩺 بررسی قالب", "callback_data": f"ctdiag_{tid}"}],
        [{"text": "🔙 قالب", "callback_data": f"ctv_{tid}"}]]},
        force_new=True)


def preview(cid, uid, tid):
    """👁️ ساخت یک نمونه با داده آزمایشی"""
    if not _guard(cid, uid):
        return
    t = get_template(tid)
    if not t:
        return send(cid, "❌ یافت نشد")

    send(cid, "⏳ در حال ساخت پیش‌نمایش...")
    m = build_mapping(
        name="نمونه آزمایشی", first_name="نمونه", last_name="آزمایشی",
        national_id="0010247165", mobile="09121234567",
        event="کارگاه آموزشی نمونه", date="۱۴۰۴/۰۶/۱۵",
        hours="۳", sessions="۴", score="۹۵", grade="عالی",
        location="سالن اجتماعات", mode="حضوری",
        org_role="مدیر آموزش", serial="NORA-TEST-00001")
    res = generate(m, t)

    sent = False
    if res.get("png"):
        send_photo(cid, res["png"], "👁️ پیش‌نمایش گواهینامه")
        sent = True
    if res.get("pdf"):
        send_document(cid, res["pdf"], "📄 نسخه PDF")
        sent = True
    if not sent and res.get("docx"):
        send_document(cid, res["docx"], "📄 نسخه ورد شخصی‌سازی‌شده")
        sent = True

    msg = "✅ پیش‌نمایش آماده شد" if sent else "❌ ساخت پیش‌نمایش ناموفق"
    if res.get("error"):
        msg += f"\n\n⚠️ {res['error']}"
    send(cid, msg)
    return show_template(cid, uid, tid)


def send_template_file(cid, uid, tid):
    """📥 دریافت فایل خام قالب"""
    if not _guard(cid, uid):
        return
    t = get_template(tid)
    if not t or not Path(t.get("file_path") or "").exists():
        return send(cid, "❌ فایل قالب پیدا نشد")
    send_document(cid, t["file_path"], f"📄 قالب: {t.get('name')}")
    return show_template(cid, uid, tid)


def set_default(cid, uid, tid):
    if not _guard(cid, uid):
        return
    db_execute("UPDATE cert_templates SET is_default=0")
    db_execute("UPDATE cert_templates SET is_default=1 WHERE id=?", (tid,))
    send(cid, "⭐ این قالب پیش‌فرض شد")
    return show_template(cid, uid, tid)


def delete_template(cid, uid, tid):
    if not _guard(cid, uid):
        return
    used = db_scalar("SELECT COUNT(*) FROM certificates "
                     "WHERE template_id=?", (tid,)) or 0
    if used:
        db_execute("UPDATE cert_templates SET is_active=0 WHERE id=?", (tid,))
        send(cid, f"🚫 قالب غیرفعال شد ({used} گواهینامه با آن صادر شده)")
    else:
        t = get_template(tid)
        db_execute("DELETE FROM cert_templates WHERE id=?", (tid,))
        try:
            if t and t.get("file_path"):
                Path(t["file_path"]).unlink(missing_ok=True)
        except Exception:
            pass
        send(cid, "🗑️ قالب حذف شد")
    return show_panel(cid, uid)


def start_box(cid, uid, tid):
    """📐 تعیین مختصات پارامترها روی قالب تصویری"""
    if not _guard(cid, uid):
        return
    t = get_template(tid)
    if not t:
        return send(cid, "❌ یافت نشد")
    try:
        from PIL import Image
        w, h = Image.open(t["file_path"]).size
    except Exception:
        w = h = 0
    cur = t.get("boxes") or "[]"
    set_state(uid, STATE_CT_BOX, {"tid": tid}, merge=False)
    send(cid, (
        f"📐 تعیین جای پارامترها\n━━━━━━━━━━━━━━\n\n"
        f"🖼️ ابعاد تصویر: {w}×{h} پیکسل\n\n"
        f"هر خط یک پارامتر:\n"
        f"پارامتر | x | y | اندازه\n\n"
        f"مثال:\n"
        f"نام | 850 | 570 | 48\n"
        f"کدملی | 640 | 585 | 44\n"
        f"شماره | 150 | 700 | 24\n"
        f"کیوآر | 1400 | 950 | 150\n\n"
        f"📄 فعلی: {cur[:200]}\n\n"
        f"💡 x از چپ، y از بالا. متن وسط‌چین می‌شود."
    ), kb_cancel())


def handle_box(message):
    """دریافت مختصات‌ها"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid)
    tid = d.get("tid")

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_template(cid, uid, tid)

    boxes, qr = [], None
    bad = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            bad.append(line[:24])
            continue
        key = resolve_key(parts[0])
        if not key:
            bad.append(parts[0][:24])
            continue
        try:
            x = int(normalize_digits(parts[1]))
            y = int(normalize_digits(parts[2]))
            sz = int(normalize_digits(parts[3])) if len(parts) > 3 else 40
        except (ValueError, TypeError):
            bad.append(line[:24])
            continue
        if key == "qr":
            qr = {"x": x, "y": y, "size": sz}
        else:
            boxes.append({"key": key, "x": x, "y": y, "size": sz,
                          "align": "center"})

    if not boxes and not qr:
        return send(cid, (
            "⚠️ چیزی خوانده نشد\n\n"
            "قالب درست: نام | 850 | 570 | 48"
        ), kb_cancel())

    db_execute("UPDATE cert_templates SET boxes=?, qr_x=?, qr_y=?, "
               "qr_size=? WHERE id=?",
               (json.dumps(boxes, ensure_ascii=False),
                (qr or {}).get("x", 0), (qr or {}).get("y", 0),
                (qr or {}).get("size", 150), tid))
    # پارامترها را هم به‌روز کن
    phs = sorted({b["key"] for b in boxes} | ({"qr"} if qr else set()))
    db_execute("UPDATE cert_templates SET placeholders=? WHERE id=?",
               (json.dumps(phs, ensure_ascii=False), tid))
    clear_state(uid)

    msg = f"✅ {len(boxes)} پارامتر ثبت شد"
    if qr:
        msg += " + کیوآرکد"
    if bad:
        msg += f"\n⚠️ نامفهوم: {', '.join(bad[:4])}"
    send(cid, msg, kb_remove())
    return show_template(cid, uid, tid)


# ══════════════════════════════════════════════════════════
# 🧹 فاز ۱۹-ب — پاکسازی خودکار فایل‌های تولیدشده
#
# 🎯 «گواهی‌ها که ساخته میشن ذخیره نکن که دیتابیس و حافظه پر بشه،
#     یه تایمی بده به کاربر که ذخیره کنه بعد پاکش کن»
#
# 🔑 نکته مهم: فقط **فایل** پاک می‌شود، نه رکورد دیتابیس.
#    یعنی شماره گواهینامه و اعتبارسنجی برای همیشه کار می‌کند،
#    ولی فایل سنگین روی دیسک نمی‌ماند. اگر کاربر دوباره خواست،
#    از روی همان داده‌ها بازتولید می‌شود.
# ══════════════════════════════════════════════════════════
def keep_hours():
    """چند ساعت فایل گواهینامه نگه داشته شود؟ (۰ = برای همیشه)"""
    try:
        return int(get_setting("cert_keep_hours", "24") or 24)
    except (TypeError, ValueError):
        return 24


def autodelete_on():
    return get_setting("cert_autodelete", "1") == "1"


def cleanup_files(force=False):
    """
    🧹 پاک کردن فایل‌های منقضی گواهینامه.

    خروجی: (تعداد فایل, حجم آزادشده به کیلوبایت)
    """
    if not autodelete_on() and not force:
        return 0, 0
    hours = keep_hours()
    if hours <= 0 and not force:
        return 0, 0

    cutoff = time.time() - (hours * 3600)
    n = kb = 0

    # ۱) فایل‌های روی دیسک
    try:
        for f in CERT_OUT_DIR.glob("*"):
            if not f.is_file():
                continue
            try:
                st = f.stat()
                if force or st.st_mtime < cutoff:
                    kb += st.st_size // 1024
                    f.unlink()
                    n += 1
            except Exception:
                pass
    except Exception as e:
        log(f"⚠️ پاکسازی فایل گواهینامه: {e}")

    # ۲) مسیرها را از دیتابیس هم خالی کن (رکورد می‌ماند)
    #    اگر جدول هنوز ساخته نشده، بی‌صدا رد شو
    if not db_execute("SELECT name FROM sqlite_master WHERE type='table' "
                      "AND name='certificates'", fetch="one"):
        return n, kb
    try:
        if hours > 0:
            db_execute(
                "UPDATE certificates SET png_path=NULL, pdf_path=NULL, "
                "docx_path=NULL, file_path=NULL "
                "WHERE issued_at < datetime('now', ?)",
                (f"-{hours} hours",))
        elif force:
            db_execute("UPDATE certificates SET png_path=NULL, "
                       "pdf_path=NULL, docx_path=NULL, file_path=NULL")
    except Exception as e:
        log(f"⚠️ پاکسازی مسیر گواهینامه: {e}")

    if n:
        log(f"🧹 {n} فایل گواهینامه پاک شد ({kb} KB آزاد شد)")
    return n, kb


def files_stats():
    """📊 وضعیت فایل‌های گواهینامه"""
    out = {"count": 0, "kb": 0, "oldest_h": 0}
    try:
        now = time.time()
        oldest = now
        for f in CERT_OUT_DIR.glob("*"):
            if not f.is_file():
                continue
            st = f.stat()
            out["count"] += 1
            out["kb"] += st.st_size // 1024
            oldest = min(oldest, st.st_mtime)
        if out["count"]:
            out["oldest_h"] = int((now - oldest) / 3600)
    except Exception:
        pass
    return out


def regenerate(cert_row):
    """
    ♻️ بازتولید گواهینامه از روی رکورد دیتابیس.

    وقتی فایل پاک شده ولی کاربر دوباره می‌خواهد.
    """
    if not cert_row:
        return None
    try:
        from auth import get_user
        import events as _ev
        u = get_user(cert_row.get("bale_user_id")) or {}
        ev = _ev.get_event(cert_row.get("event_id")) or {}
        mp = build_mapping(
            name=f"{u.get('first_name') or ''} "
                 f"{u.get('last_name') or ''}".strip(),
            first_name=u.get("first_name"), last_name=u.get("last_name"),
            national_id=u.get("national_id"), mobile=u.get("mobile"),
            gender=u.get("gender"), city=u.get("city"),
            province=u.get("province"), education=u.get("education_level"),
            field_study=u.get("field_of_study"),
            university=u.get("university"), job=u.get("job_title"),
            company=u.get("company_name"), email=u.get("email"),
            father_name=u.get("father_name"),
            birth_date=u.get("birth_date"),
            member_id=u.get("id"),
            event=ev.get("title"), event_type=ev.get("event_type"),
            event_desc=ev.get("description"),
            date=ev.get("start_date"), start_date=ev.get("start_date"),
            location=ev.get("location_address"),
            organizer=ev.get("organizer"),
            mode="برخط" if ev.get("location_type") == "online" else "حضوری",
            hours=(round((ev.get("duration_minutes") or 0) / 60, 1)
                   if ev.get("duration_minutes") else ""),
            serial=cert_row.get("serial"))

        # 🔖 فاز ۳۷ — شناسهٔ دولایه و تاریخ‌های ثبت‌شده را
        #    **دوباره از رکورد** بردار.
        #
        #    🔴 باگ رفع‌شده: بازتولید فقط `serial` را می‌داد.
        #       کد فردی، شمارهٔ نامه و تاریخ اعتبار از نقشه
        #       غایب بودند، پس فایل تازه بدون آن‌ها ساخته
        #       می‌شد و با نسخهٔ اول فرق داشت — کیوآر هم به
        #       آدرس اشتباه می‌رفت.
        for _k, _col in (("verify_code", "person_code"),
                         ("doc_no", "doc_no"),
                         ("full_code", "full_code"),
                         ("issue_date", "issued_on"),
                         ("issued_on", "issued_on"),
                         ("expire_date", "expires_on"),
                         ("expires_on", "expires_on")):
            _v = cert_row.get(_col)
            if _v:
                mp[_k] = _v
        if cert_row.get("full_code"):
            try:
                import certverify as _cv
                mp["verify_url"] = _cv.verify_link(cert_row["full_code"])
            except Exception:
                pass

        tpl = get_template(cert_row.get("template_id")) or get_template()

        # 📷 فاز ۳۷ — عکس پرسنلی در بازتولید هم باشد
        try:
            import certphoto as _cp
            _cp.attach(mp, cert_row.get("bale_user_id"), tpl)
        except Exception as _pe:
            log(f"⚠️ عکس پرسنلی در بازتولید: {_pe}")

        res = generate(mp, tpl)
        if res.get("png") or res.get("pdf") or res.get("docx"):
            db_execute(
                "UPDATE certificates SET png_path=?, pdf_path=?, "
                "docx_path=?, file_path=? WHERE id=?",
                (res.get("png"), res.get("pdf"), res.get("docx"),
                 res.get("png") or res.get("pdf") or res.get("docx"),
                 cert_row.get("id")))
        return res
    except Exception as e:
        log(f"⚠️ بازتولید گواهینامه: {e}")
        return None


# ══════════════════════════════════════════════════════════
# ⚙️ فاز ۱۹-ب — تنظیمات جامع گواهینامه و بلیط
# ══════════════════════════════════════════════════════════
STATE_CT_SET = "ct_setting"
STATE_CT_ASSET = "ct_asset"

# (کلید تنظیم, آیکن, عنوان, نوع, پیش‌فرض, راهنما)
CERT_SETTINGS = [
    # ─── هویت سازمان ───
    ("cert_org_en", "🔤", "نام لاتین مجموعه", "text", "",
     "نام انگلیسی مجموعه برای گواهینامه دوزبانه"),
    ("cert_org_address", "🗺️", "آدرس مجموعه", "text", "", "آدرس کامل"),
    ("cert_org_phone", "☎️", "تلفن مجموعه", "text", "", "شماره تماس"),
    ("cert_org_site", "🌍", "وب‌سایت", "text", "", "آدرس سایت"),
    # ─── امضاها ───
    ("cert_signer", "✍️", "نام امضاکننده اول", "text", "",
     "مثال: حمیدرضا ابراهیمی"),
    ("cert_role", "🎖️", "سمت امضاکننده اول", "text", "",
     "مثال: معاون فرهنگی و تربیتی"),
    ("cert_signer2", "✍️", "نام امضاکننده دوم", "text", "",
     "برای گواهینامه دو امضایی"),
    ("cert_role2", "🎖️", "سمت امضاکننده دوم", "text", "", ""),
    ("cert_signer3", "✍️", "نام امضاکننده سوم", "text", "", ""),
    ("cert_role3", "🎖️", "سمت امضاکننده سوم", "text", "", ""),
    # ─── خطاب ───
    ("cert_title_male", "👨", "خطاب آقایان", "text", "جناب آقای", ""),
    ("cert_title_female", "👩", "خطاب خانم‌ها", "text", "سرکار خانم", ""),
    ("cert_title_none", "🎩", "خطاب نامشخص", "text",
     "جناب آقای / سرکار خانم", "وقتی جنسیت ثبت نشده"),
    # ─── نمره و اعتبار ───
    ("cert_pass_score", "🎯", "حد نصاب قبولی", "num", "0",
     "۰ = بدون حد نصاب"),
    ("cert_txt_pass", "✅", "متن قبولی", "text", "قبول", ""),
    ("cert_txt_fail", "❌", "متن مردودی", "text", "مردود", ""),
    # 🔴 باگ رفع‌شده (فاز ۳۵): «cert_valid_months» دو بار در همین
    #    لیست بود — یکی اینجا با پیش‌فرض «۰» و یکی در بخش استعلام
    #    با «۲۴». نتیجه: پنل دو ردیف تکراری نشان می‌داد و ردیف
    #    اول پیش‌فرض غلط «بدون انقضا» را جا می‌انداخت.
    #    تعریف درست فقط یک‌جا در بخش «استعلام و اعتبار» می‌ماند.
    # ─── اعتبارسنجی ───
    ("cert_qr_on", "🔳", "کیوآرکد اعتبارسنجی", "bool", "1", ""),
    ("cert_barcode_on", "▌", "بارکد خطی", "bool", "0",
     "نیازمند نصب python-barcode"),
    ("cert_serial_prefix", "🔖", "پیشوند شماره", "text", "NORA",
     "مثال: NORA → NORA-0405-12345"),
    # ─── خروجی ───
    ("cert_out_png", "🖼️", "ارسال تصویر PNG", "bool", "1", ""),
    ("cert_out_pdf", "📄", "ارسال فایل PDF", "bool", "1", ""),
    ("cert_out_docx", "📝", "ارسال فایل ورد", "bool", "0",
     "معمولاً لازم نیست"),
    ("cert_dpi", "🔍", "کیفیت تصویر (DPI)", "num", "150",
     "۱۵۰ معمولی · ۳۰۰ چاپ"),
    ("cert_fa_digits", "🔢", "اعداد فارسی", "bool", "1",
     "۱۴۰۴ به‌جای 1404 — شماره سریال لاتین می‌ماند"),
    ("cert_png_stretch", "📏", "پخش محتوا در کل صفحه", "bool", "1",
     "اگر خاموش باشد، محتوا از بالا شروع می‌شود"),
    ("cert_soffice_path", "🖨️", "مسیر LibreOffice", "text", "",
     "اگر ربات خودش پیدا نکرد، مسیر soffice.exe را اینجا بگذارید\n"
     "مثال: C:\\Program Files\\LibreOffice\\program\\soffice.exe"),
    ("cert_png_fallback", "🖼️", "موتور داخلی PNG (پشتیبان)", "bool", "1",
     "اگر LibreOffice و Word نبودند، خود ربات تصویر بسازد"),
    ("cert_trim_margin", "✂️", "برش حاشیهٔ سفید اضافه", "bool", "1",
     "اگر موتور تبدیل نوار سفید گذاشت، خودکار بریده شود"),
    ("cert_force_images", "🔳", "تصویرهای همیشه‌درج", "text", "qr",
     "اگر جایشان در قالب نبود، ته صفحه اضافه شوند · با کاما جدا کنید"),
    ("cert_one_page", "📄", "گواهینامه تک‌صفحه بماند", "bool", "1",
     "خط‌های خالی ته سند حذف شوند تا صفحهٔ دوم باز نشود"),
    ("cert_pos_from_tpl", "🎯", "جای تصویر از خود قالب", "bool", "1",
     "اگر {کیوآر} داخل کادر ورد باشد، تصویر دقیقاً همان‌جا بنشیند"),
    # ─── 📷 عکس پرسنلی (فاز ۳۶) ───
    ("cert_photo_need_approve", "✅", "فقط عکس تأییدشده", "bool", "1",
     "عکس پروفایل وقتی روی گواهینامه بنشیند که تأیید شده باشد"),
    ("cert_photo_fallback", "🧍", "آدمک برای بی‌عکس‌ها", "bool", "1",
     "اگر عکس نداشت، آدمک ساده بنشیند — نه جای خالی"),
    # ─── 🔒 صدور خودسرویس (فاز ۳۹) ───
    ("cert_self_issue", "🔓", "کاربر خودش گواهینامه بسازد", "bool", "0",
     "⚠️ توصیه: خاموش بماند — صدور فقط از مرکز صدور\n"
     "اگر روشن شود، کاربر بعد از ثبت حضور خودش می‌سازد"),
    ("cert_self_issue_msg", "💬", "پیام وقتی خودش نمی‌تواند", "text",
     "گواهینامه‌ها را برگزارکننده صادر می‌کند 💚", ""),
    # ─── 🔍 استعلام و اعتبار (فاز ۳۴) ───
    ("cert_valid_months", "📅", "اعتبار گواهینامه (ماه)", "num", "24",
     "۲۴ = دو سال · ۰ = بدون انقضا · در رویداد قابل تغییر"),
    ("cert_doc_no", "📄", "شمارهٔ نامهٔ پیش‌فرض", "text", "",
     "اگر رویداد شمارهٔ خودش را نداشته باشد، این استفاده می‌شود"),
    ("cert_code_len", "🔖", "طول کد فردی", "num", "6",
     "کد یکتای هر نفر — بین ۴ تا ۱۲"),
    ("cert_show_nid", "🆔", "نمایش کد ملی در استعلام", "bool", "1",
     "میانهٔ کد ملی پوشانده می‌شود"),
    ("cert_expiry_warn", "⏰", "هشدار انقضا (روز)", "num", "30",
     "چند روز قبل از انقضا به دارنده خبر بده · ۰ = هرگز"),
    # ─── پاکسازی ───
    ("cert_autodelete", "🧹", "پاکسازی خودکار فایل‌ها", "bool", "1",
     "رکورد و اعتبارسنجی می‌ماند، فقط فایل پاک می‌شود"),
    ("cert_keep_hours", "⏰", "مهلت نگهداری (ساعت)", "num", "24",
     "بعد از این مدت فایل پاک می‌شود · ۰ = هرگز"),
    ("cert_warn_user", "💬", "یادآوری ذخیره به کاربر", "bool", "1",
     "به کاربر بگوید تا کی فرصت دارد"),
]

TICKET_SETTINGS = [
    # ─── محتوای بلیط ───
    ("tk_title", "🎫", "عنوان بالای بلیط", "text", "بلیت ورود", ""),
    ("tk_show_name", "👤", "نمایش نام", "bool", "1", ""),
    ("tk_show_mobile", "📱", "نمایش موبایل", "bool", "1", ""),
    ("tk_show_nid", "🆔", "نمایش کد ملی", "bool", "0",
     "برای رویدادهای رسمی"),
    ("tk_show_code", "🎟️", "نمایش کد بلیط", "bool", "1", ""),
    ("tk_show_date", "📅", "نمایش تاریخ و ساعت", "bool", "1", ""),
    ("tk_show_place", "📍", "نمایش مکان", "bool", "1", ""),
    ("tk_show_link", "🔗", "نمایش لینک آنلاین", "bool", "1", ""),
    ("tk_show_price", "💰", "نمایش مبلغ پرداختی", "bool", "1", ""),
    ("tk_show_organizer", "👥", "نمایش برگزارکننده", "bool", "1", ""),
    ("tk_show_seat", "💺", "نمایش شماره صندلی", "bool", "0", ""),
    ("tk_show_photo", "📷", "نمایش عکس کاربر", "bool", "0", ""),
    ("tk_show_rules", "📜", "نمایش قوانین ورود", "bool", "0", ""),
    # ─── اعتبارسنجی ───
    ("tk_qr_on", "🔳", "کیوآرکد بلیط", "bool", "1",
     "برای اسکن در ورودی"),
    ("tk_barcode_on", "▌", "بارکد خطی", "bool", "0", ""),
    ("tk_verify_on", "✅", "اعتبارسنجی آنلاین", "bool", "1",
     "با اسکن، اصالت بررسی شود"),
    ("tk_once_only", "🔒", "بلیط یکبار مصرف", "bool", "0",
     "بعد از اسکن، دیگر معتبر نباشد"),
    # ─── ظاهر ───
    ("tk_style", "🎨", "سبک بلیط", "text", "classic",
     "classic · modern · minimal"),
    ("tk_note", "📝", "یادداشت پای بلیط", "text",
     "لطفاً این بلیط را همراه داشته باشید 💚", ""),
    ("tk_rules_text", "📜", "متن قوانین ورود", "text", "",
     "مثلاً: ۳۰ دقیقه قبل حاضر باشید"),
    ("tk_footer", "🏷️", "پانویس بلیط", "text", "", "نام مجموعه یا شعار"),
    # ─── تصویری ───
    ("tk_image_on", "🖼️", "بلیط تصویری", "bool", "0",
     "به‌جای متن، تصویر بفرستد"),
    ("tk_logo_on", "🏛️", "نمایش لوگو روی بلیط", "bool", "1", ""),
    # ─── پاکسازی ───
    ("tk_autodelete", "🧹", "پاکسازی خودکار فایل بلیط", "bool", "1", ""),
    ("tk_keep_hours", "⏰", "مهلت نگهداری بلیط (ساعت)", "num", "48",
     "۰ = هرگز"),
]


def tk(key, dflt=""):
    """خواندن یک تنظیم بلیط"""
    row = next((r for r in TICKET_SETTINGS if r[0] == key), None)
    return get_setting(key, dflt or (row[4] if row else ""))


def tk_on(key, dflt="1"):
    return tk(key, dflt) == "1"


def build_ticket_text(reg, user=None, event=None):
    """
    🎫 ساخت متن بلیط با احترام به همه تنظیمات ادمین.

    🎯 فاز ۲۰: قبلاً تنظیمات بلیط وجود داشت ولی هیچ‌جا اعمال
       نمی‌شد — متن بلیط ثابت بود.
    """
    reg = reg or {}
    user = user or {}
    event = event or {}
    nm = f"{user.get('first_name') or ''} " \
         f"{user.get('last_name') or ''}".strip()

    title = tk("tk_title", "بلیت ورود")
    lines = [f"🎫 ━━━━ {title} ━━━━ 🎫", ""]

    ev_title = event.get("title") or reg.get("title") or ""
    if ev_title:
        lines += [f"🎉 {ev_title}", ""]

    if tk_on("tk_show_name") and nm:
        lines.append(f"👤 نام: {nm}")
    if tk_on("tk_show_mobile") and user.get("mobile"):
        lines.append(f"📱 موبایل: {user['mobile']}")
    if tk_on("tk_show_nid", "0") and user.get("national_id"):
        lines.append(f"🆔 کد ملی: {user['national_id']}")
    if tk_on("tk_show_code") and reg.get("ticket_code"):
        lines.append(f"🎟️ کد بلیط: {reg['ticket_code']}")
    if tk_on("tk_show_seat", "0") and reg.get("seat_no"):
        lines.append(f"💺 صندلی: {reg['seat_no']}")

    if tk_on("tk_show_date"):
        d = event.get("start_date") or reg.get("start_date")
        t = event.get("start_time") or reg.get("start_time")
        if d:
            lines += ["", f"📅 تاریخ: {d}"]
        if t:
            lines.append(f"🕐 ساعت: {t}")

    if tk_on("tk_show_place"):
        loc = event.get("location_address") or reg.get("location_address")
        if loc:
            lines.append(f"📍 مکان: {loc}")
    if tk_on("tk_show_link"):
        lk = event.get("online_link") or reg.get("online_link")
        if lk:
            lines += ["", f"🔗 لینک ورود:\n{lk}"]

    if tk_on("tk_show_price") and reg.get("amount_paid"):
        try:
            from config import money
            lines.append(f"💰 پرداخت‌شده: {money(reg['amount_paid'])}")
        except Exception:
            pass
    if tk_on("tk_show_organizer"):
        org = event.get("organizer") or reg.get("organizer")
        if org:
            lines.append(f"👥 برگزارکننده: {org}")

    if tk_on("tk_show_rules", "0") and tk("tk_rules_text"):
        lines += ["", "📜 قوانین ورود:", tk("tk_rules_text")]

    note = tk("tk_note", "لطفاً این بلیط را همراه داشته باشید 💚")
    lines += ["", "━━━━━━━━━━━━━━━━━━━"]
    if note:
        lines.append(f"💡 {note}")
    foot = tk("tk_footer")
    if foot:
        lines.append(foot)
    return "\n".join(lines)


def _setting_of(key):
    for row in CERT_SETTINGS + TICKET_SETTINGS:
        if row[0] == key:
            return row
    return None


def _sval(key, dflt=""):
    return get_setting(key, dflt)


def show_hub(cid, uid):
    """
    🎓 هاب گواهینامه و بلیط — نقطه ورود واحد

    🎯 فاز ۲۰: «بخش مدیریت قالب و بلیط‌ها خیلی بهم‌ریخته‌ست»
       قبلاً تنظیمات، قالب‌ها، تصاویر و بلیط هرکدام جای متفاوتی
       بودند. حالا یک صفحه با چهار در ورودی روشن.
    """
    if not _guard(cid, uid):
        return

    n_tpl = db_scalar("SELECT COUNT(*) FROM cert_templates "
                      "WHERE is_active=1") or 0
    n_cert = db_scalar("SELECT COUNT(*) FROM certificates") or 0
    n_asset = len(all_assets())
    fs = files_stats()
    st = engine_status()

    # وضعیت آمادگی
    ready = n_tpl > 0
    engine_ok = st["libreoffice"] or st.get("word") or st.get("png_builtin")

    lines = ["🎓 گواهینامه و بلیط", "━━━━━━━━━━━━━━", "",
             f"{'🟢' if ready else '🔴'} قالب فعال: {n_tpl}",
             f"🖼️ تصاویر (امضا/مهر/لوگو): {n_asset}",
             f"🎓 صادرشده: {n_cert:,}",
             f"💾 فایل روی دیسک: {fs['count']} ({fs['kb']} KB)", ""]

    if not ready:
        lines += ["⚠️ هنوز قالبی ندارید",
                  "   از «📄 قالب‌ها» یک فایل ورد بفرستید", ""]
    if not engine_ok:
        lines += ["⚠️ موتور تبدیل در دسترس نیست", ""]
    elif not (st["libreoffice"] or st.get("word")):
        lines += ["🟡 موتور داخلی فعال است (طرح ورد ساده‌تر)",
                  "   LibreOffice دارید ولی دیده نمی‌شود؟ 🩺", ""]

    lines += ["━━━━━━━━━━━━━━", "از کجا شروع کنیم؟"]

    # 🏛️ فاز ۳۶ — آمار مرکز صدور
    try:
        n_iss = db_scalar("SELECT COUNT(*) FROM cert_issues "
                          "WHERE status='published'") or 0
        n_wait = db_scalar("SELECT COUNT(*) FROM cert_shares "
                           "WHERE state='ready'") or 0
    except Exception:
        n_iss = n_wait = 0
    if n_iss or n_wait:
        lines.insert(-2, f"🏛️ طرح منتشرشده: {n_iss}  ·  "
                         f"⏳ در انتظار دریافت: {n_wait}")

    btns = [
        [{"text": "🏛️ مرکز صدور گواهینامه",
          "callback_data": "cc_home"}],
        [{"text": f"📄 قالب‌های گواهینامه ({n_tpl})",
          "callback_data": "ct_panel"}],
        [{"text": f"🖼️ تصاویر: امضا · مهر · لوگو ({n_asset})",
          "callback_data": "ct_assets"}],
        [{"text": "📷 عکس پرسنلی", "callback_data": "cc_photo"}],
        [{"text": "⚙️ تنظیمات گواهینامه",
          "callback_data": "ct_set_cert"}],
        [{"text": "🎫 بلیط متنی رویداد",
          "callback_data": "ct_set_ticket"}],
        [{"text": "🎟️ بلیط تصویری فرم", "callback_data": "tk_panel"}],
        [{"text": "📊 آمار و پاکسازی", "callback_data": "ct_stats"}],
        [{"text": f"🩺 موتور تبدیل "
                  f"{'✅' if (st['libreoffice'] or st.get('word')) else '🟡'}",
          "callback_data": "ct_engine"}],
        [{"text": "📦 وضعیت نصب و راهنما",
          "callback_data": "ct_install"}],
        [{"text": "🔙 تنظیمات", "callback_data": "admin_settings"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_stats_page(cid, uid):
    """📊 آمار گواهینامه و پاکسازی"""
    if not _guard(cid, uid):
        return
    fs = files_stats()
    n_cert = db_scalar("SELECT COUNT(*) FROM certificates") or 0
    n_month = db_scalar("SELECT COUNT(*) FROM certificates "
                        "WHERE issued_at >= datetime('now','-30 day')") or 0
    n_week = db_scalar("SELECT COUNT(*) FROM certificates "
                       "WHERE issued_at >= datetime('now','-7 day')") or 0
    n_rev = db_scalar("SELECT COUNT(*) FROM certificates "
                      "WHERE COALESCE(revoked,0)=1") or 0

    top = db_execute("""SELECT e.title, COUNT(c.id) n
        FROM certificates c LEFT JOIN events e ON e.id=c.event_id
        GROUP BY c.event_id ORDER BY n DESC LIMIT 5""",
        fetch="all") or []

    lines = ["📊 آمار گواهینامه", "━━━━━━━━━━━━━━", "",
             f"🎓 کل صادرشده: {n_cert:,}",
             f"📅 ۳۰ روز اخیر: {n_month}",
             f"📆 ۷ روز اخیر: {n_week}"]
    if n_rev:
        lines.append(f"🚫 باطل‌شده: {n_rev}")
    lines += ["", "━━━━━━━━━━━━━━", "💾 فایل‌ها:",
              f"   📁 تعداد: {fs['count']}",
              f"   📏 حجم: {fs['kb']} کیلوبایت"]
    if fs["oldest_h"]:
        lines.append(f"   ⏰ قدیمی‌ترین: {fs['oldest_h']} ساعت پیش")
    lines += ["", f"🧹 پاکسازی خودکار: "
                  f"{'🟢 روشن' if autodelete_on() else '🔴 خاموش'}"]
    if autodelete_on():
        lines.append(f"⏰ مهلت نگهداری: {keep_hours()} ساعت")

    if top and top[0].get("title"):
        lines += ["", "🏆 بیشترین گواهینامه — به تفکیک رویداد:"]
        for r in top:
            if r.get("title"):
                lines.append(f"   • {str(r['title'])[:26]} — {r['n']}")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": f"🧹 پاکسازی الان ({fs['count']} فایل)",
          "callback_data": "ct_clean"}],
        [{"text": "⚙️ تنظیم پاکسازی",
          "callback_data": "ct_set_cert"}],
        [{"text": "🔙 بازگشت", "callback_data": "ct_hub"}]]})


def show_settings(cid, uid, page="cert"):
    """
    ⚙️ تنظیمات گواهینامه و بلیط — همه‌چیز یکجا.

    🎯 «همه اینا در تنظیمات گواهینامه و بلیط در منو تنظیمات
        قابل تغییر و تنظیم باشه»
    """
    if not _guard(cid, uid):
        return

    if page == "ticket":
        items, title = TICKET_SETTINGS, "🎫 تنظیمات بلیط"
    else:
        items, title = CERT_SETTINGS, "🎓 تنظیمات گواهینامه"

    fs = files_stats()
    n_cert = db_scalar("SELECT COUNT(*) FROM certificates") or 0
    n_tpl = db_scalar("SELECT COUNT(*) FROM cert_templates "
                      "WHERE is_active=1") or 0

    lines = [title, "━━━━━━━━━━━━━━", ""]
    if page == "cert":
        lines += [f"🎓 صادرشده: {n_cert}  |  📄 قالب فعال: {n_tpl}",
                  f"💾 فایل روی دیسک: {fs['count']} ({fs['kb']} KB)"]
        if fs["count"] and fs["oldest_h"]:
            lines.append(f"⏰ قدیمی‌ترین: {fs['oldest_h']} ساعت پیش")
        lines.append("")

    btns = []
    cur_group = None
    for key, icon, name, kind, dflt, hint in items:
        v = _sval(key, dflt)
        if kind == "bool":
            on = str(v) == "1"
            lines.append(f"{'🟢' if on else '⚪'} {icon} {name}")
            btns.append([{"text": f"{'✅' if on else '❌'} {icon} {name}"[:34],
                          "callback_data": f"ctsb_{key}"}])
        else:
            shown = v if str(v).strip() else "—"
            lines.append(f"▫️ {icon} {name}: {shown}")
            btns.append([{"text": f"{icon} {name}: {str(shown)[:14]}"[:34],
                          "callback_data": f"ctse_{key}"}])

    if page == "cert":
        btns.append([{"text": "🖼️ تصاویر (امضا · مهر · لوگو)",
                      "callback_data": "ct_assets"}])
        btns.append([{"text": "📐 اندازه تصاویر",
                      "callback_data": "ct_sizes"}])
        btns.append([{"text": f"🧹 پاکسازی الان ({fs['count']} فایل)",
                      "callback_data": "ct_clean"}])
        btns.append([{"text": "📄 قالب‌های گواهینامه",
                      "callback_data": "ct_panel"}])
        btns.append([{"text": "📝 متن ساده گواهینامه",
                      "callback_data": "cert_settings"}])
        btns.append([{"text": "🎫 بلیط متنی رویداد",
                      "callback_data": "ct_set_ticket"}])
        btns.append([{"text": "🎟️ بلیط تصویری فرم",
                      "callback_data": "tk_panel"}])
    else:
        btns.append([{"text": "🎟️ بلیط تصویری فرم",
                      "callback_data": "tk_panel"}])
        btns.append([{"text": "🎓 تنظیمات گواهینامه",
                      "callback_data": "ct_set_cert"}])

    btns.append([{"text": "🔙 گواهینامه و بلیط",
                  "callback_data": "ct_hub"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_setting(cid, uid, key):
    """روشن/خاموش کردن یک تنظیم"""
    if not _guard(cid, uid):
        return
    row = _setting_of(key)
    if not row or row[3] != "bool":
        return send(cid, "❌ نامعتبر")
    cur = _sval(key, row[4]) == "1"
    set_setting(key, "0" if cur else "1", row[2], "certificate", uid)
    page = "ticket" if key.startswith("tk_") else "cert"
    return show_settings(cid, uid, page)


def start_setting(cid, uid, key):
    """ویرایش مقدار متنی/عددی"""
    if not _guard(cid, uid):
        return
    row = _setting_of(key)
    if not row:
        return send(cid, "❌ نامعتبر")
    _, icon, name, kind, dflt, hint = row
    cur = _sval(key, dflt)
    set_state(uid, STATE_CT_SET, {"key": key}, merge=False)
    txt = [f"✏️ {icon} {name}", "━━━━━━━━━━━━━━", "",
           f"📄 فعلی: {cur or '—'}", ""]
    if hint:
        txt += [f"💡 {hint}", ""]
    txt.append("مقدار جدید را بنویسید:")
    txt.append("💡 برای خالی کردن، «-» بفرستید")
    send(cid, "\n".join(txt), kb_cancel())


def handle_setting(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid)
    key = d.get("key")
    size_key = d.get("size_key")        # 📐 اندازه تصویر
    row = _setting_of(key)

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        if size_key:
            return show_sizes(cid, uid)
        return show_settings(cid, uid,
                             "ticket" if str(key).startswith("tk_")
                             else "cert")

    # 📐 اندازه تصویر — کلیدش در CERT_SETTINGS نیست
    if size_key:
        num = normalize_digits(raw).replace("٫", ".").replace(",", ".")
        num = "".join(ch for ch in num if ch.isdigit() or ch == ".")
        try:
            v = float(num)
        except (TypeError, ValueError):
            return send(cid, "⚠️ عدد بفرستید (مثال: 30):", kb_cancel())
        if not (1 <= v <= 300):
            return send(cid, "⚠️ بین ۱ تا ۳۰۰ میلی‌متر:", kb_cancel())
        set_setting(key, f"{v:g}", f"اندازه {ph_label(size_key)}",
                    "certificate", uid)
        clear_state(uid)
        send(cid, f"✅ اندازه {ph_label(size_key)}: {v:g} میلی‌متر",
             kb_remove())
        return show_sizes(cid, uid)

    if not row:
        clear_state(uid)
        return send(cid, "❌ نامعتبر", kb_remove())

    if raw == "-":
        val = ""
    elif row[3] == "num":
        digits = "".join(ch for ch in normalize_digits(raw) if ch.isdigit())
        if not digits:
            return send(cid, "⚠️ فقط عدد بفرستید:", kb_cancel())
        val = str(int(digits))
    elif key == "cert_soffice_path":
        # 🖨️ مسیر LibreOffice — طولانی‌تر از ۲۰۰ و بدون گیومه
        val = raw.strip().strip('"').strip("'")[:400]
    else:
        val = raw[:200]

    set_setting(key, val, row[2], "certificate", uid)
    clear_state(uid)
    log_action(uid, "cert_setting_changed", {"key": key})

    # 🖨️ مسیر لیبره عوض شد → کش را پاک کن و همان‌جا تست کن
    if key == "cert_soffice_path":
        global _LO_BIN, _LO_AT
        _LO_BIN, _LO_AT = None, 0.0
        try:
            from database import clear_settings_cache
            clear_settings_cache()
        except Exception:
            pass
        found = libreoffice_bin(force=True)
        if found:
            send(cid, f"✅ عالی! LibreOffice کار می‌کند 💚\n\n"
                      f"📂 {found}", kb_remove())
        elif val:
            send(cid, "⚠️ این مسیر جواب نداد.\n\n"
                      "💡 باید مسیر کامل خود فایل soffice.exe باشد،\n"
                      "   مثال:\n"
                      "C:\\Program Files\\LibreOffice\\program\\soffice.exe\n\n"
                      "💡 راه ساده: در ویندوز روی میان‌بر LibreOffice\n"
                      "   راست‌کلیک → Properties → مقدار Target را\n"
                      "   کپی کنید.", kb_remove())
        else:
            send(cid, "✅ مسیر دستی پاک شد — ربات خودش می‌گردد",
                 kb_remove())
        return show_engine(cid, uid)

    send(cid, f"✅ ذخیره شد: {val or '—'}", kb_remove())
    return show_settings(cid, uid,
                         "ticket" if key.startswith("tk_") else "cert")


def clean_now(cid, uid):
    """🧹 پاکسازی دستی فوری"""
    if not _guard(cid, uid):
        return
    n, kb = cleanup_files(force=True)
    send(cid, f"🧹 {n} فایل پاک شد ({kb} کیلوبایت آزاد شد)\n\n"
              f"💡 رکوردها و اعتبارسنجی دست‌نخورده باقی ماند.")
    return show_settings(cid, uid, "cert")


# ─────────── 🖼️ مدیریت تصاویر ───────────
ASSET_KEYS = ["sign_img", "sign_img2", "sign_img3", "stamp",
              "logo", "logo2", "logo3", "badge", "watermark"]


def show_assets(cid, uid):
    """🖼️ امضاها، مهر و لوگوها"""
    if not _guard(cid, uid):
        return
    have = all_assets()
    lines = ["🖼️ تصاویر گواهینامه", "━━━━━━━━━━━━━━", "",
             "این تصاویر روی همه گواهینامه‌ها می‌نشینند:", ""]
    btns = []
    for k in ASSET_KEYS:
        ok = k in have
        lines.append(f"{'🟢' if ok else '⚪'} {ph_icon(k)} {ph_label(k)}")
        row = [{"text": f"{'✅' if ok else '➕'} {ph_icon(k)} "
                        f"{ph_label(k)}"[:30],
                "callback_data": f"ctas_{k}"}]
        if ok:
            row.append({"text": "🗑️", "callback_data": f"ctad_{k}"})
        btns.append(row)

    lines += ["", "💡 در قالب ورد بنویسید مثلاً {امضا} یا {مهر}",
              "   تا تصویر همان‌جا بنشیند."]
    btns.append([{"text": "🔙 تنظیمات گواهینامه",
                  "callback_data": "ct_set_cert"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_asset(cid, uid, key):
    """آپلود یک تصویر"""
    if not _guard(cid, uid):
        return
    if key not in ASSET_KEYS:
        return send(cid, "❌ نامعتبر")
    set_state(uid, STATE_CT_ASSET, {"key": key}, merge=False)
    send(cid, (
        f"{ph_icon(key)} {ph_label(key)}\n━━━━━━━━━━━━━━\n\n"
        f"تصویر را بفرستید.\n\n"
        f"💡 ترجیحاً PNG با پس‌زمینه شفاف\n"
        f"💡 برای امضا و مهر، شفافیت مهم است\n\n"
        f"📐 اندازه فعلی روی گواهینامه: {image_mm(key):g} میلی‌متر"
    ), kb_cancel())


def handle_asset(message):
    """دریافت تصویر امضا/مهر/لوگو"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    d = get_state_data(uid)
    key = d.get("key")

    txt = (message.get("text") or "").strip()
    if txt in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_assets(cid, uid)
    if key not in ASSET_KEYS:
        clear_state(uid)
        return send(cid, "❌ نامعتبر", kb_remove())

    doc = message.get("document")
    photo = message.get("photo")
    if not doc and not photo:
        return send(cid, "⚠️ لطفاً تصویر را بفرستید:", kb_cancel())

    from bale_api import get_file_info, download_file
    if doc:
        fid = doc.get("file_id")
        fname = str(doc.get("file_name") or "img.png").lower()
        if not fname.endswith((".png", ".jpg", ".jpeg", ".webp")):
            return send(cid, "⚠️ فقط تصویر PNG یا JPG:", kb_cancel())
        ext = ".png" if fname.endswith(".png") else ".jpg"
    else:
        best = sorted(photo, key=lambda x: x.get("file_size") or 0)[-1]
        fid = best.get("file_id")
        ext = ".jpg"
        send(cid, "💡 نکته: برای شفافیت بهتر، PNG را به‌صورت «فایل» "
                  "بفرستید نه عکس.")

    info = get_file_info(fid)
    if not info.get("ok"):
        return send(cid, "❌ دریافت فایل ناموفق")
    fpath = (info.get("result") or {}).get("file_path")
    data = download_file(fpath) if fpath else None
    if not data:
        return send(cid, "❌ دانلود ناموفق")

    import uuid as _uu
    CERT_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    dest = CERT_ASSET_DIR / f"{key}_{int(time.time())}_{_uu.uuid4().hex[:6]}{ext}"
    try:
        dest.write_bytes(data)
    except Exception as e:
        return send(cid, f"❌ ذخیره ناموفق: {user_error_message(e)}")

    set_asset(key, dest, ph_label(key), uid)
    clear_state(uid)
    log_action(uid, "cert_asset_added", {"key": key})
    send(cid, f"✅ {ph_label(key)} ذخیره شد", kb_remove())
    return show_assets(cid, uid)


def remove_asset(cid, uid, key):
    if not _guard(cid, uid):
        return
    del_asset(key)
    send(cid, f"🗑️ {ph_label(key)} حذف شد")
    return show_assets(cid, uid)


def show_sizes(cid, uid):
    """📐 اندازه تصاویر روی گواهینامه"""
    if not _guard(cid, uid):
        return
    lines = ["📐 اندازه تصاویر (میلی‌متر)", "━━━━━━━━━━━━━━", "",
             "این اندازه‌ها فقط در قالب ورد اعمال می‌شوند:", ""]
    btns = []
    for k in ["qr", "barcode"] + ASSET_KEYS + ["photo"]:
        if k not in PLACEHOLDERS:
            continue
        lines.append(f"▫️ {ph_icon(k)} {ph_label(k)}: {image_mm(k):g} mm")
        btns.append([{"text": f"{ph_icon(k)} {ph_label(k)}: "
                              f"{image_mm(k):g}mm"[:34],
                      "callback_data": f"ctmm_{k}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "ct_set_cert"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_size(cid, uid, key):
    if not _guard(cid, uid):
        return
    if key not in PLACEHOLDERS:
        return send(cid, "❌ نامعتبر")
    set_state(uid, STATE_CT_SET, {"key": f"cert_mm_{key}",
                                  "size_key": key}, merge=False)
    send(cid, (f"📐 اندازه {ph_label(key)}\n━━━━━━━━━━━━━━\n\n"
               f"📄 فعلی: {image_mm(key):g} میلی‌متر\n\n"
               f"عدد جدید را بنویسید (میلی‌متر):\n"
               f"مثال: 30"), kb_cancel())
