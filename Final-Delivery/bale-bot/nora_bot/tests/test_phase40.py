# -*- coding: utf-8 -*-
"""
🧪 تست فاز ۴۰ — رفع باگ‌های دو دور اسکن

پوشش: B1 · B2 · B3 · B4 · B5 · B6 · B11 · B12 · B14 · B15
      · B16 · تنظیمات بی‌اثر · سبک‌سازی
"""
import os
import re
import sys
import pathlib
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("BOT_TOKEN", "0:test")
os.environ.setdefault("SUPER_ADMIN_ID", "1")
os.environ.setdefault("BOT_USERNAME", "nora_test_bot")

_TDB = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "_p40.db")
for _e in ("", "-wal", "-shm"):
    try:
        os.remove(_TDB + _e)
    except OSError:
        pass
os.environ["DB_PATH"] = _TDB

_ok = _bad = 0
_fails = []


def check(name, cond, extra=""):
    global _ok, _bad
    if cond:
        _ok += 1
    else:
        _bad += 1
        _fails.append(name)
        print(f"  ❌ {name}  {extra}")


print("=" * 58)
print("🧪 فاز ۴۰ — رفع باگ‌ها")
print("=" * 58)

import bale_api as _ba

SENT = []


def _send(cid, text="", kb=None, **k):
    SENT.append({"cid": cid, "text": str(text), "kb": kb})
    return {"ok": True, "result": {"message_id": len(SENT)}}


_ba.api = lambda m, p=None, **k: {"ok": True,
                                  "result": {"message_id": 1}}
_ba.send = _send
_ba.send_or_edit = _send
_ba.send_photo = _ba.send_document = lambda *a, **k: {
    "ok": True, "result": {}}
_ba.get_me = lambda: {"ok": True, "result": {"username": "t"}}

SRC = {f.name: f.read_text(encoding="utf-8")
       for f in pathlib.Path(".").glob("*.py")}

import database
database.init_db()
_main = SRC["main.py"]
_al = dict(re.findall(r"^import (\w+) as (\w+)$", _main, re.M))
_rev = {v: k for k, v in _al.items()}
for _ma, _fn in re.findall(r"^\s{4}(\w+)\.(init_\w+|seed_\w+)\(\)",
                           _main, re.M):
    try:
        getattr(__import__(_rev.get(_ma, _ma)), _fn, lambda: None)()
    except Exception:
        pass

database.db_execute(
    "INSERT OR IGNORE INTO users (bale_user_id, first_name, is_admin,"
    " admin_type, profile_status, is_authenticated) VALUES "
    "(1,'ادمین',1,'super_admin','approved',1)")
database.db_execute(
    "INSERT OR IGNORE INTO users (bale_user_id, first_name,"
    " profile_status, is_authenticated) VALUES "
    "(40500,'کاربر','approved',1)")


def last():
    return SENT[-1]["text"] if SENT else ""


# ══════════════════════════════════════════════════════════
print("\n[B1] 🏆 امتیاز حضور و نظرسنجی")

check("attendance_auto دیگر club.add_points ندارد",
      "from club import add_points" not in SRC["attendance_auto.py"])
check("survey دیگر club.add_points ندارد",
      "from club import add_points" not in SRC["survey.py"])
check("از _award_points استفاده می‌کند",
      "_award_points" in SRC["attendance_auto.py"])
check("survey از دفترکل امتیاز می‌دهد", "post_points" in SRC["survey.py"])
check("خطا لاگ می‌شود (نه pass بی‌صدا)",
      "امتیاز حضور" in SRC["attendance_auto.py"])

# 🔬 زنده: تابع واقعاً کار می‌کند؟
import attendance as att
_p0 = (database.db_execute("SELECT total_points FROM users WHERE"
                           " bale_user_id=40500", fetch="one")
       or {}).get("total_points") or 0
_sid40 = database.db_execute(
    "INSERT INTO attendance_sessions (event_id, title, session_code, points) "
    "VALUES (1, 'جلسهٔ آزمایشی ۴۰', 'S40CODE', 15)")
att._award_points(40500, 15, _sid40)          # دفترکل: کلید (جلسه، کاربر)
att._award_points(40500, 15, _sid40)          # تکرار → بدون اثر دوم
_p1 = (database.db_execute("SELECT total_points FROM users WHERE"
                           " bale_user_id=40500", fetch="one")
       or {}).get("total_points") or 0
check("🔑 امتیاز واقعاً اضافه می‌شود (یک‌بار)", _p1 == _p0 + 15,
      f"{_p0}→{_p1}")

# ══════════════════════════════════════════════════════════
print("[B2] 🔢 normalize_digits از auth")

check("certbatch از auth می‌خواند",
      "from auth import normalize_digits" in SRC["certbatch.py"])
check("eventcert از auth می‌خواند",
      "from auth import normalize_digits" in SRC["eventcert.py"])
check("دیگر از config نمی‌خواند",
      "from config import normalize_digits" not in
      SRC["certbatch.py"] + SRC["eventcert.py"])

from auth import normalize_digits
check("🔑 ارقام فارسی تبدیل می‌شوند",
      int(normalize_digits("۱۲۳")) == 123)

