"""
تست فاز ۱۳ — بازچینی منوها + روش‌های پرداخت پیشرفته

درخواست‌های کاربر که اینجا تست می‌شوند:
  ۱) لاگ فعالیت → مدیریت ادمین‌ها
  ۲) مالی و تراکنش → تنظیمات › روش‌های پرداخت (زیرمجموعه)
  ۳) روش‌های پرداخت پیشرفته‌تر (چند روشی + پرداخت با امتیاز)
  ۴) درخواست‌های پروفایل → مدیریت کاربران
  ۵) منوی اصلی خلوت و جامع
  ۶) فقط سوپرادمین به مالی و درآمد کل دسترسی دارد
  ۷) منوی کاربر معمولی به سوپرادمین و ادمین کامل نمایش داده نشود
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TMP = tempfile.mkdtemp(prefix="nora13_")
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


bale_api.api = _api
bale_api.api_async = _api
bale_api.send = _send
bale_api.send_or_edit = _soe
bale_api._send_file = _file
bale_api.send_photo = lambda c, p, cap=None, kb=None: _file("sendPhoto", "p", c, p, cap, kb)
bale_api.send_document = lambda c, d, cap=None, kb=None: _file("sendDocument", "d", c, d, cap, kb)
bale_api.send_invoice = lambda *a, **k: _api("sendInvoice", {})

import config  # noqa: E402
import database  # noqa: E402
sys.path.insert(0, str(ROOT / "tests"))
import _points_fixture as _pf  # noqa: E402  (موجودی آزمایشی از مسیر دفترکل)
import auth  # noqa: E402
import forms as F  # noqa: E402
import payments as PAY  # noqa: E402
import events as EV  # noqa: E402
import attendance as AT  # noqa: E402
import occasions as OC  # noqa: E402
import permissions as PM  # noqa: E402
import activity_log as AL  # noqa: E402
import finance as FIN  # noqa: E402
import club as CL  # noqa: E402
import tickets as TK  # noqa: E402
import admin as AD  # noqa: E402
import main as M  # noqa: E402
import shared_api  # noqa: E402
from types import SimpleNamespace  # noqa: E402

for mod in (F, PAY, EV, AT, OC, AL, FIN, CL, TK, AD, M):
    for n in ("send", "send_or_edit", "send_photo", "send_document"):
        if hasattr(mod, n):
            setattr(mod, n, getattr(bale_api, n))
PAY.send_invoice = bale_api.send_invoice

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


def replykb():
    """آخرین کیبورد پایین صفحه"""
    for s in reversed(SENT):
        kb = s["p"].get("kb") or {}
        if kb.get("keyboard"):
            return [b["text"] if isinstance(b, dict) else str(b)
                    for r in kb["keyboard"] for b in r]
    return []


def msg(uid, t):
    return {"message_id": 1, "from": {"id": uid, "first_name": "ت"},
            "chat": {"id": uid, "type": "private"}, "text": t}


def cb(uid, d):
    return {"id": "c", "from": {"id": uid, "first_name": "ت"}, "data": d,
            "message": {"message_id": 1, "chat": {"id": uid, "type": "private"}}}


S = 100000001
A_FULL, A_EV, A_FIN, A_RP = 830001, 830002, 830003, 830004
U1, U2 = 840001, 840002

print("=" * 62)
print("🧪 تست فاز ۱۳ — بازچینی منو + پرداخت پیشرفته")
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

auth.create_auth_user({"id": S, "first_name": "مدیر"}, "09120000000", "phone")
auth.ensure_super_admin(S)
for u, nm in ((A_FULL, "فرهاد"), (A_EV, "رضا"), (A_FIN, "لیلا"),
              (A_RP, "کاوه"), (U1, "علی"), (U2, "سارا")):
    auth.create_auth_user({"id": u, "first_name": nm}, f"0913{u}", "phone")

PM.set_role(A_FULL, "full_admin", S)
PM.set_role(A_EV, "event_admin", S)
PM.set_role(A_FIN, "finance_admin", S)
PM.set_role(A_RP, "report_admin", S)


# ═══════════ ۱) مالی فقط برای سوپرادمین ═══════════
print("\n[۱] 🔒 مالی و درآمد کل — فقط سوپرادمین")

check("fin_view در SUPER_ONLY", "fin_view" in PM.SUPER_ONLY)
check("fin_export در SUPER_ONLY", "fin_export" in PM.SUPER_ONLY)
check("fin_settings در SUPER_ONLY", "fin_settings" in PM.SUPER_ONLY)

check("✅ سوپرادمین می‌بیند", PM.has_perm(S, "fin_view"))
for a, nm in ((A_FULL, "ادمین کامل"), (A_EV, "ادمین رویداد"),
              (A_FIN, "ادمین رسیدها"), (A_RP, "گزارش‌گیر")):
    check(f"🔒 {nm} درآمد نمی‌بیند", not PM.has_perm(a, "fin_view"))
    check(f"🔒 {nm} خروجی مالی ندارد", not PM.has_perm(a, "fin_export"))

# حتی با custom هم نمی‌شود داد
PM.set_role(A_EV, "custom", S, perms=["fin_view", "fin_export", "ev_create"])
check("🔒 با custom هم fin_view داده نمی‌شود", not PM.has_perm(A_EV, "fin_view"))
check("✅ بقیه custom کار می‌کند", PM.has_perm(A_EV, "ev_create"))
PM.set_role(A_EV, "event_admin", S)

# گارد عملی
SENT.clear()
FIN.show_dashboard(A_FULL, A_FULL)
check("🔒 گارد داشبورد درآمد", "دسترسی" in last(), last()[:50])
SENT.clear()
FIN.show_transactions(A_FIN, A_FIN, 0, "all")
check("🔒 گارد لیست تراکنش", "دسترسی" in last(), last()[:50])
SENT.clear()
FIN.export_finance(A_FULL, A_FULL)
check("🔒 گارد خروجی مالی", "دسترسی" in last(), last()[:50])
SENT.clear()
PAY.show_payment_settings(A_FULL, A_FULL)
check("🔒 گارد صفحه پرداخت", "سوپرادمین" in last() or "دسترسی" in last(),
      last()[:50])
SENT.clear()
PAY.show_advanced_payment(A_FULL, A_FULL)
check("🔒 گارد پرداخت پیشرفته", "سوپرادمین" in last() or "دسترسی" in last())

SENT.clear()
FIN.show_dashboard(S, S)
check("✅ سوپرادمین داشبورد را می‌بیند", "داشبورد مالی" in last())

# ادمین رسیدها هنوز کار روزمره‌اش را می‌کند
check("✅ ادمین رسیدها تأیید رسید دارد", PM.has_perm(A_FIN, "fin_approve"))
check("✅ ادمین رسیدها بازپرداخت دارد", PM.has_perm(A_FIN, "fin_refund"))


# ═══════════ ۲) پنل ادمین خلوت ═══════════
print("\n[۲] 🧹 پنل ادمین خلوت و جامع")

SENT.clear()
M.handle_callback(cb(S, "admin_panel"))
panel = allcb()
check("پنل باز شد", "پنل ادمین" in last())
check(f"حداکثر ۸ دکمه (شد {len(panel)})", len(panel) <= 8, str(panel))

for d in ("admin_users", "admin_settings", "admin_stats", "fb_panel",
          "admin_notify", "admin_care", "ev_list"):
    check(f"دکمه {d}", d in panel, str(panel))

check("🔄 مالی از پنل اصلی رفت", "fin_dash" not in panel)
check("🔄 لاگ از پنل اصلی رفت", "lg_list" not in panel)
check("🔄 درخواست پروفایل از پنل اصلی رفت", "admin_subs" not in panel)
check("🔄 تیکت از پنل اصلی رفت", "tk_admin" not in panel)
check("🔄 باشگاه از پنل اصلی رفت", "cl_panel" not in panel)
check("🔄 «تعریف رویداد جدید» جدا نیست", "ev_new" not in panel)


# ═══════════ ۳) جابه‌جایی‌های خواسته‌شده ═══════════
print("\n[۳] 📦 هر چیز سر جای جدیدش")

# ۳.۱ کارتابل پروفایل/فیش با مجوز سروری در مدیریت کاربران
SENT.clear()
_original_identity = shared_api.get_identity
shared_api.get_identity = lambda _uid: SimpleNamespace(
    has_permission=lambda permission: permission in {"us_approve", "receipt_approve"}
)
try:
    M.handle_callback(cb(S, "admin_users"))
finally:
    shared_api.get_identity = _original_identity
um = allcb()
check("📋 کارتابل مشترک در مدیریت کاربران", "shared_inbox" in um, str(um))
check("لیست کاربران هست", "um_list" in um)
check("ورود اکسل هست", "admin_import" in um)
check("خروجی اکسل هست", "admin_export" in um)
check("مدیریت ادمین‌ها هست", "um_admins" in um)

# ۳.۲ لاگ فعالیت → مدیریت ادمین‌ها
SENT.clear()
M.handle_callback(cb(S, "um_admins"))
adm = allcb()
check("📋 لاگ کامل در مدیریت ادمین‌ها", "lg_list" in adm, str(adm))
check("📊 آمار لاگ در مدیریت ادمین‌ها", "lg_stats" in adm)
check("🎭 راهنمای نقش‌ها", "pm_help" in adm)
check("روی هر ادمین → صفحه دسترسی",
      any(d.startswith("pm_view_") for d in adm), str(adm))

SENT.clear()
M.handle_callback(cb(S, "pm_help"))
check("راهنمای نقش‌ها باز شد", "راهنمای نقش" in last())
check("نقش‌ها را می‌شمارد", "ادمین رویدادها" in last())
check("دسترسی سوپرادمینی را جدا می‌کند", "سوپرادمین" in last())

# ۳.۳ مالی → تنظیمات › پرداخت
SENT.clear()
M.handle_callback(cb(S, "admin_settings"))
st = allcb()
check("💳 پرداخت و مالی در تنظیمات", "set_payment" in st, str(st))
check("🔄 میانبر تکراری ادمین‌ها حذف شد", "um_admins" not in st)

SENT.clear()
M.handle_callback(cb(S, "set_payment"))
pay = allcb()
check("صفحه پرداخت و مالی", "پرداخت و مالی" in last())
check("💰 داشبورد درآمد زیرمجموعه", "fin_dash" in pay, str(pay))
check("🧾 تراکنش‌ها زیرمجموعه", "fin_tx_0_all" in pay)
check("🎛️ روش پیشرفته زیرمجموعه", "pay_adv" in pay)
check("💳 کارت‌ها زیرمجموعه", "pay_cards" in pay)
check("🔗 درگاه‌ها زیرمجموعه", "pay_gateways" in pay)

# ۳.۴ مناسبت + همگانی → اطلاع‌رسانی
SENT.clear()
M.handle_callback(cb(S, "admin_notify"))
nt = allcb()
check("📢 پیام همگانی", "admin_broadcast" in nt, str(nt))
check("🎂 مناسبت‌ها", "oc_panel" in nt)

# ۳.۵ تیکت + باشگاه → پشتیبانی و باشگاه
SENT.clear()
M.handle_callback(cb(S, "admin_care"))
cr = allcb()
check("📱 تیکت‌ها", "tk_admin" in cr, str(cr))
check("🏅 باشگاه", "cl_panel" in cr)


# ═══════════ ۴) منوی پایین بر اساس نقش ═══════════
print("\n[۴] ⌨️ منوی پایین — کاربر عادی به ادمین کامل نمایش داده نشود")

SENT.clear()
M.process_message(msg(U1, "/start"))
u_kb = replykb()
check("کاربر عادی منوی کاربر دارد",
      any("رویدادها" in x for x in u_kb), str(u_kb))
check("کاربر عادی «دعوت از دوستان» دارد",
      any("دعوت" in x for x in u_kb))
check("کاربر عادی پنل ادمین ندارد",
      not any("پنل ادمین" in x for x in u_kb))

SENT.clear()
M.process_message(msg(S, "/start"))
s_kb = replykb()
check("🔴 سوپرادمین «دعوت از دوستان» نمی‌بیند",
      not any("دعوت از دوستان" in x for x in s_kb), str(s_kb))
check("🔴 سوپرادمین «اعلان‌ها» نمی‌بیند",
      not any("اعلان‌ها" in x for x in s_kb))
check("🔴 سوپرادمین «پروفایل من» نمی‌بیند",
      not any("پروفایل من" in x for x in s_kb))
check("✅ سوپرادمین «پنل ادمین» دارد",
      any("پنل ادمین" in x for x in s_kb))
check("✅ سوپرادمین «کاربران» دارد", any("کاربران" in x for x in s_kb))
check("✅ سوپرادمین «تنظیمات» دارد", any("تنظیمات" in x for x in s_kb))
check("✅ سوپرادمین «نمای کاربر» دارد",
      any("نمای کاربر" in x for x in s_kb))
check("منوی مدیریتی خلوت است", len(s_kb) <= 8, str(len(s_kb)))

SENT.clear()
M.process_message(msg(A_FULL, "/start"))
f_kb = replykb()
check("🔴 ادمین کامل هم منوی کاربر نمی‌بیند",
      not any("دعوت از دوستان" in x for x in f_kb), str(f_kb))
check("✅ ادمین کامل منوی مدیریتی دارد",
      any("پنل ادمین" in x for x in f_kb))

SENT.clear()
M.process_message(msg(A_EV, "/start"))
e_kb = replykb()
check("✅ ادمین جزئی منوی کاربر + پنل دارد",
      any("دعوت" in x for x in e_kb) and any("پنل ادمین" in x for x in e_kb),
      str(e_kb))


# ═══════════ ۵) نمای کاربر (رفت و برگشت) ═══════════
print("\n[۵] 👤 نمای کاربر — رفت و برگشت")

SENT.clear()
M.process_message(msg(S, "👤 نمای کاربر"))
v_kb = replykb()
check("نمای کاربر روشن شد", M.in_user_view(S))
check("منوی کاربر ظاهر شد", any("دعوت از دوستان" in x for x in v_kb),
      str(v_kb))
check("راهنمای بازگشت هست", "پنل ادمین" in alltext())

SENT.clear()
M.process_message(msg(S, "👤 پروفایل من"))
check("در نمای کاربر پروفایل کار می‌کند", "پروفایل" in alltext())

SENT.clear()
M.process_message(msg(S, "👨‍💼 پنل ادمین"))
check("نمای کاربر خاموش شد", not M.in_user_view(S))
check("به پنل ادمین برگشت", "پنل ادمین" in last())

SENT.clear()
M.process_message(msg(S, "/start"))
check("منوی مدیریتی برگشت",
      not any("دعوت از دوستان" in x for x in replykb()), str(replykb()))

SENT.clear()
M.process_message(msg(U1, "👤 نمای کاربر"))
check("🔒 کاربر عادی نمای کاربر ندارد", "دسترسی" in last())


# ═══════════ ۶) منوی ادمین کامل — دکمه‌ها کار می‌کنند ═══════════
print("\n[۶] 🎛️ دکمه‌های منوی مدیریتی")

for btn, expect in (("👥 کاربران", "مدیریت کاربران"),
                    ("📝 فرم‌ساز", "فرم‌ساز"),
                    ("📊 گزارش‌ها", "آمار"),
                    ("⚙️ تنظیمات", "تنظیمات")):
    SENT.clear()
    M.process_message(msg(S, btn))
    check(f"دکمه «{btn}»", expect in last(), last()[:45])

SENT.clear()
M.process_message(msg(S, "🎉 رویدادها"))
check("«رویدادها» برای ادمین کامل = پنل ادمین رویداد",
      "رویداد" in last())

SENT.clear()
M.process_message(msg(U1, "👥 کاربران"))
check("🔒 کاربر عادی به «کاربران» نمی‌رسد", "دسترسی" in last())


# ═══════════ ۷) پرداخت با امتیاز — محاسبات ═══════════
print("\n[۷] 🏆 پرداخت با امتیاز — محاسبات")

check("پیش‌فرض غیرفعال است", not PAY.points_enabled())
database.set_setting("pay_points_enabled", "1", "t", "payment")
database.set_setting("pay_points_rate", "10000", "t", "payment")
database.set_setting("pay_points_max_pct", "100", "t", "payment")
database.set_setting("pay_points_min_keep", "0", "t", "payment")
check("فعال شد", PAY.points_enabled())

check("نرخ ریالی عیناً خوانده شد", PAY.points_rate_rial() == 10000,
      str(PAY.points_rate_rial()))
check("۵۰ امتیاز = ۵۰۰٬۰۰۰ ریال", PAY.points_to_rial(50) == 500000)
check("۵۰۰٬۰۰۰ ریال = ۵۰ امتیاز", PAY.rial_to_points(500000) == 50)
check("رند به بالا", PAY.rial_to_points(500001) == 51)
check("صفر امن است", PAY.rial_to_points(0) == 0)
check("مقدار خراب کرش نمی‌کند", PAY.rial_to_points(None) == 0)

_pf.set_balance(U1, 100)
q = PAY.points_quote(U1, 500000)     # ۵۰ امتیاز لازم، ۱۰۰ دارد
check("پوشش کامل", q["ok"] and q["full"], str(q))
check("۵۰ امتیاز کسر می‌شود", q["use"] == 50, str(q["use"]))
check("باقی‌مانده صفر", q["rest"] == 0)

q2 = PAY.points_quote(U1, 2000000)   # ۲۰۰ لازم، ۱۰۰ دارد
check("پوشش جزئی", q2["ok"] and not q2["full"], str(q2))
check("همه ۱۰۰ امتیاز خرج می‌شود", q2["use"] == 100)
check("باقی‌مانده ۱٬۰۰۰٬۰۰۰", q2["rest"] == 1000000, str(q2["rest"]))

# سقف درصدی
database.set_setting("pay_points_max_pct", "50", "t", "payment")
q3 = PAY.points_quote(U1, 500000)
check("سقف ۵۰٪ رعایت شد", q3["covered"] <= 250000, str(q3["covered"]))
check("با سقف، پوشش کامل نیست", not q3["full"])
database.set_setting("pay_points_max_pct", "100", "t", "payment")

# حداقل باقی‌مانده
database.set_setting("pay_points_min_keep", "80", "t", "payment")
q4 = PAY.points_quote(U1, 500000)
check("فقط ۲۰ امتیاز قابل خرج", q4["use"] == 20, str(q4["use"]))
database.set_setting("pay_points_min_keep", "0", "t", "payment")

# کاربر بی‌امتیاز
q5 = PAY.points_quote(U2, 500000)
check("کاربر بی‌امتیاز رد می‌شود", not q5["ok"], str(q5))
check("دلیل دارد", bool(q5["reason"]))

# غیرفعال
database.set_setting("pay_points_enabled", "0", "t", "payment")
check("وقتی غیرفعال است quote رد می‌شود",
      not PAY.points_quote(U1, 500000)["ok"])
database.set_setting("pay_points_enabled", "1", "t", "payment")


# ═══════════ ۸) کسر امتیاز اتمیک ═══════════
print("\n[۸] 🔒 کسر امتیاز اتمیک")

_pf.set_balance(U1, 100)
import points_ledger as _PL
_r1 = _PL.post_points(U1, -30, entry_type="spend", source="payment_spend",
                      ref_key="pay:test:1:1:paid0:amt300000", ref_table="transactions", ref_id=1,
                      actor_kind="user", actor_id=U1)
check("کسر موفق", _r1.created and _r1.balance_after == 70, str(_r1))

try:
    _PL.post_points(U1, -999, entry_type="spend", source="payment_spend",
                    ref_key="pay:test:1:1:paid0:amt999", ref_table="transactions", ref_id=2)
    _ok2 = False
except _PL.InsufficientPoints:
    _ok2 = True
check("🔒 کسر بیش از موجودی رد شد", _ok2)
check("امتیاز دست‌نخورده ماند", database.db_scalar(
    "SELECT total_points FROM users WHERE bale_user_id=?", (U1,)) == 70)

_r2 = _PL.reverse_entry(_r1.entry_id, reason="تست برگشت", actor_id=S)
after = database.db_scalar("SELECT total_points FROM users "
                           "WHERE bale_user_id=?", (U1,))
check("بازگشت امتیاز (ردیف معکوس)", after == 100, str(after))
check("🔒 مسیر قدیمی spend_points چیزی کم نمی‌کند", PAY.spend_points(U1, 10)[0] is False)
check("🔒 مسیر قدیمی refund_points غیرفعال است", PAY.refund_points(U1, 10) is False)
check("موجودی تغییر نکرد",
      database.db_scalar("SELECT total_points FROM users "
                         "WHERE bale_user_id=?", (U1,)) == 100)


# ═══════════ ۹) چند روشی ═══════════
print("\n[۹] 🎛️ پرداخت چند روشی")

check("multi در روش‌ها هست", "multi" in PAY.PAYMENT_METHODS)
check("onsite در روش‌ها هست", "onsite" in PAY.PAYMENT_METHODS)
check("points در روش‌ها هست", "points" in PAY.PAYMENT_METHODS)
check("۵ گزینه چند روشی", len(PAY.MULTI_CHOICES) == 5,
      str(PAY.MULTI_CHOICES))

check("تک روش → همان",
      PAY.allowed_methods({"payment_method": "card"}) == ["card"])
check("multi → لیست",
      PAY.allowed_methods({"payment_method": "multi",
                           "payment_methods": "card,onsite"})
      == ["card", "onsite"])
check("multi خالی → fallback",
      len(PAY.allowed_methods({"payment_method": "multi",
                               "payment_methods": ""})) >= 1)
check("روش نامعتبر فیلتر می‌شود",
      PAY.allowed_methods({"payment_method": "multi",
                           "payment_methods": "card,evil,onsite"})
      == ["card", "onsite"])
check("None امن است", PAY.allowed_methods(None) == ["none"])
check("تکراری حذف می‌شود",
      PAY.allowed_methods({"payment_method": "multi",
                           "payment_methods": "card,card"}) == ["card"])

check("onsite همیشه در دسترس", PAY.method_available("onsite")[0])
check("points با فعال بودن در دسترس", PAY.method_available("points")[0])
check("روش نامعتبر رد", not PAY.method_available("evil")[0])


# ═══════════ ۱۰) ستون‌ها و جداول ═══════════
print("\n[۱۰] 🗄️ ستون‌های جدید")

ev_cols = {c["name"] for c in
           database.db_execute("PRAGMA table_info(events)", fetch="all")}
check("events.payment_methods", "payment_methods" in ev_cols)

fm_cols = {c["name"] for c in
           database.db_execute("PRAGMA table_info(forms)", fetch="all")}
check("forms.payment_methods", "payment_methods" in fm_cols)

tx_cols = {c["name"] for c in
           database.db_execute("PRAGMA table_info(transactions)", fetch="all")}
for c in ("method", "points_used", "form_id"):
    check(f"transactions.{c}", c in tx_cols)


# ═══════════ ۱۱) جریان واقعی پرداخت با امتیاز ═══════════
print("\n[۱۱] 🎬 جریان واقعی — پرداخت کامل با امتیاز")

eid = database.db_execute(
    "INSERT INTO events (title, event_type, status, is_paid, price, "
    "payment_method, capacity, created_by) "
    "VALUES ('کارگاه امتیازی','workshop','published',1,500000,'points',50,?)",
    (S,))
ev = EV.get_event(eid)
check("رویداد امتیازی ساخته شد", bool(ev))

_pf.set_balance(U1, 100)
u1row = auth.get_user(U1)
rid = database.db_execute(
    "INSERT INTO event_registrations (event_id, user_id, bale_user_id, status) "
    "VALUES (?,?,?,'pending')", (eid, u1row["id"], U1))

SENT.clear()
PAY.route_payment(U1, U1, ev, rid, 500000)
check("پرداخت با امتیاز انجام شد", "امتیاز" in alltext(), alltext()[:80])
pts = database.db_scalar("SELECT total_points FROM users "
                         "WHERE bale_user_id=?", (U1,))
check("۵۰ امتیاز کسر شد", pts == 50, str(pts))
reg = database.db_execute("SELECT * FROM event_registrations WHERE id=?",
                          (rid,), fetch="one")
check("ثبت‌نام قطعی شد", reg["status"] == "confirmed", str(reg["status"]))
tx = database.db_execute("SELECT * FROM transactions WHERE registration_id=?",
                         (rid,), fetch="one")
check("تراکنش ثبت شد", bool(tx))
check("روش = points", tx and tx.get("method") == "points")
check("امتیاز مصرفی ذخیره شد", tx and tx.get("points_used") == 50,
      str(tx.get("points_used") if tx else None))

# امتیاز ناکافی
SENT.clear()
rid2 = database.db_execute(
    "INSERT INTO event_registrations (event_id, user_id, bale_user_id, status) "
    "VALUES (?,?,?,'pending')",
    (eid, auth.get_user(U2)["id"], U2))
PAY.route_payment(U2, U2, ev, rid2, 500000)
check("امتیاز ناکافی پیام می‌دهد",
      "امتیاز" in alltext() and ("کافی" in alltext() or "ندارید" in alltext()),
      alltext()[:80])
check("امتیاز کسی کم نشد",
      (database.db_scalar("SELECT total_points FROM users "
                          "WHERE bale_user_id=?", (U2,)) or 0) == 0)


# ═══════════ ۱۲) جریان پرداخت در محل ═══════════
print("\n[۱۲] 💰 پرداخت در محل")

eid2 = database.db_execute(
    "INSERT INTO events (title, event_type, status, is_paid, price, "
    "payment_method, capacity, created_by) "
    "VALUES ('همایش حضوری','conference','published',1,300000,'onsite',50,?)",
    (S,))
ev2 = EV.get_event(eid2)
rid3 = database.db_execute(
    "INSERT INTO event_registrations (event_id, user_id, bale_user_id, status) "
    "VALUES (?,?,?,'pending')", (eid2, auth.get_user(U1)["id"], U1))

SENT.clear()
PAY.route_payment(U1, U1, ev2, rid3, 300000)
check("پیام پرداخت در محل", "محل" in alltext(), alltext()[:80])
check("کد پیگیری داده شد", "OS" in alltext())
tx2 = database.db_execute(
    "SELECT * FROM transactions WHERE registration_id=?", (rid3,), fetch="one")
check("تراکنش با وضعیت onsite", tx2 and tx2["status"] == "onsite",
      str(tx2.get("status") if tx2 else None))
reg3 = database.db_execute("SELECT * FROM event_registrations WHERE id=?",
                           (rid3,), fetch="one")
check("ثبت‌نام قطعی شد (بدهی می‌ماند)", reg3["status"] == "confirmed")

SENT.clear()
M.handle_callback(cb(S, "pay_onsite"))
check("لیست بدهی‌ها", "بدهی" in last(), last()[:50])
check("دکمه تأیید دریافت", any(d.startswith("payos_") for d in allcb()))

SENT.clear()
PAY.mark_onsite_paid(S, S, tx2["id"])
tx2b = database.db_execute("SELECT * FROM transactions WHERE id=?",
                           (tx2["id"],), fetch="one")
check("✅ وجه در محل تأیید شد", tx2b["status"] == "paid", str(tx2b["status"]))
check("پیام به کاربر رفت", "پرداخت شما در محل" in alltext())

SENT.clear()
PAY.mark_onsite_paid(S, S, tx2["id"])
check("🔒 تأیید دوباره جلوگیری شد", "قبلاً" in last(), last()[:40])

SENT.clear()
PAY.mark_onsite_paid(A_RP, A_RP, tx2["id"])
check("🔒 بدون دسترسی تأیید نمی‌شود", "دسترسی" in last())


# ═══════════ ۱۳) انتخاب روش توسط کاربر ═══════════
print("\n[۱۳] 🎛️ کاربر روش را انتخاب می‌کند")

eid3 = database.db_execute(
    "INSERT INTO events (title, event_type, status, is_paid, price, "
    "payment_method, payment_methods, capacity, created_by) "
    "VALUES ('کارگاه چندروشی','workshop','published',1,400000,'multi',"
    "'bale_wallet,onsite,points',50,?)", (S,))
ev3 = EV.get_event(eid3)
check("روش‌های مجاز خوانده شد",
      PAY.allowed_methods(ev3) == ["bale_wallet", "onsite", "points"],
      str(PAY.allowed_methods(ev3)))

_pf.set_balance(U1, 200)
rid4 = database.db_execute(
    "INSERT INTO event_registrations (event_id, user_id, bale_user_id, status) "
    "VALUES (?,?,?,'pending')", (eid3, auth.get_user(U1)["id"], U1))

SENT.clear()
PAY.route_payment(U1, U1, ev3, rid4, 400000)
picks = [d for d in allcb() if d.startswith("paypick_")]
check("صفحه انتخاب روش", "روش پرداخت" in alltext(), alltext()[:60])
check("۳ روش پیشنهاد شد", len(picks) == 3, str(picks))
check("کیف پول هست", any("bale_wallet" in d for d in picks))
check("در محل هست", any("onsite" in d for d in picks))
check("امتیاز هست", any("points" in d for d in picks))

SENT.clear()
M.handle_callback(cb(U1, f"paypick_points_{rid4}"))
check("انتخاب امتیاز کار کرد", "امتیاز" in alltext(), alltext()[:60])
pts2 = database.db_scalar("SELECT total_points FROM users "
                          "WHERE bale_user_id=?", (U1,))
check("۴۰ امتیاز کسر شد", pts2 == 160, str(pts2))

# روش غیرمجاز
SENT.clear()
rid5 = database.db_execute(
    "INSERT INTO event_registrations (event_id, user_id, bale_user_id, status) "
    "VALUES (?,?,?,'pending')", (eid3, auth.get_user(U2)["id"], U2))
M.handle_callback(cb(U2, f"paypick_card_{rid5}"))
check("🔒 روش غیرمجاز رد شد",
      "مجاز" in alltext() or "دسترس" in alltext(), alltext()[:60])

# ثبت‌نام کس دیگر
SENT.clear()
M.handle_callback(cb(U2, f"paypick_onsite_{rid4}"))
check("🔒 ثبت‌نام دیگری قابل پرداخت نیست",
      "یافت نشد" in alltext(), alltext()[:60])


# ═══════════ ۱۴) پنل تنظیمات پرداخت پیشرفته ═══════════
print("\n[۱۴] ⚙️ پنل روش‌های پرداخت پیشرفته")

SENT.clear()
M.handle_callback(cb(S, "pay_adv"))
adv = allcb()
check("صفحه باز شد", "پیشرفته" in last())
check("دکمه فعال/غیرفعال امتیاز", "payp_toggle" in adv, str(adv))
check("دکمه نرخ امتیاز", "payn_pay_points_rate" in adv)
check("دکمه سقف درصد", "payn_pay_points_max_pct" in adv)
check("دکمه روش‌های پیش‌فرض", "paydm" in adv)
check("دکمه بدهی در محل", "pay_onsite" in adv)

SENT.clear()
M.handle_callback(cb(S, "payp_toggle"))
check("خاموش شد", not PAY.points_enabled())
M.handle_callback(cb(S, "payp_toggle"))
check("دوباره روشن شد", PAY.points_enabled())

SENT.clear()
M.handle_callback(cb(S, "payn_pay_points_rate"))
check("ویرایش نرخ شروع شد", "ارزش" in last(), last()[:40])
M.process_message(msg(S, "20000"))
check("نرخ ذخیره شد",
      database.get_setting("pay_points_rate") == "20000",
      database.get_setting("pay_points_rate"))
check("نرخ ریالی به‌روز شد", PAY.points_rate_rial() == 20000)
database.set_setting("pay_points_rate", "10000", "t", "payment")

SENT.clear()
M.handle_callback(cb(S, "payn_pay_points_max_pct"))
M.process_message(msg(S, "150"))
check("🔒 درصد بالای ۱۰۰ رد شد", "۱۰۰" in last() or "100" in last(),
      last()[:40])
M.process_message(msg(S, "80"))
check("درصد معتبر ذخیره شد",
      database.get_setting("pay_points_max_pct") == "80")
database.set_setting("pay_points_max_pct", "100", "t", "payment")

SENT.clear()
M.handle_callback(cb(S, "payn_pay_points_rate"))
M.process_message(msg(S, "abc"))
check("🔒 ورودی غیرعددی رد شد", "عدد" in last(), last()[:40])
M.process_message(msg(S, "🔙 بازگشت"))
check("لغو کار کرد", "لغو" in alltext() or "پیشرفته" in last())

SENT.clear()
M.handle_callback(cb(S, "paydm"))
check("صفحه روش‌های پیش‌فرض", "پیش‌فرض" in last())
before = database.get_setting("pay_default_methods", "")
M.handle_callback(cb(S, "paydm_onsite"))
after_s = database.get_setting("pay_default_methods", "")
check("تیک روش عوض شد", before != after_s, f"{before} → {after_s}")
M.handle_callback(cb(S, "paydm_onsite"))
check("تیک برداشته شد",
      database.get_setting("pay_default_methods", "") == before)


# ═══════════ ۱۵) ویزارد رویداد — ۶ روش ═══════════
print("\n[۱۵] 🧙 ویزارد رویداد")

SENT.clear()
auth.set_state(S, EV.STATE_EV_CREATE, {"step": 12, "is_paid": 1,
                                       "price": 100000}, merge=False)
EV.show_payment_choice(S, S)
pm = [d for d in allcb() if d.startswith("paym_")]
check("۶ روش پرداخت", len(pm) == 6, str(pm))
for m in ("card", "bale_wallet", "custom_gateway", "onsite", "points",
          "multi"):
    check(f"روش {m} در ویزارد", f"paym_{m}" in pm)

SENT.clear()
M.handle_callback(cb(S, "paym_multi"))
check("انتخابگر چند روشی باز شد", "مجاز" in last(), last()[:50])
check("دکمه تأیید هست", "evmmok" in allcb())

SENT.clear()
M.handle_callback(cb(S, "evmm_onsite"))
d = auth.get_state_data(S)
check("روش به state اضافه شد", "onsite" in (d.get("payment_methods") or ""),
      str(d.get("payment_methods")))

SENT.clear()
M.handle_callback(cb(S, "evmmok"))
d2 = auth.get_state_data(S)
check("روش multi ثبت شد", d2.get("payment_method") == "multi",
      str(d2.get("payment_method")))
auth.clear_state(S)

# ویرایش روش‌های مجاز بعد از ساخت رویداد
SENT.clear()
EV.show_advanced(S, S, eid3)
check("💳 روش پرداخت در قابلیت‌های پیشرفته", "پرداخت" in last(), last()[:60])
check("🎛️ دکمه ویرایش روش‌های مجاز", f"evmulti_{eid3}" in allcb(),
      str(allcb())[:120])

SENT.clear()
M.handle_callback(cb(S, f"evmulti_{eid3}"))
check("انتخابگر ویرایش باز شد", "مجاز" in last())
_b4 = (EV.get_event(eid3) or {}).get("payment_methods")
M.handle_callback(cb(S, f"evmm_card_{eid3}"))
_af = (EV.get_event(eid3) or {}).get("payment_methods")
check("روش در دیتابیس ذخیره شد", _b4 != _af, f"{_b4} → {_af}")
check("card اضافه شد", "card" in (_af or ""))
M.handle_callback(cb(S, f"evmm_card_{eid3}"))
check("card برداشته شد",
      "card" not in (EV.get_event(eid3) or {}).get("payment_methods", ""))
SENT.clear()
M.handle_callback(cb(S, f"evmmok_{eid3}"))
check("تأیید ویرایش کار کرد", "ذخیره" in alltext() or "رویداد" in alltext())

# پرداخت با امتیاز وقتی غیرفعال است
database.set_setting("pay_points_enabled", "0", "t", "payment")
SENT.clear()
auth.set_state(S, EV.STATE_EV_CREATE, {"step": 12, "is_paid": 1}, merge=False)
M.handle_callback(cb(S, "paym_points"))
check("🔒 امتیاز غیرفعال هشدار می‌دهد", "غیرفعال" in last(), last()[:50])
check("راه فعال‌سازی پیشنهاد شد", "pay_adv" in allcb())
database.set_setting("pay_points_enabled", "1", "t", "payment")
auth.clear_state(S)


# ═══════════ ۱۶) ورودی‌های خراب ═══════════
print("\n[۱۶] 🛡️ ورودی‌های خراب کرش نکنند")

bad = [
    "paypick_", "paypick_evil_1", "paypick_card_abc", "paypick_card_999999",
    "paypt_go_abc", "paypt_go_999999", "paypt_other_x",
    "paydm_", "paydm_evil", "payn_", "payn_evil_key",
    "payos_", "payos_abc", "payos_999999",
    "evmm_", "evmm_evil_1", "evmmok_abc", "evmulti_abc",
    "pay_adv", "pay_onsite", "paydm", "payp_toggle",
    "admin_notify", "admin_care", "pm_help", "tx_list",
]
crashed = []
for d in bad:
    try:
        SENT.clear()
        M.handle_callback(cb(S, d))
    except Exception as e:
        crashed.append(f"{d}: {type(e).__name__} {e}")
check("هیچ ورودی خرابی کرش نمی‌کند", not crashed, str(crashed[:3]))

crashed2 = []
for d in bad:
    try:
        SENT.clear()
        M.handle_callback(cb(U1, d))
    except Exception as e:
        crashed2.append(f"{d}: {type(e).__name__} {e}")
check("کاربر عادی هم کرش نمی‌کند", not crashed2, str(crashed2[:3]))

# متن‌های خراب در state
for st in (PAY.STATE_PAY_NUM, PAY.STATE_PICK_METHOD,
           PAY.STATE_POINTS_CONFIRM):
    try:
        auth.set_state(S, st, {"key": "pay_points_rate"}, merge=False)
        SENT.clear()
        M.process_message(msg(S, "!@#$%"))
    except Exception as e:
        check(f"state {st} کرش کرد", False, str(e))
auth.clear_state(S)
check("state های جدید کرش نمی‌کنند", True)


# ═══════════ ۱۷) لاگ فارسی برای فعالیت‌های جدید ═══════════
print("\n[۱۷] 📋 ترجمه فارسی فعالیت‌های جدید")

import re as _re
_missing = []
for f in ROOT.glob("*.py"):
    src = f.read_text(encoding="utf-8")
    for m in _re.finditer(r'log_action\([^,]+,\s*"([a-z_]+)"', src):
        if m.group(1) not in AL.ACTION_FA:
            _missing.append(m.group(1))
check("همه فعالیت‌ها ترجمه دارند", not set(_missing), str(set(_missing)))

for k in ("onsite_pending", "onsite_confirmed", "points_payment",
          "points_spent", "points_refund"):
    check(f"ترجمه {k}", k in AL.ACTION_FA)


# ═══════════ ۱۸) گارد بخش‌ها ═══════════
print("\n[۱۸] 🔐 گارد بخش‌ها بر اساس نقش")

check("ادمین رویداد بخش رویداد را می‌بیند",
      PM.can_section(A_EV, "events"))
check("ادمین رویداد بخش تنظیمات را نمی‌بیند",
      not PM.can_section(A_EV, "settings"))
check("گزارش‌گیر بخش گزارش را می‌بیند", PM.can_section(A_RP, "reports"))
# گزارش‌گیر fm_responses دارد پس بخش فرم را می‌بیند — ولی فقط خواندنی
check("گزارش‌گیر پاسخ فرم می‌بیند", PM.has_perm(A_RP, "fm_responses"))
check("🔒 گزارش‌گیر فرم نمی‌سازد", not PM.has_perm(A_RP, "fm_create"))
check("🔒 گزارش‌گیر فرم ویرایش نمی‌کند", not PM.has_perm(A_RP, "fm_edit"))
check("🔒 گزارش‌گیر بخش تنظیمات را نمی‌بیند",
      not PM.can_section(A_RP, "settings"))
check("سوپرادمین همه بخش‌ها را می‌بیند",
      all(PM.can_section(S, s) for s in PM.SECTION_PERMS))

check("is_full_admin سوپرادمین", PM.is_full_admin(S))
check("is_full_admin ادمین کامل", PM.is_full_admin(A_FULL))
check("is_full_admin ادمین جزئی نه", not PM.is_full_admin(A_EV))
check("is_full_admin کاربر عادی نه", not PM.is_full_admin(U1))

# پنل ادمین جزئی خلوت‌تر است
SENT.clear()
M.handle_callback(cb(A_EV, "admin_panel"))
p_ev = allcb()
check("ادمین رویداد پنل محدود دارد", "ev_list" in p_ev, str(p_ev))
check("🔒 ادمین رویداد تنظیمات نمی‌بیند", "admin_settings" not in p_ev)
check("🔒 ادمین رویداد فرم‌ساز نمی‌بیند", "fb_panel" not in p_ev)

SENT.clear()
M.handle_callback(cb(A_EV, "admin_users"))
check("🔒 ادمین رویداد فقط مشاهده کاربر دارد",
      "admin_import" not in allcb(), str(allcb()))

SENT.clear()
M.handle_callback(cb(A_EV, "um_admins"))
check("🔒 ادمین جزئی مدیریت ادمین ندارد", "دسترسی" in last(), last()[:50])


# ═══════════ ۱۹) رگرسیون فازهای قبل ═══════════
print("\n[۱۹] ♻️ رگرسیون")

SENT.clear()
M.handle_callback(cb(S, "admin_subs"))
check("درخواست‌های پروفایل کار می‌کند",
      "درخواست" in alltext() or "انتظار" in alltext(), alltext()[:50])

SENT.clear()
M.handle_callback(cb(S, "lg_list"))
check("لاگ فارسی کار می‌کند", "لاگ" in last() or "فعالیت" in last())

SENT.clear()
M.handle_callback(cb(S, "fin_dash"))
check("داشبورد مالی کار می‌کند", "داشبورد مالی" in last())
check("امتیاز/پرداخت‌ها در آمار", "درآمد" in last())

SENT.clear()
M.handle_callback(cb(S, "fin_tx_0_all"))
check("لیست تراکنش‌ها کار می‌کند", "تراکنش" in last())

SENT.clear()
M.handle_callback(cb(S, "tx_list"))
check("tx_list قدیمی هدایت می‌شود", "تراکنش" in last())

SENT.clear()
M.handle_callback(cb(U1, "cl_shop"))
check("فروشگاه پاداش کار می‌کند", "فروشگاه" in last() or "پاداش" in last())

SENT.clear()
M.handle_callback(cb(U1, "tk_my"))
check("تیکت کاربر کار می‌کند", "تیکت" in last())

SENT.clear()
M.process_message(msg(U1, "🎉 رویدادها"))
check("کاربر عادی لیست رویداد می‌بیند", "رویداد" in last())

SENT.clear()
M.process_message(msg(U1, "/start"))
check("start کاربر کار می‌کند", "نورا" in alltext() or "سلام" in alltext())
check("منوی کاربر برگشت", any("دعوت" in x for x in replykb()))

# پرداخت‌های قدیمی هنوز کار می‌کنند
eid9 = database.db_execute(
    "INSERT INTO events (title, event_type, status, is_paid, price, "
    "payment_method, capacity, created_by) "
    "VALUES ('رویداد کیف‌پولی','workshop','published',1,150000,"
    "'bale_wallet',50,?)", (S,))
ev9 = EV.get_event(eid9)
rid9 = database.db_execute(
    "INSERT INTO event_registrations (event_id, user_id, bale_user_id, status) "
    "VALUES (?,?,?,'pending')", (eid9, auth.get_user(U2)["id"], U2))
SENT.clear()
PAY.route_payment(U2, U2, ev9, rid9, 150000)
tx9 = database.db_execute("SELECT * FROM transactions WHERE registration_id=?",
                          (rid9,), fetch="one")
check("♻️ کیف پول بله هنوز کار می‌کند", bool(tx9), "تراکنش ساخته نشد")


# ═══════════ ۲۰) یکپارچگی ═══════════
print("\n[۲۰] 🧩 یکپارچگی")

check("امتیاز هیچ‌کس منفی نشد",
      (database.db_scalar("SELECT COUNT(*) FROM users "
                          "WHERE total_points < 0") or 0) == 0)
check("هیچ تراکنش با مبلغ منفی نیست",
      (database.db_scalar("SELECT COUNT(*) FROM transactions "
                          "WHERE amount < 0") or 0) == 0)
check("points_used منفی نیست",
      (database.db_scalar("SELECT COUNT(*) FROM transactions "
                          "WHERE COALESCE(points_used,0) < 0") or 0) == 0)

_sum_used = database.db_scalar(
    "SELECT COALESCE(SUM(points_used),0) FROM transactions") or 0
check("مجموع امتیاز مصرفی منطقی است", _sum_used > 0, str(_sum_used))

check("SUPER_ONLY دست‌نخورده",
      PM.SUPER_ONLY >= {"sys_admins", "sys_settings", "fin_view"})
check("همه دسترسی‌ها یکتا",
      len(PM.PERM_KEYS) == len(set(PM.PERM_KEYS)))
check("همه نقش‌ها معتبرند",
      all(set(r["perms"]) <= set(PM.PERM_KEYS) for r in PM.ROLES.values()))
check("هیچ نقشی SUPER_ONLY ندارد (به‌جز سوپرادمین)",
      all(not (set(r["perms"]) & PM.SUPER_ONLY)
          for k, r in PM.ROLES.items() if k != "super_admin"))


print("\n" + "=" * 62)
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if FAILED:
    print("\nناموفق:")
    for f in FAILED:
        print(f"  ❌ {f}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۱۳ پاس شدند!")
