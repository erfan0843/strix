"""
تست شبیه‌سازی کامل ربات نورا (بدون نیاز به اتصال واقعی به بله)

اجرا:
    cd nora_bot
    py tests/test_bot.py

این تست همه‌ی مسیرهای اصلی را شبیه‌سازی می‌کند و مخصوصاً
دو باگ گزارش‌شده‌ی فاز ۴ را بررسی می‌کند.
"""
import os
import sys
import tempfile
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# --- محیط تست قبل از import ماژول‌ها ---
TMP = tempfile.mkdtemp(prefix="nora_test_")
os.environ["BOT_TOKEN"] = "111222333:TEST_TOKEN_FOR_UNITTEST"
os.environ["SUPER_ADMIN_ID"] = "999000111"
os.environ["DB_PATH"] = str(Path(TMP) / "test.db")
os.environ["BACKUP_DIR"] = str(Path(TMP) / "backups")
os.environ["IMPORT_DIR"] = str(Path(TMP) / "imports")
os.environ["FILES_DIR"] = str(Path(TMP) / "files")
os.environ["PROFILES_DIR"] = str(Path(TMP) / "files/profiles")
os.environ["LOG_DIR"] = str(Path(TMP) / "logs")
os.environ["SAFIR_API_KEY"] = ""

import bale_api  # noqa: E402

# ============ Mock کردن API بله ============
SENT = []


def _mock_api(method, params=None, **kw):
    SENT.append({"method": method, "params": params or {}})
    if method == "getMe":
        return {"ok": True, "result": {"username": "nora_test_bot", "first_name": "نورا"}}
    if method == "getChatMember":
        return {"ok": True, "result": {"status": "member"}}
    if method == "getChat":
        return {"ok": True, "result": {"title": "کانال تست", "username": "test_ch"}}
    return {"ok": True, "result": {"message_id": len(SENT)}}


def _mock_send(cid, text, kb=None):
    SENT.append({"method": "sendMessage", "params": {"chat_id": cid, "text": text, "kb": kb}})
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
bale_api.get_chat = lambda cid: _mock_api("getChat")
bale_api.get_chat_member = lambda c, u: _mock_api("getChatMember")

import database  # noqa: E402
import auth  # noqa: E402
import profile as profile_mod  # noqa: E402
import admin as admin_mod  # noqa: E402
import import_excel as imp_mod  # noqa: E402
import main as main_mod  # noqa: E402

# جایگزینی send در همه ماژول‌ها
for m in (database, auth, profile_mod, admin_mod, imp_mod, main_mod):
    if hasattr(m, "send"):
        m.send = _mock_send
    if hasattr(m, "send_or_edit"):
        m.send_or_edit = _mock_send_or_edit
    if hasattr(m, "forget_menu"):
        m.forget_menu = lambda c: None
profile_mod.send_photo = lambda *a, **k: {"ok": True}
admin_mod.send_document = lambda *a, **k: {"ok": True}
admin_mod.get_chat = lambda cid: _mock_api("getChat")

SUPER = 999000111
USER = 555444333
CID = USER


def last_text(n=1):
    msgs = [s for s in SENT if s["method"] == "sendMessage"]
    return msgs[-n]["params"]["text"] if len(msgs) >= n else ""


def all_texts():
    return [s["params"]["text"] for s in SENT if s["method"] == "sendMessage"]


def texts_to(chat_id):
    return [s["params"]["text"] for s in SENT
            if s["method"] == "sendMessage" and s["params"].get("chat_id") == chat_id]


PASS, FAIL = [], []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  ✅ {name}")
    else:
        FAIL.append((name, detail))
        print(f"  ❌ {name}  {detail}")


def msg(uid, text, chat_id=None):
    return {"message_id": 1, "from": {"id": uid, "first_name": "تست"},
            "chat": {"id": chat_id or uid, "type": "private"}, "text": text}


def cb(uid, data):
    return {"id": "cb1", "from": {"id": uid, "first_name": "تست"},
            "data": data, "message": {"chat": {"id": uid}, "message_id": 1}}


# ==================== شروع ====================
print("\n" + "=" * 60)
print("🧪 تست ربات نورا 4.1")
print("=" * 60)

