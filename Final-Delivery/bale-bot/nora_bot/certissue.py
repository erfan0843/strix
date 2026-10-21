"""
🎓 مرکز صدور گواهینامه رویداد — فاز ۲۲

درخواست کاربر (عیناً):
  «گواهینامه تو مدیریت رویداد صادر نمیشه، صدور گواهینامهٔ مبتنی بر
   حضور رو کامل و دقیق و با جزییات و انتخاب قالب و تغییر پارامترها...
   کامل و دقیق بیار تو صدور گواهینامه گروهی رویداد»

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 چهار باگ ریشه‌ای که پیدا شد

  ۱) صدور گروهی، فایل نمی‌فرستاد!
     issue_certificate(silent=True) صدا زده می‌شد — یعنی «فایل
     نفرست» — و بعد فقط متن خام template ارسال می‌شد. کل موتور
     certgen (فاز ۱۹ تا ۲۱) دور زده می‌شد. PNG و PDF ساخته
     می‌شدند، در دیتابیس ذخیره می‌شدند، ولی هرگز به دست کاربر
     نمی‌رسیدند.

  ۲) شرط دریافت گواهینامه بی‌اثر بود
     ستون‌های cert_condition و cert_min_sessions در جدول رویداد
     وجود داشتند ولی هیچ‌جای کد خوانده نمی‌شدند. هرکس ثبت‌نام
     کرده بود گواهینامه می‌گرفت — حتی اگر یک جلسه هم نیامده بود.

  ۳) انتخاب قالب ممکن نبود
     همیشه certgen.get_template() یعنی قالب پیش‌فرض. نمی‌شد برای
     هر رویداد قالب جدا داد.

  ۴) پارامترها قابل تغییر نبودند
     ادمین نمی‌توانست برای یک رویداد خاص مقدار دلخواه بگذارد.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 جریان کار جدید

  🎓 مرکز صدور  →  ۱️⃣ قالب   ۲️⃣ شرط   ۳️⃣ پارامتر
                  ۴️⃣ پیش‌نمایش   ۵️⃣ صدور   ۶️⃣ مدیریت صادرشده‌ها
"""
from privacy import user_error_message
import json
import time
from pathlib import Path

from database import db_execute, db_scalar, get_setting, set_setting, log
from auth import (set_state, get_state_data, clear_state, log_action,
                  normalize_digits, is_admin as _is_admin, get_user)
from bale_api import (send, send_or_edit, send_document, send_photo,
                      kb_cancel, kb_remove, BTN_BACK)
import jalali as _jd

STATE_CI_PARAM = "ci_param"


# ══════════════════════════════════════════════════════════
# 📋 شرط دریافت گواهینامه
#
# 🎯 «صدور گواهینامه بر پایهٔ حضور — کامل و دقیق»
#    حضوری یعنی بر اساس حضور واقعی — نه صرفِ ثبت‌نام.
# ══════════════════════════════════════════════════════════
CONDITIONS = {
    "registered": {
        "icon": "📝", "name": "فقط ثبت‌نام",
        "desc": "هرکس ثبت‌نام کرده — بدون توجه به حضور",
    },
    "attended": {
        "icon": "✋", "name": "حداقل یک جلسه حضور",
        "desc": "باید دست‌کم در یک جلسه حاضر بوده باشد",
    },
    "sessions": {
        "icon": "🔢", "name": "حداقل تعداد جلسه",
        "desc": "تعداد جلسه‌ای که شما تعیین می‌کنید",
    },
    "percent": {
        "icon": "📊", "name": "حداقل درصد حضور",
        "desc": "مثلاً ۸۰٪ جلسات را حاضر بوده باشد",
    },
    "all": {
        "icon": "💯", "name": "حضور کامل",
        "desc": "در همه جلسات حاضر بوده باشد",
    },
    "manual": {
        "icon": "👤", "name": "انتخاب دستی",
        "desc": "خودتان نفرات را یکی‌یکی انتخاب می‌کنید",
    },
}

# پارامترهایی که ادمین می‌تواند برای هر رویداد دستی بگذارد
# (کلید certgen, آیکن, عنوان, راهنما)
EVENT_PARAMS = [
    ("course", "📚", "نام دوره", "اگر با عنوان رویداد فرق دارد"),
    ("hours", "⏱️", "ساعت آموزشی", "مثال: 16"),
    ("sessions_total", "🔢", "کل جلسات", "برای محاسبه درصد حضور"),
    ("teacher", "👨‍🏫", "نام استاد", ""),
    ("teacher_role", "🎖️", "سمت استاد", ""),
    ("grade", "💯", "نمره", "اگر آزمون داشته"),
    ("level", "🏅", "سطح دوره", "مثال: مقدماتی · پیشرفته"),
    ("field", "📖", "رشته / موضوع", ""),
    ("place", "📍", "محل برگزاری", "اگر با آدرس رویداد فرق دارد"),
    ("mode", "🌐", "نحوه برگزاری", "حضوری · برخط · ترکیبی"),
    ("desc", "📝", "توضیح دلخواه", "متن آزاد روی گواهینامه"),
    ("code", "🔖", "کد دوره", ""),
]


# ══════════════════════════════════════════════════════════
# 🗄️ تنظیمات گواهینامه هر رویداد
# ══════════════════════════════════════════════════════════
def _eid(v):
    """🛡️ تبدیل امن شناسه — ورودی خراب کرش نکند"""
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _cfg_key(eid):
    return f"evcert_{_eid(eid)}"


def get_cfg(eid):
    """
    ⚙️ تنظیمات گواهینامه یک رویداد.

    در settings ذخیره می‌شود تا نیازی به ستون جدید در جدول
    رویداد نباشد (مهاجرت امن‌تر).
    """
    raw = get_setting(_cfg_key(eid), "")
    if raw:
        try:
            d = json.loads(raw)
            if isinstance(d, dict):
                return d
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def save_cfg(eid, cfg, uid=None):
    set_setting(_cfg_key(eid), json.dumps(cfg, ensure_ascii=False),
                f"گواهینامه رویداد {eid}", "certificate", uid)
    return cfg


def cfg_get(eid, key, dflt=""):
    return get_cfg(eid).get(key, dflt)


def cfg_set(eid, key, val, uid=None):
    c = get_cfg(eid)
    c[key] = val
    return save_cfg(eid, c, uid)


def condition_of(eid, ev=None):
    """
    📋 شرط فعلی دریافت گواهینامه.

    🔴 قبلاً ستون cert_condition در جدول رویداد بود ولی هیچ‌جا
       خوانده نمی‌شد. حالا هم آن را می‌خوانیم هم تنظیم جدید را.
    """
    c = get_cfg(eid)
    if c.get("condition"):
        return c["condition"]
    # 🔴 ستون cert_condition مقدار پیش‌فرض 'attended' دارد ولی
    #    هرگز خوانده نمی‌شد — یعنی هیچ رویدادی واقعاً آن را
    #    «انتخاب» نکرده. اگر همان پیش‌فرض خام است، نادیده بگیر،
    #    وگرنه رویدادهای قدیمی ناگهان گواهینامه نمی‌دهند.
    if ev:
        v = str(ev.get("cert_condition") or "")
        if v in CONDITIONS and v != "attended":
            return v
    # 🎯 پیش‌فرض «ثبت‌نام» تا رفتار رویدادهای قبلی عوض نشود.
    #    اگر رویداد جلسه دارد، پنل پیشنهاد می‌دهد سخت‌گیرتر شوید.
    return get_setting("cert_default_condition", "registered")


def min_sessions_of(eid, ev=None):
    c = get_cfg(eid)
    if c.get("min_sessions") is not None:
        try:
            return int(c["min_sessions"])
        except (TypeError, ValueError):
            return 0
    try:
        return int((ev or {}).get("cert_min_sessions") or 0)
    except (TypeError, ValueError):
        return 0


def min_percent_of(eid):
    try:
        return int(cfg_get(eid, "min_percent", 80) or 80)
    except (TypeError, ValueError):
        return 80


def template_of(eid):
    """
    📄 قالب انتخابی این رویداد — یا پیش‌فرض.

    🎯 «انتخاب قالب» — قبلاً همیشه قالب پیش‌فرض استفاده می‌شد.

    🛡️ اگر جدول قالب‌ها هنوز ساخته نشده (نصب تازه) کرش نمی‌کند —
       گواهینامه به‌صورت متنی ساده صادر می‌شود.
    """
    import certgen
    try:
        certgen.init_cert_tables()
    except Exception:
        pass
    try:
        tid = cfg_get(eid, "template_id")
        if tid:
            t = certgen.get_template(int(tid))
            if t and t.get("is_active"):
                return t
        return certgen.get_template()
    except Exception as e:
        log(f"⚠️ خواندن قالب گواهینامه: {e}")
        return None


# ══════════════════════════════════════════════════════════
# 🧮 محاسبه واجدین شرایط
# ══════════════════════════════════════════════════════════
def sessions_count(eid):
    """تعداد جلسات تعریف‌شده رویداد"""
    return db_scalar("SELECT COUNT(*) FROM attendance_sessions "
                     "WHERE event_id=?", (eid,)) or 0


def excused_counts():
    """
    📄 آیا «غیبت موجه» به‌جای حضور حساب شود؟

    🎯 معنای «موجه» همین است — غیبتی که پذیرفته شده و نباید
       فرد را جریمه کند. پس پیش‌فرض روشن است.
       ادمین می‌تواند از تنظیمات خاموشش کند.
    """
    return get_setting("cert_excused_counts", "1") == "1"


