"""
📊 نظرسنجی حرفه‌ای بعد از رویداد — فاز ۳۳

درخواست کاربر (عیناً):
  «نظرسنجی بعد رویداد رو حرفه ای و کامل کن»

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 مشکلی که بود

  رویداد ستون‌های `survey_enabled`, `survey_form_id`,
  `survey_send_time`, `survey_sent` را داشت و صفحهٔ تنظیماتش
  هم بود — ولی **هیچ کدی آن‌ها را نمی‌خواند**. یعنی نظرسنجی
  هرگز فرستاده نمی‌شد.

✅ حالا موتور کامل: زمان‌بندی · ارسال · یادآوری · گزارش

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 گزارش حرفه‌ای

  • نرخ پاسخ (چند نفر از چند نفر)
  • میانگین امتیاز هر سوال ستاره‌ای
  • نمودار متنی توزیع پاسخ‌ها
  • NPS — شاخص خالص ترویج‌کنندگان
  • نظرات متنی جدا
  • خروجی اکسل
"""
import json
from datetime import datetime, timedelta

from database import db_execute, db_scalar, get_setting, log
from bale_api import send, send_or_edit, send_document

# ⏰ چه وقت فرستاده شود — دقیقه بعد از پایان رویداد
SEND_DELAY = {
    "immediate": 0,
    "2h_after": 120,
    "next_day": 24 * 60,
    "3d_after": 3 * 24 * 60,
}

# 🎯 چه کسی نظرسنجی بگیرد
AUDIENCE = {
    "attended":   ("✅ فقط حاضران", "کسانی که حضورشان ثبت شده"),
    "registered": ("🎫 همهٔ ثبت‌نام‌شده‌ها", "حتی اگر نیامده باشند"),
    "paid":       ("💳 فقط پرداخت‌کرده‌ها", "کسانی که هزینه داده‌اند"),
}


def init_tables():
    """🗄️ جدول پیگیری ارسال نظرسنجی"""
    from database import ensure_table
    ensure_table("survey_sends", {
        "event_id": "INTEGER",
        "bale_user_id": "INTEGER",
        "form_id": "INTEGER",
        "sent_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "reminded_at": "TEXT",
        "answered": "INTEGER DEFAULT 0",
        "answered_at": "TEXT",
        "response_id": "INTEGER",
    })
    for q in [
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_svsend "
        "ON survey_sends(event_id, bale_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_svsend_ev "
        "ON survey_sends(event_id)",
    ]:
        try:
            db_execute(q)
        except Exception:
            pass
    log("✅ جدول نظرسنجی آماده شد")


# ══════════════════════════════════════════════════════════
# 🎯 مخاطبان
# ══════════════════════════════════════════════════════════
def audience(eid, mode=None):
    """👥 چه کسانی باید نظرسنجی بگیرند؟"""
    from events import get_event
    ev = get_event(eid) or {}
    mode = (mode or ev.get("survey_audience") or "attended").strip()

    if mode == "registered":
        rows = db_execute(
            "SELECT DISTINCT bale_user_id FROM event_registrations "
            "WHERE event_id=? AND status NOT IN ('cancelled','rejected')",
            (int(eid),), fetch="all") or []
    elif mode == "paid":
        # 💳 پرداخت‌کرده = مبلغی پرداخت شده یا رویداد رایگان بوده
        rows = db_execute(
            "SELECT DISTINCT bale_user_id FROM event_registrations "
            "WHERE event_id=? AND status NOT IN ('cancelled','rejected') "
            "AND (COALESCE(amount_paid,0)>0 OR paid_at IS NOT NULL)",
            (int(eid),), fetch="all") or []
    else:
        rows = db_execute(
            "SELECT DISTINCT bale_user_id FROM attendance_records "
            "WHERE event_id=? AND status IN ('present','late')",
            (int(eid),), fetch="all") or []
    return [r["bale_user_id"] for r in rows if r.get("bale_user_id")]


