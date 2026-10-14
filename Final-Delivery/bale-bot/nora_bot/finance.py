"""
💰 مالی و تراکنش‌ها — فاز ۱۲

گزارش مالی کامل و دقیق طبق فایل معماری:
  • داشبورد مالی با مقایسه دوره قبل
  • تراکنش‌ها با فیلتر و جستجو
  • درآمد به تفکیک رویداد / فرم / روش پرداخت
  • بدهی‌ها و پرداخت‌های ناتمام
  • خروجی Excel چند شیتی

⚠️ همه مبالغ ریال‌اند — ورودی، ذخیره، نمایش و درگاه.
"""
from datetime import datetime

from config import CURRENCY_LABEL, FILES_DIR, money
from database import db_execute, db_scalar, log
from bale_api import send, send_or_edit, send_document
import permissions as perm
import jalali as _jd

TX_PER_PAGE = 8

TX_STATUS = {
    "paid":      {"icon": "✅", "name": "پرداخت‌شده"},
    "confirmed": {"icon": "✅", "name": "تأییدشده"},
    "success":   {"icon": "✅", "name": "موفق"},
    "pending":   {"icon": "⏳", "name": "در انتظار"},
    "failed":    {"icon": "❌", "name": "ناموفق"},
    "refunded":  {"icon": "💸", "name": "بازپرداخت‌شده"},
    "cancelled": {"icon": "⛔", "name": "لغوشده"},
}

PAID_STATES = ("paid", "confirmed", "success")


def _st(s):
    return TX_STATUS.get(s, {"icon": "▫️", "name": s or "نامشخص"})


def _sum(where="", params=()):
    """جمع مبالغ پرداخت‌شده"""
    q = ("SELECT COALESCE(SUM(amount),0) FROM transactions "
         f"WHERE status IN {PAID_STATES}")
    if where:
        q += f" AND {where}"
    return db_scalar(q, params)


def _count(where="", params=()):
    q = "SELECT COUNT(*) FROM transactions"
    if where:
        q += f" WHERE {where}"
    return db_scalar(q, params)


def _pct(now, before):
    """درصد تغییر نسبت به دوره قبل"""
    if not before:
        return "🆕 جدید" if now else "—"
    d = (now - before) * 100.0 / before
    if abs(d) < 0.5:
        return "➖ بدون تغییر"
    return f"{'▲' if d > 0 else '▼'} {abs(d):.1f}%"


# ══════════════════════════════════════════════════════════
# 🧮 موتور تفکیک درآمد — فاز ۳۰
#
# 🎯 «درآمد کارمزد جدا مشخص نشده، درآمدها را همه تفکیک و
#     کامل و با جزئیات بیار»
#
# 🔴 مشکل نسخهٔ قبل: فقط SUM(amount) نشان داده می‌شد.
#    ولی amount = مبلغ پایه + کارمزد. یعنی:
#      • معلوم نبود چقدرش کارمزد است
#      • معلوم نبود چقدرش سهم واقعی رویداد/فرم است
#      • امتیاز مصرف‌شده اصلاً دیده نمی‌شد
#      • بازپرداخت از درآمد کم نمی‌شد → عدد متورم
# ══════════════════════════════════════════════════════════

# 🏷️ منابع درآمد — هرکدام مستقل شمرده می‌شود
SOURCES = {
    "event":   {"icon": "🎉", "name": "رویدادها",
                "where": "event_id IS NOT NULL AND event_id>0"},
    "form":    {"icon": "📝", "name": "فرم‌ها",
                "where": "(form_id IS NOT NULL AND form_id>0) OR "
                         "(form_response_id IS NOT NULL AND "
                         "form_response_id>0)"},
    "plan":    {"icon": "📅", "name": "اقساط و جلسات",
                "where": "plan_id IS NOT NULL AND plan_id>0"},
    "other":   {"icon": "📦", "name": "سایر",
                "where": "(event_id IS NULL OR event_id=0) AND "
                         "(form_id IS NULL OR form_id=0) AND "
                         "(form_response_id IS NULL OR form_response_id=0) "
                         "AND (plan_id IS NULL OR plan_id=0)"},
}

# ⏱️ بازه‌های زمانی استاندارد
PERIODS = {
    "today": ("امروز", "date(created_at)=date('now')",
              "date(created_at)=date('now','-1 day')"),
    "week":  ("۷ روز اخیر", "created_at >= datetime('now','-7 days')",
              "created_at >= datetime('now','-14 days') AND "
              "created_at < datetime('now','-7 days')"),
    "month": ("۳۰ روز اخیر", "created_at >= datetime('now','-30 days')",
              "created_at >= datetime('now','-60 days') AND "
              "created_at < datetime('now','-30 days')"),
    "all":   ("از ابتدا", "", ""),
}


def _agg(where="", params=()):
    """
    📊 تجمیع کامل یک بازه — همهٔ اعداد در یک کوئری.

    برمی‌گرداند:
      gross  ناخالص (هرچه کاربر پرداخت کرده)
      fee    کارمزد (سهم ما از تراکنش)
      base   خالص پایه (سهم واقعی رویداد/فرم)
      points ارزش ریالی امتیاز مصرف‌شده
      n      تعداد تراکنش موفق
    """
    w = f"status IN {PAID_STATES}"
    if where:
        w += f" AND ({where})"
    row = db_execute(
        "SELECT COALESCE(SUM(amount),0) gross, "
        "COALESCE(SUM(fee_amount),0) fee, "
        "COALESCE(SUM(CASE WHEN base_amount>0 THEN base_amount "
        "         ELSE amount-COALESCE(fee_amount,0) END),0) base, "
        "COALESCE(SUM(points_used),0) points, "
        "COUNT(*) n "
        f"FROM transactions WHERE {w}", params, fetch="one") or {}
    return {
        "gross": int(row.get("gross") or 0),
        "fee": int(row.get("fee") or 0),
        "base": int(row.get("base") or 0),
        "points": int(row.get("points") or 0),
        "n": int(row.get("n") or 0),
    }