def _present_map(eid):
    """
    {bale_user_id: تعداد جلساتی که «حاضر» حساب می‌شود}

    ✅ حاضر و ⏰ تأخیر همیشه حساب می‌شوند.
    📄 غیبت موجه هم — مگر ادمین خاموشش کند.
    """
    ok_st = ["present", "late"]
    if excused_counts():
        ok_st.append("excused")
    marks = ",".join("?" * len(ok_st))
    rows = db_execute(f"""
        SELECT bale_user_id, COUNT(DISTINCT session_id) n
        FROM attendance_records
        WHERE event_id=? AND status IN ({marks})
          AND bale_user_id IS NOT NULL
        GROUP BY bale_user_id
    """, tuple([eid] + ok_st), fetch="all") or []
    return {r["bale_user_id"]: r["n"] for r in rows}


def eligible(eid, ev=None):
    """
    ✅ چه کسانی واجد شرایط گواهینامه‌اند؟

    خروجی: (فهرست واجدین, فهرست ردشده‌ها, توضیح شرط)

    🔴 این تابع قلب رفع باگ ۲ است — قبلاً هیچ شرطی بررسی نمی‌شد
       و هرکس ثبت‌نام کرده بود گواهینامه می‌گرفت.
    """
    from events import get_event
    ev = ev or get_event(eid)
    cond = condition_of(eid, ev)
    total_s = sessions_count(eid)
    pres = _present_map(eid)

    regs = db_execute("""
        SELECT r.bale_user_id, r.status, r.id reg_id,
               COALESCE(r.attended, 0) reg_attended,
               u.first_name, u.last_name, u.national_id, u.mobile,
               u.id uid_db, u.gender, u.birth_date
        FROM event_registrations r
        LEFT JOIN users u ON u.id = r.user_id
        WHERE r.event_id=? AND r.status IN ('confirmed','attended')
          AND r.bale_user_id IS NOT NULL
        ORDER BY u.first_name, u.last_name
    """, (eid,), fetch="all") or []

    # 🔴 اگر رویداد اصلاً جلسه ندارد، شرط‌های مبتنی بر جلسه
    #    بی‌معنی‌اند — همه را برای همیشه رد می‌کنند!
    #    در این حالت به وضعیت ثبت‌نام برمی‌گردیم.
    #    (رویدادهای تک‌جلسه‌ای معمولاً جلسه تعریف نمی‌کنند)
    no_sessions = (total_s == 0)

    picked = set()
    if cond == "manual":
        try:
            picked = set(int(x) for x in cfg_get(eid, "picked", []) or [])
        except (TypeError, ValueError):
            picked = set()

    need_n = min_sessions_of(eid, ev)
    need_p = min_percent_of(eid)

    ok, no = [], []
    for r in regs:
        bu = r["bale_user_id"]
        n = pres.get(bu, 0)
        pct = int(n * 100 / total_s) if total_s else 0
        r = dict(r)
        r["present_n"] = n
        r["total_s"] = total_s
        r["percent"] = pct

        # بدون جلسه: «حاضر» یعنی ثبت‌نامش وضعیت attended دارد
        marked = (r.get("status") == "attended"
                  or bool(r.get("reg_attended")))

        if cond == "registered":
            good, why = True, ""
        elif cond == "attended":
            if no_sessions:
                good = marked
                why = "حضورش تأیید نشده"
            else:
                good = n >= 1
                why = "در هیچ جلسه‌ای حاضر نبوده"
        elif cond == "sessions":
            if no_sessions:
                good = marked
                why = "جلسه‌ای تعریف نشده — حضورش تأیید نشده"
            else:
                good = n >= max(1, need_n)
                why = f"{n} جلسه از {max(1, need_n)} جلسه لازم"
        elif cond == "percent":
            if no_sessions:
                good = marked
                why = "جلسه‌ای تعریف نشده — حضورش تأیید نشده"
            else:
                good = pct >= need_p
                why = f"{pct}٪ حضور — کمتر از {need_p}٪"
        elif cond == "all":
            if no_sessions:
                good = marked
                why = "جلسه‌ای تعریف نشده — حضورش تأیید نشده"
            else:
                good = n >= total_s
                why = f"{n} از {total_s} جلسه"
        elif cond == "manual":
            good = bu in picked
            why = "انتخاب نشده"
        else:
            good, why = True, ""

        if good:
            ok.append(r)
        else:
            r["why"] = why
            no.append(r)

    return ok, no, cond_text(eid, ev)


def cond_text(eid, ev=None):
    """📋 توضیح فارسی شرط فعلی"""
    cond = condition_of(eid, ev)
    c = CONDITIONS.get(cond, CONDITIONS["attended"])
    if cond == "sessions":
        return f"{c['icon']} حداقل {min_sessions_of(eid, ev)} جلسه حضور"
    if cond == "percent":
        return f"{c['icon']} حداقل {min_percent_of(eid)}٪ حضور"
    return f"{c['icon']} {c['name']}"


def _name_of(r):
    return f"{r.get('first_name') or ''} " \
           f"{r.get('last_name') or ''}".strip() or "بدون نام"


# ══════════════════════════════════════════════════════════
# 📋 ساخت داده‌های گواهینامه یک نفر
# ══════════════════════════════════════════════════════════
def build_for(eid, bale_uid, serial, ev=None, row=None):
    """
    📋 همه پارامترهای گواهینامه یک نفر.

    🎯 «تغییر پارامترها» — پارامترهای دستی ادمین اینجا
       روی مقادیر خودکار می‌نشینند.
    """
    import certgen
    from events import get_event
    ev = ev or get_event(eid) or {}
    u = row or get_user(bale_uid) or {}

    total_s = sessions_count(eid)
    n_pres = db_scalar(
        "SELECT COUNT(DISTINCT session_id) FROM attendance_records "
        "WHERE event_id=? AND bale_user_id=? AND status IN "
        "('present','late')", (eid, bale_uid)) or 0

    name = f"{u.get('first_name') or ''} " \
           f"{u.get('last_name') or ''}".strip() or "کاربر"

    # ساعت آموزشی — از رویداد یا دستی
    hours = ""
    if ev.get("duration_minutes"):
        try:
            hours = round(float(ev["duration_minutes"]) / 60, 1)
            hours = int(hours) if float(hours).is_integer() else hours
        except (TypeError, ValueError):
            hours = ""

    kw = dict(
        name=name,
        first_name=u.get("first_name") or "",
        last_name=u.get("last_name") or "",
        national_id=u.get("national_id") or "",
        mobile=u.get("mobile") or "",
        gender=u.get("gender") or "",
        birth_date=u.get("birth_date") or "",
        event=ev.get("title") or "",
        course=ev.get("title") or "",
        date=ev.get("start_date") or "",
        start_date=ev.get("start_date") or "",
        end_date=ev.get("end_date") or ev.get("start_date") or "",
        serial=serial,
        sessions=n_pres,
        sessions_total=total_s,
        hours=hours,
        location=ev.get("location_address") or "",
        place=ev.get("location_address") or "",
        organizer=ev.get("organizer") or "",
        mode="برخط" if ev.get("location_type") == "online" else "حضوری",
    )

    # ✏️ پارامترهای دستی ادمین — بالاترین اولویت
    manual = get_cfg(eid).get("params") or {}
    for k, v in manual.items():
        if str(v).strip():
            kw[k] = v

    return certgen.build_mapping(**kw)


