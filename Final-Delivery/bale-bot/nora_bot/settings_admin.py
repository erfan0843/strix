"""
تنظیمات ادمین — متن‌های داینامیک، OTP، پرداخت
(فاز ۵ — طبق درخواست: همه متن‌ها از پنل ادمین قابل تغییر)
"""
from config import (
    SUPER_ADMIN_ID, SAFIR_ENABLED, SAFIR_BOT_ID, SAFIR_API_KEY,
    MAIN_BOT_ID, PAYMENT_ENABLED, PAYMENT_TEST_MODE,
    PAYMENT_PROVIDER_TOKEN, AUTO_REACT_ENABLED, AUTO_REACT_EMOJI,
    CURRENCY_LABEL,
)
from database import db_execute, get_setting, set_setting, clear_settings_cache, log
from auth import (
    set_state, get_state_data, clear_state, normalize_mobile,
    test_safir_connection, generate_otp, save_otp, send_otp_via_safir,
    is_admin as _is_admin,
)
from bale_api import send, send_or_edit, kb_cancel, kb_remove, kb_settings, BTN_BACK
import jalali as _jd

STATE_EDIT_TEXT = "edit_text"
STATE_TEST_OTP = "test_otp"


# متن‌های قابل ویرایش — دسته‌بندی شده
EDITABLE_TEXTS = [
    ("msg_welcome",          "👋 پیام خوش‌آمد",           "شروع"),
    ("msg_auth",             "🔐 پیام احراز هویت",        "شروع"),
    ("msg_force_join",       "🔗 پیام عضویت اجباری",      "شروع"),
    ("msg_profile_intro",    "📝 پیام تکمیل پروفایل",     "پروفایل"),
    ("msg_profile_approved", "✅ پیام تأیید پروفایل",     "پروفایل"),
    ("msg_profile_rejected", "❌ پیام رد پروفایل",        "پروفایل"),
    ("msg_events_empty",     "📭 پیام نبود رویداد",       "رویداد"),
    ("msg_register_ok",      "🎫 پیام ثبت‌نام موفق",      "رویداد"),
    ("msg_payment_ok",       "💳 پیام پرداخت موفق",       "رویداد"),
    ("msg_support",          "💬 متن پشتیبانی",           "عمومی"),
    ("msg_about",            "ℹ️ متن درباره ما",          "عمومی"),
    ("msg_faq",              "❓ سوالات متداول",          "عمومی"),
    ("msg_referral",         "👥 متن دعوت دوستان",        "عمومی"),
    ("msg_blocked",          "🚫 پیام کاربر مسدود",       "عمومی"),
    ("msg_error",            "⚠️ پیام خطای عمومی",        "عمومی"),
    # ═══════════ 🆕 فاز ۱۷-ج ═══════════
    ("msg_otp_sent",         "🔢 پیام ارسال کد یکبار مصرف", "شروع"),
    ("msg_otp_hint",         "💡 راهنمای دریافت کد",        "شروع"),
    ("msg_invite_required",  "🤝 پیام دعوت اجباری رویداد",  "رویداد"),
    ("msg_event_paid_hidden", "💳 پیام رویداد هزینه‌دار (بدون عدد)",
     "رویداد"),
    ("msg_profile_needed",   "👤 پیام نیاز به پروفایل",     "پروفایل"),
]


def _guard(cid, uid):
    if not _is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    return True


def show_settings(cid, uid):
    if not _guard(cid, uid):
        return
    # 🔴 فاز ۱۳: رسیدهای در انتظار روی دکمه پرداخت نشان داده می‌شود
    pend = 0
    try:
        pend = db_execute("SELECT COUNT(*) c FROM payment_receipts "
                          "WHERE status='pending'", fetch="one")["c"] or 0
    except Exception:
        pend = 0
    send_or_edit(cid, (
        "⚙️ تنظیمات ربات\n"
        "━━━━━━━━━━━━━━\n\n"
        "از این بخش می‌توانید همه‌چیز را بدون تغییر کد تنظیم کنید."
    ), kb_settings(uid=uid, pending_pay=pend))


# ==================== متن‌ها ====================
def show_texts(cid, uid, category=None):
    if not _guard(cid, uid):
        return

    cats = []
    for _, _, c in EDITABLE_TEXTS:
        if c not in cats:
            cats.append(c)

    if not category:
        btns = [[{"text": f"📂 {c}", "callback_data": f"txtcat_{i}"}]
                for i, c in enumerate(cats)]
        btns.append([{"text": "🔙 تنظیمات", "callback_data": "admin_settings"}])
        return send_or_edit(cid, (
            "📝 مدیریت متن‌های ربات\n"
            "━━━━━━━━━━━━━━\n\n"
            "همه پیام‌های ربات از اینجا قابل تغییر است.\n"
            "یک دسته را انتخاب کنید:"
        ), {"inline_keyboard": btns})

    items = [(k, t) for k, t, c in EDITABLE_TEXTS if c == category]
    lines = [f"📂 {category}", "━━━━━━━━━━━━━━", ""]
    btns = []
    for k, t in items:
        cur = get_setting(k, "")
        preview = (cur[:40] + "…") if len(cur) > 40 else (cur or "— خالی —")
        lines += [f"{t}", f"└── {preview}", ""]
        btns.append([{"text": f"✏️ {t}", "callback_data": f"txted_{k}"}])
    btns.append([{"text": "🔙 دسته‌ها", "callback_data": "set_texts"}])

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_edit_text(cid, uid, key):
    if not _guard(cid, uid):
        return
    title = next((t for k, t, _ in EDITABLE_TEXTS if k == key), key)
    cur = get_setting(key, "")

    set_state(uid, STATE_EDIT_TEXT, {"key": key}, merge=False)
    send(cid, (
        f"✏️ ویرایش: {title}\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"📄 متن فعلی:\n{cur or '— خالی —'}\n\n"
        f"📝 متن جدید را بفرستید:\n\n"
        f"💡 متغیرهای قابل استفاده:\n"
        f"{{name}} = نام کاربر\n"
        f"{{bot}} = نام ربات\n"
        f"{{org}} = نام سازمان"
    ), kb_cancel())


