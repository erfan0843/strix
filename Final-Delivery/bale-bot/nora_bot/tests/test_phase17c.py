"""
تست فاز ۱۷-ج — رفع ۷ مورد گزارش‌شده

  ۱) تومان/ریال قاطی شده بود — یک صفر اضافه در درگاه
  ۲) متن OTP قابل ویرایش نبود
  ۳) «هزینه دارد» به کاربر نشان داده می‌شد
  ۴) متن‌ها مهربان‌تر شوند
  ۵) پارامترهای پروفایل قابل تنظیم نبود
  ۶) پیام کاربر به ادمین ذخیره نمی‌شد → صندوق دریافت
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora17c_")
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
import activity_log as AL  # noqa: E402
import club as CL  # noqa: E402
import tickets as TK  # noqa: E402
import lottery as LT  # noqa: E402
import paylink as PL  # noqa: E402
import settings_admin as SET  # noqa: E402
import admin as AD  # noqa: E402
import main as M  # noqa: E402

for mod in (PR, F, FF, PAY, EV, AT, OC, AL, CL, TK, LT, PL, SET, AD, M):
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


def mkevent(title="رویداد", **kw):
    cols = {"title": title, "event_type": "workshop", "status": "published",
            "capacity": 50, "created_by": S}
    cols.update(kw)
    ks = list(cols)
    return database.db_execute(
        f"INSERT INTO events ({','.join(ks)}) VALUES ({','.join('?' * len(ks))})",
        [cols[k] for k in ks])


S = 100000001
U1, U2 = 1110001, 1110002

print("=" * 62)
print("🧪 تست فاز ۱۷-ج — رفع ۷ مورد گزارش‌شده")
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
    auth.create_auth_user({"id": u, "first_name": n}, f"0913{u}", "phone")
    database.db_execute("UPDATE users SET profile_status='approved', "
                        "complete_profile_percent=100 WHERE bale_user_id=?",
                        (u,))


# ═══════════ ۱) 💱 همه‌جا ریال — بدون هیچ تبدیلی ═══════════
print("\n[۱] 💱 واحد پول یکسان است: ریال")

R = 5000000                          # ۵٬۰۰۰٬۰۰۰ ریال

check("واحد قفل روی ریال", config.MONEY_UNIT == "rial", config.MONEY_UNIT)
check("برچسب واحد ریال است", config.CURRENCY_LABEL == "ریال",
      config.CURRENCY_LABEL)

# 🔴 قلب ماجرا: چهار تابع نمایش پول باید یک عدد یکسان بدهند
vals = {
    "config.money":     config.money(R, False),
    "events.fmt_money": EV.fmt_money(R),
    "payments.fmt":     PAY.fmt(R),
    "forms.fmt_amount": F.fmt_amount(R),
}
norm = {v.replace("٬", "").replace(",", "") for v in vals.values()}
check("🔴 هر چهار تابع یکسان‌اند", len(norm) == 1, str(vals))
check("🔴 عدد دست‌نخورده می‌ماند (نه ÷۱۰)", norm == {"5000000"}, str(norm))

check("parse_money بدون تبدیل", config.parse_money("5000000") == R,
      str(config.parse_money("5000000")))
check("money_rial هم‌معنی money", config.money_rial(R) == config.money(R),
      config.money_rial(R))

# متن رویداد — همان عددی که ادمین وارد کرده
eid = mkevent("رویداد قیمت‌دار", is_paid=1, price=R,
              show_price_publicly=1, require_profile=0)
body = EV.event_full_text(EV.get_event(eid), for_admin=False)
check("✅ متن رویداد همان عدد ریالی را نشان می‌دهد",
      "5٬000٬000" in body or "5,000,000" in body, body[:160])
check("🔴 عدد ۱۰ برابر کوچک‌تر نیست",
      "500٬000 " not in body and "500,000 " not in body, body[:160])
check("✅ واحد «ریال» در متن هست", "ریال" in body, body[:160])

# لیست رویدادها
SENT.clear()
EV.show_user_events(U1, U1, 0)
t = alltext()
check("لیست هم همان عدد را می‌دهد",
      "5٬000٬000" in t or "5,000,000" in t, t[:160])

# 🔴 درگاه: دقیقاً همان عددی که کاربر دید
rid = database.db_execute("""INSERT INTO event_registrations
    (event_id, user_id, bale_user_id, status)
    VALUES (?,?,?,'pending')""", (eid, auth.get_user(U1)["id"], U1))
_INV.clear()
SENT.clear()
PAY.route_payment(U1, U1, EV.get_event(eid), rid, R)
check("✅ به درگاه همان مبلغ ریالی می‌رود",
      _INV and _INV[-1]["prices"][0]["amount"] == R,
      str(_INV[-1]["prices"] if _INV else None))
check("✅ عددی که کاربر دید = عددی که به درگاه رفت",
      "5٬000٬000" in alltext() or "5,000,000" in alltext(), alltext()[:120])
tx = database.db_execute("SELECT * FROM transactions WHERE registration_id=?",
                         (rid,), fetch="one")
check("✅ در دیتابیس هم همان عدد", tx and tx["amount"] == R,
      str(tx.get("amount") if tx else None))

# 🔴 هیچ ماژولی نباید تبدیل واحد انجام دهد
for _m in ("events.py", "payments.py", "forms.py", "form_fill.py",
           "finance.py", "reports.py", "paylink.py"):
    _src = (ROOT / _m).read_text(encoding="utf-8")
    _src = _src.replace("points_to_rial(", "")   # نام تابع امتیاز، نه واحد
    check(f"🔴 {_m} تبدیل واحد ندارد",
          "to_toman(" not in _src and "to_rial(" not in _src, _m)


# ═══════════ ۲) 🔢 متن OTP قابل ویرایش ═══════════
print("\n[۲] 🔢 متن کد یکبار مصرف")

keys = [k for k, _, _ in SET.EDITABLE_TEXTS]
for k in ("msg_otp_sent", "msg_otp_hint"):
    check(f"{k} در لیست ویرایش", k in keys)

check("متن پیش‌فرض seed شد",
      database.get_setting("msg_otp_sent", "") != "")
check("جای‌گذاری {mobile} دارد",
      "{mobile}" in database.get_setting("msg_otp_sent", ""))

database.set_setting("msg_otp_sent", "🔐 کد شما برای {mobile} رفت", "t", "شروع")
database.clear_settings_cache()

# ⚠️ sandbox به سفیر دسترسی ندارد → mock می‌کنیم تا مسیر موفقیت اجرا شود
_orig_otp = M.send_otp_via_safir
M.send_otp_via_safir = lambda ph, cd: {"ok": True, "test_mode": False}
SENT.clear()
M.handle_callback(cb(U2, "auth_otp"))
M.process_message(msg(U2, "09121112233"))
M.send_otp_via_safir = _orig_otp
check("متن سفارشی استفاده شد",
      "کد شما برای" in alltext(), alltext()[-150:])
check("شماره جایگزین شد", "09121112233" in alltext())
check("راهنما هم اضافه شد", "بات رمز یکبار مصرف" in alltext())
auth.clear_state(U2)
database.db_execute("DELETE FROM settings WHERE key='msg_otp_sent'")
database.clear_settings_cache()
SET.seed_phase5_settings()


# ═══════════ ۳) 🙈 مخفی کردن کامل هزینه ═══════════
print("\n[۳] 🙈 هیچ اشاره‌ای به هزینه")

ecols = {c["name"] for c in
         database.db_execute("PRAGMA table_info(events)", fetch="all")}
check("ستون hide_cost_hint", "hide_cost_hint" in ecols)

eid2 = mkevent("رویداد مخفی", is_paid=1, price=R,
               show_price_publicly=0, hide_cost_hint=0, require_profile=0)
_SHOWN = EV.fmt_money(R)          # عددی که ادمین می‌بیند
b1 = EV.event_full_text(EV.get_event(eid2), for_admin=False)
check("با hide=0 اشاره کلی می‌آید", "هزینه" in b1, b1[:150])
check("ولی عددی نیست", _SHOWN not in b1, b1[:150])

database.db_execute("UPDATE events SET hide_cost_hint=1 WHERE id=?", (eid2,))
b2 = EV.event_full_text(EV.get_event(eid2), for_admin=False)
check("🙈 با hide=1 هیچ کلمه‌ای از هزینه نیست",
      "هزینه" not in b2, b2[:200])
check("🙈 هیچ عددی هم نیست", _SHOWN not in b2, b2[:200])

SENT.clear()
EV.show_user_events(U1, U1, 0)
_t = alltext()
check("لیست هم اشاره نمی‌کند",
      "هزینه‌دار" not in _t or "ثبت‌نام باز" in _t, _t[:200])

# ادمین همیشه می‌بیند
ba = EV.event_full_text(EV.get_event(eid2), for_admin=True)
check("✅ ادمین عدد را می‌بیند", _SHOWN in ba, ba[:150])

# قابل تنظیم از مرور و تنظیمات نمایش
SENT.clear()
M.handle_callback(cb(S, f"evrev_{eid2}"))
check("🙈 در مرور نهایی هست",
      f"evtogr_hide_cost_hint_{eid2}" in allcb(), str(allcb())[:150])
SENT.clear()
M.handle_callback(cb(S, f"evshow_{eid2}"))
check("🙈 در تنظیمات نمایش هست",
      f"evtog_hide_cost_hint_{eid2}" in allcb(), str(allcb())[:150])
check("متن پیام قابل ویرایش",
      "msg_event_paid_hidden" in [k for k, _, _ in SET.EDITABLE_TEXTS])


# ═══════════ ۴) 💚 متن‌های مهربان ═══════════
print("\n[۴] 💚 متن‌های مهربان‌تر")

warm = ["💚", "🤝", "🌱"]
n_warm = 0
for k in ("msg_welcome", "msg_referral", "msg_force_join",
          "msg_events_empty", "msg_register_ok", "msg_support"):
    v = database.get_setting(k, "")
    if any(w in v for w in warm):
        n_warm += 1
check("متن‌ها لحن گرم دارند", n_warm >= 4, f"{n_warm}/6")

check("دعوت اجباری در لیست ویرایش",
      "msg_invite_required" in [k for k, _, _ in SET.EDITABLE_TEXTS])
inv_txt = database.get_setting("msg_invite_required", "")
check("متن دعوت مهربان است",
      "همیاری" in inv_txt or "مهر" in inv_txt, inv_txt[:80])
check("متن دعوت جای‌گذاری دارد",
      "{need}" in inv_txt and "{name}" in inv_txt)

# در عمل
eid3 = mkevent("رویداد دعوتی", require_invites=1, invites_needed=2,
               require_profile=0)
SENT.clear()
EV.register(U1, U1, eid3)
t3 = alltext()
check("پیام دعوت مهربان نمایش داده شد",
      "همیاری" in t3 or "مهر" in t3 or "💚" in t3, t3[:200])
check("نام کاربر در پیام", "علی" in t3, t3[:200])
check("نوار پیشرفت هست", "▓" in t3 or "░" in t3)

# پیام نیاز به پروفایل
check("msg_profile_needed در لیست",
      "msg_profile_needed" in [k for k, _, _ in SET.EDITABLE_TEXTS])
eid4 = mkevent("رویداد پروفایلی", require_profile=1)
database.db_execute("UPDATE users SET profile_status='draft' "
                    "WHERE bale_user_id=?", (U2,))
SENT.clear()
EV.register(U2, U2, eid4)
check("پیام پروفایل مهربان است",
      "💚" in alltext() or "قدم" in alltext(), alltext()[:150])
database.db_execute("UPDATE users SET profile_status='approved' "
                    "WHERE bale_user_id=?", (U2,))


# ═══════════ ۵) ⚙️ پارامترهای پروفایل ═══════════
print("\n[۵] ⚙️ تنظیم پارامترهای پروفایل")

check("تابع field_on", hasattr(PR, "field_on"))
check("تابع field_required", hasattr(PR, "field_required"))
check("تابع active_steps", hasattr(PR, "active_steps"))

n0 = len(PR.active_steps())
check("پیش‌فرض همه فعال", n0 == len(PR.FORM_STEPS), f"{n0}/{len(PR.FORM_STEPS)}")

SENT.clear()
M.handle_callback(cb(S, "admin_users"))
check("⚙️ دکمه پارامترها در مدیریت کاربران",
      "pf_params" in allcb(), str(allcb())[:150])

SENT.clear()
M.handle_callback(cb(S, "pf_params"))
check("صفحه پارامترها", "پارامترهای پروفایل" in last(), last()[:50])
pf = allcb()
check("فیلدها دکمه دارند",
      sum(1 for d in pf if d.startswith("pfo_")) >= 15, str(len(pf)))
check("دکمه بازنشانی", "pf_reset" in pf)
check("نام همیشه فعال است", "همیشه فعال" in last())

# خاموش کردن یک فیلد
SENT.clear()
M.handle_callback(cb(S, "pfo_bio"))
check("فیلد bio خاموش شد", not PR.field_on("bio"))
check("از مراحل حذف شد",
      len(PR.active_steps()) == n0 - 1, str(len(PR.active_steps())))
check("bio در مراحل نیست",
      not any(s["key"] == "bio" for s in PR.active_steps()))

M.handle_callback(cb(S, "pfo_bio"))
check("دوباره روشن شد", PR.field_on("bio"))

# اجباری کردن
check("email پیش‌فرض اختیاری", not PR.field_required("email", False))
SENT.clear()
M.handle_callback(cb(S, "pfr_email"))
check("email اجباری شد", PR.field_required("email", False))
check("در REQUIRED_KEYS آمد", "email" in PR._required_keys())
M.handle_callback(cb(S, "pfr_email"))
check("دوباره اختیاری شد", not PR.field_required("email", False))

# نام قابل خاموش کردن نیست
SENT.clear()
M.handle_callback(cb(S, "pfo_full_name"))
check("🔒 نام خاموش نمی‌شود", "نامعتبر" in last(), last()[:40])
check("نام همیشه در مراحل هست",
      any(s["key"] == "full_name" for s in PR.active_steps()))

# فیلد نامعتبر
SENT.clear()
M.handle_callback(cb(S, "pfo_evil"))
check("🔒 فیلد نامعتبر رد شد", "نامعتبر" in last())

# بازنشانی
M.handle_callback(cb(S, "pfo_city"))
M.handle_callback(cb(S, "pf_reset"))
check("♻️ بازنشانی همه را برگرداند",
      len(PR.active_steps()) == n0, str(len(PR.active_steps())))

# فرم پروفایل واقعاً پویاست
M.handle_callback(cb(S, "pfo_bio"))
M.handle_callback(cb(S, "pfo_university"))
SENT.clear()
M.handle_callback(cb(U1, "profile_fill"))
check("راهنما تعداد پویا نشان می‌دهد",
      str(len(PR.active_steps())) in alltext(), alltext()[:200])
auth.clear_state(U1)
M.handle_callback(cb(S, "pf_reset"))


# ═══════════ ۶) 📥 صندوق دریافت ═══════════
print("\n[۶] 📥 صندوق دریافت پیام کاربران")

tabs = {r["name"] for r in database.db_execute(
    "SELECT name FROM sqlite_master WHERE type='table'", fetch="all")}
check("جدول admin_inbox", "admin_inbox" in tabs)

SENT.clear()
M.handle_callback(cb(U1, "u_contact"))
check("درخواست پیام", "پیام" in last(), last()[:40])
M.process_message(msg(U1, "سلام، یک سوال داشتم"))
check("🐛 پیام ذخیره شد",
      (database.db_scalar("SELECT COUNT(*) FROM admin_inbox") or 0) == 1)
check("به ادمین هم رفت",
      any("پیام از کاربر" in t for t in to(S)), str(to(S))[-100:])
check("تأیید به کاربر", "دریافت شد" in alltext())

m1 = database.db_execute("SELECT * FROM admin_inbox ORDER BY id DESC LIMIT 1",
                         fetch="one")
check("متن درست ذخیره شد", m1["message"] == "سلام، یک سوال داشتم")
check("خوانده‌نشده است", m1["is_read"] == 0)
check("unread_count درست", TK.unread_count() == 1)

# منوی پشتیبانی
SENT.clear()
M.handle_callback(cb(S, "admin_care"))
check("📥 دکمه صندوق در منو", "ib_list" in allcb(), str(allcb())[:120])
check("تعداد جدید نمایش داده شد", "صندوق" in last(), last()[:150])

SENT.clear()
M.handle_callback(cb(S, "ib_list"))
check("صندوق باز شد", "صندوق دریافت" in last(), last()[:50])
check("پیام در لیست", f"ib_v_{m1['id']}" in allcb(), str(allcb())[:120])

SENT.clear()
M.handle_callback(cb(S, f"ib_v_{m1['id']}"))
check("جزئیات پیام", "سلام، یک سوال داشتم" in last(), last()[:120])
check("مشخصات کاربر", "علی" in last())
check("دکمه پاسخ", f"ib_r_{m1['id']}" in allcb())
check("خوانده شد", TK.unread_count() == 0)

# پاسخ
SENT.clear()
M.handle_callback(cb(S, f"ib_r_{m1['id']}"))
check("درخواست پاسخ", "پاسخ" in last(), last()[:40])
M.process_message(msg(S, "سلام، بفرمایید"))
check("پاسخ ارسال شد", "ارسال شد" in alltext(), alltext()[:80])
check("کاربر پاسخ گرفت",
      any("بفرمایید" in t for t in to(U1)), str(to(U1))[-100:])
m1b = database.db_execute("SELECT * FROM admin_inbox WHERE id=?",
                          (m1["id"],), fetch="one")
check("پاسخ ذخیره شد", m1b["replied"] == 1)
check("متن پاسخ محفوظ", m1b["reply_text"] == "سلام، بفرمایید")

# فیلتر خوانده‌نشده
M.process_message(msg(U1, "/start"))
auth.clear_state(U1)
M.handle_callback(cb(U1, "u_contact"))
M.process_message(msg(U1, "پیام دوم"))
SENT.clear()
M.handle_callback(cb(S, "ib_p_0_1"))
check("فیلتر خوانده‌نشده", "صندوق" in last())
check("فقط جدید نشان می‌دهد", TK.unread_count() == 1)

SENT.clear()
M.handle_callback(cb(S, "ib_allread"))
check("همه خوانده شدند", TK.unread_count() == 0)

# حذف
n_before = database.db_scalar("SELECT COUNT(*) FROM admin_inbox")
SENT.clear()
M.handle_callback(cb(S, f"ib_d_{m1['id']}"))
check("پیام حذف شد",
      database.db_scalar("SELECT COUNT(*) FROM admin_inbox") == n_before - 1)

# 🔒 دسترسی
SENT.clear()
M.handle_callback(cb(U2, "ib_list"))
check("🔒 کاربر عادی صندوق را نمی‌بیند", "دسترسی" in last())


# ═══════════ ۷) ورودی‌های خراب ═══════════
print("\n[۷] 🛡️ ورودی‌های خراب")

bad = [
    "pf_params", "pf_reset", "pfo_", "pfo_evil", "pfo_full_name",
    "pfr_", "pfr_evil", "pfr_full_name",
    "ib_list", "ib_v_", "ib_v_abc", "ib_v_999999",
    "ib_r_abc", "ib_r_999999", "ib_d_abc", "ib_p_x_y", "ib_allread",
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

try:
    auth.set_state(S, TK.STATE_INBOX_REPLY, {"mid": 999999}, merge=False)
    SENT.clear()
    M.process_message(msg(S, "تست"))
    check("state با پیام ناموجود امن", True)
except Exception as e:
    check("state با پیام ناموجود امن", False, str(e))
auth.clear_state(S)


# ═══════════ ۸) لاگ فارسی ═══════════
print("\n[۸] 📋 لاگ فارسی")

import re as _re
_missing = []
for f in ROOT.glob("*.py"):
    src = f.read_text(encoding="utf-8")
    for m in _re.finditer(r'log_action\([^,]+,\s*"([a-z_]+)"', src):
        if m.group(1) not in AL.ACTION_FA:
            _missing.append(m.group(1))
check("همه فعالیت‌ها ترجمه دارند", not set(_missing), str(set(_missing)))
for k in ("profile_param", "inbox_reply", "admin_edit_profile"):
    check(f"ترجمه {k}", k in AL.ACTION_FA)


# ═══════════ ۹) رگرسیون ═══════════
print("\n[۹] ♻️ رگرسیون")

for d, expect in (("admin_panel", "پنل ادمین"),
                  ("admin_users", "مدیریت کاربران"),
                  ("admin_care", "پشتیبانی"),
                  ("set_payment", "پرداخت"),
                  ("admin_stats", "داشبورد گزارشات"),
                  ("fb_panel", "فرم‌ساز"),
                  ("pl_panel", "غیرمتمرکز"),
                  ("pay_fee", "کارمزد")):
    SENT.clear()
    M.handle_callback(cb(S, d))
    check(f"{expect} سالم", expect in last(), last()[:45])

SENT.clear()
M.process_message(msg(U1, "/start"))
check("start کاربر سالم", "نورا" in alltext() or "سلام" in alltext())

# پروفایل کاربر هنوز کار می‌کند
SENT.clear()
M.handle_callback(cb(U1, "profile_view"))
check("پروفایل کاربر سالم", "پروفایل" in last())

# ویرایش پروفایل ادمین
tid = auth.get_user(U1)["id"]
SENT.clear()
M.handle_callback(cb(S, f"upe_{tid}"))
check("ویرایشگر پروفایل سالم", "ویرایش پروفایل" in last())


# ═══════════ ۱۰) یکپارچگی ═══════════
print("\n[۱۰] 🧩 یکپارچگی")

check("هیچ مبلغ منفی",
      (database.db_scalar("SELECT COUNT(*) FROM transactions "
                          "WHERE amount < 0") or 0) == 0)
check("صندوق: پیام بدون فرستنده نیست",
      (database.db_scalar("SELECT COUNT(*) FROM admin_inbox "
                          "WHERE bale_user_id IS NULL") or 0) == 0)
check("active_steps همیشه full_name دارد",
      any(s["key"] == "full_name" for s in PR.active_steps()))
check("REQUIRED_KEYS خالی نیست", len(PR._required_keys()) > 0)


print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\nناموفق:")
    for f in FAILED:
        print(f"  ❌ {f}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۱۷-ج پاس شدند!")
