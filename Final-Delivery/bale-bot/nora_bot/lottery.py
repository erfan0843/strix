"""
🎲 قرعه‌کشی و انتخاب برنده — فاز ۱۴

طبق فایل معماری (خطوط ۵۷۷۸۱ تا ۵۸۰۹۰):

  ۶ روش انتخاب برنده:
    🎲 تصادفی (قرعه‌کشی از همه)
    🥇 بالاترین نمره
    ⚡ سریع‌ترین پاسخ
    🎯 ترکیب نمره + زمان
    👤 انتخاب دستی توسط ادمین
    ❌ غیرفعال

  ۳ زمان اجرا: بلافاصله بعد از پایان · تاریخ مشخص · دستی

  🎁 جوایز چندگانه با تعداد برنده مستقل (🥇🥈🥉 + دلخواه)

  📢 اطلاع‌رسانی: برندگان · همه شرکت‌کنندگان · گواهینامه برندگان

روی هر دو کار می‌کند:
  📝 فرم (مسابقه، آزمون، نظرسنجی، ...)  → source='form'
  🎉 رویداد (بین شرکت‌کنندگان)           → source='event'

⚠️ قرعه‌کشی با random.SystemRandom انجام می‌شود (امن و غیرقابل پیش‌بینی)
   و بعد از اجرا نتیجه قفل می‌شود تا کسی نتواند دوباره بگیرد.
"""
from privacy import user_error_message
import json
import random
import string
from datetime import datetime

from config import SUPER_ADMIN_ID
from database import db_execute, db_scalar, get_setting, set_setting, log
from auth import (
    set_state, get_state_data, clear_state, log_action,
    normalize_digits, is_admin as _is_admin,
)
from bale_api import send, send_or_edit, send_document, kb_cancel, kb_remove, BTN_BACK

STATE_LT_ADD = "lt_add"
STATE_LT_NUM = "lt_num"
STATE_LT_DATE = "lt_date"

# 🔐 مولد تصادفی امن — قابل پیش‌بینی نیست
_rng = random.SystemRandom()


# ==================== روش‌های انتخاب برنده ====================
WINNER_MODES = {
    "disabled": {
        "icon": "❌", "name": "غیرفعال",
        "desc": "بدون برنده — قرعه‌کشی انجام نمی‌شود",
        "needs_score": 0, "needs_time": 0,
    },
    "random": {
        "icon": "🎲", "name": "تصادفی (قرعه‌کشی)",
        "desc": "انتخاب کاملاً شانسی از بین همه شرکت‌کنندگان",
        "needs_score": 0, "needs_time": 0,
    },
    "highest_score": {
        "icon": "🥇", "name": "بالاترین نمره",
        "desc": "هر کس نمره بیشتری گرفت برنده است",
        "needs_score": 1, "needs_time": 0,
    },
    "fastest": {
        "icon": "⚡", "name": "سریع‌ترین پاسخ",
        "desc": "هر کس زودتر تکمیل کرد برنده است",
        "needs_score": 0, "needs_time": 1,
    },
    "combined": {
        "icon": "🎯", "name": "ترکیب نمره و زمان",
        "desc": "اول نمره، در صورت تساوی زمان کمتر",
        "needs_score": 1, "needs_time": 1,
    },
    "manual": {
        "icon": "👤", "name": "انتخاب دستی",
        "desc": "ادمین خودش برندگان را انتخاب می‌کند",
        "needs_score": 0, "needs_time": 0,
    },
}

DRAW_TIMES = {
    "manual":    {"icon": "👤", "name": "دستی توسط ادمین"},
    "on_close":  {"icon": "⏱️", "name": "بلافاصله بعد از پایان"},
    "scheduled": {"icon": "📅", "name": "در تاریخ مشخص"},
}

# مدال‌های پیش‌فرض جایزه
MEDALS = ["🥇", "🥈", "🥉", "🎁", "🎀", "🏅", "⭐", "💎"]