print("\n[۱] راه‌اندازی دیتابیس")
database.init_db()
database.seed_default_settings()
auth.ensure_super_admin(SUPER, "سوپرادمین")
check("دیتابیس ساخته شد", Path(os.environ["DB_PATH"]).exists())
check("سوپرادمین ثبت شد", bool(auth.get_user(SUPER)))
check("جدول settings پر شد", database.get_setting("msg_welcome") != "")
tables = database.db_execute(
    "SELECT name FROM sqlite_master WHERE type='table'", fetch="all")
check("همه جداول ساخته شدند", len(tables) >= 8, f"({len(tables)} جدول)")


print("\n[۲] توابع کمکی (helpers)")
check("موبایل 09xxx", auth.normalize_mobile("09121234567") == "09121234567")
check("موبایل +98", auth.normalize_mobile("+989121234567") == "09121234567")
check("موبایل 98", auth.normalize_mobile("989121234567") == "09121234567")
check("موبایل 9xxx", auth.normalize_mobile("9121234567") == "09121234567")
check("موبایل با خط تیره", auth.normalize_mobile("0912-123-4567") == "09121234567")
check("موبایل ارقام فارسی", auth.normalize_mobile("۰۹۱۲۱۲۳۴۵۶۷") == "09121234567")
check("موبایل float اکسل", auth.normalize_mobile("9121234567.0") == "09121234567")
check("موبایل نامعتبر", auth.normalize_mobile("12345") is None)
check("نام دو کلمه", auth.split_full_name("علی محمدی") == ("علی", "محمدی"))
check("نام با سید", auth.split_full_name("سید علی موسوی") == ("سید علی", "موسوی"))
check("نام سه کلمه", auth.split_full_name("علی رضا محمدی") == ("علی", "رضا محمدی"))
check("تاریخ تولد", auth.validate_birth_date("1370/1/5") == "1370/01/05")
check("تاریخ نامعتبر", auth.validate_birth_date("سلام") is None)
check("تاریخ ماه ۱۳", auth.validate_birth_date("1370/13/01") is None)
check("کد ملی ۱۰ رقم", auth.validate_national_id("1234567891"))
check("کد ملی کوتاه", not auth.validate_national_id("123"))
check("کد ملی همه یکسان", not auth.validate_national_id("1111111111"))
check("ایمیل درست", auth.validate_email("a@b.com"))
check("ایمیل غلط", not auth.validate_email("abc"))


print("\n[۳] 🐛 تست باگ اصلی: حفظ داده در state")
auth.clear_state(USER)
auth.set_state(USER, "form_filling", {"step": 0}, merge=False)
auth.update_state_data(USER, {"first_name": "علی", "last_name": "محمدی"})
auth.set_state(USER, "form_filling", {"step": 1}, merge=True)
d = auth.get_state_data(USER)
check("داده بعد از تغییر step حفظ شد", d.get("first_name") == "علی", str(d))
check("step آپدیت شد", d.get("step") == 1)
auth.update_state_data(USER, {"national_id": "1234567891"})
auth.set_state(USER, "form_filling", {"step": 2}, merge=True)
d = auth.get_state_data(USER)
check("سه فیلد همزمان حفظ شدند",
      d.get("first_name") == "علی" and d.get("national_id") == "1234567891", str(d))
check("get_state_data هیچ‌وقت None نیست",
      isinstance(auth.get_state_data(123456789), dict))
auth.clear_state(USER)


print("\n[۴] احراز هویت کاربر جدید")
SENT.clear()
main_mod.handle_start(msg(USER, "/start"))
check("پیام خوش‌آمد", "خوش آمدید" in last_text())
check("state احراز", auth.get_state_name(USER) == "waiting_auth")

main_mod.handle_callback(cb(USER, "auth_otp"))
check("درخواست شماره", "موبایل" in last_text())

main_mod.handle_phone_otp(msg(USER, "09121112233"))
check("کد ارسال شد (حالت تست)", "کد" in last_text())
check("state OTP", auth.get_state_name(USER) == "waiting_otp")

otp_row = database.db_execute(
    "SELECT code FROM otp_codes WHERE bale_user_id=? ORDER BY id DESC LIMIT 1",
    (USER,), fetch="one")
code = otp_row["code"]

main_mod.handle_otp(msg(USER, "000000"))
check("کد اشتباه رد شد", "اشتباه" in last_text())

