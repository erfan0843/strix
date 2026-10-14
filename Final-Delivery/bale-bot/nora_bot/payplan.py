"""
💠 پرداخت مرحله‌ای — فاز ۱۸-الف

درخواست کاربر:
  «پرداخت اقساط هم اضافه کن به روش های پرداخت، یا پرداخت جلسه ای
   و کل جزییات ممکنش رو در مالی و پرداخت بزار»

سه حالت:
  📅 اقساطی    — مبلغ به N قسط مساوی تقسیم می‌شود
  🎟️ جلسه‌ای   — هر جلسه یک پرداخت (مثل کلاس ۱۲ جلسه‌ای)
  💵 پیش‌پرداخت — درصدی الان، باقی‌مانده بعداً

هر قسط یک تراکنش مستقل است و از همان موتور پرداخت
(کیف پول / کارت / درگاه / در محل) عبور می‌کند.

🔑 نکته معماری:
   جدول payment_plans = «طرح» که ادمین تعریف می‌کند
   جدول payment_schedules = «قسط‌های یک کاربر مشخص»
"""
import time
from datetime import datetime, timedelta

from config import CURRENCY_LABEL, money
from database import db_execute, db_scalar, get_setting, set_setting, log
from auth import (
    set_state, get_state_data, clear_state, log_action, normalize_digits,
    is_admin as _is_admin,
)
from bale_api import send, send_or_edit, kb_cancel, kb_remove, BTN_BACK

STATE_PP_NEW = "pp_new"
STATE_PP_EDIT = "pp_edit"

# ══════════════════════════════════════════════════════════
# انواع طرح پرداخت
# ══════════════════════════════════════════════════════════
PLAN_MODES = {
    "installment": {
        "icon": "📅", "name": "اقساطی",
        "desc": "مبلغ کل به چند قسط مساوی تقسیم می‌شود",
        "hint": "مثال: ۳٬۰۰۰٬۰۰۰ ریال در ۳ قسط ماهانه",
    },
    "sessions": {
        "icon": "🎟️", "name": "جلسه‌ای",
        "desc": "برای هر جلسه جداگانه پرداخت می‌شود",
        "hint": "مثال: کلاس ۱۲ جلسه‌ای، هر جلسه ۲۵۰٬۰۰۰ ریال",
    },
    "prepay": {
        "icon": "💵", "name": "پیش‌پرداخت",
        "desc": "بخشی الان، باقی‌مانده بعداً",
        "hint": "مثال: ۳۰٪ هنگام ثبت‌نام، ۷۰٪ روز برگزاری",
    },
}

# فاصله بین اقساط
INTERVALS = {
    "weekly":   {"name": "هفتگی", "days": 7},
    "biweekly": {"name": "دو هفته یکبار", "days": 14},
    "monthly":  {"name": "ماهانه", "days": 30},
    "custom":   {"name": "دستی (بدون تاریخ)", "days": 0},
}

