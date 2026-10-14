"""
🔍 استعلام گواهینامه — شناسهٔ دولایه و اعتبار زمانی — فاز ۳۴

درخواست کاربر (عیناً):
  «مبنای استعلام چیه؟ هر رویداد یدونه شماره ثبت برای کل
   گواهینامه ها داره چطوری شخصی که استعلام میزنه اطلاعات و
   مشخصات گواهی براش میاد بالا؟ کد ثبت که ثابته پس چیزی که به
   ربات لینک میشه حتما ترکیب کدملی با شماره نامه یا هر پارامتر
   دیگست»

  «اعتبار گواهینامه ها پیش فرض ۲۴ ماه یا دوساله باشه و این مورد
   تو تنظیمات مربوطه قابل تنظیم باشه»

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 تشخیص کاملاً درست شما

  یک رویداد → یک «شمارهٔ نامه» (مثلاً ۱۴۲۱/۵۴۷۲/۵۰۰۰/د)
  ولی ۵۰ نفر گواهینامه می‌گیرند.

  اگر کیوآر فقط شمارهٔ نامه را داشته باشد، معلوم نیست
  گواهینامهٔ **کدام نفر** است.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔑 راه‌حل — شناسهٔ دولایه

  لایهٔ ۱: شمارهٔ نامه   ← مشترک بین همهٔ گواهینامه‌های رویداد
  لایهٔ ۲: کد فردی      ← یکتا برای هر نفر

  شناسهٔ کامل =  <شمارهٔ نامه>-<کد فردی>
  نمونه       =  1421/5472/5000/د-A7K2M9

  کیوآر → شناسهٔ کامل → دقیقاً همان یک گواهینامه

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔐 سه راه استعلام

  ۱) اسکن کیوآر            فوری، بدون تایپ
  ۲) شمارهٔ نامه + کد ملی   وقتی کیوآر خراب شده
  ۳) کد فردی تنها          کوتاه و قابل تایپ
"""
import re
import secrets
from datetime import datetime, timedelta

from database import db_execute, db_scalar, get_setting, log
from bale_api import send, send_or_edit, kb_cancel, kb_remove

# 🔤 الفبای کد فردی — بدون حروف گیج‌کننده (O/0، I/1)
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

# 📅 واحدهای اعتبار
VALIDITY = {
    "0":   "♾️ بدون انقضا",
    "6":   "۶ ماه",
    "12":  "۱ سال",
    "24":  "۲ سال (پیش‌فرض)",
    "36":  "۳ سال",
    "60":  "۵ سال",
}


def init_tables():
    """🗄️ ستون‌های استعلام و اعتبار"""
    from database import ensure_table
    # 📋 ستون‌های شناسه در CERTS_SCHEMA (attendance.py) تعریف شده‌اند
    #    و ensure_table خودش اضافه‌شان می‌کند. اینجا فقط مطمئن
    #    می‌شویم آن تابع صدا زده شده باشد.
    try:
        import attendance as _att
        ensure_table("certificates", _att.CERTS_SCHEMA)
    except Exception:
        pass

    # 📜 گزارش استعلام‌ها — برای آمار و کشف سوءاستفاده
    ensure_table("cert_verifies", {
        "cert_id": "INTEGER",
        "full_code": "TEXT",
        "by_user": "INTEGER",
        "method": "TEXT",          # qr | code | doc_nid
        "result": "TEXT",          # valid | expired | revoked | notfound
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    })
    for q in [
        "CREATE INDEX IF NOT EXISTS idx_cert_full "
        "ON certificates(full_code)",
        "CREATE INDEX IF NOT EXISTS idx_cert_person "
        "ON certificates(person_code)",
        "CREATE INDEX IF NOT EXISTS idx_cert_doc "
        "ON certificates(doc_no)",
        "CREATE INDEX IF NOT EXISTS idx_cv_code "
        "ON cert_verifies(full_code)",
    ]:
        try:
            db_execute(q)
        except Exception:
            pass
    log("✅ جدول استعلام گواهینامه آماده شد")


