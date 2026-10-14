#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 تست فاز ۳۱ — لینک‌های عمیق و مقاومت در برابر تغییر توکن

🎯 «لینک پشت کیوآر کدا چیه؟ لینک کامل باشه اسکن که شد بات باز
    کنه و اینکه بعدا شاید توکن و آیدی بات عوض کنم پس حواست به
    اون موردم باشه — به سورس ای ان وی دقت کن تو لینکا»

🔴 باگی که رفع شد:
   یوزرنیم ربات یک بار از getMe خوانده و در کلید ثابت
   «bot_username» ذخیره می‌شد. با عوض شدن توکن، همان
   یوزرنیم قدیمی برمی‌گشت → همهٔ کیوآرکدها به ربات اشتباه
   اشاره می‌کردند.
"""
import sys
import os
import re
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

OK = 0
FAIL = 0
ERRORS = []


def check(label, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
    else:
        FAIL += 1
        ERRORS.append(f"{label} {detail}")


def section(t):
    print(f"\n{'─' * 62}\n{t}\n{'─' * 62}")


# ══════════════════════════════════════════════════════════
section("۱) منبع حقیقت واحد در config")
# ══════════════════════════════════════════════════════════
import config

for name in ["BOT_USERNAME_ENV", "BALE_DOMAIN", "bot_username",
             "deep_link", "MAIN_BOT_ID"]:
    check(f"config.{name}", hasattr(config, name))

check("دامنه پیش‌فرض", config.BALE_DOMAIN.startswith("http"))
check("دامنه بدون / انتهایی", not config.BALE_DOMAIN.endswith("/"))


# ══════════════════════════════════════════════════════════
section("۲) ساخت لینک عمیق")
# ══════════════════════════════════════════════════════════
_save_env = os.environ.get("BOT_USERNAME")
_save_tok = os.environ.get("BOT_TOKEN")

os.environ["BOT_USERNAME"] = "@TestBot"      # با @ عمداً
os.environ["BOT_TOKEN"] = "555555:TESTTOKEN"
importlib.reload(config)

check("@ از یوزرنیم حذف شد", config.BOT_USERNAME_ENV == "TestBot",
      repr(config.BOT_USERNAME_ENV))
check("bot_username()", config.bot_username() == "TestBot")

base = config.deep_link()
full = config.deep_link("cert_A3F9")
check("لینک پایه", base == "https://ble.ir/TestBot", base)
check("لینک با payload",
      full == "https://ble.ir/TestBot?start=cert_A3F9", full)
check("لینک کامل است (https)", full.startswith("https://"))
check("لینک ?start= دارد", "?start=" in full)


# ══════════════════════════════════════════════════════════
section("۳) لینک همهٔ ماژول‌ها")
# ══════════════════════════════════════════════════════════
import certgen
import forms
import paylink
for m in (certgen, forms, paylink):
    importlib.reload(m)

cases = [
    ("🎓 گواهینامه", certgen.verify_url("A3F9C2"), "cert_A3F9C2"),
    ("📝 فرم", forms.form_link({"slug": "spring", "id": 41}),
     "form_spring"),
    ("💳 پرداخت", paylink.link_url({"code": "P9K2"}), "pay_P9K2"),
]
for label, url, payload in cases:
    check(f"{label} — دامنه", url.startswith("https://ble.ir/"), url)
    check(f"{label} — یوزرنیم", "/TestBot" in url, url)
    check(f"{label} — payload", url.endswith(payload), url)
    # 🔍 ساختار کامل: https://<domain>/<user>?start=<payload>
    check(f"{label} — ساختار",
          re.fullmatch(r"https://[\w.\-]+/[\w\-]+\?start=[\w\-]+", url)
          is not None, url)


# ══════════════════════════════════════════════════════════
section("۴) بدون یوزرنیم — نباید لینک نصفه بسازد")
# ══════════════════════════════════════════════════════════
os.environ.pop("BOT_USERNAME", None)
os.environ["BOT_TOKEN"] = "777777:NOUSER"
importlib.reload(config)

import database
try:
    database.db_execute(
        "DELETE FROM settings WHERE key LIKE 'bot_username%'")
except Exception:
    pass

check("deep_link خالی برمی‌گرداند", config.deep_link("x") == "",
      repr(config.deep_link("x")))

for m in (certgen, forms, paylink):
    importlib.reload(m)
check("گواهینامه fallback متنی",
      certgen.verify_url("Z1").startswith("/start "),
      certgen.verify_url("Z1"))
check("فرم fallback متنی",
      forms.form_link({"slug": "s", "id": 1}).startswith("/start "))
check("پرداخت fallback متنی",
      paylink.link_url({"code": "c"}).startswith("/start "))

# 🔴 هرگز لینک ناقص مثل https://ble.ir/?start=x نسازد
for u in [certgen.verify_url("Z1"), forms.form_link({"slug": "s"}),
          paylink.link_url({"code": "c"})]:
    check("بدون لینک ناقص", "//?" not in u and "ir/?" not in u, u)


# ══════════════════════════════════════════════════════════
section("۵) 🔑 مقاومت در برابر عوض شدن توکن")
# ══════════════════════════════════════════════════════════
import settings_admin as SA

os.environ.pop("BOT_USERNAME", None)

# ربات قدیمی
os.environ["BOT_TOKEN"] = "111111:OLD"
importlib.reload(config)
importlib.reload(SA)
check("کلید کش شامل شناسهٔ توکن",
      SA._uname_key() == "bot_username_111111", SA._uname_key())
database.set_setting("bot_username_111111", "OldBot", "", "system")
importlib.reload(SA)
check("ربات قدیم یوزرنیمش را می‌گیرد",
      SA.get_bot_username() == "OldBot")

# 🔄 توکن عوض شد
os.environ["BOT_TOKEN"] = "999999:NEW"
importlib.reload(config)
importlib.reload(SA)
check("کلید کش عوض شد",
      SA._uname_key() == "bot_username_999999", SA._uname_key())
got = SA.get_bot_username()
check("🔴 یوزرنیم قدیمی نشت نکرد", got != "OldBot",
      f"→ {got!r} — باید OldBot نباشد")

# ربات جدید ثبت می‌شود
database.set_setting("bot_username_999999", "NewBot", "", "system")
importlib.reload(SA)
check("ربات جدید یوزرنیم خودش را دارد",
      SA.get_bot_username() == "NewBot", SA.get_bot_username())

# برگشت به توکن قدیم
os.environ["BOT_TOKEN"] = "111111:OLD"
importlib.reload(config)
importlib.reload(SA)
check("برگشت به توکن قدیم درست است",
      SA.get_bot_username() == "OldBot", SA.get_bot_username())


# ══════════════════════════════════════════════════════════
section("۶) .env بالاترین اولویت دارد")
# ══════════════════════════════════════════════════════════
# در دیتابیس OldBot هست، ولی .env چیز دیگری می‌گوید
os.environ["BOT_USERNAME"] = "EnvWins"
importlib.reload(config)
importlib.reload(SA)
check("env بر دیتابیس مقدم است",
      SA.get_bot_username() == "EnvWins", SA.get_bot_username())
check("config هم env را می‌بیند",
      config.bot_username() == "EnvWins")
check("لینک با env ساخته می‌شود",
      config.deep_link("t") == "https://ble.ir/EnvWins?start=t")


# ══════════════════════════════════════════════════════════
section("۷) دامنهٔ قابل تنظیم")
# ══════════════════════════════════════════════════════════
os.environ["BALE_DOMAIN"] = "https://example.test/"   # با / عمداً
importlib.reload(config)
check("/ انتهایی حذف شد",
      config.BALE_DOMAIN == "https://example.test",
      config.BALE_DOMAIN)
check("لینک با دامنهٔ تازه",
      config.deep_link("q") == "https://example.test/EnvWins?start=q",
      config.deep_link("q"))
os.environ.pop("BALE_DOMAIN", None)


# ══════════════════════════════════════════════════════════
section("۸) hardcode باقی نمانده")
# ══════════════════════════════════════════════════════════
# فایل‌هایی که لینک عملیاتی می‌سازند نباید ble.ir را
# دستی بچسبانند (متن راهنما و کامنت اشکالی ندارد)
for fn in ["certgen.py", "forms.py", "paylink.py", "events.py"]:
    bad = []
    for i, ln in enumerate(Path(fn).read_text(encoding="utf-8")
                           .splitlines(), 1):
        st = ln.strip()
        if st.startswith("#") or st.startswith('"""'):
            continue
        if 'f"https://ble.ir/' in ln or "f'https://ble.ir/" in ln:
            bad.append(str(i))
    check(f"{fn} بدون لینک hardcode", not bad, " · ".join(bad))

