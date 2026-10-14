# -*- coding: utf-8 -*-
"""
🧪 تست فاز ۳۸ — پروفایل: عکس، پارامترهای رسانه‌ای، منوی مرتب

🎯 درخواست شما:
   «افزودن عکس تو منو پروفایل من بره زیر مجموع تکمیل پروفایل و
    تنظیمات و کنترلش بره تو قسمت مربوطه تو مدیریت کاربران که
    مثل بقیه پارامتر ها متن و اجباری و اختیاری بودن پارامتر های
    پروفایل کاربر قابل تغییر و تنظیم باشه»

   «قسمت پارامتر های پروفایل بشه متن و رسانه هم بهش سوالات
    پروفایل اضافه کرد — این مورد هم برای سوالات پیش فرض هم برای
    سوالاتی که از لیست اضافه میکنم»

   «قسمت پروفایل من تو منو کاربر خیلی شلخته‌س، جمع و جور و
    جامع‌تر و شیک‌ترش کن»
"""
import os
import re
import sys
import json
import pathlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("BOT_TOKEN", "0:test")
os.environ.setdefault("SUPER_ADMIN_ID", "1")
os.environ.setdefault("BOT_USERNAME", "nora_test_bot")

# 🧪 دیتابیس اختصاصی — مستقل از ترتیب اجرا
_TDB = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "_p38.db")
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
print("🧪 فاز ۳۸ — پروفایل: عکس · رسانه · منوی مرتب")
print("=" * 58)

# 🌐 شبکه را ماک کن
import bale_api as _ba

SENT = []


def _fake_api(m, p=None, **k):
    SENT.append({"method": m, "params": p or {}})
    if m == "getMe":
        return {"ok": True, "result": {"username": "nora_test_bot"}}
    return {"ok": True, "result": {"message_id": len(SENT)}}


def _fake_send(cid, text="", kb=None, **k):
    SENT.append({"method": "sendMessage",
                 "params": {"chat_id": cid, "text": text, "kb": kb}})
    return {"ok": True, "result": {"message_id": len(SENT)}}


def _fake_file(cid, path=None, caption="", **k):
    SENT.append({"method": "sendFile", "params": {"chat_id": cid}})
    return {"ok": True, "result": {"message_id": len(SENT)}}


_ba.api = _fake_api
_ba.send = _fake_send
_ba.send_or_edit = _fake_send
_ba.send_photo = _fake_file
_ba.send_document = _fake_file

SRC = {f.name: f.read_text(encoding="utf-8")
       for f in pathlib.Path(".").glob("*.py")}

import database
import profile as pf
import admin as ad

database.init_db()
pf.init_profile_extra()


def _last():
    for s in reversed(SENT):
        if s["method"] == "sendMessage":
            return s["params"].get("text") or ""
    return ""


def _last_kb():
    for s in reversed(SENT):
        if s["method"] == "sendMessage" and s["params"].get("kb"):
            return s["params"]["kb"]
    return {}


def _btn_texts(kb):
    out = []
    for row in (kb or {}).get("inline_keyboard", []):
        for b in row:
            out.append(b.get("text", ""))
    return out


# ══════════════════════════════════════════════════════════
print("\n[۱] 📸 عکس یک پارامتر شد")

check("عکس در FORM_STEPS هست",
      any(s["key"] == "profile_photo" for s in pf.FORM_STEPS))
_ps = next(s for s in pf.FORM_STEPS if s["key"] == "profile_photo")
check("نوعش «photo» است", _ps.get("ftype") == "photo")
check("پیش‌فرض اختیاری است", _ps.get("required") is False)
check("برچسب فارسی دارد", "profile_photo" in pf.LABELS)
check("در DB_FIELDS نیست (متنی نیست)",
      "profile_photo" not in pf.DB_FIELDS)
check("MEDIA_TYPES تعریف شده", len(pf.MEDIA_TYPES) == 4)
for t in ("photo", "document", "voice", "video"):
    check(f"نوع رسانه {t}", t in pf.MEDIA_TYPES)
check("is_media_step عکس را می‌شناسد", pf.is_media_step(_ps))
check("is_media_step متن را نمی‌گیرد",
      not pf.is_media_step({"key": "bio"}))
check("is_media_step با None امن است", not pf.is_media_step(None))

# ── ادمین کنترلش دارد ──
print("[۲] ⚙️ کنترل عکس در پنل مدیریت")