def handle_edit_text(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    if text == BTN_BACK:
        clear_state(uid)
        return show_texts(cid, uid)

    data = get_state_data(uid)
    key = data.get("key")
    clear_state(uid)

    if not key:
        return send(cid, "⚠️ خطا — دوباره تلاش کنید", kb_remove())
    if not text:
        return send(cid, "⚠️ متن خالی است", kb_remove())

    title = next((t for k, t, _ in EDITABLE_TEXTS if k == key), key)
    set_setting(key, text[:3000], title, "messages", uid)
    clear_settings_cache()

    send(cid, (
        f"✅ ذخیره شد\n\n"
        f"📝 {title}\n\n"
        f"متن جدید:\n{text[:300]}"
    ), kb_remove())
    show_texts(cid, uid)


def render_text(key, default="", **kw):
    """جایگزینی متغیرها در متن"""
    from config import bot_name, org_name, brand
    t = get_setting(key, default)
    repl = {"bot": bot_name(), "org": org_name(), "brand": brand()}
    repl.update(kw)
    for k, v in repl.items():
        t = t.replace("{" + k + "}", str(v))
    return t


# ==================== وضعیت OTP ====================
def show_otp_settings(cid, uid):
    if not _guard(cid, uid):
        return

    info = test_safir_connection()
    lines = [
        "📱 تنظیمات رمز یکبار مصرف (سفیر)",
        "━━━━━━━━━━━━━━",
        "",
        f"📌 وضعیت: {'✅ فعال' if info['enabled'] else '⚠️ غیرفعال (حالت تست)'}",
        "",
        f"🔑 کلید دسترسی: {'✅ ثبت شده' if info['api_key_set'] else '❌ خالی'}",
    ]
    if info["api_key_set"]:
        lines.append(f"    {info['api_key_preview']}")

    lines += [
        f"🤖 شناسه بات OTP: {info['bot_id'] or '❌ خالی'}",
        f"🆔 شناسه بات اصلی: {info['main_bot_id']}",
    ]

    if info["same_as_main"] and info["enabled"]:
        lines += ["", "⚠️ هشدار: شناسه بات OTP با بات اصلی یکی است.",
                  "معمولاً بات رمز یکبار مصرف جداست."]

    if not info["enabled"]:
        lines += [
            "",
            "🔧 برای فعال‌سازی، در فایل .env بنویسید:",
            "",
            "SAFIR_API_KEY=کلید_شما",
            "SAFIR_BOT_ID=شناسه_عددی_بات_OTP",
            "",
            "سپس ربات را ری‌استارت کنید.",
        ]
    else:
        lines += ["", "💡 برای تست واقعی، دکمه زیر را بزنید."]

    btns = [[{"text": "🧪 تست ارسال کد", "callback_data": "otp_test"}]]
    btns.append([{"text": "🔙 تنظیمات", "callback_data": "admin_settings"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_otp_test(cid, uid):
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_TEST_OTP, {}, merge=False)
    send(cid, (
        "🧪 تست ارسال رمز یکبار مصرف\n"
        "━━━━━━━━━━━━━━\n\n"
        "شماره موبایل مقصد را بفرستید:\n"
        "مثال: 09120000000\n\n"
        "💡 یک کد واقعی به این شماره ارسال می‌شود."
    ), kb_cancel())


def handle_otp_test(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    if text == BTN_BACK:
        clear_state(uid)
        return show_otp_settings(cid, uid)

    mobile = normalize_mobile(text)
    if not mobile:
        return send(cid, "❌ شماره نامعتبر\n\nمثال: 09120000000")

    clear_state(uid)
    send(cid, "⏳ در حال ارسال...")

    from auth import to_intl_phone
    code = generate_otp()
    res = send_otp_via_safir(mobile, code)

    lines = [
        "🧪 نتیجه تست OTP",
        "━━━━━━━━━━━━━━",
        "",
        f"📱 شماره: {mobile}",
        f"🌐 فرمت ارسالی: {to_intl_phone(mobile)}",
        f"🤖 bot_id: {SAFIR_BOT_ID}",
        "",
    ]
    if res.get("test_mode"):
        lines += [
            "⚠️ حالت تست — سفیر تنظیم نشده",
            f"🔢 کد تولید شده: {code}",
            "",
            "برای ارسال واقعی، SAFIR_API_KEY و SAFIR_BOT_ID را در .env بنویسید.",
        ]
    elif res.get("ok"):
        lines += [
            "✅ ارسال موفق!",
            f"🧾 شناسه پیام: {res.get('message_id')}",
            "",
            "💡 کد باید در بات رمز یکبار مصرف بله دریافت شده باشد.",
        ]
    else:
        lines += [
            "❌ ارسال ناموفق",
            "",
            f"📄 خطا: {res.get('error')}",
        ]
        if res.get("hint"):
            lines.append(f"💡 راهنما: {res['hint']}")
        lines += [
            "",
            "🔍 موارد رایج:",
            "• bot_id اشتباه (باید بات OTP باشد نه بات اصلی)",
            "• کلید api-access-key منقضی یا غلط",
            "• شماره در پنل کسب‌وکار مجاز نیست",
        ]

    send(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔄 تست دوباره", "callback_data": "otp_test"}],
        [{"text": "🔙 بازگشت", "callback_data": "set_otp"}],
    ]})


# ==================== وضعیت پرداخت ====================
def payment_test_menu(cid, uid):
    """🧪 ابزار تست پرداخت — فاز ۷"""
    if not _guard(cid, uid):
        return
    from config import PAYMENT_ENABLED, PAYMENT_TEST_MODE, PAYMENT_PROVIDER_TOKEN

    lines = [
        "🧪 تست پرداخت",
        "━━━━━━━━━━━━━━",
        "",
    ]
    if not PAYMENT_ENABLED:
        lines += [
            "❌ توکن پرداخت تنظیم نشده",
            "",
            "🔧 برای تست، در فایل .env بنویسید:",
            "",
            "PAYMENT_PROVIDER_TOKEN=WALLET-TEST-1111111111111111",
            "",
            "این توکن آزمایشی است — پولی جابه‌جا نمی‌شود",
            "ولی کل فرآیند را می‌توانید تست کنید.",
            "",
            "📌 توکن واقعی را از @botfather بگیرید.",
        ]
        return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
            [{"text": "🔙 تنظیمات پرداخت", "callback_data": "set_payment"}]]})

    from config import PAYMENT_TEST_AMOUNT, PAYMENT_MAX_AMOUNT
    from events import fmt_money

    if PAYMENT_TEST_MODE:
        lines += [
            "📌 حالت: 🧪 آزمایشی",
            f"🔑 توکن: {PAYMENT_PROVIDER_TOKEN[:14]}***",
            "",
            "✅ پولی جابه‌جا نمی‌شود — با خیال راحت تست کنید",
        ]
    else:
        lines += [
            "📌 حالت: 💰 واقعی",
            f"🔑 توکن: {PAYMENT_PROVIDER_TOKEN[:10]}***{PAYMENT_PROVIDER_TOKEN[-4:]}",
            "",
            "🔴🔴 هشدار: توکن واقعی است!",
            "پرداخت‌ها از کیف پول واقعی کم می‌شوند",
            "و به کیف پول شما واریز می‌گردند.",
            "",
            f"🛡️ سقف هر تراکنش: {fmt_money(PAYMENT_MAX_AMOUNT)} {CURRENCY_LABEL}",
        ]

    lines += [
        "",
        "🎯 تست‌های موجود:",
        f"1️⃣ فاکتور {fmt_money(PAYMENT_TEST_AMOUNT)} {CURRENCY_LABEL}",
        "2️⃣ رویداد آزمایشی — تست کامل ثبت‌نام پولی",
        "3️⃣ استعلام تراکنش — بررسی inquireTransaction",
    ]
    if not PAYMENT_TEST_MODE:
        lines += ["", "💡 برای تست بدون پول، در .env بگذارید:",
                  "PAYMENT_PROVIDER_TOKEN=WALLET-TEST-1111111111111111"]

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "1️⃣ ارسال فاکتور تست", "callback_data": "pay_test_invoice"}],
        [{"text": "2️⃣ ساخت رویداد آزمایشی", "callback_data": "pay_test_event"}],
        [{"text": "3️⃣ استعلام تراکنش", "callback_data": "pay_test_inquire"}],
        [{"text": "🧾 لیست تراکنش‌ها", "callback_data": "tx_list"}],
        [{"text": "🔙 تنظیمات پرداخت", "callback_data": "set_payment"}],
    ]})