# ══════════════════════════════════════════════════════════
print("[B3] 🛡️ شناسهٔ حذف‌شده کرش نمی‌کند")

import certbatch
import certissue as ci

for nm, fn in (("certbatch.export_status",
                lambda: certbatch.export_status(1, 1, 999999)),
               ("certissue.show_stats",
                lambda: ci.show_stats(1, 1, 999999))):
    SENT.clear()
    try:
        fn()
        check(f"{nm} پیام مهربان می‌دهد",
              "وجود ندارد" in last(), last()[:40])
    except Exception as e:
        check(f"{nm} — {type(e).__name__}", False)

# ══════════════════════════════════════════════════════════
print("[B4] 🛡️ نگهبان شناسه — ۹۸ نقطه رفع شد")

import main as M

check("فهرست پیشوند عددی ساخته می‌شود",
      hasattr(M, "_NUM_ONLY_PREFIXES"))
check("فهرست خالی نیست", len(M._NUM_ONLY_PREFIXES) > 100,
      str(len(getattr(M, "_NUM_ONLY_PREFIXES", []))))
check("پیشوندهای two کنار گذاشته شدند",
      "evmm_" not in M._NUM_ONLY_PREFIXES)


def cb(uid, data):
    return {"id": "1", "from": {"id": uid}, "message":
            {"chat": {"id": uid}, "message_id": 1}, "data": data}


BAD_CBS = ["fbrdel_abc", "ffcy_xyz", "sv_xl_abc", "ffy_1_abc",
           "cc_pg_abc", "evpay_abc", "fbflt_999999",
           "cc_pw_999999", "cc_sets_abc", "ffo_999999",
           "cbT_999999", "evcT_999999"]
crash = []
for c in BAD_CBS:
    SENT.clear()
    try:
        M.handle_callback(cb(1, c))
    except Exception as e:
        crash.append((c, f"{type(e).__name__}: {str(e)[:40]}"))
check(f"🔑 {len(BAD_CBS)} callback خراب بدون استثنا",
      not crash, str(crash[:3]))

SENT.clear()
M.handle_callback(cb(1, "fbrdel_abc"))
check("پیام «دیگر معتبر نیست» می‌آید",
      "معتبر" in last() or "منوی اصلی" in last(), last()[:40])

# callback سالم نباید مسدود شود
SENT.clear()
M.handle_callback(cb(1, "back_main"))
check("callback سالم کار می‌کند",
      "معتبر نیست" not in last(), last()[:40])

# ══════════════════════════════════════════════════════════
print("[B5/B6] 🔧 موارد کوچک")

import certverify as cv
SENT.clear()
try:
    cv.show_validity(1, 1, 1, "abc")
    check("show_validity با ورودی خراب امن است", True)
except Exception as e:
    check(f"show_validity — {type(e).__name__}", False)

check("doctor_test دیگر بی‌هندلر نیست",
      '"doctor_test"' not in SRC["doctor.py"])

# ══════════════════════════════════════════════════════════
print("[B11] ⏰ تست مستقل از ساعت")

_t20 = pathlib.Path("tests/test_phase20.py").read_text(
    encoding="utf-8")
check("کمپین quiet_hours خاموش می‌شود",
      "SET quiet_hours=0" in _t20)
check("بازهٔ سکوت ۰ تا ۲۴ است",
      '"ads_quiet_end", "24"' in _t20)

import ads
_h = datetime.datetime.now().hour
database.set_setting("ads_quiet_on", "1", "", "ads")
database.set_setting("ads_quiet_start", "0", "", "ads")
database.set_setting("ads_quiet_end", "24", "", "ads")
database.clear_settings_cache()
check("🔑 بازهٔ ۰..۲۴ همیشه سکوت است (هر ساعتی)",
      ads.in_quiet_hours(), f"ساعت={_h}")
database.db_execute("DELETE FROM settings WHERE key LIKE 'ads_quiet%'")
database.clear_settings_cache()

# ══════════════════════════════════════════════════════════
print("[B12] 📐 سقف ۱۰ ردیف")