main_mod.handle_otp(msg(USER, code))
u = auth.get_user(USER)
check("کاربر ساخته شد", bool(u))
check("احراز شد", u and u.get("is_authenticated") == 1)
check("موبایل ذخیره شد", u and u.get("mobile") == "09121112233")
check("کد معرف ساخته شد", bool(u.get("referral_code")))


print("\n[۵] 🐛 باگ ۱ — پیش‌نمایش پروفایل")
SENT.clear()
main_mod.handle_callback(cb(USER, "profile_fill"))
main_mod.handle_callback(cb(USER, "form_go"))

answers = [
    "علی محمدی", "1234567891", "1370/05/12", "👨 مرد",
    "حسن", "زهرا", "تهران", "تهران",
    "خیابان آزادی پلاک ۱۰", "1234567890",
    "کارشناسی", "مهندسی نرم‌افزار", "دانشگاه تهران",
    "برنامه‌نویس", "شرکت نمونه", "ali@example.com", "علاقه‌مند به فناوری",
]
for a in answers:
    main_mod.process_message(msg(USER, a))

# 📸 فاز ۳۸: آخرین مرحلهٔ فرم «عکس پروفایل» است (رسانه‌ای).
#    این تست فقط پاسخ متنی می‌فرستد، پس با «رد کردن» عبور
#    می‌کنیم تا به پیش‌نمایش برسیم.
from bale_api import BTN_SKIP as _SKIP
main_mod.process_message(msg(USER, _SKIP))

preview = last_text()
print("\n----- پیش‌نمایش تولید شده -----")
print(preview[:800])
print("-------------------------------\n")

check("پیش‌نمایش نمایش داده شد", "پیش‌نمایش پروفایل" in preview)
check("🐛 نام درست نمایش داده شد", "علی" in preview and "محمدی" in preview)
check("🐛 کد ملی نمایش داده شد", "1234567891" in preview)
check("🐛 تاریخ تولد نمایش داده شد", "1370/05/12" in preview)
check("🐛 استان نمایش داده شد", "تهران" in preview)
check("🐛 ایمیل نمایش داده شد", "ali@example.com" in preview)
check("🐛 شغل نمایش داده شد", "برنامه‌نویس" in preview)
check("🐛 فیلد اجباری خالی نمانده", "❌ وارد نشده" not in preview)
check("شمارش فیلد درست", "18 از 18" in preview or "17 از 18" in preview, preview[:200])

_last_kb = [s for s in SENT if s["method"] == "sendMessage"][-1]["params"].get("kb") or {}
_kb_labels = [b["text"] for row in _last_kb.get("inline_keyboard", []) for b in row]
check("دکمه ارسال فعال", any("ارسال برای تأیید" in t for t in _kb_labels), str(_kb_labels))


print("\n[۶] 🐛 باگ ۲ — ارسال به ادمین")
SENT.clear()
main_mod.handle_callback(cb(USER, "form_submit"))

admin_msgs = texts_to(SUPER)
admin_text = admin_msgs[-1] if admin_msgs else ""
print("\n----- پیام ارسالی به ادمین -----")
print(admin_text[:700])
print("---------------------------------\n")

check("پیام به ادمین رفت", bool(admin_text))
check("🐛 نام در پیام ادمین", "علی" in admin_text)
check("🐛 کد ملی در پیام ادمین", "1234567891" in admin_text)
check("🐛 موبایل در پیام ادمین", "09121112233" in admin_text)
check("🐛 ایمیل در پیام ادمین", "ali@example.com" in admin_text)
check("🐛 دانشگاه در پیام ادمین", "دانشگاه تهران" in admin_text)
check("تعداد فیلد درست", "تعداد فیلد: 18" in admin_text or "تعداد فیلد: 17" in admin_text)

sub = database.db_execute(
    "SELECT * FROM profile_submissions WHERE bale_user_id=? ORDER BY id DESC LIMIT 1",
    (USER,), fetch="one")
check("درخواست ثبت شد", bool(sub))
pdata = json.loads(sub["profile_data"])
check("🐛 دیتای درخواست خالی نیست", len(pdata) >= 17, f"({len(pdata)} فیلد)")
check("وضعیت کاربر pending", auth.get_user(USER)["profile_status"] == "pending")
check("state پاک شد", auth.get_state(USER) is None)


