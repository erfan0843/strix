"""
تست فاز ۱۰ — تومان، پروفایل خودکار، تأیید شماره، مناسبت‌ها

پوشش هفت درخواست کاربر:
  ۱) پرکردن پروفایل از فرم تأییدی ادمین
  ۲) عدم نمایش مبلغ در ابتدای فرم
  ۳) تبدیل ریال ↔ تومان
  ۴) صورتحساب نهایی به ریال
  ۵) روش تأیید شماره (دکمه / کد / هر دو)
  ۶) انتخاب نحوه نمایش سوالات
  ۷) تبریک تولد و مناسبت‌ها + امتیاز
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora10_")
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
    if m == "getChatMember":
        return {"ok": True, "result": {"status": "member"}}
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

import config  # noqa: E402
import database  # noqa: E402
import auth  # noqa: E402
import forms as F  # noqa: E402
import form_fields as FF  # noqa: E402
import form_fill as FL  # noqa: E402
import form_reports as FR  # noqa: E402
import payments as PAY  # noqa: E402
import events as EV  # noqa: E402
import attendance as AT  # noqa: E402
import occasions as OC  # noqa: E402
import main as M  # noqa: E402

for mod in (F, FF, FL, FR, PAY, EV, AT, OC, M):
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


def kbl():
    for s in reversed(SENT):
        kb = s["p"].get("kb") or {}
        rows = kb.get("inline_keyboard") or kb.get("keyboard") or []
        out = [b["text"] if isinstance(b, dict) else str(b) for r in rows for b in r]
        if out:
            return out
    return []


def cbdata():
    for s in reversed(SENT):
        kb = s["p"].get("kb") or {}
        out = [b.get("callback_data") for r in kb.get("inline_keyboard", [])
               for b in r if isinstance(b, dict) and b.get("callback_data")]
        if out:
            return out
    return []


def msg(uid, t):
    return {"message_id": 1, "from": {"id": uid, "first_name": "ت"},
            "chat": {"id": uid, "type": "private"}, "text": t}


def cb(uid, d):
    return {"id": "c", "from": {"id": uid, "first_name": "ت"}, "data": d,
            "message": {"message_id": 1, "chat": {"id": uid, "type": "private"}}}


S = 100000001
U1, U2, U3 = 910001, 910002, 910003

print("=" * 62)
print("🧪 تست فاز ۱۰ — تومان، پروفایل، مناسبت‌ها")
print("=" * 62)

database.init_db()
EV.init_event_tables()
AT.init_attendance_tables()
PAY.init_payment_tables()
F.init_form_tables()
OC.init_occasion_tables()

auth.create_auth_user({"id": S, "first_name": "مدیر"}, "09120000000", "phone")
auth.ensure_super_admin(S)
for u, nm in ((U1, "علی"), (U2, "سارا"), (U3, "رضا")):
    auth.create_auth_user({"id": u, "first_name": nm}, f"091200{u}", "phone")

database.db_execute("INSERT INTO bank_cards (owner_id,bank_name,card_number,"
                    "card_holder_name,is_active) VALUES (?,?,?,?,1)",
                    (S, "ملی", "6037991234567890", "مدیر"))


# ═══════════════ ۳) واحد پول — همه‌جا ریال ═══════════════
print("\n[۳] واحد پول یکسان: ریال")
check("واحد پیش‌فرض ریال است", config.CURRENCY_LABEL == "ریال",
      config.CURRENCY_LABEL)
check("واحد قفل روی ریال", config.MONEY_UNIT == "rial", config.MONEY_UNIT)
check("money() ریال می‌دهد", "5,000" in config.money(5000)
      and "ریال" in config.money(5000), config.money(5000))
check("money_rial() هم‌معنی money()",
      config.money_rial(5000) == config.money(5000))
check("money بدون واحد", config.money(5000, False) == "5,000",
      config.money(5000, False))
check("parse_money بدون تبدیل", config.parse_money("2500") == 2500)
check("parse_money ارقام فارسی", config.parse_money("۱۰۰۰") == 1000)
check("parse_money متن نامعتبر", config.parse_money("abc") == 0)
check("money ورودی خراب", config.money(None, False) == "0",
      config.money(None, False))

# 🔴 قلب ماجرا: چهار تابع نمایش باید دقیقاً یک عدد بدهند
_R = 700000
_four = {
    "config.money":     config.money(_R, False).replace(",", ""),
    "forms.fmt_amount": F.fmt_amount(_R).replace(",", ""),
    "payments.fmt":     PAY.fmt(_R).replace("٬", ""),
    "events.fmt_money": EV.fmt_money(_R).replace("٬", ""),
}
check("🔴 هر چهار تابع نمایش یکسان‌اند", len(set(_four.values())) == 1,
      str(_four))
check("🔴 و عدد دست‌نخورده است", set(_four.values()) == {"700000"},
      str(_four))
check("payments.fmt_rial هم‌معنی fmt", PAY.fmt_rial(_R) == PAY.fmt(_R))


# ═══════════════ ساخت فرم پولی ═══════════════
print("\n[۳.۱] ورودی ادمین ریال → ذخیره همان عدد")
M.handle_callback(cb(S, "fb_new"))
M.handle_callback(cb(S, "fbt_registration"))
M.process_message(msg(S, "ثبت‌نام دوره فن بیان"))
M.process_message(msg(S, "⏭️ رد کردن"))
fid = database.db_scalar("SELECT MAX(id) FROM forms")
M.handle_callback(cb(S, f"fbtpl_{fid}"))
M.handle_callback(cb(S, f"fbpm_card_{fid}"))
M.handle_callback(cb(S, f"fbprice_{fid}"))
M.process_message(msg(S, "200000"))
check("۲۰۰٬۰۰۰ ریال عیناً ذخیره شد",
      F.get_form(fid)["price"] == 200000, str(F.get_form(fid)["price"]))

course = next(f for f in F.get_fields(fid)
              if F.field_meta(f["field_type"])["kind"] == "item")
M.handle_callback(cb(S, f"fbia_{course['id']}"))
M.process_message(msg(S, "دوره مقدماتی | 500000 | 2"))
M.handle_callback(cb(S, f"fbia_{course['id']}"))
M.process_message(msg(S, "دوره پیشرفته | 1200000"))
items = F.parse_items(F.get_field(course["id"]))
check("آیتم ۵۰۰٬۰۰۰ ریال عیناً ذخیره شد", items[0]["price"] == 500000,
      str(items[0]["price"]))
check("ظرفیت آیتم ثبت شد", items[0]["capacity"] == 2)
check("آیتم دوم بدون ظرفیت", items[1]["capacity"] == 0)
check("نمایش آیتم به ریال", "500,000" in F.item_label(items[0]),
      F.item_label(items[0]))


# ═══════════════ ۵) روش تأیید شماره ═══════════════
print("\n[۵] روش تأیید شماره موبایل")
check("۳ حالت تعریف شده", len(F.PHONE_VERIFY_MODES) == 3)
check("پیش‌فرض both", (F.get_form(fid).get("phone_verify_mode") or "both") == "both")
SENT.clear()
M.handle_callback(cb(S, f"fbpv_{fid}"))
check("صفحه انتخاب روش", "روش تأیید شماره" in last())
check("۳ گزینه نمایش", sum(1 for d in cbdata() if d.startswith("fbpvs_")) == 3)
for mode in ("contact", "otp", "both"):
    M.handle_callback(cb(S, f"fbpvs_{mode}_{fid}"))
    check(f"حالت {mode} ذخیره شد",
          F.get_form(fid)["phone_verify_mode"] == mode)


# ═══════════════ ۱) تأیید ادمین + پروفایل ═══════════════
print("\n[۱] تأیید ادمین و پرکردن پروفایل")
check("پیش‌فرض تأیید لازم نیست", not F.get_form(fid).get("needs_approval"))
check("پیش‌فرض پرکردن پروفایل روشن", F.get_form(fid).get("fill_profile") == 1)
M.handle_callback(cb(S, f"fbtog_needs_approval_{fid}"))
check("تأیید ادمین فعال شد", F.get_form(fid)["needs_approval"] == 1)
M.handle_callback(cb(S, f"fbpvs_contact_{fid}"))
M.handle_callback(cb(S, f"fbpub_{fid}"))


# ═══════════════ ۲) مبلغ در ابتدای فرم ═══════════════
print("\n[۲] عدم نمایش مبلغ در ابتدای فرم")
SENT.clear()
M.handle_callback(cb(U1, f"ffopen_{fid}"))
_land = alltext()
# ⚡ پیش‌فرض: هیچ اشاره‌ای به هزینه نمی‌شود (درخواست کاربر)
check("هیچ اشاره‌ای به هزینه نیست", "هزینه" not in _land, _land[-90:])
check("عدد مبلغ نیست", "20,000" not in _land and "200,000" not in _land)
check("عدد آیتم هم نیست", "50,000" not in _land)
# ادمین می‌تواند نمایش مبلغ را روشن کند
M.handle_callback(cb(S, f"fbtog_show_price_upfront_{fid}"))
check("ادمین نمایش مبلغ را روشن کرد",
      F.get_form(fid)["show_price_upfront"] == 1)
SENT.clear()
M.handle_callback(cb(U1, f"ffopen_{fid}"))
check("حالا مبلغ نمایش داده می‌شود", "هزینه" in alltext())
M.handle_callback(cb(S, f"fbtog_show_price_upfront_{fid}"))
check("دوباره خاموش شد", F.get_form(fid)["show_price_upfront"] == 0)


# ═══════════════ پر کردن فرم ═══════════════
print("\n[۵.۱] رفتار حالت «فقط دکمه اشتراک شماره»")
M.handle_callback(cb(U1, f"ffstart_{fid}"))
rid = auth.get_state_data(U1).get("rid")
fl = F.get_fields(fid)
M.handle_callback(cb(U1, f"ffq_{fl[0]['id']}"))
M.process_message(msg(U1, "علی محمدی"))
SENT.clear()
M.process_message(msg(U1, "09121112233"))
check("تایپ شماره در حالت contact رد شد", "ارسال شماره‌ام" in last(), last()[:60])
M.process_message({**msg(U1, ""), "contact": {"phone_number": "09121112233"}})
check("دکمه اشتراک شماره پذیرفته شد",
      FL._answer_map(rid).get(fl[1]["id"]) == "09121112233")

M.process_message(msg(U1, "0084575948"))
M.handle_callback(cb(U1, f"ffo_1_{fl[3]['id']}"))

print("\n[۳.۲] انتخاب آیتم و ظرفیت")
SENT.clear()
M.handle_callback(cb(U1, f"ffi_1_{course['id']}"))
check("آیتم انتخاب شد", FL._answer_map(rid).get(course["id"]) == "دوره مقدماتی")
check("قیمت به ریال اعلام شد", "500,000" in alltext(), alltext()[-70:])

trm = next(f for f in fl if F.field_meta(f["field_type"]).get("has_terms"))
check("متن قوانین پیش‌فرض دارد", bool(trm.get("terms_text")))
M.handle_callback(cb(U1, f"ffy_{trm['id']}"))


# ═══════════════ ۴) صورتحساب ═══════════════
print("\n[۴] صورتحساب نهایی — ریال")
SENT.clear()
M.handle_callback(cb(U1, f"ffsubmit_{rid}"))
inv = alltext()
check("صورتحساب نمایش داده شد", "صورتحساب" in inv)
check("جمع کل به ریال", "700,000" in inv, inv[:150])
# فاز۱۷-د: همه‌جا ریال — همان عددی که ادمین وارد کرد
check("🔴 عدد ۱۰ برابر کوچک‌تر نیست", "70,000 " not in inv, inv[:150])
check("صورتحساب نمایش داده شد", "مبلغ" in inv or "پرداخت" in inv, inv[:100])
r = database.db_execute("SELECT * FROM form_responses WHERE id=?", (rid,), fetch="one")
check("مبلغ در دیتابیس ریال است", r["amount"] == 700000, str(r["amount"]))
check("وضعیت در انتظار پرداخت", r["status"] == "pending_payment", r["status"])

print("\n[۱.۱] پروفایل قبل و بعد از تأیید")
before = database.db_execute("SELECT last_name, national_id, gender FROM users "
                             "WHERE bale_user_id=?", (U1,), fetch="one")
check("قبل تأیید: نام خانوادگی خالی", not before.get("last_name"))
check("قبل تأیید: کد ملی خالی", not before.get("national_id"))

SENT.clear()
M.handle_callback(cb(S, f"fbrok_{rid}"))
after = database.db_execute(
    "SELECT first_name,last_name,national_id,mobile,gender,"
    "complete_profile_percent FROM users WHERE bale_user_id=?", (U1,), fetch="one")
check("نام خانوادگی پر شد", after.get("last_name") == "محمدی", str(after))
check("کد ملی پر شد", after.get("national_id") == "0084575948")
# موبایل هنگام ثبت‌نام از قبل پر بوده → بازنویسی نمی‌شود (رفتار درست)
check("موبایل قبلی حفظ شد", bool(after.get("mobile")), str(after.get("mobile")))
check("جنسیت پر شد", after.get("gender") == "مرد")
check("درصد پروفایل به‌روز شد", int(after.get("complete_profile_percent") or 0) > 0)
check("کاربر مطلع شد", any(s["p"].get("cid") == U1 for s in SENT))
check("پیام شامل تعداد فیلد", "پروفایل" in alltext())

print("\n[۱.۲] فیلدهای پرشده بازنویسی نمی‌شوند")
database.db_execute("UPDATE users SET last_name='قبلی' WHERE bale_user_id=?", (U2,))
r2 = database.db_execute("""INSERT INTO form_responses (form_id,bale_user_id,status)
    VALUES (?,?,'completed')""", (fid, U2))
database.db_execute("""INSERT INTO form_answers
    (response_id,form_id,field_id,field_type,value_text)
    VALUES (?,?,?,'full_name','سارا جدید')""", (r2, fid, fl[0]["id"]))
F.sync_profile_from_response(r2)
check("نام خانوادگی قبلی حفظ شد",
      database.db_execute("SELECT last_name FROM users WHERE bale_user_id=?",
                          (U2,), fetch="one")["last_name"] == "قبلی")

check("نگاشت پروفایل تعریف شده", len(F.FIELD_TO_PROFILE) >= 15)
_bad = [k for k in F.FIELD_TO_PROFILE if k not in F.FIELD_TYPES]
check("همه کلیدهای نگاشت معتبرند", not _bad, str(_bad))
check("sync با پاسخ ناموجود کرش نمی‌کند", F.sync_profile_from_response(999999) == 0)


# ═══════════════ ۶) نحوه نمایش ═══════════════
print("\n[۶] انتخاب نحوه نمایش سوالات")
check("۲ حالت", len(F.DISPLAY_MODES) == 2)
check("نام «همه سوالات یکجا»",
      "یکجا" in F.DISPLAY_MODES["user_choice"]["name"])
check("نام «دونه‌دونه»", "دونه" in F.DISPLAY_MODES["one_by_one"]["name"])
SENT.clear()
M.handle_callback(cb(S, f"fbdisp_{fid}"))
check("صفحه انتخاب", "نحوه نمایش" in last())
check("هر دو گزینه", sum(1 for d in cbdata() if d.startswith("fbdisps_")) == 2)
M.handle_callback(cb(S, f"fbdisps_one_by_one_{fid}"))
check("حالت دونه‌دونه ذخیره شد",
      F.get_form(fid)["display_mode"] == "one_by_one")
M.handle_callback(cb(S, f"fbdisps_user_choice_{fid}"))
check("حالت یکجا ذخیره شد", F.get_form(fid)["display_mode"] == "user_choice")


# ═══════════════ ۷) مناسبت‌ها ═══════════════
print("\n[۷] تبریک تولد و مناسبت‌ها")
jy, jm, jd = OC.today_jalali()
check("تاریخ شمسی معتبر", 1300 < jy < 1500 and 1 <= jm <= 12 and 1 <= jd <= 31,
      f"{jy}/{jm}/{jd}")

for tbl in ("occasions", "greeting_log"):
    check(f"جدول {tbl}", bool(database.db_execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (tbl,), fetch="one")))
check("مناسبت‌های پیش‌فرض ثبت شد",
      database.db_scalar("SELECT COUNT(*) FROM occasions") >= 14)
for k in ("girl_day", "boy_day", "men_day", "women_day", "nowruz", "yalda"):
    check(f"مناسبت {k}", bool(database.db_execute(
        "SELECT id FROM occasions WHERE key=?", (k,), fetch="one")))

# کاربران تست
for uid, nm, g in ((950001, "سارا", "زن"), (950002, "رضا", "مرد"),
                   (950003, "مینا", "زن")):
    auth.create_auth_user({"id": uid, "first_name": nm}, f"0913{uid}", "phone")
    database.db_execute("UPDATE users SET gender=? WHERE bale_user_id=?", (g, uid))
database.db_execute("UPDATE users SET birth_date=? WHERE bale_user_id IN (?,?)",
                    (f"1375/{jm:02d}/{jd:02d}", 950001, 950002))

print("\n[۷.۱] تبریک تولد")
SENT.clear()
n, names = OC.check_birthdays()
check("۲ تولد امروز", n == 2, f"{n} {names}")
check("پیام تولد ارسال شد", any("تولدت مبارک" in t for t in texts()))
# 🔴 نظام سخت‌گیرانه: امتیاز تولد ۱۵ شد (قبلاً ۵۰)
check("امتیاز تولد داده شد",
      database.db_scalar("SELECT total_points FROM users WHERE bale_user_id=?",
                         (950001,)) == 15,
      str(database.db_scalar("SELECT total_points FROM users "
                             "WHERE bale_user_id=?", (950001,))))
n2, _ = OC.check_birthdays()
check("ارسال تکراری جلوگیری شد", n2 == 0)
check("لاگ ثبت شد",
      database.db_scalar("SELECT COUNT(*) FROM greeting_log WHERE kind='birthday'") == 2)

print("\n[۷.۲] فیلتر جنسیت")
database.db_execute("UPDATE occasions SET jmonth=?, jday=?, is_active=1 "
                    "WHERE key='girl_day'", (jm, jd))
SENT.clear()
n, fired = OC.check_occasions()
got = {s["p"].get("cid") for s in SENT if s["m"] == "sendMessage"}
check("روز دختر ارسال شد", n == 2, f"{n} {fired}")
check("خانم‌ها گرفتند", 950001 in got and 950003 in got)
check("🔴 آقا نگرفت", 950002 not in got)
n3, _ = OC.check_occasions()
check("مناسبت تکراری نمی‌رود", n3 == 0)

print("\n[۷.۳] پنل ادمین مناسبت‌ها")
SENT.clear()
M.handle_callback(cb(S, "oc_panel"))
check("پنل باز شد", "مناسبت" in last())
check("دکمه لیست", "oc_list" in cbdata())
SENT.clear()
M.handle_callback(cb(S, "oc_list"))
check("لیست مناسبت‌ها", any(d.startswith("oc_v_") for d in cbdata()))

gd = database.db_execute("SELECT id FROM occasions WHERE key='girl_day'",
                         fetch="one")["id"]
SENT.clear()
M.handle_callback(cb(S, f"oc_v_{gd}"))
check("جزئیات مناسبت", "روز دختر" in last())
M.handle_callback(cb(S, f"oc_pts_{gd}"))
M.process_message(msg(S, "77"))
check("امتیاز تغییر کرد",
      database.db_execute("SELECT points FROM occasions WHERE id=?", (gd,),
                          fetch="one")["points"] == 77)
M.handle_callback(cb(S, f"oc_date_{gd}"))
M.process_message(msg(S, "7/10"))
_oc = database.db_execute("SELECT jmonth,jday FROM occasions WHERE id=?", (gd,),
                          fetch="one")
check("تاریخ تغییر کرد", _oc["jmonth"] == 7 and _oc["jday"] == 10)
M.handle_callback(cb(S, f"oc_date_{gd}"))
M.process_message(msg(S, "غلط"))
check("تاریخ نامعتبر رد شد", "نامعتبر" in last())
M.process_message(msg(S, "7/10"))

M.handle_callback(cb(S, f"oc_gens_male_{gd}"))
check("جنسیت تغییر کرد",
      database.db_execute("SELECT gender FROM occasions WHERE id=?", (gd,),
                          fetch="one")["gender"] == "male")
M.handle_callback(cb(S, f"oc_gens_female_{gd}"))

M.handle_callback(cb(S, f"oc_tg_{gd}"))
check("غیرفعال شد",
      database.db_execute("SELECT is_active FROM occasions WHERE id=?", (gd,),
                          fetch="one")["is_active"] == 0)
M.handle_callback(cb(S, f"oc_tg_{gd}"))

SENT.clear()
M.handle_callback(cb(S, f"oc_del_{gd}"))
check("مناسبت پیش‌فرض حذف نمی‌شود", "حذف نمی‌شود" in alltext())

print("\n[۷.۴] مناسبت سفارشی")
M.handle_callback(cb(S, "oc_add"))
M.process_message(msg(S, "روز کتاب | 8/24 | 20"))
newoc = database.db_execute("SELECT * FROM occasions WHERE name='روز کتاب'",
                            fetch="one")
check("مناسبت سفارشی ساخته شد", bool(newoc))
check("تاریخ درست", newoc and newoc["jmonth"] == 8 and newoc["jday"] == 24)
check("امتیاز درست", newoc and newoc["points"] == 20)
M.handle_callback(cb(S, "oc_add"))
M.process_message(msg(S, "بدون تاریخ"))
check("مناسبت بدون تاریخ رد شد", "نامعتبر" in last())
M.process_message(msg(S, "🔙 بازگشت"))
M.handle_callback(cb(S, f"oc_dely_{newoc['id']}"))
check("مناسبت سفارشی حذف شد",
      not database.db_execute("SELECT id FROM occasions WHERE id=?",
                              (newoc["id"],), fetch="one"))

print("\n[۷.۵] تنظیمات و متن‌ها")
M.handle_callback(cb(S, "oc_bpoints"))
M.process_message(msg(S, "99"))
check("امتیاز تولد تغییر کرد",
      database.get_setting("oc_birthday_points") == "99")
SENT.clear()
M.handle_callback(cb(S, "oc_texts"))
check("لیست متن‌ها", any(d.startswith("octx_") for d in cbdata()))
M.handle_callback(cb(S, "octx_birthday"))
check("ویرایش متن شروع شد", auth.get_state_name(S) == OC.STATE_OC_EDIT)
M.process_message(msg(S, "🎂 تولدت مبارک {name}! هدیه: {points}"))
check("متن ذخیره شد",
      "هدیه" in database.get_setting("oc_txt_birthday"))
M.handle_callback(cb(S, "octx_birthday"))
M.process_message(msg(S, "-"))
check("بازگردانی پیش‌فرض",
      "آرزو می‌کنیم" in database.get_setting("oc_txt_birthday"))

# ⚡ متن جدید از {dear} استفاده می‌کند (اسم کوچک + عزیز/خانم)
check("render متغیر جایگزین می‌کند",
      "علی عزیز" in OC.render("oc_txt_birthday", dear="علی عزیز", points=10))
check("متن تبریک شیرین است",
      "🎈" in OC.render("oc_txt_birthday", dear="علی عزیز", points=10))
check("render بدون متغیر کرش نمی‌کند",
      isinstance(OC.render("oc_txt_birthday"), str))
check("render کلید ناشناس", isinstance(OC.render("nope", x=1), str))

M.handle_callback(cb(S, "oc_tog_birthday"))
check("تبریک تولد خاموش شد",
      database.get_setting("oc_birthday_enabled") == "0")
n4, _ = OC.check_birthdays()
check("وقتی خاموش است ارسال نمی‌شود", n4 == 0)
M.handle_callback(cb(S, "oc_tog_birthday"))

SENT.clear()
M.handle_callback(cb(S, "oc_history"))
check("تاریخچه", "تاریخچه" in last())
SENT.clear()
M.handle_callback(cb(S, f"oc_test_{gd}"))
check("تست ارسال به ادمین", "پیش‌نمایش" in alltext())

print("\n[۷.۶] اجرای روزانه")
database.set_setting("oc_last_run", "", "t", "occasions")
b, o = OC.run_daily()
check("run_daily اجرا شد", isinstance(b, int) and isinstance(o, int))
b2, o2 = OC.run_daily()
check("بار دوم اجرا نمی‌شود", b2 == 0 and o2 == 0)
b3, o3 = OC.run_daily(force=True)
check("force دوباره اجرا می‌کند", isinstance(b3, int))


# ═══════════════ دسترسی و ورودی خراب ═══════════════
print("\n[۸] دسترسی و مقاومت")
for d in ("oc_panel", "oc_list", "oc_add", "oc_run", "oc_history",
          "oc_texts", "oc_bpoints"):
    SENT.clear()
    M.handle_callback(cb(U3, d))
    check(f"🔒 کاربر عادی: {d}", "دسترسی ندارید" in last(), last()[:40])

bad = ["oc_v_", "oc_v_999999", "oc_tg_abc", "oc_del_999999", "oc_pts_",
       "oc_date_x", "oc_gens_zz_1", "oc_gen_999", "oc_test_999999",
       "octx_nothing", "oc_pg_x", "fbpvs_bad_1", "fbpv_999999",
       "fbtog_needs_approval_999999", "fbtog_fill_profile_abc"]
crashed = []
for d in bad:
    try:
        M.handle_callback(cb(S, d))
    except Exception as e:
        crashed.append(f"{d}: {type(e).__name__} {e}")
check("هیچ ورودی خرابی کرش نمی‌کند", not crashed, str(crashed[:2]))

check("کاربر بدون تاریخ تولد مشکلی نمی‌سازد",
      isinstance(OC.check_birthdays()[0], int))
database.db_execute("UPDATE users SET birth_date='خراب' WHERE bale_user_id=?",
                    (950003,))
check("تاریخ تولد خراب کرش نمی‌کند",
      isinstance(OC.check_birthdays()[0], int))


# ═══════════════ یکپارچگی ═══════════════
print("\n[۹] یکپارچگی")
dup = database.db_scalar("""SELECT COUNT(*) FROM (SELECT bale_user_id,kind,ref_key,
    jyear FROM greeting_log GROUP BY bale_user_id,kind,ref_key,jyear
    HAVING COUNT(*)>1)""")
check("لاگ تبریک تکراری نیست", dup == 0, str(dup))
neg = database.db_scalar("SELECT COUNT(*) FROM users WHERE total_points<0")
check("امتیاز منفی نیست", neg == 0)
badp = database.db_scalar("SELECT COUNT(*) FROM forms WHERE price<0")
check("قیمت منفی نیست", badp == 0)
badm = database.db_scalar("""SELECT COUNT(*) FROM forms
    WHERE phone_verify_mode NOT IN ('contact','otp','both')""")
check("حالت تأیید شماره معتبر", badm == 0)

print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\n❌ تست‌های ناموفق:")
    for f_ in FAILED:
        print(f"   • {f_}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۱۰ پاس شدند!")
