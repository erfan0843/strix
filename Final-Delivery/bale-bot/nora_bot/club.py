"""
🏅 باشگاه کاربران — فاز ۱۲

  • دستاوردها (Achievements) با نوار پیشرفت
  • فروشگاه پاداش (خرید با امتیاز)
  • جدول رتبه‌بندی (کلی / ماهانه / حضور / دعوت)

⚠️ متناسب با نظام امتیازدهی سخت‌گیرانه فاز ۱۲:
   چون امتیاز کمیاب است، قیمت‌های فروشگاه هم پایین نگه داشته شده.
"""
import json
import random
import string
from datetime import datetime

from config import SUPER_ADMIN_ID, CURRENCY_LABEL, money
from database import (
    db_execute, db_scalar, ensure_table, get_setting, set_setting, log,
)
from auth import (
    get_user, set_state, get_state_data, clear_state, log_action,
    normalize_digits, is_admin as _is_admin,
)
from bale_api import send, send_or_edit, kb_cancel, kb_remove, BTN_BACK
import permissions as perm
import jalali as _jd

STATE_CLUB_ADD = "club_add"
STATE_CLUB_EDIT = "club_edit"


# ==================== 🎖️ دستاوردها ====================
"""
هر دستاورد یک شرط دارد (مثل قوانین امتیاز) و وقتی برآورده شد
نشان + امتیاز می‌گیرد. سخت‌گیرانه طراحی شده.
"""
ACHIEVEMENT_SCHEMA = {
    "key": "TEXT",
    "icon": "TEXT DEFAULT '🎖️'",
    "title": "TEXT NOT NULL",
    "description": "TEXT",
    "trigger": "TEXT NOT NULL",
    "threshold": "INTEGER DEFAULT 1",
    "points": "INTEGER DEFAULT 0",
    "tier": "TEXT DEFAULT 'bronze'",
    "is_active": "INTEGER DEFAULT 1",
    "is_secret": "INTEGER DEFAULT 0",
    "total_earned": "INTEGER DEFAULT 0",
    "created_by": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

USER_ACHIEVEMENT_SCHEMA = {
    "bale_user_id": "INTEGER NOT NULL",
    "achievement_key": "TEXT NOT NULL",
    "points_given": "INTEGER DEFAULT 0",
    "earned_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

TIERS = {
    "bronze": {"icon": "🥉", "name": "برنزی"},
    "silver": {"icon": "🥈", "name": "نقره‌ای"},
    "gold":   {"icon": "🥇", "name": "طلایی"},
    "legend": {"icon": "💎", "name": "افسانه‌ای"},
}

# 🔴 سخت‌گیرانه — دستاورد باید واقعاً سخت باشد
DEFAULT_ACHIEVEMENTS = [
    # برنزی — شروع مسیر
    ("first_step", "👣", "اولین قدم", "در اولین رویداد حاضر شدی",
     "event_attend", 1, 5, "bronze"),
    ("profile_pro", "👤", "پروفایل کامل", "همه اطلاعات پروفایلت را پر کردی",
     "profile_complete", 100, 5, "bronze"),
    ("first_form", "📝", "پاسخ‌گو", "اولین فرم را تکمیل کردی",
     "form_submit", 1, 5, "bronze"),

    # نقره‌ای — تعهد
    ("regular", "🔥", "پرحضور", "در ۱۰ رویداد حاضر شدی",
     "event_attend", 10, 15, "silver"),
    ("friend_maker", "👥", "دوست‌ساز", "۱۰ نفر را دعوت کردی",
     "invite_friend", 10, 20, "silver"),
    ("scholar", "🎓", "دانش‌آموز نمونه", "۵ گواهینامه گرفتی",
     "certificate", 5, 15, "silver"),
    ("form_master", "📋", "فرم‌شناس", "۱۰ فرم را تکمیل کردی",
     "form_submit", 10, 10, "silver"),

    # طلایی — وفاداری
    ("loyal", "🏅", "وفادار", "در ۳۰ رویداد حاضر شدی",
     "event_attend", 30, 40, "gold"),
    ("ambassador", "🌟", "سفیر", "۳۰ نفر را دعوت کردی",
     "invite_friend", 30, 50, "gold"),
    ("collector", "🎓", "گواهینامه‌جمع", "۱۵ گواهینامه گرفتی",
     "certificate", 15, 40, "gold"),
    ("supporter", "💰", "حامی برتر", "۱۰ بار پرداخت موفق داشتی",
     "payment_done", 10, 30, "gold"),

    # افسانه‌ای — نادر
    ("legend_100", "💎", "افسانه", "در ۱۰۰ رویداد حاضر شدی",
     "event_attend", 100, 100, "legend"),
    ("legend_inviter", "👑", "بنیان‌گذار", "۱۰۰ نفر را دعوت کردی",
     "invite_friend", 100, 100, "legend"),
]


# ==================== 🛍️ فروشگاه پاداش ====================
REWARD_SCHEMA = {
    "key": "TEXT",
    "icon": "TEXT DEFAULT '🎁'",
    "title": "TEXT NOT NULL",
    "description": "TEXT",
    "cost": "INTEGER DEFAULT 0",
    "reward_type": "TEXT DEFAULT 'custom'",
    "reward_value": "TEXT",
    "stock": "INTEGER DEFAULT 0",
    "sold": "INTEGER DEFAULT 0",
    "per_user_limit": "INTEGER DEFAULT 1",
    "is_active": "INTEGER DEFAULT 1",
    "created_by": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

REDEEM_SCHEMA = {
    "bale_user_id": "INTEGER NOT NULL",
    "reward_key": "TEXT NOT NULL",
    "reward_title": "TEXT",
    "cost": "INTEGER DEFAULT 0",
    "code": "TEXT",
    "status": "TEXT DEFAULT 'pending'",
    "admin_note": "TEXT",
    "handled_by": "INTEGER",
    "handled_at": "TEXT",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

REWARD_TYPES = {
    "vip":      {"icon": "⭐", "name": "عضویت VIP", "auto": 1,
                 "desc": "کاربر خودکار VIP می‌شود (روز)"},
    "discount": {"icon": "🎫", "name": "کد تخفیف", "auto": 1,
                 "desc": "کد تخفیف درصدی ساخته می‌شود"},
    "custom":   {"icon": "🎁", "name": "جایزه دستی", "auto": 0,
                 "desc": "ادمین دستی تحویل می‌دهد"},
}

# 🔴 قیمت‌ها متناسب با امتیاز کمیاب (سقف ماهانه ۳۰۰)
DEFAULT_REWARDS = [
    ("disc10", "🎫", "کد تخفیف ۱۰٪", "برای ثبت‌نام بعدی",
     60, "discount", "10"),
    ("disc20", "🎟️", "کد تخفیف ۲۰٪", "برای ثبت‌نام بعدی",
     120, "discount", "20"),
    ("vip30", "⭐", "عضویت VIP یک ماهه", "دسترسی به رویدادهای ویژه",
     250, "vip", "30"),
    ("book", "📚", "کتاب هدیه", "یک جلد کتاب از انتشارات گروه",
     200, "custom", ""),
    ("free_ticket", "🎫", "بلیت رایگان", "ثبت‌نام رایگان در یک رویداد",
     300, "custom", ""),
]


def init_club_tables():
    ensure_table("achievements", ACHIEVEMENT_SCHEMA)
    ensure_table("user_achievements", USER_ACHIEVEMENT_SCHEMA)
    ensure_table("rewards", REWARD_SCHEMA)
    ensure_table("reward_redemptions", REDEEM_SCHEMA)
    for q in [
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_ach ON achievements(key)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_uach ON user_achievements"
        "(bale_user_id, achievement_key)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_rw ON rewards(key)",
        "CREATE INDEX IF NOT EXISTS idx_redeem ON reward_redemptions"
        "(bale_user_id, status)",
    ]:
        db_execute(q)

    for k, ic, t, d, trg, thr, pts, tier in DEFAULT_ACHIEVEMENTS:
        if not db_execute("SELECT id FROM achievements WHERE key=?", (k,),
                          fetch="one"):
            db_execute("""INSERT INTO achievements
                (key, icon, title, description, trigger, threshold, points, tier)
                VALUES (?,?,?,?,?,?,?,?)""", (k, ic, t, d, trg, thr, pts, tier))

    for k, ic, t, d, cost, rt, rv in DEFAULT_REWARDS:
        if not db_execute("SELECT id FROM rewards WHERE key=?", (k,), fetch="one"):
            db_execute("""INSERT INTO rewards
                (key, icon, title, description, cost, reward_type, reward_value)
                VALUES (?,?,?,?,?,?,?)""", (k, ic, t, d, cost, rt, rv))

    log("✅ جدول‌های باشگاه آماده شد")


def _guard(cid, uid):
    if not _is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    return True


def _progress(uid, trigger, threshold):
    """پیشرفت کاربر — از موتور امتیاز شرطی استفاده می‌کند"""
    import occasions as oc
    have = oc._rule_progress(uid, trigger)
    pct = int(min(100, have * 100 / threshold)) if threshold else 0
    return have, pct


def _bar(pct, width=10):
    blocks = max(0, min(width, int(pct * width / 100)))
    return "▓" * blocks + "░" * (width - blocks)


# ==================== بررسی و اعطای دستاورد ====================
def check_achievements(uid, trigger=None, silent=False):
    """
    🎖️ بررسی دستاوردها و اعطای نشان.
    بعد از هر فعالیت مهم صدا زده می‌شود.
    خروجی: (تعداد نشان جدید، مجموع امتیاز)
    """
    if get_setting("club_enabled", "1") != "1":
        return 0, 0

    where = "is_active=1"
    params = []
    if trigger:
        where += " AND trigger=?"
        params.append(trigger)
    rows = db_execute(f"SELECT * FROM achievements WHERE {where}",
                      tuple(params), fetch="all") or []
    if not rows:
        return 0, 0

    u = get_user(uid)
    if not u:
        return 0, 0

    import occasions as oc
    n_new = total = 0
    for a in rows:
        key = a.get("key")
        if db_execute("SELECT id FROM user_achievements WHERE bale_user_id=? "
                      "AND achievement_key=?", (uid, key), fetch="one"):
            continue

        have, _ = _progress(uid, a.get("trigger"), int(a.get("threshold") or 1))
        if have < int(a.get("threshold") or 1):
            continue

        pts, why = oc.cap_points(uid, a.get("points"))
        db_execute("""INSERT OR IGNORE INTO user_achievements
            (bale_user_id, achievement_key, points_given) VALUES (?,?,?)""",
            (uid, key, pts))
        if pts:
            db_execute("UPDATE users SET total_points=COALESCE(total_points,0)+? "
                       "WHERE bale_user_id=?", (pts, uid))
            db_execute("""INSERT OR IGNORE INTO greeting_log
                (bale_user_id, kind, ref_key, jyear, points_given)
                VALUES (?,'achievement',?,0,?)""", (uid, key, pts))
        db_execute("UPDATE achievements SET total_earned="
                   "COALESCE(total_earned,0)+1 WHERE id=?", (a["id"],))

        if not silent:
            tier = TIERS.get(a.get("tier") or "bronze", TIERS["bronze"])
            try:
                dear = oc.polite_name(u)
            except Exception:
                dear = "دوست عزیز"
            txt = (
                f"🎖️ نشان جدید گرفتی، {dear}!\n"
                f"━━━━━━━━━━━━━━\n\n"
                f"{a.get('icon') or '🎖️'} {a.get('title')}\n"
                f"{tier['icon']} سطح {tier['name']}\n\n"
                f"📄 {a.get('description') or ''}\n"
            )
            if pts:
                txt += f"\n🎁 {pts} امتیاز پاداش گرفتی!"
            elif why:
                txt += f"\n⚠️ {why}"
            try:
                send(uid, txt)
            except Exception as e:
                log(f"⚠️ ارسال نشان: {e}")

        log_action(uid, "achievement", {"key": key, "points": pts})
        n_new += 1
        total += pts
    return n_new, total


# ==================== 🎖️ نمای کاربر: دستاوردها ====================
def show_my_achievements(cid, uid):
    """🎖️ دستاوردهای من"""
    u = get_user(uid)
    if not u:
        return send(cid, "⚠️ ابتدا /start را بزنید")

    earned = db_execute("""SELECT a.*, ua.earned_at, ua.points_given
        FROM user_achievements ua
        JOIN achievements a ON a.key = ua.achievement_key
        WHERE ua.bale_user_id=? ORDER BY ua.id DESC""", (uid,), fetch="all") or []
    all_a = db_execute("SELECT * FROM achievements WHERE is_active=1 "
                       "ORDER BY threshold", fetch="all") or []
    got = {e["key"] for e in earned}

    lines = [f"🎖️ دستاوردهای من ({len(earned)}/{len(all_a)})",
             "━━━━━━━━━━━━━━", ""]

    if earned:
        lines.append("✅ کسب‌شده:")
        for e in earned:
            t = TIERS.get(e.get("tier") or "bronze", TIERS["bronze"])
            lines.append(f"   {e.get('icon')} {e.get('title')} {t['icon']}")
        lines.append("")

    # سه دستاورد بعدی با نوار پیشرفت
    nxt = []
    for a in all_a:
        if a["key"] in got or a.get("is_secret"):
            continue
        have, pct = _progress(uid, a.get("trigger"), int(a.get("threshold") or 1))
        nxt.append((pct, have, a))
    nxt.sort(key=lambda x: -x[0])

    if nxt:
        lines.append("⭐ دستاوردهای بعدی:")
        for pct, have, a in nxt[:4]:
            lines.append(f"\n{a.get('icon')} {a.get('title')}")
            lines.append(f"   {have}/{a.get('threshold')}")
            lines.append(f"   {_bar(pct)} {pct}%")
        lines.append("")

    lines.append(f"🏆 امتیاز فعلی شما: {u.get('total_points') or 0}")

    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "📋 همه دستاوردها", "callback_data": "cl_all"}],
        [{"text": "🛍️ فروشگاه پاداش", "callback_data": "cl_shop"}],
        [{"text": "🏆 جدول رتبه‌بندی", "callback_data": "cl_board"}],
        [{"text": "🔙 پروفایل", "callback_data": "profile_view"}],
    ]})