print("\n[۷] تأیید ادمین و ذخیره در دیتابیس")
SENT.clear()
main_mod.handle_callback(cb(SUPER, f"sa_{sub['id']}"))
u = auth.get_user(USER)
check("وضعیت approved", u["profile_status"] == "approved")
check("🐛 نام در دیتابیس ذخیره شد", u["first_name"] == "علی")
check("🐛 فامیل ذخیره شد", u["last_name"] == "محمدی")
check("🐛 کد ملی ذخیره شد", u["national_id"] == "1234567891")
check("🐛 استان ذخیره شد", u["province"] == "تهران")
check("🐛 دانشگاه ذخیره شد", u["university"] == "دانشگاه تهران")
check("🐛 بیو ذخیره شد", u["bio"] == "علاقه‌مند به فناوری")
check("درصد تکمیل محاسبه شد", u["complete_profile_percent"] >= 90,
      f"({u['complete_profile_percent']}%)")
check("پیام تأیید به کاربر", any("تأیید شد" in t for t in texts_to(USER)))

# تأیید دوباره نباید کار کند
SENT.clear()
main_mod.handle_callback(cb(SUPER, f"sa_{sub['id']}"))
check("تأیید تکراری جلوگیری شد", "قبلاً بررسی" in last_text())


print("\n[۸] نمایش پروفایل")
SENT.clear()
profile_mod.show_profile(CID, USER)
p = last_text()
check("پروفایل نمایش داده شد", "پروفایل من" in p)
check("نام در پروفایل", "علی" in p)
check("وضعیت تأیید شده", "تأیید شده" in p)
check("هیچ فیلد پرشده‌ای ❌ ندارد", "علی" in p and p.count("— ثبت نشده") <= 1)


print("\n[۹] ویرایش پروفایل (prefill)")
SENT.clear()
main_mod.handle_callback(cb(USER, "profile_fill"))
d = auth.get_state_data(USER)
check("مقادیر قبلی بارگذاری شد", d.get("first_name") == "علی", str(list(d.keys()))[:120])
main_mod.handle_callback(cb(USER, "form_go"))
check("مقدار فعلی نمایش داده شد", "مقدار فعلی" in last_text())
# رد کردن همه با skip
for _ in range(len(profile_mod.FORM_STEPS)):
    main_mod.process_message(msg(USER, "⏭️ رد کردن"))
check("پیش‌نمایش بعد از skip پر است", "علی" in last_text())
auth.clear_state(USER)


print("\n[۱۰] بازگشت به مرحله قبل داخل فرم")
SENT.clear()
auth.set_state(USER, profile_mod.STATE_FORM, {"step": 0}, merge=False)
main_mod.process_message(msg(USER, "رضا احمدی"))
check("رفت به مرحله ۲", auth.get_state_data(USER).get("step") == 1)
main_mod.process_message(msg(USER, "🔙 بازگشت"))
check("برگشت به مرحله ۱", auth.get_state_data(USER).get("step") == 0)
check("داده حفظ شد", auth.get_state_data(USER).get("first_name") == "رضا")
auth.clear_state(USER)


print("\n[۱۱] اعتبارسنجی ورودی‌های اشتباه")
SENT.clear()
auth.set_state(USER, profile_mod.STATE_FORM, {"step": 0}, merge=False)
main_mod.process_message(msg(USER, "علی"))
check("نام تک‌کلمه‌ای رد شد", "نام خانوادگی" in last_text())
main_mod.process_message(msg(USER, "علی محمدی"))
main_mod.process_message(msg(USER, "123"))
check("کد ملی کوتاه رد شد", "نامعتبر" in last_text())
main_mod.process_message(msg(USER, "1234567891"))
main_mod.process_message(msg(USER, "سلام"))
check("تاریخ غلط رد شد", "تاریخ نامعتبر" in last_text())
auth.clear_state(USER)


print("\n[۱۲] رد کردن پروفایل با دلیل")
SENT.clear()
auth.set_state(USER, profile_mod.STATE_FORM,
               {"first_name": "تست", "last_name": "تستی",
                "national_id": "1234567891", "birth_date": "1370/01/01",
                "province": "قم", "city": "قم"}, merge=False)