# ══════════════════════════════════════════════════════════
# 📤 ارسال
# ══════════════════════════════════════════════════════════
def due(eid):
    """
    ⏰ آیا وقت ارسال نظرسنجی این رویداد رسیده؟

    خروجی: (بله/خیر، دلیل)
    """
    from events import get_event
    ev = get_event(eid)
    if not ev:
        return False, "رویداد پیدا نشد"
    if not ev.get("survey_enabled"):
        return False, "نظرسنجی این رویداد خاموش است"
    if ev.get("survey_sent"):
        return False, "قبلاً فرستاده شده"
    if not ev.get("survey_form_id"):
        return False, "فرم نظرسنجی انتخاب نشده"
    if (ev.get("status") or "") != "finished":
        return False, "رویداد هنوز تمام نشده"

    delay = SEND_DELAY.get(ev.get("survey_send_time") or "2h_after", 120)
    fin = ev.get("finished_at") or ev.get("updated_at")
    if delay and fin:
        try:
            t = datetime.fromisoformat(str(fin)[:19])
            if datetime.now() < t + timedelta(minutes=delay):
                return False, "هنوز زمانش نرسیده"
        except Exception:
            pass
    return True, ""


def send_survey(eid, force=False, uid=None):
    """
    📤 ارسال نظرسنجی به مخاطبان.

    خروجی: (تعداد ارسال، پیام)
    """
    from events import get_event
    ev = get_event(eid)
    if not ev:
        return 0, "رویداد پیدا نشد"
    if not force:
        ok, why = due(eid)
        if not ok:
            return 0, why
    fid = ev.get("survey_form_id")
    if not fid:
        return 0, "فرم نظرسنجی انتخاب نشده"

    people = audience(eid)
    if not people:
        return 0, "کسی واجد شرایط نیست"

    try:
        from forms import form_link, get_form
        f = get_form(fid) or {}
        link = form_link(f)
    except Exception:
        f, link = {}, ""

    pts = int(ev.get("survey_points") or 0)
    txt = _invite_text(ev, f, pts, link)
    kb = {"inline_keyboard": [
        [{"text": "📝 پر کردن نظرسنجی",
          "callback_data": f"ffopen_{fid}"}]]}

    n = 0
    for u in people:
        if db_execute("SELECT id FROM survey_sends WHERE event_id=? "
                      "AND bale_user_id=?", (int(eid), int(u)),
                      fetch="one"):
            continue
        try:
            send(u, txt, kb)
            db_execute(
                "INSERT INTO survey_sends (event_id, bale_user_id, "
                "form_id) VALUES (?,?,?)", (int(eid), int(u), int(fid)))
            n += 1
        except Exception:
            pass

    if n:
        db_execute("UPDATE events SET survey_sent=1 WHERE id=?",
                   (int(eid),))
        log(f"📊 نظرسنجی رویداد #{eid} برای {n} نفر فرستاده شد")
    return n, ""


def _invite_text(ev, form, pts, link):
    """✉️ متن دعوت — از پنل قابل تغییر"""
    tpl = get_setting("survey_invite_text", "").strip()
    title = ev.get("title") or "رویداد"
    if tpl:
        return (tpl.replace("{رویداد}", title)
                   .replace("{فرم}", form.get("title") or "نظرسنجی")
                   .replace("{امتیاز}", str(pts))
                   .replace("{لینک}", link or ""))
    lines = [f"📊 نظر شما برای ما مهم است",
             "━━━━━━━━━━━━━━", "",
             f"🎉 {title}", "",
             "امیدواریم برایتان مفید بوده باشد 💚",
             "",
             "چند دقیقه وقت بگذارید و نظرتان را بگویید —",
             "کمک می‌کند برنامه‌های بعدی بهتر شوند."]
    if pts:
        try:
            from certgen import fa_digits
            lines += ["", f"🎁 با تکمیل نظرسنجی {fa_digits(pts)} "
                          f"امتیاز می‌گیرید"]
        except Exception:
            lines += ["", f"🎁 با تکمیل نظرسنجی {pts} امتیاز می‌گیرید"]
    if ev.get("survey_anonymous"):
        lines += ["", "🕶️ پاسخ‌ها ناشناس ثبت می‌شود"]
    return "\n".join(lines)