# ══════════════════════════════════════════════════════════
# 🔑 ساخت شناسه
# ══════════════════════════════════════════════════════════
def new_person_code(n=None):
    """
    🔑 کد یکتای یک نفر — کوتاه و قابل تایپ.

    از الفبای بدون حروف گیج‌کننده استفاده می‌کند تا کسی که
    از روی کاغذ تایپ می‌کند اشتباه نکند.
    """
    try:
        n = int(n or get_setting("cert_code_len", "6") or 6)
    except (TypeError, ValueError):
        n = 6
    n = max(4, min(12, n))
    for _ in range(30):
        c = "".join(secrets.choice(ALPHABET) for _ in range(n))
        if not db_scalar("SELECT COUNT(*) FROM certificates "
                         "WHERE person_code=?", (c,)):
            return c
    return secrets.token_hex(4).upper()


def build_full_code(doc_no, person_code):
    """
    🔗 ترکیب شمارهٔ نامه و کد فردی.

    اگر شمارهٔ نامه نباشد، فقط کد فردی — باز هم یکتاست.
    """
    d = (doc_no or "").strip()
    p = (person_code or "").strip()
    if not p:
        return d
    return f"{d}-{p}" if d else p


def normalize_code(txt):
    """
    🧹 پاکسازی ورودی کاربر.

    مردم کد را با فاصله، خط تیرهٔ اضافه، حروف کوچک یا ارقام
    فارسی می‌نویسند — همه را یکدست می‌کنیم.
    """
    t = str(txt or "").strip()
    t = t.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
                                  "01234567890123456789"))
    t = t.replace("ي", "ی").replace("ك", "ک")
    t = re.sub(r"[\s_\u200c]+", "", t)
    return t.upper()


def event_doc_no(eid):
    """
    📄 شمارهٔ نامهٔ یک رویداد.

    اول از خود رویداد، بعد از الگوی پیش‌فرض پنل.
    """
    if not eid:
        return (get_setting("cert_doc_no", "") or "").strip()
    r = db_execute("SELECT cert_doc_no FROM events WHERE id=?",
                   (int(eid),), fetch="one") or {}
    v = (r.get("cert_doc_no") or "").strip()
    if v:
        return v
    return (get_setting("cert_doc_no", "") or "").strip()


# ══════════════════════════════════════════════════════════
# 📅 اعتبار زمانی
# ══════════════════════════════════════════════════════════
def default_months(eid=None):
    """
    📅 اعتبار پیش‌فرض بر حسب ماه.

    🎯 «اعتبار گواهینامه‌ها پیش‌فرض ۲۴ ماه یا دوساله باشه و
        این مورد تو تنظیمات قابل تنظیم باشه»

    اولویت: تنظیم رویداد ← تنظیم پنل ← ۲۴ ماه
    """
    if eid:
        r = db_execute("SELECT cert_valid_months FROM events WHERE id=?",
                       (int(eid),), fetch="one") or {}
        v = r.get("cert_valid_months")
        if v is not None and str(v).strip() != "":
            try:
                return max(0, int(v))
            except (TypeError, ValueError):
                pass
    try:
        return max(0, int(get_setting("cert_valid_months", "24") or 24))
    except (TypeError, ValueError):
        return 24


