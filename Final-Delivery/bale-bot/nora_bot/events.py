"""
رویدادها — هسته اصلی ربات نورا (فاز ۵)

طبق معماری توافق‌شده:
  رویداد ← ثبت‌نام ← پرداخت ← بلیت ← حضور و غیاب ← گواهینامه ← گزارش

۸ نوع رویداد، همه قابلیت‌ها سفارشی و دست ادمین.
"""
from privacy import user_error_message
import json
import random
import string
import time
from datetime import datetime
from pathlib import Path

from config import (
    SUPER_ADMIN_ID, EVENTS_DIR, EVENTS_PER_PAGE,
    PAYMENT_PROVIDER_TOKEN, PAYMENT_ENABLED, PAYMENT_TEST_MODE,
    CURRENCY_LABEL, check_amount,
)
from database import db_execute, db_scalar, db_transaction, get_setting, log
import points_ledger as pl
from auth import (
    get_user, get_user_by_id, set_state, get_state_name, get_state_data,
    update_state_data, clear_state, log_action, normalize_digits,
    validate_birth_date, is_admin as _is_admin,
)
from bale_api import (
    send, send_or_edit, forget_menu, send_photo, send_invoice,
    answer_pre_checkout_query, inquire_transaction,
    kb_cancel, kb_remove, kb_skip, kb_location,
    get_file_info, download_file, BTN_BACK, BTN_SKIP,
)

STATE_EV_CREATE = "ev_create"
# ⚠️ سه state زیر بلااستفاده بودند و حذف شدند تا کد تمیز بماند:
#    STATE_EV_EDIT / STATE_EV_REG / STATE_EV_NOTIFY
#    (ویرایش رویداد از همان STATE_EV_CREATE استفاده می‌کند،
#     ثبت‌نام و اطلاع‌رسانی با دکمه انجام می‌شوند نه state)
STATE_EV_ADV = "ev_adv"
STATE_EV_PWD = "ev_pwd"
STATE_EV_DISC = "ev_disc"
STATE_EV_APPLY_DISC = "ev_apply_disc"
STATE_EV_NUM = "ev_num_edit"   # 🆕 فاز ۱۵ — ویرایش سریع عدد از صفحه مرور
STATE_EV_QUICK = "ev_quick_form"  # 🆕 فاز ۱۶ — انتخاب فیلدهای فرم سریع


# ==================== انواع رویداد ====================
EVENT_TYPES = {
    "meeting":   {"icon": "📅", "name": "جلسه هفتگی/دوره‌ای", "attendance": 1, "cert": 0},
    "workshop":  {"icon": "🎓", "name": "کارگاه آموزشی",       "attendance": 1, "cert": 1},
    "webinar":   {"icon": "📹", "name": "وبینار",              "attendance": 1, "cert": 1},
    "cultural":  {"icon": "🎭", "name": "برنامه فرهنگی/هنری",  "attendance": 0, "cert": 0},
    "conference":{"icon": "🎪", "name": "همایش/جشن",           "attendance": 1, "cert": 1},
    "trip":      {"icon": "🏃", "name": "اردو/گردش",           "attendance": 1, "cert": 0},
    "expert":    {"icon": "💼", "name": "رویداد تخصصی",         "attendance": 1, "cert": 1},
    "custom":    {"icon": "⚙️", "name": "سفارشی",              "attendance": 0, "cert": 0},
}

LOCATION_TYPES = {
    "online":   {"icon": "💻", "name": "آنلاین"},
    "physical": {"icon": "🏢", "name": "حضوری"},
    "hybrid":   {"icon": "🎭", "name": "ترکیبی (حضوری + آنلاین)"},
}

PRIVACY_TYPES = {
    "public":  {"icon": "🌍", "name": "عمومی — همه می‌بینند"},
    "code":    {"icon": "🔑", "name": "با کد دعوت"},
    "vip":     {"icon": "⭐", "name": "فقط اعضای VIP"},
    "hidden":  {"icon": "🔒", "name": "مخفی — فقط با لینک مستقیم"},
}

STATUS_LABELS = {
    "draft":     "📝 پیش‌نویس",
    "published": "🟢 منتشر شده",
    "closed":    "🔴 ثبت‌نام بسته",
    "finished":  "✅ برگزار شده",
    "cancelled": "❌ لغو شده",
}

REG_STATUS = {
    "pending":   "⏳ در انتظار پرداخت",
    "confirmed": "✅ تأیید شده",
    "cancelled": "❌ لغو شده",
    "waitlist":  "📋 لیست انتظار",
    "attended":  "🎯 حاضر",
    "absent":    "🚫 غایب",
}