check("عکس پیش‌فرض روشن است", pf.field_on("profile_photo"))
database.set_setting("pf_profile_photo_on", "0", "", "profile")
check("می‌شود خاموشش کرد", not pf.field_on("profile_photo"))
check("خاموش → از مراحل حذف می‌شود",
      not any(s["key"] == "profile_photo" for s in pf.active_steps()))
database.set_setting("pf_profile_photo_on", "1", "", "profile")
check("دوباره روشن می‌شود", pf.field_on("profile_photo"))
check("روشن → در مراحل هست",
      any(s["key"] == "profile_photo" for s in pf.active_steps()))

check("پیش‌فرض اختیاری", not pf.field_required("profile_photo", False))
database.set_setting("pf_profile_photo_req", "1", "", "profile")
check("می‌شود اجباری کرد",
      pf.field_required("profile_photo", False))
_st = next(s for s in pf.active_steps()
           if s["key"] == "profile_photo")
check("در active_steps اجباری شد", _st["required"])
database.set_setting("pf_profile_photo_req", "0", "", "profile")

# ══════════════════════════════════════════════════════════
print("[۳] 💬 متن پرسش قابل تغییر")

check("تابع prompt_of هست", hasattr(pf, "prompt_of"))
check("تابع set_prompt هست", hasattr(pf, "set_prompt"))
check("تابع field_type هست", hasattr(pf, "field_type"))

check("بدون تنظیم → پیش‌فرض",
      pf.prompt_of("bio", "متن پیش‌فرض") == "متن پیش‌فرض")
pf.set_prompt("bio", "📝 چند خط دربارهٔ خودتان بنویسید:")
check("متن دلخواه ثبت شد",
      pf.prompt_of("bio", "x") == "📝 چند خط دربارهٔ خودتان بنویسید:")
_bs = next(s for s in pf.active_steps() if s["key"] == "bio")
check("active_steps متن تازه را می‌دهد",
      _bs["prompt"] == "📝 چند خط دربارهٔ خودتان بنویسید:")

# متن عکس هم
pf.set_prompt("profile_photo", "📸 عکس پرسنلی خود را بفرستید:")
_ps2 = next(s for s in pf.active_steps()
            if s["key"] == "profile_photo")
check("متن پرسش عکس عوض شد",
      _ps2["prompt"] == "📸 عکس پرسنلی خود را بفرستید:")
check("نوع رسانه‌اش حفظ شد", _ps2.get("ftype") == "photo")

ad._forget_setting("pf_bio_q")
check("حذف تنظیم → برگشت به پیش‌فرض",
      pf.prompt_of("bio", "پیش‌فرض") == "پیش‌فرض")

check("field_type عکس", pf.field_type("profile_photo") == "photo")
check("field_type متن", pf.field_type("bio") == "short_text")
check("field_type ناشناخته", pf.field_type("nope") == "short_text")

# ══════════════════════════════════════════════════════════
print("[۴] ➕ افزودن پرسش دلخواه — متنی و رسانه‌ای")

for fn in ("show_param_edit", "start_param_text", "reset_param_text",
           "start_new_param", "start_new_media", "handle_param_text"):
    check(f"تابع پنل {fn}", hasattr(ad, fn))
check("state متن", hasattr(ad, "STATE_PF_TEXT"))
check("state پرسش تازه", hasattr(ad, "STATE_PF_NEW"))

from auth import set_state, get_state_name, clear_state

# 🔬 افزودن پرسش متنی
database.db_execute(
    "INSERT OR IGNORE INTO users (bale_user_id, first_name, "
    "is_admin, admin_type, profile_status) "
    "VALUES (1,'ادمین',1,'super_admin','approved')")
set_state(1, ad.STATE_PF_NEW, {"ftype": "short_text"}, merge=False)
SENT.clear()
ad.handle_param_text({"from": {"id": 1}, "chat": {"id": 1},
                      "text": "کد پرسنلی"})
_cf = pf.custom_fields()
check("پرسش متنی اضافه شد",
      any(c.get("name") == "کد پرسنلی" for c in _cf), f"{_cf}")
_new = next((c for c in _cf if c.get("name") == "کد پرسنلی"), {})
check("کلید لاتین ساخته شد",
      bool(re.match(r"^[a-z][a-z0-9_]*$", _new.get("key", ""))),
      _new.get("key"))
check("نوعش متنی است", _new.get("ftype") == "short_text")
check("خودکار روشن شد", pf.field_on(_new.get("key")))
check("در مراحل ظاهر شد",
      any(s["key"] == _new["key"] for s in pf.active_steps()))

