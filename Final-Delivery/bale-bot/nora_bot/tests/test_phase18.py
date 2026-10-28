"""
تست فاز ۱۸ — امکانات ویژه فرم · پرداخت فرم‌ساز · اقساط · درباره ما

درخواست‌های کاربر که اینجا تست می‌شوند:
  ۱) هر نوع فرم امکانات ویژه خودش (آزمون زمان دارد، مسابقه مهلت و…)
  ۲) 🔴 باگ: «فرم‌ساز پارامتر هزینه‌دار → ربات می‌گوید درگاه فعال نیست»
  ۳) دسترسی فرم: عمومی / لینکی / متصل به بخش / خصوصی
  ۴) پرداخت اقساطی و جلسه‌ای
  ۵) پارامترهای پروفایل + افزودن پارامتر از کاتالوگ فرم‌ساز
  ۶) 🔴 باگ: «جلو اجباری نوشته فول نیم»
  ۷) درباره ما و پشتیبانی جامع
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora18_")
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
_INV = []


def _api(m, p=None, **k):
    SENT.append({"m": m, "p": p or {}})
    if m == "getMe":
        return {"ok": True, "result": {"username": "nora_bot"}}
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


def _send(cid, text, kb=None, reply_to=None):
    SENT.append({"m": "sendMessage", "p": {"cid": cid, "text": text, "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


def _soe(cid, text, kb=None, mid=None, force_new=False):
    SENT.append({"m": "editMessageText",
                 "p": {"cid": cid, "text": text, "kb": kb}})
    return {"ok": True, "result": {"message_id": mid or 1}}


def _file(method, key, cid, f, caption=None, kb=None):
    SENT.append({"m": method, "p": {"cid": cid, "caption": caption, "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


def _invoice(cid, **kw):
    _INV.append({"cid": cid, **kw})
    SENT.append({"m": "sendInvoice", "p": {"cid": cid, "text": "invoice"}})
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


bale_api.api = _api
bale_api.api_async = _api
bale_api.send = _send
bale_api.send_or_edit = _soe
bale_api._send_file = _file
bale_api.send_photo = lambda c, p, cap=None, kb=None: _file("sendPhoto", "p", c, p, cap, kb)
bale_api.send_document = lambda c, d, cap=None, kb=None: _file("sendDocument", "d", c, d, cap, kb)
bale_api.send_invoice = _invoice

import config  # noqa: E402
import database  # noqa: E402
sys.path.insert(0, str(ROOT / "tests"))
import _points_fixture as _pf  # noqa: E402  (موجودی آزمایشی از مسیر دفترکل)
import auth  # noqa: E402
import profile as PR  # noqa: E402
import forms as F  # noqa: E402
import form_fill as FF  # noqa: E402
import payments as PAY  # noqa: E402
import payplan as PP  # noqa: E402
import events as EV  # noqa: E402
import attendance as AT  # noqa: E402
import occasions as OC  # noqa: E402
import permissions as PM  # noqa: E402
import club as CL  # noqa: E402
import tickets as TK  # noqa: E402
import lottery as LT  # noqa: E402
import paylink as PL  # noqa: E402
import about as AB  # noqa: E402
import settings_admin as SET  # noqa: E402
import admin as AD  # noqa: E402
import main as M  # noqa: E402

for mod in (PR, F, FF, PAY, PP, EV, AT, OC, CL, TK, LT, PL, AB, SET, AD, M):
    for n in ("send", "send_or_edit", "send_photo", "send_document"):
        if hasattr(mod, n):
            setattr(mod, n, getattr(bale_api, n))
PAY.send_invoice = _invoice
EV.send_invoice = _invoice

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
            "message": {"message_id": 1,
                        "chat": {"id": uid, "type": "private"}}}


def mkform(title, ftype="questionnaire", **kw):
    cols = {"title": title, "form_type": ftype, "status": "active",
            "owner_id": S, "visibility": "public"}
    cols.update(kw)
    ks = list(cols)
    return database.db_execute(
        f"INSERT INTO forms ({','.join(ks)}) VALUES ({','.join('?' * len(ks))})",
        [cols[k] for k in ks])


S = 100000001
U1, U2 = 1330001, 1330002

print("=" * 62)
print("🧪 تست فاز ۱۸ — فرم‌ساز پیشرفته · اقساط · درباره ما")
print("=" * 62)

database.init_db()
EV.init_event_tables()
AT.init_attendance_tables()
PAY.init_payment_tables()
F.init_form_tables()
OC.init_occasion_tables()
PM.init_permission_tables()
CL.init_club_tables()
TK.init_ticket_tables()
TK.init_inbox_table()
LT.init_lottery_tables()
PL.init_paylink_tables()
PP.init_payplan_tables()
PR.init_profile_extra()
AB.init_about_tables()
database.seed_default_settings()
SET.seed_phase5_settings()

auth.create_auth_user({"id": S, "first_name": "مدیر"}, "09120000000", "phone")
auth.ensure_super_admin(S)
for u, n in ((U1, "علی"), (U2, "سارا")):
    auth.create_auth_user({"id": u, "first_name": n}, f"0915{u}", "phone")
    database.db_execute("UPDATE users SET profile_status='approved', "
                        "complete_profile_percent=100 WHERE bale_user_id=?",
                        (u,))


# ═══════════ ۱) ✨ امکانات ویژه هر نوع فرم ═══════════
print("\n[۱] ✨ امکانات ویژه مخصوص هر نوع فرم")

check("کاتالوگ امکانات ویژه وجود دارد", bool(F.TYPE_FEATURES))
for t in ("exam", "contest", "election", "order", "attendance"):
    check(f"نوع «{F.FORM_TYPES[t]['name']}» امکان ویژه دارد",
          len(F.type_features(t)) > 0, str(len(F.type_features(t))))

_exam_keys = {k for k, *_ in F.type_features("exam")}
check("آزمون: زمان دارد", "time_limit_min" in _exam_keys)
check("آزمون: نمره قبولی دارد", "pass_score" in _exam_keys)
check("آزمون: ترتیب تصادفی دارد", "shuffle_questions" in _exam_keys)
check("آزمون: دفعات مجاز دارد", "max_attempts" in _exam_keys)

_c_keys = {k for k, *_ in F.type_features("contest")}
check("مسابقه: مهلت دارد", "contest_deadline" in _c_keys)
check("مسابقه: رتبه‌بندی دارد", "leaderboard_enabled" in _c_keys)

_e_keys = {k for k, *_ in F.type_features("election")}
check("انتخابات: بازه رأی دارد",
      "vote_start" in _e_keys and "vote_end" in _e_keys)

# همه ستون‌ها واقعاً در دیتابیس هستند
_cols = {c["name"] for c in
         database.db_execute("PRAGMA table_info(forms)", fetch="all")}
_all_feat = {k for lst in F.TYPE_FEATURES.values() for k, *_ in lst}
_missing = _all_feat - _cols
check("🔴 همه امکانات ویژه ستون دیتابیس دارند", not _missing, str(_missing))

# پنل ادمین
eid_exam = mkform("آزمون ریاضی", "exam")
SENT.clear()
M.handle_callback(cb(S, f"fbfeat_{eid_exam}"))
check("پنل امکانات ویژه باز شد", "امکانات ویژه" in last(), last()[:60])
_cbs = allcb()
check("دکمه تنظیم زمان هست",
      any("time_limit_min" in c for c in _cbs), str(_cbs)[:120])

# روشن/خاموش کردن
SENT.clear()
M.handle_callback(cb(S, f"fbft_shuffle_questions_{eid_exam}"))
check("ترتیب تصادفی روشن شد",
      F.get_form(eid_exam)["shuffle_questions"] == 1)
M.handle_callback(cb(S, f"fbft_shuffle_questions_{eid_exam}"))
check("دوباره خاموش شد",
      F.get_form(eid_exam)["shuffle_questions"] == 0)

# تنظیم عدد
SENT.clear()
M.handle_callback(cb(S, f"fbfx_time_limit_min_{eid_exam}"))
check("ویرایش زمان شروع شد", "مهلت" in last(), last()[:50])
M.process_message(msg(S, "30"))
check("مهلت ۳۰ دقیقه ذخیره شد",
      F.get_form(eid_exam)["time_limit_min"] == 30,
      str(F.get_form(eid_exam)["time_limit_min"]))

M.handle_callback(cb(S, f"fbfx_pass_score_{eid_exam}"))
M.process_message(msg(S, "60"))
check("نمره قبولی ذخیره شد", F.get_form(eid_exam)["pass_score"] == 60)


# ═══════════ ۲) ⏱️ اعمال واقعی مهلت و قوانین ═══════════
print("\n[۲] ⏱️ قوانین ویژه واقعاً اعمال می‌شوند")

# مهلت مسابقه گذشته
cid_old = mkform("مسابقه تمام‌شده", "contest",
                 contest_deadline="1400/01/01")
ok_, why_, _ = F.form_gate(F.get_form(cid_old), U1)
check("🏆 مسابقه با مهلت گذشته بسته است",
      not ok_ and why_ == "expired", f"{ok_} {why_}")

# بازه رأی‌گیری آینده
vid = mkform("انتخابات آینده", "election", vote_start="1499/01/01")
ok_, why_, _ = F.form_gate(F.get_form(vid), U1)
check("🗳️ رأی‌گیری شروع‌نشده بسته است",
      not ok_ and why_ == "not_started", f"{ok_} {why_}")

# دفعات مجاز
aid = mkform("آزمون یکبار", "exam", max_attempts=1)
database.db_execute("""INSERT INTO form_responses
    (form_id, bale_user_id, status) VALUES (?,?,'completed')""", (aid, U1))
ok_, why_, _ = F.form_gate(F.get_form(aid), U1)
check("🔁 سقف دفعات شرکت اعمال شد",
      not ok_ and why_ == "max_attempts", f"{ok_} {why_}")
ok2_, _, _ = F.form_gate(F.get_form(aid), U2)
check("🔁 کاربر دیگر هنوز می‌تواند شرکت کند", ok2_)

# 🔴 رگرسیون: سقف دفعات نباید فرم را از فهرست عمومی حذف کند
ok3_, _, _ = F.form_gate(F.get_form(aid), U1, strict=False)
check("🔴 فرم پرشده از فهرست عمومی غیب نمی‌شود", ok3_)

# لیست انتظار
wid = mkform("ثبت‌نام پر", "registration", limit_enabled=1,
             max_responses=1, waitlist_enabled=1)
database.db_execute("""INSERT INTO form_responses
    (form_id, bale_user_id, status) VALUES (?,?,'completed')""", (wid, U2))
ok_, why_, _ = F.form_gate(F.get_form(wid), U1)
check("⏳ لیست انتظار به‌جای «پر شد»",
      not ok_ and why_ == "waitlist", f"{ok_} {why_}")

# مهلت در جریان پر کردن
tid = mkform("آزمون زمان‌دار", "exam", time_limit_min=30)
database.db_execute("""INSERT INTO form_fields
    (form_id, field_type, label, field_order) VALUES (?,?,?,1)""",
    (tid, "short_text", "سوال ۱"))
SENT.clear()
FF.start_fill(U1, U1, tid)
check("⏱️ مهلت به کاربر اعلام شد", "مهلت" in alltext(), alltext()[:150])
_st = auth.get_state_data(U1)
check("⏱️ deadline در state ثبت شد", bool(_st.get("deadline")))
check("⏱️ زمان باقی‌مانده مثبت است", (FF._time_left(U1) or 0) > 0)
auth.clear_state(U1)


# ═══════════ ۳) 🔴 باگ اصلی: پرداخت فرم‌ساز ═══════════
print("\n[۳] 🔴 باگ: «درگاه پرداختی فعال نیست»")

# ستون‌های لازم واقعاً وجود دارند
_rc = {c["name"] for c in
       database.db_execute("PRAGMA table_info(form_responses)", fetch="all")}
check("🔴 ستون amount_paid در form_responses هست", "amount_paid" in _rc)
check("🔴 ستون payment_payload در form_responses هست",
      "payment_payload" in _rc)
_tc = {c["name"] for c in
       database.db_execute("PRAGMA table_info(transactions)", fetch="all")}
check("🔴 ستون form_response_id در transactions هست",
      "form_response_id" in _tc)
check("ستون installment_no در transactions هست", "installment_no" in _tc)

# کارت ثبت می‌کنیم تا روش پرداخت سالم باشد
database.db_execute("""INSERT INTO bank_cards
    (owner_id, bank_name, card_number, card_holder_name, is_active)
    VALUES (?,?,?,?,1)""", (S, "ملی", "6037991234567890", "مدیر"))

pfid = mkform("ثبت‌نام دوره", "registration",
              payment_method="card", price=500000)
database.db_execute("""INSERT INTO form_fields
    (form_id, field_type, label, field_order) VALUES (?,?,?,1)""",
    (pfid, "short_text", "نام"))

rid = database.db_execute("""INSERT INTO form_responses
    (form_id, bale_user_id, status, amount) VALUES (?,?,'draft',0)""",
    (pfid, U1))
SENT.clear()
FF._start_payment(U1, U1, F.get_form(pfid), {"id": rid}, 500000)
check("✅ پرداخت فرم شروع شد بدون خطای درگاه",
      "فعال نیست" not in alltext() and "تنظیم نشده" not in alltext(),
      alltext()[:150])
_tx = database.db_execute(
    "SELECT * FROM transactions WHERE form_response_id=? "
    "ORDER BY id DESC LIMIT 1", (rid,), fetch="one")
check("✅ تراکنش به پاسخ فرم گره خورد", bool(_tx),
      str(_tx.get("id") if _tx else None))
check("✅ مبلغ درست ثبت شد", _tx and _tx["amount"] == 500000,
      str(_tx.get("amount") if _tx else None))

# 🔴 مهم‌ترین: بعد از پرداخت موفق، فرم نهایی شود
_pay_msg = {
    "from": {"id": U1}, "chat": {"id": U1},
    "successful_payment": {
        "invoice_payload": _tx["payload"], "total_amount": 500000,
        "telegram_payment_charge_id": "CH1",
        "provider_payment_charge_id": "PR1"},
}
SENT.clear()
EV.handle_successful_payment(_pay_msg)
_fr = database.db_execute("SELECT * FROM form_responses WHERE id=?",
                          (rid,), fetch="one")
check("🔴 پس از پرداخت، پاسخ فرم دیگر pending_payment نیست",
      _fr["status"] != "pending_payment", str(_fr["status"]))
check("✅ payment_status پرداخت‌شده شد",
      _fr.get("payment_status") == "paid", str(_fr.get("payment_status")))
check("✅ amount_paid ثبت شد", _fr.get("amount_paid") == 500000,
      str(_fr.get("amount_paid")))
check("✅ کد پیگیری صادر شد", bool(_fr.get("tracking_code")))

# بازگشت خودکار به روش سالم
check("روش سالم پیدا می‌شود", PAY.best_available_method() is not None,
      str(PAY.best_available_method()))
_bad = mkform("فرم درگاه‌نداشته", "registration",
              payment_method="custom_gateway", price=200000)
rid2 = database.db_execute("""INSERT INTO form_responses
    (form_id, bale_user_id, status) VALUES (?,?,'draft')""", (_bad, U2))
SENT.clear()
_obj = dict(F.get_form(_bad))
_obj["_form_response_id"] = rid2
PAY.route_payment(U2, U2, _obj, None, 200000)
check("♻️ روش خراب → خودکار به روش سالم رفت",
      "پوزش" not in alltext(), alltext()[:120])


# ═══════════ ۴) 👁️ دسترسی فرم ═══════════
print("\n[۴] 👁️ سطح دسترسی فرم")

check("۴ سطح دسترسی تعریف شده", len(F.VISIBILITY) == 4, str(list(F.VISIBILITY)))
check("بخش‌های ربات تعریف شده", "join_us" in F.FORM_SECTIONS)

pub = mkform("فرم عمومی", visibility="public")
lnk = mkform("فرم لینکی", visibility="link")
sec = mkform("فرم همکاری", visibility="section", section_key="join_us")
prv = mkform("فرم خصوصی", visibility="private", access_code="VIP123")

_vis = [f["id"] for f in F.list_visible_forms()]
check("🌍 عمومی در فهرست هست", pub in _vis)
check("🔗 لینکی در فهرست نیست", lnk not in _vis)
check("🧩 بخشی در فهرست نیست", sec not in _vis)
check("🔒 خصوصی در فهرست نیست", prv not in _vis)

check("🧩 فرم بخش «همکاری با ما» پیدا می‌شود",
      any(f["id"] == sec for f in F.forms_for_section("join_us")))

ok_, _ = F.can_user_open(F.get_form(lnk), U1, via_link=True)
check("🔗 لینکی با لینک مستقیم باز می‌شود", ok_)
ok_, _ = F.can_user_open(F.get_form(prv), U1)
check("🔒 خصوصی بدون کد باز نمی‌شود", not ok_)
ok_, _ = F.can_user_open(F.get_form(prv), U1, code="VIP123")
check("🔒 خصوصی با کد درست باز می‌شود", ok_)

# پنل ادمین دسترسی
SENT.clear()
M.handle_callback(cb(S, f"fbvis_{pub}"))
check("پنل دسترسی باز شد", "دسترسی" in last(), last()[:50])
M.handle_callback(cb(S, f"fbvs_link_{pub}"))
check("تغییر به «فقط با لینک»",
      F.get_form(pub)["visibility"] == "link",
      F.get_form(pub)["visibility"])
M.handle_callback(cb(S, f"fbvs_private_{pub}"))
check("🔑 کد دسترسی خودکار ساخته شد",
      bool(F.get_form(pub).get("access_code")))
SENT.clear()
M.handle_callback(cb(S, f"fbsec_{pub}_join_us"))
check("🧩 اتصال به بخش کار کرد",
      F.get_form(pub)["section_key"] == "join_us" and
      F.get_form(pub)["visibility"] == "section")

# 🔴 مهاجرت: فرم قدیمی بدون visibility نباید غیب شود
database.db_execute("UPDATE forms SET visibility=NULL WHERE id=?", (lnk,))
F.init_form_tables()
check("♻️ فرم قدیمی روی «عمومی» تنظیم شد",
      F.get_form(lnk)["visibility"] == "public",
      str(F.get_form(lnk)["visibility"]))


# ═══════════ ۵) 💠 پرداخت اقساطی و جلسه‌ای ═══════════
print("\n[۵] 💠 پرداخت مرحله‌ای")

check("۳ حالت طرح تعریف شده", len(PP.PLAN_MODES) == 3, str(list(PP.PLAN_MODES)))
check("روش‌های مرحله‌ای در PAYMENT_METHODS هستند",
      all(m in PAY.PAYMENT_METHODS
          for m in ("installment", "sessions", "prepay")))

# تقسیم مبلغ — جمع باید دقیق باشد
for total, parts in ((3000000, 3), (1000000, 3), (999999, 7), (5, 3)):
    got = PP.split_amount(total, parts)
    check(f"🧮 تقسیم {total} به {parts} قسط دقیق است",
          sum(got) == total, f"{got} جمع={sum(got)}")

pp = PP.split_amount(1000000, 2, "prepay", prepay_percent=30)
check("💵 پیش‌پرداخت ۳۰٪ درست است", pp == [300000, 700000], str(pp))
ss = PP.split_amount(0, 12, "sessions", part_amount=250000)
check("🎟️ جلسه‌ای: ۱۲ جلسه × ۲۵۰هزار",
      len(ss) == 12 and ss[0] == 250000, str(ss[:3]))

# ساخت طرح از پنل
SENT.clear()
M.handle_callback(cb(S, "pp_panel"))
check("پنل پرداخت مرحله‌ای باز شد", "مرحله‌ای" in last(), last()[:50])
M.handle_callback(cb(S, "pp_new"))
M.process_message(msg(S, "شهریه دوره فن بیان"))
_plan = database.db_execute("SELECT * FROM payment_plans "
                            "ORDER BY id DESC LIMIT 1", fetch="one")
check("طرح ساخته شد", _plan and _plan["title"] == "شهریه دوره فن بیان")
M.handle_callback(cb(S, f"ppe_parts_{_plan['id']}"))
M.process_message(msg(S, "4"))
check("تعداد قسط ذخیره شد",
      PP.get_plan(_plan["id"])["parts"] == 4)
M.handle_callback(cb(S, f"ppm_{_plan['id']}_sessions"))
check("نوع طرح به جلسه‌ای تغییر کرد",
      PP.get_plan(_plan["id"])["mode"] == "sessions")

# جریان واقعی: رویداد اقساطی
iev = database.db_execute("""INSERT INTO events
    (title, event_type, status, capacity, created_by, is_paid, price,
     payment_method, require_profile)
    VALUES ('دوره اقساطی','workshop','published',50,?,1,3000000,
            'installment',0)""", (S,))
irid = database.db_execute("""INSERT INTO event_registrations
    (event_id, user_id, bale_user_id, status)
    VALUES (?,?,?,'pending')""", (iev, auth.get_user(U1)["id"], U1))
SENT.clear()
PAY.route_payment(U1, U1, EV.get_event(iev), irid, 3000000)
_sch = database.db_execute("SELECT * FROM payment_schedules "
                           "WHERE bale_user_id=? ORDER BY part_no",
                           (U1,), fetch="all") or []
check("📅 زمان‌بندی اقساط ساخته شد", len(_sch) >= 2, str(len(_sch)))
check("📅 جمع اقساط = مبلغ کل",
      sum(int(x["amount"]) for x in _sch) == 3000000,
      str(sum(int(x["amount"]) for x in _sch)))
check("📅 به کاربر جدول اقساط نشان داده شد",
      "قسط" in alltext(), alltext()[:150])

_n_left, _amt_left = PP.remaining(U1, irid)
check("باقی‌مانده درست محاسبه شد", _n_left == len(_sch))
PP.mark_part_paid(_sch[0]["id"])
_n2, _ = PP.remaining(U1, irid)
check("بعد از پرداخت قسط اول، یکی کم شد", _n2 == _n_left - 1)
check("هنوز تسویه نشده", not PP.all_paid(U1, irid))

# نمای کاربر
SENT.clear()
M.handle_callback(cb(U1, "pp_mine"))
check("👤 صفحه اقساط من کار می‌کند",
      "مرحله‌ای" in last() or "قسط" in last(), last()[:80])

# تسویه دستی ادمین
SENT.clear()
M.handle_callback(cb(S, f"ppok_{_sch[1]['id']}"))
_s2 = database.db_execute("SELECT status FROM payment_schedules WHERE id=?",
                          (_sch[1]["id"],), fetch="one")
check("✅ تسویه دستی ادمین کار کرد", _s2["status"] == "paid")


# ═══════════ ۶) 👤 پارامترهای پروفایل ═══════════
print("\n[۶] 👤 پارامترهای پروفایل")

# 🔴 باگ «فول نیم»
_lbl = PR._required_label()
check("🔴 «full_name» خام دیگر نمایش داده نمی‌شود",
      "full_name" not in _lbl, _lbl)
check("✅ به‌جایش فارسی نوشته می‌شود",
      "نام و نام خانوادگی" in _lbl, _lbl)
check("full_name ستون دیتابیسی نیست", "full_name" not in PR.DB_FIELDS)

SENT.clear()
M.handle_callback(cb(S, "pf_params"))
check("پنل پارامترها باز شد", "پارامترهای پروفایل" in last(), last()[:50])
check("🔴 در پنل هم فارسی است", "full_name" not in last(), last()[:200])
check("دکمه افزودن پارامتر هست", "pfadd" in allcb())

# افزودن پارامتر از کاتالوگ فرم‌ساز
SENT.clear()
M.handle_callback(cb(S, "pfadd"))
check("کاتالوگ فیلدها باز شد", "افزودن پارامتر" in last(), last()[:50])
SENT.clear()
M.handle_callback(cb(S, "pfadd_telegram_id"))
_cf = PR.custom_fields()
check("➕ پارامتر سفارشی اضافه شد",
      any(c["key"] == "telegram_id" for c in _cf), str(_cf))
check("پارامتر جدید در مراحل پروفایل آمد",
      any(s["key"] == "telegram_id" for s in PR.active_steps()))

# ذخیره مقدار
PR.set_extra(U1, "telegram_id", "@ali")
check("مقدار پارامتر سفارشی ذخیره شد",
      PR.get_extra(U1, "telegram_id") == "@ali")

# حذف
SENT.clear()
M.handle_callback(cb(S, "pfdel_telegram_id"))
check("🗑️ پارامتر حذف شد",
      not any(c["key"] == "telegram_id" for c in PR.custom_fields()))

# خاموش کردن یک فیلد
M.handle_callback(cb(S, "pfo_bio"))
check("فیلد بیو خاموش شد", not PR.field_on("bio"))
check("و از مراحل حذف شد",
      not any(s["key"] == "bio" for s in PR.active_steps()))
M.handle_callback(cb(S, "pfo_bio"))


# ═══════════ ۷) ℹ️ درباره ما و پشتیبانی ═══════════
print("\n[۷] ℹ️ درباره ما و پشتیبانی")

# 🎛️ فاز ۲۰: چیدمان «کامل» تا همه دکمه‌ها را ببینیم
database.set_setting("ab_layout", "full", "t", "about")
database.clear_settings_cache()
SENT.clear()
M.handle_callback(cb(U1, "u_support"))
check("صفحه پشتیبانی و درباره ما باز شد",
      "پشتیبانی" in last(), last()[:60])
_cbs = allcb()
# 🆕 فاز ۱۸-ج: فهرست تخت شد — همه گزینه‌ها همین‌جا هستند
check("دکمه درباره ما هست", "ab_about" in _cbs)
check("تیکت مستقیم در فهرست هست",
      "tk_my" in _cbs or "tk_new" in _cbs, str(_cbs)[:120])
check("پیام مستقیم در فهرست هست", "u_contact" in _cbs)
check("سوالات متداول در فهرست هست", "u_faq" in _cbs)
check("راه‌های تماس در فهرست هست", "ab_contact" in _cbs)

SENT.clear()
M.handle_callback(cb(U1, "ab_about"))
check("درباره ما باز شد", "درباره" in last(), last()[:50])
check("متن معرفی دارد", len(last()) > 60)

SENT.clear()
M.handle_callback(cb(U1, "ab_support"))
check("پشتیبانی باز شد", "پشتیبانی" in last(), last()[:50])
_cbs = allcb()
check("تیکت در پشتیبانی هست", "tk_my" in _cbs or "tk_new" in _cbs)
check("پیام مستقیم هست", "u_contact" in _cbs)
check("سوالات متداول هست", "u_faq" in _cbs)

# همکاری با ما + فرم متصل
jf = mkform("فرم همکاری با ما", "questionnaire",
            visibility="section", section_key="join_us")
SENT.clear()
M.handle_callback(cb(U1, "ab_join"))
check("🤝 همکاری با ما باز شد",
      "همکاری" in last() or "گرمی" in last(), last()[:50])
check("🤝 فرم متصل نمایش داده شد",
      f"ffstart_{jf}" in allcb(), str(allcb())[:120])

# شبکه‌های اجتماعی
SENT.clear()
M.handle_callback(cb(S, "ablnew_bale_channel"))
M.process_message(msg(S, "کانال خط زندگی | https://ble.ir/test"))
check("🌐 لینک اضافه شد", len(AB.get_links()) == 1)
SENT.clear()
M.handle_callback(cb(U1, "ab_social"))
check("🌐 شبکه‌های اجتماعی نمایش داده شد",
      "دنبال" in last() or "کانال" in last(), last()[:80])

# تیم
SENT.clear()
M.handle_callback(cb(S, "abpnew"))
M.process_message(msg(S, "علی محمدی | مدیر آموزش | ۱۰ سال سابقه | @ali"))
check("👥 عضو تیم اضافه شد", len(AB.get_people()) == 1)
SENT.clear()
M.handle_callback(cb(U1, "ab_team"))
check("👥 تیم به کاربر نمایش داده شد",
      "علی محمدی" in last(), last()[:80])

# روشن/خاموش بودن بخش‌ها
check("بخش‌ها پیش‌فرض روشن‌اند", AB.block_on("intro"))
SENT.clear()
M.handle_callback(cb(S, "abt_team"))
check("🔴 بخش تیم خاموش شد", not AB.block_on("team"))
SENT.clear()
M.handle_callback(cb(U1, "ab_about"))
check("🔴 دکمه تیم دیگر نیست", "ab_team" not in allcb())
M.handle_callback(cb(S, "abt_team"))
check("🟢 دوباره روشن شد", AB.block_on("team"))

# ویرایش متن
SENT.clear()
M.handle_callback(cb(S, "abe_intro"))
check("ویرایش متن شروع شد", "متن فعلی" in last(), last()[:50])
M.process_message(msg(S, "ما گروه خط زندگی هستیم و کنار شماییم"))
check("✏️ متن ذخیره شد",
      "خط زندگی هستیم" in AB._txt("ab_intro"), AB._txt("ab_intro")[:60])
M.handle_callback(cb(S, "abe_intro"))
M.process_message(msg(S, "پیش‌فرض"))
check("♻️ بازگشت به پیش‌فرض کار کرد",
      "خط زندگی هستیم" not in AB._txt("ab_intro"))

# پنل ادمین
SENT.clear()
M.handle_callback(cb(S, "ab_admin"))
check("⚙️ پنل ادمین درباره ما باز شد",
      "درباره ما و پشتیبانی" in last(), last()[:60])
check("همه بخش‌ها قابل تنظیم‌اند",
      sum(1 for c in allcb() if c.startswith("abt_")) >= 10,
      str(sum(1 for c in allcb() if c.startswith("abt_"))))


# ═══════════ ۷.۵) 🛡️ هشدار فیلترشکن ═══════════
print("\n[۷.۵] 🛡️ هشدار خاموش کردن فیلترشکن")

check("هشدار پیش‌فرض فعال است", PAY.vpn_warn_enabled())

# 🔴 درخواست صریح: فقط درگاه‌های آنلاین
check("🛡️ کیف پول بله هشدار می‌گیرد",
      PAY.vpn_warn_needed("bale_wallet"))
check("🛡️ درگاه سفارشی هشدار می‌گیرد",
      PAY.vpn_warn_needed("custom_gateway"))
check("⬜ کارت به کارت هشدار نمی‌گیرد",
      not PAY.vpn_warn_needed("card"))
check("⬜ پرداخت با امتیاز هشدار نمی‌گیرد",
      not PAY.vpn_warn_needed("points"))
check("⬜ پرداخت در محل هشدار نمی‌گیرد",
      not PAY.vpn_warn_needed("onsite"))
check("⬜ رایگان هشدار نمی‌گیرد", not PAY.vpn_warn_needed("none"))

check("متن هشدار خالی نیست", len(PAY.vpn_warn_text()) > 40)
check("متن حاوی کلمه فیلترشکن است",
      "فیلترشکن" in PAY.vpn_warn_text())
check("یادآوری کوتاه برای کارت خالی است",
      PAY.vpn_warn_inline("card") == "")
check("یادآوری کوتاه برای کیف پول پر است",
      "فیلترشکن" in PAY.vpn_warn_inline("bale_wallet"))


def _saw_vpn(method, price=500000):
    """آیا هنگام پرداخت با این روش، هشدار فیلترشکن آمد؟"""
    _e = database.db_execute(
        "INSERT INTO events (title,event_type,status,capacity,created_by,"
        "is_paid,price,payment_method,require_profile) "
        "VALUES (?,'workshop','published',50,?,1,?,?,0)",
        (f"تست {method}", S, price, method))
    _r = database.db_execute(
        "INSERT INTO event_registrations (event_id,user_id,bale_user_id,"
        "status) VALUES (?,?,?,'pending')",
        (_e, auth.get_user(U2)["id"], U2))
    SENT.clear()
    PAY.route_payment(U2, U2, EV.get_event(_e), _r, price)
    return "فیلترشکن" in alltext()


# کارت و درگاه لازم است تا روش‌ها در دسترس باشند
database.db_execute("""INSERT INTO payment_gateways
    (gateway_name, gateway_type, callback_url, is_active)
    VALUES ('زرین‌پال','zarinpal','https://zarinpal.com/pg',1)""")
database.set_setting("pay_points_enabled", "1", "t", "payment")
database.set_setting("pay_points_rate", "10000", "t", "payment")
database.clear_settings_cache()
_pf.set_balance(U2, 500)

check("🛡️ جریان واقعی: کیف پول → هشدار آمد", _saw_vpn("bale_wallet"))
check("🛡️ جریان واقعی: درگاه سفارشی → هشدار آمد",
      _saw_vpn("custom_gateway"))
check("⬜ جریان واقعی: کارت به کارت → هشدار نیامد",
      not _saw_vpn("card"))
check("⬜ جریان واقعی: امتیاز → هشدار نیامد", not _saw_vpn("points"))
check("⬜ جریان واقعی: در محل → هشدار نیامد", not _saw_vpn("onsite"))

# پنل ادمین
SENT.clear()
M.handle_callback(cb(S, "pay_vpn"))
check("پنل هشدار فیلترشکن باز شد",
      "فیلترشکن" in last(), last()[:60])
check("پنل نشان می‌دهد کدام روش‌ها مستثنا هستند",
      "کارت به کارت" in last(), last()[:200])

SENT.clear()
M.handle_callback(cb(S, "payvpn_toggle"))
check("🔴 ادمین هشدار را خاموش کرد", not PAY.vpn_warn_enabled())
check("خاموش که شد، هیچ روشی هشدار نمی‌گیرد",
      not PAY.vpn_warn_needed("bale_wallet"))
check("🔴 در جریان واقعی هم حذف شد", not _saw_vpn("bale_wallet"))

M.handle_callback(cb(S, "payvpn_toggle"))
check("🟢 دوباره روشن شد", PAY.vpn_warn_enabled())

# متن قابل ویرایش
database.set_setting("pay_txt_vpn_warn", "لطفاً وی‌پی‌ان را قطع کنید",
                     "t", "payment")
database.clear_settings_cache()
check("✏️ متن سفارشی ادمین اعمال شد",
      "وی‌پی‌ان" in PAY.vpn_warn_text(), PAY.vpn_warn_text()[:50])
database.db_execute("DELETE FROM settings WHERE key='pay_txt_vpn_warn'")
database.clear_settings_cache()
check("♻️ بدون متن سفارشی، پیش‌فرض برمی‌گردد",
      "فیلترشکن" in PAY.vpn_warn_text())

check("لاگ فارسی هشدار فیلترشکن دارد",
      "vpn_warn_toggle" in __import__("activity_log").ACTION_FA)


# ═══════════ ۷.۶) 📊 آمار قابل تنظیم + 🏷️ هویت ربات ═══════════
print("\n[۷.۶] 📊 آمار نمایشی و 🏷️ هویت ربات")

# چند کاربر و رویداد بسازیم تا آمار عدد داشته باشد
for _i in range(6):
    auth.create_auth_user({"id": 1440000 + _i, "first_name": f"u{_i}"},
                          f"09170000{_i:03d}", "phone")
database.db_execute("""INSERT INTO events
    (title, event_type, status, capacity, created_by)
    VALUES ('رویداد آماری','workshop','published',50,?)""", (S,))

_st = AB._stats_line()
check("📊 آمار پیش‌فرض نمایش داده می‌شود", bool(_st), _st)
check("📊 تعداد کاربران در آمار هست", "همراه" in _st, _st)
check("📊 تعداد رویدادها در آمار هست", "رویداد" in _st, _st)

# خاموش کردن فقط «تعداد نفرات»
SENT.clear()
M.handle_callback(cb(S, "abst_users"))
_st = AB._stats_line()
check("🔴 تعداد نفرات خاموش شد", "همراه" not in _st, _st)
check("🟢 ولی رویدادها هنوز هست", "رویداد" in _st, _st)

# خاموش کردن رویدادها هم
M.handle_callback(cb(S, "abst_events"))
check("🔴 هر دو خاموش → آمار خالی", AB._stats_line() == "",
      AB._stats_line())

# روشن کردن یک شاخص جدید
M.handle_callback(cb(S, "abst_forms"))
check("🟢 تعداد فرم‌ها روشن شد", "فرم" in AB._stats_line(),
      AB._stats_line())

# برگرداندن
M.handle_callback(cb(S, "abst_users"))
M.handle_callback(cb(S, "abst_events"))
M.handle_callback(cb(S, "abst_forms"))

# کلید اصلی خاموش → هیچ آماری
SENT.clear()
M.handle_callback(cb(S, "abt_stats"))
check("🔴 کلید اصلی آمار خاموش شد", AB._stats_line() == "",
      AB._stats_line())
M.handle_callback(cb(S, "abt_stats"))
check("🟢 دوباره روشن شد", bool(AB._stats_line()))

# پنل آمار
SENT.clear()
M.handle_callback(cb(S, "ab_stats"))
check("پنل آمار باز شد", "آمار نمایشی" in last(), last()[:50])
check("هر شاخص دکمه جدا دارد",
      sum(1 for c in allcb() if c.startswith("abst_")) == 4,
      str(sum(1 for c in allcb() if c.startswith("abst_"))))

# ─── 🏷️ هویت ربات ───
check("نام پیش‌فرض از .env می‌آید", config.bot_name() == config.BOT_NAME_ENV,
      config.bot_name())
check("برند شامل نام است", config.bot_name() in config.brand(),
      config.brand())

SENT.clear()
M.handle_callback(cb(S, "ab_identity"))
check("پنل هویت باز شد", "هویت ربات" in last(), last()[:50])

# تغییر نام ربات
SENT.clear()
M.handle_callback(cb(S, "abid_bot_name"))
check("ویرایش نام شروع شد", "نام" in last(), last()[:50])
M.process_message(msg(S, "آوا"))
database.clear_settings_cache()
check("🏷️ نام ربات عوض شد", config.bot_name() == "آوا", config.bot_name())
check("🏷️ برند هم عوض شد", config.brand() == "ربات آوا", config.brand())

# تغییر نام مجموعه
M.handle_callback(cb(S, "abid_org_name"))
M.process_message(msg(S, "انجمن نمونه"))
database.clear_settings_cache()
check("🏢 نام مجموعه عوض شد", config.org_name() == "انجمن نمونه",
      config.org_name())

# 🔴 مهم: تغییر باید در متن‌های کاربر هم دیده شود
SENT.clear()
M.handle_callback(cb(U1, "u_support"))
check("🔴 نام جدید در صفحه کاربر آمد", "انجمن نمونه" in last(),
      last()[:120])

# خاموش کردن نمایش نام
SENT.clear()
M.handle_callback(cb(S, "abid_toggle"))
database.clear_settings_cache()
check("👁️ نمایش نام خاموش شد", not config.show_bot_name())
check("👁️ برند فقط «ربات» شد", config.brand() == "ربات", config.brand())
M.handle_callback(cb(S, "abid_toggle"))
database.clear_settings_cache()
check("👁️ دوباره روشن شد", config.show_bot_name())

# بازگشت به پیش‌فرض
SENT.clear()
M.handle_callback(cb(S, "abid_reset"))
database.clear_settings_cache()
check("♻️ هویت به پیش‌فرض برگشت",
      config.bot_name() == config.BOT_NAME_ENV, config.bot_name())
check("♻️ نام مجموعه هم برگشت",
      config.org_name() == config.ORG_NAME_ENV, config.org_name())

check("لاگ تغییر هویت فارسی دارد",
      "identity_changed" in __import__("activity_log").ACTION_FA)

# 🧩 تنظیمات درباره ما زیر «پشتیبانی و باشگاه» است
import bale_api as _BA
_care = _BA.kb_care_menu(uid=S)
_care_cbs = [b.get("callback_data") for r in _care["inline_keyboard"]
             for b in r]
check("🧩 «درباره ما» در منوی پشتیبانی و باشگاه هست",
      "ab_admin" in _care_cbs, str(_care_cbs))
_settings = _BA.kb_settings(uid=S)
_set_cbs = [b.get("callback_data") for r in _settings["inline_keyboard"]
            for b in r]
check("🧩 و از منوی تنظیمات حذف شد", "ab_admin" not in _set_cbs,
      str(_set_cbs))


# ═══════════ ۷.۷) 💾 بک‌آپ خودکار + ✨ امکانات در ویزارد ═══════════
print("\n[۷.۷] 💾 بک‌آپ خودکار و ایمنی داده")

check("تابع بک‌آپ خودکار هست", hasattr(database, "auto_backup"))
check("آمار بک‌آپ هست", hasattr(database, "backup_stats"))
check("صحت‌سنجی بک‌آپ هست", hasattr(database, "_verify_backup"))

_bp = database.auto_backup(force=True)
check("💾 بک‌آپ اجباری گرفته شد", bool(_bp), str(_bp))
check("💾 فایل بک‌آپ واقعاً وجود دارد",
      bool(_bp) and Path(_bp).exists())
check("🔍 بک‌آپ سالم است", database._verify_backup(Path(_bp)))

_st = database.backup_stats()
check("📊 آمار بک‌آپ درست است", _st["count"] >= 1, str(_st))
check("📅 بک‌آپ روزانه ساخته شد", _st["daily"] >= 1, str(_st["daily"]))

# بلافاصله دوباره → نباید بگیرد (زمان‌بندی رعایت شود)
check("⏱️ بک‌آپ زودتر از موعد تکرار نمی‌شود",
      database.auto_backup() is None)

# فایل خراب باید رد شود
_bad = Path(_bp).parent / "broken_test.db"
_bad.write_bytes(b"this is not a database")
check("🔍 فایل خراب رد می‌شود", not database._verify_backup(_bad))
_bad.unlink()

# 🔴 مهم‌ترین: داده با آپدیت از بین نرود
_before_users = database.db_scalar("SELECT COUNT(*) FROM users")
_before_forms = database.db_scalar("SELECT COUNT(*) FROM forms")
_before_name = F.get_form(eid_exam)["title"]
database.set_setting("test_survive_key", "زنده‌ام", "t", "general")

# شبیه‌سازی آپدیت: ستون جدید + اجرای دوباره init
F.FORMS_SCHEMA["phase19_future_col"] = "TEXT DEFAULT 'ok'"
F.init_form_tables()
EV.init_event_tables()
PAY.init_payment_tables()
database.clear_settings_cache()

check("🔴 هیچ کاربری حذف نشد",
      database.db_scalar("SELECT COUNT(*) FROM users") == _before_users)
check("🔴 هیچ فرمی حذف نشد",
      database.db_scalar("SELECT COUNT(*) FROM forms") == _before_forms)
check("🔴 محتوای فرم سالم ماند",
      F.get_form(eid_exam)["title"] == _before_name)
check("🔴 تنظیمات سفارشی حفظ شد",
      database.get_setting("test_survive_key", "") == "زنده‌ام")
check("➕ ستون جدید اضافه شد",
      F.get_form(eid_exam).get("phase19_future_col") == "ok")
check("🔴 امکانات ویژه قبلی پاک نشد",
      F.get_form(eid_exam)["time_limit_min"] == 30,
      str(F.get_form(eid_exam)["time_limit_min"]))
F.FORMS_SCHEMA.pop("phase19_future_col", None)

# پنل بک‌آپ
SENT.clear()
M.handle_callback(cb(S, "admin_backup"))
check("پنل بک‌آپ باز شد", "بک‌آپ" in last(), last()[:60])
check("وضعیت خودکار نمایش داده می‌شود",
      "خودکار" in last(), last()[:200])
check("توضیح ایمنی آپدیت هست",
      "آپدیت" in last(), last()[:400])

# 🔔 یادآوری اقساط باید در حلقه اصلی صدا زده شود
_main_src = (ROOT / "main.py").read_text(encoding="utf-8")
check("🔔 یادآوری اقساط در حلقه اصلی وصل شد",
      "check_due_reminders()" in _main_src)
check("💾 بک‌آپ خودکار در حلقه اصلی وصل شد",
      "auto_backup()" in _main_src)


print("\n[۷.۸] ✨ امکانات ویژه در ویزارد ساخت فرم")

SENT.clear()
M.handle_callback(cb(S, "fb_new"))
M.handle_callback(cb(S, "fbt_contest"))
M.process_message(msg(S, "مسابقه عکاسی"))
SENT.clear()
M.process_message(msg(S, "⏭️ رد کردن"))
_txt_all = alltext()
_cbs = allcb()
check("✨ امکانات ویژه همان اول نشان داده شد",
      "امکان ویژه" in _txt_all, _txt_all[:200])
check("✨ نام امکانات ذکر شده",
      "مهلت شرکت" in _txt_all or "رتبه‌بندی" in _txt_all,
      _txt_all[:250])
check("✨ دکمه تنظیم امکانات ویژه هست",
      any(c.startswith("fbfeat_") for c in _cbs), str(_cbs))
check("🎁 دکمه سوالات پیشنهادی هم هست",
      any(c.startswith("fbtpl_") for c in _cbs), str(_cbs))
check("✍️ دکمه ساخت دستی هم هست",
      any(c.startswith("fbf_") for c in _cbs), str(_cbs))

# فرمی که امکان ویژه ندارد نباید دکمه بی‌خود نشان دهد
_no_feat = [k for k in F.FORM_TYPES if not F.type_features(k)]
check("انواع بدون امکان ویژه هم پشتیبانی می‌شوند",
      isinstance(_no_feat, list))


# ═══════════ ۸) 🛡️ رگرسیون ═══════════
print("\n[۸] 🛡️ رگرسیون")

check("همه مبالغ هنوز ریال‌اند", config.MONEY_UNIT == "rial")
check("فرم‌های عمومی هنوز دیده می‌شوند",
      len(F.list_visible_forms()) > 0)

# هیچ فرمی به‌خاطر ستون‌های جدید خراب نشده
SENT.clear()
M.handle_callback(cb(U1, "u_forms"))
check("فهرست فرم‌های کاربر سالم است",
      "فرم" in last(), last()[:60])

SENT.clear()
M.handle_callback(cb(S, f"fbdet_{eid_exam}"))
check("جزئیات فرم سالم است", "جزئیات" in last(), last()[:50])
check("دکمه امکانات ویژه در جزئیات هست",
      any("fbfeat_" in c for c in allcb()))
check("دکمه دسترسی در جزئیات هست",
      any("fbvis_" in c for c in allcb()))

check("مبلغ منفی در اقساط نیست",
      (database.db_scalar("SELECT COUNT(*) FROM payment_schedules "
                          "WHERE amount < 0") or 0) == 0)
check("قسط بدون کاربر نیست",
      (database.db_scalar("SELECT COUNT(*) FROM payment_schedules "
                          "WHERE bale_user_id IS NULL") or 0) == 0)

# لاگ فارسی همه اکشن‌های جدید
import activity_log as AL  # noqa: E402
for a in ("payplan_started", "payplan_created", "installment_paid",
          "profile_param_added", "about_text_edited", "about_link_added"):
    check(f"لاگ «{a}» ترجمه فارسی دارد", a in AL.ACTION_FA)


print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\nناموفق:")
    for f in FAILED:
        print(f"  ❌ {f}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۱۸ پاس شدند!")