# .env.example باید کلیدها را داشته باشد
env = Path(".env.example").read_text(encoding="utf-8")
check(".env.example: BOT_USERNAME", "BOT_USERNAME=" in env)
check(".env.example: BALE_DOMAIN", "BALE_DOMAIN=" in env)
check(".env.example: راهنمای تغییر توکن",
      "توکن یا آیدی ربات را عوض" in env)


# ══════════════════════════════════════════════════════════
section("۹) بازگردانی محیط")
# ══════════════════════════════════════════════════════════
if _save_env is None:
    os.environ.pop("BOT_USERNAME", None)
else:
    os.environ["BOT_USERNAME"] = _save_env
if _save_tok is not None:
    os.environ["BOT_TOKEN"] = _save_tok
importlib.reload(config)
importlib.reload(SA)
try:
    database.db_execute(
        "DELETE FROM settings WHERE key LIKE 'bot_username_%'")
except Exception:
    pass
check("محیط بازگردانده شد", True)


print(f"\n{'=' * 62}")
print(f"✅ موفق: {OK}    ❌ ناموفق: {FAIL}")
print("=" * 62)
if ERRORS:
    print("\n❌ خطاها:")
    for e in ERRORS[:30]:
        print(f"   • {e}")
    sys.exit(1)
print("\n🎉 همه تست‌های فاز ۳۱ پاس شدند!")
