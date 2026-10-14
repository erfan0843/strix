"""
✍️ موتور پر کردن فرم توسط کاربر — فاز ۹

پشتیبانی از دو حالت نمایش:
  • user_choice — لیست همه سوالات، کاربر هرکدام را خواست پر می‌کند و می‌تواند برگردد
  • one_by_one — سوالات پشت سر هم بدون بازگشت

اعتبارسنجی کامل هر نوع فیلد + پیشنهاد خودکار + شرط نمایش + پرداخت + بلیت
"""
import json
import re
import time
from datetime import datetime
from urllib.parse import urlencode

import iran_data
import jalali as _jd
import shared_api
from auth import (
    clear_state,
    get_state_data,
    get_user,
    log_action,
    normalize_digits,
    normalize_mobile,
    set_state,
    update_state_data,
)
from bale_api import (
    BTN_BACK,
    BTN_SKIP,
    kb_cancel,
    kb_remove,
    send,
    send_or_edit,
    send_photo,
)
from config import CURRENCY_LABEL, FILES_DIR, NORA_WEBAPP_URL
from database import db_execute, db_scalar, get_setting, log
from form_fields import condition_met
from forms import (
    DISPLAY_MODES,
    FORM_TYPES,
    cache_answer,
    chosen_items,
    field_label,
    field_meta,
    fmt_amount,
    form_gate,
    form_link,
    form_total_price,
    gen_qr_code,
    gen_tracking,
    get_field,
    get_fields,
    get_form,
    get_form_by_slug,
    get_suggestions,
    item_is_full,
    item_label,
    jnow,
    parse_items,
    parse_options,
    price_preview,
    recount_responses,
    render,
    set_items,
)


STATE_FILL = "form_fill"

# فیلدهایی که با پیام (نه دکمه) پاسخ داده می‌شوند
TEXT_KINDS = {
    "text", "longtext", "number", "email", "mobile", "national_id", "postal",
    "card", "sheba", "amount", "date", "time", "datetime", "plate",
}
MEDIA_KINDS = {"photo", "file", "video", "voice", "location"}
BUTTON_KINDS = {"choice", "multi", "dropdown", "quiz", "rating", "confirm",
                "education", "province_city", "item"}


# ==================== ورود به فرم ====================
def open_form(cid, uid, slug_or_id, user=None):
    """صفحه ورود فرم (Landing) — با بنر و لوگو"""
    form = None
    s = str(slug_or_id or "").strip()
    if s.startswith("id") and s[2:].isdigit():
        form = get_form(int(s[2:]))
    if not form:
        form = get_form_by_slug(s)
    if not form and s.isdigit():
        form = get_form(int(s))

    if not form:
        return send(cid, "❌ فرم مورد نظر پیدا نشد.\n\n💡 لینک را دوباره بررسی کنید.")

    db_execute("UPDATE forms SET views_count=COALESCE(views_count,0)+1 WHERE id=?",
               (form["id"],))

    ok, reason, extra = form_gate(form)
    if not ok:
        return _closed_message(cid, form, reason, extra)

    # بررسی دسترسی
    u = get_user(uid)
    if form.get("require_auth") and not (u and u.get("is_authenticated")):
        return send(cid, (
            "🔐 برای تکمیل این فرم باید احراز هویت کنید.\n\n"
            "لطفاً /start را بزنید و شماره خود را تأیید کنید."
        ))
    if form.get("require_profile"):
        pct = int((u or {}).get("complete_profile_percent") or 0)
        if pct < 70:
            return send(cid, (
                f"📋 برای تکمیل این فرم، پروفایل شما باید کامل باشد.\n\n"
                f"📊 تکمیل فعلی: {pct}%\n\n"
                f"💡 از «👤 پروفایل من» تکمیل کنید."
            ), {"inline_keyboard": [
                [{"text": "👤 تکمیل پروفایل", "callback_data": "profile_fill"}]]})

    # پاسخ قبلی
    prev = db_execute("""SELECT * FROM form_responses WHERE form_id=? AND bale_user_id=?
        AND status IN ('completed','confirmed') ORDER BY id DESC LIMIT 1""",
        (form["id"], uid), fetch="one")
    from forms import user_can_edit as _uce
    if prev and form.get("one_per_user") and not _uce(form):
        return send(cid, render("form_txt_duplicate",
                                tracking=prev.get("tracking_code") or "—"),
                    {"inline_keyboard": [
                        [{"text": "📄 مشاهده پاسخ من", "callback_data": f"ffmy_{prev['id']}"}],
                        [{"text": "🏠 منوی اصلی", "callback_data": "back_main"}]]})

    fields = get_fields(form["id"])
    if not fields:
        return send(cid, "⚠️ این فرم هنوز سوالی ندارد.")

    t = FORM_TYPES.get(form.get("form_type") or "questionnaire",
                       FORM_TYPES["questionnaire"])
    minutes = max(1, round(len(fields) * 0.4))
    body = render("form_txt_landing",
                  title=form["title"],
                  description=form.get("description") or t["desc"],
                  fields=len(fields), minutes=minutes)

    # 💳 نمایش هزینه در ابتدای فرم — کاملاً به انتخاب ادمین
    #    پیش‌فرض: هیچ چیزی درباره هزینه گفته نمی‌شود
    extra_lines = []
    show_cost = int(form.get("show_price_upfront") or 0)
    if show_cost:
        has_cost, cost_txt = price_preview(form["id"])
        if has_cost:
            extra_lines.append("\n" + cost_txt)
            extra_lines.append("💡 پرداخت در پایان فرم انجام می‌شود.")
        else:
            extra_lines.append("\n🎁 این فرم رایگان است")
    if form.get("limit_enabled") and form.get("max_responses"):
        left = int(form["max_responses"]) - int(form.get("responses_count") or 0)
        extra_lines.append(f"👥 ظرفیت باقیمانده: {max(0, left)} نفر")
    if form.get("end_at"):
        extra_lines.append(f"⛔ مهلت: {form['end_at']}")
    if form.get("ticket_enabled"):
        extra_lines.append("🎫 پس از ثبت، بلیت دریافت می‌کنید")
    # 🆕 فاز ۱۵
    if form.get("cert_enabled"):
        extra_lines.append("🎓 پس از تکمیل، گواهینامه صادر می‌شود")
    if form.get("idcard_enabled"):
        extra_lines.append("🆔 پس از ثبت، کارت شما صادر می‌شود")

    # 👋 صفحه خوش‌آمدگویی (فاز ۱۵) — پیش از توضیحات فرم
    welcome = (form.get("welcome_text") or "").strip()
    head = (welcome + "\n━━━━━━━━━━━━━━\n\n") if welcome else ""

    text = head + body + "\n" + "\n".join(extra_lines)

    kb = {"inline_keyboard": [
        [{"text": "▶️ شروع پر کردن فرم", "callback_data": f"ffstart_{form['id']}"}],
        [{"text": "🏠 منوی اصلی", "callback_data": "back_main"}],
    ]}

    banner = form.get("banner_file_id")
    if banner:
        r = send_photo(cid, banner, text[:1000], kb)
        if r.get("ok"):
            return r
    return send_or_edit(cid, text, kb)


def _closed_message(cid, form, reason, extra):
    if reason == "not_started":
        return send(cid, render("form_txt_not_started", start=extra or "—"))
    if reason == "expired":
        return send(cid, render("form_txt_expired", end=extra or "—"))
    if reason == "full":
        return send(cid, render("form_txt_full"))
    # 🆕 فاز ۱۸-الف
    if reason == "max_attempts":
        return send(cid, (
            f"🌟 شما قبلاً شرکت کرده‌اید\n━━━━━━━━━━━━━━\n\n"
            f"سقف مجاز شرکت در این فرم {extra} بار است.\n\n"
            f"سپاس از همراهی شما 💚"))
    if reason == "waitlist":
        return send(cid, (
            "⏳ ظرفیت تکمیل شده است\n━━━━━━━━━━━━━━\n\n"
            "ولی نگران نباشید — اسم شما را در لیست انتظار می‌گذاریم.\n"
            "اگر جایی باز شود، حتماً خبرتان می‌کنیم 💚"))
    if reason == "private":
        return send(cid, (
            "🔒 این فرم خصوصی است\n━━━━━━━━━━━━━━\n\n"
            "برای دسترسی، کد دعوت لازم دارید.\n"
            "اگر کد دارید، آن را برای ما بفرستید 💚"))
    # 🎉 فاز ۳۳ — فرم مخصوص شرکت‌کنندگان یک رویداد
    if reason in ("ev_not_registered", "ev_not_attended"):
        return _event_only_message(cid, form, reason, extra)
    return send(cid, render("form_txt_closed", reason="این فرم غیرفعال است."))


def _event_only_message(cid, form, reason, extra):
    """
    🎉 پیام مهربان وقتی فرم مخصوص یک رویداد است.

    به‌جای «دسترسی ندارید»، خودِ رویداد را نشان می‌دهیم تا
    کاربر بتواند ثبت‌نام کند.
    """
    ev = None
    try:
        eid = int(extra or form.get("event_id") or 0)
        if eid:
            from events import get_event
            ev = get_event(eid)
    except Exception:
        eid = 0
    title = (ev or {}).get("title") or "رویداد"

    if reason == "ev_not_attended":
        txt = (f"✋ این فرم برای شرکت‌کنندگان است\n"
               f"━━━━━━━━━━━━━━\n\n"
               f"🎉 {title}\n\n"
               f"این فرم فقط برای کسانی باز است که در رویداد\n"
               f"حضور داشته‌اند.\n\n"
               f"💡 اگر حضور داشتید ولی ثبت نشده، به برگزارکننده\n"
               f"   اطلاع دهید 💚")
    else:
        txt = (f"🎉 این فرم مخصوص یک رویداد است\n"
               f"━━━━━━━━━━━━━━\n\n"
               f"📅 {title}\n\n"
               f"برای پر کردن این فرم، باید در این رویداد\n"
               f"ثبت‌نام کرده باشید.\n\n"
               f"💚 اگر هنوز ثبت‌نام نکرده‌اید، از دکمهٔ زیر\n"
               f"   اقدام کنید.")

    btns = []
    if ev and (ev.get("status") or "") in ("published", "open"):
        btns.append([{"text": "📅 دیدن رویداد",
                      "callback_data": f"uev_{ev['id']}"}])
    btns.append([{"text": "🎉 رویدادها", "callback_data": "u_events"}])
    btns.append([{"text": "🏠 منوی اصلی", "callback_data": "back_main"}])
    return send(cid, txt, {"inline_keyboard": btns})


# ==================== شروع پر کردن ====================
def start_fill(cid, uid, fid):
    form = get_form(fid)
    if not form:
        return send(cid, "❌ فرم یافت نشد")
    ok, reason, extra = form_gate(form, uid)
    if not ok:
        return _closed_message(cid, form, reason, extra)

    # 🔐 فاز ۱۸-الف — سطح دسترسی فرم
    from forms import can_user_open
    okv, whyv = can_user_open(form, uid, via_link=True)
    if not okv:
        return _closed_message(cid, form, "private", whyv)

    fields = get_fields(fid)
    if not fields:
        return send(cid, "⚠️ این فرم سوالی ندارد.")

    # پاسخ نیمه‌کاره؟
    draft = db_execute("""SELECT * FROM form_responses WHERE form_id=? AND bale_user_id=?
        AND status='draft' ORDER BY id DESC LIMIT 1""", (fid, uid), fetch="one")

    if draft:
        n = db_scalar("SELECT COUNT(*) FROM form_answers WHERE response_id=?",
                      (draft["id"],))
        if n:
            return send_or_edit(cid, (
                f"📝 فرم نیمه‌کاره\n━━━━━━━━━━━━━━\n\n"
                f"📋 {form['title']}\n"
                f"✅ {n} سوال قبلاً پاسخ داده‌اید.\n\n"
                f"می‌خواهید ادامه دهید یا از اول شروع کنید؟"
            ), {"inline_keyboard": [
                [{"text": "▶️ ادامه", "callback_data": f"ffres_{draft['id']}"}],
                [{"text": "🔄 شروع مجدد", "callback_data": f"ffnew_{fid}"}],
                [{"text": "❌ انصراف", "callback_data": "back_main"}]]})
        rid = draft["id"]
    else:
        rid = _new_response(fid, uid)

    if not rid:
        return send(cid, "❌ خطا در ایجاد فرم")
    return _begin(cid, uid, form, rid)


def restart_fill(cid, uid, fid):
    """شروع مجدد — پاسخ‌های نیمه‌کاره پاک می‌شوند"""
    drafts = db_execute("SELECT id FROM form_responses WHERE form_id=? AND "
                        "bale_user_id=? AND status='draft'", (fid, uid), fetch="all") or []
    for d in drafts:
        db_execute("DELETE FROM form_answers WHERE response_id=?", (d["id"],))
        db_execute("DELETE FROM form_responses WHERE id=?", (d["id"],))
    form = get_form(fid)
    if not form:
        return send(cid, "❌ فرم یافت نشد")
    rid = _new_response(fid, uid)
    return _begin(cid, uid, form, rid)


def resume_fill(cid, uid, rid):
    r = db_execute("SELECT * FROM form_responses WHERE id=?", (int(rid),), fetch="one")
    if not r or r.get("bale_user_id") != uid:
        return send(cid, "❌ یافت نشد")
    form = get_form(r["form_id"])
    if not form:
        return send(cid, "❌ فرم یافت نشد")
    return _begin(cid, uid, form, r["id"])


def _new_response(fid, uid):
    u = get_user(uid) or {}
    return db_execute("""INSERT INTO form_responses
        (form_id, bale_user_id, user_id, status, started_at)
        VALUES (?,?,?,'draft',CURRENT_TIMESTAMP)""",
        (fid, uid, u.get("id")))


def _begin(cid, uid, form, rid):
    st = {
        "fid": form["id"], "rid": rid, "idx": 0, "multi": [],
        "prov": None, "files": [], "items": [],
    }

    # ⏱️ فاز ۱۸-الف — مهلت پاسخ‌دهی (آزمون و مسابقه)
    limit = int(form.get("time_limit_min") or 0)
    if limit > 0:
        st["deadline"] = int(time.time()) + limit * 60
        st["limit_min"] = limit

    # 🔀 فاز ۱۸-الف — ترتیب تصادفی سوالات
    if form.get("shuffle_questions"):
        import random as _r
        ids = [f["id"] for f in get_fields(form["id"])]
        _r.shuffle(ids)
        st["order"] = ids

    set_state(uid, STATE_FILL, st, merge=False)
    send(cid, render("form_txt_start"), kb_remove())

    if limit > 0:
        send(cid, (
            f"⏱️ مهلت شما: {limit} دقیقه\n\n"
            f"از همین حالا شمارش شروع شد — با آرامش پاسخ دهید 💚"))

    if (form.get("display_mode") or "one_by_one") == "one_by_one":
        return ask_next(cid, uid)
    return show_question_list(cid, uid)