# 🔬 افزودن پرسش رسانه‌ای
set_state(1, ad.STATE_PF_NEW, {"ftype": "photo"}, merge=False)
SENT.clear()
ad.handle_param_text({"from": {"id": 1}, "chat": {"id": 1},
                      "text": "کارت ملی"})
_cf2 = pf.custom_fields()
_med = next((c for c in _cf2 if c.get("name") == "کارت ملی"), {})
check("پرسش رسانه‌ای اضافه شد", bool(_med))
check("نوعش عکس است", _med.get("ftype") == "photo")
check("آیکن عکس گرفت", _med.get("icon") == "📸")
_ms = next((s for s in pf.active_steps()
            if s["key"] == _med.get("key")), None)
check("در مراحل رسانه‌ای است", _ms and pf.is_media_step(_ms))

# 🔬 کلید تکراری نمی‌سازد
set_state(1, ad.STATE_PF_NEW, {"ftype": "short_text"}, merge=False)
ad.handle_param_text({"from": {"id": 1}, "chat": {"id": 1},
                      "text": "کد پرسنلی"})
_keys = [c.get("key") for c in pf.custom_fields()]
check("کلیدها یکتا هستند", len(_keys) == len(set(_keys)), f"{_keys}")

# 🔬 نام خیلی کوتاه رد می‌شود
set_state(1, ad.STATE_PF_NEW, {"ftype": "short_text"}, merge=False)
_n0 = len(pf.custom_fields())
ad.handle_param_text({"from": {"id": 1}, "chat": {"id": 1}, "text": "ا"})
check("نام کوتاه رد شد", len(pf.custom_fields()) == _n0)
check("state باز مانده تا دوباره بنویسد",
      get_state_name(1) == ad.STATE_PF_NEW)
clear_state(1)

# 🔬 ویرایش متن یک پرسش سفارشی
set_state(1, ad.STATE_PF_TEXT, {"key": _new["key"]}, merge=False)
ad.handle_param_text({"from": {"id": 1}, "chat": {"id": 1},
                      "text": "🔢 کد پرسنلی خود را وارد کنید:"})
check("متن سفارشی ثبت شد",
      pf.prompt_of(_new["key"], "x") ==
      "🔢 کد پرسنلی خود را وارد کنید:")

# 🔬 بازگشت به پیش‌فرض با «-»
set_state(1, ad.STATE_PF_TEXT, {"key": _new["key"]}, merge=False)
ad.handle_param_text({"from": {"id": 1}, "chat": {"id": 1}, "text": "-"})
check("با «-» به پیش‌فرض برگشت",
      pf.prompt_of(_new["key"], "پیش‌فرض") == "پیش‌فرض")

# 🔬 انصراف
set_state(1, ad.STATE_PF_TEXT, {"key": _new["key"]}, merge=False)
ad.handle_param_text({"from": {"id": 1}, "chat": {"id": 1},
                      "text": "❌ انصراف"})
check("انصراف state را پاک کرد", not get_state_name(1))

check("ورودی بی‌ربط رد می‌شود",
      ad.handle_param_text({"from": {"id": 1}, "chat": {"id": 1},
                            "text": "سلام"}) is False)

# ══════════════════════════════════════════════════════════
print("[۵] 🖥️ پنل پارامترها — نمایش")

SENT.clear()
ad.show_profile_params(1, 1)
_t = _last()
_kb = _last_kb()
check("صفحه باز شد", "پارامترهای پروفایل" in _t)
check("عکس در فهرست هست", "عکس پروفایل" in _t)
check("پرسش سفارشی هست", "کد پرسنلی" in _t)
check("دکمهٔ افزودن متنی", any("پرسش متنی" in b
                               for b in _btn_texts(_kb)))
check("دکمهٔ افزودن رسانه", any("رسانه" in b
                                for b in _btn_texts(_kb)))
check("دکمهٔ ویرایش متن (✏️)",
      any("✏️" in b for b in _btn_texts(_kb)))
_cbs = [b.get("callback_data", "")
        for r in _kb.get("inline_keyboard", []) for b in r]
check("callback ویرایش هست", any(c.startswith("pfv_") for c in _cbs))
check("callback روشن/خاموش عکس",
      "pfo_profile_photo" in _cbs)

# ── صفحهٔ یک پارامتر ──
SENT.clear()
ad.show_param_edit(1, 1, "profile_photo")
_t2 = _last()
check("صفحهٔ عکس باز شد", "عکس پروفایل" in _t2)
check("نوعش نشان داده شد", "📸" in _t2)
check("متن پرسش نشان داده شد", "متن پرسش" in _t2)
_kb2 = _last_kb()
_cb2 = [b.get("callback_data", "")
        for r in _kb2.get("inline_keyboard", []) for b in r]