sub_id = profile_mod.submit_profile(CID, USER)
check("درخواست دوم ثبت شد", bool(sub_id))
main_mod.handle_callback(cb(SUPER, f"sr_{sub_id}"))
check("درخواست دلیل شد", "دلیل" in last_text())
main_mod.process_message(msg(SUPER, "کد ملی اشتباه است"))
u = auth.get_user(USER)
check("وضعیت rejected", u["profile_status"] == "rejected")
check("دلیل ذخیره شد", u["rejection_reason"] == "کد ملی اشتباه است")
check("دلیل به کاربر رسید", any("کد ملی اشتباه" in t for t in texts_to(USER)))


print("\n[۱۳] پنل ادمین")
SENT.clear()
admin_mod.show_admin_panel(SUPER, SUPER)
check("پنل ادمین باز شد", "پنل ادمین" in last_text())
admin_mod.show_user_list(SUPER, SUPER, 0)
check("لیست کاربران", "مدیریت کاربران" in last_text())
admin_mod.show_stats(SUPER, SUPER)
check("آمار", "آمار سیستم" in last_text())
admin_mod.show_dbinfo(SUPER, SUPER)
check("اطلاعات دیتابیس", "اطلاعات دیتابیس" in last_text())

# دسترسی کاربر عادی
SENT.clear()
admin_mod.show_admin_panel(USER, USER)
check("کاربر عادی دسترسی ندارد", "دسترسی" in last_text())


print("\n[۱۴] امنیت: حذف کاربر و سوپرادمین")
u_row = auth.get_user(USER)
SENT.clear()
admin_mod.handle_user_action(SUPER, SUPER, f"udq_{u_row['id']}")
check("حذف تأیید دومرحله‌ای دارد", "قابل بازگشت نیست" in last_text())
check("کاربر هنوز حذف نشده", bool(auth.get_user(USER)))

su_row = auth.get_user(SUPER)
SENT.clear()
admin_mod.handle_user_action(SUPER, SUPER, f"ub_{su_row['id']}")
check("سوپرادمین بلاک نمی‌شود", "نمی‌توان" in last_text())
SENT.clear()
admin_mod.handle_user_action(SUPER, SUPER, f"udy_{su_row['id']}")
check("سوپرادمین حذف نمی‌شود", "قابل حذف نیست" in last_text())

# SQL injection در صفحه‌بندی
SENT.clear()
admin_mod.show_user_list(SUPER, SUPER, 99999)
check("صفحه خارج از محدوده کرش نمی‌کند", len(SENT) > 0)


print("\n[۱۵] عضویت اجباری (کانال عمومی و گروه خصوصی)")
SENT.clear()
admin_mod.handle_force_join_callback(SUPER, SUPER, "fj_add")
admin_mod.handle_add_channel(msg(SUPER, "@test_channel"))
chs = auth.get_all_channels()
check("کانال عمومی اضافه شد", len(chs) == 1)
check("در ستون username ذخیره شد", chs[0]["channel_username"] == "@test_channel")

admin_mod.handle_force_join_callback(SUPER, SUPER, "fj_add")
admin_mod.handle_add_channel(msg(SUPER, "-1001234567890"))
chs = auth.get_all_channels()
priv = [c for c in chs if c["is_private"]]
check("گروه خصوصی اضافه شد", len(priv) == 1)
check("🐛 در ستون channel_id ذخیره شد", priv[0]["channel_id"] == "-1001234567890")
check("target درست است", auth.channel_target(priv[0]) == "-1001234567890")

# لینک دعوت
admin_mod.handle_force_join_callback(SUPER, SUPER, f"fj_link_{priv[0]['id']}")
admin_mod.handle_channel_link(msg(SUPER, "https://ble.ir/join/abc123"))
priv2 = [c for c in auth.get_all_channels() if c["is_private"]][0]
check("لینک ذخیره شد", priv2["invite_link"] == "https://ble.ir/join/abc123")

kb = bale_api.kb_force_join([priv2])
check("🐛 دکمه خصوصی از لینک درست استفاده می‌کند",
      kb["inline_keyboard"][0][0].get("url") == "https://ble.ir/join/abc123")

# تکراری
SENT.clear()
admin_mod.handle_force_join_callback(SUPER, SUPER, "fj_add")
admin_mod.handle_add_channel(msg(SUPER, "@test_channel"))
check("کانال تکراری رد شد", any("قبلاً اضافه" in t for t in all_texts()))

