# -*- coding: utf-8 -*-
"""
🏛️ مرکز صدور گواهینامه

🎯 گزارش شما:
   «یه مرکز صدور گواهینامه تو قسمت کاربران اضافه کن... اونجا من
    گواهینامه رو انتخاب کنم با جای خالی پارامترهای توی قالب
    گواهینامه، بعد به اون پارامترها داده میدم و اون داده‌ها میشن
    یه گواهینامه جدید و ذخیره میشن تو منتشرشده... بعد دسته
    کاربران رو انتخاب کنم مثلا یک رویداد یا یک دسته خاص یا
    ورودی اکسل... بعد یه پیشنمایش تصادفی به من نشون بده و بعد
    بزنم ارسال... درآخر گواهینامه بره بشینه تو قسمت گواهینامه‌های
    من پروفایلش، همون لحظه برای همه ساخته نشه»

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📐 دو مفهوم کلیدی

  «طرح» (issue)
     قالب ورد + مقدار پارامترهای مشترک + تنظیمات ارسال.
     مثل یک «قالبِ پرشده» که آمادهٔ انتشار است.

  «سهم» (share)
     یک ردیف برای هر گیرنده. **فایل ساخته نمی‌شود** — فقط
     رزرو می‌شود. کاربر هر وقت به پروفایلش رفت، همان لحظه
     ساخته و تحویل داده می‌شود.

  🔑 چرا؟ «همون لحظه برای همه ساخته نشه و ارسال بشه تا به
     سیستم فشار بیاد» — ساخت ۵۰۰ گواهینامه یعنی ۵۰۰ بار اجرای
     LibreOffice. با این روش فقط یک اعلان می‌رود و بار روی
     زمان پخش می‌شود.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔄 چرخهٔ کار — ۶ گام
   ۱ قالب را انتخاب کن
   ۲ پارامترهای خالی را پر کن
   ۳ گیرنده‌ها را انتخاب کن (رویداد · دسته · اکسل · دستی)
   ۴ پیش‌نمایش تصادفی ببین
   ۵ منتشر کن
   ۶ اعلان برود · کاربر خودش دانلود کند
"""
from privacy import user_error_message
import json
import random
import re
import secrets
from datetime import datetime
from pathlib import Path

from database import (db_execute, db_scalar, get_setting, set_setting,
                      ensure_table, log)
import jalali as _jd

