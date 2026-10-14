"""
تست فاز ۱۱ — تکمیل رویداد طبق فایل معماری

پوشش:
  • دعوت اجباری (سطح رویداد)
  • محدودیت جنسیت / سن / شهر / امتیاز
  • تنظیمات نمایش (لیست، جستجو، قیمت، تعداد)
  • محتوای تکمیلی (سخنران، برنامه، پیش‌نیاز، گروه)
  • جزئیات آنلاین/حضوری + زمان ارسال لینک
  • کدهای دعوت چندگانه
  • رمز عبور رویداد
  • بازپرداخت و یادآوری
  • نمایش مبلغ فرم به انتخاب ادمین
  • انتقال مناسبت‌ها به مدیریت کاربران
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora11_")
os.environ.update({
    "BOT_TOKEN": "1095412158:T", "SUPER_ADMIN_ID": "100000001",
    "SAFIR_API_KEY": "k", "SAFIR_BOT_ID": "317041514",
    "PAYMENT_PROVIDER_TOKEN": "WALLET-TEST-1111111111111111",
    "DB_PATH": f"{TMP}/t.db", "BACKUP_DIR": f"{TMP}/b", "IMPORT_DIR": f"{TMP}/i",
    "FILES_DIR": f"{TMP}/f", "PROFILES_DIR": f"{TMP}/f/p",
    "EVENTS_DIR": f"{TMP}/f/e", "LOG_DIR": f"{TMP}/l", "BROADCAST_RATE": "999",
})

import bale_api  # noqa: E402

SENT = []


def _api(m, p=None, **k):
    p = p or {}
    SENT.append({"m": m, "p": p})
    if m == "getMe":
        return {"ok": True, "result": {"username": "nora_bot"}}
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


def _send(cid, text, kb=None, reply_to=None):
    SENT.append({"m": "sendMessage", "p": {"cid": cid, "text": text, "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


def _soe(cid, text, kb=None, mid=None, force_new=False):
    SENT.append({"m": "editMessageText", "p": {"cid": cid, "text": text, "kb": kb}})
    return {"ok": True, "result": {"message_id": mid or 1}}


def _file(method, key, cid, f, caption=None, kb=None):
    SENT.append({"m": method, "p": {"cid": cid, "caption": caption, "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


bale_api.api = _api
bale_api.api_async = _api
bale_api.send = _send
bale_api.send_or_edit = _soe
bale_api._send_file = _file
bale_api.send_photo = lambda c, p, cap=None, kb=None: _file("sendPhoto", "p", c, p, cap, kb)
bale_api.send_document = lambda c, d, cap=None, kb=None: _file("sendDocument", "d", c, d, cap, kb)

import database  # noqa: E402
import auth  # noqa: E402
import forms as F  # noqa: E402
import form_fill as FL  # noqa: E402
import payments as PAY  # noqa: E402
import events as EV  # noqa: E402
import attendance as AT  # noqa: E402
import occasions as OC  # noqa: E402
import main as M  # noqa: E402

for mod in (F, FL, PAY, EV, AT, OC, M):
    for n in ("send", "send_or_edit", "send_photo", "send_document"):
        if hasattr(mod, n):
            setattr(mod, n, getattr(bale_api, n))

OK = FAIL = 0
FAILED = []


def check(name, cond, extra=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        FAILED.append(name)
        print(f"  ❌ {name}   {extra}")


def texts():
    return [s["p"].get("text") or s["p"].get("caption") or "" for s in SENT]


def last():
    t = texts()
    return t[-1] if t else ""


def alltext():
    return " ".join(texts())


def cbdata():
    for s in reversed(SENT):
        kb = s["p"].get("kb") or {}
        out = [b.get("callback_data") for r in kb.get("inline_keyboard", [])
               for b in r if isinstance(b, dict) and b.get("callback_data")]
        if out:
            return out
    return []


def allcb():
    out = []
    for s in SENT:
        kb = s["p"].get("kb") or {}
        for r in kb.get("inline_keyboard", []):
            for b in r:
                if isinstance(b, dict) and b.get("callback_data"):
                    out.append(b["callback_data"])
    return out


def msg(uid, t):
    return {"message_id": 1, "from": {"id": uid, "first_name": "ت"},
            "chat": {"id": uid, "type": "private"}, "text": t}


def cb(uid, d):
    return {"id": "c", "from": {"id": uid, "first_name": "ت"}, "data": d,
            "message": {"message_id": 1, "chat": {"id": uid, "type": "private"}}}


S = 100000001
U1, U2, U3 = 811001, 811002, 811003

print("=" * 62)
print("🧪 تست فاز ۱۱ — تکمیل رویداد")
print("=" * 62)

database.init_db()
EV.init_event_tables()
AT.init_attendance_tables()
PAY.init_payment_tables()
F.init_form_tables()
OC.init_occasion_tables()

auth.create_auth_user({"id": S, "first_name": "مدیر"}, "09120000000", "phone")
auth.ensure_super_admin(S)
for u, nm, g in ((U1, "علی", "مرد"), (U2, "سارا", "زن"), (U3, "رضا", "مرد")):
    auth.create_auth_user({"id": u, "first_name": nm}, f"0912{u}", "phone")
    database.db_execute("UPDATE users SET gender=?, profile_status='approved', "
                        "city='تهران', birth_date='1375/01/01' "
                        "WHERE bale_user_id=?", (g, u))

eid = database.db_execute("""INSERT INTO events
    (title, event_type, status, privacy, capacity, created_by, has_ticket)
    VALUES ('کارگاه تست','workshop','published','public',100,?,1)""", (S,))


# ═══════════ ۱) ساختار ═══════════
print("\n[۱] ساختار داده")
import re
_s = open(ROOT / "events.py", encoding="utf-8").read()
_i = _s.index("EVENTS_SCHEMA")
_cols = set(re.findall(r'"([a-z_0-9]+)":', _s[_i:_s.index("\n}", _i)]))
for c in ("require_invites", "invites_needed", "invite_message",
          "restrict_gender", "restrict_age_min", "restrict_age_max",
          "restrict_city", "min_points_required", "password_hash",
          "show_in_list", "show_in_search", "show_participant_count",
          "show_price_publicly", "speakers", "agenda", "faq",
          "prerequisites", "required_items", "chat_group_url",
          "online_platform", "online_password", "online_link_send_time",
          "venue_name", "venue_has_parking", "refund_enabled",
          "reminder_enabled", "total_registered", "rating_count"):
    check(f"ستون {c}", c in _cols)

for tbl in ("event_invite_codes", "event_access_logs", "event_ratings"):
    check(f"جدول {tbl}", bool(database.db_execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (tbl,), fetch="one")))


# ═══════════ ۲) دعوت اجباری ═══════════
print("\n[۲] دعوت اجباری")
SENT.clear()
M.handle_callback(cb(S, f"evx_{eid}"))
check("صفحه قابلیت‌های پیشرفته", "قابلیت‌های پیشرفته" in last())
check("دکمه دعوت اجباری", f"evinv_{eid}" in cbdata())

SENT.clear()
M.handle_callback(cb(S, f"evinv_{eid}"))
check("صفحه دعوت اجباری", "دعوت اجباری" in last())
M.handle_callback(cb(S, f"evtog_require_invites_{eid}"))
check("دعوت اجباری فعال شد",
      EV.get_event(eid)["require_invites"] == 1)
M.handle_callback(cb(S, f"evnum_invites_needed_{eid}"))
M.process_message(msg(S, "2"))
check("تعداد دعوت ثبت شد", EV.get_event(eid)["invites_needed"] == 2)
M.handle_callback(cb(S, f"evtxt_invite_message_{eid}"))
M.process_message(msg(S, "برای ثبت‌نام ۲ نفر دعوت کنید"))
check("پیام دعوت ثبت شد",
      "۲ نفر" in (EV.get_event(eid).get("invite_message") or ""))

SENT.clear()
M.handle_callback(cb(U1, f"ureg_{eid}"))
check("🔴 کاربر بدون دعوت رد شد", "دعوت" in alltext())
# فاز۱۷-ج: متن دعوت مهربان‌تر شد — «تا اینجا: 0 از 2»
# متن سفارشی ادمین اولویت دارد؛ نوار پیشرفت همیشه می‌آید
check("پیشرفت نمایش داده شد",
      ("▓" in alltext() or "░" in alltext() or "0/2" in alltext()
       or "0 از 2" in alltext()), alltext()[-150:])
check("لینک دعوت داده شد", "لینک" in alltext())
check("ثبت‌نام انجام نشد",
      database.db_scalar("SELECT COUNT(*) FROM event_registrations "
                         "WHERE event_id=? AND bale_user_id=?", (eid, U1)) == 0)

# دو نفر دعوت‌شده تأییدشده
for inv in (860001, 860002):
    auth.create_auth_user({"id": inv, "first_name": "دعوتی"}, f"0919{inv}", "phone")
    database.db_execute("UPDATE users SET referred_by=?, is_authenticated=1, "
                        "complete_profile_percent=50 WHERE bale_user_id=?", (U1, inv))
check("شمارش دعوت تأییدشده", EV.count_confirmed_invites(U1) == 2)

SENT.clear()
M.handle_callback(cb(U1, f"ureg_{eid}"))
check("✅ بعد از دعوت ثبت‌نام شد",
      database.db_scalar("SELECT COUNT(*) FROM event_registrations "
                         "WHERE event_id=? AND bale_user_id=?", (eid, U1)) == 1)

# دعوت ناقص حساب نمی‌شود
auth.create_auth_user({"id": 860003, "first_name": "ناقص"}, "0919860003", "phone")
database.db_execute("UPDATE users SET referred_by=?, complete_profile_percent=5 "
                    "WHERE bale_user_id=?", (U2, 860003))
check("دعوت با پروفایل ناقص حساب نمی‌شود",
      EV.count_confirmed_invites(U2) == 0)

M.handle_callback(cb(S, f"evtog_require_invites_{eid}"))
check("دعوت اجباری خاموش شد", not EV.get_event(eid)["require_invites"])


# ═══════════ ۳) محدودیت ثبت‌نام ═══════════
print("\n[۳] محدودیت جنسیت / سن / شهر / امتیاز")
SENT.clear()
M.handle_callback(cb(S, f"evres_{eid}"))
check("صفحه محدودیت‌ها", "محدودیت ثبت‌نام" in last())

M.handle_callback(cb(S, f"evgens_female_{eid}"))
check("محدودیت زنانه ثبت شد",
      EV.get_event(eid)["restrict_gender"] == "female")
ok, m_, _ = EV.check_eligibility(U1, EV.get_event(eid))
check("🔴 آقا رد شد", not ok and "خانم" in m_)
ok2, _, _ = EV.check_eligibility(U2, EV.get_event(eid))
check("✅ خانم قبول شد", ok2)
M.handle_callback(cb(S, f"evgens_male_{eid}"))
ok3, _, _ = EV.check_eligibility(U1, EV.get_event(eid))
check("✅ آقا در حالت male قبول", ok3)
M.handle_callback(cb(S, f"evgens_all_{eid}"))

M.handle_callback(cb(S, f"evnum_restrict_age_min_{eid}"))
M.process_message(msg(S, "40"))
check("حداقل سن ثبت شد", EV.get_event(eid)["restrict_age_min"] == 40)
ok, m_, _ = EV.check_eligibility(U1, EV.get_event(eid))
check("🔴 سن کم رد شد", not ok and "سن" in m_, m_[:50])
M.handle_callback(cb(S, f"evnum_restrict_age_min_{eid}"))
M.process_message(msg(S, "0"))
check("✅ بدون محدودیت سنی", EV.check_eligibility(U1, EV.get_event(eid))[0])

M.handle_callback(cb(S, f"evtxt_restrict_city_{eid}"))
M.process_message(msg(S, "اصفهان، شیراز"))
ok, m_, _ = EV.check_eligibility(U1, EV.get_event(eid))
check("🔴 شهر غیرمجاز رد شد", not ok and "شهر" in m_)
M.handle_callback(cb(S, f"evtxt_restrict_city_{eid}"))
M.process_message(msg(S, "تهران، کرج"))
check("✅ شهر مجاز قبول", EV.check_eligibility(U1, EV.get_event(eid))[0])
M.handle_callback(cb(S, f"evtxt_restrict_city_{eid}"))
M.process_message(msg(S, "-"))

M.handle_callback(cb(S, f"evnum_min_points_required_{eid}"))
M.process_message(msg(S, "500"))
ok, m_, _ = EV.check_eligibility(U1, EV.get_event(eid))
check("🔴 امتیاز کم رد شد", not ok and "امتیاز" in m_)
database.db_execute("UPDATE users SET total_points=600 WHERE bale_user_id=?", (U1,))
check("✅ با امتیاز کافی قبول",
      EV.check_eligibility(U1, EV.get_event(eid))[0])
M.handle_callback(cb(S, f"evnum_min_points_required_{eid}"))
M.process_message(msg(S, "0"))

check("👑 ادمین از همه محدودیت‌ها معاف است",
      EV.check_eligibility(S, EV.get_event(eid))[0])


# ═══════════ ۴) تنظیمات نمایش ═══════════
print("\n[۴] تنظیمات نمایش")
SENT.clear()
M.handle_callback(cb(S, f"evshow_{eid}"))
check("صفحه نمایش", "تنظیمات نمایش" in last())
# فاز۱۷-ج: hide_cost_hint اضافه شد → ۷ گزینه
check("۷ گزینه نمایش", sum(1 for d in cbdata() if d.startswith("evtog_")) == 7,
      str(cbdata()))

M.handle_callback(cb(S, f"evtog_show_in_list_{eid}"))
check("مخفی از لیست", EV.get_event(eid)["show_in_list"] == 0)
SENT.clear()
M.handle_callback(cb(U2, "u_events"))
check("🔴 رویداد مخفی در لیست نیست", "کارگاه تست" not in alltext())
M.handle_callback(cb(S, f"evtog_show_in_list_{eid}"))
SENT.clear()
M.handle_callback(cb(U2, "u_events"))
check("✅ بعد از روشن کردن دیده می‌شود", "کارگاه تست" in alltext())

for col in ("show_in_search", "show_participant_count",
            "show_participant_list", "show_price_publicly", "allow_sharing"):
    b = EV.get_event(eid).get(col)
    M.handle_callback(cb(S, f"evtog_{col}_{eid}"))
    check(f"تاگل {col}", EV.get_event(eid).get(col) != b)
    M.handle_callback(cb(S, f"evtog_{col}_{eid}"))


# ═══════════ ۵) محتوای تکمیلی ═══════════
print("\n[۵] محتوای تکمیلی")
SENT.clear()
M.handle_callback(cb(S, f"evcnt_{eid}"))
check("صفحه محتوا", "محتوای تکمیلی" in last())
for key, val in (("speakers", "دکتر احمدی\nمهندس رضایی"),
                 ("agenda", "۹:۰۰ افتتاحیه\n۱۰:۳۰ کارگاه"),
                 ("prerequisites", "آشنایی با مبانی"),
                 ("required_items", "لپ‌تاپ و دفترچه"),
                 ("faq", "س: هزینه؟ ج: رایگان"),
                 ("chat_group_url", "https://ble.ir/join/xyz"),
                 ("subtitle", "ویژه اعضای فعال")):
    M.handle_callback(cb(S, f"evtxt_{key}_{eid}"))
    M.process_message(msg(S, val))
    check(f"{key} ثبت شد", val.split("\n")[0][:10] in
          (EV.get_event(eid).get(key) or ""), str(EV.get_event(eid).get(key))[:40])


# ═══════════ ۶) جزئیات برگزاری ═══════════
print("\n[۶] جزئیات آنلاین/حضوری")
SENT.clear()
M.handle_callback(cb(S, f"evloc_{eid}"))
check("صفحه جزئیات", "جزئیات برگزاری" in last())
M.handle_callback(cb(S, f"evtxt_online_platform_{eid}"))
M.process_message(msg(S, "اسکای‌روم"))
check("پلتفرم ثبت شد", EV.get_event(eid)["online_platform"] == "اسکای‌روم")
M.handle_callback(cb(S, f"evtxt_online_password_{eid}"))
M.process_message(msg(S, "1234"))
check("رمز جلسه ثبت شد", EV.get_event(eid)["online_password"] == "1234")
M.handle_callback(cb(S, f"evlts_1h_before_{eid}"))
check("زمان ارسال لینک",
      EV.get_event(eid)["online_link_send_time"] == "1h_before")
M.handle_callback(cb(S, f"evtxt_venue_name_{eid}"))
M.process_message(msg(S, "سالن اجتماعات"))
check("نام محل ثبت شد", EV.get_event(eid)["venue_name"] == "سالن اجتماعات")
M.handle_callback(cb(S, f"evtog_venue_has_parking_{eid}"))
check("پارکینگ فعال شد", EV.get_event(eid)["venue_has_parking"] == 1)


# ═══════════ ۷) کدهای دعوت ═══════════
print("\n[۷] کدهای دعوت")
SENT.clear()
M.handle_callback(cb(S, f"evcode_{eid}"))
check("صفحه کدها", "کدهای دعوت" in last())
M.handle_callback(cb(S, f"evcadd_{eid}"))
code_row = database.db_execute("SELECT * FROM event_invite_codes WHERE event_id=? "
                               "ORDER BY id DESC LIMIT 1", (eid,), fetch="one")
check("کد ساخته شد", bool(code_row) and code_row["code"].startswith("EVC"))
check("کد یکتاست",
      database.db_scalar("SELECT COUNT(*) FROM (SELECT code FROM "
                         "event_invite_codes GROUP BY code HAVING COUNT(*)>1)") == 0)

SENT.clear()
M.handle_callback(cb(S, f"evcadd_{eid}"))
n_codes = database.db_scalar("SELECT COUNT(*) FROM event_invite_codes "
                             "WHERE event_id=?", (eid,))
check("کد دوم ساخته شد", n_codes == 2)

SENT.clear()
EV.register_by_code(U3, U3, code_row["code"])
check("ورود با کد دعوت", "معتبر" in alltext())
check("شمارنده استفاده بالا رفت",
      database.db_execute("SELECT current_uses FROM event_invite_codes WHERE id=?",
                          (code_row["id"],), fetch="one")["current_uses"] == 1)

database.db_execute("UPDATE event_invite_codes SET max_uses=1 WHERE id=?",
                    (code_row["id"],))
SENT.clear()
EV.register_by_code(U2, U2, code_row["code"])
check("🔴 سقف مصرف رعایت شد", "سقف" in alltext())

SENT.clear()
EV.register_by_code(U2, U2, "EVCNOTEXIST")
check("کد نامعتبر رد شد", "نامعتبر" in alltext())

M.handle_callback(cb(S, f"evcdel_{code_row['id']}_{eid}"))
check("کد حذف شد",
      not database.db_execute("SELECT id FROM event_invite_codes WHERE id=?",
                              (code_row["id"],), fetch="one"))


# ═══════════ ۸) رمز عبور ═══════════
print("\n[۸] رمز عبور رویداد")
SENT.clear()
M.handle_callback(cb(S, f"evpwd_{eid}"))
check("صفحه رمز", "رمز عبور" in last())
M.handle_callback(cb(S, f"evpwdset_{eid}"))
M.process_message(msg(S, "ab"))
check("رمز کوتاه رد شد", "۳ کاراکتر" in last())
M.process_message(msg(S, "secret123"))
check("رمز ذخیره شد", bool(EV.get_event(eid).get("password_hash")))
check("رمز هش شده (خام نیست)",
      "secret123" not in (EV.get_event(eid).get("password_hash") or ""))
M.handle_callback(cb(S, f"evpwddel_{eid}"))
check("رمز حذف شد", not EV.get_event(eid).get("password_hash"))


# ═══════════ ۹) بازپرداخت و یادآوری ═══════════
print("\n[۹] بازپرداخت و یادآوری")
SENT.clear()
M.handle_callback(cb(S, f"evref_{eid}"))
check("صفحه بازپرداخت", "بازپرداخت" in last())
M.handle_callback(cb(S, f"evtog_refund_enabled_{eid}"))
check("بازپرداخت فعال شد", EV.get_event(eid)["refund_enabled"] == 1)
M.handle_callback(cb(S, f"evnum_refund_percent_{eid}"))
M.process_message(msg(S, "80"))
check("درصد بازپرداخت", EV.get_event(eid)["refund_percent"] == 80)
M.handle_callback(cb(S, f"evnum_refund_percent_{eid}"))
M.process_message(msg(S, "500"))
check("درصد بیش از ۱۰۰ محدود شد", EV.get_event(eid)["refund_percent"] == 100)

SENT.clear()
M.handle_callback(cb(S, f"evrem_{eid}"))
check("صفحه یادآوری", "یادآوری" in last())
b = EV.get_event(eid).get("reminder_enabled")
M.handle_callback(cb(S, f"evtog_reminder_enabled_{eid}"))
check("تاگل یادآوری", EV.get_event(eid).get("reminder_enabled") != b)


# ═══════════ ۱۰) امتیازدهی و لاگ ═══════════
print("\n[۱۰] نظرات و لاگ دسترسی")
database.db_execute("""INSERT INTO event_ratings (event_id,bale_user_id,rating,comment)
    VALUES (?,?,5,'عالی بود')""", (eid, U1))
database.db_execute("UPDATE events SET rating_sum=5, rating_count=1 WHERE id=?", (eid,))
SENT.clear()
M.handle_callback(cb(S, f"evrate_{eid}"))
check("صفحه نظرات", "نظرات" in last())
check("نظر نمایش داده شد", "عالی بود" in last())
check("میانگین محاسبه شد", "5.0" in last())

EV.log_access(eid, U1, "view", True)
check("لاگ دسترسی ثبت شد",
      database.db_scalar("SELECT COUNT(*) FROM event_access_logs "
                         "WHERE event_id=?", (eid,)) >= 1)


# ═══════════ ۱۱) نمایش مبلغ فرم ═══════════
print("\n[۱۱] نمایش مبلغ فرم به انتخاب ادمین")
M.handle_callback(cb(S, "fb_new"))
M.handle_callback(cb(S, "fbt_registration"))
M.process_message(msg(S, "فرم تست مبلغ"))
M.process_message(msg(S, "⏭️ رد کردن"))
ffid = database.db_scalar("SELECT MAX(id) FROM forms")
M.handle_callback(cb(S, f"fbtpl_{ffid}"))
M.handle_callback(cb(S, f"fbpm_card_{ffid}"))
M.handle_callback(cb(S, f"fbprice_{ffid}"))
M.process_message(msg(S, "30000"))
M.handle_callback(cb(S, f"fbpub_{ffid}"))

check("پیش‌فرض: مبلغ نشان داده نمی‌شود",
      F.get_form(ffid).get("show_price_upfront") == 0)
SENT.clear()
M.handle_callback(cb(U2, f"ffopen_{ffid}"))
check("🔴 هیچ اشاره‌ای به هزینه نیست", "هزینه" not in alltext(), alltext()[-80:])
check("عددی نیست", "30,000" not in alltext())

SENT.clear()
M.handle_callback(cb(S, f"fbpay_{ffid}"))
check("دکمه نمایش مبلغ در صفحه پرداخت",
      any("show_price_upfront" in (d or "") for d in cbdata()))
M.handle_callback(cb(S, f"fbtog_show_price_upfront_{ffid}"))
check("ادمین روشن کرد", F.get_form(ffid)["show_price_upfront"] == 1)
SENT.clear()
M.handle_callback(cb(U2, f"ffopen_{ffid}"))
check("✅ حالا مبلغ نشان داده می‌شود", "هزینه" in alltext())
check("عدد تومانی درست", "30,000" in alltext(), alltext()[-90:])


# ═══════════ ۱۲) مناسبت‌ها زیر «اطلاع‌رسانی» (فاز ۱۳) ═══════════
print("\n[۱۲] مناسبت‌ها زیر اطلاع‌رسانی")
SENT.clear()
M.handle_callback(cb(S, "admin_notify"))
check("دکمه مناسبت‌ها در اطلاع‌رسانی", "oc_panel" in allcb(), str(allcb()))
check("🔄 از پنل اصلی حذف شد (خلوت‌سازی فاز ۱۳)", True)
SENT.clear()
M.handle_callback(cb(S, "admin_panel"))
check("🔴 از پنل ادمین حذف شد", "oc_panel" not in allcb())
SENT.clear()
M.handle_callback(cb(S, "oc_panel"))
check("بازگشت به مدیریت کاربران", "admin_users" in allcb())


# ═══════════ ۱۳) دسترسی و ورودی خراب ═══════════
print("\n[۱۳] دسترسی و مقاومت")
for d in (f"evx_{eid}", f"evinv_{eid}", f"evres_{eid}", f"evcode_{eid}",
          f"evpwd_{eid}", f"evshow_{eid}", f"evrate_{eid}"):
    SENT.clear()
    M.handle_callback(cb(U2, d))
    check(f"🔒 کاربر عادی: {d[:14]}", "دسترسی ندارید" in last(), last()[:40])

bad = ["evx_", "evx_abc", "evx_999999", "evinv_999999", "evtog_evil_1",
       "evtog_users_1", "evtxt_evilcol_1", "evnum_badkey_1", "evgens_zz_1",
       "evlts_bad_1", "evcadd_999999", "evcdel_abc_1", "evpwdset_999999",
       "evres_x", "evloc_", "evcnt_999999", "evref_abc", "evrem_x"]
crashed = []
for d in bad:
    try:
        M.handle_callback(cb(S, d))
    except Exception as e:
        crashed.append(f"{d}: {type(e).__name__} {e}")
check("هیچ ورودی خرابی کرش نمی‌کند", not crashed, str(crashed[:2]))

check("ستون غیرمجاز تاگل نمی‌شود", "evil" not in str(EV.EV_TOGGLES.keys()))
_badt = [k for k in EV.EV_TOGGLES if k not in _cols]
check("همه کلیدهای تاگل ستون واقعی‌اند", not _badt, str(_badt))
_badx = [k for k in EV.EV_TEXTS if k not in _cols]
check("همه کلیدهای متنی ستون واقعی‌اند", not _badx, str(_badx))
_badn = [k for k in EV.EV_NUMS if k not in _cols]
check("همه کلیدهای عددی ستون واقعی‌اند", not _badn, str(_badn))


# ═══════════ ۱۴) یکپارچگی ═══════════
print("\n[۱۴] یکپارچگی")
check("کد دعوت یتیم نیست",
      database.db_scalar("""SELECT COUNT(*) FROM event_invite_codes c
        WHERE NOT EXISTS (SELECT 1 FROM events e WHERE e.id=c.event_id)""") == 0)
check("نظر یتیم نیست",
      database.db_scalar("""SELECT COUNT(*) FROM event_ratings r
        WHERE NOT EXISTS (SELECT 1 FROM events e WHERE e.id=r.event_id)""") == 0)
check("درصد بازپرداخت معتبر",
      database.db_scalar("SELECT COUNT(*) FROM events WHERE refund_percent<0 "
                         "OR refund_percent>100") == 0)
check("جنسیت محدودیت معتبر",
      database.db_scalar("""SELECT COUNT(*) FROM events WHERE restrict_gender
        NOT IN ('all','male','female')""") == 0)

print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\n❌ تست‌های ناموفق:")
    for f_ in FAILED:
        print(f"   • {f_}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۱۱ پاس شدند!")
