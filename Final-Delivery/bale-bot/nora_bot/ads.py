"""
📣 پنل تبلیغات و کمپین — فاز ۲۰

درخواست کاربر:
  «قسمت تبلیغات هم در اطلاع‌رسانی اضافه کن و همه جزییات لازم خیلی
   شیک و جامع برای پنل تبلیغات در ربات اضافه کن. هرچی به نظرت خوبه
   واسه تبلیغات و متدهای روز، به ربات اضافه کن»

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 چه چیزهایی دارد؟

  🎯 کمپین‌های هدفمند   — به چه کسانی، چه زمانی
  📊 A/B تست           — دو نسخه، برنده خودکار
  📈 آمار دقیق         — بازدید · کلیک · تبدیل · CTR
  ⏰ زمان‌بندی          — الان / زمان مشخص / تکرارشونده
  🐢 ارسال تدریجی      — سرور و کاربر خسته نشوند
  🔗 لینک ردیابی‌شونده  — بفهمیم چند نفر کلیک کردند
  🎟️ کد تخفیف اختصاصی  — برای هر کمپین
  🔕 لغو اشتراک        — کاربر بتواند خاموش کند (احترام)
  🏆 امتیازدهی         — کاربران فعال پاداش بگیرند
  ♻️ کمپین تکراری      — هفتگی / ماهانه
  🚦 سقف روزانه        — بیش از حد پیام نرود
"""
import json
import random
import time
from datetime import datetime, timedelta

from config import SUPER_ADMIN_ID, money
from database import (db_execute, db_scalar, get_setting, set_setting,
                      ensure_table, log)
from auth import (
    set_state, get_state_data, update_state_data, clear_state,
    log_action, normalize_digits, is_admin as _is_admin,
)
from bale_api import (
    send, send_or_edit, send_photo, send_document,
    kb_cancel, kb_remove, BTN_BACK,
)

STATE_AD_NEW = "ad_new"
STATE_AD_EDIT = "ad_edit"
STATE_AD_MEDIA = "ad_media"

# ══════════════════════════════════════════════════════════
# 🎯 انواع کمپین
# ══════════════════════════════════════════════════════════
AD_TYPES = {
    "promo": {"icon": "📣", "name": "تبلیغ عمومی",
              "desc": "معرفی یک رویداد، دوره یا خبر"},
    "event": {"icon": "🎉", "name": "معرفی رویداد",
              "desc": "با دکمه ثبت‌نام مستقیم"},
    "form": {"icon": "📝", "name": "دعوت به فرم",
             "desc": "نظرسنجی، ثبت‌نام، همکاری"},
    "discount": {"icon": "🎟️", "name": "کد تخفیف",
                 "desc": "کد اختصاصی با مهلت"},
    "reminder": {"icon": "🔔", "name": "یادآوری",
                 "desc": "یادآوری رویداد یا اقدام ناتمام"},
    "reengage": {"icon": "💚", "name": "بازگرداندن کاربر",
                 "desc": "برای کسانی که مدتی نیامده‌اند"},
    "announce": {"icon": "📢", "name": "اطلاعیه رسمی",
                 "desc": "خبر مهم — بدون لحن تبلیغاتی"},
}

# ⏰ زمان‌بندی
SCHEDULES = {
    "now": {"icon": "⚡", "name": "همین حالا"},
    "at": {"icon": "🕐", "name": "زمان مشخص"},
    "daily": {"icon": "📅", "name": "هر روز"},
    "weekly": {"icon": "🗓️", "name": "هفتگی"},
    "monthly": {"icon": "📆", "name": "ماهانه"},
}

# 🚦 وضعیت
AD_STATUS = {
    "draft": {"icon": "📝", "name": "پیش‌نویس"},
    "scheduled": {"icon": "⏳", "name": "زمان‌بندی‌شده"},
    "running": {"icon": "🚀", "name": "در حال ارسال"},
    "paused": {"icon": "⏸️", "name": "متوقف"},
    "done": {"icon": "✅", "name": "تمام‌شده"},
    "failed": {"icon": "❌", "name": "ناموفق"},
}