def _refunded(where="", params=()):
    """💸 مبلغ بازپرداخت‌شده — باید از درآمد کم شود"""
    w = "status='refunded'"
    if where:
        w += f" AND ({where})"
    return int(db_scalar("SELECT COALESCE(SUM(amount),0) "
                         f"FROM transactions WHERE {w}", params) or 0)


def _by_source():
    """📊 تفکیک درآمد بر اساس منبع (رویداد / فرم / اقساط / سایر)"""
    out = []
    for key, meta in SOURCES.items():
        a = _agg(meta["where"])
        if a["n"]:
            a.update(key=key, icon=meta["icon"], name=meta["name"])
            out.append(a)
    return sorted(out, key=lambda x: -x["gross"])


def _by_method():
    """💳 تفکیک درآمد بر اساس روش پرداخت"""
    rows = db_execute(
        "SELECT COALESCE(NULLIF(method,''),'نامشخص') m, "
        "COALESCE(SUM(amount),0) gross, "
        "COALESCE(SUM(fee_amount),0) fee, "
        "COUNT(*) n FROM transactions "
        f"WHERE status IN {PAID_STATES} "
        "GROUP BY m ORDER BY gross DESC", fetch="all") or []
    try:
        from payments import PAYMENT_METHODS as PM
    except Exception:
        PM = {}
    out = []
    for r in rows:
        m = r.get("m") or "نامشخص"
        meta = PM.get(m, {})
        out.append({
            "key": m,
            "icon": meta.get("icon", "▫️"),
            "name": meta.get("name", m),
            "gross": int(r.get("gross") or 0),
            "fee": int(r.get("fee") or 0),
            "n": int(r.get("n") or 0),
        })
    return out


def _fee_detail():
    """
    💳 ریز کارمزد به تفکیک روش — «درآمد کارمزد» ما.

    این همان چیزی است که در نسخهٔ قبل اصلاً دیده نمی‌شد.
    """
    rows = db_execute(
        "SELECT COALESCE(NULLIF(method,''),'نامشخص') m, "
        "COALESCE(SUM(fee_amount),0) fee, "
        "COUNT(*) n FROM transactions "
        f"WHERE status IN {PAID_STATES} AND COALESCE(fee_amount,0)>0 "
        "GROUP BY m ORDER BY fee DESC", fetch="all") or []
    try:
        from payments import PAYMENT_METHODS as PM, fee_percent, fee_fixed
    except Exception:
        PM, fee_percent, fee_fixed = {}, None, None
    out = []
    for r in rows:
        m = r.get("m") or "نامشخص"
        meta = PM.get(m, {})
        d = {"key": m, "icon": meta.get("icon", "▫️"),
             "name": meta.get("name", m),
             "fee": int(r.get("fee") or 0),
             "n": int(r.get("n") or 0), "pct": None, "fix": None}
        if fee_percent:
            try:
                d["pct"] = fee_percent(m)
                d["fix"] = fee_fixed(m)
            except Exception:
                pass
        out.append(d)
    return out


def _infra_split():
    """
    🧱 جدا کردن «هزینه زیرساخت» از درآمد واقعی.

    مبالغ زیر سقف تعیین‌شده، بهای برنامه نیستند — هزینهٔ
    درگاه و پشتیبانی‌اند. باید جدا شمرده شوند.
    """
    try:
        import infra_fee
        if not infra_fee.enabled():
            return None
        cap = infra_fee.threshold()
    except Exception:
        return None
    if not cap or cap <= 0:
        return None
    low = _agg(f"amount<={int(cap)}")
    high = _agg(f"amount>{int(cap)}")
    try:
        title = infra_fee.title()
    except Exception:
        title = "هزینه زیرساخت و خدمات"
    return {"cap": int(cap), "title": title, "low": low, "high": high}