def confirm_test_invoice(cid, uid):
    """تأیید قبل از ارسال فاکتور واقعی"""
    if not _guard(cid, uid):
        return
    from config import (PAYMENT_TEST_MODE, PAYMENT_TEST_AMOUNT,
                        PAYMENT_CONFIRM, CURRENCY_LABEL)
    from events import fmt_money

    if PAYMENT_TEST_MODE or not PAYMENT_CONFIRM:
        return send_test_invoice(cid, uid)

    send_or_edit(cid, (
        f"⚠️ تأیید ارسال فاکتور واقعی\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🔴 توکن پرداخت شما واقعی است.\n\n"
        f"💰 مبلغ: {fmt_money(PAYMENT_TEST_AMOUNT)} {CURRENCY_LABEL}\n\n"
        f"اگر پرداخت کنید، این مبلغ واقعاً\n"
        f"از کیف پول شما کم و به کیف پول بات واریز می‌شود.\n\n"
        f"ادامه می‌دهید؟"
    ), {"inline_keyboard": [
        [{"text": "✅ بله، فاکتور را بفرست", "callback_data": "pay_test_inv_go"}],
        [{"text": "❌ انصراف", "callback_data": "pay_test"}],
    ]})


def send_test_invoice(cid, uid):
    """ارسال فاکتور آزمایشی"""
    if not _guard(cid, uid):
        return
    from config import (PAYMENT_PROVIDER_TOKEN, PAYMENT_ENABLED,
                        PAYMENT_TEST_MODE, PAYMENT_TEST_AMOUNT,
                        CURRENCY_LABEL, check_amount)
    from bale_api import send_invoice
    from events import fmt_money
    import time as _t

    if not PAYMENT_ENABLED:
        return send(cid, "❌ توکن پرداخت تنظیم نشده")

    amount = PAYMENT_TEST_AMOUNT
    okamt, amsg = check_amount(amount)
    if not okamt:
        return send(cid, f"⛔ {amsg}")

    import uuid as _uu
    payload = f"test_{uid}_{int(_t.time())}_{_uu.uuid4().hex[:6]}"
    db_execute("""INSERT INTO transactions
        (bale_user_id, event_id, registration_id, payload, amount, status)
        VALUES (?,NULL,NULL,?,?,'pending')""", (uid, payload, amount))

    r = send_invoice(
        cid, title="تست پرداخت نورا",
        description="فاکتور آزمایشی برای بررسی سیستم پرداخت",
        payload=payload,
        provider_token=PAYMENT_PROVIDER_TOKEN,
        prices=[{"label": "تست سیستم", "amount": amount}])

    if r.get("ok"):
        warn_txt = ("\n\n🧪 آزمایشی — پولی کم نمی‌شود."
                    if PAYMENT_TEST_MODE else
                    "\n\n🔴 واقعی — اگر پرداخت کنید پول کم می‌شود!")
        send_or_edit(cid, (
            f"✅ فاکتور ارسال شد\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"💰 مبلغ: {fmt_money(amount)} {CURRENCY_LABEL}\n"
            f"🔖 شناسه: {payload}\n\n"
            f"💡 روی فاکتور بالا بزنید.\n"
            f"بعد از پرداخت، ربات باید پیام تأیید بدهد."
            f"{warn_txt}"
        ), {"inline_keyboard": [
            [{"text": "🔙 تست پرداخت", "callback_data": "pay_test"}]]})
    else:
        send_or_edit(cid, (
            f"❌ ارسال فاکتور ناموفق\n\n"
            f"📄 خطا: {r.get('description')}\n\n"
            f"🔍 علت‌های احتمالی:\n"
            f"• توکن پرداخت اشتباه است\n"
            f"• بات مجوز پرداخت ندارد\n"
            f"• sendInvoice در بله فعال نیست"
        ), {"inline_keyboard": [
            [{"text": "🔙 بازگشت", "callback_data": "pay_test"}]]})