# ══════════════════════════════════════════════════════════
# 🎓 صدور واقعی
# ══════════════════════════════════════════════════════════
def issue_one(eid, bale_uid, admin_uid, ev=None, row=None,
              send_to_user=True, force=False):
    """
    🎓 صدور گواهینامه یک نفر — با فایل واقعی.

    🔴 رفع باگ ۱: قبلاً در صدور گروهی، issue_certificate با
       silent=True صدا زده می‌شد و بعد فقط متن خام فرستاده
       می‌شد. فایل PNG/PDF ساخته می‌شد ولی هرگز ارسال نمی‌شد.

    خروجی: (cert_row یا None, پیام وضعیت)
    """
    import certgen
    import attendance as att
    from events import get_event
    ev = ev or get_event(eid)
    if not ev:
        return None, "رویداد یافت نشد"

    ex = db_execute("SELECT * FROM certificates WHERE event_id=? "
                    "AND bale_user_id=?", (eid, bale_uid), fetch="one")
    if ex and not force:
        if send_to_user:
            send_cert_files(bale_uid, ex, ev)
        return ex, "قبلاً صادر شده"

    u = row or get_user(bale_uid) or {}
    serial = (ex or {}).get("serial") or att.gen_serial()
    name = f"{u.get('first_name') or ''} " \
           f"{u.get('last_name') or ''}".strip() or "کاربر"

    # متن ساده (پشتیبان — اگر قالب نباشد)
    body = att.render_cert(
        get_setting("cert_template", att.DEFAULT_CERT),
        name=name, event=ev.get("title") or "",
        date=ev.get("start_date") or "-",
        org=get_setting("org_name", "") or "",
        serial=serial, national_id=u.get("national_id"),
        sessions=db_scalar(
            "SELECT COUNT(DISTINCT session_id) FROM attendance_records "
            "WHERE event_id=? AND bale_user_id=? AND status IN "
            "('present','late')", (eid, bale_uid)) or 0)

    files = {"png": None, "pdf": None, "docx": None, "tid": None}
    err = ""
    # 🔍 فاز ۳۴ — شناسهٔ دولایه: شمارهٔ نامه + کد فردی
    #
    # 🎯 «هر رویداد یدونه شماره ثبت داره، چطوری شخصی که استعلام
    #     میزنه اطلاعات اون گواهی براش میاد بالا؟»
    #
    # رکورد را **قبل از** ساخت فایل درج می‌کنیم تا شناسه‌اش
    # آماده باشد و روی خود گواهینامه چاپ شود.
    _cvinfo = {}
    # 🔢 آیا رکورد را همین حالا ما ساختیم؟ (فاز ۳۵)
    #    لازم است چون پایین‌تر باید شمارندهٔ کاربر را بالا ببریم.
    _brand_new = False
    if not ex:
        _pre = db_execute(
            "INSERT INTO certificates (event_id, user_id, bale_user_id, "
            "serial, issued_by) VALUES (?,?,?,?,?)",
            (eid, u.get("id"), bale_uid, serial, admin_uid))
        ex = db_execute("SELECT * FROM certificates WHERE id=?",
                        (_pre,), fetch="one")
        force = True
        _brand_new = True
    try:
        import certverify as _cv
        _cvinfo = _cv.stamp(ex["id"], eid)
        # 🔴 باگ رفع‌شده (فاز ۳۵):
        #    قبلاً هر بار serial با full_code جایگزین می‌شد.
        #    وقتی رویداد «شمارهٔ نامه» نداشت، build_full_code فقط
        #    کد فردی («KTF55E») را برمی‌گرداند و شمارهٔ سریال
        #    رسمی «NORA-۰۵۰۴-۱۲۳۴۵» کاملاً گم می‌شد — هم روی
        #    گواهینامه، هم در دیتابیس.
        #
        #    حالا فقط وقتی شمارهٔ نامهٔ واقعی وجود دارد جایگزین
        #    می‌کنیم؛ چون آن‌وقت full_code شکل کامل
        #    «۱۴۲۱/۵۴۷۲/۵۰۰۰/د-A7K2M9» را دارد که خودش
        #    شناسهٔ رسمی است.
        if _cvinfo.get("full_code") and _cvinfo.get("doc_no"):
            serial = _cvinfo["full_code"]
    except Exception as _e:
        log(f"⚠️ شناسهٔ استعلام: {_e}")

    tpl = template_of(eid)
    if tpl:
        try:
            mp = build_for(eid, bale_uid, serial, ev, u)
            if _cvinfo:
                mp["verify_code"] = _cvinfo.get("person_code") or ""
                mp["doc_no"] = _cvinfo.get("doc_no") or ""
                mp["issued_on"] = _cvinfo.get("issued_on") or ""
                if _cvinfo.get("expires_on"):
                    mp["expires_on"] = _cvinfo["expires_on"]
                try:
                    mp["verify_url"] = _cv.verify_link(
                        _cvinfo["full_code"])
                except Exception:
                    pass
            # 📷 فاز ۳۷ — عکس پرسنلی در گواهینامهٔ رویداد
            #    قبلاً فقط مرکز صدور عکس می‌گذاشت؛ گواهینامهٔ
            #    رویداد جای {عکس} را خالی رها می‌کرد.
            try:
                import certphoto as _cp
                _cp.attach(mp, bale_uid, tpl)
            except Exception as _pe:
                log(f"⚠️ عکس پرسنلی: {_pe}")

            res = certgen.generate(mp, tpl)
            files = {"png": res.get("png"), "pdf": res.get("pdf"),
                     "docx": res.get("docx"), "tid": tpl.get("id")}
            err = res.get("error") or ""
        except Exception as e:
            err = user_error_message(e)
            log(f"⚠️ ساخت گواهینامه {bale_uid}: {e}")

    if ex and force:
        db_execute("""UPDATE certificates SET serial=?, template=?,
            template_id=?, png_path=?, pdf_path=?, docx_path=?,
            file_path=?, revoked=0, issued_by=?,
            issued_at=CURRENT_TIMESTAMP WHERE id=?""",
            (serial, body, files["tid"], files["png"], files["pdf"],
             files["docx"], files["png"] or files["pdf"] or files["docx"],
             admin_uid, ex["id"]))
        new_id = ex["id"]
        # 🔴 باگ رفع‌شده (فاز ۳۵) — «شمارندهٔ گواهینامهٔ کاربر»:
        #    از فاز ۳۴ رکورد **قبل از** ساخت فایل درج می‌شود تا
        #    شناسهٔ دولایه روی خودِ گواهینامه چاپ شود. نتیجهٔ
        #    ناخواسته: مسیر اجرا همیشه به شاخهٔ «force» می‌رفت و
        #    شاخهٔ INSERT پایین — که تنها جای افزایش شمارنده بود —
        #    هرگز اجرا نمی‌شد. پس `total_certificates` کاربر روی
        #    صفر می‌ماند و در پروفایل «🎓 گواهینامه‌ها: ۰» نشان
        #    می‌داد، با اینکه گواهینامه گرفته بود.
        if _brand_new:
            db_execute("UPDATE users SET total_certificates="
                       "COALESCE(total_certificates,0)+1 "
                       "WHERE bale_user_id=?", (bale_uid,))
    else:
        new_id = db_execute("""INSERT INTO certificates
            (event_id, user_id, bale_user_id, serial, template, issued_by,
             template_id, png_path, pdf_path, docx_path, file_path)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (eid, u.get("id"), bale_uid, serial, body, admin_uid,
             files["tid"], files["png"], files["pdf"], files["docx"],
             files["png"] or files["pdf"] or files["docx"]))
        if new_id:
            db_execute("UPDATE users SET total_certificates="
                       "COALESCE(total_certificates,0)+1 "
                       "WHERE bale_user_id=?", (bale_uid,))

    if not new_id:
        return None, err or "ثبت در دیتابیس ناموفق"

    cert = db_execute("SELECT * FROM certificates WHERE id=?",
                      (new_id,), fetch="one")
    if send_to_user and cert:
        send_cert_files(bale_uid, cert, ev)
    log_action(bale_uid, "certificate_issued",
               {"event_id": eid, "serial": serial})
    # 🪞 آینهٔ سرور مشترک (بهترین‌تلاش؛ ربات صادرکننده می‌ماند)
    try:
        import shared_certificates as _sc
        _sc.sync_after_change(new_id)
    except Exception:
        pass
    return cert, err


# ══════════════════════════════════════════════════════════
# 🔒 فاز ۳۹ — قفل صدور خودسرویس
#
# 🎯 «صدور گواهینامه چرا دست کاربره؟ کلا صدور گواهینامه رو از
#     کاربر بگیر. چرا بعد اعلام کد حضور میتونه گواهی خودشو
#     بسازه؟ فقط و فقط چیزایی که من برای پروفایل کاربر
#     میفرستم میتونه بسازه و دریافت کنه»
#
# 🔴 سه راه خودسرویس وجود داشت:
#     ۱) دکمهٔ «🎓 دریافت گواهینامه» بعد از ثبت حضور  (ucert_)
#     ۲) دکمهٔ «🎓 صدور» در پنل رویداد کاربر          (evc_iss_)
#     ۳) صدا زدن مستقیم issue_certificate از روتر
#
# ✅ حالا همه از یک دروازه رد می‌شوند. پیش‌فرض: **بسته**.
#    کاربر فقط چیزی را می‌گیرد که ادمین از مرکز صدور برایش
#    منتشر کرده باشد (ccget_) یا قبلاً صادر شده باشد (evc_get_).
# ══════════════════════════════════════════════════════════
def self_issue_allowed():
    """
    🔓 آیا کاربر اجازه دارد خودش گواهینامه صادر کند؟

    پیش‌فرض «۰» یعنی بسته. از پنل قابل روشن‌کردن است، ولی
    توصیه می‌شود بسته بماند.
    """
    return get_setting("cert_self_issue", "0") == "1"


def deny_self_issue(cid, extra=""):
    """🌱 پیام مهربان وقتی کاربر خودش خواست صادر کند"""
    txt = get_setting(
        "cert_self_issue_msg",
        "گواهینامه‌ها را برگزارکننده صادر می‌کند 💚")
    lines = ["🌱 گواهینامه در راه است", "━━━━━━━━━━━━━━", "",
             txt, ""]
    if extra:
        lines += [extra, ""]
    lines += ["📬 به‌محض صدور، همین‌جا خبرتان می‌کنیم.",
              "", "💡 گواهینامه‌های صادرشده‌تان در",
              "   «🎓 گواهینامه‌های من» است."]
    return send(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🎓 گواهینامه‌های من",
          "callback_data": "u_my_certs"}],
        [{"text": "🔙 منوی اصلی", "callback_data": "back_main"}]]})


def send_cert_files(to_uid, cert, ev=None):
    """
    📤 ارسال گواهینامه به کاربر — با فایل واقعی.

    🔴 رفع باگ ۱: این تابع همان کاری را می‌کند که صدور گروهی
       نمی‌کرد — فرستادن PNG و PDF واقعی، نه متن خام.

    🔴 باگ رفع‌شده (فاز ۳۷) — «گواهینامه به دست کاربر نمی‌رسید»:
       سه صداکننده به‌جای رکورد، **شمارهٔ** گواهینامه می‌دادند:

           send_cert_files(cid, cert_id)      ❌ eventcert.py:694
           send_cert_files(cid, row["cert_id"])  ❌ certbatch:1020
           send_cert_files(cid, cert_id)      ❌ certbatch:1085

       نتیجه: `AttributeError: 'int' object has no attribute
       'get'` — استثنا در بلوک try خورده می‌شد و کاربر هیچ
       فایلی نمی‌گرفت. در گواهینامهٔ رویداد و لینک اکسل
       سکوت کامل بود.

       حالا هر دو شکل را می‌پذیریم: رکورد کامل یا فقط شناسه.
    """
    # 🔢 اگر شناسهٔ عددی داده شد، خودمان رکورد را می‌خوانیم
    if isinstance(cert, (int, float, str)):
        try:
            cert = db_execute("SELECT * FROM certificates WHERE id=?",
                              (int(cert),), fetch="one")
        except (TypeError, ValueError):
            cert = None
    if not cert:
        log("⚠️ send_cert_files: گواهینامه یافت نشد")
        return False

    # 🎉 اگر رویداد داده نشد ولی گواهینامه به رویدادی وصل است
    if ev is None and cert.get("event_id"):
        try:
            from events import get_event
            ev = get_event(cert["event_id"]) or {}
        except Exception:
            ev = {}

    title = (ev or {}).get("title") or ""
    cap_t = get_setting("cert_msg_title", "🎓 گواهینامه شما صادر شد!")
    note = get_setting("cert_msg_note",
                       "این گواهینامه با کیوآرکد قابل اعتبارسنجی است 💚")
    sent = False

    png = cert.get("png_path")
    if png and Path(png).exists():
        send_photo(to_uid, png, f"🎓 {title}"[:200])
        sent = True
    pdf = cert.get("pdf_path")
    if pdf and Path(pdf).exists():
        send_document(to_uid, pdf, f"📄 گواهینامه — {title}"[:200])
        sent = True
    if not sent:
        dx = cert.get("docx_path")
        if dx and Path(dx).exists():
            send_document(to_uid, dx, f"📄 گواهینامه — {title}"[:200])
            sent = True

    lines = [cap_t, "━━━━━━━━━━━━━━", ""]
    if title:
        lines += [f"🎉 {title}", ""]
    if not sent:
        lines += [str(cert.get("template") or ""), ""]
    lines += [f"🔖 شماره: {cert.get('serial')}"]

    # 📅 تاریخ صدور و اعتبار — شمسی (فاز ۳۶)
    #    🔴 قبلاً هیچ تاریخی در پیام نبود و هرجا بود میلادی خام
    #       نشان داده می‌شد: «2026-07-29».
    _iss = cert.get("issued_on") or cert.get("issued_at")
    if _iss:
        lines.append(f"📅 تاریخ صدور: {_jd.fmt(_iss, 'long')}")
    _exp = cert.get("expires_on")
    if _exp:
        _left = _jd.days_left(_exp)
        if _left < 0:
            lines.append(f"⏳ اعتبار: {_jd.fmt(_exp, 'long')} (منقضی شده)")
        else:
            lines.append(f"⏳ اعتبار تا: {_jd.fmt(_exp, 'long')}")
    if note:
        lines += ["", f"💡 {note}"]

    kb = {"inline_keyboard": [
        [{"text": "🎓 گواهینامه‌های من", "callback_data": "u_my_certs"}]]}
    send(to_uid, "\n".join(lines), kb)
    return sent


# ══════════════════════════════════════════════════════════
# 🖥️ پنل ادمین — مرکز صدور
# ══════════════════════════════════════════════════════════
def _guard(cid, uid):
    if not _is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    return True


def show_hub(cid, uid, eid):
    """
    🎓 مرکز صدور گواهینامه رویداد.

    🎯 «صدور گواهینامه گروهی رویداد خلاصه‌ست، بخشش رو کامل کن»
       قبلاً فقط یک دکمه «بله صادر کن» بود. حالا یک مرکز کامل.
    """
    if not _guard(cid, uid):
        return
    eid = _eid(eid)
    if not eid:
        return send(cid, "❌ رویداد نامعتبر")
    from events import get_event
    import certgen

    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    ok, no, ctext = eligible(eid, ev)
    done = db_scalar("SELECT COUNT(*) FROM certificates "
                     "WHERE event_id=? AND COALESCE(revoked,0)=0",
                     (eid,)) or 0
    total_s = sessions_count(eid)
    tpl = template_of(eid)
    st = certgen.engine_status()
    params = get_cfg(eid).get("params") or {}
    n_param = len([1 for v in params.values() if str(v).strip()])

    lines = ["🎓 مرکز صدور گروهی گواهینامه", "━━━━━━━━━━━━━━", "",
             f"🎉 {ev.get('title')}", ""]

    if not ev.get("has_certificate"):
        lines += ["⚠️ گواهینامه این رویداد خاموش است",
                  "   از «⚙️ قابلیت‌ها» روشنش کنید", ""]

    lines += ["📋 وضعیت:",
              f"├── 📄 قالب: {tpl.get('name') if tpl else '— متن ساده —'}",
              f"├── ✅ شرط: {ctext}",
              f"├── 📚 جلسات رویداد: {total_s}",
              f"├── ✏️ پارامتر دستی: {n_param}",
              f"├── 👥 واجد شرایط: {len(ok)}",
              f"├── ⛔ رد شده: {len(no)}",
              f"└── 🎓 صادرشده: {done}", ""]

    if not tpl:
        lines += ["💡 هنوز قالب ورد ندارید — گواهینامه به‌صورت",
                  "   متنی ساده صادر می‌شود.", ""]
    elif not (st["libreoffice"] or st.get("word")):
        lines += ["🟡 موتور داخلی فعال است (طرح ساده‌تر)", ""]

    # 💡 نکتهٔ هوشمند: رویداد جلسه دارد ولی شرط «فقط ثبت‌نام» است
    if total_s and condition_of(eid, ev) == "registered":
        lines += ["💡 این رویداد جلسه دارد.",
                  "   می‌خواهید فقط به حاضرین گواهینامه بدهید؟",
                  "   از «✅ شرط دریافت» تغییرش دهید.", ""]

    remain = len([r for r in ok if not _has_cert(eid, r["bale_user_id"])])
    if remain:
        lines += [f"🌱 {remain} نفر منتظر گواهینامه‌اند", ""]
    elif ok:
        lines += ["🎉 همه واجدین شرایط گواهینامه گرفته‌اند 💚", ""]

    lines += ["━━━━━━━━━━━━━━", "از کجا شروع کنیم؟"]

    btns = [
        [{"text": f"📄 انتخاب قالب "
                  f"({tpl.get('name')[:14] if tpl else 'ندارد'})",
          "callback_data": f"ci_tpl_{eid}"}],
        [{"text": f"✅ شرط دریافت ({ctext[:18]})",
          "callback_data": f"ci_cond_{eid}"}],
        [{"text": f"✏️ پارامترهای گواهینامه ({n_param})",
          "callback_data": f"ci_par_{eid}"}],
        [{"text": f"👥 واجدین شرایط ({len(ok)})",
          "callback_data": f"ci_ok_{eid}_0"}],
    ]
    if no:
        btns.append([{"text": f"⛔ رد شده‌ها ({len(no)})",
                      "callback_data": f"ci_no_{eid}_0"}])
    btns += [
        [{"text": "👁️ پیش‌نمایش (تست با یک نفر)",
          "callback_data": f"ci_prev_{eid}"}],
    ]
    if remain:
        btns.append([{"text": f"🎓 صدور برای {remain} نفر",
                      "callback_data": f"ci_run_{eid}"}])
    if done:
        btns.append([{"text": f"📜 مدیریت صادرشده‌ها ({done})",
                      "callback_data": f"ci_done_{eid}_0"}])
    btns += [
        # 🏛️ فاز ۳۷ — میان‌بر به مرکز صدور
        #    «صدور گواهی که تو رویداد هست هم کامل بروز بشه»
        #
        #    ⚠️ اینجا گذاشته شد نه در پنل رویداد: آن صفحه از
        #       سقف ۱۰ دکمه رد می‌شد (تست فاز ۲۳ این را می‌گیرد)
        #       و اینجا هم جای منطقی‌تری است.
        [{"text": "🏛️ صدور از مرکز (ساخت تنبل + پیش‌نمایش)",
          "callback_data": f"cc_ev_{eid}"}],
        [{"text": "📊 آمار و گزارش", "callback_data": f"ci_stat_{eid}"}],
        [{"text": "🔙 رویداد", "callback_data": f"ev_view_{eid}"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def _has_cert(eid, bu):
    return bool(db_scalar("SELECT COUNT(*) FROM certificates "
                          "WHERE event_id=? AND bale_user_id=? "
                          "AND COALESCE(revoked,0)=0", (eid, bu)))


# ─────────── 📄 انتخاب قالب ───────────
def show_templates(cid, uid, eid):
    """📄 انتخاب قالب برای این رویداد"""
    if not _guard(cid, uid):
        return
    eid = _eid(eid)
    if not eid:
        return send(cid, "❌ رویداد نامعتبر")
    import certgen

    rows = db_execute("SELECT * FROM cert_templates WHERE is_active=1 "
                      "ORDER BY is_default DESC, id DESC",
                      fetch="all") or []
    cur = cfg_get(eid, "template_id")

    lines = ["📄 قالب گواهینامه این رویداد", "━━━━━━━━━━━━━━", ""]
    if not rows:
        lines += ["📭 هنوز قالبی نساخته‌اید.", "",
                  "💡 یک فایل ورد با جای خالی {نام} بفرستید تا",
                  "   گواهینامه‌ها با طرح دلخواه شما ساخته شوند.", "",
                  "تا آن موقع، گواهینامه متنی ساده صادر می‌شود."]
    else:
        lines += ["هر رویداد می‌تواند قالب خودش را داشته باشد:", ""]
        for r in rows:
            try:
                phs = json.loads(r.get("placeholders") or "[]")
            except (json.JSONDecodeError, TypeError):
                phs = []
            mark = "🔘" if str(cur) == str(r["id"]) else "▫️"
            dflt = " ⭐" if r.get("is_default") else ""
            kind = "📄" if (r.get("kind") or "docx") == "docx" else "🖼️"
            lines.append(f"{mark} {kind} {r.get('name')}{dflt} "
                         f"— {len(phs)} پارامتر")
        lines += ["", "⭐ = پیش‌فرض کل ربات"]

    btns = []
    if not cur:
        btns.append([{"text": "🔘 پیش‌فرض ربات (فعلی)",
                      "callback_data": f"ci_setpl_{eid}_0"}])
    else:
        btns.append([{"text": "▫️ برگرد به پیش‌فرض ربات",
                      "callback_data": f"ci_setpl_{eid}_0"}])
    for r in rows:
        mark = "🔘" if str(cur) == str(r["id"]) else "▫️"
        btns.append([{"text": f"{mark} {r.get('name')}"[:34],
                      "callback_data": f"ci_setpl_{eid}_{r['id']}"}])
    btns += [[{"text": "➕ ساخت قالب جدید", "callback_data": "ct_panel"}],
             [{"text": "🔙 مرکز صدور", "callback_data": f"cert_bulk_{eid}"}]]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_template(cid, uid, eid, tid):
    if not _guard(cid, uid):
        return
    import certgen
    if tid:
        t = certgen.get_template(tid)
        if not t:
            return send(cid, "❌ قالب یافت نشد")
        cfg_set(eid, "template_id", int(tid), uid)
        send(cid, f"✅ قالب «{t.get('name')}» انتخاب شد 💚")
    else:
        c = get_cfg(eid)
        c.pop("template_id", None)
        save_cfg(eid, c, uid)
        send(cid, "✅ به قالب پیش‌فرض ربات برگشت")
    log_action(uid, "cert_setting_changed",
               {"event_id": eid, "template_id": tid})
    return show_templates(cid, uid, eid)


# ─────────── ✅ شرط دریافت ───────────
def show_conditions(cid, uid, eid):
    """✅ شرط دریافت گواهینامه"""
    if not _guard(cid, uid):
        return
    eid = _eid(eid)
    if not eid:
        return send(cid, "❌ رویداد نامعتبر")
    from events import get_event
    ev = get_event(eid)
    cur = condition_of(eid, ev)
    total_s = sessions_count(eid)
    ok, no, _ = eligible(eid, ev)

    lines = ["✅ شرط دریافت گواهینامه", "━━━━━━━━━━━━━━", "",
             "چه کسی گواهینامه بگیرد؟", ""]
    for k, c in CONDITIONS.items():
        mark = "🔘" if k == cur else "▫️"
        lines.append(f"{mark} {c['icon']} {c['name']}")
        lines.append(f"      {c['desc']}")
    lines += ["", "━━━━━━━━━━━━━━",
              f"📚 جلسات این رویداد: {total_s}",
              f"👥 با شرط فعلی: {len(ok)} واجد · {len(no)} رد"]
    if total_s == 0 and cur in ("attended", "sessions", "percent", "all"):
        lines += ["", "⚠️ هنوز جلسه‌ای تعریف نکرده‌اید!",
                  "   با این شرط هیچ‌کس گواهینامه نمی‌گیرد.",
                  "   اول از «✋ حضور و غیاب» جلسه بسازید."]

    lines += ["", f"📄 غیبت موجه به‌جای حضور: "
                  f"{'🟢 بله' if excused_counts() else '🔴 خیر'}"]

    btns = []
    for k, c in CONDITIONS.items():
        mark = "🔘" if k == cur else "▫️"
        btns.append([{"text": f"{mark} {c['icon']} {c['name']}"[:34],
                      "callback_data": f"ci_setc_{eid}_{k}"}])
    btns.append([{"text": f"📄 غیبت موجه حساب شود: "
                          f"{'✅' if excused_counts() else '❌'}",
                  "callback_data": f"ci_exc_{eid}"}])
    if cur == "sessions":
        btns.append([{"text": f"🔢 تعداد جلسه لازم: "
                              f"{min_sessions_of(eid, ev)}",
                      "callback_data": f"ci_pset_{eid}_min_sessions"}])
    if cur == "percent":
        btns.append([{"text": f"📊 درصد لازم: {min_percent_of(eid)}٪",
                      "callback_data": f"ci_pset_{eid}_min_percent"}])
    if cur == "manual":
        btns.append([{"text": "👤 انتخاب نفرات",
                      "callback_data": f"ci_pick_{eid}_0"}])
    btns.append([{"text": "🔙 مرکز صدور",
                  "callback_data": f"cert_bulk_{eid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_excused(cid, uid, eid):
    """📄 روشن/خاموش کردن «غیبت موجه = حضور»"""
    if not _guard(cid, uid):
        return
    cur = excused_counts()
    set_setting("cert_excused_counts", "0" if cur else "1",
                "غیبت موجه به‌جای حضور", "certificate", uid)
    send(cid, "📄 غیبت موجه دیگر حساب نمی‌شود" if cur
              else "📄 غیبت موجه مثل حضور حساب می‌شود 💚")
    return show_conditions(cid, uid, eid)


def set_condition(cid, uid, eid, cond):
    if not _guard(cid, uid):
        return
    if cond not in CONDITIONS:
        return send(cid, "❌ نامعتبر")
    cfg_set(eid, "condition", cond, uid)
    db_execute("UPDATE events SET cert_condition=? WHERE id=?",
               (cond, eid))
    log_action(uid, "cert_setting_changed",
               {"event_id": eid, "condition": cond})
    send(cid, f"✅ شرط: {CONDITIONS[cond]['name']}")
    return show_conditions(cid, uid, eid)


# ─────────── ✏️ پارامترها ───────────
def show_params(cid, uid, eid):
    """
    ✏️ پارامترهای دلخواه گواهینامه این رویداد.

    🎯 «تغییر پارامترها» — ادمین می‌تواند برای هر رویداد
       مقدار دلخواه بگذارد که روی مقدار خودکار می‌نشیند.
    """
    if not _guard(cid, uid):
        return
    eid = _eid(eid)
    if not eid:
        return send(cid, "❌ رویداد نامعتبر")
    from events import get_event
    import certgen
    ev = get_event(eid) or {}
    params = get_cfg(eid).get("params") or {}

    # مقدار خودکار برای مقایسه
    auto = build_for(eid, uid, "NMONE-0000", ev)

    lines = ["✏️ پارامترهای گواهینامه", "━━━━━━━━━━━━━━", "",
             f"🎉 {ev.get('title')}", "",
             "اگر خالی بگذارید، مقدار خودکار استفاده می‌شود:", ""]
    btns = []
    for key, icon, name, hint in EVENT_PARAMS:
        v = str(params.get(key) or "").strip()
        a = str(auto.get(key) or "").strip()
        if v:
            lines.append(f"✏️ {icon} {name}: {v}")
        elif a:
            lines.append(f"🔄 {icon} {name}: {a}  (خودکار)")
        else:
            lines.append(f"⚪ {icon} {name}: —")
        btns.append([{"text": f"{icon} {name}: {(v or a or '—')[:12]}"[:34],
                      "callback_data": f"ci_pset_{eid}_{key}"}])

    lines += ["", "✏️ = دستی شما   🔄 = خودکار   ⚪ = خالی", "",
              "💡 قالب ورد شما ۷۲ پارامتر می‌شناسد — این‌ها",
              "   پرکاربردترین‌هایند."]

    if params:
        btns.append([{"text": "🧹 پاک کردن همه دستی‌ها",
                      "callback_data": f"ci_pclr_{eid}"}])
    btns += [[{"text": "📋 راهنمای همه پارامترها",
               "callback_data": "ct_help"}],
             [{"text": "🔙 مرکز صدور", "callback_data": f"cert_bulk_{eid}"}]]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_param(cid, uid, eid, key):
    """✏️ ورود مقدار یک پارامتر"""
    if not _guard(cid, uid):
        return
    row = next((r for r in EVENT_PARAMS if r[0] == key), None)
    special = {"min_sessions": ("🔢", "حداقل جلسه لازم",
                                "عدد بفرستید — مثال: 3"),
               "min_percent": ("📊", "حداقل درصد حضور",
                               "عددی بین ۱ تا ۱۰۰ — مثال: 80")}
    if key in special:
        icon, name, hint = special[key]
    elif row:
        _, icon, name, hint = row
    else:
        return send(cid, "❌ نامعتبر")

    cur = ""
    if key in special:
        cur = str(min_sessions_of(eid) if key == "min_sessions"
                  else min_percent_of(eid))
    else:
        cur = str((get_cfg(eid).get("params") or {}).get(key) or "")

    set_state(uid, STATE_CI_PARAM, {"eid": eid, "key": key}, merge=False)
    txt = [f"✏️ {icon} {name}", "━━━━━━━━━━━━━━", "",
           f"📄 فعلی: {cur or '—'}", ""]
    if hint:
        txt += [f"💡 {hint}", ""]
    txt += ["مقدار جدید را بنویسید:",
            "💡 برای خالی کردن، «-» بفرستید"]
    send(cid, "\n".join(txt), kb_cancel())


def handle_param(message):
    """📥 دریافت مقدار پارامتر"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    raw = (message.get("text") or "").strip()
    d = get_state_data(uid)
    eid = d.get("eid")
    key = d.get("key")

    if raw in (BTN_BACK, "🔙 بازگشت", "❌ انصراف", "لغو"):
        clear_state(uid)
        send(cid, "❌ لغو شد", kb_remove())
        if key in ("min_sessions", "min_percent"):
            return show_conditions(cid, uid, eid)
        return show_params(cid, uid, eid)

    if not eid or not key:
        clear_state(uid)
        return send(cid, "❌ نامعتبر", kb_remove())

    # 🔢 مقادیر عددی شرط
    if key in ("min_sessions", "min_percent"):
        digits = "".join(ch for ch in normalize_digits(raw)
                         if ch.isdigit())
        if not digits:
            return send(cid, "⚠️ فقط عدد بفرستید:", kb_cancel())
        v = int(digits)
        if key == "min_percent":
            v = max(1, min(100, v))
        else:
            v = max(0, min(999, v))
        cfg_set(eid, key, v, uid)
        if key == "min_sessions":
            db_execute("UPDATE events SET cert_min_sessions=? WHERE id=?",
                       (v, eid))
        clear_state(uid)
        send(cid, f"✅ ذخیره شد: {v}", kb_remove())
        return show_conditions(cid, uid, eid)

    # ✏️ پارامتر متنی
    c = get_cfg(eid)
    params = c.get("params") or {}
    if raw == "-":
        params.pop(key, None)
        msg_ok = "✅ پاک شد — مقدار خودکار استفاده می‌شود"
    else:
        params[key] = raw[:200]
        msg_ok = f"✅ ذخیره شد: {raw[:60]}"
    c["params"] = params
    save_cfg(eid, c, uid)
    clear_state(uid)
    log_action(uid, "cert_setting_changed", {"event_id": eid, "param": key})
    send(cid, msg_ok, kb_remove())
    return show_params(cid, uid, eid)


def clear_params(cid, uid, eid):
    if not _guard(cid, uid):
        return
    c = get_cfg(eid)
    c["params"] = {}
    save_cfg(eid, c, uid)
    send(cid, "🧹 همه پارامترهای دستی پاک شدند")
    return show_params(cid, uid, eid)


# ─────────── 👥 فهرست‌ها ───────────
def show_list(cid, uid, eid, kind="ok", page=0):
    """👥 فهرست واجدین / ردشده‌ها"""
    if not _guard(cid, uid):
        return
    from events import get_event
    ev = get_event(eid)
    ok, no, ctext = eligible(eid, ev)
    rows = ok if kind == "ok" else no
    per = 8
    pages = max(1, (len(rows) + per - 1) // per)
    page = max(0, min(page, pages - 1))
    chunk = rows[page * per:(page + 1) * per]

    if kind == "ok":
        head = f"👥 واجدین شرایط ({len(rows)})"
    else:
        head = f"⛔ رد شده‌ها ({len(rows)})"
    lines = [head, "━━━━━━━━━━━━━━", "", f"✅ شرط: {ctext}", ""]

    if not rows:
        lines.append("📭 کسی در این فهرست نیست")
        if kind == "ok":
            lines += ["", "💡 شاید شرط سخت‌گیرانه است؟",
                      "   یا هنوز حضوری ثبت نشده."]
    for i, r in enumerate(chunk, page * per + 1):
        nm = _name_of(r)
        has = _has_cert(eid, r["bale_user_id"])
        mark = "🎓" if has else ("✅" if kind == "ok" else "⛔")
        lines.append(f"{mark} {i}. {nm}")
        det = f"      ✋ {r['present_n']}"
        if r["total_s"]:
            det += f"/{r['total_s']} جلسه ({r['percent']}٪)"
        else:
            det += " جلسه"
        lines.append(det)
        if kind == "no" and r.get("why"):
            lines.append(f"      💬 {r['why']}")

    btns = []
    for r in chunk:
        nm = _name_of(r)
        has = _has_cert(eid, r["bale_user_id"])
        row = [{"text": f"{'🎓' if has else '📤'} {nm}"[:28],
                "callback_data": f"ci_one_{eid}_{r['bale_user_id']}"}]
        btns.append(row)

    nav = []
    if page > 0:
        nav.append({"text": "◀️", "callback_data":
                    (f"ci_ok_{eid}_{page-1}" if kind == "ok"
                     else f"ci_no_{eid}_{page-1}")})
    nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
    if page < pages - 1:
        nav.append({"text": "▶️", "callback_data":
                    (f"ci_ok_{eid}_{page+1}" if kind == "ok"
                     else f"ci_no_{eid}_{page+1}")})
    if len(nav) > 1:
        btns.append(nav)

    if kind == "ok" and rows:
        n_rem = len([r for r in rows
                     if not _has_cert(eid, r["bale_user_id"])])
        if n_rem:
            btns.append([{"text": f"🎓 صدور برای همه ({n_rem})",
                          "callback_data": f"ci_run_{eid}"}])
    if kind == "no" and rows:
        btns.append([{"text": "✅ تغییر شرط",
                      "callback_data": f"ci_cond_{eid}"}])
    btns.append([{"text": "🔙 مرکز صدور",
                  "callback_data": f"cert_bulk_{eid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_one(cid, uid, eid, bale_uid):
    """👤 کارت یک نفر — صدور تکی"""
    if not _guard(cid, uid):
        return
    from events import get_event
    ev = get_event(eid)
    u = get_user(bale_uid) or {}
    nm = f"{u.get('first_name') or ''} " \
         f"{u.get('last_name') or ''}".strip() or "بدون نام"

    total_s = sessions_count(eid)
    n = db_scalar("SELECT COUNT(DISTINCT session_id) FROM "
                  "attendance_records WHERE event_id=? AND bale_user_id=? "
                  "AND status IN ('present','late')",
                  (eid, bale_uid)) or 0
    pct = int(n * 100 / total_s) if total_s else 0
    cert = db_execute("SELECT * FROM certificates WHERE event_id=? "
                      "AND bale_user_id=?", (eid, bale_uid), fetch="one")

    lines = [f"👤 {nm}", "━━━━━━━━━━━━━━", ""]
    if u.get("national_id"):
        lines.append(f"🆔 کد ملی: {u['national_id']}")
    if u.get("mobile"):
        lines.append(f"📱 {u['mobile']}")
    lines += ["", f"✋ حضور: {n} از {total_s} جلسه ({pct}٪)", ""]

    if cert:
        rev = cert.get("revoked")
        lines += [f"{'🚫 باطل‌شده' if rev else '🎓 گواهینامه دارد'}",
                  f"🔖 شماره: {cert.get('serial')}",
                  f"📅 {_jd.fmt(cert.get('issued_at'), 'datetime')}"]
        f_ok = []
        for k, lbl in (("png_path", "🖼️ تصویر"), ("pdf_path", "📄 PDF"),
                       ("docx_path", "📝 ورد")):
            p = cert.get(k)
            if p and Path(p).exists():
                f_ok.append(lbl)
        lines.append(f"📎 فایل‌ها: {'، '.join(f_ok) if f_ok else 'پاک شده'}")
    else:
        lines.append("⚪ هنوز گواهینامه ندارد")

    btns = []
    if cert:
        btns += [
            [{"text": "📤 ارسال دوباره به کاربر",
              "callback_data": f"ci_resend_{eid}_{bale_uid}"}],
            [{"text": "🔄 بازتولید (با قالب فعلی)",
              "callback_data": f"ci_regen_{eid}_{bale_uid}"}],
        ]
        if cert.get("revoked"):
            btns.append([{"text": "♻️ برگرداندن از ابطال",
                          "callback_data": f"ci_unrev_{eid}_{bale_uid}"}])
        else:
            btns.append([{"text": "🚫 ابطال گواهینامه",
                          "callback_data": f"ci_rev_{eid}_{bale_uid}"}])
    else:
        btns.append([{"text": "🎓 صدور همین حالا",
                      "callback_data": f"ci_mk_{eid}_{bale_uid}"}])
    btns.append([{"text": "🔙 فهرست",
                  "callback_data": f"ci_ok_{eid}_0"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def issue_single(cid, uid, eid, bale_uid, force=False):
    """🎓 صدور تکی از پنل"""
    if not _guard(cid, uid):
        return
    from events import get_event
    ev = get_event(eid)
    send(cid, "⏳ در حال ساخت گواهینامه...")
    cert, err = issue_one(eid, bale_uid, uid, ev, force=force)
    if not cert:
        return send(cid, f"❌ ناموفق\n\n{err}", {"inline_keyboard": [
            [{"text": "🔙 بازگشت",
              "callback_data": f"ci_one_{eid}_{bale_uid}"}]]})
    msg = "✅ صادر و ارسال شد 💚"
    if err:
        msg += f"\n\n💡 {err}"
    send(cid, msg)
    return show_one(cid, uid, eid, bale_uid)


def resend(cid, uid, eid, bale_uid):
    if not _guard(cid, uid):
        return
    from events import get_event
    cert = db_execute("SELECT * FROM certificates WHERE event_id=? "
                      "AND bale_user_id=?", (eid, bale_uid), fetch="one")
    if not cert:
        return send(cid, "❌ گواهینامه‌ای نیست")
    okf = send_cert_files(bale_uid, cert, get_event(eid))
    send(cid, "📤 دوباره فرستاده شد 💚" if okf else
              "📤 متن فرستاده شد (فایل پاک شده بود)")
    return show_one(cid, uid, eid, bale_uid)


def revoke(cid, uid, eid, bale_uid, undo=False):
    """🚫 ابطال / بازگردانی"""
    if not _guard(cid, uid):
        return
    db_execute("UPDATE certificates SET revoked=? WHERE event_id=? "
               "AND bale_user_id=?", (0 if undo else 1, eid, bale_uid))
    log_action(uid, "cert_revoked" if not undo else "cert_restored",
               {"event_id": eid, "user": bale_uid})
    # 🪞 وضعیت جدید را به ثبت مشترک سرور هم برسان (بهترین‌تلاش)
    try:
        import shared_certificates as _sc
        for _row in db_execute("SELECT id FROM certificates WHERE event_id=? "
                               "AND bale_user_id=?", (eid, bale_uid),
                               fetch="all") or []:
            _sc.sync_after_change(_row.get("id"))
    except Exception:
        pass
    send(cid, "♻️ از ابطال خارج شد" if undo else
              "🚫 باطل شد — اعتبارسنجی دیگر تأیید نمی‌کند")
    return show_one(cid, uid, eid, bale_uid)


# ─────────── 👁️ پیش‌نمایش ───────────
def preview(cid, uid, eid):
    """
    👁️ پیش‌نمایش — با اولین واجد شرایط تست می‌کند.

    🎯 قبل از صدور برای ۵۰ نفر، ادمین باید ببیند نتیجه چطور
       می‌شود. این گواهینامه ذخیره نمی‌شود.
    """
    if not _guard(cid, uid):
        return
    eid = _eid(eid)
    if not eid:
        return send(cid, "❌ رویداد نامعتبر")
    from events import get_event
    import certgen
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")

    ok, _no, _c = eligible(eid, ev)
    tpl = template_of(eid)

    if not tpl:
        return send_or_edit(cid, (
            "👁️ پیش‌نمایش\n━━━━━━━━━━━━━━\n\n"
            "📭 قالبی انتخاب نشده — گواهینامه متنی ساده\n"
            "   صادر می‌شود.\n\n"
            "💡 برای گواهینامه گرافیکی، یک فایل ورد بفرستید."
        ), {"inline_keyboard": [
            [{"text": "📄 انتخاب قالب", "callback_data": f"ci_tpl_{eid}"}],
            [{"text": "🔙 مرکز صدور",
              "callback_data": f"cert_bulk_{eid}"}]]})

    send(cid, "⏳ در حال ساخت پیش‌نمایش...")
    sample = ok[0] if ok else None
    bu = sample["bale_user_id"] if sample else uid
    mp = build_for(eid, bu, "PREVIEW-0000", ev)
    if not sample:
        mp["name"] = "نمونه — امیر نعمتی"
        mp["national_id"] = "0010247165"

    try:
        res = certgen.generate(mp, tpl)
    except Exception as e:
        return send(cid, f"❌ خطا در ساخت: {user_error_message(e)}")

    lines = ["👁️ پیش‌نمایش گواهینامه", "━━━━━━━━━━━━━━", "",
             f"📄 قالب: {tpl.get('name')}",
             f"👤 نمونه: {mp.get('name')}", ""]
    if res.get("png") or res.get("pdf"):
        lines.append("✅ ساخته شد — پایین ببینید")
    else:
        lines.append("⚠️ فایل ساخته نشد")
    if res.get("error"):
        lines += ["", f"💡 {res['error']}"]
    lines += ["", "🌱 این نسخه ذخیره نشد — فقط برای دیدن."]

    if res.get("png") and Path(res["png"]).exists():
        send_photo(cid, res["png"], "👁️ پیش‌نمایش گواهینامه")
    if res.get("pdf") and Path(res["pdf"]).exists():
        send_document(cid, res["pdf"], "👁️ پیش‌نمایش (PDF)")

    # پاکسازی فایل‌های پیش‌نمایش
    for k in ("png", "pdf", "docx"):
        p = res.get(k)
        if p:
            try:
                Path(p).unlink(missing_ok=True)
            except OSError:
                pass

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔄 دوباره", "callback_data": f"ci_prev_{eid}"}],
        [{"text": "✏️ تغییر پارامترها",
          "callback_data": f"ci_par_{eid}"}],
        [{"text": "📄 تغییر قالب", "callback_data": f"ci_tpl_{eid}"}],
        [{"text": "🔙 مرکز صدور", "callback_data": f"cert_bulk_{eid}"}]]},
        force_new=True)


# ─────────── 🎓 صدور گروهی ───────────
def confirm_run(cid, uid, eid):
    """🎓 تأیید قبل از صدور گروهی"""
    if not _guard(cid, uid):
        return
    eid = _eid(eid)
    if not eid:
        return send(cid, "❌ رویداد نامعتبر")
    from events import get_event
    import certgen
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")

    ok, no, ctext = eligible(eid, ev)
    remain = [r for r in ok if not _has_cert(eid, r["bale_user_id"])]
    tpl = template_of(eid)
    st = certgen.engine_status()

    if not remain:
        return send_or_edit(cid, (
            "🎓 صدور گروهی\n━━━━━━━━━━━━━━\n\n"
            "🎉 همه واجدین شرایط گواهینامه دارند!\n\n"
            f"✅ شرط: {ctext}\n"
            f"👥 واجد شرایط: {len(ok)}"
        ), {"inline_keyboard": [
            [{"text": "🔄 بازتولید همه",
              "callback_data": f"ci_regall_{eid}"}],
            [{"text": "🔙 مرکز صدور",
              "callback_data": f"cert_bulk_{eid}"}]]})

    lines = ["🎓 تأیید صدور گروهی", "━━━━━━━━━━━━━━", "",
             f"🎉 {ev.get('title')}", "",
             f"✅ شرط: {ctext}",
             f"📄 قالب: {tpl.get('name') if tpl else 'متن ساده'}",
             f"👥 گیرندگان: {len(remain)} نفر"]
    if no:
        lines.append(f"⛔ رد شده: {len(no)} نفر")
    lines += ["", "این افراد گواهینامه می‌گیرند:"]
    for r in remain[:7]:
        lines.append(f"   • {_name_of(r)} — {r['present_n']} جلسه")
    if len(remain) > 7:
        lines.append(f"   … و {len(remain) - 7} نفر دیگر")

    if not tpl:
        lines += ["", "⚠️ بدون قالب — گواهینامه متنی ساده می‌شود"]
    elif not (st["libreoffice"] or st.get("word")):
        lines += ["", "🟡 موتور داخلی — طرح ورد ساده‌تر می‌شود"]

    est = max(1, int(len(remain) * 1.5 / 60))
    lines += ["", f"⏱️ حدود {est} دقیقه طول می‌کشد",
              "", "شروع کنیم؟ 🌱"]

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": f"🎓 بله، صدور برای {len(remain)} نفر",
          "callback_data": f"ci_go_{eid}"}],
        [{"text": "👁️ اول پیش‌نمایش ببینم",
          "callback_data": f"ci_prev_{eid}"}],
        [{"text": "❌ انصراف", "callback_data": f"cert_bulk_{eid}"}]]})