# ==================== داشبورد مالی ====================
def show_dashboard(cid, uid):
    """💰 داشبورد مالی — آمار کامل با مقایسه دوره قبل"""
    if not perm.require(cid, uid, "fin_view", send):
        return

    total = _sum()
    n_paid = _count(f"status IN {PAID_STATES}")
    n_pending = _count("status='pending'")
    amt_pending = db_scalar("SELECT COALESCE(SUM(amount),0) FROM transactions "
                            "WHERE status='pending'")
    n_failed = _count("status='failed'")
    n_refund = _count("status='refunded'")
    amt_refund = db_scalar("SELECT COALESCE(SUM(amount),0) FROM transactions "
                           "WHERE status='refunded'")

    today = _sum("date(created_at)=date('now')")
    yday = _sum("date(created_at)=date('now','-1 day')")
    week = _sum("created_at >= datetime('now','-7 days')")
    pweek = _sum("created_at >= datetime('now','-14 days') "
                 "AND created_at < datetime('now','-7 days')")
    month = _sum("created_at >= datetime('now','-30 days')")
    pmonth = _sum("created_at >= datetime('now','-60 days') "
                  "AND created_at < datetime('now','-30 days')")

    avg = int(total / n_paid) if n_paid else 0
    n_all = _count()
    rate = (n_paid * 100.0 / n_all) if n_all else 0

    # 🧮 تفکیک کامل — فاز ۳۰
    a = _agg()
    net = a["gross"] - amt_refund          # درآمد واقعی بعد از بازپرداخت
    srcs = _by_source()

    lines = [
        "💰 داشبورد مالی", "━━━━━━━━━━━━━━", "",
        "💵 خلاصهٔ درآمد:", "",
        f"   ناخالص کل        {money(a['gross'])}",
    ]
    if amt_refund:
        lines.append(f"   بازپرداخت        −{money(amt_refund)}")
        lines.append("   ─────────────────────")
        lines.append(f"   💰 درآمد خالص     {money(net)}")
    lines += ["", "🔍 این مبلغ از چه تشکیل شده:", ""]

    # سهم پایه در برابر کارمزد
    if a["fee"]:
        share = a["fee"] * 100.0 / a["gross"] if a["gross"] else 0
        lines += [
            f"   📦 بهای خدمات     {money(a['base'])}",
            f"   💳 کارمزد ما      {money(a['fee'])}  ({share:.1f}٪)",
        ]
    else:
        lines += [f"   📦 بهای خدمات     {money(a['base'])}",
                  "   💳 کارمزد ما      — (فعال نیست)"]
    if a["points"]:
        lines.append(f"   🏆 امتیاز مصرفی   {money(a['points'])}")

    # 🧱 هزینهٔ زیرساخت جدا شمرده شود
    inf = _infra_split()
    if inf and inf["low"]["n"]:
        lines += ["", f"🧱 {inf['title']}:",
                  f"   زیر {money(inf['cap'])} → "
                  f"{money(inf['low']['gross'])} "
                  f"({inf['low']['n']} تراکنش)",
                  f"   بالاتر            → "
                  f"{money(inf['high']['gross'])} "
                  f"({inf['high']['n']} تراکنش)"]

    # 📊 منابع درآمد
    if srcs:
        lines += ["", "📊 منابع درآمد:", ""]
        for s in srcs:
            p = s["gross"] * 100.0 / a["gross"] if a["gross"] else 0
            bar = "▓" * max(1, int(p / 10)) + "░" * (10 - max(1, int(p / 10)))
            lines.append(f"   {s['icon']} {s['name']}")
            lines.append(f"      {bar} {p:.0f}٪")
            lines.append(f"      {money(s['gross'])} · {s['n']} تراکنش")

    lines += [
        "", "📈 روند درآمد:",
        f"   📅 امروز: {money(today)}   {_pct(today, yday)}",
        f"   🗓️ ۷ روز اخیر: {money(week)}   {_pct(week, pweek)}",
        f"   📆 ۳۰ روز اخیر: {money(month)}   {_pct(month, pmonth)}",
        "",
        "🧾 تراکنش‌ها:",
        f"   ✅ موفق: {n_paid}",
        f"   ⏳ در انتظار: {n_pending}  ({money(amt_pending)})",
        f"   ❌ ناموفق: {n_failed}",
    ]
    if n_refund:
        lines.append(f"   💸 بازپرداخت: {n_refund}  ({money(amt_refund)})")
    lines += [
        f"   📊 نرخ موفقیت: {rate:.1f}%",
        f"   💳 میانگین هر تراکنش: {money(avg)}",
    ]

    # رسیدهای در انتظار تأیید
    try:
        rcp = db_scalar("SELECT COUNT(*) FROM payment_receipts "
                        "WHERE status='pending'")
        if rcp:
            lines += ["", f"⚠️ {rcp} رسید در انتظار تأیید شماست"]
    except Exception:
        pass

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "💳 ریز درآمد کارمزد", "callback_data": "fin_fees"}],
        [{"text": "🧮 تفکیک کامل درآمد", "callback_data": "fin_break"}],
        [{"text": "🧾 لیست تراکنش‌ها", "callback_data": "fin_tx_0_all"}],
        [{"text": "🎉 درآمد رویدادها", "callback_data": "fin_events"},
         {"text": "📝 درآمد فرم‌ها", "callback_data": "fin_forms"}],
        [{"text": "💳 به تفکیک روش پرداخت", "callback_data": "fin_methods"}],
        [{"text": "📅 گزارش دوره‌ای", "callback_data": "fin_period"}],
        [{"text": "⏳ پرداخت‌های ناتمام", "callback_data": "fin_pending"}],
        [{"text": "👤 پرداخت‌های یک کاربر", "callback_data": "fin_byuser"}],
        [{"text": "📤 خروجی Excel کامل", "callback_data": "fin_export"}],
        [{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}],
    ]})


# ══════════════════════════════════════════════════════════
# 💳 ریز درآمد کارمزد — فاز ۳۰
# ══════════════════════════════════════════════════════════
def show_fees(cid, uid):
    """
    💳 درآمد کارمزد — کامل و به تفکیک روش.

    🎯 «درآمد کارمزد جدا مشخص نشده»

    این همان پولی است که **ما** برمی‌داریم، جدا از بهای
    خدماتی که به برگزارکننده می‌رسد.
    """
    if not perm.require(cid, uid, "fin_view", send):
        return

    a = _agg()
    det = _fee_detail()

    lines = ["💳 درآمد کارمزد", "━━━━━━━━━━━━━━", ""]

    if not a["fee"]:
        lines += ["📭 هنوز کارمزدی دریافت نشده.", "",
                  "💡 اگر انتظار کارمزد دارید، بررسی کنید",
                  "   در «مالی و پرداخت ← کارمزد» روشن باشد."]
        return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
            [{"text": "⚙️ تنظیمات کارمزد", "callback_data": "pay_fee"}],
            [{"text": "🔙 داشبورد مالی", "callback_data": "fin_dash"}]]})

    share = a["fee"] * 100.0 / a["gross"] if a["gross"] else 0
    avg_fee = int(a["fee"] / a["n"]) if a["n"] else 0

    lines += [
        "💰 مجموع کارمزد دریافتی:",
        f"   {money(a['fee'])}", "",
        f"   سهم از کل گردش:  {share:.2f}٪",
        f"   میانگین هر تراکنش: {money(avg_fee)}",
        f"   تعداد تراکنش:     {a['n']}",
        "", "━━━━━━━━━━━━━━", "",
        "📊 به تفکیک روش پرداخت:", "",
    ]

    for d in det:
        p = d["fee"] * 100.0 / a["fee"] if a["fee"] else 0
        lines.append(f"{d['icon']} {d['name']}")
        lines.append(f"   💵 {money(d['fee'])}  ({p:.1f}٪ از کارمزد)")
        lines.append(f"   🧾 {d['n']} تراکنش")
        if d["pct"] is not None:
            rule = []
            if d["pct"]:
                rule.append(f"{d['pct']}٪")
            if d["fix"]:
                rule.append(f"+ {money(d['fix'])}")
            if rule:
                lines.append(f"   ⚙️ نرخ: {' '.join(rule)}")
        lines.append("")

    # 📈 روند کارمزد
    f_today = _agg("date(created_at)=date('now')")["fee"]
    f_week = _agg("created_at >= datetime('now','-7 days')")["fee"]
    f_month = _agg("created_at >= datetime('now','-30 days')")["fee"]
    lines += ["━━━━━━━━━━━━━━", "", "📈 روند کارمزد:",
              f"   📅 امروز:      {money(f_today)}",
              f"   🗓️ ۷ روز اخیر:  {money(f_week)}",
              f"   📆 ۳۰ روز اخیر: {money(f_month)}"]

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "⚙️ تنظیمات کارمزد", "callback_data": "pay_fee"}],
        [{"text": "🧮 تفکیک کامل درآمد", "callback_data": "fin_break"}],
        [{"text": "🔙 داشبورد مالی", "callback_data": "fin_dash"}]]})


