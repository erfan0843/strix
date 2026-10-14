"""
📱 تیکت پشتیبانی — فاز ۱۲

طبق فایل معماری (خط ۳۵۶۱۳):
  • کاربر تیکت می‌سازد با موضوع و دسته
  • گفتگوی دوطرفه داخل تیکت
  • وضعیت: باز / در حال بررسی / پاسخ داده / بسته
  • گزارش باگ و پیشنهاد ویژگی هم همین‌جا
"""
import random
import string
from datetime import datetime

from config import SUPER_ADMIN_ID
from database import (
    db_execute, db_scalar, ensure_table, get_setting, set_setting, log,
)
from auth import (
    get_user, set_state, get_state_data, clear_state, log_action,
    is_admin as _is_admin,
)
from bale_api import send, send_or_edit, kb_cancel, kb_remove, BTN_BACK
import permissions as perm
import jalali as _jd

STATE_TK_NEW = "tk_new"
STATE_TK_REPLY = "tk_reply"

TICKETS_PER_PAGE = 6

TICKET_SCHEMA = {
    "code": "TEXT",
    "bale_user_id": "INTEGER NOT NULL",
    "category": "TEXT DEFAULT 'support'",
    "subject": "TEXT",
    "priority": "TEXT DEFAULT 'normal'",
    "status": "TEXT DEFAULT 'open'",
    "assigned_to": "INTEGER",
    "closed_by": "INTEGER",
    "closed_at": "TEXT",
    "rating": "INTEGER",
    "last_reply_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "unread_admin": "INTEGER DEFAULT 1",
    "unread_user": "INTEGER DEFAULT 0",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

MESSAGE_SCHEMA = {
    "ticket_id": "INTEGER NOT NULL",
    "sender_id": "INTEGER",
    "is_admin": "INTEGER DEFAULT 0",
    "body": "TEXT",
    "file_id": "TEXT",
    "file_type": "TEXT",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

CATEGORIES = {
    "support":  {"icon": "💬", "name": "پشتیبانی عمومی"},
    "payment":  {"icon": "💳", "name": "مشکل پرداخت"},
    "event":    {"icon": "🎉", "name": "رویداد و ثبت‌نام"},
    "bug":      {"icon": "🐛", "name": "گزارش مشکل فنی"},
    "feature":  {"icon": "💡", "name": "پیشنهاد ویژگی"},
    "other":    {"icon": "📄", "name": "سایر"},
}

STATUSES = {
    "open":     {"icon": "🟢", "name": "باز"},
    "progress": {"icon": "🟡", "name": "در حال بررسی"},
    "answered": {"icon": "🔵", "name": "پاسخ داده شد"},
    "closed":   {"icon": "⚫", "name": "بسته"},
}

PRIORITIES = {
    "low":    {"icon": "🔽", "name": "کم"},
    "normal": {"icon": "➖", "name": "عادی"},
    "high":   {"icon": "🔺", "name": "زیاد"},
    "urgent": {"icon": "🚨", "name": "فوری"},
}


def init_ticket_tables():
    ensure_table("tickets", TICKET_SCHEMA)
    ensure_table("ticket_messages", MESSAGE_SCHEMA)
    for q in [
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_tk_code ON tickets(code)",
        "CREATE INDEX IF NOT EXISTS idx_tk_user ON tickets(bale_user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_tk_status ON tickets(status)",
        "CREATE INDEX IF NOT EXISTS idx_tkm ON ticket_messages(ticket_id)",
    ]:
        db_execute(q)
    log("✅ جدول‌های تیکت آماده شد")


def _guard(cid, uid):
    if not _is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    return True


def gen_code():
    for _ in range(30):
        c = "TK" + "".join(random.choices(string.digits, k=6))
        if not db_execute("SELECT id FROM tickets WHERE code=?", (c,),
                          fetch="one"):
            return c
    return f"TK{int(datetime.now().timestamp())}"


def get_ticket(tid):
    try:
        return db_execute("SELECT * FROM tickets WHERE id=?", (int(tid),),
                          fetch="one")
    except (TypeError, ValueError):
        return None


def _cat(k):
    return CATEGORIES.get(k, CATEGORIES["other"])


def _st(k):
    return STATUSES.get(k, STATUSES["open"])


# ==================== 👤 نمای کاربر ====================
def show_my_tickets(cid, uid):
    """📱 تیکت‌های من"""
    rows = db_execute("""SELECT * FROM tickets WHERE bale_user_id=?
        ORDER BY id DESC LIMIT 15""", (uid,), fetch="all") or []
    open_n = sum(1 for r in rows if r.get("status") != "closed")

    hours = get_setting("support_hours", "")
    lines = ["📱 تیکت پشتیبانی", "━━━━━━━━━━━━━━", ""]
    if hours:
        lines += [f"⏰ ساعت پاسخگویی:\n{hours}", ""]
    lines.append(f"📊 تیکت‌های شما: {len(rows)}  (باز: {open_n})")
    lines.append("")

    btns = []
    if rows:
        for r in rows[:8]:
            s = _st(r.get("status"))
            c = _cat(r.get("category"))
            unread = " 🔴" if r.get("unread_user") else ""
            lines.append(f"{s['icon']} #{r.get('code')} — {c['icon']} "
                         f"{r.get('subject') or '(بدون موضوع)'}{unread}")
            lines.append(f"   {s['name']}  |  "
                         f"{_jd.fmt(r.get('created_at'), 'date')}")
            btns.append([{"text": f"{s['icon']} #{r.get('code')}"
                                  f" {str(r.get('subject') or '')[:24]}{unread}",
                          "callback_data": f"tk_v_{r['id']}"}])
    else:
        lines.append("📭 هنوز تیکتی نساخته‌اید")

    btns.append([{"text": "➕ تیکت جدید", "callback_data": "tk_new"}])
    btns.append([{"text": "🔙 پشتیبانی", "callback_data": "u_support"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_new(cid, uid):
    """➕ انتخاب دسته تیکت"""
    u = get_user(uid)
    if not u:
        return send(cid, "⚠️ ابتدا /start را بزنید")

    # جلوگیری از اسپم
    open_n = db_scalar("""SELECT COUNT(*) FROM tickets
        WHERE bale_user_id=? AND status<>'closed'""", (uid,))
    mx = int(get_setting("ticket_max_open", "3") or 3)
    if open_n >= mx:
        return send_or_edit(cid, (
            f"⚠️ شما {open_n} تیکت باز دارید\n\n"
            f"حداکثر {mx} تیکت باز مجاز است.\n"
            f"لطفاً ابتدا تیکت‌های قبلی را ببندید."
        ), {"inline_keyboard": [
            [{"text": "📱 تیکت‌های من", "callback_data": "tk_my"}]]})

    btns = [[{"text": f"{v['icon']} {v['name']}",
              "callback_data": f"tk_cat_{k}"}] for k, v in CATEGORIES.items()]
    btns.append([{"text": "🔙 بازگشت", "callback_data": "tk_my"}])
    return send_or_edit(cid, (
        "➕ تیکت جدید\n━━━━━━━━━━━━━━\n\n"
        "موضوع درخواست شما در چه زمینه‌ای است؟"
    ), {"inline_keyboard": btns})


def pick_category(cid, uid, cat):
    if cat not in CATEGORIES:
        return send(cid, "❌ دسته نامعتبر")
    c = CATEGORIES[cat]
    set_state(uid, STATE_TK_NEW, {"cat": cat, "step": "subject"}, merge=False)
    return send(cid, (
        f"{c['icon']} {c['name']}\n━━━━━━━━━━━━━━\n\n"
        f"📝 موضوع تیکت را در یک خط بنویسید:\n\n"
        f"مثال: مشکل در پرداخت کارگاه فن بیان"
    ), kb_cancel())


def handle_new(message):
    """دریافت موضوع سپس متن تیکت"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    d = get_state_data(uid)
    step = d.get("step")

    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_my_tickets(cid, uid)

    if step == "subject":
        if len(text) < 3:
            return send(cid, "⚠️ موضوع باید حداقل ۳ حرف باشد:", kb_cancel())
        set_state(uid, STATE_TK_NEW,
                  {"cat": d.get("cat"), "subject": text[:120], "step": "body"},
                  merge=False)
        return send(cid, (
            f"📝 موضوع: {text[:120]}\n\n"
            f"حالا توضیحات کامل را بنویسید:\n\n"
            f"💡 هرچه دقیق‌تر بنویسید، سریع‌تر کمکتان می‌کنیم.\n"
            f"📎 می‌توانید عکس هم بفرستید."
        ), kb_cancel())

    if step == "body":
        return _create(cid, uid, d, text)

    clear_state(uid)
    return send(cid, "⚠️ خطای مرحله", kb_remove())


def handle_new_photo(message):
    """عکس به‌عنوان بدنه تیکت"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    d = get_state_data(uid)
    if d.get("step") != "body":
        return send(cid, "⚠️ ابتدا موضوع را بنویسید", kb_cancel())
    photos = message.get("photo") or []
    fid = photos[-1].get("file_id") if photos else None
    cap = (message.get("caption") or "").strip() or "(تصویر پیوست)"
    return _create(cid, uid, d, cap, fid, "photo")


def _create(cid, uid, d, body, file_id=None, file_type=None):
    """ساخت تیکت"""
    code = gen_code()
    tid = db_execute("""INSERT INTO tickets
        (code, bale_user_id, category, subject, status, unread_admin)
        VALUES (?,?,?,?, 'open', 1)""",
        (code, uid, d.get("cat") or "support", d.get("subject") or ""))
    if not tid:
        clear_state(uid)
        return send(cid, "❌ خطا در ساخت تیکت", kb_remove())

    db_execute("""INSERT INTO ticket_messages
        (ticket_id, sender_id, is_admin, body, file_id, file_type)
        VALUES (?,?,0,?,?,?)""", (tid, uid, body[:3000], file_id, file_type))
    clear_state(uid)
    log_action(uid, "ticket_created", {"code": code})

    u = get_user(uid) or {}
    c = _cat(d.get("cat"))
    send(cid, (
        f"✅ تیکت شما ثبت شد\n━━━━━━━━━━━━━━\n\n"
        f"🎫 شماره پیگیری: #{code}\n"
        f"{c['icon']} دسته: {c['name']}\n"
        f"📝 موضوع: {d.get('subject')}\n\n"
        f"⏳ به‌زودی پاسخ می‌دهیم."
    ), kb_remove())

    # اعلان به ادمین‌ها
    nm = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip()
    _notify_admins((
        f"🎫 تیکت جدید #{code}\n━━━━━━━━━━━━━━\n\n"
        f"{c['icon']} {c['name']}\n"
        f"📝 {d.get('subject')}\n"
        f"👤 {nm or uid}  📱 {u.get('mobile') or '—'}\n\n"
        f"💬 {body[:200]}"
    ), {"inline_keyboard": [
        [{"text": "👁️ مشاهده و پاسخ", "callback_data": f"tk_v_{tid}"}]]})
    return show_my_tickets(cid, uid)


def _notify_admins(text, kb=None):
    rows = db_execute("""SELECT bale_user_id FROM users
        WHERE is_admin=1 AND bale_user_id IS NOT NULL""", fetch="all") or []
    for r in rows:
        tuid = r["bale_user_id"]
        if not perm.has_perm(tuid, "tk_manage"):
            continue
        try:
            send(tuid, text, kb)
        except Exception:
            pass


# ==================== مشاهده تیکت ====================
def view_ticket(cid, uid, tid):
    """👁️ مشاهده گفتگوی تیکت"""
    t = get_ticket(tid)
    if not t:
        return send(cid, "❌ تیکت یافت نشد")

    is_owner = t.get("bale_user_id") == uid
    is_staff = _is_admin(uid) and perm.has_perm(uid, "tk_manage")
    if not (is_owner or is_staff):
        return send(cid, "❌ دسترسی ندارید")

    # علامت خوانده‌شدن
    if is_owner:
        db_execute("UPDATE tickets SET unread_user=0 WHERE id=?", (t["id"],))
    elif is_staff:
        db_execute("UPDATE tickets SET unread_admin=0 WHERE id=?", (t["id"],))

    msgs = db_execute("""SELECT m.*, u.first_name, u.last_name
        FROM ticket_messages m
        LEFT JOIN users u ON u.bale_user_id=m.sender_id
        WHERE m.ticket_id=? ORDER BY m.id""", (t["id"],), fetch="all") or []

    s = _st(t.get("status"))
    c = _cat(t.get("category"))
    pr = PRIORITIES.get(t.get("priority") or "normal", PRIORITIES["normal"])

    lines = [f"🎫 تیکت #{t.get('code')}", "━━━━━━━━━━━━━━", "",
             f"📝 {t.get('subject') or '—'}",
             f"{c['icon']} {c['name']}  |  {s['icon']} {s['name']}"]
    if is_staff:
        u = get_user(t.get("bale_user_id")) or {}
        nm = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip()
        lines.append(f"👤 {nm or t.get('bale_user_id')}  "
                     f"📱 {u.get('mobile') or '—'}")
        lines.append(f"{pr['icon']} اولویت: {pr['name']}")
    lines += ["", "━━━ گفتگو ━━━", ""]

    for m in msgs:
        who = "👨‍💼 پشتیبانی" if m.get("is_admin") else "👤 شما"
        if is_staff and not m.get("is_admin"):
            nm = f"{m.get('first_name') or ''} {m.get('last_name') or ''}".strip()
            who = f"👤 {nm or 'کاربر'}"
        lines.append(f"{who}  ({_jd.fmt(m.get('created_at'), 'datetime')})")
        lines.append(f"{m.get('body') or ''}")
        if m.get("file_id"):
            lines.append("   📎 (فایل پیوست)")
        lines.append("")

    btns = []
    if t.get("status") != "closed":
        btns.append([{"text": "💬 پاسخ", "callback_data": f"tk_r_{t['id']}"}])
    if is_staff:
        if t.get("status") != "closed":
            btns.append([{"text": "🟡 در حال بررسی",
                          "callback_data": f"tk_s_progress_{t['id']}"},
                         {"text": "⚫ بستن",
                          "callback_data": f"tk_s_closed_{t['id']}"}])
        else:
            btns.append([{"text": "🟢 بازکردن مجدد",
                          "callback_data": f"tk_s_open_{t['id']}"}])
        btns.append([{"text": "🚨 اولویت", "callback_data": f"tk_pr_{t['id']}"}])
        btns.append([{"text": "🔙 لیست تیکت‌ها", "callback_data": "tk_admin"}])
    else:
        if t.get("status") == "closed" and not t.get("rating"):
            btns.append([{"text": "⭐ امتیاز به پشتیبانی",
                          "callback_data": f"tk_rate_{t['id']}"}])
        btns.append([{"text": "🔙 تیکت‌های من", "callback_data": "tk_my"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_reply(cid, uid, tid):
    t = get_ticket(tid)
    if not t:
        return send(cid, "❌ یافت نشد")
    is_owner = t.get("bale_user_id") == uid
    is_staff = _is_admin(uid) and perm.has_perm(uid, "tk_manage")
    if not (is_owner or is_staff):
        return send(cid, "❌ دسترسی ندارید")
    if t.get("status") == "closed":
        return send(cid, "⚫ این تیکت بسته است")

    set_state(uid, STATE_TK_REPLY, {"tid": t["id"]}, merge=False)
    return send(cid, (
        f"💬 پاسخ به تیکت #{t.get('code')}\n━━━━━━━━━━━━━━\n\n"
        f"پیام خود را بنویسید:"
    ), kb_cancel())


def handle_reply(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    tid = get_state_data(uid).get("tid")

    if text in (BTN_BACK, "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return view_ticket(cid, uid, tid)

    t = get_ticket(tid)
    if not t:
        clear_state(uid)
        return send(cid, "❌ تیکت یافت نشد", kb_remove())
    if not text:
        return send(cid, "⚠️ پیام خالی است:", kb_cancel())

    is_staff = _is_admin(uid) and perm.has_perm(uid, "tk_manage")
    db_execute("""INSERT INTO ticket_messages
        (ticket_id, sender_id, is_admin, body) VALUES (?,?,?,?)""",
        (t["id"], uid, 1 if is_staff else 0, text[:3000]))

    if is_staff:
        db_execute("""UPDATE tickets SET status='answered', unread_user=1,
            assigned_to=?, last_reply_at=CURRENT_TIMESTAMP WHERE id=?""",
            (uid, t["id"]))
        try:
            send(t["bale_user_id"], (
                f"💬 پاسخ جدید به تیکت #{t.get('code')}\n"
                f"━━━━━━━━━━━━━━\n\n{text[:500]}"
            ), {"inline_keyboard": [
                [{"text": "👁️ مشاهده", "callback_data": f"tk_v_{t['id']}"}]]})
        except Exception:
            pass
    else:
        db_execute("""UPDATE tickets SET status='open', unread_admin=1,
            last_reply_at=CURRENT_TIMESTAMP WHERE id=?""", (t["id"],))
        u = get_user(uid) or {}
        nm = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip()
        _notify_admins((
            f"💬 پاسخ جدید در تیکت #{t.get('code')}\n"
            f"👤 {nm or uid}\n\n{text[:300]}"
        ), {"inline_keyboard": [
            [{"text": "👁️ مشاهده", "callback_data": f"tk_v_{t['id']}"}]]})

    clear_state(uid)
    send(cid, "✅ پیام ارسال شد", kb_remove())
    return view_ticket(cid, uid, tid)


def set_status(cid, uid, tid, status):
    """تغییر وضعیت تیکت (ادمین)"""
    if not perm.require(cid, uid, "tk_manage", send):
        return
    if status not in STATUSES:
        return send(cid, "❌ وضعیت نامعتبر")
    t = get_ticket(tid)
    if not t:
        return send(cid, "❌ یافت نشد")

    if status == "closed":
        db_execute("""UPDATE tickets SET status='closed', closed_by=?,
            closed_at=CURRENT_TIMESTAMP, unread_user=1 WHERE id=?""",
            (uid, t["id"]))
        try:
            send(t["bale_user_id"], (
                f"⚫ تیکت #{t.get('code')} بسته شد\n\n"
                f"اگر مشکلتان حل نشده، تیکت جدید بسازید."
            ), {"inline_keyboard": [
                [{"text": "⭐ امتیاز به پشتیبانی",
                  "callback_data": f"tk_rate_{t['id']}"}]]})
        except Exception:
            pass
    else:
        db_execute("UPDATE tickets SET status=? WHERE id=?", (status, t["id"]))
    log_action(uid, "ticket_status", {"code": t.get("code"), "reason": status})
    return view_ticket(cid, uid, tid)


def show_priority(cid, uid, tid, pr=None):
    if not perm.require(cid, uid, "tk_manage", send):
        return
    t = get_ticket(tid)
    if not t:
        return send(cid, "❌ یافت نشد")
    if pr is not None:
        if pr not in PRIORITIES:
            return send(cid, "❌ نامعتبر")
        db_execute("UPDATE tickets SET priority=? WHERE id=?", (pr, t["id"]))
        return view_ticket(cid, uid, tid)
    cur = t.get("priority") or "normal"
    btns = [[{"text": f"{'🔘' if k == cur else '⚪'} {v['icon']} {v['name']}",
              "callback_data": f"tk_prs_{k}_{t['id']}"}]
            for k, v in PRIORITIES.items()]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"tk_v_{t['id']}"}])
    return send_or_edit(cid, "🚨 اولویت تیکت:", {"inline_keyboard": btns})


def rate_ticket(cid, uid, tid, stars=None):
    """⭐ امتیاز کاربر به پشتیبانی"""
    t = get_ticket(tid)
    if not t or t.get("bale_user_id") != uid:
        return send(cid, "❌ دسترسی ندارید")
    if stars is not None:
        try:
            v = max(1, min(5, int(stars)))
        except (TypeError, ValueError):
            return send(cid, "❌ نامعتبر")
        db_execute("UPDATE tickets SET rating=? WHERE id=?", (v, t["id"]))
        send(cid, f"{'⭐' * v}\n\n🙏 ممنون از بازخوردتان!")
        return show_my_tickets(cid, uid)
    btns = [[{"text": "⭐" * i, "callback_data": f"tk_rt_{i}_{t['id']}"}]
            for i in range(5, 0, -1)]
    btns.append([{"text": "🔙 بازگشت", "callback_data": "tk_my"}])
    return send_or_edit(cid, (
        "⭐ رضایت شما از پشتیبانی؟\n━━━━━━━━━━━━━━\n\n"
        "۵ ستاره = عالی"
    ), {"inline_keyboard": btns})


# ==================== 👨‍💼 نمای ادمین ====================
def show_admin_tickets(cid, uid, page=0, flt="open"):
    """📱 مدیریت تیکت‌ها"""
    if not perm.require(cid, uid, "tk_manage", send):
        return

    where = ""
    if flt == "open":
        where = "t.status<>'closed'"
    elif flt in STATUSES:
        where = f"t.status='{flt}'"
    elif flt == "unread":
        where = "t.unread_admin=1"

    sql = """SELECT t.*, u.first_name, u.last_name, u.mobile
        FROM tickets t LEFT JOIN users u ON u.bale_user_id=t.bale_user_id"""
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY t.unread_admin DESC, t.id DESC LIMIT 200"
    rows = db_execute(sql, fetch="all") or []

    n_open = db_scalar("SELECT COUNT(*) FROM tickets WHERE status<>'closed'")
    n_unread = db_scalar("SELECT COUNT(*) FROM tickets WHERE unread_admin=1")
    n_all = db_scalar("SELECT COUNT(*) FROM tickets")

    fname = {"open": "باز", "unread": "خوانده‌نشده",
             "closed": "بسته", "all": "همه"}.get(flt, flt)
    lines = [f"📱 تیکت‌ها — {fname}", "━━━━━━━━━━━━━━",
             f"📊 کل: {n_all}  |  🟢 باز: {n_open}  |  🔴 جدید: {n_unread}", ""]

    if not rows:
        lines.append("✅ تیکتی در این دسته نیست")
    per = TICKETS_PER_PAGE
    pages = max(1, (len(rows) + per - 1) // per)
    page = max(0, min(int(page or 0), pages - 1))
    chunk = rows[page * per:(page + 1) * per]

    btns = []
    for r in chunk:
        s = _st(r.get("status"))
        c = _cat(r.get("category"))
        pr = PRIORITIES.get(r.get("priority") or "normal")
        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
        flag = " 🔴" if r.get("unread_admin") else ""
        urg = f" {pr['icon']}" if r.get("priority") in ("high", "urgent") else ""
        lines.append(f"{s['icon']} #{r.get('code')} {c['icon']}"
                     f" {str(r.get('subject') or '')[:32]}{flag}{urg}")
        lines.append(f"   👤 {nm or '—'}  |  {_jd.fmt(r.get('created_at'), 'date')}")
        btns.append([{"text": f"{s['icon']} #{r.get('code')} "
                              f"{str(r.get('subject') or '')[:22]}{flag}",
                      "callback_data": f"tk_v_{r['id']}"}])

    if pages > 1:
        nav = []
        if page > 0:
            nav.append({"text": "⬅️", "callback_data": f"tk_p_{page-1}_{flt}"})
        nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
        if page < pages - 1:
            nav.append({"text": "➡️", "callback_data": f"tk_p_{page+1}_{flt}"})
        btns.append(nav)

    btns.append([{"text": "🔴 خوانده‌نشده", "callback_data": "tk_p_0_unread"},
                 {"text": "🟢 باز", "callback_data": "tk_p_0_open"}])
    btns.append([{"text": "⚫ بسته", "callback_data": "tk_p_0_closed"},
                 {"text": "📋 همه", "callback_data": "tk_p_0_all"}])
    btns.append([{"text": "📊 آمار پشتیبانی", "callback_data": "tk_stats"}])
    btns.append([{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_stats(cid, uid):
    """📊 آمار پشتیبانی"""
    if not perm.require(cid, uid, "tk_manage", send):
        return
    total = db_scalar("SELECT COUNT(*) FROM tickets")
    closed = db_scalar("SELECT COUNT(*) FROM tickets WHERE status='closed'")
    open_n = total - closed
    avg_rate = db_scalar("SELECT COALESCE(AVG(rating),0) FROM tickets "
                         "WHERE rating IS NOT NULL")
    n_rated = db_scalar("SELECT COUNT(*) FROM tickets WHERE rating IS NOT NULL")

    lines = ["📊 آمار پشتیبانی", "━━━━━━━━━━━━━━", "",
             f"🎫 کل تیکت‌ها: {total}",
             f"🟢 باز: {open_n}   ⚫ بسته: {closed}"]
    if n_rated:
        lines.append(f"⭐ رضایت: {float(avg_rate):.1f} از ۵  ({n_rated} رأی)")
    lines.append("")

    by_cat = db_execute("""SELECT category, COUNT(*) n FROM tickets
        GROUP BY category ORDER BY n DESC""", fetch="all") or []
    if by_cat:
        lines.append("📂 به تفکیک دسته:")
        for r in by_cat:
            c = _cat(r["category"])
            lines.append(f"   {c['icon']} {c['name']}: {r['n']}")
        lines.append("")

    staff = db_execute("""SELECT t.assigned_to, u.first_name, u.last_name,
        COUNT(*) n FROM tickets t
        LEFT JOIN users u ON u.bale_user_id=t.assigned_to
        WHERE t.assigned_to IS NOT NULL
        GROUP BY t.assigned_to ORDER BY n DESC LIMIT 5""", fetch="all") or []
    if staff:
        lines.append("👨‍💼 فعال‌ترین پشتیبان‌ها:")
        for s in staff:
            nm = f"{s.get('first_name') or ''} {s.get('last_name') or ''}".strip()
            lines.append(f"   • {nm or s.get('assigned_to')}: {s['n']} تیکت")

    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "📱 لیست تیکت‌ها", "callback_data": "tk_admin"}],
        [{"text": "🔙 پنل ادمین", "callback_data": "admin_panel"}]]})


# ══════════════════════════════════════════════════════════
# 📥 فاز ۱۷-ج — صندوق دریافت پیام‌های مستقیم کاربران
#
# درخواست: «کاربر به ادمین پیام میده، جایی نیست که ذخیره بشه —
#   تو همون قسمت پشتیبانی باشگاه، صندوق دریافت رو بیار»
# ══════════════════════════════════════════════════════════
INBOX_SCHEMA = {
    "bale_user_id": "INTEGER",
    "message": "TEXT",
    "is_read": "INTEGER DEFAULT 0",
    "replied": "INTEGER DEFAULT 0",
    "reply_text": "TEXT",
    "replied_by": "INTEGER",
    "replied_at": "TIMESTAMP",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

STATE_INBOX_REPLY = "inbox_reply"
INBOX_PER_PAGE = 8


def init_inbox_table():
    from database import ensure_table
    ensure_table("admin_inbox", INBOX_SCHEMA)
    db_execute("CREATE INDEX IF NOT EXISTS idx_inbox_read "
               "ON admin_inbox(is_read)")
    log("✅ جدول صندوق دریافت آماده شد")


def save_inbox(uid, text):
    """💾 ذخیره پیام کاربر — از forward_to_admins صدا زده می‌شود"""
    try:
        return db_execute("INSERT INTO admin_inbox (bale_user_id, message) "
                          "VALUES (?,?)", (uid, str(text)[:2000]))
    except Exception as e:
        log(f"⚠️ ذخیره پیام صندوق: {e}")
        return None


def unread_count():
    try:
        return db_scalar("SELECT COUNT(*) FROM admin_inbox "
                         "WHERE is_read=0") or 0
    except Exception:
        return 0


def show_inbox(cid, uid, page=0, only_unread=0):
    """📥 صندوق دریافت پیام‌های کاربران"""
    if not _guard(cid, uid):
        return

    where = "WHERE i.is_read=0" if only_unread else ""
    rows = db_execute(f"""SELECT i.*, u.first_name, u.last_name, u.mobile
        FROM admin_inbox i
        LEFT JOIN users u ON u.bale_user_id=i.bale_user_id
        {where}
        ORDER BY i.is_read, i.id DESC LIMIT 200""", fetch="all") or []

    n_all = db_scalar("SELECT COUNT(*) FROM admin_inbox") or 0
    n_new = unread_count()
    n_rep = db_scalar("SELECT COUNT(*) FROM admin_inbox "
                      "WHERE replied=1") or 0

    lines = ["📥 صندوق دریافت", "━━━━━━━━━━━━━━",
             f"📨 کل: {n_all}  |  🔴 خوانده‌نشده: {n_new}  |  "
             f"💬 پاسخ‌داده: {n_rep}", ""]
    btns = []

    if not rows:
        lines.append("📭 پیامی نیست" if not only_unread
                     else "✅ همه پیام‌ها خوانده شده‌اند")
    else:
        per = INBOX_PER_PAGE
        pages = max(1, (len(rows) + per - 1) // per)
        page = max(0, min(int(page or 0), pages - 1))
        for m in rows[page * per:(page + 1) * per]:
            nm = f"{m.get('first_name') or ''} " \
                 f"{m.get('last_name') or ''}".strip()
            ic = "🔴" if not m.get("is_read") else (
                "💬" if m.get("replied") else "▫️")
            lines += [f"{ic} {nm or '—'}  📱 {m.get('mobile') or '—'}",
                      f"   📄 {str(m.get('message') or '')[:60]}",
                      f"   🕐 {_jd.fmt(m.get('created_at'), 'datetime')}", ""]
            btns.append([{"text": f"{ic} {nm or m['id']}"[:40],
                          "callback_data": f"ib_v_{m['id']}"}])
        if pages > 1:
            nav = []
            if page > 0:
                nav.append({"text": "⬅️",
                            "callback_data": f"ib_p_{page-1}_{only_unread}"})
            nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
            if page < pages - 1:
                nav.append({"text": "➡️",
                            "callback_data": f"ib_p_{page+1}_{only_unread}"})
            btns.append(nav)

    btns.append([
        {"text": "🔴 فقط خوانده‌نشده" if not only_unread else "📋 همه",
         "callback_data": f"ib_p_0_{0 if only_unread else 1}"},
    ])
    if n_new:
        btns.append([{"text": "✅ همه را خوانده‌شده کن",
                      "callback_data": "ib_allread"}])
    btns.append([{"text": "🔙 پشتیبانی و باشگاه",
                  "callback_data": "admin_care"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def view_inbox_msg(cid, uid, mid):
    """👁️ مشاهده یک پیام + امکان پاسخ"""
    if not _guard(cid, uid):
        return
    try:
        mid = int(mid)
    except (TypeError, ValueError):
        return send(cid, "❌ شناسه نامعتبر")

    m = db_execute("""SELECT i.*, u.first_name, u.last_name, u.mobile,
        u.city, u.profile_status FROM admin_inbox i
        LEFT JOIN users u ON u.bale_user_id=i.bale_user_id
        WHERE i.id=?""", (mid,), fetch="one")
    if not m:
        return send(cid, "❌ پیام یافت نشد")

    if not m.get("is_read"):
        db_execute("UPDATE admin_inbox SET is_read=1 WHERE id=?", (mid,))

    nm = f"{m.get('first_name') or ''} {m.get('last_name') or ''}".strip()
    lines = [
        "📩 پیام کاربر", "━━━━━━━━━━━━━━", "",
        f"👤 {nm or '—'}",
        f"📱 {m.get('mobile') or '—'}",
        f"🏙️ {m.get('city') or '—'}",
        f"🆔 {m.get('bale_user_id') or '—'}",
        f"🕐 {_jd.fmt(m.get('created_at'), 'datetime')}", "",
        "📄 متن پیام:",
        str(m.get("message") or "—"),
    ]
    if m.get("replied"):
        lines += ["", "━━━━━━━━━━━━━━", "💬 پاسخ شما:",
                  str(m.get("reply_text") or "—"),
                  f"🕐 {str(m.get('replied_at') or '')[:16]}"]

    btns = [[{"text": "💬 پاسخ به کاربر",
              "callback_data": f"ib_r_{mid}"}]]
    if m.get("bale_user_id"):
        u = db_execute("SELECT id FROM users WHERE bale_user_id=?",
                       (m["bale_user_id"],), fetch="one")
        if u:
            btns.append([{"text": "👤 پروفایل کاربر",
                          "callback_data": f"uv_{u['id']}"}])
    btns.append([{"text": "🗑️ حذف پیام", "callback_data": f"ib_d_{mid}"}])
    btns.append([{"text": "🔙 صندوق دریافت", "callback_data": "ib_list"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_inbox_reply(cid, uid, mid):
    """💬 شروع پاسخ به پیام"""
    if not _guard(cid, uid):
        return
    try:
        mid = int(mid)
    except (TypeError, ValueError):
        return send(cid, "❌ شناسه نامعتبر")
    m = db_execute("SELECT * FROM admin_inbox WHERE id=?", (mid,),
                   fetch="one")
    if not m:
        return send(cid, "❌ پیام یافت نشد")
    if not m.get("bale_user_id"):
        return send(cid, "⚠️ این پیام فرستنده مشخصی ندارد")

    set_state(uid, STATE_INBOX_REPLY, {"mid": mid}, merge=False)
    send(cid, (f"💬 پاسخ به کاربر\n━━━━━━━━━━━━━━\n\n"
               f"📄 پیام او:\n{str(m.get('message') or '')[:300]}\n\n"
               f"✍️ پاسخ خود را بنویسید:"), kb_cancel())


def handle_inbox_reply(message):
    """دریافت متن پاسخ و ارسال به کاربر"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    d = get_state_data(uid)
    mid = d.get("mid")

    if text in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        return show_inbox(cid, uid)
    if not text:
        return send(cid, "⚠️ لطفاً متن پاسخ را بنویسید:")

    m = db_execute("SELECT * FROM admin_inbox WHERE id=?", (mid,),
                   fetch="one")
    if not m:
        clear_state(uid)
        return send(cid, "❌ پیام یافت نشد", kb_remove())

    db_execute("""UPDATE admin_inbox SET replied=1, reply_text=?,
        replied_by=?, replied_at=CURRENT_TIMESTAMP, is_read=1
        WHERE id=?""", (text[:2000], uid, mid))
    clear_state(uid)

    target = m.get("bale_user_id")
    ok = False
    if target:
        try:
            send(target, (
                "💬 پاسخ پشتیبانی\n━━━━━━━━━━━━━━\n\n"
                f"{text[:1500]}\n\n"
                "💚 اگر باز هم سوالی داشتید در خدمتیم."))
            ok = True
        except Exception as e:
            log(f"⚠️ ارسال پاسخ صندوق: {e}")

    log_action(uid, "inbox_reply", {"mid": mid})
    send(cid, "✅ پاسخ ارسال شد" if ok else
              "⚠️ پاسخ ذخیره شد ولی ارسال ناموفق بود", kb_remove())
    return show_inbox(cid, uid)


def mark_all_read(cid, uid):
    """✅ همه را خوانده‌شده کن"""
    if not _guard(cid, uid):
        return
    db_execute("UPDATE admin_inbox SET is_read=1 WHERE is_read=0")
    send(cid, "✅ همه پیام‌ها خوانده‌شده شدند")
    return show_inbox(cid, uid)


def delete_inbox_msg(cid, uid, mid):
    """🗑️ حذف یک پیام"""
    if not _guard(cid, uid):
        return
    try:
        mid = int(mid)
    except (TypeError, ValueError):
        return send(cid, "❌ شناسه نامعتبر")
    db_execute("DELETE FROM admin_inbox WHERE id=?", (mid,))
    send(cid, "🗑️ پیام حذف شد")
    return show_inbox(cid, uid)