check("دکمهٔ تغییر متن", any(c.startswith("pfq_") for c in _cb2))
check("دکمهٔ روشن/خاموش", any(c.startswith("pfo_") for c in _cb2))
check("دکمهٔ اجباری", any(c.startswith("pfr_") for c in _cb2))

SENT.clear()
ad.show_param_edit(1, 1, "full_name")
check("نام کامل قفل است", "همیشه فعال" in _last())
_kbf = _last_kb()
_cbf = [b.get("callback_data", "")
        for r in _kbf.get("inline_keyboard", []) for b in r]
check("نام کامل دکمهٔ خاموش ندارد",
      not any(c == "pfo_full_name" for c in _cbf))

SENT.clear()
ad.show_param_edit(1, 1, "nope_xyz")
check("پارامتر ناموجود پیام می‌دهد", "یافت نشد" in _last())

# ══════════════════════════════════════════════════════════
print("[۶] 👤 منوی پروفایل — جمع‌وجور")

from bale_api import kb_profile

_k = kb_profile(False, "draft")
_rows = _k["inline_keyboard"]
check("۵ ردیف یا کمتر", len(_rows) <= 5, f"{len(_rows)} ردیف")
_all = _btn_texts(_k)
check("حداکثر ۱۰ دکمه", len(_all) <= 10, f"{len(_all)}")
check("دکمهٔ عکس جدا حذف شد",
      not any("عکس" in b for b in _all), f"{_all}")
check("تکمیل پروفایل هست", any("تکمیل پروفایل" in b for b in _all))
check("گواهینامه هست", any("گواهینامه" in b for b in _all))
check("بلیت هست", any("بلیت" in b for b in _all))
check("باشگاه هست", any("باشگاه" in b for b in _all))
check("پشتیبانی هست", any("پشتیبانی" in b for b in _all))
check("بازگشت هست", any("منوی اصلی" in b for b in _all))

_k2 = kb_profile(True, "approved")
_all2 = _btn_texts(_k2)
check("حالت تأییدشده → ویرایش",
      any("ویرایش پروفایل" in b for b in _all2))
check("با عکس هم دکمهٔ حذف عکس نیست",
      not any("حذف عکس" in b for b in _all2))

# نشان‌ها
_k3 = kb_profile(False, "draft", {"certs": 3, "tickets": 2, "tk": 1})
_all3 = _btn_texts(_k3)
check("نشان گواهینامه", any("(3)" in b for b in _all3), f"{_all3}")
check("نشان بلیت", any("(2)" in b for b in _all3))
check("نشان صفر نشان داده نمی‌شود",
      not any("(0)" in b for b in _btn_texts(
          kb_profile(False, "draft", {"certs": 0}))))

# همهٔ دکمه‌ها هندلر دارند
_mn = SRC["main.py"]
for r in _rows:
    for b in r:
        cb = b.get("callback_data", "")
        check(f"هندلر {cb}", f'"{cb}"' in _mn, cb)

# فروشگاه و رتبه‌بندی داخل باشگاه در دسترس‌اند
check("فروشگاه در باشگاه", '"cl_shop"' in SRC["club.py"])
check("رتبه‌بندی در باشگاه", '"cl_board"' in SRC["club.py"])

# ══════════════════════════════════════════════════════════
print("[۷] 📋 نمایش پروفایل — فقط فیلدهای فعال")

# 🧪 کاربری با اطلاعات پر — تا گروه‌ها سطر به سطر چاپ شوند
#    (گروهِ کاملاً خالی فقط یک خط خلاصه می‌گیرد)
database.db_execute("DELETE FROM users WHERE bale_user_id=77001")
database.db_execute(
    "INSERT INTO users (bale_user_id, first_name, last_name, "
    "national_id, birth_date, gender, father_name, mother_name, "
    "province, city, address, postal_code, education_level, "
    "field_of_study, university, job_title, company_name, email, "
    "bio, profile_status) VALUES "
    "(77001,'رضا','کریمی','0012345679','1370/01/15','مرد','حسن',"
    "'مریم','تهران','تهران','خیابان آزادی','1234567890','کارشناسی',"
    "'کامپیوتر','شریف','برنامه‌نویس','نورا','r@x.com','سلام',"
    "'draft')")