def _test_amount():
    from config import PAYMENT_TEST_AMOUNT
    return PAYMENT_TEST_AMOUNT


def create_test_event(cid, uid):
    """ساخت رویداد آزمایشی پولی برای تست کامل"""
    if not _guard(cid, uid):
        return
    from datetime import datetime as _dt

    exists = db_execute(
        "SELECT id FROM events WHERE title='🧪 رویداد آزمایشی پرداخت'",
        fetch="one")
    if exists:
        eid = exists["id"]
        send(cid, f"ℹ️ رویداد آزمایشی از قبل وجود دارد (#{eid})")
    else:
        eid = db_execute("""INSERT INTO events
            (title, description, event_type, location_type, online_link,
             start_date, start_time, status, capacity, is_paid, price,
             privacy, has_ticket, has_attendance, require_profile,
             points_reward, organizer, created_by)
            VALUES ('🧪 رویداد آزمایشی پرداخت',
                    'این رویداد فقط برای تست پرداخت ساخته شده',
                    'workshop','online','https://ble.ir/test',
                    '1404/12/29','20:00','published',100,1,?,
                    'public',1,0,0,0,'تست',?)""",
            (_test_amount(), uid))
        if not eid:
            return send(cid, "❌ خطا در ساخت رویداد آزمایشی")
        send(cid, f"✅ رویداد آزمایشی ساخته شد (#{eid})")

    from events import fmt_money as _fm
    send_or_edit(cid, (
        f"🧪 رویداد آزمایشی پرداخت\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"💰 مبلغ: {_fm(_test_amount())} {CURRENCY_LABEL}\n"
        f"🎫 بلیت: فعال\n"
        f"👤 نیاز به پروفایل: ندارد\n\n"
        f"📋 مراحل تست:\n"
        f"۱. روی «ثبت‌نام» بزنید\n"
        f"۲. فاکتور می‌آید → پرداخت کنید\n"
        f"۳. باید بلیت + لینک دریافت کنید\n\n"
        f"💡 با توکن آزمایشی پولی کم نمی‌شود."
    ), {"inline_keyboard": [
        [{"text": "🎫 شروع تست ثبت‌نام", "callback_data": f"uev_{eid}"}],
        [{"text": "🗑️ حذف رویداد آزمایشی", "callback_data": f"pay_test_del_{eid}"}],
        [{"text": "🔙 تست پرداخت", "callback_data": "pay_test"}],
    ]})