# ==================== دیتابیس ====================
LOTTERY_SCHEMA = {
    "source": "TEXT DEFAULT 'form'",        # form | event
    "form_id": "INTEGER",
    "event_id": "INTEGER",
    "title": "TEXT",
    "is_active": "INTEGER DEFAULT 1",
    "winner_mode": "TEXT DEFAULT 'random'",
    "draw_time": "TEXT DEFAULT 'manual'",
    "draw_at": "TEXT",                      # تاریخ شمسی برای scheduled
    "min_score": "INTEGER DEFAULT 0",       # حداقل نمره برای شرکت
    "exclude_previous": "INTEGER DEFAULT 0",  # برنده قبلی دوباره برنده نشود
    "only_attended": "INTEGER DEFAULT 0",   # فقط حاضرین (رویداد)
    "notify_winners": "INTEGER DEFAULT 1",
    "notify_all": "INTEGER DEFAULT 1",
    "cert_winners": "INTEGER DEFAULT 0",
    "show_leaderboard": "INTEGER DEFAULT 1",
    "winner_message": "TEXT",
    "public_message": "TEXT",
    "status": "TEXT DEFAULT 'pending'",     # pending | done | cancelled
    "drawn_at": "TIMESTAMP",
    "drawn_by": "INTEGER",
    "participants_count": "INTEGER DEFAULT 0",
    "created_by": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

PRIZE_SCHEMA = {
    "lottery_id": "INTEGER NOT NULL",
    "rank_order": "INTEGER DEFAULT 1",
    "icon": "TEXT",
    "title": "TEXT",
    "description": "TEXT",
    "winner_count": "INTEGER DEFAULT 1",
    "points_reward": "INTEGER DEFAULT 0",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

WINNER_SCHEMA = {
    "lottery_id": "INTEGER NOT NULL",
    "prize_id": "INTEGER",
    "bale_user_id": "INTEGER",
    "response_id": "INTEGER",
    "registration_id": "INTEGER",
    "rank_no": "INTEGER",
    "score": "INTEGER DEFAULT 0",
    "time_taken": "INTEGER DEFAULT 0",
    "notified": "INTEGER DEFAULT 0",
    "claimed": "INTEGER DEFAULT 0",
    "code": "TEXT",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}


def init_lottery_tables():
    from database import ensure_table
    ensure_table("form_lotteries", LOTTERY_SCHEMA)
    ensure_table("lottery_prizes", PRIZE_SCHEMA)
    ensure_table("lottery_winners", WINNER_SCHEMA)
    for q in [
        "CREATE INDEX IF NOT EXISTS idx_lt_form ON form_lotteries(form_id)",
        "CREATE INDEX IF NOT EXISTS idx_lt_event ON form_lotteries(event_id)",
        "CREATE INDEX IF NOT EXISTS idx_lt_status ON form_lotteries(status)",
        "CREATE INDEX IF NOT EXISTS idx_lp_lot ON lottery_prizes(lottery_id)",
        "CREATE INDEX IF NOT EXISTS idx_lw_lot ON lottery_winners(lottery_id)",
        "CREATE INDEX IF NOT EXISTS idx_lw_user ON lottery_winners(bale_user_id)",
    ]:
        db_execute(q)
    seed_lottery_texts()
    log("✅ جدول‌های قرعه‌کشی آماده شد")


LOTTERY_TEXTS = [
    ("lt_txt_winner", "🎉 پیام به برنده",
     "🎉 تبریک {dear}!\n"
     "━━━━━━━━━━━━━━\n\n"
     "شما در قرعه‌کشی «{title}» برنده شدید!\n\n"
     "{prize_icon} جایزه شما: {prize}\n"
     "🏅 رتبه: {rank}\n"
     "🔖 کد پیگیری: {code}\n\n"
     "💚 برای دریافت جایزه با پشتیبانی تماس بگیرید."),

    ("lt_txt_public", "📢 اعلام عمومی نتیجه",
     "🎲 نتیجه قرعه‌کشی «{title}»\n"
     "━━━━━━━━━━━━━━\n\n"
     "👥 شرکت‌کنندگان: {total} نفر\n"
     "🏆 برندگان: {winners} نفر\n\n"
     "{list}\n\n"
     "💚 از همه شرکت‌کنندگان سپاسگزاریم."),

    ("lt_txt_loser", "💚 پیام به شرکت‌کننده بدون جایزه",
     "🎲 قرعه‌کشی «{title}» انجام شد\n"
     "━━━━━━━━━━━━━━\n\n"
     "{dear}، این بار شانس با شما یار نبود 🌱\n"
     "ولی از شرکت شما سپاسگزاریم.\n\n"
     "🏆 برندگان:\n{list}\n\n"
     "💡 در رویدادهای بعدی حتماً شرکت کنید!"),

    ("lt_txt_pending", "⏳ پیام قرعه‌کشی برگزارنشده",
     "⏳ قرعه‌کشی هنوز برگزار نشده است\n"
     "📅 زمان اعلام: {when}"),
]


def seed_lottery_texts():
    for key, title, default in LOTTERY_TEXTS:
        if not db_execute("SELECT key FROM settings WHERE key=?",
                          (key,), fetch="one"):
            set_setting(key, default, title, "lottery")


def render(key, **kw):
    default = next((d for k, t, d in LOTTERY_TEXTS if k == key), "")
    txt = get_setting(key, default)
    for k, v in kw.items():
        txt = txt.replace("{" + k + "}", str(v))
    return txt


# ==================== کمکی ====================
def _guard(cid, uid, perm_key="fm_edit"):
    if not _is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    import permissions as perm
    if not perm.has_any(uid, perm_key, "ev_edit", "fm_edit"):
        send(cid, "🔒 دسترسی به قرعه‌کشی ندارید")
        return False
    return True


def get_lottery(lid):
    """خواندن امن قرعه‌کشی — با شناسه خراب کرش نمی‌کند"""
    try:
        lid = int(lid)
    except (TypeError, ValueError):
        return None
    return db_execute("SELECT * FROM form_lotteries WHERE id=?",
                      (lid,), fetch="one")


def get_prizes(lid):
    try:
        lid = int(lid)
    except (TypeError, ValueError):
        return []
    return db_execute("SELECT * FROM lottery_prizes WHERE lottery_id=? "
                      "ORDER BY rank_order, id", (lid,), fetch="all") or []


def get_winners(lid):
    try:
        lid = int(lid)
    except (TypeError, ValueError):
        return []
    return db_execute("""SELECT w.*, u.first_name, u.last_name, u.mobile,
        u.gender, p.title prize_title, p.icon prize_icon,
        p.points_reward
        FROM lottery_winners w
        LEFT JOIN users u ON u.bale_user_id=w.bale_user_id
        LEFT JOIN lottery_prizes p ON p.id=w.prize_id
        WHERE w.lottery_id=? ORDER BY w.rank_no, w.id""",
        (lid,), fetch="all") or []


def total_winner_slots(lid):
    """مجموع تعداد برندگان همه جوایز"""
    return sum(int(p.get("winner_count") or 1) for p in get_prizes(lid))


def find_lottery(source, oid):
    """پیدا کردن قرعه‌کشی یک فرم یا رویداد"""
    col = "form_id" if source == "form" else "event_id"
    try:
        oid = int(oid)
    except (TypeError, ValueError):
        return None
    return db_execute(
        f"SELECT * FROM form_lotteries WHERE source=? AND {col}=? "
        "ORDER BY id DESC LIMIT 1", (source, oid), fetch="one")


def _name(u):
    n = f"{(u or {}).get('first_name') or ''} " \
        f"{(u or {}).get('last_name') or ''}".strip()
    return n or "کاربر"


def gen_code(n=8):
    return "LT" + "".join(_rng.choices(string.ascii_uppercase + string.digits,
                                       k=n))


# ==================== جمع‌آوری شرکت‌کنندگان ====================
def get_participants(lot):
    """
    لیست واجدین شرایط برای قرعه‌کشی.

    خروجی: [{"uid","name","mobile","score","time_taken",
              "response_id","registration_id"}]
    """
    if not lot:
        return []
    src = lot.get("source") or "form"
    min_score = int(lot.get("min_score") or 0)
    out = []

    if src == "form":
        fid = lot.get("form_id")
        if not fid:
            return []
        rows = db_execute("""SELECT r.id, r.bale_user_id, r.score,
            r.started_at, r.completed_at, u.first_name, u.last_name, u.mobile
            FROM form_responses r
            LEFT JOIN users u ON u.bale_user_id=r.bale_user_id
            WHERE r.form_id=? AND r.status IN ('completed','confirmed')
              AND r.bale_user_id IS NOT NULL""", (fid,), fetch="all") or []
        for r in rows:
            sc = int(r.get("score") or 0)
            if min_score and sc < min_score:
                continue
            out.append({
                "uid": r["bale_user_id"],
                "name": _name(r), "mobile": r.get("mobile") or "—",
                "score": sc,
                "time_taken": _seconds(r.get("started_at"),
                                       r.get("completed_at")),
                "response_id": r["id"], "registration_id": None,
            })
    else:
        eid = lot.get("event_id")
        if not eid:
            return []
        cond = "r.status IN ('confirmed','attended')"
        if int(lot.get("only_attended") or 0):
            cond = "(r.attended=1 OR r.status='attended')"
        rows = db_execute(f"""SELECT r.id, r.bale_user_id, r.created_at,
            u.first_name, u.last_name, u.mobile
            FROM event_registrations r
            LEFT JOIN users u ON u.bale_user_id=r.bale_user_id
            WHERE r.event_id=? AND {cond}
              AND r.bale_user_id IS NOT NULL""", (eid,), fetch="all") or []
        for r in rows:
            out.append({
                "uid": r["bale_user_id"],
                "name": _name(r), "mobile": r.get("mobile") or "—",
                "score": 0, "time_taken": 0,
                "response_id": None, "registration_id": r["id"],
            })

    # حذف برندگان قبلی
    if int(lot.get("exclude_previous") or 0):
        prev = db_execute("""SELECT DISTINCT bale_user_id FROM lottery_winners
            WHERE lottery_id <> ?""", (lot["id"],), fetch="all") or []
        skip = {p["bale_user_id"] for p in prev if p.get("bale_user_id")}
        out = [p for p in out if p["uid"] not in skip]

    # هر کاربر فقط یک بار
    seen, uniq = set(), []
    for p in out:
        if p["uid"] in seen:
            continue
        seen.add(p["uid"])
        uniq.append(p)
    return uniq


def _seconds(start, end):
    """اختلاف دو timestamp به ثانیه"""
    if not start or not end:
        return 0
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            a = datetime.strptime(str(start)[:26], fmt)
            b = datetime.strptime(str(end)[:26], fmt)
            return max(0, int((b - a).total_seconds()))
        except (ValueError, TypeError):
            continue
    return 0


def rank_participants(parts, mode):
    """مرتب‌سازی شرکت‌کنندگان بر اساس روش انتخاب برنده"""
    p = list(parts)
    if mode == "random":
        _rng.shuffle(p)
    elif mode == "highest_score":
        # نمره بیشتر بهتر؛ در تساوی، زمان کمتر
        p.sort(key=lambda x: (-x["score"], x["time_taken"] or 10 ** 9))
    elif mode == "fastest":
        # زمان صفر یعنی نامعلوم → ته صف
        p.sort(key=lambda x: (x["time_taken"] or 10 ** 9))
    elif mode == "combined":
        p.sort(key=lambda x: (-x["score"], x["time_taken"] or 10 ** 9))
    return p


# ==================== ساخت و تنظیم ====================
def ensure_lottery(source, oid, uid, title=""):
    """قرعه‌کشی را می‌سازد اگر نباشد"""
    lot = find_lottery(source, oid)
    if lot:
        return lot
    col = "form_id" if source == "form" else "event_id"
    lid = db_execute(
        f"INSERT INTO form_lotteries (source, {col}, title, created_by) "
        "VALUES (?,?,?,?)", (source, oid, title or "قرعه‌کشی", uid))
    if lid:
        # سه جایزه پیش‌فرض
        for i, (icon, nm) in enumerate(
                [("🥇", "جایزه اول"), ("🥈", "جایزه دوم"),
                 ("🥉", "جایزه سوم")], 1):
            db_execute("""INSERT INTO lottery_prizes
                (lottery_id, rank_order, icon, title, winner_count)
                VALUES (?,?,?,?,1)""", (lid, i, icon, nm))
        log_action(uid, "lottery_created", {"source": source, "id": oid})
    return get_lottery(lid)


def show_panel(cid, uid, source, oid):
    """🎲 پنل قرعه‌کشی یک فرم یا رویداد"""
    if not _guard(cid, uid):
        return
    title = _obj_title(source, oid)
    if title is None:
        return send(cid, "❌ یافت نشد")

    lot = ensure_lottery(source, oid, uid, title)
    if not lot:
        return send(cid, "❌ خطا در ساخت قرعه‌کشی")
    return show_lottery(cid, uid, lot["id"])


def _obj_title(source, oid):
    """عنوان فرم یا رویداد — None یعنی وجود ندارد"""
    try:
        oid = int(oid)
    except (TypeError, ValueError):
        return None
    if source == "form":
        r = db_execute("SELECT title FROM forms WHERE id=?", (oid,),
                       fetch="one")
    else:
        r = db_execute("SELECT title FROM events WHERE id=?", (oid,),
                       fetch="one")
    return r["title"] if r else None


def show_lottery(cid, uid, lid):
    """🎲 صفحه اصلی یک قرعه‌کشی"""
    if not _guard(cid, uid):
        return
    lot = get_lottery(lid)
    if not lot:
        return send(cid, "❌ قرعه‌کشی یافت نشد")

    mode = WINNER_MODES.get(lot.get("winner_mode") or "random",
                            WINNER_MODES["random"])
    dt = DRAW_TIMES.get(lot.get("draw_time") or "manual",
                        DRAW_TIMES["manual"])
    prizes = get_prizes(lid)
    slots = total_winner_slots(lid)
    parts = get_participants(lot)
    done = lot.get("status") == "done"

    lines = [
        "🎲 قرعه‌کشی و انتخاب برنده",
        f"📋 {lot.get('title') or '—'}",
        "━━━━━━━━━━━━━━", "",
        f"🎯 روش: {mode['icon']} {mode['name']}",
        f"   {mode['desc']}",
        f"📅 زمان اجرا: {dt['icon']} {dt['name']}",
    ]
    if lot.get("draw_time") == "scheduled" and lot.get("draw_at"):
        lines.append(f"   🗓️ {lot['draw_at']}")

    lines += ["", f"👥 واجد شرایط: {len(parts)} نفر",
              f"🎁 جوایز: {len(prizes)}  |  🏆 برندگان: {slots} نفر"]

    if int(lot.get("min_score") or 0):
        lines.append(f"📊 حداقل نمره: {lot['min_score']}")
    if int(lot.get("exclude_previous") or 0):
        lines.append("🔁 برندگان قبلی حذف می‌شوند")
    if lot.get("source") == "event" and int(lot.get("only_attended") or 0):
        lines.append("✋ فقط حاضرین در رویداد")

    if prizes:
        lines += ["", "🎁 جوایز:"]
        for p in prizes:
            extra = f" (+{p['points_reward']} امتیاز)" \
                if int(p.get("points_reward") or 0) else ""
            lines.append(f"   {p.get('icon') or '🎁'} {p.get('title')}"
                         f" — {p.get('winner_count') or 1} نفر{extra}")

    lines += ["", "📢 اطلاع‌رسانی:",
              f"   • به برندگان: {'✅' if lot.get('notify_winners') else '❌'}",
              f"   • به همه شرکت‌کنندگان: {'✅' if lot.get('notify_all') else '❌'}",
              f"   • گواهینامه برندگان: {'✅' if lot.get('cert_winners') else '❌'}"]

    if done:
        w = get_winners(lid)
        lines += ["", "━━━━━━━━━━━━━━",
                  f"✅ اجرا شده در {(lot.get('drawn_at') or '')[:16]}",
                  f"🏆 {len(w)} برنده انتخاب شد"]

    btns = []
    if done:
        btns.append([{"text": "🏆 مشاهده برندگان",
                      "callback_data": f"lt_win_{lid}"}])
        btns.append([{"text": "📤 خروجی Excel",
                      "callback_data": f"lt_exp_{lid}"},
                     {"text": "🔄 اجرای مجدد",
                      "callback_data": f"lt_reset_{lid}"}])
    else:
        if mode["needs_score"] and lot.get("source") == "event":
            lines += ["", "⚠️ این روش برای رویداد نمره ندارد — «تصادفی» بگذارید"]
        can_draw = (lot.get("winner_mode") != "disabled" and parts and prizes)
        if can_draw:
            btns.append([{"text": f"🎲 اجرای قرعه‌کشی ({len(parts)} نفر)",
                          "callback_data": f"lt_draw_{lid}"}])
        elif not parts:
            lines += ["", "⚠️ هنوز شرکت‌کننده‌ای نیست"]
        elif not prizes:
            lines += ["", "⚠️ حداقل یک جایزه تعریف کنید"]

    btns += [
        [{"text": "🎯 روش انتخاب برنده", "callback_data": f"lt_mode_{lid}"}],
        [{"text": "🎁 مدیریت جوایز", "callback_data": f"lt_prz_{lid}"}],
        [{"text": "📅 زمان اجرا", "callback_data": f"lt_when_{lid}"}],
        [{"text": "⚙️ شرایط شرکت", "callback_data": f"lt_cond_{lid}"}],
        [{"text": "📢 تنظیمات اطلاع‌رسانی", "callback_data": f"lt_notif_{lid}"}],
    ]
    back = (f"fbv_{lot['form_id']}" if lot.get("source") == "form"
            else f"evx_{lot['event_id']}")
    btns.append([{"text": "🔙 بازگشت", "callback_data": back}])

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


# ==================== روش انتخاب ====================
def show_modes(cid, uid, lid):
    if not _guard(cid, uid):
        return
    lot = get_lottery(lid)
    if not lot:
        return send(cid, "❌ یافت نشد")
    cur = lot.get("winner_mode") or "random"
    is_event = lot.get("source") == "event"

    lines = ["🎯 روش انتخاب برنده", "━━━━━━━━━━━━━━", ""]
    btns = []
    for k, m in WINNER_MODES.items():
        mark = "🔘" if k == cur else "⚪"
        warn = ""
        if is_event and (m["needs_score"] or m["needs_time"]):
            warn = "  ⚠️ فقط برای فرم"
        lines += [f"{mark} {m['icon']} {m['name']}{warn}",
                  f"     {m['desc']}", ""]
        btns.append([{"text": f"{mark} {m['icon']} {m['name']}",
                      "callback_data": f"lt_setm_{k}_{lid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"lt_v_{lid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_mode(cid, uid, mode, lid):
    if not _guard(cid, uid):
        return
    if mode not in WINNER_MODES:
        return send(cid, "❌ روش نامعتبر")
    lot = get_lottery(lid)
    if not lot:
        return send(cid, "❌ یافت نشد")
    if lot.get("status") == "done":
        return send(cid, "⚠️ قرعه‌کشی اجرا شده — اول «اجرای مجدد» را بزنید")
    db_execute("UPDATE form_lotteries SET winner_mode=?, "
               "updated_at=CURRENT_TIMESTAMP WHERE id=?", (mode, lid))
    log_action(uid, "lottery_mode", {"lid": lid, "mode": mode})
    return show_lottery(cid, uid, lid)


# ==================== زمان اجرا ====================
def show_when(cid, uid, lid):
    if not _guard(cid, uid):
        return
    lot = get_lottery(lid)
    if not lot:
        return send(cid, "❌ یافت نشد")
    cur = lot.get("draw_time") or "manual"

    lines = ["📅 زمان اجرای قرعه‌کشی", "━━━━━━━━━━━━━━", ""]
    btns = []
    for k, d in DRAW_TIMES.items():
        mark = "🔘" if k == cur else "⚪"
        lines.append(f"{mark} {d['icon']} {d['name']}")
        btns.append([{"text": f"{mark} {d['icon']} {d['name']}",
                      "callback_data": f"lt_setw_{k}_{lid}"}])
    if cur == "scheduled":
        lines += ["", f"🗓️ تاریخ: {lot.get('draw_at') or '— تعیین نشده —'}"]
        btns.append([{"text": "🗓️ تعیین تاریخ",
                      "callback_data": f"lt_date_{lid}"}])
    lines += ["", "💡 «بلافاصله بعد از پایان» یعنی وقتی مهلت فرم/رویداد",
              "تمام شد، قرعه‌کشی خودکار اجرا می‌شود."]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"lt_v_{lid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_when(cid, uid, when, lid):
    if not _guard(cid, uid):
        return
    if when not in DRAW_TIMES:
        return send(cid, "❌ نامعتبر")
    db_execute("UPDATE form_lotteries SET draw_time=?, "
               "updated_at=CURRENT_TIMESTAMP WHERE id=?", (when, lid))
    if when == "scheduled":
        return show_when(cid, uid, lid)
    return show_lottery(cid, uid, lid)


def start_date(cid, uid, lid):
    if not _guard(cid, uid):
        return
    if not get_lottery(lid):
        return send(cid, "❌ یافت نشد")
    set_state(uid, STATE_LT_DATE, {"lid": lid}, merge=False)
    send(cid, ("🗓️ تاریخ قرعه‌کشی\n━━━━━━━━━━━━━━\n\n"
               "تاریخ شمسی را بنویسید:\n\nمثال: 1404/06/20\n"
               "یا با ساعت: 1404/06/20 20:00"), kb_cancel())


def handle_date(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = normalize_digits((message.get("text") or "").strip())
    d = get_state_data(uid)
    lid = d.get("lid")

    if text in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_lottery(cid, uid, lid)

    import re
    if not re.match(r"^1[34]\d{2}/\d{1,2}/\d{1,2}( \d{1,2}:\d{2})?$", text):
        return send(cid, "⚠️ قالب درست نیست.\nمثال: 1404/06/20")

    db_execute("UPDATE form_lotteries SET draw_at=?, draw_time='scheduled', "
               "updated_at=CURRENT_TIMESTAMP WHERE id=?", (text, lid))
    clear_state(uid)
    send(cid, f"✅ تاریخ ثبت شد: {text}", kb_remove())
    return show_lottery(cid, uid, lid)


# ==================== جوایز ====================
def show_prizes(cid, uid, lid):
    if not _guard(cid, uid):
        return
    lot = get_lottery(lid)
    if not lot:
        return send(cid, "❌ یافت نشد")
    prizes = get_prizes(lid)

    lines = ["🎁 جوایز قرعه‌کشی", "━━━━━━━━━━━━━━", ""]
    btns = []
    if not prizes:
        lines.append("📭 هنوز جایزه‌ای تعریف نشده")
    for p in prizes:
        pts = f"  🏅 +{p['points_reward']} امتیاز" \
            if int(p.get("points_reward") or 0) else ""
        lines += [f"{p.get('icon') or '🎁'} {p.get('title')}",
                  f"   👥 {p.get('winner_count') or 1} برنده{pts}", ""]
        btns.append([
            {"text": f"{p.get('icon')} {p.get('title')}"[:28],
             "callback_data": f"lt_pv_{p['id']}"},
            {"text": "🗑️", "callback_data": f"lt_pdel_{p['id']}"},
        ])
    lines += [f"🏆 مجموع برندگان: {total_winner_slots(lid)} نفر"]

    btns.append([{"text": "➕ افزودن جایزه", "callback_data": f"lt_padd_{lid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"lt_v_{lid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_add_prize(cid, uid, lid):
    if not _guard(cid, uid):
        return
    if not get_lottery(lid):
        return send(cid, "❌ یافت نشد")
    set_state(uid, STATE_LT_ADD, {"lid": lid}, merge=False)
    send(cid, (
        "➕ افزودن جایزه\n━━━━━━━━━━━━━━\n\n"
        "عنوان جایزه را بنویسید:\n\n"
        "مثال: کارت هدیه ۵ میلیون ریالی\n\n"
        "💡 می‌توانید تعداد برنده و امتیاز را هم\n"
        "با کاما اضافه کنید:\n"
        "«کارت هدیه, 2, 50»\n"
        "(عنوان، تعداد برنده، امتیاز)"
    ), kb_cancel())


def handle_add_prize(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    d = get_state_data(uid)
    lid = d.get("lid")

    if text in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_prizes(cid, uid, lid)
    if not text:
        return send(cid, "⚠️ عنوان جایزه را بنویسید:")

    parts = [x.strip() for x in text.split(",")]
    title = parts[0][:60]
    if not title:
        return send(cid, "⚠️ عنوان نمی‌تواند خالی باشد:")

    count = 1
    points = 0
    if len(parts) > 1:
        try:
            count = max(1, min(100, int(normalize_digits(parts[1]))))
        except (ValueError, TypeError):
            count = 1
    if len(parts) > 2:
        try:
            points = max(0, min(1000, int(normalize_digits(parts[2]))))
        except (ValueError, TypeError):
            points = 0

    n = len(get_prizes(lid))
    icon = MEDALS[n] if n < len(MEDALS) else "🎁"
    db_execute("""INSERT INTO lottery_prizes
        (lottery_id, rank_order, icon, title, winner_count, points_reward)
        VALUES (?,?,?,?,?,?)""", (lid, n + 1, icon, title, count, points))
    clear_state(uid)
    log_action(uid, "lottery_prize", {"lid": lid, "title": title})
    send(cid, f"✅ جایزه «{title}» اضافه شد", kb_remove())
    return show_prizes(cid, uid, lid)


def view_prize(cid, uid, pid):
    if not _guard(cid, uid):
        return
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return send(cid, "❌ نامعتبر")
    p = db_execute("SELECT * FROM lottery_prizes WHERE id=?", (pid,),
                   fetch="one")
    if not p:
        return send(cid, "❌ جایزه یافت نشد")

    lines = [f"{p.get('icon')} {p.get('title')}", "━━━━━━━━━━━━━━", "",
             f"👥 تعداد برنده: {p.get('winner_count') or 1}",
             f"🏅 امتیاز هدیه: {p.get('points_reward') or 0}"]
    if p.get("description"):
        lines += ["", f"📄 {p['description']}"]

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "👥 تعداد برنده", "callback_data": f"ltn_count_{pid}"},
         {"text": "🏅 امتیاز", "callback_data": f"ltn_points_{pid}"}],
        [{"text": "🗑️ حذف جایزه", "callback_data": f"lt_pdel_{pid}"}],
        [{"text": "🔙 جوایز", "callback_data": f"lt_prz_{p['lottery_id']}"}],
    ]})


def start_prize_num(cid, uid, field, pid):
    if not _guard(cid, uid):
        return
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return send(cid, "❌ نامعتبر")
    p = db_execute("SELECT * FROM lottery_prizes WHERE id=?", (pid,),
                   fetch="one")
    if not p or field not in ("count", "points"):
        return send(cid, "❌ نامعتبر")

    set_state(uid, STATE_LT_NUM, {"pid": pid, "field": field}, merge=False)
    q = ("👥 چند نفر این جایزه را ببرند؟" if field == "count"
         else "🏅 چند امتیاز به برنده داده شود؟\n\n۰ = بدون امتیاز")
    cur = p.get("winner_count") if field == "count" else p.get("points_reward")
    send(cid, f"{q}\n\n📄 مقدار فعلی: {cur or 0}", kb_cancel())


def handle_prize_num(message):
    """
    دریافت عدد — هم برای جایزه (count/points) و هم حداقل نمره قرعه‌کشی.

    ⚠️ start_min_score کلید `lid` می‌گذارد نه `pid`، پس هر دو حالت
       اینجا مدیریت می‌شود.
    """
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = normalize_digits((message.get("text") or "").strip())
    d = get_state_data(uid)
    pid, lid, field = d.get("pid"), d.get("lid"), d.get("field")
    is_lot = field == "min_score"

    def _back_page():
        if is_lot:
            return show_conditions(cid, uid, lid)
        return view_prize(cid, uid, pid)

    if text in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return _back_page()

    import re
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return send(cid, "⚠️ فقط عدد بفرستید:")
    val = int(digits)

    if is_lot:
        val = max(0, min(100000, val))
        db_execute("UPDATE form_lotteries SET min_score=?, "
                   "updated_at=CURRENT_TIMESTAMP WHERE id=?", (val, lid))
    elif field == "count":
        val = max(1, min(100, val))
        db_execute("UPDATE lottery_prizes SET winner_count=? WHERE id=?",
                   (val, pid))
    else:
        val = max(0, min(1000, val))
        db_execute("UPDATE lottery_prizes SET points_reward=? WHERE id=?",
                   (val, pid))
    clear_state(uid)
    send(cid, f"✅ ذخیره شد: {val}", kb_remove())
    return _back_page()


def delete_prize(cid, uid, pid):
    if not _guard(cid, uid):
        return
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return send(cid, "❌ نامعتبر")
    p = db_execute("SELECT * FROM lottery_prizes WHERE id=?", (pid,),
                   fetch="one")
    if not p:
        return send(cid, "❌ یافت نشد")
    lid = p["lottery_id"]
    db_execute("DELETE FROM lottery_prizes WHERE id=?", (pid,))
    send(cid, f"🗑️ جایزه «{p.get('title')}» حذف شد")
    return show_prizes(cid, uid, lid)


# ==================== شرایط شرکت ====================
def show_conditions(cid, uid, lid):
    if not _guard(cid, uid):
        return
    lot = get_lottery(lid)
    if not lot:
        return send(cid, "❌ یافت نشد")
    is_event = lot.get("source") == "event"

    lines = ["⚙️ شرایط شرکت در قرعه‌کشی", "━━━━━━━━━━━━━━", "",
             f"📊 حداقل نمره: {lot.get('min_score') or 0}"
             + ("  (فقط فرم)" if is_event else ""),
             f"🔁 حذف برندگان قبلی: "
             f"{'✅' if lot.get('exclude_previous') else '❌'}"]
    if is_event:
        lines.append(f"✋ فقط حاضرین: "
                     f"{'✅' if lot.get('only_attended') else '❌'}")

    parts = get_participants(lot)
    lines += ["", f"👥 با این شرایط: {len(parts)} نفر واجد شرایط‌اند"]

    btns = []
    if not is_event:
        btns.append([{"text": "📊 حداقل نمره",
                      "callback_data": f"ltn_minscore_{lid}"}])
    btns.append([{"text": f"🔁 حذف برندگان قبلی "
                          f"{'✅' if lot.get('exclude_previous') else '❌'}",
                  "callback_data": f"lt_tog_exclude_previous_{lid}"}])
    if is_event:
        btns.append([{"text": f"✋ فقط حاضرین "
                              f"{'✅' if lot.get('only_attended') else '❌'}",
                      "callback_data": f"lt_tog_only_attended_{lid}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"lt_v_{lid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_min_score(cid, uid, lid):
    if not _guard(cid, uid):
        return
    if not get_lottery(lid):
        return send(cid, "❌ یافت نشد")
    set_state(uid, STATE_LT_NUM, {"lid": lid, "field": "min_score"},
              merge=False)
    send(cid, ("📊 حداقل نمره برای شرکت در قرعه‌کشی\n\n"
               "۰ = همه می‌توانند شرکت کنند"), kb_cancel())


def show_notif(cid, uid, lid):
    if not _guard(cid, uid):
        return
    lot = get_lottery(lid)
    if not lot:
        return send(cid, "❌ یافت نشد")

    keys = [("notify_winners", "🎉 پیام به برندگان"),
            ("notify_all", "📢 پیام به همه شرکت‌کنندگان"),
            ("cert_winners", "🎓 صدور گواهینامه برای برندگان"),
            ("show_leaderboard", "🏆 نمایش جدول امتیازات به کاربر")]

    lines = ["📢 تنظیمات اطلاع‌رسانی", "━━━━━━━━━━━━━━", ""]
    btns = []
    for k, nm in keys:
        on = int(lot.get(k) or 0)
        lines.append(f"{'✅' if on else '❌'} {nm}")
        btns.append([{"text": f"{'✅' if on else '⬜'} {nm}",
                      "callback_data": f"lt_tog_{k}_{lid}"}])
    lines += ["", "💡 متن پیام‌ها از ⚙️ تنظیمات › 📝 مدیریت متن‌ها",
              "قابل تغییر است."]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"lt_v_{lid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_flag(cid, uid, key, lid):
    if not _guard(cid, uid):
        return
    allowed = {"notify_winners", "notify_all", "cert_winners",
               "show_leaderboard", "exclude_previous", "only_attended",
               "is_active"}
    if key not in allowed:
        return send(cid, "❌ نامعتبر")
    lot = get_lottery(lid)
    if not lot:
        return send(cid, "❌ یافت نشد")
    new = 0 if int(lot.get(key) or 0) else 1
    db_execute(f"UPDATE form_lotteries SET {key}=?, "
               "updated_at=CURRENT_TIMESTAMP WHERE id=?", (new, lid))
    if key in ("exclude_previous", "only_attended"):
        return show_conditions(cid, uid, lid)
    return show_notif(cid, uid, lid)


# ==================== 🎲 اجرای قرعه‌کشی ====================
def confirm_draw(cid, uid, lid):
    """⚠️ تأیید نهایی قبل از اجرا"""
    if not _guard(cid, uid):
        return
    lot = get_lottery(lid)
    if not lot:
        return send(cid, "❌ یافت نشد")
    if lot.get("status") == "done":
        return send(cid, "⚠️ این قرعه‌کشی قبلاً اجرا شده است")

    parts = get_participants(lot)
    prizes = get_prizes(lid)
    slots = total_winner_slots(lid)
    mode = WINNER_MODES.get(lot.get("winner_mode") or "random",
                            WINNER_MODES["random"])

    if not parts:
        return send(cid, "⚠️ هیچ شرکت‌کننده واجد شرایطی نیست")
    if not prizes:
        return send(cid, "⚠️ حداقل یک جایزه تعریف کنید")

    lines = [
        "🎲 اجرای قرعه‌کشی", "━━━━━━━━━━━━━━", "",
        "📊 اطلاعات:",
        f"├── 👥 شرکت‌کنندگان: {len(parts)} نفر",
        f"├── 🎯 روش: {mode['icon']} {mode['name']}",
        f"├── 🎁 تعداد جوایز: {len(prizes)}",
        f"└── 🏆 تعداد کل برندگان: {min(slots, len(parts))}",
        "",
    ]
    if slots > len(parts):
        lines += [f"⚠️ {slots} جایزه دارید ولی فقط {len(parts)} شرکت‌کننده —",
                  "   بعضی جوایز بدون برنده می‌مانند.", ""]

    lines += ["⚠️ تأیید نهایی", "",
              "با اجرای قرعه‌کشی، برندگان انتخاب شده و",
              "اطلاع‌رسانی خودکار انجام می‌شود.", "",
              "🔒 این کار برگشت‌ناپذیر است."]

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🎲 بله، اجرا کن", "callback_data": f"lt_go_{lid}"}],
        [{"text": "❌ انصراف", "callback_data": f"lt_v_{lid}"}],
    ]})


def run_draw(cid, uid, lid, silent=False):
    """
    🎲 اجرای واقعی قرعه‌کشی.

    🔒 قفل اتمیک: وضعیت فقط وقتی 'pending' باشد به 'done' می‌رود،
       پس دو کلیک همزمان دو بار قرعه‌کشی نمی‌کند.
    """
    lot = get_lottery(lid)
    if not lot:
        if not silent:
            send(cid, "❌ یافت نشد")
        return None
    if not silent and not _guard(cid, uid):
        return None
    if lot.get("status") == "done":
        if not silent:
            send(cid, "⚠️ قبلاً اجرا شده است")
        return None
    if (lot.get("winner_mode") or "random") == "disabled":
        if not silent:
            send(cid, "⚠️ روش انتخاب برنده «غیرفعال» است")
        return None

    parts = get_participants(lot)
    prizes = get_prizes(lid)
    if not parts or not prizes:
        if not silent:
            send(cid, "⚠️ شرکت‌کننده یا جایزه‌ای نیست")
        return None

    # 🔒 قفل اتمیک
    db_execute("""UPDATE form_lotteries SET status='done',
        drawn_at=CURRENT_TIMESTAMP, drawn_by=?, participants_count=?,
        updated_at=CURRENT_TIMESTAMP
        WHERE id=? AND status<>'done'""", (uid, len(parts), lid))
    fresh = get_lottery(lid)
    if not fresh or fresh.get("status") != "done":
        if not silent:
            send(cid, "⚠️ اجرا ناموفق بود، دوباره تلاش کنید")
        return None
    # مطمئن شویم برنده تکراری از اجرای قبلی نمانده
    db_execute("DELETE FROM lottery_winners WHERE lottery_id=?", (lid,))

    mode = lot.get("winner_mode") or "random"
    ranked = rank_participants(parts, mode)

    # توزیع برندگان بین جوایز
    winners = []
    idx = rank_no = 0
    for p in prizes:
        need = int(p.get("winner_count") or 1)
        for _ in range(need):
            if idx >= len(ranked):
                break
            person = ranked[idx]
            idx += 1
            rank_no += 1
            code = gen_code()
            db_execute("""INSERT INTO lottery_winners
                (lottery_id, prize_id, bale_user_id, response_id,
                 registration_id, rank_no, score, time_taken, code)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (lid, p["id"], person["uid"], person.get("response_id"),
                 person.get("registration_id"), rank_no, person["score"],
                 person["time_taken"], code))
            winners.append({**person, "prize": p, "rank": rank_no,
                            "code": code})

    log_action(uid, "lottery_draw",
               {"lid": lid, "winners": len(winners), "participants": len(parts)})

    # 🏅 امتیاز جایزه
    for w in winners:
        pts = int((w["prize"].get("points_reward") or 0))
        if pts > 0:
            try:
                import occasions as oc
                real, _ = oc.cap_points(w["uid"], pts)
                if real > 0:
                    db_execute("UPDATE users SET total_points="
                               "COALESCE(total_points,0)+? "
                               "WHERE bale_user_id=?", (real, w["uid"]))
            except Exception as e:
                log(f"⚠️ امتیاز جایزه: {e}")

    _notify(lot, winners, parts)

    if not silent:
        return show_winners(cid, uid, lid, just_drawn=True)
    return winners


def _notify(lot, winners, parts):
    """📢 اطلاع‌رسانی نتیجه"""
    title = lot.get("title") or "قرعه‌کشی"
    wlist = "\n".join(
        f"{w['prize'].get('icon') or '🏆'} {w['name']} — "
        f"{w['prize'].get('title')}" for w in winners) or "—"

    win_ids = {w["uid"] for w in winners}

    # به برندگان
    if int(lot.get("notify_winners") or 0):
        for w in winners:
            try:
                from occasions import polite_name
                u = db_execute("SELECT * FROM users WHERE bale_user_id=?",
                               (w["uid"],), fetch="one") or {}
                dear = polite_name(u)
            except Exception:
                dear = w["name"]
            try:
                send(w["uid"], render(
                    "lt_txt_winner", dear=dear, title=title,
                    prize=w["prize"].get("title"),
                    prize_icon=w["prize"].get("icon") or "🎁",
                    rank=w["rank"], code=w["code"]))
                db_execute("UPDATE lottery_winners SET notified=1 "
                           "WHERE lottery_id=? AND bale_user_id=?",
                           (lot["id"], w["uid"]))
            except Exception as e:
                log(f"⚠️ اعلام به برنده: {e}")

    # به بقیه شرکت‌کنندگان
    if int(lot.get("notify_all") or 0):
        for p in parts:
            if p["uid"] in win_ids:
                continue
            try:
                from occasions import polite_name
                u = db_execute("SELECT * FROM users WHERE bale_user_id=?",
                               (p["uid"],), fetch="one") or {}
                dear = polite_name(u)
            except Exception:
                dear = p["name"]
            try:
                send(p["uid"], render("lt_txt_loser", dear=dear,
                                      title=title, list=wlist))
            except Exception as e:
                log(f"⚠️ اعلام عمومی: {e}")

    # 🎓 گواهینامه برندگان
    if int(lot.get("cert_winners") or 0) and lot.get("source") == "event":
        try:
            import attendance as att
            for w in winners:
                att.issue_certificate(w["uid"], w["uid"], lot.get("event_id"),
                                      target_uid=w["uid"], silent=True)
        except Exception as e:
            log(f"⚠️ گواهینامه برنده: {e}")


def show_winners(cid, uid, lid, just_drawn=False):
    """🏆 نمایش برندگان"""
    if not _guard(cid, uid):
        return
    lot = get_lottery(lid)
    if not lot:
        return send(cid, "❌ یافت نشد")
    winners = get_winners(lid)

    if just_drawn:
        head = ["🎉 قرعه‌کشی انجام شد!", "━━━━━━━━━━━━━━", ""]
    else:
        head = [f"🏆 برندگان «{lot.get('title')}»", "━━━━━━━━━━━━━━", ""]

    lines = head
    if not winners:
        lines.append("📭 برنده‌ای ثبت نشده")
    for w in winners:
        nm = f"{w.get('first_name') or ''} {w.get('last_name') or ''}".strip()
        lines += [
            f"{w.get('prize_icon') or '🏆'} رتبه {w.get('rank_no')}:",
            f"   👤 {nm or '—'}",
            f"   📱 {w.get('mobile') or '—'}",
            f"   🎁 {w.get('prize_title') or '—'}",
        ]
        if int(w.get("score") or 0):
            lines.append(f"   📊 نمره: {w['score']}")
        if int(w.get("time_taken") or 0):
            m, s = divmod(int(w["time_taken"]), 60)
            lines.append(f"   ⏱️ زمان: {m:02d}:{s:02d}")
        lines.append(f"   🔖 {w.get('code') or '—'}")
        lines.append("")

    if just_drawn:
        n_notif = sum(1 for w in winners if w.get("notified"))
        lines += ["📢 اطلاع‌رسانی:",
                  f"✅ به برندگان: {n_notif}/{len(winners)}"]
        if int(lot.get("notify_all") or 0):
            lines.append(f"✅ به شرکت‌کنندگان: "
                         f"{lot.get('participants_count') or 0} نفر")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "📤 خروجی Excel", "callback_data": f"lt_exp_{lid}"}],
        [{"text": "🔙 قرعه‌کشی", "callback_data": f"lt_v_{lid}"}],
    ]})


def reset_draw(cid, uid, lid, confirmed=False):
    """🔄 اجرای مجدد — پاک کردن برندگان قبلی"""
    if not _guard(cid, uid):
        return
    lot = get_lottery(lid)
    if not lot:
        return send(cid, "❌ یافت نشد")

    if not confirmed:
        return send_or_edit(cid, (
            "🔄 اجرای مجدد قرعه‌کشی\n━━━━━━━━━━━━━━\n\n"
            "⚠️ برندگان فعلی پاک می‌شوند و قرعه‌کشی\n"
            "از نو انجام خواهد شد.\n\n"
            "❓ مطمئنید؟"
        ), {"inline_keyboard": [
            [{"text": "🔄 بله، پاک کن", "callback_data": f"lt_rsty_{lid}"}],
            [{"text": "❌ انصراف", "callback_data": f"lt_v_{lid}"}]]})

    db_execute("DELETE FROM lottery_winners WHERE lottery_id=?", (lid,))
    db_execute("""UPDATE form_lotteries SET status='pending', drawn_at=NULL,
        drawn_by=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?""", (lid,))
    log_action(uid, "lottery_reset", {"lid": lid})
    send(cid, "🔄 قرعه‌کشی بازنشانی شد")
    return show_lottery(cid, uid, lid)


def export_winners(cid, uid, lid):
    """📤 خروجی Excel برندگان"""
    if not _guard(cid, uid):
        return
    lot = get_lottery(lid)
    if not lot:
        return send(cid, "❌ یافت نشد")
    winners = get_winners(lid)
    if not winners:
        return send(cid, "📭 برنده‌ای برای خروجی نیست")

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        return send(cid, "⚠️ برای خروجی Excel نیاز به openpyxl است:\n"
                         "pip install openpyxl")

    wb = Workbook()
    ws = wb.active
    ws.title = "برندگان"
    ws.sheet_view.rightToLeft = True

    heads = ["رتبه", "نام", "موبایل", "جایزه", "امتیاز جایزه",
             "نمره", "زمان (ثانیه)", "کد پیگیری", "اطلاع داده شد"]
    ws.append(heads)
    for i, _ in enumerate(heads, 1):
        c = ws.cell(row=1, column=i)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="6A1B9A")
        c.alignment = Alignment(horizontal="center")

    for w in winners:
        nm = f"{w.get('first_name') or ''} {w.get('last_name') or ''}".strip()
        ws.append([
            w.get("rank_no"), nm or "—", w.get("mobile") or "—",
            w.get("prize_title") or "—", w.get("points_reward") or 0,
            w.get("score") or 0, w.get("time_taken") or 0,
            w.get("code") or "—", "بله" if w.get("notified") else "خیر",
        ])

    for col, wd in zip("ABCDEFGHI", (8, 24, 16, 24, 12, 10, 14, 16, 12)):
        ws.column_dimensions[col].width = wd
    ws.freeze_panes = "A2"

    from pathlib import Path
    from config import IMPORT_DIR
    Path(IMPORT_DIR).mkdir(parents=True, exist_ok=True)
    safe = "".join(ch for ch in str(lot.get("title") or "lottery")
                   if ch.isalnum() or ch in " -_")[:30]
    out = Path(IMPORT_DIR) / \
        f"lottery_{lid}_{safe}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    try:
        wb.save(out)
    except Exception as e:
        return send(cid, f"❌ خطا در ساخت فایل: {user_error_message(e)}")

    r = send_document(cid, str(out),
                      f"🏆 برندگان «{lot.get('title')}» ({len(winners)} نفر)")
    if not r or not r.get("ok"):
        send(cid, f"⚠️ ارسال ناموفق. فایل در سرور:\n{out}")
    log_action(uid, "lottery_export", {"lid": lid})


# ==================== نمای کاربر ====================
def user_result(cid, uid, source, oid):
    """🎯 نتیجه قرعه‌کشی از دید کاربر"""
    lot = find_lottery(source, oid)
    if not lot or not int(lot.get("is_active") or 0):
        return send(cid, "🎲 برای این مورد قرعه‌کشی تعریف نشده است")

    title = lot.get("title") or "قرعه‌کشی"
    if lot.get("status") != "done":
        when = lot.get("draw_at") or \
            DRAW_TIMES.get(lot.get("draw_time") or "manual",
                           DRAW_TIMES["manual"])["name"]
        return send_or_edit(cid, render("lt_txt_pending", when=when),
                            {"inline_keyboard": [
                                [{"text": "🔙 بازگشت",
                                  "callback_data": "back_main"}]]})

    winners = get_winners(lot["id"])
    mine = [w for w in winners if w.get("bale_user_id") == uid]

    lines = [f"🎲 نتیجه قرعه‌کشی «{title}»", "━━━━━━━━━━━━━━", ""]
    if mine:
        w = mine[0]
        lines += ["🎉 تبریک! شما برنده شدید!", "",
                  f"{w.get('prize_icon') or '🎁'} جایزه: {w.get('prize_title')}",
                  f"🏅 رتبه: {w.get('rank_no')}",
                  f"🔖 کد پیگیری: {w.get('code')}", ""]
    lines.append("🏆 برندگان:")
    for w in winners:
        nm = f"{w.get('first_name') or ''} {w.get('last_name') or ''}".strip()
        me = " ← شما" if w.get("bale_user_id") == uid else ""
        lines.append(f"{w.get('prize_icon') or '🏆'} {nm or '—'} — "
                     f"{w.get('prize_title')}{me}")
    if not mine:
        lines += ["", "🌱 این بار شانس با شما یار نبود،",
                  "ولی از شرکت شما سپاسگزاریم."]

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": "back_main"}]]})


# ==================== اجرای خودکار (زمان‌بندی) ====================
def check_scheduled():
    """
    ⏰ قرعه‌کشی‌هایی که وقتشان رسیده را اجرا می‌کند.
    از حلقه پس‌زمینه main.py صدا زده می‌شود.

    خروجی: (تعداد اجراشده، لیست عنوان‌ها)
    """
    done, names = 0, []

    # ۱) زمان‌بندی‌شده با تاریخ مشخص
    try:
        from occasions import today_jalali
        jy, jm, jd = today_jalali()
        today = f"{jy}/{jm:02d}/{jd:02d}"
    except Exception:
        today = ""

    rows = db_execute("""SELECT * FROM form_lotteries
        WHERE status='pending' AND is_active=1
          AND draw_time='scheduled' AND draw_at IS NOT NULL""",
        fetch="all") or []
    for lot in rows:
        raw = str(lot.get("draw_at") or "").split(" ")[0]
        parts = raw.split("/")
        if len(parts) != 3 or not today:
            continue
        try:
            norm = f"{int(parts[0])}/{int(parts[1]):02d}/{int(parts[2]):02d}"
        except (ValueError, TypeError):
            continue
        if norm > today:
            continue
        w = run_draw(lot.get("created_by") or SUPER_ADMIN_ID,
                     lot.get("created_by") or SUPER_ADMIN_ID,
                     lot["id"], silent=True)
        if w:
            done += 1
            names.append(lot.get("title") or f"#{lot['id']}")

    # ۲) «بلافاصله بعد از پایان» — فرم/رویداد بسته شده باشد
    rows2 = db_execute("""SELECT * FROM form_lotteries
        WHERE status='pending' AND is_active=1 AND draw_time='on_close'""",
        fetch="all") or []
    for lot in rows2:
        closed = False
        if lot.get("source") == "form" and lot.get("form_id"):
            f = db_execute("SELECT status, end_at FROM forms WHERE id=?",
                           (lot["form_id"],), fetch="one")
            if f and (f.get("status") in ("closed", "archived")):
                closed = True
        elif lot.get("event_id"):
            e = db_execute("SELECT status FROM events WHERE id=?",
                           (lot["event_id"],), fetch="one")
            if e and e.get("status") == "finished":
                closed = True
        if not closed:
            continue
        w = run_draw(lot.get("created_by") or SUPER_ADMIN_ID,
                     lot.get("created_by") or SUPER_ADMIN_ID,
                     lot["id"], silent=True)
        if w:
            done += 1
            names.append(lot.get("title") or f"#{lot['id']}")

    if done:
        log(f"🎲 {done} قرعه‌کشی خودکار اجرا شد")
    return done, names


# ==================== لیست کلی (پنل ادمین) ====================
def show_all(cid, uid, page=0):
    """🎲 همه قرعه‌کشی‌ها"""
    if not _guard(cid, uid):
        return
    rows = db_execute("""SELECT l.*,
        (SELECT COUNT(*) FROM lottery_winners w WHERE w.lottery_id=l.id) nw
        FROM form_lotteries l ORDER BY l.id DESC LIMIT 100""",
        fetch="all") or []

    n_pend = sum(1 for r in rows if r.get("status") == "pending")
    n_done = sum(1 for r in rows if r.get("status") == "done")

    lines = ["🎲 قرعه‌کشی‌ها", "━━━━━━━━━━━━━━",
             f"📊 کل: {len(rows)}  |  ⏳ در انتظار: {n_pend}  |  "
             f"✅ اجراشده: {n_done}", ""]
    btns = []
    if not rows:
        lines += ["📭 هنوز قرعه‌کشی‌ای تعریف نشده", "",
                  "💡 از داخل هر فرم یا رویداد می‌توانید",
                  "قرعه‌کشی تعریف کنید."]

    per = 8
    pages = max(1, (len(rows) + per - 1) // per)
    page = max(0, min(int(page or 0), pages - 1))
    for r in rows[page * per:(page + 1) * per]:
        st = {"pending": "⏳", "done": "✅",
              "cancelled": "⛔"}.get(r.get("status"), "▫️")
        src = "📝" if r.get("source") == "form" else "🎉"
        m = WINNER_MODES.get(r.get("winner_mode") or "random",
                             WINNER_MODES["random"])
        lines += [f"{st} {src} {r.get('title') or '—'}",
                  f"   {m['icon']} {m['name']}"
                  + (f"  |  🏆 {r['nw']} برنده" if r.get("nw") else ""), ""]
        btns.append([{"text": f"{st} {r.get('title') or '—'}"[:40],
                      "callback_data": f"lt_v_{r['id']}"}])

    if pages > 1:
        nav = []
        if page > 0:
            nav.append({"text": "⬅️", "callback_data": f"lt_pg_{page-1}"})
        nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
        if page < pages - 1:
            nav.append({"text": "➡️", "callback_data": f"lt_pg_{page+1}"})
        btns.append(nav)
    btns.append([{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})