# ══════════════════════════════════════════════════════════
# 🧮 تفکیک کامل درآمد — فاز ۳۰
# ══════════════════════════════════════════════════════════
def show_breakdown(cid, uid):
    """
    🧮 صورت کامل درآمد — از ناخالص تا خالص، خط به خط.

    مثل یک صورت سود و زیان ساده: هر ریال از کجا آمده و
    کجا رفته.
    """
    if not perm.require(cid, uid, "fin_view", send):
        return

    a = _agg()
    refund = _refunded()
    net = a["gross"] - refund

    lines = ["🧮 تفکیک کامل درآمد", "━━━━━━━━━━━━━━", ""]

    if not a["n"]:
        lines.append("📭 هنوز تراکنش موفقی ثبت نشده.")
        return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
            [{"text": "🔙 داشبورد مالی", "callback_data": "fin_dash"}]]})

    # ═══ صورت درآمد ═══
    lines += [
        "📋 صورت درآمد:", "",
        f"   ناخالص دریافتی     {money(a['gross'])}",
    ]
    if refund:
        lines.append(f"   کسر بازپرداخت      −{money(refund)}")
    lines += ["   ══════════════════════",
              f"   💰 خالص             {money(net)}", ""]

    # ═══ تقسیم خالص ═══
    lines += ["🔀 تقسیم درآمد:", ""]
    if a["fee"]:
        pf = a["fee"] * 100.0 / a["gross"] if a["gross"] else 0
        pb = 100 - pf
        lines += [
            f"   📦 بهای خدمات   {money(a['base'])}  ({pb:.1f}٪)",
            f"      ↳ سهم برگزارکننده",
            f"   💳 کارمزد       {money(a['fee'])}  ({pf:.1f}٪)",
            f"      ↳ درآمد ما",
        ]
    else:
        lines += [f"   📦 بهای خدمات   {money(a['base'])}  (۱۰۰٪)",
                  "   💳 کارمزد       — (غیرفعال)"]
    if a["points"]:
        lines += ["", f"   🏆 امتیاز مصرفی  {money(a['points'])}",
                  "      ↳ تخفیف باشگاه، نه پول نقد"]

    # ═══ منابع ═══
    srcs = _by_source()
    if srcs:
        lines += ["", "━━━━━━━━━━━━━━", "", "📊 به تفکیک منبع:", ""]
        for s in srcs:
            p = s["gross"] * 100.0 / a["gross"] if a["gross"] else 0
            lines.append(f"{s['icon']} {s['name']}  ({p:.1f}٪)")
            lines.append(f"   ناخالص  {money(s['gross'])}")
            if s["fee"]:
                lines.append(f"   کارمزد  {money(s['fee'])}")
                lines.append(f"   خالص    {money(s['base'])}")
            lines.append(f"   🧾 {s['n']} تراکنش")
            lines.append("")

    # ═══ روش‌های پرداخت ═══
    meths = _by_method()
    if meths:
        lines += ["━━━━━━━━━━━━━━", "", "💳 به تفکیک روش:", ""]
        for m in meths:
            p = m["gross"] * 100.0 / a["gross"] if a["gross"] else 0
            fee_txt = f" · کارمزد {money(m['fee'])}" if m["fee"] else ""
            lines.append(f"{m['icon']} {m['name']}  ({p:.1f}٪)")
            lines.append(f"   {money(m['gross'])} · {m['n']} تراکنش{fee_txt}")
        lines.append("")

    # ═══ معوقات ═══
    pend = int(db_scalar("SELECT COALESCE(SUM(amount),0) FROM transactions "
                         "WHERE status='pending'") or 0)
    if pend:
        n_p = _count("status='pending'")
        lines += ["━━━━━━━━━━━━━━", "", "⏳ در انتظار وصول:",
                  f"   {money(pend)}  ({n_p} تراکنش)",
                  "   💡 هنوز درآمد نیست — ممکن است لغو شود"]

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "💳 ریز کارمزد", "callback_data": "fin_fees"}],
        [{"text": "📅 گزارش دوره‌ای", "callback_data": "fin_period"}],
        [{"text": "📤 خروجی Excel", "callback_data": "fin_export"}],
        [{"text": "🔙 داشبورد مالی", "callback_data": "fin_dash"}]]})


