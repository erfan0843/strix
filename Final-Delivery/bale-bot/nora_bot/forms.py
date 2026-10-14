"""
📝 فرم‌ساز نورا — فاز ۹ (هسته)

طبق معماری توافق‌شده (طرح دیجی‌فرم):
  ۹ نوع فرم × ۵۵ نوع فیلد × ۸ تنظیم پیشرفته × ۴ روش پرداخت

این فایل شامل:
  • تعریف ۹ نوع فرم
  • کاتالوگ ۵۵+ نوع فیلد در ۱۵ دسته
  • ساختار دیتابیس (۷ جدول با مهاجرت خودکار)
  • پنل ادمین فرم‌ساز + ویزارد ساخت فرم
  • مدیریت فرم (انتشار، ویرایش، کپی، حذف، QR)
  • تنظیمات پیشرفته (۸ بخش) + تنظیمات پرداخت فرم
  • متن‌های قابل ویرایش از پنل ادمین
"""
import json
import random
import string
import time
from datetime import datetime

from config import CURRENCY_LABEL, bot_name, org_name
from database import db_execute, db_scalar, ensure_table, get_setting, set_setting, log
from auth import (
    get_user, set_state, get_state_name, get_state_data,
    update_state_data, clear_state, log_action, normalize_digits,
    is_admin as _is_admin,
)
from bale_api import (
    send, send_or_edit, kb_cancel, kb_remove, BTN_BACK, BTN_SKIP,
)

STATE_FB_CREATE = "fb_create"
STATE_FB_EDIT = "fb_edit"
STATE_FB_FIELD = "fb_field"
STATE_FB_OPTION = "fb_option"
STATE_FB_ADV = "fb_adv"
STATE_FB_SEARCH = "fb_search"
STATE_FB_TEXT = "fb_text"

FORMS_PER_PAGE = 5
FIELDS_PER_PAGE = 8


# ==================== ۹ نوع فرم ====================
FORM_TYPES = {
    "questionnaire": {
        "icon": "📝", "name": "پرسشنامه",
        "desc": "جمع‌آوری اطلاعات و نظرات به‌صورت سوالات باز و بسته",
        "result_btn": "پاسخ‌ها", "anonymous": 0, "multi": 0,
    },
    "survey": {
        "icon": "✅", "name": "نظرسنجی",
        "desc": "سنجش نظر اعضا با نمایش نتایج آماری",
        "result_btn": "نتایج", "anonymous": 1, "multi": 0,
    },
    "registration": {
        "icon": "👤", "name": "ثبت‌نام",
        "desc": "ثبت‌نام در دوره، کارگاه، همایش (با بلیت و پرداخت)",
        "result_btn": "ثبت‌نام‌ها", "anonymous": 0, "multi": 0,
    },
    "election": {
        "icon": "🗳️", "name": "انتخابات",
        "desc": "رأی‌گیری با شمارش آرا (هر نفر یک بار)",
        "result_btn": "نتایج آرا", "anonymous": 1, "multi": 0,
    },
    "datacollect": {
        "icon": "📁", "name": "ثبت اطلاعات",
        "desc": "بانک اطلاعاتی اعضا، آرشیو و بایگانی",
        "result_btn": "رکوردها", "anonymous": 0, "multi": 1,
    },
    "contest": {
        "icon": "🏆", "name": "مسابقه",
        "desc": "مسابقه با امتیازدهی و رتبه‌بندی شرکت‌کنندگان",
        "result_btn": "شرکت‌کنندگان", "anonymous": 0, "multi": 0,
    },
    "attendance": {
        "icon": "✋", "name": "حضور و غیاب",
        "desc": "ثبت حضور اعضا در جلسه یا برنامه",
        "result_btn": "حاضرین", "anonymous": 0, "multi": 1,
    },
    "exam": {
        "icon": "📄", "name": "آزمون",
        "desc": "آزمون با کلید صحیح، نمره‌دهی خودکار و کارنامه",
        "result_btn": "کارنامه‌ها", "anonymous": 0, "multi": 0,
    },
    "order": {
        "icon": "🛒", "name": "ثبت سفارش",
        "desc": "دریافت سفارش کالا یا خدمات همراه با پرداخت",
        "result_btn": "سفارش‌ها", "anonymous": 0, "multi": 1,
    },
}

FORM_STATUS = {
    "draft":    {"icon": "📝", "name": "پیش‌نویس"},
    "active":   {"icon": "🟢", "name": "فعال"},
    "inactive": {"icon": "🚫", "name": "غیرفعال"},
    "archived": {"icon": "📦", "name": "بایگانی"},
}

# ══════════════════════════════════════════════════════════
# 👁️ فاز ۱۸-الف — سطح دسترسی فرم
#
# 🎯 «نیاز نباشه همه فرم‌هارو منتشر کنم که همه ببینن،
#     بعضی فرم‌ها فقط لینکی یا اتصال به بعضی بخش‌های ربات»
# ══════════════════════════════════════════════════════════
VISIBILITY = {
    "public": {
        "icon": "🌍", "name": "عمومی",
        "desc": "در فهرست فرم‌های ربات به همه نمایش داده می‌شود",
    },
    "link": {
        "icon": "🔗", "name": "فقط با لینک",
        "desc": "در فهرست نیست — فقط کسی که لینک دارد می‌بیند",
    },
    "section": {
        "icon": "🧩", "name": "متصل به بخش ربات",
        "desc": "از جای مشخصی در ربات باز می‌شود (مثل «همکاری با ما»)",
    },
    "private": {
        "icon": "🔒", "name": "خصوصی (با کد)",
        "desc": "فقط با کد دعوت یا برای افراد مشخص",
    },
}

# بخش‌هایی از ربات که می‌توان فرم را به آن‌ها وصل کرد
FORM_SECTIONS = {
    "join_us":    {"icon": "🤝", "name": "همکاری با ما"},
    "feedback":   {"icon": "💡", "name": "انتقاد و پیشنهاد"},
    "support":    {"icon": "💬", "name": "پشتیبانی"},
    "membership": {"icon": "🎗️", "name": "عضویت"},
    "donation":   {"icon": "❤️", "name": "حمایت مالی"},
    "volunteer":  {"icon": "🙌", "name": "داوطلبی"},
    "contact":    {"icon": "📞", "name": "تماس با ما"},
}


# ══════════════════════════════════════════════════════════
# ✨ فاز ۱۸-الف — امکانات ویژه هر نوع فرم
#
# 🎯 «هر نوع فرم امکانات ویژه خودشو داره، مثلا آزمون زمان داره
#     یا مسابقه هم زمان داره فرم»
#
# هر ورودی: (کلید_ستون, آیکن, عنوان, نوع, راهنما)
#   نوع: bool = دکمه روشن/خاموش · num = عدد · text = متن · date = تاریخ
# ══════════════════════════════════════════════════════════
TYPE_FEATURES = {
    "exam": [
        ("time_limit_min", "⏱️", "مهلت پاسخ‌دهی", "num",
         "چند دقیقه فرصت دارد؟\n\n۰ = بدون محدودیت"),
        ("pass_score", "🎯", "نمره قبولی", "num",
         "حداقل نمره برای قبولی\n\n۰ = بدون حد نصاب"),
        ("max_attempts", "🔁", "دفعات مجاز شرکت", "num",
         "هر نفر چند بار بتواند آزمون بدهد؟\n\nمثال: 1"),
        ("shuffle_questions", "🔀", "ترتیب تصادفی سوالات", "bool", ""),
        ("shuffle_options", "🎲", "ترتیب تصادفی گزینه‌ها", "bool", ""),
        ("show_score", "💯", "نمایش نمره به شرکت‌کننده", "bool", ""),
        ("show_answers", "✅", "نمایش پاسخ صحیح بعد از آزمون", "bool", ""),
        ("negative_marking", "➖", "نمره منفی", "bool", ""),
    ],
    "contest": [
        ("contest_deadline", "📆", "مهلت شرکت", "date",
         "تاریخ پایان مسابقه (شمسی)\n\nمثال: 1404/12/29"),
        ("time_limit_min", "⏱️", "مهلت پاسخ‌دهی", "num",
         "چند دقیقه فرصت دارد؟\n\n۰ = بدون محدودیت"),
        ("leaderboard_enabled", "🏅", "جدول رتبه‌بندی", "bool", ""),
        ("leaderboard_size", "🔢", "تعداد نفرات جدول", "num",
         "چند نفر برتر نمایش داده شوند؟\n\nمثال: 10"),
        ("speed_tiebreak", "⚡", "سرعت پاسخ = ملاک تساوی", "bool", ""),
        ("prize_text", "🎁", "توضیح جوایز", "text",
         "جوایز مسابقه را بنویسید"),
        ("auto_lottery", "🎲", "قرعه‌کشی بین شرکت‌کنندگان", "bool", ""),
        ("show_score", "💯", "نمایش امتیاز", "bool", ""),
    ],
    "election": [
        ("vote_start", "🟢", "شروع رأی‌گیری", "date",
         "تاریخ شروع (شمسی)\n\nمثال: 1404/06/01"),
        ("vote_end", "🔴", "پایان رأی‌گیری", "date",
         "تاریخ پایان (شمسی)\n\nمثال: 1404/06/10"),
        ("max_choices", "☑️", "حداکثر انتخاب هر نفر", "num",
         "هر رأی‌دهنده چند نفر را انتخاب کند؟\n\nمثال: 1"),
        ("live_results", "📊", "نمایش زنده نتایج", "bool", ""),
        ("voter_list_public", "👥", "فهرست رأی‌دهندگان عمومی", "bool", ""),
    ],
    "order": [
        ("stock_control", "📦", "کنترل موجودی", "bool", ""),
        ("delivery_enabled", "🚚", "دریافت آدرس و ارسال", "bool", ""),
        ("delivery_fee", "💰", "هزینه ارسال", "num",
         f"هزینه ارسال به {CURRENCY_LABEL}\n\n۰ = رایگان"),
        ("order_note_enabled", "📝", "یادداشت سفارش", "bool", ""),
        ("waitlist_enabled", "⏳", "لیست انتظار وقتی تمام شد", "bool", ""),
    ],
    "attendance": [
        ("session_date", "📅", "تاریخ جلسه", "date",
         "تاریخ جلسه (شمسی)\n\nمثال: 1404/06/15"),
        ("checkin_window", "🕐", "بازه مجاز ثبت حضور", "num",
         "تا چند دقیقه بعد از شروع بتواند ثبت کند؟\n\n۰ = بدون محدودیت"),
        ("late_after", "⏰", "بعد از چند دقیقه = تأخیر", "num",
         "مثال: 15"),
    ],
    "survey": [
        ("show_stats_after", "📊", "نمایش آمار بعد از پاسخ", "bool", ""),
        ("live_results", "📈", "نتایج زنده", "bool", ""),
    ],
    "registration": [
        ("waitlist_enabled", "⏳", "لیست انتظار پس از تکمیل ظرفیت",
         "bool", ""),
        ("session_date", "📅", "تاریخ برگزاری", "date",
         "تاریخ (شمسی)\n\nمثال: 1404/06/15"),
    ],
    "questionnaire": [
        ("time_limit_min", "⏱️", "مهلت تکمیل", "num",
         "چند دقیقه؟\n\n۰ = بدون محدودیت"),
    ],
    "datacollect": [
        ("max_attempts", "🔁", "دفعات مجاز ثبت", "num",
         "هر نفر چند رکورد بتواند ثبت کند؟\n\n۰ = نامحدود"),
    ],
}


def type_features(form_type):
    """امکانات ویژه یک نوع فرم"""
    return TYPE_FEATURES.get(form_type or "questionnaire", [])


def feat_value(form, key):
    """مقدار فعلی یک امکان ویژه"""
    return (form or {}).get(key)


def visibility_of(form):
    """سطح دسترسی فرم — با پیش‌فرض امن"""
    v = (form or {}).get("visibility") or "public"
    return v if v in VISIBILITY else "public"


def can_user_open(form, uid=None, via_link=False, code=None):
    """
    🔐 آیا این کاربر اجازه باز کردن فرم را دارد؟
    خروجی: (ok, دلیل)
    """
    if not form:
        return False, "فرم یافت نشد"
    if (form.get("status") or "draft") != "active":
        return False, "این فرم فعلاً فعال نیست"

    vis = visibility_of(form)
    if vis in ("public", "link", "section"):
        # لینکی و بخشی هم با لینک مستقیم باز می‌شوند؛
        # فقط در فهرست عمومی نمایش داده نمی‌شوند.
        return True, ""

    if vis == "private":
        want = (form.get("access_code") or "").strip()
        if want and code and str(code).strip() == want:
            return True, ""
        allowed = str(form.get("allowed_users") or "")
        ids = {x.strip() for x in allowed.split(",") if x.strip()}
        if uid and str(uid) in ids:
            return True, ""
        return False, "این فرم خصوصی است — کد دعوت لازم دارید"

    return True, ""


def list_visible_forms(uid=None, limit=50):
    """فرم‌هایی که در فهرست عمومی نمایش داده می‌شوند"""
    return db_execute(
        "SELECT * FROM forms WHERE status='active' "
        "AND COALESCE(visibility,'public')='public' "
        "ORDER BY id DESC LIMIT ?", (limit,), fetch="all") or []


def forms_for_section(section_key):
    """فرم‌های متصل به یک بخش ربات (مثل «همکاری با ما»)"""
    if not section_key:
        return []
    return db_execute(
        "SELECT * FROM forms WHERE status='active' "
        "AND COALESCE(visibility,'')='section' AND section_key=? "
        "ORDER BY id DESC", (section_key,), fetch="all") or []


# ==================== کاتالوگ ۵۵+ نوع فیلد ====================
# kind = نحوه دریافت پاسخ از کاربر (موتور پر کردن فرم از این استفاده می‌کند)
FIELD_TYPES = {
    # ---------- 👤 اطلاعات شخصی ----------
    "full_name":    {"icon": "👤", "name": "نام و نام خانوادگی", "cat": "personal", "kind": "text",
                     "q": "نام و نام خانوادگی خود را وارد کنید", "cache": "name", "min": 3, "max": 80},
    "first_name":   {"icon": "🔤", "name": "نام", "cat": "personal", "kind": "text",
                     "q": "نام خود را وارد کنید", "cache": "fname", "min": 2, "max": 40},
    "last_name":    {"icon": "🔡", "name": "نام خانوادگی", "cat": "personal", "kind": "text",
                     "q": "نام خانوادگی خود را وارد کنید", "cache": "lname", "min": 2, "max": 40},
    "father_name":  {"icon": "👨", "name": "نام پدر", "cat": "personal", "kind": "text",
                     "q": "نام پدر را وارد کنید", "cache": "father", "min": 2, "max": 40},
    "mother_name":  {"icon": "👩", "name": "نام مادر", "cat": "personal", "kind": "text",
                     "q": "نام مادر را وارد کنید", "min": 2, "max": 40},
    "guardian":     {"icon": "🧑‍🤝‍🧑", "name": "نام ولی/سرپرست", "cat": "personal", "kind": "text",
                     "q": "نام ولی یا سرپرست را وارد کنید", "min": 2, "max": 60},
    "gender":       {"icon": "⚧️", "name": "جنسیت", "cat": "personal", "kind": "choice",
                     "q": "جنسیت خود را انتخاب کنید", "opts": ["مرد", "زن"], "cache": "gender"},
    "age":          {"icon": "🎂", "name": "سن", "cat": "personal", "kind": "number",
                     "q": "سن خود را وارد کنید", "min": 1, "max": 120},
    "birth_date":   {"icon": "📅", "name": "تاریخ تولد", "cat": "personal", "kind": "date",
                     "q": "تاریخ تولد خود را وارد کنید (مثال: 1370/05/12)", "cache": "birth"},
    "marital":      {"icon": "💍", "name": "وضعیت تأهل", "cat": "personal", "kind": "choice",
                     "q": "وضعیت تأهل خود را انتخاب کنید", "opts": ["مجرد", "متأهل"]},

    # ---------- 📞 اطلاعات تماس ----------
    "mobile":       {"icon": "📱", "name": "موبایل", "cat": "contact", "kind": "mobile",
                     "q": "شماره موبایل خود را وارد کنید", "cache": "mobile"},
    "phone":        {"icon": "☎️", "name": "تلفن ثابت", "cat": "contact", "kind": "number",
                     "q": "شماره تلفن ثابت را با کد شهر وارد کنید", "min": 8, "max": 11},
    "email":        {"icon": "✉️", "name": "ایمیل", "cat": "contact", "kind": "email",
                     "q": "آدرس ایمیل خود را وارد کنید", "cache": "email"},
    "address":      {"icon": "📍", "name": "آدرس", "cat": "contact", "kind": "longtext",
                     "q": "آدرس کامل خود را وارد کنید", "cache": "address", "min": 5, "max": 400},
    "postal_code":  {"icon": "📦", "name": "کد پستی", "cat": "contact", "kind": "postal",
                     "q": "کد پستی ۱۰ رقمی خود را وارد کنید"},
    "province_city": {"icon": "🗺️", "name": "استان و شهر", "cat": "contact", "kind": "province_city",
                      "q": "استان و شهر خود را انتخاب کنید", "cache": "city"},
    "telegram_id":  {"icon": "🆔", "name": "شناسه پیام‌رسان", "cat": "contact", "kind": "text",
                     "q": "شناسه (آیدی) خود را وارد کنید", "max": 60},

    # ---------- 🎓 اطلاعات تحصیلی ----------
    "education":    {"icon": "🎓", "name": "مقطع تحصیلی", "cat": "education", "kind": "education",
                     "q": "مقطع تحصیلی خود را انتخاب کنید", "cache": "edu"},
    "field_study":  {"icon": "📚", "name": "رشته تحصیلی", "cat": "education", "kind": "text",
                     "q": "رشته تحصیلی خود را وارد کنید", "max": 80},
    "school_name":  {"icon": "🏫", "name": "نام مدرسه", "cat": "education", "kind": "text",
                     "q": "نام مدرسه را وارد کنید", "max": 80},
    "university":   {"icon": "🏛️", "name": "نام دانشگاه", "cat": "education", "kind": "text",
                     "q": "نام دانشگاه را وارد کنید", "max": 80},
    "teacher_name": {"icon": "🧑‍🏫", "name": "نام استاد/معلم", "cat": "education", "kind": "text",
                     "q": "نام استاد یا معلم را وارد کنید", "max": 80},
    "student_no":   {"icon": "🎫", "name": "شماره دانشجویی", "cat": "education", "kind": "number",
                     "q": "شماره دانشجویی خود را وارد کنید", "max": 20},
    "class_no":     {"icon": "🎒", "name": "شماره کلاس", "cat": "education", "kind": "text",
                     "q": "شماره یا نام کلاس را وارد کنید", "max": 30},
    "grade":        {"icon": "🔢", "name": "پایه تحصیلی", "cat": "education", "kind": "text",
                     "q": "پایه تحصیلی خود را وارد کنید", "max": 30},

    # ---------- 💼 اطلاعات شغلی ----------
    "company":      {"icon": "🏢", "name": "نام شرکت/سازمان", "cat": "job", "kind": "text",
                     "q": "نام شرکت یا سازمان را وارد کنید", "max": 80},
    "job_title":    {"icon": "💼", "name": "شغل / سمت", "cat": "job", "kind": "text",
                     "q": "شغل یا سمت خود را وارد کنید", "cache": "job", "max": 60},
    "personnel_no": {"icon": "🔢", "name": "کد پرسنلی", "cat": "job", "kind": "number",
                     "q": "کد پرسنلی خود را وارد کنید", "max": 20},
    "work_exp":     {"icon": "📈", "name": "سابقه کار (سال)", "cat": "job", "kind": "number",
                     "q": "سابقه کار خود را به سال وارد کنید", "min": 0, "max": 70},

    # ---------- 🆔 اطلاعات هویتی ----------
    "national_id":  {"icon": "🆔", "name": "کد ملی", "cat": "identity", "kind": "national_id",
                     "q": "کد ملی ۱۰ رقمی خود را وارد کنید", "cache": "nid"},
    "org_id":       {"icon": "🏛️", "name": "شناسه ملی سازمان", "cat": "identity", "kind": "number",
                     "q": "شناسه ملی سازمان را وارد کنید", "max": 14},
    "id_serial":    {"icon": "📖", "name": "سریال شناسنامه", "cat": "identity", "kind": "text",
                     "q": "سریال شناسنامه را وارد کنید", "max": 20},
    "id_card_photo": {"icon": "🪪", "name": "تصویر کارت ملی", "cat": "identity", "kind": "photo",
                      "q": "تصویر واضح کارت ملی خود را ارسال کنید"},
    "birth_cert_photo": {"icon": "📖", "name": "تصویر شناسنامه", "cat": "identity", "kind": "photo",
                         "q": "تصویر صفحه اول شناسنامه را ارسال کنید"},
    "personal_photo": {"icon": "👤", "name": "تصویر پرسنلی", "cat": "identity", "kind": "photo",
                       "q": "عکس پرسنلی خود را ارسال کنید"},

    # ---------- 💳 اطلاعات مالی ----------
    "card_number":  {"icon": "💳", "name": "شماره کارت", "cat": "finance", "kind": "card",
                     "q": "شماره کارت ۱۶ رقمی را وارد کنید"},
    "sheba":        {"icon": "🏦", "name": "شماره شبا", "cat": "finance", "kind": "sheba",
                     "q": "شماره شبا را وارد کنید (با یا بدون IR)"},
    "account_no":   {"icon": "🏦", "name": "شماره حساب", "cat": "finance", "kind": "number",
                     "q": "شماره حساب خود را وارد کنید", "max": 24},
    "amount":       {"icon": "💰", "name": "مبلغ", "cat": "finance", "kind": "amount",
                     "q": f"مبلغ را به {CURRENCY_LABEL} وارد کنید"},

    # ---------- 📝 سوالات عمومی ----------
    "short_text":   {"icon": "➖", "name": "متن کوتاه", "cat": "question", "kind": "text",
                     "q": "پاسخ خود را بنویسید", "max": 200},
    "long_text":    {"icon": "📄", "name": "متن چند خطی", "cat": "question", "kind": "longtext",
                     "q": "پاسخ خود را بنویسید", "max": 2000},
    "essay":        {"icon": "📝", "name": "سوال تشریحی", "cat": "question", "kind": "longtext",
                     "q": "پاسخ تشریحی خود را بنویسید", "max": 4000},
    "number":       {"icon": "🔢", "name": "فیلد عددی", "cat": "question", "kind": "number",
                     "q": "یک عدد وارد کنید"},
    "yes_no":       {"icon": "✅", "name": "سوال بله / خیر", "cat": "question", "kind": "choice",
                     "q": "پاسخ خود را انتخاب کنید", "opts": ["بله", "خیر"]},
    "single_choice": {"icon": "⚪", "name": "چند گزینه‌ای (تک انتخاب)", "cat": "question", "kind": "choice",
                      "q": "یکی از موارد زیر را انتخاب کنید", "opts": ["گزینه اول", "گزینه دوم"]},
    "multi_choice": {"icon": "☑️", "name": "چند انتخابی همزمان", "cat": "question", "kind": "multi",
                     "q": "می‌توانید چند مورد را انتخاب کنید", "opts": ["گزینه اول", "گزینه دوم"]},
    "dropdown":     {"icon": "📋", "name": "لیست کشویی", "cat": "question", "kind": "dropdown",
                     "q": "یک مورد را از لیست انتخاب کنید", "opts": ["مورد اول", "مورد دوم"]},
    "quiz":         {"icon": "🎯", "name": "سوال چندگزینه‌ای آزمون", "cat": "question", "kind": "quiz",
                     "q": "پاسخ صحیح را انتخاب کنید", "opts": ["گزینه ۱", "گزینه ۲", "گزینه ۳", "گزینه ۴"]},
    "reason":       {"icon": "❔", "name": "علت مراجعه", "cat": "question", "kind": "longtext",
                     "q": "علت مراجعه خود را بنویسید", "max": 500},

    # ---------- 📅 زمان ----------
    "date":         {"icon": "📅", "name": "تاریخ", "cat": "time", "kind": "date",
                     "q": "تاریخ را وارد کنید (مثال: 1404/06/15)"},
    "time":         {"icon": "⏰", "name": "ساعت و دقیقه", "cat": "time", "kind": "time",
                     "q": "ساعت را وارد کنید (مثال: 18:30)"},
    "datetime":     {"icon": "🕰️", "name": "تاریخ و ساعت", "cat": "time", "kind": "datetime",
                     "q": "تاریخ و ساعت را وارد کنید (مثال: 1404/06/15 18:30)"},
    "duration":     {"icon": "⏱️", "name": "مدت زمان (دقیقه)", "cat": "time", "kind": "number",
                     "q": "مدت زمان را به دقیقه وارد کنید", "min": 0, "max": 100000},

    # ---------- ⭐ امتیازدهی ----------
    "rating_star":  {"icon": "⭐", "name": "کیفیت — ستاره", "cat": "rating", "kind": "rating",
                     "q": "کیفیت را امتیاز دهید", "emoji": "⭐", "scale": 5},
    "rating_heart": {"icon": "❤️", "name": "کیفیت — قلب", "cat": "rating", "kind": "rating",
                     "q": "میزان رضایت خود را مشخص کنید", "emoji": "❤️", "scale": 5},
    "rating_smile": {"icon": "😊", "name": "کیفیت — اموجی", "cat": "rating", "kind": "rating",
                     "q": "حس خود را انتخاب کنید", "emoji": "😊", "scale": 5},
    "rating_like":  {"icon": "👍", "name": "کیفیت — لایک", "cat": "rating", "kind": "rating",
                     "q": "امتیاز خود را ثبت کنید", "emoji": "👍", "scale": 5},
    "rating_10":    {"icon": "💯", "name": "امتیاز ۰ تا ۱۰", "cat": "rating", "kind": "rating",
                     "q": "از ۰ تا ۱۰ امتیاز دهید", "emoji": "🔟", "scale": 10},

    # ---------- 📎 فایل و رسانه ----------
    "photo":        {"icon": "🖼️", "name": "تصویر", "cat": "media", "kind": "photo",
                     "q": "تصویر مورد نظر را ارسال کنید"},
    "file":         {"icon": "📁", "name": "فایل", "cat": "media", "kind": "file",
                     "q": "فایل مورد نظر را ارسال کنید"},
    "receive_file": {"icon": "📥", "name": "دریافت فایل", "cat": "media", "kind": "file",
                     "q": "فایل خواسته‌شده را ارسال کنید"},
    "video":        {"icon": "🎬", "name": "ویدیو", "cat": "media", "kind": "video",
                     "q": "ویدیو مورد نظر را ارسال کنید"},
    "voice":        {"icon": "🎤", "name": "پیام صوتی", "cat": "media", "kind": "voice",
                     "q": "پیام صوتی خود را ارسال کنید"},

    # ---------- 🔐 احراز هویت ----------
    "selfie":       {"icon": "📷", "name": "تصویر احراز هویت (سلفی)", "cat": "auth", "kind": "photo",
                     "q": "سلفی خود را همراه کارت ملی ارسال کنید"},
    "auth_video":   {"icon": "🎥", "name": "فیلم احراز هویت", "cat": "auth", "kind": "video",
                     "q": "ویدیوی کوتاه احراز هویت را ارسال کنید"},
    "signature":    {"icon": "✏️", "name": "امضا دیجیتال", "cat": "auth", "kind": "photo",
                     "q": "تصویر امضای خود را روی کاغذ سفید ارسال کنید"},

    # ---------- 📍 موقعیت ----------
    "location":     {"icon": "📍", "name": "موقعیت مکانی (GPS)", "cat": "location", "kind": "location",
                     "q": "موقعیت مکانی خود را ارسال کنید"},

    # ---------- 🚗 خاص ----------
    "car_plate":    {"icon": "🚗", "name": "شماره پلاک خودرو", "cat": "special", "kind": "plate",
                     "q": "شماره پلاک خودرو را وارد کنید (مثال: 12 ب 345 ایران 10)"},
    "color_pick":   {"icon": "🎨", "name": "انتخاب رنگ", "cat": "special", "kind": "choice",
                     "q": "یک رنگ انتخاب کنید",
                     "opts": ["🔴 قرمز", "🟢 سبز", "🔵 آبی", "🟡 زرد", "⚫ مشکی", "⚪ سفید"]},

    # ---------- 📜 مقررات ----------
    "terms":        {"icon": "📜", "name": "قوانین و مقررات", "cat": "terms", "kind": "confirm",
                     "q": "قوانین و مقررات را مطالعه و تأیید کنید",
                     "has_terms": 1},
    "privacy":      {"icon": "🔒", "name": "حریم خصوصی", "cat": "terms", "kind": "confirm",
                     "q": "سیاست حریم خصوصی را مطالعه و تأیید کنید",
                     "has_terms": 1},
    "newsletter":   {"icon": "📬", "name": "عضویت در خبرنامه", "cat": "terms", "kind": "confirm",
                     "q": "مایل به دریافت اطلاع‌رسانی هستید؟"},

    # ---------- 🎓 ثبت‌نام آماده (با اسم و هزینه) ----------
    "reg_class":    {"icon": "🎓", "name": "ثبت‌نام کلاس", "cat": "ready", "kind": "item",
                     "q": "کلاس مورد نظر خود را انتخاب کنید", "opts": [], "priced": 1},
    "reg_course":   {"icon": "📚", "name": "ثبت‌نام دوره", "cat": "ready", "kind": "item",
                     "q": "دوره مورد نظر خود را انتخاب کنید", "opts": [], "priced": 1},
    "reg_conf":     {"icon": "🎪", "name": "ثبت‌نام همایش", "cat": "ready", "kind": "item",
                     "q": "همایش مورد نظر خود را انتخاب کنید", "opts": [], "priced": 1},
    "reg_workshop": {"icon": "🛠️", "name": "ثبت‌نام کارگاه", "cat": "ready", "kind": "item",
                     "q": "کارگاه مورد نظر خود را انتخاب کنید", "opts": [], "priced": 1},
    "product":      {"icon": "🛒", "name": "انتخاب کالا/خدمت", "cat": "ready", "kind": "item",
                     "q": "کالا یا خدمت مورد نظر را انتخاب کنید", "opts": [], "priced": 1},

    # ---------- ✅ تأیید هویت ----------
    "verify_mobile": {"icon": "✅", "name": "تأیید شماره موبایل (کد پیامکی)",
                      "cat": "verify", "kind": "verify_mobile",
                      "q": "شماره موبایل خود را وارد کنید تا کد تأیید بفرستیم",
                      "cache": "mobile"},
}