PLANS_SCHEMA = {
    "owner_id": "INTEGER",
    "title": "TEXT",
    "mode": "TEXT DEFAULT 'installment'",
    "total_amount": "INTEGER DEFAULT 0",
    "parts": "INTEGER DEFAULT 2",          # تعداد قسط/جلسه
    "part_amount": "INTEGER DEFAULT 0",    # مبلغ هر قسط (جلسه‌ای)
    "prepay_percent": "INTEGER DEFAULT 30",
    "interval": "TEXT DEFAULT 'monthly'",
    "grace_days": "INTEGER DEFAULT 3",     # مهلت تأخیر
    "remind_before": "INTEGER DEFAULT 2",  # چند روز قبل یادآوری
    "late_fee": "INTEGER DEFAULT 0",       # جریمه تأخیر (ریال)
    "allow_early": "INTEGER DEFAULT 1",    # تسویه زودهنگام مجاز؟
    "block_on_late": "INTEGER DEFAULT 0",  # با تأخیر، دسترسی قطع شود؟
    "note": "TEXT",
    "is_active": "INTEGER DEFAULT 1",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

SCHEDULES_SCHEMA = {
    "plan_id": "INTEGER",
    "bale_user_id": "INTEGER",
    "event_id": "INTEGER",
    "registration_id": "INTEGER",
    "form_response_id": "INTEGER",
    "part_no": "INTEGER DEFAULT 1",
    "parts_total": "INTEGER DEFAULT 1",
    "amount": "INTEGER DEFAULT 0",
    "due_date": "TEXT",                 # شمسی
    "status": "TEXT DEFAULT 'pending'",  # pending | paid | late | waived
    "transaction_id": "INTEGER",
    "paid_at": "TIMESTAMP",
    "reminded_at": "TIMESTAMP",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}


def init_payplan_tables():
    from database import ensure_table
    ensure_table("payment_plans", PLANS_SCHEMA)
    ensure_table("payment_schedules", SCHEDULES_SCHEMA)
    for q in (
        "CREATE INDEX IF NOT EXISTS idx_sched_user "
        "ON payment_schedules(bale_user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_sched_plan "
        "ON payment_schedules(plan_id)",
    ):
        try:
            db_execute(q)
        except Exception:
            pass
    log("✅ جدول‌های پرداخت مرحله‌ای آماده شد")


def get_plan(pid):
    return db_execute("SELECT * FROM payment_plans WHERE id=?", (pid,),
                      fetch="one")


def fmt(v):
    return money(v, with_unit=False)


# ══════════════════════════════════════════════════════════
# 🧮 محاسبه اقساط
# ══════════════════════════════════════════════════════════
def split_amount(total, parts, mode="installment", prepay_percent=30,
                 part_amount=0):
    """
    مبلغ را به قسط‌ها تقسیم می‌کند.
    خروجی: لیست مبالغ — جمعشان دقیقاً برابر total است.

    🔴 نکته: باقی‌مانده تقسیم به قسط اول اضافه می‌شود تا
       جمع اقساط هرگز با مبلغ کل اختلاف پیدا نکند.
    """
    try:
        total = max(0, int(total or 0))
        parts = max(1, int(parts or 1))
    except (TypeError, ValueError):
        return []

    if mode == "sessions":
        per = max(0, int(part_amount or 0))
        if per <= 0:
            per = total // parts if parts else 0
        return [per] * parts

    if mode == "prepay":
        pct = max(1, min(99, int(prepay_percent or 30)))
        first = (total * pct) // 100
        return [first, total - first]

    # اقساطی مساوی
    base = total // parts
    rest = total - base * parts
    out = [base] * parts
    if out:
        out[0] += rest          # باقی‌مانده به قسط اول
    return out


def _due_dates(parts, interval="monthly", start=None):
    """تاریخ سررسید هر قسط (شمسی)"""
    days = INTERVALS.get(interval, INTERVALS["monthly"])["days"]
    if not days:
        return [None] * parts
    from forms import g2j
    base = start or datetime.now()
    out = []
    for i in range(parts):
        d = base + timedelta(days=days * i)
        y, m, dd = g2j(d.year, d.month, d.day)
        out.append(f"{y}/{m:02d}/{dd:02d}")
    return out


def plan_summary(plan, total=None):
    """📄 متن خلاصه یک طرح برای نمایش"""
    if not plan:
        return "—"
    mode = plan.get("mode") or "installment"
    info = PLAN_MODES.get(mode, PLAN_MODES["installment"])
    total = int(total if total is not None else (plan.get("total_amount") or 0))
    parts = split_amount(total, plan.get("parts"), mode,
                         plan.get("prepay_percent"), plan.get("part_amount"))

    lines = [f"{info['icon']} {info['name']}", ""]
    if mode == "prepay":
        pct = plan.get("prepay_percent") or 30
        lines += [f"💵 پیش‌پرداخت ({pct}٪): {money(parts[0] if parts else 0)}",
                  f"💳 باقی‌مانده: {money(parts[1] if len(parts) > 1 else 0)}"]
    else:
        unit = "جلسه" if mode == "sessions" else "قسط"
        lines.append(f"🔢 تعداد {unit}: {len(parts)}")
        if parts and len(set(parts)) == 1:
            lines.append(f"💰 هر {unit}: {money(parts[0])}")
        else:
            for i, a in enumerate(parts, 1):
                lines.append(f"   {unit} {i}: {money(a)}")
    lines.append(f"🧾 جمع کل: {money(sum(parts))}")

    iv = INTERVALS.get(plan.get("interval") or "monthly")
    if iv and iv["days"]:
        lines.append(f"📆 فاصله: {iv['name']}")
    if plan.get("late_fee"):
        lines.append(f"⏰ جریمه تأخیر: {money(plan['late_fee'])}")
    if plan.get("grace_days"):
        lines.append(f"🕊️ مهلت تأخیر: {plan['grace_days']} روز")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════
# 🚀 شروع پرداخت مرحله‌ای برای یک کاربر
# ══════════════════════════════════════════════════════════
def start_plan(cid, uid, obj, rid, amount, mode="installment"):
    """
    کاربر می‌خواهد با طرح مرحله‌ای پرداخت کند.
    زمان‌بندی ساخته می‌شود و قسط اول بلافاصله دریافت می‌گردد.
    """
    plan = None
    pid = (obj or {}).get("payment_plan_id")
    if pid:
        plan = get_plan(pid)
    if not plan:
        # طرح پیش‌فرض از تنظیمات
        plan = {
            "mode": mode,
            "parts": int(get_setting("pp_default_parts", "3") or 3),
            "prepay_percent": int(get_setting("pp_default_prepay", "30") or 30),
            "interval": get_setting("pp_default_interval", "monthly"),
            "part_amount": 0, "grace_days": 3, "late_fee": 0,
            "id": None,
        }

    parts = split_amount(amount, plan.get("parts"), plan.get("mode") or mode,
                         plan.get("prepay_percent"), plan.get("part_amount"))
    if not parts:
        return None

    dues = _due_dates(len(parts), plan.get("interval") or "monthly")
    frid = (obj or {}).get("_form_response_id")

    # پاک کردن زمان‌بندی قبلی همین کاربر برای همین مقصد (اگر نیمه‌کاره بود)
    try:
        if frid:
            db_execute("DELETE FROM payment_schedules WHERE bale_user_id=? "
                       "AND form_response_id=? AND status='pending'",
                       (uid, frid))
        elif rid:
            db_execute("DELETE FROM payment_schedules WHERE bale_user_id=? "
                       "AND registration_id=? AND status='pending'",
                       (uid, rid))
    except Exception as e:
        log(f"⚠️ پاکسازی زمان‌بندی قبلی: {e}")

    for i, amt in enumerate(parts, 1):
        db_execute("""INSERT INTO payment_schedules
            (plan_id, bale_user_id, event_id, registration_id,
             form_response_id, part_no, parts_total, amount, due_date, status)
            VALUES (?,?,?,?,?,?,?,?,?,'pending')""",
            (plan.get("id"), uid, (obj or {}).get("id"), rid, frid,
             i, len(parts), amt, dues[i - 1]))

    info = PLAN_MODES.get(plan.get("mode") or mode,
                          PLAN_MODES["installment"])
    unit = "جلسه" if (plan.get("mode") or mode) == "sessions" else "قسط"

    lines = [f"{info['icon']} پرداخت {info['name']}", "━━━━━━━━━━━━━━", "",
             f"💰 مبلغ کل: {money(sum(parts))}", ""]
    for i, amt in enumerate(parts, 1):
        d = f" — سررسید {dues[i-1]}" if dues[i - 1] else ""
        mark = "👈" if i == 1 else "  "
        lines.append(f"{mark} {unit} {i}: {money(amt)}{d}")
    lines += ["", f"✅ حالا فقط {unit} اول را پرداخت می‌کنید.",
              "🔔 برای بقیه، به‌موقع یادآوری می‌فرستیم 💚"]

    send(cid, "\n".join(lines))
    log_action(uid, "payplan_started",
               {"parts": len(parts), "total": sum(parts)})

    return pay_part(cid, uid, obj, rid, part_no=1)


def _my_schedules(uid, rid=None, frid=None, status=None):
    w = ["bale_user_id=?"]
    p = [uid]
    if frid:
        w.append("form_response_id=?")
        p.append(frid)
    elif rid:
        w.append("registration_id=?")
        p.append(rid)
    if status:
        w.append("status=?")
        p.append(status)
    return db_execute(
        f"SELECT * FROM payment_schedules WHERE {' AND '.join(w)} "
        f"ORDER BY part_no", tuple(p), fetch="all") or []


def pay_part(cid, uid, obj, rid, part_no=None, sched_id=None):
    """پرداخت یک قسط مشخص — از موتور پرداخت عادی عبور می‌کند"""
    import payments as pay

    if sched_id:
        s = db_execute("SELECT * FROM payment_schedules WHERE id=?",
                       (sched_id,), fetch="one")
    else:
        frid = (obj or {}).get("_form_response_id")
        rows = _my_schedules(uid, rid, frid, status="pending")
        s = None
        for r in rows:
            if part_no is None or int(r.get("part_no") or 0) == int(part_no):
                s = r
                break
    if not s:
        return None
    if s.get("bale_user_id") != uid and not _is_admin(uid):
        return send(cid, "❌ دسترسی ندارید")
    if s.get("status") == "paid":
        return send(cid, "ℹ️ این قسط قبلاً پرداخت شده است")

    # مقصد را دقیقاً مثل پرداخت عادی می‌سازیم ولی با روش پایه
    sub = dict(obj or {})
    sub["payment_method"] = _base_method(obj)
    sub["_plan_part"] = s["id"]
    return pay.route_payment(cid, uid, sub, rid, int(s.get("amount") or 0))


def _base_method(obj):
    """
    روش واقعی که قسط با آن گرفته می‌شود.
    ادمین می‌تواند در تنظیمات مشخص کند؛ پیش‌فرض: بهترین روش موجود.
    """
    import payments as pay
    pref = (obj or {}).get("plan_base_method") \
        or get_setting("pp_base_method", "") or None
    return pay.best_available_method(pref) or "card"


def mark_part_paid(sched_id, txid=None):
    """یک قسط پرداخت شد"""
    db_execute("""UPDATE payment_schedules SET status='paid',
        transaction_id=?, paid_at=CURRENT_TIMESTAMP WHERE id=?""",
        (txid, sched_id))


def remaining(uid, rid=None, frid=None):
    """(تعداد باقی‌مانده، مبلغ باقی‌مانده)"""
    rows = _my_schedules(uid, rid, frid)
    left = [r for r in rows if r.get("status") in ("pending", "late")]
    return len(left), sum(int(r.get("amount") or 0) for r in left)


def all_paid(uid, rid=None, frid=None):
    """آیا همه اقساط تسویه شده؟"""
    n, _ = remaining(uid, rid, frid)
    return n == 0


# ══════════════════════════════════════════════════════════
# 👤 نمای کاربر — اقساط من
# ══════════════════════════════════════════════════════════
def show_my_installments(cid, uid):
    """💠 اقساط و پرداخت‌های مرحله‌ای من"""
    rows = db_execute("""SELECT s.*, e.title ev_title, f.title form_title
        FROM payment_schedules s
        LEFT JOIN events e ON e.id=s.event_id
        LEFT JOIN form_responses fr ON fr.id=s.form_response_id
        LEFT JOIN forms f ON f.id=fr.form_id
        WHERE s.bale_user_id=? ORDER BY s.status='paid', s.due_date
        LIMIT 60""", (uid,), fetch="all") or []

    if not rows:
        return send_or_edit(cid, (
            "💠 پرداخت‌های مرحله‌ای\n━━━━━━━━━━━━━━\n\n"
            "🌱 فعلاً قسطی ندارید.\n\n"
            "هر وقت در دوره‌ای با پرداخت اقساطی ثبت‌نام کنید،\n"
            "قسط‌هایتان اینجا نمایش داده می‌شود."
        ), {"inline_keyboard": [
            [{"text": "🔙 منوی اصلی", "callback_data": "back_main"}]]})

    paid = [r for r in rows if r.get("status") == "paid"]
    left = [r for r in rows if r.get("status") != "paid"]
    total_left = sum(int(r.get("amount") or 0) for r in left)

    lines = ["💠 پرداخت‌های مرحله‌ای شما", "━━━━━━━━━━━━━━", "",
             f"✅ پرداخت‌شده: {len(paid)}   ⏳ باقی‌مانده: {len(left)}"]
    if total_left:
        lines.append(f"💰 مانده: {money(total_left)}")
    lines.append("")

    btns = []
    for r in left[:10]:
        nm = r.get("ev_title") or r.get("form_title") or "پرداخت"
        due = f" — {r['due_date']}" if r.get("due_date") else ""
        icon = "⚠️" if r.get("status") == "late" else "⏳"
        lines.append(f"{icon} {nm} — قسط {r['part_no']}/{r['parts_total']}"
                     f" — {money(r['amount'])}{due}")
        btns.append([{"text": f"💳 پرداخت قسط {r['part_no']} "
                              f"({fmt(r['amount'])})"[:34],
                      "callback_data": f"ppay_{r['id']}"}])

    if paid:
        lines += ["", "✅ پرداخت‌شده‌ها:"]
        for r in paid[:6]:
            nm = r.get("ev_title") or r.get("form_title") or "پرداخت"
            lines.append(f"   ✔️ {nm} — قسط {r['part_no']} — "
                         f"{money(r['amount'])}")

    btns.append([{"text": "🔙 منوی اصلی", "callback_data": "back_main"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def pay_one(cid, uid, sched_id):
    """کاربر روی «پرداخت قسط» زد"""
    s = db_execute("SELECT * FROM payment_schedules WHERE id=?",
                   (sched_id,), fetch="one")
    if not s:
        return send(cid, "❌ یافت نشد")
    if s.get("bale_user_id") != uid:
        return send(cid, "❌ دسترسی ندارید")
    if s.get("status") == "paid":
        return send(cid, "ℹ️ این قسط قبلاً پرداخت شده 💚")

    obj = None
    if s.get("event_id"):
        import events as _ev
        obj = _ev.get_event(s["event_id"])
    if not obj and s.get("form_response_id"):
        fr = db_execute("SELECT * FROM form_responses WHERE id=?",
                        (s["form_response_id"],), fetch="one")
        if fr:
            from forms import get_form
            f = get_form(fr["form_id"]) or {}
            obj = dict(f)
            obj["_form_response_id"] = s["form_response_id"]
    if not obj:
        return send(cid, "❌ مورد مرتبط یافت نشد")

    return pay_part(cid, uid, obj, s.get("registration_id"),
                    sched_id=s["id"])


# ══════════════════════════════════════════════════════════
# 🔔 یادآوری اقساط (از حلقه اصلی صدا زده می‌شود)
# ══════════════════════════════════════════════════════════
def check_due_reminders():
    """قسط‌هایی که سررسیدشان نزدیک یا گذشته است"""
    try:
        from forms import jnow
        today = jnow()[:10]
    except Exception:
        return 0

    n = 0
    rows = db_execute("""SELECT * FROM payment_schedules
        WHERE status='pending' AND due_date IS NOT NULL AND due_date<=?
        AND (reminded_at IS NULL
             OR reminded_at < datetime('now','-1 day'))
        LIMIT 50""", (today,), fetch="all") or []

    for r in rows:
        try:
            send(r["bale_user_id"], (
                f"🔔 یادآوری مهربانه\n━━━━━━━━━━━━━━\n\n"
                f"قسط {r['part_no']} از {r['parts_total']} شما\n"
                f"💰 {money(r['amount'])}\n"
                f"📆 سررسید: {r.get('due_date')}\n\n"
                f"هر وقت راحت بودید پرداخت کنید 💚"
            ), {"inline_keyboard": [
                [{"text": "💳 پرداخت همین حالا",
                  "callback_data": f"ppay_{r['id']}"}]]})
            db_execute("UPDATE payment_schedules SET "
                       "reminded_at=CURRENT_TIMESTAMP WHERE id=?", (r["id"],))
            n += 1
        except Exception as e:
            log(f"⚠️ یادآوری قسط: {e}")
    return n


# ══════════════════════════════════════════════════════════
# ⚙️ پنل ادمین — تنظیمات پرداخت مرحله‌ای
# ══════════════════════════════════════════════════════════
def _guard(cid, uid):
    if not _is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    import permissions as perm
    if not perm.has_perm(uid, "fin_settings"):
        send(cid, "🔒 این بخش فقط برای سوپرادمین است")
        return False
    return True


def show_panel(cid, uid):
    """💠 پنل پرداخت مرحله‌ای"""
    if not _guard(cid, uid):
        return

    n_plans = db_scalar("SELECT COUNT(*) FROM payment_plans "
                        "WHERE is_active=1") or 0
    n_open = db_scalar("SELECT COUNT(*) FROM payment_schedules "
                       "WHERE status IN ('pending','late')") or 0
    amt_open = db_scalar("SELECT COALESCE(SUM(amount),0) FROM "
                         "payment_schedules WHERE status IN "
                         "('pending','late')") or 0
    n_paid = db_scalar("SELECT COUNT(*) FROM payment_schedules "
                       "WHERE status='paid'") or 0
    n_late = db_scalar("SELECT COUNT(*) FROM payment_schedules "
                       "WHERE status='late'") or 0

    lines = [
        "💠 پرداخت مرحله‌ای", "━━━━━━━━━━━━━━", "",
        "اقساطی · جلسه‌ای · پیش‌پرداخت", "",
        f"📋 طرح‌های فعال: {n_plans}",
        f"⏳ اقساط باز: {n_open}  ({money(amt_open)})",
        f"✅ پرداخت‌شده: {n_paid}",
    ]
    if n_late:
        lines.append(f"⚠️ معوق: {n_late}")

    lines += ["", "⚙️ پیش‌فرض‌ها:",
              f"   🔢 تعداد قسط: {get_setting('pp_default_parts', '3')}",
              f"   💵 پیش‌پرداخت: {get_setting('pp_default_prepay', '30')}٪",
              f"   📆 فاصله: "
              f"{INTERVALS.get(get_setting('pp_default_interval','monthly'), {}).get('name','ماهانه')}"]

    btns = [
        [{"text": "📋 طرح‌های پرداخت", "callback_data": "pp_plans"}],
        [{"text": "➕ طرح جدید", "callback_data": "pp_new"}],
        [{"text": "⏳ اقساط باز", "callback_data": "pp_open"}],
        [{"text": f"🔢 تعداد قسط پیش‌فرض "
                  f"({get_setting('pp_default_parts', '3')})",
          "callback_data": "ppset_parts"}],
        [{"text": f"💵 درصد پیش‌پرداخت "
                  f"({get_setting('pp_default_prepay', '30')}٪)",
          "callback_data": "ppset_prepay"}],
        [{"text": "📆 فاصله اقساط", "callback_data": "ppset_interval"}],
        [{"text": "🔙 پرداخت و مالی", "callback_data": "set_payment"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_plans(cid, uid, page=0):
    if not _guard(cid, uid):
        return
    rows = db_execute("SELECT * FROM payment_plans ORDER BY is_active DESC, "
                      "id DESC LIMIT 40", fetch="all") or []
    lines = ["📋 طرح‌های پرداخت", "━━━━━━━━━━━━━━", ""]
    btns = []
    if not rows:
        lines += ["🌱 هنوز طرحی نساخته‌اید.", "",
                  "با «➕ طرح جدید» اولین طرح را بسازید."]
    for r in rows:
        info = PLAN_MODES.get(r.get("mode") or "installment",
                              PLAN_MODES["installment"])
        st = "🟢" if r.get("is_active") else "🔴"
        lines.append(f"{st} {info['icon']} {r.get('title') or '—'} — "
                     f"{r.get('parts')} قسمت")
        btns.append([{"text": f"{st} {r.get('title') or '—'}"[:32],
                      "callback_data": f"ppv_{r['id']}"}])
    btns.append([{"text": "➕ طرح جدید", "callback_data": "pp_new"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "pp_panel"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_plan(cid, uid, pid):
    if not _guard(cid, uid):
        return
    p = get_plan(pid)
    if not p:
        return send(cid, "❌ یافت نشد")
    used = db_scalar("SELECT COUNT(DISTINCT bale_user_id) FROM "
                     "payment_schedules WHERE plan_id=?", (pid,)) or 0

    lines = [f"📋 {p.get('title') or '—'}", "━━━━━━━━━━━━━━", "",
             plan_summary(p), "",
             f"👥 استفاده‌کننده: {used}",
             f"📌 وضعیت: {'🟢 فعال' if p.get('is_active') else '🔴 غیرفعال'}"]
    if p.get("note"):
        lines += ["", f"📄 {p['note']}"]

    btns = [
        [{"text": "✏️ عنوان", "callback_data": f"ppe_title_{pid}"},
         {"text": "🔢 تعداد", "callback_data": f"ppe_parts_{pid}"}],
        [{"text": "💰 مبلغ کل", "callback_data": f"ppe_total_amount_{pid}"},
         {"text": "🎟️ مبلغ هر جلسه",
          "callback_data": f"ppe_part_amount_{pid}"}],
        [{"text": "💵 درصد پیش‌پرداخت",
          "callback_data": f"ppe_prepay_percent_{pid}"},
         {"text": "⏰ جریمه تأخیر", "callback_data": f"ppe_late_fee_{pid}"}],
        [{"text": "🕊️ مهلت تأخیر", "callback_data": f"ppe_grace_days_{pid}"},
         {"text": "🔔 یادآوری قبل",
          "callback_data": f"ppe_remind_before_{pid}"}],
        [{"text": "📆 فاصله اقساط", "callback_data": f"ppiv_{pid}"}],
        [{"text": "🔄 نوع طرح", "callback_data": f"ppm_{pid}"}],
        [{"text": ("🟢 فعال" if p.get("is_active") else "🔴 غیرفعال"),
          "callback_data": f"pptog_{pid}"}],
        [{"text": "🗑️ حذف", "callback_data": f"ppdel_{pid}"}],
        [{"text": "🔙 طرح‌ها", "callback_data": "pp_plans"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_new(cid, uid):
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_PP_NEW, {"step": 0}, merge=False)
    send(cid, (
        "➕ طرح پرداخت جدید\n━━━━━━━━━━━━━━\n\n"
        "یک نام برای این طرح بنویسید:\n\n"
        "مثال: شهریه دوره فن بیان (۳ قسط)"
    ), kb_cancel())


def handle_new(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    if text in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_panel(cid, uid)
    if len(text) < 2:
        return send(cid, "⚠️ نام حداقل ۲ حرف باشد:", kb_cancel())

    pid = db_execute("""INSERT INTO payment_plans
        (owner_id, title, mode, parts, prepay_percent, interval)
        VALUES (?,?,?,?,?,?)""",
        (uid, text[:80], "installment",
         int(get_setting("pp_default_parts", "3") or 3),
         int(get_setting("pp_default_prepay", "30") or 30),
         get_setting("pp_default_interval", "monthly")))
    clear_state(uid)
    send(cid, f"✅ طرح «{text[:40]}» ساخته شد", kb_remove())
    log_action(uid, "payplan_created", {"pid": pid})
    return show_plan(cid, uid, pid)


PP_FIELDS = {
    "title": ("✏️ عنوان طرح", "نام جدید را بنویسید:"),
    "parts": ("🔢 تعداد قسط/جلسه", "چند قسمت؟\n\nمثال: 3"),
    "total_amount": ("💰 مبلغ کل", f"مبلغ کل به {CURRENCY_LABEL}:"),
    "part_amount": ("🎟️ مبلغ هر جلسه",
                    f"مبلغ هر جلسه به {CURRENCY_LABEL}:\n\n۰ = خودکار"),
    "prepay_percent": ("💵 درصد پیش‌پرداخت", "چند درصد؟\n\nمثال: 30"),
    "late_fee": ("⏰ جریمه تأخیر",
                 f"جریمه به {CURRENCY_LABEL}:\n\n۰ = بدون جریمه"),
    "grace_days": ("🕊️ مهلت تأخیر", "چند روز مهلت؟\n\nمثال: 3"),
    "remind_before": ("🔔 یادآوری قبل", "چند روز قبل یادآوری شود؟"),
}


def start_edit(cid, uid, field, pid):
    if not _guard(cid, uid):
        return
    if field not in PP_FIELDS or not get_plan(pid):
        return send(cid, "❌ نامعتبر")
    title, prompt = PP_FIELDS[field]
    cur = (get_plan(pid) or {}).get(field)
    set_state(uid, STATE_PP_EDIT, {"pid": pid, "field": field}, merge=False)
    send(cid, f"{title}\n━━━━━━━━━━━━━━\n\n📄 فعلی: {cur}\n\n{prompt}",
         kb_cancel())


def handle_edit(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid)
    pid, field = d.get("pid"), d.get("field")

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_plan(cid, uid, pid)
    if field not in PP_FIELDS:
        clear_state(uid)
        return send(cid, "❌ نامعتبر", kb_remove())

    if field == "title":
        if len(raw) < 2:
            return send(cid, "⚠️ حداقل ۲ حرف:", kb_cancel())
        val = raw[:80]
    else:
        digits = "".join(ch for ch in normalize_digits(raw) if ch.isdigit())
        if not digits:
            return send(cid, "⚠️ فقط عدد بفرستید:", kb_cancel())
        val = int(digits)
        if field == "parts":
            val = max(1, min(60, val))
        elif field == "prepay_percent":
            val = max(1, min(99, val))
        elif field in ("grace_days", "remind_before"):
            val = max(0, min(60, val))

    db_execute(f"UPDATE payment_plans SET {field}=? WHERE id=?", (val, pid))
    clear_state(uid)
    send(cid, "✅ ذخیره شد", kb_remove())
    return show_plan(cid, uid, pid)


def pick_mode(cid, uid, pid, mode=None):
    if not _guard(cid, uid):
        return
    if mode:
        if mode not in PLAN_MODES:
            return send(cid, "❌ نامعتبر")
        db_execute("UPDATE payment_plans SET mode=? WHERE id=?", (mode, pid))
        return show_plan(cid, uid, pid)
    btns = [[{"text": f"{v['icon']} {v['name']} — {v['desc']}"[:44],
              "callback_data": f"ppm_{pid}_{k}"}]
            for k, v in PLAN_MODES.items()]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"ppv_{pid}"}])
    send_or_edit(cid, "🔄 نوع طرح پرداخت را انتخاب کنید:",
                 {"inline_keyboard": btns})


def pick_interval(cid, uid, pid, iv=None):
    if not _guard(cid, uid):
        return
    if iv:
        if iv not in INTERVALS:
            return send(cid, "❌ نامعتبر")
        db_execute("UPDATE payment_plans SET interval=? WHERE id=?", (iv, pid))
        return show_plan(cid, uid, pid)
    btns = [[{"text": v["name"], "callback_data": f"ppiv_{pid}_{k}"}]
            for k, v in INTERVALS.items()]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"ppv_{pid}"}])
    send_or_edit(cid, "📆 فاصله بین اقساط:", {"inline_keyboard": btns})


def toggle_plan(cid, uid, pid):
    if not _guard(cid, uid):
        return
    p = get_plan(pid)
    if not p:
        return send(cid, "❌ یافت نشد")
    db_execute("UPDATE payment_plans SET is_active=? WHERE id=?",
               (0 if p.get("is_active") else 1, pid))
    return show_plan(cid, uid, pid)


def delete_plan(cid, uid, pid):
    if not _guard(cid, uid):
        return
    used = db_scalar("SELECT COUNT(*) FROM payment_schedules WHERE plan_id=?",
                     (pid,)) or 0
    if used:
        db_execute("UPDATE payment_plans SET is_active=0 WHERE id=?", (pid,))
        send(cid, f"🚫 طرح غیرفعال شد (چون {used} قسط به آن وصل است)")
    else:
        db_execute("DELETE FROM payment_plans WHERE id=?", (pid,))
        send(cid, "🗑️ طرح حذف شد")
    return show_plans(cid, uid)


def show_open(cid, uid, page=0):
    """⏳ اقساط باز همه کاربران"""
    if not _guard(cid, uid):
        return
    rows = db_execute("""SELECT s.*, u.first_name, u.last_name, u.mobile,
        e.title ev_title FROM payment_schedules s
        LEFT JOIN users u ON u.bale_user_id=s.bale_user_id
        LEFT JOIN events e ON e.id=s.event_id
        WHERE s.status IN ('pending','late')
        ORDER BY s.due_date LIMIT 40""", fetch="all") or []

    total = sum(int(r.get("amount") or 0) for r in rows)
    lines = ["⏳ اقساط باز", "━━━━━━━━━━━━━━", "",
             f"🧾 {len(rows)} قسط  |  💰 {money(total)}", ""]
    if not rows:
        lines.append("🎉 همه اقساط تسویه شده‌اند!")
    btns = []
    for r in rows[:20]:
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
        due = f" — {r['due_date']}" if r.get("due_date") else ""
        lines.append(f"• {nm or r['bale_user_id']} — "
                     f"{r.get('ev_title') or 'فرم'} — "
                     f"قسط {r['part_no']}/{r['parts_total']} — "
                     f"{money(r['amount'])}{due}")
        btns.append([{"text": f"✅ تسویه دستی #{r['id']}"[:30],
                      "callback_data": f"ppok_{r['id']}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "pp_panel"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def admin_mark_paid(cid, uid, sched_id):
    """ادمین دستی یک قسط را تسویه می‌کند (مثلاً نقدی گرفته)"""
    if not _guard(cid, uid):
        return
    s = db_execute("SELECT * FROM payment_schedules WHERE id=?",
                   (sched_id,), fetch="one")
    if not s:
        return send(cid, "❌ یافت نشد")
    mark_part_paid(sched_id)
    log_action(uid, "payplan_manual_paid", {"sched": sched_id})
    send(cid, f"✅ قسط {s['part_no']} تسویه شد")
    try:
        send(s["bale_user_id"], (
            f"✅ قسط {s['part_no']} از {s['parts_total']} شما ثبت شد\n\n"
            f"💰 {money(s['amount'])}\n\nسپاس از همراهی‌تان 💚"))
    except Exception:
        pass
    return show_open(cid, uid)


def start_num_setting(cid, uid, key):
    if not _guard(cid, uid):
        return
    titles = {
        "parts": ("🔢 تعداد قسط پیش‌فرض", "pp_default_parts", "مثال: 3"),
        "prepay": ("💵 درصد پیش‌پرداخت", "pp_default_prepay", "مثال: 30"),
    }
    if key not in titles:
        return send(cid, "❌ نامعتبر")
    t, sk, hint = titles[key]
    set_state(uid, STATE_PP_EDIT, {"setting": sk}, merge=False)
    send(cid, f"{t}\n━━━━━━━━━━━━━━\n\n"
              f"📄 فعلی: {get_setting(sk, '')}\n\n{hint}", kb_cancel())


def handle_num_setting(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid)
    sk = d.get("setting")
    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_panel(cid, uid)
    digits = "".join(ch for ch in normalize_digits(raw) if ch.isdigit())
    if not digits:
        return send(cid, "⚠️ فقط عدد:", kb_cancel())
    v = int(digits)
    if sk == "pp_default_parts":
        v = max(1, min(60, v))
    elif sk == "pp_default_prepay":
        v = max(1, min(99, v))
    set_setting(sk, str(v), "پرداخت مرحله‌ای", "payment", uid)
    clear_state(uid)
    send(cid, f"✅ ذخیره شد: {v}", kb_remove())
    return show_panel(cid, uid)


def pick_default_interval(cid, uid, iv=None):
    if not _guard(cid, uid):
        return
    if iv:
        if iv not in INTERVALS:
            return send(cid, "❌ نامعتبر")
        set_setting("pp_default_interval", iv, "فاصله اقساط", "payment", uid)
        return show_panel(cid, uid)
    btns = [[{"text": v["name"], "callback_data": f"ppset_iv_{k}"}]
            for k, v in INTERVALS.items()]
    btns.append([{"text": "🔙 بازگشت", "callback_data": "pp_panel"}])
    send_or_edit(cid, "📆 فاصله پیش‌فرض بین اقساط:",
                 {"inline_keyboard": btns})