# ══════════════════════════════════════════════════════════
# 🗄️ جدول‌ها
# ══════════════════════════════════════════════════════════
ISSUE_SCHEMA = {
    "title": "TEXT",                    # نام طرح
    "template_id": "INTEGER",           # قالب ورد
    # 🔴 نام ستون «params» است نه «values»:
    #    VALUES یک **کلمهٔ کلیدی SQL** است و
    #    «INSERT INTO … (values) VALUES (…)» خطای نحوی می‌دهد.
    "params": "TEXT",                   # JSON — پارامترهای مشترک
    "audience": "TEXT",                 # event | segment | excel | manual
    "audience_ref": "TEXT",             # شناسهٔ رویداد / نام دسته / …
    "status": "TEXT DEFAULT 'draft'",   # draft | published | closed
    "notify_title": "TEXT",
    "notify_body": "TEXT",
    "doc_no": "TEXT",                   # شمارهٔ نامهٔ مشترک
    "valid_months": "INTEGER DEFAULT -1",   # ‑۱ = از تنظیمات کلی
    "link_token": "TEXT",               # لینک عمومی دریافت
    "link_on": "INTEGER DEFAULT 1",
    "auto_photo": "INTEGER DEFAULT 1",  # عکس پرسنلی خودکار
    "total": "INTEGER DEFAULT 0",
    "built": "INTEGER DEFAULT 0",       # چند نفر واقعاً ساختند
    "published_at": "TIMESTAMP",
    "created_by": "INTEGER",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

SHARE_SCHEMA = {
    "issue_id": "INTEGER",
    "bale_user_id": "INTEGER",          # ممکن است خالی باشد (اکسل)
    "full_name": "TEXT",
    "national_id": "TEXT",
    "mobile": "TEXT",
    "extra": "TEXT",                    # JSON — پارامترهای شخصی
    "person_code": "TEXT",              # کد یکتای فرد
    "cert_id": "INTEGER",               # وقتی ساخته شد
    "state": "TEXT DEFAULT 'ready'",    # ready | built | failed
    "notified": "INTEGER DEFAULT 0",
    "built_at": "TIMESTAMP",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

AUDIENCES = {
    "event":   ("🎉", "شرکت‌کنندگان یک رویداد"),
    "segment": ("🏷️", "دستهٔ خاصی از کاربران"),
    "excel":   ("📊", "فهرست اکسل"),
    "manual":  ("✍️", "دستی یا جستجو"),
}

# 🏷️ دسته‌های آماده — از پنل قابل گسترش
SEGMENTS = {
    "all":       ("👥", "همهٔ کاربران تأییدشده",
                  "profile_status='approved'"),
    "vip":       ("⭐", "کاربران ویژه", "is_vip=1"),
    "active":    ("🔥", "فعال‌های ۳۰ روز اخیر",
                  "last_activity_at >= datetime('now','-30 days')"),
    "withphoto": ("📷", "دارندگان عکس تأییدشده",
                  "profile_photo IS NOT NULL AND profile_status='approved'"),
    "admins":    ("🛡️", "ادمین‌ها", "is_admin=1"),
}


def init_tables():
    # 🔴 جدول «certificates» مال ماژول حضوروغیاب است ولی ما هم
    #    در آن می‌نویسیم. اگر ترتیب راه‌اندازی عوض شود یا کسی
    #    فقط این ماژول را import کند، جدول وجود ندارد و
    #    INSERT بی‌صدا شکست می‌خورد.
    try:
        import attendance as _att
        _att.init_attendance_tables()
    except Exception as e:
        log(f"⚠️ آماده‌سازی جدول گواهینامه‌ها: {e}")
    ensure_table("cert_issues", ISSUE_SCHEMA)
    ensure_table("cert_shares", SHARE_SCHEMA)
    for q in (
        "CREATE INDEX IF NOT EXISTS idx_ci_status "
        "ON cert_issues(status)",
        "CREATE INDEX IF NOT EXISTS idx_cs_issue "
        "ON cert_shares(issue_id)",
        "CREATE INDEX IF NOT EXISTS idx_cs_user "
        "ON cert_shares(bale_user_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_cs "
        "ON cert_shares(issue_id, bale_user_id, national_id)",
    ):
        try:
            db_execute(q)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════
# 🧩 پارامترها
# ══════════════════════════════════════════════════════════
# 🤖 پارامترهایی که ربات **خودش** پر می‌کند — از ادمین نمی‌پرسیم
# ══════════════════════════════════════════════════════════
# 🧩 دسته‌بندی پارامترها — بازطراحی فاز ۳۹
#
# 🎯 «من گفتم برای تمام داده‌های گواهینامه بتونم داده‌هایی که
#     دوست دارم تعریف کنم بدون هیچ دستکاری و اضافه‌ای از تو»
#
# 🔴 اشتباه نسخهٔ قبل: یک فهرست بلند AUTO_KEYS داشت و هر چه
#    در آن بود، **از شما پرسیده نمی‌شد** — حتی «تاریخ صدور» و
#    «شماره نامه» که خودتان می‌خواستید تعیین کنید.
#
# ✅ منطق تازه، دقیقاً همان چیزی که گفتید:
#
#    🔁 متغیر  → برای هر نفر فرق دارد، از پروفایل/اکسل می‌آید
#                (نام، کد ملی، موبایل، عکس)
#    📌 ثابت   → برای همه یکی است، **شما** پرش می‌کنید
#                (نام رویداد، تاریخ برگزاری، مدرس، ساعت، …)
#    🤖 سیستمی → فقط اگر خودتان مقدار ندهید، ربات می‌سازد
#                (کد فردی، کیوآر، شمارهٔ سریال)
# ══════════════════════════════════════════════════════════

# 🔁 برای هر نفر فرق دارد — هرگز از ادمین پرسیده نمی‌شود
PER_PERSON = {
    "name", "first_name", "last_name", "national_id", "mobile",
    "gender", "gender_title", "birth_date", "member_id", "email",
    "city", "province", "education", "field_study", "university",
    "job", "company", "father_name", "mother_name", "address",
    "postal_code", "bio", "photo",
    # 📊 آمار حضور — مخصوص هر نفر
    "sessions", "total_sessions", "attendance_pct", "score", "rank",
}

# 🤖 ربات می‌سازد — **ولی اگر شما مقدار بدهید، مال شما برنده است**
#
# 🎯 «کد فردی و این چیزا اگه من پارامترش گذاشتم قرار بده وگرنه
#     از کدملی یا هرچی از خودت بساز برای خودت»
SYSTEM_KEYS = {
    "serial", "verify_code", "full_code", "verify_url",
    "qr", "barcode",
    "issue_date", "issued_on", "today", "date_fa",
    "expire_date", "expires_on",
}

# 🔙 سازگاری با کد قدیمی
AUTO_KEYS = PER_PERSON | SYSTEM_KEYS


def template_fields(tid):
    """
    🔍 پارامترهای یک قالب — تفکیک‌شده.

    خروجی: (پارامترهای پرسیدنی، پارامترهای خودکار، تصاویر)
    """
    import certgen as cg

    t = cg.get_template(tid)
    if not t:
        return [], [], []

    keys = []
    # ۱) از فهرست ذخیره‌شده
    try:
        keys = list(json.loads(t.get("placeholders") or "[]"))
    except Exception:
        keys = []

    # ۲) اگر خالی بود، خود فایل را بخوان
    if not keys:
        keys = scan_template(tid)

    ask, auto, imgs = [], [], []
    for k in keys:
        if k in cg.IMAGE_KEYS:
            imgs.append(k)
        elif k in PER_PERSON:
            auto.append(k)          # 🔁 مخصوص هر نفر
        else:
            # 📌 ثابت **و** 🤖 سیستمی — هر دو از شما پرسیده
            #    می‌شوند. سیستمی‌ها اختیاری‌اند: خالی بگذارید،
            #    ربات خودش می‌سازد.
            ask.append(k)
    return ask, auto, imgs


def field_kind(key):
    """
    🏷️ این پارامتر از کدام دسته است؟

    خروجی: "person" | "system" | "fixed" | "image"
    """
    import certgen as cg
    if key in cg.IMAGE_KEYS:
        return "image"
    if key in PER_PERSON:
        return "person"
    if key in SYSTEM_KEYS:
        return "system"
    return "fixed"


KIND_FA = {
    "person": ("🔁", "برای هر نفر فرق دارد"),
    "system": ("🤖", "خالی بگذارید تا ربات بسازد"),
    "fixed":  ("📌", "برای همه یکسان"),
    "image":  ("🖼️", "تصویر"),
}


def scan_template(tid):
    """📖 فایل ورد را باز می‌کند و پارامترها را بیرون می‌کشد"""
    import certgen as cg

    t = cg.get_template(tid)
    if not t:
        return []
    src = t.get("file_path")
    if not src or not Path(src).exists():
        return []
    if (t.get("kind") or "docx") != "docx":
        try:
            return list(json.loads(t.get("placeholders") or "[]"))
        except Exception:
            return []
    try:
        import docx
        from docx.oxml.ns import qn
        d = docx.Document(str(src))
    except Exception as e:
        log(f"⚠️ خواندن قالب {tid}: {e}")
        return []

    blob = []
    try:
        for p in cg._all_paragraphs(d):
            if p.text:
                blob.append(p.text)
        for node in d.element.body.iter(qn("w:t")):
            if node.text:
                blob.append(node.text)
    except Exception:
        pass

    found, seen = [], set()
    for m in cg._PH_RE.finditer("\n".join(blob)):
        k = cg.resolve_key(m.group(1))
        if k and k not in seen:
            seen.add(k)
            found.append(k)

    # 💾 ذخیره کن تا دفعهٔ بعد سریع باشد
    try:
        db_execute("UPDATE cert_templates SET placeholders=? WHERE id=?",
                   (json.dumps(found, ensure_ascii=False), int(tid)))
    except Exception:
        pass
    return found


# ══════════════════════════════════════════════════════════
# 📋 طرح‌ها
# ══════════════════════════════════════════════════════════
def get_issue(iid):
    try:
        n = int(iid)
    except (TypeError, ValueError):
        return None
    return db_execute("SELECT * FROM cert_issues WHERE id=?",
                      (n,), fetch="one")


def issue_values(iss):
    """مقادیر پارامترهای یک طرح — dict"""
    try:
        return dict(json.loads((iss or {}).get("params") or "{}"))
    except Exception:
        return {}


def set_value(iid, key, val):
    iss = get_issue(iid)
    if not iss:
        return False
    v = issue_values(iss)
    if val == "" or val is None:
        v.pop(key, None)
    else:
        # 🔴 باگ رفع‌شده (فاز ۴۰): برش در خودِ تابع، نه فقط در
        #    مسیرهای ورودی. ورودی ۹۰۰۰ نویسه‌ای عیناً ذخیره
        #    می‌شد و ستون params را باد می‌کرد.
        v[key] = str(val)[:300]
    db_execute("UPDATE cert_issues SET params=? WHERE id=?",
               (json.dumps(v, ensure_ascii=False), int(iid)))
    return True


def create_issue(uid, title, tid):
    """➕ طرح تازه"""
    init_tables()
    return db_execute(
        "INSERT INTO cert_issues (title, template_id, params, "
        "link_token, created_by) VALUES (?,?,?,?,?)",
        (title[:120], int(tid), "{}", secrets.token_urlsafe(8), uid))


def list_issues(status=None, limit=30):
    q = "SELECT * FROM cert_issues"
    a = []
    if status:
        q += " WHERE status=?"
        a.append(status)
    q += " ORDER BY id DESC LIMIT ?"
    a.append(int(limit))
    return db_execute(q, tuple(a), fetch="all") or []


def issue_ready(iss):
    """
    ✅ آیا این طرح آمادهٔ انتشار است؟

    خروجی: (آماده؟، فهرست کارهای مانده)
    """
    todo = []
    if not iss:
        return False, ["طرح یافت نشد"]
    if not iss.get("template_id"):
        todo.append("قالب انتخاب نشده")
    else:
        ask, _, _ = template_fields(iss["template_id"])
        vals = issue_values(iss)
        # 🤖 پارامترهای سیستمی اختیاری‌اند — اگر خالی باشند
        #    ربات خودش می‌سازد، پس مانع انتشار نیستند.
        #
        #    🎯 «کد فردی و این چیزا اگه من پارامترش گذاشتم قرار
        #        بده وگرنه از خودت بساز»
        empty = [k for k in ask
                 if field_kind(k) != "system"
                 and not str(vals.get(k) or "").strip()]
        if empty:
            import certgen as cg
            names = "، ".join(cg.ph_label(k) for k in empty[:4])
            more = f" و {len(empty) - 4} مورد دیگر" if len(empty) > 4 else ""
            todo.append(f"پارامتر خالی: {names}{more}")
    n = db_scalar("SELECT COUNT(*) FROM cert_shares WHERE issue_id=?",
                  (iss["id"],)) or 0
    if not n:
        todo.append("گیرنده‌ای انتخاب نشده")
    return (not todo), todo


# ══════════════════════════════════════════════════════════
# 👥 گیرنده‌ها
# ══════════════════════════════════════════════════════════
def _name_of(u):
    return (f"{u.get('first_name') or ''} "
            f"{u.get('last_name') or ''}").strip() or "کاربر"


def add_share(iid, uid=None, name="", nid="", mobile="", extra=None):
    """➕ یک گیرنده — تکراری‌ها نادیده گرفته می‌شوند"""
    import certverify as cv
    try:
        return db_execute(
            "INSERT OR IGNORE INTO cert_shares (issue_id, bale_user_id, "
            "full_name, national_id, mobile, extra, person_code) "
            "VALUES (?,?,?,?,?,?,?)",
            (int(iid), uid, name[:120], nid or "", mobile or "",
             json.dumps(extra or {}, ensure_ascii=False),
             cv.new_person_code()))
    except Exception as e:
        log(f"⚠️ افزودن گیرنده: {e}")
        return None


def fill_from_event(iid, eid):
    """🎉 همهٔ ثبت‌نام‌های تأییدشدهٔ یک رویداد"""
    rows = db_execute(
        "SELECT u.* FROM event_registrations r "
        "JOIN users u ON u.bale_user_id = r.bale_user_id "
        "WHERE r.event_id=? AND r.status IN ('confirmed','attended')",
        (int(eid),), fetch="all") or []
    n = 0
    for u in rows:
        if add_share(iid, u.get("bale_user_id"), _name_of(u),
                     u.get("national_id") or "", u.get("mobile") or ""):
            n += 1
    _sync_total(iid, "event", str(eid))
    return n


def fill_from_segment(iid, seg):
    """🏷️ یک دستهٔ آماده"""
    s = SEGMENTS.get(seg)
    if not s:
        return 0
    rows = db_execute(
        f"SELECT * FROM users WHERE {s[2]} AND is_blocked=0",
        fetch="all") or []
    n = 0
    for u in rows:
        if add_share(iid, u.get("bale_user_id"), _name_of(u),
                     u.get("national_id") or "", u.get("mobile") or ""):
            n += 1
    _sync_total(iid, "segment", seg)
    return n


def fill_from_rows(iid, rows):
    """📊 ردیف‌های اکسل — به کاربر موجود وصل می‌شوند اگر پیدا شد"""
    n = 0
    for r in rows:
        nid = (r.get("national_id") or "").strip()
        mob = (r.get("mobile") or "").strip()
        uid = None
        if nid:
            u = db_execute("SELECT bale_user_id FROM users "
                           "WHERE national_id=?", (nid,), fetch="one")
            uid = (u or {}).get("bale_user_id")
        if not uid and mob:
            u = db_execute("SELECT bale_user_id FROM users "
                           "WHERE mobile=?", (mob,), fetch="one")
            uid = (u or {}).get("bale_user_id")
        if add_share(iid, uid, r.get("full_name") or "", nid, mob,
                     r.get("extra")):
            n += 1
    _sync_total(iid, "excel", "")
    return n


def _sync_total(iid, audience=None, ref=None):
    n = db_scalar("SELECT COUNT(*) FROM cert_shares WHERE issue_id=?",
                  (int(iid),)) or 0
    if audience:
        db_execute("UPDATE cert_issues SET total=?, audience=?, "
                   "audience_ref=? WHERE id=?",
                   (n, audience, ref or "", int(iid)))
    else:
        db_execute("UPDATE cert_issues SET total=? WHERE id=?",
                   (n, int(iid)))
    return n


def shares(iid, limit=None, state=None):
    q = "SELECT * FROM cert_shares WHERE issue_id=?"
    a = [int(iid)]
    if state:
        q += " AND state=?"
        a.append(state)
    q += " ORDER BY id"
    if limit:
        q += " LIMIT ?"
        a.append(int(limit))
    return db_execute(q, tuple(a), fetch="all") or []


def clear_shares(iid):
    db_execute("DELETE FROM cert_shares WHERE issue_id=?", (int(iid),))
    _sync_total(iid)


# ══════════════════════════════════════════════════════════
# 🏗️ ساخت گواهینامه — تنبل
# ══════════════════════════════════════════════════════════
def mapping_for(iss, share):
    """
    🗺️ همهٔ پارامترهای یک نفر — آمادهٔ تحویل به موتور ورد.

    ترتیب اولویت (بالاتر برنده است):
       ۱ مقادیر خودکار (نام، کد ملی، تاریخ، …)
       ۲ مقادیر مشترک طرح
       ۳ مقادیر شخصیِ همان ردیف (ستون‌های اضافهٔ اکسل)
    """
    import certgen as cg
    import certverify as cv

    vals = issue_values(iss)
    uid = share.get("bale_user_id")
    u = {}
    if uid:
        u = db_execute("SELECT * FROM users WHERE bale_user_id=?",
                       (uid,), fetch="one") or {}

    name = (share.get("full_name") or "").strip() or _name_of(u)
    nid = (share.get("national_id") or u.get("national_id") or "")
    mob = (share.get("mobile") or u.get("mobile") or "")

    # 🔖 شمارهٔ نامه — اولویت: مقدار پارامتر شما ← تنظیم طرح ← پنل
    #
    # 🎯 «کد فردی و این چیزا اگه من پارامترش گذاشتم قرار بده
    #     وگرنه از کدملی یا هرچی از خودت بساز»
    doc = (str(vals.get("doc_no") or "").strip()
           or (iss.get("doc_no") or "").strip()
           or get_setting("cert_doc_no", "") or "")

    # 🔑 کد فردی — اگر خودتان تعیین کرده‌اید همان، وگرنه ربات
    pcode = (str(vals.get("verify_code") or "").strip()
             or share.get("person_code")
             or cv.new_person_code())

    # 🔗 شناسهٔ کامل — اگر دستی داده‌اید دست نمی‌خورد
    full = (str(vals.get("full_code") or "").strip()
            or cv.build_full_code(doc, pcode))

    months = iss.get("valid_months")
    if months is None or int(months) < 0:
        try:
            months = int(get_setting("cert_valid_months", "24") or 0)
        except (TypeError, ValueError):
            months = 0
    issued = _jd.today_iso()
    expires = _jd.add_months(issued, months) if months else ""

    kw = dict(
        name=name,
        first_name=u.get("first_name") or name.split(" ")[0],
        last_name=u.get("last_name")
        or " ".join(name.split(" ")[1:]),
        national_id=nid, mobile=mob,
        gender=u.get("gender") or "",
        birth_date=u.get("birth_date") or "",
        email=u.get("email") or "",
        city=u.get("city") or "", province=u.get("province") or "",
        education=u.get("education") or "",
        field_study=u.get("field_study") or "",
        university=u.get("university") or "",
        job=u.get("job") or "", company=u.get("company") or "",
        father_name=u.get("father_name") or "",
        member_id=u.get("id") or "",
        serial=full or pcode,
        doc_no=doc, verify_code=pcode, full_code=full,
        issue_date=_jd.fmt(issued, "date"),
        expire_date=_jd.fmt(expires, "date") if expires else "",
        today=_jd.today_str(),
    )
    # 🔁 نام‌های جایگزینی که resolve_key برمی‌گرداند
    kw["issued_on"] = kw["issue_date"]
    kw["expires_on"] = kw["expire_date"]
    kw["date_fa"] = kw["today"]
    try:
        import certverify as _cv2
        kw["verify_url"] = _cv2.verify_link(full or pcode)
    except Exception:
        pass

    # ۲) مقادیر مشترک طرح — **بالاترین اولویت**
    #
    # 🎯 «بدون هیچ دستکاری و اضافه‌ای از تو»
    #    هر چه اینجا نوشته‌اید، عیناً روی گواهینامه می‌نشیند و
    #    مقدار ساختهٔ ربات را کنار می‌زند.
    for k, v in vals.items():
        if str(v).strip():
            kw[k] = v
            # 🔁 کلیدهای هم‌معنی را هم هماهنگ کن تا قالب با هر
            #    نامی که نوشته باشد همان مقدار را بگیرد
            for _a, _b in (("issue_date", "issued_on"),
                           ("expire_date", "expires_on"),
                           ("today", "date_fa")):
                if k == _a:
                    kw[_b] = v
                elif k == _b:
                    kw[_a] = v

    # ۳) مقادیر شخصی
    try:
        ex = json.loads(share.get("extra") or "{}")
    except Exception:
        ex = {}
    for k, v in (ex or {}).items():
        rk = cg.resolve_key(k) or k
        if str(v).strip():
            kw[rk] = v

    return cg.build_mapping(**kw), {
        "doc_no": doc, "person_code": pcode, "full_code": full,
        "issued_on": issued, "expires_on": expires,
        "valid_months": int(months or 0)}


def _attach_photo(iss, tid, share, mp):
    """
    📷 عکس پرسنلی را به نقشهٔ پارامترها می‌چسباند.

    🔑 موتور `certgen.generate` عکس شخص را از کلید ویژهٔ
       `_photo` می‌خواند (نه از آرگومان جدا).
    """
    if str(iss.get("auto_photo") or "1") != "1":
        return
    try:
        _, _, imgs = template_fields(tid)
        if "photo" not in imgs:
            return
        import certphoto
        p = certphoto.photo_for(share.get("bale_user_id"))
        if p:
            mp["_photo"] = str(p)
    except Exception as e:
        log(f"⚠️ عکس پرسنلی: {e}")


def build_one(iid, share_id, notify=False):
    """
    🏗️ گواهینامهٔ یک نفر را **همین حالا** بساز.

    این تابع وقتی صدا زده می‌شود که کاربر خودش در پروفایلش
    روی گواهینامه بزند — نه هنگام انتشار.

    خروجی: (رکورد گواهینامه، خطا)
    """
    import certgen as cg

    iss = get_issue(iid)
    sh = db_execute("SELECT * FROM cert_shares WHERE id=?",
                    (int(share_id),), fetch="one")
    if not iss or not sh:
        return None, "طرح یا گیرنده یافت نشد"

    # ♻️ قبلاً ساخته شده؟
    if sh.get("cert_id"):
        c = db_execute("SELECT * FROM certificates WHERE id=?",
                       (sh["cert_id"],), fetch="one")
        if c:
            paths = [c.get("png_path"), c.get("pdf_path"),
                     c.get("docx_path")]
            if any(p and Path(p).exists() for p in paths):
                return c, ""

    tid = iss.get("template_id")
    if not tid:
        return None, "قالبی برای این طرح تعیین نشده"

    mp, info = mapping_for(iss, sh)
    _attach_photo(iss, tid, sh, mp)

    uid = sh.get("bale_user_id")
    tpl = cg.get_template(tid)
    if not tpl:
        return None, "قالب یافت نشد"
    try:
        files = cg.generate(mp, tpl)
    except Exception as e:
        log(f"⚠️ ساخت گواهینامه: {e}")
        db_execute("UPDATE cert_shares SET state='failed' WHERE id=?",
                   (sh["id"],))
        return None, str(e)[:120]

    if not files or not any(files.get(k) for k in ("png", "pdf", "docx")):
        db_execute("UPDATE cert_shares SET state='failed' WHERE id=?",
                   (sh["id"],))
        return None, (files or {}).get("error") or "ساخت فایل ناموفق بود"

    cid_ = db_execute(
        "INSERT INTO certificates (event_id, bale_user_id, serial, "
        "template, template_id, png_path, pdf_path, docx_path, "
        "file_path, doc_no, person_code, full_code, issued_on, "
        "expires_on, valid_months, source, issued_by) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (None, uid, info["full_code"] or info["person_code"],
         "", tid, files.get("png"), files.get("pdf"),
         files.get("docx"),
         files.get("png") or files.get("pdf") or files.get("docx"),
         info["doc_no"], info["person_code"], info["full_code"],
         info["issued_on"], info["expires_on"], info["valid_months"],
         "center", iss.get("created_by")))

    # 🔴 باگ رفع‌شده: اگر INSERT شکست می‌خورد (مثلاً جدول نبود)،
    #    `cid_` تهی می‌شد ولی کد بی‌سروصدا ادامه می‌داد و سهم را
    #    «ساخته‌شده» علامت می‌زد — بدون هیچ گواهینامه‌ای.
    if not cid_:
        db_execute("UPDATE cert_shares SET state='failed' WHERE id=?",
                   (sh["id"],))
        return None, "ثبت گواهینامه در دیتابیس ناموفق بود"

    db_execute(
        "UPDATE cert_shares SET cert_id=?, state='built', "
        "built_at=CURRENT_TIMESTAMP WHERE id=?", (cid_, sh["id"]))
    db_execute("UPDATE cert_issues SET built=COALESCE(built,0)+1 "
               "WHERE id=?", (int(iid),))
    if uid:
        db_execute("UPDATE users SET total_certificates="
                   "COALESCE(total_certificates,0)+1 "
                   "WHERE bale_user_id=?", (uid,))

    cert = db_execute("SELECT * FROM certificates WHERE id=?",
                      (cid_,), fetch="one")
    if not cert:
        db_execute("UPDATE cert_shares SET state='failed' WHERE id=?",
                   (sh["id"],))
        return None, "گواهینامه ثبت شد ولی خوانده نشد"

    if notify and uid and cert:
        try:
            import certissue
            certissue.send_cert_files(uid, cert, None)
        except Exception as e:
            log(f"⚠️ ارسال گواهینامه: {e}")
    return cert, ""


def preview(iid, share_id=None):
    """
    👁️ پیش‌نمایش — یک نفر تصادفی.

    🎯 «یه پیشنمایش تصادفی به من نشون بده»

    فایل ساخته می‌شود ولی در جدول گواهینامه‌ها ثبت **نمی‌شود**
    و به کسی هم فرستاده نمی‌شود.
    """
    import certgen as cg

    iss = get_issue(iid)
    if not iss:
        return None, "طرح یافت نشد"
    rows = shares(iid)
    if not rows:
        return None, "هنوز گیرنده‌ای انتخاب نشده"

    sh = None
    if share_id:
        sh = next((r for r in rows if r["id"] == int(share_id)), None)
    sh = sh or random.choice(rows)

    tid = iss.get("template_id")
    if not tid:
        return None, "قالبی تعیین نشده"

    mp, info = mapping_for(iss, sh)
    _attach_photo(iss, tid, sh, mp)
    tpl = cg.get_template(tid)
    if not tpl:
        return None, "قالب یافت نشد"
    try:
        files = cg.generate(mp, tpl)
    except Exception as e:
        return None, str(e)[:120]
    if not files or not any(files.get(k) for k in ("png", "pdf", "docx")):
        return None, ((files or {}).get("error")
                      or "ساخت پیش‌نمایش ناموفق بود")
    files["_who"] = sh
    return files, ""


# ══════════════════════════════════════════════════════════
# 📢 انتشار
# ══════════════════════════════════════════════════════════
def publish(iid, notify=True):
    """
    📢 طرح را منتشر کن.

    🔑 هیچ فایلی ساخته نمی‌شود — فقط وضعیت عوض می‌شود و اعلان
       می‌رود. ساخت واقعی وقتی است که کاربر خودش اقدام کند.

    خروجی: (تعداد اعلان‌شده، خطا)
    """
    from bale_api import send

    iss = get_issue(iid)
    if not iss:
        return 0, "طرح یافت نشد"
    ok, todo = issue_ready(iss)
    if not ok:
        return 0, "؛ ".join(todo)

    db_execute("UPDATE cert_issues SET status='published', "
               "published_at=CURRENT_TIMESTAMP WHERE id=?", (int(iid),))

    # 🐢 فاز ۴۰ — تنظیم `cc_lazy_build` حالا واقعاً اثر دارد
    #
    # 🔴 تعریف شده بود ولی هرگز خوانده نمی‌شد. اگر ادمین
    #    خاموشش کند یعنی «همه را همین حالا بساز» — رفتار
    #    قدیمی قبل از فاز ۳۶.
    if get_setting("cc_lazy_build", "1") != "1":
        built = 0
        for sh in shares(iid):
            c, _e = build_one(iid, sh["id"], notify=False)
            if c:
                built += 1
        log(f"⚡ ساخت فوری {built} گواهینامه (ساخت تنبل خاموش)")

    if not notify:
        return 0, ""

    title = (iss.get("notify_title") or "").strip() or get_setting(
        "cc_notify_title", "🎓 گواهینامهٔ شما آماده است!")
    body = (iss.get("notify_body") or "").strip() or get_setting(
        "cc_notify_body",
        "می‌توانید از پروفایلتان آن را دریافت کنید 💚")

    # 📦 فاز ۴۰ — سقف اعلان در هر نوبت و تأخیر بین ارسال‌ها
    #
    # 🔴 دو باگ رفع‌شده:
    #    B14) تنظیم `cc_notify_batch` تعریف شده بود ولی هرگز
    #         خوانده نمی‌شد.
    #    B16) هیچ تأخیری بین ارسال‌ها نبود. با ۵۰۰ گیرنده،
    #         بله محدودیت نرخ می‌زد و بخشی از اعلان‌ها گم
    #         می‌شدند. الگو از ads.py گرفته شد.
    import time as _t
    try:
        cap = int(get_setting("cc_notify_batch", "25") or 25)
    except (TypeError, ValueError):
        cap = 25
    cap = max(1, cap)

    n = 0
    for sh in shares(iid):
        uid = sh.get("bale_user_id")
        if not uid or sh.get("notified"):
            continue
        if n and n % cap == 0:
            _t.sleep(1.0)          # نفس‌گیری بین دسته‌ها
        elif n:
            _t.sleep(0.05)
        lines = [title, "━━━━━━━━━━━━━━", ""]
        if iss.get("title"):
            lines += [f"🎉 {iss['title']}", ""]
        lines += [body, "", f"📅 {_jd.today_str()}"]
        try:
            send(uid, "\n".join(lines), {"inline_keyboard": [
                [{"text": "🎓 دریافت گواهینامه",
                  "callback_data": f"ccget_{sh['id']}"}],
                [{"text": "👤 گواهینامه‌های من",
                  "callback_data": "u_my_certs"}]]})
            db_execute("UPDATE cert_shares SET notified=1 WHERE id=?",
                       (sh["id"],))
            n += 1
        except Exception as e:
            log(f"⚠️ اعلان به {uid}: {e}")
    return n, ""


def pending_for(uid):
    """🎓 گواهینامه‌های آمادهٔ ساختِ یک کاربر — برای پروفایل"""
    return db_execute(
        "SELECT s.*, i.title AS issue_title FROM cert_shares s "
        "JOIN cert_issues i ON i.id = s.issue_id "
        "WHERE s.bale_user_id=? AND i.status='published' "
        "AND s.state='ready' ORDER BY s.id DESC",
        (uid,), fetch="all") or []


def link_of(iss):
    """🔗 لینک عمومی دریافت"""
    # 🔴 باگ رفع‌شده (فاز ۴۰): تنظیم سراسری `cc_link_on` تعریف
    #    شده بود ولی هرگز خوانده نمی‌شد — ادمین خاموشش می‌کرد
    #    و لینک‌ها همچنان کار می‌کردند.
    if get_setting("cc_link_on", "1") != "1":
        return ""
    if not iss or str(iss.get("link_on") or "1") != "1":
        return ""
    tok = iss.get("link_token")
    if not tok:
        return ""
    try:
        import config
        return config.deep_link(f"cc_{tok}")
    except Exception:
        return ""


def by_token(tok):
    return db_execute("SELECT * FROM cert_issues WHERE link_token=?",
                      (str(tok or "").strip(),), fetch="one")


# ══════════════════════════════════════════════════════════
# 🎛️ تنظیمات — همه از پنل قابل تغییر
# ══════════════════════════════════════════════════════════
CC_SETTINGS = [
    ("cc_notify_title", "📢", "عنوان اعلان",
     "text", "🎓 گواهینامهٔ شما آماده است!",
     "پیامی که هنگام انتشار برای گیرنده می‌رود"),
    ("cc_notify_body", "💬", "متن اعلان", "text",
     "می‌توانید از پروفایلتان آن را دریافت کنید 💚", ""),
    ("cc_lazy_build", "🐢", "ساخت هنگام دریافت", "bool", "1",
     "گواهینامه وقتی ساخته شود که کاربر اقدام کند — "
     "جلوی فشار به سیستم را می‌گیرد"),
    ("cc_link_on", "🔗", "لینک عمومی دریافت", "bool", "1",
     "هر طرح یک لینک دارد که با آن می‌شود گواهینامه گرفت"),
    ("cc_auto_photo", "📷", "عکس پرسنلی خودکار", "bool", "1",
     "اگر قالب {عکس} داشته باشد، عکس تأییدشدهٔ پروفایل بنشیند"),
    ("cc_preview_n", "👁️", "تعداد پیش‌نمایش", "num", "1",
     "چند نفر تصادفی برای بررسی نشان داده شود · بین ۱ تا ۵"),
    ("cc_notify_batch", "📦", "اعلان دسته‌ای در هر نوبت", "num", "25",
     "برای جلوگیری از محدودیت بله"),
    ("cc_export_max", "📄", "سقف خروجی یکجا", "num", "200",
     "بیشتر از این تعداد، خروجی یکجا گرفته نمی‌شود"),
]


# ══════════════════════════════════════════════════════════
# 🖥️ پنل ادمین
# ══════════════════════════════════════════════════════════
def _guard(cid, uid):
    from auth import is_admin
    from bale_api import send
    if not is_admin(uid):
        send(cid, "❌ دسترسی ندارید")
        return False
    return True


def _fa(n):
    return _jd.fa(n)


def _short(s, n=28):
    s = str(s or "")
    return s if len(s) <= n else s[:n - 1] + "…"


ST_HOME = "cc_home"


def show_home(cid, uid, note=""):
    """
    🏛️ صفحهٔ اصلی مرکز صدور

    🎯 «کار تمیز با جزییات و دقت و جامع در بیار»
    """
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    init_tables()

    n_draft = db_scalar("SELECT COUNT(*) FROM cert_issues "
                        "WHERE status='draft'") or 0
    n_pub = db_scalar("SELECT COUNT(*) FROM cert_issues "
                      "WHERE status='published'") or 0
    n_share = db_scalar("SELECT COUNT(*) FROM cert_shares") or 0
    n_built = db_scalar("SELECT COUNT(*) FROM cert_shares "
                        "WHERE state='built'") or 0
    waiting = max(0, n_share - n_built)

    import certgen as cg
    n_tpl = db_scalar("SELECT COUNT(*) FROM cert_templates "
                      "WHERE is_active=1") or 0

    lines = ["🏛️ مرکز صدور گواهینامه", "━━━━━━━━━━━━━━", ""]
    if note:
        lines += [note, ""]
    lines += [
        f"📝 پیش‌نویس: {_fa(n_draft)}   |   📢 منتشرشده: {_fa(n_pub)}",
        f"👥 گیرندگان: {_fa(n_share)}",
        f"✅ دریافت‌کرده: {_fa(n_built)}   |   ⏳ در انتظار: {_fa(waiting)}",
        f"📄 قالب فعال: {_fa(n_tpl)}",
        "",
    ]
    if not n_tpl:
        lines += ["⚠️ هنوز قالبی ندارید",
                  "   اول از «📄 قالب‌ها» یک فایل ورد بفرستید", ""]
    lines += ["━━━━━━━━━━━━━━",
              "💡 گواهینامه‌ها همان لحظه ساخته نمی‌شوند؛",
              "   هر کاربر خودش از پروفایلش دریافت می‌کند."]

    btns = [
        [{"text": "➕ طرح تازه", "callback_data": "cc_new"}],
        [{"text": f"📝 پیش‌نویس‌ها ({_fa(n_draft)})",
          "callback_data": "cc_list_draft"},
         {"text": f"📢 منتشرشده ({_fa(n_pub)})",
          "callback_data": "cc_list_published"}],
        [{"text": "📄 قالب‌های گواهینامه", "callback_data": "ct_panel"}],
        [{"text": "📷 عکس پرسنلی", "callback_data": "cc_photo"}],
        [{"text": "⚙️ تنظیمات مرکز", "callback_data": "cc_set"}],
        [{"text": "📊 آمار و گزارش", "callback_data": "cc_stats"}],
        [{"text": "👥 مدیریت کاربران", "callback_data": "admin_users"},
         {"text": "🔙 گواهینامه و بلیط", "callback_data": "ct_hub"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_list(cid, uid, status="draft", page=0):
    """📋 فهرست طرح‌ها"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    rows = list_issues(status, limit=200)
    per = 8
    pages = max(1, (len(rows) + per - 1) // per)
    page = max(0, min(page, pages - 1))
    chunk = rows[page * per:(page + 1) * per]

    ttl = ("📝 پیش‌نویس‌ها" if status == "draft"
           else "📢 منتشرشده" if status == "published"
           else "📋 طرح‌ها")
    lines = [ttl, "━━━━━━━━━━━━━━", ""]
    if not chunk:
        lines += ["📭 چیزی اینجا نیست.", "",
                  "💡 از «➕ طرح تازه» شروع کنید."]
    btns = []
    for r in chunk:
        n = db_scalar("SELECT COUNT(*) FROM cert_shares WHERE issue_id=?",
                      (r["id"],)) or 0
        b = r.get("built") or 0
        mark = "✅" if r.get("status") == "published" else "📝"
        lines += [f"{mark} {r.get('title') or 'بدون نام'}",
                  f"   👥 {_fa(n)} نفر · 🎓 {_fa(b)} دریافت‌شده",
                  f"   📅 {_jd.fmt(r.get('created_at'), 'date')}", ""]
        btns.append([{"text": f"{mark} {_short(r.get('title'), 30)}",
                      "callback_data": f"cc_v_{r['id']}"}])

    nav = []
    if page > 0:
        nav.append({"text": "◀️ قبلی",
                    "callback_data": f"cc_pg_{status}_{page - 1}"})
    if page < pages - 1:
        nav.append({"text": "بعدی ▶️",
                    "callback_data": f"cc_pg_{status}_{page + 1}"})
    if nav:
        btns.append(nav)
    btns.append([{"text": "➕ طرح تازه", "callback_data": "cc_new"}])
    btns.append([{"text": "🔙 مرکز صدور", "callback_data": "cc_home"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_new(cid, uid):
    """➕ گام ۱ — نام طرح"""
    from bale_api import send, kb_cancel
    from auth import set_state
    if not _guard(cid, uid):
        return
    n_tpl = db_scalar("SELECT COUNT(*) FROM cert_templates "
                      "WHERE is_active=1") or 0
    if not n_tpl:
        return send(cid, (
            "⚠️ هنوز قالبی ندارید\n"
            "━━━━━━━━━━━━━━\n\n"
            "اول یک فایل ورد به‌عنوان قالب اضافه کنید.\n\n"
            "💡 در قالب، جای هر پارامتر را با آکولاد بنویسید:\n"
            "   {نام} · {رویداد} · {تاریخ} · {کیوآر}"
        ), {"inline_keyboard": [
            [{"text": "📄 قالب‌ها", "callback_data": "ct_panel"}],
            [{"text": "🔙 مرکز صدور", "callback_data": "cc_home"}]]})

    set_state(uid, "cc_title", {}, merge=False)
    send(cid, (
        "➕ طرح تازه — گام ۱ از ۵\n"
        "━━━━━━━━━━━━━━\n\n"
        "📝 یک نام برای این طرح بنویسید:\n\n"
        "مثال: گواهینامهٔ کارگاه هلال احمر ۱۴۰۵\n\n"
        "💡 این نام فقط برای خودتان است و روی گواهینامه\n"
        "   چاپ نمی‌شود."
    ), kb_cancel())


def show_issue(cid, uid, iid, note=""):
    """🗂️ صفحهٔ یک طرح — قلب پنل"""
    from bale_api import send_or_edit
    import certgen as cg
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return send_or_edit(cid, "❌ طرح یافت نشد",
                            {"inline_keyboard": [
                                [{"text": "🔙 مرکز صدور",
                                  "callback_data": "cc_home"}]]})

    tid = iss.get("template_id")
    tpl = cg.get_template(tid) if tid else None
    ask, auto, imgs = template_fields(tid) if tid else ([], [], [])
    vals = issue_values(iss)
    filled = [k for k in ask if str(vals.get(k) or "").strip()]
    empty = [k for k in ask if not str(vals.get(k) or "").strip()]
    n = db_scalar("SELECT COUNT(*) FROM cert_shares WHERE issue_id=?",
                  (iss["id"],)) or 0
    built = iss.get("built") or 0
    pub = iss.get("status") == "published"
    ok, todo = issue_ready(iss)

    lines = [f"🗂️ {iss.get('title') or 'بدون نام'}",
             "━━━━━━━━━━━━━━", ""]
    if note:
        lines += [note, ""]

    # وضعیت
    lines += [f"{'📢 منتشرشده' if pub else '📝 پیش‌نویس'}"
              f"   ·   📅 {_jd.fmt(iss.get('created_at'), 'date')}", ""]

    # گام ۱ — قالب
    lines.append(f"{'✅' if tid else '⬜'} ۱. قالب: "
                 f"{tpl.get('name') if tpl else '—'}")
    # گام ۲ — پارامترها
    if ask:
        lines.append(f"{'✅' if not empty else '⬜'} ۲. پارامترها: "
                     f"{_fa(len(filled))} از {_fa(len(ask))}")
    else:
        lines.append("✅ ۲. پارامترها: نیازی نیست")
    # گام ۳ — گیرنده
    aud = AUDIENCES.get(iss.get("audience") or "", ("", ""))
    lines.append(f"{'✅' if n else '⬜'} ۳. گیرندگان: "
                 f"{_fa(n)} نفر {aud[0]}")
    # گام ۴/۵
    lines.append(f"{'✅' if pub else '⬜'} ۴. انتشار")
    lines.append("")

    if imgs:
        nm = "، ".join(cg.ph_label(k) for k in imgs)
        lines += [f"🖼️ تصاویر قالب: {nm}"]
        if "photo" in imgs:
            st = "روشن" if str(iss.get("auto_photo") or "1") == "1" \
                else "خاموش"
            lines.append(f"   📷 عکس پرسنلی خودکار: {st}")
        lines.append("")

    if empty:
        nm = "، ".join(cg.ph_label(k) for k in empty[:5])
        more = f" و {_fa(len(empty) - 5)} مورد" if len(empty) > 5 else ""
        lines += [f"⚠️ پارامتر خالی: {nm}{more}", ""]

    if pub:
        lines += [f"🎓 دریافت‌کرده: {_fa(built)} از {_fa(n)}", ""]
        lk = link_of(iss)
        if lk:
            lines += [f"🔗 {lk}", ""]
    elif todo:
        lines += ["📌 برای انتشار:"] + [f"   • {t}" for t in todo] + [""]

    lines += ["━━━━━━━━━━━━━━"]

    btns = []
    btns.append([{"text": f"📄 قالب: {_short(tpl.get('name') if tpl else 'انتخاب کنید', 22)}",
                  "callback_data": f"cc_tpl_{iss['id']}"}])
    if ask:
        btns.append([{"text": f"🧩 پارامترها ({_fa(len(filled))}/{_fa(len(ask))})",
                      "callback_data": f"cc_ph_{iss['id']}"}])
    btns.append([{"text": f"👥 گیرندگان ({_fa(n)})",
                  "callback_data": f"cc_aud_{iss['id']}"}])
    if n and tid:
        btns.append([{"text": "👁️ پیش‌نمایش تصادفی",
                      "callback_data": f"cc_prev_{iss['id']}"}])
    btns.append([{"text": "✉️ متن اعلان",
                  "callback_data": f"cc_msg_{iss['id']}"},
                 {"text": "🔖 شماره نامه",
                  "callback_data": f"cc_doc_{iss['id']}"}])
    if "photo" in imgs:
        on = str(iss.get("auto_photo") or "1") == "1"
        btns.append([{"text": f"{'✅' if on else '❌'} 📷 عکس پرسنلی خودکار",
                      "callback_data": f"cc_photo_{iss['id']}"}])
    if not pub:
        if ok:
            btns.append([{"text": "📤 انتشار (۴ روش)",
                          "callback_data": f"cc_pub_{iss['id']}"}])
        else:
            btns.append([{"text": "🔒 هنوز آمادهٔ انتشار نیست",
                          "callback_data": f"cc_why_{iss['id']}"}])
    else:
        btns.append([{"text": "🔗 لینک دریافت",
                      "callback_data": f"cc_link_{iss['id']}"},
                     {"text": "📊 وضعیت",
                      "callback_data": f"cc_rep_{iss['id']}"}])
        btns.append([{"text": "🔔 اعلان دوباره به نگرفته‌ها",
                      "callback_data": f"cc_renot_{iss['id']}"}])
    btns.append([{"text": "✏️ تغییر نام",
                  "callback_data": f"cc_ren_{iss['id']}"},
                 {"text": "🗑️ حذف",
                  "callback_data": f"cc_del_{iss['id']}"}])
    btns.append([{"text": "🔙 مرکز صدور", "callback_data": "cc_home"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_tpl_pick(cid, uid, iid):
    """📄 گام ۱ — انتخاب قالب"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return show_home(cid, uid, "❌ طرح یافت نشد")
    rows = db_execute("SELECT * FROM cert_templates WHERE is_active=1 "
                      "ORDER BY id DESC", fetch="all") or []
    lines = ["📄 انتخاب قالب", "━━━━━━━━━━━━━━", ""]
    if not rows:
        lines += ["📭 قالب فعالی ندارید.", "",
                  "💡 از «📄 قالب‌ها» یک فایل ورد بفرستید."]
    else:
        lines += ["کدام قالب برای این طرح؟", ""]
    btns = []
    cur = iss.get("template_id")
    for t in rows:
        keys = scan_template(t["id"])
        mark = "✅ " if t["id"] == cur else ""
        lines += [f"{mark}📄 {t.get('name')}",
                  f"   🧩 {_fa(len(keys))} پارامتر · "
                  f"{'ورد' if (t.get('kind') or 'docx') == 'docx' else 'تصویری'}",
                  ""]
        btns.append([{"text": f"{mark}{_short(t.get('name'), 30)}",
                      "callback_data": f"cc_settpl_{iss['id']}_{t['id']}"}])
    btns.append([{"text": "📄 مدیریت قالب‌ها", "callback_data": "ct_panel"}])
    btns.append([{"text": "🔙 بازگشت",
                  "callback_data": f"cc_v_{iss['id']}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_template(cid, uid, iid, tid):
    if not _guard(cid, uid):
        return
    db_execute("UPDATE cert_issues SET template_id=? WHERE id=?",
               (int(tid), int(iid)))
    scan_template(tid)
    show_issue(cid, uid, iid, "✅ قالب انتخاب شد")


def show_params(cid, uid, iid):
    """🧩 گام ۲ — پر کردن پارامترها"""
    from bale_api import send_or_edit
    import certgen as cg
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return show_home(cid, uid, "❌ طرح یافت نشد")
    tid = iss.get("template_id")
    if not tid:
        return show_issue(cid, uid, iid, "⚠️ اول قالب را انتخاب کنید")

    ask, auto, imgs = template_fields(tid)
    vals = issue_values(iss)

    # 📌 ثابت‌ها و 🤖 سیستمی‌ها را جدا نشان بده
    fixed = [k for k in ask if field_kind(k) == "fixed"]
    system = [k for k in ask if field_kind(k) == "system"]

    n_f = sum(1 for k in fixed if str(vals.get(k) or "").strip())
    lines = ["🧩 دادهٔ گواهینامه", "━━━━━━━━━━━━━━", "",
             f"📌 ثابت: {_fa(n_f)} از {_fa(len(fixed))} پر شده", ""]
    btns = []

    if fixed:
        lines += ["📌 برای همه یکسان — شما پر می‌کنید:", ""]
        for k in fixed:
            v = str(vals.get(k) or "").strip()
            mark = "🟢" if v else "⚪"
            lines.append(f"{mark} {cg.ph_icon(k)} {cg.ph_label(k)}: "
                         f"{_short(v, 20) if v else '—'}")
            btns.append([{"text": f"{cg.ph_icon(k)} "
                                  f"{cg.ph_label(k)}: "
                                  f"{_short(v, 12) if v else '—'}"[:34],
                          "callback_data": f"cc_pe_{iss['id']}_{k}"}])
        lines.append("")
    else:
        lines += ["✅ این قالب پارامتر ثابتی ندارد.", ""]

    if system:
        lines += ["🤖 ربات می‌سازد — خالی بگذارید:", ""]
        for k in system:
            v = str(vals.get(k) or "").strip()
            mark = "✏️" if v else "🤖"
            shown = _short(v, 20) if v else "خودکار"
            lines.append(f"{mark} {cg.ph_icon(k)} {cg.ph_label(k)}: "
                         f"{shown}")
            btns.append([{"text": f"{mark} {cg.ph_label(k)}: "
                                  f"{_short(v, 12) if v else 'خودکار'}"[:34],
                          "callback_data": f"cc_pe_{iss['id']}_{k}"}])
        lines += ["", "💡 اگر مقدار بدهید، همان روی گواهینامه",
                  "   می‌نشیند و ربات دخالتی نمی‌کند.", ""]

    if auto:
        lines += ["🔁 برای هر نفر فرق دارد — خودکار:", ""]
        nm = "، ".join(cg.ph_label(k) for k in auto)
        lines += [f"   {nm}", ""]
    if imgs:
        lines += ["🖼️ تصاویر:", ""]
        for k in imgs:
            src = ("خودکار" if k in ("qr", "barcode")
                   else "عکس پروفایل" if k == "photo"
                   else "از تنظیمات تصاویر")
            lines.append(f"   {cg.ph_icon(k)} {cg.ph_label(k)} — {src}")
        lines.append("")

    if fixed:
        btns.append([{"text": "⚡ پر کردن پشت‌سرهم",
                      "callback_data": f"cc_wiz_{iss['id']}"}])
    btns.append([{"text": "🔙 بازگشت",
                  "callback_data": f"cc_v_{iss['id']}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_param(cid, uid, iid, key):
    """✍️ ورودی یک پارامتر"""
    from bale_api import send, kb_cancel
    from auth import set_state
    import certgen as cg
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return
    vals = issue_values(iss)
    cur = str(vals.get(key) or "")
    set_state(uid, "cc_param", {"iid": int(iid), "key": key},
              merge=False)
    hint = cg.ph_desc(key)
    lines = [f"✍️ {cg.ph_icon(key)} {cg.ph_label(key)}",
             "━━━━━━━━━━━━━━", ""]
    if hint:
        lines += [f"💡 {hint}", ""]
    if cur:
        lines += [f"📄 مقدار فعلی: {cur}", ""]
    lines += ["مقدار تازه را بنویسید:", "",
              "🗑️ برای خالی‌کردن، یک خط تیره «-» بفرستید."]
    send(cid, "\n".join(lines), kb_cancel())


def show_audience(cid, uid, iid):
    """👥 گام ۳ — انتخاب گیرندگان"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return show_home(cid, uid, "❌ طرح یافت نشد")
    n = db_scalar("SELECT COUNT(*) FROM cert_shares WHERE issue_id=?",
                  (iss["id"],)) or 0
    cur = iss.get("audience") or ""
    ref = iss.get("audience_ref") or ""

    lines = ["👥 گیرندگان گواهینامه", "━━━━━━━━━━━━━━", ""]
    if n:
        a = AUDIENCES.get(cur, ("", "نامشخص"))
        lines += [f"✅ الان {_fa(n)} نفر انتخاب شده‌اند",
                  f"   {a[0]} {a[1]}", ""]
        # نمونهٔ چند نفر
        sample = shares(iid, limit=5)
        if sample:
            lines.append("نمونه:")
            for s in sample:
                lines.append(f"   • {s.get('full_name') or '—'}"
                             f"{'  🔗' if s.get('bale_user_id') else '  ⚠️ بدون حساب'}")
            if n > 5:
                lines.append(f"   … و {_fa(n - 5)} نفر دیگر")
            lines.append("")
    else:
        lines += ["📭 هنوز کسی انتخاب نشده.", "",
                  "از کجا بیاوریم؟", ""]
    for k, (ic, t) in AUDIENCES.items():
        lines.append(f"{ic} {t}")

    btns = [
        [{"text": "🎉 از یک رویداد",
          "callback_data": f"cc_ae_{iss['id']}"},
         {"text": "🏷️ از یک دسته",
          "callback_data": f"cc_as_{iss['id']}"}],
        [{"text": "🔍 جستجوی کاربران",
          "callback_data": f"cc_asr_{iss['id']}"},
         {"text": "✍️ افزودن دستی",
          "callback_data": f"cc_amn_{iss['id']}"}],
        [{"text": "📊 از فایل اکسل",
          "callback_data": f"cc_ax_{iss['id']}"},
         {"text": "📥 نمونهٔ اکسل",
          "callback_data": f"cc_xs_{iss['id']}"}],
    ]
    if n:
        btns.append([{"text": f"📋 فهرست کامل ({_fa(n)})",
                      "callback_data": f"cc_alist_{iss['id']}_0"}])
        btns.append([{"text": "🗑️ پاک‌کردن فهرست",
                      "callback_data": f"cc_aclr_{iss['id']}"}])
    btns.append([{"text": "🔙 بازگشت",
                  "callback_data": f"cc_v_{iss['id']}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def pick_event(cid, uid, iid, page=0):
    """🎉 انتخاب رویداد"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    rows = db_execute(
        "SELECT e.id, e.title, "
        "(SELECT COUNT(*) FROM event_registrations r "
        " WHERE r.event_id=e.id AND r.status IN ('confirmed','attended')) "
        "AS n FROM events e ORDER BY e.id DESC LIMIT 40",
        fetch="all") or []
    rows = [r for r in rows if (r.get("n") or 0) > 0]
    per = 8
    pages = max(1, (len(rows) + per - 1) // per)
    page = max(0, min(page, pages - 1))
    chunk = rows[page * per:(page + 1) * per]

    lines = ["🎉 کدام رویداد؟", "━━━━━━━━━━━━━━", ""]
    if not chunk:
        lines += ["📭 رویدادی با ثبت‌نام تأییدشده پیدا نشد."]
    btns = []
    for r in chunk:
        lines.append(f"🎉 {r['title']} — {_fa(r['n'])} نفر")
        btns.append([{"text": f"{_short(r['title'], 26)} "
                              f"({_fa(r['n'])})",
                      "callback_data": f"cc_sete_{iid}_{r['id']}"}])
    nav = []
    if page > 0:
        nav.append({"text": "◀️", "callback_data":
                    f"cc_aep_{iid}_{page - 1}"})
    if page < pages - 1:
        nav.append({"text": "▶️", "callback_data":
                    f"cc_aep_{iid}_{page + 1}"})
    if nav:
        btns.append(nav)
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"cc_aud_{iid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def pick_segment(cid, uid, iid):
    """🏷️ انتخاب دسته"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    lines = ["🏷️ کدام دسته؟", "━━━━━━━━━━━━━━", ""]
    btns = []
    for k, (ic, t, where) in SEGMENTS.items():
        try:
            n = db_scalar(f"SELECT COUNT(*) FROM users "
                          f"WHERE {where} AND is_blocked=0") or 0
        except Exception:
            n = 0
        lines.append(f"{ic} {t} — {_fa(n)} نفر")
        btns.append([{"text": f"{ic} {t} ({_fa(n)})"[:34],
                      "callback_data": f"cc_sets_{iid}_{k}"}])
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"cc_aud_{iid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def set_event(cid, uid, iid, eid):
    if not _guard(cid, uid):
        return
    clear_shares(iid)
    n = fill_from_event(iid, eid)
    show_issue(cid, uid, iid, f"✅ {_fa(n)} نفر از رویداد اضافه شدند")


def set_segment(cid, uid, iid, seg):
    if not _guard(cid, uid):
        return
    # 🛡️ فاز ۴۰: شناسهٔ طرح باید عدد باشد
    try:
        iid = int(iid)
    except (TypeError, ValueError):
        from bale_api import send
        return send(cid, "🌱 این طرح دیگر معتبر نیست")
    clear_shares(iid)
    n = fill_from_segment(iid, seg)
    show_issue(cid, uid, iid, f"✅ {_fa(n)} نفر از دسته اضافه شدند")


def clear_audience(cid, uid, iid):
    if not _guard(cid, uid):
        return
    clear_shares(iid)
    show_audience(cid, uid, iid)


def ask_excel(cid, uid, iid):
    """📊 گام ۳ج — اکسل"""
    from bale_api import send, kb_cancel
    from auth import set_state
    if not _guard(cid, uid):
        return
    set_state(uid, "cc_excel", {"iid": int(iid)}, merge=False)
    send(cid, (
        "📊 فهرست اکسل\n"
        "━━━━━━━━━━━━━━\n\n"
        "فایل xlsx را همین‌جا بفرستید.\n\n"
        "📋 ستون‌های شناخته‌شده:\n"
        "   • نام و نام خانوادگی  (الزامی)\n"
        "   • کد ملی\n"
        "   • موبایل\n"
        "   • هر ستون دیگری که نامش با یک پارامتر\n"
        "     قالب بخواند — مثلاً «نمره» یا «ساعت»\n\n"
        "💡 سطر اول باید عنوان ستون‌ها باشد.\n\n"
        "🔗 اگر کد ملی یا موبایل با حساب کاربری بخواند،\n"
        "   گواهینامه خودکار به پروفایلش وصل می‌شود."
    ), kb_cancel())


def show_share_list(cid, uid, iid, page=0):
    """📋 فهرست کامل گیرندگان"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    rows = shares(iid)
    per = 12
    pages = max(1, (len(rows) + per - 1) // per)
    page = max(0, min(page, pages - 1))
    chunk = rows[page * per:(page + 1) * per]

    lines = [f"📋 گیرندگان ({_fa(len(rows))})",
             "━━━━━━━━━━━━━━", ""]
    for i, s in enumerate(chunk, page * per + 1):
        st = {"built": "✅", "failed": "❌"}.get(s.get("state"), "⏳")
        who = s.get("full_name") or "—"
        tag = "" if s.get("bale_user_id") else " ⚠️"
        lines.append(f"{_fa(i)}. {st} {who}{tag}")
    if not rows:
        lines.append("📭 خالی")
    lines += ["", "✅ دریافت‌کرده · ⏳ در انتظار · ⚠️ بدون حساب ربات"]

    btns = []
    nav = []
    if page > 0:
        nav.append({"text": "◀️",
                    "callback_data": f"cc_alist_{iid}_{page - 1}"})
    if page < pages - 1:
        nav.append({"text": "▶️",
                    "callback_data": f"cc_alist_{iid}_{page + 1}"})
    if nav:
        btns.append(nav)
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"cc_aud_{iid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_preview(cid, uid, iid):
    """
    👁️ گام ۴ — پیش‌نمایش تصادفی

    🎯 «یه پیشنمایش تصادفی به من نشون بده»
    """
    from bale_api import send, send_photo, send_document
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return show_home(cid, uid, "❌ طرح یافت نشد")

    send(cid, "⏳ در حال ساخت پیش‌نمایش…")
    try:
        n = int(get_setting("cc_preview_n", "1") or 1)
    except (TypeError, ValueError):
        n = 1
    n = max(1, min(n, 5))

    done = 0
    for _ in range(n):
        files, err = preview(iid)
        if err or not files:
            send(cid, f"❌ {err or 'ناموفق'}", {"inline_keyboard": [
                [{"text": "🔙 بازگشت",
                  "callback_data": f"cc_v_{iid}"}]]})
            return
        who = files.get("_who") or {}
        cap = (f"👁️ پیش‌نمایش — {who.get('full_name') or '—'}\n"
               f"🔖 {who.get('person_code') or ''}")
        if files.get("png"):
            send_photo(cid, files["png"], cap[:200])
        elif files.get("pdf"):
            send_document(cid, files["pdf"], cap[:200])
        done += 1

    lines = ["👁️ پیش‌نمایش آماده شد", "━━━━━━━━━━━━━━", "",
             f"🎲 {_fa(done)} نفر تصادفی از فهرست", "",
             "✅ اگر درست است، «📢 انتشار» بزنید.",
             "✏️ اگر نه، پارامترها یا قالب را عوض کنید."]
    send(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔄 یکی دیگر", "callback_data": f"cc_prev_{iid}"}],
        [{"text": "🧩 پارامترها", "callback_data": f"cc_ph_{iid}"}],
        [{"text": "📢 انتشار و اعلان",
          "callback_data": f"cc_pubc_{iid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"cc_v_{iid}"}]]})


def confirm_publish(cid, uid, iid):
    """📢 تأیید انتشار"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return show_home(cid, uid, "❌ طرح یافت نشد")
    ok, todo = issue_ready(iss)
    if not ok:
        return show_issue(cid, uid, iid,
                          "⚠️ " + "؛ ".join(todo))
    n = db_scalar("SELECT COUNT(*) FROM cert_shares WHERE issue_id=?",
                  (iss["id"],)) or 0
    n_bot = db_scalar("SELECT COUNT(*) FROM cert_shares "
                      "WHERE issue_id=? AND bale_user_id IS NOT NULL",
                      (iss["id"],)) or 0
    title = (iss.get("notify_title") or "").strip() or get_setting(
        "cc_notify_title", "🎓 گواهینامهٔ شما آماده است!")

    lines = ["📢 انتشار طرح", "━━━━━━━━━━━━━━", "",
             f"🗂️ {iss.get('title')}", "",
             f"👥 گیرندگان: {_fa(n)} نفر",
             f"🔔 اعلان می‌رود به: {_fa(n_bot)} نفر"]
    if n - n_bot:
        lines.append(f"⚠️ {_fa(n - n_bot)} نفر حساب ربات ندارند —")
        lines.append("   با لینک دریافت می‌توانند بگیرند.")
    lines += ["", "✉️ متن اعلان:", f"   {title}", "",
              "━━━━━━━━━━━━━━",
              "💡 گواهینامه‌ها همین حالا ساخته نمی‌شوند.",
              "   هر کاربر که اقدام کند، همان لحظه ساخته",
              "   و تحویل داده می‌شود — بدون فشار به سیستم.",
              "", "تأیید می‌کنید؟"]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "✅ بله، منتشر کن",
          "callback_data": f"cc_pubY_{iid}"}],
        [{"text": "✉️ اول متن اعلان را عوض کنم",
          "callback_data": f"cc_msg_{iid}"}],
        [{"text": "🔙 انصراف", "callback_data": f"cc_v_{iid}"}]]})


def do_publish(cid, uid, iid):
    """✅ انتشار واقعی"""
    from bale_api import send
    if not _guard(cid, uid):
        return
    send(cid, "⏳ در حال ارسال اعلان‌ها…")
    n, err = publish(iid, notify=True)
    if err:
        return show_issue(cid, uid, iid, f"❌ {err}")
    show_issue(cid, uid, iid,
               f"🎉 منتشر شد — {_fa(n)} اعلان فرستاده شد")


def renotify(cid, uid, iid):
    """🔔 اعلان دوباره به کسانی که هنوز نگرفته‌اند"""
    from bale_api import send
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return
    rows = [s for s in shares(iid)
            if s.get("bale_user_id") and s.get("state") != "built"]
    if not rows:
        return show_issue(cid, uid, iid, "✅ همه دریافت کرده‌اند")
    db_execute("UPDATE cert_shares SET notified=0 WHERE issue_id=? "
               "AND state<>'built'", (int(iid),))
    n, err = publish(iid, notify=True)
    show_issue(cid, uid, iid,
               f"🔔 {_fa(n)} یادآوری فرستاده شد")


def show_report(cid, uid, iid):
    """📊 وضعیت یک طرح"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return show_home(cid, uid, "❌ طرح یافت نشد")
    rows = shares(iid)
    built = [s for s in rows if s.get("state") == "built"]
    failed = [s for s in rows if s.get("state") == "failed"]
    nobot = [s for s in rows if not s.get("bale_user_id")]
    waiting = [s for s in rows
               if s.get("state") == "ready" and s.get("bale_user_id")]

    pct = int(len(built) * 100 / max(1, len(rows)))
    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)

    lines = [f"📊 {iss.get('title')}", "━━━━━━━━━━━━━━", "",
             f"{bar}  {_fa(pct)}٪", "",
             f"👥 کل: {_fa(len(rows))}",
             f"✅ دریافت‌کرده: {_fa(len(built))}",
             f"⏳ در انتظار: {_fa(len(waiting))}",
             f"⚠️ بدون حساب ربات: {_fa(len(nobot))}"]
    if failed:
        lines.append(f"❌ ناموفق: {_fa(len(failed))}")
    lines += ["", f"📅 انتشار: "
              f"{_jd.fmt(iss.get('published_at'), 'datetime')}"]
    lk = link_of(iss)
    if lk:
        lines += ["", "🔗 لینک دریافت:", lk]

    btns = [[{"text": "📋 فهرست کامل",
              "callback_data": f"cc_alist_{iid}_0"}],
            [{"text": "🔔 یادآوری به نگرفته‌ها",
              "callback_data": f"cc_renot_{iid}"}],
            [{"text": "🔙 بازگشت", "callback_data": f"cc_v_{iid}"}]]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_link(cid, uid, iid):
    """🔗 لینک دریافت"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return
    lk = link_of(iss)
    lines = ["🔗 لینک دریافت گواهینامه", "━━━━━━━━━━━━━━", ""]
    if lk:
        lines += [lk, "",
                  "💡 هرکس این لینک را باز کند و کد ملی‌اش در",
                  "   فهرست باشد، گواهینامه‌اش را می‌گیرد.", "",
                  "🔒 اگر در فهرست نباشد، چیزی دریافت نمی‌کند."]
    else:
        lines += ["⚠️ لینک خاموش است.", "",
                  "از تنظیمات مرکز روشنش کنید."]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": f"cc_v_{iid}"}]]})


def toggle_photo(cid, uid, iid):
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return
    cur = str(iss.get("auto_photo") or "1") == "1"
    db_execute("UPDATE cert_issues SET auto_photo=? WHERE id=?",
               (0 if cur else 1, int(iid)))
    show_issue(cid, uid, iid,
               f"📷 عکس پرسنلی خودکار {'خاموش' if cur else 'روشن'} شد")


def why_blocked(cid, uid, iid):
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    ok, todo = issue_ready(iss)
    lines = ["🔒 هنوز آمادهٔ انتشار نیست", "━━━━━━━━━━━━━━", "",
             "این‌ها مانده:", ""]
    lines += [f"   • {t}" for t in todo]
    lines += ["", "💡 بعد از رفع، دکمهٔ «📢 انتشار» ظاهر می‌شود."]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": f"cc_v_{iid}"}]]})


def confirm_delete(cid, uid, iid):
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return
    n = db_scalar("SELECT COUNT(*) FROM cert_shares WHERE issue_id=?",
                  (int(iid),)) or 0
    b = iss.get("built") or 0
    lines = ["🗑️ حذف طرح", "━━━━━━━━━━━━━━", "",
             f"🗂️ {iss.get('title')}",
             f"👥 {_fa(n)} گیرنده · 🎓 {_fa(b)} صادرشده", ""]
    if b:
        lines += ["⚠️ گواهینامه‌های صادرشده **پاک نمی‌شوند** و",
                  "   در پروفایل کاربران می‌مانند.", ""]
    lines.append("مطمئنید؟")
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🗑️ بله، حذف کن",
          "callback_data": f"cc_delY_{iid}"}],
        [{"text": "🔙 انصراف", "callback_data": f"cc_v_{iid}"}]]})


def do_delete(cid, uid, iid):
    if not _guard(cid, uid):
        return
    db_execute("DELETE FROM cert_shares WHERE issue_id=?", (int(iid),))
    db_execute("DELETE FROM cert_issues WHERE id=?", (int(iid),))
    show_home(cid, uid, "🗑️ طرح حذف شد")


# ══════════════════════════════════════════════════════════
# 👤 سمت کاربر
# ══════════════════════════════════════════════════════════
def user_get(cid, uid, share_id):
    """
    🎓 کاربر روی «دریافت گواهینامه» زد — همین حالا بساز.

    🎯 «هروقت کاربر ساخت میره تو پروفایلش میسازه و دانلود میکنه»
    """
    from bale_api import send
    sh = db_execute("SELECT * FROM cert_shares WHERE id=?",
                    (int(share_id),), fetch="one")
    if not sh:
        return send(cid, "❌ یافت نشد")
    if sh.get("bale_user_id") and sh["bale_user_id"] != uid:
        from auth import is_admin
        if not is_admin(uid):
            return send(cid, "❌ این گواهینامه برای شما نیست")

    iss = get_issue(sh.get("issue_id"))
    if not iss or iss.get("status") != "published":
        return send(cid, "⏳ این گواهینامه هنوز منتشر نشده است")

    send(cid, "⏳ گواهینامه‌تان در حال آماده‌سازی است…")
    cert, err = build_one(sh["issue_id"], sh["id"], notify=False)
    if not cert:
        return send(cid, f"❌ ساخت ناموفق بود\n\n{err}",
                    {"inline_keyboard": [
                        [{"text": "🔄 تلاش دوباره",
                          "callback_data": f"ccget_{sh['id']}"}]]})
    try:
        import certissue
        certissue.send_cert_files(uid, cert, None)
    except Exception as e:
        log(f"⚠️ ارسال: {e}")
        send(cid, "✅ ساخته شد — از «گواهینامه‌های من» ببینید")


def claim_by_link(cid, uid, token, user=None):
    """
    🔗 ورود با لینک عمومی

    اگر کاربر در فهرست گیرندگان باشد، وصل می‌شود.
    """
    from bale_api import send
    iss = by_token(token)
    if not iss:
        return send(cid, "❌ این لینک معتبر نیست")
    if iss.get("status") != "published":
        return send(cid, "⏳ این گواهینامه هنوز منتشر نشده است")

    u = user or db_execute("SELECT * FROM users WHERE bale_user_id=?",
                           (uid,), fetch="one") or {}
    nid = (u.get("national_id") or "").strip()
    mob = (u.get("mobile") or "").strip()

    sh = db_execute("SELECT * FROM cert_shares WHERE issue_id=? "
                    "AND bale_user_id=?", (iss["id"], uid), fetch="one")
    if not sh and nid:
        sh = db_execute("SELECT * FROM cert_shares WHERE issue_id=? "
                        "AND national_id=? AND national_id<>''",
                        (iss["id"], nid), fetch="one")
    if not sh and mob:
        sh = db_execute("SELECT * FROM cert_shares WHERE issue_id=? "
                        "AND mobile=? AND mobile<>''",
                        (iss["id"], mob), fetch="one")
    if not sh:
        return send(cid, (
            "🌱 نام شما در این فهرست نیست\n"
            "━━━━━━━━━━━━━━\n\n"
            f"🗂️ {iss.get('title')}\n\n"
            "💡 اگر فکر می‌کنید اشتباهی رخ داده، پروفایلتان\n"
            "   را کامل کنید (کد ملی و موبایل) و دوباره\n"
            "   امتحان کنید."
        ), {"inline_keyboard": [
            [{"text": "👤 پروفایل من", "callback_data": "profile_view"}]]})

    if not sh.get("bale_user_id"):
        db_execute("UPDATE cert_shares SET bale_user_id=? WHERE id=?",
                   (uid, sh["id"]))
    return user_get(cid, uid, sh["id"])


# ══════════════════════════════════════════════════════════
# ⌨️ ورودی‌ها
# ══════════════════════════════════════════════════════════
def handle_text(message):
    """📝 ورودی متنی مرکز صدور"""
    from bale_api import send, kb_remove
    from auth import (get_state_data, get_state_name,
                      clear_state, set_state)
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    txt = (message.get("text") or "").strip()

    # 🔴 باگ رفع‌شده (فاز ۳۹): get_state_data فقط **دیکشنری**

    #    برمی‌گرداند، نه (نام، داده). این unpack غلط بود و

    #    ValueError می‌داد — یعنی هیچ ورودی متنی پردازش

    #    نمی‌شد. نام state را جدا می‌گیریم.

    st = get_state_name(uid)

    data = get_state_data(uid)
    if not st or not st.startswith("cc_"):
        return False
    if txt in ("انصراف", "❌ انصراف", "/cancel", "لغو", "🔙 بازگشت"):
        clear_state(uid)
        send(cid, "✅ لغو شد", kb_remove())
        iid = (data or {}).get("iid")
        if iid:
            show_issue(cid, uid, iid)
        else:
            show_home(cid, uid)
        return True

    # ── نام طرح تازه ──
    if st == "cc_title":
        if len(txt) < 3:
            send(cid, "⚠️ نام خیلی کوتاه است — دست‌کم ۳ حرف")
            return True
        rows = db_execute("SELECT id FROM cert_templates "
                          "WHERE is_active=1 ORDER BY is_default DESC, "
                          "id DESC LIMIT 1", fetch="one")
        iid = create_issue(uid, txt, (rows or {}).get("id") or 0)
        clear_state(uid)
        send(cid, "✅ طرح ساخته شد", kb_remove())
        if rows:
            scan_template(rows["id"])
        show_issue(cid, uid, iid,
                   "🎉 طرح تازه آماده است — گام بعد: پارامترها")
        return True

    # ── تغییر نام ──
    if st == "cc_rename":
        iid = data.get("iid")
        if len(txt) < 3:
            send(cid, "⚠️ نام خیلی کوتاه است")
            return True
        db_execute("UPDATE cert_issues SET title=? WHERE id=?",
                   (txt[:120], int(iid)))
        clear_state(uid)
        send(cid, "✅ نام عوض شد", kb_remove())
        show_issue(cid, uid, iid)
        return True

    # ── ✍️ افزودن دستی ──
    if st == "cc_manual":
        manual_input(cid, uid, txt)
        return True

    # ── 🔍 جستجوی کاربران ──
    if st == "cc_search":
        search_input(cid, uid, txt)
        return True

    # ── ⚡ پر کردن پشت‌سرهم ──
    if st == "cc_wiz":
        wizard_input(cid, uid, txt)
        return True

    # ── مقدار یک پارامتر ──
    if st == "cc_param":
        iid, key = data.get("iid"), data.get("key")
        set_value(iid, key, "" if txt == "-" else txt[:300])
        clear_state(uid)
        send(cid, "✅ ثبت شد", kb_remove())
        show_params(cid, uid, iid)
        return True

    # ── شمارهٔ نامه ──
    if st == "cc_docno":
        iid = data.get("iid")
        db_execute("UPDATE cert_issues SET doc_no=? WHERE id=?",
                   ("" if txt == "-" else txt[:80], int(iid)))
        clear_state(uid)
        send(cid, "✅ ثبت شد", kb_remove())
        show_issue(cid, uid, iid)
        return True

    # ── متن اعلان ──
    if st == "cc_msgt":
        iid = data.get("iid")
        db_execute("UPDATE cert_issues SET notify_title=? WHERE id=?",
                   ("" if txt == "-" else txt[:200], int(iid)))
        clear_state(uid)
        send(cid, "✅ عنوان اعلان ثبت شد", kb_remove())
        show_msg(cid, uid, iid)
        return True

    if st == "cc_msgb":
        iid = data.get("iid")
        db_execute("UPDATE cert_issues SET notify_body=? WHERE id=?",
                   ("" if txt == "-" else txt[:600], int(iid)))
        clear_state(uid)
        send(cid, "✅ متن اعلان ثبت شد", kb_remove())
        show_msg(cid, uid, iid)
        return True

    # ── تنظیمات مرکز ──
    if st == "cc_setv":
        key = data.get("key")
        row = next((r for r in CC_SETTINGS if r[0] == key), None)
        if not row:
            clear_state(uid)
            return True
        val = "" if txt == "-" else txt[:300]
        if row[3] == "num":
            digits = "".join(c for c in _jd.en(txt) if c.isdigit())
            if not digits:
                send(cid, "⚠️ فقط عدد بفرستید")
                return True
            val = str(int(digits))
        set_setting(key, val, row[2], "certificate", uid)
        clear_state(uid)
        send(cid, "✅ ثبت شد", kb_remove())
        show_settings(cid, uid)
        return True

    # ── تنظیم عکس پرسنلی ──
    if st == "cc_photov":
        import certphoto as cp
        key = data.get("key")
        row = next((r for r in cp.PHOTO_SETTINGS if r[0] == key), None)
        if not row:
            clear_state(uid)
            return True
        val = txt.strip()[:40]
        if key in ("cert_photo_bg", "cert_photo_fg"):
            v = val.lstrip("#")
            if len(v) != 6 or any(c not in "0123456789abcdefABCDEF"
                                  for c in v):
                send(cid, "⚠️ کد رنگ شش‌رقمی بفرستید — مثال: #EEF1F4")
                return True
            val = "#" + v.upper()
            # کش آدمک را نو کن
            try:
                cp.SILHOUETTE.unlink(missing_ok=True)
            except Exception:
                pass
        set_setting(key, val, row[2], "certificate", uid)
        clear_state(uid)
        send(cid, "✅ ثبت شد", kb_remove())
        show_photo_panel(cid, uid)
        return True

    if st == "cc_excel":
        send(cid, "⚠️ لطفاً فایل اکسل بفرستید یا «انصراف» بزنید")
        return True

    return False


def handle_document(message):
    """📊 دریافت اکسل گیرندگان"""
    from bale_api import send, kb_remove
    from auth import (get_state_data, get_state_name,
                      clear_state)
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    # 🔴 باگ رفع‌شده (فاز ۳۹): get_state_data فقط **دیکشنری**
    #    برمی‌گرداند، نه (نام، داده). این unpack غلط بود و
    #    ValueError می‌داد — یعنی هیچ ورودی متنی پردازش
    #    نمی‌شد. نام state را جدا می‌گیریم.
    st = get_state_name(uid)
    data = get_state_data(uid)
    if st != "cc_excel":
        return False

    iid = (data or {}).get("iid")
    doc = message.get("document") or {}
    fname = str(doc.get("file_name") or "").lower()
    if not fname.endswith((".xlsx", ".xlsm")):
        send(cid, "⚠️ فقط فایل اکسل (xlsx) قبول است")
        return True

    try:
        from bale_api import get_file_info, download_file
        fi = get_file_info(doc.get("file_id")) or {}
        fpath = (fi.get("result") or {}).get("file_path")
        if not fpath:
            send(cid, "❌ آدرس فایل از بله دریافت نشد")
            return True
        content = download_file(fpath)
        if not content:
            send(cid, "❌ دانلود ناموفق بود")
            return True
        from config import FILES_DIR
        d = Path(FILES_DIR) / "cert_center"
        d.mkdir(parents=True, exist_ok=True)
        dest = d / f"in_{uid}_{secrets.token_hex(3)}.xlsx"
        dest.write_bytes(content)
    except Exception as e:
        log(f"⚠️ دریافت اکسل مرکز: {e}")
        send(cid, f"❌ دریافت فایل: {user_error_message(e)}")
        return True

    import certbatch
    rows, cmap, errs = certbatch.parse_excel(dest)
    if not rows:
        msg = ["❌ هیچ ردیف معتبری پیدا نشد", "━━━━━━━━━━━━━━", ""]
        if errs:
            msg += [f"   • {e}" for e in errs[:8]]
        msg += ["", "💡 سطر اول باید عنوان ستون‌ها باشد و",
                "   دست‌کم یک ستون «نام» داشته باشد."]
        send(cid, "\n".join(msg))
        return True

    clear_state(uid)
    clear_shares(iid)
    n = fill_from_rows(iid, rows)
    linked = db_scalar("SELECT COUNT(*) FROM cert_shares WHERE "
                       "issue_id=? AND bale_user_id IS NOT NULL",
                       (int(iid),)) or 0
    note = [f"✅ {_fa(n)} نفر از اکسل اضافه شدند",
            f"🔗 {_fa(linked)} نفر به حساب ربات وصل شدند"]
    if errs:
        note.append(f"⚠️ {_fa(len(errs))} هشدار")
    send(cid, "\n".join(note), kb_remove())
    show_issue(cid, uid, iid)
    return True


def start_rename(cid, uid, iid):
    from bale_api import send, kb_cancel
    from auth import set_state
    if not _guard(cid, uid):
        return
    set_state(uid, "cc_rename", {"iid": int(iid)}, merge=False)
    send(cid, "✏️ نام تازهٔ طرح را بنویسید:", kb_cancel())


def start_docno(cid, uid, iid):
    from bale_api import send, kb_cancel
    from auth import set_state
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    cur = (iss or {}).get("doc_no") or get_setting("cert_doc_no", "")
    set_state(uid, "cc_docno", {"iid": int(iid)}, merge=False)
    send(cid, (
        "🔖 شمارهٔ نامه\n"
        "━━━━━━━━━━━━━━\n\n"
        f"📄 فعلی: {cur or '—'}\n\n"
        "شمارهٔ نامهٔ این طرح را بنویسید:\n\n"
        "مثال: ۱۴۲۱/۵۴۷۲/۵۰۰۰/د\n\n"
        "💡 این شماره برای همه یکسان است. کد فردی هر نفر\n"
        "   خودکار به آن اضافه می‌شود:\n"
        "   ۱۴۲۱/۵۴۷۲/۵۰۰۰/د-A7K2M9\n\n"
        "🗑️ برای خالی‌کردن «-» بفرستید."
    ), kb_cancel())


def show_msg(cid, uid, iid):
    """✉️ متن اعلان"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return
    t = (iss.get("notify_title") or "").strip()
    b = (iss.get("notify_body") or "").strip()
    dt = get_setting("cc_notify_title", "🎓 گواهینامهٔ شما آماده است!")
    db_ = get_setting("cc_notify_body",
                      "می‌توانید از پروفایلتان آن را دریافت کنید 💚")

    lines = ["✉️ متن اعلان", "━━━━━━━━━━━━━━", "",
             "این پیام هنگام انتشار برای گیرندگان می‌رود:", "",
             "┌─────────────",
             f"│ {t or dt}",
             "│ ━━━━━━━━━━",
             f"│ 🎉 {iss.get('title')}",
             f"│ {b or db_}",
             f"│ 📅 {_jd.today_str()}",
             "└─────────────", ""]
    if not t:
        lines.append("💡 عنوان از تنظیمات کلی می‌آید")
    if not b:
        lines.append("💡 متن از تنظیمات کلی می‌آید")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "📢 عنوان اعلان", "callback_data": f"cc_msgt_{iid}"}],
        [{"text": "💬 متن اعلان", "callback_data": f"cc_msgb_{iid}"}],
        [{"text": "🔙 بازگشت", "callback_data": f"cc_v_{iid}"}]]})


def start_msg(cid, uid, iid, part):
    from bale_api import send, kb_cancel
    from auth import set_state
    if not _guard(cid, uid):
        return
    set_state(uid, f"cc_msg{part}", {"iid": int(iid)}, merge=False)
    what = "عنوان" if part == "t" else "متن"
    send(cid, (
        f"✉️ {what} اعلان\n"
        "━━━━━━━━━━━━━━\n\n"
        f"{what} تازه را بنویسید:\n\n"
        "🗑️ برای برگشت به پیش‌فرض «-» بفرستید."
    ), kb_cancel())


def show_settings(cid, uid):
    """⚙️ تنظیمات مرکز"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    lines = ["⚙️ تنظیمات مرکز صدور", "━━━━━━━━━━━━━━", ""]
    btns = []
    for key, icon, name, kind, dflt, hint in CC_SETTINGS:
        v = get_setting(key, dflt)
        if kind == "bool":
            on = str(v) == "1"
            lines.append(f"{'🟢' if on else '⚪'} {icon} {name}")
            btns.append([{"text": f"{'✅' if on else '❌'} {icon} {name}"[:34],
                          "callback_data": f"ccsb_{key}"}])
        else:
            shown = str(v).strip() or "—"
            lines.append(f"▫️ {icon} {name}: {_short(shown, 24)}")
            btns.append([{"text": f"{icon} {name}: {_short(shown, 12)}"[:34],
                          "callback_data": f"ccse_{key}"}])
    lines += ["", "📷 تنظیمات عکس پرسنلی جداست 👇"]
    btns.append([{"text": "📷 عکس پرسنلی", "callback_data": "cc_photo"}])
    btns.append([{"text": "🔙 مرکز صدور", "callback_data": "cc_home"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_setting(cid, uid, key):
    if not _guard(cid, uid):
        return
    row = next((r for r in CC_SETTINGS if r[0] == key), None)
    if not row or row[3] != "bool":
        return
    cur = get_setting(key, row[4]) == "1"
    set_setting(key, "0" if cur else "1", row[2], "certificate", uid)
    show_settings(cid, uid)


def start_setting(cid, uid, key):
    from bale_api import send, kb_cancel
    from auth import set_state
    if not _guard(cid, uid):
        return
    row = next((r for r in CC_SETTINGS if r[0] == key), None)
    if not row:
        return
    _, icon, name, kind, dflt, hint = row
    cur = get_setting(key, dflt)
    set_state(uid, "cc_setv", {"key": key}, merge=False)
    lines = [f"{icon} {name}", "━━━━━━━━━━━━━━", ""]
    if hint:
        lines += [f"💡 {hint}", ""]
    lines += [f"📄 فعلی: {cur or '—'}", "", "مقدار تازه را بنویسید:"]
    if kind == "num":
        lines.append("(فقط عدد)")
    send(cid, "\n".join(lines), kb_cancel())


def show_photo_panel(cid, uid):
    """📷 پنل عکس پرسنلی"""
    from bale_api import send_or_edit, send_photo
    if not _guard(cid, uid):
        return
    import certphoto as cp
    s = cp.stats()
    lines = ["📷 عکس پرسنلی گواهینامه", "━━━━━━━━━━━━━━", "",
             "اگر قالب پارامتر {عکس} داشته باشد:", "",
             "   ✅ عکس پروفایل تأییدشده → همان عکس",
             "   🧍 در غیر این صورت → آدمک ساده", "",
             f"👥 کل کاربران: {_fa(s['total'])}",
             f"📷 عکس تأییدشده: {_fa(s['real'])}",
             f"🧍 آدمک می‌گیرند: {_fa(s['fallback'])}", ""]
    btns = []
    for key, icon, name, kind, dflt, hint in cp.PHOTO_SETTINGS:
        v = get_setting(key, dflt)
        if kind == "bool":
            on = str(v) == "1"
            lines.append(f"{'🟢' if on else '⚪'} {icon} {name}")
            btns.append([{"text": f"{'✅' if on else '❌'} {icon} {name}"[:34],
                          "callback_data": f"ccpb_{key}"}])
        else:
            lines.append(f"▫️ {icon} {name}: {v}")
            btns.append([{"text": f"{icon} {name}: {v}"[:34],
                          "callback_data": f"ccpe_{key}"}])
    btns.append([{"text": "👁️ دیدن آدمک", "callback_data": "cc_silh"}])
    btns.append([{"text": "🔙 مرکز صدور", "callback_data": "cc_home"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def toggle_photo_setting(cid, uid, key):
    if not _guard(cid, uid):
        return
    import certphoto as cp
    row = next((r for r in cp.PHOTO_SETTINGS if r[0] == key), None)
    if not row or row[3] != "bool":
        return
    cur = get_setting(key, row[4]) == "1"
    set_setting(key, "0" if cur else "1", row[2], "certificate", uid)
    show_photo_panel(cid, uid)


def start_photo_setting(cid, uid, key):
    from bale_api import send, kb_cancel
    from auth import set_state
    if not _guard(cid, uid):
        return
    import certphoto as cp
    row = next((r for r in cp.PHOTO_SETTINGS if r[0] == key), None)
    if not row:
        return
    set_state(uid, "cc_photov", {"key": key}, merge=False)
    send(cid, (
        f"{row[1]} {row[2]}\n"
        "━━━━━━━━━━━━━━\n\n"
        f"💡 {row[5]}\n\n"
        f"📄 فعلی: {get_setting(key, row[4])}\n\n"
        "مقدار تازه را بنویسید:"
    ), kb_cancel())


def show_silhouette(cid, uid):
    from bale_api import send, send_photo
    if not _guard(cid, uid):
        return
    import certphoto as cp
    p = cp.make_silhouette(force=True)
    if p and Path(p).exists():
        send_photo(cid, p, "🧍 آدمک پیش‌فرض — برای کسانی که\n"
                           "عکس تأییدشده ندارند")
    else:
        send(cid, "❌ ساخت آدمک ناموفق بود")
    show_photo_panel(cid, uid)


def show_stats(cid, uid):
    """📊 آمار کلی مرکز"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    n_iss = db_scalar("SELECT COUNT(*) FROM cert_issues") or 0
    n_pub = db_scalar("SELECT COUNT(*) FROM cert_issues "
                      "WHERE status='published'") or 0
    n_sh = db_scalar("SELECT COUNT(*) FROM cert_shares") or 0
    n_b = db_scalar("SELECT COUNT(*) FROM cert_shares "
                    "WHERE state='built'") or 0
    n_f = db_scalar("SELECT COUNT(*) FROM cert_shares "
                    "WHERE state='failed'") or 0
    n_all = db_scalar("SELECT COUNT(*) FROM certificates") or 0
    n_ctr = db_scalar("SELECT COUNT(*) FROM certificates "
                      "WHERE source='center'") or 0
    pct = int(n_b * 100 / max(1, n_sh))
    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)

    lines = ["📊 آمار مرکز صدور", "━━━━━━━━━━━━━━", "",
             f"🗂️ طرح‌ها: {_fa(n_iss)}  (📢 {_fa(n_pub)} منتشرشده)",
             f"👥 گیرندگان: {_fa(n_sh)}",
             "",
             f"{bar}  {_fa(pct)}٪ دریافت‌شده",
             "",
             f"✅ ساخته‌شده: {_fa(n_b)}",
             f"⏳ در انتظار: {_fa(max(0, n_sh - n_b - n_f))}"]
    if n_f:
        lines.append(f"❌ ناموفق: {_fa(n_f)}")
    lines += ["", "━━━━━━━━━━━━━━",
              f"🎓 کل گواهینامه‌های ربات: {_fa(n_all)}",
              f"🏛️ از مرکز صدور: {_fa(n_ctr)}"]

    top = db_execute(
        "SELECT title, total, built FROM cert_issues "
        "WHERE status='published' ORDER BY built DESC LIMIT 5",
        fetch="all") or []
    if top:
        lines += ["", "🏆 پرمخاطب‌ترین طرح‌ها:", ""]
        for i, t in enumerate(top, 1):
            lines.append(f"{_fa(i)}. {_short(t['title'], 24)} — "
                         f"{_fa(t.get('built') or 0)}/{_fa(t.get('total') or 0)}")

    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 مرکز صدور", "callback_data": "cc_home"}]]})


def from_event(cid, uid, eid):
    """
    🎉 میان‌بر: از پنل رویداد → طرح تازه با گیرندگان همان رویداد

    🎯 «صدور گواهی که تو رویداد هست هم کامل بروز بشه با این
        تغییرات»

    یک طرح می‌سازد، قالب پیش‌فرض را می‌گذارد، شرکت‌کنندگان را
    پر می‌کند و شمارهٔ نامهٔ رویداد را برمی‌دارد — بعد ادمین
    فقط پارامترها را پر می‌کند و منتشر می‌کند.
    """
    from bale_api import send
    if not _guard(cid, uid):
        return
    init_tables()

    from events import get_event
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد یافت نشد")

    # 🔁 اگر قبلاً برای این رویداد طرحی ساخته‌ایم، همان را باز کن
    old = db_execute(
        "SELECT * FROM cert_issues WHERE audience='event' "
        "AND audience_ref=? ORDER BY id DESC LIMIT 1",
        (str(eid),), fetch="one")
    if old:
        return show_issue(cid, uid, old["id"],
                          "🔁 طرح موجود این رویداد باز شد")

    tpl = db_execute("SELECT id FROM cert_templates WHERE is_active=1 "
                     "ORDER BY is_default DESC, id DESC LIMIT 1",
                     fetch="one")
    if not tpl:
        return send(cid, (
            "⚠️ هنوز قالبی ندارید\n"
            "━━━━━━━━━━━━━━\n\n"
            "اول یک فایل ورد به‌عنوان قالب اضافه کنید."
        ), {"inline_keyboard": [
            [{"text": "📄 قالب‌ها", "callback_data": "ct_panel"}],
            [{"text": "🔙 بازگشت", "callback_data": f"ev_view_{eid}"}]]})

    iid = create_issue(uid, f"گواهینامهٔ {ev.get('title') or 'رویداد'}",
                       tpl["id"])
    if not iid:
        return send(cid, "❌ ساخت طرح ناموفق بود")

    scan_template(tpl["id"])
    n = fill_from_event(iid, eid)

    # 🔖 شمارهٔ نامه و اعتبار را از خود رویداد بردار
    upd, args = [], []
    if ev.get("cert_doc_no"):
        upd.append("doc_no=?")
        args.append(ev["cert_doc_no"])
    if ev.get("cert_valid_months") not in (None, ""):
        upd.append("valid_months=?")
        args.append(int(ev["cert_valid_months"]))
    if upd:
        args.append(int(iid))
        db_execute(f"UPDATE cert_issues SET {', '.join(upd)} WHERE id=?",
                   tuple(args))

    # 🎉 عنوان رویداد را در پارامتر {رویداد} بگذار
    if ev.get("title"):
        set_value(iid, "event", ev["title"])
    if ev.get("start_date"):
        set_value(iid, "date", ev["start_date"])

    show_issue(cid, uid, iid,
               f"🎉 طرح از رویداد ساخته شد — {_fa(n)} شرکت‌کننده")


# ══════════════════════════════════════════════════════════
# ⚡ فاز ۳۹ — پر کردن پشت‌سرهم پارامترها
#
# 🎯 «تو میگی برای پارامترهای ثابت مثل تاریخ برگزاری، تاریخ
#     صدور و شماره نامه و اسم کارگاه و هر پارامتری که تو
#     گواهینامه هست، تو میگی من دیتا بدم»
#
# به‌جای اینکه ادمین یکی‌یکی روی دکمه‌ها بزند، ربات پشت سر هم
# می‌پرسد و او فقط جواب می‌دهد.
# ══════════════════════════════════════════════════════════
def wizard_start(cid, uid, iid):
    """⚡ شروع پرسش پشت‌سرهم"""
    from bale_api import send
    from auth import set_state
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return show_home(cid, uid, "❌ طرح یافت نشد")
    tid = iss.get("template_id")
    if not tid:
        return show_issue(cid, uid, iid, "⚠️ اول قالب را انتخاب کنید")

    ask, _, _ = template_fields(tid)
    fixed = [k for k in ask if field_kind(k) == "fixed"]
    if not fixed:
        return show_params(cid, uid, iid)

    set_state(uid, "cc_wiz", {"iid": int(iid), "keys": fixed, "i": 0},
              merge=False)
    _wizard_ask(cid, uid)


def _wizard_ask(cid, uid):
    """❓ پرسش گام جاری"""
    from bale_api import send, kb_cancel
    from auth import get_state_data, clear_state
    import certgen as cg

    # ℹ️ فقط دادهٔ state لازم است — نامش را

    #    فراخوانندهٔ بالادست بررسی کرده.

    data = get_state_data(uid)
    keys = data.get("keys") or []
    i = int(data.get("i") or 0)
    iid = data.get("iid")

    if i >= len(keys):
        clear_state(uid)
        return show_params(cid, uid, iid)

    iss = get_issue(iid)
    vals = issue_values(iss)
    k = keys[i]
    cur = str(vals.get(k) or "").strip()

    lines = [f"⚡ گام {_fa(i + 1)} از {_fa(len(keys))}",
             "━━━━━━━━━━━━━━", "",
             f"{cg.ph_icon(k)} {cg.ph_label(k)}"]
    hint = cg.ph_desc(k)
    if hint:
        lines.append(f"💡 {hint}")
    lines.append("")
    if cur:
        lines += [f"📄 مقدار فعلی: {cur}", ""]
    lines += ["مقدار را بنویسید:", "",
              "⏭️ «رد» = این یکی را خالی بگذار",
              "🏁 «پایان» = بقیه را بعداً پر می‌کنم"]
    send(cid, "\n".join(lines), kb_cancel())


def wizard_input(cid, uid, txt):
    """📝 پاسخ یک گام"""
    from bale_api import send, kb_remove
    from auth import get_state_data, set_state, clear_state

    # ℹ️ فقط دادهٔ state لازم است — نامش را

    #    فراخوانندهٔ بالادست بررسی کرده.

    data = get_state_data(uid)
    keys = data.get("keys") or []
    i = int(data.get("i") or 0)
    iid = data.get("iid")

    if txt in ("پایان", "🏁 پایان", "تمام"):
        clear_state(uid)
        send(cid, "✅ ثبت شد", kb_remove())
        return show_params(cid, uid, iid)

    if i < len(keys):
        k = keys[i]
        if txt not in ("رد", "⏭️ رد", "skip", "-"):
            set_value(iid, k, txt[:300])

    set_state(uid, "cc_wiz",
              {"iid": iid, "keys": keys, "i": i + 1}, merge=False)
    _wizard_ask(cid, uid)


# ══════════════════════════════════════════════════════════
# 👥 فاز ۳۹ — راه‌های تازهٔ انتخاب گیرنده
#
# 🎯 «من بتونم هم دستی اسم بدم · هم از کاربران جستجو کنم ·
#     هم از اکسل بزارم · هم از دسته‌ای خاص یا برنامه‌ای خاص»
# ══════════════════════════════════════════════════════════
def ask_manual(cid, uid, iid):
    """✍️ افزودن دستی — چند نفر با هم"""
    from bale_api import send, kb_cancel
    from auth import set_state
    if not _guard(cid, uid):
        return
    set_state(uid, "cc_manual", {"iid": int(iid)}, merge=False)
    send(cid, (
        "✍️ افزودن دستی\n"
        "━━━━━━━━━━━━━━\n\n"
        "نام‌ها را بنویسید — هر نفر در یک خط:\n\n"
        "```\n"
        "علی محمدی\n"
        "زهرا کریمی\n"
        "```\n\n"
        "💡 اگر کد ملی هم دارید، با ویرگول:\n"
        "   علی محمدی، ۰۰۱۲۳۴۵۶۷۸\n\n"
        "🔗 اگر کد ملی با حساب کاربری بخواند،\n"
        "   گواهینامه خودکار به پروفایلش می‌رود."
    ), kb_cancel())


def manual_input(cid, uid, txt):
    """📝 پردازش فهرست دستی"""
    from bale_api import send, kb_remove
    from auth import get_state_data, clear_state, normalize_digits

    # ℹ️ فقط دادهٔ state لازم است — نامش را

    #    فراخوانندهٔ بالادست بررسی کرده.

    data = get_state_data(uid)
    iid = data.get("iid")
    rows, bad = [], 0
    for ln in (txt or "").split("\n"):
        ln = ln.strip(" -•\t")
        if not ln:
            continue
        parts = [p.strip() for p in ln.replace("،", ",").split(",")]
        nm = parts[0]
        nid = ""
        mob = ""
        for extra in parts[1:]:
            d = "".join(c for c in normalize_digits(extra)
                        if c.isdigit())
            if len(d) == 10 and d.startswith("0") is False:
                nid = d
            elif len(d) == 10:
                nid = d
            elif len(d) == 11:
                mob = d
        if len(nm) < 2:
            bad += 1
            continue
        rows.append({"full_name": nm, "national_id": nid,
                     "mobile": mob, "extra": {}})

    if not rows:
        send(cid, "⚠️ هیچ نامی خوانده نشد — دوباره بنویسید")
        return

    clear_state(uid)
    n = fill_from_rows(iid, rows)
    linked = db_scalar("SELECT COUNT(*) FROM cert_shares WHERE "
                       "issue_id=? AND bale_user_id IS NOT NULL",
                       (int(iid),)) or 0
    msg = [f"✅ {_fa(n)} نفر اضافه شدند",
           f"🔗 {_fa(linked)} نفر به حساب ربات وصل شدند"]
    if bad:
        msg.append(f"⚠️ {_fa(bad)} خط نامفهوم رد شد")
    send(cid, "\n".join(msg), kb_remove())
    show_issue(cid, uid, iid)


def ask_search(cid, uid, iid):
    """🔍 جستجو در کاربران"""
    from bale_api import send, kb_cancel
    from auth import set_state
    if not _guard(cid, uid):
        return
    set_state(uid, "cc_search", {"iid": int(iid)}, merge=False)
    send(cid, (
        "🔍 جستجوی کاربران\n"
        "━━━━━━━━━━━━━━\n\n"
        "نام، کد ملی یا موبایل را بنویسید:\n\n"
        "مثال: محمدی\n"
        "مثال: ۰۰۱۲۳۴۵۶۷۸\n\n"
        "💡 می‌توانید بخشی از نام را بنویسید."
    ), kb_cancel())


def search_input(cid, uid, txt):
    """🔎 نتیجهٔ جستجو"""
    from bale_api import send, send_or_edit
    from auth import get_state_data, clear_state, normalize_digits

    # ℹ️ فقط دادهٔ state لازم است — نامش را

    #    فراخوانندهٔ بالادست بررسی کرده.

    data = get_state_data(uid)
    iid = data.get("iid")
    q = (txt or "").strip()
    if len(q) < 2:
        send(cid, "⚠️ دست‌کم ۲ حرف بنویسید")
        return

    qd = normalize_digits(q)
    like = f"%{q}%"
    rows = db_execute(
        "SELECT * FROM users WHERE is_blocked=0 AND ("
        "  (first_name || ' ' || COALESCE(last_name,'')) LIKE ?"
        "  OR national_id LIKE ? OR mobile LIKE ?) "
        "ORDER BY id DESC LIMIT 20",
        (like, f"%{qd}%", f"%{qd}%"), fetch="all") or []

    clear_state(uid)
    if not rows:
        return send_or_edit(cid, (
            f"🔍 «{q}»\n━━━━━━━━━━━━━━\n\n"
            "📭 کسی پیدا نشد.\n\n"
            "💡 شاید هنوز در ربات ثبت‌نام نکرده — می‌توانید\n"
            "   دستی اضافه‌اش کنید."
        ), {"inline_keyboard": [
            [{"text": "🔍 جستجوی دوباره",
              "callback_data": f"cc_asr_{iid}"}],
            [{"text": "✍️ افزودن دستی",
              "callback_data": f"cc_amn_{iid}"}],
            [{"text": "🔙 بازگشت", "callback_data": f"cc_aud_{iid}"}]]})

    have = {s.get("bale_user_id") for s in shares(iid)}
    lines = [f"🔍 «{q}» — {_fa(len(rows))} نفر",
             "━━━━━━━━━━━━━━", ""]
    btns = []
    for u in rows:
        nm = _name_of(u)
        added = u.get("bale_user_id") in have
        lines.append(f"{'✅' if added else '▫️'} {nm}"
                     f"{'  ' + (u.get('national_id') or '')}")
        btns.append([{"text": f"{'✅' if added else '➕'} {nm}"[:34],
                      "callback_data":
                          f"cc_addu_{iid}_{u['bale_user_id']}"}])
    lines += ["", "💡 روی هرکس بزنید تا اضافه شود."]
    btns.append([{"text": "🔍 جستجوی دوباره",
                  "callback_data": f"cc_asr_{iid}"}])
    btns.append([{"text": "🔙 گیرندگان",
                  "callback_data": f"cc_aud_{iid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def add_one_user(cid, uid, iid, target):
    """➕ افزودن یک کاربر از نتیجهٔ جستجو"""
    from bale_api import send
    if not _guard(cid, uid):
        return
    u = db_execute("SELECT * FROM users WHERE bale_user_id=?",
                   (int(target),), fetch="one")
    if not u:
        return send(cid, "❌ کاربر یافت نشد")
    r = add_share(iid, u.get("bale_user_id"), _name_of(u),
                  u.get("national_id") or "", u.get("mobile") or "")
    _sync_total(iid, "manual", "")
    send(cid, f"{'✅ افزوده شد' if r else 'ℹ️ از قبل بود'}: "
              f"{_name_of(u)}")
    show_audience(cid, uid, iid)


def send_sample_excel(cid, uid, iid):
    """
    📥 فایل اکسل نمونه — با ستون‌های همین قالب

    🎯 «هم از اکسل بزارم که آماده کنی»

    ستون‌ها بر اساس پارامترهای واقعی قالب ساخته می‌شوند، پس
    ادمین دقیقاً می‌داند چه چیزی لازم است.
    """
    from bale_api import send, send_document
    import certgen as cg
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return send(cid, "❌ طرح یافت نشد")
    try:
        import openpyxl
    except ImportError:
        return send(cid, "⚠️ openpyxl نصب نیست")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "گیرندگان"

    head = ["نام و نام خانوادگی", "کد ملی", "موبایل"]
    tid = iss.get("template_id")
    if tid:
        _a, auto, _i = template_fields(tid)
        for k in auto:
            if k in ("name", "first_name", "last_name",
                     "national_id", "mobile", "photo"):
                continue
            head.append(cg.ph_label(k))
    ws.append(head)
    ws.append(["علی محمدی", "0012345679", "09121112233"]
              + [""] * (len(head) - 3))
    ws.append(["زهرا کریمی", "0023456787", "09354445566"]
              + [""] * (len(head) - 3))

    try:
        from openpyxl.styles import Font
        for c in ws[1]:
            c.font = Font(bold=True)
        for i, _h in enumerate(head, 1):
            ws.column_dimensions[
                openpyxl.utils.get_column_letter(i)].width = 22
    except Exception:
        pass

    from config import FILES_DIR
    d = Path(FILES_DIR) / "cert_center"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"sample_{iid}.xlsx"
    wb.save(str(p))
    send_document(cid, str(p), (
        "📥 نمونهٔ اکسل\n\n"
        "ستون‌ها را نگه دارید و ردیف‌ها را با اسامی\n"
        "خودتان پر کنید.\n\n"
        "💡 ستون «نام و نام خانوادگی» الزامی است."))
    return show_audience(cid, uid, iid)


# ══════════════════════════════════════════════════════════
# 📤 فاز ۳۹ — روش‌های انتشار
#
# 🎯 «روش انتشار که من بتونم از کلش خروجی پی‌دی‌اف بگیرم · یا
#     بفرستم بره رو پروفایلشون · یا لینکش کنم هرکسی اومد بات
#     رو استارت زد بگیره»
# ══════════════════════════════════════════════════════════
PUBLISH_WAYS = {
    "notify": ("📬", "اعلان به پروفایل",
               "همه خبردار می‌شوند و از پروفایلشان می‌گیرند"),
    "link":   ("🔗", "فقط با لینک",
               "بی‌صدا — هرکس لینک را باز کند می‌گیرد"),
    "pdf":    ("📄", "خروجی یکجا برای خودم",
               "همه را می‌سازد و یک فایل به شما می‌دهد"),
    "silent": ("🤫", "بدون اعلان",
               "آماده می‌ماند، بعداً خبر می‌دهید"),
}


def show_publish(cid, uid, iid):
    """📤 انتخاب روش انتشار"""
    from bale_api import send_or_edit
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return show_home(cid, uid, "❌ طرح یافت نشد")
    ok, todo = issue_ready(iss)
    if not ok:
        return show_issue(cid, uid, iid, "⚠️ " + "؛ ".join(todo))

    n = db_scalar("SELECT COUNT(*) FROM cert_shares WHERE issue_id=?",
                  (iss["id"],)) or 0
    n_bot = db_scalar("SELECT COUNT(*) FROM cert_shares WHERE "
                      "issue_id=? AND bale_user_id IS NOT NULL",
                      (iss["id"],)) or 0

    lines = ["📤 روش انتشار", "━━━━━━━━━━━━━━", "",
             f"🗂️ {iss.get('title')}",
             f"👥 {_fa(n)} گیرنده  ·  🔗 {_fa(n_bot)} با حساب ربات", ""]
    if n - n_bot:
        lines += [f"⚠️ {_fa(n - n_bot)} نفر حساب ربات ندارند —",
                  "   با لینک می‌توانند بگیرند.", ""]
    lines += ["چطور منتشر شود؟", ""]
    btns = []
    for k, (ic, nm, desc) in PUBLISH_WAYS.items():
        lines += [f"{ic} {nm}", f"   {desc}", ""]
        btns.append([{"text": f"{ic} {nm}",
                      "callback_data": f"cc_pw_{iid}_{k}"}])
    lines += ["━━━━━━━━━━━━━━",
              "💡 گواهینامه‌ها هنگام انتشار ساخته نمی‌شوند —",
              "   هر کاربر که اقدام کند همان لحظه ساخته می‌شود.",
              "   (جز «خروجی یکجا» که همه را می‌سازد)"]
    btns.append([{"text": "🔙 بازگشت", "callback_data": f"cc_v_{iid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def publish_way(cid, uid, iid, way):
    """📤 اجرای روش انتخاب‌شده"""
    from bale_api import send
    if not _guard(cid, uid):
        return
    if way not in PUBLISH_WAYS:
        return send(cid, "❌ روش نامعتبر")

    if way == "pdf":
        return export_all(cid, uid, iid)

    if way == "link":
        db_execute("UPDATE cert_issues SET link_on=1 WHERE id=?",
                   (int(iid),))
        n, err = publish(iid, notify=False)
        if err:
            return show_issue(cid, uid, iid, f"❌ {err}")
        return show_link(cid, uid, iid)

    if way == "silent":
        n, err = publish(iid, notify=False)
        if err:
            return show_issue(cid, uid, iid, f"❌ {err}")
        return show_issue(cid, uid, iid,
                          "🤫 منتشر شد — بدون اعلان")

    # 📬 notify
    send(cid, "⏳ در حال ارسال اعلان‌ها…")
    n, err = publish(iid, notify=True)
    if err:
        return show_issue(cid, uid, iid, f"❌ {err}")
    return show_issue(cid, uid, iid,
                      f"🎉 منتشر شد — {_fa(n)} اعلان فرستاده شد")


def export_all(cid, uid, iid):
    """
    📄 ساخت همهٔ گواهینامه‌ها و تحویل یکجا به ادمین

    🎯 «من بتونم از کلش خروجی پی‌دی‌اف بگیرم»

    ⚠️ این تنها روشی است که همه را همین حالا می‌سازد. برای
       فهرست‌های بزرگ زمان می‌برد، پس سقف دارد.
    """
    from bale_api import send, send_document
    if not _guard(cid, uid):
        return
    iss = get_issue(iid)
    if not iss:
        return send(cid, "❌ طرح یافت نشد")

    rows = shares(iid)
    if not rows:
        return send(cid, "📭 گیرنده‌ای نیست")

    try:
        cap = int(get_setting("cc_export_max", "200") or 200)
    except (TypeError, ValueError):
        cap = 200
    if len(rows) > cap:
        return send(cid, (
            f"⚠️ {_fa(len(rows))} نفر زیاد است\n"
            "━━━━━━━━━━━━━━\n\n"
            f"سقف خروجی یکجا: {_fa(cap)} نفر\n\n"
            "💡 از تنظیمات مرکز سقف را بالا ببرید، یا\n"
            "   روش «📬 اعلان به پروفایل» را انتخاب کنید."))

    # 📢 اول منتشر کن تا رکوردها معتبر شوند
    if iss.get("status") != "published":
        _n, err = publish(iid, notify=False)
        if err:
            return send(cid, f"❌ {err}")

    send(cid, f"⏳ ساخت {_fa(len(rows))} گواهینامه…\n"
              "این کار ممکن است چند دقیقه طول بکشد.")

    made, failed = [], 0
    for sh in rows:
        cert, err = build_one(iid, sh["id"], notify=False)
        if cert:
            p = cert.get("pdf_path") or cert.get("png_path") \
                or cert.get("docx_path")
            if p and Path(p).exists():
                made.append(p)
                continue
        failed += 1

    if not made:
        return send(cid, "❌ هیچ فایلی ساخته نشد")

    # 📦 همه را در یک زیپ بگذار
    import zipfile
    from config import FILES_DIR
    d = Path(FILES_DIR) / "cert_center"
    d.mkdir(parents=True, exist_ok=True)
    zp = d / f"issue_{iid}_{secrets.token_hex(3)}.zip"
    try:
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for i, p in enumerate(made, 1):
                z.write(p, f"{i:04d}_{Path(p).name}")
    except Exception as e:
        log(f"⚠️ ساخت زیپ: {e}")
        return send(cid, f"❌ بسته‌بندی ناموفق: {user_error_message(e)}")

    cap_txt = [f"📦 {_fa(len(made))} گواهینامه", ""]
    if failed:
        cap_txt.append(f"⚠️ {_fa(failed)} مورد ناموفق")
    cap_txt.append(f"🗂️ {iss.get('title')}")
    send_document(cid, str(zp), "\n".join(cap_txt))
    return show_issue(cid, uid, iid,
                      f"📄 خروجی آماده شد — {_fa(len(made))} فایل")
