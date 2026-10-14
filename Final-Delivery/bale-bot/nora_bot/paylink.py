"""
🔗 پرداخت غیرمتمرکز — لینک پرداخت مستقل

درخواست کاربر (فاز ۱۷):
  «یه بخشی هم اضافه کن به اسم ساخت لینک پرداخت، ینی با کلیک کردن
   رو اون ادمین مبلغ و کارمزد و جزئیات اضافه کنه ... بعد با اون
   پارامترهایی که ادمین میده یه لینک پرداخت یکبار یا چند بار مصرف
   ربات به ادمین بده تا به هرکی دوست داشت بده تا از طریق اون
   پرداخت کنه. اسمش هم بزار پرداخت غیر متمرکز و تو مالی اضافش کن»

🎯 کاربرد: پرداخت بدون رویداد و بدون فرم — مثل شهریه، کمک مالی،
   فروش کالا، تسویه بدهی، هر چیزی.

جریان کار:
  ادمین → ➕ لینک جدید → عنوان → مبلغ → روش پرداخت → تنظیمات
       → 🔗 لینک تولید می‌شود → به هر کس خواست می‌دهد
  کاربر → روی لینک می‌زند → جزئیات را می‌بیند → پرداخت می‌کند
       → ادمین اعلان می‌گیرد

انواع لینک:
  🔂 یکبار مصرف     بعد از اولین پرداخت بسته می‌شود
  🔁 چندبار مصرف    تا سقف تعیین‌شده (یا نامحدود)
  💰 مبلغ ثابت      مبلغ را ادمین تعیین می‌کند
  ✍️ مبلغ باز       کاربر خودش مبلغ را وارد می‌کند (کمک مالی)
"""
from privacy import user_error_message
import random
import re
import string
import time
from datetime import datetime

from config import SUPER_ADMIN_ID, CURRENCY_LABEL, money, parse_money
from database import db_execute, db_scalar, get_setting, set_setting, log
from auth import (
    get_user, set_state, get_state_data, clear_state, log_action,
    normalize_digits, is_admin as _is_admin,
)
from bale_api import (
    send, send_or_edit, send_document, kb_cancel, kb_remove, BTN_BACK,
)
import jalali as _jd

STATE_PL_NEW = "pl_new"        # ویزارد ساخت
STATE_PL_EDIT = "pl_edit"      # ویرایش یک فیلد
STATE_PL_PAY = "pl_pay"        # کاربر مبلغ باز را وارد می‌کند

_rng = random.SystemRandom()

LINKS_PER_PAGE = 6