def _en(t):
    return str(t or "").translate(str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def add_months(date_str, months):
    """
    📅 افزودن ماه به تاریخ شمسی «۱۴۰۴/۰۷/۲۹».

    اگر روز در ماه مقصد وجود نداشته باشد (۳۱ اسفند)، به
    آخرین روز آن ماه می‌رود.
    """
    if not date_str or not months:
        return ""
    try:
        p = re.split(r"[/\-.]", _en(date_str).strip())
        y, m, d = int(p[0]), int(p[1]), int(p[2])
    except Exception:
        return ""
    total = (y * 12 + (m - 1)) + int(months)
    ny, nm = total // 12, total % 12 + 1
    nd = min(d, _jm_days(ny, nm))
    return f"{ny:04d}/{nm:02d}/{nd:02d}"


def _jm_days(y, m):
    """تعداد روزهای یک ماه شمسی"""
    if m <= 6:
        return 31
    if m <= 11:
        return 30
    return 30 if ((y + 12) % 33) % 4 == 1 else 29


def today_jalali():
    """📅 تاریخ امروز شمسی"""
    try:
        import jdatetime
        j = jdatetime.date.today()
        return f"{j.year:04d}/{j.month:02d}/{j.day:02d}"
    except Exception:
        pass
    try:
        from forms import jnow
        return str(jnow())[:10]
    except Exception:
        return ""


def _key(date_str):
    """🔢 تاریخ شمسی → عدد قابل مقایسه"""
    try:
        p = re.split(r"[/\-.]", _en(date_str).strip())
        return int(p[0]) * 10000 + int(p[1]) * 100 + int(p[2])
    except Exception:
        return 0


def is_expired(row):
    """⏰ آیا گواهینامه منقضی شده؟"""
    exp = (row or {}).get("expires_on")
    if not exp:
        return False
    t = today_jalali()
    if not t:
        return False
    return _key(t) > _key(exp)


def days_left(row):
    """📅 چند روز تا انقضا؟ (منفی = گذشته)"""
    exp = (row or {}).get("expires_on")
    if not exp:
        return None
    try:
        import jdatetime
        p = re.split(r"[/\-.]", _en(exp))
        g1 = jdatetime.date(int(p[0]), int(p[1]),
                            int(p[2])).togregorian()
        return (g1 - jdatetime.date.today().togregorian()).days
    except Exception:
        pass
    # 🩹 بدون jdatetime — تخمین با شمارش روزهای واقعی ماه‌ها
    try:
        p1 = re.split(r"[/\-.]", _en(today_jalali()))
        p2 = re.split(r"[/\-.]", _en(exp))
        y1, m1, d1 = int(p1[0]), int(p1[1]), int(p1[2])
        y2, m2, d2 = int(p2[0]), int(p2[1]), int(p2[2])
    except Exception:
        return None

    def _ord(y, m, d):
        """شمارهٔ روز از ابتدای سال ۱۳۰۰"""
        n = 0
        for yy in range(1300, y):
            n += 366 if ((yy + 12) % 33) % 4 == 1 else 365
        for mm in range(1, m):
            n += _jm_days(y, mm)
        return n + d

    return _ord(y2, m2, d2) - _ord(y1, m1, d1)


# ══════════════════════════════════════════════════════════
# 🏷️ ثبت شناسه روی گواهینامه
# ══════════════════════════════════════════════════════════
def stamp(cert_id, eid=None, months=None):
    """
    🏷️ شناسهٔ دولایه و تاریخ اعتبار را روی گواهینامه می‌نشاند.

    خروجی: dict با کلیدهای doc_no · person_code · full_code ·
            issued_on · expires_on
    """
    row = db_execute("SELECT * FROM certificates WHERE id=?",
                     (int(cert_id),), fetch="one")
    if not row:
        return {}
    eid = eid or row.get("event_id")

    doc = (row.get("doc_no") or "").strip() or event_doc_no(eid)
    pcode = (row.get("person_code") or "").strip() or new_person_code()
    full = build_full_code(doc, pcode)

    issued = (row.get("issued_on") or "").strip() or today_jalali()
    mon = months if months is not None else default_months(eid)
    expires = add_months(issued, mon) if mon else ""

    db_execute(
        "UPDATE certificates SET doc_no=?, person_code=?, full_code=?, "
        "issued_on=?, expires_on=?, valid_months=? WHERE id=?",
        (doc, pcode, full, issued, expires, int(mon or 0),
         int(cert_id)))
    return {"doc_no": doc, "person_code": pcode, "full_code": full,
            "issued_on": issued, "expires_on": expires,
            "valid_months": int(mon or 0)}


def verify_link(full_code):
    """🔗 لینک استعلام — همان که پشت کیوآر می‌نشیند"""
    try:
        from config import deep_link
        u = deep_link(f"cv_{full_code}")
        if u:
            return u
    except Exception:
        pass
    return f"/start cv_{full_code}"


# ══════════════════════════════════════════════════════════
# 🔍 استعلام
# ══════════════════════════════════════════════════════════
def find(code=None, doc_no=None, national_id=None):
    """
    🔍 پیدا کردن گواهینامه — سه راه.

    خروجی: (ردیف یا None، دلیل)
    """
    # راه ۱ — شناسهٔ کامل یا کد فردی
    if code:
        c = normalize_code(code)
        r = db_execute(
            "SELECT * FROM certificates WHERE UPPER(REPLACE("
            "REPLACE(full_code,' ',''),'\u200c',''))=?", (c,),
            fetch="one")
        if r:
            return r, ""
        # شاید فقط کد فردی داده
        r = db_execute("SELECT * FROM certificates WHERE person_code=?",
                       (c,), fetch="one")
        if r:
            return r, ""
        # سازگاری با نسخهٔ قبل — سریال قدیمی
        r = db_execute("SELECT * FROM certificates WHERE UPPER(serial)=?",
                       (c,), fetch="one")
        if r:
            return r, ""
        return None, "این شناسه در سامانه ثبت نشده است"

    # راه ۲ — شمارهٔ نامه + (کد ملی یا کد فردی)
    if doc_no and national_id:
        d = (doc_no or "").strip()
        raw = _en(str(national_id or "")).strip()
        nid = re.sub(r"\D", "", raw)          # فقط رقم → کد ملی
        pc = normalize_code(raw)              # حروف+رقم → کد فردی
        # 🔍 اول با کد فردی (قطعی‌تر است)
        r = db_execute(
            "SELECT * FROM certificates WHERE doc_no=? AND "
            "UPPER(COALESCE(person_code,''))=?", (d, pc), fetch="one")
        if r:
            return r, ""
        # بعد با کد ملی از پروفایل
        if nid:
            r = db_execute(
                "SELECT c.* FROM certificates c "
                "JOIN users u ON u.bale_user_id=c.bale_user_id "
                "WHERE c.doc_no=? AND u.national_id=?",
                (d, nid), fetch="one")
            if r:
                return r, ""
        return None, "با این شمارهٔ نامه و کد ملی چیزی پیدا نشد"

    return None, "اطلاعات کافی نیست"


def status_of(row):
    """
    📊 وضعیت گواهینامه.

    خروجی: (کلید، آیکن، متن)
    """
    if not row:
        return "notfound", "❌", "پیدا نشد"
    if row.get("revoked"):
        return "revoked", "🚫", "باطل شده"
    if is_expired(row):
        return "expired", "⏰", "اعتبارش تمام شده"
    return "valid", "✅", "معتبر"


def log_verify(row, by_user=None, method="qr", result="valid",
               code=""):
    """📜 ثبت استعلام — برای آمار و کشف سوءاستفاده"""
    try:
        db_execute(
            "INSERT INTO cert_verifies (cert_id, full_code, by_user, "
            "method, result) VALUES (?,?,?,?,?)",
            ((row or {}).get("id"),
             (row or {}).get("full_code") or code, by_user,
             method, result))
        if row and row.get("id"):
            db_execute(
                "UPDATE certificates SET verify_count="
                "COALESCE(verify_count,0)+1, "
                "last_verified=datetime('now') WHERE id=?",
                (row["id"],))
    except Exception:
        pass


def report(row):
    """
    📋 متن گزارش استعلام — آنچه استعلام‌کننده می‌بیند.
    """
    key, icon, label = status_of(row)
    if not row:
        return f"{icon} گواهینامه پیدا نشد"

    u = {}
    try:
        from auth import get_user
        u = get_user(row.get("bale_user_id")) or {}
    except Exception:
        pass
    ev = {}
    if row.get("event_id"):
        ev = db_execute("SELECT * FROM events WHERE id=?",
                        (row["event_id"],), fetch="one") or {}

    name = (f"{u.get('first_name') or ''} "
            f"{u.get('last_name') or ''}").strip()
    if not name:
        try:
            from ticket import clean_name
            name = clean_name("")
        except Exception:
            name = "—"

    try:
        from certgen import fa_digits as _fd
    except Exception:
        def _fd(x):
            return str(x)

    lines = [f"{icon} گواهینامه {label}", "━━━━━━━━━━━━━━", ""]

    if key == "valid":
        lines += ["🎓 این گواهینامه معتبر است و در سامانه",
                  "   ثبت شده است.", ""]
    elif key == "expired":
        lines += ["⏰ این گواهینامه صادر شده ولی مدت اعتبارش",
                  "   به پایان رسیده است.", ""]
    elif key == "revoked":
        lines += ["🚫 این گواهینامه توسط صادرکننده باطل شده.", ""]

    lines += [f"👤 دارنده: {name}"]
    nid = (u.get("national_id") or "").strip()
    if nid and get_setting("cert_show_nid", "1") == "1":
        lines.append(f"🆔 کد ملی: {_mask_nid(nid)}")
    if ev.get("title"):
        lines.append(f"🎉 عنوان: {ev['title']}")
    if row.get("doc_no"):
        lines.append(f"📄 شمارهٔ نامه: {row['doc_no']}")
    if row.get("person_code"):
        lines.append(f"🔖 کد فردی: {row['person_code']}")
    if row.get("issued_on"):
        lines.append(f"📅 تاریخ صدور: {_fd(row['issued_on'])}")

    if row.get("expires_on"):
        d = days_left(row)
        if key == "expired":
            lines.append(f"⏰ انقضا: {_fd(row['expires_on'])} (گذشته)")
        elif d is not None and d >= 0:
            lines.append(f"⏳ اعتبار تا: {_fd(row['expires_on'])}"
                         f"  ({_fd(d)} روز مانده)")
        else:
            lines.append(f"⏳ اعتبار تا: {_fd(row['expires_on'])}")
    else:
        lines.append("♾️ بدون تاریخ انقضا")

    n = int(row.get("verify_count") or 0)
    if n > 1:
        lines += ["", f"🔍 این گواهینامه {_fd(n)} بار استعلام شده"]

    org = get_setting("org_name", "") or ""
    if org:
        lines += ["", f"🏛️ صادرکننده: {org}"]
    return "\n".join(lines)


def _mask_nid(nid):
    """🆔 پوشاندن میانهٔ کد ملی — حریم خصوصی"""
    d = re.sub(r"\D", "", str(nid or ""))
    if len(d) < 8:
        return "—"
    try:
        from certgen import fa_digits
        return fa_digits(f"{d[:3]}•••••{d[-2:]}")
    except Exception:
        return f"{d[:3]}•••••{d[-2:]}"


# ══════════════════════════════════════════════════════════
# 👤 استعلام — سمت کاربر
# ══════════════════════════════════════════════════════════
def handle_scan(cid, uid, code):
    """
    📱 کیوآر اسکن شد — ?start=cv_<شناسه>

    هرکسی می‌تواند استعلام کند، حتی بدون ثبت‌نام.
    """
    row, why = find(code=code)
    key, _icon, _lbl = status_of(row)
    log_verify(row, uid, "qr", key, code)
    if not row:
        return send(cid, (
            f"❌ گواهینامه پیدا نشد\n━━━━━━━━━━━━━━\n\n"
            f"🔖 شناسه: {code}\n\n"
            f"{why}\n\n"
            f"💡 اگر از روی کاغذ تایپ کرده‌اید، دوباره بررسی کنید."),
            {"inline_keyboard": [
                [{"text": "🔍 استعلام دستی",
                  "callback_data": "cv_ask"}]]})
    return send(cid, report(row), {"inline_keyboard": [
        [{"text": "🔍 استعلام دیگر", "callback_data": "cv_ask"}]]})


def show_ask(cid, uid):
    """🔍 صفحهٔ استعلام دستی"""
    lines = ["🔍 استعلام گواهینامه", "━━━━━━━━━━━━━━", "",
             "اصالت یک گواهینامه را بررسی کنید.", "",
             "سه راه دارید:", "",
             "   📱 کیوآر روی گواهینامه را اسکن کنید",
             "   🔖 کد فردی را بفرستید",
             "   📄 شمارهٔ نامه + کد ملی", ""]
    return send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔖 با کد فردی", "callback_data": "cv_bycode"}],
        [{"text": "📄 شمارهٔ نامه + کد ملی",
          "callback_data": "cv_bydoc"}],
        [{"text": "🏠 منوی اصلی", "callback_data": "back_main"}]]})