def remind(eid, uid=None):
    """
    🔁 یادآوری به کسانی که هنوز پاسخ نداده‌اند.

    خروجی: (تعداد، پیام)
    """
    from events import get_event
    ev = get_event(eid)
    if not ev:
        return 0, "رویداد پیدا نشد"
    if not ev.get("survey_reminder"):
        return 0, "یادآوری این رویداد خاموش است"

    try:
        gap = int(get_setting("survey_remind_hours", "24") or 24)
    except (TypeError, ValueError):
        gap = 24

    rows = db_execute(
        "SELECT * FROM survey_sends WHERE event_id=? AND answered=0 "
        "AND (reminded_at IS NULL OR reminded_at='')",
        (int(eid),), fetch="all") or []
    fid = ev.get("survey_form_id")
    try:
        from forms import get_form
        f = get_form(fid) or {}
    except Exception:
        f = {}

    txt = (f"🌱 یادآوری کوچک\n━━━━━━━━━━━━━━\n\n"
           f"🎉 {ev.get('title') or 'رویداد'}\n\n"
           f"هنوز نظرتان را نگفته‌اید.\n"
           f"فقط چند دقیقه وقت می‌برد 💚")
    kb = {"inline_keyboard": [
        [{"text": "📝 پر کردن نظرسنجی",
          "callback_data": f"ffopen_{fid}"}]]}

    n = 0
    for r in rows:
        try:
            st = datetime.fromisoformat(str(r["sent_at"])[:19])
            if datetime.now() < st + timedelta(hours=gap):
                continue
        except Exception:
            pass
        try:
            send(r["bale_user_id"], txt, kb)
            db_execute("UPDATE survey_sends SET "
                       "reminded_at=datetime('now') WHERE id=?",
                       (r["id"],))
            n += 1
        except Exception:
            pass
    if n:
        log(f"🔁 یادآوری نظرسنجی #{eid} برای {n} نفر")
    return n, ""


def mark_answered(eid, user_id, response_id=None):
    """✅ ثبت اینکه این نفر پاسخ داد + دادن امتیاز"""
    r = db_execute("SELECT * FROM survey_sends WHERE event_id=? AND "
                   "bale_user_id=?", (int(eid), int(user_id)),
                   fetch="one")
    if not r or r.get("answered"):
        return False
    db_execute("UPDATE survey_sends SET answered=1, "
               "answered_at=datetime('now'), response_id=? WHERE id=?",
               (response_id, r["id"]))
    try:
        from events import get_event
        ev = get_event(eid) or {}
        pts = int(ev.get("survey_points") or 0)
        if pts:
            # 🔴 باگ رفع‌شده (فاز ۴۰): همان باگ امتیاز حضور —
            #    `club.add_points` وجود ندارد.
            from attendance import _award_points
            _award_points(user_id, pts)
    except Exception as _e:
        log(f"⚠️ امتیاز نظرسنجی {user_id}: {_e}")
    return True


def on_form_submit(form_id, user_id, response_id=None):
    """
    🔗 قلاب — وقتی فرمی پر شد، اگر نظرسنجی رویدادی است ثبت کن.

    از `form_fill` بعد از تکمیل صدا زده می‌شود.
    """
    rows = db_execute(
        "SELECT event_id FROM survey_sends WHERE form_id=? AND "
        "bale_user_id=? AND answered=0", (int(form_id), int(user_id)),
        fetch="all") or []
    for r in rows:
        mark_answered(r["event_id"], user_id, response_id)
    return len(rows)


# ══════════════════════════════════════════════════════════
# 📈 گزارش حرفه‌ای
# ══════════════════════════════════════════════════════════
def stats(eid):
    """📊 آمار پایهٔ نظرسنجی"""
    total = db_scalar("SELECT COUNT(*) FROM survey_sends WHERE event_id=?",
                      (int(eid),)) or 0
    ans = db_scalar("SELECT COUNT(*) FROM survey_sends WHERE event_id=? "
                    "AND answered=1", (int(eid),)) or 0
    rem = db_scalar("SELECT COUNT(*) FROM survey_sends WHERE event_id=? "
                    "AND reminded_at IS NOT NULL AND reminded_at<>''",
                    (int(eid),)) or 0
    return {"sent": total, "answered": ans, "pending": total - ans,
            "reminded": rem,
            "rate": round(ans * 100.0 / total) if total else 0}