def _time_left(uid):
    """ثانیه باقی‌مانده مهلت — None یعنی بدون محدودیت"""
    st = get_state_data(uid) or {}
    dl = st.get("deadline")
    if not dl:
        return None
    return int(dl) - int(time.time())


def _check_deadline(cid, uid, rid=None):
    """
    ⏱️ اگر مهلت تمام شده باشد، فرم را خودکار ثبت می‌کند.
    خروجی: True یعنی وقت تمام شد و کار انجام شد.
    """
    left = _time_left(uid)
    if left is None or left > 0:
        return False
    st = get_state_data(uid) or {}
    rid = rid or st.get("rid")
    send(cid, (
        "⏱️ زمان شما به پایان رسید\n━━━━━━━━━━━━━━\n\n"
        "پاسخ‌هایی که تا این لحظه داده‌اید ثبت می‌شود.\n"
        "سپاس از تلاش‌تان 💚"))
    if rid:
        try:
            return submit_form(cid, uid, rid) or True
        except Exception as e:
            log(f"⚠️ ثبت خودکار پس از پایان مهلت: {e}")
    clear_state(uid)
    return True


def _ordered_fields(uid, fields):
    """ترتیب سوالات با احترام به shuffle"""
    st = get_state_data(uid) or {}
    order = st.get("order")
    if not order:
        return fields
    pos = {fid: i for i, fid in enumerate(order)}
    return sorted(fields, key=lambda f: pos.get(f["id"], 9999))