def delete_test_event(cid, uid, eid):
    if not _guard(cid, uid):
        return
    db_execute("DELETE FROM event_registrations WHERE event_id=?", (eid,))
    db_execute("DELETE FROM transactions WHERE event_id=?", (eid,))
    db_execute("DELETE FROM events WHERE id=? AND title LIKE '🧪%'", (eid,))
    send_or_edit(cid, "🗑️ رویداد آزمایشی حذف شد", {"inline_keyboard": [
        [{"text": "🔙 تست پرداخت", "callback_data": "pay_test"}]]})


STATE_INQUIRE = "tx_inquire"


def start_inquire(cid, uid):
    if not _guard(cid, uid):
        return
    rows = db_execute("""SELECT transaction_id, amount, status FROM transactions
        WHERE transaction_id IS NOT NULL AND transaction_id!=''
        ORDER BY id DESC LIMIT 5""", fetch="all") or []
    txt = "🔍 استعلام تراکنش\n━━━━━━━━━━━━━━\n\nشناسه تراکنش را بفرستید:"
    if rows:
        txt += "\n\n📋 آخرین تراکنش‌ها:\n"
        for r in rows:
            txt += f"• {r['transaction_id'][:24]} ({r['status']})\n"
    set_state(uid, STATE_INQUIRE, {}, merge=False)
    send(cid, txt, kb_cancel())


def handle_inquire(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    if text == BTN_BACK:
        clear_state(uid)
        return payment_test_menu(cid, uid)
    clear_state(uid)
    if not text:
        return send(cid, "⚠️ شناسه را بفرستید")

    from bale_api import inquire_transaction
    from events import fmt_money
    from config import CURRENCY_LABEL

    send(cid, "⏳ در حال استعلام...")
    r = inquire_transaction(text)
    if not r.get("ok"):
        return send(cid, (
            f"❌ استعلام ناموفق\n\n📄 {r.get('description')}"
        ), {"inline_keyboard": [
            [{"text": "🔙 بازگشت", "callback_data": "pay_test"}]]})

    res = r.get("result") or {}
    labels = {"pending": "⏳ در حال پردازش", "paid": "✅ پرداخت شده",
              "failed": "❌ ناموفق", "rejected": "🚫 رد شده"}
    send(cid, (
        f"🧾 نتیجه استعلام\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🆔 {res.get('id')}\n"
        f"📌 {labels.get(res.get('status'), res.get('status'))}\n"
        f"💰 {fmt_money(res.get('amount'))} {CURRENCY_LABEL}\n"
        f"👤 کاربر: {res.get('userID')}"
    ), {"inline_keyboard": [
        [{"text": "🔙 تست پرداخت", "callback_data": "pay_test"}]]})


def show_transactions(cid, uid, page=0):
    if not _guard(cid, uid):
        return
    from events import fmt_money

    rows = db_execute("""
        SELECT t.*, u.first_name, u.last_name, u.mobile, e.title
        FROM transactions t
        LEFT JOIN users u ON u.bale_user_id=t.bale_user_id
        LEFT JOIN events e ON e.id=t.event_id
        ORDER BY t.id DESC LIMIT 15
    """, fetch="all") or []

    if not rows:
        return send_or_edit(cid, "📭 تراکنشی ثبت نشده", {"inline_keyboard": [
            [{"text": "🔙 بازگشت", "callback_data": "set_payment"}]]})

    icons = {"paid": "✅", "pending": "⏳", "failed": "❌", "rejected": "🚫"}
    lines = ["🧾 آخرین تراکنش‌ها", "━━━━━━━━━━━━━━", ""]
    for t in rows:
        nm = f"{t.get('first_name') or ''} {t.get('last_name') or ''}".strip() or "—"
        lines += [
            f"{icons.get(t.get('status'), '•')} #{t['id']} — {fmt_money(t.get('amount'))} {CURRENCY_LABEL}",
            f"├── 👤 {nm} ({t.get('mobile') or '-'})",
            f"├── 🎉 {t.get('title') or '-'}",
            f"└── 📅 {_jd.fmt(t.get('created_at'), 'datetime')}",
            "",
        ]

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": "set_payment"}]]})


# ==================== بخش‌های کاربر ====================
def show_support(cid, uid):
    """
    💬 نسخه ساده پشتیبانی.

    ⚠️ از فاز ۱۸-ب، مسیر اصلی `about.show_hub` است. این تابع فقط
       برای سازگاری با کدهای قدیمی نگه داشته شده.
    """
    try:
        import about as _ab
        return _ab.show_hub(cid, uid)
    except Exception:
        pass
    from config import brand, org_name
    support = get_setting("msg_support", "")
    about = get_setting("msg_about", "")

    lines = ["💬 پشتیبانی و درباره ما", "━━━━━━━━━━━━━━", ""]
    if about:
        lines += ["ℹ️ درباره ما:", about, ""]
    else:
        lines += [f"ℹ️ {brand()}", org_name(), ""]
    if support:
        lines += ["📞 ارتباط با ما:", support]
    else:
        lines.append("📞 برای ارتباط، به ادمین پیام دهید.")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "❓ سوالات متداول", "callback_data": "u_faq"}],
        [{"text": "📱 تیکت پشتیبانی", "callback_data": "tk_my"}],
        [{"text": "💬 ارسال پیام به ادمین", "callback_data": "u_contact"}],
        [{"text": "🔙 منوی اصلی", "callback_data": "back_main"}],
    ]})


