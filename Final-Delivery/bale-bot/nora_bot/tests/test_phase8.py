"""
تست فاز ۸ — ۴ روش پرداخت + بازچینی منوها + متن‌های پرداخت

طبق معماری توافق‌شده:
  ❌ غیرفعال / 💳 کارت به کارت / 🏦 کیف پول بله / 🔗 درگاه سفارشی
  و انتقال همه امور کاربران به «مدیریت کاربران»
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora8_")
os.environ.update({
    "BOT_TOKEN": "1095412158:T", "SUPER_ADMIN_ID": "100000001",
    "SAFIR_API_KEY": "k", "SAFIR_BOT_ID": "317041514",
    "PAYMENT_PROVIDER_TOKEN": "WALLET-TEST-1111111111111111",
    "DB_PATH": f"{TMP}/t.db", "BACKUP_DIR": f"{TMP}/b", "IMPORT_DIR": f"{TMP}/i",
    "FILES_DIR": f"{TMP}/f", "PROFILES_DIR": f"{TMP}/f/p",
    "EVENTS_DIR": f"{TMP}/f/e", "LOG_DIR": f"{TMP}/l", "BROADCAST_RATE": "999",
})

import bale_api  # noqa: E402

SENT, INVOICES = [], []


def _api(m, p=None, **k):
    p = p or {}
    SENT.append({"m": m, "p": p})
    if m == "getMe":
        return {"ok": True, "result": {"username": "nora_bot"}}
    if m == "getChatMember":
        return {"ok": True, "result": {"status": "member"}}
    if m == "getChat":
        return {"ok": True, "result": {"title": "x"}}
    if m == "getFile":
        return {"ok": True, "result": {"file_path": "photos/x.jpg"}}
    return {"ok": True, "result": {"message_id": len(SENT)}}


def _send(cid, text, kb=None, reply_to=None):
    SENT.append({"m": "sendMessage", "chat_id": cid, "text": text, "kb": kb})
    return {"ok": True, "result": {"message_id": len(SENT)}}


bale_api.api = _api
bale_api.send = _send
bale_api.send_or_edit = lambda c, t, kb=None, mid=None, force_new=False: _send(c, t, kb)
bale_api.send_photo = lambda *a, **k: {"ok": True}
bale_api.send_document = lambda *a, **k: {"ok": True}
bale_api.answer_callback = lambda *a, **k: {"ok": True}
bale_api.set_context = lambda *a, **k: None
bale_api.clear_context = lambda *a, **k: None
bale_api.forget_menu = lambda c: None
bale_api.set_reaction = lambda *a, **k: {"ok": True}
bale_api.ask_review = lambda *a, **k: {"ok": True}
bale_api.get_file_info = lambda f: {"ok": True,
                                    "result": {"file_path": "photos/x.jpg"}}
bale_api.download_file = lambda f: b"FAKEIMAGE"
bale_api.get_chat = lambda c: {"ok": True, "result": {"title": "x"}}
bale_api.get_chat_member = lambda c, u: {"ok": True, "result": {"status": "member"}}


def _inv(cid, title, description, payload, provider_token, prices, **k):
    INVOICES.append({"chat_id": cid, "payload": payload, "prices": prices})
    return {"ok": True, "result": {"message_id": 1}}


bale_api.send_invoice = _inv

import database, auth, profile as pf, admin as ad  # noqa: E402
import import_excel as ie, events as ev, attendance as att  # noqa: E402
import settings_admin as sa, payments as pay, main as M, config  # noqa: E402

MODS = (database, auth, pf, ad, ie, ev, att, sa, pay, M)
for m in MODS:
    if hasattr(m, "send"):
        m.send = _send
    if hasattr(m, "send_or_edit"):
        m.send_or_edit = bale_api.send_or_edit
    if hasattr(m, "send_photo"):
        m.send_photo = lambda *a, **k: {"ok": True}
    if hasattr(m, "send_document"):
        m.send_document = lambda *a, **k: {"ok": True}
    if hasattr(m, "get_file_info"):
        m.get_file_info = bale_api.get_file_info
    if hasattr(m, "download_file"):
        m.download_file = bale_api.download_file
ad.get_chat = lambda c: {"ok": True, "result": {"title": "x"}}
ev.send_invoice = _inv
pay.send_invoice = _inv
sa.get_bot_username = lambda: "nora_bot"

database.init_db()
ev.init_event_tables()
att.init_attendance_tables()
pay.init_payment_tables()
database.seed_default_settings()
sa.seed_phase5_settings()
auth.ensure_super_admin(100000001)

S, U = 100000001, 666111
database.db_execute("""INSERT INTO users(bale_user_id,first_name,last_name,
    mobile,is_authenticated,profile_status,referral_code,city,gender)
    VALUES(?,?,?,?,1,'approved',?,?,?)""",
    (U, "رضا", "کریمی", "09121234567", f"NORA{U}", "تهران", "مرد"))

PASS, FAIL = [], []


def check(n, c, d=""):
    if c:
        PASS.append(n); print(f"  ✅ {n}")
    else:
        FAIL.append((n, d)); print(f"  ❌ {n}  {d}")


def last():
    m = [c for c in SENT if c["m"] == "sendMessage"]
    return m[-1]["text"] if m else ""


def texts():
    return [c["text"] for c in SENT if c["m"] == "sendMessage"]


def to(cid):
    return [c["text"] for c in SENT
            if c["m"] == "sendMessage" and c.get("chat_id") == cid]


def kbl():
    m = [c for c in SENT if c["m"] == "sendMessage"]
    kb = (m[-1].get("kb") or {}) if m else {}
    out = [b["text"] for r in kb.get("inline_keyboard", []) for b in r]
    out += [b["text"] if isinstance(b, dict) else str(b)
            for r in kb.get("keyboard", []) for b in r]
    return out


def msg(uid, t, mid=1, photo=False):
    m = {"message_id": mid, "from": {"id": uid, "first_name": "ت"},
         "chat": {"id": uid, "type": "private"}, "text": t}
    if photo:
        m.pop("text")
        m["photo"] = [{"file_id": "PH1", "file_size": 1000, "width": 800}]
    return m


def cb(uid, d):
    return {"id": "c", "from": {"id": uid, "first_name": "ت"}, "data": d,
            "message": {"chat": {"id": uid}, "message_id": 9}}


print("\n" + "=" * 62)
print("🧪 تست فاز ۸ — پرداخت و بازچینی منوها")
print("=" * 62)


print("\n[۱] جداول پرداخت")
tb = [t["name"] for t in database.db_execute(
    "SELECT name FROM sqlite_master WHERE type='table'", fetch="all")]
for t in ("bank_cards", "payment_gateways", "payment_receipts"):
    check(f"جدول {t}", t in tb)
ev_cols = {c["name"] for c in database.db_execute(
    "PRAGMA table_info(events)", fetch="all")}
for c in ("payment_method", "payment_card_id", "payment_gateway_id",
          "payment_verification"):
    check(f"ستون events.{c}", c in ev_cols)


print("\n[۲] 👥 بازچینی منوی مدیریت کاربران")
SENT.clear()
M.handle_callback(cb(S, "admin_users"))
check("منوی مدیریت کاربران باز شد", "مدیریت کاربران" in last())
check("آمار سریع دارد", "آمار سریع" in last())
lb = kbl()
expected = ["کاربران", "جستجو", "افزودن کاربر دستی",
            "ورودی گروهی", "خروجی لیست", "برچسب‌ها", "مدیریت ادمین‌ها",
            "مسدودها", "گزارش کاربران"]
for e in expected:
    check(f"🎯 {e}", any(e in x for x in lb), str(lb)[:100])

print("\n[۳] ⚙️ تنظیمات — بدون اکسل")
SENT.clear()
M.handle_callback(cb(S, "admin_settings"))
sl = kbl()
check("🐛 ورودی اکسل از تنظیمات حذف شد",
      not any("ورود از اکسل" in x for x in sl), str(sl))
check("🐛 خروجی اکسل از تنظیمات حذف شد",
      not any("خروجی اکسل" in x for x in sl), str(sl))
check("روش‌های پرداخت هست", any("پرداخت" in x for x in sl))
check("مدیریت متن‌ها هست", any("متن" in x for x in sl))
check("میانبر ادمین‌ها هست", any("ادمین" in x for x in sl))


print("\n[۴] زیرمنوهای مدیریت کاربران")
for data, expect in [("um_list", "مدیریت کاربران"), ("um_admins", "ادمین"),
                     ("um_blocked", "مسدود"), ("um_tags", "برچسب"),
                     ("um_report", "گزارش کاربران"), ("um_vip", "VIP"),
                     ("um_adminlog", "لاگ")]:
    SENT.clear()
    M.handle_callback(cb(S, data))
    check(f"زیرمنو: {expect}", expect in last(), last()[:50])

SENT.clear()
M.handle_callback(cb(S, "um_add"))
check("افزودن کاربر دستی", "افزودن کاربر" in last())
M.process_message(msg(S, "09129998877"))
check("درخواست نام", "نام" in last())
M.process_message(msg(S, "سارا احمدی"))
check("🐛 کاربر دستی اضافه شد", "اضافه شد" in " ".join(texts()))
nu = database.db_execute("SELECT * FROM users WHERE mobile=?",
                         ("09129998877",), fetch="one")
check("در دیتابیس", bool(nu) and nu["first_name"] == "سارا")
check("منبع manual", nu and nu["registration_source"] == "manual")


print("\n[۵] 💳 کارت‌های بانکی")
SENT.clear()
M.handle_callback(cb(S, "pay_cards"))
check("صفحه کارت‌ها", "کارت‌های بانکی" in last())
check("پیام خالی بودن", "ثبت نشده" in last())

M.handle_callback(cb(S, "card_add"))
check("شروع ثبت کارت", "شماره کارت" in last())

M.process_message(msg(S, "123"))
check("کارت کوتاه رد شد", "۱۶ رقم" in last() or "16" in last())
M.process_message(msg(S, "1234567890123456"))
check("🛡️ Luhn نامعتبر رد شد", "نامعتبر" in last(), last()[:50])

VALID = "6037997599999999"
# ساخت یک شماره معتبر Luhn
def make_valid(prefix="603799"):
    base = prefix + "1234567890"[:10 - 0]
    base = (prefix + "0000000000")[:15]
    for d in range(10):
        cand = base + str(d)
        if pay.luhn_valid(cand):
            return cand
    return None

VALID = make_valid()
check("شماره معتبر ساخته شد", bool(VALID), str(VALID))
M.process_message(msg(S, VALID))
check("🐛 شماره معتبر پذیرفته شد", "نام صاحب" in last(), last()[:60])
check("بانک تشخیص داده شد", "ملی" in " ".join(texts()))

M.process_message(msg(S, "علی محمدی"))
check("درخواست بانک", "بانک" in last())
M.process_message(msg(S, "ملی"))
check("درخواست شبا", "شبا" in last())
M.process_message(msg(S, "-"))
check("🐛 کارت ثبت شد", "کارت ثبت شد" in " ".join(texts()))

card = database.db_execute("SELECT * FROM bank_cards LIMIT 1", fetch="one")
check("در دیتابیس", bool(card))
check("پیش‌فرض شد (اولین کارت)", card and card["is_default"] == 1)
check("ماسک درست", pay.mask_card(VALID).startswith("6037") and
      "****" in pay.mask_card(VALID))

SENT.clear()
M.handle_callback(cb(S, f"card_view_{card['id']}"))
check("جزئیات کارت", "جزئیات کارت" in last())
check("شماره کامل نمایش", pay.format_card(VALID) in last())

M.handle_callback(cb(S, f"card_tog_{card['id']}"))
c2 = pay.get_card(card["id"])
check("تاگل فعال/غیرفعال", c2["is_active"] == 0)
M.handle_callback(cb(S, f"card_tog_{card['id']}"))

# کارت تکراری
SENT.clear()
M.handle_callback(cb(S, "card_add"))
M.process_message(msg(S, VALID))
check("🛡️ کارت تکراری رد شد", "قبلاً ثبت" in " ".join(texts()))


print("\n[۶] 🔗 درگاه‌های سفارشی")
SENT.clear()
M.handle_callback(cb(S, "pay_gateways"))
check("صفحه درگاه‌ها", "درگاه" in last())
M.handle_callback(cb(S, "gw_add"))
check("انتخاب نوع درگاه", "نوع درگاه" in last())
check("۵ نوع درگاه", len([x for x in kbl() if "انصراف" not in x]) == 5,
      str(kbl()))
M.handle_callback(cb(S, "gwt_zarinpal"))
check("نام نمایشی خواسته شد", "نام نمایشی" in last())
M.process_message(msg(S, "زرین‌پال خط زندگی"))
check("Merchant خواسته شد", "Merchant" in last())
M.process_message(msg(S, "abc-123-merchant"))
check("API Key خواسته شد", "API" in last())
M.process_message(msg(S, "-"))
check("Callback خواسته شد", "Callback" in last())
M.process_message(msg(S, "https://example.com/cb"))
check("🐛 درگاه ثبت شد", "درگاه ثبت شد" in " ".join(texts()))
gw = database.db_execute("SELECT * FROM payment_gateways LIMIT 1", fetch="one")
check("در دیتابیس", bool(gw) and gw["gateway_type"] == "zarinpal")


print("\n[۷] 📝 متن‌های پرداخت — قابل ویرایش")
SENT.clear()
M.handle_callback(cb(S, "pay_texts"))
check("صفحه متن‌های پرداخت", "متن‌های پرداخت" in last())
check(f"{len(pay.PAYMENT_TEXTS)} متن قابل ویرایش",
      len([x for x in kbl() if "✏️" in x]) == len(pay.PAYMENT_TEXTS),
      str(len([x for x in kbl() if "✏️" in x])))
check("راهنمای متغیرها", "{amount}" in last())

M.handle_callback(cb(S, "ptx_pay_txt_card_intro"))
check("ویرایش شروع شد", "متن جدید" in last())
NEW = "💳 لطفاً {amount} تومان به {card} واریز کنید. بانک: {bank}"
M.process_message(msg(S, NEW))
check("🐛 متن ذخیره شد", database.get_setting("pay_txt_card_intro") == NEW)

rendered = pay.render("pay_txt_card_intro", amount="50٬000",
                      card="6037-1111-2222-3333", bank="ملی")
check("🐛 متغیرها جایگزین شدند",
      "50٬000" in rendered and "6037-1111" in rendered and "ملی" in rendered,
      rendered[:80])
check("هیچ {} باقی نماند", "{" not in rendered, rendered)

SENT.clear()
M.handle_callback(cb(S, "ptx_reset"))
check("بازگردانی پیش‌فرض", "پیش‌فرض" in " ".join(texts()))
check("متن برگشت", "{amount}" in database.get_setting("pay_txt_card_intro"))


print("\n[۸] 💳 ویزارد رویداد — انتخاب روش پرداخت")
SENT.clear()
M.handle_callback(cb(S, "ev_new"))
M.handle_callback(cb(S, "ev_go"))
flow = [("t", "کارگاه پرداختی"), ("t", "توضیح"), ("c", "evt_workshop"),
        ("c", "evl_physical"), ("t", "تهران"), ("t", "1404/09/01"),
        ("t", "17:00"), ("t", "120"), ("t", "50"), ("c", "evpay_1"),
        ("t", "200000")]
for k, v in flow:
    if k == "c":
        M.handle_callback(cb(S, v))
    else:
        M.process_message(msg(S, v))

check("🐛 مرحله نحوه پرداخت رسید", "پرداخت" in last(), last()[:60])
pl = kbl()
check("💳 کارت به کارت هست", any("کارت به کارت" in x for x in pl), str(pl))
check("🏦 کیف پول هست", any("کیف پول" in x for x in pl))
check("🔗 درگاه سفارشی هست", any("درگاه سفارشی" in x for x in pl))
check("تعداد کارت نمایش داده شد", any("کارت)" in x for x in pl), str(pl))

M.handle_callback(cb(S, "paym_card"))
d = auth.get_state_data(S)
check("🐛 روش کارت انتخاب شد", d.get("payment_method") == "card", str(d)[:120])
check("card_id ذخیره شد", bool(d.get("payment_card_id")))
check("تأیید دستی", d.get("payment_verification") == "manual")
check("رفت مرحله بعد", "دسترسی" in last(), last()[:50])

M.handle_callback(cb(S, "evp_public"))
M.handle_callback(cb(S, "evf_done"))
M.process_message(msg(S, "10"))
M.process_message(msg(S, "خط زندگی"))
M.process_message(msg(S, "⏭️ رد کردن"))
check("پیش‌نمایش", "پیش‌نمایش" in last(), last()[:50])
check("🐛 روش پرداخت در پیش‌نمایش", "کارت به کارت" in last(), last()[:400])

M.handle_callback(cb(S, "ev_save_publish"))
E = database.db_execute("SELECT * FROM events ORDER BY id DESC LIMIT 1",
                        fetch="one")
check("🐛 رویداد ذخیره شد", bool(E))
check("🐛 payment_method ذخیره شد", E and E["payment_method"] == "card",
      str(E and E.get("payment_method")))
check("🐛 payment_card_id ذخیره شد", E and E["payment_card_id"] == card["id"])
EID = E["id"] if E else None


print("\n[۹] 💳 جریان کامل کارت به کارت")
SENT.clear()
INVOICES.clear()
M.handle_callback(cb(U, f"ureg_{EID}"))
check("🐛 فاکتور نفرستاد (کارت به کارت است)", len(INVOICES) == 0,
      f"{len(INVOICES)} فاکتور!")
t = " ".join(to(U))
check("🐛 اطلاعات کارت نمایش داده شد", pay.format_card(VALID) in t, t[:200])
check("نام صاحب کارت", "علی محمدی" in t)
check("بانک", "ملی" in t)
check("درخواست رسید", "رسید" in t)
check("state رسید", auth.get_state_name(U) == pay.STATE_RECEIPT)

tx = database.db_execute(
    "SELECT * FROM transactions WHERE bale_user_id=? ORDER BY id DESC LIMIT 1",
    (U,), fetch="one")
check("تراکنش pending ثبت شد", tx and tx["status"] == "pending")

SENT.clear()
M.process_message(msg(U, "", photo=True))
check("🐛 رسید دریافت شد", "رسید شما دریافت" in " ".join(to(U)),
      " ".join(to(U))[:100])
rcp = database.db_execute(
    "SELECT * FROM payment_receipts ORDER BY id DESC LIMIT 1", fetch="one")
check("رسید در دیتابیس", bool(rcp))
check("وضعیت pending", rcp and rcp["status"] == "pending")
check("کد پیگیری دارد", rcp and rcp["ref_code"].startswith("R"))
check("🐛 ادمین خبردار شد", any("رسید جدید" in x for x in to(S)))

SENT.clear()
M.handle_callback(cb(S, "pay_receipts"))
check("لیست رسیدها", "رسید" in " ".join(texts()))

SENT.clear()
M.handle_callback(cb(S, f"rcpok_{rcp['id']}"))
r2 = database.db_execute("SELECT * FROM payment_receipts WHERE id=?",
                         (rcp["id"],), fetch="one")
check("🐛 رسید تأیید شد", r2 and r2["status"] == "approved")
tx2 = database.db_execute("SELECT * FROM transactions WHERE id=?",
                          (rcp["transaction_id"],), fetch="one")
check("تراکنش paid شد", tx2 and tx2["status"] == "paid")
reg = database.db_execute(
    "SELECT * FROM event_registrations WHERE event_id=? AND bale_user_id=?",
    (EID, U), fetch="one")
check("🐛 ثبت‌نام confirmed", reg and reg["status"] == "confirmed")
check("🎫 بلیت صادر شد", reg and bool(reg["ticket_code"]))
check("مبلغ ثبت شد", reg and reg["amount_paid"] == 200000)
check("پیام تأیید به کاربر", any("تأیید" in x for x in to(U)))


print("\n[۱۰] ❌ رد رسید با دلیل")
U2 = 666222
database.db_execute("""INSERT INTO users(bale_user_id,first_name,mobile,
    is_authenticated,profile_status,referral_code)
    VALUES(?,?,?,1,'approved',?)""", (U2, "نگار", "09127776655", f"N{U2}"))
SENT.clear()
M.handle_callback(cb(U2, f"ureg_{EID}"))
M.process_message(msg(U2, "", photo=True))
rcp2 = database.db_execute(
    "SELECT * FROM payment_receipts WHERE bale_user_id=? ORDER BY id DESC LIMIT 1",
    (U2,), fetch="one")
check("رسید دوم ثبت شد", bool(rcp2))

SENT.clear()
M.handle_callback(cb(S, f"rcpno_{rcp2['id']}"))
check("درخواست دلیل", "دلیل" in last())
M.process_message(msg(S, "مبلغ کمتر از حد است"))
r3 = database.db_execute("SELECT * FROM payment_receipts WHERE id=?",
                         (rcp2["id"],), fetch="one")
check("🐛 رسید رد شد", r3 and r3["status"] == "rejected")
check("دلیل ذخیره شد", r3 and "مبلغ کمتر" in (r3.get("reject_reason") or ""))
check("🐛 دلیل به کاربر رسید", any("مبلغ کمتر" in x for x in to(U2)))


print("\n[۱۱] 🏦 رویداد با کیف پول بله")
eid2 = database.db_execute("""INSERT INTO events
    (title,event_type,location_type,start_date,status,is_paid,price,
     payment_method,payment_verification,require_profile,has_ticket,created_by)
    VALUES ('وبینار کیف پول','webinar','online','1404/10/01','published',
            1,150000,'bale_wallet','auto',0,1,?)""", (S,))
SENT.clear()
INVOICES.clear()
M.handle_callback(cb(U, f"ureg_{eid2}"))
check("🐛 فاکتور کیف پول ارسال شد", len(INVOICES) == 1, f"{len(INVOICES)}")
if INVOICES:
    check("مبلغ درست", INVOICES[0]["prices"][0]["amount"] == 150000)
    pl2 = INVOICES[0]["payload"]
    M.process_update({"update_id": 1, "pre_checkout_query": {
        "id": "p1", "from": {"id": U}, "total_amount": 150000,
        "invoice_payload": pl2}})
    SENT.clear()
    M.process_update({"update_id": 2, "message": {
        "message_id": 50, "from": {"id": U}, "chat": {"id": U, "type": "private"},
        "successful_payment": {"currency": "IRR", "total_amount": 150000,
                               "invoice_payload": pl2,
                               "telegram_payment_charge_id": "C9",
                               "provider_payment_charge_id": "P9"}}})
    r4 = database.db_execute(
        "SELECT * FROM event_registrations WHERE event_id=? AND bale_user_id=?",
        (eid2, U), fetch="one")
    check("🐛 پرداخت کیف پول → confirmed", r4 and r4["status"] == "confirmed")
    check("بلیت صادر شد", r4 and bool(r4["ticket_code"]))


print("\n[۱۲] 🔗 رویداد با درگاه سفارشی")
eid3 = database.db_execute("""INSERT INTO events
    (title,event_type,location_type,start_date,status,is_paid,price,
     payment_method,payment_gateway_id,payment_verification,
     require_profile,created_by)
    VALUES ('همایش درگاه','conference','physical','1404/11/01','published',
            1,300000,'custom_gateway',?,'auto',0,?)""", (gw["id"], S))
SENT.clear()
INVOICES.clear()
M.handle_callback(cb(U, f"ureg_{eid3}"))
check("🐛 فاکتور کیف پول نفرستاد", len(INVOICES) == 0)
t3 = " ".join(to(U))
check("🐛 لینک درگاه نمایش داده شد", "زرین‌پال" in t3 or "پرداخت" in t3,
      t3[:120])
lastkb = [c for c in SENT if c["m"] == "sendMessage"][-1].get("kb") or {}
urls = [b.get("url") for r in lastkb.get("inline_keyboard", [])
        for b in r if b.get("url")]
check("دکمه لینک پرداخت", any("example.com" in (u or "") for u in urls),
      str(urls))


print("\n[۱۳] ❌ رویداد رایگان — بدون پرداخت")
eid4 = database.db_execute("""INSERT INTO events
    (title,event_type,location_type,start_date,status,is_paid,
     payment_method,require_profile,created_by)
    VALUES ('جلسه رایگان','meeting','online','1404/12/01','published',
            0,'none',0,?)""", (S,))
SENT.clear()
INVOICES.clear()
U3 = 666333
database.db_execute("""INSERT INTO users(bale_user_id,first_name,mobile,
    is_authenticated,profile_status,referral_code)
    VALUES(?,?,?,1,'approved',?)""", (U3, "حسین", "09125554433", f"N{U3}"))
M.handle_callback(cb(U3, f"ureg_{eid4}"))
check("🐛 رایگان → بدون فاکتور", len(INVOICES) == 0)
r5 = database.db_execute(
    "SELECT * FROM event_registrations WHERE event_id=? AND bale_user_id=?",
    (eid4, U3), fetch="one")
check("🐛 مستقیم confirmed", r5 and r5["status"] == "confirmed")


print("\n[۱۴] 💳 صفحه تنظیمات پرداخت")
SENT.clear()
M.handle_callback(cb(S, "set_payment"))
# فاز ۱۳: عنوان به «پرداخت و مالی» تغییر کرد (مالی زیرمجموعه شد)
check("صفحه روش‌های پرداخت", "پرداخت" in last(), last()[:60])
check("فاز۱۳: مالی زیرمجموعه پرداخت شد",
      any("درآمد" in x or "تراکنش" in x for x in kbl()), str(kbl()))
check("وضعیت کارت", "کارت به کارت" in last())
check("وضعیت کیف پول", "کیف پول" in last())
check("وضعیت درگاه", "درگاه" in last())
check("آمار مالی", "تراکنش موفق" in last())
pkb = kbl()
for e in ["کارت‌های بانکی", "کیف پول", "درگاه‌های سفارشی",
          "متن‌های پرداخت", "تراکنش"]:
    check(f"دکمه {e}", any(e in x for x in pkb), str(pkb)[:120])

SENT.clear()
M.handle_callback(cb(S, "pay_wallet"))
check("اطلاعات کیف پول", "کیف پول" in last())
check("محافظت‌ها نمایش", "سقف" in last() or "آزمایشی" in last())


print("\n[۱۵] 🛡️ امنیت")
for d, w in [("pay_cards", "دسترسی"), ("card_add", "دسترسی"),
             ("pay_gateways", "دسترسی"), ("gw_add", "دسترسی"),
             ("pay_texts", "دسترسی"), ("um_admins", "دسترسی"),
             ("um_add", "دسترسی"), ("pay_receipts", "دسترسی"),
             (f"rcpok_1", "دسترسی")]:
    SENT.clear()
    M.handle_callback(cb(U, d))
    check(f"🔒 کاربر عادی: {d}", w in last(), last()[:40])


print("\n[۱۶] پایداری")
weird = [
    {"update_id": 40, "callback_query": {"id": "x", "from": {"id": S},
     "data": "card_view_abc", "message": {"chat": {"id": S}}}},
    {"update_id": 41, "callback_query": {"id": "x", "from": {"id": S},
     "data": "gw_del_9999", "message": {"chat": {"id": S}}}},
    {"update_id": 42, "callback_query": {"id": "x", "from": {"id": S},
     "data": "ptx_nonexistent", "message": {"chat": {"id": S}}}},
    {"update_id": 43, "callback_query": {"id": "x", "from": {"id": S},
     "data": "rcpok_9999", "message": {"chat": {"id": S}}}},
    {"update_id": 44, "callback_query": {"id": "x", "from": {"id": S},
     "data": "paycard_abc", "message": {"chat": {"id": S}}}},
    {"update_id": 45, "callback_query": {"id": "x", "from": {"id": U},
     "data": "paym_card", "message": {"chat": {"id": U}}}},
]
crash = 0
for w in weird:
    try:
        M.process_update(w)
    except Exception as e:
        crash += 1
        print(f"      💥 {e}")
check("هیچ کرشی نیست", crash == 0, f"{crash}")


print("\n[۱۷] همه دکمه‌ها پاسخ می‌دهند")
import re  # noqa: E402
src = "".join(Path(ROOT, f).read_text(encoding="utf-8")
              for f in ["bale_api.py", "events.py", "admin.py", "payments.py",
                        "settings_admin.py", "attendance.py", "profile.py"])
statics = {c for c in re.findall(r'"callback_data":\s*"([^"{]+)"', src)}
statics.discard("noop")
silent = []
for c in sorted(statics):
    auth.clear_state(S)
    SENT.clear()
    try:
        M.handle_callback(cb(S, c))
        if not SENT:
            silent.append(c)
    except Exception as e:
        silent.append(f"{c}({str(e)[:30]})")
check(f"🐛 همه {len(statics)} دکمه پاسخ دادند", not silent, str(silent[:5]))


print("\n" + "=" * 62)
print(f"✅ موفق: {len(PASS)}    ❌ ناموفق: {len(FAIL)}")
print("=" * 62)
if FAIL:
    print("\nناموفق:")
    for n, d in FAIL:
        print(f"  ❌ {n}   {d}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۸ پاس شدند!")
sys.exit(0)
