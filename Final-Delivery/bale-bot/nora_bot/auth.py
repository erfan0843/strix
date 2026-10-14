"""
احراز هویت + مدیریت State + OTP سفیر - نسخه 4.1 (فیکس شده)

🐛 فیکس ریشه‌ای باگ فاز ۴:
   قبلاً set_state(uid, state, data) کل data را جایگزین می‌کرد.
   در ask_step فقط {'step': n} پاس داده می‌شد و همه پاسخ‌های قبلی پاک می‌شد
   -> پیش‌نمایش خالی + ارسال خالی به ادمین.
   حالا:
     - set_state پارامتر merge دارد (پیش‌فرض True) و داده قبلی را حفظ می‌کند
     - update_state_data() برای به‌روزرسانی جزئی اضافه شد
     - get_state_data() همیشه dict برمی‌گرداند (هیچ‌وقت None)
"""
import json
import random
import string
import time
from datetime import datetime, timedelta

import requests

from config import (
    SUPER_ADMIN_ID, SAFIR_API_KEY, SAFIR_BOT_ID, SAFIR_URL, SAFIR_ENABLED,
    SAFIR_SEND_REQUEST_ID,
    OTP_TTL_MINUTES, OTP_MAX_ATTEMPTS, OTP_RESEND_SECONDS,
    STATE_TTL_MINUTES, STRICT_NATIONAL_ID, FORCE_JOIN_FAIL_OPEN,
)
from database import db_execute, log


