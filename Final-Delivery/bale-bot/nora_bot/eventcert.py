"""
🎓 چند گواهینامه برای یک رویداد — فاز ۳۲

درخواست کاربر (عیناً):
  «بعضی رویداد ها همکاری هستن و ممکن یک تا چندین گواهی مستقل
   صادر بشه پس گواهینامه هارو تو بخش رویداد بتونم چندتا انتخاب
   کنم و بفرستم به شرکت کننده ها و این مورد توی ایجاد رویداد هم
   باشه و تو تبلیغات رویداد و تو پنل کاربر و ... همه جزییات
   مربوطه این مورد ذکر بشه و همه چی قابل تنظیم باشه»

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 ایده

  رویداد مشترک بین دو سازمان → دو گواهینامهٔ مستقل:
      🎓 گواهینامهٔ دانشگاه فرهنگیان
      🎓 گواهینامهٔ جمعیت هلال‌احمر

  هرکدام قالب، صادرکننده، لوگو و **شرط جداگانه** دارد.
  ممکن است کسی شرط یکی را داشته باشد و دیگری را نه.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔗 این اطلاعات در چهار جا دیده می‌شود:
   ۱) ویزارد ساخت رویداد
   ۲) تبلیغ و صفحهٔ رویداد (قبل از ثبت‌نام)
   ۳) پنل کاربر بعد از شرکت
   ۴) مرکز صدور گواهینامه
"""
import json
from pathlib import Path

from database import db_execute, db_scalar, get_setting, log
from bale_api import send, send_or_edit, kb_cancel, kb_remove
from auth import set_state, get_state_data, clear_state

# 🎯 شرط‌های صدور — مستقل برای هر گواهینامه
CONDITIONS = {
    "none":      ("🎫 فقط ثبت‌نام", "هرکس ثبت‌نام کرده"),
    "present":   ("✅ حضور تأییدشده", "در لیست حضور باشد"),
    "sessions":  ("📅 حداقل جلسه", "در چند جلسه حاضر بوده"),
    "score":     ("🎯 حداقل نمره", "نمرهٔ آزمون بالای حد"),
    "paid":      ("💳 پرداخت کامل", "هزینه را پرداخت کرده"),
    "manual":    ("👤 تأیید دستی", "ادمین یکی‌یکی تأیید کند"),
}

MAX_PER_EVENT = 8          # سقف منطقی — بیشتر شود UI شلوغ می‌شود

# 🧭 فاز ۹.۳ — سیاست گواهی حضور: ثبت‌نام یا پرداخت به‌تنهایی «حضور» را اثبات نمی‌کند.
# شرط‌های زیر مجازند (حذف نمی‌شوند) ولی گواهی‌شان گواهی حضور نیست و ادمین باید این را آگاهانه انتخاب کند.
NON_ATTENDANCE_CONDITIONS = ("none", "paid")
ATTENDANCE_POLICY_WARNING = (
    "⚠️ این شرط حضور را اثبات نمی‌کند: گواهیِ صادرشده با آن «گواهی حضور» نیست "
    "(فقط ثبت‌نام/پرداخت). برای گواهی حضور از «حضور تأییدشده»، «حداقل جلسه» یا «تأیید دستی» استفاده کنید. "
    "خرید محتوای ضبط‌شده هم ثبت‌نام این رویداد نیست و شرطی را برآورده نمی‌کند."
)


def condition_policy_note(cond):
    """متن هشدار برای شرط‌های غیرحضوری؛ برای بقیه خالی."""
    return ATTENDANCE_POLICY_WARNING if (cond or "present") in NON_ATTENDANCE_CONDITIONS else ""


# ══════════════════════════════════════════════════════════
# 📚 داده
# ══════════════════════════════════════════════════════════
def list_certs(event_id, only_active=True):
    """🎓 همهٔ گواهینامه‌های یک رویداد — به ترتیب نمایش"""
    q = "SELECT * FROM event_certs WHERE event_id=?"
    if only_active:
        q += " AND is_active=1"
    q += " ORDER BY position, id"
    return db_execute(q, (int(event_id),), fetch="all") or []


def count_certs(event_id):
    return db_scalar("SELECT COUNT(*) FROM event_certs "
                     "WHERE event_id=? AND is_active=1",
                     (int(event_id),)) or 0


def get_cert(cid_row):
    return db_execute("SELECT * FROM event_certs WHERE id=?",
                      (int(cid_row),), fetch="one")


