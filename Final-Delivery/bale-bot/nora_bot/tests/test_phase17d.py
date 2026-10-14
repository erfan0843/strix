"""
تست فاز ۱۷-د — 💱 «کلا ریالش کن»

🔴 باگ گزارش‌شده کاربر:
   «باز تو مالی و پرداخت ریال میزنه نمیتونی درستش کنی کلا ریالش کن»

🔍 ریشه باگ:
   .env کاربر CURRENCY_LABEL=ریال داشت، ولی کد INPUT_CURRENCY=toman
   بود؛ یعنی هر عدد موقع نمایش ÷۱۰ می‌شد ولی برچسب «ریال» می‌خورد و
   عدد کامل به درگاه می‌رفت → «یه صفر جلوی مبلغ».

✅ راه‌حل نهایی: حذف کامل لایه تبدیل. همه‌جا ریال.

این فایل مهم‌ترین ادعا را ثابت می‌کند:
   عددی که ادمین تایپ می‌کند
     == عددی که در دیتابیس می‌نشیند
     == عددی که کاربر می‌بیند
     == عددی که به درگاه بله می‌رود
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora17d_")
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
import auth  # noqa: E402
import profile as PR  # noqa: E402
import forms as F  # noqa: E402
import form_fill as FF  # noqa: E402
import payments as PAY  # noqa: E402
import events as EV  # noqa: E402
import attendance as AT  # noqa: E402
import occasions as OC  # noqa: E402
import permissions as PM  # noqa: E402
import club as CL  # noqa: E402
import tickets as TK  # noqa: E402
import lottery as LT  # noqa: E402
import paylink as PL  # noqa: E402
import finance as FIN  # noqa: E402
import reports as RP  # noqa: E402
import settings_admin as SET  # noqa: E402
import admin as AD  # noqa: E402
import main as M  # noqa: E402

for mod in (PR, F, FF, PAY, EV, AT, OC, CL, TK, LT, PL, FIN, RP, SET, AD, M):
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


def msg(uid, t):
    return {"message_id": 1, "from": {"id": uid, "first_name": "ت"},
            "chat": {"id": uid, "type": "private"}, "text": t}


def cb(uid, d):
    return {"id": "c", "from": {"id": uid, "first_name": "ت"}, "data": d,
            "message": {"message_id": 1,
                        "chat": {"id": uid, "type": "private"}}}


def mkevent(title="رویداد", **kw):
    cols = {"title": title, "event_type": "workshop", "status": "published",
            "capacity": 50, "created_by": S}
    cols.update(kw)
    ks = list(cols)
    return database.db_execute(
        f"INSERT INTO events ({','.join(ks)}) VALUES ({','.join('?' * len(ks))})",
        [cols[k] for k in ks])


def digits_of(s):
    """فقط ارقام یک رشته — برای مقایسه مستقل از جداکننده"""
    return "".join(ch for ch in str(s) if ch.isdigit())


S = 100000001
U1, U2 = 1220001, 1220002

print("=" * 62)
print("🧪 تست فاز ۱۷-د — 💱 همه‌جا ریال")
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
database.seed_default_settings()
SET.seed_phase5_settings()

auth.create_auth_user({"id": S, "first_name": "مدیر"}, "09120000000", "phone")
auth.ensure_super_admin(S)
for u, n in ((U1, "علی"), (U2, "سارا")):
    auth.create_auth_user({"id": u, "first_name": n}, f"0914{u}", "phone")
    database.db_execute("UPDATE users SET profile_status='approved', "
                        "complete_profile_percent=100 WHERE bale_user_id=?",
                        (u,))


# ═══════════ ۱) قرارداد واحد پول ═══════════
print("\n[۱] 📜 قرارداد: همه‌جا ریال")

check("MONEY_UNIT قفل روی ریال", config.MONEY_UNIT == "rial",
      config.MONEY_UNIT)
check("CURRENCY_LABEL ریال است", config.CURRENCY_LABEL == "ریال",
      config.CURRENCY_LABEL)

# 🔴 ادعای اصلی: هیچ تابعی عدد را تغییر ندهد
for v in (0, 1, 999, 10000, 250000, 5000000, 123456789):
    got = digits_of(config.money(v, with_unit=False))
    check(f"money({v}) عدد را تغییر نمی‌دهد", got == str(v), got)

check("parse_money معکوس money است",
      config.parse_money(config.money(750000)) == 750000,
      str(config.parse_money(config.money(750000))))
check("parse_money با جداکننده", config.parse_money("1,500,000") == 1500000)
check("parse_money با ارقام فارسی و جداکننده فارسی",
      config.parse_money("۲٬۵۰۰٬۰۰۰") == 2500000,
      str(config.parse_money("۲٬۵۰۰٬۰۰۰")))
check("parse_money ورودی خراب", config.parse_money("سلام") == 0)
check("money ورودی None", digits_of(config.money(None)) == "0")

# ۴ تابع نمایش پول باید یکی باشند
AMT = 4_850_000
four = {
    "config.money":     digits_of(config.money(AMT, False)),
    "events.fmt_money": digits_of(EV.fmt_money(AMT)),
    "payments.fmt":     digits_of(PAY.fmt(AMT)),
    "forms.fmt_amount": digits_of(F.fmt_amount(AMT)),
}
check("🔴 هر چهار تابع نمایش یک عدد می‌دهند",
      len(set(four.values())) == 1, str(four))
check("🔴 و آن عدد دقیقاً ورودی است",
      set(four.values()) == {str(AMT)}, str(four))
check("money_rial هم‌معنی money", config.money_rial(AMT) == config.money(AMT))
check("payments.fmt_rial هم‌معنی fmt", PAY.fmt_rial(AMT) == PAY.fmt(AMT))


# ═══════════ ۲) 🔴 سرتاسری: ادمین → دیتابیس → کاربر → درگاه ═══════════
print("\n[۲] 🔴 زنجیره کامل مبلغ (باگ اصلی کاربر)")

PRICE = 850000          # عددی که ادمین تایپ می‌کند

eid = mkevent("کارگاه ریالی", is_paid=1, price=PRICE,
              show_price_publicly=1, require_profile=0,
              payment_method="bale_wallet")

ev = EV.get_event(eid)
check("① دیتابیس همان عدد را دارد", ev["price"] == PRICE, str(ev["price"]))

body = EV.event_full_text(ev, for_admin=False)
check("② کاربر همان عدد را می‌بیند", digits_of(PRICE) in digits_of(body),
      body[:150])
check("② واحد «ریال» کنارش هست", "ریال" in body, body[:150])
check("🔴 عدد ۱۰ برابر کوچک‌تر (۸۵٬۰۰۰) نیست",
      "85,000 " not in body and "85٬000 " not in body, body[:150])

rid = database.db_execute("""INSERT INTO event_registrations
    (event_id, user_id, bale_user_id, status)
    VALUES (?,?,?,'pending')""", (eid, auth.get_user(U1)["id"], U1))

_INV.clear()
SENT.clear()
PAY.route_payment(U1, U1, ev, rid, PRICE)

check("③ به درگاه همان عدد می‌رود",
      _INV and _INV[-1]["prices"][0]["amount"] == PRICE,
      str(_INV[-1]["prices"] if _INV else None))

shown = alltext()
check("④ عددی که کاربر دید = عددی که به درگاه رفت",
      digits_of(PRICE) in digits_of(shown), shown[:150])

tx = database.db_execute("SELECT * FROM transactions WHERE registration_id=?",
                         (rid,), fetch="one")
check("⑤ تراکنش هم همان عدد", tx and tx["amount"] == PRICE,
      str(tx.get("amount") if tx else None))

check("🎯 هر پنج مرحله یک عدد واحد",
      ev["price"] == _INV[-1]["prices"][0]["amount"] == tx["amount"] == PRICE)


# ═══════════ ۳) ورودی ادمین از داخل ربات ═══════════
print("\n[۳] ⌨️ عددی که ادمین تایپ می‌کند")

# مبلغ فرم
M.handle_callback(cb(S, "fb_new"))
M.handle_callback(cb(S, "fbt_registration"))
M.process_message(msg(S, "فرم ریالی"))
M.process_message(msg(S, "⏭️ رد کردن"))
fid = database.db_scalar("SELECT MAX(id) FROM forms")
M.handle_callback(cb(S, f"fbtpl_{fid}"))
M.handle_callback(cb(S, f"fbpm_card_{fid}"))
M.handle_callback(cb(S, f"fbprice_{fid}"))
SENT.clear()
M.process_message(msg(S, "1250000"))
check("فرم: عدد تایپ‌شده عیناً ذخیره شد",
      F.get_form(fid)["price"] == 1250000, str(F.get_form(fid)["price"]))
check("فرم: تأیید همان عدد را نشان می‌دهد",
      "1250000" in digits_of(last()), last()[:80])

# ارقام فارسی
M.handle_callback(cb(S, f"fbprice_{fid}"))
M.process_message(msg(S, "۹۹۰۰۰۰"))
check("فرم: ارقام فارسی هم بدون تبدیل",
      F.get_form(fid)["price"] == 990000, str(F.get_form(fid)["price"]))

# لینک پرداخت غیرمتمرکز
M.handle_callback(cb(S, "pl_new"))
M.process_message(msg(S, "کمک به مدرسه"))
M.process_message(msg(S, "⏭️ رد کردن"))
M.process_message(msg(S, "3300000"))
lk = database.db_execute("SELECT * FROM payment_links ORDER BY id DESC LIMIT 1",
                         fetch="one")
check("لینک پرداخت: عدد تایپ‌شده عیناً ذخیره شد",
      lk and lk["amount"] == 3300000, str(lk.get("amount") if lk else None))

# کد تخفیف مبلغی
M.handle_callback(cb(S, f"evdadd_{eid}"))
M.process_message(msg(S, "RIAL10 | 120000 | 5"))
dc = database.db_execute("SELECT * FROM event_discount_codes WHERE code=?",
                         ("RIAL10",), fetch="one")
check("کد تخفیف: مبلغ عیناً ریال",
      dc and dc["amount"] == 120000, str(dc.get("amount") if dc else None))


# ═══════════ ۴) کارمزد ═══════════
print("\n[۴] 💳 کارمزد هم ریالی است")

database.set_setting("pay_fee_bale_wallet_on", "1", "t", "payment")
database.set_setting("pay_fee_bale_wallet_pct", "0", "t", "payment")
database.set_setting("pay_fee_bale_wallet_fix", "45000", "t", "payment")
database.clear_settings_cache()

check("کارمزد ثابت عیناً خوانده شد",
      PAY.fee_fixed("bale_wallet") == 45000,
      str(PAY.fee_fixed("bale_wallet")))
fee, total = PAY.calc_fee(1000000, "bale_wallet")
check("کارمزد درست محاسبه شد", fee == 45000, str(fee))
check("مبلغ کل = اصل + کارمزد", total == 1045000, str(total))

brk = PAY.fee_breakdown(1000000, "bale_wallet")
check("ریز مبلغ اصل را نشان می‌دهد", "1,000,000" in brk, brk[:120])
check("ریز مبلغ کارمزد را نشان می‌دهد", "45,000" in brk, brk[:120])
check("ریز مبلغ جمع را نشان می‌دهد", "1,045,000" in brk, brk[:120])

# 🔴 مبلغی که با کارمزد به درگاه می‌رود
eid2 = mkevent("رویداد کارمزددار", is_paid=1, price=1000000,
               show_price_publicly=1, require_profile=0,
               payment_method="bale_wallet")
rid2 = database.db_execute("""INSERT INTO event_registrations
    (event_id, user_id, bale_user_id, status)
    VALUES (?,?,?,'pending')""", (eid2, auth.get_user(U2)["id"], U2))
_INV.clear()
SENT.clear()
PAY.route_payment(U2, U2, EV.get_event(eid2), rid2, 1000000)
_sum = sum(p["amount"] for p in (_INV[-1]["prices"] if _INV else []))
check("🔴 جمع اقلام فاکتور = اصل + کارمزد", _sum == 1045000, str(_sum))

database.set_setting("pay_fee_bale_wallet_on", "0", "t", "payment")
database.clear_settings_cache()


# ═══════════ ۵) امتیاز ═══════════
print("\n[۵] 🏆 نرخ امتیاز ریالی")

database.set_setting("pay_points_enabled", "1", "t", "payment")
database.set_setting("pay_points_rate", "20000", "t", "payment")
database.set_setting("pay_points_max_pct", "100", "t", "payment")
database.set_setting("pay_points_min_keep", "0", "t", "payment")
database.clear_settings_cache()

check("نرخ عیناً ریال خوانده شد", PAY.points_rate_rial() == 20000,
      str(PAY.points_rate_rial()))
check("۱۰ امتیاز = ۲۰۰٬۰۰۰ ریال", PAY.points_to_rial(10) == 200000)
check("۲۰۰٬۰۰۰ ریال = ۱۰ امتیاز", PAY.rial_to_points(200000) == 10)

database.db_execute("UPDATE users SET total_points=50 WHERE bale_user_id=?",
                    (U1,))
q = PAY.points_quote(U1, 1000000)
check("۵۰ امتیاز = ۱٬۰۰۰٬۰۰۰ ریال پوشش", q["covered"] == 1000000, str(q))
check("پوشش کامل است", q["full"], str(q))

database.set_setting("pay_points_enabled", "0", "t", "payment")
database.clear_settings_cache()


# ═══════════ ۶) گزارش‌ها و اکسل ═══════════
print("\n[۶] 📊 گزارش مالی ریالی")

database.db_execute("UPDATE transactions SET status='paid' WHERE id IS NOT NULL")
SENT.clear()
M.handle_callback(cb(S, "fin_dash"))
d = last()
check("داشبورد مالی باز شد", "داشبورد مالی" in d, d[:60])
check("داشبورد واحد ریال دارد", "ریال" in d, d[:120])
check("🔴 داشبورد کلمه تومان ندارد", "تومان" not in d, d[:150])

_paid_sum = database.db_scalar(
    "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE status='paid'")
check("جمع درآمد داشبورد = جمع دیتابیس",
      digits_of(f"{_paid_sum:,}") in digits_of(d), f"{_paid_sum}")


# ═══════════ ۷) 🔴 هیچ ماژولی تبدیل نکند ═══════════
print("\n[۷] 🔒 هیچ لایه تبدیلی باقی نمانده")

MODS = ["events.py", "payments.py", "forms.py", "form_fill.py",
        "form_fields.py", "form_reports.py", "finance.py", "reports.py",
        "paylink.py", "settings_admin.py", "admin.py", "club.py",
        "attendance.py", "lottery.py", "main.py", "tickets.py"]

for m in MODS:
    src = (ROOT / m).read_text(encoding="utf-8")
    src = src.replace("points_to_rial(", "")     # نام تابع امتیاز، نه واحد پول
    bad = [x for x in ("to_toman(", "to_rial(") if x in src]
    check(f"{m} تبدیل واحد ندارد", not bad, str(bad))

# نباید جایی دستی ÷۱۰ یا ×۱۰ روی مبلغ باشد
import re as _re
for m in MODS:
    src = (ROOT / m).read_text(encoding="utf-8")
    hits = _re.findall(r"(?:amount|price|total|fee|mablagh)\s*(?://|\*)\s*10\b",
                       src)
    check(f"{m} ÷۱۰ یا ×۱۰ دستی ندارد", not hits, str(hits[:3]))

check("config تنها جای تعریف واحد است",
      "RIAL_PER_TOMAN" not in (ROOT / "payments.py").read_text(encoding="utf-8"))


# ═══════════ ۸) مهاجرت تنظیمات قدیمی ═══════════
print("\n[۸] ♻️ مهاجرت تنظیمات تومانی قدیمی")

check("پرچم مهاجرت ثبت شد",
      database.get_setting("money_unit_rial", "") == "1",
      database.get_setting("money_unit_rial", ""))

# شبیه‌سازی دیتابیس قدیمی: پرچم را برداریم و مقدار تومانی بگذاریم
database.db_execute("DELETE FROM settings WHERE key='money_unit_rial'")
database.set_setting("pay_points_rate", "1000", "t", "payment")     # تومان
database.set_setting("pay_fee_card_fix", "500", "t", "payment")     # تومان
database.clear_settings_cache()

database.migrate_money_to_rial()

check("♻️ نرخ امتیاز ×۱۰ شد", database.get_setting("pay_points_rate") == "10000",
      database.get_setting("pay_points_rate"))
check("♻️ کارمزد ثابت ×۱۰ شد",
      database.get_setting("pay_fee_card_fix") == "5000",
      database.get_setting("pay_fee_card_fix"))
check("♻️ پرچم دوباره ثبت شد",
      database.get_setting("money_unit_rial") == "1")

# بار دوم نباید دوباره ×۱۰ کند
database.migrate_money_to_rial()
check("🔒 مهاجرت دوبار اجرا نمی‌شود",
      database.get_setting("pay_points_rate") == "10000",
      database.get_setting("pay_points_rate"))


# ═══════════ ۹) رگرسیون — باگ‌های قبلی برنگشته باشند ═══════════
print("\n[۹] 🛡️ رگرسیون")

check("مبلغ منفی در تراکنش‌ها نیست",
      (database.db_scalar("SELECT COUNT(*) FROM transactions "
                          "WHERE amount < 0") or 0) == 0)
check("مبلغ منفی در لینک پرداخت نیست",
      (database.db_scalar("SELECT COUNT(*) FROM payment_links "
                          "WHERE amount < 0") or 0) == 0)
check("قیمت منفی در رویدادها نیست",
      (database.db_scalar("SELECT COUNT(*) FROM events "
                          "WHERE price < 0") or 0) == 0)

# check_amount با اعداد ریالی منطقی کار کند
ok1, _ = config.check_amount(500000)
check("check_amount مبلغ متعارف را می‌پذیرد", ok1)
ok2, m2 = config.check_amount(5)
check("check_amount مبلغ خیلی کم را رد می‌کند", not ok2, m2[:50])
ok3, m3 = config.check_amount(999_999_999)
check("check_amount مبلغ نجومی را رد می‌کند", not ok3, m3[:50])

# پیام خطای سقف باید ریالی باشد
check("پیام خطای سقف ریالی است", "ریال" in m3, m3[:80])

# فرم برگشت‌پذیر (باگ گیرکردن کاربر)
check("دکمه سوال قبل وجود دارد",
      "ffprev" in (ROOT / "form_fill.py").read_text(encoding="utf-8"))
check("روتر ffprev را می‌شناسد",
      '"ffprev"' in (ROOT / "main.py").read_text(encoding="utf-8"))
check("go_prev_question تعریف شده", hasattr(FF, "go_prev_question"))


print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\nناموفق:")
    for f in FAILED:
        print(f"  ❌ {f}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۱۷-د پاس شدند!")
print("💱 عدد ادمین = دیتابیس = کاربر = درگاه — همه ریال")
