"""
تست فاز ۱۷ — کارمزد چندروشی + پرداخت غیرمتمرکز

درخواست کاربر:
  ۱) کارمزد روی همه روش‌های پرداخت (نه فقط درگاه)، هر کدام
     درصد و مبلغ مستقل
  ۲) پرداخت غیرمتمرکز — ساخت لینک پرداخت یکبار/چندبار مصرف
     با مبلغ، کارمزد و جزئیات
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora17_")
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
    SENT.append({"m": "editMessageText",
                 "p": {"cid": cid, "text": text, "kb": kb}})
    return {"ok": True, "result": {"message_id": mid or 1}}


def _file(method, key, cid, f, caption=None, kb=None):
    SENT.append({"m": method, "p": {"cid": cid, "caption": caption, "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT) + 100}}


_INV = []


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
import auth  # noqa: E402
import forms as F  # noqa: E402
import form_fill as FF  # noqa: E402
import payments as PAY  # noqa: E402
import events as EV  # noqa: E402
import attendance as AT  # noqa: E402
import occasions as OC  # noqa: E402
import permissions as PM  # noqa: E402
import activity_log as AL  # noqa: E402
import club as CL  # noqa: E402
import tickets as TK  # noqa: E402
import lottery as LT  # noqa: E402
import paylink as PL  # noqa: E402
import admin as AD  # noqa: E402
import main as M  # noqa: E402

for mod in (F, FF, PAY, EV, AT, OC, AL, CL, TK, LT, PL, AD, M):
    for n in ("send", "send_or_edit", "send_photo", "send_document"):
        if hasattr(mod, n):
            setattr(mod, n, getattr(bale_api, n))
PAY.send_invoice = _invoice

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


def to(cid):
    return [s["p"].get("text") or "" for s in SENT
            if s["m"] == "sendMessage" and s["p"].get("cid") == cid]


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


def setfee(method, **kw):
    for part, val in kw.items():
        database.set_setting(PAY._fk(method, part), str(val), "t", "payment")
    database.clear_settings_cache()


S = 100000001
A_FIN, A_EV = 980001, 980002
U1, U2 = 990001, 990002

print("=" * 62)
print("🧪 تست فاز ۱۷ — کارمزد چندروشی + پرداخت غیرمتمرکز")
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
LT.init_lottery_tables()
PL.init_paylink_tables()

auth.create_auth_user({"id": S, "first_name": "مدیر"}, "09120000000", "phone")
auth.ensure_super_admin(S)
auth.create_auth_user({"id": A_FIN, "first_name": "لیلا"}, "09131111111",
                      "phone")
auth.create_auth_user({"id": A_EV, "first_name": "رضا"}, "09132222222",
                      "phone")
PM.set_role(A_FIN, "finance_admin", S)
PM.set_role(A_EV, "event_admin", S)
for u, n in ((U1, "علی"), (U2, "سارا")):
    auth.create_auth_user({"id": u, "first_name": n}, f"0913{u}", "phone")
    database.db_execute("UPDATE users SET profile_status='approved', "
                        "complete_profile_percent=100 WHERE bale_user_id=?",
                        (u,))


# ═══════════ ۱) کارمزد چندروشی ═══════════
print("\n[۱] 💳 کارمزد روی همه روش‌ها")

check("۵ روش قابل کارمزد", len(PAY.FEE_METHODS) == 5,
      str(PAY.FEE_METHODS))
for m in ("custom_gateway", "bale_wallet", "card", "onsite", "points"):
    check(f"روش {m}", m in PAY.FEE_METHODS)

check("همه پیش‌فرض خاموش",
      not any(PAY.fee_enabled(m) for m in PAY.FEE_METHODS))
check("any_fee_enabled خاموش", not PAY.any_fee_enabled())

# هر روش مستقل
setfee("card", on=1, pct=3)
check("کارت روشن شد", PAY.fee_enabled("card"))
check("🔒 بقیه هنوز خاموش", not PAY.fee_enabled("bale_wallet"))
check("any_fee_enabled روشن", PAY.any_fee_enabled())

f_c, t_c = PAY.calc_fee(1000000, "card")
check("کارمزد کارت ۳٪", f_c == 30000, str(f_c))
f_w, t_w = PAY.calc_fee(1000000, "bale_wallet")
check("کیف پول بدون کارمزد", f_w == 0 and t_w == 1000000, f"{f_w},{t_w}")

# درصدهای متفاوت
setfee("bale_wallet", on=1, pct=1.5)
setfee("custom_gateway", on=1, pct=2)
check("کیف پول ۱.۵٪", PAY.calc_fee(1000000, "bale_wallet")[0] == 15000)
check("درگاه ۲٪", PAY.calc_fee(1000000, "custom_gateway")[0] == 20000)
check("کارت هنوز ۳٪", PAY.calc_fee(1000000, "card")[0] == 30000)

# مبلغ ثابت
setfee("onsite", on=1, pct=0, fix=50000)   # ۵۰٬۰۰۰ ریال ثابت
check("مبلغ ثابت", PAY.calc_fee(1000000, "onsite")[0] == 50000,
      str(PAY.calc_fee(1000000, "onsite")[0]))

# درصد + ثابت
setfee("points", on=1, pct=2, fix=10000)
f_p, _ = PAY.calc_fee(1000000, "points")
check("درصد + ثابت", f_p == 20000 + 10000, str(f_p))

# عنوان مستقل
setfee("card", label="کارمزد بانکی")
setfee("bale_wallet", label="کارمزد کیف پول")
check("عنوان کارت", PAY.fee_label("card") == "کارمزد بانکی")
check("عنوان کیف پول", PAY.fee_label("bale_wallet") == "کارمزد کیف پول")
check("عنوان پیش‌فرض بقیه",
      PAY.fee_label("onsite") == PAY.DEFAULT_FEE_LABEL,
      PAY.fee_label("onsite"))

# سقف و حداقل مستقل
setfee("card", max=20000)
check("سقف کارت", PAY.calc_fee(10000000, "card")[0] == 20000,
      str(PAY.calc_fee(10000000, "card")[0]))
check("سقف روی درگاه اثر ندارد",
      PAY.calc_fee(10000000, "custom_gateway")[0] == 200000)
setfee("card", max=0, min=10000)
check("حداقل کارت", PAY.calc_fee(10000, "card")[0] == 10000,
      str(PAY.calc_fee(10000, "card")[0]))
setfee("card", min=0)

# ورودی خراب
check("روش نامعتبر", PAY.calc_fee(1000, "evil") == (0, 1000))
check("مبلغ None", PAY.calc_fee(None, "card") == (0, 0))
check("fee_enabled نامعتبر", not PAY.fee_enabled("evil"))

# breakdown
brk = PAY.fee_breakdown(1000000, "card")
check("ریز مبلغ ساخته شد", "ریز مبلغ" in brk, brk[:60])
check("عنوان در ریز مبلغ", "کارمزد بانکی" in brk)
setfee("card", on=0)
check("خاموش → ریز مبلغ خالی", PAY.fee_breakdown(1000000, "card") == "")
setfee("card", on=1)


# ═══════════ ۲) پنل کارمزد چندروشی ═══════════
print("\n[۲] ⚙️ پنل کارمزد")

SENT.clear()
M.handle_callback(cb(S, "pay_fee"))
fe = allcb()
check("صفحه کارمزد", "کارمزد" in last(), last()[:50])
check("همه روش‌ها دکمه دارند",
      sum(1 for d in fe if d.startswith("payfm_")) == 5, str(fe))
check("وضعیت هر روش نشان داده شد",
      "🟢" in last() or "⚪" in last(), last()[:120])
# یکی را خاموش کنیم تا هر دو حالت دیده شود
setfee("points", on=0)
SENT.clear()
M.handle_callback(cb(S, "pay_fee"))
check("روش خاموش با ⚪ و روشن با 🟢",
      "🟢" in last() and "⚪" in last(), last()[:150])
setfee("points", on=1)

SENT.clear()
M.handle_callback(cb(S, "payfm_card"))
fm = allcb()
check("صفحه کارت", "کارت به کارت" in last(), last()[:50])
check("دکمه تاگل", "payft_card" in fm, str(fm))
check("دکمه درصد", "payfe_pct_card" in fm)
check("دکمه ثابت", "payfe_fix_card" in fm)
check("دکمه حداقل", "payfe_min_card" in fm)
check("دکمه سقف", "payfe_max_card" in fm)
check("دکمه عنوان", "payfe_label_card" in fm)
check("مثال محاسبه", "مثال" in last())

# تغییر درصد
SENT.clear()
M.handle_callback(cb(S, "payfe_pct_card"))
check("ویرایش درصد", "درصد" in last(), last()[:40])
M.process_message(msg(S, "abc"))
check("🔒 ورودی خراب رد شد", "معتبر" in last(), last()[:40])
M.process_message(msg(S, "4.5"))
check("درصد ذخیره شد", PAY.fee_percent("card") == 4.5,
      str(PAY.fee_percent("card")))
check("🔒 روش دیگر دست‌نخورد", PAY.fee_percent("bale_wallet") == 1.5)

# مبلغ ثابت
SENT.clear()
M.handle_callback(cb(S, "payfe_fix_card"))
M.process_message(msg(S, "20000"))
check("مبلغ ثابت ذخیره شد", PAY.fee_fixed("card") == 20000,
      str(PAY.fee_fixed("card")))
setfee("card", fix=0)

# تاگل
SENT.clear()
M.handle_callback(cb(S, "payft_card"))
check("خاموش شد", not PAY.fee_enabled("card"))
M.handle_callback(cb(S, "payft_card"))
check("روشن شد", PAY.fee_enabled("card"))

# 🔒 دسترسی
SENT.clear()
M.handle_callback(cb(A_FIN, "pay_fee"))
check("🔒 ادمین رسیدها دسترسی ندارد",
      "سوپرادمین" in last() or "دسترسی" in last(), last()[:50])
SENT.clear()
M.handle_callback(cb(A_EV, "payft_card"))
check("🔒 ادمین رویداد تاگل نمی‌کند", PAY.fee_enabled("card"))


# ═══════════ ۳) کارمزد در پرداخت واقعی ═══════════
print("\n[۳] 🧾 کارمزد در جریان پرداخت")

setfee("bale_wallet", on=1, pct=2, fix=0, min=0, max=0)
eid = database.db_execute(
    "INSERT INTO events (title, event_type, status, is_paid, price, "
    "payment_method, capacity, created_by) "
    "VALUES ('رویداد کیف‌پولی','workshop','published',1,1000000,"
    "'bale_wallet',50,?)", (S,))
ev = EV.get_event(eid)
rid = database.db_execute("""INSERT INTO event_registrations
    (event_id, user_id, bale_user_id, status)
    VALUES (?,?,?,'pending')""", (eid, auth.get_user(U1)["id"], U1))

_INV.clear()
SENT.clear()
PAY.route_payment(U1, U1, ev, rid, 1000000)
check("ریز مبلغ کیف پول", "ریز مبلغ" in alltext(), alltext()[:150])
tx = database.db_execute("SELECT * FROM transactions WHERE registration_id=?",
                         (rid,), fetch="one")
check("کارمزد کیف پول ذخیره شد", tx and tx["fee_amount"] == 20000,
      str(tx.get("fee_amount") if tx else None))
check("مبلغ کل درست", tx and tx["amount"] == 1020000,
      str(tx.get("amount") if tx else None))
check("صورتحساب دو خطی شد",
      _INV and len(_INV[-1].get("prices") or []) == 2,
      str(_INV[-1].get("prices") if _INV else None))

# کارت به کارت
setfee("card", on=1, pct=3, fix=0)
database.db_execute("""INSERT INTO bank_cards
    (owner_id, card_number, card_holder_name, bank_name, is_active)
    VALUES (?,'6037991234567890','مدیر','ملی',1)""", (S,))
eid2 = database.db_execute(
    "INSERT INTO events (title, event_type, status, is_paid, price, "
    "payment_method, capacity, created_by) "
    "VALUES ('رویداد کارتی','workshop','published',1,1000000,'card',50,?)",
    (S,))
rid2 = database.db_execute("""INSERT INTO event_registrations
    (event_id, user_id, bale_user_id, status)
    VALUES (?,?,?,'pending')""", (eid2, auth.get_user(U2)["id"], U2))
SENT.clear()
PAY.route_payment(U2, U2, EV.get_event(eid2), rid2, 1000000)
check("ریز مبلغ کارت", "ریز مبلغ" in alltext(), alltext()[:150])
tx2 = database.db_execute("SELECT * FROM transactions WHERE registration_id=?",
                          (rid2,), fetch="one")
check("کارمزد کارت ذخیره شد", tx2 and tx2["fee_amount"] == 30000,
      str(tx2.get("fee_amount") if tx2 else None))
auth.clear_state(U2)


# ═══════════ ۴) پرداخت غیرمتمرکز — ساختار ═══════════
print("\n[۴] 🔗 پرداخت غیرمتمرکز — ساختار")

tabs = {r["name"] for r in database.db_execute(
    "SELECT name FROM sqlite_master WHERE type='table'", fetch="all")}
check("جدول payment_links", "payment_links" in tabs)
check("جدول paylink_payments", "paylink_payments" in tabs)

c1, c2 = PL.gen_code(), PL.gen_code()
check("کد یکتا تولید می‌شود", c1 != c2)
check("کد با PL شروع می‌شود", c1.startswith("PL"))

SENT.clear()
M.handle_callback(cb(S, "set_payment"))
check("🔗 دکمه در منوی مالی", "pl_panel" in allcb(), str(allcb()))

SENT.clear()
M.handle_callback(cb(S, "pl_panel"))
check("پنل باز شد", "پرداخت غیرمتمرکز" in last(), last()[:50])
check("دکمه ساخت", "pl_new" in allcb())
check("راهنما نمایش داده شد", "لینک پرداخت مستقل" in last())


# ═══════════ ۵) ساخت لینک (ویزارد) ═══════════
print("\n[۵] ➕ ساخت لینک")

SENT.clear()
M.handle_callback(cb(S, "pl_new"))
check("ویزارد شروع شد", "عنوان" in last(), last()[:50])

M.process_message(msg(S, "شهریه ترم بهار"))
check("توضیحات پرسیده شد", "توضیح" in last(), last()[:40])
M.process_message(msg(S, "شهریه دوره فن‌بیان"))
check("مبلغ پرسیده شد", "مبلغ" in last(), last()[:40])
M.process_message(msg(S, "2500000"))
check("لینک ساخته شد", "ساخته شد" in alltext(), alltext()[:60])

link = database.db_execute("SELECT * FROM payment_links ORDER BY id DESC "
                           "LIMIT 1", fetch="one")
check("در دیتابیس ذخیره شد", bool(link))
check("عنوان درست", link["title"] == "شهریه ترم بهار")
check("توضیحات درست", link["description"] == "شهریه دوره فن‌بیان")
check("مبلغ ریالی درست", link["amount"] == 2500000, str(link["amount"]))
check("کد دارد", bool(link["code"]))
check("فعال است", link["is_active"] == 1)
check("پیش‌فرض چندبار مصرف", link["usage_type"] == "multi")

lid = link["id"]

SENT.clear()
M.handle_callback(cb(S, f"pl_v_{lid}"))
check("صفحه لینک", "شهریه ترم بهار" in last(), last()[:50])
check("لینک نمایش داده شد", link["code"] in last())
v = allcb()
for d in ("pl_share_", "pl_meth_", "pl_use_", "pl_ask_", "pl_tog_",
          "pl_del_"):
    check(f"دکمه {d}", any(x.startswith(d) for x in v), str(v)[:100])

# مبلغ دلخواه
SENT.clear()
M.handle_callback(cb(S, "pl_new"))
M.process_message(msg(S, "کمک مالی"))
M.process_message(msg(S, "⏭️ رد کردن"))
M.process_message(msg(S, "✍️ مبلغ دلخواه"))
link2 = database.db_execute("SELECT * FROM payment_links ORDER BY id DESC "
                            "LIMIT 1", fetch="one")
check("لینک مبلغ باز ساخته شد", link2["amount_mode"] == "open",
      str(link2["amount_mode"]))
check("توضیحات خالی", not link2["description"])
lid2 = link2["id"]

# لغو ویزارد
SENT.clear()
M.handle_callback(cb(S, "pl_new"))
M.process_message(msg(S, "🔙 بازگشت"))
check("لغو ویزارد", "لغو" in alltext(), alltext()[:40])

# عنوان خالی
SENT.clear()
M.handle_callback(cb(S, "pl_new"))
M.process_message(msg(S, "   "))
check("🔒 عنوان خالی رد شد", "لازم" in last(), last()[:40])
auth.clear_state(S)


# ═══════════ ۶) تنظیمات لینک ═══════════
print("\n[۶] ⚙️ تنظیمات لینک")

# روش پرداخت
SENT.clear()
M.handle_callback(cb(S, f"pl_meth_{lid}"))
check("انتخاب روش", "روش پرداخت" in last(), last()[:40])
check("نشان کارمزد", "💳 = این روش کارمزد دارد" in last())
M.handle_callback(cb(S, f"pl_sm_card_{lid}"))
check("روش عوض شد", PL.get_link(lid)["method"] == "card")

# نوع مصرف
SENT.clear()
M.handle_callback(cb(S, f"pl_use_{lid}"))
check("نوع مصرف", "نوع مصرف" in last(), last()[:40])
M.handle_callback(cb(S, f"pl_su_once_{lid}"))
check("یکبار مصرف شد", PL.get_link(lid)["usage_type"] == "once")
M.handle_callback(cb(S, f"pl_su_multi_{lid}"))
check("چندبار مصرف شد", PL.get_link(lid)["usage_type"] == "multi")

SENT.clear()
M.handle_callback(cb(S, f"pl_max_{lid}"))
M.process_message(msg(S, "5"))
check("سقف تعداد ذخیره شد", PL.get_link(lid)["max_uses"] == 5,
      str(PL.get_link(lid)["max_uses"]))

# سوالات
SENT.clear()
M.handle_callback(cb(S, f"pl_ask_{lid}"))
check("صفحه سوالات", "پرداخت‌کننده" in last(), last()[:40])
M.handle_callback(cb(S, f"pl_t_ask_note_{lid}"))
check("سوال توضیح روشن شد", PL.get_link(lid)["ask_note"] == 1)
M.handle_callback(cb(S, f"pl_t_require_auth_{lid}"))
check("احراز هویت خاموش شد", PL.get_link(lid)["require_auth"] == 0)
M.handle_callback(cb(S, f"pl_t_require_auth_{lid}"))

SENT.clear()
M.handle_callback(cb(S, f"pl_t_evil_{lid}"))
check("🔒 فیلد نامعتبر رد شد", "نامعتبر" in last())

# ویرایش
SENT.clear()
M.handle_callback(cb(S, f"pl_e_title_{lid}"))
M.process_message(msg(S, "شهریه ترم تابستان"))
check("عنوان ویرایش شد",
      PL.get_link(lid)["title"] == "شهریه ترم تابستان")

SENT.clear()
M.handle_callback(cb(S, f"pl_e_amount_{lid}"))
M.process_message(msg(S, "3000000"))
check("مبلغ ویرایش شد", PL.get_link(lid)["amount"] == 3000000,
      str(PL.get_link(lid)["amount"]))

SENT.clear()
M.handle_callback(cb(S, f"pl_e_expires_at_{lid}"))
M.process_message(msg(S, "بد"))
check("🔒 تاریخ خراب رد شد", "قالب" in last(), last()[:40])
M.process_message(msg(S, "1404/12/29"))
check("انقضا ذخیره شد", PL.get_link(lid)["expires_at"] == "1404/12/29")

# اشتراک‌گذاری
SENT.clear()
M.handle_callback(cb(S, f"pl_share_{lid}"))
check("پیام اشتراک‌گذاری", "پرداخت" in alltext())
check("لینک در پیام", PL.get_link(lid)["code"] in alltext())


# ═══════════ ۷) وضعیت لینک ═══════════
print("\n[۷] 📊 وضعیت لینک")

database.db_execute("UPDATE payment_links SET expires_at=NULL, "
                    "is_active=1, paid_count=0, max_uses=0, "
                    "usage_type='multi' WHERE id=?", (lid,))
l = PL.get_link(lid)
ic, st, usable = PL.link_status(l)
check("لینک فعال قابل استفاده", usable, st)

# غیرفعال
M.handle_callback(cb(S, f"pl_tog_{lid}"))
check("غیرفعال شد", not PL.link_status(PL.get_link(lid))[2])
M.handle_callback(cb(S, f"pl_tog_{lid}"))
check("دوباره فعال شد", PL.link_status(PL.get_link(lid))[2])

# منقضی
database.db_execute("UPDATE payment_links SET expires_at='1400/01/01' "
                    "WHERE id=?", (lid,))
check("منقضی قابل استفاده نیست",
      not PL.link_status(PL.get_link(lid))[2])
database.db_execute("UPDATE payment_links SET expires_at=NULL WHERE id=?",
                    (lid,))

# سقف پر
database.db_execute("UPDATE payment_links SET max_uses=2, paid_count=2 "
                    "WHERE id=?", (lid,))
ic2, st2, us2 = PL.link_status(PL.get_link(lid))
check("سقف پر → غیرقابل استفاده", not us2, st2)
database.db_execute("UPDATE payment_links SET max_uses=0, paid_count=0 "
                    "WHERE id=?", (lid,))

# یکبار مصرف استفاده‌شده
database.db_execute("UPDATE payment_links SET usage_type='once', "
                    "paid_count=1 WHERE id=?", (lid,))
check("یکبار مصرف استفاده‌شده",
      not PL.link_status(PL.get_link(lid))[2])
database.db_execute("UPDATE payment_links SET usage_type='multi', "
                    "paid_count=0 WHERE id=?", (lid,))

check("لینک None امن", PL.link_status(None)[2] is False)


# ═══════════ ۸) پرداخت کاربر ═══════════
print("\n[۸] 👤 پرداخت کاربر از لینک")

code = PL.get_link(lid)["code"]
url = PL.link_url(PL.get_link(lid))
check("لینک URL ساخته شد", code in url, url)

SENT.clear()
PL.open_link(U1, U1, code)
check("کاربر جزئیات را می‌بیند", "شهریه ترم تابستان" in last(), last()[:60])
check("دکمه پرداخت", f"plpay_{lid}" in allcb(), str(allcb()))

# کارمزد در نمای کاربر
setfee("card", on=1, pct=3)
SENT.clear()
PL.open_link(U1, U1, code)
check("کارمزد در نمای کاربر", "کارمزد" in last(), last()[:200])

# کد نامعتبر
SENT.clear()
PL.open_link(U1, U1, "PLXXXXXXXX")
check("🔒 کد نامعتبر", "معتبر نیست" in last(), last()[:40])
SENT.clear()
PL.open_link(U1, U1, "evil")
check("🔒 کد خراب امن", "معتبر نیست" in last())

# deep link
SENT.clear()
M.process_message(msg(U1, f"/start pay_{code}"))
check("deep link کار می‌کند",
      "شهریه ترم تابستان" in alltext(), alltext()[:80])

# پرداخت کارت
SENT.clear()
M.handle_callback(cb(U1, f"plpay_{lid}"))
check("صفحه پرداخت کارت", "کارت به کارت" in last(), last()[:60])
check("شماره کارت نمایش داده شد", "6037" in last())
check("ریز مبلغ", "ریز مبلغ" in last())
p1 = database.db_execute("SELECT * FROM paylink_payments WHERE link_id=? "
                         "ORDER BY id DESC LIMIT 1", (lid,), fetch="one")
check("رکورد پرداخت ساخته شد", bool(p1))
check("مبلغ پایه", p1 and p1["amount"] == 3000000, str(p1.get("amount")))
check("کارمزد", p1 and p1["fee_amount"] == 90000, str(p1.get("fee_amount")))
check("مبلغ کل", p1 and p1["total_amount"] == 3090000,
      str(p1.get("total_amount")))
check("وضعیت pending", p1 and p1["status"] == "pending")
auth.clear_state(U1)

# مبلغ باز
SENT.clear()
M.handle_callback(cb(U2, f"plpay_{lid2}"))
check("مبلغ باز پرسیده شد", "مبلغ" in last(), last()[:40])
M.process_message(msg(U2, "abc"))
check("🔒 مبلغ خراب رد شد", "عدد" in last(), last()[:40])
M.process_message(msg(U2, "1500000"))
p2 = database.db_execute("SELECT * FROM paylink_payments WHERE link_id=? "
                         "ORDER BY id DESC LIMIT 1", (lid2,), fetch="one")
check("پرداخت مبلغ باز ثبت شد", p2 and p2["amount"] == 1500000,
      str(p2.get("amount") if p2 else None))
auth.clear_state(U2)

# حداقل و حداکثر مبلغ باز
database.db_execute("UPDATE payment_links SET min_amount=1000000, "
                    "max_amount=5000000 WHERE id=?", (lid2,))
SENT.clear()
M.handle_callback(cb(U2, f"plpay_{lid2}"))
M.process_message(msg(U2, "500000"))
check("🔒 کمتر از حداقل رد شد", "حداقل" in last(), last()[:40])
M.process_message(msg(U2, "9000000"))
check("🔒 بیشتر از حداکثر رد شد", "حداکثر" in last(), last()[:40])
auth.clear_state(U2)


# ═══════════ ۹) ثبت پرداخت موفق ═══════════
print("\n[۹] ✅ ثبت پرداخت موفق")

before_paid = PL.get_link(lid)["paid_count"] or 0
before_total = PL.get_link(lid)["total_collected"] or 0

SENT.clear()
ok = PL.mark_paid(p1["payload"], "TXN123")
check("mark_paid موفق", ok)
p1b = database.db_execute("SELECT * FROM paylink_payments WHERE id=?",
                          (p1["id"],), fetch="one")
check("وضعیت paid شد", p1b["status"] == "paid")
check("شماره پیگیری ذخیره شد", p1b["transaction_id"] == "TXN123")

lk = PL.get_link(lid)
check("شمارنده افزایش یافت", lk["paid_count"] == before_paid + 1,
      str(lk["paid_count"]))
check("مبلغ جمع شد",
      lk["total_collected"] == before_total + 3090000,
      str(lk["total_collected"]))
check("کاربر پیام گرفت",
      any("موفقیت" in t for t in to(U1)), str(to(U1))[-100:])
check("ادمین اعلان گرفت",
      any("پرداخت جدید" in t for t in to(S)), str(to(S))[-100:])

# دوباره
check("mark_paid دوباره امن", PL.mark_paid(p1["payload"], "X"))
check("شمارنده تکرار نشد", PL.get_link(lid)["paid_count"] == before_paid + 1)

check("payload نامعتبر", not PL.mark_paid("evil", ""))

# پیام سفارشی
database.db_execute("UPDATE payment_links SET success_text=? WHERE id=?",
                    ("🎉 ممنون از پرداخت شما!", lid))
p3 = database.db_execute("""INSERT INTO paylink_payments
    (link_id, bale_user_id, amount, total_amount, method, status, payload)
    VALUES (?,?,100000,100000,'card','pending','plTEST9')""", (lid, U2))
SENT.clear()
PL.mark_paid("plTEST9", "T9")
check("پیام سفارشی ارسال شد",
      any("ممنون از پرداخت" in t for t in to(U2)), str(to(U2))[-80:])


# ═══════════ ۱۰) گزارش و خروجی ═══════════
print("\n[۱۰] 📊 گزارش")

SENT.clear()
M.handle_callback(cb(S, "pl_rep"))
check("گزارش کلی", "گزارش پرداخت" in last(), last()[:50])
check("مجموع نمایش داده شد", "مجموع" in last())

SENT.clear()
M.handle_callback(cb(S, f"pl_tx_{lid}"))
check("پرداخت‌های یک لینک", "پرداخت‌های" in last(), last()[:50])

SENT.clear()
M.handle_callback(cb(S, "pl_exp"))
check("خروجی Excel",
      any(s["m"] == "sendDocument" for s in SENT), last()[:60])

SENT.clear()
M.handle_callback(cb(S, "pl_panel"))
check("آمار در پنل", "مجموع دریافتی" in last(), last()[:100])
check("لینک‌ها لیست شدند",
      any(d.startswith("pl_v_") for d in allcb()))


# ═══════════ ۱۱) حذف و دسترسی ═══════════
print("\n[۱۱] 🔒 حذف و دسترسی")

SENT.clear()
M.handle_callback(cb(S, f"pl_del_{lid2}"))
check("تأیید حذف", "مطمئن" in last(), last()[:40])
check("هنوز حذف نشده", bool(PL.get_link(lid2)))
M.handle_callback(cb(S, f"pl_dely_{lid2}"))
check("حذف شد", not PL.get_link(lid2))

SENT.clear()
M.handle_callback(cb(A_EV, "pl_panel"))
check("🔒 ادمین رویداد دسترسی ندارد",
      "سوپرادمین" in last() or "دسترسی" in last(), last()[:50])
SENT.clear()
M.handle_callback(cb(U1, "pl_new"))
check("🔒 کاربر عادی لینک نمی‌سازد", "دسترسی" in last())
SENT.clear()
M.handle_callback(cb(U1, f"pl_del_{lid}"))
check("🔒 کاربر عادی حذف نمی‌کند", bool(PL.get_link(lid)))


# ═══════════ ۱۲) ورودی‌های خراب ═══════════
print("\n[۱۲] 🛡️ ورودی‌های خراب")

bad = [
    "pl_panel", "pl_new", "pl_rep", "pl_exp", "pl_pg_abc",
    "pl_v_", "pl_v_abc", "pl_v_999999",
    "pl_share_abc", "pl_meth_999999", "pl_sm_evil_1", "pl_sm_card_999999",
    "pl_use_abc", "pl_su_evil_1", "pl_max_999999",
    "pl_ask_abc", "pl_t_evil_1", "pl_t_is_admin_1",
    "pl_e_", "pl_e_evil_1", "pl_e_title_999999",
    "pl_tog_abc", "pl_del_999999", "pl_dely_abc", "pl_tx_abc",
    "plpay_", "plpay_abc", "plpay_999999",
    "plrok_abc", "plrno_999999",
    "pay_fee", "payfm_evil", "payft_evil", "payfe_evil_x",
]
crashed = []
for d in bad:
    try:
        SENT.clear()
        M.handle_callback(cb(S, d))
    except Exception as e:
        crashed.append(f"{d}: {type(e).__name__} {e}")
check("ادمین: هیچ کرشی", not crashed, str(crashed[:3]))

crashed2 = []
for d in bad:
    try:
        SENT.clear()
        M.handle_callback(cb(U1, d))
    except Exception as e:
        crashed2.append(f"{d}: {type(e).__name__} {e}")
check("کاربر عادی: هیچ کرشی", not crashed2, str(crashed2[:3]))

for st in (PL.STATE_PL_NEW, PL.STATE_PL_EDIT, PL.STATE_PL_PAY,
           PAY.STATE_PAY_FEE):
    try:
        auth.set_state(S, st, {"lid": lid, "field": "title",
                               "method": "card", "part": "pct",
                               "step": 0}, merge=False)
        SENT.clear()
        M.process_message(msg(S, "!@#$"))
    except Exception as e:
        check(f"state {st}", False, str(e))
auth.clear_state(S)
check("state های جدید سالم", True)


# ═══════════ ۱۳) لاگ فارسی ═══════════
print("\n[۱۳] 📋 لاگ فارسی")

import re as _re
_missing = []
for f in ROOT.glob("*.py"):
    src = f.read_text(encoding="utf-8")
    for m in _re.finditer(r'log_action\([^,]+,\s*"([a-z_]+)"', src):
        if m.group(1) not in AL.ACTION_FA:
            _missing.append(m.group(1))
check("همه فعالیت‌ها ترجمه دارند", not set(_missing), str(set(_missing)))
for k in ("paylink_created", "paylink_paid", "paylink_deleted",
          "pay_fee_toggle"):
    check(f"ترجمه {k}", k in AL.ACTION_FA)


# ═══════════ ۱۴) رگرسیون ═══════════
print("\n[۱۴] ♻️ رگرسیون")

SENT.clear()
M.handle_callback(cb(S, "admin_panel"))
check("پنل ادمین سالم", "پنل ادمین" in last())
check("پنل خلوت مانده", len(allcb()) <= 8, str(len(allcb())))

SENT.clear()
M.handle_callback(cb(S, "set_payment"))
check("پرداخت و مالی سالم", "پرداخت" in last())

SENT.clear()
M.handle_callback(cb(S, "fin_dash"))
check("داشبورد مالی سالم", "داشبورد مالی" in last())

SENT.clear()
M.handle_callback(cb(S, "admin_stats"))
check("داشبورد گزارشات سالم", "داشبورد گزارشات" in last())

SENT.clear()
M.handle_callback(cb(S, "pay_adv"))
check("پرداخت پیشرفته سالم", "پیشرفته" in last())
check("دکمه کارمزد", "pay_fee" in allcb())

SENT.clear()
M.process_message(msg(U1, "/start"))
check("start کاربر سالم", "نورا" in alltext() or "سلام" in alltext())

# پرداخت رویداد با کارمزد خاموش
for m in PAY.FEE_METHODS:
    setfee(m, on=0)
eid9 = database.db_execute(
    "INSERT INTO events (title, event_type, status, is_paid, price, "
    "payment_method, capacity, created_by) "
    "VALUES ('رویداد ساده','workshop','published',1,500000,"
    "'bale_wallet',50,?)", (S,))
rid9 = database.db_execute("""INSERT INTO event_registrations
    (event_id, user_id, bale_user_id, status)
    VALUES (?,?,?,'pending')""", (eid9, auth.get_user(U2)["id"], U2))
SENT.clear()
PAY.route_payment(U2, U2, EV.get_event(eid9), rid9, 500000)
tx9 = database.db_execute("SELECT * FROM transactions WHERE registration_id=?",
                          (rid9,), fetch="one")
check("♻️ پرداخت بدون کارمزد سالم",
      tx9 and tx9["amount"] == 500000 and (tx9.get("fee_amount") or 0) == 0,
      str(tx9.get("amount") if tx9 else None))


# ═══════════ ۱۵) یکپارچگی ═══════════
print("\n[۱۵] 🧩 یکپارچگی")

# نکته: با حذف لینک، سابقه پرداختش عمداً می‌ماند (برای حسابرسی)
_orph = database.db_scalar("""SELECT COUNT(*) FROM paylink_payments p
    WHERE NOT EXISTS (SELECT 1 FROM payment_links l
                      WHERE l.id=p.link_id)""") or 0
check("سابقه پرداخت بعد از حذف لینک حفظ شد", _orph > 0, str(_orph))
check("مبلغ منفی نیست",
      (database.db_scalar("SELECT COUNT(*) FROM paylink_payments "
                          "WHERE total_amount < 0") or 0) == 0)
check("کارمزد منفی نیست",
      (database.db_scalar("SELECT COUNT(*) FROM paylink_payments "
                          "WHERE COALESCE(fee_amount,0) < 0") or 0) == 0)
check("کل = پایه + کارمزد",
      (database.db_scalar("""SELECT COUNT(*) FROM paylink_payments
          WHERE total_amount <> amount + COALESCE(fee_amount,0)""")
       or 0) == 0)
check("کدها یکتا هستند",
      (database.db_scalar("""SELECT COUNT(*) FROM (
          SELECT code, COUNT(*) c FROM payment_links
          GROUP BY code HAVING c > 1)""") or 0) == 0)


print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\nناموفق:")
    for f in FAILED:
        print(f"  ❌ {f}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۱۷ پاس شدند!")