def show_all_achievements(cid, uid):
    """📋 فهرست کامل دستاوردها"""
    rows = db_execute("SELECT * FROM achievements WHERE is_active=1 "
                      "ORDER BY tier, threshold", fetch="all") or []
    got = {r["achievement_key"] for r in db_execute(
        "SELECT achievement_key FROM user_achievements WHERE bale_user_id=?",
        (uid,), fetch="all") or []}

    lines = [f"📋 همه دستاوردها ({len(got)}/{len(rows)})", "━━━━━━━━━━━━━━", ""]
    by_tier = {}
    for r in rows:
        by_tier.setdefault(r.get("tier") or "bronze", []).append(r)

    for tk in ("bronze", "silver", "gold", "legend"):
        items = by_tier.get(tk) or []
        if not items:
            continue
        t = TIERS[tk]
        lines.append(f"{t['icon']} سطح {t['name']}:")
        for a in items:
            if a.get("is_secret") and a["key"] not in got:
                lines.append("   🔒 ??? (مخفی)")
                continue
            mark = "✅" if a["key"] in got else "⬜"
            lines.append(f"   {mark} {a.get('icon')} {a.get('title')}"
                         + (f" — {a.get('points')} امتیاز" if a.get("points") else ""))
            if a["key"] not in got and a.get("description"):
                lines.append(f"      {a['description']}")
        lines.append("")

    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🎖️ دستاوردهای من", "callback_data": "cl_my"}],
        [{"text": "🔙 بازگشت", "callback_data": "profile_view"}]]})