# ==================== جداول ====================
EVENTS_SCHEMA = {
    "title": "TEXT",
    "description": "TEXT",
    "event_type": "TEXT DEFAULT 'meeting'",
    "poster": "TEXT",
    "location_type": "TEXT DEFAULT 'online'",
    "location_address": "TEXT",
    "location_lat": "REAL",
    "location_lon": "REAL",
    "online_link": "TEXT",
    "start_date": "TEXT",
    "start_time": "TEXT",
    "end_date": "TEXT",
    "end_time": "TEXT",
    "duration_minutes": "INTEGER",
    "is_recurring": "INTEGER DEFAULT 0",
    "recurrence": "TEXT",
    "sessions_count": "INTEGER DEFAULT 1",
    # ⏰ فاز ۳۳ — ساخت خودکار جلسات
    "session_repeat": "TEXT DEFAULT 'weekly'",   # daily|weekly|biweekly|custom
    "session_gap_days": "INTEGER DEFAULT 7",
    "start_time": "TEXT",                        # ساعت شروع جلسات
    "att_method": "TEXT",                        # روش پیش‌فرض حضور
    "capacity": "INTEGER DEFAULT 0",
    "reg_start": "TEXT",
    "reg_end": "TEXT",
    "allow_waitlist": "INTEGER DEFAULT 1",
    "is_paid": "INTEGER DEFAULT 0",
    "price": "INTEGER DEFAULT 0",
    "price_vip": "INTEGER DEFAULT 0",
    "payment_method": "TEXT DEFAULT 'bale_wallet'",
    # 🆕 فاز ۱۳: وقتی payment_method='multi' باشد،
    #   روش‌های مجاز اینجا با کاما ذخیره می‌شوند
    "payment_methods": "TEXT",
    "payment_card_id": "INTEGER",
    "payment_gateway_id": "INTEGER",
    "payment_verification": "TEXT DEFAULT 'auto'",
    "discount_code": "TEXT",
    "discount_percent": "INTEGER DEFAULT 0",
    "privacy": "TEXT DEFAULT 'public'",
    "invite_code": "TEXT",
    "has_attendance": "INTEGER DEFAULT 0",
    "has_certificate": "INTEGER DEFAULT 0",
    "has_ticket": "INTEGER DEFAULT 1",
    "has_survey": "INTEGER DEFAULT 0",
    "require_profile": "INTEGER DEFAULT 1",
    "require_approval": "INTEGER DEFAULT 0",
    "points_reward": "INTEGER DEFAULT 0",
    "organizer": "TEXT",
    "contact_info": "TEXT",
    "notes": "TEXT",
    "status": "TEXT DEFAULT 'draft'",
    "created_by": "INTEGER",
    "published_at": "TIMESTAMP",

    # ═══════════ فاز ۱۱: تکمیل طبق فایل معماری ═══════════
    # 🎯 دعوت اجباری
    "require_invites": "INTEGER DEFAULT 0",
    "invites_needed": "INTEGER DEFAULT 0",
    "invite_message": "TEXT",

    # 🔐 حریم خصوصی پیشرفته
    "password_hash": "TEXT",
    "show_in_list": "INTEGER DEFAULT 1",
    "show_in_search": "INTEGER DEFAULT 1",
    "show_participant_count": "INTEGER DEFAULT 1",
    "show_participant_list": "INTEGER DEFAULT 0",
    "show_price_publicly": "INTEGER DEFAULT 1",
    # 🆕 فاز ۱۷-ج: هیچ اشاره‌ای به هزینه نشود (حتی «هزینه دارد»)
    "hide_cost_hint": "INTEGER DEFAULT 0",
    "unauthorized_message": "TEXT",
    "allow_sharing": "INTEGER DEFAULT 1",

    # 🔗 لینک اختصاصی
    "link_type": "TEXT DEFAULT 'permanent'",
    "link_expires_at": "TEXT",
    "link_max_uses": "INTEGER DEFAULT 0",
    "link_current_uses": "INTEGER DEFAULT 0",

    # 🚻 محدودیت‌های ثبت‌نام
    "restrict_gender": "TEXT DEFAULT 'all'",
    "restrict_age_min": "INTEGER DEFAULT 0",
    "restrict_age_max": "INTEGER DEFAULT 0",
    "restrict_city": "TEXT",
    "restrict_tags": "TEXT",
    "min_points_required": "INTEGER DEFAULT 0",

    # 🌐 آنلاین پیشرفته
    "online_platform": "TEXT",
    "online_password": "TEXT",
    "online_link_send_time": "TEXT DEFAULT 'immediate'",
    "online_instructions": "TEXT",

    # 🏢 محل برگزاری
    "venue_name": "TEXT",
    "venue_access_info": "TEXT",
    "venue_has_parking": "INTEGER DEFAULT 0",

    # 📋 محتوای تکمیلی (JSON)
    # 🆕 فاز ۱۵ — اسپانسر، گالری، محتوای آموزشی، اردو
    "sponsors": "TEXT",
    "gallery": "TEXT",
    "materials": "TEXT",
    "trip_plan": "TEXT",
    "emergency_contacts": "TEXT",
    "speakers": "TEXT",
    "agenda": "TEXT",
    "faq": "TEXT",
    "prerequisites": "TEXT",
    "required_items": "TEXT",
    "tags": "TEXT",
    "subtitle": "TEXT",

    # 💬 گروه گفتگو
    "chat_group_url": "TEXT",
    "chat_group_after": "TEXT DEFAULT 'keep'",

    # 🔔 یادآوری خودکار (طبق خط ۳۹۷۸۳ فایل معماری)
    "reminder_enabled": "INTEGER DEFAULT 1",
    "reminder_times": "TEXT",
    "reminder_sent": "TEXT",
    "rem_3d": "INTEGER DEFAULT 0",
    "rem_1d": "INTEGER DEFAULT 1",
    "rem_2h": "INTEGER DEFAULT 1",
    "rem_30m": "INTEGER DEFAULT 0",
    "rem_start": "INTEGER DEFAULT 0",
    "rem_welcome": "INTEGER DEFAULT 1",
    "rem_thanks": "INTEGER DEFAULT 1",
    "rem_message": "TEXT",

    # 📊 نظرسنجی پس از رویداد (طبق خط ۵۱۰۲۲)
    "survey_enabled": "INTEGER DEFAULT 0",
    "survey_form_id": "INTEGER",
    "survey_send_time": "TEXT DEFAULT '2h_after'",
    "survey_reminder": "INTEGER DEFAULT 0",
    "survey_points": "INTEGER DEFAULT 0",
    "survey_anonymous": "INTEGER DEFAULT 0",
    "survey_sent": "INTEGER DEFAULT 0",
    # 📊 فاز ۳۳ — چه کسی نظرسنجی بگیرد
    "survey_audience": "TEXT DEFAULT 'attended'",
    # 🔍 فاز ۳۴ — استعلام و اعتبار گواهینامه
    "cert_doc_no": "TEXT",                    # شمارهٔ نامهٔ رویداد
    "cert_valid_months": "INTEGER",           # اعتبار (ماه) — خالی = پیش‌فرض

    # 🎯 دعوت اجباری — تنظیمات پیشرفته
    "invite_strict": "INTEGER DEFAULT 1",
    "invite_recent_days": "INTEGER DEFAULT 0",
    "invite_exempt_vip": "INTEGER DEFAULT 0",
    "invite_reward": "INTEGER DEFAULT 0",

    # 🎫 بلیت و گواهینامه
    "ticket_template": "TEXT",
    "cert_condition": "TEXT DEFAULT 'attended'",
    "cert_min_sessions": "INTEGER DEFAULT 0",

    # 💸 بازپرداخت
    "refund_enabled": "INTEGER DEFAULT 0",
    "refund_until": "TEXT",
    "refund_percent": "INTEGER DEFAULT 100",

    # 📝 فرم ثبت‌نام سفارشی
    "registration_form_id": "INTEGER",

    # 📊 آمار کش‌شده
    "total_registered": "INTEGER DEFAULT 0",
    "total_attended": "INTEGER DEFAULT 0",
    "total_revenue": "INTEGER DEFAULT 0",
    "rating_sum": "INTEGER DEFAULT 0",
    "rating_count": "INTEGER DEFAULT 0",
    "views_count": "INTEGER DEFAULT 0",

    # ⛔ لغو
    "cancelled_at": "TEXT",
    "cancel_reason": "TEXT",

    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

# 🎫 کدهای دعوت رویداد (طبق event_invite_codes فایل معماری)
EVENT_CODES_SCHEMA = {
    "event_id": "INTEGER NOT NULL",
    "code": "TEXT NOT NULL",
    "code_type": "TEXT DEFAULT 'universal'",
    "assigned_user_id": "INTEGER",
    "assigned_name": "TEXT",
    "assigned_phone": "TEXT",
    "max_uses": "INTEGER DEFAULT 0",
    "current_uses": "INTEGER DEFAULT 0",
    "expires_at": "TEXT",
    "is_active": "INTEGER DEFAULT 1",
    "created_by": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

# 📋 لاگ دسترسی (طبق event_access_logs)
EVENT_ACCESS_LOG_SCHEMA = {
    "event_id": "INTEGER",
    "bale_user_id": "INTEGER",
    "access_type": "TEXT",
    "success": "INTEGER DEFAULT 0",
    "failure_reason": "TEXT",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

# 🎁 کدهای تخفیف رویداد (طبق event_discount_codes فایل معماری)
EVENT_DISCOUNTS_SCHEMA = {
    "event_id": "INTEGER",
    "code": "TEXT NOT NULL",
    "discount_type": "TEXT DEFAULT 'percent'",
    "amount": "INTEGER DEFAULT 0",
    "max_uses": "INTEGER DEFAULT 0",
    "current_uses": "INTEGER DEFAULT 0",
    "per_user_limit": "INTEGER DEFAULT 1",
    "min_amount": "INTEGER DEFAULT 0",
    "expires_at": "TEXT",
    "is_active": "INTEGER DEFAULT 1",
    "revenue_from_code": "INTEGER DEFAULT 0",
    "total_discount": "INTEGER DEFAULT 0",
    "created_by": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

# 📋 لاگ استفاده از کد تخفیف (طبق event_discount_usage)
DISCOUNT_USAGE_SCHEMA = {
    "discount_id": "INTEGER NOT NULL",
    "event_id": "INTEGER",
    "registration_id": "INTEGER",
    "bale_user_id": "INTEGER",
    "original_amount": "INTEGER DEFAULT 0",
    "discount_amount": "INTEGER DEFAULT 0",
    "final_amount": "INTEGER DEFAULT 0",
    "used_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}


# ⭐ امتیازدهی به رویداد
EVENT_RATINGS_SCHEMA = {
    "event_id": "INTEGER NOT NULL",
    "bale_user_id": "INTEGER NOT NULL",
    "rating": "INTEGER DEFAULT 5",
    "comment": "TEXT",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

REGISTRATIONS_SCHEMA = {
    "event_id": "INTEGER",
    "user_id": "INTEGER",
    "bale_user_id": "INTEGER",
    "status": "TEXT DEFAULT 'pending'",
    "ticket_code": "TEXT",
    "answers": "TEXT",
    "amount_paid": "INTEGER DEFAULT 0",
    "transaction_id": "TEXT",
    "payment_payload": "TEXT",
    "paid_at": "TIMESTAMP",
    "attended": "INTEGER DEFAULT 0",
    "attended_at": "TIMESTAMP",
    "certificate_issued": "INTEGER DEFAULT 0",
    "note": "TEXT",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

TRANSACTIONS_SCHEMA = {
    "bale_user_id": "INTEGER",
    "event_id": "INTEGER",
    "registration_id": "INTEGER",
    "payload": "TEXT",
    "amount": "INTEGER",
    "currency": "TEXT DEFAULT 'IRR'",
    "status": "TEXT DEFAULT 'pending'",
    "transaction_id": "TEXT",
    "provider_charge_id": "TEXT",
    "error_message": "TEXT",
    # 🆕 فاز ۱۳ — روش پرداخت و امتیاز مصرف‌شده
    "method": "TEXT",
    "points_used": "INTEGER DEFAULT 0",
    "form_id": "INTEGER",
    # 🆕 فاز ۱۶ — کارمزد درگاه
    "fee_amount": "INTEGER DEFAULT 0",
    "base_amount": "INTEGER DEFAULT 0",
    # 🆕 فاز ۱۸-الف — پرداخت فرم‌ساز
    #   بدون این ستون، پرداخت فرم به هیچ رکوردی وصل نمی‌شد و
    #   بعد از پرداخت، پاسخ کاربر در حالت pending_payment گیر می‌کرد.
    "form_response_id": "INTEGER",
    # 🆕 فاز ۱۸-الف — پرداخت اقساطی / جلسه‌ای
    "plan_id": "INTEGER",           # به کدام طرح پرداخت مربوط است
    "installment_no": "INTEGER DEFAULT 0",   # قسط چندم
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}


def init_event_tables():
    """
    ✅ فیکس بحرانی: حالا از ensure_table استفاده می‌شود
    که ستون‌های گمشده را به جدول‌های موجود اضافه می‌کند.
    قبلاً CREATE TABLE IF NOT EXISTS بود و ستون جدید اضافه نمی‌شد
    ⇒ INSERT شکست می‌خورد ⇒ «دکمه ذخیره کار نمی‌کند»
    """
    from database import ensure_table

    ensure_table("events", EVENTS_SCHEMA)
    ensure_table("event_registrations", REGISTRATIONS_SCHEMA,
                 unique="event_id, bale_user_id")
    ensure_table("event_invite_codes", EVENT_CODES_SCHEMA)
    ensure_table("event_access_logs", EVENT_ACCESS_LOG_SCHEMA)
    ensure_table("event_ratings", EVENT_RATINGS_SCHEMA)
    ensure_table("event_discount_codes", EVENT_DISCOUNTS_SCHEMA)
    ensure_table("event_discount_usage", DISCOUNT_USAGE_SCHEMA)
    for _q in [
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_evdisc ON event_discount_codes(code)",
        "CREATE INDEX IF NOT EXISTS idx_evdisc ON event_discount_codes(event_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_evcode ON event_invite_codes(code)",
        "CREATE INDEX IF NOT EXISTS idx_evcode_ev ON event_invite_codes(event_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_evrate ON event_ratings"
        "(event_id, bale_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_evlog ON event_access_logs(event_id)",
    ]:
        db_execute(_q)
    ensure_table("transactions", TRANSACTIONS_SCHEMA)

    for q in [
        "CREATE INDEX IF NOT EXISTS idx_ev_status ON events(status)",
        "CREATE INDEX IF NOT EXISTS idx_reg_event ON event_registrations(event_id)",
        "CREATE INDEX IF NOT EXISTS idx_reg_user ON event_registrations(bale_user_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_reg ON event_registrations(event_id, bale_user_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_tx_payload ON transactions(payload)",
        "CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions(bale_user_id)",
    ]:
        db_execute(q)

    Path(EVENTS_DIR).mkdir(parents=True, exist_ok=True)


# ==================== کمکی ====================
def show_price(ev, for_admin=False):
    """
    🔴 فاز ۱۵ — آیا مبلغ به این مخاطب نشان داده شود؟

    درخواست صریح کاربر: «نمایش مبلغ خاموش کردم ولی هنوز به کاربر
    نشون میده — کلا هیچ عددی برای پرداخت به کاربر نشون نده تا میره
    برای پرداخت»

    ادمین همیشه می‌بیند؛ کاربر عادی فقط اگر show_price_publicly روشن باشد.
    """
    if for_admin:
        return True
    return bool((ev or {}).get("show_price_publicly", 1))


def _vpn_hint(method="bale_wallet"):
    """
    🛡️ یادآوری کوتاه خاموش کردن فیلترشکن.

    اگر روش پرداخت آفلاین باشد (کارت به کارت / امتیاز) رشته خالی
    برمی‌گرداند — طبق درخواست صریح کاربر.
    """
    try:
        from payments import vpn_warn_inline
        return vpn_warn_inline(method)
    except Exception:
        return ""


def fmt_money(rial):
    """
    💰 نمایش مبلغ — ریال، بدون هیچ تبدیلی (فاز ۱۷-د).

    🔴 تاریخچه باگ:
       قبلاً یک لایه تبدیل تومان↔ریال وسط بود و هر تابعی که
       یادش می‌رفت تبدیل کند یک صفر جابه‌جا می‌کرد. حالا کل
       ربات ریالی است و این تابع فقط عدد را قالب‌بندی می‌کند.

    قانون: ورودی ادمین = دیتابیس = نمایش = درگاه (همه ریال)
    """
    from config import money
    return money(rial, with_unit=False).replace(",", "٬")


def gen_code(prefix="", n=6):
    return prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def get_event(eid):
    return db_execute("SELECT * FROM events WHERE id=?", (eid,), fetch="one")


def event_line(ev, short=False):
    t = EVENT_TYPES.get(ev.get("event_type") or "meeting", EVENT_TYPES["meeting"])
    label = f"{t['icon']} {ev['title']}"
    if short:
        return label[:45]
    when = ev.get("start_date") or "-"
    if ev.get("start_time"):
        when += f" ساعت {ev['start_time']}"
    return f"{label}\n📅 {when}"


def reg_count(eid, status=None):
    if status:
        return db_scalar(
            "SELECT COUNT(*) FROM event_registrations WHERE event_id=? AND status=?",
            (eid, status))
    return db_scalar(
        "SELECT COUNT(*) FROM event_registrations WHERE event_id=? AND status!='cancelled'",
        (eid,))


def is_full(ev):
    cap = int(ev.get("capacity") or 0)
    if cap <= 0:
        return False
    return reg_count(ev["id"], "confirmed") >= cap


def event_full_text(ev, for_admin=False):
    """متن کامل رویداد"""
    t = EVENT_TYPES.get(ev.get("event_type") or "meeting", EVENT_TYPES["meeting"])
    loc = LOCATION_TYPES.get(ev.get("location_type") or "online", LOCATION_TYPES["online"])
    priv = PRIVACY_TYPES.get(ev.get("privacy") or "public", PRIVACY_TYPES["public"])

    lines = [
        f"{t['icon']} {ev['title']}",
        "━━━━━━━━━━━━━━",
        "",
    ]
    if ev.get("description"):
        lines += [ev["description"], ""]

    lines.append(f"🏷️ نوع: {t['name']}")

    when = ev.get("start_date") or "تعیین نشده"
    if ev.get("start_time"):
        when += f" — ساعت {ev['start_time']}"
    lines.append(f"📅 زمان: {when}")

    if ev.get("end_date") and ev["end_date"] != ev.get("start_date"):
        lines.append(f"🏁 پایان: {ev['end_date']}")
    if ev.get("duration_minutes"):
        lines.append(f"⏱️ مدت: {ev['duration_minutes']} دقیقه")
    if ev.get("is_recurring") and ev.get("recurrence"):
        lines.append(f"🔁 تکرار: {ev['recurrence']}")
    if (ev.get("sessions_count") or 1) > 1:
        lines.append(f"📚 تعداد جلسات: {ev['sessions_count']}")

    lines.append(f"{loc['icon']} برگزاری: {loc['name']}")
    if ev.get("location_address"):
        lines.append(f"📍 آدرس: {ev['location_address']}")

    # لینک آنلاین فقط بعد از ثبت‌نام تأییدشده نمایش داده می‌شود
    if for_admin and ev.get("online_link"):
        lines.append(f"🔗 لینک: {ev['online_link']}")

    cap = int(ev.get("capacity") or 0)
    confirmed = reg_count(ev["id"], "confirmed")
    if cap > 0:
        remain = max(0, cap - confirmed)
        lines.append(f"👥 ظرفیت: {confirmed} از {cap} (باقی: {remain})")
    else:
        lines.append(f"👥 ثبت‌نام شده: {confirmed} (ظرفیت نامحدود)")

    if ev.get("is_paid"):
        # 🔴 فاز ۱۵: اگر «نمایش قیمت» خاموش است، هیچ عددی به کاربر
        #    نشان داده نمی‌شود — نه در متن، نه در دکمه، نه در لیست.
        if show_price(ev, for_admin):
            # 🧱 فاز ۲۴ — مبالغ کم = «رایگان + هزینه زیرساخت»
            _lbl = ""
            if not for_admin:
                try:
                    import infra_fee as _inf
                    _lbl, _ = _inf.price_label(ev.get("price"),
                                               with_note=True)
                except Exception as _e:
                    log(f"⚠️ زیرساخت: {_e}")
            if _lbl:
                lines.append(_lbl)
            else:
                lines.append(f"💳 هزینه: {fmt_money(ev.get('price'))} {CURRENCY_LABEL}")
            if ev.get("price_vip"):
                lines.append(f"⭐ هزینه VIP: {fmt_money(ev['price_vip'])} {CURRENCY_LABEL}")
        elif not int(ev.get("hide_cost_hint") or 0):
            # اشاره کلی — بدون هیچ عددی
            lines.append(get_setting("msg_event_paid_hidden", "").strip()
                         or "💳 برای این برنامه هزینه‌ای در نظر گرفته شده.")
        # اگر hide_cost_hint روشن باشد → هیچ کلمه‌ای درباره هزینه نیست
        try:
            from payments import PAYMENT_METHODS as _PM
            pm = _PM.get(ev.get("payment_method") or "bale_wallet")
            if pm:
                lines.append(f"{pm['icon']} روش پرداخت: {pm['name']}")
        except Exception:
            pass
    else:
        lines.append("🆓 رایگان")

    feats = []
    if ev.get("has_ticket"):
        feats.append("🎫 بلیت")
    if ev.get("has_attendance"):
        feats.append("✋ حضور و غیاب")
    if ev.get("has_certificate"):
        feats.append("🎓 گواهینامه")
    if ev.get("has_survey"):
        feats.append("📊 نظرسنجی")
    if ev.get("points_reward"):
        feats.append(f"🏆 {ev['points_reward']} امتیاز")
    if feats:
        lines.append("✨ " + " • ".join(feats))

    # 🎓 فاز ۳۲ — جزئیات گواهینامه‌ها در تبلیغ رویداد
    #    🎯 «چه در تبلیغات رویداد ... همه جزییات ذکر بشه»
    if ev.get("has_certificate"):
        try:
            import eventcert as _evc
            _cl = _evc.ad_lines(ev.get("id"))
            if _cl:
                lines.append("")
                lines += _cl
        except Exception:
            pass

    if ev.get("organizer"):
        lines.append(f"👤 برگزارکننده: {ev['organizer']}")
    if ev.get("contact_info"):
        lines.append(f"📞 تماس: {ev['contact_info']}")

    if for_admin:
        lines += [
            "",
            f"📌 وضعیت: {STATUS_LABELS.get(ev.get('status'), '-')}",
            f"{priv['icon']} دسترسی: {priv['name']}",
        ]
        if ev.get("invite_code"):
            lines.append(f"🔑 کد دعوت: {ev['invite_code']}")
        lines.append(f"🆔 شناسه: {ev['id']}")

    return "\n".join(lines)


# ==================== ساخت رویداد (ویزارد) ====================
CREATE_STEPS = [
    {"key": "title",       "q": "📝 عنوان رویداد را بنویسید:",                     "req": True},
    {"key": "description", "q": "📄 توضیحات رویداد:",                              "req": False},
    {"key": "event_type",  "q": "🏷️ نوع رویداد را انتخاب کنید:", "kind": "choice", "req": True},
    {"key": "location_type", "q": "📍 نحوه برگزاری:",             "kind": "choice", "req": True},
    {"key": "location_address", "q": "🏢 آدرس محل برگزاری:",                       "req": False},
    {"key": "online_link", "q": "🔗 لینک ورود آنلاین:\n\n💡 فقط به شرکت‌کنندگان تأییدشده داده می‌شود.", "req": False},
    {"key": "start_date",  "q": "📅 تاریخ شروع (شمسی):\n\nمثال: 1404/06/15",       "req": True},
    {"key": "start_time",  "q": "🕐 ساعت شروع:\n\nمثال: 18:30",                    "req": False},
    {"key": "duration_minutes", "q": "⏱️ مدت زمان (دقیقه):\n\nمثال: 90",           "req": False},
    {"key": "capacity",    "q": "👥 ظرفیت:\n\n۰ = نامحدود",                        "req": False},
    {"key": "is_paid",     "q": "💳 رویداد پولی است؟",           "kind": "choice", "req": True},
    {"key": "price",       "q": f"💰 مبلغ به {CURRENCY_LABEL}:\n\nمثال: 500000",   "req": False},
    {"key": "payment_method", "q": "💳 نحوه پرداخت:",            "kind": "choice", "req": False},
    {"key": "privacy",     "q": "🔐 سطح دسترسی:",                "kind": "choice", "req": True},
    {"key": "features",    "q": "✨ قابلیت‌ها:",                 "kind": "toggle", "req": False},
    {"key": "points_reward", "q": "🏆 امتیاز شرکت در رویداد:\n\nمثال: 10",         "req": False},
    {"key": "organizer",   "q": "👤 نام برگزارکننده:",                             "req": False},
    {"key": "poster",      "q": "🖼️ پوستر رویداد را ارسال کنید:",  "kind": "photo", "req": False},
]


def start_create(cid, uid):
    if not _is_admin(uid):
        return send(cid, "❌ فقط ادمین می‌تواند رویداد بسازد")
    import permissions as _pm
    if not _pm.require(cid, uid, "ev_create", send):
        return
    set_state(uid, STATE_EV_CREATE, {"step": 0}, merge=False)
    send(cid, (
        "🎉 ساخت رویداد جدید\n"
        "━━━━━━━━━━━━━━\n\n"
        f"📋 {len(CREATE_STEPS)} مرحله\n"
        f"⭐ اجباری: عنوان، نوع، نحوه برگزاری، تاریخ\n"
        f"⏭️ بقیه اختیاری — با «{BTN_SKIP}» رد کنید\n"
        f"🔙 «{BTN_BACK}» = مرحله قبل\n\n"
        "💡 در پایان می‌توانید پیش‌نمایش ببینید و منتشر کنید."
    ), {"inline_keyboard": [
        [{"text": "✅ شروع", "callback_data": "ev_go"}],
        [{"text": "❌ انصراف", "callback_data": "admin_panel"}],
    ]})


def ask_create_step(cid, uid, idx):
    if idx < 0:
        idx = 0
    if idx >= len(CREATE_STEPS):
        return show_create_preview(cid, uid)

    step = CREATE_STEPS[idx]
    # ✅ فیکس: یک بار ذخیره با نام صریح state (نه دو بار)
    data = set_state(uid, STATE_EV_CREATE, {"step": idx}, merge=True)
    key = step["key"]

    # رد کردن هوشمند مراحل بی‌ربط
    if key == "location_address" and data.get("location_type") == "online":
        return ask_create_step(cid, uid, idx + 1)
    if key == "online_link" and data.get("location_type") == "physical":
        return ask_create_step(cid, uid, idx + 1)
    if key == "price" and not int(data.get("is_paid") or 0):
        return ask_create_step(cid, uid, idx + 1)
    if key == "payment_method" and not int(data.get("is_paid") or 0):
        set_state(uid, STATE_EV_CREATE, {"payment_method": "none"}, merge=True)
        return ask_create_step(cid, uid, idx + 1)

    done = int((idx / len(CREATE_STEPS)) * 10)
    bar = "▓" * done + "░" * (10 - done)
    header = f"🎉 مرحله {idx + 1} از {len(CREATE_STEPS)}\n{bar}"
    text = f"{header}\n━━━━━━━━━━━━━━\n\n{step['q']}"

    cur = data.get(key)
    if cur not in (None, "") and step.get("kind") not in ("choice", "toggle"):
        text += f"\n\n♻️ مقدار فعلی: {cur}"

    # کیبورد انتخابی
    if key == "event_type":
        btns = [[{"text": f"{v['icon']} {v['name']}", "callback_data": f"evt_{k}"}]
                for k, v in EVENT_TYPES.items()]
        btns.append([{"text": "🔙 مرحله قبل", "callback_data": "ev_back"},
                     {"text": "❌ انصراف", "callback_data": "ev_cancel"}])
        return send(cid, text, {"inline_keyboard": btns})

    if key == "location_type":
        btns = [[{"text": f"{v['icon']} {v['name']}", "callback_data": f"evl_{k}"}]
                for k, v in LOCATION_TYPES.items()]
        btns.append([{"text": "🔙 مرحله قبل", "callback_data": "ev_back"},
                     {"text": "❌ انصراف", "callback_data": "ev_cancel"}])
        return send(cid, text, {"inline_keyboard": btns})

    if key == "privacy":
        btns = [[{"text": f"{v['icon']} {v['name']}", "callback_data": f"evp_{k}"}]
                for k, v in PRIVACY_TYPES.items()]
        btns.append([{"text": "🔙 مرحله قبل", "callback_data": "ev_back"},
                     {"text": "❌ انصراف", "callback_data": "ev_cancel"}])
        return send(cid, text, {"inline_keyboard": btns})

    if key == "is_paid":
        if not PAYMENT_ENABLED:
            text += "\n\n⚠️ توکن پرداخت تنظیم نشده — فعلاً فقط رایگان ممکن است."
            update_state_data(uid, {"is_paid": 0})
            return ask_create_step(cid, uid, idx + 1)
        return send(cid, text, {"inline_keyboard": [
            [{"text": "🆓 رایگان", "callback_data": "evpay_0"}],
            [{"text": "💳 پولی", "callback_data": "evpay_1"}],
            [{"text": "🔙 مرحله قبل", "callback_data": "ev_back"},
             {"text": "❌ انصراف", "callback_data": "ev_cancel"}],
        ]})

    if key == "payment_method":
        return show_payment_choice(cid, uid, text)

    if key == "features":
        return show_features(cid, uid)

    if key == "poster":
        return send(cid, text, kb_skip())

    send(cid, text, kb_skip() if not step["req"] else kb_cancel())


def show_payment_choice(cid, uid, header_text=""):
    """
    💳 انتخاب نحوه پرداخت — فاز ۱۳

    ۶ گزینه: کارت به کارت / کیف پول بله / درگاه سفارشی /
             پرداخت در محل / پرداخت با امتیاز / چند روشی
    """
    from payments import (get_cards, get_gateways, points_enabled,
                          points_rate_rial)
    from config import PAYMENT_ENABLED as _PE

    d = get_state_data(uid)
    cur = d.get("payment_method")
    cards = get_cards()
    gws = get_gateways()

    lines = [header_text or "💳 نحوه پرداخت:", "", "یکی را انتخاب کنید:", ""]
    btns = []

    def add(key, label, warn=""):
        btns.append([{"text": ("✅ " if cur == key else "") + label
                      + (f" ⚠️ {warn}" if warn else ""),
                      "callback_data": f"paym_{key}"}])

    add("card", f"💳 کارت به کارت ({len(cards)} کارت)" if cards
        else "💳 کارت به کارت", "" if cards else "کارتی ثبت نشده")
    add("bale_wallet", "🏦 درگاه پرداخت بله (کیف پول)",
        "" if _PE else "توکن ندارد")
    add("custom_gateway", f"🔗 درگاه سفارشی ({len(gws)} درگاه)" if gws
        else "🔗 درگاه سفارشی", "" if gws else "تعریف نشده")
    add("onsite", "💰 پرداخت در محل")
    add("points", "🏆 پرداخت با امتیاز",
        "" if points_enabled() else "غیرفعال است")
    add("multi", "🎛️ چند روشی (کاربر انتخاب کند)")

    btns.append([{"text": "🔙 مرحله قبل", "callback_data": "ev_back"},
                 {"text": "❌ انصراف", "callback_data": "ev_cancel"}])

    lines += ["", "💡 راهنما:",
              "• کارت به کارت → تأیید دستی ادمین",
              "• کیف پول بله → تأیید خودکار و آنی",
              "• درگاه سفارشی → زرین‌پال، پی‌پینگ و...",
              "• پرداخت در محل → روز رویداد، نقدی یا کارتخوان",
              "• پرداخت با امتیاز → کسر از امتیاز باشگاه کاربر",
              "• چند روشی → چند گزینه بگذارید، کاربر انتخاب کند"]
    if points_enabled():
        from config import CURRENCY_LABEL as _CL
        rate = fmt_money(points_rate_rial())
        lines.append(f"   (هر امتیاز = {rate} {_CL})")

    return send(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_multi_picker(cid, uid, eid=None):
    """
    🎛️ انتخاب روش‌های مجاز در حالت «چند روشی»

    هم در ویزارد ساخت (eid=None) و هم در ویرایش رویداد کار می‌کند.
    """
    from payments import (PAYMENT_METHODS, MULTI_CHOICES, method_available)
    from database import get_setting as _gs

    if eid:
        ev = get_event(eid)
        if not ev:
            return send(cid, "❌ رویداد یافت نشد")
        raw = ev.get("payment_methods") or ""
        back = f"ev_view_{eid}"
    else:
        d = get_state_data(uid)
        raw = d.get("payment_methods") or \
            _gs("pay_default_methods", "bale_wallet,card")
        back = "ev_paymenu"

    cur = [m.strip() for m in str(raw).split(",") if m.strip()]

    lines = ["🎛️ روش‌های پرداخت مجاز", "━━━━━━━━━━━━━━", "",
             "کاربر بین این روش‌ها انتخاب می‌کند:", ""]
    btns = []
    for m in MULTI_CHOICES:
        info = PAYMENT_METHODS[m]
        on = m in cur
        ok, why = method_available(m)
        mark = "✅" if on else "⬜"
        label = f"{mark} {info['icon']} {info['name']}"
        if not ok:
            label += f" ⚠️ {why}"
        lines.append(label)
        sfx = f"_{eid}" if eid else ""
        btns.append([{"text": label[:45],
                      "callback_data": f"evmm_{m}{sfx}"}])

    if not cur:
        lines += ["", "⚠️ حداقل یک روش را انتخاب کنید"]

    done = f"evmmok_{eid}" if eid else "evmmok"
    btns.append([{"text": "✅ تأیید و ادامه", "callback_data": done}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": back}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_multi_method(cid, uid, method, eid=None):
    """تیک زدن/برداشتن یک روش در حالت چند روشی"""
    from payments import MULTI_CHOICES
    from database import get_setting as _gs
    if method not in MULTI_CHOICES:
        return send(cid, "❌ روش نامعتبر")

    if eid:
        ev = get_event(eid)
        if not ev:
            return send(cid, "❌ رویداد یافت نشد")
        raw = ev.get("payment_methods") or ""
    else:
        d = get_state_data(uid)
        raw = d.get("payment_methods") or \
            _gs("pay_default_methods", "bale_wallet,card")

    cur = [m.strip() for m in str(raw).split(",") if m.strip()]
    if method in cur:
        cur.remove(method)
    else:
        cur.append(method)
    val = ",".join(cur)

    if eid:
        db_execute("UPDATE events SET payment_methods=?, "
                   "updated_at=CURRENT_TIMESTAMP WHERE id=?", (val, eid))
    else:
        update_state_data(uid, {"payment_methods": val})
    return show_multi_picker(cid, uid, eid)


def confirm_multi(cid, uid, eid=None):
    """تأیید انتخاب روش‌های چند روشی"""
    from database import get_setting as _gs
    if eid:
        ev = get_event(eid)
        if not ev:
            return send(cid, "❌ رویداد یافت نشد")
        if not (ev.get("payment_methods") or "").strip():
            return send(cid, "⚠️ حداقل یک روش پرداخت را انتخاب کنید")
        send(cid, "✅ روش‌های پرداخت ذخیره شد")
        return show_event_admin(cid, uid, eid)

    d = get_state_data(uid)
    val = d.get("payment_methods") or \
        _gs("pay_default_methods", "bale_wallet,card")
    if not str(val).strip():
        return send(cid, "⚠️ حداقل یک روش پرداخت را انتخاب کنید")
    update_state_data(uid, {"payment_method": "multi",
                            "payment_methods": val,
                            "payment_verification": "mixed"})
    d = get_state_data(uid)
    return ask_create_step(cid, uid, int(d.get("step") or 0) + 1)


def pick_payment_method(cid, uid, method):
    """انتخاب روش پرداخت در ویزارد"""
    from payments import get_cards, get_gateways

    if method == "card":
        cards = get_cards()
        if not cards:
            return send(cid, (
                "⚠️ هیچ کارت بانکی ثبت نشده\n\n"
                "ابتدا از ⚙️ تنظیمات → 💳 روش‌های پرداخت → کارت‌های بانکی\n"
                "یک کارت ثبت کنید."
            ), {"inline_keyboard": [
                [{"text": "💳 ثبت کارت", "callback_data": "card_add"}],
                [{"text": "🔙 انتخاب دیگر", "callback_data": "ev_paymenu"}]]})
        if len(cards) == 1:
            update_state_data(uid, {"payment_method": "card",
                                    "payment_card_id": cards[0]["id"],
                                    "payment_verification": "manual"})
            d = get_state_data(uid)
            return ask_create_step(cid, uid, int(d.get("step") or 0) + 1)
        # چند کارت → انتخاب
        from payments import mask_card
        btns = [[{"text": f"💳 {mask_card(c['card_number'])} — {c.get('bank_name')}"[:40],
                  "callback_data": f"paycard_{c['id']}"}] for c in cards]
        btns.append([{"text": "🔙 بازگشت", "callback_data": "ev_paymenu"}])
        return send(cid, "💳 کدام کارت؟", {"inline_keyboard": btns})

    if method == "custom_gateway":
        gws = get_gateways()
        if not gws:
            return send(cid, (
                "⚠️ درگاه سفارشی تعریف نشده\n\n"
                "ابتدا از ⚙️ تنظیمات → 💳 روش‌های پرداخت → درگاه‌های سفارشی\n"
                "یک درگاه تعریف کنید."
            ), {"inline_keyboard": [
                [{"text": "🔗 تعریف درگاه", "callback_data": "gw_add"}],
                [{"text": "🔙 انتخاب دیگر", "callback_data": "ev_paymenu"}]]})
        if len(gws) == 1:
            update_state_data(uid, {"payment_method": "custom_gateway",
                                    "payment_gateway_id": gws[0]["id"],
                                    "payment_verification": "auto"})
            d = get_state_data(uid)
            return ask_create_step(cid, uid, int(d.get("step") or 0) + 1)
        btns = [[{"text": f"🔗 {g['gateway_name']}"[:40],
                  "callback_data": f"paygw_{g['id']}"}] for g in gws]
        btns.append([{"text": "🔙 بازگشت", "callback_data": "ev_paymenu"}])
        return send(cid, "🔗 کدام درگاه؟", {"inline_keyboard": btns})

    # ═══════════ 🆕 فاز ۱۳ ═══════════
    if method == "multi":
        return show_multi_picker(cid, uid)

    if method == "onsite":
        update_state_data(uid, {"payment_method": "onsite",
                                "payment_verification": "manual"})
        d = get_state_data(uid)
        return ask_create_step(cid, uid, int(d.get("step") or 0) + 1)

    if method == "points":
        from payments import points_enabled
        if not points_enabled():
            return send(cid, (
                "⚠️ پرداخت با امتیاز غیرفعال است\n\n"
                "ابتدا از ⚙️ تنظیمات → 💳 پرداخت و مالی →\n"
                "🎛️ روش‌های پرداخت پیشرفته آن را فعال کنید."
            ), {"inline_keyboard": [
                [{"text": "🎛️ فعال‌سازی", "callback_data": "pay_adv"}],
                [{"text": "🔙 انتخاب دیگر", "callback_data": "ev_paymenu"}]]})
        update_state_data(uid, {"payment_method": "points",
                                "payment_verification": "auto"})
        d = get_state_data(uid)
        return ask_create_step(cid, uid, int(d.get("step") or 0) + 1)

    if method == "bale_wallet":
        from config import PAYMENT_ENABLED as _PE
        if not _PE:
            return send(cid, (
                "⚠️ توکن کیف پول بله تنظیم نشده\n\n"
                "در فایل .env بگذارید:\n"
                "PAYMENT_PROVIDER_TOKEN=توکن_شما"
            ), {"inline_keyboard": [
                [{"text": "🔙 انتخاب دیگر", "callback_data": "ev_paymenu"}]]})
        update_state_data(uid, {"payment_method": "bale_wallet",
                                "payment_verification": "auto"})
    else:
        update_state_data(uid, {"payment_method": "none",
                                "payment_verification": "auto"})

    d = get_state_data(uid)
    ask_create_step(cid, uid, int(d.get("step") or 0) + 1)


def pick_payment_card(cid, uid, card_id):
    update_state_data(uid, {"payment_method": "card",
                            "payment_card_id": card_id,
                            "payment_verification": "manual"})
    d = get_state_data(uid)
    ask_create_step(cid, uid, int(d.get("step") or 0) + 1)


def pick_payment_gateway(cid, uid, gw_id):
    update_state_data(uid, {"payment_method": "custom_gateway",
                            "payment_gateway_id": gw_id,
                            "payment_verification": "auto"})
    d = get_state_data(uid)
    ask_create_step(cid, uid, int(d.get("step") or 0) + 1)


def show_features(cid, uid):
    """انتخاب قابلیت‌ها با تاگل"""
    d = get_state_data(uid)
    et = EVENT_TYPES.get(d.get("event_type") or "meeting", EVENT_TYPES["meeting"])

    # پیش‌فرض هوشمند بر اساس نوع رویداد
    if "has_attendance" not in d:
        update_state_data(uid, {
            "has_attendance": et["attendance"],
            "has_certificate": et["cert"],
            "has_ticket": 1,
            "has_survey": 0,
            "require_profile": 1,
            "require_approval": 0,
        })
        d = get_state_data(uid)

    def mark(k):
        return "✅" if int(d.get(k) or 0) else "⬜"

    return send_or_edit(cid, (
        "✨ قابلیت‌های رویداد\n"
        "━━━━━━━━━━━━━━\n\n"
        "روی هر مورد بزنید تا فعال/غیرفعال شود:\n\n"
        "💡 همه چیز دست شماست — هر ترکیبی می‌توانید بسازید.\n\n"
        "🎓 اگر رویداد مشترک است و چند گواهینامهٔ مستقل دارد،\n"
        "   بعد از ساخت از «🎓 گواهینامه‌های رویداد» تعریفشان کنید."
    ), {"inline_keyboard": [
        [{"text": f"{mark('has_ticket')} 🎫 صدور بلیت", "callback_data": "evf_has_ticket"}],
        [{"text": f"{mark('has_attendance')} ✋ حضور و غیاب", "callback_data": "evf_has_attendance"}],
        [{"text": f"{mark('has_certificate')} 🎓 گواهینامه", "callback_data": "evf_has_certificate"}],
        [{"text": f"{mark('has_survey')} 📊 نظرسنجی پایانی", "callback_data": "evf_has_survey"}],
        [{"text": f"{mark('require_profile')} 👤 نیاز به پروفایل کامل", "callback_data": "evf_require_profile"}],
        [{"text": f"{mark('require_approval')} ✅ تأیید دستی ادمین", "callback_data": "evf_require_approval"}],
        [{"text": "➡️ ادامه", "callback_data": "evf_done"}],
        [{"text": "🔙 مرحله قبل", "callback_data": "ev_back"},
         {"text": "❌ انصراف", "callback_data": "ev_cancel"}],
    ]})


def wizard_back(cid, uid):
    """برگشت به مرحله قبل از دکمه inline"""
    d = get_state_data(uid)
    idx = int(d.get("step") or 0)
    if idx <= 0:
        return wizard_cancel(cid, uid)
    ask_create_step(cid, uid, idx - 1)


def wizard_cancel(cid, uid):
    """لغو ویزارد و بازگشت به پنل"""
    clear_state(uid)
    send(cid, "❌ ساخت رویداد لغو شد", kb_remove())
    from admin import show_admin_panel
    show_admin_panel(cid, uid)


def handle_create_input(message):
    """پردازش متن/عکس در ویزارد ساخت"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()

    data = get_state_data(uid)
    idx = int(data.get("step") or 0)
    if idx >= len(CREATE_STEPS):
        return show_create_preview(cid, uid)

    step = CREATE_STEPS[idx]
    key = step["key"]

    # عکس پوستر
    if key == "poster" and "photo" in message:
        return save_poster(cid, uid, message, idx)

    if raw == BTN_BACK:
        if idx == 0:
            clear_state(uid)
            send(cid, "❌ ساخت رویداد لغو شد", kb_remove())
            from admin import show_admin_panel
            return show_admin_panel(cid, uid)
        return ask_create_step(cid, uid, idx - 1)

    if raw == BTN_SKIP:
        if step["req"] and not data.get(key):
            return send(cid, "⛔ این فیلد اجباری است")
        return ask_create_step(cid, uid, idx + 1)

    if not raw:
        return send(cid, "⚠️ لطفاً متن وارد کنید")

    text = normalize_digits(raw)
    patch = {}

    if key == "title":
        if len(text) < 3:
            return send(cid, "❌ عنوان باید حداقل ۳ کاراکتر باشد")
        patch[key] = text[:120]

    elif key == "description":
        patch[key] = text[:2000]

    elif key == "start_date":
        norm = validate_birth_date(text)
        if not norm:
            return send(cid, "❌ تاریخ نامعتبر\n\n💡 فرمت درست: 1404/06/15")
        patch[key] = norm

    elif key == "start_time":
        t = text.replace(".", ":").replace("-", ":")
        parts = t.split(":")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            return send(cid, "❌ ساعت نامعتبر\n\n💡 مثال: 18:30")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return send(cid, "❌ ساعت نامعتبر")
        patch[key] = f"{h:02d}:{m:02d}"

    elif key in ("duration_minutes", "capacity", "points_reward"):
        v = text.replace(",", "").replace("٬", "")
        if not v.isdigit():
            return send(cid, "❌ فقط عدد وارد کنید")
        patch[key] = int(v)

    elif key == "price":
        v = text.replace(",", "").replace("٬", "").replace(" ", "")
        if not v.isdigit():
            return send(cid, f"❌ فقط عدد وارد کنید (به {CURRENCY_LABEL})")
        amount = int(v)
        okamt, amsg = check_amount(amount)
        if not okamt:
            return send(cid, f"❌ {amsg}")
        patch[key] = amount
        # هشدار مبلغ بزرگ با توکن واقعی
        if not PAYMENT_TEST_MODE and amount >= 1_000_000:
            send(cid, (
                f"⚠️ توجه: مبلغ {fmt_money(amount)} {CURRENCY_LABEL}\n\n"
                f"🔴 توکن پرداخت واقعی است — مطمئنید؟"
            ))

    elif key == "online_link":
        if not text.startswith("http"):
            return send(cid, "❌ لینک باید با http شروع شود")
        patch[key] = text[:500]

    else:
        patch[key] = text[:500]

    update_state_data(uid, patch)
    ask_create_step(cid, uid, idx + 1)


def save_poster(cid, uid, message, idx):
    photos = message.get("photo") or []
    if not photos:
        return send(cid, "❌ عکس ارسال کنید")
    try:
        best = max(photos, key=lambda p: (p.get("file_size") or 0, p.get("width") or 0))
    except (ValueError, TypeError):
        best = photos[-1]

    send(cid, "⏳ در حال ذخیره پوستر...")
    fi = get_file_info(best.get("file_id"))
    if not fi.get("ok"):
        send(cid, "⚠️ خطا در دریافت — بدون پوستر ادامه می‌دهیم")
        return ask_create_step(cid, uid, idx + 1)

    content = download_file((fi.get("result") or {}).get("file_path"))
    if not content:
        send(cid, "⚠️ خطا در دانلود — بدون پوستر ادامه می‌دهیم")
        return ask_create_step(cid, uid, idx + 1)

    try:
        d = Path(EVENTS_DIR) / datetime.now().strftime("%Y/%m")
        d.mkdir(parents=True, exist_ok=True)
        fp = d / f"poster_{uid}_{int(time.time())}.jpg"
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(content))
            if img.mode != "RGB":
                img = img.convert("RGB")
            resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1)
            img.thumbnail((1280, 1280), resample)
            img.save(fp, "JPEG", quality=88, optimize=True)
        except ImportError:
            fp.write_bytes(content)
        update_state_data(uid, {"poster": str(fp).replace("\\", "/")})
        send(cid, "✅ پوستر ذخیره شد")
    except Exception as e:
        log(f"⚠️ پوستر: {e}")
        send(cid, "⚠️ ذخیره پوستر ناموفق بود")

    ask_create_step(cid, uid, idx + 1)


def show_create_preview(cid, uid):
    d = get_state_data(uid)
    if not d.get("title"):
        clear_state(uid)
        return send(cid, "❌ اطلاعاتی ثبت نشده. دوباره تلاش کنید.")

    fake = dict(d)
    fake["id"] = 0
    body = event_full_text(fake, for_admin=True)

    missing = [k for k in ("title", "event_type", "location_type", "start_date")
               if not d.get(k)]
    if missing:
        return send_or_edit(cid, "⛔ فیلدهای اجباری ناقص:\n" + "، ".join(missing),
                    {"inline_keyboard": [
                        [{"text": "🔄 از اول", "callback_data": "ev_new"}],
                        [{"text": "❌ انصراف", "callback_data": "admin_panel"}]]})

    set_state(uid, STATE_EV_CREATE, {"preview": 1}, merge=True)

    text = "👁️ پیش‌نمایش رویداد\n━━━━━━━━━━━━━━\n\n" + body + "\n\n⚠️ ذخیره شود؟"
    kb = {"inline_keyboard": [
        [{"text": "💾 ذخیره پیش‌نویس", "callback_data": "ev_save_draft"}],
        [{"text": "🚀 ذخیره و انتشار", "callback_data": "ev_save_publish"}],
        [{"text": "✏️ ویرایش از اول", "callback_data": "ev_new"}],
        [{"text": "❌ انصراف", "callback_data": "admin_panel"}],
    ]}

    if d.get("poster") and Path(d["poster"]).exists():
        send_photo(cid, d["poster"], "🖼️ پوستر رویداد")
    send(cid, text, kb)


def save_event(cid, uid, publish=False):
    """
    ✅ فیکس کامل باگ «دکمه ذخیره کار نمی‌کند»:
      • اگر state گم شده باشد، پیام واضح می‌دهد (نه سکوت)
      • خطای دیتابیس گزارش می‌شود
      • تأیید ذخیره با خواندن دوباره از دیتابیس
      • state فقط بعد از موفقیت پاک می‌شود
    """
    d = get_state_data(uid)

    if not d or not d.get("title"):
        # تلاش برای بازیابی از رکورد منقضی
        raw = db_execute("SELECT data FROM user_states WHERE bale_user_id=?",
                         (uid,), fetch="one")
        if raw and raw.get("data"):
            try:
                recovered = json.loads(raw["data"])
                if isinstance(recovered, dict) and recovered.get("title"):
                    d = recovered
                    log(f"♻️ اطلاعات رویداد بازیابی شد برای {uid}")
            except (json.JSONDecodeError, TypeError):
                pass

    if not d or not d.get("title"):
        clear_state(uid)
        return send_or_edit(cid, (
            "❌ اطلاعات رویداد پیدا نشد\n"
            "━━━━━━━━━━━━━━\n\n"
            "احتمالاً زمان زیادی طول کشیده و اطلاعات موقت پاک شده.\n\n"
            "💡 لطفاً دوباره رویداد را بسازید."
        ), {"inline_keyboard": [
            [{"text": "🎉 ساخت دوباره", "callback_data": "ev_new"}],
            [{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}]]})

    missing = [k for k in ("title", "event_type", "location_type", "start_date")
               if not d.get(k)]
    if missing:
        names = {"title": "عنوان", "event_type": "نوع",
                 "location_type": "نحوه برگزاری", "start_date": "تاریخ"}
        return send_or_edit(cid, (
            "⛔ این فیلدهای اجباری خالی هستند:\n"
            + "، ".join(names.get(m, m) for m in missing)
        ), {"inline_keyboard": [
            [{"text": "🔄 ساخت دوباره", "callback_data": "ev_new"}],
            [{"text": "❌ انصراف", "callback_data": "admin_panel"}]]})

    cols = {
        "title": d.get("title"),
        "description": d.get("description"),
        "event_type": d.get("event_type") or "meeting",
        "poster": d.get("poster"),
        "location_type": d.get("location_type") or "online",
        "location_address": d.get("location_address"),
        "online_link": d.get("online_link"),
        "start_date": d.get("start_date"),
        "start_time": d.get("start_time"),
        "duration_minutes": d.get("duration_minutes") or 0,
        "capacity": d.get("capacity") or 0,
        "is_paid": int(d.get("is_paid") or 0),
        "price": int(d.get("price") or 0),
        "payment_method": d.get("payment_method") or
                          ("bale_wallet" if int(d.get("is_paid") or 0) else "none"),
        "payment_methods": d.get("payment_methods"),
        "payment_card_id": d.get("payment_card_id"),
        "payment_gateway_id": d.get("payment_gateway_id"),
        "payment_verification": d.get("payment_verification") or "auto",
        "privacy": d.get("privacy") or "public",
        "has_attendance": int(d.get("has_attendance") or 0),
        "has_certificate": int(d.get("has_certificate") or 0),
        "has_ticket": int(d.get("has_ticket") or 1),
        "has_survey": int(d.get("has_survey") or 0),
        "require_profile": int(d.get("require_profile") or 1),
        "require_approval": int(d.get("require_approval") or 0),
        "points_reward": int(d.get("points_reward") or 0),
        "organizer": d.get("organizer"),
        "status": "published" if publish else "draft",
        "created_by": uid,
    }
    if cols["privacy"] == "code":
        cols["invite_code"] = gen_code("EV")
    if publish:
        cols["published_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    keys = list(cols.keys())
    ph = ", ".join("?" * len(keys))
    eid = db_execute(
        f"INSERT INTO events ({', '.join(keys)}) VALUES ({ph})",
        [cols[k] for k in keys])

    # ✅ تأیید واقعی ذخیره — نه فقط اعتماد به lastrowid
    saved = get_event(eid) if eid else None
    if not saved:
        log(f"❌ ذخیره رویداد ناموفق برای {uid}: eid={eid}")
        return send_or_edit(cid, (
            "❌ ذخیره در دیتابیس ناموفق بود\n"
            "━━━━━━━━━━━━━━\n\n"
            "اطلاعات شما هنوز محفوظ است.\n"
            "💡 دوباره روی دکمه ذخیره بزنید."
        ), {"inline_keyboard": [
            [{"text": "🔄 تلاش دوباره", "callback_data":
              "ev_save_publish" if publish else "ev_save_draft"}],
            [{"text": "❌ انصراف", "callback_data": "admin_panel"}]]})

    # فقط بعد از موفقیت قطعی
    clear_state(uid)
    forget_menu(cid)
    log(f"✅ رویداد #{eid} «{saved['title']}» ذخیره شد (publish={publish})")
    log_action(uid, "event_created", {"event_id": eid, "published": publish})

    # ⏰ فاز ۳۳ — جلسات حضور و غیاب خودکار ساخته شوند
    #    🎯 «باید یه دور دیگه جلسه تعیین کنم تا کار کنه — اتوماتیک کن»
    _made = 0
    if saved.get("has_attendance"):
        try:
            import attendance_auto as _aa
            _made = _aa.sync_on_enable(eid, uid)
        except Exception as _e:
            log(f"⚠️ ساخت خودکار جلسات: {_e}")

    t = EVENT_TYPES.get(saved.get("event_type") or "meeting", EVENT_TYPES["meeting"])
    msg = [
        "✅ رویداد با موفقیت ذخیره شد!",
        "━━━━━━━━━━━━━━",
        "",
        f"{t['icon']} {saved['title']}",
        f"🆔 شناسه: {eid}",
        f"📌 وضعیت: {STATUS_LABELS['published' if publish else 'draft']}",
        f"📅 {saved.get('start_date') or '-'}"
        + (f" ساعت {saved['start_time']}" if saved.get("start_time") else ""),
    ]
    if saved.get("is_paid"):
        msg.append(f"💳 {fmt_money(saved.get('price'))} {CURRENCY_LABEL}")
    else:
        msg.append("🆓 رایگان")
    if cols.get("invite_code"):
        msg += ["", f"🔑 کد دعوت: {cols['invite_code']}",
                "💡 این کد را به افراد مورد نظر بدهید."]
    if _made:
        msg += ["", f"⏰ {_made} جلسهٔ حضور و غیاب خودکار ساخته شد",
                "   💡 از «✋ حضور و غیاب» قابل ویرایش است."]
    if publish:
        msg += ["", "📢 حالا می‌توانید به کاربران اطلاع‌رسانی کنید."]

    msg += ["", "👇 حالا یک قدم مانده — روش ثبت‌نام را انتخاب کنید:"]
    send_or_edit(cid, "\n".join(msg), {"inline_keyboard": [
        [{"text": "📝 روش ثبت‌نام و تنظیمات",
          "callback_data": f"evwiz_{eid}"}],
        [{"text": "👁️ مشاهده رویداد", "callback_data": f"ev_view_{eid}"}],
        [{"text": "📋 رویدادهای من", "callback_data": "ev_list"}],
    ]})


# ══════════════════════════════════════════════════════════
# 🧭 فاز ۱۵ — دستیار بعد از ساخت رویداد
#
# درخواست کاربر:
#   «باید ربات بعد از پیش نویس رویداد به کاربر بگه انتخاب کن فرم
#    بسازه یا پروفایل تکمیل کنه یا از فرم های قبل استفاده کنه»
#   «وقتی پیش نویس به انتها میرسه یه دور تنظیمات پیشرفته رویداد رو
#    مرور کنه ... همون دم دستش تغییرات اعمال کنه نه ۶۰ دور بچرخه»
# ══════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════
# 📝 فرم ثبت‌نام رویداد — طبق فایل معماری (خط ۵۰۷۵۰)
#
#   ⚡ فرم سریع همینجا      فقط فیلدهای اساسی، بدون خروج از رویداد
#   📋 استفاده از فرم موجود  از فرم‌های ساخته‌شده
#   🎨 ساخت فرم پیشرفته     رفتن به فرم‌ساز و برگشت خودکار
#   🎁 بدون فرم             فقط کلیک «ثبت‌نام» — اطلاعات از پروفایل
# ══════════════════════════════════════════════════════════
REG_MODES = {
    "quick": {
        "icon": "⚡", "name": "فرم سریع همینجا",
        "desc": "فقط فیلدهای اساسی — بدون خروج از این صفحه",
    },
    "existing": {
        "icon": "📋", "name": "استفاده از فرم موجود",
        "desc": "یکی از فرم‌هایی که قبلاً ساخته‌اید",
    },
    "advanced": {
        "icon": "🎨", "name": "ساخت فرم پیشرفته",
        "desc": "فرم‌ساز کامل — بعد از ساخت برمی‌گردید همینجا",
    },
    "none": {
        "icon": "🎁", "name": "بدون فرم",
        "desc": "کاربر فقط «ثبت‌نام» می‌زند، اطلاعات از پروفایل",
    },
}

# ⚡ فیلدهای «فرم سریع» — طبق فایل معماری
#    (کلید، برچسب، پیش‌فرض تیک‌خورده، اجباری)
QUICK_FIELDS = [
    ("full_name",      "نام و نام خانوادگی", 1, 1),
    ("mobile",         "شماره موبایل",       1, 1),
    ("email",          "ایمیل",              0, 0),
    ("national_id",    "کد ملی",             0, 0),
    ("age",            "سن",                 0, 0),
    ("gender",         "جنسیت",              0, 0),
    ("province_city",  "شهر",                0, 0),
    ("short_text",     "معرف / آشنایی با رویداد", 0, 0),
]


def _quick_defaults():
    return [k for k, _, on, _r in QUICK_FIELDS if on]


def _quick_selected(uid, eid):
    """فیلدهای انتخاب‌شده فرم سریع (در state نگه داشته می‌شود)"""
    d = get_state_data(uid) or {}
    key = f"qf_{eid}"
    if key in d:
        return [x for x in (d.get(key) or "").split(",") if x]
    return _quick_defaults()


def show_reg_wizard(cid, uid, eid):
    """📝 مرحله فرم ثبت‌نام — ۴ گزینه معماری"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    cur_fid = ev.get("registration_form_id")
    cur_form = None
    if cur_fid:
        cur_form = db_execute(
            "SELECT id, title, "
            "(SELECT COUNT(*) FROM form_fields WHERE form_id=forms.id) nf "
            "FROM forms WHERE id=?", (cur_fid,), fetch="one")

    lines = [
        "📝 فرم ثبت‌نام رویداد",
        f"🎉 {ev.get('title')}",
        "━━━━━━━━━━━━━━", "",
    ]
    if cur_form:
        lines += [f"✅ فرم فعلی: {cur_form['title']}",
                  f"   📋 {cur_form['nf']} سوال", ""]
    else:
        lines += ["📌 در حال حاضر: 🎁 بدون فرم "
                  "(اطلاعات از پروفایل کاربر)", ""]

    lines.append("🎯 چطور فرم ثبت‌نام را تنظیم کنیم؟")
    lines.append("")

    btns = []
    for k, m in REG_MODES.items():
        mark = ""
        if k == "none" and not cur_fid:
            mark = "✅ "
        elif k == "existing" and cur_fid:
            mark = "✅ "
        lines += [f"{mark}{m['icon']} {m['name']}", f"   {m['desc']}", ""]
        btns.append([{"text": f"{mark}{m['icon']} {m['name']}",
                      "callback_data": f"evrm_{k}_{eid}"}])

    if cur_form:
        btns.append([{"text": "✏️ ویرایش فرم فعلی",
                      "callback_data": f"fbv_{cur_form['id']}"}])
        btns.append([{"text": "🗑️ حذف اتصال فرم",
                      "callback_data": f"evrm_none_{eid}"}])
    btns.append([{"text": "⏭️ بعداً — برو به مرور تنظیمات",
                  "callback_data": f"evrev_{eid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def pick_reg_mode(cid, uid, mode, eid):
    """انتخاب روش فرم ثبت‌نام"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    if mode == "none":
        old = ev.get("registration_form_id")
        # ⚠️ require_profile دست نمی‌خورد — انتخاب ادمین محترم است
        db_execute("UPDATE events SET registration_form_id=NULL, "
                   "updated_at=CURRENT_TIMESTAMP WHERE id=?", (eid,))
        if old:
            db_execute("UPDATE forms SET event_id=NULL WHERE id=?", (old,))
        send(cid, "🎁 بدون فرم — کاربر فقط «ثبت‌نام» می‌زند\n"
                  "اطلاعات از پروفایلش گرفته می‌شود.")
        return show_review(cid, uid, eid)

    if mode == "quick":
        return show_quick_form(cid, uid, eid)
    if mode == "existing":
        return pick_existing_form(cid, uid, eid)
    if mode == "advanced":
        return create_reg_form(cid, uid, eid, advanced=True)
    return send(cid, "❌ گزینه نامعتبر")


# ==================== ⚡ فرم سریع ====================
def show_quick_form(cid, uid, eid):
    """⚡ انتخاب فیلدهای فرم سریع — بدون خروج از رویداد"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    sel = _quick_selected(uid, eid)
    lines = [
        "⚡ فرم سریع", "━━━━━━━━━━━━━━", "",
        "کدام اطلاعات را از کاربر بپرسیم؟", "",
    ]
    btns = []
    for key, label, _d, req in QUICK_FIELDS:
        on = key in sel
        star = " ⭐" if req else ""
        lines.append(f"{'☑️' if on else '⬜'} {label}{star}")
        btns.append([{"text": f"{'☑️' if on else '⬜'} {label}{star}",
                      "callback_data": f"evqf_{key}_{eid}"}])

    lines += ["", f"📋 {len(sel)} سوال انتخاب شده",
              "⭐ = اجباری", "",
              "💡 بعداً می‌توانید سوال دلخواه هم اضافه کنید."]

    btns.append([{"text": f"✅ ساخت فرم ({len(sel)} سوال)",
                  "callback_data": f"evqok_{eid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"evwiz_{eid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_quick_field(cid, uid, key, eid):
    """تیک زدن/برداشتن یک فیلد فرم سریع"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    valid = {k for k, _, _, _ in QUICK_FIELDS}
    if key not in valid:
        return send(cid, "❌ فیلد نامعتبر")

    sel = _quick_selected(uid, eid)
    req = {k for k, _, _, r in QUICK_FIELDS if r}
    if key in sel:
        if key in req:
            send(cid, "⚠️ این فیلد اجباری است و حذف نمی‌شود")
            return show_quick_form(cid, uid, eid)
        sel.remove(key)
    else:
        sel.append(key)

    set_state(uid, STATE_EV_QUICK, {f"qf_{eid}": ",".join(sel)}, merge=True)
    return show_quick_form(cid, uid, eid)


def build_quick_form(cid, uid, eid):
    """✅ ساخت واقعی فرم سریع از فیلدهای انتخاب‌شده"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    sel = _quick_selected(uid, eid)
    if not sel:
        return send(cid, "⚠️ حداقل یک سوال انتخاب کنید")

    try:
        import forms as fb
        from form_fields import FIELD_TYPES, REQUIRED_BY_DEFAULT

        slug = fb.gen_slug()
        while db_execute("SELECT id FROM forms WHERE slug=?", (slug,),
                         fetch="one"):
            slug = fb.gen_slug()

        title = f"ثبت‌نام {str(ev.get('title'))[:40]}"
        fid = db_execute("""INSERT INTO forms
            (owner_id, form_type, title, slug, status, one_per_user,
             end_text, payment_method, event_id, display_mode)
            VALUES (?,'registration',?,?,'active',1,?,'none',?,'one_by_one')""",
            (uid, title, slug,
             get_setting("form_txt_end_default", "💚 سپاس از شما"), eid))
        if not fid:
            return send(cid, "❌ خطا در ساخت فرم")

        req_keys = {k for k, _, _, r in QUICK_FIELDS if r}
        order = 0
        for key in sel:
            m = FIELD_TYPES.get(key)
            if not m:
                continue
            order += 1
            opts = m.get("opts")
            db_execute("""INSERT INTO form_fields
                (form_id, field_order, field_type, label, options,
                 is_required, min_val, max_val, max_files)
                VALUES (?,?,?,?,?,?,?,?,1)""",
                (fid, order, key,
                 dict((k2, l) for k2, l, _, _ in QUICK_FIELDS).get(key)
                 or m.get("q", ""),
                 json.dumps(opts, ensure_ascii=False) if opts else None,
                 1 if (key in req_keys or key in REQUIRED_BY_DEFAULT) else 0,
                 m.get("min"), m.get("max")))

        _link_form(eid, fid)
        clear_state(uid)
        log_action(uid, "event_form_linked", {"eid": eid, "fid": fid,
                                              "mode": "quick"})
        send(cid, (f"✅ فرم سریع ساخته شد!\n"
                   f"━━━━━━━━━━━━━━\n\n"
                   f"📋 {title}\n"
                   f"📝 {order} سوال\n"
                   f"🟢 فعال و آماده ثبت‌نام"))
        return show_review(cid, uid, eid)
    except Exception as e:
        log(f"❌ ساخت فرم سریع: {e}")
        return send(cid, "❌ خطا در ساخت فرم")


def _link_form(eid, fid):
    """🔗 اتصال دوطرفه فرم و رویداد"""
    db_execute("UPDATE events SET registration_form_id=?, "
               "updated_at=CURRENT_TIMESTAMP WHERE id=?", (fid, eid))
    db_execute("UPDATE forms SET event_id=? WHERE id=?", (eid, fid))


def pick_existing_form(cid, uid, eid, page=0):
    """📋 انتخاب از فرم‌های قبلی — با تعداد سوال و پاسخ"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    rows = db_execute("""SELECT f.id, f.title, f.form_type, f.status,
        (SELECT COUNT(*) FROM form_fields x WHERE x.form_id=f.id) nf,
        (SELECT COUNT(*) FROM form_responses r WHERE r.form_id=f.id
         AND r.status IN ('completed','confirmed')) nr
        FROM forms f WHERE COALESCE(f.status,'') <> 'deleted'
        ORDER BY f.id DESC LIMIT 30""", fetch="all") or []
    rows = [r for r in rows if r["nf"] > 0]

    if not rows:
        return send_or_edit(cid, (
            "📭 فرم آماده‌ای ندارید\n━━━━━━━━━━━━━━\n\n"
            "می‌توانید «⚡ فرم سریع» بسازید یا به فرم‌ساز بروید."
        ), {"inline_keyboard": [
            [{"text": "⚡ فرم سریع", "callback_data": f"evrm_quick_{eid}"}],
            [{"text": "🎨 فرم‌ساز", "callback_data": f"evrm_advanced_{eid}"}],
            [{"text": "🔙 بازگشت", "callback_data": f"evwiz_{eid}"}]]})

    from forms import FORM_TYPES
    lines = ["📋 فرم‌های شما", "━━━━━━━━━━━━━━", "",
             "کدام فرم برای این رویداد استفاده شود؟", ""]
    btns = []
    for r in rows[:12]:
        t = FORM_TYPES.get(r.get("form_type") or "registration",
                           FORM_TYPES["registration"])
        st = "🟢" if r.get("status") == "active" else "📝"
        lines += [f"{st} {t['icon']} {r['title']}",
                  f"   📋 {r['nf']} سوال  |  📊 {r['nr']} پاسخ", ""]
        btns.append([{"text": f"{t['icon']} {r['title']} ({r['nf']} سوال)"[:44],
                      "callback_data": f"evpick_{r['id']}_{eid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"evwiz_{eid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_reg_form(cid, uid, fid, eid):
    """اتصال یک فرم موجود به رویداد"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")
    try:
        fid = int(fid)
    except (TypeError, ValueError):
        return send(cid, "❌ شناسه فرم نامعتبر")
    f = db_execute("SELECT * FROM forms WHERE id=?", (fid,), fetch="one")
    if not f:
        return send(cid, "❌ فرم یافت نشد")

    nf = db_scalar("SELECT COUNT(*) FROM form_fields WHERE form_id=?",
                   (fid,)) or 0
    if nf == 0:
        return send(cid, "⚠️ این فرم هیچ سوالی ندارد")

    _link_form(eid, fid)
    # فرم پیش‌نویس را فعال کن تا کاربر بتواند پر کند
    if f.get("status") != "active":
        db_execute("UPDATE forms SET status='active' WHERE id=?", (fid,))
    log_action(uid, "event_form_linked", {"eid": eid, "fid": fid,
                                          "mode": "existing"})
    send(cid, f"✅ فرم «{f['title']}» به این رویداد وصل شد\n"
              f"📋 {nf} سوال  |  🟢 فعال")
    return show_review(cid, uid, eid)


# ==================== 🔍 مرور تنظیمات مهم ====================
# تاگل‌های پرکاربرد که در «مرور نهایی» یک‌جا نشان داده می‌شوند.
# همه با پیشوند ثابت evtog_ کار می‌کنند (هندلر موجود).
REVIEW_TOGGLES = [
    ("require_profile",  "👤", "نیاز به پروفایل تأییدشده"),
    ("hide_cost_hint",   "🙈", "مخفی کردن کامل اشاره به هزینه"),
    ("reminder_enabled", "🔔", "یادآوری خودکار"),
    ("has_attendance",   "✋", "حضور و غیاب"),
    ("has_certificate",  "🎓", "گواهینامه پایان"),
    ("require_approval", "👨‍💼", "تأیید دستی ادمین"),
    ("show_price_publicly", "💰", "نمایش قیمت به کاربر"),
    ("refund_enabled",   "💸", "امکان بازپرداخت"),
    ("has_survey",       "📊", "نظرسنجی بعد از رویداد"),
]


def show_review(cid, uid, eid):
    """
    🔍 مرور یک‌جای تنظیمات مهم — همه چیز دم دست.

    به‌جای اینکه کاربر ۶۰ بار در منوها بچرخد، همه تاگل‌های پرکاربرد
    را اینجا می‌بیند و با یک کلیک عوض می‌کند.
    """
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    lines = [
        "🔍 مرور نهایی تنظیمات",
        f"🎉 {ev.get('title')}",
        "━━━━━━━━━━━━━━", "",
        "یک نگاه بیندازید — هرچه لازم بود همین‌جا عوض کنید:", "",
    ]
    btns = []

    # ظرفیت
    cap = int(ev.get("capacity") or 0)
    lines.append(f"👥 ظرفیت: {cap if cap else 'نامحدود'}")
    btns.append([{"text": f"👥 ظرفیت: {cap if cap else 'نامحدود'}",
                  "callback_data": f"evcap_capacity_{eid}"}])

    # روش ثبت‌نام
    fid = ev.get("registration_form_id")
    if fid:
        f = db_execute("SELECT title, status FROM forms WHERE id=?", (fid,),
                       fetch="one")
        nf = db_scalar("SELECT COUNT(*) FROM form_fields WHERE form_id=?",
                       (fid,)) or 0
        if f:
            rm = f"📝 {f['title']} ({nf} سوال)"
            if f.get("status") != "active":
                rm += " ⚠️ منتشر نشده"
        else:
            rm = "📝 فرم اختصاصی"
    else:
        rm = "🎁 بدون فرم (از پروفایل)"
    lines.append(f"📋 ثبت‌نام با: {rm}")
    btns.append([{"text": f"📋 ثبت‌نام: {rm}"[:40],
                  "callback_data": f"evwiz_{eid}"}])

    # تاگل‌های مهم — همه با evtog_ (هندلر موجود)
    for key, icon, title in REVIEW_TOGGLES:
        on = int(ev.get(key) or 0)
        lines.append(f"{icon} {title}: {'✅ روشن' if on else '❌ خاموش'}")
        btns.append([{"text": f"{icon} {title}: {'✅' if on else '❌'}",
                      "callback_data": "evtogr_" + key + f"_{eid}"}])

    lines += ["", "━━━━━━━━━━━━━━"]
    st = ev.get("status")
    if st == "draft":
        lines.append("📝 وضعیت: پیش‌نویس — هنوز منتشر نشده")
        btns.append([{"text": "🚀 تأیید و انتشار رویداد",
                      "callback_data": f"ev_pub_{eid}"}])
    else:
        lines.append(f"📌 وضعیت: {STATUS_LABELS.get(st, st)}")

    btns.append([{"text": "⚙️ تنظیمات پیشرفته‌تر",
                  "callback_data": f"evx_{eid}"}])
    btns.append([{"text": "👁️ مشاهده رویداد",
                  "callback_data": f"ev_view_{eid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_num_edit(cid, uid, key, eid):
    """ویرایش سریع یک عدد از صفحه مرور"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    if key not in ("capacity",):
        return send(cid, "❌ نامعتبر")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    set_state(uid, STATE_EV_NUM, {"eid": eid, "key": key}, merge=False)
    cur = ev.get(key) or 0
    send(cid, (f"👥 ظرفیت رویداد\n━━━━━━━━━━━━━━\n\n"
               f"📄 مقدار فعلی: {cur if cur else 'نامحدود'}\n\n"
               f"عدد جدید را بفرستید:\n۰ = نامحدود"), kb_cancel())


def handle_num_edit(message):
    """دریافت عدد جدید"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = normalize_digits((message.get("text") or "").strip())
    d = get_state_data(uid)
    eid, key = d.get("eid"), d.get("key")

    if text in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_review(cid, uid, eid)

    import re as _re
    digits = _re.sub(r"[^\d]", "", text)
    if not digits:
        return send(cid, "⚠️ فقط عدد بفرستید:")
    val = max(0, min(1000000, int(digits)))

    if key == "capacity":
        db_execute("UPDATE events SET capacity=?, "
                   "updated_at=CURRENT_TIMESTAMP WHERE id=?", (val, eid))
    clear_state(uid)
    send(cid, f"✅ ذخیره شد: {val if val else 'نامحدود'}", kb_remove())
    return show_review(cid, uid, eid)


# ==================== لیست ادمین ====================
def show_admin_events(cid, uid, page=0):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")

    total = db_scalar("SELECT COUNT(*) FROM events")
    if total == 0:
        return send_or_edit(cid, "📭 هنوز رویدادی ساخته نشده", {"inline_keyboard": [
            [{"text": "🎉 ساخت رویداد جدید", "callback_data": "ev_new"}],
            [{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}]]})

    per = EVENTS_PER_PAGE
    pages = max(1, (total + per - 1) // per)
    page = max(0, min(int(page or 0), pages - 1))

    rows = db_execute(
        "SELECT * FROM events ORDER BY id DESC LIMIT ? OFFSET ?",
        (per, page * per), fetch="all")

    lines = [f"📋 رویدادهای من ({total})", "━━━━━━━━━━━━━━", ""]
    btns = []
    for ev in rows:
        t = EVENT_TYPES.get(ev.get("event_type") or "meeting", EVENT_TYPES["meeting"])
        cnt = reg_count(ev["id"], "confirmed")
        lines += [
            f"{t['icon']} {ev['title']}",
            f"├── {STATUS_LABELS.get(ev.get('status'), '-')}",
            f"├── 📅 {ev.get('start_date') or '-'}",
            f"└── 👥 {cnt} ثبت‌نام" + (f" از {ev['capacity']}" if ev.get("capacity") else ""),
            "",
        ]
        btns.append([{"text": f"{t['icon']} {ev['title']}"[:45],
                      "callback_data": f"ev_view_{ev['id']}"}])

    nav = []
    if page > 0:
        nav.append({"text": "◀️", "callback_data": f"evpg_{page-1}"})
    nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
    if page < pages - 1:
        nav.append({"text": "▶️", "callback_data": f"evpg_{page+1}"})
    btns.append(nav)
    btns.append([{"text": "🎉 رویداد جدید", "callback_data": "ev_new"}])
    btns.append([{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}])

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_event_admin(cid, uid, eid):
    """
    🎉 کارت مدیریت رویداد — سبک و مرتب.

    🎯 فاز ۲۳: «کلا قسمت مدیریت رویداد رو منوش رو جامع و کامل کن،
       خیلی بهم‌ریختس، کامل و جامع و سبک باشه»

    🔴 قبلاً ۱۲ دکمهٔ هم‌ارز پشت هم بود — کاربر نمی‌فهمید کدام
       مهم است. حالا سه لایه:
         ۱) کار اصلی همین حالا (وضعیت رویداد)
         ۲) چهار در ورودی اصلی
         ۳) بقیه پشت «⚙️ تنظیمات» و «⋮ بیشتر»
    """
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    confirmed = reg_count(eid, "confirmed")
    pending = reg_count(eid, "pending")
    waitlist = reg_count(eid, "waitlist")
    income = db_scalar(
        "SELECT COALESCE(SUM(amount_paid),0) FROM event_registrations "
        "WHERE event_id=? AND status IN ('confirmed','attended')", (eid,))

    st = ev.get("status")
    t = EVENT_TYPES.get(ev.get("event_type") or "workshop",
                        EVENT_TYPES.get("workshop", {}))
    stat = STATUS_LABELS.get(st, st or "—")

    # ── خلاصه یک‌نگاهی ──
    lines = [f"{t.get('icon','🎉')} {ev.get('title')}",
             "━━━━━━━━━━━━━━", "",
             f"📊 وضعیت: {stat}"]
    if ev.get("start_date"):
        d = ev["start_date"]
        if ev.get("start_time"):
            d += f" — {ev['start_time']}"
        lines.append(f"📅 {d}")
    cap = int(ev.get("capacity") or 0)
    lines.append(f"👥 ثبت‌نام: {confirmed}" + (f" از {cap}" if cap else ""))
    if pending:
        lines.append(f"⏳ در انتظار پرداخت: {pending}")
    if waitlist:
        lines.append(f"📋 لیست انتظار: {waitlist}")
    if int(ev.get("is_paid") or 0):
        lines.append(f"💰 درآمد: {fmt_money(income)} {CURRENCY_LABEL}")
    else:
        lines.append("🎁 رایگان")

    # ── قابلیت‌های روشن ──
    on = []
    if ev.get("has_attendance"):
        n_s = db_scalar("SELECT COUNT(*) FROM attendance_sessions "
                        "WHERE event_id=?", (eid,)) or 0
        on.append(f"✋ حضور ({n_s} جلسه)")
    if ev.get("has_certificate"):
        n_c = db_scalar("SELECT COUNT(*) FROM certificates "
                        "WHERE event_id=?", (eid,)) or 0
        # 🎓 فاز ۳۲ — اگر چند گواهینامهٔ مستقل دارد، بگو
        try:
            import eventcert as _evc
            _nk = _evc.count_certs(eid)
        except Exception:
            _nk = 0
        if _nk > 1:
            on.append(f"🎓 {_nk} گواهینامه ({n_c} صادرشده)")
        else:
            on.append(f"🎓 گواهینامه ({n_c})")
    if ev.get("has_ticket"):
        on.append("🎫 بلیت")
    if ev.get("registration_form_id"):
        on.append("📝 فرم ثبت‌نام")
    if on:
        lines += ["", "✨ " + " · ".join(on)]

    # 💡 قدم بعدی — کاربر سردرگم نشود
    tip = _next_step_tip(ev, confirmed)
    if tip:
        lines += ["", tip]

    # ═══ دکمه‌ها: سه لایه ═══
    btns = []

    # لایه ۱ — کار اصلی همین حالا
    if st == "draft":
        btns.append([{"text": "🚀 انتشار رویداد",
                      "callback_data": f"ev_pub_{eid}"}])
    elif st == "published":
        btns.append([{"text": "📢 اطلاع‌رسانی",
                      "callback_data": f"ev_notify_{eid}"},
                     {"text": "🔴 بستن ثبت‌نام",
                      "callback_data": f"ev_close_{eid}"}])
    elif st == "closed":
        btns.append([{"text": "🟢 بازکردن",
                      "callback_data": f"ev_pub_{eid}"},
                     {"text": "✅ اتمام رویداد",
                      "callback_data": f"ev_finish_{eid}"}])

    # لایه ۲ — چهار در اصلی
    btns.append([{"text": f"👥 ثبت‌نام‌ها ({confirmed})",
                  "callback_data": f"ev_regs_{eid}_0"}])
    row = []
    if ev.get("has_attendance"):
        row.append({"text": "✋ حضور و غیاب",
                    "callback_data": f"att_list_{eid}"})
    if ev.get("has_certificate"):
        # 🎓 فاز ۳۲ — اگر چند گواهینامهٔ مستقل دارد، مستقیم به
        #    مدیریت آن‌ها برود؛ وگرنه همان صدور گروهی قبلی.
        try:
            import eventcert as _evc
            _nk = _evc.count_certs(eid)
        except Exception:
            _nk = 0
        row.append({"text": (f"🎓 گواهینامه ({_nk})" if _nk > 1
                             else "🎓 گواهینامه"),
                    "callback_data": (f"evc_p_{eid}" if _nk > 1
                                      else f"cert_bulk_{eid}")})
    if row:
        btns.append(row)
    btns.append([{"text": "📊 گزارش", "callback_data": f"ev_report_{eid}"},
                 {"text": "🔍 مرور سریع", "callback_data": f"evrev_{eid}"}])
    btns.append([{"text": "⚙️ تنظیمات", "callback_data": f"evset_{eid}"},
                 {"text": "⋮ بیشتر", "callback_data": f"evmore_{eid}"}])

    btns.append([{"text": "🔙 لیست رویدادها", "callback_data": "ev_list"}])

    text = "\n".join(lines)
    has_poster = bool(ev.get("poster") and Path(ev["poster"]).exists())
    if has_poster:
        send_photo(cid, ev["poster"])
    send_or_edit(cid, text, {"inline_keyboard": btns}, force_new=has_poster)


def _next_step_tip(ev, confirmed=0):
    """💡 قدم بعدی چیست؟ — راهنمای کوتاه و مهربان"""
    eid = ev["id"]
    st = ev.get("status")
    if st == "draft":
        return "💡 رویداد پیش‌نویس است — با «🚀 انتشار» آن را باز کنید."
    if st == "published" and not confirmed:
        return "🌱 هنوز کسی ثبت‌نام نکرده — «📢 اطلاع‌رسانی» کمک می‌کند."
    if ev.get("has_attendance"):
        n_s = db_scalar("SELECT COUNT(*) FROM attendance_sessions "
                        "WHERE event_id=?", (eid,)) or 0
        if not n_s and confirmed:
            return "💡 برای حضور و غیاب، اول یک جلسه بسازید."
    # 🎓 فاز ۳۲ — اگر گواهینامه روشن است ولی تعریف نشده
    if ev.get("has_certificate"):
        try:
            import eventcert as _evc
            if not _evc.count_certs(eid):
                return ("🎓 گواهینامه روشن است ولی تعریف نشده — "
                        "از «🎓 گواهینامه‌های رویداد» اضافه کنید.")
        except Exception:
            pass
    if st == "finished" and ev.get("has_certificate"):
        n_c = db_scalar("SELECT COUNT(*) FROM certificates "
                        "WHERE event_id=?", (eid,)) or 0
        if not n_c and confirmed:
            return "🎓 رویداد تمام شد — وقت صدور گواهینامه است."
    return ""


def show_event_settings(cid, uid, eid):
    """
    ⚙️ تنظیمات رویداد — همه‌چیز قابل تغییر، یکجا و دسته‌بندی‌شده.

    🎯 «کامل و جامع و سبک باشه»
    """
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    t = EVENT_TYPES.get(ev.get("event_type") or "workshop", {})
    lines = ["⚙️ تنظیمات رویداد", "━━━━━━━━━━━━━━", "",
             f"{t.get('icon','🎉')} {ev.get('title')[:38]}", "",
             "📌 پایه:",
             f"   🏷️ نوع: {t.get('name','—')}",
             f"   📅 تاریخ: {ev.get('start_date') or '—'}",
             f"   📍 مکان: {(ev.get('location_address') or '—')[:34]}",
             f"   👥 ظرفیت: {ev.get('capacity') or 'نامحدود'}",
             "",
             "💰 مالی:"]
    if int(ev.get("is_paid") or 0):
        from payments import PAYMENT_METHODS
        pm = PAYMENT_METHODS.get(ev.get("payment_method") or "", {})
        lines += [f"   💳 {pm.get('icon','')} {pm.get('name','—')}",
                  f"   💵 مبلغ: {fmt_money(ev.get('price'))} "
                  f"{CURRENCY_LABEL}"]
    else:
        lines.append("   🎁 رایگان")

    lines += ["", "✨ قابلیت‌ها:"]
    for key, icon, name in (("has_attendance", "✋", "حضور و غیاب"),
                            ("has_certificate", "🎓", "گواهینامه"),
                            ("has_ticket", "🎫", "بلیت"),
                            ("has_survey", "📊", "نظرسنجی پایانی")):
        lines.append(f"   {'🟢' if ev.get(key) else '⚪'} {icon} {name}")

    btns = [
        [{"text": "🔍 مرور و تغییر سریع", "callback_data": f"evrev_{eid}"}],
        [{"text": "⚙️ تنظیمات پیشرفته", "callback_data": f"evx_{eid}"}],
    ]
    if ev.get("registration_form_id"):
        btns.append([{"text": "📝 فرم ثبت‌نام",
                      "callback_data": f"fbv_{ev['registration_form_id']}"}])
    btns.append([{"text": "🔙 رویداد", "callback_data": f"ev_view_{eid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_event_more(cid, uid, eid):
    """⋮ کارهای کم‌کاربرد — از صفحه اصلی جدا شد"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    send_or_edit(cid, (
        f"⋮ گزینه‌های بیشتر\n━━━━━━━━━━━━━━\n\n"
        f"🎉 {ev.get('title')[:38]}"
    ), {"inline_keyboard": [
        [{"text": "📤 خروجی اکسل", "callback_data": f"ev_export_{eid}"}],
        [{"text": "🎓 گواهینامه‌های رویداد",
          "callback_data": f"evc_p_{eid}"}],
        [{"text": "🔍 مرور سریع تنظیمات", "callback_data": f"evrev_{eid}"}],
        [{"text": "🗑️ حذف رویداد", "callback_data": f"ev_delq_{eid}"}],
        [{"text": "🔙 رویداد", "callback_data": f"ev_view_{eid}"}]]})


def set_event_status(cid, uid, eid, status):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")

    extra = ""
    if status == "published" and not ev.get("published_at"):
        db_execute("UPDATE events SET published_at=CURRENT_TIMESTAMP WHERE id=?", (eid,))
    db_execute("UPDATE events SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (status, eid))

    # اتمام رویداد → امتیازدهی به حاضرین
    if status == "finished" and ev.get("points_reward"):
        # هر کاربر فقط یک‌بار به‌ازای هر رویداد (کلید evfin:{event}:{user})؛
        # اجرای دوبارهٔ «پایان» امتیاز تکراری نمی‌دهد ولی نفرات ثبت‌نشده را تکمیل می‌کند.
        regs = db_execute(
            "SELECT id, bale_user_id FROM event_registrations "
            "WHERE event_id=? AND status IN ('confirmed','attended')", (eid,), fetch="all")
        n = dup = failed = 0
        for r in regs or []:
            if not r.get("bale_user_id"):
                continue
            try:
                with db_transaction():
                    res = pl.post_points(
                        r["bale_user_id"], int(ev["points_reward"]), entry_type="award",
                        source="event_finished", ref_key=f"evfin:{eid}:{r['bale_user_id']}",
                        ref_table="event_registrations", ref_id=r["id"],
                        actor_kind="admin", actor_id=uid, reason=f"پایان رویداد {eid}")
                    if res.created:
                        db_execute(
                            "UPDATE users SET total_events_registered="
                            "COALESCE(total_events_registered,0)+1 WHERE bale_user_id=?",
                            (r["bale_user_id"],))
                        n += 1
                    else:
                        dup += 1
            except pl.LedgerError as e:
                failed += 1
                log(f"❌ امتیاز پایان رویداد {eid} برای {r['bale_user_id']}: {e.code}")
        pl.sync_pending(limit=50)
        extra = f"\n🏆 {ev['points_reward']} امتیاز به {n} نفر داده شد"
        if dup:
            extra += f"\nℹ️ {dup} نفر قبلاً امتیاز این رویداد را گرفته بودند"
        if failed:
            extra += f"\n⚠️ {failed} نفر ثبت نشدند؛ با اجرای دوبارهٔ «پایان» تکمیل می‌شود"

    send(cid, f"✅ وضعیت تغییر کرد: {STATUS_LABELS.get(status)}{extra}")
    show_event_admin(cid, uid, eid)


def delete_event(cid, uid, eid, confirmed=False):
    if uid != SUPER_ADMIN_ID and not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")

    if not confirmed:
        n = reg_count(eid)
        return send_or_edit(cid, (
            f"⚠️ حذف دائمی رویداد\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"🎉 {ev['title']}\n"
            f"👥 {n} ثبت‌نام\n\n"
            f"❗ این عمل قابل بازگشت نیست!"
        ), {"inline_keyboard": [
            [{"text": "🗑️ بله، حذف کن", "callback_data": f"ev_dely_{eid}"}],
            [{"text": "🔙 انصراف", "callback_data": f"ev_view_{eid}"}]]})

    db_execute("DELETE FROM event_registrations WHERE event_id=?", (eid,))
    db_execute("DELETE FROM events WHERE id=?", (eid,))
    log_action(uid, "event_deleted", {"event_id": eid})
    send(cid, "🗑️ رویداد حذف شد")
    show_admin_events(cid, uid, 0)


# ==================== نمای کاربر ====================
def show_user_events(cid, uid, page=0):
    """فقط رویدادهای فعال — بدون دسته‌بندی (طبق درخواست شما)"""
    u = get_user(uid)
    is_vip = bool(u and u.get("is_vip"))

    rows = db_execute("""
        SELECT * FROM events
        WHERE status='published' AND privacy IN ('public','vip')
          AND COALESCE(show_in_list, 1) = 1
        ORDER BY
          CASE WHEN start_date IS NULL OR start_date='' THEN 1 ELSE 0 END,
          start_date ASC, id DESC
    """, fetch="all") or []

    visible = [e for e in rows if e.get("privacy") != "vip" or is_vip]

    if not visible:
        return send_or_edit(cid, (
            "🎉 رویدادها\n"
            "━━━━━━━━━━━━━━\n\n"
            "📭 در حال حاضر رویداد فعالی وجود ندارد.\n\n"
            "💡 به‌زودی برنامه‌های جدید اعلام می‌شود."
        ), {"inline_keyboard": [
            [{"text": "🔑 ورود با کد دعوت", "callback_data": "ev_bycode"}],
            [{"text": "🔙 منوی اصلی", "callback_data": "back_main"}]]})

    per = EVENTS_PER_PAGE
    pages = max(1, (len(visible) + per - 1) // per)
    page = max(0, min(int(page or 0), pages - 1))
    chunk = visible[page * per:(page + 1) * per]

    lines = ["🎉 رویدادهای فعال", "━━━━━━━━━━━━━━", ""]
    btns = []
    for ev in chunk:
        t = EVENT_TYPES.get(ev.get("event_type") or "meeting", EVENT_TYPES["meeting"])
        my = db_execute(
            "SELECT status FROM event_registrations WHERE event_id=? AND bale_user_id=?",
            (ev["id"], uid), fetch="one")

        badge = ""
        if my and my.get("status") == "confirmed":
            badge = "✅ "
        elif my and my.get("status") == "pending":
            badge = "⏳ "
        elif is_full(ev):
            badge = "🈵 "

        if not ev.get("is_paid"):
            cost = "🆓 رایگان"
        elif show_price(ev):
            cost = ""
            try:
                import infra_fee as _inf
                cost, _ = _inf.short_label(ev.get("price"))
            except Exception:
                cost = ""
            if not cost:
                cost = f"💳 {fmt_money(ev.get('price'))} {CURRENCY_LABEL}"
        elif int(ev.get("hide_cost_hint") or 0):
            cost = "📌 ثبت‌نام باز است"
        else:
            cost = "💳 هزینه‌دار"
        when = ev.get("start_date") or "به‌زودی"
        if ev.get("start_time"):
            when += f" ساعت {ev['start_time']}"

        lines += [f"{badge}{t['icon']} {ev['title']}", f"├── 📅 {when}", f"└── {cost}", ""]
        btns.append([{"text": f"{badge}{t['icon']} {ev['title']}"[:45],
                      "callback_data": f"uev_{ev['id']}"}])

    nav = []
    if page > 0:
        nav.append({"text": "◀️", "callback_data": f"uevpg_{page-1}"})
    if pages > 1:
        nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
    if page < pages - 1:
        nav.append({"text": "▶️", "callback_data": f"uevpg_{page+1}"})
    if nav:
        btns.append(nav)

    btns.append([{"text": "🎫 رویدادهای من", "callback_data": "u_myevents"}])
    btns.append([{"text": "🔑 ورود با کد دعوت", "callback_data": "ev_bycode"}])
    btns.append([{"text": "🔙 منوی اصلی", "callback_data": "back_main"}])

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_event_user(cid, uid, eid):
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    if ev.get("status") not in ("published", "closed"):
        return send(cid, "⚠️ این رویداد در دسترس نیست")

    u = get_user(uid)
    if ev.get("privacy") == "vip" and not (u and u.get("is_vip")):
        return send(cid, "⭐ این رویداد فقط برای اعضای ویژه است")

    my = db_execute(
        "SELECT * FROM event_registrations WHERE event_id=? AND bale_user_id=?",
        (eid, uid), fetch="one")

    text = event_full_text(ev, for_admin=False)

    btns = []
    if my:
        st = my.get("status")
        text += f"\n\n📌 وضعیت ثبت‌نام شما: {REG_STATUS.get(st, st)}"
        if my.get("ticket_code"):
            text += f"\n🎫 کد بلیت: {my['ticket_code']}"

        if st == "confirmed":
            if ev.get("online_link"):
                text += f"\n\n🔗 لینک ورود:\n{ev['online_link']}"
            btns.append([{"text": "🎫 مشاهده بلیت", "callback_data": f"uticket_{eid}"}])
            btns.append([{"text": "❌ لغو ثبت‌نام", "callback_data": f"ucancel_{eid}"}])
        elif st == "pending":
            text += "\n\n💡 پرداخت شما تکمیل نشده است."
            btns.append([{"text": "💳 پرداخت", "callback_data": f"upay_{eid}"}])
            btns.append([{"text": "❌ لغو", "callback_data": f"ucancel_{eid}"}])
        elif st == "waitlist":
            text += "\n\n📋 شما در لیست انتظار هستید."
            btns.append([{"text": "❌ خروج از لیست", "callback_data": f"ucancel_{eid}"}])
    else:
        if ev.get("status") == "closed":
            text += "\n\n🔴 ثبت‌نام این رویداد بسته شده است."
        elif is_full(ev):
            text += "\n\n🈵 ظرفیت تکمیل شده است."
            if ev.get("allow_waitlist"):
                btns.append([{"text": "📋 ثبت در لیست انتظار", "callback_data": f"ureg_{eid}"}])
        else:
            if not ev.get("is_paid"):
                label = "🎫 ثبت‌نام رایگان"
            elif show_price(ev):
                label = ""
                try:
                    import infra_fee as _inf
                    if _inf.is_infra(ev.get("price")):
                        label = "🎫 ثبت‌نام رایگان"
                except Exception:
                    label = ""
                if not label:
                    label = (f"💳 ثبت‌نام ({fmt_money(ev.get('price'))} "
                             f"{CURRENCY_LABEL})")
            else:
                label = "💳 ثبت‌نام"
            btns.append([{"text": label, "callback_data": f"ureg_{eid}"}])

    btns.append([{"text": "🔙 لیست رویدادها", "callback_data": "u_events"}])

    has_poster = bool(ev.get("poster") and Path(ev["poster"]).exists())
    if has_poster:
        send_photo(cid, ev["poster"])
    send_or_edit(cid, text, {"inline_keyboard": btns}, force_new=has_poster)


# ==================== ثبت‌نام ====================
# ═══════════════════════════════════════════════════════════
# ⚙️ قابلیت‌های پیشرفته رویداد (فاز ۱۱)
# ═══════════════════════════════════════════════════════════
EV_TOGGLES = {
    "require_invites": "🎯 دعوت اجباری",
    "show_in_list": "👁️ نمایش در لیست عمومی",
    "show_in_search": "🔍 نمایش در جستجو",
    "show_participant_count": "🔢 نمایش تعداد شرکت‌کنندگان",
    "show_participant_list": "📋 نمایش لیست شرکت‌کنندگان",
    "show_price_publicly": "💰 نمایش قیمت پیش از ثبت‌نام",
    "allow_sharing": "📤 اجازه اشتراک‌گذاری",
    "reminder_enabled": "🔔 یادآوری خودکار",
    "refund_enabled": "💸 امکان بازپرداخت",
    "venue_has_parking": "🅿️ پارکینگ دارد",
    "survey_enabled": "📊 نظرسنجی بعد از رویداد",
    "survey_reminder": "🔁 یادآوری نظرسنجی",
    "survey_anonymous": "🕶️ نظرسنجی ناشناس",
    "rem_3d": "📅 یادآوری ۳ روز قبل",
    "rem_1d": "📆 یادآوری ۱ روز قبل",
    "rem_2h": "🕐 یادآوری ۲ ساعت قبل",
    "rem_30m": "🕧 یادآوری ۳۰ دقیقه قبل",
    "rem_start": "▶️ یادآوری لحظه شروع",
    "rem_welcome": "👋 پیام خوش‌آمد",
    "rem_thanks": "💚 پیام تشکر",
    "invite_strict": "🎯 فقط دعوت تأییدشده",
    "invite_exempt_vip": "⭐ معافیت VIP از دعوت",
    # 🆕 فاز ۱۵ — تاگل‌های «مرور نهایی» (قابل تغییر از یک صفحه)
    "has_attendance": "✋ حضور و غیاب",
    "has_certificate": "🎓 گواهینامه پایان",
    "has_survey": "📊 نظرسنجی بعد از رویداد",
    "require_approval": "👨‍💼 تأیید دستی ادمین",
    "has_ticket": "🎫 صدور بلیت",
    "require_profile": "👤 نیاز به پروفایل تأییدشده",
    "hide_cost_hint": "🙈 مخفی کردن کامل اشاره به هزینه",
}

# ستون‌هایی که وقتی از «مرور نهایی» تاگل شوند، باید به همان صفحه برگردند
REVIEW_COLS = {
    "has_attendance", "has_certificate", "has_survey",
    "require_approval", "has_ticket", "require_profile",
    "hide_cost_hint",
}

EV_TEXTS = {
    "invite_message": ("🎯 پیام دعوت اجباری", "پیامی که هنگام کمبود دعوت نشان داده شود:"),
    "unauthorized_message": ("🚫 پیام غیرمجاز", "پیام برای کسانی که شرایط ندارند:"),
    "online_platform": ("🌐 پلتفرم آنلاین", "مثال: اسکای‌روم، گوگل‌میت، زوم"),
    "online_password": ("🔑 رمز جلسه آنلاین", "رمز ورود به جلسه:"),
    "online_instructions": ("📖 راهنمای ورود آنلاین", "توضیح نحوه اتصال:"),
    "venue_name": ("🏢 نام محل", "نام سالن / مکان:"),
    "venue_access_info": ("🚗 راهنمای دسترسی", "نحوه رسیدن، پارکینگ، ...:"),
    "speakers": ("🎤 سخنرانان", "نام سخنرانان (هر خط یک نفر):"),
    "agenda": ("📋 برنامه زمانی", "سرفصل‌ها (هر خط یک مورد):"),
    "prerequisites": ("📚 پیش‌نیازها", "پیش‌نیازهای شرکت (هر خط یکی):"),
    "required_items": ("🎒 وسایل لازم", "چه چیزهایی همراه بیاورند:"),
    "faq": ("❓ سوالات متداول", "سوال و جواب‌ها:"),
    "chat_group_url": ("💬 لینک گروه گفتگو", "لینک گروه بله:"),
    # 🆕 فاز ۱۵
    "sponsors": ("🏢 اسپانسرها", "نام حامیان (هر خط یکی):"),
    "gallery": ("📸 گالری دوره‌های قبل",
                "لینک عکس‌ها یا توضیح (هر خط یکی):"),
    "materials": ("📚 محتوای آموزشی",
                  "لینک PDF/ویدیو یا توضیح (هر خط یکی):"),
    "trip_plan": ("🗺️ برنامه سفر", "برنامه روزانه اردو (هر خط یکی):"),
    "emergency_contacts": ("🚨 تماس اضطراری",
                           "شماره‌های ضروری (هر خط یکی):"),
    "restrict_city": ("🏙️ محدودیت شهر", "شهرهای مجاز با کاما:\n\nمثال: تهران، کرج"),
    "subtitle": ("📝 زیرعنوان", "توضیح کوتاه زیر عنوان:"),
    "rem_message": ("📝 پیام یادآوری", "متن سفارشی یادآوری رویداد:"),
}

EV_NUMS = {
    "invites_needed": ("🎯 تعداد دعوت لازم", "چند نفر باید دعوت کند؟"),
    "restrict_age_min": ("🎂 حداقل سن", "حداقل سن مجاز (۰ = بدون محدودیت):"),
    "restrict_age_max": ("🎂 حداکثر سن", "حداکثر سن مجاز (۰ = بدون محدودیت):"),
    "min_points_required": ("🏆 حداقل امتیاز", "حداقل امتیاز لازم (۰ = آزاد):"),
    "refund_percent": ("💸 درصد بازپرداخت", "چند درصد برگردد؟ (۰ تا ۱۰۰):"),
    "cert_min_sessions": ("🎓 حداقل جلسات گواهینامه", "برای گواهینامه چند جلسه لازم است؟"),
    "survey_points": ("🎁 امتیاز تکمیل نظرسنجی", "چند امتیاز برای پاسخ به نظرسنجی؟"),
    "invite_recent_days": ("📅 دعوت در N روز اخیر",
                           "دعوت باید در چند روز اخیر باشد؟ (۰ = بدون محدودیت)"),
    "invite_reward": ("🎁 پاداش هر دعوت", "برای هر دعوت چند امتیاز؟"),
}


def show_advanced(cid, uid, eid):
    """⚙️ قابلیت‌های پیشرفته — همه آپشن‌های فایل معماری"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    gmap = {"all": "👥 همه", "male": "👨 فقط آقایان", "female": "👩 فقط خانم‌ها"}
    lines = [
        f"⚙️ قابلیت‌های پیشرفته",
        f"🎉 {ev.get('title')}",
        "━━━━━━━━━━━━━━", "",
        "🎯 دعوت اجباری: "
        + (f"✅ {ev.get('invites_needed') or 0} نفر"
           if ev.get("require_invites") else "❌ غیرفعال"),
        "",
        "🚦 محدودیت ثبت‌نام:",
        f"   • جنسیت: {gmap.get(ev.get('restrict_gender') or 'all')}",
        f"   • سن: "
        + (f"{ev.get('restrict_age_min') or '—'} تا {ev.get('restrict_age_max') or '—'}"
           if (ev.get("restrict_age_min") or ev.get("restrict_age_max")) else "آزاد"),
        f"   • شهر: {ev.get('restrict_city') or 'آزاد'}",
        f"   • حداقل امتیاز: {ev.get('min_points_required') or 0}",
        "",
        "👁️ نمایش:",
        f"   • در لیست: {'✅' if ev.get('show_in_list', 1) else '❌'}"
        f"   • در جستجو: {'✅' if ev.get('show_in_search', 1) else '❌'}",
        f"   • تعداد شرکت‌کنندگان: {'✅' if ev.get('show_participant_count', 1) else '❌'}",
        f"   • قیمت: {'✅' if ev.get('show_price_publicly', 1) else '❌'}",
        "",
        f"🎤 سخنرانان: {'✅' if ev.get('speakers') else '—'}"
        f"   📋 برنامه: {'✅' if ev.get('agenda') else '—'}",
        f"💬 گروه گفتگو: {'✅' if ev.get('chat_group_url') else '—'}",
        f"🔔 یادآوری: {'✅ فعال' if ev.get('reminder_enabled', 1) else '❌'}",
        f"💸 بازپرداخت: "
        + (f"✅ {ev.get('refund_percent') or 100}%"
           if ev.get("refund_enabled") else "❌"),
    ]
    if ev.get("password_hash"):
        lines.append("🔐 رمز عبور: ✅ دارد")

    # 💳 فاز ۱۳ — روش پرداخت (و روش‌های مجاز در حالت چند روشی)
    if int(ev.get("is_paid") or 0):
        from payments import PAYMENT_METHODS as _PM, allowed_methods
        _m = ev.get("payment_method") or "none"
        _info = _PM.get(_m, _PM["none"])
        lines += ["", f"💳 پرداخت: {_info['icon']} {_info['name']}"]
        if _m == "multi":
            _names = [f"{_PM[x]['icon']} {_PM[x]['name']}"
                      for x in allowed_methods(ev) if x in _PM]
            lines.append("   " + (" | ".join(_names) or "— انتخاب نشده —"))

    btns_pay = []
    if int(ev.get("is_paid") or 0) and \
            (ev.get("payment_method") or "") == "multi":
        btns_pay.append([{"text": "🎛️ روش‌های پرداخت مجاز",
                          "callback_data": f"evmulti_{eid}"}])

    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns_pay + [
        [{"text": "🎯 دعوت اجباری", "callback_data": f"evinv_{eid}"}],
        [{"text": "🚦 محدودیت ثبت‌نام", "callback_data": f"evres_{eid}"}],
        [{"text": "👁️ تنظیمات نمایش", "callback_data": f"evshow_{eid}"}],
        [{"text": "🎤 محتوا (سخنران، برنامه، ...)", "callback_data": f"evcnt_{eid}"}],
        [{"text": "🌐 جزئیات آنلاین/حضوری", "callback_data": f"evloc_{eid}"}],
        [{"text": "🎫 کدهای دعوت", "callback_data": f"evcode_{eid}"}],
        [{"text": "🔐 رمز عبور رویداد", "callback_data": f"evpwd_{eid}"}],
        [{"text": "🎁 کدهای تخفیف", "callback_data": f"evdisc_{eid}"}],
        [{"text": "💸 بازپرداخت", "callback_data": f"evref_{eid}"}],
        [{"text": "🔔 یادآوری خودکار", "callback_data": f"evrem_{eid}"}],
        [{"text": "📊 نظرسنجی بعد از رویداد", "callback_data": f"evsurv_{eid}"}],
        [{"text": "📝 فرم ثبت‌نام رویداد", "callback_data": f"evform_{eid}"}],
        [{"text": "⭐ نظرات شرکت‌کنندگان", "callback_data": f"evrate_{eid}"}],
        [{"text": "🎲 قرعه‌کشی و جوایز", "callback_data": f"lt_event_{eid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"ev_view_{eid}"}],
    ]})


def show_invites(cid, uid, eid):
    """🎯 تنظیم دعوت اجباری رویداد"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    on = bool(ev.get("require_invites"))
    strict = ev.get("invite_strict")
    strict = 1 if strict is None else strict
    days = int(ev.get("invite_recent_days") or 0)

    lines = [
        "🎯 دعوت اجباری", "━━━━━━━━━━━━━━", "",
        f"وضعیت: {'✅ فعال' if on else '❌ غیرفعال'}",
        f"📊 تعداد لازم: {ev.get('invites_needed') or 0} نفر",
        "",
        "⚙️ شرایط پیشرفته:",
        f"   {'✅' if strict else '⬜'} فقط دعوت‌های تأییدشده حساب شود",
        f"      (ثبت‌نام کرده + پروفایل ≥ ۳۰٪)",
        f"   {'✅' if ev.get('invite_exempt_vip') else '⬜'} کاربران VIP معاف باشند",
        f"   📅 دعوت در {days} روز اخیر"
        + ("  (۰ = بدون محدودیت زمانی)" if not days else ""),
        f"   🎁 پاداش هر دعوت: {ev.get('invite_reward') or 0} امتیاز",
        "",
        f"📝 پیام: {ev.get('invite_message') or '(پیش‌فرض)'}",
        "",
        "💡 ادمین‌ها همیشه معافند.",
    ]
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": ("❌ غیرفعال کردن" if on else "✅ فعال کردن"),
          "callback_data": f"evtog_require_invites_{eid}"}],
        [{"text": "🔢 تعداد دعوت لازم", "callback_data": f"evnum_invites_needed_{eid}"}],
        [{"text": f"{'✅' if strict else '⬜'} فقط دعوت تأییدشده",
          "callback_data": f"evtog_invite_strict_{eid}"}],
        [{"text": f"{'✅' if ev.get('invite_exempt_vip') else '⬜'} معافیت VIP",
          "callback_data": f"evtog_invite_exempt_vip_{eid}"}],
        [{"text": "📅 محدوده زمانی دعوت",
          "callback_data": f"evnum_invite_recent_days_{eid}"}],
        [{"text": "🎁 پاداش هر دعوت", "callback_data": f"evnum_invite_reward_{eid}"}],
        [{"text": "📝 پیام سفارشی", "callback_data": f"evtxt_invite_message_{eid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"evx_{eid}"}]]})


def show_restrictions(cid, uid, eid):
    """🚦 محدودیت‌های ثبت‌نام"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    gmap = {"all": "👥 همه", "male": "👨 فقط آقایان", "female": "👩 فقط خانم‌ها"}
    return send_or_edit(cid, (
        "🚦 محدودیت ثبت‌نام\n━━━━━━━━━━━━━━\n\n"
        f"🚻 جنسیت: {gmap.get(ev.get('restrict_gender') or 'all')}\n"
        f"🎂 سن: {ev.get('restrict_age_min') or 0} تا "
        f"{ev.get('restrict_age_max') or 0}  (۰ = آزاد)\n"
        f"🏙️ شهر: {ev.get('restrict_city') or 'آزاد'}\n"
        f"🏆 حداقل امتیاز: {ev.get('min_points_required') or 0}\n\n"
        f"🚫 پیام غیرمجاز: {ev.get('unauthorized_message') or '(پیش‌فرض)'}"
    ), {"inline_keyboard": [
        [{"text": "🚻 جنسیت", "callback_data": f"evgen_{eid}"}],
        [{"text": "🎂 حداقل سن", "callback_data": f"evnum_restrict_age_min_{eid}"},
         {"text": "🎂 حداکثر سن", "callback_data": f"evnum_restrict_age_max_{eid}"}],
        [{"text": "🏙️ شهرهای مجاز", "callback_data": f"evtxt_restrict_city_{eid}"}],
        [{"text": "🏆 حداقل امتیاز",
          "callback_data": f"evnum_min_points_required_{eid}"}],
        [{"text": "🚫 پیام غیرمجاز",
          "callback_data": f"evtxt_unauthorized_message_{eid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"evx_{eid}"}]]})


def show_gender_restrict(cid, uid, eid, g=None):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    if g is not None:
        if g not in ("all", "male", "female"):
            return send(cid, "❌ نامعتبر")
        db_execute("UPDATE events SET restrict_gender=? WHERE id=?", (g, eid))
        return show_restrictions(cid, uid, eid)
    cur = ev.get("restrict_gender") or "all"
    opts = [("all", "👥 همه"), ("male", "👨 فقط آقایان"), ("female", "👩 فقط خانم‌ها")]
    btns = [[{"text": f"{'🔘' if k == cur else '⚪'} {n}",
              "callback_data": f"evgens_{k}_{eid}"}] for k, n in opts]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"evres_{eid}"}])
    return send_or_edit(cid, "🚻 این رویداد برای چه کسانی است؟",
                        {"inline_keyboard": btns})


def show_display_opts(cid, uid, eid):
    """👁️ تنظیمات نمایش"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    keys = ["show_in_list", "show_in_search", "show_participant_count",
            "show_participant_list", "show_price_publicly",
            "hide_cost_hint", "allow_sharing"]
    btns = [[{"text": f"{EV_TOGGLES[k]} {'✅' if ev.get(k, 1) else '❌'}",
              "callback_data": f"evtog_{k}_{eid}"}] for k in keys]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"evx_{eid}"}])
    return send_or_edit(cid, (
        "👁️ تنظیمات نمایش\n━━━━━━━━━━━━━━\n\n"
        "کنترل کنید چه چیزی به کاربران نشان داده شود:"
    ), {"inline_keyboard": btns})


def show_content(cid, uid, eid):
    """🎤 محتوای تکمیلی رویداد"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    keys = ["subtitle", "speakers", "agenda", "prerequisites",
            "required_items", "faq", "chat_group_url",
            # 🆕 فاز ۱۵
            "sponsors", "gallery", "materials",
            "trip_plan", "emergency_contacts"]
    lines = ["🎤 محتوای تکمیلی", "━━━━━━━━━━━━━━", ""]
    btns = []
    for k in keys:
        title = EV_TEXTS[k][0]
        val = ev.get(k)
        lines.append(f"{title}: {'✅ دارد' if val else '—'}")
        btns.append([{"text": f"✏️ {title}", "callback_data": f"evtxt_{k}_{eid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"evx_{eid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_location_opts(cid, uid, eid):
    """🌐 جزئیات آنلاین و حضوری"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    SEND_TIMES = {"immediate": "بلافاصله", "1h_before": "۱ ساعت قبل",
                  "30m_before": "۳۰ دقیقه قبل", "at_start": "زمان شروع"}
    lines = [
        "🌐 جزئیات برگزاری", "━━━━━━━━━━━━━━", "",
        f"🌐 پلتفرم: {ev.get('online_platform') or '—'}",
        f"🔑 رمز جلسه: {'✅' if ev.get('online_password') else '—'}",
        f"⏰ ارسال لینک: "
        + SEND_TIMES.get(ev.get("online_link_send_time") or "immediate", "بلافاصله"),
        f"📖 راهنمای ورود: {'✅' if ev.get('online_instructions') else '—'}",
        "",
        f"🏢 نام محل: {ev.get('venue_name') or '—'}",
        f"🚗 راهنمای دسترسی: {'✅' if ev.get('venue_access_info') else '—'}",
        f"🅿️ پارکینگ: {'✅ دارد' if ev.get('venue_has_parking') else '❌'}",
    ]
    btns = [
        [{"text": "🌐 پلتفرم", "callback_data": f"evtxt_online_platform_{eid}"}],
        [{"text": "🔑 رمز جلسه", "callback_data": f"evtxt_online_password_{eid}"}],
        [{"text": "⏰ زمان ارسال لینک", "callback_data": f"evlt_{eid}"}],
        [{"text": "📖 راهنمای ورود",
          "callback_data": f"evtxt_online_instructions_{eid}"}],
        [{"text": "🏢 نام محل", "callback_data": f"evtxt_venue_name_{eid}"}],
        [{"text": "🚗 راهنمای دسترسی",
          "callback_data": f"evtxt_venue_access_info_{eid}"}],
        [{"text": f"🅿️ پارکینگ {'✅' if ev.get('venue_has_parking') else '❌'}",
          "callback_data": f"evtog_venue_has_parking_{eid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"evx_{eid}"}],
    ]
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_link_time(cid, uid, eid, t=None):
    """⏰ زمان ارسال لینک آنلاین"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    opts = [("immediate", "⚡ بلافاصله بعد ثبت‌نام"),
            ("1h_before", "🕐 یک ساعت قبل"),
            ("30m_before", "🕧 نیم ساعت قبل"),
            ("at_start", "▶️ زمان شروع")]
    if t is not None:
        if t not in dict(opts):
            return send(cid, "❌ نامعتبر")
        db_execute("UPDATE events SET online_link_send_time=? WHERE id=?", (t, eid))
        return show_location_opts(cid, uid, eid)
    ev = get_event(eid) or {}
    cur = ev.get("online_link_send_time") or "immediate"
    btns = [[{"text": f"{'🔘' if k == cur else '⚪'} {n}",
              "callback_data": f"evlts_{k}_{eid}"}] for k, n in opts]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"evloc_{eid}"}])
    return send_or_edit(cid, (
        "⏰ لینک آنلاین کی برای کاربر ارسال شود؟\n\n"
        "💡 ارسال دیرتر جلوی لو رفتن لینک را می‌گیرد."
    ), {"inline_keyboard": btns})


def show_refund(cid, uid, eid):
    """💸 تنظیمات بازپرداخت"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    on = bool(ev.get("refund_enabled"))
    return send_or_edit(cid, (
        "💸 بازپرداخت\n━━━━━━━━━━━━━━\n\n"
        f"وضعیت: {'✅ فعال' if on else '❌ غیرفعال'}\n"
        f"📊 درصد بازگشت: {ev.get('refund_percent') or 100}%\n"
        f"📅 مهلت: {ev.get('refund_until') or '—'}\n\n"
        "💡 اگر فعال باشد، کاربر تا مهلت تعیین‌شده\n"
        "   می‌تواند درخواست انصراف و بازگشت وجه بدهد."
    ), {"inline_keyboard": [
        [{"text": ("❌ غیرفعال کردن" if on else "✅ فعال کردن"),
          "callback_data": f"evtog_refund_enabled_{eid}"}],
        [{"text": "📊 درصد بازگشت", "callback_data": f"evnum_refund_percent_{eid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"evx_{eid}"}]]})


REMINDER_SLOTS = [
    ("rem_3d", "📅 ۳ روز قبل"),
    ("rem_1d", "📆 ۱ روز قبل"),
    ("rem_2h", "🕐 ۲ ساعت قبل"),
    ("rem_30m", "🕧 ۳۰ دقیقه قبل"),
    ("rem_start", "▶️ لحظه شروع"),
    ("rem_welcome", "👋 خوش‌آمد بعد از ثبت‌نام"),
    ("rem_thanks", "💚 تشکر بعد از رویداد"),
]


def show_reminder(cid, uid, eid):
    """🔔 یادآوری خودکار — تنظیمات کامل طبق خط ۳۹۷۸۳ فایل معماری"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    on = bool(ev.get("reminder_enabled", 1))

    lines = ["🔔 یادآوری خودکار", "━━━━━━━━━━━━━━", "",
             f"وضعیت کلی: {'✅ فعال' if on else '❌ خاموش'}", "",
             "⏰ زمان‌های ارسال:"]
    for col, label in REMINDER_SLOTS:
        dflt = 1 if col in ("rem_1d", "rem_2h", "rem_welcome", "rem_thanks") else 0
        v = ev.get(col)
        v = dflt if v is None else v
        lines.append(f"   {'✅' if v else '⬜'} {label}")
    if ev.get("rem_message"):
        lines += ["", f"📝 پیام سفارشی: {str(ev['rem_message'])[:100]}"]
    lines += ["", "💡 فقط به کسانی می‌رود که ثبت‌نامشان قطعی شده."]

    btns = [[{"text": ("❌ خاموش کردن همه" if on else "✅ روشن کردن"),
              "callback_data": f"evtog_reminder_enabled_{eid}"}]]
    for col, label in REMINDER_SLOTS:
        dflt = 1 if col in ("rem_1d", "rem_2h", "rem_welcome", "rem_thanks") else 0
        v = ev.get(col)
        v = dflt if v is None else v
        btns.append([{"text": f"{'✅' if v else '⬜'} {label}",
                      "callback_data": f"evtog_{col}_{eid}"}])
    btns.append([{"text": "📝 پیام سفارشی یادآوری",
                  "callback_data": f"evtxt_rem_message_{eid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"evx_{eid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


SURVEY_TIMES = {
    "immediate": "⚡ بلافاصله بعد از پایان",
    "2h_after": "🕐 ۲ ساعت بعد",
    "next_day": "📆 روز بعد",
    "3d_after": "📅 ۳ روز بعد",
}


def show_survey(cid, uid, eid):
    """📊 نظرسنجی پس از رویداد — طبق خط ۵۱۰۲۲ فایل معماری"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    on = bool(ev.get("survey_enabled"))

    fname = "—"
    if ev.get("survey_form_id"):
        row = db_execute("SELECT title FROM forms WHERE id=?",
                         (ev["survey_form_id"],), fetch="one")
        fname = (row or {}).get("title") or "(حذف‌شده)"

    lines = [
        "📊 نظرسنجی بعد از رویداد", "━━━━━━━━━━━━━━", "",
        f"وضعیت: {'✅ فعال' if on else '❌ غیرفعال'}",
        f"📋 فرم نظرسنجی: {fname}",
        f"⏰ زمان ارسال: "
        + SURVEY_TIMES.get(ev.get("survey_send_time") or "2h_after", "۲ ساعت بعد"),
        f"🔁 یادآوری برای بی‌پاسخ‌ها: "
        f"{'✅' if ev.get('survey_reminder') else '❌'}",
        f"🕶️ پاسخ ناشناس: {'✅' if ev.get('survey_anonymous') else '❌'}",
        f"🎁 امتیاز تکمیل: {ev.get('survey_points') or 0}",
        "",
        "💡 فقط برای کسانی ارسال می‌شود که حضورشان ثبت شده.",
    ]
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": ("❌ غیرفعال کردن" if on else "✅ فعال کردن"),
          "callback_data": f"evtog_survey_enabled_{eid}"}],
        [{"text": "📋 انتخاب فرم نظرسنجی", "callback_data": f"evsf_{eid}"}],
        [{"text": "⏰ زمان ارسال", "callback_data": f"evst_{eid}"}],
        [{"text": f"🔁 یادآوری {'✅' if ev.get('survey_reminder') else '❌'}",
          "callback_data": f"evtog_survey_reminder_{eid}"},
         {"text": f"🕶️ ناشناس {'✅' if ev.get('survey_anonymous') else '❌'}",
          "callback_data": f"evtog_survey_anonymous_{eid}"}],
        [{"text": "🎁 امتیاز تکمیل", "callback_data": f"evnum_survey_points_{eid}"}],
        [{"text": "📈 گزارش و ارسال", "callback_data": f"sv_rep_{eid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"evx_{eid}"}]]})


def pick_survey_form(cid, uid, eid, fid=None):
    """انتخاب یا ساخت فرم نظرسنجی"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")

    if fid is not None:
        db_execute("UPDATE events SET survey_form_id=? WHERE id=?",
                   (fid if fid > 0 else None, eid))
        send(cid, "✅ فرم نظرسنجی تنظیم شد" if fid > 0 else "🔗 اتصال حذف شد")
        return show_survey(cid, uid, eid)

    rows = db_execute("""SELECT id, title FROM forms
        WHERE form_type IN ('survey','questionnaire')
        ORDER BY id DESC LIMIT 12""", fetch="all") or []
    cur = ev.get("survey_form_id")
    btns = [[{"text": f"{'🔘' if not cur else '⚪'} بدون فرم",
              "callback_data": f"evsfs_0_{eid}"}]]
    for f in rows:
        btns.append([{"text": f"{'🔘' if cur == f['id'] else '⚪'} {f['title'][:32]}",
                      "callback_data": f"evsfs_{f['id']}_{eid}"}])
    btns.append([{"text": "➕ ساخت فرم نظرسنجی جدید",
                  "callback_data": f"evsfnew_{eid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"evsurv_{eid}"}])
    return send_or_edit(cid, (
        "📋 فرم نظرسنجی\n━━━━━━━━━━━━━━\n\n"
        + ("یک فرم انتخاب کنید:" if rows
           else "هنوز فرم نظرسنجی نساخته‌اید.")
    ), {"inline_keyboard": btns})


def show_survey_time(cid, uid, eid, t=None):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    if t is not None:
        if t not in SURVEY_TIMES:
            return send(cid, "❌ نامعتبر")
        db_execute("UPDATE events SET survey_send_time=? WHERE id=?", (t, eid))
        return show_survey(cid, uid, eid)
    ev = get_event(eid) or {}
    cur = ev.get("survey_send_time") or "2h_after"
    btns = [[{"text": f"{'🔘' if k == cur else '⚪'} {v}",
              "callback_data": f"evsts_{k}_{eid}"}] for k, v in SURVEY_TIMES.items()]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"evsurv_{eid}"}])
    return send_or_edit(cid, "⏰ نظرسنجی کی ارسال شود؟",
                        {"inline_keyboard": btns})


# ═══════════════════════════════════════════════════════════
# 📝 فرم ثبت‌نام اختصاصی رویداد
# طبق فایل: «گزینه A فرم داخل رویداد، گزینه B از فرم‌ساز»
# ═══════════════════════════════════════════════════════════
def show_reg_form(cid, uid, eid, fid=None):
    """📝 اتصال یا ساخت فرم ثبت‌نام برای رویداد"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")

    if fid is not None:
        db_execute("UPDATE events SET registration_form_id=? WHERE id=?",
                   (fid if fid > 0 else None, eid))
        send(cid, "✅ فرم ثبت‌نام تنظیم شد" if fid > 0 else "🔗 اتصال حذف شد")
        return show_reg_form(cid, uid, eid)

    cur = ev.get("registration_form_id")
    cur_name = "—"
    n_fields = 0
    if cur:
        row = db_execute("SELECT title FROM forms WHERE id=?", (cur,), fetch="one")
        cur_name = (row or {}).get("title") or "(حذف‌شده)"
        n_fields = db_scalar("SELECT COUNT(*) FROM form_fields WHERE form_id=?",
                             (cur,))

    rows = db_execute("""SELECT id, title FROM forms
        WHERE form_type='registration' ORDER BY id DESC LIMIT 10""",
        fetch="all") or []

    lines = [
        "📝 فرم ثبت‌نام رویداد", "━━━━━━━━━━━━━━", "",
        f"📋 فرم فعلی: {cur_name}",
    ]
    if cur:
        lines.append(f"❓ تعداد سوالات: {n_fields}")
    lines += ["", "💡 اگر فرم وصل کنید، کاربر هنگام ثبت‌نام",
              "   ابتدا سوالات فرم را پاسخ می‌دهد."]

    btns = [[{"text": "➕ ساخت فرم اختصاصی این رویداد",
              "callback_data": f"evformnew_{eid}"}]]
    if rows:
        btns.append([{"text": f"{'🔘' if not cur else '⚪'} بدون فرم",
                      "callback_data": f"evforms_0_{eid}"}])
        for f in rows:
            btns.append([{"text": f"{'🔘' if cur == f['id'] else '⚪'} {f['title'][:30]}",
                          "callback_data": f"evforms_{f['id']}_{eid}"}])
    if cur:
        btns.append([{"text": "⚙️ ویرایش این فرم", "callback_data": f"fbv_{cur}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"evx_{eid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def create_reg_form(cid, uid, eid, advanced=False):
    """
    ➕ ساخت فرم ثبت‌نام آماده برای این رویداد.

    advanced=True → کاربر به فرم‌ساز می‌رود و بعد از ویرایش
    با دکمه «بازگشت به رویداد» برمی‌گردد (طبق فایل معماری).
    """
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    try:
        import forms as fb
        slug = fb.gen_slug()
        while db_execute("SELECT id FROM forms WHERE slug=?", (slug,), fetch="one"):
            slug = fb.gen_slug()
        title = f"ثبت‌نام {str(ev.get('title'))[:40]}"
        fid = db_execute("""INSERT INTO forms
            (owner_id, form_type, title, slug, status, one_per_user,
             end_text, payment_method, event_id)
            VALUES (?, 'registration', ?, ?, 'active', 1, ?, 'none', ?)""",
            (uid, title, slug,
             get_setting("form_txt_end_default", "💚 سپاس از شما"), eid))
        if not fid:
            return send(cid, "❌ خطا در ساخت فرم")
        n = fb.apply_template(fid, "registration")
        _link_form(eid, fid)
        log_action(uid, "event_form_linked",
                   {"eid": eid, "fid": fid, "mode": "advanced"})
        send(cid, (
            f"✅ فرم «{title}» ساخته شد\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"📝 {n} سوال آماده اضافه شد\n"
            f"🔗 به رویداد «{str(ev.get('title'))[:30]}» وصل شد\n\n"
            f"💡 حالا سوالات را دلخواه ویرایش کنید،\n"
            f"بعد «🔙 بازگشت به رویداد» را بزنید."
        ), {"inline_keyboard": [
            [{"text": "📝 ویرایش سوالات", "callback_data": f"fbf_{fid}"}],
            [{"text": "🎨 فرم‌ساز کامل", "callback_data": f"fbv_{fid}"}],
            [{"text": "🔙 بازگشت به رویداد",
              "callback_data": f"evrev_{eid}"}]]})
        return fid
    except Exception as e:
        log(f"❌ ساخت فرم رویداد: {e}")
        return send(cid, "❌ خطا در ساخت فرم")


def create_survey_form(cid, uid, eid):
    """➕ ساخت فرم نظرسنجی آماده برای این رویداد"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    try:
        import forms as fb
        slug = fb.gen_slug()
        while db_execute("SELECT id FROM forms WHERE slug=?", (slug,), fetch="one"):
            slug = fb.gen_slug()
        title = f"نظرسنجی {str(ev.get('title'))[:40]}"
        fid = db_execute("""INSERT INTO forms
            (owner_id, form_type, title, slug, status, anonymous, one_per_user,
             end_text, payment_method, event_id)
            VALUES (?, 'survey', ?, ?, 'draft', 1, 1, ?, 'none', ?)""",
            (uid, title, slug,
             get_setting("form_txt_end_default", "💚 سپاس از شما"), eid))
        if not fid:
            return send(cid, "❌ خطا در ساخت فرم")
        n = fb.apply_template(fid, "survey")
        db_execute("UPDATE events SET survey_form_id=?, survey_enabled=1 WHERE id=?",
                   (fid, eid))
        send(cid, (
            f"✅ فرم «{title}» ساخته شد\n"
            f"📝 {n} سوال آماده اضافه شد\n"
            f"📊 نظرسنجی این رویداد فعال شد."
        ))
        return fb.show_form(cid, uid, fid)
    except Exception as e:
        log(f"❌ ساخت فرم نظرسنجی: {e}")
        return send(cid, "❌ خطا در ساخت فرم")


# ═══════════════════════════════════════════════════════════
# 🎁 کدهای تخفیف رویداد
# ═══════════════════════════════════════════════════════════
def show_discounts(cid, uid, eid):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    rows = db_execute("SELECT * FROM event_discount_codes WHERE event_id=? "
                      "ORDER BY id DESC", (eid,), fetch="all") or []

    from config import money
    lines = [f"🎁 کدهای تخفیف «{str(ev.get('title'))[:24]}»",
             "━━━━━━━━━━━━━━", ""]
    btns = []
    if rows:
        for d in rows:
            st = "🟢" if d.get("is_active") else "⚫"
            amt = (f"{d.get('amount')}%" if d.get("discount_type") == "percent"
                   else money(d.get("amount") or 0))
            mx = d.get("max_uses") or 0
            lines.append(f"{st} `{d['code']}` — {amt}")
            lines.append(f"   استفاده: {d.get('current_uses') or 0}/"
                         f"{mx if mx else '∞'}"
                         + (f" | تا {d['expires_at']}" if d.get("expires_at") else ""))
            btns.append([
                {"text": f"{st} {d['code']}", "callback_data": f"evdv_{d['id']}_{eid}"},
                {"text": "🗑️", "callback_data": f"evddel_{d['id']}_{eid}"},
            ])
    else:
        lines.append("📭 کد تخفیفی تعریف نشده")
    lines += ["", "💡 کاربر هنگام پرداخت کد را وارد می‌کند."]
    btns.append([{"text": "➕ کد تخفیف جدید", "callback_data": f"evdadd_{eid}"}])
    if rows:
        btns.append([{"text": "📊 گزارش استفاده", "callback_data": f"evdrep_{eid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"evx_{eid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_add_discount(cid, uid, eid):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    from config import CURRENCY_LABEL
    set_state(uid, STATE_EV_DISC, {"eid": eid}, merge=False)
    send(cid, (
        "➕ کد تخفیف جدید\n━━━━━━━━━━━━━━\n\n"
        "در یک خط بنویسید:\n\n"
        "کد | مقدار | سقف استفاده\n\n"
        "مثال درصدی:\n"
        "NOWRUZ | 20% | 50\n\n"
        f"مثال مبلغی:\n"
        f"OFF5 | 5000 | 10   ({CURRENCY_LABEL})\n\n"
        "💡 سقف ۰ یا خالی = نامحدود"
    ), kb_cancel())


def handle_add_discount(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    eid = get_state_data(uid).get("eid")

    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_discounts(cid, uid, eid)

    parts = [p.strip() for p in text.replace("،", "|").split("|")]
    code = (parts[0] if parts else "").upper().replace(" ", "")
    code = "".join(ch for ch in code if ch.isalnum() or ch in "-_")
    if len(code) < 3:
        return send(cid, "⚠️ کد حداقل ۳ کاراکتر (انگلیسی/عدد):", kb_cancel())
    if db_execute("SELECT id FROM event_discount_codes WHERE code=?", (code,),
                  fetch="one"):
        return send(cid, "⚠️ این کد قبلاً استفاده شده. کد دیگری بنویسید:",
                    kb_cancel())

    raw = parts[1] if len(parts) > 1 else "0"
    is_pct = "%" in raw or "٪" in raw
    digits = "".join(ch for ch in normalize_digits(raw) if ch.isdigit())
    if not digits:
        return send(cid, "⚠️ مقدار تخفیف را بنویسید (مثال: 20% یا 5000):",
                    kb_cancel())
    val = int(digits)
    if is_pct:
        val = max(1, min(100, val))
        dtype = "percent"
    else:
        from config import parse_money
        val = parse_money(digits)
        dtype = "amount"

    mx = 0
    if len(parts) > 2:
        d2 = "".join(ch for ch in normalize_digits(parts[2]) if ch.isdigit())
        mx = int(d2) if d2 else 0

    clear_state(uid)
    db_execute("""INSERT INTO event_discount_codes
        (event_id, code, discount_type, amount, max_uses, created_by)
        VALUES (?,?,?,?,?,?)""", (eid, code, dtype, val, mx, uid))
    from config import money
    shown = f"{val}%" if dtype == "percent" else money(val)
    send(cid, f"✅ کد `{code}` ساخته شد\n🎁 تخفیف: {shown}\n"
              f"📊 سقف: {mx if mx else 'نامحدود'}", kb_remove())
    return show_discounts(cid, uid, eid)


def delete_discount(cid, uid, did, eid):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    try:
        db_execute("DELETE FROM event_discount_codes WHERE id=?", (int(did),))
    except (TypeError, ValueError):
        pass
    return show_discounts(cid, uid, eid)


def view_discount(cid, uid, did, eid):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    try:
        d = db_execute("SELECT * FROM event_discount_codes WHERE id=?",
                       (int(did),), fetch="one")
    except (TypeError, ValueError):
        d = None
    if not d:
        return send(cid, "❌ یافت نشد")
    from config import money
    amt = (f"{d.get('amount')}%" if d.get("discount_type") == "percent"
           else money(d.get("amount") or 0))
    return send_or_edit(cid, (
        f"🎁 کد `{d['code']}`\n━━━━━━━━━━━━━━\n\n"
        f"💰 تخفیف: {amt}\n"
        f"📊 استفاده: {d.get('current_uses') or 0}/"
        f"{d.get('max_uses') or '∞'}\n"
        f"👤 سقف هر نفر: {d.get('per_user_limit') or 1}\n"
        f"💸 مجموع تخفیف داده‌شده: {money(d.get('total_discount') or 0)}\n"
        f"📈 درآمد با این کد: {money(d.get('revenue_from_code') or 0)}\n"
        f"📊 وضعیت: {'🟢 فعال' if d.get('is_active') else '⚫ غیرفعال'}"
    ), {"inline_keyboard": [
        [{"text": ("⚫ غیرفعال" if d.get("is_active") else "🟢 فعال"),
          "callback_data": f"evdtg_{d['id']}_{eid}"}],
        [{"text": "🗑️ حذف", "callback_data": f"evddel_{d['id']}_{eid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"evdisc_{eid}"}]]})


def toggle_discount(cid, uid, did, eid):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    try:
        d = db_execute("SELECT is_active FROM event_discount_codes WHERE id=?",
                       (int(did),), fetch="one")
    except (TypeError, ValueError):
        d = None
    if not d:
        return send(cid, "❌ یافت نشد")
    db_execute("UPDATE event_discount_codes SET is_active=? WHERE id=?",
               (0 if d.get("is_active") else 1, int(did)))
    return view_discount(cid, uid, did, eid)


def discount_report(cid, uid, eid):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    from config import money
    rows = db_execute("""SELECT d.code, d.discount_type, d.amount,
        d.current_uses, d.total_discount, d.revenue_from_code
        FROM event_discount_codes d WHERE d.event_id=?
        ORDER BY d.current_uses DESC""", (eid,), fetch="all") or []
    tot_used = sum(int(r.get("current_uses") or 0) for r in rows)
    tot_disc = sum(int(r.get("total_discount") or 0) for r in rows)
    lines = ["📊 گزارش کدهای تخفیف", "━━━━━━━━━━━━━━", "",
             f"🎫 تعداد کد: {len(rows)}",
             f"📈 مجموع استفاده: {tot_used}",
             f"💸 مجموع تخفیف: {money(tot_disc)}", ""]
    for r in rows:
        amt = (f"{r.get('amount')}%" if r.get("discount_type") == "percent"
               else money(r.get("amount") or 0))
        lines.append(f"• {r['code']} ({amt}) — {r.get('current_uses') or 0} بار")
    if not rows:
        lines.append("📭 کدی نیست")
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": f"evdisc_{eid}"}]]})


def apply_discount(code, eid, uid, amount):
    """
    اعمال کد تخفیف روی مبلغ.
    خروجی: (ok, مبلغ نهایی, پیام, discount_id)
    """
    code = (code or "").strip().upper()
    if not code:
        return False, amount, "کد خالی است", None
    d = db_execute("""SELECT * FROM event_discount_codes
        WHERE code=? AND is_active=1 AND (event_id=? OR event_id IS NULL)""",
        (code, eid), fetch="one")
    if not d:
        return False, amount, "کد تخفیف نامعتبر است", None

    mx = int(d.get("max_uses") or 0)
    if mx and int(d.get("current_uses") or 0) >= mx:
        return False, amount, "سقف استفاده این کد پر شده", None

    exp = (d.get("expires_at") or "").strip()
    if exp:
        from forms import jdt_key, jnow
        k1, k2 = jdt_key(exp), jdt_key(jnow())
        if k1 and k2 and k2 > k1:
            return False, amount, "این کد منقضی شده", None

    per = int(d.get("per_user_limit") or 1)
    if per:
        used = db_scalar("SELECT COUNT(*) FROM event_discount_usage "
                         "WHERE discount_id=? AND bale_user_id=?", (d["id"], uid))
        if used >= per:
            return False, amount, "شما قبلاً از این کد استفاده کرده‌اید", None

    mn = int(d.get("min_amount") or 0)
    if mn and amount < mn:
        from config import money
        return False, amount, f"حداقل مبلغ برای این کد: {money(mn)}", None

    if d.get("discount_type") == "percent":
        cut = int(amount * int(d.get("amount") or 0) / 100)
    else:
        cut = int(d.get("amount") or 0)
    cut = max(0, min(amount, cut))
    final = amount - cut

    from config import money
    return True, final, f"تخفیف {money(cut)} اعمال شد", d["id"]


def record_discount_use(discount_id, eid, rid, uid, original, cut, final):
    """ثبت استفاده از کد تخفیف"""
    if not discount_id:
        return
    db_execute("""INSERT INTO event_discount_usage
        (discount_id, event_id, registration_id, bale_user_id,
         original_amount, discount_amount, final_amount)
        VALUES (?,?,?,?,?,?,?)""",
        (discount_id, eid, rid, uid, original, cut, final))
    db_execute("""UPDATE event_discount_codes SET
        current_uses=COALESCE(current_uses,0)+1,
        total_discount=COALESCE(total_discount,0)+?,
        revenue_from_code=COALESCE(revenue_from_code,0)+?
        WHERE id=?""", (cut, final, discount_id))


def show_ratings(cid, uid, eid):
    """⭐ نظرات شرکت‌کنندگان"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    rows = db_execute("""SELECT r.*, u.first_name, u.last_name
        FROM event_ratings r LEFT JOIN users u ON u.bale_user_id=r.bale_user_id
        WHERE r.event_id=? ORDER BY r.id DESC LIMIT 15""", (eid,), fetch="all") or []
    cnt = int(ev.get("rating_count") or 0)
    avg = (int(ev.get("rating_sum") or 0) / cnt) if cnt else 0

    lines = ["⭐ نظرات شرکت‌کنندگان", "━━━━━━━━━━━━━━", "",
             f"📊 میانگین: {avg:.1f} از ۵  ({cnt} نظر)", ""]
    if rows:
        for r in rows:
            nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or "—"
            lines.append(f"{'⭐' * int(r.get('rating') or 0)} {nm}")
            if r.get("comment"):
                lines.append(f"   «{r['comment'][:80]}»")
    else:
        lines.append("📭 هنوز نظری ثبت نشده")
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": f"evx_{eid}"}]]})


def toggle_ev(cid, uid, eid, col, back=None):
    """
    تاگل امن — فقط ستون‌های مجاز.

    🆕 فاز ۱۵: اگر از صفحه «مرور نهایی» آمده باشد (back='review')
       به همان‌جا برمی‌گردد نه به منوی دیگر.
    """
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    if col not in EV_TOGGLES:
        return send(cid, "❌ نامعتبر")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    default = 1 if col.startswith("show_") or col in (
        "allow_sharing", "reminder_enabled") else 0
    cur = ev.get(col)
    cur = default if cur is None else cur
    db_execute(f"UPDATE events SET {col}=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (0 if cur else 1, eid))

    # از صفحه مرور آمده → همان‌جا بماند
    if back == "review" or col in REVIEW_COLS:
        return show_review(cid, uid, eid)

    # برگرد به همان صفحه‌ای که آمده
    if col == "require_invites":
        return show_invites(cid, uid, eid)
    if col == "refund_enabled":
        return show_refund(cid, uid, eid)
    if col == "reminder_enabled":
        return show_reminder(cid, uid, eid)
    if col == "venue_has_parking":
        return show_location_opts(cid, uid, eid)
    if col.startswith("survey_"):
        return show_survey(cid, uid, eid)
    if col.startswith("rem_"):
        return show_reminder(cid, uid, eid)
    if col.startswith("invite_"):
        return show_invites(cid, uid, eid)
    return show_display_opts(cid, uid, eid)


def start_ev_text(cid, uid, eid, key):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    if key not in EV_TEXTS:
        return send(cid, "❌ نامعتبر")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    title, prompt = EV_TEXTS[key]
    set_state(uid, STATE_EV_ADV, {"eid": eid, "key": key}, merge=False)
    cur = ev.get(key) or "—"
    send(cid, (
        f"{title}\n━━━━━━━━━━━━━━\n\n"
        f"📌 فعلی:\n{str(cur)[:400]}\n\n{prompt}\n\n💡 «-» = خالی کردن"
    ), kb_cancel())


def start_ev_num(cid, uid, eid, key):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    if key not in EV_NUMS:
        return send(cid, "❌ نامعتبر")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    title, prompt = EV_NUMS[key]
    set_state(uid, STATE_EV_ADV, {"eid": eid, "key": key, "num": 1}, merge=False)
    send(cid, f"{title}\n━━━━━━━━━━━━━━\n\n📌 فعلی: {ev.get(key) or 0}\n\n{prompt}",
         kb_cancel())


def handle_adv_input(message):
    """ورودی متنی/عددی قابلیت‌های پیشرفته"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    data = get_state_data(uid)
    eid = data.get("eid")
    key = data.get("key")

    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_advanced(cid, uid, eid)

    if data.get("num"):
        d = "".join(ch for ch in normalize_digits(text) if ch.isdigit())
        if not d:
            return send(cid, "⚠️ فقط عدد وارد کنید:", kb_cancel())
        val = int(d)
        if key == "refund_percent":
            val = max(0, min(100, val))
        if key not in EV_NUMS:
            clear_state(uid)
            return send(cid, "⚠️ نامعتبر", kb_remove())
        clear_state(uid)
        db_execute(f"UPDATE events SET {key}=? WHERE id=?", (val, eid))
        send(cid, f"✅ ثبت شد: {val}", kb_remove())
        if key == "invites_needed":
            return show_invites(cid, uid, eid)
        if key == "refund_percent":
            return show_refund(cid, uid, eid)
        if key == "survey_points":
            return show_survey(cid, uid, eid)
        if key.startswith("invite_"):
            return show_invites(cid, uid, eid)
        return show_restrictions(cid, uid, eid)

    if key not in EV_TEXTS:
        clear_state(uid)
        return send(cid, "⚠️ نامعتبر", kb_remove())
    clear_state(uid)
    val = "" if text == "-" else text[:2000]
    db_execute(f"UPDATE events SET {key}=? WHERE id=?", (val, eid))
    send(cid, "✅ ذخیره شد", kb_remove())
    if key in ("invite_message",):
        return show_invites(cid, uid, eid)
    if key == "rem_message":
        return show_reminder(cid, uid, eid)
    if key in ("restrict_city", "unauthorized_message"):
        return show_restrictions(cid, uid, eid)
    if key in ("online_platform", "online_password", "online_instructions",
               "venue_name", "venue_access_info"):
        return show_location_opts(cid, uid, eid)
    return show_content(cid, uid, eid)


# ═══════════════════════════════════════════════════════════
# 🎫 کدهای دعوت رویداد
# ═══════════════════════════════════════════════════════════
def show_codes(cid, uid, eid):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    rows = db_execute("SELECT * FROM event_invite_codes WHERE event_id=? "
                      "ORDER BY id DESC", (eid,), fetch="all") or []
    lines = [f"🎫 کدهای دعوت «{ev.get('title')[:26]}»", "━━━━━━━━━━━━━━", ""]
    btns = []
    if rows:
        for c in rows:
            st = "🟢" if c.get("is_active") else "⚫"
            used = f"{c.get('current_uses') or 0}"
            mx = c.get("max_uses") or 0
            lines.append(f"{st} `{c['code']}`")
            lines.append(f"   استفاده: {used}/{mx if mx else '∞'}"
                         + (f" | {c.get('assigned_name')}"
                            if c.get("assigned_name") else ""))
            btns.append([{"text": f"🗑️ {c['code']}",
                          "callback_data": f"evcdel_{c['id']}_{eid}"}])
    else:
        lines.append("📭 کدی ساخته نشده")
    lines += ["", "💡 کاربر با /start و این کد مستقیم وارد رویداد می‌شود."]
    btns.append([{"text": "➕ ساخت کد جدید", "callback_data": f"evcadd_{eid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"evx_{eid}"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def add_code(cid, uid, eid):
    """ساخت کد دعوت یکتا"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    for _ in range(30):
        code = "EVC" + "".join(random.choices(
            string.ascii_uppercase + string.digits, k=7))
        if not db_execute("SELECT id FROM event_invite_codes WHERE code=?",
                          (code,), fetch="one"):
            db_execute("""INSERT INTO event_invite_codes
                (event_id, code, code_type, max_uses, created_by)
                VALUES (?,?, 'universal', 0, ?)""", (eid, code, uid))
            send(cid, f"✅ کد ساخته شد:\n\n`{code}`")
            return show_codes(cid, uid, eid)
    send(cid, "❌ خطا در ساخت کد")
    return show_codes(cid, uid, eid)


def delete_code(cid, uid, code_id, eid):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    try:
        db_execute("DELETE FROM event_invite_codes WHERE id=?", (int(code_id),))
    except (ValueError, TypeError):
        pass
    return show_codes(cid, uid, eid)


def show_password(cid, uid, eid):
    """🔐 رمز عبور رویداد"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")
    has = bool(ev.get("password_hash"))
    btns = [[{"text": ("🔄 تغییر رمز" if has else "🔐 تعیین رمز"),
              "callback_data": f"evpwdset_{eid}"}]]
    if has:
        btns.append([{"text": "🗑️ حذف رمز", "callback_data": f"evpwddel_{eid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"evx_{eid}"}])
    return send_or_edit(cid, (
        "🔐 رمز عبور رویداد\n━━━━━━━━━━━━━━\n\n"
        f"وضعیت: {'✅ رمز دارد' if has else '❌ بدون رمز'}\n\n"
        "💡 اگر رمز بگذارید، کاربر برای ثبت‌نام باید آن را وارد کند."
    ), {"inline_keyboard": btns})


def start_password(cid, uid, eid):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    set_state(uid, STATE_EV_PWD, {"eid": eid}, merge=False)
    send(cid, "🔐 رمز جدید رویداد را بنویسید:", kb_cancel())


def handle_password(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    eid = get_state_data(uid).get("eid")
    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_password(cid, uid, eid)
    if len(text) < 3:
        return send(cid, "⚠️ رمز حداقل ۳ کاراکتر:", kb_cancel())
    import hashlib
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    clear_state(uid)
    db_execute("UPDATE events SET password_hash=? WHERE id=?", (h, eid))
    send(cid, "✅ رمز ثبت شد", kb_remove())
    return show_password(cid, uid, eid)


def delete_password(cid, uid, eid):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    db_execute("UPDATE events SET password_hash=NULL WHERE id=?", (eid,))
    send(cid, "🗑️ رمز حذف شد")
    return show_password(cid, uid, eid)


# ═══════════════════════════════════════════════════════════
# 🚦 موتور بررسی شرایط دسترسی به رویداد
# طبق فایل معماری: دعوت اجباری، جنسیت، سن، شهر، امتیاز، برچسب
# ═══════════════════════════════════════════════════════════
def log_access(eid, uid, kind, success=True, reason=""):
    """ثبت لاگ دسترسی (طبق event_access_logs فایل معماری)"""
    try:
        db_execute("""INSERT INTO event_access_logs
            (event_id, bale_user_id, access_type, success, failure_reason)
            VALUES (?,?,?,?,?)""",
            (eid, uid, kind, 1 if success else 0, reason[:120]))
    except Exception as e:
        log(f"⚠️ لاگ دسترسی: {e}")


def count_confirmed_invites(uid, ev=None):
    """
    تعداد دعوت‌های تأییدشده کاربر.

    طبق فایل معماری، «تأییدشده» یعنی دعوت‌شده ثبت‌نام کرده
    و پروفایل پایه‌اش را تکمیل کرده باشد.
    اگر رویداد بدهیم، تنظیمات خودش (سخت‌گیری و بازه زمانی) اعمال می‌شود.
    """
    if ev is not None:
        strict = ev.get("invite_strict")
        strict = 1 if strict is None else int(strict or 0)
        days = int(ev.get("invite_recent_days") or 0)
    else:
        strict = 1 if get_setting("invite_strict", "1") == "1" else 0
        days = 0

    where = ["referred_by=?"]
    params = [uid]
    if strict:
        where.append("is_authenticated=1")
        where.append("COALESCE(complete_profile_percent,0) >= 30")
    if days > 0:
        where.append(f"created_at >= datetime('now', '-{int(days)} days')")
    return db_scalar(f"SELECT COUNT(*) FROM users WHERE {' AND '.join(where)}",
                     tuple(params))


def _age_from_birth(birth):
    """سن تقریبی از تاریخ تولد شمسی"""
    if not birth:
        return None
    try:
        from forms import g2j
        from datetime import datetime as _dt
        parts = normalize_digits(str(birth)).replace("-", "/").split("/")
        by = int(parts[0])
        g = _dt.now()
        jy, _, _ = g2j(g.year, g.month, g.day)
        age = jy - by
        return age if 0 < age < 130 else None
    except (ValueError, IndexError, TypeError):
        return None


def check_eligibility(uid, ev, u=None):
    """
    آیا کاربر شرایط ثبت‌نام در این رویداد را دارد؟
    خروجی: (ok, پیام، کیبورد)
    """
    u = u or get_user(uid) or {}
    eid = ev.get("id")

    # ادمین‌ها معافند (طبق «استثناها» در فایل)
    if _is_admin(uid):
        return True, "", None

    # ⭐ VIP
    if ev.get("privacy") == "vip" and not u.get("is_vip"):
        return False, (
            "⭐ رویداد ویژه اعضای VIP\n"
            "━━━━━━━━━━━━━━\n\n"
            + (ev.get("unauthorized_message")
               or "این رویداد فقط برای اعضای VIP است.")
        ), {"inline_keyboard": [
            [{"text": "🔙 بازگشت", "callback_data": f"uev_{eid}"}]]}

    # 🎯 دعوت اجباری
    if ev.get("require_invites") and int(ev.get("invites_needed") or 0) > 0:
        # ⭐ معافیت VIP (طبق «استثناها» در فایل معماری)
        if ev.get("invite_exempt_vip") and u.get("is_vip"):
            return True, "", None
        need = int(ev["invites_needed"])
        have = count_confirmed_invites(uid, ev)
        if have < need:
            pct = int(have * 100 / need) if need else 0
            blocks = max(0, min(10, pct // 10))
            code = u.get("referral_code") or ""
            try:
                from config import deep_link as _dl
                _u = _dl(code) if code else ""
            except Exception:
                _u = ""
            link = _u or f"کد معرف شما: {code}"
            # 💚 فاز ۱۷-ج — متن مهربان و قابل ویرایش از پنل
            from config import org_name as _org_fn
            try:
                from occasions import polite_name as _pn
                _nm = _pn(u)
            except Exception:
                _nm = u.get("first_name") or "دوست"

            if ev.get("invite_message"):
                body = str(ev["invite_message"])
            else:
                body = get_setting("msg_invite_required", "").strip() or (
                    "🤝 با همیاری و مهر\n"
                    "━━━━━━━━━━━━━━\n\n"
                    "{name} عزیز، برای شرکت در این برنامه\n"
                    "{need} نفر از دوستانتان را به مسیر علمی و فرهنگی\n"
                    "{org} دعوت کنید 💚\n\n"
                    "📊 تا اینجا: {done} از {need} نفر\n\n"
                    "هر دعوت، یک قدم برای گسترش این خانواده است 🌱")
            body = (body.replace("{name}", _nm)
                        .replace("{need}", str(need))
                        .replace("{done}", str(have))
                        .replace("{org}", _org_fn()))
            return False, (
                f"{body}\n\n"
                f"{'▓' * blocks}{'░' * (10 - blocks)} {pct}%\n\n"
                f"🔗 لینک اختصاصی شما:\n{link}"
            ), {"inline_keyboard": [
                [{"text": "🔄 بررسی مجدد", "callback_data": f"ureg_{eid}"}],
                [{"text": "👥 دعوت از دوستان", "callback_data": "u_referral"}],
                [{"text": "🔙 بازگشت", "callback_data": f"uev_{eid}"}]]}

    # 🚻 جنسیت
    g = (ev.get("restrict_gender") or "all").strip()
    if g in ("male", "female"):
        ug = (u.get("gender") or "").strip()
        male_ok = ug in ("مرد", "male", "آقا")
        female_ok = ug in ("زن", "female", "خانم")
        if (g == "male" and not male_ok) or (g == "female" and not female_ok):
            who = "آقایان" if g == "male" else "خانم‌ها"
            return False, (
                f"🚻 این رویداد فقط برای {who} است.\n\n"
                + (ev.get("unauthorized_message") or "")
            ), {"inline_keyboard": [
                [{"text": "🔙 بازگشت", "callback_data": f"uev_{eid}"}]]}

    # 🎂 سن
    lo = int(ev.get("restrict_age_min") or 0)
    hi = int(ev.get("restrict_age_max") or 0)
    if lo or hi:
        age = _age_from_birth(u.get("birth_date"))
        if age is None:
            return False, (
                "🎂 برای این رویداد باید تاریخ تولد شما ثبت باشد.\n\n"
                "از «👤 پروفایل من» تکمیل کنید."
            ), {"inline_keyboard": [
                [{"text": "📝 تکمیل پروفایل", "callback_data": "profile_fill"}],
                [{"text": "🔙 بازگشت", "callback_data": f"uev_{eid}"}]]}
        if (lo and age < lo) or (hi and age > hi):
            rng = (f"{lo} تا {hi}" if lo and hi
                   else (f"حداقل {lo}" if lo else f"حداکثر {hi}"))
            return False, (
                f"🎂 محدودیت سنی\n\nاین رویداد برای سن {rng} سال است.\n"
                f"سن شما: {age}"
            ), {"inline_keyboard": [
                [{"text": "🔙 بازگشت", "callback_data": f"uev_{eid}"}]]}

    # 🏙️ شهر
    city_r = (ev.get("restrict_city") or "").strip()
    if city_r:
        allowed = [c.strip() for c in city_r.replace("،", ",").split(",") if c.strip()]
        ucity = (u.get("city") or "").strip()
        if allowed and ucity not in allowed:
            return False, (
                f"🏙️ این رویداد فقط برای ساکنان: {'، '.join(allowed)}\n\n"
                f"شهر ثبت‌شده شما: {ucity or '—'}"
            ), {"inline_keyboard": [
                [{"text": "📝 اصلاح پروفایل", "callback_data": "profile_fill"}],
                [{"text": "🔙 بازگشت", "callback_data": f"uev_{eid}"}]]}

    # 🏆 حداقل امتیاز
    minp = int(ev.get("min_points_required") or 0)
    if minp:
        have = int(u.get("total_points") or 0)
        if have < minp:
            return False, (
                f"🏆 حداقل امتیاز لازم: {minp}\n"
                f"امتیاز شما: {have}\n\n"
                f"با شرکت در رویدادها و دعوت دوستان امتیاز بگیرید."
            ), {"inline_keyboard": [
                [{"text": "🏆 امتیاز من", "callback_data": "u_points"}],
                [{"text": "🔙 بازگشت", "callback_data": f"uev_{eid}"}]]}

    return True, "", None


def register(cid, uid, eid):
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")
    if ev.get("status") == "closed":
        return send(cid, "🔴 ثبت‌نام این رویداد بسته شده است")
    if ev.get("status") != "published":
        return send(cid, "⚠️ این رویداد در دسترس نیست")

    u = get_user(uid)
    if not u:
        return send(cid, "⚠️ ابتدا /start را بزنید")

    # 🚦 بررسی همه شرایط دسترسی (دعوت اجباری، جنسیت، سن، شهر، امتیاز)
    ok_gate, gate_msg, gate_kb = check_eligibility(uid, ev, u)
    if not ok_gate:
        log_access(eid, uid, "register_attempt", False, gate_msg[:60])
        return send_or_edit(cid, gate_msg, gate_kb)

    # نیاز به پروفایل تأییدشده
    if ev.get("require_profile") and u.get("profile_status") != "approved":
        _stmap = {"draft": "تکمیل نشده", "pending": "در انتظار تأیید",
                  "rejected": "نیاز به اصلاح"}
        _st = _stmap.get(u.get("profile_status") or "draft", "تکمیل نشده")
        try:
            from occasions import polite_name as _pn
            _nm = _pn(u)
        except Exception:
            _nm = u.get("first_name") or "دوست"
        _txt = get_setting("msg_profile_needed", "").strip() or (
            "👤 یک قدم تا همراهی\n"
            "━━━━━━━━━━━━━━\n\n"
            "{name} عزیز، برای شرکت در این برنامه لازم است\n"
            "پروفایلتان تکمیل و تأیید شده باشد.\n\n"
            "📊 وضعیت فعلی: {status}\n\n"
            "💚 تکمیلش فقط چند دقیقه وقت می‌برد.")
        _txt = _txt.replace("{name}", _nm).replace("{status}", _st)
        return send_or_edit(cid, _txt, {"inline_keyboard": [
            [{"text": "📝 تکمیل پروفایل", "callback_data": "profile_fill"}],
            [{"text": "🔙 بازگشت", "callback_data": f"uev_{eid}"}]]})

    exist = db_execute(
        "SELECT * FROM event_registrations WHERE event_id=? AND bale_user_id=?",
        (eid, uid), fetch="one")
    if exist and exist.get("status") not in ("cancelled", None):
        _st = exist.get("status")

        # 🔴 فاز ۲۴ — «چرا کاربر وقتی پرداختش کنسل میکنه کلا
        #    ثبت‌نام واسش بسته میشه؟»
        #
        #    ثبت‌نام پرداخت‌نشده روی 'pending' گیر می‌کرد و
        #    کاربر برای همیشه قفل می‌شد. حالا اجازه می‌دهیم
        #    ادامه دهد یا از نو شروع کند.
        if _st == "pending" and not int(exist.get("amount_paid") or 0):
            _left = int(ev.get("price") or 0)
            return send_or_edit(cid, (
                f"⏳ ثبت‌نام نیمه‌تمام شما\n"
                f"━━━━━━━━━━━━━━\n\n"
                f"🎉 {ev['title']}\n\n"
                f"قبلاً شروع کرده بودید ولی پرداخت کامل نشد.\n"
                f"🌱 نگران نباشید — همین حالا می‌توانید ادامه دهید."
            ), {"inline_keyboard": [
                [{"text": "💳 ادامه و پرداخت",
                  "callback_data": f"urepay_{eid}"}],
                [{"text": "🔄 شروع دوباره",
                  "callback_data": f"uregnew_{eid}"}],
                [{"text": "❌ انصراف از ثبت‌نام",
                  "callback_data": f"ucancel_{eid}"}],
                [{"text": "🔙 بازگشت", "callback_data": f"uev_{eid}"}]]})

        return send(cid, f"ℹ️ شما قبلاً ثبت‌نام کرده‌اید\n\n"
                         f"وضعیت: {REG_STATUS.get(_st)}")

    full = is_full(ev)
    if full and not ev.get("allow_waitlist"):
        return send(cid, "🈵 ظرفیت تکمیل شده است")

    # ═══════════════════════════════════════════════════
    # 📝 فاز ۱۶ — اگر رویداد فرم ثبت‌نام دارد، اول فرم پر شود
    #
    # 🔴 باگ بحرانی که رفع شد: فرم به رویداد وصل می‌شد ولی
    #    register() هرگز بازش نمی‌کرد — کاربر فرم را نمی‌دید!
    # ═══════════════════════════════════════════════════
    fid = ev.get("registration_form_id")
    if fid and not full:
        done = db_execute("""SELECT id FROM form_responses
            WHERE form_id=? AND bale_user_id=?
              AND status IN ('completed','confirmed')""",
            (fid, uid), fetch="one")
        if not done:
            frm = db_execute("SELECT * FROM forms WHERE id=?", (fid,),
                             fetch="one")
            nf = db_scalar("SELECT COUNT(*) FROM form_fields WHERE form_id=?",
                           (fid,)) or 0
            if frm and nf:
                send(cid, (
                    f"📝 تکمیل فرم ثبت‌نام\n"
                    f"━━━━━━━━━━━━━━\n\n"
                    f"🎉 {ev['title']}\n\n"
                    f"برای ثبت‌نام، لطفاً {nf} سوال زیر را پاسخ دهید.\n"
                    f"⏱️ حدود {max(1, round(nf * 0.4))} دقیقه"))
                try:
                    import form_fill as _ff
                    return _ff.open_form(cid, uid, fid)
                except Exception as _e:
                    log(f"⚠️ باز کردن فرم رویداد: {_e}")

    is_paid = bool(ev.get("is_paid")) and int(ev.get("price") or 0) > 0
    price = int(ev.get("price") or 0)
    if u.get("is_vip") and ev.get("price_vip"):
        price = int(ev["price_vip"])

    if full:
        status = "waitlist"
    elif is_paid:
        status = "pending"
    elif ev.get("require_approval"):
        status = "pending"
    else:
        status = "confirmed"

    ticket = gen_code("T") if status == "confirmed" and ev.get("has_ticket") else None

    if exist:
        db_execute("""UPDATE event_registrations
            SET status=?, ticket_code=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?""", (status, ticket, exist["id"]))
        rid = exist["id"]
    else:
        rid = db_execute("""INSERT INTO event_registrations
            (event_id, user_id, bale_user_id, status, ticket_code)
            VALUES (?,?,?,?,?)""", (eid, u["id"], uid, status, ticket))

    if not rid:
        return send(cid, "❌ خطا در ثبت‌نام")

    log_action(uid, "event_register", {"event_id": eid, "status": status})

    if status == "waitlist":
        pos = db_scalar(
            "SELECT COUNT(*) FROM event_registrations WHERE event_id=? AND status='waitlist'",
            (eid,))
        return send_or_edit(cid, (
            f"📋 در لیست انتظار ثبت شدید\n\n"
            f"🎉 {ev['title']}\n"
            f"🔢 نوبت شما: {pos}\n\n"
            f"💡 اگر ظرفیت آزاد شود، خبرتان می‌کنیم."
        ), {"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": f"uev_{eid}"}]]})

    if is_paid:
        # 🎁 اگر رویداد کد تخفیف فعال دارد، اول بپرس
        has_disc = db_scalar("""SELECT COUNT(*) FROM event_discount_codes
            WHERE event_id=? AND is_active=1""", (eid,))
        if has_disc:
            set_state(uid, STATE_EV_APPLY_DISC,
                      {"eid": eid, "rid": rid, "price": price}, merge=False)
            from config import money
            _amt = (f"💰 مبلغ: {money(price)}\n\n"
                    if show_price(ev) else "")
            return send(cid, (
                f"🎁 کد تخفیف\n━━━━━━━━━━━━━━\n\n"
                f"{_amt}"
                f"اگر کد تخفیف دارید بنویسید،\n"
                f"وگرنه «⏭️ رد کردن» را بزنید."
            ), {"keyboard": [[{"text": BTN_SKIP}],
                             [{"text": BTN_BACK}, {"text": "🏠 منوی اصلی"}]],
                "resize_keyboard": True})
        from payments import route_payment
        return route_payment(cid, uid, ev, rid, price)

    if ev.get("require_approval"):
        notify_event_admins(ev, (
            f"🔔 درخواست ثبت‌نام جدید\n\n"
            f"🎉 {ev['title']}\n"
            f"👤 {u.get('first_name') or ''} {u.get('last_name') or ''}\n"
            f"📱 {u.get('mobile') or '-'}"
        ), {"inline_keyboard": [
            [{"text": "✅ تأیید", "callback_data": f"regok_{rid}"},
             {"text": "❌ رد", "callback_data": f"regno_{rid}"}]]})
        return send_or_edit(cid, (
            "⏳ درخواست شما ثبت شد\n\n"
            "پس از تأیید ادمین، بلیت برایتان ارسال می‌شود."
        ), {"inline_keyboard": [[{"text": "🔙 بازگشت", "callback_data": f"uev_{eid}"}]]})

    finish_registration(cid, uid, ev, rid)


def finish_registration(cid, uid, ev, rid):
    """تکمیل ثبت‌نام رایگان یا بعد از پرداخت"""
    reg = db_execute("SELECT * FROM event_registrations WHERE id=?", (rid,), fetch="one")
    if not reg or reg.get("status") == "confirmed":
        return

    # 🏅 بررسی امتیاز شرطی
    try:
        import occasions as _oc
        _oc.check_point_rules(uid, "event_register")
    except Exception as _e:
        log(f"⚠️ امتیاز شرطی: {_e}")

    try:
        import club as _cl
        _cl.check_achievements(uid, "invite_friend")
    except Exception as _e:
        log(f"⚠️ دستاورد: {_e}")

    ticket = reg.get("ticket_code")
    if not ticket and ev.get("has_ticket"):
        ticket = gen_code("T")
        db_execute("UPDATE event_registrations SET ticket_code=? WHERE id=?", (ticket, rid))

    db_execute("""UPDATE event_registrations
        SET status='confirmed', updated_at=CURRENT_TIMESTAMP WHERE id=?""", (rid,))

    lines = [
        "🎉 ثبت‌نام شما قطعی شد!",
        "━━━━━━━━━━━━━━",
        "",
        f"📌 {ev['title']}",
    ]
    when = ev.get("start_date") or "-"
    if ev.get("start_time"):
        when += f" ساعت {ev['start_time']}"
    lines.append(f"📅 {when}")

    if ev.get("location_address"):
        lines.append(f"📍 {ev['location_address']}")
    if ev.get("online_link"):
        lines += ["", f"🔗 لینک ورود:\n{ev['online_link']}",
                  "⚠️ این لینک شخصی است، به دیگران ندهید."]
    if ticket:
        lines += ["", f"🎫 کد بلیت شما: {ticket}"]
        if ev.get("has_attendance"):
            lines.append("💡 این کد را در روز برگزاری همراه داشته باشید.")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🎫 رویدادهای من", "callback_data": "u_myevents"}],
        [{"text": "🔙 منوی اصلی", "callback_data": "back_main"}],
    ]})

    u = get_user(uid)
    notify_event_admins(ev, (
        f"✅ ثبت‌نام جدید\n\n"
        f"🎉 {ev['title']}\n"
        f"👤 {(u or {}).get('first_name') or ''} {(u or {}).get('last_name') or ''}\n"
        f"📱 {(u or {}).get('mobile') or '-'}\n"
        f"👥 مجموع: {reg_count(ev['id'], 'confirmed')}"
    ))

    # فرم رضایت‌سنجی بعد از یک عملیات موفق
    try:
        from config import ASK_REVIEW_ENABLED, ASK_REVIEW_DELAY
        if ASK_REVIEW_ENABLED:
            from bale_api import ask_review
            ask_review(uid, ASK_REVIEW_DELAY)
    except Exception:
        pass


def resume_payment(cid, uid, eid):
    """
    💳 ادامهٔ پرداخت ثبت‌نام نیمه‌تمام.

    🎯 «چرا کاربر وقتی پرداختش کنسل میکنه کلا ثبت‌نام واسش
       بسته میشه؟» — حالا فقط ادامه می‌دهد.
    """
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")
    reg = db_execute(
        "SELECT * FROM event_registrations WHERE event_id=? "
        "AND bale_user_id=?", (eid, uid), fetch="one")
    if not reg or reg.get("status") == "cancelled":
        return register(cid, uid, eid)
    if reg.get("status") in ("confirmed", "attended"):
        return send(cid, "✅ ثبت‌نام شما قبلاً تأیید شده 💚")

    left = int(ev.get("price") or 0) - int(reg.get("amount_paid") or 0)
    if left <= 0:
        return finish_registration(cid, uid, ev, reg["id"])

    if ev.get("status") not in ("published", "closed"):
        return send(cid, "⚠️ ثبت‌نام این رویداد باز نیست")

    try:
        import payments as pay
        return pay.route_payment(cid, uid, ev, reg["id"], left)
    except Exception as e:
        log(f"⚠️ ادامه پرداخت: {e}")
        return send(cid, "⚠️ خطا در شروع پرداخت. دوباره تلاش کنید.")


def restart_registration(cid, uid, eid):
    """
    🔄 شروع دوبارهٔ ثبت‌نام — رکورد پرداخت‌نشده پاک می‌شود.

    🛡️ فقط وقتی هیچ پولی پرداخت نشده باشد.
    """
    reg = db_execute(
        "SELECT * FROM event_registrations WHERE event_id=? "
        "AND bale_user_id=?", (eid, uid), fetch="one")
    if reg and int(reg.get("amount_paid") or 0) > 0:
        return send(cid, "⚠️ چون بخشی از مبلغ پرداخت شده، ثبت‌نام "
                         "پاک نمی‌شود.\n\n💡 با پشتیبانی تماس بگیرید 💚")
    if reg:
        db_execute("DELETE FROM transactions WHERE registration_id=? "
                   "AND status='pending'", (reg["id"],))
        db_execute("DELETE FROM event_registrations WHERE id=?",
                   (reg["id"],))
        log_action(uid, "event_reg_restart", {"event_id": eid})
    return register(cid, uid, eid)


def cancel_registration(cid, uid, eid):
    reg = db_execute(
        "SELECT * FROM event_registrations WHERE event_id=? AND bale_user_id=?",
        (eid, uid), fetch="one")
    if not reg or reg.get("status") == "cancelled":
        return send(cid, "ℹ️ ثبت‌نام فعالی ندارید")

    db_execute("""UPDATE event_registrations
        SET status='cancelled', updated_at=CURRENT_TIMESTAMP WHERE id=?""", (reg["id"],))
    log_action(uid, "event_cancel", {"event_id": eid})

    send_or_edit(cid, "❌ ثبت‌نام شما لغو شد", {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": f"uev_{eid}"}]]})

    # ارتقای نفر اول لیست انتظار
    ev = get_event(eid)
    if ev and not is_full(ev):
        nxt = db_execute("""SELECT * FROM event_registrations
            WHERE event_id=? AND status='waitlist' ORDER BY id LIMIT 1""",
            (eid,), fetch="one")
        if nxt and nxt.get("bale_user_id"):
            if ev.get("is_paid"):
                db_execute("UPDATE event_registrations SET status='pending' WHERE id=?",
                           (nxt["id"],))
                send(nxt["bale_user_id"], (
                    f"🎉 ظرفیت آزاد شد!\n\n"
                    f"📌 {ev['title']}\n\n"
                    f"💳 برای قطعی شدن، پرداخت کنید."
                ), {"inline_keyboard": [
                    [{"text": "💳 پرداخت", "callback_data": f"upay_{eid}"}]]})
            else:
                finish_registration(nxt["bale_user_id"], nxt["bale_user_id"], ev, nxt["id"])


def approve_registration(cid, admin_id, rid, ok=True):
    if not _is_admin(admin_id):
        return send(cid, "❌ دسترسی ندارید")
    reg = db_execute("SELECT * FROM event_registrations WHERE id=?", (rid,), fetch="one")
    if not reg:
        return send(cid, "❌ یافت نشد")
    ev = get_event(reg["event_id"])
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    if ok:
        send(cid, "✅ تأیید شد")
        finish_registration(reg["bale_user_id"], reg["bale_user_id"], ev, rid)
    else:
        db_execute("UPDATE event_registrations SET status='cancelled' WHERE id=?", (rid,))
        send(cid, "❌ رد شد")
        if reg.get("bale_user_id"):
            send(reg["bale_user_id"],
                 f"❌ درخواست ثبت‌نام شما در «{ev['title']}» تأیید نشد.")


# ==================== پرداخت ====================
def start_payment(cid, uid, ev, rid, amount):
    """ارسال درخواست پول کیف‌پولی"""
    if not PAYMENT_ENABLED:
        return send(cid, (
            "⚠️ سیستم پرداخت فعال نیست\n\n"
            "لطفاً با پشتیبانی تماس بگیرید."
        ))

    # 🛡️ محافظت: بررسی مبلغ قبل از ارسال فاکتور واقعی
    okamt, amsg = check_amount(amount)
    if not okamt:
        log(f"⛔ مبلغ رد شد: {amount} برای رویداد {ev['id']}")
        send(cid, f"⛔ خطا در مبلغ\n\n{amsg}")
        notify_event_admins(ev, (
            f"⛔ فاکتور ارسال نشد — مبلغ نامعتبر\n\n"
            f"🎉 {ev['title']}\n"
            f"💰 مبلغ: {fmt_money(amount)} {CURRENCY_LABEL}\n"
            f"📄 {amsg}"
        ))
        return

    # 🛡️ فاز ۱۸-ب — هشدار خاموش کردن فیلترشکن قبل از فاکتور بله
    try:
        from payments import send_vpn_warning
        send_vpn_warning(cid, "bale_wallet")
    except Exception as _e:
        log(f"⚠️ هشدار فیلترشکن: {_e}")

    import uuid as _uu
    payload = (f"ev{ev['id']}u{uid}r{rid}t{int(time.time())}"
               f"x{_uu.uuid4().hex[:6]}")

    db_execute("""INSERT INTO transactions
        (bale_user_id, event_id, registration_id, payload, amount, status)
        VALUES (?,?,?,?,?,'pending')""",
        (uid, ev["id"], rid, payload, amount))

    db_execute("UPDATE event_registrations SET payment_payload=? WHERE id=?",
               (payload, rid))

    desc = (ev.get("description") or ev["title"])[:250]
    res = send_invoice(
        cid,
        title=ev["title"][:32],
        description=desc,
        payload=payload,
        provider_token=PAYMENT_PROVIDER_TOKEN,
        prices=[{"label": f"ثبت‌نام {ev['title']}"[:32], "amount": int(amount)}],
    )

    if res.get("ok"):
        note = ("\n\n🧪 حالت آزمایشی — پولی جابه‌جا نمی‌شود."
                if PAYMENT_TEST_MODE else
                "\n\n💳 پرداخت از کیف پول بله شما انجام می‌شود.")
        send(cid, (
            f"💳 درخواست پرداخت ارسال شد\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"🎉 {ev['title']}\n"
            f"💰 مبلغ: {fmt_money(amount)} {CURRENCY_LABEL}\n"
            f"⏳ پس از پرداخت، بلیت شما صادر می‌شود.{note}"
            f"{_vpn_hint()}"
        ))
    else:
        log(f"❌ sendInvoice ناموفق: {res.get('description')}")
        send(cid, (
            "❌ خطا در ایجاد درخواست پرداخت\n\n"
            "لطفاً بعداً تلاش کنید یا با پشتیبانی تماس بگیرید."
        ))


def handle_pre_checkout(pcq):
    """
    ⚠️ باید ظرف ۱۰ ثانیه پاسخ داده شود وگرنه پرداخت لغو می‌شود.
    اینجا بررسی می‌کنیم: تراکنش معتبر است؟ ظرفیت هست؟
    """
    qid = pcq.get("id")
    payload = pcq.get("invoice_payload") or ""
    total = int(pcq.get("total_amount") or 0)
    uid = (pcq.get("from") or {}).get("id")

    # 🔗 فاز ۱۷ — لینک پرداخت غیرمتمرکز
    if payload.startswith("pl"):
        p = db_execute("SELECT * FROM paylink_payments WHERE payload=?",
                       (payload,), fetch="one")
        if not p:
            answer_pre_checkout_query(qid, False, "لینک پرداخت نامعتبر است")
            return
        if p.get("status") == "paid":
            answer_pre_checkout_query(qid, False, "این پرداخت قبلاً انجام شده")
            return
        answer_pre_checkout_query(qid, True)
        return

    tx = db_execute("SELECT * FROM transactions WHERE payload=?", (payload,), fetch="one")
    if not tx:
        answer_pre_checkout_query(qid, False, "درخواست پرداخت نامعتبر است")
        log(f"⛔ pre_checkout رد شد: payload ناشناخته {payload}")
        return

    if tx.get("status") == "paid":
        answer_pre_checkout_query(qid, False, "این پرداخت قبلاً انجام شده است")
        return

    ev = get_event(tx.get("event_id"))
    if not ev:
        answer_pre_checkout_query(qid, False, "رویداد یافت نشد")
        return

    if ev.get("status") not in ("published", "closed"):
        answer_pre_checkout_query(qid, False, "ثبت‌نام این رویداد بسته شده است")
        return

    if total and int(tx.get("amount") or 0) and total != int(tx["amount"]):
        answer_pre_checkout_query(qid, False, "مبلغ پرداخت با صورتحساب مطابقت ندارد")
        log(f"⛔ مبلغ نامطابق: {total} != {tx['amount']}")
        return

    answer_pre_checkout_query(qid, True)
    log(f"✅ pre_checkout تأیید شد: {payload} ({total} ریال)")


def handle_successful_payment(message):
    """پرداخت موفق — صدور بلیت"""
    sp = message.get("successful_payment") or {}
    uid = (message.get("from") or {}).get("id")
    cid = (message.get("chat") or {}).get("id") or uid

    payload = sp.get("invoice_payload") or ""
    amount = int(sp.get("total_amount") or 0)
    charge_id = sp.get("telegram_payment_charge_id") or ""
    provider_charge = sp.get("provider_payment_charge_id") or ""

    # 🔗 فاز ۱۷ — اگر پرداخت مال «لینک غیرمتمرکز» بود
    if payload.startswith("pl"):
        try:
            import paylink as _pl
            if _pl.mark_paid(payload, charge_id or provider_charge):
                return
        except Exception as e:
            log(f"⚠️ ثبت پرداخت لینک: {e}")

    tx = db_execute("SELECT * FROM transactions WHERE payload=?", (payload,), fetch="one")
    if not tx:
        log(f"⚠️ پرداخت با payload ناشناخته: {payload}")
        return send(cid, (
            "✅ پرداخت شما دریافت شد.\n\n"
            "⚠️ در ثبت خودکار مشکلی پیش آمد — با پشتیبانی تماس بگیرید.\n"
            f"شماره پیگیری: {provider_charge or charge_id}"
        ))

    if tx.get("status") == "paid":
        return send(cid, "ℹ️ این پرداخت قبلاً ثبت شده است")

    db_execute("""UPDATE transactions
        SET status='paid', transaction_id=?, provider_charge_id=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?""", (charge_id, provider_charge, tx["id"]))

    rid = tx.get("registration_id")
    frid = tx.get("form_response_id")

    # 💠 فاز ۱۸-الف — اگر این پرداخت یک «قسط» بود
    part_no = tx.get("installment_no")
    if part_no:
        try:
            import payplan as _pp
            _pp.mark_part_paid(int(part_no))
            left_n, left_amt = _pp.remaining(uid, rid, frid)
            if left_n:
                send(cid, (
                    f"✅ قسط شما با موفقیت پرداخت شد\n"
                    f"━━━━━━━━━━━━━━\n\n"
                    f"💰 مبلغ: {fmt_money(amount)} {CURRENCY_LABEL}\n"
                    f"🧾 پیگیری: {provider_charge or charge_id}\n\n"
                    f"⏳ {left_n} قسط باقی مانده "
                    f"({fmt_money(left_amt)} {CURRENCY_LABEL})\n"
                    f"🔔 به‌موقع یادآوری می‌کنیم 💚"))
                log_action(uid, "installment_paid",
                           {"part": part_no, "amount": amount})
                return
            # آخرین قسط → مسیر عادی ادامه پیدا می‌کند
            send(cid, "🎉 تمام اقساط شما تسویه شد! سپاس از همراهی‌تان 💚")
        except Exception as e:
            log(f"⚠️ بستن قسط: {e}")

    # 📝 فاز ۱۸-الف — پرداخت مربوط به فرم‌ساز
    #    🔴 قبلاً فقط event_registrations به‌روز می‌شد؛ پاسخ فرم برای
    #    همیشه در حالت pending_payment گیر می‌کرد و کاربر هرگز کد
    #    پیگیری/گواهینامه نمی‌گرفت.
    if frid:
        db_execute("""UPDATE form_responses
            SET amount_paid=?, payment_status='paid', transaction_id=?
            WHERE id=?""", (amount, charge_id, frid))
        log_action(uid, "payment_success",
                   {"amount": amount, "form_response_id": frid})
        send(cid, (
            f"✅ پرداخت موفق\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"💰 مبلغ: {fmt_money(amount)} {CURRENCY_LABEL}\n"
            f"🧾 شماره پیگیری: {provider_charge or charge_id}\n\n"
            f"⏳ در حال نهایی کردن ثبت شما..."
        ))
        try:
            import form_fill as _ff
            fr = db_execute("SELECT * FROM form_responses WHERE id=?",
                            (frid,), fetch="one") or {}
            return _ff.finalize(cid, uid, frid, fr.get("score"),
                                fr.get("max_score"))
        except Exception as e:
            log(f"⚠️ نهایی‌سازی فرم پس از پرداخت: {e}")
            return send(cid, "✅ پرداخت ثبت شد. با پشتیبانی تماس بگیرید.")

    if rid:
        db_execute("""UPDATE event_registrations
            SET amount_paid=?, transaction_id=?, paid_at=CURRENT_TIMESTAMP
            WHERE id=?""", (amount, charge_id, rid))

    ev = get_event(tx.get("event_id"))
    log_action(uid, "payment_success", {"amount": amount, "event_id": tx.get("event_id")})

    send(cid, (
        f"✅ پرداخت موفق\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"💰 مبلغ: {fmt_money(amount)} {CURRENCY_LABEL}\n"
        f"🧾 شماره پیگیری: {provider_charge or charge_id}\n\n"
        f"⏳ در حال صدور بلیت..."
    ))

    if ev and rid:
        finish_registration(cid, uid, ev, rid)


def check_transaction(cid, uid, tx_id):
    """استعلام دستی تراکنش"""
    res = inquire_transaction(tx_id)
    if not res.get("ok"):
        return send(cid, f"❌ استعلام ناموفق: {res.get('description')}")
    r = res.get("result") or {}
    labels = {"pending": "⏳ در حال پردازش", "paid": "✅ پرداخت شده",
              "failed": "❌ ناموفق", "rejected": "🚫 رد شده"}
    send(cid, (
        f"🧾 وضعیت تراکنش\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🆔 {r.get('id')}\n"
        f"📌 {labels.get(r.get('status'), r.get('status'))}\n"
        f"💰 {fmt_money(r.get('amount'))} {CURRENCY_LABEL}\n"
        f"👤 {r.get('userID')}"
    ))


# ==================== رویدادهای من (کاربر) ====================
def show_my_events(cid, uid):
    rows = db_execute("""
        SELECT r.*, e.title, e.event_type, e.start_date, e.start_time,
               e.online_link, e.location_address, e.status AS ev_status
        FROM event_registrations r
        JOIN events e ON e.id = r.event_id
        WHERE r.bale_user_id=? AND r.status!='cancelled'
        ORDER BY r.id DESC LIMIT 20
    """, (uid,), fetch="all") or []

    if not rows:
        return send_or_edit(cid, (
            "🎫 رویدادهای من\n"
            "━━━━━━━━━━━━━━\n\n"
            "📭 هنوز در رویدادی ثبت‌نام نکرده‌اید."
        ), {"inline_keyboard": [
            [{"text": "🎉 مشاهده رویدادها", "callback_data": "u_events"}],
            [{"text": "🔙 منوی اصلی", "callback_data": "back_main"}]]})

    lines = [f"🎫 رویدادهای من ({len(rows)})", "━━━━━━━━━━━━━━", ""]
    btns = []
    for r in rows:
        t = EVENT_TYPES.get(r.get("event_type") or "meeting", EVENT_TYPES["meeting"])
        lines += [
            f"{t['icon']} {r['title']}",
            f"├── 📅 {r.get('start_date') or '-'}"
            + (f" ساعت {r['start_time']}" if r.get("start_time") else ""),
            f"├── {REG_STATUS.get(r.get('status'), r.get('status'))}",
        ]
        if r.get("ticket_code"):
            lines.append(f"└── 🎫 {r['ticket_code']}")
        else:
            lines.append("└── —")
        lines.append("")
        btns.append([{"text": f"{t['icon']} {r['title']}"[:45],
                      "callback_data": f"uev_{r['event_id']}"}])

    btns.append([{"text": "🔙 منوی اصلی", "callback_data": "back_main"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_ticket(cid, uid, eid):
    reg = db_execute("""
        SELECT r.*, e.title, e.start_date, e.start_time, e.location_address,
               e.online_link, e.event_type, e.organizer
        FROM event_registrations r JOIN events e ON e.id=r.event_id
        WHERE r.event_id=? AND r.bale_user_id=?
    """, (eid, uid), fetch="one")

    if not reg or reg.get("status") != "confirmed":
        return send(cid, "❌ بلیت فعالی برای این رویداد ندارید")

    u = get_user(uid)
    name = f"{(u or {}).get('first_name') or ''} {(u or {}).get('last_name') or ''}".strip()
    t = EVENT_TYPES.get(reg.get("event_type") or "meeting", EVENT_TYPES["meeting"])

    # 🎫 فاز ۲۰ — متن بلیط از تنظیمات ادمین ساخته می‌شود
    try:
        import certgen as _cg
        body = _cg.build_ticket_text(reg, u, reg)
        lines = body.split("\n")
    except Exception as _e:
        log(f"⚠️ ساخت بلیط از تنظیمات: {_e}")
        lines = [
            "🎫 ━━━━ بلیت ورود ━━━━ 🎫",
            "",
            f"{t['icon']} {reg['title']}",
            "",
            f"👤 نام: {name or '-'}",
            f"📱 موبایل: {(u or {}).get('mobile') or '-'}",
            f"🎟️ کد بلیت: {reg.get('ticket_code') or '-'}",
            "",
            f"📅 تاریخ: {reg.get('start_date') or '-'}",
        ]
        if reg.get("start_time"):
            lines.append(f"🕐 ساعت: {reg['start_time']}")
        if reg.get("location_address"):
            lines.append(f"📍 مکان: {reg['location_address']}")
        if reg.get("online_link"):
            lines += ["", f"🔗 لینک ورود:\n{reg['online_link']}"]
        if reg.get("amount_paid"):
            lines.append(f"\n💰 پرداخت شده: {fmt_money(reg['amount_paid'])} {CURRENCY_LABEL}")
        if reg.get("organizer"):
            lines.append(f"👥 برگزارکننده: {reg['organizer']}")
        lines += ["", "━━━━━━━━━━━━━━━━━━━", "💡 این بلیت شخصی است."]

    kb = None
    if reg.get("ticket_code"):
        kb = {"inline_keyboard": [
            [{"text": "📋 کپی کد بلیت", "copy_text": {"text": reg["ticket_code"]}}],
            [{"text": "🔙 بازگشت", "callback_data": f"uev_{eid}"}],
        ]}
    send(cid, "\n".join(lines), kb)


def register_by_code(cid, uid, code):
    """
    ثبت‌نام با کد دعوت.

    دو منبع پشتیبانی می‌شود:
      • invite_code خود رویداد (کد ساده)
      • جدول event_invite_codes (کدهای چندگانه با سقف مصرف و انقضا)
    """
    code = (code or "").strip().upper()
    clear_state(uid)

    ev = db_execute(
        "SELECT * FROM events WHERE invite_code=? AND status='published'",
        (code,), fetch="one")

    if not ev:
        row = db_execute("""SELECT c.*, e.id AS eid FROM event_invite_codes c
            JOIN events e ON e.id=c.event_id
            WHERE c.code=? AND c.is_active=1 AND e.status='published'""",
            (code,), fetch="one")
        if row:
            mx = int(row.get("max_uses") or 0)
            used = int(row.get("current_uses") or 0)
            if mx and used >= mx:
                log_access(row["eid"], uid, "invite_code", False, "سقف مصرف")
                return send_or_edit(cid, (
                    "🚫 این کد دعوت به سقف استفاده رسیده است."
                ), {"inline_keyboard": [
                    [{"text": "🔙 بازگشت", "callback_data": "u_events"}]]})
            exp = (row.get("expires_at") or "").strip()
            if exp:
                from forms import jdt_key, jnow
                k1, k2 = jdt_key(exp), jdt_key(jnow())
                if k1 and k2 and k2 > k1:
                    log_access(row["eid"], uid, "invite_code", False, "منقضی")
                    return send_or_edit(cid, "⛔ این کد دعوت منقضی شده است.",
                                        {"inline_keyboard": [
                                            [{"text": "🔙 بازگشت",
                                              "callback_data": "u_events"}]]})
            db_execute("UPDATE event_invite_codes SET current_uses="
                       "COALESCE(current_uses,0)+1 WHERE id=?", (row["id"],))
            ev = get_event(row["eid"])
            log_access(row["eid"], uid, "invite_code", True)

    if not ev:
        return send_or_edit(cid, "❌ کد دعوت نامعتبر است", {"inline_keyboard": [
            [{"text": "🔙 بازگشت", "callback_data": "u_events"}]]})
    send(cid, "✅ کد معتبر است!")
    show_event_user(cid, uid, ev["id"])


# ==================== اطلاع‌رسانی ====================
def notify_event_admins(ev, text, kb=None):
    rows = db_execute(
        "SELECT DISTINCT bale_user_id FROM users WHERE is_admin=1 AND bale_user_id IS NOT NULL",
        fetch="all") or []
    ids = {r["bale_user_id"] for r in rows if r.get("bale_user_id")}
    if SUPER_ADMIN_ID:
        ids.add(SUPER_ADMIN_ID)
    for aid in ids:
        send(aid, text, kb)


def notify_event(cid, uid, eid):
    """اطلاع‌رسانی رویداد به همه کاربران"""
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")

    total = db_scalar(
        "SELECT COUNT(*) FROM users WHERE bale_user_id IS NOT NULL "
        "AND is_authenticated=1 AND COALESCE(is_blocked,0)=0")

    send_or_edit(cid, (
        f"📢 اطلاع‌رسانی رویداد\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🎉 {ev['title']}\n"
        f"👥 گیرندگان: {total} کاربر\n\n"
        f"⏳ زمان تقریبی: {max(1, total // 20)} ثانیه\n\n"
        f"شروع شود؟"
    ), {"inline_keyboard": [
        [{"text": "📢 بله، ارسال کن", "callback_data": f"ev_notifygo_{eid}"}],
        [{"text": "❌ انصراف", "callback_data": f"ev_view_{eid}"}],
    ]})


def do_notify_event(cid, uid, eid):
    from config import BROADCAST_RATE
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")

    users = db_execute(
        "SELECT bale_user_id FROM users WHERE bale_user_id IS NOT NULL "
        "AND is_authenticated=1 AND COALESCE(is_blocked,0)=0", fetch="all") or []

    text = "📢 رویداد جدید!\n━━━━━━━━━━━━━━\n\n" + event_full_text(ev, for_admin=False)
    kb = {"inline_keyboard": [
        [{"text": "🎫 مشاهده و ثبت‌نام", "callback_data": f"uev_{eid}"}]]}

    send(cid, f"⏳ در حال ارسال به {len(users)} نفر...")

    ok = fail = 0
    delay = 1.0 / max(1, BROADCAST_RATE)
    poster = ev.get("poster") if ev.get("poster") and Path(ev["poster"]).exists() else None

    for i, r in enumerate(users, 1):
        target = r.get("bale_user_id")
        if not target:
            continue
        try:
            if poster:
                send_photo(target, poster)
            res = send(target, text, kb)
            if res.get("ok"):
                ok += 1
            else:
                fail += 1
        except Exception:
            fail += 1
        time.sleep(delay)
        if i % 100 == 0:
            send(cid, f"📊 {i}/{len(users)} — موفق {ok}")

    db_execute("UPDATE events SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (eid,))
    log_action(uid, "event_broadcast", {"event_id": eid, "ok": ok, "fail": fail})

    send(cid, (
        f"✅ اطلاع‌رسانی تمام شد\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"├── ✅ موفق: {ok}\n"
        f"└── ❌ ناموفق: {fail}"
    ), {"inline_keyboard": [[{"text": "🔙 رویداد", "callback_data": f"ev_view_{eid}"}]]})


# ==================== لیست ثبت‌نام‌ها و گزارش ====================
def show_registrations(cid, uid, eid, page=0):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")

    total = reg_count(eid)
    if total == 0:
        return send_or_edit(cid, "📭 هنوز کسی ثبت‌نام نکرده", {"inline_keyboard": [
            [{"text": "🔙 بازگشت", "callback_data": f"ev_view_{eid}"}]]})

    per = 8
    pages = max(1, (total + per - 1) // per)
    page = max(0, min(int(page or 0), pages - 1))

    rows = db_execute("""
        SELECT r.*, u.first_name, u.last_name, u.mobile
        FROM event_registrations r LEFT JOIN users u ON u.id=r.user_id
        WHERE r.event_id=? AND r.status!='cancelled'
        ORDER BY r.id DESC LIMIT ? OFFSET ?
    """, (eid, per, page * per), fetch="all") or []

    lines = [f"👥 ثبت‌نام‌های «{ev['title']}»", f"📊 مجموع: {total}", "━━━━━━━━━━━━━━", ""]
    for i, r in enumerate(rows, start=page * per + 1):
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or "بدون نام"
        lines.append(f"{i}. {nm}")
        lines.append(f"   📱 {r.get('mobile') or '-'}")
        lines.append(f"   {REG_STATUS.get(r.get('status'), r.get('status'))}")
        if r.get("ticket_code"):
            lines.append(f"   🎫 {r['ticket_code']}")
        if r.get("amount_paid"):
            lines.append(f"   💰 {fmt_money(r['amount_paid'])}")
        lines.append("")

    btns = []
    nav = []
    if page > 0:
        nav.append({"text": "◀️", "callback_data": f"ev_regs_{eid}_{page-1}"})
    nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
    if page < pages - 1:
        nav.append({"text": "▶️", "callback_data": f"ev_regs_{eid}_{page+1}"})
    btns.append(nav)
    btns.append([{"text": "📤 خروجی اکسل", "callback_data": f"ev_export_{eid}"}])
    btns.append([{"text": "🔙 رویداد", "callback_data": f"ev_view_{eid}"}])

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def event_report(cid, uid, eid):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")

    def c(st):
        return db_scalar(
            "SELECT COUNT(*) FROM event_registrations WHERE event_id=? AND status=?",
            (eid, st))

    confirmed = c("confirmed")
    pending = c("pending")
    cancelled = c("cancelled")
    waitlist = c("waitlist")
    attended = db_scalar(
        "SELECT COUNT(*) FROM event_registrations WHERE event_id=? AND attended=1", (eid,))
    income = db_scalar(
        "SELECT COALESCE(SUM(amount_paid),0) FROM event_registrations WHERE event_id=?", (eid,))

    male = db_scalar("""SELECT COUNT(*) FROM event_registrations r
        JOIN users u ON u.id=r.user_id WHERE r.event_id=? AND u.gender='مرد'
        AND r.status!='cancelled'""", (eid,))
    female = db_scalar("""SELECT COUNT(*) FROM event_registrations r
        JOIN users u ON u.id=r.user_id WHERE r.event_id=? AND u.gender='زن'
        AND r.status!='cancelled'""", (eid,))

    cities = db_execute("""SELECT u.city, COUNT(*) AS n FROM event_registrations r
        JOIN users u ON u.id=r.user_id
        WHERE r.event_id=? AND r.status!='cancelled' AND u.city IS NOT NULL AND u.city!=''
        GROUP BY u.city ORDER BY n DESC LIMIT 5""", (eid,), fetch="all") or []

    cap = int(ev.get("capacity") or 0)
    fill = f"{confirmed * 100 // cap}%" if cap else "نامحدود"
    att_rate = f"{attended * 100 // confirmed}%" if confirmed else "-"

    lines = [
        f"📊 گزارش «{ev['title']}»",
        "━━━━━━━━━━━━━━",
        "",
        "👥 ثبت‌نام:",
        f"├── ✅ تأیید شده: {confirmed}",
        f"├── ⏳ در انتظار: {pending}",
        f"├── 📋 لیست انتظار: {waitlist}",
        f"├── ❌ لغو شده: {cancelled}",
        f"└── 📈 پر شدن ظرفیت: {fill}",
        "",
        "✋ حضور:",
        f"├── 🎯 حاضر: {attended}",
        f"└── 📊 نرخ حضور: {att_rate}",
        "",
        "💰 مالی:",
        f"└── درآمد: {fmt_money(income)} {CURRENCY_LABEL}",
        "",
        "👤 جنسیت:",
        f"├── 👨 مرد: {male}",
        f"└── 👩 زن: {female}",
    ]
    if cities:
        lines += ["", "🏙️ شهرهای برتر:"]
        for i, r in enumerate(cities):
            mark = "└──" if i == len(cities) - 1 else "├──"
            lines.append(f"{mark} {r['city']}: {r['n']}")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "📤 خروجی اکسل", "callback_data": f"ev_export_{eid}"}],
        [{"text": "🔙 رویداد", "callback_data": f"ev_view_{eid}"}],
    ]})


def export_registrations(cid, uid, eid):
    if not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    try:
        import openpyxl
        from openpyxl.styles import Font
    except ImportError:
        return send(cid, "❌ openpyxl نصب نیست:\npy -m pip install openpyxl")

    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")

    rows = db_execute("""
        SELECT r.*, u.first_name, u.last_name, u.mobile, u.national_id,
               u.gender, u.city, u.province, u.email, u.birth_date
        FROM event_registrations r LEFT JOIN users u ON u.id=r.user_id
        WHERE r.event_id=? ORDER BY r.id
    """, (eid,), fetch="all") or []

    if not rows:
        return send(cid, "📭 داده‌ای برای خروجی نیست")

    send(cid, "⏳ در حال ساخت فایل...")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ثبت‌نام‌ها"
    ws.sheet_view.rightToLeft = True

    heads = ["ردیف", "نام", "نام خانوادگی", "موبایل", "کد ملی", "جنسیت",
             "تاریخ تولد", "استان", "شهر", "ایمیل", "وضعیت", "کد بلیت",
             "مبلغ پرداختی", "شماره پیگیری", "حاضر", "تاریخ ثبت‌نام"]
    ws.append(heads)
    for c in ws[1]:
        c.font = Font(bold=True)

    for i, r in enumerate(rows, 1):
        ws.append([
            i, r.get("first_name") or "", r.get("last_name") or "",
            r.get("mobile") or "", r.get("national_id") or "",
            r.get("gender") or "", r.get("birth_date") or "",
            r.get("province") or "", r.get("city") or "", r.get("email") or "",
            REG_STATUS.get(r.get("status"), r.get("status") or ""),
            r.get("ticket_code") or "", r.get("amount_paid") or 0,
            r.get("transaction_id") or "",
            "بله" if r.get("attended") else "خیر",
            r.get("created_at") or "",
        ])

    for i, h in enumerate(heads, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = max(12, len(h) + 6)
    ws.freeze_panes = "A2"

    from config import IMPORT_DIR
    Path(IMPORT_DIR).mkdir(parents=True, exist_ok=True)
    safe = "".join(ch for ch in ev["title"] if ch.isalnum() or ch in " -_")[:30]
    out = Path(IMPORT_DIR) / f"event_{eid}_{safe}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    try:
        wb.save(out)
    except Exception as e:
        return send(cid, f"❌ خطا: {user_error_message(e)}")

    from bale_api import send_document
    r = send_document(cid, str(out), f"📤 ثبت‌نام‌های «{ev['title']}» ({len(rows)} نفر)")
    if not r.get("ok"):
        send(cid, f"⚠️ ارسال ناموفق. فایل در سرور:\n{out}")


def handle_apply_discount(message):
    """کاربر کد تخفیف را وارد می‌کند (یا رد می‌کند)"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    d = get_state_data(uid)
    eid, rid = d.get("eid"), d.get("rid")
    price = int(d.get("price") or 0)
    ev = get_event(eid)
    if not ev:
        clear_state(uid)
        return send(cid, "❌ رویداد یافت نشد", kb_remove())

    from payments import route_payment
    from config import money

    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_event_user(cid, uid, eid)

    if text in (BTN_SKIP, "⏭️ رد کردن"):
        clear_state(uid)
        send(cid, "⏭️ بدون کد تخفیف", kb_remove())
        return route_payment(cid, uid, ev, rid, price)

    ok, final, msg, did = apply_discount(text, eid, uid, price)
    if not ok:
        return send(cid, f"❌ {msg}\n\nدوباره بنویسید یا «⏭️ رد کردن» را بزنید:")

    cut = price - final
    record_discount_use(did, eid, rid, uid, price, cut, final)
    db_execute("UPDATE event_registrations SET amount_paid=? WHERE id=?",
               (final, rid))
    clear_state(uid)
    send(cid, (
        f"✅ {msg}\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"💰 مبلغ اولیه: {money(price)}\n"
        f"🎁 تخفیف: {money(cut)}\n"
        f"💳 مبلغ نهایی: {money(final)}"
    ), kb_remove())

    if final <= 0:
        return finish_registration(cid, uid, ev, rid)
    return route_payment(cid, uid, ev, rid, final)