def run_bulk(cid, uid, eid, regen=False):
    """
    🎓 صدور گروهی واقعی.

    🔴 رفع باگ ۱: حالا issue_one صدا زده می‌شود که فایل واقعی
       PNG/PDF را می‌فرستد — نه متن خام.
    """
    if not _guard(cid, uid):
        return
    from events import get_event
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ یافت نشد")

    ok, _no, ctext = eligible(eid, ev)
    targets = ok if regen else [r for r in ok
                                if not _has_cert(eid, r["bale_user_id"])]
    if not targets:
        return send(cid, "📭 کسی برای صدور نیست")

    send(cid, f"⏳ صدور برای {len(targets)} نفر...\n"
              f"🌱 لطفاً صبر کنید — پیام پایانی می‌آید.")

    made = failed = 0
    errs = []
    t0 = time.time()
    for i, r in enumerate(targets, 1):
        bu = r["bale_user_id"]
        try:
            cert, err = issue_one(eid, bu, uid, ev, row=r,
                                  send_to_user=True, force=regen)
            if cert:
                made += 1
            else:
                failed += 1
                if err and len(errs) < 3:
                    errs.append(f"{_name_of(r)}: {err[:60]}")
        except Exception as e:
            failed += 1
            log(f"⚠️ صدور گواهینامه {bu}: {e}")
            if len(errs) < 3:
                errs.append(f"{_name_of(r)}: {user_error_message(e)}")
        # نفس کشیدن — سقف ارسال بله
        time.sleep(0.08)
        if i % 15 == 0:
            send(cid, f"⏳ {i} از {len(targets)}...")

    dt = int(time.time() - t0)
    lines = ["✅ صدور گروهی تمام شد", "━━━━━━━━━━━━━━", "",
             f"🎓 صادر شد: {made}"]
    if failed:
        lines.append(f"⚠️ ناموفق: {failed}")
    lines += [f"⏱️ زمان: {dt} ثانیه", ""]
    if errs:
        lines += ["💬 چند نمونه خطا:"]
        for e in errs:
            lines.append(f"   • {e}")
        lines.append("")
    if made:
        lines.append("💚 گواهینامه‌ها با فایل تصویر و PDF")
        lines.append("   برای کاربران فرستاده شد.")

    log_action(uid, "cert_bulk_issued",
               {"event_id": eid, "made": made, "failed": failed})
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "📜 مدیریت صادرشده‌ها",
          "callback_data": f"ci_done_{eid}_0"}],
        [{"text": "🔙 مرکز صدور", "callback_data": f"cert_bulk_{eid}"}]]})