# همه روشن
SENT.clear()
pf.show_profile(77001, 77001)
_full = _last()
check("پروفایل نمایش داده شد", "پروفایل من" in _full)


def _field_rows(txt):
    """فقط سطرهای فیلد پروفایل — نه بخش آمار"""
    out = 0
    for ln in txt.split("\n"):
        if ("├──" in ln or "└──" in ln) and \
                not any(w in ln for w in ("امتیاز", "رویدادها",
                                          "گواهینامه", "آمادهٔ")):
            out += 1
    return out


_n_all = _field_rows(_full)

# چند فیلد را خاموش کن
for k in ("postal_code", "mother_name", "university", "company_name"):
    database.set_setting(f"pf_{k}_on", "0", "", "profile")
SENT.clear()
pf.show_profile(77001, 77001)
_less = _last()
_n_less = _field_rows(_less)
check("فیلدهای خاموش حذف شدند", _n_less < _n_all,
      f"{_n_all} → {_n_less}")
check("کد پستی دیگر نیست", "کد پستی" not in _less)
check("نام مادر دیگر نیست", "نام مادر" not in _less)
for k in ("postal_code", "mother_name", "university", "company_name"):
    database.set_setting(f"pf_{k}_on", "1", "", "profile")

check("وضعیت عکس در متن هست", "عکس پروفایل" in _last())

# ══════════════════════════════════════════════════════════
print("[۸] 🔒 اجباری‌بودن رسانه واقعاً اثر دارد")

from auth import set_state as _ss2, get_state_data

# 🧹 بقیهٔ فیلدهای اجباری را موقتاً اختیاری کن تا فقط
#    رفتار «عکس اجباری» سنجیده شود.
_REQ_OFF = ("national_id", "birth_date", "province", "city",
            "gender", "father_name", "address", "postal_code")
for _k in _REQ_OFF:
    database.set_setting(f"pf_{_k}_req", "0", "", "profile")
database.set_setting("pf_profile_photo_req", "1", "", "profile")
database.db_execute(
    "UPDATE users SET profile_photo=NULL WHERE bale_user_id=?",
    (77001,))

_ss2(77001, pf.STATE_FORM,
     {"first_name": "رضا", "last_name": "کریمی", "step": 99},
     merge=False)
def _blocked():
    """متن پیام «فیلدهای اجباری خالی» — اگر آمده باشد"""
    for s in SENT:
        t = s["params"].get("text", "") if s["method"] == "sendMessage" \
            else ""
        if "فیلدهای اجباری خالی" in t:
            return t
    return ""


SENT.clear()
pf.submit_profile(77001, 77001)
_msg = _blocked()
check("🔑 عکس اجباری بدون عکس → جلوگیری شد",
      "عکس پروفایل" in _msg, _msg[:90])

# با عکس → عبور می‌کند
import tempfile
_tmp = tempfile.mkdtemp(prefix="p38_")
_pp = os.path.join(_tmp, "u.png")
try:
    from PIL import Image
    Image.new("RGB", (80, 80), (100, 150, 100)).save(_pp)
except ImportError:
    open(_pp, "wb").write(b"x")
database.db_execute(
    "UPDATE users SET profile_photo=? WHERE bale_user_id=?",
    (_pp, 77001))
_ss2(77001, pf.STATE_FORM,
     {"first_name": "رضا", "last_name": "کریمی", "step": 99},
     merge=False)
SENT.clear()
pf.submit_profile(77001, 77001)
_msg2 = _blocked()
check("با عکس → دیگر مانع نیست",
      "عکس پروفایل" not in _msg2, _msg2[:90])
database.set_setting("pf_profile_photo_req", "0", "", "profile")

# پارامتر سفارشی اجباری
database.set_setting(f"pf_{_new['key']}_req", "1", "", "profile")
_ss2(77001, pf.STATE_FORM,
     {"first_name": "رضا", "last_name": "کریمی", "step": 99},
     merge=False)
SENT.clear()
pf.submit_profile(77001, 77001)
_msg3 = _blocked()
check("🔑 پارامتر سفارشی اجباری هم بررسی می‌شود",
      "کد پرسنلی" in _msg3, _msg3[:90])
database.set_setting(f"pf_{_new['key']}_req", "0", "", "profile")
for _k in _REQ_OFF:
    database.db_execute("DELETE FROM settings WHERE key=?",
                        (f"pf_{_k}_req",))
from database import clear_settings_cache as _csc
_csc()
clear_state(77001)