def start_code(cid, uid):
    from auth import set_state
    set_state(uid, "cv_code", {})
    send(cid, ("🔖 کد گواهینامه\n━━━━━━━━━━━━━━\n\n"
               "کد فردی یا شناسهٔ کامل را بفرستید.\n\n"
               "نمونه:\n"
               "   A7K2M9\n"
               "   1421/5472/5000/د-A7K2M9"), kb_cancel())


def start_doc(cid, uid):
    from auth import set_state
    set_state(uid, "cv_doc", {})
    send(cid, ("📄 شمارهٔ نامه\n━━━━━━━━━━━━━━\n\n"
               "شمارهٔ نامهٔ روی گواهینامه را بفرستید.\n\n"
               "نمونه: ۱۴۲۱/۵۴۷۲/۵۰۰۰/د"), kb_cancel())


def handle_text(message):
    """📝 ورودی استعلام"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    txt = (message.get("text") or "").strip()
    from auth import get_state_data, clear_state, set_state
    st, data = get_state_data(uid)
    if not st or not st.startswith("cv_"):
        return False
    if txt in ("انصراف", "❌ انصراف", "/cancel"):
        clear_state(uid)
        send(cid, "✅ لغو شد", kb_remove())
        return True

    if st == "cv_code":
        clear_state(uid)
        row, why = find(code=txt)
        key, _i, _l = status_of(row)
        log_verify(row, uid, "code", key, txt)
        if not row:
            send(cid, f"❌ {why}", kb_remove())
            return True
        send(cid, report(row), kb_remove())
        return True

    if st == "cv_doc":
        set_state(uid, "cv_nid", {"doc": txt})
        send(cid, ("🆔 کد ملی\n━━━━━━━━━━━━━━\n\n"
                   "کد ملی دارندهٔ گواهینامه را بفرستید:"),
             kb_cancel())
        return True

    if st == "cv_nid":
        clear_state(uid)
        row, why = find(doc_no=data.get("doc"), national_id=txt)
        key, _i, _l = status_of(row)
        log_verify(row, uid, "doc_nid", key, data.get("doc") or "")
        if not row:
            send(cid, f"❌ {why}", kb_remove())
            return True
        send(cid, report(row), kb_remove())
        return True
    return False


# ══════════════════════════════════════════════════════════
# 🖥️ پنل ادمین
# ══════════════════════════════════════════════════════════
def _guard(cid, uid):
    """🛡️ بررسی ادمین — منطق مشترک در helpers"""
    from helpers import guard_admin
    return guard_admin(cid, uid)


def _fa(n):
    """🔢 ارقام فارسی — منطق مشترک در helpers"""
    from helpers import fa
    return fa(n)


def show_event_cfg(cid, uid, eid):
    """🔍 تنظیم شمارهٔ نامه و اعتبار یک رویداد"""
    if not _guard(cid, uid):
        return
    from events import get_event
    ev = get_event(eid)
    if not ev:
        return send(cid, "❌ رویداد پیدا نشد")

    doc = (ev.get("cert_doc_no") or "").strip()
    mv = ev.get("cert_valid_months")
    months = default_months(eid)
    n = db_scalar("SELECT COUNT(*) FROM certificates WHERE event_id=?",
                  (int(eid),)) or 0

    lines = ["🔍 استعلام و اعتبار", "━━━━━━━━━━━━━━", "",
             f"🎉 {ev.get('title') or '—'}", "",
             f"📄 شمارهٔ نامه: {doc or '— (پیش‌فرض ربات)'}",
             f"📅 اعتبار: "
             + ("♾️ بدون انقضا" if not months
                else f"{_fa(months)} ماه"
                     + ("" if mv is not None else " (پیش‌فرض)")),
             f"🎓 صادرشده: {_fa(n)}", "",
             "━━━━━━━━━━━━━━", "",
             "💡 شمارهٔ نامه بین همهٔ گواهینامه‌های این رویداد",
             "   مشترک است. برای هر نفر یک کد فردی یکتا هم",
             "   ساخته می‌شود:", "",
             "   شناسهٔ کامل = شمارهٔ نامه + کد فردی", "",
             "   کیوآر همین شناسه را دارد، پس با اسکن دقیقاً",
             "   گواهینامهٔ همان نفر بالا می‌آید."]

    btns = [
        [{"text": "📄 شمارهٔ نامه", "callback_data": f"cve_doc_{eid}"}],
        [{"text": "📅 مدت اعتبار", "callback_data": f"cve_val_{eid}"}],
        [{"text": "📊 آمار استعلام", "callback_data": f"cve_st_{eid}"}],
        [{"text": "🔙 گواهینامه‌ها", "callback_data": f"evc_p_{eid}"}],
    ]
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def show_validity(cid, uid, eid, val=None):
    """📅 انتخاب مدت اعتبار"""
    if not _guard(cid, uid):
        return
    if val is not None:
        # 🔴 باگ رفع‌شده (فاز ۴۰): int(val) بدون محافظ —
        #    callback خراب ValueError می‌داد.
        if val == "def":
            v = None
        else:
            try:
                v = max(0, int(val))
            except (TypeError, ValueError):
                return send(cid, "❌ مقدار نامعتبر")
        try:
            db_execute("UPDATE events SET cert_valid_months=? "
                       "WHERE id=?", (v, int(eid)))
        except (TypeError, ValueError):
            return send(cid, "❌ رویداد نامعتبر")
        return show_event_cfg(cid, uid, eid)

    from events import get_event
    ev = get_event(eid) or {}
    cur = ev.get("cert_valid_months")
    lines = ["📅 مدت اعتبار گواهینامه", "━━━━━━━━━━━━━━", "",
             "گواهینامه‌های این رویداد چند وقت معتبر باشند؟", ""]
    btns = [[{"text": f"{'🔘' if cur is None else '▫️'} "
                      f"پیش‌فرض ربات ({_fa(default_months())} ماه)",
              "callback_data": f"cvv_def_{eid}"}]]
    for k, nm in VALIDITY.items():
        mark = "🔘" if (cur is not None and int(cur) == int(k)) else "▫️"
        lines.append(f"{mark} {nm}")
        btns.append([{"text": f"{mark} {nm}",
                      "callback_data": f"cvv_{k}_{eid}"}])
    lines += ["", "💡 بعد از انقضا، گواهینامه پاک نمی‌شود —",
              "   فقط در استعلام «اعتبارش تمام شده» نشان می‌دهد."]
    btns.append([{"text": "🔙 بازگشت",
                  "callback_data": f"cve_{eid}"}])
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": btns})


def start_doc_edit(cid, uid, eid):
    if not _guard(cid, uid):
        return
    from auth import set_state
    set_state(uid, "cv_edoc", {"eid": int(eid)})
    send(cid, ("📄 شمارهٔ نامهٔ رویداد\n━━━━━━━━━━━━━━\n\n"
               "شمارهٔ نامه‌ای که روی گواهینامه‌های این رویداد\n"
               "چاپ می‌شود را بفرستید.\n\n"
               "نمونه: ۱۴۲۱/۵۴۷۲/۵۰۰۰/د\n\n"
               "💡 خالی بفرستید تا پیش‌فرض ربات استفاده شود."),
         kb_cancel())


def handle_admin_text(message):
    """📝 ورودی ادمین"""
    uid = message["from"]["id"]
    cid = message["chat"]["id"]
    txt = (message.get("text") or "").strip()
    from auth import get_state_data, clear_state
    st, data = get_state_data(uid)
    if st != "cv_edoc":
        return False
    if txt in ("انصراف", "❌ انصراف", "/cancel"):
        clear_state(uid)
        send(cid, "✅ لغو شد", kb_remove())
        return True
    eid = data.get("eid")
    db_execute("UPDATE events SET cert_doc_no=? WHERE id=?",
               (txt[:60], int(eid)))
    clear_state(uid)
    send(cid, "✅ ذخیره شد", kb_remove())
    show_event_cfg(cid, uid, eid)
    return True


def show_stats(cid, uid, eid):
    """📊 آمار استعلام یک رویداد"""
    if not _guard(cid, uid):
        return
    rows = db_execute(
        "SELECT c.*, "
        "(SELECT COUNT(*) FROM cert_verifies v WHERE v.cert_id=c.id) vn "
        "FROM certificates c WHERE c.event_id=? "
        "ORDER BY vn DESC LIMIT 20", (int(eid),), fetch="all") or []
    total = db_scalar(
        "SELECT COUNT(*) FROM cert_verifies v JOIN certificates c "
        "ON c.id=v.cert_id WHERE c.event_id=?", (int(eid),)) or 0
    exp = sum(1 for r in rows if is_expired(r))

    lines = ["📊 آمار استعلام", "━━━━━━━━━━━━━━", "",
             f"🎓 گواهینامه: {_fa(len(rows))}",
             f"🔍 کل استعلام‌ها: {_fa(total)}",
             f"⏰ منقضی‌شده: {_fa(exp)}", ""]
    if rows:
        lines.append("🔝 بیشترین استعلام:")
        for r in rows[:6]:
            if not r.get("vn"):
                continue
            lines.append(f"   {r.get('person_code') or '—'} — "
                         f"{_fa(r['vn'])} بار")
    send_or_edit(cid, "\n".join(lines), {"inline_keyboard": [
        [{"text": "🔙 بازگشت", "callback_data": f"cve_{eid}"}]]})


# ══════════════════════════════════════════════════════════
# ⏰ هشدار انقضا (cron)
# ══════════════════════════════════════════════════════════
def warn_expiring(limit=50):
    """
    ⏰ به دارندگانی که گواهینامه‌شان نزدیک انقضاست خبر بده.

    خروجی: تعداد پیام
    """
    try:
        days = int(get_setting("cert_expiry_warn", "30") or 30)
    except (TypeError, ValueError):
        days = 30
    if days <= 0:
        return 0

    rows = db_execute(
        "SELECT * FROM certificates WHERE revoked=0 AND "
        "expires_on IS NOT NULL AND expires_on<>'' LIMIT ?",
        (int(limit) * 4,), fetch="all") or []
    n = 0
    for r in rows:
        d = days_left(r)
        if d is None or d < 0 or d > days:
            continue
        if r.get("last_verified") == "warned":
            continue
        try:
            send(r["bale_user_id"], (
                f"⏰ یادآوری اعتبار گواهینامه\n"
                f"━━━━━━━━━━━━━━\n\n"
                f"🔖 {r.get('person_code') or r.get('serial') or ''}\n"
                f"📅 تا {_fa(r.get('expires_on'))} معتبر است\n"
                f"   ({_fa(d)} روز مانده)\n\n"
                f"💚 اگر نیاز به تمدید دارید، با ما تماس بگیرید."))
            n += 1
            if n >= limit:
                break
        except Exception:
            pass
    return n