# ─────────── 📜 صادرشده‌ها ───────────
def show_issued(cid, uid, eid, page=0):
    """📜 مدیریت گواهینامه‌های صادرشده"""
    if not _guard(cid, uid):
        return
    per = 8
    total = db_scalar("SELECT COUNT(*) FROM certificates WHERE event_id=?",
                      (eid,)) or 0
    rows = db_execute("""
        SELECT c.*, u.first_name, u.last_name
        FROM certificates c LEFT JOIN users u ON u.id=c.user_id
        WHERE c.event_id=? ORDER BY c.id DESC LIMIT ? OFFSET ?
    """, (eid, per, page * per), fetch="all") or []

    pages = max(1, (total + per - 1) // per)
    lines = [f"📜 گواهینامه‌های صادرشده ({total})",
             "━━━━━━━━━━━━━━", ""]
    if not rows:
        lines.append("📭 هنوز گواهینامه‌ای صادر نشده")
    for r in rows:
        nm = _name_of(r)
        mark = "🚫" if r.get("revoked") else "🎓"
        lines += [f"{mark} {nm}",
                  f"      🔖 {r.get('serial')} · "
                  f"{_jd.fmt(r.get('issued_at'), 'date')}"]

    btns = []
    for r in rows:
        nm = _name_of(r)
        mark = "🚫" if r.get("revoked") else "🎓"
        btns.append([{"text": f"{mark} {nm}"[:30],
                      "callback_data":
                          f"ci_one_{eid}_{r.get('bale_user_id')}"}])
    nav = []
    if page > 0:
        nav.append({"text": "◀️",
                    "callback_data": f"ci_done_{eid}_{page-1}"})
    nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
    if page < pages - 1:
        nav.append({"text": "▶️",
                    "callback_data": f"ci_done_{eid}_{page+1}"})
    if len(nav) > 1:
        btns.append(nav)
    if total:
        btns.append([{"text": "🔄 بازتولید همه (قالب فعلی)",
                      "callback_data": f"ci_regall_{eid}"}])
        btns.append([{"text": "📤 ارسال دوباره به همه",
                      "callback_data": f"ci_resall_{eid}"}])
    btns.append([{"text": "🔙 مرکز صدور",
                  "callback_data": f"cert_bulk_{eid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def resend_all(cid, uid, eid):
    """📤 ارسال دوباره به همه"""
    if not _guard(cid, uid):
        return
    from events import get_event
    ev = get_event(eid)
    rows = db_execute("SELECT * FROM certificates WHERE event_id=? "
                      "AND COALESCE(revoked,0)=0", (eid,),
                      fetch="all") or []
    if not rows:
        return send(cid, "📭 گواهینامه‌ای نیست")
    send(cid, f"⏳ ارسال به {len(rows)} نفر...")
    n = 0
    for r in rows:
        if r.get("bale_user_id"):
            try:
                send_cert_files(r["bale_user_id"], r, ev)
                n += 1
            except Exception as e:
                log(f"⚠️ ارسال دوباره: {e}")
        time.sleep(0.07)
    send_or_edit(cid, f"📤 برای {n} نفر فرستاده شد 💚",
                 {"inline_keyboard": [
                     [{"text": "🔙 مرکز صدور",
                       "callback_data": f"cert_bulk_{eid}"}]]})


# ─────────── 📊 آمار ───────────
def show_stats(cid, uid, eid):
    """📊 آمار گواهینامه رویداد"""
    if not _guard(cid, uid):
        return
    eid = _eid(eid)
    if not eid:
        return send(cid, "❌ رویداد نامعتبر")
    from events import get_event
    ev = get_event(eid)
    # 🔴 باگ رفع‌شده (فاز ۴۰): رویداد حذف‌شده → get_event=None
    #    و eligible() با AttributeError می‌مرد.
    if not ev:
        return send(cid, "🌱 این رویداد دیگر وجود ندارد",
                    {"inline_keyboard": [
                        [{"text": "🔙 رویدادها",
                          "callback_data": "ev_list"}]]})
    ok, no, ctext = eligible(eid, ev)
    total = db_scalar("SELECT COUNT(*) FROM certificates WHERE event_id=?",
                      (eid,)) or 0
    rev = db_scalar("SELECT COUNT(*) FROM certificates WHERE event_id=? "
                    "AND COALESCE(revoked,0)=1", (eid,)) or 0
    total_s = sessions_count(eid)
    regs = db_scalar("SELECT COUNT(*) FROM event_registrations "
                     "WHERE event_id=? AND status IN "
                     "('confirmed','attended')", (eid,)) or 0

    # فایل‌های موجود
    rows = db_execute("SELECT png_path, pdf_path FROM certificates "
                      "WHERE event_id=?", (eid,), fetch="all") or []
    have = sum(1 for r in rows
               if (r.get("png_path") and Path(r["png_path"]).exists())
               or (r.get("pdf_path") and Path(r["pdf_path"]).exists()))

    pct = int(total * 100 / regs) if regs else 0
    lines = ["📊 آمار گواهینامه", "━━━━━━━━━━━━━━", "",
             f"🎉 {ev.get('title')}", "",
             f"👥 ثبت‌نامی: {regs}",
             f"📚 جلسات: {total_s}",
             f"✅ شرط: {ctext}", "",
             f"🎓 صادرشده: {total} ({pct}٪ ثبت‌نامی‌ها)",
             f"✔️ واجد شرایط: {len(ok)}",
             f"⛔ رد شده: {len(no)}"]
    if rev:
        lines.append(f"🚫 باطل‌شده: {rev}")
    lines += ["", f"📎 فایل موجود: {have} از {total}"]
    if total and have < total:
        lines.append("   💡 بقیه پاکسازی شده‌اند — با «بازتولید»")
        lines.append("      دوباره ساخته می‌شوند.")

    # توزیع حضور
    if total_s:
        buckets = {"100": 0, "75": 0, "50": 0, "low": 0}
        for r in ok + no:
            p = r["percent"]
            if p >= 100:
                buckets["100"] += 1
            elif p >= 75:
                buckets["75"] += 1
            elif p >= 50:
                buckets["50"] += 1
            else:
                buckets["low"] += 1
        lines += ["", "📈 توزیع حضور:",
                  f"   💯 کامل: {buckets['100']}",
                  f"   🟢 ۷۵٪+: {buckets['75']}",
                  f"   🟡 ۵۰٪+: {buckets['50']}",
                  f"   🔴 زیر ۵۰٪: {buckets['low']}"]

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "📤 خروجی اکسل حضور",
          "callback_data": f"att_export_{eid}"}],
        [{"text": "👥 واجدین شرایط", "callback_data": f"ci_ok_{eid}_0"}],
        [{"text": "🔙 مرکز صدور", "callback_data": f"cert_bulk_{eid}"}]]})