# fail-open
saved = bale_api.get_chat_member
auth_get = getattr(auth, "check_user_joined")
import bale_api as _b
_b.get_chat_member = lambda c, u: {"ok": False, "description": "bot is not a member"}
nj = auth.check_user_joined(USER, auth.get_active_channels())
check("خطای سیستمی کاربر را قفل نمی‌کند (fail-open)", len(nj) == 0)
_b.get_chat_member = saved

# پاکسازی
for c in auth.get_all_channels():
    auth.remove_force_channel(c["id"])


print("\n[۱۶] 🐛 ورود از اکسل — خواندن نام")
try:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["نام و نام خانوادگی", "موبایل", "کد ملی", "شهر و استان",
               "ایمیل", "جنسیت", "مقطع تحصیلی"])
    ws.append(["حسن رضایی", "09351112233", 1234567891, "تهران_ری",
               "h@x.com", "مرد", "کارشناسی"])
    ws.append(["زهرا کریمی", 9361112244, "0987654321", "قم-قم",
               "z@x.com", "زن", "دکترا"])
    ws.append(["سید محمد حسینی", "۰۹۳۷۱۱۱۲۲۵۵", None, "اصفهان", "", "", ""])
    ws.append(["بدون شماره", "", "", "", "", "", ""])
    ws.append(["حسن رضایی", "09351112233", "", "", "", "", ""])  # تکراری
    xf = Path(TMP) / "test_import.xlsx"
    wb.save(xf)

    heads, rows = imp_mod.read_file(str(xf))
    mapped, unmapped = imp_mod.map_headers(heads)
    print(f"    نگاشت: {mapped}")
    check("🐛 ستون «نام و نام خانوادگی» شناسایی شد",
          "full_name" in mapped.values(), str(mapped))
    check("ستون موبایل شناسایی شد", "mobile" in mapped.values())
    check("ستون شهر و استان شناسایی شد", "city_province" in mapped.values())
    check("ستون جنسیت شناسایی شد", "gender" in mapped.values())

    st = imp_mod.do_import(str(xf), mapped, SUPER, "test.xlsx")
    print(f"    نتیجه: {st}")
    check("۳ کاربر جدید ثبت شد", st["success"] == 3, str(st))
    check("ردیف بدون موبایل خطا خورد", st["error"] == 1)
    check("ردیف تکراری تشخیص داده شد", st["duplicate"] == 1)

    h = auth.get_user_by_mobile("09351112233")
    check("🐛 نام از اکسل خوانده شد", h and h["first_name"] == "حسن", str(h and h.get("first_name")))
    check("🐛 فامیل از اکسل خوانده شد", h and h["last_name"] == "رضایی")
    check("کد ملی عددی درست شد", h and h["national_id"] == "1234567891")
    check("استان از ترکیبی جدا شد", h and h["province"] == "تهران")
    check("شهر از ترکیبی جدا شد", h and h["city"] == "ری")

    z = auth.get_user_by_mobile("09361112244")
    check("🐛 موبایل عددی (float) درست شد", bool(z), "09361112244 پیدا نشد")
    check("جنسیت زن ثبت شد", z and z["gender"] == "زن")

    s = auth.get_user_by_mobile("09371112255")
    check("موبایل با ارقام فارسی", bool(s))
    check("نام با پیشوند سید", s and s["first_name"] == "سید محمد", str(s and s.get("first_name")))

    # update mode
    wb2 = openpyxl.Workbook()
    ws2 = wb2.active
    ws2.append(["موبایل", "شغل"])
    ws2.append(["09351112233", "معلم"])
    xf2 = Path(TMP) / "upd.xlsx"
    wb2.save(xf2)
    h2, r2 = imp_mod.read_file(str(xf2))
    m2, _ = imp_mod.map_headers(h2)
    st2 = imp_mod.do_import(str(xf2), m2, SUPER, "upd.xlsx", update_existing=True)
    check("حالت به‌روزرسانی کار کرد", st2["updated"] == 1, str(st2))
    check("شغل آپدیت شد", auth.get_user_by_mobile("09351112233")["job_title"] == "معلم")

    # export
    SENT.clear()
    admin_mod.export_users(SUPER, SUPER)
    check("خروجی اکسل ساخته شد", any("خروجی گرفته شد" in t for t in all_texts()))

except ImportError:
    print("  ⚠️ openpyxl نصب نیست — تست اکسل رد شد")


print("\n[۱۷] اتصال کاربر import شده به بله")
SENT.clear()
NEW_BALE = 777888999
main_mod.complete_auth(NEW_BALE, {"id": NEW_BALE, "first_name": "حسن"},
                       "09351112233", "otp")