# ==================== حالت ۱: لیست سوالات ====================
def show_question_list(cid, uid, rid=None):
    st = get_state_data(uid)
    rid = rid or st.get("rid")
    r = db_execute("SELECT * FROM form_responses WHERE id=?", (rid,), fetch="one")
    if not r:
        clear_state(uid)
        return send(cid, "⚠️ اطلاعات این مرحله دیگر در دسترس نیست؛ از فهرست فرم‌ها دوباره شروع کنید.")
    form = get_form(r["form_id"])
    if not form:
        return send(cid, "❌ فرم یافت نشد")

    answers = _answer_map(rid)
    fields = [f for f in get_fields(form["id"]) if condition_met(f, answers)]
    done = sum(1 for f in fields if answers.get(f["id"]) not in (None, ""))
    req_missing = [f for f in fields
                   if f.get("is_required") and answers.get(f["id"]) in (None, "")]

    lines = [f"📋 {form['title']}", "━━━━━━━━━━━━━━", ""]
    if form.get("show_progress"):
        pct = int(done * 100 / len(fields)) if fields else 0
        blocks = max(0, min(10, pct // 10))
        lines += [f"📊 پیشرفت: {done}/{len(fields)} ({pct}%)",
                  "▓" * blocks + "░" * (10 - blocks), ""]

    ready = not req_missing
    lines.append("✅ همه سوالات اجباری پاسخ داده شد — می‌توانید ثبت کنید."
                 if ready else "روی هر سوال بزنید و پاسخ دهید:")
    lines.append("")
    btns = []
    for i, f in enumerate(fields, 1):
        m = field_meta(f.get("field_type"))
        val = answers.get(f["id"])
        mark = "✅" if val not in (None, "") else ("⭐" if f.get("is_required") else "⭕")
        short = _short(val) if val not in (None, "") else ""
        lines.append(f"{mark} {i}. {field_label(f)[:40]}" + (f"\n     └ {short}" if short else ""))
        btns.append([{"text": f"{mark} {i}. {m['icon']} {field_label(f)[:26]}",
                      "callback_data": f"ffq_{f['id']}"}])

    # ⚡ اگر سوال بی‌پاسخی هست، دکمه «ادامه» مستقیم می‌بردش سراغش
    nxt = next((f for f in fields if answers.get(f["id"]) in (None, "")), None)
    if nxt:
        btns.insert(0, [{"text": "▶️ ادامه از سوال بعدی",
                         "callback_data": f"ffq_{nxt['id']}"}])

    if req_missing:
        lines += ["", f"⚠️ {len(req_missing)} سوال اجباری باقی مانده",
                  "برای ثبت نهایی باید پاسخ داده شوند."]

    btns.append([{"text": (f"📤 ثبت نهایی ({done}/{len(fields)})" if ready
                           else f"📤 ثبت نهایی — {len(req_missing)} سوال اجباری مانده"),
                  "callback_data": f"ffsubmit_{rid}"}])
    btns.append([{"text": "❌ انصراف", "callback_data": f"ffcancel_{rid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def _short(v, n=34):
    s = str(v or "").replace("\n", " ")
    return s[:n] + "…" if len(s) > n else s


def _answer_map(rid):
    """{field_id: value_text} از پاسخ‌های ثبت‌شده"""
    rows = db_execute("SELECT field_id, value_text, value_options, file_id "
                      "FROM form_answers WHERE response_id=?", (rid,), fetch="all") or []
    out = {}
    for r in rows:
        v = r.get("value_text")
        if not v and r.get("value_options"):
            try:
                arr = json.loads(r["value_options"])
                v = "، ".join(str(x) for x in arr) if isinstance(arr, list) else r["value_options"]
            except (ValueError, TypeError):
                v = r["value_options"]
        if not v and r.get("file_id"):
            v = "📎 فایل"
        out[r["field_id"]] = v
    return out


# ==================== پرسیدن یک سوال ====================
def ask_field(cid, uid, field_id):
    """پرسیدن سوال مشخص (حالت لیست)"""
    f = get_field(field_id)
    if not f:
        return send(cid, "❌ سوال یافت نشد")
    st = get_state_data(uid)
    if not st.get("rid"):
        return send(cid, "⚠️ ابتدا فرم را شروع کنید")
    update_state_data(uid, {"cur": field_id, "multi": [], "files": [], "prov": None})
    return _render_question(cid, uid, f)


def go_prev_question(cid, uid):
    """
    ⬅️ برگشت به سوال قبل (حالت تک‌مرحله‌ای).

    🔴 بدون این، کاربری که روی یک فیلد گزینه‌ای بود هیچ راه برگشتی
       نداشت و مجبور بود کل فرم را رها کند.
    """
    st = get_state_data(uid)
    rid = st.get("rid")
    r = db_execute("SELECT * FROM form_responses WHERE id=?", (rid,),
                   fetch="one")
    if not r:
        clear_state(uid)
        return send(cid, "⚠️ اطلاعات این مرحله دیگر در دسترس نیست؛ از فهرست فرم‌ها دوباره شروع کنید.")

    form = get_form(r["form_id"])
    one_by_one = (form or {}).get("display_mode", "one_by_one") == "one_by_one"
    if not one_by_one:
        return show_question_list(cid, uid, rid)

    idx = int(st.get("idx") or 0)
    if idx <= 0:
        send(cid, "🌟 این اولین سوال است")
        return ask_next(cid, uid)

    update_state_data(uid, {"idx": idx - 1})
    return ask_next(cid, uid)


def ask_next(cid, uid):
    """حالت one_by_one — سوال بعدی"""
    st = get_state_data(uid)
    rid = st.get("rid")
    r = db_execute("SELECT * FROM form_responses WHERE id=?", (rid,), fetch="one")
    if not r:
        clear_state(uid)
        return send(cid, "⚠️ اطلاعات این مرحله دیگر در دسترس نیست؛ از فهرست فرم‌ها دوباره شروع کنید.")

    # ⏱️ فاز ۱۸-الف — مهلت تمام شد؟
    if _check_deadline(cid, uid, rid):
        return None

    answers = _answer_map(rid)
    fields = [f for f in get_fields(r["form_id"]) if condition_met(f, answers)]
    fields = _ordered_fields(uid, fields)   # 🔀 ترتیب تصادفی
    idx = int(st.get("idx") or 0)

    # از اولین سوال بی‌پاسخ ادامه بده
    while idx < len(fields) and answers.get(fields[idx]["id"]) not in (None, ""):
        idx += 1

    if idx >= len(fields):
        return submit_form(cid, uid, rid)

    update_state_data(uid, {"idx": idx, "cur": fields[idx]["id"],
                            "multi": [], "files": [], "prov": None})
    return _render_question(cid, uid, fields[idx], idx + 1, len(fields))


def _render_question(cid, uid, f, pos=None, total=None):
    st = get_state_data(uid)
    rid = st.get("rid")
    r = db_execute("SELECT * FROM form_responses WHERE id=?", (rid,), fetch="one")
    form = get_form(r["form_id"]) if r else None
    if not form:
        return send(cid, "❌ فرم یافت نشد")

    m = field_meta(f.get("field_type"))
    kind = m.get("kind")
    one_by_one = (form.get("display_mode") or "one_by_one") == "one_by_one"

    lines = []
    if pos and total:
        done = sum(1 for x in get_fields(form["id"])
                   if _answer_map(rid).get(x["id"]) not in (None, ""))
        if form.get("show_progress"):
            pct = int(done * 100 / total) if total else 0
            blocks = max(0, min(10, pct // 10))
            lines += [f"📊 سوال {pos} از {total}  ({done} پاسخ داده‌شده)",
                      "▓" * blocks + "░" * (10 - blocks), ""]
        else:
            lines += [f"📊 سوال {pos} از {total}", ""]

    # ⏱️ فاز ۱۸-الف — زمان باقی‌مانده (آزمون/مسابقه)
    left = _time_left(uid)
    if left is not None:
        if left <= 0:
            return _check_deadline(cid, uid, rid)
        mins, secs = divmod(max(0, left), 60)
        warn = "🔴" if mins < 2 else ("🟡" if mins < 5 else "⏱️")
        lines.append(f"{warn} زمان باقی‌مانده: {mins}:{secs:02d}")
        lines.append("")

    star = " *" if f.get("is_required") else ""
    lines.append(f"{m['icon']} {field_label(f)}{star}")
    if f.get("description"):
        lines.append(f"\n📄 {f['description']}")
    if f.get("help_text"):
        lines.append(f"\n⚠️ {f['help_text']}")

    # 📜 متن کامل قوانین را نشان بده (وگرنه تأیید بی‌معنی است)
    if m.get("has_terms") and f.get("terms_text"):
        lines.append("\n" + "─" * 18)
        lines.append(str(f["terms_text"])[:2500])
        lines.append("─" * 18)

    # 🎓 آیتم‌ها با هزینه
    if kind == "item":
        items = parse_items(f)
        if items:
            lines.append("\n💰 گزینه‌های موجود:")
            for it in items:
                p = int(it.get("price") or 0)
                tag = f"{fmt_amount(p)} {CURRENCY_LABEL}" if p else "رایگان"
                mark = "🚫" if item_is_full(it) else "▫️"
                lines.append(f"{mark} {it['title']} — {tag}")
                if it.get("desc"):
                    lines.append(f"    {it['desc'][:70]}")

    hint = _hint_for(f, m)
    if hint:
        lines.append(f"\n💡 {hint}")

    # پیشنهاد خودکار
    sug = []
    if m.get("cache") and kind in TEXT_KINDS:
        sug = get_suggestions(uid, m["cache"], 3)
        if sug:
            lines.append("\n📌 پاسخ‌های قبلی شما:")

    text = "\n".join(lines)
    kb = _keyboard_for(f, m, kind, sug, one_by_one, form, uid)

    if f.get("media_file_id"):
        res = send_photo(cid, f["media_file_id"], text[:900], kb)
        if res.get("ok"):
            return res
    return send_or_edit(cid, text, kb)


def _hint_for(f, m):
    kind = m.get("kind")
    lo, hi = f.get("min_val"), f.get("max_val")
    if kind in ("text", "longtext"):
        if lo and hi:
            return f"بین {lo} تا {hi} کاراکتر"
        if hi:
            return f"حداکثر {hi} کاراکتر"
    if kind == "number":
        if lo is not None and hi is not None:
            return f"عددی بین {lo} تا {hi}"
    if kind == "mobile":
        return "مثال: 09123456789"
    if kind == "national_id":
        return "۱۰ رقم بدون خط تیره"
    if kind == "postal":
        return "۱۰ رقم"
    if kind == "email":
        return "مثال: name@example.com"
    if kind == "card":
        return "۱۶ رقم"
    if kind == "sheba":
        return "۲۴ رقم بعد از IR"
    if kind == "date":
        return "تاریخ شمسی — مثال: 1370/05/12"
    if kind == "time":
        return "مثال: 18:30"
    if kind == "datetime":
        return "مثال: 1404/06/15 18:30"
    if kind == "amount":
        return f"مبلغ به {CURRENCY_LABEL}"
    if kind == "plate":
        return "مثال: 12 ب 345 ایران 10"
    if kind in ("file", "photo", "video", "voice"):
        n = f.get("max_files") or 1
        return f"تا {n} فایل" if n > 1 else "یک فایل ارسال کنید"
    if kind == "location":
        return "دکمه «ارسال موقعیت» را بزنید"
    return ""


def _keyboard_for(f, m, kind, sug, one_by_one, form, uid_for_kb=None):
    """
    کیبورد مناسب هر نوع فیلد.

    🔴 باگ رفع‌شده: در حالت تک‌مرحله‌ای (پیش‌فرض فاز ۱۵) فیلدهایی که
       کیبورد شیشه‌ای دارند (گزینه‌ای، چندگزینه‌ای، امتیازی و…) هیچ
       راه برگشتی نداشتند و کاربر گیر می‌کرد. حالا دکمه «⬅️ سوال قبل»
       گذاشته می‌شود.
    """
    # همیشه راه برگشت باشد تا کاربر هرگز گیر نکند
    nav_back = [{"text": "⬅️ سوال قبل", "callback_data": "ffprev"}] \
        if one_by_one else \
        [{"text": "📋 همه سوالات", "callback_data": "fflist"}]

    if kind in ("choice", "dropdown", "quiz"):
        opts = parse_options(f)
        # 🎲 فاز ۱۸-الف — ترتیب تصادفی گزینه‌ها (آزمون)
        #    ⚠️ ایندکس اصلی حفظ می‌شود وگرنه پاسخ اشتباه ثبت می‌شد.
        order = list(enumerate(opts, 1))
        if (form or {}).get("shuffle_options"):
            import random as _r
            seed = f"{f.get('id')}-{(form or {}).get('id')}"
            _r.Random(seed).shuffle(order)
        btns = [[{"text": o[:60], "callback_data": f"ffo_{i}_{f['id']}"}]
                for i, o in order]
        if not f.get("is_required"):
            btns.append([{"text": "⏭️ رد کردن", "callback_data": f"ffskip_{f['id']}"}])
        if nav_back:
            btns.append(nav_back)
        return {"inline_keyboard": btns}

    if kind == "multi":
        opts = parse_options(f)
        btns = [[{"text": f"⬜ {o[:56]}", "callback_data": f"ffm_{i}_{f['id']}"}]
                for i, o in enumerate(opts, 1)]
        btns.append([{"text": "✅ تأیید و ادامه", "callback_data": f"ffmok_{f['id']}"}])
        if not f.get("is_required"):
            btns.append([{"text": "⏭️ رد کردن", "callback_data": f"ffskip_{f['id']}"}])
        if nav_back:
            btns.append(nav_back)
        return {"inline_keyboard": btns}

    if kind == "rating":
        scale = int(m.get("scale") or 5)
        emoji = m.get("emoji") or "⭐"
        btns, row = [], []
        for i in range(1, scale + 1):
            row.append({"text": f"{emoji}{i}", "callback_data": f"ffr_{i}_{f['id']}"})
            if len(row) == 5:
                btns.append(row)
                row = []
        if row:
            btns.append(row)
        if not f.get("is_required"):
            btns.append([{"text": "⏭️ رد کردن", "callback_data": f"ffskip_{f['id']}"}])
        if nav_back:
            btns.append(nav_back)
        return {"inline_keyboard": btns}

    if kind == "confirm":
        btns = [[{"text": "✅ می‌پذیرم", "callback_data": f"ffy_{f['id']}"}]]
        if not f.get("is_required"):
            btns.append([{"text": "❌ نمی‌پذیرم", "callback_data": f"ffn_{f['id']}"}])
        if nav_back:
            btns.append(nav_back)
        return {"inline_keyboard": btns}

    if kind == "education":
        btns = [[{"text": f"🎓 {lv}", "callback_data": f"ffe_{i}_{f['id']}"}]
                for i, lv in enumerate(iran_data.EDUCATION_LEVELS, 1)]
        if not f.get("is_required"):
            btns.append([{"text": "⏭️ رد کردن", "callback_data": f"ffskip_{f['id']}"}])
        if nav_back:
            btns.append(nav_back)
        return {"inline_keyboard": btns}

    if kind == "province_city":
        btns, row = [], []
        for i, p in enumerate(iran_data.PROVINCE_LIST, 1):
            row.append({"text": p[:18], "callback_data": f"ffp_{i}_{f['id']}"})
            if len(row) == 2:
                btns.append(row)
                row = []
        if row:
            btns.append(row)
        if not f.get("is_required"):
            btns.append([{"text": "⏭️ رد کردن", "callback_data": f"ffskip_{f['id']}"}])
        if nav_back:
            btns.append(nav_back)
        return {"inline_keyboard": btns}

    if kind == "item":
        items = parse_items(f)
        if not items:
            btns = [[{"text": "⏭️ رد کردن", "callback_data": f"ffskip_{f['id']}"}]]
            if nav_back:
                btns.append(nav_back)
            return {"inline_keyboard": btns}

        # 🆕 فاز ۲۳ — چند مورد هزینه‌دار با هم
        #    «مثلا من مورد ۱ و مورد ۲ رو انتخاب کنم و بعد تایید کنم»
        if f.get("multi_item"):
            st = get_state_data(uid_for_kb) if uid_for_kb else {}
            sel = list(st.get("items") or [])
            btns = []
            for i, it in enumerate(items, 1):
                if item_is_full(it) and i not in sel:
                    btns.append([{"text": f"🚫 {it['title'][:38]} (تکمیل)",
                                  "callback_data": "noop"}])
                    continue
                mark = "☑️" if i in sel else "⬜"
                btns.append([{"text": f"{mark} {item_label(it)[:56]}",
                              "callback_data": f"ffim_{i}_{f['id']}"}])
            total = sum(int(items[i - 1].get("price") or 0)
                        for i in sel if 1 <= i <= len(items))
            lbl = f"✅ تأیید ({len(sel)} مورد"
            if total:
                lbl += f" — {fmt_amount(total)} {CURRENCY_LABEL}"
            lbl += ")"
            btns.append([{"text": lbl[:60],
                          "callback_data": f"ffiok_{f['id']}"}])
            if not f.get("is_required"):
                btns.append([{"text": "⏭️ رد کردن",
                              "callback_data": f"ffskip_{f['id']}"}])
            if nav_back:
                btns.append(nav_back)
            return {"inline_keyboard": btns}

        btns = []
        for i, it in enumerate(items, 1):
            if item_is_full(it):
                btns.append([{"text": f"🚫 {it['title'][:40]} (تکمیل)",
                              "callback_data": "noop"}])
            else:
                btns.append([{"text": item_label(it)[:60],
                              "callback_data": f"ffi_{i}_{f['id']}"}])
        if not f.get("is_required"):
            btns.append([{"text": "⏭️ رد کردن", "callback_data": f"ffskip_{f['id']}"}])
        if nav_back:
            btns.append(nav_back)
        return {"inline_keyboard": btns}

    if kind == "verify_mobile":
        # روش تأیید را ادمین تعیین می‌کند: contact / otp / both
        mode = (form.get("phone_verify_mode") or "both").strip().lower()
        rows = []
        if mode in ("contact", "both"):
            rows.append([{"text": "📱 ارسال شماره‌ام", "request_contact": True}])
        if mode in ("otp", "both"):
            for s in sug[:2]:
                rows.append([{"text": s}])
        if not f.get("is_required"):
            rows.append([{"text": BTN_SKIP}])
        rows.append([{"text": BTN_BACK}, {"text": "🏠 منوی اصلی"}])
        return {"keyboard": rows, "resize_keyboard": True}

    # ⚠️ location/mobile به کیبورد reply نیاز دارند (request_location/contact)
    # پس دکمه شیشه‌ای «همه سوالات» اینجا ممکن نیست؛ در عوض BTN_BACK
    # می‌گذاریم که handle_text آن را به فهرست سوالات می‌برد.
    if kind == "location":
        rows = [[{"text": "📍 ارسال موقعیت من", "request_location": True}]]
        if not f.get("is_required"):
            rows.append([{"text": BTN_SKIP}])
        rows.append([{"text": BTN_BACK}, {"text": "🏠 منوی اصلی"}])
        return {"keyboard": rows, "resize_keyboard": True}

    if kind == "mobile":
        rows = [[{"text": "📱 ارسال شماره‌ام", "request_contact": True}]]
        for s in sug[:2]:
            rows.append([{"text": s}])
        if not f.get("is_required"):
            rows.append([{"text": BTN_SKIP}])
        rows.append([{"text": BTN_BACK}, {"text": "🏠 منوی اصلی"}])
        return {"keyboard": rows, "resize_keyboard": True}

    # فیلدهای متنی و فایل — کیبورد reply
    rows = []
    for s in sug[:3]:
        rows.append([{"text": s[:60]}])
    if not f.get("is_required"):
        rows.append([{"text": BTN_SKIP}])
    rows.append([{"text": BTN_BACK}, {"text": "🏠 منوی اصلی"}])
    return {"keyboard": rows, "resize_keyboard": True}


# ==================== اعتبارسنجی ====================
def validate(f, m, raw):
    """
    اعتبارسنجی پاسخ.
    خروجی: (ok, value_or_error, number_or_None)
    """
    kind = m.get("kind")
    s = str(raw or "").strip()
    if not s:
        return False, "پاسخ خالی است", None

    lo, hi = f.get("min_val"), f.get("max_val")

    if kind in ("text", "longtext"):
        if lo and len(s) < int(lo):
            return False, f"حداقل {lo} کاراکتر لازم است", None
        if hi and len(s) > int(hi):
            return False, f"حداکثر {hi} کاراکتر مجاز است", None
        return True, s, None

    if kind == "number":
        d = normalize_digits(s).replace(",", "").replace("٬", "")
        neg = d.startswith("-")
        core = d[1:] if neg else d
        if not core.replace(".", "", 1).isdigit():
            return False, "فقط عدد وارد کنید", None
        try:
            v = float(d)
        except ValueError:
            return False, "عدد نامعتبر", None
        if lo is not None and v < float(lo):
            return False, f"حداقل مقدار: {lo}", None
        if hi is not None and v > float(hi):
            return False, f"حداکثر مقدار: {hi}", None
        return True, (str(int(v)) if v == int(v) else str(v)), v

    if kind == "amount":
        d = "".join(ch for ch in normalize_digits(s) if ch.isdigit())
        if not d:
            return False, "مبلغ را با عدد وارد کنید", None
        v = int(d)
        if lo is not None and v < int(lo):
            return False, f"حداقل مبلغ: {int(lo):,}", None
        if hi is not None and v > int(hi):
            return False, f"حداکثر مبلغ: {int(hi):,}", None
        return True, f"{v:,}", float(v)

    if kind == "email":
        if not re.match(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$", s):
            return False, "ایمیل معتبر نیست", None
        return True, s.lower(), None

    if kind == "mobile":
        mob = normalize_mobile(s)
        if not mob:
            return False, "شماره موبایل معتبر نیست (مثال: 09123456789)", None
        return True, mob, None

    if kind == "national_id":
        d = "".join(ch for ch in normalize_digits(s) if ch.isdigit())
        if len(d) != 10:
            return False, "کد ملی باید ۱۰ رقم باشد", None
        if not _valid_national_id(d):
            return False, "کد ملی نامعتبر است", None
        return True, d, None

    if kind == "postal":
        d = "".join(ch for ch in normalize_digits(s) if ch.isdigit())
        if len(d) != 10:
            return False, "کد پستی باید ۱۰ رقم باشد", None
        return True, d, None

    if kind == "card":
        d = "".join(ch for ch in normalize_digits(s) if ch.isdigit())
        if len(d) != 16:
            return False, "شماره کارت باید ۱۶ رقم باشد", None
        try:
            from payments import luhn_valid
            if not luhn_valid(d):
                return False, "شماره کارت نامعتبر است", None
        except ImportError:
            pass
        return True, d, None

    if kind == "sheba":
        raw2 = normalize_digits(s).upper().replace(" ", "").replace("-", "")
        if raw2.startswith("IR"):
            raw2 = raw2[2:]
        if len(raw2) != 24 or not raw2.isdigit():
            return False, "شبا باید ۲۴ رقم بعد از IR باشد", None
        return True, "IR" + raw2, None

    if kind == "date":
        from forms import validate_jdatetime
        ok, norm = validate_jdatetime(s)
        if not ok:
            return False, "تاریخ نامعتبر (مثال: 1370/05/12)", None
        return True, norm.split()[0], None

    if kind == "time":
        t = normalize_digits(s).replace(".", ":").strip()
        parts = t.split(":")
        if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
            return False, "ساعت نامعتبر (مثال: 18:30)", None
        hh, mm = int(parts[0]), int(parts[1])
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return False, "ساعت باید بین 00:00 تا 23:59 باشد", None
        return True, f"{hh:02d}:{mm:02d}", None

    if kind == "datetime":
        from forms import validate_jdatetime
        ok, norm = validate_jdatetime(s)
        if not ok:
            return False, "فرمت نامعتبر (مثال: 1404/06/15 18:30)", None
        return True, norm, None

    if kind == "plate":
        if len(s) < 6:
            return False, "پلاک نامعتبر", None
        return True, s[:30], None

    return True, s[:1000], None


def _valid_national_id(code):
    """اعتبارسنجی کد ملی ایران"""
    if len(code) != 10 or len(set(code)) == 1:
        return False
    try:
        s = sum(int(code[i]) * (10 - i) for i in range(9))
        r = s % 11
        c = int(code[9])
        return (r < 2 and c == r) or (r >= 2 and c == 11 - r)
    except (ValueError, IndexError):
        return False


# ==================== ذخیره پاسخ ====================
def save_answer(rid, f, value=None, options=None, file_id=None,
                file_type=None, file_name=None, number=None, correct=None):
    """ذخیره/به‌روزرسانی پاسخ یک فیلد"""
    old = db_execute("SELECT id FROM form_answers WHERE response_id=? AND field_id=?",
                     (rid, f["id"]), fetch="one")
    opts_json = json.dumps(options, ensure_ascii=False) if options is not None else None
    if old:
        db_execute("""UPDATE form_answers SET value_text=?, value_number=?,
            value_options=?, file_id=?, file_type=?, file_name=?, is_correct=?
            WHERE id=?""",
            (value, number, opts_json, file_id, file_type, file_name, correct, old["id"]))
        return old["id"]
    return db_execute("""INSERT INTO form_answers
        (response_id, form_id, field_id, field_type, value_text, value_number,
         value_options, file_id, file_type, file_name, is_correct)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (rid, f["form_id"], f["id"], f["field_type"], value, number,
         opts_json, file_id, file_type, file_name, correct))


def _after_answer(cid, uid, f):
    """
    بعد از ذخیره پاسخ چه اتفاقی بیفتد.

    ⚡ اصلاح مهم (بازخورد کاربر: «کار با فرم سخته»):
       قبلاً بعد از هر پاسخ به لیست سوالات برمی‌گشت و کاربر باید
       دستی سوال بعدی را پیدا و لمس می‌کرد → برای فرم ۱۰ سوالی
       ۲۰ لمس لازم بود.

       حالا مثل دیجی‌فرم خودکار می‌رود سوال بعدیِ بی‌پاسخ.
       دکمه «📋 همه سوالات» همیشه هست تا هر وقت خواست بپرد عقب.
    """
    st = get_state_data(uid)
    rid = st.get("rid")
    r = db_execute("SELECT * FROM form_responses WHERE id=?", (rid,), fetch="one")
    form = get_form(r["form_id"]) if r else None
    if not form:
        clear_state(uid)
        return send(cid, "⚠️ اطلاعات این مرحله دیگر در دسترس نیست؛ از فهرست فرم‌ها دوباره شروع کنید.")

    if (form.get("display_mode") or "one_by_one") == "one_by_one":
        update_state_data(uid, {"idx": int(st.get("idx") or 0) + 1})
        return ask_next(cid, uid)

    answers = _answer_map(rid)
    fields = [x for x in get_fields(form["id"]) if condition_met(x, answers)]

    # اولین سوال بی‌پاسخ بعد از سوال فعلی
    nxt, seen = None, False
    for x in fields:
        if x["id"] == f["id"]:
            seen = True
            continue
        if seen and answers.get(x["id"]) in (None, ""):
            nxt = x
            break
    # اگر بعدش چیزی نبود، از اول دنبال جامانده بگرد
    if nxt is None:
        for x in fields:
            if answers.get(x["id"]) in (None, ""):
                nxt = x
                break

    # همه پاسخ داده شد → صفحه مرور و ثبت
    if nxt is None:
        return show_question_list(cid, uid, rid)

    pos = next((i for i, x in enumerate(fields, 1) if x["id"] == nxt["id"]), None)
    update_state_data(uid, {"cur": nxt["id"], "multi": [], "files": [],
                            "prov": None, "items": []})
    return _render_question(cid, uid, nxt, pos, len(fields))


# ==================== ورودی متنی کاربر ====================
def handle_text(message):
    """پیام متنی در حالت پر کردن فرم"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    st = get_state_data(uid)
    rid = st.get("rid")
    field_id = st.get("cur")

    if not rid:
        clear_state(uid)
        return send(cid, "⚠️ اطلاعات این مرحله دیگر در دسترس نیست؛ از فهرست فرم‌ها دوباره شروع کنید.", kb_remove())

    r = db_execute("SELECT * FROM form_responses WHERE id=?", (rid,), fetch="one")
    form = get_form(r["form_id"]) if r else None
    if not form:
        clear_state(uid)
        return send(cid, "⚠️ فرم یافت نشد", kb_remove())

    one_by_one = (form.get("display_mode") or "one_by_one") == "one_by_one"

    if text in (BTN_BACK, "🔙 بازگشت"):
        if one_by_one:
            idx = max(0, int(st.get("idx") or 0) - 1)
            update_state_data(uid, {"idx": idx})
            send(cid, "⬅️ سوال قبل", kb_remove())
            return ask_next(cid, uid)
        send(cid, "📋 لیست سوالات", kb_remove())
        return show_question_list(cid, uid, rid)

    if not field_id:
        send(cid, "💡 یک سوال را انتخاب کنید", kb_remove())
        return show_question_list(cid, uid, rid)

    f = get_field(field_id)
    if not f:
        return show_question_list(cid, uid, rid)
    m = field_meta(f.get("field_type"))

    if text in (BTN_SKIP, "⏭️ رد کردن"):
        if f.get("is_required"):
            return send(cid, render("form_txt_required"))
        save_answer(rid, f, value="")
        send(cid, "⏭️ رد شد", kb_remove())
        return _after_answer(cid, uid, f)

    kind = m.get("kind")

    # ✅ تأیید شماره: دو مرحله (شماره → کد)
    if kind == "verify_mobile":
        if st.get("verify_wait"):
            return handle_verify_code(cid, uid, f, text)
        mode = (form.get("phone_verify_mode") or "both").strip().lower()
        if mode == "contact":
            # ادمین فقط دکمه اشتراک شماره را مجاز کرده
            return send(cid, "📱 لطفاً روی دکمه «ارسال شماره‌ام» بزنید.")
        mob = normalize_mobile(text)
        if not mob:
            return send(cid, render("form_txt_invalid",
                                    hint="شماره موبایل معتبر نیست (مثال: 09123456789)"))
        return start_mobile_verify(cid, uid, f, mob)

    if kind in MEDIA_KINDS:
        return send(cid, f"⚠️ برای این سوال باید {_media_name(kind)} ارسال کنید.")
    if kind in BUTTON_KINDS:
        return send(cid, "⚠️ لطفاً از دکمه‌های بالا یکی را انتخاب کنید.")

    ok, val, num = validate(f, m, text)
    if not ok:
        return send(cid, render("form_txt_invalid", hint=val))

    save_answer(rid, f, value=val, number=num)
    if m.get("cache"):
        cache_answer(uid, m["cache"], val)
    send(cid, "✅ ثبت شد", kb_remove())
    return _after_answer(cid, uid, f)


def _media_name(kind):
    return {"photo": "عکس", "file": "فایل", "video": "ویدیو",
            "voice": "پیام صوتی", "location": "موقعیت مکانی"}.get(kind, "فایل")


def handle_media(message):
    """عکس/فایل/ویدیو/صوت در حالت پر کردن فرم"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    st = get_state_data(uid)
    rid = st.get("rid")
    field_id = st.get("cur")
    if not (rid and field_id):
        return send(cid, "💡 ابتدا یک سوال انتخاب کنید", kb_remove())

    f = get_field(field_id)
    if not f:
        return show_question_list(cid, uid, rid)
    m = field_meta(f.get("field_type"))
    kind = m.get("kind")

    file_id = file_type = file_name = None
    if "photo" in message and message["photo"]:
        file_id, file_type = message["photo"][-1].get("file_id"), "photo"
    elif "document" in message:
        d = message["document"]
        file_id, file_type = d.get("file_id"), "document"
        file_name = d.get("file_name")
    elif "video" in message:
        file_id, file_type = message["video"].get("file_id"), "video"
    elif "voice" in message:
        file_id, file_type = message["voice"].get("file_id"), "voice"
    elif "audio" in message:
        file_id, file_type = message["audio"].get("file_id"), "audio"

    if not file_id:
        return send(cid, "⚠️ فایل شناسایی نشد")

    expect = {"photo": ("photo",), "file": ("document", "photo", "video", "audio"),
              "video": ("video",), "voice": ("voice", "audio")}
    allowed = expect.get(kind)
    if allowed and file_type not in allowed:
        return send(cid, f"⚠️ برای این سوال باید {_media_name(kind)} بفرستید.")

    maxf = int(f.get("max_files") or 1)
    if maxf > 1:
        files = list(st.get("files") or [])
        files.append({"file_id": file_id, "file_type": file_type,
                      "file_name": file_name})
        update_state_data(uid, {"files": files})
        if len(files) < maxf:
            return send(cid, (
                f"📎 دریافت شد ({len(files)}/{maxf})\n\n"
                f"فایل بعدی را بفرستید یا «تأیید» بزنید."
            ), {"inline_keyboard": [
                [{"text": "✅ تأیید و ادامه", "callback_data": f"fffok_{f['id']}"}]]})
        save_answer(rid, f, value=f"{len(files)} فایل", options=files,
                    file_id=files[0]["file_id"], file_type=files[0]["file_type"])
        update_state_data(uid, {"files": []})
        send(cid, f"✅ {len(files)} فایل ثبت شد", kb_remove())
        return _after_answer(cid, uid, f)

    save_answer(rid, f, value=f"📎 {_media_name(kind)}", file_id=file_id,
                file_type=file_type, file_name=file_name)
    send(cid, "✅ دریافت شد", kb_remove())
    return _after_answer(cid, uid, f)


def confirm_files(cid, uid, field_id):
    """پایان ارسال چند فایل"""
    st = get_state_data(uid)
    rid = st.get("rid")
    f = get_field(field_id)
    if not (rid and f):
        return send(cid, "⚠️ نامعتبر")
    files = list(st.get("files") or [])
    if not files:
        if f.get("is_required"):
            return send(cid, render("form_txt_required"))
        save_answer(rid, f, value="")
    else:
        save_answer(rid, f, value=f"{len(files)} فایل", options=files,
                    file_id=files[0]["file_id"], file_type=files[0]["file_type"])
    update_state_data(uid, {"files": []})
    send(cid, "✅ ثبت شد")
    return _after_answer(cid, uid, f)


def handle_location(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    st = get_state_data(uid)
    rid, field_id = st.get("rid"), st.get("cur")
    if not (rid and field_id):
        return send(cid, "💡 ابتدا یک سوال انتخاب کنید", kb_remove())
    f = get_field(field_id)
    if not f:
        return show_question_list(cid, uid, rid)
    loc = message.get("location") or {}
    lat, lon = loc.get("latitude"), loc.get("longitude")
    if lat is None or lon is None:
        return send(cid, "⚠️ موقعیت نامعتبر")
    save_answer(rid, f, value=f"{lat},{lon}")
    send(cid, "📍 موقعیت ثبت شد", kb_remove())
    return _after_answer(cid, uid, f)


def handle_contact(message):
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    st = get_state_data(uid)
    rid, field_id = st.get("rid"), st.get("cur")
    if not (rid and field_id):
        return False
    f = get_field(field_id)
    if not f:
        return False
    m = field_meta(f.get("field_type"))
    kind = m.get("kind")
    if kind not in ("mobile", "verify_mobile"):
        return False
    c = message.get("contact") or {}
    mob = normalize_mobile(c.get("phone_number") or "")
    if not mob:
        send(cid, "⚠️ شماره نامعتبر")
        return True

    # شماره‌ای که خود بله می‌دهد قابل اعتماد است → نیازی به کد نیست
    save_answer(rid, f, value=mob)
    cache_answer(uid, "mobile", mob)
    update_state_data(uid, {"verify_wait": 0, "verify_mobile": None})
    send(cid, f"✅ {mob}" + ("  (تأییدشده)" if kind == "verify_mobile" else ""),
         kb_remove())
    _after_answer(cid, uid, f)
    return True


# ==================== پاسخ‌های دکمه‌ای ====================
def pick_option(cid, uid, field_id, index):
    f = get_field(field_id)
    st = get_state_data(uid)
    rid = st.get("rid")
    if not (f and rid):
        return send(cid, "⚠️ نامعتبر")
    opts = parse_options(f)
    i = int(index)
    if not (1 <= i <= len(opts)):
        return send(cid, "⚠️ گزینه نامعتبر")

    m = field_meta(f.get("field_type"))
    correct = None
    if m.get("kind") == "quiz" and f.get("correct_option"):
        correct = 1 if str(f["correct_option"]) == str(i) else 0
    save_answer(rid, f, value=opts[i - 1], correct=correct)
    if m.get("cache"):
        cache_answer(uid, m["cache"], opts[i - 1])
    return _after_answer(cid, uid, f)


def pick_item(cid, uid, field_id, index):
    """🎓 انتخاب آیتم قیمت‌دار (کلاس/دوره/همایش/کالا)"""
    f = get_field(field_id)
    st = get_state_data(uid)
    rid = st.get("rid")
    if not (f and rid):
        return send(cid, "⚠️ نامعتبر")
    items = parse_items(f)
    i = int(index)
    if not (1 <= i <= len(items)):
        return send(cid, "⚠️ گزینه نامعتبر")
    it = items[i - 1]
    if item_is_full(it):
        return send(cid, f"🚫 ظرفیت «{it['title']}» تکمیل شده.\n\nمورد دیگری انتخاب کنید.")

    p = int(it.get("price") or 0)
    save_answer(rid, f, value=it["title"], number=float(p))
    send(cid, f"✅ {it['title']}\n"
              + (f"💰 {fmt_amount(p)} {CURRENCY_LABEL}" if p else "🎁 رایگان"))
    return _after_answer(cid, uid, f)


def toggle_item(cid, uid, field_id, index):
    """
    ☑️ انتخاب/لغو یک مورد هزینه‌دار (چندانتخابی).

    🎯 درخواست کاربر: «توی ثبت‌نام و انتخاب موردهای هزینه‌دار،
       امکان انتخاب چند گزینه باشه — مثلا من مورد ۱ و مورد ۲ رو
       انتخاب کنم و بعد تایید کنم برم برای پرداخت»
    """
    field_id = _rid_ok(field_id)
    f = get_field(field_id) if field_id else None
    st = get_state_data(uid)
    rid = st.get("rid")
    if not (f and rid):
        return send(cid, "⚠️ نامعتبر")
    items = parse_items(f)
    try:
        i = int(index)
    except (TypeError, ValueError):
        return send(cid, "⚠️ نامعتبر")
    if not (1 <= i <= len(items)):
        return send(cid, "⚠️ گزینه نامعتبر")

    sel = list(st.get("items") or [])
    it = items[i - 1]
    if i in sel:
        sel.remove(i)
    else:
        if item_is_full(it):
            return send(cid, f"🚫 ظرفیت «{it['title']}» تکمیل شده 🌱")
        cap = int(f.get("max_items") or 0)
        if cap and len(sel) >= cap:
            return send(cid, f"⚠️ حداکثر {cap} مورد می‌توانید انتخاب کنید.\n\n"
                             f"💡 اول یکی را بردارید.")
        sel.append(i)
    update_state_data(uid, {"items": sel, "cur": field_id})

    rd = db_execute("SELECT form_id FROM form_responses WHERE id=?",
                    (rid,), fetch="one")
    form = get_form(rd["form_id"]) if rd else None
    m = field_meta(f.get("field_type"))
    pos_total = None
    return _render_question(cid, uid, f, None, pos_total)


def confirm_items(cid, uid, field_id):
    """✅ تأیید موردهای انتخاب‌شده و رفتن به سوال بعد"""
    field_id = _rid_ok(field_id)
    f = get_field(field_id) if field_id else None
    st = get_state_data(uid)
    rid = st.get("rid")
    if not (f and rid):
        return send(cid, "⚠️ نامعتبر")
    items = parse_items(f)
    sel = sorted(set(st.get("items") or []))
    chosen = [items[i - 1] for i in sel if 1 <= i <= len(items)]

    if not chosen and f.get("is_required"):
        return send(cid, "⚠️ حداقل یک مورد انتخاب کنید 🌱")

    titles = [c["title"] for c in chosen]
    total = sum(int(c.get("price") or 0) for c in chosen)
    save_answer(rid, f, value="، ".join(titles), options=titles,
                number=float(total))
    update_state_data(uid, {"items": []})

    if chosen:
        lines = [f"✅ {len(chosen)} مورد انتخاب شد:"]
        for c in chosen:
            p = int(c.get("price") or 0)
            lines.append(f"   • {c['title']}"
                         + (f" — {fmt_amount(p)} {CURRENCY_LABEL}"
                            if p else " — رایگان"))
        if total:
            lines.append(f"\n💰 جمع: {fmt_amount(total)} {CURRENCY_LABEL}")
        send(cid, "\n".join(lines))
    return _after_answer(cid, uid, f)


# ==================== ✅ تأیید شماره موبایل ====================
def _send_verify_code(cid, uid, mobile):
    """ارسال کد تأیید با سرویس سفیر"""
    from auth import generate_otp, save_otp, send_otp_via_safir
    code = generate_otp()
    save_otp(uid, mobile, code)
    ok, err = send_otp_via_safir(mobile, code)
    if not ok:
        log(f"⚠️ ارسال کد تأیید فرم: {err}")
    return ok, err


def start_mobile_verify(cid, uid, f, mobile):
    """مرحله ۱: شماره گرفته شد → کد بفرست"""
    st = get_state_data(uid)
    ok, err = _send_verify_code(cid, uid, mobile)
    update_state_data(uid, {"verify_mobile": mobile, "verify_wait": 1})
    if ok:
        return send(cid, (
            f"📲 کد تأیید به {mobile} ارسال شد\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"کد ۶ رقمی را وارد کنید:"
        ), {"keyboard": [[{"text": "🔄 ارسال مجدد"}],
                         [{"text": BTN_BACK}, {"text": "🏠 منوی اصلی"}]],
            "resize_keyboard": True})
    # اگر سرویس پیامک کار نکرد، کاربر را گیر نینداز
    update_state_data(uid, {"verify_wait": 0})
    save_answer(st.get("rid"), f, value=mobile)
    cache_answer(uid, "mobile", mobile)
    send(cid, f"✅ {mobile} ثبت شد\n\n⚠️ ارسال کد ممکن نشد؛ شماره بدون تأیید ثبت شد.")
    return _after_answer(cid, uid, f)


def handle_verify_code(cid, uid, f, text):
    """مرحله ۲: بررسی کد"""
    from auth import verify_otp
    st = get_state_data(uid)
    mobile = st.get("verify_mobile")
    rid = st.get("rid")

    if text in ("🔄 ارسال مجدد", "ارسال مجدد"):
        _send_verify_code(cid, uid, mobile)
        return send(cid, f"📲 کد مجدداً به {mobile} ارسال شد")

    code = normalize_digits(text).strip()
    if not code.isdigit():
        return send(cid, "⚠️ فقط کد عددی را بفرستید:")

    ok, msg = verify_otp(uid, code)
    if not ok:
        return send(cid, f"❌ {msg}\n\nدوباره وارد کنید:")

    update_state_data(uid, {"verify_wait": 0, "verify_mobile": None})
    save_answer(rid, f, value=mobile)
    cache_answer(uid, "mobile", mobile)
    send(cid, f"✅ شماره {mobile} تأیید شد", kb_remove())
    return _after_answer(cid, uid, f)


def toggle_multi(cid, uid, field_id, index):
    """انتخاب/لغو گزینه در چند انتخابی"""
    f = get_field(field_id)
    st = get_state_data(uid)
    if not (f and st.get("rid")):
        return send(cid, "⚠️ نامعتبر")
    opts = parse_options(f)
    i = int(index)
    if not (1 <= i <= len(opts)):
        return send(cid, "⚠️ نامعتبر")

    sel = list(st.get("multi") or [])
    if i in sel:
        sel.remove(i)
    else:
        sel.append(i)
    update_state_data(uid, {"multi": sel, "cur": field_id})

    m = field_meta(f.get("field_type"))
    star = " *" if f.get("is_required") else ""
    lines = [f"{m['icon']} {field_label(f)}{star}"]
    if f.get("description"):
        lines.append(f"\n📄 {f['description']}")
    lines.append(f"\n☑️ انتخاب‌شده: {len(sel)}")

    btns = []
    for j, o in enumerate(opts, 1):
        mark = "☑️" if j in sel else "⬜"
        btns.append([{"text": f"{mark} {o[:56]}", "callback_data": f"ffm_{j}_{field_id}"}])
    btns.append([{"text": f"✅ تأیید و ادامه ({len(sel)})",
                  "callback_data": f"ffmok_{field_id}"}])
    if not f.get("is_required"):
        btns.append([{"text": "⏭️ رد کردن", "callback_data": f"ffskip_{field_id}"}])
    rd = db_execute("SELECT form_id FROM form_responses WHERE id=?",
                    (st["rid"],), fetch="one")
    form = get_form(rd["form_id"]) if rd else None
    if form and (form.get("display_mode") or "one_by_one") != "one_by_one":
        btns.append([{"text": "🔙 لیست سوالات", "callback_data": "fflist"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def confirm_multi(cid, uid, field_id):
    f = get_field(field_id)
    st = get_state_data(uid)
    rid = st.get("rid")
    if not (f and rid):
        return send(cid, "⚠️ نامعتبر")
    sel = list(st.get("multi") or [])
    opts = parse_options(f)
    if not sel and f.get("is_required"):
        return send(cid, render("form_txt_required"))
    chosen = [opts[i - 1] for i in sorted(sel) if 1 <= i <= len(opts)]
    save_answer(rid, f, value="، ".join(chosen), options=chosen)
    update_state_data(uid, {"multi": []})
    return _after_answer(cid, uid, f)


def pick_rating(cid, uid, field_id, value):
    f = get_field(field_id)
    st = get_state_data(uid)
    rid = st.get("rid")
    if not (f and rid):
        return send(cid, "⚠️ نامعتبر")
    m = field_meta(f.get("field_type"))
    v = int(value)
    scale = int(m.get("scale") or 5)
    v = max(1, min(scale, v))
    emoji = m.get("emoji") or "⭐"
    save_answer(rid, f, value=f"{v}", number=float(v))
    send(cid, f"{emoji * min(v, 10)} امتیاز {v} ثبت شد")
    return _after_answer(cid, uid, f)


def pick_confirm(cid, uid, field_id, yes):
    f = get_field(field_id)
    st = get_state_data(uid)
    rid = st.get("rid")
    if not (f and rid):
        return send(cid, "⚠️ نامعتبر")
    if not yes and f.get("is_required"):
        return send(cid, "⚠️ برای ادامه باید قوانین را بپذیرید.")
    save_answer(rid, f, value="پذیرفتم" if yes else "نپذیرفتم")
    return _after_answer(cid, uid, f)


def pick_education(cid, uid, field_id, index):
    f = get_field(field_id)
    st = get_state_data(uid)
    rid = st.get("rid")
    if not (f and rid):
        return send(cid, "⚠️ نامعتبر")
    i = int(index)
    lv = iran_data.EDUCATION_LEVELS
    if not (1 <= i <= len(lv)):
        return send(cid, "⚠️ نامعتبر")
    save_answer(rid, f, value=lv[i - 1])
    cache_answer(uid, "edu", lv[i - 1])
    return _after_answer(cid, uid, f)


def pick_province(cid, uid, field_id, index):
    """مرحله ۱ فیلد استان و شهر"""
    f = get_field(field_id)
    st = get_state_data(uid)
    if not (f and st.get("rid")):
        return send(cid, "⚠️ نامعتبر")
    i = int(index)
    plist = iran_data.PROVINCE_LIST
    if not (1 <= i <= len(plist)):
        return send(cid, "⚠️ نامعتبر")
    prov = plist[i - 1]
    update_state_data(uid, {"prov": prov, "cur": field_id})

    cities = iran_data.cities_of(prov)
    btns, row = [], []
    for j, c in enumerate(cities, 1):
        row.append({"text": c[:18], "callback_data": f"ffcy_{j}_{field_id}"})
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([{"text": "🏙️ سایر شهرها (تایپ می‌کنم)",
                  "callback_data": f"ffcyo_{field_id}"}])
    btns.append([{"text": "🔙 تغییر استان", "callback_data": f"ffq_{field_id}"}])
    return send_or_edit(cid, (
        f"📍 استان: {prov}\n━━━━━━━━━━━━━━\n\n"
        f"🏙️ شهر خود را انتخاب کنید:"
    ), {"inline_keyboard": btns})


def pick_city(cid, uid, field_id, index):
    # 🛡️ فاز ۴۰: ورودی خراب («ffcy_xyz» بدون شناسه) باعث
    #    int(None) می‌شد.
    try:
        i = int(index)
    except (TypeError, ValueError):
        return send(cid, "⚠️ انتخاب نامعتبر — دوباره تلاش کنید")
    f = get_field(field_id)
    st = get_state_data(uid)
    rid = st.get("rid")
    prov = st.get("prov")
    if not (f and rid and prov):
        return send(cid, "⚠️ ابتدا استان را انتخاب کنید")
    cities = iran_data.cities_of(prov)
    if not (1 <= i <= len(cities)):
        return send(cid, "⚠️ نامعتبر")
    val = f"{prov} - {cities[i-1]}"
    save_answer(rid, f, value=val)
    cache_answer(uid, "city", val)
    update_state_data(uid, {"prov": None})
    return _after_answer(cid, uid, f)


def other_city(cid, uid, field_id):
    """کاربر شهر را تایپ می‌کند"""
    st = get_state_data(uid)
    prov = st.get("prov") or ""
    update_state_data(uid, {"cur": field_id, "await_city": 1})
    return send(cid, (
        f"🏙️ نام شهر خود را در استان «{prov}» بنویسید:"
    ), kb_cancel())


def skip_field(cid, uid, field_id):
    f = get_field(field_id)
    st = get_state_data(uid)
    rid = st.get("rid")
    if not (f and rid):
        return send(cid, "⚠️ نامعتبر")
    if f.get("is_required"):
        return send(cid, render("form_txt_required"))
    save_answer(rid, f, value="")
    return _after_answer(cid, uid, f)


# ==================== ثبت نهایی ====================
def submit_form(cid, uid, rid):
    r = db_execute("SELECT * FROM form_responses WHERE id=?", (int(rid),), fetch="one")
    if not r or r.get("bale_user_id") != uid:
        return send(cid, "❌ یافت نشد")
    if r.get("status") in ("completed", "confirmed"):
        return send(cid, render("form_txt_duplicate",
                                tracking=r.get("tracking_code") or "—"))

    form = get_form(r["form_id"])
    if not form:
        return send(cid, "❌ فرم یافت نشد")

    ok, reason, extra = form_gate(form)
    if not ok and reason in ("expired", "full"):
        return _closed_message(cid, form, reason, extra)

    answers = _answer_map(rid)
    fields = [f for f in get_fields(form["id"]) if condition_met(f, answers)]
    missing = [f for f in fields
               if f.get("is_required") and answers.get(f["id"]) in (None, "")]

    if missing:
        lines = ["⚠️ سوالات اجباری ناقص", "━━━━━━━━━━━━━━", "",
                 f"❌ {len(missing)} سوال اجباری بی‌پاسخ است:", ""]
        btns = []
        for f in missing[:8]:
            m = field_meta(f.get("field_type"))
            lines.append(f"• {field_label(f)[:44]}")
            btns.append([{"text": f"✍️ {field_label(f)[:30]}",
                          "callback_data": f"ffq_{f['id']}"}])
        btns.append([{"text": "🔙 لیست سوالات", "callback_data": "fflist"}])
        return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})

    # نمره‌دهی آزمون
    score = max_score = 0
    for f in fields:
        if field_meta(f.get("field_type")).get("kind") == "quiz":
            max_score += int(f.get("score") or 0)
    if max_score:
        rows = db_execute("SELECT field_id, is_correct FROM form_answers "
                          "WHERE response_id=?", (rid,), fetch="all") or []
        cmap = {x["field_id"]: x.get("is_correct") for x in rows}
        for f in fields:
            if field_meta(f.get("field_type")).get("kind") == "quiz":
                if cmap.get(f["id"]) == 1:
                    score += int(f.get("score") or 0)

    # 💰 مبلغ نهایی = هزینه ثابت فرم + آیتم‌های انتخاب‌شده
    price = form_total_price(form["id"], rid)
    method = form.get("payment_method") or "none"
    if price > 0 and method == "none":
        # فرم روش پرداخت ندارد ولی آیتم قیمت‌دار دارد → کارت‌به‌کارت پیش‌فرض
        method = "card"

    if method != "none" and price > 0:
        # 🧾 فاز ۲۳ — یک صورتحساب شیک، نه چند پیام پشت هم
        db_execute("""UPDATE form_responses SET status='pending_payment', score=?,
            max_score=?, amount=?, payment_status='pending' WHERE id=?""",
            (score, max_score, price, rid))
        clear_state(uid)
        return show_invoice(cid, uid, rid, price)

    return finalize(cid, uid, rid, score, max_score)


def finalize(cid, uid, rid, score=None, max_score=None):
    """تکمیل نهایی پاسخ — صدور کد پیگیری، بلیت، اعلان"""
    r = db_execute("SELECT * FROM form_responses WHERE id=?", (int(rid),), fetch="one")
    if not r:
        return send(cid, "❌ یافت نشد")
    if r.get("status") in {"completed", "pending_review"}:
        return r
    form = get_form(r["form_id"])
    if not form:
        return send(cid, "❌ فرم یافت نشد")

    tracking = r.get("tracking_code") or gen_tracking()
    qr = r.get("qr_code") or gen_qr_code()
    if score is None:
        score = r.get("score") or 0
    if max_score is None:
        max_score = r.get("max_score") or 0

    # 👤 فرم تأییدی ادمین → منتظر تأیید بماند
    needs_ok = bool(form.get("needs_approval"))
    new_status = "pending_review" if needs_ok else "completed"

    db_execute("""UPDATE form_responses SET status=?, tracking_code=?,
        qr_code=?, score=?, max_score=?, completed_at=CURRENT_TIMESTAMP WHERE id=?""",
        (new_status, tracking, qr, score, max_score, rid))
    recount_responses(form["id"])
    clear_state(uid)
    log_action(uid, "form_submit", {"fid": form["id"], "rid": rid})

    # 🏅 بررسی امتیاز شرطی
    try:
        import occasions as _oc
        _oc.check_point_rules(uid, "form_submit")
    except Exception as _e:
        log(f"⚠️ امتیاز شرطی: {_e}")

    try:
        import club as _cl
        _cl.check_achievements(uid, "form_submit")
    except Exception as _e:
        log(f"⚠️ دستاورد: {_e}")

    # 📊 فاز ۳۳ — اگر این فرم نظرسنجی یک رویداد بود، ثبت کن
    #    (امتیاز تکمیل هم همان‌جا داده می‌شود)
    try:
        import survey as _sv
        _sv.on_form_submit(form["id"], uid, rid)
    except Exception as _e:
        log(f"⚠️ ثبت نظرسنجی: {_e}")


    # 👤 پروفایل را از همین حالا پر کن (اگر تأییدی نیست)
    if not needs_ok and form.get("fill_profile", 1):
        try:
            from forms import sync_profile_from_response
            sync_profile_from_response(rid)
        except Exception as e:
            log(f"⚠️ پرکردن پروفایل: {e}")

    u = get_user(uid) or {}
    name = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip() or "کاربر"
    end_text = form.get("end_text") or get_setting("form_txt_end_default", "💚 سپاس از شما")

    txt = render("form_txt_saved", title=form["title"], end_text=end_text,
                 tracking=tracking, date=jnow(), name=name)

    # 💯 فاز ۱۸-الف — نمایش نمره فقط اگر ادمین اجازه داده باشد
    ftype = form.get("form_type") or "questionnaire"
    if max_score and form.get("show_score", 1):
        pct = int(score * 100 / max_score) if max_score else 0
        txt += f"\n\n🎯 نمره شما: {score} از {max_score} ({pct}%)"

        # 🎯 حد نصاب قبولی
        need = int(form.get("pass_score") or 0)
        if need > 0:
            if score >= need:
                txt += (f"\n🎉 تبریک! قبول شدید "
                        f"(حد نصاب: {need})")
            else:
                txt += (f"\n💪 حد نصاب قبولی {need} بود — "
                        f"دفعه بعد حتماً موفق می‌شوید 💚")

    # 🏅 فاز ۱۸-الف — رتبه در مسابقه
    if ftype == "contest" and form.get("leaderboard_enabled", 1) and max_score:
        try:
            rank = db_scalar(
                "SELECT COUNT(*)+1 FROM form_responses WHERE form_id=? "
                "AND status IN ('completed','confirmed') AND score>?",
                (form["id"], score)) or 1
            total_n = db_scalar(
                "SELECT COUNT(*) FROM form_responses WHERE form_id=? "
                "AND status IN ('completed','confirmed')",
                (form["id"],)) or 1
            txt += f"\n🏅 رتبه فعلی شما: {rank} از {total_n}"
        except Exception as e:
            log(f"⚠️ محاسبه رتبه: {e}")

    if needs_ok:
        txt += ("\n\n⏳ پاسخ شما در انتظار تأیید ادمین است.\n"
                "پس از بررسی به شما اطلاع داده می‌شود.")

    btns = []
    if form.get("ticket_enabled") and not needs_ok:
        btns.append([{"text": "🎫 دریافت بلیت", "callback_data": f"fftk_{rid}"}])
    # 🆕 فاز ۱۵ — گواهینامه و آیدی کارت برای فرم
    if form.get("cert_enabled") and not needs_ok:
        btns.append([{"text": "🎓 دریافت گواهینامه",
                      "callback_data": f"ffcert_{rid}"}])
    if form.get("idcard_enabled") and not needs_ok:
        btns.append([{"text": "🆔 دریافت کارت",
                      "callback_data": f"ffcard_{rid}"}])
    if form.get("contact_enabled"):
        btns.append([{"text": "💬 پیام به برگزارکننده",
                      "callback_data": f"ffmsg_{rid}"}])
    btns.append([{"text": "📄 مشاهده پاسخ‌های من", "callback_data": f"ffmy_{rid}"}])
    btns.append([{"text": "🏠 منوی اصلی", "callback_data": "back_main"}])
    send(cid, txt, {"inline_keyboard": btns})

    # بلیت فقط بعد از تأیید صادر می‌شود
    if form.get("ticket_enabled") and not needs_ok:
        send_ticket(cid, uid, rid)

    if form.get("notify_admins"):
        _notify_new_response(form, r, name, tracking)

    # 🔗 فاز ۱۷ — وبهوک
    _fire_webhook(form, r, "completed", {"name": name,
                                         "tracking": tracking,
                                         "score": score})

    # ═══════════════════════════════════════════════════
    # 🔗 فاز ۱۶ — اگر این فرم به رویدادی وصل است،
    #    بعد از تکمیل، ثبت‌نام رویداد را ادامه بده
    # ═══════════════════════════════════════════════════
    if form.get("event_id") and not needs_ok:
        try:
            import events as _ev
            ev = _ev.get_event(form["event_id"])
            if ev and ev.get("status") in ("published", "closed"):
                already = db_execute(
                    "SELECT status FROM event_registrations "
                    "WHERE event_id=? AND bale_user_id=?",
                    (ev["id"], uid), fetch="one")
                if not already or already.get("status") == "cancelled":
                    send(cid, (
                        "✅ فرم شما ثبت شد\n"
                        "━━━━━━━━━━━━━━\n\n"
                        "⏳ در حال تکمیل ثبت‌نام رویداد..."))
                    _ev.register(cid, uid, ev["id"])
        except Exception as e:
            log(f"⚠️ ادامه ثبت‌نام رویداد: {e}")

    return True


def _fire_webhook(form, r, event, extra=None):
    """
    🔗 فاز ۱۷ — ارسال رویداد به وبهوک خارجی.

    غیرمسدودکننده: با صف پس‌زمینه می‌رود تا ربات یخ نزند.
    اگر آدرس تنظیم نشده باشد، هیچ کاری نمی‌کند.
    """
    url = (form or {}).get("webhook_url") or ""
    if not url or not url.startswith("https://"):
        return False
    evs = (form.get("webhook_events") or "completed,paid").split(",")
    if event not in [e.strip() for e in evs]:
        return False

    payload = {
        "event": event,
        "form_id": form.get("id"),
        "form_title": form.get("title"),
        "response_id": (r or {}).get("id"),
        "tracking_code": (r or {}).get("tracking_code"),
        "bale_user_id": (r or {}).get("bale_user_id"),
        "amount": (r or {}).get("amount") or 0,
        "at": jnow(),
    }
    payload.update(extra or {})

    def _send_hook():
        try:
            import requests
            requests.post(url, json=payload, timeout=8)
            log(f"🔗 وبهوک {event} → {url[:40]}")
        except Exception as e:
            log(f"⚠️ وبهوک ناموفق: {e}")

    try:
        import threading
        threading.Thread(target=_send_hook, daemon=True).start()
    except Exception as e:
        log(f"⚠️ اجرای وبهوک: {e}")
    return True


def _notify_new_response(form, r, name, tracking):
    """اعلان پاسخ جدید به ادمین‌ها"""
    txt = render("form_txt_admin_new", title=form["title"],
                 name=name, tracking=tracking, date=jnow())
    targets = set()
    if form.get("owner_id"):
        targets.add(form["owner_id"])
    for a in db_execute("SELECT bale_user_id FROM form_admins WHERE form_id=?",
                        (form["id"],), fetch="all") or []:
        if a.get("bale_user_id"):
            targets.add(a["bale_user_id"])
    kb = {"inline_keyboard": [
        [{"text": "📄 مشاهده پاسخ", "callback_data": f"fbrv_{r['id']}"}]]}
    for t in targets:
        try:
            send(t, txt, kb)
        except Exception as e:
            log(f"⚠️ اعلان پاسخ: {e}")


def build_invoice(rid, total=None):
    """
    🧾 صورتحساب شیک — یک پیام، همه چیز شفاف.

    🎯 درخواست کاربر (فاز ۲۳):
       «وقتی فرم رو ثبت میکنم و میرم واسه پرداخت هزارتا پیام نیاد.
        یه پیام صورت حساب خوشگل و شیک بیاد که گزینه‌ها شفاف توش
        بیاد فقط، و اگه کاربر تایید کرد مدل پرداخت براش باز بشه»

    خروجی: (متن, مبلغ کل)
    """
    r = db_execute("SELECT * FROM form_responses WHERE id=?",
                   (int(rid),), fetch="one")
    if not r:
        return "", 0
    form = get_form(r["form_id"])
    if not form:
        return "", 0
    if total is None:
        total = form_total_price(form["id"], rid)

    title = get_setting("form_txt_invoice_title", "🧾 صورتحساب شما")
    lines = [title, "━━━━━━━━━━━━━━", "", f"📋 {form['title']}", ""]

    rows = []
    base = int(form.get("price") or 0)
    if base and (form.get("payment_method") or "none") != "none":
        _nm = "هزینه ثبت‌نام"
        try:
            import infra_fee as _inf
            _il = _inf.invoice_line(base, for_form=True)
            if _il:
                _nm = _il
        except Exception as _e:
            log(f"⚠️ زیرساخت صورتحساب: {_e}")
        rows.append((_nm, base))

    for a in db_execute("""SELECT field_id, value_text, value_options
        FROM form_answers WHERE response_id=?""",
        (rid,), fetch="all") or []:
        fl = get_field(a.get("field_id"))
        if not fl or field_meta(fl.get("field_type")).get("kind") != "item":
            continue
        for it in chosen_items(fl, a):
            rows.append((it["title"], int(it.get("price") or 0)))

    if rows:
        lines.append("📦 موارد انتخابی شما:")
        lines.append("")
        for i, (name, price) in enumerate(rows, 1):
            p = (f"{fmt_amount(price)} {CURRENCY_LABEL}" if price
                 else "رایگان 🎁")
            lines.append(f"   {i}. {name}")
            lines.append(f"      └ {p}")
        lines.append("")

    lines += ["━━━━━━━━━━━━━━",
              f"💰 مبلغ قابل پرداخت:",
              f"     {fmt_amount(total)} {CURRENCY_LABEL}"]

    note = (form.get("payment_note") or "").strip()
    if note:
        lines += ["", f"📝 {note}"]

    # 🧱 توضیح هزینه زیرساخت
    try:
        import infra_fee as _inf
        if _inf.is_infra(total, for_form=True) and _inf.note():
            lines += ["", f"💡 {_inf.note()}"]
    except Exception:
        pass

    # 🛡️ هشدار کوتاه فیلترشکن — فقط یک خط، نه یک پیام جدا
    try:
        import payments as _pay
        method = form.get("payment_method") or "none"
        if method in ("multi", "none"):
            method = "bale_wallet"
        if _pay.vpn_warn_needed(method):
            short = (get_setting("pay_txt_vpn_short", "") or "").strip()
            if not short:
                short = ("🛡️ لطفاً قبل از پرداخت، فیلترشکن (VPN) را "
                         "خاموش کنید.")
            lines += ["", short]
    except Exception as e:
        log(f"⚠️ هشدار VPN صورتحساب: {e}")

    foot = get_setting("form_txt_invoice_foot",
                       "اگر تأیید کنید، روش پرداخت را انتخاب می‌کنید 💚")
    if foot:
        lines += ["", foot]
    return "\n".join(lines), total


def _rid_ok(v):
    """🛡️ شناسه امن — ورودی خراب کرش نکند"""
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def show_invoice(cid, uid, rid, total=None):
    """
    🧾 نمایش صورتحساب با دکمه تأیید.

    🔴 قبلاً سه پیام پشت هم می‌آمد:
         ۱) «🧾 صورتحساب...»
         ۲) «💳 تکمیل این فرم نیازمند پرداخت است...»
         ۳) پیام خود روش پرداخت
       حالا فقط یکی — و روش پرداخت وقتی باز می‌شود که کاربر
       تأیید کند.
    """
    rid = _rid_ok(rid)
    if not rid:
        return send(cid, "❌ درخواست نامعتبر")
    txt, total = build_invoice(rid, total)
    if not txt:
        return send(cid, "❌ اطلاعات پرداخت یافت نشد")
    return send_or_edit(cid, txt, {"inline_keyboard": [
        [{"text": f"💳 تأیید و پرداخت ({fmt_amount(total)} "
                  f"{CURRENCY_LABEL})"[:60],
          "callback_data": f"ffpay_{rid}"}],
        [{"text": "◀️ بازگشت و ویرایش پاسخ‌ها",
          "callback_data": f"ffback_{rid}"}],
        [{"text": "❌ انصراف", "callback_data": f"ffcancel_{rid}"}],
    ]})


def go_pay(cid, uid, rid):
    """💳 کاربر صورتحساب را تأیید کرد → روش پرداخت باز شود"""
    rid = _rid_ok(rid)
    if not rid:
        return send(cid, "❌ درخواست نامعتبر")
    r = db_execute("SELECT * FROM form_responses WHERE id=?",
                   (int(rid),), fetch="one")
    if not r or r.get("bale_user_id") != uid:
        return send(cid, "❌ یافت نشد")
    if r.get("payment_status") == "paid":
        return send(cid, "✅ این فرم قبلاً پرداخت شده است 💚")
    form = get_form(r["form_id"])
    if not form:
        return send(cid, "❌ فرم یافت نشد")
    price = int(r.get("amount") or 0) or form_total_price(form["id"], rid)
    if price <= 0:
        return finalize(cid, uid, rid)
    return _start_payment(cid, uid, form, r, price)


def back_to_form(cid, uid, rid):
    """◀️ برگشت از صورتحساب به فرم برای ویرایش"""
    rid = _rid_ok(rid)
    if not rid:
        return send(cid, "❌ درخواست نامعتبر")
    r = db_execute("SELECT * FROM form_responses WHERE id=?",
                   (int(rid),), fetch="one")
    if not r or r.get("bale_user_id") != uid:
        return send(cid, "❌ یافت نشد")
    if r.get("payment_status") == "paid":
        return send(cid, "✅ این فرم پرداخت شده — قابل تغییر نیست")
    db_execute("UPDATE form_responses SET status='draft' WHERE id=?", (rid,))
    form = get_form(r["form_id"])
    if not form:
        return send(cid, "❌ فرم یافت نشد")
    recount_responses(form["id"])

    # 🔴 مهم: _begin نزنیم! چون همه سوال‌ها پاسخ دارند و
    #    ask_next بلافاصله دوباره ثبت نهایی می‌کند → حلقه.
    #    به‌جایش فهرست سوالات را نشان می‌دهیم تا کاربر
    #    هرکدام را خواست عوض کند.
    st = {"fid": form["id"], "rid": rid, "idx": 0, "multi": [],
          "prov": None, "files": [], "items": []}
    set_state(uid, STATE_FILL, st, merge=False)
    return show_question_list(cid, uid, rid)


def _start_payment(cid, uid, form, r, price):
    """
    شروع پرداخت فرم — استفاده از موتور پرداخت فاز ۸.

    🔴 فاز ۲۳: پیام «نیاز به پرداخت» حذف شد — کاربر همین الان
       صورتحساب را دیده و تأیید کرده، دوباره گفتنش اضافی است.
    """
    method = form.get("payment_method") or "none"
    pseudo = {
        "id": form["id"], "title": form["title"],
        "description": form.get("description") or form["title"],
        "payment_method": method,
        "payment_card_id": form.get("payment_card_id"),
        "payment_gateway_id": form.get("payment_gateway_id"),
        "_form_response_id": r["id"],
        "_quiet_vpn": 1,     # 🛡️ هشدار در صورتحساب آمده — تکرار نشود
    }
    try:
        import payments as pay
        txid = pay.route_payment(cid, uid, pseudo, r["id"], price)
        if txid:
            db_execute("UPDATE form_responses SET transaction_id=? WHERE id=?",
                       (txid, r["id"]))
    except Exception as e:
        log(f"❌ پرداخت فرم: {e}")
        send(cid, "⚠️ خطا در شروع پرداخت. با پشتیبانی تماس بگیرید.")
    return True


def cancel_fill(cid, uid, rid=None):
    clear_state(uid)
    send(cid, render("form_txt_cancel"), kb_remove())
    from bale_api import kb_main
    from auth import is_admin
    return send(cid, "🏠 منوی اصلی", kb_main(is_admin(uid)))


# ==================== بلیت ====================
# ══════════════════════════════════════════════════════════
# 🆕 فاز ۱۵ — گواهینامه فرم · آیدی کارت · پیام به برگزارکننده
# ══════════════════════════════════════════════════════════
STATE_FF_MSG = "ff_contact_msg"


def _own_response(uid, rid):
    """پاسخ را برمی‌گرداند اگر مال همین کاربر (یا ادمین) باشد"""
    try:
        rid = int(rid)
    except (TypeError, ValueError):
        return None, None
    r = db_execute("SELECT * FROM form_responses WHERE id=?", (rid,),
                   fetch="one")
    if not r:
        return None, None
    if r.get("bale_user_id") != uid:
        from auth import is_admin
        if not is_admin(uid):
            return None, None
    return r, get_form(r["form_id"])


def send_form_cert(cid, uid, rid):
    """🎓 صدور گواهینامه برای پاسخ فرم"""
    r, form = _own_response(uid, rid)
    if not r or not form:
        return send(cid, "❌ یافت نشد یا دسترسی ندارید")
    if not form.get("cert_enabled"):
        return send(cid, "⚠️ این فرم گواهینامه ندارد")
    if r.get("status") not in ("completed", "confirmed"):
        return send(cid, "⏳ ابتدا فرم را کامل کنید")

    u = get_user(uid) or {}
    name = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip()         or "شرکت‌کننده"
    serial = r.get("tracking_code") or "—"
    tpl = form.get("cert_template") or (
        "🎓 گواهینامه شرکت\n"
        "━━━━━━━━━━━━━━\n\n"
        "بدین‌وسیله گواهی می‌شود\n\n"
        "🧑 {name}\n\n"
        "در «{title}» شرکت کرده است.\n\n"
        "📅 {date}\n"
        "🔖 شماره: {serial}")
    txt = (tpl.replace("{name}", name)
              .replace("{title}", form.get("title") or "")
              .replace("{date}", jnow())
              .replace("{serial}", serial))
    log_action(uid, "form_cert", {"rid": r["id"], "fid": form["id"]})
    return send(cid, txt, {"inline_keyboard": [
        [{"text": "🏠 منوی اصلی", "callback_data": "back_main"}]]})


def send_id_card(cid, uid, rid):
    """🆔 صدور آیدی کارت (کارت عضویت / هوادار)"""
    r, form = _own_response(uid, rid)
    if not r or not form:
        return send(cid, "❌ یافت نشد یا دسترسی ندارید")
    if not form.get("idcard_enabled"):
        return send(cid, "⚠️ این فرم کارت ندارد")

    u = get_user(uid) or {}
    name = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip()         or "عضو"
    title = form.get("idcard_title") or form.get("title") or "کارت عضویت"
    code = r.get("tracking_code") or r.get("qr_code") or "—"

    lines = [
        "🆔 " + title,
        "━━━━━━━━━━━━━━", "",
        f"👤 {name}",
    ]
    if u.get("mobile"):
        lines.append(f"📱 {u['mobile']}")
    if u.get("city"):
        lines.append(f"🏙️ {u['city']}")
    lines += ["", f"🔖 شماره کارت: {code}", f"📅 صدور: {jnow()}"]
    log_action(uid, "form_idcard", {"rid": r["id"], "fid": form["id"]})
    return send(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🏠 منوی اصلی", "callback_data": "back_main"}]]})


def start_contact(cid, uid, rid):
    """💬 شروع پیام به برگزارکننده فرم"""
    r, form = _own_response(uid, rid)
    if not r or not form:
        return send(cid, "❌ یافت نشد")
    if not form.get("contact_enabled"):
        return send(cid, "⚠️ ارتباط برای این فرم فعال نیست")
    set_state(uid, STATE_FF_MSG, {"rid": r["id"], "fid": form["id"]},
              merge=False)
    from bale_api import kb_cancel
    send(cid, (f"💬 پیام به برگزارکننده\n━━━━━━━━━━━━━━\n\n"
               f"📋 {form.get('title')}\n\n"
               f"پیام خود را بنویسید:"), kb_cancel())


def handle_contact_msg(message):
    """دریافت پیام کاربر و ارسال به مالک فرم"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    d = get_state_data(uid)
    fid, rid = d.get("fid"), d.get("rid")

    from bale_api import BTN_BACK, kb_remove
    if text in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        return send(cid, "❌ لغو شد", kb_remove())
    if not text:
        return send(cid, "⚠️ لطفاً متن پیام را بنویسید:")

    form = get_form(fid)
    if not form:
        clear_state(uid)
        return send(cid, "❌ فرم یافت نشد", kb_remove())

    u = get_user(uid) or {}
    name = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip()         or "کاربر"
    body = (f"💬 پیام درباره فرم «{form.get('title')}»\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"👤 {name}\n"
            f"📱 {u.get('mobile') or '—'}\n"
            f"🔖 کد پیگیری: {(db_execute('SELECT tracking_code FROM form_responses WHERE id=?', (rid,), fetch='one') or {}).get('tracking_code') or '—'}\n\n"
            f"📄 پیام:\n{text[:1500]}")

    targets = set()
    if form.get("owner_id"):
        targets.add(form["owner_id"])
    for a in db_execute("SELECT bale_user_id FROM form_admins WHERE form_id=?",
                        (fid,), fetch="all") or []:
        if a.get("bale_user_id"):
            targets.add(a["bale_user_id"])

    sent_n = 0
    for t in targets:
        try:
            send(t, body)
            sent_n += 1
        except Exception as e:
            log(f"⚠️ ارسال پیام فرم: {e}")

    clear_state(uid)
    log_action(uid, "form_contact", {"fid": fid})
    if sent_n:
        return send(cid, "✅ پیام شما ارسال شد\n\n"
                         "💚 به‌زودی پاسخ می‌گیرید.", kb_remove())
    return send(cid, "⚠️ فعلاً مخاطبی برای این فرم ثبت نشده", kb_remove())


def send_ticket(cid, uid, rid):
    r = db_execute("SELECT * FROM form_responses WHERE id=?", (int(rid),), fetch="one")
    if not r:
        return send(cid, "❌ یافت نشد")
    if r.get("bale_user_id") != uid:
        from auth import is_admin
        if not is_admin(uid):
            return send(cid, "❌ دسترسی ندارید")
    form = get_form(r["form_id"])
    if not form:
        return send(cid, "❌ فرم یافت نشد")
    if r.get("status") not in ("completed", "confirmed"):
        return send(cid, "⚠️ ابتدا فرم را تکمیل کنید")

    u = get_user(r.get("bale_user_id")) or {}
    name = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip()
    if not name:
        name = _find_name_answer(r["id"]) or "کاربر"

    tracking = r.get("tracking_code") or "—"
    qr = r.get("qr_code") or "—"
    cap = render("form_txt_ticket", name=name, tracking=tracking, qr=qr,
                 title=form["title"])

    # 🎫 فاز ۲۶ — موتور تازهٔ بلیط (قابل تنظیم از پنل)
    path = None
    try:
        import ticket as _tk
        if _tk.enabled():
            path = _tk.build_for_response(rid)
    except Exception as e:
        log(f"⚠️ بلیط تصویری: {e}")
    if not path:
        path = _make_ticket_image(form, name, tracking, qr)
    if path:
        res = send_photo(cid, path, cap)
        if res.get("ok"):
            return res
    return send(cid, cap + f"\n\n📋 {form['title']}")


def _find_name_answer(rid):
    """پیدا کردن نام از پاسخ‌های فرم"""
    rows = db_execute("""SELECT a.value_text, a.field_type FROM form_answers a
        WHERE a.response_id=? AND a.field_type IN
        ('full_name','first_name','last_name')""", (rid,), fetch="all") or []
    for r in rows:
        if r.get("field_type") == "full_name" and r.get("value_text"):
            return r["value_text"]
    parts = [r.get("value_text") for r in rows if r.get("value_text")]
    return " ".join(parts) if parts else None


def _make_ticket_image(form, name, tracking, qr):
    """ساخت تصویر بلیت با Pillow"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    try:
        from pathlib import Path
        W, H = 1000, 620
        bg = (250, 240, 245)
        accent = (200, 90, 140)
        img = Image.new("RGB", (W, H), bg)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, 90], fill=accent)
        d.rectangle([20, 110, W - 20, H - 20], outline=accent, width=4)

        try:
            import arabic_reshaper
            from bidi.algorithm import get_display

            def shape(t):
                return get_display(arabic_reshaper.reshape(str(t)))
        except ImportError:
            def shape(t):
                return str(t)

        def center(t, y, fill=(40, 40, 40)):
            s = shape(t)
            try:
                bb = d.textbbox((0, 0), s)
                w = bb[2] - bb[0]
            except Exception:
                w = len(s) * 7
            d.text(((W - w) / 2, y), s, fill=fill)

        center(form.get("title") or "بلیت", 35, (255, 255, 255))
        center(name, 150)
        center(f"کد پیگیری: {tracking}", 200)
        center(f"کد QR: {qr}", 240)

        qpath = None
        try:
            import qrcode
            qimg = qrcode.make(qr).resize((200, 200))
            img.paste(qimg, (int((W - 200) / 2), 280))
        except ImportError:
            d.rectangle([int((W - 200) / 2), 280, int((W + 200) / 2), 480],
                        outline=accent, width=3)
            center(qr, 370)

        center(jnow(), 520)

        out = Path(FILES_DIR) / "forms" / "tickets"
        out.mkdir(parents=True, exist_ok=True)
        fp = out / f"{tracking}.jpg"
        img.save(fp, "JPEG", quality=90)
        return str(fp)
    except Exception as e:
        log(f"⚠️ ساخت بلیت: {e}")
        return None


# ==================== مشاهده پاسخ خود کاربر ====================
def show_my_response(cid, uid, rid):
    """
    📄 پاسخ کاربر.

    🔴 فاز ۲۳: دکمه حذف کاملاً برداشته شد. دسترسی‌های کاربر
       را ادمین از فرم‌ساز تعیین می‌کند (AFTER_SUBMIT).
    """
    from forms import (after_submit_of, AFTER_SUBMIT, user_can_edit,
                       user_can_withdraw, user_can_view)
    r = db_execute("SELECT * FROM form_responses WHERE id=?", (int(rid),), fetch="one")
    if not r:
        return send(cid, "❌ یافت نشد")
    is_owner = (r.get("bale_user_id") == uid)
    if not is_owner:
        from auth import is_admin
        if not is_admin(uid):
            return send(cid, "❌ دسترسی ندارید")
    form = get_form(r["form_id"])
    if not form:
        return send(cid, "❌ فرم یافت نشد")

    # 🔒 ادمین فرم را بسته — کاربر نباید ببیند
    if is_owner and not user_can_view(form):
        return send_or_edit(cid, (
            "🔒 پاسخ ثبت شد\n━━━━━━━━━━━━━━\n\n"
            f"📋 {form['title']}\n"
            f"🔖 کد پیگیری: {r.get('tracking_code') or '—'}\n\n"
            "💚 سپاس از شما — پاسخ شما با موفقیت ثبت شد."
        ), {"inline_keyboard": [
            [{"text": "🏠 منوی اصلی", "callback_data": "back_main"}]]})

    withdrawn = (r.get("status") == "withdrawn")
    lines = [f"📄 پاسخ شما — {form['title']}", "━━━━━━━━━━━━━━", ""]
    if withdrawn:
        lines += ["🚪 شما از این درخواست انصراف داده‌اید", ""]
    lines += [f"🔖 کد پیگیری: {r.get('tracking_code') or '—'}",
              f"📅 {r.get('completed_at') or _jd.fmt(r.get('started_at'), 'datetime')}", ""]

    rows = db_execute("""SELECT a.*, f.label, f.field_type ft, f.field_order
        FROM form_answers a LEFT JOIN form_fields f ON f.id=a.field_id
        WHERE a.response_id=? ORDER BY f.field_order""", (rid,), fetch="all") or []
    for a in rows:
        fl = a.get("label") or field_meta(a.get("ft")).get("name", "سوال")
        v = a.get("value_text") or ""
        if a.get("file_id") and not v:
            v = "📎 فایل"
        lines.append(f"▫️ {fl[:40]}:\n   {v or '—'}")

    if r.get("max_score"):
        lines += ["", f"🎯 نمره: {r.get('score')} از {r.get('max_score')}"]
    if r.get("payment_status") == "paid":
        lines += ["", f"💰 پرداخت: {fmt_amount(r.get('amount'))} {CURRENCY_LABEL} ✅"]
    elif r.get("status") == "pending_payment":
        lines += ["", f"⏳ در انتظار پرداخت: "
                      f"{fmt_amount(r.get('amount'))} {CURRENCY_LABEL}"]

    btns = []
    if r.get("status") == "pending_payment" and is_owner:
        btns.append([{"text": "💳 پرداخت", "callback_data": f"ffinv_{rid}"}])
    if form.get("ticket_enabled") and r.get("status") in ("completed", "confirmed"):
        btns.append([{"text": "🎫 دریافت مجدد بلیت", "callback_data": f"fftk_{rid}"}])

    if is_owner and not withdrawn:
        if user_can_edit(form) and r.get("status") == "completed":
            btns.append([{"text": "✏️ ویرایش پاسخ‌ها",
                          "callback_data": f"ffedit_{rid}"}])
        if user_can_withdraw(form) and r.get("status") in ("completed",
                                                           "confirmed"):
            btns.append([{"text": "🚪 انصراف از این درخواست",
                          "callback_data": f"ffwd_{rid}"}])

    btns.append([{"text": "📋 فرم‌های من", "callback_data": "ff_myforms"}])
    btns.append([{"text": "🏠 منوی اصلی", "callback_data": "back_main"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def withdraw_response(cid, uid, rid, confirmed=False):
    """
    🚪 انصراف کاربر از درخواست.

    🔴 مهم: هیچ داده‌ای پاک نمی‌شود — فقط وضعیت عوض می‌شود.
       کاربر هرگز نباید بتواند پاسخش را حذف کند (درخواست صریح).
       ادمین همچنان همه‌چیز را می‌بیند.
    """
    from forms import user_can_withdraw
    rid = _rid_ok(rid)
    r = db_execute("SELECT * FROM form_responses WHERE id=?",
                   (rid,), fetch="one") if rid else None
    if not r or r.get("bale_user_id") != uid:
        return send(cid, "❌ دسترسی ندارید")
    form = get_form(r["form_id"])
    if not form:
        return send(cid, "❌ فرم یافت نشد")
    if not user_can_withdraw(form):
        return send(cid, "⚠️ انصراف از این فرم ممکن نیست.\n\n"
                         "💡 برای پیگیری با پشتیبانی تماس بگیرید 💚")
    if r.get("status") == "withdrawn":
        return send(cid, "ℹ️ قبلاً انصراف داده‌اید")

    if not confirmed:
        warn = ""
        if r.get("payment_status") == "paid":
            warn = ("\n\n💰 شما برای این فرم پرداخت کرده‌اید.\n"
                    "   بازگشت وجه تابع قوانین مجموعه است.")
        return send_or_edit(cid, (
            f"🚪 انصراف از درخواست\n━━━━━━━━━━━━━━\n\n"
            f"📋 {form['title']}\n"
            f"🔖 {r.get('tracking_code') or '—'}\n\n"
            f"آیا مطمئنید می‌خواهید انصراف دهید؟{warn}\n\n"
            f"🌱 اطلاعات شما پاک نمی‌شود — فقط به ما اعلام\n"
            f"   می‌کنید که دیگر شرکت نمی‌کنید."
        ), {"inline_keyboard": [
            [{"text": "🚪 بله، انصراف می‌دهم",
              "callback_data": f"ffwdy_{rid}"}],
            [{"text": "◀️ نه، برگرد", "callback_data": f"ffmy_{rid}"}]]})

    db_execute("UPDATE form_responses SET status='withdrawn' WHERE id=?",
               (rid,))
    recount_responses(form["id"])
    log_action(uid, "form_withdraw", {"fid": form["id"], "rid": rid})

    # 🔔 ادمین بداند
    try:
        if form.get("notify_admins"):
            from auth import get_user as _gu
            u = _gu(uid) or {}
            nm = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip()
            _notify_new_response(form, r, f"🚪 انصراف: {nm}",
                                 r.get("tracking_code") or "—")
    except Exception as e:
        log(f"⚠️ اعلان انصراف: {e}")

    send(cid, "🚪 انصراف شما ثبت شد.\n\n"
              "🌱 هر وقت خواستید دوباره می‌توانید اقدام کنید 💚")
    return show_local_my_forms(cid, uid, 0)


def edit_my_response(cid, uid, rid):
    """ویرایش پاسخ (اگر فرم اجازه دهد)"""
    r = db_execute("SELECT * FROM form_responses WHERE id=?", (int(rid),), fetch="one")
    if not r or r.get("bale_user_id") != uid:
        return send(cid, "❌ دسترسی ندارید")
    from forms import user_can_edit
    form = get_form(r["form_id"])
    if not form or not user_can_edit(form):
        return send(cid, "⚠️ ویرایش این فرم مجاز نیست 🌱")
    ok, reason, extra = form_gate(form)
    if not ok:
        return _closed_message(cid, form, reason, extra)
    db_execute("UPDATE form_responses SET status='draft' WHERE id=?", (rid,))
    recount_responses(form["id"])
    return _begin(cid, uid, form, rid)


# ==================== فرم‌های من (کاربر) ====================
def show_local_my_forms(cid, uid, page=0):
    """Explicit viewer for historical bot-local responses; never an API fallback."""
    rows = db_execute("""SELECT r.*, f.title, f.form_type, f.ticket_enabled
        FROM form_responses r JOIN forms f ON f.id=r.form_id
        WHERE r.bale_user_id=? AND r.status IN
              ('completed','confirmed','pending_payment','withdrawn')
        ORDER BY r.id DESC""", (uid,), fetch="all") or []

    if not rows:
        return send_or_edit(cid, (
            "📚 سوابق محلی قدیمی\n━━━━━━━━━━━━━━\n\n"
            "📭 سابقه‌ای در داده‌های قدیمی ربات پیدا نشد."
        ), {"inline_keyboard": [
            [{"text": "📋 پاسخ‌های پایگاه مشترک", "callback_data": "ff_myforms"}],
            [{"text": "🏠 منوی اصلی", "callback_data": "back_main"}]]})

    per = 6
    pages = max(1, (len(rows) + per - 1) // per)
    page = max(0, min(int(page or 0), pages - 1))
    chunk = rows[page * per:(page + 1) * per]

    lines = [f"📚 سوابق محلی قدیمی ({len(rows)})", "━━━━━━━━━━━━━━", ""]
    btns = []
    for r in chunk:
        t = FORM_TYPES.get(r.get("form_type") or "", {})
        st = ("✅" if r["status"] in ("completed", "confirmed")
              else ("🚪" if r["status"] == "withdrawn" else "⏳"))
        lines.append(f"{st} {t.get('icon','📄')} {r['title'][:34]}")
        lines.append(f"   🔖 {r.get('tracking_code') or '—'}")
        btns.append([{"text": f"{st} {r['title'][:30]}",
                      "callback_data": f"ffmy_{r['id']}"}])

    if pages > 1:
        nav = []
        if page > 0:
            nav.append({"text": "⬅️", "callback_data": f"fflocalpg_{page-1}"})
        nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
        if page < pages - 1:
            nav.append({"text": "➡️", "callback_data": f"fflocalpg_{page+1}"})
        btns.append(nav)
    btns.append([{"text": "📋 پاسخ‌های پایگاه مشترک", "callback_data": "ff_myforms"}])
    btns.append([{"text": "🏠 منوی اصلی", "callback_data": "back_main"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_my_forms(cid, uid, page=0):
    """List only this user's submitted conversational responses from the shared API."""
    try:
        history = shared_api.list_my_bot_form_responses(uid, page)
    except shared_api.SharedAPIError:
        return send_or_edit(cid, (
            "📋 فرم‌های من\n━━━━━━━━━━━━━━\n\n"
            "سوابق از پایگاه مشترک در دسترس نیست.\n"
            "اطلاعات محلی جایگزین نمی‌شود؛ کمی بعد دوباره تلاش کنید."
        ), {"inline_keyboard": [
            [{"text": "🔄 تلاش دوباره", "callback_data": "ff_myforms"}],
            [{"text": "🏠 منوی اصلی", "callback_data": "back_main"}]]})

    items = history["items"]
    if not items:
        return send_or_edit(cid, (
            "📋 فرم‌های من\n━━━━━━━━━━━━━━\n\n"
            "هنوز پاسخی از گفت‌وگوی بات در پایگاه مشترک ثبت نشده است."
        ), {"inline_keyboard": [
            [{"text": "📝 فرم‌های فعال", "callback_data": "ffpg_0"}],
            [{"text": "📚 سوابق محلی قدیمی", "callback_data": "ff_local_forms"}],
            [{"text": "🏠 منوی اصلی", "callback_data": "back_main"}]]})

    total = history["total"]
    current_page = history["page"]
    pages = history["pages"]
    lines = [f"📋 فرم‌های من ({total})", "━━━━━━━━━━━━━━", ""]
    buttons = []
    for item in items:
        accepted = item["status"] == "accepted"
        icon = "✅" if accepted else "⏳"
        date_text = _jd.fmt(item["created_at"], "datetime")
        status_text = "ثبت‌شده" if accepted else "فهرست انتظار"
        lines.append(f"{icon} {item['form_name'][:48]}")
        lines.append(f"   {status_text} · {date_text} · {item['answer_count']} پاسخ")
        buttons.append([{
            "text": f"📄 مشاهده: {item['form_name'][:34]}",
            "callback_data": f"ffsr_{item['id']}",
        }])

    if pages > 1:
        navigation = []
        if current_page > 0:
            navigation.append({
                "text": "⬅️", "callback_data": f"ffmypg_{current_page - 1}"
            })
        navigation.append({"text": f"{current_page + 1}/{pages}", "callback_data": "noop"})
        if current_page < pages - 1:
            navigation.append({
                "text": "➡️", "callback_data": f"ffmypg_{current_page + 1}"
            })
        buttons.append(navigation)
    buttons.extend([
        [{"text": "📝 فرم‌های فعال", "callback_data": "ffpg_0"}],
        [{"text": "📚 سوابق محلی قدیمی", "callback_data": "ff_local_forms"}],
        [{"text": "🏠 منوی اصلی", "callback_data": "back_main"}],
    ])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": buttons})


def show_shared_response(cid, uid, response_id):
    """Read one response through the shared API; never fall back to bot SQLite."""
    response_id = str(response_id or "")
    if not re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        response_id,
    ):
        return send(cid, "این دکمهٔ پاسخ معتبر نیست؛ از فهرست فرم‌های من دوباره انتخاب کنید.")
    try:
        result = shared_api.get_my_bot_form_response(uid, response_id)
    except shared_api.SharedAPIError as error:
        if error.status == 404:
            message = "این پاسخ پیدا نشد یا به حساب بلهٔ شما تعلق ندارد."
            keyboard = [[{"text": "📋 فرم‌های من", "callback_data": "ff_myforms"}]]
        else:
            message = "پاسخ از پایگاه مشترک در دسترس نیست؛ کمی بعد دوباره تلاش کنید."
            keyboard = [
                [{"text": "🔄 تلاش دوباره", "callback_data": f"ffsr_{response_id}"}],
                [{"text": "📋 فرم‌های من", "callback_data": "ff_myforms"}],
            ]
        return send_or_edit(
            cid,
            message,
            {"inline_keyboard": [*keyboard, [{"text": "🏠 منوی اصلی", "callback_data": "back_main"}]]},
        )

    response = result["response"]
    snapshot = response["form_snapshot"]
    accepted = response["status"] == "accepted"
    status_line = (
        "✅ پاسخ ثبت شده است."
        if accepted
        else "⏳ پاسخ در فهرست انتظار است؛ این وضعیت تأیید نهایی نیست."
    )
    lines = [
        f"📄 {snapshot['name'][:100]}",
        "━━━━━━━━━━━━━━",
        status_line,
        f"📅 {_jd.fmt(response['created_at'], 'datetime')}",
        "",
    ]
    ticket_type = snapshot.get("ticket_type")
    if accepted and isinstance(ticket_type, dict) and isinstance(ticket_type.get("name"), str):
        lines.insert(4, f"🎟 مدل بلیت: {ticket_type['name'][:120]}")
    answers = response["answers"]
    for field in snapshot["fields"]:
        value = answers.get(field["id"])
        if isinstance(value, list):
            rendered = "، ".join(value) if value else "—"
        elif isinstance(value, str) and value.strip():
            rendered = value
        else:
            rendered = "—"
        lines.append(f"▫️ {field['label'][:100]}:\n   {rendered}")
    return send_or_edit(
        cid,
        "\n".join(lines),
        {"inline_keyboard": [
            [{"text": "📋 فرم‌های من", "callback_data": "ff_myforms"}],
            [{"text": "📝 فرم‌های فعال", "callback_data": "ffpg_0"}],
            [{"text": "🏠 منوی اصلی", "callback_data": "back_main"}],
        ]},
    )


# ==================== فرم‌های منتشرشده (پایگاه مشترک) ====================
def show_public_forms(cid, _uid, page=0):
    """Show the shared server catalog; never substitute the bot's SQLite forms."""
    try:
        visible = shared_api.list_public_forms()
    except shared_api.SharedAPIError:
        return send_or_edit(cid, (
            "📝 فرم‌های فعال\n━━━━━━━━━━━━━━\n\n"
            "فهرست فرم‌های پایگاه مشترک در دسترس نیست.\n"
            "اطلاعات محلی ربات جایگزین نمی‌شود؛ کمی بعد دوباره تلاش کنید."
        ), {"inline_keyboard": [
            [{"text": "🔄 تلاش دوباره", "callback_data": "ffpg_0"}],
            [{"text": "🏠 منوی اصلی", "callback_data": "back_main"}]]})

    if not visible:
        return send_or_edit(cid, (
            "📝 فرم‌های فعال\n━━━━━━━━━━━━━━\n\n"
            "فعلاً فرم منتشرشده و قابل‌پاسخی در پایگاه مشترک نیست."
        ), {"inline_keyboard": [
            [{"text": "📋 فرم‌های من", "callback_data": "ff_myforms"}],
            [{"text": "🏠 منوی اصلی", "callback_data": "back_main"}]]})

    per = 6
    pages = max(1, (len(visible) + per - 1) // per)
    page = max(0, min(int(page or 0), pages - 1))
    chunk = visible[page * per:(page + 1) * per]

    lines = ["📝 فرم‌های فعال", "━━━━━━━━━━━━━━", ""]
    btns = []
    for form in chunk:
        name = " ".join(form["name"].split())
        lines.append(f"📄 {name[:64]}")
        row = []
        if NORA_WEBAPP_URL:
            form_url = f"{NORA_WEBAPP_URL.rstrip('/')}/form.html?{urlencode({'fid': form['id']})}"
            row.append({
                "text": f"📝 {name[:42]}",
                "web_app": {"url": form_url},
            })
        row.append({
            "text": f"💬 گفتگو: {name[:34]}",
            "callback_data": f"bffstart_{form['id']}",
        })
        btns.append(row)

    if not NORA_WEBAPP_URL:
        lines.extend([
            "",
            "نشانی وب‌اپ تنظیم نشده؛ می‌توانید از دکمهٔ گفتگومحور استفاده کنید.",
        ])
    else:
        lines.extend(["", "برای پاسخ‌گویی، وب‌اپ یا گفتگوی بات را انتخاب کنید."])

    if pages > 1:
        nav = []
        if page > 0:
            nav.append({"text": "⬅️", "callback_data": f"ffpg_{page-1}"})
        nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
        if page < pages - 1:
            nav.append({"text": "➡️", "callback_data": f"ffpg_{page+1}"})
        btns.append(nav)
    btns.append([{"text": "📋 فرم‌های من", "callback_data": "ff_myforms"}])
    btns.append([{"text": "🏠 منوی اصلی", "callback_data": "back_main"}])
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})