# ─────────── 👤 انتخاب دستی ───────────
def show_pick(cid, uid, eid, page=0):
    """👤 انتخاب دستی نفرات"""
    if not _guard(cid, uid):
        return
    per = 8
    rows = db_execute("""
        SELECT r.bale_user_id, u.first_name, u.last_name
        FROM event_registrations r LEFT JOIN users u ON u.id=r.user_id
        WHERE r.event_id=? AND r.status IN ('confirmed','attended')
          AND r.bale_user_id IS NOT NULL
        ORDER BY u.first_name LIMIT ? OFFSET ?
    """, (eid, per, page * per), fetch="all") or []
    total = db_scalar("SELECT COUNT(*) FROM event_registrations "
                      "WHERE event_id=? AND status IN "
                      "('confirmed','attended')", (eid,)) or 0
    try:
        picked = set(int(x) for x in cfg_get(eid, "picked", []) or [])
    except (TypeError, ValueError):
        picked = set()

    pages = max(1, (total + per - 1) // per)
    lines = [f"👤 انتخاب دستی ({len(picked)} نفر)",
             "━━━━━━━━━━━━━━", "",
             "روی هر نفر بزنید تا انتخاب/لغو شود:", ""]
    btns = []
    for r in rows:
        nm = _name_of(r)
        on = r["bale_user_id"] in picked
        btns.append([{"text": f"{'✅' if on else '⬜'} {nm}"[:34],
                      "callback_data":
                          f"ci_tog_{eid}_{r['bale_user_id']}_{page}"}])
    nav = []
    if page > 0:
        nav.append({"text": "◀️",
                    "callback_data": f"ci_pick_{eid}_{page-1}"})
    nav.append({"text": f"{page+1}/{pages}", "callback_data": "noop"})
    if page < pages - 1:
        nav.append({"text": "▶️",
                    "callback_data": f"ci_pick_{eid}_{page+1}"})
    if len(nav) > 1:
        btns.append(nav)
    btns.append([{"text": "🔙 شرط دریافت",
                  "callback_data": f"ci_cond_{eid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_pick(cid, uid, eid, bale_uid, page=0):
    if not _guard(cid, uid):
        return
    try:
        picked = set(int(x) for x in cfg_get(eid, "picked", []) or [])
    except (TypeError, ValueError):
        picked = set()
    if bale_uid in picked:
        picked.discard(bale_uid)
    else:
        picked.add(bale_uid)
    cfg_set(eid, "picked", sorted(picked), uid)
    return show_pick(cid, uid, eid, page)