# ══════════════════════════════════════════════════════════
print("[۹] 📸 دریافت عکس در جریان فرم")

check("تابع handle_form_photo هست", hasattr(pf, "handle_form_photo"))
check("تابع مشترک _save_photo_file", hasattr(pf, "_save_photo_file"))
check("در main وصل است",
      "profile_mod.handle_form_photo" in _mn)

# بدون state فرم → رد می‌کند
check("بدون فرم رد می‌شود",
      pf.handle_form_photo({"from": {"id": 77001},
                            "chat": {"id": 77001},
                            "photo": [{"file_id": "x"}]}) is False)

# در مرحلهٔ متنی → رد می‌کند
_steps = pf.active_steps()
_ti = next(i for i, s in enumerate(_steps)
           if not pf.is_media_step(s) and s["key"] != "full_name")
_ss2(77001, pf.STATE_FORM, {"step": _ti}, merge=False)
check("در مرحلهٔ متنی عکس رد می‌شود",
      pf.handle_form_photo({"from": {"id": 77001},
                            "chat": {"id": 77001},
                            "photo": [{"file_id": "x"}]}) is False)
clear_state(77001)

# متن در مرحلهٔ رسانه‌ای → پیام راهنما
_mi = next((i for i, s in enumerate(_steps)
            if pf.is_media_step(s)), None)
check("مرحلهٔ رسانه‌ای وجود دارد", _mi is not None)
if _mi is not None:
    _ss2(77001, pf.STATE_FORM, {"step": _mi}, merge=False)
    SENT.clear()
    pf.handle_form_input({"from": {"id": 77001},
                          "chat": {"id": 77001},
                          "text": "یک متن"})
    check("متن در مرحلهٔ رسانه رد شد",
          "بفرستید" in _last(), _last()[:60])
    clear_state(77001)

# ── متن پرسش رسانه‌ای درست ساخته می‌شود ──
if _mi is not None:
    _ss2(77001, pf.STATE_FORM, {"step": _mi}, merge=False)
    SENT.clear()
    pf.ask_step(77001, 77001, _mi)
    _q = _last()
    check("پرسش رسانه‌ای نمایش داده شد", "مرحله" in _q)
    check("نوع فایل ذکر شده",
          any(w in _q for w in ("عکس", "فایل", "صدا", "ویدیو")))
    clear_state(77001)

# ══════════════════════════════════════════════════════════
print("[۱۰] 🧩 استحکام")

check("prompt_of با کلید ناموجود",
      pf.prompt_of("nope_xyz", "d") == "d")
check("field_on با کلید ناموجود امن است",
      isinstance(pf.field_on("nope_xyz"), bool))
check("get_extra ناموجود → پیش‌فرض",
      pf.get_extra(99999, "nope", "d") == "d")
pf.set_extra(77001, "test_k", "مقدار")
check("set/get_extra کار می‌کند",
      pf.get_extra(77001, "test_k") == "مقدار")
pf.set_extra(77001, "test_k", "تازه")
check("مقدار بازنویسی می‌شود",
      pf.get_extra(77001, "test_k") == "تازه")

_before = len(pf.custom_fields())
ad.del_param(1, 1, _med.get("key"))
check("حذف پارامتر کار می‌کند",
      len(pf.custom_fields()) == _before - 1)
check("حذف‌شده از مراحل رفت",
      not any(s["key"] == _med.get("key")
              for s in pf.active_steps()))

try:
    ad.show_param_edit(1, 1, "")
    check("کلید خالی خطا نمی‌دهد", True)
except Exception as e:
    check(f"کلید خالی نباید خطا بدهد ({e})", False)

# ══════════════════════════════════════════════════════════
print("[۱۱] 🔗 روتر و یکپارچگی")

for cb in ("pfv_", "pfq_", "pfqr_", "pfnew_", "pfnm_"):
    check(f"روتر {cb}", f'"{cb}' in _mn, cb)
check("ترتیب pfnm قبل از pfnew",
      _mn.index('startswith("pfnm_")') <
      _mn.index('startswith("pfnew_")'))
check("state ها در روتر", "STATE_PF_TEXT" in _mn)
check("عکس فرم در روتر", "handle_form_photo" in _mn)

check("درصد تکمیل عکس را می‌شمارد",
      "profile_photo" in SRC["auth.py"])

# هیچ ارجاع شکسته‌ای به دکمهٔ حذف‌شده نماند
check("profile_photo_del هنوز هندلر دارد (از جای دیگر)",
      '"profile_photo_del"' in _mn)

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
