"""
💳 سیستم پرداخت — فاز ۸
طبق معماری توافق‌شده: ۴ روش پرداخت

┌─────────────────────────────────────────────┐
│  ❌ غیرفعال (رایگان)                        │
│  💳 کارت به کارت                            │
│      ├── انتخاب از کارت‌های ثبت شده        │
│      └── ➕ ثبت شماره کارت جدید            │
│  🏦 درگاه پرداخت بله (کیف پول)             │
│  🔗 درگاه پرداخت سفارشی                     │
│      └── ➕ تعریف درگاه جدید               │
└─────────────────────────────────────────────┘

همه متن‌های پرداخت از پنل ادمین قابل تغییر است.
"""
import json
import re
import time
from datetime import datetime
from pathlib import Path

from config import (
    SUPER_ADMIN_ID, PAYMENT_PROVIDER_TOKEN, PAYMENT_ENABLED,
    PAYMENT_TEST_MODE, CURRENCY_LABEL, check_amount, FILES_DIR,
    money,
)
from database import db_execute, db_scalar, get_setting, set_setting, log
from auth import (
    get_user, get_user_by_id, set_state, get_state_name, get_state_data,
    update_state_data, clear_state, log_action, normalize_digits,
    is_admin as _is_admin,
)
from bale_api import (
    send, send_or_edit, send_photo, send_invoice, kb_cancel, kb_remove,
    kb_payment_settings, get_file_info, download_file, BTN_BACK,
)
import jalali as _jd

STATE_CARD_ADD = "pay_card_add"
STATE_GW_ADD = "pay_gw_add"
STATE_TEXT_EDIT = "pay_text_edit"
STATE_RECEIPT = "pay_receipt"
# 🆕 فاز ۱۳
STATE_PICK_METHOD = "pay_pick_method"
STATE_POINTS_CONFIRM = "pay_points_confirm"
STATE_PAY_NUM = "pay_num_edit"
STATE_PAY_FEE = "pay_fee_edit"   # 🆕 فاز ۱۶ — کارمزد درگاه

RECEIPTS_DIR = Path(FILES_DIR) / "receipts"


# ==================== روش‌های پرداخت ====================
PAYMENT_METHODS = {
    "none": {"icon": "❌", "name": "غیرفعال (رایگان)",
             "verify": "-", "desc": "رویداد رایگان است"},
    "card": {"icon": "💳", "name": "کارت به کارت",
             "verify": "manual", "desc": "کاربر واریز و رسید ارسال می‌کند"},
    "bale_wallet": {"icon": "🏦", "name": "کیف پول بله",
                    "verify": "auto", "desc": "پرداخت آنی و تأیید خودکار"},
    "custom_gateway": {"icon": "🔗", "name": "درگاه سفارشی",
                       "verify": "auto", "desc": "زرین‌پال، پی‌پینگ و..."},

    # ═══════════ 🆕 فاز ۱۳ ═══════════
    "onsite": {"icon": "💰", "name": "پرداخت در محل",
               "verify": "manual",
               "desc": "کاربر روز رویداد نقدی/کارتخوان پرداخت می‌کند"},
    "points": {"icon": "🏆", "name": "پرداخت با امتیاز",
               "verify": "auto",
               "desc": "کسر از امتیاز باشگاه کاربر — بدون پول"},
    "multi": {"icon": "🎛️", "name": "چند روشی (انتخاب کاربر)",
              "verify": "mixed",
              "desc": "کاربر خودش بین روش‌های مجاز انتخاب می‌کند"},

    # ═══════════ 🆕 فاز ۱۸-الف — پرداخت مرحله‌ای ═══════════
    "installment": {"icon": "📅", "name": "پرداخت اقساطی",
                    "verify": "mixed",
                    "desc": "مبلغ به چند قسط مساوی تقسیم می‌شود"},
    "sessions": {"icon": "🎟️", "name": "پرداخت جلسه‌ای",
                 "verify": "mixed",
                 "desc": "برای هر جلسه جداگانه پرداخت می‌شود"},
    "prepay": {"icon": "💵", "name": "پیش‌پرداخت + تسویه",
               "verify": "mixed",
               "desc": "بخشی الان، باقی‌مانده بعداً"},
}

# روش‌هایی که مرحله‌ای‌اند (طرح پرداخت دارند)
STAGED_METHODS = ["installment", "sessions", "prepay"]

# روش‌هایی که می‌توانند عضو حالت «چند روشی» باشند
MULTI_CHOICES = ["bale_wallet", "card", "custom_gateway", "onsite", "points"]

# ═══════════ 🏆 پرداخت با امتیاز — تنظیمات ═══════════
#   نرخ: هر «۱ امتیاز» چند ریال ارزش دارد؟ (همه‌جا ریال)
# ═══════════ 💳 کارمزد پرداخت — فاز ۱۷ (هر روش مستقل) ═══════════
#
# درخواست کاربر: «کارمزد درگاه پرداخت روی تمامی درگاه ها ادمین بتونه
#   فعال کنه نه فقط یکی، با هر روشی کارمزد و درصد قابل تعیین باشه»
#
# حالا هر روش پرداخت تنظیمات کارمزد مستقل دارد:
#   pay_fee_<method>_on       فعال/غیرفعال
#   pay_fee_<method>_pct      درصد
#   pay_fee_<method>_fix      مبلغ ثابت (ریال)
#   pay_fee_<method>_min      حداقل کارمزد (ریال)
#   pay_fee_<method>_max      سقف کارمزد (ریال، ۰=بی‌سقف)
#   pay_fee_<method>_label    عنوان نمایشی
#
# 🔒 فقط سوپرادمین (fin_settings در SUPER_ONLY است)

# روش‌هایی که می‌توانند کارمزد داشته باشند
FEE_METHODS = ["custom_gateway", "bale_wallet", "card", "onsite", "points"]

DEFAULT_FEE_LABEL = "کارمزد پرداخت"


def _fk(method, part):
    """کلید تنظیم کارمزد یک روش"""
    return f"pay_fee_{method}_{part}"


def fee_enabled(method="custom_gateway"):
    """آیا کارمزد این روش فعال است؟"""
    if method not in FEE_METHODS:
        return False
    return get_setting(_fk(method, "on"), "0") == "1"


def any_fee_enabled():
    """آیا حداقل یک روش کارمزد دارد؟"""
    return any(fee_enabled(m) for m in FEE_METHODS)


def fee_percent(method="custom_gateway"):
    """درصد کارمزد این روش — اعشار هم می‌پذیرد (مثلاً ۲.۵)"""
    try:
        v = float(normalize_digits(str(get_setting(_fk(method, "pct"), "0"))))
    except (ValueError, TypeError):
        v = 0.0
    return max(0.0, min(100.0, v))


def fee_label(method="custom_gateway"):
    """عنوان نمایشی کارمزد این روش"""
    v = (get_setting(_fk(method, "label"), "") or "").strip()
    return v or DEFAULT_FEE_LABEL


def _fee_amount(method, part):
    """مبلغ ثابت/حداقل/سقف — ریال (بدون تبدیل)"""
    try:
        t = int(normalize_digits(str(get_setting(_fk(method, part), "0")))
                or 0)
    except (ValueError, TypeError):
        t = 0
    return max(0, t)


def fee_fixed(method="custom_gateway"):
    return _fee_amount(method, "fix")


def calc_fee(amount, method="custom_gateway"):
    """
    💳 محاسبه کارمزد یک روش پرداخت.

    فرمول:  کارمزد = (مبلغ × درصد) + مبلغ ثابت
    سپس بین «حداقل» و «سقف» محدود می‌شود.

    خروجی: (کارمزد_ریال، مبلغ_نهایی_ریال)
    """
    try:
        base = max(0, int(amount or 0))
    except (TypeError, ValueError):
        return 0, 0
    if base <= 0 or method not in FEE_METHODS or not fee_enabled(method):
        return 0, base

    pct = fee_percent(method)
    fix = fee_fixed(method)
    if pct <= 0 and fix <= 0:
        return 0, base

    fee = int(round(base * pct / 100.0)) + fix
    lo = _fee_amount(method, "min")
    hi = _fee_amount(method, "max")
    if lo and fee < lo:
        fee = lo
    if hi and fee > hi:
        fee = hi
    return max(0, fee), base + max(0, fee)


def fee_breakdown(amount, method="custom_gateway"):
    """
    🧾 متن ریز مبلغ برای نمایش به کاربر.
    اگر کارمزد صفر باشد، رشته خالی برمی‌گرداند.
    """
    fee, total = calc_fee(amount, method)
    if fee <= 0:
        return ""
    pct = fee_percent(method)
    fix = fee_fixed(method)
    if pct > 0 and fix > 0:
        how = f"{pct:g}٪ + {money(fix)}"
    elif pct > 0:
        how = f"{pct:g}٪"
    else:
        how = "ثابت"
    return ("🧾 ریز مبلغ:\n"
            f"   ▫️ مبلغ اصلی: {money(amount)}\n"
            f"   ▫️ {fee_label(method)} ({how}): {money(fee)}\n"
            "   ━━━━━━━━━━\n"
            f"   💰 قابل پرداخت: {money(total)}")


def seed_fee_settings():
    """ثبت تنظیمات پیش‌فرض کارمزد همه روش‌ها + مهاجرت از فاز ۱۶"""
    # 🔄 مهاجرت: تنظیمات تک‌روشی قدیمی → درگاه سفارشی
    old_on = db_execute("SELECT value FROM settings WHERE key='pay_fee_enabled'",
                        fetch="one")
    if old_on:
        pairs = [("pay_fee_enabled", "on"), ("pay_fee_percent", "pct"),
                 ("pay_fee_label", "label"), ("pay_fee_min", "min"),
                 ("pay_fee_max", "max")]
        for old_key, part in pairs:
            row = db_execute("SELECT value FROM settings WHERE key=?",
                             (old_key,), fetch="one")
            nk = _fk("custom_gateway", part)
            if row and not db_execute("SELECT key FROM settings WHERE key=?",
                                      (nk,), fetch="one"):
                set_setting(nk, row.get("value") or "",
                            "کارمزد درگاه سفارشی", "payment")
        db_execute("DELETE FROM settings WHERE key IN "
                   "('pay_fee_enabled','pay_fee_percent','pay_fee_label',"
                   "'pay_fee_min','pay_fee_max')")
        log("♻️ تنظیمات کارمزد به حالت چندروشی مهاجرت کرد")

    for m in FEE_METHODS:
        nm = PAYMENT_METHODS.get(m, {}).get("name", m)
        for part, default in (("on", "0"), ("pct", "0"), ("fix", "0"),
                              ("min", "0"), ("max", "0"),
                              ("label", DEFAULT_FEE_LABEL)):
            k = _fk(m, part)
            if not db_execute("SELECT key FROM settings WHERE key=?",
                              (k,), fetch="one"):
                set_setting(k, default, f"کارمزد {nm} — {part}", "payment")


POINTS_SETTINGS = [
    ("pay_points_enabled",  "🏆 پرداخت با امتیاز فعال", "0"),
    ("pay_points_rate",     "💱 ارزش هر امتیاز (ریال)", "10000"),
    ("pay_points_max_pct",  "📊 حداکثر درصد قابل پرداخت با امتیاز", "100"),
    ("pay_points_min_keep", "🔒 حداقل امتیاز باقی‌مانده", "0"),
]


def points_enabled():
    return get_setting("pay_points_enabled", "0") == "1"


def points_rate_rial():
    """ارزش هر امتیاز به ریال"""
    try:
        v = int(normalize_digits(str(
            get_setting("pay_points_rate", "10000"))) or 10000)
    except (ValueError, TypeError):
        v = 10000
    return max(1, v)


def points_max_pct():
    try:
        p = int(normalize_digits(str(
            get_setting("pay_points_max_pct", "100"))) or 100)
    except (ValueError, TypeError):
        p = 100
    return max(0, min(100, p))


def points_min_keep():
    try:
        return max(0, int(normalize_digits(str(
            get_setting("pay_points_min_keep", "0"))) or 0))
    except (ValueError, TypeError):
        return 0


def rial_to_points(rial):
    """چند امتیاز لازم است تا این مبلغ ریالی پوشش داده شود؟ (به بالا رند)"""
    r = points_rate_rial()
    try:
        amount = max(0, int(rial or 0))
    except (TypeError, ValueError):
        return 0
    return (amount + r - 1) // r


def points_to_rial(points):
    """این تعداد امتیاز چقدر ارزش ریالی دارد؟"""
    try:
        return max(0, int(points or 0)) * points_rate_rial()
    except (TypeError, ValueError):
        return 0


def points_quote(uid, amount):
    """
    🏆 محاسبه اینکه کاربر چقدر از این مبلغ را می‌تواند با امتیاز بدهد.

    خروجی: dict با کلیدهای
      ok        آیا اصلاً امکان‌پذیر است
      have      امتیاز فعلی کاربر
      usable    امتیازی که مجاز است خرج کند
      need_full امتیاز لازم برای پرداخت کامل
      use       امتیازی که واقعاً کسر می‌شود
      covered   مبلغ ریالی پوشش‌داده‌شده
      rest      باقی‌مانده ریالی که باید نقدی بدهد
      full      آیا کل مبلغ با امتیاز پوشش داده شد
      reason    اگر ok=False چرا
    """
    out = {"ok": False, "have": 0, "usable": 0, "need_full": 0, "use": 0,
           "covered": 0, "rest": int(amount or 0), "full": False, "reason": ""}
    try:
        amount = max(0, int(amount or 0))
    except (TypeError, ValueError):
        amount = 0
    out["rest"] = amount

    if not points_enabled():
        out["reason"] = "پرداخت با امتیاز غیرفعال است"
        return out
    if amount <= 0:
        out["reason"] = "مبلغی برای پرداخت نیست"
        return out

    u = get_user(uid) or {}
    have = int(u.get("total_points") or 0)
    keep = points_min_keep()
    usable = max(0, have - keep)
    need_full = rial_to_points(amount)

    # سقف درصدی
    pct = points_max_pct()
    cap_rial = amount * pct // 100
    cap_points = rial_to_points(cap_rial) if pct < 100 else need_full
    usable = min(usable, cap_points)

    out.update({"have": have, "usable": usable, "need_full": need_full})

    if usable <= 0:
        out["reason"] = ("امتیاز کافی ندارید"
                         if have <= keep else "سقف مجاز صفر است")
        return out

    use = min(usable, need_full)
    covered = min(amount, points_to_rial(use))
    out.update({
        "ok": True, "use": use, "covered": covered,
        "rest": max(0, amount - covered),
        "full": covered >= amount,
    })
    return out


def spend_points(uid, points, reason=""):
    """
    🔴 کسر اتمیک امتیاز — شرط داخل خود UPDATE است تا race نشود.
    خروجی: (ok, remaining)
    """
    try:
        pts = int(points or 0)
    except (TypeError, ValueError):
        return False, 0
    if pts <= 0:
        return True, int((get_user(uid) or {}).get("total_points") or 0)

    before = int((get_user(uid) or {}).get("total_points") or 0)
    if before < pts:
        return False, before

    db_execute("""UPDATE users SET total_points = total_points - ?
        WHERE bale_user_id=? AND COALESCE(total_points,0) >= ?""",
        (pts, uid, pts))
    after = int((get_user(uid) or {}).get("total_points") or 0)
    if after != before - pts:
        return False, after
    log_action(uid, "points_spent", {"points": pts, "reason": reason})
    return True, after


