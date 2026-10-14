"""
تست فاز ۱۱-ب — تکمیل رویداد و مناسبت‌ها

هفت درخواست کاربر:
  ۱) تبریک شیرین و مودبانه با «اسم کوچک + عزیز/خانم»
  ۲) امتیاز شرطی (مثل «اولین کارگاه → ۱۰۰ امتیاز»)
  ۳) یادآوری رویداد با تنظیمات کامل
  ۴) نظرسنجی پیشرفته
  ۵) ساخت فرم ثبت‌نام برای رویداد
  ۶) کد تخفیف
  ۷) دعوت اجباری با تنظیمات پیشرفته
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora11b_")
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
    SENT.append({"m": m, "p": p or {}})
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

import config  # noqa: E402
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


def msg(uid, t):
    return {"message_id": 1, "from": {"id": uid, "first_name": "ت"},
            "chat": {"id": uid, "type": "private"}, "text": t}


def cb(uid, d):
    return {"id": "c", "from": {"id": uid, "first_name": "ت"}, "data": d,
            "message": {"message_id": 1, "chat": {"id": uid, "type": "private"}}}


S = 100000001
UM, UF, UX = 771001, 771002, 771003   # مرد، زن، بدون جنسیت

print("=" * 62)
print("🧪 تست فاز ۱۱-ب")
print("=" * 62)

database.init_db()
EV.init_event_tables()
AT.init_attendance_tables()
PAY.init_payment_tables()
F.init_form_tables()
OC.init_occasion_tables()

auth.create_auth_user({"id": S, "first_name": "مدیر"}, "09120000000", "phone")
auth.ensure_super_admin(S)
for u, nm, g in ((UM, "علی محمدی", "مرد"), (UF, "سارا رضایی", "زن"),
                 (UX, "کامران", "")):
    auth.create_auth_user({"id": u, "first_name": nm}, f"0912{u}", "phone")
    database.db_execute("UPDATE users SET gender=?, profile_status='approved' "
                        "WHERE bale_user_id=?", (g, u))
database.db_execute("INSERT INTO bank_cards (owner_id,bank_name,card_number,"
                    "card_holder_name,is_active) VALUES (?,?,?,?,1)",
                    (S, "ملی", "6037991234567890", "مدیر"))


# ═══════ ۱) تبریک مودبانه ═══════
print("\n[۱] خطاب مودبانه با اسم کوچک")
um = database.db_execute("SELECT * FROM users WHERE bale_user_id=?", (UM,), fetch="one")
uf = database.db_execute("SELECT * FROM users WHERE bale_user_id=?", (UF,), fetch="one")
ux = database.db_execute("SELECT * FROM users WHERE bale_user_id=?", (UX,), fetch="one")

check("مرد → «علی عزیز»", OC.polite_name(um) == "علی عزیز", OC.polite_name(um))
check("زن → «سارا خانم»", OC.polite_name(uf) == "سارا خانم", OC.polite_name(uf))
check("بدون جنسیت → «کامران عزیز»", OC.polite_name(ux) == "کامران عزیز",
      OC.polite_name(ux))
check("فقط اسم کوچک (نه فامیل)", "محمدی" not in OC.polite_name(um))
check("بی‌نام → «دوست عزیز»", OC.polite_name({}) == "دوست عزیز")
check("نام خالی → «دوست عزیز»", OC.polite_name({"first_name": "  "}) == "دوست عزیز")

_b = OC.render("oc_txt_birthday", dear="علی عزیز", points=50)
check("تبریک تولد شامل خطاب", "علی عزیز" in _b)
check("تبریک تولد شیرین است", "🎂" in _b and "🎈" in _b)
check("تبریک تولد مودبانه است", "مهر و احترام" in _b or "💚" in _b)
check("تبریک امتیاز را می‌گوید", "50" in _b)
_o = OC.render("oc_txt_occasion", dear="سارا خانم", occasion="روز دختر",
               icon="🎀", points=30, custom="")
check("مناسبت شامل خطاب", "سارا خانم" in _o)
check("مناسبت مودبانه", "آرزوی بهترین‌ها" in _o)
check("۴ پیام تولد متنوع", len(OC.BIRTHDAY_WISHES) >= 4)

# ارسال واقعی
jy, jm, jd = OC.today_jalali()
database.db_execute("UPDATE users SET birth_date=? WHERE bale_user_id IN (?,?)",
                    (f"1375/{jm:02d}/{jd:02d}", UM, UF))
SENT.clear()
n, _ = OC.check_birthdays()
check("۲ تبریک ارسال شد", n == 2, str(n))
_got = {s["p"].get("cid"): s["p"].get("text") for s in SENT
        if s["m"] == "sendMessage"}
check("آقا «عزیز» گرفت", "علی عزیز" in (_got.get(UM) or ""))
check("خانم «خانم» گرفت", "سارا خانم" in (_got.get(UF) or ""))


# ═══════ ۲) امتیاز شرطی ═══════
print("\n[۲] امتیاز شرطی")
check("جدول point_rules", bool(database.db_execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='point_rules'",
    fetch="one")))
check("۶ قانون پیش‌فرض",
      database.db_scalar("SELECT COUNT(*) FROM point_rules") >= 6)
check("۸ نوع شرط", len(OC.TRIGGERS) == 8, str(len(OC.TRIGGERS)))
check("قانون «اولین کارگاه» هست", bool(database.db_execute(
    "SELECT id FROM point_rules WHERE key='first_workshop'", fetch="one")))

_bad = [k for k in OC.TRIGGERS if not OC.TRIGGERS[k].get("name")]
check("همه شرط‌ها نام دارند", not _bad, str(_bad))

# شبیه‌سازی حضور در کارگاه
eid = database.db_execute("""INSERT INTO events (title,event_type,status,privacy,
    created_by,has_ticket) VALUES ('کارگاه فن بیان','workshop','published',
    'public',?,1)""", (S,))
database.db_execute("""INSERT INTO event_registrations
    (event_id,bale_user_id,status,attended) VALUES (?,?,'attended',1)""", (eid, UX))

before = database.db_scalar("SELECT total_points FROM users WHERE bale_user_id=?",
                            (UX,))
SENT.clear()
nf, pts = OC.check_point_rules(UX, "workshop_attend")
check("قانون اجرا شد", nf == 1, f"{nf} rules")
# 🔴 نظام سخت‌گیرانه: اولین کارگاه = ۲۰ امتیاز (قبلاً ۱۰۰ بود)
check("۲۰ امتیاز داده شد", pts == 20, str(pts))
after = database.db_scalar("SELECT total_points FROM users WHERE bale_user_id=?",
                           (UX,))
check("امتیاز کاربر افزایش یافت", after == (before or 0) + 20,
      f"{before}->{after}")
check("پیام تبریک رفت", "آفرین" in alltext())
check("پیام شامل خطاب مودبانه", "کامران عزیز" in alltext())
check("پیام شامل مجموع امتیاز", "مجموع امتیاز" in alltext())

nf2, _ = OC.check_point_rules(UX, "workshop_attend")
check("یک‌بار مصرف رعایت شد", nf2 == 0)

# شرط برآورده‌نشده
check("پیشرفت دعوت صفر است", OC._rule_progress(UM, "invite_friend") == 0)
nf3, _ = OC.check_point_rules(UM, "invite_friend")
check("بدون برآورده شدن شرط امتیاز نمی‌دهد", nf3 == 0)

# حد نصاب چندتایی
for i in range(5):
    database.db_execute("""INSERT INTO event_registrations
        (event_id,bale_user_id,status,attended) VALUES (?,?,'attended',1)""",
        (database.db_execute("INSERT INTO events (title,event_type,status) "
                             "VALUES (?,'meeting','published')", (f"ج{i}",)), UF))
check("پیشرفت حضور محاسبه شد", OC._rule_progress(UF, "event_attend") == 5)
SENT.clear()
nf4, pts4 = OC.check_point_rules(UF, "event_attend")
# 🔴 سخت‌گیرانه: ۵ حضور = ۳۰ امتیاز
check("قانون «۵ حضور» فعال شد", nf4 >= 1 and pts4 >= 30, f"{nf4}/{pts4}")

# پنل ادمین
SENT.clear()
M.handle_callback(cb(S, "pr_list"))
check("پنل امتیاز شرطی", "امتیازهای شرطی" in last())
check("دکمه قانون جدید", "pr_add" in cbdata())
rid = database.db_execute("SELECT id FROM point_rules WHERE key='first_workshop'",
                          fetch="one")["id"]
SENT.clear()
M.handle_callback(cb(S, f"pr_v_{rid}"))
check("جزئیات قانون", "اولین کارگاه" in last())
M.handle_callback(cb(S, f"prn_points_{rid}"))
M.process_message(msg(S, "150"))
check("امتیاز تغییر کرد", database.db_execute(
    "SELECT points FROM point_rules WHERE id=?", (rid,), fetch="one")["points"] == 150)
M.handle_callback(cb(S, f"prtg_event_attend_{rid}"))
check("شرط تغییر کرد", database.db_execute(
    "SELECT trigger FROM point_rules WHERE id=?", (rid,),
    fetch="one")["trigger"] == "event_attend")
M.handle_callback(cb(S, f"prtg_workshop_attend_{rid}"))
M.handle_callback(cb(S, f"pr_tg_{rid}"))
check("غیرفعال شد", database.db_execute(
    "SELECT is_active FROM point_rules WHERE id=?", (rid,),
    fetch="one")["is_active"] == 0)
M.handle_callback(cb(S, f"pr_tg_{rid}"))

M.handle_callback(cb(S, "pr_add"))
M.process_message(msg(S, "قهرمان فرم | form_submit | 3 | 80"))
_new = database.db_execute("SELECT * FROM point_rules WHERE title='قهرمان فرم'",
                           fetch="one")
check("قانون سفارشی ساخته شد", bool(_new))
check("شرط درست", _new and _new["trigger"] == "form_submit")
check("حد نصاب درست", _new and _new["threshold"] == 3)
check("امتیاز درست", _new and _new["points"] == 80)
M.handle_callback(cb(S, "pr_add"))
M.process_message(msg(S, "بد | trigger_غلط | 1 | 10"))
check("شرط نامعتبر رد شد", "نامعتبر" in last())
M.process_message(msg(S, "🔙 بازگشت"))

M.handle_callback(cb(S, "pr_toggle_sys"))
check("سیستم خاموش شد", database.get_setting("rules_enabled") == "0")
nf5, _ = OC.check_point_rules(UM, "event_register")
check("وقتی خاموش است اجرا نمی‌شود", nf5 == 0)
M.handle_callback(cb(S, "pr_toggle_sys"))

M.handle_callback(cb(S, f"pr_dely_{_new['id']}"))
check("قانون حذف شد", not database.db_execute(
    "SELECT id FROM point_rules WHERE id=?", (_new["id"],), fetch="one"))


# ═══════ ۳) یادآوری ═══════
print("\n[۳] یادآوری رویداد")
SENT.clear()
M.handle_callback(cb(S, f"evrem_{eid}"))
check("صفحه یادآوری", "یادآوری خودکار" in last())
check("۷ زمان مختلف", len(EV.REMINDER_SLOTS) == 7)
for _lbl in ("۳ روز قبل", "۱ روز قبل", "۲ ساعت قبل", "۳۰ دقیقه قبل",
             "لحظه شروع", "خوش‌آمد", "تشکر"):
    check(f"گزینه {_lbl}", _lbl in last())
# دقیقاً ۷ اسلات (evtog_reminder_enabled جدا حساب نشود)
_slots = {c for c, _ in EV.REMINDER_SLOTS}
_emitted = {d.rsplit("_", 1)[0].replace("evtog_", "")
            for d in cbdata() if d.startswith("evtog_rem_")}
check("همه ۷ گزینه دکمه دارند", _emitted == _slots,
      str(sorted(_emitted ^ _slots)))

for col in ("rem_3d", "rem_30m", "rem_start"):
    b = EV.get_event(eid).get(col)
    M.handle_callback(cb(S, f"evtog_{col}_{eid}"))
    check(f"تاگل {col}", EV.get_event(eid).get(col) != b)
M.handle_callback(cb(S, f"evtxt_rem_message_{eid}"))
M.process_message(msg(S, "فردا منتظرتان هستیم!"))
check("پیام یادآوری ثبت شد",
      "منتظرتان" in (EV.get_event(eid).get("rem_message") or ""))
check("پیش‌فرض ۱ روز قبل روشن است",
      EV.get_event(eid).get("rem_1d") == 1)


# ═══════ ۴) نظرسنجی ═══════
print("\n[۴] نظرسنجی پیشرفته")
SENT.clear()
M.handle_callback(cb(S, f"evsurv_{eid}"))
check("صفحه نظرسنجی", "نظرسنجی بعد از رویداد" in last())
check("۴ زمان ارسال", len(EV.SURVEY_TIMES) == 4)
M.handle_callback(cb(S, f"evtog_survey_enabled_{eid}"))
check("نظرسنجی فعال شد", EV.get_event(eid)["survey_enabled"] == 1)
M.handle_callback(cb(S, f"evsts_next_day_{eid}"))
check("زمان ارسال تغییر کرد",
      EV.get_event(eid)["survey_send_time"] == "next_day")
M.handle_callback(cb(S, f"evtog_survey_reminder_{eid}"))
check("یادآوری نظرسنجی", EV.get_event(eid)["survey_reminder"] == 1)
M.handle_callback(cb(S, f"evtog_survey_anonymous_{eid}"))
check("نظرسنجی ناشناس", EV.get_event(eid)["survey_anonymous"] == 1)
M.handle_callback(cb(S, f"evnum_survey_points_{eid}"))
M.process_message(msg(S, "25"))
check("امتیاز نظرسنجی", EV.get_event(eid)["survey_points"] == 25)

SENT.clear()
M.handle_callback(cb(S, f"evsfnew_{eid}"))
_ev = EV.get_event(eid)
check("فرم نظرسنجی ساخته شد", bool(_ev.get("survey_form_id")))
_sf = database.db_execute("SELECT * FROM forms WHERE id=?",
                          (_ev["survey_form_id"],), fetch="one")
check("نوع فرم survey است", _sf and _sf["form_type"] == "survey")
check("فرم ناشناس است", _sf and _sf["anonymous"] == 1)
check("سوال آماده دارد",
      database.db_scalar("SELECT COUNT(*) FROM form_fields WHERE form_id=?",
                         (_ev["survey_form_id"],)) > 0)
check("به رویداد وصل است", _sf and _sf.get("event_id") == eid)
M.handle_callback(cb(S, f"evsfs_0_{eid}"))
check("اتصال حذف شد", not EV.get_event(eid).get("survey_form_id"))
M.handle_callback(cb(S, f"evsfs_{_sf['id']}_{eid}"))
check("دوباره وصل شد", EV.get_event(eid).get("survey_form_id") == _sf["id"])


# ═══════ ۵) فرم ثبت‌نام رویداد ═══════
print("\n[۵] فرم ثبت‌نام رویداد")
SENT.clear()
M.handle_callback(cb(S, f"evform_{eid}"))
check("صفحه فرم ثبت‌نام", "فرم ثبت‌نام رویداد" in last())
check("دکمه ساخت فرم", any(d.startswith("evformnew_") for d in cbdata()))
M.handle_callback(cb(S, f"evformnew_{eid}"))
_ev = EV.get_event(eid)
check("فرم ثبت‌نام ساخته شد", bool(_ev.get("registration_form_id")))
_rf = database.db_execute("SELECT * FROM forms WHERE id=?",
                          (_ev["registration_form_id"],), fetch="one")
check("نوع registration", _rf and _rf["form_type"] == "registration")
check("سوالات آماده", database.db_scalar(
    "SELECT COUNT(*) FROM form_fields WHERE form_id=?", (_rf["id"],)) >= 5)
check("عنوان شامل نام رویداد", _rf and "فن بیان" in _rf["title"])
M.handle_callback(cb(S, f"evforms_0_{eid}"))
check("اتصال فرم حذف شد",
      not EV.get_event(eid).get("registration_form_id"))
M.handle_callback(cb(S, f"evforms_{_rf['id']}_{eid}"))
check("فرم دوباره وصل شد",
      EV.get_event(eid).get("registration_form_id") == _rf["id"])


# ═══════ ۶) کد تخفیف ═══════
print("\n[۶] کد تخفیف")
peid = database.db_execute("""INSERT INTO events (title,event_type,status,privacy,
    created_by,is_paid,price,payment_method,has_ticket) VALUES
    ('همایش','conference','published','public',?,1,1000000,'card',1)""", (S,))
SENT.clear()
M.handle_callback(cb(S, f"evdisc_{peid}"))
check("صفحه کدهای تخفیف", "کدهای تخفیف" in last())
M.handle_callback(cb(S, f"evdadd_{peid}"))
M.process_message(msg(S, "NOWRUZ | 20% | 50"))
_d = database.db_execute("SELECT * FROM event_discount_codes WHERE code='NOWRUZ'",
                         fetch="one")
check("کد درصدی ساخته شد", bool(_d))
check("نوع percent", _d and _d["discount_type"] == "percent")
check("مقدار ۲۰", _d and _d["amount"] == 20)
check("سقف ۵۰", _d and _d["max_uses"] == 50)

M.handle_callback(cb(S, f"evdadd_{peid}"))
M.process_message(msg(S, "OFF5 | 50000 | 10"))
_d2 = database.db_execute("SELECT * FROM event_discount_codes WHERE code='OFF5'",
                          fetch="one")
check("کد مبلغی ساخته شد", bool(_d2))
check("نوع amount", _d2 and _d2["discount_type"] == "amount")
check("مبلغ تخفیف عیناً ریال ذخیره شد", _d2 and _d2["amount"] == 50000,
      str(_d2 and _d2["amount"]))

M.handle_callback(cb(S, f"evdadd_{peid}"))
M.process_message(msg(S, "NOWRUZ | 10% | 5"))
check("کد تکراری رد شد", "قبلاً استفاده شده" in last())
M.process_message(msg(S, "ab | 10%"))
check("کد کوتاه رد شد", "۳ کاراکتر" in last())
M.process_message(msg(S, "🔙 بازگشت"))

# اعمال تخفیف
ok_, final, msg_, did = EV.apply_discount("NOWRUZ", peid, UM, 1000000)
check("تخفیف درصدی اعمال شد", ok_ and final == 800000, f"{final}")
ok2, final2, _, _ = EV.apply_discount("OFF5", peid, UM, 1000000)
check("تخفیف مبلغی اعمال شد", ok2 and final2 == 950000, f"{final2}")
ok3, _, m3, _ = EV.apply_discount("NOTEXIST", peid, UM, 1000000)
check("کد نامعتبر رد شد", not ok3 and "نامعتبر" in m3)
ok4, f4, _, _ = EV.apply_discount("NOWRUZ", peid, UM, 100)
check("تخفیف بیش از مبلغ نمی‌شود", ok4 and f4 >= 0, str(f4))

EV.record_discount_use(did, peid, 1, UM, 1000000, 200000, 800000)
_d = database.db_execute("SELECT * FROM event_discount_codes WHERE code='NOWRUZ'",
                         fetch="one")
check("شمارنده استفاده", _d["current_uses"] == 1)
check("مجموع تخفیف ثبت شد", _d["total_discount"] == 200000)
check("درآمد ثبت شد", _d["revenue_from_code"] == 800000)
ok5, _, m5, _ = EV.apply_discount("NOWRUZ", peid, UM, 1000000)
check("سقف هر کاربر رعایت شد", not ok5 and "قبلاً" in m5, m5)

database.db_execute("UPDATE event_discount_codes SET max_uses=1 WHERE code='OFF5'")
database.db_execute("UPDATE event_discount_codes SET current_uses=1 WHERE code='OFF5'")
ok6, _, m6, _ = EV.apply_discount("OFF5", peid, UF, 1000000)
check("سقف کل رعایت شد", not ok6 and "سقف" in m6, m6)

SENT.clear()
M.handle_callback(cb(S, f"evdrep_{peid}"))
check("گزارش کد تخفیف", "گزارش کدهای تخفیف" in last())
M.handle_callback(cb(S, f"evdtg_{_d['id']}_{peid}"))
check("کد غیرفعال شد", database.db_execute(
    "SELECT is_active FROM event_discount_codes WHERE id=?", (_d["id"],),
    fetch="one")["is_active"] == 0)
ok7, _, _, _ = EV.apply_discount("NOWRUZ", peid, UF, 1000000)
check("کد غیرفعال کار نمی‌کند", not ok7)
M.handle_callback(cb(S, f"evdtg_{_d['id']}_{peid}"))

# جریان واقعی کاربر
SENT.clear()
M.handle_callback(cb(UF, f"ureg_{peid}"))
check("از کاربر کد تخفیف پرسیده شد", "کد تخفیف" in alltext())
SENT.clear()
M.process_message(msg(UF, "NOWRUZ"))
check("تخفیف در جریان واقعی اعمال شد", "تخفیف" in alltext())
_r = database.db_execute("""SELECT amount_paid FROM event_registrations
    WHERE event_id=? AND bale_user_id=?""", (peid, UF), fetch="one")
check("مبلغ نهایی ذخیره شد (ریال)", _r and _r["amount_paid"] == 800000,
      str(_r and _r["amount_paid"]))
check("نمایش به ریال", "800,000" in alltext() or "800٬000" in alltext(),
      alltext()[-120:])

SENT.clear()
M.handle_callback(cb(UM, f"ureg_{peid}"))
M.process_message(msg(UM, "⏭️ رد کردن"))
check("رد کردن کد تخفیف کار می‌کند", "کارت" in alltext() or "پرداخت" in alltext())


# ═══════ ۷) دعوت اجباری پیشرفته ═══════
print("\n[۷] دعوت اجباری پیشرفته")
SENT.clear()
M.handle_callback(cb(S, f"evinv_{eid}"))
check("صفحه دعوت", "دعوت اجباری" in last())
check("شرایط پیشرفته نمایش", "شرایط پیشرفته" in last())
check("گزینه دعوت تأییدشده", "تأییدشده" in last())
check("گزینه معافیت VIP", "VIP" in last())
check("محدوده زمانی", "روز اخیر" in last())
check("پاداش دعوت", "پاداش هر دعوت" in last())

M.handle_callback(cb(S, f"evtog_require_invites_{eid}"))
M.handle_callback(cb(S, f"evnum_invites_needed_{eid}"))
M.process_message(msg(S, "2"))
check("تعداد دعوت", EV.get_event(eid)["invites_needed"] == 2)

# دعوت‌شده‌های تأییدشده و ناقص
for inv, pct in ((880001, 60), (880002, 60), (880003, 5)):
    auth.create_auth_user({"id": inv, "first_name": "د"}, f"0917{inv}", "phone")
    database.db_execute("""UPDATE users SET referred_by=?, is_authenticated=1,
        complete_profile_percent=? WHERE bale_user_id=?""", (UM, pct, inv))

_ev = EV.get_event(eid)
check("حالت سخت‌گیرانه: ۲ نفر", EV.count_confirmed_invites(UM, _ev) == 2)
M.handle_callback(cb(S, f"evtog_invite_strict_{eid}"))
check("حالت آزاد: ۳ نفر",
      EV.count_confirmed_invites(UM, EV.get_event(eid)) == 3)
M.handle_callback(cb(S, f"evtog_invite_strict_{eid}"))

# معافیت VIP
database.db_execute("UPDATE users SET is_vip=1 WHERE bale_user_id=?", (UF,))
ok_v, m_v, _ = EV.check_eligibility(UF, EV.get_event(eid))
check("🔴 VIP بدون معافیت رد می‌شود", not ok_v)
M.handle_callback(cb(S, f"evtog_invite_exempt_vip_{eid}"))
ok_v2, _, _ = EV.check_eligibility(UF, EV.get_event(eid))
check("✅ با معافیت VIP قبول می‌شود", ok_v2)
M.handle_callback(cb(S, f"evtog_invite_exempt_vip_{eid}"))

# محدوده زمانی
M.handle_callback(cb(S, f"evnum_invite_recent_days_{eid}"))
M.process_message(msg(S, "30"))
check("محدوده زمانی ثبت شد",
      EV.get_event(eid)["invite_recent_days"] == 30)
check("دعوت‌های اخیر شمرده می‌شوند",
      EV.count_confirmed_invites(UM, EV.get_event(eid)) == 2)
database.db_execute("""UPDATE users SET created_at=datetime('now','-100 days')
    WHERE bale_user_id IN (880001,880002)""")
check("دعوت قدیمی حساب نمی‌شود",
      EV.count_confirmed_invites(UM, EV.get_event(eid)) == 0)
M.handle_callback(cb(S, f"evnum_invite_recent_days_{eid}"))
M.process_message(msg(S, "0"))
check("بدون محدودیت زمانی دوباره ۲",
      EV.count_confirmed_invites(UM, EV.get_event(eid)) == 2)

M.handle_callback(cb(S, f"evnum_invite_reward_{eid}"))
M.process_message(msg(S, "25"))
check("پاداش دعوت ثبت شد", EV.get_event(eid)["invite_reward"] == 25)
check("👑 ادمین معاف است", EV.check_eligibility(S, EV.get_event(eid))[0])


# ═══════ ۸) دسترسی و ورودی خراب ═══════
print("\n[۸] دسترسی و مقاومت")
for d in ("pr_list", "pr_add", f"evsurv_{eid}", f"evdisc_{eid}",
          f"evform_{eid}", f"evrem_{eid}"):
    SENT.clear()
    M.handle_callback(cb(UX, d))
    check(f"🔒 کاربر عادی: {d[:14]}", "دسترسی ندارید" in last(), last()[:40])

bad = ["pr_v_", "pr_v_abc", "pr_v_999999", "pr_tg_x", "pr_del_999999",
       "prtg_bad_1", "prn_evil_1", "prt_evil_1", "pr_once_abc",
       "evsurv_abc", "evsfs_x_1", "evsts_bad_1", "evform_999999",
       "evforms_x_1", "evdisc_abc", "evdadd_999999", "evdv_x_1",
       "evdtg_abc_1", "evddel_x_1", "evdrep_999999", "evsfnew_999999",
       "evformnew_999999", "evtog_rem_evil_1"]
crashed = []
for d in bad:
    try:
        M.handle_callback(cb(S, d))
    except Exception as e:
        crashed.append(f"{d}: {type(e).__name__} {e}")
check("هیچ ورودی خرابی کرش نمی‌کند", not crashed, str(crashed[:2]))

_badt = [k for k in EV.EV_TOGGLES if k not in
         open(ROOT / "events.py", encoding="utf-8").read()]
check("کلیدهای تاگل معتبرند", not _badt, str(_badt))
check("allowlist شامل ستون خطرناک نیست",
      not any(k in ("users", "is_admin") for k in EV.EV_TOGGLES))


# ═══════ ۹) یکپارچگی ═══════
print("\n[۹] یکپارچگی")
check("کد تخفیف یتیم نیست", database.db_scalar(
    """SELECT COUNT(*) FROM event_discount_codes d WHERE d.event_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM events e WHERE e.id=d.event_id)""") == 0)
check("لاگ تخفیف یتیم نیست", database.db_scalar(
    """SELECT COUNT(*) FROM event_discount_usage u WHERE NOT EXISTS
       (SELECT 1 FROM event_discount_codes d WHERE d.id=u.discount_id)""") == 0)
check("کد تخفیف تکراری نیست", database.db_scalar(
    """SELECT COUNT(*) FROM (SELECT code FROM event_discount_codes
       GROUP BY code HAVING COUNT(*)>1)""") == 0)
check("امتیاز منفی نیست",
      database.db_scalar("SELECT COUNT(*) FROM users WHERE total_points<0") == 0)
check("قانون امتیاز شرط معتبر دارد", database.db_scalar(
    f"""SELECT COUNT(*) FROM point_rules WHERE trigger NOT IN
        ({','.join('?' * len(OC.TRIGGERS))})""", tuple(OC.TRIGGERS)) == 0)
check("لاگ قانون تکراری نیست", database.db_scalar(
    """SELECT COUNT(*) FROM (SELECT bale_user_id,ref_key FROM greeting_log
       WHERE kind='rule' GROUP BY bale_user_id,ref_key HAVING COUNT(*)>1)""") == 0)

print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\n❌ تست‌های ناموفق:")
    for f_ in FAILED:
        print(f"   • {f_}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۱۱-ب پاس شدند!")