def analyze(eid):
    """
    📈 تحلیل عمیق پاسخ‌ها.

    برای هر سوال:
      • ستاره‌ای → میانگین + توزیع
      • انتخابی  → توزیع درصدی
      • متنی     → چند نمونه
    """
    from events import get_event
    ev = get_event(eid) or {}
    fid = ev.get("survey_form_id")
    if not fid:
        return []

    fields = db_execute(
        "SELECT * FROM form_fields WHERE form_id=? "
        "ORDER BY field_order, id", (int(fid),), fetch="all") or []
    out = []
    for f in fields:
        ft = (f.get("field_type") or "").strip()
        rows = db_execute(
            "SELECT a.value_text FROM form_answers a "
            "JOIN form_responses r ON r.id=a.response_id "
            "WHERE a.field_id=? AND r.status IN ('completed','confirmed')",
            (f["id"],), fetch="all") or []
        vals = [str(r.get("value_text") or "").strip()
                for r in rows if (r.get("value_text") or "").strip()]
        if not vals:
            continue

        item = {"title": f.get("label") or "—", "type": ft,
                "n": len(vals)}

        if ft in ("rating", "stars", "scale", "nps"):
            nums = []
            for v in vals:
                try:
                    nums.append(float(_en(v)))
                except (TypeError, ValueError):
                    pass
            if nums:
                item["avg"] = round(sum(nums) / len(nums), 2)
                dist = {}
                for x in nums:
                    dist[int(x)] = dist.get(int(x), 0) + 1
                item["dist"] = dict(sorted(dist.items()))
                if ft == "nps" or max(nums) > 5:
                    item["nps"] = _nps(nums)
        elif ft in ("choice", "select", "radio", "multi", "checkbox",
                    "yesno", "confirm"):
            dist = {}
            for v in vals:
                for part in (v.split("،") if "،" in v else [v]):
                    k = part.strip()
                    if k:
                        dist[k] = dist.get(k, 0) + 1
            item["dist"] = dict(sorted(dist.items(),
                                       key=lambda x: -x[1]))
        else:
            item["samples"] = vals[:8]
        out.append(item)
    return out