def show_faq(cid, uid):
    faq = get_setting("msg_faq", "")
    if not faq:
        faq = (
            "❓ سوالات متداول\n\n"
            "۱. چطور در رویداد ثبت‌نام کنم؟\n"
            "از منوی «🎉 رویدادها» رویداد مورد نظر را انتخاب کنید.\n\n"
            "۲. چرا باید پروفایلم را تکمیل کنم؟\n"
            "برای برخی رویدادها، اطلاعات کامل لازم است.\n\n"
            "۳. بلیت من کجاست؟\n"
            "از «👤 پروفایل من» → «🎫 بلیت‌های من»"
        )
    send_or_edit(cid, faq, {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": "u_support"}]]})


def show_referral(cid, uid):
    """
    ✅ فیکس: دعوت از دوستان حالا لینک واقعی قابل کلیک دارد
    لینک: https://ble.ir/<username>?start=<code>
    وقتی دوست روی آن بزند، /start CODE برای ربات ارسال می‌شود
    و رابطه دعوت خودکار ثبت می‌گردد.
    """
    from auth import get_user
    from config import brand
    from database import db_scalar

    u = get_user(uid)
    if not u:
        return send(cid, "⚠️ ابتدا /start را بزنید")

    code = u.get("referral_code") or f"NORA{uid}"
    from config import deep_link
    link = deep_link(code)

    invited = db_scalar("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,))
    invited_active = db_scalar(
        "SELECT COUNT(*) FROM users WHERE referred_by=? AND is_authenticated=1", (uid,))

    custom = get_setting("msg_referral", "")
    lines = ["👥 دعوت از دوستان", "━━━━━━━━━━━━━━", ""]
    if custom:
        lines += [custom, ""]

    lines += [
        f"🎁 کد دعوت شما: {code}",
        "",
        "📊 آمار شما:",
        f"├── 👤 دعوت‌شده: {invited} نفر",
        f"└── ✅ فعال: {invited_active} نفر",
        "",
    ]

    if link:
        lines += [
            "🔗 لینک اختصاصی شما:",
            link,
            "",
            "💡 این لینک را برای دوستانتان بفرستید.",
            "با یک کلیک وارد ربات می‌شوند و به نام شما ثبت می‌گردند.",
        ]
    else:
        lines += [
            "💡 کد بالا را به دوستانتان بدهید.",
            f"آن‌ها هنگام شروع {brand()} می‌توانند آن را وارد کنند.",
        ]

    btns = []
    if link:
        share_text = (
            f"سلام! 👋\n\n"
            f"من در {brand()} عضو شدم.\n"
            f"برای عضویت روی لینک زیر بزن:\n\n{link}"
        )
        btns.append([{"text": "📋 کپی لینک دعوت", "copy_text": {"text": link}}])
        btns.append([{"text": "📤 متن آماده اشتراک", "callback_data": "u_ref_share"}])
    btns.append([{"text": "📋 کپی کد", "copy_text": {"text": code}}])
    if invited:
        btns.append([{"text": f"👥 لیست دعوت‌شده‌ها ({invited})",
                      "callback_data": "u_ref_list"}])
    btns.append([{"text": "🔙 منوی اصلی", "callback_data": "back_main"}])

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


_bot_username_cache = {"v": None, "bot": None}


def _uname_key():
    """
    🔑 کلید ذخیره‌سازی — وابسته به شناسهٔ توکن.

    🔴 چرا؟ اگر توکن ربات عوض شود، یوزرنیم قبلی دیگر معتبر
       نیست. با گنجاندن شناسهٔ عددی توکن در کلید، کش خودکار
       باطل می‌شود و یوزرنیم تازه گرفته می‌شود.
    """
    try:
        from config import MAIN_BOT_ID
        return f"bot_username_{MAIN_BOT_ID}" if MAIN_BOT_ID \
            else "bot_username"
    except Exception:
        return "bot_username"


def get_bot_username(force=False):
    """
    🏷️ یوزرنیم ربات — بدون @

    ترتیب اولویت:
      ۱) BOT_USERNAME در .env      ← دست شماست، همیشه برنده
      ۲) تنظیم ذخیره‌شده (وابسته به توکن)
      ۳) getMe از API

    force=True کش را دور می‌زند و دوباره از API می‌پرسد.
    """
    try:
        from config import MAIN_BOT_ID, BOT_USERNAME_ENV
    except Exception:
        MAIN_BOT_ID, BOT_USERNAME_ENV = 0, ""

    # 1️⃣ .env بالاترین اولویت — با عوض شدن توکن هم دست‌نخورده
    if BOT_USERNAME_ENV:
        return BOT_USERNAME_ENV

    # ♻️ اگر توکن عوض شده، کش حافظه را دور بینداز
    if _bot_username_cache["bot"] != MAIN_BOT_ID:
        _bot_username_cache["v"] = None
        _bot_username_cache["bot"] = MAIN_BOT_ID

    if not force and _bot_username_cache["v"] is not None:
        return _bot_username_cache["v"]

    key = _uname_key()
    if not force:
        cached = (get_setting(key, "") or "").strip().lstrip("@")
        if cached:
            _bot_username_cache["v"] = cached
            return cached

    # 3️⃣ از خود بله بپرس
    try:
        from bale_api import get_me
        r = get_me()
        if r.get("ok"):
            un = ((r.get("result") or {}).get("username") or "").lstrip("@")
            if un:
                set_setting(key, un, "یوزرنیم ربات", "system")
                _bot_username_cache["v"] = un
                return un
    except Exception:
        pass
    if not force:
        _bot_username_cache["v"] = ""
    return ""


def share_referral(cid, uid):
    """متن آماده برای فوروارد کردن"""
    from auth import get_user
    from config import BOT_NAME, ORG_NAME
    u = get_user(uid)
    if not u:
        return
    code = u.get("referral_code") or f"NORA{uid}"
    from config import deep_link
    link = deep_link(code) or code

    text = (
        f"سلام! 👋\n\n"
        f"من عضو ربات {BOT_NAME} هستم\n"
        f"({ORG_NAME})\n\n"
        f"اینجا از رویدادها، کارگاه‌ها و برنامه‌های فرهنگی باخبر می‌شوی\n"
        f"و می‌تونی ثبت‌نام کنی.\n\n"
        f"🔗 برای عضویت:\n{link}"
    )
    send(cid, (
        "📤 متن آماده اشتراک‌گذاری\n"
        "━━━━━━━━━━━━━━\n\n"
        "این پیام را فوروارد کنید 👇"
    ))
    send_or_edit(cid, text, {"inline_keyboard": [
        [{"text": "📋 کپی متن", "copy_text": {"text": text[:250]}}],
        [{"text": "🔙 بازگشت", "callback_data": "u_referral"}],
    ]})


def show_referral_list(cid, uid):
    """لیست کسانی که با کد من عضو شده‌اند"""
    rows = db_execute("""
        SELECT first_name, last_name, created_at, is_authenticated, profile_status
        FROM users WHERE referred_by=? ORDER BY id DESC LIMIT 25
    """, (uid,), fetch="all") or []

    if not rows:
        return send_or_edit(cid, "📭 هنوز کسی با لینک شما عضو نشده", {"inline_keyboard": [
            [{"text": "🔙 بازگشت", "callback_data": "u_referral"}]]})

    lines = [f"👥 دعوت‌شده‌های شما ({len(rows)})", "━━━━━━━━━━━━━━", ""]
    for i, r in enumerate(rows, 1):
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or "بدون نام"
        mark = "✅" if r.get("is_authenticated") else "⏳"
        lines.append(f"{i}. {mark} {nm}")
        lines.append(f"   📅 {_jd.fmt(r.get('created_at'), 'date')}")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": "u_referral"}]]})


def show_points(cid, uid):
    from auth import get_user
    u = get_user(uid)
    if not u:
        return send(cid, "⚠️ ابتدا /start را بزنید")

    pts = int(u.get("total_points") or 0)
    rank = db_execute(
        "SELECT COUNT(*)+1 AS r FROM users WHERE COALESCE(total_points,0) > ?",
        (pts,), fetch="one") or {}
    total_users = db_execute("SELECT COUNT(*) AS c FROM users WHERE is_authenticated=1",
                             fetch="one") or {}

    top = db_execute("""
        SELECT first_name, last_name, total_points FROM users
        WHERE COALESCE(total_points,0) > 0
        ORDER BY total_points DESC LIMIT 5
    """, fetch="all") or []

    lines = [
        "🏆 امتیاز و رتبه من",
        "━━━━━━━━━━━━━━",
        "",
        f"🎯 امتیاز شما: {pts}",
        f"📊 رتبه: {rank.get('r') or '-'} از {total_users.get('c') or 0}",
        f"🎉 رویدادها: {u.get('total_events_registered') or 0}",
        f"🎓 گواهینامه‌ها: {u.get('total_certificates') or 0}",
    ]
    if top:
        lines += ["", "🥇 برترین‌ها:"]
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, t in enumerate(top):
            nm = f"{t.get('first_name') or ''} {t.get('last_name') or ''}".strip() or "کاربر"
            lines.append(f"{medals[i]} {nm} — {t.get('total_points') or 0}")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 پروفایل", "callback_data": "profile_view"}]]})


def show_notifications(cid, uid):
    rows = db_execute("""
        SELECT action_type, action_data, created_at FROM user_actions
        WHERE bale_user_id=? AND action_type IN
          ('profile_approved','profile_rejected','event_register','payment_success')
        ORDER BY id DESC LIMIT 10
    """, (uid,), fetch="all") or []

    if not rows:
        return send_or_edit(cid, (
            "🔔 اعلان‌ها\n━━━━━━━━━━━━━━\n\n📭 اعلانی ندارید."
        ), {"inline_keyboard": [[{"text": "🔙 منوی اصلی", "callback_data": "back_main"}]]})

    labels = {
        "profile_approved": "✅ پروفایل شما تأیید شد",
        "profile_rejected": "❌ پروفایل شما رد شد",
        "event_register": "🎫 ثبت‌نام در رویداد",
        "payment_success": "💳 پرداخت موفق",
    }
    lines = ["🔔 اعلان‌های اخیر", "━━━━━━━━━━━━━━", ""]
    for r in rows:
        lines += [labels.get(r["action_type"], r["action_type"]),
                  f"└── 📅 {_jd.fmt(r.get('created_at'), 'datetime')}", ""]

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 منوی اصلی", "callback_data": "back_main"}]]})


def seed_phase5_settings():
    """متن‌های پیش‌فرض فاز ۵"""
    from config import BOT_NAME, ORG_NAME
    # 💚 فاز ۱۷-ج — متن‌ها مهربان‌تر و صمیمی‌تر شدند
    #    (درخواست کاربر: «متن‌های ربات رو کلا مهربون‌تر و شیرین‌ترش کن»)
    defaults = [
        ("msg_events_empty",
         "🌱 فعلاً برنامه‌ای در راه نیست\n\n"
         "به‌زودی رویدادهای تازه‌ای اضافه می‌شود —\n"
         "همراهمان بمانید 💚", "رویداد"),

        ("msg_register_ok",
         "🎉 چه خوب که هستید!\n\n"
         "ثبت‌نام شما با موفقیت انجام شد.\n"
         "مشتاقانه منتظر دیدارتان هستیم 💚", "رویداد"),

        ("msg_payment_ok",
         "✅ پرداخت شما دریافت شد\n\n"
         "سپاس از همراهی و اعتمادتان 💚", "رویداد"),

        ("msg_support",
         f"💬 ما اینجاییم\n\n"
         f"هر سوال، پیشنهاد یا انتقادی داشتید با ما در میان بگذارید.\n"
         f"{ORG_NAME} 💚", "عمومی"),

        ("msg_about", f"ℹ️ ربات {BOT_NAME}\n{ORG_NAME}", "عمومی"),
        ("msg_faq", "", "عمومی"),

        ("msg_referral",
         "🤝 با هم بیشتر می‌درخشیم\n\n"
         "دوستانتان را به این مسیر علمی و فرهنگی دعوت کنید —\n"
         "هم آن‌ها بهره می‌برند، هم شما امتیاز می‌گیرید 💚", "عمومی"),

        # ═══════════ 🆕 متن‌های جدید فاز ۱۷-ج ═══════════
        ("msg_otp_sent",
         "✅ کد یکبار مصرف برایتان ارسال شد\n"
         "━━━━━━━━━━━━━━\n\n"
         "📱 شماره: {mobile}\n"
         "⏰ اعتبار: ۳ دقیقه\n\n"
         "🔢 لطفاً کد ۶ رقمی را وارد کنید:", "شروع"),

        ("msg_otp_hint",
         "💡 کد در «بات رمز یکبار مصرف» بله برایتان ارسال شده است.",
         "شروع"),

        ("msg_invite_required",
         "🤝 با همیاری و مهر\n"
         "━━━━━━━━━━━━━━\n\n"
         "{name} عزیز، برای شرکت در این برنامه\n"
         "{need} نفر از دوستانتان را به مسیر علمی و فرهنگی\n"
         "{org} دعوت کنید 💚\n\n"
         "📊 تا اینجا: {done} از {need} نفر\n\n"
         "هر دعوت، یک قدم برای گسترش این خانواده است 🌱",
         "رویداد"),

        ("msg_event_paid_hidden",
         "💳 برای این برنامه هزینه‌ای در نظر گرفته شده\n"
         "که در مرحله پرداخت به شما نمایش داده می‌شود.", "رویداد"),

        ("msg_profile_needed",
         "👤 یک قدم تا همراهی\n"
         "━━━━━━━━━━━━━━\n\n"
         "{name} عزیز، برای شرکت در این برنامه لازم است\n"
         "پروفایلتان تکمیل و تأیید شده باشد.\n\n"
         "📊 وضعیت فعلی: {status}\n\n"
         "💚 تکمیلش فقط چند دقیقه وقت می‌برد.", "پروفایل"),

        ("msg_force_join",
         "🤝 به جمع ما بپیوندید\n\n"
         "برای استفاده از ربات، لطفاً در کانال/گروه‌های زیر\n"
         "عضو شوید — آنجا از برنامه‌ها باخبر می‌شوید 💚", "شروع"),

        ("msg_welcome",
         f"👋 خوش آمدید به {BOT_NAME}\n\n"
         f"{ORG_NAME}\n\n"
         "💚 خوشحالیم که اینجایید.", "شروع"),

        ("msg_auth",
         "🔐 برای شروع، لطفاً هویتتان را تأیید کنید\n\n"
         "این کار فقط یک بار انجام می‌شود و اطلاعات شما\n"
         "نزد ما محفوظ است 🤝", "شروع"),

        ("msg_profile_approved",
         "✅ پروفایل شما تأیید شد\n\n"
         "حالا می‌توانید در همه برنامه‌ها شرکت کنید 💚", "پروفایل"),

        ("msg_profile_intro",
         "📝 بیایید بیشتر آشنا شویم\n\n"
         "با تکمیل پروفایل، برنامه‌های متناسب با شما را\n"
         "بهتر معرفی می‌کنیم 💚", "پروفایل"),
    ]
    for key, val, cat in defaults:
        exists = db_execute("SELECT key FROM settings WHERE key=?", (key,), fetch="one")
        if not exists and val:
            title = next((t for k, t, _ in EDITABLE_TEXTS if k == key), key)
            set_setting(key, val, title, cat)