# فیلدهایی که آیتم قیمت‌دار دارند (اسم + هزینه + ظرفیت)
PRICED_KINDS = {"item"}


# ==================== 👤 نگاشت فیلد فرم → پروفایل کاربر ====================
"""
وقتی فرمی از نوع «تأییدی ادمین» تکمیل و تأیید می‌شود،
اطلاعات کاربر خودکار در پروفایلش هم ذخیره می‌شود
تا دوباره از او پرسیده نشود.
"""
FIELD_TO_PROFILE = {
    "full_name":      "_full_name",     # به first_name + last_name تقسیم می‌شود
    "first_name":     "first_name",
    "last_name":      "last_name",
    "father_name":    "father_name",
    "mother_name":    "mother_name",
    "gender":         "gender",
    "birth_date":     "birth_date",
    "national_id":    "national_id",
    "mobile":         "mobile",
    "verify_mobile":  "mobile",
    "email":          "email",
    "address":        "address",
    "postal_code":    "postal_code",
    "province_city":  "_province_city",  # «استان - شهر» تفکیک می‌شود
    "education":      "education_level",
    "field_study":    "field_of_study",
    "university":     "university",
    "school_name":    "university",
    "job_title":      "job_title",
    "company":        "company_name",
}


def sync_profile_from_response(rid):
    """
    پر کردن پروفایل کاربر از پاسخ‌های فرم.

    فقط فیلدهای خالی پروفایل پر می‌شوند تا داده‌های
    تأییدشده قبلی بازنویسی نشوند.
    خروجی: تعداد فیلدهای پرشده
    """
    r = db_execute("SELECT * FROM form_responses WHERE id=?", (int(rid),), fetch="one")
    if not r or not r.get("bale_user_id"):
        return 0
    uid = r["bale_user_id"]

    user = db_execute("SELECT * FROM users WHERE bale_user_id=?", (uid,), fetch="one")
    if not user:
        return 0

    rows = db_execute("""SELECT a.value_text, a.field_type FROM form_answers a
        WHERE a.response_id=? AND a.value_text IS NOT NULL AND a.value_text<>''""",
        (int(rid),), fetch="all") or []

    updates = {}
    for a in rows:
        col = FIELD_TO_PROFILE.get(a.get("field_type"))
        val = (a.get("value_text") or "").strip()
        if not col or not val:
            continue

        if col == "_full_name":
            parts = val.split(None, 1)
            if not user.get("first_name") and parts:
                updates["first_name"] = parts[0][:60]
            if not user.get("last_name") and len(parts) > 1:
                updates["last_name"] = parts[1][:60]
            continue

        if col == "_province_city":
            if " - " in val:
                p, c = val.split(" - ", 1)
            else:
                p, c = val, ""
            if not user.get("province") and p:
                updates["province"] = p.strip()[:40]
            if not user.get("city") and c:
                updates["city"] = c.strip()[:40]
            continue

        # فقط اگر پروفایل خالی است
        if not user.get(col):
            updates[col] = val[:200]

    if not updates:
        return 0

    sets = ", ".join(f"{k}=?" for k in updates)
    params = list(updates.values()) + [uid]
    db_execute(f"UPDATE users SET {sets}, updated_at=CURRENT_TIMESTAMP "
               f"WHERE bale_user_id=?", tuple(params))

    try:
        from auth import update_percent
        update_percent(uid)
    except Exception as e:
        log(f"⚠️ به‌روزرسانی درصد پروفایل: {e}")

    log(f"👤 پروفایل کاربر {uid} از فرم پر شد ({len(updates)} فیلد)")
    return len(updates)

FIELD_CATS = [
    ("personal",  "👤", "اطلاعات شخصی"),
    ("contact",   "📞", "اطلاعات تماس"),
    ("education", "🎓", "اطلاعات تحصیلی"),
    ("job",       "💼", "اطلاعات شغلی"),
    ("identity",  "🆔", "اطلاعات هویتی"),
    ("finance",   "💳", "اطلاعات مالی"),
    ("question",  "📝", "سوالات عمومی"),
    ("time",      "📅", "زمان"),
    ("rating",    "⭐", "امتیازدهی"),
    ("media",     "📎", "فایل و رسانه"),
    ("auth",      "🔐", "احراز هویت"),
    ("location",  "📍", "موقعیت"),
    ("special",   "🚗", "خاص"),
    ("terms",     "📜", "مقررات"),
    ("ready",     "🎓", "ثبت‌نام آماده"),
    ("verify",    "✅", "تأیید هویت"),
]

# فیلدهایی که گزینه دارند و ادمین می‌تواند ویرایش کند
OPTION_KINDS = {"choice", "multi", "dropdown", "quiz", "item"}


# ==================== ⚡ افزودن سریع (مثل دیجی‌فرم) ====================
"""
دیجی‌فرم پرکاربردترین فیلدها را مستقیم نشان می‌دهد، نه اول دسته‌بندی.
اینجا هم ۱۶ فیلد پرکاربرد یک‌لمسی‌اند؛ بقیه زیر «همه دسته‌ها».
"""
POPULAR_FIELDS = [
    "full_name", "mobile",
    "national_id", "gender",
    "age", "email",
    "province_city", "address",
    "education", "short_text",
    "long_text", "single_choice",
    "multi_choice", "yes_no",
    "date", "photo",
]

# سوالاتی که به‌طور پیش‌فرض اجباری‌اند
REQUIRED_BY_DEFAULT = {"full_name", "mobile", "verify_mobile", "national_id"}

# 🎁 قالب آماده هر نوع فرم — با یک لمس فرم نیمه‌ساخته می‌شود
FORM_TEMPLATES = {
    "registration": ["full_name", "verify_mobile", "national_id", "gender",
                     "reg_course", "terms"],
    "questionnaire": ["full_name", "mobile", "short_text", "long_text"],
    "survey": ["single_choice", "rating_star", "long_text"],
    "election": ["national_id", "single_choice"],
    "datacollect": ["full_name", "mobile", "province_city", "address"],
    "contest": ["full_name", "mobile", "photo"],
    "attendance": ["full_name", "mobile"],
    "exam": ["full_name", "quiz"],
    "order": ["full_name", "verify_mobile", "address", "product", "terms"],
}

# متن پیش‌فرض قوانین (ادمین می‌تواند تغییر دهد)
DEFAULT_TERMS = (
    "۱. اطلاعات واردشده باید صحیح و متعلق به خود شما باشد.\n"
    "۲. در صورت انصراف، بازگشت وجه تابع قوانین مجموعه است.\n"
    "۳. حضور به‌موقع در برنامه الزامی است.\n"
    "۴. اطلاعات شما نزد ما محفوظ می‌ماند و در اختیار دیگری قرار نمی‌گیرد.\n"
    "۵. مجموعه حق تغییر زمان یا مکان برنامه را با اطلاع‌رسانی قبلی دارد."
)

DEFAULT_PRIVACY = (
    "اطلاعات شما فقط برای همین فرم استفاده می‌شود و در اختیار "
    "شخص یا سازمان دیگری قرار نمی‌گیرد.\n"
    "شما هر زمان می‌توانید درخواست حذف اطلاعات خود را بدهید."
)


# 📜 فاز ۲۳ — قوانین پیش‌فرض متناسب با نوع فرم
#
# 🎯 «متن قوانین و مقررات برای هر فرم مرتبط با اون فرم
#    پیش‌فرضش عوض بشه»
#    قبلاً همه فرم‌ها یک متن یکسان می‌گرفتند — برای آزمون
#    نوشته بود «حضور به‌موقع در برنامه الزامی است»!
TERMS_BY_TYPE = {
    "registration": (
        "۱. اطلاعات واردشده باید صحیح و متعلق به خود شما باشد.\n"
        "۲. ثبت‌نام پس از تکمیل ظرفیت امکان‌پذیر نیست.\n"
        "۳. حضور به‌موقع در برنامه الزامی است.\n"
        "۴. در صورت انصراف، بازگشت وجه تابع قوانین مجموعه است.\n"
        "۵. مجموعه حق تغییر زمان یا مکان را با اطلاع قبلی دارد."
    ),
    "exam": (
        "۱. آزمون باید توسط شخص خودتان انجام شود.\n"
        "۲. استفاده از منبع کمکی یا کمک دیگران مجاز نیست.\n"
        "۳. مهلت پاسخ‌گویی قابل تمدید نیست.\n"
        "۴. پس از ثبت نهایی، امکان تغییر پاسخ‌ها وجود ندارد.\n"
        "۵. تخلف موجب حذف نتیجه آزمون می‌شود."
    ),
    "contest": (
        "۱. شرکت در مسابقه فقط با اطلاعات واقعی مجاز است.\n"
        "۲. هر نفر تنها یک بار می‌تواند شرکت کند.\n"
        "۳. آثار ارسالی باید متعلق به خود شرکت‌کننده باشد.\n"
        "۴. تصمیم داوران قطعی و غیرقابل اعتراض است.\n"
        "۵. مجموعه در انتشار آثار برگزیده مجاز است."
    ),
    "election": (
        "۱. رأی شما محرمانه است و به کسی نشان داده نمی‌شود.\n"
        "۲. هر نفر فقط یک بار می‌تواند رأی دهد.\n"
        "۳. پس از ثبت رأی، امکان تغییر آن وجود ندارد.\n"
        "۴. نتایج پس از پایان زمان رأی‌گیری اعلام می‌شود."
    ),
    "order": (
        "۱. اطلاعات تماس و نشانی باید دقیق باشد.\n"
        "۲. سفارش پس از تأیید پرداخت ثبت می‌شود.\n"
        "۳. زمان تحویل تقریبی است و ممکن است تغییر کند.\n"
        "۴. شرایط مرجوعی تابع قوانین مجموعه است.\n"
        "۵. در صورت ناموجود بودن کالا، وجه بازگردانده می‌شود."
    ),
    "survey": (
        "۱. پاسخ‌های شما فقط برای تحلیل آماری استفاده می‌شود.\n"
        "۲. هویت شما در گزارش‌ها فاش نمی‌شود.\n"
        "۳. شرکت در نظرسنجی کاملاً اختیاری است."
    ),
    "datacollect": (
        "۱. اطلاعات واردشده باید صحیح و به‌روز باشد.\n"
        "۲. اطلاعات شما نزد مجموعه محفوظ می‌ماند.\n"
        "۳. در صورت تغییر اطلاعات، به‌روزرسانی بر عهده شماست."
    ),
    "attendance": (
        "۱. ثبت حضور باید توسط خود شخص انجام شود.\n"
        "۲. ثبت حضور به‌جای دیگری تخلف محسوب می‌شود.\n"
        "۳. حضور پس از زمان مقرر «تأخیر» ثبت می‌شود."
    ),
    "questionnaire": DEFAULT_TERMS,
}


def terms_for_form_type(form_type):
    """
    📜 متن قوانین پیش‌فرض متناسب با نوع فرم.

    اولویت: تنظیم دستی ادمین برای همان نوع ← متن آمادهٔ نوع ←
            متن عمومی
    """
    ft = str(form_type or "questionnaire")
    custom = get_setting(f"form_terms_{ft}", "")
    if custom:
        return custom
    generic = get_setting("form_default_terms", "")
    if ft in TERMS_BY_TYPE:
        return TERMS_BY_TYPE[ft]
    return generic or DEFAULT_TERMS


def default_terms_for(ftype, form_type=None):
    """
    متن پیش‌فرض قوانین/حریم خصوصی — تا ادمین از صفر ننویسد.

    🆕 فاز ۲۳: اگر نوع فرم داده شود، متن مرتبط با همان نوع
       برگردانده می‌شود.
    """
    if ftype == "terms":
        if form_type:
            return terms_for_form_type(form_type)
        return get_setting("form_default_terms", DEFAULT_TERMS)
    if ftype == "privacy":
        return get_setting("form_default_privacy", DEFAULT_PRIVACY)
    return None