# ==================== STATE ====================
def set_state(uid, state, data=None, merge=True):
    """
    ذخیره وضعیت کاربر.
    merge=True  -> داده جدید روی داده قبلی merge می‌شود
    merge=False -> داده قبلی کاملاً پاک و جایگزین می‌شود

    ⚠️ اگر state=None باشد و رکورد قبلی وجود داشته باشد،
       نام قبلی حفظ می‌شود (نه NULL) — فیکس باگ «ویزارد می‌میرد»
    """
    payload = {}
    old_row = None
    if merge or state is None:
        old_row = _raw_state(uid)
        if old_row:
            raw = old_row.get("data")
            if raw:
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict) and merge:
                        payload.update(parsed)
                except (json.JSONDecodeError, TypeError):
                    pass

    if isinstance(data, dict):
        payload.update(data)

    # ✅ فیکس بحرانی: هرگز نام state را NULL نکن
    if state is None and old_row:
        state = old_row.get("state")

    dj = json.dumps(payload, ensure_ascii=False) if payload else None
    exp = (datetime.now() + timedelta(minutes=STATE_TTL_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")

    db_execute("""
        INSERT INTO user_states (bale_user_id, state, data, expires_at, updated_at)
        VALUES (?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(bale_user_id) DO UPDATE SET
            state=excluded.state,
            data=excluded.data,
            expires_at=excluded.expires_at,
            updated_at=CURRENT_TIMESTAMP
    """, (uid, state, dj, exp))
    return payload


def _raw_state(uid):
    """خواندن رکورد state بدون فیلتر انقضا (برای بازیابی نام)"""
    return db_execute(
        "SELECT * FROM user_states WHERE bale_user_id=?", (uid,), fetch="one")


def update_state_data(uid, patch):
    """
    فقط داده را آپدیت کن، نام state دست نخورد.

    ⚠️ فیکس: اگر state منقضی شده باشد ولی رکورد باشد، نام از رکورد
    بازیابی می‌شود و انقضا تمدید می‌گردد (کاربر وسط ویزارد گم نمی‌شود).
    """
    if not isinstance(patch, dict):
        return get_state_data(uid)

    cur = get_state(uid)
    if cur:
        name = cur.get("state")
    else:
        # state منقضی شده — نام را از رکورد خام بگیر
        raw = _raw_state(uid)
        name = raw.get("state") if raw else None

    return set_state(uid, name, patch, merge=True)


def get_state(uid):
    """وضعیت کاربر یا None. کلید data همیشه dict است."""
    r = db_execute("""
        SELECT * FROM user_states
        WHERE bale_user_id=?
          AND (expires_at IS NULL OR expires_at > datetime('now'))
    """, (uid,), fetch="one")
    if not r:
        return None
    raw = r.get("data")
    if raw:
        try:
            parsed = json.loads(raw)
            r["data"] = parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            r["data"] = {}
    else:
        r["data"] = {}
    return r


def get_state_name(uid):
    s = get_state(uid)
    return s.get("state") if s else None


def get_state_data(uid):
    """همیشه dict برمی‌گرداند (هیچ‌وقت None) - فیکس مهم"""
    s = get_state(uid)
    return s.get("data", {}) if s else {}


def clear_state(uid):
    db_execute("DELETE FROM user_states WHERE bale_user_id=?", (uid,))


# ==================== OTP ====================
def generate_otp(length=6):
    """کد امن (secrets به‌جای random)"""
    try:
        import secrets
        return "".join(secrets.choice(string.digits) for _ in range(length))
    except ImportError:
        return "".join(random.choices(string.digits, k=length))


def can_resend_otp(uid):
    """
    جلوگیری از اسپم OTP.
    خروجی: (True, 0) یا (False, ثانیه_باقیمانده)
    """
    row = db_execute("""
        SELECT created_at,
               CAST((julianday('now') - julianday(created_at)) * 86400 AS INTEGER) AS age
        FROM otp_codes
        WHERE bale_user_id=?
        ORDER BY id DESC LIMIT 1
    """, (uid,), fetch="one")
    if not row:
        return True, 0
    age = row.get("age")
    if age is None:
        return True, 0
    if age >= OTP_RESEND_SECONDS:
        return True, 0
    return False, OTP_RESEND_SECONDS - int(age)


def save_otp(uid, phone, code):
    db_execute("UPDATE otp_codes SET is_used=1 WHERE bale_user_id=? AND is_used=0", (uid,))
    exp = (datetime.now() + timedelta(minutes=OTP_TTL_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
    return db_execute("""
        INSERT INTO otp_codes (bale_user_id, phone_number, code, expires_at, max_attempts)
        VALUES (?,?,?,?,?)
    """, (uid, phone, code, exp, OTP_MAX_ATTEMPTS))


def verify_otp(uid, code):
    """
    بررسی کد.
    فیکس: قبلاً attempts قبل از مقایسه +1 می‌شد و پیام «باقی‌مانده» یکی کمتر
    نشان می‌داد؛ همچنین کد ورودی نرمال‌سازی نمی‌شد (ارقام فارسی).
    """
    code = normalize_digits(str(code or "").strip())

    otp = db_execute("""
        SELECT * FROM otp_codes
        WHERE bale_user_id=? AND is_used=0 AND expires_at > datetime('now')
        ORDER BY id DESC LIMIT 1
    """, (uid,), fetch="one")

    if not otp:
        return {"success": False, "message": "کد منقضی شده. دوباره درخواست کنید."}

    attempts = otp.get("attempts") or 0
    max_att = otp.get("max_attempts") or OTP_MAX_ATTEMPTS

    if attempts >= max_att:
        db_execute("UPDATE otp_codes SET is_used=1 WHERE id=?", (otp["id"],))
        return {"success": False, "message": "تعداد تلاش تمام شد. کد جدید بگیرید."}

    if str(otp.get("code")) != code:
        db_execute("UPDATE otp_codes SET attempts=attempts+1 WHERE id=?", (otp["id"],))
        remaining = max_att - attempts - 1
        if remaining <= 0:
            db_execute("UPDATE otp_codes SET is_used=1 WHERE id=?", (otp["id"],))
            return {"success": False, "message": "تعداد تلاش تمام شد. کد جدید بگیرید."}
        return {"success": False, "message": f"کد اشتباه است. {remaining} تلاش باقی مانده."}

    db_execute("UPDATE otp_codes SET is_used=1 WHERE id=?", (otp["id"],))
    return {"success": True, "phone": otp.get("phone_number")}


def to_intl_phone(phone):
    """09123456789 → 989123456789 (فرمت مورد نیاز سفیر)"""
    n = normalize_mobile(phone)
    if not n:
        return None
    return "98" + n[1:]


def _safir_post(payload):
    """یک درخواست به سفیر — خروجی (ok, data|error, http_status)"""
    try:
        r = requests.post(
            SAFIR_URL,
            json=payload,
            headers={
                "api-access-key": SAFIR_API_KEY,
                "Content-Type": "application/json",
            },
            timeout=20,
        )
        try:
            data = r.json()
        except Exception:
            data = {"_raw": (r.text or "")[:200]}

        # پاسخ موفق طبق مستندات: {"message_id": "...", "error_data": null}
        if r.status_code in (200, 201) and data.get("message_id") and not data.get("error_data"):
            return True, data, r.status_code

        err = (data.get("error_data") or data.get("message")
               or data.get("error") or data.get("_raw") or f"HTTP {r.status_code}")
        return False, err, r.status_code

    except requests.exceptions.Timeout:
        return False, "timeout — پاسخ سرویس دیر شد", 0
    except Exception as e:
        return False, str(e)[:200], 0


def send_otp_via_safir(phone, code):
    """
    ارسال رمز یکبار مصرف از طریق سرویس سفیر بله.

    فرمت دقیق (مطابق curl شما):
      POST https://safir.bale.ai/api/v3/send_message
      header: api-access-key: <کلید>
      body:
        {
          "bot_id": 317041514,
          "phone_number": "989120000000",
          "message_data": {"otp_message": {"otp": "123456"}}
        }

    ⚠️ نکته حیاتی: bot_id همان شناسه بات OTP در پنل کسب‌وکار است
       و معمولاً با شناسه بات اصلی شما فرق دارد.

    اگر request_id باعث خطا شود، خودکار بدون آن دوباره تلاش می‌شود.
    """
    if not SAFIR_ENABLED:
        reason = []
        if not SAFIR_API_KEY:
            reason.append("SAFIR_API_KEY خالی است")
        if not SAFIR_BOT_ID:
            reason.append("SAFIR_BOT_ID خالی است")
        log(f"📱 [حالت تست] OTP برای {phone}: {code}"
            + (f"  ({'، '.join(reason)})" if reason else ""))
        return {"ok": True, "test_mode": True}

    intl = to_intl_phone(phone)
    if not intl:
        return {"ok": False, "error": "شماره موبایل نامعتبر است"}

    base = {
        "bot_id": int(SAFIR_BOT_ID),
        "phone_number": intl,
        "message_data": {"otp_message": {"otp": str(code)}},
    }

    attempts = []
    if SAFIR_SEND_REQUEST_ID:
        with_id = dict(base)
        with_id["request_id"] = f"nora{int(time.time()*1000)}{random.randint(100, 999)}"
        attempts.append(("با request_id", with_id))
    attempts.append(("بدون request_id", base))

    last_err = "نامشخص"
    for label, payload in attempts:
        ok, data, status = _safir_post(payload)
        if ok:
            log(f"✅ OTP سفیر ارسال شد → {intl} ({label}, msg_id={data.get('message_id')})")
            return {"ok": True, "message_id": data.get("message_id")}

        last_err = data
        log(f"⚠️ سفیر ناموفق ({label}) → {intl} | HTTP {status} | {str(data)[:160]}")

        # این خطاها با تلاش دوباره حل نمی‌شوند
        s = str(data).lower()
        if any(k in s for k in ("unauthor", "invalid key", "access", "403", "401")):
            return {"ok": False, "error": str(data)[:200],
                    "hint": "کلید api-access-key یا bot_id اشتباه است"}

    return {"ok": False, "error": str(last_err)[:200]}


def test_safir_connection(phone=None):
    """
    تست اتصال سفیر — برای دستور /testotp در پنل ادمین.
    خروجی: dict با جزئیات کامل برای عیب‌یابی
    """
    from config import MAIN_BOT_ID
    info = {
        "api_key_set": bool(SAFIR_API_KEY),
        "api_key_preview": (SAFIR_API_KEY[:4] + "***" + SAFIR_API_KEY[-2:]) if SAFIR_API_KEY else "",
        "bot_id": SAFIR_BOT_ID,
        "main_bot_id": MAIN_BOT_ID,
        "same_as_main": SAFIR_BOT_ID == MAIN_BOT_ID,
        "enabled": SAFIR_ENABLED,
        "url": SAFIR_URL,
    }
    if not SAFIR_ENABLED:
        info["result"] = "غیرفعال"
        return info
    if not phone:
        info["result"] = "تنظیمات موجود است (برای تست واقعی شماره بدهید)"
        return info

    code = generate_otp()
    res = send_otp_via_safir(phone, code)
    info["result"] = "موفق ✅" if res.get("ok") else f"ناموفق ❌ — {res.get('error')}"
    info["sent_code"] = code if res.get("test_mode") else "***"
    return info


# ==================== HELPERS ====================
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_DIGIT_MAP = {ord(p): str(i) for i, p in enumerate(PERSIAN_DIGITS)}
_DIGIT_MAP.update({ord(a): str(i) for i, a in enumerate(ARABIC_DIGITS)})
_DIGIT_MAP[ord("\u064a")] = "\u06cc"  # ی عربی
_DIGIT_MAP[ord("\u0643")] = "\u06a9"  # ک عربی


def normalize_digits(text):
    """تبدیل ارقام فارسی/عربی به انگلیسی - فیکس مهم برای ورودی موبایل کاربر"""
    if text is None:
        return ""
    return str(text).translate(_DIGIT_MAP)


def normalize_mobile(m):
    """نرمال‌سازی موبایل به فرمت 09xxxxxxxxx"""
    if m is None:
        return None
    s = normalize_digits(m).strip()
    # حذف ".0" که openpyxl برای اعداد می‌گذارد
    if s.endswith(".0"):
        s = s[:-2]
    for ch in (" ", "-", "(", ")", "+", "\u200c", "\t"):
        s = s.replace(ch, "")
    if not s:
        return None
    if s.startswith("0098"):
        s = "0" + s[4:]
    elif s.startswith("98") and len(s) == 12:
        s = "0" + s[2:]
    elif len(s) == 10 and s.startswith("9"):
        s = "0" + s
    if len(s) == 11 and s.startswith("09") and s.isdigit():
        return s
    return None


def split_full_name(full):
    """
    جدا کردن نام و نام خانوادگی.
    فیکس: قبلاً برای اسم‌های سه‌کلمه‌ای مثل «سید علی محمدی»
    نام='سید' و فامیل='علی محمدی' می‌شد که غلط بود.
    حالا پیشوندها هوشمند مدیریت می‌شوند.
    """
    if not full:
        return None, None
    f = " ".join(normalize_digits(str(full)).split())
    if not f:
        return None, None

    parts = f.split()
    if len(parts) == 1:
        return parts[0], None

    prefixes = {"سید", "سیده", "میر", "شیخ", "حاج", "حاجی", "دکتر", "مهندس", "استاد"}
    if len(parts) >= 3 and parts[0] in prefixes:
        return f"{parts[0]} {parts[1]}", " ".join(parts[2:])
    return parts[0], " ".join(parts[1:])


def validate_national_id(code):
    """اعتبارسنجی کد ملی ایران (با رقم کنترلی)"""
    c = normalize_digits(code).strip()
    if not c.isdigit() or len(c) != 10:
        return False
    if c == c[0] * 10:  # 0000000000، 1111111111 و...
        return False
    if not STRICT_NATIONAL_ID:
        return True
    s = sum(int(c[i]) * (10 - i) for i in range(9))
    r = s % 11
    check = int(c[9])
    return check == r if r < 2 else check == 11 - r


def validate_email(e):
    import re
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$", (e or "").strip()))


def validate_birth_date(d):
    """
    تاریخ شمسی 1370/01/15
    فیکس: قبلاً هیچ اعتبارسنجی‌ای نداشت و هر متنی قبول می‌شد
    """
    s = normalize_digits(d).strip().replace("-", "/").replace(".", "/")
    parts = [p for p in s.split("/") if p != ""]
    if len(parts) != 3:
        return None
    try:
        y, m, dd = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    if y < 100:
        y += 1300
    if not (1250 <= y <= 1450):
        return None
    if not (1 <= m <= 12):
        return None
    max_day = 31 if m <= 6 else (30 if m <= 11 else 30)
    if not (1 <= dd <= max_day):
        return None
    return f"{y:04d}/{m:02d}/{dd:02d}"


# ==================== USER ====================
def get_user(uid):
    return db_execute("SELECT * FROM users WHERE bale_user_id=?", (uid,), fetch="one")


def get_user_by_mobile(m):
    if not m:
        return None
    return db_execute("SELECT * FROM users WHERE mobile=?", (m,), fetch="one")


def get_user_by_id(user_id):
    return db_execute("SELECT * FROM users WHERE id=?", (user_id,), fetch="one")


def is_admin(uid):
    if uid == SUPER_ADMIN_ID:
        return True
    u = get_user(uid)
    return bool(u and u.get("is_admin"))


def is_blocked(uid):
    u = get_user(uid)
    return bool(u and u.get("is_blocked"))


def make_referral_code(bale_id):
    return f"NORA{bale_id}"


def link_bale(user_id, bu):
    """اتصال یک رکورد قدیمی (import شده) به اکانت بله"""
    db_execute("""
        UPDATE users SET
            bale_user_id=?, bale_username=?, bale_first_name=?, bale_last_name=?,
            is_authenticated=1, authenticated_at=CURRENT_TIMESTAMP,
            phone_verified=1, last_activity_at=CURRENT_TIMESTAMP,
            login_count=COALESCE(login_count,0)+1,
            referral_code=COALESCE(NULLIF(referral_code,''), ?),
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (
        bu["id"], bu.get("username", ""), bu.get("first_name", ""),
        bu.get("last_name", ""), make_referral_code(bu["id"]), user_id,
    ))


def create_auth_user(bu, mobile, method):
    """
    ساخت یا آپدیت کاربر احراز شده.
    فیکس: قبلاً first_name کاربر با نام بله overwrite می‌شد و
    نام تأییدشده پروفایل از بین می‌رفت. حالا فقط اگر خالی باشد پر می‌شود.
    """
    uid = bu["id"]
    existing = get_user(uid)

    if existing:
        db_execute("""
            UPDATE users SET
                mobile=?, is_authenticated=1, auth_method=?,
                authenticated_at=CURRENT_TIMESTAMP, phone_verified=1,
                bale_username=?, bale_first_name=?, bale_last_name=?,
                first_name=COALESCE(NULLIF(first_name,''), ?),
                last_name=COALESCE(NULLIF(last_name,''), ?),
                last_activity_at=CURRENT_TIMESTAMP,
                login_count=COALESCE(login_count,0)+1,
                referral_code=COALESCE(NULLIF(referral_code,''), ?),
                updated_at=CURRENT_TIMESTAMP
            WHERE bale_user_id=?
        """, (
            mobile, method,
            bu.get("username", ""), bu.get("first_name", ""), bu.get("last_name", ""),
            bu.get("first_name", ""), bu.get("last_name", ""),
            make_referral_code(uid), uid,
        ))
        return existing["id"]

    return db_execute("""
        INSERT INTO users
        (bale_user_id, bale_username, bale_first_name, bale_last_name,
         first_name, last_name, mobile, referral_code,
         is_authenticated, auth_method, authenticated_at,
         phone_verified, registration_source, last_activity_at, login_count)
        VALUES (?,?,?,?,?,?,?,?,1,?,CURRENT_TIMESTAMP,1,'bot',CURRENT_TIMESTAMP,1)
    """, (
        uid, bu.get("username", ""), bu.get("first_name", ""), bu.get("last_name", ""),
        bu.get("first_name", ""), bu.get("last_name", ""),
        mobile, make_referral_code(uid), method,
    ))


def ensure_super_admin(uid, first_name="سوپرادمین"):
    """ثبت/ارتقای سوپرادمین - idempotent"""
    u = get_user(uid)
    if u:
        if not u.get("is_admin"):
            db_execute("""
                UPDATE users SET is_admin=1, admin_type='super_admin',
                    admin_role='super_admin', is_authenticated=1,
                    profile_status=CASE WHEN profile_status='draft' THEN 'approved' ELSE profile_status END,
                    basic_profile_approved=1
                WHERE bale_user_id=?
            """, (uid,))
        return u["id"]
    return db_execute("""
        INSERT INTO users
        (bale_user_id, first_name, is_admin, admin_type, admin_role,
         is_authenticated, auth_method, referral_code,
         basic_profile_approved, basic_profile_completed, profile_status,
         last_activity_at)
        VALUES (?,?,1,'super_admin','super_admin',1,'system',?,1,1,'approved',CURRENT_TIMESTAMP)
    """, (uid, first_name, make_referral_code(uid)))


def update_activity(uid):
    db_execute("""
        UPDATE users SET last_activity_at=CURRENT_TIMESTAMP,
            login_count=COALESCE(login_count,0)+1
        WHERE bale_user_id=?
    """, (uid,))


def log_action(uid, action, data=None):
    db_execute(
        "INSERT INTO user_actions (bale_user_id, action_type, action_data) VALUES (?,?,?)",
        (uid, action, json.dumps(data, ensure_ascii=False) if data else None),
    )


PERCENT_FIELDS = [
    "first_name", "last_name", "mobile", "national_id", "birth_date",
    "gender", "province", "city", "address", "postal_code",
    "email", "education_level", "field_of_study", "university",
    "job_title", "company_name", "father_name", "mother_name",
    "bio", "profile_photo",
]


def calc_percent(u):
    if not u:
        return 0
    filled = sum(1 for f in PERCENT_FIELDS if str(u.get(f) or "").strip())
    return int(round(filled * 100 / len(PERCENT_FIELDS)))


def update_percent(uid):
    u = get_user(uid)
    if not u:
        return 0
    p = calc_percent(u)
    db_execute(
        "UPDATE users SET complete_profile_percent=?, updated_at=CURRENT_TIMESTAMP WHERE bale_user_id=?",
        (p, uid),
    )
    return p


# ==================== FORCE JOIN ====================
def get_active_channels():
    return db_execute(
        "SELECT * FROM force_join_channels WHERE is_active=1 ORDER BY id",
        fetch="all",
    ) or []


def get_all_channels():
    return db_execute(
        "SELECT * FROM force_join_channels ORDER BY id DESC", fetch="all"
    ) or []


def add_force_channel(identifier, title, added_by, invite_link=None, is_private=False):
    """
    افزودن کانال/گروه.
    identifier: @username یا chat_id عددی منفی
    فیکس: قبلاً chat_id خصوصی در ستون channel_username ذخیره می‌شد
    و در جای دیگر از channel_id خوانده می‌شد -> عملاً کار نمی‌کرد.
    """
    ident = str(identifier).strip()
    dup = db_execute(
        "SELECT id FROM force_join_channels WHERE channel_username=? OR channel_id=?",
        (ident, ident), fetch="one",
    )
    if dup:
        return None

    if is_private:
        return db_execute("""
            INSERT INTO force_join_channels
            (channel_id, channel_username, channel_title, invite_link, is_private, is_active, added_by)
            VALUES (?, '', ?, ?, 1, 1, ?)
        """, (ident, title, invite_link or "", added_by))

    return db_execute("""
        INSERT INTO force_join_channels
        (channel_id, channel_username, channel_title, invite_link, is_private, is_active, added_by)
        VALUES ('', ?, ?, ?, 0, 1, ?)
    """, (ident, title, invite_link or "", added_by))


def set_channel_link(channel_row_id, link):
    db_execute("UPDATE force_join_channels SET invite_link=? WHERE id=?", (link, channel_row_id))


def remove_force_channel(channel_row_id):
    db_execute("DELETE FROM force_join_channels WHERE id=?", (channel_row_id,))


def toggle_force_channel(channel_row_id):
    ch = db_execute(
        "SELECT is_active FROM force_join_channels WHERE id=?",
        (channel_row_id,), fetch="one",
    )
    if not ch:
        return None
    new = 0 if ch["is_active"] else 1
    db_execute("UPDATE force_join_channels SET is_active=? WHERE id=?", (new, channel_row_id))
    return new


def channel_target(ch):
    """شناسه‌ای که باید به getChatMember داده شود"""
    cid = (ch.get("channel_id") or "").strip()
    if cid:
        return cid
    un = (ch.get("channel_username") or "").strip()
    if un and not un.startswith("@"):
        un = "@" + un
    return un


def check_user_joined(user_id, channels):
    """
    چک عضویت. لیست کانال‌هایی که کاربر عضو نیست را برمی‌گرداند.

    فیکس مهم: قبلاً هر خطای API (مثلاً ادمین نبودن ربات) به معنی
    «عضو نیست» تفسیر می‌شد و همه کاربران قفل می‌شدند.
    حالا با FORCE_JOIN_FAIL_OPEN خطای سیستمی نادیده گرفته می‌شود.
    """
    not_joined = []
    for ch in channels or []:
        target = channel_target(ch)
        if not target:
            continue
        try:
            from bale_api import get_chat_member
            res = get_chat_member(target, user_id)

            if res.get("ok"):
                status = (res.get("result") or {}).get("status", "")
                if status in ("creator", "administrator", "member", "owner"):
                    continue
                not_joined.append(ch)
            else:
                desc = str(res.get("description", "")).lower()
                if "not found" in desc or "user not found" in desc:
                    not_joined.append(ch)
                else:
                    log(f"⚠️ چک عضویت {target} ناموفق: {res.get('description')}")
                    if not FORCE_JOIN_FAIL_OPEN:
                        not_joined.append(ch)
        except Exception as e:
            log(f"⚠️ خطای چک عضویت {target}: {e}")
            if not FORCE_JOIN_FAIL_OPEN:
                not_joined.append(ch)
    return not_joined