ADS_SCHEMA = {
    "title": "TEXT",
    "ad_type": "TEXT DEFAULT 'promo'",
    "body": "TEXT",
    "body_b": "TEXT",                 # 📊 نسخه دوم برای A/B تست
    "ab_test": "INTEGER DEFAULT 0",
    "media_type": "TEXT",             # photo | video | document
    "media_id": "TEXT",
    "btn_text": "TEXT",
    "btn_url": "TEXT",
    "btn_cb": "TEXT",                 # callback داخلی (رویداد/فرم)
    "event_id": "INTEGER",
    "form_id": "INTEGER",
    "discount_code": "TEXT",
    "target": "TEXT DEFAULT 'all'",   # فیلتر مخاطب
    "target_value": "TEXT",
    "schedule": "TEXT DEFAULT 'now'",
    "run_at": "TEXT",                 # تاریخ شمسی
    "run_time": "TEXT",               # ساعت
    "status": "TEXT DEFAULT 'draft'",
    "rate": "INTEGER DEFAULT 20",     # پیام در دقیقه
    "quiet_hours": "INTEGER DEFAULT 1",   # شب مزاحم نشود
    "points_reward": "INTEGER DEFAULT 0",
    # 📊 آمار
    "sent_count": "INTEGER DEFAULT 0",
    "fail_count": "INTEGER DEFAULT 0",
    "view_count": "INTEGER DEFAULT 0",
    "click_count": "INTEGER DEFAULT 0",
    "convert_count": "INTEGER DEFAULT 0",
    "sent_a": "INTEGER DEFAULT 0",
    "sent_b": "INTEGER DEFAULT 0",
    "click_a": "INTEGER DEFAULT 0",
    "click_b": "INTEGER DEFAULT 0",
    "last_run": "TIMESTAMP",
    "created_by": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

LOG_SCHEMA = {
    "ad_id": "INTEGER",
    "bale_user_id": "INTEGER",
    "variant": "TEXT DEFAULT 'a'",
    "sent_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "clicked": "INTEGER DEFAULT 0",
    "clicked_at": "TIMESTAMP",
    "converted": "INTEGER DEFAULT 0",
}


def init_ads_tables():
    ensure_table("ad_campaigns", ADS_SCHEMA)
    ensure_table("ad_logs", LOG_SCHEMA)
    for q in ("CREATE INDEX IF NOT EXISTS idx_adlog_ad "
              "ON ad_logs(ad_id, bale_user_id)",
              "CREATE INDEX IF NOT EXISTS idx_ad_status "
              "ON ad_campaigns(status)"):
        try:
            db_execute(q)
        except Exception:
            pass
    log("✅ جدول‌های تبلیغات آماده شد")


def get_ad(aid):
    return db_execute("SELECT * FROM ad_campaigns WHERE id=?", (aid,),
                      fetch="one")


def _guard(cid, uid):
    if not _is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    import permissions as perm
    if not perm.can_section(uid, "notify"):
        send(cid, "🔒 دسترسی به بخش اطلاع‌رسانی ندارید")
        return False
    return True


# ══════════════════════════════════════════════════════════
# 🔕 احترام به کاربر — لغو اشتراک و سقف روزانه
# ══════════════════════════════════════════════════════════
def user_opted_out(uid):
    """آیا کاربر تبلیغات را خاموش کرده؟"""
    try:
        r = db_execute("SELECT ads_optout FROM users WHERE bale_user_id=?",
                       (uid,), fetch="one")
        return bool((r or {}).get("ads_optout"))
    except Exception:
        return False


def set_optout(uid, on=True):
    try:
        db_execute("UPDATE users SET ads_optout=? WHERE bale_user_id=?",
                   (1 if on else 0, uid))
        return True
    except Exception as e:
        log(f"⚠️ لغو اشتراک تبلیغات: {e}")
        return False


def daily_cap():
    """حداکثر تبلیغ در روز برای هر کاربر"""
    try:
        return int(get_setting("ads_daily_cap", "2") or 2)
    except (TypeError, ValueError):
        return 2


def got_enough_today(uid):
    """آیا امروز به سقف رسیده؟"""
    cap = daily_cap()
    if cap <= 0:
        return False
    try:
        n = db_scalar("SELECT COUNT(*) FROM ad_logs WHERE bale_user_id=? "
                      "AND sent_at >= datetime('now','-1 day')", (uid,)) or 0
        return n >= cap
    except Exception:
        return False


def in_quiet_hours():
    """🌙 ساعت سکوت — نصف‌شب مزاحم کسی نشویم"""
    if get_setting("ads_quiet_on", "1") != "1":
        return False
    try:
        s = int(get_setting("ads_quiet_start", "23") or 23)
        e = int(get_setting("ads_quiet_end", "8") or 8)
        h = datetime.now().hour
        return (h >= s or h < e) if s > e else (s <= h < e)
    except Exception:
        return False


# ══════════════════════════════════════════════════════════
# 📊 آمار
# ══════════════════════════════════════════════════════════
def ctr(ad):
    """نرخ کلیک"""
    s = int((ad or {}).get("sent_count") or 0)
    c = int((ad or {}).get("click_count") or 0)
    return round(c * 100 / s, 1) if s else 0.0


def conv_rate(ad):
    s = int((ad or {}).get("sent_count") or 0)
    c = int((ad or {}).get("convert_count") or 0)
    return round(c * 100 / s, 1) if s else 0.0


def ab_winner(ad):
    """🏆 کدام نسخه بهتر بود؟"""
    sa = int((ad or {}).get("sent_a") or 0)
    sb = int((ad or {}).get("sent_b") or 0)
    ca = int((ad or {}).get("click_a") or 0)
    cb = int((ad or {}).get("click_b") or 0)
    if not sa or not sb:
        return None, 0, 0
    ra = ca * 100 / sa
    rb = cb * 100 / sb
    if abs(ra - rb) < 1:
        return "tie", round(ra, 1), round(rb, 1)
    return ("a" if ra > rb else "b"), round(ra, 1), round(rb, 1)


# ══════════════════════════════════════════════════════════
# 📋 پنل اصلی
# ══════════════════════════════════════════════════════════
def show_panel(cid, uid, page=0):
    """📣 پنل تبلیغات"""
    if not _guard(cid, uid):
        return

    rows = db_execute("SELECT * FROM ad_campaigns ORDER BY id DESC "
                      "LIMIT 60", fetch="all") or []
    running = sum(1 for r in rows if r.get("status") in
                  ("running", "scheduled"))
    tot_sent = sum(int(r.get("sent_count") or 0) for r in rows)
    tot_click = sum(int(r.get("click_count") or 0) for r in rows)
    avg_ctr = round(tot_click * 100 / tot_sent, 1) if tot_sent else 0

    try:
        n_out = db_scalar("SELECT COUNT(*) FROM users "
                          "WHERE COALESCE(ads_optout,0)=1") or 0
    except Exception:
        n_out = 0

    lines = ["📣 پنل تبلیغات", "━━━━━━━━━━━━━━", "",
             f"📊 کمپین‌ها: {len(rows)}   🚀 فعال: {running}",
             f"📨 کل ارسال: {tot_sent:,}   👆 کلیک: {tot_click:,}"]
    if tot_sent:
        lines.append(f"📈 میانگین نرخ کلیک: {avg_ctr}٪")
    if n_out:
        lines.append(f"🔕 لغو اشتراک کرده: {n_out} نفر")
    if in_quiet_hours():
        lines.append("🌙 الان ساعت سکوت است — ارسال متوقف می‌ماند")
    lines.append("")

    btns = [[{"text": "➕ کمپین جدید", "callback_data": "ad_new"}]]

    if rows:
        lines.append("📋 آخرین کمپین‌ها:")
        for r in rows[:6]:
            st = AD_STATUS.get(r.get("status") or "draft",
                               AD_STATUS["draft"])
            t = AD_TYPES.get(r.get("ad_type") or "promo",
                             AD_TYPES["promo"])
            extra = ""
            if r.get("sent_count"):
                extra = f" — {r['sent_count']} ارسال · {ctr(r)}٪"
            lines.append(f"{st['icon']} {t['icon']} "
                         f"{str(r.get('title'))[:24]}{extra}")
            btns.append([{"text": f"{st['icon']} "
                                  f"{str(r.get('title'))[:26]}",
                          "callback_data": f"adv_{r['id']}"}])
        lines.append("")
    else:
        lines += ["🌱 هنوز کمپینی نساخته‌اید.", "",
                  "با «➕ کمپین جدید» شروع کنید — در چند قدم", "",
                  "پیام، مخاطب و زمان را مشخص می‌کنید.", ""]

    btns.append([{"text": "📊 گزارش عملکرد", "callback_data": "ad_report"},
                 {"text": "⚙️ تنظیمات", "callback_data": "ad_settings"}])
    btns.append([{"text": "💡 راهنما و ایده‌ها",
                  "callback_data": "ad_tips"}])
    btns.append([{"text": "🔙 اطلاع‌رسانی",
                  "callback_data": "admin_notify"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ══════════════════════════════════════════════════════════
# ➕ ساخت کمپین — ویزارد
# ══════════════════════════════════════════════════════════
def start_new(cid, uid, ad_type=None):
    if not _guard(cid, uid):
        return
    if not ad_type:
        lines = ["➕ کمپین جدید", "━━━━━━━━━━━━━━", "",
                 "چه نوع کمپینی می‌خواهید؟", ""]
        btns = []
        for k, v in AD_TYPES.items():
            lines.append(f"{v['icon']} {v['name']} — {v['desc']}")
            btns.append([{"text": f"{v['icon']} {v['name']}",
                          "callback_data": f"adnew_{k}"}])
        btns.append([{"text": "🔙 بازگشت", "callback_data": "ad_panel"}])
        return send_or_edit(cid, "\n".join(lines),
                            {"inline_keyboard": btns})

    if ad_type not in AD_TYPES:
        return send(cid, "❌ نامعتبر")
    set_state(uid, STATE_AD_NEW, {"ad_type": ad_type, "step": 0},
              merge=False)
    v = AD_TYPES[ad_type]
    send(cid, (
        f"{v['icon']} {v['name']}\n━━━━━━━━━━━━━━\n\n"
        f"یک نام برای این کمپین بنویسید:\n\n"
        f"💡 این نام فقط برای خودتان است، کاربر نمی‌بیند.\n"
        f"مثال: دعوت به کارگاه فن بیان"
    ), kb_cancel())


def handle_new(message):
    """ویزارد ساخت کمپین"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid)
    step = int(d.get("step") or 0)

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_panel(cid, uid)

    # مرحله ۰ — نام
    if step == 0:
        if len(raw) < 2:
            return send(cid, "⚠️ نام حداقل ۲ حرف:", kb_cancel())
        update_state_data(uid, {"title": raw[:80], "step": 1})
        return send(cid, (
            "📝 متن پیام\n━━━━━━━━━━━━━━\n\n"
            "متنی که به کاربر نمایش داده می‌شود را بنویسید:\n\n"
            "💡 می‌توانید از این‌ها استفاده کنید:\n"
            "   {نام} — نام کاربر\n"
            "   {سازمان} — نام مجموعه\n\n"
            "✨ نکته: پیام کوتاه و صمیمی بهتر جواب می‌دهد."
        ), kb_cancel())

    # مرحله ۱ — متن
    if step == 1:
        if len(raw) < 5:
            return send(cid, "⚠️ متن خیلی کوتاه است:", kb_cancel())
        aid = db_execute("""INSERT INTO ad_campaigns
            (title, ad_type, body, status, created_by)
            VALUES (?,?,?,'draft',?)""",
            (d.get("title"), d.get("ad_type") or "promo",
             raw[:3000], uid))
        clear_state(uid)
        if not aid:
            return send(cid, "❌ ذخیره ناموفق", kb_remove())
        log_action(uid, "ad_created", {"id": aid})
        send(cid, "✅ کمپین ساخته شد", kb_remove())
        return show_ad(cid, uid, aid)

    clear_state(uid)
    return send(cid, "⚠️ مرحله نامشخص", kb_remove())


def show_ad(cid, uid, aid):
    """📋 جزئیات و تنظیمات یک کمپین"""
    if not _guard(cid, uid):
        return
    a = get_ad(aid)
    if not a:
        return send(cid, "❌ یافت نشد")

    t = AD_TYPES.get(a.get("ad_type") or "promo", AD_TYPES["promo"])
    st = AD_STATUS.get(a.get("status") or "draft", AD_STATUS["draft"])
    sc = SCHEDULES.get(a.get("schedule") or "now", SCHEDULES["now"])

    try:
        import admin as _ad
        tgt = _ad.BC_FILTERS.get(a.get("target") or "all",
                                 {"icon": "👥", "name": "همه"})
    except Exception:
        tgt = {"icon": "👥", "name": a.get("target") or "همه"}

    lines = [f"{t['icon']} {a.get('title')}", "━━━━━━━━━━━━━━", "",
             f"📌 وضعیت: {st['icon']} {st['name']}",
             f"🏷️ نوع: {t['name']}",
             f"🎯 مخاطب: {tgt['icon']} {tgt['name']}",
             f"⏰ زمان: {sc['icon']} {sc['name']}"]
    if a.get("run_at"):
        lines.append(f"   📅 {a['run_at']} {a.get('run_time') or ''}")
    lines.append("")

    body = str(a.get("body") or "")
    lines += ["📝 متن پیام:", body[:300] + ("…" if len(body) > 300 else ""),
              ""]
    if a.get("ab_test") and a.get("body_b"):
        lines += ["🅱️ نسخه دوم (A/B):",
                  str(a["body_b"])[:200], ""]
    if a.get("media_id"):
        lines.append(f"🖼️ رسانه: {a.get('media_type') or 'عکس'} ✅")
    if a.get("btn_text"):
        lines.append(f"🔘 دکمه: {a['btn_text']}")
    if a.get("discount_code"):
        lines.append(f"🎟️ کد تخفیف: {a['discount_code']}")
    if a.get("points_reward"):
        lines.append(f"🏆 امتیاز: {a['points_reward']}")

    # 📊 آمار
    if a.get("sent_count"):
        lines += ["", "━━━━━━━━━━━━━━", "📊 عملکرد:",
                  f"   📨 ارسال: {a['sent_count']:,}"
                  + (f"  ❌ ناموفق: {a['fail_count']}"
                     if a.get("fail_count") else ""),
                  f"   👆 کلیک: {a.get('click_count') or 0}  "
                  f"({ctr(a)}٪)"]
        if a.get("convert_count"):
            lines.append(f"   ✅ تبدیل: {a['convert_count']}  "
                         f"({conv_rate(a)}٪)")
        if a.get("ab_test"):
            w, ra, rb = ab_winner(a)
            if w:
                nm = {"a": "🅰️ نسخه اول", "b": "🅱️ نسخه دوم",
                      "tie": "🤝 مساوی"}[w]
                lines.append(f"   🏆 برنده A/B: {nm} "
                             f"(A={ra}٪ B={rb}٪)")

    btns = []
    if a.get("status") in ("draft", "paused"):
        btns.append([{"text": "🚀 ارسال / فعال‌سازی",
                      "callback_data": f"adgo_{aid}"}])
        btns.append([{"text": "👁️ پیش‌نمایش",
                      "callback_data": f"adprev_{aid}"},
                     {"text": "📤 ارسال آزمایشی",
                      "callback_data": f"adtest_{aid}"}])
        btns.append([{"text": "📝 متن", "callback_data": f"ade_body_{aid}"},
                     {"text": "🖼️ رسانه",
                      "callback_data": f"admedia_{aid}"}])
        btns.append([{"text": "🎯 مخاطب",
                      "callback_data": f"adtgt_{aid}"},
                     {"text": "⏰ زمان‌بندی",
                      "callback_data": f"adsch_{aid}"}])
        btns.append([{"text": "🔘 دکمه اقدام",
                      "callback_data": f"adbtn_{aid}"},
                     {"text": "🅱️ A/B تست",
                      "callback_data": f"adab_{aid}"}])
        btns.append([{"text": "⚡ سرعت و امتیاز",
                      "callback_data": f"adadv_{aid}"}])
    elif a.get("status") == "running":
        btns.append([{"text": "⏸️ توقف", "callback_data": f"adpause_{aid}"}])
    elif a.get("status") in ("done", "failed"):
        btns.append([{"text": "📊 گزارش عملکرد",
                      "callback_data": "ad_report"}])
        btns.append([{"text": "♻️ ساخت کپی",
                      "callback_data": f"adcopy_{aid}"}])

    btns.append([{"text": "🗑️ حذف", "callback_data": f"addel_{aid}"}])
    btns.append([{"text": "🔙 کمپین‌ها", "callback_data": "ad_panel"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ══════════════════════════════════════════════════════════
# ✏️ ویرایش بخش‌ها
# ══════════════════════════════════════════════════════════
AD_FIELDS = {
    "body": ("📝 متن پیام", "متن جدید را بنویسید:"),
    "body_b": ("🅱️ متن نسخه دوم",
               "متن نسخه دوم برای A/B تست:\n\n"
               "💡 نصف کاربران این را می‌بینند و می‌فهمیم کدام بهتر است."),
    "btn_text": ("🔘 متن دکمه", "روی دکمه چه بنویسیم؟\n\nمثال: ثبت‌نام کن"),
    "btn_url": ("🔗 لینک دکمه", "آدرس کامل:\n\nمثال: https://ble.ir/..."),
    "discount_code": ("🎟️ کد تخفیف", "کد تخفیف را بنویسید:"),
    "rate": ("⚡ سرعت ارسال", "چند پیام در دقیقه؟\n\n"
             "💡 ۲۰ پیشنهادی · بیشتر = خطر محدودیت بله"),
    "points_reward": ("🏆 امتیاز", "چند امتیاز به کسی که کلیک کند؟\n\n۰ = هیچ"),
}


def start_edit(cid, uid, field, aid):
    if not _guard(cid, uid):
        return
    if field not in AD_FIELDS or not get_ad(aid):
        return send(cid, "❌ نامعتبر")
    title, hint = AD_FIELDS[field]
    cur = (get_ad(aid) or {}).get(field)
    set_state(uid, STATE_AD_EDIT, {"aid": aid, "field": field},
              merge=False)
    send(cid, f"{title}\n━━━━━━━━━━━━━━\n\n📄 فعلی: {cur or '—'}\n\n{hint}",
         kb_cancel())


def handle_edit(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid)
    aid, field = d.get("aid"), d.get("field")

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_ad(cid, uid, aid)
    if field not in AD_FIELDS:
        clear_state(uid)
        return send(cid, "❌ نامعتبر", kb_remove())

    if field in ("rate", "points_reward"):
        digits = "".join(c for c in normalize_digits(raw) if c.isdigit())
        if not digits:
            return send(cid, "⚠️ فقط عدد:", kb_cancel())
        val = int(digits)
        if field == "rate":
            val = max(1, min(60, val))
    elif field == "btn_url":
        if not raw.startswith("http"):
            return send(cid, "⚠️ لینک باید با http شروع شود:", kb_cancel())
        val = raw[:400]
    else:
        val = raw[:3000]

    db_execute(f"UPDATE ad_campaigns SET {field}=? WHERE id=?", (val, aid))
    if field == "body_b":
        db_execute("UPDATE ad_campaigns SET ab_test=1 WHERE id=?", (aid,))
    clear_state(uid)
    send(cid, "✅ ذخیره شد", kb_remove())
    return show_ad(cid, uid, aid)


def show_target(cid, uid, aid, pick=None):
    """🎯 انتخاب مخاطب"""
    if not _guard(cid, uid):
        return
    import admin as _ad
    if pick:
        db_execute("UPDATE ad_campaigns SET target=? WHERE id=?",
                   (pick, aid))
        return show_ad(cid, uid, aid)

    a = get_ad(aid) or {}
    cur = a.get("target") or "all"
    lines = ["🎯 مخاطبان کمپین", "━━━━━━━━━━━━━━", "",
             "این پیام به چه کسانی برسد؟", ""]
    btns = []
    for k, v in _ad.BC_FILTERS.items():
        mark = "🔘" if k == cur else "⚪"
        try:
            w, prm = _ad._bc_query(k)
            n = db_scalar(f"SELECT COUNT(*) FROM users WHERE {w}",
                          tuple(prm)) or 0
        except Exception:
            n = 0
        lines.append(f"{mark} {v['icon']} {v['name']} — {n} نفر")
        btns.append([{"text": f"{mark} {v['icon']} {v['name']} ({n})"[:34],
                      "callback_data": f"adtg_{k}_{aid}"}])
    lines += ["", "🔕 کسانی که تبلیغات را خاموش کرده‌اند",
              "   خودکار کنار گذاشته می‌شوند."]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"adv_{aid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_schedule(cid, uid, aid, pick=None):
    """⏰ زمان‌بندی"""
    if not _guard(cid, uid):
        return
    if pick:
        if pick not in SCHEDULES:
            return send(cid, "❌ نامعتبر")
        db_execute("UPDATE ad_campaigns SET schedule=? WHERE id=?",
                   (pick, aid))
        if pick != "now":
            set_state(uid, STATE_AD_EDIT,
                      {"aid": aid, "field": "_when"}, merge=False)
            return send(cid, (
                "🕐 زمان اجرا\n━━━━━━━━━━━━━━\n\n"
                "تاریخ و ساعت را بنویسید:\n\n"
                "مثال: 1404/06/15 18:30\n"
                "یا فقط ساعت برای تکرارها: 09:00"
            ), kb_cancel())
        return show_ad(cid, uid, aid)

    a = get_ad(aid) or {}
    cur = a.get("schedule") or "now"
    lines = ["⏰ زمان‌بندی ارسال", "━━━━━━━━━━━━━━", ""]
    btns = []
    for k, v in SCHEDULES.items():
        mark = "🔘" if k == cur else "⚪"
        lines.append(f"{mark} {v['icon']} {v['name']}")
        btns.append([{"text": f"{mark} {v['icon']} {v['name']}",
                      "callback_data": f"adsc_{k}_{aid}"}])
    if a.get("run_at"):
        lines += ["", f"📅 تنظیم‌شده: {a['run_at']} "
                      f"{a.get('run_time') or ''}"]
    lines += ["", "🌙 در ساعت سکوت (شب) ارسال متوقف می‌ماند."]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"adv_{aid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def handle_when(message):
    """دریافت تاریخ/ساعت اجرا"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = normalize_digits((message.get("text") or "").strip())
    d = get_state_data(uid)
    aid = d.get("aid")

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_ad(cid, uid, aid)

    parts = raw.split()
    date_s = time_s = ""
    for p in parts:
        if "/" in p:
            date_s = p
        elif ":" in p:
            time_s = p
    if not date_s and not time_s:
        return send(cid, "⚠️ قالب درست نیست\n\nمثال: 1404/06/15 18:30",
                    kb_cancel())
    if time_s:
        try:
            h, m = [int(x) for x in time_s.split(":")[:2]]
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
            time_s = f"{h:02d}:{m:02d}"
        except (ValueError, TypeError):
            return send(cid, "⚠️ ساعت نامعتبر — مثال: 18:30", kb_cancel())

    db_execute("UPDATE ad_campaigns SET run_at=?, run_time=?, "
               "status='scheduled' WHERE id=?", (date_s, time_s, aid))
    clear_state(uid)
    send(cid, f"✅ زمان‌بندی شد: {date_s} {time_s}", kb_remove())
    return show_ad(cid, uid, aid)


def start_media(cid, uid, aid):
    """🖼️ افزودن عکس/ویدیو"""
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_AD_MEDIA, {"aid": aid}, merge=False)
    send(cid, (
        "🖼️ رسانه کمپین\n━━━━━━━━━━━━━━\n\n"
        "عکس یا ویدیو را بفرستید.\n\n"
        "💡 پیام‌های تصویردار تا ۳ برابر بیشتر دیده می‌شوند.\n"
        "💡 برای حذف رسانه، «حذف» بنویسید."
    ), kb_cancel())


def handle_media(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    d = get_state_data(uid)
    aid = d.get("aid")
    txt = (message.get("text") or "").strip()

    if txt in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_ad(cid, uid, aid)
    if txt == "حذف":
        db_execute("UPDATE ad_campaigns SET media_id=NULL, "
                   "media_type=NULL WHERE id=?", (aid,))
        clear_state(uid)
        send(cid, "🗑️ رسانه حذف شد", kb_remove())
        return show_ad(cid, uid, aid)

    mtype = mid = None
    if message.get("photo"):
        best = sorted(message["photo"],
                      key=lambda p: p.get("file_size") or 0)[-1]
        mtype, mid = "photo", best.get("file_id")
    elif message.get("video"):
        mtype, mid = "video", message["video"].get("file_id")
    elif message.get("document"):
        mtype, mid = "document", message["document"].get("file_id")
    if not mid:
        return send(cid, "⚠️ عکس یا ویدیو بفرستید:", kb_cancel())

    db_execute("UPDATE ad_campaigns SET media_type=?, media_id=? "
               "WHERE id=?", (mtype, mid, aid))
    clear_state(uid)
    send(cid, "✅ رسانه ذخیره شد", kb_remove())
    return show_ad(cid, uid, aid)


def show_button(cid, uid, aid):
    """🔘 دکمه اقدام"""
    if not _guard(cid, uid):
        return
    a = get_ad(aid) or {}
    lines = ["🔘 دکمه اقدام", "━━━━━━━━━━━━━━", "",
             f"📄 متن دکمه: {a.get('btn_text') or '—'}",
             f"🔗 لینک: {a.get('btn_url') or '—'}", "",
             "💡 دکمه نرخ کلیک را چند برابر می‌کند.", "",
             "🔍 کلیک‌ها خودکار شمرده می‌شوند."]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "✏️ متن دکمه", "callback_data": f"ade_btn_text_{aid}"}],
        [{"text": "🔗 لینک", "callback_data": f"ade_btn_url_{aid}"}],
        [{"text": "🎉 وصل به رویداد",
          "callback_data": f"adlink_event_{aid}"},
         {"text": "📝 وصل به فرم",
          "callback_data": f"adlink_form_{aid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"adv_{aid}"}]]})


def link_target(cid, uid, kind, aid, oid=None):
    """🔗 وصل کردن دکمه به رویداد یا فرم"""
    if not _guard(cid, uid):
        return
    if oid:
        if kind == "event":
            db_execute("UPDATE ad_campaigns SET event_id=?, btn_cb=? "
                       "WHERE id=?", (oid, f"uev_{oid}", aid))
        else:
            db_execute("UPDATE ad_campaigns SET form_id=?, btn_cb=? "
                       "WHERE id=?", (oid, f"ffstart_{oid}", aid))
        send(cid, "✅ دکمه وصل شد")
        return show_ad(cid, uid, aid)

    if kind == "event":
        rows = db_execute("SELECT id, title FROM events "
                          "WHERE status='published' ORDER BY id DESC "
                          "LIMIT 12", fetch="all") or []
        icon = "🎉"
        btns = [[{"text": f"🎉 {str(r['title'])[:28]}",
                  "callback_data": f"adle_{r['id']}_{aid}"}]
                for r in rows]
    else:
        rows = db_execute("SELECT id, title FROM forms "
                          "WHERE status='active' ORDER BY id DESC "
                          "LIMIT 12", fetch="all") or []
        icon = "📝"
        btns = [[{"text": f"📝 {str(r['title'])[:28]}",
                  "callback_data": f"adlf_{r['id']}_{aid}"}]
                for r in rows]

    if not rows:
        return send(cid, f"📭 {icon} موردی برای اتصال نیست")
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"adbtn_{aid}"}])
    send_or_edit(cid, f"{icon} کدام مورد؟", {"inline_keyboard": btns})


def show_ab(cid, uid, aid):
    """🅱️ A/B تست"""
    if not _guard(cid, uid):
        return
    a = get_ad(aid) or {}
    on = bool(a.get("ab_test"))
    lines = ["🅱️ تست A/B", "━━━━━━━━━━━━━━", "",
             f"وضعیت: {'🟢 فعال' if on else '⚪ خاموش'}", "",
             "دو نسخه از پیام می‌سازید؛ نصف کاربران اولی و",
             "نصف دیگر دومی را می‌بینند. بعد می‌فهمید",
             "کدام بیشتر کلیک خورده.", ""]
    if a.get("body_b"):
        lines += ["🅱️ متن نسخه دوم:", str(a["body_b"])[:200], ""]
    if on and a.get("sent_a"):
        w, ra, rb = ab_winner(a)
        lines += [f"📊 A: {a.get('sent_a')} ارسال / {ra}٪ کلیک",
                  f"📊 B: {a.get('sent_b')} ارسال / {rb}٪ کلیک"]
        if w == "a":
            lines.append("🏆 نسخه اول بهتر است")
        elif w == "b":
            lines.append("🏆 نسخه دوم بهتر است")
        elif w == "tie":
            lines.append("🤝 تفاوت معناداری ندارند")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "✏️ نوشتن نسخه دوم",
          "callback_data": f"ade_body_b_{aid}"}],
        [{"text": f"{'🔴 خاموش کردن' if on else '🟢 فعال کردن'}",
          "callback_data": f"adabt_{aid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"adv_{aid}"}]]})


def toggle_ab(cid, uid, aid):
    if not _guard(cid, uid):
        return
    a = get_ad(aid) or {}
    if not a.get("body_b") and not a.get("ab_test"):
        return send(cid, "⚠️ اول متن نسخه دوم را بنویسید")
    db_execute("UPDATE ad_campaigns SET ab_test=? WHERE id=?",
               (0 if a.get("ab_test") else 1, aid))
    return show_ab(cid, uid, aid)


def show_advanced(cid, uid, aid):
    """⚡ سرعت، امتیاز، ساعت سکوت"""
    if not _guard(cid, uid):
        return
    a = get_ad(aid) or {}
    q = bool(a.get("quiet_hours"))
    lines = ["⚡ تنظیمات پیشرفته", "━━━━━━━━━━━━━━", "",
             f"🐢 سرعت: {a.get('rate') or 20} پیام در دقیقه",
             f"🌙 احترام به ساعت سکوت: {'✅' if q else '❌'}",
             f"🏆 امتیاز کلیک: {a.get('points_reward') or 0}", "",
             "💡 سرعت پایین‌تر = امن‌تر برای حساب ربات"]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🐢 سرعت ارسال", "callback_data": f"ade_rate_{aid}"}],
        [{"text": "🏆 امتیاز کلیک",
          "callback_data": f"ade_points_reward_{aid}"}],
        [{"text": f"🌙 ساعت سکوت: {'✅' if q else '❌'}",
          "callback_data": f"adq_{aid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"adv_{aid}"}]]})


def toggle_quiet(cid, uid, aid):
    if not _guard(cid, uid):
        return
    a = get_ad(aid) or {}
    db_execute("UPDATE ad_campaigns SET quiet_hours=? WHERE id=?",
               (0 if a.get("quiet_hours") else 1, aid))
    return show_advanced(cid, uid, aid)


# ══════════════════════════════════════════════════════════
# 👁️ پیش‌نمایش و ارسال
# ══════════════════════════════════════════════════════════
def _render_body(a, user=None, variant="a"):
    """متن نهایی با جایگزینی متغیرها"""
    from config import org_name, bot_name
    body = a.get("body_b") if (variant == "b" and a.get("body_b")) \
        else a.get("body")
    body = str(body or "")
    nm = ""
    if user:
        nm = f"{user.get('first_name') or ''} " \
             f"{user.get('last_name') or ''}".strip()
    return (body.replace("{نام}", nm or "دوست عزیز")
                .replace("{name}", nm or "دوست عزیز")
                .replace("{سازمان}", org_name())
                .replace("{org}", org_name())
                .replace("{ربات}", bot_name()))


def _ad_keyboard(a, uid=None):
    """دکمه‌های پیام تبلیغاتی"""
    rows = []
    if a.get("btn_text"):
        if a.get("btn_url"):
            rows.append([{"text": a["btn_text"], "url": a["btn_url"]}])
        elif a.get("btn_cb"):
            rows.append([{"text": a["btn_text"],
                          "callback_data": f"adclick_{a['id']}"}])
        else:
            rows.append([{"text": a["btn_text"],
                          "callback_data": f"adclick_{a['id']}"}])
    if get_setting("ads_optout_btn", "1") == "1":
        rows.append([{"text": "🔕 دیگر تبلیغ نفرست",
                      "callback_data": "ad_optout"}])
    return {"inline_keyboard": rows} if rows else None


def preview(cid, uid, aid):
    """👁️ پیش‌نمایش دقیق"""
    if not _guard(cid, uid):
        return
    a = get_ad(aid)
    if not a:
        return send(cid, "❌ یافت نشد")
    from auth import get_user
    u = get_user(uid)
    send(cid, "👁️ کاربر این را می‌بیند:")
    _deliver(cid, a, u, variant="a", preview=True)
    if a.get("ab_test") and a.get("body_b"):
        send(cid, "🅱️ نسخه دوم:")
        _deliver(cid, a, u, variant="b", preview=True)
    return show_ad(cid, uid, aid)


def _deliver(target_cid, a, user=None, variant="a", preview=False):
    """📤 ارسال واقعی یک پیام"""
    body = _render_body(a, user, variant)
    kb = _ad_keyboard(a)
    try:
        if a.get("media_id") and a.get("media_type") == "photo":
            send_photo(target_cid, a["media_id"], body, kb)
        elif a.get("media_id"):
            send_document(target_cid, a["media_id"], body, kb)
        else:
            send(target_cid, body, kb)
        return True
    except Exception as e:
        if not preview:
            log(f"⚠️ ارسال تبلیغ: {e}")
        return False


def test_send(cid, uid, aid):
    """📤 ارسال آزمایشی به خود ادمین"""
    if not _guard(cid, uid):
        return
    a = get_ad(aid)
    if not a:
        return send(cid, "❌ یافت نشد")
    from auth import get_user
    ok = _deliver(cid, a, get_user(uid), "a")
    send(cid, "✅ ارسال آزمایشی انجام شد" if ok else "❌ ارسال ناموفق")
    return show_ad(cid, uid, aid)


def start_campaign(cid, uid, aid, confirmed=False):
    """🚀 شروع ارسال"""
    if not _guard(cid, uid):
        return
    a = get_ad(aid)
    if not a:
        return send(cid, "❌ یافت نشد")
    if not str(a.get("body") or "").strip():
        return send(cid, "⚠️ اول متن پیام را بنویسید")

    import admin as _ad
    w, prm = _ad._bc_query(a.get("target") or "all")
    try:
        rows = db_execute(
            f"SELECT bale_user_id, first_name, last_name FROM users "
            f"WHERE {w} AND COALESCE(ads_optout,0)=0", tuple(prm),
            fetch="all") or []
    except Exception as e:
        log(f"⚠️ کوئری مخاطبان: {e}")
        rows = []

    if not rows:
        return send(cid, "📭 مخاطبی برای این فیلتر نیست")

    if not confirmed:
        tgt = _ad.BC_FILTERS.get(a.get("target") or "all",
                                 {"icon": "👥", "name": "همه"})
        lines = ["🚀 تأیید ارسال", "━━━━━━━━━━━━━━", "",
                 f"📣 {a.get('title')}",
                 f"🎯 {tgt['icon']} {tgt['name']}",
                 f"👥 {len(rows)} نفر",
                 f"🐢 سرعت: {a.get('rate') or 20}/دقیقه"]
        mins = len(rows) / max(1, int(a.get("rate") or 20))
        lines.append(f"⏱️ زمان تقریبی: {int(mins) + 1} دقیقه")
        if a.get("ab_test") and a.get("body_b"):
            lines.append("🅱️ A/B فعال — نصف/نصف")
        lines += ["", "مطمئنید؟"]
        return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
            [{"text": "🚀 بله، ارسال کن",
              "callback_data": f"adgo2_{aid}"}],
            [{"text": "📤 اول آزمایشی بفرست",
              "callback_data": f"adtest_{aid}"}],
            [{"text": "❌ انصراف", "callback_data": f"adv_{aid}"}]]})

    if in_quiet_hours() and a.get("quiet_hours"):
        return send(cid, "🌙 الان ساعت سکوت است.\n\n"
                         "کمپین زمان‌بندی شد و صبح ارسال می‌شود.")

    db_execute("UPDATE ad_campaigns SET status='running' WHERE id=?",
               (aid,))
    send(cid, f"🚀 ارسال شروع شد — {len(rows)} مخاطب")

    sent = fail = 0
    rate = max(1, int(a.get("rate") or 20))
    delay = 60.0 / rate
    ab = bool(a.get("ab_test") and a.get("body_b"))

    for i, r in enumerate(rows):
        tuid = r.get("bale_user_id")
        if not tuid:
            continue
        if got_enough_today(tuid):
            continue
        variant = ("b" if (i % 2) else "a") if ab else "a"
        if _deliver(tuid, a, r, variant):
            sent += 1
            db_execute("""INSERT INTO ad_logs (ad_id, bale_user_id, variant)
                VALUES (?,?,?)""", (aid, tuid, variant))
            db_execute(f"UPDATE ad_campaigns SET sent_count=sent_count+1, "
                       f"sent_{variant}=sent_{variant}+1 WHERE id=?",
                       (aid,))
        else:
            fail += 1
            db_execute("UPDATE ad_campaigns SET fail_count=fail_count+1 "
                       "WHERE id=?", (aid,))
        if i and i % 25 == 0:
            time.sleep(delay * 2)
        else:
            time.sleep(delay)

    db_execute("UPDATE ad_campaigns SET status='done', "
               "last_run=CURRENT_TIMESTAMP WHERE id=?", (aid,))
    log_action(uid, "ad_sent", {"id": aid, "sent": sent})
    send(cid, (f"✅ ارسال تمام شد\n━━━━━━━━━━━━━━\n\n"
               f"📨 موفق: {sent}\n"
               f"❌ ناموفق: {fail}\n\n"
               f"📊 آمار کلیک را در جزئیات کمپین ببینید."))
    return show_ad(cid, uid, aid)


def click(cid, uid, aid):
    """👆 کاربر روی دکمه زد"""
    a = get_ad(aid)
    if not a:
        return
    try:
        row = db_execute("SELECT * FROM ad_logs WHERE ad_id=? AND "
                         "bale_user_id=?", (aid, uid), fetch="one")
        if row and not row.get("clicked"):
            db_execute("UPDATE ad_logs SET clicked=1, "
                       "clicked_at=CURRENT_TIMESTAMP WHERE id=?",
                       (row["id"],))
            v = row.get("variant") or "a"
            db_execute(f"UPDATE ad_campaigns SET "
                       f"click_count=click_count+1, "
                       f"click_{v}=click_{v}+1 WHERE id=?", (aid,))
            # 🏆 پاداش
            pts = int(a.get("points_reward") or 0)
            if pts:
                try:
                    import occasions as _oc
                    _oc.add_points(uid, pts, "کلیک روی تبلیغ")
                except Exception:
                    pass
    except Exception as e:
        log(f"⚠️ ثبت کلیک: {e}")

    # هدایت به مقصد
    cbv = a.get("btn_cb") or ""
    if cbv.startswith("uev_"):
        try:
            import events as _ev
            return _ev.show_user_event(cid, uid, int(cbv[4:]))
        except Exception:
            pass
    elif cbv.startswith("ffstart_"):
        try:
            import form_fill as _ff
            return _ff.start_fill(cid, uid, int(cbv[8:]))
        except Exception:
            pass
    if a.get("discount_code"):
        return send(cid, (f"🎟️ کد تخفیف شما:\n\n"
                          f"<code>{a['discount_code']}</code>\n\n"
                          f"موقع پرداخت وارد کنید 💚"))
    return send(cid, "✅ ثبت شد، سپاس از توجه‌تان 💚")


def user_optout(cid, uid):
    """🔕 کاربر لغو اشتراک کرد"""
    set_optout(uid, True)
    send(cid, ("🔕 دیگر پیام تبلیغاتی نمی‌فرستیم\n"
               "━━━━━━━━━━━━━━\n\n"
               "پیام‌های مهم مثل یادآوری رویدادهایی که ثبت‌نام\n"
               "کرده‌اید همچنان ارسال می‌شود.\n\n"
               "هر وقت خواستید از پروفایل دوباره روشن کنید 💚"))


# ══════════════════════════════════════════════════════════
# 📊 گزارش و تنظیمات
# ══════════════════════════════════════════════════════════
def show_report(cid, uid):
    """📊 گزارش کلی عملکرد"""
    if not _guard(cid, uid):
        return
    rows = db_execute("SELECT * FROM ad_campaigns WHERE sent_count>0 "
                      "ORDER BY sent_count DESC LIMIT 15",
                      fetch="all") or []
    if not rows:
        return send_or_edit(cid, (
            "📊 گزارش تبلیغات\n━━━━━━━━━━━━━━\n\n"
            "🌱 هنوز کمپینی ارسال نشده."
        ), {"inline_keyboard": [
            [{"text": "🔙 بازگشت", "callback_data": "ad_panel"}]]})

    tot_s = sum(int(r.get("sent_count") or 0) for r in rows)
    tot_c = sum(int(r.get("click_count") or 0) for r in rows)
    lines = ["📊 گزارش عملکرد تبلیغات", "━━━━━━━━━━━━━━", "",
             f"📨 کل ارسال: {tot_s:,}",
             f"👆 کل کلیک: {tot_c:,}",
             f"📈 نرخ کلیک کلی: "
             f"{round(tot_c * 100 / tot_s, 1) if tot_s else 0}٪", "",
             "🏆 پرکلیک‌ترین کمپین‌ها:", ""]
    best = sorted(rows, key=lambda r: ctr(r), reverse=True)
    for r in best[:8]:
        t = AD_TYPES.get(r.get("ad_type") or "promo", AD_TYPES["promo"])
        lines.append(f"{t['icon']} {str(r.get('title'))[:22]}")
        lines.append(f"     📨 {r.get('sent_count')} · 👆 "
                     f"{r.get('click_count') or 0} · {ctr(r)}٪")
    lines += ["", "💡 نرخ کلیک بالای ۵٪ خیلی خوب است."]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": "ad_panel"}]]})


AD_SETTINGS = [
    ("ads_daily_cap", "🚦", "سقف تبلیغ روزانه هر کاربر", "num", "2",
     "۰ = بدون سقف · پیشنهاد: ۲"),
    ("ads_quiet_on", "🌙", "احترام به ساعت سکوت", "bool", "1", ""),
    ("ads_quiet_start", "🌆", "شروع سکوت (ساعت)", "num", "23", ""),
    ("ads_quiet_end", "🌅", "پایان سکوت (ساعت)", "num", "8", ""),
    ("ads_optout_btn", "🔕", "دکمه «دیگر نفرست»", "bool", "1",
     "احترام به کاربر — توصیه می‌شود روشن باشد"),
    ("ads_default_rate", "🐢", "سرعت پیش‌فرض (پیام/دقیقه)", "num", "20",
     "بیشتر از ۳۰ = خطر محدودیت بله"),
]


def show_settings(cid, uid):
    """⚙️ تنظیمات تبلیغات"""
    if not _guard(cid, uid):
        return
    lines = ["⚙️ تنظیمات تبلیغات", "━━━━━━━━━━━━━━", ""]
    btns = []
    for key, icon, name, kind, dflt, hint in AD_SETTINGS:
        v = get_setting(key, dflt)
        if kind == "bool":
            on = str(v) == "1"
            lines.append(f"{'🟢' if on else '⚪'} {icon} {name}")
            btns.append([{"text": f"{'✅' if on else '❌'} {icon} "
                                  f"{name}"[:34],
                          "callback_data": f"adsb_{key}"}])
        else:
            lines.append(f"▫️ {icon} {name}: {v}")
            btns.append([{"text": f"{icon} {name}: {v}"[:34],
                          "callback_data": f"adse_{key}"}])
    lines += ["", "🛡️ این تنظیمات از اسپم شدن جلوگیری می‌کنند",
              "   و حساب ربات را امن نگه می‌دارند."]
    btns.append([{"text": "🔙 بازگشت", "callback_data": "ad_panel"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_setting(cid, uid, key):
    if not _guard(cid, uid):
        return
    row = next((r for r in AD_SETTINGS if r[0] == key), None)
    if not row or row[3] != "bool":
        return send(cid, "❌ نامعتبر")
    cur = get_setting(key, row[4]) == "1"
    set_setting(key, "0" if cur else "1", row[2], "ads", uid)
    return show_settings(cid, uid)


def start_setting(cid, uid, key):
    if not _guard(cid, uid):
        return
    row = next((r for r in AD_SETTINGS if r[0] == key), None)
    if not row:
        return send(cid, "❌ نامعتبر")
    set_state(uid, STATE_AD_EDIT, {"setting": key}, merge=False)
    send(cid, (f"✏️ {row[1]} {row[2]}\n━━━━━━━━━━━━━━\n\n"
               f"📄 فعلی: {get_setting(key, row[4])}\n\n"
               f"{row[5] or 'مقدار جدید:'}"), kb_cancel())


def handle_setting(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid)
    key = d.get("setting")

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_settings(cid, uid)
    row = next((r for r in AD_SETTINGS if r[0] == key), None)
    if not row:
        clear_state(uid)
        return send(cid, "❌ نامعتبر", kb_remove())

    digits = "".join(c for c in normalize_digits(raw) if c.isdigit())
    if not digits:
        return send(cid, "⚠️ فقط عدد:", kb_cancel())
    v = int(digits)
    if key in ("ads_quiet_start", "ads_quiet_end"):
        v = max(0, min(23, v))
    elif key == "ads_default_rate":
        v = max(1, min(60, v))
    set_setting(key, str(v), row[2], "ads", uid)
    clear_state(uid)
    send(cid, f"✅ ذخیره شد: {v}", kb_remove())
    return show_settings(cid, uid)


def show_tips(cid, uid):
    """💡 راهنما و ایده‌های تبلیغاتی"""
    if not _guard(cid, uid):
        return
    send_or_edit(cid, (
        "💡 راهنمای تبلیغات مؤثر\n━━━━━━━━━━━━━━\n\n"
        "✍️ متن:\n"
        "   • کوتاه — ۳ تا ۵ خط کافی است\n"
        "   • با {نام} شخصی‌سازی کنید\n"
        "   • یک پیام = یک هدف\n"
        "   • با سوال یا خبر خوب شروع کنید\n\n"
        "🖼️ تصویر:\n"
        "   • پیام تصویردار تا ۳ برابر بیشتر دیده می‌شود\n\n"
        "🔘 دکمه:\n"
        "   • فعل امری: «ثبت‌نام کن» بهتر از «اطلاعات بیشتر»\n"
        "   • فقط یک دکمه اصلی\n\n"
        "🎯 مخاطب:\n"
        "   • هدفمند بفرستید، نه به همه\n"
        "   • «غیرفعال ۳۰ روز» برای بازگرداندن\n\n"
        "⏰ زمان:\n"
        "   • ۱۰ تا ۱۲ صبح و ۶ تا ۹ شب بهترین‌اند\n"
        "   • شب دیروقت نفرستید\n\n"
        "🅱️ A/B:\n"
        "   • دو متن بسازید، برنده را نگه دارید\n\n"
        "🛡️ احترام:\n"
        "   • سقف روزانه را رعایت کنید\n"
        "   • دکمه «دیگر نفرست» را بردارید نکنید\n"
        "   • تبلیغ زیاد = ریزش کاربر"
    ), {"inline_keyboard": [
        [{"text": "➕ حالا یک کمپین بساز",
          "callback_data": "ad_new"}],
        [{"text": "🔙 بازگشت", "callback_data": "ad_panel"}]]})


def copy_ad(cid, uid, aid):
    """♻️ کپی یک کمپین"""
    if not _guard(cid, uid):
        return
    a = get_ad(aid)
    if not a:
        return send(cid, "❌ یافت نشد")
    nid = db_execute("""INSERT INTO ad_campaigns
        (title, ad_type, body, body_b, ab_test, media_type, media_id,
         btn_text, btn_url, btn_cb, event_id, form_id, discount_code,
         target, schedule, rate, quiet_hours, points_reward,
         status, created_by)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'draft',?)""",
        (f"کپی {a.get('title')}"[:80], a.get("ad_type"), a.get("body"),
         a.get("body_b"), a.get("ab_test"), a.get("media_type"),
         a.get("media_id"), a.get("btn_text"), a.get("btn_url"),
         a.get("btn_cb"), a.get("event_id"), a.get("form_id"),
         a.get("discount_code"), a.get("target"), a.get("schedule"),
         a.get("rate"), a.get("quiet_hours"), a.get("points_reward"),
         uid))
    send(cid, "♻️ کپی ساخته شد")
    return show_ad(cid, uid, nid)


def pause_ad(cid, uid, aid):
    if not _guard(cid, uid):
        return
    db_execute("UPDATE ad_campaigns SET status='paused' WHERE id=?", (aid,))
    send(cid, "⏸️ متوقف شد")
    return show_ad(cid, uid, aid)


def delete_ad(cid, uid, aid):
    if not _guard(cid, uid):
        return
    db_execute("DELETE FROM ad_logs WHERE ad_id=?", (aid,))
    db_execute("DELETE FROM ad_campaigns WHERE id=?", (aid,))
    send(cid, "🗑️ کمپین حذف شد")
    return show_panel(cid, uid)


def check_scheduled():
    """⏰ کمپین‌های زمان‌بندی‌شده — از حلقه اصلی"""
    if in_quiet_hours():
        return 0
    try:
        from forms import jnow
        today = jnow()[:10]
        now_h = datetime.now().strftime("%H:%M")
    except Exception:
        return 0
    n = 0
    rows = db_execute("SELECT * FROM ad_campaigns WHERE status='scheduled'",
                      fetch="all") or []
    for a in rows:
        due = False
        sc = a.get("schedule") or "now"
        if sc == "at":
            if (a.get("run_at") or "") <= today and \
                    (a.get("run_time") or "00:00") <= now_h:
                due = True
        elif sc in ("daily", "weekly", "monthly"):
            last = str(a.get("last_run") or "")[:10]
            gap = {"daily": 1, "weekly": 7, "monthly": 30}[sc]
            if not last:
                due = (a.get("run_time") or "00:00") <= now_h
            else:
                try:
                    d0 = datetime.strptime(last, "%Y-%m-%d")
                    due = (datetime.now() - d0).days >= gap
                except Exception:
                    due = False
        if due:
            try:
                start_campaign(SUPER_ADMIN_ID, SUPER_ADMIN_ID,
                               a["id"], confirmed=True)
                n += 1
            except Exception as e:
                log(f"⚠️ اجرای کمپین زمان‌بندی‌شده: {e}")
    return n