def apply_template(fid, ftype):
    """افزودن سوالات آماده این نوع فرم — خروجی: تعداد سوال اضافه‌شده"""
    keys = FORM_TEMPLATES.get(ftype) or []
    if not keys:
        return 0
    order = db_scalar("SELECT COALESCE(MAX(field_order),0) FROM form_fields "
                      "WHERE form_id=?", (int(fid),)) or 0
    added = 0
    for k in keys:
        m = FIELD_TYPES.get(k)
        if not m:
            continue
        order += 1
        opts = m.get("opts")
        row = db_execute("""INSERT INTO form_fields
            (form_id, field_order, field_type, label, options, is_required,
             min_val, max_val, max_files, score, terms_text)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (int(fid), order, k, m.get("q", ""),
             json.dumps(opts, ensure_ascii=False) if opts else None,
             1 if (k in REQUIRED_BY_DEFAULT or m.get("kind") == "confirm") else 0,
             m.get("min"), m.get("max"), 1,
             1 if m.get("kind") == "quiz" else 0,
             default_terms_for(k, ftype)))
        if row:
            added += 1
    if added:
        touch_form(fid)
    return added

# ══════════════════════════════════════════════════════════
# 🔐 فاز ۲۳ — دسترسی کاربر بعد از ثبت فرم
#
# 🎯 درخواست کاربر: «منو مدیریت رویداد کاربر چرا میتونه پاسخ‌هاشو
#    حذف کنه تو فرم؟ اینو کاملا بردار و تنظیمش رو بزار تو فرم‌ساز
#    که کاربر بعد از ثبت و تکمیل دسترسی‌هاش چیه»
#
# 🔴 حذف پاسخ توسط کاربر کاملاً برداشته شد — حتی «برداشتن
#    درخواست» فقط علامت می‌زند و داده پاک نمی‌شود.
# ══════════════════════════════════════════════════════════
AFTER_SUBMIT = {
    "view": {"icon": "👁️", "name": "فقط مشاهده",
             "desc": "پاسخش را می‌بیند ولی نمی‌تواند تغییر دهد"},
    "edit": {"icon": "✏️", "name": "مشاهده و ویرایش",
             "desc": "می‌تواند برگردد و پاسخ‌هایش را اصلاح کند"},
    "withdraw": {"icon": "🚪", "name": "مشاهده و انصراف",
                 "desc": "می‌تواند درخواستش را پس بگیرد "
                         "(داده پاک نمی‌شود، فقط علامت می‌خورد)"},
    "none": {"icon": "🔒", "name": "بسته",
             "desc": "بعد از ثبت، دیگر چیزی نمی‌بیند"},
}


def after_submit_of(form):
    """🔐 دسترسی کاربر بعد از ثبت — با سازگاری با allow_edit قدیمی"""
    v = str((form or {}).get("after_submit") or "").strip()
    if v in AFTER_SUBMIT:
        return v
    # فرم‌های قدیمی: allow_edit روشن بوده → ویرایش
    return "edit" if (form or {}).get("allow_edit") else "view"


def user_can_edit(form):
    return after_submit_of(form) == "edit"


def user_can_withdraw(form):
    return after_submit_of(form) == "withdraw"


def user_can_view(form):
    return after_submit_of(form) != "none"


DISPLAY_MODES = {
    "user_choice": {"icon": "🗂️", "name": "همه سوالات یکجا",
                    "desc": "کاربر فهرست همه سوالات را می‌بیند، هرکدام را خواست "
                            "پر می‌کند و می‌تواند برگردد و ویرایش کند"},
    "one_by_one":  {"icon": "1️⃣", "name": "دونه‌دونه (هر مرحله یک سوال)",
                    "desc": "سوالات پشت سر هم می‌آیند — ساده‌تر ولی بدون بازگشت"},
}

TEXT_DIRS = {
    "rtl": {"icon": "➡️", "name": "راست‌چین (فارسی)"},
    "ltr": {"icon": "⬅️", "name": "چپ‌چین (انگلیسی)"},
}


# ==================== متن‌های قابل ویرایش ====================
FORM_TEXTS = [
    ("form_txt_landing", "🏠 متن صفحه ورود فرم",
     "📋 {title}\n"
     "━━━━━━━━━━━━━━\n\n"
     "{description}\n\n"
     "📝 تعداد سوالات: {fields}\n"
     "⏱️ زمان تقریبی: {minutes} دقیقه"),

    ("form_txt_start", "▶️ پیام شروع پر کردن",
     "✍️ شروع کنیم!\n\n"
     "💡 در هر مرحله می‌توانید با «{back}» به سوال قبل برگردید."),

    ("form_txt_required", "⚠️ پیام فیلد اجباری",
     "⚠️ پاسخ به این سوال اجباری است.\n\nلطفاً پاسخ خود را وارد کنید."),

    ("form_txt_invalid", "❌ پیام پاسخ نامعتبر",
     "❌ پاسخ وارد شده معتبر نیست.\n\n{hint}"),

    ("form_txt_saved", "✅ پیام ثبت موفق",
     "✅ اطلاعات شما با موفقیت ثبت شد\n"
     "━━━━━━━━━━━━━━\n\n"
     "{end_text}\n\n"
     "📋 فرم: {title}\n"
     "🔖 کد پیگیری: {tracking}\n"
     "📅 تاریخ ثبت: {date}"),

    ("form_txt_end_default", "💚 متن پیش‌فرض پایان فرم",
     "💚 سپاس از شما"),

    ("form_txt_closed", "🔒 پیام فرم بسته",
     "🔒 این فرم در حال حاضر پذیرش ندارد.\n\n{reason}"),

    ("form_txt_full", "👥 پیام تکمیل ظرفیت",
     "👥 ظرفیت این فرم تکمیل شده است.\n\n"
     "💡 در صورت ایجاد ظرفیت جدید اطلاع‌رسانی می‌شود."),

    ("form_txt_duplicate", "🔁 پیام پاسخ تکراری",
     "🔁 شما قبلاً این فرم را تکمیل کرده‌اید.\n\n"
     "🔖 کد پیگیری: {tracking}"),

    ("form_txt_not_started", "⏳ پیام شروع نشدن فرم",
     "⏳ زمان پذیرش این فرم هنوز شروع نشده است.\n\n"
     "📅 شروع: {start}"),

    ("form_txt_expired", "⛔ پیام پایان مهلت",
     "⛔ مهلت تکمیل این فرم به پایان رسیده است.\n\n"
     "📅 پایان: {end}"),

    ("form_txt_pay_needed", "💳 پیام نیاز به پرداخت",
     "💳 تکمیل این فرم نیازمند پرداخت است\n"
     "━━━━━━━━━━━━━━\n\n"
     "💰 مبلغ: {amount} {currency}\n\n"
     "{note}"),

    ("form_txt_ticket", "🎫 کپشن بلیت",
     "🎫 بلیت شما\n"
     "━━━━━━━━━━━━━━\n\n"
     "👤 {name}\n"
     "🔖 کد پیگیری: {tracking}\n"
     "📱 کد QR: {qr}\n\n"
     "⚠️ لطفاً این بلیت را همراه داشته باشید."),

    ("form_txt_admin_new", "🔔 اعلان پاسخ جدید به ادمین",
     "🔔 پاسخ جدید\n"
     "━━━━━━━━━━━━━━\n\n"
     "📋 فرم: {title}\n"
     "👤 کاربر: {name}\n"
     "🔖 کد پیگیری: {tracking}\n"
     "📅 {date}"),

    ("form_txt_cancel", "❌ پیام انصراف از فرم",
     "❌ پر کردن فرم لغو شد.\n\n"
     "💡 پاسخ‌های نیمه‌کاره ذخیره شد؛ هر وقت خواستید ادامه دهید."),
]


def seed_form_texts():
    """ثبت متن‌های پیش‌فرض فرم‌ساز"""
    for key, title, default in FORM_TEXTS:
        if not db_execute("SELECT key FROM settings WHERE key=?", (key,), fetch="one"):
            set_setting(key, default, title, "forms")


def render(key, **kw):
    """جایگزینی متغیرها در متن فرم — هرگز KeyError نمی‌دهد"""
    default = next((d for k, t, d in FORM_TEXTS if k == key), "")
    txt = get_setting(key, default) or default
    kw.setdefault("currency", CURRENCY_LABEL)
    kw.setdefault("back", BTN_BACK)
    kw.setdefault("bot", bot_name())
    kw.setdefault("org", org_name())
    try:
        return txt.format(**kw)
    except (KeyError, IndexError, ValueError):
        out = txt
        for k, v in kw.items():
            out = out.replace("{" + k + "}", str(v))
        return out


# ==================== دیتابیس ====================
FORMS_SCHEMA = {
    "owner_id": "INTEGER",
    "form_type": "TEXT DEFAULT 'questionnaire'",
    "title": "TEXT NOT NULL",
    "slug": "TEXT",
    "description": "TEXT",
    "end_text": "TEXT",
    "banner_file_id": "TEXT",
    "logo_file_id": "TEXT",
    "status": "TEXT DEFAULT 'draft'",
    # پرداخت
    "is_free": "INTEGER DEFAULT 1",
    "price": "INTEGER DEFAULT 0",
    "payment_method": "TEXT DEFAULT 'none'",
    # 🆕 فاز ۱۳: روش‌های مجاز در حالت 'multi' (با کاما)
    "payment_methods": "TEXT",
    # ═══════════ 🆕 فاز ۱۵ ═══════════
    "welcome_text": "TEXT",              # صفحه خوش‌آمدگویی
    "cert_enabled": "INTEGER DEFAULT 0",  # گواهینامه برای فرم
    "cert_template": "TEXT",
    "idcard_enabled": "INTEGER DEFAULT 0",  # 🆔 آیدی کارت
    "idcard_title": "TEXT",
    "contact_enabled": "INTEGER DEFAULT 0",  # ارتباط تکمیل‌کننده با ادمین
    # ═══════════ 🆕 فاز ۱۷ — دو آیتم آخر معماری ═══════════
    "webhook_url": "TEXT",                   # 🔗 وبهوک و رخدادها
    "webhook_events": "TEXT",                # completed,paid
    "workflow_enabled": "INTEGER DEFAULT 0",  # 🔀 گردش کار
    "workflow_steps": "TEXT",                # JSON مراحل تأیید
    "payment_card_id": "INTEGER",
    "payment_gateway_id": "INTEGER",
    "payment_verification": "TEXT DEFAULT 'manual'",
    "payment_note": "TEXT",
    # 💳 آیا مبلغ در ابتدای فرم به کاربر نشان داده شود؟ (پیش‌فرض: خیر)
    "show_price_upfront": "INTEGER DEFAULT 0",
    # تنظیمات پیشرفته
    "notify_admins": "INTEGER DEFAULT 1",
    "text_dir": "TEXT DEFAULT 'rtl'",
    # 🔴 فاز ۱۵ — درخواست کاربر: «فرم کلا تک مرحله ای بشه، ینی کاربر
    #    هر مرحله یک سوال جواب بده، پیش فرض این باشه»
    "display_mode": "TEXT DEFAULT 'one_by_one'",
    "limit_enabled": "INTEGER DEFAULT 0",
    "max_responses": "INTEGER DEFAULT 0",
    "ticket_enabled": "INTEGER DEFAULT 0",
    "ticket_template": "TEXT DEFAULT 'classic'",
    "start_at": "TEXT",
    "end_at": "TEXT",
    # دسترسی
    "require_auth": "INTEGER DEFAULT 1",
    "require_profile": "INTEGER DEFAULT 0",
    # 👤 فرم تأییدی ادمین: پاسخ باید تأیید شود و پروفایل کاربر هم پر می‌شود
    "needs_approval": "INTEGER DEFAULT 0",
    "fill_profile": "INTEGER DEFAULT 1",
    # 📱 روش تأیید شماره: contact / otp / both
    "phone_verify_mode": "TEXT DEFAULT 'both'",
    "one_per_user": "INTEGER DEFAULT 1",
    "allow_edit": "INTEGER DEFAULT 0",
    # 🆕 فاز ۲۳ — دسترسی کاربر بعد از ثبت فرم
    #    «کاربر بعد از ثبت و تکمیل، دسترسی‌هاش چیه»
    #    view | edit | withdraw | none
    "after_submit": "TEXT DEFAULT 'view'",
    "anonymous": "INTEGER DEFAULT 0",
    "show_progress": "INTEGER DEFAULT 1",
    # اتصال به رویداد
    "event_id": "INTEGER",
    # 🎉 فاز ۳۳ — چه کسی فرم وابسته به رویداد را ببیند
    #    registered (پیش‌فرض) · attended · public
    "event_access": "TEXT DEFAULT 'registered'",

    # ═══════════ 🆕 فاز ۱۸-الف — دسترسی فرم ═══════════
    # 🎯 «نیاز نباشه همه فرم‌ها رو منتشر کنم که همه ببینن»
    #   public  → در لیست فرم‌های ربات دیده می‌شود
    #   link    → فقط با لینک مستقیم باز می‌شود (در لیست نیست)
    #   section → به یک بخش ربات وصل است (مثل «همکاری با ما»)
    #   private → فقط با کد دعوت / افراد مشخص
    "visibility": "TEXT DEFAULT 'public'",
    "section_key": "TEXT",        # کدام بخش ربات (join_us, ...)
    "access_code": "TEXT",        # برای visibility=private
    "allowed_users": "TEXT",      # شناسه‌های مجاز با کاما

    # ═══════════ 🆕 فاز ۱۸-الف — پرداخت مرحله‌ای ═══════════
    "payment_plan_id": "INTEGER",

    # ═══════════ 🆕 فاز ۱۸-الف — امکانات ویژه هر نوع فرم ═══════════
    # 📄 آزمون
    "time_limit_min": "INTEGER DEFAULT 0",     # مهلت پاسخ (دقیقه)
    "pass_score": "INTEGER DEFAULT 0",         # نمره قبولی
    "shuffle_questions": "INTEGER DEFAULT 0",  # ترتیب تصادفی سوال
    "shuffle_options": "INTEGER DEFAULT 0",    # ترتیب تصادفی گزینه
    "show_answers": "INTEGER DEFAULT 1",       # نمایش پاسخ صحیح
    "show_score": "INTEGER DEFAULT 1",         # نمایش نمره
    # ۰ = نامحدود. ⚠️ پیش‌فرض عمداً ۰ است؛ اگر ۱ باشد هر فرمی که
    #    کاربر یک‌بار پر کرده از فهرست عمومی ناپدید می‌شود.
    "max_attempts": "INTEGER DEFAULT 0",       # دفعات مجاز شرکت
    "negative_marking": "INTEGER DEFAULT 0",   # نمره منفی
    # 🏆 مسابقه
    "contest_deadline": "TEXT",                # مهلت شرکت (شمسی)
    "leaderboard_enabled": "INTEGER DEFAULT 1",
    "leaderboard_size": "INTEGER DEFAULT 10",
    "prize_text": "TEXT",
    "auto_lottery": "INTEGER DEFAULT 0",       # قرعه‌کشی خودکار
    "speed_tiebreak": "INTEGER DEFAULT 1",     # سرعت = ملاک تساوی
    # 🗳️ انتخابات
    "vote_start": "TEXT",
    "vote_end": "TEXT",
    "live_results": "INTEGER DEFAULT 0",       # نتیجه زنده
    "max_choices": "INTEGER DEFAULT 1",        # حداکثر انتخاب
    "voter_list_public": "INTEGER DEFAULT 0",
    # 🛒 سفارش
    "stock_control": "INTEGER DEFAULT 0",      # کنترل موجودی
    "delivery_enabled": "INTEGER DEFAULT 0",   # آدرس و ارسال
    "delivery_fee": "INTEGER DEFAULT 0",
    "order_note_enabled": "INTEGER DEFAULT 1",
    # ✋ حضور و غیاب
    "session_date": "TEXT",
    "checkin_window": "INTEGER DEFAULT 0",     # بازه مجاز (دقیقه)
    "late_after": "INTEGER DEFAULT 0",         # بعد از N دقیقه = تأخیر
    # ✅ نظرسنجی
    "show_stats_after": "INTEGER DEFAULT 1",   # نمایش آمار بعد پاسخ
    # 👤 ثبت‌نام
    "waitlist_enabled": "INTEGER DEFAULT 0",   # لیست انتظار

    # آمار
    "responses_count": "INTEGER DEFAULT 0",
    "views_count": "INTEGER DEFAULT 0",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

FIELDS_SCHEMA = {
    "form_id": "INTEGER NOT NULL",
    "field_order": "INTEGER DEFAULT 0",
    "field_type": "TEXT NOT NULL",
    "label": "TEXT",
    "description": "TEXT",
    "help_text": "TEXT",
    "placeholder": "TEXT",
    "media_file_id": "TEXT",
    "media_type": "TEXT",
    "options": "TEXT",
    "correct_option": "TEXT",
    "score": "INTEGER DEFAULT 0",
    "is_required": "INTEGER DEFAULT 0",
    "min_val": "INTEGER",
    "max_val": "INTEGER",
    "max_files": "INTEGER DEFAULT 1",
    "allowed_types": "TEXT",
    "default_value": "TEXT",
    "condition_field_id": "INTEGER",
    "condition_operator": "TEXT",
    "condition_value": "TEXT",
    # 🎓 آیتم‌های قیمت‌دار (ثبت‌نام کلاس/دوره/همایش/کالا)
    # JSON: [{"title":"دوره الف","price":500000,"capacity":30,"booked":0,"desc":""}]
    "items": "TEXT",
    # 🆕 فاز ۲۳ — انتخاب چند مورد هزینه‌دار
    #    «مثلا من مورد ۱ و مورد ۲ رو انتخاب کنم و بعد تایید کنم»
    "multi_item": "INTEGER DEFAULT 0",   # ۱ = چند مورد قابل انتخاب
    "max_items": "INTEGER DEFAULT 0",    # سقف تعداد · ۰ = نامحدود
    # 📜 متن قوانین/حریم خصوصی که کاربر باید تأیید کند
    "terms_text": "TEXT",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

RESPONSES_SCHEMA = {
    "form_id": "INTEGER NOT NULL",
    "bale_user_id": "INTEGER",
    "user_id": "INTEGER",
    "status": "TEXT DEFAULT 'draft'",
    "tracking_code": "TEXT",
    "qr_code": "TEXT",
    "amount": "INTEGER DEFAULT 0",
    "payment_status": "TEXT DEFAULT 'none'",
    "transaction_id": "INTEGER",
    "receipt_id": "INTEGER",
    # 🆕 فاز ۱۸-الف — پرداخت فرم‌ساز
    #   🔴 بدون این دو ستون، UPDATEهای موتور پرداخت بی‌صدا شکست
    #      می‌خوردند و پاسخ کاربر در pending_payment گیر می‌کرد.
    "amount_paid": "INTEGER DEFAULT 0",
    "payment_payload": "TEXT",
    "score": "INTEGER DEFAULT 0",
    "max_score": "INTEGER DEFAULT 0",
    "tags": "TEXT",
    "admin_note": "TEXT",
    "reviewed_by": "INTEGER",
    "reviewed_at": "TEXT",
    "started_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "completed_at": "TEXT",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

ANSWERS_SCHEMA = {
    "response_id": "INTEGER NOT NULL",
    "form_id": "INTEGER",
    "field_id": "INTEGER",
    "field_type": "TEXT",
    "value_text": "TEXT",
    "value_number": "REAL",
    "value_options": "TEXT",
    "file_id": "TEXT",
    "file_type": "TEXT",
    "file_name": "TEXT",
    "is_correct": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

FORM_ADMINS_SCHEMA = {
    "form_id": "INTEGER NOT NULL",
    "bale_user_id": "INTEGER NOT NULL",
    "role": "TEXT DEFAULT 'editor'",
    "added_by": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

FIELD_CACHE_SCHEMA = {
    "bale_user_id": "INTEGER NOT NULL",
    "cache_key": "TEXT NOT NULL",
    "value": "TEXT",
    "used_count": "INTEGER DEFAULT 1",
    "last_used_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

FORM_TAGS_SCHEMA = {
    "form_id": "INTEGER",
    "name": "TEXT NOT NULL",
    "color": "TEXT DEFAULT '⚪'",
    "created_by": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}


def init_form_tables():
    """ساخت/مهاجرت جدول‌های فرم‌ساز"""
    ensure_table("forms", FORMS_SCHEMA)
    ensure_table("form_fields", FIELDS_SCHEMA)
    ensure_table("form_responses", RESPONSES_SCHEMA)
    ensure_table("form_answers", ANSWERS_SCHEMA)
    ensure_table("form_admins", FORM_ADMINS_SCHEMA)
    ensure_table("user_field_cache", FIELD_CACHE_SCHEMA)
    ensure_table("form_tags", FORM_TAGS_SCHEMA)

    for q in [
        "CREATE INDEX IF NOT EXISTS idx_forms_status ON forms(status)",
        "CREATE INDEX IF NOT EXISTS idx_forms_owner ON forms(owner_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_forms_slug ON forms(slug) WHERE slug IS NOT NULL AND slug<>''",
        "CREATE INDEX IF NOT EXISTS idx_ff_form ON form_fields(form_id, field_order)",
        "CREATE INDEX IF NOT EXISTS idx_fr_form ON form_responses(form_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_fr_user ON form_responses(bale_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_fr_track ON form_responses(tracking_code)",
        "CREATE INDEX IF NOT EXISTS idx_fa_resp ON form_answers(response_id)",
        "CREATE INDEX IF NOT EXISTS idx_fa_field ON form_answers(field_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_cache ON user_field_cache(bale_user_id, cache_key, value)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_fadmin ON form_admins(form_id, bale_user_id)",
    ]:
        db_execute(q)

    seed_form_texts()
    # 🔴 فاز ۱۸-الف — مهاجرت: فرم‌های قدیمی visibility ندارند (NULL)
    #    بدون این، همه فرم‌های موجود ناگهان از فهرست عمومی غیب می‌شدند.
    try:
        n_fix = db_scalar("SELECT COUNT(*) FROM forms "
                          "WHERE visibility IS NULL OR visibility=''") or 0
        if n_fix:
            db_execute("UPDATE forms SET visibility='public' "
                       "WHERE visibility IS NULL OR visibility=''")
            log(f"♻️ {n_fix} فرم قدیمی روی دسترسی «عمومی» تنظیم شد")
    except Exception as e:
        log(f"⚠️ مهاجرت visibility: {e}")

    log("✅ جدول‌های فرم‌ساز آماده شد")


# ==================== ابزارها ====================
def _guard(cid, uid):
    if not _is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    return True


def gen_slug(n=9):
    return "f" + "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def gen_tracking():
    """کد پیگیری یکتا — مثل TL1307BVUC1981"""
    for _ in range(30):
        code = ("TL" + "".join(random.choices(string.digits, k=4))
                + "".join(random.choices(string.ascii_uppercase, k=4))
                + "".join(random.choices(string.digits, k=4)))
        if not db_execute("SELECT id FROM form_responses WHERE tracking_code=?",
                          (code,), fetch="one"):
            return code
    return f"TL{int(time.time())}"


def gen_qr_code():
    for _ in range(30):
        code = "w" + "".join(random.choices(string.ascii_lowercase + string.digits, k=9))
        if not db_execute("SELECT id FROM form_responses WHERE qr_code=?",
                          (code,), fetch="one"):
            return code
    return f"w{int(time.time())}"


def clean_slug(raw):
    """فقط حروف انگلیسی، عدد، خط تیره و زیرخط"""
    s = (raw or "").strip().lower()
    out = "".join(ch for ch in s if ch.isascii() and (ch.isalnum() or ch in "-_"))
    return out[:40]


def get_form(fid):
    if not fid:
        return None
    return db_execute("SELECT * FROM forms WHERE id=?", (int(fid),), fetch="one")


def get_form_by_slug(slug):
    if not slug:
        return None
    return db_execute("SELECT * FROM forms WHERE slug=?", (str(slug).strip(),), fetch="one")


def get_fields(fid):
    return db_execute(
        "SELECT * FROM form_fields WHERE form_id=? ORDER BY field_order ASC, id ASC",
        (int(fid),), fetch="all") or []


def get_field(field_id):
    return db_execute("SELECT * FROM form_fields WHERE id=?",
                      (int(field_id),), fetch="one")


def field_meta(ftype):
    """اطلاعات نوع فیلد — همیشه dict برمی‌گرداند"""
    return FIELD_TYPES.get(ftype) or {
        "icon": "❔", "name": ftype or "نامشخص", "cat": "question",
        "kind": "text", "q": "پاسخ خود را وارد کنید",
    }


def field_label(f):
    """متن سوالی که به کاربر نشان داده می‌شود"""
    if f.get("label"):
        return f["label"]
    return field_meta(f.get("field_type")).get("q", "پاسخ خود را وارد کنید")


def parse_options(f):
    """گزینه‌های فیلد — لیست رشته"""
    raw = f.get("options")
    if raw:
        try:
            v = json.loads(raw)
            if isinstance(v, list):
                return [str(x) for x in v if str(x).strip()]
        except (ValueError, TypeError):
            pass
    return list(field_meta(f.get("field_type")).get("opts") or [])


def set_options(field_id, opts):
    db_execute("UPDATE form_fields SET options=? WHERE id=?",
               (json.dumps(list(opts), ensure_ascii=False), int(field_id)))


# ==================== 🎓 آیتم‌های قیمت‌دار ====================
def parse_items(f):
    """
    آیتم‌های ثبت‌نام یک فیلد.
    خروجی: [{"title","price","capacity","booked","desc"}]
    """
    raw = (f or {}).get("items")
    if not raw:
        return []
    try:
        v = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(v, list):
        return []
    out = []
    for x in v:
        if not isinstance(x, dict) or not str(x.get("title") or "").strip():
            continue
        out.append({
            "title": str(x.get("title")).strip()[:80],
            "price": int(x.get("price") or 0),
            "capacity": int(x.get("capacity") or 0),
            "booked": int(x.get("booked") or 0),
            "desc": str(x.get("desc") or "")[:200],
        })
    return out


def set_items(field_id, items):
    db_execute("UPDATE form_fields SET items=? WHERE id=?",
               (json.dumps(list(items), ensure_ascii=False), int(field_id)))


def item_is_full(it):
    cap = int(it.get("capacity") or 0)
    return cap > 0 and int(it.get("booked") or 0) >= cap


def item_label(it, with_price=True):
    """برچسب نمایشی آیتم برای دکمه"""
    s = it.get("title") or ""
    if with_price:
        p = int(it.get("price") or 0)
        s += f" — {fmt_amount(p)} {CURRENCY_LABEL}" if p else " — رایگان"
    if item_is_full(it):
        s = "🚫 " + s + " (تکمیل)"
    elif int(it.get("capacity") or 0) > 0:
        left = int(it["capacity"]) - int(it.get("booked") or 0)
        s += f" ({left} جا)"
    return s


def chosen_items(field, answer_row):
    """
    🧾 آیتم‌های انتخاب‌شده یک فیلد.

    🆕 فاز ۲۳: کاربر می‌تواند چند مورد انتخاب کند، پس پاسخ
       ممکن است چند عنوان داشته باشد (در value_options).
       نسخهٔ تک‌انتخابی هم پشتیبانی می‌شود.
    """
    items = parse_items(field)
    if not items:
        return []
    titles = []
    raw = (answer_row or {}).get("value_options")
    if raw:
        try:
            v = json.loads(raw)
            if isinstance(v, list):
                titles = [str(x) for x in v]
        except (ValueError, TypeError):
            titles = []
    if not titles:
        t = (answer_row or {}).get("value_text") or ""
        # چند موردی که با «، » به هم چسبیده‌اند
        titles = [x.strip() for x in str(t).split("،")] if t else []
    out = []
    for t in titles:
        for it in items:
            if it["title"] == t:
                out.append(it)
                break
    return out


def form_total_price(fid, rid=None):
    """
    مبلغ کل فرم = هزینه ثابت فرم + آیتم‌های انتخاب‌شده کاربر.
    اگر rid ندهیم فقط هزینه ثابت برمی‌گردد.

    🆕 فاز ۲۳: چند آیتم هم‌زمان جمع زده می‌شود.
    """
    form = get_form(fid)
    if not form:
        return 0
    total = int(form.get("price") or 0) if (form.get("payment_method") or "none") != "none" else 0
    if not rid:
        return total
    rows = db_execute("""SELECT a.value_text, a.value_options, a.field_id
        FROM form_answers a WHERE a.response_id=?""",
        (int(rid),), fetch="all") or []
    for a in rows:
        fl = get_field(a.get("field_id"))
        if not fl or field_meta(fl.get("field_type")).get("kind") != "item":
            continue
        for it in chosen_items(fl, a):
            total += int(it.get("price") or 0)
    return total


def price_preview(fid):
    """
    پیش‌نمایش هزینه برای «اول فرم به کاربر بگو هزینه دارد».
    خروجی: (has_cost, text)
    """
    form = get_form(fid)
    if not form:
        return False, ""
    base = int(form.get("price") or 0) if (form.get("payment_method") or "none") != "none" else 0
    ranges = []
    for f in get_fields(fid):
        if field_meta(f.get("field_type")).get("kind") != "item":
            continue
        prices = [int(i.get("price") or 0) for i in parse_items(f)]
        if prices:
            ranges.append((min(prices), max(prices)))

    if not base and not ranges:
        return False, "🎁 این فرم رایگان است"

    lo = base + sum(r[0] for r in ranges)
    hi = base + sum(r[1] for r in ranges)
    if lo == hi:
        return True, f"💳 هزینه: {fmt_amount(lo)} {CURRENCY_LABEL}"
    return True, (f"💳 هزینه: از {fmt_amount(lo)} تا {fmt_amount(hi)} {CURRENCY_LABEL}\n"
                  f"   (بسته به انتخاب شما — در پایان محاسبه می‌شود)")


def form_can_manage(uid, form):
    """آیا کاربر اجازه مدیریت این فرم را دارد؟"""
    if not form:
        return False
    if not _is_admin(uid):
        return False
    from config import SUPER_ADMIN_ID
    if uid == SUPER_ADMIN_ID or form.get("owner_id") == uid:
        return True
    row = db_execute("SELECT id FROM form_admins WHERE form_id=? AND bale_user_id=?",
                     (form["id"], uid), fetch="one")
    return bool(row)


def touch_form(fid):
    db_execute("UPDATE forms SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (int(fid),))


def recount_responses(fid):
    n = db_scalar("SELECT COUNT(*) FROM form_responses WHERE form_id=? "
                  "AND status IN ('completed','confirmed')", (int(fid),))
    db_execute("UPDATE forms SET responses_count=? WHERE id=?", (n, int(fid)))
    return n


def form_link(form):
    """
    🔗 لینک اختصاصی فرم — قابل اشتراک و اسکن.

    یوزرنیم از config.deep_link می‌آید (.env ← پنل ← getMe)
    تا با عوض شدن آیدی/توکن ربات خودکار درست بماند.
    """
    slug = form.get("slug") or f"id{form.get('id')}"
    try:
        from config import deep_link
        u = deep_link(f"form_{slug}")
        if u:
            return u
    except Exception:
        pass
    return f"/start form_{slug}"


def fmt_amount(v):
    """
    💰 نمایش مبلغ — ریال، بدون تبدیل (به config.money وصل است).

    ⚠️ همه مبالغ در کل ربات ریال‌اند: ورودی ادمین، دیتابیس،
       نمایش به کاربر و مبلغ ارسالی به درگاه — همگی یک عدد.
    """
    from config import money
    return money(v, with_unit=False)


def status_badge(form):
    st = FORM_STATUS.get(form.get("status") or "draft", FORM_STATUS["draft"])
    return f"{st['icon']} {st['name']}"


# ==================== پنل فرم‌ساز ====================
def show_panel(cid, uid):
    """👨‍💼 پنل فرم‌ساز نورا — طبق منوی نهایی توافق‌شده"""
    if not _guard(cid, uid):
        return

    from config import SUPER_ADMIN_ID
    if uid == SUPER_ADMIN_ID:
        total = db_scalar("SELECT COUNT(*) FROM forms")
        active = db_scalar("SELECT COUNT(*) FROM forms WHERE status='active'")
        resp = db_scalar("SELECT COUNT(*) FROM form_responses "
                         "WHERE status IN ('completed','confirmed')")
    else:
        total = db_scalar("SELECT COUNT(*) FROM forms WHERE owner_id=?", (uid,))
        active = db_scalar("SELECT COUNT(*) FROM forms WHERE owner_id=? AND status='active'",
                           (uid,))
        resp = db_scalar("SELECT COUNT(*) FROM form_responses r "
                         "JOIN forms f ON f.id=r.form_id WHERE f.owner_id=? "
                         "AND r.status IN ('completed','confirmed')", (uid,))

    # پیش‌نویس‌ها و پاسخ‌های تازه
    if uid == SUPER_ADMIN_ID:
        drafts = db_scalar("SELECT COUNT(*) FROM forms "
                           "WHERE status='draft'") or 0
        new_resp = db_scalar(
            "SELECT COUNT(*) FROM form_responses WHERE "
            "status IN ('completed','confirmed') AND "
            "created_at >= datetime('now','-7 day')") or 0
        pending = db_scalar("SELECT COUNT(*) FROM form_responses "
                            "WHERE status='pending_review'") or 0
    else:
        drafts = db_scalar("SELECT COUNT(*) FROM forms "
                           "WHERE owner_id=? AND status='draft'", (uid,)) or 0
        new_resp = db_scalar(
            "SELECT COUNT(*) FROM form_responses r JOIN forms f "
            "ON f.id=r.form_id WHERE f.owner_id=? AND "
            "r.status IN ('completed','confirmed') AND "
            "r.created_at >= datetime('now','-7 day')", (uid,)) or 0
        pending = db_scalar(
            "SELECT COUNT(*) FROM form_responses r JOIN forms f "
            "ON f.id=r.form_id WHERE f.owner_id=? AND "
            "r.status='pending_review'", (uid,)) or 0

    lines = ["📝 فرم‌ساز نورا", "━━━━━━━━━━━━━━", "",
             f"📋 فرم‌های شما: {total}",
             f"   🟢 فعال: {active}   📝 پیش‌نویس: {drafts}",
             f"📊 پاسخ‌های دریافتی: {resp}"]
    if new_resp:
        lines.append(f"   🆕 {new_resp} پاسخ در ۷ روز اخیر")
    if pending:
        lines += ["", f"🔴 {pending} پاسخ منتظر تأیید شماست"]
    if total == 0:
        lines += ["", "💡 هنوز فرمی نساخته‌اید —",
                  "با «➕ ساخت فرم جدید» شروع کنید."]
    lines += ["", "از منوی زیر انتخاب کنید:"]

    send_or_edit(cid, "\n".join(lines), kb_panel({
        "total": total, "drafts": drafts, "new_resp": new_resp,
        "pending": pending}))


def kb_panel(stats=None):
    """
    📝 پنل فرم‌ساز — فاز ۱۶: خلوت‌تر و کاربردی‌تر

    «ایجاد فرم» بالا و برجسته · پاسخ‌های نخوانده با badge
    · گزارش و ادمین در یک ردیف · تنظیمات ته صف
    """
    st = stats or {}
    n_new = st.get("new_resp") or 0
    n_draft = st.get("drafts") or 0

    resp_lbl = "📊 پاسخ‌های دریافتی"
    if n_new:
        resp_lbl += f" 🔴{n_new}"
    list_lbl = f"📋 فرم‌های من ({st.get('total', 0)})"
    if n_draft:
        list_lbl += f" · {n_draft} پیش‌نویس"

    rows = [
        [{"text": "➕ ساخت فرم جدید", "callback_data": "fb_new"}],
        [{"text": list_lbl, "callback_data": "fb_list"}],
        [{"text": resp_lbl, "callback_data": "fb_allresp"}],
    ]
    n_pend = st.get("pending") or 0
    if n_pend:
        rows.append([{"text": f"🔀 صف تأیید پاسخ‌ها 🔴{n_pend}",
                      "callback_data": "fb_approvals"}])
    return {"inline_keyboard": rows + [
        [{"text": "📈 گزارش و آمار", "callback_data": "fb_allstats"},
         {"text": "👥 ادمین‌ها", "callback_data": "fb_admins"}],
        [{"text": "⚙️ تنظیمات فرم‌ساز", "callback_data": "fb_settings"}],
        [{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}],
    ]}


# ==================== ساخت فرم — مرحله ۱: نوع ====================
def start_create(cid, uid):
    if not _guard(cid, uid):
        return
    import permissions as _pm
    if not _pm.require(cid, uid, "fm_create", send):
        return
    btns = []
    row = []
    for key, t in FORM_TYPES.items():
        row.append({"text": f"{t['icon']} {t['name']}", "callback_data": f"fbt_{key}"})
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([{"text": "📋 کپی از فرم موجود", "callback_data": "fb_copyfrom"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "fb_panel"}])

    send_or_edit(cid, (
        "➕ ایجاد فرم جدید\n"
        "━━━━━━━━━━━━━━\n\n"
        "نوع فرم را انتخاب کنید:\n\n"
        + "\n".join(f"{t['icon']} {t['name']} — {t['desc']}"
                    for t in FORM_TYPES.values())
    ), {"inline_keyboard": btns})


def pick_type(cid, uid, ftype):
    if not _guard(cid, uid):
        return
    if ftype not in FORM_TYPES:
        return send(cid, "❌ نوع نامعتبر")
    t = FORM_TYPES[ftype]
    set_state(uid, STATE_FB_CREATE, {"form_type": ftype, "step": 0}, merge=False)
    send(cid, (
        f"{t['icon']} فرم {t['name']}\n"
        "━━━━━━━━━━━━━━\n\n"
        "📝 عنوان فرم را بنویسید:\n\n"
        "مثال: ثبت‌نام کارگاه فن بیان"
    ), kb_cancel())


def handle_create_input(message):
    """ویزارد ساخت فرم: عنوان → لینک اختصاصی"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    data = get_state_data(uid)
    step = int(data.get("step") or 0)

    if text in (BTN_BACK, "🔙 بازگشت"):
        if step == 0:
            clear_state(uid)
            send(cid, "❌ لغو شد", kb_remove())
            return start_create(cid, uid)
        update_state_data(uid, {"step": step - 1})
        return _ask_create_step(cid, uid, step - 1)

    if step == 0:
        if len(text) < 3:
            return send(cid, "⚠️ عنوان باید حداقل ۳ حرف باشد.\n\nدوباره بنویسید:",
                        kb_cancel())
        update_state_data(uid, {"title": text[:120], "step": 1})
        return _ask_create_step(cid, uid, 1)

    if step == 1:
        slug = ""
        if text not in (BTN_SKIP, "⏭️ رد کردن", "-"):
            slug = clean_slug(text)
            if slug and db_execute("SELECT id FROM forms WHERE slug=?", (slug,), fetch="one"):
                return send(cid, (
                    "⚠️ این لینک قبلاً استفاده شده است.\n\n"
                    "لینک دیگری بنویسید یا «رد کردن» را بزنید:"
                ), _kb_slug())
        return _finish_create(cid, uid, slug)

    clear_state(uid)
    return send(cid, "⚠️ خطای مرحله — دوباره شروع کنید", kb_remove())


def _kb_slug():
    return {"keyboard": [
        [{"text": BTN_SKIP}],
        [{"text": BTN_BACK}, {"text": "🏠 منوی اصلی"}],
    ], "resize_keyboard": True}


def _ask_create_step(cid, uid, step):
    data = get_state_data(uid)
    if step == 0:
        return send(cid, "📝 عنوان فرم را بنویسید:", kb_cancel())
    if step == 1:
        return send(cid, (
            "🔗 لینک اختصاصی فرم (اختیاری)\n"
            "━━━━━━━━━━━━━━\n\n"
            "فقط حروف انگلیسی، عدد، خط تیره و زیرخط.\n\n"
            f"📌 عنوان: {data.get('title')}\n\n"
            "مثال: karegah_fanbayan\n\n"
            "💡 اگر رد کنید، یک لینک تصادفی ساخته می‌شود."
        ), _kb_slug())


def _finish_create(cid, uid, slug):
    data = get_state_data(uid)
    title = data.get("title") or "فرم بدون عنوان"
    ftype = data.get("form_type") or "questionnaire"
    if not slug:
        slug = gen_slug()
        while db_execute("SELECT id FROM forms WHERE slug=?", (slug,), fetch="one"):
            slug = gen_slug()

    t = FORM_TYPES.get(ftype, FORM_TYPES["questionnaire"])
    fid = db_execute("""INSERT INTO forms
        (owner_id, form_type, title, slug, status, anonymous, one_per_user,
         end_text, payment_method)
        VALUES (?,?,?,?,'draft',?,?,?,'none')""",
        (uid, ftype, title, slug, t.get("anonymous", 0),
         0 if t.get("multi") else 1,
         get_setting("form_txt_end_default", "💚 سپاس از شما")))

    clear_state(uid)
    if not fid:
        return send(cid, "❌ خطا در ساخت فرم", kb_remove())

    log_action(uid, "form_create", {"fid": fid, "type": ftype})

    # ✨ فاز ۱۸-د — امکانات ویژه این نوع فرم را همان اول نشان بده
    #    🎯 «امکانات ویژه اون فرم هم همون اول که ادمین فرم میسازه
    #        واسش نمایش بده تا در صورت نیاز انتخاب کنه»
    feats = type_features(ftype)
    tpl = FORM_TEMPLATES.get(ftype) or []

    head = [f"✅ فرم «{title}» ساخته شد!", "━━━━━━━━━━━━━━", "",
            f"{t['icon']} نوع: {t['name']}", ""]

    if feats:
        head.append(f"✨ این نوع فرم {len(feats)} امکان ویژه دارد:")
        for key, icon, name, kind, _h in feats[:6]:
            head.append(f"   {icon} {name}")
        if len(feats) > 6:
            head.append(f"   … و {len(feats) - 6} مورد دیگر")
        head.append("")

    btns = []
    if tpl:
        names = "\n".join(
            f"   {i}. {FIELD_TYPES[k]['icon']} {FIELD_TYPES[k]['name']}"
            for i, k in enumerate(tpl, 1) if k in FIELD_TYPES)
        head += [f"🎁 سوالات پیشنهادی:\n{names}", ""]
        btns.append([{"text": f"✅ افزودن {len(tpl)} سوال پیشنهادی",
                      "callback_data": f"fbtpl_{fid}"}])
    if feats:
        btns.append([{"text": f"✨ تنظیم امکانات ویژه {t['name']}"[:36],
                      "callback_data": f"fbfeat_{fid}"}])
    btns.append([{"text": "✍️ افزودن سوال‌های خودم",
                  "callback_data": f"fbf_{fid}"}])
    btns.append([{"text": "🎨 جزئیات و تنظیمات فرم",
                  "callback_data": f"fbdet_{fid}"}])

    head.append("از کجا شروع کنیم؟ 👇")
    send(cid, "\n".join(head), kb_remove())
    return send_or_edit(cid, "یکی را انتخاب کنید:",
                        {"inline_keyboard": btns})


def use_template(cid, uid, fid):
    """🎁 افزودن سوالات آماده"""
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    n = apply_template(fid, form.get("form_type"))
    send(cid, (
        f"✅ {n} سوال اضافه شد!\n\n"
        f"می‌توانید ویرایششان کنید یا سوال جدید بسازید."
    ))
    return show_fields_entry(cid, uid, fid)


def show_fields_entry(cid, uid, fid):
    """میانبر به لیست سوالات (از form_fields)"""
    import form_fields as _ff
    return _ff.show_fields(cid, uid, fid, 0)


# ==================== نمایش/مدیریت یک فرم ====================
def show_form(cid, uid, fid):
    """صفحه ویرایش فرم — طبق ساختار دیجی‌فرم"""
    form = get_form(fid)
    if not form:
        return send(cid, "❌ فرم یافت نشد")
    if not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")

    fields = get_fields(fid)
    t = FORM_TYPES.get(form.get("form_type") or "questionnaire",
                       FORM_TYPES["questionnaire"])
    req = sum(1 for f in fields if f.get("is_required"))

    lines = [
        f"{t['icon']} {form['title']}",
        "━━━━━━━━━━━━━━",
        "",
        f"🏷️ نوع: {t['name']}",
        f"📊 وضعیت: {status_badge(form)}",
        f"🔗 لینک: {form.get('slug') or '-'}",
        f"📝 سوالات: {len(fields)} (اجباری: {req})",
        f"📥 پاسخ‌ها: {form.get('responses_count') or 0}",
    ]
    if form.get("banner_file_id"):
        lines.append("🖼️ بنر: ✅ دارد")

    # 🔗 فاز ۱۶ — اگر این فرم به رویدادی وصل است، معلوم باشد
    if form.get("event_id"):
        _e = db_execute("SELECT title, status FROM events WHERE id=?",
                        (form["event_id"],), fetch="one")
        if _e:
            lines.append(f"🔗 فرم ثبت‌نام رویداد: {str(_e['title'])[:30]}")

    if form.get("description"):
        lines.append(f"\n📄 {str(form['description'])[:150]}")

    # 💡 راهنمای قدم بعدی — کاربر سردرگم نشود
    if not fields:
        lines += ["", "⚠️ این فرم هنوز سوالی ندارد",
                  "💡 اول سوالات را اضافه کنید."]
    elif form.get("status") != "active":
        lines += ["", "💡 فرم آماده است — «🔍 مرور و انتشار» را بزنید."]

    if (form.get("payment_method") or "none") != "none":
        from payments import PAYMENT_METHODS
        pm = PAYMENT_METHODS.get(form["payment_method"], {})
        lines.append(f"\n💳 پرداخت: {pm.get('icon','')} {pm.get('name','')} "
                     f"— {fmt_amount(form.get('price'))} {CURRENCY_LABEL}")
    else:
        lines.append("\n🎁 رایگان")

    if form.get("limit_enabled") and form.get("max_responses"):
        lines.append(f"👥 ظرفیت: {form.get('responses_count') or 0}/{form['max_responses']}")
    if form.get("ticket_enabled"):
        lines.append("🎫 بلیت: ✅ فعال")
    if form.get("start_at"):
        lines.append(f"📅 شروع: {form['start_at']}")
    if form.get("end_at"):
        lines.append(f"⛔ پایان: {form['end_at']}")

    send_or_edit(cid, "\n".join(lines), kb_form(form, len(fields)))


def kb_form(form, nfields=0):
    """
    منوی اصلی فرم — دو بخش کاملاً جدا (درخواست کاربر):
      📝 سوالات فرم    → افزودن/ویرایش سوالات
      🎨 جزئیات فرم    → عنوان، بنر، پرداخت، قوانین، تنظیمات
    """
    fid = form["id"]
    t = FORM_TYPES.get(form.get("form_type") or "questionnaire", FORM_TYPES["questionnaire"])
    active = (form.get("status") == "active")
    return {"inline_keyboard": [
        [{"text": f"📝 سوالات فرم ({nfields})", "callback_data": f"fbf_{fid}"}],
        [{"text": "🎨 جزئیات و تنظیمات فرم", "callback_data": f"fbdet_{fid}"}],
        [{"text": f"📊 {t['result_btn']}", "callback_data": f"fbr_{fid}"},
         {"text": "📈 گزارش", "callback_data": f"fbrep_{fid}"}],
        # 🔴 فاز ۱۵: پیش‌نویس اول از «مرور نهایی» عبور می‌کند
        [{"text": ("🚫 غیرفعال کردن" if active else "🔍 مرور و انتشار"),
          "callback_data": (f"fbunpub_{fid}" if active else f"fbrev_{fid}")}],
        [{"text": "👁️ پیش‌نمایش", "callback_data": f"fbprev_{fid}"},
         {"text": "⋮ بیشتر", "callback_data": f"fbmore_{fid}"}],
        ([{"text": "🔙 بازگشت به رویداد",
           "callback_data": f"evrev_{form['event_id']}"}]
         if form.get("event_id") else
         [{"text": "🔙 فرم‌های من", "callback_data": "fb_list"}]),
    ]}


def show_details(cid, uid, fid):
    """🎨 جزئیات فرم — همه‌چیز غیر از سوالات، یکجا"""
    form = get_form(fid)
    if not form:
        return send(cid, "❌ فرم یافت نشد")
    if not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")

    from payments import PAYMENT_METHODS
    pm = PAYMENT_METHODS.get(form.get("payment_method") or "none", {})
    has_cost, cost_txt = price_preview(fid)
    dm = DISPLAY_MODES.get(form.get("display_mode") or "one_by_one",
                           DISPLAY_MODES["one_by_one"])

    lines = [
        f"🎨 جزئیات فرم «{form['title'][:30]}»",
        "━━━━━━━━━━━━━━",
        "",
        f"📝 عنوان: {form['title']}",
        f"🔗 لینک: {form.get('slug') or '—'}",
        f"📄 توضیحات: {'✅ دارد' if form.get('description') else '—'}",
        f"💚 پیام پایانی: {'✅ دارد' if form.get('end_text') else '—'}",
        f"🖼️ بنر: {'✅' if form.get('banner_file_id') else '—'}"
        f"   🏷️ لوگو: {'✅' if form.get('logo_file_id') else '—'}",
        "",
        f"💳 پرداخت: {pm.get('icon','')} {pm.get('name','—')}",
        f"   {cost_txt}",
        "",
        f"👁️ نمایش: {dm['icon']} {dm['name']}",
        f"👥 ظرفیت: "
        + (f"{form.get('max_responses')} نفر" if form.get("limit_enabled")
           and form.get("max_responses") else "نامحدود"),
        f"🎫 بلیت: {'✅ فعال' if form.get('ticket_enabled') else '❌'}",
    ]
    if form.get("start_at"):
        lines.append(f"📅 شروع: {form['start_at']}")
    if form.get("end_at"):
        lines.append(f"⛔ پایان: {form['end_at']}")

    # ✨ فاز ۱۸-الف — امکانات ویژه این نوع فرم و سطح دسترسی
    ftype = form.get("form_type") or "questionnaire"
    feats = type_features(ftype)
    tinfo = FORM_TYPES.get(ftype, FORM_TYPES["questionnaire"])
    vis = VISIBILITY[visibility_of(form)]
    lines += ["", f"👁️ دسترسی: {vis['icon']} {vis['name']}"]
    if visibility_of(form) == "section" and form.get("section_key"):
        sec = FORM_SECTIONS.get(form["section_key"], {})
        lines.append(f"   🧩 بخش: {sec.get('icon','')} "
                     f"{sec.get('name', form['section_key'])}")

    btns = [
        [{"text": "📝 عنوان و توضیحات", "callback_data": f"fbinfo_{fid}"}],
        [{"text": "🖼️ بنر و لوگو", "callback_data": f"fbmedia_{fid}"}],
        [{"text": "💳 پرداخت و هزینه", "callback_data": f"fbpay_{fid}"}],
    ]
    if feats:
        btns.append([{"text": f"✨ امکانات ویژه {tinfo['name']} "
                              f"({len(feats)})",
                      "callback_data": f"fbfeat_{fid}"}])
    btns += [
        [{"text": f"👁️ دسترسی: {vis['icon']} {vis['name']}",
          "callback_data": f"fbvis_{fid}"}],
        [{"text": "📜 قوانین و مقررات", "callback_data": f"fbterms_{fid}"}],
        [{"text": "⚙️ تنظیمات پیشرفته", "callback_data": f"fbadv_{fid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"fbv_{fid}"}],
    ]
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ══════════════════════════════════════════════════════════
# ✨ فاز ۱۸-الف — پنل امکانات ویژه هر نوع فرم
# ══════════════════════════════════════════════════════════
STATE_FB_FEAT = "fb_feat"


def show_features(cid, uid, fid):
    """✨ امکانات ویژه مخصوص نوع این فرم"""
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")

    ftype = form.get("form_type") or "questionnaire"
    feats = type_features(ftype)
    t = FORM_TYPES.get(ftype, FORM_TYPES["questionnaire"])

    if not feats:
        return send_or_edit(cid, (
            f"✨ امکانات ویژه\n━━━━━━━━━━━━━━\n\n"
            f"برای فرم نوع «{t['name']}» امکان ویژه‌ای تعریف نشده.\n\n"
            f"💡 تنظیمات عمومی را از «⚙️ تنظیمات پیشرفته» ببینید."
        ), {"inline_keyboard": [
            [{"text": "🔙 بازگشت", "callback_data": f"fbdet_{fid}"}]]})

    lines = [f"✨ امکانات ویژه {t['icon']} {t['name']}",
             "━━━━━━━━━━━━━━", "",
             "این تنظیمات مخصوص همین نوع فرم است:", ""]
    btns = []
    for key, icon, name, kind, hint in feats:
        v = form.get(key)
        if kind == "bool":
            on = bool(v)
            lines.append(f"{'🟢' if on else '⚪'} {icon} {name}")
            btns.append([{"text": f"{'✅' if on else '❌'} {icon} {name}"[:36],
                          "callback_data": f"fbft_{key}_{fid}"}])
        else:
            shown = v if v not in (None, "", 0) else "—"
            if kind == "num" and key in ("delivery_fee",):
                shown = fmt_amount(v) if v else "—"
            lines.append(f"▫️ {icon} {name}: {shown}")
            btns.append([{"text": f"{icon} {name}: {shown}"[:36],
                          "callback_data": f"fbfx_{key}_{fid}"}])

    lines += ["", "💡 روی هر مورد بزنید تا تغییر کند."]
    btns.append([{"text": "🔙 جزئیات فرم", "callback_data": f"fbdet_{fid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def _feat_def(form, key):
    for f in type_features(form.get("form_type") or "questionnaire"):
        if f[0] == key:
            return f
    return None


def toggle_feature(cid, uid, key, fid):
    """روشن/خاموش کردن یک امکان ویژه"""
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    d = _feat_def(form, key)
    if not d or d[3] != "bool":
        return send(cid, "❌ نامعتبر")
    cur = 1 if form.get(key) else 0
    db_execute(f"UPDATE forms SET {key}=?, updated_at=CURRENT_TIMESTAMP "
               f"WHERE id=?", (0 if cur else 1, fid))
    return show_features(cid, uid, fid)


def start_feature_edit(cid, uid, key, fid):
    """ویرایش مقدار عددی/متنی/تاریخی یک امکان ویژه"""
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    d = _feat_def(form, key)
    if not d:
        return send(cid, "❌ نامعتبر")
    _, icon, name, kind, hint = d
    cur = form.get(key)
    set_state(uid, STATE_FB_FEAT, {"fid": fid, "key": key, "kind": kind},
              merge=False)
    send(cid, (f"{icon} {name}\n━━━━━━━━━━━━━━\n\n"
               f"📄 فعلی: {cur if cur not in (None, '') else '—'}\n\n"
               f"{hint}"), kb_cancel())


def handle_feature_input(message):
    """دریافت مقدار جدید امکان ویژه"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid)
    fid, key, kind = d.get("fid"), d.get("key"), d.get("kind")

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_features(cid, uid, fid)

    form = get_form(fid)
    if not form or not _feat_def(form, key):
        clear_state(uid)
        return send(cid, "❌ نامعتبر", kb_remove())

    if kind == "num":
        digits = "".join(ch for ch in normalize_digits(raw) if ch.isdigit())
        if not digits:
            return send(cid, "⚠️ فقط عدد بفرستید:", kb_cancel())
        val = int(digits)
        if key == "leaderboard_size":
            val = max(1, min(100, val))
        elif key == "max_choices":
            val = max(1, min(50, val))
        elif key == "max_attempts":
            val = max(0, min(100, val))
    elif kind == "date":
        val = normalize_digits(raw)
        if not validate_jdatetime(val):
            return send(cid, "⚠️ تاریخ نامعتبر\n\nمثال: 1404/06/15",
                        kb_cancel())
    else:
        val = raw[:500]

    db_execute(f"UPDATE forms SET {key}=?, updated_at=CURRENT_TIMESTAMP "
               f"WHERE id=?", (val, fid))
    clear_state(uid)
    send(cid, "✅ ذخیره شد", kb_remove())
    return show_features(cid, uid, fid)


# ══════════════════════════════════════════════════════════
# 👁️ فاز ۱۸-الف — سطح دسترسی فرم
# ══════════════════════════════════════════════════════════
STATE_FB_CODE = "fb_access_code"


def show_visibility(cid, uid, fid):
    """👁️ چه کسانی این فرم را ببینند؟"""
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")

    cur = visibility_of(form)
    lines = ["👁️ سطح دسترسی فرم", "━━━━━━━━━━━━━━", "",
             f"📋 {form['title'][:40]}", "",
             "تعیین کنید چه کسانی این فرم را ببینند:", ""]
    btns = []
    for k, v in VISIBILITY.items():
        mark = "🔘" if k == cur else "⚪"
        lines.append(f"{mark} {v['icon']} {v['name']}")
        lines.append(f"      {v['desc']}")
        btns.append([{"text": f"{mark} {v['icon']} {v['name']}",
                      "callback_data": f"fbvs_{k}_{fid}"}])

    if cur == "section":
        sec = FORM_SECTIONS.get(form.get("section_key") or "", {})
        lines += ["", f"🧩 بخش فعلی: {sec.get('icon','')} "
                      f"{sec.get('name') or '— انتخاب نشده —'}"]
        btns.append([{"text": "🧩 انتخاب بخش ربات",
                      "callback_data": f"fbsec_{fid}"}])
    if cur == "private":
        code = form.get("access_code") or "—"
        lines += ["", f"🔑 کد دسترسی: {code}"]
        btns.append([{"text": "🔑 تعیین کد دسترسی",
                      "callback_data": f"fbcode_{fid}"}])

    if cur != "public":
        lines += ["", "💡 این فرم در فهرست عمومی نمایش داده نمی‌شود.",
                  f"🔗 لینک مستقیم: {form_link(form)}"]

    btns.append([{"text": "🔙 جزئیات فرم", "callback_data": f"fbdet_{fid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_visibility(cid, uid, vis, fid):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    if vis not in VISIBILITY:
        return send(cid, "❌ نامعتبر")
    db_execute("UPDATE forms SET visibility=?, updated_at=CURRENT_TIMESTAMP "
               "WHERE id=?", (vis, fid))
    if vis == "private" and not (form.get("access_code") or "").strip():
        import random as _r
        import string as _st
        code = "".join(_r.choices(_st.ascii_uppercase + _st.digits, k=6))
        db_execute("UPDATE forms SET access_code=? WHERE id=?", (code, fid))
    return show_visibility(cid, uid, fid)


def show_sections(cid, uid, fid, key=None):
    """🧩 اتصال فرم به یک بخش ربات"""
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    if key:
        if key not in FORM_SECTIONS:
            return send(cid, "❌ نامعتبر")
        db_execute("UPDATE forms SET section_key=?, visibility='section' "
                   "WHERE id=?", (key, fid))
        sec = FORM_SECTIONS[key]
        send(cid, f"✅ این فرم به «{sec['icon']} {sec['name']}» وصل شد")
        return show_visibility(cid, uid, fid)

    cur = form.get("section_key")
    lines = ["🧩 فرم به کدام بخش ربات وصل شود؟", "━━━━━━━━━━━━━━", "",
             "کاربر با ورود به آن بخش، این فرم را می‌بیند.", ""]
    btns = []
    for k, v in FORM_SECTIONS.items():
        mark = "🔘" if k == cur else "⚪"
        n_used = db_scalar("SELECT COUNT(*) FROM forms WHERE section_key=? "
                           "AND status='active' AND id<>?", (k, fid)) or 0
        extra = f" ({n_used} فرم دیگر)" if n_used else ""
        lines.append(f"{mark} {v['icon']} {v['name']}{extra}")
        btns.append([{"text": f"{mark} {v['icon']} {v['name']}",
                      "callback_data": f"fbsec_{fid}_{k}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbvis_{fid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_access_code(cid, uid, fid):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    set_state(uid, STATE_FB_CODE, {"fid": fid}, merge=False)
    send(cid, (f"🔑 کد دسترسی فرم\n━━━━━━━━━━━━━━\n\n"
               f"📄 فعلی: {form.get('access_code') or '—'}\n\n"
               f"کد جدید را بنویسید (انگلیسی/عدد):\n\n"
               f"💡 فقط کسانی که این کد را دارند فرم را می‌بینند."),
         kb_cancel())


def handle_access_code(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid)
    fid = d.get("fid")
    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_visibility(cid, uid, fid)
    code = "".join(ch for ch in raw if ch.isalnum())[:20]
    if len(code) < 3:
        return send(cid, "⚠️ کد حداقل ۳ کاراکتر (انگلیسی/عدد):", kb_cancel())
    db_execute("UPDATE forms SET access_code=? WHERE id=?", (code, fid))
    clear_state(uid)
    send(cid, f"✅ کد دسترسی: {code}", kb_remove())
    return show_visibility(cid, uid, fid)


def show_terms(cid, uid, fid):
    """
    📜 قوانین و مقررات — میانبری که کاربر گفت پیدا نمی‌کند.

    اگر فرم سوال «قوانین» ندارد، همین‌جا با یک دکمه می‌سازد.
    """
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")

    tf = [f for f in get_fields(fid)
          if field_meta(f.get("field_type")).get("has_terms")]

    if not tf:
        return send_or_edit(cid, (
            "📜 قوانین و مقررات\n━━━━━━━━━━━━━━\n\n"
            "این فرم هنوز سوال «تأیید قوانین» ندارد.\n\n"
            "💡 با دکمه زیر اضافه کنید — کاربر قبل از ثبت باید تأییدش کند."
        ), {"inline_keyboard": [
            [{"text": "➕ افزودن «قوانین و مقررات»",
              "callback_data": f"fbn_terms_{fid}"}],
            [{"text": "🔒 افزودن «حریم خصوصی»",
              "callback_data": f"fbn_privacy_{fid}"}],
            [{"text": "🔙 بازگشت", "callback_data": f"fbdet_{fid}"}]]})

    lines = ["📜 قوانین و مقررات", "━━━━━━━━━━━━━━", ""]
    btns = []
    for f in tf:
        m = field_meta(f.get("field_type"))
        txt = f.get("terms_text") or ""
        lines += [f"{m['icon']} {m['name']}",
                  f"   {'✅ متن دارد (' + str(len(txt)) + ' کاراکتر)' if txt else '⚠️ متن ندارد!'}",
                  f"   {'⭐ اجباری' if f.get('is_required') else '◽ اختیاری'}", ""]
        btns.append([{"text": f"✏️ متن {m['name']}",
                      "callback_data": f"fbtt_{f['id']}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbdet_{fid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_after_submit(cid, uid, fid):
    """
    🔐 دسترسی کاربر بعد از ثبت فرم.

    🎯 «کاربر چرا میتونه پاسخ‌هاشو حذف کنه تو فرم؟ اینو کاملا
       بردار و تنظیمش رو بزار تو فرم‌ساز که کاربر بعد از ثبت و
       تکمیل دسترسی‌هاش چیه»
    """
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    cur = after_submit_of(form)

    lines = ["🔐 دسترسی کاربر بعد از ثبت", "━━━━━━━━━━━━━━", "",
             f"📋 {form['title'][:36]}", "",
             "بعد از اینکه کاربر فرم را ثبت کرد، چه کاری", 
             "می‌تواند بکند؟", ""]
    for k, v in AFTER_SUBMIT.items():
        mark = "🔘" if k == cur else "▫️"
        lines.append(f"{mark} {v['icon']} {v['name']}")
        lines.append(f"      {v['desc']}")
    lines += ["", "━━━━━━━━━━━━━━",
              "🛡️ در هیچ حالتی کاربر نمی‌تواند پاسخش را",
              "   پاک کند — داده‌ها همیشه نزد شما می‌ماند.",
              "   «انصراف» فقط علامت می‌خورد."]

    btns = [[{"text": f"{'🔘' if k == cur else '▫️'} {v['icon']} {v['name']}",
              "callback_data": f"fbaft_{k}_{fid}"}]
            for k, v in AFTER_SUBMIT.items()]
    btns.append([{"text": "🔙 تنظیمات پیشرفته",
                  "callback_data": f"fbadv_{fid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_after_submit(cid, uid, fid, mode):
    """🔐 اعمال دسترسی بعد از ثبت"""
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    if mode not in AFTER_SUBMIT:
        return send(cid, "❌ نامعتبر")
    db_execute("UPDATE forms SET after_submit=?, allow_edit=?, "
               "updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (mode, 1 if mode == "edit" else 0, fid))
    log_action(uid, "form_setting", {"fid": fid, "after_submit": mode})
    send(cid, f"✅ {AFTER_SUBMIT[mode]['icon']} {AFTER_SUBMIT[mode]['name']}")
    return show_after_submit(cid, uid, fid)


def show_more(cid, uid, fid):
    """⋮ منوی گزینه‌های بیشتر — طبق معماری"""
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    send_or_edit(cid, (
        f"⋮ گزینه‌های بیشتر\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"📋 فرم: {form['title']}"
    # 🧹 فاز ۴۰ — از ۱۳ ردیف به ۷ ردیف
    #    قانون کاربر: «حداکثر ۱۰ دکمه در هر صفحه»
    #    دکمه‌های هم‌خانواده کنار هم دوستونی شدند.
    ), {"inline_keyboard": [
        # ─── انتشار ───
        [{"text": "📌 لینک انتشار", "callback_data": f"fblink_{fid}"},
         {"text": "📱 کیوآرکد", "callback_data": f"fbqr_{fid}"}],
        # ─── پاسخ‌ها ───
        [{"text": "📊 پاسخ‌ها", "callback_data": f"fbr_{fid}"},
         {"text": "📈 گزارش و آمار", "callback_data": f"fbrep_{fid}"}],
        # ─── خروجی ───
        [{"text": "📄 خروجی اکسل", "callback_data": f"fbx_{fid}"},
         {"text": "📑 خروجی متنی", "callback_data": f"fbpdf_{fid}"}],
        # ─── مدیریت ───
        [{"text": "🏷️ برچسب‌ها", "callback_data": f"fbtags_{fid}"},
         {"text": "👥 ادمین‌ها", "callback_data": f"fbfadm_{fid}"}],
        [{"text": "🔗 اتصال به رویداد",
          "callback_data": f"fblinkev_{fid}"},
         {"text": "📋 کپی فرم", "callback_data": f"fbcopy_{fid}"}],
        # ─── خطرناک ───
        [{"text": "👁️ پیش‌نمایش", "callback_data": f"fbprev_{fid}"},
         {"text": "🗑️ حذف فرم", "callback_data": f"fbdel_{fid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"fbv_{fid}"}],
    ]})


# ==================== لیست فرم‌ها ====================
def show_list(cid, uid, page=0, ftype=None, query=None):
    if not _guard(cid, uid):
        return
    from config import SUPER_ADMIN_ID

    where, params = [], []
    if uid != SUPER_ADMIN_ID:
        where.append("(owner_id=? OR id IN (SELECT form_id FROM form_admins WHERE bale_user_id=?))")
        params += [uid, uid]
    if ftype and ftype in FORM_TYPES:
        where.append("form_type=?")
        params.append(ftype)
    if query:
        where.append("(title LIKE ? OR slug LIKE ?)")
        params += [f"%{query}%", f"%{query}%"]

    sql = "SELECT * FROM forms"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC"
    rows = db_execute(sql, tuple(params), fetch="all") or []

    if not rows:
        msg = "📭 هنوز فرمی نساخته‌اید."
        if query:
            msg = f"🔍 نتیجه‌ای برای «{query}» پیدا نشد."
        elif ftype:
            # 🔴 باگ رفع‌شده (فاز ۴۰): دسترسی مستقیم به
            #    FORM_TYPES[ftype] با نوع ناشناخته KeyError
            #    می‌داد. بالاتر در همین تابع `ftype in FORM_TYPES`
            #    بررسی می‌شود ولی اینجا نه.
            _ft = FORM_TYPES.get(ftype)
            msg = (f"📭 فرمی از نوع {_ft['name']} ندارید."
                   if _ft else "📭 فرمی با این نوع ندارید.")
        return send_or_edit(cid, (
            "📋 فرم‌های من\n━━━━━━━━━━━━━━\n\n" + msg
        ), {"inline_keyboard": [
            [{"text": "➕ ایجاد فرم جدید", "callback_data": "fb_new"}],
            [{"text": "🎛️ همه فرم‌ها", "callback_data": "fb_list"}],
            [{"text": "🔙 پنل فرم‌ساز", "callback_data": "fb_panel"}],
        ]})

    per = FORMS_PER_PAGE
    pages = max(1, (len(rows) + per - 1) // per)
    page = max(0, min(int(page or 0), pages - 1))
    chunk = rows[page * per:(page + 1) * per]

    head = "📋 فرم‌های من"
    if ftype:
        head += f" — {FORM_TYPES[ftype]['icon']} {FORM_TYPES[ftype]['name']}"
    if query:
        head += f" — 🔍 {query}"
    lines = [f"{head} ({len(rows)} فرم)", "━━━━━━━━━━━━━━", ""]
    btns = []

    for f in chunk:
        t = FORM_TYPES.get(f.get("form_type") or "questionnaire", FORM_TYPES["questionnaire"])
        free = "🎁 رایگان" if (f.get("payment_method") or "none") == "none" \
            else f"💳 {fmt_amount(f.get('price'))} {CURRENCY_LABEL}"
        lines += [
            f"📄 {f['title']}",
            f"   🏷️ {t['name']} | {status_badge(f)} | {free}",
            f"   📊 پاسخ‌ها: {f.get('responses_count') or 0}  🔗 {f.get('slug') or '-'}",
            "",
        ]
        btns.append([
            {"text": f"📊 {t['result_btn']}", "callback_data": f"fbr_{f['id']}"},
            {"text": "⚙️ مدیریت", "callback_data": f"fbv_{f['id']}"},
            {"text": "⋮", "callback_data": f"fbmore_{f['id']}"},
        ])

    if pages > 1:
        nav = []
        sfx = f"_{ftype}" if ftype else ""
        if page > 0:
            nav.append({"text": "⬅️ قبلی", "callback_data": f"fbpg_{page-1}{sfx}"})
        nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
        if page < pages - 1:
            nav.append({"text": "بعدی ➡️", "callback_data": f"fbpg_{page+1}{sfx}"})
        btns.append(nav)

    btns.append([{"text": "🔍 جستجو", "callback_data": "fb_search"},
                 {"text": "🎛️ فیلتر", "callback_data": "fb_filter"}])
    btns.append([{"text": "➕ ایجاد فرم جدید", "callback_data": "fb_new"}])
    btns.append([{"text": "🔙 پنل فرم‌ساز", "callback_data": "fb_panel"}])

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_filter(cid, uid):
    if not _guard(cid, uid):
        return
    btns = [[{"text": "✅ همه فرم‌ها", "callback_data": "fb_list"}]]
    row = []
    for key, t in FORM_TYPES.items():
        row.append({"text": f"{t['icon']} {t['name']}", "callback_data": f"fbflt_{key}"})
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([{"text": "🔙 بازگشت", "callback_data": "fb_list"}])
    send_or_edit(cid, (
        "🎛️ فیلتر فرم‌ها\n━━━━━━━━━━━━━━\n\nنوع فرم را انتخاب کنید:"
    ), {"inline_keyboard": btns})


def start_search(cid, uid):
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_FB_SEARCH, {}, merge=False)
    send(cid, (
        "🔍 جستجوی فرم\n━━━━━━━━━━━━━━\n\n"
        "بخشی از عنوان یا لینک فرم را بنویسید:"
    ), kb_cancel())


def handle_search(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    clear_state(uid)
    if text in (BTN_BACK, "🔙 بازگشت") or not text:
        send(cid, "❌ لغو شد", kb_remove())
        return show_list(cid, uid, 0)
    send(cid, f"🔍 جستجو: {text}", kb_remove())
    return show_list(cid, uid, 0, query=text[:40])


# ==================== انتشار / وضعیت ====================
# ══════════════════════════════════════════════════════════
# 🔍 فاز ۱۵ — مرور تنظیمات قبل از انتشار فرم
#
# درخواست کاربر: «تو پیشنویس فرم مراحل آخرش تنظیمات پیشرفته به
#   کاربر نشون بده تا بعد از تنظیم اونا فرمش نهایی کنه»
# ══════════════════════════════════════════════════════════
FORM_REVIEW = [
    ("display_mode",   "👁️", "نحوه نمایش سوالات"),
    ("one_per_user",   "1️⃣", "هر نفر فقط یک بار"),
    ("require_auth",   "🔐", "نیاز به احراز هویت"),
    ("needs_approval", "👨‍💼", "تأیید ادمین لازم"),
    ("ticket_enabled", "🎫", "صدور بلیت"),
    ("notify_admins",  "🔔", "اعلان به ادمین"),
    ("fill_profile",   "👤", "پرکردن پروفایل کاربر"),
    ("show_progress",  "📊", "نوار پیشرفت"),
]


def show_review(cid, uid, fid):
    """
    🔍 مرور نهایی فرم — همه تنظیمات مهم یک‌جا، قابل تغییر با یک کلیک.

    به‌جای اینکه کاربر در ۸ منوی مختلف بچرخد، اینجا همه چیز
    دم دستش است و بعد مستقیم منتشر می‌کند.
    """
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")

    fields = get_fields(fid)
    ft = FORM_TYPES.get(form.get("form_type") or "questionnaire",
                        FORM_TYPES["questionnaire"])

    lines = [
        "🔍 مرور نهایی فرم",
        f"{ft['icon']} {form['title']}",
        "━━━━━━━━━━━━━━", "",
        f"📝 تعداد سوالات: {len(fields)}",
    ]

    dm = DISPLAY_MODES.get(form.get("display_mode") or "one_by_one",
                           DISPLAY_MODES["one_by_one"])
    lines.append(f"👁️ نمایش: {dm['icon']} {dm['name']}")

    method = form.get("payment_method") or "none"
    if method != "none":
        from payments import PAYMENT_METHODS as _PM
        pm = _PM.get(method, _PM["none"])
        lines.append(f"{pm['icon']} پرداخت: {pm['name']}"
                     f" — {fmt_amount(form.get('price'))} {CURRENCY_LABEL}")
    else:
        lines.append("🎁 رایگان")

    lines += ["", "⚙️ تنظیمات:"]
    btns = []
    for key, icon, title in FORM_REVIEW:
        if key == "display_mode":
            btns.append([{"text": f"👁️ نمایش: {dm['name']}"[:40],
                          "callback_data": f"fbdisp_{fid}"}])
            continue
        on = int(form.get(key) or 0)
        lines.append(f"   {icon} {title}: {'✅' if on else '❌'}")
        btns.append([{"text": f"{icon} {title}: {'✅' if on else '❌'}",
                      "callback_data": f"fbtog_{key}_{fid}"}])

    # هشدارهای قبل از انتشار
    warn = []
    if not fields:
        warn.append("⛔ هیچ سوالی ندارد — قابل انتشار نیست")
    if method != "none" and not form.get("price"):
        warn.append("⛔ روش پرداخت فعال است ولی مبلغ ندارد")
    if warn:
        lines += ["", "⚠️ قبل از انتشار:"] + [f"   {w}" for w in warn]

    lines += ["", "━━━━━━━━━━━━━━"]
    if form.get("status") == "active":
        lines.append("🟢 این فرم منتشر شده است")
    else:
        lines.append("📝 وضعیت: پیش‌نویس")

    btns.append([{"text": "➕ سوالات فرم", "callback_data": f"fbf_{fid}"},
                 {"text": "💳 پرداخت", "callback_data": f"fbpay_{fid}"}])
    btns.append([{"text": "⚙️ تنظیمات پیشرفته‌تر",
                  "callback_data": f"fbadv_{fid}"}])
    if form.get("status") != "active":
        btns.append([{"text": "🚀 تأیید و انتشار فرم",
                      "callback_data": f"fbpub_{fid}"}])
    btns.append([{"text": "🔙 صفحه فرم", "callback_data": f"fbv_{fid}"}])

    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def publish_form(cid, uid, fid, publish=True):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")

    if publish:
        fields = get_fields(fid)
        if not fields:
            return send_or_edit(cid, (
                "⚠️ فرم بدون سوال قابل انتشار نیست!\n\n"
                "ابتدا حداقل یک سوال اضافه کنید."
            ), {"inline_keyboard": [
                [{"text": "➕ افزودن سوال", "callback_data": f"fbfa_{fid}"}],
                [{"text": "🔙 بازگشت", "callback_data": f"fbv_{fid}"}]]})

        # 🔴 فاز ۲۳ — فرمی که هزینه‌اش از «موردهای قیمت‌دار» می‌آید
        #    نباید بلوکه شود. قبلاً چنین فرمی هرگز منتشر نمی‌شد!
        has_priced = any(
            int(it.get("price") or 0) > 0
            for fl in fields
            if field_meta(fl.get("field_type")).get("kind") == "item"
            for it in parse_items(fl))
        if ((form.get("payment_method") or "none") != "none"
                and not form.get("price") and not has_priced):
            return send_or_edit(cid, (
                "⚠️ روش پرداخت فعال است ولی مبلغی تعیین نشده!\n\n"
                "یکی از این دو را انجام دهید:\n"
                "   • مبلغ ثابت فرم را مشخص کنید\n"
                "   • یا برای سوال‌های ثبت‌نام، مورد قیمت‌دار بسازید"
            ), {"inline_keyboard": [
                [{"text": "💳 تنظیمات پرداخت", "callback_data": f"fbpay_{fid}"}],
                [{"text": "📝 سوالات فرم", "callback_data": f"fbf_{fid}"}],
                [{"text": "🔙 بازگشت", "callback_data": f"fbv_{fid}"}]]})

    if publish:
        # 🔴 فاز ۲۳ — «دکمه انتشار میزنی انتشار عمومی میشه فوری»
        #    قبلاً فرم active می‌شد ولی visibility روی «لینک» یا
        #    «خصوصی» می‌ماند و در فهرست عمومی دیده نمی‌شد.
        #    کاربر منتشر می‌کرد و هیچ‌کس فرم را نمی‌دید!
        vis = visibility_of(form)
        if vis in ("private", "link"):
            db_execute("UPDATE forms SET visibility='public' WHERE id=?",
                       (fid,))
            vis = "public"

    db_execute("UPDATE forms SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               ("active" if publish else "inactive", fid))
    log_action(uid, "form_publish" if publish else "form_unpublish", {"fid": fid})

    if publish:
        form = get_form(fid)
        v = VISIBILITY[visibility_of(form)]
        send(cid, (
            f"✅ فرم منتشر شد!\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"{v['icon']} همین حالا {v['name']} است و کاربران\n"
            f"   می‌توانند پرش کنند 💚\n\n"
            f"🔗 {form_link(form)}"
        ), {"inline_keyboard": [
            [{"text": "🔗 لینک و کیوآر", "callback_data": f"fblink_{fid}"}],
            [{"text": "📢 اطلاع‌رسانی به کاربران",
              "callback_data": f"fbnotify_{fid}"}],
            [{"text": "👁️ دسترسی فرم", "callback_data": f"fbvis_{fid}"}],
            [{"text": "🔙 فرم", "callback_data": f"fbv_{fid}"}]]})
        return
    send(cid, "🚫 فرم غیرفعال شد")
    return show_form(cid, uid, fid)


def notify_users(cid, uid, fid, confirmed=False):
    """
    📢 اطلاع‌رسانی فرم تازه‌منتشرشده به کاربران.

    🎯 فاز ۲۳: بعد از انتشار، ادمین با یک دکمه به همه خبر می‌دهد
       — دیگر لازم نیست از پنل تبلیغات دور بزند.
    """
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    if form.get("status") != "active":
        return send(cid, "⚠️ اول فرم را منتشر کنید 🌱")

    n = db_scalar("SELECT COUNT(*) FROM users WHERE is_active=1 "
                  "AND COALESCE(is_blocked,0)=0") or 0
    t = FORM_TYPES.get(form.get("form_type") or "questionnaire",
                       FORM_TYPES["questionnaire"])

    if not confirmed:
        has_cost, cost_txt = price_preview(fid)
        return send_or_edit(cid, (
            f"📢 اطلاع‌رسانی فرم\n━━━━━━━━━━━━━━\n\n"
            f"{t['icon']} {form['title']}\n"
            f"   {cost_txt}\n\n"
            f"👥 گیرندگان: {n} کاربر فعال\n\n"
            f"پیام همراه با دکمه «شرکت می‌کنم» فرستاده می‌شود.\n\n"
            f"ارسال شود؟ 🌱"
        ), {"inline_keyboard": [
            [{"text": f"📢 بله، به {n} نفر بفرست",
              "callback_data": f"fbnoty_{fid}"}],
            [{"text": "❌ انصراف", "callback_data": f"fbv_{fid}"}]]})

    rows = db_execute("SELECT bale_user_id FROM users WHERE is_active=1 "
                      "AND COALESCE(is_blocked,0)=0 "
                      "AND bale_user_id IS NOT NULL", fetch="all") or []
    has_cost, cost_txt = price_preview(fid)
    txt = [f"{t['icon']} {form['title']}", "━━━━━━━━━━━━━━", ""]
    if form.get("description"):
        txt += [str(form["description"])[:300], ""]
    txt.append(cost_txt)
    if form.get("end_at"):
        txt.append(f"⛔ مهلت: {form['end_at']}")
    if form.get("limit_enabled") and form.get("max_responses"):
        left = int(form["max_responses"]) - int(form.get("responses_count") or 0)
        txt.append(f"👥 ظرفیت باقیمانده: {max(0, left)} نفر")
    txt += ["", "🌱 منتظر شما هستیم 💚"]
    body = "\n".join(txt)
    kb = {"inline_keyboard": [
        [{"text": "▶️ شرکت می‌کنم", "callback_data": f"ffopen_{fid}"}]]}

    send(cid, f"⏳ ارسال به {len(rows)} نفر...")
    import time as _t
    okn = 0
    for r in rows:
        try:
            if send(r["bale_user_id"], body, kb).get("ok"):
                okn += 1
        except Exception as e:
            log(f"⚠️ اطلاع‌رسانی فرم: {e}")
        _t.sleep(0.05)
    log_action(uid, "form_notify", {"fid": fid, "count": okn})
    return send_or_edit(cid, f"📢 به {okn} نفر اطلاع داده شد 💚",
                        {"inline_keyboard": [
                            [{"text": "🔙 فرم",
                              "callback_data": f"fbv_{fid}"}]]})


def show_link(cid, uid, fid):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    link = form_link(form)
    warn = ""
    if form.get("status") != "active":
        warn = "\n\n⚠️ فرم هنوز منتشر نشده — کاربران نمی‌توانند وارد شوند."
    send_or_edit(cid, (
        f"📌 انتشار فرم\n━━━━━━━━━━━━━━\n\n"
        f"📋 {form['title']}\n\n"
        f"🔗 لینک اختصاصی:\n{link}\n\n"
        f"💡 این لینک را برای اعضا بفرستید.{warn}"
    ), {"inline_keyboard": [
        [{"text": "📋 کپی لینک", "copy_text": {"text": link}}],
        [{"text": "📢 ارسال همگانی لینک", "callback_data": f"fbcast_{fid}"}],
        [{"text": "📱 دریافت QR Code", "callback_data": f"fbqr_{fid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"fbv_{fid}"}],
    ]})


def show_qr(cid, uid, fid):
    """QR کد فرم — با Pillow اگر در دسترس باشد، وگرنه متنی"""
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    link = form_link(form)
    path = _make_qr_image(link, f"form{fid}")
    if path:
        from bale_api import send_photo
        send_photo(cid, path, f"📱 QR Code فرم «{form['title']}»\n\n🔗 {link}")
        return send(cid, "👆 این کد را اسکن کنید", {"inline_keyboard": [
            [{"text": "🔙 بازگشت", "callback_data": f"fbv_{fid}"}]]})
    return send_or_edit(cid, (
        f"📱 QR Code\n━━━━━━━━━━━━━━\n\n"
        f"⚠️ کتابخانه qrcode نصب نیست.\n\n"
        f"🔗 لینک فرم:\n{link}\n\n"
        f"💡 نصب: py -m pip install qrcode"
    ), {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": f"fbv_{fid}"}]]})


def _make_qr_image(data, name):
    """ساخت تصویر QR — بی‌صدا None برمی‌گرداند اگر ممکن نباشد"""
    try:
        import qrcode
    except ImportError:
        return None
    try:
        from pathlib import Path
        from config import FILES_DIR
        d = Path(FILES_DIR) / "forms"
        d.mkdir(parents=True, exist_ok=True)
        img = qrcode.make(data)
        fp = d / f"qr_{name}.png"
        img.save(fp)
        return str(fp)
    except Exception as e:
        log(f"⚠️ ساخت QR: {e}")
        return None


def copy_form(cid, uid, fid):
    """📋 کپی از این فرم"""
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")

    slug = gen_slug()
    while db_execute("SELECT id FROM forms WHERE slug=?", (slug,), fetch="one"):
        slug = gen_slug()

    cols = [c for c in FORMS_SCHEMA
            if c not in ("created_at", "updated_at", "responses_count", "views_count")]
    vals = []
    for c in cols:
        if c == "title":
            vals.append(f"{form.get('title')} (کپی)")
        elif c == "slug":
            vals.append(slug)
        elif c == "status":
            vals.append("draft")
        elif c == "owner_id":
            vals.append(uid)
        else:
            vals.append(form.get(c))

    new_id = db_execute(
        f"INSERT INTO forms ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
        tuple(vals))
    if not new_id:
        return send(cid, "❌ خطا در کپی")

    fcols = [c for c in FIELDS_SCHEMA if c != "created_at"]
    for f in get_fields(fid):
        fv = [new_id if c == "form_id" else f.get(c) for c in fcols]
        db_execute(
            f"INSERT INTO form_fields ({','.join(fcols)}) "
            f"VALUES ({','.join('?' * len(fcols))})", tuple(fv))

    # اصلاح شرط‌ها: ارجاع به فیلدهای فرم جدید
    old = get_fields(fid)
    new = get_fields(new_id)
    m = {o["id"]: n["id"] for o, n in zip(old, new)}
    for n in new:
        if n.get("condition_field_id") in m:
            db_execute("UPDATE form_fields SET condition_field_id=? WHERE id=?",
                       (m[n["condition_field_id"]], n["id"]))

    log_action(uid, "form_copy", {"from": fid, "to": new_id})
    send(cid, f"✅ فرم کپی شد ({len(new)} سوال)")
    return show_form(cid, uid, new_id)


def delete_form(cid, uid, fid, confirmed=False):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")

    if not confirmed:
        n = db_scalar("SELECT COUNT(*) FROM form_responses WHERE form_id=?", (fid,))
        return send_or_edit(cid, (
            f"🗑️ حذف فرم\n━━━━━━━━━━━━━━\n\n"
            f"📋 {form['title']}\n"
            f"📝 سوالات: {len(get_fields(fid))}\n"
            f"📊 پاسخ‌ها: {n}\n\n"
            f"⚠️ همه سوالات و پاسخ‌ها حذف می‌شوند!\n"
            f"این عمل بازگشت‌پذیر نیست."
        ), {"inline_keyboard": [
            [{"text": "🗑️ بله، حذف کن", "callback_data": f"fbdely_{fid}"}],
            [{"text": "❌ انصراف", "callback_data": f"fbv_{fid}"}]]})

    resp = db_execute("SELECT id FROM form_responses WHERE form_id=?", (fid,), fetch="all") or []
    for r in resp:
        db_execute("DELETE FROM form_answers WHERE response_id=?", (r["id"],))
    db_execute("DELETE FROM form_responses WHERE form_id=?", (fid,))
    db_execute("DELETE FROM form_fields WHERE form_id=?", (fid,))
    db_execute("DELETE FROM form_admins WHERE form_id=?", (fid,))
    db_execute("DELETE FROM forms WHERE id=?", (fid,))
    log_action(uid, "form_delete", {"fid": fid})
    send(cid, "🗑️ فرم حذف شد")
    return show_list(cid, uid, 0)


# ==================== عنوان و توضیحات ====================
INFO_FIELDS = {
    "title":       ("📝 عنوان فرم", "عنوان جدید فرم را بنویسید:"),
    "description": ("📄 توضیحات ابتدای فرم", "توضیحاتی که ابتدای فرم نمایش داده می‌شود:"),
    "end_text":    ("💚 توضیحات پایانی", "متنی که بعد از ثبت اطلاعات نمایش داده می‌شود:"),
    "slug":        ("🔗 لینک اختصاصی", "لینک جدید (فقط انگلیسی و عدد):"),
    "payment_note": ("💳 راهنمای پرداخت", "توضیح واریز وجه برای کاربر:"),
    # 🆕 فاز ۱۵
    "welcome_text": ("👋 صفحه خوش‌آمدگویی",
                     "متنی که پیش از شروع فرم نشان داده می‌شود:"),
    "idcard_title": ("🆔 عنوان روی کارت",
                     "مثال: کارت عضویت خط زندگی"),
    # 🆕 فاز ۱۷
    "webhook_url": ("🔗 آدرس وبهوک",
                    "آدرس HTTPS که رویدادها به آن ارسال شود:\n\n"
                    "مثال: https://example.com/hook\n«-» = غیرفعال"),
}


def show_info(cid, uid, fid):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    lines = ["🎨 عنوان و توضیحات", "━━━━━━━━━━━━━━", ""]
    btns = []
    for key, (title, _) in INFO_FIELDS.items():
        if key == "payment_note":
            continue
        val = form.get(key)
        show = (str(val)[:40] + "…") if val and len(str(val)) > 40 else (val or "—")
        lines.append(f"{title}: {show}")
        btns.append([{"text": f"✏️ {title}", "callback_data": f"fbset_{key}_{fid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbv_{fid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_edit_info(cid, uid, fid, key):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    if key not in INFO_FIELDS:
        return send(cid, "❌ نامعتبر")
    title, prompt = INFO_FIELDS[key]
    cur = form.get(key) or "—"
    set_state(uid, STATE_FB_EDIT, {"fid": fid, "key": key}, merge=False)
    send(cid, (
        f"{title}\n━━━━━━━━━━━━━━\n\n"
        f"📌 مقدار فعلی:\n{cur}\n\n"
        f"{prompt}\n\n"
        f"💡 برای خالی کردن، «-» بفرستید."
    ), kb_cancel())


def handle_edit_info(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    data = get_state_data(uid)
    fid = data.get("fid")
    key = data.get("key")
    clear_state(uid)

    if text in (BTN_BACK, "🔙 بازگشت"):
        send(cid, "❌ لغو شد", kb_remove())
        return show_info(cid, uid, fid)

    if key not in INFO_FIELDS:
        return send(cid, "❌ نامعتبر", kb_remove())

    val = "" if text == "-" else text
    if key == "slug":
        val = clean_slug(val)
        if val and db_execute("SELECT id FROM forms WHERE slug=? AND id<>?",
                              (val, fid), fetch="one"):
            send(cid, "⚠️ این لینک تکراری است", kb_remove())
            return show_info(cid, uid, fid)
        if not val:
            val = gen_slug()
    elif key == "title":
        if len(val) < 3:
            send(cid, "⚠️ عنوان کوتاه است", kb_remove())
            return show_info(cid, uid, fid)
        val = val[:120]

    db_execute(f"UPDATE forms SET {key}=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (val, fid))
    send(cid, "✅ ذخیره شد", kb_remove())
    if key == "payment_note":
        return show_payment(cid, uid, fid)
    return show_info(cid, uid, fid)


# ==================== بنر و لوگو ====================
def show_media(cid, uid, fid):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    b = "✅ دارد" if form.get("banner_file_id") else "—"
    lg = "✅ دارد" if form.get("logo_file_id") else "—"
    send_or_edit(cid, (
        f"🖼️ بنر و لوگوی فرم\n━━━━━━━━━━━━━━\n\n"
        f"🖼️ تصویر سربرگ (بنر): {b}\n"
        f"🏷️ لوگو: {lg}\n\n"
        f"💡 بنر بالای صفحه ورود فرم نمایش داده می‌شود."
    ), {"inline_keyboard": [
        [{"text": "🖼️ تنظیم بنر", "callback_data": f"fbban_{fid}"}],
        [{"text": "🏷️ تنظیم لوگو", "callback_data": f"fblogo_{fid}"}],
        [{"text": "🗑️ حذف بنر", "callback_data": f"fbbandel_{fid}"},
         {"text": "🗑️ حذف لوگو", "callback_data": f"fblogodel_{fid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"fbv_{fid}"}],
    ]})


def start_media(cid, uid, fid, kind):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    set_state(uid, STATE_FB_EDIT, {"fid": fid, "key": f"media_{kind}"}, merge=False)
    nm = "بنر (تصویر سربرگ)" if kind == "banner" else "لوگو"
    send(cid, f"🖼️ {nm} را ارسال کنید:\n\n💡 یک عکس بفرستید.", kb_cancel())


def handle_media_photo(message):
    """دریافت عکس بنر/لوگو"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    data = get_state_data(uid)
    fid = data.get("fid")
    key = str(data.get("key") or "")
    if not key.startswith("media_"):
        return send(cid, "⚠️ حالت نامعتبر", kb_remove())

    photos = message.get("photo") or []
    if not photos:
        return send(cid, "⚠️ لطفاً یک عکس بفرستید", kb_cancel())
    file_id = photos[-1].get("file_id")
    col = "banner_file_id" if key == "media_banner" else "logo_file_id"
    db_execute(f"UPDATE forms SET {col}=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (file_id, fid))
    clear_state(uid)
    send(cid, "✅ تصویر ذخیره شد", kb_remove())
    return show_media(cid, uid, fid)


def delete_media(cid, uid, fid, kind):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    col = "banner_file_id" if kind == "banner" else "logo_file_id"
    db_execute(f"UPDATE forms SET {col}=NULL WHERE id=?", (fid,))
    send(cid, "🗑️ حذف شد")
    return show_media(cid, uid, fid)


# ==================== تنظیمات پرداخت فرم ====================
def show_payment(cid, uid, fid):
    """💳 تنظیمات پرداخت فرم — همان ۴ روش توافق‌شده"""
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")

    from payments import PAYMENT_METHODS, get_cards, get_gateways
    method = form.get("payment_method") or "none"
    pm = PAYMENT_METHODS.get(method, PAYMENT_METHODS["none"])

    lines = [
        "💳 تنظیمات پرداخت فرم",
        "━━━━━━━━━━━━━━",
        "",
        f"📋 فرم: {form['title']}",
        f"💰 مبلغ: {fmt_amount(form.get('price'))} {CURRENCY_LABEL}",
        f"🔧 روش: {pm['icon']} {pm['name']}",
        f"✔️ تأیید: {'خودکار' if pm.get('verify') == 'auto' else ('دستی توسط ادمین' if pm.get('verify') == 'manual' else '—')}",
    ]
    if method == "card":
        cards = get_cards()
        sel = form.get("payment_card_id")
        cur = next((c for c in cards if c["id"] == sel), None)
        lines.append(f"💳 کارت: {cur['bank_name'] if cur else 'پیش‌فرض'}")
    elif method == "custom_gateway":
        gws = get_gateways()
        sel = form.get("payment_gateway_id")
        cur = next((g for g in gws if g["id"] == sel), None)
        lines.append(f"🔗 درگاه: {cur['gateway_name'] if cur else 'پیش‌فرض'}")
    if form.get("payment_note"):
        lines.append(f"\n📄 راهنما: {str(form['payment_note'])[:120]}")

    btns = [[{"text": "💰 تعیین مبلغ", "callback_data": f"fbprice_{fid}"}]]
    for k, m in PAYMENT_METHODS.items():
        mark = "🔘" if k == method else "⚪"
        btns.append([{"text": f"{mark} {m['icon']} {m['name']}",
                      "callback_data": f"fbpm_{k}_{fid}"}])
    if method == "card":
        btns.append([{"text": "💳 انتخاب کارت", "callback_data": f"fbpcard_{fid}"}])
    elif method == "custom_gateway":
        btns.append([{"text": "🔗 انتخاب درگاه", "callback_data": f"fbpgw_{fid}"}])
    if method != "none":
        btns.append([{"text": "📄 راهنمای واریز", "callback_data": f"fbset_payment_note_{fid}"}])
    btns.append([{"text": ("💰 نمایش مبلغ در ابتدای فرم: ✅ بله"
                           if form.get("show_price_upfront")
                           else "🙈 نمایش مبلغ در ابتدای فرم: ❌ خیر"),
                  "callback_data": f"fbtog_show_price_upfront_{fid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbv_{fid}"}])

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_payment_method(cid, uid, fid, method):
    from payments import PAYMENT_METHODS
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    if method not in PAYMENT_METHODS:
        return send(cid, "❌ نامعتبر")
    m = PAYMENT_METHODS[method]
    ver = m.get("verify") if m.get("verify") in ("auto", "manual") else "manual"
    db_execute("UPDATE forms SET payment_method=?, payment_verification=?, "
               "is_free=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (method, ver, 1 if method == "none" else 0, fid))
    return show_payment(cid, uid, fid)


def start_price(cid, uid, fid):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    set_state(uid, STATE_FB_EDIT, {"fid": fid, "key": "price"}, merge=False)
    send(cid, (
        f"💰 مبلغ فرم\n━━━━━━━━━━━━━━\n\n"
        f"📌 فعلی: {fmt_amount(form.get('price'))} {CURRENCY_LABEL}\n\n"
        f"مبلغ جدید را به {CURRENCY_LABEL} وارد کنید:\n\n"
        f"مثال: 500000\n"
        f"💡 عدد ۰ = رایگان"
    ), kb_cancel())


def handle_price(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = normalize_digits((message.get("text") or "").strip())
    data = get_state_data(uid)
    fid = data.get("fid")

    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_payment(cid, uid, fid)

    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return send(cid, "⚠️ فقط عدد وارد کنید:", kb_cancel())
    # مبلغ ریال است — عیناً ذخیره می‌شود (بدون تبدیل)
    from config import parse_money
    amount = parse_money(digits)

    if amount > 0:
        from config import check_amount
        ok, msg = check_amount(amount)
        if not ok:
            return send(cid, f"⛔ {msg}\n\nمبلغ دیگری وارد کنید:", kb_cancel())

    clear_state(uid)
    db_execute("UPDATE forms SET price=?, is_free=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (amount, 1 if amount == 0 else 0, fid))
    send(cid, f"✅ مبلغ ثبت شد: {fmt_amount(amount)} {CURRENCY_LABEL}", kb_remove())
    return show_payment(cid, uid, fid)


def pick_card(cid, uid, fid, card_id=None):
    from payments import get_cards
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    if card_id is not None:
        db_execute("UPDATE forms SET payment_card_id=? WHERE id=?", (card_id, fid))
        return show_payment(cid, uid, fid)

    cards = get_cards()
    if not cards:
        return send_or_edit(cid, (
            "💳 هیچ کارتی ثبت نشده!\n\n"
            "ابتدا از «تنظیمات ← روش‌های پرداخت» کارت اضافه کنید."
        ), {"inline_keyboard": [
            [{"text": "➕ افزودن کارت", "callback_data": "card_add"}],
            [{"text": "🔙 بازگشت", "callback_data": f"fbpay_{fid}"}]]})

    from payments import mask_card
    btns = []
    for c in cards:
        mark = "🔘" if c["id"] == form.get("payment_card_id") else "⚪"
        btns.append([{"text": f"{mark} {c['bank_name']} — {mask_card(c['card_number'])}",
                      "callback_data": f"fbpcs_{c['id']}_{fid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbpay_{fid}"}])
    send_or_edit(cid, "💳 کارت مقصد را انتخاب کنید:", {"inline_keyboard": btns})


def pick_gateway(cid, uid, fid, gw_id=None):
    from payments import get_gateways
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    if gw_id is not None:
        db_execute("UPDATE forms SET payment_gateway_id=? WHERE id=?", (gw_id, fid))
        return show_payment(cid, uid, fid)

    gws = get_gateways()
    if not gws:
        return send_or_edit(cid, (
            "🔗 هیچ درگاهی ثبت نشده!\n\n"
            "ابتدا از «تنظیمات ← روش‌های پرداخت» درگاه تعریف کنید."
        ), {"inline_keyboard": [
            [{"text": "➕ تعریف درگاه", "callback_data": "gw_add"}],
            [{"text": "🔙 بازگشت", "callback_data": f"fbpay_{fid}"}]]})

    btns = []
    for g in gws:
        mark = "🔘" if g["id"] == form.get("payment_gateway_id") else "⚪"
        btns.append([{"text": f"{mark} {g['gateway_name']}",
                      "callback_data": f"fbpgs_{g['id']}_{fid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbpay_{fid}"}])
    send_or_edit(cid, "🔗 درگاه پرداخت را انتخاب کنید:", {"inline_keyboard": btns})


# ==================== تنظیمات پیشرفته (۸ بخش) ====================
def show_advanced(cid, uid, fid):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")

    dm = DISPLAY_MODES.get(form.get("display_mode") or "one_by_one",
                           DISPLAY_MODES["one_by_one"])
    td = TEXT_DIRS.get(form.get("text_dir") or "rtl", TEXT_DIRS["rtl"])
    lim = (f"✅ {form.get('max_responses')} نفر" if form.get("limit_enabled")
           and form.get("max_responses") else "❌ نامحدود")

    lines = [
        "⚙️ تنظیمات پیشرفته فرم",
        "━━━━━━━━━━━━━━",
        "",
        f"1️⃣ 💚 توضیحات پایانی: {'✅ دارد' if form.get('end_text') else '—'}",
        f"2️⃣ 🔔 اعلان پاسخ به ادمین: {'✅ فعال' if form.get('notify_admins') else '❌ خاموش'}",
        f"3️⃣ 🔤 جهت متون: {td['icon']} {td['name']}",
        f"4️⃣ 👁️ نحوه نمایش: {dm['icon']} {dm['name']}",
        f"5️⃣ 👥 محدودیت تعداد: {lim}",
        f"6️⃣ 🎫 بلیت: {'✅ فعال' if form.get('ticket_enabled') else '❌ غیرفعال'}",
        f"7️⃣ 📅 زمان شروع: {form.get('start_at') or '— (بلافاصله)'}",
        f"8️⃣ ⛔ زمان پایان: {form.get('end_at') or '— (بدون محدودیت)'}",
        "",
        "🔒 دسترسی:",
        f"   • احراز هویت: {'✅ لازم' if form.get('require_auth') else '❌ آزاد'}",
        f"   • پروفایل کامل: {'✅ لازم' if form.get('require_profile') else '❌ لازم نیست'}",
        f"   • یک پاسخ به ازای هر نفر: {'✅' if form.get('one_per_user') else '❌ چند بار مجاز'}",
        f"   • دسترسی بعد از ثبت: "
        + AFTER_SUBMIT[after_submit_of(form)]["icon"] + " "
        + AFTER_SUBMIT[after_submit_of(form)]["name"],
        f"   • پاسخ ناشناس: {'✅' if form.get('anonymous') else '❌'}",
        f"   • نوار پیشرفت: {'✅' if form.get('show_progress') else '❌'}",
        "",
        "👨‍💼 تأیید و پروفایل:",
        f"   • تأیید ادمین لازم: {'✅ بله' if form.get('needs_approval') else '❌ خودکار'}",
        f"   • پرکردن پروفایل کاربر: {'✅' if form.get('fill_profile', 1) else '❌'}",
        f"   • روش تأیید شماره: "
        + PHONE_VERIFY_MODES.get(
            (form.get("phone_verify_mode") or "both"),
            PHONE_VERIFY_MODES["both"])["name"],
    ]

    # 🧹 فاز ۴۰ — از ۱۹ ردیف به ۱۰ ردیف
    #    قانون کاربر: «حداکثر ۱۰ دکمه در هر صفحه»
    #    کلیدهای روشن/خاموش هم‌خانواده دوستونی شدند.
    def _m(v):
        return "✅" if v else "❌"

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        # ─── متن‌ها ───
        [{"text": "👋 خوش‌آمدگویی",
          "callback_data": f"fbset_welcome_text_{fid}"},
         {"text": "💚 توضیحات پایانی",
          "callback_data": f"fbset_end_text_{fid}"}],
        # ─── ظاهر ───
        [{"text": "🔤 جهت متون", "callback_data": f"fbdir_{fid}"},
         {"text": "👁️ نحوه نمایش", "callback_data": f"fbdisp_{fid}"}],
        [{"text": f"📊 نوار پیشرفت {_m(form.get('show_progress'))}",
          "callback_data": f"fbtog_show_progress_{fid}"},
         {"text": f"🕶️ ناشناس {_m(form.get('anonymous'))}",
          "callback_data": f"fbtog_anonymous_{fid}"}],
        # ─── دسترسی ───
        [{"text": f"🔐 احراز هویت {_m(form.get('require_auth'))}",
          "callback_data": f"fbtog_require_auth_{fid}"},
         {"text": f"📋 پروفایل کامل {_m(form.get('require_profile'))}",
          "callback_data": f"fbtog_require_profile_{fid}"}],
        [{"text": f"1️⃣ یک پاسخ per نفر {_m(form.get('one_per_user'))}",
          "callback_data": f"fbtog_one_per_user_{fid}"},
         {"text": "📱 تأیید شماره", "callback_data": f"fbpv_{fid}"}],
        # ─── زمان و ظرفیت ───
        [{"text": "📅 زمان شروع",
          "callback_data": f"fbtime_start_{fid}"},
         {"text": "⛔ زمان پایان",
          "callback_data": f"fbtime_end_{fid}"}],
        [{"text": "👥 محدودیت تعداد",
          "callback_data": f"fblimit_{fid}"},
         {"text": "🔐 دسترسی بعد از ثبت",
          "callback_data": f"fbafter_{fid}"}],
        # ─── خروجی‌ها ───
        [{"text": f"🎫 بلیت {_m(form.get('ticket_enabled'))}",
          "callback_data": f"fbtog_ticket_enabled_{fid}"},
         {"text": f"🎓 گواهینامه {_m(form.get('cert_enabled'))}",
          "callback_data": f"fbtog_cert_enabled_{fid}"}],
        [{"text": f"🆔 آیدی کارت {_m(form.get('idcard_enabled'))}",
          "callback_data": f"fbtog_idcard_enabled_{fid}"},
         {"text": f"👤 پرکردن پروفایل "
                  f"{_m(form.get('fill_profile', 1))}",
          "callback_data": f"fbtog_fill_profile_{fid}"}],
        # ─── پیشرفته ───
        [{"text": "⋮ بیشتر", "callback_data": f"fbadv2_{fid}"},
         {"text": "🔙 بازگشت", "callback_data": f"fbv_{fid}"}],
    ]})


def show_advanced2(cid, uid, fid):
    """
    ⋮ لایهٔ دوم تنظیمات پیشرفتهٔ فرم — فاز ۴۰

    🎯 صفحهٔ «⋮ پیشرفته» ۱۹ ردیف دکمه داشت و از سقف ۱۰ ردیف
       رد می‌شد. این موارد به اینجا منتقل شدند:
       تأیید ادمین · ارتباط · گردش کار · قرعه‌کشی · وبهوک
    """
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")

    def _m(v):
        return "✅" if v else "❌"

    lines = ["⋮ تنظیمات پیشرفته", "━━━━━━━━━━━━━━", "",
             f"📋 {form['title']}", ""]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": f"👨‍💼 تأیید ادمین لازم "
                  f"{_m(form.get('needs_approval'))}",
          "callback_data": f"fbtog_needs_approval_{fid}"}],
        [{"text": f"💬 ارتباط تکمیل‌کننده "
                  f"{_m(form.get('contact_enabled'))}",
          "callback_data": f"fbtog_contact_enabled_{fid}"}],
        [{"text": f"🔀 گردش کار "
                  f"{_m(form.get('workflow_enabled'))}",
          "callback_data": f"fbtog_workflow_enabled_{fid}"}],
        [{"text": "🎲 قرعه‌کشی و انتخاب برنده",
          "callback_data": f"lt_form_{fid}"}],
        [{"text": ("🔗 وبهوک: ✅ فعال" if form.get("webhook_url")
                   else "🔗 وبهوک و رخدادها"),
          "callback_data": f"fbset_webhook_url_{fid}"}],
        [{"text": "🔙 تنظیمات پیشرفته",
          "callback_data": f"fbadv_{fid}"}],
    ]})


def show_phone_mode(cid, uid, fid):
    """📱 انتخاب روش تأیید شماره — دکمه اشتراک یا کد یکبار مصرف"""
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    cur = (form.get("phone_verify_mode") or "both").strip().lower()

    lines = ["📱 روش تأیید شماره موبایل", "━━━━━━━━━━━━━━", "",
             "برای سوال «تأیید شماره موبایل» کدام روش باشد؟", ""]
    btns = []
    for k, v in PHONE_VERIFY_MODES.items():
        lines.append(f"{v['icon']} {v['name']}\n   {v['desc']}\n")
        btns.append([{"text": f"{'🔘' if k == cur else '⚪'} {v['icon']} {v['name']}",
                      "callback_data": f"fbpvs_{k}_{fid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbadv_{fid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_phone_mode(cid, uid, fid, mode):
    if mode not in PHONE_VERIFY_MODES:
        return send(cid, "❌ نامعتبر")
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    db_execute("UPDATE forms SET phone_verify_mode=? WHERE id=?", (mode, fid))
    return show_advanced(cid, uid, fid)


TOGGLE_COLS = {
    "notify_admins", "ticket_enabled", "require_auth", "require_profile",
    "one_per_user", "allow_edit", "anonymous", "show_progress", "limit_enabled",
    "needs_approval", "fill_profile", "show_price_upfront",
    # 🆕 فاز ۱۵
    "cert_enabled", "idcard_enabled", "contact_enabled",
    # 🆕 فاز ۱۷
    "workflow_enabled",
}

PHONE_VERIFY_MODES = {
    "contact": {"icon": "📱", "name": "فقط دکمه اشتراک شماره",
                "desc": "سریع‌ترین — شماره از خود بله گرفته می‌شود"},
    "otp":     {"icon": "🔢", "name": "فقط کد یکبار مصرف",
                "desc": "کاربر شماره را تایپ می‌کند و کد پیامکی می‌گیرد"},
    "both":    {"icon": "🔀", "name": "هر دو (به انتخاب کاربر)",
                "desc": "کاربر هرکدام را خواست استفاده می‌کند"},
}


def toggle_setting(cid, uid, fid, col):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    if col not in TOGGLE_COLS:
        return send(cid, "❌ نامعتبر")
    new = 0 if form.get(col) else 1
    db_execute(f"UPDATE forms SET {col}=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (new, fid))
    if col == "show_price_upfront":
        return show_payment(cid, uid, fid)
    return show_advanced(cid, uid, fid)


def show_dir(cid, uid, fid):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    cur = form.get("text_dir") or "rtl"
    btns = [[{"text": f"{'🔘' if k == cur else '⚪'} {v['icon']} {v['name']}",
              "callback_data": f"fbdirs_{k}_{fid}"}] for k, v in TEXT_DIRS.items()]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbadv_{fid}"}])
    send_or_edit(cid, (
        "🔤 جهت متون\n━━━━━━━━━━━━━━\n\n"
        "جهت نمایش متون فرم به کاربر:\n\n"
        "💡 چپ‌چین برای فرم‌های انگلیسی مناسب است."
    ), {"inline_keyboard": btns})


def set_dir(cid, uid, fid, d):
    if d not in TEXT_DIRS:
        return send(cid, "❌ نامعتبر")
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    db_execute("UPDATE forms SET text_dir=? WHERE id=?", (d, fid))
    return show_advanced(cid, uid, fid)


def show_display(cid, uid, fid):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    cur = form.get("display_mode") or "one_by_one"
    lines = ["👁️ نحوه نمایش سوالات", "━━━━━━━━━━━━━━", ""]
    btns = []
    for k, v in DISPLAY_MODES.items():
        lines.append(f"{v['icon']} {v['name']}\n   {v['desc']}\n")
        btns.append([{"text": f"{'🔘' if k == cur else '⚪'} {v['icon']} {v['name']}",
                      "callback_data": f"fbdisps_{k}_{fid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbadv_{fid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_display(cid, uid, fid, mode):
    if mode not in DISPLAY_MODES:
        return send(cid, "❌ نامعتبر")
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    db_execute("UPDATE forms SET display_mode=? WHERE id=?", (mode, fid))
    return show_advanced(cid, uid, fid)


def show_limit(cid, uid, fid):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    on = bool(form.get("limit_enabled"))
    send_or_edit(cid, (
        f"👥 محدودیت تعداد پاسخ\n━━━━━━━━━━━━━━\n\n"
        f"وضعیت: {'✅ فعال' if on else '❌ غیرفعال'}\n"
        f"ظرفیت: {form.get('max_responses') or '—'}\n"
        f"پاسخ فعلی: {form.get('responses_count') or 0}\n\n"
        f"💡 پس از تکمیل ظرفیت، فرم پذیرش نمی‌کند."
    ), {"inline_keyboard": [
        [{"text": ("🚫 غیرفعال کردن محدودیت" if on else "✅ فعال کردن محدودیت"),
          "callback_data": f"fbtog_limit_enabled_{fid}"}],
        [{"text": "🔢 تعیین ظرفیت", "callback_data": f"fbmax_{fid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"fbadv_{fid}"}],
    ]})


def start_max(cid, uid, fid):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    set_state(uid, STATE_FB_ADV, {"fid": fid, "key": "max_responses"}, merge=False)
    send(cid, (
        f"🔢 حداکثر تعداد پاسخ\n━━━━━━━━━━━━━━\n\n"
        f"📌 فعلی: {form.get('max_responses') or '—'}\n\n"
        f"عدد وارد کنید (۰ = نامحدود):"
    ), kb_cancel())


def start_time(cid, uid, fid, which):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    col = "start_at" if which == "start" else "end_at"
    nm = "📅 زمان شروع پذیرش" if which == "start" else "⛔ زمان پایان پذیرش"
    set_state(uid, STATE_FB_ADV, {"fid": fid, "key": col}, merge=False)
    send(cid, (
        f"{nm}\n━━━━━━━━━━━━━━\n\n"
        f"📌 فعلی: {form.get(col) or '— (بدون محدودیت)'}\n\n"
        f"تاریخ و ساعت شمسی را بنویسید:\n\n"
        f"مثال: 1405/05/02 21:55\n"
        f"یا فقط تاریخ: 1405/05/02\n\n"
        f"💡 برای حذف محدودیت، «-» بفرستید."
    ), kb_cancel())


def handle_adv_input(message):
    """ورودی‌های عددی/تاریخی تنظیمات پیشرفته"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = normalize_digits((message.get("text") or "").strip())
    data = get_state_data(uid)
    fid = data.get("fid")
    key = data.get("key")

    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_advanced(cid, uid, fid)

    if key == "max_responses":
        digits = "".join(ch for ch in text if ch.isdigit())
        if not digits:
            return send(cid, "⚠️ فقط عدد وارد کنید:", kb_cancel())
        n = int(digits)
        clear_state(uid)
        db_execute("UPDATE forms SET max_responses=?, limit_enabled=? WHERE id=?",
                   (n, 1 if n > 0 else 0, fid))
        send(cid, f"✅ ظرفیت: {n if n else 'نامحدود'}", kb_remove())
        return show_limit(cid, uid, fid)

    if key in ("start_at", "end_at"):
        # ⚠️ state فقط بعد از موفقیت پاک می‌شود، وگرنه کاربر
        #    نمی‌تواند دوباره تلاش کند (باگ: ورودی بعدی گم می‌شد)
        if text == "-":
            clear_state(uid)
            db_execute(f"UPDATE forms SET {key}=NULL WHERE id=?", (fid,))
            send(cid, "✅ محدودیت زمانی حذف شد", kb_remove())
            return show_advanced(cid, uid, fid)
        ok, norm = validate_jdatetime(text)
        if not ok:
            return send(cid, (
                "❌ فرمت نامعتبر!\n\n"
                "نمونه صحیح: 1405/05/02 21:55\n\n"
                "دوباره بنویسید یا «🔙 بازگشت» را بزنید:"
            ), kb_cancel())
        clear_state(uid)
        db_execute(f"UPDATE forms SET {key}=? WHERE id=?", (norm, fid))
        send(cid, f"✅ ثبت شد: {norm}", kb_remove())
        return show_advanced(cid, uid, fid)

    clear_state(uid)
    return send(cid, "⚠️ نامعتبر", kb_remove())


def validate_jdatetime(text):
    """
    اعتبارسنجی تاریخ/ساعت شمسی.
    خروجی: (ok, 'YYYY/MM/DD HH:MM')
    """
    s = normalize_digits(str(text or "").strip()).replace("-", "/")
    parts = s.split()
    date_part = parts[0] if parts else ""
    time_part = parts[1] if len(parts) > 1 else "00:00"

    d = date_part.split("/")
    if len(d) != 3:
        return False, ""
    try:
        y, m, dd = int(d[0]), int(d[1]), int(d[2])
    except ValueError:
        return False, ""
    if not (1300 <= y <= 1500 and 1 <= m <= 12 and 1 <= dd <= 31):
        return False, ""
    if m > 6 and dd > 30:
        return False, ""
    if m == 12 and dd > 30:
        return False, ""

    t = time_part.replace(".", ":").split(":")
    try:
        hh = int(t[0])
        mm = int(t[1]) if len(t) > 1 else 0
    except (ValueError, IndexError):
        return False, ""
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return False, ""

    return True, f"{y:04d}/{m:02d}/{dd:02d} {hh:02d}:{mm:02d}"


def jnow():
    """تاریخ و ساعت جاری شمسی (تبدیل ساده و دقیق میلادی→شمسی)"""
    g = datetime.now()
    jy, jm, jd = g2j(g.year, g.month, g.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d} {g.hour:02d}:{g.minute:02d}"


def g2j(gy, gm, gd):
    """تبدیل میلادی به شمسی (الگوریتم استاندارد)"""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1
    g_day_no = (365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100
                + (gy2 + 399) // 400 + g_d_m[gm2] + gd2)
    if gm > 2 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
        g_day_no += 1
    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365
    if j_day_no < 186:
        jm = 1 + j_day_no // 31
        jd = 1 + j_day_no % 31
    else:
        jm = 7 + (j_day_no - 186) // 30
        jd = 1 + (j_day_no - 186) % 30
    return jy, jm, jd


def jdt_key(s):
    """
    تبدیل '1405/05/02 21:55' به عدد قابل مقایسه 140505022155.
    برای مقایسه زمان شروع/پایان استفاده می‌شود.
    """
    if not s:
        return None
    ok, norm = validate_jdatetime(s)
    if not ok:
        return None
    d, t = norm.split()
    y, m, dd = d.split("/")
    hh, mm = t.split(":")
    return int(f"{y}{m}{dd}{hh}{mm}")


def form_gate(form, uid=None, strict=True):
    """
    آیا فرم در حال حاضر پذیرش دارد؟
    خروجی: (ok, reason_key, extra)

    🆕 فاز ۱۸-الف: قوانین ویژه هر نوع فرم هم اینجا اعمال می‌شود
       (مهلت مسابقه، بازه رأی‌گیری، دفعات مجاز شرکت و…)
    """
    if not form:
        return False, "notfound", ""
    if form.get("status") != "active":
        return False, "closed", ""

    now = jdt_key(jnow())
    st = jdt_key(form.get("start_at"))
    en = jdt_key(form.get("end_at"))
    if st and now and now < st:
        return False, "not_started", form.get("start_at")
    if en and now and now > en:
        return False, "expired", form.get("end_at")

    ftype = form.get("form_type") or "questionnaire"

    # 🏆 مهلت مسابقه
    if ftype == "contest" and form.get("contest_deadline"):
        dl = jdt_key(form["contest_deadline"])
        if dl and now and now > dl:
            return False, "expired", form["contest_deadline"]

    # 🗳️ بازه رأی‌گیری
    if ftype == "election":
        vs = jdt_key(form.get("vote_start"))
        ve = jdt_key(form.get("vote_end"))
        if vs and now and now < vs:
            return False, "not_started", form.get("vote_start")
        if ve and now and now > ve:
            return False, "expired", form.get("vote_end")

    # 🔁 دفعات مجاز شرکت (آزمون/مسابقه/ثبت اطلاعات)
    #    ⚠️ فقط هنگام باز کردن فرم بررسی می‌شود (strict=True)، نه در
    #    ساختن فهرست — وگرنه فرم‌های پرشده از لیست غیب می‌شوند.
    if uid and strict:
        mx = int(form.get("max_attempts") or 0)
        if mx > 0:
            done = db_scalar(
                "SELECT COUNT(*) FROM form_responses WHERE form_id=? "
                "AND bale_user_id=? AND status IN "
                "('completed','confirmed')", (form["id"], uid)) or 0
            if done >= mx:
                return False, "max_attempts", str(mx)

    if form.get("limit_enabled") and form.get("max_responses"):
        n = db_scalar("SELECT COUNT(*) FROM form_responses WHERE form_id=? "
                      "AND status IN ('completed','confirmed')", (form["id"],))
        if n >= int(form["max_responses"]):
            # ⏳ لیست انتظار (اگر ادمین فعال کرده باشد)
            if form.get("waitlist_enabled"):
                return False, "waitlist", ""
            return False, "full", ""

    # 🎉 فاز ۳۳ — فرم وابسته به رویداد فقط برای شرکت‌کنندگان
    #
    # 🎯 «بعضی فرم‌های اختصاصی رویدادها رو فقط برای رویدادها
    #     میسازم مثل فرم نظرسنجی، ولی وقتی تأیید و انتشار
    #     میزنم همه کاربرا میتونن ببینن»
    #
    # 🔴 قبلاً event_id هیچ اثری روی دسترسی نداشت. فرم نظرسنجی
    #    یک رویداد خاص، در فهرست عمومی همه دیده می‌شد.
    if uid and form.get("event_id"):
        ok, why = event_form_gate(form, uid)
        if not ok:
            return False, why, str(form.get("event_id"))

    return True, "", ""


def event_form_gate(form, uid):
    """
    🎉 آیا این کاربر اجازهٔ دیدن فرم وابسته به رویداد را دارد؟

    خروجی: (بله/خیر، کلید دلیل)

    سه سطح دسترسی — از پنل قابل تنظیم با `ev_form_access`:
      registered  فقط ثبت‌نام‌شده‌ها (پیش‌فرض)
      attended    فقط کسانی که حضورشان ثبت شده
      public      همه (رفتار قدیمی)
    """
    eid = form.get("event_id")
    if not eid:
        return True, ""

    mode = (form.get("event_access")
            or get_setting("ev_form_access", "registered")
            or "registered").strip()
    if mode == "public":
        return True, ""

    reg = db_execute(
        "SELECT * FROM event_registrations "
        "WHERE event_id=? AND bale_user_id=?",
        (int(eid), int(uid)), fetch="one")
    if not reg:
        return False, "ev_not_registered"

    st = (reg.get("status") or "").lower()
    if st in ("cancelled", "rejected"):
        return False, "ev_not_registered"

    if mode == "attended":
        n = db_scalar(
            "SELECT COUNT(*) FROM attendance_records WHERE event_id=? "
            "AND bale_user_id=? AND status IN ('present','late')",
            (int(eid), int(uid))) or 0
        if not n:
            return False, "ev_not_attended"

    return True, ""


# ==================== کش پاسخ‌های کاربر (پیشنهاد خودکار) ====================
def cache_answer(uid, cache_key, value):
    """ذخیره پاسخ برای پیشنهاد در فرم‌های بعدی"""
    if not (uid and cache_key and value):
        return
    v = str(value).strip()[:200]
    if not v:
        return
    row = db_execute(
        "SELECT id, used_count FROM user_field_cache "
        "WHERE bale_user_id=? AND cache_key=? AND value=?", (uid, cache_key, v),
        fetch="one")
    if row:
        db_execute("UPDATE user_field_cache SET used_count=used_count+1, "
                   "last_used_at=CURRENT_TIMESTAMP WHERE id=?", (row["id"],))
    else:
        db_execute("INSERT INTO user_field_cache (bale_user_id, cache_key, value) "
                   "VALUES (?,?,?)", (uid, cache_key, v))


def get_suggestions(uid, cache_key, limit=3):
    """پیشنهادهای قبلی کاربر برای این نوع فیلد"""
    if not (uid and cache_key):
        return []
    rows = db_execute(
        "SELECT value FROM user_field_cache WHERE bale_user_id=? AND cache_key=? "
        "ORDER BY used_count DESC, last_used_at DESC LIMIT ?",
        (uid, cache_key, int(limit)), fetch="all") or []
    return [r["value"] for r in rows if r.get("value")]


# ==================== تنظیمات کلی فرم‌ساز ====================
def show_settings(cid, uid):
    if not _guard(cid, uid):
        return
    total = db_scalar("SELECT COUNT(*) FROM forms")
    resp = db_scalar("SELECT COUNT(*) FROM form_responses")
    cache = db_scalar("SELECT COUNT(*) FROM user_field_cache")
    send_or_edit(cid, (
        "⚙️ تنظیمات فرم‌ساز\n━━━━━━━━━━━━━━\n\n"
        f"📋 کل فرم‌ها: {total}\n"
        f"📊 کل پاسخ‌ها: {resp}\n"
        f"💾 کش پیشنهاد خودکار: {cache} رکورد\n\n"
        "همه متن‌های فرم‌ساز از اینجا قابل تغییر است."
    ), {"inline_keyboard": [
        [{"text": "📝 متن‌های فرم‌ساز", "callback_data": "fb_texts"}],
        [{"text": "🏷️ برچسب‌های عمومی", "callback_data": "fb_gtags"}],
        [{"text": "🧹 پاکسازی کش پیشنهادها", "callback_data": "fb_clearcache"}],
        [{"text": "🗑️ حذف پاسخ‌های پیش‌نویس", "callback_data": "fb_cleandraft"}],
        [{"text": "🔙 پنل فرم‌ساز", "callback_data": "fb_panel"}],
    ]})


def show_texts(cid, uid):
    if not _guard(cid, uid):
        return
    lines = ["📝 متن‌های فرم‌ساز", "━━━━━━━━━━━━━━", "",
             "متغیرهای قابل استفاده:",
             "{title} {description} {tracking} {qr} {name} {date}",
             "{amount} {currency} {fields} {minutes} {end_text} {hint}",
             "{start} {end} {reason} {note} {back}", ""]
    btns = []
    for key, title, _ in FORM_TEXTS:
        cur = get_setting(key, "")
        mark = "✏️" if cur else "📄"
        btns.append([{"text": f"{mark} {title}", "callback_data": f"fbtxt_{key}"}])
    btns.append([{"text": "♻️ بازگردانی همه به پیش‌فرض", "callback_data": "fb_txtreset"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "fb_settings"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_edit_text(cid, uid, key):
    if not _guard(cid, uid):
        return
    item = next((x for x in FORM_TEXTS if x[0] == key), None)
    if not item:
        return send(cid, "❌ نامعتبر")
    _, title, default = item
    cur = get_setting(key, default)
    set_state(uid, STATE_FB_TEXT, {"key": key}, merge=False)
    send(cid, (
        f"{title}\n━━━━━━━━━━━━━━\n\n"
        f"📄 متن فعلی:\n{cur}\n\n"
        f"✍️ متن جدید را بنویسید:\n\n"
        f"💡 «-» = بازگردانی به پیش‌فرض"
    ), kb_cancel())


def handle_edit_text(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    data = get_state_data(uid)
    key = data.get("key")
    clear_state(uid)

    if text in (BTN_BACK, "🔙 بازگشت"):
        send(cid, "❌ لغو شد", kb_remove())
        return show_texts(cid, uid)

    item = next((x for x in FORM_TEXTS if x[0] == key), None)
    if not item:
        return send(cid, "❌ نامعتبر", kb_remove())
    _, title, default = item
    val = default if text == "-" else text[:3000]
    set_setting(key, val, title, "forms", uid)
    send(cid, "✅ متن ذخیره شد", kb_remove())
    return show_texts(cid, uid)


def reset_texts(cid, uid):
    if not _guard(cid, uid):
        return
    for key, title, default in FORM_TEXTS:
        set_setting(key, default, title, "forms", uid)
    send(cid, "♻️ همه متن‌ها به پیش‌فرض برگشت")
    return show_texts(cid, uid)


def clear_cache(cid, uid):
    if not _guard(cid, uid):
        return
    n = db_scalar("SELECT COUNT(*) FROM user_field_cache")
    db_execute("DELETE FROM user_field_cache")
    send(cid, f"🧹 {n} رکورد کش پاک شد")
    return show_settings(cid, uid)


def clean_drafts(cid, uid):
    if not _guard(cid, uid):
        return
    rows = db_execute("SELECT id FROM form_responses WHERE status='draft'",
                      fetch="all") or []
    for r in rows:
        db_execute("DELETE FROM form_answers WHERE response_id=?", (r["id"],))
    db_execute("DELETE FROM form_responses WHERE status='draft'")
    send(cid, f"🗑️ {len(rows)} پاسخ نیمه‌کاره حذف شد")
    return show_settings(cid, uid)


# ==================== ادمین‌های فرم ====================
def show_form_admins(cid, uid, fid):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    rows = db_execute("""SELECT a.*, u.first_name, u.last_name, u.mobile
        FROM form_admins a LEFT JOIN users u ON u.bale_user_id=a.bale_user_id
        WHERE a.form_id=?""", (fid,), fetch="all") or []

    owner = db_execute("SELECT first_name, last_name FROM users WHERE bale_user_id=?",
                       (form.get("owner_id"),), fetch="one") or {}
    lines = [
        "👥 ادمین‌های این فرم", "━━━━━━━━━━━━━━", "",
        f"👑 مالک: {owner.get('first_name') or '—'} {owner.get('last_name') or ''}",
        "",
    ]
    btns = []
    if rows:
        for r in rows:
            nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or "—"
            lines.append(f"👤 {nm} ({r['bale_user_id']})")
            btns.append([{"text": f"🗑️ حذف {nm}", "callback_data": f"fbadmdel_{r['id']}_{fid}"}])
    else:
        lines.append("📭 ادمین دیگری تعریف نشده")

    btns.append([{"text": "➕ افزودن ادمین", "callback_data": f"fbadmadd_{fid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbmore_{fid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_add_form_admin(cid, uid, fid):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    set_state(uid, STATE_FB_EDIT, {"fid": fid, "key": "add_admin"}, merge=False)
    send(cid, (
        "➕ افزودن ادمین فرم\n━━━━━━━━━━━━━━\n\n"
        "آیدی عددی بله یا شماره موبایل کاربر را بفرستید:\n\n"
        "💡 کاربر باید قبلاً در ربات ثبت‌نام کرده باشد."
    ), kb_cancel())


def handle_add_form_admin(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = normalize_digits((message.get("text") or "").strip())
    data = get_state_data(uid)
    fid = data.get("fid")

    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_form_admins(cid, uid, fid)

    from auth import normalize_mobile
    target = None
    if text.isdigit() and len(text) < 12:
        target = db_execute("SELECT * FROM users WHERE bale_user_id=?",
                            (int(text),), fetch="one")
    if not target:
        mob = normalize_mobile(text)
        if mob:
            target = db_execute("SELECT * FROM users WHERE mobile=?", (mob,), fetch="one")

    if not target or not target.get("bale_user_id"):
        return send(cid, (
            "❌ کاربر پیدا نشد.\n\n"
            "آیدی عددی یا موبایل صحیح بفرستید:"
        ), kb_cancel())

    clear_state(uid)
    tid = target["bale_user_id"]
    if db_execute("SELECT id FROM form_admins WHERE form_id=? AND bale_user_id=?",
                  (fid, tid), fetch="one"):
        send(cid, "⚠️ این کاربر قبلاً ادمین این فرم است", kb_remove())
        return show_form_admins(cid, uid, fid)

    db_execute("INSERT INTO form_admins (form_id, bale_user_id, role, added_by) "
               "VALUES (?,?,'editor',?)", (fid, tid, uid))
    if not target.get("is_admin"):
        db_execute("UPDATE users SET is_admin=1 WHERE bale_user_id=?", (tid,))

    form = get_form(fid)
    nm = f"{target.get('first_name') or ''} {target.get('last_name') or ''}".strip()
    send(cid, f"✅ {nm or tid} به ادمین‌های فرم اضافه شد", kb_remove())
    send(tid, (
        f"👥 شما به ادمین‌های فرم زیر اضافه شدید:\n\n"
        f"📋 {form['title'] if form else ''}\n\n"
        f"از «پنل ادمین ← فرم‌ساز» می‌توانید مدیریت کنید."
    ))
    return show_form_admins(cid, uid, fid)


def remove_form_admin(cid, uid, row_id, fid):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    db_execute("DELETE FROM form_admins WHERE id=?", (int(row_id),))
    send(cid, "🗑️ حذف شد")
    return show_form_admins(cid, uid, fid)


# ==================== اتصال به رویداد ====================
def show_link_event(cid, uid, fid, eid=None):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")

    if eid is not None:
        db_execute("UPDATE forms SET event_id=? WHERE id=?",
                   (eid if eid > 0 else None, fid))
        send(cid, "✅ اتصال به‌روزرسانی شد" if eid > 0 else "🔗 اتصال حذف شد")
        return show_more(cid, uid, fid)

    rows = db_execute("SELECT id, title FROM events ORDER BY id DESC LIMIT 12",
                      fetch="all") or []
    cur = form.get("event_id")
    acc = (form.get("event_access") or "registered").strip()
    lines = ["🔗 اتصال فرم به رویداد", "━━━━━━━━━━━━━━", "",
             "پاسخ‌های این فرم به رویداد انتخابی نسبت داده می‌شود.", ""]

    # 🎉 فاز ۳۳ — وقتی وصل است، سطح دسترسی هم مهم می‌شود
    if cur:
        lines += [f"👁️ دسترسی فعلی: {EV_ACCESS.get(acc, ('—',))[0]}",
                  f"   {EV_ACCESS.get(acc, ('', ''))[1]}", ""]

    btns = [[{"text": f"{'🔘' if not cur else '⚪'} بدون اتصال",
              "callback_data": f"fblev_0_{fid}"}]]
    if rows:
        for e in rows:
            mark = "🔘" if cur == e["id"] else "⚪"
            btns.append([{"text": f"{mark} {e['title'][:35]}",
                          "callback_data": f"fblev_{e['id']}_{fid}"}])
    else:
        lines.append("📭 رویدادی تعریف نشده")
    if cur:
        btns.append([{"text": f"👁️ دسترسی: {EV_ACCESS.get(acc, ('—',))[0]}",
                      "callback_data": f"fbeva_{fid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbmore_{fid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# 👁️ سطوح دسترسی فرم وابسته به رویداد
EV_ACCESS = {
    "registered": ("🎫 فقط ثبت‌نام‌شده‌ها",
                   "هرکس در رویداد ثبت‌نام کرده"),
    "attended":   ("✅ فقط حاضران",
                   "هرکس حضورش ثبت شده باشد"),
    "public":     ("🌍 همه",
                   "در فهرست عمومی هم دیده می‌شود"),
}


def show_event_access(cid, uid, fid, mode=None):
    """
    👁️ چه کسی این فرم وابسته به رویداد را ببیند؟

    🎯 «فرم‌های اختصاصی رویدادها فقط برای رویدادها میسازم ولی
        وقتی انتشار میزنم همه کاربرا میتونن ببینن»
    """
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")

    if mode:
        if mode not in EV_ACCESS:
            return send(cid, "❌ نامعتبر")
        db_execute("UPDATE forms SET event_access=? WHERE id=?", (mode, fid))
        send(cid, f"✅ {EV_ACCESS[mode][0]}")
        return show_link_event(cid, uid, fid)

    cur = (form.get("event_access") or "registered").strip()
    ev = None
    if form.get("event_id"):
        ev = db_execute("SELECT title FROM events WHERE id=?",
                        (form["event_id"],), fetch="one")

    lines = ["👁️ چه کسی این فرم را ببیند؟", "━━━━━━━━━━━━━━", ""]
    if ev:
        lines += [f"🎉 رویداد: {ev.get('title') or '—'}", ""]
    lines += ["این فرم به یک رویداد وصل است. تعیین کنید چه",
              "کسانی بتوانند بازش کنند:", ""]
    btns = []
    for k, (nm, desc) in EV_ACCESS.items():
        mark = "🔘" if k == cur else "▫️"
        lines.append(f"{mark} {nm}")
        lines.append(f"     {desc}")
        btns.append([{"text": f"{mark} {nm}",
                      "callback_data": f"fbevs_{k}_{fid}"}])
    lines += ["", "💡 «فقط ثبت‌نام‌شده‌ها» برای نظرسنجی پس از",
              "   رویداد مناسب‌ترین است."]
    btns.append([{"text": "🔙 اتصال رویداد",
                  "callback_data": f"fblinkev_{fid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ==================== پاسخ‌های همه فرم‌ها ====================
def show_all_responses(cid, uid):
    if not _guard(cid, uid):
        return
    from config import SUPER_ADMIN_ID
    if uid == SUPER_ADMIN_ID:
        rows = db_execute("""SELECT f.id, f.title, f.form_type,
            (SELECT COUNT(*) FROM form_responses r WHERE r.form_id=f.id
             AND r.status IN ('completed','confirmed')) AS n
            FROM forms f ORDER BY n DESC, f.id DESC LIMIT 20""", fetch="all") or []
    else:
        rows = db_execute("""SELECT f.id, f.title, f.form_type,
            (SELECT COUNT(*) FROM form_responses r WHERE r.form_id=f.id
             AND r.status IN ('completed','confirmed')) AS n
            FROM forms f WHERE f.owner_id=?
              OR f.id IN (SELECT form_id FROM form_admins WHERE bale_user_id=?)
            ORDER BY n DESC, f.id DESC LIMIT 20""", (uid, uid), fetch="all") or []

    if not rows:
        return send_or_edit(cid, (
            "📊 پاسخ‌های دریافتی\n━━━━━━━━━━━━━━\n\n📭 هنوز فرمی ندارید."
        ), {"inline_keyboard": [
            [{"text": "➕ ایجاد فرم", "callback_data": "fb_new"}],
            [{"text": "🔙 پنل فرم‌ساز", "callback_data": "fb_panel"}]]})

    lines = ["📊 پاسخ‌های دریافتی", "━━━━━━━━━━━━━━", ""]
    btns = []
    for r in rows:
        t = FORM_TYPES.get(r.get("form_type") or "questionnaire", FORM_TYPES["questionnaire"])
        lines.append(f"{t['icon']} {r['title'][:32]} — {r['n']} پاسخ")
        if r["n"]:
            btns.append([{"text": f"📊 {r['title'][:28]} ({r['n']})",
                          "callback_data": f"fbr_{r['id']}"}])
    btns.append([{"text": "🔙 پنل فرم‌ساز", "callback_data": "fb_panel"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_all_stats(cid, uid):
    """📈 گزارش کلی فرم‌ساز"""
    if not _guard(cid, uid):
        return
    total = db_scalar("SELECT COUNT(*) FROM forms")
    active = db_scalar("SELECT COUNT(*) FROM forms WHERE status='active'")
    resp = db_scalar("SELECT COUNT(*) FROM form_responses "
                     "WHERE status IN ('completed','confirmed')")
    draft = db_scalar("SELECT COUNT(*) FROM form_responses WHERE status='draft'")
    paid = db_scalar("SELECT COALESCE(SUM(amount),0) FROM form_responses "
                     "WHERE payment_status='paid'")

    lines = ["📈 گزارش کلی فرم‌ساز", "━━━━━━━━━━━━━━", "",
             f"📋 کل فرم‌ها: {total}", f"🟢 فعال: {active}",
             f"📊 پاسخ کامل: {resp}", f"📝 نیمه‌کاره: {draft}",
             f"💰 مجموع پرداختی: {fmt_amount(paid)} {CURRENCY_LABEL}", ""]

    by_type = db_execute("""SELECT form_type, COUNT(*) n FROM forms
        GROUP BY form_type ORDER BY n DESC""", fetch="all") or []
    if by_type:
        lines.append("🏷️ به تفکیک نوع:")
        for r in by_type:
            t = FORM_TYPES.get(r["form_type"] or "", {})
            pct = (r["n"] * 100 / total) if total else 0
            lines.append(f"├── {t.get('icon','📄')} {t.get('name', r['form_type'])}: "
                         f"{r['n']} ({pct:.1f}%)")
        lines.append("")

    top = db_execute("""SELECT f.title, f.responses_count n FROM forms f
        WHERE f.responses_count>0 ORDER BY f.responses_count DESC LIMIT 5""",
        fetch="all") or []
    if top:
        lines.append("🏆 پربازخوردترین فرم‌ها:")
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, r in enumerate(top):
            lines.append(f"{medals[i] if i < len(medals) else '•'} {r['title'][:30]} — {r['n']}")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "📋 فرم‌های من", "callback_data": "fb_list"}],
        [{"text": "🔙 پنل فرم‌ساز", "callback_data": "fb_panel"}]]})


# ==================== برچسب‌های عمومی ====================
def show_global_tags(cid, uid):
    if not _guard(cid, uid):
        return
    rows = db_execute("SELECT * FROM form_tags WHERE form_id IS NULL ORDER BY id",
                      fetch="all") or []
    lines = ["🏷️ برچسب‌های عمومی پاسخ", "━━━━━━━━━━━━━━", "",
             "برای دسته‌بندی پاسخ‌های دریافتی استفاده می‌شوند.", ""]
    btns = []
    if rows:
        for r in rows:
            lines.append(f"{r.get('color') or '⚪'} {r['name']}")
            btns.append([{"text": f"🗑️ {r['name']}", "callback_data": f"fbtagdel_{r['id']}"}])
    else:
        lines.append("📭 برچسبی تعریف نشده")
    btns.append([{"text": "➕ افزودن برچسب", "callback_data": "fb_tagadd"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "fb_settings"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_add_tag(cid, uid, fid=None):
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_FB_EDIT, {"key": "add_tag", "fid": fid}, merge=False)
    send(cid, (
        "🏷️ افزودن برچسب\n━━━━━━━━━━━━━━\n\n"
        "نام برچسب را بنویسید:\n\n"
        "مثال: تأییدشده\n"
        "💡 می‌توانید اول اموجی بگذارید: ✅ تأییدشده"
    ), kb_cancel())


def handle_add_tag(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    data = get_state_data(uid)
    fid = data.get("fid")
    clear_state(uid)

    if text in (BTN_BACK, "🔙 بازگشت") or not text:
        send(cid, "❌ لغو شد", kb_remove())
        return show_global_tags(cid, uid) if not fid else show_form_tags(cid, uid, fid)

    color = "⚪"
    name = text[:40]
    if text and not text[0].isalnum() and len(text) > 2:
        parts = text.split(None, 1)
        if len(parts) == 2:
            color, name = parts[0][:4], parts[1][:40]

    db_execute("INSERT INTO form_tags (form_id, name, color, created_by) VALUES (?,?,?,?)",
               (fid, name, color, uid))
    send(cid, f"✅ برچسب «{color} {name}» اضافه شد", kb_remove())
    return show_global_tags(cid, uid) if not fid else show_form_tags(cid, uid, fid)


def delete_tag(cid, uid, tag_id):
    if not _guard(cid, uid):
        return
    row = db_execute("SELECT * FROM form_tags WHERE id=?", (int(tag_id),), fetch="one")
    db_execute("DELETE FROM form_tags WHERE id=?", (int(tag_id),))
    send(cid, "🗑️ حذف شد")
    if row and row.get("form_id"):
        return show_form_tags(cid, uid, row["form_id"])
    return show_global_tags(cid, uid)


def show_form_tags(cid, uid, fid):
    form = get_form(fid)
    if not form or not form_can_manage(uid, form):
        return send(cid, "❌ دسترسی ندارید")
    rows = db_execute("SELECT * FROM form_tags WHERE form_id=? OR form_id IS NULL "
                      "ORDER BY form_id IS NULL DESC, id", (fid,), fetch="all") or []
    lines = [f"🏷️ برچسب‌های فرم «{form['title'][:30]}»", "━━━━━━━━━━━━━━", ""]
    btns = []
    for r in rows:
        scope = "🌐" if not r.get("form_id") else "📌"
        lines.append(f"{scope} {r.get('color') or '⚪'} {r['name']}")
        if r.get("form_id"):
            btns.append([{"text": f"🗑️ {r['name']}", "callback_data": f"fbtagdel_{r['id']}"}])
    if not rows:
        lines.append("📭 برچسبی نیست")
    btns.append([{"text": "➕ افزودن برچسب این فرم", "callback_data": f"fbtagaddf_{fid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"fbmore_{fid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def get_tags_for(fid):
    return db_execute("SELECT * FROM form_tags WHERE form_id=? OR form_id IS NULL "
                      "ORDER BY form_id IS NULL DESC, id", (int(fid),), fetch="all") or []