import ast
over = []
for f in pathlib.Path(".").glob("*.py"):
    try:
        t = ast.parse(f.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for n in ast.walk(t):
        if not isinstance(n, ast.Dict):
            continue
        for k, v in zip(n.keys, n.values):
            if isinstance(k, ast.Constant) and \
                    k.value == "inline_keyboard" and \
                    isinstance(v, ast.List) and len(v.elts) > 10:
                over.append(f"{f.name}:{n.lineno} ({len(v.elts)})")
check(f"🔑 هیچ کیبورد ثابتی >۱۰ ردیف ({over})", not over)

import forms as F
check("show_advanced2 ساخته شد", hasattr(F, "show_advanced2"))
check("روتر fbadv2_ دارد", "fbadv2_" in _main)
check("ترتیب fbadv2 قبل از fbadv",
      _main.index('startswith("fbadv2_")') <
      _main.index('startswith("fbadv_")'))

# ══════════════════════════════════════════════════════════
print("[B14/B15/B16] ⚙️ تنظیمات بی‌اثر")

import certcenter as cc

check("cc_link_on خوانده می‌شود",
      'get_setting("cc_link_on"' in SRC["certcenter.py"])
check("cc_notify_batch خوانده می‌شود",
      'get_setting("cc_notify_batch"' in SRC["certcenter.py"])
check("cc_lazy_build خوانده می‌شود",
      'get_setting("cc_lazy_build"' in SRC["certcenter.py"])
check("تأخیر بین اعلان‌ها هست",
      "_t.sleep" in SRC["certcenter.py"])

# 🔬 set_value برش می‌دهد
import certgen as cg
cg.init_cert_tables()
cc.init_tables()
_tid = database.db_execute(
    "INSERT INTO cert_templates (name,file_path,kind,is_active)"
    " VALUES ('t','/tmp/none.docx','docx',1)")
_iid = cc.create_issue(1, "تست برش", _tid)
cc.set_value(_iid, "event", "ب" * 9000)
_v = cc.issue_values(cc.get_issue(_iid)).get("event", "")
check("🔑 set_value برش می‌دهد", len(_v) <= 300, str(len(_v)))

# 🔬 لینک با خاموش‌بودن تنظیم
database.set_setting("cc_link_on", "0", "", "certificate")
database.clear_settings_cache()
check("🔑 خاموش‌کردن cc_link_on لینک را می‌بندد",
      cc.link_of(cc.get_issue(_iid)) == "")
database.set_setting("cc_link_on", "1", "", "certificate")
database.clear_settings_cache()

# ══════════════════════════════════════════════════════════
print("[تنظیمات] 🔧 سریال و خروجی")

database.set_setting("cert_serial_prefix", "HELAL", "", "certificate")
database.clear_settings_cache()
check("🔑 پیشوند سریال اعمال می‌شود",
      att.gen_serial().startswith("HELAL-"), att.gen_serial())
database.set_setting("cert_serial_prefix", "NORA", "", "certificate")
database.clear_settings_cache()
check("برگشت به پیش‌فرض", att.gen_serial().startswith("NORA-"))

check("generate از تنظیمات خروجی می‌خواند",
      'get_setting(sk, "1" if k != "docx" else "0")'
      in SRC["certgen.py"])
check("want پیش‌فرض None شد",
      "def generate(mapping, tpl=None, want=None)"
      in SRC["certgen.py"])

# ══════════════════════════════════════════════════════════
print("[حضور] 🎯 بستن حضورهای باز")

check("close_open_presence وصل شد",
      "close_open_presence" in SRC["attendance.py"])
check("فقط هنگام بستن جلسه", "if not new:" in SRC["attendance.py"])

import attendance_auto as aa
check("تابع وجود دارد", hasattr(aa, "close_open_presence"))
try:
    aa.close_open_presence(999999)
    check("با جلسهٔ ناموجود امن است", True)
except Exception as e:
    check(f"close_open_presence — {type(e).__name__}", False)

# ══════════════════════════════════════════════════════════
print("[سبک‌سازی] 🧹 helpers مشترک")

import helpers
for fn in ("guard_admin", "guard_section", "fa", "en", "short",
           "num_or", "bar"):
    check(f"helpers.{fn}", hasattr(helpers, fn))

check("num_or با ورودی خراب", helpers.num_or("abc", 7) == 7)
check("num_or با محدوده", helpers.num_or("500", 0, hi=100) == 100)
check("short برش می‌دهد", len(helpers.short("ا" * 60, 20)) == 20)
check("fa ارقام", helpers.fa("123") == "۱۲۳")
check("bar نوار", len(helpers.bar(50, 10)) == 10)

_shared = sum(1 for f in ("attendance_auto.py", "certbatch.py",
                          "certverify.py", "eventcert.py",
                          "survey.py")
              if "from helpers import guard_admin" in SRC.get(f, ""))
check(f"🔑 {_shared} ماژول به helpers وصل شدند", _shared == 5)

check("_place_qr حذف شد", "def _place_qr" not in SRC["certgen.py"])
check("jalali.now_str حذف شد",
      "def now_str" not in SRC["jalali.py"])

# ══════════════════════════════════════════════════════════
print("[یکپارچگی] 🔗 چیزی نشکسته")

check("guard_admin کار می‌کند",
      helpers.guard_admin(1, 1) is True)
SENT.clear()
check("کاربر عادی رد می‌شود",
      helpers.guard_admin(40500, 40500) is False)
check("پیام داده شد", "دسترسی" in last())

import certverify
check("certverify._guard کار می‌کند",
      certverify._guard(1, 1) is True)
check("certverify._fa کار می‌کند", certverify._fa(5) == "۵")

print()
print("=" * 58)
print(f"✅ موفق: {_ok}   ❌ ناموفق: {_bad}")
if _fails:
    print("\nناموفق‌ها:")
    for f in _fails:
        print("  •", f)
print("=" * 58)

try:
    database.close_db()
except Exception:
    pass
for _e in ("", "-wal", "-shm"):
    try:
        os.remove(_TDB + _e)
    except OSError:
        pass

sys.exit(1 if _bad else 0)