def refund_points(uid, points, reason=""):
    """برگرداندن امتیاز (مثلاً وقتی پرداخت باقی‌مانده ناموفق شد)"""
    try:
        pts = int(points or 0)
    except (TypeError, ValueError):
        return False
    if pts <= 0:
        return True
    db_execute("UPDATE users SET total_points=COALESCE(total_points,0)+? "
               "WHERE bale_user_id=?", (pts, uid))
    log_action(uid, "points_refund", {"points": pts, "reason": reason})
    return True


def allowed_methods(obj):
    """
    🎛️ روش‌های پرداخت مجاز یک رویداد/فرم.

    اگر payment_method == 'multi' باشد، ستون payment_methods
    (رشته‌ای مثل "bale_wallet,card,onsite") خوانده می‌شود.
    در غیر این صورت همان تک روش برمی‌گردد.
    """
    method = (obj or {}).get("payment_method") or "none"
    if method != "multi":
        return [method] if method in PAYMENT_METHODS else ["none"]

    raw = (obj or {}).get("payment_methods") or ""
    out = []
    for m in str(raw).split(","):
        m = m.strip()
        if m in MULTI_CHOICES and m not in out:
            out.append(m)
    if not out:
        # چیزی انتخاب نشده → امن‌ترین حالت
        out = ["bale_wallet"] if PAYMENT_ENABLED else ["card"]
    return out


# ══════════════════════════════════════════════════════════
# 🎯 فاز ۱۸-الف — لایه «مقصد پرداخت»
#
# 🔴 باگ ریشه‌ای که رفع می‌کند:
#    موتور پرداخت فقط برای رویداد نوشته شده بود و همه‌جا
#    `UPDATE event_registrations` می‌زد. وقتی فرم‌ساز یک آیتم
#    قیمت‌دار داشت، pseudo-event می‌ساخت ولی هیچ ردیفی در
#    event_registrations نبود → پرداخت نیمه‌کاره می‌ماند و
#    کاربر پیام «درگاه پرداختی فعال نیست» می‌گرفت.
#
#    حالا هر پرداخت یک «مقصد» دارد: event یا form.
# ══════════════════════════════════════════════════════════
def pay_target(obj):
    """
    مقصد پرداخت را تشخیص می‌دهد.
    خروجی: ("form", response_id) یا ("event", registration_id)
    """
    if (obj or {}).get("_form_response_id"):
        return "form", int(obj["_form_response_id"])
    return "event", None


def mark_paid(obj, rid, amount, ref=None, full=True):
    """
    💾 ثبت پرداخت روی مقصد درست — رویداد یا فرم.

    این تابع جایگزین همه `UPDATE event_registrations` های
    پراکنده شد تا فرم‌ها هم درست به‌روز شوند.
    """
    kind, frid = pay_target(obj)
    try:
        if kind == "form" and frid:
            db_execute(
                "UPDATE form_responses SET amount_paid=?, "
                "payment_status=?, transaction_id=COALESCE(?,transaction_id) "
                "WHERE id=?",
                (int(amount or 0), "paid" if full else "partial",
                 ref, frid))
            return True
        if rid:
            db_execute(
                "UPDATE event_registrations SET amount_paid=?, "
                "transaction_id=COALESCE(?,transaction_id), "
                "paid_at=CURRENT_TIMESTAMP WHERE id=?",
                (int(amount or 0), ref, rid))
            return True
    except Exception as e:
        log(f"⚠️ mark_paid: {e}")
    return False


def mark_payload(obj, rid, payload):
    """ذخیره payload روی مقصد درست"""
    kind, frid = pay_target(obj)
    try:
        if kind == "form" and frid:
            db_execute("UPDATE form_responses SET payment_payload=? "
                       "WHERE id=?", (payload, frid))
        elif rid:
            db_execute("UPDATE event_registrations SET payment_payload=? "
                       "WHERE id=?", (payload, rid))
    except Exception as e:
        log(f"⚠️ mark_payload: {e}")


def finish_target(cid, uid, obj, rid):
    """
    🏁 بعد از پرداخت موفق، مقصد را نهایی کن.
    رویداد → صدور بلیت · فرم → finalize و کد پیگیری
    """
    kind, frid = pay_target(obj)
    try:
        if kind == "form" and frid:
            import form_fill as _ff
            r = db_execute("SELECT * FROM form_responses WHERE id=?",
                           (frid,), fetch="one")
            return _ff.finalize(cid, uid, frid,
                                (r or {}).get("score"),
                                (r or {}).get("max_score"))
        import events as _ev
        ev = obj if obj.get("start_date") else _ev.get_event(obj.get("id"))
        if ev and rid:
            return _ev.finish_registration(cid, uid, ev, rid)
    except Exception as e:
        log(f"⚠️ finish_target: {e}")
    return None


# ══════════════════════════════════════════════════════════
# 🛡️ فاز ۱۸-ب — هشدار خاموش کردن فیلترشکن
#
# 🎯 درخواست کاربر:
#    «برای ورود به درگاه پرداخت‌ها حتما هشدار بده VPN خاموش کنن کاربرا.
#     بجز برای کارت به کارت و امتیاز این هشدار روی همه درگاه‌ها بزار»
#
# 🔍 چرا لازم است؟
#    درگاه‌های بانکی ایران (شاپرک) و کیف پول بله ترافیک خارج از کشور را
#    رد می‌کنند. کاربری که VPN روشن دارد یا اصلاً به صفحه پرداخت نمی‌رسد
#    یا وسط تراکنش قطع می‌شود و پول بلاتکلیف می‌ماند.
#
# 📌 روش‌هایی که هشدار می‌گیرند (اتصال به سرور بانکی دارند):
#      🏦 کیف پول بله · 🔗 درگاه سفارشی · و حالت‌های مرحله‌ای
#    روش‌هایی که هشدار نمی‌گیرند (آفلاین‌اند):
#      💳 کارت به کارت (کاربر خودش در اپ بانک واریز می‌کند)
#      🏆 پرداخت با امتیاز (اصلاً پول جابه‌جا نمی‌شود)
#      💰 پرداخت در محل (روز رویداد، نقدی)
# ══════════════════════════════════════════════════════════

# روش‌هایی که به درگاه واقعی وصل می‌شوند → هشدار لازم دارند
VPN_WARN_METHODS = {"bale_wallet", "custom_gateway"}

# روش‌هایی که عمداً هشدار نمی‌گیرند (درخواست صریح کاربر)
VPN_SKIP_METHODS = {"card", "points", "onsite", "none"}

DEFAULT_VPN_WARN = (
    "🛡️ لطفاً فیلترشکن را خاموش کنید\n"
    "━━━━━━━━━━━━━━\n\n"
    "درگاه‌های بانکی ایران با فیلترشکن (VPN) کار نمی‌کنند.\n\n"
    "🔴 اگر روشن باشد ممکن است:\n"
    "   • صفحه پرداخت باز نشود\n"
    "   • وسط پرداخت قطع شود\n"
    "   • پول کم شود ولی ثبت نگردد\n\n"
    "✅ لطفاً قبل از ادامه، VPN را خاموش کنید.\n\n"
    "🙏 ممنون از همراهی‌تان 💚"
)


def vpn_warn_enabled():
    """آیا هشدار فیلترشکن فعال است؟ (قابل خاموش کردن از پنل ادمین)"""
    return get_setting("pay_vpn_warn_on", "1") == "1"


def vpn_warn_needed(method):
    """
    آیا این روش پرداخت به هشدار فیلترشکن نیاز دارد؟

    ⚠️ کارت به کارت و امتیاز عمداً مستثنا هستند — درخواست صریح کاربر.
    """
    if not vpn_warn_enabled():
        return False
    m = (method or "").strip()
    if m in VPN_SKIP_METHODS:
        return False
    return m in VPN_WARN_METHODS


def vpn_warn_text():
    """متن هشدار — از پنل ادمین قابل ویرایش است"""
    return (get_setting("pay_txt_vpn_warn", "") or DEFAULT_VPN_WARN).strip()


def send_vpn_warning(cid, method, ev=None):
    """
    🛡️ هشدار خاموش کردن فیلترشکن — قبل از هدایت به درگاه.

    🔴 فاز ۲۳: اگر هشدار قبلاً در صورتحساب آمده (`_quiet_vpn`)
       دوباره فرستاده نمی‌شود. کاربر گفت: «هزارتا پیام نیاد».

    خروجی: True اگر هشدار فرستاده شد.
    """
    if ev and ev.get("_quiet_vpn"):
        return False
    if not vpn_warn_needed(method):
        return False
    send(cid, vpn_warn_text())
    return True


def vpn_warn_inline(method):
    """
    نسخه کوتاه برای چسباندن ته پیام پرداخت (وقتی پیام جدا نمی‌خواهیم).
    درخواست کاربر: «پیام جدید باز نکن تا جایی که راه می‌دهد»
    """
    if not vpn_warn_needed(method):
        return ""
    short = (get_setting("pay_txt_vpn_short", "") or "").strip()
    if not short:
        short = ("🛡️ لطفاً قبل از پرداخت، فیلترشکن (VPN) را خاموش کنید — "
                 "درگاه‌های بانکی با آن کار نمی‌کنند.")
    return "\n\n" + short


def _payload(prefix, ev, uid, rid):
    """
    🔑 شناسه یکتای پرداخت.

    🔴 باگ رفع‌شده (فاز ۱۸-الف): قبلاً فقط ثانیه در payload بود، پس اگر
       کاربر دو بار پشت‌سرهم اقدام می‌کرد یا دو قسط همزمان ساخته می‌شد،
       UNIQUE constraint می‌خورد و تراکنش بی‌صدا از دست می‌رفت.
    """
    import uuid
    return (f"{prefix}{(ev or {}).get('id') or 0}u{uid}r{rid or 0}"
            f"t{int(time.time())}x{uuid.uuid4().hex[:6]}")


def _frid(obj):
    """شناسه پاسخ فرم (اگر پرداخت مربوط به فرم باشد) وگرنه None"""
    v = (obj or {}).get("_form_response_id")
    try:
        return int(v) if v else None
    except (TypeError, ValueError):
        return None


def _tag_plan_part(txid, obj):
    """
    💠 فاز ۱۸-الف — تراکنش را به قسط مربوطه گره می‌زند.
    بدون این، بعد از پرداخت معلوم نبود کدام قسط تسویه شده.
    """
    part = (obj or {}).get("_plan_part")
    if not (txid and part):
        return
    try:
        db_execute("UPDATE transactions SET plan_id=?, installment_no=? "
                   "WHERE id=?", (None, int(part), txid))
        db_execute("UPDATE payment_schedules SET transaction_id=? WHERE id=?",
                   (txid, int(part)))
    except Exception as e:
        log(f"⚠️ اتصال تراکنش به قسط: {e}")


def method_available(m):
    """آیا این روش عملاً قابل استفاده است؟ خروجی: (ok, دلیل)"""
    if m == "card":
        return (True, "") if get_cards() else (False, "کارتی ثبت نشده")
    if m == "bale_wallet":
        return (True, "") if PAYMENT_ENABLED else (False, "توکن تنظیم نشده")
    if m == "custom_gateway":
        return (True, "") if get_gateways() else (False, "درگاهی تعریف نشده")
    if m == "points":
        return (True, "") if points_enabled() else (False, "غیرفعال است")
    if m in ("onsite", "none"):
        return True, ""
    if m in ("installment", "sessions", "prepay"):
        # مرحله‌ای فقط وقتی معنی دارد که حداقل یک روش پایه سالم باشد
        base = best_available_method()
        return (True, "") if base else (False, "روش پرداخت پایه ندارید")
    return False, "نامعتبر"


# متن‌های قابل ویرایش — طبق درخواست شما
PAYMENT_TEXTS = [
    ("pay_txt_card_intro", "💳 راهنمای کارت به کارت",
     "💳 پرداخت کارت به کارت\n"
     "━━━━━━━━━━━━━━\n\n"
     "لطفاً مبلغ {amount} {currency} را به کارت زیر واریز کنید:\n\n"
     "🏦 بانک: {bank}\n"
     "👤 به نام: {holder}\n"
     "🔢 شماره کارت:\n{card}\n\n"
     "📸 پس از واریز، تصویر رسید را همینجا ارسال کنید.\n"
     "⏳ پس از تأیید ادمین، ثبت‌نام شما قطعی می‌شود."),

    ("pay_txt_card_received", "📸 پیام دریافت رسید",
     "✅ رسید شما دریافت شد\n"
     "━━━━━━━━━━━━━━\n\n"
     "🔖 شماره پیگیری: #{ref}\n"
     "⏳ در انتظار بررسی ادمین\n\n"
     "💡 پس از تأیید، بلیت شما صادر می‌شود."),

    ("pay_txt_card_approved", "✅ تأیید رسید",
     "🎉 پرداخت شما تأیید شد!\n\n"
     "💰 مبلغ: {amount} {currency}\n"
     "🎫 ثبت‌نام شما قطعی شد."),

    ("pay_txt_card_rejected", "❌ رد رسید",
     "❌ رسید شما تأیید نشد\n\n"
     "📄 دلیل: {reason}\n\n"
     "💡 لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."),

    ("pay_txt_wallet_intro", "🏦 راهنمای کیف پول بله",
     "🏦 پرداخت با کیف پول بله\n"
     "━━━━━━━━━━━━━━\n\n"
     "💰 مبلغ: {amount} {currency}\n\n"
     "روی فاکتور بالا بزنید و پرداخت کنید.\n"
     "✅ تأیید آنی و خودکار است."),

    ("pay_txt_wallet_success", "✅ پرداخت موفق کیف پول",
     "✅ پرداخت موفق\n"
     "━━━━━━━━━━━━━━\n\n"
     "💰 مبلغ: {amount} {currency}\n"
     "🧾 شماره پیگیری: {ref}\n\n"
     "🎫 در حال صدور بلیت..."),

    ("pay_txt_gateway_intro", "🔗 راهنمای درگاه سفارشی",
     "🔗 پرداخت آنلاین\n"
     "━━━━━━━━━━━━━━\n\n"
     "💰 مبلغ: {amount} {currency}\n"
     "🏦 درگاه: {gateway}\n\n"
     "روی دکمه زیر بزنید تا به صفحه پرداخت منتقل شوید."),

    # ═══════════ 🆕 فاز ۱۸-ب — هشدار فیلترشکن ═══════════
    ("pay_txt_vpn_warn", "🛡️ هشدار خاموش کردن فیلترشکن",
     DEFAULT_VPN_WARN),

    ("pay_txt_vpn_short", "🛡️ یادآوری کوتاه فیلترشکن",
     "🛡️ لطفاً قبل از پرداخت، فیلترشکن (VPN) را خاموش کنید — "
     "درگاه‌های بانکی با آن کار نمی‌کنند."),

    ("pay_txt_failed", "⚠️ پیام پرداخت ناموفق",
     "❌ پرداخت انجام نشد\n\n"
     "💡 لطفاً دوباره تلاش کنید.\n"
     "اگر مبلغ کم شده، تا ۷۲ ساعت برمی‌گردد."),

    ("pay_txt_pending", "⏳ پیام در انتظار پرداخت",
     "⏳ پرداخت شما تکمیل نشده\n\n"
     "💡 برای قطعی شدن ثبت‌نام، پرداخت را کامل کنید."),

    ("pay_txt_refund", "💸 پیام بازگشت وجه",
     "💸 وجه شما بازگردانده شد\n\n"
     "💰 مبلغ: {amount} {currency}\n"
     "📄 دلیل: {reason}"),

    # ═══════════ 🆕 فاز ۱۳ ═══════════
    ("pay_txt_choose", "🎛️ پیام انتخاب روش پرداخت",
     "💳 روش پرداخت را انتخاب کنید\n"
     "━━━━━━━━━━━━━━\n\n"
     "📋 {title}\n"
     "💰 مبلغ: {amount} {currency}\n\n"
     "👇 یکی از روش‌های زیر را بزنید:"),

    ("pay_txt_onsite", "💰 راهنمای پرداخت در محل",
     "✅ ثبت‌نام شما ثبت شد\n"
     "━━━━━━━━━━━━━━\n\n"
     "💰 مبلغ {amount} {currency} را روز رویداد در محل پرداخت کنید.\n"
     "📍 نقدی یا با کارتخوان\n\n"
     "🔖 کد پیگیری: {ref}\n\n"
     "💡 لطفاً کد بلیت خود را همراه داشته باشید."),

    ("pay_txt_points_offer", "🏆 پیشنهاد پرداخت با امتیاز",
     "🏆 پرداخت با امتیاز\n"
     "━━━━━━━━━━━━━━\n\n"
     "💰 مبلغ: {amount} {currency}\n"
     "🏅 امتیاز شما: {have}\n"
     "💱 ارزش هر امتیاز: {rate} {currency}\n\n"
     "{detail}"),

    ("pay_txt_points_done", "✅ پرداخت با امتیاز موفق",
     "🎉 پرداخت با امتیاز انجام شد!\n"
     "━━━━━━━━━━━━━━\n\n"
     "🏅 امتیاز کسرشده: {used}\n"
     "💰 معادل: {covered} {currency}\n"
     "🏆 امتیاز باقیمانده: {left}\n\n"
     "✅ ثبت‌نام شما قطعی شد."),

    ("pay_txt_points_partial", "🧮 پرداخت ترکیبی امتیاز + نقدی",
     "🧮 پرداخت ترکیبی\n"
     "━━━━━━━━━━━━━━\n\n"
     "🏅 امتیاز کسرشده: {used}  (معادل {covered} {currency})\n"
     "💳 باقی‌مانده نقدی: {rest} {currency}\n\n"
     "👇 حالا باقی‌مانده را پرداخت کنید:"),

    ("pay_txt_points_low", "🔒 امتیاز کافی نیست",
     "🔒 امتیاز کافی ندارید\n"
     "━━━━━━━━━━━━━━\n\n"
     "🏅 امتیاز شما: {have}\n"
     "🎯 امتیاز لازم: {need}\n\n"
     "💡 با شرکت در رویدادها امتیاز جمع کنید."),
]