def _en(t):
    return str(t or "").translate(str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def _nps(nums):
    """
    📊 شاخص خالص ترویج‌کنندگان.

    ۹-۱۰ مروج · ۷-۸ خنثی · ۰-۶ منتقد
    NPS = درصد مروج − درصد منتقد
    """
    if not nums:
        return 0
    pro = sum(1 for x in nums if x >= 9)
    det = sum(1 for x in nums if x <= 6)
    return round((pro - det) * 100.0 / len(nums))


def bar(n, total, width=10):
    """▓ نوار متنی"""
    if not total:
        return "░" * width
    k = max(0, min(width, round(n / total * width)))
    return "▓" * k + "░" * (width - k)


# ══════════════════════════════════════════════════════════
# 🖥️ پنل گزارش
# ══════════════════════════════════════════════════════════
def _guard(cid, uid):
    """🛡️ بررسی ادمین — منطق مشترک در helpers"""
    from helpers import guard_admin
    return guard_admin(cid, uid)


def _fa(n):
    """🔢 ارقام فارسی — منطق مشترک در helpers"""
    from helpers import fa
    return fa(n)


def show_report(cid, uid, eid):
    """📈 گزارش کامل نظرسنجی"""
    if not _guard(cid, uid):
        return
    from events import get_event
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد پیدا نشد")

    st = stats(eid)
    lines = ["📈 گزارش نظرسنجی", "━━━━━━━━━━━━━━", "",
             f"🎉 {ev.get('title') or '—'}", ""]

    if not st["sent"]:
        lines += ["📭 هنوز نظرسنجی فرستاده نشده.", ""]
        ok, why = due(eid)
        lines.append("✅ آمادهٔ ارسال است" if ok else f"⏳ {why}")
        return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
            [{"text": "📤 ارسال همین حالا",
              "callback_data": f"sv_send_{eid}"}],
            [{"text": "⚙️ تنظیمات نظرسنجی",
              "callback_data": f"evsurv_{eid}"}],
            [{"text": "🔙 رویداد", "callback_data": f"ev_view_{eid}"}]]})

    lines += [f"📤 فرستاده شده: {_fa(st['sent'])}",
              f"✅ پاسخ داده: {_fa(st['answered'])}",
              f"⏳ بی‌پاسخ: {_fa(st['pending'])}",
              f"🔁 یادآوری‌شده: {_fa(st['reminded'])}", "",
              f"📊 نرخ پاسخ: {bar(st['answered'], st['sent'])} "
              f"{_fa(st['rate'])}٪", ""]

    an = analyze(eid)
    if an:
        lines.append("━━━━━━━━━━━━━━")
        lines.append("")
        for q in an[:6]:
            lines.append(f"❓ {q['title'][:40]}")
            if "avg" in q:
                lines.append(f"   ⭐ میانگین: {_fa(q['avg'])}")
                if "nps" in q:
                    nps = q["nps"]
                    face = "😍" if nps >= 50 else ("🙂" if nps >= 0
                                                   else "😟")
                    lines.append(f"   {face} NPS: {_fa(nps)}")
                for k, v in (q.get("dist") or {}).items():
                    lines.append(f"   {_fa(k)} {bar(v, q['n'], 8)} "
                                 f"{_fa(v)}")
            elif q.get("dist"):
                for k, v in list(q["dist"].items())[:5]:
                    pct = round(v * 100.0 / q["n"])
                    lines.append(f"   {k[:20]} {bar(v, q['n'], 8)} "
                                 f"{_fa(pct)}٪")
            elif q.get("samples"):
                for sm in q["samples"][:2]:
                    lines.append(f"   💬 {sm[:50]}")
            lines.append("")

    btns = [
        [{"text": "💬 همهٔ نظرات متنی",
          "callback_data": f"sv_txt_{eid}_0"}],
        [{"text": f"🔁 یادآوری به {_fa(st['pending'])} نفر",
          "callback_data": f"sv_rem_{eid}"}],
        [{"text": "📤 خروجی اکسل", "callback_data": f"sv_xl_{eid}"}],
        [{"text": "⚙️ تنظیمات", "callback_data": f"evsurv_{eid}"}],
        [{"text": "🔙 رویداد", "callback_data": f"ev_view_{eid}"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_comments(cid, uid, eid, page=0):
    """💬 نظرات متنی"""
    if not _guard(cid, uid):
        return
    an = analyze(eid)
    texts = []
    for q in an:
        for sm in (q.get("samples") or []):
            texts.append((q["title"], sm))
    if not texts:
        return send_or_edit(cid, (
            "💬 نظرات متنی\n━━━━━━━━━━━━━━\n\n"
            "📭 هنوز نظر متنی ثبت نشده."), {"inline_keyboard": [
                [{"text": "🔙 گزارش",
                  "callback_data": f"sv_rep_{eid}"}]]})

    per, page = 5, max(0, int(page or 0))
    pages = max(1, (len(texts) + per - 1) // per)
    page = min(page, pages - 1)
    chunk = texts[page * per:(page + 1) * per]

    lines = ["💬 نظرات شرکت‌کنندگان", "━━━━━━━━━━━━━━", ""]
    for t, sm in chunk:
        lines += [f"❓ {t[:36]}", f"   «{sm[:180]}»", ""]

    btns = []
    if pages > 1:
        nav = []
        if page > 0:
            nav.append({"text": "⬅️",
                        "callback_data": f"sv_txt_{eid}_{page-1}"})
        nav.append({"text": f"{_fa(page+1)}/{_fa(pages)}",
                    "callback_data": "noop"})
        if page < pages - 1:
            nav.append({"text": "➡️",
                        "callback_data": f"sv_txt_{eid}_{page+1}"})
        btns.append(nav)
    btns.append([{"text": "🔙 گزارش", "callback_data": f"sv_rep_{eid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def do_send(cid, uid, eid):
    """📤 ارسال دستی"""
    if not _guard(cid, uid):
        return
    n, why = send_survey(eid, force=True, uid=uid)
    if not n:
        return send(cid, f"🌱 {why or 'ارسال نشد'}")
    send(cid, f"✅ نظرسنجی برای {_fa(n)} نفر فرستاده شد")
    return show_report(cid, uid, eid)


def do_remind(cid, uid, eid):
    """🔁 یادآوری دستی"""
    if not _guard(cid, uid):
        return
    n, why = remind(eid, uid)
    if not n:
        return send(cid, f"🌱 {why or 'کسی برای یادآوری نبود'}")
    send(cid, f"🔁 یادآوری برای {_fa(n)} نفر فرستاده شد")
    return show_report(cid, uid, eid)


def export(cid, uid, eid):
    """📤 خروجی اکسل نظرسنجی"""
    if not _guard(cid, uid):
        return
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        return send(cid, "❌ openpyxl نصب نیست")
    from events import get_event
    from pathlib import Path
    from config import FILES_DIR

    ev = get_event(eid) or {}
    st = stats(eid)
    an = analyze(eid)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "خلاصه"
    ws.sheet_view.rightToLeft = True

    def _head(sheet, cols):
        sheet.append(cols)
        sheet.sheet_view.rightToLeft = True
        for i in range(1, len(cols) + 1):
            c = sheet.cell(row=1, column=i)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="4472C4")
            sheet.column_dimensions[
                openpyxl.utils.get_column_letter(i)].width = 24
        sheet.freeze_panes = "A2"

    _head(ws, ["شاخص", "مقدار"])
    for k, v in [("رویداد", ev.get("title") or ""),
                 ("فرستاده شده", st["sent"]),
                 ("پاسخ داده", st["answered"]),
                 ("بی‌پاسخ", st["pending"]),
                 ("نرخ پاسخ (٪)", st["rate"])]:
        ws.append([k, v])

    ws2 = wb.create_sheet("تحلیل سوالات")
    _head(ws2, ["سوال", "نوع", "تعداد پاسخ", "میانگین", "NPS"])
    for q in an:
        ws2.append([q["title"], q["type"], q["n"],
                    q.get("avg", ""), q.get("nps", "")])

    ws3 = wb.create_sheet("نظرات")
    _head(ws3, ["سوال", "نظر"])
    for q in an:
        for sm in (q.get("samples") or []):
            ws3.append([q["title"], sm])

    d = Path(FILES_DIR) / "exports"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"survey_{eid}.xlsx"
    wb.save(str(p))
    send_document(cid, str(p),
                  f"📊 گزارش نظرسنجی «{ev.get('title') or ''}»")
    return show_report(cid, uid, eid)


# ══════════════════════════════════════════════════════════
# ⏰ cron
# ══════════════════════════════════════════════════════════
def run_due(limit=20):
    """
    ⏰ ارسال خودکار نظرسنجی‌های سررسیده.

    از cron روزانه صدا زده می‌شود.
    """
    rows = db_execute(
        "SELECT id FROM events WHERE survey_enabled=1 AND "
        "COALESCE(survey_sent,0)=0 AND status='finished' "
        "ORDER BY id DESC LIMIT ?", (int(limit),), fetch="all") or []
    total = 0
    for r in rows:
        ok, _ = due(r["id"])
        if ok:
            n, _ = send_survey(r["id"])
            total += n
    return total


def run_reminders(limit=20):
    """🔁 یادآوری خودکار"""
    rows = db_execute(
        "SELECT DISTINCT event_id FROM survey_sends WHERE answered=0 "
        "AND (reminded_at IS NULL OR reminded_at='') LIMIT ?",
        (int(limit),), fetch="all") or []
    total = 0
    for r in rows:
        n, _ = remind(r["event_id"])
        total += n
    return total