def add_cert(event_id, title, template_id=None, uid=None, **kw):
    """➕ افزودن یک گواهینامه به رویداد"""
    n = count_certs(event_id)
    if n >= MAX_PER_EVENT:
        return None, f"حداکثر {MAX_PER_EVENT} گواهینامه برای هر رویداد"
    pos = db_scalar("SELECT COALESCE(MAX(position),0)+1 FROM event_certs "
                    "WHERE event_id=?", (int(event_id),)) or 1
    rid = db_execute(
        "INSERT INTO event_certs (event_id, template_id, title, issuer, "
        "issuer_logo, note, auto_issue, condition, min_sessions, "
        "min_score, show_in_ad, position, created_by) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (int(event_id), template_id, title, kw.get("issuer") or "",
         kw.get("issuer_logo") or "", kw.get("note") or "",
         1 if kw.get("auto_issue", True) else 0,
         kw.get("condition") or "present",
         int(kw.get("min_sessions") or 0),
         int(kw.get("min_score") or 0),
         1 if kw.get("show_in_ad", True) else 0, pos, uid))
    return rid, ""


def update_cert(row_id, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    db_execute(f"UPDATE event_certs SET {cols} WHERE id=?",
               tuple(fields.values()) + (int(row_id),))


def delete_cert(row_id):
    db_execute("DELETE FROM event_certs WHERE id=?", (int(row_id),))


def move_cert(row_id, delta):
    """🔀 جابه‌جایی ترتیب"""
    r = get_cert(row_id)
    if not r:
        return
    rows = list_certs(r["event_id"], only_active=False)
    ids = [x["id"] for x in rows]
    if row_id not in ids:
        return
    i = ids.index(row_id)
    j = max(0, min(len(ids) - 1, i + delta))
    if i == j:
        return
    ids[i], ids[j] = ids[j], ids[i]
    for pos, rid in enumerate(ids, 1):
        db_execute("UPDATE event_certs SET position=? WHERE id=?",
                   (pos, rid))


# ══════════════════════════════════════════════════════════
# ✅ سنجش شرط
# ══════════════════════════════════════════════════════════
def eligible(cert_row, event_id, user_id):
    """
    🎯 آیا این کاربر شرط این گواهینامهٔ خاص را دارد؟

    خروجی: (بله/خیر، دلیل)
    """
    cond = (cert_row.get("condition") or "present").strip()

    reg = db_execute(
        "SELECT * FROM event_registrations "
        "WHERE event_id=? AND bale_user_id=?",
        (int(event_id), int(user_id)), fetch="one")
    if not reg:
        return False, "در این رویداد ثبت‌نام نکرده‌اید"

    if cond == "none":
        return True, ""

    if cond == "paid":
        if (reg.get("amount_paid") or 0) > 0 or reg.get("paid_at"):
            return True, ""
        return False, "هزینهٔ رویداد پرداخت نشده"

    if cond == "manual":
        ok = db_scalar(
            "SELECT COUNT(*) FROM certificates WHERE event_id=? AND "
            "bale_user_id=? AND source='manual'",
            (int(event_id), int(user_id)))
        return (bool(ok), "" if ok else "در انتظار تأیید برگزارکننده")

    if cond == "score":
        need = int(cert_row.get("min_score") or 0)
        try:
            sc = int(reg.get("score") or 0)
        except (TypeError, ValueError):
            sc = 0
        if sc >= need:
            return True, ""
        return False, f"نمرهٔ لازم {need} — نمرهٔ شما {sc}"

    # present / sessions
    try:
        n = db_scalar(
            "SELECT COUNT(*) FROM attendance_records WHERE event_id=? "
            "AND bale_user_id=? AND status IN ('present','late')",
            (int(event_id), int(user_id))) or 0
    except Exception:
        n = 0

    if cond == "present":
        if n > 0:
            return True, ""
        return False, "حضور شما ثبت نشده است"

    need = int(cert_row.get("min_sessions") or 1)
    if n >= need:
        return True, ""
    return False, f"حداقل {need} جلسه لازم است — شما {n} جلسه"


def eligible_list(event_id, user_id):
    """
    📋 وضعیت همهٔ گواهینامه‌های رویداد برای یک کاربر.

    خروجی: [{row, ok, why, issued}]
    """
    out = []
    for c in list_certs(event_id):
        ok, why = eligible(c, event_id, user_id)
        issued = db_execute(
            "SELECT id, serial FROM certificates WHERE event_id=? AND "
            "bale_user_id=? AND event_cert_id=? AND revoked=0",
            (int(event_id), int(user_id), c["id"]), fetch="one")
        out.append({"row": c, "ok": ok, "why": why, "issued": issued})
    return out


# ══════════════════════════════════════════════════════════
# 📣 متن برای تبلیغ رویداد و پنل کاربر
# ══════════════════════════════════════════════════════════
def ad_lines(event_id, detailed=None):
    """
    📣 خطوط گواهینامه برای تبلیغ و صفحهٔ رویداد.

    🎯 «تو تبلیغات رویداد ... همه جزییات مربوطه ذکر بشه»
    """
    certs = [c for c in list_certs(event_id) if c.get("show_in_ad")]
    if not certs:
        return []
    if detailed is None:
        detailed = get_setting("ev_cert_ad_detail", "1") == "1"

    n = len(certs)
    head = get_setting("ev_cert_ad_title", "").strip()
    if not head:
        head = ("🎓 گواهینامه" if n == 1
                else f"🎓 {_fa(n)} گواهینامهٔ مستقل")
    lines = [head]

    if not detailed:
        lines.append("   " + " · ".join(
            (c.get("title") or "گواهینامه") for c in certs))
        return lines

    for c in certs:
        t = c.get("title") or "گواهینامه"
        lines.append(f"   • {t}")
        iss = (c.get("issuer") or "").strip()
        if iss:
            lines.append(f"     🏛️ {iss}")
        cond = (c.get("condition") or "present")
        lines.append(f"     🎯 {_cond_fa(c)}")
        note = (c.get("note") or "").strip()
        if note:
            lines.append(f"     💬 {note}")
    return lines


def _cond_fa(c):
    """🎯 شرط این گواهینامه به زبان آدمیزاد"""
    cond = (c.get("condition") or "present").strip()
    if cond == "sessions":
        return f"حضور در حداقل {_fa(c.get('min_sessions') or 1)} جلسه"
    if cond == "score":
        return f"نمرهٔ حداقل {_fa(c.get('min_score') or 0)}"
    return CONDITIONS.get(cond, ("—", ""))[1]


def _fa(n):
    """🔢 ارقام فارسی — منطق مشترک در helpers"""
    from helpers import fa
    return fa(n)


def user_panel_lines(event_id, user_id):
    """
    👤 وضعیت گواهینامه‌ها در پنل کاربر بعد از شرکت.

    🎯 «تو پنل کاربر ... همه جزییات مربوطه ذکر بشه»
    """
    st = eligible_list(event_id, user_id)
    if not st:
        return [], []
    lines = ["🎓 گواهینامه‌های این رویداد:", ""]
    btns = []
    for s in st:
        c, ok, why, iss = s["row"], s["ok"], s["why"], s["issued"]
        t = c.get("title") or "گواهینامه"
        if iss:
            lines.append(f"   ✅ {t}")
            lines.append(f"      🔖 {iss.get('serial') or '—'}")
            btns.append([{"text": f"📥 دریافت «{t[:22]}»",
                          "callback_data": f"evc_get_{iss['id']}"}])
        elif ok:
            # 🔒 فاز ۳۹ — وقتی قفل بسته است، دکمهٔ «صدور» را
            #    اصلاً نشان نده؛ فقط بگو در نوبت است.
            _self = True
            try:
                import certissue as _ci
                _self = _ci.self_issue_allowed()
            except ImportError:
                pass
            if _self:
                lines.append(f"   🟢 {t}")
                lines.append("      آمادهٔ صدور")
                btns.append([{"text": f"🎓 صدور «{t[:22]}»",
                              "callback_data":
                                  f"evc_iss_{event_id}_{c['id']}"}])
            else:
                lines.append(f"   🟢 {t}")
                lines.append("      ✅ شرایطش را دارید — "
                             "به‌زودی صادر می‌شود")
        else:
            lines.append(f"   ⏳ {t}")
            lines.append(f"      {why}")
        iss_name = (c.get("issuer") or "").strip()
        if iss_name:
            lines.append(f"      🏛️ {iss_name}")
        lines.append("")
    return lines, btns


def summary(event_id):
    """📊 خلاصهٔ یک‌خطی برای کارت رویداد در پنل ادمین"""
    n = count_certs(event_id)
    if not n:
        return "⚪ ندارد"
    if n == 1:
        c = list_certs(event_id)[0]
        return f"✅ {c.get('title') or 'گواهینامه'}"
    return f"✅ {_fa(n)} گواهینامه"


# ══════════════════════════════════════════════════════════
# 🖥️ پنل ادمین
# ══════════════════════════════════════════════════════════
def _guard(cid, uid):
    """🛡️ بررسی ادمین — منطق مشترک در helpers"""
    from helpers import guard_admin
    return guard_admin(cid, uid)


def show_panel(cid, uid, eid):
    """
    🎓 مدیریت گواهینامه‌های یک رویداد.

    🎯 «تو پنل گواهینامه قسمت رویداد اینو داشته باش»
    """
    if not _guard(cid, uid):
        return
    from events import get_event
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد پیدا نشد")

    certs = list_certs(eid, only_active=False)
    lines = ["🎓 گواهینامه‌های رویداد", "━━━━━━━━━━━━━━", "",
             f"📅 {ev.get('title') or '—'}", ""]

    if not certs:
        lines += ["📭 هنوز گواهینامه‌ای تعریف نشده.", "",
                  "💡 اگر این رویداد مشترک است، می‌توانید چند",
                  "   گواهینامهٔ مستقل تعریف کنید — هرکدام با",
                  "   قالب، صادرکننده و شرط جداگانه."]
    else:
        lines.append(f"📊 {_fa(len(certs))} گواهینامه:")
        lines.append("")
        for i, c in enumerate(certs, 1):
            on = "🟢" if c.get("is_active") else "⚪"
            lines.append(f"{on} {_fa(i)}. {c.get('title') or 'بی‌نام'}")
            iss = (c.get("issuer") or "").strip()
            if iss:
                lines.append(f"      🏛️ {iss}")
            lines.append(f"      🎯 {_cond_fa(c)}")
            tpl = c.get("template_id")
            if tpl:
                try:
                    from certgen import get_template
                    t = get_template(tpl)
                    lines.append(f"      📄 {(t or {}).get('name') or '—'}")
                except Exception:
                    pass
            else:
                lines.append("      📄 قالب پیش‌فرض")
            lines.append(
                f"      {'🤖 خودکار' if c.get('auto_issue') else '👤 دستی'}"
                f" · {'📣 در تبلیغ' if c.get('show_in_ad') else '🔕 مخفی'}")
            n = db_scalar(
                "SELECT COUNT(*) FROM certificates WHERE event_cert_id=? "
                "AND revoked=0", (c["id"],)) or 0
            lines.append(f"      📤 {_fa(n)} صادرشده")
            lines.append("")

    btns = []
    for c in certs:
        btns.append([{"text": f"{'🟢' if c.get('is_active') else '⚪'} "
                              f"{(c.get('title') or 'بی‌نام')[:26]}",
                      "callback_data": f"evc_v_{c['id']}"}])
    if len(certs) < MAX_PER_EVENT:
        btns.append([{"text": "➕ افزودن گواهینامه",
                      "callback_data": f"evc_add_{eid}"}])
    if certs:
        btns.append([{"text": "📤 صدور گروهی همه",
                      "callback_data": f"cert_bulk_{eid}"}])
        btns.append([{"text": "👁️ پیش‌نمایش متن تبلیغ",
                      "callback_data": f"evc_prev_{eid}"}])
    btns.append([{"text": "🔍 استعلام و اعتبار",
                  "callback_data": f"cve_{eid}"}])
    btns.append([{"text": "🔙 مدیریت رویداد",
                  "callback_data": f"ev_view_{eid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_cert(cid, uid, row_id):
    """🎓 جزئیات و تنظیمات یک گواهینامه"""
    if not _guard(cid, uid):
        return
    c = get_cert(row_id)
    if not c:
        return send(cid, "❌ پیدا نشد")

    tpl_name = "پیش‌فرض ربات"
    if c.get("template_id"):
        try:
            from certgen import get_template
            t = get_template(c["template_id"])
            tpl_name = (t or {}).get("name") or "—"
        except Exception:
            pass

    n = db_scalar("SELECT COUNT(*) FROM certificates WHERE event_cert_id=? "
                  "AND revoked=0", (c["id"],)) or 0

    lines = [f"🎓 {c.get('title') or 'بی‌نام'}", "━━━━━━━━━━━━━━", "",
             f"🏛️ صادرکننده: {c.get('issuer') or '—'}",
             f"📄 قالب: {tpl_name}",
             f"🎯 شرط: {_cond_fa(c)}",
             f"🤖 صدور: {'خودکار' if c.get('auto_issue') else 'دستی'}",
             f"📣 در تبلیغ: {'بله' if c.get('show_in_ad') else 'خیر'}",
             f"📤 صادرشده: {_fa(n)}", ""]
    note = (c.get("note") or "").strip()
    if note:
        lines += [f"💬 {note}", ""]
    policy = condition_policy_note(c.get("condition"))
    if policy:
        lines += [policy, ""]

    btns = [
        [{"text": "✏️ عنوان", "callback_data": f"evce_title_{c['id']}"},
         {"text": "🏛️ صادرکننده",
          "callback_data": f"evce_issuer_{c['id']}"}],
        [{"text": "📄 انتخاب قالب",
          "callback_data": f"evc_tpl_{c['id']}"}],
        [{"text": "🎯 شرط صدور", "callback_data": f"evc_cond_{c['id']}"}],
        [{"text": "💬 توضیح", "callback_data": f"evce_note_{c['id']}"}],
        [{"text": f"🤖 خودکار: {'✅' if c.get('auto_issue') else '❌'}",
          "callback_data": f"evct_auto_{c['id']}"},
         {"text": f"📣 تبلیغ: {'✅' if c.get('show_in_ad') else '❌'}",
          "callback_data": f"evct_ad_{c['id']}"}],
        [{"text": "⬆️", "callback_data": f"evcm_u_{c['id']}"},
         {"text": "⬇️", "callback_data": f"evcm_d_{c['id']}"},
         {"text": f"{'🟢 فعال' if c.get('is_active') else '⚪ خاموش'}",
          "callback_data": f"evct_on_{c['id']}"}],
        [{"text": "🗑️ حذف", "callback_data": f"evc_del_{c['id']}"}],
        [{"text": "🔙 گواهینامه‌ها",
          "callback_data": f"evc_p_{c['event_id']}"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_add(cid, uid, eid):
    """➕ شروع افزودن گواهینامه"""
    if not _guard(cid, uid):
        return
    if count_certs(eid) >= MAX_PER_EVENT:
        return send(cid, f"⚠️ حداکثر {_fa(MAX_PER_EVENT)} گواهینامه")
    set_state(uid, "evc_add_title", {"event_id": int(eid)})
    send(cid, (
        "🎓 گواهینامهٔ تازه\n━━━━━━━━━━━━━━\n\n"
        "عنوان گواهینامه را بنویسید.\n\n"
        "💡 اگر رویداد مشترک است، نام سازمان را هم بیاورید:\n"
        "   «گواهینامهٔ دانشگاه فرهنگیان»\n"
        "   «گواهینامهٔ جمعیت هلال‌احمر»"), kb_cancel())


def handle_text(message):
    """📝 دریافت ورودی متنی"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    txt = (message.get("text") or "").strip()
    st, data = get_state_data(uid)
    if not st or not st.startswith("evc_"):
        return False
    if txt in ("انصراف", "❌ انصراف", "/cancel"):
        clear_state(uid)
        send(cid, "✅ لغو شد", kb_remove())
        return True

    if st == "evc_add_title":
        if len(txt) < 3:
            send(cid, "⚠️ عنوان خیلی کوتاه است")
            return True
        eid = data.get("event_id")
        rid, err = add_cert(eid, txt[:80], uid=uid)
        clear_state(uid)
        if not rid:
            send(cid, f"❌ {err}", kb_remove())
            return True
        send(cid, f"✅ «{txt[:40]}» اضافه شد", kb_remove())
        show_cert(cid, uid, rid)
        return True

    if st.startswith("evc_edit_"):
        field = st[len("evc_edit_"):]
        rid = data.get("row_id")
        if field in ("title", "issuer", "note"):
            update_cert(rid, **{field: txt[:200]})
            clear_state(uid)
            send(cid, "✅ ذخیره شد", kb_remove())
            show_cert(cid, uid, rid)
            return True

    if st == "evc_min":
        rid = data.get("row_id")
        key = data.get("key") or "min_sessions"
        try:
            # 🔴 باگ رفع‌شده (فاز ۴۰): همان باگ certbatch —
            #    normalize_digits در auth.py است نه config.py
            from auth import normalize_digits
            v = int(normalize_digits(txt))
        except Exception:
            send(cid, "⚠️ یک عدد بنویسید")
            return True
        update_cert(rid, **{key: max(0, v)})
        clear_state(uid)
        send(cid, "✅ ذخیره شد", kb_remove())
        show_cert(cid, uid, rid)
        return True
    return False


def start_edit(cid, uid, field, row_id):
    if not _guard(cid, uid):
        return
    labels = {"title": "عنوان گواهینامه", "issuer": "نام صادرکننده",
              "note": "توضیح برای شرکت‌کننده"}
    set_state(uid, f"evc_edit_{field}", {"row_id": int(row_id)})
    send(cid, f"✏️ {labels.get(field, field)} را بنویسید:", kb_cancel())


def toggle(cid, uid, what, row_id):
    if not _guard(cid, uid):
        return
    c = get_cert(row_id)
    if not c:
        return send(cid, "❌ پیدا نشد")
    key = {"auto": "auto_issue", "ad": "show_in_ad",
           "on": "is_active"}.get(what)
    if not key:
        return send(cid, "❌ نامعتبر")
    update_cert(row_id, **{key: 0 if c.get(key) else 1})
    return show_cert(cid, uid, row_id)


def do_move(cid, uid, direction, row_id):
    if not _guard(cid, uid):
        return
    c = get_cert(row_id)
    if not c:
        return send(cid, "❌ پیدا نشد")
    move_cert(row_id, -1 if direction == "u" else 1)
    return show_panel(cid, uid, c["event_id"])


def show_cond(cid, uid, row_id):
    """🎯 انتخاب شرط صدور"""
    if not _guard(cid, uid):
        return
    c = get_cert(row_id)
    if not c:
        return send(cid, "❌ پیدا نشد")
    cur = c.get("condition") or "present"
    lines = ["🎯 شرط صدور این گواهینامه", "━━━━━━━━━━━━━━", "",
             "چه کسی این گواهینامه را بگیرد؟", ""]
    btns = []
    for k, (nm, desc) in CONDITIONS.items():
        mark = "🔘" if k == cur else "▫️"
        lines.append(f"{mark} {nm}")
        lines.append(f"     {desc}")
        btns.append([{"text": f"{mark} {nm}",
                      "callback_data": f"evcc_{k}_{row_id}"}])
    if cur == "sessions":
        lines += ["", f"📅 حداقل جلسه: {_fa(c.get('min_sessions') or 1)}"]
        btns.append([{"text": "✏️ تغییر حداقل جلسه",
                      "callback_data": f"evcn_sessions_{row_id}"}])
    if cur == "score":
        lines += ["", f"🎯 حداقل نمره: {_fa(c.get('min_score') or 0)}"]
        btns.append([{"text": "✏️ تغییر حداقل نمره",
                      "callback_data": f"evcn_score_{row_id}"}])
    policy = condition_policy_note(cur)
    if policy:
        lines += ["", policy]
    btns.append([{"text": "🔙 بازگشت",
                  "callback_data": f"evc_v_{row_id}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_cond(cid, uid, cond, row_id):
    if not _guard(cid, uid):
        return
    if cond not in CONDITIONS:
        return send(cid, "❌ نامعتبر")
    c = get_cert(row_id)
    if not c:
        return send(cid, "❌ پیدا نشد")
    before = (c.get("condition") or "present").strip()
    update_cert(row_id, condition=cond)
    # 📝 فاز ۹.۳ — تغییر شرط صدور با عامل در گزارش فعالیت؛ شرط غیرحضوری صریحاً علامت می‌خورد
    try:
        from auth import log_action
        log_action(uid, "event_cert_condition",
                   {"event_cert": int(row_id), "event": int(c.get("event_id") or 0),
                    "before": before, "after": cond,
                    "attendance_proof": cond not in NON_ATTENDANCE_CONDITIONS})
    except Exception:
        pass
    return show_cond(cid, uid, row_id)


def start_min(cid, uid, key, row_id):
    if not _guard(cid, uid):
        return
    set_state(uid, "evc_min", {"row_id": int(row_id),
                               "key": f"min_{key}"})
    lbl = "حداقل تعداد جلسه" if key == "sessions" else "حداقل نمره"
    send(cid, f"✏️ {lbl} را بنویسید:", kb_cancel())


def show_tpl_picker(cid, uid, row_id):
    """📄 انتخاب قالب برای این گواهینامه"""
    if not _guard(cid, uid):
        return
    c = get_cert(row_id)
    if not c:
        return send(cid, "❌ پیدا نشد")
    try:
        tpls = db_execute(
            "SELECT * FROM cert_templates WHERE is_active=1 "
            "ORDER BY is_default DESC, id DESC", fetch="all") or []
    except Exception:
        tpls = []
    lines = ["📄 قالب این گواهینامه", "━━━━━━━━━━━━━━", ""]
    cur = c.get("template_id")
    btns = [[{"text": f"{'🔘' if not cur else '▫️'} پیش‌فرض ربات",
              "callback_data": f"evcT_0_{row_id}"}]]
    if not tpls:
        lines.append("📭 قالبی ثبت نشده — پیش‌فرض استفاده می‌شود.")
    for t in tpls:
        mark = "🔘" if cur == t["id"] else "▫️"
        lines.append(f"{mark} {t.get('name') or '—'}")
        btns.append([{"text": f"{mark} {(t.get('name') or '—')[:26]}",
                      "callback_data": f"evcT_{t['id']}_{row_id}"}])
    btns.append([{"text": "🔙 بازگشت",
                  "callback_data": f"evc_v_{row_id}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_tpl(cid, uid, tid, row_id):
    if not _guard(cid, uid):
        return
    update_cert(row_id, template_id=int(tid) or None)
    return show_cert(cid, uid, row_id)


def confirm_delete(cid, uid, row_id):
    if not _guard(cid, uid):
        return
    c = get_cert(row_id)
    if not c:
        return send(cid, "❌ پیدا نشد")
    n = db_scalar("SELECT COUNT(*) FROM certificates WHERE event_cert_id=?",
                  (row_id,)) or 0
    lines = [f"🗑️ حذف «{c.get('title') or 'بی‌نام'}»",
             "━━━━━━━━━━━━━━", ""]
    if n:
        lines += [f"⚠️ {_fa(n)} گواهینامه از این تعریف صادر شده.",
                  "   خودِ گواهینامه‌ها پاک نمی‌شوند، فقط این",
                  "   تعریف از رویداد برداشته می‌شود.", ""]
    lines.append("مطمئنید؟")
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🗑️ بله، حذف کن",
          "callback_data": f"evcD_{row_id}"}],
        [{"text": "🔙 نه، برگرد",
          "callback_data": f"evc_v_{row_id}"}]]})


def do_delete(cid, uid, row_id):
    if not _guard(cid, uid):
        return
    c = get_cert(row_id)
    if not c:
        return send(cid, "❌ پیدا نشد")
    eid = c["event_id"]
    delete_cert(row_id)
    send(cid, "🗑️ حذف شد")
    return show_panel(cid, uid, eid)


def show_ad_preview(cid, uid, eid):
    """👁️ پیش‌نمایش متنی که در تبلیغ رویداد دیده می‌شود"""
    if not _guard(cid, uid):
        return
    lines = ad_lines(eid)
    if not lines:
        txt = ("👁️ پیش‌نمایش تبلیغ\n━━━━━━━━━━━━━━\n\n"
               "📭 هیچ گواهینامه‌ای برای نمایش در تبلیغ فعال نیست.\n\n"
               "💡 در تنظیمات هر گواهینامه، «📣 در تبلیغ» را روشن کنید.")
    else:
        txt = ("👁️ این متن در تبلیغ رویداد دیده می‌شود\n"
               "━━━━━━━━━━━━━━\n\n" + "\n".join(lines))
    send_or_edit(cid, txt, {"inline_keyboard": [
        [{"text": "🔙 گواهینامه‌ها", "callback_data": f"evc_p_{eid}"}]]})


# ══════════════════════════════════════════════════════════
# 👤 سمت کاربر — دریافت گواهینامه
# ══════════════════════════════════════════════════════════
def user_get(cid, uid, cert_id):
    """📥 دریافت دوبارهٔ گواهینامهٔ صادرشده"""
    row = db_execute(
        "SELECT * FROM certificates WHERE id=? AND bale_user_id=?",
        (int(cert_id), int(uid)), fetch="one")
    if not row:
        return send(cid, "🌱 این گواهینامه پیدا نشد")
    if row.get("revoked"):
        return send(cid, "🚫 این گواهینامه باطل شده است")
    try:
        from certissue import send_cert_files
        return send_cert_files(cid, cert_id)
    except Exception as e:
        log(f"⚠️ ارسال گواهینامه: {e}")
        p = row.get("file_path") or row.get("png_path") or row.get("pdf_path")
        if p and Path(p).exists():
            from bale_api import send_document
            return send_document(cid, p, "🎓 گواهینامهٔ شما")
        return send(cid, "🌱 فایل در دسترس نیست — به برگزارکننده بگویید")


def user_issue(cid, uid, eid, row_id):
    """
    🎓 صدور گواهینامه به درخواست خود کاربر.

    فقط اگر شرط را داشته باشد و قبلاً نگرفته باشد.
    """
    # 🔒 فاز ۳۹ — صدور خودسرویس بسته است
    try:
        import certissue as _ci
        from auth import is_admin as _isadm
        if not _ci.self_issue_allowed() and not _isadm(uid):
            return _ci.deny_self_issue(cid)
    except ImportError:
        pass

    c = get_cert(row_id)
    if not c or int(c.get("event_id") or 0) != int(eid):
        return send(cid, "🌱 این گواهینامه پیدا نشد")
    if not c.get("is_active"):
        return send(cid, "🌱 این گواهینامه فعلاً غیرفعال است")

    ok, why = eligible(c, eid, uid)
    if not ok:
        return send(cid, f"🌱 هنوز نمی‌توانید بگیرید\n\n{why}")

    old = db_execute(
        "SELECT id FROM certificates WHERE event_id=? AND bale_user_id=? "
        "AND event_cert_id=? AND revoked=0",
        (int(eid), int(uid), int(row_id)), fetch="one")
    if old:
        return user_get(cid, uid, old["id"])

    send(cid, "⏳ در حال ساخت گواهینامه…")
    try:
        import certgen
        from events import get_event
        from auth import get_user
        ev = get_event(eid) or {}
        u = get_user(uid) or {}

        import attendance as _att
        serial = (_att.gen_serial() if hasattr(_att, "gen_serial")
                  else f"E{eid}-{row_id}-{uid}")
        mp = certgen.build_mapping(
            name=f"{u.get('first_name') or ''} "
                 f"{u.get('last_name') or ''}".strip(),
            national_id=u.get("national_id"),
            mobile=u.get("mobile"),
            event=ev.get("title"),
            date=ev.get("start_date"),
            organizer=(c.get("issuer") or ev.get("organizer")),
            serial=serial)
        mp.setdefault("verify_url", certgen.verify_url(serial))

        tpl = (certgen.get_template(c["template_id"])
               if c.get("template_id") else None) or certgen.get_template()
        cert_id = db_execute(
            "INSERT INTO certificates (event_id, bale_user_id, serial, "
            "template_id, event_cert_id, source, issued_at) "
            "VALUES (?,?,?,?,?,'event',datetime('now'))",
            (int(eid), int(uid), serial, (tpl or {}).get("id"),
             int(row_id)))
        # 🔍 فاز ۳۴ — شناسهٔ دولایه و تاریخ اعتبار
        try:
            import certverify as _cv
            info = _cv.stamp(cert_id, eid)
            if info.get("full_code"):
                mp["serial"] = info["full_code"]
                mp["verify_code"] = info["person_code"]
                mp["doc_no"] = info["doc_no"]
                mp["verify_url"] = _cv.verify_link(info["full_code"])
                if info.get("expires_on"):
                    mp["expires_on"] = info["expires_on"]
                mp["issued_on"] = info.get("issued_on") or ""
                # 🔴 باگ رفع‌شده (فاز ۳۷):
                #    اینجا برخلاف certbatch حتی `serial` محلی
                #    هم عوض نمی‌شد؛ پیام «شمارهٔ ثبت» به کاربر
                #    سریال موقت را نشان می‌داد نه شناسهٔ واقعی.
                if info.get("doc_no"):
                    serial = info["full_code"]
                db_execute("UPDATE certificates SET serial=? "
                           "WHERE id=?", (serial, cert_id))
        except Exception as _e:
            log(f"⚠️ شناسهٔ استعلام: {_e}")

        # 📷 فاز ۳۷ — عکس پرسنلی
        try:
            import certphoto as _cp
            _cp.attach(mp, uid, tpl)
        except Exception as _pe:
            log(f"⚠️ عکس پرسنلی: {_pe}")

        res = certgen.generate(mp, tpl)
        path = res.get("png") or res.get("pdf") or res.get("docx")
        if path:
            db_execute(
                "UPDATE certificates SET png_path=?, pdf_path=?, "
                "docx_path=?, file_path=? WHERE id=?",
                (res.get("png"), res.get("pdf"), res.get("docx"),
                 path, cert_id))
        # 🔴 باگ رفع‌شده (فاز ۳۷): شمارندهٔ کاربر بالا نمی‌رفت
        db_execute("UPDATE users SET total_certificates="
                   "COALESCE(total_certificates,0)+1 "
                   "WHERE bale_user_id=?", (int(uid),))
        # 🪞 آینهٔ سرور مشترک (بهترین‌تلاش)
        try:
            import shared_certificates as _sc
            _sc.sync_after_change(cert_id)
        except Exception:
            pass
        send(cid, (f"🎉 {c.get('title') or 'گواهینامه'} آماده شد\n"
                   f"🔖 شمارهٔ ثبت: {serial}"))
        return user_get(cid, uid, cert_id)
    except Exception as e:
        log(f"❌ صدور گواهینامهٔ رویداد: {e}")
        return send(cid, ("🌱 ساخت گواهینامه به مشکل خورد.\n\n"
                          "کمی بعد دوباره امتحان کنید."))