def seed_payment_texts():
    """ثبت متن‌های پیش‌فرض پرداخت"""
    for key, title, default in PAYMENT_TEXTS:
        if not db_execute("SELECT key FROM settings WHERE key=?", (key,), fetch="one"):
            set_setting(key, default, title, "payment")
    # 🆕 فاز ۱۳ — تنظیمات عددی پرداخت با امتیاز
    for key, title, default in POINTS_SETTINGS:
        if not db_execute("SELECT key FROM settings WHERE key=?",
                          (key,), fetch="one"):
            set_setting(key, default, title, "payment")
    seed_fee_settings()
    if not db_execute("SELECT key FROM settings WHERE key=?",
                      ("pay_default_methods",), fetch="one"):
        set_setting("pay_default_methods", "bale_wallet,card",
                    "🧩 روش‌های پیش‌فرض چند روشی", "payment")


def render(key, **kw):
    """جایگزینی متغیرها در متن پرداخت"""
    default = next((d for k, t, d in PAYMENT_TEXTS if k == key), "")
    txt = get_setting(key, default)
    kw.setdefault("currency", CURRENCY_LABEL)
    for k, v in kw.items():
        txt = txt.replace("{" + k + "}", str(v if v is not None else "-"))
    return txt


def fmt(rial):
    """💰 نمایش مبلغ — ریال، بدون تبدیل (به config.money وصل است)"""
    from config import money
    return money(rial, with_unit=False).replace(",", "٬")


def fmt_rial(rial):
    """هم‌معنیِ fmt() — همه‌چیز ریال است"""
    return fmt(rial)


def _guard(cid, uid):
    if not _is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    return True


# ==================== جداول ====================
def init_payment_tables():
    from database import ensure_table

    ensure_table("bank_cards", {
        "owner_id": "INTEGER",
        "card_number": "TEXT",
        "card_holder_name": "TEXT",
        "bank_name": "TEXT",
        "sheba_number": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "is_default": "INTEGER DEFAULT 0",
        "note": "TEXT",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    })

    ensure_table("payment_gateways", {
        "owner_id": "INTEGER",
        "gateway_name": "TEXT",
        "gateway_type": "TEXT DEFAULT 'zarinpal'",
        "merchant_id": "TEXT",
        "api_key": "TEXT",
        "callback_url": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    })

    ensure_table("payment_receipts", {
        "transaction_id": "INTEGER",
        "event_id": "INTEGER",
        "registration_id": "INTEGER",
        # 🆕 فاز ۱۸-الف — رسید مربوط به فرم‌ساز
        "form_response_id": "INTEGER",
        "bale_user_id": "INTEGER",
        "amount": "INTEGER",
        "card_id": "INTEGER",
        "photo_path": "TEXT",
        "photo_file_id": "TEXT",
        "ref_code": "TEXT",
        "status": "TEXT DEFAULT 'pending'",
        "reviewed_by": "INTEGER",
        "reviewed_at": "TIMESTAMP",
        "reject_reason": "TEXT",
        "shared_task_id": "TEXT",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    })

    for q in [
        "CREATE INDEX IF NOT EXISTS idx_cards_active ON bank_cards(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_gw_active ON payment_gateways(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_rcp_status ON payment_receipts(status)",
        "CREATE INDEX IF NOT EXISTS idx_rcp_user ON payment_receipts(bale_user_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_rcp_shared_task ON payment_receipts(shared_task_id) WHERE shared_task_id IS NOT NULL",
    ]:
        db_execute(q)

    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    seed_payment_texts()


# ==================== کارت‌های بانکی ====================
def normalize_card(num):
    """نرمال‌سازی شماره کارت"""
    n = normalize_digits(str(num or ""))
    n = re.sub(r"[^\d]", "", n)
    return n if len(n) == 16 else None


def mask_card(num):
    n = str(num or "")
    if len(n) != 16:
        return n
    return f"{n[:4]}-****-****-{n[12:]}"


def format_card(num):
    n = str(num or "")
    if len(n) != 16:
        return n
    return f"{n[:4]}-{n[4:8]}-{n[8:12]}-{n[12:]}"


def luhn_valid(num):
    """اعتبارسنجی شماره کارت با الگوریتم Luhn"""
    n = str(num or "")
    if len(n) != 16 or not n.isdigit():
        return False
    total = 0
    for i, ch in enumerate(n):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


IRAN_BANKS = {
    "603799": "ملی", "589210": "سپه", "627648": "توسعه صادرات",
    "627961": "صنعت و معدن", "603770": "کشاورزی", "628023": "مسکن",
    "627760": "پست بانک", "502908": "توسعه تعاون", "627412": "اقتصاد نوین",
    "622106": "پارسیان", "639194": "پارسیان", "627884": "پارسیان",
    "502229": "پاسارگاد", "639347": "پاسارگاد", "627488": "کارآفرین",
    "502910": "کارآفرین", "621986": "سامان", "639346": "سینا",
    "639607": "سرمایه", "636214": "آینده", "502806": "شهر",
    "504706": "شهر", "639217": "کشاورزی", "628157": "توسعه",
    "505785": "دی", "636795": "مرکزی", "639599": "قوامین",
    "504172": "رسالت", "605694": "پارسیان", "628158": "انصار",
    "627381": "انصار", "639370": "مهر اقتصاد", "606373": "قرض‌الحسنه مهر",
    "610433": "ملت", "991975": "ملت", "589463": "رفاه",
    "621986 ": "سامان", "507677": "نور", "636949": "حکمت ایرانیان",
}


def detect_bank(card):
    n = str(card or "")
    if len(n) >= 6:
        return IRAN_BANKS.get(n[:6], "")
    return ""


def get_cards(active_only=True):
    q = "SELECT * FROM bank_cards"
    if active_only:
        q += " WHERE is_active=1"
    q += " ORDER BY is_default DESC, id DESC"
    return db_execute(q, fetch="all") or []


def get_card(cid_):
    return db_execute("SELECT * FROM bank_cards WHERE id=?", (cid_,), fetch="one")