linked = auth.get_user(NEW_BALE)
check("رکورد قدیمی به بله وصل شد", bool(linked))
check("نام قبلی حفظ شد", linked and linked["first_name"] == "حسن")
check("imported flag حفظ شد", linked and linked["imported"] == 1)
check("پیام خوش برگشتید", any("خوش برگشتید" in t for t in all_texts()))


print("\n[۱۸] مسدود کردن کاربر")
SENT.clear()
database.db_execute("UPDATE users SET is_blocked=1 WHERE bale_user_id=?", (NEW_BALE,))
main_mod.process_message(msg(NEW_BALE, "سلام"))
check("کاربر مسدود پیام مسدودی می‌گیرد", "مسدود" in last_text())
database.db_execute("UPDATE users SET is_blocked=0 WHERE bale_user_id=?", (NEW_BALE,))


print("\n[۱۹] پایداری در برابر ورودی‌های عجیب")
weird = [
    {"update_id": 1, "message": {"from": {"id": USER}, "chat": {"id": USER, "type": "private"}}},
    {"update_id": 2, "message": {"chat": {"id": USER, "type": "private"}, "text": "x"}},
    {"update_id": 3, "callback_query": {"id": "1", "from": {"id": USER}, "data": "unknown_xyz",
                                        "message": {"chat": {"id": USER}}}},
    {"update_id": 4, "callback_query": {"id": "2", "from": {"id": USER}, "data": "uv_abc",
                                        "message": {"chat": {"id": USER}}}},
    {"update_id": 5, "callback_query": {"id": "3", "from": {"id": USER}, "data": "sa_notanumber",
                                        "message": {"chat": {"id": USER}}}},
    {"update_id": 6, "message": {"from": {"id": USER}, "chat": {"id": USER, "type": "private"},
                                 "text": "A" * 5000}},
    {"update_id": 7, "edited_message": {"from": {"id": USER}, "chat": {"id": USER}}},
    {"update_id": 8, "message": {"from": {"id": USER}, "chat": {"id": -100999, "type": "group"},
                                 "text": "/chatid"}},
]
crashed = 0
for w in weird:
    try:
        main_mod.process_update(w)
    except Exception as e:
        crashed += 1
        print(f"      کرش: {e}")
check("هیچ ورودی عجیبی ربات را نمی‌خواباند", crashed == 0, f"({crashed} کرش)")


print("\n[۲۰] شکستن پیام طولانی")
SENT.clear()
bale_api.send = bale_api.send  # نسخه واقعی برای تست split
real_chunks = bale_api._split_text("خط\n" * 3000)
check("پیام طولانی تکه شد", len(real_chunks) > 1, f"({len(real_chunks)} تکه)")
check("هر تکه زیر حد مجاز", all(len(c) <= 4000 for c in real_chunks))


print("\n[۲۱] دستورات عمومی")
SENT.clear()
main_mod.process_message(msg(USER, "/help"))
check("راهنما", "راهنما" in last_text())
main_mod.process_message(msg(USER, "/id"))
check("آیدی", str(USER) in last_text())
main_mod.process_message(msg(USER, "/cancel"))
check("لغو → منوی اصلی",
      any(k in " ".join(all_texts()) for k in ("لغو شد", "منوی اصلی", "ربات نورا")),
      last_text()[:50])
main_mod.process_message(msg(SUPER, "/admin"))
check("پنل ادمین با دستور", "پنل ادمین" in last_text())
main_mod.process_message(msg(USER, "/admin"))
check("کاربر عادی به پنل نمی‌رسد", "دسترسی" in last_text())


print("\n[۲۲] بک‌آپ")
b = database.backup_db()
check("بک‌آپ ساخته شد", b and Path(b).exists())
check("بک‌آپ سالم است", b and os.path.getsize(b) > 1000)


# ==================== نتیجه ====================
print("\n" + "=" * 60)
print(f"✅ موفق: {len(PASS)}    ❌ ناموفق: {len(FAIL)}")
print("=" * 60)
if FAIL:
    print("\nموارد ناموفق:")
    for n, d in FAIL:
        print(f"  ❌ {n}  {d}")
    sys.exit(1)
print("\n🎉 همه تست‌ها پاس شدند!")
sys.exit(0)
