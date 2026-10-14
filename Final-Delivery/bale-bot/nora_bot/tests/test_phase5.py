"""
تست کامل فاز ۵ — رویدادها، پرداخت، OTP سفیر، لایک خودکار، متن‌های داینامیک

اجرا:
    cd nora_bot
    py tests/test_phase5.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora5_")
os.environ.update({
    "BOT_TOKEN": "1095412158:TEST_TOKEN_FOR_UNITTEST",
    "SUPER_ADMIN_ID": "100000001",
    "SAFIR_API_KEY": "3tViTIlQy9WTutRL",
    "SAFIR_BOT_ID": "317041514",
    "PAYMENT_PROVIDER_TOKEN": "WALLET-TEST-1111111111111111",
    "DB_PATH": str(Path(TMP) / "t.db"),
    "BACKUP_DIR": str(Path(TMP) / "backups"),
    "IMPORT_DIR": str(Path(TMP) / "imports"),
    "FILES_DIR": str(Path(TMP) / "files"),
    "PROFILES_DIR": str(Path(TMP) / "files/profiles"),
    "EVENTS_DIR": str(Path(TMP) / "files/events"),
    "LOG_DIR": str(Path(TMP) / "logs"),
    "BROADCAST_RATE": "1000",
    "AUTO_REACT_ENABLED": "1",
})

import bale_api  # noqa: E402

SENT, REACTIONS, INVOICES, SAFIR_CALLS, PRECHECKOUT = [], [], [], [], []


def _mock_api(method, params=None, **kw):
    p = params or {}
    SENT.append({"method": method, "params": p})
    if method == "getMe":
        return {"ok": True, "result": {"username": "nora_bot", "first_name": "نورا"}}
    if method == "getChatMember":
        return {"ok": True, "result": {"status": "member"}}
    if method == "getChat":
        return {"ok": True, "result": {"title": "کانال تست", "username": "test_ch"}}
    if method == "setMessageReaction":
        REACTIONS.append(p)
        return {"ok": True, "result": True}
    if method == "sendInvoice":
        INVOICES.append(p)
        return {"ok": True, "result": {"message_id": len(SENT)}}
    if method == "answerPreCheckoutQuery":
        PRECHECKOUT.append(p)
        return {"ok": True, "result": True}
    if method == "inquireTransaction":
        return {"ok": True, "result": {"id": p.get("transaction_id"), "status": "paid",
                                       "amount": 500000, "userID": 555}}
    return {"ok": True, "result": {"message_id": len(SENT)}}


def _mock_send(cid, text, kb=None, reply_to=None):
    SENT.append({"method": "sendMessage",
                 "params": {"chat_id": cid, "text": text, "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT)}}


bale_api.api = _mock_api
bale_api.send = _mock_send

# --- mock کردن send_or_edit (فاز ۶: ویرایش در جا) ---
def _mock_send_or_edit(cid, text, kb=None, mid=None, force_new=False):
    return _mock_send(cid, text, kb)
bale_api.send_or_edit = _mock_send_or_edit
bale_api.forget_menu = lambda c: None
bale_api.set_context = lambda *a, **k: None
bale_api.clear_context = lambda *a, **k: None
bale_api.remember_menu = lambda c, r: None

bale_api.send_photo = lambda *a, **k: {"ok": True}
bale_api.send_document = lambda *a, **k: {"ok": True}
bale_api.answer_callback = lambda *a, **k: {"ok": True}
bale_api.get_chat = lambda c: _mock_api("getChat")
bale_api.get_chat_member = lambda c, u: _mock_api("getChatMember")
bale_api.set_reaction = lambda c, m, e=None, b=False: _mock_api(
    "setMessageReaction", {"chat_id": c, "message_id": m,
                           "reaction": [{"type": "emoji", "emoji": e or "❤️"}]})
bale_api.ask_review = lambda u, d=5: {"ok": True}
bale_api.send_invoice = lambda cid, title, description, payload, provider_token, prices, **k: \
    _mock_api("sendInvoice", {"chat_id": cid, "title": title, "payload": payload,
                              "provider_token": provider_token, "prices": prices})
bale_api.answer_pre_checkout_query = lambda q, ok=True, err=None: _mock_api(
    "answerPreCheckoutQuery", {"pre_checkout_query_id": q, "ok": ok, "error_message": err})
bale_api.inquire_transaction = lambda t: _mock_api("inquireTransaction",
                                                   {"transaction_id": t})

import database, auth, profile as profile_mod, admin as admin_mod  # noqa: E402
import import_excel as imp_mod, events as ev_mod  # noqa: E402
import settings_admin as set_mod, main as main_mod, config  # noqa: E402
import payments as pay_mod  # noqa: E402

for m in (database, auth, profile_mod, admin_mod, imp_mod, ev_mod,
          set_mod, pay_mod, main_mod):
    if hasattr(m, "send"):
        m.send = _mock_send
    if hasattr(m, "send_or_edit"):
        m.send_or_edit = _mock_send_or_edit
    if hasattr(m, "forget_menu"):
        m.forget_menu = lambda c: None
for m in (profile_mod, ev_mod, admin_mod):
    if hasattr(m, "send_photo"):
        m.send_photo = lambda *a, **k: {"ok": True}
ev_mod.send_invoice = bale_api.send_invoice
ev_mod.answer_pre_checkout_query = bale_api.answer_pre_checkout_query
ev_mod.inquire_transaction = bale_api.inquire_transaction
admin_mod.send_document = lambda *a, **k: {"ok": True}
admin_mod.get_chat = lambda c: _mock_api("getChat")
main_mod.set_reaction = bale_api.set_reaction


# mock سفیر
import requests as _rq  # noqa: E402


class _Resp:
    def __init__(self, code=200, body=None):
        self.status_code = code
        self._b = body or {}
        self.text = json.dumps(self._b)

    def json(self):
        return self._b


_SAFIR_OK = True


def _mock_post(url, json=None, headers=None, timeout=None, **kw):
    if "safir" in str(url):
        SAFIR_CALLS.append({"url": url, "body": json, "headers": headers})
        if _SAFIR_OK:
            return _Resp(200, {"message_id": "abc-123", "error_data": None})
        return _Resp(401, {"error_data": "invalid api-access-key"})
    return _Resp(200, {"ok": True})


auth.requests.post = _mock_post

SUPER = 100000001
USER = 555444333
USER2 = 555444444

PASS, FAIL = [], []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  ✅ {name}")
    else:
        FAIL.append((name, detail))
        print(f"  ❌ {name}  {detail}")


def last_text(n=1):
    m = [s for s in SENT if s["method"] == "sendMessage"]
    return m[-n]["params"]["text"] if len(m) >= n else ""


def last_kb():
    m = [s for s in SENT if s["method"] == "sendMessage"]
    return (m[-1]["params"].get("kb") or {}) if m else {}


def kb_labels():
    kb = last_kb()
    return [b["text"] for row in kb.get("inline_keyboard", []) for b in row]


def all_texts():
    return [s["params"]["text"] for s in SENT if s["method"] == "sendMessage"]


def texts_to(cid):
    return [s["params"]["text"] for s in SENT
            if s["method"] == "sendMessage" and s["params"].get("chat_id") == cid]


def msg(uid, text, mid=100, chat_id=None, ctype="private"):
    return {"message_id": mid, "from": {"id": uid, "first_name": "تست"},
            "chat": {"id": chat_id or uid, "type": ctype}, "text": text}


def cb(uid, data):
    return {"id": "cb1", "from": {"id": uid, "first_name": "تست"}, "data": data,
            "message": {"chat": {"id": uid}, "message_id": 1}}


print("\n" + "=" * 62)
print("🧪 تست فاز ۵ — ربات نورا 5.0")
print("=" * 62)

print("\n[۱] راه‌اندازی")
database.init_db()
ev_mod.init_event_tables()
pay_mod.init_payment_tables()
database.seed_default_settings()
set_mod.seed_phase5_settings()
auth.ensure_super_admin(SUPER, "سوپرادمین")
tables = [t["name"] for t in database.db_execute(
    "SELECT name FROM sqlite_master WHERE type='table'", fetch="all")]
check("جدول events", "events" in tables)
check("جدول event_registrations", "event_registrations" in tables)
check("جدول transactions", "transactions" in tables)
check("جدول settings", "settings" in tables)
check("سوپرادمین ثبت شد", bool(auth.get_user(SUPER)))


print("\n[۲] 🔑 تنظیمات OTP سفیر (باگ گزارش‌شده)")
check("SAFIR_BOT_ID از env خوانده شد", config.SAFIR_BOT_ID == 317041514,
      f"={config.SAFIR_BOT_ID}")
check("bot_id اصلی جدا شناسایی شد", config.MAIN_BOT_ID == 1095412158,
      f"={config.MAIN_BOT_ID}")
check("🐛 bot_id سفیر ≠ bot_id اصلی", config.SAFIR_BOT_ID != config.MAIN_BOT_ID)
check("سفیر فعال است", config.SAFIR_ENABLED)
check("فرمت شماره بین‌الملل", auth.to_intl_phone("09120000000") == "989120000000")
check("فرمت با +98", auth.to_intl_phone("+989120000000") == "989120000000")

SAFIR_CALLS.clear()
res = auth.send_otp_via_safir("09120000000", "123456")
check("ارسال OTP موفق", res.get("ok"), str(res))
check("درخواست به سفیر رفت", len(SAFIR_CALLS) >= 1)

body = SAFIR_CALLS[0]["body"]
hdr = SAFIR_CALLS[0]["headers"]
print(f"    payload: {json.dumps(body, ensure_ascii=False)}")
check("🐛 bot_id درست ارسال شد", body.get("bot_id") == 317041514, str(body.get("bot_id")))
check("🐛 phone_number فرمت درست", body.get("phone_number") == "989120000000")
check("otp در جای درست", body.get("message_data", {}).get("otp_message", {}).get("otp") == "123456")
check("هدر api-access-key", hdr.get("api-access-key") == "3tViTIlQy9WTutRL")
check("URL سفیر درست", "safir.bale.ai/api/v3/send_message" in SAFIR_CALLS[0]["url"])

# تست fallback بدون request_id
_SAFIR_OK = False
SAFIR_CALLS.clear()
res_fail = auth.send_otp_via_safir("09120000000", "999999")
check("خطای سفیر درست تشخیص داده شد", not res_fail.get("ok"))
check("راهنمای خطا داده شد", bool(res_fail.get("hint")), str(res_fail))
_SAFIR_OK = True

info = auth.test_safir_connection()
check("تابع تشخیص وضعیت کار می‌کند", info["enabled"] and not info["same_as_main"])


print("\n[۳] 👍 لایک خودکار روی پیام کاربر")
# کاربر احراز شده بسازیم
main_mod.handle_start(msg(USER, "/start"))
main_mod.handle_callback(cb(USER, "auth_otp"))
main_mod.handle_phone_otp(msg(USER, "09121112233"))
row = database.db_execute(
    "SELECT code FROM otp_codes WHERE bale_user_id=? ORDER BY id DESC LIMIT 1",
    (USER,), fetch="one")
main_mod.handle_otp(msg(USER, row["code"]))
check("کاربر احراز شد", auth.get_user(USER)["is_authenticated"] == 1)

REACTIONS.clear()
main_mod.process_message(msg(USER, "سلام خوبی؟", mid=555))
check("🐛 روی پیام کاربر عادی لایک خورد", len(REACTIONS) == 1, str(REACTIONS))
if REACTIONS:
    r = REACTIONS[0]
    check("ری‌اکشن روی message_id درست", r.get("message_id") == 555)
    check("ایموجی ❤️", r.get("reaction", [{}])[0].get("emoji") == "❤️",
          str(r.get("reaction")))
    check("فرمت استاندارد ReactionType", r.get("reaction", [{}])[0].get("type") == "emoji")

REACTIONS.clear()
main_mod.process_message(msg(SUPER, "سلام", mid=556))
check("🐛 روی پیام ادمین لایک نخورد", len(REACTIONS) == 0, str(REACTIONS))

REACTIONS.clear()
main_mod.process_message(msg(USER, "/help", mid=557))
check("روی دستور هم لایک می‌خورد", len(REACTIONS) == 1)

REACTIONS.clear()
main_mod.process_message(msg(USER, "پیام گروه", mid=558, chat_id=-100999, ctype="group"))
check("در گروه لایک نمی‌خورد", len(REACTIONS) == 0)


print("\n[۴] 🎉 ساخت رویداد (ویزارد ۱۷ مرحله‌ای)")
SENT.clear()
main_mod.handle_callback(cb(SUPER, "ev_new"))
check("ویزارد شروع شد", "ساخت رویداد جدید" in last_text())
main_mod.handle_callback(cb(SUPER, "ev_go"))
check("مرحله ۱: عنوان", "عنوان رویداد" in last_text())

main_mod.process_message(msg(SUPER, "کارگاه مهارت‌های زندگی"))
main_mod.process_message(msg(SUPER, "کارگاه دو روزه با حضور اساتید برجسته"))
check("مرحله نوع رویداد", "نوع رویداد" in last_text())
check("۸ نوع رویداد + دکمه‌های ناوبری",
      len([x for x in kb_labels() if "انصراف" not in x and "مرحله قبل" not in x]) == 8,
      str(kb_labels()))

main_mod.handle_callback(cb(SUPER, "evt_workshop"))
check("مرحله نحوه برگزاری", "نحوه برگزاری" in last_text())
main_mod.handle_callback(cb(SUPER, "evl_online"))
check("🐛 آدرس برای آنلاین رد شد", "لینک ورود" in last_text(), last_text()[:80])

main_mod.process_message(msg(SUPER, "https://ble.ir/join/workshop123"))
check("مرحله تاریخ", "تاریخ شروع" in last_text())
main_mod.process_message(msg(SUPER, "سلام"))
check("تاریخ غلط رد شد", "تاریخ نامعتبر" in last_text())
main_mod.process_message(msg(SUPER, "1404/06/15"))
main_mod.process_message(msg(SUPER, "25:99"))
check("ساعت غلط رد شد", "ساعت نامعتبر" in last_text())
main_mod.process_message(msg(SUPER, "18:30"))
main_mod.process_message(msg(SUPER, "120"))
main_mod.process_message(msg(SUPER, "3"))     # ظرفیت ۳ برای تست لیست انتظار
check("مرحله پولی/رایگان", "پولی است" in last_text())

main_mod.handle_callback(cb(SUPER, "evpay_1"))
check("مرحله مبلغ", "مبلغ" in last_text())
main_mod.process_message(msg(SUPER, "500"))
check("مبلغ خیلی کم رد شد", "حداقل" in last_text())
main_mod.process_message(msg(SUPER, "500000"))
check("💳 مرحله نحوه پرداخت", "پرداخت" in last_text(), last_text()[:60])
paylabels = kb_labels()
check("۳ روش پرداخت نمایش داده شد",
      sum(1 for x in paylabels
          if any(k in x for k in ("کارت", "کیف پول", "درگاه"))) == 3,
      str(paylabels))
main_mod.handle_callback(cb(SUPER, "paym_bale_wallet"))
check("مرحله دسترسی", "دسترسی" in last_text(), last_text()[:60])

main_mod.handle_callback(cb(SUPER, "evp_public"))
check("مرحله قابلیت‌ها", "قابلیت‌های رویداد" in last_text())
labels = kb_labels()
check("پیش‌فرض هوشمند کارگاه: گواهینامه روشن",
      any("✅" in l and "گواهینامه" in l for l in labels), str(labels))
check("پیش‌فرض حضور و غیاب روشن",
      any("✅" in l and "حضور" in l for l in labels))

main_mod.handle_callback(cb(SUPER, "evf_has_survey"))
check("تاگل نظرسنجی کار کرد",
      any("✅" in l and "نظرسنجی" in l for l in kb_labels()))
main_mod.handle_callback(cb(SUPER, "evf_done"))
main_mod.process_message(msg(SUPER, "20"))               # امتیاز
main_mod.process_message(msg(SUPER, "گروه خط زندگی"))    # برگزارکننده
main_mod.process_message(msg(SUPER, "⏭️ رد کردن"))       # پوستر
# اگر مرحله‌ای باقی مانده، رد کن تا پیش‌نمایش برسد
for _ in range(3):
    if "پیش‌نمایش" in last_text():
        break
    main_mod.process_message(msg(SUPER, "⏭️ رد کردن"))  # پوستر

prev = last_text()
print("\n----- پیش‌نمایش رویداد -----")
print(prev[:600])
print("----------------------------\n")
check("پیش‌نمایش نمایش داده شد", "پیش‌نمایش رویداد" in prev)
check("عنوان در پیش‌نمایش", "کارگاه مهارت‌های زندگی" in prev)
check("قیمت در پیش‌نمایش", "500٬000" in prev or "500,000" in prev, prev[:200])
check("ظرفیت در پیش‌نمایش", "ظرفیت" in prev)
check("امتیاز در پیش‌نمایش", "20 امتیاز" in prev)

main_mod.handle_callback(cb(SUPER, "ev_save_publish"))
check("رویداد ذخیره شد", "ذخیره شد" in last_text())
EV = database.db_execute("SELECT * FROM events ORDER BY id DESC LIMIT 1", fetch="one")
check("در دیتابیس ثبت شد", bool(EV))
check("وضعیت published", EV["status"] == "published")
check("🐛 همه فیلدها ذخیره شدند",
      EV["title"] == "کارگاه مهارت‌های زندگی" and EV["price"] == 500000
      and EV["capacity"] == 3 and EV["points_reward"] == 20
      and EV["has_certificate"] == 1 and EV["has_survey"] == 1,
      f"price={EV['price']} cap={EV['capacity']} pts={EV['points_reward']}")
check("لینک آنلاین ذخیره شد", EV["online_link"] == "https://ble.ir/join/workshop123")
EID = EV["id"]


print("\n[۵] نمای کاربر و کنترل پروفایل")
SENT.clear()
main_mod.handle_callback(cb(USER, "u_events"))
check("لیست رویدادها", "رویدادهای فعال" in last_text())
check("رویداد در لیست", "کارگاه مهارت" in last_text())

main_mod.handle_callback(cb(USER, f"uev_{EID}"))
detail = last_text()
check("جزئیات رویداد", "کارگاه مهارت‌های زندگی" in detail)
check("🐛 لینک آنلاین قبل ثبت‌نام مخفی است",
      "ble.ir/join/workshop123" not in detail, "لینک لو رفت!")
check("دکمه ثبت‌نام پولی", any("ثبت‌نام" in l for l in kb_labels()))

SENT.clear()
main_mod.handle_callback(cb(USER, f"ureg_{EID}"))
check("🐛 بدون پروفایل تأییدشده اجازه نمی‌دهد", "پروفایل" in last_text())

# پروفایل را تأیید کنیم
database.db_execute(
    "UPDATE users SET profile_status='approved', first_name='علی', last_name='محمدی' "
    "WHERE bale_user_id=?", (USER,))


print("\n[۶] 💳 پرداخت کیف پول بله")
SENT.clear()
INVOICES.clear()
main_mod.handle_callback(cb(USER, f"ureg_{EID}"))
check("درخواست پرداخت ارسال شد", len(INVOICES) == 1, str(len(INVOICES)))
inv = INVOICES[0] if INVOICES else {}
check("مبلغ درست در invoice", inv.get("prices", [{}])[0].get("amount") == 500000)
check("provider_token ارسال شد",
      inv.get("provider_token") == "WALLET-TEST-1111111111111111")
check("payload یکتا ساخته شد", bool(inv.get("payload")))

reg = database.db_execute(
    "SELECT * FROM event_registrations WHERE event_id=? AND bale_user_id=?",
    (EID, USER), fetch="one")
check("ثبت‌نام pending شد", reg and reg["status"] == "pending")
tx = database.db_execute("SELECT * FROM transactions WHERE payload=?",
                         (inv.get("payload"),), fetch="one")
check("تراکنش ثبت شد", bool(tx))
check("تراکنش pending", tx and tx["status"] == "pending")

# --- PreCheckout ---
PRECHECKOUT.clear()
main_mod.process_update({"update_id": 1, "pre_checkout_query": {
    "id": "pcq1", "from": {"id": USER}, "currency": "IRR",
    "total_amount": 500000, "invoice_payload": inv["payload"]}})
check("🐛 pre_checkout تأیید شد", PRECHECKOUT and PRECHECKOUT[0]["ok"] is True,
      str(PRECHECKOUT))

# مبلغ دستکاری‌شده باید رد شود
PRECHECKOUT.clear()
main_mod.process_update({"update_id": 2, "pre_checkout_query": {
    "id": "pcq2", "from": {"id": USER}, "currency": "IRR",
    "total_amount": 1000, "invoice_payload": inv["payload"]}})
check("🔒 مبلغ دستکاری‌شده رد شد",
      PRECHECKOUT and PRECHECKOUT[0]["ok"] is False, str(PRECHECKOUT))

# payload جعلی
PRECHECKOUT.clear()
main_mod.process_update({"update_id": 3, "pre_checkout_query": {
    "id": "pcq3", "from": {"id": USER}, "total_amount": 500000,
    "invoice_payload": "fake_payload_xyz"}})
check("🔒 payload جعلی رد شد", PRECHECKOUT and PRECHECKOUT[0]["ok"] is False)

# --- پرداخت موفق ---
SENT.clear()
main_mod.process_update({"update_id": 4, "message": {
    "message_id": 900, "from": {"id": USER}, "chat": {"id": USER, "type": "private"},
    "successful_payment": {
        "currency": "IRR", "total_amount": 500000,
        "invoice_payload": inv["payload"],
        "telegram_payment_charge_id": "CHG123",
        "provider_payment_charge_id": "PRV456"}}})

tx2 = database.db_execute("SELECT * FROM transactions WHERE payload=?",
                          (inv["payload"],), fetch="one")
check("🐛 تراکنش paid شد", tx2 and tx2["status"] == "paid")
check("شماره پیگیری ذخیره شد", tx2 and tx2["provider_charge_id"] == "PRV456")

reg2 = database.db_execute(
    "SELECT * FROM event_registrations WHERE event_id=? AND bale_user_id=?",
    (EID, USER), fetch="one")
check("🐛 ثبت‌نام confirmed شد", reg2 and reg2["status"] == "confirmed")
check("مبلغ پرداختی ثبت شد", reg2 and reg2["amount_paid"] == 500000)
check("🎫 بلیت صادر شد", reg2 and bool(reg2["ticket_code"]))
txts = " ".join(all_texts())
check("پیام پرداخت موفق", "پرداخت موفق" in txts)
check("🔗 لینک ورود بعد از پرداخت داده شد", "ble.ir/join/workshop123" in txts)

# پرداخت تکراری
SENT.clear()
main_mod.process_update({"update_id": 5, "message": {
    "message_id": 901, "from": {"id": USER}, "chat": {"id": USER, "type": "private"},
    "successful_payment": {"total_amount": 500000, "invoice_payload": inv["payload"],
                           "telegram_payment_charge_id": "CHG123",
                           "provider_payment_charge_id": "PRV456"}}})
check("🔒 پرداخت تکراری ثبت نشد", "قبلاً ثبت" in last_text())


print("\n[۷] 🎫 بلیت")
SENT.clear()
main_mod.handle_callback(cb(USER, f"uticket_{EID}"))
t = last_text()
check("بلیت نمایش داده شد", "بلیت ورود" in t)
check("نام روی بلیت", "علی" in t)
check("کد بلیت روی بلیت", reg2["ticket_code"] in t)
check("لینک روی بلیت", "ble.ir/join" in t)
check("دکمه کپی کد بلیت", any("کپی" in l for l in kb_labels()))


print("\n[۸] ظرفیت و لیست انتظار")
# دو کاربر دیگر بسازیم تا ظرفیت ۳ پر شود
for i, u in enumerate([USER2, 555444555]):
    database.db_execute("""INSERT INTO users
        (bale_user_id, first_name, last_name, mobile, is_authenticated,
         profile_status, referral_code)
        VALUES (?,?,?,?,1,'approved',?)""",
        (u, f"کاربر{i}", "تست", f"0912999888{i}", f"R{u}"))
    database.db_execute("""INSERT INTO event_registrations
        (event_id, user_id, bale_user_id, status, ticket_code)
        VALUES (?,(SELECT id FROM users WHERE bale_user_id=?),?,'confirmed',?)""",
        (EID, u, u, f"T{u}"))

ev_now = ev_mod.get_event(EID)
check("ظرفیت پر شد", ev_mod.is_full(ev_now),
      f"{ev_mod.reg_count(EID,'confirmed')}/{ev_now['capacity']}")

U4 = 555444666
database.db_execute("""INSERT INTO users
    (bale_user_id, first_name, mobile, is_authenticated, profile_status, referral_code)
    VALUES (?,?,?,1,'approved',?)""", (U4, "چهارم", "09129998884", f"R{U4}"))
SENT.clear()
main_mod.handle_callback(cb(U4, f"ureg_{EID}"))
check("🐛 وقتی پر است → لیست انتظار", "لیست انتظار" in last_text())
w = database.db_execute(
    "SELECT status FROM event_registrations WHERE event_id=? AND bale_user_id=?",
    (EID, U4), fetch="one")
check("وضعیت waitlist", w and w["status"] == "waitlist")

# لغو یکی → ارتقای لیست انتظار
SENT.clear()
main_mod.handle_callback(cb(USER2, f"ucancel_{EID}"))
check("لغو انجام شد", any("لغو شد" in t for t in all_texts()), str(all_texts()[:2]))
w2 = database.db_execute(
    "SELECT status FROM event_registrations WHERE event_id=? AND bale_user_id=?",
    (EID, U4), fetch="one")
check("🐛 نفر لیست انتظار ارتقا یافت (پولی→pending)",
      w2 and w2["status"] == "pending", str(w2))


print("\n[۹] رویداد رایگان + تأیید دستی")
SENT.clear()
eid2 = database.db_execute("""INSERT INTO events
    (title, event_type, location_type, start_date, status, is_paid,
     require_approval, require_profile, has_ticket, points_reward, created_by)
    VALUES ('جلسه هفتگی','meeting','physical','1404/07/01','published',0,1,0,1,5,?)""",
    (SUPER,))
main_mod.handle_callback(cb(USER, f"ureg_{eid2}"))
check("رویداد نیازمند تأیید → pending", "در انتظار تأیید" in last_text()
      or "درخواست شما ثبت" in last_text(), last_text()[:80])
r3 = database.db_execute(
    "SELECT * FROM event_registrations WHERE event_id=? AND bale_user_id=?",
    (eid2, USER), fetch="one")
check("ثبت‌نام pending", r3 and r3["status"] == "pending")

SENT.clear()
main_mod.handle_callback(cb(SUPER, f"regok_{r3['id']}"))
r4 = database.db_execute("SELECT * FROM event_registrations WHERE id=?",
                         (r3["id"],), fetch="one")
check("🐛 بعد تأیید ادمین confirmed شد", r4 and r4["status"] == "confirmed")
check("بلیت صادر شد", bool(r4["ticket_code"]))

# اتمام رویداد → امتیازدهی
before = auth.get_user(USER)["total_points"] or 0
main_mod.handle_callback(cb(SUPER, f"ev_finish_{eid2}"))
after = auth.get_user(USER)["total_points"] or 0
check("🏆 امتیاز بعد اتمام رویداد داده شد", after == before + 5,
      f"{before}→{after}")


print("\n[۱۰] کد دعوت و رویداد خصوصی")
eid3 = database.db_execute("""INSERT INTO events
    (title, event_type, location_type, start_date, status, privacy,
     invite_code, is_paid, require_profile, created_by)
    VALUES ('نشست ویژه','expert','online','1404/08/01','published','code','EVSECRET',0,0,?)""",
    (SUPER,))
SENT.clear()
main_mod.handle_callback(cb(USER, "u_events"))
check("🔒 رویداد کددار در لیست عمومی نیست", "نشست ویژه" not in last_text())

SENT.clear()
ev_mod.register_by_code(USER, USER, "EVSECRET")
check("🔑 با کد دعوت پیدا شد", "نشست ویژه" in " ".join(all_texts()))

SENT.clear()
ev_mod.register_by_code(USER, USER, "WRONGCODE")
check("کد اشتباه رد شد", "نامعتبر" in last_text())

# VIP
eid4 = database.db_execute("""INSERT INTO events
    (title, event_type, location_type, start_date, status, privacy, is_paid, created_by)
    VALUES ('رویداد VIP','conference','online','1404/09/01','published','vip',0,?)""",
    (SUPER,))
SENT.clear()
main_mod.handle_callback(cb(USER, "u_events"))
check("⭐ رویداد VIP برای کاربر عادی مخفی است", "رویداد VIP" not in last_text())
database.db_execute("UPDATE users SET is_vip=1 WHERE bale_user_id=?", (USER,))
SENT.clear()
main_mod.handle_callback(cb(USER, "u_events"))
check("⭐ رویداد VIP برای کاربر VIP دیده می‌شود", "رویداد VIP" in last_text())
database.db_execute("UPDATE users SET is_vip=0 WHERE bale_user_id=?", (USER,))


print("\n[۱۱] deep link")
SENT.clear()
U5 = 555444777
main_mod.process_message(msg(U5, "/start EVSECRET"))
check("deep link برای کاربر جدید ذخیره شد",
      (auth.get_state_data(U5) or {}).get("deep") == "EVSECRET")
auth.clear_state(U5)


print("\n[۱۲] گزارش و خروجی رویداد")
SENT.clear()
main_mod.handle_callback(cb(SUPER, f"ev_report_{EID}"))
rep = last_text()
check("گزارش تولید شد", "گزارش" in rep)
check("آمار ثبت‌نام", "تأیید شده" in rep)
check("درآمد در گزارش", "درآمد" in rep)
check("نرخ حضور", "نرخ حضور" in rep)

SENT.clear()
main_mod.handle_callback(cb(SUPER, f"ev_regs_{EID}_0"))
check("لیست ثبت‌نام‌ها", "ثبت‌نام‌های" in last_text())

try:
    import openpyxl  # noqa: F401
    SENT.clear()
    main_mod.handle_callback(cb(SUPER, f"ev_export_{EID}"))
    files = list(Path(TMP, "imports").glob("event_*.xlsx"))
    check("📤 خروجی اکسل رویداد ساخته شد", len(files) >= 1)
except ImportError:
    print("  ⚠️ openpyxl نصب نیست")


print("\n[۱۳] 📢 اطلاع‌رسانی")
SENT.clear()
main_mod.handle_callback(cb(SUPER, f"ev_notify_{EID}"))
check("تأیید اطلاع‌رسانی خواسته شد", "اطلاع‌رسانی رویداد" in last_text())
SENT.clear()
main_mod.handle_callback(cb(SUPER, f"ev_notifygo_{EID}"))
check("اطلاع‌رسانی انجام شد", "اطلاع‌رسانی تمام شد" in " ".join(all_texts()))

SENT.clear()
main_mod.handle_callback(cb(SUPER, "admin_broadcast"))
check("همگانی شروع شد", "اطلاع‌رسانی همگانی" in last_text())
main_mod.process_message(msg(SUPER, "سلام به همه اعضای گروه"))
check("پیش‌نمایش همگانی", "پیش‌نمایش" in last_text())
SENT.clear()
main_mod.handle_callback(cb(SUPER, "bc_go"))
check("ارسال همگانی انجام شد", "اطلاع‌رسانی تمام شد" in " ".join(all_texts()))


print("\n[۱۴] 📝 متن‌های داینامیک")
SENT.clear()
main_mod.handle_callback(cb(SUPER, "admin_settings"))
check("پنل تنظیمات", "تنظیمات ربات" in last_text())
main_mod.handle_callback(cb(SUPER, "set_texts"))
check("مدیریت متن‌ها", "مدیریت متن" in last_text())
main_mod.handle_callback(cb(SUPER, "txtcat_0"))
check("دسته متن‌ها", len(kb_labels()) > 1)

main_mod.handle_callback(cb(SUPER, "txted_msg_welcome"))
check("ویرایش متن شروع شد", "ویرایش" in last_text())
main_mod.process_message(msg(SUPER, "🌟 سلام! به خانواده خط زندگی خوش آمدید"))
check("متن ذخیره شد", database.get_setting("msg_welcome").startswith("🌟"))

SENT.clear()
U6 = 555444888
main_mod.handle_start(msg(U6, "/start"))
check("🐛 متن جدید در خوش‌آمد نمایش داده شد",
      "خانواده خط زندگی" in last_text(), last_text()[:80])


print("\n[۱۵] تنظیمات OTP و پرداخت در پنل")
SENT.clear()
main_mod.handle_callback(cb(SUPER, "set_otp"))
o = last_text()
check("صفحه تنظیمات OTP", "رمز یکبار مصرف" in o)
check("bot_id نمایش داده شد", "317041514" in o)
check("وضعیت فعال", "✅ فعال" in o)

SENT.clear()
main_mod.handle_callback(cb(SUPER, "otp_test"))
check("تست OTP شروع شد", "تست ارسال" in last_text())
SAFIR_CALLS.clear()
main_mod.process_message(msg(SUPER, "09120000000"))
check("تست OTP ارسال شد", len(SAFIR_CALLS) >= 1)
check("نتیجه تست نمایش داده شد", "نتیجه تست" in last_text())
check("bot_id در نتیجه", "317041514" in last_text())

SENT.clear()
main_mod.handle_callback(cb(SUPER, "set_payment"))
p = last_text()
check("صفحه پرداخت", "پرداخت" in p, p[:60])
check("حالت پرداخت نمایش داده شد",
      "آزمایشی" in p or "واقعی" in p or "کیف پول" in p, p[:80])
check("آمار تراکنش", "موفق" in p)

SENT.clear()
main_mod.handle_callback(cb(SUPER, "tx_list"))
check("لیست تراکنش‌ها", "تراکنش" in last_text())


print("\n[۱۶] بخش‌های کاربر")
for data, expect in [("u_support", "پشتیبانی"), ("u_faq", "سوالات متداول"),
                     ("u_referral", "دعوت از دوستان"), ("u_points", "امتیاز و رتبه"),
                     ("u_notifications", "اعلان"), ("u_myevents", "رویدادهای من")]:
    SENT.clear()
    main_mod.handle_callback(cb(USER, data))
    check(f"بخش {expect}", expect in last_text(), last_text()[:60])

SENT.clear()
main_mod.handle_callback(cb(USER, "u_contact"))
main_mod.process_message(msg(USER, "یک سوال دارم"))
check("پیام به ادمین رسید", any("پیام از کاربر" in t for t in texts_to(SUPER)))
# فاز ۱۷-ج: متن مهربان‌تر شد («دریافت شد» به‌جای «ارسال شد»)
check("تأیید به کاربر", "دریافت شد" in last_text()
      or "ارسال شد" in last_text(), last_text()[:60])


print("\n[۱۷] فاز ۴ — رگرسیون (باگ‌های قبلی برنگشته باشند)")
U7 = 555444999
database.db_execute("""INSERT INTO users
    (bale_user_id, first_name, mobile, is_authenticated, referral_code)
    VALUES (?,?,?,1,?)""", (U7, "رگرسیون", "09127777777", f"R{U7}"))
SENT.clear()
main_mod.handle_callback(cb(U7, "profile_fill"))
main_mod.handle_callback(cb(U7, "form_go"))
for a in ["حسن رضایی", "1234567891", "1370/05/12", "👨 مرد", "علی", "مریم",
          "قم", "قم", "خیابان امام", "1234567890", "کارشناسی", "حقوق",
          "دانشگاه قم", "وکیل", "دفتر", "h@x.com", "بیو تست"]:
    main_mod.process_message(msg(U7, a))
# 📸 فاز ۳۸ — مرحلهٔ عکس (رسانه‌ای) را رد کن
from bale_api import BTN_SKIP as _SKIP7
main_mod.process_message(msg(U7, _SKIP7))
prev7 = last_text()
check("🐛 باگ ۱ برنگشته: پیش‌نمایش پر است",
      "حسن" in prev7 and "1234567891" in prev7 and "❌ وارد نشده" not in prev7)

SENT.clear()
main_mod.handle_callback(cb(U7, "form_submit"))
adm = [t for t in texts_to(SUPER) if "درخواست تأیید پروفایل" in t]
check("🐛 باگ ۲ برنگشته: پیام ادمین پر است",
      adm and "حسن" in adm[-1] and "1234567891" in adm[-1], str(adm[-1][:100]) if adm else "")

sub = database.db_execute(
    "SELECT * FROM profile_submissions WHERE bale_user_id=? ORDER BY id DESC LIMIT 1",
    (U7,), fetch="one")
main_mod.handle_callback(cb(SUPER, f"sa_{sub['id']}"))
u7 = auth.get_user(U7)
check("🐛 ذخیره بعد تأیید کار می‌کند",
      u7["first_name"] == "حسن" and u7["national_id"] == "1234567891")


print("\n[۱۸] پایداری در برابر ورودی‌های خراب")
weird = [
    {"update_id": 10, "message": {"from": {"id": USER}, "chat": {"id": USER, "type": "private"}}},
    {"update_id": 11, "callback_query": {"id": "x", "from": {"id": USER},
                                         "data": "uev_abc", "message": {"chat": {"id": USER}}}},
    {"update_id": 12, "callback_query": {"id": "x", "from": {"id": USER},
                                         "data": "ev_regs_", "message": {"chat": {"id": USER}}}},
    {"update_id": 13, "callback_query": {"id": "x", "from": {"id": USER},
                                         "data": "upay_99999", "message": {"chat": {"id": USER}}}},
    {"update_id": 14, "pre_checkout_query": {"id": "p", "from": {"id": USER}}},
    {"update_id": 15, "message": {"from": {"id": USER}, "chat": {"id": USER, "type": "private"},
                                  "successful_payment": {"invoice_payload": "nope"}}},
    {"update_id": 16, "message": {"from": {"id": SUPER}, "chat": {"id": SUPER, "type": "private"},
                                  "text": "A" * 6000}},
    {"update_id": 17, "callback_query": {"id": "x", "from": {"id": USER},
                                         "data": "evt_", "message": {"chat": {"id": USER}}}},
]
crashed = 0
for w in weird:
    try:
        main_mod.process_update(w)
    except Exception as e:
        crashed += 1
        print(f"      💥 {e}")
check("هیچ ورودی خرابی ربات را نمی‌خواباند", crashed == 0, f"({crashed} کرش)")


print("\n[۱۹] امنیت")
SENT.clear()
main_mod.handle_callback(cb(USER, "ev_new"))
check("🔒 کاربر عادی رویداد نمی‌سازد", "ادمین" in last_text() or "دسترسی" in last_text())
SENT.clear()
main_mod.handle_callback(cb(USER, "admin_settings"))
check("🔒 کاربر عادی به تنظیمات نمی‌رسد", "دسترسی" in last_text())
SENT.clear()
main_mod.handle_callback(cb(USER, f"ev_delq_{EID}"))
check("🔒 کاربر عادی رویداد حذف نمی‌کند", "دسترسی" in last_text())
SENT.clear()
main_mod.handle_callback(cb(USER, "admin_broadcast"))
check("🔒 کاربر عادی همگانی نمی‌فرستد", "دسترسی" in last_text())

database.db_execute("UPDATE users SET is_blocked=1 WHERE bale_user_id=?", (USER,))
SENT.clear()
main_mod.process_message(msg(USER, "سلام", mid=700))
check("🚫 کاربر مسدود متوقف شد", "مسدود" in last_text())
database.db_execute("UPDATE users SET is_blocked=0 WHERE bale_user_id=?", (USER,))


print("\n[۲۰] حذف رویداد با تأیید")
SENT.clear()
main_mod.handle_callback(cb(SUPER, f"ev_delq_{eid4}"))
check("تأیید حذف خواسته شد", "قابل بازگشت نیست" in last_text())
check("هنوز حذف نشده", bool(ev_mod.get_event(eid4)))
main_mod.handle_callback(cb(SUPER, f"ev_dely_{eid4}"))
check("بعد تأیید حذف شد", ev_mod.get_event(eid4) is None)


print("\n" + "=" * 62)
print(f"✅ موفق: {len(PASS)}    ❌ ناموفق: {len(FAIL)}")
print("=" * 62)
if FAIL:
    print("\nموارد ناموفق:")
    for n, d in FAIL:
        print(f"  ❌ {n}   {d}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۵ پاس شدند!")
sys.exit(0)