def show_cards(cid, uid):
    if not _guard(cid, uid):
        return
    cards = db_execute("SELECT * FROM bank_cards ORDER BY is_default DESC, id DESC",
                       fetch="all") or []

    lines = ["💳 کارت‌های بانکی", "━━━━━━━━━━━━━━", ""]
    if not cards:
        lines += ["📭 هنوز کارتی ثبت نشده", "",
                  "💡 برای رویدادهای «کارت به کارت» حداقل یک کارت لازم است."]
    else:
        for c in cards:
            star = "⭐ " if c.get("is_default") else ""
            state = "🟢" if c.get("is_active") else "🔴"
            lines += [
                f"{star}{state} {c.get('bank_name') or 'بانک'}",
                f"├── 🔢 {mask_card(c.get('card_number'))}",
                f"└── 👤 {c.get('card_holder_name') or '-'}",
                "",
            ]

    btns = [[{"text": "➕ ثبت کارت جدید", "callback_data": "card_add"}]]
    for c in cards:
        lbl = f"{'⭐' if c.get('is_default') else '💳'} {mask_card(c.get('card_number'))}"
        btns.append([
            {"text": lbl[:28], "callback_data": f"card_view_{c['id']}"},
            {"text": "🔴" if c.get("is_active") else "🟢",
             "callback_data": f"card_tog_{c['id']}"},
            {"text": "🗑️", "callback_data": f"card_del_{c['id']}"},
        ])
    btns.append([{"text": "🔙 تنظیمات پرداخت", "callback_data": "set_payment"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_add_card(cid, uid):
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_CARD_ADD, {"step": 0}, merge=False)
    send(cid, (
        "➕ ثبت کارت جدید\n"
        "━━━━━━━━━━━━━━\n\n"
        "🔢 شماره کارت ۱۶ رقمی را بفرستید:\n\n"
        "مثال: 6037991234567890"
    ), kb_cancel())


def handle_add_card(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    if text == BTN_BACK:
        clear_state(uid)
        return show_cards(cid, uid)

    d = get_state_data(uid)
    step = int(d.get("step") or 0)

    if step == 0:
        num = normalize_card(text)
        if not num:
            return send(cid, "❌ شماره کارت باید دقیقاً ۱۶ رقم باشد")
        if not luhn_valid(num):
            return send(cid, (
                "❌ شماره کارت نامعتبر است\n\n"
                "💡 رقم کنترلی درست نیست — دوباره بررسی کنید."
            ))
        dup = db_execute("SELECT id FROM bank_cards WHERE card_number=?",
                         (num,), fetch="one")
        if dup:
            clear_state(uid)
            send(cid, "⚠️ این کارت قبلاً ثبت شده است", kb_remove())
            return show_cards(cid, uid)
        bank = detect_bank(num)
        update_state_data(uid, {"step": 1, "card_number": num, "bank_name": bank})
        msg = f"✅ شماره کارت ثبت شد\n{format_card(num)}\n"
        if bank:
            msg += f"🏦 بانک تشخیص داده شد: {bank}\n"
        msg += "\n👤 نام صاحب کارت را بفرستید:"
        return send(cid, msg, kb_cancel())

    if step == 1:
        if len(text) < 3:
            return send(cid, "❌ نام باید حداقل ۳ کاراکتر باشد")
        update_state_data(uid, {"step": 2, "card_holder_name": text[:80]})
        cur = get_state_data(uid).get("bank_name")
        return send(cid, (
            f"🏦 نام بانک را بفرستید:\n\n"
            + (f"💡 تشخیص خودکار: {cur}\n(برای تأیید همین را بنویسید)"
               if cur else "مثال: ملی، ملت، پاسارگاد")
        ), kb_cancel())

    if step == 2:
        update_state_data(uid, {"step": 3, "bank_name": text[:40]})
        return send(cid, (
            "🔢 شماره شبا (اختیاری):\n\n"
            "مثال: IR123456789012345678901234\n\n"
            "برای رد کردن بنویسید: -"
        ), kb_cancel())

    if step == 3:
        sheba = "" if text in ("-", "—") else normalize_digits(text).upper()
        if sheba and not re.match(r"^IR\d{24}$", sheba):
            return send(cid, "❌ شبا نامعتبر\n\nفرمت: IR + ۲۴ رقم\nیا «-» برای رد کردن")
        d = get_state_data(uid)
        clear_state(uid)

        is_first = db_scalar("SELECT COUNT(*) FROM bank_cards") == 0
        rid = db_execute("""INSERT INTO bank_cards
            (owner_id, card_number, card_holder_name, bank_name,
             sheba_number, is_active, is_default)
            VALUES (?,?,?,?,?,1,?)""",
            (uid, d.get("card_number"), d.get("card_holder_name"),
             d.get("bank_name"), sheba, 1 if is_first else 0))

        if not rid:
            send(cid, "❌ خطا در ذخیره کارت", kb_remove())
        else:
            send(cid, (
                f"✅ کارت ثبت شد\n"
                f"━━━━━━━━━━━━━━\n\n"
                f"🏦 {d.get('bank_name')}\n"
                f"🔢 {format_card(d.get('card_number'))}\n"
                f"👤 {d.get('card_holder_name')}\n"
                + (f"🏛️ {sheba}\n" if sheba else "")
                + ("\n⭐ به‌عنوان کارت پیش‌فرض تنظیم شد" if is_first else "")
            ), kb_remove())
        return show_cards(cid, uid)


def view_card(cid, uid, card_id):
    if not _guard(cid, uid):
        return
    c = get_card(card_id)
    if not c:
        return send(cid, "❌ کارت یافت نشد")
    used = db_scalar(
        "SELECT COUNT(*) FROM payment_receipts WHERE card_id=?", (card_id,))
    total = db_scalar(
        "SELECT COALESCE(SUM(amount),0) FROM payment_receipts "
        "WHERE card_id=? AND status='approved'", (card_id,))
    send_or_edit(cid, (
        f"💳 جزئیات کارت\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🏦 بانک: {c.get('bank_name') or '-'}\n"
        f"🔢 شماره: {format_card(c.get('card_number'))}\n"
        f"👤 صاحب: {c.get('card_holder_name') or '-'}\n"
        f"🏛️ شبا: {c.get('sheba_number') or '-'}\n"
        f"📌 وضعیت: {'🟢 فعال' if c.get('is_active') else '🔴 غیرفعال'}\n"
        f"⭐ پیش‌فرض: {'بله' if c.get('is_default') else 'خیر'}\n\n"
        f"📊 آمار:\n"
        f"├── 🧾 رسیدها: {used}\n"
        f"└── 💰 دریافتی: {fmt(total)} {CURRENCY_LABEL}"
    ), {"inline_keyboard": [
        [{"text": "⭐ تنظیم به‌عنوان پیش‌فرض",
          "callback_data": f"card_def_{card_id}"}],
        [{"text": "📋 کپی شماره کارت",
          "copy_text": {"text": c.get("card_number") or ""}}],
        [{"text": "🗑️ حذف کارت", "callback_data": f"card_del_{card_id}"}],
        [{"text": "🔙 کارت‌ها", "callback_data": "pay_cards"}],
    ]})


def toggle_card(cid, uid, card_id):
    if not _guard(cid, uid):
        return
    c = get_card(card_id)
    if not c:
        return send(cid, "❌ یافت نشد")
    new = 0 if c.get("is_active") else 1
    db_execute("UPDATE bank_cards SET is_active=? WHERE id=?", (new, card_id))
    show_cards(cid, uid)


def set_default_card(cid, uid, card_id):
    if not _guard(cid, uid):
        return
    db_execute("UPDATE bank_cards SET is_default=0")
    db_execute("UPDATE bank_cards SET is_default=1, is_active=1 WHERE id=?",
               (card_id,))
    send(cid, "⭐ کارت پیش‌فرض تنظیم شد")
    show_cards(cid, uid)


def delete_card(cid, uid, card_id, confirmed=False):
    if not _guard(cid, uid):
        return
    c = get_card(card_id)
    if not c:
        return send(cid, "❌ یافت نشد")
    if not confirmed:
        return send_or_edit(cid, (
            f"⚠️ حذف کارت\n\n"
            f"🏦 {c.get('bank_name')}\n"
            f"🔢 {mask_card(c.get('card_number'))}\n\n"
            f"❗ رویدادهایی که از این کارت استفاده می‌کنند مشکل پیدا می‌کنند."
        ), {"inline_keyboard": [
            [{"text": "🗑️ بله، حذف کن", "callback_data": f"card_dely_{card_id}"}],
            [{"text": "🔙 انصراف", "callback_data": "pay_cards"}]]})
    db_execute("DELETE FROM bank_cards WHERE id=?", (card_id,))
    send(cid, "🗑️ کارت حذف شد")
    show_cards(cid, uid)


# ==================== درگاه‌های سفارشی ====================
GATEWAY_TYPES = {
    "zarinpal": {"name": "زرین‌پال", "url": "https://www.zarinpal.com"},
    "payping": {"name": "پی‌پینگ", "url": "https://www.payping.ir"},
    "idpay": {"name": "آیدی‌پی", "url": "https://idpay.ir"},
    "nextpay": {"name": "نکست‌پی", "url": "https://nextpay.org"},
    "other": {"name": "سایر", "url": ""},
}


def get_gateways(active_only=True):
    q = "SELECT * FROM payment_gateways"
    if active_only:
        q += " WHERE is_active=1"
    return db_execute(q + " ORDER BY id DESC", fetch="all") or []


def show_gateways(cid, uid):
    if not _guard(cid, uid):
        return
    gws = db_execute("SELECT * FROM payment_gateways ORDER BY id DESC",
                     fetch="all") or []
    lines = ["🔗 درگاه‌های پرداخت سفارشی", "━━━━━━━━━━━━━━", ""]
    if not gws:
        lines += [
            "📭 درگاهی تعریف نشده",
            "",
            "💡 اگر درگاه پرداخت اینترنتی دارید (زرین‌پال، پی‌پینگ و...)",
            "می‌توانید اینجا ثبت کنید.",
            "",
            "⚠️ توجه: اتصال کامل به درگاه نیاز به وب‌سرور دارد.",
            "فعلاً اطلاعات ذخیره می‌شود و لینک پرداخت دستی ساخته می‌شود.",
        ]
    else:
        for g in gws:
            st = "🟢" if g.get("is_active") else "🔴"
            t = GATEWAY_TYPES.get(g.get("gateway_type") or "other", {})
            lines += [
                f"{st} {g.get('gateway_name')}",
                f"├── نوع: {t.get('name', '-')}",
                f"└── Merchant: {(g.get('merchant_id') or '')[:12]}***",
                "",
            ]

    btns = [[{"text": "➕ تعریف درگاه جدید", "callback_data": "gw_add"}]]
    for g in gws:
        btns.append([
            {"text": f"🔗 {g.get('gateway_name')}"[:26],
             "callback_data": f"gw_view_{g['id']}"},
            {"text": "🔴" if g.get("is_active") else "🟢",
             "callback_data": f"gw_tog_{g['id']}"},
            {"text": "🗑️", "callback_data": f"gw_del_{g['id']}"},
        ])
    btns.append([{"text": "🔙 تنظیمات پرداخت", "callback_data": "set_payment"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_add_gateway(cid, uid):
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_GW_ADD, {"step": 0}, merge=False)
    btns = [[{"text": v["name"], "callback_data": f"gwt_{k}"}]
            for k, v in GATEWAY_TYPES.items()]
    btns.append([{"text": "❌ انصراف", "callback_data": "pay_gateways"}])
    send_or_edit(cid, (
        "➕ تعریف درگاه جدید\n"
        "━━━━━━━━━━━━━━\n\n"
        "نوع درگاه را انتخاب کنید:"
    ), {"inline_keyboard": btns})


def pick_gateway_type(cid, uid, gtype):
    if not _guard(cid, uid):
        return
    t = GATEWAY_TYPES.get(gtype, GATEWAY_TYPES["other"])
    update_state_data(uid, {"step": 1, "gateway_type": gtype,
                            "gateway_name": t["name"]})
    set_state(uid, STATE_GW_ADD, {"step": 1}, merge=True)
    send(cid, (
        f"🔗 درگاه: {t['name']}\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🏷️ نام نمایشی درگاه را بفرستید:\n"
        f"(مثلاً: زرین‌پال خط زندگی)\n\n"
        f"برای استفاده از «{t['name']}» بنویسید: -"
    ), kb_cancel())


def handle_add_gateway(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()

    if text == BTN_BACK:
        clear_state(uid)
        return show_gateways(cid, uid)

    d = get_state_data(uid)
    step = int(d.get("step") or 0)

    if step == 1:
        name = d.get("gateway_name") if text in ("-", "—") else text[:50]
        update_state_data(uid, {"step": 2, "gateway_name": name})
        return send(cid, (
            "🆔 Merchant ID را بفرستید:\n\n"
            "(کد پذیرنده که از درگاه گرفته‌اید)"
        ), kb_cancel())

    if step == 2:
        if len(text) < 3:
            return send(cid, "❌ خیلی کوتاه است")
        update_state_data(uid, {"step": 3, "merchant_id": text[:120]})
        return send(cid, (
            "🔑 API Key را بفرستید:\n\n"
            "اگر ندارد بنویسید: -"
        ), kb_cancel())

    if step == 3:
        api_key = "" if text in ("-", "—") else text[:200]
        update_state_data(uid, {"step": 4, "api_key": api_key})
        return send(cid, (
            "🔗 Callback URL را بفرستید:\n\n"
            "مثال: https://yourdomain.com/pay/callback\n\n"
            "اگر ندارید بنویسید: -"
        ), kb_cancel())

    if step == 4:
        cb_url = "" if text in ("-", "—") else text[:300]
        if cb_url and not cb_url.startswith("http"):
            return send(cid, "❌ آدرس باید با http شروع شود")
        d = get_state_data(uid)
        clear_state(uid)
        rid = db_execute("""INSERT INTO payment_gateways
            (owner_id, gateway_name, gateway_type, merchant_id,
             api_key, callback_url, is_active)
            VALUES (?,?,?,?,?,?,1)""",
            (uid, d.get("gateway_name"), d.get("gateway_type"),
             d.get("merchant_id"), d.get("api_key"), cb_url))
        if rid:
            send(cid, (
                f"✅ درگاه ثبت شد\n\n"
                f"🔗 {d.get('gateway_name')}\n"
                f"🆔 {(d.get('merchant_id') or '')[:14]}***"
            ), kb_remove())
        else:
            send(cid, "❌ خطا در ذخیره", kb_remove())
        return show_gateways(cid, uid)


def view_gateway(cid, uid, gid):
    if not _guard(cid, uid):
        return
    g = db_execute("SELECT * FROM payment_gateways WHERE id=?", (gid,), fetch="one")
    if not g:
        return send(cid, "❌ یافت نشد")
    t = GATEWAY_TYPES.get(g.get("gateway_type") or "other", {})
    send_or_edit(cid, (
        f"🔗 {g.get('gateway_name')}\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🏷️ نوع: {t.get('name', '-')}\n"
        f"🆔 Merchant: {(g.get('merchant_id') or '')[:16]}***\n"
        f"🔑 API Key: {'✅ ثبت شده' if g.get('api_key') else '❌ ندارد'}\n"
        f"🔗 Callback: {g.get('callback_url') or '-'}\n"
        f"📌 وضعیت: {'🟢 فعال' if g.get('is_active') else '🔴 غیرفعال'}"
    ), {"inline_keyboard": [
        [{"text": "🗑️ حذف", "callback_data": f"gw_del_{gid}"}],
        [{"text": "🔙 درگاه‌ها", "callback_data": "pay_gateways"}],
    ]})


def toggle_gateway(cid, uid, gid):
    if not _guard(cid, uid):
        return
    g = db_execute("SELECT is_active FROM payment_gateways WHERE id=?",
                   (gid,), fetch="one")
    if g:
        db_execute("UPDATE payment_gateways SET is_active=? WHERE id=?",
                   (0 if g["is_active"] else 1, gid))
    show_gateways(cid, uid)


def delete_gateway(cid, uid, gid):
    if not _guard(cid, uid):
        return
    db_execute("DELETE FROM payment_gateways WHERE id=?", (gid,))
    send(cid, "🗑️ درگاه حذف شد")
    show_gateways(cid, uid)


# ==================== متن‌های پرداخت ====================
def show_payment_texts(cid, uid):
    if not _guard(cid, uid):
        return
    lines = ["📝 متن‌های پرداخت", "━━━━━━━━━━━━━━", "",
             "همه پیام‌های پرداخت از اینجا قابل تغییر است:", ""]
    btns = []
    for key, title, default in PAYMENT_TEXTS:
        cur = get_setting(key, default)
        preview = cur.replace("\n", " ")[:36]
        lines.append(f"• {title}")
        lines.append(f"  {preview}…")
        btns.append([{"text": f"✏️ {title}"[:40], "callback_data": f"ptx_{key}"}])
    lines += ["", "💡 متغیرها: {amount} {currency} {card} {bank} {holder}",
              "{ref} {reason} {gateway}"]
    btns.append([{"text": "♻️ بازگردانی همه به پیش‌فرض",
                  "callback_data": "ptx_reset"}])
    btns.append([{"text": "🔙 تنظیمات پرداخت", "callback_data": "set_payment"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_edit_payment_text(cid, uid, key):
    if not _guard(cid, uid):
        return
    entry = next((e for e in PAYMENT_TEXTS if e[0] == key), None)
    if not entry:
        return send(cid, "❌ متن یافت نشد")
    _, title, default = entry
    cur = get_setting(key, default)
    set_state(uid, STATE_TEXT_EDIT, {"key": key}, merge=False)
    send(cid, (
        f"✏️ {title}\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"📄 متن فعلی:\n{cur}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"📝 متن جدید را بفرستید:\n\n"
        f"💡 متغیرهای قابل استفاده:\n"
        f"{{amount}} مبلغ | {{currency}} واحد پول\n"
        f"{{card}} شماره کارت | {{bank}} بانک\n"
        f"{{holder}} نام صاحب کارت\n"
        f"{{ref}} کد پیگیری | {{reason}} دلیل\n"
        f"{{gateway}} نام درگاه"
    ), kb_cancel())


def handle_edit_payment_text(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    if text == BTN_BACK:
        clear_state(uid)
        return show_payment_texts(cid, uid)
    d = get_state_data(uid)
    key = d.get("key")
    clear_state(uid)
    if not key or not text:
        return send(cid, "⚠️ خطا — دوباره تلاش کنید", kb_remove())
    entry = next((e for e in PAYMENT_TEXTS if e[0] == key), None)
    title = entry[1] if entry else key
    set_setting(key, text[:3000], title, "payment", uid)
    send(cid, f"✅ ذخیره شد\n\n📝 {title}", kb_remove())
    show_payment_texts(cid, uid)


def reset_payment_texts(cid, uid):
    if not _guard(cid, uid):
        return
    for key, title, default in PAYMENT_TEXTS:
        set_setting(key, default, title, "payment", uid)
    send(cid, "♻️ همه متن‌های پرداخت به حالت پیش‌فرض برگشتند")
    show_payment_texts(cid, uid)


# ==================== جریان پرداخت ====================
def start_card_payment(cid, uid, ev, rid, amount, card_id=None):
    """💳 کارت به کارت"""
    card = get_card(card_id) if card_id else None
    if not card:
        cards = get_cards()
        card = cards[0] if cards else None
    if not card:
        send(cid, "⚠️ کارتی برای واریز تنظیم نشده. با پشتیبانی تماس بگیرید.")
        _notify_admins(f"⚠️ رویداد «{ev['title']}» روش کارت به کارت دارد "
                       f"ولی هیچ کارتی ثبت نشده!")
        return None

    # 💳 فاز ۱۷ — کارمزد کارت به کارت (اگر فعال باشد)
    fee, total = calc_fee(amount, "card")

    payload = _payload("card", ev, uid, rid)
    txid = db_execute("""INSERT INTO transactions
        (bale_user_id, event_id, registration_id, payload, amount,
         status, method, fee_amount, base_amount, form_response_id)
        VALUES (?,?,?,?,?,'pending','card',?,?,?)""",
        (uid, ev["id"], rid, payload, total, fee, amount, _frid(ev)))
    _tag_plan_part(txid, ev)

    mark_payload(ev, rid, payload)

    txt = render("pay_txt_card_intro",
                 amount=fmt(total), card=format_card(card.get("card_number")),
                 bank=card.get("bank_name") or "-",
                 holder=card.get("card_holder_name") or "-")
    brk = fee_breakdown(amount, "card")
    if brk:
        txt += "\n\n" + brk

    set_state(uid, STATE_RECEIPT, {
        "tx_id": txid, "event_id": ev["id"], "reg_id": rid,
        "amount": total, "card_id": card["id"],
        "frid": _frid(ev),          # 📝 فاز ۱۸-الف: رسید فرم‌ساز
    }, merge=False)

    send(cid, txt, {"keyboard": [
        [{"text": "❌ انصراف از پرداخت"}],
        [{"text": "🏠 منوی اصلی"}],
    ], "resize_keyboard": True})
    return txid


def handle_receipt(message):
    """دریافت عکس رسید از کاربر"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    d = get_state_data(uid)

    if text in ("❌ انصراف از پرداخت", BTN_BACK):
        clear_state(uid)
        return send(cid, "❌ پرداخت لغو شد", kb_remove())

    photos = message.get("photo") or []
    if not photos:
        return send(cid, "📸 لطفاً تصویر رسید را ارسال کنید")

    # 🔗 فاز ۱۷ — رسید برای لینک پرداخت غیرمتمرکز
    if d.get("paylink_pid") and not d.get("tx_id"):
        return _handle_paylink_receipt(message, d)
    if not d.get("tx_id"):
        clear_state(uid)
        return send(cid, "⏰ منقضی شد. دوباره ثبت‌نام کنید", kb_remove())

    try:
        best = max(photos, key=lambda p: (p.get("file_size") or 0,
                                          p.get("width") or 0))
    except (ValueError, TypeError):
        best = photos[-1]
    fid = best.get("file_id")

    import uuid
    import shared_api
    from events import get_event

    event = get_event(d.get("event_id")) or {}
    workflow_key = d.get("_shared_idempotency_key")
    ref = d.get("_shared_ref_code")
    submitted_at = d.get("_shared_submitted_at")
    if not isinstance(workflow_key, str) or not workflow_key:
        workflow_key = f"receipt:{uid}:{uuid.uuid4().hex}"
    if not ref:
        ref = f"R{int(time.time()) % 1000000}"
    if not submitted_at:
        submitted_at = datetime.now().isoformat(timespec="seconds")
    update_state_data(uid, {
        "_shared_idempotency_key": workflow_key,
        "_shared_ref_code": ref,
        "_shared_submitted_at": submitted_at,
    })

    if not fid:
        return send(cid, "تصویر رسید دریافت نشد؛ دوباره عکس را بفرستید.")
    file_info = get_file_info(fid)
    if not file_info.get("ok"):
        return send(cid, "دریافت تصویر از بله انجام نشد؛ دوباره تلاش کنید.")
    file_path = (file_info.get("result") or {}).get("file_path")
    content = download_file(file_path) if file_path else None
    if not content:
        return send(cid, "ذخیرهٔ مشترک تصویر رسید انجام نشد؛ دوباره تلاش کنید.")
    try:
        shared_file_id = shared_api.upload_private_file(
            uid,
            content,
            Path(file_path).name or "receipt.jpg",
            "receipt-file:" + workflow_key,
        )
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ بارگذاری رسید در مخزن مشترک انجام نشد: {exc.code}")
        return send(cid, "تصویر رسید در مخزن مشترک ثبت نشد؛ اتصال سرویس را بررسی کنید و دوباره بفرستید.")

    receipt_data = {
        "transaction_id": d.get("tx_id"),
        "event_id": d.get("event_id"),
        "event_title": event.get("title") or "",
        "registration_id": d.get("reg_id"),
        "form_response_id": d.get("frid"),
        "amount": int(d.get("amount") or 0),
        "currency": CURRENCY_LABEL,
        "ref_code": ref,
        "photo_file_id": fid or "",
        "file_refs": [shared_file_id],
        "submitted_at": submitted_at,
    }
    try:
        result = shared_api.submit_workflow(
            uid, "receipt_review", receipt_data, workflow_key
        )
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ ثبت فیش در API مشترک انجام نشد: {exc.code}")
        return send(cid, "فیش ثبت نشد؛ اتصال سرویس مشترک را بررسی کنید و دوباره بفرستید.")

    clear_state(uid)
    task = result["task"]
    send(cid, render("pay_txt_card_received", ref=ref,
                     amount=fmt(d.get("amount"))) +
         f"\n\nکد پیگیری: {task['id'][:8]}", kb_remove())
    log_action(uid, "receipt_sent", {"task_id": task["id"], "ref": ref})
    return task["id"]

def _notify_admins(text, kb=None, photo=None):
    rows = db_execute(
        "SELECT DISTINCT bale_user_id FROM users "
        "WHERE is_admin=1 AND bale_user_id IS NOT NULL", fetch="all") or []
    ids = {r["bale_user_id"] for r in rows if r.get("bale_user_id")}
    if SUPER_ADMIN_ID:
        ids.add(SUPER_ADMIN_ID)
    for aid in ids:
        if photo and Path(photo).exists():
            send_photo(aid, photo)
        send(aid, text, kb)


def show_receipts(cid, uid, status="pending"):
    """نمایش صف فیش‌های مشترک؛ تاریخچهٔ قدیمی جداگانه نگه داشته می‌شود."""
    if status != "pending":
        return send(cid, "نمایش تاریخچهٔ فیش‌های قدیمی در این کارتابل فعال نیست.", kb_remove())
    from shared_workflows import show_inbox
    return show_inbox(cid, uid, kind="receipt_review")

def apply_shared_review_projection(task):
    """Project a central receipt decision into bot-side payment operations."""
    if not isinstance(task, dict) or task.get("kind") != "receipt_review":
        raise ValueError("invalid_shared_receipt_task")
    decision = task.get("status")
    if decision not in {"approved", "rejected"}:
        raise ValueError("shared_receipt_task_not_decided")
    data = task.get("payload") or {}
    try:
        target = int(task.get("bale_user_id"))
    except (TypeError, ValueError):
        raise ValueError("invalid_shared_receipt_user") from None
    if target <= 0:
        raise ValueError("invalid_shared_receipt_user")
    if data.get("registration_source") == "public_form":
        # The shared API owns public-web response cancellation and notifications;
        # never project this UUID into the bot's legacy SQLite form tables.
        log_action(target, "public_form_receipt_approved" if decision == "approved" else "public_form_receipt_rejected", {
            "shared_task": task.get("id"),
            "reason": task.get("review_reason") or "",
        })
        return

    shared_task_id = task.get("id")
    existing = db_execute(
        "SELECT id FROM payment_receipts WHERE shared_task_id=?", (shared_task_id,), fetch="one"
    )
    from legacy_review_projection import project_legacy_review

    project_legacy_review(
        "receipt_review", task, decision, db_execute=db_execute
    )
    if not existing:
        db_execute("""INSERT INTO payment_receipts
            (transaction_id, event_id, registration_id, form_response_id,
             bale_user_id, amount, photo_file_id, ref_code, status,
             reviewed_by, reviewed_at, reject_reason, shared_task_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,?,?)""",
            (
                data.get("transaction_id"), data.get("event_id"), data.get("registration_id"),
                data.get("form_response_id"), target, data.get("amount"),
                data.get("photo_file_id") or (data.get("file_refs") or [None])[0],
                data.get("ref_code"), decision,
                task.get("reviewed_by_bale_user_id"), task.get("review_reason"), shared_task_id,
            ),
        )

    transaction_id = data.get("transaction_id")
    response_id = data.get("form_response_id")
    registration_id = data.get("registration_id")
    paylink_id = data.get("paylink_payment_id")
    if decision == "approved":
        if transaction_id:
            db_execute("""UPDATE transactions SET status='paid',
                transaction_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (data.get("ref_code"), transaction_id))
        if response_id:
            old = db_execute(
                "SELECT status FROM form_responses WHERE id=?", (response_id,), fetch="one"
            ) or {}
            db_execute("""UPDATE form_responses
                SET amount_paid=?, payment_status='paid', transaction_id=?
                WHERE id=?""", (data.get("amount"), data.get("ref_code"), response_id))
            if old.get("status") not in {"completed", "pending_review"}:
                try:
                    import form_fill as _ff
                    form_row = db_execute(
                        "SELECT * FROM form_responses WHERE id=?", (response_id,), fetch="one"
                    ) or {}
                    _ff.finalize(target, target, response_id, form_row.get("score"), form_row.get("max_score"))
                except Exception as exc:
                    log(f"⚠️ تکمیل پاسخ فرم پس از تأیید رسید: {type(exc).__name__}")
        elif registration_id:
            db_execute("""UPDATE event_registrations
                SET amount_paid=?, transaction_id=?, paid_at=COALESCE(paid_at,CURRENT_TIMESTAMP)
                WHERE id=?""", (data.get("amount"), data.get("ref_code"), registration_id))
            try:
                from events import get_event, finish_registration
                event = get_event(data.get("event_id"))
                if event:
                    finish_registration(target, target, event, registration_id)
            except Exception as exc:
                log(f"⚠️ تکمیل ثبت‌نام پس از تأیید رسید: {type(exc).__name__}")
        if paylink_id:
            payment = db_execute("SELECT * FROM paylink_payments WHERE id=?", (paylink_id,), fetch="one") or {}
            if payment and payment.get("status") != "paid":
                import paylink as _pl
                _pl.mark_paid(payment.get("payload") or "", f"MAN{paylink_id}")
    else:
        if transaction_id:
            db_execute("UPDATE transactions SET status='failed' WHERE id=?", (transaction_id,))
        if paylink_id:
            db_execute("UPDATE paylink_payments SET status='failed' WHERE id=? AND status<>'paid'", (paylink_id,))
    log_action(target, "receipt_approved" if decision == "approved" else "receipt_rejected", {
        "shared_task": shared_task_id,
        "reason": task.get("review_reason") or "",
    })


def _legacy_receipt_review_redirect(cid, uid, *, clear_legacy_state=False):
    """Fail closed for legacy SQLite receipt decisions."""
    if clear_legacy_state:
        clear_state(uid)
    send(
        cid,
        "تأیید یا رد محلی فیش غیرفعال است؛ فقط کارتابل مشترک اجازهٔ تصمیم دارد. "
        "رسیدهای قدیمیِ خارج از کارتابل به انتقال کنترل‌شده نیاز دارند.",
        kb_remove(),
    )
    from shared_workflows import show_inbox
    return show_inbox(cid, uid, kind="receipt_review")


def approve_receipt(cid, uid, rcp_id):
    return _legacy_receipt_review_redirect(cid, uid)


def start_reject_receipt(cid, uid, rcp_id):
    return _legacy_receipt_review_redirect(cid, uid)


def handle_reject_receipt(message):
    """Close a stale local reject state without recording a local decision."""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    return _legacy_receipt_review_redirect(cid, uid, clear_legacy_state=True)


def _handle_paylink_receipt(message, d):
    """📸 رسید کارت‌به‌کارت برای لینک پرداخت غیرمتمرکز"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    photos = message.get("photo") or []
    if not photos:
        return send(cid, "📸 لطفاً تصویر رسید را ارسال کنید")

    try:
        best = max(photos, key=lambda p: (p.get("file_size") or 0,
                                          p.get("width") or 0))
    except (ValueError, TypeError):
        best = photos[-1]

    import uuid
    import shared_api

    pid = d.get("paylink_pid")
    amount = int(d.get("amount") or 0)
    best_fid = best.get("file_id")
    payment = db_execute("SELECT * FROM paylink_payments WHERE id=?", (pid,), fetch="one") or {}
    link = db_execute("SELECT * FROM payment_links WHERE id=?", (payment.get("link_id"),), fetch="one") or {}
    workflow_key = d.get("_shared_idempotency_key")
    ref = d.get("_shared_ref_code")
    submitted_at = d.get("_shared_submitted_at")
    if not isinstance(workflow_key, str) or not workflow_key:
        workflow_key = f"receipt:{uid}:{uuid.uuid4().hex}"
    if not ref:
        ref = f"R{int(time.time()) % 1000000}"
    if not submitted_at:
        submitted_at = datetime.now().isoformat(timespec="seconds")
    update_state_data(uid, {
        "_shared_idempotency_key": workflow_key,
        "_shared_ref_code": ref,
        "_shared_submitted_at": submitted_at,
    })
    if not best_fid:
        return send(cid, "تصویر رسید دریافت نشد؛ دوباره عکس را بفرستید.")
    file_info = get_file_info(best_fid)
    if not file_info.get("ok"):
        return send(cid, "دریافت تصویر از بله انجام نشد؛ دوباره تلاش کنید.")
    file_path = (file_info.get("result") or {}).get("file_path")
    content = download_file(file_path) if file_path else None
    if not content:
        return send(cid, "ذخیرهٔ مشترک تصویر رسید انجام نشد؛ دوباره تلاش کنید.")
    try:
        shared_file_id = shared_api.upload_private_file(
            uid, content, Path(file_path).name or "receipt.jpg", "receipt-file:" + workflow_key
        )
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ بارگذاری رسید لینک در مخزن مشترک انجام نشد: {exc.code}")
        return send(cid, "تصویر رسید در مخزن مشترک ثبت نشد؛ اتصال سرویس را بررسی کنید و دوباره بفرستید.")
    receipt_data = {
        "amount": amount,
        "currency": CURRENCY_LABEL,
        "event_title": link.get("title") or "پرداخت لینک",
        "ref_code": ref,
        "photo_file_id": best_fid or "",
        "file_refs": [shared_file_id],
        "submitted_at": submitted_at,
        "paylink_payment_id": pid,
    }
    try:
        result = shared_api.submit_workflow(
            uid, "receipt_review", receipt_data, workflow_key
        )
    except shared_api.SharedAPIError as exc:
        log(f"⚠️ ثبت فیش لینک در API مشترک انجام نشد: {exc.code}")
        return send(cid, "فیش ثبت نشد؛ اتصال سرویس مشترک را بررسی کنید و دوباره بفرستید.")
    clear_state(uid)
    task = result["task"]
    send(cid, render("pay_txt_card_received", ref=ref,
                     amount=fmt(amount)) +
         f"\n\nکد پیگیری: {task['id'][:8]}", kb_remove())
    log_action(uid, "receipt_sent", {"task_id": task["id"], "ref": ref})
    return task["id"]


def approve_paylink_receipt(cid, uid, pid, approve=True):
    """✅/❌ بررسی رسید لینک پرداخت"""
    import permissions as perm
    if not perm.require(cid, uid, "fin_approve", send):
        return
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return send(cid, "❌ شناسه نامعتبر")
    p = db_execute("SELECT * FROM paylink_payments WHERE id=?", (pid,),
                   fetch="one")
    if not p:
        return send(cid, "❌ پرداخت یافت نشد")
    if p.get("status") == "paid":
        return send(cid, "ℹ️ قبلاً تأیید شده است")

    if approve:
        import paylink as _pl
        _pl.mark_paid(p.get("payload") or "", f"MAN{pid}")
        if p.get("receipt_id"):
            db_execute("""UPDATE payment_receipts SET status='approved',
                reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP WHERE id=?""",
                (uid, p["receipt_id"]))
        send(cid, "✅ پرداخت تأیید شد")
    else:
        db_execute("UPDATE paylink_payments SET status='failed' WHERE id=?",
                   (pid,))
        if p.get("receipt_id"):
            db_execute("""UPDATE payment_receipts SET status='rejected',
                reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP WHERE id=?""",
                (uid, p["receipt_id"]))
        send(cid, "❌ پرداخت رد شد")
        if p.get("bale_user_id"):
            send(p["bale_user_id"],
                 "❌ رسید پرداخت شما تأیید نشد\n\n"
                 "💡 با پشتیبانی تماس بگیرید.")
    log_action(uid, "paylink_review", {"pid": pid, "ok": approve})


def start_wallet_payment(cid, uid, ev, rid, amount):
    """🏦 کیف پول بله"""
    if not PAYMENT_ENABLED:
        send(cid, "⚠️ درگاه کیف پول تنظیم نشده")
        return None

    # 💳 فاز ۱۷ — کارمزد کیف پول (اگر ادمین فعال کرده باشد)
    fee, total = calc_fee(amount, "bale_wallet")

    ok, msg = check_amount(total)
    if not ok:
        send(cid, f"⛔ {msg}")
        return None

    # 🛡️ فاز ۱۸-ب — هشدار فیلترشکن قبل از هدایت به درگاه
    send_vpn_warning(cid, "bale_wallet", ev)

    payload = _payload("ev", ev, uid, rid)
    txid = db_execute("""INSERT INTO transactions
        (bale_user_id, event_id, registration_id, payload, amount,
         status, method, fee_amount, base_amount, form_response_id)
        VALUES (?,?,?,?,?,'pending','wallet',?,?,?)""",
        (uid, ev["id"], rid, payload, total, fee, amount, _frid(ev)))
    _tag_plan_part(txid, ev)
    mark_payload(ev, rid, payload)

    # 🧱 فاز ۲۴ — اگر مبلغ کم است، عنوانش «هزینه زیرساخت» شود
    _lbl = f"ثبت‌نام {ev['title']}"
    try:
        import infra_fee as _inf
        _il = _inf.invoice_line(amount, bool(_frid(ev)))
        if _il:
            _lbl = _il
    except Exception as _e:
        log(f"⚠️ برچسب زیرساخت: {_e}")
    prices = [{"label": _lbl[:32], "amount": int(amount)}]
    if fee > 0:
        prices.append({"label": fee_label("bale_wallet")[:32],
                       "amount": int(fee)})

    res = send_invoice(
        cid, title=ev["title"][:32],
        description=(ev.get("description") or ev["title"])[:250],
        payload=payload, provider_token=PAYMENT_PROVIDER_TOKEN,
        prices=prices)

    if res.get("ok"):
        txt = render("pay_txt_wallet_intro", amount=fmt(total))
        brk = fee_breakdown(amount, "bale_wallet")
        if brk:
            txt += "\n\n" + brk
        txt += vpn_warn_inline("bale_wallet")
        send(cid, txt + ("\n\n🧪 حالت آزمایشی" if PAYMENT_TEST_MODE else ""))
        return txid
    log(f"❌ sendInvoice: {res.get('description')}")
    send(cid, render("pay_txt_failed"))
    return None


def start_gateway_payment(cid, uid, ev, rid, amount, gw_id=None):
    """🔗 درگاه سفارشی"""
    gws = get_gateways()
    gw = None
    if gw_id:
        gw = db_execute("SELECT * FROM payment_gateways WHERE id=? AND is_active=1",
                        (gw_id,), fetch="one")
    if not gw:
        gw = gws[0] if gws else None
    if not gw:
        send(cid, "⚠️ درگاه پرداختی تنظیم نشده. با پشتیبانی تماس بگیرید.")
        return None

    # 💳 کارمزد این روش روی مبلغ اضافه می‌شود
    fee, total = calc_fee(amount, "custom_gateway")

    # 🛡️ فاز ۱۸-ب — هشدار فیلترشکن قبل از هدایت به درگاه
    send_vpn_warning(cid, "custom_gateway", ev)

    payload = _payload("gw", ev, uid, rid)
    txid = db_execute("""INSERT INTO transactions
        (bale_user_id, event_id, registration_id, payload, amount,
         status, method, fee_amount, base_amount, form_response_id)
        VALUES (?,?,?,?,?,'pending','gateway',?,?,?)""",
        (uid, ev["id"], rid, payload, total, fee, amount, _frid(ev)))
    _tag_plan_part(txid, ev)
    mark_payload(ev, rid, payload)

    txt = render("pay_txt_gateway_intro", amount=fmt(total),
                 gateway=gw.get("gateway_name"))
    # 🧾 ریز مبلغ وقتی کارمزد دارد — کاربر بداند بابت چه پول می‌دهد
    brk = fee_breakdown(amount, "custom_gateway")
    if brk:
        txt += "\n\n" + brk
    txt += vpn_warn_inline("custom_gateway")

    url = gw.get("callback_url") or ""
    btns = []
    if url:
        sep = "&" if "?" in url else "?"
        btns.append([{"text": "💳 پرداخت آنلاین",
                      "url": f"{url}{sep}amount={total}&ref={payload}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"uev_{ev['id']}"}])
    send(cid, txt, {"inline_keyboard": btns})
    return txid


# ==================== 🆕 فاز ۱۳: پرداخت در محل ====================
def start_onsite_payment(cid, uid, ev, rid, amount):
    """💰 پرداخت در محل — ثبت بدهی و تأیید ثبت‌نام"""
    # 💳 فاز ۱۷ — کارمزد پرداخت در محل (اگر فعال باشد)
    fee, total = calc_fee(amount, "onsite")

    payload = _payload("os", ev, uid, rid)
    ref = f"OS{int(time.time()) % 1000000}"
    txid = db_execute("""INSERT INTO transactions
        (bale_user_id, event_id, registration_id, payload, amount,
         status, method, transaction_id, fee_amount, base_amount,
         form_response_id)
        VALUES (?,?,?,?,?,'onsite',?,?,?,?,?)""",
        (uid, ev["id"], rid, payload, total, "onsite", ref, fee, amount,
         _frid(ev)))
    _tag_plan_part(txid, ev)
    amount = total
    mark_payload(ev, rid, payload)

    send(cid, render("pay_txt_onsite", amount=fmt(amount), ref=ref))
    log_action(uid, "onsite_pending", {"amount": amount, "ref": ref})

    u = get_user(uid) or {}
    _notify_admins(
        f"💰 ثبت‌نام با پرداخت در محل\n━━━━━━━━━━━━━━\n\n"
        f"🎉 {ev.get('title')}\n"
        f"👤 {u.get('first_name') or ''} {u.get('last_name') or ''}\n"
        f"📱 {u.get('mobile') or '—'}\n"
        f"💰 {fmt(amount)} {CURRENCY_LABEL}\n"
        f"🔖 {ref}\n\n"
        f"💡 بعد از دریافت وجه، از «🧾 تراکنش‌ها» تأیید کنید.")

    # ثبت‌نام قطعی می‌شود ولی بدهی باقی می‌ماند
    try:
        import events as _ev
        _ev.finish_registration(cid, uid, ev, rid)
    except Exception as e:
        log(f"⚠️ finish_registration پس از onsite: {e}")
    return txid


def mark_onsite_paid(cid, uid, txid):
    """✅ ادمین تأیید می‌کند که پول در محل دریافت شد"""
    import permissions as perm
    if not perm.require(cid, uid, "fin_approve", send):
        return
    # ⚠️ txid ممکن است None یا خراب باشد (callback دستکاری‌شده)
    try:
        txid = int(txid)
    except (TypeError, ValueError):
        return send(cid, "❌ شناسه تراکنش نامعتبر است")
    tx = db_execute("SELECT * FROM transactions WHERE id=?",
                    (txid,), fetch="one")
    if not tx:
        return send(cid, "❌ تراکنش یافت نشد")
    if tx.get("status") == "paid":
        return send(cid, "ℹ️ قبلاً تأیید شده است")

    db_execute("""UPDATE transactions SET status='paid',
        updated_at=CURRENT_TIMESTAMP WHERE id=?""", (tx["id"],))
    if tx.get("registration_id"):
        db_execute("""UPDATE event_registrations SET amount_paid=?,
            paid_at=CURRENT_TIMESTAMP WHERE id=?""",
            (tx.get("amount"), tx["registration_id"]))
    elif tx.get("form_response_id"):
        db_execute("UPDATE form_responses SET amount_paid=?, "
                   "payment_status='paid' WHERE id=?",
                   (tx.get("amount"), tx["form_response_id"]))

    send(cid, f"✅ دریافت وجه در محل ثبت شد ({fmt(tx.get('amount'))} "
              f"{CURRENCY_LABEL})")
    log_action(uid, "onsite_confirmed", {"tx": tx["id"]})
    if tx.get("bale_user_id"):
        send(tx["bale_user_id"],
             f"✅ پرداخت شما در محل ثبت شد\n\n"
             f"💰 مبلغ: {fmt(tx.get('amount'))} {CURRENCY_LABEL}\n"
             f"💚 سپاس از شما.")


# ==================== 🆕 فاز ۱۳: پرداخت با امتیاز ====================
def start_points_payment(cid, uid, ev, rid, amount, auto=False):
    """
    🏆 پرداخت با امتیاز.

    اگر امتیاز کل مبلغ را پوشش دهد → ثبت‌نام قطعی.
    اگر بخشی را پوشش دهد → امتیاز کسر و باقی‌مانده نقدی گرفته می‌شود.
    """
    q = points_quote(uid, amount)
    if not q["ok"]:
        send(cid, render("pay_txt_points_low",
                         have=q["have"], need=q["need_full"]))
        if not auto:
            _offer_other_methods(cid, uid, ev, rid, amount, skip="points")
        return None

    if not auto and not q["full"]:
        # تأیید کاربر برای حالت ترکیبی
        set_state(uid, STATE_POINTS_CONFIRM, {
            "eid": ev.get("id"), "rid": rid, "amount": amount,
        }, merge=False)
        detail = (f"🧮 با {q['use']} امتیاز، {fmt(q['covered'])} "
                  f"{CURRENCY_LABEL} پوشش داده می‌شود\n"
                  f"💳 باقی‌مانده: {fmt(q['rest'])} {CURRENCY_LABEL}")
        return send(cid, render("pay_txt_points_offer",
                                amount=fmt(amount), have=q["have"],
                                rate=f"{points_rate_rial():,}"
                                     .replace(",", "٬"),
                                detail=detail),
                    {"inline_keyboard": [
                        [{"text": "✅ بله، امتیاز را کسر کن",
                          "callback_data": f"paypt_go_{rid}"}],
                        [{"text": "💳 روش دیگر",
                          "callback_data": f"paypt_other_{rid}"}],
                    ]})

    return _do_points_payment(cid, uid, ev, rid, amount, q)


def _do_points_payment(cid, uid, ev, rid, amount, q=None):
    """کسر واقعی امتیاز و ادامه مسیر"""
    q = q or points_quote(uid, amount)
    if not q["ok"]:
        return send(cid, render("pay_txt_points_low",
                                have=q["have"], need=q["need_full"]))

    ok, left = spend_points(uid, q["use"], f"payment_ev{ev.get('id')}")
    if not ok:
        return send(cid, "⚠️ کسر امتیاز ناموفق بود. دوباره تلاش کنید.")

    payload = _payload("pt", ev, uid, rid)
    db_execute("""INSERT INTO transactions
        (bale_user_id, event_id, registration_id, payload, amount,
         status, method, points_used, transaction_id, form_response_id)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (uid, ev["id"], rid, payload, q["covered"],
         "paid" if q["full"] else "partial", "points", q["use"],
         f"PT{int(time.time()) % 1000000}", _frid(ev)))

    log_action(uid, "points_payment",
               {"points": q["use"], "amount": q["covered"]})

    if q["full"]:
        mark_paid(ev, rid, q["covered"], full=True)
        send(cid, render("pay_txt_points_done", used=q["use"],
                         covered=fmt(q["covered"]), left=left))
        finish_target(cid, uid, ev, rid)
        return True

    # ترکیبی → باقی‌مانده را با روش دیگری بگیر
    send(cid, render("pay_txt_points_partial", used=q["use"],
                     covered=fmt(q["covered"]), rest=fmt(q["rest"])))
    mark_paid(ev, rid, q["covered"], full=False)
    return _offer_other_methods(cid, uid, ev, rid, q["rest"], skip="points")


def _offer_other_methods(cid, uid, ev, rid, amount, skip=None):
    """وقتی امتیاز کافی نبود یا کاربر نخواست — بقیه روش‌ها را پیشنهاد بده"""
    methods = [m for m in allowed_methods(ev)
               if m != skip and m not in ("none", "points", "multi")]
    methods = [m for m in methods if method_available(m)[0]]
    if not methods:
        # fallback به تک روش پیش‌فرض
        return start_wallet_payment(cid, uid, ev, rid, amount) \
            if PAYMENT_ENABLED else start_card_payment(
                cid, uid, ev, rid, amount, ev.get("payment_card_id"))
    if len(methods) == 1:
        return _dispatch(cid, uid, ev, rid, amount, methods[0])
    return show_method_choice(cid, uid, ev, rid, amount, methods)


# ==================== 🆕 فاز ۱۳: چند روشی ====================
def show_method_choice(cid, uid, ev, rid, amount, methods=None):
    """
    🎛️ کاربر خودش روش پرداخت را انتخاب می‌کند.

    طبق فایل معماری: هر روش با یک توضیح کوتاه نمایش داده می‌شود.
    """
    methods = methods or [m for m in allowed_methods(ev) if m != "none"]

    hints = {
        "bale_wallet": "⚡ آنی و خودکار — توصیه‌شده",
        "card": "📸 ارسال رسید — تأیید توسط ادمین",
        "custom_gateway": "🔗 انتقال به صفحه پرداخت",
        "onsite": "📅 پرداخت روز رویداد در محل",
        "points": "🏅 کسر از امتیاز باشگاه شما",
    }
    # 🛡️ فاز ۱۸-ب — کدام روش‌ها فیلترشکن را نمی‌پذیرند
    net_note = "🛡️ بدون فیلترشکن"

    btns, lines = [], []
    shown = 0
    for m in methods:
        info = PAYMENT_METHODS.get(m)
        if not info:
            continue
        ok, why = method_available(m)
        if not ok:
            continue
        label = f"{info['icon']} {info['name']}"
        extra = hints.get(m, "")
        if m == "points":
            q = points_quote(uid, amount)
            if not q["ok"]:
                continue
            extra = (f"🏅 {q['use']} امتیاز"
                     + ("" if q["full"] else f" + {fmt(q['rest'])} نقدی"))
        lines += [f"{label}", f"   {extra}"]
        if vpn_warn_needed(m):
            lines.append(f"   {net_note}")
        lines.append("")
        btns.append([{"text": label, "callback_data": f"paypick_{m}_{rid}"}])
        shown += 1

    if shown == 0:
        send(cid, "⚠️ فعلاً هیچ روش پرداختی در دسترس نیست.\n"
                  "لطفاً با پشتیبانی تماس بگیرید.")
        _notify_admins(f"⚠️ رویداد «{ev.get('title')}» هیچ روش پرداخت "
                       f"فعالی ندارد — کاربر نتوانست پرداخت کند!")
        return None
    if shown == 1:
        # فقط یکی مانده → مستقیم برو، کاربر را معطل نکن
        only = btns[0][0]["callback_data"].split("_")[1]
        return _dispatch(cid, uid, ev, rid, amount, only)

    btns.append([{"text": "❌ انصراف",
                  "callback_data": f"uev_{ev.get('id')}"}])

    header = render("pay_txt_choose", title=ev.get("title") or "ثبت‌نام",
                    amount=fmt(amount))
    set_state(uid, STATE_PICK_METHOD, {
        "eid": ev.get("id"), "rid": rid, "amount": amount,
    }, merge=False)
    send(cid, header + "\n\n" + "\n".join(lines).rstrip(),
         {"inline_keyboard": btns})
    return None


def _dispatch(cid, uid, ev, rid, amount, method):
    """اجرای یک روش پرداخت مشخص"""
    if method == "card":
        return start_card_payment(cid, uid, ev, rid, amount,
                                  ev.get("payment_card_id"))
    if method == "custom_gateway":
        return start_gateway_payment(cid, uid, ev, rid, amount,
                                     ev.get("payment_gateway_id"))
    if method == "onsite":
        return start_onsite_payment(cid, uid, ev, rid, amount)
    if method == "points":
        return start_points_payment(cid, uid, ev, rid, amount)
    return start_wallet_payment(cid, uid, ev, rid, amount)


def pick_method(cid, uid, method, rid):
    """کاربر روی یکی از روش‌ها زد"""
    d = get_state_data(uid)
    clear_state(uid)
    try:
        rid = int(rid)
    except (TypeError, ValueError):
        return send(cid, "❌ درخواست نامعتبر")

    reg = db_execute("SELECT * FROM event_registrations WHERE id=?",
                     (rid,), fetch="one")
    if not reg or reg.get("bale_user_id") != uid:
        return send(cid, "❌ ثبت‌نام یافت نشد")

    import events as _ev
    ev = _ev.get_event(reg.get("event_id"))
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    amount = int(d.get("amount") or 0)
    if amount <= 0:
        amount = int(ev.get("price") or 0) - int(reg.get("amount_paid") or 0)
    if amount <= 0:
        return send(cid, "ℹ️ مبلغی برای پرداخت باقی نمانده است")

    if method not in allowed_methods(ev) and method != "points":
        return send(cid, "❌ این روش برای این رویداد مجاز نیست")
    ok, why = method_available(method)
    if not ok:
        return send(cid, f"⚠️ این روش در دسترس نیست: {why}")

    return _dispatch(cid, uid, ev, rid, amount, method)


def confirm_points(cid, uid, rid, yes=True):
    """پاسخ کاربر به پیشنهاد پرداخت ترکیبی با امتیاز"""
    d = get_state_data(uid)
    clear_state(uid)
    try:
        rid = int(rid)
    except (TypeError, ValueError):
        return send(cid, "❌ درخواست نامعتبر")

    reg = db_execute("SELECT * FROM event_registrations WHERE id=?",
                     (rid,), fetch="one")
    if not reg or reg.get("bale_user_id") != uid:
        return send(cid, "❌ ثبت‌نام یافت نشد")
    import events as _ev
    ev = _ev.get_event(reg.get("event_id"))
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    amount = int(d.get("amount") or 0) or int(ev.get("price") or 0)
    if not yes:
        return _offer_other_methods(cid, uid, ev, rid, amount, skip="points")
    return _do_points_payment(cid, uid, ev, rid, amount)


def best_available_method(preferred=None):
    """
    🎯 فاز ۱۸-الف — اولین روش پرداختی که واقعاً قابل استفاده است.

    🔴 باگ رفع‌شده: اگر ادمین روشی را انتخاب می‌کرد که تنظیم نشده بود
       (مثلاً «درگاه سفارشی» بدون تعریف درگاه)، کاربر بن‌بست می‌خورد
       و پیام «درگاه پرداختی فعال نیست» می‌گرفت. حالا خودکار به
       روش سالم بعدی می‌رویم.
    """
    order = [preferred] if preferred else []
    order += ["bale_wallet", "card", "custom_gateway", "onsite"]
    for m in order:
        if m and m not in ("none", "multi") and method_available(m)[0]:
            return m
    return None


def route_payment(cid, uid, ev, rid, amount):
    """
    مسیریابی بر اساس روش پرداخت رویداد یا فرم.
    این تابع نقطه ورود واحد برای همه پرداخت‌هاست.

    🆕 فاز ۱۳: «در محل»، «با امتیاز» و «چند روشی».
    🆕 فاز ۱۸-الف: اقساطی/جلسه‌ای + بازگشت خودکار به روش سالم.
    """
    method = ev.get("payment_method") or "bale_wallet"
    if method == "none":
        return None
    if method == "multi":
        return show_method_choice(cid, uid, ev, rid, amount)

    # 💠 فاز ۱۸-الف — پرداخت مرحله‌ای (اقساط / جلسه‌ای / پیش‌پرداخت)
    if method in ("installment", "sessions", "prepay"):
        import payplan
        return payplan.start_plan(cid, uid, ev, rid, amount, method)

    ok, why = method_available(method)
    if not ok:
        alt = best_available_method()
        if not alt:
            _notify_admins(
                f"⚠️ کاربر می‌خواست پرداخت کند ولی هیچ روش پرداختی "
                f"تنظیم نشده!\n\nروش انتخابی: {method} ({why})\n"
                f"💡 تنظیمات › روش‌های پرداخت")
            send(cid, "🙏 پوزش می‌خواهیم — پرداخت موقتاً در دسترس نیست.\n\n"
                      "به ادمین اطلاع دادیم؛ به‌زودی درست می‌شود 💚")
            return None
        log(f"♻️ روش {method} در دسترس نبود ({why}) → {alt}")
        method = alt

    return _dispatch(cid, uid, ev, rid, amount, method)


# ==================== تنظیمات پرداخت ====================
def _guard_money(cid, uid):
    """
    🔒 فاز ۱۳ — گارد بخش مالی.

    درخواست صریح کاربر: «جز سوپر ادمین کسی دسترسی به مالی و
    درآمد کل ربات نداشته باشد». fin_view در SUPER_ONLY است،
    پس has_perm برای همه به‌جز سوپرادمین False برمی‌گرداند.
    """
    import permissions as perm
    if perm.has_perm(uid, "fin_view"):
        return True
    send(cid, "🔒 بخش مالی و درآمد فقط برای سوپرادمین است")
    return False


def show_payment_settings(cid, uid):
    """💳 پرداخت و مالی — فاز ۱۳: همه چیز پول در یک جا"""
    if not _guard(cid, uid):
        return
    if not _guard_money(cid, uid):
        return

    cards = len(get_cards())
    gws = len(get_gateways())
    pending_rcp = db_scalar(
        "SELECT COUNT(*) FROM payment_receipts WHERE status='pending'") or 0
    paid = db_execute(
        "SELECT COUNT(*) c, COALESCE(SUM(amount),0) s FROM transactions "
        "WHERE status IN ('paid','confirmed','success')", fetch="one") or {}
    try:
        n_onsite = db_scalar("SELECT COUNT(*) FROM transactions "
                             "WHERE status='onsite'") or 0
        pts_used = db_scalar("SELECT COALESCE(SUM(points_used),0) "
                             "FROM transactions") or 0
    except Exception:
        n_onsite, pts_used = 0, 0

    lines = ["💳 پرداخت و مالی", "━━━━━━━━━━━━━━", "",
             "📌 وضعیت روش‌ها:", ""]
    lines.append("💳 کارت به کارت: "
                 + (f"🟢 {cards} کارت" if cards else "🔴 کارتی ثبت نشده"))
    if PAYMENT_ENABLED:
        mode = "🧪 آزمایشی" if PAYMENT_TEST_MODE else "💰 واقعی"
        lines.append(f"🏦 کیف پول بله: 🟢 فعال ({mode})")
    else:
        lines.append("🏦 کیف پول بله: 🔴 توکن تنظیم نشده")
    lines.append("🔗 درگاه سفارشی: "
                 + (f"🟢 {gws} درگاه" if gws else "🔴 تعریف نشده"))
    lines.append("💰 پرداخت در محل: 🟢 همیشه در دسترس")
    if points_enabled():
        rate = fmt(points_rate_rial())
        lines.append(f"🏆 پرداخت با امتیاز: 🟢 فعال "
                     f"(هر امتیاز {rate} {CURRENCY_LABEL})")
    else:
        lines.append("🏆 پرداخت با امتیاز: 🔴 غیرفعال")

    lines += ["", "📊 آمار مالی:",
              f"├── ✅ تراکنش موفق: {paid.get('c') or 0}",
              f"├── 💰 مجموع: {fmt(paid.get('s') or 0)} {CURRENCY_LABEL}",
              f"├── 🧾 رسید در انتظار: {pending_rcp}"]
    if n_onsite:
        lines.append(f"├── 💰 بدهی در محل: {n_onsite}")
    if pts_used:
        lines.append(f"├── 🏆 امتیاز خرج‌شده: {pts_used}")
    lines.append("└── 💡 جزئیات کامل در «داشبورد درآمد»")

    send_or_edit(cid, "\n".join(lines),
                 kb_payment_settings(pending_rcp, uid))


# ==================== 🎛️ روش‌های پرداخت پیشرفته ====================
# ══════════════════════════════════════════════════════════
# 🛡️ فاز ۱۸-ب — پنل مدیریت هشدار فیلترشکن
# ══════════════════════════════════════════════════════════
def show_vpn_settings(cid, uid):
    """🛡️ تنظیمات هشدار فیلترشکن"""
    if not _guard(cid, uid) or not _guard_money(cid, uid):
        return

    on = vpn_warn_enabled()
    warned = sorted(VPN_WARN_METHODS)
    skipped = sorted(VPN_SKIP_METHODS - {"none"})

    lines = [
        "🛡️ هشدار خاموش کردن فیلترشکن", "━━━━━━━━━━━━━━", "",
        f"وضعیت: {'🟢 فعال' if on else '🔴 خاموش'}", "",
        "درگاه‌های بانکی ایران با فیلترشکن کار نمی‌کنند.",
        "این هشدار قبل از هدایت کاربر به درگاه نمایش داده می‌شود.", "",
        "📌 هشدار داده می‌شود برای:",
    ]
    for m in warned:
        info = PAYMENT_METHODS.get(m, {})
        lines.append(f"   ✅ {info.get('icon','')} {info.get('name', m)}")
    lines += ["", "📌 هشدار داده نمی‌شود برای:"]
    for m in skipped:
        info = PAYMENT_METHODS.get(m, {})
        why = {"card": "کاربر در اپ بانک خودش واریز می‌کند",
               "points": "پولی جابه‌جا نمی‌شود",
               "onsite": "پرداخت حضوری است"}.get(m, "")
        lines.append(f"   ⬜ {info.get('icon','')} {info.get('name', m)}"
                     + (f" — {why}" if why else ""))

    lines += ["", "━━━━━━━━━━━━━━", "📄 متن کامل هشدار:", "",
              vpn_warn_text()[:400]]

    btns = [
        [{"text": f"🛡️ هشدار فیلترشکن: {'✅ فعال' if on else '❌ خاموش'}",
          "callback_data": "payvpn_toggle"}],
        [{"text": "✏️ ویرایش متن کامل",
          "callback_data": "ptx_pay_txt_vpn_warn"}],
        [{"text": "✏️ ویرایش یادآوری کوتاه",
          "callback_data": "ptx_pay_txt_vpn_short"}],
        [{"text": "👁️ پیش‌نمایش", "callback_data": "payvpn_preview"}],
        [{"text": "🔙 پرداخت و مالی", "callback_data": "set_payment"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_vpn_warn(cid, uid):
    """روشن/خاموش کردن هشدار فیلترشکن"""
    if not _guard(cid, uid) or not _guard_money(cid, uid):
        return
    new = "0" if vpn_warn_enabled() else "1"
    set_setting("pay_vpn_warn_on", new,
                "🛡️ هشدار خاموش کردن فیلترشکن", "payment", uid)
    log_action(uid, "vpn_warn_toggle", {"on": new})
    send(cid, "✅ هشدار فیلترشکن " + ("فعال شد" if new == "1"
                                     else "خاموش شد"))
    return show_vpn_settings(cid, uid)


def preview_vpn_warn(cid, uid):
    """👁️ کاربر دقیقاً چه می‌بیند"""
    if not _guard(cid, uid):
        return
    if not vpn_warn_enabled():
        return send(cid, "⚠️ هشدار خاموش است — کاربر چیزی نمی‌بیند.")
    send(cid, "👁️ پیام کامل (قبل از درگاه):")
    send(cid, vpn_warn_text())
    send(cid, "👁️ یادآوری کوتاه (ته پیام پرداخت):"
              + vpn_warn_inline("bale_wallet"))
    return show_vpn_settings(cid, uid)


def show_advanced_payment(cid, uid):
    """
    🎛️ تنظیمات پیشرفته روش‌های پرداخت — فاز ۱۳

    🎯 «آپشن های روش پرداخت پیشرفته تر بشه مثل امکان پرداخت با
       چند روش و پرداخت با امتیاز»
    """
    if not _guard(cid, uid):
        return
    if not _guard_money(cid, uid):
        return

    en = points_enabled()
    rate = fmt(points_rate_rial())
    pct = points_max_pct()
    keep = points_min_keep()
    dflt = get_setting("pay_default_methods", "bale_wallet,card")

    lines = [
        "🎛️ روش‌های پرداخت پیشرفته", "━━━━━━━━━━━━━━", "",
        "🧩 چند روشی:",
        "   هنگام ساخت رویداد/فرم می‌توانید «🎛️ چند روشی» را",
        "   انتخاب کنید تا کاربر خودش روش را برگزیند.",
        "",
        f"   📌 پیش‌فرض پیشنهادی: {_methods_label(dflt)}",
        "",
        "━━━━━━━━━━━━━━",
        "🏆 پرداخت با امتیاز:",
        f"   وضعیت: {'🟢 فعال' if en else '🔴 غیرفعال'}",
        f"   💱 ارزش هر امتیاز: {rate} {CURRENCY_LABEL}",
        f"   📊 حداکثر سهم امتیاز: {pct}%",
        f"   🔒 حداقل امتیاز باقی‌مانده: {keep}",
        "",
    ]
    if en:
        if pct >= 100:
            lines.append("   ✅ کاربر می‌تواند کل مبلغ را با امتیاز بدهد")
        else:
            lines.append(f"   🧮 حداکثر {pct}% با امتیاز، "
                         f"بقیه نقدی (پرداخت ترکیبی)")
    else:
        lines.append("   💡 برای فعال‌سازی دکمه زیر را بزنید")

    lines += ["", "━━━━━━━━━━━━━━",
              "💰 پرداخت در محل:",
              "   کاربر ثبت‌نام می‌کند و روز رویداد پرداخت می‌کند.",
              "   بدهی در «🧾 تراکنش‌ها» با وضعیت «در محل» می‌ماند",
              "   و بعد از دریافت وجه، ادمین آن را تأیید می‌کند."]

    btns = [
        [{"text": ("🏆 پرداخت با امتیاز: ✅ فعال" if en
                   else "🏆 پرداخت با امتیاز: ❌ غیرفعال"),
          "callback_data": "payp_toggle"}],
    ]
    if en:
        btns += [
            [{"text": f"💱 ارزش هر امتیاز ({rate})",
              "callback_data": "payn_pay_points_rate"}],
            [{"text": f"📊 حداکثر سهم امتیاز ({pct}%)",
              "callback_data": "payn_pay_points_max_pct"}],
            [{"text": f"🔒 حداقل امتیاز باقی‌مانده ({keep})",
              "callback_data": "payn_pay_points_min_keep"}],
        ]
    btns += [
        [{"text": "🧩 روش‌های پیش‌فرض چند روشی",
          "callback_data": "paydm"}],
        [{"text": "💳 کارمزد درگاه پرداخت",
          "callback_data": "pay_fee"}],
        [{"text": "💰 بدهی‌های پرداخت در محل",
          "callback_data": "pay_onsite"}],
        [{"text": "🔙 پرداخت و مالی", "callback_data": "set_payment"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ==================== 💳 تنظیمات کارمزد (چندروشی) ====================
def show_fee_settings(cid, uid):
    """💳 کارمزد پرداخت — لیست همه روش‌ها"""
    if not _guard(cid, uid) or not _guard_money(cid, uid):
        return

    lines = ["💳 کارمزد روش‌های پرداخت", "━━━━━━━━━━━━━━", "",
             "برای هر روش می‌توانید کارمزد جداگانه تعیین کنید:", ""]
    btns = []
    for m in FEE_METHODS:
        info = PAYMENT_METHODS.get(m, {})
        on = fee_enabled(m)
        if on:
            pct = fee_percent(m)
            fix = fee_fixed(m)
            bits = []
            if pct > 0:
                bits.append(f"{pct:g}٪")
            if fix > 0:
                bits.append(money(fix))
            desc = " + ".join(bits) if bits else "۰ (بی‌اثر)"
            lines.append(f"🟢 {info.get('icon')} {info.get('name')}: {desc}")
        else:
            lines.append(f"⚪ {info.get('icon')} {info.get('name')}: خاموش")
        btns.append([{"text": f"{'🟢' if on else '⚪'} {info.get('icon')} "
                              f"{info.get('name')}",
                      "callback_data": f"payfm_{m}"}])

    lines += ["", "━━━━━━━━━━━━━━",
              "ℹ️ فرمول: (مبلغ × درصد) + مبلغ ثابت",
              "سپس بین «حداقل» و «سقف» محدود می‌شود."]
    btns.append([{"text": "🔙 پرداخت پیشرفته", "callback_data": "pay_adv"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_fee_method(cid, uid, method):
    """💳 تنظیمات کارمزد یک روش مشخص"""
    if not _guard(cid, uid) or not _guard_money(cid, uid):
        return
    if method not in FEE_METHODS:
        return send(cid, "❌ روش نامعتبر")

    info = PAYMENT_METHODS.get(method, {})
    on = fee_enabled(method)
    pct = fee_percent(method)
    fix = fee_fixed(method)
    lo = _fee_amount(method, "min")
    hi = _fee_amount(method, "max")

    lines = [
        f"💳 کارمزد {info.get('icon')} {info.get('name')}",
        "━━━━━━━━━━━━━━", "",
        f"وضعیت: {'🟢 فعال' if on else '🔴 خاموش'}",
        f"🏷️ عنوان: {fee_label(method)}",
        f"📊 درصد: {pct:g}٪",
        f"➕ مبلغ ثابت: {money(fix) if fix else '— ندارد'}",
        f"🔽 حداقل: {money(lo) if lo else '— ندارد'}",
        f"🔼 سقف: {money(hi) if hi else '— بی‌سقف'}",
    ]

    if on and (pct > 0 or fix > 0):
        sample = 1000000
        f_, t_ = calc_fee(sample, method)
        lines += ["", f"🧮 مثال ({money(sample)}):",
                  f"   + {fee_label(method)}: {money(f_)}",
                  f"   = قابل پرداخت: {money(t_)}"]
    elif on:
        lines += ["", "⚠️ فعال است ولی درصد و مبلغ ثابت صفرند — بی‌اثر"]

    btns = [[{"text": f"💳 کارمزد: {'✅ فعال' if on else '❌ خاموش'}",
              "callback_data": f"payft_{method}"}]]
    if on:
        btns += [
            [{"text": f"📊 درصد ({pct:g}٪)",
              "callback_data": f"payfe_pct_{method}"},
             {"text": f"➕ ثابت ({fix:,})",
              "callback_data": f"payfe_fix_{method}"}],
            [{"text": f"🔽 حداقل ({lo:,})",
              "callback_data": f"payfe_min_{method}"},
             {"text": f"🔼 سقف ({hi:,})",
              "callback_data": f"payfe_max_{method}"}],
            [{"text": "🏷️ عنوان نمایشی",
              "callback_data": f"payfe_label_{method}"}],
        ]
    btns.append([{"text": "🔙 همه روش‌ها", "callback_data": "pay_fee"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_fee(cid, uid, method):
    """روشن/خاموش کردن کارمزد یک روش"""
    if not _guard(cid, uid) or not _guard_money(cid, uid):
        return
    if method not in FEE_METHODS:
        return send(cid, "❌ روش نامعتبر")
    new = "0" if fee_enabled(method) else "1"
    set_setting(_fk(method, "on"), new, "کارمزد", "payment", uid)
    log_action(uid, "pay_fee_toggle", {"method": method, "on": new})
    nm = PAYMENT_METHODS.get(method, {}).get("name", method)
    send(cid, f"✅ کارمزد {nm} " + ("فعال شد" if new == "1" else "خاموش شد"))
    return show_fee_method(cid, uid, method)


def start_fee_edit(cid, uid, part, method):
    """ویرایش یکی از مقادیر کارمزد"""
    if not _guard(cid, uid) or not _guard_money(cid, uid):
        return
    if method not in FEE_METHODS or part not in ("pct", "fix", "min",
                                                 "max", "label"):
        return send(cid, "❌ نامعتبر")

    nm = PAYMENT_METHODS.get(method, {}).get("name", method)
    titles = {
        "pct": "📊 درصد کارمزد", "fix": "➕ مبلغ ثابت کارمزد",
        "min": "🔽 حداقل کارمزد", "max": "🔼 سقف کارمزد",
        "label": "🏷️ عنوان نمایشی",
    }
    hints = {
        "pct": "چند درصد روی مبلغ اضافه شود؟\n\nمثال: 2  یا  2.5\n۰ = بدون درصد",
        "fix": f"مبلغ ثابت به {CURRENCY_LABEL} که به هر تراکنش اضافه شود"
                "\n\n۰ = ندارد",
        "min": f"حداقل کارمزد به {CURRENCY_LABEL}\n\n۰ = بدون حداقل",
        "max": f"سقف کارمزد به {CURRENCY_LABEL}\n\n۰ = بی‌سقف",
        "label": "این عنوان به کاربر نشان داده می‌شود.\n\n"
                 "مثال: کارمزد درگاه پرداخت",
    }
    cur = get_setting(_fk(method, part), "0")
    set_state(uid, STATE_PAY_FEE, {"method": method, "part": part},
              merge=False)
    send(cid, (f"✏️ {titles[part]} — {nm}\n━━━━━━━━━━━━━━\n\n"
               f"📄 مقدار فعلی: {cur}\n\n{hints[part]}"), kb_cancel())


def handle_fee_input(message):
    """دریافت مقدار جدید کارمزد"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid)
    method, part = d.get("method"), d.get("part")

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_fee_method(cid, uid, method)

    if method not in FEE_METHODS:
        clear_state(uid)
        return send(cid, "❌ روش نامعتبر", kb_remove())

    if part == "label":
        if not raw:
            return send(cid, "⚠️ عنوان نمی‌تواند خالی باشد:")
        set_setting(_fk(method, part), raw[:60], "عنوان کارمزد",
                    "payment", uid)
        clear_state(uid)
        send(cid, f"✅ عنوان ثبت شد: {raw[:60]}", kb_remove())
        return show_fee_method(cid, uid, method)

    text = normalize_digits(raw).replace("٫", ".").replace("،", "")
    if part == "pct":
        cleaned = re.sub(r"[^\d.]", "", text)
        if not cleaned or not any(ch.isdigit() for ch in cleaned):
            return send(cid, "⚠️ عدد معتبر بفرستید (مثال: 2.5):")
        try:
            val = float(cleaned)
        except ValueError:
            return send(cid, "⚠️ عدد معتبر بفرستید (مثال: 2.5):")
        if val < 0 or val > 100:
            return send(cid, "⚠️ درصد باید بین ۰ تا ۱۰۰ باشد:")
        set_setting(_fk(method, part), f"{val:g}", "درصد کارمزد",
                    "payment", uid)
        shown = f"{val:g}٪"
    else:
        digits = re.sub(r"[^\d]", "", text)
        if not digits:
            return send(cid, "⚠️ فقط عدد بفرستید:")
        val = min(100000000, int(digits))
        set_setting(_fk(method, part), str(val), "مبلغ کارمزد",
                    "payment", uid)
        shown = f"{val:,} {CURRENCY_LABEL}"

    clear_state(uid)
    log_action(uid, "pay_fee_setting", {"method": method, "part": part})
    send(cid, f"✅ ذخیره شد: {shown}", kb_remove())
    return show_fee_method(cid, uid, method)


def _methods_label(raw):
    """رشته 'card,onsite' → '💳 کارت به کارت + 💰 پرداخت در محل'"""
    out = []
    for m in str(raw or "").split(","):
        m = m.strip()
        info = PAYMENT_METHODS.get(m)
        if info:
            out.append(f"{info['icon']} {info['name']}")
    return " + ".join(out) if out else "— چیزی انتخاب نشده —"


def toggle_points_payment(cid, uid):
    """روشن/خاموش کردن پرداخت با امتیاز"""
    if not _guard(cid, uid) or not _guard_money(cid, uid):
        return
    new = "0" if points_enabled() else "1"
    set_setting("pay_points_enabled", new,
                "🏆 پرداخت با امتیاز فعال", "payment", uid)
    log_action(uid, "pay_points_toggle", {"on": new})
    send(cid, "✅ پرداخت با امتیاز " + ("فعال شد" if new == "1"
                                       else "غیرفعال شد"))
    return show_advanced_payment(cid, uid)


def show_default_methods(cid, uid):
    """🧩 انتخاب روش‌های پیش‌فرض برای حالت چند روشی"""
    if not _guard(cid, uid) or not _guard_money(cid, uid):
        return
    cur = [m.strip() for m in
           str(get_setting("pay_default_methods", "bale_wallet,card")).split(",")
           if m.strip()]

    lines = ["🧩 روش‌های پیش‌فرض چند روشی", "━━━━━━━━━━━━━━", "",
             "وقتی رویداد/فرم جدیدی می‌سازید و «چند روشی» را",
             "انتخاب می‌کنید، این روش‌ها از قبل تیک خورده‌اند.", ""]
    btns = []
    for m in MULTI_CHOICES:
        info = PAYMENT_METHODS[m]
        on = m in cur
        ok, why = method_available(m)
        label = f"{'✅' if on else '⬜'} {info['icon']} {info['name']}"
        if not ok:
            label += f" ⚠️ {why}"
        btns.append([{"text": label, "callback_data": f"paydm_{m}"}])
        lines.append(f"{'✅' if on else '⬜'} {info['icon']} {info['name']}"
                     + (f"  ⚠️ {why}" if not ok else ""))
    btns.append([{"text": "🔙 بازگشت", "callback_data": "pay_adv"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_default_method(cid, uid, method):
    """تیک زدن/برداشتن یک روش از پیش‌فرض‌ها"""
    if not _guard(cid, uid) or not _guard_money(cid, uid):
        return
    if method not in MULTI_CHOICES:
        return send(cid, "❌ روش نامعتبر")
    cur = [m.strip() for m in
           str(get_setting("pay_default_methods", "bale_wallet,card")).split(",")
           if m.strip()]
    if method in cur:
        cur.remove(method)
    else:
        cur.append(method)
    set_setting("pay_default_methods", ",".join(cur),
                "🧩 روش‌های پیش‌فرض چند روشی", "payment", uid)
    return show_default_methods(cid, uid)


def start_pay_num(cid, uid, key):
    """ویرایش یک عدد در تنظیمات پرداخت"""
    if not _guard(cid, uid) or not _guard_money(cid, uid):
        return
    titles = {k: t for k, t, _ in POINTS_SETTINGS}
    if key not in titles:
        return send(cid, "❌ نامعتبر")
    cur = get_setting(key, next(d for k, _, d in POINTS_SETTINGS if k == key))
    hint = {
        "pay_points_rate": f"هر ۱ امتیاز چند {CURRENCY_LABEL} ارزش دارد؟"
                           "\n\nمثال: 10000",
        "pay_points_max_pct": "حداکثر چند درصد از مبلغ با امتیاز؟\n\n"
                              "۱۰۰ = کل مبلغ  |  ۵۰ = نصف",
        "pay_points_min_keep": "کاربر حداقل چند امتیاز باید نگه دارد؟\n\n"
                               "۰ = محدودیتی نیست",
    }.get(key, "مقدار جدید:")

    set_state(uid, STATE_PAY_NUM, {"key": key}, merge=False)
    send(cid, (f"✏️ {titles[key]}\n━━━━━━━━━━━━━━\n\n"
               f"📄 مقدار فعلی: {cur}\n\n{hint}"), kb_cancel())


def handle_pay_num(message):
    """دریافت عدد جدید تنظیمات پرداخت"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = normalize_digits((message.get("text") or "").strip())
    d = get_state_data(uid)
    key = d.get("key")

    if text in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_advanced_payment(cid, uid)

    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return send(cid, "⚠️ فقط عدد بفرستید:")
    val = int(digits)

    if key == "pay_points_max_pct" and val > 100:
        return send(cid, "⚠️ درصد نمی‌تواند بیشتر از ۱۰۰ باشد:")
    if key == "pay_points_rate" and val < 1:
        return send(cid, f"⚠️ ارزش هر امتیاز حداقل ۱ {CURRENCY_LABEL} است:")

    titles = {k: t for k, t, _ in POINTS_SETTINGS}
    set_setting(key, str(val), titles.get(key, key), "payment", uid)
    clear_state(uid)
    log_action(uid, "pay_setting", {"key": key, "value": val})
    send(cid, f"✅ ذخیره شد: {val}", kb_remove())
    return show_advanced_payment(cid, uid)


def show_onsite_debts(cid, uid, page=0):
    """💰 بدهی‌های پرداخت در محل — تأیید دریافت وجه"""
    if not _guard(cid, uid):
        return
    import permissions as perm
    if not perm.has_any(uid, "fin_view", "fin_approve"):
        return send(cid, "🔒 دسترسی ندارید")

    rows = db_execute("""SELECT t.*, u.first_name, u.last_name, u.mobile,
        e.title ev_title FROM transactions t
        LEFT JOIN users u ON u.bale_user_id=t.bale_user_id
        LEFT JOIN events e ON e.id=t.event_id
        WHERE t.status='onsite' ORDER BY t.id DESC LIMIT 100""",
        fetch="all") or []

    total = sum(int(r.get("amount") or 0) for r in rows)
    lines = ["💰 بدهی‌های پرداخت در محل", "━━━━━━━━━━━━━━",
             f"🧾 {len(rows)} مورد  |  💵 {fmt(total)} {CURRENCY_LABEL}", ""]
    btns = []
    if not rows:
        lines.append("✅ بدهی معوقی نیست")
    for r in rows[:10]:
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
        lines += [
            f"💰 {fmt(r.get('amount'))} {CURRENCY_LABEL} — {nm or '—'}",
            f"   🎉 {str(r.get('ev_title') or '—')[:30]}",
            f"   📱 {r.get('mobile') or '—'}   🔖 {r.get('transaction_id') or '—'}",
            "",
        ]
        btns.append([{"text": f"✅ دریافت شد — {nm or r.get('id')}"[:40],
                      "callback_data": f"payos_{r['id']}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "pay_adv"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_wallet_info(cid, uid):
    if not _guard(cid, uid):
        return
    from config import (PAYMENT_MAX_AMOUNT, PAYMENT_MIN_AMOUNT,
                        PAYMENT_CONFIRM)
    tok = PAYMENT_PROVIDER_TOKEN
    lines = ["🏦 کیف پول بله", "━━━━━━━━━━━━━━", ""]
    if not PAYMENT_ENABLED:
        lines += [
            "🔴 توکن تنظیم نشده",
            "",
            "🔧 در فایل .env بنویسید:",
            "PAYMENT_PROVIDER_TOKEN=توکن_از_botfather",
            "",
            "🧪 برای تست: WALLET-TEST-1111111111111111",
        ]
    else:
        lines += [
            f"🔑 توکن: {tok[:10]}***{tok[-4:]}",
            f"📌 حالت: {'🧪 آزمایشی' if PAYMENT_TEST_MODE else '💰 واقعی'}",
            "",
            "🛡️ محافظت‌ها:",
            f"├── سقف تراکنش: {fmt(PAYMENT_MAX_AMOUNT)} {CURRENCY_LABEL}",
            f"├── حداقل: {fmt(PAYMENT_MIN_AMOUNT)} {CURRENCY_LABEL}",
            f"└── تأیید دومرحله‌ای: {'✅' if PAYMENT_CONFIRM else '❌'}",
        ]
        if not PAYMENT_TEST_MODE:
            lines += ["", "🔴 توکن واقعی — پرداخت‌ها واقعی هستند!"]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🧪 تست پرداخت", "callback_data": "pay_test"}],
        [{"text": "🔙 روش‌های پرداخت", "callback_data": "set_payment"}],
    ]})