# ==================== دیتابیس ====================
PAYLINK_SCHEMA = {
    "code": "TEXT",                       # کد یکتای لینک
    "title": "TEXT",
    "description": "TEXT",
    "amount": "INTEGER DEFAULT 0",        # ریال — ۰ یعنی مبلغ باز
    "amount_mode": "TEXT DEFAULT 'fixed'",  # fixed | open
    "min_amount": "INTEGER DEFAULT 0",    # برای مبلغ باز
    "max_amount": "INTEGER DEFAULT 0",
    "method": "TEXT DEFAULT 'bale_wallet'",
    "card_id": "INTEGER",
    "gateway_id": "INTEGER",
    "usage_type": "TEXT DEFAULT 'multi'",  # once | multi
    "max_uses": "INTEGER DEFAULT 0",      # ۰ = نامحدود
    "used_count": "INTEGER DEFAULT 0",
    "paid_count": "INTEGER DEFAULT 0",
    "total_collected": "INTEGER DEFAULT 0",
    "expires_at": "TEXT",                 # تاریخ شمسی
    "require_auth": "INTEGER DEFAULT 1",
    "ask_name": "INTEGER DEFAULT 0",
    "ask_mobile": "INTEGER DEFAULT 0",
    "ask_note": "INTEGER DEFAULT 0",      # توضیح پرداخت‌کننده
    "note_label": "TEXT",
    "success_text": "TEXT",
    "notify_admin": "INTEGER DEFAULT 1",
    "is_active": "INTEGER DEFAULT 1",
    "created_by": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

PAYLINK_TX_SCHEMA = {
    "link_id": "INTEGER NOT NULL",
    "bale_user_id": "INTEGER",
    "payer_name": "TEXT",
    "payer_mobile": "TEXT",
    "payer_note": "TEXT",
    "amount": "INTEGER DEFAULT 0",         # مبلغ پایه
    "fee_amount": "INTEGER DEFAULT 0",
    "total_amount": "INTEGER DEFAULT 0",
    "method": "TEXT",
    "status": "TEXT DEFAULT 'pending'",    # pending | paid | failed
    "payload": "TEXT",
    "transaction_id": "TEXT",
    "receipt_id": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "paid_at": "TIMESTAMP",
}


def init_paylink_tables():
    from database import ensure_table
    ensure_table("payment_links", PAYLINK_SCHEMA)
    ensure_table("paylink_payments", PAYLINK_TX_SCHEMA)
    for q in [
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_plcode ON payment_links(code)",
        "CREATE INDEX IF NOT EXISTS idx_pl_active ON payment_links(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_plp_link ON paylink_payments(link_id)",
        "CREATE INDEX IF NOT EXISTS idx_plp_user "
        "ON paylink_payments(bale_user_id)",
    ]:
        db_execute(q)
    log("✅ جدول‌های پرداخت غیرمتمرکز آماده شد")


# ==================== کمکی ====================
def _guard(cid, uid):
    """🔒 فقط سوپرادمین و کسانی که دسترسی مالی دارند"""
    if not _is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    import permissions as perm
    if not perm.has_any(uid, "fin_view", "fin_settings"):
        send(cid, "🔒 پرداخت غیرمتمرکز فقط برای سوپرادمین است")
        return False
    return True


def gen_code(n=10):
    """کد یکتای لینک"""
    alpha = string.ascii_uppercase + string.digits
    for _ in range(20):
        c = "PL" + "".join(_rng.choices(alpha, k=n))
        if not db_execute("SELECT id FROM payment_links WHERE code=?",
                          (c,), fetch="one"):
            return c
    return "PL" + str(int(time.time()))


def get_link(lid):
    """خواندن امن لینک با شناسه"""
    try:
        lid = int(lid)
    except (TypeError, ValueError):
        return None
    return db_execute("SELECT * FROM payment_links WHERE id=?",
                      (lid,), fetch="one")


def get_link_by_code(code):
    code = (code or "").strip().upper()
    if not code or not re.match(r"^PL[A-Z0-9]{4,20}$", code):
        return None
    return db_execute("SELECT * FROM payment_links WHERE code=?",
                      (code,), fetch="one")


def link_url(link):
    """
    🔗 لینک پرداخت قابل اشتراک‌گذاری.

    از config.deep_link می‌آید تا با عوض شدن آیدی/توکن
    ربات خودکار درست بماند.
    """
    code = (link or {}).get("code") or ""
    try:
        from config import deep_link
        u = deep_link(f"pay_{code}")
        if u:
            return u
    except Exception:
        pass
    return f"/start pay_{code}"


def link_status(link):
    """وضعیت لینک — (آیکون، متن، قابل استفاده؟)"""
    if not link:
        return "❌", "یافت نشد", False
    if not int(link.get("is_active") or 0):
        return "⛔", "غیرفعال", False

    if link.get("expires_at"):
        try:
            from occasions import today_jalali
            jy, jm, jd = today_jalali()
            today = f"{jy}/{jm:02d}/{jd:02d}"
            parts = str(link["expires_at"]).split("/")
            if len(parts) == 3:
                exp = (f"{int(parts[0])}/{int(parts[1]):02d}/"
                       f"{int(parts[2]):02d}")
                if exp < today:
                    return "⏰", "منقضی‌شده", False
        except Exception:
            pass

    used = int(link.get("paid_count") or 0)
    if (link.get("usage_type") or "multi") == "once":
        if used >= 1:
            return "✅", "استفاده‌شده (یکبار مصرف)", False
        return "🟢", "فعال — یکبار مصرف", True

    mx = int(link.get("max_uses") or 0)
    if mx and used >= mx:
        return "🈵", f"سقف پر شد ({used}/{mx})", False
    return "🟢", (f"فعال ({used}/{mx})" if mx else f"فعال ({used} پرداخت)"), True


def _fmt_amount(link):
    """نمایش مبلغ لینک"""
    if (link.get("amount_mode") or "fixed") == "open":
        lo = int(link.get("min_amount") or 0)
        hi = int(link.get("max_amount") or 0)
        if lo and hi:
            return f"✍️ دلخواه ({money(lo)} تا {money(hi)})"
        if lo:
            return f"✍️ دلخواه (از {money(lo)})"
        if hi:
            return f"✍️ دلخواه (تا {money(hi)})"
        return "✍️ دلخواه کاربر"
    return money(link.get("amount") or 0)


# ==================== 📋 لیست لینک‌ها ====================
def show_panel(cid, uid, page=0):
    """🔗 پنل پرداخت غیرمتمرکز"""
    if not _guard(cid, uid):
        return

    rows = db_execute("""SELECT * FROM payment_links
        ORDER BY is_active DESC, id DESC LIMIT 100""", fetch="all") or []

    n_all = len(rows)
    n_on = sum(1 for r in rows if link_status(r)[2])
    total = db_scalar("SELECT COALESCE(SUM(total_collected),0) "
                      "FROM payment_links") or 0
    n_paid = db_scalar("SELECT COUNT(*) FROM paylink_payments "
                       "WHERE status='paid'") or 0

    lines = [
        "🔗 پرداخت غیرمتمرکز", "━━━━━━━━━━━━━━", "",
        "لینک پرداخت مستقل بسازید و به هر کس خواستید بدهید —",
        "بدون نیاز به رویداد یا فرم.", "",
        f"📊 لینک‌ها: {n_all}  |  🟢 فعال: {n_on}",
        f"💰 مجموع دریافتی: {money(total)}",
        f"🧾 پرداخت موفق: {n_paid}", "",
    ]

    btns = [[{"text": "➕ ساخت لینک پرداخت", "callback_data": "pl_new"}]]

    if not rows:
        lines += ["📭 هنوز لینکی نساخته‌اید", "",
                  "💡 با «➕ ساخت لینک پرداخت» شروع کنید."]
    else:
        per = LINKS_PER_PAGE
        pages = max(1, (n_all + per - 1) // per)
        page = max(0, min(int(page or 0), pages - 1))
        for r in rows[page * per:(page + 1) * per]:
            ic, st, _ = link_status(r)
            lines += [f"{ic} {r.get('title')}",
                      f"   💰 {_fmt_amount(r)}  |  {st}",
                      f"   🧾 {r.get('paid_count') or 0} پرداخت — "
                      f"{money(r.get('total_collected') or 0)}", ""]
            btns.append([{"text": f"{ic} {r.get('title')}"[:42],
                          "callback_data": f"pl_v_{r['id']}"}])
        if pages > 1:
            nav = []
            if page > 0:
                nav.append({"text": "⬅️", "callback_data": f"pl_pg_{page-1}"})
            nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
            if page < pages - 1:
                nav.append({"text": "➡️", "callback_data": f"pl_pg_{page+1}"})
            btns.append(nav)

    if n_paid:
        btns.append([{"text": "📊 گزارش پرداخت‌ها", "callback_data": "pl_rep"},
                     {"text": "📤 خروجی Excel", "callback_data": "pl_exp"}])
    btns.append([{"text": "🔙 پرداخت و مالی", "callback_data": "set_payment"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ==================== ➕ ساخت لینک (ویزارد) ====================
WIZ_STEPS = [
    ("title", "📝 عنوان پرداخت", "مثال: شهریه ترم بهار  یا  کمک به جشن نوروز"),
    ("description", "📄 توضیحات", "توضیح کوتاه برای پرداخت‌کننده\n\n"
                                  "«⏭️ رد کردن» = بدون توضیح"),
    ("amount", "💰 مبلغ", None),
]


def start_new(cid, uid):
    """➕ شروع ویزارد ساخت لینک"""
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_PL_NEW, {"step": 0}, merge=False)
    send(cid, (
        "🔗 ساخت لینک پرداخت\n"
        "━━━━━━━━━━━━━━\n\n"
        "با چند سوال ساده یک لینک پرداخت می‌سازیم که\n"
        "می‌توانید به هر کس بدهید.\n\n"
        "📝 عنوان پرداخت را بنویسید:\n\n"
        "مثال: شهریه ترم بهار"
    ), kb_cancel())


def handle_wizard(message):
    """پردازش مراحل ویزارد"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    d = get_state_data(uid)
    step = int(d.get("step") or 0)

    if text in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_panel(cid, uid)

    skip = text in ("⏭️ رد کردن", "رد کردن", "-")

    # مرحله ۰ — عنوان
    if step == 0:
        if not text or skip:
            return send(cid, "⚠️ عنوان لازم است. بنویسید:")
        set_state(uid, STATE_PL_NEW, {"title": text[:80], "step": 1},
                  merge=True)
        return send(cid, (
            "📄 توضیحات\n━━━━━━━━━━━━━━\n\n"
            "توضیح کوتاهی که پرداخت‌کننده می‌بیند:\n\n"
            "💡 اگر لازم نیست «⏭️ رد کردن» را بزنید."
        ), {"keyboard": [[{"text": "⏭️ رد کردن"}], [{"text": BTN_BACK}]],
            "resize_keyboard": True})

    # مرحله ۱ — توضیحات
    if step == 1:
        set_state(uid, STATE_PL_NEW,
                  {"description": "" if skip else text[:500], "step": 2},
                  merge=True)
        return send(cid, (
            "💰 مبلغ پرداخت\n━━━━━━━━━━━━━━\n\n"
            f"مبلغ را به {CURRENCY_LABEL} بنویسید:\n\n"
            "مثال: 250000\n\n"
            "💡 اگر می‌خواهید کاربر خودش مبلغ را وارد کند\n"
            "(مثل کمک مالی)، «✍️ مبلغ دلخواه» را بزنید."
        ), {"keyboard": [[{"text": "✍️ مبلغ دلخواه"}], [{"text": BTN_BACK}]],
            "resize_keyboard": True})

    # مرحله ۲ — مبلغ
    if step == 2:
        if text in ("✍️ مبلغ دلخواه", "مبلغ دلخواه"):
            set_state(uid, STATE_PL_NEW,
                      {"amount": 0, "amount_mode": "open"}, merge=True)
            return _finish_wizard(cid, uid)
        digits = re.sub(r"[^\d]", "", normalize_digits(text))
        if not digits:
            return send(cid, "⚠️ مبلغ را به عدد بنویسید:\n\nمثال: 250000")
        rial = parse_money(digits)
        if rial <= 0:
            return send(cid, "⚠️ مبلغ باید بیشتر از صفر باشد:")
        set_state(uid, STATE_PL_NEW,
                  {"amount": rial, "amount_mode": "fixed"}, merge=True)
        return _finish_wizard(cid, uid)

    clear_state(uid)
    return send(cid, "⚠️ مرحله نامشخص — دوباره تلاش کنید", kb_remove())


def _finish_wizard(cid, uid):
    """ساخت لینک از داده‌های ویزارد"""
    d = get_state_data(uid)
    title = d.get("title")
    if not title:
        clear_state(uid)
        return send(cid, "❌ اطلاعات ناقص — دوباره شروع کنید", kb_remove())

    from payments import PAYMENT_ENABLED
    default_method = "bale_wallet" if PAYMENT_ENABLED else "card"

    code = gen_code()
    lid = db_execute("""INSERT INTO payment_links
        (code, title, description, amount, amount_mode, method,
         usage_type, created_by)
        VALUES (?,?,?,?,?,?,'multi',?)""",
        (code, title, d.get("description") or "",
         int(d.get("amount") or 0), d.get("amount_mode") or "fixed",
         default_method, uid))
    clear_state(uid)

    if not lid:
        return send(cid, "❌ خطا در ساخت لینک", kb_remove())

    log_action(uid, "paylink_created", {"id": lid, "code": code})
    send(cid, "✅ لینک ساخته شد!", kb_remove())
    return show_link(cid, uid, lid)


# ==================== 👁️ صفحه یک لینک ====================
def show_link(cid, uid, lid):
    """👁️ جزئیات و تنظیمات یک لینک"""
    if not _guard(cid, uid):
        return
    link = get_link(lid)
    if not link:
        return send(cid, "❌ لینک یافت نشد")

    from payments import PAYMENT_METHODS, calc_fee, fee_enabled, fee_label
    ic, st, usable = link_status(link)
    method = link.get("method") or "bale_wallet"
    pm = PAYMENT_METHODS.get(method, PAYMENT_METHODS["bale_wallet"])

    lines = [
        f"{ic} {link.get('title')}", "━━━━━━━━━━━━━━", "",
        f"📊 وضعیت: {st}",
        f"💰 مبلغ: {_fmt_amount(link)}",
        f"{pm['icon']} روش: {pm['name']}",
    ]

    # کارمزد
    if (link.get("amount_mode") or "fixed") == "fixed" and \
            fee_enabled(method):
        base = int(link.get("amount") or 0)
        fee, total = calc_fee(base, method)
        if fee > 0:
            lines += [f"   + {fee_label(method)}: {money(fee)}",
                      f"   💳 قابل پرداخت: {money(total)}"]

    usage = "🔂 یکبار مصرف" if (link.get("usage_type") or "multi") == "once" \
        else (f"🔁 چندبار (سقف {link['max_uses']})"
              if int(link.get("max_uses") or 0) else "🔁 نامحدود")
    lines.append(f"🔄 نوع: {usage}")

    if link.get("expires_at"):
        lines.append(f"⏰ انقضا: {link['expires_at']}")
    if link.get("description"):
        lines.append(f"\n📄 {str(link['description'])[:200]}")

    asks = []
    if int(link.get("ask_name") or 0):
        asks.append("نام")
    if int(link.get("ask_mobile") or 0):
        asks.append("موبایل")
    if int(link.get("ask_note") or 0):
        asks.append(link.get("note_label") or "توضیح")
    if asks:
        lines.append(f"📋 از پرداخت‌کننده می‌پرسد: {'، '.join(asks)}")

    lines += ["", "━━━━━━━━━━━━━━",
              f"🧾 پرداخت موفق: {link.get('paid_count') or 0}",
              f"💵 مجموع دریافتی: {money(link.get('total_collected') or 0)}"]

    url = link_url(link)
    lines += ["", "🔗 لینک پرداخت:", url, "",
              f"🔖 کد: {link.get('code')}"]
    if not usable:
        lines += ["", "⚠️ این لینک الان قابل استفاده نیست."]

    btns = [
        [{"text": "📤 ارسال لینک برای اشتراک‌گذاری",
          "callback_data": f"pl_share_{lid}"}],
        [{"text": "💰 مبلغ", "callback_data": f"pl_e_amount_{lid}"},
         {"text": "💳 روش پرداخت", "callback_data": f"pl_meth_{lid}"}],
        [{"text": "🔄 نوع مصرف", "callback_data": f"pl_use_{lid}"},
         {"text": "⏰ انقضا", "callback_data": f"pl_e_expires_at_{lid}"}],
        [{"text": "📝 عنوان", "callback_data": f"pl_e_title_{lid}"},
         {"text": "📄 توضیحات", "callback_data": f"pl_e_description_{lid}"}],
        [{"text": "📋 سوالات پرداخت‌کننده",
          "callback_data": f"pl_ask_{lid}"}],
        [{"text": "💚 پیام بعد از پرداخت",
          "callback_data": f"pl_e_success_text_{lid}"}],
    ]
    if int(link.get("paid_count") or 0):
        btns.append([{"text": f"🧾 پرداخت‌ها ({link['paid_count']})",
                      "callback_data": f"pl_tx_{lid}"}])
    btns += [
        [{"text": ("⛔ غیرفعال کردن" if int(link.get("is_active") or 0)
                   else "🟢 فعال کردن"),
          "callback_data": f"pl_tog_{lid}"}],
        [{"text": "🗑️ حذف لینک", "callback_data": f"pl_del_{lid}"}],
        [{"text": "🔙 لینک‌ها", "callback_data": "pl_panel"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def share_link(cid, uid, lid):
    """📤 پیام آماده برای فوروارد کردن"""
    if not _guard(cid, uid):
        return
    link = get_link(lid)
    if not link:
        return send(cid, "❌ یافت نشد")

    from payments import PAYMENT_METHODS, calc_fee
    method = link.get("method") or "bale_wallet"
    lines = [f"💳 {link.get('title')}", "━━━━━━━━━━━━━━", ""]
    if link.get("description"):
        lines += [str(link["description"])[:300], ""]

    if (link.get("amount_mode") or "fixed") == "open":
        lines.append("💰 مبلغ: به انتخاب شما")
    else:
        base = int(link.get("amount") or 0)
        fee, total = calc_fee(base, method)
        lines.append(f"💰 مبلغ: {money(total if fee else base)}")

    lines += ["", "👇 برای پرداخت روی لینک زیر بزنید:", link_url(link)]

    send(cid, "\n".join(lines))
    send(cid, ("📤 پیام بالا آماده ارسال است\n\n"
               "می‌توانید آن را فوروارد کنید یا لینک را کپی کرده\n"
               "و هر جا خواستید بگذارید."),
         {"inline_keyboard": [
             [{"text": "🔙 بازگشت", "callback_data": f"pl_v_{lid}"}]]})


# ==================== ✏️ ویرایش ====================
PL_FIELDS = {
    "title": ("📝 عنوان", "عنوان جدید را بنویسید:"),
    "description": ("📄 توضیحات", "توضیح جدید:\n\n«-» = حذف توضیح"),
    "amount": ("💰 مبلغ", None),
    "expires_at": ("⏰ تاریخ انقضا",
                   "تاریخ شمسی:\n\nمثال: 1404/12/29\n«-» = بدون انقضا"),
    "success_text": ("💚 پیام بعد از پرداخت",
                     "پیامی که بعد از پرداخت موفق نشان داده می‌شود:\n\n"
                     "«-» = پیام پیش‌فرض"),
    "note_label": ("🏷️ عنوان سوال", "مثال: بابت چه پرداختی؟"),
    "max_uses": ("🔢 سقف تعداد", "چند نفر بتوانند پرداخت کنند؟\n\n۰ = نامحدود"),
}


def start_edit(cid, uid, field, lid):
    """✏️ ویرایش یک فیلد لینک"""
    if not _guard(cid, uid):
        return
    link = get_link(lid)
    if not link:
        return send(cid, "❌ یافت نشد")
    if field not in PL_FIELDS:
        return send(cid, "❌ فیلد نامعتبر")

    title, prompt = PL_FIELDS[field]
    if field == "amount":
        set_state(uid, STATE_PL_EDIT, {"lid": lid, "field": field},
                  merge=False)
        return send(cid, (
            f"💰 مبلغ\n━━━━━━━━━━━━━━\n\n"
            f"📄 فعلی: {_fmt_amount(link)}\n\n"
            f"مبلغ جدید را به {CURRENCY_LABEL} بنویسید:\n\n"
            "💡 «✍️ مبلغ دلخواه» = کاربر خودش وارد کند"
        ), {"keyboard": [[{"text": "✍️ مبلغ دلخواه"}], [{"text": BTN_BACK}]],
            "resize_keyboard": True})

    cur = link.get(field) or "—"
    set_state(uid, STATE_PL_EDIT, {"lid": lid, "field": field}, merge=False)
    send(cid, f"✏️ {title}\n━━━━━━━━━━━━━━\n\n"
              f"📄 فعلی: {cur}\n\n{prompt}", kb_cancel())


def handle_edit(message):
    """دریافت مقدار جدید"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    d = get_state_data(uid)
    lid, field = d.get("lid"), d.get("field")

    if text in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_link(cid, uid, lid)

    if field not in PL_FIELDS:
        clear_state(uid)
        return send(cid, "❌ فیلد نامعتبر", kb_remove())

    if field == "amount":
        if text in ("✍️ مبلغ دلخواه", "مبلغ دلخواه"):
            db_execute("UPDATE payment_links SET amount=0, "
                       "amount_mode='open', updated_at=CURRENT_TIMESTAMP "
                       "WHERE id=?", (lid,))
            clear_state(uid)
            send(cid, "✅ مبلغ دلخواه شد", kb_remove())
            return show_link(cid, uid, lid)
        digits = re.sub(r"[^\d]", "", normalize_digits(text))
        if not digits:
            return send(cid, "⚠️ مبلغ را به عدد بنویسید:")
        rial = parse_money(digits)
        if rial <= 0:
            return send(cid, "⚠️ مبلغ باید بیشتر از صفر باشد:")
        db_execute("UPDATE payment_links SET amount=?, amount_mode='fixed', "
                   "updated_at=CURRENT_TIMESTAMP WHERE id=?", (rial, lid))
        clear_state(uid)
        send(cid, f"✅ مبلغ: {money(rial)}", kb_remove())
        return show_link(cid, uid, lid)

    if field == "expires_at":
        if text == "-":
            val = None
        elif re.match(r"^1[34]\d{2}/\d{1,2}/\d{1,2}$",
                      normalize_digits(text)):
            val = normalize_digits(text)
        else:
            return send(cid, "⚠️ قالب درست نیست.\nمثال: 1404/12/29")
        db_execute("UPDATE payment_links SET expires_at=?, "
                   "updated_at=CURRENT_TIMESTAMP WHERE id=?", (val, lid))
        clear_state(uid)
        send(cid, f"✅ انقضا: {val or 'ندارد'}", kb_remove())
        return show_link(cid, uid, lid)

    if field == "max_uses":
        digits = re.sub(r"[^\d]", "", normalize_digits(text))
        if not digits and text != "0":
            return send(cid, "⚠️ فقط عدد بفرستید:")
        n = min(100000, int(digits or 0))
        db_execute("UPDATE payment_links SET max_uses=?, "
                   "updated_at=CURRENT_TIMESTAMP WHERE id=?", (n, lid))
        clear_state(uid)
        send(cid, f"✅ سقف: {n if n else 'نامحدود'}", kb_remove())
        return show_usage(cid, uid, lid)

    val = "" if text == "-" else text[:500]
    if field == "title" and not val:
        return send(cid, "⚠️ عنوان نمی‌تواند خالی باشد:")
    db_execute(f"UPDATE payment_links SET {field}=?, "
               "updated_at=CURRENT_TIMESTAMP WHERE id=?", (val, lid))
    clear_state(uid)
    send(cid, "✅ ذخیره شد", kb_remove())
    return show_link(cid, uid, lid)


def show_methods(cid, uid, lid):
    """💳 انتخاب روش پرداخت لینک"""
    if not _guard(cid, uid):
        return
    link = get_link(lid)
    if not link:
        return send(cid, "❌ یافت نشد")

    from payments import PAYMENT_METHODS, method_available, fee_enabled
    cur = link.get("method") or "bale_wallet"
    lines = ["💳 روش پرداخت لینک", "━━━━━━━━━━━━━━", ""]
    btns = []
    for m in ("bale_wallet", "card", "custom_gateway"):
        info = PAYMENT_METHODS[m]
        ok, why = method_available(m)
        mark = "🔘" if m == cur else "⚪"
        fee_tag = " 💳" if fee_enabled(m) else ""
        lines.append(f"{mark} {info['icon']} {info['name']}{fee_tag}"
                     + ("" if ok else f"  ⚠️ {why}"))
        btns.append([{"text": f"{mark} {info['icon']} {info['name']}",
                      "callback_data": f"pl_sm_{m}_{lid}"}])
    lines += ["", "💳 = این روش کارمزد دارد"]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"pl_v_{lid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_method(cid, uid, method, lid):
    if not _guard(cid, uid):
        return
    from payments import PAYMENT_METHODS
    if method not in ("bale_wallet", "card", "custom_gateway"):
        return send(cid, "❌ روش نامعتبر")
    db_execute("UPDATE payment_links SET method=?, "
               "updated_at=CURRENT_TIMESTAMP WHERE id=?", (method, lid))
    return show_link(cid, uid, lid)


def show_usage(cid, uid, lid):
    """🔄 نوع مصرف لینک"""
    if not _guard(cid, uid):
        return
    link = get_link(lid)
    if not link:
        return send(cid, "❌ یافت نشد")
    cur = link.get("usage_type") or "multi"
    mx = int(link.get("max_uses") or 0)

    lines = ["🔄 نوع مصرف لینک", "━━━━━━━━━━━━━━", "",
             f"{'🔘' if cur == 'once' else '⚪'} 🔂 یکبار مصرف",
             "   بعد از اولین پرداخت موفق بسته می‌شود", "",
             f"{'🔘' if cur == 'multi' else '⚪'} 🔁 چندبار مصرف",
             f"   سقف: {mx if mx else 'نامحدود'}", "",
             f"🧾 تا الان: {link.get('paid_count') or 0} پرداخت"]

    btns = [
        [{"text": "🔂 یکبار مصرف", "callback_data": f"pl_su_once_{lid}"}],
        [{"text": "🔁 چندبار مصرف", "callback_data": f"pl_su_multi_{lid}"}],
    ]
    if cur == "multi":
        btns.append([{"text": f"🔢 سقف تعداد ({mx if mx else 'نامحدود'})",
                      "callback_data": f"pl_max_{lid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"pl_v_{lid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_usage(cid, uid, kind, lid):
    if not _guard(cid, uid):
        return
    if kind not in ("once", "multi"):
        return send(cid, "❌ نامعتبر")
    db_execute("UPDATE payment_links SET usage_type=?, "
               "updated_at=CURRENT_TIMESTAMP WHERE id=?", (kind, lid))
    return show_usage(cid, uid, lid)


def start_max(cid, uid, lid):
    if not _guard(cid, uid):
        return
    if not get_link(lid):
        return send(cid, "❌ یافت نشد")
    set_state(uid, STATE_PL_EDIT, {"lid": lid, "field": "max_uses"},
              merge=False)
    send(cid, ("🔢 سقف تعداد پرداخت\n━━━━━━━━━━━━━━\n\n"
               "چند نفر بتوانند از این لینک پرداخت کنند؟\n\n"
               "۰ = نامحدود"), kb_cancel())


def show_asks(cid, uid, lid):
    """📋 سوالات از پرداخت‌کننده"""
    if not _guard(cid, uid):
        return
    link = get_link(lid)
    if not link:
        return send(cid, "❌ یافت نشد")

    items = [
        ("require_auth", "🔐", "نیاز به احراز هویت"),
        ("ask_name", "👤", "پرسیدن نام"),
        ("ask_mobile", "📱", "پرسیدن موبایل"),
        ("ask_note", "📝", "پرسیدن توضیح"),
        ("notify_admin", "🔔", "اعلان به ادمین"),
    ]
    lines = ["📋 تنظیمات پرداخت‌کننده", "━━━━━━━━━━━━━━", ""]
    btns = []
    for key, ic, nm in items:
        on = int(link.get(key) or 0)
        lines.append(f"{'✅' if on else '⬜'} {ic} {nm}")
        btns.append([{"text": f"{'✅' if on else '⬜'} {ic} {nm}",
                      "callback_data": f"pl_t_{key}_{lid}"}])
    if int(link.get("ask_note") or 0):
        btns.append([{"text": f"🏷️ عنوان سوال "
                              f"({link.get('note_label') or 'توضیح'})",
                      "callback_data": f"pl_e_note_label_{lid}"}])
    lines += ["", "💡 اگر «احراز هویت» خاموش باشد، هر کسی بدون",
              "ثبت‌نام می‌تواند پرداخت کند."]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"pl_v_{lid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_flag(cid, uid, key, lid):
    if not _guard(cid, uid):
        return
    allowed = {"require_auth", "ask_name", "ask_mobile", "ask_note",
               "notify_admin"}
    if key not in allowed:
        return send(cid, "❌ نامعتبر")
    link = get_link(lid)
    if not link:
        return send(cid, "❌ یافت نشد")
    new = 0 if int(link.get(key) or 0) else 1
    db_execute(f"UPDATE payment_links SET {key}=?, "
               "updated_at=CURRENT_TIMESTAMP WHERE id=?", (new, lid))
    return show_asks(cid, uid, lid)


def toggle_active(cid, uid, lid):
    if not _guard(cid, uid):
        return
    link = get_link(lid)
    if not link:
        return send(cid, "❌ یافت نشد")
    new = 0 if int(link.get("is_active") or 0) else 1
    db_execute("UPDATE payment_links SET is_active=?, "
               "updated_at=CURRENT_TIMESTAMP WHERE id=?", (new, lid))
    log_action(uid, "paylink_toggle", {"id": lid, "on": new})
    send(cid, "🟢 لینک فعال شد" if new else "⛔ لینک غیرفعال شد")
    return show_link(cid, uid, lid)


def delete_link(cid, uid, lid, confirmed=False):
    if not _guard(cid, uid):
        return
    link = get_link(lid)
    if not link:
        return send(cid, "❌ یافت نشد")
    if not confirmed:
        n = int(link.get("paid_count") or 0)
        warn = (f"\n\n⚠️ {n} پرداخت روی این لینک ثبت شده —\n"
                "سابقه پرداخت‌ها حذف نمی‌شود." if n else "")
        return send_or_edit(cid, (
            f"🗑️ حذف لینک «{link.get('title')}»\n━━━━━━━━━━━━━━\n\n"
            f"❓ مطمئنید؟{warn}"
        ), {"inline_keyboard": [
            [{"text": "🗑️ بله، حذف کن", "callback_data": f"pl_dely_{lid}"}],
            [{"text": "❌ انصراف", "callback_data": f"pl_v_{lid}"}]]})
    db_execute("DELETE FROM payment_links WHERE id=?", (lid,))
    log_action(uid, "paylink_deleted", {"id": lid})
    send(cid, "🗑️ لینک حذف شد")
    return show_panel(cid, uid)


# ==================== 👤 نمای کاربر — پرداخت ====================
def open_link(cid, uid, code, user=None):
    """
    👤 کاربر روی لینک زده — نمایش جزئیات و دکمه پرداخت.
    از deep link (/start pay_XXXX) صدا زده می‌شود.
    """
    link = get_link_by_code(code)
    if not link:
        return send(cid, "❌ این لینک پرداخت معتبر نیست")

    ic, st, usable = link_status(link)
    if not usable:
        return send(cid, (
            f"{ic} این لینک پرداخت در دسترس نیست\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"📊 وضعیت: {st}\n\n"
            "💡 با کسی که لینک را داده تماس بگیرید."))

    if int(link.get("require_auth") or 0):
        u = get_user(uid)
        if not u or not u.get("is_authenticated"):
            return send(cid, (
                "🔐 برای این پرداخت باید احراز هویت کنید\n\n"
                "لطفاً /start را بزنید و شماره خود را تأیید کنید."))

    from payments import PAYMENT_METHODS, calc_fee, fee_label
    method = link.get("method") or "bale_wallet"
    pm = PAYMENT_METHODS.get(method, PAYMENT_METHODS["bale_wallet"])

    lines = [f"💳 {link.get('title')}", "━━━━━━━━━━━━━━", ""]
    if link.get("description"):
        lines += [str(link["description"])[:400], ""]

    if (link.get("amount_mode") or "fixed") == "open":
        lo = int(link.get("min_amount") or 0)
        hi = int(link.get("max_amount") or 0)
        lines.append("💰 مبلغ: به انتخاب شما")
        if lo:
            lines.append(f"   🔽 حداقل: {money(lo)}")
        if hi:
            lines.append(f"   🔼 حداکثر: {money(hi)}")
    else:
        base = int(link.get("amount") or 0)
        fee, total = calc_fee(base, method)
        lines.append(f"💰 مبلغ: {money(base)}")
        if fee > 0:
            lines += [f"   + {fee_label(method)}: {money(fee)}",
                      f"   ━━━━━━━━━━",
                      f"   💳 قابل پرداخت: {money(total)}"]

    lines += ["", f"{pm['icon']} روش پرداخت: {pm['name']}"]
    if (link.get("usage_type") or "multi") == "once":
        lines.append("🔂 این لینک یکبار مصرف است")

    btns = [[{"text": "💳 پرداخت", "callback_data": f"plpay_{link['id']}"}],
            [{"text": "🏠 منوی اصلی", "callback_data": "back_main"}]]
    send(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_payment(cid, uid, lid):
    """💳 شروع پرداخت لینک"""
    link = get_link(lid)
    if not link:
        return send(cid, "❌ لینک یافت نشد")

    ic, st, usable = link_status(link)
    if not usable:
        return send(cid, f"{ic} این لینک دیگر قابل استفاده نیست ({st})")

    if int(link.get("require_auth") or 0):
        u = get_user(uid)
        if not u or not u.get("is_authenticated"):
            return send(cid, "🔐 ابتدا /start را بزنید و احراز هویت کنید")

    # مبلغ باز → از کاربر بپرس
    if (link.get("amount_mode") or "fixed") == "open":
        set_state(uid, STATE_PL_PAY, {"lid": lid}, merge=False)
        lo = int(link.get("min_amount") or 0)
        hi = int(link.get("max_amount") or 0)
        hint = ""
        if lo:
            hint += f"\n🔽 حداقل: {money(lo)}"
        if hi:
            hint += f"\n🔼 حداکثر: {money(hi)}"
        return send(cid, (
            f"💰 مبلغ پرداخت\n━━━━━━━━━━━━━━\n\n"
            f"📋 {link.get('title')}\n{hint}\n\n"
            f"مبلغ مورد نظر را به {CURRENCY_LABEL} بنویسید:"
        ), kb_cancel())

    return _do_payment(cid, uid, link, int(link.get("amount") or 0))


def handle_open_amount(message):
    """کاربر مبلغ دلخواه را وارد کرد"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    d = get_state_data(uid)
    lid = d.get("lid")

    if text in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        return send(cid, "❌ لغو شد", kb_remove())

    link = get_link(lid)
    if not link:
        clear_state(uid)
        return send(cid, "❌ لینک یافت نشد", kb_remove())

    digits = re.sub(r"[^\d]", "", normalize_digits(text))
    if not digits:
        return send(cid, "⚠️ مبلغ را به عدد بنویسید:")
    rial = parse_money(digits)
    if rial <= 0:
        return send(cid, "⚠️ مبلغ باید بیشتر از صفر باشد:")

    lo = int(link.get("min_amount") or 0)
    hi = int(link.get("max_amount") or 0)
    if lo and rial < lo:
        return send(cid, f"⚠️ حداقل مبلغ {money(lo)} است:")
    if hi and rial > hi:
        return send(cid, f"⚠️ حداکثر مبلغ {money(hi)} است:")

    clear_state(uid)
    return _do_payment(cid, uid, link, rial)


def _do_payment(cid, uid, link, base):
    """ساخت تراکنش و هدایت به درگاه"""
    from payments import (calc_fee, fee_label, PAYMENT_METHODS,
                          get_cards, get_gateways, format_card, render,
                          PAYMENT_ENABLED, PAYMENT_PROVIDER_TOKEN,
                          STATE_RECEIPT, fmt)
    from bale_api import send_invoice

    method = link.get("method") or "bale_wallet"
    fee, total = calc_fee(base, method)
    import uuid as _uu
    payload = (f"pl{link['id']}u{uid}t{int(time.time())}"
               f"x{_uu.uuid4().hex[:6]}")

    pid = db_execute("""INSERT INTO paylink_payments
        (link_id, bale_user_id, amount, fee_amount, total_amount,
         method, status, payload)
        VALUES (?,?,?,?,?,?,'pending',?)""",
        (link["id"], uid, base, fee, total, method, payload))
    db_execute("UPDATE payment_links SET used_count=COALESCE(used_count,0)+1 "
               "WHERE id=?", (link["id"],))

    brk = ""
    if fee > 0:
        brk = ("\n\n🧾 ریز مبلغ:\n"
               f"   ▫️ مبلغ: {money(base)}\n"
               f"   ▫️ {fee_label(method)}: {money(fee)}\n"
               "   ━━━━━━━━━━\n"
               f"   💰 قابل پرداخت: {money(total)}")

    # 🏦 کیف پول بله
    if method == "bale_wallet":
        if not PAYMENT_ENABLED:
            return send(cid, "⚠️ درگاه پرداخت تنظیم نشده — با ادمین تماس بگیرید")
        # 🛡️ فاز ۱۸-ب — هشدار فیلترشکن
        from payments import send_vpn_warning, vpn_warn_inline
        send_vpn_warning(cid, "bale_wallet")
        prices = [{"label": str(link.get("title"))[:32], "amount": int(base)}]
        if fee > 0:
            prices.append({"label": fee_label(method)[:32],
                           "amount": int(fee)})
        res = send_invoice(
            cid, title=str(link.get("title"))[:32],
            description=(link.get("description")
                         or link.get("title") or "پرداخت")[:250],
            payload=payload, provider_token=PAYMENT_PROVIDER_TOKEN,
            prices=prices)
        if res.get("ok"):
            send(cid, f"💳 صورتحساب ارسال شد{brk}"
                      f"{vpn_warn_inline('bale_wallet')}")
            return pid
        db_execute("UPDATE paylink_payments SET status='failed' WHERE id=?",
                   (pid,))
        return send(cid, "❌ ساخت صورتحساب ناموفق بود")

    # 💳 کارت به کارت
    if method == "card":
        cards = get_cards()
        card = None
        if link.get("card_id"):
            card = next((c for c in cards if c["id"] == link["card_id"]), None)
        card = card or (cards[0] if cards else None)
        if not card:
            return send(cid, "⚠️ کارتی تنظیم نشده — با ادمین تماس بگیرید")
        set_state(uid, STATE_RECEIPT, {
            "paylink_pid": pid, "amount": total,
            "card_id": card["id"], "tx_id": None,
        }, merge=False)
        return send(cid, (
            f"💳 پرداخت کارت به کارت\n━━━━━━━━━━━━━━\n\n"
            f"📋 {link.get('title')}\n"
            f"💰 مبلغ: {money(total)}{brk}\n\n"
            f"🏦 {card.get('bank_name') or '-'}\n"
            f"👤 {card.get('card_holder_name') or '-'}\n"
            f"🔢 {format_card(card.get('card_number'))}\n\n"
            "📸 بعد از واریز، تصویر رسید را همینجا بفرستید."
        ), {"keyboard": [[{"text": "❌ انصراف از پرداخت"}],
                         [{"text": "🏠 منوی اصلی"}]],
            "resize_keyboard": True})

    # 🔗 درگاه سفارشی
    gws = get_gateways()
    gw = None
    if link.get("gateway_id"):
        gw = next((g for g in gws if g["id"] == link["gateway_id"]), None)
    gw = gw or (gws[0] if gws else None)
    if not gw:
        return send(cid, "⚠️ درگاهی تنظیم نشده — با ادمین تماس بگیرید")
    # 🛡️ فاز ۱۸-ب — هشدار فیلترشکن قبل از رفتن به درگاه
    from payments import send_vpn_warning, vpn_warn_inline
    send_vpn_warning(cid, "custom_gateway")

    url = gw.get("callback_url") or ""
    btns = []
    if url:
        sep = "&" if "?" in url else "?"
        btns.append([{"text": "💳 پرداخت آنلاین",
                      "url": f"{url}{sep}amount={total}&ref={payload}"}])
    btns.append([{"text": "🏠 منوی اصلی", "callback_data": "back_main"}])
    send(cid, (f"🔗 پرداخت آنلاین\n━━━━━━━━━━━━━━\n\n"
               f"📋 {link.get('title')}\n"
               f"💰 مبلغ: {money(total)}{brk}\n\n"
               f"🏦 درگاه: {gw.get('gateway_name')}"
               f"{vpn_warn_inline('custom_gateway')}"),
         {"inline_keyboard": btns})
    return pid


def mark_paid(payload, tx_id=""):
    """
    ✅ ثبت پرداخت موفق — از handle_successful_payment صدا زده می‌شود.
    خروجی: True اگر این payload مال لینک پرداخت بود.
    """
    p = db_execute("SELECT * FROM paylink_payments WHERE payload=?",
                   (payload,), fetch="one")
    if not p:
        return False
    if p.get("status") == "paid":
        return True

    db_execute("""UPDATE paylink_payments SET status='paid',
        transaction_id=?, paid_at=CURRENT_TIMESTAMP WHERE id=?""",
        (tx_id, p["id"]))
    db_execute("""UPDATE payment_links
        SET paid_count=COALESCE(paid_count,0)+1,
            total_collected=COALESCE(total_collected,0)+?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?""", (int(p.get("total_amount") or 0), p["link_id"]))

    link = get_link(p["link_id"])
    uid = p.get("bale_user_id")

    if uid:
        txt = (link or {}).get("success_text") or ""
        if not txt:
            txt = ("✅ پرداخت شما با موفقیت انجام شد\n"
                   "━━━━━━━━━━━━━━\n\n"
                   f"📋 {(link or {}).get('title') or '—'}\n"
                   f"💰 مبلغ: {money(p.get('total_amount'))}\n"
                   f"🔖 پیگیری: {tx_id or p.get('payload')}\n\n"
                   "💚 سپاس از شما.")
        try:
            send(uid, txt)
        except Exception as e:
            log(f"⚠️ اعلام پرداخت لینک: {e}")
        log_action(uid, "paylink_paid",
                   {"link": p["link_id"], "amount": p.get("total_amount")})

    if link and int(link.get("notify_admin") or 0):
        u = get_user(uid) or {}
        nm = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip()
        body = (f"💰 پرداخت جدید از لینک\n━━━━━━━━━━━━━━\n\n"
                f"📋 {link.get('title')}\n"
                f"👤 {nm or p.get('payer_name') or '—'}\n"
                f"📱 {u.get('mobile') or p.get('payer_mobile') or '—'}\n"
                f"💰 {money(p.get('total_amount'))}\n"
                f"🔖 {tx_id or p.get('payload')}")
        target = link.get("created_by") or SUPER_ADMIN_ID
        try:
            send(target, body)
        except Exception as e:
            log(f"⚠️ اعلان ادمین لینک: {e}")
    return True


# ==================== 📊 گزارش ====================
def show_payments(cid, uid, lid=None, page=0):
    """🧾 پرداخت‌های یک لینک یا همه"""
    if not _guard(cid, uid):
        return

    if lid:
        link = get_link(lid)
        if not link:
            return send(cid, "❌ یافت نشد")
        rows = db_execute("""SELECT p.*, u.first_name, u.last_name, u.mobile
            FROM paylink_payments p
            LEFT JOIN users u ON u.bale_user_id=p.bale_user_id
            WHERE p.link_id=? ORDER BY p.id DESC LIMIT 50""",
            (lid,), fetch="all") or []
        head = f"🧾 پرداخت‌های «{link.get('title')}»"
        back = f"pl_v_{lid}"
    else:
        rows = db_execute("""SELECT p.*, u.first_name, u.last_name, u.mobile,
            l.title link_title FROM paylink_payments p
            LEFT JOIN users u ON u.bale_user_id=p.bale_user_id
            LEFT JOIN payment_links l ON l.id=p.link_id
            ORDER BY p.id DESC LIMIT 50""", fetch="all") or []
        head = "📊 گزارش پرداخت‌های غیرمتمرکز"
        back = "pl_panel"

    paid = [r for r in rows if r.get("status") == "paid"]
    total = sum(int(r.get("total_amount") or 0) for r in paid)
    fees = sum(int(r.get("fee_amount") or 0) for r in paid)

    lines = [head, "━━━━━━━━━━━━━━",
             f"✅ موفق: {len(paid)}  |  ⏳ ناتمام: {len(rows) - len(paid)}",
             f"💰 مجموع: {money(total)}"]
    if fees:
        lines.append(f"💳 از این مبلغ کارمزد: {money(fees)}")
    lines.append("")

    if not rows:
        lines.append("📭 هنوز پرداختی ثبت نشده")
    for r in rows[:15]:
        ic = {"paid": "✅", "pending": "⏳",
              "failed": "❌"}.get(r.get("status"), "▫️")
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
        lines.append(f"{ic} {money(r.get('total_amount'))} — "
                     f"{nm or r.get('payer_name') or '—'}")
        if not lid and r.get("link_title"):
            lines.append(f"   📋 {str(r['link_title'])[:28]}")
        lines.append(f"   🕐 {_jd.fmt(r.get('created_at'), 'datetime')}")

    btns = []
    if paid:
        btns.append([{"text": "📤 خروجی Excel", "callback_data": "pl_exp"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": back}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def export_payments(cid, uid):
    """📤 خروجی Excel همه پرداخت‌های لینک"""
    if not _guard(cid, uid):
        return
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        return send(cid, "⚠️ نیاز به openpyxl:\npip install openpyxl")

    rows = db_execute("""SELECT p.*, u.first_name, u.last_name, u.mobile,
        l.title link_title, l.code FROM paylink_payments p
        LEFT JOIN users u ON u.bale_user_id=p.bale_user_id
        LEFT JOIN payment_links l ON l.id=p.link_id
        ORDER BY p.id DESC LIMIT 5000""", fetch="all") or []
    if not rows:
        return send(cid, "📭 پرداختی برای خروجی نیست")

    wb = Workbook()
    ws = wb.active
    ws.title = "پرداخت غیرمتمرکز"
    ws.sheet_view.rightToLeft = True
    heads = ["لینک", "کد", "پرداخت‌کننده", "موبایل",
             f"مبلغ({CURRENCY_LABEL})", f"کارمزد({CURRENCY_LABEL})",
             f"کل({CURRENCY_LABEL})", "روش", "وضعیت", "توضیح",
             "پیگیری", "تاریخ"]
    ws.append(heads)
    for i, _ in enumerate(heads, 1):
        c = ws.cell(row=1, column=i)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="00695C")
        c.alignment = Alignment(horizontal="center")

    for r in rows:
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
        ws.append([
            r.get("link_title") or "—", r.get("code") or "—",
            nm or r.get("payer_name") or "—",
            r.get("mobile") or r.get("payer_mobile") or "—",
            int(r.get("amount") or 0),
            int(r.get("fee_amount") or 0),
            int(r.get("total_amount") or 0),
            r.get("method") or "—", r.get("status") or "—",
            r.get("payer_note") or "", r.get("transaction_id") or "—",
            _jd.fmt(r.get('created_at'), 'datetime'),
        ])
    for col, wd in zip("ABCDEFGHIJKL",
                       (24, 14, 20, 14, 14, 14, 14, 12, 10, 24, 18, 18)):
        ws.column_dimensions[col].width = wd
    ws.freeze_panes = "A2"

    from pathlib import Path
    from config import IMPORT_DIR
    Path(IMPORT_DIR).mkdir(parents=True, exist_ok=True)
    out = (Path(IMPORT_DIR) /
           f"paylinks_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
    try:
        wb.save(out)
    except Exception as e:
        return send(cid, f"❌ خطا: {user_error_message(e)}")

    r = send_document(cid, str(out),
                      f"🔗 پرداخت‌های غیرمتمرکز ({len(rows)} مورد)")
    if not r or not r.get("ok"):
        send(cid, f"⚠️ ارسال ناموفق. فایل در سرور:\n{out}")
    log_action(uid, "paylink_export", {})
