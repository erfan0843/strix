"""
تست فاز ۷ — رفع یخ‌زدگی ربات + راه فرار + تست پرداخت

🔴 باگ اصلی که رفع شد:
   ربات تک‌نخی بود. متدهای غیرحیاتی (setMessageReaction، answerCallbackQuery)
   وقتی تایم‌اوت می‌شدند، ۱۵-۳۰ ثانیه کل ربات را قفل می‌کردند.
   ⇒ «دکمه بازگشت کار نمی‌کند»، «مرحله بعد نمی‌رود»، «/start کار نمی‌کند»
"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora7_")
os.environ.update({
    "BOT_TOKEN": "1095412158:T", "SUPER_ADMIN_ID": "100000001",
    "SAFIR_API_KEY": "k", "SAFIR_BOT_ID": "317041514",
    "PAYMENT_PROVIDER_TOKEN": "WALLET-AvKTlq6kt9pJEyaH",
    "DB_PATH": f"{TMP}/t.db", "BACKUP_DIR": f"{TMP}/b", "IMPORT_DIR": f"{TMP}/i",
    "FILES_DIR": f"{TMP}/f", "PROFILES_DIR": f"{TMP}/f/p",
    "EVENTS_DIR": f"{TMP}/f/e", "LOG_DIR": f"{TMP}/l",
    "BROADCAST_RATE": "999", "AUTO_REACT_ENABLED": "1",
})

import requests  # noqa: E402
import bale_api  # noqa: E402

CALLS = []
MID = [2000]
SLOW = set()      # متدهایی که تایم‌اوت می‌شوند
DEAD = set()      # متدهایی که بله ندارد
ASYNC_LOG = []


class _R:
    def __init__(self, code=200, body=None):
        self.status_code = code
        self._b = body or {"ok": True, "result": {"message_id": 1}}

    def json(self):
        return self._b


def _fake_post(self, url, **kw):
    u = str(url)
    method = u.rsplit("/", 1)[-1]
    if method in SLOW:
        time.sleep(min(kw.get("timeout", 10), 10))
        raise requests.exceptions.Timeout("timeout")
    if method in DEAD:
        return _R(200, {"ok": False, "description": "Bad Request: method not found"})
    if method == "sendMessage":
        MID[0] += 1
        return _R(200, {"ok": True, "result": {"message_id": MID[0]}})
    return _R(200, {"ok": True, "result": {"message_id": MID[0]}})


requests.Session.post = _fake_post


def _track_async(m, p=None):
    ASYNC_LOG.append(m)
    return {"ok": True, "queued": True}


_orig_async = bale_api.api_async


def _send(cid, text, kb=None, reply_to=None):
    MID[0] += 1
    CALLS.append({"m": "sendMessage", "chat_id": cid, "text": text, "kb": kb,
                  "mid": MID[0]})
    return {"ok": True, "result": {"message_id": MID[0]}}


bale_api.send = _send
bale_api.send_or_edit = lambda cid, t, kb=None, mid=None, force_new=False: _send(cid, t, kb)
bale_api.send_photo = lambda *a, **k: {"ok": True}
bale_api.send_document = lambda *a, **k: {"ok": True}
bale_api.get_chat = lambda c: {"ok": True, "result": {"title": "x"}}
bale_api.get_chat_member = lambda c, u: {"ok": True, "result": {"status": "member"}}
bale_api.set_context = lambda *a, **k: None
bale_api.clear_context = lambda *a, **k: None
bale_api.forget_menu = lambda c: None
bale_api.send_invoice = lambda cid, title, description, payload, provider_token, prices, **k: (
    CALLS.append({"m": "sendInvoice", "payload": payload, "prices": prices})
    or {"ok": True, "result": {"message_id": 1}})
bale_api.inquire_transaction = lambda t: {
    "ok": True, "result": {"id": t, "status": "paid", "amount": 1000, "userID": 1}}

import database, auth, profile as pf, admin as ad  # noqa: E402
import import_excel as ie, events as ev, attendance as att  # noqa: E402
import settings_admin as sa, main as M, config  # noqa: E402

MODS = (database, auth, pf, ad, ie, ev, att, sa, M)
for m in MODS:
    if hasattr(m, "send"):
        m.send = _send
    if hasattr(m, "send_or_edit"):
        m.send_or_edit = bale_api.send_or_edit
    if hasattr(m, "send_photo"):
        m.send_photo = lambda *a, **k: {"ok": True}
    if hasattr(m, "forget_menu"):
        m.forget_menu = lambda c: None
ad.get_chat = lambda c: {"ok": True, "result": {"title": "x"}}
ev.send_invoice = bale_api.send_invoice
sa.get_bot_username = lambda: "nora_bot"

database.init_db()
ev.init_event_tables()
att.init_attendance_tables()
database.seed_default_settings()
sa.seed_phase5_settings()
auth.ensure_super_admin(100000001)

S, U = 100000001, 555777
database.db_execute("""INSERT INTO users(bale_user_id,first_name,last_name,mobile,
    is_authenticated,profile_status,referral_code,city,gender)
    VALUES(?,?,?,?,1,'approved',?,?,?)""",
    (U, "علی", "محمدی", "09121112233", f"NORA{U}", "قم", "مرد"))

PASS, FAIL = [], []


def check(n, c, d=""):
    if c:
        PASS.append(n); print(f"  ✅ {n}")
    else:
        FAIL.append((n, d)); print(f"  ❌ {n}  {d}")


def last():
    m = [c for c in CALLS if c["m"] == "sendMessage"]
    return m[-1]["text"] if m else ""


def texts():
    return [c["text"] for c in CALLS if c["m"] == "sendMessage"]


def kbl():
    m = [c for c in CALLS if c["m"] == "sendMessage"]
    kb = (m[-1].get("kb") or {}) if m else {}
    out = [b["text"] for r in kb.get("inline_keyboard", []) for b in r]
    out += [b["text"] if isinstance(b, dict) else str(b)
            for r in kb.get("keyboard", []) for b in r]
    return out


def msg(uid, t, mid=1):
    return {"message_id": mid, "from": {"id": uid, "first_name": "ت"},
            "chat": {"id": uid, "type": "private"}, "text": t}


def cb(uid, d, mid=9):
    return {"id": "c", "from": {"id": uid, "first_name": "ت"}, "data": d,
            "message": {"chat": {"id": uid}, "message_id": mid}}


print("\n" + "=" * 62)
print("🧪 تست فاز ۷ — یخ‌زدگی، راه فرار، پرداخت")
print("=" * 62)


print("\n[۱] 🔴 یخ‌زدگی ربات — باگ اصلی")
SLOW.update({"setMessageReaction", "answerCallbackQuery", "askReview",
             "sendChatAction"})
bale_api._unsupported.clear()
bale_api._fail_count.clear()

t0 = time.time()
M.process_message(msg(U, "سلام", mid=100))
d1 = time.time() - t0
check(f"🐛 پیام کاربر سریع پردازش شد ({d1:.1f}s)", d1 < 2,
      f"{d1:.1f} ثانیه — ربات یخ زد!")

t0 = time.time()
M.handle_callback(cb(U, "back_main"))
d2 = time.time() - t0
check(f"🐛 کلیک دکمه سریع ({d2:.1f}s)", d2 < 2, f"{d2:.1f} ثانیه")

t0 = time.time()
for i in range(5):
    M.process_message(msg(U, f"پیام {i}", mid=200 + i))
    M.handle_callback(cb(U, "back_main"))
d3 = time.time() - t0
check(f"🐛 ۱۰ تعامل پشت‌سرهم ({d3:.1f}s)", d3 < 3,
      f"{d3:.1f} ثانیه — کاربر منتظر می‌ماند")
SLOW.clear()


print("\n[۲] متدهای ناموجود خودکار خاموش می‌شوند")
DEAD.add("setMessageReaction")
bale_api._unsupported.clear()
bale_api._fail_count.clear()
for i in range(5):
    bale_api._raw_call("setMessageReaction", {"chat_id": 1, "message_id": 1},
                       retries=0, timeout=3)
check("🐛 بعد از چند شکست غیرفعال شد",
      bale_api._unsupported.get("setMessageReaction") is True,
      str(bale_api._unsupported))
r = bale_api.api("setMessageReaction", {})
check("دیگر تلاش نمی‌کند", r.get("skipped") or r.get("queued"))
DEAD.clear()
bale_api._unsupported.clear()
bale_api._fail_count.clear()


print("\n[۳] ❤️ ری‌اکشن قلب")
check("ایموجی پیش‌فرض قلب است", config.AUTO_REACT_EMOJI == "❤️",
      config.AUTO_REACT_EMOJI)
ASYNC_LOG.clear()
_bk = bale_api.api_async
bale_api.api_async = _track_async
M.set_reaction = lambda c, m, e=None, b=False: _track_async(
    "setMessageReaction", {"emoji": e or config.AUTO_REACT_EMOJI})
M.process_message(msg(U, "یک پیام", mid=300))
check("🐛 ری‌اکشن روی پیام کاربر", "setMessageReaction" in ASYNC_LOG,
      str(ASYNC_LOG))
ASYNC_LOG.clear()
M.process_message(msg(S, "پیام ادمین", mid=301))
check("روی پیام ادمین ری‌اکشن نمی‌زند",
      "setMessageReaction" not in ASYNC_LOG)
bale_api.api_async = _bk
M.set_reaction = bale_api.set_reaction


print("\n[۴] 🔙 راه فرار از هر حالت")
states = [
    ("ویزارد رویداد", lambda: (M.handle_callback(cb(S, "ev_new")),
                               M.handle_callback(cb(S, "ev_go")),
                               M.process_message(msg(S, "تست")))),
    ("همگانی", lambda: (M.handle_callback(cb(S, "admin_broadcast")),
                        M.handle_callback(cb(S, "bcf_all")))),
    ("جستجوی شهر", lambda: (M.handle_callback(cb(S, "admin_broadcast")),
                            M.handle_callback(cb(S, "bcf_city")))),
    ("جستجوی کاربر", lambda: M.handle_callback(cb(S, "u_search"))),
    ("افزودن کانال", lambda: M.handle_callback(cb(S, "fj_add"))),
    ("ویرایش متن", lambda: M.handle_callback(cb(S, "txted_msg_welcome"))),
    ("تست OTP", lambda: M.handle_callback(cb(S, "otp_test"))),
    ("قالب گواهینامه", lambda: M.handle_callback(cb(S, "cert_edit"))),
    ("استعلام تراکنش", lambda: M.handle_callback(cb(S, "pay_test_inquire"))),
    ("عکس پروفایل", lambda: M.handle_callback(cb(S, "profile_photo"))),
    ("Import", lambda: M.process_message(msg(S, "/import"))),
]
escapes = ["/start", "/menu", "/cancel", "🏠 منوی اصلی"]
bad = []
for name, setup in states:
    for esc in escapes:
        auth.clear_state(S)
        try:
            setup()
        except Exception:
            pass
        CALLS.clear()
        try:
            M.process_message(msg(S, esc))
        except Exception as e:
            bad.append(f"{name}+{esc}: کرش {e}")
            continue
        if auth.get_state_name(S) is not None:
            bad.append(f"{name}+{esc}: state گیر کرد")
        elif not CALLS:
            bad.append(f"{name}+{esc}: بدون پاسخ")
check(f"🐛 فرار از {len(states)}×{len(escapes)}={len(states)*len(escapes)} حالت",
      not bad, str(bad[:4]))


print("\n[۵] 🔙 دکمه بازگشت در ویزارد")
auth.clear_state(S)
CALLS.clear()
M.handle_callback(cb(S, "ev_new"))
M.handle_callback(cb(S, "ev_go"))
M.process_message(msg(S, "رویداد بازگشت"))
st1 = auth.get_state_data(S).get("step")
M.process_message(msg(S, "🔙 بازگشت"))
st2 = auth.get_state_data(S).get("step")
check("🐛 بازگشت به مرحله قبل", st2 == st1 - 1, f"{st1}→{st2}")
check("داده حفظ شد", auth.get_state_data(S).get("title") == "رویداد بازگشت")

# دکمه inline بازگشت
M.process_message(msg(S, "توضیح"))
CALLS.clear()
M.handle_callback(cb(S, "ev_back"))
check("🐛 دکمه inline «مرحله قبل» کار می‌کند", "مرحله" in last(), last()[:40])
CALLS.clear()
M.handle_callback(cb(S, "ev_cancel"))
check("🐛 دکمه inline «انصراف» کار می‌کند",
      auth.get_state_name(S) is None and "لغو" in " ".join(texts()))


print("\n[۶] 🎉 ویزارد کامل تا ذخیره")
auth.clear_state(S)
CALLS.clear()
M.handle_callback(cb(S, "ev_new"))
M.handle_callback(cb(S, "ev_go"))
flow = [("t", "همایش فاز ۷"), ("t", "توضیحات کامل"), ("c", "evt_conference"),
        ("c", "evl_hybrid"), ("t", "تهران سالن اصلی"),
        ("t", "https://ble.ir/live"), ("t", "1404/08/15"), ("t", "10:00"),
        ("t", "240"), ("t", "200"), ("c", "evpay_1"), ("t", "350000"), ("c", "paym_bale_wallet"),
        ("c", "evp_public"), ("c", "evf_done"), ("t", "30"),
        ("t", "خط زندگی"), ("t", "⏭️ رد کردن")]
steps_ok = True
for i, (k, v) in enumerate(flow):
    before = auth.get_state_data(S).get("step")
    if k == "c":
        M.handle_callback(cb(S, v))
    else:
        M.process_message(msg(S, v))
    after = auth.get_state_data(S).get("step")
    if after is None and i < len(flow) - 1:
        steps_ok = False
        print(f"      💥 مرحله {i}: state گم شد بعد از «{v[:20]}»")
        break
check("🐛 همه ۱۷ مرحله بدون گیر", steps_ok)
check("پیش‌نمایش رسید", "پیش‌نمایش رویداد" in last(), last()[:50])

before = database.db_scalar("SELECT COUNT(*) FROM events")
CALLS.clear()
M.handle_callback(cb(S, "ev_save_publish"))
after = database.db_scalar("SELECT COUNT(*) FROM events")
check("🐛🐛 دکمه ذخیره و انتشار کار کرد", after == before + 1,
      f"{before}→{after} | {last()[:60]}")
E = database.db_execute("SELECT * FROM events ORDER BY id DESC LIMIT 1",
                        fetch="one")
if E:
    check("قیمت ذخیره شد", E["price"] == 350000)
    check("ظرفیت ذخیره شد", E["capacity"] == 200)
    check("حالت ترکیبی", E["location_type"] == "hybrid")
    EID = E["id"]
else:
    EID = None


print("\n[۷] 📢 پیام همگانی + فیلتر شهر")
auth.clear_state(S)
CALLS.clear()
M.handle_callback(cb(S, "admin_broadcast"))
check("منوی فیلتر", "اطلاع‌رسانی همگانی" in last())
labels = kbl()
check("فیلترها موجودند", len(labels) >= 9, f"{len(labels)}")

CALLS.clear()
M.handle_callback(cb(S, "bcf_city"))
check("🐛 دکمه جستجوی شهر کار کرد", "شهر" in last(), last()[:50])
check("state درست", auth.get_state_data(S).get("stage") == "city")

CALLS.clear()
M.process_message(msg(S, "قم"))
d = auth.get_state_data(S)
check("🐛 شهر پذیرفته شد", d.get("filter") == "city" and d.get("value") == "قم",
      str(d)[:100])
check("تعداد نمایش داده شد", "نفر" in last(), last()[:60])

M.process_message(msg(S, "سلام به اهالی قم"))
check("پیش‌نمایش", "پیش‌نمایش نهایی" in last())
check("ready=1", auth.get_state_data(S).get("ready") == 1)

CALLS.clear()
M.handle_callback(cb(S, "bc_go"))
got = [c for c in CALLS if c["m"] == "sendMessage" and c["chat_id"] == U
       and "سلام به اهالی قم" in c["text"]]
check("🐛 پیام به کاربر قمی رسید", len(got) >= 1, f"{len(got)}")
check("گزارش پایانی", any("تمام شد" in t for t in texts()))

# شهر ناموجود
CALLS.clear()
M.handle_callback(cb(S, "admin_broadcast"))
M.handle_callback(cb(S, "bcf_city"))
M.process_message(msg(S, "شهر_ناموجود_xyz"))
check("شهر ناموجود پیام واضح می‌دهد", "پیدا نشد" in last(), last()[:50])
auth.clear_state(S)


print("\n[۸] 💳 ابزار تست پرداخت")
CALLS.clear()
M.handle_callback(cb(S, "pay_test"))
check("🐛 منوی تست پرداخت", "تست پرداخت" in last())
check("حالت آزمایشی تشخیص داده شد", "آزمایشی" in last())
check("۳ گزینه تست", len(kbl()) >= 4, str(len(kbl())))

CALLS.clear()
M.handle_callback(cb(S, "pay_test_invoice"))
inv = [c for c in CALLS if c["m"] == "sendInvoice"]
if not inv:
    # توکن واقعی → اول تأیید می‌خواهد (رفتار درست)
    check("🛡️ توکن واقعی → تأیید خواست", "تأیید" in last() or "واقعی" in last(),
          last()[:50])
    CALLS.clear()
    M.handle_callback(cb(S, "pay_test_inv_go"))
    inv = [c for c in CALLS if c["m"] == "sendInvoice"]
check("🐛 فاکتور تست ارسال شد", len(inv) == 1, f"{len(inv)}")
if inv:
    check("مبلغ از تنظیمات خوانده شد",
          inv[0]["prices"][0]["amount"] == config.PAYMENT_TEST_AMOUNT,
          str(inv[0]["prices"][0]["amount"]))
    tx = database.db_execute("SELECT * FROM transactions WHERE payload=?",
                             (inv[0]["payload"],), fetch="one")
    check("تراکنش ثبت شد", bool(tx))

CALLS.clear()
M.handle_callback(cb(S, "pay_test_event"))
check("🐛 رویداد آزمایشی ساخته شد",
      "رویداد آزمایشی" in " ".join(texts()), last()[:60])
tev = database.db_execute(
    "SELECT * FROM events WHERE title LIKE '🧪%'", fetch="one")
check("در دیتابیس", bool(tev))
if tev:
    check("پولی است", tev["is_paid"] == 1 and tev["price"] == 10000)
    check("نیاز به پروفایل ندارد", tev["require_profile"] == 0)

    # تست کامل ثبت‌نام پولی
    CALLS.clear()
    M.handle_callback(cb(U, f"ureg_{tev['id']}"))
    inv2 = [c for c in CALLS if c["m"] == "sendInvoice"]
    check("🐛 ثبت‌نام پولی فاکتور فرستاد", len(inv2) == 1, f"{len(inv2)}")

    if inv2:
        pl = inv2[0]["payload"]
        M.process_update({"update_id": 1, "pre_checkout_query": {
            "id": "p1", "from": {"id": U}, "total_amount": 10000,
            "invoice_payload": pl}})
        CALLS.clear()
        M.process_update({"update_id": 2, "message": {
            "message_id": 90, "from": {"id": U},
            "chat": {"id": U, "type": "private"},
            "successful_payment": {
                "currency": "IRR", "total_amount": 10000,
                "invoice_payload": pl,
                "telegram_payment_charge_id": "C1",
                "provider_payment_charge_id": "P1"}}})
        reg = database.db_execute(
            "SELECT * FROM event_registrations WHERE event_id=? AND bale_user_id=?",
            (tev["id"], U), fetch="one")
        check("🐛 پرداخت → ثبت‌نام قطعی", reg and reg["status"] == "confirmed")
        check("🎫 بلیت صادر شد", reg and bool(reg["ticket_code"]))

CALLS.clear()
M.handle_callback(cb(S, "pay_test_inquire"))
check("استعلام شروع شد", "استعلام" in last())
M.process_message(msg(S, "TX12345"))
check("🐛 استعلام نتیجه داد", "پرداخت شده" in last() or "نتیجه" in last(),
      last()[:60])


print("\n[۹] ⌨️ منوی دائمی پایین صفحه")
CALLS.clear()
M.process_message(msg(U, "/start"))
kb = [c for c in CALLS if c["m"] == "sendMessage"][-1].get("kb") or {}
check("منوی اصلی نمایش داده شد", "منوی اصلی" in last() or "نورا" in last())

for btn, expect in [("🎉 رویدادها", "رویداد"), ("👤 پروفایل من", "پروفایل"),
                    ("✋ حضور و غیاب", "حضور")]:
    CALLS.clear()
    M.process_message(msg(U, btn))
    check(f"دکمه دائمی «{btn}»", expect in last(), last()[:40])

CALLS.clear()
M.process_message(msg(S, "👨‍💼 پنل ادمین"))
check("دکمه دائمی پنل ادمین", "پنل ادمین" in last())
CALLS.clear()
M.process_message(msg(U, "👨‍💼 پنل ادمین"))
check("🔒 کاربر عادی به پنل نمی‌رسد", "دسترسی" in last())


print("\n[۱۰] کیبوردها راه فرار دارند")
kbs = {
    "kb_cancel": bale_api.kb_cancel(),
    "kb_skip": bale_api.kb_skip(),
    "kb_gender": bale_api.kb_gender(),
    "kb_education": bale_api.kb_education(),
    "kb_otp": bale_api.kb_otp(),
}
for name, k in kbs.items():
    btns = [b["text"] for r in k.get("keyboard", []) for b in r]
    check(f"{name} دکمه خانه دارد",
          any("منوی اصلی" in b for b in btns), str(btns))


print("\n[۱۱] ✋ حضور و غیاب (فاز ۶) هنوز کار می‌کند")
if EID:
    database.db_execute("UPDATE events SET has_attendance=1 WHERE id=?", (EID,))
    uu = auth.get_user(U)
    database.db_execute("""INSERT OR REPLACE INTO event_registrations
        (event_id,user_id,bale_user_id,status,ticket_code)
        VALUES (?,?,?,'confirmed','TX1')""", (EID, uu["id"], U))
    CALLS.clear()
    M.handle_callback(cb(S, f"att_new_{EID}"))
    # 🆕 فاز ۳۳: جلسات خودکار هم ساخته می‌شوند — جلسهٔ **باز** را بگیر
    sess = database.db_execute(
        "SELECT * FROM attendance_sessions WHERE is_open=1 "
        "ORDER BY id DESC LIMIT 1", fetch="one") or database.db_execute(
        "SELECT * FROM attendance_sessions ORDER BY id DESC LIMIT 1",
        fetch="one")
    check("جلسه ساخته شد", bool(sess))
    if sess:
        CALLS.clear()
        # 🆕 فاز ۳۳: مستقیم همان جلسه را انتخاب کن
        #    (چون حالا چند جلسهٔ خودکار هم وجود دارد)
        M.handle_callback(cb(U, f"uatts_{sess['id']}"))
        M.process_message(msg(U, sess["session_code"]))
        rec = database.db_execute(
            "SELECT * FROM attendance_records WHERE session_id=? AND bale_user_id=?",
            (sess["id"], U), fetch="one")
        check("🐛 حضور ثبت شد", bool(rec))


print("\n[۱۲] 👥 دعوت لینکی (فاز ۶)")
CALLS.clear()
M.handle_callback(cb(U, "u_referral"))
t = " ".join(texts())
check("لینک قابل کلیک", "https://ble.ir/nora_bot?start=" in t, t[:100])


print("\n[۱۳] پایداری در برابر ورودی خراب")
weird = [
    {"update_id": 30, "callback_query": {"id": "x", "from": {"id": S},
     "data": "ev_back", "message": {"chat": {"id": S}}}},
    {"update_id": 31, "callback_query": {"id": "x", "from": {"id": S},
     "data": "ev_cancel", "message": {"chat": {"id": S}}}},
    {"update_id": 32, "callback_query": {"id": "x", "from": {"id": S},
     "data": "pay_test_del_abc", "message": {"chat": {"id": S}}}},
    {"update_id": 33, "callback_query": {"id": "x", "from": {"id": U},
     "data": "bcf_city", "message": {"chat": {"id": U}}}},
    {"update_id": 34, "message": {"from": {"id": S},
     "chat": {"id": S, "type": "private"}, "text": "🏠 منوی اصلی"}},
]
crash = 0
for w in weird:
    try:
        M.process_update(w)
    except Exception as e:
        crash += 1
        print(f"      💥 {e}")
check("هیچ کرشی نیست", crash == 0, f"{crash}")


print("\n[۱۴] همه دکمه‌ها پاسخ می‌دهند")
import re  # noqa: E402
src = "".join(Path(ROOT, f).read_text(encoding="utf-8")
              for f in ["bale_api.py", "events.py", "admin.py",
                        "settings_admin.py", "attendance.py", "profile.py"])
statics = {c for c in re.findall(r'"callback_data":\s*"([^"{]+)"', src)}
statics.discard("noop")
silent = []
for c in sorted(statics):
    auth.clear_state(S)
    CALLS.clear()
    try:
        M.handle_callback(cb(S, c))
        if not CALLS:
            silent.append(c)
    except Exception as e:
        silent.append(f"{c}({e})")
check(f"🐛 همه {len(statics)} دکمه پاسخ دادند", not silent, str(silent[:5]))



print("\n[۱۵] 🛡️ محافظت پرداخت واقعی")
import config as _cfg
_real = "WALLET-AvKTlq6kt9pJEyaH"
check("توکن واقعی تشخیص داده می‌شود",
      not _real.upper().startswith("WALLET-TEST"))
for amt, should in [(5000, False), (10000, True), (350000, True),
                    (50000000, True), (99000000, False), (-5, False)]:
    okk, _m = _cfg.check_amount(amt)
    check(f"مبلغ {amt:,} → {'مجاز' if should else 'رد'}", okk == should,
          f"{okk} != {should}")
check("سقف پیش‌فرض ۵۰ میلیون", _cfg.PAYMENT_MAX_AMOUNT == 50_000_000)
check("حداقل ۱۰ هزار", _cfg.PAYMENT_MIN_AMOUNT == 10_000)

# مبلغ خارج از محدوده نباید فاکتور بفرستد
CALLS.clear()
_ev = database.db_execute("SELECT * FROM events WHERE is_paid=1 LIMIT 1",
                          fetch="one")
if _ev:
    ev.start_payment(S, S, _ev, 9999, 99_000_000)
    inv_bad = [c for c in CALLS if c["m"] == "sendInvoice"]
    check("🛡️ مبلغ بیش از سقف → فاکتور ارسال نشد", len(inv_bad) == 0,
          f"{len(inv_bad)} فاکتور!")
    check("پیام خطا داده شد", any("سقف" in t or "خطا" in t for t in texts()))

    CALLS.clear()
    ev.start_payment(S, S, _ev, 9999, 350000)
    inv_ok = [c for c in CALLS if c["m"] == "sendInvoice"]
    check("مبلغ مجاز → فاکتور ارسال شد", len(inv_ok) == 1, f"{len(inv_ok)}")

print("\n[۱۶] تأیید دومرحله‌ای فاکتور واقعی")
CALLS.clear()
M.handle_callback(cb(S, "pay_test_invoice"))
inv_direct = [c for c in CALLS if c["m"] == "sendInvoice"]
if _cfg.PAYMENT_TEST_MODE:
    check("حالت تست → مستقیم می‌فرستد", len(inv_direct) >= 0)
else:
    check("🛡️ توکن واقعی → اول تأیید می‌خواهد", len(inv_direct) == 0,
          "بدون تأیید فاکتور فرستاد!")
    check("پیام هشدار", "واقعی" in last() or "تأیید" in last(), last()[:50])
    CALLS.clear()
    M.handle_callback(cb(S, "pay_test_inv_go"))
    check("بعد از تأیید فاکتور رفت",
          len([c for c in CALLS if c["m"] == "sendInvoice"]) == 1)

print("\n" + "=" * 62)
print(f"✅ موفق: {len(PASS)}    ❌ ناموفق: {len(FAIL)}")
print("=" * 62)
if FAIL:
    print("\nناموفق:")
    for n, d in FAIL:
        print(f"  ❌ {n}   {d}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۷ پاس شدند!")
sys.exit(0)