# ══════════════════════════════════════════════════════════
# 📅 گزارش دوره‌ای — فاز ۳۰
# ══════════════════════════════════════════════════════════
def show_period(cid, uid, key="month"):
    """📅 گزارش یک بازهٔ زمانی با همهٔ تفکیک‌ها"""
    if not perm.require(cid, uid, "fin_view", send):
        return

    name, w_now, w_prev = PERIODS.get(key, PERIODS["month"])
    a = _agg(w_now)
    prev = _agg(w_prev) if w_prev else None
    refund = _refunded(w_now)

    lines = [f"📅 گزارش {name}", "━━━━━━━━━━━━━━", ""]

    if not a["n"]:
        lines.append(f"📭 در {name} تراکنش موفقی نبوده.")
    else:
        net = a["gross"] - refund
        lines += [
            "💵 درآمد:", "",
            f"   ناخالص      {money(a['gross'])}",
        ]
        if refund:
            lines.append(f"   بازپرداخت   −{money(refund)}")
            lines.append(f"   خالص        {money(net)}")
        lines += ["",
                  f"   📦 بهای خدمات {money(a['base'])}",
                  f"   💳 کارمزد     {money(a['fee'])}"]
        if a["points"]:
            lines.append(f"   🏆 امتیاز     {money(a['points'])}")
        lines += ["", f"   🧾 {a['n']} تراکنش موفق",
                  f"   💳 میانگین {money(int(a['gross'] / a['n']))}"]

        if prev and prev["n"]:
            lines += ["", "📊 نسبت به دورهٔ قبل:", "",
                      f"   ناخالص  {_pct(a['gross'], prev['gross'])}",
                      f"   کارمزد  {_pct(a['fee'], prev['fee'])}",
                      f"   تعداد   {_pct(a['n'], prev['n'])}"]

        # منابع در همین بازه
        rows = []
        for skey, meta in SOURCES.items():
            w = meta["where"]
            if w_now:
                w = f"({w}) AND ({w_now})"
            sa = _agg(w)
            if sa["n"]:
                rows.append((meta, sa))
        if rows:
            lines += ["", "━━━━━━━━━━━━━━", "", "📊 منابع:", ""]
            for meta, sa in sorted(rows, key=lambda x: -x[1]["gross"]):
                p = sa["gross"] * 100.0 / a["gross"] if a["gross"] else 0
                lines.append(f"   {meta['icon']} {meta['name']}: "
                             f"{money(sa['gross'])} ({p:.0f}٪)")

    btns = []
    row = []
    for k, (nm, _a, _b) in PERIODS.items():
        mark = "🔘" if k == key else "▫️"
        row.append({"text": f"{mark} {nm}", "callback_data": f"fin_per_{k}"})
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([{"text": "🧮 تفکیک کامل", "callback_data": "fin_break"}])
    btns.append([{"text": "🔙 داشبورد مالی", "callback_data": "fin_dash"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ==================== لیست تراکنش‌ها ====================
def show_transactions(cid, uid, page=0, flt="all"):
    if not perm.require(cid, uid, "fin_view", send):
        return

    where = ""
    if flt == "paid":
        where = f"t.status IN {PAID_STATES}"
    elif flt in ("pending", "failed", "refunded"):
        where = f"t.status='{flt}'"

    sql = """SELECT t.*, u.first_name, u.last_name, u.mobile, e.title ev_title
        FROM transactions t
        LEFT JOIN users u ON u.bale_user_id=t.bale_user_id
        LEFT JOIN events e ON e.id=t.event_id"""
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY t.id DESC LIMIT 300"
    rows = db_execute(sql, fetch="all") or []

    if not rows:
        return send_or_edit(cid, (
            "🧾 تراکنش‌ها\n━━━━━━━━━━━━━━\n\n📭 تراکنشی یافت نشد."
        ), {"inline_keyboard": [
            [{"text": "🎛️ همه", "callback_data": "fin_tx_0_all"}],
            [{"text": "🔙 بازگشت", "callback_data": "fin_dash"}]]})

    per = TX_PER_PAGE
    pages = max(1, (len(rows) + per - 1) // per)
    page = max(0, min(int(page or 0), pages - 1))
    chunk = rows[page * per:(page + 1) * per]

    fname = {"all": "همه", "paid": "موفق", "pending": "در انتظار",
             "failed": "ناموفق", "refunded": "بازپرداخت"}.get(flt, "همه")
    shown = sum(int(r.get("amount") or 0) for r in rows
                if r.get("status") in PAID_STATES)
    lines = [f"🧾 تراکنش‌ها — {fname}", "━━━━━━━━━━━━━━",
             f"📊 {len(rows)} مورد | 💵 {money(shown)}", ""]

    for r in chunk:
        s = _st(r.get("status"))
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
        lines.append(f"{s['icon']} {money(r.get('amount'))} — {s['name']}")
        lines.append(f"   👤 {nm or r.get('bale_user_id') or '—'}")
        if r.get("ev_title"):
            lines.append(f"   🎉 {str(r['ev_title'])[:30]}")
        lines.append(f"   🕐 {_jd.fmt(r.get('created_at'), 'datetime')}")
        lines.append("")

    btns = []
    if pages > 1:
        nav = []
        if page > 0:
            nav.append({"text": "⬅️", "callback_data": f"fin_tx_{page-1}_{flt}"})
        nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
        if page < pages - 1:
            nav.append({"text": "➡️", "callback_data": f"fin_tx_{page+1}_{flt}"})
        btns.append(nav)
    btns.append([{"text": "✅ موفق", "callback_data": "fin_tx_0_paid"},
                 {"text": "⏳ در انتظار", "callback_data": "fin_tx_0_pending"}])
    btns.append([{"text": "❌ ناموفق", "callback_data": "fin_tx_0_failed"},
                 {"text": "🎛️ همه", "callback_data": "fin_tx_0_all"}])
    btns.append([{"text": "🔙 داشبورد مالی", "callback_data": "fin_dash"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ==================== درآمد به تفکیک ====================
def show_by_event(cid, uid):
    if not perm.require(cid, uid, "fin_view", send):
        return
    rows = db_execute(f"""SELECT e.id, e.title, e.price,
        COUNT(t.id) n, COALESCE(SUM(t.amount),0) total
        FROM events e LEFT JOIN transactions t
          ON t.event_id=e.id AND t.status IN {PAID_STATES}
        GROUP BY e.id HAVING n > 0
        ORDER BY total DESC LIMIT 20""", fetch="all") or []

    grand = sum(int(r["total"]) for r in rows)
    lines = ["🎉 درآمد به تفکیک رویداد", "━━━━━━━━━━━━━━",
             f"💵 مجموع: {money(grand)}", ""]
    if rows:
        for i, r in enumerate(rows, 1):
            pct = int(r["total"]) * 100.0 / grand if grand else 0
            bar = "█" * max(1, int(pct / 10))
            lines.append(f"{i}. {str(r['title'])[:30]}")
            lines.append(f"   {bar} {money(r['total'])} ({pct:.0f}%)")
            lines.append(f"   🎫 {r['n']} پرداخت")
    else:
        lines.append("📭 درآمدی ثبت نشده")
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 داشبورد مالی", "callback_data": "fin_dash"}]]})


def show_by_form(cid, uid):
    if not perm.require(cid, uid, "fin_view", send):
        return
    rows = db_execute("""SELECT f.id, f.title,
        COUNT(r.id) n, COALESCE(SUM(r.amount),0) total
        FROM forms f LEFT JOIN form_responses r
          ON r.form_id=f.id AND r.payment_status='paid'
        GROUP BY f.id HAVING n > 0
        ORDER BY total DESC LIMIT 20""", fetch="all") or []

    grand = sum(int(r["total"]) for r in rows)
    lines = ["📝 درآمد به تفکیک فرم", "━━━━━━━━━━━━━━",
             f"💵 مجموع: {money(grand)}", ""]
    if rows:
        for i, r in enumerate(rows, 1):
            pct = int(r["total"]) * 100.0 / grand if grand else 0
            bar = "█" * max(1, int(pct / 10))
            lines.append(f"{i}. {str(r['title'])[:30]}")
            lines.append(f"   {bar} {money(r['total'])} ({pct:.0f}%)")
            lines.append(f"   📥 {r['n']} پرداخت")
    else:
        lines.append("📭 درآمدی ثبت نشده")
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 داشبورد مالی", "callback_data": "fin_dash"}]]})


def show_by_method(cid, uid):
    """💳 درآمد به تفکیک روش پرداخت"""
    if not perm.require(cid, uid, "fin_view", send):
        return
    from payments import PAYMENT_METHODS

    lines = ["💳 درآمد به تفکیک روش پرداخت", "━━━━━━━━━━━━━━", ""]
    grand = _sum()

    # کیف پول / درگاه از transactions
    wallet = _sum("payload LIKE 'ev%'")
    gateway = _sum("payload LIKE 'gw%'")
    # کارت به کارت از رسیدها
    card = 0
    n_card = 0
    try:
        card = db_scalar("SELECT COALESCE(SUM(amount),0) FROM payment_receipts "
                         "WHERE status='approved'")
        n_card = db_scalar("SELECT COUNT(*) FROM payment_receipts "
                           "WHERE status='approved'")
    except Exception:
        pass

    data = [
        ("🏦 کیف پول بله", wallet, _count(f"payload LIKE 'ev%' "
                                          f"AND status IN {PAID_STATES}")),
        ("🔗 درگاه سفارشی", gateway, _count(f"payload LIKE 'gw%' "
                                            f"AND status IN {PAID_STATES}")),
        ("💳 کارت به کارت", card, n_card),
    ]
    tot = sum(d[1] for d in data) or 1
    for name, amt, n in data:
        pct = amt * 100.0 / tot
        bar = "█" * max(1, int(pct / 10)) if amt else ""
        lines.append(f"{name}")
        lines.append(f"   {bar} {money(amt)} ({pct:.0f}%)")
        lines.append(f"   🧾 {n} تراکنش")
        lines.append("")

    lines.append(f"💵 مجموع: {money(sum(d[1] for d in data))}")
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 داشبورد مالی", "callback_data": "fin_dash"}]]})


def show_pending(cid, uid):
    """⏳ پرداخت‌های ناتمام — پول‌هایی که هنوز وصول نشده"""
    if not perm.require(cid, uid, "fin_view", send):
        return

    rows = db_execute("""SELECT t.*, u.first_name, u.last_name, u.mobile,
        e.title ev_title FROM transactions t
        LEFT JOIN users u ON u.bale_user_id=t.bale_user_id
        LEFT JOIN events e ON e.id=t.event_id
        WHERE t.status='pending' ORDER BY t.id DESC LIMIT 20""",
        fetch="all") or []
    amt = db_scalar("SELECT COALESCE(SUM(amount),0) FROM transactions "
                    "WHERE status='pending'")

    lines = ["⏳ پرداخت‌های ناتمام", "━━━━━━━━━━━━━━",
             f"💰 مبلغ معلق: {money(amt)}",
             f"🧾 تعداد: {len(rows)}", ""]
    if rows:
        for r in rows:
            nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
            lines.append(f"⏳ {money(r.get('amount'))} — {nm or '—'}")
            if r.get("ev_title"):
                lines.append(f"   🎉 {str(r['ev_title'])[:30]}")
            lines.append(f"   📱 {r.get('mobile') or '—'}")
            lines.append(f"   🕐 {_jd.fmt(r.get('created_at'), 'datetime')}")
            lines.append("")
        lines.append("💡 می‌توانید به این کاربران یادآوری کنید.")
    else:
        lines.append("✅ پرداخت ناتمامی نیست")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 داشبورد مالی", "callback_data": "fin_dash"}]]})


def show_user_payments(cid, uid, target=None):
    """👤 سابقه پرداخت یک کاربر"""
    if not perm.require(cid, uid, "fin_view", send):
        return
    if target is None:
        from auth import set_state
        set_state(uid, "fin_search", {}, merge=False)
        from bale_api import kb_cancel
        return send(cid, (
            "👤 پرداخت‌های یک کاربر\n━━━━━━━━━━━━━━\n\n"
            "شماره موبایل یا آیدی عددی کاربر را بفرستید:"
        ), kb_cancel())

    u = db_execute("SELECT * FROM users WHERE bale_user_id=?", (target,),
                   fetch="one")
    rows = db_execute("""SELECT t.*, e.title ev_title FROM transactions t
        LEFT JOIN events e ON e.id=t.event_id
        WHERE t.bale_user_id=? ORDER BY t.id DESC LIMIT 20""",
        (target,), fetch="all") or []
    paid = _sum("bale_user_id=?", (target,))

    nm = f"{(u or {}).get('first_name') or ''} {(u or {}).get('last_name') or ''}".strip()
    lines = [f"👤 پرداخت‌های {nm or target}", "━━━━━━━━━━━━━━",
             f"💵 مجموع پرداختی: {money(paid)}",
             f"🧾 تعداد تراکنش: {len(rows)}", ""]
    for r in rows:
        s = _st(r.get("status"))
        lines.append(f"{s['icon']} {money(r.get('amount'))} — {s['name']}")
        if r.get("ev_title"):
            lines.append(f"   🎉 {str(r['ev_title'])[:30]}")
        lines.append(f"   🕐 {_jd.fmt(r.get('created_at'), 'datetime')}")
    if not rows:
        lines.append("📭 تراکنشی ندارد")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 داشبورد مالی", "callback_data": "fin_dash"}]]})


def handle_search(message):
    """جستجوی کاربر برای گزارش مالی"""
    from auth import clear_state, normalize_mobile, normalize_digits
    from bale_api import kb_remove, BTN_BACK
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = normalize_digits((message.get("text") or "").strip())
    clear_state(uid)

    if text in (BTN_BACK, "🔙 بازگشت"):
        send(cid, "❌ لغو شد", kb_remove())
        return show_dashboard(cid, uid)

    target = None
    if text.isdigit() and len(text) < 12:
        r = db_execute("SELECT bale_user_id FROM users WHERE bale_user_id=?",
                       (int(text),), fetch="one")
        target = (r or {}).get("bale_user_id")
    if not target:
        mob = normalize_mobile(text)
        if mob:
            r = db_execute("SELECT bale_user_id FROM users WHERE mobile=?",
                           (mob,), fetch="one")
            target = (r or {}).get("bale_user_id")
    if not target:
        send(cid, "❌ کاربر پیدا نشد", kb_remove())
        return show_dashboard(cid, uid)
    send(cid, "🔍 پیدا شد", kb_remove())
    return show_user_payments(cid, uid, target)


# ==================== خروجی Excel ====================
def export_finance(cid, uid):
    """📤 خروجی Excel مالی — ۴ شیت"""
    if not perm.require(cid, uid, "fin_export", send):
        return
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        return send(cid, "❌ openpyxl نصب نیست:\npy -m pip install openpyxl")

    wb = openpyxl.Workbook()
    bold = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="4472C4")

    def _head(ws, cols):
        ws.append(cols)
        ws.sheet_view.rightToLeft = True
        for i in range(1, len(cols) + 1):
            c = ws.cell(row=1, column=i)
            c.font = bold
            c.fill = fill
            c.alignment = Alignment(horizontal="center")
        for i, h in enumerate(cols, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = \
                max(12, min(34, len(str(h)) + 10))
        ws.freeze_panes = "A2"

    # شیت ۱: تراکنش‌ها
    ws = wb.active
    ws.title = "تراکنش‌ها"
    _head(ws, ["ردیف", "تاریخ", "کاربر", "موبایل", "منبع", "عنوان",
               "روش پرداخت", "ناخالص (ریال)", "کارمزد (ریال)",
               "خالص (ریال)", "امتیاز", "وضعیت", "کد پیگیری"])
    rows = db_execute("""SELECT t.*, u.first_name, u.last_name, u.mobile,
        e.title ev_title FROM transactions t
        LEFT JOIN users u ON u.bale_user_id=t.bale_user_id
        LEFT JOIN events e ON e.id=t.event_id
        ORDER BY t.id DESC LIMIT 5000""", fetch="all") or []
    try:
        from payments import PAYMENT_METHODS as _PM
    except Exception:
        _PM = {}
    for n, r in enumerate(rows, 1):
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
        gross = int(r.get("amount") or 0)
        fee = int(r.get("fee_amount") or 0)
        base = int(r.get("base_amount") or 0) or (gross - fee)
        # 🏷️ منبع درآمد
        if r.get("event_id"):
            src, ttl = "رویداد", r.get("ev_title") or ""
        elif r.get("form_id") or r.get("form_response_id"):
            src, ttl = "فرم", ""
        elif r.get("plan_id"):
            src, ttl = "قسط", f"قسط {r.get('installment_no') or ''}"
        else:
            src, ttl = "سایر", ""
        mkey = r.get("method") or ""
        mname = _PM.get(mkey, {}).get("name", mkey or "نامشخص")
        ws.append([n, _jd.fmt(r.get('created_at'), 'datetime'), nm,
                   r.get("mobile") or "", src, ttl, mname,
                   gross, fee, base, int(r.get("points_used") or 0),
                   _st(r.get("status"))["name"],
                   r.get("transaction_id") or r.get("payload") or ""])

    # شیت ۲: خلاصه
    ws2 = wb.create_sheet("خلاصه مالی")
    _head(ws2, ["شاخص", "مقدار (ریال)"])
    pending_amt = db_scalar("SELECT COALESCE(SUM(amount),0) FROM transactions "
                            "WHERE status='pending'")
    _a = _agg()
    _ref = _refunded()
    for label, val in [
        ("═══ درآمد ═══", ""),
        ("ناخالص کل", _a["gross"]),
        ("بازپرداخت‌شده", -_ref if _ref else 0),
        ("خالص کل", _a["gross"] - _ref),
        ("═══ تقسیم ═══", ""),
        ("بهای خدمات (سهم برگزارکننده)", _a["base"]),
        ("کارمزد (درآمد ما)", _a["fee"]),
        ("امتیاز مصرف‌شده", _a["points"]),
        ("═══ بازه ═══", ""),
        ("امروز", _sum("date(created_at)=date('now')")),
        ("۷ روز اخیر", _sum("created_at >= datetime('now','-7 days')")),
        ("۳۰ روز اخیر", _sum("created_at >= datetime('now','-30 days')")),
        ("در انتظار وصول", pending_amt),
    ]:
        ws2.append([label, int(val or 0) if val != "" else ""])
    ws2.append(["═══ تعداد ═══", ""])
    ws2.append(["تراکنش موفق", _count(f"status IN {PAID_STATES}")])
    ws2.append(["در انتظار", _count("status='pending'")])
    ws2.append(["ناموفق", _count("status='failed'")])
    ws2.append(["بازپرداخت", _count("status='refunded'")])
    if _a["n"]:
        ws2.append(["میانگین هر تراکنش", int(_a["gross"] / _a["n"])])
        if _a["gross"]:
            ws2.append(["سهم کارمزد از گردش (٪)",
                        round(_a["fee"] * 100.0 / _a["gross"], 2)])

    # شیت ۲-ب: ریز کارمزد به تفکیک روش
    wsf = wb.create_sheet("ریز کارمزد")
    _head(wsf, ["روش پرداخت", "تعداد", "ناخالص (ریال)",
                "کارمزد (ریال)", "سهم از کارمزد (٪)", "نرخ"])
    try:
        from payments import fee_percent as _fp, fee_fixed as _ff
    except Exception:
        _fp = _ff = None
    for d in _fee_detail():
        rule = ""
        if _fp:
            try:
                _p2, _f2 = _fp(d["key"]), _ff(d["key"])
                rule = (f"{_p2}٪" if _p2 else "") + \
                       (f" + {_f2}" if _f2 else "")
            except Exception:
                pass
        g = next((m["gross"] for m in _by_method()
                  if m["key"] == d["key"]), 0)
        wsf.append([d["name"], d["n"], g, d["fee"],
                    round(d["fee"] * 100.0 / _a["fee"], 2)
                    if _a["fee"] else 0, rule.strip()])

    # شیت ۲-ج: تفکیک منبع درآمد
    wss = wb.create_sheet("منابع درآمد")
    _head(wss, ["منبع", "تعداد", "ناخالص (ریال)",
                "کارمزد (ریال)", "خالص (ریال)", "سهم (٪)"])
    for _src in _by_source():
        wss.append([_src["name"], _src["n"], _src["gross"],
                    _src["fee"], _src["base"],
                    round(_src["gross"] * 100.0 / _a["gross"], 2)
                    if _a["gross"] else 0])

    # شیت ۳: درآمد رویدادها
    ws3 = wb.create_sheet("درآمد رویدادها")
    _head(ws3, ["رویداد", "تعداد پرداخت", "درآمد (ریال)"])
    for r in db_execute(f"""SELECT e.title, COUNT(t.id) n,
        COALESCE(SUM(t.amount),0) total FROM events e
        LEFT JOIN transactions t ON t.event_id=e.id
          AND t.status IN {PAID_STATES}
        GROUP BY e.id HAVING n>0 ORDER BY total DESC""", fetch="all") or []:
        ws3.append([r["title"], r["n"], int(r["total"])])

    # شیت ۴: رسیدهای کارت‌به‌کارت
    ws4 = wb.create_sheet("رسیدها")
    _head(ws4, ["ردیف", "تاریخ", "کاربر", "مبلغ (ریال)", "وضعیت"])
    try:
        for n, r in enumerate(db_execute("""SELECT p.*, u.first_name, u.last_name
            FROM payment_receipts p
            LEFT JOIN users u ON u.bale_user_id=p.bale_user_id
            ORDER BY p.id DESC LIMIT 2000""", fetch="all") or [], 1):
            nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
            ws4.append([n, _jd.fmt(r.get('created_at'), 'datetime'), nm,
                        int(r.get("amount") or 0),
                        _st(r.get("status"))["name"]])
    except Exception as e:
        log(f"⚠️ شیت رسیدها: {e}")

    from pathlib import Path
    d = Path(FILES_DIR) / "exports"
    d.mkdir(parents=True, exist_ok=True)
    fp = d / f"finance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    try:
        wb.save(fp)
    except Exception as e:
        log(f"❌ ذخیره اکسل مالی: {e}")
        return send(cid, "❌ خطا در ساخت فایل")

    res = send_document(cid, str(fp), (
        f"💰 گزارش مالی کامل\n\n"
        f"🧾 {len(rows)} تراکنش | 💵 {money(_sum())}\n"
        f"📄 ۴ شیت: تراکنش‌ها، خلاصه، رویدادها، رسیدها"
    ))
    if not res.get("ok"):
        send(cid, f"⚠️ ارسال ناموفق\n📁 {fp}")
    return send(cid, "✅ خروجی آماده شد", {"inline_keyboard": [
        [{"text": "🔙 داشبورد مالی", "callback_data": "fin_dash"}]]})