# ==================== 🛍️ فروشگاه پاداش ====================
def show_shop(cid, uid):
    """🛍️ فروشگاه پاداش"""
    if get_setting("shop_enabled", "1") != "1":
        return send_or_edit(cid, (
            "🛍️ فروشگاه پاداش\n━━━━━━━━━━━━━━\n\n"
            "🚧 فروشگاه موقتاً بسته است."
        ), {"inline_keyboard": [
            [{"text": "🔙 بازگشت", "callback_data": "profile_view"}]]})

    u = get_user(uid)
    if not u:
        return send(cid, "⚠️ ابتدا /start را بزنید")
    pts = int(u.get("total_points") or 0)

    rows = db_execute("SELECT * FROM rewards WHERE is_active=1 ORDER BY cost",
                      fetch="all") or []
    lines = ["🛍️ فروشگاه پاداش", "━━━━━━━━━━━━━━", "",
             f"🏆 امتیاز شما: {pts}", ""]
    btns = []
    if rows:
        for r in rows:
            cost = int(r.get("cost") or 0)
            stock = int(r.get("stock") or 0)
            sold = int(r.get("sold") or 0)
            out = stock > 0 and sold >= stock
            afford = pts >= cost
            mark = "🚫" if out else ("✅" if afford else "🔒")
            lines.append(f"{mark} {r.get('icon')} {r.get('title')} — {cost} امتیاز")
            if r.get("description"):
                lines.append(f"      {r['description']}")
            if out:
                lines.append("      ⛔ موجودی تمام شد")
            elif not afford:
                lines.append(f"      نیاز به {cost - pts} امتیاز بیشتر")
            elif stock > 0:
                lines.append(f"      📦 موجودی: {stock - sold}")
            if afford and not out:
                btns.append([{"text": f"{r.get('icon')} {r.get('title')} "
                                      f"({cost} امتیاز)",
                              "callback_data": f"cl_buy_{r['id']}"}])
    else:
        lines.append("📭 فعلاً پاداشی موجود نیست")

    lines += ["", "💡 با شرکت در رویدادها و دعوت دوستان امتیاز بگیرید."]
    btns.append([{"text": "📜 سابقه خریدهای من", "callback_data": "cl_myredeem"}])
    btns.append([{"text": "🎖️ دستاوردها", "callback_data": "cl_my"}])
    btns.append([{"text": "🔙 پروفایل", "callback_data": "profile_view"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def confirm_buy(cid, uid, rid):
    """تأیید خرید"""
    try:
        r = db_execute("SELECT * FROM rewards WHERE id=?", (int(rid),), fetch="one")
    except (TypeError, ValueError):
        r = None
    if not r or not r.get("is_active"):
        return send(cid, "❌ این پاداش موجود نیست")

    u = get_user(uid)
    pts = int((u or {}).get("total_points") or 0)
    cost = int(r.get("cost") or 0)
    if pts < cost:
        return send(cid, f"🔒 امتیاز کافی ندارید\n\n"
                         f"🏆 شما: {pts}  |  نیاز: {cost}")

    return send_or_edit(cid, (
        f"🛒 تأیید خرید\n━━━━━━━━━━━━━━\n\n"
        f"{r.get('icon')} {r.get('title')}\n"
        f"📄 {r.get('description') or ''}\n\n"
        f"💰 هزینه: {cost} امتیاز\n"
        f"🏆 امتیاز شما: {pts}\n"
        f"📊 باقیمانده پس از خرید: {pts - cost}\n\n"
        f"⚠️ امتیاز کسر‌شده برنمی‌گردد. مطمئنید؟"
    ), {"inline_keyboard": [
        [{"text": "✅ بله، خرید کن", "callback_data": f"cl_buyok_{r['id']}"}],
        [{"text": "❌ انصراف", "callback_data": "cl_shop"}]]})


def do_buy(cid, uid, rid):
    """انجام خرید — کسر امتیاز و تحویل"""
    try:
        r = db_execute("SELECT * FROM rewards WHERE id=?", (int(rid),), fetch="one")
    except (TypeError, ValueError):
        r = None
    if not r or not r.get("is_active"):
        return send(cid, "❌ این پاداش موجود نیست")

    cost = int(r.get("cost") or 0)
    stock = int(r.get("stock") or 0)
    sold = int(r.get("sold") or 0)
    if stock > 0 and sold >= stock:
        return send(cid, "⛔ موجودی این پاداش تمام شد")

    # سقف هر کاربر
    lim = int(r.get("per_user_limit") or 0)
    if lim:
        mine = db_scalar("""SELECT COUNT(*) FROM reward_redemptions
            WHERE bale_user_id=? AND reward_key=? AND status<>'rejected'""",
            (uid, r.get("key")))
        if mine >= lim:
            return send(cid, f"⚠️ حداکثر {lim} بار می‌توانید این پاداش را بگیرید")

    u = get_user(uid)
    pts = int((u or {}).get("total_points") or 0)
    if pts < cost:
        return send(cid, "🔒 امتیاز کافی ندارید")

    # 🔴 کسر امتیاز به‌صورت اتمیک (شرط در خود UPDATE)
    db_execute("""UPDATE users SET total_points = total_points - ?
        WHERE bale_user_id=? AND COALESCE(total_points,0) >= ?""",
        (cost, uid, cost))
    fresh = int((get_user(uid) or {}).get("total_points") or 0)
    if fresh != pts - cost:
        return send(cid, "⚠️ خطا در کسر امتیاز. دوباره تلاش کنید.")

    code = "RW" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    rtype = r.get("reward_type") or "custom"
    auto = REWARD_TYPES.get(rtype, {}).get("auto", 0)
    status = "delivered" if auto else "pending"

    db_execute("""INSERT INTO reward_redemptions
        (bale_user_id, reward_key, reward_title, cost, code, status)
        VALUES (?,?,?,?,?,?)""",
        (uid, r.get("key"), r.get("title"), cost, code, status))
    db_execute("UPDATE rewards SET sold=COALESCE(sold,0)+1 WHERE id=?", (r["id"],))
    log_action(uid, "reward_redeem", {"key": r.get("key"), "points": cost})

    lines = [f"🎉 خرید انجام شد!", "━━━━━━━━━━━━━━", "",
             f"{r.get('icon')} {r.get('title')}",
             f"💰 {cost} امتیاز کسر شد",
             f"🏆 امتیاز باقیمانده: {fresh}", ""]

    # تحویل خودکار
    if rtype == "vip":
        days = int(r.get("reward_value") or 30)
        db_execute("UPDATE users SET is_vip=1 WHERE bale_user_id=?", (uid,))
        lines.append(f"⭐ عضویت VIP شما برای {days} روز فعال شد!")
    elif rtype == "discount":
        pct = int(r.get("reward_value") or 10)
        try:
            db_execute("""INSERT INTO event_discount_codes
                (event_id, code, discount_type, amount, max_uses,
                 per_user_limit, created_by)
                VALUES (NULL,?,'percent',?,1,1,?)""", (code, pct, uid))
            lines += [f"🎫 کد تخفیف {pct}٪ شما:", f"`{code}`", "",
                      "💡 هنگام پرداخت این کد را وارد کنید."]
        except Exception as e:
            log(f"⚠️ ساخت کد تخفیف: {e}")
            lines.append("⚠️ خطا در ساخت کد — با پشتیبانی تماس بگیرید")
    else:
        lines += [f"🔖 کد پیگیری: {code}", "",
                  "⏳ ادمین به‌زودی با شما تماس می‌گیرد."]
        _notify_admins(
            f"🛍️ درخواست پاداش جدید\n━━━━━━━━━━━━━━\n\n"
            f"{r.get('icon')} {r.get('title')}\n"
            f"👤 {(u or {}).get('first_name') or ''} "
            f"{(u or {}).get('last_name') or ''}\n"
            f"📱 {(u or {}).get('mobile') or '—'}\n"
            f"💰 {cost} امتیاز\n"
            f"🔖 {code}")

    send(cid, "\n".join(lines))
    return show_shop(cid, uid)


def _notify_admins(text):
    rows = db_execute("SELECT bale_user_id FROM users WHERE is_admin=1 "
                      "AND bale_user_id IS NOT NULL", fetch="all") or []
    for r in rows:
        try:
            send(r["bale_user_id"], text)
        except Exception:
            pass


def show_my_redemptions(cid, uid):
    """📜 سابقه خریدهای کاربر"""
    rows = db_execute("""SELECT * FROM reward_redemptions
        WHERE bale_user_id=? ORDER BY id DESC LIMIT 20""", (uid,), fetch="all") or []
    spent = db_scalar("""SELECT COALESCE(SUM(cost),0) FROM reward_redemptions
        WHERE bale_user_id=? AND status<>'rejected'""", (uid,))

    st_map = {"pending": "⏳ در انتظار تحویل", "delivered": "✅ تحویل شد",
              "rejected": "❌ رد شد"}
    lines = ["📜 خریدهای من", "━━━━━━━━━━━━━━", "",
             f"💰 مجموع امتیاز خرج‌شده: {spent}", ""]
    if rows:
        for r in rows:
            lines.append(f"• {r.get('reward_title')} — {r.get('cost')} امتیاز")
            lines.append(f"   {st_map.get(r.get('status'), r.get('status'))}"
                         f"  |  🔖 {r.get('code') or '—'}")
            lines.append(f"   🕐 {_jd.fmt(r.get('created_at'), 'datetime')}")
    else:
        lines.append("📭 هنوز خریدی نداشته‌اید")

    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🛍️ فروشگاه", "callback_data": "cl_shop"}],
        [{"text": "🔙 پروفایل", "callback_data": "profile_view"}]]})


# ==================== 🏆 جدول رتبه‌بندی ====================
BOARDS = {
    "points":  {"icon": "🏆", "name": "امتیاز کل"},
    "attend":  {"icon": "✋", "name": "بیشترین حضور"},
    "invite":  {"icon": "👥", "name": "بیشترین دعوت"},
    "badges":  {"icon": "🎖️", "name": "بیشترین نشان"},
}


def show_leaderboard(cid, uid, board="points"):
    """🏆 جدول رتبه‌بندی"""
    if get_setting("board_enabled", "1") != "1":
        return send_or_edit(cid, "🏆 جدول رتبه‌بندی غیرفعال است.",
                            {"inline_keyboard": [
                                [{"text": "🔙 بازگشت",
                                  "callback_data": "profile_view"}]]})

    board = board if board in BOARDS else "points"

    if board == "points":
        rows = db_execute("""SELECT bale_user_id, first_name, last_name,
            COALESCE(total_points,0) v FROM users
            WHERE COALESCE(total_points,0) > 0
              AND (is_blocked IS NULL OR is_blocked=0)
            ORDER BY v DESC LIMIT 10""", fetch="all") or []
        unit = "امتیاز"
    elif board == "attend":
        rows = db_execute("""SELECT u.bale_user_id, u.first_name, u.last_name,
            COUNT(r.id) v FROM users u
            JOIN event_registrations r ON r.bale_user_id=u.bale_user_id
              AND r.attended=1
            WHERE (u.is_blocked IS NULL OR u.is_blocked=0)
            GROUP BY u.bale_user_id ORDER BY v DESC LIMIT 10""",
            fetch="all") or []
        unit = "حضور"
    elif board == "invite":
        rows = db_execute("""SELECT u.bale_user_id, u.first_name, u.last_name,
            (SELECT COUNT(*) FROM users x WHERE x.referred_by=u.bale_user_id
             AND x.is_authenticated=1) v
            FROM users u WHERE (u.is_blocked IS NULL OR u.is_blocked=0)
            ORDER BY v DESC LIMIT 10""", fetch="all") or []
        rows = [r for r in rows if int(r.get("v") or 0) > 0]
        unit = "دعوت"
    else:
        rows = db_execute("""SELECT u.bale_user_id, u.first_name, u.last_name,
            COUNT(a.id) v FROM users u
            JOIN user_achievements a ON a.bale_user_id=u.bale_user_id
            WHERE (u.is_blocked IS NULL OR u.is_blocked=0)
            GROUP BY u.bale_user_id ORDER BY v DESC LIMIT 10""",
            fetch="all") or []
        unit = "نشان"

    b = BOARDS[board]
    lines = [f"{b['icon']} جدول رتبه‌بندی — {b['name']}",
             "━━━━━━━━━━━━━━", ""]
    medals = ["🥇", "🥈", "🥉"]
    me_rank = None
    anon = get_setting("board_anonymous", "0") == "1"

    if rows:
        for i, r in enumerate(rows):
            nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
            nm = nm or "کاربر"
            if anon and r.get("bale_user_id") != uid:
                nm = nm[:1] + "***"
            me = " ← شما" if r.get("bale_user_id") == uid else ""
            if me:
                me_rank = i + 1
            mk = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{mk} {nm} — {r.get('v')} {unit}{me}")
    else:
        lines.append("📭 هنوز داده‌ای نیست")

    if me_rank is None:
        u = get_user(uid) or {}
        if board == "points":
            mine = int(u.get("total_points") or 0)
            better = db_scalar("SELECT COUNT(*) FROM users WHERE "
                               "COALESCE(total_points,0) > ?", (mine,))
            lines += ["", f"📊 رتبه شما: {better + 1}  ({mine} {unit})"]

    btns = [[{"text": f"{v['icon']} {v['name']}", "callback_data": f"cl_bd_{k}"}]
            for k, v in BOARDS.items() if k != board]
    btns.append([{"text": "🎖️ دستاوردهای من", "callback_data": "cl_my"}])
    btns.append([{"text": "🔙 پروفایل", "callback_data": "profile_view"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ==================== ⚙️ پنل ادمین باشگاه ====================
def show_admin_panel(cid, uid):
    if not _guard(cid, uid):
        return
    n_ach = db_scalar("SELECT COUNT(*) FROM achievements")
    n_earned = db_scalar("SELECT COUNT(*) FROM user_achievements")
    n_rw = db_scalar("SELECT COUNT(*) FROM rewards WHERE is_active=1")
    n_pending = db_scalar("SELECT COUNT(*) FROM reward_redemptions "
                          "WHERE status='pending'")
    spent = db_scalar("SELECT COALESCE(SUM(cost),0) FROM reward_redemptions "
                      "WHERE status<>'rejected'")

    lines = ["🏅 باشگاه کاربران", "━━━━━━━━━━━━━━", "",
             f"🎖️ دستاوردها: {n_ach}  (اعطاشده: {n_earned})",
             f"🛍️ پاداش‌های فعال: {n_rw}",
             f"💰 امتیاز خرج‌شده: {spent}"]
    if n_pending:
        lines += ["", f"⏳ {n_pending} درخواست پاداش در انتظار تحویل"]

    btns = []
    if n_pending:
        btns.append([{"text": f"⏳ درخواست‌های پاداش ({n_pending})",
                      "callback_data": "cl_reqs"}])
    btns += [
        [{"text": "🎖️ مدیریت دستاوردها", "callback_data": "cl_adm_ach"}],
        [{"text": "🛍️ مدیریت فروشگاه", "callback_data": "cl_adm_rw"}],
        [{"text": "🏆 جدول رتبه‌بندی", "callback_data": "cl_bd_points"}],
        [{"text": "⚙️ تنظیمات باشگاه", "callback_data": "cl_settings"}],
        [{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}],
    ]
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_requests(cid, uid):
    """⏳ درخواست‌های پاداش در انتظار"""
    if not _guard(cid, uid):
        return
    rows = db_execute("""SELECT r.*, u.first_name, u.last_name, u.mobile
        FROM reward_redemptions r
        LEFT JOIN users u ON u.bale_user_id=r.bale_user_id
        WHERE r.status='pending' ORDER BY r.id DESC LIMIT 20""",
        fetch="all") or []
    lines = ["⏳ درخواست‌های پاداش", "━━━━━━━━━━━━━━", ""]
    btns = []
    if rows:
        for r in rows:
            nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
            lines.append(f"🎁 {r.get('reward_title')}")
            lines.append(f"   👤 {nm or '—'}  📱 {r.get('mobile') or '—'}")
            lines.append(f"   💰 {r.get('cost')} امتیاز  🔖 {r.get('code')}")
            lines.append("")
            btns.append([
                {"text": f"✅ تحویل {r.get('code')}",
                 "callback_data": f"cl_ok_{r['id']}"},
                {"text": "❌ رد", "callback_data": f"cl_rej_{r['id']}"},
            ])
    else:
        lines.append("✅ درخواستی در انتظار نیست")
    btns.append([{"text": "🔙 بازگشت", "callback_data": "cl_panel"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def handle_request(cid, uid, rid, approve=True):
    """✅/❌ تحویل یا رد درخواست پاداش"""
    if not _guard(cid, uid):
        return
    try:
        r = db_execute("SELECT * FROM reward_redemptions WHERE id=?",
                       (int(rid),), fetch="one")
    except (TypeError, ValueError):
        r = None
    if not r:
        return send(cid, "❌ یافت نشد")
    if r.get("status") != "pending":
        return send(cid, "⚠️ این درخواست قبلاً بررسی شده")

    if approve:
        db_execute("""UPDATE reward_redemptions SET status='delivered',
            handled_by=?, handled_at=CURRENT_TIMESTAMP WHERE id=?""",
            (uid, r["id"]))
        try:
            send(r["bale_user_id"], (
                f"✅ پاداش شما تحویل شد!\n\n"
                f"🎁 {r.get('reward_title')}\n"
                f"🔖 {r.get('code')}"
            ))
        except Exception:
            pass
        send(cid, "✅ تحویل ثبت شد")
    else:
        # رد → امتیاز برگردد
        db_execute("""UPDATE reward_redemptions SET status='rejected',
            handled_by=?, handled_at=CURRENT_TIMESTAMP WHERE id=?""",
            (uid, r["id"]))
        db_execute("UPDATE users SET total_points=COALESCE(total_points,0)+? "
                   "WHERE bale_user_id=?", (int(r.get("cost") or 0),
                                            r["bale_user_id"]))
        db_execute("UPDATE rewards SET sold=MAX(0,COALESCE(sold,0)-1) "
                   "WHERE key=?", (r.get("reward_key"),))
        try:
            send(r["bale_user_id"], (
                f"❌ درخواست پاداش شما رد شد\n\n"
                f"🎁 {r.get('reward_title')}\n"
                f"💰 {r.get('cost')} امتیاز به شما برگردانده شد."
            ))
        except Exception:
            pass
        send(cid, "❌ رد شد و امتیاز برگشت")
    return show_requests(cid, uid)


def show_admin_achievements(cid, uid):
    if not _guard(cid, uid):
        return
    rows = db_execute("SELECT * FROM achievements ORDER BY tier, threshold",
                      fetch="all") or []
    lines = [f"🎖️ مدیریت دستاوردها ({len(rows)})", "━━━━━━━━━━━━━━", ""]
    btns = []
    for a in rows:
        t = TIERS.get(a.get("tier") or "bronze", TIERS["bronze"])
        st = "🟢" if a.get("is_active") else "⚫"
        lines.append(f"{st} {a.get('icon')} {a.get('title')} {t['icon']}")
        lines.append(f"   {a.get('trigger')} ≥ {a.get('threshold')}"
                     f" → {a.get('points')} امتیاز"
                     f"  (کسب‌شده: {a.get('total_earned') or 0})")
        btns.append([{"text": f"{st} {a.get('title')[:28]}",
                      "callback_data": f"cl_av_{a['id']}"}])
    btns.append([{"text": "➕ دستاورد جدید", "callback_data": "cl_aadd"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "cl_panel"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def view_achievement(cid, uid, aid):
    if not _guard(cid, uid):
        return
    try:
        a = db_execute("SELECT * FROM achievements WHERE id=?", (int(aid),),
                       fetch="one")
    except (TypeError, ValueError):
        a = None
    if not a:
        return send(cid, "❌ یافت نشد")
    t = TIERS.get(a.get("tier") or "bronze", TIERS["bronze"])
    return send_or_edit(cid, (
        f"{a.get('icon')} {a.get('title')}\n━━━━━━━━━━━━━━\n\n"
        f"📄 {a.get('description') or '—'}\n"
        f"{t['icon']} سطح: {t['name']}\n"
        f"🎯 شرط: {a.get('trigger')} ≥ {a.get('threshold')}\n"
        f"🎁 امتیاز: {a.get('points')}\n"
        f"👥 کسب‌شده: {a.get('total_earned') or 0} نفر\n"
        f"📊 وضعیت: {'🟢 فعال' if a.get('is_active') else '⚫ غیرفعال'}"
    ), {"inline_keyboard": [
        [{"text": "🎁 تغییر امتیاز", "callback_data": f"cln_points_{aid}"},
         {"text": "📊 حد نصاب", "callback_data": f"cln_threshold_{aid}"}],
        [{"text": ("⚫ غیرفعال" if a.get("is_active") else "🟢 فعال"),
          "callback_data": f"cl_atg_{aid}"}],
        [{"text": "🗑️ حذف", "callback_data": f"cl_adel_{aid}"}],
        [{"text": "🔙 بازگشت", "callback_data": "cl_adm_ach"}]]})


def show_admin_rewards(cid, uid):
    if not _guard(cid, uid):
        return
    rows = db_execute("SELECT * FROM rewards ORDER BY cost", fetch="all") or []
    lines = [f"🛍️ مدیریت فروشگاه ({len(rows)})", "━━━━━━━━━━━━━━", ""]
    btns = []
    for r in rows:
        st = "🟢" if r.get("is_active") else "⚫"
        stock = int(r.get("stock") or 0)
        lines.append(f"{st} {r.get('icon')} {r.get('title')} — "
                     f"{r.get('cost')} امتیاز")
        lines.append(f"   فروش: {r.get('sold') or 0}"
                     + (f"/{stock}" if stock else " (نامحدود)"))
        btns.append([{"text": f"{st} {r.get('title')[:28]}",
                      "callback_data": f"cl_rv_{r['id']}"}])
    btns.append([{"text": "➕ پاداش جدید", "callback_data": "cl_radd"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": "cl_panel"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def view_reward(cid, uid, rid):
    if not _guard(cid, uid):
        return
    try:
        r = db_execute("SELECT * FROM rewards WHERE id=?", (int(rid),),
                       fetch="one")
    except (TypeError, ValueError):
        r = None
    if not r:
        return send(cid, "❌ یافت نشد")
    rt = REWARD_TYPES.get(r.get("reward_type") or "custom",
                          REWARD_TYPES["custom"])
    return send_or_edit(cid, (
        f"{r.get('icon')} {r.get('title')}\n━━━━━━━━━━━━━━\n\n"
        f"📄 {r.get('description') or '—'}\n"
        f"💰 هزینه: {r.get('cost')} امتیاز\n"
        f"🎁 نوع: {rt['icon']} {rt['name']}\n"
        f"📦 موجودی: {r.get('stock') or 'نامحدود'}\n"
        f"🛒 فروش‌رفته: {r.get('sold') or 0}\n"
        f"👤 سقف هر نفر: {r.get('per_user_limit') or 'نامحدود'}\n"
        f"📊 وضعیت: {'🟢 فعال' if r.get('is_active') else '⚫ غیرفعال'}"
    ), {"inline_keyboard": [
        [{"text": "💰 تغییر هزینه", "callback_data": f"clrn_cost_{rid}"},
         {"text": "📦 موجودی", "callback_data": f"clrn_stock_{rid}"}],
        [{"text": ("⚫ غیرفعال" if r.get("is_active") else "🟢 فعال"),
          "callback_data": f"cl_rtg_{rid}"}],
        [{"text": "🗑️ حذف", "callback_data": f"cl_rdel_{rid}"}],
        [{"text": "🔙 بازگشت", "callback_data": "cl_adm_rw"}]]})


def toggle_item(cid, uid, kind, iid):
    if not _guard(cid, uid):
        return
    tbl = "achievements" if kind == "a" else "rewards"
    try:
        row = db_execute(f"SELECT is_active FROM {tbl} WHERE id=?",
                         (int(iid),), fetch="one")
    except (TypeError, ValueError):
        row = None
    if not row:
        return send(cid, "❌ یافت نشد")
    db_execute(f"UPDATE {tbl} SET is_active=? WHERE id=?",
               (0 if row.get("is_active") else 1, int(iid)))
    return (view_achievement(cid, uid, iid) if kind == "a"
            else view_reward(cid, uid, iid))


def delete_item(cid, uid, kind, iid, confirmed=False):
    if not _guard(cid, uid):
        return
    tbl = "achievements" if kind == "a" else "rewards"
    try:
        row = db_execute(f"SELECT * FROM {tbl} WHERE id=?", (int(iid),),
                         fetch="one")
    except (TypeError, ValueError):
        row = None
    if not row:
        return send(cid, "❌ یافت نشد")
    if not confirmed:
        # callback ثابت می‌سازیم تا ابزار بازبینی بتواند تحلیلش کند
        yes_cb = f"cl_adely_{iid}" if kind == "a" else f"cl_rdely_{iid}"
        back_cb = f"cl_av_{iid}" if kind == "a" else f"cl_rv_{iid}"
        return send_or_edit(cid, (
            f"🗑️ حذف «{row.get('title')}»؟\n\nاین عمل بازگشت‌پذیر نیست."
        ), {"inline_keyboard": [
            [{"text": "🗑️ بله", "callback_data": yes_cb}],
            [{"text": "❌ انصراف", "callback_data": back_cb}]]})
    db_execute(f"DELETE FROM {tbl} WHERE id=?", (int(iid),))
    send(cid, "🗑️ حذف شد")
    return (show_admin_achievements(cid, uid) if kind == "a"
            else show_admin_rewards(cid, uid))


def start_num_edit(cid, uid, kind, iid, field):
    """ویرایش عددی دستاورد/پاداش"""
    if not _guard(cid, uid):
        return
    allowed = {"a": ("points", "threshold"), "r": ("cost", "stock")}
    if field not in allowed.get(kind, ()):
        return send(cid, "❌ نامعتبر")
    tbl = "achievements" if kind == "a" else "rewards"
    try:
        row = db_execute(f"SELECT * FROM {tbl} WHERE id=?", (int(iid),),
                         fetch="one")
    except (TypeError, ValueError):
        row = None
    if not row:
        return send(cid, "❌ یافت نشد")
    names = {"points": "🎁 امتیاز", "threshold": "📊 حد نصاب",
             "cost": "💰 هزینه (امتیاز)", "stock": "📦 موجودی (۰=نامحدود)"}
    set_state(uid, STATE_CLUB_EDIT,
              {"kind": kind, "iid": int(iid), "field": field}, merge=False)
    send(cid, f"{names[field]}\n━━━━━━━━━━━━━━\n\n"
              f"📌 فعلی: {row.get(field) or 0}\n\nعدد جدید:", kb_cancel())


def handle_num_edit(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    d = get_state_data(uid)
    kind, iid, field = d.get("kind"), d.get("iid"), d.get("field")

    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return (view_achievement(cid, uid, iid) if kind == "a"
                else view_reward(cid, uid, iid))

    allowed = {"a": ("points", "threshold"), "r": ("cost", "stock")}
    if field not in allowed.get(kind, ()):
        clear_state(uid)
        return send(cid, "⚠️ نامعتبر", kb_remove())

    digits = "".join(ch for ch in normalize_digits(text) if ch.isdigit())
    if not digits:
        return send(cid, "⚠️ فقط عدد وارد کنید:", kb_cancel())
    val = int(digits)

    # 🔴 سقف سخت‌گیرانه امتیاز
    if field == "points":
        import occasions as oc
        val = min(val, oc.POINTS_MAX_SINGLE)

    clear_state(uid)
    tbl = "achievements" if kind == "a" else "rewards"
    db_execute(f"UPDATE {tbl} SET {field}=? WHERE id=?", (val, iid))
    send(cid, f"✅ ثبت شد: {val}", kb_remove())
    return (view_achievement(cid, uid, iid) if kind == "a"
            else view_reward(cid, uid, iid))


def start_add(cid, uid, kind):
    if not _guard(cid, uid):
        return
    set_state(uid, STATE_CLUB_ADD, {"kind": kind}, merge=False)
    if kind == "a":
        import occasions as oc
        trg = "، ".join(oc.TRIGGERS.keys())
        send(cid, (
            "➕ دستاورد جدید\n━━━━━━━━━━━━━━\n\n"
            "عنوان | شرط | حد نصاب | امتیاز\n\n"
            "مثال:\n"
            "قهرمان حضور | event_attend | 50 | 60\n\n"
            f"🎯 شرط‌ها: {trg}"
        ), kb_cancel())
    else:
        send(cid, (
            "➕ پاداش جدید\n━━━━━━━━━━━━━━\n\n"
            "عنوان | هزینه | نوع | مقدار\n\n"
            "مثال‌ها:\n"
            "کد تخفیف ۱۵٪ | 90 | discount | 15\n"
            "VIP دوماهه | 400 | vip | 60\n"
            "کتاب هدیه | 200 | custom\n\n"
            "🎁 نوع‌ها: discount، vip، custom"
        ), kb_cancel())


def handle_add(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    kind = get_state_data(uid).get("kind")

    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return (show_admin_achievements(cid, uid) if kind == "a"
                else show_admin_rewards(cid, uid))

    parts = [p.strip() for p in text.replace("،", "|").split("|")]
    if len(parts) < 2:
        return send(cid, "⚠️ فرمت نادرست — دوباره بنویسید:", kb_cancel())

    def _n(x, dflt=0):
        dd = "".join(ch for ch in normalize_digits(x or "") if ch.isdigit())
        return int(dd) if dd else dflt

    title = parts[0][:80]
    if kind == "a":
        import occasions as oc
        trg = parts[1]
        if trg not in oc.TRIGGERS:
            return send(cid, f"⚠️ شرط نامعتبر.\n\nمجاز: {', '.join(oc.TRIGGERS)}",
                        kb_cancel())
        thr = _n(parts[2] if len(parts) > 2 else "", 1)
        pts = min(_n(parts[3] if len(parts) > 3 else "", 0),
                  oc.POINTS_MAX_SINGLE)
        clear_state(uid)
        key = f"cus{int(datetime.now().timestamp())}"
        aid = db_execute("""INSERT INTO achievements
            (key, icon, title, trigger, threshold, points, tier, created_by)
            VALUES (?,'🎖️',?,?,?,?,'silver',?)""",
            (key, title, trg, thr, pts, uid))
        send(cid, f"✅ دستاورد «{title}» ساخته شد\n🎁 {pts} امتیاز", kb_remove())
        return view_achievement(cid, uid, aid) if aid else \
            show_admin_achievements(cid, uid)

    cost = _n(parts[1], 0)
    rtype = (parts[2] if len(parts) > 2 else "custom").strip().lower()
    if rtype not in REWARD_TYPES:
        rtype = "custom"
    rval = parts[3] if len(parts) > 3 else ""
    clear_state(uid)
    key = f"rw{int(datetime.now().timestamp())}"
    rid = db_execute("""INSERT INTO rewards
        (key, icon, title, cost, reward_type, reward_value, created_by)
        VALUES (?,'🎁',?,?,?,?,?)""",
        (key, title, cost, rtype, rval, uid))
    send(cid, f"✅ پاداش «{title}» ساخته شد\n💰 {cost} امتیاز", kb_remove())
    return view_reward(cid, uid, rid) if rid else show_admin_rewards(cid, uid)


def show_settings(cid, uid):
    if not _guard(cid, uid):
        return
    ach = get_setting("club_enabled", "1") == "1"
    shop = get_setting("shop_enabled", "1") == "1"
    board = get_setting("board_enabled", "1") == "1"
    anon = get_setting("board_anonymous", "0") == "1"
    return send_or_edit(cid, (
        "⚙️ تنظیمات باشگاه\n━━━━━━━━━━━━━━\n\n"
        f"🎖️ دستاوردها: {'✅ فعال' if ach else '❌ خاموش'}\n"
        f"🛍️ فروشگاه: {'✅ فعال' if shop else '❌ خاموش'}\n"
        f"🏆 جدول رتبه‌بندی: {'✅ فعال' if board else '❌ خاموش'}\n"
        f"🕶️ نام‌های مخفی در جدول: {'✅' if anon else '❌'}"
    ), {"inline_keyboard": [
        [{"text": f"🎖️ دستاوردها {'✅' if ach else '❌'}",
          "callback_data": "cl_tog_club_enabled"}],
        [{"text": f"🛍️ فروشگاه {'✅' if shop else '❌'}",
          "callback_data": "cl_tog_shop_enabled"}],
        [{"text": f"🏆 جدول {'✅' if board else '❌'}",
          "callback_data": "cl_tog_board_enabled"}],
        [{"text": f"🕶️ نام مخفی {'✅' if anon else '❌'}",
          "callback_data": "cl_tog_board_anonymous"}],
        [{"text": "🔙 بازگشت", "callback_data": "cl_panel"}]]})


CLUB_FLAGS = {"club_enabled", "shop_enabled", "board_enabled",
              "board_anonymous"}


def toggle_flag(cid, uid, key):
    if not _guard(cid, uid):
        return
    if key not in CLUB_FLAGS:
        return send(cid, "❌ نامعتبر")
    cur = get_setting(key, "1" if key != "board_anonymous" else "0")
    set_setting(key, "0" if cur == "1" else "1", key, "club", uid)
    return show_settings(cid, uid)
